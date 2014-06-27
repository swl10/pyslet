#! /usr/bin/env python

import unittest
import logging
import StringIO
import socket


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(HTTP2617Tests, 'test')  # ,
        #		unittest.makeSuite(MoreTests,'test')
    ))


from pyslet.rfc2617 import *
import test_rfc2616 as http

import random
import os
import sys

TEST_STRING = "The quick brown fox jumped over the lazy dog"

TEST_SERVER_1 = {
    "GET / HTTP/1.1\r\nHost: www.domain1.com": "HTTP/1.1 401 Who are you?\r\nWWW-Authenticate: Basic realm=\"RFC2617\"\r\nContent-Length: %i\r\n\r\n%s" % (len(TEST_STRING), TEST_STRING),
    "GET / HTTP/1.1\r\nAuthorization: Basic dXNlcjpQYXNzd29yZA==\r\nHost: www.domain1.com": "HTTP/1.1 200 You got it!\r\nContent-Length: %i\r\n\r\n%s" % (len(TEST_STRING), TEST_STRING),
}

TEST_SERVER_2 = {
    "HEAD / HTTP/1.1\r\nHost: www.domain2.com": "HTTP/1.1 301 Moved\r\nLocation: http://www.domain1.com/\r\n\r\n"
}

TEST_SERVER = {
    'www.domain1.com': TEST_SERVER_1,
    'www.domain2.com': TEST_SERVER_2
}

BAD_REQUEST = "HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"


class FakeHTTPConnection(http.FakeHTTPConnection):

    def new_socket(self):
        http.FakeHTTPConnection.new_socket(self)
        self.responseTable = TEST_SERVER[self.host]


class FakeHTTPRequestManager(http.FakeHTTPRequestManager):
    ConnectionClass = FakeHTTPConnection


class HTTP2617Tests(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def testCaseBasicChallenge(self):
        c = BasicChallenge()
        self.assertTrue(c.scheme == "Basic", "Challenge scheme: %s" % c.scheme)
        self.assertTrue(
            c.protectionSpace is None, "Challenge protection space: %s" % c.protectionSpace)
        self.assertTrue(
            c["realm"] == "Default", "Initial challenge realm: %s" % c["realm"])
        c = BasicChallenge.FromString('Basic realm="Firewall"')
        self.assertTrue(
            c["realm"] == "Firewall", "Parsed realm: %s" % c["realm"])
        self.assertTrue(
            str(c) == 'Basic realm="Firewall"', "Format challenge: %s" % repr(str(c)))

    def testCaseBasicCredentials(self):
        c = BasicCredentials()
        self.assertTrue(
            c.scheme == "Basic", "Credential scheme: %s" % c.scheme)
        self.assertTrue(c.protectionSpace is None,
                        "Initial credential protected space: %s" % c.protectionSpace)
        self.assertTrue(
            c.realm is None, "Initial credential realm: %s" % c.realm)
        c.SetBasicCredentials('dXNlcjpQYXNzd29yZA==')
        self.assertTrue(c.userid == "user", "User name: %s" % c.userid)
        self.assertTrue(c.password == "Password", "Password: %s" % c.userid)
        self.assertTrue(
            str(c) == 'Basic dXNlcjpQYXNzd29yZA==', "Format credentials")

    def testCaseBasicPaths(self):
        c = BasicCredentials()
        self.assertTrue(len(c.pathPrefixes) == 0, "No prefixes initially")
        c.AddSuccessPath("/website/private/document")
        self.assertTrue(len(c.pathPrefixes) == 1, "One path")
        self.assertTrue(
            c.TestPath("/website/private/document"), "Simple match")
        self.assertFalse(
            c.TestPath("/website/private/document.doc"), "No match with segment extension")
        self.assertFalse(
            c.TestPath("/website/private/"), "Simple match doesn't apply to parent")
        c.AddSuccessPath("/website/private/document2")
        self.assertTrue(len(c.pathPrefixes) == 2, "Two paths, no common root")
        self.assertTrue(
            c.TestPath("/website/private/document"), "Simple match")
        self.assertTrue(
            c.TestPath("/website/private/document2"), "Simple match")
        self.assertFalse(
            c.TestPath("/website/private/"), "Simple match doesn't apply to parent")
        c.AddSuccessPath("/website/~user/secrets")
        self.assertTrue(
            len(c.pathPrefixes) == 3, "Three paths, no common root")
        c.AddSuccessPath("/website/private/")
        self.assertTrue(
            len(c.pathPrefixes) == 2, "Reduced to two paths with common root")
        self.assertTrue(
            c.TestPath("/website/private/document"), "Simple match")
        self.assertTrue(
            c.TestPath("/website/private/document2"), "Simple match")
        self.assertFalse(c.TestPath(
            "/website/private"), "Simple match doesn't apply to parent (without redirect)")
        c.AddSuccessPath("/website")
        self.assertTrue(
            len(c.pathPrefixes) == 1, "Reduced to one paths with common root (no slash)")
        self.assertTrue(
            c.TestPath("/website/private/document"), "Simple match")
        self.assertTrue(
            c.TestPath("/website/private/document2"), "Simple match")
        self.assertTrue(c.TestPath("/website/"), "Simple match with slash")
        self.assertTrue(c.TestPath("/website"), "Simple match without slash")
        self.assertFalse(
            c.TestPath("/websites"), "No match with segment extension")

    def testCase401(self):
        rm = FakeHTTPRequestManager()
        rm.httpUserAgent = None
        request1 = http.HTTPRequest("http://www.domain1.com/")
        rm.QueueRequest(request1)
        # ThreadLoop will process the queue until it blocks for more than the
        # timeout (default, 60s)
        rm.ThreadLoop()
        response1 = request1.response
        self.assertTrue(
            response1.status == 401, "Status in response1: %i" % response1.status)
        self.assertTrue(response1.reason == "Who are you?",
                        "Reason in response1: %s" % response1.reason)
        self.assertTrue(
            request1.resBody == TEST_STRING, "Data in response1: %s" % request1.resBody)
        challenges = response1.GetWWWAuthenticate()
        self.assertTrue(len(challenges) == 1 and isinstance(
            challenges[0], BasicChallenge), "Challenge")
        c = BasicCredentials()
        c.protectionSpace = "http://www.domain1.com"
        c.realm = None		# should match all realms!
        c.userid = 'user'
        c.password = 'Password'
        rm.AddCredentials(c)
        request2 = http.HTTPRequest("http://www.domain1.com/")
        rm.QueueRequest(request2)
        rm.ThreadLoop()
        response2 = request2.response
        self.assertTrue(str(response2.protocolVersion) == "HTTP/1.1",
                        "Protocol in response1: %s" % response1.protocolVersion)
        self.assertTrue(
            response2.status == 200, "Status in response1: %i" % response1.status)
        self.assertTrue(response2.reason == "You got it!",
                        "Reason in response1: %s" % response1.reason)
        self.assertTrue(
            request2.resBody == TEST_STRING, "Data in response1: %s" % request1.resBody)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
