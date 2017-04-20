#! /usr/bin/env python

import errno
import io
import logging
import os.path
import select
import shutil
import socket
import threading
import time
import random
import unittest

from tempfile import mkdtemp

import pyslet.http.client as http
import pyslet.http.messages as messages
import pyslet.http.params as params
import pyslet.http.server as server
import pyslet.rfc2396 as uri

from pyslet.py2 import range3
from pyslet.streams import Pipe, io_timedout

from test_http_server import MockSocketBase, MockTime


TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_rfc2616')

TEST_STRING = b"The quick brown fox jumped over the lazy dog"

TEST_BODY = b"123456\r\n\r\n"


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ClientTests, 'test'),
        unittest.makeSuite(LegacyServerTests, 'test'),
        unittest.makeSuite(ClientRequestTests, 'test'),
        # unittest.makeSuite(SecureTests, 'test')
    ))


class MockSocket(MockSocketBase):

    """Mocks the socket for the client"""

    def __init__(self, connection, allow_continue=True, close_on_417=False):
        super(MockSocket, self).__init__()
        self.allow_continue = allow_continue
        self.close_on_417 = close_on_417
        # start a thread to mock the server side of the connection
        t = threading.Thread(target=connection.manager.mock_server,
                             args=(connection.host, connection.port, self))
        t.start()

    def recv_request(self):
        while True:
            responded = False
            request = messages.Request()
            request.start_receiving()
            check_continue = False
            try:
                while True:
                    if check_continue and request.get_expect_continue():
                        # push an expect response
                        if self.allow_continue:
                            logging.debug("Sending 100 Continue")
                            self.send_continue()
                        else:
                            logging.debug("Sending 417 Expectation Failed")
                            self.send_expectation_failed()
                            if self.close_on_417:
                                # we're not sending any more data, hangup
                                self.mock_shutdown(socket.SHUT_RDWR)
                                return None
                            else:
                                # wait for the next request
                                responded = True
                        check_continue = False
                    mode = request.recv_mode()
                    if mode == messages.Message.RECV_LINE:
                        line = self.send_pipe.readmatch()
                        if line == b'':
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
                        last_line = b''
                        while last_line != b'\r\n':
                            last_line = self.send_pipe.readmatch()
                            lines.append(last_line)
                        request.recv(lines)
                        check_continue = True
                    elif mode is None:
                        break
                    elif mode > 0:
                        data = self.send_pipe.read(mode)
                        if data == b'':
                            # EOF, unexpected
                            raise messages.HTTPException(
                                "Unexpected EOF in mock socket")
                        else:
                            request.recv(data)
                    elif mode == messages.Message.RECV_ALL:
                        data = self.send_pipe.read()
                        if data == b'':
                            # EOF, expected
                            break
                        else:
                            request.recv(data)
                    else:
                        raise ValueError("unexpected recv_mode!")
            except IOError as e:
                if io_timedout(e):
                    logging.debug(
                        "mock socket timed out while reading request")
                    responded = False
                    request = None
                else:
                    raise
            if responded:
                continue
            else:
                return request

    def send_continue(self):
        self.recv_pipe.write(b"HTTP/1.1 100 Go on then!\r\n\r\n")

    def send_expectation_failed(self):
        self.recv_pipe.write(
            b"HTTP/1.1 417 Expectation Failed\r\n"
            b"Content-Length: 0\r\n")
        if self.close_on_417:
            self.recv_pipe.write(b"Connection: close\r\n")
        self.recv_pipe.write(b"\r\n")

    def send_response(self, response):
        try:
            response.start_sending()
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
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise


class MockSocketNoContinue(MockSocket):

    def __init__(self, connection):
        super(MockSocketNoContinue, self).__init__(connection,
                                                   allow_continue=False)


class MockSocketNoContinueClose(MockSocket):

    def __init__(self, connection):
        super(MockSocketNoContinueClose, self).__init__(
            connection, allow_continue=False, close_on_417=True)


class MockConnectionWrapper(http.Connection):

    SocketClass = MockSocket

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
                self.socket = self.SocketClass(self)
                self.socket_file = self.socket
                self.socket.setblocking(False)
                self.socketSelect = self.SocketClass.wrap_select


class MockConnectionWrapperNoContinue(MockConnectionWrapper):

    SocketClass = MockSocketNoContinue


class MockConnectionWrapperNoContinueClose(MockConnectionWrapper):

    SocketClass = MockSocketNoContinueClose


