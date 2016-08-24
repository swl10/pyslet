#! /usr/bin/env python

import io
import logging
import unittest

from pyslet.http import grammar
from pyslet.http import messages as http
from pyslet.http import multipart
from pyslet.http.params import MediaType, APPLICATION_OCTETSTREAM
from pyslet.py2 import (
    byte,
    is_text,
    range3,
    ul)

from test_http_messages import MockBlockingByteReader


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(SyntaxTests, 'test'),
        unittest.makeSuite(MessagePartTests, 'test'),
        unittest.makeSuite(MultipartRecvWrapperTests, 'test'),
        unittest.makeSuite(MultipartSendWrapperTests, 'test')
    ))


class SyntaxTests(unittest.TestCase):

    def test_boundary_delimiter(self):
        # boundary_delimiter is read from the MediaType
        ct = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        boundary = multipart.get_boundary_delimiter(ct)
        self.assertTrue(boundary == "\r\n--gc0p4Jq0M2Yt08j34c0p")
        ct = MediaType.from_str(
            'multipart/mixed; boundary="gc0pJq0M:08jU534c0p"')
        boundary = multipart.get_boundary_delimiter(ct)
        self.assertTrue(boundary == "\r\n--gc0pJq0M:08jU534c0p")
        # boundary delimiters and headers are always 7bit US-ASCII
        # (non-US-ASCII encoding deprecated)
        ct = MediaType.from_str(
            ul('multipart/mixed; boundary="gc0pJq0M\xa608jU534c0p"'))
        try:
            boundary = multipart.get_boundary_delimiter(ct)
            self.fail("8-bit boundary")
        except multipart.MultipartError:
            pass
        # must be no longer than 70 characters, not counting the two
        # leading hyphens
        ct = MediaType.from_str(
            "multipart/mixed; boundary=abcdefghijklmnopqrstuvwxyz1234567890"
            "abcdefghijklmnopqrstuvwxyz12345678")
        self.assertTrue(len(multipart.get_boundary_delimiter(ct)) == 74)
        ct = MediaType.from_str(
            "multipart/mixed; boundary=abcdefghijklmnopqrstuvwxyz1234567890"
            "abcdefghijklmnopqrstuvwxyz123456789")
        try:
            multipart.get_boundary_delimiter(ct)
            self.fail("long boundary")
        except multipart.MultipartError:
            pass

    def test_make_delimiter(self):
        # function to make a delimiter
        been_there = set()
        for i in range3(100):
            # try it 100 times, should be different each time
            boundary = multipart.make_boundary_delimiter()
            self.assertFalse(boundary in been_there)
            # check the syntax
            self.assertTrue(multipart.is_valid_boundary(boundary))
            # check length, need at least 20 characters in length
            # representing 120 bits of information
            self.assertTrue(len(boundary) >= 20)
            been_there.add(boundary)
            # now do one with a prefix
            boundary = multipart.make_boundary_delimiter(b"-- boundary ")
            self.assertTrue(multipart.is_valid_boundary(boundary))
            self.assertTrue(len(boundary) >= 32)
            been_there.add(boundary)
        # now do an illegal one
        try:
            boundary = multipart.make_boundary_delimiter(b" boundary ")
            self.fail("boundary starts with space")
        except ValueError:
            pass
        try:
            boundary = multipart.make_boundary_delimiter(b"-- {boundary} ")
            self.fail("boundary contains illegal character")
        except ValueError:
            pass

    def test_boundary_syntax(self):
        """Tests for basic boundary classes."""
        # bcharsnospace :=  DIGIT / ALPHA / "'" / "(" / ")" / "+" / "_" /
        #                   "," / "-" / "." / "/" / ":" / "=" / "?"
        extras = b"'()+_,-./:=?"
        for i in range3(0, 256):
            b = byte(i)
            self.assertTrue(multipart.is_bcharnospace(b) ==
                            (b in extras or grammar.is_digit(b) or
                             grammar.is_alpha(b)))
            self.assertTrue(multipart.is_bchars(b) ==
                            (b in extras or grammar.is_digit(b) or
                             grammar.is_alpha(b) or b == grammar.SP))

    def test_specials(self):
        """Tests for basic byte classes."""
        # specials = "(" / ")" / "<" / ">" / "@" / "," / ";" / ":" /
        #            "\" / <"> /  "." / "[" / "]"
        specials = b"()<>@,;:\\\".[]"
        for i in range3(0, 256):
            b = byte(i)
            self.assertTrue(
                multipart.is_special(b) == (b in specials),
                "is_special(byte(%i))" % i)
        p = multipart.RFC822Parser("atomic/?={}.blondie")
        self.assertTrue(p.is_atom(), "It is an atom")
        result = p.parse_atom()
        self.assertTrue(result == b"atomic/?={}", "rfc822 atom: %s" % result)

    def test_atom_parser(self):
        # we have our own special atom parser that handles
        # domain-literals too
        p = multipart.RFC822Parser(" [10.0\.3.19] ")
        self.assertTrue(p.the_token, "Expected a token")
        self.assertFalse(p.is_atom(), "It is not an atom")
        self.assertTrue(p.is_domain_literal(), "Expected domain literal")
        self.assertTrue(p.parse_domain_literal() == "10.0.3.19")
        # check sub-domain
        p = multipart.RFC822Parser(" [10.0\.3.19] pyslet.org")
        # re-encoded as a canonical domain literal
        self.assertTrue(p.parse_sub_domain() == "[10.0.3.19]")
        self.assertTrue(p.parse_sub_domain() == "pyslet")
        self.assertTrue(p.parse_sub_domain() is None, ". is not a sub-domain")
        # check domain
        p = multipart.RFC822Parser(" [10.0\.3.19] .pyslet. org@home")
        self.assertTrue(p.require_domain() == "[10.0.3.19].pyslet.org")
        try:
            p.require_domain()
            self.fail("no domain to parse")
        except grammar.BadSyntax:
            pass
        # check local part
        p = multipart.RFC822Parser(' WWW . "pysle\\t" . org . [10.0.3.19]')
        self.assertTrue(p.require_localpart() == "WWW.pyslet.org")
        self.assertTrue(p.is_special(byte(".")))
        # and finally check the full addr-spec
        p = multipart.RFC822Parser(
            ' "www Pysle\\t" . Org @ [10.0.3.19]. pyslet.Org<')
        # domains are uninterpreted in addr-spec
        self.assertTrue(p.require_addr_spec() ==
                        '"www Pyslet".Org@[10.0.3.19].pyslet.Org')
        self.assertTrue(p.is_special(byte("<")))

    def test_msg_id(self):
        sources = (
            "<ddd @Org>",
            "<ddd @ Org>",
            "<ddd@ Org>",
            '<":sysmail"@  Some-Group. Some-Org>',
            '<Muhammed.(I am  the greatest) Ali @(the)Vegas.WBA>',
            '<"Full Name"@Domain >',
            "<sender@registry-A.registry-1.organization-X>",
            "<mailbox.sub1.sub2@this-domain>",
            "<sub-net.mailbox@sub-domain.domain>",
            "</main/davis/people/standard@Other-Host>",
            '<"<Jones>standard.dist.3"@Tops-20-Host>'
            )
        expected = (
            "ddd@Org",
            "ddd@Org",
            "ddd@Org",
            '":sysmail"@Some-Group.Some-Org',
            'Muhammed.Ali@Vegas.WBA',
            '"Full Name"@Domain',
            "sender@registry-A.registry-1.organization-X",
            "mailbox.sub1.sub2@this-domain",
            "sub-net.mailbox@sub-domain.domain",
            "/main/davis/people/standard@Other-Host",
            '"<Jones>standard.dist.3"@Tops-20-Host'
            )
        for i in range3(len(sources)):
            p = multipart.RFC822Parser(sources[i])
            try:
                result = p.require_msg_id()
                self.assertTrue(result == expected[i], result)
            except grammar.BadSyntax as e:
                logging.info("Testing: %s" % sources[i])
                logging.info(repr(p.tokens))
                logging.info(str(e))
                raise


