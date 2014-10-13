#! /usr/bin/env python

import unittest
import logging
import io
import socket
import SocketServer
import random
import select

import pyslet.rfc5023 as app
from pyslet.http.server import *       # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ServerTests, 'test'),
        unittest.makeSuite(PipeTests, 'test'),
    ))


TEST_BODY = "The quick brown fox jumped over the lazy dog."


class MockTime:
    now = time.time()

    @classmethod
    def time(cls):
        return cls.now

    @classmethod
    def gmtime(cls, *args):
        return time.gmtime(*args)

    @classmethod
    def localtime(cls, *args):
        return time.localtime(*args)


class MockSocketBase(object):

    id_next = 1
    id_lock = threading.RLock()

    def __init__(self):
        with self.id_lock:
            self.id = MockSocketBase.id_next
            MockSocketBase.id_next += 1
        self.blocking = True
        self.send_pipe = Pipe(timeout=10, name="MockSocket.send[%i]" % self.id)
        self.recv_pipe = Pipe(timeout=10, name="MockSocket.recv[%i]" % self.id)
        self.send_rbuffer = io.BufferedReader(self.send_pipe)
        self.recv_wbuffer = io.BufferedWriter(self.recv_pipe)
        self.io_error = None

    pass_select = select.select

    @classmethod
    def wrap_select(cls, rlist, wlist, xlist, timeout=5):
        mrlist = []
        mwlist = []
        mxlist = []
        srlist = []
        swlist = []
        sxlist = []
        for r in rlist:
            if isinstance(r, cls):
                mrlist.append(r)
            else:
                srlist.append(r)
        for w in wlist:
            if isinstance(w, cls):
                mwlist.append(w)
            else:
                swlist.append(w)
        for x in xlist:
            if isinstance(x, cls):
                mxlist.append(x)
            else:
                sxlist.append(x)
        if srlist or swlist or sxlist:
            return cls.pass_select(srlist, swlist, sxlist, timeout)
        else:
            return cls.select(mrlist, mwlist, mxlist, timeout)

    @classmethod
    def select(cls, rlist, wlist, xlist, timeout=5):
        the_time = time.time()
        if timeout is not None:
            tstop = the_time + timeout
        else:
            tstop = 0
        while timeout is None or the_time <= tstop:
            # we must always go around at least once
            rs = []
            ws = []
            for r in rlist:
                if r.recv_pipe.canread():
                    rs.append(r)
            for w in wlist:
                if w.send_pipe.canwrite():
                    ws.append(w)
            if rs or ws:
                return rs, ws, []
            else:
                time.sleep(1)
                the_time = time.time()
        return [], [], []

    def setblocking(self, blocking):
        self.blocking = blocking
        # turn off blocking for recv and send
        self.recv_pipe.set_readblocking(blocking)
        self.send_pipe.set_writeblocking(blocking)

    def recv(self, nbytes):
        if self.io_error:
            raise self.io_error
        result = self.recv_pipe.read(nbytes)
        if self.io_error:
            raise self.io_error
        return result

    def send(self, data):
        if self.io_error:
            raise self.io_error
        result = self.send_pipe.write(data)
        if self.io_error:
            raise self.io_error
        return result

    def shutdown(self, how):
        if self.io_error:
            raise self.io_error
        if how in (socket.SHUT_RD, socket.SHUT_RDWR):
            # don't want any more data
            self.recv_pipe.write_eof()
            # don't wait for recv buffer, we stopped reading
            # self.recv_wbuffer.flush()
        if how in (socket.SHUT_WR, socket.SHUT_RDWR):
            self.send_pipe.write_eof()
            # but wait for the client to finish reading
            self.send_pipe.set_writeblocking(True)
            self.send_rbuffer.flush()
        if self.io_error:
            raise self.io_error

    def mock_shutdown(self, how):
        if how in (socket.SHUT_WR, socket.SHUT_RDWR):
            self.recv_pipe.write_eof()
            # wait for the other end to finish reading
            self.recv_pipe.set_writeblocking(True)
            self.recv_wbuffer.flush()
        if how in (socket.SHUT_RD, socket.SHUT_RDWR):
            # don't want any more data
            self.send_pipe.write_eof()
            # but don't wait for send buffer, we stopped reading
            # self.send_rbuffer.flush()
            self.send_pipe.close()

    def close(self):
        self.send_pipe.close()
        self.recv_pipe.close()


