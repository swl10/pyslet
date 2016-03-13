#! /usr/bin/env python

import io
import unittest

from pyslet.xml.structures import ElementType
import pyslet.xml.namespace as xmlns


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XMLNames20091208Tests, 'test'),
        unittest.makeSuite(XMLNSValidationTests, 'test'),
        unittest.makeSuite(XMLNSElementTests, 'test'),
        unittest.makeSuite(XMLNSDocumentTests, 'test')
    ))

EXAMPLE_1 = b"""<?xml version="1.0" encoding="UTF-8"?>
<tag>Hello World</tag>"""


class XMLNames20091208Tests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(
            xmlns.XML_NAMESPACE == "http://www.w3.org/XML/1998/namespace",
            "Wrong XML namespace: %s" % xmlns.XML_NAMESPACE)


class XMLNSValidationTests(unittest.TestCase):

    def test_name(self):
        """These are the same tests as is_valid_name for xml, but two of
        the results we expect to be different!"""
        self.assertTrue(xmlns.is_valid_ncname("Simple"))
        self.assertFalse(xmlns.is_valid_ncname(":BadNCName"))
        self.assertFalse(xmlns.is_valid_ncname("prefix:BadNCName"))
        self.assertTrue(xmlns.is_valid_ncname("_GoodNCName"))
        self.assertFalse(xmlns.is_valid_ncname("-BadName"))
        self.assertFalse(xmlns.is_valid_ncname(".BadName"))
        self.assertFalse(xmlns.is_valid_ncname("0BadName"))
        self.assertTrue(xmlns.is_valid_ncname("GoodName-0.12"))
        self.assertFalse(xmlns.is_valid_ncname("BadName$"))
        self.assertFalse(xmlns.is_valid_ncname("BadName+"))


class XMLNSElementTests(unittest.TestCase):

    def test_constructor(self):
        e = xmlns.NSElement(None)
        self.assertTrue(e.ns is None, 'ns set on construction')
        self.assertTrue(e.xmlname is None,
                        'element name not set on construction')


class XMLExampleElement(xmlns.NSElement):
    XMLCONTENT = ElementType.ElementContent


class XMLExampleDocument(xmlns.NSDocument):
    default_ns = "http://www.example.com"

    @classmethod
    def get_element_class(cls, name):
        if name[1] in ("createTag"):
            return XMLExampleElement
        else:
            return xmlns.NSDocument.get_element_class(name)


class XMLNSDocumentTests(unittest.TestCase):

    def test_read_string(self):
        """Test the reading of the NSDocument from a supplied stream"""
        d = xmlns.NSDocument()
        d.read(src=io.BytesIO(EXAMPLE_1))
        root = d.root
        self.assertTrue(isinstance(root, xmlns.NSElement))
        self.assertTrue(root.ns is None and root.xmlname == 'tag' and
                        root.get_value() == 'Hello World')

    def test_create_ns(self):
        """Test the handling of namespaces in output"""
        create_2_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<createTag xmlns:alt="http://www.example.com/alt">
    <alt:createTag xml:base="http://www.example.com/create.xml">
        <tag2>Hello World</tag2>
    </alt:createTag>
</createTag>"""
        create_2_output = b'<?xml version="1.0" encoding="UTF-8"?>\n'\
            b'<createTag xmlns="http://www.example.com">\n'\
            b'\t<createTag xmlns="http://www.example.com/alt" '\
            b'xml:base="http://www.example.com/create.xml">\n'\
            b'\t\t<tag2 xmlns="http://www.example.com">Hello World</tag2>\n'\
            b'\t</createTag>\n'\
            b'</createTag>'
        d = XMLExampleDocument()
        d.read(src=io.BytesIO(create_2_xml))
        dst = io.BytesIO()
        d.reset_prefix_map(True)
        d.create(dst=dst)
        self.assertTrue(
            dst.getvalue() == create_2_output,
            "Simple NS output: \n%s>>>Expected: \n%s" %
            (dst.getvalue(), create_2_output))

    def test_attr_ns_declared(self):
        """Test that attributes can be used to trigger NS declarations"""
        attr_xml = b'<?xml version="1.0" encoding="UTF-8"?>\n'\
            b'<createTag xmlns="http://www.example.com" '\
            b'xmlns:ns1="http://www.example.com/attributes" '\
            b'ns1:test="Hello"/>'
        attr_xml_alt = b'<?xml version="1.0" encoding="UTF-8"?>\n'\
            b'<createTag xmlns="http://www.example.com" '\
            b'xmlns:test="http://www.example.com/attributes" '\
            b'test:test="Hello"/>'
        d = xmlns.NSDocument()
        d.read(src=io.BytesIO(attr_xml))
        dst = io.BytesIO()
        d.create(dst=dst)
        self.assertTrue(
            dst.getvalue() == attr_xml,
            "Simple NS attribute: \nWanted:\n%s\n\nGot:\n%s" %
            (repr(attr_xml), repr(dst.getvalue())))
        d.reset_prefix_map(True)
        d.make_prefix("http://www.example.com/attributes", 'test')
        dst = io.BytesIO()
        d.create(dst=dst)
        self.assertTrue(
            dst.getvalue() == attr_xml_alt,
            "Simple NS attribute, preferred prefix: "
            "\nWanted:\n%s\n\nGot:\n%s" %
            (repr(attr_xml_alt), repr(dst.getvalue())))

if __name__ == "__main__":
    unittest.main()
