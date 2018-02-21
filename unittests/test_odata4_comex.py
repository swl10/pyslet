#! /usr/bin/env python

import decimal
import logging
import unittest
import uuid

from pyslet import iso8601 as iso
from pyslet.xml import xsdatatypes as xsi

from pyslet.odata4 import (
    comex,
    errors,
    geotypes,
    names,
    )
from pyslet.py2 import (
    range3,
    to_text,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ExpressionTests, 'test'),
        ))


class NoMemberFormatter(comex.ExpressionFormatter):

    def first_member(self, segment):
        raise errors.PathError

    def member(self, segment):
        raise errors.PathError


class ExpressionTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.ep = comex.ExpressionProcessor()
        self.ef = comex.ExpressionFormatter()
        self.sf = comex.SearchFormatter()

    def test_common(self):
        e = comex.CommonExpression()
        # in general, common expressions do not satisfy commonExpr!
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_collection_path())
        self.assertFalse(e.is_function())
        self.assertFalse(e.is_function_parameter())

        # abstract class but does define comparisons

        class MockExpression(comex.CommonExpression):

            def __init__(self, sort_value):
                self.sort_value = sort_value

            def sortkey(self):
                return self.sort_value

        e1 = MockExpression(10)
        e2 = MockExpression(20)
        self.assertTrue(e1 < e2)
        self.assertTrue(e2 > e1)
        self.assertFalse(e1 == e2)
        self.assertTrue(e2 < e, "default sort key is high")
        e100 = MockExpression(100)
        self.assertTrue(e100 == e)
        # comparisons with other types: you're on your own
        ex = object()
        try:
            self.assertFalse(e1 == ex)
            self.assertFalse(ex == e1)
        except TypeError:
            # python 3 we assume
            pass
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated CommonExpression")
        except NotImplementedError:
            pass
        try:
            self.ef.evaluate(e)
            self.fail("ExpressionFormatter evaluated CommonExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated CommonExpression")
        except NotImplementedError:
            pass

    def test_literal(self):
        e = comex.LiteralExpression(1)
        # all literal expressions satisfy commonExpr!
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertTrue(e.value == 1)
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated LiteralExpression")
        except NotImplementedError:
            pass
        try:
            self.ef.evaluate(e)
            self.fail("ExpressionFormatter evaluated LiteralExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated LiteralExpression")
        except NotImplementedError:
            pass

    def test_null(self):
        e = comex.NullExpression()
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated NullExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "null")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated NullExpression")
        except NotImplementedError:
            pass

    def test_boolean(self):
        e = comex.BooleanExpression(True)
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        self.assertTrue(e.is_bool_common())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated BooleanExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "true")
        e = comex.BooleanExpression(False)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "false")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated BooleanExpression")
        except NotImplementedError:
            pass

    def test_guid(self):
        e = comex.GuidExpression(uuid.UUID(int=3))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated GuidExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "00000000-0000-0000-0000-000000000003")
        e = comex.GuidExpression(uuid.UUID(int=15))
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "00000000-0000-0000-0000-00000000000F")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated GuidExpression")
        except NotImplementedError:
            pass

    def test_date(self):
        e = comex.DateExpression(iso.Date.from_str('2017-12-30'))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated DateExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "2017-12-30")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated DateExpression")
        except NotImplementedError:
            pass

    def test_date_time_offset(self):
        e = comex.DateTimeOffsetExpression(
            iso.TimePoint.from_str('2017-12-30T15:00:00Z'))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated DateTimeOffsetExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "2017-12-30T15:00:00.000000Z", estr)
        tstr = '2017-12-30T10:00:00.125-05:00'
        e = comex.DateTimeOffsetExpression(
            iso.TimePoint.from_str(tstr), tstr)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == tstr, estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated DateTimeOffsetExpression")
        except NotImplementedError:
            pass

    def test_time_of_day(self):
        e = comex.TimeOfDayExpression(
            iso.Time.from_str('15:00:00'))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated TimeOfDayExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "15:00:00.000000", estr)
        tstr = '10:00:00.125'
        e = comex.TimeOfDayExpression(
            iso.Time.from_str(tstr), tstr)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == tstr, estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated TimeOfDayExpression")
        except NotImplementedError:
            pass

    def test_decimal(self):
        e = comex.DecimalExpression(decimal.Decimal('1.50'))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated DecimalExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "1.50", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated DecimalExpression")
        except NotImplementedError:
            pass

    def test_double(self):
        e = comex.DoubleExpression(1.5)
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated DoubleExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "1.5", estr)
        e = comex.DoubleExpression(1.5E2)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "150.0", estr)
        # can take Decimal too)
        d = decimal.Decimal("1.500E+02")
        e = comex.DoubleExpression(d)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "150.0", estr)
        e = comex.DoubleExpression(float('-inf'))
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "-INF", estr)
        e = comex.DoubleExpression(float('inf'))
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "INF", estr)
        e = comex.DoubleExpression(float('nan'))
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "NaN", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated DoubleExpression")
        except NotImplementedError:
            pass

    def test_int64(self):
        e = comex.Int64Expression(3)
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated Int64Expression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "3", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated Int64Expression")
        except NotImplementedError:
            pass

    def test_string(self):
        e = comex.StringExpression("It's My Life")
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated StringExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "'It''s My Life'", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated StringExpression")
        except NotImplementedError:
            pass

    def test_duration(self):
        e = comex.DurationExpression(xsi.Duration('PT15H1.5S'))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated DurationExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "duration'PT15H0M1.500000S'", estr)
        tstr = 'PT15H1.125S'
        e = comex.DurationExpression(xsi.Duration(tstr), tstr)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "duration'" + tstr + "'", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated DurationExpression")
        except NotImplementedError:
            pass

    def test_binary(self):
        e = comex.BinaryDataExpression(b"It's My Life")
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated BinaryDataExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "binary'SXQncyBNeSBMaWZl'", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated BinaryDataExpression")
        except NotImplementedError:
            pass

    def test_enum(self):
        e = comex.EnumExpression(
            names.EnumLiteral("Schema.Type", ("Red", "Green", "Blue")))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated EnumExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "Schema.Type'Red,Green,Blue'", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated EnumExpression")
        except NotImplementedError:
            pass

    def test_geography(self):
        e = comex.GeographyExpression(
            geotypes.PointLiteral(
                srid=4326,
                point=geotypes.Point(-1.00244140625, 51.44775390625)))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated GeographyExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(
            estr == "geography'SRID=4326;"
            "Point(-1.00244140625 51.44775390625)'", estr)
        pstr = "SRID=4326;Point(-1.21053539044307995401 51.44775390625)"
        e = comex.GeographyExpression(
            geotypes.PointLiteral(
                srid=4326,
                point=geotypes.Point(-1.21053539044307995401, 51.44775390625)),
            pstr)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "geography'%s'" % pstr, estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated GeographyExpression")
        except NotImplementedError:
            pass

    def test_geometry(self):
        e = comex.GeometryExpression(
            geotypes.PointLiteral(
                srid=0,
                point=geotypes.Point(-1.00244140625, 51.44775390625)))
        self.assertTrue(isinstance(e, comex.LiteralExpression))
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated GeographyExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(
            estr == "geometry'SRID=0;Point(-1.00244140625 51.44775390625)'",
            estr)
        pstr = "SRID=0;Point(-1.21053539044307995401 51.44775390625)"
        e = comex.GeometryExpression(
            geotypes.PointLiteral(
                srid=0,
                point=geotypes.Point(-1.21053539044307995401, 51.44775390625)),
            pstr)
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "geometry'%s'" % pstr, estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated GeographyExpression")
        except NotImplementedError:
            pass

    def test_parameter(self):
        e = comex.ParameterExpression("param")
        self.assertFalse(isinstance(e, comex.LiteralExpression))
        self.assertTrue(e.is_common())
        # a parameter may result in a boolean
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated ParameterExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "@param")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated ParameterExpression")
        except NotImplementedError:
            pass
        # now check that the evaluator will accept parameters
        self.ef.declare_param("param", comex.Int64Expression(3))
        # but that they don't effect the result of formatting
        op, estr = self.ef.evaluate(e)
        self.assertTrue(estr == "@param")

    def test_root(self):
        e = comex.RootExpression()
        self.assertFalse(isinstance(e, comex.LiteralExpression))
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        # perhaps oddly, but $root is not itself a root expression as it
        # must be joined using the member operator
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated RootExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "$root")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated RootExpression")
        except NotImplementedError:
            pass

    def test_it(self):
        e = comex.ItExpression()
        self.assertFalse(isinstance(e, comex.LiteralExpression))
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated ItExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "$it")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated ItExpression")
        except NotImplementedError:
            pass

    def test_identifier(self):
        # identifier expression represents an odataIdentifier
        e = comex.IdentifierExpression("Property")
        self.assertFalse(isinstance(e, comex.LiteralExpression))
        self.assertTrue(e.is_common())
        # could result in a boolean!  This means that the simple
        # expression "null" is considered to be a boolCommonExpr, not
        # because null is a boolean but because there might be a boolean
        # property called "null" in the schema.  Failure is detected at
        # runtime if, in the most likely case, there is no such property.
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertTrue(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated IdentifierExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "Property")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated IdentifierExpression")
        except NotImplementedError:
            pass
        for rname in (
                "INF", "NaN", "true", "false", "null", "dummy",
                "True", "False", "TRUE", "FALSE"):
            e = comex.IdentifierExpression(rname)
            op, estr = self.ef.evaluate(e)
            self.assertTrue(op == comex.Operator.atom, op)
            self.assertTrue(estr == rname)
            try:
                self.sf.evaluate(e)
                self.fail("SearchFormatter evaluated IdentifierExpression")
            except NotImplementedError:
                pass
        # now check what happens if we have an evaluator that won't let
        # any member operation succeed.  Check that evaluation correctly
        # falls back to the built-in objects
        nmf = NoMemberFormatter()
        for rname in (
                "INF", "NaN", "true", "false", "null"):
            e = comex.IdentifierExpression(rname)
            op, estr = nmf.evaluate(e)
            self.assertTrue(op == comex.Operator.atom, op)
            self.assertTrue(estr == rname)
        for rname in ("True", "False", "TRUE", "FALSE"):
            e = comex.IdentifierExpression(rname)
            op, estr = nmf.evaluate(e)
            self.assertTrue(op == comex.Operator.atom, op)
            self.assertTrue(estr == rname.lower(), estr)
        e = comex.IdentifierExpression("dummy")
        try:
            nmf.evaluate(e)
            self.fail("Expected PathError")
        except errors.PathError:
            pass

    def test_qname(self):
        # qname expression represents a qualified name
        e = comex.QNameExpression(names.QualifiedName("Schema", "Property"))
        self.assertFalse(isinstance(e, comex.LiteralExpression))
        # on their own, qualified names are not actually valid
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated QNameExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "Schema.Property")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated QNameExpression")
        except NotImplementedError:
            pass

    def test_term_ref(self):
        # term_ref expression represents a Term reference
        e = comex.TermRefExpression(
            names.TermRef(names.QualifiedName("Schema", "Term"), "q"))
        self.assertFalse(isinstance(e, comex.LiteralExpression))
        # on their own, term references are not actually valid
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated TermRefExpression")
        except NotImplementedError:
            pass
        try:
            self.ef.evaluate(e)
            self.fail("ExpressionFormatter evaluated TermRefExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated TermRefExpression")
        except NotImplementedError:
            pass

    def test_operator(self):
        add = comex.OperatorExpression(comex.Operator.add)
        # abstract class but does define attributes
        self.assertTrue(add.op_code == comex.Operator.add)
        self.assertTrue(len(add.operands) == 0)
        # need more information before we declare ourselves valid
        self.assertFalse(add.is_common())
        self.assertFalse(add.is_bool_common())
        self.assertFalse(add.is_root())
        self.assertFalse(add.is_first_member())
        self.assertFalse(add.is_member())
        self.assertFalse(add.is_property_path())
        # check we can add arbitrary number of operands
        for i in range3(10):
            add.add_operand(comex.NullExpression())
        self.assertTrue(len(add.operands) == 10)
        sub = comex.OperatorExpression(comex.Operator.sub)
        mul = comex.OperatorExpression(comex.Operator.mul)
        # check comparisons based on sort codes
        self.assertTrue(add < mul)
        self.assertTrue(mul > add)
        self.assertTrue(add == sub)
        self.assertTrue(add == add)
        self.assertTrue(add <= mul)
        self.assertTrue(mul >= add)
        self.assertTrue(add <= sub)
        self.assertTrue(add >= sub)
        try:
            self.ep.evaluate(add)
            self.fail("ExpressionProcessor evaluated CommonExpression")
        except NotImplementedError:
            pass
        try:
            self.ef.evaluate(add)
            self.fail("ExpressionFormatter evaluated CommonExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(add)
            self.fail("SearchFormatter evaluated CommonExpression")
        except NotImplementedError:
            pass
        # check binary_format
        op, estr = comex.OperatorExpression.binary_format(
            (comex.Operator.mul, "2*2"), (comex.Operator.mul, "3*3"),
            comex.Operator.add, "%s+%s")
        self.assertTrue(op == comex.Operator.add)
        self.assertTrue(estr == "2*2+3*3", estr)
        op, estr = comex.OperatorExpression.binary_format(
            (comex.Operator.add, "2+2"), (comex.Operator.add, "3+3"),
            comex.Operator.mul, "%s*%s")
        self.assertTrue(estr == "(2+2)*(3+3)", estr)
        # check unary_format
        op, estr = comex.OperatorExpression.unary_format(
            (comex.Operator.call, "length(A)"), comex.Operator.negate, "-%s")
        self.assertTrue(op == comex.Operator.negate)
        self.assertTrue(estr == "-length(A)", estr)
        op, estr = comex.OperatorExpression.unary_format(
            (comex.Operator.add, "2+2"), comex.Operator.negate, "-%s")
        self.assertTrue(estr == "-(2+2)", estr)

    def test_collection_expression(self):
        e = comex.CollectionExpression()
        self.assertTrue(isinstance(e, comex.OperatorExpression))
        self.assertTrue(e.op_code == comex.Operator.collection)
        # with no operands it is a valid empty collection
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated CollectionExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.collection, op)
        self.assertTrue(estr == "[]")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated CollectionExpression")
        except NotImplementedError:
            pass
        e.add_operand(comex.Int64Expression(3))
        self.assertTrue(self.ef.evaluate(e)[1] == "[3]")
        e.add_operand(comex.IdentifierExpression("Age"))
        # not a legal URI expression, rendered with angle brackets...
        self.assertTrue(self.ef.evaluate(e)[1] == "[3,<Age>]")

    def test_record_expression(self):
        e = comex.RecordExpression()
        self.assertTrue(isinstance(e, comex.OperatorExpression))
        self.assertTrue(e.op_code == comex.Operator.record)
        # with no operands it is a valid empty record
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated RecordExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.record, op)
        self.assertTrue(estr == "{}")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated RecordExpression")
        except NotImplementedError:
            pass
        try:
            e.add_operand(comex.Int64Expression(3))
            self.fail("Record requires MemberBindExpression")
        except ValueError:
            pass
        m = comex.MemberBindExpression()
        m.add_operand(comex.IdentifierExpression("Name"))
        m.add_operand(comex.StringExpression("John"))
        e.add_operand(m)
        self.assertTrue(self.ef.evaluate(e)[1] == '{"Name":"John"}')
        m = comex.MemberBindExpression()
        m.add_operand(
            comex.TermRefExpression(
                names.TermRef(names.QualifiedName("Schema", "Term"), "q")))
        m.add_operand(comex.StringExpression("Jane"))
        e.add_operand(m)
        self.assertTrue(self.ef.evaluate(e)[1] ==
                        '{"Name":"John","@Schema.Term#q":"Jane"}',
                        self.ef.evaluate(e)[1])

    def test_member_bind(self):
        e = comex.MemberBindExpression()
        self.assertTrue(e.name is None)
        try:
            e.add_operand(comex.Int64Expression(3))
            self.fail("MemberBind requires name")
        except ValueError:
            pass
        e.add_operand(comex.IdentifierExpression("x"))
        self.assertTrue(e.name == "x")
        self.assertFalse(e.is_common())
        e.add_operand(comex.StringExpression("literalA"))
        self.assertFalse(e.is_common())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated MemberBindExpression")
        except errors.ExpressionError:
            pass
        try:
            self.ef.evaluate(e)
            self.fail("ExpressionFormatter evaluated MemberBindExpression")
        except errors.ExpressionError:
            pass
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated MemberBindExpression")
        except errors.ExpressionError:
            pass
        # you can't add any more operands to a member bind
        try:
            e.add_operand(comex.IdentifierExpression("PropertyB"))
            self.fail('x:"literalA","literalB"')
        except ValueError:
            pass
        # an alternative to an identifier is a TermRef
        e = comex.MemberBindExpression()
        e.add_operand(
            comex.TermRefExpression(names.TermRef.from_str("@Schema.Type#q")))
        self.assertTrue(isinstance(e.name, names.TermRef))
        self.assertTrue(to_text(e.name) == "@Schema.Type#q")
        e.add_operand(comex.StringExpression("literalA"))
        self.assertFalse(e.is_common())
        # but not a QName
        e = comex.MemberBindExpression()
        try:
            e.add_operand(
                comex.QNameExpression(
                    names.QualifiedName.from_str("Schema.Type")))
            self.fail("MemberBind requires name or term ref, not qname")
        except ValueError:
            pass

    def test_binary_operator(self):
        add = comex.BinaryExpression(comex.Operator.add)
        self.assertFalse(add.is_common())
        # we should only be able to add two arguments
        add.add_operand(comex.NullExpression())
        add.add_operand(comex.NullExpression())
        try:
            add.add_operand(comex.NullExpression())
            self.fail("BinaryOperator with 3 operands")
        except ValueError:
            pass
        try:
            self.ep.evaluate(add)
            self.fail("ExpressionProcessor evaluated BinaryExpression")
        except NotImplementedError:
            pass
        try:
            self.ef.evaluate(add)
            self.fail("ExpressionFormatter evaluated BinaryExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(add)
            self.fail("SearchFormatter evaluated BinaryExpression")
        except NotImplementedError:
            pass

    def test_member(self):
        e = comex.MemberExpression()
        self.assertTrue(isinstance(e, comex.BinaryExpression))
        self.assertTrue(e.op_code == comex.Operator.member)
        # with no arguments it is not a common expression
        self.assertFalse(e.is_common())
        # add some operands, start simple
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertFalse(e.is_common())
        e.add_operand(comex.IdentifierExpression("B"))
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertTrue(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated MemberExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.member, op)
        self.assertTrue(estr == "A/B")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated MemberExpression")
        except NotImplementedError:
            pass
        # test rotation
        # A/B
        e1 = comex.MemberExpression()
        a = comex.IdentifierExpression("A")
        e1.add_operand(a)
        e1.add_operand(comex.IdentifierExpression("B"))
        self.assertTrue(e1.is_common())
        # A/B / C
        e2 = comex.MemberExpression()
        e2.add_operand(e1)
        e2.add_operand(comex.IdentifierExpression("C"))
        # A/B/C /D
        e3 = comex.MemberExpression()
        e3.add_operand(e2)
        self.assertFalse(e3.is_common())
        e3.add_operand(comex.IdentifierExpression("D"))
        self.assertTrue(e3.is_common())
        self.assertTrue(e3.operands[0] is a)
        op, estr = self.ef.evaluate(e3)
        self.assertTrue(op == comex.Operator.member, op)
        self.assertTrue(estr == "A/B/C/D", estr)
        # now try adding a right associated node (for completeness)
        # shouldn't happen as the parser uses only left association
        e4 = comex.MemberExpression()
        e4.add_operand(comex.IdentifierExpression("E"))
        e4.add_operand(comex.IdentifierExpression("F"))
        e5 = comex.MemberExpression()
        e5.add_operand(e3)
        e5.add_operand(e4)
        # test ABNF rule checkers
        e = comex.MemberExpression()
        e.add_operand(comex.RootExpression())   # incomplete
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_function())
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertTrue(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "$root/A")
        #
        e = comex.MemberExpression()
        e.add_operand(comex.RootExpression())
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "func")))
        # $root/schema.function
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "$root/schema.func")
        #
        e = comex.MemberExpression()
        e.add_operand(comex.ItExpression())
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "$it/A")
        #
        e = comex.MemberExpression()
        e.add_operand(comex.IdentifierExpression("A"))
        e.add_operand(comex.IdentifierExpression("B"))
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertTrue(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "A/B")
        #
        e = comex.MemberExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "type")))
        e.add_operand(comex.IdentifierExpression("A"))  # schema.type/A
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "schema.type/A")
        #
        e = comex.MemberExpression()
        e.add_operand(comex.IdentifierExpression("A"))
        e1 = comex.CallExpression()
        e1.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "type")))
        e2 = comex.ArgsExpression()
        e2.add_operand(comex.Int64Expression(3))
        e1.add_operand(e2)
        e.add_operand(e1)
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertTrue(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "A/schema.type(3)")
        #
        e = comex.MemberExpression()
        e.add_operand(comex.IdentifierExpression("A"))
        e1 = comex.MemberExpression()
        e1.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "type")))
        e1.add_operand(comex.CountExpression())
        e.add_operand(e1)
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertTrue(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "A/schema.type/$count")
        #
        e = comex.MemberExpression()
        e1 = comex.CallExpression()
        e1.add_operand(comex.IdentifierExpression("A"))
        e2 = comex.ArgsExpression()
        e2.add_operand(comex.Int64Expression(3))
        e1.add_operand(e2)
        e.add_operand(e1)
        e.add_operand(comex.IdentifierExpression("B"))
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertTrue(e.is_property_path())
        self.assertFalse(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "A(3)/B")
        #
        e = comex.MemberExpression()
        e1 = comex.CallExpression()
        e2 = comex.CallExpression()
        e2.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "func")))
        e3 = comex.ArgsExpression()
        e4 = comex.BindExpression()
        e4.add_operand(comex.IdentifierExpression("a"))
        e4.add_operand(comex.Int64Expression(1))
        e3.add_operand(e4)
        e2.add_operand(e3)
        e1.add_operand(e2)
        e5 = comex.ArgsExpression()
        e5.add_operand(comex.Int64Expression(3))
        e1.add_operand(e5)
        e.add_operand(e1)
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertTrue(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "schema.func(a=1)(3)/A")
        #
        e = comex.MemberExpression()
        e1 = comex.CallExpression()
        e1.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "func")))
        e2 = comex.ArgsExpression()
        e3 = comex.BindExpression()
        e3.add_operand(comex.IdentifierExpression("a"))
        e3.add_operand(comex.Int64Expression(1))
        e2.add_operand(e3)
        e1.add_operand(e2)
        e.add_operand(e1)
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertTrue(e.is_function())
        self.assertTrue(self.ef.evaluate(e)[1] == "schema.func(a=1)/A")
        #
        e = comex.MemberExpression()
        e1 = comex.CallExpression()
        e1.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "func")))
        e2 = comex.ArgsExpression()
        e3 = comex.BindExpression()
        e3.add_operand(comex.IdentifierExpression("a"))
        e3.add_operand(comex.Int64Expression(1))
        e2.add_operand(e3)
        e1.add_operand(e2)
        e.add_operand(e1)
        e4 = comex.CallExpression()
        e4.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "type")))
        e5 = comex.ArgsExpression()
        e5.add_operand(comex.Int64Expression(3))
        e4.add_operand(e5)
        e.add_operand(e4)
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertTrue(e.is_function())
        self.assertTrue(
            self.ef.evaluate(e)[1] == "schema.func(a=1)/schema.type(3)")
        #
        e = comex.MemberExpression()
        e1 = comex.CallExpression()
        e1.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "func")))
        e2 = comex.ArgsExpression()
        e3 = comex.BindExpression()
        e3.add_operand(comex.IdentifierExpression("a"))
        e3.add_operand(comex.Int64Expression(1))
        e2.add_operand(e3)
        e1.add_operand(e2)
        e.add_operand(e1)
        e4 = comex.MemberExpression()
        e4.add_operand(
            comex.QNameExpression(names.QualifiedName("schema", "type")))
        e4.add_operand(comex.CountExpression())
        e.add_operand(e4)
        self.assertFalse(e.is_root())
        self.assertTrue(e.is_first_member())
        self.assertTrue(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertTrue(e.is_function())
        self.assertTrue(
            self.ef.evaluate(e)[1] == "schema.func(a=1)/schema.type/$count")
        #
        e = comex.MemberExpression()
        e.add_operand(comex.IdentifierExpression("A"))
        e.add_operand(comex.ItExpression())
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_function())
        try:
            self.ef.evaluate(e)
            self.fail("A/$it")
        except errors.ExpressionError:
            pass

    def test_call(self):
        e = comex.CallExpression()
        self.assertTrue(isinstance(e, comex.BinaryExpression))
        self.assertTrue(e.op_code == comex.Operator.call)
        self.assertTrue(e.method is None)
        # with no arguments it is not a valid keyPredicate
        self.assertFalse(e.is_id_and_key())
        self.assertFalse(e.is_qname_and_key())
        # with no arguments it is not a common expression
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_collection_path())
        # add some operands, start simple, left operand must be
        # an Identifier, QName or another Call
        try:
            e.add_operand(comex.RootExpression())
            self.fail("$root()")
        except ValueError:
            pass
        e.add_operand(comex.IdentifierExpression("now"))
        self.assertTrue(e.method == comex.Method.now)
        self.assertFalse(e.is_id_and_key())
        self.assertFalse(e.is_qname_and_key())
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_collection_path())
        # two arguments required for evaluation
        try:
            self.ef.evaluate(e)
            self.fail("CallExpression with no ArgsExpression")
        except errors.ExpressionError:
            pass
        try:
            with self.ef.new_context((100, "A")):
                e.evaluate_path_node(self.ef)
            self.fail("CallExpression with no ArgsExpression")
        except errors.ExpressionError:
            pass
        # the right operand must be an args expression
        try:
            e.add_operand(comex.IdentifierExpression("B"))
            self.fail("Call requires Args")
        except ValueError:
            pass
        args = comex.ArgsExpression()
        e.add_operand(args)
        self.assertFalse(e.is_id_and_key())
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())    # now() can't be nav(key)
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())   # now() can't be nav(key)
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        self.assertFalse(e.is_collection_path(), "now() collectionPathExpr")
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated MemberExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.call, op)
        self.assertTrue(estr == "now()")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated CallExpression")
        except NotImplementedError:
            pass
        # check we don't interpret method aliases
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("geo", "length")))
        self.assertTrue(e.method == comex.Method.geo_length)
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("geo_length"))
        self.assertTrue(e.method is None)
        #
        # check that keyPredicate forms are not boolean functions or
        # collection paths
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("Products"))
        args = comex.ArgsExpression()
        e.add_operand(args)
        args.add_operand(comex.Int64Expression(3))
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_collection_path())
        self.assertTrue(self.ef.evaluate(e)[1] == "Products(3)")
        with self.ef.new_context((100, "A")):
            self.assertTrue(
                e.evaluate_path_node(self.ef)[1] == "A/Products(3)")
        #
        # check that function forms are (possible) boolean functions and
        # possible collectionPathExprs (ignoring required / prefix)
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("Schema", "Func")))
        args = comex.ArgsExpression()
        e.add_operand(args)
        e1 = comex.BindExpression()
        e1.add_operand(comex.IdentifierExpression("a"))
        e1.add_operand(comex.Int64Expression(3))
        args.add_operand(e1)
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertTrue(e.is_collection_path())
        self.assertTrue(self.ef.evaluate(e)[1] == "Schema.Func(a=3)")
        with self.ef.new_context((100, "A")):
            self.assertTrue(
                e.evaluate_path_node(self.ef)[1] == "A/Schema.Func(a=3)")
        #
        # check collection returning functions can be called
        e2 = comex.CallExpression()
        e2.add_operand(e)
        args = comex.ArgsExpression()
        e2.add_operand(args)
        args.add_operand(comex.Int64Expression(1))
        self.assertTrue(e2.is_common())
        self.assertTrue(e2.is_bool_common())
        self.assertTrue(e2.is_collection_path())
        self.assertTrue(self.ef.evaluate(e2)[1] == "Schema.Func(a=3)(1)")
        with self.ef.new_context((100, "A")):
            self.assertTrue(
                e2.evaluate_path_node(self.ef)[1] == "A/Schema.Func(a=3)(1)")
        #
        # check that boolean methods are boolean functions
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("startswith"))
        args = comex.ArgsExpression()
        e.add_operand(args)
        args.add_operand(comex.StringExpression("abc"))
        args.add_operand(comex.StringExpression("a"))
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_collection_path())
        self.assertTrue(self.ef.evaluate(e)[1] == "startswith('abc','a')")
        #
        # check that isof methods are boolean functions
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("isof"))
        args = comex.ArgsExpression()
        args.add_operand(
            comex.QNameExpression(names.QualifiedName("Edm", "String")))
        e.add_operand(args)
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_collection_path())
        self.assertTrue(self.ef.evaluate(e)[1] == "isof(Edm.String)",
                        self.ef.evaluate(e)[1])
        #
        # a bound function requires arguments (even if empty)
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("Schema", "Func")))
        self.assertFalse(e.is_function())
        args = comex.ArgsExpression()
        e.add_operand(args)
        self.assertTrue(e.is_function())
        self.assertTrue(e.is_collection_path())
        #
        # check all
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("all"))
        args = comex.ArgsExpression()
        e1 = comex.LambdaBindExpression()
        e1.add_operand(comex.IdentifierExpression("x"))
        e2 = comex.EqExpression()
        e2.add_operand(comex.IdentifierExpression("x"))
        e2.add_operand(comex.Int64Expression(3))
        e1.add_operand(e2)
        args.add_operand(e1)
        e.add_operand(args)
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertTrue(e.is_collection_path())
        try:
            self.ef.evaluate(e)
            self.fail("all outside path")
        except errors.ExpressionError:
            pass
        with self.ef.new_context((100, "Integers")):
            self.assertTrue(
                e.evaluate_path_node(self.ef)[1] == "Integers/all(x:x eq 3)")
        e.operands[0].identifier = "any"
        with self.ef.new_context((100, "Integers")):
            self.assertTrue(
                e.evaluate_path_node(self.ef)[1] == "Integers/any(x:x eq 3)")
        #
        # check geo functions render property
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("geo", "distance")))
        args = comex.ArgsExpression()
        args.add_operand(comex.IdentifierExpression("PointA"))
        args.add_operand(comex.IdentifierExpression("PointB"))
        e.add_operand(args)
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_collection_path(), "bad func params")
        self.assertTrue(
            self.ef.evaluate(e)[1] == "geo.distance(PointA,PointB)")
        #
        # check annotation functions will render (they don't parse)
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName("odata", "concat")))
        args = comex.ArgsExpression()
        args.add_operand(comex.IdentifierExpression("LastName"))
        args.add_operand(comex.StringExpression(", "))
        args.add_operand(comex.IdentifierExpression("FirstName"))
        e.add_operand(args)
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_collection_path(), "bad func params")
        self.assertTrue(
            self.ef.evaluate(e)[1] == "odata.concat(LastName,', ',FirstName)")
        #
        # check explicit cast
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("cast"))
        args = comex.ArgsExpression()
        args.add_operand(comex.IdentifierExpression("Name"))
        args.add_operand(
            comex.QNameExpression(names.QualifiedName("Edm", "String")))
        e.add_operand(args)
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_collection_path(), "bad func params")
        self.assertTrue(
            self.ef.evaluate(e)[1] == "cast(Name,Edm.String)")
        #
        # check correct fallback from keyPredicate-like method call
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression("length"))
        args = comex.ArgsExpression()
        args.add_operand(comex.StringExpression("A Piece Of String"))
        e.add_operand(args)
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_collection_path(), "bad func param")
        self.assertTrue(
            self.ef.evaluate(e)[1] == "length('A Piece Of String')")
        nmf = NoMemberFormatter()
        self.assertTrue(
            nmf.evaluate(e)[1] == "length('A Piece Of String')")
        #
        # evaluation of badly formed CallExpression (can't happen so
        # hack in the lnode)
        e = comex.CallExpression()
        e.operands.append(comex.StringExpression("now"))
        args = comex.ArgsExpression()
        e.add_operand(args)
        try:
            self.ef.evaluate(e)
            self.fail("'now'()")
        except errors.ExpressionError:
            pass
        try:
            with self.ef.new_context((100, "A")):
                e.evaluate_path_node(self.ef)[1]
            self.fail("A/'now'()")
        except errors.ExpressionError:
            pass

    def test_call_methods(self):
        # check eval path for named methods
        for method_name, nargs in (
                ('mindatetime', 0),
                ('maxdatetime', 0),
                ('now', 0),
                ('length', 1),
                ('tolower', 1),
                ('toupper', 1),
                ('trim', 1),
                ('year', 1),
                ('month', 1),
                ('day', 1),
                ('hour', 1),
                ('minute', 1),
                ('second', 1),
                ('fractionalseconds', 1),
                ('totalseconds', 1),
                ('date', 1),
                ('time', 1),
                ('totaloffsetminutes', 1),
                ('round', 1),
                ('floor', 1),
                ('ceiling', 1),
                ('contains', 2),
                ('startswith', 2),
                ('endswith', 2),
                ('indexof', 2),
                ('concat', 2)):
            e = comex.CallExpression()
            e.add_operand(comex.IdentifierExpression(method_name))
            args = comex.ArgsExpression()
            e.add_operand(args)
            i = 0
            while i < 5:
                estr = "%s(%s)" % (method_name, ",".join(["Arg"] * i))
                # these don't match keyPredicate forms so should fail
                # unless they are recognized methods
                if i == nargs:
                    self.assertTrue(
                        self.ef.evaluate(e)[1] == estr,
                        "Found %r expected %r" %
                        (self.ef.evaluate(e)[1], estr))
                else:
                    try:
                        self.ef.evaluate(e)
                        self.fail(estr)
                    except errors.ExpressionError:
                        pass
                args.add_operand(comex.IdentifierExpression("Arg"))
                i += 1
        #
        # check substring: special 2 or 3 parameter form
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression('substring'))
        args = comex.ArgsExpression()
        e.add_operand(args)
        for i in range3(5):
            estr = "substring(%s)" % ",".join(["Arg"] * i)
            if i in (2, 3):
                self.assertTrue(
                    self.ef.evaluate(e)[1] == estr,
                    "Found %r expected %r" %
                    (self.ef.evaluate(e)[1], estr))
            else:
                try:
                    self.ef.evaluate(e)
                    self.fail(estr)
                except errors.ExpressionError:
                    pass
            args.add_operand(comex.IdentifierExpression("Arg"))
        #
        # check geo methods
        for method_name, nargs in (
                ('length', 1),
                ('intersects', 2),
                ('distance', 2)):
            e = comex.CallExpression()
            e.add_operand(
                comex.QNameExpression(names.QualifiedName("geo", method_name)))
            args = comex.ArgsExpression()
            e.add_operand(args)
            i = 0
            while i < 5:
                estr = "geo.%s(%s)" % (method_name, ",".join(["Arg"] * i))
                # these don't match boundFunction or keyPredicate forms
                # so should fail unless they are recognized methods
                if i == nargs:
                    self.assertTrue(
                        self.ef.evaluate(e)[1] == estr,
                        "Found %r expected %r" %
                        (self.ef.evaluate(e)[1], estr))
                else:
                    try:
                        self.ef.evaluate(e)
                        self.fail(estr)
                    except errors.ExpressionError:
                        pass
                args.add_operand(comex.IdentifierExpression("Arg"))
                i += 1
        #
        # check non-methods
        e = comex.CallExpression()
        e.add_operand(comex.IdentifierExpression('unknown'))
        args = comex.ArgsExpression()
        e.add_operand(args)
        try:
            self.ef.evaluate(e)
            self.fail("unknown()")
        except errors.ExpressionError:
            pass

    def test_call_odata_methods(self):
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName('odata', 'concat')))
        args = comex.ArgsExpression()
        e.add_operand(args)
        for i in range3(10):
            estr = "odata.concat(%s)" % ",".join(["Arg"] * i)
            if i >= 2:
                self.assertTrue(
                    self.ef.evaluate(e)[1] == estr,
                    "Found %r expected %r" %
                    (self.ef.evaluate(e)[1], estr))
            else:
                try:
                    self.ef.evaluate(e)
                    self.fail(estr)
                except errors.ExpressionError:
                    pass
            args.add_operand(comex.IdentifierExpression("Arg"))
        #
        # check odata.fillUriTemplate
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(
                names.QualifiedName('odata', 'fillUriTemplate')))
        args = comex.ArgsExpression()
        e.add_operand(args)
        try:
            self.ef.evaluate(e)
            self.fail("odata.fillUriTemplate with no args")
        except errors.ExpressionError:
            pass
        args.add_operand(
            comex.StringExpression(
                "http://host/someAPI/Actors/{actorName}/CV"))
        self.assertTrue(
            self.ef.evaluate(e)[1] ==
            "odata.fillUriTemplate("
            "'http://host/someAPI/Actors/{actorName}/CV')")
        #
        # check odata.uriEncode
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName('odata', 'uriEncode')))
        args = comex.ArgsExpression()
        e.add_operand(args)
        try:
            self.ef.evaluate(e)
            self.fail("odata.uriEncode with no args")
        except errors.ExpressionError:
            pass
        args.add_operand(comex.StringExpression("Ryan O'Neal"))
        self.assertTrue(
            self.ef.evaluate(e)[1] == "odata.uriEncode('Ryan O''Neal')")
        #
        # check odata.cast(commonExpr, qname)
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName('odata', 'cast')))
        args = comex.ArgsExpression()
        e.add_operand(args)
        try:
            self.ef.evaluate(e)
            self.fail("odata.cast with no args")
        except errors.ExpressionError:
            pass
        args.add_operand(comex.IdentifierExpression("Property"))
        try:
            self.ef.evaluate(e)
            self.fail("odata.cast with a single argument")
        except errors.ExpressionError:
            pass
        # the second operand must by a TypeExpression
        args.add_operand(
            comex.QNameExpression(names.QualifiedName('schema', 'type')))
        try:
            self.ef.evaluate(e)
            self.fail("odata.cast with a QName instead of type")
        except errors.ExpressionError:
            pass
        #
        # check odata.cast(commonExpr, type)
        e = comex.CallExpression()
        e.add_operand(
            comex.QNameExpression(names.QualifiedName('odata', 'cast')))
        args = comex.ArgsExpression()
        e.add_operand(args)
        args.add_operand(comex.IdentifierExpression("Property"))

        class MockType(object):

            def __repr__(self):
                return "schema.MockType"

        type_def = MockType()
        args.add_operand(comex.TypeExpression(type_def))
        self.assertTrue(
            self.ef.evaluate(e)[1] == "cast(Property,schema.MockType)")
        #
        # check isof
        e.operands[0].identifier = names.QualifiedName('odata', 'isof')
        self.assertTrue(
            self.ef.evaluate(e)[1] == "isof(Property,schema.MockType)")
        #
        # check bad odata name
        e.operands[0].identifier = names.QualifiedName('odata', 'unknown')
        try:
            self.ef.evaluate(e)
            self.fail("odata.cast with a QName instead of type")
        except errors.ExpressionError:
            pass

    def test_args(self):
        # with no args
        e = comex.ArgsExpression()
        self.assertTrue(isinstance(e, comex.OperatorExpression))
        self.assertTrue(e.op_code == comex.Operator.args)
        self.assertFalse(e.is_key_predicate())
        self.assertTrue(e.is_function_parameters())     # schema.func() OK
        self.assertTrue(e.is_method_parameters())       # e.g., now()
        self.assertTrue(e.is_any())                     # any() is OK
        name, expr = e.get_lambda_args()
        self.assertTrue(name is None)
        self.assertTrue(expr is None)
        self.assertFalse(e.is_all())                    # all() is not!
        # for isof and cast
        type_arg, expr_arg = e.get_type_args()
        self.assertTrue(type_arg is None)
        self.assertTrue(expr_arg is None)
        self.assertFalse(e.is_type_args())
        estr_list = self.ep.evaluate(e)
        self.assertTrue(isinstance(estr_list, list))
        self.assertTrue(len(estr_list) == 0)
        estr_list = self.ef.evaluate(e)
        self.assertTrue(isinstance(estr_list, list))
        self.assertTrue(len(estr_list) == 0)
        estr_list = self.sf.evaluate(e)
        self.assertTrue(isinstance(estr_list, list))
        self.assertTrue(len(estr_list) == 0)
        #
        # Test single literal argument
        e.add_operand(comex.Int64Expression(1))
        self.assertTrue(e.is_key_predicate())
        self.assertFalse(e.is_function_parameters())
        self.assertTrue(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        type_arg, expr_arg = e.get_type_args()
        self.assertTrue(isinstance(type_arg, comex.Int64Expression))
        self.assertTrue(expr_arg is None)
        self.assertFalse(e.is_type_args())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated non-empty ArgsExpression")
        except NotImplementedError:
            pass
        estr_list = self.ef.evaluate(e)
        self.assertTrue(isinstance(estr_list, list))
        self.assertTrue(len(estr_list) == 1)
        self.assertTrue(estr_list[0][0] == comex.Operator.atom)
        self.assertTrue(estr_list[0][1] == "1")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated non-empty ArgsExpression")
        except NotImplementedError:
            pass
        #
        # Test multiple literal arguments
        e.add_operand(comex.Int64Expression(2))
        self.assertFalse(e.is_key_predicate())      # Products(1,2) not OK
        self.assertFalse(e.is_function_parameters())
        self.assertTrue(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        self.assertFalse(e.is_type_args())
        estr_list = self.ef.evaluate(e)
        self.assertTrue(estr_list[0][1] == "1")
        self.assertTrue(estr_list[1][1] == "2")
        #
        # Test single bind
        e = comex.ArgsExpression()
        e1 = comex.BindExpression()
        e1.add_operand(comex.IdentifierExpression("a"))
        e1.add_operand(comex.Int64Expression(1))
        e.add_operand(e1)
        self.assertTrue(e.is_key_predicate())      # Products(a=1) OK
        self.assertTrue(e.is_function_parameters())
        self.assertFalse(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        self.assertFalse(e.is_type_args())
        estr_list = self.ef.evaluate(e)
        self.assertTrue(estr_list[0][1] == "a=1")
        #
        # Test multiple bind
        e = comex.ArgsExpression()
        e1 = comex.BindExpression()
        e1.add_operand(comex.IdentifierExpression("a"))
        e1.add_operand(comex.Int64Expression(1))
        e.add_operand(e1)
        e2 = comex.BindExpression()
        e2.add_operand(comex.IdentifierExpression("b"))
        e2.add_operand(comex.Int64Expression(2))
        e.add_operand(e2)
        self.assertTrue(e.is_key_predicate())      # Products(a=1,b=2) OK
        self.assertTrue(e.is_function_parameters())
        self.assertFalse(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        self.assertFalse(e.is_type_args())
        estr_list = self.ef.evaluate(e)
        self.assertTrue(estr_list[1][1] == "b=2")
        #
        # Test mixed bind
        e = comex.ArgsExpression()
        e1 = comex.BindExpression()
        e1.add_operand(comex.IdentifierExpression("a"))
        e1.add_operand(comex.Int64Expression(1))
        e.add_operand(e1)
        e.add_operand(comex.Int64Expression(2))
        self.assertFalse(e.is_key_predicate())      # Products(a=1,2)
        self.assertFalse(e.is_function_parameters())
        self.assertFalse(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        self.assertFalse(e.is_type_args())
        estr_list = self.ef.evaluate(e)
        self.assertTrue(estr_list[1][1] == "2")
        #
        # Test bind to expression
        e = comex.ArgsExpression()
        e1 = comex.BindExpression()
        e1.add_operand(comex.IdentifierExpression("a"))
        e2 = comex.AddExpression()
        e2.add_operand(comex.Int64Expression(2))
        e2.add_operand(comex.Int64Expression(2))
        e1.add_operand(e2)
        e.add_operand(e1)
        self.assertFalse(e.is_key_predicate())      # Products(a=2 add 2)
        self.assertTrue(e.is_function_parameters())
        self.assertFalse(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        self.assertFalse(e.is_type_args())
        estr_list = self.ef.evaluate(e)
        self.assertTrue(estr_list[0][1] == "a=2 add 2")
        #
        # Test single expression
        e = comex.ArgsExpression()
        e1 = comex.AddExpression()
        e1.add_operand(comex.Int64Expression(2))
        e1.add_operand(comex.Int64Expression(2))
        e.add_operand(e1)
        self.assertFalse(e.is_key_predicate())      # Products(2 add 2)
        self.assertFalse(e.is_function_parameters())
        self.assertTrue(e.is_method_parameters())
        self.assertFalse(e.is_any())
        self.assertFalse(e.is_all())
        self.assertFalse(e.is_type_args())
        estr_list = self.ef.evaluate(e)
        self.assertTrue(estr_list[0][1] == "2 add 2")
        #
        # Test single lambda expression
        e = comex.ArgsExpression()
        e1 = comex.LambdaBindExpression()
        e1.add_operand(comex.IdentifierExpression("a"))
        e2 = comex.EqExpression()
        e2.add_operand(comex.IdentifierExpression("a"))
        e2.add_operand(comex.Int64Expression(2))
        e1.add_operand(e2)
        e.add_operand(e1)
        self.assertFalse(e.is_key_predicate())      # Products(a:a eq 2)
        self.assertFalse(e.is_function_parameters())
        self.assertFalse(e.is_method_parameters())
        self.assertTrue(e.is_any())
        self.assertTrue(e.is_all())
        name, expr = e.get_lambda_args()
        self.assertTrue(name == "a")
        self.assertTrue(self.ef.evaluate(expr)[1] == "a eq 2")
        self.assertFalse(e.is_type_args())
        try:
            self.ef.evaluate(e)
            self.fail("Lambda out of context")
        except errors.ExpressionError:
            pass

    def test_bind(self):
        # test abstract
        e = comex.BindExpression()
        self.assertTrue(e.name is None)
        try:
            e.add_operand(
                comex.TermRefExpression(
                    names.TermRef.from_str("@Schema.Type")))
            self.fail("Bind requires name")
        except ValueError:
            pass
        e.add_operand(comex.IdentifierExpression("x"))
        self.assertTrue(e.name == "x")
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_function_parameter())
        try:
            self.ef.evaluate(e)
            self.fail("Incomplete bind")
        except errors.ExpressionError:
            pass
        e.add_operand(comex.IdentifierExpression("Property"))
        self.assertFalse(e.is_common())
        self.assertTrue(e.is_function_parameter())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated non-empty BindExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.bind)
        self.assertTrue(estr == "x=Property")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated non-empty BindExpression")
        except NotImplementedError:
            pass
        # you can't add any more operands to a bind
        try:
            e.add_operand(comex.IdentifierExpression("PropertyB"))
            self.fail("x=Property,PropertyB")
        except ValueError:
            pass
        e = comex.BindExpression()
        e.add_operand(comex.IdentifierExpression("x"))
        e.add_operand(comex.RootExpression())
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_function_parameter(), "f param be common")

    def test_lambda_bind(self):
        e = comex.LambdaBindExpression()
        self.assertTrue(e.name is None)
        try:
            e.add_operand(comex.Int64Expression(3))
            self.fail("LambdaBind requires name")
        except ValueError:
            pass
        e.add_operand(comex.IdentifierExpression("x"))
        self.assertTrue(e.name == "x")
        self.assertFalse(e.is_common())
        e.add_operand(comex.IdentifierExpression("Property"))
        self.assertFalse(e.is_common())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated LambdaBindExpression")
        except errors.ExpressionError:
            pass
        try:
            self.ef.evaluate(e)
            self.fail("ExpressionFormatter evaluated LambdaBindExpression")
        except errors.ExpressionError:
            pass
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated LambdaBindExpression")
        except errors.ExpressionError:
            pass
        # you can't add any more operands to a lambda bind
        try:
            e.add_operand(comex.IdentifierExpression("PropertyB"))
            self.fail("x:Property,PropertyB")
        except ValueError:
            pass

    def test_binary_op(self):
        for cls, name, op_match, be, le in (
                (comex.AndExpression, "and", comex.Operator.bool_and, True,
                 True),
                (comex.OrExpression, "or", comex.Operator.bool_or, True, True),
                (comex.EqExpression, "eq", comex.Operator.eq, True, False),
                (comex.NeExpression, "ne", comex.Operator.ne, True, False),
                (comex.LtExpression, "lt", comex.Operator.lt, True, False),
                (comex.LeExpression, "le", comex.Operator.le, True, False),
                (comex.GtExpression, "gt", comex.Operator.gt, True, False),
                (comex.GeExpression, "ge", comex.Operator.ge, True, False),
                (comex.AddExpression, "add", comex.Operator.add, False, False),
                (comex.SubExpression, "sub", comex.Operator.sub, False, False),
                (comex.MulExpression, "mul", comex.Operator.mul, False, False),
                (comex.DivExpression, "div", comex.Operator.div, False, False),
                (comex.ModExpression, "mod", comex.Operator.mod, False,
                 False)):
            e = cls()
            self.assertFalse(e.is_common(), "%s no args is common" % name)
            self.assertFalse(e.is_bool_common(), "%s no args is bool" % name)
            try:
                self.ef.evaluate(e)
                self.fail("%s no args evaluated" % name)
            except errors.ExpressionError:
                pass
            if le:
                # try adding a non-boolean expression
                try:
                    e.add_operand(comex.Int64Expression(1))
                    self.fail("1 %s..." % name)
                except ValueError:
                    pass
            e.add_operand(comex.IdentifierExpression("A"))
            self.assertFalse(e.is_common(), "A %s... is common" % name)
            self.assertFalse(e.is_bool_common(), "A %s... is bool" % name)
            try:
                self.ef.evaluate(e)
                self.fail("A %s... evaluated" % name)
            except errors.ExpressionError:
                pass
            e.add_operand(comex.IdentifierExpression("B"))
            self.assertTrue(e.is_common(), "A %s B is not common" % name)
            self.assertTrue(e.is_bool_common() is be,
                            "A %s B bool mismatch" % name)
            try:
                self.ep.evaluate(e)
                self.fail("ExpressionProcessor evaluated %s" % cls.__name__)
            except NotImplementedError:
                pass
            op, estr = self.ef.evaluate(e)
            self.assertTrue(op == op_match)
            self.assertTrue(estr == "A %s B" % name)
            try:
                self.sf.evaluate(e)
                self.fail("SearchFormatter evaluated %s" % cls.__name__)
            except NotImplementedError:
                pass

    def test_has(self):
        e = comex.HasExpression()
        self.assertFalse(e.is_common(), "has with no args is common")
        self.assertFalse(e.is_bool_common(), "has with no args is bool")
        try:
            self.ef.evaluate(e)
            self.fail("has with no args evaluated")
        except errors.ExpressionError:
            pass
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertFalse(e.is_common(), "A has... is common")
        self.assertFalse(e.is_bool_common(), "A has... is bool")
        try:
            self.ef.evaluate(e)
            self.fail("A has... evaluated")
        except errors.ExpressionError:
            pass
        try:
            e.add_operand(comex.IdentifierExpression("B"))
            self.fail("has requires enum")
        except ValueError:
            pass
        e.add_operand(
            comex.EnumExpression(
                names.EnumLiteral("Schema.Type", ("Red", "Green"))))
        self.assertTrue(e.is_common(), "has should be common")
        self.assertTrue(e.is_bool_common(), "has should be bool")
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated HasExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.has)
        self.assertTrue(estr == "A has Schema.Type'Red,Green'")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated HasExpression")
        except NotImplementedError:
            pass

    def test_unary_operator(self):
        add = comex.UnaryExpression(comex.Operator.add)
        self.assertFalse(add.is_common())
        # we should only be able to add one arguments
        add.add_operand(comex.NullExpression())
        try:
            add.add_operand(comex.NullExpression())
            self.fail("UnaryOperator with 2 operands")
        except ValueError:
            pass
        try:
            self.ep.evaluate(add)
            self.fail("ExpressionProcessor evaluated UnaryExpression")
        except NotImplementedError:
            pass
        try:
            self.ef.evaluate(add)
            self.fail("ExpressionFormatter evaluated UnaryExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(add)
            self.fail("SearchFormatter evaluated UnaryExpression")
        except NotImplementedError:
            pass

    def test_not(self):
        e = comex.NotExpression()
        self.assertFalse(e.is_common(), "not no args is common")
        self.assertFalse(e.is_bool_common(), "not no args is bool")
        try:
            self.ef.evaluate(e)
            self.fail("not no args evaluated")
        except errors.ExpressionError:
            pass
        # try adding a non-boolean expression
        try:
            e.add_operand(comex.Int64Expression(1))
            self.fail("not 1 was allowed")
        except ValueError:
            pass
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertTrue(e.is_common(), "not A is not common")
        self.assertTrue(e.is_bool_common(), "not A is not bool common")
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated not")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.bool_not)
        self.assertTrue(estr == "not A")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated not")
        except NotImplementedError:
            pass

    def test_negate(self):
        e = comex.NegateExpression()
        self.assertFalse(e.is_common(), "- no args is common")
        self.assertFalse(e.is_bool_common(), "- no args is bool")
        try:
            self.ef.evaluate(e)
            self.fail("- no args evaluated")
        except errors.ExpressionError:
            pass
        # try adding a non-common expression
        try:
            e.add_operand(comex.RootExpression())
            self.fail("-$root was allowed")
        except ValueError:
            pass
        e.add_operand(comex.IdentifierExpression("A"))
        self.assertTrue(e.is_common(), "-A is not common")
        self.assertFalse(e.is_bool_common(), "-A is bool common")
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated -")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.negate)
        self.assertTrue(estr == "-A")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated -")
        except NotImplementedError:
            pass

    # Annotation-specific expression nodes

    def test_reference(self):
        # a special qname expression representing a label reference
        e = comex.ReferenceExpression(
            names.QualifiedName("Schema", "Expression"))
        self.assertTrue(isinstance(e, comex.QNameExpression))
        # we could references as common and boolean as we don't know
        # what they'll point to, but they can't be used within paths
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated ReferenceExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.atom, op)
        self.assertTrue(estr == "Schema.Expression")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated ReferenceExpression")
        except NotImplementedError:
            pass

    def test_type(self):

        class MockType(object):

            def __repr__(self):
                return "schema.MockType"

        type_def = MockType()
        e = comex.TypeExpression(type_def)
        self.assertTrue(isinstance(e, comex.CommonExpression))
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated TypeExpression")
        except NotImplementedError:
            pass
        try:
            # we don't support a formatting because this is handled in
            # Edm.Cast and Edm.IsOf renderings, the only place where a
            # type expression can appear (in other contexts a
            # QNameExpression is used and lookup is deferred.
            self.ef.evaluate(e)
            self.fail("ExpressionFormatter evaluated TypeExpression")
        except NotImplementedError:
            pass
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated TypeExpression")
        except NotImplementedError:
            pass

    def test_if(self):
        e = comex.IfExpression()
        self.assertTrue(isinstance(e, comex.OperatorExpression))
        self.assertTrue(e.op_code == comex.Operator.bool_test)
        # no operands...
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        # try adding a non-boolean expression for the condition
        try:
            e.add_operand(comex.Int64Expression(1))
            self.fail("if 1... was allowed")
        except ValueError:
            pass
        e.add_operand(comex.PathExpression(("A", "B")))
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        # the remaining expressions can be anything common... but the
        # type determines whether or not we are common or bool common
        try:
            e.add_operand(comex.RootExpression())
            self.fail("if A/B then $root ... was allowed")
        except ValueError:
            pass
        # with just one argument you can't evaluate it
        try:
            self.ef.evaluate(e)
            self.fail("evaluation of if A/B with no outcomes")
        except errors.ExpressionError:
            pass
        e.add_operand(comex.BooleanExpression(True))
        self.assertFalse(e.is_common())
        self.assertFalse(e.is_bool_common())
        e.add_operand(comex.BooleanExpression(False))
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        try:
            e.add_operand(comex.BooleanExpression(False))
            self.fail("3-valued logic")
        except ValueError:
            pass
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated IfExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.call, op)
        self.assertTrue(estr == "if(<Path>A/B</Path>,true,false)")
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated IfExpression")
        except NotImplementedError:
            pass
        # check non bool expressions
        e = comex.IfExpression()
        e.add_operand(comex.PathExpression(("A", "B")))
        e.add_operand(comex.BooleanExpression(True))
        e.add_operand(comex.Int64Expression(0))
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())

    def test_path(self):
        e = comex.PathExpression(("Property", ))
        self.assertTrue(isinstance(e, comex.CommonExpression))
        # no operands...
        self.assertTrue(e.is_common())
        self.assertTrue(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated PathExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.member, op)
        self.assertTrue(estr == "<Path>Property</Path>", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated PathExpression")
        except NotImplementedError:
            pass

    def test_annotation_path(self):
        e = comex.AnnotationPathExpression(
            ("Property", names.TermRef.from_str("@Schema.Term")))
        self.assertTrue(isinstance(e, comex.CommonExpression))
        # no operands...
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated AnnotationPathExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.member, op)
        self.assertTrue(
            estr == "<AnnotationPath>Property/@Schema.Term</AnnotationPath>",
            estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated AnnotationPathExpression")
        except NotImplementedError:
            pass

    def test_navigation_path(self):
        e = comex.NavigationPropertyPathExpression(("Complex", "Navigation"))
        self.assertTrue(isinstance(e, comex.CommonExpression))
        # no operands...
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated "
                      "NavigationPropertyPathExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.member, op)
        self.assertTrue(
            estr == "<NavigationPropertyPath>Complex/Navigation"
            "</NavigationPropertyPath>", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated "
                      "NavigationPropertyPathExpression")
        except NotImplementedError:
            pass

    def test_property_path(self):
        e = comex.PropertyPathExpression(("Complex", "Property"))
        self.assertTrue(isinstance(e, comex.CommonExpression))
        # no operands...
        self.assertTrue(e.is_common())
        self.assertFalse(e.is_bool_common())
        self.assertFalse(e.is_root())
        self.assertFalse(e.is_first_member())
        self.assertFalse(e.is_member())
        self.assertFalse(e.is_property_path())
        try:
            self.ep.evaluate(e)
            self.fail("ExpressionProcessor evaluated PropertyPathExpression")
        except NotImplementedError:
            pass
        op, estr = self.ef.evaluate(e)
        self.assertTrue(op == comex.Operator.member, op)
        self.assertTrue(
            estr == "<PropertyPath>Complex/Property</PropertyPath>", estr)
        try:
            self.sf.evaluate(e)
            self.fail("SearchFormatter evaluated PropertyPathExpression")
        except NotImplementedError:
            pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
