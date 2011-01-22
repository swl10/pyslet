import unittest
import tempfile
import os
from StringIO import StringIO

from cp import *
from md import IMSMetadata
from qti.metadata import QTIMetadata
from PyAssess.ieee.p1484_12 import LOMMetadata

from PyAssess.ietf.rfc2396 import URIReference

import pdb

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(SampleManifestTests,'test'),
		unittest.makeSuite(GeneralManifestTests,'test')
		))


SAMPLE_MANIFEST="""<?xml version = "1.0" encoding = "UTF-8"?>
<manifest xmlns = "http://www.imsglobal.org/xsd/imscp_v1p1" 
	xmlns:imsmd = "http://www.imsglobal.org/xsd/imsmd_v1p2" 
	xmlns:xsi = "http://www.w3.org/2001/XMLSchema-instance" 	xsi:schemaLocation = "http://www.imsglobal.org/xsd/imscp_v1p1 http://www.imsglobal.org/xsd/imscp_v1p1.xsd http://www.imsglobal.org/xsd/imsmd_v1p2 http://www.imsglobal.org/xsd/imsmd_v1p2.xsd "
		identifier="Manifest3-CEC3D3-3201-DF8E-8F42-3CEED12F4197"
   	version="IMS CP 1.1.4">

		<metadata>
		<schema>IMS Content</schema>
		<schemaversion>1.1.4</schemaversion>
		<imsmd:lom>
			<imsmd:general>
				<imsmd:title>
					<imsmd:langstring xml:lang="en-US">IMS Content Packaging Sample - Full Metadata</imsmd:langstring>
				</imsmd:title>
				<imsmd:catalogentry>
					<imsmd:catalog>ISBN</imsmd:catalog>
					<imsmd:entry>
						<imsmd:langstring>0-534-26702-5</imsmd:langstring>
					</imsmd:entry>
				</imsmd:catalogentry>
				<imsmd:language>en-US</imsmd:language>
				<imsmd:description>
					<!--English description-->
					<imsmd:langstring xml:lang="en-US">A sample content packaging record</imsmd:langstring>
					<!--French Description -->
					<imsmd:langstring xml:lang="fr">Un programme...</imsmd:langstring>
				</imsmd:description>
				<imsmd:keyword>
					<!--English Keywords, unordered list-->
					<imsmd:langstring xml:lang="en">content interchange</imsmd:langstring>
					<!--Going to have to fix this problem with keyword rather then keywords and the issue of multiple langstrings-->
					<!--<imsmd:langstring xml:lang="en">learning objects</imsmd:langstring>-->
					<!--<imsmd:langstring xml:lang="en">e-learning</imsmd:langstring>-->
				</imsmd:keyword>
				<imsmd:coverage>
					<imsmd:langstring xml:lang="en">Sample code</imsmd:langstring>
				</imsmd:coverage>
				<imsmd:structure>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">Hierarchical</imsmd:langstring>
					</imsmd:value>
				</imsmd:structure>
				<imsmd:aggregationlevel>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">2</imsmd:langstring>
					</imsmd:value>
				</imsmd:aggregationlevel>
			</imsmd:general>
			<imsmd:lifecycle>
				<imsmd:version>
					<imsmd:langstring xml:lang="en">1.0</imsmd:langstring>
				</imsmd:version>
				<imsmd:status>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">Final</imsmd:langstring>
					</imsmd:value>
				</imsmd:status>
				<!--Contains an unordered list of  contribute-->
				<imsmd:contribute>
					<imsmd:role>
						<imsmd:source>
							<imsmd:langstring xml:lang="en">LOMv1.0</imsmd:langstring>
						</imsmd:source>
						<imsmd:value>
							<imsmd:langstring xml:lang="en">Author</imsmd:langstring>
						</imsmd:value>
					</imsmd:role>
					<imsmd:centity>
						<imsmd:vcard>BEGIN:vCard FN:Chris Moffatt N:Moffatt END:vCard</imsmd:vcard>
					</imsmd:centity>
					<imsmd:date>
						<imsmd:datetime>2000-01-01</imsmd:datetime>
					</imsmd:date>
				</imsmd:contribute>
				<imsmd:contribute>
					<imsmd:role>
						<imsmd:source>
							<imsmd:langstring xml:lang="en">LOMv1.0</imsmd:langstring>
						</imsmd:source>
						<imsmd:value>
							<imsmd:langstring xml:lang="en">Publisher</imsmd:langstring>
						</imsmd:value>
					</imsmd:role>
					<imsmd:centity>
						<imsmd:vcard>BEGIN:vCard ORG:IMS Global Learning Corporation END:vCard</imsmd:vcard>
					</imsmd:centity>
					<imsmd:date>
						<imsmd:datetime>2000-01-01</imsmd:datetime>
						<imsmd:description>
							<imsmd:langstring xml:lang="en-US">20th Century</imsmd:langstring>
						</imsmd:description>
					</imsmd:date>
				</imsmd:contribute>
			</imsmd:lifecycle>
			<imsmd:metametadata>
				<imsmd:catalogentry>
					<imsmd:catalog>IMS-Test</imsmd:catalog>
					<imsmd:entry>
						<imsmd:langstring>1999.000003</imsmd:langstring>
					</imsmd:entry>
				</imsmd:catalogentry>
				<imsmd:catalogentry>
					<imsmd:catalog>ABC123</imsmd:catalog>
					<imsmd:entry>
						<imsmd:langstring xml:lang="en-US">123A</imsmd:langstring>
					</imsmd:entry>
				</imsmd:catalogentry>
				<imsmd:contribute>
					<imsmd:role>
						<imsmd:source>
							<imsmd:langstring xml:lang="en">LOMv1.0</imsmd:langstring>
						</imsmd:source>
						<imsmd:value>
							<imsmd:langstring xml:lang="en">Creator</imsmd:langstring>
						</imsmd:value>
					</imsmd:role>
					<imsmd:centity>
						<imsmd:vcard>BEGIN:vCard FN:Chris Moffatt N:Moffatt END:vCard</imsmd:vcard>
					</imsmd:centity>
					<imsmd:date>
						<imsmd:datetime>1999-08-05</imsmd:datetime>
					</imsmd:date>
				</imsmd:contribute>
				<imsmd:metadatascheme>LOMv1.0</imsmd:metadatascheme>
				<!-- English as default metadata language. -->
				<imsmd:language>en-US</imsmd:language>
			</imsmd:metametadata>
			<imsmd:technical>
				<imsmd:format>XMLL 1.0</imsmd:format>
				<imsmd:size>70306</imsmd:size>
				<imsmd:location type="URI">http://www.imsglobal.org/content</imsmd:location>
				<imsmd:requirement>
					<imsmd:type>
						<!--
						<imsmd:source>
							<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
						</imsmd:source>
						-->
						<imsmd:value>
							<imsmd:langstring xml:lang="x-none">Binding</imsmd:langstring>
						</imsmd:value>
					</imsmd:type>
					<imsmd:name>
						<!--
						<imsmd:source>
							<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
						</imsmd:source>
						-->
						<imsmd:value>
							<imsmd:langstring xml:lang="x-none">XML</imsmd:langstring>
						</imsmd:value>
					</imsmd:name>
					<imsmd:minimumversion>1.0</imsmd:minimumversion>
					<imsmd:maximumversion>5.2</imsmd:maximumversion>
				</imsmd:requirement>
				<imsmd:installationremarks>
					<imsmd:langstring xml:lang="en">Download</imsmd:langstring>
				</imsmd:installationremarks>
				<imsmd:otherplatformrequirements>
					<imsmd:langstring xml:lang="en">Requires web browser for rendering</imsmd:langstring>
				</imsmd:otherplatformrequirements>
				<imsmd:duration />
			</imsmd:technical>
			<imsmd:educational>
				<imsmd:learningresourcetype>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">Exercise</imsmd:langstring>
					</imsmd:value>
				</imsmd:learningresourcetype>
				<imsmd:interactivitylevel>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">very low</imsmd:langstring>
					</imsmd:value>
				</imsmd:interactivitylevel>
				<imsmd:semanticdensity>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">low</imsmd:langstring>
					</imsmd:value>
				</imsmd:semanticdensity>
				<imsmd:intendedenduserrole>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">Learner</imsmd:langstring>
					</imsmd:value>
				</imsmd:intendedenduserrole>
				<imsmd:context>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">Vocational Training</imsmd:langstring>
					</imsmd:value>
				</imsmd:context>
				<imsmd:typicalagerange>
					<imsmd:langstring xml:lang="x-none">18-99</imsmd:langstring>
				</imsmd:typicalagerange>
				<imsmd:description>
					<imsmd:langstring xml:lang="en">Sample code</imsmd:langstring>
				</imsmd:description>
				<imsmd:language>en-US</imsmd:language>
			</imsmd:educational>
			<imsmd:rights>
				<imsmd:cost>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">no</imsmd:langstring>
					</imsmd:value>
				</imsmd:cost>
				<imsmd:copyrightandotherrestrictions>
					<imsmd:source>
						<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
					</imsmd:source>
					<imsmd:value>
						<imsmd:langstring xml:lang="x-none">no</imsmd:langstring>
					</imsmd:value>
				</imsmd:copyrightandotherrestrictions>
			</imsmd:rights>
		</imsmd:lom>
	</metadata>
	<organizations default="TOC1">
		<organization identifier="TOC1" structure="hierarchical">
			<title>default</title>
			<item identifier="ITEM1" identifierref="RESOURCE1">
				<title>Lesson 1</title>
				<item identifier="ITEM2" identifierref="RESOURCE2">
					<title>Introduction 1</title>
				</item>
				<item identifier="ITEM3" identifierref="RESOURCE3">
					<title>Content 1</title>
				</item>
				<item identifier="ITEM4" identifierref="RESOURCE4">
					<title>Summary 1</title>
				</item>
			</item>
			<item identifier="ITEM5" identifierref="RESOURCE5">
				<title>Lesson 2</title>
				<item identifier="ITEM6" identifierref="RESOURCE6">
					<title>Introduction 2</title>
				</item>
				<item identifier="ITEM7" identifierref="RESOURCE7">
					<title>Content 2</title>
				</item>
				<item identifier="ITEM8" identifierref="RESOURCE8">
					<title>Summary 2</title>
				</item>
			</item>
			<item identifier="ITEM9" identifierref="RESOURCE9">
				<title>Lesson 3</title>
				<item identifier="ITEM10" identifierref="RESOURCE10">
					<title>Introduction 3</title>
				</item>
				<item identifier="ITEM11" identifierref="RESOURCE11">
					<title>Content 3</title>
				</item>
				<item identifier="ITEM12" identifierref="RESOURCE12">
					<title>Summary 3</title>
				</item>
			</item>
		</organization>
	</organizations>
	<resources>
		<resource identifier="RESOURCE1" type="webcontent" href="lesson1.htm">
			<file href="lesson1.htm"/>
		</resource>
		<resource identifier="RESOURCE2" type="webcontent" href="intro1.htm">
			<file href="intro1.htm"/>
		</resource>
		<resource identifier="RESOURCE3" type="webcontent" href="content1.htm">
			<file href="content1.htm"/>
		</resource>
		<resource identifier="RESOURCE4" type="webcontent" href="summary1.htm">
			<file href="summary1.htm"/>
		</resource>
		<resource identifier="RESOURCE5" type="webcontent" href="lesson2.htm">
			<file href="lesson1.htm"/>
		</resource>
		<resource identifier="RESOURCE6" type="webcontent" href="intro2.htm">
			<file href="intro2.htm"/>
		</resource>
		<resource identifier="RESOURCE7" type="webcontent" href="content2.htm">
			<file href="content1.htm"/>
		</resource>
		<resource identifier="RESOURCE8" type="webcontent" href="summary2.htm">
			<file href="summary1.htm"/>
		</resource>
		<resource identifier="RESOURCE9" type="webcontent" href="lesson3.htm">
			<file href="lesson3.htm"/>
		</resource>
		<resource identifier="RESOURCE10" type="webcontent" href="intro3.htm">
			<file href="intro3.htm"/>
		</resource>
		<resource identifier="RESOURCE11" type="webcontent" href="content3.htm">
			<file href="content3.htm"/>
		</resource>
		<resource identifier="RESOURCE12" type="webcontent" href="summary3.htm">
			<file href="summary3.htm"/>
		</resource>
	</resources>
</manifest>
"""

