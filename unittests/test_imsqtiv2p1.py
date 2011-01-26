#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(QTITests,'test'),
		unittest.makeSuite(QTIElementTests,'test'),
		unittest.makeSuite(QTIParserTests,'test')
		))

from pyslet.imsqtiv2p1 import *

class QTITests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(IMSQTI_NAMESPACE=="http://www.imsglobal.org/xsd/imsqti_v2p1","Wrong QTI namespace: %s"%IMSQTI_NAMESPACE)

class QTIElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=QTIElement(None)
		self.failUnless(e.ns==IMSQTI_NAMESPACE,'ns on construction')
		

EXAMPLE_1="""<?xml version="1.0" encoding="utf-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="test"></assessmentItem>"""

EXAMPLE_2="""<?xml version="1.0" encoding="UTF-8"?>
<!-- Thie example adapted from the PET Handbook, copyright University of Cambridge ESOL Examinations -->
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
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
    <responseProcessing template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct"/>
</assessmentItem>
"""

class QTIParserTests(unittest.TestCase):
	def testCaseConstructor(self):
		p=QTIParser()

	def testCaseExample1(self):
		p=QTIParser()
		doc=p.ParseDocument(EXAMPLE_1)
		self.failUnless(isinstance(doc,xml.XMLDocument))
		root=doc.rootElement
		self.failUnless(isinstance(root,QTIAssessmentItem))
		self.failUnless(root.ns==IMSQTI_NAMESPACE and root.xmlname=='assessmentItem')

	def testCaseExample1(self):
		p=QTIParser()
		doc=p.ParseDocument(EXAMPLE_2)
		vardefs=doc.rootElement.GetDeclarations()
		self.failUnless(len(vardefs.keys())==1 and isinstance(vardefs['RESPONSE'],QTIResponseDeclaration))
	

if __name__ == "__main__":
	unittest.main()

