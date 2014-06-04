#! /usr/bin/env python
import unittest
import logging

from sys import maxunicode
import string

MAX_CHAR = 0x10FFFF
if maxunicode < MAX_CHAR:
    MAX_CHAR = maxunicode

from pyslet.unicode5 import *


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(CharClassTests, 'test'),
        unittest.makeSuite(UCDTests, 'test')
    ))

from pyslet.unicode5 import *


class CharClassTests(unittest.TestCase):

    def testConstructor(self):
        c = CharClass()
        if MAX_CHAR < 0x10FFFF:
            logging.warn(
                "unicode5 tests truncated to unichr(0x%X) by narrow python build" % MAX_CHAR)
        for code in xrange(MAX_CHAR + 1):
            self.assertFalse(c.Test(unichr(code)))
        c = CharClass('a')
        self.assertTrue(self.ClassTest(c) == 'a')
        c = CharClass(('a', 'z'))
        self.assertTrue(self.ClassTest(c) == 'abcdefghijklmnopqrstuvwxyz')
        c = CharClass('abcxyz')
        self.assertTrue(
            len(c.ranges) == 2, "No range optimization: %s" % repr(c.ranges))
        self.assertTrue(self.ClassTest(c) == 'abcxyz')
        cc = CharClass(c)
        self.assertTrue(self.ClassTest(cc) == 'abcxyz')

    def testComplexConstructors(self):
        INIT_TESTS = [
            [[], ""],
            [[['a', 'z']], "abcdefghijklmnopqrstuvwxyz"],
            [[['a', 'd'], ['f', 'k']], "abcdfghijk"],
            [[['b', 'b']], "b"],
            [[['a', 'b'], ['c', 'd'], ['e', 'f'], ['g', 'h'],
              ['i', 'j'], ['k', 'k']], "abcdefghijk"],
            [[['a', 'b'], ['d', 'f'], ['h', 'h']], "abdefh"],
            [[['h', 'h'], ['d', 'f'], ['a', 'b']], "abdefh"],
        ]
        for test in INIT_TESTS:
            c = CharClass(*test[0])
            result = self.ClassTest(c)
            self.assertTrue(
                result == test[1], "CharClass test: expected %s, found %s" % (test[1], result))

    def testAdd(self):
        c = CharClass("ac")
        c.AddChar("b")
        self.assertTrue(self.ClassTest(c) == "abc", "AddChar")
        c.AddRange("b", "e")
        self.assertTrue(self.ClassTest(c) == "abcde", "AddRange")
        c.AddClass(CharClass(["m", "s"]))
        self.assertTrue(self.ClassTest(c) == "abcdemnopqrs", "AddClass")

    def testSubtraction(self):
        c = CharClass("abc")
        c.SubtractChar("b")
        result = self.ClassTest(c)
        self.assertTrue(result == "ac", "SubtractChar: %s" % result)
        c.SubtractRange("b", "d")
        self.assertTrue(self.ClassTest(c) == "a", "SubtractRange")
        TESTS = [
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
        for test in TESTS:
            c1 = CharClass(*test[0])
            c2 = CharClass(*test[1])
            c3 = CharClass(c1)
            c3.SubtractClass(c2)
            result = self.ClassTest(c3)
            self.assertTrue(
                result == test[2], "Subtract: %s - %s, found %s" % (repr(c1), repr(c2), repr(c3)))

    def testNegateCharClass(self):
        """Check the Negation function"""
        minChar = unichr(0)
        maxChar = unichr(maxunicode)
        CHAR_CLASS_TESTS = [
            [[], [[minChar, maxChar]]],
            [[['b', 'c']], [[minChar, 'a'], ['d', maxChar]]],
            [[['b', 'c'], ['e', 'f']], [
                [minChar, 'a'], ['d', 'd'], ['g', maxChar]]]
        ]
        for test in CHAR_CLASS_TESTS:
            c1 = CharClass(*test[0])
            c2 = CharClass(c1)
            c2.Negate()
            c3 = CharClass(*test[1])
            self.assertTrue(
                c2 == c3, "%s negated to %s, expected %s" % (repr(c1), repr(c2), repr(c3)))
            c2.Negate()
            self.assertTrue(
                c2 == c1, "%s double negation got %s" % (repr(c1), repr(c2)))

    def testRepresentation(self):
        REPR_TESTS = [
            [[], "CharClass()", ""],
            [[['a', 'z']], "CharClass((u'a',u'z'))", "a-z"],
            [[['a', 'd'], ['f', 'k']],
             "CharClass((u'a',u'd'), (u'f',u'k'))", "a-df-k"],
            [[['-', '-']], "CharClass(u'-')", "\\-"],
            [[['[', ']']], "CharClass((u'[',u']'))", "[-\\]"],
            [[['\\', '\\']], "CharClass(u'\\\\')", "\\\\"],
        ]
        for test in REPR_TESTS:
            c = CharClass(*test[0])
            self.assertTrue(repr(c) == test[
                            1], "CharClass repr test: expected %s, found %s" % (test[1], repr(c)))
            result = c.FormatRe()
            self.assertTrue(
                result == test[2], "CharClass Re test: expected %s, found %s" % (test[2], result))

    def ClassTest(self, cClass):
        result = []
        for c in range(ord('a'), ord('z') + 1):
            if cClass.Test(unichr(c)):
                result.append(unichr(c))
        result = string.join(result, '')
        return result


class UCDTests(unittest.TestCase):

    """Tests of the Unicode Category classes"""

    def testUCDClasses(self):
        classCc = CharClass.UCDCategory('Cc')
        classC = CharClass.UCDCategory('C')
        for code in xrange(0x20):
            self.assertTrue(classCc.Test(unichr(code)))
            self.assertTrue(classC.Test(unichr(code)))
        for code in xrange(0x7F, 0xA0):
            self.assertTrue(classCc.Test(unichr(code)))
            self.assertTrue(classC.Test(unichr(code)))
        self.assertFalse(classCc.Test(unichr(0xAD)))
        self.assertTrue(classC.Test(unichr(0xAD)))
        self.assertTrue(CharClass.UCDCategory('Cf').Test(unichr(0xAD)))

    def testUCDBlocks(self):
        classBasicLatin = CharClass.UCDBlock('Basic Latin')
        self.assertTrue(classBasicLatin is CharClass.UCDBlock(
            'basiclatin'), "block name normalization")
        for code in xrange(0x80):
            self.assertTrue(classBasicLatin.Test(unichr(code)))
        self.assertFalse(classBasicLatin.Test(unichr(0x80)))
        # randomly pick one of the other blocks
        classBasicLatin = CharClass.UCDBlock('Arrows')
        self.assertFalse(classBasicLatin.Test(unichr(0x2150)))
        self.assertTrue(classBasicLatin.Test(unichr(0x2190)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
