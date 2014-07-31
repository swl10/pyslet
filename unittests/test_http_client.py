#! /usr/bin/env python

import unittest
import logging
import threading
import random
from StringIO import StringIO

import pyslet.http.messages as messages
import pyslet.http.server as server
from test_http_server import MockSocketBase

from pyslet.http.client import *       # noqa


TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_rfc2616')

TEST_STRING = "The quick brown fox jumped over the lazy dog"

TEST_BODY = "123456\r\n\r\n"


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ClientTests, 'test'),
        unittest.makeSuite(LegacyServerTests, 'test'),
        # unittest.makeSuite(SecureTests, 'test')
    ))


class MockSocket(MockSocketBase):

    """Mocks the socket for the client"""

    def __init__(self, connection):
        super(MockSocket, self).__init__()
        # start a thread to mock the server side of the connection
        t = threading.Thread(target=connection.manager.mock_server,
                             args=(connection.host, connection.port, self))
        t.start()

    def recv_request(self):
        request = messages.Request()
        request.start_receiving()
        check_continue = False
        try:
            while True:
                if check_continue and request.get_expect_continue():
                    # push an expect response
                    self.recv_pipe.write("HTTP/1.1 100 Go on then!\r\n\r\n")
                    check_continue = False
                mode = request.recv_mode()
                if mode == messages.Message.RECV_LINE:
                    line = self.send_pipe.readmatch()
                    if line is '':
                        if request.method is None:
                            # EOF, no more requests
                            return None
                        else:
                            # EOF, unexpected
                            raise messages.HTTPException(
                                "Unexpected EOF in mock socket")
                    request.recv(line)
                elif mode == messages.Message.RECV_HEADERS:
                    lines = []
                    last_line = ''
                    while last_line != '\r\n':
                        last_line = self.send_pipe.readmatch()
                        lines.append(last_line)
                    request.recv(lines)
                    check_continue = True
                elif mode is None:
                    break
                elif mode > 0:
                    request.recv(self.send_pipe.read(mode))
                elif mode == messages.Message.RECV_ALL:
                    request.recv(self.send_pipe.read())
                else:
                    raise ValueError("unexpected recv_mode!")
        except IOError as e:
            if e.errno == errno.ETIMEDOUT:
                logging.debug("mock socket timed out while reading request")
                request = None
            else:
                raise
        return request

    def send_response(self, response):
        response.start_sending()
        try:
            self.recv_pipe.write(response.send_start())
            self.recv_pipe.write(response.send_header())
            while True:
                data = response.send_body()
                if data:
                    self.recv_pipe.write(data)
                else:
                    break
        except IOError as e:
            logging.debug("mock socket error while sending response: %s",
                          str(e))


class MockConnectionWrapper(Connection):

    def new_socket(self):
        # turn the timeout down nice and low
        self.timeout = 10
        with self.lock:
            if self.closed:
                logging.error(
                    "new_socket called on dead connection to %s", self.host)
                raise messages.HTTPException("Connection closed")
                self.socket = None
                self.socket_file = None
                self.socketSelect = select.select
            else:
                logging.info("Opening connection to %s...", self.host)
                self.socket = MockSocket(self)
                self.socket_file = self.socket
                self.socketSelect = MockSocket.wrap_select


class MockClientWrapper(Client):

    ConnectionClass = MockConnectionWrapper

    def __init__(self, mock_server, **kwargs):
        Client.__init__(self, **kwargs)
        self.socketSelect = MockSocket.wrap_select
        self.mock_server = mock_server


class ClientTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.client = MockClientWrapper(self.run_manager, max_connections=3)
        self.client.httpUserAgent = None
        self.unreliable = True

    def tearDown(self):     # noqa
        self.client.close()

    def test_simple(self):
        """simple tests

        RFC 2616:

            If the abs_path is not present in the URL, it MUST be given
            as "/" when used as a Request-URI for a resource"""
        request = ClientRequest("http://www.example.com/")
        request.start_sending()
        request_line = request.send_start()
        self.assertTrue(request_line.startswith("GET / HTTP/1."), request_line)

    def run_domain1(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                response = messages.Response(req, entity_body=TEST_STRING)
                response.set_status(200, "You got it!")
            elif req.method == "HEAD":
                response.set_content_length(len(TEST_STRING))
                response.set_status(200, "You got it!")
            elif req.method == "PUT":
                # check the request body
                response = messages.Response(req, entity_body='')
                if req.entity_body.getvalue() != TEST_BODY:
                    response.set_status(400, "PUT failed for domain1")
                    logging.debug("run_domain1: PUT %s" %
                                  repr(req.entity_body.getvalue()))
                else:
                    response.set_status(200)
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

    def run_domain5(self, sock):
        while True:
            if self.unreliable:
                self.unreliable = False
                # shutdown the socket
                logging.debug("Server hang-up before reading request")
                sock.mock_shutdown(socket.SHUT_RDWR)
                break
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                response = messages.Response(req, entity_body=TEST_STRING)
                response.set_status(200, "Thanks for your patience")
            elif req.method == "HEAD":
                response.set_content_length(len(TEST_STRING))
                response.set_status(200, "Thanks for your patience")
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain5")
            sock.send_response(response)

    def run_domain6(self, sock):
        while True:
            # shutdown the socket
            logging.debug("Server hang-up before reading request")
            sock.mock_shutdown(socket.SHUT_RDWR)
            break

    def run_manager(self, host, port, sock):
        # read some data from sock, and post a response
        if host == "www.domain1.com" and port == 80:
            self.run_domain1(sock)
        elif host == "www.domain2.com" and port == 80:
            self.run_domain2(sock)
        elif host == "www.domain3.com" and port == 80:
            # just a copy of domain1
            self.run_domain1(sock)
        elif host == "www.domain4.com" and port == 80:
            # just a copy of domain1
            self.run_domain1(sock)
        elif host == "www.domain5.com" and port == 80:
            self.run_domain5(sock)
        elif host == "www.domain6.com" and port == 80:
            self.run_domain6(sock)
        else:
            # connection error
            raise ValueError("run_manager: bad host in connect")

    def test_manager(self):
        request1 = ClientRequest("http://www.domain1.com/")
        self.assertTrue(request1.method == "GET")
        request2 = ClientRequest("http://www.domain2.com/", "HEAD")
        self.assertTrue(request2.method == "HEAD")
        self.client.queue_request(request1)
        self.client.queue_request(request2)
        # thread_loop will process the queue until it blocks for more
        # than the timeout (default, 60s)
        self.client.thread_loop(timeout=5)
        response1 = request1.response
        self.assertTrue(
            str(response1.protocol) == "HTTP/1.1",
            "Protocol in response1: %s" % response1.protocol)
        self.assertTrue(
            response1.status == 200,
            "Status in response1: %i" %
            response1.status)
        self.assertTrue(response1.reason == "You got it!",
                        "Reason in response1: %s" % response1.reason)
        self.assertTrue(
            request1.res_body == TEST_STRING,
            "Data in response1: %s" %
            request1.res_body)
        response2 = request2.response
        self.assertTrue(
            str(response2.protocol) == "HTTP/1.1",
            "Protocol in response2: %s" % response2.protocol)
        self.assertTrue(
            response2.status == 200,
            "Status in response2: %i" %
            response2.status)
        self.assertTrue(response2.reason == "You got it!",
                        "Reason in response2: %s" % response2.reason)
        self.assertTrue(request2.res_body == "",
                        "Data in response2: %s" % request2.res_body)

    def test_continue(self):
        request1 = ClientRequest(
            "http://www.domain1.com/file", "PUT",
            entity_body=TEST_BODY)
        self.assertTrue(request1.method == "PUT")
        request2 = ClientRequest(
            "http://www.domain1.com/file2", "PUT",
            entity_body=TEST_BODY)
        request2.set_expect_continue()
        self.client.queue_request(request1)
        self.client.queue_request(request2)
        # thread_loop will process the queue until it blocks for more than the
        # timeout (default, forever)
        self.client.thread_loop(timeout=5)
        response1 = request1.response
        self.assertTrue(
            response1.status == 200,
            "Status in response1: %i" %
            response1.status)
        self.assertTrue(
            response1.reason == "OK",
            "Reason in response1: %s" %
            response1.reason)
        self.assertTrue(request1.res_body == '',
                        "Data in response1: %s" % request1.res_body)
        response2 = request2.response
        self.assertTrue(
            response2.status == 200,
            "Status in response2: %i" %
            response2.status)
        self.assertTrue(
            response2.reason == "OK",
            "Reason in response2: %s" %
            response2.reason)
        self.assertTrue(request2.res_body == "",
                        "Data in response2: %s" % request2.res_body)
        # How do we test that response2 held back from sending the data before
        # the redirect?

    def test_streamed_put(self):
        request = ClientRequest(
            "http://www.domain1.com/file2",
            "PUT",
            entity_body=StringIO("123456\r\n\r\n"))
        request.set_expect_continue()
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200, "Status in response: %i" % response.status)
        self.assertTrue(
            response.reason == "OK",
            "Reason in response: %s" %
            response.reason)
        self.assertTrue(
            request.res_body == "", "Data in response: %s" % request.res_body)
        request = ClientRequest(
            "http://www.domain1.com/file",
            "PUT",
            entity_body=StringIO("123456\r\n\r\n"))
        request.set_content_length(10)
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200, "Status in response: %i" % response.status)
        self.assertTrue(
            response.reason == "OK",
            "Reason in response: %s" %
            response.reason)
        self.assertTrue(
            request.res_body == "", "Data in response: %s" % request.res_body)

    def test_streamed_get(self):
        buff = StringIO()
        request = ClientRequest(
            "http://www.domain1.com/", "GET", entity_body=None, res_body=buff)
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200, "Status in response: %i" % response.status)
        self.assertTrue(
            buff.getvalue() == TEST_STRING,
            "Data in response: %s" %
            request.res_body)
        self.assertTrue(
            request.res_body == "",
            "Data in streamed response: %s" %
            request.res_body)

    def domain3_thread_oneshot(self):
        time.sleep(1)
        logging.debug("domain3_thread_oneshot starting...")
        request = ClientRequest("http://www.domain3.com/index.txt")
        try:
            self.client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)

    def domain4_thread_oneshot(self):
        time.sleep(1)
        logging.debug("domain4_thread_oneshot starting...")
        request = ClientRequest("http://www.domain4.com/index.txt")
        try:
            self.client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)

    def test_multiget(self):
        threads = []
        for i in xrange(10):
            threads.append(
                threading.Thread(target=self.domain3_thread_oneshot))
        for i in xrange(10):
            threads.append(
                threading.Thread(target=self.domain4_thread_oneshot))
        for t in threads:
            t.start()
        while threads:
            t = threads.pop()
            t.join()
        # success criteria?  that we survived
        self.client.idle_cleanup(3)
        self.client.idle_cleanup(0)

    def test_async_close(self):
        """RFC2616:

            clients, servers, and proxies MUST be able to recover from
            asynchronous close events

            Client software SHOULD reopen the transport connection and
            retransmit the aborted sequence of requests without user
            interaction so long as the request sequence is idempotent"""
        request = ClientRequest("http://www.domain5.com/unreliable")
        # this request will timeout the first time before any data
        # has been sent to the client, it should retry and succeed
        self.client.process_request(request)
        response = request.response
        self.assertFalse(response.status is None, "No response")
        self.assertTrue(
            response.status == 200, "Status in response: %i" % response.status)
        self.assertTrue(
            response.reason == "Thanks for your patience",
            "Reason in response: %s" %
            response.reason)
        self.assertTrue(
            response.entity_body.getvalue() == TEST_STRING,
            "Body in response: %i" % response.status)
        request = ClientRequest("http://www.domain6.com/unreliable")
        # this request will always fail with a broken server
        self.client.process_request(request)
        response = request.response
        self.assertTrue(response.status is None, "No response")

    def test_kill(self):
        threads = []
        for i in xrange(10):
            threads.append(
                threading.Thread(target=self.domain3_thread_oneshot))
        for i in xrange(10):
            threads.append(
                threading.Thread(target=self.domain4_thread_oneshot))
        for t in threads:
            t.start()
        # we can't guarantee we'll find active connections unfortunately
        time.sleep(1)
        logging.info("%i active connections", self.client.active_count())
        self.client.active_cleanup(3)
        logging.info(
            "%i active connections after active_cleanup(3)",
            self.client.active_count())
        self.client.active_cleanup(0)
        logging.info(
            "%i active connections after active_cleanup(0)",
            self.client.active_count())
        while threads:
            t = threads.pop()
            t.join()


class LegacyServerTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.port = random.randint(1111, 9999)
        self.server = server.Server(port=self.port, app=self.legacy_app,
                                    protocol=params.HTTP_1p0)
        self.server.timeout = 0.5
        self.client = Client()

    def tearDown(self):     # noqa
        self.client.close()

    def run_legacy(self, nrequests):
        while nrequests:
            logging.debug("run_legacy: handling request...")
            self.server.handle_request()
            nrequests = nrequests - 1
        logging.debug("run_legacy: terminating")

    def legacy_app(self, environ, start_response):
        method = environ['REQUEST_METHOD'].upper()
        path = environ['PATH_INFO']
        content_length = environ.get('CONTENT_LENGTH', None)
        if content_length:
            content_length = int(content_length)
        else:
            content_length = 0
        logging.debug("legacy_app invoked: %s %s", method, path)
        if path == "/nochunked":
            if method == "GET":
                # just return some data
                start_response("200 OK", [])
                return ["Got it!"]
            elif method == "PUT":
                environ['wsgi.input'].read(content_length)
                start_response("204 Updated", [])
                return []
            else:
                start_resonse("500 Unexpected", [])
                return []
        else:
            start_response("404 Not Fond", [])
            return []

    def test_nochunked(self):
        """RFC2616:

            For compatibility with HTTP/1.0 applications, HTTP/1.1
            requests containing a message-body MUST include a valid
            Content-Length header field unless the server is known to be
            HTTP/1.1 compliant"""
        # TODO
        t = threading.Thread(target=self.run_legacy, args=(2,))
        t.start()
        request = ClientRequest("http://localhost:%i/nochunked" % self.port)
        self.assertTrue(request.protocol == params.HTTP_1p1)
        # start off optimistic about keep_alive
        self.assertTrue(request.keep_alive)
        self.client.process_request(request)
        self.assertTrue(request.response.status == 200)
        self.assertTrue(request.response.protocol == params.HTTP_1p0)
        # legacy server closes the connection
        self.assertFalse(request.response.keep_alive)
        # now try and make a call which would normally default to chunked
        data = "How long is a piece of string?"
        bodytext = server.Pipe(rblocking=False, timeout=10)
        bodytext.write(data)
        request = ClientRequest("http://localhost:%i/nochunked" % self.port,
                                "PUT", entity_body=bodytext)
        # we should now know that the server is 1.0, so we expect an
        # error when trying to send an unbounded entity without
        # content-length
        self.client.process_request(request)
        self.assertTrue(request.response.status is None)
        request.set_content_length(len(data))
        self.client.process_request(request)
        self.assertTrue(request.response.status == 204)
        self.assertFalse(request.response.keep_alive)


class SecureTests(unittest.TestCase):

    def test_google_insecure(self):
        client = Client()
        request = ClientRequest("https://code.google.com/p/qtimigration/")
        try:
            client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)
        client.close()

    def test_google_secure(self):
        client = Client(
            ca_certs=os.path.join(TEST_DATA_DIR, "ca_certs.txt"))
        request = ClientRequest("https://code.google.com/p/qtimigration/")
        try:
            client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)
        client.close()
        client = Client(
            ca_certs=os.path.join(TEST_DATA_DIR, "no_certs.txt"))
        request = ClientRequest("https://code.google.com/p/qtimigration/")
        try:
            client.process_request(request)
            if request.status != 0:
                self.fail("Expected status=0 after security failure")
            if not request.error:
                self.fail("Expected error after security failure")
            logging.info(str(request.error))
        except messages.HTTPException as err:
            logging.error(str(err))
        client.close()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
