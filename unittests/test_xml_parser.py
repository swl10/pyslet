#! /usr/bin/env python

import logging
import os.path
import unittest

from sys import maxunicode

import pyslet.rfc2396 as uri

from pyslet.py2 import (
    character,
    is_unicode,
    range3,
    ul)
from pyslet.xml import parser
from pyslet.xml import structures


MAX_CHAR = 0x10FFFF
if maxunicode < MAX_CHAR:
    MAX_CHAR = maxunicode


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XMLCharacterTests, 'test'),
        unittest.makeSuite(XMLValidationTests, 'test'),
        unittest.makeSuite(XMLParserTests, 'test')
    ))

TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_xml20081126')


class PIRecorderElement(structures.Element):

    def __init__(self, parent):
        structures.Element.__init__(self, parent)
        self.target = None
        self.instruction = None

    def processing_instruction(self, target, instruction):
        self.target = target
        self.instruction = instruction


class XMLCharacterTests(unittest.TestCase):
    # Test IsNameChar

    def test_char(self):
        """[2] Char ::=
        #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
        """
        expected_edges = [0x9, 0xB, 0xD, 0xE, 0x20, 0xD800, 0xE000, 0xFFFE,
                          0x10000, 0x110000]
        if MAX_CHAR < 0x10FFFF:
            expected_edges = expected_edges[0:8]
            logging.warn("xml tests truncated to character(0x%X) by narrow "
                         "python build" % MAX_CHAR)
        self.assertTrue(
            self.find_edges(parser.is_char, MAX_CHAR) == expected_edges,
            "is_char range test: " +
            str(self.find_edges(parser.is_char, MAX_CHAR)))

    def test_pubid_char(self):
        """[13] PubidChar ::=
        #x20 | #xD | #xA | [a-zA-Z0-9] | [-'()+,./:=?;!*#@$_%] """
        match_set = " \x0d\x0a-'()+,./:=?;!*#@$_%abcdefghijklmnopqrstuvwxyz"\
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for code in range3(0xFF):
            c = character(code)
            if parser.is_pubid_char(c):
                if c not in match_set:
                    self.fail("PubidChar false positive: %s" % c)
            else:
                if c in match_set:
                    self.fail("PubidChar not recognized: %s" % c)

    def test_char_classes(self):
        """[84] Letter ::= BaseChar | Ideographic
        [85] BaseChar ::= [#x0041-#x005A] | ...
        [86] Ideographic ::= [#x4E00-#x9FA5] | #x3007 | [#x3021-#x3029]
        [87] CombiningChar ::= [#x0300-#x0345] | ...
        [88] Digit ::= [#x0030-#x0039] | ...
        [89] Extender ::= #x00B7 | ..."""
        nbase_chars = 0
        nideographics = 0
        ncombining_chars = 0
        ndigits = 0
        nextenders = 0
        for code in range3(0x10000):
            c = character(code)
            if parser.is_letter(c):
                if parser.is_ideographic(c):
                    nideographics += 1
                elif parser.is_base_char(c):
                    nbase_chars += 1
                else:
                    self.fail("character(%#x) is a letter but not an "
                              "ideographic or base character" % code)
            else:
                self.assertFalse(
                    parser.is_ideographic(c) or parser.is_base_char(c),
                    "character(%#x) is an ideographic or base character "
                    "but not a letter")
            if parser.is_combining_char(c):
                ncombining_chars += 1
            if parser.is_digit(c):
                ndigits += 1
            if parser.is_extender(c):
                nextenders += 1
        self.assertTrue(nbase_chars == 13602,
                        "base char total %i" % nbase_chars)
        self.assertTrue(nideographics == 20912,
                        "ideographic char total %i" % nideographics)
        self.assertTrue(ncombining_chars == 437,
                        "combing char total %i" % ncombining_chars)
        self.assertTrue(ndigits == 149, "digit total %i" % ndigits)
        self.assertTrue(nextenders == 18, "extender total %i" % nextenders)

    def find_edges(self, test_func, max):
        edges = []
        flag = False
        for code in range3(max + 1):
            c = character(code)
            if flag != test_func(c):
                flag = not flag
                edges.append(code)
        if flag:
            edges.append(max + 1)
        return edges


class XMLValidationTests(unittest.TestCase):

    def test_well_formed(self):
        dpath = os.path.join(TEST_DATA_DIR, 'wellformed')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(f) as e:
                d = structures.Document()
                p = parser.XMLParser(e)
                p.check_validity = False
                try:
                    p.parse_document(d)
                    self.assertTrue(
                        p.valid is None,
                        "Well-Formed Example: %s marked valid but "
                        "check_validity was False" % fname)
                except parser.XMLWellFormedError as e:
                    self.fail("Well-Formed Example: %s raised "
                              "XMLWellFormedError\n%s" % (fname, str(e)))
        dpath = os.path.join(TEST_DATA_DIR, 'notwellformed')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(f) as e:
                d = structures.Document()
                try:
                    d.read(e)
                    self.fail("%s is not Well-Formed but failed to raise "
                              "XMLWellFormedError" % fname)
                except parser.XMLWellFormedError as e:
                    logging.info("\n%s: Well-formed Errors:", fname)
                    logging.info(str(e))

    def test_valid(self):
        dpath = os.path.join(TEST_DATA_DIR, 'valid')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(f) as e:
                p = parser.XMLParser(e)
                p.check_validity = True
                p.open_external_entities = True
                p.raiseValidityErrors = True
                try:
                    p.parse_document()
                    self.assertTrue(p.valid, "Valid Example: %s not marked as "
                                    "valid in the parser" % fname)
                    self.assertTrue(
                        len(p.nonFatalErrors) == 0,
                        "Valid Example: %s reported validity errors" % fname)
                except structures.XMLValidityError as e:
                    self.fail(
                        "Valid Example: %s raised "
                        "structures.XMLValidityError\n%s" % (fname, str(e)))
                except parser.XMLWellFormedError as e:
                    self.fail("Valid Example: %s raised "
                              "XMLWellFormedError" % fname)
        dpath = os.path.join(TEST_DATA_DIR, 'wellformed')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(f) as e:
                p = parser.XMLParser(e)
                p.check_validity = True
                p.open_external_entities = True
                # By default we don't raise validity errors...
                try:
                    p.parse_document()
                    self.assertFalse(p.valid, "Invalid Example: %s marked as "
                                     "valid in the parser" % fname)
                    self.assertFalse(
                        len(p.nonFatalErrors) == 0,
                        "Invalid Example: %s reported no validity errors" %
                        fname)
                    logging.info("\n%s: Validity Errors:", fname)
                    for e in p.nonFatalErrors:
                        logging.info(str(e))
                except structures.XMLValidityError as e:
                    self.fail("structures.XMLValidityError raised when "
                              "raiseVaidityErrors is False (%s)" % fname)
                except parser.XMLWellFormedError as e:
                    self.fail("Invalid but Well-Formed Example raised "
                              "XMLWellFormedError (%s)\n%s" % (fname, str(e)))
                except structures.XMLError as e:
                    self.fail("Other XMLError raised by invalid but "
                              "Well-Formed Example (%s)" % fname)

    def test_incompatible(self):
        dpath = os.path.join(TEST_DATA_DIR, 'compatible')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(f) as e:
                p = parser.XMLParser(e)
                p.checkCompatibility = True
                try:
                    p.parse_document()
                    self.assertTrue(
                        len(p.nonFatalErrors) == 0,
                        "Compatible Example: %s reported compatibility "
                        "errors" % fname)
                except structures.XMLValidityError as e:
                    self.fail("Compatible Example: %s raised "
                              "structures.XMLValidityError" % fname)
                except parser.XMLWellFormedError as e:
                    self.fail("Compatible Example: %s raised "
                              "XMLWellFormedError" % fname)
                except structures.XMLError as e:
                    self.fail("Compatible Example: %s raised other XMLError" %
                              fname)
        dpath = os.path.join(TEST_DATA_DIR, 'incompatible')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(f) as e:
                p = parser.XMLParser(e)
                p.checkCompatibility = True
                try:
                    p.parse_document()
                    self.assertFalse(
                        len(p.nonFatalErrors) == 0,
                        "Incompatible Example: %s reported no non-fatal "
                        "errors" % fname)
                    logging.info("\n%s: Compatibility Errors:", fname)
                    for e in p.nonFatalErrors:
                        logging.info(str(e))
                except structures.XMLValidityError as e:
                    self.fail("structures.XMLValidityError raised when "
                              "raiseVaidityErrors is False (%s)" % fname)
                except parser.XMLWellFormedError as e:
                    self.fail("Incompatible but Well-Formed Example raised "
                              "XMLWellFormedError (%s)" % fname)
                except structures.XMLError as e:
                    self.fail("Other XMLError raised by incompatible but "
                              "Well-Formed Example (%s)" % fname)

    def test_error(self):
        dpath = os.path.join(TEST_DATA_DIR, 'noerrors')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(
                    f, 'latin-1' if "latin" in fname else None) as e:
                p = parser.XMLParser(e)
                p.checkAllErrors = True
                try:
                    p.parse_document()
                    self.assertTrue(
                        len(p.nonFatalErrors) == 0,
                        "No errors example: %s reported errors" % fname)
                except structures.XMLError as e:
                    self.fail("No errors example: %s raised XMLError" % fname)
        dpath = os.path.join(TEST_DATA_DIR, 'errors')
        for fname in os.listdir(dpath):
            if fname[-4:] != ".xml":
                continue
            f = uri.URI.from_path(os.path.join(dpath, fname))
            with structures.XMLEntity(
                    f, 'latin-1' if "latin" in fname else None) as e:
                p = parser.XMLParser(e)
                p.checkAllErrors = True
                try:
                    p.parse_document()
                    self.assertFalse(
                        len(p.nonFatalErrors) == 0,
                        "Error example: %s reported no non-fatal errors" %
                        fname)
                    logging.info("\n%s: Errors:", fname)
                    for e in p.nonFatalErrors:
                        logging.info(str(e))
                except structures.XMLError as e:
                    self.fail("XMLError raised by (non-fatal) error "
                              "example (%s)" % fname)

    def test_xidmode(self):
        dpath = os.path.join(TEST_DATA_DIR, 'xidmode')
        save_dir = os.getcwd()
        try:
            os.chdir(dpath)
            data = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE foo [
        <!ELEMENT foo ANY >
        <!ENTITY bad SYSTEM "secret.txt" >]>
    <foo>&bad;</foo>"""
            with structures.XMLEntity(data) as e:
                # default configuration
                p = parser.XMLParser(e)
                try:
                    doc = p.parse_document()
                    data = doc.root.get_value()
                    if "secret" in data:
                        self.fail("Default parser resolves xid")
                except structures.XMLMissingResourceError as e:
                    pass
            with structures.XMLEntity(data) as e:
                # explicitly allow external entities
                p = parser.XMLParser(e)
                p.open_external_entities = True
                try:
                    doc = p.parse_document()
                    data = doc.root.get_value()
                    self.assertTrue("secret" in data)
                except structures.XMLMissingResourceError as e:
                    self.fail("Failed to resolve xid")
        finally:
            os.chdir(save_dir)

    def tesx_xidmode_http(self):
        dpath = os.path.join(TEST_DATA_DIR, 'xidmode')
        save_dir = os.getcwd()
        try:
            os.chdir(dpath)
            data = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE foo [
        <!ELEMENT foo ANY >
        <!ENTITY bad SYSTEM
            "https://raw.githubusercontent.com/swl10/pyslet/master/LICENSE.txt"
        >]>
    <foo>&bad;</foo>"""
            with structures.XMLEntity(data) as e:
                # default configuration
                p = parser.XMLParser(e)
                try:
                    doc = p.parse_document()
                    data = doc.root.get_value()
                    if "Copyright" in data:
                        self.fail("Default parser resolves xid via http")
                except structures.XMLMissingResourceError as e:
                    pass
            with structures.XMLEntity(data) as e:
                # default configuration
                p = parser.XMLParser(e)
                p.open_external_entities = True
                try:
                    doc = p.parse_document()
                    data = doc.root.get_value()
                    if "Copyright" in data:
                        self.fail("Default parser resolves xid via http")
                except structures.XMLMissingResourceError as e:
                    pass
            with structures.XMLEntity(data) as e:
                # explicitly allow external entities
                p = parser.XMLParser(e)
                p.open_external_entities = True
                p.open_remote_entities = True
                try:
                    doc = p.parse_document()
                    data = doc.root.get_value()
                    self.assertTrue("Copyright" in data)
                except structures.XMLMissingResourceError as e:
                    self.fail("Failed to resolve remote xid")
        finally:
            os.chdir(save_dir)