class MockClientWrapper(http.Client):

    ConnectionClass = MockConnectionWrapper

    def __init__(self, mock_server, **kwargs):
        http.Client.__init__(self, **kwargs)
        self.socketSelect = self.ConnectionClass.SocketClass.wrap_select
        self.mock_server = mock_server


class ClientRequestTests(unittest.TestCase):

    def setUp(self):        # noqa
        global time
        self.save_time = http.time
        http.time = MockTime

    def tearDown(self):     # noqa
        global time
        http.time = self.save_time
        MockTime.now = time.time()

    def test_retries(self):
        request = http.ClientRequest("http://www.domain1.com/", max_retries=10,
                                     min_retry_time=4)
        self.assertTrue(request.max_retries == 10)
        self.assertTrue(request.nretries == 0)
        self.assertTrue(request.retry_time == 0)
        MockTime.now = 10.0
        ranges = [
            (10.0, 10.0),   # 10+0 +-0
            (13.0, 15.0),   # 10+4 +-1
            (13.0, 15.0),   # 10+4 +-1
            (16.0, 20.0),   # 10+8 +-2
            (19.0, 25.0),   # 10+12 +-3
            (25.0, 35.0),   # 10+20 +-5
            (34.0, 50.0),   # 10+32 +-8
            (49.0, 75.0),   # 10+52 +-13
            (73.0, 115.0),  # 10+84 +-21
            (112.0, 180.0)]  # 10+136 +-34
        for i in range3(10):
            # simulate a failed send
            request.connect(None, 0)
            request.disconnect(1)
            self.assertTrue(request.can_retry(), "retry %ith time" % i)
            self.assertTrue(request.retry_time >= ranges[i][0],
                            "%f too small in pair %i" %
                            (request.retry_time, i))
            self.assertTrue(request.retry_time <= ranges[i][1],
                            "%f too large in pair %i" %
                            (request.retry_time, i))


class ClientTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.client = MockClientWrapper(self.run_manager, max_connections=3)
        self.client.httpUserAgent = None
        self.unreliable = True
        self.error_count = 2

    def tearDown(self):     # noqa
        self.client.close()

    def test_simple(self):
        """simple tests

        RFC 2616:

            If the abs_path is not present in the URL, it MUST be given
            as "/" when used as a Request-URI for a resource"""
        request = http.ClientRequest("http://www.example.com/")
        request.start_sending()
        request_line = request.send_start()
        self.assertTrue(request_line.startswith(b"GET / HTTP/1."),
                        request_line)

    def run_domain1(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                response = messages.Response(req, entity_body=TEST_STRING)
                response.set_status(200, "You got it!")
            elif req.method == "HEAD":
                response = messages.Response(req)
                response.set_content_length(len(TEST_STRING))
                response.set_status(200, "You got it!")
            elif req.method == "PUT":
                # check the request body
                response = messages.Response(req, entity_body=b'')
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
            if req.method == "GET":
                response = messages.Response(req, entity_body=b"Not here")
                response.set_status(301, "Moved")
                response.set_location("http://www.domain1.com/")
            elif req.method == "HEAD":
                response = messages.Response(req, entity_body=None)
                response.set_status(301, "Moved")
                response.set_location("http://www.domain1.com/")
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain2")
            sock.send_response(response)

    def run_domain5(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            if self.unreliable:
                self.unreliable = False
                # shutdown the socket
                logging.debug("Server hang-up after reading request")
                sock.mock_shutdown(socket.SHUT_RDWR)
                break
            if req.method == "GET":
                response = messages.Response(req, entity_body=TEST_STRING)
                response.set_status(200, "Thanks for your patience")
            elif req.method == "HEAD":
                response = messages.Response(req)
                response.set_content_length(len(TEST_STRING))
                response.set_status(200, "Thanks for your patience")
            elif req.method == "POST":
                response = messages.Response(req, entity_body=TEST_STRING)
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

    def run_domain7(self, sock):
        while True:
            if self.error_count > 1:
                # generate an error on the socket for the client
                sock.io_error = socket.error(errno.EINTR,
                                             os.strerror(errno.EINTR))
                self.error_count -= 1
                break
            elif self.error_count:
                req = sock.recv_request()
                if req is None:
                    break
                sock.io_error = socket.error(errno.EINTR,
                                             os.strerror(errno.EINTR))
                self.error_count -= 1
                sock.close()
                break
            else:
                req = sock.recv_request()
                if req is None:
                    break
                response = messages.Response(req, entity_body=TEST_STRING)
                response.set_status(200, "Thanks for your patience")
            sock.send_response(response)

    def run_domain8(self, sock):
        while True:
            # simulates a server with a short fuse, shuts down
            # the socket after a single request
            req = sock.recv_request()
            if req is None:
                break
            if req.method == "GET":
                response = messages.Response(req, entity_body=TEST_STRING)
                response.set_status(200, "Success")
            elif req.method == "HEAD":
                response = messages.Response(req)
                response.set_content_length(len(TEST_STRING))
                response.set_status(200, "Success")
            elif req.method == "POST":
                response = messages.Response(req)
                response.set_status(200, "Success")
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain8")
            sock.send_response(response)
            logging.debug("Server hang-up after 0s idle time")
            sock.mock_shutdown(socket.SHUT_RDWR)
            break

    def run_domain9(self, sock):
        while True:
            # simulates a server that supports upgrade to happy
            req = sock.recv_request()
            if req is None:
                break
            connection = req.get_connection()
            if "upgrade" in connection:
                response = messages.Response(req)
                response.set_status(101)
                response.set_upgrade([params.ProductToken("happy")])
                sock.send_response(response)
                logging.debug("Switching to happy protocol")
                input = sock.send_pipe.readmatch()
                sock.recv_pipe.write(input)
                sock.recv_pipe.write_eof()
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain9")
                sock.send_response(response)
            sock.mock_shutdown(socket.SHUT_RDWR)
            break

    def run_manager(self, host, port, sock):
        # read some data from sock, and post a response
        logging.debug('run_manager: %s, %i' % (host, port))
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
        elif host == "www.domain7.com" and port == 80:
            self.run_domain7(sock)
        elif host == "www.domain8.com" and port == 80:
            self.run_domain8(sock)
        elif host == "www.domain9.com" and port == 80:
            self.run_domain9(sock)
        else:
            # connection error
            raise ValueError("run_manager: bad host in connect")

    def test_manager(self):
        request1 = http.ClientRequest("http://www.domain1.com/")
        self.assertTrue(request1.method == "GET")
        request2 = http.ClientRequest("http://www.domain2.com/", "HEAD")
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
        self.assertTrue(request2.res_body == b"",
                        "Data in response2: %s" % request2.res_body)

    def test_redirect(self):
        request = http.ClientRequest("http://www.domain2.com/")
        self.client.queue_request(request)
        self.client.thread_loop(timeout=5)
        response = request.response
        self.assertTrue(
            str(response.protocol) == "HTTP/1.1",
            "Protocol in response1: %s" % response.protocol)
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        self.assertTrue(response.reason == "You got it!",
                        "Reason in response: %s" % response.reason)
        self.assertTrue(
            request.res_body == TEST_STRING,
            "Data in response: %s" %
            repr(request.res_body))

    def test_continue(self):
        """RFC2616:

            If a client will wait for a 100 (Continue) response before
            sending the request body, it MUST send an Expect
            request-header field with the "100-continue" expectation."""
        request1 = http.ClientRequest(
            "http://www.domain1.com/file", method="PUT",
            entity_body=TEST_BODY)
        self.assertTrue(request1.method == "PUT")
        request2 = http.ClientRequest(
            "http://www.domain1.com/file2", method="PUT",
            entity_body=TEST_BODY)
        request2.set_expect_continue()
        self.client.queue_request(request1)
        self.assertTrue(request1.get_header('Expect') is None)
        self.client.queue_request(request2)
        self.assertTrue(request2.get_header('Expect') == b"100-continue")
        # thread_loop will process the queue until it blocks for more
        # than the timeout (default, forever)
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
        self.assertTrue(request1.res_body == b'',
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
        self.assertTrue(request2.res_body == b"",
                        "Data in response2: %s" % request2.res_body)
        # How do we test that response2 held back from sending the data before
        # the redirect?

    def test_expectation_failed(self):
        """RFC7231

        A client that receives a 417 (Expectation Failed) status code in
        response to a request containing a 100-continue expectation
        SHOULD repeat that request without a 100-continue expectation

        Try this using the same connection (aborted send)"""
        # fix up the mock client to force a 417 response
        self.client.ConnectionClass = MockConnectionWrapperNoContinue
        request1 = http.ClientRequest(
            "http://www.domain1.com/file", method="PUT",
            entity_body=TEST_BODY)
        request1.set_expect_continue()
        self.client.queue_request(request1)
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
        self.assertTrue(request1.res_body == b'',
                        "Data in response1: %s" % request1.res_body)

    def test_expectation_failed_reconnect(self):
        """RFC7231

        A client that receives a 417 (Expectation Failed) status code in
        response to a request containing a 100-continue expectation
        SHOULD repeat that request without a 100-continue expectation

        Try this using a new connection after server indicates closing"""
        # fix up the mock client to force a 417 response
        self.client.ConnectionClass = MockConnectionWrapperNoContinueClose
        request1 = http.ClientRequest(
            "http://www.domain1.com/file", method="PUT",
            entity_body=TEST_BODY)
        request1.set_expect_continue()
        self.client.queue_request(request1)
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
        self.assertTrue(request1.res_body == b'',
                        "Data in response1: %s" % request1.res_body)

    def test_streamed_put(self):
        request = http.ClientRequest(
            "http://www.domain1.com/file2",
            "PUT",
            entity_body=io.BytesIO(b"123456\r\n\r\n"))
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
            request.res_body == b"", "Data in response: %s" % request.res_body)
        request = http.ClientRequest(
            "http://www.domain1.com/file",
            "PUT",
            entity_body=io.BytesIO(b"123456\r\n\r\n"))
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
            request.res_body == b"", "Data in response: %s" % request.res_body)

    def test_streamed_get(self):
        buff = io.BytesIO()
        request = http.ClientRequest(
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
            request.res_body == b"",
            "Data in streamed response: %s" %
            repr(request.res_body))

    def domain3_thread_oneshot(self):
        time.sleep(1)
        logging.debug("domain3_thread_oneshot starting...")
        request = http.ClientRequest("http://www.domain3.com/index.txt")
        try:
            self.client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)

    def domain4_thread_oneshot(self):
        time.sleep(1)
        logging.debug("domain4_thread_oneshot starting...")
        request = http.ClientRequest("http://www.domain4.com/index.txt")
        try:
            self.client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)

    def test_multiget(self):
        threads = []
        for i in range3(10):
            threads.append(
                threading.Thread(target=self.domain3_thread_oneshot))
        for i in range3(10):
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
        request = http.ClientRequest("http://www.domain5.com/unreliable")
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
        request = http.ClientRequest("http://www.domain6.com/unreliable",
                                     min_retry_time=0.1)
        # this request will always fail with a broken server
        self.client.process_request(request)
        response = request.response
        self.assertTrue(response.status is None, "No response")

    def test_async_close2(self):
        """RFC2616:

            Non-idempotent methods or sequences MUST NOT be
            automatically retried."""
        request = http.ClientRequest("http://www.domain5.com/unreliable",
                                     method="POST", entity_body=b"Hello")
        # this request will timeout the first time before any data
        # has been sent to the client, it should retry and fail!
        self.client.process_request(request)
        response = request.response
        self.assertTrue(response.status is None, "No response")

    def test_async_error(self):
        request = http.ClientRequest(
            "http://www.domain7.com/", min_retry_time=0.1)
        self.client.process_request(request)
        response = request.response
        self.assertTrue(response.status == 200)
        self.client.idle_cleanup(0)

    def test_post_after_shutdown(self):
        request = http.ClientRequest("http://www.domain8.com/",
                                     method="POST", entity_body=b"Hello")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(response.status == 200)
        # the remote end has shut down the socket, but without telling
        # us so we'll get an error here.  We should be able to detect
        # that the error happens before we send the request and so
        # re-establish the connection.  A fail is likely though because
        # the method is POST which we won't resend if the data was
        # partially sent.
        request = http.ClientRequest("http://www.domain8.com/",
                                     method="POST", entity_body=b"Hello")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(response.status == 200)

    def test_kill(self):
        threads = []
        for i in range3(10):
            threads.append(
                threading.Thread(target=self.domain3_thread_oneshot))
        for i in range3(10):
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

    def upgrade_request(self, request):
        self.client.process_request(request)

    def test_upgrade(self):
        request = http.ClientRequest("http://www.domain9.com/socket")
        request.set_upgrade([params.ProductToken("happy")])
        self.client.process_request(request)
        self.assertTrue(request.status == 101)
        try:
            self.assertTrue(isinstance(request.send_pipe, Pipe))
            self.assertTrue(isinstance(request.recv_pipe, Pipe))
            request.send_pipe.write(b'hello\r\n')
            request.send_pipe.write_eof()
            output = request.recv_pipe.read()
            self.assertTrue(output == b'hello\r\n',
                            "Failed echo test on upgrade: %s" % str(output))
        finally:
            request.recv_pipe.close()


class LegacyServerTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.port = random.randint(1111, 9999)
        self.server = server.Server(port=self.port, app=self.legacy_app,
                                    protocol=params.HTTP_1p0)
        # We need to give time to prevent handle_request doing nothing
        self.server.timeout = 10
        self.client = http.Client()

    def tearDown(self):     # noqa
        self.client.close()
        self.server.server_close()

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
                return [b"Got it!"]
            elif method == "PUT":
                environ['wsgi.input'].read(content_length)
                start_response("204 Updated", [])
                return []
            else:
                start_response("500 Unexpected", [])
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
        t = threading.Thread(target=self.run_legacy, args=(2,))
        t.start()
        request = http.ClientRequest(
            "http://localhost:%i/nochunked" % self.port)
        self.assertTrue(request.protocol == params.HTTP_1p1)
        # start off optimistic about keep_alive
        self.assertTrue(request.keep_alive)
        self.client.process_request(request)
        self.assertTrue(request.response.status == 200)
        self.assertTrue(request.response.protocol == params.HTTP_1p0)
        # legacy server closes the connection
        self.assertFalse(request.response.keep_alive)
        # now try and make a call which would normally default to chunked
        data = b"How long is a piece of string?"
        bodytext = Pipe(rblocking=False, timeout=10)
        bodytext.write(data)
        request = http.ClientRequest(
            "http://localhost:%i/nochunked" % self.port,
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

    def test_nochunked2(self):
        """RFC2616:

            when a client sends this header field to an origin server
            (possibly via a proxy) from which it has never seen a 100
            (Continue) status, the client SHOULD NOT wait for an
            indefinite period before sending the request body."""
        t = threading.Thread(target=self.run_legacy, args=(1,))
        t.start()
        data = b"How long is a piece of string?"
        request = http.ClientRequest(
            "http://localhost:%i/nochunked" % self.port,
            "PUT", entity_body=data)
        # we don't know that the server is 1.0, let's clip the timeout
        # on the wait for 100-Continue, 6s on the client is about right,
        # will translate to 1s on the wait for continue timeout
        self.client.timeout = 6.0
        request.set_expect_continue()
        self.client.process_request(request)
        self.assertTrue(request.response.status == 204)


class SecureTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()
        self.d = mkdtemp('.d', 'pyslet-test_https-')
        os.chdir(self.d)

    def tearDown(self):     # noqa
        os.chdir(self.cwd)
        shutil.rmtree(self.d, True)

    def test_google_insecure(self):
        client = http.Client()
        request = http.ClientRequest("https://code.google.com/p/qtimigration/")
        try:
            client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)
        client.close()

    def test_google_secure(self):
        client = http.Client(
            ca_certs=os.path.join(TEST_DATA_DIR, "ca_certs.txt"))
        request = http.ClientRequest("https://code.google.com/p/qtimigration/")
        try:
            client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)
        client.close()
        client = http.Client(
            ca_certs=os.path.join(TEST_DATA_DIR, "no_certs.txt"))
        request = http.ClientRequest("https://code.google.com/p/qtimigration/")
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

    def test_chain(self):
        try:
            from OpenSSL import SSL     # noqa
        except ImportError:
            logging.warning(
                "Skipping chain test (install pyOpenSSL to activate test)")
            return
        client = http.Client()
        try:
            client.get_server_certificate_chain(
                uri.URI.from_octets("http://www.pyslet.org/"))
            self.fail("Can't get certificate chain from http URL")
        except ValueError:
            pass
        chain = client.get_server_certificate_chain(
            uri.URI.from_octets("https://code.google.com/p/qtimigration/"))
        fpath = os.path.join(self.d, 'ca_certs.txt')
        with open(fpath, 'wb') as f:
            f.write(chain)
        client = http.Client(ca_certs=fpath)
        request = http.ClientRequest("https://code.google.com/p/qtimigration/")
        try:
            client.process_request(request)
        except messages.HTTPException as err:
            logging.error(err)
        client.close()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
