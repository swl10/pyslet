#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(QTITests,'test'),
		unittest.makeSuite(QTIElementTests,'test'),
		unittest.makeSuite(QTIDocumentTests,'test')
		))

from pyslet.imsqtiv1p2p1 import *

from StringIO import StringIO
import codecs

class QTITests(unittest.TestCase):
	def testCaseConstants(self):
		#self.failUnless(IMSQTI_NAMESPACE=="http://www.imsglobal.org/xsd/ims_qtiasiv1p2","Wrong QTI namespace: %s"%IMSQTI_NAMESPACE)
		pass

	def testCaseNCNameFixup(self):
		self.failUnless(MakeValidName("Simple")=="Simple")
		self.failUnless(MakeValidName(":BadNCName")==":BadNCName")
		self.failUnless(MakeValidName("prefix:BadNCName")=="prefix:BadNCName")
		self.failUnless(MakeValidName("_GoodNCName")=="_GoodNCName")
		self.failUnless(MakeValidName("-BadName")=="_-BadName")
		self.failUnless(MakeValidName(".BadName")=="_.BadName")
		self.failUnless(MakeValidName("0BadName")=="_0BadName")
		self.failUnless(MakeValidName("GoodName-0.12")=="GoodName-0.12")
		self.failUnless(MakeValidName("BadName$")=="BadName_")
		self.failUnless(MakeValidName("BadName+")=="BadName_")
		
class QTIElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=QTIElement(None)

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

class QTIDocumentTests(unittest.TestCase):
	def testCaseConstructor(self):
		doc=QTIDocument()
		self.failUnless(isinstance(doc,xml.XMLDocument))

	def testCaseExample1(self):
		doc=QTIDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		root=doc.rootElement
		self.failUnless(isinstance(root,QTIQuesTestInterop))
		self.failUnless(root.xmlname=='questestinterop')

	def testCaseExample2(self):
		doc=QTIDocument()
		doc.Read(src=StringIO(EXAMPLE_2))
		objects=doc.rootElement.GetObjectList()
		self.failUnless(len(objects)==1 and isinstance(objects[0],QTIItem))
	

class QTIBig5Tests(unittest.TestCase):
	def testCaseBIG5(self):
		try:
			big5=codecs.lookup('CN-BIG5')
			self.fail("CN-BIG5 already declared: stale test?")
			big5=codecs.lookup('big5')
		except codecs.LookupError:
			pass
		FixupCNBig5()
		try:
			cnbig5=codecs.lookup('CN-BIG5')
			self.failUnless(cnbig5 is big5,"Big5 mismatch")
		except codecs.LookupError:
			self.fail("CN-BIG5 registration failed")
			
		

if __name__ == "__main__":
	unittest.main()

