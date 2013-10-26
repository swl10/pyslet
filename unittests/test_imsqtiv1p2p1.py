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
import codecs, os, os.path

class QTITests(unittest.TestCase):
	def testCaseConstants(self):
		#self.assertTrue(IMSQTI_NAMESPACE=="http://www.imsglobal.org/xsd/ims_qtiasiv1p2","Wrong QTI namespace: %s"%IMSQTI_NAMESPACE)
		pass

	def testCaseNCNameFixup(self):
		self.assertTrue(MakeValidName("Simple")=="Simple")
		self.assertTrue(MakeValidName(":BadNCName")==":BadNCName")
		self.assertTrue(MakeValidName("prefix:BadNCName")=="prefix:BadNCName")
		self.assertTrue(MakeValidName("_GoodNCName")=="_GoodNCName")
		self.assertTrue(MakeValidName("-BadName")=="_-BadName")
		self.assertTrue(MakeValidName(".BadName")=="_.BadName")
		self.assertTrue(MakeValidName("0BadName")=="_0BadName")
		self.assertTrue(MakeValidName("GoodName-0.12")=="GoodName-0.12")
		self.assertTrue(MakeValidName("BadName$")=="BadName_")
		self.assertTrue(MakeValidName("BadName+")=="BadName_")
		
class QTIElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=QTIElement(None)

	def testCaseQuesTestInterop(self):
		e=QuesTestInterop(None)
		self.assertTrue(e.QTIComment is None)
		self.assertTrue(e.ObjectBank is None)
		self.assertTrue(e.Assessment is None)
		self.assertTrue(e.ObjectMixin==[])
		

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
	def setUp(self):
		self.cwd=os.getcwd()
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_imsqtiv1p2p1')
		os.chdir(self.dataPath)
		
	def tearDown(self):
		os.chdir(self.cwd)

	def testCaseConstructor(self):
		doc=QTIDocument()
		self.assertTrue(isinstance(doc,xml.Document))

	def testCaseExample1(self):
		doc=QTIDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		root=doc.root
		self.assertTrue(isinstance(root,QuesTestInterop))
		self.assertTrue(root.xmlname=='questestinterop')
		
	def testCaseExample2(self):
		doc=QTIDocument()
		doc.Read(src=StringIO(EXAMPLE_2))
		root=doc.root
		self.assertTrue(root.QTIComment.GetValue()=='Example2')
		objects=doc.root.ObjectMixin
		self.assertTrue(len(objects)==1 and isinstance(objects[0],Item))
		self.assertTrue(len(root.ObjectMixin)==1)
	

class QTIV2ConversionTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_imsqtiv1p2p1')
		self.cp=imscp.ContentPackage()
		
	def tearDown(self):
		self.cp.Close()
		os.chdir(self.cwd)
	
	def testCaseOutputV2(self):
		self.cp.manifest.root.SetID('outputv2')
		dPath=os.path.join(self.dataPath,'input')
		for f in os.listdir(dPath):
			if self.cp.IgnoreFile(f):
				continue
			stem,ext=os.path.splitext(f)
			if ext.lower()=='.xml':
				doc=QTIDocument(baseURI=str(uri.URIFactory.URLFromPathname(os.path.join(dPath,f))))
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
		if fList1!=fList2:
			diagnosis=[]
			for f in fList1:
				if f not in fList2:
					diagnosis.append("Extra file found: %s"%f)
			for f in fList2:
				if f not in fList1:
					diagnosis.append("Missing file: %s"%f)
			self.fail("File lists:\n  %s"%string.join(diagnosis,'\n  '))
		output=self.cp.manifest.DiffString(cp2.manifest)
		self.assertTrue(self.cp.manifest.root==cp2.manifest.root,"Manifests differ:\n%s"%output)
		checkFiles={}
		for r in cp2.manifest.root.Resources.Resource:
			# Check the entry-point of each resource
			f=r.GetEntryPoint()
			if f:
				fPath=f.PackagePath(cp2)
				qtiDoc=qtiv2.core.QTIDocument(baseURI=str(uri.URIFactory.URLFromVirtualFilePath(self.cp.dPath.join(fPath))))
				qtiDoc.Read()
				#print str(qtiDoc)
				qtiDoc2=qtiv2.core.QTIDocument(baseURI=str(uri.URIFactory.URLFromVirtualFilePath(cp2.dPath.join(fPath))))
				qtiDoc2.Read()
				#print str(qtiDoc2)
				output=qtiDoc.DiffString(qtiDoc2)
				result=(qtiDoc.root==qtiDoc2.root)
				if not result and output is None:
					# This should not happen
					self.PrintPrettyWeird(qtiDoc.root,qtiDoc2.root)
				self.assertTrue(qtiDoc.root==qtiDoc2.root,"QTI Files differ at %s (actual output shown first)\n%s"%(fPath,output))	
			for f in r.File:
				if f.href is None or f.href.IsAbsolute():
					continue
				fPath=f.PackagePath(cp2)
				fAbsPath=self.cp.dPath.join(fPath)
				fAbsPath2=cp2.dPath.join(fPath)
				baseURI=str(uri.URIFactory.URLFromVirtualFilePath(fAbsPath))
				baseURI2=str(uri.URIFactory.URLFromVirtualFilePath(fAbsPath2))
				if fAbsPath.splitext()[1].lower()=='.xml':
					# Two xml files, compare with simple XMLElement
					doc=xml.Document(baseURI=baseURI)
					doc.Read()
					doc2=xml.Document(baseURI=baseURI2)
					doc2.Read()
					output=doc.DiffString(doc2)
					result=(doc.root==doc2.root)
					if not result and output is None:
						# This should not happen
						self.PrintPrettyWeird(doc.root,doc2.root)
					self.assertTrue(doc.root==doc2.root,"XML Files differ at %s (actual output shown first)\n%s"%(fPath,output))	
				else:
					# Binary compare the two files.
					f=fAbsPath.open('rb')
					f2=fAbsPath2.open('rb')
					while True:
						fData=f.read(1024)
						fData2=f2.read(1024)
						self.assertTrue(fData==fData2,"Binary files don't match: %s"%fPath)
						if not fData:
							break							
				
				
	def PrintPrettyWeird(self,e1,e2):
		c1=e1.GetCanonicalChildren()
		c2=e2.GetCanonicalChildren()
		if len(c1)!=len(c2):
			print "Number of children mismatch in similar elements...\n>>>\n%s\n>>>\n%s\n>>>\n%s"%(repr(c1),repr(c2),str(e1))
			return
		for i in xrange(len(c1)):
			if c1[i]!=c2[i]:
				if isinstance(c1[i],xml.XMLElement) and isinstance(c2[i],xml.XMLElement):
					self.PrintPrettyWeird(c1[i],c2[i])
				else:
					print "Mismatch in similar elements...\n>>>\n%s\n>>>\n%s"%(repr(e1),repr(e2))
			
class QTIBig5Tests(unittest.TestCase):
	def testCaseBIG5(self):
		big5=codecs.lookup('big5')
		try:
			cnbig5=codecs.lookup('CN-BIG5')
			pass
		except LookupError:
			self.fail("CN-BIG5 registration failed")
			
		

if __name__ == "__main__":
	unittest.main()

