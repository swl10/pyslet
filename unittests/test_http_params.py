#! /usr/bin/env python

import unittest
import logging

import pyslet.http.grammar as grammar

from pyslet.py2 import byte, ul
from pyslet.http.params import *       # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ProtocolParameterTests, 'test'),
    ))


class ProtocolParameterTests(unittest.TestCase):

    def test_version(self):
        """test HTTPVersion

        RFC2616 quotes...

            Note that the major and minor numbers MUST be treated as
            separate integers and that each MAY be incremented higher
            than a single digit.

            Leading zeros MUST be ignored by recipients and MUST NOT be
            sent."""
        v = HTTPVersion()
        self.assertTrue(v.major == 1 and v.minor == 1, "1.1 on construction")
        self.assertTrue(str(v) == "HTTP/1.1", "Formatting")
        v = HTTPVersion(1)
        self.assertTrue(v.major == 1 and v.minor == 1, "1.1 on construction")
        v = HTTPVersion(2)
        self.assertTrue(v.major == 2 and v.minor == 0, "2.0 on construction")
        v = HTTPVersion(2, 1)
        self.assertTrue(v.major == 2 and v.minor == 1, "2.1 on construction")
        v = HTTPVersion.from_str(" HTTP / 1.0 ")
        self.assertTrue(str(v) == "HTTP/1.0", "Parse of 1.0")
        v1 = HTTPVersion.from_str("HTTP/2.4")
        self.assertTrue(v1.major == 2 and v1.minor == 4, "2.4")
        v2 = HTTPVersion.from_str("HTTP/2.13")
        v3 = HTTPVersion.from_str("HTTP/12.3")
        self.assertTrue(v1 < v2, "2.4 < 2.13")
        self.assertTrue(v2 < v3, "2.13 < 12.3")
        self.assertTrue(v1 < v3, "2.4 < 12.3")
        v4 = HTTPVersion.from_str("HTTP/02.004")
        self.assertTrue(v4.major == 2 and v4.minor == 4, "2.4")
        self.assertTrue(v1 == v4, "2.4 == 02.004")

    def test_url(self):
        """URL comparison tests.

        RFC2616:

        When comparing two URIs to decide if they match or not, a client
        SHOULD use a case-sensitive octet-by-octet comparison of the
        entire URIs, with these exceptions:

        -   A port that is empty or not given is equivalent to the
            default port for that URI-reference;

        -   Comparisons of host names MUST be case-insensitive;

        -   Comparisons of scheme names MUST be case-insensitive;

        -   An empty abs_path is equivalent to an abs_path of "/"."""
        v1 = HTTPURL("http://abc.com:80/~smith/home.html")
        v2 = HTTPURL("http://ABC.com/%7Esmith/home.html")
        v3 = HTTPURL("http://ABC.com:/%7esmith/home.html")
        v4 = HTTPURL("http://abc.com/~smith/HOME.html")
        v5 = HTTPURL("http://abc.com:/~smith/home.html")
        v6 = HTTPURL("http://abc.com/~smith/home.html")
        v7 = HTTPURL("http://ABC.com/~smith/home.html")
        v8 = HTTPURL("HTTP://ABC.com/~smith/home.html")
        self.assertFalse(v1.match(v4))
        self.assertTrue(v1.match(v5))
        self.assertTrue(v1.match(v6))
        self.assertTrue(v1.match(v7))
        self.assertTrue(v1.match(v8))
        # explicit examples from the specification...
        self.assertTrue(v1.match(v2))
        self.assertTrue(v1.match(v3))
        self.assertTrue(v2.match(v3))

    def test_full_date(self):
        """date tests from RFC2616:

            HTTP/1.1 clients and servers that parse the date value MUST
            accept all three formats..., though they MUST only generate
            the RFC 1123 format for representing HTTP-date values in
            header fields

            All HTTP date/time stamps MUST be represented in Greenwich
            Mean Time (GMT).  This ...MUST be assumed when reading the
            asctime format.

            HTTP-date is case sensitive and MUST NOT include additional
            LWS beyond that specifically included as SP in the grammar"""
        # RFC 822, updated by RFC 1123
        timestamp_822 = FullDate.from_http_str(
            "Sun, 06 Nov 1994 08:49:37 GMT")
        self.assertTrue(timestamp_822.get_zone()[0] == 0)
        # RFC 850, obsoleted by RFC 1036
        timestamp_850 = FullDate.from_http_str(
            "Sunday, 06-Nov-94 08:49:37 GMT")
        self.assertTrue(timestamp_850.get_zone()[0] == 0)
        # ANSI C's asctime() format
        timestamp_c = FullDate.from_http_str("Sun Nov  6 08:49:37 1994")
        self.assertTrue(timestamp_c.get_zone()[0] == 0)
        self.assertTrue(
            timestamp_822 == timestamp_850, "RFC 850 timestamp parser")
        self.assertTrue(
            timestamp_822 == timestamp_c,
            "ANSI C timestamp parser")
        self.assertTrue(str(timestamp_822) == "Sun, 06 Nov 1994 08:49:37 GMT")
        self.assertTrue(str(timestamp_850) == "Sun, 06 Nov 1994 08:49:37 GMT")
        self.assertTrue(str(timestamp_c) == "Sun, 06 Nov 1994 08:49:37 GMT")
        try:
            # Weekday mismatch
            timestamp_822 = FullDate.from_http_str(
                "Mon, 06 Nov 1994 08:49:37 GMT")
            self.fail("Weekday mismatch passed")
        except grammar.BadSyntax:
            pass
        timestamp_822 = FullDate.from_http_str(
            "Sun, 06 Nov 1994 08:49:37 GMT")
        self.assertTrue(
            str(timestamp_822) == "Sun, 06 Nov 1994 08:49:37 GMT",
            "All-in-one parser")

    def test_utc_date(self):
        """UTC variant of date format

        Seen in the wild::

            Server: Apache-Coyote/1.1
            Date: Sat, 12 Nov 2016 16:22:58 GMT
            Expires: Sat, 19 Nov 2016 16:22:58 UTC
            Last-Modified: Mon, 16 Nov 2015 01:26:00 UTC
        """
        timestamp_822 = FullDate.from_http_str("Sat, 19 Nov 2016 16:22:58 UTC")
        self.assertTrue(timestamp_822.get_zone()[0] == 0)
        self.assertTrue(
            timestamp_822 == iso.TimePoint.from_str("2016-11-19T16:22:58Z"))

    def test_transfer_encoding(self):
        te = TransferEncoding()
        self.assertTrue(te.token == "chunked", "Default not chunked")
        self.assertTrue(
            len(te.parameters) == 0, "Default has extension parameters")
        te = TransferEncoding.from_str("Extension ; x=1 ; y = 2")
        self.assertTrue(te.token == "extension", "Token not case insensitive")
        self.assertTrue(len(te.parameters) == 2, "No of extension parameters")
        self.assertTrue(
            te.parameters == {'x': ('x', b'1'), 'y': ('y', b'2')},
            "Extension parameters: %s" % repr(te.parameters))
        self.assertTrue(str(te) == "extension; x=1; y=2", "te output")
        te = TransferEncoding.from_str("Bob; a=4")
        self.assertTrue(te.token == "bob", "Token not case insensitive")
        self.assertTrue(len(te.parameters) == 1, "No of extension parameters")
        self.assertTrue(
            te.parameters == {'a': ('a', b'4')},
            "Single extension parameters: %s" % repr(te.parameters))
        try:
            te = TransferEncoding.from_str("chunked ; x=1 ; y = 2")
            self.fail("chunked with spurious parameters")
        except grammar.BadSyntax:
            pass
        parameters = {}
        ParameterParser("; x=1 ; y = 2").parse_parameters(parameters)
        te = TransferEncoding("chunked", parameters)
        self.assertTrue(
            len(te.parameters) == 0, "Overparsing of chunked with parameters")
        te = TransferEncoding.from_str("chunkie ; z = 3 ")
        self.assertTrue(te.parameters == {'z': ('z', b'3')},
                        "chunkie parameters")
        telist = TransferEncoding.list_from_str("chunkie; z=3, ,gzip, chunked")
        self.assertTrue(len(telist) == 3)
        self.assertTrue(telist[0] == te, repr([str(i) for i in telist]))
        self.assertTrue(telist[1] == "gzip", repr([str(i) for i in telist]))
        self.assertTrue(telist[2] == "chunked",
                        repr([str(i) for i in telist]))

    def test_chunk(self):
        chunk = Chunk()
        self.assertTrue(chunk.size == 0, "Default chunk size")
        self.assertTrue(len(chunk.extensions) == 0,
                        "Default x-params %s" % repr(chunk.extensions))
        chunk = Chunk.from_str('ABCD; y = "abcd"; x=1')
        self.assertTrue(chunk.size == 0xabcd, "Chunk size")
        self.assertTrue(len(chunk.extensions) == 2,
                        "Default x-params %s" % repr(chunk.extensions))
        self.assertTrue(
            chunk.extensions == {'x': ('x', b'1'), 'y': ('y', b'abcd')})
        self.assertTrue(str(chunk) == "ABCD; x=1; y=abcd", repr(str(chunk)))

    def test_media_type(self):
        """RFC 2616:

            Linear white space (LWS) MUST NOT be used between the type
            and subtype, nor between an attribute and its value"""
        mtype = MediaType()
        try:
            mtype = MediaType.from_str(' application / octet-stream ')
            self.fail("Space between type and sub-type")
        except grammar.BadSyntax:
            pass
        try:
            mtype = MediaType.from_str(' application/octet-stream ')
        except grammar.BadSyntax:
            self.fail("No space between type and sub-type")
        try:
            mtype = MediaType.from_str(
                ' application/octet-stream ; Charset = "en-US"')
            self.fail("Space between param and value")
        except grammar.BadSyntax:
            pass
        try:
            mtype = MediaType.from_str(
                ' application/octet-stream ; Charset="en-US" ; x=1')
        except grammar.BadSyntax:
            self.fail("No space between param and value")
        self.assertTrue(mtype.type == 'application', "Media type")
        self.assertTrue(mtype.subtype == 'octet-stream', "Media sub-type")
        self.assertTrue(mtype['charset'] == b'en-US')
        self.assertTrue(mtype['x'] == b'1')
        try:
            mtype['y']
            self.fail("unparsed parameter in __getitem__")
        except KeyError:
            pass
        self.assertTrue(
            str(mtype) == 'application/octet-stream; Charset=en-US; x=1')

    def test_product_token(self):
        ptoken = ProductToken()
        self.assertTrue(ptoken.token is None)
        self.assertTrue(ptoken.version is None)
        p = ParameterParser('http/2616; x=1')
        ptoken = p.parse_production(p.require_product_token)
        self.assertTrue(p.the_word == byte(";"),
                        "ParseProductToken result: %s" % p.the_word)
        self.assertTrue(ptoken.token == "http", "Product token")
        self.assertTrue(ptoken.version == "2616", "Product token version")
        try:
            ptoken = ProductToken.from_str('http/2616; x=1')
            self.fail("Spurious data test")
        except grammar.BadSyntax:
            pass
        ptokens = ProductToken.list_from_str(
            "CERN-LineMode/2.15 libwww/2.17b3")
        self.assertTrue(len(ptokens) == 2)
        self.assertTrue(ptokens[0].version == "2.15")
        self.assertTrue(ptokens[1].version == "2.17b3")
        self.assertTrue(
            ProductToken.explode("2.17b3") == (
                (2, "~"), (17, "b", 3, "~")), "Complex explode: %s" %
            repr(ProductToken.explode("2.17b3")))
        self.assertTrue(ProductToken.explode("2.b3") ==
                        ((2, "~"), (-1, "b", 3, "~")))
        self.assertTrue(ProductToken.explode(".b3") ==
                        ((), (-1, "b", 3, "~")))
        self.assertTrue(
            ProductToken("Apache", "0.8.4") < ProductToken("Apache", "0.8.30"))
        self.assertTrue(
            ProductToken(
                "Apache",
                "0.8.200") > ProductToken(
                "Apache",
                "0.8.30"))
        self.assertTrue(
            ProductToken(
                "Apache",
                "0.8.4") == ProductToken(
                "Apache",
                "0.8.04"))
        self.assertTrue(
            ProductToken(
                "Apache",
                "0.8.4") > ProductToken(
                "Apache",
                "0.8b1.4"))
        self.assertTrue(
            ProductToken(
                "Apache",
                "1b4.8.4") > ProductToken(
                "Apache",
                "0.8.4"))

    def test_qvalue(self):
        """RFC2616:

            HTTP/1.1 applications MUST NOT generate more than three
            digits after the decimal point"""
        wp = ParameterParser('0.2 1.x x.1 1.001 0.14151')
        self.assertTrue(str(wp.parse_qvalue()) == '0.2', "0.2")
        self.assertTrue(wp.parse_qvalue() is None, "1.x")
        wp.parse_token()
        self.assertTrue(wp.parse_qvalue() is None, "x.1")
        wp.parse_token()
        self.assertTrue(wp.parse_qvalue() == 1.0, "1.001")
        q = wp.parse_qvalue()
        self.assertTrue(str(q) == '0.142', "0.14151: %s" % str(q))

    def test_language_tag(self):
        lang = LanguageTag("EN")
        self.assertTrue(lang.primary == 'EN', "Primary tag")
        self.assertTrue(len(lang.subtags) == 0, "Sub-tags")
        self.assertTrue(str(lang) == "EN")
        lang = LanguageTag("x", "pig", "latin")
        self.assertTrue(lang.primary == 'x', "Primary tag")
        self.assertTrue(len(lang.subtags) == 2, "Sub-tags")
        self.assertTrue(str(lang) == "x-pig-latin")
        try:
            # White space is not allowed within the tag
            lang = LanguageTag.from_str(' en - us ')
            self.fail("Space between primary tag and sub-tags")
        except grammar.BadSyntax:
            pass
        try:
            lang = LanguageTag.from_str(' en-us ')
        except grammar.BadSyntax:
            self.fail("No space between primary tag and sub-tags")
        lang = LanguageTag.from_str('en-US')
        self.assertTrue(lang.primary == 'en', "Primary tag")
        self.assertTrue(
            lang.subtags == ('US',), "Sub-tags: %s" % repr(lang.subtags))
        self.assertTrue(str(lang) == 'en-US')
        # all tags are case-insensitive
        self.assertTrue(lang == "en-US", "Naked string comparison")
        self.assertTrue(
            lang == LanguageTag.from_str('en-us'),
            "case insensitive comparison")
        for langStr in ["en", "en-US", "en-cockney", "i-cherokee",
                        "x-pig-latin"]:
            lang = LanguageTag.from_str(langStr)
        # test for case-insensitive ordering
        self.assertTrue(
            LanguageTag.from_str("en-US") > LanguageTag.from_str("en-gb"),
            "case insensitive order")
        # test for hash
        self.assertTrue(hash(LanguageTag.from_str("en-us")) ==
                        hash(LanguageTag.from_str("en-US")),
                        "case insensitive hash")

    def test_entity_tag(self):
        try:
            etag = EntityTag()
            self.fail("Required tag in constructor")
        except TypeError:
            pass
        etag = EntityTag("hello")
        self.assertTrue(etag.weak, "ETag constructor makes weak tags")
        etag = EntityTag("hello", False)
        self.assertFalse(etag.weak, "ETag constructor with strong tag")
        self.assertTrue(etag.tag, "ETag constructor tag not None")
        etag = EntityTag.from_str('W/"hello"')
        self.assertTrue(etag.weak, "Failed to parse weak tag")
        self.assertTrue(etag.tag == b"hello", "Failed to parse ETag value")
        etag = EntityTag.from_str('w/ "h\\"ello"')
        self.assertTrue(
            etag.weak, "Failed to parse weak tag with lower case 'w'")
        self.assertTrue(
            etag.tag == b'h"ello',
            "Failed to unpick quoted pair from ETag value; found %s" %
            repr(etag.tag))
        etag = EntityTag.from_str('"hello"')
        self.assertFalse(etag.weak, "Failed to parse strong tag")
        self.assertTrue(etag.tag == b"hello", "Failed to parse ETag value")
        etag = EntityTag.from_str(ul('"hello"'))
        self.assertFalse(etag.weak, "Failed to parse strong tag")
        self.assertTrue(etag.tag == b"hello", "Failed to parse ETag value")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
