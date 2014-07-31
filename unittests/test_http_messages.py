#! /usr/bin/env python

import unittest
import logging
import random
from StringIO import StringIO

import pyslet.http.grammar as grammar
import pyslet.http.params as params
import pyslet.http.server as server

from pyslet.http.messages import *       # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(BufferedEntityWrapperTests, 'test'),
        unittest.makeSuite(MessageTests, 'test'),
        unittest.makeSuite(ChunkedTests, 'test'),
        unittest.makeSuite(HeaderTests, 'test'),
    ))


class BufferedEntityWrapperTests(unittest.TestCase):

    def test_goodsize(self):
        data = "How long is a piece of string?"
        src = StringIO(data)
        # default buffer is larger than src
        b = BufferedEntityWrapper(src)
        self.assertTrue(isinstance(b, io.RawIOBase))
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertTrue(b.seekable())
        self.assertTrue(b.length == len(data))
        pos = b.tell()
        self.assertTrue(pos == 0, "buffer starts at beginning of stream")
        for i in xrange(100):
            # check seek and read
            newpos = random.randint(0, len(data) + 1)
            rlen = random.randint(0, len(data) + 1)
            whence = random.choice((io.SEEK_SET, io.SEEK_CUR, io.SEEK_END))
            if whence == io.SEEK_CUR:
                adj = newpos - pos
            elif whence == io.SEEK_END:
                adj = newpos - len(data)
            elif whence == io.SEEK_SET:
                adj = newpos
            b.seek(adj, whence)
            self.assertTrue(b.tell() == newpos,
                            "Expected %i found %i" % (newpos, b.tell()))
            pos = newpos
            xlen = max(0, min(len(data) - pos, rlen))
            rdata = b.read(rlen)
            self.assertTrue(len(rdata) == xlen)
            self.assertTrue(rdata == data[pos:pos + rlen])
            pos += xlen

    def test_badsize(self):
        data = "How long is a piece of string?"
        src = StringIO(data)
        # make buffer smaller than src
        b = BufferedEntityWrapper(src, len(data) // 2)
        self.assertTrue(isinstance(b, io.RawIOBase))
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertFalse(b.seekable())
        self.assertTrue(b.length is None)
        buff = []
        while True:
            rdata = b.read(7)
            if rdata == '':
                break
            else:
                buff.append(rdata)
        result = string.join(buff, '')
        self.assertTrue(result == data, repr(result))
        # now read to align with buffer size
        src.seek(0)
        b = BufferedEntityWrapper(src, 10)
        buff = []
        while True:
            rdata = b.read(5)
            if rdata == '':
                break
            else:
                buff.append(rdata)
        result = string.join(buff, '')
        self.assertTrue(result == data, repr(result))
        # now read exactly buffer size
        src.seek(0)
        b = BufferedEntityWrapper(src, 10)
        buff = []
        while True:
            rdata = b.read(10)
            if rdata == '':
                break
            else:
                buff.append(rdata)
        result = string.join(buff, '')
        self.assertTrue(result == data, repr(result))

    def test_boundarysize(self):
        data = "How long is a piece of string?"
        src = StringIO(data)
        # make buffer same length as src
        b = BufferedEntityWrapper(src, len(data))
        self.assertTrue(isinstance(b, io.RawIOBase))
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        # not seekable as we can't peek past the end of src so it counts
        # as an overflow.
        self.assertFalse(b.seekable())
        self.assertTrue(b.length is None)
        # treat as readall
        result = b.read()
        self.assertTrue(result == data, repr(result))

    def test_blocked(self):
        data = "How long is a piece of string?"
        src = server.Pipe(rblocking=False, name="test_blocked")
        src.write(data)
        # no eof, default buffer size will trigger block
        b = BufferedEntityWrapper(src)
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertFalse(b.seekable())
        self.assertTrue(b.length is None)
        # but note that we can still peek on the data
        # that we have buffered
        self.assertTrue(b.peek(3) == data[0:3])

    def test_unblocked(self):
        data = "How long is a piece of string?"
        src = server.Pipe(rblocking=False, name="test_unblocked")
        # write one byte at a time
        for c in data:
            src.write(c)
        src.write_eof()
        # default buffer size outgrows pipe
        b = BufferedEntityWrapper(src)
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertTrue(b.seekable())
        self.assertTrue(b.length == len(data))
        # the buffer also smooths access to the data
        self.assertTrue(b.read(10) == data[0:10])

    def test_peek(self):
        data = "How long is a piece of string?"
        src = StringIO(data)
        # make buffer smaller than src
        b = BufferedEntityWrapper(src, 10)
        self.assertTrue(b.peek(3) == data[0:3])
        self.assertTrue(b.read(8) == data[0:8], "Data consumed by peek")
        self.assertTrue(b.peek(3) == data[8:10], "Peek to end of buffer")
        nbytes = 0
        while nbytes < 3:
            rdata = b.read(3 - nbytes)
            self.assertTrue(rdata, "reading past buffer")
            nbytes += len(rdata)
        # now peek should always return empty
        self.assertTrue(b.peek(1) == "", "Can't peek past end of buffer")


class ChunkedTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()

    def tearDown(self):     # noqa
        os.chdir(self.cwd)

    def test_chunked_reader(self):
        src = StringIO("10\r\n0123456789ABCDEF\r\n"
                       "5; ext=true\r\n01234\r\n"
                       "0\r\nhead: false trailer\r\n\r\ntrailer")
        r = ChunkedReader(src)
        self.assertTrue(r.read() == "0123456789ABCDEF01234", "unchunked data")
        self.assertTrue(src.read() == "trailer", "trailer left on the stream")


class MessageTests(unittest.TestCase):

    def test_simple(self):
        request = Request()
        # test ability to hold a simple request
        request.start_receiving()
        self.assertTrue(request.recv_mode() == request.RECV_LINE)
        request.recv("GET /pub/WWW/TheProject.html HTTP/1.1\r\n")
        self.assertTrue(request.recv_mode() == request.RECV_HEADERS)
        request.recv(["Host: www.w3.org\r\n", "\r\n"])
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
        request = Request(entity_body=StringIO("How long?"))
        request.set_method("PUT")
        request.set_request_uri("/resource")
        request.set_host("www.example.com")
        request.start_sending(params.HTTP_1p0)
        # a content-length must have been set
        self.assertTrue(request.get_content_length() is not None)
        self.assertTrue(request.get_transfer_encoding() is None)
        # now check that we default to chunked instead of buffering
        request = Request(entity_body=StringIO("How long?"))
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
        request.recv("POST /script.cgi HTTP/1.1\r\n")
        request.recv(["Transfer-Encoding: gzip, chunked\r\n", "\r\n"])
        # message must now be in line mode for chunk header
        self.assertTrue(request.recv_mode() == request.RECV_LINE)
        response = Response(request)
        response.start_receiving()
        response.recv("HTTP/1.1 200 OK\r\n")
        response.recv(["Transfer-Encoding: gzip\r\n", "\r\n"])
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
        request.recv("POST /script.cgi HTTP/1.1\r\n")
        request.recv(["Transfer-Encoding: chunked\r\n", "\r\n"])
        chunk1 = "The quick brown "
        chunk2 = "fox jumped over the lazy dog."
        request.recv('%X ; a=xyz; b="\\"odd\\\rparam\\\n"\r\n' % len(chunk1))
        request.recv(chunk1)
        request.recv('\r\n')
        request.recv('%X\r\n' % len(chunk2))
        request.recv(chunk2)
        request.recv('\r\n')
        request.recv('0; the=end \r\n')
        request.recv(['\r\n'])
        self.assertTrue(request.entity_body.getvalue() == chunk1 + chunk2)

    def test_gzip(self):
        srcbody = StringIO("The quick brown fox jumped over the lazy dog")
        zchunked = StringIO()
        dstbody = StringIO()
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
        headers = map(lambda x: x + grammar.CRLF, headers.split('\r\n')[:-1])
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
        response_start = "HTTP/1.1 206 Partial Content\r\n"
        response_headers = [
            "Date: Wed, 15 Nov 1995 06:25:24 GMT\r\n",
            "Last-Modified: Wed, 15 Nov 1995 04:58:08 GMT\r\n",
            "Content-type: multipart/byteranges; "
            "boundary=THIS_STRING_SEPARATES\r\n",
            "\r\n"]
        response_body = [
            "--THIS_STRING_SEPARATES\r\n",
            "Content-type: application/pdf\r\n",
            "Content-range: bytes 500-999/8000\r\n",
            "\r\n",
            "...the first range...\r\n",
            "--THIS_STRING_SEPARATES\r\n",
            "Content-type: application/pdf\r\n",
            "Content-range: bytes 7000-7999/8000\r\n",
            "\r\n",
            "...the second range\r\n",
            "--THIS_STRING_",
            "SEPARATES-- junk \r\n"]
        dstbody = StringIO()
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
        self.assertTrue(dstbody.getvalue() ==
                        string.join(response_body, '')[:-8])
        response_headers = [
            "Date: Wed, 15 Nov 1995 06:25:24 GMT\r\n",
            "Last-Modified: Wed, 15 Nov 1995 04:58:08 GMT\r\n",
            "Content-type: multipart/mixed\r\n",
            "\r\n"]
        dstbody = StringIO()
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
        self.assertTrue(request.get_header("X-Test") == "good-bye")
        request.set_header("X-Test", "hello again", True)
        self.assertTrue(request.get_header("X-Test") ==
                        "good-bye, hello again")
        response = Response(request)
        response.start_receiving()
        response.recv("HTTP/1.1 200 OK\r\n")
        response.recv(["X-Test: hello\r\n", "x-test: good-bye\r\n", "\r\n"])
        self.assertTrue(response.get_header("X-test").strip() ==
                        "hello, good-bye")

    def test_message_body_req(self):
        """RFC2616:

            A message-body MUST NOT be included in a request if the
            specification of the request method (section 5.1.1) does not
            allow sending an entity-body in requests...

            A server SHOULD read and forward a message-body on any
            request"""
        request = Request(entity_body="Bad data")
        request.set_method("GET")
        request.set_request_uri("/")
        try:
            request.start_sending()
            self.fail("GET request with body")
        except HTTPException:
            pass
        body = StringIO()
        bad_data = "Bad data"
        request = Request(entity_body=body)
        request.start_receiving()
        request.recv("GET / HTTP/1.1\r\n")
        request.recv(["Content-Length: %i\r\n" % len(bad_data),
                      "Content-type: text/plain\r\n",
                      "\r\n"])
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
        body = "Bad data"
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
        response.recv("HTTP/1.1 200 OK")
        response.recv(
            ["Content-type: text/plain\r\n",
             "Content-Length: %i\r\n" % len(body),
             "\r\n"])
        self.assertTrue(response.recv_mode() is None)

    def test_message_body_res(self):
        """RFC2616:

            All 1xx (informational), 204 (no content), and 304 (not
            modified) responses MUST NOT include a message-body"""
        request = Request()
        request.set_method("PUT")
        request.set_request_uri("/resource")
        body = "Bad data"
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
            response.recv("HTTP/1.1 %i For Testing" % i)
            response.recv(
                ["Content-type: text/plain\r\n",
                 "Content-Length: %i\r\n" % len(body),
                 "\r\n"])
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
        body = "Bad data"
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
        request.recv("PUT /resource HTTP/1.1\r\n")
        request.recv([
            "Content-Length: %i\r\n" % (len(body) - 3),  # misleading length
            "Content-Type: text/plain\r\n",
            "Transfer-Encoding: chunked\r\n",
            "\r\n"])
        # so we should be back in line mode ready for
        # the chunk header
        self.assertTrue(request.recv_mode() == request.RECV_LINE)
        request.recv("%X\r\n" % len(body))
        request.recv(body)
        request.recv(grammar.CRLF)
        request.recv("0\r\n")
        request.recv([grammar.CRLF])
        self.assertTrue(request.entity_body.getvalue() == body)
        request = Request()
        request.start_receiving()
        request.recv("PUT /resource HTTP/1.1\r\n")
        request.recv([
            "Content-Length: %i\r\n" % len(body),
            "Content-Type: text/plain\r\n",
            "Transfer-Encoding: identity\r\n",
            "\r\n"])
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
        body = """--THIS_STRING_SEPARATES
Content-type: application/pdf
Content-range: bytes 500-999/8000

...the first range...
--THIS_STRING_SEPARATES
Content-type: application/pdf
Content-range: bytes 7000-7999/8000

...the second range
--THIS_STRING_SEPARATES--"""
        response = Response(request, entity_body=StringIO(body))
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
        self.assertTrue(
            type(
                rq_tokens.select_token(
                    ["en-US"])) in types.StringTypes,
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
        self.assertTrue(ar[0] == "bytes", "bytes at index 0")
        self.assertTrue(ar[1] == "bits", "bits at index 1")
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
        self.assertTrue(allow[1] == "HEAD", "HEAD at index 1")
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
        self.assertTrue(cc[0] == "no-store", "integer index")
        self.assertTrue(
            cc[1] == ("private", ("x", "y", "z")), "integer index 1")
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
                        'application/octet-stream; Charset=utf8')
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


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
