#! /usr/bin/env python

import unittest
import logging


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(QTITests, 'test'),
        unittest.makeSuite(ValueTests, 'test'),
        unittest.makeSuite(QTIElementTests, 'test'),
        unittest.makeSuite(VariableTests, 'test'),
        unittest.makeSuite(ResponseProcessingTests, 'test'),
        unittest.makeSuite(TemplateProcessingTests, 'test'),
        unittest.makeSuite(ExpressionTests, 'test'),
        unittest.makeSuite(BasicAssessmentTests, 'test'),
        unittest.makeSuite(MultiPartAssessmentTests, 'test'),
        unittest.makeSuite(ErrorAssessmentTests, 'test'),
        unittest.makeSuite(QTIDocumentTests, 'test')
    ))

from pyslet.imsqtiv2p1 import *
import pyslet.html40_19991224 as html

from StringIO import StringIO
import os
import types
import time


class QTITests(unittest.TestCase):

    def testCaseConstants(self):
        self.assertTrue(core.IMSQTI_NAMESPACE == "http://www.imsglobal.org/xsd/imsqti_v2p1",
                        "Wrong QTI namespace: %s" % core.IMSQTI_NAMESPACE)
        self.assertTrue(core.IMSQTI_ITEM_RESOURCETYPE == "imsqti_item_xmlv2p1",
                        "Wrong QTI resource type: %s" % core.IMSQTI_ITEM_RESOURCETYPE)


