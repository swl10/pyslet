#! /usr/bin/env python

import io
import logging
import random
import unittest

import pyslet.http.grammar as grammar
import pyslet.http.params as params

from pyslet.py2 import is_string
from pyslet.py26 import RawIOBase

from pyslet.http.messages import *       # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(MessageTests, 'test'),
        unittest.makeSuite(RecvWrapperTests, 'test'),
        unittest.makeSuite(SendWrapperTests, 'test'),
        unittest.makeSuite(ChunkedTests, 'test'),
        unittest.makeSuite(WSGITests, 'test'),
        unittest.makeSuite(HeaderTests, 'test'),
    ))


class ChunkedTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()

    def tearDown(self):     # noqa
        os.chdir(self.cwd)

    def test_chunked_reader(self):
        src = io.BytesIO(b"10\r\n0123456789ABCDEF\r\n"
                         b"5; ext=true\r\n01234\r\n"
                         b"0\r\nhead: false trailer\r\n\r\ntrailer")
        r = ChunkedReader(src)
        self.assertTrue(r.read() == b"0123456789ABCDEF01234", "unchunked data")
        self.assertTrue(src.read() == b"trailer", "trailer left on the stream")


class WSGITests(unittest.TestCase):

    FOX = b'The quick brown fox jumped over the lazy dog'

    def test_simple(self):
        input = io.BytesIO()
        # write some data to the input
        input.write(self.FOX)
        input.seek(0)
        environ = {'wsgi.input': input, 'CONTENT_LENGTH': str(len(self.FOX))}
        r = WSGIInputWrapper(environ)
        self.assertTrue(r.read() == self.FOX, "input data")


