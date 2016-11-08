#! /usr/bin/env python

import unittest
import logging
import time
import os.path

import pyslet.rfc2396 as uri
import pyslet.iso8601 as iso
import pyslet.http.client as http
import pyslet.http.grammar as grammar
import pyslet.http.params as params
import pyslet.http.messages as messages
import pyslet.http.cookie as cookie

from pyslet.py2 import range3, u8, ul, byte, join_bytes

from test_http_client import MockClientWrapper, MockConnectionWrapper,\
    MockSocket


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(CookieTests, 'test'),
        unittest.makeSuite(DomainTests, 'test'),
        unittest.makeSuite(HeaderTests, 'test'),
        unittest.makeSuite(StoreTests, 'test'),
        unittest.makeSuite(ClientTests, 'test'),
    ))


TEST_STRING = b"The quick fudge brownie jumped over the lazy cookie box"


class MockCookieSocket(MockSocket):

    def send_continue(self):
        self.recv_pipe.write(b"HTTP/1.1 100 Go on then!\r\n"
                             b"Set-Cookie: SID=Status100\r\n\r\n")


class MockCookieConnectionWrapper(MockConnectionWrapper):

    SocketClass = MockCookieSocket


class MockCookieClient(MockClientWrapper):

    ConnectionClass = MockCookieConnectionWrapper


