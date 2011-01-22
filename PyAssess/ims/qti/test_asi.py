import unittest

from os import listdir
from os.path import join as pathjoin
from sys import exc_info
from traceback import format_tb

from StringIO import StringIO

from asi import *
from session import ItemSession

from PyAssess.w3c.xml import XMLFile

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(AssessmentTestTest),
		unittest.makeSuite(AssessmentItemTest)
		))

SAMPLE_ITEM="""<?xml version="1.0" encoding="UTF-8"?>
<!-- This example adapted from the PET Handbook, copyright University of Cambridge ESOL Examinations -->
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p0 imsqti_v2p0.xsd"
    identifier="choice" title="Unattended Luggage" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
        <correctResponse>
            <value>ChoiceA</value>
        </correctResponse>
    </responseDeclaration>
    <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="integer">
        <defaultValue>
            <value>0</value>
        </defaultValue>
    </outcomeDeclaration>
    <itemBody>
        <p>Look at the text in the picture.</p>
        <p>
            <img src="images/sign.png" alt="NEVER LEAVE LUGGAGE UNATTENDED"/>
        </p>
        <choiceInteraction responseIdentifier="RESPONSE" shuffle="false" maxChoices="1">
            <prompt>What does it say?</prompt>
            <simpleChoice identifier="ChoiceA">You must stay with your luggage at all times.</simpleChoice>
            <simpleChoice identifier="ChoiceB">Do not let someone else look after your luggage.</simpleChoice>
            <simpleChoice identifier="ChoiceC">Remember your luggage when you leave.</simpleChoice>
        </choiceInteraction>
    </itemBody>
    <responseProcessing
        template="http://www.imsglobal.org/question/qti_v2p0/rptemplates/match_correct"/>
</assessmentItem>"""


class AssessmentTestTest(unittest.TestCase):
	pass


class AssessmentItemTest(unittest.TestCase):
	def testConstructor(self):
		"""Test constructor"""
		item=AssessmentItem("item001","A Test Item",0,0)
	
	def testValidTests(self):
		"""Test AssessmentItemParser class against all conformance examples"""
		p=AssessmentItemParser()
		dpath=pathjoin('testdata','valid')
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			f=open(pathjoin(dpath,fName),'r')
			inputData=f.read()
			try:
				fInput=StringIO(inputData)
				item=p.ReadAssessmentItem(fInput)
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
			
	def testInvalidTests(self):
		"""Test AssessmentItemParser class against all non-conformant examples"""
		p=AssessmentItemParser()
		dpath=pathjoin('testdata','invalid')
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			f=open(pathjoin(dpath,fName),'r')
			try:
				item=p.ReadAssessmentItem(f)
				self.fail("AssessmentItemParser succeeded for %s"%fName)
			except IMSQTIError:
				pass
			f.close()
			
	def testRTETests(self):
		"""Test AssessmentItem class against all run-time exception examples"""
		p=AssessmentItemParser()
		dpath=pathjoin('testdata','rte')
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			f=open(pathjoin(dpath,fName),'r')
			item=p.ReadAssessmentItem(f)
			try:
					session=ItemSession(item)
					session.BeginAttempt()
					session.EndAttempt()
					self.fail("AssessmentItem succeeded for %s"%fName)
			except IMSQTIError:
				pass
			f.close()
			
	def testParser(self):
		p=AssessmentItemParser()
		item=p.ReadAssessmentItem(StringIO(SAMPLE_ITEM))
		self.failUnless(isinstance(item.LookupVariableDeclaration('RESPONSE'),ResponseDeclaration),
			"RESPONSE declaration")

if __name__ == "__main__":
	unittest.main()