class MessageTests(unittest.TestCase):

    def test_simple(self):
        request = Request()
        # test ability to hold a simple request
        request.start_receiving()
        self.assertTrue(request.recv_mode() == request.RECV_LINE)
        request.recv(b"GET /pub/WWW/TheProject.html HTTP/1.1\r\n")
        self.assertTrue(request.recv_mode() == request.RECV_HEADERS)
        request.recv([b"Host: www.w3.org\r\n", b"\r\n"])
        self.assertTrue(request.recv_mode() is None)

    def test_nochunked(self):
        """RFC2616:

            For compatibility with HTTP/1.0 applications, HTTP/1.1
            requests containing a message-body MUST include a valid
            Content-Length header field unless the server is known to be
            HTTP/1.1 compliant

        This is also tested at the client level but here we check that
        we get an error if we are generating a message for an HTTP/1.0
        recipient."""
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("PUT")
        request.set_request_uri("/resource")
        request.set_host("www.example.com")
        request.start_sending(params.HTTP_1p0)
        # a content-length must have been set
        self.assertTrue(request.get_content_length() is not None)
        self.assertTrue(request.get_transfer_encoding() is None)
        # now check that we default to chunked instead of buffering
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("PUT")
        request.set_request_uri("/resource")
        request.set_host("www.example.com")
        request.start_sending(params.HTTP_1p1)
        # a content-length must not have been set
        self.assertTrue(request.get_content_length() is None)
        self.assertTrue(request.get_transfer_encoding() is not None)

    def test_chunked(self):
        """From RFC2616:

            Whenever a transfer-coding is applied to a message-body, the
            set of transfer-codings MUST include "chunked", unless the
            message is terminated by closing the connection"""
        request = Request()
        request.start_receiving()
        request.recv(b"POST /script.cgi HTTP/1.1\r\n")
        request.recv([b"Transfer-Encoding: gzip, chunked\r\n", b"\r\n"])
        # message must now be in line mode for chunk header
        self.assertTrue(request.recv_mode() == request.RECV_LINE)
        response = Response(request)
        response.start_receiving()
        response.recv(b"HTTP/1.1 200 OK\r\n")
        response.recv([b"Transfer-Encoding: gzip\r\n", b"\r\n"])
        # message must now be in 'read until close' mode
        self.assertTrue(response.recv_mode() == request.RECV_ALL)

    def test_chunks(self):
        """From RFC2616:

            All HTTP/1.1 applications MUST be able to receive and decode
            the "chunked" transfer-coding, and MUST ignore
            chunk-extension extensions they do not understand.

            All HTTP/1.1 applications that receive entities MUST accept
            the "chunked" transfer-coding"""
        request = Request()
        request.start_receiving()
        request.recv(b"POST /script.cgi HTTP/1.1\r\n")
        request.recv([b"Transfer-Encoding: chunked\r\n", b"\r\n"])
        chunk1 = b"The quick brown "
        chunk2 = b"fox jumped over the lazy dog."
        request.recv(b'%X ; a=xyz; b="\\"odd\\\rparam\\\n"\r\n' % len(chunk1))
        request.recv(chunk1)
        request.recv(b'\r\n')
        request.recv(b'%X\r\n' % len(chunk2))
        request.recv(chunk2)
        request.recv(b'\r\n')
        request.recv(b'0; the=end \r\n')
        request.recv([b'\r\n'])
        self.assertTrue(request.entity_body.getvalue() == chunk1 + chunk2)

    def test_gzip(self):
        srcbody = io.BytesIO(b"The quick brown fox jumped over the lazy dog")
        zchunked = io.BytesIO()
        dstbody = io.BytesIO()
        src_request = Request(entity_body=srcbody)
        dst_request = Request(entity_body=dstbody)
        src_request.set_method("post")
        src_request.set_request_uri("/script.cgi")
        src_request.set_host("www.example.com")
        src_request.set_transfer_encoding("gzip, chunked")
        src_request.start_sending()
        dst_request.start_receiving()
        # send_* and recv should match, take a short cut
        dst_request.recv(src_request.send_start())
        headers = src_request.send_header()
        headers = [h + grammar.CRLF for h in headers.split(b'\r\n')[:-1]]
        dst_request.recv(headers)
        while True:
            data = src_request.send_body()
            if data:
                pos = data.index(grammar.CRLF)
                cline = data[:pos + 2]
                cdata = data[pos + 2:-2]
                zchunked.write(cdata)
                dst_request.recv(cline)
                if cdata:
                    dst_request.recv(cdata)
                    dst_request.recv(grammar.CRLF)
                else:
                    dst_request.recv([grammar.CRLF])
                    break
            else:
                break
        self.assertTrue(srcbody.getvalue() == dstbody.getvalue())
        self.assertTrue(srcbody.getvalue() != zchunked.getvalue())

    def test_multipart(self):
        """RFC 2616:

            All multipart types share a common syntax, as defined in
            section 5.1.1 of RFC 2046 and MUST include a boundary
            parameter as part of the media type value"""
        response_start = b"HTTP/1.1 206 Partial Content\r\n"
        response_headers = [
            b"Date: Wed, 15 Nov 1995 06:25:24 GMT\r\n",
            b"Last-Modified: Wed, 15 Nov 1995 04:58:08 GMT\r\n",
            b"Content-type: multipart/byteranges; "
            b"boundary=THIS_STRING_SEPARATES\r\n",
            b"\r\n"]
        response_body = [
            b"--THIS_STRING_SEPARATES\r\n",
            b"Content-type: application/pdf\r\n",
            b"Content-range: bytes 500-999/8000\r\n",
            b"\r\n",
            b"...the first range...\r\n",
            b"--THIS_STRING_SEPARATES\r\n",
            b"Content-type: application/pdf\r\n",
            b"Content-range: bytes 7000-7999/8000\r\n",
            b"\r\n",
            b"...the second range\r\n",
            b"--THIS_STRING_",
            b"SEPARATES-- junk \r\n"]
        dstbody = io.BytesIO()
        request = Request()
        dst_response = Response(request, entity_body=dstbody)
        dst_response.start_receiving()
        dst_response.recv(response_start)
        dst_response.recv(response_headers)
        # no Content-Length means read forever and close connection
        self.assertFalse(dst_response.keep_alive, "no keep_alive allowed")
        self.assertTrue(dst_response.recv_mode() == Response.RECV_ALL)
        for line in response_body:
            dst_response.recv(line)
        # we can't prevent all over-reading but as soon as the boundary
        # is detected the message should stop receiving
        self.assertTrue(dst_response.recv_mode() is None)
        # transport padding and the closing CRLF are considered spurious
        self.assertTrue(dstbody.getvalue() == b''.join(response_body)[:-8])
        response_headers = [
            b"Date: Wed, 15 Nov 1995 06:25:24 GMT\r\n",
            b"Last-Modified: Wed, 15 Nov 1995 04:58:08 GMT\r\n",
            b"Content-type: multipart/mixed\r\n",
            b"\r\n"]
        dstbody = io.BytesIO()
        request = Request()
        dst_response = Response(request, entity_body=dstbody)
        dst_response.start_receiving()
        dst_response.recv(response_start)
        try:
            dst_response.recv(response_headers)
            self.fail("Expected ProtocolError on missing boundary parameter")
        except ProtocolError:
            pass

    def test_combining_fields(self):
        """RFC2616:

            It MUST be possible to combine the multiple header fields
            into one "field-name: field-value" pair, without changing
            the semantics of the message, by appending each subsequent
            field-value to the first, each separated by a comma"""
        request = Request()
        request.set_header("X-Test", "hello")
        request.set_header("X-Test", "good-bye")
        self.assertTrue(request.get_header("X-Test") == b"good-bye")
        request.set_header("X-Test", "hello again", True)
        self.assertTrue(request.get_header("X-Test") ==
                        b"good-bye, hello again")
        response = Response(request)
        response.start_receiving()
        response.recv(b"HTTP/1.1 200 OK\r\n")
        response.recv([b"X-Test: hello\r\n", b"x-test: good-bye\r\n", b"\r\n"])
        self.assertTrue(response.get_header("X-test").strip() ==
                        b"hello, good-bye")

    def test_message_body_req(self):
        """RFC2616:

            A message-body MUST NOT be included in a request if the
            specification of the request method (section 5.1.1) does not
            allow sending an entity-body in requests...

            A server SHOULD read and forward a message-body on any
            request"""
        request = Request(entity_body=b"Bad data")
        request.set_method("GET")
        request.set_request_uri("/")
        try:
            request.start_sending()
            self.fail("GET request with body")
        except HTTPException:
            pass
        body = io.BytesIO()
        bad_data = b"Bad data"
        request = Request(entity_body=body)
        request.start_receiving()
        request.recv(b"GET / HTTP/1.1\r\n")
        request.recv([b"Content-Length: %i\r\n" % len(bad_data),
                      b"Content-type: text/plain\r\n",
                      b"\r\n"])
        self.assertTrue(request.recv_mode() > 0)
        request.recv(bad_data)
        self.assertTrue(request.recv_mode() is None)
        self.assertTrue(body.getvalue() == bad_data)

    def test_message_body_head(self):
        """RFC2616:

            All responses to the HEAD request method MUST NOT include a
            message-body, even though the presence of entity- header
            fields might lead one to believe they do"""
        request = Request()
        request.set_method("HEAD")
        request.set_request_uri("/")
        body = b"Bad data"
        response = Response(request, entity_body=body)
        response.set_status(200)
        response.set_content_length(len(body))
        response.set_content_type("text/plain")
        try:
            response.start_sending()
            self.fail("HEAD response with body")
        except HTTPException:
            pass
        response = Response(request)
        response.start_receiving()
        response.recv(b"HTTP/1.1 200 OK")
        response.recv(
            [b"Content-type: text/plain\r\n",
             b"Content-Length: %i\r\n" % len(body),
             b"\r\n"])
        self.assertTrue(response.recv_mode() is None)

    def test_message_body_res(self):
        """RFC2616:

            All 1xx (informational), 204 (no content), and 304 (not
            modified) responses MUST NOT include a message-body"""
        request = Request()
        request.set_method("PUT")
        request.set_request_uri("/resource")
        body = b"Bad data"
        for i in (100, 101, 204, 304):
            response = Response(request, entity_body=body)
            response.set_status(i)
            response.set_content_length(len(body))
            response.set_content_type("text/plain")
            try:
                response.start_sending()
                self.fail("%i response with body")
            except HTTPException:
                pass
            response = Response(request)
            response.start_receiving()
            response.recv(b"HTTP/1.1 %i For Testing" % i)
            response.recv(
                [b"Content-type: text/plain\r\n",
                 b"Content-Length: %i\r\n" % len(body),
                 b"\r\n"])
            self.assertTrue(response.recv_mode() is None)

    def test_message_length1(self):
        """RFC2616:

            The Content-Length header field MUST NOT be sent if these
            two lengths are different (i.e., if a Transfer-Encoding
            header field is present)

            If a message is received with both a Transfer-Encoding
            header field and a Content-Length header field, the latter
            MUST be ignored.

            Messages MUST NOT include both a Content-Length header field
            and a non-identity transfer-coding. If the message does
            include a non-identity transfer-coding, the Content-Length
            MUST be ignored.

        The second rule here appears a little more specific which
        suggests that we should be generous when receiving a
        Transfer-Encoding of identity."""
        body = b"Bad data"
        request = Request(entity_body=body)
        request.set_method("PUT")
        request.set_request_uri("/resource")
        request.set_content_length(len(body))
        request.set_content_type("text/plain")
        request.set_transfer_encoding("chunked")
        try:
            request.start_sending()
            self.fail("request with conflicting headers")
        except HTTPException:
            pass
        request = Request()
        request.start_receiving()
        request.recv(b"PUT /resource HTTP/1.1\r\n")
        request.recv([
            b"Content-Length: %i\r\n" % (len(body) - 3),  # misleading length
            b"Content-Type: text/plain\r\n",
            b"Transfer-Encoding: chunked\r\n",
            b"\r\n"])
        # so we should be back in line mode ready for
        # the chunk header
        self.assertTrue(request.recv_mode() == request.RECV_LINE)
        request.recv(b"%X\r\n" % len(body))
        request.recv(body)
        request.recv(grammar.CRLF)
        request.recv(b"0\r\n")
        request.recv([grammar.CRLF])
        self.assertTrue(request.entity_body.getvalue() == body)
        request = Request()
        request.start_receiving()
        request.recv(b"PUT /resource HTTP/1.1\r\n")
        request.recv([
            b"Content-Length: %i\r\n" % len(body),
            b"Content-Type: text/plain\r\n",
            b"Transfer-Encoding: identity\r\n",
            b"\r\n"])
        # we should abide by Content-Length, ignoring identity encoding
        self.assertTrue(request.recv_mode() == len(body))
        request.recv(body)
        self.assertTrue(request.recv_mode() is None)
        self.assertTrue(request.entity_body.getvalue() == body)

    def test_message_length2(self):
        """RFC2616:

            A range header might be forwarded by a 1.0 proxy that does
            not understand multipart/byteranges; in this case the server
            MUST delimit the message using methods defined in items 1,3
            or 5 of this section."""
        request = Request()
        request.set_protocol(params.HTTP_1p0)
        request.set_method("GET")
        request.set_request_uri("/resource")
        request.set_header("Range", "bytes=500-999,7000-7999")
        body = b"""--THIS_STRING_SEPARATES
Content-type: application/pdf
Content-range: bytes 500-999/8000

...the first range...
--THIS_STRING_SEPARATES
Content-type: application/pdf
Content-range: bytes 7000-7999/8000

...the second range
--THIS_STRING_SEPARATES--"""
        response = Response(request, entity_body=io.BytesIO(body))
        response.set_status(206)
        response.set_date("Wed, 15 Nov 1995 06:25:24 GMT")
        response.set_content_type(
            "multipart/byteranges; boundary=THIS_STRING_SEPARATES")
        response.set_last_modified("Wed, 15 Nov 1995 04:58:08 GMT")
        # with no content-length to guide us we should close the
        # connection (method 5)
        response.start_sending()
        self.assertTrue("close" in response.get_connection())
        # now try and force chunked, it should get stripped
        response.set_connection(None)
        response.set_transfer_encoding("chunked")
        response.start_sending()
        self.assertTrue(response.get_transfer_encoding() is None)
        self.assertTrue("close" in response.get_connection())

    def test_aborted_send(self):
        body = b"Bad data"
        request = Request(entity_body=body)
        request.set_protocol(params.HTTP_1p1)
        request.set_method("PUT")
        request.set_request_uri("/resource")
        request.set_content_type("text/plain")
        request.set_transfer_encoding("chunked")
        request.start_sending()
        request.send_start()
        request.send_header()
        # now abort the send, should send a zero length chunk
        self.assertTrue(request.abort_sending() == 0)
        self.assertTrue(request.send_body() == b"0\r\n\r\n")
        request = Request(entity_body=body)
        request.set_protocol(params.HTTP_1p1)
        request.set_method("PUT")
        request.set_request_uri("/resource")
        request.set_content_type("text/plain")
        request.set_content_length(len(body))
        request.start_sending()
        request.send_start()
        request.send_header()
        # now abort the send, should indicate remaining length
        self.assertTrue(request.abort_sending() == len(body))
        self.assertTrue(request.send_body() == body)


