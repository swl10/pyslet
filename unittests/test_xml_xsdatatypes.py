#! /usr/bin/env python

import logging
import random
import unittest

from sys import maxunicode

import pyslet.xml.xsdatatypes as xsi

from pyslet.unicode5 import CharClass
from pyslet.py2 import character, dict_keys, range3, to_text, u8, ul


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XSDatatypes20041028Tests, 'test'),
        unittest.makeSuite(XSDatatypesBooleanTests, 'test'),
        unittest.makeSuite(XSRegularExpressionTests, 'test'),
        unittest.makeSuite(XSRegularExpressionParserTests, 'test')
    ))


class XSDatatypes20041028Tests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(xsi.XMLSCHEMA_NAMESPACE ==
                        "http://www.w3.org/2001/XMLSchema-instance",
                        "XSI namespace: %s" % xsi.XMLSCHEMA_NAMESPACE)


class XSDatatypesBooleanTests(unittest.TestCase):

    def test_dencode(self):
        self.assertTrue(xsi.boolean_from_str('true') is True, 'true')
        self.assertTrue(xsi.boolean_from_str('1') is True, '1')
        self.assertTrue(xsi.boolean_from_str('false') is False, 'false')
        self.assertTrue(xsi.boolean_from_str('0') is False, '0')
        self.assertTrue(xsi.boolean_from_str(None) is None, 'None')
        try:
            xsi.boolean_from_str('False')
            self.fail('False')
        except ValueError:
            pass
        try:
            xsi.boolean_from_str('True')
            self.fail('True')
        except ValueError:
            pass
        try:
            xsi.boolean_from_str('yes')
            self.fail('yes')
        except ValueError:
            pass

    def test_encode(self):
        self.assertTrue(xsi.boolean_to_str(True) == "true", 'True')
        self.assertTrue(xsi.boolean_to_str(False) == "false", 'False')
        self.assertTrue(xsi.boolean_to_str(1) == "true", '1')
        self.assertTrue(xsi.boolean_to_str(0) == "false", '0')
        self.assertTrue(xsi.boolean_to_str(['a']) == "true", 'Non-empty list')
        self.assertTrue(xsi.boolean_to_str([]) == "false", 'Empty list')
        try:
            xsi.boolean_to_str(None)
            self.fail('None')
        except ValueError:
            pass


class XSDatatypesDecimalTests(unittest.TestCase):

    def test_decode(self):
        tests = {
            "-1.23": -1.23,
            "+100000.00": 100000.0,
            "210.": 210.0,
            "010": 10,
            "010.": 10,
            "01.0": 1,
            "0.10": 0.1,
            ".010": 0.01,
            " 1": ValueError,
            "1,000": ValueError,
            "0.0": 0.0,
            "+0.0": 0.0,
            "-0.0": 0.0,
            "1E+2": ValueError,
            "1e-2": ValueError,
            "1 ": ValueError,
            "1 000": ValueError}
        for src in dict_keys(tests):
            t = tests[src]
            try:
                result = xsi.decimal_from_str(src)
                self.assertTrue(result == t,
                                "Mismatched decimal: %s expected %s" %
                                (repr(result), repr(t)))
            except ValueError:
                if t is ValueError:
                    pass
                else:
                    logging.debug("Failed to parse %s" % repr(src))
                    raise

    def test_encode(self):
        tests = {
            -1.23: "-1.23",
            100000.0: "100000.0",
            210: "210.0",
            10: "10.0",
            -1: "-1.0",
            0.01: "0.01",
            0.1: "0.1",
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
            -99999999999999: "-99999999999999.0"}
        for src in dict_keys(tests):
            try:
                result = xsi.decimal_to_str(src)
                t = tests[src]
                self.assertTrue(result == t,
                                "Mismatched decimal: %s expected %s" %
                                (repr(result), repr(t)))
            except ValueError:
                logging.debug("Failed to encode %s" % repr(src))
                raise


