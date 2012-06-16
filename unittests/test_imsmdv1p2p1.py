#! /usr/bin/env python

import unittest

from StringIO import StringIO

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(LRMTests,'test'),
		unittest.makeSuite(LRMElementTests,'test'),
		unittest.makeSuite(LRMEducationalTests,'test'),
		unittest.makeSuite(LRMDocumentTests,'test')
		))

from pyslet.imsmdv1p2p1 import *
import pyslet.imscpv1p2 as imscp

try:
	import pkg_resources
except ImportError:
	pkg_resources=None
	
if vobject is None:
	print "vobject tests skipped"
	print "\tTry installing vobject from http://vobject.skyhouseconsulting.com/  (vobject-0.8.1c)"
	print "\t\talso requires http://labix.org/python-dateutil"
elif pkg_resources:
	vv=pkg_resources.get_distribution("vobject").version
	dv=pkg_resources.get_distribution("python-dateutil").version
	if vv!='0.8.1c':
		print "Designed for vobject-0.8.1c, testing with version %s"%vv
	if dv!='1.5':
		print "Designed for python-dateutil-1.5, testing with version %s"%dv
else:
	print "\tCannot determine vobject package version, install setuptools to remove this message"

	
class LRMTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSLRM_NAMESPACE=="http://www.imsglobal.org/xsd/imsmd_v1p2","Wrong LRM namespace: %s"%IMSLRM_NAMESPACE)
		self.failUnless(len(IMSLRM_NAMESPACE_ALIASES)==2)
		for alias in IMSLRM_NAMESPACE_ALIASES:
			self.failIf(alias==IMSLRM_NAMESPACE)
		self.failUnless(IMSLRM_SCHEMALOCATION=="http://www.imsglobal.org/xsd/imsmd_v1p2p4.xsd","LRM schemaLocation: %s"%IMSLRM_SCHEMALOCATION)
		self.failUnless(LOM_SOURCE=="LOMv1.0","LOM_SOURCE")
		
	def testCaseClassMap(self):
		self.failUnless(GetElementClass((IMSLRM_NAMESPACE,'lom')) is LOM)
		for alias in IMSLRM_NAMESPACE_ALIASES:
			self.failUnless(GetElementClass((alias,'lom')) is LOM)
		self.failIf(GetElementClass(('http://www.example.com/','lom')) is LOM)
		self.failUnless(GetElementClass((IMSLRM_NAMESPACE,'x-undefined')) is LRMElement)
		
class LRMElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=LRMElement(None)
		#self.failUnless(e.ns==IMSLRM_NAMESPACE,'ns on construction')
		
EXAMPLE_1="""<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1" xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_v1p2" 
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


class LRMEducationalTests(unittest.TestCase):
	def testCaseDescription(self):
		"""We have to deal with the LRM binding's lack of multiplicity on educational description.
		That means that we need method in lists of LangStrings that allow us to add language-tagged
		text to an existing list of langstrings."""
		edu=LOMEducational(None)
		description=edu.ChildElement(Description)
		hello=description.ChildElement(description.LangStringClass)
		hello.SetValue("Hello")
		hello.SetLang('en-GB')
		ciao=description.ChildElement(description.LangStringClass)
		ciao.SetValue("Ciao")
		ciao.SetLang('it')
		helloTest=description.GetLangString('en')
		self.failUnless(helloTest.GetValue()=='Hello')
		ciaoTest=description.GetLangString('it')
		self.failUnless(ciaoTest.GetValue()=='Ciao')
		ciaoTest=description.GetLangString('it-IT')
		self.failUnless(ciaoTest.GetValue()=='Ciao')
		description.AddString('en','World')
		helloTest=description.GetLangString('en')
		self.failUnless(helloTest.GetValue()=='Hello; World')
		bonjour=description.AddString('fr','Bonjour')
		bonjourTest=description.GetLangString('fr')
		self.failUnless(bonjourTest.GetValue()=='Bonjour')
		unknown=description.AddString(None,'Hi')
		unknownTest=description.GetLangString(None)
		self.failUnless(unknownTest.GetValue()=='Hi')
		

class LRMDocumentTests(unittest.TestCase):
	def testCaseExample1(self):
		doc=imscp.ManifestDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		r=doc.GetElementByID('choice')
		self.failUnless(isinstance(list(r.Metadata.GetChildren())[0],LOM),"LOM")
		
if __name__ == "__main__":
	unittest.main()

