#! /usr/bin/env python

import logging
import os.path
import shutil
import unittest

from io import StringIO
from sys import maxunicode
from tempfile import mkdtemp

from pyslet import rfc2396 as uri
from pyslet.py2 import (
    character,
    dict_keys,
    is_unicode,
    range3,
    ul)
from pyslet.xml import structures


MAX_CHAR = 0x10FFFF
if maxunicode < MAX_CHAR:
    MAX_CHAR = maxunicode


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XML20081126Tests, 'test'),
        unittest.makeSuite(XMLCharacterTests, 'test'),
        unittest.makeSuite(XMLValidationTests, 'test'),
        unittest.makeSuite(XMLEntityTests, 'test'),
        unittest.makeSuite(ElementTests, 'test'),
        unittest.makeSuite(DocumentTests, 'test')
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


class NamedElement(structures.Element):
    XMLNAME = "test"
    XMLCONTENT = structures.ElementType.ElementContent


def decode_yn(value):
    return value == 'Yes'


def encode_yn(value):
    if value:
        return 'Yes'
    else:
        return 'No'


class GenericElementA(structures.Element):
    pass


class GenericSubclassA(GenericElementA):
    pass


class GenericElementB(structures.Element):
    pass


class GenericSubclassB(GenericElementB):
    pass


class ReflectiveElement(structures.Element):
    XMLNAME = "reflection"

    XMLATTR_btest = 'bTest'
    XMLATTR_ctest = ('cTest', decode_yn, encode_yn)
    XMLATTR_dtest = ('dTest', decode_yn, encode_yn, list)
    XMLATTR_dtestR = ('dTestR', decode_yn, encode_yn)  # legacy test
    XMLATTR_etest = ('eTest', decode_yn, encode_yn, dict)
    XMLATTR_etestR = ('eTestR', decode_yn, encode_yn) 	# legacy test
    XMLATTR_ftest = 'fTest'		# missing attribute value

    def __init__(self, parent):
        structures.Element.__init__(self, parent)
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

    def get_children(self):
        for child in structures.Element.get_children(self):
            yield child
        if self.child:
            yield self.child

    def ReflectiveElement(self):    # noqa
        if self.child:
            return self.child
        else:
            e = ReflectiveElement(self)
            self.child = e
            return e

    def GenericElementA(self, childClass=GenericElementA):  # noqa
        child = childClass(self)
        self.generics.append(child)
        return child


class ReflectiveDocument(structures.Document):

    @classmethod
    def get_element_class(cls, name):
        if name in ["reflection", "etest"]:
            return ReflectiveElement
        else:
            return structures.Element


class EmptyElement(structures.Element):
    XMLNAME = "empty"
    XMLCONTENT = structures.XMLEmpty


class ElementContent(structures.Element):
    XMLNAME = "elements"
    XMLCONTENT = structures.ElementType.ElementContent


class MixedElement(structures.Element):
    XMLNAME = "mixed"
    XMLCONTENT = structures.ElementType.Mixed


class IDElement(structures.Element):
    XMLName = "ide"
    XMLCONTENT = structures.XMLEmpty
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

    def test_constants(self):
        pass

    def test_declare(self):
        class_map = {}
        structures.map_class_elements(class_map, Elements)
        self.assertTrue(issubclass(class_map['mixed'], structures.Element),
                        "class type not declared")
        self.assertFalse(
            hasattr(class_map, 'bad'), "class type declared by mistake")