class MockBlockingByteReader(RawIOBase):

    def __init__(self, src, block_after=set()):
        RawIOBase.__init__(self)
        self.src = src
        self.block_after = block_after
        self.buffer = bytearray(io.DEFAULT_BUFFER_SIZE)
        self.bpos = 0
        self.blen = 0
        self.src_eof = False

    def close(self):
        super(MockBlockingByteReader, self).close()
        self.src.close()

    def readable(self):
        return True

    def readinto(self, b):
        if self.closed:
            raise IOError(errno.EBADF, os.strerror(errno.EBADF),
                          "stream is closed")
        nbytes = len(b)
        if self.blen > self.bpos:
            # buffered data to read
            if random.random() < 0.5:
                # blocked half of the time
                return None
            # copy data from our buffer to b
            i = 0
            while i < nbytes and self.bpos < self.blen:
                if i and random.random() < 0.9:
                    # arbitrary break in data
                    # don't return 0 as that means EOF
                    break
                b[i] = self.buffer[self.bpos]
                self.bpos += 1
                if b[i] in self.block_after:
                    # we'll break here
                    return i + 1
                i += 1
            return i
        if self.src_eof:
            return 0
        # our buffer is empty, fill it
        self.bpos = self.blen = 0
        nread = self.src.readinto(self.buffer)
        if nread is None:
            # the src is actually blocked too!
            return None
        elif nread == 0:
            # end of file
            self.src_eof = True
            return 0
        else:
            # we have read some data, return None to force a
            # second call
            self.blen = nread
            return None

    def writable(self):
        return False

    def write(self, b):
        raise IOError(errno.EPERM, os.strerror(errno.EPERM),
                      "stream not writable")


