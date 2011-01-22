import unittest

from StringIO import StringIO

from deliveryEngine import *
from assessmentItem import AssessmentItemParser
from session import ItemSession

def suite():
	return unittest.makeSuite(TextEngineTest,'test')

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

SAMPLE_OUTPUT_1="""Look at the text in the picture.

NEVER LEAVE LUGGAGE UNATTENDED

What does it say?

[1 ] You must stay with your luggage at all times.
[2 ] Do not let someone else look after your luggage.
[3 ] Remember your luggage when you leave.
"""

SAMPLE_OUTPUT_2="""Look at the text in the picture.

NEVER LEAVE LUGGAGE UNATTENDED

What does it say?

[1*] You must stay with your luggage at all times.
[2 ] Do not let someone else look after your luggage.
[3 ] Remember your luggage when you leave.
"""

SAMPLE_OUTPUT_3="""Look at the text in the picture.

NEVER LEAVE LUGGAGE UNATTENDED

What does it say?

[1 ] You must stay with your luggage at all times.
[2 ] Do not let someone else look after your luggage.
[3*] Remember your luggage when you leave.
"""

class TextEngineTest(unittest.TestCase):

	def testRender(self):
		"""Check the text-based delivery engine"""
		p=AssessmentItemParser()
		item=p.ReadAssessmentItem(StringIO(SAMPLE_ITEM))
		session=ItemSession(item)
		fOut=StringIO()
		view=TextItemView(session,fOut)
		item.RenderBody(view)
		self.failUnless(fOut.getvalue()==SAMPLE_OUTPUT_1,"Sample rendering 1: %s"%fOut.getvalue())
		view.DoAction(["1"])
		fOut.truncate(0)
		item.RenderBody(view)
		self.failUnless(fOut.getvalue()==SAMPLE_OUTPUT_2,"Sample rendering 2: %s"%fOut.getvalue())
		view.DoAction(["3"])
		fOut.truncate(0)
		item.RenderBody(view)
		self.failUnless(fOut.getvalue()==SAMPLE_OUTPUT_3,"Sample rendering 3: %s"%fOut.getvalue())
		
if __name__ == "__main__":
	unittest.main()