class MessagePartTests(unittest.TestCase):

    def test_constructor(self):
        part = multipart.MessagePart()
        self.assertTrue(isinstance(part, http.Message))

    def test_content_transfer_encoding(self):
        part = multipart.MessagePart()
        # value is a single token, represented as a character string
        for token in ("7bit", "8bit", "binary", "quoted-printable",
                      "base64", "x-custom", "BINARY"):
            part.set_content_transfer_encoding(token)
            self.assertTrue(part.get_header('Content-Transfer-Encoding') ==
                            token.encode('ascii'))
            self.assertTrue(is_text(part.get_content_transfer_encoding()))
            self.assertTrue(part.get_content_transfer_encoding() ==
                            token.lower())
        # default is 7bit
        part.set_header('Content-Transfer-Encoding', None)
        self.assertTrue(part.get_content_transfer_encoding() == '7bit')
        # bad tokens should raise an error on set
        try:
            part.set_content_transfer_encoding("9:bit")
            self.fail("bad token in content-transfer-encoding (set)")
        except ValueError:
            pass
        part.set_header('Content-Transfer-Encoding', b"9:bit")
        # badly formed should be treated as an unrecognized value
        self.assertTrue(part.get_content_transfer_encoding() is None)
        # Any entity with an unrecognized Content-Transfer-Encoding must
        # be treated as if it has a Content-Type of
        # "application/octet-stream", regardless of what the
        # Content-Type header field actually says.
        self.assertTrue(part.get_content_type() == APPLICATION_OCTETSTREAM)
        part.set_content_type("text/plain")
        self.assertTrue(part.get_content_type() == APPLICATION_OCTETSTREAM)
        part.set_content_transfer_encoding("9bit")
        self.assertTrue(part.get_content_type() == APPLICATION_OCTETSTREAM)

    def test_content_id(self):
        part = multipart.MessagePart()
        # value is a character string that must be a valid addr-spec
        # spaces are removed and ignored as per specification
        part.set_content_id(" content @ pyslet.org ")
        self.assertTrue(part.get_header('Content-ID') ==
                        b"<content@pyslet.org>")
        self.assertTrue(is_text(part.get_content_id()))
        self.assertTrue(part.get_content_id() == "content@pyslet.org")
        try:
            part.set_content_id("content:1@pyslet.org")
            self.fail("bad localpart in content ID")
        except grammar.BadSyntax:
            pass
        part.set_header("Content-ID", b"content:1@pyslet.org")
        self.assertTrue(part.get_content_id() is None)

    def test_content_description(self):
        part = multipart.MessagePart()
        # any text, though non-ascii will be problematic 'the mechanism
        # specified in RFC 2047' is broken and not work implementing. we
        # treat this field as ASCII text or raw bytes with spaces trimmed
        part.set_content_description(" About my content ")
        self.assertTrue(part.get_header('Content-Description') ==
                        b"About my content")
        self.assertTrue(part.get_content_description() == b"About my content")
        try:
            part.set_content_description(ul("Caf\xe9"))
            self.fail("Content description should ASCII encode")
        except UnicodeError:
            pass
        # OK to pass raw bytes
        part.set_content_description(ul("Caf\xe9").encode('iso-8859-1'))
        self.assertTrue(part.get_header('Content-Description') == b"Caf\xe9")
        self.assertTrue(part.get_content_description() == b"Caf\xe9")


