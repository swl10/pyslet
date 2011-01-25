#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(QTITests,'test'),
		unittest.makeSuite(QTIElementTests,'test'),
		unittest.makeSuite(QTIParserTests,'test')
		))

from pyslet.imsqtiv1p2p1 import *

class QTITests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSQTI_NAMESPACE=="http://www.imsglobal.org/xsd/ims_qtiasiv1p2","Wrong QTI namespace: %s"%IMSQTI_NAMESPACE)

class QTIElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=QTIElement(None)
		self.failUnless(e.ns==IMSQTI_NAMESPACE,'ns on construction')

	def testCaseQuesTestInterop(self):
		e=QTIQuesTestInterop(None)
		self.failUnless(e.GetComment() is None)
		self.failUnless(e.GetObjectBank() is None)
		self.failUnless(e.GetAssessment() is None)
		self.failUnless(e.GetObjectList()==[])
		

EXAMPLE_1="""<?xml version="1.0" encoding="utf-8"?>
<questestinterop></questestinterop>"""

EXAMPLE_2="""<?xml version = "1.0" encoding = "UTF-8" standalone = "no"?>
<!DOCTYPE questestinterop SYSTEM "ims_qtiasiv1p2p1.dtd">
<questestinterop>
	<qticomment>Example2</qticomment>  
	<item title = "Multiple Choice Item" ident = "EXAMPLE_002">    
		<presentation label = "EXAMPLE_002">
			<flow>
				<material>        
					<mattext>What is the answer to the question?</mattext>      
				</material>
				<response_lid ident = "RESPONSE" rcardinality = "Single" rtiming = "No">        
					<render_choice shuffle = "Yes">
						<flow_label>        
							<response_label ident = "A">
								<material>
									<mattext>Yes</mattext>
								</material>
							</response_label>
						</flow_label>
						<flow_label>        
							<response_label ident = "B"> 
								<material>
									<mattext>No</mattext>
								</material>        
							</response_label>
						</flow_label>
						<flow_label>        
							<response_label ident = "C"> 
								<material>
									<mattext>Maybe</mattext>
								</material>        
							</response_label>
						</flow_label>
					</render_choice>      
				</response_lid>
			</flow>                
		</presentation>  
	</item>
</questestinterop>"""

class QTIParserTests(unittest.TestCase):
	def testCaseConstructor(self):
		p=QTIParser()

	def testCaseExample1(self):
		p=QTIParser()
		doc=p.ParseDocument(EXAMPLE_1)
		self.failUnless(isinstance(doc,xml.XMLDocument))
		root=doc.rootElement
		self.failUnless(isinstance(root,QTIQuesTestInterop))
		self.failUnless(root.ns==IMSQTI_NAMESPACE and root.xmlname=='questestinterop')

	def testCaseExample1(self):
		p=QTIParser()
		doc=p.ParseDocument(EXAMPLE_2)
		objects=doc.rootElement.GetObjectList()
		self.failUnless(len(objects)==1 and isinstance(objects[0],QTIItem))
	

if __name__ == "__main__":
	unittest.main()