class CookieTests(unittest.TestCase):

    def test_constructor(self):
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        self.assertTrue(c.name == b'SID')
        self.assertTrue(c.value == b'31d4d96e407aad42')
        self.assertTrue(c.path is None)
        self.assertTrue(c.domain is None)
        self.assertFalse(c.secure)
        self.assertFalse(c.http_only)
        self.assertFalse(c.is_persistent())
        self.assertTrue(c.is_hostonly())
        self.assertTrue(c.creation_time is not None)
        self.assertTrue(c.creation_time <= time.time())
        self.assertTrue(c.access_time is not None)
        self.assertTrue(c.access_time == c.creation_time)
        c = cookie.Cookie(b'SID', b'31d4d96e407aad42', path="/",
                          domain="example.com")
        self.assertTrue(c.name == b'SID')
        self.assertTrue(c.value == b'31d4d96e407aad42')
        self.assertTrue(c.path == '/')
        self.assertTrue(c.domain == 'example.com')
        c = cookie.Cookie('SID', '31d4d96e407aad42', path="/", secure=True,
                          http_only=True, max_age=300)
        self.assertTrue(c.name == b'SID')
        self.assertTrue(c.value == b'31d4d96e407aad42')
        self.assertTrue(c.path == '/')
        self.assertTrue(c.domain is None)
        self.assertTrue(c.secure)
        self.assertTrue(c.max_age == 300)
        self.assertTrue(c.is_persistent())
        self.assertTrue(c.http_only)

    def test_touch(self):
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        t0 = time.time() - 300
        c.creation_time = t0
        c.access_time = c.creation_time
        c.touch()
        self.assertTrue(c.creation_time == t0)
        self.assertTrue(c.access_time > t0)
        self.assertTrue(c.access_time <= time.time())

    def test_attributes(self):
        """Attribute tests:

        To maximize compatibility with user agents, servers SHOULD NOT
        produce two attributes with the same name in the same
        set-cookie-string"""
        try:
            cookie.Section4Cookie(
                'SID', '31d4d96e407aad42',
                extensions=["lang=en-US", "fortesting=True", "lang=en-GB"])
            self.fail("Two extensions, same attribute name")
        except cookie.CookieError:
            pass
        try:
            cookie.Section4Cookie(
                'SID', '31d4d96e407aad42', path="/",
                extensions=["path=/en-US", "fortesting=True"])
            self.fail("Extensions and attribute clash")
        except cookie.CookieError:
            pass

    def test_expires(self):
        """The Expires attribute indicates the maximum lifetime of the
        cookie, represented as the date and time at which the cookie
        expires."""
        c = cookie.Cookie(
            'SID', '31d4d96e407aad42',
            expires=iso.TimePoint.from_str('2014-11-14T20:32:39Z'))
        self.assertTrue(c.expired())
        self.assertTrue(c.is_persistent())
        # check against an explicit time
        expire_time = iso.TimePoint.from_str(
            '2014-11-14T20:32:38Z').get_unixtime()
        self.assertFalse(c.expired(expire_time))
        c = cookie.Cookie(
            'SID', '31d4d96e407aad42',
            expires=params.FullDate.from_unix_time(time.time()+300))
        self.assertFalse(c.expired())
        # If the attribute-value failed to parse as a cookie date,
        # ignore the cookie-av.
        p = cookie.CookieParser(
            "SID=31d4d96e407aad42; expires=20 July 1600 20:17:40")
        c = p.require_set_cookie_string()
        self.assertTrue(c.expires is None)
        p = cookie.CookieParser(
            "SID=31d4d96e407aad42; expires=20 July 1969 20:17:40")
        c = p.require_set_cookie_string()
        self.assertTrue(c.expires ==
                        iso.TimePoint.from_str('19690720T201740Z'))

    def test_max_age(self):
        """The Max-Age attribute indicates the maximum lifetime of the
        cookie, represented as the number of seconds until the cookie
        expires.

        If a cookie has both the Max-Age and the Expires attribute, the
        Max- Age attribute has precedence

        If a cookie has neither the Max-Age nor the Expires attribute,
        the user agent will retain the cookie until "the current session
        is over"""
        c = cookie.Cookie('SID', '31d4d96e407aad42', max_age=60)
        self.assertFalse(c.expired())
        expire_time = time.time()+300
        self.assertTrue(c.expired(expire_time))
        # check the string representation
        self.assertTrue(str(c) == "SID=31d4d96e407aad42; Max-Age=60")
        c = cookie.Cookie(
            'SID', '31d4d96e407aad42', max_age=60,
            expires=iso.TimePoint.from_str('2014-11-14T20:32:39Z'))
        self.assertFalse(c.expired())
        self.assertTrue(c.expired(expire_time))
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        self.assertFalse(c.expired())
        expire_time = iso.TimePoint.from_str(
            '3014-11-14T20:32:39Z').get_unixtime()
        self.assertFalse(c.expired(expire_time))
        # If the first character of the attribute-value is not a DIGIT
        # or a "-" character, ignore the cookie-av.
        p = cookie.CookieParser("SID=31d4d96e407aad42; max-age=+10")
        c = p.require_set_cookie_string()
        self.assertTrue(c.max_age is None)
        # If the remainder of attribute-value contains a non-DIGIT
        # character, ignore the cookie-av.
        p = cookie.CookieParser("SID=31d4d96e407aad42; max-age=10s")
        c = p.require_set_cookie_string()
        self.assertTrue(c.max_age is None)
        p = cookie.CookieParser("SID=31d4d96e407aad42; max-age=-10")
        c = p.require_set_cookie_string()
        self.assertTrue(c.max_age == -10, repr(c.max_age))
        # multiple values, last is used
        p = cookie.CookieParser(
            "SID=31d4d96e407aad42; max-age=5; httpOnly; max-age=6")
        c = p.require_set_cookie_string()
        self.assertTrue(c.max_age == 6)

    def test_domain(self):
        # If the attribute-value is empty, the behavior is undefined.
        # However, the user agent SHOULD ignore the cookie-av entirely.
        p = cookie.CookieParser("SID=31d4d96e407aad42; domain=")
        c = p.require_set_cookie_string()
        self.assertTrue(c.domain is None)
        # If the first character of the attribute-value string is %x2E
        # ("."): Let cookie-domain be the attribute-value without the
        # leading %x2E (".") character.
        p = cookie.CookieParser("SID=31d4d96e407aad42; domain=.Example.COM")
        c = p.require_set_cookie_string()
        self.assertTrue(c.domain == "example.com", repr(c.domain))
        # check last domain used
        p = cookie.CookieParser(
            "SID=31d4d96e407aad42; domain=.Example.COM; max-age=300; "
            "domain=example.CO.UK")
        c = p.require_set_cookie_string()
        self.assertTrue(c.domain == "example.co.uk")

    def test_path(self):
        # If the attribute-value is empty or if the first character of
        # the attribute-value is not %x2F ("/"): Let cookie-path be the
        # default-path.
        p = cookie.CookieParser("SID=31d4d96e407aad42; path=")
        c = p.require_set_cookie_string()
        self.assertTrue(c.path is None)
        p = cookie.CookieParser("SID=31d4d96e407aad42; path=dir/file")
        c = p.require_set_cookie_string()
        self.assertTrue(c.path is None)
        p = cookie.CookieParser("SID=31d4d96e407aad42; path=/dir/file")
        c = p.require_set_cookie_string()
        self.assertTrue(c.path == "/dir/file")
        # check last value
        p = cookie.CookieParser(
            "SID=31d4d96e407aad42; path=/dir/file; max-age=300; path=/")
        c = p.require_set_cookie_string()
        self.assertTrue(c.path == "/")

    def test_parser1_strict(self):
        p = cookie.CookieParser("")
        self.assertTrue(isinstance(p, grammar.OctetParser))
        p = cookie.CookieParser('a b"c,d;e\\fg\t"hi"j')
        result = []
        while p.the_char is not None:
            result.append(p.require_cookie_value())
            p.next_char()
        self.assertTrue(result == [b'a', b'b', b'c', b'd', b'e', b'fg',
                                   b'"hi"'], repr(result))
        p = cookie.CookieParser('SID=31d4d96e407aad42')
        name, value = p.parse_cookie_pair()
        self.assertTrue(name == b"SID")
        self.assertTrue(value == b"31d4d96e407aad42")
        # check preservation of quote
        p = cookie.CookieParser('SID="31d4d96e407aad42"')
        name, value = p.parse_cookie_pair()
        self.assertTrue(name == b"SID")
        self.assertTrue(value == b"\"31d4d96e407aad42\"")
        p = cookie.CookieParser('a \tb;c\'d,e"\\"')
        result = []
        while p.the_char is not None:
            result.append(p.parse_cookie_av())
            p.next_char()
        self.assertTrue(result == [b'a ', b'b', b'c\'d,e"\\"'])
        # simple example
        p = cookie.CookieParser('SID=31d4d96e407aad42')
        c = p.require_set_cookie_string(strict=True)
        self.assertTrue(isinstance(c, cookie.Cookie))
        self.assertTrue(c.name == b"SID")
        self.assertTrue(c.value == b"31d4d96e407aad42")
        self.assertTrue(c.expires is None)
        self.assertTrue(c.max_age is None)
        self.assertTrue(c.domain is None)
        self.assertTrue(c.path is None)
        self.assertTrue(c.secure is False)
        self.assertTrue(c.http_only is False)
        # full example, include double space for generous parsing
        p = cookie.CookieParser(
            'SID="31d4d96e407aad42"; httponly; secure; path=/; '
            'domain=example.com; max-age=1000; '
            'expires=Fri, 14 Nov 2014 20:32:39 GMT; lang=en-US; trailer')
        c = p.require_set_cookie_string(strict=True)
        self.assertTrue(c.name == b"SID")
        self.assertTrue(c.value == b'"31d4d96e407aad42"')
        self.assertTrue(c.expires ==
                        iso.TimePoint.from_str('2014-11-14T20:32:39Z'))
        self.assertTrue(c.max_age == 1000)
        self.assertTrue(c.domain == 'example.com')
        self.assertTrue(c.path == '/', repr(c.path))
        self.assertTrue(c.secure is True)
        self.assertTrue(c.http_only is True)
        self.assertTrue(c.extensions == [b'lang=en-US', b'trailer'])

    def test_parser1(self):
        p = cookie.CookieParser(' SID = 31d4d96e407aad42 ')
        c = p.require_set_cookie_string()
        self.assertTrue(isinstance(c, cookie.Cookie))
        # Remove any leading or trailing WSP characters from the name
        # string and the value string.
        self.assertTrue(c.name == b"SID")
        self.assertTrue(c.value == b"31d4d96e407aad42")
        p = cookie.CookieParser('SID = "31d4d96e407aad42')
        try:
            c = p.require_set_cookie_string(strict=True)
            self.fail("padded '='")
        except ValueError:
            pass
        p = cookie.CookieParser('SID=3,4 ;x=1')
        c = p.require_set_cookie_string()
        self.assertTrue(isinstance(c, cookie.Cookie))
        self.assertTrue(c.name == b"SID")
        self.assertTrue(c.value == b"3,4")
        # If the name-value-pair string lacks a %x3D ("=") character,
        # ignore the set-cookie-string entirely.
        p = cookie.CookieParser('SID34;x=1')
        c = p.require_set_cookie_string()
        self.assertTrue(c is None)
        self.assertTrue(p.the_char is None)
        # If the name string is empty, ignore the set-cookie-string
        # entirely.
        p = cookie.CookieParser('= 34 ;x=1')
        c = p.require_set_cookie_string()
        self.assertTrue(c is None)
        self.assertTrue(p.the_char is None)
        p = cookie.CookieParser(
            'SID=34 ;x=1;path;=1;httponly;secure;; domain = com ;')
        c = p.require_set_cookie_string()
        self.assertTrue(isinstance(c, cookie.Cookie))
        self.assertTrue(c.secure is True)
        self.assertTrue(c.http_only is True)
        self.assertTrue(c.domain == "com")
        # default the path
        self.assertTrue(c.path is None)
        self.assertTrue(p.the_char is None)

    def test_parser2(self):
        p = cookie.CookieParser('\r\n SID=31d4d96e407aad42; lang="en-US"\r\n ')
        clist = p.require_cookie_string()
        # results in a dictionary of cookies
        self.assertTrue(len(clist) == 2)
        self.assertTrue(b'SID' in clist)
        self.assertTrue(clist[b'SID'] == b'31d4d96e407aad42')
        self.assertTrue(b'lang' in clist)
        self.assertTrue(clist[b'lang'] == b'"en-US"')
        # check the parser consumed the last OWS
        self.assertTrue(p.the_char is None)
        p = cookie.CookieParser('SID=31d4d96e407aad42;  lang="en-US"')
        # 2 spaces not allowed, harsh but true
        clist = p.require_cookie_string(strict=True)
        self.assertTrue(len(clist) == 1)
        p = cookie.CookieParser('SID=31d4d96e407aad42;\r\n lang="en-US"')
        # fold not allowed
        clist = p.require_cookie_string(strict=True)
        self.assertTrue(len(clist) == 1)
        # multi-set match case
        p = cookie.CookieParser('lang=en-GB; SID=31d4d96e407aad42; lang=en-US')
        clist = p.require_cookie_string()
        self.assertTrue(len(clist) == 2)
        self.assertTrue(b'SID' in clist)
        self.assertTrue(b'lang' in clist)
        # we insist that multiple values are returned as sets to ensure
        # that servers cannot rely upon the serialization order
        self.assertTrue(isinstance(clist[b'lang'], set))
        self.assertTrue(len(clist[b'lang']) == 2)
        self.assertTrue(b'en-GB' in clist[b'lang'])
        self.assertTrue(b'en-US' in clist[b'lang'])

    def test_syntax(self):
        for i in range3(0, 0x21):
            self.assertFalse(cookie.is_cookie_octet(byte(i)))
        self.assertTrue(cookie.is_cookie_octet(byte(0x21)))
        self.assertFalse(cookie.is_cookie_octet(byte(0x22)))
        for i in range3(0x23, 0x2C):
            self.assertTrue(cookie.is_cookie_octet(byte(i)))
        self.assertFalse(cookie.is_cookie_octet(byte(0x2C)))
        for i in range3(0x2D, 0x3B):
            self.assertTrue(cookie.is_cookie_octet(byte(i)))
        self.assertFalse(cookie.is_cookie_octet(byte(0x3B)))
        for i in range3(0x3C, 0x5C):
            self.assertTrue(cookie.is_cookie_octet(byte(i)))
        self.assertFalse(cookie.is_cookie_octet(byte(0x5C)))
        for i in range3(0x5D, 0x7F):
            self.assertTrue(cookie.is_cookie_octet(byte(i)))
        for i in range3(0x7F, 0x100):
            self.assertFalse(cookie.is_cookie_octet(byte(i)))

    def test_date_tokens(self):
        for i in range3(0, 0x09):
            self.assertFalse(cookie.is_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        self.assertTrue(cookie.is_delimiter(byte(0x09)))
        self.assertFalse(cookie.is_non_delimiter(byte(0x09)))
        self.assertTrue(cookie.is_non_digit(byte(0x09)))
        for i in range3(0x0A, 0x20):
            self.assertFalse(cookie.is_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x20, 0x30):
            self.assertTrue(cookie.is_delimiter(byte(i)))
            self.assertFalse(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x30, 0x3A):
            self.assertFalse(cookie.is_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_delimiter(byte(i)))
            self.assertFalse(cookie.is_non_digit(byte(i)))
        self.assertFalse(cookie.is_delimiter(byte(0x3A)))
        self.assertTrue(cookie.is_non_delimiter(byte(0x3A)))
        self.assertTrue(cookie.is_non_digit(byte(0x3A)))
        for i in range3(0x3B, 0x41):
            self.assertTrue(cookie.is_delimiter(byte(i)))
            self.assertFalse(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x41, 0x5B):
            self.assertFalse(cookie.is_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x5B, 0x61):
            self.assertTrue(cookie.is_delimiter(byte(i)))
            self.assertFalse(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x61, 0x7B):
            self.assertFalse(cookie.is_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x7B, 0x7F):
            self.assertTrue(cookie.is_delimiter(byte(i)))
            self.assertFalse(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        for i in range3(0x7F, 0x100):
            self.assertFalse(cookie.is_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_delimiter(byte(i)))
            self.assertTrue(cookie.is_non_digit(byte(i)))
        src = []
        for i in range3(0, 0x100):
            src.append(byte(i))
        p = cookie.CookieParser(join_bytes(src))
        tokens = p.parse_cookie_date_tokens()
        self.assertTrue(tokens == [
            b"\x00\x01\x02\x03\x04\x05\x06\x07\x08",
            b"\x0A\x0B\x0C\x0D\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18"
            b"\x19\x1A\x1B\x1C\x1D\x1E\x1F",
            b"0123456789:",
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            b"abcdefghijklmnopqrstuvwxyz",
            b"\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d"
            b"\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c"
            b"\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab"
            b"\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba"
            b"\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9"
            b"\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8"
            b"\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7"
            b"\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6"
            b"\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff"], repr(tokens))

    def test_time(self):
        h, m, s = cookie.split_time(b"0:0:0pm\r\n")
        self.assertTrue(h == 0)
        self.assertTrue(m == 0)
        self.assertTrue(s == 0)
        h, m, s = cookie.split_time(b"99:9:09pm\r\n")
        self.assertTrue(h == 99)
        self.assertTrue(m == 9)
        self.assertTrue(s == 9)
        # too many digits, raises an error
        try:
            h, m, s = cookie.split_time(b"12:34:005pm\r\n")
            self.fail("3DIGIT fails to match time-field")
        except ValueError:
            pass
        # no seconds raises an error
        try:
            h, m, s = cookie.split_time(b"12:34pm\r\n")
            self.fail("Missing seconds fails to match time-field")
        except ValueError:
            pass

    def test_year(self):
        y = cookie.split_year(b"94AD\r\n")
        self.assertTrue(y == 1994)
        y = cookie.split_year(b"1994AD\r\n")
        self.assertTrue(y == 1994)
        y = cookie.split_year(b"054ad\r\n")
        self.assertTrue(y == 2054)
        try:
            y = cookie.split_year(b"5ad\r\n")
            self.fail("DIGIT fails to match year")
        except ValueError:
            pass
        try:
            y = cookie.split_year(b"10005ad\r\n")
            self.fail("5DIGIT fails to match year")
        except ValueError:
            pass

    def test_dom(self):
        d = cookie.split_day_of_month(b"1st\r\n")
        self.assertTrue(d == 1)
        d = cookie.split_day_of_month(b"55th\r\n")
        self.assertTrue(d == 55)
        d = cookie.split_day_of_month(b"00th\r\n")
        self.assertTrue(d == 0)
        try:
            d = cookie.split_day_of_month(b"101st\r\n")
            self.fail("3DIGIT fails to match day of month")
        except ValueError:
            pass

    def test_month(self):
        m = cookie.split_month(b"january")
        self.assertTrue(m == 1)
        m = cookie.split_month(b"febuary\r\n")
        self.assertTrue(m == 2)
        m = cookie.split_month(b"february")
        self.assertTrue(m == 2)
        m = cookie.split_month(b"mar")
        self.assertTrue(m == 3)
        m = cookie.split_month(b"Mars")
        self.assertTrue(m == 3)
        m = cookie.split_month(b"Apricot\r\n")
        self.assertTrue(m == 4)
        m = cookie.split_month(b"MAY")
        self.assertTrue(m == 5)
        m = cookie.split_month(b"June")
        self.assertTrue(m == 6)
        m = cookie.split_month(b"Juliet")
        self.assertTrue(m == 7)
        m = cookie.split_month(b"Augustus")
        self.assertTrue(m == 8)
        m = cookie.split_month(b"sep7\r\n")
        self.assertTrue(m == 9)
        m = cookie.split_month(b"octopus")
        self.assertTrue(m == 10)
        m = cookie.split_month(b"NOV5th\r\n")
        self.assertTrue(m == 11)
        m = cookie.split_month(b"Decimal")
        self.assertTrue(m == 12)
        try:
            m = cookie.split_month(b"Avril")
            self.fail("unrecognized month")
        except ValueError:
            pass
        try:
            m = cookie.split_month(b"12")
            self.fail("unrecognized month")
        except ValueError:
            pass

    def test_cookie_date(self):
        """date tests

        2069-07-20T20:17:40Z"""
        t = params.FullDate.from_str("1969-07-20T20:17:40Z")
        t2000 = params.FullDate.from_str("2069-07-20T20:17:40Z")
        p = cookie.CookieParser("20:17:40 20th July 69")
        self.assertTrue(p.require_cookie_date() == t2000)
        p = cookie.CookieParser("20th July 69 20:17:40")
        self.assertTrue(p.require_cookie_date() == t2000)
        # day of month trumps year
        p = cookie.CookieParser("20th 69 20:17:40pm July")
        self.assertTrue(p.require_cookie_date() == t2000)
        # the format does not work for ISO dates, but nearly
        p = cookie.CookieParser("1969-July-20 20:17:40Z")
        self.assertTrue(p.require_cookie_date() == t)
        # all of these should fail, and so return None
        for src in [
                "20th July 1969",
                "20th 1969 20:17:40",
                "July 1969 20:17:40",
                "20th July 20:17:40",
                "32 July 1969 20:17:40",
                "0 July 1969 20:17:40",
                "20 July 1600 20:17:40",
                "20 July 1969 24:17:40",
                "20 July 1969 20:60:40",
                "20 July 1969 20:17:60",
                "31 Nov 1969 20:17:40"]:
            p = cookie.CookieParser(src)
            self.assertTrue(p.require_cookie_date() is None)
            # always consumes the whole string
            self.assertTrue(p.the_char is None)


class DomainTests(unittest.TestCase):

    def test_ldh_label(self):
        """LDH rules:

        <label> ::= <letter> [ [ <ldh-str> ] <let-dig> ]
        <ldh-str> ::= <let-dig-hyp> | <let-dig-hyp> <ldh-str>"""
        self.assertTrue(cookie.is_ldh_label(b"ab-2"))
        self.assertTrue(cookie.is_ldh_label(b"ab--cde"))
        # can be 63 chars long
        self.assertTrue(cookie.is_ldh_label(
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"
            b"abcdefghijklmnopqrstuvwxyz"))
        # can't be 64 chars long
        self.assertFalse(cookie.is_ldh_label(
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ--0123456789"
            b"abcdefghijklmnopqrstuvwxyz"))
        # labels can now start with a number!
        self.assertTrue(cookie.is_ldh_label(b"131"))
        # or be a number
        self.assertTrue(cookie.is_ldh_label(b"4ab"))
        # can't start with a or a hyphen
        self.assertFalse(cookie.is_ldh_label(b"-ab"))
        # or end with a hypen
        self.assertFalse(cookie.is_ldh_label(b"cde-"))
        # the label cannot contain a ','
        self.assertFalse(cookie.is_ldh_label(b"cd.ef"))
        # the label cannot contain or '_'
        self.assertFalse(cookie.is_ldh_label(b"cd_ef"))
        # empty strings are not valid labels
        self.assertFalse(cookie.is_ldh_label(b""))

    def test_rldh_label(self):
        """R-LDH rules:

        Reserved LDH labels... have the property that they contain "--"
        in the third and fourth characters"""
        self.assertTrue(cookie.is_rldh_label(b"ab--cde"))
        self.assertFalse(cookie.is_rldh_label(b"abc--de"))
        self.assertFalse(cookie.is_rldh_label(b"a--bcde"))

    def test_a_label(self):
        """A-label rule: xn--"""
        self.assertTrue(cookie.is_a_label(b"xn--ab"))
        self.assertTrue(cookie.is_a_label(b"XN--ab"))
        self.assertTrue(cookie.is_a_label(b"Xn--ab"))
        self.assertFalse(cookie.is_a_label(b"ab--xn--ab"))
        self.assertTrue(cookie.is_a_label(b'xn--fiqs8s'))

    def test_split_domain(self):
        """Splits a domain into appropriate labels"""
        # check unicode support
        self.assertTrue(
            cookie.split_domain(u8(b'\xe5\x85\xac\xe5\x8f\xb8.cn')) ==
            ['xn--55qx5d', 'cn'])
        self.assertTrue(
            cookie.split_domain(u8(b'\xe5\x85\xac\xe5\x8f\xb8.CN')) ==
            ['xn--55qx5d', 'cn'])
        # assume strings are utf-8 encoded
        self.assertTrue(
            cookie.split_domain(b'\xe5\x85\xac\xe5\x8f\xb8.CN') ==
            ['xn--55qx5d', 'cn'])
        # but encode labels can pass through both forms...
        self.assertTrue(
            cookie.split_domain(ul('xn--55qx5d.CN')) ==
            ['xn--55qx5d', 'cn'])
        self.assertTrue(
            cookie.split_domain(b'xn--55qx5d.CN') ==
            ['xn--55qx5d', 'cn'])
        try:
            cookie.split_domain('*.xn--55qx5d.CN')
            self.fail("* in domain")
        except ValueError:
            pass
        self.assertTrue(
            cookie.split_domain('*.xn--55qx5d.CN', allow_wildcard=True) ==
            ['*', 'xn--55qx5d', 'cn'])
        self.assertTrue(
            cookie.split_domain('*.*.CN', allow_wildcard=True) ==
            ['*', '*', 'cn'])
        self.assertTrue(
            cookie.split_domain('xn--55qx5d.*.CN', allow_wildcard=True) ==
            ['xn--55qx5d', '*', 'cn'])
        self.assertTrue(
            cookie.split_domain('*', allow_wildcard=True) == ['*'])


class HeaderTests(unittest.TestCase):

    def test_request(self):
        request = messages.Request()
        request.set_cookie([cookie.Cookie('SID', '31d4d96e407aad42')])
        cookies = request.get_cookie()
        # should be a dictionary containing a single cookie
        self.assertTrue(isinstance(cookies, dict))
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(b"SID" in cookies)
        self.assertTrue(cookies[b"SID"] == b'31d4d96e407aad42')
        cookies = request.get_header('Cookie')
        self.assertTrue(cookies == b'SID=31d4d96e407aad42')
        # set_cookie replaces value
        request.set_cookie([cookie.Cookie('lang', 'en-US')])
        cookies = request.get_cookie()
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(b"lang" in cookies)
        # None removes value
        request.set_cookie(None)
        cookies = request.get_cookie()
        self.assertTrue(len(cookies) == 0)
        cookies = request.get_header('Cookie')
        self.assertTrue(cookies is None)
        # multiple values
        request.set_cookie([cookie.Cookie('SID', '31d4d96e407aad42'),
                            cookie.Cookie('lang', 'en-US')])
        cookies = request.get_cookie()
        self.assertTrue(len(cookies) == 2)
        self.assertTrue(b"lang" in cookies)
        self.assertTrue(b"SID" in cookies)
        cookies = request.get_header('Cookie')
        self.assertTrue(cookies == b'SID=31d4d96e407aad42; lang=en-US')

    def test_response_folding(self):
        """Folding test:

        Origin servers SHOULD NOT fold multiple Set-Cookie header fields
        into a single header field.

        Servers SHOULD NOT include more than one Set-Cookie header field
        in the same response with the same cookie-name -- we don't
        police this second constraint as we wish to be generous when
        parsing responses."""
        request = messages.Request()
        response = messages.Response(request)
        # you can't set more than one cookie in a single header...
        response.set_set_cookie(cookie.Cookie('c1', 'value1'))
        # but if you call it again it should add a second header
        response.set_set_cookie(cookie.Cookie('c2', 'value2'))
        cookies = response.get_header('Set-Cookie', list_mode=True)
        self.assertTrue(isinstance(cookies, list))
        self.assertTrue(len(cookies) == 2)
        # can replace all existing cookies
        response.set_set_cookie(cookie.Cookie('c4', 'value4'), replace=True)
        cookies = response.get_header('Set-Cookie', list_mode=True)
        self.assertTrue(len(cookies) == 1)
        # None removes all values (implicit replace) for compatibility
        response.set_set_cookie(None)
        cookies = response.get_header('Set-Cookie')
        self.assertTrue(cookies is None)


class StoreTests(unittest.TestCase):

    def test_constructor(self):
        cookie.CookieStore()

    def test_public_list(self):
        cs = cookie.CookieStore()
        # by default we are set to an empty black_list but treat
        # unmatched domains as being public, rather than matching the
        # TLD only as described by publicsuffix.org
        self.assertTrue(cs.test_public_domain('com'))
        self.assertTrue(cs.test_public_domain('example.com'))
        self.assertTrue(cs.test_public_domain('www.example.com'))
        # now we add a black list
        black_list = """// black listed domains
com

*.jp
// Hosts in .hokkaido.jp can't set cookies below level 4...
*.hokkaido.jp
*.tokyo.jp
// ...except hosts in pref.hokkaido.jp, which can set cookies at level 3.
!pref.hokkaido.jp
!metro.tokyo.jp"""
        cs.set_public_list(black_list)
        # Cookies may be set for foo.com.
        self.assertFalse(cs.test_public_domain('foo.com'))
        # Cookies may be set for foo.bar.jp.
        self.assertFalse(cs.test_public_domain('foo.bar.jp'))
        # Cookies may not be set for bar.jp.
        self.assertTrue(cs.test_public_domain('bar.jp'))
        # Cookies may be set for foo.bar.hokkaido.jp.
        self.assertFalse(cs.test_public_domain('foo.bar.hokkaido.jp'))
        # Cookies may not be set for bar.hokkaido.jp.
        self.assertTrue(cs.test_public_domain('bar.hokkaido.jp'))
        # Cookies may be set for foo.bar.tokyo.jp.
        self.assertFalse(cs.test_public_domain('foo.bar.tokyo.jp'))
        # Cookies may not be set for bar.tokyo.jp.
        self.assertTrue(cs.test_public_domain('bar.tokyo.jp'))
        # Cookies may be set for pref.hokkaido.jp because the exception
        # overrides the previous rule.
        self.assertFalse(cs.test_public_domain('pref.hokkaido.jp'))
        # Cookies may be set for metro.tokyo.jp, because the exception
        # overrides the previous rule.
        self.assertFalse(cs.test_public_domain('metro.tokyo.jp'))
        # check an unmatched domain, default tld depth = 1
        # Cookies may not be set for uk, implicit '*' rule
        self.assertTrue(cs.test_public_domain('uk'))
        # Cookies may be set for co.uk
        self.assertFalse(cs.test_public_domain('co.uk'))
        # now increase the depth to 2
        cs.set_public_list(black_list, tld_depth=2)
        self.assertTrue(cs.test_public_domain('uk'))
        # Cookies may not be set for co.uk, implicit *.* rule
        self.assertTrue(cs.test_public_domain('co.uk'))
        # Cookies may be set for www.co.uk
        self.assertFalse(cs.test_public_domain('www.co.uk'))
        self.assertFalse(cs.test_public_domain('alt.www.co.uk'))
        # use a large value to effectively ban everything
        # except defined exceptions!
        cs.set_public_list(black_list, tld_depth=100)
        self.assertTrue(cs.test_public_domain('ww1.ww2.ww3.ww4.ww5.co.uk'))

    def test_domain(self):
        """if the value of the Domain attribute is "example.com", the
        user agent will include the cookie in the Cookie header when
        making HTTP requests to example.com, www.example.com, and
        www.corp.example.com

        ...a leading %x2E ("."), if present, is ignored... but a
        trailing %x2E ("."), if present, will cause the user agent to
        ignore the attribute.

        If the server omits the Domain attribute, the user agent will
        return the cookie only to the origin server

        The user agent will reject cookies unless the Domain attribute
        specifies a scope for the cookie that would include the origin
        server"""
        cs = cookie.CookieStore()
        cs.set_public_list(ul("""// public suffix list
// accept domain cookies within the following...
!example.com
!example2.com
!example3.com
!example4.com"""), tld_depth=100)
        c = cookie.Cookie('SID', '31d4d96e407aad42', domain='example.com')
        cs.set_cookie(uri.URI.from_octets('http://test.example.com/'), c)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://test.example.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.example.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.test.example.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example2.com/'))) == 0)
        c = cookie.Cookie('SID', '31d4d96e407aad42', domain='.example2.com')
        cs.set_cookie(uri.URI.from_octets('http://test.example2.com/'), c)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example2.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://test.example2.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.example2.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.test.example2.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example3.com/'))) == 0)
        c = cookie.Cookie('SID', '31d4d96e407aad42', domain='example3.com.')
        cs.set_cookie(uri.URI.from_octets('http://test.example3.com/'), c)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example3.com/'))) == 0)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://test.example3.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.example3.com/'))) == 0)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.test.example3.com/'))) == 0)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example4.com/'))) == 0)
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        cs.set_cookie(uri.URI.from_octets('http://test.example4.com/'), c)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example4.com/'))) == 0)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://test.example4.com/'))) == 1)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.example4.com/'))) == 0)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://www.test.example4.com/'))) == 0)
        self.assertTrue(len(cs.search(
            uri.URI.from_octets('http://example5.com/'))) == 0)
        c = cookie.Cookie('SID', '31d4d96e407aad42', domain="bar.example.com")
        try:
            cs.set_cookie(uri.URI.from_octets('http://foo.example.com/'), c)
            self.fail("Domain cookie: bar.example.com")
        except cookie.CookieError:
            pass
        c = cookie.Cookie('SID', '31d4d96e407aad42',
                          domain="baz.foo.example.com")
        try:
            cs.set_cookie(uri.URI.from_octets('http://foo.example.com/'), c)
            self.fail("Domain cookie: baz.foo.example.com")
        except cookie.CookieError:
            pass

    def test_path(self):
        """Path tests...

        If the server omits the Path attribute, the user agent will
        use the "directory" of the request-uri's path component as the
        default value.

        The user agent will include the cookie in an HTTP request only
        if the path portion of the request-uri matches (or is a
        subdirectory of) the cookie's Path attribute

        If the user agent receives a new cookie with the same
        cookie-name, domain-value, and path-value as a cookie that it
        has already stored, the existing cookie is evicted and replaced
        with the new cookie."""
        cs = cookie.CookieStore()
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        self.assertTrue(c.path is None)
        # no path
        cs.set_cookie(
            uri.URI.from_octets('http://test.example.com/images/logo.gif'), c)
        # c will have been stored with the path '/images/'
        clist = cs.search(uri.URI.from_octets('http://test.example.com/'))
        self.assertTrue(len(clist) == 0)
        clist = cs.search(
            uri.URI.from_octets('http://test.example.com/images/logo.gif'))
        self.assertTrue(len(clist) == 1)
        clist = cs.search(
            uri.URI.from_octets('http://test.example.com/images/banner.gif'))
        self.assertTrue(len(clist) == 1)
        clist = cs.search(
            uri.URI.from_octets('http://test.example.com/images/css/box.gif'))
        self.assertTrue(len(clist) == 1)
        # this cookie should evict the previous one...
        c = cookie.Cookie('SID', 'new_value', path="/images")
        cs.set_cookie(
            uri.URI.from_octets('http://test.example.com/home.htm'), c)
        clist = cs.search(
            uri.URI.from_octets('http://test.example.com/images/logo.gif'))
        self.assertTrue(len(clist) == 1)
        self.assertTrue(clist[0].value == b'new_value')
        clist = cs.search(
            uri.URI.from_octets('http://test.example.com/home.htm'))
        # doesn't match the path
        self.assertTrue(len(clist) == 0)

    def test_secure(self):
        """secure test:

        When a cookie has the Secure attribute, the user agent will
        include the cookie in an HTTP request only if the request is
        transmitted over a secure channel"""
        cs = cookie.CookieStore()
        url = uri.URI.from_octets('http://test.example.com/')
        surl = uri.URI.from_octets('https://test.example.com/')
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        self.assertTrue(c.secure is False)
        # insecure cookie
        cs.set_cookie(url, c)
        self.assertTrue(len(cs.search(url)) == 1)
        self.assertTrue(len(cs.search(surl)) == 1)
        c2 = cookie.Cookie('SSID', '31d4d96e407aad42', secure=True)
        self.assertTrue(c2.secure is True)
        # secure cookie, set by secure URL
        cs.set_cookie(surl, c2)
        self.assertTrue(len(cs.search(url)) == 1)
        self.assertTrue(len(cs.search(surl)) == 2)
        c3 = cookie.Cookie('SishSID', '31d4d96e407aad42', secure=True)
        self.assertTrue(c3.secure is True)
        # secure cookie, set by insecure URL
        cs.set_cookie(url, c3)
        self.assertTrue(len(cs.search(url)) == 1)
        self.assertTrue(len(cs.search(surl)) == 3)

    def test_http(self):
        """http_only test:

        the attribute instructs the user agent to omit the cookie when
        providing access to cookies via "non-HTTP" APIs"""
        cs = cookie.CookieStore()
        url = uri.URI.from_octets('http://test.example.com/')
        furl = uri.URI.from_octets('file://test.example.com/')
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        # implicit default is any protocol
        self.assertTrue(c.http_only is False)
        # general cookie, set by http
        cs.set_cookie(url, c)
        self.assertTrue(len(cs.search(url)) == 1)
        self.assertTrue(len(cs.search(furl)) == 1)
        c2 = cookie.Cookie('HSID', '31d4d96e407aad42', http_only=True)
        self.assertTrue(c2.http_only is True)
        # http_only cookie, set by http
        cs.set_cookie(url, c2)
        self.assertTrue(len(cs.search(url)) == 2)
        self.assertTrue(len(cs.search(furl)) == 1)
        c3 = cookie.Cookie('HishSID', '31d4d96e407aad42', http_only=True)
        # http_only cookie, set by a different protocol should be ignored
        try:
            cs.set_cookie(furl, c3)
            self.fail("Set http_only cookie with file: URL")
        except cookie.CookieError:
            pass
        self.assertTrue(len(cs.search(url)) == 2)
        self.assertTrue(len(cs.search(furl)) == 1)

    def test_session_cookie(self):
        """session cookie

        Unless the cookie's attributes indicate otherwise, the cookie...
        expires at the end of the current session (as defined by the
        user agent)"""
        cs = cookie.CookieStore()
        url = uri.URI.from_octets('http://test.example.com/')
        c = cookie.Cookie('SID', '31d4d96e407aad42')
        cs.set_cookie(url, c)
        self.assertTrue(len(cs.search(url)) == 1)
        c = cookie.Cookie('lang', 'long-life', max_age=300)
        cs.set_cookie(url, c)
        self.assertTrue(len(cs.search(url)) == 2)
        # end session remove only session cookies
        cs.end_session()
        clist = cs.search(url)
        self.assertTrue(len(clist) == 1)
        self.assertTrue(clist[0].name == b'lang')
        self.assertTrue(clist[0].value == b'long-life')

    def test_expire_cookies(self):
        """The user agent MUST evict all expired cookies from the cookie
        store if, at any time, an expired cookie exists in the cookie
        store."""
        cs = cookie.CookieStore()
        url = uri.URI.from_octets('http://test.example.com/')
        c = cookie.Cookie('SID', '31d4d96e407aad42', max_age=300)
        expire_time = time.time()+600
        self.assertTrue(c.expired(expire_time))
        cs.set_cookie(url, c)
        self.assertTrue(len(cs.search(url)) == 1)
        cs.expire_cookies()
        self.assertTrue(len(cs.search(url)) == 1)
        # pass a future time to expire the cookie forcibly
        cs.expire_cookies(expire_time)
        self.assertTrue(len(cs.search(url)) == 0)

    def test_sort_order(self):
        """Sort order tests:

        Cookies with longer paths are listed before cookies with shorter
        paths.

        Among cookies that have equal-length path fields, cookies with
        earlier creation-times are listed before cookies with later
        creation-times."""
        cs = cookie.CookieStore()
        cs.add_private_suffix('example.com')
        url = uri.URI.from_octets('http://test.example.com/dir/file.txt')
        c = cookie.Cookie('SID', 's1', path="/")
        c.creation_time = c.access_tiem = time.time() - 300
        cs.set_cookie(url, c)
        c = cookie.Cookie('SID', 's2')
        # default path of /dir/
        cs.set_cookie(url, c)
        c = cookie.Cookie('SID', 's3', path="/", domain="example.com")
        cs.set_cookie(url, c)
        clist = cs.search(url)
        self.assertTrue(len(clist) == 3)
        self.assertTrue(clist[0].value == b"s2")
        self.assertTrue(clist[1].value == b"s1")
        self.assertTrue(clist[2].value == b"s3")


class ClientTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.client = MockCookieClient(self.run_manager, max_connections=3)
        self.cs = cookie.CookieStore()
        self.cs.add_private_suffix('domain1.com')
        self.cs.add_private_suffix('domain2.com')
        self.client.set_cookie_store(self.cs)
        self.cookie_count = 0

    def tearDown(self):     # noqa
        self.client.close()

    def run_manager(self, host, port, sock):
        # read some data from sock, and post a response
        if host == "www.domain1.com" and port == 80:
            self.run_domain1(sock)
        elif host == "www.domain2.com" and port == 80:
            # same handler!
            self.run_domain1(sock)
        elif host == "www.domain3.com" and port == 80:
            # same handler!
            self.run_domain1(sock)
        elif host == "alt.www.domain1.com" and port == 80:
            # same handler!
            self.run_domain1(sock)
        elif host == "alt.www.domain3.com" and port == 80:
            # same handler!
            self.run_domain1(sock)
        else:
            # connection error
            raise ValueError("run_manager: bad host in connect")

    def run_domain1(self, sock):
        while True:
            req = sock.recv_request()
            if req is None:
                break
            response = messages.Response(req, entity_body=TEST_STRING)
            if req.request_uri == "/status100":
                response.set_status(200, "You got it!")
            elif req.request_uri == "/status200":
                response.set_set_cookie(
                    cookie.Cookie('SID', '31d4d96e407aad42'))
                response.set_status(200, "Success")
            elif req.request_uri == "/redirect":
                response.set_location('http://www.domain1.com/status300')
                response.set_set_cookie(cookie.Cookie('SID', 'Status300'))
                response.set_status(301, "Moved")
            elif req.request_uri == "/status300":
                response.set_status(200, "Success")
            elif req.request_uri == "/status403":
                response.set_set_cookie(cookie.Cookie('SID', 'GoAway'))
                response.set_status(403, "Unauthorized")
            elif req.request_uri == "/status500":
                response.set_set_cookie(cookie.Cookie('SID', 'DaisyDaisy'))
                response.set_status(500, "Server Error")
            elif req.request_uri == "/setCookie":
                response.set_set_cookie(
                    cookie.Cookie('SID', '31d4d96e407aad42'))
                response.set_status(200, "Success")
            elif req.request_uri == "/setCookieFlag":
                response.set_set_cookie(
                    cookie.Cookie('SID', '31d4d96e407aad42',
                                  extensions=['extra=1']))
                response.set_status(200, "Success")
            elif req.request_uri == "/setFutureCookie":
                # sets a cookie that expires in the future
                response.set_set_cookie(
                    cookie.Cookie(
                        'SID', '31d4d96e407aad42',
                        expires=params.FullDate.from_unix_time(
                            time.time()+300)))
                response.set_status(200, "Cookie set")
            elif req.request_uri == "/checkCookie":
                cookies = req.get_cookie()
                # returns a dictionary of cookies or an empty dictionary
                if b'SID' in cookies and cookies[b'SID'] == \
                        b'31d4d96e407aad42':
                    response.set_status(200, "Cookie checked")
                else:
                    response.set_status(400, "Missing cookie")
            elif req.request_uri == "/set2Cookies":
                response.set_set_cookie(
                    cookie.Cookie('SID', '31d4d96e407aad42', path='/',
                                  secure=True, http_only=True))
                response.set_set_cookie(
                    cookie.Cookie('lang', 'en-US', path='/',
                                  domain='domain1.com'))
                response.set_status(200, "Success")
            elif req.request_uri == "/check2Cookies":
                cookies = req.get_cookie()
                # returns a dictionary of cookies
                if (len(cookies) == 2 and
                        cookies.get(b'SID', b'x') == b'31d4d96e407aad42' and
                        cookies.get(b'lang', b'x') == b'en-US'):
                    response.set_status(200, "Cookies checked")
                else:
                    response.set_status(400, "Missing cookie(s)")
            elif req.request_uri == '/counter':
                cookies = req.get_cookie()
                if (self.cookie_count == 0 or
                        (cookies and cookies.get(b'count', b'x') ==
                         str(self.cookie_count).encode('ascii'))):
                    self.cookie_count += 1
                    response.set_set_cookie(
                        cookie.Cookie('count', str(self.cookie_count)))
                    response.set_status(200, "Cookie incremented")
                else:
                    response.set_status(400, "Missing or bad cookie")
            elif req.request_uri == '/expirecount':
                response.set_set_cookie(
                    cookie.Cookie(
                        'count', str(self.cookie_count),
                        expires=params.FullDate(
                            iso.TimePoint.from_str('20010101T010101Z'))))
                response.set_status(200, "Cookie cleared")
            elif req.request_uri == "/check0Cookies":
                cookies = req.get_cookie()
                # returns a dictionary of cookies
                if (len(cookies) == 0):
                    response.set_status(200, "Cookies cleared")
                else:
                    response.set_status(400, "Unexpected cookie(s)")
            elif req.request_uri == '/siteCookie':
                response.set_set_cookie(cookie.Cookie('wwwonly', 'domain'))
                response.set_status(200, "Site cookie set")
            elif req.request_uri == "/checkSiteCookie":
                cookies = req.get_cookie()
                if b'wwwonly' in cookies and cookies[b'wwwonly'] == b'domain':
                    response.set_status(200, "Cookie checked")
                else:
                    response.set_status(400, "Missing cookie")
            elif req.request_uri == '/publicCookie':
                response.set_set_cookie(
                    cookie.Cookie('public', 'domain', domain="com"))
                response.set_status(200, "Public cookie set")
            elif req.request_uri == '/domain3Cookie':
                response.set_set_cookie(
                    cookie.Cookie('public', 'domain',
                                  domain="www.domain3.com"))
                response.set_status(200, "Domain cookie set")
            elif req.request_uri == '/checkDomain3Cookie':
                cookies = req.get_cookie()
                if b'public' in cookies and cookies[b'public'] == b'domain':
                    response.set_status(200, "Cookie checked")
                else:
                    response.set_status(400, "Missing cookie")
            elif req.request_uri == '/crossDomainCookie':
                response.set_set_cookie(
                    cookie.Cookie('public', 'domain', domain="domain2.com"))
                response.set_status(200, "Site cookie set")
            else:
                response = messages.Response(req)
                response.set_status(400, "Test failed for domain1: %s")
            sock.send_response(response)

    def test_simple(self):
        """simple test:

        Set a cookie, check that it is returned."""
        request = http.ClientRequest("http://www.domain1.com/setCookie")
        self.client.process_request(request)
        request = http.ClientRequest("http://www.domain1.com/checkCookie")
        self.client.process_request(request)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)

    def test_multiple(self):
        """simple test:

        Set two cookies, check that both are returned."""
        request = http.ClientRequest("http://www.domain1.com/set2Cookies")
        self.client.process_request(request)
        request = http.ClientRequest("http://www.domain1.com/check2Cookies")
        self.client.process_request(request)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)

    def test_replace(self):
        """simple test:

        Set a cookie, update a cookie, check it replaces:

        If the user agent receives a new cookie with the same
        cookie-name, domain-value, and path-value as a cookie that it
        has already stored, the existing cookie is evicted and replaced
        with the new cookie

        Notice that servers can delete cookies by sending the user agent
        a new cookie with an Expires attribute with a value in the
        past."""
        request = http.ClientRequest("http://www.domain1.com/counter")
        self.client.process_request(request)
        request = http.ClientRequest("http://www.domain1.com/counter")
        self.client.process_request(request)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        request = http.ClientRequest("http://www.domain1.com/expirecount")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # now the next call should have no cookies
        request = http.ClientRequest("http://www.domain1.com/check0Cookies")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)

    def test_status(self):
        """status tests

        RFC 6265:

            User agents MAY ignore Set-Cookie headers contained in
            responses with 100-level status codes but MUST process
            Set-Cookie headers contained in other responses (including
            responses with 400- and 500-level status codes)"""
        request = http.ClientRequest(
            "http://www.domain1.com/status100", method="PUT",
            entity_body=TEST_STRING)
        request.set_expect_continue()
        self.client.queue_request(request)
        # thread_loop will process the queue until it blocks for more
        # than the timeout (default, forever)
        self.client.thread_loop(timeout=5)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # check that the cookie was stored
        cookies = self.cs.search(
            uri.URI.from_octets('http://www.domain1.com/'))
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(cookies[0].name == b"SID")
        self.assertTrue(cookies[0].value == b"Status100")
        # Check status 200
        request = http.ClientRequest("http://www.domain1.com/status200")
        self.client.process_request(request)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        cookies = self.cs.search(
            uri.URI.from_octets('http://www.domain1.com/'))
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(cookies[0].name == b"SID")
        self.assertTrue(cookies[0].value == b"31d4d96e407aad42")
        # Check status 3xx
        request = http.ClientRequest("http://www.domain1.com/redirect")
        self.client.process_request(request)
        response = request.response
        # check that the follow-up response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        cookies = self.cs.search(
            uri.URI.from_octets('http://www.domain1.com/'))
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(cookies[0].name == b"SID")
        self.assertTrue(cookies[0].value == b"Status300")
        # Check status 4xx
        request = http.ClientRequest("http://www.domain1.com/status403")
        self.client.process_request(request)
        response = request.response
        # check that the follow-up response was received
        self.assertTrue(
            response.status == 403,
            "Status in response: %i" %
            response.status)
        cookies = self.cs.search(
            uri.URI.from_octets('http://www.domain1.com/'))
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(cookies[0].name == b"SID")
        self.assertTrue(cookies[0].value == b"GoAway")
        # Check status 5xx
        request = http.ClientRequest("http://www.domain1.com/status500")
        self.client.process_request(request)
        response = request.response
        # check that the follow-up response was received
        self.assertTrue(
            response.status == 500,
            "Status in response: %i" %
            response.status)
        cookies = self.cs.search(
            uri.URI.from_octets('http://www.domain1.com/'))
        self.assertTrue(len(cookies) == 1)
        self.assertTrue(cookies[0].name == b"SID")
        self.assertTrue(cookies[0].value == b"DaisyDaisy")

    def test_site_cookie(self):
        """subdomain test...

        Unless the cookie's attributes indicate otherwise, the cookie
        is returned only to the origin server (and not, for example, to
        any subdomains)"""
        request = http.ClientRequest("http://www.domain1.com/siteCookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        request = http.ClientRequest("http://www.domain1.com/checkSiteCookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        request = http.ClientRequest("http://www.domain2.com/checkSiteCookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 400,
            "Status in response: %i" %
            response.status)
        request = http.ClientRequest(
            "http://alt.www.domain1.com/checkSiteCookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 400,
            "Status in response: %i" %
            response.status)

    def test_public_cookie(self):
        request = http.ClientRequest("http://www.domain1.com/publicCookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # we should reject the .com cookie as being public
        request = http.ClientRequest("http://www.domain1.com/check0Cookies")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # now hit a public server directly
        request = http.ClientRequest("http://www.domain3.com/domain3Cookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # we should reject the domain setting but keep it for this case:
        request = http.ClientRequest(
            "http://www.domain3.com/checkDomain3Cookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # the cookie should be host only for www.domain3.com
        request = http.ClientRequest(
            "http://alt.www.domain3.com/check0Cookies")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)

    def test_cross_domain(self):
        request = http.ClientRequest(
            "http://www.domain1.com/crossDomainCookie")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)
        # we should reject the domain2.com cookie as being cross-domain
        request = http.ClientRequest("http://www.domain2.com/check0Cookies")
        self.client.process_request(request)
        response = request.response
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)

    def test_unrecognized_attribute(self):
        """Unrecognized attribute

        User agents ignore unrecognized cookie attributes (but not the
        entire cookie)"""
        request = http.ClientRequest("http://www.domain1.com/setCookieFlag")
        self.client.process_request(request)
        request = http.ClientRequest("http://www.domain1.com/checkCookie")
        self.client.process_request(request)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)

    def test_future_cookie(self):
        """Future cookie"""
        request = http.ClientRequest("http://www.domain1.com/setFutureCookie")
        self.client.process_request(request)
        request = http.ClientRequest("http://www.domain1.com/checkCookie")
        self.client.process_request(request)
        response = request.response
        # check that the response was received
        self.assertTrue(
            response.status == 200,
            "Status in response: %i" %
            response.status)


