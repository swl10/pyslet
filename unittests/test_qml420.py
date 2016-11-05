#! /usr/bin/env python

import io
import unittest

from pyslet import qml420 as qml
from pyslet.xml import structures as xml


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(QML420Tests, 'test'),
        unittest.makeSuite(QMLDocumentTests, 'test')
    ))


EXAMPLE_1 = b"""<QUESTION ID="4123762784159489" DESCRIPTION="Yes / No"
    TOPIC="All Q Types\All questions" STATUS="Normal">
    <TAG NAME="WL Difficulty Level"><![CDATA[Not Defined]]></TAG>
    <TAG NAME="Content"><![CDATA[1.0]]></TAG>
    <TAG NAME="MKey"><![CDATA[A]]></TAG>
    <TAG NAME="Tag Name3"><![CDATA[Loud 1]]></TAG>
    <TAG NAME="Tag Name"><![CDATA[Value 1]]></TAG>
    <TAG NAME="Tag Name2"><![CDATA[Green 1]]></TAG>
    <CONTENT TYPE="text/html"><![CDATA[<P>Yes / No</P>
        <P>- Nuclear power is evil</P>]]></CONTENT>
    <ANSWER QTYPE="YN" SUBTYPE="VERT">
        <CHOICE ID="0">
            <CONTENT TYPE="text/html"><![CDATA[Yes]]></CONTENT>
        </CHOICE>
        <CHOICE ID="1">
            <CONTENT TYPE="text/html"><![CDATA[No]]></CONTENT>
        </CHOICE>
    </ANSWER>
    <OUTCOME ID="0 Yes" SCORE="5">
        <CONDITION>"0"</CONDITION>
        <CONTENT TYPE="text/html"><![CDATA[<P>Correct - </P>
            <P>Harnessing your mung bean fuel you manage to power a small
            light for a few minutes!</P>]]></CONTENT>
    </OUTCOME>
    <OUTCOME ID="1 No" SCORE="0">
        <CONDITION>"1"</CONDITION>
        <CONTENT TYPE="text/html"><![CDATA[<P>Wrong </P>
            <P>- Clean up your mess, for the next 10,000
            years!</P>]]></CONTENT>
    </OUTCOME>
</QUESTION>"""


EXAMPLE_1_OUT = """<?xml version="1.0" encoding="UTF-8"?>
<QUESTION DESCRIPTION="Yes / No" ID="4123762784159489" STATUS="Normal"
    TOPIC="All Q Types\All questions">
    <TAG NAME="WL Difficulty Level">Not Defined</TAG>
    <TAG NAME="Content">1.0</TAG>
    <TAG NAME="MKey">A</TAG>
    <TAG NAME="Tag Name3">Loud 1</TAG>
    <TAG NAME="Tag Name">Value 1</TAG>
    <TAG NAME="Tag Name2">Green 1</TAG>
    <CONTENT TYPE="text/html"><!CDATA[[<P>Yes / No</P>
        <P>- Nuclear power is evil</P>]]></CONTENT>
    <ANSWER QTYPE="YN" SUBTYPE="VERT">
        <CHOICE ID="0">
            <CONTENT TYPE="text/html"><!CDATA[[Yes]]></CONTENT>
        </CHOICE>
        <CHOICE ID="1">
            <CONTENT TYPE="text/html"><!CDATA[[No]]></CONTENT>
        </CHOICE></ANSWER>
    <OUTCOME ID="0 Yes" SCORE="5">
        <CONDITION>"0"</CONDITION>
        <CONTENT TYPE="text/html"><!CDATA[[<P>Correct - </P>
            <P>Harnessing your mung bean fuel you manage to power a
            small light for a few minutes!</P>]]></CONTENT></OUTCOME>
    <OUTCOME ID="1 No" SCORE="0">
        <CONDITION>"1"</CONDITION>
        <CONTENT TYPE="text/html"><!CDATA[[<P>Wrong </P>
            <P>- Clean up your mess, for the next 10,000
            years!</P>]]></CONTENT></OUTCOME>
</QUESTION>"""


EXAMPLE_2 = b"""<QML>
<QUESTION ID="4123762784159489" DESCRIPTION="Yes / No" TOPIC="All Q
    Types\All questions" STATUS="Normal">
    <TAG NAME="WL Difficulty Level"><![CDATA[Not Defined]]></TAG>
    <TAG NAME="Content"><![CDATA[1.0]]></TAG>
    <TAG NAME="MKey"><![CDATA[A]]></TAG>
    <TAG NAME="Tag Name3"><![CDATA[Loud 1]]></TAG>
    <TAG NAME="Tag Name"><![CDATA[Value 1]]></TAG>
    <TAG NAME="Tag Name2"><![CDATA[Green 1]]></TAG>
    <CONTENT TYPE="text/html"><![CDATA[<P>Yes / No</P>
        <P>- Nuclear power is evil</P>]]></CONTENT>
    <ANSWER QTYPE="YN" SUBTYPE="VERT">
        <CHOICE ID="0">
            <CONTENT TYPE="text/html"><![CDATA[Yes]]></CONTENT>
        </CHOICE>
        <CHOICE ID="1">
            <CONTENT TYPE="text/html"><![CDATA[No]]></CONTENT>
        </CHOICE>
    </ANSWER>
    <OUTCOME ID="0 Yes" SCORE="5">
        <CONDITION>"0"</CONDITION>
        <CONTENT TYPE="text/html"><![CDATA[<P>Correct - </P>
            <P>Harnessing your mung bean fuel you manage to power a
            small light for a few minutes!</P>]]></CONTENT>
    </OUTCOME>
    <OUTCOME ID="1 No" SCORE="0">
        <CONDITION>"1"</CONDITION>
        <CONTENT TYPE="text/html"><![CDATA[<P>Wrong </P>
            <P>- Clean up your mess, for the next 10,000
            years!</P>]]></CONTENT>
    </OUTCOME>
</QUESTION>
</QML>"""


class QML420Tests(unittest.TestCase):

    def test_basics(self):
        # q = QML
        pass


class QMLDocumentTests(unittest.TestCase):

    def test_constructor(self):
        doc = qml.QMLDocument()
        self.assertTrue(isinstance(doc, xml.Document))

    def test_example1(self):
        doc = qml.QMLDocument()
        doc.read(src=io.BytesIO(EXAMPLE_1))
        root = doc.root
        self.assertTrue(isinstance(root, qml.QMLQuestion))
        self.assertTrue(root.xmlname == 'QUESTION')
        self.assertTrue(root.qid == '4123762784159489', "QuestionID parsing")
        self.assertTrue(
            root.description == 'Yes / No', 'DescriptionString parsing')
        self.assertTrue(
            root.topic == "All Q Types\All questions", "Topic parsing")
        self.assertTrue(len(root.QMLTag) == 6, "TAG parsing")

    def test_example2(self):
        doc = qml.QMLDocument()
        doc.read(src=io.BytesIO(EXAMPLE_2))
        root = doc.root
        self.assertTrue(isinstance(root, qml.QML))
        self.assertTrue(root.xmlname == 'QML')
        # self.assertTrue(root.QTIComment.get_value()=='Example2')
        # objects=doc.root.objectList
        # self.assertTrue(len(objects)==1 and isinstance(objects[0],QTIItem))
        # self.assertTrue(len(root.objectList)==1)


if __name__ == "__main__":
    unittest.main()