class ValueTests(unittest.TestCase):

    def testCaseNULL(self):
        v = variables.Value()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertFalse(v, "Null zero/false test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is None, "BaseType should be unknown on default constructor.")
        v = variables.StringValue()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.string, "NULL value with known type.")
        v.SetValue("x")
        self.assertTrue(not v.IsNull(), "Null test with value")
        self.assertTrue(v, "Null zero/false test on creation.")
        v.SetValue(None)
        self.assertTrue(v.IsNull(), "Null test with Non value")
        self.assertFalse(v, "Null zero/false test with Non value.")
        self.assertTrue(
            v.baseType is variables.BaseType.string, "NULL value retains known type.")

    def testCaseIdentifier(self):
        v = variables.IdentifierValue()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertFalse(v, "Null zero/false test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.identifier, "baseType on creation")
        for vIn in ('name', 'goodName'):
            v.SetValue(vIn)
            self.assertTrue(
                type(v.value) is types.UnicodeType, "Value type on set")
            self.assertTrue(v.value == vIn, "Good strings")
        for vIn in ('1', '.Name'):
            try:
                v.SetValue(vIn)
                self.fail("Error string: %s" % vIn)
            except ValueError:
                pass
        try:
            v.SetValue(".Name", False)
        except ValueError:
            self.fail("Bad name with nameCheck=False")

    def testCaseBoolean(self):
        v = variables.BooleanValue()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.boolean, "baseType on creation")
        for vIn in ('true', '1', True, 1, 2L):
            v.SetValue(vIn)
            self.assertTrue(v.value is True, "True values")
        for vIn in ('false', '0', False, 0, 0L):
            v.SetValue(vIn)
            self.assertTrue(v.value is False, "False values")
        for vIn in ('True', 'Yes', "FALSE", "2", 3.14):
            try:
                v.SetValue(vIn)
                self.fail("Error string: %s" % repr(vIn))
            except ValueError:
                pass

    def testCaseInteger(self):
        v = variables.IntegerValue()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.integer, "baseType on creation")
        for vIn in ('1', '-2', 3, 4L, '+0'):
            v.SetValue(vIn)
            self.assertTrue(
                type(v.value) is types.IntType, "Value type on set: %s" % repr(type(v.value)))
            self.assertTrue(v.value == int(vIn), "Good strings")
        for vIn in ('1.3', 'pi', 3.14, '2+2'):
            try:
                v.SetValue(vIn)
                self.fail("Error string: %s" % vIn)
            except ValueError:
                pass

    def testCaseFloat(self):
        for t in (variables.BaseType.float, variables.BaseType.duration):
            v = variables.FloatValue(
            ) if t is variables.BaseType.float else variables.DurationValue()
            self.assertTrue(v.IsNull(), "Null test on creation.")
            self.assertTrue(v.value is None, "Value should be None")
            self.assertTrue(v.baseType is t, "baseType on creation")
            for vIn in ('1', '-2', 3.141, 4.0, '2.', '+2', '1E4'):
                v.SetValue(vIn)
                self.assertTrue(
                    type(v.value) is types.FloatType, "Value type on set: %s" % repr(type(v.value)))
                self.assertTrue(v.value == float(vIn), "Good strings")
            for vIn in (' 1.3', 'pi', '.', '1E', '1.3 ', '2+2'):
                try:
                    v.SetValue(vIn)
                    self.fail("Error string: %s" % repr(vIn))
                except ValueError:
                    pass

    def testCaseString(self):
        v = variables.StringValue()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.string, "baseType on creation")
        # Empty containers and empty strings are always treated as NULL values.
        v.SetValue('')
        self.assertTrue(v.IsNull(), "Null test with empty string.")
        for vIn in ('1', '-2', '2.', '+2', u'Hello', "Bye"):
            v.SetValue(vIn)
            self.assertTrue(type(v.value) is types.UnicodeType,
                            "Value type on set: %s" % repr(type(v.value)))
            self.assertTrue(v.value == vIn, "Good strings")
        for vIn in (3.141, 4.0, 1):
            try:
                v.SetValue(vIn)
                self.fail("Error string: %s" % repr(vIn))
            except ValueError:
                pass

    def testCasePoint(self):
        v = variables.PointValue()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.point, "baseType on creation")
        for vIn in ('1 2', '4 -2', (3, 4), [-1, 4L], '+0 -0'):
            v.SetValue(vIn)
            self.assertTrue(type(v.value) is types.TupleType,
                            "Value type on set: %s" % repr(type(v.value)))
            self.assertTrue(len(v.value) == 2, "Good strings")
            self.assertTrue(type(v.value[0]) == type(v.value[1]) and type(
                v.value[0]) == types.IntType, "Good point! %s" % repr(v.value))
        for vIn in ('1.3 1', 'pi', 3, '2+2', (1, 2, 3), {1: True, 2: True}):
            try:
                v.SetValue(vIn)
                self.fail("Error string: %s" % vIn)
            except ValueError:
                pass

    def testCasePairs(self):
        dpPass = False
        for t in (variables.BaseType.pair, variables.BaseType.directedPair):
            v = variables.PairValue(
            ) if t is variables.BaseType.pair else variables.DirectedPairValue()
            self.assertTrue(v.IsNull(), "Null test on creation.")
            self.assertTrue(v.value is None, "Value should be None")
            self.assertTrue(v.baseType is t, "baseType on creation")
            for vIn in (('nameB', 'nameA'), "goodName badName", ["A", "B"]):
                v.SetValue(vIn)
                self.assertTrue(
                    type(v.value) is types.TupleType, "Value type on set")
                self.assertTrue(len(v.value) == 2, "Good identifiers")
                self.assertTrue(type(v.value[0]) == type(v.value[1]) and type(v.value[0]) == types.UnicodeType,
                                "Good identifiers! %s" % repr(v.value))
                if t == variables.BaseType.pair:
                    self.assertTrue(
                        v.value[0] < v.value[1], "Pair ordering: %s" % repr(v.value))
                elif v.value[0] > v.value[1]:
                    dpPass = True
            for vIn in ('1 2', '.NameA .NameB', (1, "A"), ["a", "b", "c"]):
                try:
                    v.SetValue(vIn)
                    self.fail("Error string: %s" % vIn)
                except ValueError:
                    pass
            try:
                v.SetValue((".NameA", ".NameB"), False)
            except ValueError:
                self.fail("nameCheck=False parsing from tuple")
            try:
                v.SetValue(".NameA .NameB", False)
                self.fail("nameCheck=False parsing from string")
            except ValueError:
                pass
        self.assertTrue(dpPass, "directedPair ordering!")

    def testCaseOrdred(self):
        v = variables.OrderedContainer()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(v.baseType is None, "baseType is unknown on creation")
        v = variables.OrderedContainer(variables.BaseType.identifier)
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.identifier, "baseType forced on creation")
        v.SetValue([], variables.BaseType.string)
        self.assertTrue(v.IsNull(), "Null test on empty list.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType == variables.BaseType.string, "baseType is unknown on empty list")
        v.SetValue([None], None)
        self.assertTrue(
            v.IsNull(), "Null test on list with a single NULL value.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.string, "baseType inherited when unspecified")
        v.SetValue(["A", "B", None], variables.BaseType.identifier)
        self.assertFalse(v.IsNull(), "Null test on non-empty list.")
        self.assertTrue(
            type(v.value) == types.ListType, "Value should be a list")
        self.assertTrue(
            v.baseType is variables.BaseType.identifier, "baseType from list")
        self.assertTrue(
            len(v.value) == 2, "NULL value should be ignored by SetValue")
        self.assertTrue(v.value[1] == u"B", "value on set")
        v.SetValue((u"C", u"D"), variables.BaseType.string)
        self.assertTrue(v.value[1] == u"D", "set from tuple")
        try:
            v.SetValue(["A", 3], variables.BaseType.string)
            self.fail("No error on mixed type values")
        except ValueError:
            pass

    def testCaseMultiple(self):
        v = variables.MultipleContainer()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(v.baseType is None, "baseType is unknown on creation")
        v = variables.MultipleContainer(variables.BaseType.identifier)
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.identifier, "baseType forced on creation")
        v.SetValue([])
        self.assertTrue(v.IsNull(), "Null test on empty list.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is variables.BaseType.identifier, "baseType inherited when unspecified")
        v.SetValue([None], variables.BaseType.string)
        self.assertTrue(
            v.IsNull(), "Null test on list with a single NULL value.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(v.baseType is variables.BaseType.string,
                        "baseType is known, NULL value in list")
        v.SetValue(["A", "A", None, "B"], variables.BaseType.identifier)
        self.assertFalse(v.IsNull(), "Null test on non-empty list.")
        self.assertTrue(
            type(v.value) == types.DictType, "Value should be a dictionary")
        self.assertTrue(
            v.baseType is variables.BaseType.identifier, "baseType from list")
        self.assertTrue(len(v.value.keys()) == 2,
                        "NULL value should be ignored by SetValue: %s" % repr(v.value))
        self.assertTrue(v.value[u'A'] == 2, "frequency of value on set")
        v.SetValue((u"C", u"D"), variables.BaseType.string)
        self.assertTrue(v.value[u"D"] == 1, "set from tuple")
        try:
            v.SetValue(["A", 3.14, "B"], variables.BaseType.string)
            self.fail("No error on mixed type values")
        except ValueError:
            pass

    def testCaseRecord(self):
        v = variables.RecordContainer()
        self.assertTrue(v.IsNull(), "Null test on creation.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is None, "baseType is unknown for record containers")
        v.SetValue({})
        self.assertTrue(v.IsNull(), "Null test on empty list.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is None, "baseType is unknown for record containers")
        v.SetValue({'x': None})
        self.assertTrue(
            v.IsNull(), "Null test on list with a single NULL value.")
        self.assertTrue(v.value is None, "Value should be None")
        self.assertTrue(
            v.baseType is None, "baseType is unknown for record containers")
        v.SetValue({
            u'x': variables.IdentifierValue(u"Hello"),
            u'y': None,
            u'pi': variables.FloatValue(3.14159)
        })
        self.assertFalse(v.IsNull(), "Null test on non-empty list.")
        self.assertTrue(
            type(v.value) == types.DictType, "Value should be a dictionary")
        self.assertTrue(
            v.baseType is None, "baseType is unknown for record containers")
        self.assertTrue(len(v.value.keys()) == 2,
                        "NULL value should be ignored by SetValue: %s" % repr(v.value))
        self.assertTrue(
            isinstance(v.value[u'pi'], variables.FloatValue), "type of pi value")
        self.assertTrue(v.value[u'pi'].value == 3.14159, "value of pi")
        # We also support direct look up of the values
        self.assertTrue(
            isinstance(v[u'pi'], variables.FloatValue), "type of pi value - direct lookup")
        self.assertTrue(
            v[u'pi'].value == 3.14159, "value of pi - direct lookup")
        # And direct assignment...
        v[u"e"] = variables.FloatValue(2.718)
        self.assertTrue(
            len(v.value.keys()) == 3, "New field added: %s" % repr(v.value))
        self.assertTrue(
            isinstance(v.value[u'e'], variables.FloatValue), "type of e value")
        self.assertTrue(v.value[u'e'].value == 2.718, "value of e")


class QTIElementTests(unittest.TestCase):

    def testCaseConstructor(self):
        e = core.QTIElement(None)


class VariableTests(unittest.TestCase):

    def testCaseValue(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        rd = doc.root.ResponseDeclaration[0].GetDefaultValue()
        self.assertTrue(
            isinstance(rd, variables.Value), "Default value not a Value")
        self.assertTrue(
            rd.Cardinality() == variables.Cardinality.single, "Single value was a container")
        self.assertTrue(
            rd.baseType == variables.BaseType.identifier, "Single default base type")
        self.assertTrue(rd.value == u"A", "Singe default value")
        rd = doc.root.ResponseDeclaration[1].GetDefaultValue()
        self.assertTrue(
            rd.Cardinality() == variables.Cardinality.ordered, "Ordered value not a container")
        self.assertTrue(
            rd.baseType == variables.BaseType.integer, "Ordered default base type")
        self.assertTrue(rd.value == [3, 2, 1], "Ordered default value")
        rd = doc.root.ResponseDeclaration[2].GetDefaultValue()
        self.assertTrue(
            rd.Cardinality() == variables.Cardinality.multiple, "Multiple value not a container")
        self.assertTrue(
            rd.baseType == variables.BaseType.float, "Multiple default base type")
        self.assertTrue(rd.value == {
                        3.0: 1, 0.1: 1, 0.04: 1, 0.001: 1, 0.0006: 1}, "Multiple default value")
        rd = doc.root.ResponseDeclaration[3].GetDefaultValue()
        self.assertTrue(
            rd.Cardinality() == variables.Cardinality.record, "Record value not a container")
        self.assertTrue(rd.baseType == None, "Record default base type")
        self.assertTrue(
            rd[u'value'].value == 3.14159, "Record default value: %s" % repr(rd[u'value']))
        rd = doc.root.ResponseDeclaration[4].GetDefaultValue()
        self.assertTrue(
            rd.Cardinality() == variables.Cardinality.single, "Single NULL value cardinality")
        self.assertTrue(
            rd.baseType == variables.BaseType.string, "Single NULL base type")
        self.assertTrue(
            rd.value is None, "Single NULL value: %s" % repr(rd.value))

    def testCaseCorrect(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        rc = doc.root.ResponseDeclaration[0].GetCorrectValue()
        self.assertTrue(
            isinstance(rc, variables.Value), "Correct value not a Value")
        self.assertTrue(
            rc.Cardinality() == variables.Cardinality.single, "Single value was a container")
        self.assertTrue(
            rc.baseType == variables.BaseType.identifier, "Single default base type")
        self.assertTrue(
            rc.value == u"A", "Singe default value: %s" % repr(rc.value))
        self.assertTrue(doc.root.ResponseDeclaration[
                        0].CorrectResponse.interpretation == "single", "Correct interpretation")
        rc = doc.root.ResponseDeclaration[1].GetCorrectValue()
        self.assertTrue(
            rc.Cardinality() == variables.Cardinality.ordered, "Ordered value not a container")
        self.assertTrue(
            rc.baseType == variables.BaseType.integer, "Ordered default base type")
        self.assertTrue(rc.value == [3, 2, 1], "Ordered default value")
        self.assertTrue(doc.root.ResponseDeclaration[
                        1].CorrectResponse.interpretation is None, "Emptyy correct interpretation")
        rc = doc.root.ResponseDeclaration[2].GetCorrectValue()
        self.assertTrue(
            rc.Cardinality() == variables.Cardinality.single, "Single NULL value cardinality")
        self.assertTrue(
            rc.baseType == variables.BaseType.string, "Single NULL base type")
        self.assertTrue(
            rc.value is None, "Single NULL value: %s" % repr(rc.value))

    def testCaseMapping(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        mapping = doc.root.ResponseDeclaration[0].Mapping
        self.assertTrue(mapping.baseType is variables.BaseType.identifier,
                        "Base type of mapping auto-discovered")
        for v, mv in {
                "A": 8.0,
                "B": 2.0,
                "C": 4.0,
                "D": 1.0,
                "ABCDE": 14.0,
                "BCDE": 6.5,
                "ABDD": 11.0,
                "": 0.0}.items():
            value = variables.MultipleContainer(mapping.baseType)
            value.SetValue(iter(v))
            mValue = mapping.MapValue(value)
            self.assertTrue(
                isinstance(mValue, variables.FloatValue), "MapValue response type")
            self.assertTrue(
                mValue.value == mv, "Mapping failed for multiple %s, returned %.1f" % (v, mValue.value))
            value = variables.OrderedContainer(mapping.baseType)
            value.SetValue(iter(v))
            mValue = mapping.MapValue(value)
            self.assertTrue(
                mValue.value == mv, "Mapping failed for ordered %s, returned %.1f" % (v, mValue.value))

    def testCaseAreaMapping(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        mapping = doc.root.ResponseDeclaration[0].AreaMapping
        for v, mv in {
                ((12, 13),): 8.0,
                ((12, 8),): 2.0,
                ((43, 13),): 4.0,
                ((42, 9),): 1.0,
                ((1, 1),): 16.0,
                ((12, 13), (11, 12),): 8.0,
                ((12, 13), (12, 8), (43, 13), (42, 9), (1, 1), (200, 200),): 20.0,
                ((12, 8), (43, 13), (42, 9), (200, 200),): 6.5,
                ((12, 13), (12, 8), (42, 9), (42, 8),): 11.0,
                (): 0.0}.items():
            value = variables.MultipleContainer(variables.BaseType.point)
            value.SetValue(iter(v))
            mValue = mapping.MapValue(value, 50, 50)
            self.assertTrue(
                isinstance(mValue, variables.FloatValue), "MapValue response type")
            self.assertTrue(
                mValue.value == mv, "AreaMapping failed for multiple %s, returned %.1f" % (v, mValue.value))
            value = variables.OrderedContainer(variables.BaseType.point)
            value.SetValue(iter(v))
            mValue = mapping.MapValue(value, 50, 50)
            self.assertTrue(
                mValue.value == mv, "Mapping failed for ordered %s, returned %.1f" % (v, mValue.value))

    def testCaseLookupTable(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        matchTable = doc.root.OutcomeDeclaration[0].LookupTable
        interpolationTable = doc.root.OutcomeDeclaration[1].LookupTable
        self.assertTrue(matchTable.baseType is variables.BaseType.identifier,
                        "Base type of matchTable auto-discovered")
        self.assertTrue(interpolationTable.baseType is variables.BaseType.identifier,
                        "Base type of interpolationTable auto-discovered")
        for rawScore, grade in {
                0: "U",
                1: "E",
                2: "E",
                3: "D",
                4: "D",
                5: "C",
                6: "C",
                7: "B",
                8: "B",
                9: "A",
                10: "A",
                -1: "U"}.items():
            value = variables.IntegerValue(rawScore)
            mapGrade = matchTable.Lookup(value)
            self.assertTrue(
                isinstance(mapGrade, variables.IdentifierValue), "Lookup response type")
            self.assertTrue(mapGrade.value == grade, "MatchTable failed for %i, returned %s" % (
                rawScore, mapGrade.value))
            try:
                value = variables.FloatValue(float(rawScore))
                mapGrade = matchTable.Lookup(value)
                self.fail("MatchTable accepted float for lookup")
            except ValueError:
                pass
            value = variables.IntegerValue(rawScore)
            mapGrade = interpolationTable.Lookup(value)
            self.assertTrue(
                isinstance(mapGrade, variables.IdentifierValue), "Lookup response type")
            self.assertTrue(mapGrade.value == grade, "InterpolationTable failed for %i, returned %s" % (
                rawScore, mapGrade.value))
            value = variables.FloatValue(float(rawScore))
            mapGrade = interpolationTable.Lookup(value)
            self.assertTrue(
                isinstance(mapGrade, variables.IdentifierValue), "Lookup response type")
            self.assertTrue(mapGrade.value == grade, "InterpolationTable failed for %i, returned %s" % (
                rawScore, mapGrade.value))

    def testCaseItemSession(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="TestCase" title="Test Case" adaptive="false" timeDependent="false">
</assessmentItem>"""
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        sessionState = variables.ItemSessionState(doc.root)
        self.assertTrue(
            sessionState.item == doc.root, "Session State item pointer")
        value = sessionState['numAttempts']
        self.assertTrue(isinstance(
            value, variables.IntegerValue), "numAttempts must be of IntegerValue type")
        self.assertTrue(value.value is None, "numAttempts non NULL")
        self.assertTrue(sessionState.IsResponse(
            'numAttempts'), "numAttempts is a response variable")
        self.assertTrue(not sessionState.IsOutcome(
            'numAttempts'), "numAttempts is not an outcome variable")
        self.assertTrue(not sessionState.IsTemplate(
            'numAttempts'), "numAttempts is not a template variable")
        value = sessionState['duration']
        self.assertTrue(isinstance(
            value, variables.DurationValue), "duration must be of DurationValue type")
        self.assertTrue(value.value is None, "duration non NULL")
        self.assertTrue(
            sessionState.IsResponse('duration'), "duration is a response variable")
        self.assertTrue(not sessionState.IsOutcome(
            'duration'), "duration is not an outcome variable")
        self.assertTrue(not sessionState.IsTemplate(
            'duration'), "duration is not a template variable")
        value = sessionState['completionStatus']
        self.assertTrue(isinstance(value, variables.IdentifierValue),
                        "completionStatus must be of IdentifierValue type")
        self.assertTrue(value.value is None, "completionStatus non NULL")
        self.assertTrue(not sessionState.IsResponse(
            'completionStatus'), "completionStatus is not a response variable")
        self.assertTrue(sessionState.IsOutcome(
            'completionStatus'), "completionStatus is an outcome variable")
        self.assertTrue(not sessionState.IsTemplate(
            'completionStatus'), "completionStatus is not a template variable")
        self.assertTrue(len(sessionState) == 3, "3 default variables")
        sessionState.BeginSession()
        self.assertTrue(
            sessionState['numAttempts'].value == 0, "numAttempts must initially be 0")
        self.assertTrue(
            sessionState['duration'].value == 0.0, "duration must initially be 0")
        self.assertTrue(sessionState[
                        'completionStatus'].value == "not_attempted", "completionStatus must initially be not_attempted")
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        sessionState = variables.ItemSessionState(doc.root)
        self.assertTrue(len(
            sessionState) == 15, "6 defined + 3 built-in variables + 1 correct + 5 defaults")
        value = sessionState['RESPONSE']
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "RESPONSE type")
        self.assertFalse(value, "RESPONSE non NULL")
        self.assertTrue(
            sessionState.IsResponse('RESPONSE'), "RESPONSE is a response variable")
        self.assertTrue(not sessionState.IsOutcome(
            'RESPONSE'), "RESPONSE is not an outcome variable")
        self.assertTrue(not sessionState.IsTemplate(
            'RESPONSE'), "RESPONSE is not a template variable")
        value = sessionState['SCORE']
        self.assertTrue(
            isinstance(value, variables.IntegerValue), "SCORE type")
        self.assertFalse(value, "SCORE non NULL")
        self.assertTrue(not sessionState.IsResponse(
            'SCORE'), "SCORE is not a response variable")
        self.assertTrue(
            sessionState.IsOutcome('SCORE'), "SCORE is an outcome variable")
        self.assertTrue(not sessionState.IsTemplate(
            'SCORE'), "SCORE is not a template variable")
        value = sessionState['SCORE1']
        self.assertTrue(
            isinstance(value, variables.IntegerValue), "SCORE1 type")
        self.assertFalse(value, "SCORE1 non NULL")
        value = sessionState['SCORE2']
        self.assertTrue(isinstance(value, variables.FloatValue), "SCORE2 type")
        self.assertFalse(value, "SCORE2 non NULL")
        value = sessionState['SCORE3']
        self.assertTrue(
            isinstance(value, variables.StringValue), "SCORE3 type")
        self.assertFalse(value, "SCORE3 non NULL")
        value = sessionState['VARIABLE']
        self.assertTrue(
            isinstance(value, variables.FloatValue), "VARIABLE type")
        self.assertTrue(value.value == 3.14159, "VARIABLE initial value")
        self.assertTrue(not sessionState.IsResponse(
            'VARIABLE'), "VARIABLE is not a response variable")
        self.assertTrue(not sessionState.IsOutcome(
            'VARIABLE'), "VARIABLE is not an outcome variable")
        self.assertTrue(
            sessionState.IsTemplate('VARIABLE'), "VARIABLE is a template variable")
        sessionState.BeginSession()
        self.assertFalse(
            sessionState['RESPONSE'], "RESPONSE initial value must be NULL")
        self.assertTrue(
            sessionState['SCORE'].value == -1, "SCORE initial value")
        self.assertTrue(
            sessionState['SCORE1'].value == 0, "SCORE1 initial value")
        self.assertTrue(
            sessionState['SCORE2'].value == 0.0, "SCORE2 initial value")
        self.assertFalse(
            sessionState['SCORE3'], "SCORE3 initial value must be NULL")
        self.assertTrue(
            sessionState['VARIABLE'].value == 3.14159, "VARIABLE initial value")
        sessionState.BeginAttempt()
        value = sessionState['numAttempts']
        self.assertTrue(
            value.value == 1, "numAttempts set to 1 at start of attempt")
        value = sessionState['RESPONSE']
        self.assertTrue(
            value.value == u"A", "RESPONSE set to default at start of first attempt")
        value.SetValue(u"B")
        value = sessionState['completionStatus']
        self.assertTrue(value.value == u"unknown",
                        "completionStatus set to unknown at start of first attempt: %s" % value.value)
        value.SetValue("completed")
        sessionState.EndAttempt()
        sessionState.BeginAttempt()
        value = sessionState['numAttempts']
        self.assertTrue(value.value == 2, "numAttempts incremented")
        value = sessionState['completionStatus']
        self.assertTrue(
            value.value == u"completed", "completionStatus keeps its value")
        value = sessionState['RESPONSE']
        self.assertTrue(value.value == u"B", "RESPONSE keeps its value")

    def testCaseTestSession(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
	identifier="http://www.example.com/assessmentTest" title="Assessment Test Case"
	toolName="Pyslet" toolVersion="0.3">
	<testPart identifier="PartI" navigationMode="nonlinear" submissionMode="individual">
		<assessmentSection identifier="SectionA" title="Section A" visible="true"/>
	</testPart>
</assessmentTest>"""
        doc = core.QTIDocument()
        doc.Read(src=StringIO(SAMPLE))
        form = tests.TestForm(doc.root)
        sessionState = variables.TestSessionState(form)
        self.assertTrue(
            sessionState.test == doc.root, "Session State test pointer")
        self.assertTrue(
            sessionState.form == form, "Session State form pointer")
        value = sessionState['duration']
        self.assertTrue(isinstance(
            value, variables.DurationValue), "duration must be of DurationValue type")
        self.assertTrue(value.value is None, "duration non NULL")
        self.assertTrue(
            sessionState.IsResponse('duration'), "duration is a response variable")
        self.assertTrue(not sessionState.IsOutcome(
            'duration'), "duration is not an outcome variable")
        self.assertTrue(not sessionState.IsTemplate(
            'duration'), "duration is not a template variable")
        value = sessionState['PartI.duration']
        self.assertTrue(isinstance(
            value, variables.DurationValue), "duration must be of DurationValue type")
        self.assertTrue(value.value is None, "duration non NULL")
        value = sessionState['SectionA.duration']
        self.assertTrue(isinstance(
            value, variables.DurationValue), "duration must be of DurationValue type")
        self.assertTrue(value.value is None, "duration non NULL")
        self.assertTrue(len(sessionState) == 3, "3 default variables")
        sessionState.BeginSession(sessionState.key)
        self.assertTrue(
            sessionState['duration'].value == 0.0, "duration must initially be 0")
        self.assertTrue(sessionState.t <= time.time() and sessionState.t >= time.time(
        ) - 1.0, "test session took more than 1s to start: %f" % (time.time() - sessionState.t))
        self.assertTrue(
            type(sessionState.key) == types.UnicodeType, "key should be a string")
        self.assertTrue(
            len(sessionState.key) >= 56, "key should be 56 bytes or more")


class ResponseProcessingTests(unittest.TestCase):

    def setUp(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
    identifier="TestCase" title="Test Case" adaptive="false" timeDependent="false">
    <responseDeclaration identifier="TESTCASE" cardinality="single" baseType="identifier"/>
    <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
        <defaultValue>
            <value>A</value>
        </defaultValue>
        <correctResponse>
            <value>B</value>
        </correctResponse>
        <mapping defaultValue="-1.0">
            <mapEntry mapKey="A" mappedValue="3.14"/>
            <mapEntry mapKey="B" mappedValue="5"/>
        </mapping>
    </responseDeclaration>
    <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="float">
        <defaultValue>
            <value>0.5</value>
        </defaultValue>
    </outcomeDeclaration>
    <outcomeDeclaration identifier="N" cardinality="single" baseType="integer">
        <defaultValue>
            <value>0</value>
        </defaultValue>
    </outcomeDeclaration>
    <templateDeclaration identifier="T" cardinality="single" baseType="identifier"/>
    <responseProcessing>
        <responseCondition>
            <responseIf>
                <match>
                    <variable identifier="TESTCASE"/>
                    <baseValue baseType="identifier">CASE_1</baseValue>
                </match>
                <exitResponse/>
            </responseIf>
            <responseElseIf>
                <match>
                    <variable identifier="TESTCASE"/>
                    <baseValue baseType="identifier">CASE_2</baseValue>
                </match>
                <setOutcomeValue identifier="SCORE">
                    <mapResponse identifier="RESPONSE"/>
                </setOutcomeValue>
            </responseElseIf>
            <responseElse>
                <setOutcomeValue identifier="SCORE">
                    <baseValue baseType="float">3</baseValue>
                </setOutcomeValue>
            </responseElse>
        </responseCondition>
        <setOutcomeValue identifier="N">
            <sum>
                <variable identifier="N"/>
                <baseValue baseType="integer">1</baseValue>
            </sum>
        </setOutcomeValue>
    </responseProcessing>
</assessmentItem>"""
        self.doc = core.QTIDocument()
        self.doc.Read(src=StringIO(SAMPLE))
        self.sessionState = variables.ItemSessionState(self.doc.root)
        self.sessionState.BeginSession()

    def tearDown(self):
        pass

    def testCaseNonAdaptive(self):
        self.sessionState.BeginAttempt()
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_1")
        self.assertTrue(
            self.sessionState["SCORE"].value == 0.5, "Initial score value")
        self.assertTrue(self.sessionState["N"].value == 0, "Initial N value")
        self.assertTrue(
            self.sessionState["numAttempts"].value == 1, "Initial numAttempts")
        self.sessionState.EndAttempt()
        self.assertTrue(
            self.sessionState["SCORE"].value == 0.5, "Initial score value")
        self.assertTrue(self.sessionState["N"].value == 0, "CASE_1 N value: %s" % repr(
            self.sessionState["N"].value))
        self.sessionState.BeginAttempt()
        self.assertTrue(
            self.sessionState["numAttempts"].value == 2, "numAttempts=2")
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_2")
        self.sessionState.EndAttempt()
        self.assertTrue(
            self.sessionState["SCORE"].value == 3.14, "CASE_2 score")
        self.assertTrue(self.sessionState["N"].value == 1, "CASE_2 N value")
        self.sessionState.BeginAttempt()
        self.assertTrue(
            self.sessionState["numAttempts"].value == 3, "numAttempts=3")
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_3")
        self.sessionState.EndAttempt()
        self.assertTrue(
            self.sessionState["SCORE"].value == 3.0, "CASE_3 score")
        self.assertTrue(self.sessionState["N"].value == 1, "CASE_3 N value: %s" % repr(
            self.sessionState["N"].value))

    def testCaseAdaptive(self):
        self.sessionState.BeginAttempt()
        self.sessionState.item.adaptive = True
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_1")
        self.assertTrue(self.sessionState["N"].value == 0, "Initial N value")
        self.assertTrue(
            self.sessionState["numAttempts"].value == 1, "Initial numAttempts")
        self.sessionState.EndAttempt()
        self.assertTrue(self.sessionState["N"].value == 0, "CASE_1 N value: %s" % repr(
            self.sessionState["N"].value))
        self.sessionState.BeginAttempt()
        self.assertTrue(
            self.sessionState["numAttempts"].value == 2, "numAttempts=2")
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_2")
        self.sessionState.EndAttempt()
        self.assertTrue(self.sessionState["N"].value == 1, "CASE_2 N value")
        self.sessionState.BeginAttempt()
        self.assertTrue(
            self.sessionState["numAttempts"].value == 3, "numAttempts=3")
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_3")
        self.sessionState.EndAttempt()
        self.assertTrue(self.sessionState["N"].value == 2, "CASE_3 N value: %s" % repr(
            self.sessionState["N"].value))

    def testCaseError(self):
        rule = processing.SetOutcomeValue(None)
        rule.identifier = "RESPONSE"
        v = rule.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.identifier
        v.AddData("A")
        try:
            rule.Run(self.sessionState)
            self.fail("<setOutcomeValue> sets RESPONSE")
        except core.ProcessingError:
            pass
        rule.identifier = "T"
        try:
            rule.Run(self.sessionState)
            self.fail("<setOutcomeValue> sets T")
        except core.ProcessingError:
            pass


class TemplateProcessingTests(unittest.TestCase):

    def setUp(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
    </responseDeclaration>
    <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="float">
        <defaultValue>
            <value>0.5</value>
        </defaultValue>
    </outcomeDeclaration>
    <outcomeDeclaration identifier="GRADE" cardinality="single" baseType="identifier"/>
    <templateDeclaration identifier="TESTCASE" cardinality="single" baseType="identifier"/>
    <templateDeclaration identifier="T" cardinality="single" baseType="boolean"/>
    <templateProcessing>
        <templateCondition>
            <templateIf>
                <match>
                    <variable identifier="TESTCASE"/>
                    <baseValue baseType="identifier">CASE_1</baseValue>
                </match>
                <exitTemplate/>
            </templateIf>
            <templateElseIf>
                <match>
                    <variable identifier="TESTCASE"/>
                    <baseValue baseType="identifier">CASE_2</baseValue>
                </match>
                <setCorrectResponse identifier="RESPONSE">
                    <baseValue baseType="identifier">A</baseValue>
                </setCorrectResponse>
            </templateElseIf>
            <templateElseIf>
                <match>
                    <variable identifier="TESTCASE"/>
                    <baseValue baseType="identifier">CASE_3</baseValue>
                </match>
                <setDefaultValue identifier="RESPONSE">
                    <baseValue baseType="identifier">B</baseValue>
                </setDefaultValue>
            </templateElseIf>
            <templateElse>
                <setDefaultValue identifier="SCORE">
                    <baseValue baseType="float">0.0</baseValue>
                </setDefaultValue>
            </templateElse>
        </templateCondition>
        <setTemplateValue identifier="T">
            <match>
                <correct identifier="RESPONSE"/>
                <default identifier="RESPONSE"/>
            </match>
        </setTemplateValue>
    </templateProcessing>
</assessmentItem>"""
        self.doc = core.QTIDocument()
        self.doc.Read(src=StringIO(SAMPLE))
        self.sessionState = variables.ItemSessionState(self.doc.root)

    def tearDown(self):
        pass

    def testCase1(self):
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_1")
        self.sessionState.SelectClone()
        v = self.sessionState['T']
        self.assertFalse(v, "CASE_1 result: %s" % repr(v.value))
        self.sessionState.BeginSession()
        # outcomes have their defaults
        v = self.sessionState['SCORE']
        self.assertTrue(
            v.value == 0.5, "CASE_1 default SCORE: %s" % repr(v.value))
        self.sessionState.BeginAttempt()
        # responses have their defaults
        v = self.sessionState['RESPONSE']
        self.assertTrue(
            v.value == u"A", "CASE_1 default RESPONSE: %s" % repr(v.value))

    def testCase2(self):
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_2")
        self.sessionState.SelectClone()
        v = self.sessionState['T']
        self.assertTrue(v.value is True, "CASE_2 result: %s" % repr(v.value))
        self.sessionState.BeginSession()
        # outcomes have their defaults
        v = self.sessionState['SCORE']
        self.assertTrue(
            v.value == 0.5, "CASE_2 default SCORE: %s" % repr(v.value))
        self.sessionState.BeginAttempt()
        # responses have their defaults
        v = self.sessionState['RESPONSE']
        self.assertTrue(
            v.value == u"A", "CASE_2 default RESPONSE: %s" % repr(v.value))

    def testCase3(self):
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_3")
        self.sessionState.SelectClone()
        v = self.sessionState['T']
        self.assertTrue(v.value is True, "CASE_3 result: %s" % repr(v.value))
        self.sessionState.BeginSession()
        # outcomes have their defaults
        v = self.sessionState['SCORE']
        self.assertTrue(
            v.value == 0.5, "CASE_3 default SCORE: %s" % repr(v.value))
        self.sessionState.BeginAttempt()
        # responses have their defaults
        v = self.sessionState['RESPONSE']
        self.assertTrue(
            v.value == u"B", "CASE_3 default RESPONSE: %s" % repr(v.value))

    def testCase4(self):
        self.sessionState["TESTCASE"] = variables.IdentifierValue("CASE_4")
        self.sessionState.SelectClone()
        v = self.sessionState['T']
        self.assertTrue(v.value is False, "CASE_4 result: %s" % repr(v.value))
        self.sessionState.BeginSession()
        # outcomes have their defaults
        v = self.sessionState['SCORE']
        self.assertTrue(
            v.value == 0.0, "CASE_4 default SCORE: %s" % repr(v.value))
        self.sessionState.BeginAttempt()
        # responses have their defaults
        v = self.sessionState['RESPONSE']
        self.assertTrue(
            v.value == u"A", "CASE_4 default RESPONSE: %s" % repr(v.value))

    def testCaseSetTemplateValue(self):
        rule = processing.SetTemplateValue(None)
        rule.identifier = "RESPONSE"
        v = rule.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.identifier
        v.AddData("A")
        try:
            rule.Run(self.sessionState)
            self.fail("<setTemplateValue> sets RESPONSE")
        except core.ProcessingError:
            pass
        rule.identifier = "GRADE"
        try:
            rule.Run(self.sessionState)
            self.fail("<setTemplateValue> sets SCORE")
        except core.ProcessingError:
            pass
        rule.identifier = "TESTCASE"
        rule.Run(self.sessionState)

    def testCaseSetCorrectResponse(self):
        rule = processing.SetCorrectResponse(None)
        rule.identifier = "GRADE"
        v = rule.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.identifier
        v.AddData("A")
        try:
            rule.Run(self.sessionState)
            self.fail("<setCorrectResponse> sets GRADE")
        except core.ProcessingError:
            pass
        rule.identifier = "TESTCASE"
        try:
            rule.Run(self.sessionState)
            self.fail("<setCorrectResponse> sets TESTCASE")
        except core.ProcessingError:
            pass
        rule.identifier = "RESPONSE"
        rule.Run(self.sessionState)

    def testCaseSetDefaultValue(self):
        rule = processing.SetDefaultValue(None)
        rule.identifier = "TESTCASE"
        v = rule.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.identifier
        v.AddData("A")
        try:
            rule.Run(self.sessionState)
            self.fail("<setDefaultValue> sets TESTCASE")
        except core.ProcessingError:
            pass
        rule.identifier = "RESPONSE"
        rule.Run(self.sessionState)
        rule.identifier = "GRADE"
        rule.Run(self.sessionState)


class ExpressionTests(unittest.TestCase):

    def setUp(self):
        SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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
        self.doc = core.QTIDocument()
        self.doc.Read(src=StringIO(SAMPLE))
        self.sessionState = variables.ItemSessionState(self.doc.root)
        self.sessionState.BeginSession()
        self.sessionState.BeginAttempt()

    def tearDown(self):
        pass

    def testCaseBaseValue(self):
        e = expressions.BaseValue(None)
        e.baseType = variables.BaseType.point
        e.AddData("3 1")
        e.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.PointValue), "BaseValue type")
        self.assertTrue(
            value.value == (3, 1), "BaseValue value: %s" % repr(value.value))

    def testCaseVariable(self):
        e = expressions.Variable(None)
        e.identifier = 'RESPONSE'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "Variable type")
        self.assertTrue(
            value.value == u"A", "Variable value: %s" % repr(value.value))
        try:
            e.identifier = 'UNDECLARED'
            value = e.Evaluate(self.sessionState)
            self.fail("Variable UNDECLARED")
        except core.ProcessingError:
            pass
        # TODO: add tests for outcome processing lookups (when
        # AssessmentSessionState is defined)

    def testCaseDefault(self):
        e = expressions.Default(None)
        e.identifier = 'RESPONSE'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "Variable type")
        self.assertTrue(
            value.value == u"A", "Variable value: %s" % repr(value.value))
        e.identifier = 'SCORE1'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.StringValue), "Variable type")
        self.assertFalse(value, "NULL default value: %s" % repr(value.value))
        try:
            e.identifier = 'UNDECLARED'
            value = e.Evaluate(self.sessionState)
            self.fail("Default UNDECLARED")
        except core.ProcessingError:
            pass

    def testCaseCorrect(self):
        e = expressions.Correct(None)
        e.identifier = 'RESPONSE'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "Correct type")
        self.assertTrue(
            value.value == u"B", "Correct value: %s" % repr(value.value))
        try:
            e.identifier = 'UNDECLARED'
            value = e.Evaluate(self.sessionState)
            self.fail("Correct UNDECLARED")
        except core.ProcessingError:
            pass
        try:
            e.identifier = 'SCORE'
            value = e.Evaluate(self.sessionState)
            self.fail("Correct value of outcome")
        except core.ProcessingError:
            pass

    def testCaseMapResponse(self):
        e = expressions.MapResponse(None)
        e.identifier = 'RESPONSE'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.FloatValue), "MapResponse type")
        self.assertTrue(
            value.value == 3.14, "Mapped value: %s" % repr(value.value))
        try:
            e.identifier = 'RESPONSE1'
            value = e.Evaluate(self.sessionState)
            self.fail("MapResponse with no mapping")
        except core.ProcessingError:
            pass
        try:
            e.identifier = 'SCORE'
            value = e.Evaluate(self.sessionState)
            self.fail("MapResponse value of outcome")
        except core.ProcessingError:
            pass

    def testCaseMapResponsePoint(self):
        e = expressions.MapResponsePoint(None)
        e.identifier = 'RESPONSE1'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.FloatValue), "MapResponsePoint type")
        self.assertTrue(
            value.value == 3.14, "Mapped value: %s" % repr(value.value))
        try:
            e.identifier = 'RESPONSE'
            value = e.Evaluate(self.sessionState)
            self.fail("MapResponsePoint with wrong baseType")
        except core.ProcessingError:
            pass
        try:
            e.identifier = 'RESPONSE2'
            value = e.Evaluate(self.sessionState)
            self.fail("MapResponsePoint with no areaMapping")
        except core.ProcessingError:
            pass
        try:
            e.identifier = 'SCORE'
            value = e.Evaluate(self.sessionState)
            self.fail("MapResponsePoint with outcome")
        except core.ProcessingError:
            pass

    def testCaseNull(self):
        e = expressions.Null(None)
        value = e.Evaluate(self.sessionState)
        self.assertTrue(isinstance(value, variables.Value), "Null type")
        self.assertTrue(value.baseType is None, "Null base type: %s" %
                        variables.BaseType.EncodeValue(value.baseType))
        self.assertTrue(value.value is None, "Null value: %s" %
                        repr(value.value))
        self.assertFalse(value, "Null is null")

    def testCaseRandomInteger(self):
        e = expressions.RandomInteger(None)
        e.min = "2"
        e.max = "11"
        e.step = "3"
        gotValue = {}
        for i in xrange(100):
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                isinstance(value, variables.IntegerValue), "RandomInteger type")
            self.assertTrue(
                value.value in (2, 5, 8, 11), "RandomInteger value: %s" % repr(value.value))
            gotValue[value.value] = True
        for i in (2, 5, 8, 11):
            self.assertTrue(
                i in gotValue, "RandomInteger failed with p=0.000000000001, really?")
        # TODO: also supports template references

    def testCaseRandomFloat(self):
        e = expressions.RandomFloat(None)
        e.min = "5.0"
        e.max = "5.5"
        gotValue = {}
        for i in xrange(200):
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                isinstance(value, variables.FloatValue), "RandomFloat type")
            self.assertTrue(value.value >= 5.0 and value.value <=
                            5.5, "RandomFloat value: %s" % repr(value.value))
            v = "%.1f" % value.value
            self.assertTrue(
                v in ("5.0", "5.1", "5.2", "5.3", "5.4", "5.5"), "RandomFloat value: %s" % v)
            gotValue[v] = True
        for i in ("5.0", "5.1", "5.2", "5.3", "5.4", "5.5"):
            self.assertTrue(
                i in gotValue, "RandomFloat failed with p=0.0000000014, really?")
        # TODO: also supports template references

    def testCaseMultiple(self):
        e = expressions.Multiple(None)
        # check the null case
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.MultipleContainer), "Multiple type")
        self.assertTrue(
            value.Cardinality() == variables.Cardinality.multiple, "Multiple cardinality")
        self.assertTrue(
            value.baseType is None, "Multiple with unknown base type")
        # check that sub-expressions with NULL values are ignored
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.integer
        v1.AddData("1")
        v1.ContentChanged()
        v2 = e.ChildElement(expressions.Null)
        v3 = e.ChildElement(expressions.BaseValue)
        v3.baseType = variables.BaseType.integer
        v3.AddData("3")
        v3.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.MultipleContainer), "Multiple type")
        self.assertTrue(
            value.baseType == variables.BaseType.integer, "Multiple base type")
        self.assertTrue(
            value.value == {1: 1, 3: 1}, "Multiple value: %s" % repr(value.value))
        v4 = e.ChildElement(expressions.Multiple)
        v4_1 = v4.ChildElement(expressions.BaseValue)
        v4_1.baseType = variables.BaseType.integer
        v4_1.AddData("3")
        v4_1.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == {1: 1, 3: 2}, "Multiple in Multiple value: %s" % repr(value.value))
        # check that mixed base types raise an error
        v5 = e.ChildElement(expressions.BaseValue)
        v5.baseType = variables.BaseType.float
        v5.AddData("3.1")
        v5.ContentChanged()
        try:
            value = e.Evaluate(self.sessionState)
            self.fail("Multiple with mixed base types")
        except core.ProcessingError:
            pass

    def testCaseOrdered(self):
        e = expressions.Ordered(None)
        # check the null case
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.OrderedContainer), "Ordered cardinality")
        self.assertTrue(
            value.baseType is None, "Ordered with unknown base type")
        # check that sub-expressions with NULL values are ignored
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.integer
        v1.AddData("1")
        v1.ContentChanged()
        v2 = e.ChildElement(expressions.Null)
        v3 = e.ChildElement(expressions.BaseValue)
        v3.baseType = variables.BaseType.integer
        v3.AddData("3")
        v3.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.OrderedContainer), "Ordered type")
        self.assertTrue(
            value.baseType == variables.BaseType.integer, "Ordered base type")
        self.assertTrue(
            value.value == [1, 3], "Ordered value: %s" % repr(value.value))
        v4 = e.ChildElement(expressions.Ordered)
        v4_1 = v4.ChildElement(expressions.BaseValue)
        v4_1.baseType = variables.BaseType.integer
        v4_1.AddData("3")
        v4_1.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == [1, 3, 3], "Ordered in Ordered value: %s" % repr(value.value))
        # check that mixed base types raise an error
        v5 = e.ChildElement(expressions.BaseValue)
        v5.baseType = variables.BaseType.float
        v5.AddData("3.1")
        v5.ContentChanged()
        try:
            value = e.Evaluate(self.sessionState)
            self.fail("Ordered with mixed base types")
        except core.ProcessingError:
            pass

    def testCaseContainerSize(self):
        e = expressions.ContainerSize(None)
        # check the null case
        eo = e.ChildElement(expressions.Ordered)
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IntegerValue), "ContainerSize type")
        self.assertTrue(value.value == 0, "ContainerSize of NULL value")
        for i in xrange(5):
            v = eo.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.integer
            v.AddData("1")
            v.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == 5, "ContainerSize of ordered value")
        e = expressions.ContainerSize(None)
        em = e.ChildElement(expressions.Multiple)
        for i in xrange(6):
            v = em.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.integer
            v.AddData(str(i // 2))
            v.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == 6, "ContainerSize of multiple value")
        # check that single values raise an error
        e = expressions.ContainerSize(None)
        es = e.ChildElement(expressions.BaseValue)
        es.baseType = variables.BaseType.integer
        es.AddData("3")
        es.ContentChanged()
        try:
            value = e.Evaluate(self.sessionState)
            self.fail("ContainerSize with singe value")
        except core.ProcessingError:
            pass

    def testCaseIsNull(self):
        e = expressions.IsNull(None)
        e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.BooleanValue), "IsNull type")
        self.assertTrue(
            value.value == True, "IsNull value (on Null): %s" % repr(value.value))
        self.assertTrue(value, "IsNull evaluates to True")
        e = expressions.IsNull(None)
        b = e.ChildElement(expressions.BaseValue)
        b.baseType = variables.BaseType.boolean
        b.AddData("true")
        b.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.BooleanValue), "IsNull type")
        self.assertTrue(
            value.value == False, "IsNull value (on non-Null): %s" % repr(value.value))
        self.assertTrue(value, "IsNull value always evaluates to True")
        # Note that empty containers and empty strings are both treated as
        # NULL.
        e = expressions.IsNull(None)
        b = e.ChildElement(expressions.BaseValue)
        b.baseType = variables.BaseType.string
        b.AddData("")
        b.ContentChanged()
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "IsNull value (empty string): %s" % repr(value.value))
        e = expressions.IsNull(None)
        b = e.ChildElement(expressions.Multiple)
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "IsNull value (empty container): %s" % repr(value.value))

    def testCaseIndex(self):
        e = expressions.Index(None)
        e.n = 2
        v = e.ChildElement(expressions.Variable)
        v.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "Index type")
        self.assertTrue(value.value == u"B", "Index value: %s" %
                        repr(value.value))
        e.n = 4
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "Index type")
        self.assertFalse(value, "Index out of bounds is False")
        self.assertTrue(
            value.value == None, "Index out of bounds: %s" % repr(value.value))
        # n must be a positive integer
        try:
            e.n = 0
            value = e.Evaluate(self.sessionState)
            self.fail("Index 0")
        except core.ProcessingError:
            pass
        try:
            e.n = -1
            value = e.Evaluate(self.sessionState)
            self.fail("Index -1")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Index(None)
            e.n = 1
            v = e.ChildElement(expressions.Variable)
            v.identifier = 'RESPONSE'
            value = e.Evaluate(self.sessionState)
            self.fail("Index of single value")
        except core.ProcessingError:
            pass

    def testCaseFieldValue(self):
        e = expressions.FieldValue(None)
        e.fieldIdentifier = "unknown"
        v = e.ChildElement(expressions.Variable)
        v.identifier = 'RESPONSE4'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.baseType is None, "fieldValue type on unknown")
        self.assertFalse(value, "fieldValue out of bounds is False")
        e.fieldIdentifier = "fieldA"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.IdentifierValue), "fieldValue type")
        self.assertTrue(
            value.value == u"A", "fieldValue identifier: %s" % repr(value.value))
        e.fieldIdentifier = "pi"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            isinstance(value, variables.FloatValue), "fieldValue type: float")
        self.assertTrue(
            value.value == 3.14159, "fieldValue float: %s" % repr(value.value))
        try:
            e = expressions.FieldValue(None)
            e.fieldIdentifier = "fieldA"
            v = e.ChildElement(expressions.Variable)
            v.identifier = 'RESPONSE'
            value = e.Evaluate(self.sessionState)
            self.fail("fieldValue of single value")
        except core.ProcessingError:
            pass

    def testCaseRandom(self):
        e = expressions.Random(None)
        em = e.ChildElement(expressions.Null)
        # check the null case
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Random(NULL) is NULL")
        self.assertTrue(value.baseType is None, "Random(NULL) base type")
        self.assertTrue(
            value.Cardinality() == variables.Cardinality.single, "Random(NULL) base type")
        e = expressions.Random(None)
        em = e.ChildElement(expressions.Multiple)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Random(empty multiple container) is NULL")
        self.assertTrue(value.baseType is None, "Random(NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Random(NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        for i in (2, 5, 8, 11, 8):
            v = em.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.integer
            v.AddData(str(i))
        gotValue = {}
        for i in xrange(100):
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                isinstance(value, variables.IntegerValue), "Random(Multiple) type")
            self.assertTrue(
                value.value in (2, 5, 8, 11), "Random(Multiple) value: %s" % repr(value.value))
            gotValue[value.value] = gotValue.get(value.value, 0) + 1
        for i in (2, 5, 8, 11):
            self.assertTrue(
                i in gotValue, "Random(Multiple) failed with p=0.000000001, really?")
        for i in xrange(200):
            # do another 200 iterations
            value = e.Evaluate(self.sessionState)
            gotValue[value.value] = gotValue.get(value.value, 0) + 1
        # we can be pretty sure that f(8) > all the rest
        for i in (2, 5, 11):
            self.assertTrue(gotValue[8] > gotValue[
                            i], "Multiple element frequency test! %s" % repr(gotValue))
        e = expressions.Random(None)
        eo = e.ChildElement(expressions.Ordered)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Random(empty ordered container) is NULL")
        self.assertTrue(value.baseType is None, "Random(NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Random(NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        for i in ("A", "B", "C", "D", "B"):
            v = eo.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.identifier
            v.AddData(i)
        gotValue = {}
        for i in xrange(200):
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                isinstance(value, variables.IdentifierValue), "Random(Ordered) type")
            self.assertTrue(value.value in (
                "A", "B", "C", "D"), "Random(Ordered) value: %s" % repr(value.value))
            gotValue[value.value] = gotValue.get(value.value, 0) + 1
        for i in ("A", "B", "C", "D"):
            self.assertTrue(
                i in gotValue, "Random(Ordered) failed with p=4E-25, really?")
        # we now test that f("B") is reasonable
        self.assertTrue(gotValue[
                        "B"] > 51, "Ordered element frequency test, F(51; n,p) <= 0.0001; F('B')=%i" % gotValue["B"])
        try:
            e = expressions.Random(None)
            er = e.ChildElement(expressions.Variable)
            er.identifier = 'RESPONSE4'
            value = e.Evaluate(self.sessionState)
            self.fail("Random(Record)")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Random(None)
            v = e.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.identifier
            v.AddData("FAIL")
            value = e.Evaluate(self.sessionState)
            self.fail("Random(single)")
        except core.ProcessingError:
            pass

    def testCaseMember(self):
        e = expressions.Member(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Member(Null,RESPONSE3) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "Member(Null,RESPONSE3) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Member(NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Member(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("B")
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Member('B',NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "Member('B',NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Member('B',NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Member(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Member(NULL,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "Member(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Member(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        try:
            e = expressions.Member(None)
            v1 = e.ChildElement(expressions.Variable)
            v1.identifier = 'RESPONSE3'
            v2 = e.ChildElement(expressions.Variable)
            v2.identifier = 'RESPONSE3'
            value = e.Evaluate(self.sessionState)
            self.fail("Member(RESPONSE3,RESPONSE3)")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Member(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("B")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.identifier
            v2.AddData("B")
            value = e.Evaluate(self.sessionState)
            self.fail("Member('B','B')")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Member(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.duration
            v1.AddData("3.14")
            v2 = e.ChildElement(expressions.Ordered)
            v21 = v2.ChildElement(expressions.BaseValue)
            v21.baseType = variables.BaseType.duration
            v21.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.fail("Member(duration,Ordered(duration))")
        except core.ProcessingError:
            pass
        e = expressions.Member(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("B")
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "Member('B',RESPONSE3)")
        v1.SetValue("D")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "Member('D',RESPONSE3)")

    def testCaseDelete(self):
        e = expressions.Delete(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Delete(Null,RESPONSE3) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.identifier, "Delete(Null,RESPONSE3) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.ordered,
                        "Delete(NULL,RESPONSE3) cardinality, found %s" % variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Delete(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("B")
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Delete('B',NULL) is NULL")
        self.assertTrue(
            isinstance(value, variables.Container), "Delete('B',NULL) class")
        self.assertTrue(
            value.baseType is variables.BaseType.identifier, "Delete('B',NULL) base type")
        self.assertTrue(value.Cardinality() == None, "Delete('B',NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Delete(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Delete(NULL,NULL) is NULL")
        self.assertTrue(
            isinstance(value, variables.Container), "Delete(NULL,NULL) class")
        self.assertTrue(value.baseType is None, "Delete(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == None, "Delete(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        try:
            e = expressions.Delete(None)
            v1 = e.ChildElement(expressions.Variable)
            v1.identifier = 'RESPONSE3'
            v2 = e.ChildElement(expressions.Variable)
            v2.identifier = 'RESPONSE3'
            value = e.Evaluate(self.sessionState)
            self.fail("Delete(RESPONSE3,RESPONSE3)")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Delete(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("B")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.identifier
            v2.AddData("B")
            value = e.Evaluate(self.sessionState)
            self.fail("Delete('B','B')")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Delete(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.duration
            v1.AddData("3.14")
            v2 = e.ChildElement(expressions.Ordered)
            v21 = v2.ChildElement(expressions.BaseValue)
            v21.baseType = variables.BaseType.duration
            v21.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.fail("Delete(duration,Ordered(duration))")
        except core.ProcessingError:
            pass
        e = expressions.Delete(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("B")
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.baseType is variables.BaseType.identifier, "Delete('B',RESPONSE3) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.ordered,
                        "Delete('B',RESPONSE3) cardinality, found %s" % variables.Cardinality.EncodeValue(value.Cardinality()))
        self.assertTrue(value.value == ["A", "C"], "Delete('B',RESPONSE3)")
        v1.SetValue("D")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == ["A", "B", "C"], "Delete('D',RESPONSE3)")
        e = expressions.Delete(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("B")
        v2 = e.ChildElement(expressions.Multiple)
        for i in ("A", "B", "C", "B", "A"):
            v21 = v2.ChildElement(expressions.BaseValue)
            v21.baseType = variables.BaseType.identifier
            v21.AddData(i)
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.Cardinality() == variables.Cardinality.multiple,
                        "Delete('B',{'A','B','C','D'}) cardinality, found %s" % variables.Cardinality.EncodeValue(value.Cardinality()))
        self.assertTrue(
            value.value == {"A": 2, "C": 1}, "Delete('B',{'A','B','C','D'})")

    def testCaseContains(self):
        e = expressions.Contains(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Contains(Null,RESPONSE3) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "Contains(Null,RESPONSE3) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Contains(NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Contains(None)
        v1 = e.ChildElement(expressions.Variable)
        v1.identifier = 'RESPONSE3'
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Contains(RESPONSE3,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "Contains(RESPONSE3,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Contains(RESPONSE3,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Contains(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "Contains(NULL,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "Contains(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "Contains(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Contains(None)
        v1 = e.ChildElement(expressions.Variable)
        v1.identifier = 'RESPONSE3'
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "Contains(RESPONSE3,RESPONSE3)")
        try:
            e = expressions.Contains(None)
            v1 = e.ChildElement(expressions.Multiple)
            v2 = e.ChildElement(expressions.Variable)
            v2.identifier = 'RESPONSE3'
            value = e.Evaluate(self.sessionState)
            self.fail("Contains(Multiple,RESPONSE3)")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Contains(None)
            v1 = e.ChildElement(expressions.Ordered)
            v11 = v1.ChildElement(expressions.BaseValue)
            v11.baseType = variables.BaseType.duration
            v11.AddData("3.14")
            v2 = e.ChildElement(expressions.Ordered)
            v21 = v2.ChildElement(expressions.BaseValue)
            v21.baseType = variables.BaseType.duration
            v21.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.fail("Contains(Ordered(duration),Ordered(duration))")
        except core.ProcessingError:
            pass
        e = expressions.Contains(None)
        v1 = e.ChildElement(expressions.Ordered)
        v11 = v1.ChildElement(expressions.BaseValue)
        v11.baseType = variables.BaseType.identifier
        v11.AddData("C")
        v12 = v1.ChildElement(expressions.BaseValue)
        v12.baseType = variables.BaseType.identifier
        v12.AddData("A")
        v2 = e.ChildElement(expressions.Variable)
        v2.identifier = 'RESPONSE3'
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "Contains(('C','A'),RESPONSE3)")
        e = expressions.Contains(None)
        v1 = e.ChildElement(expressions.Multiple)
        v11 = v1.ChildElement(expressions.BaseValue)
        v11.baseType = variables.BaseType.identifier
        v11.AddData("C")
        v12 = v1.ChildElement(expressions.BaseValue)
        v12.baseType = variables.BaseType.identifier
        v12.AddData("C")
        v13 = v1.ChildElement(expressions.BaseValue)
        v13.baseType = variables.BaseType.identifier
        v13.AddData("A")
        v2 = e.ChildElement(expressions.Multiple)
        v21 = v2.ChildElement(expressions.BaseValue)
        v21.baseType = variables.BaseType.identifier
        v21.AddData("A")
        v22 = v2.ChildElement(expressions.BaseValue)
        v22.baseType = variables.BaseType.identifier
        v22.AddData("B")
        v23 = v2.ChildElement(expressions.BaseValue)
        v23.baseType = variables.BaseType.identifier
        v23.AddData("C")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "Contains(('C','C','A'),('A','B','C')")
        v24 = v2.ChildElement(expressions.BaseValue)
        v24.baseType = variables.BaseType.identifier
        v24.AddData("C")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "Contains(('C','C','A'),('A','B','C','C')")

    def testCaseSubstring(self):
        e = expressions.SubString(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.string
        v2.AddData("Shell")
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "substring(Null,'Shell') is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "substring(Null,'Shell') base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "substring(Null,'Shell') cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.SubString(None)
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.string
        v2.AddData("Shell")
        v1 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "substring('Shell',NULL) is NULL")
        e = expressions.SubString(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "substring(NULL,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "substring(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "substring(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.SubString(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.string
        v1.AddData("Hell")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.string
        v2.AddData("Shell")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "substring('Hell','Shell')")
        e.caseSensitive = False
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "substring('Hell','Shell')")
        try:
            e = expressions.SubString(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("hell")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.identifier
            v2.AddData("Shell")
            value = e.Evaluate(self.sessionState)
            self.fail("substring(identifier,identifier)")
        except core.ProcessingError:
            pass

    def testCaseNot(self):
        e = expressions.Not(None)
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "not(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "not(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "not(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Not(None)
        v = e.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.boolean
        v.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "not(true) not null")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "not(true) base type")
        self.assertTrue(value.value == False, "not(true) value")
        v.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "not(false) value")
        try:
            e = expressions.Not(None)
            v = e.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.string
            v.AddData("true")
            value = e.Evaluate(self.sessionState)
            self.fail("not(string)")
        except core.ProcessingError:
            pass

    def testCaseAnd(self):
        e = expressions.And(None)
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "and(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "and(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "and(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.And(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.boolean
        v1.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "and(true) not null")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "and(true) base type")
        self.assertTrue(value.value == True, "and(true) value")
        v1.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "and(false) value")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.boolean
        v2.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "and(false,true) value")
        v2.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "and(false,false) value")
        v1.SetValue("true")
        v2.SetValue("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "and(true,true) value")
        v3 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "and(true,true,NULL) is NULL")
        v2.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "and(true,false,NULL) is False")
        v4 = e.ChildElement(expressions.BaseValue)
        v4.baseType = variables.BaseType.string
        v4.AddData("true")
        try:
            value = e.Evaluate(self.sessionState)
            self.fail("and(true,false,NULL,string)")
        except core.ProcessingError:
            pass

    def testCaseOr(self):
        e = expressions.Or(None)
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "or(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "or(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "or(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Or(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.boolean
        v1.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "or(true) not null")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "or(true) base type")
        self.assertTrue(value.value == True, "or(true) value")
        v1.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "or(false) value")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.boolean
        v2.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "or(false,true) value")
        v2.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "or(false,false) value")
        v1.SetValue("true")
        v2.SetValue("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "or(true,true) value")
        v3 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "or(true,true,NULL) value")
        v2.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "or(true,false,NULL) value")
        v1.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "or(false,false,NULL) is NULL")
        v4 = e.ChildElement(expressions.BaseValue)
        v4.baseType = variables.BaseType.string
        v4.AddData("true")
        try:
            value = e.Evaluate(self.sessionState)
            self.fail("and(false,false,NULL,string)")
        except core.ProcessingError:
            pass

    def testCaseAnyN(self):
        e = expressions.AnyN(None)
        e.min = "1"
        e.max = "2"
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "anyN(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "anyN(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "anyN(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.AnyN(None)
        e.min = "1"
        e.max = "2"
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.boolean
        v1.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "anyN(true) not null")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "anyN(true) base type")
        self.assertTrue(value.value == True, "anyN(true) value")
        v1.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "anyN(false) value")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.boolean
        v2.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "anyN(false,true) value")
        v2.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "anyN(false,false) value")
        v1.SetValue("true")
        v2.SetValue("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "anyN(true,true) value")
        v3 = e.ChildElement(expressions.BaseValue)
        v3.baseType = variables.BaseType.boolean
        v3.AddData("true")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "anyN(true,true,true) value")
        v3.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "anyN(true,true,false) value")
        v4 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "or(true,true,false,NULL) value")
        v2.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "or(true,false,false,NULL) value")
        v1.SetValue("false")
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "or(false,false,false,NULL) value")
        v5 = e.ChildElement(expressions.BaseValue)
        v5.baseType = variables.BaseType.string
        v5.AddData("true")
        try:
            value = e.Evaluate(self.sessionState)
            self.fail("anyN(false,false,false,NULL,string)")
        except core.ProcessingError:
            pass

    def testCaseMatch(self):
        e = expressions.Match(None)
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "match(Null,Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "match(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "match(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Match(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("A")
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "match(Null,Null) is NULL")
        e = expressions.Match(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.identifier
        v1.AddData("A")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.identifier
        v2.AddData("A")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "match(A,A)")
        v2.SetValue("B")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "match(A,B)")
        e = expressions.Match(None)
        v1 = e.ChildElement(expressions.Ordered)
        v11 = v1.ChildElement(expressions.BaseValue)
        v11.baseType = variables.BaseType.identifier
        v11.AddData("A")
        v12 = v1.ChildElement(expressions.BaseValue)
        v12.baseType = variables.BaseType.identifier
        v12.AddData("B")
        v2 = e.ChildElement(expressions.Ordered)
        v21 = v2.ChildElement(expressions.BaseValue)
        v21.baseType = variables.BaseType.identifier
        v21.AddData("A")
        v22 = v2.ChildElement(expressions.BaseValue)
        v22.baseType = variables.BaseType.identifier
        v22.AddData("A")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "match([A,B],[A,A])")
        v22.SetValue("B")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "match([A,B],[A,B])")
        e = expressions.Match(None)
        v1 = e.ChildElement(expressions.Multiple)
        v11 = v1.ChildElement(expressions.BaseValue)
        v11.baseType = variables.BaseType.identifier
        v11.AddData("A")
        v12 = v1.ChildElement(expressions.BaseValue)
        v12.baseType = variables.BaseType.identifier
        v12.AddData("B")
        v2 = e.ChildElement(expressions.Multiple)
        v21 = v2.ChildElement(expressions.BaseValue)
        v21.baseType = variables.BaseType.identifier
        v21.AddData("B")
        v22 = v2.ChildElement(expressions.BaseValue)
        v22.baseType = variables.BaseType.identifier
        v22.AddData("A")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "match({A,B},{B,A})")
        v22.SetValue("B")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "match({A,B},{B,B})")
        try:
            e = expressions.Match(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("A")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.string
            v2.AddData("A")
            value = e.Evaluate(self.sessionState)
            self.fail("match(string,identifier)")
        except core.ProcessingError:
            pass
        try:
            e = expressions.Match(None)
            v1 = e.ChildElement(expressions.Multiple)
            v2 = e.ChildElement(expressions.Ordered)
            value = e.Evaluate(self.sessionState)
        except core.ProcessingError:
            pass
        try:
            e = expressions.Match(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.duration
            v1.AddData("3.14159")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.duration
            v2.AddData("3.14159")
            value = e.Evaluate(self.sessionState)
            self.fail("match(duration,duration)")
        except core.ProcessingError:
            pass

    def testCaseStringMatch(self):
        e = expressions.StringMatch(None)
        e.caseSensitive = True
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.string
        v2.AddData("Shell")
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "stringMatch(Null,'Shell') is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "stringMatch(Null,'Shell') base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "stringMatch(Null,'Shell') cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.StringMatch(None)
        e.caseSensitive = True
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.string
        v2.AddData("Shell")
        v1 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "stringMatch('Shell',NULL) is NULL")
        e = expressions.StringMatch(None)
        e.caseSensitive = True
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "stringMatch(NULL,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "stringMatch(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "stringMatch(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.StringMatch(None)
        e.caseSensitive = True
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.string
        v1.AddData("Hell")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.string
        v2.AddData("Shell")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "stringMatch('Hell','Shell')")
        e.caseSensitive = False
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "stringMatch('Hell','Shell')")
        e.substring = True
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "stringMatch('Hell','Shell') - substring")
        e.substring = False
        v2.SetValue("hell")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "stringMatch('Hell','hell') - case insensitive")
        e.caseSensitive = True
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "stringMatch('Hell','hell') - case sensitive")
        try:
            e = expressions.StringMatch(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("hell")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.identifier
            v2.AddData("Shell")
            value = e.Evaluate(self.sessionState)
            self.fail("stringMatch(identifier,identifier)")
        except core.ProcessingError:
            pass

    def testCasePatternMatch(self):
        e = expressions.PatternMatch(None)
        e.pattern = "\\s*[\\p{Lu}-[ABC]]+\\s*"
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "patternMatch(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "patternMatch(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "patternMatch(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.PatternMatch(None)
        e.pattern = "\\s*[\\p{Lu}-[DEG]]+\\s*"
        v = e.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.string
        v.AddData(u"  CAF\xc9\t")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "patternMatch(u'  CAF\xc9\t') is NULL")
        self.assertTrue(value.baseType is variables.BaseType.boolean,
                        "patternMatch(u'  CAF\xc9\t') base type")
        self.assertTrue(
            value.value == True, "patternMatch(u'  CAF\xc9\t') is True")
        e = expressions.PatternMatch(None)
        e.pattern = "\\s*[\\p{Lu}-[CDE]]+\\s*"
        v = e.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.string
        v.AddData(u"  CAF\xc9\t")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "patternMatch(u'  CAF\xc9\t') is NULL")
        self.assertTrue(
            value.value == False, "patternMatch(u'  CAF\xc9\t') is False")
        try:
            e = expressions.PatternMatch(None)
            e.pattern = "\\s*[\\p{Lu}-[ABCD]]+\\s*"
            v = e.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.identifier
            v.AddData(u"CAF\xc9")
            value = e.Evaluate(self.sessionState)
            self.fail("patternMatch(identifier)")
        except core.ProcessingError:
            pass

    def testCaseEqual(self):
        e = expressions.Equal(None)
        e.toleranceMode = expressions.ToleranceMode.exact
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.14")
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "equal(Null,3.14) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "equal(Null,3.14) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "equal(Null,3.14) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        # --
        e = expressions.Equal(None)
        e.toleranceMode = expressions.ToleranceMode.exact
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.14")
        v1 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "equal(3.14, Null) is NULL")
        # --
        e = expressions.Equal(None)
        e.toleranceMode = expressions.ToleranceMode.exact
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "equal(NULL,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "equal(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "equal(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        # --
        e = expressions.Equal(None)
        e.toleranceMode = expressions.ToleranceMode.exact
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.integer
        v1.AddData("3")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.0")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "equal(3,3.0)")
        v2.SetValue("3.14")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "equal(3,3.14)")
        e.toleranceMode = expressions.ToleranceMode.absolute
        e.tolerance = ['0.14']
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "equal(3,3.14) +-0.14")
        e.tolerance = ['0.0', '0.14']
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == True, "equal(3,3.14) -0.0,+0.14")
        e.tolerance = ['0.0', '0.13']
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == False, "equal(3,3.14) -0.0,+0.13")
        e.includeUpperBound = False
        e.tolerance = ['0.14']
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "equal(3,3.14) +-0.14, no upper bound")
        e.tolerance = ['0.0', '5.0']
        e.toleranceMode = expressions.ToleranceMode.relative
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "equal(3,3.14) -0%,+5%, no upper bound")
        e.tolerance = ['0.0', '3.0']
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "equal(3,3.14) -0%,+3%, no upper bound")
        try:
            e = expressions.Equal(None)
            e.toleranceMode = expressions.ToleranceMode.exact
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("three")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.identifier
            v2.AddData("pi")
            value = e.Evaluate(self.sessionState)
            self.fail("equal(identifier,identifier)")
        except core.ProcessingError:
            pass

    def testCaseEqualRounded(self):
        e = expressions.EqualRounded(None)
        e.roundingMode = expressions.RoundingMode.significantFigures
        e.figures = "1"
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.14")
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "equalRounded(Null,3.14) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "equalRounded(Null,3.14) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "equalRounded(Null,3.14) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        # --
        e = expressions.EqualRounded(None)
        e.roundingMode = expressions.RoundingMode.significantFigures
        e.figures = "1"
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.14")
        v1 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "equalRounded(3.14, Null) is NULL")
        # --
        e = expressions.EqualRounded(None)
        e.roundingMode = expressions.RoundingMode.significantFigures
        e.figures = "1"
        v1 = e.ChildElement(expressions.Null)
        v2 = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "equalRounded(NULL,NULL) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "equalRounded(NULL,NULL) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "equalRounded(NULL,NULL) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        # --
        e = expressions.EqualRounded(None)
        e.roundingMode = expressions.RoundingMode.significantFigures
        e.figures = "2"
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.integer
        v1.AddData("3")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.14")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "equalRounded(3,3.14) to 2 sig fig")
        e.figures = "1"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "equalRounded(3,3.14) to 1 sig fig")
        e.roundingMode = expressions.RoundingMode.decimalPlaces
        e.figures = "2"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "equalRounded(3,3.14) to 2 decimal places")
        v2.SetValue("3.0001")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "equalRounded(3,3.0001) to 2 decimal places")
        e.figures = "4"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "equalRounded(3,3.0001) to 4 decimal places")
        # --
        e = expressions.EqualRounded(None)
        e.roundingMode = expressions.RoundingMode.decimalPlaces
        e.figures = "4"
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.float
        v1.AddData("3.14159")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.float
        v2.AddData("3.1416")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "equalRounded(3.1416,3.14159) to 4 decimal places")
        e.figures = "3"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "equalRounded(3.1416,3.14159) to 3 decimal places")
        e.figures = "5"
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "equalRounded(3.1416,3.14159) to 3 decimal places")
        try:
            e = expressions.EqualRounded(None)
            e.roundingMode = expressions.RoundingMode.decimalPlaces
            e.figures = "2"
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.identifier
            v1.AddData("three")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.identifier
            v2.AddData("pi")
            value = e.Evaluate(self.sessionState)
            self.fail("equalRounded(identifier,identifier)")
        except core.ProcessingError:
            pass

    def testCaseInside(self):
        e = expressions.Inside(None)
        e.shape = core.Shape.default
        # by default coords is an empty list, which is OK for default test
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "inside(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "inside(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "inside(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        e = expressions.Inside(None)
        e.shape = core.Shape.default
        v = e.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.point
        v.AddData(u"10 10")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "inside(u'10 10', default) is not NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.boolean, "inside(u'10 10', default) base type")
        self.assertTrue(
            value.value == True, "inside(u'10 10', default) is True")
        e.shape = core.Shape.rect
        e.coords = html.Coords(u"5,5,15,15")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "inside(u'10 10', rect(5,5,15,15)) is True")
        e.coords = html.Coords(u"15,15,25,25")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "inside(u'10 10', rect(15,15,25,25)) is False")
        e.shape = core.Shape.circle
        e.coords = html.Coords(u"10,10,3")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "inside(u'10 10', circle(10,10,3)) is True")
        e.coords = html.Coords(u"15,15,3")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "inside(u'10 10', circle(15,15,5)) is False")
        e.shape = core.Shape.poly
        e.coords = html.Coords(u"5,5,5,15,15,15,15,5,5,5")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "inside(u'10 10', poly(5,5,5,15,15,15,15,5,5,5)) is True")
        e.coords = html.Coords(u"15,15,15,25,25,25,25,15,15,15")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "inside(u'10 10', poly(15,15,15,25,25,25,25,15,15,15)) is False")
        e.shape = core.Shape.ellipse
        e.coords = html.Coords(u"10,10,10,5")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "inside(u'10 10', ellipse(10,10,10,5)) is True")
        e.coords = html.Coords(u"15,15,6,5")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "inside(u'10 10', ellipse(15,15,6,5)) is False")
        # --
        e = expressions.Inside(None)
        e.shape = core.Shape.circle
        e.coords = html.Coords(u"10,10,5")
        eo = e.ChildElement(expressions.Ordered)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "inside(Ordered()) is NULL")
        v = eo.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.point
        v.SetValue("5 5")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "inside(ordered('5 5')), circle(10,10,5)) is False")
        v = eo.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.point
        v.SetValue("10 10")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "inside(ordered('5 5','10 10')), circle(10,10,5)) is True")
        # --
        e = expressions.Inside(None)
        e.shape = core.Shape.circle
        e.coords = html.Coords(u"10,10,5")
        em = e.ChildElement(expressions.Multiple)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "inside(Multiple()) is NULL")
        v = em.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.point
        v.SetValue("5 5")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == False, "inside(multiple('5 5')), circle(10,10,5)) is False")
        v = em.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.point
        v.SetValue("10 10")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(
            value.value == True, "inside(multiple('5 5','10 10')), circle(10,10,5)) is True")
        try:
            e = expressions.Inside(None)
            e.shape = core.Shape.circle
            e.coords = html.Coords(u"10,10,5")
            v = e.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.string
            v.AddData(u"10 10")
            value = e.Evaluate(self.sessionState)
            self.fail("inside(identifier)")
        except core.ProcessingError:
            pass

    def testCaseInequality(self):
        tests = {
            # (3,3.0), (3,3.14), (4,3.14)
            expressions.LT: (False, True, False),
            expressions.GT: (False, False, True),
            expressions.LTE: (True, True, False),
            expressions.GTE: (True, False, True)
        }
        for eType in tests.keys():
            expected = tests[eType]
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<inequality>(Null,3.14) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.boolean, "<inequality>(Null,3.14) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<inequality>(Null,3.14) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.14")
            v1 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<inequality>(3.14, Null) is NULL")
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<inequality>(NULL,NULL) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.boolean, "<inequality>(NULL,NULL) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<inequality>(NULL,NULL) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.integer
            v1.AddData("3")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.0")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[0], "<inequality>(3,3.0)")
            v2.SetValue("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[1], "<inequality>(3,3.14)")
            v1.SetValue("4")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[2], "<inequality>(4,3.14)")
            try:
                e = eType(None)
                v1 = e.ChildElement(expressions.BaseValue)
                v1.baseType = variables.BaseType.identifier
                v1.AddData("three")
                v2 = e.ChildElement(expressions.BaseValue)
                v2.baseType = variables.BaseType.identifier
                v2.AddData("pi")
                value = e.Evaluate(self.sessionState)
                self.fail("<inequality>(identifier,identifier)")
            except core.ProcessingError:
                pass

    def testCaseDurInequality(self):
        tests = {
            # (3,3.0), (3,3.14), (4,3.14)
            expressions.DurationLT: (False, True, False),
            expressions.DurationGTE: (True, False, True)
        }
        for eType in tests.keys():
            expected = tests[eType]
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.duration
            v2.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<durInequality>(Null,3.14) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.boolean, "<durInequality>(Null,3.14) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<durInequality>(Null,3.14) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.duration
            v2.AddData("3.14")
            v1 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<durInequality>(3.14, Null) is NULL")
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<durInequality>(NULL,NULL) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.boolean, "<durInequality>(NULL,NULL) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<durInequality>(NULL,NULL) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.duration
            v1.AddData("3")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.duration
            v2.AddData("3.0")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[0], "<durInequality>(3,3.0)")
            v2.SetValue("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[1], "<durInequality>(3,3.14)")
            v1.SetValue("4")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[2], "<durInequality>(4,3.14)")
            try:
                e = eType(None)
                v1 = e.ChildElement(expressions.BaseValue)
                v1.baseType = variables.BaseType.float
                v1.AddData("3")
                v2 = e.ChildElement(expressions.BaseValue)
                v2.baseType = variables.BaseType.float
                v2.AddData("3.14")
                value = e.Evaluate(self.sessionState)
                self.fail("<durInequality>(float,float)")
            except core.ProcessingError:
                pass

    def testCaseMathMulti(self):
        tests = {
            # (3,3.0), (3,3.14), (4,3.14), (4,3.14,-10.0), (3)
            expressions.Sum: (6.0, 6.14, 7.14, -2.86, 3),
            expressions.Product: (9.0, 9.42, 12.56, -125.6, 3)
        }
        for eType in tests.keys():
            expected = tests[eType]
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<mathMulti>(Null,3.14) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.float, "<mathMulti>(Null,3.14) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<mathMulti>(Null,3.14) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.14")
            v1 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<mathMulti>(3.14, Null) is NULL")
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<mathMulti>(NULL,NULL) is NULL")
            self.assertTrue(
                value.baseType is None, "<mathMulti>(NULL,NULL) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<mathMulti>(NULL,NULL) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.integer
            v1.AddData("3")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[4], "<mathMulti>(3)")
            self.assertTrue(
                value.baseType is variables.BaseType.integer, "<mathMulti>(3) base type")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.0")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.5f" % value.value == "%.5f" %
                            expected[0], "<mathMulti>(3,3.0)")
            self.assertTrue(
                value.baseType is variables.BaseType.float, "<mathMulti>(3,3.0) base type")
            v2.SetValue("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.5f" % value.value == "%.5f" %
                            expected[1], "<mathMulti>(3,3.14)")
            v1.SetValue("4")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.5f" % value.value == "%.5f" %
                            expected[2], "<mathMulti>(4,3.14)")
            v3 = e.ChildElement(expressions.BaseValue)
            v3.baseType = variables.BaseType.float
            v3.AddData("-10")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.5f" % value.value == "%.5f" % expected[3], "<mathMulti>(4,3.14,-10), expected %s, found %s" %
                            (repr(expected[3]), repr(value.value)))
            try:
                e = eType(None)
                v1 = e.ChildElement(expressions.BaseValue)
                v1.baseType = variables.BaseType.duration
                v1.AddData("3")
                v2 = e.ChildElement(expressions.BaseValue)
                v2.baseType = variables.BaseType.identifier
                v2.AddData("pi")
                value = e.Evaluate(self.sessionState)
                self.fail("<mathMulti>(duration,identifier)")
            except core.ProcessingError:
                pass

    def testCaseMathBinary(self):
        tests = {
            # (3,3.0), (3,3.14), (4,3.14), (4,-3.14)
            expressions.Subtract: (0.0, -0.14, 0.86, 7.14),
            expressions.Divide: (1.0, 0.9554, 1.2739, -1.2739),
            expressions.Power: (27.0, 31.4891, 77.7085, 0.0129)
        }
        for eType in tests.keys():
            expected = tests[eType]
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<mathBinary>(Null,3.14) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.float, "<mathBinary>(Null,3.14) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<mathBinary>(Null,3.14) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.14")
            v1 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<mathBinary>(3.14, Null) is NULL")
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<mathBinary>(NULL,NULL) is NULL")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<mathBinary>(NULL,NULL) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.integer
            v1.AddData("3")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.float
            v2.AddData("3.0")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.4f" % value.value == "%.4f" %
                            expected[0], "<mathBinary>(3,3.0)")
            self.assertTrue(
                value.baseType is variables.BaseType.float, "<mathBinary>(3,3.0) base type")
            v2.SetValue("3.14")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.4f" % value.value == "%.4f" % expected[1], "<mathBinary>(3,3.14), expected %s, found %s" %
                            (repr(expected[1]), repr(value.value)))
            v1.SetValue("4")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.4f" % value.value == "%.4f" %
                            expected[2], "<mathBinary>(4,3.14)")
            v2.SetValue("-3.14")
            value = e.Evaluate(self.sessionState)
            self.assertTrue("%.4f" % value.value == "%.4f" %
                            expected[3], "<mathBinary>(4,-3.14)")
            try:
                e = eType(None)
                v1 = e.ChildElement(expressions.BaseValue)
                v1.baseType = variables.BaseType.duration
                v1.AddData("3")
                v2 = e.ChildElement(expressions.BaseValue)
                v2.baseType = variables.BaseType.identifier
                v2.AddData("pi")
                value = e.Evaluate(self.sessionState)
                self.fail("<mathBinary>(duration,identifier)")
            except core.ProcessingError:
                pass
        # check the integer subtraction return base type case
        e = expressions.Subtract(None)
        v1 = e.ChildElement(expressions.BaseValue)
        v1.baseType = variables.BaseType.integer
        v1.AddData("3")
        v2 = e.ChildElement(expressions.BaseValue)
        v2.baseType = variables.BaseType.integer
        v2.AddData("-1")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == 4, "Subtrace(3,-1)")
        self.assertTrue(
            value.baseType is variables.BaseType.integer, "<mathBinary>(3,-1) base type")

    def testCaseIntegerBinary(self):
        tests = {
            # (3,2), (3,3), (2,3), (-2,-3), (-2,3)
            expressions.IntegerDivide: (1, 1, 0, 0, -1),
            expressions.IntegerModulus: (1, 0, 2, -2, 1),
        }
        for eType in tests.keys():
            expected = tests[eType]
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.integer
            v2.AddData("3")
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<integerBinary>(Null,3) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.integer, "<integerBinary>(Null,3) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<integerBinary>(Null,3) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.integer
            v2.AddData("3")
            v1 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<integerBinary>(3, Null) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.integer, "<integerBinary>(3,Null) base type")
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.Null)
            v2 = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<integerBinary>(NULL,NULL) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.integer, "<integerBinary>(Null,Null) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<integerBinary>(NULL,NULL) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v1 = e.ChildElement(expressions.BaseValue)
            v1.baseType = variables.BaseType.integer
            v1.AddData("3")
            v2 = e.ChildElement(expressions.BaseValue)
            v2.baseType = variables.BaseType.integer
            v2.AddData("2")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[0], "<integerBinary>(3,2)")
            v2.SetValue("3")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[1], "<integerBinary>(3,3)")
            v1.SetValue("2")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value.value == expected[2], "<integerBinary>(2,3)")
            v1.SetValue("-2")
            v2.SetValue("-3")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[3], "<integerBinary>(-2,-3)")
            v2.SetValue("3")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[4], "<integerBinary>(-2,3)")
            try:
                e = eType(None)
                v1 = e.ChildElement(expressions.BaseValue)
                v1.baseType = variables.BaseType.float
                v1.AddData("3.0")
                v2 = e.ChildElement(expressions.BaseValue)
                v2.baseType = variables.BaseType.float
                v2.AddData("3.14")
                value = e.Evaluate(self.sessionState)
                self.fail("<integerBinary>(float,float)")
            except core.ProcessingError:
                pass

    def testCaseFloatToInteger(self):
        tests = {
            # 6.49, -6.49, 6.5, -6.5, 6.51, -6.51
            expressions.Truncate: (6, -6, 6, -6, 6, -6),
            expressions.Round: (6, -6, 7, -6, 7, -7),
        }
        for eType in tests.keys():
            expected = tests[eType]
            e = eType(None)
            v = e.ChildElement(expressions.Null)
            value = e.Evaluate(self.sessionState)
            self.assertFalse(value, "<floatToInteger>(Null) is NULL")
            self.assertTrue(
                value.baseType is variables.BaseType.integer, "<floatToInteger>(Null) base type")
            self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<floatToInteger>(Null) cardinality, found %s" %
                            variables.Cardinality.EncodeValue(value.Cardinality()))
            # --
            e = eType(None)
            v = e.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.float
            v.AddData("6.49")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(value, "<floatToInteger>(6.49)")
            self.assertTrue(
                value.baseType is variables.BaseType.integer, "<floatToInteger>(6.49) base type")
            self.assertTrue(
                value.value == expected[0], "<floatToInteger>(6.49)")
            v.SetValue("-6.49")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[1], "<floatToInteger>(-6.49)")
            v.SetValue("6.5")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[2], "<floatToInteger>(6.5)")
            v.SetValue("-6.5")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[3], "<floatToInteger>(-6.5)")
            v.SetValue("6.51")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[4], "<floatToInteger>(6.51)")
            v.SetValue("-6.51")
            value = e.Evaluate(self.sessionState)
            self.assertTrue(
                value.value == expected[5], "<floatToInteger>(-6.51)")
            # --
            try:
                e = eType(None)
                v = e.ChildElement(expressions.BaseValue)
                v.baseType = variables.BaseType.integer
                v.AddData("3")
                value = e.Evaluate(self.sessionState)
                self.fail("<floatToInteger>(integer)")
            except core.ProcessingError:
                pass

    def testCaseIntegerToFloat(self):
        e = expressions.IntegerToFloat(None)
        v = e.ChildElement(expressions.Null)
        value = e.Evaluate(self.sessionState)
        self.assertFalse(value, "<integerToFloat>(Null) is NULL")
        self.assertTrue(
            value.baseType is variables.BaseType.float, "<integerToFloat>(Null) base type")
        self.assertTrue(value.Cardinality() == variables.Cardinality.single, "<integerToFloat>(Null) cardinality, found %s" %
                        variables.Cardinality.EncodeValue(value.Cardinality()))
        # --
        e = expressions.IntegerToFloat(None)
        v = e.ChildElement(expressions.BaseValue)
        v.baseType = variables.BaseType.integer
        v.AddData("6")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value, "<integerToFloat>(6)")
        self.assertTrue(
            value.baseType is variables.BaseType.float, "<integerToFloat>(6) base type")
        self.assertTrue(value.value == 6.0, "<integerToFloat>(6)")
        v.SetValue("0")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == 0.0, "<integerToFloat>(0)")
        v.SetValue("-6")
        value = e.Evaluate(self.sessionState)
        self.assertTrue(value.value == -6.0, "<integerToFloat>(-6)")
        # --
        try:
            e = expressions.IntegerToFloat(None)
            v = e.ChildElement(expressions.BaseValue)
            v.baseType = variables.BaseType.float
            v.AddData("3.0")
            value = e.Evaluate(self.sessionState)
            self.fail("<integerToFloat>(float)")
        except core.ProcessingError:
            pass

    def testCaseCustomOperator(self):
        e = expressions.CustomOperator(None)
        e.SetAttribute(u"class", u"math")
        e.customClass = "math"
        e.definition = "http://www.example.com/math/sin"
        v = e.ChildElement(expressions.Null)
        try:
            value = e.Evaluate(self.sessionState)
        except core.ProcessingError:
            pass


