#! /usr/bin/env python
"""This module implements test to check against the IMSCC Profile 1.0 specification defined by IMS GLC"""

import unittest
from types import StringTypes
import pyslet.imscpv1p2 as imscp
import os.path

CCOrganizationStructure="rooted-hierarchy"
CartridgeWebContentType="webcontent"
AssociatedContentType="associatedcontent/imscc_xmlv1p0/learning-application-resource"
DiscussionTopicContentType="imsdt_xmlv1p0"
WebLinkContentType="imswl_xmlv1p0"
AssessmentContentType="imsqti_xmlv1p2/imscc_xmlv1p0/assessment"
QuestionBankContentType="imsqti_xmlv1p2/imscc_xmlv1p0/question-bank"
		

class CommonCartridge:
	
	ContentPackageClass=imscp.ContentPackage
	
	def __init__(self,src=None):
		if type(src) in StringTypes:
			self.cp=self.ContentPackageClass(src)
		elif isinstance(src,self.ContentPackageClass):
			self.cp=src
		elif src is None:
			self.cp=self.ContentPackageClass()
		else:
			raise ValueError
		self.ScanResources()
		
	def ScanResources(self):
		"""Scans the content package and builds lists of resources.
		
		Resources in Common Cartridge are either Cartridge Web Content resources,
		Learning Application Object (LAO) resources or an LAO's Associated Content
		resources.  Any other resources are treated as passengers."""		
		self.cwcList=[]
		self.laoTable={}
		resources=self.cp.manifest.root.Resources
		# First pass is a search for CWCs and LAOs
		for r in resources.Resource:
			rType=r.type
			if rType==AssociatedContentType:
				# Associated content is linked from the LAO later
				continue
			if rType==CartridgeWebContentType:
				self.cwcList.append(r)
				continue
			# All other resoure types are treated as LAOs
			if len(r.File)>=1:
				laoDescriptor=r.File[0]
				fPath=laoDescriptor.PackagePath(self.cp)
				head,tail=fPath.split()
				if not head:
					# The LAO must be in a directory, not at the top-level of the CP
					head=None
			else:
				head=None
			# Is there associated content?
			acr=None
			depList=r.Dependency
			for dep in depList:
				rDep=self.cp.manifest.GetElementByID(dep.identifierref)
				if isinstance(rDep,imscp.Resource) and rDep.type==AssociatedContentType:
					acr=rDep
					break
			self.laoTable[r.id]=[head,acr]
		
	def Close(self):
		if self.cp:
			self.cp.Close()
		self.cp=None

		
class CCTestSuite(unittest.TestSuite):
	def __init__(self,cp):
		"""This test suite requires an IMS Content Package to test"""
		unittest.TestSuite.__init__(self)
		loader=unittest.TestLoader()
		for tName in loader.getTestCaseNames(CCTestCase):
			self.addTest(CCTestCase(cp,tName))

