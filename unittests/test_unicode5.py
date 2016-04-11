#! /usr/bin/env python

import codecs
import logging
import unittest

from sys import maxunicode

import pyslet.unicode5 as unicode5

from pyslet.py2 import (
    byte,
    character,
    is_text,
    join_bytes,
    py2,
    range3,
    u8,
    ul)


MAX_CHAR = 0x10FFFF
if maxunicode < MAX_CHAR:
    MAX_CHAR = maxunicode

CHINESE_TEST = u8(b'\xe8\x8b\xb1\xe5\x9b\xbd')


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(EncodingTests, 'test'),
        unittest.makeSuite(CharClassTests, 'test'),
        unittest.makeSuite(UCDTests, 'test'),
        unittest.makeSuite(ParserTests, 'test')
    ))


class EncodingTests(unittest.TestCase):

    def test_detection(self):
        test_string = u"Caf\xe9"
        for codec, bom in (
                ('utf_8', codecs.BOM_UTF8),
                ('utf_32_be', codecs.BOM_UTF32_BE),
                ('utf_32_le', codecs.BOM_UTF32_LE),
                ('utf_16_be', codecs.BOM_UTF16_BE),
                ('utf_16_le', codecs.BOM_UTF16_LE)):
            data = test_string.encode(codec)
            detected = unicode5.detect_encoding(data)
            self.assertTrue(detected == codec,
                            "%s detected as %s" % (codec, detected))
            # and once with the BOM
            if codec == 'utf_8':
                codec = 'utf_8_sig'
            data = bom + data
            detected = unicode5.detect_encoding(data)
            self.assertTrue(detected == codec,
                            "%s with BOM detected as %s" % (codec, detected))


