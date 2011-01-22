import unittest

from os import listdir
from os.path import join as pathjoin
from sys import exc_info
from traceback import format_tb

from StringIO import StringIO

from assessmentItem import *

def suite():
	return unittest.makeSuite(AssessmentItemTest,'test')

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


class AssessmentItemTest(unittest.TestCase):
	def testConstructor(self):
		"""Test constructor"""
		item=AssessmentItem("item001","A Test Item",0,0)
	
	def testValidTests(self):
		"""Test AssessmentItemParser class against all conformance examples"""
		p=AssessmentItemParser()
		dpath=pathjoin('testdata','valid')
		print
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			f=open(pathjoin(dpath,fName),'r')
			try:
				print fName
				item=p.ReadAssessmentItem(f)
			except:
				self.fail("AssessmentItemParser failed for %s: %s\n%s"%(fName,str(exc_info()[1]),join(format_tb(exc_info()[2]))))
			f.close()
			
	def testInvalidTests(self):
		"""Test AssessmentItemParser class against all non-conformant examples"""
		p=AssessmentItemParser()
		dpath=pathjoin('testdata','invalid')
		print
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			f=open(pathjoin(dpath,fName),'r')
			try:
				print fName
				item=p.ReadAssessmentItem(f)
				self.fail("AssessmentItemParser succeeded for %s"%fName)
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