class MultipartRecvWrapperTests(unittest.TestCase):

    SIMPLE_TYPE = MediaType.from_str(
        'multipart/mixed; boundary="simple boundary"')

    SIMPLE = (
        b"This is the preamble.  It is to be ignored, though it",
        b"is a handy place for composition agents to include an",
        b"explanatory note to non-MIME conformant readers.",
        b"",
        b"--simple boundary",
        b"",
        b"This is implicitly typed plain US-ASCII text.",
        b"It does NOT end with a linebreak.",
        b"--simple boundary",
        b"Content-type: text/plain; charset=us-ascii",
        b"",
        b"This is explicitly typed plain US-ASCII text.",
        b"It DOES end with a linebreak.",
        b"",
        b"--simple boundary--",
        b"",
        b"This is the epilogue.  It is also to be ignored.")

    def test_constructor(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        # pass in a source stream and a MediaType
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        try:
            mstream.fileno()
            self.fail("MultipartRecvWrapper.fileno")
        except IOError:
            pass
        # flush does nothing but is callable
        mstream.flush()
        self.assertFalse(mstream.isatty())
        self.assertTrue(mstream.readable())
        mstream.close()

    def test_close(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        self.assertFalse(mstream.closed)
        mstream.close()
        self.assertTrue(mstream.closed)
        try:
            mstream.read(1)
            self.fail("MultipartRecvWrapper.read after close")
        except IOError:
            pass

    def test_readline(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        # starts by reading the preamble
        self.assertTrue(
            mstream.readline() ==
            b"This is the preamble.  It is to be ignored, though it\r\n")
        mstream.readline()
        # note the preamble ends with a line break
        self.assertTrue(
            mstream.readline() ==
            b"explanatory note to non-MIME conformant readers.\r\n")
        # that's the lot
        self.assertTrue(mstream.readline() == b"")
        mstream.close()

    def test_readlines(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        # starts by reading the preamble
        lines = mstream.readlines(10)
        self.assertTrue(len(lines) == 1)
        self.assertTrue(
            lines[0] ==
            b"This is the preamble.  It is to be ignored, though it\r\n")
        lines = mstream.readlines()
        self.assertTrue(len(lines) == 2, lines)
        # note the preamble ends with a line break
        self.assertTrue(
            lines[1] ==
            b"explanatory note to non-MIME conformant readers.\r\n")
        # that's the lot
        self.assertTrue(mstream.readline() == b"")
        mstream.close()

    def test_read(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        # blocking stream
        c = mstream.read(1)
        self.assertTrue(c == b"T")
        line = []
        while c != b"\n":
            line.append(c)
            c = mstream.read(1)
            # won't return None
            self.assertTrue(len(c) == 1)
        self.assertTrue(
            b"".join(line) ==
            b'This is the preamble.  It is to be ignored, though it\r')
        data = mstream.read()
        self.assertTrue(data.endswith(b"readers.\r\n"), data)
        self.assertTrue(mstream.read(1) == b"")
        mstream.close()

    def test_read_nonblocking(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        # simulate breaks in the data after LF
        src = MockBlockingByteReader(src, block_after=((10,)))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        # non-blocking non-empty stream
        line = []
        blocks = 0
        while True:
            c = mstream.read(1)
            if c:
                if c == b"\n":
                    break
                else:
                    line.append(c)
                    continue
            self.assertTrue(c is None,
                            "stream non-blocking: %s" % repr(c))
            blocks += 1
        # our mock blocking stream always returns None at least once
        self.assertTrue(blocks > 1, "non-blocking stream failed to stall")
        self.assertTrue(
            b"".join(line) ==
            b'This is the preamble.  It is to be ignored, though it\r')
        # readall behaviour is undefined, don't test it
        mstream.close()

    def test_seek(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        self.assertFalse(mstream.seekable())
        try:
            mstream.seek(0)
            self.fail("MultipartRecvWrapper.seek")
        except IOError:
            pass
        try:
            mstream.tell()
            self.fail("MultipartRecvWrapper.tell")
        except IOError:
            pass
        try:
            mstream.truncate(0)
            self.fail("MultipartRecvWrapper.truncate")
        except IOError:
            pass
        mstream.close()

    def test_write(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        self.assertFalse(mstream.writable())
        try:
            mstream.write(b"Hello")
            self.fail("MultipartRecvWrapper.write")
        except IOError:
            pass
        mstream.close()

    def check_boundaries(self, mstream):
        # read one line from the preamble
        mstream.readline()
        # read_boundary discards the rest
        self.assertTrue(mstream.read_boundary())
        # now we're in the first proper part, which starts with blank
        # line
        self.assertTrue(mstream.readline() == b"\r\n")
        lines = mstream.readlines()
        self.assertTrue(len(lines) == 2)
        # The CRLF preceding the boundary delimiter line is conceptually
        # attached to the boundary so that it is possible to have a part
        # that does not end with a CRLF (line  break)
        self.assertTrue(lines[1] == b"It does NOT end with a linebreak.")
        # check we can't read any more data
        self.assertTrue(mstream.read(1) == b"")
        self.assertTrue(mstream.read_boundary())
        data = mstream.readall()
        self.assertTrue(data.endswith(b"It DOES end with a linebreak.\r\n"))
        self.assertFalse(mstream.read_boundary())
        data = mstream.readall()
        self.assertTrue(data.endswith(
            b"\r\nThis is the epilogue.  It is also to be ignored."))

    def test_read_boundary(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        self.check_boundaries(mstream)
        # it is an error to call read_boundary during the epilogue
        try:
            mstream.read_boundary()
            self.fail("expected MultipartError")
        except multipart.MultipartError:
            pass
        # now check for non-blocking case
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        # simulate breaks in the data after LF
        src = MockBlockingByteReader(src, block_after=((10,)))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        blocks = 0
        while True:
            result = mstream.read_boundary()
            if result is None:
                # blocked, continue
                blocks += 1
                continue
            if result is False:
                break
        if not blocks:
            logging.warning("read_boundary expected at least one None")

    LWS = (
        b"This is the preamble.  It is to be ignored, though it",
        b"is a handy place for composition agents to include an",
        b"explanatory note to non-MIME conformant readers.",
        b"",
        b"--simple boundary \t",
        b"",
        b"This is implicitly typed plain US-ASCII text.",
        b"It does NOT end with a linebreak.",
        b"--simple boundary\t",
        b"Content-type: text/plain; charset=us-ascii",
        b"",
        b"This is explicitly typed plain US-ASCII text.",
        b"It DOES end with a linebreak.",
        b"",
        b"--simple boundary-- ",
        b"",
        b"This is the epilogue.  It is also to be ignored.")

    def test_lws(self):
        # The boundary may be followed by zero or more characters of
        # linear whitespace.
        src = io.BytesIO(grammar.CRLF.join(self.LWS))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        self.check_boundaries(mstream)

    BAD = (
        b"This is the preamble.  It is to be ignored, though it",
        b"is a handy place for composition agents to include an",
        b"explanatory note to non-MIME conformant readers.",
        b"",
        b"--simple boundary",
        b"",
        b"This is implicitly typed plain US-ASCII text.",
        b"It does NOT end with a linebreak.",
        b"--simple boundary  extra data  ",
        b"Content-type: text/plain; charset=us-ascii",
        b"",
        b"This is explicitly typed plain US-ASCII text.",
        b"It DOES end with a linebreak.",
        b"",
        b"--simple boundary--",
        b"",
        b"This is the epilogue.  It is also to be ignored.")

    def test_bad_boundary(self):
        # Boundary string comparisons must compare the boundary value
        # with the beginning of each candidate line.  An exact match of
        # the entire candidate line is not required; it is sufficient
        # that the boundary appear in its entirety following the CRLF.
        #
        # Therefore, a boundary delimiter followed by anything other
        # than white space suggests a violation of:
        #
        # Boundary delimiters must not appear within the encapsulated
        # material
        src = io.BytesIO(grammar.CRLF.join(self.BAD))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        # ignore the preamble
        self.assertTrue(mstream.read_boundary())
        try:
            mstream.read_boundary()
            self.fail("boundary detected in encapsulated material")
        except multipart.MultipartError:
            pass

    def test_next_part(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        # first call advances past the preamble
        part1 = mstream.next_part()
        self.assertTrue(isinstance(part1, http.RecvWrapper))
        self.assertTrue(isinstance(part1.message, multipart.MessagePart))
        # the process of reading from this wrapper will force the
        # headers to be read...
        #
        # [the boundary delimiter] is then terminated by either another
        # CRLF and the header fields for the next part, or by two CRLFs,
        # in which case there are no header fields for the next part.
        lines = part1.readlines()
        # NO header fields are actually required in body parts
        self.assertTrue(len(part1.message.get_headerlist()) == 0)
        # but we simulate the default Content-Type
        mtype = part1.message.get_content_type()
        self.assertTrue(isinstance(mtype, MediaType))
        self.assertTrue(mtype.type == "text")
        self.assertTrue(mtype.subtype == "plain")
        self.assertTrue(mtype['charset'] == b"us-ascii")
        # The blank line is ignored as it terminates empty headers
        self.assertTrue(len(lines) == 2)
        self.assertTrue(lines[1] == b"It does NOT end with a linebreak.")
        # check we can't read any more data
        self.assertTrue(part1.read(1) == b"")
        part2 = mstream.next_part()
        lines = part2.readlines()
        self.assertTrue(len(part2.message.get_headerlist()) == 1)
        mtype = part2.message.get_content_type()
        self.assertTrue(isinstance(mtype, MediaType))
        self.assertTrue(mtype.type == "text")
        self.assertTrue(mtype.subtype == "plain")
        self.assertTrue(mtype['charset'] == b"us-ascii")
        try:
            mstream.next_part()
            self.fail("Expected StopIteration for epilogue")
        except StopIteration:
            pass
        # check non-blocking case
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        # simulate breaks in the data after LF
        src = MockBlockingByteReader(src, block_after=((10,)))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        blocks = 0
        parts = 0
        while True:
            try:
                part = mstream.next_part()
            except StopIteration:
                break
            if part is None:
                # blocked, continue
                blocks += 1
                continue
            parts += 1
        self.assertTrue(parts == 2)
        if not blocks:
            logging.warning("next_part expected at least one None")

    def test_read_parts(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        parts = []
        for part in mstream.read_parts():
            self.assertTrue(isinstance(part, http.RecvWrapper))
            self.assertTrue(isinstance(part.message, multipart.MessagePart))
            # headers should already be loaded
            nheaders = len(part.message.get_headerlist())
            parts.append((part, part.readlines()))
            self.assertTrue(nheaders == len(part.message.get_headerlist()))
        self.assertTrue(len(parts) == 2)
        lines = parts[0][1]
        self.assertTrue(len(lines) == 2)
        self.assertTrue(lines[1] == b"It does NOT end with a linebreak.")
        lines = parts[1][1]
        self.assertTrue(len(lines) == 2)
        self.assertTrue(lines[1] == b"It DOES end with a linebreak.\r\n")
        # check non-blocking case
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        # simulate breaks in the data after LF
        src = MockBlockingByteReader(src, block_after=((10,)))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        blocks = 0
        parts = []
        for part in mstream.read_parts():
            if part is None:
                blocks += 1
            else:
                self.assertTrue(isinstance(part, http.RecvWrapper))
                self.assertTrue(isinstance(part.message,
                                           multipart.MessagePart))
                # headers should already be loaded
                nheaders = len(part.message.get_headerlist())
                parts.append(part)
                self.assertTrue(nheaders ==
                                len(part.message.get_headerlist()))
        self.assertTrue(len(parts) == 2)
        if not blocks:
            logging.warning("read_parts expected at least one None")

    EMPTY = (
        b"This is the preamble.  It is to be ignored, though it",
        b"is a handy place for composition agents to include an",
        b"explanatory note to non-MIME conformant readers.",
        b"--simple boundary--",
        b"",
        b"This is the epilogue.  It is also to be ignored.")

    def test_empty(self):
        # The body must contain one or more body parts
        src = io.BytesIO(grammar.CRLF.join(self.EMPTY))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        try:
            mstream.next_part()
            self.fail("no boundary")
        except multipart.MultipartError:
            pass
        # try the same thing but with no boundary at all
        src = io.BytesIO(grammar.CRLF.join(self.EMPTY[:-3]))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        try:
            mstream.next_part()
            self.fail("no boundary")
        except multipart.MultipartError:
            pass

    def test_header_defaults(self):
        src = io.BytesIO(grammar.CRLF.join(self.SIMPLE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        parts = [part for part in mstream.read_parts()]
        # A body part that starts with a blank line ... is a body part
        # for which all default values are to be assumed.
        p = parts[0]
        # The absence of a Content-Type 'usually' indicates "text/plain;
        # charset=US-ASCII". If no Content-Type field is present it is
        # assumed to be "message/rfc822" in a "multipart/digest" and
        # "text/plain" otherwise.
        t = p.message.get_content_type()
        self.assertTrue(t == "text/plain; charset=us-ascii")
        # "Content-Transfer-Encoding: 7BIT" is assumed if the
        # Content-Transfer-Encoding header field is not present.
        self.assertTrue(p.message.get_content_transfer_encoding() == "7bit")
        self.assertTrue(p.message.get_content_id() is None)
        self.assertTrue(p.message.get_content_description() is None)

    MISC_HEADERS = (
        b"Preamble",
        b"",
        b"--simple boundary",
        b"Content-type: text/plain; charset=us-ascii",
        b"Content-Description: misc header test",
        b"User-Agent: pyslet/1.0",
        b"",
        b"This is explicitly typed plain US-ASCII text.",
        b"It DOES end with a linebreak.",
        b"",
        b"--simple boundary--",
        b"",
        b"This is the epilogue.  It is also to be ignored.")

    def test_misc_headers(self):
        src = io.BytesIO(grammar.CRLF.join(self.MISC_HEADERS))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        parts = [part for part in mstream.read_parts()]
        # Only Content- header fields have meaning, others may be
        # ignored but should be retained
        p = parts[0]
        self.assertTrue(p.message.get_header('User-Agent') == b"pyslet/1.0")

    NESTED = (
        b"Preamble",
        b"",
        b"--simple boundary",
        b"Content-type: multipart/alternative; boundary=nested",
        b"",
        b"Nested Preamble",
        b"--nested",
        b"",
        b"This is explicitly typed plain US-ASCII text.",
        b"It DOES end with a linebreak.",
        b"",
        b"--nested--",
        b"--simple boundary--",
        b"",
        b"This is the epilogue.  It is also to be ignored.")

    def test_nested(self):
        src = io.BytesIO(grammar.CRLF.join(self.NESTED))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        for part in mstream.read_parts():
            self.assertTrue(part.message.get_content_type().type ==
                            "multipart")
            # so part should be a readable stream we can wrap
            nstream = multipart.MultipartRecvWrapper(
                part, part.message.get_content_type())
            nparts = [np for np in nstream.read_parts()]
            self.assertTrue(len(nparts) == 1)
        # MIME implementations are therefore required to recognize outer
        # level boundary markers at ANY level of inner nesting.
        bad_nested = list(self.NESTED)
        # remove the closing inner boundary
        del bad_nested[11]
        src = io.BytesIO(grammar.CRLF.join(bad_nested))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        for part in mstream.read_parts():
            self.assertTrue(part.message.get_content_type().type ==
                            "multipart")
            # so part should be a readable stream we can wrap
            nstream = multipart.MultipartRecvWrapper(
                part, part.message.get_content_type())
            try:
                nparts = [np for np in nstream.read_parts()]
                self.fail("Expected multipart error due to missing boundary")
            except multipart.MultipartError:
                pass
        # but not error from the outer multipart parser

    NO_PREAMBLE_OR_EPILOGUE = (
        b"--simple boundary",
        b"",
        b"This is plain US-ASCII text.",
        b"",
        b"--simple boundary--")

    def test_no_preamble_or_epilogue(self):
        src = io.BytesIO(grammar.CRLF.join(self.NO_PREAMBLE_OR_EPILOGUE))
        mstream = multipart.MultipartRecvWrapper(src, self.SIMPLE_TYPE)
        parts = [p for p in mstream.read_parts()]
        self.assertTrue(len(parts) == 1)


class MultipartSendWrapperTests(unittest.TestCase):

    def test_constructor(self):
        part = multipart.MessagePart()
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        # pass in an iterable of MessageParts and required mime type
        mstream = multipart.MultipartSendWrapper(mtype, [part])
        try:
            mstream.fileno()
            self.fail("MultipartSendWrapper.fileno")
        except IOError:
            pass
        # flush does nothing but is callable
        mstream.flush()
        self.assertFalse(mstream.isatty())
        self.assertTrue(mstream.readable())
        mstream.close()
        # can add an optional preamble, epilogue and boundary
        mstream = multipart.MultipartSendWrapper(
            mtype, [part], preamble=b"Hello", epilogue=b"Goodbye")

    def test_close(self):
        part = multipart.MessagePart()
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        # pass in an iterable of MessageParts
        mstream = multipart.MultipartSendWrapper(mtype, [part])
        self.assertFalse(mstream.closed)
        mstream.close()
        self.assertTrue(mstream.closed)
        try:
            mstream.read(1)
            self.fail("MultipartSendWrapper.read after close")
        except IOError:
            pass

    def test_readline(self):
        part = multipart.MessagePart(entity_body=b"How are you?")
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(mtype, [part])
        # preamble is empty, straight into the boundary
        self.assertTrue(
            mstream.readline() ==
            b"--gc0p4Jq0M2Yt08j34c0p\r\n")
        self.assertTrue(
            mstream.readline() ==
            b"Content-Type: text/plain\r\n")
        # blank line
        self.assertTrue(mstream.readline() == b"\r\n")
        # body
        self.assertTrue(mstream.readline() == b"How are you?\r\n")
        # terminating boundary has NO CRLF
        self.assertTrue(
            mstream.readline() ==
            b"--gc0p4Jq0M2Yt08j34c0p--")

    def test_readlines(self):
        # Now try with preamble and epilogue (no CRLF)
        part = multipart.MessagePart(entity_body=b"How are you?")
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(
            mtype, [part], preamble=b"Just wanted to ask\r\n...",
            epilogue=b"Fine\r\nthanks!")
        lines = mstream.readlines()
        matches = [
            b"Just wanted to ask\r\n",
            b"...\r\n",
            b"--gc0p4Jq0M2Yt08j34c0p\r\n",
            b"Content-Type: text/plain\r\n",
            b"\r\n",
            b"How are you?\r\n",
            b"--gc0p4Jq0M2Yt08j34c0p--\r\n",
            b"Fine\r\n",
            b"thanks!"]
        self.assertTrue(len(lines) == len(matches))
        for line, match in zip(lines, matches):
            self.assertTrue(line == match, "Failed to match: %s" % match)
        mstream.close()

    def test_readlines_crlf(self):
        # Now repeat the exercise with maximal CRLF
        part = multipart.MessagePart(entity_body=b"\r\nHow are you?\r\n")
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(
            mtype, [part], preamble=b"\r\nJust wanted to ask\r\n",
            epilogue=b"\r\nFine thanks!\r\n")
        lines = mstream.readlines()
        matches = [
            b"\r\n",
            b"Just wanted to ask\r\n",
            b"\r\n",
            b"--gc0p4Jq0M2Yt08j34c0p\r\n",
            b"Content-Type: text/plain\r\n",
            b"\r\n",
            b"\r\n",
            b"How are you?\r\n",
            b"\r\n",
            b"--gc0p4Jq0M2Yt08j34c0p--\r\n",
            b"\r\n",
            b"Fine thanks!\r\n"]
        self.assertTrue(len(lines) == len(matches), lines)
        for line, match in zip(lines, matches):
            self.assertTrue(line == match, "Failed to match: %s" % match)
        mstream.close()

    def test_read(self):
        part = multipart.MessagePart(entity_body=b"How are you?")
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(
            mtype, [part], preamble=b"Just wanted to ask\r\n...",
            epilogue=b"Fine\r\nthanks!")
        # blocking stream
        c = mstream.read(1)
        self.assertTrue(c == b"J")
        line = []
        while c != b"\n":
            line.append(c)
            c = mstream.read(1)
            # won't return None
            self.assertTrue(len(c) == 1)
        self.assertTrue(
            b"".join(line) ==
            b'Just wanted to ask\r')
        data = mstream.read()
        self.assertTrue(data.endswith(b"Fine\r\nthanks!"), data)
        self.assertTrue(mstream.read(1) == b"")
        mstream.close()

    def test_read_nonblocking(self):
        src = io.BytesIO(b"How are you?\n" * 10)
        src = MockBlockingByteReader(src, block_after=((10,)))
        part = multipart.MessagePart(entity_body=src)
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(mtype, [part])
        # non-blocking non-empty stream
        lines = []
        line = []
        blocks = 0
        while True:
            c = mstream.read(1)
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
        self.assertTrue(boundary > 0, lines)
        for line in lines[boundary + 1:boundary + 11]:
            self.assertTrue(line == b"How are you?")
        mstream.close()

    def test_seek(self):
        part = multipart.MessagePart(entity_body=b"How are you?")
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(mtype, [part])
        self.assertFalse(mstream.seekable())
        try:
            mstream.seek(0)
            self.fail("MultipartSendWrapper.seek")
        except IOError:
            pass
        try:
            mstream.tell()
            self.fail("MultipartSendWrapper.tell")
        except IOError:
            pass
        try:
            mstream.truncate(0)
            self.fail("MultipartSendWrapper.truncate")
        except IOError:
            pass
        mstream.close()

    def test_write(self):
        part = multipart.MessagePart(entity_body=b"How are you?")
        part.set_content_type("text/plain")
        mtype = MediaType.from_str(
            "multipart/mixed; boundary=gc0p4Jq0M2Yt08j34c0p")
        mstream = multipart.MultipartSendWrapper(mtype, [part])
        self.assertFalse(mstream.writable())
        try:
            mstream.write(b"Hello")
            self.fail("MultipartSendWrapper.write")
        except IOError:
            pass
        mstream.close()

    def test_multiple(self):
        part1 = multipart.MessagePart(
            entity_body=b"plain text version\r\n")
        part1.set_content_type("text/plain; charset=us-ascii")
        part2 = multipart.MessagePart(
            entity_body=b"RFC 1896 text/enriched version\r\n")
        part2.set_content_type("text/enriched")
        part3 = multipart.MessagePart(
            entity_body=b"fanciest version\r\n")
        part3.set_content_type("application/x-whatever")
        mtype = MediaType.from_str(
            "multipart/alternative; boundary=boundary42")
        mstream = multipart.MultipartSendWrapper(mtype, [part1, part2, part3])
        self.assertTrue(
            mstream.read() == b"--boundary42\r\n"
            b"Content-Type: text/plain; charset=us-ascii\r\n"
            b"\r\n"
            b"plain text version\r\n"
            b"\r\n"
            b"--boundary42\r\n"
            b"Content-Type: text/enriched\r\n"
            b"\r\n"
            b"RFC 1896 text/enriched version\r\n"
            b"\r\n"
            b"--boundary42\r\n"
            b"Content-Type: application/x-whatever\r\n"
            b"\r\n"
            b"fanciest version\r\n"
            b"\r\n"
            b"--boundary42--")

    def test_nested(self):
        part_a = multipart.MessagePart(entity_body=b"Introduction")
        part_a.set_content_type("text/plain")
        part1 = multipart.MessagePart(
            entity_body=b"plain text version\r\n")
        part1.set_content_type("text/plain; charset=us-ascii")
        part2 = multipart.MessagePart(
            entity_body=b"RFC 1896 text/enriched version\r\n")
        part2.set_content_type("text/enriched")
        mtype = MediaType.from_str(
            'multipart/alternative; boundary="---- next message ----"')
        mstream = multipart.MultipartSendWrapper(mtype, [part1, part2])
        part_b = multipart.MessagePart(entity_body=mstream)
        part_b.set_content_type(mtype)
        mtype = MediaType.from_str(
            'multipart/mixed; boundary="---- main boundary ----"')
        mstream = multipart.MultipartSendWrapper(mtype, [part_a, part_b])
        result = mstream.read()
        self.assertTrue(
            result == b"------ main boundary ----\r\n"
            b'Content-Type: text/plain\r\n'
            b"\r\n"
            b"Introduction\r\n"
            b"------ main boundary ----\r\n"
            b"Content-Type: multipart/alternative; "
            b'boundary="---- next message ----"\r\n'
            b"\r\n"
            b"------ next message ----\r\n"
            b"Content-Type: text/plain; charset=us-ascii\r\n"
            b"\r\n"
            b"plain text version\r\n"
            b"\r\n"
            b"------ next message ----\r\n"
            b"Content-Type: text/enriched\r\n"
            b"\r\n"
            b"RFC 1896 text/enriched version\r\n"
            b"\r\n"
            b"------ next message ------\r\n"
            b"------ main boundary ------", repr(result))

# no encoding other than "7bit", "8bit", or "binary" is permitted for
# entities of type "multipart"


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
