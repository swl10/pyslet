#! /usr/bin/env python

import unittest
import logging

from pyslet.http.grammar import *       # noqa


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(GenericParserTests, 'test'),
    ))


class GenericParserTests(unittest.TestCase):

    def test_basic(self):
        # OCTET = <any 8-bit sequence of data>
        for c in xrange(0, 256):
            self.assertTrue(is_octet(chr(c)), "is_octet(chr(%i))" % c)
        # CHAR = <any US-ASCII character (octets 0 - 127)>
        for c in xrange(0, 128):
            self.assertTrue(is_char(chr(c)), "is_char(chr(%i))" % c)
        for c in xrange(128, 256):
            self.assertFalse(is_char(chr(c)), "is_char(chr(%i))" % c)
        # upalpha = <any US-ASCII uppercase letter "A".."Z">
        upalpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(
                is_upalpha(c) == (c in upalpha), "is_upalpha(chr(%i))" % i)
        # loalpha = <any US-ASCII lowercase letter "a".."z">
        loalpha = "abcdefghijklmnopqrstuvwxyz"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(
                is_loalpha(c) == (c in loalpha), "is_loalpha(chr(%i))" % i)
        # alpha = upalpha | loalpha
        alpha = upalpha + loalpha
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(is_alpha(c) == (c in alpha),
                            "is_alpha(chr(%i))" % i)
        # digit  = <any US-ASCII digit "0".."9">
        digit = "0123456789"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(is_digit(c) == (c in digit),
                            "is_digit(chr(%i))" % i)
        # ctl = <any US-ASCII control character (octets 0 - 31) and DEL (127)>
        ctl = string.join(map(chr, xrange(0, 32)) + [chr(127)], '')
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(is_ctl(c) == (c in ctl), "is_ctl(chr(%i))" % i)
        # CR = <US-ASCII CR, carriage return (13)>
        self.assertTrue(CR == chr(13), "CR")
        # LF = <US-ASCII LF, linefeed (10)>
        self.assertTrue(LF == chr(10), "LF")
        # SP = <US-ASCII SP, space (32)>
        self.assertTrue(SP == chr(32), "SP")
        # HT = <US-ASCII HT, horizontal-tab (9)>
        self.assertTrue(HT == chr(9), "HT")
        # DQUOTE = <US-ASCII double-quote mark (34)>
        self.assertTrue(DQUOTE == chr(34), "DQUOTE")
        # CRLF
        self.assertTrue(CRLF == CR + LF, "CRLF")
        # LWS = [CRLF] 1*( SP | HT )
        lws_test = "; \t ;\r\n ;\r\n \r\n\t \r "
        p = OctetParser(lws_test)
        self.assertTrue(p.parse_lws() is None, "No LWS")
        p.Parse(";")
        self.assertTrue(p.parse_lws() == " \t ", "LWS no CRLF")
        p.Parse(";")
        self.assertTrue(p.parse_lws() == "\r\n ", "LWS with CRLF")
        p.Parse(";")
        self.assertTrue(p.parse_lws() == "\r\n ", "LWS ending at CRLF")
        self.assertTrue(p.parse_lws() == "\r\n\t ", "LWS ending at CRLF")
        # TEXT = <any OCTET except CTLs, but including LWS>
        p = OctetParser(lws_test)
        self.assertTrue(len(p.parse_text()) == 16, "TEXT ending at CR")
        p = OctetParser(lws_test)
        self.assertTrue(p.parse_text(True) == "; \t ; ;  ", "Unfolded TEXT")
        # hexdigit = "A" | "B" | "C" | "D" | "E" | "F" | "a" | "b" | "c"
        # | "d" | "e" | "f" | digit
        hexdigit = "ABCDEFabcdef" + digit
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(is_hex(c) == (c in hexdigit),
                            "is_hex(chr(%i))" % i)
        # words, including comment, quoted string and qdpair
        word_test = 'Hi(Hi\r\n Hi)Hi<Hi>Hi@Hi,Hi;Hi:Hi\\Hi"\\"Hi\r\n Hi\\""'\
            '/Hi[Hi]Hi?Hi=Hi{Hi}Hi Hi\tHi\r\n Hi'
        word_testresult = [
            "Hi", "(Hi Hi)", "Hi", "<", "Hi", ">", "Hi", "@", "Hi", ",",
            "Hi", ";", "Hi", ":", "Hi", "\\", "Hi", '"\\"Hi Hi\\""', "/",
            "Hi", "[", "Hi", "]", "Hi", "?", "Hi", "=", "Hi", "{", "Hi",
            "}", "Hi", "Hi", "Hi", "Hi"]
        p = OctetParser(word_test)
        p = WordParser(p.parse_text(True))
        self.assertTrue(p.words == word_testresult, "basic word parser")
        # token
        try:
            check_token("Hi")
        except ValueError:
            self.fail("check_token('Hi')")
        for t in word_testresult:
            if t == "Hi":
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
        self.assertTrue(p.parse_token() == "a", "Expected 'a'")
        self.assertFalse(p.the_word, "Expected no more words")
        self.assertFalse(p.is_token(), "Expected no token")

    def test_token_list(self):
        p = WordParser(" a ")
        self.assertTrue(p.parse_tokenlist() == ["a"], "Expected ['a']")
        self.assertFalse(p.the_word, "Expected no more words")
        self.assertFalse(p.is_token(), "Expected no token")
        p = WordParser(" a , b,c ,d,,efg")
        self.assertTrue(
            p.parse_tokenlist() == ["a", "b", "c", "d", "efg"],
            "Bad token list")
        self.assertFalse(p.the_word, "Expected no more words")
        self.assertFalse(p.is_token(), "Expected no token")

    def test_parameter(self):
        parameters = {}
        p = WordParser(' ;X=1 ;y=2;Zoo=";A=\\"Three\\""')
        p.parse_parameters(parameters)
        self.assertTrue(
            parameters == {
                'x': ('X', '1'),
                'y': ('y', '2'),
                'zoo': ('Zoo', ';A="Three"')},
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
        p = WordParser(' ;X=1 ;q=2;Zoo=";A=\\"Three\\""')
        p.parse_parameters(parameters, qmode="q")
        self.assertTrue(
            parameters == {'x': ('X', '1')},
            "Paremters: %s" % repr(parameters))
        parameters = {}
        p.parse_parameters(parameters)
        self.assertTrue(
            parameters == {'q': ('q', '2'), 'zoo': ('Zoo', ';A="Three"')},
            "Paremters: %s" % repr(parameters))
        parameters = {}
        p = WordParser(' ;X=1 ;y=2;Zoo=";A=\\"Three\\""')
        p.parse_parameters(parameters, case_sensitive=True)
        self.assertTrue(
            parameters == {'X': ('X', '1'), 'y': ('y', '2'),
                           'Zoo': ('Zoo', ';A="Three"')},
            "Paremters: %s" % repr(parameters))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO, format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
