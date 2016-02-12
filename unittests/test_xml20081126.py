#! /usr/bin/env python

import unittest
import logging

from sys import maxunicode
from tempfile import mkdtemp
import shutil
import os.path
from StringIO import StringIO
from types import UnicodeType

import pyslet.rfc2396 as uri

MAX_CHAR = 0x10FFFF
if maxunicode < MAX_CHAR:
    MAX_CHAR = maxunicode


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XML20081126Tests, 'test'),
        unittest.makeSuite(XMLCharacterTests, 'test'),
        unittest.makeSuite(XMLValidationTests, 'test'),
        unittest.makeSuite(XMLEntityTests, 'test'),
        unittest.makeSuite(XMLParserTests, 'test'),
        unittest.makeSuite(ElementTests, 'test'),
        unittest.makeSuite(DocumentTests, 'test')
    ))

TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_xml20081126')

from pyslet.xml20081126.structures import *
from pyslet.xml20081126.parser import XMLParser


class PIRecorderElement(Element):

    def __init__(self, parent):
        Element.__init__(self, parent)
        self.target = None
        self.instruction = None

    def ProcessingInstruction(self, target, instruction):
        self.target = target
        self.instruction = instruction


class NamedElement(Element):
    XMLNAME = "test"
    XMLCONTENT = ElementType.ElementContent


def DecodeYN(value):
    return value == 'Yes'


def EncodeYN(value):
    if value:
        return 'Yes'
    else:
        return 'No'


class GenericElementA(Element):
    pass


class GenericSubclassA(GenericElementA):
    pass


class GenericElementB(Element):
    pass


class GenericSubclassB(GenericElementB):
    pass


class ReflectiveElement(Element):
    XMLNAME = "reflection"

    XMLATTR_btest = 'bTest'
    XMLATTR_ctest = ('cTest', DecodeYN, EncodeYN)
    XMLATTR_dtest = ('dTest', DecodeYN, EncodeYN, types.ListType)
    XMLATTR_dtestR = ('dTestR', DecodeYN, EncodeYN)  # legacy test
    XMLATTR_etest = ('eTest', DecodeYN, EncodeYN, types.DictType)
    XMLATTR_etestR = ('eTestR', DecodeYN, EncodeYN) 	# legacy test
    XMLATTR_ftest = 'fTest'		# missing attribute value

    def __init__(self, parent):
        Element.__init__(self, parent)
        self.atest = None
        self.bTest = None
        self.cTest = None
        self.dTest = None
        self.dTestR = []
        self.eTest = None
        self.eTestR = {}
        self.child = None
        self.generics = []
        self.GenericElementB = None

    def GetChildren(self):
        for child in Element.GetChildren(self):
            yield child
        if self.child:
            yield self.child

    def ReflectiveElement(self):
        if self.child:
            return self.child
        else:
            e = ReflectiveElement(self)
            self.child = e
            return e

    def GenericElementA(self, childClass=GenericElementA):
        child = childClass(self)
        self.generics.append(child)
        return child


class ReflectiveDocument(Document):

    @classmethod
    def get_element_class(cls, name):
        if name in ["reflection", "etest"]:
            return ReflectiveElement
        else:
            return Element


class EmptyElement(Element):
    XMLNAME = "empty"
    XMLCONTENT = XMLEmpty


class ElementContent(Element):
    XMLNAME = "elements"
    XMLCONTENT = ElementContent


class MixedElement(Element):
    XMLNAME = "mixed"
    XMLCONTENT = XMLMixedContent


class IDElement(Element):
    XMLName = "ide"
    XMLCONTENT = XMLEmpty
    ID = "id"


class BadElement:
    XMLNAME = "bad"


class Elements:
    named = NamedElement
    reflective = ReflectiveElement
    empty = EmptyElement
    elements = ElementContent
    mixed = MixedElement
    id = IDElement
    bad = BadElement


class XML20081126Tests(unittest.TestCase):

    def testCaseConstants(self):
        #self.assertTrue(APP_NAMESPACE=="http://www.w3.org/2007/app","Wrong APP namespace: %s"%APP_NAMESPACE)
        #self.assertTrue(ATOMSVC_MIMETYPE=="application/atomsvc+xml","Wrong APP service mime type: %s"%ATOMSVC_MIMETYPE)
        #self.assertTrue(ATOMCAT_MIMETYPE=="application/atomcat+xml","Wrong APP category mime type: %s"%ATOMCAT_MIMETYPE)
        pass

    def testCaseDeclare(self):
        classMap = {}
        MapClassElements(classMap, Elements)
        self.assertTrue(
            issubclass(classMap['mixed'], Element), "class type not declared")
        self.assertFalse(
            hasattr(classMap, 'bad'), "class type declared by mistake")


class XMLCharacterTests(unittest.TestCase):
    # Test IsNameChar

    def testChar(self):
        """[2] Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]"""
        expectedEdges = [
            0x9, 0xB, 0xD, 0xE, 0x20, 0xD800, 0xE000, 0xFFFE, 0x10000, 0x110000]
        if MAX_CHAR < 0x10FFFF:
            expectedEdges = expectedEdges[0:8]
            logging.warn(
                "xml tests truncated to unichr(0x%X) by narrow python build" % MAX_CHAR)
        self.assertTrue(self.FindEdges(IsChar, MAX_CHAR) == expectedEdges,
                        "IsChar range test: " + str(self.FindEdges(IsChar, MAX_CHAR)))

    def testSpace(self):
        """[3] S ::= (#x20 | #x9 | #xD | #xA)+"""
        expectedEdges = [0x9, 0xB, 0xD, 0xE, 0x20, 0x21]
        self.assertTrue(self.FindEdges(is_s, 256) == expectedEdges, "is_s")

    def testNameStart(self):
        """[4] NameStartChar ::= ":" | [A-Z] | "_" | [a-z] | [#xC0-#xD6] | [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] | [#x37F-#x1FFF] | [#x200C-#x200D] | [#x2070-#x218F] | [#x2C00-#x2FEF] | [#x3001-#xD7FF] | [#xF900-#xFDCF] | [#xFDF0-#xFFFD] | [#x10000-#xEFFFF]
        [5] NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 | [#x0300-#x036F] | [#x203F-#x2040]"""
        nNameStartChars = 0
        nNameChars = 0
        for code in xrange(0x10000):
            c = unichr(code)
            if IsNameChar(c):
                nNameChars += 1
                if IsNameStartChar(c):
                    nNameStartChars += 1
            else:
                self.assertFalse(
                    IsNameStartChar(c), "NameStart not a name char: %s" % c)
        self.assertTrue(nNameChars == 54129, "name char total %i" % nNameChars)
        self.assertTrue(
            nNameStartChars == 54002, "name start char total %i" % nNameStartChars)

    def testPubidChar(self):
        """[13] PubidChar ::= #x20 | #xD | #xA | [a-zA-Z0-9] | [-'()+,./:=?;!*#@$_%] """
        matchSet = " \x0d\x0a-'()+,./:=?;!*#@$_%abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for code in xrange(0xFF):
            c = unichr(code)
            if IsPubidChar(c):
                if not c in matchSet:
                    self.fail("PubidChar false positive: %s" % c)
            else:
                if c in matchSet:
                    self.fail("PubidChar not recognized: %s" % c)

    def testCharClasses(self):
        """[84] Letter ::= BaseChar | Ideographic
        [85] BaseChar ::= [#x0041-#x005A] | ...
        [86] Ideographic ::= [#x4E00-#x9FA5] | #x3007 | [#x3021-#x3029]
        [87] CombiningChar ::= [#x0300-#x0345] | ...
        [88] Digit ::= [#x0030-#x0039] | ...
        [89] Extender ::= #x00B7 | ..."""
        nBaseChars = 0
        nIdeographics = 0
        nCombiningChars = 0
        nDigits = 0
        nExtenders = 0
        for code in xrange(0x10000):
            c = unichr(code)
            if IsLetter(c):
                if IsIdeographic(c):
                    nIdeographics += 1
                elif IsBaseChar(c):
                    nBaseChars += 1
                else:
                    self.fail(
                        "unichr(%#x) is a letter but not an ideographic or base character" % code)
            else:
                self.assertFalse(IsIdeographic(c) or IsBaseChar(c),
                                 "unichr(%#x) is an ideographic or base character but not a letter")
            if IsCombiningChar(c):
                nCombiningChars += 1
            if is_digit(c):
                nDigits += 1
            if IsExtender(c):
                nExtenders += 1
        self.assertTrue(nBaseChars == 13602, "base char total %i" % nBaseChars)
        self.assertTrue(
            nIdeographics == 20912, "ideographic char total %i" % nIdeographics)
        self.assertTrue(
            nCombiningChars == 437, "combing char total %i" % nCombiningChars)
        self.assertTrue(nDigits == 149, "digit total %i" % nDigits)
        self.assertTrue(nExtenders == 18, "extender total %i" % nExtenders)

    def FindEdges(self, testFunc, max):
        edges = []
        flag = False
        for code in xrange(max + 1):
            c = unichr(code)
            if flag != testFunc(c):
                flag = not flag
                edges.append(code)
        if flag:
            edges.append(max + 1)
        return edges


class XMLValidationTests(unittest.TestCase):

    def testCaseName(self):
        self.assertTrue(IsValidName("Simple"))
        self.assertTrue(IsValidName(":BadNCName"))
        self.assertTrue(IsValidName("prefix:BadNCName"))
        self.assertTrue(IsValidName("_GoodNCName"))
        self.assertFalse(IsValidName("-BadName"))
        self.assertFalse(IsValidName(".BadName"))
        self.assertFalse(IsValidName("0BadName"))
        self.assertTrue(IsValidName("GoodName-0.12"))
        self.assertFalse(IsValidName("BadName$"))
        self.assertFalse(IsValidName("BadName+"))
        self.assertTrue(IsValidName(u"Caf\xe9"))

    def testWellFormed(self):
        dPath = os.path.join(TEST_DATA_DIR, 'wellformed')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f)
            d = Document()
            p = XMLParser(e)
            p.checkValidity = False
            try:
                p.parse_document(d)
                self.assertTrue(
                    p.valid is None, "Well-Formed Example: %s marked valid but checkValidity was False" % fName)
            except XMLWellFormedError, e:
                self.fail(
                    "Well-Formed Example: %s raised XMLWellFormedError\n%s" % (fName, str(e)))
        dPath = os.path.join(TEST_DATA_DIR, 'notwellformed')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f)
            d = Document()
            try:
                d.Read(e)
                self.fail(
                    "%s is not Well-Formed but failed to raise XMLWellFormedError" % fName)
            except XMLWellFormedError, e:
                logging.info("\n%s: Well-formed Errors:", fName)
                logging.info(str(e))

    def testValid(self):
        dPath = os.path.join(TEST_DATA_DIR, 'valid')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f)
            p = XMLParser(e)
            p.checkValidity = True
            p.raiseValidityErrors = True
            try:
                p.parse_document()
                self.assertTrue(
                    p.valid, "Valid Example: %s not marked as valid in the parser" % fName)
                self.assertTrue(
                    len(p.nonFatalErrors) == 0, "Valid Example: %s reported validity errors" % fName)
            except XMLValidityError, e:
                self.fail(
                    "Valid Example: %s raised XMLValidityError\n%s" % (fName, str(e)))
            except XMLWellFormedError, e:
                self.fail(
                    "Valid Example: %s raised XMLWellFormedError" % fName)
        dPath = os.path.join(TEST_DATA_DIR, 'wellformed')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f)
            p = XMLParser(e)
            p.checkValidity = True
            # By default we don't raise validity errors...
            try:
                p.parse_document()
                self.assertFalse(
                    p.valid, "Invalid Example: %s marked as valid in the parser" % fName)
                self.assertFalse(len(
                    p.nonFatalErrors) == 0, "Invalid Example: %s reported no validity errors" % fName)
                logging.info("\n%s: Validity Errors:", fName)
                for e in p.nonFatalErrors:
                    logging.info(str(e))
            except XMLValidityError, e:
                self.fail(
                    "XMLValidityError raised when raiseVaidityErrors is False (%s)" % fName)
            except XMLWellFormedError, e:
                self.fail(
                    "Invalid but Well-Formed Example raised XMLWellFormedError (%s)\n%s" % (fName, str(e)))
            except XMLError, e:
                self.fail(
                    "Other XMLError raised by invalid but Well-Formed Example (%s)" % fName)

    def testIncompatible(self):
        dPath = os.path.join(TEST_DATA_DIR, 'compatible')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f)
            p = XMLParser(e)
            p.checkCompatibility = True
            try:
                p.parse_document()
                self.assertTrue(len(
                    p.nonFatalErrors) == 0, "Compatible Example: %s reported compatibility errors" % fName)
            except XMLValidityError, e:
                self.fail(
                    "Compatible Example: %s raised XMLValidityError" % fName)
            except XMLWellFormedError, e:
                self.fail(
                    "Compatible Example: %s raised XMLWellFormedError" % fName)
            except XMLError, e:
                self.fail(
                    "Compatible Example: %s raised other XMLError" % fName)
        dPath = os.path.join(TEST_DATA_DIR, 'incompatible')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f)
            p = XMLParser(e)
            p.checkCompatibility = True
            try:
                p.parse_document()
                self.assertFalse(len(
                    p.nonFatalErrors) == 0, "Incompatible Example: %s reported no non-fatal errors" % fName)
                logging.info("\n%s: Compatibility Errors:", fName)
                for e in p.nonFatalErrors:
                    logging.info(str(e))
            except XMLValidityError, e:
                self.fail(
                    "XMLValidityError raised when raiseVaidityErrors is False (%s)" % fName)
            except XMLWellFormedError, e:
                self.fail(
                    "Incompatible but Well-Formed Example raised XMLWellFormedError (%s)" % fName)
            except XMLError, e:
                self.fail(
                    "Other XMLError raised by incompatible but Well-Formed Example (%s)" % fName)

    def testError(self):
        dPath = os.path.join(TEST_DATA_DIR, 'noerrors')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f, 'latin-1' if "latin" in fName else None)
            p = XMLParser(e)
            p.checkAllErrors = True
            try:
                p.parse_document()
                self.assertTrue(
                    len(p.nonFatalErrors) == 0, "No errors example: %s reported errors" % fName)
            except XMLError, e:
                self.fail("No errors example: %s raised XMLError" % fName)
        dPath = os.path.join(TEST_DATA_DIR, 'errors')
        for fName in os.listdir(dPath):
            if fName[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dPath, fName))
            e = XMLEntity(f, 'latin-1' if "latin" in fName else None)
            p = XMLParser(e)
            p.checkAllErrors = True
            try:
                p.parse_document()
                self.assertFalse(len(
                    p.nonFatalErrors) == 0, "Error example: %s reported no non-fatal errors" % fName)
                logging.info("\n%s: Errors:", fName)
                for e in p.nonFatalErrors:
                    logging.info(str(e))
            except XMLError, e:
                self.fail(
                    "XMLError raised by (non-fatal) error example (%s)" % fName)