class CharClassTests(unittest.TestCase):

    def test_constructor(self):
        c = unicode5.CharClass()
        if MAX_CHAR < 0x10FFFF:
            logging.warn("unicode5 tests truncated to character(0x%X) by "
                         "narrow python build" % MAX_CHAR)
        for code in range3(MAX_CHAR + 1):
            self.assertFalse(c.test(character(code)))
        c = unicode5.CharClass('a')
        self.assertTrue(self.class_test(c) == 'a')
        c = unicode5.CharClass(('a', 'z'))
        self.assertTrue(self.class_test(c) == 'abcdefghijklmnopqrstuvwxyz')
        c = unicode5.CharClass('abcxyz')
        self.assertTrue(
            len(c.ranges) == 2, "No range optimization: %s" % repr(c.ranges))
        self.assertTrue(self.class_test(c) == 'abcxyz')
        cc = unicode5.CharClass(c)
        self.assertTrue(self.class_test(cc) == 'abcxyz')
        c = unicode5.CharClass(('a', 'c'), ('e', 'g'), 'd')
        self.assertTrue(
            len(c.ranges) == 1, "Missing range optimization: %s"
            % repr(c.ranges))

    def test_complex_constructors(self):
        init_tests = [
            [[], ""],
            [[['a', 'z']], "abcdefghijklmnopqrstuvwxyz"],
            [[['a', 'd'], ['f', 'k']], "abcdfghijk"],
            [[['b', 'b']], "b"],
            [[['a', 'b'], ['c', 'd'], ['e', 'f'], ['g', 'h'],
              ['i', 'j'], ['k', 'k']], "abcdefghijk"],
            [[['a', 'b'], ['d', 'f'], ['h', 'h']], "abdefh"],
            [[['h', 'h'], ['d', 'f'], ['a', 'b']], "abdefh"],
        ]
        for test in init_tests:
            c = unicode5.CharClass(*test[0])
            result = self.class_test(c)
            self.assertTrue(result == test[1],
                            "CharClass test: expected %s, found %s" %
                            (test[1], result))

    def test_add(self):
        c = unicode5.CharClass(u"ac")
        c.add_char(u"b")
        self.assertTrue(self.class_test(c) == "abc", "add_char")
        c.add_range(u"b", u"e")
        self.assertTrue(self.class_test(c) == "abcde", "add_range")
        c.add_class(unicode5.CharClass(["m", "s"]))
        self.assertTrue(self.class_test(c) == "abcdemnopqrs", "add_class")

    def test_subtraction(self):
        c = unicode5.CharClass("abc")
        c.subtract_char("b")
        result = self.class_test(c)
        self.assertTrue(result == "ac", "subtract_char: %s" % result)
        c.subtract_range("b", "d")
        self.assertTrue(self.class_test(c) == "a", "subtract_range")
        tests = [
                [[], [], ""],
                [[['a', 'b']], [['c', 'd']], "ab"],
                [[['a', 'b']], [['b', 'c']], "a"],
                [[['a', 'c']], [['b', 'd']], "a"],
                [[['a', 'd']], [['b', 'd']], "a"],
                [[['a', 'd']], [['b', 'c']], "ad"],
                [[['a', 'c']], [['a', 'd']], ""],
                [[['a', 'c']], [['a', 'c']], ""],
                [[['a', 'd']], [['a', 'b']], "cd"],
                [[['b', 'c']], [['a', 'd']], ""],
                [[['b', 'c']], [['a', 'c']], ""],
                [[['b', 'd']], [['a', 'c']], "d"],
                [[['a', 'z']], [['f', 'h'], ['s', 'u']],
                    "abcdeijklmnopqrvwxyz"],
                [[['a', 'e'], ['i', 'r'], ['v', 'z']],
                    [['m', 'x']], "abcdeijklyz"]
        ]
        for test in tests:
            c1 = unicode5.CharClass(*test[0])
            c2 = unicode5.CharClass(*test[1])
            c3 = unicode5.CharClass(c1)
            c3.subtract_class(c2)
            result = self.class_test(c3)
            self.assertTrue(result == test[2],
                            "Subtract: %s - %s, found %s" %
                            (repr(c1), repr(c2), repr(c3)))

    def test_negate_char_class(self):
        """Check the Negation function"""
        min_char = character(0)
        max_char = character(maxunicode)
        char_class_tests = [
            [[], [[min_char, max_char]]],
            [[['b', 'c']], [[min_char, 'a'], ['d', max_char]]],
            [[['b', 'c'], ['e', 'f']], [
                [min_char, 'a'], ['d', 'd'], ['g', max_char]]]
        ]
        for test in char_class_tests:
            c1 = unicode5.CharClass(*test[0])
            c2 = unicode5.CharClass(c1)
            c2.negate()
            c3 = unicode5.CharClass(*test[1])
            self.assertTrue(c2 == c3, "%s negated to %s, expected %s" %
                            (repr(c1), repr(c2), repr(c3)))
            c2.negate()
            self.assertTrue(c2 == c1,
                            "%s double negation got %s" % (repr(c1), repr(c2)))

    def test_representation(self):
        repr_tests = [
            [[], "CharClass()", ""],
            [[['a', 'z']],
             "CharClass((u'a',u'z'))" if py2 else "CharClass(('a','z'))",
             "a-z"],
            [[['a', 'd'], ['f', 'k']],
             "CharClass((u'a',u'd'), (u'f',u'k'))" if py2 else
             "CharClass(('a','d'), ('f','k'))", "a-df-k"],
            [[['-', '-']],
             "CharClass(u'-')" if py2 else "CharClass('-')", "\\-"],
            [[['[', ']']],
             "CharClass((u'[',u']'))" if py2 else "CharClass(('[',']'))",
             "[-\\]"],
            [[['\\', '\\']],
             "CharClass(u'\\\\')" if py2 else "CharClass('\\\\')",
             "\\\\"],
        ]
        for test in repr_tests:
            c = unicode5.CharClass(*test[0])
            self.assertTrue(repr(c) == test[1],
                            "CharClass repr test: expected %s, found %s" %
                            (test[1], repr(c)))
            result = c.format_re()
            self.assertTrue(result == test[2],
                            "CharClass Re test: expected %s, found %s" %
                            (test[2], result))

    def class_test(self, cclass):
        result = []
        for c in range(ord('a'), ord('z') + 1):
            if cclass.test(character(c)):
                result.append(character(c))
        result = ''.join(result)
        return result