class XMLCharacterTests(unittest.TestCase):
    # Test is_name_char

    def test_space(self):
        """[3] S ::= (#x20 | #x9 | #xD | #xA)+"""
        expected_edges = [0x9, 0xB, 0xD, 0xE, 0x20, 0x21]
        self.assertTrue(self.find_edges(structures.is_s, 256) ==
                        expected_edges, "is_s")

    def test_name_start(self):
        """Productions::

            [4] NameStartChar ::= ":" | [A-Z] | "_" | [a-z] |
                [#xC0-#xD6] | [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] |
                [#x37F-#x1FFF] | [#x200C-#x200D] | [#x2070-#x218F] |
                [#x2C00-#x2FEF] | [#x3001-#xD7FF] | [#xF900-#xFDCF] |
                [#xFDF0-#xFFFD] | [#x10000-#xEFFFF]

            [5] NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 |
                [#x0300-#x036F] | [#x203F-#x2040]"""
        n_namestartchars = 0
        n_namechars = 0
        for code in range3(0x10000):
            c = character(code)
            if structures.is_name_char(c):
                n_namechars += 1
                if structures.is_name_start_char(c):
                    n_namestartchars += 1
            else:
                self.assertFalse(structures.is_name_start_char(c),
                                 "NameStart not a name char: %s" % c)
        self.assertTrue(n_namechars == 54129,
                        "name char total %i" % n_namechars)
        self.assertTrue(n_namestartchars == 54002,
                        "name start char total %i" % n_namestartchars)

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

    def test_name(self):
        self.assertTrue(structures.is_valid_name("Simple"))
        self.assertTrue(structures.is_valid_name(":BadNCName"))
        self.assertTrue(structures.is_valid_name("prefix:BadNCName"))
        self.assertTrue(structures.is_valid_name("_GoodNCName"))
        self.assertFalse(structures.is_valid_name("-BadName"))
        self.assertFalse(structures.is_valid_name(".BadName"))
        self.assertFalse(structures.is_valid_name("0BadName"))
        self.assertTrue(structures.is_valid_name("GoodName-0.12"))
        self.assertFalse(structures.is_valid_name("BadName$"))
        self.assertFalse(structures.is_valid_name("BadName+"))
        self.assertTrue(structures.is_valid_name(ul("Caf\xe9")))