class MockSocket(MockSocketBase):

    def __init__(self):
        super(MockSocket, self).__init__()
        self.client_address = ("127.0.0.1", random.randint(1111, 9999))

    def send_request(self, request):
        request.start_sending()
        self.recv_pipe.write(request.send_start())
        self.recv_pipe.write(request.send_header())
        while True:
            if request.get_expect_continue():
                # don't send the body if we're expecting continue
                break
            data = request.send_body()
            if data:
                self.recv_pipe.write(data)
            else:
                break
        # now to receive the data
        response = self.receive_response(request)
        return response

    def receive_response(self, request):
        response = messages.Response(request)
        response.start_receiving()
        while True:
            mode = response.recv_mode()
            if mode == messages.Message.RECV_LINE:
                response.recv(self.send_pipe.readmatch())
            elif mode == messages.Message.RECV_HEADERS:
                lines = []
                last_line = ''
                while last_line != '\r\n':
                    last_line = self.send_pipe.readmatch()
                    lines.append(last_line)
                response.recv(lines)
            elif mode is None:
                break
            elif mode > 0:
                response.recv(self.send_pipe.read(mode))
            elif mode == messages.Message.RECV_ALL:
                response.recv(self.send_pipe.read())
            else:
                raise ValueError("unexpected recv_mode!")
        return response


