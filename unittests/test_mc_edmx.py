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
		self.assertTrue(EDMX_NAMESPACE=="http://schemas.microsoft.com/ado/2007/06/edmx","Wrong EDMX namespace: %s"%EDMX_NAMESPACE)

	def testCaseEdmx(self):
		edmx=Edmx(None)
		self.assertTrue(isinstance(edmx,xml.Element),"Edmx not an XML element")
		self.assertTrue(edmx.ns==EDMX_NAMESPACE,"Edmx namespace")
		self.assertTrue(edmx.version=="1.0","Edmx version")
		self.assertTrue(len(edmx.Reference)==0,"No Reference children allowed on construction")
		self.assertTrue(len(edmx.AnnotationsReference)==0,"No AnnotationReference children allowed on construction")
		self.assertTrue(isinstance(edmx.DataServices,DataServices),"No DataServices element")
		self.assertTrue(len(edmx.DataServices.Schema)==0,"No Schema children allowed on construction")
		
if __name__ == "__main__":
	unittest.main()
