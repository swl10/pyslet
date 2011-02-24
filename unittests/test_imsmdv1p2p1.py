#! /usr/bin/env python

import unittest

from StringIO import StringIO

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(LRMTests,'test'),
		unittest.makeSuite(LRMElementTests,'test'),
		unittest.makeSuite(LRMDocumentTests,'test')
		))

from pyslet.imsmdv1p2p1 import *
import pyslet.imscpv1p2 as imscp

class LRMTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSLRM_NAMESPACE=="http://www.imsglobal.org/xsd/imsmd_v1p2","Wrong LRM namespace: %s"%IMSLRM_NAMESPACE)
		self.failUnless(len(IMSLRM_NAMESPACE_ALIASES)==2)
		for alias in IMSLRM_NAMESPACE_ALIASES:
			self.failIf(alias==IMSLRM_NAMESPACE)
		self.failUnless(IMSLRM_SCHEMALOCATION=="http://www.imsglobal.org/xsd/imsmd_v1p2p4.xsd","LRM schemaLocation: %s"%IMSLRM_SCHEMALOCATION)

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


class LRMDocumentTests(unittest.TestCase):
	def testCaseExample1(self):
		doc=imscp.CPDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		r=doc.GetElementByID('choice')
		self.failUnless(isinstance(r.metadata.GetChildren()[0],LOM),"LOM")
		
if __name__ == "__main__":
	unittest.main()

