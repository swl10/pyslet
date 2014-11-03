#! /usr/bin/env python

import unittest
from sys import maxunicode
import random
from pyslet.xsdatatypes20041028 import *


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XSDatatypes20041028Tests, 'test'),
        unittest.makeSuite(XSDatatypesBooleanTests, 'test'),
        unittest.makeSuite(XSRegularExpressionTests, 'test'),
        unittest.makeSuite(XSRegularExpressionParserTests, 'test')
    ))

from pyslet.xsdatatypes20041028 import *


class XSDatatypes20041028Tests(unittest.TestCase):

    def testCaseConstants(self):
        self.assertTrue(XMLSCHEMA_NAMESPACE == "http://www.w3.org/2001/XMLSchema-instance",
                        "XSI namespace: %s" % XMLSCHEMA_NAMESPACE)


class XSDatatypesBooleanTests(unittest.TestCase):

    def testCaseDencode(self):
        self.assertTrue(DecodeBoolean('true') is True, 'true')
        self.assertTrue(DecodeBoolean('1') is True, '1')
        self.assertTrue(DecodeBoolean('false') is False, 'false')
        self.assertTrue(DecodeBoolean('0') is False, '0')
        self.assertTrue(DecodeBoolean(None) is None, 'None')
        try:
            DecodeBoolean('False')
            self.fail('False')
        except ValueError:
            pass
        try:
            DecodeBoolean('True')
            self.fail('True')
        except ValueError:
            pass
        try:
            DecodeBoolean('yes')
            self.fail('yes')
        except ValueError:
            pass

    def testCaseEncode(self):
        self.assertTrue(EncodeBoolean(True) == "true", 'True')
        self.assertTrue(EncodeBoolean(False) == "false", 'False')
        self.assertTrue(EncodeBoolean(1) == "true", '1')
        self.assertTrue(EncodeBoolean(0) == "false", '0')
        self.assertTrue(EncodeBoolean(['a']) == "true", 'Non-empty list')
        self.assertTrue(EncodeBoolean([]) == "false", 'Empty list')
        try:
            EncodeBoolean(None)
            self.fail('None')
        except ValueError:
            pass


class XSDatatypesDecimalTests(unittest.TestCase):

    def testCaseDecode(self):
        tests = {
            u"-1.23": -1.23,
            u"+100000.00": 100000.0,
            u"210.": 210.0,
            u"010": 10,
            u"010.": 10,
            u"01.0": 1,
            u"0.10": 0.1,
            u".010": 0.01,
            u" 1": ValueError,
            u"1,000": ValueError,
            u"0.0": 0.0,
            u"+0.0": 0.0,
            u"-0.0": 0.0,
            u"1E+2": ValueError,
            u"1e-2": ValueError,
            u"1 ": ValueError,
            u"1 000": ValueError
        }
        for src in tests.keys():
            t = tests[src]
            try:
                result = DecodeDecimal(src)
                self.assertTrue(
                    result == t, "Mismatched decimal: %s expected %s" % (repr(result), repr(t)))
            except ValueError:
                if t is ValueError:
                    pass
                else:
                    print "Failed to parse %s" % repr(src)
                    raise

    def testCaseEncode(self):
        tests = {
            -1.23: "-1.23",
            100000.0: u"100000.0",
            210: u"210.0",
            10: u"10.0",
                -1: u"-1.0",
            0.01: u"0.01",
            0.1: u"0.1",
            0: "0.0",
            0.1: "0.1",
            0.01: "0.01",
            0.001: "0.001",
            0.0001: "0.0001",
            0.00001: "0.00001",
            0.000001: "0.000001",
            0.0000001: "0.0000001",
            1E-10: "0.0000000001",
            1E-12: "0.000000000001",
            1E-14: "0.00000000000001",
            1E-16: "0.0000000000000001",
            1.23456789E-32: "0.0000000000000000000000000000000123456789",
            1.0000001: "1.0000001",
            1.000001: "1.000001",
            1.00001: "1.00001",
                -9: "-9.0",
                -9999999999: "-9999999999.0",
                -999999999999: "-999999999999.0",
                -99999999999999: "-99999999999999.0",
        }
        for src in tests.keys():
            try:
                result = EncodeDecimal(src)
                t = tests[src]
                self.assertTrue(
                    result == t, "Mismatched decimal: %s expected %s" % (repr(result), repr(t)))
            except ValueError:
                print "Failed to encode %s" % repr(src)
                raise


