import unittest
from os import listdir
from os.path import join as pathjoin, isfile
from StringIO import StringIO
from string import split

from PyAssess.w3c.xml import XMLFile
from PyAssess.ims.md import WriteLRMXML
from PyAssess.ieee.p1484_12 import LOMMetadata
from questestinterop import *

def suite():
	return unittest.makeSuite(QuestestinteropTest,'test')

def ObjectToXML(qtiObject):
	output=StringIO()
	xf=XMLFile(output)
	if isinstance(qtiObject,LOMMetadata):
		WriteLRMXML(xf,qtiObject)
	else:
		qtiObject.WriteXML(xf)
	return output.getvalue()
	
class QuestestinteropTest(unittest.TestCase):
	def testParser(self):
		p=QuestestinteropParser()
		fPath=pathjoin('testdata','migration','questestinterop-in.xml')
		result=p.ReadQuestestinterop(file(fPath))
		output=map(ObjectToXML,result)
		for i in range(len(output)):
			fPath=pathjoin('testdata','migration','questestinterop-out'+str(i)+'.xml')
			inSplit=split(file(fPath).read())
			outSplit=split(output[i])
			if not inSplit==outSplit:
				print "Migration failure in %s, first difference follows..."%fPath
				for i in xrange(len(inSplit)):
					if inSplit[i]!=outSplit[i]:
						print "\n\nInput: \n"+join(inSplit[i:],' ')
						print "\n\nOutput: \n"+join(outSplit[i:],' ')
						break
				self.fail("Migration: output for %s did not match input data"%fPath)
		fPath=pathjoin('testdata','migration','questestinterop-out'+str(len(output))+'.xml')
		self.failIf(isfile(fPath),"Migration: no output created for %s"%fPath)
			
	def testValidTests(self):
		"""Test AssessmentItemParser class against all conformance examples"""
		p=QuestestinteropParser()
		dpath=pathjoin('testdata','questestinterop')
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			f=open(pathjoin(dpath,fName),'r')
			inputData=f.read()
			try:
				fInput=StringIO(inputData)
				item=p.ReadQuestestinterop(fInput)
				if "responseRules" in fName:
					session=ItemSession(item)
					session.BeginAttempt()
					session.EndAttempt()
					score=session.GetOutcomeValue('SCORE')[2]
					self.failUnless(score==1,"%s: SCORE=%s"%(fName,str(score)))
				fOutput=StringIO()
				item.WriteXML(XMLFile(fOutput))
				inSplit=split(fInput.getvalue())
				outSplit=split(fOutput.getvalue())
				if not inSplit==outSplit:
					for i in xrange(len(inSplit)):
						if inSplit[i]!=outSplit[i]:
							print "\n\nInput: \n"+join(inSplit[i:],' ')
							print "\n\nOutput: \n"+join(outSplit[i:],' ')
							break
				self.failUnless(split(fOutput.getvalue())==split(fInput.getvalue()),
					"WriteXML: output for %s did not match input data"%item.identifier)
			except:
				self.fail("AssessmentItemParser failed for %s: %s\n%s"%(fName,str(exc_info()[1]),join(format_tb(exc_info()[2]))))
			f.close()

if __name__ == "__main__":
	unittest.main()