class RecvWrapperTests(unittest.TestCase):

    GET_EXAMPLE = (
        b"GET / HTTP/1.1",
        b"Host: www.pyslet.org",
        b"User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:45.0) "
        b"Gecko/20100101 Firefox/45.0",
        b"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,"
        b"*/*;q=0.8",
        b"Accept-Language: en-US,en;q=0.5",
        b"Accept-Encoding: gzip, deflate",
        b"DNT: 1",
        b"Connection: keep-alive",
        b"",
        b"")

    RESPONSE_EXAMPLE = (
        b"HTTP/1.1 301 Moved Permanently",
        b"Date: Thu, 21 Apr 2016 08:48:53 GMT",
        b"Server: Apache/2.2.31 (Amazon)",
        b"Location: https://www.pyslet.org/",
        b"Content-Length: 311",
        b"Connection: close",
        b"Content-Type: text/html; charset=iso-8859-1",
        b"",
        b"<!DOCTYPE HTML PUBLIC \"-//IETF//DTD HTML 2.0//EN\">\n"
        b"<html><head>\n"
        b"<title>301 Moved Permanently</title>\n"
        b"</head><body>\n"
        b"<h1>Moved Permanently</h1>\n"
        b"<p>The document has moved <a "
        b"href=\"https://www.pyslet.org/\">here</a>.</p>\n"
        b"<hr>\n"
        b"<address>Apache/2.2.31 (Amazon) Server at www.pyslet.org Port "
        b"80</address>\n"
        b"</body></html>\n")

    def test_constructor(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        # pass in a srouce stream and a class to receive
        rstream = RecvWrapper(src, Request)
        self.assertTrue(isinstance(rstream.message, Request))
        try:
            rstream.fileno()
            self.fail("RecvWrapper.fileno")
        except IOError:
            pass
        # flush does nothing but is callable
        rstream.flush()
        self.assertFalse(rstream.isatty())
        self.assertTrue(rstream.readable())
        rstream.close()

    def test_close(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        self.assertFalse(rstream.closed)
        rstream.close()
        self.assertTrue(rstream.closed)
        try:
            rstream.read(1)
            self.fail("RecvWrapper.read after close")
        except IOError:
            pass

    def test_readline(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        # blocking empty stream
        self.assertTrue(rstream.readline() == b"")
        rstream.close()
        src = io.BytesIO(grammar.CRLF.join(self.RESPONSE_EXAMPLE))
        rstream = RecvWrapper(src, Response)
        # blocking non-empty stream
        self.assertTrue(
            rstream.readline() ==
            b'<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\n')
        # blocking non-empty stream with limit bytes
        self.assertTrue(rstream.readline(6) == b'<html>')
        rstream.close()

    def test_readlines(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        # blocking empty stream
        lines = rstream.readlines()
        # returns a list of lines
        self.assertTrue(isinstance(lines, list))
        # should be empty
        self.assertTrue(len(lines) == 0)
        rstream.close()
        src = io.BytesIO(grammar.CRLF.join(self.RESPONSE_EXAMPLE))
        rstream = RecvWrapper(src, Response)
        # read 10 bytes (ish)
        lines = rstream.readlines(10)
        self.assertTrue(len(lines) == 1)
        self.assertTrue(
            lines[0] ==
            b'<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\n')
        # read the rest, no trailing empty line!
        lines = rstream.readlines()
        self.assertTrue(len(lines) == 8)
        self.assertTrue(lines[7] == b"</body></html>\n")
        rstream.close()

    def test_read(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        # blocking empty stream
        self.assertTrue(rstream.read(1) == b"")
        rstream.close()
        src = io.BytesIO(grammar.CRLF.join(self.RESPONSE_EXAMPLE))
        rstream = RecvWrapper(src, Response)
        # blocking non-empty stream
        c = rstream.read(1)
        self.assertTrue(c == b"<")
        line = []
        while c != b"\n":
            line.append(c)
            c = rstream.read(1)
            # won't return None
            self.assertTrue(len(c) == 1)
        self.assertTrue(b"".join(line) ==
                        b'<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">')
        data = rstream.read()
        self.assertTrue(data.endswith(b"</html>\n"))
        self.assertTrue(rstream.read(1) == b"")
        rstream.close()

    def test_read_nonblocking(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        # simulate breaks in the data after LF
        src = MockBlockingByteReader(src, block_after=((10,)))
        rstream = RecvWrapper(src, Request)
        # non-blocking empty stream
        while True:
            c = rstream.read(1)
            if c == b"":
                break
            self.assertTrue(c is None,
                            "empty stream non-blocking: %s" % repr(c))
        rstream.close()
        src = io.BytesIO(grammar.CRLF.join(self.RESPONSE_EXAMPLE))
        src = MockBlockingByteReader(src, block_after=((10,)))
        rstream = RecvWrapper(src, Response)
        # non-blocking non-empty stream
        line = []
        blocks = 0
        while True:
            c = rstream.read(1)
            if c:
                if c == b"\n":
                    break
                else:
                    line.append(c)
                    continue
            self.assertTrue(c is None,
                            "empty stream non-blocking: %s" % repr(c))
            blocks += 1
        # our mock blocking stream always returns None at least once
        self.assertTrue(blocks > 1, "non-blocking stream failed to stall")
        self.assertTrue(b"".join(line) ==
                        b'<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">')
        # readall behaviour is undefined, don't test it
        rstream.close()

    def test_seek(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        self.assertFalse(rstream.seekable())
        try:
            rstream.seek(0)
            self.fail("RecvWrapper.seek")
        except IOError:
            pass
        try:
            rstream.tell()
            self.fail("RecvWrapper.tell")
        except IOError:
            pass
        try:
            rstream.truncate(0)
            self.fail("RecvWrapper.truncate")
        except IOError:
            pass
        rstream.close()

    def test_write(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        self.assertFalse(rstream.writable())
        try:
            rstream.write(b"Hello")
            self.fail("RecvWrapper.write")
        except IOError:
            pass
        rstream.close()

    def test_message_header(self):
        src = io.BytesIO(grammar.CRLF.join(self.GET_EXAMPLE))
        rstream = RecvWrapper(src, Request)
        # initially the message object exists but has no headers
        self.assertTrue(rstream.message.get_host() is None)
        message = rstream.read_message_header()
        # just returns the message
        self.assertTrue(rstream.message is message)
        # but now with headers!
        self.assertTrue(message.get_host() == b"www.pyslet.org")
        # check the last header
        self.assertTrue("keep-alive" in message.get_connection())
        # subsequent calls just return the message again
        message = rstream.read_message_header()
        self.assertTrue(rstream.message is message)
        # the content of the stream is unaltered
        self.assertTrue(rstream.read(1) == b"")
        rstream.close()
        # non-blocking test with response
        src = io.BytesIO(grammar.CRLF.join(self.RESPONSE_EXAMPLE))
        src = MockBlockingByteReader(src, block_after=((10,)))
        rstream = RecvWrapper(src, Response)
        blocks = 0
        while True:
            message = rstream.read_message_header()
            if message is None:
                blocks += 1
                continue
            self.assertTrue(message is rstream.message)
            break
        self.assertTrue(blocks > 1, "non-blocking stream failed to stall")
        mt = message.get_content_type()
        self.assertTrue(mt.type == "text")
        self.assertTrue(mt['charset'] == b"iso-8859-1")
        line = []
        while True:
            c = rstream.read(1)
            if c:
                if c == b"\n":
                    break
                else:
                    line.append(c)
                    continue
            self.assertTrue(c is None,
                            "empty stream non-blocking: %s" % repr(c))
        self.assertTrue(b"".join(line) ==
                        b'<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">')
        rstream.close()


class SendWrapperTests(unittest.TestCase):

    def test_constructor(self):
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("POST")
        request.set_request_uri("/script.cgi")
        request.set_content_type("text/plain")
        rstream = SendWrapper(request)
        self.assertTrue(rstream.message is request)
        try:
            rstream.fileno()
            self.fail("SendWrapper.fileno")
        except IOError:
            pass
        # flush does nothing but is callable
        rstream.flush()
        self.assertFalse(rstream.isatty())
        self.assertTrue(rstream.readable())
        rstream.close()

    def test_close(self):
        request = Request()
        request.set_method("GET")
        request.set_request_uri("/script.cgi")
        request.set_content_type("text/plain")
        rstream = SendWrapper(request)
        self.assertFalse(rstream.closed)
        rstream.close()
        self.assertTrue(rstream.closed)
        try:
            rstream.read(1)
            self.fail("SendWrapper.read after close")
        except IOError:
            pass

    def test_readline(self):
        request = Request()
        request.set_method("GET")
        request.set_request_uri("/index.html")
        rstream = SendWrapper(request)
        # blocking empty message body
        self.assertTrue(rstream.readline() == b"GET /index.html HTTP/1.1\r\n")
        self.assertTrue(rstream.readline() == b"\r\n")
        self.assertTrue(rstream.readline() == b"")
        rstream.close()
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("POST")
        request.set_request_uri("/script.cgi")
        rstream = SendWrapper(request, params.HTTP_1p0)
        # blocking non-empty message body
        self.assertTrue(rstream.readline() == b"POST /script.cgi HTTP/1.1\r\n")
        self.assertTrue(rstream.readline() == b"Connection: close\r\n")
        self.assertTrue(rstream.readline() == b"Content-Length: 9\r\n")
        self.assertTrue(rstream.readline() == b"\r\n")
        # blocking non-empty stream with limit bytes
        self.assertTrue(rstream.readline(6) == b"How lo")
        rstream.close()

    def test_readlines(self):
        request = Request()
        request.set_method("GET")
        request.set_request_uri("/index.html")
        rstream = SendWrapper(request)
        # blocking empty message body
        lines = rstream.readlines()
        # returns a list of lines
        self.assertTrue(isinstance(lines, list))
        # should be empty
        self.assertTrue(len(lines) == 2)
        rstream.close()
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("POST")
        request.set_request_uri("/script.cgi")
        rstream = SendWrapper(request, params.HTTP_1p0)
        # blocking non-empty message body
        # read 10 bytes (ish)
        lines = rstream.readlines(10)
        self.assertTrue(len(lines) == 1)
        self.assertTrue(
            lines[0] ==
            b'POST /script.cgi HTTP/1.1\r\n')
        # read the rest, no trailing empty line!
        lines = rstream.readlines()
        self.assertTrue(len(lines) == 4)
        self.assertTrue(lines[3] == b"How long?")
        rstream.close()

    def test_read(self):
        request = Request()
        request.set_method("GET")
        request.set_request_uri("/index.html")
        rstream = SendWrapper(request)
        # blocking empty message body
        self.assertTrue(rstream.readline() == b"GET /index.html HTTP/1.1\r\n")
        self.assertTrue(rstream.readline() == b"\r\n")
        self.assertTrue(rstream.read(1) == b"")
        rstream.close()
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("POST")
        request.set_request_uri("/script.cgi")
        rstream = SendWrapper(request, params.HTTP_1p0)
        # blocking non-empty message body
        c = rstream.read(1)
        self.assertTrue(c == b"P")
        line = []
        while c != b"\n":
            line.append(c)
            c = rstream.read(1)
            # won't return None
            self.assertTrue(len(c) == 1)
        self.assertTrue(b"".join(line) ==
                        b'POST /script.cgi HTTP/1.1\r')
        data = rstream.read()
        self.assertTrue(data.endswith(b"How long?"))
        self.assertTrue(rstream.read(1) == b"")
        rstream.close()

    def test_read_nonblocking(self):
        src = io.BytesIO(b"How long?\n" * 10)
        src = MockBlockingByteReader(src, block_after=((10,)))
        response = Response(entity_body=src)
        response.set_status(200)
        rstream = SendWrapper(response, params.HTTP_1p0)
        # non-blocking non-empty message body
        lines = []
        line = []
        blocks = 0
        while True:
            c = rstream.read(1)
            if c:
                if c == b"\n":
                    # end of line
                    lines.append(b"".join(line))
                    line = []
                else:
                    line.append(c)
            elif c is None:
                blocks += 1
            else:
                break
        # our mock blocking stream always returns None at least once
        self.assertTrue(blocks > 1, "non-blocking stream failed to stall")
        boundary = lines.index(b"\r")
        self.assertTrue(boundary > 0)
        for line in lines[boundary + 1:]:
            self.assertTrue(line == b"How long?")
        # readall behaviour is undefined, don't test it
        rstream.close()

    def test_seek(self):
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("POST")
        request.set_request_uri("/script.cgi")
        rstream = SendWrapper(request, params.HTTP_1p0)
        self.assertFalse(rstream.seekable())
        try:
            rstream.seek(0)
            self.fail("RecvWrapper.seek")
        except IOError:
            pass
        try:
            rstream.tell()
            self.fail("RecvWrapper.tell")
        except IOError:
            pass
        try:
            rstream.truncate(0)
            self.fail("RecvWrapper.truncate")
        except IOError:
            pass
        rstream.close()

    def test_write(self):
        request = Request(entity_body=io.BytesIO(b"How long?"))
        request.set_method("POST")
        request.set_request_uri("/script.cgi")
        rstream = SendWrapper(request, params.HTTP_1p0)
        self.assertFalse(rstream.writable())
        try:
            rstream.write(b"Hello")
            self.fail("RecvWrapper.write")
        except IOError:
            pass
        rstream.close()


class HeaderTests(unittest.TestCase):

    def test_media_range(self):
        mr = MediaRange()
        self.assertTrue(
            isinstance(mr, params.MediaType), "Special type of media-type")
        self.assertTrue(str(mr) == "*/*")
        mr = MediaRange.from_str("*/*")
        self.assertTrue(mr.type == "*", "Main type")
        self.assertTrue(mr.subtype == "*", "subtype")
        self.assertTrue(len(mr.parameters) == 0, "Parameters")
        p = HeaderParser("text/*;charset=utf-8; q=1.0; x=5")
        mr = MediaRange()
        mr = p.parse_media_range()
        self.assertTrue(len(mr.parameters) == 1,
                        "q-value terminates parameters: %s" %
                        repr(mr.parameters))
        # check comparisons
        self.assertTrue(
            MediaRange.from_str("image/*") < MediaRange.from_str("*/*"),
            "Specific over general */*")
        self.assertTrue(
            MediaRange.from_str("image/png") <
            MediaRange.from_str("image/*"),
            "Specific over general image/*")
        self.assertTrue(
            MediaRange.from_str("text/plain;charset=utf-8") <
            MediaRange.from_str("text/plain"),
            "Parameter over no-parameter")

    def test_accept_list(self):
        al = AcceptList()
        self.assertTrue(len(al) == 0)
        al = AcceptList.from_str("audio/*; q=0.2, audio/basic")
        self.assertTrue(len(al) == 2, "Length of AcceptList")
        self.assertTrue(isinstance(al[0], AcceptItem), "AcceptList item type")
        self.assertTrue(str(al[0].range) == "audio/basic", str(al[0].range))
        self.assertTrue(al[0].q == 1.0)
        self.assertTrue(len(al[0].params) == 0)
        self.assertTrue(str(al[0]) == "audio/basic",
                        "don't add 1 for defaults: %s" % str(al[0]))
        self.assertTrue(str(al[1].range) == "audio/*")
        self.assertTrue(al[1].q == 0.2)
        self.assertTrue(len(al[1].params) == 0)
        self.assertTrue(str(al[1]) == "audio/*; q=0.2", "add the q value")
        al = AcceptList.from_str(
            "text/plain; q=0.5, text/html,  text/x-dvi; q=0.8, text/x-c")
        self.assertTrue(len(al) == 4, "Length of AcceptList")
        self.assertTrue(
            str(al) ==
            "text/html, text/plain; q=0.5, text/x-c, text/x-dvi; q=0.8",
            str(al))
        al = AcceptList.from_str("text/*, text/html, text/html;level=1, */*")
        self.assertTrue(
            str(al) == "text/html; level=1, text/html, text/*, */*", str(al))
        type_list = [
            params.MediaType.from_str("text/html;level=1"),
            params.MediaType.from_str("text/html"),
            params.MediaType.from_str("text/html;level=2"),
            params.MediaType.from_str("text/xhtml")]
        best_type = al.select_type(type_list)
        #   Accept: text/html; level=1, text/html, text/*, */*
        #   text/html;level=1   : q=1.0
        #   text/html           : q=1.0
        #   text/html;level=2   : q-1.0     partial match on text/html
        #   text/xhtml          : q=1.0     partial match on text/*
        # first in list
        self.assertTrue(str(best_type) == "text/html; level=1", str(best_type))
        al = AcceptList.from_str(
            "text/*; q=1.0, text/html; q=0.5, text/html;level=1; q=0, */*")
        #   Accept: text/*; q=1.0, text/html; q=0.5, text/html;level=1;
        #       q=0, */*
        #   text/html;level=1   : q=0.0
        #   text/html           : q=0.5
        #   text/html;level=2   : q-0.5     partial match on text/html
        #   text/xhtml          : q=1.0     partial match on text/*
        best_type = al.select_type(type_list)
        self.assertTrue(
            str(best_type) == "text/xhtml",
            "Specific match with confusing q value: %s" %
            str(best_type))
        del type_list[3]
        best_type = al.select_type(type_list)
        self.assertTrue(
            str(best_type) == "text/html",
            "beats level 2 only on order in list")
        del type_list[1]
        best_type = al.select_type(type_list)
        self.assertTrue(str(best_type) == "text/html; level=2",
                        "Partial level match beats exact rule deprecation")
        al = AcceptList.from_str(
            "text/*;q=0.3, text/html;q=0.7, "
            "text/html;level=1,  text/html;level=2;q=0.4, */*;q=0.5 ")
        type_list = [
            params.MediaType.from_str("text/html;level=1"),
            params.MediaType.from_str("text/html"),
            params.MediaType.from_str("text/plain"),
            params.MediaType.from_str("image/jpeg"),
            params.MediaType.from_str("text/html;level=2"),
            params.MediaType.from_str("text/html;level=3")]
        #   Accept: text/*;q=0.3, text/html;q=0.7, text/html;level=1,
        #       text/html;level=2;q=0.4, */*;q=0.5
        #   text/html;level=1   : q=1.0
        #   text/html           : q=0.7
        #   text/plain          : q=0.3
        #   image/jpeg          : q=0.5
        #   text/html;level=2   : q=0.4
        #   text/html;level=3   : q=0.7
        best_type = al.select_type(type_list)
        self.assertTrue(
            str(best_type) == "text/html; level=1",
            "Only exact match with q=1")
        del type_list[0]
        best_type = al.select_type(type_list)
        self.assertTrue(
            str(best_type) == "text/html", "beats level=3 on order in list")
        del type_list[0]
        best_type = al.select_type(type_list)
        self.assertTrue(
            str(best_type) == "text/html; level=3", "matches text/html")
        del type_list[-1]
        best_type = al.select_type(type_list)
        self.assertTrue(str(best_type) == "image/jpeg",
                        "matches */*, returned %s" % str(str(best_type)))
        del type_list[1]
        best_type = al.select_type(type_list)
        self.assertTrue(
            str(best_type) == "text/html; level=2", "exact match with q=0.4")
        del type_list[1]
        best_type = al.select_type(type_list)
        self.assertTrue(str(best_type) == "text/plain", "matches text/*")
        al = AcceptList.from_str("text/*, text/html, text/html;level=1, "
                                 "image/*; q=0, image/png; q=0.05")
        #   Accept: text/*, text/html, text/html;level=1, */*; q=0,
        #       image/*; q=0.05
        #   video/mpeg  : q=0.0
        #   image/png   : q=0.05
        best_type = al.select_type([params.MediaType.from_str('video/mpeg')])
        self.assertTrue(best_type is None, "Unacceptable: %s" % str(best_type))
        best_type = al.select_type([params.MediaType.from_str('image/png')])
        self.assertTrue(
            str(best_type) == "image/png",
            "Best partial match: %s" %
            str(best_type))

    def test_accept_token_list(self):
        rq_token = AcceptToken()
        self.assertTrue(
            rq_token.token == "*" and rq_token.q == 1.0,
            "AcceptToken constructor")
        self.assertTrue(str(rq_token) == "*", "AcceptToken Format default")
        rq_token = AcceptToken("gzip", 0.5)
        self.assertTrue(
            str(rq_token) == "gzip;q=0.5",
            "AcceptToken custom constructor Format default: %s" %
            str(rq_token))
        rq_tokens = AcceptTokenList.from_str(
            " gzip;q=1.0, identity; q=0.5, *;q=0")
        self.assertTrue(rq_tokens[0].token == 'gzip' and rq_tokens[0].q == 1.0,
                        "Parse accept encodings: gzip;q=1.0")
        self.assertTrue(
            str(rq_tokens[0]) == "gzip",
            "Format accept encodings: found %s" % str(rq_tokens[0]))
        self.assertTrue(
            rq_tokens[1].token == 'identity' and rq_tokens[1].q == 0.5,
            "Accept encodings identity;q=0.5")
        self.assertTrue(
            str(rq_tokens[1]) ==
            "identity;q=0.5", "Format accept encodings: identity;q=0.5")
        self.assertTrue(rq_tokens[2].token == '*' and rq_tokens[2].q == 0,
                        "Accept encodings *;q=0")
        self.assertTrue(
            str(rq_tokens[2]) == "*;q=0",
            "Format accept encodings: found %s" % str(rq_tokens[2]))
        # Final tests check bad values for q
        rq_token = AcceptToken.from_str("x;q=1.3")
        self.assertTrue(rq_token.q == 1.0, "Large q value")

    def test_accept_charset_list(self):
        # checks the rule that iso-8859-1, if not present explicitly, matches *
        rq_tokens = AcceptCharsetList.from_str(
            " utf-8;q=1.0, symbol; q=0.5, *;q=0.5")
        self.assertTrue(
            rq_tokens.select_token(["iso-8859-1"]) is not None, "match *")
        # so if * is excluded then it will be excluded
        rq_tokens = AcceptCharsetList.from_str(
            " utf-8;q=1.0, symbol; q=0.5, *;q=0")
        self.assertTrue(
            rq_tokens.select_token(["iso-8859-1"]) is None, "match * q=0")
        # and if * is not present it gets q value 1
        rq_tokens = AcceptCharsetList.from_str(
            " utf-8;q=1.0, symbol; q=0.5")
        self.assertTrue(rq_tokens.select_token(
            ["symbol", "iso-8859-1"]) == "iso-8859-1",
            "default q=1 for latin-1")

    def test_accept_encoding_list(self):
        rq_tokens = AcceptEncodingList.from_str("compress, gzip")
        self.assertTrue(
            rq_tokens.select_token(["gzip"]) is not None, "match token")
        rq_tokens = AcceptEncodingList.from_str("compress, gzip;q=0")
        self.assertTrue(
            rq_tokens.select_token(["gzip"]) is None, "match token unless q=0")
        rq_tokens = AcceptEncodingList.from_str("compress, *, gzip;q=0")
        self.assertTrue(
            rq_tokens.select_token(
                ["gzip"]) is None,
            "match token unless q=0; unmatched *")
        rq_tokens = AcceptEncodingList.from_str("compress, *;q=0")
        self.assertTrue(rq_tokens.select_token(["gzip"]) is None,
                        "match * q=0")
        rq_tokens = AcceptEncodingList.from_str(
            "compress; q=0.5, gzip;q=0.75")
        self.assertTrue(
            rq_tokens.select_token(["compress", "gzip"]) == "gzip",
            "match highest q")
        rq_tokens = AcceptEncodingList.from_str(
            "compress; q=0.5, gzip;q=0.75, *;q=1")
        self.assertTrue(rq_tokens.select_token(
            ["compress", "gzip", "weird"]) == "weird", "match highest q *")
        rq_tokens = AcceptEncodingList.from_str(
            "compress; q=0.5, gzip;q=0.75")
        self.assertTrue(
            rq_tokens.select_token(
                ["identity"]) is not None,
            "identity acceptable")
        rq_tokens = AcceptEncodingList.from_str(
            "compress; q=0.5, gzip;q=0.75, identity;q=0")
        self.assertTrue(
            rq_tokens.select_token(
                ["identity"]) is None,
            "identity unacceptable")
        rq_tokens = AcceptEncodingList.from_str(
            "compress; q=0.5, gzip;q=0.75, *;q=0")
        self.assertTrue(
            rq_tokens.select_token(
                ["identity"]) is None,
            "identity unacceptable *")
        rq_tokens = AcceptEncodingList.from_str("")
        self.assertTrue(
            rq_tokens.select_token(
                ["identity"]) is not None,
            "identity acceptable (empty)")
        self.assertTrue(
            rq_tokens.select_token(
                ["gzip"]) is None,
            "gzip unacceptable (empty)")

    def test_accept_language_list(self):
        rq_tokens = AcceptLanguageList.from_str(
            " da, en-gb;q=0.8, en;q=0.7 ")
        self.assertTrue(
            rq_tokens.select_token(["en-US"]) == "en-US", "match prefix")
        self.assertTrue(is_string(rq_tokens.select_token(["en-US"])),
                        "select_token return type")
        match = rq_tokens.select_language(
            [params.LanguageTag.from_str("en-US")])
        self.assertTrue(match == "en-US", "match prefix (tag version)")
        self.assertTrue(
            isinstance(match, params.LanguageTag),
            "select_language return type")
        rq_tokens = AcceptLanguageList.from_str(
            " da, en-gb;q=0.8, en;q=0.7 ")
        self.assertTrue(rq_tokens.select_language(
            [params.LanguageTag.from_str("eng-US")]) is None,
            "match prefix only")
        match = rq_tokens.select_language(
            [params.LanguageTag.from_str("en-US"),
             params.LanguageTag.from_str("en-gb")])
        self.assertTrue(
            match == "en-gb", "match preference: found %s" % repr(match))
        rq_tokens = AcceptLanguageList.from_str(
            " da, en-gb;q=0.8, en;q=0.7, *;q=0.75 ")
        self.assertTrue(rq_tokens.select_language([
            params.LanguageTag.from_str("en-US"),
            params.LanguageTag.from_str("de"),
            params.LanguageTag.from_str("en-gb")
        ]) == "en-gb", "match preference")
        self.assertTrue(rq_tokens.select_language([
            params.LanguageTag.from_str("en-US"),
            params.LanguageTag.from_str("de"),
        ]) == "de", "match preference")
        self.assertTrue(rq_tokens.select_language([params.LanguageTag.from_str(
            "en-gb-drawl-berkshire-westreading")]) is not None,
            "match long prefix only")
        rq_tokens = AcceptLanguageList.from_str(
            " da, en-us;q=0.8, en-sg;q=0.7")
        self.assertTrue(rq_tokens.select_language([params.LanguageTag.from_str(
            "en-gb-drawl-berkshire-westreading")]) is None,
            "no match on long prefix only")
        rq_tokens = AcceptLanguageList.from_str(
            " da, en-us;q=0.8, en-sg;q=0.7, en-gb-drawl-berkshire")
        self.assertTrue(rq_tokens.select_language([params.LanguageTag.from_str(
            "en-gb-drawl-berkshire-westreading")]) is not None,
            "match on long prefix")

    def test_accept_ranges(self):
        ar = AcceptRanges()
        # none maps to an empty set of ranges
        self.assertTrue(len(ar) == 0, "Default to none")
        self.assertTrue(str(ar) == "none", "Default to none, str")
        ar = AcceptRanges("none")
        self.assertTrue(len(ar) == 0, "Explicit none")
        self.assertTrue(str(ar) == "none", "Explicit none, str")
        ar = AcceptRanges("bytes", "bits")
        self.assertTrue(len(ar) == 2, "bytes and bits")
        self.assertTrue(ar[0] == b"bytes", "bytes at index 0")
        self.assertTrue(ar[1] == b"bits", "bits at index 1")
        self.assertTrue(str(ar) == "bytes, bits", "bytes and bits, str")
        try:
            ar[2]
            self.fail("Expected index error")
        except IndexError:
            pass
        try:
            ar2 = AcceptRanges.from_str("")
            self.fail("range unit required")
        except grammar.BadSyntax:
            pass
        ar2 = AcceptRanges.from_str("Bits,Bytes")
        self.assertTrue(
            ar2 == ar, "Equality test is case insensitive and sorted")
        self.assertTrue(
            str(ar2) == "Bits, Bytes",
            "str preserves order and case but not spae")
        try:
            AcceptRanges("bytes", "none", "bits")
            self.fail("none must be alone")
        except grammar.BadSyntax:
            pass

    def test_allow(self):
        allow = Allow()
        # none maps to an empty list of methods
        self.assertTrue(len(allow) == 0, "Default to no methods")
        self.assertTrue(str(allow) == "", "Default to no methods, str")
        allow = Allow("GET", "head", "PUT")
        self.assertTrue(len(allow) == 3, "3 methods")
        self.assertTrue(
            str(allow) == "GET, HEAD, PUT", "Force upper-case on str")
        self.assertTrue(allow[1] == b"HEAD", "HEAD at index 1")
        self.assertTrue(
            allow.is_allowed("head"), "method test case insensitive")
        try:
            allow[3]
            self.fail("Expected index error")
        except IndexError:
            pass
        allow2 = Allow.from_str("")
        self.assertTrue(
            len(allow2) == 0, "Empty string allowed for no methods")
        allow2 = Allow.from_str("PUT, get  ,, hEAd")
        self.assertTrue(
            allow2 == allow, "Equality test is case insensitive and sorted")
        self.assertTrue(
            str(allow2) == "PUT, GET, HEAD",
            "str preserves order but not case or space")

    def test_cache_control(self):
        try:
            cc = CacheControl()
            self.fail("Constructor requires at least one directive")
        except TypeError:
            pass
        cc = CacheControl("NO-cache")
        self.assertTrue(len(cc) == 1, "One item in cc")
        self.assertTrue("no-cache" in cc, "Case insensitive check")
        self.assertTrue(str(cc) == "no-cache", "Case insenstivie rendering")
        cc = CacheControl("no-store", ("max-age", 60))
        self.assertTrue(len(cc) == 2, "Two items in cc")
        self.assertTrue("max-age" in cc, "Tuple in constructor check")
        self.assertTrue(
            str(cc) == "no-store, max-age=60", "Unsorted rendering with token")
        cc = CacheControl("no-store", ("private", ("x", "y", "z")))
        self.assertTrue(len(cc) == 2, "Two items in cc")
        self.assertTrue(
            "private" in cc, "Tuple with tuple in constructor check")
        self.assertTrue(
            str(cc) == "no-store, private=\"x, y, z\"", "Quoted string")
        self.assertTrue(cc[0] == b"no-store", "integer index")
        self.assertTrue(
            cc[1] == (b"private", ("x", "y", "z")), "integer index 1")
        self.assertTrue(cc["no-store"] is None, "key no value")
        self.assertTrue(cc["private"] == ("x", "y", "z"), "key tuple value")
        cc = CacheControl(
            "no-transform", ("ext", "token"), ("ext2", "token=4"))
        self.assertTrue(
            str(cc) == "no-transform, ext=token, ext2=\"token=4\"",
            "Token and Quoted string")

    def test_content_range(self):
        cr = ContentRange()
        try:
            len(cr)
            self.fail("length of unsatisifed byte range not allowed")
        except ValueError:
            pass
        self.assertTrue(cr.first_byte is None)
        self.assertTrue(cr.last_byte is None)
        self.assertTrue(cr.total_len is None)
        self.assertFalse(cr.is_valid(), "range is not valid")
        self.assertTrue(str(cr) == "bytes */*", "str output")
        try:
            cr = ContentRange(0)
            self.fail("Contstructor requires byte ranges")
        except TypeError:
            pass
        cr = ContentRange(None, None, 1234)
        try:
            len(cr)
            self.fail("length of unsatisfied byte range")
        except ValueError:
            pass
        self.assertFalse(cr.is_valid(), "range is not valid")
        self.assertTrue(cr.total_len == 1234)
        cr = ContentRange(0, 499)
        self.assertTrue(len(cr) == 500, "Length of content range")
        self.assertTrue(cr.is_valid(), "range is valid")
        self.assertTrue(
            cr.first_byte == 0 and cr.last_byte == 499, "field values")
        self.assertTrue(cr.total_len is None, "Unknown total length")
        self.assertTrue(str(cr) == "bytes 0-499/*", "str output")
        cr1 = ContentRange.from_str("bytes 0-499 / 1234")
        self.assertTrue(
            cr1.first_byte == 0 and
            cr1.last_byte == 499 and
            cr1.total_len == 1234)
        self.assertTrue(cr1.is_valid())
        self.assertTrue(str(cr1) == "bytes 0-499/1234")
        cr2 = ContentRange.from_str("bytes 500-999/1234")
        self.assertTrue(cr2.first_byte == 500 and len(cr2) == 500)
        self.assertTrue(cr2.is_valid())
        cr3 = ContentRange.from_str("bytes 500-1233/1234")
        self.assertTrue(cr3.is_valid())
        self.assertTrue(len(cr3) == 1234 - 500)
        cr4 = ContentRange.from_str("bytes 734-1233/1234")
        self.assertTrue(cr4.is_valid())
        self.assertTrue(len(cr4) == 500)
        cr5 = ContentRange.from_str("bytes 734-734/1234")
        self.assertTrue(cr5.is_valid())
        self.assertTrue(len(cr5) == 1)
        cr6 = ContentRange.from_str("bytes 734-733/1234")
        self.assertFalse(cr6.is_valid())
        try:
            len(cr6)
            self.fail("Invalid range generates error on len")
        except ValueError:
            pass
        cr7 = ContentRange.from_str("bytes 734-1234/1234")
        self.assertFalse(cr7.is_valid())

    def test_content_type(self):
        req = Request()
        mtype = params.MediaType('application', 'octet-stream',
                                 {'charset': ['Charset', 'utf8']})
        req.set_content_type(mtype)
        self.assertTrue(req.get_header('Content-type') ==
                        b'application/octet-stream; Charset=utf8')
        self.assertTrue(isinstance(req.get_content_type(), params.MediaType))

    def test_transfer_encoding(self):
        """From RFC2616:

            When the "chunked" transfer-coding is used, it MUST be the
            last transfer-coding applied to the message-body

            The "chunked" transfer-coding MUST NOT be applied more than
            once to a message-body"""
        req = Request()
        req.set_transfer_encoding("gzip, chunked")
        req.set_transfer_encoding(
            params.TransferEncoding.list_from_str("gzip, chunked"))
        try:
            req.set_transfer_encoding(
                params.TransferEncoding.list_from_str("chunked, gzip"))
            self.fail("gzip after chunked transfer encoding")
        except ProtocolError:
            pass
        try:
            req.set_transfer_encoding(
                params.TransferEncoding.list_from_str(
                    "chunked, gzip, chunked"))
            self.fail("2xchunked transfer encoding")
        except ProtocolError:
            pass

    def test_upgrade(self):
        """From RFC2616:

            the upgrade keyword MUST be supplied within a Connection
            header field (section 14.10) whenever Upgrade is present in
            an HTTP/1.1 message"""
        req = Request()
        req.set_header("Upgrade", "HTTP/2.0, SHTTP/1.3, IRC/6.9, RTA/x11")
        protocols = req.get_upgrade()
        self.assertTrue(isinstance(protocols, list))
        self.assertTrue(len(protocols) == 4)
        for p in protocols:
            self.assertTrue(isinstance(p, params.ProductToken))
        req = Request()
        req.set_upgrade([params.ProductToken("HTTP", "2.0"),
                         params.ProductToken("SHTTP", "1.3")])
        self.assertTrue(req.get_header("Upgrade") == b"HTTP/2.0, SHTTP/1.3")
        self.assertTrue("upgrade" in req.get_connection())


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
