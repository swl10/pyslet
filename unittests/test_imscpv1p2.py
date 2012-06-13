#! /usr/bin/env python

import unittest
from tempfile import mkdtemp
import os, os.path, shutil
from StringIO import StringIO
from codecs import encode

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CPTests,'test'),
		unittest.makeSuite(CPElementTests,'test'),
		unittest.makeSuite(CPDocumentTests,'test'),
		unittest.makeSuite(CPManifestTests,'test'),
		unittest.makeSuite(CPResourcesTests,'test'),
		unittest.makeSuite(CPResourceTests,'test'),
		unittest.makeSuite(ContentPackageTests,'test'),
		))

TEST_DATA_DIR=os.path.join(os.path.split(os.path.abspath(__file__))[0],'data_imscpv1p2')

from pyslet.imscpv1p2 import *

class CPTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSCP_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_v1p1","Wrong CP namespace: %s"%IMSCP_NAMESPACE)
		self.failUnless(IMSCPX_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_extensionv1p2","Wrong extension namespace: %s"%IMSCPX_NAMESPACE)

class CPElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=CPElement(None)
		
# class CPXElementTests(unittest.TestCase):
# 	def testCaseConstructor(self):
# 		e=CPXElement(None)
# 		self.failUnless(e.ns==IMSCPX_NAMESPACE,'ns on construction')

		
EXAMPLE_1="""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1" identifier="test"></manifest>"""

EXAMPLE_2="""<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1" xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_v1p2" 
xmlns:imsqti="http://www.imsglobal.org/xsd/imsqti_v2p1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="MANIFEST-QTI-1" 
xsi:schemaLocation="http://www.imsglobal.org/xsd/imscp_v1p1 http://www.imsglobal.org/xsd/imscp_v1p1.xsd   
http://www.imsglobal.org/xsd/imsmd_v1p2 imsmd_v1p2p4.xsd  http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd">
	<organizations/>
	<resources>
		<resource identifier="choice" type="imsqti_item_xmlv2p1" href="choice.xml">
			<metadata>
				<imsmd:lom>
					<imsmd:general>
						<imsmd:identifier>qti_v2_item_01</imsmd:identifier>
						<imsmd:title>
							<imsmd:langstring xml:lang="en">Metadata Example Item #1</imsmd:langstring>
						</imsmd:title>
						<imsmd:description>
							<imsmd:langstring xml:lang="en">This is a dummy item</imsmd:langstring>
						</imsmd:description>
					</imsmd:general>
					<imsmd:lifecycle>
						<imsmd:version>
							<imsmd:langstring xml:lang="en">1.0.1</imsmd:langstring>
						</imsmd:version>
						<imsmd:status>
							<imsmd:source>
								<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
							</imsmd:source>
							<imsmd:value>
								<imsmd:langstring xml:lang="x-none">Draft</imsmd:langstring>
							</imsmd:value>
						</imsmd:status>
					</imsmd:lifecycle>
					<imsmd:metametadata>
						<imsmd:metadatascheme>LOMv1.0</imsmd:metadatascheme>
						<imsmd:metadatascheme>QTIv2.1</imsmd:metadatascheme>
						<imsmd:language>en</imsmd:language>
					</imsmd:metametadata>
					<imsmd:technical>
						<imsmd:format>text/x-imsqti-item-xml</imsmd:format>
						<imsmd:format>image/png</imsmd:format>
					</imsmd:technical>
				</imsmd:lom>
				<imsqti:qtiMetadata>
					<imsqti:timeDependent>false</imsqti:timeDependent>
					<imsqti:interactionType>choiceInteraction</imsqti:interactionType>
					<imsqti:feedbackType>nonadaptive</imsqti:feedbackType>
					<imsqti:solutionAvailable>true</imsqti:solutionAvailable>
					<imsqti:toolName>XMLSPY</imsqti:toolName>
					<imsqti:toolVersion>5.4</imsqti:toolVersion>
					<imsqti:toolVendor>ALTOVA</imsqti:toolVendor>
				</imsqti:qtiMetadata>
			</metadata>
			<file href="choice.xml"/>
			<file href="images/sign.png"/>
		</resource>
	</resources>
</manifest>"""


class CPDocumentTests(unittest.TestCase):
	def testCaseConstructor(self):
		doc=ManifestDocument()
		self.failUnless(isinstance(doc,xmlns.XMLNSDocument))
		doc=ManifestDocument(root=Manifest)
		root=doc.root
		self.failUnless(isinstance(root,Manifest))
		
	def testCaseExample1(self):
		doc=ManifestDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		root=doc.root
		self.failUnless(isinstance(root,Manifest))
		self.failUnless(root.ns==IMSCP_NAMESPACE and root.xmlname=='manifest')
		self.failUnless(root.id=='test')
		
	def testCaseExample2(self):
		doc=ManifestDocument()
		doc.Read(src=StringIO(EXAMPLE_2))
		resources=doc.root.Resources
		self.failUnless(len(resources.Resource)==1 and isinstance(resources.Resource[0],Resource))
		manifest=doc.GetElementByID("MANIFEST-QTI-1")
		self.failUnless(doc.root is manifest and isinstance(manifest,Manifest))
		resource=doc.GetElementByID("choice")
		self.failUnless(resource is resources.Resource[0])
	
	def testCaseSetID(self):
		doc=ManifestDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		manifest=doc.GetElementByID("test")
		self.failUnless(doc.root is manifest)
		manifest.SetID("manifest")
		self.failUnless(doc.GetElementByID("test") is None,"Old identifier still declared")
		self.failUnless(doc.GetElementByID("manifest") is manifest,"New identifier not declared")


class CPManifestTests(unittest.TestCase):
	def testCaseConstructor(self):
		m=Manifest(None)
		self.failUnless(m.Metadata is None,"Metadata present on construction")
		self.failUnless(isinstance(m.Organizations,Organizations),"Organizations element required on construction")
		self.failUnless(isinstance(m.Resources,Resources),"Resources element required on construction")
		self.failUnless(len(m.Manifest)==0,"Child manifests present on construction")


class CPResourcesTests(unittest.TestCase):
	def testCaseConstructor(self):
		r=Resources(None)
		self.failUnless(len(r.Resource)==0,"Resource list not empty on constructio")
		
	def testCaseNewResource(self):
		doc=ManifestDocument(root=Manifest)
		resources=doc.root.Resources
		try:
			resource=resources.ChildElement(resources.ResourceClass)
			resource.SetID('resource#1')
			resource.type='imsqti_item_xmlv2p1'
			self.fail("Invalid Name for resource identifier")
		except xmlns.XMLIDValueError:
			pass
		resource.SetID('resource_1')
		resource.type='imsqti_item_xmlv2p1'
		self.failUnless(isinstance(resource,Resource))
		self.failUnless(doc.GetElementByID('resource_1') is resource)
		self.failUnless(len(resources.Resource)==1 and resources.Resource[0] is resource)
	

class CPResourceTests(unittest.TestCase):
	def testCaseConstructor(self):
		r=Resource(None)
		self.failUnless(len(r.File)==0,"File list not empty on constructio")
		self.failUnless(len(r.Dependency)==0,"Dependency list not empty on constructio")

	def testCaseNewFile(self):
		doc=ManifestDocument()
		doc.Read(src=StringIO(EXAMPLE_2))
		r=doc.GetElementByID('choice')
		index=len(r.File)
		f=r.ChildElement(r.FileClass)
		f.SetAttribute('href','Extra.txt')
		self.failUnless(isinstance(f,File))
		self.failUnless(len(r.File)==index+1 and r.File[index] is f)

	def testCaseDeleteFile(self):
		doc=ManifestDocument()
		doc.Read(src=StringIO(EXAMPLE_2))
		r=doc.GetElementByID('choice')
		index=len(r.File)
		f=r.File[0]
		f1=r.File[1]
		r.DeleteFile(f)
		self.failUnless(len(r.File)==index-1 and r.File[0] is f1)


class ContentPackageTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.dList=[]
		self.d=mkdtemp('.d','pyslet-test_imscpv1p2-')
		os.chdir(self.d)
		os.mkdir('package')
		os.mkdir('mpackage')
		mpath=os.path.join('mpackage','imsmanifest.xml')
		f=open(mpath,'wb')
		f.write(EXAMPLE_2)
		f.close()
		self.dList.append(self.d)
		
	def tearDown(self):
		os.chdir(self.cwd)
		for d in self.dList:
			shutil.rmtree(d,True)

	def testCaseConstructor(self):
		cp=ContentPackage()
		self.failUnless(os.path.isdir(cp.dPath),"Default constructor must create a temp directory")
		self.failUnless(cp.GetPackageName()=='imscp',"Default package name is not empty string")
		# Ensure the temporary directory is cleaned up
		self.dList.append(cp.dPath)
		url=uri.URIFactory.URI(cp.manifest.GetBase())
		self.failUnless(isinstance(cp.manifest,xmlns.XMLNSDocument) and isinstance(cp.manifest.root,Manifest),"Constructor must create manifest")
		self.failUnless(os.path.split(url.GetPathname())[1]=='imsmanifest.xml',"Manifest file name")
		self.failUnless(isinstance(cp.manifest.root,Manifest),"Constructor must create manifest element")
		id=cp.manifest.root.id
		self.failUnless(cp.manifest.GetElementByID(id) is cp.manifest.root,"Manifest identifief not declared")
		self.failUnless(os.path.isfile(url.GetPathname()),"Constructor must create manifest file")
		cp=ContentPackage('newpackage')
		self.failUnless(os.path.isdir(cp.dPath) and os.path.abspath('newpackage')==cp.dPath,"Constructor creates specified directory")
		self.failUnless(cp.GetPackageName()=='newpackage',"Package name not taken from directory")
		cp=ContentPackage('package')
		self.failUnless(os.path.abspath('package')==cp.dPath,"Constructor with existing directory, no manifest")
		cp=ContentPackage('mpackage')
		self.failUnless(cp.manifest.root.id=="MANIFEST-QTI-1","Constructor with existing directory and manifest")
		self.failUnless(cp.GetPackageName()=='mpackage',"Package name wrongly affected by manifest")
		cp=ContentPackage(os.path.join('mpackage','imsmanifest.xml'))
		self.failUnless(os.path.isdir(cp.dPath) and os.path.abspath('mpackage')==cp.dPath,"Constructor identifies pkg dir from manifest file")
		self.failUnless(cp.manifest.root.id=="MANIFEST-QTI-1","Constructor from manifest file")
	
	def testCaseUnicode(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_1'))
		resources=cp.manifest.root.Resources
		r=resources.Resource[0]
		self.failUnless(len(r.File)==1)
		f=r.File[0]
		self.failUnless(isinstance(f,File) and str(f.href)=="%E8%8B%B1%E5%9B%BD.xml","File path")
		doc=xmlns.Document(baseURI=f.ResolveURI(f.href))
		doc.Read()
		self.failUnless(doc.root.xmlname=='tag' and
			doc.root.GetValue()==u"Unicode Test: \u82f1\u56fd")
		cp2=ContentPackage(os.path.join(TEST_DATA_DIR,encode(u'\u82f1\u56fd','utf-8')))
		self.failUnless(cp2.GetPackageName()==u'\u82f1\u56fd',"Unicode package name test")

	def testCaseZipRead(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_1.zip'))
		self.failUnless(os.path.isdir(cp.dPath),"Zip constructor must create a temp directory")
		# Ensure the temporary directory is cleaned up
		self.dList.append(cp.dPath)
		self.failUnless(cp.GetPackageName()=='package_1',"Zip extension not removed for name")
		resources=cp.manifest.root.Resources
		f=resources.Resource[0].File[0]
		doc=xmlns.Document(baseURI=f.ResolveURI(f.href))
		doc.Read()
		self.failUnless(doc.root.xmlname=='tag' and
			doc.root.GetValue()==u"Unicode Test: \u82f1\u56fd")
	
	def testCaseZipWrite(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_1.zip'))
		self.dList.append(cp.dPath)
		cp.ExportToPIF('Package2.zip')
		cp2=ContentPackage('Package2.zip')
		self.dList.append(cp2.dPath)
		resources=cp2.manifest.root.Resources
		f=resources.Resource[0].File[0]
		doc=xmlns.Document(baseURI=f.ResolveURI(f.href))
		doc.Read()
		self.failUnless(doc.root.xmlname=='tag' and
			doc.root.GetValue()==u"Unicode Test: \u82f1\u56fd")
	
	def testCaseFileTable(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_3'))
		ft=cp.fileTable
		self.failUnless(len(ft.keys())==6)
		self.failUnless(len(ft['file_1.xml'])==2 and isinstance(ft['file_1.xml'][0],File))
		self.failUnless(len(ft['file_4.xml'])==0,File)
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_3'))
		cp.SetIgnoreFiles("\\..*|.*4.*")
		cp.RebuildFileTable()
		ft=cp.fileTable
		self.failUnless(len(ft.keys())==5)

	def testCaseUniqueFile(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_3'))
		ft=cp.fileTable
		fPath=cp.GetUniqueFile('file_1.xml')
		self.failIf(fPath=='file_1.xml',"file path must be unique")
		self.failUnless(fPath[-4:]=='.xml',"Must preserve extension")
		self.failIf(fPath in ft, "file path must not be in use")

	def testCaseDeleteFile(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_3'))
		cp.ExportToPIF('package_3.zip')
		cp2=ContentPackage('package_3.zip')
		self.dList.append(cp2.dPath)
		r1=cp2.manifest.GetElementByID('test1')
		r2=cp2.manifest.GetElementByID('test2')
		r1Len=len(r1.File)
		r2Len=len(r2.File)
		cp2.DeleteFile('file_1.xml')
		self.failUnless(len(r1.File)==r1Len-1)
		self.failUnless(len(r2.File)==r2Len-1)
		
	def testCasePathInPath(self):
		goodPath=os.path.join(TEST_DATA_DIR,'hello','world')
		self.failUnless(PathInPath(goodPath,TEST_DATA_DIR)==os.path.join('hello','world'))
		self.failUnless(PathInPath(goodPath,os.path.join(TEST_DATA_DIR,'hello'))=='world')
		badPath=os.path.join(TEST_DATA_DIR,'hello','worlds','bad')
		self.failUnless(PathInPath(badPath,goodPath) is None,badPath)
		self.failUnless(PathInPath(goodPath,goodPath)=='',"Match")
		self.failUnless(PathInPath(TEST_DATA_DIR,goodPath) is None,"Path contains Path")

	def testCasePackagePaths(self):
		cp=ContentPackage(os.path.join(TEST_DATA_DIR,'package_3'))
		goodPath=os.path.join(cp.dPath,'hello','world')
		self.failUnless(cp.PackagePath(goodPath)==os.path.join('hello','world'))
		badPath=os.path.join(TEST_DATA_DIR,'package_3x','hello','world')
		self.failUnless(cp.PackagePath(badPath) is None,badPath)
		badPath=os.path.join(TEST_DATA_DIR,'package_x')
		self.failUnless(cp.PackagePath(badPath) is None,badPath)
		badPath=TEST_DATA_DIR
		self.failUnless(cp.PackagePath(badPath) is None,badPath)

	def testCaseCleanUp(self):
		cp=ContentPackage()
		dPath=cp.dPath
		self.failUnless(os.path.isdir(dPath))
		cp.Close()
		self.failUnless(cp.manifest is None,"Manifest not removed on close")
		self.failIf(os.path.isdir(dPath),"Temp directory not deleted on close")
		cp=ContentPackage('package')
		dPath=cp.dPath
		self.failUnless(os.path.isdir(dPath))
		cp.Close()
		self.failUnless(cp.manifest is None,"Manifest not removed on close")
		self.failUnless(os.path.isdir(dPath),"Non-temp directory removed on close")
		
		
if __name__ == "__main__":
	unittest.main()

