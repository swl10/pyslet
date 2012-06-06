#! /usr/bin/env python

import unittest

def suite():
	loader=unittest.TestLoader()
	loader.testMethodPrefix='test'
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(EDMXTests)
		))

def load_tests(loader, tests, pattern):
	return suite()


from pyslet.mc_edmx import *
import pyslet.xml20081126.structures as xml

class EDMXTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(EDMX_NAMESPACE=="http://schemas.microsoft.com/ado/2007/06/edmx","Wrong EDMX namespace: %s"%EDMX_NAMESPACE)

	def testCaseEdmx(self):
		edmx=Edmx(None)
		self.failUnless(isinstance(edmx,xml.Element),"Edmx not an XML element")
		self.failUnless(edmx.ns==EDMX_NAMESPACE,"Edmx namespace")
		self.failUnless(edmx.version=="1.0","Edmx version")
		self.failUnless(len(edmx.Reference)==0,"No Reference children allowed on construction")
		self.failUnless(len(edmx.AnnotationsReference)==0,"No AnnotationReference children allowed on construction")
		self.failUnless(isinstance(edmx.DataServices,DataServices),"No DataServices element")
		self.failUnless(len(edmx.DataServices.Schema)==0,"No Schema children allowed on construction")
		
if __name__ == "__main__":
	unittest.main()