class XMLParserTests(unittest.TestCase):

    def test_constructor(self):
        with structures.XMLEntity("<hello>") as e:
            parser.XMLParser(e)

    def test_rewind(self):
        data = "Hello\r\nWorld\nCiao\rTutti!"
        data2 = "Hello\nWorld\nCiao\nTutti!"
        with structures.XMLEntity(data) as e:
            p = parser.XMLParser(e)
            for i in range3(len(data2)):
                self.assertTrue(p.the_char == data2[i],
                                "Failed at data[%i] before look ahead" % i)
                for j in range3(5):
                    data = []
                    for k in range3(j):
                        if p.the_char is not None:
                            data.append(p.the_char)
                        p.next_char()
                    p.buff_text(''.join(data))
                    self.assertTrue(
                        p.the_char == data2[i],
                        "Failed at data[%i] after Rewind(%i)" % (i, j))
                p.next_char()

    def test_namecase_general(self):
        data = "Hello GoodBye"
        with structures.XMLEntity(data) as e:
            p = parser.XMLParser(e)
            self.assertFalse(p.parse_literal("HELLO"),
                             "Case insensitve literal in default parser")
            p.sgml_namecase_general = True
            self.assertTrue(p.parse_literal("HELLO"), "Upper-case literals")
            p.parse_s()
            # self.assertTrue(p.parse_name()=="GOODBYE",
            #                 "Upper-case general names")

    def test_document(self):
        """[1] document ::= prolog element Misc* """
        os.chdir(TEST_DATA_DIR)
        f = open('readFile.xml', 'rb')
        with structures.XMLEntity(f) as e:
            # shouldn't close the file as f already open
            d = structures.Document()
            d.read(e)
            root = d.root
            self.assertTrue(isinstance(root, structures.Element))
            self.assertTrue(
                root.xmlname == 'tag' and root.get_value() == 'Hello World')
        f.close()
        f = open('readFile.xml', 'rb')
        with structures.XMLEntity(f) as e:
            p = parser.XMLParser(e)
            p.parse_document()
            root = p.doc.root
            self.assertTrue(isinstance(root, structures.Element))
            self.assertTrue(
                root.xmlname == 'tag' and root.get_value() == 'Hello World')
        f.close()

    # Following production is implemented as a character class:
    # [2] Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] |
    # [#x10000-#x10FFFF]

    def test_s(self):
        """[3] S ::= (#x20 | #x9 | #xD | #xA)+ """
        with structures.XMLEntity(" \t\r\n \r \nH ello") as e:
            p = parser.XMLParser(e)
            self.assertTrue(p.parse_s() == " \t\n \n \n")
            self.assertTrue(p.the_char == 'H')
            p.next_char()
            try:
                p.parse_required_s()
            except parser.XMLWellFormedError:
                self.fail("parse_required_s failed to parse white space")
            try:
                p.parse_required_s()
                self.fail("parse_required_s failed to throw exception")
            except parser.XMLWellFormedError:
                pass

    # Following two productions are implemented as character classes:
    # [4] NameStartChar ::= ":" | [A-Z] | "_" | [a-z] | [#xC0-#xD6] |
    # [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] | [#x37F-#x1FFF] |
    # [#x200C-#x200D] | [#x2070-#x218F] | [#x2C00-#x2FEF] |
    # [#x3001-#xD7FF] | [#xF900-#xFDCF] | [#xFDF0-#xFFFD] |
    # [#x10000-#xEFFFF]
    # [4a] NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 |
    # [#x0300-#x036F] | [#x203F-#x2040]

    def test_name(self):
        """[5] Name ::= NameStartChar (NameChar)*"""
        sgood = ('hello', ':ello', ul(b'A\xb72'), '_')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                name = p.parse_name()
                self.assertTrue(name == s,
                                ul("Name: %s (expected %s)") % (name, s))
        sbad = ('-Atlantis', '&hello', 'fish&chips',
                'what?', '.ello', ul('\xb7RaisedDot'), '-')
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    name = p.parse_name()
                    self.assertFalse(p.the_char is None,
                                     "parse_name negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass
        with structures.XMLEntity('&noname') as e:
            p = parser.XMLParser(e)
            try:
                p.parse_required_name()
                self.fail("parse_required_name: failed to throw exception")
            except parser.XMLWellFormedError:
                pass

    def test_names(self):
        """[6] Names ::= Name (#x20 Name)*  """
        with structures.XMLEntity("Hello World -Atlantis!") as e:
            p = parser.XMLParser(e)
            self.assertTrue(p.parse_names() == ['Hello', 'World'])

    def test_nmtoken(self):
        """[7] Nmtoken ::= (NameChar)+"""
        sgood = ('hello', 'h:ello', '-Atlantis', ':ello',
                 ul('\xb7RaisedDot'), ul('1\xb72'), '-')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                name = p.parse_nmtoken()
                self.assertTrue(name == s, ul("Nmtoken: %s") % name)
        sbad = ('&hello', 'fish&chips', 'what?')
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    name = p.parse_nmtoken()
                    self.assertFalse(p.the_char is None,
                                     "parse_nmtoken negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_nmtokens(self):
        """[8] Nmtokens ::= Nmtoken (#x20 Nmtoken)*"""
        with structures.XMLEntity("Hello World -Atlantis!") as e:
            p = parser.XMLParser(e)
            tokens = p.parse_nmtokens()
            self.assertTrue(
                tokens == ['Hello', 'World', '-Atlantis'], repr(tokens))

    def test_entity_value(self):
        """[9] EntityValue ::=
        '"' ([^%&"] | PEReference | Reference)* '"' | "'"
        ([^%&'] | PEReference | Reference)* "'"     """
        with structures.XMLEntity("'first'\"second\"'3&gt;2''2%ltpe;3'") as e:
            m = ['first', 'second', '3&gt;2', '2<3']
            p = parser.XMLParser(e)
            p.check_validity = True
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('ltpe', '<'))
            for match in m:
                value = p.parse_entity_value()
                self.assertTrue(
                    value == match,
                    "Match failed: %s (expected %s)" % (value, match))

    def test_att_value(self):
        """[10] AttValue ::=
        '"' ([^<&"] | Reference)* '"' |  "'" ([^<&'] | Reference)* "'" """
        with structures.XMLEntity("'first'\"second\"'3&gt;2''Caf&#xE9;'") as e:
            m = ['first', 'second', '3>2', ul('Caf\xe9')]
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_att_value()
                self.assertTrue(
                    value == match,
                    "Match failed: %s (expected %s)" % (value, match))
        sbad = ('"3<2"', "'Fish&Chips'")
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    value = p.parse_att_value()
                    self.fail("AttValue negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_system_literal(self):
        """[11] SystemLiteral ::= ('"' [^"]* '"') | ("'" [^']* "'") """
        with structures.XMLEntity(
                "'first'\"second\"'3&gt;2''2%ltpe;3''Caf&#xE9;'") as e:
            m = ['first', 'second', '3&gt;2', '2%ltpe;3', 'Caf&#xE9;']
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_system_literal()
                self.assertTrue(
                    value == match,
                    "Match failed: %s (expected %s)" % (value, match))

    def test_pubid_literal(self):
        """[12] PubidLiteral ::=
        '"' PubidChar* '"' | "'" (PubidChar - "'")* "'"     """
        with structures.XMLEntity(
                "'first'\"second\"'http://www.example.com/schema.dtd?"
                "strict''[bad]'") as e:
            m = ['first', 'second', 'http://www.example.com/schema.dtd?strict']
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_pubid_literal()
                self.assertTrue(
                    value == match,
                    "Match failed: %s (expected %s)" % (value, match))
            try:
                value = p.parse_pubid_literal()
                self.fail("Parsed bad PubidLiterasl: %s" % value)
            except parser.XMLFatalError:
                pass

    # [13] PubidChar: tested as a character class

    def test_char_data(self):
        """[14] CharData ::= [^<&]* - ([^<&]* ']]>' [^<&]*) """
        with structures.XMLEntity("First<Second&Third]]&Fourth]]>") as e:
            m = ['First', 'Second', 'Third]]', 'Fourth']
            p = parser.XMLParser(e)
            p.doc = structures.Document()
            for match in m:
                p.element = structures.Element(p.doc)
                p.parse_char_data()
                p.next_char()
                self.assertTrue(p.element.get_value() == match,
                                "Match failed: %s (expected %s)" %
                                (p.element.get_value(), match))

    def test_comment(self):
        """[15] Comment ::= '<!--' ((Char - '-') | ('-' (Char - '-')))* '-->'
        """
        with structures.XMLEntity(
                "<!--First--><!--Secon-d--><!--Thi<&r]]>d--><!--Fourt<!-h-->"
                "<!--Bad-Comment--->") as e:
            m = ['First', 'Secon-d', 'Thi<&r]]>d', 'Fourt<!-h']
            p = parser.XMLParser(e)
            for match in m:
                pstr = p.parse_comment()
                self.assertTrue(
                    pstr == match,
                    "Match failed: %s (expected %s)" % (pstr, match))
            try:
                if p.parse_literal('<!--'):
                    pstr = p.parse_comment()
                self.fail("Parsed bad comment: %s" % pstr)
            except parser.XMLFatalError:
                pass

    def test_pi(self):
        """[16] PI ::= '<?' PITarget (S (Char* - (Char* '?>' Char*)))? '?>' """
        with structures.XMLEntity(
                "<?target instruction?><?xm_xml \n\r<!--no comment-->?>"
                "<?markup \t]]>?&<?>") as e:
            m = [('target', 'instruction'), ('xm_xml', '<!--no comment-->'),
                 ('markup', ']]>?&<')]
            p = parser.XMLParser(e)
            p.doc = structures.Document()
            for matchTarget, matchStr in m:
                p.element = PIRecorderElement(p.doc)
                p.parse_pi()
                self.assertTrue(
                    p.element.target == matchTarget,
                    "Match failed for target: %s (expected %s)" %
                    (p.element.target, matchTarget))
                self.assertTrue(
                    p.element.instruction == matchStr,
                    "Match failed for instruction: %s (expected %s)" %
                    (p.element.instruction, matchStr))
        sbad = ('<?xml reserved?>')
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.doc = structures.Document()
                try:
                    p.parse_pi()
                    self.fail("PI negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_pitarget(self):
        """[17] PITarget ::= Name - (('X' | 'x') ('M' | 'm') ('L' | 'l'))
        """
        sgood = ('hello', 'helloxml', 'xmlhello', 'xmhello', 'xm', 'ml', 'xl')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                name = p.parse_pi_target()
                self.assertTrue(name == s, "PITarget: %s" % name)
        sbad = ('xml', 'XML', 'xML', 'Xml')
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    name = p.parse_pi_target()
                    self.fail("PITarget negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_cdsect(self):
        """[18] CDSect ::= CDStart CData CDEnd      """
        sgood = ('<![CDATA[hello]]>',
                 "<![CDATA[]]>",
                 "<![CDATA[a]b]]c]>d><![CDATAe]]>",
                 'hello]]>',
                 "<![CDATA[<hello>&world;]]>")
        m = ['hello', '', 'a]b]]c]>d><![CDATAe', 'hello', "<hello>&world;"]
        for s, match in zip(sgood, m):
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.doc = structures.Document()
                p.element = structures.Element(p.doc)
                p.parse_cdsect(p.the_char != '<')
                self.assertTrue(p.element.get_value() == match,
                                "CDSect conent: %s" % p.element.get_value())
        sbad = ('<!CDATA [hello]]>',
                "<!CDATA[hello]]",
                "hello")
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.doc = structures.Document()
                p.element = structures.Element(p.doc)
                try:
                    p.parse_cdsect(p.the_char != '<')
                    self.fail("CDSect negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass
        with structures.XMLEntity("&hello;<end") as e:
            p = parser.XMLParser(e)
            p.doc = structures.Document()
            p.element = structures.Element(p.doc)
            p.parse_cdsect(True, '<end')
            self.assertTrue(p.element.get_value() == '&hello;',
                            "Custom CDSect: %s" % p.element.get_value())

    def test_cdstart(self):
        """[21] CDStart ::= '<!CDATA['  """
        with structures.XMLEntity("<![CDATA[") as e:
            p = parser.XMLParser(e)
            p.parse_cdstart()
            self.assertTrue(p.the_char is None, "Short parse on CDStart")

    def test_cdata(self):
        """[20] CData ::= (Char* - (Char* ']]>' Char*))     """
        sgood = ('', ' ', '<!-- comment -->', '&hello;]]>', ']', ']]', ']]h>')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.doc = structures.Document()
                p.element = structures.Element(p.doc)
                p.parse_cdata()
                if p.the_char is None:
                    self.assertTrue(p.element.get_value() == s,
                                    "CData conent: %s" % p.element.get_value())
                else:
                    p.parse_cdend()
                    self.assertTrue(p.element.get_value() == s[:-3],
                                    "CData conent: %s" % p.element.get_value())
        # no negative tests as prolog can be empty, but check the custom CDEnd
        # case.
        with structures.XMLEntity("hello<end") as e:
            p = parser.XMLParser(e)
            p.doc = structures.Document()
            p.element = structures.Element(p.doc)
            p.parse_cdata('<end')
            self.assertTrue(p.element.get_value() == 'hello',
                            "Custom CDEnd: %s" % p.element.get_value())

    def test_cd_end(self):
        """[21] CDEnd ::= ']]>'     """
        with structures.XMLEntity("]]>") as e:
            p = parser.XMLParser(e)
            p.parse_cdend()
            self.assertTrue(p.the_char is None, "Short parse on CDEnd")

    def test_prolog(self):
        """[22] prolog ::= XMLDecl? Misc* (doctypedecl Misc*)?  """
        sgood = (
            '', ' ', '<!-- comment -->',
            '<?xml version="1.0"?>',
            '<?xml version="1.0"?><!-- comment --> ',
            '<?xml version="1.0"?><!-- comment --> <!DOCTYPE steve>',
            '<?xml version="1.0"?><!-- comment --> <!DOCTYPE steve><?pi?> ')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.doc = structures.Document()
                p.parse_prolog()
                self.assertTrue(p.the_char is None, "Short parse on Prolog")
        # no negative tests as prolog can be empty!

    def test_xml_decl(self):
        """[23] XMLDecl ::= '<?xml' VersionInfo EncodingDecl? SDDecl? S? '?>'
        """
        sgood = ('<?xml version="1.0" encoding="utf-8" standalone="no" ?>',
                 "<?xml version='1.0' standalone='yes'?>",
                 "<?xml version='1.0' encoding='utf-8'?>",
                 "<?xml version='1.1'?>",
                 " version='1.2'?>")
        m = [('1.0', 'utf-8', False),
             ('1.0', None, True),
             ('1.0', 'utf-8', False),
             ('1.1', None, False),
             ('1.2', None, False)]
        for s, match in zip(sgood, m):
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                d = p.parse_xml_decl(not ('x' in s))
                self.assertTrue(isinstance(d, structures.XMLDeclaration),
                                "xml declaration type")
                self.assertTrue(d.version == match[0],
                                "declared version mismatch: %s" % d.version)
                self.assertTrue(d.encoding == match[1],
                                "declared encoding mismatch: %s" % d.encoding)
                self.assertTrue(
                    d.standalone == match[2],
                    "standalone declaration mismatch: %s" % d.standalone)
                self.assertTrue(p.the_char is None, "Short parse on XMLDecl")
        sbad = ('', 'version="1.0"', " ='1.0'", " version=1.0")
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_xml_decl()
                    self.fail("XMLDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_version_info(self):
        """[24] VersionInfo ::=
        S 'version' Eq ("'" VersionNum "'" | '"' VersionNum '"')    """
        sgood = (' version="1.0"', "  version  =  '1.1'", " = '1.0'")
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.parse_version_info(not ('v' in s))
                self.assertTrue(p.the_char is None,
                                "Short parse on VersionInfo")
        sbad = ('', 'version="1.0"', " ='1.0'", " version=1.0")
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_version_info()
                    self.fail("VersionInfo negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_eq(self):
        """[25] Eq ::= S? '=' S?    """
        sgood = ('=', ' = ', ' =', '= ')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.parse_eq()
                self.assertTrue(p.the_char is None, "Short parse on Eq")
        sbad = ('', '-')
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_eq()
                    self.fail("Eq negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_version_num(self):
        """[26] VersionNum ::= '1.' [0-9]+ """
        sgood = ('1.0', '1.10', '1.1', '1.0123456789')
        for s in sgood:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                self.assertTrue(p.parse_version_num() == s,
                                "Failed to parse VersionNum: %s" % s)
                self.assertTrue(p.the_char is None,
                                "Short parse on VersionNum")
        sbad = ('1. ', '2.0', '1', '1,0')
        for s in sbad:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_version_num()
                    self.fail("VersionNum negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_misc(self):
        """[27] Misc ::= Comment | PI | S """
        s = "<!-- comment --><?pi?> "
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            for i in range3(3):
                p.parse_misc()
            self.assertTrue(p.the_char is None, "Short parse of Misc")

    def test_doctypedecl(self):
        """[28] doctypedecl ::=
        '<!DOCTYPE' S Name (S ExternalID)? S? ('[' intSubset ']' S?)? '>'
        """
        s = ["<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd'[ <!ENTITY name "
             "'Steve'> ]>",
             "<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd' [] >",
             "<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd' >",
             "<!DOCTYPE Steve [ ] >",
             "<!DOCTYPE Steve>"]
        m = [('Steve', 'SteveDoc.dtd', 'Steve'),
             ('Steve', 'SteveDoc.dtd', None),
             ('Steve', 'SteveDoc.dtd', None),
             ('Steve', None, None),
             ('Steve', None, None)]
        dtd_path = os.path.join(TEST_DATA_DIR, 'SteveDoc.dtd')
        f = uri.URI.from_path(dtd_path)
        for sEntity, match in zip(s, m):
            with structures.XMLEntity(sEntity) as e:
                e.location = f
                p = parser.XMLParser(e)
                p.parse_doctypedecl()
                self.assertTrue(isinstance(p.dtd, structures.XMLDTD),
                                "No DTD created")
                self.assertTrue(p.dtd.name == match[0], "Name mismatch")
                if match[1] is None:
                    self.assertTrue(p.dtd.external_id is None,
                                    "External ID: expected None")
                else:
                    self.assertTrue(
                        isinstance(p.dtd.external_id,
                                   structures.XMLExternalID),
                        "Type of ExternalID")
                    self.assertTrue(p.dtd.external_id.system == match[1],
                                    "System ID mismatch")
                if match[2] is not None:
                    self.assertTrue(
                        p.dtd.get_entity('name').definition == match[2],
                        "Expected general entity declared: %s" %
                        repr(p.dtd.get_entity('name').definition))

    def test_decl_sep(self):
        """[28a] DeclSep ::= PEReference | S"""
        s = "%stuff; %stuff; x"
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('stuff', ' '))
            p.check_validity = True
            p.refMode = parser.XMLParser.RefModeInDTD
            while p.the_char != 'x':
                p.parse_decl_sep()

    def test_int_subset(self):
        """[28b] intSubset ::= (markupdecl | DeclSep)* """
        s = """<!ELEMENT elem1 ANY>
\t\t<!ATTLIST elem1 attr CDATA 'Steve'>
\t\t<!ENTITY name 'Steve'>
\t\t<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'>
\t\t<?stuff?>
\t\t<!-- more stuff -->
\t\tx"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.doc = structures.Document()
            p.parse_int_subset()
            self.assertTrue(
                p.the_char == 'x',
                "Short parse on internal subset: found %s" % repr(p.the_char))

    def test_markup_decl(self):
        """[29] markupdecl ::=
        elementdecl | AttlistDecl | EntityDecl | NotationDecl | PI | Comment
        """
        s = """<!ELEMENT elem1 ANY>
\t\t<!ATTLIST elem1 attr CDATA 'Steve'>
\t\t<!ENTITY name 'Steve'>
\t\t<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'>
\t\t<?stuff?>
\t\t<!-- more stuff -->
\t\tx"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            # ensures that elements are declared in the DTD
            p.dtd = structures.XMLDTD()
            while p.the_char == '<':
                p.parse_markup_decl(False)
                p.parse_s()
            self.assertTrue(p.the_char == 'x',
                            "Short parse on markup declarations: found %s" %
                            repr(p.the_char))
            etype = p.dtd.get_element_type('elem1')
            self.assertTrue(etype.content_type == structures.ElementType.Any,
                            "element content type")
            alist = p.dtd.get_attribute_list('elem1')
            self.assertTrue(alist['attr'].defaultValue == 'Steve', "attlist")
            self.assertTrue(p.dtd.get_entity('name').definition == 'Steve',
                            "entity declaration")
            self.assertTrue(p.dtd.get_notation('SteveN').external_id.system ==
                            '/home/steve.txt', "notation declaration")

    def test_ext_subset(self):
        """[30] extSubset ::= TextDecl? extSubsetDecl """
        s = '<?xml encoding = "latin-1"?> <?stuff?> !'
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.parse_ext_subset()
            self.assertTrue(p.the_char == '!',
                            "Short parse on extSubset: %s" % p.the_char)
        s = '<?stuff?> !'
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.parse_ext_subset()
            self.assertTrue(p.the_char == '!',
                            "Short parse on extSubset: %s" % p.the_char)

    def test_ext_subset_decl(self):
        """[31] extSubsetDecl ::= ( markupdecl | conditionalSect | DeclSep)*
        """
        s = "<?stuff?><![INCLUDE[]]>%moreStuff; "
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(
                structures.XMLParameterEntity('moreStuff', ' <?stuff?>'))
            p.check_validity = True
            p.refMode = parser.XMLParser.RefModeInDTD
            p.parse_ext_subset_decl()
            self.assertTrue(p.the_char is None,
                            "Short parse on extSubsetDecl: %s" % p.the_char)

    def test_sd_decl(self):
        """[32] SDDecl ::=
        S 'standalone' Eq (("'" ('yes' | 'no') "'") | ('"' ('yes' | 'no') '"'))
        """
        with structures.XMLEntity(" standalone='yes' standalone = \"no\" "
                                  "standalone = 'bad'") as e:
            m = [True, False]
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_sd_decl()
                self.assertTrue(
                    value == match,
                    "Match failed: %s (expected %s)" % (value, match))
            try:
                value = p.parse_sd_decl()
                self.fail("Parsed bad SDDecl: %s" % value)
            except parser.XMLFatalError:
                pass

    # There are no productions [33]-[38]

    def test_element(self):
        """[39] element ::= EmptyElemTag | STag content ETag """
        s = """<elem1/><elem2>hello</elem2><elem3>goodbye</elem4>"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInContent
            element = p.element = structures.Element("a")
            p.parse_element()
            p.parse_element()
            try:
                p.parse_element()
                self.fail("Parsed bad element.")
            except parser.XMLWellFormedError:
                pass
            children = list(element.get_children())
            self.assertTrue(isinstance(children[0], structures.Element),
                            "First element: %s" % repr(children[0]))
            self.assertTrue(children[0].xmlname == 'elem1',
                            "First element name: %s" % repr(
                children[0].xmlname))
            self.assertTrue(children[0].get_value() == '',
                            "First element empty value: %s" %
                            repr(children[0].get_value()))
            self.assertTrue(isinstance(children[1], structures.Element),
                            "Second element: %s" % repr(children[1]))
            self.assertTrue(
                children[1].xmlname == 'elem2',
                "Second element name: %s" % repr(children[1].xmlname))
            self.assertTrue(
                children[1].get_value() == 'hello',
                "Second element value: %s" % repr(children[1].get_value()))

    def test_stag(self):
        """[40] STag ::= '<' Name (S Attribute)* S? '>' """
        with structures.XMLEntity("<tag hello='world' ciao=\"tutti\">") as e:
            p = parser.XMLParser(e)
            name, attrs, empty = p.parse_stag()
            self.assertTrue(name == 'tag' and attrs['hello'] == 'world' and
                            attrs['ciao'] == 'tutti' and not empty)
        with structures.XMLEntity("<tag hello/>") as e:
            p = parser.XMLParser(e)
            p.sgml_shorttag = True
            name, attrs, empty = p.parse_stag()
            self.assertTrue(name == 'tag' and attrs['hello'] == 'hello' and
                            empty is True)
        with structures.XMLEntity("<tag width=20%>") as e:
            p = parser.XMLParser(e)
            p.dont_check_wellformedness = True
            name, attrs, empty = p.parse_stag()
            self.assertTrue(name == 'tag' and attrs['width'] == '20%' and
                            empty is False)

    def test_attribute(self):
        """[41] Attribute ::= Name Eq AttValue """
        s = "a='b'c=\"d\"e=f i j g=h%"
        with structures.XMLEntity(s) as e:
            m = [('a', 'b'), ('c', 'd')]
            p = parser.XMLParser(e)
            for match in m:
                name, value = p.parse_attribute()
                self.assertTrue(
                    name == match[0],
                    "Attribute name match failed: %s (expected %s)" %
                    (name, match[0]))
                self.assertTrue(
                    value == match[1],
                    "Attribute value match failed: %s (expected %s)" %
                    (value, match[1]))
            try:
                p.parse_s()
                value = p.parse_attribute()
                self.fail("Parsed bad Attribute: %s" % value)
            except parser.XMLWellFormedError:
                pass
        with structures.XMLEntity(s) as e:
            m = [('a', 'b'), ('c', 'd'), ('e', 'f'),
                 ('i', 'i'), ('j', 'j'), ('g', 'h%')]
            p = parser.XMLParser(e)
            p.dont_check_wellformedness = True
            p.sgml_shorttag = True
            for match in m:
                p.parse_s()
                name, value = p.parse_attribute()
                self.assertTrue(
                    name == match[0],
                    "Compatibility: Attribute name match failed: %s "
                    "(expected %s)" % (name, match[0]))
                self.assertTrue(
                    value == match[1],
                    "Compatibility: Attribute value match failed: %s "
                    "(expected %s)" % (value, match[1]))
            self.assertTrue(p.the_char is None, "Short parse of ETag tests")

    def test_etag(self):
        """[42] ETag ::= '</' Name S? '>' """
        s = "</elem1>elem2></elem3/>"
        with structures.XMLEntity(s) as e:
            m = ['elem1', 'elem2']
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_etag(p.the_char != '<')
                self.assertTrue(
                    value == match,
                    "ETag name match failed: %s (expected %s)" %
                    (value, match))
            try:
                value = p.parse_etag()
                self.fail("Parsed bad ETag: %s" % value)
            except parser.XMLWellFormedError:
                p.parse_literal('/>')
                pass
            self.assertTrue(p.the_char is None, "Short parse of ETag tests")

    def test_content(self):
        """[43] content ::=
        CharData? ((element | Reference | CDSect | PI | Comment) CharData?)*
        """
        s = """a<elem1/>b&amp;c<![CDATA[&amp;]]>d<?x?>e<!-- y -->f"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInContent
            p.element = structures.Element("a")
            p.parse_content()
            children = list(p.element.get_children())
            self.assertTrue(children[0] == 'a',
                            "First character: %s" % repr(children[0]))
            self.assertTrue(isinstance(children[1], structures.Element),
                            "First element: %s" % repr(children[1]))
            self.assertTrue(children[1].xmlname == 'elem1',
                            "First element name: %s" % repr(
                children[1].xmlname))
            self.assertTrue(children[2] == 'b&c&amp;def',
                            "Remaining data: %s" % repr(children[2]))

    def test_empty_elem_tag(self):
        """[44] EmptyElemTag ::= '<' Name (S Attribute)* S? '/> """
        s = """<elem1/> <elem2 /> <elem3 x="1"/>"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            m = [('elem1', {}), ('elem2', {}), ('elem3', {'x': '1'})]
            for match in m:
                try:
                    p.parse_empty_elem_tag()
                    self.fail("Expected ParseEmptyElem to be unimplemented.")
                except NotImplementedError:
                    pass
                name, attrs, emptyFlag = p.parse_stag()
                self.assertTrue(emptyFlag, "Expected empty element tag")
                self.assertTrue(name == match[0],
                                "Element name mismatch: %s" % name)
                self.assertTrue(attrs == match[1],
                                "Element attrs mismatch: %s" % repr(attrs))
                p.parse_s()
            self.assertTrue(p.the_char is None,
                            "Short parse of empty elements")

    def test_element_decl(self):
        """[45] elementdecl ::= '<!ELEMENT' S Name S contentspec S? '>' """
        s = """<!ELEMENT elem1 ANY>
\t\t<!ELEMENT elem2 (#PCDATA)>
\t\t<!ELEMENT elem3 ( A | ( B,C )? | (D,E,F)* | (G,H)+ | (I | (J,K)+)* ) >
\t\t"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            # ensures that elements are declared in the DTD
            p.dtd = structures.XMLDTD()
            try:
                while True:
                    p.parse_element_decl(p.the_char != '<')
                    p.parse_s()
            except parser.XMLWellFormedError:
                pass
            etype = p.dtd.get_element_type('elem1')
            self.assertTrue(etype.content_type == structures.ElementType.Any,
                            "First element")
            etype = p.dtd.get_element_type('elem2')
            self.assertTrue(etype.content_type == structures.ElementType.Mixed,
                            "Second element")
            etype = p.dtd.get_element_type('elem3')
            self.assertTrue(
                etype.content_type == structures.ElementType.ElementContent,
                "Third element")
            self.assertTrue(
                etype.content_model.children[4].children[1].children[1].name ==
                "K", "Third element model")
            self.assertTrue(p.the_char is None,
                            "Short parse on element declarations")

    def test_content_spec(self):
        """[46] contentspec ::= 'EMPTY' | 'ANY' | Mixed | children """
        s = """EMPTY
\t\t\tANY
\t\t\t(#PCDATA)
\t\t\t(#PCDATA)*
\t\t\t( #PCDATA | Steve1 | Steve2 )*
\t\t\t(Particle2|Particle3)?
\t\t\t(Particle4,Particle5,Particle6)+"""
        with structures.XMLEntity(s) as e:
            m = [(structures.ElementType.Empty, None, None, None),
                 (structures.ElementType.Any, None, None, None),
                 (structures.ElementType.Mixed, structures.XMLChoiceList,
                  structures.XMLContentParticle.ZeroOrMore, 0),
                 (structures.ElementType.Mixed, structures.XMLChoiceList,
                  structures.XMLContentParticle.ZeroOrMore, 0),
                 (structures.ElementType.Mixed, structures.XMLChoiceList,
                  structures.XMLContentParticle.ZeroOrMore, 2),
                 (structures.ElementType.ElementContent,
                  structures.XMLChoiceList,
                  structures.XMLContentParticle.ZeroOrOne, 2),
                 (structures.ElementType.ElementContent,
                  structures.XMLSequenceList,
                  structures.XMLContentParticle.OneOrMore, 3)]
            p = parser.XMLParser(e)
            for match in m:
                etype = structures.ElementType()
                p.parse_content_spec(etype)
                self.assertTrue(etype.content_type == match[0],
                                "Content type mismatch")
                if match[1] is None:
                    self.assertTrue(etype.content_model is None,
                                    "Content model type mismatch")
                else:
                    self.assertTrue(
                        isinstance(etype.content_model, match[1]),
                        "Content model type mismatch")
                    self.assertTrue(
                        etype.content_model.occurrence == match[2],
                        "Content model occurrence mismatch")
                    self.assertTrue(
                        len(etype.content_model.children) == match[3],
                        "Number of children in content model mismatch")
                p.parse_s()
            self.assertTrue(
                p.the_char is None,
                "Incomplete parse in contentspec tests: %s" % repr(p.the_char))

    def test_children(self):
        """[47] children ::= (choice | seq) ('?' | '*' | '+')? """
        s = """(Particle2|Particle3)?
\t\t\t(Particle4,Particle5)*
\t\t\t(Particle6,(Particle7|Particle8),(Particle9,Particle10))+
\t\t\tParticle1"""
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLChoiceList,
                  structures.XMLContentParticle.ZeroOrOne),
                 (structures.XMLSequenceList,
                  structures.XMLContentParticle.ZeroOrMore),
                 (structures.XMLSequenceList,
                  structures.XMLContentParticle.OneOrMore)]
            p = parser.XMLParser(e)
            for match in m:
                cp = p.parse_children()
                self.assertTrue(isinstance(cp, match[0]),
                                "Particle type mismatch")
                self.assertTrue(
                    cp.occurrence == match[1],
                    "Particle occurrence mismatch, %i (expected %i)" %
                    (cp.occurrence, match[1]))
                p.parse_s()
            try:
                cp = p.parse_children()
                self.fail("Name not allowed outside choice or sequence")
            except parser.XMLFatalError:
                # fails to parse 'Particle1'
                p.parse_literal('Particle1')
            self.assertTrue(
                p.the_char is None,
                "Incomplete parse in children tests: %s" % repr(p.the_char))

    def test_cp(self):
        """[48] cp ::= (Name | choice | seq) ('?' | '*' | '+')? """
        s = """Particle1
\t\t\t(Particle2|Particle3)?
\t\t\t(Particle4,Particle5)*
\t\t\t(Particle6,(Particle7|Particle8),(Particle9,Particle10))+"""
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLNameParticle,
                  structures.XMLContentParticle.ExactlyOnce),
                 (structures.XMLChoiceList,
                  structures.XMLContentParticle.ZeroOrOne),
                 (structures.XMLSequenceList,
                  structures.XMLContentParticle.ZeroOrMore),
                 (structures.XMLSequenceList,
                  structures.XMLContentParticle.OneOrMore)]
            p = parser.XMLParser(e)
            for match in m:
                cp = p.parse_cp()
                self.assertTrue(isinstance(cp, match[0]),
                                "Particle type mismatch")
                self.assertTrue(
                    cp.occurrence == match[1],
                    "Particle occurrence mismatch, %i (expected %i)" %
                    (cp.occurrence, match[1]))
                p.parse_s()
            self.assertTrue(
                p.the_char is None,
                "Incomplete parse in CP tests: %s" % repr(p.the_char))

    def test_choice(self):
        """[49] choice ::= '(' S? cp ( S? '|' S? cp )+ S? ')' """
        s = "(Particle1|Particle2?|Particle3*)( Particle4+ | Particle5 )"\
            "(Particle6|Particle7+)+(Particle8*)()"
        with structures.XMLEntity(s) as e:
            m = [[('Particle1', structures.XMLContentParticle.ExactlyOnce),
                  ('Particle2', structures.XMLContentParticle.ZeroOrOne),
                  ('Particle3', structures.XMLContentParticle.ZeroOrMore)],
                 [('Particle4', structures.XMLContentParticle.OneOrMore),
                  ('Particle5', structures.XMLContentParticle.ExactlyOnce)],
                 [('Particle6', structures.XMLContentParticle.ExactlyOnce),
                  ('Particle7', structures.XMLContentParticle.OneOrMore)]]
            p = parser.XMLParser(e)
            for match in m:
                cp = p.parse_choice()
                self.assertTrue(isinstance(cp, structures.XMLChoiceList),
                                "Choice list match failed")
                self.assertTrue(len(cp.children) == len(match),
                                "Choice list match length mismatch")
                for cpi, mi in zip(cp.children, match):
                    self.assertTrue(
                        isinstance(cpi, structures.XMLNameParticle),
                        "Not a name particle")
                    self.assertTrue(cpi.name == mi[0],
                                    "Particle name mismatch")
                    self.assertTrue(cpi.occurrence == mi[1],
                                    "Particle occurrence mismatch")
            self.assertTrue(
                p.parse_literal('+'), "Final occurrence parsed in error")
            try:
                cp = p.parse_choice()
                self.fail("Singleton choice not allowed")
            except parser.XMLFatalError:
                # fails to parse ')'
                p.parse_literal(')')
            try:
                cp = p.parse_choice()
                self.fail("Empty choice not allowed")
            except parser.XMLFatalError:
                # fails to parse ')'
                p.parse_literal(')')
            self.assertTrue(
                p.the_char is None,
                "Incomplete parse in choice tests: %s" % repr(p.the_char))

    def test_seq(self):
        """[50] seq ::= '(' S? cp ( S? ',' S? cp )* S? ')' """
        s = "(Particle1,Particle2?,Particle3*)( Particle4+ , "\
            "Particle5 )(Particle6+)+()"
        with structures.XMLEntity(s) as e:
            m = [[('Particle1', structures.XMLContentParticle.ExactlyOnce),
                  ('Particle2', structures.XMLContentParticle.ZeroOrOne),
                  ('Particle3', structures.XMLContentParticle.ZeroOrMore)],
                 [('Particle4', structures.XMLContentParticle.OneOrMore),
                  ('Particle5', structures.XMLContentParticle.ExactlyOnce)],
                 [('Particle6', structures.XMLContentParticle.OneOrMore)]]
            p = parser.XMLParser(e)
            for match in m:
                cp = p.parse_seq()
                self.assertTrue(isinstance(cp, structures.XMLSequenceList),
                                "Sequence match failed")
                self.assertTrue(len(cp.children) == len(match),
                                "Sequence match length mismatch")
                for cpi, mi in zip(cp.children, match):
                    self.assertTrue(
                        isinstance(cpi, structures.XMLNameParticle),
                        "Not a name particle")
                    self.assertTrue(cpi.name == mi[0],
                                    "Particle name mismatch")
                    self.assertTrue(cpi.occurrence == mi[1],
                                    "Particle occurrence mismatch")
            self.assertTrue(
                p.parse_literal('+'), "Final occurrence parsed in error")
            try:
                cp = p.parse_seq()
                self.fail("Empty sequence not allowed")
            except parser.XMLFatalError:
                # fails to parse ')'
                p.parse_literal(')')
            self.assertTrue(
                p.the_char is None,
                "Incomplete parse in sequence tests: %s" % repr(p.the_char))

    def test_mixed(self):
        """[51] Mixed ::=
        '(' S? '#PCDATA' (S? '|' S? Name)* S? ')*' | '(' S? '#PCDATA' S? ')'
        """
        s = "(#PCDATA)(#PCDATA)*( #PCDATA | Steve1 | Steve2 )*( #PCDATA "\
            "|Steve1|Steve2)*(#PCDATA|Steve1)(Steve1|#PCDATA)*"
        with structures.XMLEntity(s) as e:
            m = [[], [], ['Steve1', 'Steve2'], ['Steve1', 'Steve2']]
            p = parser.XMLParser(e)
            for match in m:
                cp = p.parse_mixed()
                self.assertTrue(
                    isinstance(cp, structures.XMLChoiceList),
                    "Mixed must be a choice")
                self.assertTrue(
                    cp.occurrence ==
                    structures.XMLContentParticle.ZeroOrMore,
                    "Mixed must be '*'")
                self.assertTrue(
                    len(cp.children) == len(match),
                    "Particle count mismatch: %s" % str(match))
                for cpi, mi in zip(cp.children, match):
                    self.assertTrue(
                        isinstance(cpi, structures.XMLNameParticle),
                        "Mixed particles must be names")
                    self.assertTrue(
                        cpi.occurrence ==
                        structures.XMLContentParticle.ExactlyOnce,
                        "Mixed occurrence")
                    self.assertTrue(cpi.name == mi, "Mixed particle name")
            try:
                p.parse_mixed()
                self.fail("Missed trailing *")
            except parser.XMLFatalError:
                # fails to parse ')*'
                p.parse_literal(')')
            try:
                p.parse_mixed()
                self.fail("#PCDATA must come first")
            except parser.XMLFatalError:
                # fails to parse '#PCDATA'
                p.parse_literal('Steve1|#PCDATA)*')
            self.assertTrue(
                p.the_char is None,
                "Incomplete parse in Mixed tests: %s" % repr(p.the_char))

    def test_attlist_decl(self):
        """[52] AttlistDecl ::= '<!ATTLIST' S Name AttDef* S? '>' """
        s = """<!ATTLIST elem attr CDATA 'Steve' attr2 CDATA #IMPLIED>
\t\t<!ATTLIST elem attr3 (1|2|3) '1'>
\t\t elem2 (1|2|3) >"""
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            try:
                while True:
                    p.parse_attlist_decl(p.the_char != '<')
                    p.parse_s()
            except parser.XMLWellFormedError:
                pass
            alist = p.dtd.get_attribute_list('elem')
            self.assertTrue(
                alist['attr'].defaultValue == 'Steve', "First attribute")
            self.assertTrue(
                alist['attr2'].presence ==
                structures.XMLAttributeDefinition.IMPLIED, "Second attribute")
            self.assertTrue(
                alist['attr3'].type ==
                structures.XMLAttributeDefinition.ENUMERATION,
                "Third attribute")
            alist = p.dtd.get_attribute_list('elem2')
            self.assertTrue(alist is None, "Bad attribute")

    def test_att_def(self):
        """[53] AttDef ::= S Name S AttType S DefaultDecl"""
        s = " attr CDATA 'Steve' attr2 CDATA #IMPLIED attr3 (1|2|3) '1' "\
            "attr4 #REQUIRED"
        with structures.XMLEntity(s) as e:
            m = [('attr', structures.XMLAttributeDefinition.CDATA, None,
                  structures.XMLAttributeDefinition.DEFAULT, 'Steve'),
                 ('attr2', structures.XMLAttributeDefinition.CDATA,
                  None, structures.XMLAttributeDefinition.IMPLIED, None),
                 ('attr3', structures.XMLAttributeDefinition.ENUMERATION,
                  {'1': True, '2': True, '3': True},
                  structures.XMLAttributeDefinition.DEFAULT, '1')]
            p = parser.XMLParser(e)
            for match in m:
                a = p.parse_att_def()
                self.assertTrue(
                    a.name == match[0],
                    "AttDef match failed: %s (expected %s)" %
                    (a.name, match[0]))
                self.assertTrue(
                    a.type == match[1],
                    "AttDef match failed: %i (expected %i)" %
                    (a.type, match[1]))
                self.assertTrue(
                    a.values == match[2],
                    "AttDef match failed: %s (expected %s)" %
                    (a.values, match[2]))
                self.assertTrue(
                    a.presence == match[3],
                    "AttDef match failed: %i (expected %i)" %
                    (a.presence, match[3]))
                self.assertTrue(
                    a.defaultValue == match[4],
                    "AttDef match failed: %s (expected %s)" %
                    (a.defaultValue, match[4]))
            try:
                a = p.parse_att_def()
                self.fail("Parsed bad AttDef: %s" % a.name)
            except parser.XMLFatalError:
                pass

    def test_att_type(self):
        """[54] AttType ::= StringType | TokenizedType | EnumeratedType"""
        s = "CDATA ENTITIES NOTATION (Steve) (1 | 2 | 3) NAMES)"
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLAttributeDefinition.CDATA, None),
                 (structures.XMLAttributeDefinition.ENTITIES, None),
                 (structures.XMLAttributeDefinition.NOTATION, {'Steve': True}),
                 (structures.XMLAttributeDefinition.ENUMERATION,
                  {'1': True, '2': True, '3': True})]
            p = parser.XMLParser(e)
            for match in m:
                a = structures.XMLAttributeDefinition()
                p.parse_att_type(a)
                self.assertTrue(
                    a.type == match[0],
                    "Attribute type match failed: %i (expected %i)" %
                    (a.type, match[0]))
                self.assertTrue(
                    a.values == match[1],
                    "Attribute type match failed: %s (expected %s)" %
                    (a.values, match[1]))
                p.parse_s()
            try:
                a = structures.XMLAttributeDefinition()
                p.parse_att_type(a)
                self.fail("Parsed bad AttType: %i; %s" % (a.type, a.values))
            except parser.XMLFatalError:
                pass

    def test_string_type(self):
        """[55] StringType ::= 'CDATA' """
        s = "CDATA ID"
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLAttributeDefinition.CDATA, None)]
            p = parser.XMLParser(e)
            for match in m:
                a = structures.XMLAttributeDefinition()
                p.parse_string_type(a)
                self.assertTrue(
                    a.type == match[0],
                    "String type match failed: %i (expected %i)" %
                    (a.type, match[0]))
                self.assertTrue(
                    a.values == match[1],
                    "String type match failed: %s (expected %s)" %
                    (a.values, match[1]))
                p.parse_s()
            try:
                a = structures.XMLAttributeDefinition()
                p.parse_string_type(a)
                self.fail("Parsed bad StringType: %i; %s" % (a.type, a.values))
            except parser.XMLFatalError:
                pass

    def test_tokenized_type(self):
        """[56] TokenizedType ::=
        'ID' | 'IDREF' | 'IDREFS' | 'ENTITY' | 'ENTITIES' | 'NMTOKEN' |
        'NMTOKENS' """
        s = "ID IDREF IDREFS ENTITY ENTITIES NMTOKEN NMTOKENS NAME"
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLAttributeDefinition.ID, None),
                 (structures.XMLAttributeDefinition.IDREF, None),
                 (structures.XMLAttributeDefinition.IDREFS, None),
                 (structures.XMLAttributeDefinition.ENTITY, None),
                 (structures.XMLAttributeDefinition.ENTITIES, None),
                 (structures.XMLAttributeDefinition.NMTOKEN, None),
                 (structures.XMLAttributeDefinition.NMTOKENS, None)]
            p = parser.XMLParser(e)
            for match in m:
                a = structures.XMLAttributeDefinition()
                p.parse_tokenized_type(a)
                self.assertTrue(
                    a.type == match[0],
                    "Tokenized type match failed: %i (expected %i)" %
                    (a.type, match[0]))
                self.assertTrue(
                    a.values == match[1],
                    "Tokenized type match failed: %s (expected %s)" %
                    (a.values, match[1]))
                p.parse_s()
            try:
                a = structures.XMLAttributeDefinition()
                p.parse_tokenized_type(a)
                self.fail("Parsed bad Tokenized: %i; %s" % (a.type, a.values))
            except parser.XMLFatalError:
                pass

    def test_enumerated_type(self):
        """[57] EnumeratedType ::= NotationType | Enumeration """
        s = "NOTATION (Steve1)NOTATION (Steve1|Steve2)(1|2|3)NOTATION (1|2|3)"
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLAttributeDefinition.NOTATION,
                  {'Steve1': True}),
                 (structures.XMLAttributeDefinition.NOTATION,
                  {'Steve1': True, 'Steve2': True}),
                 (structures.XMLAttributeDefinition.ENUMERATION,
                  {'1': True, '2': True, '3': True})]
            p = parser.XMLParser(e)
            for match in m:
                a = structures.XMLAttributeDefinition()
                p.parse_enumerated_type(a)
                self.assertTrue(
                    a.type == match[0],
                    "Enumerated type match failed: %i (expected %i)" %
                    (a.type, match[0]))
                self.assertTrue(
                    a.values == match[1],
                    "Enumerated type match failed: %s (expected %s)" %
                    (a.values, match[1]))
            try:
                a = structures.XMLAttributeDefinition()
                p.parse_enumerated_type(a)
                self.fail("Parsed bad EnumeratedType: %i; %s" %
                          (a.type, a.values))
            except parser.XMLFatalError:
                pass

    def test_notation_type(self):
        """[58] NotationType ::=
        'NOTATION' S '(' S? Name (S? '|' S? Name)* S? ')'"""
        s = "NOTATION (Steve1)NOTATION (Steve1|Steve2|Steve3)NOTATION "\
            "( Steve1 ) ( Steve1 | Steve2 | Steve3 )NOTATION(Steve1|Steve2)"
        with structures.XMLEntity(s) as e:
            m = [{'Steve1': True},
                 {'Steve1': True, 'Steve2': True, 'Steve3': True},
                 {'Steve1': True},
                 {'Steve1': True, 'Steve2': True, 'Steve3': True}]
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_notation_type(p.the_char != 'N')
                self.assertTrue(value == match,
                                "NotationType match failed: %s (expected %s)" %
                                (value, match))
            try:
                value = p.parse_notation_type()
                self.fail("Parsed bad NotationType: %s" % value)
            except parser.XMLFatalError:
                pass

    def test_enumeration(self):
        """[59] Enumeration ::= '(' S? Nmtoken (S? '|' S? Nmtoken)* S? ')' """
        s = "(Steve1)(Steve1|Steve2|3Steve)( Steve1 )"\
            "( Steve1 | Steve2 | 3Steve )(Steve1|Steve 2)"
        with structures.XMLEntity(s) as e:
            m = [{'Steve1': True},
                 {'Steve1': True, 'Steve2': True, '3Steve': True},
                 {'Steve1': True},
                 {'Steve1': True, 'Steve2': True, '3Steve': True}]
            p = parser.XMLParser(e)
            for match in m:
                value = p.parse_enumeration()
                self.assertTrue(value == match,
                                "Enumeration match failed: %s (expected %s)" %
                                (value, match))
            try:
                value = p.parse_enumeration()
                self.fail("Parsed bad Enumeration: %s" % value)
            except parser.XMLFatalError:
                pass

    def test_default_decl(self):
        """[60] DefaultDecl ::=
        '#REQUIRED' | '#IMPLIED' | (('#FIXED' S)? AttValue) """
        s = "#REQUIRED #IMPLIED #FIXED 'Steve' 'Steve'Steve"
        with structures.XMLEntity(s) as e:
            m = [(structures.XMLAttributeDefinition.REQUIRED, None),
                 (structures.XMLAttributeDefinition.IMPLIED, None),
                 (structures.XMLAttributeDefinition.FIXED, 'Steve'),
                 (structures.XMLAttributeDefinition.DEFAULT, 'Steve')]
            p = parser.XMLParser(e)
            for match in m:
                a = structures.XMLAttributeDefinition()
                p.parse_default_decl(a)
                self.assertTrue(
                    a.presence == match[0],
                    "DefaultDecl declaration match failed: %i (expected %i)" %
                    (a.presence, match[0]))
                self.assertTrue(
                    a.defaultValue == match[1],
                    "DefaultDecl value match failed: %s (expected %s)" %
                    (a.defaultValue, match[1]))
                p.parse_s()
            try:
                a = structures.XMLAttributeDefinition()
                p.parse_default_decl(a)
                self.fail("Parsed bad DefaultDecl: (%i,%s)" %
                          (a.presence, a.defaultValue))
            except parser.XMLFatalError:
                pass

    def test_conditional_sect(self):
        """[61] conditionalSect ::= includeSect | ignoreSect"""
        s = "<![%include;[ <!ENTITY included 'yes'> <![ IGNORE [ <!ENTITY "\
            "ignored 'no'> ]]> ]]>"
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(
                structures.XMLParameterEntity('include', 'INCLUDE'))
            p.check_validity = True
            p.refMode = parser.XMLParser.RefModeInDTD
            try:
                p.parse_conditional_sect()
                self.assertTrue(
                    p.the_char is None,
                    "Short parse on ConditionalSect: %s" % p.the_char)
                self.assertTrue(
                    p.dtd.get_entity('included').definition == 'yes',
                    "included entity declaration")
                self.assertTrue(p.dtd.get_entity('ignored') is None,
                                "ignored entity declaration")
            except parser.XMLWellFormedError as e:
                self.fail("parse_conditional_sect positive test: %s\n%s" %
                          (s, str(e)))

    def test_include_sect(self):
        """[62] includeSect ::=
        '<![' S? 'INCLUDE' S? '[' extSubsetDecl ']]>' """
        for s in ["<![INCLUDE[]]>", "<![ INCLUDE [ <?stuff?> ]]>",
                  "<![ INCLUDE [<![IGNORE[ included ]]> ]]>",
                  "<![%include;[]]>"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.dtd = structures.XMLDTD()
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('include', 'INCLUDE'))
                p.check_validity = True
                p.refMode = parser.XMLParser.RefModeInDTD
                try:
                    p.parse_include_sect()
                    self.assertTrue(
                        p.the_char is None,
                        "Short parse on IncludeSect: %s" % p.the_char)
                except parser.XMLWellFormedError as e:
                    self.fail("parse_include_sect positive test: %s\n%s" %
                              (s, str(e)))
        for s in [" <![INCLUDE[]>", "<! [INCLUDE[]]>", "<![INCLUDE[] ]>"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.refMode = parser.XMLParser.RefModeInDTD
                try:
                    p.parse_include_sect()
                    self.fail("parse_include_sect negative well-formedness "
                              "test: %s" % s)
                except parser.XMLWellFormedError:
                    pass
        for s in ["<![ %include1; <?stuff?> ]]>",
                  "%include2; [ <!--stuff--> ]]>",
                  "<![ INCLUDE [ <?stuff?> %include3;"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.refMode = parser.XMLParser.RefModeInContent
                p.dtd = structures.XMLDTD()
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('include1', 'INCLUDE ['))
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('include2', '<![INCLUDE '))
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('include3',
                                                  '<?included?> ]]>'))
                p.check_validity = True
                p.raiseValidityErrors = True
                p.refMode = parser.XMLParser.RefModeInDTD
                try:
                    p.parse_s()
                    p.parse_include_sect()
                    self.fail("parse_include_sect negative validity "
                              "test: %s" % s)
                except parser.XMLWellFormedError as e:
                    logging.info(str(e))
                    self.fail("parse_include_sect spurious well-formed "
                              "error: %s" % s)
                except structures.XMLValidityError:
                    pass

    def test_ignore_sect(self):
        """[63] ignoreSect ::=
        '<![' S? 'IGNORE' S? '[' ignoreSectContents* ']]>' """
        for s in ["<![IGNORE[]]>", "<![ IGNORE [ stuff ]]>",
                  "<![ IGNORE [<![INCLUDE[ ignored ]]> ]]>",
                  "<![%ignore;[]]>"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.dtd = structures.XMLDTD()
                p.dtd.declare_entity(structures.XMLParameterEntity('ignore',
                                                                   'IGNORE'))
                p.check_validity = True
                p.refMode = parser.XMLParser.RefModeInDTD
                try:
                    p.parse_ignore_sect()
                    self.assertTrue(
                        p.the_char is None,
                        "Short parse on IgnoreSect: %s" % p.the_char)
                except parser.XMLWellFormedError:
                    self.fail("parse_ignore_sect positive test: %s" % s)
        for s in [" <![IGNORE[]>", "<! [IGNORE[]]>", "<![IGNORE[] ]>"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.refMode = parser.XMLParser.RefModeInDTD
                try:
                    p.parse_ignore_sect()
                    self.fail("parse_ignore_sect negative well-formedness "
                              "test: %s" % s)
                except parser.XMLWellFormedError:
                    pass
        for s in ["<![ %ignore1; stuff ]]>", "%ignore2; [ stuff ]]>",
                  # "<![ IGNORE [ stuff %ignore3;" -
                  # this PE is ignored so we can't test this
                  ]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.refMode = parser.XMLParser.RefModeInContent
                p.dtd = structures.XMLDTD()
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('ignore1', 'IGNORE ['))
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('ignore2', '<![IGNORE '))
                p.dtd.declare_entity(
                    structures.XMLParameterEntity('ignore3', 'ignored ]]>'))
                p.check_validity = True
                p.raiseValidityErrors = True
                p.refMode = parser.XMLParser.RefModeInDTD
                try:
                    p.parse_s()
                    p.parse_ignore_sect()
                    self.fail(
                        "parse_ignore_sect negative validity test: %s" % s)
                except parser.XMLWellFormedError as e:
                    logging.info(str(e))
                    self.fail(
                        "parse_ignore_sect spurious well-formed error: %s" % s)
                except structures.XMLValidityError:
                    pass

    def test_ignore_sect_contents(self):
        """[64] ignoreSectContents ::=
        Ignore ('<![' ignoreSectContents ']]>' Ignore)* """
        s = "preamble<![ INCLUDE [ %x; <![IGNORE[ also ignored ]]>]]> also "\
            "ignored]]>end"
        with structures.XMLEntity(s) as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('x', 'bad'))
            p.parse_ignore_sect_contents()
            p.parse_literal(']]>')
            self.assertTrue(p.parse_name() == 'end',
                            "Failed to parse ignore section contents")

    def test_ignore(self):
        """[65] Ignore ::= Char* - (Char* ('<![' | ']]>') Char*) """
        s = "<!FIRST%x;1st]]>second<![third]]3rd<!3rd<3rd]3rd"
        with structures.XMLEntity(s) as e:
            # These tests are a bit odd because we follow the entity and
            # not the parser so we expect the trailing markup to be
            # consumed; we check the_char too to be sure.
            m = [('<!FIRST%x;1st]]>', ']'), ('second<![', '<'),
                 ('third]]3rd<!3rd<3rd]3rd', None)]
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('x', 'bad'))
            pos = 0
            for match, c in m:
                p.parse_ignore()
                self.assertTrue(
                    p.the_char == c,
                    "Parser position: %s (expected %s)" % (p.the_char, c))
                self.assertTrue(s[pos:e.line_pos - 1] == match,
                                "Match failed: %s (expected %s)" %
                                (s[pos:e.line_pos - 1], match))
                p.next_char()
                pos = pos + len(match)

    def test_char_ref(self):
        """[66] CharRef ::= '&#' [0-9]+ ';'  |  '&#x' [0-9a-fA-F]+ ';' """
        for m in (parser.XMLParser.RefModeInContent,
                  parser.XMLParser.RefModeInAttributeValue,
                  parser.XMLParser.RefModeInEntityValue):
            with structures.XMLEntity("&#xe9;") as e:
                p = parser.XMLParser(e)
                p.refMode = m
                data = p.parse_char_ref()
                self.assertTrue(data == character(0xE9),
                                "parse_char_ref failed to interpret hex "
                                "character reference: %s" % data)
                self.assertTrue(p.the_char is None,
                                "Short parse on CharRef: %s" % p.the_char)
        with structures.XMLEntity("&#xe9;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeAsAttributeValue
            data = p.parse_char_ref()
            self.assertTrue(data == "&#xe9;",
                            "parse_char_ref AsAttribute: %s" % data)
            self.assertTrue(p.the_char is None,
                            "Short parse on CharRef: %s" % p.the_char)
        with structures.XMLEntity("&#xe9;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInDTD
            try:
                data = p.parse_char_ref()
                self.fail("parse_char_ref InDTD")
            except parser.XMLForbiddenEntityReference:
                pass
        with structures.XMLEntity("#233;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInContent
            data = p.parse_char_ref(True)
            self.assertTrue(data == character(0xE9),
                            "parse_char_ref failed to interpret decimal "
                            "character reference: %s" % data)
            self.assertTrue(p.the_char is None,
                            "Short parse on CharRef: %s" % p.the_char)
        for s in [" &#xe9;", "& #xe9;", "&# xe9;", "&#xe 9;", "&#xe9 ;",
                  "&#e9;", "&#xg9;", "&#1;", "&#;", "&#x;"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.refMode = parser.XMLParser.RefModeInContent
                try:
                    p.parse_char_ref()
                    self.fail("parse_char_ref negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_reference(self):
        """[67] Reference ::= EntityRef | CharRef """
        with structures.XMLEntity("&animal;") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLGeneralEntity('animal', 'dog'))
            p.refMode = parser.XMLParser.RefModeInContent
            data = p.parse_reference()
            self.assertTrue(
                data == '',
                "parse_reference failed to interpret entity reference")
            self.assertTrue(p.parse_name() == 'dog',
                            "Failed to replace Entity in Content")
            self.assertTrue(p.the_char is None, "Short parse on EntityRef")
        with structures.XMLEntity("&#xe9;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInContent
            data = p.parse_reference()
            self.assertTrue(
                data == character(0xE9),
                "parse_reference failed to interpret character reference: %s" %
                data)
            self.assertTrue(p.the_char is None,
                            "Short parse on EntityRef: %s" % p.the_char)
        for s in [" &animal;", "& animal;", "&animal ;", "animal", "#xE9"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_reference()
                    self.fail("parse_reference negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_entity_ref(self):
        """[68] EntityRef ::= '&' Name ';'"""
        with structures.XMLEntity("&amp;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInContent
            self.assertTrue(p.parse_entity_ref() == '&',
                            "Predefined entity not recognized in Content")
            self.assertTrue(p.the_char is None,
                            "Short parse on Entity replacement text")
        with structures.XMLEntity("&animal;") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLGeneralEntity('animal', 'dog'))
            p.refMode = parser.XMLParser.RefModeInContent
            self.assertTrue(p.parse_entity_ref() == '',
                            "EntityRef not recognized in Content")
            # This should result in the entity value being expanded into
            # the stream
            self.assertTrue(p.parse_name() == 'dog',
                            "Failed to replace Entity in Content")
            self.assertTrue(
                p.the_char is None, "Short parse on Entity replacement text")
        with structures.XMLEntity("animal;") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLGeneralEntity('animal', 'dog'))
            p.refMode = parser.XMLParser.RefModeInAttributeValue
            self.assertTrue(p.parse_entity_ref(True) == '',
                            "EntityRef not recognized in Attribute Value")
            # This should result in the entity value being expanded into
            # the stream
            self.assertTrue(p.parse_name() == 'dog',
                            "Failed to replace Entity in Attribute Vaue")
            self.assertTrue(
                p.the_char is None, "Short parse on Entity replacement text")
        with structures.XMLEntity("&animal;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeAsAttributeValue
            try:
                p.parse_entity_ref()
                self.fail("EntityRef recognized as Attribute Value")
            except parser.XMLForbiddenEntityReference:
                pass
        with structures.XMLEntity("&animal;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInEntityValue
            data = p.parse_entity_ref()
            self.assertTrue(data == '&animal;',
                            "EntityRef recognized in EntityValue: %s" % data)
            self.assertTrue(p.the_char is None, "Short parse on EntityRef")
        with structures.XMLEntity("&animal;") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInDTD
            try:
                p.parse_entity_ref()
                self.fail("EntityRef recognized in DTD")
            except parser.XMLForbiddenEntityReference:
                pass
        with structures.XMLEntity("<element attribute='a-&EndAttr;>") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('EndAttr',
                                                               "27'"))
            try:
                p.parse_stag()
                self.fail("EntityRef quote test failed in attribute value")
            except parser.XMLWellFormedError:
                pass

    def test_pe_reference(self):
        """[69] PEReference ::= '%' Name ';' """
        with structures.XMLEntity("%animal;") as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            p.refMode = parser.XMLParser.RefModeInContent
            data = p.parse_pe_reference()
            self.assertTrue(data == '%animal;',
                            "PEReference recognized in content: %s" % data)
            self.assertTrue(p.the_char is None, "Short parse on PEReference")
        with structures.XMLEntity("%animal;") as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            p.refMode = parser.XMLParser.RefModeInAttributeValue
            self.assertTrue(p.parse_pe_reference() == '%animal;',
                            "PEReference recognized in attribute value")
            self.assertTrue(p.the_char is None, "Short parse on PEReference")
        with structures.XMLEntity("%animal;") as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            p.refMode = parser.XMLParser.RefModeAsAttributeValue
            self.assertTrue(p.parse_pe_reference() == "%animal;",
                            "PEReference recognized as attribute value")
            self.assertTrue(p.the_char is None, "Short parse on PEReference")
        with structures.XMLEntity("%animal;") as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('animal',
                                                               'dog'))
            p.refMode = parser.XMLParser.RefModeInEntityValue
            self.assertTrue(p.parse_pe_reference() == '',
                            "PEReference not recognized in entity value")
            # This should result in the entity value being expanded into
            # the stream
            self.assertTrue(p.parse_name() == 'dog',
                            "Failed to replace PE in entity value")
            self.assertTrue(p.the_char is None,
                            "Short parse on PEReference replacement text")
        with structures.XMLEntity("%animal;") as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('animal',
                                                               'dog'))
            p.refMode = parser.XMLParser.RefModeInDTD
            self.assertTrue(p.parse_pe_reference() == '',
                            "PEReference not recognized in DTD")
            # This should result in the entity value being expanded into
            # the stream with surrounding spaces
            self.assertTrue(p.parse_s() == ' ',
                            "Missing leading space on PE replacement text")
            self.assertTrue(p.parse_name() == 'dog',
                            "Failed to replace PE in DTD")
            self.assertTrue(p.parse_s() == ' ',
                            "Missing trailing space on PE replacement text")
            self.assertTrue(p.the_char is None, "Short parse on PEReference")
        with structures.XMLEntity('<!ENTITY WhatHeSaid "He said %YN;" >') as e:
            p = parser.XMLParser(e)
            p.check_validity = True
            p.dtd = structures.XMLDTD()
            p.dtd.declare_entity(structures.XMLParameterEntity('YN', '"Yes"'))
            try:
                ge = p.parse_entity_decl()
                # This should result in the entity value being expanded
                # into the stream with surrounding spaces
                self.assertTrue(
                    ge.definition == 'He said "Yes"',
                    "PEReference quote test failed in entity value: %s" %
                    ge.definition)
                self.assertTrue(
                    p.the_char is None,
                    "Short parse on PEReference in entity declaration")
            except parser.XMLWellFormedError:
                self.fail("PEReference quote test failed in entity value")

    def test_entity_decl(self):
        """[70] EntityDecl ::= GEDecl | PEDecl """
        with structures.XMLEntity("<!ENTITY Steve 'SteveValue'>") as e:
            p = parser.XMLParser(e)
            ed = p.parse_entity_decl()
            self.assertTrue(isinstance(ed, structures.XMLGeneralEntity),
                            "parse_entity_decl failed to return GeneralEntity")
            self.assertTrue(ed.name == 'Steve',
                            "Failed to parse general entity name")
            self.assertTrue(p.the_char is None, "Short parse on EntityDecl")
        with structures.XMLEntity(" % Steve 'SteveValue'>") as e:
            p = parser.XMLParser(e)
            ed = p.parse_entity_decl(True)
            self.assertTrue(
                isinstance(ed, structures.XMLParameterEntity),
                "parse_entity_decl failed to return ParameterEntity")
            self.assertTrue(ed.name == 'Steve',
                            "Failed to parse parameter entity name")
            self.assertTrue(p.the_char is None, "Short parse on EntityDecl")

    def test_ge_decl(self):
        """[71] GEDecl ::= '<!ENTITY' S Name S EntityDef S? '>' """
        with structures.XMLEntity("<!ENTITY Steve 'SteveValue'>") as e:
            p = parser.XMLParser(e)
            ge = p.parse_ge_decl()
            self.assertTrue(isinstance(ge, structures.XMLGeneralEntity),
                            "parse_ge_decl failed to return GeneralEntity")
            self.assertTrue(ge.name == 'Steve',
                            "Failed to parse general entity name")
            self.assertTrue(ge.definition == 'SteveValue',
                            "Failed to parse general entity value")
            self.assertTrue(p.the_char is None, "Short parse on GEDecl")
        with structures.XMLEntity(
                "Steve PUBLIC 'Steve' '/home/steve.txt' NDATA SteveN  >") as e:
            p = parser.XMLParser(e)
            ge = p.parse_ge_decl(True)
            self.assertTrue(ge.definition.public == 'Steve',
                            "parse_ge_decl failed to parse external public ID")
            self.assertTrue(ge.definition.system == '/home/steve.txt',
                            "parse_ge_decl failed to parse external system ID")
            self.assertTrue(
                ge.notation == 'SteveN',
                "parse_ge_decl failed to parse unparsed entity notation")
            self.assertTrue(p.the_char is None, "Short parse on GEDecl")
        for s in ["<!entity Steve 'v'>", "<!ENTITYSteve 'v'>",
                  "<!ENTITY Steve PUBLIC 'Steve' "
                  "'/home/steve.txt'NDATA SteveN >",
                  "  Steve PUBLIC 'Steve' '/home/steve.txt' NDATA SteveN  >"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    ge = p.parse_ge_decl(s[0] != '<')
                    self.fail("GEDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_pe_decl(self):
        """[72] PEDecl ::= '<!ENTITY' S '%' S Name S PEDef S? '>' """
        with structures.XMLEntity("<!ENTITY % Steve 'SteveValue'>") as e:
            p = parser.XMLParser(e)
            p.refMode = parser.XMLParser.RefModeInDTD
            pe = p.parse_pe_decl()
            self.assertTrue(isinstance(pe, structures.XMLParameterEntity),
                            "parse_pe_decl failed to return ParameterEntity")
            self.assertTrue(pe.name == 'Steve',
                            "Failed to parse parameter entity name")
            self.assertTrue(pe.definition == 'SteveValue',
                            "Failed to parse parameter entity value")
            self.assertTrue(p.the_char is None, "Short parse on PEDecl")
        with structures.XMLEntity(
                "% Steve PUBLIC 'Steve' '/home/steve.txt'   >") as e:
            p = parser.XMLParser(e)
            pe = p.parse_pe_decl(True)
            self.assertTrue(
                pe.definition.public == 'Steve',
                "parse_pe_decl failed to parse external public ID")
            self.assertTrue(
                pe.definition.system == '/home/steve.txt',
                "parse_pe_decl failed to parse external system ID")
            self.assertTrue(p.the_char is None, "Short parse on PEDecl")
        for s in ["<!entity % Steve 'v'>", "<!ENTITY% Steve 'v'>",
                  "<!ENTITY %Steve 'v'>", "<!ENTITY % Steve'v'>",
                  "  % Steve PUBLIC 'Steve' '/home/steve.txt'   >"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    pe = p.parse_pe_decl(s[0] != '<')
                    self.fail("PEDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_entity_def(self):
        """[73] EntityDef ::= EntityValue | (ExternalID NDataDecl?) """
        with structures.XMLEntity("'Steve'") as e:
            p = parser.XMLParser(e)
            ge = structures.XMLGeneralEntity()
            p.parse_entity_def(ge)
            self.assertTrue(is_unicode(ge.definition),
                            "parse_entity_def failed to for internal entity")
            self.assertTrue(ge.definition == 'Steve',
                            "Failed to parse internal entity value")
            self.assertTrue(
                ge.notation is None, "Found notation for internal entity")
            self.assertTrue(p.the_char is None, "Short parse on EntityDef")
        with structures.XMLEntity("PUBLIC 'Steve' '/home/steve.txt'") as e:
            p = parser.XMLParser(e)
            ge = structures.XMLGeneralEntity()
            p.parse_entity_def(ge)
            self.assertTrue(
                isinstance(ge.definition, structures.XMLExternalID),
                "parse_entity_def failed for external entity")
            self.assertTrue(
                ge.definition.public == 'Steve',
                "parse_entity_def failed to parse external public ID")
            self.assertTrue(
                ge.definition.system == '/home/steve.txt',
                "parse_entity_def failed to parse external system ID")
            self.assertTrue(
                ge.notation is None, "Found notation for internal entity")
            self.assertTrue(p.the_char is None, "Short parse on EntityDef")
        with structures.XMLEntity("SYSTEM '/path' NDATA SteveN") as e:
            p = parser.XMLParser(e)
            ge = structures.XMLGeneralEntity()
            p.parse_entity_def(ge)
            self.assertTrue(ge.definition.public is None,
                            "parse_entity_def found spurious public ID")
            self.assertTrue(
                ge.definition.system == '/path',
                "parse_entity_def failed to parse external system ID")
            self.assertTrue(
                ge.notation == 'SteveN',
                "Failed to find notation for unparsed external entity")
            self.assertTrue(p.the_char is None, "Short parse on EntityDef")
        for s in ["NDATA 'SteveN'", " 'Steve'", " SYSTEM '/path'"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                ge = structures.XMLGeneralEntity()
                try:
                    p.parse_entity_def(ge)
                    self.fail("EntityDef negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_pe_def(self):
        """[74] PEDef ::= EntityValue | ExternalID """
        with structures.XMLEntity("PUBLIC 'Steve' '/home/steve.txt'") as e:
            p = parser.XMLParser(e)
            pe = structures.XMLParameterEntity()
            p.parse_pe_def(pe)
            self.assertTrue(
                isinstance(pe.definition, structures.XMLExternalID),
                "parse_pe_def failed to return "
                "structures.XMLExternalID instance")
            self.assertTrue(pe.definition.public == 'Steve',
                            "Failed to parse external public ID")
            self.assertTrue(pe.definition.system == '/home/steve.txt',
                            "Failed to parse external system ID")
            self.assertTrue(p.the_char is None, "Short parse on PEDef")
        with structures.XMLEntity("'Steve'") as e:
            p = parser.XMLParser(e)
            pe = structures.XMLParameterEntity()
            p.parse_pe_def(pe)
            self.assertTrue(is_unicode(pe.definition),
                            "parse_pe_def failed to return String value")
            self.assertTrue(pe.definition == 'Steve',
                            "Failed to parse simple entity value")
            self.assertTrue(p.the_char is None, "Short parse on PEDef")
        with structures.XMLEntity('"Caf&#xE9;s &amp; Bars"') as e:
            p = parser.XMLParser(e)
            pe = structures.XMLParameterEntity()
            p.parse_pe_def(pe)
            self.assertTrue(is_unicode(pe.definition),
                            "parse_pe_def failed to return String value")
            self.assertTrue(pe.definition == ul('Caf\xe9s &amp; Bars'),
                            "Failed to replace character entities: %s" %
                            repr(pe.definition))
            self.assertTrue(p.the_char is None, "Short parse on PEDef")
        for s in ["Steve", "Caf&#xE9;s &amp; Bars", "PUBLIC 'Steve'"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                pe = structures.XMLParameterEntity()
                try:
                    p.parse_pe_def(pe)
                    self.fail("PEDef negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_external_i_d(self):
        """[75] ExternalID ::=
        'SYSTEM' S SystemLiteral | 'PUBLIC' S PubidLiteral S SystemLiteral """
        with structures.XMLEntity("PUBLIC 'Steve' '/home/steve.txt'") as e:
            p = parser.XMLParser(e)
            xid = p.parse_external_id()
            self.assertTrue(
                xid.public == 'Steve', "Failed to parse external public ID")
            self.assertTrue(xid.system == '/home/steve.txt',
                            "Failed to parse external system ID")
            self.assertTrue(p.the_char is None, "Short parse on ExternalID")
        with structures.XMLEntity("SYSTEM  '/home/steve.txt'") as e:
            p = parser.XMLParser(e)
            xid = p.parse_external_id()
            self.assertTrue(xid.public is None,
                            "Failed to parse external empty public ID")
            self.assertTrue(xid.system == '/home/steve.txt',
                            "Failed to parse external system ID")
            self.assertTrue(p.the_char is None, "Short parse on ExternalID")
        for s in ["PUBLIC 'Steve'", "'Steve'", " SYSTEM '/path'",
                  "SYSTEM'/path'", "PUBLIC'Steve' '/path'",
                  "PUBLIC 'Steve''/path'"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    xid = p.parse_external_id()
                    self.fail("ExternalID negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_n_data_decl(self):
        """[76] NDataDecl ::= S 'NDATA' S Name """
        with structures.XMLEntity("  NDATA Steve") as e:
            p = parser.XMLParser(e)
            self.assertTrue(p.parse_ndata_decl() == "Steve",
                            "Failed to parse NData declaration")
            self.assertTrue(p.the_char is None,
                            "Short parse on NData declaration")
        with structures.XMLEntity(" Steve") as e:
            p = parser.XMLParser(e)
            self.assertTrue(p.parse_ndata_decl(True) == "Steve",
                            "Failed to parse NData declaration (no literal)")
            self.assertTrue(p.the_char is None,
                            "Short parse on NData declaration")
        for s in ["NDATA Steve", " MDATA Steve", "NDATASteve"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_ndata_decl()
                    self.fail("NDataDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_text_decl(self):
        """[77] TextDecl ::= '<?xml' VersionInfo? EncodingDecl S? '?>' """
        with structures.XMLEntity(
                "<?xml version='1.0' encoding='latin-1'  ?>") as e:
            p = parser.XMLParser(e)
            t = p.parse_text_decl()
            self.assertTrue(t.version == "1.0")
            self.assertTrue(t.encoding == "latin-1",
                            "Failed to parse encoding in text declaration")
            self.assertTrue(p.the_char is None, "Short parse on TextDecl")
        with structures.XMLEntity('<?xml encoding = "latin-1"?>') as e:
            p = parser.XMLParser(e)
            t = p.parse_text_decl()
            self.assertTrue(t.version is None)
            self.assertTrue(t.encoding == "latin-1",
                            "Failed to parse encoding in text declaration")
            self.assertTrue(p.the_char is None, "Short parse on TextDecl")
        for s in ["<?xml version='1.0' ?>"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_encoding_decl()
                    self.fail("TextDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    # There is no method for parsing production [78]

    # There is no production [79]

    def test_encoding_decl(self):
        """[80] EncodingDecl ::=
        S 'encoding' Eq ('"' EncName '"' | "'" EncName "'" ) """
        with structures.XMLEntity("  encoding = 'latin-1'") as e:
            p = parser.XMLParser(e)
            self.assertTrue(p.parse_encoding_decl() == "latin-1",
                            "Failed to parse encoding declaration")
            self.assertTrue(p.the_char is None, "Short parse on EncodingDecl")
        with structures.XMLEntity(" = 'latin-1'") as e:
            p = parser.XMLParser(e)
            self.assertTrue(
                p.parse_encoding_decl(True) == "latin-1",
                "Failed to parse encoding declaration (no literal)")
            self.assertTrue(p.the_char is None, "Short parse on EncodingDecl")
        with structures.XMLEntity(' encoding="latin-1"') as e:
            p = parser.XMLParser(e)
            self.assertTrue(p.parse_encoding_decl() == "latin-1",
                            "Failed to parse encoding declaration")
            self.assertTrue(p.the_char is None, "Short parse on EncodingDecl")
        for s in ["encoding = 'latin-1'", " decoding='latin-1'",
                  " encoding=latin-1"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_encoding_decl()
                    self.fail("EncodingDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_enc_name(self):
        """[81] EncName ::= [A-Za-z] ([A-Za-z0-9._] | '-')* """
        with structures.XMLEntity(
                "UTF-8 UTF-16 ISO-10646-UCS-2 ISO-10646-UCS-4 Shift_JIS -8 "
                "_JIS .Private x.Private") as e:
            result = ["UTF-8", "UTF-16", "ISO-10646-UCS-2", "ISO-10646-UCS-4",
                      "Shift_JIS", "JIS", "Private", "x.Private"]
            p = parser.XMLParser(e)
            i = 0
            while p.the_char is not None:
                ename = p.parse_enc_name()
                if ename:
                    self.assertTrue(
                        ename == result[i],
                        "%s parsed, expected %s" % (ename, result[i]))
                    p.parse_s()
                    i = i + 1
                else:
                    p.next_char()

    def test_notation_decl(self):
        """[82] NotationDecl ::=
            '<!NOTATION' S Name S (ExternalID | PublicID) S? '>'"""
        with structures.XMLEntity(
                "<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'>") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.parse_notation_decl()
            n = p.dtd.get_notation('SteveN')
            self.assertTrue(n.name == 'SteveN',
                            "Failed to parse notation name")
            self.assertTrue(n.external_id.public == 'Steve',
                            "Failed to parse notation public ID")
            self.assertTrue(n.external_id.system == '/home/steve.txt',
                            "Failed to parse notation system ID")
            self.assertTrue(p.the_char is None, "Short parse on NotationDecl")
        with structures.XMLEntity(" SteveN PUBLIC 'Steve' >") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.parse_notation_decl(True)
            n = p.dtd.get_notation('SteveN')
            self.assertTrue(n.name == 'SteveN',
                            "Failed to parse notation name")
            self.assertTrue(n.external_id.public == 'Steve',
                            "Failed to parse notation public ID")
            self.assertTrue(n.external_id.system is None,
                            "Failed to parse empty notation system ID")
            self.assertTrue(p.the_char is None, "Short parse on NotationDecl")
        with structures.XMLEntity(
                "<!NOTATION SteveN SYSTEM  '/home/steve.txt' >") as e:
            p = parser.XMLParser(e)
            p.dtd = structures.XMLDTD()
            p.parse_notation_decl()
            n = p.dtd.get_notation('SteveN')
            self.assertTrue(n.name == 'SteveN',
                            "Failed to parse notation name")
            self.assertTrue(n.external_id.public is None,
                            "Failed to parse empty notation public ID")
            self.assertTrue(n.external_id.system == '/home/steve.txt',
                            "Failed to parse notation system ID")
            self.assertTrue(p.the_char is None, "Short parse on NotationDecl")
        for s in ["SteveN PUBLIC 'Steve' >", " 'SteveN' PUBLIC 'Steve' >",
                  "SteveN 'Steve' >", "SteveN PUBLIC >", "SteveN SYSTEM>",
                  "SteveN SYSTEM 'Steve' '/path'>", "SteveN PUBLIC 'Steve' "]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                p.dtd = structures.XMLDTD()
                try:
                    p.parse_notation_decl(True)
                    self.fail("NotationDecl negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass

    def test_public_id(self):
        """[83] PublicID ::= 'PUBLIC' S PubidLiteral"""
        with structures.XMLEntity("PUBLIC 'Steve'") as e:
            p = parser.XMLParser(e)
            self.assertTrue(
                p.parse_public_id() == 'Steve', "Failed to parse Public ID")
            self.assertTrue(p.the_char is None, "Short parse on Public ID")
        for s in [" PUBLIC 'Steve'", "'Steve'", "PUBLIC'Steve'",
                  "Public 'Steve'"]:
            with structures.XMLEntity(s) as e:
                p = parser.XMLParser(e)
                try:
                    p.parse_public_id()
                    self.fail("PublicID negative test: %s" % s)
                except parser.XMLWellFormedError:
                    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
