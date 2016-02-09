#! /usr/bin/env python

import unittest
import logging

from pyslet.py2 import range3, byte, join_bytes
from pyslet.http.grammar import *       # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(GenericParserTests, 'test'),
    ))


class GenericParserTests(unittest.TestCase):

    def test_basic(self):
        # OCTET = <any 8-bit sequence of data>
        for c in range3(0, 256):
            self.assertTrue(is_octet(byte(c)), "is_octet(byte(%i))" % c)
        # CHAR = <any US-ASCII character (octets 0 - 127)>
        for c in range3(0, 128):
            self.assertTrue(is_char(byte(c)), "is_char(byte(%i))" % c)
        for c in range3(128, 256):
            self.assertFalse(is_char(byte(c)), "is_char(byte(%i))" % c)
        # upalpha = <any US-ASCII uppercase letter "A".."Z">
        upalpha = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i in range3(0, 256):
            c = byte(i)
            self.assertTrue(
                is_upalpha(c) == (c in upalpha), "is_upalpha(byte(%i))" % i)
        # loalpha = <any US-ASCII lowercase letter "a".."z">
        loalpha = b"abcdefghijklmnopqrstuvwxyz"
        for i in range3(0, 256):
            c = byte(i)
            self.assertTrue(
                is_loalpha(c) == (c in loalpha), "is_loalpha(byte(%i))" % i)
        # alpha = upalpha | loalpha
        alpha = upalpha + loalpha
        for i in range3(0, 256):
            c = byte(i)
            self.assertTrue(is_alpha(c) == (c in alpha),
                            "is_alpha(byte(%i))" % i)
        # digit  = <any US-ASCII digit "0".."9">
        digit = b"0123456789"
        for i in range3(0, 256):
            c = byte(i)
            self.assertTrue(is_digit(c) == (c in digit),
                            "is_digit(byte(%i))" % i)
        # ctl = <any US-ASCII control character (octets 0 - 31) and DEL (127)>
        ctl = join_bytes([byte(ic) for ic in range3(0, 32)] + [byte(127)])
        for i in range3(0, 256):
            c = byte(i)
            self.assertTrue(is_ctl(c) == (c in ctl), "is_ctl(byte(%i))" % i)
        # CR = <US-ASCII CR, carriage return (13)>
        self.assertTrue(CR == byte(13), "CR")
        # LF = <US-ASCII LF, linefeed (10)>
        self.assertTrue(LF == byte(10), "LF")
        # SP = <US-ASCII SP, space (32)>
        self.assertTrue(SP == byte(32), "SP")
        # HT = <US-ASCII HT, horizontal-tab (9)>
        self.assertTrue(HT == byte(9), "HT")
        # DQUOTE = <US-ASCII double-quote mark (34)>
        self.assertTrue(DQUOTE == byte(34), "DQUOTE")
        # CRLF
        self.assertTrue(CRLF == join_bytes([CR, LF]), "CRLF")
        # LWS = [CRLF] 1*( SP | HT )
        lws_test = "; \t ;\r\n ;\r\n \r\n\t \r "
        p = OctetParser(lws_test)
        self.assertTrue(p.parse_lws() is None, "No LWS")
        p.parse(b";")
        result = p.parse_lws()
        self.assertTrue(result == b" \t ", "LWS no CRLF: %s" % repr(result))
        p.parse(b";")
        result = p.parse_lws()
        self.assertTrue(result == b"\r\n ", "LWS with CRLF: %s" % repr(result))
        p.parse(b";")
        self.assertTrue(p.parse_lws() == b"\r\n ", "LWS ending at CRLF")
        self.assertTrue(p.parse_lws() == b"\r\n\t ", "LWS ending at CRLF")
        # TEXT = <any OCTET except CTLs, but including LWS>
        p = OctetParser(lws_test)
        self.assertTrue(len(p.parse_text()) == 16, "TEXT ending at CR")
        p = OctetParser(lws_test)
        self.assertTrue(p.parse_text(True) == b"; \t ; ;  ", "Unfolded TEXT")
        # hexdigit = "A" | "B" | "C" | "D" | "E" | "F" | "a" | "b" | "c"
        # | "d" | "e" | "f" | digit
        hexdigit = b"ABCDEFabcdef" + digit
        for i in range3(0, 256):
            c = byte(i)
            self.assertTrue(is_hex(c) == (c in hexdigit),
                            "is_hex(byte(%i))" % i)
        # words, including comment, quoted string and qdpair
        word_test = b'Hi(Hi\r\n Hi)Hi<Hi>Hi@Hi,Hi;Hi:Hi\\Hi"\\"Hi\r\n Hi\\""'\
            b'/Hi[Hi]Hi?Hi=Hi{Hi}Hi Hi\tHi\r\n Hi'
        word_testresult = [
            b"Hi", b"(Hi Hi)", b"Hi", byte("<"), b"Hi", byte(">"), b"Hi",
            byte("@"), b"Hi", byte(","), b"Hi", byte(";"), b"Hi", byte(":"),
            b"Hi", byte("\\"), b"Hi", b'"\\"Hi Hi\\""', byte("/"), b"Hi",
            byte("["), b"Hi", byte("]"), b"Hi", byte("?"), b"Hi", byte("="),
            b"Hi", byte("{"), b"Hi", byte("}"), b"Hi", b"Hi", b"Hi", b"Hi"]
        p = OctetParser(word_test)
        p = WordParser(p.parse_text(True))
        self.assertTrue(p.words == word_testresult, "basic word parser: %s" %
                        repr(p.words))
        # token
        try:
            self.assertTrue(check_token(b"Hi") == "Hi")
        except ValueError:
            self.fail("check_token(b'Hi')")
        for t in word_testresult:
            if t == b"Hi":
                continue
            try:
                check_token(t)
                self.fail("Non token checked OK: %s" % t)
            except ValueError:
                pass
        # comment

    def test_token(self):
        p = WordParser(" a ")
        self.assertTrue(p.the_word, "Expected a word")
        self.assertTrue(p.is_token(), "Expected a token")
        self.assertTrue(p.parse_token() == b"a", "Expected 'a'")
        self.assertFalse(p.the_word, "Expected no more words")
        self.assertFalse(p.is_token(), "Expected no token")

    def test_token_list(self):
        p = WordParser(" a ")
        self.assertTrue(p.parse_tokenlist() == ["a"], "Expected ['a']")
        self.assertFalse(p.the_word, "Expected no more words")
        self.assertFalse(p.is_token(), "Expected no token")
        p = WordParser(" a , b,c ,d,,efg")
        result = p.parse_tokenlist()
        self.assertTrue(
            result == ["a", "b", "c", "d", "efg"],
            "Bad token list: %s" % repr(result))
        self.assertFalse(p.the_word, "Expected no more words")
        self.assertFalse(p.is_token(), "Expected no token")

    def test_parameter(self):
        """tests parameter parsing

        RFC2616 quotes...

            special characters MUST be in a quoted string to be used
            within a parameter value"""
        parameters = {}
        p = WordParser(' ;X=1 ;y=2;Zoo=";A=\\"Three\\""')
        p.parse_parameters(parameters)
        self.assertTrue(
            parameters == {
                'x': ('X', b'1'),
                'y': ('y', b'2'),
                'zoo': ('Zoo', b';A="Three"')},
            "Paremters: %s" % repr(parameters))
        try:
            parameters = {}
            p = WordParser('token ;X =1', ignore_sp=False)
            p.parse_parameters(parameters, ignore_allsp=False)
            p.require_end()
            self.fail("parse_parameters: ignore_sp=False")
        except BadSyntax:
            pass
        parameters = {}
        p = WordParser(b' ;X=1 ;q=2;Zoo=";A=\\"Three\\""')
        p.parse_parameters(parameters, qmode="q")
        self.assertTrue(
            parameters == {'x': ('X', b'1')},
            "Paremters: %s" % repr(parameters))
        parameters = {}
        p.parse_parameters(parameters)
        self.assertTrue(
            parameters == {'q': ('q', b'2'), 'zoo':
                           ('Zoo', b';A="Three"')},
            "Paremters: %s" % repr(parameters))
        parameters = {}
        p = WordParser(b' ;X=1 ;y=2;Zoo=";A=\\"Three\\""')
        p.parse_parameters(parameters, case_sensitive=True)
        self.assertTrue(
            parameters == {'X': ('X', b'1'), 'y': ('y', b'2'),
                           'Zoo': ('Zoo', b';A="Three"')},
            "Paremters: %s" % repr(parameters))

    def test_crlf(self):
        try:
            p = WordParser('"\\\r\n"')
            self.fail("Unquoted CTL")
        except ValueError:
            pass
        try:
            p = WordParser('"\\\r\\\n"')
            self.assertTrue(decode_quoted_string(p.parse_word()) == b"\r\n")
        except ValueError:
            self.fail("Quoted CTL")
        try:
            p = WordParser('token1, token2, token3\r\nstuff')
            self.fail("CRLF without fold")
        except ValueError:
            pass


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