class XSDatatypesDoubleTests(unittest.TestCase):

    def test_decode(self):
        tests = {
            "-1.23": -1.23E0,
            "+100000.00": 100000.0,
            "210.": 210.0,
            "010": 10,
            "010.": 10,
            "01.0": 1,
            "0.10": 0.1,
            ".010": 0.01,
            " 1": ValueError,
            "1,000": ValueError,
            "0.0": 0.0,
            "+0.0": 0.0,
            "-0.0": 0.0,
            "1E+2": 100.0,
            "1e-2": 0.01,
            "1 ": ValueError,
            "1 000": ValueError
        }
        for src in dict_keys(tests):
            t = tests[src]
            try:
                result = xsi.double_from_str(src)
                self.assertTrue(result == t,
                                "Mismatched decimal: %s expected %s" %
                                (repr(result), repr(t)))
            except ValueError:
                if t is ValueError:
                    pass
                else:
                    logging.debug("Failed to parse %s" % repr(src))
                    raise

    def test_encode(self):
        tests = {
            -1.23: "-1.23E0",
            100000.0: "1.0E5",
            210: "2.1E2",
            10: "1.0E1",
            -1: "-1.0E0",
            0.01: "1.0E-2",
            0.1: "1.0E-1",
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
            -99999999999999: "-9.9999999999999E13"}
        for src in dict_keys(tests):
            try:
                result = xsi.double_to_str(src)
                t = tests[src]
                self.assertTrue(result == t,
                                "Mismatched decimal: %s expected %s" %
                                (repr(result), repr(t)))
            except ValueError:
                logging.debug("Failed to encode %s" % repr(src))
                raise


class XSRegularExpressionTests(unittest.TestCase):

    def test_constructor(self):
        r = xsi.RegularExpression(".*")
        self.assertTrue(r.src == ".*", "Source still available")


