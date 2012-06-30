#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(QTITests,'test'),
		unittest.makeSuite(ValueTests,'test'),
		unittest.makeSuite(QTIElementTests,'test'),
		unittest.makeSuite(VariableTests,'test'),
		unittest.makeSuite(QTIDocumentTests,'test')
		))

from pyslet.imsqtiv2p1 import *

from StringIO import StringIO
import types

class QTITests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(core.IMSQTI_NAMESPACE=="http://www.imsglobal.org/xsd/imsqti_v2p1","Wrong QTI namespace: %s"%core.IMSQTI_NAMESPACE)
		self.failUnless(core.IMSQTI_ITEM_RESOURCETYPE=="imsqti_item_xmlv2p1","Wrong QTI resource type: %s"%core.IMSQTI_ITEM_RESOURCETYPE)

class ValueTests(unittest.TestCase):
	def testCaseNULL(self):
		v=variables.Value()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failIf(v,"Null zero/false test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is None,"BaseType should be unknown on default constructor.")
		v=variables.StringValue()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.string,"NULL value with known type.")
		v.SetValue("x")
		self.failUnless(not v.IsNull(),"Null test with value")
		self.failUnless(v,"Null zero/false test on creation.")
		v.SetValue(None)
		self.failUnless(v.IsNull(),"Null test with Non value")
		self.failIf(v,"Null zero/false test with Non value.")
		self.failUnless(v.baseType is variables.BaseType.string,"NULL value retains known type.")
		
	def testCaseIdentifier(self):
		v=variables.IdentifierValue()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failIf(v,"Null zero/false test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.identifier,"baseType on creation")
		for vIn in ('name','goodName'):
			v.SetValue(vIn)
			self.failUnless(type(v.value) is types.UnicodeType,"Value type on set")
			self.failUnless(v.value==vIn,"Good strings")
		for vIn in ('1','.Name'):
			try:
				v.SetValue(vIn)
				self.fail("Error string: %s"%vIn)
			except ValueError:
				pass
		try:
			v.SetValue(".Name",False)
		except ValueError:
			self.fail("Bad name with nameCheck=False")
			
	def testCaseBoolean(self):
		v=variables.BooleanValue()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.boolean,"baseType on creation")
		for vIn in ('true','1',True,1,2L):
			v.SetValue(vIn)
			self.failUnless(v.value is True,"True values")
		for vIn in ('false','0',False,0,0L):
			v.SetValue(vIn)
			self.failUnless(v.value is False,"False values")
		for vIn in ('True','Yes',"FALSE","2",3.14):
			try:
				v.SetValue(vIn)
				self.fail("Error string: %s"%repr(vIn))
			except ValueError:
				pass

	def testCaseInteger(self):
		v=variables.IntegerValue()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.integer,"baseType on creation")
		for vIn in ('1','-2',3,4L,'+0'):
			v.SetValue(vIn)
			self.failUnless(type(v.value) is types.IntType,"Value type on set: %s"%repr(type(v.value)))
			self.failUnless(v.value==int(vIn),"Good strings")
		for vIn in ('1.3','pi',3.14,'2+2'):
			try:
				v.SetValue(vIn)
				self.fail("Error string: %s"%vIn)
			except ValueError:
				pass

	def testCaseFloat(self):
		for t in (variables.BaseType.float,variables.BaseType.duration):
			v=variables.FloatValue() if t is variables.BaseType.float else variables.DurationValue()
			self.failUnless(v.IsNull(),"Null test on creation.")
			self.failUnless(v.value is None,"Value should be None")
			self.failUnless(v.baseType is t,"baseType on creation")
			for vIn in ('1','-2',3.141,4.0,'2.','+2','1E4'):
				v.SetValue(vIn)
				self.failUnless(type(v.value) is types.FloatType,"Value type on set: %s"%repr(type(v.value)))
				self.failUnless(v.value==float(vIn),"Good strings")
			for vIn in (' 1.3','pi','.','1E','1.3 ','2+2'):
				try:
					v.SetValue(vIn)
					self.fail("Error string: %s"%repr(vIn))
				except ValueError:
					pass

	def testCaseString(self):
		v=variables.StringValue()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.string,"baseType on creation")
		# Empty containers and empty strings are always treated as NULL values.
		v.SetValue('')
		self.failUnless(v.IsNull(),"Null test with empty string.")		
		for vIn in ('1','-2','2.','+2',u'Hello',"Bye"):
			v.SetValue(vIn)
			self.failUnless(type(v.value) is types.UnicodeType,"Value type on set: %s"%repr(type(v.value)))
			self.failUnless(v.value==vIn,"Good strings")
		for vIn in (3.141,4.0,1):
			try:
				v.SetValue(vIn)
				self.fail("Error string: %s"%repr(vIn))
			except ValueError:
				pass
		
	def testCasePoint(self):
		v=variables.PointValue()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.point,"baseType on creation")
		for vIn in ('1 2','4 -2',(3,4),[-1,4L],'+0 -0'):
			v.SetValue(vIn)
			self.failUnless(type(v.value) is types.TupleType,"Value type on set: %s"%repr(type(v.value)))
			self.failUnless(len(v.value)==2,"Good strings")
			self.failUnless(type(v.value[0])==type(v.value[1]) and type(v.value[0])==types.IntType,"Good point! %s"%repr(v.value))
		for vIn in ('1.3 1','pi',3,'2+2',(1,2,3),{1:True,2:True}):
			try:
				v.SetValue(vIn)
				self.fail("Error string: %s"%vIn)
			except ValueError:
				pass

	def testCasePairs(self):
		dpPass=False
		for t in (variables.BaseType.pair,variables.BaseType.directedPair):
			v=variables.PairValue() if t is variables.BaseType.pair else variables.DirectedPairValue()
			self.failUnless(v.IsNull(),"Null test on creation.")
			self.failUnless(v.value is None,"Value should be None")
			self.failUnless(v.baseType is t,"baseType on creation")
			for vIn in (('nameB','nameA'),"goodName badName",["A","B"]):
				v.SetValue(vIn)
				self.failUnless(type(v.value) is types.TupleType,"Value type on set")
				self.failUnless(len(v.value)==2,"Good identifiers")
				self.failUnless(type(v.value[0])==type(v.value[1]) and type(v.value[0])==types.UnicodeType,
					"Good identifiers! %s"%repr(v.value))
				if t==variables.BaseType.pair:
					self.failUnless(v.value[0]<v.value[1],"Pair ordering: %s"%repr(v.value))
				elif v.value[0]>v.value[1]:
					dpPass=True
			for vIn in ('1 2','.NameA .NameB',(1,"A"),["a","b","c"]):
				try:
					v.SetValue(vIn)
					self.fail("Error string: %s"%vIn)
				except ValueError:
					pass
			try:
				v.SetValue((".NameA",".NameB"),False)
			except ValueError:
				self.fail("nameCheck=False parsing from tuple")
			try:
				v.SetValue(".NameA .NameB",False)
				self.fail("nameCheck=False parsing from string")
			except ValueError:
				pass		
		self.failUnless(dpPass,"directedPair ordering!")


	def testCaseOrdred(self):
		v=variables.OrderedContainer()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is None,"baseType is unknown on creation")
		v=variables.OrderedContainer(variables.BaseType.identifier)
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.identifier,"baseType forced on creation")
		v.SetValue([],variables.BaseType.string)
		self.failUnless(v.IsNull(),"Null test on empty list.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType==variables.BaseType.string,"baseType is unknown on empty list")
		v.SetValue([None],None)
		self.failUnless(v.IsNull(),"Null test on list with a single NULL value.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.string,"baseType inherited when unspecified")
		v.SetValue(["A","B",None],variables.BaseType.identifier)
		self.failIf(v.IsNull(),"Null test on non-empty list.")
		self.failUnless(type(v.value)==types.ListType,"Value should be a list")
		self.failUnless(v.baseType is variables.BaseType.identifier,"baseType from list")
		self.failUnless(len(v.value)==2,"NULL value should be ignored by SetValue")
		self.failUnless(v.value[1]==u"B","value on set")
		v.SetValue((u"C",u"D"),variables.BaseType.string)
		self.failUnless(v.value[1]==u"D","set from tuple")		
		try:
			v.SetValue(["A",3],variables.BaseType.string)
			self.fail("No error on mixed type values")
		except ValueError:
			pass


	def testCaseMultiple(self):
		v=variables.MultipleContainer()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is None,"baseType is unknown on creation")
		v=variables.MultipleContainer(variables.BaseType.identifier)
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.identifier,"baseType forced on creation")
		v.SetValue([])
		self.failUnless(v.IsNull(),"Null test on empty list.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.identifier,"baseType inherited when unspecified")
		v.SetValue([None],variables.BaseType.string)
		self.failUnless(v.IsNull(),"Null test on list with a single NULL value.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is variables.BaseType.string,"baseType is known, NULL value in list")
		v.SetValue(["A","A",None,"B"],variables.BaseType.identifier)
		self.failIf(v.IsNull(),"Null test on non-empty list.")
		self.failUnless(type(v.value)==types.DictType,"Value should be a dictionary")
		self.failUnless(v.baseType is variables.BaseType.identifier,"baseType from list")
		self.failUnless(len(v.value.keys())==2,"NULL value should be ignored by SetValue: %s"%repr(v.value))
		self.failUnless(v.value[u'A']==2,"frequency of value on set")
		v.SetValue((u"C",u"D"),variables.BaseType.string)
		self.failUnless(v.value[u"D"]==1,"set from tuple")		
		try:
			v.SetValue(["A",3.14,"B"],variables.BaseType.string)
			self.fail("No error on mixed type values")
		except ValueError:
			pass


	def testCaseRecord(self):
		v=variables.RecordContainer()
		self.failUnless(v.IsNull(),"Null test on creation.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is None,"baseType is unknown for record containers")
		v.SetValue({})
		self.failUnless(v.IsNull(),"Null test on empty list.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is None,"baseType is unknown for record containers")
		v.SetValue({'x':None})
		self.failUnless(v.IsNull(),"Null test on list with a single NULL value.")
		self.failUnless(v.value is None,"Value should be None")
		self.failUnless(v.baseType is None,"baseType is unknown for record containers")
		v.SetValue({
			u'x':variables.IdentifierValue(u"Hello"),
			u'y':None,
			u'pi':variables.FloatValue(3.14159)
			})
		self.failIf(v.IsNull(),"Null test on non-empty list.")
		self.failUnless(type(v.value)==types.DictType,"Value should be a dictionary")
		self.failUnless(v.baseType is None,"baseType is unknown for record containers")
		self.failUnless(len(v.value.keys())==2,"NULL value should be ignored by SetValue: %s"%repr(v.value))
		self.failUnless(isinstance(v.value[u'pi'],variables.FloatValue),"type of pi value")
		self.failUnless(v.value[u'pi'].value==3.14159,"value of pi")
		# We also support direct look up of the values
		self.failUnless(isinstance(v[u'pi'],variables.FloatValue),"type of pi value - direct lookup")
		self.failUnless(v[u'pi'].value==3.14159,"value of pi - direct lookup")
		# And direct assignment...
		v[u"e"]=variables.FloatValue(2.718)
		self.failUnless(len(v.value.keys())==3,"New field added: %s"%repr(v.value))
		self.failUnless(isinstance(v.value[u'e'],variables.FloatValue),"type of e value")
		self.failUnless(v.value[u'e'].value==2.718,"value of e")
			

class QTIElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=core.QTIElement(None)


class VariableTests(unittest.TestCase):

	def testCaseValue(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="Mapping" title="Mapping Test" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE_AS" cardinality="single" baseType="identifier">
        <defaultValue>
            <value>A</value>
        </defaultValue>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE_BO" cardinality="ordered" baseType="integer">
        <defaultValue>
            <value>3</value>
            <value>2</value>
            <value>1</value>
        </defaultValue>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE_CM" cardinality="multiple" baseType="float">
        <defaultValue>
            <value>3.0</value>
            <value>0.1</value>
            <value>4e-2</value>
            <value>0.001</value>
            <value>600E-6</value>    
        </defaultValue>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE_DR" cardinality="record">
        <defaultValue>
            <value fieldIdentifier="name" baseType="identifier">pi</value>
            <value fieldIdentifier="value" baseType="float">3.14159</value>
            <value fieldIdentifier="approx" baseType="integer">3</value>
        </defaultValue>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE_ENULL" cardinality="single" baseType="string"/>
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		rd=doc.root.ResponseDeclaration[0].GetDefaultValue()
		self.failUnless(isinstance(rd,variables.Value),"Default value not a Value")
		self.failUnless(rd.Cardinality()==variables.Cardinality.single,"Single value was a container")
		self.failUnless(rd.baseType==variables.BaseType.identifier,"Single default base type")
		self.failUnless(rd.value==u"A","Singe default value")
		rd=doc.root.ResponseDeclaration[1].GetDefaultValue()
		self.failUnless(rd.Cardinality()==variables.Cardinality.ordered,"Ordered value not a container")
		self.failUnless(rd.baseType==variables.BaseType.integer,"Ordered default base type")
		self.failUnless(rd.value==[3,2,1],"Ordered default value")
		rd=doc.root.ResponseDeclaration[2].GetDefaultValue()
		self.failUnless(rd.Cardinality()==variables.Cardinality.multiple,"Multiple value not a container")
		self.failUnless(rd.baseType==variables.BaseType.float,"Multiple default base type")
		self.failUnless(rd.value=={3.0:1,0.1:1,0.04:1,0.001:1,0.0006:1},"Multiple default value")
		rd=doc.root.ResponseDeclaration[3].GetDefaultValue()
		self.failUnless(rd.Cardinality()==variables.Cardinality.record,"Record value not a container")
		self.failUnless(rd.baseType==None,"Record default base type")
		self.failUnless(rd[u'value'].value==3.14159,"Record default value: %s"%repr(rd[u'value']))
		rd=doc.root.ResponseDeclaration[4].GetDefaultValue()
		self.failUnless(rd.Cardinality()==variables.Cardinality.single,"Single NULL value cardinality")
		self.failUnless(rd.baseType==variables.BaseType.string,"Single NULL base type")
		self.failUnless(rd.value is None,"Single NULL value: %s"%repr(rd.value))

		
	def testCaseMapping(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="Mapping" title="Mapping Test" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE" cardinality="multiple" baseType="identifier">
        <mapping defaultValue="-0.5" lowerBound="0.0" upperBound="14">
            <mapEntry mapKey="A" mappedValue="8.0"/>
            <mapEntry mapKey="B" mappedValue="2.0"/>
            <mapEntry mapKey="C" mappedValue="4.0"/>
            <mapEntry mapKey="D" mappedValue="1.0"/>
        </mapping>
    </responseDeclaration>
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		mapping=doc.root.ResponseDeclaration[0].Mapping
		self.failUnless(mapping.baseType is variables.BaseType.identifier,"Base type of mapping auto-discovered")
		for v,mv in {
			"A":8.0,
			"B":2.0,
			"C":4.0,
			"D":1.0,
			"ABCDE":14.0,
			"BCDE":6.5,
			"ABDD":11.0,
			"":0.0}.items():
			value=variables.MultipleContainer(mapping.baseType)
			value.SetValue(iter(v))
			mValue=mapping.MapValue(value)
			self.failUnless(isinstance(mValue,variables.FloatValue),"MapValue response type")
			self.failUnless(mValue.value==mv,"Mapping failed for multiple %s, returned %.1f"%(v,mValue.value))						
			value=variables.OrderedContainer(mapping.baseType)
			value.SetValue(iter(v))
			mValue=mapping.MapValue(value)
			self.failUnless(mValue.value==mv,"Mapping failed for ordered %s, returned %.1f"%(v,mValue.value))						
			
	

EXAMPLE_1="""<?xml version="1.0" encoding="utf-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="test"></assessmentItem>"""

EXAMPLE_2="""<?xml version="1.0" encoding="UTF-8"?>
<!-- This example adapted from the PET Handbook, copyright University of Cambridge ESOL Examinations -->
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

class QTIDocumentTests(unittest.TestCase):
	def testCaseConstructor(self):
		doc=QTIDocument()
		self.failUnless(isinstance(doc,xmlns.XMLNSDocument))

	def testCaseExample1(self):
		doc=QTIDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		root=doc.root
		self.failUnless(isinstance(root,QTIAssessmentItem))
		self.failUnless(root.ns==core.IMSQTI_NAMESPACE and root.xmlname=='assessmentItem')

	def testCaseExample2(self):
		doc=QTIDocument()
		doc.Read(src=StringIO(EXAMPLE_2))
		vardefs=doc.root.declarations
		self.failUnless(len(vardefs.keys())==2)
		self.failUnless(isinstance(vardefs['RESPONSE'],variables.ResponseDeclaration))
		self.failUnless(isinstance(vardefs['SCORE'],variables.OutcomeDeclaration))
	

if __name__ == "__main__":
	unittest.main()