class XMLEntityTests(unittest.TestCase):

    def testCaseConstructor(self):
        e = XMLEntity("<hello>")
        self.assertTrue(e.lineNum == 1)
        self.assertTrue(e.linePos == 1)
        self.assertTrue(type(e.the_char) is UnicodeType and e.the_char == u'<')
        e = XMLEntity(u"<hello>")
        self.assertTrue(type(e.the_char) is UnicodeType and e.the_char == u'<')
        e = XMLEntity(StringIO("<hello>"))
        self.assertTrue(e.lineNum == 1)
        self.assertTrue(e.linePos == 1)
        self.assertTrue(type(e.the_char) is UnicodeType and e.the_char == u'<')

    def testCaseChars(self):
        e = XMLEntity("<hello>")
        for c in "<hello>":
            self.assertTrue(e.the_char == c)
            e.next_char()
        self.assertTrue(e.the_char is None)
        e.reset()
        self.assertTrue(e.the_char == '<')

    def testLines(self):
        e = XMLEntity("Hello\nWorld\n!")
        while e.the_char is not None:
            c = e.the_char
            e.next_char()
        self.assertTrue(e.lineNum == 3)
        self.assertTrue(e.linePos == 2)

    def testCodecs(self):
        m = u'Caf\xe9'
        e = XMLEntity('Caf\xc3\xa9')
        self.assertTrue(e.bom is False, 'defaulted utf-8 BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c, "Print: parsing utf-8 got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        e = XMLEntity('Caf\xe9', 'latin_1')
        self.assertTrue(e.bom is False, 'latin_1 BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c, "Print: parsing latin-1 got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        # This string should be automatically detected
        e = XMLEntity('\xff\xfeC\x00a\x00f\x00\xe9\x00')
        self.assertTrue(e.bom is True, 'utf-16-le BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c, "Print: parsing utf-16LE got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        e = XMLEntity('\xfe\xff\x00C\x00a\x00f\x00\xe9')
        self.assertTrue(e.bom is True, 'utf-16-be BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c, "Print: parsing utf-16BE got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        e = XMLEntity('\xef\xbb\xbfCaf\xc3\xa9', 'utf-8')
        self.assertTrue(e.bom is False, 'utf-8 BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c, "Print: parsing utf-8 with BOM got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        e = XMLEntity('Caf\xe9')
        for c in 'Ca':
            e.next_char()
        e.ChangeEncoding('ISO-8859-1')
        self.assertTrue(e.the_char == 'f', "Bad encoding change")
        e.next_char()
        self.assertTrue(e.the_char == u'\xe9', "Print: change encoding got %s instead of %s" % (
            repr(e.the_char), repr(u'\xe9')))
        e = XMLEntity('C\x00a\x00f\x00\xe9\x00', 'utf-16-le')
        self.assertTrue(e.bom is False, 'utf-16-le no BOM detection error')
        for c in m:
            self.assertTrue(
                e.the_char == c, "Print: parsing utf-16LE no BOM got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        # add <? to trigger auto-detection
        e = XMLEntity('\x00<\x00?\x00C\x00a\x00f\x00\xe9')
        self.assertTrue(e.bom is False, 'utf-16-be no BOM detection error')
        for c in u"<?" + m:
            self.assertTrue(
                e.the_char == c, "Print: parsing utf-16BE no BOM got %s instead of %s" % (repr(e.the_char), repr(c)))
            e.next_char()
        e = XMLEntity('\xfe\xff\xfe\xff\x00C\x00a\x00f\x00\xe9')
        for c in u'\ufeff' + m:
            self.assertTrue(e.the_char == c, "Print: parsing double BOM got %s instead of %s" % (
                repr(e.the_char), repr(c)))
            e.next_char()


class XMLParserTests(unittest.TestCase):

    def testCaseConstructor(self):
        e = XMLEntity("<hello>")
        p = XMLParser(e)

    def testCaseRewind(self):
        data = "Hello\r\nWorld\nCiao\rTutti!"
        data2 = "Hello\nWorld\nCiao\nTutti!"
        e = XMLEntity(data)
        p = XMLParser(e)
        for i in xrange(len(data2)):
            self.assertTrue(
                p.the_char == data2[i], "Failed at data[%i] before look ahead" % i)
            for j in xrange(5):
                data = []
                for k in xrange(j):
                    if p.the_char is not None:
                        data.append(p.the_char)
                    p.next_char()
                p.buff_text(string.join(data, ''))
                self.assertTrue(
                    p.the_char == data2[i], "Failed at data[%i] after Rewind(%i)" % (i, j))
            p.next_char()

    def testCaseNamecaseGeneral(self):
        data = "Hello GoodBye"
        e = XMLEntity(data)
        p = XMLParser(e)
        self.assertFalse(
            p.parse_literal("HELLO"), "Case insensitve literal in default parser")
        p.sgmlNamecaseGeneral = True
        self.assertTrue(p.parse_literal("HELLO"), "Upper-case literals")
        p.parse_s()
        #self.assertTrue(p.parse_name()=="GOODBYE","Upper-case general names")

    def testDocument(self):
        """[1] document ::= prolog element Misc* """
        os.chdir(TEST_DATA_DIR)
        f = open('readFile.xml', 'rb')
        e = XMLEntity(f)
        d = Document()
        d.Read(e)
        root = d.root
        self.assertTrue(isinstance(root, Element))
        self.assertTrue(
            root.xmlname == 'tag' and root.GetValue() == 'Hello World')
        f.close()
        f = open('readFile.xml', 'rb')
        e = XMLEntity(f)
        p = XMLParser(e)
        p.parse_document()
        root = p.doc.root
        self.assertTrue(isinstance(root, Element))
        self.assertTrue(
            root.xmlname == 'tag' and root.GetValue() == 'Hello World')
        f.close()

    # Following production is implemented as a character class:
    # [2] Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]

    def testCaseS(self):
        """[3] S ::= (#x20 | #x9 | #xD | #xA)+ """
        e = XMLEntity(" \t\r\n \r \nH ello")
        p = XMLParser(e)
        self.assertTrue(p.parse_s() == " \t\n \n \n")
        self.assertTrue(p.the_char == 'H')
        p.next_char()
        try:
            p.parse_required_s()
        except XMLWellFormedError:
            self.fail("parse_required_s failed to parse white space")
        try:
            p.parse_required_s()
            self.fail("parse_required_s failed to throw exception")
        except XMLWellFormedError:
            pass

    # Following two productions are implemented as character classes:
    # [4] NameStartChar ::= ":" | [A-Z] | "_" | [a-z] | [#xC0-#xD6] | [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] | [#x37F-#x1FFF] | [#x200C-#x200D] | [#x2070-#x218F] | [#x2C00-#x2FEF] | [#x3001-#xD7FF] | [#xF900-#xFDCF] | [#xFDF0-#xFFFD] | [#x10000-#xEFFFF]
    # [4a] NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 | [#x0300-#x036F] | [#x203F-#x2040]

    def testCaseName(self):
        """[5] Name ::= NameStartChar (NameChar)*"""
        sGood = ('hello', ':ello', u'A\xb72', '_')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            name = p.parse_name()
            self.assertTrue(name == s, u"Name: %s (expected %s)" % (name, s))
        sBad = ('-Atlantis', '&hello', 'fish&chips',
                'what?', '.ello', u'\xb7RaisedDot', '-')
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                name = p.parse_name()
                self.assertFalse(
                    p.the_char is None, "parse_name negative test: %s" % s)
            except XMLWellFormedError:
                pass
        e = XMLEntity('&noname')
        p = XMLParser(e)
        try:
            p.parse_required_name()
            self.fail("parse_required_name: failed to throw exception")
        except XMLWellFormedError:
            pass

    def testCaseNames(self):
        """[6] Names ::= Name (#x20 Name)*	"""
        e = XMLEntity("Hello World -Atlantis!")
        p = XMLParser(e)
        self.assertTrue(p.parse_names() == ['Hello', 'World'])

    def testCaseNmtoken(self):
        """[7] Nmtoken ::= (NameChar)+"""
        sGood = ('hello', 'h:ello', '-Atlantis', ':ello',
                 u'\xb7RaisedDot', u'1\xb72', '-')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            name = p.parse_nmtoken()
            self.assertTrue(name == s, u"Nmtoken: %s" % name)
        sBad = ('&hello', 'fish&chips', 'what?')
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                name = p.parse_nmtoken()
                self.assertFalse(
                    p.the_char is None, "parse_nmtoken negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testCaseNmtokens(self):
        """[8] Nmtokens ::= Nmtoken (#x20 Nmtoken)*"""
        e = XMLEntity("Hello World -Atlantis!")
        p = XMLParser(e)
        tokens = p.parse_nmtokens()
        self.assertTrue(
            tokens == ['Hello', 'World', '-Atlantis'], repr(tokens))

    def testCaseEntityValue(self):
        """[9] EntityValue ::= '"' ([^%&"] | PEReference | Reference)* '"' | "'" ([^%&'] | PEReference | Reference)* "'"	"""
        e = XMLEntity("'first'\"second\"'3&gt;2''2%ltpe;3'")
        m = ['first', 'second', '3&gt;2', '2<3']
        p = XMLParser(e)
        p.checkValidity = True
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('ltpe', '<'))
        for match in m:
            value = p.parse_entity_value()
            self.assertTrue(
                value == match, "Match failed: %s (expected %s)" % (value, match))

    def testAttValue(self):
        """[10] AttValue ::= '"' ([^<&"] | Reference)* '"' |  "'" ([^<&'] | Reference)* "'" """
        e = XMLEntity("'first'\"second\"'3&gt;2''Caf&#xE9;'")
        m = ['first', 'second', '3>2', u'Caf\xe9']
        p = XMLParser(e)
        for match in m:
            value = p.parse_att_value()
            self.assertTrue(
                value == match, "Match failed: %s (expected %s)" % (value, match))
        sBad = ('"3<2"', "'Fish&Chips'")
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                value = p.parse_att_value()
                self.fail("AttValue negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testSystemLiteral(self):
        """[11] SystemLiteral ::= ('"' [^"]* '"') | ("'" [^']* "'") """
        e = XMLEntity("'first'\"second\"'3&gt;2''2%ltpe;3''Caf&#xE9;'")
        m = [u'first', u'second', u'3&gt;2', u'2%ltpe;3', u'Caf&#xE9;']
        p = XMLParser(e)
        for match in m:
            value = p.parse_system_literal()
            self.assertTrue(
                value == match, "Match failed: %s (expected %s)" % (value, match))

    def testPubidLiteral(self):
        """[12] PubidLiteral ::= '"' PubidChar* '"' | "'" (PubidChar - "'")* "'"	"""
        e = XMLEntity(
            "'first'\"second\"'http://www.example.com/schema.dtd?strict''[bad]'")
        m = ['first', 'second', 'http://www.example.com/schema.dtd?strict']
        p = XMLParser(e)
        for match in m:
            value = p.parse_pubid_literal()
            self.assertTrue(
                value == match, "Match failed: %s (expected %s)" % (value, match))
        try:
            value = p.parse_pubid_literal()
            self.fail("Parsed bad PubidLiterasl: %s" % value)
        except XMLFatalError:
            pass

    # [13] PubidChar: tested as a character class

    def testCaseCharData(self):
        """[14] CharData ::= [^<&]* - ([^<&]* ']]>' [^<&]*) """
        e = XMLEntity("First<Second&Third]]&Fourth]]>")
        m = ['First', 'Second', 'Third]]', 'Fourth']
        p = XMLParser(e)
        p.doc = Document()
        for match in m:
            p.element = Element(p.doc)
            p.parse_char_data()
            p.next_char()
            self.assertTrue(p.element.GetValue() == match, "Match failed: %s (expected %s)" % (
                p.element.GetValue(), match))

    def testCaseComment(self):
        """[15] Comment ::= '<!--' ((Char - '-') | ('-' (Char - '-')))* '-->' """
        e = XMLEntity(
            "<!--First--><!--Secon-d--><!--Thi<&r]]>d--><!--Fourt<!-h--><!--Bad-Comment--->")
        m = ['First', 'Secon-d', 'Thi<&r]]>d', 'Fourt<!-h']
        p = XMLParser(e)
        for match in m:
            pStr = p.parse_comment()
            self.assertTrue(
                pStr == match, "Match failed: %s (expected %s)" % (pStr, match))
        try:
            if p.parse_literal('<!--'):
                pStr = p.parse_comment()
            self.fail("Parsed bad comment: %s" % pStr)
        except XMLFatalError:
            pass

    def testCasePI(self):
        """[16] PI ::= '<?' PITarget (S (Char* - (Char* '?>' Char*)))? '?>' """
        e = XMLEntity(
            "<?target instruction?><?xm_xml \n\r<!--no comment-->?><?markup \t]]>?&<?>")
        m = [('target', 'instruction'),
             ('xm_xml', '<!--no comment-->'), ('markup', ']]>?&<')]
        p = XMLParser(e)
        p.doc = Document()
        for matchTarget, matchStr in m:
            p.element = PIRecorderElement(p.doc)
            p.parse_pi()
            self.assertTrue(p.element.target == matchTarget, "Match failed for target: %s (expected %s)" % (
                p.element.target, matchTarget))
            self.assertTrue(p.element.instruction == matchStr, "Match failed for instruction: %s (expected %s)" % (
                p.element.instruction, matchStr))
        sBad = ('<?xml reserved?>')
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.doc = Document()
            try:
                p.parse_pi()
                self.fail("PI negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testPITarget(self):
        """[17] PITarget ::= Name - (('X' | 'x') ('M' | 'm') ('L' | 'l'))	"""
        sGood = ('hello', 'helloxml', 'xmlhello', 'xmhello', 'xm', 'ml', 'xl')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            name = p.parse_pi_target()
            self.assertTrue(name == s, "PITarget: %s" % name)
        sBad = ('xml', 'XML', 'xML', 'Xml')
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                name = p.parse_pi_target()
                self.fail("PITarget negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testCDSect(self):
        """[18] CDSect ::= CDStart CData CDEnd	"""
        sGood = ('<![CDATA[hello]]>',
                 "<![CDATA[]]>",
                 "<![CDATA[a]b]]c]>d><![CDATAe]]>",
                 'hello]]>',
                 "<![CDATA[<hello>&world;]]>")
        m = ['hello', '', 'a]b]]c]>d><![CDATAe', 'hello', "<hello>&world;"]
        for s, match in zip(sGood, m):
            e = XMLEntity(s)
            p = XMLParser(e)
            p.doc = Document()
            p.element = Element(p.doc)
            p.parse_cdsect(p.the_char != '<')
            self.assertTrue(
                p.element.GetValue() == match, "CDSect conent: %s" % p.element.GetValue())
        sBad = ('<!CDATA [hello]]>',
                "<!CDATA[hello]]",
                "hello")
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.doc = Document()
            p.element = Element(p.doc)
            try:
                p.parse_cdsect(p.the_char != '<')
                self.fail("CDSect negative test: %s" % s)
            except XMLWellFormedError:
                pass
        e = XMLEntity("&hello;<end")
        p = XMLParser(e)
        p.doc = Document()
        p.element = Element(p.doc)
        p.parse_cdsect(True, '<end')
        self.assertTrue(
            p.element.GetValue() == '&hello;', "Custom CDSect: %s" % p.element.GetValue())

    def testCDStart(self):
        """[21] CDStart ::= '<!CDATA['	"""
        e = XMLEntity("<![CDATA[")
        p = XMLParser(e)
        p.parse_cdstart()
        self.assertTrue(p.the_char is None, "Short parse on CDStart")

    def testCData(self):
        """[20] CData ::= (Char* - (Char* ']]>' Char*))	"""
        sGood = ('', ' ', '<!-- comment -->',
                 '&hello;]]>',
                 ']',
                 ']]',
                 ']]h>')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.doc = Document()
            p.element = Element(p.doc)
            p.parse_cdata()
            if p.the_char is None:
                self.assertTrue(
                    p.element.GetValue() == s, "CData conent: %s" % p.element.GetValue())
            else:
                p.parse_cdend()
                self.assertTrue(
                    p.element.GetValue() == s[:-3], "CData conent: %s" % p.element.GetValue())
        # no negative tests as prolog can be empty, but check the custom CDEnd
        # case.
        e = XMLEntity("hello<end")
        p = XMLParser(e)
        p.doc = Document()
        p.element = Element(p.doc)
        p.parse_cdata('<end')
        self.assertTrue(
            p.element.GetValue() == 'hello', "Custom CDEnd: %s" % p.element.GetValue())

    def testCDEnd(self):
        """[21] CDEnd ::= ']]>'	"""
        e = XMLEntity("]]>")
        p = XMLParser(e)
        p.parse_cdend()
        self.assertTrue(p.the_char is None, "Short parse on CDEnd")

    def testProlog(self):
        """[22] prolog ::= XMLDecl? Misc* (doctypedecl Misc*)?	"""
        sGood = ('', ' ', '<!-- comment -->',
                 '<?xml version="1.0"?>',
                 '<?xml version="1.0"?><!-- comment --> ',
                 '<?xml version="1.0"?><!-- comment --> <!DOCTYPE steve>',
                 '<?xml version="1.0"?><!-- comment --> <!DOCTYPE steve><?pi?> ')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.doc = Document()
            p.parse_prolog()
            self.assertTrue(p.the_char is None, "Short parse on Prolog")
        # no negative tests as prolog can be empty!

    def testXMLDecl(self):
        """[23] XMLDecl ::= '<?xml' VersionInfo EncodingDecl? SDDecl? S? '?>'	"""
        sGood = ('<?xml version="1.0" encoding="utf-8" standalone="no" ?>',
                 "<?xml version='1.0' standalone='yes'?>",
                 "<?xml version='1.0' encoding='utf-8'?>",
                 "<?xml version='1.1'?>",
                 " version='1.2'?>")
        m = [('1.0', 'utf-8', False),
             ('1.0', None, True),
             ('1.0', 'utf-8', False),
             ('1.1', None, False),
             ('1.2', None, False)]
        for s, match in zip(sGood, m):
            e = XMLEntity(s)
            p = XMLParser(e)
            d = p.parse_xml_decl(not ('x' in s))
            self.assertTrue(
                isinstance(d, XMLDeclaration), "xml declaration type")
            self.assertTrue(
                d.version == match[0], "declared version mismatch: %s" % d.version)
            self.assertTrue(
                d.encoding == match[1], "declared encoding mismatch: %s" % d.encoding)
            self.assertTrue(
                d.standalone == match[2], "standalone declaration mismatch: %s" % d.standalone)
            self.assertTrue(p.the_char is None, "Short parse on XMLDecl")
        sBad = ('', 'version="1.0"', " ='1.0'", " version=1.0")
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_xml_decl()
                self.fail("XMLDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testVersionInfo(self):
        """[24] VersionInfo ::= S 'version' Eq ("'" VersionNum "'" | '"' VersionNum '"')	"""
        sGood = (' version="1.0"', "  version  =  '1.1'", " = '1.0'")
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.parse_version_info(not ('v' in s))
            self.assertTrue(p.the_char is None, "Short parse on VersionInfo")
        sBad = ('', 'version="1.0"', " ='1.0'", " version=1.0")
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_version_info()
                self.fail("VersionInfo negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testEq(self):
        """[25] Eq ::= S? '=' S?	"""
        sGood = ('=', ' = ', ' =', '= ')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.parse_eq()
            self.assertTrue(p.the_char is None, "Short parse on Eq")
        sBad = ('', '-')
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_eq()
                self.fail("Eq negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testVersionNum(self):
        """[26] VersionNum ::= '1.' [0-9]+ """
        sGood = ('1.0', '1.10', '1.1', '1.0123456789')
        for s in sGood:
            e = XMLEntity(s)
            p = XMLParser(e)
            self.assertTrue(
                p.parse_version_num() == s, "Failed to parse VersionNum: %s" % s)
            self.assertTrue(p.the_char is None, "Short parse on VersionNum")
        sBad = ('1. ', '2.0', '1', '1,0')
        for s in sBad:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_version_num()
                self.fail("VersionNum negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testMisc(self):
        """[27] Misc ::= Comment | PI | S """
        s = "<!-- comment --><?pi?> "
        e = XMLEntity(s)
        p = XMLParser(e)
        for i in xrange(3):
            p.parse_misc()
        self.assertTrue(p.the_char is None, "Short parse of Misc")

    def testDoctypedecl(self):
        """[28] doctypedecl ::= '<!DOCTYPE' S Name (S ExternalID)? S? ('[' intSubset ']' S?)? '>'	"""
        s = ["<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd'[ <!ENTITY name 'Steve'> ]>",
             "<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd' [] >",
             "<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd' >",
             "<!DOCTYPE Steve [ ] >",
             "<!DOCTYPE Steve>"]
        m = [('Steve', 'SteveDoc.dtd', 'Steve'),
             ('Steve', 'SteveDoc.dtd', None),
             ('Steve', 'SteveDoc.dtd', None),
             ('Steve', None, None),
             ('Steve', None, None)]
        dtdPath = os.path.join(TEST_DATA_DIR, 'SteveDoc.dtd')
        f = uri.URI.from_path(dtdPath)
        for sEntity, match in zip(s, m):
            e = XMLEntity(sEntity)
            e.location = f
            p = XMLParser(e)
            p.parse_doctypedecl()
            self.assertTrue(isinstance(p.dtd, XMLDTD), "No DTD created")
            self.assertTrue(p.dtd.name == match[0], "Name mismatch")
            if match[1] is None:
                self.assertTrue(
                    p.dtd.external_id is None, "External ID: expected None")
            else:
                self.assertTrue(
                    isinstance(p.dtd.external_id, XMLExternalID), "Type of ExternalID")
                self.assertTrue(
                    p.dtd.external_id.system == match[1], "System ID mismatch")
            if match[2] is not None:
                self.assertTrue(p.dtd.GetEntity('name').definition == match[
                                2], "Expected general entity declared: %s" % repr(p.dtd.GetEntity('name').definition))

    def testDeclSep(self):
        """[28a] DeclSep ::= PEReference | S"""
        s = "%stuff; %stuff; x"
        e = XMLEntity(s)
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('stuff', ' '))
        p.checkValidity = True
        p.refMode = XMLParser.RefModeInDTD
        while p.the_char != 'x':
            p.parse_decl_sep()

    def testIntSubset(self):
        """[28b] intSubset ::= (markupdecl | DeclSep)* """
        s = """<!ELEMENT elem1 ANY>
		<!ATTLIST elem1 attr CDATA 'Steve'>
		<!ENTITY name 'Steve'>
		<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'> 
		<?stuff?>
		<!-- more stuff -->
		x"""
        e = XMLEntity(s)
        p = XMLParser(e)
        p.doc = Document()
        p.parse_int_subset()
        self.assertTrue(
            p.the_char == 'x', "Short parse on internal subset: found %s" % repr(p.the_char))

    def testMarkupDecl(self):
        """[29] markupdecl ::= elementdecl | AttlistDecl | EntityDecl | NotationDecl | PI | Comment	"""
        s = """<!ELEMENT elem1 ANY>
		<!ATTLIST elem1 attr CDATA 'Steve'>
		<!ENTITY name 'Steve'>
		<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'> 
		<?stuff?>
		<!-- more stuff -->
		x"""
        e = XMLEntity(s)
        p = XMLParser(e)
        p.checkValidity = True  # ensures that elements are declared in the DTD
        p.dtd = XMLDTD()
        while p.the_char == '<':
            p.parse_markup_decl(False)
            p.parse_s()
        self.assertTrue(
            p.the_char == 'x', "Short parse on markup declarations: found %s" % repr(p.the_char))
        etype = p.dtd.GetElementType('elem1')
        self.assertTrue(
            etype.contentType == ElementType.Any, "element content type")
        alist = p.dtd.GetAttributeList('elem1')
        self.assertTrue(alist['attr'].defaultValue == 'Steve', "attlist")
        self.assertTrue(
            p.dtd.GetEntity('name').definition == 'Steve', "entity declaration")
        self.assertTrue(p.dtd.GetNotation(
            'SteveN').external_id.system == '/home/steve.txt', "notation declaration")

    def testExtSubset(self):
        """[30] extSubset ::= TextDecl? extSubsetDecl """
        s = '<?xml encoding = "latin-1"?> <?stuff?> !'
        e = XMLEntity(s)
        p = XMLParser(e)
        p.parse_ext_subset()
        self.assertTrue(
            p.the_char == '!', "Short parse on extSubset: %s" % p.the_char)
        s = '<?stuff?> !'
        e = XMLEntity(s)
        p = XMLParser(e)
        p.parse_ext_subset()
        self.assertTrue(
            p.the_char == '!', "Short parse on extSubset: %s" % p.the_char)

    def testExtSubsetDecl(self):
        """[31] extSubsetDecl ::= ( markupdecl | conditionalSect | DeclSep)*	"""
        s = "<?stuff?><![INCLUDE[]]>%moreStuff; "
        e = XMLEntity(s)
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('moreStuff', ' <?stuff?>'))
        p.checkValidity = True
        p.refMode = XMLParser.RefModeInDTD
        p.parse_ext_subset_decl()
        self.assertTrue(
            p.the_char is None, "Short parse on extSubsetDecl: %s" % p.the_char)

    def testSDDecl(self):
        """[32] SDDecl ::= S 'standalone' Eq (("'" ('yes' | 'no') "'") | ('"' ('yes' | 'no') '"')) """
        e = XMLEntity(
            " standalone='yes' standalone = \"no\" standalone = 'bad'")
        m = [True, False]
        p = XMLParser(e)
        for match in m:
            value = p.parse_sd_decl()
            self.assertTrue(
                value == match, "Match failed: %s (expected %s)" % (value, match))
        try:
            value = p.parse_sd_decl()
            self.fail("Parsed bad SDDecl: %s" % value)
        except XMLFatalError:
            pass

    # There are no productions [33]-[38]

    def testElement(self):
        """[39] element ::= EmptyElemTag | STag content ETag """
        s = """<elem1/><elem2>hello</elem2><elem3>goodbye</elem4>"""
        e = XMLEntity(s)
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInContent
        element = p.element = Element("a")
        p.parse_element()
        p.parse_element()
        try:
            p.parse_element()
            self.fail("Parsed bad element.")
        except XMLWellFormedError:
            pass
        children = list(element.GetChildren())
        self.assertTrue(
            isinstance(children[0], Element), "First element: %s" % repr(children[0]))
        self.assertTrue(children[0].xmlname == 'elem1', "First element name: %s" % repr(
            children[0].xmlname))
        self.assertTrue(children[0].GetValue(
        ) == '', "First element empty value: %s" % repr(children[0].GetValue()))
        self.assertTrue(
            isinstance(children[1], Element), "Second element: %s" % repr(children[1]))
        self.assertTrue(children[1].xmlname == 'elem2', "Second element name: %s" % repr(
            children[1].xmlname))
        self.assertTrue(children[1].GetValue(
        ) == 'hello', "Second element value: %s" % repr(children[1].GetValue()))

    def testSTag(self):
        """[40] STag ::= '<' Name (S Attribute)* S? '>' """
        e = XMLEntity("<tag hello='world' ciao=\"tutti\">")
        p = XMLParser(e)
        name, attrs, empty = p.parse_stag()
        self.assertTrue(name == 'tag' and attrs['hello'] == 'world' and attrs[
                        'ciao'] == 'tutti' and empty == False)
        e = XMLEntity("<tag hello/>")
        p = XMLParser(e)
        p.sgmlShorttag = True
        name, attrs, empty = p.parse_stag()
        self.assertTrue(
            name == 'tag' and attrs['@hello'] == 'hello' and empty is True)
        e = XMLEntity("<tag width=20%>")
        p = XMLParser(e)
        p.dontCheckWellFormedness = True
        name, attrs, empty = p.parse_stag()
        self.assertTrue(
            name == 'tag' and attrs['width'] == '20%' and empty is False)

    def testAttribute(self):
        """[41] Attribute ::= Name Eq AttValue """
        s = "a='b'c=\"d\"e=f i j g=h%"
        e = XMLEntity(s)
        m = [('a', 'b'), ('c', 'd')]
        p = XMLParser(e)
        for match in m:
            name, value = p.parse_attribute()
            self.assertTrue(name == match[
                            0], "Attribute name match failed: %s (expected %s)" % (name, match[0]))
            self.assertTrue(value == match[
                            1], "Attribute value match failed: %s (expected %s)" % (value, match[1]))
        try:
            p.parse_s()
            value = p.parse_attribute()
            self.fail("Parsed bad Attribute: %s" % value)
        except XMLWellFormedError:
            pass
        e = XMLEntity(s)
        m = [('a', 'b'), ('c', 'd'), ('e', 'f'),
             ('@i', 'i'), ('@j', 'j'), ('g', 'h%')]
        p = XMLParser(e)
        p.dontCheckWellFormedness = True
        p.sgmlShorttag = True
        for match in m:
            p.parse_s()
            name, value = p.parse_attribute()
            self.assertTrue(name == match[
                            0], "Compatibility: Attribute name match failed: %s (expected %s)" % (name, match[0]))
            self.assertTrue(value == match[
                            1], "Compatibility: Attribute value match failed: %s (expected %s)" % (value, match[1]))
        self.assertTrue(p.the_char is None, "Short parse of ETag tests")

    def testETag(self):
        """[42] ETag ::= '</' Name S? '>' """
        s = "</elem1>elem2></elem3/>"
        e = XMLEntity(s)
        m = ['elem1', 'elem2']
        p = XMLParser(e)
        for match in m:
            value = p.parse_etag(p.the_char != '<')
            self.assertTrue(
                value == match, "ETag name match failed: %s (expected %s)" % (value, match))
        try:
            value = p.parse_etag()
            self.fail("Parsed bad ETag: %s" % value)
        except XMLWellFormedError:
            p.parse_literal('/>')
            pass
        self.assertTrue(p.the_char is None, "Short parse of ETag tests")

    def testContent(self):
        """[43] content ::= CharData? ((element | Reference | CDSect | PI | Comment) CharData?)* """
        s = """a<elem1/>b&amp;c<![CDATA[&amp;]]>d<?x?>e<!-- y -->f"""
        e = XMLEntity(s)
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInContent
        p.element = Element("a")
        p.parse_content()
        children = list(p.element.GetChildren())
        self.assertTrue(
            children[0] == 'a', "First character: %s" % repr(children[0]))
        self.assertTrue(
            isinstance(children[1], Element), "First element: %s" % repr(children[1]))
        self.assertTrue(children[1].xmlname == 'elem1', "First element name: %s" % repr(
            children[1].xmlname))
        self.assertTrue(
            children[2] == 'b&c&amp;def', "Remaining data: %s" % repr(children[2]))

    def testEmptyElemTag(self):
        """[44] EmptyElemTag ::= '<' Name (S Attribute)* S? '/> """
        s = """<elem1/> <elem2 /> <elem3 x="1"/>"""
        e = XMLEntity(s)
        p = XMLParser(e)
        m = [('elem1', {}), ('elem2', {}), ('elem3', {'x': '1'})]
        for match in m:
            try:
                p.parse_empty_elem_tag()
                self.fail("Expected ParseEmptyElem to be unimplemented.")
            except NotImplementedError:
                pass
            name, attrs, emptyFlag = p.parse_stag()
            self.assertTrue(emptyFlag, "Expected empty element tag")
            self.assertTrue(
                name == match[0], "Element name mismatch: %s" % name)
            self.assertTrue(
                attrs == match[1], "Element attrs mismatch: %s" % repr(attrs))
            p.parse_s()
        self.assertTrue(p.the_char is None, "Short parse of empty elements")

    def testElementDecl(self):
        """[45] elementdecl ::= '<!ELEMENT' S Name S contentspec S? '>'	"""
        s = """<!ELEMENT elem1 ANY>
		<!ELEMENT elem2 (#PCDATA)>
		<!ELEMENT elem3 ( A | ( B,C )? | (D,E,F)* | (G,H)+ | (I | (J,K)+)* ) >"""
        e = XMLEntity(s)
        p = XMLParser(e)
        p.checkValidity = True  # ensures that elements are declared in the DTD
        p.dtd = XMLDTD()
        try:
            while True:
                p.parse_element_decl(p.the_char != '<')
                p.parse_s()
        except XMLWellFormedError:
            pass
        etype = p.dtd.GetElementType('elem1')
        self.assertTrue(etype.contentType == ElementType.Any, "First element")
        etype = p.dtd.GetElementType('elem2')
        self.assertTrue(
            etype.contentType == ElementType.Mixed, "Second element")
        etype = p.dtd.GetElementType('elem3')
        self.assertTrue(
            etype.contentType == ElementType.ElementContent, "Third element")
        self.assertTrue(etype.contentModel.children[4].children[
                        1].children[1].name == "K", "Third element model")
        self.assertTrue(
            p.the_char is None, "Short parse on element declarations")

    def testContentSpec(self):
        """[46] contentspec ::= 'EMPTY' | 'ANY' | Mixed | children """
        s = """EMPTY
			ANY
			(#PCDATA)
			(#PCDATA)*
			( #PCDATA | Steve1 | Steve2 )*
			(Particle2|Particle3)?
			(Particle4,Particle5,Particle6)+"""
        e = XMLEntity(s)
        m = [	(ElementType.Empty, None, None, None),
              (ElementType.Any, None, None, None),
              (ElementType.Mixed, XMLChoiceList,
               XMLContentParticle.ZeroOrMore, 0),
              (ElementType.Mixed, XMLChoiceList,
               XMLContentParticle.ZeroOrMore, 0),
              (ElementType.Mixed, XMLChoiceList,
               XMLContentParticle.ZeroOrMore, 2),
              (ElementType.ElementContent, XMLChoiceList,
               XMLContentParticle.ZeroOrOne, 2),
              (ElementType.ElementContent, XMLSequenceList, XMLContentParticle.OneOrMore, 3)]
        p = XMLParser(e)
        for match in m:
            etype = ElementType()
            p.parse_content_spec(etype)
            self.assertTrue(
                etype.contentType == match[0], "Content type mismatch")
            if match[1] is None:
                self.assertTrue(
                    etype.contentModel is None, "Content model type mismatch")
            else:
                self.assertTrue(
                    isinstance(etype.contentModel, match[1]), "Content model type mismatch")
                self.assertTrue(
                    etype.contentModel.occurrence == match[2], "Content model occurrence mismatch")
                self.assertTrue(len(etype.contentModel.children) == match[
                                3], "Number of children in content model mismatch")
            p.parse_s()
        self.assertTrue(
            p.the_char is None, "Incomplete parse in contentspec tests: %s" % repr(p.the_char))

    def testChildren(self):
        """[47] children ::= (choice | seq) ('?' | '*' | '+')? """
        s = """(Particle2|Particle3)?
			(Particle4,Particle5)*
			(Particle6,(Particle7|Particle8),(Particle9,Particle10))+
			Particle1"""
        e = XMLEntity(s)
        m = [	(XMLChoiceList, XMLContentParticle.ZeroOrOne),
              (XMLSequenceList, XMLContentParticle.ZeroOrMore),
              (XMLSequenceList, XMLContentParticle.OneOrMore)]
        p = XMLParser(e)
        for match in m:
            cp = p.parse_children()
            self.assertTrue(isinstance(cp, match[0]), "Particle type mismatch")
            self.assertTrue(cp.occurrence == match[
                            1], "Particle occurrence mismatch, %i (expected %i)" % (cp.occurrence, match[1]))
            p.parse_s()
        try:
            cp = p.parse_children()
            self.fail("Name not allowed outside choice or sequence")
        except XMLFatalError:
            # fails to parse 'Particle1'
            p.parse_literal('Particle1')
        self.assertTrue(
            p.the_char is None, "Incomplete parse in children tests: %s" % repr(p.the_char))

    def testCP(self):
        """[48] cp ::= (Name | choice | seq) ('?' | '*' | '+')? """
        s = """Particle1
			(Particle2|Particle3)?
			(Particle4,Particle5)*
			(Particle6,(Particle7|Particle8),(Particle9,Particle10))+"""
        e = XMLEntity(s)
        m = [	(XMLNameParticle, XMLContentParticle.ExactlyOnce),
              (XMLChoiceList, XMLContentParticle.ZeroOrOne),
              (XMLSequenceList, XMLContentParticle.ZeroOrMore),
              (XMLSequenceList, XMLContentParticle.OneOrMore)]
        p = XMLParser(e)
        for match in m:
            cp = p.parse_cp()
            self.assertTrue(isinstance(cp, match[0]), "Particle type mismatch")
            self.assertTrue(cp.occurrence == match[
                            1], "Particle occurrence mismatch, %i (expected %i)" % (cp.occurrence, match[1]))
            p.parse_s()
        self.assertTrue(
            p.the_char is None, "Incomplete parse in CP tests: %s" % repr(p.the_char))

    def testChoice(self):
        """[49] choice ::= '(' S? cp ( S? '|' S? cp )+ S? ')' """
        s = "(Particle1|Particle2?|Particle3*)( Particle4+ | Particle5 )(Particle6|Particle7+)+(Particle8*)()"
        e = XMLEntity(s)
        m = [[('Particle1', XMLContentParticle.ExactlyOnce), ('Particle2', XMLContentParticle.ZeroOrOne),
              ('Particle3', XMLContentParticle.ZeroOrMore)], [('Particle4', XMLContentParticle.OneOrMore),
                                                              ('Particle5', XMLContentParticle.ExactlyOnce)], [('Particle6', XMLContentParticle.ExactlyOnce),
                                                                                                               ('Particle7', XMLContentParticle.OneOrMore)]]
        p = XMLParser(e)
        for match in m:
            cp = p.parse_choice()
            self.assertTrue(
                isinstance(cp, XMLChoiceList), "Choice list match failed")
            self.assertTrue(
                len(cp.children) == len(match), "Choice list match length mismatch")
            i = 0
            for cpi, mi in zip(cp.children, match):
                self.assertTrue(
                    isinstance(cpi, XMLNameParticle), "Not a name particle")
                self.assertTrue(cpi.name == mi[0], "Particle name mismatch")
                self.assertTrue(
                    cpi.occurrence == mi[1], "Particle occurrence mismatch")
        self.assertTrue(
            p.parse_literal('+'), "Final occurrence parsed in error")
        try:
            cp = p.parse_choice()
            self.fail("Singleton choice not allowed")
        except XMLFatalError:
            # fails to parse ')'
            p.parse_literal(')')
        try:
            cp = p.parse_choice()
            self.fail("Empty choice not allowed")
        except XMLFatalError:
            # fails to parse ')'
            p.parse_literal(')')
        self.assertTrue(
            p.the_char is None, "Incomplete parse in choice tests: %s" % repr(p.the_char))

    def testSeq(self):
        """[50] seq ::= '(' S? cp ( S? ',' S? cp )* S? ')' """
        s = "(Particle1,Particle2?,Particle3*)( Particle4+ , Particle5 )(Particle6+)+()"
        e = XMLEntity(s)
        m = [[('Particle1', XMLContentParticle.ExactlyOnce), ('Particle2', XMLContentParticle.ZeroOrOne),
              ('Particle3', XMLContentParticle.ZeroOrMore)], [('Particle4', XMLContentParticle.OneOrMore),
                                                              ('Particle5', XMLContentParticle.ExactlyOnce)], [('Particle6', XMLContentParticle.OneOrMore)]]
        p = XMLParser(e)
        for match in m:
            cp = p.parse_seq()
            self.assertTrue(
                isinstance(cp, XMLSequenceList), "Sequence match failed")
            self.assertTrue(
                len(cp.children) == len(match), "Sequence match length mismatch")
            i = 0
            for cpi, mi in zip(cp.children, match):
                self.assertTrue(
                    isinstance(cpi, XMLNameParticle), "Not a name particle")
                self.assertTrue(cpi.name == mi[0], "Particle name mismatch")
                self.assertTrue(
                    cpi.occurrence == mi[1], "Particle occurrence mismatch")
        self.assertTrue(
            p.parse_literal('+'), "Final occurrence parsed in error")
        try:
            cp = p.parse_seq()
            self.fail("Empty sequence not allowed")
        except XMLFatalError:
            # fails to parse ')'
            p.parse_literal(')')
        self.assertTrue(
            p.the_char is None, "Incomplete parse in sequence tests: %s" % repr(p.the_char))

    def testMixed(self):
        """[51] Mixed ::= '(' S? '#PCDATA' (S? '|' S? Name)* S? ')*' | '(' S? '#PCDATA' S? ')' """
        s = "(#PCDATA)(#PCDATA)*( #PCDATA | Steve1 | Steve2 )*( #PCDATA |Steve1|Steve2)*(#PCDATA|Steve1)(Steve1|#PCDATA)*"
        e = XMLEntity(s)
        m = [[], [], ['Steve1', 'Steve2'], ['Steve1', 'Steve2']]
        p = XMLParser(e)
        for match in m:
            cp = p.parse_mixed()
            self.assertTrue(
                isinstance(cp, XMLChoiceList), "Mixed must be a choice")
            self.assertTrue(
                cp.occurrence == XMLContentParticle.ZeroOrMore, "Mixed must be '*'")
            self.assertTrue(
                len(cp.children) == len(match), "Particle count mismatch: %s" % str(match))
            for cpi, mi in zip(cp.children, match):
                self.assertTrue(
                    isinstance(cpi, XMLNameParticle), "Mixed particles must be names")
                self.assertTrue(
                    cpi.occurrence == XMLContentParticle.ExactlyOnce, "Mixed occurrence")
                self.assertTrue(cpi.name == mi, "Mixed particle name")
        try:
            values = p.parse_mixed()
            self.fail("Missed trailing *")
        except XMLFatalError:
            # fails to parse ')*'
            p.parse_literal(')')
        try:
            values = p.parse_mixed()
            self.fail("#PCDATA must come first")
        except XMLFatalError:
            # fails to parse '#PCDATA'
            p.parse_literal('Steve1|#PCDATA)*')
        self.assertTrue(
            p.the_char is None, "Incomplete parse in Mixed tests: %s" % repr(p.the_char))

    def testAttlistDecl(self):
        """[52] AttlistDecl ::= '<!ATTLIST' S Name AttDef* S? '>' """
        s = """<!ATTLIST elem attr CDATA 'Steve' attr2 CDATA #IMPLIED>
		<!ATTLIST elem attr3 (1|2|3) '1'>
		 elem2 (1|2|3) >"""
        e = XMLEntity(s)
        p = XMLParser(e)
        p.dtd = XMLDTD()
        try:
            while True:
                p.parse_attlist_decl(p.the_char != '<')
                p.parse_s()
        except XMLWellFormedError:
            pass
        alist = p.dtd.GetAttributeList('elem')
        self.assertTrue(
            alist['attr'].defaultValue == 'Steve', "First attribute")
        self.assertTrue(
            alist['attr2'].presence == XMLAttributeDefinition.Implied, "Second attribute")
        self.assertTrue(
            alist['attr3'].type == XMLAttributeDefinition.Enumeration, "Third attribute")
        alist = p.dtd.GetAttributeList('elem2')
        self.assertTrue(alist is None, "Bad attribute")

    def testAttDef(self):
        """[53] AttDef ::= S Name S AttType S DefaultDecl"""
        s = " attr CDATA 'Steve' attr2 CDATA #IMPLIED attr3 (1|2|3) '1' attr4 #REQUIRED"
        e = XMLEntity(s)
        m = [	('attr', XMLAttributeDefinition.CData, None, XMLAttributeDefinition.Default, 'Steve'),
              ('attr2', XMLAttributeDefinition.CData,
               None, XMLAttributeDefinition.Implied, None),
              ('attr3', XMLAttributeDefinition.Enumeration, {'1': True, '2': True, '3': True}, XMLAttributeDefinition.Default, '1')]
        p = XMLParser(e)
        for match in m:
            a = p.parse_att_def()
            self.assertTrue(
                a.name == match[0], "AttDef match failed: %s (expected %s)" % (a.name, match[0]))
            self.assertTrue(
                a.type == match[1], "AttDef match failed: %i (expected %i)" % (a.type, match[1]))
            self.assertTrue(a.values == match[
                            2], "AttDef match failed: %s (expected %s)" % (a.values, match[2]))
            self.assertTrue(a.presence == match[
                            3], "AttDef match failed: %i (expected %i)" % (a.presence, match[3]))
            self.assertTrue(a.defaultValue == match[
                            4], "AttDef match failed: %s (expected %s)" % (a.defaultValue, match[4]))
        try:
            a = p.parse_att_def()
            self.fail("Parsed bad AttDef: %s" % a.name)
        except XMLFatalError:
            pass

    def testAttType(self):
        """[54] AttType ::= StringType | TokenizedType | EnumeratedType"""
        s = "CDATA ENTITIES NOTATION (Steve) (1 | 2 | 3) NAMES)"
        e = XMLEntity(s)
        m = [(XMLAttributeDefinition.CData, None), (XMLAttributeDefinition.Entities, None), (XMLAttributeDefinition.Notation, {'Steve': True}),
             (XMLAttributeDefinition.Enumeration, {'1': True, '2': True, '3': True})]
        p = XMLParser(e)
        for match in m:
            a = XMLAttributeDefinition()
            p.parse_att_type(a)
            self.assertTrue(a.type == match[
                            0], "Attribute type match failed: %i (expected %i)" % (a.type, match[0]))
            self.assertTrue(a.values == match[
                            1], "Attribute type match failed: %s (expected %s)" % (a.values, match[1]))
            p.parse_s()
        try:
            a = XMLAttributeDefinition()
            value = p.parse_att_type(a)
            self.fail("Parsed bad AttType: %i; %s" % (a.type, a.values))
        except XMLFatalError:
            pass

    def testStringType(self):
        """[55] StringType ::= 'CDATA' """
        s = "CDATA ID"
        e = XMLEntity(s)
        m = [(XMLAttributeDefinition.CData, None)]
        p = XMLParser(e)
        for match in m:
            a = XMLAttributeDefinition()
            p.parse_string_type(a)
            self.assertTrue(a.type == match[
                            0], "String type match failed: %i (expected %i)" % (a.type, match[0]))
            self.assertTrue(a.values == match[
                            1], "String type match failed: %s (expected %s)" % (a.values, match[1]))
            p.parse_s()
        try:
            a = XMLAttributeDefinition()
            value = p.parse_string_type(a)
            self.fail("Parsed bad StringType: %i; %s" % (a.type, a.values))
        except XMLFatalError:
            pass

    def testTokenizedType(self):
        """[56] TokenizedType ::= 'ID' | 'IDREF' | 'IDREFS' | 'ENTITY' | 'ENTITIES'	 | 'NMTOKEN' | 'NMTOKENS' """
        s = "ID IDREF IDREFS ENTITY ENTITIES NMTOKEN NMTOKENS NAME"
        e = XMLEntity(s)
        m = [(XMLAttributeDefinition.ID, None), (XMLAttributeDefinition.IDRef, None), (XMLAttributeDefinition.IDRefs, None),
             (XMLAttributeDefinition.Entity, None), (XMLAttributeDefinition.Entities,
                                                     None), (XMLAttributeDefinition.NmToken, None),
             (XMLAttributeDefinition.NmTokens, None)]
        p = XMLParser(e)
        for match in m:
            a = XMLAttributeDefinition()
            p.parse_tokenized_type(a)
            self.assertTrue(a.type == match[
                            0], "Tokenized type match failed: %i (expected %i)" % (a.type, match[0]))
            self.assertTrue(a.values == match[
                            1], "Tokenized type match failed: %s (expected %s)" % (a.values, match[1]))
            p.parse_s()
        try:
            a = XMLAttributeDefinition()
            value = p.parse_tokenized_type(a)
            self.fail("Parsed bad Tokenized: %i; %s" % (a.type, a.values))
        except XMLFatalError:
            pass

    def testEnumeratedType(self):
        """[57] EnumeratedType ::= NotationType | Enumeration """
        s = "NOTATION (Steve1)NOTATION (Steve1|Steve2)(1|2|3)NOTATION (1|2|3)"
        e = XMLEntity(s)
        m = [(XMLAttributeDefinition.Notation, {'Steve1': True}), (XMLAttributeDefinition.Notation, {
            'Steve1': True, 'Steve2': True}), (XMLAttributeDefinition.Enumeration, {'1': True, '2': True, '3': True})]
        p = XMLParser(e)
        for match in m:
            a = XMLAttributeDefinition()
            p.parse_enumerated_type(a)
            self.assertTrue(a.type == match[
                            0], "Enumerated type match failed: %i (expected %i)" % (a.type, match[0]))
            self.assertTrue(a.values == match[
                            1], "Enumerated type match failed: %s (expected %s)" % (a.values, match[1]))
        try:
            a = XMLAttributeDefinition()
            value = p.parse_enumerated_type(a)
            self.fail("Parsed bad EnumeratedType: %i; %s" % (a.type, a.values))
        except XMLFatalError:
            pass

    def testNotationType(self):
        """[58] NotationType ::= 'NOTATION' S '(' S? Name (S? '|' S? Name)* S? ')'"""
        s = "NOTATION (Steve1)NOTATION (Steve1|Steve2|Steve3)NOTATION ( Steve1 ) ( Steve1 | Steve2 | Steve3 )NOTATION(Steve1|Steve2)"
        e = XMLEntity(s)
        m = [{'Steve1': True}, {'Steve1': True, 'Steve2': True, 'Steve3': True}, {
            'Steve1': True}, {'Steve1': True, 'Steve2': True, 'Steve3': True}]
        p = XMLParser(e)
        for match in m:
            value = p.parse_notation_type(p.the_char != 'N')
            self.assertTrue(
                value == match, "NotationType match failed: %s (expected %s)" % (value, match))
        try:
            value = p.parse_notation_type()
            self.fail("Parsed bad NotationType: %s" % value)
        except XMLFatalError:
            pass

    def testEnumeration(self):
        """[59] Enumeration	   ::=   	'(' S? Nmtoken (S? '|' S? Nmtoken)* S? ')' """
        s = "(Steve1)(Steve1|Steve2|3Steve)( Steve1 )( Steve1 | Steve2 | 3Steve )(Steve1|Steve 2)"
        e = XMLEntity(s)
        m = [{'Steve1': True}, {'Steve1': True, 'Steve2': True, '3Steve': True}, {
            'Steve1': True}, {'Steve1': True, 'Steve2': True, '3Steve': True}]
        p = XMLParser(e)
        for match in m:
            value = p.parse_enumeration()
            self.assertTrue(
                value == match, "Enumeration match failed: %s (expected %s)" % (value, match))
        try:
            value = p.parse_enumeration()
            self.fail("Parsed bad Enumeration: %s" % value)
        except XMLFatalError:
            pass

    def testDefaultDecl(self):
        """[60] DefaultDecl ::= '#REQUIRED' | '#IMPLIED' | (('#FIXED' S)? AttValue) """
        s = "#REQUIRED #IMPLIED #FIXED 'Steve' 'Steve'Steve"
        e = XMLEntity(s)
        m = [(XMLAttributeDefinition.Required, None), (XMLAttributeDefinition.Implied, None), (XMLAttributeDefinition.Fixed, 'Steve'),
             (XMLAttributeDefinition.Default, 'Steve')]
        p = XMLParser(e)
        for match in m:
            a = XMLAttributeDefinition()
            p.parse_default_decl(a)
            self.assertTrue(a.presence == match[
                            0], "DefaultDecl declaration match failed: %i (expected %i)" % (a.presence, match[0]))
            self.assertTrue(a.defaultValue == match[
                            1], "DefaultDecl value match failed: %s (expected %s)" % (a.defaultValue, match[1]))
            p.parse_s()
        try:
            a = XMLAttributeDefinition()
            p.parse_default_decl(a)
            self.fail("Parsed bad DefaultDecl: (%i,%s)" %
                      (a.presence, a.defaultValue))
        except XMLFatalError:
            pass

    def testConditionalSect(self):
        """[61] conditionalSect ::= includeSect | ignoreSect"""
        s = "<![%include;[ <!ENTITY included 'yes'> <![ IGNORE [ <!ENTITY ignored 'no'> ]]> ]]>"
        e = XMLEntity(s)
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('include', 'INCLUDE'))
        p.checkValidity = True
        p.refMode = XMLParser.RefModeInDTD
        try:
            p.parse_conditional_sect()
            self.assertTrue(
                p.the_char is None, "Short parse on ConditionalSect: %s" % p.the_char)
            self.assertTrue(
                p.dtd.GetEntity('included').definition == 'yes', "included entity declaration")
            self.assertTrue(
                p.dtd.GetEntity('ignored') == None, "ignored entity declaration")
        except XMLWellFormedError, e:
            self.fail("parse_conditional_sect positive test: %s\n%s" %
                      (s, str(e)))

    def testIncludeSect(self):
        """[62] includeSect ::= '<![' S? 'INCLUDE' S? '[' extSubsetDecl ']]>' """
        for s in ["<![INCLUDE[]]>", "<![ INCLUDE [ <?stuff?> ]]>", "<![ INCLUDE [<![IGNORE[ included ]]> ]]>",
                  "<![%include;[]]>"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.dtd = XMLDTD()
            p.dtd.DeclareEntity(XMLParameterEntity('include', 'INCLUDE'))
            p.checkValidity = True
            p.refMode = XMLParser.RefModeInDTD
            try:
                p.parse_include_sect()
                self.assertTrue(
                    p.the_char is None, "Short parse on IncludeSect: %s" % p.the_char)
            except XMLWellFormedError, e:
                self.fail("parse_include_sect positive test: %s\n%s" %
                          (s, str(e)))
        for s in [" <![INCLUDE[]>", "<! [INCLUDE[]]>", "<![INCLUDE[] ]>"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.refMode = XMLParser.RefModeInDTD
            try:
                p.parse_include_sect()
                self.fail(
                    "parse_include_sect negative well-formedness test: %s" % s)
            except XMLWellFormedError:
                pass
        for s in ["<![ %include1; <?stuff?> ]]>", "%include2; [ <!--stuff--> ]]>",
                  "<![ INCLUDE [ <?stuff?> %include3;"
                  ]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.refMode = XMLParser.RefModeInContent
            p.dtd = XMLDTD()
            p.dtd.DeclareEntity(XMLParameterEntity('include1', 'INCLUDE ['))
            p.dtd.DeclareEntity(XMLParameterEntity('include2', '<![INCLUDE '))
            p.dtd.DeclareEntity(
                XMLParameterEntity('include3', '<?included?> ]]>'))
            p.checkValidity = True
            p.raiseValidityErrors = True
            p.refMode = XMLParser.RefModeInDTD
            try:
                p.parse_s()
                p.parse_include_sect()
                self.fail("parse_include_sect negative validity test: %s" % s)
            except XMLWellFormedError, e:
                logging.info(str(e))
                self.fail(
                    "parse_include_sect spurious well-formed error: %s" % s)
            except XMLValidityError:
                pass

    def testIgnoreSect(self):
        """[63] ignoreSect ::= '<![' S? 'IGNORE' S? '[' ignoreSectContents* ']]>' """
        for s in ["<![IGNORE[]]>", "<![ IGNORE [ stuff ]]>", "<![ IGNORE [<![INCLUDE[ ignored ]]> ]]>",
                  "<![%ignore;[]]>"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.dtd = XMLDTD()
            p.dtd.DeclareEntity(XMLParameterEntity('ignore', 'IGNORE'))
            p.checkValidity = True
            p.refMode = XMLParser.RefModeInDTD
            try:
                p.parse_ignore_sect()
                self.assertTrue(
                    p.the_char is None, "Short parse on IgnoreSect: %s" % p.the_char)
            except XMLWellFormedError:
                self.fail("parse_ignore_sect positive test: %s" % s)
        for s in [" <![IGNORE[]>", "<! [IGNORE[]]>", "<![IGNORE[] ]>"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.refMode = XMLParser.RefModeInDTD
            try:
                p.parse_ignore_sect()
                self.fail(
                    "parse_ignore_sect negative well-formedness test: %s" % s)
            except XMLWellFormedError:
                pass
        for s in ["<![ %ignore1; stuff ]]>", "%ignore2; [ stuff ]]>",
                  # "<![ IGNORE [ stuff %ignore3;" - this PE is ignored so we can't test this
                  ]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.refMode = XMLParser.RefModeInContent
            p.dtd = XMLDTD()
            p.dtd.DeclareEntity(XMLParameterEntity('ignore1', 'IGNORE ['))
            p.dtd.DeclareEntity(XMLParameterEntity('ignore2', '<![IGNORE '))
            p.dtd.DeclareEntity(XMLParameterEntity('ignore3', 'ignored ]]>'))
            p.checkValidity = True
            p.raiseValidityErrors = True
            p.refMode = XMLParser.RefModeInDTD
            try:
                p.parse_s()
                p.parse_ignore_sect()
                self.fail("parse_ignore_sect negative validity test: %s" % s)
            except XMLWellFormedError, e:
                logging.info(str(e))
                self.fail("parse_ignore_sect spurious well-formed error: %s" % s)
            except XMLValidityError:
                pass

    def testIgnoreSectContents(self):
        """[64] ignoreSectContents ::= Ignore ('<![' ignoreSectContents ']]>' Ignore)* """
        s = "preamble<![ INCLUDE [ %x; <![IGNORE[ also ignored ]]>]]> also ignored]]>end"
        e = XMLEntity(s)
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('x', 'bad'))
        p.parse_ignore_sect_contents()
        p.parse_literal(']]>')
        self.assertTrue(
            p.parse_name() == 'end', "Failed to parse ignore section contents")

    def testIgnore(self):
        """[65] Ignore ::= Char* - (Char* ('<![' | ']]>') Char*) """
        s = "<!FIRST%x;1st]]>second<![third]]3rd<!3rd<3rd]3rd"
        e = XMLEntity(s)
        # These tests are a bit odd because we follow the entity and not the parser
        # so we expect the trailing markup to be consumed; we check the_char too
        # to be sure.
        m = [('<!FIRST%x;1st]]>', ']'), ('second<![', '<'),
             ('third]]3rd<!3rd<3rd]3rd', None)]
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('x', 'bad'))
        pos = 0
        for match, c in m:
            p.parse_ignore()
            self.assertTrue(
                p.the_char == c, "Parser position: %s (expected %s)" % (p.the_char, c))
            self.assertTrue(s[pos:e.linePos - 1] == match,
                            "Match failed: %s (expected %s)" % (s[pos:e.linePos - 1], match))
            p.next_char()
            pos = pos + len(match)

    def testCharRef(self):
        """[66] CharRef ::= '&#' [0-9]+ ';'  |  '&#x' [0-9a-fA-F]+ ';' """
        for m in (XMLParser.RefModeInContent, XMLParser.RefModeInAttributeValue, XMLParser.RefModeInEntityValue):
            e = XMLEntity("&#xe9;")
            p = XMLParser(e)
            p.refMode = m
            data = p.parse_char_ref()
            self.assertTrue(
                data == u'\xe9', "parse_char_ref failed to interpret hex character reference: %s" % data)
            self.assertTrue(
                p.the_char is None, "Short parse on CharRef: %s" % p.the_char)
        e = XMLEntity("&#xe9;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeAsAttributeValue
        data = p.parse_char_ref()
        self.assertTrue(
            data == "&#xe9;", "parse_char_ref AsAttribute: %s" % data)
        self.assertTrue(
            p.the_char is None, "Short parse on CharRef: %s" % p.the_char)
        e = XMLEntity("&#xe9;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInDTD
        try:
            data = p.parse_char_ref()
            self.fail("parse_char_ref InDTD")
        except XMLForbiddenEntityReference:
            pass
        e = XMLEntity("#233;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInContent
        data = p.parse_char_ref(True)
        self.assertTrue(
            data == u'\xe9', "parse_char_ref failed to interpret decimal character reference: %s" % data)
        self.assertTrue(
            p.the_char is None, "Short parse on CharRef: %s" % p.the_char)
        for s in [" &#xe9;", "& #xe9;", "&# xe9;", "&#xe 9;", "&#xe9 ;", "&#e9;", "&#xg9;", "&#1;", "&#;", "&#x;"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.refMode = XMLParser.RefModeInContent
            try:
                p.parse_char_ref()
                self.fail("parse_char_ref negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testReference(self):
        """[67] Reference ::= EntityRef | CharRef """
        e = XMLEntity("&animal;")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLGeneralEntity('animal', 'dog'))
        p.refMode = XMLParser.RefModeInContent
        data = p.parse_reference()
        self.assertTrue(
            data == '', "parse_reference failed to interpret entity reference")
        self.assertTrue(
            p.parse_name() == 'dog', "Failed to replace Entity in Content")
        self.assertTrue(p.the_char is None, "Short parse on EntityRef")
        e = XMLEntity("&#xe9;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInContent
        data = p.parse_reference()
        self.assertTrue(
            data == u'\xe9', "parse_reference failed to interpret character reference: %s" % data)
        self.assertTrue(
            p.the_char is None, "Short parse on EntityRef: %s" % p.the_char)
        for s in [" &animal;", "& animal;", "&animal ;", "animal", "#xE9"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_reference()
                self.fail("parse_reference negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testEntityRef(self):
        """[68] EntityRef ::= '&' Name ';'	"""
        e = XMLEntity("&amp;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInContent
        self.assertTrue(
            p.parse_entity_ref() == '&', "Predefined entity not recognized in Content")
        self.assertTrue(
            p.the_char is None, "Short parse on Entity replacement text")
        e = XMLEntity("&animal;")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLGeneralEntity('animal', 'dog'))
        p.refMode = XMLParser.RefModeInContent
        self.assertTrue(
            p.parse_entity_ref() == '', "EntityRef not recognized in Content")
        # This should result in the entity value being expanded into the stream
        self.assertTrue(
            p.parse_name() == 'dog', "Failed to replace Entity in Content")
        self.assertTrue(
            p.the_char is None, "Short parse on Entity replacement text")
        e = XMLEntity("animal;")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLGeneralEntity('animal', 'dog'))
        p.refMode = XMLParser.RefModeInAttributeValue
        self.assertTrue(
            p.parse_entity_ref(True) == '', "EntityRef not recognized in Attribute Value")
        # This should result in the entity value being expanded into the stream
        self.assertTrue(
            p.parse_name() == 'dog', "Failed to replace Entity in Attribute Vaue")
        self.assertTrue(
            p.the_char is None, "Short parse on Entity replacement text")
        e = XMLEntity("&animal;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeAsAttributeValue
        try:
            p.parse_entity_ref()
            self.fail("EntityRef recognized as Attribute Value")
        except XMLForbiddenEntityReference:
            pass
        e = XMLEntity("&animal;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInEntityValue
        data = p.parse_entity_ref()
        self.assertTrue(
            data == '&animal;', "EntityRef recognized in EntityValue: %s" % data)
        self.assertTrue(p.the_char is None, "Short parse on EntityRef")
        e = XMLEntity("&animal;")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInDTD
        try:
            p.parse_entity_ref()
            self.fail("EntityRef recognized in DTD")
        except XMLForbiddenEntityReference:
            pass
        e = XMLEntity("<element attribute='a-&EndAttr;>")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('EndAttr', "27'"))
        try:
            p.parse_stag()
            self.fail("EntityRef quote test failed in attribute value")
        except XMLWellFormedError:
            pass

    def testPEReference(self):
        """[69] PEReference ::= '%' Name ';' """
        e = XMLEntity("%animal;")
        p = XMLParser(e)
        p.checkValidity = True
        p.refMode = XMLParser.RefModeInContent
        data = p.parse_pe_reference()
        self.assertTrue(
            data == '%animal;', "PEReference recognized in content: %s" % data)
        self.assertTrue(p.the_char is None, "Short parse on PEReference")
        e = XMLEntity("%animal;")
        p = XMLParser(e)
        p.checkValidity = True
        p.refMode = XMLParser.RefModeInAttributeValue
        self.assertTrue(p.parse_pe_reference() == '%animal;',
                        "PEReference recognized in attribute value")
        self.assertTrue(p.the_char is None, "Short parse on PEReference")
        e = XMLEntity("%animal;")
        p = XMLParser(e)
        p.checkValidity = True
        p.refMode = XMLParser.RefModeAsAttributeValue
        self.assertTrue(p.parse_pe_reference() == "%animal;",
                        "PEReference recognized as attribute value")
        self.assertTrue(p.the_char is None, "Short parse on PEReference")
        e = XMLEntity("%animal;")
        p = XMLParser(e)
        p.checkValidity = True
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('animal', 'dog'))
        p.refMode = XMLParser.RefModeInEntityValue
        self.assertTrue(
            p.parse_pe_reference() == '', "PEReference not recognized in entity value")
        # This should result in the entity value being expanded into the stream
        self.assertTrue(
            p.parse_name() == 'dog', "Failed to replace PE in entity value")
        self.assertTrue(
            p.the_char is None, "Short parse on PEReference replacement text")
        e = XMLEntity("%animal;")
        p = XMLParser(e)
        p.checkValidity = True
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('animal', 'dog'))
        p.refMode = XMLParser.RefModeInDTD
        self.assertTrue(
            p.parse_pe_reference() == '', "PEReference not recognized in DTD")
        # This should result in the entity value being expanded into the stream
        # with surrounding spaces
        self.assertTrue(
            p.parse_s() == ' ', "Missing leading space on PE replacement text")
        self.assertTrue(p.parse_name() == 'dog', "Failed to replace PE in DTD")
        self.assertTrue(
            p.parse_s() == ' ', "Missing trailing space on PE replacement text")
        self.assertTrue(p.the_char is None, "Short parse on PEReference")
        e = XMLEntity('<!ENTITY WhatHeSaid "He said %YN;" >')
        p = XMLParser(e)
        p.checkValidity = True
        p.dtd = XMLDTD()
        p.dtd.DeclareEntity(XMLParameterEntity('YN', '"Yes"'))
        try:
            ge = p.parse_entity_decl()
            # This should result in the entity value being expanded into the
            # stream with surrounding spaces
            self.assertTrue(ge.definition == 'He said "Yes"',
                            "PEReference quote test failed in entity value: %s" % ge.definition)
            self.assertTrue(
                p.the_char is None, "Short parse on PEReference in entity declaration")
        except XMLWellFormedError:
            self.fail("PEReference quote test failed in entity value")

    def testEntityDecl(self):
        """[70] EntityDecl ::= GEDecl | PEDecl """
        e = XMLEntity("<!ENTITY Steve 'SteveValue'>")
        p = XMLParser(e)
        ed = p.parse_entity_decl()
        self.assertTrue(isinstance(ed, XMLGeneralEntity),
                        "parse_entity_decl failed to return GeneralEntity")
        self.assertTrue(
            ed.name == 'Steve', "Failed to parse general entity name")
        self.assertTrue(p.the_char is None, "Short parse on EntityDecl")
        e = XMLEntity(" % Steve 'SteveValue'>")
        p = XMLParser(e)
        ed = p.parse_entity_decl(True)
        self.assertTrue(isinstance(ed, XMLParameterEntity),
                        "parse_entity_decl failed to return ParameterEntity")
        self.assertTrue(
            ed.name == 'Steve', "Failed to parse parameter entity name")
        self.assertTrue(p.the_char is None, "Short parse on EntityDecl")

    def testGEDecl(self):
        """[71] GEDecl ::= '<!ENTITY' S Name S EntityDef S? '>' """
        e = XMLEntity("<!ENTITY Steve 'SteveValue'>")
        p = XMLParser(e)
        ge = p.parse_ge_decl()
        self.assertTrue(
            isinstance(ge, XMLGeneralEntity), "parse_ge_decl failed to return GeneralEntity")
        self.assertTrue(
            ge.name == 'Steve', "Failed to parse general entity name")
        self.assertTrue(
            ge.definition == 'SteveValue', "Failed to parse general entity value")
        self.assertTrue(p.the_char is None, "Short parse on GEDecl")
        e = XMLEntity("Steve PUBLIC 'Steve' '/home/steve.txt' NDATA SteveN  >")
        p = XMLParser(e)
        ge = p.parse_ge_decl(True)
        self.assertTrue(ge.definition.public == 'Steve',
                        "parse_ge_decl failed to parse external public ID")
        self.assertTrue(ge.definition.system == '/home/steve.txt',
                        "parse_ge_decl failed to parse external system ID")
        self.assertTrue(
            ge.notation == 'SteveN', "parse_ge_decl failed to parse unparsed entity notation")
        self.assertTrue(p.the_char is None, "Short parse on GEDecl")
        for s in ["<!entity Steve 'v'>", "<!ENTITYSteve 'v'>",
                  "<!ENTITY Steve PUBLIC 'Steve' '/home/steve.txt'NDATA SteveN >",
                  "  Steve PUBLIC 'Steve' '/home/steve.txt' NDATA SteveN  >"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                ge = p.parse_ge_decl(s[0] != '<')
                self.fail("GEDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testPEDecl(self):
        """[72] PEDecl ::= '<!ENTITY' S '%' S Name S PEDef S? '>' """
        e = XMLEntity("<!ENTITY % Steve 'SteveValue'>")
        p = XMLParser(e)
        p.refMode = XMLParser.RefModeInDTD
        pe = p.parse_pe_decl()
        self.assertTrue(isinstance(pe, XMLParameterEntity),
                        "parse_pe_decl failed to return ParameterEntity")
        self.assertTrue(
            pe.name == 'Steve', "Failed to parse parameter entity name")
        self.assertTrue(
            pe.definition == 'SteveValue', "Failed to parse parameter entity value")
        self.assertTrue(p.the_char is None, "Short parse on PEDecl")
        e = XMLEntity("% Steve PUBLIC 'Steve' '/home/steve.txt'   >")
        p = XMLParser(e)
        pe = p.parse_pe_decl(True)
        self.assertTrue(pe.definition.public == 'Steve',
                        "parse_pe_decl failed to parse external public ID")
        self.assertTrue(pe.definition.system == '/home/steve.txt',
                        "parse_pe_decl failed to parse external system ID")
        self.assertTrue(p.the_char is None, "Short parse on PEDecl")
        for s in ["<!entity % Steve 'v'>", "<!ENTITY% Steve 'v'>", "<!ENTITY %Steve 'v'>", "<!ENTITY % Steve'v'>",
                  "  % Steve PUBLIC 'Steve' '/home/steve.txt'   >"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                pe = p.parse_pe_decl(s[0] != '<')
                self.fail("PEDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testEntityDef(self):
        """[73] EntityDef ::= EntityValue | (ExternalID NDataDecl?) """
        e = XMLEntity("'Steve'")
        p = XMLParser(e)
        ge = XMLGeneralEntity()
        p.parse_entity_def(ge)
        self.assertTrue(type(ge.definition) in StringTypes,
                        "parse_entity_def failed to for internal entity")
        self.assertTrue(
            ge.definition == 'Steve', "Failed to parse internal entity value")
        self.assertTrue(
            ge.notation is None, "Found notation for internal entity")
        self.assertTrue(p.the_char is None, "Short parse on EntityDef")
        e = XMLEntity("PUBLIC 'Steve' '/home/steve.txt'")
        p = XMLParser(e)
        ge = XMLGeneralEntity()
        p.parse_entity_def(ge)
        self.assertTrue(isinstance(ge.definition, XMLExternalID),
                        "parse_entity_def failed for external entity")
        self.assertTrue(ge.definition.public == 'Steve',
                        "parse_entity_def failed to parse external public ID")
        self.assertTrue(ge.definition.system == '/home/steve.txt',
                        "parse_entity_def failed to parse external system ID")
        self.assertTrue(
            ge.notation is None, "Found notation for internal entity")
        self.assertTrue(p.the_char is None, "Short parse on EntityDef")
        e = XMLEntity("SYSTEM '/path' NDATA SteveN")
        p = XMLParser(e)
        ge = XMLGeneralEntity()
        p.parse_entity_def(ge)
        self.assertTrue(
            ge.definition.public is None, "parse_entity_def found spurious public ID")
        self.assertTrue(ge.definition.system == '/path',
                        "parse_entity_def failed to parse external system ID")
        self.assertTrue(
            ge.notation == 'SteveN', "Failed to find notation for unparsed external entity")
        self.assertTrue(p.the_char is None, "Short parse on EntityDef")
        for s in ["NDATA 'SteveN'", " 'Steve'", " SYSTEM '/path'"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            ge = XMLGeneralEntity()
            try:
                p.parse_entity_def(ge)
                self.fail("EntityDef negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testPEDef(self):
        """[74] PEDef ::= EntityValue | ExternalID """
        e = XMLEntity("PUBLIC 'Steve' '/home/steve.txt'")
        p = XMLParser(e)
        pe = XMLParameterEntity()
        p.parse_pe_def(pe)
        self.assertTrue(isinstance(pe.definition, XMLExternalID),
                        "parse_pe_def failed to return XMLExternalID instance")
        self.assertTrue(
            pe.definition.public == 'Steve', "Failed to parse external public ID")
        self.assertTrue(
            pe.definition.system == '/home/steve.txt', "Failed to parse external system ID")
        self.assertTrue(p.the_char is None, "Short parse on PEDef")
        e = XMLEntity("'Steve'")
        p = XMLParser(e)
        pe = XMLParameterEntity()
        p.parse_pe_def(pe)
        self.assertTrue(
            type(pe.definition) in StringTypes, "parse_pe_def failed to return String value")
        self.assertTrue(
            pe.definition == 'Steve', "Failed to parse simple entity value")
        self.assertTrue(p.the_char is None, "Short parse on PEDef")
        e = XMLEntity('"Caf&#xE9;s &amp; Bars"')
        p = XMLParser(e)
        pe = XMLParameterEntity()
        p.parse_pe_def(pe)
        self.assertTrue(
            type(pe.definition) in StringTypes, "parse_pe_def failed to return String value")
        self.assertTrue(pe.definition == u'Caf\xe9s &amp; Bars',
                        "Failed to replace character entities: %s" % repr(pe.definition))
        self.assertTrue(p.the_char is None, "Short parse on PEDef")
        for s in ["Steve", "Caf&#xE9;s &amp; Bars", "PUBLIC 'Steve'"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            pe = XMLParameterEntity()
            try:
                p.parse_pe_def(pe)
                self.fail("PEDef negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testExternalID(self):
        """[75] ExternalID ::= 'SYSTEM' S SystemLiteral | 'PUBLIC' S PubidLiteral S SystemLiteral """
        e = XMLEntity("PUBLIC 'Steve' '/home/steve.txt'")
        p = XMLParser(e)
        xid = p.parse_external_id()
        self.assertTrue(
            xid.public == 'Steve', "Failed to parse external public ID")
        self.assertTrue(
            xid.system == '/home/steve.txt', "Failed to parse external system ID")
        self.assertTrue(p.the_char is None, "Short parse on ExternalID")
        e = XMLEntity("SYSTEM  '/home/steve.txt'")
        p = XMLParser(e)
        xid = p.parse_external_id()
        self.assertTrue(
            xid.public is None, "Failed to parse external empty public ID")
        self.assertTrue(
            xid.system == '/home/steve.txt', "Failed to parse external system ID")
        self.assertTrue(p.the_char is None, "Short parse on ExternalID")
        for s in ["PUBLIC 'Steve'", "'Steve'", " SYSTEM '/path'", "SYSTEM'/path'", "PUBLIC'Steve' '/path'",
                  "PUBLIC 'Steve''/path'"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                xid = p.parse_external_id()
                self.fail("ExternalID negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testNDataDecl(self):
        """[76] NDataDecl ::= S 'NDATA' S Name """
        e = XMLEntity("  NDATA Steve")
        p = XMLParser(e)
        self.assertTrue(
            p.parse_ndata_decl() == "Steve", "Failed to parse NData declaration")
        self.assertTrue(p.the_char is None, "Short parse on NData declaration")
        e = XMLEntity(" Steve")
        p = XMLParser(e)
        self.assertTrue(p.parse_ndata_decl(True) == "Steve",
                        "Failed to parse NData declaration (no literal)")
        self.assertTrue(p.the_char is None, "Short parse on NData declaration")
        for s in ["NDATA Steve", " MDATA Steve", "NDATASteve"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_ndata_decl()
                self.fail("NDataDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testTextDecl(self):
        """[77] TextDecl ::= '<?xml' VersionInfo? EncodingDecl S? '?>' """
        e = XMLEntity("<?xml version='1.0' encoding='latin-1'  ?>")
        p = XMLParser(e)
        t = p.parse_text_decl()
        self.assertTrue(t.version == "1.0")
        self.assertTrue(
            t.encoding == "latin-1", "Failed to parse encoding in text declaration")
        self.assertTrue(p.the_char is None, "Short parse on TextDecl")
        e = XMLEntity('<?xml encoding = "latin-1"?>')
        p = XMLParser(e)
        t = p.parse_text_decl()
        self.assertTrue(t.version is None)
        self.assertTrue(
            t.encoding == "latin-1", "Failed to parse encoding in text declaration")
        self.assertTrue(p.the_char is None, "Short parse on TextDecl")
        for s in ["<?xml version='1.0' ?>"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_encoding_decl()
                self.fail("TextDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    # There is no method for parsing production [78]

    # There is no production [79]

    def testEncodingDecl(self):
        """[80] EncodingDecl ::= S 'encoding' Eq ('"' EncName '"' | "'" EncName "'" ) """
        e = XMLEntity("  encoding = 'latin-1'")
        p = XMLParser(e)
        self.assertTrue(
            p.parse_encoding_decl() == "latin-1", "Failed to parse encoding declaration")
        self.assertTrue(p.the_char is None, "Short parse on EncodingDecl")
        e = XMLEntity(" = 'latin-1'")
        p = XMLParser(e)
        self.assertTrue(p.parse_encoding_decl(True) == "latin-1",
                        "Failed to parse encoding declaration (no literal)")
        self.assertTrue(p.the_char is None, "Short parse on EncodingDecl")
        e = XMLEntity(' encoding="latin-1"')
        p = XMLParser(e)
        self.assertTrue(
            p.parse_encoding_decl() == "latin-1", "Failed to parse encoding declaration")
        self.assertTrue(p.the_char is None, "Short parse on EncodingDecl")
        for s in ["encoding = 'latin-1'", " decoding='latin-1'", " encoding=latin-1"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_encoding_decl()
                self.fail("EncodingDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testEncName(self):
        """[81] EncName ::= [A-Za-z] ([A-Za-z0-9._] | '-')* """
        e = XMLEntity(
            "UTF-8 UTF-16 ISO-10646-UCS-2 ISO-10646-UCS-4 Shift_JIS -8 _JIS .Private x.Private")
        result = ["UTF-8", "UTF-16", "ISO-10646-UCS-2",
                  "ISO-10646-UCS-4", "Shift_JIS", "JIS", "Private", "x.Private"]
        p = XMLParser(e)
        i = 0
        while p.the_char != None:
            ename = p.parse_enc_name()
            if ename:
                self.assertTrue(
                    ename == result[i], "%s parsed, expected %s" % (ename, result[i]))
                p.parse_s()
                i = i + 1
            else:
                p.next_char()

    def testCaseNotationDecl(self):
        """[82] NotationDecl ::= '<!NOTATION' S Name S (ExternalID | PublicID) S? '>'"""
        e = XMLEntity("<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'>")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.parse_notation_decl()
        n = p.dtd.GetNotation('SteveN')
        self.assertTrue(n.name == 'SteveN', "Failed to parse notation name")
        self.assertTrue(
            n.external_id.public == 'Steve', "Failed to parse notation public ID")
        self.assertTrue(
            n.external_id.system == '/home/steve.txt', "Failed to parse notation system ID")
        self.assertTrue(p.the_char is None, "Short parse on NotationDecl")
        e = XMLEntity(" SteveN PUBLIC 'Steve' >")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.parse_notation_decl(True)
        n = p.dtd.GetNotation('SteveN')
        self.assertTrue(n.name == 'SteveN', "Failed to parse notation name")
        self.assertTrue(
            n.external_id.public == 'Steve', "Failed to parse notation public ID")
        self.assertTrue(
            n.external_id.system is None, "Failed to parse empty notation system ID")
        self.assertTrue(p.the_char is None, "Short parse on NotationDecl")
        e = XMLEntity("<!NOTATION SteveN SYSTEM  '/home/steve.txt' >")
        p = XMLParser(e)
        p.dtd = XMLDTD()
        p.parse_notation_decl()
        n = p.dtd.GetNotation('SteveN')
        self.assertTrue(n.name == 'SteveN', "Failed to parse notation name")
        self.assertTrue(
            n.external_id.public is None, "Failed to parse empty notation public ID")
        self.assertTrue(
            n.external_id.system == '/home/steve.txt', "Failed to parse notation system ID")
        self.assertTrue(p.the_char is None, "Short parse on NotationDecl")
        for s in ["SteveN PUBLIC 'Steve' >", " 'SteveN' PUBLIC 'Steve' >", "SteveN 'Steve' >",
                  "SteveN PUBLIC >", "SteveN SYSTEM>", "SteveN SYSTEM 'Steve' '/path'>", "SteveN PUBLIC 'Steve' "]:
            e = XMLEntity(s)
            p = XMLParser(e)
            p.dtd = XMLDTD()
            try:
                p.parse_notation_decl(True)
                self.fail("NotationDecl negative test: %s" % s)
            except XMLWellFormedError:
                pass

    def testCasePublicID(self):
        """[83] PublicID ::= 'PUBLIC' S PubidLiteral"""
        e = XMLEntity("PUBLIC 'Steve'")
        p = XMLParser(e)
        self.assertTrue(
            p.parse_public_id() == 'Steve', "Failed to parse Public ID")
        self.assertTrue(p.the_char is None, "Short parse on Public ID")
        for s in [" PUBLIC 'Steve'", "'Steve'", "PUBLIC'Steve'", "Public 'Steve'"]:
            e = XMLEntity(s)
            p = XMLParser(e)
            try:
                p.parse_public_id()
                self.fail("PublicID negative test: %s" % s)
            except XMLWellFormedError:
                pass


class ElementTests(unittest.TestCase):

    def testCaseConstructor(self):
        e = Element(None)
        self.assertTrue(e.xmlname == None, 'element name on construction')
        self.assertTrue(
            e.GetDocument() is None, 'document set on construction')
        attrs = e.GetAttributes()
        self.assertTrue(
            len(attrs.keys()) == 0, "Attributes present on construction")
        children = e.GetChildren()
        try:
            children.next()
            self.fail("Children present on construction")
        except StopIteration:
            pass
        e = Element(None, 'test')
        self.assertTrue(e.xmlname == 'test', 'element named on construction')

    def testCaseDefaultName(self):
        e = NamedElement(None)
        self.assertTrue(
            e.xmlname == 'test', 'element default name on construction')

    def testSetXMLName(self):
        e = NamedElement(None, 'test2')
        self.assertTrue(
            e.xmlname == 'test2', 'element named explicitly in construction')

    def testAttributes(self):
        e = Element(None, 'test')
        e.SetAttribute('atest', 'value')
        attrs = e.GetAttributes()
        self.assertTrue(len(attrs.keys()) == 1, "Attribute not set")
        self.assertTrue(
            attrs['atest'] == 'value', "Attribute not set correctly")
        e = ReflectiveElement(None)
        e.SetAttribute('atest', 'value')
        # Deprecated: self.assertTrue(e.atest=='value',"Attribute relfection")
        attrs = e.GetAttributes()
        self.assertTrue(
            attrs['atest'] == 'value', "Attribute not set correctly")
        e.SetAttribute('btest', 'Yes')
        self.assertTrue(
            e.bTest == 'Yes', "Attribute relfection with simple assignment")
        attrs = e.GetAttributes()
        self.assertTrue(attrs['btest'] == 'Yes', "Attribute not set correctly")
        e.SetAttribute('ctest', 'Yes')
        self.assertTrue(
            e.cTest == True, "Attribute relfection with decode/encode")
        attrs = e.GetAttributes()
        self.assertTrue(attrs['ctest'] == 'Yes', "Attribute not set correctly")
        self.assertFalse('dtest' in attrs, "Optional ordered list attribute")
        self.assertTrue(
            attrs['dtestR'] == '', "Required ordered list attribute")
        e.SetAttribute('dtest', 'Yes No')
        self.assertTrue(
            e.dTest == [True, False], "Attribute relfection with list; %s" % repr(e.dTest))
        attrs = e.GetAttributes()
        self.assertTrue(
            attrs['dtest'] == 'Yes No', "Attribute not set correctly")
        self.assertFalse('etest' in attrs, "Optional unordered list attribute")
        self.assertTrue(
            attrs['etestR'] == '', "Required unordered list attribute")
        e.SetAttribute('etest', 'Yes No Yes')
        self.assertTrue(e.eTest == {
                        True: 2, False: 1}, "Attribute relfection with list: %s" % repr(e.eTest))
        attrs = e.GetAttributes()
        self.assertTrue(attrs['etest'] == 'No Yes Yes',
                        "Attribute not set correctly: %s" % repr(attrs['etest']))
        try:
            if e.ztest:
                pass
            self.fail("AttributeError required for undefined names")
        except AttributeError:
            pass
        e.ztest = 1
        if e.ztest:
            pass
        del e.ztest
        try:
            if e.ztest:
                pass
            self.fail("AttributeError required for undefined names after del")
        except AttributeError:
            pass
        try:
            self.assertTrue(
                e.fTest is None, "Missing attribute auto value not None")
        except AttributeError:
            self.fail("Missing attribute auto value: AttributeError")
        e.fTest = 1
        del e.fTest
        try:
            self.assertTrue(
                e.fTest is None, "Missing attribute auto value not None (after del)")
        except AttributeError:
            self.fail(
                "Missing attribute auto value: AttributeError (after del)")

    def testChildElements(self):
        """Test child element behaviour"""
        e = Element(None, 'test')
        child1 = e.ChildElement(Element, 'test1')
        children = list(e.GetChildren())
        self.assertTrue(
            len(children) == 1, "ChildElement failed to add child element")

    def testChildElementReflection(self):
        """Test child element cases using reflection"""
        e = ReflectiveElement(None)
        child1 = e.ChildElement(ReflectiveElement, 'test1')
        self.assertTrue(e.child is child1, "Element not set by reflection")
        children = list(e.GetChildren())
        self.assertTrue(len(children) == 1 and children[
                        0] is child1, "ChildElement failed to add child element")
        # Now create a second child, should return the same one due to model
        # restriction
        child2 = e.ChildElement(ReflectiveElement, 'test1')
        self.assertTrue(
            e.child is child1 and child2 is child1, "Element model violated")
        child3 = e.ChildElement(GenericElementA, 'test3')
        self.assertTrue(e.generics[0] is child3, "Generic element")
        child4 = e.ChildElement(GenericSubclassA, 'test4')
        self.assertTrue(
            e.generics[1] is child4, "Generic sub-class element via method")
        child5 = e.ChildElement(GenericSubclassB, 'test5')
        self.assertTrue(
            e.GenericElementB is child5, "Generic sub-class element via member")

    def testData(self):
        e = Element(None)
        self.assertTrue(e.IsMixed(), "Mixed default")
        e.AddData('Hello')
        self.assertTrue(e.GetValue() == 'Hello', "Data value")
        children = list(e.GetChildren())
        self.assertTrue(len(children) == 1, "Data child not set")
        self.assertTrue(children[0] == "Hello", "Data child not set correctly")

    def testEmpty(self):
        e = EmptyElement(None)
        self.assertFalse(e.IsMixed(), "EmptyElement is mixed")
        self.assertTrue(e.IsEmpty(), "EmptyElement not empty")
        try:
            e.AddData('Hello')
            self.fail("Data in EmptyElement")
        except XMLValidityError:
            pass
        try:
            child = e.ChildElement(Element)
            self.fail("Elements allowed in EmptyElement")
        except XMLValidityError:
            pass

    def testElementContent(self):
        e = ElementContent(None)
        self.assertFalse(e.IsMixed(), "ElementContent appears mixed")
        self.assertFalse(e.IsEmpty(), "ElementContent appears empty")
        try:
            e.AddData('Hello')
            self.fail("Data in ElementContent")
        except XMLValidityError:
            pass
        # white space should silently be ignored.
        e.AddData('  \n\r  \t')
        children = list(e.GetChildren())
        self.assertTrue(len(children) == 0, "Unexpected children")
        # elements can be added
        child = e.ChildElement(Element)
        children = list(e.GetChildren())
        self.assertTrue(len(children) == 1, "Expected one child")

    def testMixedContent(self):
        e = MixedElement(None)
        self.assertTrue(e.IsMixed(), "MixedElement not mixed")
        self.assertFalse(e.IsEmpty(), "MixedElement appears empty")
        e.AddData('Hello')
        self.assertTrue(
            e.GetValue() == 'Hello', 'Mixed content with a single value')
        child = e.ChildElement(Element)
        try:
            e.GetValue()
        except XMLMixedContentError:
            pass

    def testCopy(self):
        e1 = Element(None)
        e2 = e1.Copy()
        self.assertTrue(isinstance(e2, Element), "Copy didn't make Element")
        self.assertTrue(e1 == e2 and e1 is not e2)


class DocumentTests(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.d = mkdtemp('.d', 'pyslet-test_xml20081126-')
        os.chdir(self.d)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.d, True)

    def testCaseConstructor(self):
        d = Document()
        self.assertTrue(d.root is None, 'root on construction')
        self.assertTrue(d.GetBase() is None, 'base set on construction')
        d = Document(root=Element)
        self.assertTrue(
            isinstance(d.root, Element), 'root not created on construction')
        self.assertTrue(
            d.root.GetDocument() is d, 'root not linked to document')

    def testCaseBase(self):
        """Test the use of a file path on construction"""
        fpath = os.path.abspath('fpath.xml')
        furl = str(uri.URI.from_path(fpath))
        d = Document(baseURI=furl)
        self.assertTrue(d.GetBase() == furl, "Base not set in constructor")
        self.assertTrue(d.root is None, 'root on construction')
        d = Document(baseURI='fpath.xml', root=Element)
        self.assertTrue(d.GetBase(
        ) == furl, "Base not made absolute from relative URL:\n\t%s\n\t%s" % (furl, d.GetBase()))
        self.assertTrue(
            isinstance(d.root, Element), 'root not created on construction')
        d = Document()
        d.SetBase(furl)
        self.assertTrue(d.GetBase() == furl, "Base not set by SetBase")

    def testCaseReadFile(self):
        """Test the reading of the Document from the file system"""
        os.chdir(TEST_DATA_DIR)
        d = Document(baseURI='readFile.xml')
        d.Read()
        root = d.root
        self.assertTrue(isinstance(root, Element))
        self.assertTrue(
            root.xmlname == 'tag' and root.GetValue() == 'Hello World')

    def testCaseReadString(self):
        """Test the reading of the Document from a supplied stream"""
        os.chdir(TEST_DATA_DIR)
        d = Document(baseURI='readFile.xml')
        f = open('readFile.xml')
        d.Read(src=f)
        f.close()
        root = d.root
        self.assertTrue(isinstance(root, Element))
        self.assertTrue(
            root.xmlname == 'tag' and root.GetValue() == 'Hello World')

    def testCaseString(self):
        os.chdir(TEST_DATA_DIR)
        d = Document(baseURI='readFile.xml')
        d.Read()
        f = open('readFile.xml')
        fData = f.read()
        f.close()
        self.assertTrue(str(d) == fData, "XML output: %s" % str(d))
        d = Document(baseURI='ascii.xml')
        d.Read()
        f = open('ascii.xml')
        fData = f.read()
        f.close()
        self.assertTrue(str(d) == fData, "XML output: %s" % str(d))

    def testCaseResolveBase(self):
        """Test the use of ResolveURI and ResolveBase"""
        os.chdir(TEST_DATA_DIR)
        parent = Element(None)
        self.assertTrue(parent.ResolveBase() is None, "No default base")
        child = Element(parent)
        self.assertTrue(child.ResolveBase() is None, "No xml:base by default")
        parent.SetBase('file:///index.xml')
        self.assertTrue(
            child.ResolveBase() == 'file:///index.xml', "No xml:base inheritance")
        # Tests with a document follow....
        furl = str(uri.URI.from_path(os.path.abspath('base.xml')))
        href = uri.URI.from_path(os.path.abspath('link.xml'))
        hrefPath = href.abs_path
        href = str(href)
        altRef = 'file:///hello/link.xml'
        d = Document(baseURI='base.xml')
        self.assertTrue(
            d.GetBase() == furl, "Base not resolved relative to w.d. by constructor")
        d.Read()
        tag = d.root
        self.assertTrue(
            tag.ResolveBase() == furl, "Root element resolves from document")
        self.assertTrue(
            str(tag.ResolveURI("link.xml")) == href, "Root element HREF")
        self.assertTrue(
            str(tag.RelativeURI(href)) == 'link.xml', "Root element relative")
        #self.assertTrue(tag.RelativeURI(altRef)=='/hello/link.xml','Root element full path relative: %s'%tag.RelativeURI(altRef))
        childTag = tag._children[0]
        self.assertTrue(childTag.ResolveBase() == "file:///hello/base.xml",
                        "xml:base overrides in childTag (%s)" % childTag.ResolveBase())
        self.assertTrue(
            str(childTag.ResolveURI("link.xml")) == altRef, "child element HREF")
        self.assertTrue(str(childTag.RelativeURI(href)) == '..' + hrefPath,
                        "child element relative resulting in full path: %s" % childTag.RelativeURI(href))
        self.assertTrue(
            str(childTag.RelativeURI(altRef)) == 'link.xml', 'child element relative')
        # We require this next test to ensure that an href to the current document comes up blank
        # Although this was a major source of bugs in browsers (<img src=''> causing infinite loading loops)
        # these are largely fixed now and obfuscating by using a non-empty relative link to ourselves is
        # likely to start the whole thing going again.
        self.assertTrue(str(childTag.RelativeURI(childTag.ResolveBase())) == '',
                        'child element relative avoiding empty URI(%s)' % childTag.RelativeURI(childTag.ResolveBase()))
        grandChildTag = childTag._children[0]
        self.assertTrue(
            grandChildTag.ResolveBase() == "file:///hello/base.xml", "xml:base inherited")
        self.assertTrue(str(grandChildTag.ResolveURI("link.xml"))
                        == altRef, "grandChild element HREF inherited")
        self.assertTrue(str(grandChildTag.RelativeURI(href)) == '..' + hrefPath,
                        "grandChild element relative inherited: %s" % grandChildTag.RelativeURI(href))
        self.assertTrue(str(grandChildTag.RelativeURI(altRef))
                        == 'link.xml', 'grandChild element relative inherited')

    def testCaseResolveLang(self):
        """Test the use of ResolveLang"""
        parent = Element(None)
        self.assertTrue(parent.ResolveLang() is None, "No default language")
        parent.SetLang('en-GB')
        self.assertTrue(parent.GetLang() == 'en-GB', "Lang Get/Set")
        child = Element(parent)
        self.assertTrue(child.GetLang() is None, "No xml:lang by default")
        self.assertTrue(child.ResolveLang() == 'en-GB', "Lang inheritence")
        # repeat tests with a parent document
        d = Document()
        parent = Element(d)
        self.assertTrue(parent.ResolveLang() is None, "No default language")

    def testCaseCreate(self):
        """Test the creating of the Document on the file system"""
        CREATE_1_XML = """<?xml version="1.0" encoding="UTF-8"?>
<test/>"""
        d = Document(root=NamedElement)
        d.SetBase('create1.xml')
        d.Create()
        try:
            f = open("create1.xml")
            data = f.read()
            f.close()
            self.assertTrue(data == CREATE_1_XML, "Create Test")
        except IOError:
            self.fail("Create Test failed to create file")

    def testCaseUpdate(self):
        """Test the updating of the MXLDocument on the file system"""
        UPDATE_1_XML = """<?xml version="1.0" encoding="UTF-8"?>
<test>
	<test/>
</test>"""
        d = Document(root=NamedElement)
        d.SetBase('update1.xml')
        try:
            d.Update()
            self.fail("Update Document failed to spot missing file")
        except XMLMissingResourceError:
            pass
        d.Create()
        d.root.ChildElement(NamedElement)
        d.Update()
        try:
            f = open("update1.xml")
            data = f.read()
            f.close()
            self.assertTrue(data == UPDATE_1_XML, "Update Test")
        except IOError:
            self.fail("Update Test failed to update file")

    def testCaseID(self):
        """Test the built-in handling of a document's ID space."""
        doc = Document()
        e1 = Element(doc)
        e2 = Element(doc)
        e1.id = e2.id = 'test'
        doc.RegisterElement(e1)
        try:
            doc.RegisterElement(e2)
            self.fail("Failed to spot ID clash")
        except XMLIDClashError:
            pass
        e2.id = 'test2'
        doc.RegisterElement(e2)
        self.assertTrue(
            doc.GetElementByID('test') is e1, "Element look-up failed")
        newID = doc.GetUniqueID('test')
        self.assertFalse(newID == 'test' or newID == 'test2')

    def testCaseReflection(self):
        """Test the built-in handling of reflective attributes and elements."""
        REFLECTIVE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<reflection btest="Hello"><etest>Hello Again</etest></reflection>"""
        f = StringIO(REFLECTIVE_XML)
        d = ReflectiveDocument()
        d.Read(src=f)
        root = d.root
        self.assertTrue(isinstance(root, ReflectiveElement))
        self.assertTrue(root.bTest, "Attribute relfection")
        self.assertTrue(root.child, "Element relfection")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