class XSRegularExpressionParserTests(unittest.TestCase):

    def test_constructor(self):
        p = xsi.RegularExpressionParser(".*")
        self.assertTrue(p.the_char == ".")
        self.assertTrue(p.pos == 0)
        p.setpos(1)
        self.assertTrue(p.pos == 1)
        self.assertTrue(p.the_char == "*")
        p.setpos(0)
        self.assertTrue(p.pos == 0)
        self.assertTrue(p.the_char == ".")
        p.next_char()
        self.assertTrue(p.the_char == "*")
        self.assertTrue(p.pos == 1)

    def test_reg_exp(self):
        """::
        regExp ::= branch ( '|' branch )* """
        tests = {
            "A.*Z": "A[^\\n\\r]*Z",
            ".*AAA.*": "[^\\n\\r]*AAA[^\\n\\r]*"
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            t = tests[b]
            try:
                result = p.require_reg_exp()
                self.assertTrue(result == t,
                                "Mismatched regExp: %s expected %s" %
                                (repr(result), repr(t)))
                self.assertTrue(p.the_char is None)
            except xsi.RegularExpressionError:
                if t is xsi.RegularExpressionParser:
                    pass
                else:
                    logging.debug("Failed to parse %s" % repr(b))
                    raise

    def test_branch(self):
        """::
        branch ::= piece* """
        p = xsi.RegularExpressionParser(
            ul("A[A-z-[\[-\]]](Hello(Mum)|(Dad))A{0,0}[A-Z]{0,1}(Hello)"
               "{0,}B{1,}[@-\xA9]?)"))
        self.assertTrue(
            p.require_branch() ==
            ul("A[A-Z_-z^](Hello(Mum)|(Dad))[A-Z]?(Hello)*B+[@-\xA9]?"),
            "Branch")
        self.assertTrue(p.the_char == ")")

    def test_piece(self):
        """::
        piece ::= atom quantifier? """
        tests = {
            'A': "A",
            '[A-z-[\[-\]]]': "[A-Z_-z^]",
            '(Hello(Mum)|(Dad))': "(Hello(Mum)|(Dad))",
            "A{0,0}": "",
            '[A-Z]{0,1}': "[A-Z]?",
            '(Hello){0,}': "(Hello)*",
            'B{1,}': "B+",
            ul('[@-\xA9]?'): ul("[@-\xA9]?"),
            '(Bye)*': "(Bye)*",
            'X+': "X+",
            '[45]{099,}': "[45]{99,}",
            '(45){0}': "",
            '@{99}': "@{99}",
            'A{99,1}': xsi.RegularExpressionParser,
            'A{1,99}': "A{1,99}",
            'A{0,99}': "A{,99}",
            'A{,99}': xsi.RegularExpressionParser,
            '$': "\\$",
            '^': "\\^",
            'A{1,99': xsi.RegularExpressionParser,
            '\\{{0,1}': "\\{?",
            '\\??': "\\??"
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            t = tests[b]
            try:
                result = p.require_piece()
                self.assertTrue(result == t,
                                "Mismatched piece: %s expected %s" %
                                (repr(result), repr(t)))
                self.assertTrue(p.the_char is None)
            except xsi.RegularExpressionError:
                if t is xsi.RegularExpressionParser:
                    pass
                else:
                    logging.debug("Failed to parse %s" % repr(b))
                    raise

    def test_quantifier(self):
        """::
        quantifier ::= [?*+] | ( '{' quantity '}' )" """
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
            '{99,1}': xsi.RegularExpressionParser,
            '{1,99}': (1, 99),
            '{0,99}': (0, 99),
            '{,99}': xsi.RegularExpressionParser,
            '$': xsi.RegularExpressionParser,
            '{1,99': xsi.RegularExpressionParser
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            t = tests[b]
            try:
                x, y = p.require_quantifier()
                self.assertTrue(x == t[0] and y == t[1],
                                "Mismatched quantity: %s expected %s" %
                                (repr((x, y)), repr(t)))
                self.assertTrue(p.the_char is None)
            except xsi.RegularExpressionError:
                if t is xsi.RegularExpressionParser:
                    pass
                else:
                    logging.debug("Failed to parse %s" % repr(b))
                    raise

    def test_quantity(self):
        """::
        quantity ::= quantRange | quantMin | QuantExact
        quantRange ::= QuantExact ',' QuantExact
        quantMin ::= QuantExact ','  """
        tests = {
            '0,0': (0, 0),
            '0,': (0, None),
            '99,': (99, None),
            '0': (0, 0),
            '99': (99, 99),
            '99,1': xsi.RegularExpressionParser,
            '1,99': (1, 99),
            '0,99': (0, 99),
            ',99': xsi.RegularExpressionParser,
            '?': xsi.RegularExpressionParser,
            '*': xsi.RegularExpressionParser,
            '+': xsi.RegularExpressionParser
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            t = tests[b]
            try:
                x, y = p.require_quantity()
                self.assertTrue(x == t[0] and y == t[1],
                                "Mismatched quantity: %s expected %s" %
                                (repr((x, y)), repr(t)))
                self.assertTrue(p.the_char is None)
            except xsi.RegularExpressionError:
                if t is xsi.RegularExpressionParser:
                    pass
                else:
                    logging.debug("Failed to parse %s" % repr(b))
                    raise

    def test_quant_exact(self):
        """::
        QuantExact ::= [0-9]+ """
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
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                result = p.require_quant_exact()
                self.assertTrue(result == tests[b],
                                "Mismatched number: %s expected %s" %
                                (repr(result), repr(tests[b])))
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)
        p = xsi.RegularExpressionParser("x")
        try:
            p.require_quant_exact()
            self.fail("Parsed x as QuantExact")
        except xsi.RegularExpressionError:
            pass

    def test_atom(self):
        """::
        atom ::= Char | charClass | ( '(' regExp ')' ) """
        tests = {
            'A': "A",
            '[A-z-[\[-\]]]': "[A-Z_-z^]",
            '(Hello(Mum)|(Dad))': "(Hello(Mum)|(Dad))"
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                result = p.require_atom()
                self.assertTrue(result == tests[b],
                                "Mismatched atom: %s expected %s" %
                                (repr(result), repr(b)))
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)

    def test_is_char(self):
        """::

        Char ::= [^.\?*+()|#x5B#x5D]

        This definition is clearly in error.  It is missing { and }."""
        p = xsi.RegularExpressionParser(
            ul("ABC.ABC\\ABC?123* !\"+#$%(&\',)-/:|;<={>@^}_`~[\xa3\xa0\xf7]"))
        while p.the_char is not None:
            for c in "ABC":
                self.assertTrue(p.is_char(), "Defaulted character +ve test")
                self.assertFalse(p.is_char("."),
                                 "Specified character -ve test")
                p.next_char()
            self.assertFalse(p.is_char(), "Defaulted character -ve test")
            self.assertTrue(p.is_char("A"), "Specified character +ve test")
            p.next_char()

    def test_char_class(self):
        """::
        charClass ::= charClassEsc | charClassExpr | WildcardEsc """
        tests = {
            '\\P{S}': ("(){}", u8(b'+<=>\xe2\x81\x84\xe2\x82\xac')),
            '[A-z-[\[-\]]]': ("AZaz^_`", "[\\]@{-"),
            '.': ("abcABC ", "\x0a\x0d")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                cclass = p.require_char_class()
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_char_class_expr(self):
        """::
        charClassExpr ::= '[' charGroup ']' """
        tests = {
            '[a-c]': ("abc", "ABC-"),
            '[^\]-c]': ("ABC-", "]^_`abc"),
            '[A-z-[\[-\]]]': ("AZaz^_`", "[\\]@{-"),
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                cclass = p.require_char_class_expr()
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_char_group(self):
        """::
        charGroup ::= posCharGroup | negCharGroup | charClassSub """
        tests = {
            'a-c': ("abc", "ABC-"),
            '^a-c': ("ABC-", "abc"),
            '^a-z-[^A-Z]': ("ABZ", "`abz{@[-"),
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                cclass = p.require_char_group()
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_pos_char_group(self):
        """::
        posCharGroup ::= ( charRange | charClassEsc )+ """
        p = xsi.RegularExpressionParser("\\^-b^xa-c\\?-A\\p{Sc}")
        test = ul("$^_`abcx?@A\xa2\xa3\xa4\xa5")
        cclass = p.require_pos_char_group()
        for i in range3(256):
            c = character(i)
            self.assertTrue(cclass.test(c) == (c in test),
                            "Bad test on character: %s" % repr(c))
        # The - character is a valid character range only at the
        # beginning or end of a positive character group
        p = xsi.RegularExpressionParser("-a-c")
        cclass = p.require_pos_char_group()
        p = xsi.RegularExpressionParser("a-c-]")
        cclass = p.require_pos_char_group()
        p = xsi.RegularExpressionParser("A-C-a-c")
        try:
            cclass = p.require_pos_char_group()
            self.fail("hypen accepted within range")
        except xsi.RegularExpressionError:
            pass

    def test_neg_char_group(self):
        """::
        negCharGroup ::= '^' posCharGroup """
        p = xsi.RegularExpressionParser("^\\^-b^xa-c\\?-A\\p{Sc}")
        test = ul("$^_`abcx?@A\xa2\xa3\xa4\xa5")
        cclass = p.require_neg_char_group()
        for i in range3(256):
            c = character(i)
            self.assertTrue(cclass.test(c) != (c in test),
                            "Bad test on character: %s" % repr(c))
        p = xsi.RegularExpressionParser("^-a-c")
        cclass = p.require_neg_char_group()
        p = xsi.RegularExpressionParser("^a-c-]")
        cclass = p.require_neg_char_group()
        # The ^ character is only valid at the beginning of a positive
        # character group if it is part of a negative character group
        # this rule is automatically honoured by the parser
        p = xsi.RegularExpressionParser("^A-C-a-c")
        try:
            cclass = p.require_neg_char_group()
            self.fail("hypen accepted within range")
        except xsi.RegularExpressionError:
            pass

    def test_char_class_sub(self):
        """::
        charClassSub ::= ( posCharGroup | negCharGroup ) '-' charClassExpr """
        tests = {
            'a-c-[b]': ("ac", "`bdABC-"),
            'a-e-[b-d]': ("ae", "`bcdf-"),
            '^a-z-[^A-Z]': ("ABZ", "`abz{@[-"),
            'a-c--[b]': ("ac-", "`bdABC")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                cclass = p.require_char_class_sub()
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_char_range(self):
        """::
        charRange ::= seRange | XmlCharIncDash """
        p = xsi.RegularExpressionParser("^\\^-bxa-c-\\?-A")
        for match in ["\\^", "[_-b^]", "x", "[a-c]", "-", "[?-A]"]:
            cclass = p.require_char_range()
            self.assertTrue(to_text(cclass) == match,
                            "Expected %s, found %s" % (match, to_text(cclass)))
        p = xsi.RegularExpressionParser("[")
        try:
            cclass = p.require_char_range()
            self.fail("Parsed [ as CharRange")
        except xsi.RegularExpressionError:
            pass

    def test_se_range(self):
        """seRange ::= charOrEsc '-' charOrEsc  """
        tests = {
            'a-c': ("abc", "`dABC"),
            '\\?-A': ("?@A", ">Ba"),
            'z-\\|': ("z{|", "y}Z")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            try:
                cclass = p.require_se_range()
            except xsi.RegularExpressionError:
                logging.debug("Failed to parse %s" % repr(b))
                raise
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))
        p = xsi.RegularExpressionParser("c-a")
        try:
            cclass = p.require_se_range()
            self.fail("Failed to spot reversed range")
        except xsi.RegularExpressionError:
            pass

    def test_char_or_esc(self):
        """charOrEsc ::= XmlChar | SingleCharEsc  """
        p = xsi.RegularExpressionParser("ABC\\-ABC\\[ABC\\]ABC\\\\-")
        result = []
        try:
            while p.the_char is not None:
                savepos = p.pos
                result.append(p.require_char_or_esc())
                self.assertFalse(p.pos == savepos, "Failed to parse character")
        except xsi.RegularExpressionError:
            pass
        self.assertTrue(p.the_char == "-", "Incomplete parse of CharOrEsc")
        self.assertTrue(
            "".join(result) == "ABC-ABC[ABC]ABC\\", "Parse result")

    def test_is_xml_char(self):
        """XmlChar ::= [^\#x2D#x5B#x5D] """
        p = xsi.RegularExpressionParser("ABC-ABC[ABC]ABC\\")
        while p.the_char is not None:
            for c in "ABC":
                self.assertTrue(p.is_xml_char(),
                                "Defaulted character +ve test")
                self.assertFalse(
                    p.is_xml_char("\\"), "Specified character -ve test")
                p.next_char()
            self.assertFalse(p.is_xml_char(), "Defaulted character -ve test")
            self.assertTrue(p.is_xml_char("A"), "Specified character +ve test")
            p.next_char()

    def test_is_xml_char_inc_dash(self):
        """XmlCharIncDash ::= [^\#x5B#x5D] """
        p = xsi.RegularExpressionParser("ABC[ABC]ABC\\")
        while p.the_char is not None:
            for c in "ABC":
                self.assertTrue(
                    p.is_xml_char_inc_dash(), "Defaulted character +ve test")
                self.assertFalse(p.is_xml_char_inc_dash("\\"),
                                 "Specified character -ve test")
                p.next_char()
            self.assertFalse(
                p.is_xml_char_inc_dash(), "Defaulted character -ve test")
            self.assertTrue(
                p.is_xml_char_inc_dash("A"), "Specified character +ve test")
            p.next_char()

    def test_char_class_esc(self):
        """::
        charClassEsc ::= ( SingleCharEsc | MultiCharEsc | catEsc | complEsc )
        """
        tests = {
            '\\?': ("?", "\\"),
            '\\d': (u8(b'123\xd9\xa1\xd9\xa2\xd9\xa3'),
                    u8(b'ABC\xe2\x82\x81\xe2\x82\x82\xe2\x82\x83')),
            '\\p{S}': (u8(b'+<=>\xe2\x81\x84\xe2\x82\xac'), "(){}"),
            '\\P{S}': ("(){}", u8(b'+<=>\xe2\x81\x84\xe2\x82\xac'))}
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            cclass = p.require_char_class_esc()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_single_char_esc(self):
        """::
        SingleCharEsc ::= '\' [nrt\|.?*+(){}#x2D#x5B#x5D#x5E] """
        tests = {
            '\\n': "\x0A",
            '\\r': "\x0D",
            '\\t': "\x09",
            '\\\\': "\\",
            '\\|': "|",
            '\\.': ".",
            '\\?': "?",
            '\\*': "*",
            '\\+': "+",
            '\\(': "(",
            '\\)': ")",
            '\\{': "{",
            '\\}': "}",
            '\\-': "-",
            '\\[': "[",
            '\\]': "]",
            '\\^': "^"
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            c = p.require_single_char_esc()
            self.assertTrue(p.the_char is None)
            t = tests[b]
            self.assertTrue(c == t, "%s single char found %s" %
                            (repr(t), repr(c)))
        try:
            p = xsi.RegularExpressionParser("\\b")
            c = p.require_single_char_esc()
            self.assertFalse(
                p.the_char is None,
                "Undetected bad single character escape: %s" % repr(c))
        except xsi.RegularExpressionError:
            pass

    def test_cat_esc(self):
        """::
        catEsc ::= '\p{' charProp '}' """
        tests = {
            # positive and negative tests
            '\\p{Nd}': (u8(b'123\xdb\xb1\xdb\xb2\xdb\xb3'),
                        u8(b'ABC\xe2\x85\x95\xe2\x85\x96\xe2\x85'
                           b'\x97\xe2\x85\x98')),
            '\\p{S}': (u8(b'+<=>\xe2\x81\x84\xe2\x82\xac'), "(){}"),
            '\\p{IsBasicLatin}': ("ABC", ul("\xc0\xdf\xa9"))
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            cclass = p.require_cat_esc()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_compl_esc(self):
        """::
        complEsc ::= '\P{' charProp '}' """
        tests = {
            # positive and negative tests
            '\\P{Nd}':
            (u8(b'ABC\xe2\x85\x95\xe2\x85\x96\xe2\x85\x97\xe2\x85\x98'),
             u8(b'123\xdb\xb1\xdb\xb2\xdb\xb3')),
            '\\P{S}': ("(){}", u8(b'+<=>\xe2\x81\x84\xe2\x82\xac')),
            '\\P{IsBasicLatin}': (ul("\xc0\xdf\xa9"), "ABC")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            cclass = p.require_compl_esc()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_char_prop(self):
        """::
        charProp ::= IsCategory | IsBlock"""
        tests = {
            # positive and negative tests
            'Nd': (u8(b'123\xdb\xb1\xdb\xb2\xdb\xb3'),
                   u8(b'ABC\xe2\x85\x95\xe2\x85\x96\xe2\x85\x97\xe2\x85\x98')),
            'S': (u8(b'+<=>\xe2\x81\x84\xe2\x82\xac'), "(){}"),
            'IsBasicLatin': ("ABC", ul("\xc0\xdf\xa9")),
            'IsLatin-1Supplement': (ul("\xc0\xdf\xa9"), "ABC"),
            'IsCurrencySymbols': (u8(b'\xe2\x82\xa4\xe2\x82\xa9\xe2\x82\xac'),
                                  ul("\x24\xa2\xa3")),
            'IsNumberForms': (
                u8(b'\xe2\x85\x95\xe2\x85\x96\xe2\x85\x97\xe2\x85\x98'),
                "1/5 2/5 3/5 4/5")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            cclass = p.require_char_prop()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_is_category(self):
        """::
        IsCategory ::= Letters | Marks | Numbers | Punctuation |
            Separators | Symbols | Others
        Letters  ::= 'L' [ultmo]?
        Marks  ::= 'M' [nce]?
        Numbers  ::= 'N' [dlo]?
        Punctuation ::= 'P' [cdseifo]?
        Separators ::= 'Z' [slp]?
        Symbols  ::= 'S' [mcko]?
        Others  ::= 'C' [cfon]?"""
        tests = ["L", "Lu", "Ll", "Lt", "Lm", "Lo", "M", "Mn", "Mc", "Me",
                 "N", "Nd", "Nl", "No", "P", "Pc", "Pd", "Ps", "Pe", "Pi",
                 "Pf", "Po", "Z", "Zs", "Zl", "Zp", "S", "Sm", "Sc", "Sk",
                 "So", "C", "Cc", "Cf", "Co", "Cn"]
        bad = ["A", "Za"]
        for s in tests:
            p = xsi.RegularExpressionParser(s)
            self.assertTrue(isinstance(p.require_is_category(), CharClass),
                            "Missing category: %s" % s)
            self.assertTrue(
                p.the_char is None, "Incomplete parse of category: %s" % s)
        for s in bad:
            p = xsi.RegularExpressionParser(s)
            try:
                p.require_is_category()
                self.assertFalse(
                    p.the_char is None, "Undetected bad category: %s" % s)
            except xsi.RegularExpressionError:
                pass
        tests = {
            # positive and negative tests
            'Nd': (
                u8(b'123\xdb\xb1\xdb\xb2\xdb\xb3'),
                u8(b'ABC\xe2\x85\x95\xe2\x85\x96\xe2\x85\x97\xe2\x85\x98')),
            'S': (u8(b'+<=>\xe2\x81\x84\xe2\x82\xac'), "(){}")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser(b)
            cclass = p.require_is_category()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in %s" % (repr(c), b))

    def test_is_block(self):
        """::
        IsBlock    ::=    'Is' [a-zA-Z0-9#x2D]+"""
        tests = {
            # positive and negative tests
            'BasicLatin': ("ABC", ul("\xc0\xdf\xa9")),
            'Latin-1Supplement': (ul("\xc0\xdf\xa9"), "ABC"),
            'CurrencySymbols': (u8(b'\xe2\x82\xa4\xe2\x82\xa9\xe2\x82\xac'),
                                ul("\x24\xa2\xa3")),
            'NumberForms': (
                u8(b'\xe2\x85\x95\xe2\x85\x96\xe2\x85\x97\xe2\x85\x98'),
                "1/5 2/5 3/5 4/5")
        }
        for b in dict_keys(tests):
            p = xsi.RegularExpressionParser("Is" + b)
            cclass = p.require_is_block()
            self.assertTrue(p.the_char is None)
            t1, t2 = tests[b]
            for c in t1:
                self.assertTrue(cclass.test(c), "%s not in %s" % (repr(c), b))
            for c in t2:
                self.assertFalse(cclass.test(c), "%s in Is%s" % (repr(c), b))
        p = xsi.RegularExpressionParser("IsNumberFoams")
        try:
            cclass = p.require_is_block()
            self.fail("IsNumberFoams")
        except xsi.RegularExpressionError:
            pass

    def test_multi_char_esc(self):
        """::
        MultiCharEsc ::= '\' [sSiIcCdDwW]"""
        tests = {
            # positive and negative tests
            's': ("\x09\x0A\x0D ", "ABC"),
            'i': ("ABC_:", "-123"),
            'c': ("ABC_:-_123", "@<>?"),
            'd': (u8(b'123\xd9\xa1\xd9\xa2\xd9\xa3'),
                  u8(b'ABC\xe2\x82\x81\xe2\x82\x82\xe2\x82\x83')),
            'w': ("ABC", u8(b'!\xcd\xbe \xe2\x80\x82\x0c')),
        }
        for c in dict_keys(tests):
            p1 = xsi.RegularExpressionParser("\\" + c)
            cclass1 = p1.require_multi_char_esc()
            self.assertTrue(p1.pos == 2)
            p2 = xsi.RegularExpressionParser("\\" + c.upper())
            cclass2 = p2.require_multi_char_esc()
            self.assertTrue(p2.pos == 2)
            t1, t2 = tests[c]
            for c1 in t1:
                self.assertTrue(
                    cclass1.test(c1), "%s not in \\%s" % (repr(c1), c))
                self.assertFalse(
                    cclass2.test(c1), "%s in \\%s" % (repr(c1), c.upper()))
            for c2 in t2:
                self.assertFalse(
                    cclass1.test(c2), "%s in \\%s" % (repr(c2), c))
                self.assertTrue(cclass2.test(c2), "%s in \\%s" %
                                (repr(c2), c.upper()))
        p = xsi.RegularExpressionParser("\\x")
        try:
            p.require_multi_char_esc()
            self.fail("\\x")
        except xsi.RegularExpressionError:
            pass

    def test_wildcard_esc(self):
        """::
        [37a] WildcardEsc ::= '.'"""
        p = xsi.RegularExpressionParser(".*")
        cclass = p.require_wildcard_esc()
        self.assertTrue(p.pos == 1)
        self.assertFalse(cclass.test("\x0A"), "Line feed in .")
        self.assertFalse(cclass.test("\x0D"), "Carriage return in .")
        for i in range3(100):
            # do a few random tests
            j = random.randint(0, maxunicode)
            if j in (10, 13):
                continue
            self.assertTrue(cclass.test(character(j)),
                            "Random char not in . character(%04X)" % j)
        p = xsi.RegularExpressionParser("x")
        try:
            cclass = p.require_wildcard_esc()
            self.fail(".")
        except xsi.RegularExpressionError:
            pass


if __name__ == "__main__":
    unittest.main()
