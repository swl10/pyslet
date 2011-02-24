#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(XMLNames20091208Tests,'test'),
		unittest.makeSuite(XMLNSValidationTests,'test'),
		unittest.makeSuite(XMLNSElementTests,'test'),
		unittest.makeSuite(XMLNSDocumentTests,'test')
		))

from pyslet.xmlnames20091208 import *

EXAMPLE_1="""<?xml version="1.0" encoding="utf-8"?>
<tag>Hello World</tag>"""


class XMLNames20091208Tests(unittest.TestCase):		
	def testCaseConstants(self):
		self.failUnless(XML_NAMESPACE=="http://www.w3.org/XML/1998/namespace","Wrong XML namespace: %s"%XML_NAMESPACE)

class XMLNSValidationTests(unittest.TestCase):
	def testCaseName(self):
		"""These are the same tests as IsValidName for xml, but two of the results we
		expect to be different!"""
		self.failUnless(IsValidNCName("Simple"))
		self.failIf(IsValidNCName(":BadNCName"))
		self.failIf(IsValidNCName("prefix:BadNCName"))
		self.failUnless(IsValidNCName("_GoodNCName"))
		self.failIf(IsValidNCName("-BadName"))
		self.failIf(IsValidNCName(".BadName"))
		self.failIf(IsValidNCName("0BadName"))
		self.failUnless(IsValidNCName("GoodName-0.12"))
		self.failIf(IsValidNCName("BadName$"))
		self.failIf(IsValidNCName("BadName+"))
		

class XMLNSElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=XMLNSElement(None)
		self.failUnless(e.ns==None,'ns set on construction')
		self.failUnless(e.xmlname==None,'element name set on construction')

class XMLNSDocumentTests(unittest.TestCase):
	def testCaseReadString(self):
		"""Test the reading of the XMLNSDocument from a supplied stream"""
		d=XMLNSDocument()
		d.Read(src=StringIO(EXAMPLE_1))
		root=d.root
		self.failUnless(isinstance(root,XMLNSElement))
		self.failUnless(root.ns==None and root.xmlname=='tag' and root.GetValue()=='Hello World')

	def testCaseCreateNS(self):
		"""Test the handling of namespaces in output"""
		CREATE_2_XML="""<?xml version="1.0" encoding="utf-8"?>
<createTag xmlns:alt="http://www.example.com/alt">
	<alt:createTag xml:base="http://www.example.com/create.xml">
		<tag2>Hello World</tag2>
	</alt:createTag>
</createTag>"""
		CREATE_2_OUTPUT="""<?xml version="1.0" encoding="utf-8"?>
<createTag xmlns="http://www.example.com">
	<createTag xmlns="http://www.example.com/alt" xml:base="http://www.example.com/create.xml">
		<tag2 xmlns="http://www.example.com">Hello World</tag2>
	</createTag>
</createTag>"""		
		d=XMLNSDocument()
		d.SetDefaultNS("http://www.example.com")
		d.Read(src=StringIO(CREATE_2_XML))
		dst=StringIO()
		d.Create(dst=dst)
		#print
		#print repr(dst.getvalue())
		#print
		#print repr(CREATE_2_OUTPUT)
		self.failUnless(dst.getvalue()==CREATE_2_OUTPUT,"Simple NS output: \n%s"%dst.getvalue())

	def testAttrNSDeclared(self):
		"""Test that attributes can be used to trigger NS declarations"""
		ATTR_XML="""<?xml version="1.0" encoding="utf-8"?>
<createTag xmlns="http://www.example.com" xmlns:ns1="http://www.example.com/attributes" ns1:test="Hello"/>"""		
		ATTR_XML_ALT="""<?xml version="1.0" encoding="utf-8"?>
<createTag xmlns="http://www.example.com" xmlns:test="http://www.example.com/attributes" test:test="Hello"/>"""		
		d=XMLNSDocument()
		d.Read(src=StringIO(ATTR_XML))
		dst=StringIO()
		d.Create(dst=dst)
		self.failUnless(dst.getvalue()==ATTR_XML,"Simple NS attribyte: \nWanted: %s\n\nGot: %s"%(ATTR_XML,dst.getvalue()))
		d.SetNSPrefix("http://www.example.com/attributes",'test')
		dst=StringIO()
		d.Create(dst=dst)
		self.failUnless(dst.getvalue()==ATTR_XML_ALT,"Simple NS attribyte, preferred prefix: \nWanted: %s\n\nGot: %s"%(ATTR_XML,dst.getvalue()))
		
if __name__ == "__main__":
	unittest.main()