def test_publicsuffix():
    """Test function for publicsuffix.org list

    Not run routinely as it grabs the domain list from the internet each
    time it is run."""
    cs = cookie.CookieStore()
    # download the list
    path = os.path.join('local', 'effective_tld_names.dat')
    cs.fetch_public_suffix_list(path)
    with open(path, 'rb') as f:
        cs.set_public_list(f.read().decode('utf-8'))
    # The following code adapted from
    # http://mxr.mozilla.org/mozilla-central/source/netwerk/test/unit/data/test_psl.txt?raw=1
    #
    # Any copyright is dedicated to the Public Domain.
    # http://creativecommons.org/publicdomain/zero/1.0/
    #
    # null input.
    cs.check_public_suffix(None, None)
    # Mixed case.
    cs.check_public_suffix('COM', None)
    cs.check_public_suffix('example.COM', 'example.com')
    cs.check_public_suffix('WwW.example.COM', 'example.com')
    # Leading dot.
    cs.check_public_suffix('.com', None)
    cs.check_public_suffix('.example', None)
    cs.check_public_suffix('.example.com', None)
    cs.check_public_suffix('.example.example', None)
    # Unlisted TLD.
    cs.check_public_suffix('example', None)
    cs.check_public_suffix('example.example', 'example.example')
    cs.check_public_suffix('b.example.example', 'example.example')
    cs.check_public_suffix('a.b.example.example', 'example.example')
    # Listed, but non-Internet, TLD.
    # cs.check_public_suffix('local', None)
    # cs.check_public_suffix('example.local', None)
    # cs.check_public_suffix('b.example.local', None)
    # cs.check_public_suffix('a.b.example.local', None)
    # TLD with only 1 rule.
    cs.check_public_suffix('biz', None)
    cs.check_public_suffix('domain.biz', 'domain.biz')
    cs.check_public_suffix('b.domain.biz', 'domain.biz')
    cs.check_public_suffix('a.b.domain.biz', 'domain.biz')
    # TLD with some 2-level rules.
    cs.check_public_suffix('com', None)
    cs.check_public_suffix('example.com', 'example.com')
    cs.check_public_suffix('b.example.com', 'example.com')
    cs.check_public_suffix('a.b.example.com', 'example.com')
    cs.check_public_suffix('uk.com', None)
    cs.check_public_suffix('example.uk.com', 'example.uk.com')
    cs.check_public_suffix('b.example.uk.com', 'example.uk.com')
    cs.check_public_suffix('a.b.example.uk.com', 'example.uk.com')
    cs.check_public_suffix('test.ac', 'test.ac')
    # TLD with only 1 (wildcard) rule.
    cs.check_public_suffix('cy', None)
    cs.check_public_suffix('c.cy', None)
    cs.check_public_suffix('b.c.cy', 'b.c.cy')
    cs.check_public_suffix('a.b.c.cy', 'b.c.cy')
    # More complex TLD.
    cs.check_public_suffix('jp', None)
    cs.check_public_suffix('test.jp', 'test.jp')
    cs.check_public_suffix('www.test.jp', 'test.jp')
    cs.check_public_suffix('ac.jp', None)
    cs.check_public_suffix('test.ac.jp', 'test.ac.jp')
    cs.check_public_suffix('www.test.ac.jp', 'test.ac.jp')
    cs.check_public_suffix('kyoto.jp', None)
    cs.check_public_suffix('test.kyoto.jp', 'test.kyoto.jp')
    cs.check_public_suffix('ide.kyoto.jp', None)
    cs.check_public_suffix('b.ide.kyoto.jp', 'b.ide.kyoto.jp')
    cs.check_public_suffix('a.b.ide.kyoto.jp', 'b.ide.kyoto.jp')
    cs.check_public_suffix('c.kobe.jp', None)
    cs.check_public_suffix('b.c.kobe.jp', 'b.c.kobe.jp')
    cs.check_public_suffix('a.b.c.kobe.jp', 'b.c.kobe.jp')
    cs.check_public_suffix('city.kobe.jp', 'city.kobe.jp')
    cs.check_public_suffix('www.city.kobe.jp', 'city.kobe.jp')
    # TLD with a wildcard rule and exceptions.
    cs.check_public_suffix('ck', None)
    cs.check_public_suffix('test.ck', None)
    cs.check_public_suffix('b.test.ck', 'b.test.ck')
    cs.check_public_suffix('a.b.test.ck', 'b.test.ck')
    cs.check_public_suffix('www.ck', 'www.ck')
    cs.check_public_suffix('www.www.ck', 'www.ck')
    # US K12.
    cs.check_public_suffix('us', None)
    cs.check_public_suffix('test.us', 'test.us')
    cs.check_public_suffix('www.test.us', 'test.us')
    cs.check_public_suffix('ak.us', None)
    cs.check_public_suffix('test.ak.us', 'test.ak.us')
    cs.check_public_suffix('www.test.ak.us', 'test.ak.us')
    cs.check_public_suffix('k12.ak.us', None)
    cs.check_public_suffix('test.k12.ak.us', 'test.k12.ak.us')
    cs.check_public_suffix('www.test.k12.ak.us', 'test.k12.ak.us')
    # IDN labels.
    cs.check_public_suffix(u8(b'\xe9\xa3\x9f\xe7\x8b\xae.com.cn'),
                           u8(b'\xe9\xa3\x9f\xe7\x8b\xae.com.cn'))
    cs.check_public_suffix(
        u8(b'\xe9\xa3\x9f\xe7\x8b\xae.\xe5\x85\xac\xe5\x8f\xb8.cn'),
        u8(b'\xe9\xa3\x9f\xe7\x8b\xae.\xe5\x85\xac\xe5\x8f\xb8.cn'))
    cs.check_public_suffix(
        u8(b'www.\xe9\xa3\x9f\xe7\x8b\xae.\xe5\x85\xac\xe5\x8f\xb8.cn'),
        u8(b'www.\xe9\xa3\x9f\xe7\x8b\xae.\xe5\x85\xac\xe5\x8f\xb8.cn'))
    cs.check_public_suffix(u8(b'shishi.\xe5\x85\xac\xe5\x8f\xb8.cn'),
                           u8(b'shishi.\xe5\x85\xac\xe5\x8f\xb8.cn'))
    cs.check_public_suffix(u8(b'\xe5\x85\xac\xe5\x8f\xb8.cn'), None)
    cs.check_public_suffix(
        u8(b'\xe9\xa3\x9f\xe7\x8b\xae.\xe4\xb8\xad\xe5\x9b\xbd'),
        u8(b'\xe9\xa3\x9f\xe7\x8b\xae.\xe4\xb8\xad\xe5\x9b\xbd'))
    cs.check_public_suffix(
        u8(b'www.\xe9\xa3\x9f\xe7\x8b\xae.\xe4\xb8\xad\xe5\x9b\xbd'),
        u8(b'\xe9\xa3\x9f\xe7\x8b\xae.\xe4\xb8\xad\xe5\x9b\xbd'))
    cs.check_public_suffix(u8(b'shishi.\xe4\xb8\xad\xe5\x9b\xbd'),
                           u8(b'shishi.\xe4\xb8\xad\xe5\x9b\xbd'))
    cs.check_public_suffix(u8(b'\xe4\xb8\xad\xe5\x9b\xbd'), None)
    # Same as above, but punycoded.
    cs.check_public_suffix('xn--85x722f.com.cn', 'xn--85x722f.com.cn')
    cs.check_public_suffix('xn--85x722f.xn--55qx5d.cn',
                           'xn--85x722f.xn--55qx5d.cn')
    cs.check_public_suffix('www.xn--85x722f.xn--55qx5d.cn',
                           'xn--85x722f.xn--55qx5d.cn')
    cs.check_public_suffix('shishi.xn--55qx5d.cn', 'shishi.xn--55qx5d.cn')
    cs.check_public_suffix('xn--55qx5d.cn', None)
    cs.check_public_suffix('xn--85x722f.xn--fiqs8s', 'xn--85x722f.xn--fiqs8s')
    cs.check_public_suffix('www.xn--85x722f.xn--fiqs8s',
                           'xn--85x722f.xn--fiqs8s')
    cs.check_public_suffix('shishi.xn--fiqs8s', 'shishi.xn--fiqs8s')
    cs.check_public_suffix('xn--fiqs8s', None)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # test_publicsuffix()
    unittest.main()
