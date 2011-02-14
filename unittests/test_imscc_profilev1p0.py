#! /usr/bin/env python

import unittest

from tempfile import mkdtemp
import os, os.path, shutil

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CCMiscTests,'test'),
		unittest.makeSuite(CommonCartridgeTests,'test'),
		unittest.makeSuite(CCConformanceTests,'test')
		))

from pyslet.imscc_profilev1p0 import *
import pyslet.imscpv1p2 as imscp


class CCMiscTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(CCOrganizationStructure=="rooted-hierarchy")
		self.failUnless(CartridgeWebContentType=="webcontent")
		self.failUnless(AssociatedContentType=="associatedcontent/imscc_xmlv1p0/learning-application-resource")
		self.failUnless(DiscussionTopicContentType=="imsdt_xmlv1p0")
		self.failUnless(WebLinkContentType=="imswl_xmlv1p0")
		self.failUnless(AssessmentContentType=="imsqti_xmlv1p2/imscc_xmlv1p0/assessment")
		self.failUnless(QuestionBankContentType=="imsqti_xmlv1p2/imscc_xmlv1p0/question-bank")

class CommonCartridgeTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.cpList=[]
		self.tmpPath=mkdtemp('.d','pyslet-test_imscpv1p2-')
		os.chdir(self.tmpPath)
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_imscc_profilev1p0')
		
	def tearDown(self):
		for cp in self.cpList:
			cp.Close()
		shutil.rmtree(self.tmpPath,True)
		os.chdir(self.cwd)
		
	def testCaseConstructor(self):
		cc=CommonCartridge()
		self.failUnless(isinstance(cc.cp,imscp.ContentPackage))
		self.cpList.append(cc.cp)
		self.failUnless(len(cc.laoTable.keys())==0)
		cc=CommonCartridge(os.path.join(self.dataPath,'Sample1'))
		self.failUnless(len(cc.laoTable.keys())==3)
		cp=imscp.ContentPackage(os.path.join(self.dataPath,'Sample1'))
		self.cpList.append(cp)
		cc=CommonCartridge(cp)
		self.failUnless(len(cc.laoTable.keys())==3)
		dList=map(lambda x:cc.laoTable[x][0],cc.laoTable.keys())
		dList.sort()
		self.failUnless(dList==['L0001','L0002','L0003'])
		#r6=cp.manifest.GetElementByID('R0006')
		head,acr=cc.laoTable['R0006']
		self.failUnless(acr is cp.manifest.GetElementByID('R0007'))
		self.failUnless(len(acr.fileList)==3)
		
# Running tests on the cartridges on hold...		
class CCConformanceTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.tmpPath=mkdtemp('.d','pyslet-test_imscpv1p2-')
		os.chdir(self.tmpPath)
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_imscc_profilev1p0')
		cp=imscp.ContentPackage(os.path.join(self.dataPath,'Sample1'))
		cp.ExportToPIF('Sample1.zip')
		self.cc=CommonCartridge('Sample1.zip')
		
	def tearDown(self):
		self.cc.Close()
		shutil.rmtree(self.tmpPath,True)
		os.chdir(self.cwd)

	def testCasePass(self):
		self.RunTests([])

	def testCase1p4AssociatedContent_1(self):
		fPath=os.path.join(self.cc.cp.dPath,'L0001','Attachments','Extra.txt')
		f=open(fPath,'wb')
		f.write('Hello World!')
		f.close()
		self.cc.cp.RebuildFileTable()
		self.RunTests(['test1_4_AssociatedContent_1'])
	
	def testCase1p4AssociatedContent_2(self):
		fPath=os.path.join(self.cc.cp.dPath,'Extra.txt')
		f=open(fPath,'wb')
		f.write('Hello World!')
		f.close()
		r1=self.cc.cp.manifest.GetElementByID('R0004')
		f=r1.CPFile('Extra.txt')
		self.cc.cp.RebuildFileTable()
		self.RunTests(['test1_4_AssociatedContent_2'])
	
	def testCase1p4AssociatedContent_3(self):
		r1=self.cc.cp.manifest.GetElementByID('R0004')
		dep=r1.CPDependency('R0001')
		self.RunTests(['test1_4_AssociatedContent_3'])
	
	def testCase1p4LAO_1(self):
		r3=self.cc.cp.manifest.GetElementByID('R0003')
		f=r3.fileList[0]
		self.cc.cp.DeleteFile('L0001/Welcome.forum')
		self.RunTests(['test1_4_LAO_1'])
		
	def testCase1p4LAO_2(self):
		r3=self.cc.cp.manifest.GetElementByID('R0003')
		# Tricky, to prevent other tests failing we add a reference to a file already referenced
		# by the associated content for the resource.
		f=r3.CPFile('L0001/Welcome.gif')
		self.RunTests(['test1_4_LAO_2'])

	def testCase1p4LAO_3(self):
		r3=self.cc.cp.manifest.GetElementByID('R0003')
		r3.DeleteDependency(r3.dependencies[0])
		self.RunTests(['test1_4_LAO_3'])

	def testCase1p4LAO_4(self):
		r3=self.cc.cp.manifest.GetElementByID('R0003')
		r3.CPDependency('R0007')
		self.RunTests(['test1_4_LAO_4'])

	def testCase1p4WebContent_1(self):
		r1=self.cc.cp.manifest.GetElementByID('R0001')
		f=r1.CPFile('L0001/Welcome.gif')
		self.RunTests(['test1_4_WebContent_1'])

	def RunTests(self,expectedFailures):
		ccp=CCTestSuite(self.cc)
		r=unittest.TestResult()
		ccp.run(r)
		# Cross check with the expected failures:
		fList=map(lambda x:x[0].id().split('.')[-1],r.failures)
		fList.sort()
		#print
		#print "%s : %s"%(self.id(),fList)
		self.failUnless(fList==expectedFailures)
		
if __name__ == "__main__":
	unittest.main()

