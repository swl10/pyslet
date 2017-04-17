#! /usr/bin/env python

import unittest
import logging

import pyslet.http.messages as messages
import pyslet.http.client as client
from test_http_client import MockClientWrapper

from pyslet.http.auth import *        # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(HTTP2617Tests, 'test'),
        # unittest.makeSuite(MoreTests,'test')
    ))


TEST_STRING = b"The quick brown fox jumped over the lazy dog"


class HTTP2617Tests(unittest.TestCase):

    def setUp(self):        # noqa
        self.client = MockClientWrapper(self.run_manager, max_connections=3)
        self.client.httpUserAgent = None

    def tearDown(self):     # noqa
        self.client.close()

    def run_domain1(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                # check the authorization header
                credentials = req.get_authorization()
                if (isinstance(credentials, BasicCredentials) and
                        credentials.userid == "user" and
                        credentials.password == "Password"):
                    response = messages.Response(req, entity_body=TEST_STRING)
                    response.set_status(200, "You got it!")
                else:
                    challenge = BasicChallenge(('realm', b"RFC2617", True))
                    response = messages.Response(req)
                    response.set_status(401, "Who are you?")
                    # response.set_content_length(0)
                    response.set_www_authenticate([challenge])
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain1")
            sock.send_response(response)

    def run_domain2(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if req.method in ("HEAD", "GET"):
                response = messages.Response(req, entity_body=None)
                response.set_status(301, "Moved")
                response.set_location("http://www.domain1.com/")
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain2")
            sock.send_response(response)

    def run_manager(self, host, port, sock):
        # read some data from sock, and post a response
        if host == "www.domain1.com" and port == 80:
            self.run_domain1(sock)
        elif host == "www.domain2.com" and port == 80:
            self.run_domain2(sock)
        else:
            # connection error
            raise ValueError("run_manager: bad host in connect")

    def test_basic_challenge(self):
        c = BasicChallenge()
        self.assertTrue(c.scheme == "Basic", "Challenge scheme: %s" % c.scheme)
        self.assertTrue(c.protectionSpace is None,
                        "Challenge protection space: %s" % c.protectionSpace)
        self.assertTrue(c["realm"] == b"Default",
                        "Initial challenge realm: %s" % c["realm"])
        c = BasicChallenge.from_str('Basic realm="Firewall"')
        self.assertTrue(
            c["realm"] == b"Firewall", "Parsed realm: %s" % c["realm"])
        self.assertTrue(str(c) == 'Basic realm="Firewall"',
                        "Format challenge: %s" % repr(str(c)))

    def test_basic_credentials(self):
        c = BasicCredentials()
        self.assertTrue(
            c.scheme == "Basic", "Credential scheme: %s" % c.scheme)
        self.assertTrue(c.protectionSpace is None,
                        "Initial credential protected space: %s" %
                        c.protectionSpace)
        self.assertTrue(
            c.realm is None, "Initial credential realm: %s" % c.realm)
        c.set_basic_credentials('dXNlcjpQYXNzd29yZA==')
        self.assertTrue(c.userid == "user", "User name: %s" % c.userid)
        self.assertTrue(c.password == "Password", "Password: %s" % c.userid)
        self.assertTrue(
            str(c) == 'Basic dXNlcjpQYXNzd29yZA==', "Format credentials")

    def test_basic_session(self):
        challenge_a = BasicChallenge(("realm", b"TestRealmA", True))
        challenge_b = BasicChallenge(("realm", b"TestRealmB", True))
        challenge_unknown = Challenge("Unknown")
        c = BasicCredentials()
        # any realm
        c.user = "user"
        c.password = "Password"
        self.assertTrue(c.base is None)
        # trade base credentials for new credentials (pre-emptive)
        c1 = c.get_response()
        self.assertTrue(c1 is not c)
        self.assertTrue(c1.base is c)
        # still applies to any realm
        self.assertTrue(c1.realm is None)
        self.assertTrue(str(c1) == str(c))
        # no further challenge returns the same credentials
        c2 = c1.get_response()
        self.assertTrue(c2 is c1)
        self.assertTrue(c1.base is c)
        self.assertTrue(c1.realm is None)
        self.assertTrue(str(c1) == str(c))
        # any further challenge means credentials are rejected
        self.assertTrue(c1.get_response(challenge_a) is None)
        self.assertTrue(c1.get_response(challenge_unknown) is None)
        # trade base credentials for new credentials in response to A
        c1 = c.get_response(challenge_a)
        self.assertTrue(c1 is not c)
        self.assertTrue(c1.base is c)
        # now applies specifically to the realm of the challenge
        self.assertTrue(c1.realm == b"TestRealmA", repr(c1.realm))
        self.assertTrue(str(c1) == str(c))
        # no further challenge returns the same credentials
        c2 = c1.get_response()
        self.assertTrue(c2 is c1)
        self.assertTrue(c1.base is c)
        self.assertTrue(c1.realm == b"TestRealmA")
        self.assertTrue(str(c1) == str(c))
        # any further challenge means credentials are rejected
        self.assertTrue(c1.get_response(challenge_a) is None)
        self.assertTrue(c1.get_response(challenge_b) is None)
        self.assertTrue(c1.get_response(challenge_unknown) is None)
        # trade in response to mismatched scheme
        self.assertTrue(c.get_response(challenge_unknown) is None)
        # now upgrade our base credentials to be realm-specific
        c.realm = b"TestRealmA"
        # trade pre-emptively
        c1 = c.get_response()
        self.assertTrue(c1 is not c)
        self.assertTrue(c1.base is c)
        self.assertTrue(c1.realm == b"TestRealmA")
        self.assertTrue(str(c1) == str(c))
        # trade in response to A
        c1 = c.get_response(challenge_a)
        self.assertTrue(c1 is not c)
        self.assertTrue(c1.base is c)
        self.assertTrue(c1.realm == b"TestRealmA")
        self.assertTrue(str(c1) == str(c))
        # trade in response to mismatched realm
        self.assertTrue(c.get_response(challenge_b) is None)
        # trade in response to mismatched scheme
        self.assertTrue(c.get_response(challenge_unknown) is None)

    def test_basicpaths(self):
        c = BasicCredentials()
        self.assertTrue(len(c.path_prefixes) == 0, "No prefixes initially")
        c.add_success_path("/website/private/document")
        self.assertTrue(len(c.path_prefixes) == 1, "One path")
        self.assertTrue(c.test_path("/website/private/document"),
                        "Simple match")
        self.assertTrue(c.test_path("/website/private/undocument"),
                        "Match at same depth")
        self.assertTrue(c.test_path("/website/private/"),
                        "Simple match to directory at same depth")
        self.assertFalse(c.test_path("/website/private"),
                         "Simple match doesn't extend to parent")
        c.add_success_path("/website/private2/document2")
        self.assertTrue(len(c.path_prefixes) == 2, "Two paths, no common root")
        self.assertTrue(
            c.test_path("/website/private/document"), "Simple match")
        self.assertTrue(
            c.test_path("/website/private2/document2"), "Simple match")
        self.assertFalse(c.test_path("/website/private2"),
                         "Simple match doesn't apply to parent")
        c.add_success_path("/internal/~user/secrets")
        self.assertTrue(
            len(c.path_prefixes) == 3, "Three paths, no common root")
        c.add_success_path("/website/private")
        self.assertTrue(
            len(c.path_prefixes) == 2, "Reduced to two paths with common root")
        self.assertTrue(
            c.test_path("/website/private/document"), "Simple match")
        self.assertTrue(
            c.test_path("/website/private2/document2"), "Simple match")
        self.assertFalse(c.test_path("/website"),
                         "Simple match doesn't apply to parent "
                         "(without redirect)")
        c.add_success_path("/website")
        self.assertTrue(len(c.path_prefixes) == 1,
                        "Reduced to one path with common root (no slash)")
        self.assertTrue(
            c.test_path("/website/private/document"), "Simple match")
        self.assertTrue(
            c.test_path("/website/private2/document2"), "Simple match")
        self.assertTrue(c.test_path("/website/"), "Simple match with slash")
        self.assertTrue(c.test_path("/website"), "Simple match without slash")
        self.assertFalse(
            c.test_path(""), "Degenerate case, empty path")

    def test_401(self):
        request1 = client.ClientRequest("http://www.domain1.com/")
        self.client.queue_request(request1)
        # thread_loop will process the queue until it blocks for more
        # than the timeout (default, 60s)
        self.client.thread_loop()
        response1 = request1.response
        self.assertTrue(response1.status == 401,
                        "Status in response1: %i" % response1.status)
        self.assertTrue(response1.reason == "Who are you?",
                        "Reason in response1: %s" % response1.reason)
        self.assertTrue(request1.res_body == b'',
                        "Data in response1: %s" % request1.res_body)
        challenges = response1.get_www_authenticate()
        self.assertTrue(len(challenges) == 1 and isinstance(
            challenges[0], BasicChallenge), "Challenge")
        c = BasicCredentials()
        c.protectionSpace = "http://www.domain1.com"
        c.realm = None		# should match all realms!
        c.userid = 'user'
        c.password = 'Password'
        self.client.add_credentials(c)
        request2 = client.ClientRequest("http://www.domain1.com/")
        self.client.queue_request(request2)
        self.client.thread_loop()
        response2 = request2.response
        self.assertTrue(str(response2.protocol) == "HTTP/1.1",
                        "Protocol in response1: %s" % response1.protocol)
        self.assertTrue(response2.status == 200,
                        "Status in response1: %i" % response1.status)
        self.assertTrue(response2.reason == "You got it!",
                        "Reason in response1: %s" % response1.reason)
        self.assertTrue(request2.res_body == TEST_STRING,
                        "Data in response1: %s" % request1.res_body)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