class XSDatatypesDoubleTests(unittest.TestCase):

    def testCaseDecode(self):
        tests = {
            u"-1.23": -1.23E0,
            u"+100000.00": 100000.0,
            u"210.": 210.0,
            u"010": 10,
            u"010.": 10,
            u"01.0": 1,
            u"0.10": 0.1,
            u".010": 0.01,
            u" 1": ValueError,
            u"1,000": ValueError,
            u"0.0": 0.0,
            u"+0.0": 0.0,
            u"-0.0": 0.0,
            u"1E+2": 100.0,
            u"1e-2": 0.01,
            u"1 ": ValueError,
            u"1 000": ValueError
        }
        for src in tests.keys():
            t = tests[src]
            try:
                result = DecodeDouble(src)
                self.assertTrue(
                    result == t, "Mismatched decimal: %s expected %s" % (repr(result), repr(t)))
            except ValueError:
                if t is ValueError:
                    pass
                else:
                    print "Failed to parse %s" % repr(src)
                    raise

    def testCaseEncode(self):
        tests = {
            -1.23: "-1.23E0",
            100000.0: u"1.0E5",
            210: u"2.1E2",
            10: u"1.0E1",
                -1: u"-1.0E0",
            0.01: u"1.0E-2",
            0.1: u"1.0E-1",
            0: "0.0E0",
            0.1: "1.0E-1",
            0.01: "1.0E-2",
            0.001: "1.0E-3",
            0.0001: "1.0E-4",
            0.00001: "1.0E-5",
            0.000001: "1.0E-6",
            0.0000001: "1.0E-7",
            1.0000001: "1.0000001E0",
            1.000001: "1.000001E0",
            1.00001: "1.00001E0",
                -9: "-9.0E0",
                -9999999999: "-9.999999999E9",
                -99999999999: "-9.9999999999E10",
                -999999999999: "-9.99999999999E11",
                -9999999999999: "-9.999999999999E12",
                -99999999999999: "-9.9999999999999E13",
        }
        for src in tests.keys():
            try:
                result = EncodeDouble(src)
                t = tests[src]
                self.assertTrue(
                    result == t, "Mismatched decimal: %s expected %s" % (repr(result), repr(t)))
            except ValueError:
                print "Failed to encode %s" % repr(src)
                raise


class XSRegularExpressionTests(unittest.TestCase):

    def testCaseConstructor(self):
        r = RegularExpression(".*")
        self.assertTrue(r.src == ".*", "Source still available")