class UCDTests(unittest.TestCase):

    """Tests of the Unicode Category classes"""

    def test_ucd_classes(self):
        class_cc = unicode5.CharClass.ucd_category('Cc')
        class_c = unicode5.CharClass.ucd_category('C')
        for code in range3(0x20):
            self.assertTrue(class_cc.test(character(code)))
            self.assertTrue(class_c.test(character(code)))
        for code in range3(0x7F, 0xA0):
            self.assertTrue(class_cc.test(character(code)))
            self.assertTrue(class_c.test(character(code)))
        self.assertFalse(class_cc.test(character(0xAD)))
        self.assertTrue(class_c.test(character(0xAD)))
        self.assertTrue(
            unicode5.CharClass.ucd_category('Cf').test(character(0xAD)))

    def test_ucd_blocks(self):
        class_basic_latin = unicode5.CharClass.ucd_block('Basic Latin')
        self.assertTrue(class_basic_latin is unicode5.CharClass.ucd_block(
            'basiclatin'), "block name normalization")
        for code in range3(0x80):
            self.assertTrue(class_basic_latin.test(character(code)))
        self.assertFalse(class_basic_latin.test(character(0x80)))
        # randomly pick one of the other blocks
        class_basic_latin = unicode5.CharClass.ucd_block('Arrows')
        self.assertFalse(class_basic_latin.test(character(0x2150)))
        self.assertTrue(class_basic_latin.test(character(0x2190)))


