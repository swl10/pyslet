#! /usr/bin/env python

import base64
import logging
import random
import unittest

from pyslet.http import auth, client, messages
from pyslet.http.ntlmauth import (
    NegotiateChallenge,
    NTLMChallenge,
    NTLMCredentials,
    NTLMParsedCredentials)
from pyslet.py2 import (
    byte,
    join_bytes,
    range3
    )

from test_http_client import MockClientWrapper


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(NTLMChallengeTests, 'test'),
        unittest.makeSuite(NTLMCredentialTests, 'test'),
        unittest.makeSuite(NTLMTests, 'test'),
        # unittest.makeSuite(MoreTests,'test')
    ))


TEST_STRING = b"The quick brown fox jumped over the lazy dog"


class NTLMChallengeTests(unittest.TestCase):

    def test_constructor(self):
        challenge = NTLMChallenge()
        self.assertTrue(isinstance(challenge, auth.Challenge))
        self.assertTrue(challenge.scheme == "NTLM")
        # the challenge realm is omitted
        self.assertTrue("realm" not in challenge)
        self.assertTrue(challenge.auth_data is None)
        # and it is formatted without a realm parameter
        self.assertTrue(str(challenge) == "NTLM", str(challenge))
        # example challenge from
        # https://www.innovation.ch/personal/ronald/ntlm.html
        c_example = b'TlRMTVNTUAACAAAAAAAAACgAAAABggAAU3J2Tm9uY2UAAAAAAAAAAA=='
        challenge = NTLMChallenge(c_example)
        self.assertTrue("realm" not in challenge)
        self.assertTrue(challenge.auth_data == c_example)
        self.assertTrue(str(challenge) ==
                        "NTLM %s" % c_example.decode('ascii'), str(challenge))

    def test_parser(self):
        challenge = auth.Challenge.from_str("NTLM")
        self.assertTrue(isinstance(challenge, auth.Challenge))
        self.assertTrue(challenge.scheme == "NTLM")
        self.assertTrue("realm" not in challenge)
        self.assertTrue(challenge.auth_data is None)
        self.assertTrue(str(challenge) == "NTLM", str(challenge))
        c_example = 'TlRMTVNTUAACAAAAAAAAACgAAAABggAAU3J2Tm9uY2UAAAAAAAAAAA=='
        challenge = auth.Challenge.from_str("NTLM %s" % c_example)
        self.assertTrue("realm" not in challenge)
        self.assertTrue(challenge.auth_data == c_example.encode('ascii'))
        self.assertTrue(str(challenge) == "NTLM %s" % c_example)

    def test_repr(self):
        challenge = NTLMChallenge()
        self.assertTrue(repr(challenge) == "NTLMChallenge()")
        c_example = b'TlRMTVNTUAACAAAAAAAAACgAAAABggAAU3J2Tm9uY2UAAAAAAAAAAA=='
        challenge = NTLMChallenge(c_example)
        self.assertTrue(repr(challenge) ==
                        "NTLMChallenge(%s)" % repr(c_example))


def mock_challenge():
    data = [byte(0)] * 56
    data[0:7] = list(b"NTLMSSP")
    data[8] = byte(2)
    data[16] = byte(56)
    data[20] = byte(1)
    data[21] = byte(0x82)
    for i in range3(8):
        data[24 + i] = byte(random.randint(0, 255))
    return join_bytes(data)


