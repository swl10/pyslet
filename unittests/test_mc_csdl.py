#! /usr/bin/env python

import unittest

def suite():
	loader=unittest.TestLoader()
	loader.testMethodPrefix='test'
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(CSDLTests)
		))

def load_tests(loader, tests, pattern):
	return suite()


from pyslet.mc_csdl import *
import pyslet.xml20081126.structures as xml

class CSDLTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(CSDL_NAMESPACE=="http://schemas.microsoft.com/ado/2009/11/edm","Wrong CSDL namespace: %s"%CSDL_NAMESPACE)

	def testCaseSchema(self):
		s=Schema(None)
		self.failUnless(isinstance(s,xml.Element),"Schema not an XML element")
		self.failUnless(s.ns==CSDL_NAMESPACE,"CSDL namespace")
		self.failUnless(s.namespace=='Default','Namespace default')
		self.failUnless(s.alias==None,'Alias default')
		self.failUnless(len(s.Using)==0,"No Using elements allowed on construction")
		self.failUnless(len(s.Assocation)==0,"No Association elements allowed on construction")
		self.failUnless(len(s.ComplexType)==0,"No ComplexType elements allowed on construction")
		self.failUnless(len(s.EntityType)==0,"No EntityType elements allowed on construction")
		self.failUnless(len(s.EntityContainer)==0,"No EntityContainer elements allowed on construction")
		self.failUnless(len(s.Function)==0,"No Function elements allowed on construction")
		self.failUnless(len(s.Annotations)==0,"No Annotations elements allowed on construction")
		self.failUnless(len(s.ValueTerm)==0,"No ValueTerm elements allowed on construction")
		self.failUnless(len(s.AnnotationElement)==0,"No AnnotationElement elements allowed on construction")

	def testCaseEntityType(self):
		et=EntityType(None)
		self.failUnless(isinstance(et,CSDLElement),"EntityType not a CSDLelement")
		self.failUnless(et.name=="Default","Default name")
		self.failUnless(et.baseType is None,"Default baseType")
		et.SetAttribute((None,'BaseType'),"ParentClass")
		self.failUnless(et.baseType=="ParentClass","BaseType attribute setter")
		self.failUnless(et.abstract is False,"Default abstract")
		et.SetAttribute((None,'Abstract'),"true")
		self.failUnless(et.abstract is True,"Abstract attribute setter")
		self.failUnless(et.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(et.Key is None,"No Key elements allowed on construction")
		self.failUnless(len(et.Property)==0,"No Property elements allowed on construction")
		self.failUnless(len(et.NavigationProperty)==0,"No Property elements allowed on construction")
		self.failUnless(len(et.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(et.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseProperty(self):
		p=Property(None)
		self.failUnless(isinstance(p,CSDLElement),"Property not a CSDLelement")
		self.failUnless(p.name=="Default","Default name")
		
		
		
if __name__ == "__main__":
	unittest.main()