class ServerTests(unittest.TestCase):

    def setUp(self):        # noqa
        select.select = MockSocket.wrap_select
        self.port = random.randint(1111, 9999)

    def tearDown(self):     # noqa
        select.select = MockSocket.pass_select

    def run_request(self, s, sock):
        # constructor automatically calls the handle method
        s.RequestHandlerClass(sock, sock.client_address, s)
        # simulate a real socket, shutdown when we're done
        logging.debug("run_request: mocking server socket shutdown")
        sock.shutdown(socket.SHUT_RDWR)

    def test_simple(self):
        # we must pass the port (to the left?)
        s = Server(port=self.port)
        self.assertTrue(isinstance(s, SocketServer.TCPServer))
        # check some attributes
        self.assertTrue(s.address_family == socket.AF_INET)
        self.assertTrue(s.server_address == ('127.0.0.1', self.port),
                        "Server address: %s" % repr(s.server_address))
        self.assertTrue(s.allow_reuse_address, "True for easy restart")
        # s.request_queue_size - we don't care at this point
        self.assertTrue(s.socket_type == socket.SOCK_STREAM)
        self.assertTrue(s.timeout is None)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        # write of str will not block on an empty pipe
        sock.recv_wbuffer.write("GET / HTTP/1.0\r\n\r\n")
        sock.recv_wbuffer.flush()
        sock.recv_pipe.write_eof()
        # with no application bound we expect default wsgi handling
        # which returns 404
        # read a fairly large chunk of response data
        response = sock.send_rbuffer.readline()
        logging.debug("test_simple: response\r\n%s", response)
        self.assertTrue(response.startswith("HTTP/1.1 404 "))
        sock.close()
        # now join our handler as it must exit
        t.join()

    def test_transfer_encoding(self):
        """RFC2616:

            A server which receives an entity-body with a
            transfer-coding it does not understand SHOULD return 501
            (Unimplemented), and close the connection"""
        s = Server(port=self.port)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        # write of str will not block on an empty pipe
        sock.recv_wbuffer.write("POST / HTTP/1.1\r\n"
                                "Transfer-Encoding: unknown, chunked\r\n\r\n")
        # force the data into the pipe (won't flush the Pipe itself)
        sock.recv_wbuffer.flush()
        sock.send_pipe.read_wait(5)
        response = sock.send_rbuffer.read()
        self.assertTrue(response is not None, "response still blocked")
        logging.debug("test_transfer_encoding: response\r\n%s", response)
        self.assertTrue(response.startswith("HTTP/1.1 501 "))
        # let's try and send another request, should fail
        try:
            sock.recv_wbuffer.write("GET / HTTP/1.1\r\n\r\n")
            sock.recv_wbuffer.flush()
            sock.send_pipe.read_wait(5)
        except IOError as e:
            # this must not be a timeout!
            self.assertFalse(e.errno == errno.ETIMEDOUT)
        except ValueError:
            # raised by BufferedWriter when it has been closed
            pass
        # now join our handler as it must exit
        sock.close()
        t.join()

    def multidata_app(self, environ, start_response):
        # the point of this app is to generate data of unknown
        # length forcing chunked encoding where possible
        start_response("200 OK", [])
        for i in xrange(random.randint(2, 10)):
            yield "Hello"
        yield "xyz"

    def test_nochunked(self):
        """RFC2616:

        A server MUST NOT send transfer-codings to an HTTP/1.0 client"""
        s = Server(port=self.port, app=self.multidata_app)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        # write of str will not block on an empty pipe
        sock.recv_wbuffer.write("GET /a HTTP/1.0\r\n\r\n")
        # force the data into the pipe (won't flush the Pipe itself)
        sock.recv_wbuffer.flush()
        response = sock.send_pipe.readmatch("xyz")
        self.assertTrue(response is not None, "response still blocked")
        logging.debug("test_nochunked: response\r\n%s", response)
        self.assertTrue(response.startswith("HTTP/1.1 200 "))
        self.assertFalse("chunked" in response.lower(), "No chunked")
        # it should close the connection...
        try:
            sock.recv_wbuffer.write("GET /b HTTP/1.0\r\n\r\n")
            sock.recv_wbuffer.flush()
            sock.send_pipe.read_wait(5)
        except IOError as e:
            # this must not be a timeout!
            self.assertFalse(e.errno == errno.ETIMEDOUT)
        except ValueError:
            # raised by BufferedWriter when it has been closed
            pass
        # now join our handler as it must exit
        sock.close()
        logging.debug("test_nochunked: waiting for handler...")
        t.join()
        logging.debug("test_nochunked: end of test")

    def test_chunked(self):
        """Contrast test, we expect chunked for HTTP/1.1"""
        s = Server(port=self.port, app=self.multidata_app)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        # write of str will not block on an empty pipe
        sock.recv_wbuffer.write("GET /a HTTP/1.1\r\n\r\n")
        # force the data into the pipe (won't flush the Pipe itself)
        sock.recv_wbuffer.flush()
        response = sock.send_pipe.readmatch("0\r\n\r\n")
        self.assertTrue(response is not None, "response still blocked")
        logging.debug("test_chunked: response\r\n%s", response)
        self.assertTrue(response.startswith("HTTP/1.1 200 "))
        self.assertTrue("chunked" in response.lower(), "Expected chunked")
        # it should not close the connection...
        try:
            sock.recv_wbuffer.write("GET /b HTTP/1.1\r\n\r\n")
            sock.recv_wbuffer.flush()
            sock.send_pipe.read_wait(5)
            response = sock.send_pipe.readmatch("0\r\n\r\n")
        except ValueError:
            # raised by BufferedWriter when it has been closed
            self.fail("Expected keep-alive")
        # hang up the mock-socket by writing EOF
        sock.mock_shutdown(socket.SHUT_RDWR)
        # now join our handler as it must exit
        sock.close()
        t.join()

    def test_trailers(self):
        """RFC 2616:

            A server using chunked transfer-coding in a response MUST
            NOT use the trailer for any header fields unless..."""
        # wsgi does not lend itself to adding trailers, we could add
        # Content-MD5 as a trailer and calculate the hash on the way
        # through but what's the point, chances of receiving a TE header
        # with "trailers" in is Nil.  Something to do for completeness
        # later perhaps
        pass

    def test_emptylines(self):
        """RFC 2616:

            In the interest of robustness, servers SHOULD ignore any
            empty line(s) received where a Request-Line is expected."""
        s = Server(port=self.port)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        # start with an empty line, should be ignored
        sock.recv_wbuffer.write("\r\n")
        sock.recv_wbuffer.flush()
        # now send a request
        sock.recv_wbuffer.write("POST /form.cgi HTTP/1.1\r\n")
        sock.recv_wbuffer.write("Content-length: 3\r\n\r\n")
        # buggy HTTP/1.0 form with trailing CRLF after POST data
        sock.recv_wbuffer.write("a=b\r\n")
        sock.recv_wbuffer.flush()
        response = sock.send_pipe.readmatch('\r\n\r\n')
        self.assertTrue(response is not None, "response still blocked")
        logging.debug("test_emptylines: response1\r\n%s", response)
        self.assertTrue(response.startswith("HTTP/1.1 404 "))
        # should be good for the next request
        sock.recv_wbuffer.write("GET /page.htm HTTP/1.1\r\n\r\n")
        sock.recv_wbuffer.flush()
        response = sock.send_pipe.readmatch('\r\n\r\n')
        self.assertTrue(response is not None, "response still blocked")
        logging.debug("test_emptylines: response2\r\n%s", response)
        self.assertTrue(response.startswith("HTTP/1.1 404 "))
        sock.mock_shutdown(socket.SHUT_RDWR)
        # now join our handler as it must exit
        t.join()

    def host_app(self, environ, start_response):
        server_name = environ.get('HTTP_HOST', None)
        server_name = server_name.split(':')[0]
        if server_name == "localhost":
            start_response("200 OK", [])
        elif server_name is None:
            start_response("299 Default Content", [])
        else:
            start_response("298 UNexpected host", [])
        return []

    def test_absolute_uri(self):
        """RFC2616:

            all HTTP/1.1 servers MUST accept the absoluteURI form in
            requests

            If Request-URI is an absoluteURI, the host is part of the
            Request-URI. Any Host header field value in the request MUST
            be ignored

            If the host as determined ... is not a valid host on the
            server, the response MUST be a 400 (Bad Request) error
            message"""
        # the default server is 127.0.0.1
        s = Server(port=self.port, app=self.host_app)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        request = messages.Request()
        request.set_method("GET")
        request.set_request_uri("http://localhost:%i/" % self.port)
        response = sock.send_request(request)
        self.assertTrue(response.status == 200)
        request = messages.Request()
        request.set_method("GET")
        request.set_request_uri("http://localhost:%i" % self.port)
        response = sock.send_request(request)
        self.assertTrue(response.status == 200)
        request = messages.Request()
        request.set_method("GET")
        request.set_request_uri("/")
        request.set_host("localhost:%i" % self.port)
        response = sock.send_request(request)
        self.assertTrue(response.status == 200)
        request = messages.Request()
        request.set_method("GET")
        request.set_request_uri("http://localhost:%i/" % self.port)
        request.set_host("www.badhost.com")
        response = sock.send_request(request)
        self.assertTrue(response.status == 200)
        request = messages.Request()
        request.set_method("GET")
        request.set_request_uri("http://badhost:%i/" % self.port)
        response = sock.send_request(request)
        self.assertTrue(response.status == 400)
        request = messages.Request()
        request.set_method("GET")
        request.set_request_uri("http://badhost.com:%i/" % self.port)
        request.set_host("localhost:%i" % self.port)
        response = sock.send_request(request)
        self.assertTrue(response.status == 400)
        sock.mock_shutdown(socket.SHUT_RDWR)
        sock.close()
        t.join()

    def continue_app(self, environ, start_response):
        path = environ.get('PATH_INFO', None)
        if path == "/wait":
            input = app.InputWrapper(environ)
            # read and discard all the data
            input.read()
            start_response("200 Success", [])
        elif path == "/nowait200":
            # don't wait, don't read the input
            start_response("200 Success", [])
        else:
            # don't wait, don't read the input
            start_response("404 Not Found", [])
        return []

    def test_continue(self):
        """RFC2616:

            Upon receiving a request which includes an Expect
            request-header field with the "100-continue" expectation, an
            origin server MUST either respond with 100 (Continue) status
            and continue to read from the input stream, or respond with
            a final status code.

            The origin server MUST NOT wait for the request body before
            sending the 100 (Continue) response.

            It MUST NOT perform the requested method if it returns a
            final status code.

            An origin server that sends a 100 (Continue) response MUST
            ultimately send a final status code"""
        s = Server(port=self.port, app=self.continue_app)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        request = messages.Request(entity_body=TEST_BODY)
        request.set_method("POST")
        request.set_request_uri("http://localhost:%i/wait" % self.port)
        request.set_expect_continue()
        response = sock.send_request(request)
        self.assertTrue(response.status == 100)
        sock.recv_pipe.write(request.send_body())
        response = sock.receive_response(request)
        self.assertTrue(response.status == 200)
        self.assertTrue(response.keep_alive)
        # next test, check that an app that doesn't read data still
        # generates a 100 continue and still reads the data
        request = messages.Request(entity_body=TEST_BODY)
        request.set_method("POST")
        request.set_request_uri("http://localhost:%i/nowait200" % self.port)
        request.set_expect_continue()
        response = sock.send_request(request)
        self.assertTrue(response.status == 100)
        self.assertTrue(response.keep_alive)
        response = sock.receive_response(request)
        self.assertTrue(response.status == 200)
        self.assertTrue(response.keep_alive)
        # and now, finally, we should still be able to write the rest of
        # the data
        sock.recv_pipe.write(request.send_body())
        # and the connection should stay up for the next request...
        request = messages.Request(entity_body=TEST_BODY)
        request.set_method("POST")
        request.set_request_uri("http://localhost:%i/nowait404" % self.port)
        request.set_expect_continue()
        response = sock.send_request(request)
        self.assertTrue(response.status == 404)
        self.assertFalse(response.keep_alive)
        sock.mock_shutdown(socket.SHUT_RDWR)
        sock.close()
        t.join()

    def test_continue10(self):
        """RFC2616:

            An origin server ... MUST NOT send a 100 (Continue) response
            if such a request comes from an HTTP/1.0 (or earlier)
            client.

        If a 1.0 client sends an Expect: 100-Continue we assume that the
        first rule trumps and you will get a 100 response after all."""
        s = Server(port=self.port, app=self.continue_app)
        sock = MockSocket()
        t = threading.Thread(target=self.run_request, args=(s, sock))
        t.start()
        request = messages.Request(entity_body=TEST_BODY,
                                   protocol=params.HTTP_1p0)
        request.set_method("POST")
        request.set_request_uri("http://localhost:%i/wait" % self.port)
        request.set_expect_continue()
        response = sock.send_request(request)
        self.assertTrue(response.status == 100)
        sock.recv_pipe.write(request.send_body())
        response = sock.receive_response(request)
        self.assertTrue(response.status == 200)
        self.assertTrue(response.keep_alive)


