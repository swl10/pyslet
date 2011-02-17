#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(QTITests,'test'),
		unittest.makeSuite(QTIElementTests,'test'),
		unittest.makeSuite(QTIDocumentTests,'test'),
		unittest.makeSuite(QTIV2ConversionTests,'test')
		))

from pyslet.imsqtiv1p2p1 import *
import pyslet.imscpv1p2 as imscp

from StringIO import StringIO
import codecs, os, os.path, urllib

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
		root=doc.rootElement
		self.failUnless(root.GetComment().GetValue()=='Example2')
		objects=doc.rootElement.GetObjectList()
		self.failUnless(len(objects)==1 and isinstance(objects[0],QTIItem))
		self.failUnless(len(root.objectList)==1)
	

class QTIV2ConversionTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_imsqtiv1p2p1')
		self.cp=imscp.ContentPackage()
		
	def tearDown(self):
		self.cp.Close()
		os.chdir(self.cwd)
	
	def testCaseOutputV2(self):
		self.cp.manifest.rootElement.SetIdentifier('outputv2')
		dPath=os.path.join(self.dataPath,'input')
		for f in os.listdir(dPath):
			if self.cp.IgnoreFile(f):
				continue
			stem,ext=os.path.splitext(f)
			if ext.lower()=='.xml':
				doc=QTIDocument(baseURI=urllib.pathname2url(os.path.join(dPath,f)))
				doc.Read()
				doc.MigrateV2(self.cp)
		# Having migrated everything in the input folder, we now check our CP against the output
		cp2=imscp.ContentPackage(os.path.join(self.dataPath,'outputv2'))
		# To do....
		# Compare the manifests
		# Compare each file
		fList1=self.cp.fileTable.keys()
		fList1.sort()
		fList2=cp2.fileTable.keys()
		fList2.sort()
		self.failUnless(fList1==fList2)
		output=str(self.cp.manifest)
		outputDesired=str(cp2.manifest)
		self.failUnless(self.cp.manifest.rootElement==cp2.manifest.rootElement,"Output manifest:\n%s\n\nInput manifest:\n%s"%(output,outputDesired))
		checkFiles={}
		for r in cp2.manifest.rootElement.resources.list:
			# Check the entry-point of each resource
			f=r.GetEntryPoint()
			if f:
				fPath=f.PackagePath(cp2)				
				qtiDoc=qtiv2.QTIDocument(baseURI='file://'+urllib.pathname2url(os.path.join(self.cp.dPath,fPath)))
				qtiDoc.Read()
				qtiDoc2=qtiv2.QTIDocument(baseURI='file://'+urllib.pathname2url(os.path.join(cp2.dPath,fPath)))
				qtiDoc2.Read()
				output=str(qtiDoc)
				outputDesired=str(qtiDoc2)
				self.failUnless(qtiDoc.rootElement==qtiDoc2.rootElement,"Output manifest:\n%s\n\nInput manifest:\n%s"%(output,outputDesired))	

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

