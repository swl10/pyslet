#! /usr/bin/env python

import unittest

def suite():
	loader=unittest.TestLoader()
	loader.testMethodPrefix='test'
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(PyDSTests)
		))

def load_tests(loader, tests, pattern):
	return suite()

from pyslet.pyds import *

from pyslet.vfs import OSFilePath as FilePath
TEST_DATA_DIR=FilePath(FilePath(__file__).abspath().split()[0],'data_pyds')


import pyslet.mc_csdl as edm
import pyslet.mc_edmx as edmx


class PyDSTests(unittest.TestCase):

	def setUp(self):
		self.doc=Document()
		mdPath=TEST_DATA_DIR.join('metadata.xml')
		with mdPath.open('rb') as f:
			self.doc.Read(f)
		self.schema=self.doc.root.DataServices['SampleModel']
		self.container=self.doc.root.DataServices["SampleModel.SampleEntities"]
		
	def tearDown(self):
		pass

	def testCaseConstructors(self):
		et=self.schema["Employee"]
		es=EntitySet(None)
		es.entityType=et
		self.failUnless(isinstance(es,edm.EntitySet))
		ec=EntityCollection(es)
		self.failUnless(isinstance(ec,edm.EntityCollection))
		self.failUnless(len(list(ec))==0,"Empty collection")
		
	def testCaseLength(self):
		es=self.schema['SampleEntities.Employees']
		self.failUnless(isinstance(es,edm.EntitySet))
		self.failUnless(len(es)==0,"Length on load")
		es.data[u"ABCDE"]=(u"ABCDE",u"John Smith",None,None)
		self.failUnless(len(es)==1,"Length after insert")
		es.data[u"FGHIJ"]=(u"FGHIJ",u"Jane Smith",None,None)
		self.failUnless(len(es)==2,"Length after 2xinsert")
		del es[u"ABCDE"]
		self.failUnless(len(es)==1,"Length after delete")
	
	def testCaseEntityCollection(self):
		es=self.schema['SampleEntities.Employees']
		es.data[u"ABCDE"]=(u"ABCDE",u"John Smith",None,None)
		es.data[u"FGHIJ"]=(u"FGHIJ",u"Jane Smith",None,None)
		
		


if __name__ == "__main__":
	unittest.main()
