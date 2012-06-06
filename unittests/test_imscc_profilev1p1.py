#! /usr/bin/env python

import unittest

from tempfile import mkdtemp
import os, os.path, shutil

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CCMiscTests,'test'),
		unittest.makeSuite(CommonCartridgeTests,'test')		
		))

from pyslet.imscc_profilev1p1 import *
import pyslet.imscpv1p2 as imscp


class CCMiscTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSCC_CP_NAMESPACE=="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1","Wrong CP namespace: %s"%IMSCC_CP_NAMESPACE)
		self.failUnless(IMSCC_LOMMANIFEST_NAMESPACE=="http://ltsc.ieee.org/xsd/imsccv1p2/LOM/manifest","Wrong LOM Manifest namespace: %s"%IMSCC_LOMMANIFEST_NAMESPACE)
		self.failUnless(IMSCC_LOMRESOURCE_NAMESPACE=="http://ltsc.ieee.org/xsd/imsccv1p2/LOM/resource","Wrong LOM Resource namespace: %s"%IMSCC_LOMRESOURCE_NAMESPACE)

class CommonCartridgeTests(unittest.TestCase):
	def setUp(self):
		# make dataPath before we change directory (___file__ may be relative)
		self.dataPath=os.path.join(os.path.split(os.path.abspath(__file__))[0],'data_imscc_profilev1p1')
		self.cwd=os.getcwd()
		self.cpList=[]
		self.tmpPath=mkdtemp('.d','pyslet-test_imsccv1p1-')
		os.chdir(self.tmpPath)
		
	def tearDown(self):
		for cp in self.cpList:
			cp.Close()
		shutil.rmtree(self.tmpPath,True)
		os.chdir(self.cwd)
		
	def testCaseConstructor(self):
		cc=CommonCartridge()
		self.failUnless(isinstance(cc.cp,imscp.ContentPackage))
		self.failUnless(isinstance(cc.cp,ContentPackage))
		self.cpList.append(cc.cp)
		self.failUnless(len(cc.laoTable.keys())==0)
		cc=CommonCartridge(os.path.join(self.dataPath,'sample_1'))
		# import pdb;pdb.set_trace()
		# self.failUnless(len(cc.laoTable.keys())==3)
		
if __name__ == "__main__":
	#unittest.main()
	# we need can't use main because we don't want to pick up the the conformance tests
	# as they are designed to be run from within one of the other tests.
	unittest.TextTestRunner().run(suite())

