#! /usr/bin/env python

import unittest
import os.path, urllib, urlparse

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CPTests,'test'),
		unittest.makeSuite(CPElementTests,'test'),
		unittest.makeSuite(CPManifestTests,'test'),
		unittest.makeSuite(CPParserTests,'test'),
		unittest.makeSuite(ContentPackageTests,'test'),
		))

from pyslet.imscpv1p2 import *

class CPTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSCP_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_v1p1","Wrong CP namespace: %s"%IMSCP_NAMESPACE)
		self.failUnless(IMSCPX_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_extensionv1p2","Wrong extension namespace: %s"%IMSCPX_NAMESPACE)

class CPElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=CPElement(None)
		self.failUnless(e.ns==IMSCP_NAMESPACE,'ns on construction')
		
class CPXElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=CPXElement(None)
		self.failUnless(e.ns==IMSCPX_NAMESPACE,'ns on construction')

class CPManifestTests(unittest.TestCase):
	def testCaseConstructor(self):
		m=CPManifest(None)
		self.failUnless(m.GetMetadata() is None,"Metadata present on construction")
		self.failUnless(isinstance(m.GetOrganizations(),CPOrganizations),"Organizations element required on construction")
		self.failUnless(isinstance(m.GetResources(),CPResources),"Resources element required on construction")
		self.failUnless(len(m.GetChildren())==0,"Child manifests present on construction")
		

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

class CPParserTests(unittest.TestCase):
	def testCaseConstructor(self):
		p=CPParser()

	def testCaseExample1(self):
		p=CPParser()
		doc=p.ParseDocument(EXAMPLE_1)
		self.failUnless(isinstance(doc,xml.XMLDocument))
		root=doc.rootElement
		self.failUnless(isinstance(root,CPManifest))
		self.failUnless(root.ns==IMSCP_NAMESPACE and root.xmlname=='manifest')

	def testCaseExample1(self):
		p=CPParser()
		doc=p.ParseDocument(EXAMPLE_2)
		resources=doc.rootElement.GetResources()
		self.failUnless(len(resources.children)==1 and isinstance(resources.children[0],CPResource))


class ContentPackageTests(unittest.TestCase):
	def testCaseConstructor(self):
		cp=ContentPackage()
		self.failUnless(os.path.isdir(cp.dPath),"Default constructor must create a temp directory")
		url=urlparse.urlsplit(cp.manifest.GetBase())
		self.failUnless(isinstance(cp.manifest,xml.XMLDocument) and isinstance(cp.manifest.rootElement,CPManifest),"Constructor must create manifest")
		self.failUnless(os.path.split(urllib.url2pathname(url.path))[1]=='imsmanifest.xml',"Manifest file name")
		self.failUnless(isinstance(cp.manifest.rootElement,CPManifest),"Constructor must create manifest element")
		self.failUnless(os.path.isfile(urllib.url2pathname(url.path)),"Constructor must create manifest file")

if __name__ == "__main__":
	unittest.main()