class CCTestCase(unittest.TestCase):
	def __init__(self,cc,method):
		"""We initialise the test case with the Common Cartridge being
		tested and the name of the method to call."""
		unittest.TestCase.__init__(self,method)
		self.cc=cc
	
	def test1_4_AssociatedContent_1(self):
		"""A resource of the type associatedcontent must ...
		1. ...contain a file element for each file that exists in the directory
		that contains the associated Learning Application Object's descriptor
		file or any of its subdirectories."""
		for lao in self.cc.laoTable.keys():
			laoResource=self.cc.cp.manifest.GetElementByID(lao)
			dPath,acr=self.cc.laoTable[lao]
			# acr must have a file element for all items in dPath
			fPaths=self.cc.cp.fileTable.keys()
			fPaths.sort()
			for fPath in fPaths:
				if imscp.PathInPath(fPath,dPath):
					fList=self.cc.cp.fileTable[fPath]
					foundResource=False
					for f in fList:
						if f.parent is acr:
							foundResource=True
							break
						elif f.parent is laoResource:
							foundResource=True
							break
					if not foundResource:
						self.fail(fPath)
		
	def test1_4_AssociatedContent_2(self):
		"""A resource of the type associatedcontent must ...
		2. It must not contain any references to files above the directory
		containing the associated Learning Application Object's descriptor file."""
		for lao in self.cc.laoTable.keys():
			dPath,acr=self.cc.laoTable[lao]
			if acr is None:
				continue
			for f in acr.File:
				fPath=f.PackagePath(self.cc.cp)
				self.failUnless(imscp.PathInPath(fPath,dPath))
	
	def test1_4_AssociatedContent_3(self):
		"""A resource of the type associatedcontent must ...
		3. It must not contain any dependency elements."""
		for lao in self.cc.laoTable.keys():
			dPath,acr=self.cc.laoTable[lao]
			if acr is None:
				continue
			self.failIf(len(acr.Dependency)>0,acr.id)

	def test1_4_LAO_1(self):
		"""A resource that represents a Learning Application Object has the
		following general restrictions:...
		1. It must contain a file element that points to the Learning
		Application Object's descriptor file."""
		for lao in self.cc.laoTable.keys():
			laoResource=self.cc.cp.manifest.GetElementByID(lao)
			self.failIf(len(laoResource.File)==0)
	
	def test1_4_LAO_2(self):
		"""A resource that represents a Learning Application Object has the
		following general restrictions:...
		2. It must not contain any other file elements."""
		for lao in self.cc.laoTable.keys():
			laoResource=self.cc.cp.manifest.GetElementByID(lao)
			self.failIf(len(laoResource.File)>1)
	
	def GetACRListForDirectory(self,dPath):
		"""Returns a list of associated content resources that have file's
		that reside in dPath.  (Used internally.)"""
		acrList=[]
		fPaths=self.cc.cp.fileTable.keys()
		fPaths.sort()
		for fPath in fPaths:
			if imscp.PathInPath(fPath,dPath):
				fList=self.cc.cp.fileTable[fPath]
				foundResource=False
				for f in fList:
					if f.parent.type!=AssociatedContentType:
						continue
					if f.parent in acrList:
						continue
					acrList.append(f.parent)	
		return acrList
		
	def test1_4_LAO_3(self):
		"""A resource that represents a Learning Application Object has the
		following general restrictions:...
		3. If additional files exist in the directory containing the Learning
		Application Object's descriptor file, or any of its subdirectories, the
		resource must contain a dependency element that references the resource
		of type 'associatedcontent' which contains the references to these
		files."""
		for lao in self.cc.laoTable.keys():
			laoResource=self.cc.cp.manifest.GetElementByID(lao)
			dPath,acr=self.cc.laoTable[lao]
			if dPath is None:  # this is a fail of a different sort
				continue			
			acrList=self.GetACRListForDirectory(dPath)
			# Now we must have a dependency for each element of acrList
			for d in laoResource.Dependency:
				acr=self.cc.cp.manifest.GetElementByID(d.identifierref)
				if acr in acrList:
					del acrList[acrList.index(acr)]
			self.failIf(len(acrList))


	def test1_4_LAO_4(self):
		"""A resource that represents a Learning Application Object has the
		following general restrictions:...
		4. It must not contain any other dependency elements of type
		'associatedcontent'."""
		for lao in self.cc.laoTable.keys():
			laoResource=self.cc.cp.manifest.GetElementByID(lao)
			dPath,acr=self.cc.laoTable[lao]
			if dPath is None:  # this is a fail of a different sort
				continue			
			acrList=self.GetACRListForDirectory(dPath)
			# The use of 'the' suggests that there must be only one such acr
			self.failIf(len(acrList)>1)
			if len(acrList):
				# And hence all associated content dependencies in lao must be to
				# the single acr in this list.
				for d in laoResource.Dependency:
					acr=self.cc.cp.manifest.GetElementByID(d.identifierref)
					if acr is None:
						print d.identifierref
						print self.cc.cp.manifest.root
					if acr.type!=AssociatedContentType:
						continue
					self.failUnless(acr is acrList[0])
	
	def test1_4_WebContent_1(self):
		"""A resource of the type "webcontent" must comply with the following
		restrictions...
		1. It may contain a file element for any file that exists in the package
		so long as the file is not in a Learning Application Object directory or
		a subdirectory of any Learning Application Object directory."""
		dPathList=[]
		for lao in self.cc.laoTable.keys():
			dPath,acr=self.cc.laoTable[lao]
			if dPath is not None:
				dPathList.append(dPath)
		for wc in self.cc.cwcList:
			for f in wc.File:
				fPath=f.PackagePath(self.cc.cp)
				for dPath in dPathList:
					self.failIf(imscp.PathInPath(fPath,dPath))
	