class NTLMCredentialTests(unittest.TestCase):

    def test_constructor(self):
        c = NTLMCredentials()
        self.assertTrue(
            c.scheme == "NTLM", "Credential scheme: %s" % c.scheme)
        self.assertTrue(c.protectionSpace is None,
                        "Initial credential protected space: %s" %
                        c.protectionSpace)
        self.assertTrue(
            c.realm is None, "Initial credential realm: %s" % c.realm)
        c.set_ntlm_credentials('user', 'Password')
        self.assertTrue(c.userid == "user", "User name: %s" % c.userid)
        self.assertTrue(c.password == "Password", "Password: %s" % c.password)
        self.assertTrue(c.domain == "", "Domain: %s" % c.domain)
        try:
            str(c)
            self.fail("str(NTLM base credentials)")
        except ValueError:
            pass

    def test_domain(self):
        c = NTLMCredentials()
        c.set_ntlm_credentials('mydomain\\user', 'Password')
        self.assertTrue(c.userid == "user", "User name: %s" % c.userid)
        self.assertTrue(c.password == "Password", "Password: %s" % c.password)
        self.assertTrue(c.domain == "MYDOMAIN", "Domain: %s" % c.domain)

    def test_session(self):
        challenge = NTLMChallenge()
        challenge_unknown = auth.Challenge("Unknown")
        c = NTLMCredentials()
        c.set_ntlm_credentials('user', 'Password')
        self.assertTrue(c.base is None)
        # trade base credentials for new credentials (pre-emptive)
        c1 = c.get_response()
        self.assertTrue(c1 is not c,
                        "Should result in a type-1 negotiate message")
        self.assertTrue(c1.base is c, "base set")
        header = str(c1)
        self.assertTrue(header.startswith("NTLM "))
        header = header.split()
        self.assertTrue(len(header) == 2, "negotiate message two fields")
        msg = base64.b64decode(header[1])
        self.assertTrue(msg.startswith(b"NTLMSSP\x00\x01\x00\x00\x00"),
                        "negotiate message")
        # trade base credentials in response to plain NTLM challenge
        c2 = c.get_response(challenge)
        self.assertTrue(c2 is not c,
                        "Should result in a type-1 negotiate message")
        self.assertTrue(c2.base is c, "base set")
        self.assertTrue(str(c2) == str(c1), "type-1 message")
        # unknown challenge does not match these credentials
        c3 = c.get_response(challenge_unknown)
        self.assertTrue(c3 is None, "does not match unknown challenge")
        # a repeated plain challenge is a failure
        c2 = c1.get_response(challenge)
        self.assertTrue(c2 is None, "Repeated plain challenge is a failure")
        # now construct a type-2 challenge
        data = mock_challenge()
        challenge2 = NTLMChallenge(base64.b64encode(data))
        c2 = c1.get_response(challenge2)
        self.assertTrue(c2 is not c1)
        self.assertTrue(c2 is not c)
        self.assertTrue(c2.base is c, "base set")
        header = str(c2)
        self.assertTrue(header.startswith("NTLM "))
        header = header.split()
        self.assertTrue(len(header) == 2, "authenticate message two fields")
        msg = base64.b64decode(header[1])
        self.assertTrue(msg.startswith(b"NTLMSSP\x00\x03\x00\x00\x00"),
                        "authenticate message")
        c3 = c1.get_response()
        self.assertTrue(c3 is None)
        c3 = c1.get_response(challenge)
        self.assertTrue(c3 is None)
        c3 = c1.get_response(challenge_unknown)
        self.assertTrue(c3 is None)
        # the type3 authenticate message must not be challenged
        c3 = c2.get_response()
        self.assertTrue(c3 is None)
        c3 = c2.get_response(challenge)
        self.assertTrue(c3 is None)
        c3 = c2.get_response(challenge_unknown)
        self.assertTrue(c3 is None)
        c3 = c2.get_response(challenge2)
        self.assertTrue(c3 is None, "repeated type-2 challenge not allowed")


class NTLMTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.client = MockClientWrapper(self.run_manager, max_connections=3)
        self.client.httpUserAgent = None
        self.ntlm_state = 1

    def tearDown(self):     # noqa
        self.client.close()

    def run_domain1(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                # check the authorization header
                logging.debug("Received headers: %s", repr(req.headers))
                credentials = req.get_authorization()
                logging.debug("Parsed Authorization: %s", str(credentials))
                if (isinstance(credentials, NTLMParsedCredentials)):
                    if credentials.msg[8] == byte(1) and self.ntlm_state == 1:
                        # negotiate message
                        data = mock_challenge()
                        challenge = NTLMChallenge(base64.b64encode(data))
                        response = messages.Response(req)
                        response.set_status(401, "Who are you?")
                        # response.set_content_length(0)
                        response.set_www_authenticate([challenge])
                        self.ntlm_state = 3
                    elif credentials.msg[8] == byte(3) and \
                            self.ntlm_state == 3:
                        # authenticate message
                        response = messages.Response(
                            req, entity_body=TEST_STRING)
                        response.set_status(200, "You got it!")
                        self.ntlm_state = 0
                    else:
                        response.set_status(403, "Who are you?")
                        # response.set_content_length(0)
                        self.ntlm_state = 0
                else:
                    challenge = NTLMChallenge()
                    response = messages.Response(req)
                    response.set_status(401, "Who are you?")
                    # response.set_content_length(0)
                    response.set_www_authenticate([challenge])
                    self.ntlm_state = 1
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain1")
                self.ntlm_state = 1
            sock.send_response(response)

    def run_domain2(self, sock):
        negotiate = NegotiateChallenge()
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                # check the authorization header
                logging.debug("Received headers: %s", repr(req.headers))
                credentials = req.get_authorization()
                logging.debug("Parsed Authorization: %s", str(credentials))
                if (isinstance(credentials, NTLMParsedCredentials)):
                    if credentials.msg[8] == byte(1) and self.ntlm_state == 1:
                        # negotiate message
                        data = mock_challenge()
                        challenge = NTLMChallenge(base64.b64encode(data))
                        response = messages.Response(req)
                        response.set_status(401, "Who are you?")
                        # response.set_content_length(0)
                        response.set_www_authenticate([negotiate, challenge])
                        self.ntlm_state = 3
                    elif credentials.msg[8] == byte(3) and \
                            self.ntlm_state == 3:
                        # authenticate message
                        response = messages.Response(
                            req, entity_body=TEST_STRING)
                        response.set_status(200, "You got it!")
                        self.ntlm_state = 0
                    else:
                        response.set_status(403, "Who are you?")
                        # response.set_content_length(0)
                        self.ntlm_state = 0
                else:
                    challenge = NTLMChallenge()
                    response = messages.Response(req)
                    response.set_status(401, "Who are you?")
                    # response.set_content_length(0)
                    response.set_www_authenticate([negotiate, challenge])
                    self.ntlm_state = 1
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain1")
                self.ntlm_state = 1
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

    def test_ntlm_session(self):
        request1 = client.ClientRequest("http://www.domain1.com/")
        self.client.queue_request(request1)
        # thread_loop will process the queue until it blocks for more
        # than the timeout (default, 60s)
        self.client.thread_loop()
        response1 = request1.response
        self.assertTrue(response1.status == 401,
                        "Status in response1: %i" % response1.status)
        challenges = response1.get_www_authenticate()
        self.assertTrue(len(challenges) == 1 and isinstance(
            challenges[0], NTLMChallenge), "Challenge")
        c = NTLMCredentials()
        c.set_ntlm_credentials('mydomain\\user', 'Password')
        c.protectionSpace = "http://www.domain1.com"
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

    def test_ntlm_negotiate(self):
        request1 = client.ClientRequest("http://www.domain2.com/")
        self.client.queue_request(request1)
        # thread_loop will process the queue until it blocks for more
        # than the timeout (default, 60s)
        self.client.thread_loop()
        response1 = request1.response
        self.assertTrue(response1.status == 401,
                        "Status in response1: %i" % response1.status)
        challenges = response1.get_www_authenticate()
        self.assertTrue(len(challenges) == 2)
        c = NTLMCredentials()
        c.set_ntlm_credentials('mydomain\\user', 'Password')
        c.protectionSpace = "http://www.domain2.com"
        self.client.add_credentials(c)
        request2 = client.ClientRequest("http://www.domain2.com/")
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