EXAMPLE_1 = """<?xml version="1.0" encoding="utf-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="test"></assessmentItem>"""

EXAMPLE_2 = """<?xml version="1.0" encoding="UTF-8"?>
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


class BasicAssessmentTests(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.dataPath = os.path.join(
            os.path.split(__file__)[0], 'data_imsqtiv2p1')
        os.chdir(self.dataPath)
        self.doc = core.QTIDocument(baseURI="basic/assessment.xml")
        self.doc.Read()

    def tearDown(self):
        os.chdir(self.cwd)

    def testCaseAssessmentTest(self):
        self.assertTrue(
            isinstance(self.doc.root, tests.AssessmentTest), "AssessmentTest")
        f = tests.TestForm(self.doc.root)
        self.assertTrue(f.test is self.doc.root, "TestForm test link")
        # A test form is essentially a sequence of identifiers of the components
        # picked from the test for this form, augmented by a find method which maps
        # the component identifiers on to a list of indexes into the form.
        # in this case:
        # '', PartI, SectionA, A1, SectionB, B1, SectionC, C1
        self.assertTrue(len(f) == 12, "Form length: %s" % repr(len(f)))
        self.assertTrue(
            f[1] == u"PartI", "Identifier of test part: %s" % repr(f[0]))
        self.assertTrue(
            f[2:5] == [u"SectionA", u"A1", u"-SectionA"], "SectionA " + repr(f[1:3]))
        self.assertTrue(
            f[5:8] == [u"SectionB", u"B1", u"-SectionB"], "SectionB " + repr(f[3:5]))
        self.assertTrue(
            f[8:11] == [u"SectionC", u"C1", u"-SectionC"], "Invisible section " + repr(f[5:]))
        self.assertTrue(
            f[11] == u"-PartI", "Identifier of closing part: %s" % repr(f[11]))
        self.assertTrue(f.find("A1") == [3], "Index of A1")
        self.assertTrue(f.find("SectionB") == [5], "Index of SectionB")
        self.assertTrue(f.find("SectionC") == [8], "Index of SectionC")

    def testCaseLinearIndividual(self):
        doc = core.QTIDocument(baseURI="basic/linearIndividualPart.xml")
        doc.Read()
        form = tests.TestForm(doc.root)
        state = variables.TestSessionState(form)
        try:
            state.BeginSession('wrongkey')
            self.fail("TestSessionState.BeginSession: failed to match key")
        except variables.SessionKeyMismatch:
            pass
        saveKey = state.key
        htmlDiv = state.BeginSession(state.key)
        self.assertFalse(saveKey == state.key, "No key change.")
        logging.debug(htmlDiv)
        # we should be able to read the the current test part
        self.assertTrue(
            state.GetCurrentTestPart().identifier == "PartI", "Current test part")
        self.assertTrue(state.GetCurrentQuestion().identifier ==
                        "Q1", "Current question (pre-condition skip check)")
        # In linear mode (applicable to PartI) template defaults are evaluated
        # after preConditions
        self.assertTrue(state[
                        "Q0.T"].value == 0, "Template default invoked for item skipped by template rule")
        self.assertTrue(state[
                        "Q1.T"].value == 1, "Template default invoked for item not skipped by template rule")
        self.assertFalse(state["Q1.RESPONSE"], "RESPONSE not NULL initially")
        # Now let's make some checks on the output
        self.assertTrue(
            isinstance(htmlDiv, html.Div), "output is an html <div>")
        formList = list(htmlDiv.FindChildrenDepthFirst(html.Form))
        self.assertTrue(len(formList) == 1, "only one form in the html <div>")
        inputList = list(htmlDiv.FindChildrenDepthFirst(html.Input))
        self.assertTrue(len(inputList) == 4, "<input> list length")
        for i in inputList:
            self.assertTrue(
                i.type == html.InputType.radio, "<input> must be radio buttons")
            self.assertTrue(
                i.name == "Q1.RESPONSE", "<input> must have the name of the response variable")
            self.assertTrue(i.value in (
                "A", "B", "C", "D"), "<input> must have the value of a choice identifier")
            self.assertTrue(i.checked is False, "Button's initially unchecked")
        buttonList = list(htmlDiv.FindChildrenDepthFirst(html.Button))
        self.assertTrue(len(buttonList) == 2, "<button> list length")
        for i in buttonList:
            self.assertTrue(
                i.type == html.ButtonType.submit, "<buttons> must be of submit type")
            self.assertTrue(
                i.name in ("SAVE", "SUBMIT"), "unknown action name")
            self.assertTrue(
                i.value == state.key, "button actions should have key as their value")
        # sleep for 1s to ensure we register a duration
        time.sleep(1)
        # Now construct a fake form response for save....
        response = {
            "SAVE": saveKey,
            "Q1.RESPONSE": "C"}
        try:
            state.HandleEvent(response)
            self.fail(
                "TestSessionState.HandleEvent: failed to match current key")
        except variables.SessionKeyMismatch:
            self.fail("TestSessionState.HandleEvent: failed to detect old key")
        except variables.SessionKeyExpired:
            pass
        response['SAVE'] = saveKey = state.key
        htmlDiv = state.HandleEvent(response)
        logging.debug(htmlDiv)
        self.assertFalse(
            state["Q1.RESPONSE"], "RESPONSE not NULL after save (no submit)")
        self.assertTrue(
            state["Q1.RESPONSE.SAVED"].value == "C", "Saved response not recorded")
        self.assertFalse(saveKey == state.key, "Key change on save")
        inputList = list(htmlDiv.FindChildrenDepthFirst(html.Input))
        for i in inputList:
            self.assertTrue(
                i.checked is (i.value == "C"), "Saved value is checked")
        # Now check durations
        self.assertTrue(
            state["Q1.duration"].value > 1.0, "Duration of question")
        self.assertTrue(state["SectionA1.duration"].value > 1.0, "Duration of section A1: %s" % repr(
            state["SectionA1.duration"].value))
        self.assertTrue(
            state["SectionA.duration"].value > 1.0, "Duration of section A")
        self.assertTrue(
            state["SectionB.duration"].value is None, "Duration of section B")
        self.assertTrue(
            state["PartI.duration"].value > 1.0, "Duration of test part")
        self.assertTrue(state["duration"].value > 1.0, "Duration of test")
        time.sleep(1)
        response = {
            "SUBMIT": state.key,
            "Q1.RESPONSE": "D"
        }
        htmlDiv = state.HandleEvent(response)
        logging.debug(htmlDiv)
        self.assertFalse(
            "Q1.RESPONSE.SAVED" in state, "SAVED RESPONSE not NULL after submit")
        self.assertTrue(
            state["Q1.RESPONSE"].value == "D", "Submitted response not recorded")
        self.assertTrue(
            state["Q1.duration"].value > 2.0, "Duration of question 1 should now be 2s")
        self.assertTrue(
            state["PartI.duration"].value > 2.0, "Duration of test part")
        inputList = list(htmlDiv.FindChildrenDepthFirst(html.Input))
        self.assertTrue(len(inputList) == 5, "<input> list length")
        for i in inputList:
            self.assertTrue(
                i.type == html.InputType.checkbox, "<input> must be checkboxes")
            self.assertTrue(
                i.name == "Q2.RESPONSE", "<input> must have the name of the response variable")
            self.assertTrue(i.value in (
                "A", "B", "C", "D", "E"), "<input> must have the value of a choice identifier")
            self.assertTrue(
                i.checked is (i.value == "E"), "Default box initially checked")
        time.sleep(1)
        response = {
            "SUBMIT": state.key,
            "Q2.RESPONSE": ["B", "C", "D"]
        }
        htmlDiv = state.HandleEvent(response)
        logging.debug(htmlDiv)
        self.assertTrue(state["Q2.RESPONSE"].value == {
                        "B": 1, "C": 1, "D": 1}, "Submitted response for multi-response")
        self.assertTrue(
            state["Q1.duration"].value < 3.0, "Duration of question 1 should now be 2s+")
        self.assertTrue(
            state["Q2.duration"].value > 1.0, "Duration of question 2 should now be 1s+")
        self.assertTrue(
            state["PartI.duration"].value > 3.0, "Duration of test part")
        for key in state:
            logging.debug("%s: %s", key, repr(state[key].value))


class MultiPartAssessmentTests(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.dataPath = os.path.join(
            os.path.split(__file__)[0], 'data_imsqtiv2p1')
        os.chdir(self.dataPath)
        self.doc = core.QTIDocument(baseURI="basic/multiPart.xml")
        self.doc.Read()

    def tearDown(self):
        os.chdir(self.cwd)

    def testCasePartI(self):
        # PartI tests
        selections = {
            (u"I", u"A1", u"A1", u"A3", u"-I"): 0,
            (u"I", u"A1", u"A2", u"A3", u"-I"): 0,
            (u"I", u"A1", u"A3", u"A3", u"-I"): 0,
            (u"I", u"A1", u"A3", u"A4", u"-I"): 0,
            (u"I", u"A1", u"A4", u"A3", u"-I"): 0
        }
        self.CheckSelections(u"PartI", selections)

    def testCasePartII(self):
        # PartII tests
        selections = {
            (u"II", u"SectionB", u"B1", u"B2", u"-SectionB", u"SectionB", u"B1", u"B2", u"-SectionB", u"C3", u"-II"): 0,
            (u"II", u"SectionB", u"B1", u"B2", u"-SectionB", u"C2", u"C3", u"-II"): 0,
            (u"II", u"SectionB", u"B1", u"B2", u"-SectionB", u"C3", u"C3", u"-II"): 0,
            (u"II", u"SectionB", u"B1", u"B2", u"-SectionB", u"C3", u"C4", u"-II"): 0,
            (u"II", u"SectionB", u"B1", u"B2", u"-SectionB", u"C4", u"C3", u"-II"): 0
        }
        self.CheckSelections(u"PartII", selections)

    def testCasePartIII(self):
        # PartII tests
        selections = {
            (u"III", u"D1", u"D1", u"SectionE", u"E1", u"E2", u"-SectionE", u"-III"): 0,
            (u"III", u"D1", u"D2", u"SectionE", u"E1", u"E2", u"-SectionE", u"-III"): 0,
            (u"III", u"D1", u"SectionE", u"E1", u"E2", u"-SectionE", u"SectionE", u"E1", u"E2", u"-SectionE", u"-III"): 0,
            (u"III", u"D1", u"SectionE", u"E1", u"E2", u"-SectionE", u"D4", u"-III"): 0
        }
        self.CheckSelections(u"PartIII", selections)

    def testCasePartIV(self):
        # PartIV tests
        selections = {
            (u"IV", u"F1", u"F1", u"G1", u"G2", u"-IV"): 0,
            (u"IV", u"F1", u"F1", u"G2", u"G1", u"-IV"): 0,
            (u"IV", u"F1", u"F2", u"G1", u"G2", u"-IV"): 0,
            (u"IV", u"F1", u"F2", u"G2", u"G1", u"-IV"): 0,
            (u"IV", u"F1", u"G1", u"F2", u"G2", u"-IV"): 0,
            (u"IV", u"F1", u"G1", u"G2", u"F2", u"-IV"): 0,
            (u"IV", u"F1", u"G2", u"F2", u"G1", u"-IV"): 0,
            (u"IV", u"F1", u"G2", u"G1", u"F2", u"-IV"): 0,
            (u"IV", u"F1", u"G1", u"G1", u"G2", u"G2", u"-IV"): 0,
            (u"IV", u"F1", u"G1", u"G2", u"G1", u"G2", u"-IV"): 0,
            (u"IV", u"F1", u"G1", u"G2", u"G2", u"G1", u"-IV"): 0,
            (u"IV", u"F1", u"G2", u"G2", u"G1", u"G1", u"-IV"): 0,
            (u"IV", u"F1", u"G2", u"G1", u"G2", u"G1", u"-IV"): 0,
            (u"IV", u"F1", u"G2", u"G1", u"G1", u"G2", u"-IV"): 0,
            (u"IV", u"F1", u"G1", u"G2", u"F4", u"-IV"): 0,
            (u"IV", u"F1", u"G2", u"G1", u"F4", u"-IV"): 0,
        }
        self.CheckSelections(u"PartIV", selections)

    def CheckSelections(self, partId, selections):
        missing = len(selections)
        for i in xrange(1000):
            # We'll try to find all possibilities, give it 1000 goes...
            f = tests.TestForm(self.doc.root)
            # grab first instance of pardId
            aIndex = f.index(partId) + 1
            bIndex = f.index(u"-" + partId)
            section = tuple(f[aIndex:bIndex])
            x = selections.get(section, None)
            if x is None:
                self.fail("Illegal selection found: %s" % repr(section))
            if x == 0:
                missing = missing - 1
            if missing == 0:
                break
            selections[section] = x + 1
        if missing:
            for i in selections.keys():
                logging.debug("%s: %i", repr(i), selections[i])
            self.fail("Missing selection after 1000 trials: %s" %
                      repr(selections))


class ErrorAssessmentTests(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.dataPath = os.path.join(
            os.path.split(__file__)[0], 'data_imsqtiv2p1')
        os.chdir(self.dataPath)

    def tearDown(self):
        os.chdir(self.cwd)

    def testCaseRequired(self):
        self.SelectionErrorTest("errors/required.xml")

    def testCaseSelect(self):
        self.SelectionErrorTest("errors/select.xml")

    def testCaseFixed(self):
        self.SelectionErrorTest("errors/fixed.xml")

    def SelectionErrorTest(self, fName):
        self.doc = core.QTIDocument(baseURI=fName)
        self.doc.Read()
        try:
            f = tests.TestForm(self.doc.root)
            self.fail("%s failed to raise SelectionError" % fName)
        except core.SelectionError, e:
            pass


class QTIDocumentTests(unittest.TestCase):

    def testCaseConstructor(self):
        doc = core.QTIDocument()
        self.assertTrue(isinstance(doc, xmlns.XMLNSDocument))

    def testCaseExample1(self):
        doc = core.QTIDocument()
        doc.Read(src=StringIO(EXAMPLE_1))
        root = doc.root
        self.assertTrue(isinstance(root, items.AssessmentItem))
        self.assertTrue(
            root.ns == core.IMSQTI_NAMESPACE and root.xmlname == 'assessmentItem')

    def testCaseExample2(self):
        doc = core.QTIDocument()
        doc.Read(src=StringIO(EXAMPLE_2))
        vardefs = doc.root.declarations
        self.assertTrue(len(vardefs.keys()) == 2)
        self.assertTrue(
            isinstance(vardefs['RESPONSE'], variables.ResponseDeclaration))
        self.assertTrue(
            isinstance(vardefs['SCORE'], variables.OutcomeDeclaration))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