SAMPLE_MANIFEST_FILES=[
	"content1.htm",
	"content2.htm",
	"content3.htm",
	"intro1.htm",
	"intro2.htm",
	"intro3.htm",
	"lesson1.htm",
	"lesson2.htm",
	"lesson3.htm",
	"summary1.htm",
	"summary2.htm",
	"summary3.htm"]
	
SAMPLE_HTML="""<html>
<head><title>Sample HTML File</title></head>
<body>
<p>This is a sample HTML file generated by imscp_test.py</p>
</body>
</html>
"""

class SampleManifestTests(unittest.TestCase):
	def setUp(self):
		self.dpath=tempfile.mktemp()
		os.mkdir(self.dpath)
		for fName in SAMPLE_MANIFEST_FILES:
			fPath=os.path.join(self.dpath,fName)
			f=file(fPath,'w')
			f.write(SAMPLE_HTML)
			f.close()
		fPath=os.path.join(self.dpath,"imsmanifest.xml")
		f=file(fPath,'w')
		f.write(SAMPLE_MANIFEST)
		f.close()
	
	def tearDown(self):
		for fName in SAMPLE_MANIFEST_FILES:
			fPath=os.path.join(self.dpath,fName)
			os.remove(fPath)
		fPath=os.path.join(self.dpath,"imsmanifest.xml")
		os.remove(fPath)
		os.rmdir(self.dpath)
	
	def CheckSamplePackage(self,p):
		self.failUnless(p.manifest.identifier=="Manifest3-CEC3D3-3201-DF8E-8F42-3CEED12F4197","manifest id check")
		self.failUnless(p.manifest.version=="IMS CP 1.1.4","manifest version check")
		self.failUnless(p.manifest.mdSchema=="IMS Content","metadata schema check")
		self.failUnless(p.manifest.mdSchemaVersion=="1.1.4","metadata schemaVersion check")
		self.failUnless(len(p.manifest.metadata)==1 and isinstance(p.manifest.metadata[0],LOMMetadata),"metadata check")
		self.failUnless(p.manifest.defaultOrganization=="TOC1" and len(p.manifest.organizations)==1,"organizations check")
		organization=p.manifest.organizations[0]