class XSRegularExpressionParserTests(unittest.TestCase):

    def testCaseConstructor(self):
        p = RegularExpressionParser(u".*")
        self.assertTrue(p.the_char == u".")
        self.assertTrue(p.pos == 0)
        p.setpos(1)
        self.assertTrue(p.pos == 1)
        self.assertTrue(p.the_char == u"*")
        p.setpos(0)
        self.assertTrue(p.pos == 0)
        self.assertTrue(p.the_char == u".")
        p.next_char()
        self.assertTrue(p.the_char == u"*")
        self.assertTrue(p.pos == 1)

    def testRegExp(self):
        """::
        regExp	::=	branch ( '|' branch )*	"""
        tests = {
            u"A.*Z": u"A[^\\n\\r]*Z",
            u".*AAA.*": u"[^\\n\\r]*AAA[^\\n\\r]*"
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            t = tests[b]
            try:
                result = p.ParseRegExp()
                self.assertTrue(
                    result == t, "Mismatched regExp: %s expected %s" % (repr(result), repr(t)))
                self.assertTrue(p.the_char is None)
            except RegularExpressionError:
                if t is RegularExpressionError:
                    pass
                else:
                    print "Failed to parse %s" % repr(b)
                    raise

    def testCaseBranch(self):
        """::
        branch	::=	piece*	"""
        p = RegularExpressionParser(
            u"A[A-z-[\[-\]]](Hello(Mum)|(Dad))A{0,0}[A-Z]{0,1}(Hello){0,}B{1,}[@-\xA9]?)")
        self.assertTrue(p.ParseBranch(
        ) == u"A[A-Z_-z^](Hello(Mum)|(Dad))[A-Z]?(Hello)*B+[@-\xA9]?", "Branch")
        self.assertTrue(p.the_char == u")")

    def testCasePiece(self):
        """::
        piece	::=	atom quantifier?	"""
        tests = {
            u'A': u"A",
            u'[A-z-[\[-\]]]': u"[A-Z_-z^]",
            u'(Hello(Mum)|(Dad))': u"(Hello(Mum)|(Dad))",
            u"A{0,0}": u"",
            u'[A-Z]{0,1}': u"[A-Z]?",
            u'(Hello){0,}': u"(Hello)*",
            u'B{1,}': u"B+",
            u'[@-\xA9]?': u"[@-\xA9]?",
            u'(Bye)*': u"(Bye)*",
            u'X+': u"X+",
            u'[45]{099,}': u"[45]{99,}",
            u'(45){0}': u"",
            u'@{99}': u"@{99}",
            u'A{99,1}': RegularExpressionError,
            u'A{1,99}': u"A{1,99}",
            u'A{0,99}': u"A{,99}",
            u'A{,99}': RegularExpressionError,
            u'$': u"\\$",
            u'^': u"\\^",
            u'A{1,99': RegularExpressionError,
            u'\\{{0,1}': u"\\{?",
            u'\\??': u"\\??"
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            t = tests[b]
            try:
                result = p.ParsePiece()
                self.assertTrue(
                    result == t, "Mismatched piece: %s expected %s" % (repr(result), repr(t)))
                self.assertTrue(p.the_char is None)
            except RegularExpressionError:
                if t is RegularExpressionError:
                    pass
                else:
                    print "Failed to parse %s" % repr(b)
                    raise

    def testCaseQuantifier(self):
        """::
        quantifier	::=	[?*+] | ( '{' quantity '}' )"	"""
        tests = {
            '{0,0}': (0, 0),
            '{0,1}': (0, 1),
            '{0,}': (0, None),
            '{1,}': (1, None),
            '?': (0, 1),
            '*': (0, None),
            '+': (1, None),
            '{99,}': (99, None),
            '{0}': (0, 0),
            '{99}': (99, 99),
            '{99,1}': RegularExpressionError,
            '{1,99}': (1, 99),
            '{0,99}': (0, 99),
            '{,99}': RegularExpressionError,
            '$': RegularExpressionError,
            '{1,99': RegularExpressionError
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            t = tests[b]
            try:
                x, y = p.ParseQuantifier()
                self.assertTrue(x == t[0] and y == t[
                                1], "Mismatched quantity: %s expected %s" % (repr((x, y)), repr(t)))
                self.assertTrue(p.the_char is None)
            except RegularExpressionError:
                if t is RegularExpressionError:
                    pass
                else:
                    print "Failed to parse %s" % repr(b)
                    raise

    def testQuantity(self):
        """::
        quantity	::=	quantRange | quantMin | QuantExact
        quantRange	::=	QuantExact ',' QuantExact
        quantMin	::=	QuantExact ','		"""
        tests = {
            '0,0': (0, 0),
            '0,': (0, None),
            '99,': (99, None),
            '0': (0, 0),
            '99': (99, 99),
            '99,1': RegularExpressionError,
            '1,99': (1, 99),
            '0,99': (0, 99),
            ',99': RegularExpressionError,
            '?': RegularExpressionError,
            '*': RegularExpressionError,
            '+': RegularExpressionError
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            t = tests[b]
            try:
                x, y = p.ParseQuantity()
                self.assertTrue(x == t[0] and y == t[
                                1], "Mismatched quantity: %s expected %s" % (repr((x, y)), repr(t)))
                self.assertTrue(p.the_char is None)
            except RegularExpressionError:
                if t is RegularExpressionError:
                    pass
                else:
                    print "Failed to parse %s" % repr(b)
                    raise

    def testQuantExact(self):
        """::
        QuantExact	::=	[0-9]+	"""
        tests = {
            '0': 0,
            '1': 1,
            '9': 9,
            '01': 1,
            '010': 10,
            '020': 20,
            '20': 20,
            '99': 99
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                result = p.ParseQuantExact()
                self.assertTrue(result == tests[b], "Mismatched number: %s expected %s" % (
                    repr(result), repr(tests[b])))
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)
        p = RegularExpressionParser("x")
        try:
            cClass = p.ParseQuantExact()
            self.fail("Parsed x as QuantExact")
        except RegularExpressionError:
            pass

    def testCaseAtom(self):
        """::
        atom	::=	Char | charClass | ( '(' regExp ')' )	"""
        tests = {
            'A': u"A",
            '[A-z-[\[-\]]]': u"[A-Z_-z^]",
            '(Hello(Mum)|(Dad))': u"(Hello(Mum)|(Dad))"
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                result = p.ParseAtom()
                self.assertTrue(
                    result == tests[b], "Mismatched atom: %s expected %s" % (repr(result), repr(b)))
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)

    def testCaseIsChar(self):
        """::

        Char	::=	[^.\?*+()|#x5B#x5D]

        This definition is clearly in error.  It is missing { and }."""
        p = RegularExpressionParser(
            u"ABC.ABC\\ABC?123* !\"+#$%(&\',)-/:|;<={>@^}_`~[\xa3\xa0\xf7]")
        while p.the_char is not None:
            for c in "ABC":
                self.assertTrue(p.IsChar(), "Defaulted character +ve test")
                self.assertFalse(p.IsChar("."), "Specified character -ve test")
                p.next_char()
            self.assertFalse(p.IsChar(), "Defaulted character -ve test")
            self.assertTrue(p.IsChar("A"), "Specified character +ve test")
            p.next_char()

    def testCharClass(self):
        """::
        charClass	::=	charClassEsc | charClassExpr | WildcardEsc	"""
        tests = {
            '\\P{S}': (u"(){}", u"+<=>\u2044\u20AC"),
            '[A-z-[\[-\]]]': (u"AZaz^_`", u"[\\]@{-"),
            '.': (u"abcABC ", "\x0a\x0d")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                cClass = p.ParseCharClass()
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCharClassExpr(self):
        """::
        charClassExpr	::=	'[' charGroup ']'	"""
        tests = {
            '[a-c]': (u"abc", u"ABC-"),
            '[^\]-c]': (u"ABC-", u"]^_`abc"),
            '[A-z-[\[-\]]]': (u"AZaz^_`", u"[\\]@{-"),
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                cClass = p.ParseCharClassExpr()
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCharGroup(self):
        """::
        charGroup	::=	posCharGroup | negCharGroup | charClassSub	"""
        tests = {
            'a-c': (u"abc", u"ABC-"),
            '^a-c': (u"ABC-", u"abc"),
            '^a-z-[^A-Z]': (u"ABZ", u"`abz{@[-"),
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                cClass = p.ParseCharGroup()
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testPosCharGroup(self):
        """::
        posCharGroup	::=	( charRange | charClassEsc )+	"""
        p = RegularExpressionParser(u"\\^-b^xa-c\\?-A\\p{Sc}")
        test = u"$^_`abcx?@A\xa2\xa3\xa4\xa5"
        cClass = p.ParsePosCharGroup()
        for i in xrange(256):
            c = unichr(i)
            self.assertTrue(
                cClass.Test(c) == (c in test), "Bad test on character: %s" % repr(c))
        # The - character is a valid character range only at the beginning or
        # end of a positive character group
        p = RegularExpressionParser(u"-a-c")
        cClass = p.ParsePosCharGroup()
        p = RegularExpressionParser(u"a-c-]")
        cClass = p.ParsePosCharGroup()
        p = RegularExpressionParser(u"A-C-a-c")
        try:
            cClass = p.ParsePosCharGroup()
            self.fail("hypen accepted within range")
        except RegularExpressionError:
            pass

    def testNegCharGroup(self):
        """::
        negCharGroup	::=	'^' posCharGroup	"""
        p = RegularExpressionParser(u"^\\^-b^xa-c\\?-A\\p{Sc}")
        test = u"$^_`abcx?@A\xa2\xa3\xa4\xa5"
        cClass = p.ParseNegCharGroup()
        for i in xrange(256):
            c = unichr(i)
            self.assertTrue(
                cClass.Test(c) != (c in test), "Bad test on character: %s" % repr(c))
        p = RegularExpressionParser(u"^-a-c")
        cClass = p.ParseNegCharGroup()
        p = RegularExpressionParser(u"^a-c-]")
        cClass = p.ParseNegCharGroup()
        # The ^ character is only valid at the beginning of a positive character group if it is part of a negative character group
        # this rule is automatically honoured by the parser
        p = RegularExpressionParser(u"^A-C-a-c")
        try:
            cClass = p.ParseNegCharGroup()
            self.fail("hypen accepted within range")
        except RegularExpressionError:
            pass

    def testCharClassSub(self):
        """::
        charClassSub	::=	( posCharGroup | negCharGroup ) '-' charClassExpr	"""
        tests = {
            'a-c-[b]': (u"ac", u"`bdABC-"),
            'a-e-[b-d]': (u"ae", u"`bcdf-"),
            '^a-z-[^A-Z]': (u"ABZ", u"`abz{@[-"),
            'a-c--[b]': (u"ac-", u"`bdABC")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                cClass = p.ParseCharClassSub()
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCharRange(self):
        """::
        charRange	::=	seRange | XmlCharIncDash	"""
        p = RegularExpressionParser("^\\^-bxa-c-\\?-A")
        for match in [u"\\^", u"[_-b^]", u"x", u"[a-c]", u"-", u"[?-A]"]:
            savepos = p.pos
            cClass = p.ParseCharRange()
            self.assertTrue(
                unicode(cClass) == match, "Expected %s, found %s" % (match, unicode(cClass)))
        p = RegularExpressionParser("[")
        try:
            cClass = p.ParseCharRange()
            self.fail("Parsed [ as CharRange")
        except RegularExpressionError:
            pass

    def testCaseSERange(self):
        """seRange	::=	charOrEsc '-' charOrEsc		"""
        tests = {
            'a-c': (u"abc", u"`dABC"),
            '\\?-A': (u"?@A", u">Ba"),
            'z-\\|': (u"z{|", u"y}Z")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            try:
                cClass = p.ParseSERange()
            except RegularExpressionError:
                print "Failed to parse %s" % repr(b)
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))
        p = RegularExpressionParser("c-a")
        try:
            cClass = p.ParseSERange()
            self.fail("Failed to spot reversed range")
        except RegularExpressionError:
            pass

    def testCaseCharOrEsc(self):
        """charOrEsc	::=	XmlChar | SingleCharEsc		"""
        p = RegularExpressionParser(u"ABC\\-ABC\\[ABC\\]ABC\\\\-")
        result = []
        try:
            while p.the_char is not None:
                savepos = p.pos
                result.append(p.ParseCharOrEsc())
                self.assertFalse(p.pos == savepos, "Failed to parse character")
        except RegularExpressionError:
            pass
        self.assertTrue(p.the_char == u"-", "Incomplete parse of CharOrEsc")
        self.assertTrue(
            string.join(result, "") == "ABC-ABC[ABC]ABC\\", "Parse result")

    def testCaseIsXmlChar(self):
        """XmlChar	::=	[^\#x2D#x5B#x5D]	"""
        p = RegularExpressionParser(u"ABC-ABC[ABC]ABC\\")
        while p.the_char is not None:
            for c in "ABC":
                self.assertTrue(p.IsXmlChar(), "Defaulted character +ve test")
                self.assertFalse(
                    p.IsXmlChar("\\"), "Specified character -ve test")
                p.next_char()
            self.assertFalse(p.IsXmlChar(), "Defaulted character -ve test")
            self.assertTrue(p.IsXmlChar("A"), "Specified character +ve test")
            p.next_char()

    def testCaseIsXmlCharIncDash(self):
        """XmlCharIncDash	::=	[^\#x5B#x5D]	"""
        p = RegularExpressionParser(u"ABC[ABC]ABC\\")
        while p.the_char is not None:
            for c in "ABC":
                self.assertTrue(
                    p.IsXmlCharIncDash(), "Defaulted character +ve test")
                self.assertFalse(
                    p.IsXmlCharIncDash("\\"), "Specified character -ve test")
                p.next_char()
            self.assertFalse(
                p.IsXmlCharIncDash(), "Defaulted character -ve test")
            self.assertTrue(
                p.IsXmlCharIncDash("A"), "Specified character +ve test")
            p.next_char()

    def testCharClassEsc(self):
        """::
        charClassEsc	::=	( SingleCharEsc | MultiCharEsc | catEsc | complEsc )	"""
        tests = {
            '\\?': (u"?", "\\"),
            '\\d': (u"123\u0661\u0662\u0663", u"ABC\u2081\u2082\u2083"),
            '\\p{S}': (u"+<=>\u2044\u20AC", u"(){}"),
            '\\P{S}': (u"(){}", u"+<=>\u2044\u20AC")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            cClass = p.ParseCharClassEsc()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCaseSingleCharEsc(self):
        """::
        SingleCharEsc	   ::=   	'\' [nrt\|.?*+(){}#x2D#x5B#x5D#x5E]		"""
        tests = {
            '\\n': u"\x0A",
            '\\r': u"\x0D",
            '\\t': u"\x09",
            '\\\\': u"\\",
            '\\|': u"|",
            '\\.': u".",
            '\\?': u"?",
            '\\*': u"*",
            '\\+': u"+",
            '\\(': u"(",
            '\\)': u")",
            '\\{': u"{",
            '\\}': u"}",
            '\\-': u"-",
            '\\[': u"[",
            '\\]': u"]",
            '\\^': u"^"
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            c = p.ParseSingleCharEsc()
            self.assertTrue(p.the_char is None)
            t = tests[b]
            self.assertTrue(c == t, "%s single char found %s" %
                            (repr(t), repr(c)))
        try:
            p = RegularExpressionParser("\\b")
            c = p.ParseSingleCharEsc()
            self.assertFalse(
                p.the_char is None, "Undetected bad single character escape: %s" % repr(c))
        except RegularExpressionError:
            pass

    def testCaseCatEsc(self):
        """::
        catEsc	::=	'\p{' charProp '}'	"""
        tests = {
            # positive and negative tests
            '\\p{Nd}': (u"123\u06F1\u06F2\u06F3", u"ABC\u2155\u2156\u2157\u2158"),
            '\\p{S}': (u"+<=>\u2044\u20AC", u"(){}"),
            '\\p{IsBasicLatin}': (u"ABC", u"\xc0\xdf\xa9")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            cClass = p.ParseCatEsc()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCaseComplEsc(self):
        """::
        complEsc ::= '\P{' charProp '}'	"""
        tests = {
            # positive and negative tests
            '\\P{Nd}': (u"ABC\u2155\u2156\u2157\u2158", u"123\u06F1\u06F2\u06F3"),
            '\\P{S}': (u"(){}", u"+<=>\u2044\u20AC"),
            '\\P{IsBasicLatin}': (u"\xc0\xdf\xa9", u"ABC")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            cClass = p.ParseComplEsc()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCaseCharProp(self):
        """::
        charProp ::= IsCategory | IsBlock"""
        tests = {
            # positive and negative tests
            'Nd': (u"123\u06F1\u06F2\u06F3", u"ABC\u2155\u2156\u2157\u2158"),
            'S': (u"+<=>\u2044\u20AC", u"(){}"),
            'IsBasicLatin': (u"ABC", u"\xc0\xdf\xa9"),
            'IsLatin-1Supplement': (u"\xc0\xdf\xa9", u"ABC"),
            'IsCurrencySymbols': (u"\u20a4\u20a9\u20ac", u"\x24\xa2\xa3"),
            'IsNumberForms': (u"\u2155\u2156\u2157\u2158", u"1/5 2/5 3/5 4/5")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            cClass = p.ParseCharProp()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCaseIsCategory(self):
        """::
        IsCategory	::=	Letters | Marks | Numbers | Punctuation | Separators | Symbols | Others
        Letters		::=	'L' [ultmo]?
        Marks		::=	'M' [nce]?
        Numbers		::=	'N' [dlo]?
        Punctuation	::=	'P' [cdseifo]?
        Separators	::=	'Z' [slp]?
        Symbols		::=	'S' [mcko]?
        Others		::=	'C' [cfon]?"""
        tests = ["L", "Lu", "Ll", "Lt", "Lm", "Lo", "M", "Mn", "Mc", "Me",
                 "N", "Nd", "Nl", "No", "P", "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "Z", "Zs", "Zl", "Zp",
                 "S", "Sm", "Sc", "Sk", "So", "C", "Cc", "Cf", "Co", "Cn"]
        bad = ["A", "Za"]
        for s in tests:
            p = RegularExpressionParser(s)
            self.assertTrue(
                isinstance(p.ParseIsCategory(), CharClass), "Missing category: %s" % s)
            self.assertTrue(
                p.the_char is None, "Incomplete parse of category: %s" % s)
        for s in bad:
            p = RegularExpressionParser(s)
            try:
                p.ParseIsCategory()
                self.assertFalse(
                    p.the_char is None, "Undetected bad category: %s" % s)
            except RegularExpressionError:
                pass
        tests = {
            # positive and negative tests
            'Nd': (u"123\u06F1\u06F2\u06F3", u"ABC\u2155\u2156\u2157\u2158"),
            'S': (u"+<=>\u2044\u20AC", u"(){}")
        }
        for b in tests.keys():
            p = RegularExpressionParser(b)
            cClass = p.ParseIsCategory()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in %s" % (repr(c), b))

    def testCaseIsBlock(self):
        """::
        IsBlock	   ::=   	'Is' [a-zA-Z0-9#x2D]+"""
        tests = {
            # positive and negative tests
            'BasicLatin': (u"ABC", u"\xc0\xdf\xa9"),
            'Latin-1Supplement': (u"\xc0\xdf\xa9", u"ABC"),
            'CurrencySymbols': (u"\u20a4\u20a9\u20ac", u"\x24\xa2\xa3"),
            'NumberForms': (u"\u2155\u2156\u2157\u2158", u"1/5 2/5 3/5 4/5")
        }
        for b in tests.keys():
            p = RegularExpressionParser(u"Is" + b)
            cClass = p.ParseIsBlock()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cClass.Test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cClass.Test(c), "%s in Is%s" % (repr(c), b))
        p = RegularExpressionParser(u"IsNumberFoams")
        try:
            cClass = p.ParseIsBlock()
            self.fail("IsNumberFoams")
        except RegularExpressionError:
            pass

    def testCaseMultiCharEsc(self):
        """::
        MultiCharEsc ::= '\' [sSiIcCdDwW]"""
        tests = {
            # positive and negative tests
            's': (u"\x09\x0A\x0D ", u"ABC"),
            'i': (u"ABC_:", u"-123"),
            'c': (u"ABC_:-_123", u"@<>?"),
            'd': (u"123\u0661\u0662\u0663", u"ABC\u2081\u2082\u2083"),
            'w': (u"ABC", u"!\u037E \u2002\x0C"),
        }
        for c in tests.keys():
            p1 = RegularExpressionParser(u"\\" + c)
            cClass1 = p1.ParseMultiCharEsc()
            self.assertTrue(p1.pos == 2)
            p2 = RegularExpressionParser(u"\\" + c.upper())
            cClass2 = p2.ParseMultiCharEsc()
            self.assertTrue(p2.pos == 2)
            t1, t2 = tests[c]
            for c1 in t1:
                self.assertTrue(
                    cClass1.Test(c1), "%s not in \\%s" % (repr(c1), c))
                self.assertFalse(
                    cClass2.Test(c1), "%s in \\%s" % (repr(c1), c.upper()))
            for c2 in t2:
                self.assertFalse(
                    cClass1.Test(c2), "%s in \\%s" % (repr(c2), c))
                self.assertTrue(cClass2.Test(c2), "%s in \\%s" %
                                (repr(c2), c.upper()))
        p = RegularExpressionParser(u"\\x")
        try:
            cClass = p.ParseMultiCharEsc()
            self.fail("\\x")
        except RegularExpressionError:
            pass

    def testCaseWildcardEsc(self):
        """::
        [37a] WildcardEsc ::= '.'"""
        p = RegularExpressionParser(u".*")
        cClass = p.ParseWildcardEsc()
        self.assertTrue(p.pos == 1)
        self.assertFalse(cClass.Test(u"\x0A"), "Line feed in .")
        self.assertFalse(cClass.Test(u"\x0D"), "Carriage return in .")
        for i in xrange(100):
            # do a few random tests
            j = random.randint(0, maxunicode)
            if j in (10, 13):
                continue
            self.assertTrue(
                cClass.Test(unichr(j)), "Random char not in . unichr(%04X)" % j)
        p = RegularExpressionParser(u"x")
        try:
            cClass = p.ParseWildcardEsc()
            self.fail(".")
        except RegularExpressionError:
            pass


if __name__ == "__main__":
    unittest.main()
