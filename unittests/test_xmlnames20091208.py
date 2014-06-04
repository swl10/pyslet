#! /usr/bin/env python

import unittest


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(XMLNames20091208Tests, 'test'),
        unittest.makeSuite(XMLNSValidationTests, 'test'),
        unittest.makeSuite(XMLNSElementTests, 'test'),
        unittest.makeSuite(XMLNSDocumentTests, 'test')
    ))

from pyslet.xmlnames20091208 import *

EXAMPLE_1 = """<?xml version="1.0" encoding="UTF-8"?>
<tag>Hello World</tag>"""


class XMLNames20091208Tests(unittest.TestCase):

    def testCaseConstants(self):
        self.assertTrue(XML_NAMESPACE == "http://www.w3.org/XML/1998/namespace",
                        "Wrong XML namespace: %s" % XML_NAMESPACE)


class XMLNSValidationTests(unittest.TestCase):

    def testCaseName(self):
        """These are the same tests as IsValidName for xml, but two of the results we
        expect to be different!"""
        self.assertTrue(IsValidNCName("Simple"))
        self.assertFalse(IsValidNCName(":BadNCName"))
        self.assertFalse(IsValidNCName("prefix:BadNCName"))
        self.assertTrue(IsValidNCName("_GoodNCName"))
        self.assertFalse(IsValidNCName("-BadName"))
        self.assertFalse(IsValidNCName(".BadName"))
        self.assertFalse(IsValidNCName("0BadName"))
        self.assertTrue(IsValidNCName("GoodName-0.12"))
        self.assertFalse(IsValidNCName("BadName$"))
        self.assertFalse(IsValidNCName("BadName+"))


class XMLNSElementTests(unittest.TestCase):

    def testCaseConstructor(self):
        e = XMLNSElement(None, 'test')
        self.assertTrue(e.ns == None, 'ns set on construction')
        self.assertTrue(
            e.xmlname == 'test', 'element name not set on construction')


class XMLExampleElement(XMLNSElement):
    XMLCONTENT = ElementType.ElementContent


class XMLExampleDocument(XMLNSDocument):
    DefaultNS = "http://www.example.com"

    @classmethod
    def GetElementClass(cls, name):
        if name[1] in ("createTag"):
            return XMLExampleElement
        else:
            return XMLNSDocument.GetElementClass(name)


class XMLNSDocumentTests(unittest.TestCase):

    def testCaseReadString(self):
        """Test the reading of the XMLNSDocument from a supplied stream"""
        d = XMLNSDocument()
        d.Read(src=StringIO(EXAMPLE_1))
        root = d.root
        self.assertTrue(isinstance(root, XMLNSElement))
        self.assertTrue(
            root.ns == None and root.xmlname == 'tag' and root.GetValue() == 'Hello World')

    def testCaseCreateNS(self):
        """Test the handling of namespaces in output"""
        CREATE_2_XML = """<?xml version="1.0" encoding="UTF-8"?>
<createTag xmlns:alt="http://www.example.com/alt">
	<alt:createTag xml:base="http://www.example.com/create.xml">
		<tag2>Hello World</tag2>
	</alt:createTag>
</createTag>"""
        CREATE_2_OUTPUT = """<?xml version="1.0" encoding="UTF-8"?>
<createTag xmlns="http://www.example.com">
	<createTag xmlns="http://www.example.com/alt" xml:base="http://www.example.com/create.xml">
		<tag2 xmlns="http://www.example.com">Hello World</tag2>
	</createTag>
</createTag>"""
        d = XMLExampleDocument()
        d.Read(src=StringIO(CREATE_2_XML))
        dst = StringIO()
        d.ResetPrefixMap(True)
        d.Create(dst=dst)
        # print
        # print repr(dst.getvalue())
        # print
        # print repr(CREATE_2_OUTPUT)
        self.assertTrue(dst.getvalue() == CREATE_2_OUTPUT, "Simple NS output: \n%s>>>Expected: \n%s" % (
            dst.getvalue(), CREATE_2_OUTPUT))

    def testAttrNSDeclared(self):
        """Test that attributes can be used to trigger NS declarations"""
        ATTR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<createTag xmlns="http://www.example.com" xmlns:ns1="http://www.example.com/attributes" ns1:test="Hello"/>"""
        ATTR_XML_ALT = """<?xml version="1.0" encoding="UTF-8"?>
<createTag xmlns="http://www.example.com" xmlns:test="http://www.example.com/attributes" test:test="Hello"/>"""
        d = XMLNSDocument()
        d.Read(src=StringIO(ATTR_XML))
        dst = StringIO()
        d.Create(dst=dst)
        self.assertTrue(dst.getvalue() == ATTR_XML, "Simple NS attribute: \nWanted:\n%s\n\nGot:\n%s" % (
            repr(ATTR_XML), repr(dst.getvalue())))
        d.ResetPrefixMap(True)
        d.MakePrefix("http://www.example.com/attributes", 'test')
        dst = StringIO()
        d.Create(dst=dst)
        self.assertTrue(dst.getvalue() == ATTR_XML_ALT, "Simple NS attribute, preferred prefix: \nWanted:\n%s\n\nGot:\n%s" % (
            repr(ATTR_XML_ALT), repr(dst.getvalue())))

if __name__ == "__main__":
    unittest.main()