class XMLEntityTests(unittest.TestCase):

    def test_constructor(self):
        e = structures.XMLEntity(b"<hello>")
        self.assertTrue(e.line_num == 1)
        self.assertTrue(e.line_pos == 1)
        self.assertTrue(is_unicode(e.the_char) and e.the_char == '<')
        e = structures.XMLEntity(ul("<hello>"))
        self.assertTrue(is_unicode(e.the_char) and e.the_char == '<')
        e = structures.XMLEntity(StringIO(ul("<hello>")))
        self.assertTrue(e.line_num == 1)
        self.assertTrue(e.line_pos == 1)
        self.assertTrue(is_unicode(e.the_char) and e.the_char == '<')

    def test_chars(self):
        e = structures.XMLEntity(b"<hello>")
        for c in "<hello>":
            self.assertTrue(e.the_char == c)
            e.next_char()
        self.assertTrue(e.the_char is None)
        e.reset()
        self.assertTrue(e.the_char == '<')

    def test_lines(self):
        e = structures.XMLEntity(b"Hello\nWorld\n!")
        while e.the_char is not None:
            e.next_char()
        self.assertTrue(e.line_num == 3)
        self.assertTrue(e.line_pos == 2)

    def test_codecs(self):
        m = ul('Caf\xe9')
        e = structures.XMLEntity(b'Caf\xc3\xa9')
        self.assertTrue(e.bom is False, 'defaulted utf-8 BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing utf-8 got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        e = structures.XMLEntity(b'Caf\xe9', 'latin_1')
        self.assertTrue(e.bom is False, 'latin_1 BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing latin-1 got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        # This string should be automatically detected
        e = structures.XMLEntity(b'\xff\xfeC\x00a\x00f\x00\xe9\x00')
        self.assertTrue(e.bom is True, 'utf-16-le BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing utf-16LE got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        e = structures.XMLEntity(b'\xfe\xff\x00C\x00a\x00f\x00\xe9')
        self.assertTrue(e.bom is True, 'utf-16-be BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing utf-16BE got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        e = structures.XMLEntity(b'\xef\xbb\xbfCaf\xc3\xa9', 'utf-8')
        self.assertTrue(e.bom is False, 'utf-8 BOM detection')
        for c in m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing utf-8 with BOM got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        e = structures.XMLEntity(b'Caf\xe9')
        for c in 'Ca':
            e.next_char()
        e.change_encoding('ISO-8859-1')
        self.assertTrue(e.the_char == 'f', "Bad encoding change")
        e.next_char()
        self.assertTrue(
            e.the_char == character(0xE9),
            "Print: change encoding got %s instead of %s" %
            (repr(e.the_char), repr(character(0xE9))))
        e = structures.XMLEntity(b'C\x00a\x00f\x00\xe9\x00', 'utf-16-le')
        self.assertTrue(e.bom is False, 'utf-16-le no BOM detection error')
        for c in m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing utf-16LE no BOM got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        # add <? to trigger auto-detection
        e = structures.XMLEntity(b'\x00<\x00?\x00C\x00a\x00f\x00\xe9')
        self.assertTrue(e.bom is False, 'utf-16-be no BOM detection error')
        for c in ul("<?") + m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing utf-16BE no BOM got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()
        e = structures.XMLEntity(b'\xfe\xff\xfe\xff\x00C\x00a\x00f\x00\xe9')
        for c in character(0xfeff) + m:
            self.assertTrue(
                e.the_char == c,
                "Print: parsing double BOM got %s instead of %s" %
                (repr(e.the_char), repr(c)))
            e.next_char()


class ElementTests(unittest.TestCase):

    def test_constructor(self):
        e = structures.Element(None)
        self.assertTrue(e.xmlname is None, 'element name on construction')
        self.assertTrue(
            e.get_document() is None, 'document set on construction')
        attrs = e.get_attributes()
        self.assertTrue(len(list(dict_keys(attrs))) == 0,
                        "Attributes present on construction")
        children = e.get_children()
        try:
            next(children)
            self.fail("Children present on construction")
        except StopIteration:
            pass

    def test_default_name(self):
        e = NamedElement(None)
        self.assertTrue(
            e.xmlname == 'test', 'element default name on construction')

    def test_set_xml_name(self):
        e = NamedElement(None)
        e.set_xmlname('test2')
        self.assertTrue(
            e.xmlname == 'test2', 'element named explicitly in construction')

    def test_attributes(self):
        e = structures.Element(None)
        e.set_xmlname('test')
        e.set_attribute('atest', 'value')
        attrs = e.get_attributes()
        self.assertTrue(len(list(dict_keys(attrs))) == 1, "Attribute not set")
        self.assertTrue(
            attrs['atest'] == 'value', "Attribute not set correctly")
        e = ReflectiveElement(None)
        e.set_attribute('atest', 'value')
        # Deprecated: self.assertTrue(e.atest=='value',"Attribute relfection")
        attrs = e.get_attributes()
        self.assertTrue(
            attrs['atest'] == 'value', "Attribute not set correctly")
        e.set_attribute('btest', 'Yes')
        self.assertTrue(
            e.bTest == 'Yes', "Attribute relfection with simple assignment")
        attrs = e.get_attributes()
        self.assertTrue(attrs['btest'] == 'Yes', "Attribute not set correctly")
        e.set_attribute('ctest', 'Yes')
        self.assertTrue(e.cTest is True,
                        "Attribute relfection with decode/encode")
        attrs = e.get_attributes()
        self.assertTrue(attrs['ctest'] == 'Yes', "Attribute not set correctly")
        self.assertFalse('dtest' in attrs, "Optional ordered list attribute")
        self.assertTrue(
            attrs['dtestR'] == '', "Required ordered list attribute")
        e.set_attribute('dtest', 'Yes No')
        self.assertTrue(e.dTest == [True, False],
                        "Attribute relfection with list; %s" % repr(e.dTest))
        attrs = e.get_attributes()
        self.assertTrue(
            attrs['dtest'] == 'Yes No', "Attribute not set correctly")
        self.assertFalse('etest' in attrs, "Optional unordered list attribute")
        self.assertTrue(
            attrs['etestR'] == '', "Required unordered list attribute")
        e.set_attribute('etest', 'Yes No Yes')
        self.assertTrue(e.eTest == {True: 2, False: 1},
                        "Attribute relfection with list: %s" % repr(e.eTest))
        attrs = e.get_attributes()
        self.assertTrue(attrs['etest'] == 'No Yes Yes',
                        "Attribute not set correctly: %s" %
                        repr(attrs['etest']))
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
                e.fTest is None,
                "Missing attribute auto value not None (after del)")
        except AttributeError:
            self.fail(
                "Missing attribute auto value: AttributeError (after del)")

    def test_child_elements(self):
        """Test child element behaviour"""
        e = structures.Element(None)
        e.set_xmlname('test')
        e.add_child(structures.Element, 'test1')
        children = list(e.get_children())
        self.assertTrue(
            len(children) == 1, "add_child failed to add child element")

    def test_child_element_reflection(self):
        """Test child element cases using reflection"""
        e = ReflectiveElement(None)
        child1 = e.add_child(ReflectiveElement, 'test1')
        self.assertTrue(e.child is child1, "Element not set by reflection")
        children = list(e.get_children())
        self.assertTrue(len(children) == 1 and children[0] is child1,
                        "add_child failed to add child element")
        # Now create a second child, should return the same one due to model
        # restriction
        child2 = e.add_child(ReflectiveElement, 'test1')
        self.assertTrue(
            e.child is child1 and child2 is child1, "Element model violated")
        child3 = e.add_child(GenericElementA, 'test3')
        self.assertTrue(e.generics[0] is child3, "Generic element")
        child4 = e.add_child(GenericSubclassA, 'test4')
        self.assertTrue(
            e.generics[1] is child4, "Generic sub-class element via method")
        child5 = e.add_child(GenericSubclassB, 'test5')
        self.assertTrue(e.GenericElementB is child5,
                        "Generic sub-class element via member")

    def test_data(self):
        e = structures.Element(None)
        self.assertTrue(e.is_mixed(), "Mixed default")
        e.add_data('Hello')
        self.assertTrue(e.get_value() == 'Hello', "Data value")
        children = list(e.get_children())
        self.assertTrue(len(children) == 1, "Data child not set")
        self.assertTrue(children[0] == "Hello", "Data child not set correctly")

    def test_empty(self):
        e = EmptyElement(None)
        self.assertFalse(e.is_mixed(), "EmptyElement is mixed")
        self.assertTrue(e.is_empty(), "EmptyElement not empty")
        try:
            e.add_data('Hello')
            self.fail("Data in EmptyElement")
        except structures.XMLValidityError:
            pass
        try:
            e.add_child(structures.Element)
            self.fail("Elements allowed in EmptyElement")
        except structures.XMLValidityError:
            pass

    def test_element_content(self):
        e = ElementContent(None)
        self.assertFalse(e.is_mixed(), "ElementContent appears mixed")
        self.assertFalse(e.is_empty(), "ElementContent appears empty")
        try:
            e.add_data('Hello')
            self.fail("Data in ElementContent")
        except structures.XMLValidityError:
            pass
        # white space should silently be ignored.
        e.add_data('  \n\r  \t')
        children = list(e.get_children())
        self.assertTrue(len(children) == 0, "Unexpected children")
        # elements can be added
        e.add_child(structures.Element)
        children = list(e.get_children())
        self.assertTrue(len(children) == 1, "Expected one child")

    def test_mixed_content(self):
        e = MixedElement(None)
        self.assertTrue(e.is_mixed(), "MixedElement not mixed")
        self.assertFalse(e.is_empty(), "MixedElement appears empty")
        e.add_data('Hello')
        self.assertTrue(
            e.get_value() == 'Hello', 'Mixed content with a single value')
        e.add_child(structures.Element)
        try:
            e.get_value()
        except structures.XMLMixedContentError:
            pass

    def test_copy(self):
        e1 = structures.Element(None)
        e2 = e1.deepcopy()
        self.assertTrue(isinstance(e2, structures.Element),
                        "deepcopy didn't make Element")
        self.assertTrue(e1 == e2)
        self.assertTrue(e1 is not e2)


class DocumentTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()
        self.d = mkdtemp('.d', 'pyslet-test_xml20081126-')
        os.chdir(self.d)

    def tearDown(self):     # noqa
        os.chdir(self.cwd)
        shutil.rmtree(self.d, True)

    def test_constructor(self):
        d = structures.Document()
        self.assertTrue(d.root is None, 'root on construction')
        self.assertTrue(d.get_base() is None, 'base set on construction')
        d = structures.Document(root=structures.Element)
        self.assertTrue(isinstance(d.root, structures.Element),
                        'root not created on construction')
        self.assertTrue(
            d.root.get_document() is d, 'root not linked to document')

    def test_base(self):
        """Test the use of a file path on construction"""
        fpath = os.path.abspath('fpath.xml')
        furl = str(uri.URI.from_path(fpath))
        d = structures.Document(base_uri=furl)
        self.assertTrue(d.get_base() == furl, "Base not set in constructor")
        self.assertTrue(d.root is None, 'root on construction')
        d = structures.Document(base_uri='fpath.xml', root=structures.Element)
        self.assertTrue(
            d.get_base() == furl,
            "Base not made absolute from relative URL:\n\t%s\n\t%s" %
            (furl, d.get_base()))
        self.assertTrue(isinstance(d.root, structures.Element),
                        'root not created on construction')
        d = structures.Document()
        d.set_base(furl)
        self.assertTrue(d.get_base() == furl, "Base not set by set_base")

    def test_read_file(self):
        """Test the reading of the Document from the file system"""
        os.chdir(TEST_DATA_DIR)
        d = structures.Document(base_uri='readFile.xml')
        d.read()
        root = d.root
        self.assertTrue(isinstance(root, structures.Element))
        self.assertTrue(
            root.xmlname == 'tag' and root.get_value() == 'Hello World')

    def test_read_string(self):
        """Test the reading of the Document from a supplied stream"""
        os.chdir(TEST_DATA_DIR)
        d = structures.Document(base_uri='readFile.xml')
        f = open('readFile.xml', 'rb')
        d.read(src=f)
        f.close()
        root = d.root
        self.assertTrue(isinstance(root, structures.Element))
        self.assertTrue(
            root.xmlname == 'tag' and root.get_value() == 'Hello World')

    def test_string(self):
        os.chdir(TEST_DATA_DIR)
        d = structures.Document(base_uri='readFile.xml')
        d.read()
        f = open('readFile.xml', 'rb')
        flines = f.read().splitlines()
        f.close()
        # bytes always formats using unix-style newlines
        dlines = bytes(d).split(b'\n')
        self.assertTrue(dlines == flines, "XML output: %s" % bytes(d))
        d = structures.Document(base_uri='ascii.bin')
        d.read()
        f = open('ascii.bin', 'rb')
        fdata = f.read()
        f.close()
        self.assertTrue(bytes(d) == fdata, "XML output: %s" % bytes(d))

    def test_resolve_base(self):
        """Test the use of resolve_uri and resolve_base"""
        os.chdir(TEST_DATA_DIR)
        parent = structures.Element(None)
        self.assertTrue(parent.resolve_base() is None, "No default base")
        child = structures.Element(parent)
        self.assertTrue(child.resolve_base() is None, "No xml:base by default")
        parent.set_base('file:///index.xml')
        self.assertTrue(child.resolve_base() == 'file:///index.xml',
                        "No xml:base inheritance")
        # Tests with a document follow....
        furl = str(uri.URI.from_path(os.path.abspath('base.xml')))
        href = uri.URI.from_path(os.path.abspath('link.xml'))
        href_path = href.abs_path
        href = str(href)
        alt_ref = 'file:///hello/link.xml'
        d = structures.Document(base_uri='base.xml')
        self.assertTrue(d.get_base() == furl,
                        "Base not resolved relative to w.d. by constructor")
        d.read()
        tag = d.root
        self.assertTrue(
            tag.resolve_base() == furl, "Root element resolves from document")
        self.assertTrue(
            str(tag.resolve_uri("link.xml")) == href, "Root element HREF")
        self.assertTrue(
            str(tag.relative_uri(href)) == 'link.xml', "Root element relative")
        # self.assertTrue(
        #   tag.relative_uri(alt_ref)=='/hello/link.xml',
        #   'Root element full path relative: %s'%tag.relative_uri(alt_ref))
        child_tag = tag._children[0]
        self.assertTrue(child_tag.resolve_base() == "file:///hello/base.xml",
                        "xml:base overrides in child_tag (%s)" %
                        child_tag.resolve_base())
        self.assertTrue(str(child_tag.resolve_uri("link.xml")) == alt_ref,
                        "child element HREF")
        self.assertTrue(str(child_tag.relative_uri(href)) == '..' + href_path,
                        "child element relative resulting in full path: %s" %
                        child_tag.relative_uri(href))
        self.assertTrue(str(child_tag.relative_uri(alt_ref)) == 'link.xml',
                        'child element relative')
        # We require this next test to ensure that an href to the
        # current document comes up blank.  Although this was a major
        # source of bugs in browsers (<img src=''> causing infinite
        # loading loops) these are largely fixed now and obfuscating by
        # using a non-empty relative link to ourselves is likely to
        # start the whole thing going again.
        self.assertTrue(
            str(child_tag.relative_uri(child_tag.resolve_base())) == '',
            'child element relative avoiding empty URI(%s)' %
            child_tag.relative_uri(child_tag.resolve_base()))
        grandchild_tag = child_tag._children[0]
        self.assertTrue(grandchild_tag.resolve_base() ==
                        "file:///hello/base.xml", "xml:base inherited")
        self.assertTrue(str(grandchild_tag.resolve_uri("link.xml")) == alt_ref,
                        "grandchild element HREF inherited")
        self.assertTrue(
            str(grandchild_tag.relative_uri(href)) == '..' + href_path,
            "grandchild element relative inherited: %s" %
            grandchild_tag.relative_uri(href))
        self.assertTrue(
            str(grandchild_tag.relative_uri(alt_ref)) == 'link.xml',
            'grandchild element relative inherited')

    def test_resolve_lang(self):
        """Test the use of resolve_lang"""
        parent = structures.Element(None)
        self.assertTrue(parent.resolve_lang() is None, "No default language")
        parent.set_lang('en-GB')
        self.assertTrue(parent.get_lang() == 'en-GB', "Lang Get/Set")
        child = structures.Element(parent)
        self.assertTrue(child.get_lang() is None, "No xml:lang by default")
        self.assertTrue(child.resolve_lang() == 'en-GB', "Lang inheritence")
        # repeat tests with a parent document
        d = structures.Document()
        parent = structures.Element(d)
        self.assertTrue(parent.resolve_lang() is None, "No default language")

    def test_create(self):
        """Test the creating of the Document on the file system"""
        create_1_xml = """<?xml version="1.0" encoding="UTF-8"?>
<test/>"""
        d = structures.Document(root=NamedElement)
        d.set_base('create1.xml')
        d.create()
        try:
            f = open("create1.xml")
            data = f.read()
            f.close()
            self.assertTrue(data == create_1_xml, "create Test")
        except IOError:
            self.fail("create Test failed to create file")

    def test_update(self):
        """Test the updating of the MXLDocument on the file system"""
        update_1_xml = """<?xml version="1.0" encoding="UTF-8"?>
<test>
\t<test/>
</test>"""
        d = structures.Document(root=NamedElement)
        d.set_base('update1.xml')
        try:
            d.update()
            self.fail("update Document failed to spot missing file")
        except structures.XMLMissingResourceError:
            pass
        d.create()
        d.root.add_child(NamedElement)
        d.update()
        try:
            f = open("update1.xml")
            data = f.read()
            f.close()
            self.assertTrue(data == update_1_xml, "update Test")
        except IOError:
            self.fail("update Test failed to update file")

    def test_id(self):
        """Test the built-in handling of a document's ID space."""
        doc = structures.Document()
        e1 = structures.Element(doc)
        e2 = structures.Element(doc)
        e1.id = e2.id = 'test'
        doc.register_element(e1)
        try:
            doc.register_element(e2)
            self.fail("Failed to spot ID clash")
        except structures.XMLIDClashError:
            pass
        e2.id = 'test2'
        doc.register_element(e2)
        self.assertTrue(
            doc.get_element_by_id('test') is e1, "Element look-up failed")
        new_id = doc.get_unique_id('test')
        self.assertFalse(new_id == 'test' or new_id == 'test2')

    def test_reflection(self):
        """Test the built-in handling of reflective attributes and elements."""
        reflective_xml = ul("""<?xml version="1.0" encoding="UTF-8"?>
<reflection btest="Hello"><etest>Hello Again</etest></reflection>""")
        f = StringIO(reflective_xml)
        d = ReflectiveDocument()
        d.read(src=f)
        root = d.root
        self.assertTrue(isinstance(root, ReflectiveElement))
        self.assertTrue(root.bTest, "Attribute relfection")
        self.assertTrue(root.child, "Element relfection")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