class Legacy(unittest.TestCase):

    def setUp(self):        # noqa
        self.port = random.randint(1111, 9999)
        self.s = Server(port=self.port, protocol=params.HTTP_1p0)

    def run_request(self, sock):
        # automatically calls the handle method
        self.s.RequestHandlerClass(sock, sock.client_address, self.s)
        # simulate a real socket, close the mock socket
        logging.debug("run_request: mocking server socket shutdown")
        sock.shutdown(socket.SHUT_RDWR)

    def test_legacy(self):
        """RFC2616:

            If a request contains a message-body and a Content-Length is
            not given, the server SHOULD respond with 400 (bad request)
            if it cannot determine the length of the message, or with
            411 (length required) if it wishes to insist on receiving a
            valid Content-Length"""
        # TODO
        pass


class PipeTests(unittest.TestCase):

    def test_simple(self):
        p = Pipe()
        # default constructor
        self.assertTrue(isinstance(p, io.RawIOBase))
        self.assertFalse(p.closed)
        try:
            p.fileno()
            self.fail("fileno should raise IOError")
        except IOError:
            pass
        self.assertFalse(p.isatty())
        self.assertTrue(p.readable())
        self.assertFalse(p.seekable())
        self.assertTrue(p.writable())
        # now for our custom attributes
        self.assertTrue(p.readblocking())
        self.assertTrue(p.writeblocking())
        self.assertTrue(p.canwrite() == io.DEFAULT_BUFFER_SIZE)
        self.assertFalse(p.canread())
        # now try a quick read and write test
        data = "The quick brown fox jumped over the lazy dog"
        wlen = p.write(data)
        self.assertTrue(wlen == len(data))
        self.assertTrue(p.canwrite() == io.DEFAULT_BUFFER_SIZE - len(data))
        self.assertTrue(p.canread())
        self.assertTrue(p.read(3) == data[:3])
        self.assertTrue(p.canwrite() == io.DEFAULT_BUFFER_SIZE - len(data) + 3)
        self.assertTrue(p.canread())
        # now deal with EOF conditions
        p.write_eof()
        try:
            p.write("extra")
            self.fail("write past EOF")
        except IOError:
            pass
        try:
            p.canwrite()
            self.fail("canwrite called past EOF")
        except IOError:
            pass
        self.assertTrue(p.canread(), "But can still read")
        self.assertFalse(p.closed)
        self.assertTrue(p.readall() == data[3:])
        self.assertTrue(p.canread(), "Can still read")
        self.assertTrue(p.read(3) == '')
        self.assertTrue(len(p.read()) == 0)
        self.assertTrue(len(p.readall()) == 0)
        p.close()
        self.assertTrue(p.closed)
        try:
            p.canread()
            self.fail("canread called on closed pipe")
        except IOError:
            pass

    def test_blocking(self):
        p = Pipe(timeout=1, bsize=10)
        self.assertTrue(p.readblocking())
        self.assertTrue(p.writeblocking())
        try:
            # should block for 1 second and then timeout
            rresult = p.read(1)
            self.fail("blocked read returned %s" % repr(rresult))
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)
        p.write("123")
        # should not block!
        rresult = p.read(5)
        self.assertTrue(rresult == "123")
        # should not block, just!
        p.write(bytearray("1234567890"))
        try:
            # should block for 1 second
            wresult = p.write("extra")
            self.fail("blocked write returned %s" % repr(wresult))
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)
        try:
            # should block for 1 second
            logging.debug("flush waiting for 1s timeout...")
            p.flush()
            self.fail("blocked flush returned")
        except IOError as e:
            logging.debug("flush caught 1s timeout; %s", str(e))

    def wrunner(self, p):
        # write some data to the pipe p
        time.sleep(1)
        p.write("1234567890")

    def test_rblocking(self):
        p = Pipe(timeout=15)
        t = threading.Thread(target=self.wrunner, args=(p,))
        t.start()
        try:
            # should block until the other thread writes
            rresult = p.read(1)
            self.assertTrue(rresult == "1")
        except IOError as e:
            self.fail("Timeout on mutlithreaded pipe; %s" % str(e))

    def rrunner(self, p):
        # read some data from the pipe p
        time.sleep(1)
        p.read(1)

    def rallrunner(self, p):
        # read all the data from p until there is no more
        time.sleep(1)
        logging.debug("rallrunner: calling readall")
        p.readall()

    def test_rdetect(self):
        p = Pipe(timeout=15, bsize=10)
        rflag = threading.Event()
        # set a read event
        p.set_rflag(rflag)
        self.assertFalse(rflag.is_set())
        t = threading.Thread(target=self.rrunner, args=(p,))
        t.start()
        # the runner will issue a read call, should trigger the event
        rflag.wait(5.0)
        self.assertTrue(rflag.is_set())
        # write 10 bytes, thread should terminate
        p.write("1234567890")
        t.join()
        # one byte read, write another byte
        p.write("A")
        # buffer should now be full at this point...
        self.assertFalse(p.canwrite())
        self.assertFalse(rflag.is_set())
        # the next call to read should set the flag again
        p.read(1)
        self.assertTrue(rflag.is_set())

    def test_wblocking(self):
        p = Pipe(timeout=15, bsize=10)
        t = threading.Thread(target=self.rrunner, args=(p,))
        p.write("1234567890")
        data = "extra"
        t.start()
        try:
            # should block until the other thread reads
            wresult = p.write(bytearray(data))
            # and should then write at most 1 byte
            self.assertTrue(wresult == 1, repr(wresult))
        except IOError as e:
            self.fail("Timeout on mutlithreaded pipe; %s" % str(e))
        t = threading.Thread(target=self.rallrunner, args=(p,))
        t.start()
        try:
            # should block until all data has been read
            logging.debug("flush waiting...")
            p.flush()
            logging.debug("flush complete")
            self.assertTrue(p.canwrite() == 10, "empty after flush")
        except IOError as e:
            self.fail("flush timeout on mutlithreaded pipe; %s" % str(e))
        # put the other thread out of its misery
        p.write_eof()
        logging.debug("eof written, joining rallrunner")
        t.join()

    def test_rnblocking(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        self.assertFalse(p.readblocking())
        self.assertTrue(p.writeblocking())
        try:
            # should not block
            rresult = p.read(1)
            self.assertTrue(rresult is None)
        except IOError as e:
            self.fail("Timeout on non-blocking read; %s" % str(e))
        # write should still block
        p.write("1234567890")
        try:
            # should block for 1 second
            wresult = p.write("extra")
            self.fail("blocked write returned %s" % repr(wresult))
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)

    def test_wnblocking(self):
        p = Pipe(timeout=1, bsize=10, wblocking=False)
        self.assertTrue(p.readblocking())
        self.assertFalse(p.writeblocking())
        p.write("1234567890")
        data = "extra"
        try:
            # should not block
            wresult = p.write(data)
            self.assertTrue(wresult is None, repr(wresult))
        except IOError as e:
            self.fail("Timeout on non-blocking write; %s" % str(e))
        # read all the data to empty the buffer
        self.assertTrue(len(p.read(10)) == 10, "in our case, True!")
        try:
            # should block for 1 second and then timeout
            rresult = p.read(1)
            self.fail("blocked read returned %s" % repr(rresult))
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)
        p.write("1234567890")
        try:
            # should not block!
            p.flush()
            self.fail("non-blocking flush returned with data")
        except io.BlockingIOError:
            pass
        except IOError as e:
            self.fail("non-blocking flush timed out; %s" % str(e))

    def wwait_runner(self, p):
        time.sleep(1)
        p.read(1)

    def test_wwait(self):
        p = Pipe(timeout=1, bsize=10, wblocking=False)
        p.write("1234567890")
        data = "extra"
        wresult = p.write(data)
        self.assertTrue(wresult is None, "write blocked")
        try:
            p.write_wait(timeout=1)
            self.fail("wait should time out")
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)
        t = threading.Thread(target=self.wwait_runner, args=(p,))
        t.start()
        time.sleep(0)
        try:
            p.write_wait(timeout=5)
            pass
        except IOError:
            self.fail("write_wait error on multi-threaded read; %s" % str(e))

    def rwait_runner(self, p):
        time.sleep(1)
        p.write("1234567890")

    def test_rwait(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        rresult = p.read(1)
        self.assertTrue(rresult is None, "read blocked")
        try:
            p.read_wait(timeout=1)
            self.fail("wait should time out")
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)
        t = threading.Thread(target=self.rwait_runner, args=(p,))
        t.start()
        time.sleep(0)
        try:
            p.read_wait(timeout=5)
            pass
        except IOError as e:
            self.fail("read_wait error on multi-threaded write; %s" % str(e))

    def test_eof(self):
        p = Pipe(timeout=1, bsize=10)
        p.write("123")
        self.assertTrue(p.canread())
        p.read(3)
        self.assertFalse(p.canread())
        p.write_eof()
        self.assertTrue(p.canread())
        self.assertTrue(p.read(3) == '')

    def test_readall(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        p.write("123")
        # readall should block and timeout
        try:
            data = p.readall()
            self.fail("blocked readall returned: %s" % data)
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)

    def test_nbreadmatch(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        p.write("12")
        p.write("3\r\n")
        self.assertTrue(p.readmatch() == "123\r\n")
        # now check behaviour when no line is present
        p.write("1")
        p.write("2")
        p.write("3")
        self.assertTrue(p.readmatch() is None, "non-blocking readmatch")
        p.write("\r")
        self.assertTrue(p.readmatch() is None, "non-blocking partial match")
        p.write("\nabc")
        self.assertTrue(p.readmatch() == "123\r\n")
        # now check for buffer size exceeded
        p.write("\r3\n4\r56\n")
        try:
            p.readmatch()
            self.fail("non-blocking full buffer")
        except IOError as e:
            self.assertTrue(e.errno == errno.ENOBUFS)
        # now add an EOF and it should change the result
        p.write_eof()
        self.assertTrue(p.readmatch() == '')

    def test_breadmatch(self):
        p = Pipe(timeout=1, bsize=10, rblocking=True)
        p.write("12")
        p.write("3\r\n")
        self.assertTrue(p.readmatch() == "123\r\n")
        # now check behaviour when no line is present
        p.write("1")
        p.write("2")
        p.write("3")
        try:
            p.readmatch()
            self.fail("blocking readmatch")
        except IOError as e:
            self.assertTrue(e.errno == errno.ETIMEDOUT)
        p.write("\r")
        p.write("\nabc")
        self.assertTrue(p.readmatch() == "123\r\n")
        # now check for buffer size exceeded
        p.write("\r3\n4\r56\n")
        try:
            p.readmatch()
            self.fail("blocking full buffer")
        except IOError as e:
            self.assertTrue(e.errno == errno.ENOBUFS)
        # now add an EOF and it should change the result
        p.write_eof()
        self.assertTrue(p.readmatch() == '')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