class ParserTests(unittest.TestCase):

    def test_constructor(self):
        p = unicode5.BasicParser("hello")
        self.assertTrue(p.raw == py2)
        self.assertTrue(p.src == "hello")
        self.assertTrue(p.pos == 0)
        self.assertTrue(p.the_char == "h")
        p = unicode5.BasicParser(b"hello")
        self.assertTrue(p.raw)
        self.assertTrue(isinstance(p.src, bytes))
        self.assertTrue(isinstance(p.the_char, type(byte("h"))))
        p = unicode5.BasicParser(u"hello")
        self.assertFalse(p.raw)
        self.assertTrue(is_text(p.src))
        p = unicode5.BasicParser(bytearray(b"hello"))
        self.assertTrue(p.raw)
        self.assertTrue(isinstance(p.src, bytearray))

    def test_setpos(self):
        p = unicode5.BasicParser(u"hello")
        save_pos1 = p.pos
        p.parse("hell")
        save_pos2 = p.pos
        p.setpos(save_pos1)
        self.assertTrue(p.pos == 0)
        self.assertTrue(p.the_char == u"h")
        p.setpos(save_pos2)
        self.assertTrue(p.pos == 4)
        self.assertTrue(p.the_char == u"o")

    def test_nextchar(self):
        p = unicode5.BasicParser(u"hello")
        for c in u"hello":
            self.assertTrue(p.the_char == c)
            p.next_char()

    def test_parser_error(self):
        p = unicode5.BasicParser("hello")
        # called with no argument, no previous error...
        try:
            p.parser_error()
            self.fail("No parser error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e.production == '')
            self.assertTrue(e.pos == 0)
            self.assertTrue(e.left == "")
            self.assertTrue(e.right == "hello")
            self.assertTrue(str(e) ==
                            "ParserError: at [0]", str(e))
            self.assertTrue(isinstance(e, ValueError))
            last_e = e
        p.next_char()
        # called with a character string argument, raises a new parser error
        try:
            p.parser_error('test')
            self.fail("No parser error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e.production == 'test')
            self.assertTrue(e.pos == 1)
            self.assertTrue(e.left == "h")
            self.assertTrue(e.right == "ello")
            self.assertTrue(str(e) ==
                            "ParserError: expected test at [1]")
            last_e = e
        # called with no argument re-raises the previous most advanced
        # error (based on parser pos)
        try:
            p.parser_error()
            self.fail("No parser error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e is last_e)
            self.assertTrue(p.pos == e.pos)
        p.next_char()
        # called with no argument beyond the previous most advanced
        # error (based on parser pos)
        try:
            p.parser_error()
            self.fail("No parser error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e.production == '')
            self.assertTrue(e.pos == 2)
            self.assertTrue(e.left == "he")
            self.assertTrue(e.right == "llo")
            self.assertTrue(str(e) ==
                            "ParserError: at [2]")
            last_e = e
        p.next_char()
        try:
            p.parser_error('testA')
            self.fail("No syntax error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e.production == 'testA')
            self.assertTrue(e.pos == 3)
            self.assertTrue(e.left == "hel")
            self.assertTrue(e.right == "lo")
            self.assertTrue(str(e) ==
                            "ParserError: expected testA at [3]")
            test_a = e
        try:
            p.parser_error('testB')
            self.fail("No syntax error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e.production == 'testB')
            self.assertTrue(e.pos == 3)
            self.assertTrue(e.left == "hel")
            self.assertTrue(e.right == "lo")
            self.assertTrue(str(e) ==
                            "ParserError: expected testB at [3]")
        p.setpos(1)
        try:
            p.parser_error('testC')
            self.fail("No syntax error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e.production == 'testC')
            self.assertTrue(e.pos == 1)
            self.assertTrue(e.left == "h")
            self.assertTrue(e.right == "ello")
            self.assertTrue(str(e) ==
                            "ParserError: expected testC at [1]")
        # most advanced error now test_a or test_b, we return the first
        try:
            p.parser_error()
            self.fail("No parser error raised")
        except unicode5.ParserError as e:
            self.assertTrue(e is test_a)
            self.assertTrue(p.pos == e.pos)

    def test_require_production(self):
        p = unicode5.BasicParser("hello")
        x = object()
        self.assertTrue(p.require_production(x, "object") is x)
        self.assertTrue(p.require_production(x) is x)
        self.assertTrue(p.require_production(False, "Boolean") is False)
        self.assertTrue(p.require_production(0, "zero") == 0)
        try:
            p.require_production(None, "something")
            self.fail("None failed to raise ParserError")
        except unicode5.ParserError:
            pass

    def test_require_production_end(self):
        p = unicode5.BasicParser("hello")
        x = object()
        try:
            p.require_production_end(x, "something")
            self.fail("None failed to raise ParserError")
        except unicode5.ParserError:
            pass
        p.setpos(5)
        try:
            self.assertTrue(p.require_production_end(x, "object") is x)
        except unicode5.ParserError:
            self.fail("ParserError raised at end")
        try:
            p.require_production_end(None, "something")
            self.fail("None failed to raise ParserError")
        except unicode5.ParserError:
            pass

    def test_parse_production(self):
        p = unicode5.BasicParser("hello")
        x = object()
        self.assertTrue(
            p.parse_production(p.require_production, x, production="object"))
        self.assertFalse(
            p.parse_production(p.require_production, None,
                               production="something"))

    def test_peek(self):
        p = unicode5.BasicParser("hello")
        self.assertTrue(p.peek(4) == "hell")
        self.assertTrue(p.peek(0) == "")
        self.assertTrue(p.peek(6) == "hello")
        p.next_char()
        self.assertTrue(p.peek(4) == "ello")
        self.assertTrue(p.peek(0) == "")
        self.assertTrue(p.peek(6) == "ello")

    def test_match_end(self):
        p = unicode5.BasicParser("hello")
        for i in range3(5):
            self.assertFalse(p.match_end())
            p.next_char()
        self.assertTrue(p.match_end())

    def test_require_end(self):
        p = unicode5.BasicParser("hello")
        for i in range3(5):
            try:
                p.require_end()
                self.fail("require_end failed to raise exception")
            except unicode5.ParserError as e:
                self.assertTrue(e.production == ul("end"))
            p.next_char()
        p.require_end()

    def test_match(self):
        p = unicode5.BasicParser(ul("hello"))
        p.next_char()
        save_pos = p.pos
        self.assertTrue(p.match(ul("ell")))
        self.assertTrue(p.pos == save_pos)
        self.assertFalse(p.match(ul("elL")))
        self.assertTrue(p.pos == save_pos)
        self.assertFalse(p.match(ul("hell")))
        self.assertTrue(p.pos == save_pos)
        p = unicode5.BasicParser(b"hello")
        p.next_char()
        self.assertTrue(p.match(b"ell"))
        self.assertFalse(p.match(b"elL"))
        self.assertFalse(p.match(b"hell"))

    def test_parse(self):
        p = unicode5.BasicParser(ul("hello"))
        p.next_char()
        match = ul("ell")
        save_pos = p.pos
        self.assertTrue(p.parse(match) == match)
        self.assertTrue(p.pos == save_pos + 3)
        p.setpos(save_pos)
        self.assertTrue(p.parse(ul("elL")) is None)
        self.assertTrue(p.pos == save_pos)
        self.assertTrue(p.parse(ul("hell")) is None)
        self.assertTrue(p.pos == save_pos)
        p = unicode5.BasicParser(b"hello")
        p.next_char()
        save_pos = p.pos
        self.assertTrue(p.parse(b"ell") == b"ell")
        p.setpos(save_pos)
        self.assertTrue(p.parse(b"elL") is None)
        self.assertTrue(p.pos == save_pos)
        self.assertTrue(p.parse(b"hell") is None)
        self.assertTrue(p.pos == save_pos)

    def test_require(self):
        p = unicode5.BasicParser(ul("hello"))
        p.next_char()
        match = ul("ell")
        save_pos = p.pos
        result = p.require(match)
        self.assertTrue(result == match, result)
        self.assertTrue(p.pos == save_pos + 3)
        p.setpos(save_pos)
        try:
            p.require(ul("elL"))
            self.fail("match string")
        except unicode5.ParserError as e:
            self.assertTrue(str(e) == "ParserError: expected elL at [1]",
                            str(e))
            pass
        try:
            p.require(ul("elL"), "mixed")
            self.fail("false match")
        except unicode5.ParserError as e:
            self.assertTrue(str(e) == "ParserError: expected mixed at [1]",
                            str(e))
            pass
        self.assertTrue(p.pos == save_pos)
        # binary tests
        p = unicode5.BasicParser(b"hello")
        p.next_char()
        save_pos = p.pos
        self.assertTrue(p.require(b"ell") == b"ell")
        p.setpos(save_pos)
        try:
            p.require(b"elL")
            self.fail("false match")
        except unicode5.ParserError as e:
            self.assertTrue(str(e) == "ParserError: expected b'elL' at [1]",
                            str(e))
            pass
        self.assertTrue(p.pos == save_pos)

    def test_match_insensitive(self):
        p = unicode5.BasicParser(ul("heLLo"))
        p.next_char()
        save_pos = p.pos
        self.assertTrue(p.match_insensitive(ul("ell")))
        self.assertTrue(p.pos == save_pos)
        self.assertFalse(p.match_insensitive(ul("hell")))
        self.assertTrue(p.pos == save_pos)
        p = unicode5.BasicParser(b"heLLo")
        p.next_char()
        self.assertTrue(p.match_insensitive(b"ell"))
        self.assertFalse(p.match_insensitive(b"hell"))

    def test_parse_insensitive(self):
        p = unicode5.BasicParser(ul("heLLo"))
        p.next_char()
        match = ul("ell")
        save_pos = p.pos
        self.assertTrue(p.parse_insensitive(match) == ul("eLL"))
        self.assertTrue(p.pos == save_pos + 3)
        p.setpos(save_pos)
        self.assertTrue(p.parse_insensitive(ul("hell")) is None)
        self.assertTrue(p.pos == save_pos)
        p = unicode5.BasicParser(b"heLLo")
        p.next_char()
        save_pos = p.pos
        self.assertTrue(p.parse_insensitive(b"ell") == b"eLL")
        p.setpos(save_pos)
        self.assertTrue(p.parse_insensitive(b"hell") is None)
        self.assertTrue(p.pos == save_pos)

    def test_parse_until(self):
        p = unicode5.BasicParser(ul("hello"))
        self.assertTrue(p.parse_until(ul("ell")) == ul("h"))
        self.assertTrue(p.pos == 1)
        self.assertTrue(p.parse_until(ul("elL")) == ul("ello"))
        self.assertTrue(p.pos == 5)
        p.setpos(0)
        self.assertTrue(p.parse_until(ul("hell")) is ul(""))
        self.assertTrue(p.pos == 0)
        # binary
        p = unicode5.BasicParser(b"hello")
        self.assertTrue(p.parse_until(b"ell") == b"h")
        self.assertTrue(p.pos == 1)
        self.assertTrue(p.parse_until(b"elL") == b"ello")
        self.assertTrue(p.pos == 5)
        p.setpos(0)
        self.assertTrue(p.parse_until(b"hell") is b"")
        self.assertTrue(p.pos == 0)

    def test_match_one(self):
        p = unicode5.BasicParser(ul("hello"))
        self.assertTrue(p.match_one(ul("hello")))
        self.assertTrue(p.match_one(ul("h")))
        self.assertFalse(p.match_one(ul("e")))
        p = unicode5.BasicParser(b"hello")
        self.assertTrue(p.match_one(b"hello"))
        self.assertTrue(p.match_one(b"h"))
        self.assertFalse(p.match_one(b"e"))

    def test_parse_one(self):
        p = unicode5.BasicParser(ul("hello"))
        self.assertTrue(p.parse_one(ul("hello")) == ul("h"))
        self.assertTrue(p.pos == 1)
        p.setpos(0)
        self.assertTrue(p.parse_one(ul("h")) == ul("h"))
        self.assertTrue(p.pos == 1)
        p.setpos(0)
        self.assertTrue(p.parse_one(ul("e")) is None)
        self.assertTrue(p.pos == 0)
        p = unicode5.BasicParser(b"hello")
        self.assertTrue(p.parse_one(b"olleh") == byte(b"h"))
        self.assertTrue(p.pos == 1)
        p.setpos(0)
        self.assertTrue(p.parse_one(b"h") == byte(b"h"))
        p.setpos(0)
        self.assertTrue(p.parse_one(b"e") is None)

    def test_match_digit(self):
        p = unicode5.BasicParser(ul("2p"))
        self.assertTrue(p.match_digit())
        p.next_char()
        self.assertFalse(p.match_digit())
        p.next_char()
        self.assertFalse(p.match_digit())
        # test Arabic digits, should not match!
        p = unicode5.BasicParser(
            u8(b'\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5'
               b'\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9'))
        for i in range3(10):
            self.assertFalse(p.match_digit())
            p.next_char()
        p = unicode5.BasicParser(b"2p")
        self.assertTrue(p.match_digit())
        p.next_char()
        self.assertFalse(p.match_digit())
        p.next_char()
        self.assertFalse(p.match_digit())

    def test_parse_digit(self):
        p = unicode5.BasicParser(ul("2p"))
        self.assertTrue(p.parse_digit() == ul("2"))
        self.assertTrue(p.pos == 1)
        self.assertTrue(p.parse_digit() is None)
        p.next_char()
        self.assertTrue(p.parse_digit() is None)
        # test Arabic digits, should not parse!
        p = unicode5.BasicParser(
            u8(b'\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5'
               b'\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9'))
        for i in range3(10):
            self.assertTrue(p.parse_digit() is None)
            p.next_char()
        # test binary forms
        p = unicode5.BasicParser(b"2p")
        self.assertTrue(p.parse_digit() == byte(b"2"))
        self.assertTrue(p.parse_digit() is None)
        p.next_char()
        self.assertTrue(p.parse_digit() is None)

    def test_parse_digit_value(self):
        p = unicode5.BasicParser(ul("2p"))
        self.assertTrue(p.parse_digit_value() == 2)
        self.assertTrue(p.pos == 1)
        self.assertTrue(p.parse_digit_value() is None)
        p.next_char()
        self.assertTrue(p.parse_digit_value() is None)
        # test Arabic digits, should not parse!
        p = unicode5.BasicParser(
            u8(b'\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5'
               b'\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9'))
        for i in range3(10):
            self.assertTrue(p.parse_digit_value() is None)
            p.next_char()
        # test binary forms
        p = unicode5.BasicParser(b"2p")
        self.assertTrue(p.parse_digit_value() == 2)
        self.assertTrue(p.parse_digit_value() is None)
        p.next_char()
        self.assertTrue(p.parse_digit_value() is None)

    def test_parse_digits(self):
        p = unicode5.BasicParser(ul("23p"))
        # min value of 0
        self.assertTrue(p.parse_digits(0) == ul("23"))
        self.assertTrue(p.pos == 2)
        # min value of 2, should fail
        p.setpos(1)
        self.assertTrue(p.parse_digits(2) is None)
        # shouldn't move the parser
        self.assertTrue(p.pos == 1)
        # min value of 0, should throw an error
        try:
            p.parse_digits(-1)
            self.fail("min=-1 didn't raise exception")
        except ValueError:
            # and it shouldn't move the parser
            self.assertTrue(p.pos == 1)
        # min value > max, should throw an error
        try:
            p.parse_digits(3, 1)
            self.fail("min > max didn't raise exception")
        except ValueError:
            # and it shouldn't move the parser
            self.assertTrue(p.pos == 1)
        # check we can exceed ordinary integer sizes
        istr = ul("123456789" + "0" * 256)
        p = unicode5.BasicParser(istr)
        self.assertTrue(len(p.parse_digits(0, 256)) == 256)
        # and check that runs of 0 don't mean a thing
        self.assertTrue(p.parse_digits(0, 256) == ul("000000000"))
        # test Arabic digits, should not parse!
        p = unicode5.BasicParser(
            u8(b'\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5'
               b'\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9'))
        for i in range3(10):
            self.assertTrue(p.parse_digits(1) is None)
            p.next_char()
        # test binary forms
        p = unicode5.BasicParser(b"234p")
        # unlike parse_digit we return a string, even if only one digit
        self.assertTrue(p.parse_digits(1, 1) == b"2")
        self.assertTrue(p.parse_digits(1) == b"34")
        p.next_char()
        self.assertTrue(p.parse_digits(1) is None)
        self.assertTrue(p.parse_digits(0) == b"")

    def test_parse_integer(self):
        p = unicode5.BasicParser(ul("23p"))
        # all defaults, unbounded
        self.assertTrue(p.parse_integer() == 23)
        self.assertTrue(p.pos == 2)
        p.setpos(1)
        # provide a minimum value
        self.assertTrue(p.parse_integer(4) is None)
        self.assertTrue(p.parse_integer(2) == 3)
        p.setpos(1)
        # provide a minimum and maximum value
        self.assertTrue(p.parse_integer(0, 2) is None)
        self.assertTrue(p.parse_integer(1, 4) == 3)
        p.setpos(0)
        # min value < 0, should throw an error
        try:
            p.parse_integer(-1)
            self.fail("min = -1 didn't raise exception")
        except ValueError:
            # and it shouldn't move the parser
            self.assertTrue(p.pos == 0)
        # min value > max, should throw an error
        try:
            p.parse_integer(3, 1)
            self.fail("min > max didn't raise exception")
        except ValueError:
            # and it shouldn't move the parser
            self.assertTrue(p.pos == 0)
        # check we can exceed ordinary integer sizes
        istr = ul("123456789" + "0" * 256)
        p = unicode5.BasicParser(istr)
        # test max digits
        self.assertTrue(p.parse_integer(0, None, 10) == 1234567890)
        # check wide zeros
        self.assertTrue(p.parse_integer(0, None, 10) == 0)
        self.assertTrue(p.pos == 20)
        p.setpos(0)
        # check large numbers
        self.assertTrue(p.parse_integer(0, None, 15) == 123456789000000)
        # test Arabic digits, should not parse!
        p = unicode5.BasicParser(
            u8(b'\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5'
               b'\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9'))
        for i in range3(10):
            self.assertTrue(p.parse_integer() is None)
            p.next_char()
        # test binary forms
        p = unicode5.BasicParser(b"234p")
        self.assertTrue(p.parse_integer(max_digits=1) == 2)
        self.assertTrue(p.parse_integer(0, 2) is None)
        self.assertTrue(p.parse_integer() == 34)
        p.next_char()
        self.assertTrue(p.parse_integer() is None)

    def test_match_hex_digit(self):
        p = unicode5.BasicParser(
            u8(b"0123456789abcdefghijklmnopqrstuvwxyz"
               b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
               b"\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5"
               b"\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9"))
        result = []
        while p.the_char is not None:
            if p.match_hex_digit():
                result.append(p.the_char)
            p.next_char()
        self.assertTrue(ul('').join(result) ==
                        ul('0123456789abcdefABCDEF'))
        # and now binary
        p = unicode5.BasicParser(
            b"0123456789abcdefghijklmnopqrstuvwxyz"
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        result = []
        while p.the_char is not None:
            if p.match_hex_digit():
                result.append(p.the_char)
            p.next_char()
        self.assertTrue(join_bytes(result) ==
                        b'0123456789abcdefABCDEF')

    def test_parse_hex_digit(self):
        p = unicode5.BasicParser(
            u8(b"0123456789abcdefghijklmnopqrstuvwxyz"
               b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
               b"\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5"
               b"\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9"))
        result = []
        while p.the_char is not None:
            digit = p.parse_hex_digit()
            if digit is not None:
                result.append(digit)
            else:
                p.next_char()
        self.assertTrue(ul('').join(result) ==
                        ul('0123456789abcdefABCDEF'))
        # and now binary
        p = unicode5.BasicParser(
            b"0123456789abcdefghijklmnopqrstuvwxyz"
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        result = []
        while p.the_char is not None:
            digit = p.parse_hex_digit()
            if digit is not None:
                result.append(digit)
            else:
                p.next_char()
        self.assertTrue(join_bytes(result) ==
                        b'0123456789abcdefABCDEF')

    def test_parse_hex_digits(self):
        src = ul("23.FG.fg.0.00.abcdefABCDEF0123456789")
        p = unicode5.BasicParser(src)
        pb = unicode5.BasicParser(src.encode('ascii'))
        # min value of 0, should throw an error
        try:
            p.parse_hex_digits(-1)
            self.fail("min=-1 didn't raise exception")
        except ValueError:
            # and it shouldn't move the parser
            self.assertTrue(p.pos == 0)
        # min value > max, should throw an error
        try:
            p.parse_hex_digits(3, 1)
            self.fail("min > max didn't raise exception")
        except ValueError:
            # and it shouldn't move the parser
            self.assertTrue(p.pos == 0)
        # check min value of 1
        result = [ul("23"), ul("F"), ul("f"), ul("0"), ul("00"),
                  ul("abcdefABCDEF0123456789")]
        i = 0
        while p.the_char is not None:
            resulti = p.parse_hex_digits(1)
            bresulti = pb.parse_hex_digits(1)
            if resulti is not None:
                self.assertTrue(resulti == result[i], resulti)
                self.assertTrue(bresulti == result[i].encode('ascii'),
                                bresulti)
                i += 1
            p.next_char()
            pb.next_char()
        self.assertTrue(i == len(result))
        # min value of 2
        p.setpos(0)
        pb.setpos(0)
        result = [ul("23"), ul("00"), ul("abcdefABCDEF0123456789")]
        i = 0
        while p.the_char is not None:
            resulti = p.parse_hex_digits(2)
            bresulti = pb.parse_hex_digits(2)
            if resulti is not None:
                self.assertTrue(resulti == result[i], resulti)
                self.assertTrue(bresulti == result[i].encode('ascii'),
                                bresulti)
                i += 1
            p.next_char()
            pb.next_char()
        self.assertTrue(i == len(result))
        p.setpos(0)
        pb.setpos(0)
        result = [ul("23"), ul("00"), ul("abcde"), ul("ABCDE"), ul("01234"),
                  ul("6789")]
        i = 0
        while p.the_char is not None:
            resulti = p.parse_hex_digits(2, 5)
            bresulti = pb.parse_hex_digits(2, 5)
            if resulti is not None:
                self.assertTrue(resulti == result[i], resulti)
                self.assertTrue(bresulti == result[i].encode('ascii'),
                                bresulti)
                i += 1
            p.next_char()
            pb.next_char()
        self.assertTrue(i == len(result))
        # check we can exceed ordinary integer sizes
        istr = ul("123456789aBcDeF" + "0" * 256)
        p = unicode5.BasicParser(istr)
        self.assertTrue(len(p.parse_hex_digits(1, 256)) == 256)
        # and check that runs of 0 don't mean a thing
        self.assertTrue(p.parse_hex_digits(1, 256) == ul("000000000000000"))
        # test Arabic digits, should not parse!
        p = unicode5.BasicParser(
            u8(b'\xd9\xa0\xd9\xa1\xd9\xa2\xd9\xa3\xd9\xa4\xd9\xa5'
               b'\xd9\xa6\xd9\xa7\xd9\xa8\xd9\xa9'))
        for i in range3(10):
            self.assertTrue(p.parse_hex_digits(1) is None)
            p.next_char()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