#		pdb.set_trace()
		self.failUnless(organization.structure=="hierarchical" and organization.title=="default" and len(organization.items)==3,
			"organization check")
		item=organization.items[1]
		self.failUnless(item.identifier=="ITEM5" and item.title=="Lesson 2" and 
			item.identifierRef=="RESOURCE5" and len(item.items)==3,"item check")
		item=item.items[2]
		self.failUnless(item.identifier=="ITEM8" and item.title=="Summary 2" and
			item.identifierRef=="RESOURCE8" and len(item.items)==0,"sub-item check")
		self.failUnless(len(p.manifest.resources)==12,"sample manifest resource count check")
		resource=p.manifest.resources[4]
		self.failUnless(resource.identifier=="RESOURCE5" and resource.type=="webcontent" and resource.href=="lesson2.htm"
			and len(resource.files)==1,"resource check")
		try:
			p.manifest.CheckIDs()
		except CPError:
				self.fail("ID cross-check")
				
	def testLoadSampleDirectory(self):
		"""Check constructor with sample manifest directory path"""
		p=ContentPackage(self.dpath)
		self.CheckSamplePackage(p)
		
	def testLoadSampleManifest(self):
		"""Check constructor with sample manifest file path"""
		p=ContentPackage(os.path.join(self.dpath,"imsmanifest.xml"))
		self.CheckSamplePackage(p)
	
	def testExportAndReread(self):
		"""Check we can export to XML and re-read the same file"""
		p=ContentPackage(os.path.join(self.dpath,"imsmanifest.xml"))
		xmlOutput=StringIO()
		p.manifest.WriteXML(xmlOutput)
		# xmlOutput.seek(0)
		# print xmlOutput.read()
		xmlOutput.seek(0)
		p.ReadManifestFile(xmlOutput)
		self.CheckSamplePackage(p)
		
