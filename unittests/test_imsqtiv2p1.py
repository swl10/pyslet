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

		
	def testCaseCorrect(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="Mapping" title="Mapping Test" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE_A" cardinality="single" baseType="identifier">
        <correctResponse interpretation="single">
            <value>A</value>
        </correctResponse>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE_B" cardinality="ordered" baseType="integer">
        <correctResponse>
            <value>3</value>
            <value>2</value>
            <value>1</value>
        </correctResponse>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE_C" cardinality="single" baseType="string"/>
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		rc=doc.root.ResponseDeclaration[0].GetCorrectValue()
		self.failUnless(isinstance(rc,variables.Value),"Correct value not a Value")
		self.failUnless(rc.Cardinality()==variables.Cardinality.single,"Single value was a container")
		self.failUnless(rc.baseType==variables.BaseType.identifier,"Single default base type")
		self.failUnless(rc.value==u"A","Singe default value: %s"%repr(rc.value))
		self.failUnless(doc.root.ResponseDeclaration[0].CorrectResponse.interpretation=="single","Correct interpretation")
		rc=doc.root.ResponseDeclaration[1].GetCorrectValue()
		self.failUnless(rc.Cardinality()==variables.Cardinality.ordered,"Ordered value not a container")
		self.failUnless(rc.baseType==variables.BaseType.integer,"Ordered default base type")
		self.failUnless(rc.value==[3,2,1],"Ordered default value")
		self.failUnless(doc.root.ResponseDeclaration[1].CorrectResponse.interpretation is None,"Emptyy correct interpretation")
		rc=doc.root.ResponseDeclaration[2].GetCorrectValue()
		self.failUnless(rc.Cardinality()==variables.Cardinality.single,"Single NULL value cardinality")
		self.failUnless(rc.baseType==variables.BaseType.string,"Single NULL base type")
		self.failUnless(rc.value is None,"Single NULL value: %s"%repr(rc.value))


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
	
	def testCaseAreaMapping(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="Mapping" title="Mapping Test" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE" cardinality="multiple" baseType="identifier">
        <areaMapping defaultValue="-0.5" lowerBound="0.0" upperBound="20">
            <areaMapEntry shape="ellipse" coords="12,12,6%,2" mappedValue="8.0"/>
            <areaMapEntry shape="rect" coords="2,2,22,22" mappedValue="2.0"/>
            <areaMapEntry shape="circle" coords="84%,12,2" mappedValue="4.0"/>
            <areaMapEntry shape="poly" coords="42,2,32,22,52,22,42,2" mappedValue="1.0"/>
            <areaMapEntry shape="default" coords="" mappedValue="16.0"/>
        </areaMapping>
    </responseDeclaration>
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		mapping=doc.root.ResponseDeclaration[0].AreaMapping
		for v,mv in {
			((12,13),):8.0,
			((12,8),):2.0,
			((43,13),):4.0,
			((42,9),):1.0,
			((1,1),):16.0,
			((12,13),(11,12),):8.0,
			((12,13),(12,8),(43,13),(42,9),(1,1),(200,200),):20.0,
			((12,8),(43,13),(42,9),(200,200),):6.5,
			((12,13),(12,8),(42,9),(42,8),):11.0,
			():0.0}.items():
			value=variables.MultipleContainer(variables.BaseType.point)
			value.SetValue(iter(v))
			mValue=mapping.MapValue(value,50,50)
			self.failUnless(isinstance(mValue,variables.FloatValue),"MapValue response type")
			self.failUnless(mValue.value==mv,"AreaMapping failed for multiple %s, returned %.1f"%(v,mValue.value))						
			value=variables.OrderedContainer(variables.BaseType.point)
			value.SetValue(iter(v))
			mValue=mapping.MapValue(value,50,50)
			self.failUnless(mValue.value==mv,"Mapping failed for ordered %s, returned %.1f"%(v,mValue.value))						
	
	def testCaseLookupTable(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="Mapping" title="Mapping Test" adaptive="false" timeDependent="false">
    <outcomeDeclaration identifier="SCORE_A" cardinality="single" baseType="identifier">
        <matchTable defaultValue="U">
            <matchTableEntry sourceValue="10" targetValue="A"/>
            <matchTableEntry sourceValue="9" targetValue="A"/>
            <matchTableEntry sourceValue="8" targetValue="B"/>
            <matchTableEntry sourceValue="7" targetValue="B"/>
            <matchTableEntry sourceValue="6" targetValue="C"/>
            <matchTableEntry sourceValue="5" targetValue="C"/>
            <matchTableEntry sourceValue="4" targetValue="D"/>
            <matchTableEntry sourceValue="3" targetValue="D"/>
            <matchTableEntry sourceValue="2" targetValue="E"/>
            <matchTableEntry sourceValue="1" targetValue="E"/>
        </matchTable>
    </outcomeDeclaration>
    <outcomeDeclaration identifier="SCORE_B" cardinality="single" baseType="identifier">
        <interpolationTable defaultValue="U">
            <interpolationTableEntry sourceValue="9" targetValue="A"/>
            <interpolationTableEntry sourceValue="6" targetValue="B" includeBoundary="false"/>
            <interpolationTableEntry sourceValue="7" targetValue="F"/>
            <interpolationTableEntry sourceValue="5" targetValue="C" includeBoundary="true"/>
            <interpolationTableEntry sourceValue="3" targetValue="D" includeBoundary="true"/>
            <interpolationTableEntry sourceValue="0.5" targetValue="E" includeBoundary="true"/>
        </interpolationTable>
    </outcomeDeclaration>
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		matchTable=doc.root.OutcomeDeclaration[0].LookupTable
		interpolationTable=doc.root.OutcomeDeclaration[1].LookupTable
		self.failUnless(matchTable.baseType is variables.BaseType.identifier,"Base type of matchTable auto-discovered")
		self.failUnless(interpolationTable.baseType is variables.BaseType.identifier,"Base type of interpolationTable auto-discovered")
		for rawScore,grade in {
			0:"U",
			1:"E",
			2:"E",
			3:"D",
			4:"D",
			5:"C",
			6:"C",
			7:"B",
			8:"B",
			9:"A",
			10:"A",
			-1:"U"}.items():
			value=variables.IntegerValue(rawScore)
			mapGrade=matchTable.Lookup(value)
			self.failUnless(isinstance(mapGrade,variables.IdentifierValue),"Lookup response type")
			self.failUnless(mapGrade.value==grade,"MatchTable failed for %i, returned %s"%(rawScore,mapGrade.value))						
			try:
				value=variables.FloatValue(float(rawScore))
				mapGrade=matchTable.Lookup(value)
				self.fail("MatchTable accepted float for lookup")
			except ValueError:
				pass
			value=variables.IntegerValue(rawScore)
			mapGrade=interpolationTable.Lookup(value)
			self.failUnless(isinstance(mapGrade,variables.IdentifierValue),"Lookup response type")
			self.failUnless(mapGrade.value==grade,"InterpolationTable failed for %i, returned %s"%(rawScore,mapGrade.value))						
			value=variables.FloatValue(float(rawScore))
			mapGrade=interpolationTable.Lookup(value)
			self.failUnless(isinstance(mapGrade,variables.IdentifierValue),"Lookup response type")
			self.failUnless(mapGrade.value==grade,"InterpolationTable failed for %i, returned %s"%(rawScore,mapGrade.value))						
	
	def testCaseItemSession(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="TestCase" title="Test Case" adaptive="false" timeDependent="false">
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		sessionState=variables.ItemSessionState(doc.root)
		self.failUnless(sessionState.item==doc.root,"Session State item pointer")
		value=sessionState['numAttempts']
		self.failUnless(isinstance(value,variables.IntegerValue),"numAttempts must be of IntegerValue type")
		self.failUnless(value.value==0,"numAttempts must initially be 0")
		self.failUnless(sessionState.IsResponse('numAttempts'),"numAttempts is a response variable")
		self.failUnless(not sessionState.IsOutcome('numAttempts'),"numAttempts is not an outcome variable")
		self.failUnless(not sessionState.IsTemplate('numAttempts'),"numAttempts is not a template variable")
		value=sessionState['duration']
		self.failUnless(isinstance(value,variables.DurationValue),"duration must be of DurationValue type")
		self.failUnless(value.value==0.0,"duration must initially be 0")				
		self.failUnless(sessionState.IsResponse('duration'),"duration is a response variable")
		self.failUnless(not sessionState.IsOutcome('duration'),"duration is not an outcome variable")
		self.failUnless(not sessionState.IsTemplate('duration'),"duration is not a template variable")
		value=sessionState['completionStatus']
		self.failUnless(isinstance(value,variables.IdentifierValue),"completionStatus must be of IdentifierValue type")
		self.failUnless(value.value=="not_attempted","completionStatus must initially be not_attempted")				
		self.failUnless(not sessionState.IsResponse('completionStatus'),"completionStatus is not a response variable")
		self.failUnless(sessionState.IsOutcome('completionStatus'),"completionStatus is an outcome variable")
		self.failUnless(not sessionState.IsTemplate('completionStatus'),"completionStatus is not a template variable")
		self.failUnless(len(sessionState)==3,"3 default variables")
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="TestCase" title="Test Case" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
        <defaultValue>
            <value>A</value>
        </defaultValue>
    </responseDeclaration>
    <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="integer">
        <defaultValue>
            <value>-1</value>
        </defaultValue>       
    </outcomeDeclaration>
    <outcomeDeclaration identifier="SCORE1" cardinality="single" baseType="integer"/>
    <outcomeDeclaration identifier="SCORE2" cardinality="single" baseType="float"/>
    <outcomeDeclaration identifier="SCORE3" cardinality="single" baseType="string"/>
    <templateDeclaration identifier="VARIABLE" cardinality="single" baseType="float">
        <defaultValue>
            <value>3.14159</value>
        </defaultValue>
    </templateDeclaration>
</assessmentItem>"""
		doc=QTIDocument()
		doc.Read(src=StringIO(SAMPLE))
		sessionState=variables.ItemSessionState(doc.root)
		self.failUnless(len(sessionState)==9,"6 defined + 3 default variables")
		value=sessionState['RESPONSE']
		self.failUnless(isinstance(value,variables.IdentifierValue),"RESPONSE type")
		self.failIf(value,"RESPONSE initial value must be NULL")
		self.failUnless(sessionState.IsResponse('RESPONSE'),"RESPONSE is a response variable")
		self.failUnless(not sessionState.IsOutcome('RESPONSE'),"RESPONSE is not an outcome variable")
		self.failUnless(not sessionState.IsTemplate('RESPONSE'),"RESPONSE is not a template variable")
		value=sessionState['SCORE']
		self.failUnless(isinstance(value,variables.IntegerValue),"SCORE type")
		self.failUnless(value.value==-1,"SCORE initial value")				
		self.failUnless(not sessionState.IsResponse('SCORE'),"SCORE is not a response variable")
		self.failUnless(sessionState.IsOutcome('SCORE'),"SCORE is an outcome variable")
		self.failUnless(not sessionState.IsTemplate('SCORE'),"SCORE is not a template variable")
		value=sessionState['SCORE1']
		self.failUnless(isinstance(value,variables.IntegerValue),"SCORE1 type")
		self.failUnless(value.value==0,"SCORE1 initial value")				
		value=sessionState['SCORE2']
		self.failUnless(isinstance(value,variables.FloatValue),"SCORE2 type")
		self.failUnless(value.value==0.0,"SCORE2 initial value")				
		value=sessionState['SCORE3']
		self.failUnless(isinstance(value,variables.StringValue),"SCORE3 type")
		self.failIf(value,"SCORE3 initial value must be NULL")
		value=sessionState['VARIABLE']
		self.failUnless(isinstance(value,variables.FloatValue),"VARIABLE type")
		self.failUnless(value.value==3.14159,"VARIABLE initial value")				
		self.failUnless(not sessionState.IsResponse('VARIABLE'),"VARIABLE is not a response variable")
		self.failUnless(not sessionState.IsOutcome('VARIABLE'),"VARIABLE is not an outcome variable")
		self.failUnless(sessionState.IsTemplate('VARIABLE'),"VARIABLE is a template variable")
		sessionState.BeginAttempt()
		value=sessionState['numAttempts']
		self.failUnless(value.value==1,"numAttempts set to 1 at start of attempt")
		value=sessionState['RESPONSE']
		self.failUnless(value.value==u"A","RESPONSE set to default at start of first attempt")
		value.SetValue(u"B")
		value=sessionState['completionStatus']
		self.failUnless(value.value==u"unknown","completionStatus set to unknown at start of first attempt: %s"%value.value)
		value.SetValue("completed")
		sessionState.EndAttempt()
		sessionState.BeginAttempt()
		value=sessionState['numAttempts']
		self.failUnless(value.value==2,"numAttempts incremented")
		value=sessionState['completionStatus']
		self.failUnless(value.value==u"completed","completionStatus keeps its value")
		value=sessionState['RESPONSE']
		self.failUnless(value.value==u"B","RESPONSE keeps its value")
				
		
class ExpressionTests(unittest.TestCase):

	def setUp(self):
		SAMPLE="""<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="TestCase" title="Test Case" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
        <defaultValue>
            <value>A</value>
        </defaultValue>
        <correctResponse>
            <value>B</value>
        </correctResponse>
        <mapping defaultValue="0.0">
            <mapEntry mapKey="A" mappedValue="3.14"/>
            <mapEntry mapKey="B" mappedValue="5"/>
        </mapping>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE1" cardinality="ordered" baseType="point">
        <defaultValue>
            <value>5 5</value>
        </defaultValue>
        <areaMapping defaultValue="0.0">
            <areaMapEntry shape="rect" coords="0,0,10,10" mappedValue="3.14"/>
            <areaMapEntry shape="default" coords="" mappedValue="1"/>
        </areaMapping>       
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE2" cardinality="multiple" baseType="point"/>
    <responseDeclaration identifier="RESPONSE3" cardinality="ordered" baseType="identifier">
        <defaultValue>
            <value>A</value>
            <value>B</value>
            <value>C</value>
        </defaultValue>
    </responseDeclaration>
    <responseDeclaration identifier="RESPONSE4" cardinality="record">
        <defaultValue>
            <value baseType="identifier" fieldIdentifier="fieldA">A</value>
            <value baseType="float" fieldIdentifier="pi">3.14159</value>
        </defaultValue> 
    </responseDeclaration>
    <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="integer">
        <defaultValue>
            <value>-1</value>
        </defaultValue>       
    </outcomeDeclaration>
    <outcomeDeclaration identifier="SCORE1" cardinality="single" baseType="string"/>
    <templateDeclaration identifier="VARIABLE" cardinality="single" baseType="float">
        <defaultValue>
            <value>3.14159</value>
        </defaultValue>
    </templateDeclaration>
</assessmentItem>"""
		self.doc=QTIDocument()
		self.doc.Read(src=StringIO(SAMPLE))
		self.sessionState=variables.ItemSessionState(self.doc.root)
		self.sessionState.BeginAttempt()
			
	def tearDown(self):
		pass
	
	def testCaseBaseValue(self):
		e=expressions.BaseValue(None)
		e.baseType=variables.BaseType.point
		e.AddData("3 1")
		e.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.PointValue),"BaseValue type")
		self.failUnless(value.value==(3,1),"BaseValue value: %s"%repr(value.value))				
	
	def testCaseVariable(self):
		e=expressions.Variable(None)
		e.identifier='RESPONSE'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IdentifierValue),"Variable type")
		self.failUnless(value.value==u"A","Variable value: %s"%repr(value.value))
		try:
			e.identifier='UNDECLARED'
			value=e.Evaluate(self.sessionState)
			self.fail("Variable UNDECLARED")	
		except core.ProcessingError:
			pass	
		# TODO: add tests for outcome processing lookups (when AssessmentSessionState is defined)

	def testCaseDefault(self):
		e=expressions.Default(None)
		e.identifier='RESPONSE'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IdentifierValue),"Variable type")
		self.failUnless(value.value==u"A","Variable value: %s"%repr(value.value))
		e.identifier='SCORE1'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.StringValue),"Variable type")
		self.failIf(value,"NULL default value: %s"%repr(value.value))
		try:
			e.identifier='UNDECLARED'
			value=e.Evaluate(self.sessionState)
			self.fail("Default UNDECLARED")	
		except core.ProcessingError:
			pass	
		
	def testCaseCorrect(self):
		e=expressions.Correct(None)
		e.identifier='RESPONSE'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IdentifierValue),"Correct type")
		self.failUnless(value.value==u"B","Correct value: %s"%repr(value.value))
		try:
			e.identifier='UNDECLARED'
			value=e.Evaluate(self.sessionState)
			self.fail("Correct UNDECLARED")	
		except core.ProcessingError:
			pass	
		try:
			e.identifier='SCORE'
			value=e.Evaluate(self.sessionState)
			self.fail("Correct value of outcome")
		except core.ProcessingError:
			pass	
	
	def testCaseMapResponse(self):
		e=expressions.MapResponse(None)
		e.identifier='RESPONSE'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.FloatValue),"MapResponse type")
		self.failUnless(value.value==3.14,"Mapped value: %s"%repr(value.value))
		try:
			e.identifier='RESPONSE1'
			value=e.Evaluate(self.sessionState)
			self.fail("MapResponse with no mapping")	
		except core.ProcessingError:
			pass	
		try:
			e.identifier='SCORE'
			value=e.Evaluate(self.sessionState)
			self.fail("MapResponse value of outcome")
		except core.ProcessingError:
			pass	

	def testCaseMapResponsePoint(self):
		e=expressions.MapResponsePoint(None)
		e.identifier='RESPONSE1'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.FloatValue),"MapResponsePoint type")
		self.failUnless(value.value==3.14,"Mapped value: %s"%repr(value.value))
		try:
			e.identifier='RESPONSE'
			value=e.Evaluate(self.sessionState)
			self.fail("MapResponsePoint with wrong baseType")	
		except core.ProcessingError:
			pass	
		try:
			e.identifier='RESPONSE2'
			value=e.Evaluate(self.sessionState)
			self.fail("MapResponsePoint with no areaMapping")	
		except core.ProcessingError:
			pass	
		try:
			e.identifier='SCORE'
			value=e.Evaluate(self.sessionState)
			self.fail("MapResponsePoint with outcome")
		except core.ProcessingError:
			pass	

	def testCaseNull(self):
		e=expressions.Null(None)
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.Value),"Null type")
		self.failUnless(value.baseType is None,"Null base type: %s"%variables.BaseType.EncodeValue(value.baseType))				
		self.failUnless(value.value is None,"Null value: %s"%repr(value.value))				
		self.failIf(value,"Null is null")

	def testCaseRandomInteger(self):
		e=expressions.RandomInteger(None)
		e.min="2"
		e.max="11"
		e.step="3"
		gotValue={}
		for i in xrange(100):
			value=e.Evaluate(self.sessionState)
			self.failUnless(isinstance(value,variables.IntegerValue),"RandomInteger type")
			self.failUnless(value.value in (2,5,8,11),"RandomInteger value: %s"%repr(value.value))
			gotValue[value.value]=True
		for i in (2,5,8,11):
			self.failUnless(i in gotValue,"RandomInteger failed with p=0.000000000001, really?")
		# TODO: also supports template references
		
	def testCaseRandomFloat(self):
		e=expressions.RandomFloat(None)
		e.min="5.0"
		e.max="5.5"
		gotValue={}
		for i in xrange(200):
			value=e.Evaluate(self.sessionState)
			self.failUnless(isinstance(value,variables.FloatValue),"RandomFloat type")
			self.failUnless(value.value>=5.0 and value.value<=5.5,"RandomFloat value: %s"%repr(value.value))
			v="%.1f"%value.value
			self.failUnless(v in ("5.0","5.1","5.2","5.3","5.4","5.5"),"RandomFloat value: %s"%v)
			gotValue[v]=True
		for i in ("5.0","5.1","5.2","5.3","5.4","5.5"):
			self.failUnless(i in gotValue,"RandomFloat failed with p=0.0000000014, really?")
		# TODO: also supports template references
	
	def testCaseMultiple(self):
		e=expressions.Multiple(None)
		# check the null case
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.MultipleContainer),"Multiple cardinality")
		self.failUnless(value.baseType is None,"Multiple with unknown base type")		
		# check that sub-expressions with NULL values are ignored
		v1=e.ChildElement(expressions.BaseValue)
		v1.baseType=variables.BaseType.integer
		v1.AddData("1")
		v1.ContentChanged()
		v2=e.ChildElement(expressions.Null)
		v3=e.ChildElement(expressions.BaseValue)
		v3.baseType=variables.BaseType.integer
		v3.AddData("3")
		v3.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.MultipleContainer),"Multiple type")
		self.failUnless(value.baseType==variables.BaseType.integer,"Multiple base type")		
		self.failUnless(value.value=={1:1,3:1},"Multiple value: %s"%repr(value.value))
		v4=e.ChildElement(expressions.Multiple)
		v4_1=v4.ChildElement(expressions.BaseValue)
		v4_1.baseType=variables.BaseType.integer
		v4_1.AddData("3")
		v4_1.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.value=={1:1,3:2},"Multiple in Multiple value: %s"%repr(value.value))
		# check that mixed base types raise an error
		v5=e.ChildElement(expressions.BaseValue)
		v5.baseType=variables.BaseType.float
		v5.AddData("3.1")
		v5.ContentChanged()
		try:
			value=e.Evaluate(self.sessionState)
			self.fail("Multiple with mixed base types")
		except core.ProcessingError:
			pass	
					
		
	def testCaseOrdered(self):
		e=expressions.Ordered(None)
		# check the null case
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.OrderedContainer),"Ordered cardinality")
		self.failUnless(value.baseType is None,"Ordered with unknown base type")		
		# check that sub-expressions with NULL values are ignored
		v1=e.ChildElement(expressions.BaseValue)
		v1.baseType=variables.BaseType.integer
		v1.AddData("1")
		v1.ContentChanged()
		v2=e.ChildElement(expressions.Null)
		v3=e.ChildElement(expressions.BaseValue)
		v3.baseType=variables.BaseType.integer
		v3.AddData("3")
		v3.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.OrderedContainer),"Ordered type")
		self.failUnless(value.baseType==variables.BaseType.integer,"Ordered base type")		
		self.failUnless(value.value==[1,3],"Ordered value: %s"%repr(value.value))
		v4=e.ChildElement(expressions.Ordered)
		v4_1=v4.ChildElement(expressions.BaseValue)
		v4_1.baseType=variables.BaseType.integer
		v4_1.AddData("3")
		v4_1.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.value==[1,3,3],"Ordered in Ordered value: %s"%repr(value.value))
		# check that mixed base types raise an error
		v5=e.ChildElement(expressions.BaseValue)
		v5.baseType=variables.BaseType.float
		v5.AddData("3.1")
		v5.ContentChanged()
		try:
			value=e.Evaluate(self.sessionState)
			self.fail("Ordered with mixed base types")
		except core.ProcessingError:
			pass	
					
	def testCaseContainerSize(self):
		e=expressions.ContainerSize(None)
		# check the null case
		eo=e.ChildElement(expressions.Ordered)
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IntegerValue),"ContainerSize type")
		self.failUnless(value.value==0,"ContainerSize of NULL value")
		for i in xrange(5):
			v=eo.ChildElement(expressions.BaseValue)
			v.baseType=variables.BaseType.integer
			v.AddData("1")
			v.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.value==5,"ContainerSize of ordered value")
		e=expressions.ContainerSize(None)
		em=e.ChildElement(expressions.Multiple)
		for i in xrange(6):
			v=em.ChildElement(expressions.BaseValue)
			v.baseType=variables.BaseType.integer
			v.AddData(str(i/2))
			v.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.value==6,"ContainerSize of multiple value")
		# check that single values raise an error
		e=expressions.ContainerSize(None)
		es=e.ChildElement(expressions.BaseValue)
		es.baseType=variables.BaseType.integer
		es.AddData("3")
		es.ContentChanged()
		try:
			value=e.Evaluate(self.sessionState)
			self.fail("ContainerSize with singe value")
		except core.ProcessingError:
			pass	
					
	def testCaseIsNull(self):
		e=expressions.IsNull(None)
		e.ChildElement(expressions.Null)
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.BooleanValue),"IsNull type")
		self.failUnless(value.value==True,"IsNull value (on Null): %s"%repr(value.value))				
		self.failUnless(value,"IsNull evaluates to True")
		e=expressions.IsNull(None)
		b=e.ChildElement(expressions.BaseValue)
		b.baseType=variables.BaseType.boolean
		b.AddData("true")
		b.ContentChanged()				
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.BooleanValue),"IsNull type")
		self.failUnless(value.value==False,"IsNull value (on non-Null): %s"%repr(value.value))				
		self.failUnless(value,"IsNull value always evaluates to True")
		# Note that empty containers and empty strings are both treated as NULL.
		e=expressions.IsNull(None)
		b=e.ChildElement(expressions.BaseValue)
		b.baseType=variables.BaseType.string
		b.AddData("")
		b.ContentChanged()
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.value==True,"IsNull value (empty string): %s"%repr(value.value))				
		e=expressions.IsNull(None)
		b=e.ChildElement(expressions.Multiple)
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.value==True,"IsNull value (empty container): %s"%repr(value.value))				

	def testCaseIndex(self):
		e=expressions.Index(None)
		e.n=2
		v=e.ChildElement(expressions.Variable)
		v.identifier='RESPONSE3'
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IdentifierValue),"Index type")
		self.failUnless(value.value==u"B","Index value: %s"%repr(value.value))
		e.n=4
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IdentifierValue),"Index type")
		self.failIf(value,"Index out of bounds is False")
		self.failUnless(value.value==None,"Index out of bounds: %s"%repr(value.value))
		# n must be a positive integer		
		try:
			e.n=0
			value=e.Evaluate(self.sessionState)
			self.fail("Index 0")	
		except core.ProcessingError:
			pass	
		try:
			e.n=-1
			value=e.Evaluate(self.sessionState)
			self.fail("Index -1")	
		except core.ProcessingError:
			pass
		try:
			e=expressions.Index(None)
			e.n=1
			v=e.ChildElement(expressions.Variable)
			v.identifier='RESPONSE'
			value=e.Evaluate(self.sessionState)
			self.fail("Index of single value")	
		except core.ProcessingError:
			pass
		
	def testCaseFieldValue(self):
		e=expressions.FieldValue(None)
		e.fieldIdentifier="unknown"
		v=e.ChildElement(expressions.Variable)
		v.identifier='RESPONSE4'
		value=e.Evaluate(self.sessionState)
		self.failUnless(value.baseType is None,"fieldValue type on unknown")
		self.failIf(value,"fieldValue out of bounds is False")
		e.fieldIdentifier="fieldA"
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.IdentifierValue),"fieldValue type")
		self.failUnless(value.value==u"A","fieldValue identifier: %s"%repr(value.value))
		e.fieldIdentifier="pi"
		value=e.Evaluate(self.sessionState)
		self.failUnless(isinstance(value,variables.FloatValue),"fieldValue type: float")
		self.failUnless(value.value==3.14159,"fieldValue float: %s"%repr(value.value))
		try:
			e=expressions.FieldValue(None)
			e.fieldIdentifier="fieldA"
			v=e.ChildElement(expressions.Variable)
			v.identifier='RESPONSE'
			value=e.Evaluate(self.sessionState)
			self.fail("fieldValue of single value")	
		except core.ProcessingError:
			pass	
			
		
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