class GeneralManifestTests(unittest.TestCase):
	def setUp(self):
		self.dpath=tempfile.mktemp()
		os.mkdir(self.dpath)
		self.p=ContentPackage(self.dpath)
		self.m=self.p.manifest
	
	def tearDown(self):
		self.p.Erase()
		os.rmdir(self.dpath)
	
	def testBasics(self):
		"""Check basic manifest properties"""
		self.failUnless(self.m.package==self.p,"manifest to parent package")

	def testSetIdentifier(self):
		"""Check the handling of the identifier"""
		self.failUnless(self.m.identifier=="manifest","default manifest identifier")
		self.m.SetIdentifier("M4")
		self.failUnless(self.m.identifier=="M4","set good identifier")
		# Setting the identifier to its current value is benign
		self.m.SetIdentifier("M4")
		try:
			self.m.SetIdentifier("4M")
			self.fail("set bad identifier")
		except CPError:
			pass
		# Add a test to check that a duplicate identifier is caught with, say, an organization
		Organization(self.m,"Org1")
		try:
			self.m.SetIdentifier("Org1")
			self.fail("set duplicate identifier")
		except CPError:
			pass
		try:
			self.m.SetIdentifier(None)
			self.fail("None for identifier")
		except ValueError:
			pass

	def testSetVersion(self):
		"""Check the handling of the version"""
		self.failUnless(self.m.version is None,"default manifest version")
		self.m.SetVersion("1.2.3")
		self.failUnless(self.m.version=="1.2.3","set good version")
		self.m.SetVersion("01234567890123456789")
		try:
			self.m.SetVersion("012345678901234567891")
			self.fail("long version")
		except ValueError:
			pass
		self.m.SetVersion(None)
		self.failUnless(self.m.version is None,"clear manifest version")

	def testSetBase(self):
		"""Check the handling of the base URI"""
		self.failUnless(self.m.base is None,"default base URI")
		self.m.SetBase(URIReference("lesson"))
		self.failUnless(isinstance(self.m.base,URIReference) and self.m.base=="lesson","set base value")
		self.m.SetBase("lesson")
		self.failUnless(isinstance(self.m.base,URIReference) and self.m.base=="lesson","set base value")
		self.m.SetBase(None)
		self.failUnless(self.m.base is None,"clear base URI")
		
	def testAddMetadata(self):
		"""Check that we can handle metadata"""
		self.failUnless(self.m.mdSchema is None and self.m.mdSchemaVersion is None,"initial metadata schema info")
		self.m.SetMDSchemaInfo("IMS Content","1.1")
		self.failUnless(self.m.mdSchema=="IMS Content" and self.m.mdSchemaVersion=="1.1","set metadata schema info")
		self.m.SetMDSchemaInfo(None,None)
		self.failUnless(self.m.mdSchema is None and self.m.mdSchemaVersion is None,"erase metadata schema info")
		self.failUnless(len(self.m.metadata)==0,"initial metadata")
		self.m.AddMetadata(CustomMetadata())
		self.failUnless(len(self.m.metadata)==1,"add metadata")
		self.m.RemoveMetadata(0)
		self.failUnless(len(self.m.metadata)==0,"remove metadata")
		
	def testDefaultOrganization(self):
		"""Check that we can set the default organization"""
		self.failUnless(self.m.defaultOrganization is None,"default organization initial value")
		self.m.SetDefaultOrganization("organization_1")
		self.m.SetDefaultOrganization(None)
		self.failUnless(self.m.defaultOrganization is None,"clear default organization")
	
	def testOrganization(self):
		"""Check that we can handle organizations"""
		self.failUnless(len(self.m.organizations)==0,"initial organizations")
		o1=Organization(self.m)
		self.failUnless(len(self.m.organizations)==1,"add organization")
		o2=Organization(self.m)
		self.failUnless(len(self.m.organizations)==2 and o1.identifier!=o2.identifier,"add second organization")
		self.m.RemoveOrganization(o1.identifier)
		self.failUnless(len(self.m.organizations)==1,"remove organization")

	def testResource(self):
		"""Check that we can handle resources"""
		self.failUnless(len(self.m.resources)==0,"initial resources")
		r1=Resource(self.m)
		self.failUnless(len(self.m.resources)==1,"add resource")
		r2=Resource(self.m)
		self.failUnless(len(self.m.resources)==2 and r1.identifier!=r2.identifier,"add second resource")
		self.m.RemoveResource(r1.identifier)
		self.failUnless(len(self.m.resources)==1,"remove resource")

	def testSubManifest(self):
		"""Check that we can handle a sub-manifest"""
		self.failUnless(len(self.m.subManifests)==0,"initial sub-manifests")
		m1=Manifest(self.m)
		self.failUnless(len(self.m.subManifests)==1,"add manifest")
		m2=Manifest(self.m)
		self.failUnless(len(self.m.subManifests)==2 and m1.identifier!=m2.identifier,"add second manifest")
		self.m.RemoveManifest(m1.identifier)
		self.failUnless(len(self.m.subManifests)==1,"remove manifest")
		

class CustomMetadata:
	"""Mock object for holding metadata"""
	pass
		

if __name__ == "__main__":
	unittest.main()