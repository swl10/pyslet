#! /usr/bin/env python


import decimal
import hashlib
import io
import logging
import unittest
import uuid

import pyslet.http.params as params
import pyslet.http.messages as messages
import pyslet.iso8601 as iso
import pyslet.odata2.core as odata
import pyslet.odata2.csdl as edm
import pyslet.odata2.metadata as edmx

from pyslet.vfs import OSFilePath as FilePath
from pyslet.py2 import (
    is_unicode,
    range3,
    to_text,
    u8,
    ul)


def suite(prefix='test'):
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(ODataTests),
        loader.loadTestsFromTestCase(CommonExpressionTests),
        loader.loadTestsFromTestCase(ParamsExpressionTests),
        loader.loadTestsFromTestCase(ODataURITests),
        loader.loadTestsFromTestCase(JSONTests),
        loader.loadTestsFromTestCase(StreamInfoTests)
    ))


class ODataTests(unittest.TestCase):

    def test_constants(self):
        pass


class CommonExpressionTests(unittest.TestCase):

    def evaluate_common(self, expr_string):
        p = odata.Parser(expr_string)
        e = p.parse_common_expression()
        return e.evaluate(None)

    def test_confusing_identifiers(self):
        p = odata.Parser("X and binary and Binary")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("X/binary as identifier: %s" % str(e))
        p = odata.Parser("datetime and DateTime")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("datetime as identifier: %s" % str(e))
        p = odata.Parser("guid and Guid")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("guid as identifier: %s" % str(e))
        p = odata.Parser("time and Time")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("time as identifier: %s" % str(e))
        p = odata.Parser("datetimeoffset and DateTimeOffset")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("datetimeoffset as identifier: %s" % str(e))
        # we don't support these types but just in case...
        p = odata.Parser("geography and Geography")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("geography as identifier: %s" % str(e))
        # we don't support these types but just in case...
        p = odata.Parser("geometry and Geometry")
        try:
            e = p.parse_common_expression()
        except ValueError as e:
            self.fail("geometry as identifier: %s" % str(e))

    def test_evaluate_common_expression(self):
        # cursory check:
        # a commonExpression must represent any and all supported common
        # expression types
        p = odata.Parser("true and false")
        e = p.parse_common_expression()
        self.assertTrue(isinstance(e, odata.CommonExpression),
                        "Expected common expression")
        value = e.evaluate(None)
        self.assertTrue(isinstance(value, edm.SimpleValue),
                        "Expected EDM value; found %s" % repr(value))
        self.assertTrue(value.value is False, "Expected false")

    def test_evaluate_boolean_expression(self):
        # cursory check:
        # a boolCommonExpression MUST be a common expression that evaluates to
        # the EDM Primitive type Edm.Boolean
        value = self.evaluate_common("true and false")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected false")

    def test_evaluate_paren_expression(self):
        """a parenExpression MUST be evaluated by evaluating the
        expression with the parentheses, starting with the innermost
        parenthesized expressions and proceeding outwards...

        ...the result of the parenExpression MUST be the result of the
        evaluation of the contained expression."""
        p = odata.Parser("(false and false or true)")
        # note that 'or' is the weakest operator
        e = p.parse_common_expression()
        value = e.evaluate(None)
        self.assertTrue(value.value is True, "Expected True")
        p = odata.Parser("(false and (false or true))")
        # should change the result
        e = p.parse_common_expression()
        value = e.evaluate(None)
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "(((((((false) and (((false)) or true)))))))")
        self.assertTrue(value.value is False, "Expected False - multibrackets")

    def test_evaluate_boolean_paren_expression(self):
        """Cursory check: a boolParenExpression MUST be evaluated by
        evaluating the expression with the parentheses. The result of
        the boolParenExpression MUST ... be of the EDM Primitive type
        Edm.Boolean"""
        value = self.evaluate_common("(false and (false or true))")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected false")

    def test_evaluate_add_expression(self):
        """...operand expressions MUST evaluate to a value of one of the
        following EDM Primitive types:
                Edm.Decimal
                Edm.Double
                Edm.Single
                Edm.Int32
                Edm.Int64

        The addExpression SHOULD NOT be supported for any other EDM
        Primitive types.

        ..data service SHOULD follow the binary numeric promotion
        rules... The EDM Primitive type of the result of evaluating the
        addExpression MUST be the same type as the operands after binary
        numeric promotion.

        data service can support evaluating operands with null values
        following the rules defined in Lifted operators"""
        value = self.evaluate_common("2M add 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == 4, "Expected 4")
        value = self.evaluate_common("2D add 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 4.0, "Expected 4")
        value = self.evaluate_common("2F add 2D")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 4.0, "Expected 4")
        value = self.evaluate_common("2 add 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 4, "Expected 4")
        try:
            value = self.evaluate_common("2 add '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("2 add null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_sub_expression(self):
        """See test_evaluate_add_expression"""
        value = self.evaluate_common("4M sub 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == 2, "Expected 2.0")
        value = self.evaluate_common("4D sub 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        value = self.evaluate_common("4F sub 2D")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        value = self.evaluate_common("4 sub 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 2, "Expected 2L")
        try:
            value = self.evaluate_common("4 sub '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("4 sub null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_mul_expression(self):
        """See test_evaluate_add_expression"""
        value = self.evaluate_common("4M mul 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == 8, "Expected 8.0")
        value = self.evaluate_common("4D mul 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 8.0, "Expected 8.0")
        value = self.evaluate_common("4F mul 2D")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 8.0, "Expected 8.0")
        value = self.evaluate_common("4 mul 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 8, "Expected 8L")
        try:
            value = self.evaluate_common("4 mul '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("4 mul null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_div_expression(self):
        """See test_evaluate_add_expression

        OData is ambiguous in the way it defines division as it makes
        reference only to the IEEE floating point operations.  For
        compatibility with SQL though we assume that integer division
        simple truncates fractional parts."""
        value = self.evaluate_common("4M div 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == 2, "Expected 2")
        value = self.evaluate_common("4D div 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        try:
            value = self.evaluate_common("4D div 0")
            self.fail("Division by zero")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("4F div 2D")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        value = self.evaluate_common("5 div 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 2, "Expected 2L")
        value = self.evaluate_common("-5 div 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == -2, "Expected -2L")
        try:
            value = self.evaluate_common("4 div '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("4 div null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_mod_expression(self):
        """See test_evaluate_add_expression

        The data service SHOULD evaluate the operation represented by
        the modExpression, according to the rules of [IEEE754-2008]

        For integer division we just truncate fractional parts towards zero."""
        value = self.evaluate_common("5.5M mod 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == decimal.Decimal('1.5'),
                        "Expected 1.5; found %s" % repr(value.value))
        value = self.evaluate_common("5.5D mod 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 1.5, "Expected 1.5")
        try:
            value = self.evaluate_common("5.5D mod 0")
            self.fail("Division by zero")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("5.5F mod 2D")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 1.5, "Expected 1.5")
        value = self.evaluate_common("5 mod 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 1, "Expected 1L")
        value = self.evaluate_common("-5 mod 2L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == -1, "Expected -1L")
        try:
            value = self.evaluate_common("5 mod '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("5 mod null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_negate_expression(self):
        """See test_evaluate_add_expression for list of simple types.

        ..data service SHOULD follow the unary numeric promotion rules
        ... to implicitly convert the operand to a supported EDM
        Primitive type

        the result of evaluating the negateExpression SHOULD always be
        equal to the result of evaluating the subExpression where one
        operand is the value zero and the other is the value of the
        operand.  [comment applies to null processing too]"""
        value = self.evaluate_common("-(2M)")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == -2, "Expected -2.0")
        value = self.evaluate_common("-(2D)")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == -2.0, "Expected -2.0")
        p = odata.Parser("-(-2F)")
        # unary numeric promotion to Double - a bit weird
        e = p.parse_common_expression()
        value = e.evaluate(None)
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        value = self.evaluate_common("-(2L)")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == -2, "Expected -2L")
        try:
            value = self.evaluate_common("-'2'")
            self.fail("String promotion to numeric")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("-null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_and_expression(self):
        """...operand expressions MUST evaluate to the EDM Primitive
        types of Edm.Boolean. The andExpression SHOULD NOT be supported
        for operands of any other EDM Primitive types.

        The EDM Primitive type of the result of evaluating the
        andExpression MUST be Edm.Boolean.

        ...service MUST evaluate the expression to the value of true if
        the values of the operands are both true after being evaluated.
        If either operand is false after being evaluated, the expression
        MUST evaluate to the value of false.

        The data service can support evaluating operands with null
        values following the rules defined in Binary Numeric
        Promotions.... [for Boolean expressions evaluated to the value
        of null, a data service MUST return the value of false]"""
        value = self.evaluate_common("false and false")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        try:
            value = self.evaluate_common("false and 0")
            self.fail("Integer promotion to Boolean")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("false and true")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("true and false")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("true and true")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("true and null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("false and null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("false and false")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_or_expression(self):
        """See test_evaluate_and_expression for more details.

        ...data service MUST evaluate the expression to the value of
        true if at least one of the operands is true after being
        evaluated. If both operands are false after being evaluated, the
        expression MUST evaluate to the value of false"""
        value = self.evaluate_common("false or false")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        try:
            value = self.evaluate_common("false or 0")
            self.fail("Integer promotion to Boolean")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("false or true")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("true or false")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("true or true")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("true or null")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("false or null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("null or null")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_eq_expression(self):
        """...operand expressions MUST evaluate to a value of a known
        EntityType or one of the following EDM Primitive types:
                Edm.Decimal
                Edm.Double
                Edm.Single
                Edm.Int32
                Edm.Int64
                Edm.String
                Edm.DateTime
                Edm.Guid
                Edm.Binary

        (For tests on EntityType instances see the same method in the
        sample data set later)

        The eqExpression SHOULD NOT be supported for any other EDM
        Primitive types.

        [Given that the previous statement is not a requirement it is
        acceptable to extend these relations to include
        Edm.DateTimeOffset as per the OData v3 specification.]

        ...a data service SHOULD follow the binary numeric promotion
        rules defined in Unary [sic] Numeric Promotions...

        ...The EDM Primitive type of the result of evaluating the
        eqExpression MUST be Edm.Boolean.

        ...a data service MUST return a value of true if the values of
        the operands are equal and false if they are not equal. If the
        type of the operands is a known EntityType, then a value of true
        MUST be returned if the operand expressions, once evaluated,
        represent the same e instance.

        ...for equality operators, a data service MUST consider two null
        values equal and a null value unequal to any non-null value."""
        value = self.evaluate_common("2M eq 3M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("2D eq 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2F eq 2D")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2 eq 2L")
        self.assertTrue(value.value is True, "Expected True")
        try:
            value = self.evaluate_common("2 eq '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("'2' eq '2'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49:01'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' eq "
            "datetimeoffset'2013-08-30T19:49:00+01:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' eq "
            "datetimeoffset'2013-08-30T18:49:00+01:00'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq "
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq "
            "guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("X'DEADBEEF' eq binary'deadbeef'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("X'DEAD' eq binary'BEEF'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("2 eq null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("null eq null")
        self.assertTrue(value.value is True, "Expected True")

    def test_evaluate_ne_expression(self):
        """See test_evaluate_eq_expression for details."""
        value = self.evaluate_common("2M ne 3M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2D ne 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("2F ne 2D")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("2 ne 2L")
        self.assertTrue(value.value is False, "Expected False")
        try:
            value = self.evaluate_common("2 ne '2'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("'2' ne '2'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49:01'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' ne "
            "datetimeoffset'2013-08-30T19:49:00+01:00'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' ne "
            "datetimeoffset'2013-08-30T18:49:00+01:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne "
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne "
            "guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("X'DEADBEEF' ne binary'deadbeef'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("X'DEAD' ne binary'BEEF'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2 ne null")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("null ne null")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_lt_expression(self):
        """...operand expressions MUST evaluate to a value of one of the
        following EDM Primitive types:
                Edm.Decimal
                Edm.Double
                Edm.Single
                Edm.Int32
                Edm.Int64
                Edm.String
                Edm.DateTime
                Edm.Guid

        ...data service SHOULD follow the binary numeric promotion

        ...The EDM Primitive type of the result of evaluating the
        ltExpression MUST be Edm.Boolean.

        ...a data service MUST return a value of true if the value of
        the first operand is less than the value of the second operand,
        false if not.

        ...for relational operators, a data service MUST return the
        value false if one or both of the operands is null."""
        value = self.evaluate_common("2M lt 3M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2D lt 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("2.1F lt 2D")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("2 lt 3L")
        self.assertTrue(value.value is True, "Expected True")
        try:
            value = self.evaluate_common("2 lt '3'")
            self.fail("String promotion to int")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("'20' lt '3'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49:01'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' lt "
            "datetimeoffset'2013-08-30T19:50:00+01:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' lt "
            "datetimeoffset'2013-08-30T18:49:00+01:00'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt "
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt "
            "guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
        self.assertTrue(value.value is False, "Expected False")
        try:
            p = odata.Parser("X'DEADBEEF' lt binary'deadbeef'")
            e = p.parse_common_expression()
            value = e.evaluate(None)
            self.fail("Relational operation on binary data")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("2 lt null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("null lt null")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_le_expression(self):
        """See test_evaluate_lt_expression for more information -
        abbreviated tests"""
        value = self.evaluate_common("2D le 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' le datetime'2013-08-30T18:49:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' le "
            "datetimeoffset'2013-08-30T19:49:00+01:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2 le null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("null le null")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_gt_expression(self):
        """See test_evaluate_lt_expression for more information -
        abbreviated tests"""
        value = self.evaluate_common("2D gt 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' gt datetime'2013-08-30T18:49:00'")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' gt "
            "datetimeoffset'2013-08-30T18:49:00+01:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2 gt null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("null gt null")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_ge_expression(self):
        """See test_evaluate_lt_expression for more information -
        abbreviated tests"""
        value = self.evaluate_common("2D ge 2M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetime'2013-08-30T18:49' ge datetime'2013-08-30T18:49:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common(
            "datetimeoffset'2013-08-30T18:49:00Z' ge "
            "datetimeoffset'2013-08-30T19:49:00+01:00'")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("2 ge null")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("null ge null")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_not_expression(self):
        """...operation is supported ... as long as the operand
        expression evaluates to a value of the EDM Primitive type
        Edm.Boolean. The data service SHOULD NOT support operand
        expressions of any other EDM Primitive type

        The EDM Primitive type of the result of evaluating the
        notExpression MUST be Edm.Boolean.

        the data service MUST evaluate the logical negation operation by
        returning false if the operand value is true and returning true
        if the operand value is false.

        ...for unary operators, a data service MUST return the value
        null if the operand value is null."""
        value = self.evaluate_common("not false")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("not true")
        self.assertTrue(value.value is False, "Expected False")
        try:
            value = self.evaluate_common("not 1")
            self.fail("Integer promotion to Boolean")
        except odata.EvaluationError:
            pass
        value = self.evaluate_common("not null")
        self.assertTrue(value.value is None, "Expected NULL")
        value = self.evaluate_common("(not true)")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("(not false) and true")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("(not false) and false")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_is_of_expression(self):
        """...the data service MAY<24> support some or all of the common
        expressions as the first operand value... the data service can
        support the first operand as being optional... interpreted to
        apply to the e instance specified by the navigation portion
        of the request URI.

        The second operand MUST be a stringLiteral that represents the
        name of a known e or EDM Primitive type.

        The EDM Primitive type of the result of evaluating the
        isofExpression MUST be Edm.Boolean.

        ...the data service MUST evaluate the isofExpression to return a
        value of true if the targeted instance can be converted to the
        specified type. If the conversion is not allowed, then the
        expression MUST be evaluated to false.

        data service can support evaluating an operand with a null value
        following the rules defined in Binary Numeric Promotions. [It
        isn't clear what this means at all, clearly there is a typo.  We
        add our own rule... isof(NULL,'type') always returns False, in
        keeping with other boolean operators]

        It is also not clear which 'explicit conversions' are allowed in
        the Edm model and which aren't.  The approach taken is to allow
        only the numeric promotions supported for binary operations,
        which is a bit tight but perhaps safer than allowing forms which
        may not be portable."""
        value = self.evaluate_common("isof(2D,'Edm.Double')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("isof(2M,'Edm.Double')")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("isof(2,'Edm.Double')")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("isof(2.0D,'Edm.Single')")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("isof('x','Edm.String')")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("isof(X'DEAD','Edm.String')")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("isof(false or true,'Edm.Boolean')")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("isof(null,'Edm.String')")
        self.assertTrue(value.value is False, "Expected False")
        value = self.evaluate_common("isof('Edm.String')")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_cast_expression(self):
        """...see test_evaluate_is_of_expression for more information.

        The type of the result of evaluating the castExpression MUST be
        the same type as represented by the string literal value from
        the second operand.

        A data service MAY support any cast operations where there
        exists an explicit conversion from the targeted instance (first
        operand) to the type represented by second operand. In all other
        cases, the data service SHOULD NOT support the specified cast
        operation.

        The data service MAY support evaluating an operand with a null
        value following the rules defined in Lifted Operators. [again,
        not 100% clear what these are.]"""
        value = self.evaluate_common("cast(2D,'Edm.Double')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        value = self.evaluate_common("cast(2L,'Edm.Single')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Single, "Expected Single")
        self.assertTrue(value.value == 2.0, "Expected 2.0")
        value = self.evaluate_common("cast(2,'Edm.Int64')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 2, "Expected 2")
        try:
            value = self.evaluate_common("cast(2.0D,'Edm.Single')")
            self.fail("Double cast to Single")
        except:
            pass
        value = self.evaluate_common("cast('x','Edm.String')")
        self.assertTrue(value.value == 'x', "Expected 'x'")
        try:
            value = self.evaluate_common("cast(X'DEAD','Edm.String')")
            self.fail("Binary cast to String")
        except:
            pass
        try:
            value = self.evaluate_common("cast(1,'Edm.Boolean')")
            self.fail("1 cast to Boolean")
        except:
            pass
        value = self.evaluate_common("cast(null,'Edm.String')")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value is None, "Expected None")
        value = self.evaluate_common("cast('Edm.Int16')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int16, "Expected Int16")
        self.assertTrue(value.value is None, "Expected None")

    def test_evaluate_boolean_cast_expression(self):
        # cursory check:
        value = self.evaluate_common("cast(true,'Edm.Boolean')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")

    def test_evaluate_boolean_literal_expression(self):
        """the type of the boolLiteralExpression MUST always be the EDM
        primitive type Edm.Boolean."""
        value = self.evaluate_common("true")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True, "Expected True")
        value = self.evaluate_common("false")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is False, "Expected False")

    def test_evaluate_literal_expression(self):
        """the type of the literalExpression MUST be the EDM Primitive
        type for the lexical representation of the literal:

                null
                Edm.Binary
                Edm.Boolean
                Edm.Byte
                Edm.DateTime
                Edm.Decimal
                Edm.Double
                Edm.Single
                Edm.Guid
                Edm.Int16
                Edm.Int32
                Edm.Int64
                Edm.SByte,
                Edm.String,
                Edm.Time,
                Edm.DateTimeOffset"""
        value = self.evaluate_common("null")
        self.assertTrue(value.type_code is None, "Expected None")
        self.assertTrue(value.value is None, "Expected None")
        value = self.evaluate_common("X'DEAD'")
        self.assertTrue(
            value.type_code == edm.SimpleType.Binary, "Expected Binary")
        self.assertTrue(value.value == b'\xde\xad')
        value = self.evaluate_common("true")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Booelan")
        self.assertTrue(value.value is True)
        value = self.evaluate_common("123")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value == 123)
        value = self.evaluate_common("datetime'2013-08-31T15:28'")
        self.assertTrue(
            value.type_code == edm.SimpleType.DateTime, "Expected DateTime")
        self.assertTrue(value.value.date.year == 13)
        value = self.evaluate_common("123.5M")
        self.assertTrue(
            value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
        self.assertTrue(value.value == decimal.Decimal('123.5'))
        value = self.evaluate_common("123.5D")
        self.assertTrue(
            value.type_code == edm.SimpleType.Double, "Expected Double")
        self.assertTrue(value.value == 123.5)
        value = self.evaluate_common("123.5F")
        self.assertTrue(
            value.type_code == edm.SimpleType.Single, "Expected Single")
        self.assertTrue(value.value == 123.5)
        value = self.evaluate_common(
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
        self.assertTrue(value.type_code == edm.SimpleType.Guid,
                        "Expected Guid")
        self.assertTrue(
            value.value == uuid.UUID('b3afeebc-9658-4699-9d9c-1df551fd6814'))
        value = self.evaluate_common("123456")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value == 123456)
        value = self.evaluate_common("123456L")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int64, "Expected Int64")
        self.assertTrue(value.value == 123456)
        value = self.evaluate_common("-123")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value == -123)
        value = self.evaluate_common("'123'")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == '123')
        value = self.evaluate_common("time'15:28'")
        self.assertTrue(value.type_code == edm.SimpleType.Time,
                        "Expected Time")
        self.assertTrue(value.value.hour == 15)
        self.assertTrue(value.value.minute == 28)
        self.assertTrue(value.value.second == 0)
        value = self.evaluate_common(
            "datetimeoffset'2002-10-10T12:00:00-05:00'")
        self.assertTrue(
            value.type_code == edm.SimpleType.DateTimeOffset,
            "Expected DateTimeOffset")
        self.assertTrue(value.value ==
                        iso.TimePoint.from_str('2002-10-10T12:00:00-05:00'))

    def test_evaluate_method_call_expression(self):
        """Cursory check only."""
        value = self.evaluate_common("length('x')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value == 1)

    def test_evaluate_boolean_method_call_express(self):
        """Cursory check only."""
        value = self.evaluate_common("startswith('xyz','x')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True)

    def test_evaluate_ends_with_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The endsWithMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        ...the result of evaluating the endsWithMethodCallExpression
        SHOULD be a value of the EDM Primitive type Edm.Boolean.

        ...the data service SHOULD evaluate ... by returning a Boolean
        value indicating whether the end of the first parameter
        values matches the second parameter value."""
        value = self.evaluate_common("endswith('startswith','with')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True)
        value = self.evaluate_common("endswith('startswith','start')")
        self.assertTrue(value.value is False)
        value = self.evaluate_common("endswith('startswith','WITH')")
        # not case insensitive
        self.assertTrue(value.value is False)
        try:
            value = self.evaluate_common("endswith('3.14',4)")
            self.fail("integer as suffix")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("endswith('3.14')")
            self.fail("1 parameter")
        except odata.EvaluationError:
            pass

    def test_evaluate_index_of_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The indexOfMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        ...the EDM Primitive type of the result of evaluating the
        indexOfMethodCallExpression SHOULD be a value of the EDM
        Primitive type Edm.Int32.

        the data service SHOULD evaluate ... by returning an integer
        value indicating the index of the first occurrence of the second
        parameter value in the first parameter value. If no index is
        found, a value of -1 SHOULD be returned."""
        value = self.evaluate_common("indexof('startswith','tart')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value == 1)
        value = self.evaluate_common("indexof('startswith','start')")
        self.assertTrue(value.value == 0)
        value = self.evaluate_common("indexof('startswith','t')")
        self.assertTrue(value.value == 1)
        # not case insensitive
        value = self.evaluate_common("indexof('startswith','W')")
        self.assertTrue(value.value == -1)
        try:
            value = self.evaluate_common("indexof('3.14',1)")
            self.fail("integer as parameter")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("indexof('3.14')")
            self.fail("1 parameter")
        except odata.EvaluationError:
            pass

    def test_evaluate_replace_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The replaceMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        replaceMethodCallExpression SHOULD be a value of the EDM
        Primitive type Edm.String.

        the data service SHOULD evaluate ... by returning a string value
        with all occurrences of the second parameter value replaced by
        the third parameter value in the first parameter value."""
        value = self.evaluate_common("replace('startswith','tart','cake')")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == "scakeswith")
        value = self.evaluate_common("replace('startswith','t','x')")
        self.assertTrue(value.value == "sxarxswixh")
        # not case insensitive
        value = self.evaluate_common("replace('sTartswith','t','x')")
        self.assertTrue(value.value == "sTarxswixh")
        value = self.evaluate_common("replace('startswith','t','tx')")
        self.assertTrue(value.value == "stxartxswitxh")
        try:
            value = self.evaluate_common("replace('3.14','1',2)")
            self.fail("integer as parameter")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("replace('3.14','1')")
            self.fail("2 parameter")
        except odata.EvaluationError:
            pass

    def test_evaluate_starts_with_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The startsWithMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        ...the result of evaluating the startsWithMethodCallExpression
        SHOULD be a value of the EDM Primitive type Edm.Boolean.

        ...the data service SHOULD evaluate ... by returning a Boolean
        value indicating whether the beginning of the first parameter
        values matches the second parameter value."""
        value = self.evaluate_common("startswith('startswith','start')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True)
        value = self.evaluate_common("startswith('startswith','end')")
        self.assertTrue(value.value is False)
        value = self.evaluate_common("startswith('startswith','Start')")
        # not case insensitive
        self.assertTrue(value.value is False)
        try:
            value = self.evaluate_common("startswith('3.14',3)")
            self.fail("integer as prefix")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("startswith('3.14')")
            self.fail("1 parameter")
        except odata.EvaluationError:
            pass

    def test_evaluate_to_lower_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The toLowerMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        ...the EDM Primitive type of the result ... SHOULD be a value of
        the EDM Primitive type Edm.String.

        ...the data service SHOULD evaluate ... by returning a string
        value with the contents of the parameter value converted to
        lower case."""
        value = self.evaluate_common("tolower('Steve')")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == "steve")
        value = self.evaluate_common(ul("tolower('CAF\xc9')"))
        self.assertTrue(value.value == ul('caf\xe9'))
        value = self.evaluate_common(ul("tolower('caf\xe9')"))
        self.assertTrue(value.value == ul('caf\xe9'))
        try:
            value = self.evaluate_common("tolower(3.14F)")
            self.fail("floating lower")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("tolower('Steve','John')")
            self.fail("2 parameters")
        except odata.EvaluationError:
            pass

    def test_evaluate_to_upper_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The toUpperMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        ...the EDM Primitive type of the result ... SHOULD be a value of
        the EDM Primitive type Edm.String.

        ...the data service SHOULD evaluate ... by returning a string
        value with the contents of the parameter value converted to
        upper case."""
        value = self.evaluate_common("toupper('Steve')")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == ul("STEVE"))
        value = self.evaluate_common(ul("toupper('CAF\xc9')"))
        self.assertTrue(value.value == ul('CAF\xc9'))
        value = self.evaluate_common(ul("toupper('caf\xe9')"))
        self.assertTrue(value.value == ul('CAF\xc9'))
        try:
            value = self.evaluate_common("toupper(3.14F)")
            self.fail("floating upper")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("toupper('Steve','John')")
            self.fail("2 parameters")
        except odata.EvaluationError:
            pass

    def test_evaluate_trim_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The trimMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        trimMethodCallExpression SHOULD be a value of the EDM Primitive
        type Edm.String.

        the data service SHOULD evaluate ... by returning a string value
        with the contents of the parameter value with all leading and
        trailing white-space characters removed."""
        value = self.evaluate_common("trim('  Steve\t\n\r \r\n')")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == ul("Steve"))
        value = self.evaluate_common(ul("trim(' C  a  f \xe9 ')"))
        self.assertTrue(value.value == ul('C  a  f \xe9'))
        try:
            value = self.evaluate_common("trim(3.14F)")
            self.fail("floating trim")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("trim('Steve','John')")
            self.fail("2 parameters")
        except odata.EvaluationError:
            pass

    def test_evaluate_substring_expression(self):
        """The first parameter expression MUST evaluate to a value of
        the EDM Primitive type Edm.String. The second and third
        parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.Int32.

        The substringMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        substringMethodCallExpression SHOULD be a value of the EDM
        Primitive type Edm.String.

        the data service SHOULD evaluate ... by returning the string
        value starting at the character index specified by the second
        parameter value in the first parameter string value. If the
        optional third parameter is specified, the resulting string
        SHOULD be the length (in characters) of the third parameter
        value. Otherwise, the entire string from the specified starting
        index is returned."""
        value = self.evaluate_common("substring('startswith',1,4)")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == "tart")
        value = self.evaluate_common("substring('startswith',1)")
        self.assertTrue(value.value == "tartswith")
        try:
            value = self.evaluate_common("substring('startswith',1.0D,4)")
            self.fail("double as parameter")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("substring('3.14')")
            self.fail("1 parameter")
        except odata.EvaluationError:
            pass

    def test_evaluate_substring_of_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The substringOfMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        substringOfMethodCallExpression SHOULD be a value of the EDM
        Primitive type Edm.Boolean.

        ...the data service SHOULD evaluate ... by returning a Boolean
        value indicating whether the second parameter string value
        occurs in the first parameter string value.

        The definition of this function is a mess and in OData 4 it has
        been retired because of the confusion.  See:
        https://tools.oasis-open.org/issues/browse/ODATA-401"""
        value = self.evaluate_common("substringof('tart','startswith')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected Boolean")
        self.assertTrue(value.value is True)
        value = self.evaluate_common("substringof('start','startswith')")
        self.assertTrue(value.value is True)
        value = self.evaluate_common("substringof('t','startswith')")
        self.assertTrue(value.value is True)
        # not case insensitive
        value = self.evaluate_common("substringof('W','startswith')")
        self.assertTrue(value.value is False)
        try:
            value = self.evaluate_common("substringof(1,'3.14')")
            self.fail("integer as parameter")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("substringof('3.14')")
            self.fail("1 parameter")
        except odata.EvaluationError:
            pass

    def test_evaluate_concat_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The concatMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        concatMethodCallExpression SHOULD be a value of the EDM
        Primitive type Edm.String.

        the data service SHOULD evaluate ... by returning a string value
        which is the first and second parameter values merged together
        with the first parameter value coming first in the result."""
        value = self.evaluate_common("concat('starts','with')")
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected String")
        self.assertTrue(value.value == "startswith")
        value = self.evaluate_common("concat('3.1',concat('4','159'))")
        self.assertTrue(value.value == "3.14159")
        try:
            value = self.evaluate_common("concat('3.14',1)")
            self.fail("integer as parameter")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("concat('3.14')")
            self.fail("1 parameter")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("concat('3.1','4','159')")
            self.fail("3 parameters")
        except odata.EvaluationError:
            pass

    def test_evaluate_length_expression(self):
        """The parameter expressions MUST evaluate to a value of the EDM
        Primitive type Edm.String.

        The lengthMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        lengthMethodCallExpression SHOULD be a value of the EDM
        Primitive type Edm.Int32.

        the data service SHOULD evaluate ... by returning the number of
        characters in the specified parameter value."""
        value = self.evaluate_common("length('Steve')")
        self.assertTrue(
            value.type_code == edm.SimpleType.Int32, "Expected Int32")
        self.assertTrue(value.value == 5)
        value = self.evaluate_common(ul("length('CAF\xc9')"))
        self.assertTrue(value.value == 4)
        value = self.evaluate_common(ul("length('')"))
        self.assertTrue(value.value == 0)
        try:
            value = self.evaluate_common("length(3.14F)")
            self.fail("floating length")
        except odata.EvaluationError:
            pass
        try:
            value = self.evaluate_common("length('Steve','John')")
            self.fail("2 parameters")
        except odata.EvaluationError:
            pass

    def test_evaluate_year_expression(self):
        """The parameter expression MUST evaluate to a value of the EDM
        Primitive type Edm.DateTime.

        The yearMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        the EDM Primitive type of the result of evaluating the
        yearMethodCallExpression SHOULD be the EDM Primitive type
        Edm.Int32.

        the data service SHOULD evaluate ... by returning the year
        component value of the parameter value.

        We implement very similar tests for month, day, hour, minute and
        second"""
        for f, r in (
                ("year", 2013),
                ("month", 9),
                ("day", 1),
                ("hour", 10),
                ("minute", 56),
                ("second", 0)):
            value = self.evaluate_common("%s(datetime'2013-09-01T10:56')" % f)
            self.assertTrue(
                value.type_code == edm.SimpleType.Int32, "Expected Int32")
            self.assertTrue(value.value == r)
            try:
                value = self.evaluate_common(
                    "%s(datetimeoffset'2013-09-01T10:56:12-05:00')" % f)
                self.fail("datetimeoffset %s" % f)
            except odata.EvaluationError:
                pass
            try:
                value = self.evaluate_common(
                    "%s(datetime'2013-09-01T10:56',"
                    "datetime'2013-09-01T10:57')" % f)
                self.fail("2 parameters")
            except odata.EvaluationError:
                pass

    def test_evaluate_round_expression(self):
        """The parameter expression MUST evaluate to a value of one of
        the following EDM Primitive types:
                Edm.Decimal
                Edm.Double

        The roundMethodCallExpression SHOULD NOT be supported for
        parameters of any other EDM Primitive types.

        data service SHOULD follow the numeric promotion rules for
        method call parameters defined in Binary numeric promotions to
        implicitly convert the parameters to a supported EDM Primitive
        type.

        The EDM Primitive type of the result of evaluating the
        roundMethodCallExpression MUST be the same type as the parameter.

        the data service SHOULD evaluate ... by returning the nearest
        integral value to the parameter value, following the rules
        defined in [IEEE754-2008] for the rounding operation.

        We cover floor and ceil using similar routines..."""
        for f, r in (
                ("round", (2, 2, -2, 2, 3, -3, 2, 3)),
                ("floor", (1, 2, -3, 1, 2, -3, 2, 3)),
                ("ceiling", (2, 3, -2, 2, 3, -2, 3, 3))):
            value = self.evaluate_common("%s(1.5D)" % f)
            self.assertTrue(
                value.type_code == edm.SimpleType.Double, "Expected Double")
            self.assertTrue(value.value == r[0])
            # check rounding to even for binary floating point
            value = self.evaluate_common("%s(2.5D)" % f)
            self.assertTrue(value.value == r[1])
            value = self.evaluate_common("%s(-2.5D)" % f)
            self.assertTrue(value.value == r[2])
            value = self.evaluate_common("%s(1.5M)" % f)
            self.assertTrue(
                value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
            self.assertTrue(value.value == r[3])
            # check rounding away from zero for decimals
            value = self.evaluate_common("%s(2.5M)" % f)
            self.assertTrue(value.value == r[4])
            value = self.evaluate_common("%s(-2.5M)" % f)
            self.assertTrue(value.value == r[5])
            # single promotes to double
            value = self.evaluate_common("%s(2.5F)" % f)
            self.assertTrue(
                value.type_code == edm.SimpleType.Double, "Expected Double")
            self.assertTrue(value.value == r[6])
            # integers promote to decimal - seems a bit strange but there you
            # go
            value = self.evaluate_common("%s(3)" % f)
            self.assertTrue(
                value.type_code == edm.SimpleType.Decimal, "Expected Decimal")
            self.assertTrue(value.value == r[7])
            try:
                value = self.evaluate_common("%s('3')" % f)
                self.fail("round string parameter")
            except odata.EvaluationError:
                pass
            try:
                value = self.evaluate_common("%s(3.1D,3.2D)" % f)
                self.fail("two parameters")
            except odata.EvaluationError:
                pass

    def test_operator_precedence(self):
        value = self.evaluate_common("--2 mul 3 div 1 mul 2 mod 2 add 2 div "
                                     "2 sub 1 eq 2 and false or true")
        self.assertTrue(value.value is True)

    def test_string_conversion_expression(self):
        for example in [
            ul("true and false"),
            ul("(((((((false) and (((false)) or true)))))))"),
            "(false and (false or true))",
            "2M add 2M",
            "2D add 2M",
            "2F add 2D",
            "2 add 2L",
            "2 add null",
            "4D sub 2M",
            "4 sub null",
            "4F mul 2D",
            "-5 div 2L",
            "5.5M mod 2M",
            "-(2M)",
            "-(-2F)",
            "-null",
            "2F eq 2D",
            "datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'",
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq "
                "guid'b3afeebc-9658-4699-9d9c-1df551fd6814'",
            "X'DEADBEEF' eq binary'deadbeef'",
            "2 eq null",
            "X'DEAD' ne binary'BEEF'",
            "2.1F lt 2D",
            "'20' lt '3'",
            "2D gt 2M",
            "datetime'2013-08-30T18:49' ge datetime'2013-08-30T18:49:00'",
            "not false",
            "not false and not true",
            "isof(2.0D,'Edm.Single')",
            "cast(2L,'Edm.Single')",
            "true",
            "guid'b3afeebc-9658-4699-9d9c-1df551fd6814'",
            "123456L",
            "time'10:56'",
            "length('x')",
            "startswith('xyz','x')",
            "endswith('startswith','with')",
            "indexof('startswith','tart')",
            "replace('startswith','tart','cake')",
            "tolower('Steve')",
            "toupper('Steve')",
            "trim('  Steve\t\n\r \r\n')",
            "substring('startswith',1,4)",
            "substringof('startswith','tart')",
            "concat('starts','with')",
            "length('Steve')",
            "year(datetime'2013-09-01T10:56')",
            "month(datetime'2013-09-01T10:56')",
            "day(datetime'2013-09-01T10:56')",
            "hour(datetime'2013-09-01T10:56')",
            "minute(datetime'2013-09-01T10:56')",
            "second(datetime'2013-09-01T10:56')",
            "round(1.5D)",
            "floor(1.5D)",
            "ceiling(1.5D)",
            "--2 mul 3 div 1 mul 2 mod 2 add 2 div 2 sub 1 eq 2 and "
                "false or true", ]:
            e1 = odata.CommonExpression.from_str(example)
            e2 = odata.CommonExpression.from_str(to_text(e1))
            self.assertTrue(e1.evaluate(None) == e2.evaluate(
                None), "Mismatch evaluating: %s" % example)
            self.assertTrue(to_text(e1) == to_text(e2),
                            "Unstable expression: %s, %s!=%s" %
                            (example, to_text(e1), to_text(e2)))


class ParamsExpressionTests(unittest.TestCase):

    def evaluate_common(self, expr_string):
        p = odata.Parser(expr_string)
        e = p.parse_common_expression()
        return e.evaluate(None)

    def test_noparams_expression(self):
        p = odata.Parser("true and false")
        params = {}
        e = p.parse_common_expression(params)
        self.assertTrue(isinstance(e, odata.CommonExpression),
                        "Expected common expression")
        value = e.evaluate(None)
        self.assertTrue(value.value is False, "Expected false")

    def test_params_expression(self):
        p = odata.Parser("true and :bool")
        params = {}
        try:
            e = p.parse_common_expression(params)
            self.fail("Undeclared parameter")
        except ValueError:
            # undeclared parameter
            pass
        params = {'bool': edm.EDMValue.from_type(edm.SimpleType.Boolean)}
        p.setpos(0)
        e = p.parse_common_expression(params)
        self.assertTrue(isinstance(e, odata.CommonExpression),
                        "Expected common expression: %s" % repr(e))
        # true and null = false
        value = e.evaluate(None)
        self.assertTrue(value.value is False, "Expected false")
        # true and false = false
        params['bool'].set_from_value(False)
        value = e.evaluate(None)
        self.assertTrue(value.value is False, "Expected false")
        # true and true = true
        params['bool'].set_from_value(True)
        value = e.evaluate(None)
        self.assertTrue(value.value is True, "Expected true")


class ODataURITests(unittest.TestCase):

    def test_construnctor(self):
        ds_uri = odata.ODataURI('/')
        self.assertTrue(ds_uri.path_prefix == '', "empty path prefix")
        self.assertTrue(ds_uri.resource_path == '/', "resource path")
        self.assertTrue(ds_uri.query_options == [], 'query options')
        self.assertTrue(ds_uri.nav_path == [], "nav_path: %s" %
                        repr(ds_uri.nav_path))
        ds_uri = odata.ODataURI('/', '/x')
        self.assertTrue(ds_uri.path_prefix == '/x', "non-empty path prefix")
        self.assertTrue(ds_uri.resource_path is None, "resource path")
        ds_uri = odata.ODataURI('/x', '/x')
        self.assertTrue(ds_uri.path_prefix == '/x', "non-empty path prefix")
        self.assertTrue(
            ds_uri.resource_path == '', "empty resource path, special case")
        self.assertTrue(ds_uri.nav_path == [],
                        "empty nav_path, special case: %s" %
                        repr(ds_uri.nav_path))
        ds_uri = odata.ODataURI('/x.svc/Products', '/x.svc')
        self.assertTrue(ds_uri.path_prefix == '/x.svc', "svc path prefix")
        self.assertTrue(ds_uri.resource_path == '/Products', "resource path")
        self.assertTrue(len(ds_uri.nav_path) == 1, "nav_path: %s" %
                        repr(ds_uri.nav_path))
        self.assertTrue(is_unicode(ds_uri.nav_path[0][0]), "e set name type")
        self.assertTrue(
            ds_uri.nav_path[0][0] == 'Products', "e set name: Products")
        self.assertTrue(
            ds_uri.nav_path[0][1] is None, "e set no key-predicate")
        ds_uri = odata.ODataURI('Products', '/x.svc')
        self.assertTrue(ds_uri.path_prefix == '/x.svc', "svc path prefix")
        self.assertTrue(ds_uri.resource_path == '/Products', "resource path")
        try:
            ds_uri = odata.ODataURI('Products', 'x.svc')
            self.fail("x.svc/Products  - illegal path")
        except ValueError:
            pass

    def test_compound_key(self):
        ds_uri = odata.ODataURI(
            "/CompoundKeys(K3%3Ddatetime'2013-12-25T15%3A59%3A03.142'%2C"
            "K2%3D'00001'%2CK1%3D1%2CK4%3DX'DEADBEEF')")
        self.assertTrue(
            ds_uri.nav_path[0][0] == 'CompoundKeys', "e set name")
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1]['K1'], edm.Int32Value))
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1]['K2'], edm.StringValue))
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1]['K3'], edm.DateTimeValue))
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1]['K4'], edm.BinaryValue))
        ds_uri = odata.ODataURI(
            "/CompoundKeys(K3%3Ddatetime'2013-12-25T15%3A59%3A03.142',"
            "K2%3D'00001',K1%3D1,K4%3DX'DEADBEEF')")

    def test_query_options(self):
        """QueryOptions:

        Any number of the query options MAY<5> be specified in a data
        service URI.

        The order of Query Options within a URI MUST be insignificant.

        Query option names and values MUST be treated as case sensitive.

        System Query Option names MUST begin with a "$", as seen in
        System Query Option (section 2.2.3.6.1).

        Custom Query Options (section 2.2.3.6.2) MUST NOT begin with a
        "$"."""
        ds_uri = odata.ODataURI(
            "Products()?$format=json&$top=20&$skip=10&space='%20'", '/x.svc')
        self.assertTrue(set(ds_uri.sys_query_options.keys()) ==
                        set([odata.SystemQueryOption.format,
                             odata.SystemQueryOption.top,
                             odata.SystemQueryOption.skip]),
                        repr(ds_uri.sys_query_options))
        self.assertTrue(
            ds_uri.query_options == ["space='%20'"],
            'query options')
        ds_uri = odata.ODataURI(
            "Products()?$top=20&space='%20'&$format=json&$skip=10", '/x.svc')
        self.assertTrue(set(ds_uri.sys_query_options.keys()) ==
                        set([odata.SystemQueryOption.format,
                             odata.SystemQueryOption.top,
                             odata.SystemQueryOption.skip]),
                        repr(ds_uri.sys_query_options))
        self.assertTrue(
            ds_uri.query_options == ["space='%20'"],
            'query options')
        try:
            ds_uri = odata.ODataURI("Products()?$unsupported=10", '/x.svc')
            self.fail("$unsupported system query option")
        except odata.InvalidSystemQueryOption:
            pass

    def test_common_expression(self):
        ds_uri = odata.ODataURI(
            "Products()?$filter=substringof(CompanyName,%20'bikes')", '/x.svc')
        self.assertTrue(
            isinstance(
                ds_uri.sys_query_options[odata.SystemQueryOption.filter],
                odata.CommonExpression), "Expected common expression")
        ds_uri = odata.ODataURI("Products()?$filter=true%20and%20false",
                                '/x.svc')
        f = ds_uri.sys_query_options[odata.SystemQueryOption.filter]
        self.assertTrue(
            isinstance(f, odata.CommonExpression),
            "Expected common expression")
        self.assertTrue(
            isinstance(f, odata.BinaryExpression),
            "Expected binary expression, %s" % repr(f))
        self.assertTrue(
            f.operator == odata.Operator.boolAnd,
            "Expected and: %s" % repr(f.operator))
        try:
            ds_uri = odata.ODataURI(
                "Products()?$filter=true%20nand%20false", '/x.svc')
            self.fail("Expected exception for nand")
        except odata.InvalidSystemQueryOption:
            pass

    def test_entity_set(self):
        ds_uri = odata.ODataURI(
            "Products()?$format=json&$top=20&$skip=10&space='%20'", '/x.svc')
        self.assertTrue(ds_uri.resource_path == '/Products()', "resource path")
        self.assertTrue(set(ds_uri.sys_query_options.keys()) ==
                        set([odata.SystemQueryOption.format,
                             odata.SystemQueryOption.top,
                             odata.SystemQueryOption.skip]),
                        repr(ds_uri.sys_query_options))
        self.assertTrue(
            ds_uri.query_options == ["space='%20'"],
            'query options')
        self.assertTrue(ds_uri.nav_path == [('Products', {})],
                        "e set: Products, found %s" % repr(ds_uri.nav_path))
        ds_uri = odata.ODataURI('Products()/$count', '/x.svc')
        self.assertTrue(
            ds_uri.resource_path == '/Products()/$count', "resource path")
        self.assertTrue(ds_uri.sys_query_options == {}, 'sys_query_options')
        self.assertTrue(ds_uri.query_options == [], 'query options')
        self.assertTrue(ds_uri.nav_path == [('Products', {})],
                        "path: %s" % repr(ds_uri.nav_path))
        self.assertTrue(
            ds_uri.path_option == odata.PathOption.count, "$count recognised")
        ds_uri = odata.ODataURI('Products(1)/$value', '/x.svc')
        self.assertTrue(len(ds_uri.nav_path) == 1)
        self.assertTrue(ds_uri.nav_path[0][0] == 'Products')
        self.assertTrue(len(ds_uri.nav_path[0][1]))
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1][''], edm.Int32Value),
            "Key value type")
        self.assertTrue(ds_uri.nav_path[0][1][''].value == 1, "Key value")
        # [('Products',{'':1})]
        self.assertTrue(
            ds_uri.path_option == odata.PathOption.value, "$value recognised")
        ds_uri = odata.ODataURI('Products(x=1,y=2)', '/x.svc')
        self.assertTrue(len(ds_uri.nav_path) == 1)
        self.assertTrue(ds_uri.nav_path[0][0] == 'Products')
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1]['x'], edm.Int32Value),
            "Key value type")
        self.assertTrue(ds_uri.nav_path[0][1]['x'].value == 1, "x Key value")
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1]['y'], edm.Int32Value),
            "Key value type")
        self.assertTrue(ds_uri.nav_path[0][1]['y'].value == 2, "y Key value")
        # [('Products',{'x':1,'y':2})]
        ds_uri = odata.ODataURI("/service.svc/Customers('ALF%2FKI')/Orders",
                                '/service.svc')
        self.assertTrue(len(ds_uri.nav_path) == 2)
        self.assertTrue(ds_uri.nav_path[0][0] == 'Customers')
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1][''], edm.StringValue),
            "Key value type")
        self.assertTrue(ds_uri.nav_path[0][1][''].value == 'ALF/KI',
                        "String Key value")
        self.assertTrue(ds_uri.nav_path[1][0] == 'Orders')
        ds_uri = odata.ODataURI(
            "/service.svc/Customers(%27ALF%2FKI%27)/Orders",
            '/service.svc')
        self.assertTrue(len(ds_uri.nav_path) == 2)
        self.assertTrue(ds_uri.nav_path[0][0] == 'Customers')
        self.assertTrue(
            isinstance(ds_uri.nav_path[0][1][''], edm.StringValue),
            "Key value type")
        self.assertTrue(ds_uri.nav_path[0][1][''].value == 'ALF/KI',
                        "String Key value")
        self.assertTrue(ds_uri.nav_path[1][0] == 'Orders')

    def test_expand(self):
        """Redundant expandClause rules on the same data service URI can
        be considered valid, but MUST NOT alter the meaning of the
        URI."""
        ds_uri = odata.ODataURI("Customers?$expand=Orders", '/x.svc')
        expand = ds_uri.sys_query_options[odata.SystemQueryOption.expand]
        self.assertTrue(len(expand) == 1, "One path")
        self.assertTrue(expand['Orders'] is None, "Orders nav path")
        self.assertTrue(odata.format_expand(expand) == "Orders",
                        odata.format_expand(expand))
        ds_uri = odata.ODataURI("Customers?$expand=Orders,Orders", '/x.svc')
        expand = ds_uri.sys_query_options[odata.SystemQueryOption.expand]
        self.assertTrue(len(expand) == 1, "One path")
        self.assertTrue(expand['Orders'] is None, "redundant Orders nav path")
        self.assertTrue(odata.format_expand(expand) == "Orders",
                        odata.format_expand(expand))
        ds_uri = odata.ODataURI(
            "Orders?$expand=OrderLines/Product,Customer", '/x.svc')
        expand = ds_uri.sys_query_options[odata.SystemQueryOption.expand]
        self.assertTrue(expand['OrderLines'] == {
                        'Product': None},
                        "OrderLines expansion: %s" % str(expand))
        self.assertTrue(expand['Customer'] is None, "Customer expansion")
        self.assertTrue(odata.format_expand(expand) ==
                        "Customer,OrderLines/Product")

    def test_filter(self):
        ds_uri = odata.ODataURI(
            "Orders?$filter=ShipCountry%20eq%20'France'", '/x.svc')
        filter = ds_uri.sys_query_options[odata.SystemQueryOption.filter]
        self.assertTrue(
            isinstance(filter, odata.BinaryExpression),
            "Binary expression component")
        self.assertTrue(isinstance(filter.operands[0],
                                   odata.PropertyExpression))
        self.assertTrue(filter.operands[0].name == "ShipCountry")
        ds_uri = odata.ODataURI(
            "Orders?$filter%20=%20Customers/ContactName%20ne%20'Fred'",
            '/x.svc')
        filter = ds_uri.sys_query_options[odata.SystemQueryOption.filter]
        self.assertTrue(filter.operands[0].operands[1].name == "ContactName")

    def test_format(self):
        ds_uri = odata.ODataURI("Orders?$format=json", '/x.svc')
        format = ds_uri.sys_query_options[odata.SystemQueryOption.format]
        self.assertTrue(
            isinstance(format, messages.AcceptList),
            "Format is an HTTP AcceptList instance")
        self.assertTrue(str(format) == 'application/json', str(format[0]))

    def test_orderby(self):
        ds_uri = odata.ODataURI("Orders?$orderby=ShipCountry", '/x.svc')
        orderby = ds_uri.sys_query_options[odata.SystemQueryOption.orderby]
        self.assertTrue(len(orderby) == 1, "Single orderby clause")
        orderby = orderby[0]
        self.assertTrue(orderby[1] == 1, "default is asc")
        self.assertTrue(
            isinstance(orderby[0], odata.PropertyExpression),
            "orderby is a property expression")
        self.assertTrue(orderby[0].name == 'ShipCountry', str(orderby[0]))
        ds_uri = odata.ODataURI(
            "Orders?$orderby%20=%20ShipCountry%20ne%20'France'%20desc",
            '/x.svc')
        orderby = ds_uri.sys_query_options[odata.SystemQueryOption.orderby]
        orderby = orderby[0]
        self.assertTrue(orderby[1] == -1, "desc")
        self.assertTrue(
            isinstance(orderby[0], odata.BinaryExpression),
            "orderby is a binary expression")
        self.assertTrue(
            orderby[0].operands[0].name == 'ShipCountry',
            str(orderby[0].operands[0]))
        self.assertTrue(
            orderby[0].operands[0].name == 'ShipCountry',
            str(orderby[0].operands[0]))
        ds_uri = odata.ODataURI(
            "Orders?$orderby%20=%20ShipCountry%20ne%20'France'%20desc,"
            "OrderID%20asc", '/x.svc')
        orderby = ds_uri.sys_query_options[odata.SystemQueryOption.orderby]
        self.assertTrue(len(orderby) == 2, "Two orderby clauses")

    def test_skip(self):
        """The value of this query option ... MUST be an integer greater
        than or equal to zero. If a value less than 0 is specified, the
        URI should be considered malformed."""
        ds_uri = odata.ODataURI(
            "Orders?$orderby=OrderDate%20desc&$skip=10",
            '/x.svc')
        skip = ds_uri.sys_query_options[odata.SystemQueryOption.skip]
        self.assertTrue(isinstance(skip, int), "skip type")
        self.assertTrue(skip == 10, "skip 10")
        ds_uri = odata.ODataURI("Customers('ALFKI')/Orders?$skip=10", '/x.svc')
        skip = ds_uri.sys_query_options[odata.SystemQueryOption.skip]
        self.assertTrue(skip == 10, "skip 10")
        ds_uri = odata.ODataURI("Orders?$orderby=OrderDate%20desc&$skip=0",
                                '/x.svc')
        skip = ds_uri.sys_query_options[odata.SystemQueryOption.skip]
        self.assertTrue(skip == 0, "skip 0")
        try:
            ds_uri = odata.ODataURI(
                "Orders?$orderby=OrderDate%20desc&$skip=-1", '/x.svc')
            self.fail("skip=-1")
        except odata.InvalidSystemQueryOption:
            pass

    def test_top(self):
        """The value of this query option ... MUST be an integer greater
        than or equal to zero. If a value less than 0 is specified, the
        URI should be considered malformed."""
        ds_uri = odata.ODataURI("Orders?$orderby=OrderDate%20desc&$top=10",
                                '/x.svc')
        top = ds_uri.sys_query_options[odata.SystemQueryOption.top]
        self.assertTrue(isinstance(top, int), "top type")
        self.assertTrue(top == 10, "top 10")
        ds_uri = odata.ODataURI("Customers('ALFKI')/Orders?$top=10", '/x.svc')
        top = ds_uri.sys_query_options[odata.SystemQueryOption.top]
        self.assertTrue(top == 10, "top 10")
        ds_uri = odata.ODataURI("Orders?$orderby=OrderDate%20desc&$top=0",
                                '/x.svc')
        top = ds_uri.sys_query_options[odata.SystemQueryOption.top]
        self.assertTrue(top == 0, "top 0")
        try:
            ds_uri = odata.ODataURI(
                "Orders?$orderby=OrderDate%20desc&$top=-1", '/x.svc')
            self.fail("top=-1")
        except odata.InvalidSystemQueryOption:
            pass

    def test_skiptoken(self):
        """The value of this query option ... MUST be an integer greater
        than or equal to zero. If a value less than 0 is specified, the
        URI should be considered malformed."""
        ds_uri = odata.ODataURI(
            "Orders?$orderby=OrderDate%20desc&$skiptoken=AEF134ad", '/x.svc')
        skiptoken = ds_uri.sys_query_options[odata.SystemQueryOption.skiptoken]
        self.assertTrue(is_unicode(skiptoken), "skiptoken type")
        self.assertTrue(skiptoken == "AEF134ad", "skiptoken opqque string")
        ds_uri = odata.ODataURI(
            "Customers('ALFKI')/Orders?$skiptoken=0%2010", '/x.svc')
        skiptoken = ds_uri.sys_query_options[odata.SystemQueryOption.skiptoken]
        self.assertTrue(skiptoken == "0 10", "skiptoken 010")

    def test_inlinecount(self):
        """inlinecountQueryOp = "$inlinecount=" ("allpages" / "none") """
        ds_uri = odata.ODataURI("Orders?$inlinecount=allpages", '/x.svc')
        inlinecount = ds_uri.sys_query_options[
            odata.SystemQueryOption.inlinecount]
        self.assertTrue(
            inlinecount == odata.InlineCount.allpages, "allpages constant")
        ds_uri = odata.ODataURI("Orders?$inlinecount=allpages&$top=10",
                                '/x.svc')
        inlinecount = ds_uri.sys_query_options[
            odata.SystemQueryOption.inlinecount]
        self.assertTrue(
            inlinecount == odata.InlineCount.allpages, "allpages constant")
        ds_uri = odata.ODataURI("Orders?$inlinecount=none&$top=10", '/x.svc')
        inlinecount = ds_uri.sys_query_options[
            odata.SystemQueryOption.inlinecount]
        self.assertTrue(inlinecount == odata.InlineCount.none, "none constant")
        ds_uri = odata.ODataURI(
            "Orders?$inlinecount=allpages&"
            "$filter=ShipCountry%20eq%20'France'",
            '/x.svc')
        inlinecount = ds_uri.sys_query_options[
            odata.SystemQueryOption.inlinecount]
        self.assertTrue(
            inlinecount == odata.InlineCount.allpages, "allpages constant")

    def test_select(self):
        """Syntax::

        selectQueryOp = "$select=" selectClause
        selectClause = [WSP] selectItem [[WSP] "," selectClause] [WSP]
        selectItem = star / selectedProperty / (selectedNavProperty
            ["/" selectItem])
        selectedProperty = entityProperty / entityComplexProperty
        selectedNavProperty = entityNavProperty-es / entityNavProperty-et
        star = "*"	"""
        ds_uri = odata.ODataURI(
            "Customers?$select=CustomerID,CompanyName,Address", '/x.svc')
        select = ds_uri.sys_query_options[odata.SystemQueryOption.select]
        self.assertTrue(len(select) == 3, "Three paths")
        self.assertTrue(
            select == {'CompanyName': None,
                       'CustomerID': None,
                       'Address': None})
        ds_uri = odata.ODataURI("Customers?$select=CustomerID,Orders",
                                '/x.svc')
        select = ds_uri.sys_query_options[odata.SystemQueryOption.select]
        self.assertTrue(select == {'CustomerID': None, 'Orders': None})
        ds_uri = odata.ODataURI(
            "Customers?$select=CustomerID,Orders&$expand=Orders/OrderDetails",
            '/x.svc')
        select = ds_uri.sys_query_options[odata.SystemQueryOption.select]
        self.assertTrue(select == {'CustomerID': None, 'Orders': None})
        ds_uri = odata.ODataURI("Customers?$select=*", '/x.svc')
        select = ds_uri.sys_query_options[odata.SystemQueryOption.select]
        self.assertTrue(select == {'*': None})
        ds_uri = odata.ODataURI("Customers?$select=CustomerID,Orders/*&"
                                "$expand=Orders/OrderDetails", '/x.svc')
        select = ds_uri.sys_query_options[odata.SystemQueryOption.select]
        self.assertTrue(select == {'CustomerID': None, 'Orders': {'*': None}})
        ds_uri = odata.ODataURI(
            "/service.svc/Customers?$expand=Orders&"
            "$filter=substringof(CompanyName,%20'bikes')&"
            "$orderby=CompanyName%20asc&$top=2&$skip=3&"
            "$skiptoken='Contoso','AKFNU'&"
            "$inlinecount=allpages&"
            "$select=CustomerID,CompanyName,Orders&$format=xml")
        select = ds_uri.sys_query_options[odata.SystemQueryOption.select]
        self.assertTrue(len(select) == 3, "Three paths")
        try:
            ds_uri = odata.ODataURI("Customers?$select=CustomerID,*/Orders")
            self.fail("* must be last item in a select clause")
        except odata.InvalidSystemQueryOption:
            pass


class JSONTests(unittest.TestCase):

    def test_datetime_to_json(self):
        v = edm.EDMValue.from_type(edm.SimpleType.DateTime)
        j = odata.simple_value_to_json_str(v)
        self.assertTrue(j == "null")
        d = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0))
        v.set_from_value(d)
        j = odata.simple_value_to_json_str(v)
        self.assertTrue(j == '"\\/Date(0)\\/"', j)
        d = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=6, minute=0, second=0))
        v.set_from_value(d)
        j = odata.simple_value_to_json_str(v)
        self.assertTrue(j == '"\\/Date(21600000)\\/"', j)

    def test_datetime_from_json(self):
        d = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0))
        v = edm.EDMValue.from_type(edm.SimpleType.DateTime)
        odata.simple_value_from_json(v, None)
        self.assertFalse(v)
        # json.loads will have removed the redundant back-slash
        odata.simple_value_from_json(v, "/Date(0)/")
        self.assertTrue(v)
        self.assertTrue(v.value == d)
        # A timezone offset is valid for DateTime but we are going to
        # strip the zone, should we convert to UTC before doing so?  Yes
        # because the person who sent us this value is going to get
        # something back without an offset when we serialise and, if
        # they follow the standard, they'll assume it's UTZ and can
        # reapply their desired offset.
        odata.simple_value_from_json(v, "/Date(21600000+0360)/")
        self.assertTrue(v)
        self.assertTrue(v.value == d)
        # It also appears that sometimes we'll get ISO dates and
        # need to handle them in the same way.
        odata.simple_value_from_json(v, "1970-01-01T00:00:00")
        self.assertTrue(v)
        self.assertTrue(v.value == d)
        odata.simple_value_from_json(v, "1970-01-01T00:00:00Z")
        self.assertTrue(v)
        self.assertTrue(v.value == d)
        odata.simple_value_from_json(v, "1970-01-01T06:00:00+06:00")
        self.assertTrue(v)
        self.assertTrue(v.value == d)

    def test_datetimeoffset_to_json(self):
        v = edm.EDMValue.from_type(edm.SimpleType.DateTimeOffset)
        j = odata.simple_value_to_json_str(v)
        self.assertTrue(j == "null")
        d = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0, zdirection=-1, zhour=5))
        v.set_from_value(d)
        j = odata.simple_value_to_json_str(v)
        self.assertTrue(j == '"\\/Date(0-0300)\\/"', j)
        d = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=6, minute=0, second=0, zdirection=1, zhour=5))
        v.set_from_value(d)
        j = odata.simple_value_to_json_str(v)
        self.assertTrue(j == '"\\/Date(21600000+0300)\\/"', j)

    def test_datetimeoffset_from_json(self):
        d0 = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0, zdirection=0))
        d = iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0, zdirection=-1, zhour=5))
        v = edm.EDMValue.from_type(edm.SimpleType.DateTimeOffset)
        odata.simple_value_from_json(v, None)
        self.assertFalse(v)
        # json.loads will have removed the redundant back-slash
        odata.simple_value_from_json(v, "/Date(0)/")
        self.assertTrue(v)
        self.assertTrue(v.value == d0, "extended to UTC")
        self.assertTrue(v.value.get_zone()[0] == 0, "extended to UTC")
        odata.simple_value_from_json(v, "/Date(0-0300)/")
        self.assertTrue(v)
        self.assertTrue(v.value == d)
        self.assertTrue(v.value.get_zone() == (-1, 300), "zone preserved")
        # It also appears that sometimes we'll get ISO dates and
        # need to handle them in the same way.
        odata.simple_value_from_json(v, "1970-01-01T00:00:00")
        self.assertTrue(v)
        self.assertTrue(v.value == d0)
        odata.simple_value_from_json(v, "1970-01-01T00:00:00Z")
        self.assertTrue(v)
        self.assertTrue(v.value == d0)
        odata.simple_value_from_json(v, "1970-01-01T00:00:00-05:00")
        self.assertTrue(v)
        self.assertTrue(v.value == d)
        self.assertTrue(v.value.get_zone() == (-1, 300), "zone preserved")


class StreamInfoTests(unittest.TestCase):

    def test_init(self):
        sinfo = odata.StreamInfo()
        self.assertTrue(sinfo.type, params.MediaType)
        self.assertTrue(sinfo.type == params.APPLICATION_OCTETSTREAM)
        self.assertTrue(sinfo.created is None)
        self.assertTrue(sinfo.modified is None)
        self.assertTrue(sinfo.size is None)
        self.assertTrue(sinfo.md5 is None)
        sinfo2 = odata.StreamInfo(type=params.PLAIN_TEXT)
        self.assertTrue(sinfo2.type == params.PLAIN_TEXT)


class DataServiceRegressionTests(unittest.TestCase):

    """Abstract class used to test individual data services."""

    def setUp(self):        # noqa
        self.regressionData = FilePath(
            FilePath(__file__).abspath().split()[0], 'data_odatav2',
            'sample_server')
        doc = edmx.Document()
        md_path = self.regressionData.join('regression.xml')
        with md_path.open('rb') as f:
            doc.read(f)
        self.ds = doc.root.DataServices

    def tearDown(self):     # noqa
        pass

    def runtest_autokey(self):
        container = self.ds['RegressionModel.RegressionContainer']
        for keytype in ['Int32', 'Int64', 'String']:
            autokeys = container['AutoKeys' + keytype]
            with autokeys.open() as coll:
                e = coll.new_entity()
                self.assertTrue(e.exists is False)
                e['Data'].set_from_value('hello')
                coll.insert_entity(e)
                self.assertTrue(e.exists)
                try:
                    self.assertTrue(e.key() is not None)
                except KeyError:
                    self.fail("insert_entity returned a NULL key (%s)" %
                              keytype)

    def check_null(self, entity, exclude=[]):
        for pname in entity.data_keys():
            # check each property is NULL
            if pname in exclude:
                continue
            p = entity[pname]
            if isinstance(p, edm.Complex):
                for ppname in p.iterkeys():
                    self.assertFalse(p[ppname])
            else:
                self.assertFalse(entity[pname])

    def runtest_all_type_defaults(self):
        all_types = self.ds[
            'RegressionModel.RegressionContainer.AllTypeDefaults']
        with all_types.open() as coll:
            e = coll.new_entity()
            # defaults are informational and should not be set here
            self.check_null(e)
            e['ID'].set_from_value(1)
            e['NoDefaultNotNullable'].set_from_value(1)
            # insert with all items selected... all NULL that can be
            coll.insert_entity(e)
            self.check_null(e, exclude=['ID', 'NoDefaultNotNullable'])
            # now do a read back
            e1 = coll[1]
            self.check_null(e1, exclude=['ID', 'NoDefaultNotNullable'])
            # PUT semantics, unselected items are set to defaults so
            # unselect everything and update
            e1.expand(None, {})
            try:
                coll.update_entity(e1, merge=False)
                self.fail("update: Non-nullable property with no default")
            except edm.ConstraintError:
                pass
            e1 = coll[1]
            e1.expand(None, {'NoDefaultNotNullable': None})
            e1['NoDefaultNotNullable'].set_from_value(1)
            coll.update_entity(e1, merge=False)
            # we'll have to read back again to load the updated values
            e1 = coll[1]
            self.assertTrue(e1['ID'].value == 1, "ID on read")
            self.assertTrue(e1['BinaryFixed'].value == b'1234567890',
                            "BinaryFixed on read")
            self.assertTrue(e1['BinaryVariable'].value == b'1234567',
                            "BinaryVariable on read")
            self.assertTrue(e1['BooleanProperty'].value is True,
                            "BooleanProperty on read")
            self.assertTrue(isinstance(e1['DateTimeProperty'].value,
                                       iso.TimePoint),
                            "DateTimeProperty type on read")
            self.assertTrue(e1['DateTimeProperty'].value ==
                            iso.TimePoint.from_str('1972-03-03T09:45:00.000'),
                            "DateTimeProperty value on read")
            self.assertTrue(isinstance(
                e1['TimeProperty'].value, iso.Time),
                "TimeProperty type on read")
            self.assertTrue(e1['TimeProperty'].value ==
                            iso.Time.from_str('09:45:00.000'),
                            "TimeProperty value on read")
            self.assertTrue(
                isinstance(e1['DateTimeOffsetProperty'].value,
                           iso.TimePoint),
                "DateTimeOffsetProperty type on read")
            self.assertTrue(e1['DateTimeOffsetProperty'].value ==
                            iso.TimePoint.from_str(
                                '1972-07-03T09:45:00.000+01:00'),
                            "DateTimeOffsetProperty value on read")
            self.assertTrue(isinstance(e1['DecimalProperty'].value,
                                       decimal.Decimal),
                            "DecimalProperty type on read")
            self.assertTrue(e1['DecimalProperty'].value ==
                            decimal.Decimal('3.14'),
                            "DecimalProperty value on read")
            self.assertTrue(
                e1['SingleValue'].value == 3.14, "SingleValue on read")
            self.assertTrue(
                e1['DoubleValue'].value == 3.14, "DoubleValue on read")
            self.assertTrue(
                isinstance(e1['GuidValue'].value, uuid.UUID),
                "GuidValue type on read")
            self.assertTrue(
                e1['GuidValue'].value == uuid.UUID(int=3),
                "GuidValue value on read")
            self.assertTrue(
                e1['SByteValue'].value == 3, "SByteValue on read")
            self.assertTrue(
                e1['Int16Value'].value == 3, "Int16Value on read")
            self.assertTrue(
                e1['Int64Value'].value == 3, "Int64Value on read")
            self.assertTrue(
                e1['ByteValue'].value == 3, "ByteValue on read")
            self.assertTrue(
                e1['UnicodeString'].value == ul("Caf\xe9"),
                "UnicodeString on read")
            self.assertTrue(
                e1['ASCIIString'].value == "Cafe",
                "ASCIIString on read")
            self.assertTrue(
                e1['FixedString'].value == "ALFKI",
                "FixedString on read")
            self.assertTrue(
                e1['Complex']['Data'].value == "GotIt!",
                "Complex/Data on read")
            self.assertTrue(
                e1['Complex']['Index'].value == 3,
                "Complex/Index on read")
            # nullable property will default to NULL
            self.assertFalse(e1['NoDefaultNullable'])
            self.assertTrue(e1['NoDefaultNotNullable'].value == 1)
            e = coll.new_entity()
            e['ID'].set_from_value(2)
            e['UnicodeString'].set_from_value(ul("Caf\xe9s"))
            # INSERT should use defaults for unselected properties
            e.expand(None, {'ID': None, 'UnicodeString': None})
            try:
                coll.insert_entity(e)
                self.fail("insert: Non-nullable property with no default")
            except edm.ConstraintError:
                pass
            e = coll.new_entity()
            e['ID'].set_from_value(2)
            e['UnicodeString'].set_from_value(ul("Caf\xe9s"))
            e['NoDefaultNotNullable'].set_from_value(1)
            e.expand(None, {'ID': None, 'UnicodeString': None,
                            'NoDefaultNotNullable': None})
            coll.insert_entity(e)
            e2 = coll[2]
            self.assertTrue(e2['ID'].value == 2, "ID on read")
            self.assertTrue(e2['BinaryFixed'].value == b'1234567890',
                            "BinaryFixed on read")
            self.assertTrue(
                e2['UnicodeString'].value == ul("Caf\xe9s"),
                "UnicodeString on read")
            self.assertTrue(
                e2['ASCIIString'].value == "Cafe",
                "ASCIIString on read")
            self.assertFalse(e1['NoDefaultNullable'])
            self.assertTrue(e1['NoDefaultNotNullable'].value == 1)
            # MERGE semantics, unselected items are left unchanged
            # unselect all but one field and update
            e2['ASCIIString'].set_from_value("Cafes")
            e2['UnicodeString'].set_from_value("Ignored")
            e2.expand(None, {'ASCIIString': None})
            coll.update_entity(e2)
            # read back
            e2 = coll[2]
            self.assertTrue(e2['ID'].value == 2, "ID on read")
            # check a field we didn't touch
            self.assertTrue(e2['BinaryFixed'].value == b'1234567890',
                            "BinaryFixed on read")
            # check UnicodeString is not reverted to default
            self.assertTrue(e2['UnicodeString'].value == ul("Caf\xe9s"))
            # check the field we updated
            self.assertTrue(e2['ASCIIString'].value == "Cafes")
            # check fields with no default
            self.assertFalse(e1['NoDefaultNullable'])
            self.assertTrue(e1['NoDefaultNotNullable'].value == 1)

    def runtest_all_types(self):
        all_types = self.ds['RegressionModel.RegressionContainer.AllTypes']
        with all_types.open() as coll:
            e = coll.new_entity()
            self.assertTrue(e.exists is False)
            # <Property Name="ID" Type="Edm.Int32" Nullable="false"/>
            e['ID'].set_from_value(1)
            # <Property Name="BinaryFixed" Type="Edm.Binary"
            # MaxLength="10" FixedLength="true"/>
            e['BinaryFixed'].set_from_value(b'1234567890')
            # <Property Name="BinaryVariable" Type="Edm.Binary"
            # MaxLength="10" FixedLength="false"/>
            e['BinaryVariable'].set_from_value(b'1234567')
            # <Property Name="BooleanProperty" Type="Edm.Boolean"/>
            e['BooleanProperty'].set_from_value(True)
            # <Property Name="DateTimeProperty" Type="Edm.DateTime"
            # Precision="3"/>
            e['DateTimeProperty'].set_from_value(
                iso.TimePoint.from_str('1972-03-03T09:45:00'))
            # <Property Name="TimeProperty" Type="Edm.Time" Precision="3"/>
            e['TimeProperty'].set_from_value(
                iso.Time.from_str('09:45:00'))
            # <Property Name="DateTimeOffsetProperty"
            # Type="Edm.DateTimeOffset" Precision="3"/>
            e['DateTimeOffsetProperty'].set_from_value(
                iso.TimePoint.from_str('1972-07-03T09:45:00+01:00'))
            # <Property Name="DecimalProperty" Type="Edm.Decimal"
            # Precision="10" Scale="2"/>
            e['DecimalProperty'].set_from_value(decimal.Decimal('3.14'))
            # <Property Name="SingleValue" Type="Edm.Single"/>
            e['SingleValue'].set_from_value(3.14)
            # <Property Name="DoubleValue" Type="Edm.Double"/>
            e['DoubleValue'].set_from_value(3.14)
            # <Property Name="GuidValue" Type="Edm.Guid"/>
            e['GuidValue'].set_from_value(uuid.UUID(int=3))
            # <Property Name="SByteValue" Type="Edm.SByte"/>
            e['SByteValue'].set_from_value(3)
            # <Property Name="Int16Value" Type="Edm.Int16"/>
            e['Int16Value'].set_from_value(3)
            # <Property Name="Int64Value" Type="Edm.Int64"/>
            e['Int64Value'].set_from_value(3)
            # <Property Name="ByteValue" Type="Edm.Byte"/>
            e['ByteValue'].set_from_value(3)
            # <Property Name="UnicodeString" Type="Edm.String"
            # Unicode="true" FixedLength="false" MaxLength="10"/>
            e['UnicodeString'].set_from_value(ul("Caf\xe9"))
            # <Property Name="ASCIIString" Type="Edm.String"
            # Unicode="false" FixedLength="false" MaxLength="10"/>
            e['ASCIIString'].set_from_value(ul("Cafe"))
            # <Property Name="FixedString" Type="Edm.String"
            # FixedLength="true" MaxLength="5"/>
            e['FixedString'].set_from_value(ul("ALFKI"))
            # CREATE
            coll.insert_entity(e)
            self.assertTrue(e.exists is True)
            try:
                self.assertTrue(e.key() is not None)
            except KeyError:
                self.fail("Entity with NULL key after insert")
            # READ (coll)
            self.assertTrue(
                len(coll) == 1, "AllTypes length after insert")
            got_e = coll.values()[0]
            self.assertTrue(got_e['ID'].value == 1)
            # READ (by key)
            got_e = coll[1]
            self.assertTrue(got_e['ID'].value == 1, "ID on read")
            self.assertTrue(got_e['BinaryFixed'].value == b'1234567890',
                            "BinaryFixed on read")
            self.assertTrue(got_e['BinaryVariable'].value == b'1234567',
                            "BinaryVariable on read")
            self.assertTrue(got_e['BooleanProperty'].value is True,
                            "BooleanProperty on read")
            self.assertTrue(isinstance(got_e['DateTimeProperty'].value,
                                       iso.TimePoint),
                            "DateTimeProperty type on read")
            self.assertTrue(got_e['DateTimeProperty'].value ==
                            iso.TimePoint.from_str('1972-03-03T09:45:00'),
                            "DateTimeProperty value on read")
            self.assertTrue(isinstance(
                got_e['TimeProperty'].value, iso.Time),
                "TimeProperty type on read")
            self.assertTrue(got_e['TimeProperty'].value ==
                            iso.Time.from_str('09:45:00'),
                            "TimeProperty value on read")
            self.assertTrue(
                isinstance(got_e['DateTimeOffsetProperty'].value,
                           iso.TimePoint),
                "DateTimeOffsetProperty type on read")
            self.assertTrue(got_e['DateTimeOffsetProperty'].value ==
                            iso.TimePoint.from_str(
                                '1972-07-03T09:45:00+01:00'),
                            "DateTimeOffsetProperty value on read")
            self.assertTrue(isinstance(got_e['DecimalProperty'].value,
                                       decimal.Decimal),
                            "DecimalProperty type on read")
            self.assertTrue(got_e['DecimalProperty'].value ==
                            decimal.Decimal('3.14'),
                            "DecimalProperty value on read")
            self.assertTrue(
                got_e['SingleValue'].value == 3.14, "SingleValue on read")
            self.assertTrue(
                got_e['DoubleValue'].value == 3.14, "DoubleValue on read")
            self.assertTrue(
                isinstance(got_e['GuidValue'].value, uuid.UUID),
                "GuidValue type on read")
            self.assertTrue(
                got_e['GuidValue'].value == uuid.UUID(int=3),
                "GuidValue value on read")
            self.assertTrue(
                got_e['SByteValue'].value == 3, "SByteValue on read")
            self.assertTrue(
                got_e['Int16Value'].value == 3, "Int16Value on read")
            self.assertTrue(
                got_e['Int64Value'].value == 3, "Int64Value on read")
            self.assertTrue(
                got_e['ByteValue'].value == 3, "ByteValue on read")
            self.assertTrue(
                got_e['UnicodeString'].value == ul("Caf\xe9"),
                "UnicodeString on read")
            self.assertTrue(
                got_e['ASCIIString'].value == "Cafe",
                "ASCIIString on read")
            self.assertTrue(
                got_e['FixedString'].value == "ALFKI",
                "FixedString on read")
            # UPDATE
            got_e['BinaryFixed'].set_from_value(
                b'\x00\x01\x02\x03\x04~\xDE\xAD\xBE\xEF')
            got_e['BinaryVariable'].set_from_value(b'\x00~\xDE\xAD\xBE\xEF')
            got_e['BooleanProperty'].set_from_value(False)
            got_e['DateTimeProperty'].set_from_value(
                iso.TimePoint.from_str('2013-12-25T15:59:03.142'))
            got_e['TimeProperty'].set_from_value(
                iso.Time.from_str('17:32:03.142'))
            got_e['DateTimeOffsetProperty'].set_from_value(
                iso.TimePoint.from_str('2013-12-25T15:59:03.142-05:00'))
            got_e['DecimalProperty'].set_from_value(
                decimal.Decimal('-100.50'))
            got_e['SingleValue'].set_from_value(-100.5)
            got_e['DoubleValue'].set_from_value(-100.5)
            got_e['GuidValue'].set_from_value(
                uuid.UUID(int=20131225155903142))
            got_e['SByteValue'].set_from_value(-101)
            got_e['Int16Value'].set_from_value(-101)
            got_e['Int64Value'].set_from_value(-101)
            got_e['ByteValue'].set_from_value(255)
            got_e['UnicodeString'].set_from_value(u8(b'I\xe2\x9d\xa4Unicode'))
            got_e['ASCIIString'].set_from_value("Bistro")
            got_e['FixedString'].set_from_value(
                u8(b'\xe2\x9e\x80\xe2\x9e\x81\xe2\x9e\x82\xe2\x9e\x83'
                   b'\xe2\x9e\x84'))
            coll.update_entity(got_e)
            check_e = coll[1]
            self.assertTrue(check_e['BinaryFixed'].value ==
                            b'\x00\x01\x02\x03\x04~\xDE\xAD\xBE\xEF',
                            "BinaryFixed on read")
            self.assertTrue(check_e['BinaryVariable'].value ==
                            b'\x00~\xDE\xAD\xBE\xEF',
                            "BinaryVariable on read")
            self.assertTrue(check_e['BooleanProperty'].value is False,
                            "BooleanProperty on read")
            self.assertTrue(isinstance(check_e['DateTimeProperty'].value,
                                       iso.TimePoint),
                            "DateTimeProperty type on read")
            self.assertTrue(check_e['DateTimeProperty'].value ==
                            iso.TimePoint.from_str(
                                '2013-12-25T15:59:03.142'),
                            "DateTimeProperty value on read: %s" %
                            str(check_e['DateTimeProperty'].value))
            self.assertTrue(isinstance(check_e['TimeProperty'].value,
                                       iso.Time), "TimeProperty type on read")
            self.assertTrue(check_e['TimeProperty'].value.get_string(
                ndp=3, dp=".") == '17:32:03.142', "TimeProperty value on read")
            self.assertTrue(
                isinstance(check_e['DateTimeOffsetProperty'].value,
                           iso.TimePoint),
                "DateTimeOffsetProperty type on read")
            self.assertTrue(
                check_e['DateTimeOffsetProperty'].value.get_calendar_string(
                    ndp=3, dp=".") == '2013-12-25T15:59:03.142-05:00',
                "DateTimeOffsetProperty value on read")
            self.assertTrue(isinstance(check_e[
                            'DecimalProperty'].value, decimal.Decimal),
                            "DecimalProperty type on read")
            self.assertTrue(check_e['DecimalProperty'].value ==
                            decimal.Decimal('-100.50'),
                            "DecimalProperty value on read")
            self.assertTrue(
                check_e['SingleValue'].value == -100.5,
                "SingleValue on read")
            self.assertTrue(
                check_e['DoubleValue'].value == -100.5,
                "DoubleValue on read")
            self.assertTrue(
                isinstance(check_e['GuidValue'].value, uuid.UUID),
                "GuidValue type on read")
            self.assertTrue(check_e['GuidValue'].value == uuid.UUID(
                int=20131225155903142), "GuidValue value on read")
            self.assertTrue(
                check_e['SByteValue'].value == -101, "SByteValue on read")
            self.assertTrue(
                check_e['Int16Value'].value == -101, "Int16Value on read")
            self.assertTrue(
                check_e['Int64Value'].value == -101, "Int64Value on read")
            self.assertTrue(
                check_e['ByteValue'].value == 255, "ByteValue on read")
            self.assertTrue(
                check_e['UnicodeString'].value == u8(b'I\xe2\x9d\xa4Unicode'),
                "UnicodeString on read")
            self.assertTrue(check_e['ASCIIString'].value == "Bistro",
                            "ASCIIString on read")
            self.assertTrue(check_e['FixedString'].value ==
                            u8(b'\xe2\x9e\x80\xe2\x9e\x81\xe2\x9e\x82'
                               b'\xe2\x9e\x83\xe2\x9e\x84'),
                            "FixedString on read")
            # DELETE
            del coll[1]
            self.assertTrue(
                len(coll) == 0, "AllTypes length after DELETE")
            try:
                got_e = coll[1]
                self.fail("Index into coll after AllTypes DELETE")
            except KeyError:
                pass
            # NULL tests
            # CREATE
            e = coll.new_entity()
            e['ID'].set_from_value(2)
            coll.insert_entity(e)
            # READ
            got_e = coll[2]
            self.assertTrue(got_e['ID'].value == 2)
            # all other fields should be NULL
            for k, v in got_e.iteritems():
                if k == 'ID':
                    continue
                self.assertFalse(v, "%s NULL on read" % k)

    def runtest_complex_types(self):
        complex_types = self.ds[
            'RegressionModel.RegressionContainer.ComplexTypes']
        with complex_types.open() as coll:
            e = coll.new_entity()
            e['ID'].set_from_value(100)
            e['Complex']['Data'].set_from_value("Level1")
            e['Complex']['Complex']['Data'].set_from_value("Level2")
            e['Complex']['Complex']['Index'].set_from_value(255)
            # CREATE
            coll.insert_entity(e)
            # READ (coll)
            self.assertTrue(
                len(coll) == 1, "complex_types length after insert")
            got_e = coll.values()[0]
            self.assertTrue(got_e['ID'].value == 100)
            # READ (by key)
            got_e = coll[100]
            self.assertTrue(got_e['ID'].value == 100, "ID on read")
            self.assertTrue(
                got_e['Complex']['Data'].value == 'Level1',
                "Level 1 on read")
            self.assertTrue(
                got_e['Complex']['Complex']['Data'].value == 'Level2',
                "Level 2 on read")
            self.assertTrue(
                got_e['Complex']['Complex']['Index'].value == 255,
                "Level 2 index on read")
            # UPDATE
            got_e['Complex']['Data'].set_from_value("Level1Update")
            got_e['Complex']['Complex'][
                'Data'].set_from_value("Level2Update")
            got_e['Complex']['Complex']['Index'].set_from_value(-255)
            coll.update_entity(got_e)
            check_e = coll[100]
            self.assertTrue(
                check_e['Complex']['Data'].value == 'Level1Update',
                "Level 1 on read")
            self.assertTrue(check_e['Complex']['Complex'][
                            'Data'].value == 'Level2Update',
                            "Level 2 on read")
            self.assertTrue(
                check_e['Complex']['Complex']['Index'].value == -255,
                "Level 2 index on read")
            # DELETE
            del coll[100]
            self.assertTrue(
                len(coll) == 0, "complex_types length after DELETE")
            try:
                got_e = coll[100]
                self.fail("Index into coll after complex_types DELETE")
            except KeyError:
                pass

    def runtest_only_key(self):
        only_keys = self.ds[
            'RegressionModel.RegressionContainer.OnlyKeys']
        with only_keys.open() as coll:
            e = coll.new_entity()
            e['ID'].set_from_value(100)
            # CREATE
            coll.insert_entity(e)
            # READ (coll)
            self.assertTrue(
                len(coll) == 1, "only_keys length after insert")
            got_e = coll.values()[0]
            self.assertTrue(got_e['ID'].value == 100)
            # READ (by key)
            got_e = coll[100]
            self.assertTrue(got_e['ID'].value == 100, "ID on read")
            # UPDATE
            # nothing to change, should do nothing!
            coll.update_entity(got_e)
            coll[100]
            # DELETE
            del coll[100]
            self.assertTrue(
                len(coll) == 0, "only_keys length after DELETE")
            try:
                got_e = coll[100]
                self.fail("Index into coll after only_keys DELETE")
            except KeyError:
                pass

    def runtest_compound_key(self):
        compound_keys = self.ds[
            'RegressionModel.RegressionContainer.CompoundKeys']
        compound_keyxs = self.ds[
            'RegressionModel.RegressionContainer.CompoundKeyXs']
        with compound_keys.open() as coll:
            e = coll.new_entity()
            e['K1'].set_from_value(1)
            e['K2'].set_from_value('00001')
            e['K3'].set_from_value(
                iso.TimePoint.from_str('2013-12-25T15:59:03.142'))
            e['K4'].set_from_value(b'\xde\xad\xbe\xef')
            e['Data'].set_from_value("Compound Key")
            # CREATE
            coll.insert_entity(e)
            # READ (coll)
            self.assertTrue(
                len(coll) == 1, "CompoundKey length after insert")
            got_e = coll.values()[0]
            self.assertTrue(got_e['K1'].value == 1)
            self.assertTrue(got_e['K2'].value == '00001')
            self.assertTrue(got_e['K3'].value.get_calendar_string(
                ndp=3, dp=".") == '2013-12-25T15:59:03.142')
            self.assertTrue(got_e['K4'].value == b'\xde\xad\xbe\xef')
            self.assertTrue(got_e['Data'].value == 'Compound Key')
            # READ (by key)
            got_e = coll[(1, '00001', iso.TimePoint.from_str(
                '2013-12-25T15:59:03.142'), b'\xde\xad\xbe\xef')]
            self.assertTrue(got_e['Data'].value == "Compound Key")
            # UPDATE
            got_e['Data'].set_from_value("Updated Compound Key")
            coll.update_entity(got_e)
            check_e = coll[(1, '00001', iso.TimePoint.from_str(
                '2013-12-25T15:59:03.142'), b'\xde\xad\xbe\xef')]
            self.assertTrue(
                check_e['Data'].value == 'Updated Compound Key')
            with compound_keyxs.open() as collx:
                ex = collx.new_entity()
                ex['K'].set_from_value(10)
                ex['Data'].set_from_value("Compound KeyX")
                # add a binding
                ex['CompoundKey'].bind_entity(got_e)
                collx.insert_entity(ex)
            with got_e['CompoundKeyXs'].open() as collx:
                self.assertTrue(len(collx) == 1)
                self.assertTrue(10 in collx)
                ex = collx.values()[0]
                match_e = ex['CompoundKey'].get_entity()
                self.assertTrue(match_e == got_e)
            # DELETE
            del coll[(1, '00001', iso.TimePoint.from_str(
                '2013-12-25T15:59:03.142'), b'\xde\xad\xbe\xef')]
            self.assertTrue(
                len(coll) == 0, "CompoundKey length after DELETE")
            try:
                got_e = coll[(1, '00001', iso.TimePoint.from_str(
                    '2013-12-25T15:59:03.142'), b'\xde\xad\xbe\xef')]
                self.fail("Index into coll after CompoundKey DELETE")
            except KeyError:
                pass

    def runtest_simple_select(self):
        select_set = self.ds[
            'RegressionModel.RegressionContainer.SimpleSelectSet']
        with select_set.open() as coll:
            e = coll.new_entity()
            e.set_key(1)
            e['P1'].set_from_value(3.14)
            e['P2'].set_from_value("Pi")
            coll.insert_entity(e)
            e = coll.new_entity()
            e.set_key(2)
            e['P1'].set_from_value(2.72)
            e['P2'].set_from_value("e")
            coll.insert_entity(e)
            coll.select_keys()
            e = coll[1]
            self.assertTrue(e.is_selected('K'), "Key not selected")
            self.assertTrue(e['K'], "Key not selected")
            self.assertFalse(
                e.is_selected('P1'), "P1 should not be selected")
            self.assertFalse(e['P1'], "P1 value should be NULL")
            self.assertFalse(
                e.is_selected('P2'), "P2 should not be selected")
            self.assertFalse(e['P2'], "P2 value should be NULL")
            coll.set_expand(None, {'P1': None})
            for k, e in coll.iteritems():
                self.assertTrue(
                    e['K'].value == k, "Key selected and in coll")
                self.assertTrue(e['P1'])
                self.assertFalse(e['P2'])

    def runtest_paging(self):
        paging_set = self.ds['RegressionModel.RegressionContainer.PagingSet']
        with paging_set.open() as coll:
            for i in range3(10):
                for j in range3(10):
                    e = coll.new_entity()
                    e.set_key((i, j))
                    e['Sum'].set_from_value(i + j)
                    e['Product'].set_from_value(i * j)
                    coll.insert_entity(e)
            # first test, iterpage with no page set, all values returned
            self.assertTrue(len(list(coll.iterpage())) == 100, "no page")
            # now use top and skip only, no ordering
            coll.set_page(10, 2)
            result = list(coll.iterpage())
            self.assertTrue(len(result) == 10, "10,2: length")
            self.assertTrue(
                coll.next_skiptoken() is None, "10,2: skiptoken")
            self.assertTrue(result[0].key() == (0, 2), "10,2: first page")
            result = list(coll.iterpage(set_next=True))
            self.assertTrue(
                result[0].key() == (0, 2), "10,2: first page repeated")
            self.assertTrue(
                len(result) == 10, "10,2: length, first page repeated")
            for i in range3(8):
                result = list(coll.iterpage(set_next=True))
                self.assertTrue(
                    result[0].key() == (1 + i, 2), "10,2: page %i" % (i + 2))
                self.assertTrue(
                    len(result) == 10, "10,2: length, page %i" % (i + 2))
            result = list(coll.iterpage(set_next=True))
            self.assertTrue(len(result) == 8, "10,2: length, last page")
            self.assertTrue(result[7].key() == (9, 9), "10,2: last e")
            result = list(coll.iterpage(set_next=True))
            self.assertTrue(len(result) == 0, "10,2: overrun")
            # test skiptoken
            try:
                coll.set_topmax(5)
                coll.set_page(top=10)
                result = list(coll.iterpage())
                self.assertTrue(len(result) == 5, "max 5: length")
                self.assertTrue(
                    result[4].key() == (0, 4),
                    "max 5: last e on first page")
                # there should be a skiptoken
                token = coll.next_skiptoken()
                self.assertTrue(token is not None, "skip token present")
                for i in range3(4):
                    logging.info("$skiptoken=%s", coll.next_skiptoken())
                    result = list(coll.iterpage(set_next=True))
                    self.assertTrue(len(result) == 5, "max 5: length")
                    self.assertTrue(result[0].key() == (
                        (i * 5) // 10, (i * 5) % 10),
                        "max 5: first e on page")
                coll.set_page(top=10, skip=None, skiptoken=token)
                # This should wind us back to page 2
                result = list(coll.iterpage())
                self.assertTrue(len(result) == 5, "max 5: length")
                self.assertTrue(
                    result[4].key() == (0, 9), "max 5: last e on page 2")
                # now add an ordering
                coll.set_orderby(
                    odata.CommonExpression.orderby_from_str(ul("Sum desc")))
                # must have rest the skiptoken
                self.assertTrue(
                    coll.next_skiptoken() is None, "No page set")
                coll.set_page(top=10)
                result = list(coll.iterpage(set_next=True))
                self.assertTrue(
                    result[0].key() == (9, 9),
                    "first page with ordering")
                self.assertTrue(
                    result[1].key() == (8, 9),
                    "first page with ordering (8,9)")
                self.assertTrue(
                    result[2].key() == (9, 8),
                    "first page with ordering (9,8)")
                token = coll.next_skiptoken()
                self.assertTrue(token is not None, "skip token present")
                result = list(coll.iterpage(set_next=True))
                self.assertTrue(
                    result[0].key() == (9, 7),
                    "second page with ordering (9,7)")
                self.assertTrue(
                    result[1].key() == (6, 9),
                    "second page with ordering (9,8)")
                for i in range3(18):
                    logging.info("$skiptoken=%s", coll.next_skiptoken())
                    result = list(coll.iterpage(set_next=True))
                self.assertTrue(
                    result[2].key() == (0, 1),
                    "last page with ordering (0,1)")
                self.assertTrue(
                    result[3].key() == (1, 0),
                    "last page with ordering (1,0)")
                self.assertTrue(
                    result[4].key() == (0, 0),
                    "last page with ordering (0,0)")
            except NotImplementedError:
                pass

    def runtest_nav_o2o(self):
        ones = self.ds['RegressionModel.RegressionContainer.O2Os']
        onexs = self.ds['RegressionModel.RegressionContainer.O2OXs']
        with ones.open() as coll:
            with onexs.open() as coll_x:
                e = coll.new_entity()
                e['K'].set_from_value(1)
                e['Data'].set_from_value('NavigationOne')
                # CREATE
                try:
                    coll.insert_entity(e)
                    self.fail("e inserted without 1-1 relationship")
                except edm.ConstraintError:
                    pass
                e_x = coll_x.new_entity()
                e_x['K'].set_from_value(100)
                e_x['Data'].set_from_value('NavigationOneX')
                e['OX'].bind_entity(e_x)
                try:
                    coll.insert_entity(e)
                except edm.ConstraintError:
                    self.fail("e insert failed with 1-1 binding")
                # Repeat but in reverse to check symmetry
                e2 = coll.new_entity()
                e2['K'].set_from_value(2)
                e2['Data'].set_from_value('NavigationTwo')
                e2_x = coll_x.new_entity()
                e2_x['K'].set_from_value(200)
                e2_x['Data'].set_from_value('NavigationTwoX')
                e2_x['O'].bind_entity(e2)
                coll_x.insert_entity(e2_x)
                # READ both ways
                e = coll[1]
                nav_x = e['OX'].get_entity()
                self.assertTrue(
                    nav_x is not None, "Failed to read back navigation link")
                self.assertTrue(nav_x['K'] == 100)
                nav = nav_x['O'].get_entity()
                self.assertFalse(
                    nav is None, "Failed to read back reverse navigation link")
                self.assertTrue(nav['K'] == 1)
                # READ with deep filter
                filter = odata.CommonExpression.from_str(
                    "OX/Data eq 'NavigationOneX'")
                coll.set_filter(filter)
                self.assertTrue(1 in coll)
                self.assertFalse(2 in coll)
                coll.set_filter(None)
                # READ with deep 'back' filter
                with e['OX'].open() as navCollection:
                    filter = odata.CommonExpression.from_str(
                        "O/Data eq 'NavigationOne'")
                    navCollection.set_filter(filter)
                    self.assertTrue(100 in navCollection)
                    self.assertFalse(200 in navCollection)
                # UPDATE - by adding a link, should fail.  Requires a
                # deep delete.
                try:
                    with e['OX'].open() as navCollection:
                        navCollection[200] = e2_x
                    self.fail("Nav coll __setitem__ should have failed "
                              "for 1-1 relationship")
                except edm.ConstraintError:
                    pass
                # UPDATE - using bind and update - also should fail for
                # 1-1 link
                e['OX'].bind_entity(e2_x)
                try:
                    e.commit()
                    self.fail("bind_entity/commit should have failed "
                              "for 1-1 relationship")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                with e['OX'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[100]
                        self.fail("Delete of link in a 1-1 relationship")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a 1-1 link it should fail or cascade the
                # delete
                try:
                    del coll[1]
                    self.assertFalse(
                        1 in coll, "Delete with a 1-1 relationship")
                    self.assertFalse(
                        100 in coll_x, "Cascade delete for 1-1 relationship")
                except edm.ConstraintError:
                    # an error is acceptable here, though we generate a
                    # warning
                    logging.warning(
                        "entities with a 1-1 relationship cannot be deleted")
                    self.assertTrue(
                        1 in coll, "Delete with a 1-1 relationship")
                    self.assertTrue(
                        100 in coll_x, "Cascade delete for 1-1 relationship")

    def runtest_nav_o2o_1(self):
        ones = self.ds['RegressionModel.RegressionContainer.O2O1s']
        onexs = self.ds['RegressionModel.RegressionContainer.O2OX1s']
        with ones.open() as coll:
            with onexs.open() as coll_x:
                e = coll.new_entity()
                e['K'].set_from_value(1)
                e['Data'].set_from_value('NavigationOne')
                # CREATE
                try:
                    coll.insert_entity(e)
                    self.fail("e inserted without 1-1 relationship")
                except edm.ConstraintError:
                    pass
                e_x = coll_x.new_entity()
                e_x['K'].set_from_value(100)
                e_x['Data'].set_from_value('NavigationOneX')
                e['OX'].bind_entity(e_x)
                try:
                    coll.insert_entity(e)
                except edm.ConstraintError:
                    self.fail("e insert failed with 1-1 binding")
                # Repeat but in reverse to check that we can't insert into a
                # dependent e set without the principal leading
                e2 = coll.new_entity()
                e2['K'].set_from_value(2)
                e2['Data'].set_from_value('NavigationTwo')
                e2_x = coll_x.new_entity()
                e2_x['K'].set_from_value(200)
                e2_x['Data'].set_from_value('NavigationTwoX')
                try:
                    coll_x.insert_entity(e2_x)
                    self.fail(
                        "e insert should fail with unbound 1-1 relationship")
                except edm.ConstraintError:
                    pass
                e2['OX'].bind_entity(e2_x)
                coll.insert_entity(e2)
                # READ the link
                e = coll[1]
                nav_x = e['OX'].get_entity()
                self.assertTrue(
                    nav_x is not None, "Failed to read back navigation link")
                self.assertTrue(nav_x['K'] == 100)
                # READ with deep filter
                filter = odata.CommonExpression.from_str(
                    "OX/Data eq 'NavigationOneX'")
                coll.set_filter(filter)
                self.assertTrue(1 in coll)
                self.assertFalse(2 in coll)
                coll.set_filter(None)
                # UPDATE - by adding a link, should fail.  Requires a
                # deep delete.
                e2_x = coll_x[200]
                try:
                    with e['OX'].open() as navCollection:
                        navCollection[200] = e2_x
                    self.fail("Nav coll __setitem__ should have failed "
                              "for 1-1 relationship")
                except edm.ConstraintError:
                    pass
                # UPDATE - using bind and update - also should fail for
                # 1-1 link
                e['OX'].bind_entity(e2_x)
                try:
                    e.commit()
                    self.fail("bind_entity/commit should have failed "
                              "for 1-1 relationship")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                with e['OX'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[100]
                        self.fail("Delete of link in a 1-1 relationship")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a 1-1 link it should fail or cascade the
                # delete
                try:
                    # with no navigation property we mustn't cascade the
                    # delete (I'm making up my own rules here)
                    del coll_x[100]
                    self.fail(
                        "Deletion should fail for unbound 1-1 relationship")
                except edm.ConstraintError:
                    pass
                try:
                    del coll[1]
                    self.assertFalse(
                        1 in coll, "Delete with a 1-1 relationship")
                    self.assertFalse(
                        100 in coll_x, "Cascade delete for 1-1 relationship")
                except edm.ConstraintError:
                    # an error is acceptable here, though we generate a warning
                    logging.warning(
                        "entities with a 1-1 relationship cannot be deleted.")
                    self.assertTrue(
                        1 in coll, "Delete with a 1-1 relationship")
                    self.assertTrue(
                        100 in coll_x, "Cascade delete for 1-1 relationship")

    def runtest_nav_zo2o(self):
        zeroones = self.ds['RegressionModel.RegressionContainer.ZO2Os']
        ones = self.ds['RegressionModel.RegressionContainer.ZO2OXs']
        with zeroones.open() as collectionZO:
            with ones.open() as collectionO:
                e_zo = collectionZO.new_entity()
                e_zo['K'].set_from_value(1)
                e_zo['Data'].set_from_value('NavigationZeroOne')
                # CREATE
                try:
                    collectionZO.insert_entity(e_zo)
                    self.fail("e inserted without 0..1-1 relationship")
                except edm.ConstraintError:
                    pass
                e_o = collectionO.new_entity()
                e_o['K'].set_from_value(100)
                e_o['Data'].set_from_value('NavigationOne')
                e_zo['O'].bind_entity(e_o)
                try:
                    collectionZO.insert_entity(e_zo)
                except edm.ConstraintError:
                    self.fail("e insert failed with 0..1-1 binding")
                e_o = collectionO[100]
                # e_zo <-> e_o
                # Repeat but in reverse to check symmetry
                e_zo2 = collectionZO.new_entity()
                e_zo2['K'].set_from_value(2)
                e_zo2['Data'].set_from_value('NavigationZeroOne_2')
                e_o2 = collectionO.new_entity()
                e_o2['K'].set_from_value(200)
                e_o2['Data'].set_from_value('NavigationOne_2')
                e_o2['ZO'].bind_entity(e_zo2)
                collectionO.insert_entity(e_o2)
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                # Now try inserting at the 1 end without a binding
                e_o3 = collectionO.new_entity()
                e_o3['K'].set_from_value(300)
                e_o3['Data'].set_from_value('NavigationOne_3')
                try:
                    collectionO.insert_entity(e_o3)
                except edm.ConstraintError:
                    self.fail("Unbound e insert failed at the 1 end "
                              "of 0..1-1 link")
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                # None <-> e_o3
                # Insert with implicit link
                e_o4 = collectionO.new_entity()
                e_o4['K'].set_from_value(400)
                e_o4['Data'].set_from_value('NavigationOne_4')
                with e_zo['O'].open() as navCollection:
                    # 	we can't insert here as e_zo is already bound to e_o
                    try:
                        navCollection.insert_entity(e_o4)
                        self.fail("insert_entity on navigation coll "
                                  "should fail towards the 1 end")
                    except edm.ConstraintError:
                        pass
                # just create e_o4 anyway
                e_o4 = collectionO.new_entity()
                e_o4['K'].set_from_value(400)
                e_o4['Data'].set_from_value('NavigationOne_4')
                try:
                    collectionO.insert_entity(e_o4)
                except edm.ConstraintError:
                    # non-transactional warning, the e was created but
                    # not linked during previous attempt
                    logging.warn("Non-transactional behaviour detected after "
                                 "failed insert on 0..1 to 1 navigation "
                                 "coll")
                    e_o4 = collectionO[400]
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                # None <-> e_o3
                # None <-> e_o4
                e_zo3 = collectionZO.new_entity()
                e_zo3['K'].set_from_value(3)
                e_zo3['Data'].set_from_value('NavigationZeroOne_3')
                with e_o3['ZO'].open() as navCollection:
                    # we can insert here, will create a bound relationship
                    try:
                        navCollection.insert_entity(e_zo3)
                    except edm.ConstraintError:
                        self.fail("insert_entity on navigation coll "
                                  "should not fail towards the 0..1 end")
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                # e_zo3 <-> e_o3
                # None <-> e_o4
                # READ both ways
                e_zo = collectionZO[1]
                nav_o = e_zo['O'].get_entity()
                self.assertTrue(
                    nav_o is not None, "Failed to read back navigation link")
                self.assertTrue(nav_o['K'] == 100)
                nav_zo = nav_o['ZO'].get_entity()
                self.assertFalse(
                    nav_zo is None,
                    "Failed to read back reverse navigation link")
                self.assertTrue(nav_zo['K'] == 1)
                # READ with deep filter both ways
                filter = odata.CommonExpression.from_str(
                    "O/Data eq 'NavigationOne'")
                collectionZO.set_filter(filter)
                self.assertTrue(1 in collectionZO)
                self.assertFalse(2 in collectionZO)
                collectionZO.set_filter(None)
                filter = odata.CommonExpression.from_str(
                    "ZO/Data eq 'NavigationZeroOne'")
                collectionO.set_filter(filter)
                self.assertTrue(100 in collectionO)
                self.assertFalse(200 in collectionO)
                collectionO.set_filter(None)
                # UPDATE - by replacing the required target of a link,
                # should work
                try:
                    with e_zo['O'].open() as navCollection:
                        navCollection.replace(e_o4)
                except edm.ConstraintError:
                    self.fail("replace on 0..1-1 navigation property")
                # e_zo <-> e_o4
                # e_zo2 <-> e_o2
                # e_zo3 <-> e_o3
                # None <-> e_o
                nav_zo = e_o4['ZO'].get_entity()
                self.assertTrue(nav_zo['K'] == 1)
                nav_zo = e_o['ZO'].get_entity()
                self.assertTrue(nav_zo is None)
                # now the other way around, should fail as e_zo is
                # already bound to a different e (and even if we
                # allowed it, we'd have to break the link to e_zo2
                # which is illegal without deletion).
                try:
                    with e_o2['ZO'].open() as navCollection:
                        navCollection[e_zo.key()] = e_zo
                    self.fail(
                        "__setitem__ on 1-0..1 navigation property "
                        "should fail")
                except edm.ConstraintError:
                    pass
                # UPDATE - using bind and update
                e_zo['O'].bind_entity(e_o)
                try:
                    e_zo.commit()
                except edm.ConstraintError:
                    self.fail(
                        "bind_entity/commit on 0..1-1 navigation property")
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                # e_zo3 <-> e_o3
                # None <-> e_o4
                e_o2['ZO'].bind_entity(e_zo)
                try:
                    e_o2.commit()
                    self.fail("bind_entity/commit on 1-0..1 navigation "
                              "property should fail")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                with e_o['ZO'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[1]
                        self.fail(
                            "Delete of link in a 0..1-1 relationship "
                            "from 1 end")
                    except edm.ConstraintError:
                        pass
                with e_zo['O'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[100]
                        self.fail("Delete of link in a 0..1-1 relationship "
                                  "from the 0..1 end")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a 0..1-1 link should succeed on the 0..1 end
                try:
                    del collectionZO[1]
                    self.assertFalse(
                        1 in collectionZO,
                        "Delete e at 0..1 end of relationship")
                    self.assertTrue(
                        100 in collectionO,
                        "No cascade delete expected for 0..1-1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at 0..1 end of relationship")
                # None <-> e_o
                # e_zo2 <-> e_o2
                # e_zo3 <-> e_o3
                # None <-> e_o4
                # DELETE - e; for a 0..1-1 link should fail or cascade the
                # delete on the 1 end
                try:
                    del collectionO[200]
                    self.assertFalse(
                        200 in collectionO,
                        "Delete e at 1 end of relationship")
                    self.assertFalse(
                        2 in collectionZO,
                        "Cascade delete required for 0..1 end of relationship")
                except edm.ConstraintError:
                    # an error is acceptable here, though we generate a
                    # warning
                    logging.warning(
                        "no cascade delete across 0..1-1 relationship")
                    self.assertTrue(200 in collectionO)
                    self.assertTrue(2 in collectionZO)

    def runtest_nav_zo2o_f(self):
        zeroones = self.ds['RegressionModel.RegressionContainer.ZO2OFs']
        ones = self.ds['RegressionModel.RegressionContainer.ZO2OXFs']
        with zeroones.open() as collectionZO:
            with ones.open() as collectionO:
                # CREATE
                e_zo = collectionZO.new_entity()
                e_zo['K'].set_from_value(1)
                e_zo['Data'].set_from_value('NavigationZeroOne')
                e_o = collectionO.new_entity()
                e_o['K'].set_from_value(100)
                e_o['Data'].set_from_value('NavigationOne')
                e_zo['O'].bind_entity(e_o)
                try:
                    collectionZO.insert_entity(e_zo)
                except edm.ConstraintError:
                    self.fail("e insert failed with 0..1-1 binding")
                # e_zo <-> e_o
                e_o2 = collectionO.new_entity()
                e_o2['K'].set_from_value(200)
                e_o2['Data'].set_from_value('NavigationOne_2')
                collectionO.insert_entity(e_o2)
                # None <-> e_o2
                # READ (forward only)
                e_zo = collectionZO[1]
                e_o = collectionO[100]
                nav_o = e_zo['O'].get_entity()
                self.assertTrue(
                    nav_o is not None, "Failed to read back navigation link")
                self.assertTrue(nav_o['K'] == 100)
                # UPDATE - by replacing the required target of a link,
                # should work
                try:
                    with e_zo['O'].open() as navCollection:
                        navCollection.replace(e_o2)
                except edm.ConstraintError:
                    self.fail("replace on 0..1-1 navigation property")
                # e_zo <-> e_o2
                # None <-> e_o
                # UPDATE - using bind and update
                e_zo['O'].bind_entity(e_o)
                try:
                    e_zo.commit()
                except edm.ConstraintError:
                    self.fail(
                        "bind_entity/commit on 0..1-1 navigation property")
                # e_zo <-> e_o
                # None <-> e_o2
                # DELETE - link
                with e_zo['O'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[100]
                        self.fail("Delete of link in a 0..1-1 relationship "
                                  "from the 0..1 end")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a 0..1-1 link should succeed on the 0..1 end
                # e_zo <-> e_o
                try:
                    del collectionZO[1]
                    self.assertFalse(
                        1 in collectionZO,
                        "Delete e at 0..1 end of relationship")
                    self.assertTrue(
                        100 in collectionO,
                        "No cascade delete expected for 0..1-1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at 0..1 end of relationship")
                # DELETE - e; for a 0..1-1 link should fail on the 1 end
                # when there is no navigation to cascade over
                # None <-> e_o
                # None <-> e_o2
                e_zo2 = collectionZO.new_entity()
                e_zo2['K'].set_from_value(2)
                e_zo2['Data'].set_from_value('NavigationZeroOne_2')
                e_zo2['O'].bind_entity(e_o2)
                collectionZO.insert_entity(e_zo2)
                # e_zo2 <-> e_o2
                try:
                    del collectionO[200]
                    self.fail("(Cascade) delete not allowed over unbound "
                              "navigation property")
                except edm.ConstraintError:
                    self.assertTrue(200 in collectionO)
                    self.assertTrue(2 in collectionZO)

    def runtest_nav_zo2o_b(self):
        zeroones = self.ds['RegressionModel.RegressionContainer.ZO2ORs']
        ones = self.ds['RegressionModel.RegressionContainer.ZO2OXRs']
        with zeroones.open() as collectionZO:
            with ones.open() as collectionO:
                e_zo = collectionZO.new_entity()
                e_zo['K'].set_from_value(1)
                e_zo['Data'].set_from_value('NavigationZeroOne')
                # CREATE
                try:
                    collectionZO.insert_entity(e_zo)
                    self.fail("e inserted without 0..1-1 relationship "
                              "(unbound navigation property)")
                except edm.ConstraintError:
                    pass
                e_o = collectionO.new_entity()
                e_o['K'].set_from_value(100)
                e_o['Data'].set_from_value('NavigationOne')
                e_o['ZO'].bind_entity(e_zo)
                try:
                    collectionO.insert_entity(e_o)
                except edm.ConstraintError:
                    self.fail("e insert failed with 0..1-1 binding")
                # e_zo <-> e_o
                # Now try inserting at the 1 end without a binding
                e_o2 = collectionO.new_entity()
                e_o2['K'].set_from_value(200)
                e_o2['Data'].set_from_value('NavigationOne_2')
                try:
                    collectionO.insert_entity(e_o2)
                except edm.ConstraintError:
                    self.fail("Unbound e insert failed at the 1 end "
                              "of 0..1-1 link")
                # None <-> e_o2
                # READ (reverse only)
                e_o = collectionO[100]
                e_zo = collectionZO[1]
                nav_zo = e_o['ZO'].get_entity()
                self.assertTrue(
                    nav_zo is not None, "Failed to read back navigation link")
                self.assertTrue(nav_zo['K'] == 1)
                # UPDATE - by inserting a new value into the navigation coll
                # should work
                e_zo2 = collectionZO.new_entity()
                e_zo2['K'].set_from_value(2)
                e_zo2['Data'].set_from_value('NavigationZeroOne')
                with e_o2['ZO'].open() as navCollection:
                    try:
                        navCollection.insert_entity(e_zo2)
                    except NotImplementedError:
                        # acceptable to reject this as there is no back link
                        logging.warning(
                            "Insertion into O[2].ZO not supported due "
                            "to absence of back-link")
                    except edm.ConstraintError:
                        self.fail("Failed to insert a new e at the 0..1 end "
                                  "of an empty link")
                nav_zo = e_o2['ZO'].get_entity()
                if nav_zo is None:
                    # Fix up the unimplemented insertion...
                    e_o2 = collectionO.copy_entity(e_o2)
                    del collectionO[200]
                    e_o2.set_key(200)
                    e_o2['ZO'].bind_entity(e_zo2)
                    collectionO.insert_entity(e_o2)
                    nav_zo = e_o2['ZO'].get_entity()
                self.assertTrue(nav_zo['K'] == 2)
                e_zo2 = collectionZO[2]
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                # now try and update the link, should fail as e_zo
                # is already bound and even if we allowed ourselves to
                # implicitly break that link it would leave e_zo2
                # unbound which would require an implicit delete
                try:
                    with e_o2['ZO'].open() as navCollection:
                        navCollection[e_zo.key()] = e_zo
                    self.fail(
                        "__setitem__ on 1-0..1 navigation property "
                        "should fail")
                except edm.ConstraintError:
                    pass
                e_o2['ZO'].bind_entity(e_zo)
                try:
                    e_o2.commit()
                    self.fail("bind_entity/commit on 1-0..1 navigation "
                              "property should fail")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                # e_zo <-> e_o
                # e_zo2 <-> e_o2
                with e_o['ZO'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[1]
                        self.fail(
                            "Delete of link in a 0..1-1 relationship "
                            "from 1 end")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a 0..1-1 link should succeed on
                # the 0..1 end even though there is no navigation
                # property, the link must be broken of course!
                # e_zo <-> e_o
                try:
                    del collectionZO[1]
                    self.assertFalse(
                        1 in collectionZO,
                        "Delete e at 0..1 end of relationship")
                    self.assertTrue(
                        100 in collectionO,
                        "No cascade delete expected for 0..1-1 relationship")
                    self.assertTrue(e_o['ZO'].get_entity() is None,
                                    "Link should have been broken by deletion "
                                    "at 0..1 end")
                except edm.ConstraintError:
                    self.fail("Delete e failed at 0..1 end of relationship")
                # DELETE - e; for a 0..1-1 link should fail or cascade
                # e_zo2 <-> e_o2
                try:
                    del collectionO[200]
                    self.assertFalse(
                        200 in collectionO,
                        "Delete e at 1 end of relationship")
                    self.assertFalse(
                        2 in collectionZO,
                        "Cascade delete required for 0..1 end of relationship")
                except edm.ConstraintError:
                    # an error is acceptable here, though we generate a
                    # warning
                    logging.warning(
                        "no cascade delete across 0..1-1 relationship")
                    self.assertTrue(200 in collectionO)
                    self.assertTrue(2 in collectionZO)

    def runtest_nav_many2o(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2Os']
        ones = self.ds['RegressionModel.RegressionContainer.Many2OXs']
        with manys.open() as collectionMany:
            with ones.open() as collectionO:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany')
                # CREATE
                try:
                    collectionMany.insert_entity(e_many)
                    self.fail("e inserted without *-1 relationship")
                except edm.ConstraintError:
                    pass
                e_o = collectionO.new_entity()
                e_o['K'].set_from_value(100)
                e_o['Data'].set_from_value('NavigationOne')
                e_many['O'].bind_entity(e_o)
                try:
                    collectionMany.insert_entity(e_many)
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                # e_many <-> e_o
                # Repeat but in reverse to check symmetry
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_o2 = collectionO.new_entity()
                e_o2['K'].set_from_value(200)
                e_o2['Data'].set_from_value('NavigationOne_2')
                # we can create more than one link now
                e_o2['Many'].bind_entity(e_many2)
                e_o2['Many'].bind_entity(e_many3)
                collectionO.insert_entity(e_o2)
                # e_many2, e_many3 <-> e_o2
                # Now try inserting at the 1 end without a binding
                e_o3 = collectionO.new_entity()
                e_o3['K'].set_from_value(300)
                e_o3['Data'].set_from_value('NavigationOne_3')
                try:
                    collectionO.insert_entity(e_o3)
                except edm.ConstraintError:
                    self.fail(
                        "Unbound e insert failed at the 1 end of *-1 link")
                # [] <-> e_o3
                # READ both ways
                e_many = collectionMany[1]
                nav_o = e_many['O'].get_entity()
                self.assertTrue(
                    nav_o is not None, "Failed to read back navigation link")
                self.assertTrue(nav_o['K'] == 100)
                try:
                    nav_many = nav_o['Many'].get_entity()
                    self.fail("get_entity should fail on a deferred value "
                              "with multiplicity *")
                except edm.NavigationError:
                    pass
                with nav_o['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 1)
                    nav_many = navCollection[1]
                    self.assertTrue(nav_many['K'] == 1)
                # READ multiple...
                e_many2 = collectionMany[2]
                nav_o = e_many2['O'].get_entity()
                self.assertTrue(nav_o is not None, "Failed to read back Many2")
                self.assertTrue(nav_o['K'] == 200)
                e_many3 = collectionMany[3]
                nav_o = e_many3['O'].get_entity()
                self.assertTrue(nav_o is not None, "Failed to read back Many3")
                self.assertTrue(nav_o['K'] == 200)
                e_o2 = collectionO[200]
                with e_o2['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                    self.assertFalse(1 in navCollection)
                    self.assertTrue(2 in navCollection)
                    self.assertTrue(3 in navCollection)
                # READ empty link...
                with e_o3['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                # UPDATE - by replacing the required target of a link,
                # should work
                try:
                    with e_many['O'].open() as navCollection:
                        navCollection.replace(e_o3)
                except edm.ConstraintError:
                    self.fail("replace on *-1 navigation property")
                # e_many <-> e_o3
                # [] <-> e_o
                with e_o3['Many'].open() as navCollection:
                    self.assertTrue(1 in navCollection)
                e_o = collectionO[100]
                with e_o['Many'].open() as navCollection:
                    self.assertTrue(1 not in navCollection)
                    self.assertTrue(len(navCollection) == 0)
                # now the other way around, should fail as e_many is
                # already bound to a different e and we don't allow
                # that link to be broken implicitly
                # [] <-> e_o
                # e_many2, e_many3 <-> e_o2
                # e_many <-> e_o3
                try:
                    with e_o2['Many'].open() as navCollection:
                        navCollection[e_many.key()] = e_many
                    self.fail(
                        "__setitem__ on 1-* navigation property should fail")
                except edm.ConstraintError:
                    pass
                # UPDATE - using bind and update
                e_many['O'].bind_entity(e_o)
                try:
                    e_many.commit()
                except edm.ConstraintError:
                    self.fail("bind_entity/commit on *-1 navigation property")
                # e_many <-> e_o
                # e_many2, e_many3 <-> e_o2
                # [] <-> e_o3
                e_o2['Many'].bind_entity(e_many)
                try:
                    e_o2.commit()
                    self.fail(
                        "bind_entity/commit on 1-* navigation property "
                        "should fail")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                # e_many <-> e_o
                with e_o['Many'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[1]
                        self.fail(
                            "Delete of link in a *-1 relationship from 1 end")
                    except edm.ConstraintError:
                        pass
                with e_many['O'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[100]
                        self.fail(
                            "Delete of link in a *-1 relationship "
                            "from the * end")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a *-1 link should succeed on the * end
                # e_many <-> e_o
                try:
                    del collectionMany[1]
                    self.assertFalse(
                        1 in collectionMany,
                        "Delete e at * end of relationship")
                    self.assertTrue(
                        100 in collectionO,
                        "No cascade delete expected for *-1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at * end of relationship")
                # DELETE - e; for a *-1 link should fail or cascade
                # e_many2, e_many3 <-> e_o2
                try:
                    del collectionO[200]
                    self.assertFalse(
                        200 in collectionO,
                        "Delete e at 1 end of relationship")
                    self.assertFalse(
                        2 in collectionMany,
                        "Cascade delete required for * end of relationship")
                    self.assertFalse(
                        3 in collectionMany,
                        "Cascade delete required for * end of relationship")
                except edm.ConstraintError:
                    # an error is acceptable here, though we generate a
                    # warning
                    logging.warning(
                        "no cascade delete across *-1 relationship")
                    self.assertTrue(200 in collectionO)
                    self.assertTrue(2 in collectionMany)
                    self.assertTrue(3 in collectionMany)

    def runtest_nav_many2o_f(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2OFs']
        ones = self.ds['RegressionModel.RegressionContainer.Many2OXFs']
        with manys.open() as collectionMany:
            with ones.open() as collectionO:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany')
                # CREATE
                e_o = collectionO.new_entity()
                e_o['K'].set_from_value(100)
                e_o['Data'].set_from_value('NavigationOne')
                e_many['O'].bind_entity(e_o)
                try:
                    collectionMany.insert_entity(e_many)
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                # e_many <-> e_o
                # we can create more than one link now, but must go forward
                e_o2 = collectionO.new_entity()
                e_o2['K'].set_from_value(200)
                e_o2['Data'].set_from_value('NavigationOne_2')
                collectionO.insert_entity(e_o2)
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_many2['O'].bind_entity(e_o2)
                collectionMany.insert_entity(e_many2)
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_many3['O'].bind_entity(e_o2)
                collectionMany.insert_entity(e_many3)
                # e_many2, e_many3 <-> e_o2
                # Now try inserting at the 1 end without a binding
                e_o3 = collectionO.new_entity()
                e_o3['K'].set_from_value(300)
                e_o3['Data'].set_from_value('NavigationOne_3')
                collectionO.insert_entity(e_o3)
                # [] <-> e_o3
                # READ (forward only)
                e_many = collectionMany[1]
                e_o = collectionO[100]
                nav_o = e_many['O'].get_entity()
                self.assertTrue(
                    nav_o is not None, "Failed to read back navigation link")
                self.assertTrue(nav_o['K'] == 100)
                # READ multiple...
                e_many2 = collectionMany[2]
                nav_o = e_many2['O'].get_entity()
                self.assertTrue(nav_o is not None, "Failed to read back Many2")
                self.assertTrue(nav_o['K'] == 200)
                e_many3 = collectionMany[3]
                nav_o = e_many3['O'].get_entity()
                self.assertTrue(nav_o is not None, "Failed to read back Many3")
                self.assertTrue(nav_o['K'] == 200)
                # UPDATE - by replacing the required target of a link,
                # should work
                try:
                    with e_many2['O'].open() as navCollection:
                        navCollection.replace(e_o3)
                except edm.ConstraintError:
                    self.fail("replace on *-1 navigation property")
                # e_many <-> e_o
                # e_many3 <-> e_o2
                # e_many2 <-> e_o3
                self.assertTrue(collectionMany[2]['O'].get_entity().key() ==
                                300)
                # now the other way around, should fail as e_many is
                # already bound to a different e and we don't allow
                # that link to be broken implicitly
                # UPDATE - using bind and update
                e_many2['O'].bind_entity(e_o)
                try:
                    e_many2.commit()
                except edm.ConstraintError:
                    self.fail("bind_entity/commit on *-1 navigation property")
                # e_many, e_many2 <-> e_o
                # e_many3 <-> e_o2
                # [] <-> e_o3
                self.assertTrue(collectionMany[2]['O'].get_entity().key() ==
                                100)
                # DELETE - link
                with e_many3['O'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[200]
                        self.fail(
                            "Delete of link in a *-1 relationship "
                            "from the * end")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a *-1 link should succeed on the * end
                # e_many, e_many2 <-> e_o
                # e_many3 <-> e_o2
                # [] <-> e_o3
                try:
                    del collectionMany[3]
                    self.assertFalse(
                        3 in collectionMany,
                        "Delete e at * end of relationship")
                    self.assertTrue(
                        200 in collectionO,
                        "No cascade delete expected for *-1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at * end of relationship")
                # DELETE - e; for a *-1 link should fail or cascade
                # e_many, e_many2 <-> e_o
                # [] <-> e_o2
                # [] <-> e_o3
                try:
                    del collectionO[100]
                    # with no back link we don't allow cascade deletion
                    self.fail("Cascale delete across *-1 relationship "
                              "(unbound back link)")
                except edm.ConstraintError:
                    self.assertTrue(100 in collectionO)
                    self.assertTrue(1 in collectionMany)
                    self.assertTrue(2 in collectionMany)

    def runtest_nav_many2o_b(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2ORs']
        ones = self.ds['RegressionModel.RegressionContainer.Many2OXRs']
        with manys.open() as collectionMany:
            with ones.open() as collectionO:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany')
                # CREATE
                try:
                    collectionMany.insert_entity(e_many)
                    self.fail("e inserted without *-1 relationship "
                              "(no forward link)")
                except edm.ConstraintError:
                    pass
                e_o = collectionO.new_entity()
                e_o['K'].set_from_value(100)
                e_o['Data'].set_from_value('NavigationOne')
                e_o['Many'].bind_entity(e_many)
                try:
                    collectionO.insert_entity(e_o)
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                # e_many <-> e_o
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_o2 = collectionO.new_entity()
                e_o2['K'].set_from_value(200)
                e_o2['Data'].set_from_value('NavigationOne_2')
                # we can create more than one link now
                e_o2['Many'].bind_entity(e_many2)
                e_o2['Many'].bind_entity(e_many3)
                collectionO.insert_entity(e_o2)
                # e_many2, e_many3 <-> e_o2
                # Now try inserting at the 1 end without a binding
                e_o3 = collectionO.new_entity()
                e_o3['K'].set_from_value(300)
                e_o3['Data'].set_from_value('NavigationOne_3')
                try:
                    collectionO.insert_entity(e_o3)
                except edm.ConstraintError:
                    self.fail(
                        "Unbound e insert failed at the 1 end of *-1 link")
                # [] <-> e_o3
                # READ (reverse link only)
                e_many = collectionMany[1]
                try:
                    nav_many = e_o['Many'].get_entity()
                    self.fail("get_entity should fail on a deferred value "
                              "with multiplicity *")
                except edm.NavigationError:
                    pass
                with e_o['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 1)
                    nav_many = navCollection[1]
                    self.assertTrue(nav_many['K'] == 1)
                # READ multiple...
                e_o2 = collectionO[200]
                with e_o2['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                    self.assertFalse(1 in navCollection)
                    self.assertTrue(2 in navCollection)
                    self.assertTrue(3 in navCollection)
                # READ empty link...
                with e_o3['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                # UPDATE - with e creation
                e_many4 = collectionMany.new_entity()
                e_many4['K'].set_from_value(4)
                e_many4['Data'].set_from_value('NavigationMany_4')
                e_o2['Many'].bind_entity(e_many4)
                collectionO.update_entity(e_o2)
                self.assertTrue(e_many4.exists)
                with e_o2['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 3)
                    self.assertTrue(4 in navCollection)
                # UPDATE - should fail as e_many is already bound to
                # a different e and we don't allow that link to be
                # broken implicitly
                # e_many <-> e_o
                # e_many2, e_many3, e_many4 <-> e_o2
                # [] <-> e_o3
                try:
                    with e_o3['Many'].open() as navCollection:
                        navCollection[e_many.key()] = e_many
                    self.fail(
                        "__setitem__ on 1-* navigation property should fail")
                except edm.ConstraintError:
                    pass
                # UPDATE - using bind and update
                e_o3['Many'].bind_entity(e_many)
                try:
                    e_o3.commit()
                    self.fail(
                        "bind_entity/commit on 1-* navigation property "
                        "should fail")
                except edm.ConstraintError:
                    pass
                # DELETE - link; fails when link is required
                # e_many <-> e_o
                # e_many2, e_many3, e_many4 <-> e_o2
                # [] <-> e_o3
                with e_o['Many'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[1]
                        self.fail(
                            "Delete of link in a *-1 relationship from 1 end")
                    except edm.ConstraintError:
                        pass
                # DELETE - e; for a *-1 link should succeed on the * end
                # e_many <-> e_o
                # e_many2, e_many3, e_many4 <-> e_o2
                # [] <-> e_o3
                try:
                    del collectionMany[1]
                    self.assertFalse(
                        1 in collectionMany,
                        "Delete e at * end of relationship")
                    self.assertTrue(
                        100 in collectionO,
                        "No cascade delete expected for *-1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at * end of relationship")
                # DELETE - e; for a *-1 link should fail or cascade
                # [] <-> e_o
                # e_many2, e_many3, e_many4 <-> e_o2
                # [] <-> e_o3
                try:
                    del collectionO[200]
                    self.assertFalse(
                        200 in collectionO,
                        "Delete e at 1 end of relationship")
                    self.assertFalse(
                        2 in collectionMany,
                        "Cascade delete required for * end of relationship")
                    self.assertFalse(
                        3 in collectionMany,
                        "Cascade delete required for * end of relationship")
                    self.assertFalse(
                        4 in collectionMany,
                        "Cascade delete required for * end of relationship")
                except edm.ConstraintError:
                    # an error is acceptable here, though we generate a
                    # warning
                    logging.warning(
                        "no cascade delete across *-1 relationship")
                    self.assertTrue(200 in collectionO)
                    self.assertTrue(2 in collectionMany)
                    self.assertTrue(3 in collectionMany)
                    self.assertTrue(4 in collectionMany)

    def runtest_nav_many2zo(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2ZOs']
        zeroones = self.ds['RegressionModel.RegressionContainer.Many2ZOXs']
        with manys.open() as collectionMany:
            with zeroones.open() as collectionZO:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany')
                collectionMany.insert_entity(e_many)
                self.assertTrue(1 in collectionMany)
                # e_many <-> None
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_zo = collectionZO.new_entity()
                e_zo['K'].set_from_value(100)
                e_zo['Data'].set_from_value('NavigationOne')
                e_many2['ZO'].bind_entity(e_zo)
                try:
                    collectionMany.insert_entity(e_many2)
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                # e_many <-> None
                # e_many2 <-> e_zo
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_many4 = collectionMany.new_entity()
                e_many4['K'].set_from_value(4)
                e_many4['Data'].set_from_value('NavigationMany_4')
                e_zo2 = collectionZO.new_entity()
                e_zo2['K'].set_from_value(200)
                e_zo2['Data'].set_from_value('NavigationOne_2')
                # we can create more than one link now
                e_zo2['Many'].bind_entity(e_many3)
                e_zo2['Many'].bind_entity(e_many4)
                collectionZO.insert_entity(e_zo2)
                # e_many <-> None
                # e_many2 <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # Now try inserting at the 1 end without a binding
                e_zo3 = collectionZO.new_entity()
                e_zo3['K'].set_from_value(300)
                e_zo3['Data'].set_from_value('NavigationOne_3')
                try:
                    collectionZO.insert_entity(e_zo3)
                except edm.ConstraintError:
                    self.fail(
                        "Unbound e insert failed at the 1 end of *-1 link")
                # READ both ways
                # e_many <-> None
                # e_many2 <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # [] <-> e_zo3
                self.assertTrue(e_many['ZO'].get_entity() is None)
                e_many2 = collectionMany[2]
                nav_zo = e_many2['ZO'].get_entity()
                self.assertTrue(
                    nav_zo is not None, "Failed to read back navigation link")
                self.assertTrue(nav_zo['K'] == 100)
                try:
                    nav_zo['Many'].get_entity()
                    self.fail("get_entity should fail on a deferred value "
                              "with multiplicity *")
                except edm.NavigationError:
                    pass
                with nav_zo['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 1)
                    self.assertTrue(2 in navCollection)
                # READ multiple...
                # e_many <-> None
                # e_many2 <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # [] <-> e_zo3
                e_many3 = collectionMany[3]
                e_zo = collectionZO[100]
                nav_zo = e_many3['ZO'].get_entity()
                self.assertTrue(nav_zo is not None,
                                "Failed to read back Many3")
                self.assertTrue(nav_zo['K'] == 200)
                e_many4 = collectionMany[4]
                nav_zo = e_many4['ZO'].get_entity()
                self.assertTrue(nav_zo is not None,
                                "Failed to read back Many4")
                self.assertTrue(nav_zo['K'] == 200)
                e_zo2 = collectionZO[200]
                with e_zo2['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                    self.assertFalse(1 in navCollection)
                    self.assertFalse(2 in navCollection)
                    self.assertTrue(3 in navCollection)
                    self.assertTrue(4 in navCollection)
                # READ empty link...
                with e_zo3['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                # UPDATE - by replacing the target of a 0..1 link, should work
                # e_many <-> None
                # e_many2 <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # [] <-> e_zo3
                try:
                    with e_many2['ZO'].open() as navCollection:
                        navCollection.replace(e_zo3)
                except edm.ConstraintError:
                    self.fail("replace on *-0..1 navigation property")
                # e_many <-> None
                # [] <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # e_many2 <-> e_zo3
                with e_zo3['Many'].open() as navCollection:
                    self.assertTrue(2 in navCollection)
                with e_zo['Many'].open() as navCollection:
                    self.assertTrue(2 not in navCollection)
                    self.assertTrue(len(navCollection) == 0)
                # now the other way around, should fail as e_many is
                # already bound to a different e and we don't allow
                # that link to be broken implicitly
                # e_many <-> None
                # [] <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # e_many2 <-> e_zo3
                try:
                    with e_zo2['Many'].open() as navCollection:
                        navCollection[e_many2.key()] = e_many2
                    self.fail(
                        "__setitem__ on 0..1-* navigation property "
                        "should fail")
                except edm.ConstraintError:
                    pass
                # UPDATE - using bind and update
                e_many2['ZO'].bind_entity(e_zo)
                try:
                    e_many2.commit()
                except edm.ConstraintError:
                    self.fail(
                        "bind_entity/commit on *-0..1 navigation property")
                # e_many <-> None
                # e_many2 <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # [] <-> e_zo3
                e_zo2['Many'].bind_entity(e_many2)
                try:
                    e_zo2.commit()
                    self.fail(
                        "bind_entity/commit on 0..1-* navigation property "
                        "should fail")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                # e_many <-> None
                # e_many2 <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # [] <-> e_zo3
                with e_zo['Many'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[2]
                        self.assertTrue(2 in collectionMany)
                        self.assertTrue(
                            collectionMany[2]['ZO'].get_entity() is None)
                    except edm.ConstraintError:
                        self.fail(
                            "Delete of link in a *-0..1 relationship "
                            "from 1 end")
                # e_many <-> None
                # e_many2 <-> None
                # [] <-> e_zo
                # e_many3, e_many4 <-> e_zo2
                # [] <-> e_zo3
                with e_many3['ZO'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[200]
                        self.assertTrue(200 in collectionZO)
                    except edm.ConstraintError:
                        self.fail("Delete of link in a *-0..1 relationship "
                                  "from the * end")
                # DELETE - e; for a *-0..1 link should succeed on the * end
                # e_many <-> None
                # e_many2 <-> None
                # [] <-> e_zo
                # e_many3 <-> None
                # e_many4 <-> e_zo2
                # [] <-> e_zo3
                e_many['ZO'].bind_entity(e_zo)
                collectionMany.update_entity(e_many)
                e_many2['ZO'].bind_entity(e_zo)
                collectionMany.update_entity(e_many2)
                # e_many, e_many2 <-> e_zo
                # e_many3 <-> None
                # e_many4 <-> e_zo2
                # [] <-> e_zo3
                try:
                    del collectionMany[4]
                    self.assertFalse(
                        4 in collectionMany,
                        "Delete e at * end of relationship")
                    self.assertTrue(
                        200 in collectionZO,
                        "No cascade delete expected for *-0..1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at * end of relationship")
                # DELETE - e; for a *-0..1 link should succeed on the 0..1 end
                # e_many, e_many2 <-> e_zo
                # e_many3 <-> None
                # [] <-> e_zo2
                # [] <-> e_zo3
                try:
                    del collectionZO[100]
                    self.assertFalse(
                        100 in collectionZO,
                        "Delete e at 0..1 end of relationship")
                    self.assertTrue(
                        1 in collectionMany,
                        "Cascade delete not allowed for * end of relationship")
                    self.assertTrue(
                        2 in collectionMany,
                        "Cascade delete not allwoed for * end of relationship")
                except edm.ConstraintError:
                    self.fail("Delete e at the 0..1 end of the relationship")
                # e_many <-> None
                # e_many2 <-> None
                # e_many3 <-> None
                # [] <-> e_zo2
                # [] <-> e_zo3

    def runtest_nav_many2zo_f(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2ZOFs']
        zeroones = self.ds['RegressionModel.RegressionContainer.Many2ZOXFs']
        with manys.open() as collectionMany:
            with zeroones.open() as collectionZO:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany')
                collectionMany.insert_entity(e_many)
                self.assertTrue(1 in collectionMany)
                # e_many <-> None
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_zo = collectionZO.new_entity()
                e_zo['K'].set_from_value(100)
                e_zo['Data'].set_from_value('NavigationOne')
                e_many2['ZO'].bind_entity(e_zo)
                try:
                    collectionMany.insert_entity(e_many2)
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                e_zo = collectionZO[100]
                # e_many <-> None
                # e_many2 <-> e_zo
                # Now try inserting at the 1 end without a binding
                e_zo2 = collectionZO.new_entity()
                e_zo2['K'].set_from_value(200)
                e_zo2['Data'].set_from_value('NavigationOne_2')
                try:
                    collectionZO.insert_entity(e_zo2)
                except edm.ConstraintError:
                    self.fail(
                        "Unbound e insert failed at the 1 end of *-1 link")
                # insert multiple...
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_many3['ZO'].bind_entity(e_zo)
                try:
                    collectionMany.insert_entity(e_many3)
                except edm.ConstraintError:
                    self.fail("e insert failed to update * link")
                # READ (forward only)
                # e_many <-> None
                # e_many2, e_many3 <-> e_zo
                # [] <-> e_zo2
                self.assertTrue(e_many['ZO'].get_entity() is None)
                e_many2 = collectionMany[2]
                nav_zo = e_many2['ZO'].get_entity()
                self.assertTrue(
                    nav_zo is not None, "Failed to read back navigation link")
                self.assertTrue(nav_zo['K'] == 100)
                e_many3 = collectionMany[3]
                nav_zo = e_many3['ZO'].get_entity()
                self.assertTrue(nav_zo is not None,
                                "Failed to read back Many3")
                self.assertTrue(nav_zo['K'] == 100)
                # UPDATE - by replacing the target of a 0..1 link, should work
                # e_many <-> None
                # e_many2, e_many3 <-> e_zo
                # [] <-> e_zo2
                try:
                    with e_many2['ZO'].open() as navCollection:
                        navCollection.replace(e_zo2)
                except edm.ConstraintError:
                    self.fail("replace on *-0..1 navigation property")
                # e_many <-> None
                # e_many3 <-> e_zo
                # e_many2 <-> e_zo2
                # UPDATE - using bind and update
                e_many2['ZO'].bind_entity(e_zo)
                try:
                    e_many2.commit()
                except edm.ConstraintError:
                    self.fail(
                        "bind_entity/commit on *-0..1 navigation property")
                # DELETE - link
                # e_many <-> None
                # e_many2, e_many3 <-> e_zo
                # [] <-> e_zo2
                with e_many3['ZO'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[100]
                        self.assertTrue(100 in collectionZO)
                    except edm.ConstraintError:
                        self.fail("Delete of link in a *-0..1 relationship "
                                  "from the * end")
                # DELETE - e; for a *-1 link should succeed on the * end
                # e_many <-> None
                # e_many2 <-> e_zo
                # [] <-> e_zo2
                # e_many3 <-> None
                e_many['ZO'].bind_entity(e_zo)
                collectionMany.update_entity(e_many)
                e_many3['ZO'].bind_entity(e_zo2)
                collectionMany.update_entity(e_many3)
                # e_many, e_many2 <-> e_zo
                # e_many3 <-> e_zo2
                try:
                    del collectionMany[3]
                    self.assertFalse(
                        3 in collectionMany,
                        "Delete e at * end of relationship")
                    self.assertTrue(
                        200 in collectionZO,
                        "No cascade delete expected for *-0..1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at * end of relationship")
                # DELETE - e; for a *-0..1 link should not cascade
                # e_many, e_many2 <-> e_zo
                # None <-> e_zo2
                try:
                    del collectionZO[100]
                    self.assertFalse(
                        100 in collectionZO,
                        "Delete e at 0..1 end of relationship")
                    self.assertTrue(
                        1 in collectionMany,
                        "Cascade delete not allowed for * end of relationship")
                    self.assertTrue(
                        2 in collectionMany,
                        "Cascade delete not allwoed for * end of relationship")
                except edm.ConstraintError:
                    self.fail("Delete e at the 0..1 end of the relationship")
                # e_many <-> None
                # e_many2 <-> None
                # None <-> e_zo2

    def runtest_nav_many2zo_b(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2ZORs']
        zeroones = self.ds['RegressionModel.RegressionContainer.Many2ZOXRs']
        with manys.open() as collectionMany:
            with zeroones.open() as collectionZO:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany')
                collectionMany.insert_entity(e_many)
                self.assertTrue(1 in collectionMany)
                # e_many <-> None
                e_zo = collectionZO.new_entity()
                e_zo['K'].set_from_value(100)
                e_zo['Data'].set_from_value('NavigationOne')
                collectionZO.insert_entity(e_zo)
                # e_many <-> None
                # [] <-> e_zo
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_zo2 = collectionZO.new_entity()
                e_zo2['K'].set_from_value(200)
                e_zo2['Data'].set_from_value('NavigationOne_2')
                # we can create more than one link now
                e_zo2['Many'].bind_entity(e_many2)
                e_zo2['Many'].bind_entity(e_many3)
                collectionZO.insert_entity(e_zo2)
                e_many2 = collectionMany[2]
                e_many3 = collectionMany[3]
                # e_many <-> None
                # [] <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                # READ (reverse only)
                with e_zo['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                with e_zo2['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                    self.assertTrue(2 in navCollection)
                    self.assertTrue(3 in navCollection)
                # UPDATE - e_many should work, but e_many2 should
                # fail as it is already bound to a different e and
                # we don't allow that link to be broken implicitly
                # e_many <-> None
                # [] <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                with e_zo['Many'].open() as navCollection:
                    try:
                        navCollection[e_many.key()] = e_many
                        self.assertTrue(1 in navCollection)
                    except edm.ConstraintError:
                        self.fail("__setitem__ on 0..1-* navigation property "
                                  "should succeed")
                    try:
                        navCollection[e_many2.key()] = e_many2
                        self.fail("__setitem__ on 0..1-* navigation property "
                                  "should fail (target already linked)")
                    except edm.ConstraintError:
                        pass
                # UPDATE - using bind and update
                # e_many <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                e_zo['Many'].bind_entity(e_many2)
                try:
                    e_zo.commit()
                    self.fail("bind_entity/commit on 0..1-* navigation "
                              "property should fail")
                except edm.ConstraintError:
                    pass
                # DELETE - link
                # e_many <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                with e_zo['Many'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[1]
                        self.assertTrue(1 in collectionMany)
                    except edm.ConstraintError:
                        self.fail(
                            "Delete of link in a *-0..1 relationship "
                            "from 1 end")
                # e_many <-> None
                # [] <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                e_zo = collectionZO[100]
                e_zo['Many'].bind_entity(e_many)
                e_zo.commit()
                # DELETE - e; for a *-0..1 link should succeed on the * end
                # e_many <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                try:
                    del collectionMany[1]
                    self.assertFalse(
                        1 in collectionMany,
                        "Delete e at * end of relationship")
                    self.assertTrue(
                        100 in collectionZO,
                        "No cascade delete expected for *-0..1 relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed at * end of relationship")
                # DELETE - e; for a *-0..1 link should succeed on the 0..1 end
                # None <-> e_zo
                # e_many2, e_many3 <-> e_zo2
                try:
                    del collectionZO[200]
                    self.assertFalse(
                        200 in collectionZO,
                        "Delete e at 0..1 end of relationship")
                    self.assertTrue(
                        2 in collectionMany,
                        "Cascade delete not allowed for * end of relationship")
                    self.assertTrue(
                        3 in collectionMany,
                        "Cascade delete not allwoed for * end of relationship")
                except edm.ConstraintError:
                    self.fail("Delete e at the 0..1 end of the relationship")
                # None <-> e_zo
                # e_many2 <-> None
                # e_many3 <-> None

    def runtest_nav_many2zo_r(self):
        manys2zeroones = self.ds[
            'RegressionModel.RegressionContainer.Many2ZORvs']
        with manys2zeroones.open() as coll:
            e1 = coll.new_entity()
            e1['K'].set_from_value(1)
            e1['Data'].set_from_value('Navigation_1')
            coll.insert_entity(e1)
            self.assertTrue(1 in coll)
            # [] <-> e1 <-> None
            e2 = coll.new_entity()
            e2['K'].set_from_value(2)
            e2['Data'].set_from_value('Navigation_2')
            e3 = coll.new_entity()
            e3['K'].set_from_value(3)
            e3['Data'].set_from_value('Navigation_3')
            e2['ZO'].bind_entity(e3)
            try:
                coll.insert_entity(e2)
                e3 = coll[3]
            except edm.ConstraintError:
                self.fail("e insert failed with *-1 binding")
            # [] <-> e1 <-> None
            # [] <-> e2 <-> e3
            e4 = coll.new_entity()
            e4['K'].set_from_value(4)
            e4['Data'].set_from_value('Navigation_4')
            e5 = coll.new_entity()
            e5['K'].set_from_value(5)
            e5['Data'].set_from_value('Navigation_5')
            # we can create more than one link now
            e4['Many'].bind_entity(e5)
            e4['Many'].bind_entity(e3)
            coll.insert_entity(e4)
            e5 = coll[5]
            # [] <-> e1 <-> None
            # [] <-> e2 <-> e3 <-> e4 <-> None
            # [] <-> e5 ...
            # READ both ways
            self.assertTrue(e1['ZO'].get_entity() is None)
            e2 = coll[2]
            nav_zo = e2['ZO'].get_entity()
            self.assertTrue(
                nav_zo is not None, "Failed to read back navigation link")
            self.assertTrue(nav_zo['K'] == 3)
            try:
                nav_zo['Many'].get_entity()
                self.fail("get_entity should fail on a deferred value "
                          "with multiplicity *")
            except edm.NavigationError:
                pass
            with nav_zo['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 1)
                self.assertTrue(2 in navCollection)
            # READ multiple...
            e3 = coll[3]
            nav_zo = e3['ZO'].get_entity()
            self.assertTrue(nav_zo is not None, "Failed to read back Many3")
            self.assertTrue(nav_zo['K'] == 4)
            e5 = coll[5]
            nav_zo = e5['ZO'].get_entity()
            self.assertTrue(nav_zo is not None, "Failed to read back Many5")
            self.assertTrue(nav_zo['K'] == 4)
            e4 = coll[4]
            with e4['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 2)
                self.assertFalse(1 in navCollection)
                self.assertFalse(2 in navCollection)
                self.assertTrue(3 in navCollection)
                self.assertTrue(5 in navCollection)
            # READ empty link...
            with e2['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 0)
            # UPDATE - by replacing the target of a 0..1 link, should work
            # [] <-> e1 <-> None
            # [] <-> e2 <-> e3 <-> e4 <-> None
            # [] <-> e5 ...
            try:
                with e3['ZO'].open() as navCollection:
                    navCollection.replace(e1)
            except edm.ConstraintError:
                self.fail("replace on *-0..1 navigation property")
            # [] <-> e2 <-> e3 <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            with e1['Many'].open() as navCollection:
                self.assertTrue(3 in navCollection)
            with e4['Many'].open() as navCollection:
                self.assertTrue(3 not in navCollection)
                self.assertTrue(len(navCollection) == 1)
            # now the other way around, should fail when e2 is
            # already bound to a different e and we don't allow
            # that link to be broken implicitly
            try:
                with e5['Many'].open() as navCollection:
                    navCollection[e2.key()] = e2
                self.fail(
                    "__setitem__ on 0..1-* navigation property should fail")
            except edm.ConstraintError:
                pass
            # UPDATE - using bind and update
            e2['ZO'].bind_entity(e4)
            try:
                e2.commit()
            except edm.ConstraintError:
                self.fail("bind_entity/commit on *-0..1 navigation property")
            # [] <-> e3 <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            # [] <-> e2 ...
            e5['Many'].bind_entity(e2)
            try:
                e5.commit()
                self.fail("bind_entity/commit on 0..1-* navigation property "
                          "should fail")
            except edm.ConstraintError:
                pass
            # DELETE - link
            # [] <-> e3 <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            # [] <-> e2 ...
            with e1['Many'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 1)
                    del navCollection[3]
                    self.assertTrue(3 in coll)
                    self.assertTrue(coll[3]['ZO'].get_entity() is None)
                except edm.ConstraintError:
                    self.fail(
                        "Delete of link in a *-0..1 relationship from 1 end")
            # [] <-> e3 <-> None
            # [] <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            # [] <-> e2 ...
            with e2['ZO'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 1)
                    del navCollection[4]
                    self.assertTrue(4 in coll)
                except edm.ConstraintError:
                    self.fail("Delete of link in a *-0..1 relationship "
                              "from the * end")
            # DELETE - e; for a *-0..1 link should succeed on the * end
            # [] <-> e3 <-> None
            # [] <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            # [] <-> e2 <-> None
            e2['ZO'].bind_entity(e4)
            e2.commit()
            e3['ZO'].bind_entity(e4)
            e3.commit()
            # [] <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            # [] <-> e2 ...
            # [] <-> e3 ...
            try:
                del coll[3]
                self.assertFalse(
                    3 in coll, "Delete e at * end of relationship")
                self.assertTrue(
                    4 in coll,
                    "No cascade delete expected for *-0..1 relationship")
            except edm.ConstraintError:
                self.fail("Delete e failed at * end of relationship")
            # DELETE - e; for a *-0..1 link should succeed on the 0..1 end
            # [] <-> e1 <-> None
            # [] <-> e5 <-> e4 <-> None
            # [] <-> e2 ...
            try:
                del coll[4]
                self.assertFalse(
                    4 in coll,
                    "Delete e at 0..1 end of relationship")
                self.assertTrue(
                    5 in coll,
                    "Cascade delete not allowed for * end of relationship")
                self.assertTrue(
                    2 in coll,
                    "Cascade delete not allwoed for * end of relationship")
            except edm.ConstraintError:
                self.fail("Delete e at the 0..1 end of the relationship")
            # [] <-> e1 <-> None
            # [] <-> e5 <-> None
            # [] <-> e2 <-> None

    def runtest_nav_many2zo_rf(self):
        manys2zeroones = self.ds[
            'RegressionModel.RegressionContainer.Many2ZORvFs']
        with manys2zeroones.open() as coll:
            e1 = coll.new_entity()
            e1['K'].set_from_value(1)
            e1['Data'].set_from_value('Navigation_1')
            coll.insert_entity(e1)
            self.assertTrue(1 in coll)
            # [] -> e1 -> None
            e2 = coll.new_entity()
            e2['K'].set_from_value(2)
            e2['Data'].set_from_value('Navigation_2')
            e3 = coll.new_entity()
            e3['K'].set_from_value(3)
            e3['Data'].set_from_value('Navigation_3')
            e4 = coll.new_entity()
            e4['K'].set_from_value(4)
            e4['Data'].set_from_value('Navigation_4')
            e2['ZO'].bind_entity(e3)
            e3['ZO'].bind_entity(e4)
            try:
                coll.insert_entity(e2)
                e3 = coll[3]
                e4 = coll[4]
            except edm.ConstraintError:
                self.fail("e insert failed with deep *-1 binding")
            # [] -> e1 -> None
            # [] -> e2 -> e3 -> e4 -> None
            e5 = coll.new_entity()
            e5['K'].set_from_value(5)
            e5['Data'].set_from_value('Navigation_5')
            e5['ZO'].bind_entity(e4)
            coll.insert_entity(e5)
            # [] -> e1 -> None
            # [] -> e2 -> e3 -> e4 -> None
            # [] -> e5 ...
            # READ (forward only)
            self.assertTrue(e1['ZO'].get_entity() is None)
            e2 = coll[2]
            nav_zo = e2['ZO'].get_entity()
            self.assertTrue(
                nav_zo is not None, "Failed to read back navigation link")
            self.assertTrue(nav_zo['K'] == 3)
            # READ multiple...
            e3 = coll[3]
            nav_zo = e3['ZO'].get_entity()
            self.assertTrue(nav_zo is not None, "Failed to read back Many3")
            self.assertTrue(nav_zo['K'] == 4)
            e5 = coll[5]
            nav_zo = e5['ZO'].get_entity()
            self.assertTrue(nav_zo is not None, "Failed to read back Many5")
            self.assertTrue(nav_zo['K'] == 4)
            # UPDATE - by replacing the target of a 0..1 link, should work
            # [] -> e1 -> None
            # [] -> e2 -> e3 -> e4 -> None
            # [] -> e5 ...
            try:
                with e3['ZO'].open() as navCollection:
                    navCollection.replace(e1)
            except edm.ConstraintError:
                self.fail("replace on *-0..1 navigation property")
            self.assertTrue(e3['ZO'].get_entity().key() == 1)
            # [] -> e2 -> e3 -> e1 -> None
            # [] -> e5 -> e4 -> None
            # UPDATE - using bind and update
            e2['ZO'].bind_entity(e4)
            try:
                e2.commit()
            except edm.ConstraintError:
                self.fail("bind_entity/commit on *-0..1 navigation property")
            # [] -> e3 -> e1 -> None
            # [] -> e5 -> e4 -> None
            # [] -> e2 ...
            # DELETE - link
            with e3['ZO'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 1)
                    del navCollection[1]
                    self.assertTrue(1 in coll)
                    self.assertTrue(coll[3]['ZO'].get_entity() is None)
                except edm.ConstraintError:
                    self.fail(
                        "Delete of link in a *-0..1 relationship from * end")
            # [] -> e3 -> None
            # [] -> e1 -> None
            # [] -> e5 -> e4 -> None
            # [] -> e2 ...
            # DELETE - e; for a *-0..1 link should succeed on the * end
            e3['ZO'].bind_entity(e4)
            e3.commit()
            # [] -> e1 -> None
            # [] -> e5 -> e4 -> None
            # [] -> e2 ...
            # [] -> e3 ...
            try:
                del coll[3]
                self.assertFalse(
                    3 in coll,
                    "Delete e at * end of relationship")
                self.assertTrue(
                    4 in coll,
                    "No cascade delete expected for *-0..1 relationship")
            except edm.ConstraintError:
                self.fail("Delete e failed at * end of relationship")
            # DELETE - e; for a *-0..1 link should succeed on the 0..1 end
            # [] -> e1 -> None
            # [] -> e5 -> e4 -> None
            # [] -> e2 ...
            try:
                del coll[4]
                self.assertFalse(
                    4 in coll,
                    "Delete e at 0..1 end of relationship")
                self.assertTrue(
                    5 in coll,
                    "Cascade delete not allowed for * end of relationship")
                self.assertTrue(
                    2 in coll,
                    "Cascade delete not allwoed for * end of relationship")
            except edm.ConstraintError:
                self.fail("Delete e at the 0..1 end of the relationship")
            # [] -> e1 -> None
            # [] -> e5 -> None
            # [] -> e2 -> None

    def runtest_nav_many2zo_rb(self):
        manys2zeroones = self.ds[
            'RegressionModel.RegressionContainer.Many2ZORvRs']
        with manys2zeroones.open() as coll:
            e1 = coll.new_entity()
            e1['K'].set_from_value(1)
            e1['Data'].set_from_value('Navigation_1')
            coll.insert_entity(e1)
            self.assertTrue(1 in coll)
            # [] <- e1 <- None
            e2 = coll.new_entity()
            e2['K'].set_from_value(2)
            e2['Data'].set_from_value('Navigation_2')
            e3 = coll.new_entity()
            e3['K'].set_from_value(3)
            e3['Data'].set_from_value('Navigation_3')
            e3['Many'].bind_entity(e2)
            try:
                coll.insert_entity(e3)
                e2 = coll[2]
            except edm.ConstraintError:
                self.fail("e insert failed with *-1 binding")
            # [] <- e1 <- None
            # [] <- e2 <- e3
            e4 = coll.new_entity()
            e4['K'].set_from_value(4)
            e4['Data'].set_from_value('Navigation_4')
            e5 = coll.new_entity()
            e5['K'].set_from_value(5)
            e5['Data'].set_from_value('Navigation_5')
            # we can create more than one link now
            e4['Many'].bind_entity(e5)
            e4['Many'].bind_entity(e3)
            coll.insert_entity(e4)
            e5 = coll[5]
            # [] <- e1 <- None
            # [] <- e2 <- e3 <- e4 <- None
            # [] <- e5 ...
            # READ (reverse only)
            e3 = coll[3]
            try:
                e3['Many'].get_entity()
                self.fail("get_entity should fail on a deferred value "
                          "with multiplicity *")
            except edm.NavigationError:
                pass
            with e3['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 1)
                self.assertTrue(2 in navCollection)
            # READ multiple...
            e4 = coll[4]
            with e4['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 2)
                self.assertFalse(1 in navCollection)
                self.assertFalse(2 in navCollection)
                self.assertTrue(3 in navCollection)
                self.assertFalse(4 in navCollection)
                self.assertTrue(5 in navCollection)
            # READ empty link...
            with e2['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 0)
            # UPDATE - by replacing all the targets of a * link, should work
            # [] <- e1 <- None
            # [] <- e2 <- e3 <- e4 <- None
            # [] <- e5 ...
            try:
                with e4['Many'].open() as navCollection:
                    navCollection.replace(e1)
            except edm.ConstraintError:
                self.fail("replace on *-0..1 navigation property")
            # [] <- e1 <- e4 <- None
            # [] <- e2 <- e3 <- None
            # [] <- e5 <- None
            e3 = coll[3]
            with e1['Many'].open() as navCollection:
                navCollection[3] = e3
                self.assertTrue(3 in navCollection)
            # [] <- e2 <- e3 <- e1 <- e4 <- None
            # [] <- e5 <- None
            with e4['Many'].open() as navCollection:
                self.assertTrue(3 not in navCollection)
                self.assertTrue(len(navCollection) == 1)
            # should fail when e2 is already bound to a
            # different e and we don't allow that link to be
            # broken implicitly
            try:
                with e5['Many'].open() as navCollection:
                    navCollection[2] = e2
                self.fail(
                    "__setitem__ on 0..1-* navigation property should fail")
            except edm.ConstraintError:
                pass
            # UPDATE - using bind and update
            # [] <- e2 <- e3 <- e1 <- e4 <- None
            #            [] <- e5 <- None
            with e3['Many'].open() as navCollection:
                navCollection.clear()
            # [] <- e3 <- e1 <- e4 <- None
            # [] <- e5 <- None
            # [] <- e2 <- None
            with e4['Many'].open() as navCollection:
                navCollection.replace(e5)
            e4['Many'].bind_entity(e2)
            try:
                e4.commit()
            except edm.ConstraintError:
                self.fail("bind_entity/commit on *-0..1 navigation property")
            # [] <- e3 <- e1 <- None
            # [] <- e5 <- e4 <- None
            # [] <- e2 <- ...
            e5['Many'].bind_entity(e2)
            try:
                e5.commit()
                self.fail("bind_entity/commit on 0..1-* navigation property "
                          "should fail")
            except edm.ConstraintError:
                pass
            # DELETE - link
            # [] <- e3 <- e1 <- None
            # [] <- e5 <- e4 <- None
            # [] <- e2 ...
            with e1['Many'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 1)
                    del navCollection[3]
                    self.assertTrue(3 in coll)
                except edm.ConstraintError:
                    self.fail(
                        "Delete of link in a *-0..1 relationship from 1 end")
            # [] <- e3 <- None
            # [] <- e1 <- None
            # [] <- e5 <- e4 <- None
            # [] <- e2 ...
            e4['Many'].bind_entity(e3)
            e4.commit()
            # [] <- e1 <- None
            # [] <- e5 <- e4 <- None
            # [] <- e2 ...
            # [] <- e3 ...
            try:
                del coll[3]
                self.assertFalse(
                    3 in coll, "Delete e at * end of relationship")
                self.assertTrue(
                    4 in coll,
                    "No cascade delete expected for *-0..1 relationship")
            except edm.ConstraintError:
                self.fail("Delete e failed at * end of relationship")
            # DELETE - e; for a *-0..1 link should succeed on the 0..1 end
            # [] <- e1 <- None
            # [] <- e5 <- e4 <- None
            # [] <- e2 ...
            try:
                del coll[4]
                self.assertFalse(
                    4 in coll,
                    "Delete e at 0..1 end of relationship")
                self.assertTrue(
                    5 in coll,
                    "Cascade delete not allowed for * end of relationship")
                self.assertTrue(
                    2 in coll,
                    "Cascade delete not allwoed for * end of relationship")
            except edm.ConstraintError:
                self.fail("Delete e at the 0..1 end of the relationship")
            # [] <- e1 <- None
            # [] <- e5 <- None
            # [] <- e2 <- None

    def runtest_nav_many2many(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2Manys']
        manyxs = self.ds['RegressionModel.RegressionContainer.Many2ManyXs']
        with manys.open() as collectionMany:
            with manyxs.open() as collectionManyX:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany_1')
                collectionMany.insert_entity(e_many)
                self.assertTrue(1 in collectionMany)
                # e_many <-> []
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_manyx = collectionManyX.new_entity()
                e_manyx['K'].set_from_value(100)
                e_manyx['Data'].set_from_value('NavigationOne')
                e_many2['ManyX'].bind_entity(e_manyx)
                try:
                    collectionMany.insert_entity(e_many2)
                    e_manyx = collectionManyX[100]
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                # e_many <-> []
                # e_many2 <-> e_manyx
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_many4 = collectionMany.new_entity()
                e_many4['K'].set_from_value(4)
                e_many4['Data'].set_from_value('NavigationMany_4')
                e_manyx2 = collectionManyX.new_entity()
                e_manyx2['K'].set_from_value(200)
                e_manyx2['Data'].set_from_value('NavigationOne_2')
                # we can create more than one link now
                e_manyx2['Many'].bind_entity(e_many3)
                e_manyx2['Many'].bind_entity(e_many4)
                collectionManyX.insert_entity(e_manyx2)
                e_many3 = collectionMany[3]
                # e_many <-> []
                # e_many2 <-> e_manyx
                # e_many3, e_many4 <-> e_manyx2
                # Now try inserting with a binding to an existing e
                e_manyx3 = collectionManyX.new_entity()
                e_manyx3['K'].set_from_value(300)
                e_manyx3['Data'].set_from_value('NavigationOne_3')
                e_manyx3['Many'].bind_entity(e_many2)
                try:
                    collectionManyX.insert_entity(e_manyx3)
                except edm.ConstraintError:
                    self.fail("Unbound e insert failed with existing e")
                # e_many <-> []
                # e_many2 <-> e_manyx, e_manyx3
                # e_many3, e_many4 <-> e_manyx2
                # READ both ways
                try:
                    e_many['ManyX'].get_entity()
                    self.fail("get_entity should fail on a deferred value "
                              "with multiplicity *")
                except edm.NavigationError:
                    pass
                e_many2 = collectionMany[2]
                with e_many2['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                    self.assertTrue(100 in navCollection)
                    self.assertFalse(200 in navCollection)
                    self.assertTrue(300 in navCollection)
                with e_manyx['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 1)
                    self.assertFalse(1 in navCollection)
                    self.assertTrue(2 in navCollection)
                    self.assertFalse(3 in navCollection)
                    self.assertFalse(4 in navCollection)
                # READ empty link...
                with e_many['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                # UPDATE - by replace
                # e_many <-> []
                # e_many2 <-> e_manyx, e_manyx3
                # e_many3, e_many4 <-> e_manyx2
                try:
                    with e_many2['ManyX'].open() as navCollection:
                        navCollection.replace(e_manyx2)
                except edm.ConstraintError:
                    self.fail("replace on *-* navigation property")
                # e_many <-> []
                # [] <-> e_manyx
                # e_many2, e_many3, e_many4 <-> e_manyx2
                # [] <-> e_manyx3
                with e_manyx['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                with e_manyx2['Many'].open() as navCollection:
                    self.assertTrue(1 not in navCollection)
                    self.assertTrue(2 in navCollection)
                    self.assertTrue(3 in navCollection)
                    self.assertTrue(4 in navCollection)
                    self.assertTrue(len(navCollection) == 3)
                with e_manyx3['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                # UPDATE - __setitem__
                # e_many <-> []
                # [] <-> e_manyx
                # e_many2, e_many3, e_many4 <-> e_manyx2
                # [] <-> e_manyx3
                try:
                    with e_many['ManyX'].open() as navCollection:
                        navCollection[e_manyx2.key()] = e_manyx2
                        navCollection[e_manyx.key()] = e_manyx
                        self.assertTrue(len(navCollection) == 2)
                except edm.ConstraintError:
                    self.fail("__setitem__ on *-* navigation property")
                with e_manyx2['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 4)
                    self.assertTrue(1 in navCollection)
                # e_many <-> e_manyx,...
                # e_many, e_many2, e_many3, e_many4 <-> e_manyx2
                # [] <-> e_manyx3
                # UPDATE - using bind and update
                e_many['ManyX'].bind_entity(e_manyx3)
                try:
                    e_many.commit()
                except edm.ConstraintError:
                    self.fail("bind_entity/commit on *-* navigation property")
                # e_many <-> e_manyx, e_manyx2, e_manyx3
                # e_many, e_many2, e_many3, e_many4 <->
                # e_manyx2
                e_manyx3['Many'].bind_entity(e_many3)
                try:
                    e_manyx3.commit()
                except edm.ConstraintError:
                    self.fail("bind_entity/commit on *-* navigation property")
                # e_many  -> e_manyx, e_manyx2, e_manyx3
                # e_many, e_many2, e_many3, e_many4 <- e_manyx2
                # e_many, e_many3 <-  e_manyx3
                with e_manyx3['Many'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                # DELETE - link
                with e_manyx['Many'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 1)
                        del navCollection[1]
                        self.assertTrue(len(navCollection) == 0)
                        self.assertTrue(1 in collectionMany)
                    except edm.ConstraintError:
                        self.fail("Delete of link in a *-* relationship")
                # [] <- e_manyx
                # e_many  -> e_manyx2, e_manyx3
                # e_many, e_many2, e_many3, e_many4 <- e_manyx2
                # e_many, e_many3 <-  e_manyx3
                with e_many['ManyX'].open() as navCollection:
                    try:
                        self.assertTrue(len(navCollection) == 2)
                        del navCollection[300]
                        self.assertTrue(len(navCollection) == 1)
                        self.assertTrue(300 in collectionManyX)
                    except edm.ConstraintError:
                        self.fail("Delete of link in a *-* relationship")
                # [] <- e_manyx
                # e_many, e_many2, e_many3, e_many4 <- e_manyx2
                # e_many3 <-  e_manyx3
                # DELETE - e
                try:
                    del collectionMany[4]
                    self.assertFalse(
                        4 in collectionMany, "Delete e in *-* relationship")
                    self.assertTrue(
                        200 in collectionManyX,
                        "No cascade delete expected for *-* relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed for *-* relationship")
                # DELETE - e with multiple links
                # [] <- e_manyx
                # e_many, e_many2, e_many3 <-  e_manyx2
                # e_many3 <-  e_manyx3
                try:
                    del collectionManyX[200]
                    self.assertFalse(
                        200 in collectionManyX,
                        "Delete e in *-* relationship")
                    self.assertTrue(
                        1 in collectionMany,
                        "Cascade delete not allowed for * end of relationship")
                    self.assertTrue(
                        2 in collectionMany,
                        "Cascade delete not allwoed for * end of relationship")
                    self.assertTrue(
                        3 in collectionMany,
                        "Cascade delete not allwoed for * end of relationship")
                except edm.ConstraintError:
                    self.fail("Delete e for *-* relationship")
                # [] <- e_manyx
                # e_many -> []
                # e_many2 -> []
                # e_many3 <-> e_manyx3

    def runtest_nav_many2many_1(self):
        manys = self.ds['RegressionModel.RegressionContainer.Many2Many1s']
        manyxs = self.ds['RegressionModel.RegressionContainer.Many2ManyX1s']
        with manys.open() as collectionMany:
            with manyxs.open() as collectionManyX:
                e_many = collectionMany.new_entity()
                e_many['K'].set_from_value(1)
                e_many['Data'].set_from_value('NavigationMany_1')
                collectionMany.insert_entity(e_many)
                self.assertTrue(1 in collectionMany)
                # e_many <-> []
                e_many2 = collectionMany.new_entity()
                e_many2['K'].set_from_value(2)
                e_many2['Data'].set_from_value('NavigationMany_2')
                e_manyx = collectionManyX.new_entity()
                e_manyx['K'].set_from_value(100)
                e_manyx['Data'].set_from_value('NavigationOne')
                e_many2['ManyX'].bind_entity(e_manyx)
                try:
                    collectionMany.insert_entity(e_many2)
                    e_manyx = collectionManyX[100]
                except edm.ConstraintError:
                    self.fail("e insert failed with *-1 binding")
                # e_many <-> []
                # e_many2 <-> e_manyx
                e_many3 = collectionMany.new_entity()
                e_many3['K'].set_from_value(3)
                e_many3['Data'].set_from_value('NavigationMany_3')
                e_manyx2 = collectionManyX.new_entity()
                e_manyx2['K'].set_from_value(200)
                e_manyx2['Data'].set_from_value('NavigationOne_2')
                e_manyx3 = collectionManyX.new_entity()
                e_manyx3['K'].set_from_value(300)
                e_manyx3['Data'].set_from_value('NavigationOne_3')
                # we can create more than one link now
                e_many3['ManyX'].bind_entity(e_manyx2)
                e_many3['ManyX'].bind_entity(e_manyx3)
                collectionMany.insert_entity(e_many3)
                e_manyx2 = collectionManyX[200]
                e_manyx3 = collectionManyX[300]
                # e_many  -> []
                # e_many2  -> e_manyx
                # e_many3  -> e_manyx2, e_manyx3
                # Now try inserting with a binding to an existing e
                e_many4 = collectionMany.new_entity()
                e_many4['K'].set_from_value(4)
                e_many4['Data'].set_from_value('NavigationMany_4')
                e_many4['ManyX'].bind_entity(e_manyx2)
                try:
                    collectionMany.insert_entity(e_many4)
                except edm.ConstraintError:
                    self.fail("Unbound e insert failed with existing e")
                # e_many  -> []
                # e_many2  -> e_manyx
                # e_many3  -> e_manyx2, e_manyx3
                # e_many4  -> e_manyx2
                # READ (one way only)
                try:
                    e_many['ManyX'].get_entity()
                    self.fail("get_entity should fail on a deferred value "
                              "with multiplicity *")
                except edm.NavigationError:
                    pass
                e_many3 = collectionMany[3]
                with e_many3['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 2)
                    self.assertTrue(100 not in navCollection)
                    self.assertTrue(200 in navCollection)
                    self.assertTrue(300 in navCollection)
                # READ empty link...
                with e_many['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 0)
                # UPDATE - by replace
                # e_many  -> []
                # e_many2  -> e_manyx
                # e_many3  -> e_manyx2, e_manyx3
                # e_many4  -> e_manyx2
                try:
                    with e_many2['ManyX'].open() as navCollection:
                        navCollection.replace(e_manyx2)
                except edm.ConstraintError:
                    self.fail("replace on *-* navigation property")
                # e_many  -> []
                # e_many2  -> e_manyx2
                # e_many3  -> e_manyx2, e_manyx3
                # e_many4  -> e_manyx2
                for e in (e_many2, e_many3, e_many4):
                    with e['ManyX'].open() as navCollection:
                        self.assertTrue(200 in navCollection)
                        self.assertFalse(100 in navCollection)
                # UPDATE - __setitem__
                try:
                    with e_many['ManyX'].open() as navCollection:
                        navCollection[e_manyx2.key()] = e_manyx2
                        navCollection[e_manyx.key()] = e_manyx
                        self.assertTrue(len(navCollection) == 2)
                except edm.ConstraintError:
                    self.fail("__setitem__ on *-* navigation property")
                # e_many  -> e_manyx, e_manyx2
                # e_many2  -> e_manyx2
                # e_many3  -> e_manyx2, e_manyx3
                # e_many4  -> e_manyx2
                # UPDATE - using bind and update
                e_many['ManyX'].bind_entity(e_manyx3)
                try:
                    e_many.commit()
                except edm.ConstraintError:
                    self.fail("bind_entity/commit on *-* navigation property")
                # e_many  -> e_manyx, e_manyx2, e_manyx3
                # e_many2  -> e_manyx2
                # e_many3  -> e_manyx2, e_manyx3
                # e_many4  -> e_manyx2
                with e_many['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 3)
                # DELETE - link
                with e_many['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 3)
                    try:
                        del navCollection[100]
                        self.assertTrue(len(navCollection) == 2)
                        self.assertTrue(100 in collectionManyX)
                    except edm.ConstraintError:
                        self.fail("Delete of link in a *-* relationship")
                # e_many  -> e_manyx2, e_manyx3
                # e_many2  -> e_manyx2
                # e_many3  -> e_manyx2, e_manyx3
                # e_many4  -> e_manyx2
                # DELETE - e
                try:
                    del collectionMany[4]
                    self.assertFalse(
                        4 in collectionMany, "Delete e in *-* relationship")
                    self.assertTrue(
                        200 in collectionManyX,
                        "No cascade delete expected for *-* relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed for *-* relationship")
                # DELETE - e from unbound end (links just get dropped)
                try:
                    del collectionManyX[200]
                    self.assertFalse(
                        200 in collectionManyX,
                        "Delete e in *-* relationship")
                    self.assertTrue(
                        1 in collectionMany,
                        "No cascade delete expected for *-* relationship")
                    self.assertTrue(
                        2 in collectionMany,
                        "No cascade delete expected for *-* relationship")
                    self.assertTrue(
                        3 in collectionMany,
                        "No cascade delete expected for *-* relationship")
                except edm.ConstraintError:
                    self.fail("Delete e failed for unbound *-* relationship")
                # e_many  -> e_manyx3
                # e_many2  -> []
                # e_many3  -> e_manyx3
                with e_many['ManyX'].open() as navCollection:
                    self.assertTrue(len(navCollection) == 1)
                    navCollection[100] = e_manyx
                # DELETE - e with multiple links
                # e_many  -> e_manyx, e_manyx3
                # e_many2  -> []
                # e_many3  -> e_manyx3
                try:
                    del collectionMany[1]
                    self.assertFalse(
                        1 in collectionMany, "Delete e in *-* relationship")
                    self.assertTrue(
                        100 in collectionManyX,
                        "Cascade delete not allowed for * end of relationship")
                    self.assertTrue(
                        300 in collectionManyX,
                        "Cascade delete not allwoed for * end of relationship")
                except edm.ConstraintError:
                    self.fail("Delete e for *-* relationship")
                # e_many2  -> []
                # e_many3  -> e_manyx3

    def runtest_nav_many2many_r(self):
        manys2manys = self.ds[
            'RegressionModel.RegressionContainer.Many2ManyRvs']
        with manys2manys.open() as coll:
            e1 = coll.new_entity()
            e1['K'].set_from_value(1)
            e1['Data'].set_from_value('Navigation_1')
            coll.insert_entity(e1)
            self.assertTrue(1 in coll)
            # [] <- e1 -> []
            e2 = coll.new_entity()
            e2['K'].set_from_value(2)
            e2['Data'].set_from_value('Navigation_2')
            e3 = coll.new_entity()
            e3['K'].set_from_value(3)
            e3['Data'].set_from_value('Navigation_3')
            e2['ManyX'].bind_entity(e3)
            try:
                coll.insert_entity(e2)
                e3 = coll[3]
            except edm.ConstraintError:
                self.fail("e insert failed with *-* binding")
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2 <- e3 -> []
            e4 = coll.new_entity()
            e4['K'].set_from_value(4)
            e4['Data'].set_from_value('Navigation_4')
            e5 = coll.new_entity()
            e5['K'].set_from_value(5)
            e5['Data'].set_from_value('Navigation_5')
            # we can create more than one link now
            e4['Many'].bind_entity(e5)
            e4['Many'].bind_entity(e3)
            coll.insert_entity(e4)
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2 <- e3 -> e4
            # e3, e5 <- e4 -> []
            # [] <- e5 -> e4
            entity6 = coll.new_entity()
            entity6['K'].set_from_value(6)
            entity6['Data'].set_from_value('Navigation_6')
            entity6['Many'].bind_entity(e3)
            coll.insert_entity(entity6)
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2 <- e3 -> e4, entity6
            # e3, e5 <- e4 -> []
            # [] <- e5 -> e4
            # e3 <- entity6 -> []
            # READ both ways
            try:
                nav_manyx = e1['ManyX'].get_entity()
                self.fail("get_entity should fail on a deferred value "
                          "with multiplicity *")
            except edm.NavigationError:
                pass
            with e1['ManyX'].open() as nav_manyx:
                self.assertTrue(len(nav_manyx) == 0)
            e2 = coll[2]
            with e2['ManyX'].open() as nav_manyx:
                self.assertTrue(len(nav_manyx) == 1)
                self.assertTrue(3 in nav_manyx)
            e3 = coll[3]
            try:
                e3['Many'].get_entity()
                self.fail("get_entity should fail on a deferred value "
                          "with multiplicity *")
            except edm.NavigationError:
                pass
            with e3['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 1)
                self.assertTrue(2 in navCollection)
            # READ multiple...
            with e3['ManyX'].open() as navCollection:
                self.assertTrue(len(navCollection) == 2)
                self.assertTrue(4 in navCollection)
                self.assertTrue(6 in navCollection)
            e5 = coll[5]
            with e5['ManyX'].open() as navCollection:
                self.assertTrue(len(navCollection) == 1)
                self.assertTrue(4 in navCollection)
            e4 = coll[4]
            with e4['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 2)
                self.assertFalse(1 in navCollection)
                self.assertFalse(2 in navCollection)
                self.assertTrue(3 in navCollection)
                self.assertTrue(5 in navCollection)
            # READ empty return link...
            with e2['Many'].open() as navCollection:
                self.assertTrue(len(navCollection) == 0)
            # UPDATE - by replacing the target of a * link, should work
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2 <- e3 -> e4, entity6
            # e3, e5 <- e4 -> []
            # [] <- e5 -> e4
            # e3 <- entity6 -> []
            try:
                with e3['ManyX'].open() as navCollection:
                    navCollection.replace(e1)
            except edm.ConstraintError:
                self.fail("replace on *-* navigation property")
            # e3 <- e1 -> []
            # [] <- e2 -> e3
            # e2 <- e3 -> e1
            # e5 <- e4 -> []
            # [] <- e5 -> e4
            # [] <- entity6 -> []
            with e1['Many'].open() as navCollection:
                self.assertTrue(3 in navCollection)
            with e4['Many'].open() as navCollection:
                self.assertTrue(3 not in navCollection)
                self.assertTrue(len(navCollection) == 1)
            # now the other way around...
            try:
                with e5['Many'].open() as navCollection:
                    navCollection[e2.key()] = e2
            except edm.ConstraintError:
                self.fail("__setitem__ on *-* navigation property should pass")
            # e3 <- e1 -> []
            # [] <- e2 -> e3, e5
            # e2 <- e3 -> e1
            # e5 <- e4 -> []
            # e2 <- e5 -> e4
            # [] <- entity6 -> []
            # UPDATE - using bind and update
            e2['ManyX'].bind_entity(e4)
            try:
                e2.commit()
            except edm.ConstraintError:
                self.fail("bind_entity/commit on *-* navigation property")
            # e3 <- e1 -> []
            # [] <- e2 -> e3, e4, e5
            # e2 <- e3 -> e1
            # e2, e5 <- e4 -> []
            # e2 <- e5 -> e4
            # [] <- entity6 -> []
            e5['Many'].bind_entity(e1)
            try:
                e5.commit()
            except edm.ConstraintError:
                self.fail("bind_entity/commit on *-* navigation property "
                          "should pass")
            # e3 <- e1 -> e5
            # [] <- e2 -> e3, e4, e5
            # e2 <- e3 -> e1
            # e2, e5 <- e4 -> []
            # e1, e2 <- e5 -> e4
            # [] <- entity6 -> []
            # DELETE - link
            with e1['Many'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 1)
                    del navCollection[3]
                    self.assertTrue(3 in coll)
                except edm.ConstraintError:
                    self.fail("Delete of link in a *-* relationship")
            # [] <- e1 -> e5
            # [] <- e2 -> e3, e4, e5
            # e2 <- e3 -> []
            # e2, e5 <- e4 -> []
            # e1, e2 <- e5 -> e4
            # [] <- entity6 -> []
            with e3['ManyX'].open() as navCollection:
                self.assertTrue(len(navCollection) == 0)
            with e2['ManyX'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 3)
                    del navCollection[4]
                    self.assertTrue(4 in coll)
                except edm.ConstraintError:
                    self.fail("Delete of link in a *-* relationship")
            # DELETE - e; for a *-* link should succeed
            # [] <- e1 -> e5
            # [] <- e2 -> e3, e5
            # e2 <- e3 -> []
            # e5 <- e4 -> []
            # e1, e2 <- e5 -> e4
            # [] <- entity6 -> []
            try:
                del coll[3]
                self.assertFalse(
                    3 in coll, "Delete e in * relationship")
                self.assertTrue(
                    4 in coll,
                    "No cascade delete expected for *-* relationship")
            except edm.ConstraintError:
                self.fail("Delete e failed in * relationship")
            # [] <- e1 -> e5
            # [] <- e2 -> e5
            # e5 <- e4 -> []
            # e1, e2 <- e5 -> e4
            # [] <- entity6 -> []
            # DELETE - e; for a *-* link should succeed
            try:
                del coll[5]
                self.assertFalse(
                    5 in coll,
                    "Delete e in * relationship")
                self.assertTrue(
                    4 in coll,
                    "Cascade delete not allowed in * end of relationship")
                self.assertTrue(
                    2 in coll,
                    "Cascade delete not allowed in * end of relationship")
                self.assertTrue(
                    1 in coll,
                    "Cascade delete not allwoed in * end of relationship")
            except edm.ConstraintError:
                self.fail("Delete e in * relationship")
            # [] <- e1 -> []
            # [] <- e2 -> []
            # [] <- e4 -> []
            # [] <- entity6 -> []

    def runtest_nav_many2many_r1(self):
        manys2manys = self.ds[
            'RegressionModel.RegressionContainer.Many2ManyRv1s']
        with manys2manys.open() as coll:
            e1 = coll.new_entity()
            e1['K'].set_from_value(1)
            e1['Data'].set_from_value('Navigation_1')
            coll.insert_entity(e1)
            self.assertTrue(1 in coll)
            # [] <- e1 -> []
            e2 = coll.new_entity()
            e2['K'].set_from_value(2)
            e2['Data'].set_from_value('Navigation_2')
            e3 = coll.new_entity()
            e3['K'].set_from_value(3)
            e3['Data'].set_from_value('Navigation_3')
            e2['ManyX'].bind_entity(e3)
            try:
                coll.insert_entity(e2)
                # refresh e3 to ensure it exists
                e3 = coll[3]
            except edm.ConstraintError:
                self.fail("e insert failed with *-* binding")
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2 <- e3 -> []
            e4 = coll.new_entity()
            e4['K'].set_from_value(4)
            e4['Data'].set_from_value('Navigation_4')
            e5 = coll.new_entity()
            e5['K'].set_from_value(5)
            e5['Data'].set_from_value('Navigation_5')
            # we can create more than one link now
            e4['ManyX'].bind_entity(e5)
            e4['ManyX'].bind_entity(e3)
            coll.insert_entity(e4)
            e5 = coll[5]
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2, e4 <- e3 -> []
            # [] <- e4 -> e3, e5
            # e4 <- e5 -> []
            # READ (one way only)
            try:
                nav_manyx = e1['ManyX'].get_entity()
                self.fail("get_entity should fail on a deferred value "
                          "with multiplicity *")
            except edm.NavigationError:
                pass
            with e1['ManyX'].open() as nav_manyx:
                self.assertTrue(len(nav_manyx) == 0)
            e2 = coll[2]
            with e2['ManyX'].open() as nav_manyx:
                self.assertTrue(len(nav_manyx) == 1)
                self.assertTrue(3 in nav_manyx)
            # READ multiple...
            with e4['ManyX'].open() as navCollection:
                self.assertTrue(len(navCollection) == 2)
                self.assertFalse(1 in navCollection)
                self.assertFalse(2 in navCollection)
                self.assertTrue(3 in navCollection)
                self.assertTrue(5 in navCollection)
            # UPDATE - by replacing the target of a * link, should work
            # [] <- e1 -> []
            # [] <- e2 -> e3
            # e2, e4 <- e3 -> []
            # [] <- e4 -> e3, e5
            # e4 <- e5 -> []
            try:
                with e4['ManyX'].open() as navCollection:
                    navCollection.replace(e1)
            except edm.ConstraintError:
                self.fail("replace on *-* navigation property")
            try:
                with e5['ManyX'].open() as navCollection:
                    navCollection[e2.key()] = e2
            except edm.ConstraintError:
                self.fail("__setitem__ on *-* navigation property should pass")
            # e4 <- e1 -> []
            # e5 <- e2 -> e3
            # e2 <- e3 -> []
            # [] <- e4 -> e1
            # [] <- e5 -> e2
            # UPDATE - using bind and update
            e4['ManyX'].bind_entity(e2)
            try:
                e4.commit()
            except edm.ConstraintError:
                self.fail("bind_entity/commit on *-* navigation property")
            # e4 <- e1 -> []
            # e4, e5 <- e2 -> e3
            # e2 <- e3 -> []
            # [] <- e4 -> e1, e2
            # [] <- e5 -> e2
            # DELETE - link
            with e5['ManyX'].open() as navCollection:
                try:
                    self.assertTrue(len(navCollection) == 1)
                    del navCollection[2]
                    self.assertTrue(2 in coll)
                except edm.ConstraintError:
                    self.fail("Delete of link in a *-* relationship")
            # e4 <- e1 -> []
            # e4 <- e2 -> e3
            # e2 <- e3 -> []
            # [] <- e4 -> e1, e2
            # [] <- e5 -> []
            # DELETE - e; for a *-* link should succeed
            try:
                del coll[3]
                self.assertFalse(
                    3 in coll,
                    "Delete e in * relationship")
                self.assertTrue(
                    2 in coll,
                    "No cascade delete expected for *-* relationship")
            except edm.ConstraintError:
                self.fail("Delete e failed in * relationship")
            # e4 <- e1 -> []
            # e4 <- e2 -> []
            # [] <- e4 -> e1, e2
            # [] <- e5 -> []
            # DELETE - e; for a *-* link should succeed
            try:
                del coll[4]
                self.assertFalse(
                    4 in coll, "Delete e in * relationship")
                self.assertTrue(
                    2 in coll,
                    "Cascade delete not allowed in * end of relationship")
                self.assertTrue(
                    1 in coll,
                    "Cascade delete not allwoed in * end of relationship")
            except edm.ConstraintError:
                self.fail("Delete e in * relationship")
            # [] <- e1 -> []
            # [] <- e2 -> []
            # [] <- e5 -> []

    def runtest_mediaresource(self):
        streams = self.ds[
            'RegressionModel.RegressionContainer.Streams']
        fox = b'The quick brown fox jumped over the lazy dog'
        cafe = ul('I like going to the Caf\xe9').encode('utf-8')
        with streams.open() as coll:
            fin = io.BytesIO(fox)
            e1 = coll.new_stream(fin)
            # successful call results in an entity that exists
            self.assertTrue(e1.exists)
            self.assertTrue(len(coll) == 1)
            fout = io.BytesIO()
            sinfo = coll.read_stream(e1.key(), fout)
            self.assertTrue(isinstance(sinfo, odata.StreamInfo))
            self.assertTrue(fout.getvalue() == fox,
                            "Read back: "+fout.getvalue().decode('latin-1'))
            self.assertTrue(sinfo.type == params.APPLICATION_OCTETSTREAM)
            self.assertTrue(sinfo.size == len(fox))
            self.assertTrue(isinstance(sinfo.modified, iso.TimePoint))
            self.assertTrue(sinfo.md5 == hashlib.md5(fox).digest())
            # now try inserting with additional metadata
            t = iso.TimePoint.from_str('20140614T180000-0400')
            sinfo = odata.StreamInfo(type=params.PLAIN_TEXT,
                                     created=t, modified=t)
            fin.seek(0)
            e2 = coll.new_stream(fin, key='foxy', sinfo=sinfo)
            self.assertTrue(len(coll) == 2)
            self.assertTrue(e2.key() == 'foxy')
            # alternative read form with no stream to copy to
            sinfo = coll.read_stream(e2.key())
            self.assertTrue(sinfo.type == params.PLAIN_TEXT)
            self.assertTrue(sinfo.size == len(fox))
            self.assertTrue(sinfo.modified == t)
            self.assertTrue(sinfo.created == t)
            # we can update a stream by using an existing key
            fin = io.BytesIO(cafe + fox)
            sinfo = odata.StreamInfo(type=params.PLAIN_TEXT,
                                     size=len(cafe))
            # the size prevents reading to the end of the stream
            coll.update_stream(fin, key='foxy', sinfo=sinfo)
            sinfo = coll.read_stream('foxy')
            self.assertTrue(sinfo.type == params.PLAIN_TEXT)
            self.assertTrue(sinfo.size == len(cafe))
            self.assertTrue(sinfo.md5 == hashlib.md5(cafe).digest())
        # finally, we test the combined read and close method
        # although the collection's close method is called
        # the close is deferred until the generator completes
        # or is destroyed
        coll = streams.open()
        sinfo, sgen = coll.read_stream_close('foxy')
        self.assertTrue(sinfo.type == params.PLAIN_TEXT)
        self.assertTrue(sinfo.size == len(cafe))
        count = 0
        for data in sgen:
            count += len(data)
        self.assertTrue(count == sinfo.size)
        # the collection should now be closed!
        with streams.open() as coll:
            # now some negative tests
            e = coll.new_entity()
            e['slug'].set_from_value('quick_fox')
            e['title'].set_from_value('The quick fox')
            coll.insert_entity(e)
            # the result should be an entity that exists...
            self.assertTrue(e.exists)
            # ...and has an empty stream
            sinfo = coll.read_stream(e.key())
            self.assertTrue(sinfo.type == params.APPLICATION_OCTETSTREAM,
                            str(sinfo.type))
            self.assertTrue(sinfo.size == 0)
            # but it should have our requested title
            e2 = coll[e.key()]
            self.assertTrue(e2['title'].value == 'The quick fox')

    def runtest_composite_slug(self):
        streams = self.ds[
            'RegressionModel.RegressionContainer.XYStreams']
        fox = b'The quick brown fox jumped over the lazy dog'
        cafe = ul('I like going to the Caf\xe9').encode('utf-8')
        with streams.open() as coll:
            fin = io.BytesIO(fox)
            e1 = coll.new_stream(fin)
            # successful call results in an entity that exists
            self.assertTrue(e1.exists)
            self.assertTrue(len(coll) == 1)
            fout = io.BytesIO()
            sinfo = coll.read_stream(e1.key(), fout)
            self.assertTrue(isinstance(sinfo, odata.StreamInfo))
            self.assertTrue(fout.getvalue() == fox,
                            "Read back: "+fout.getvalue().decode('latin-1'))
            self.assertTrue(sinfo.type == params.APPLICATION_OCTETSTREAM)
            self.assertTrue(sinfo.size == len(fox))
            self.assertTrue(isinstance(sinfo.modified, iso.TimePoint))
            self.assertTrue(sinfo.md5 == hashlib.md5(fox).digest())
            # now try inserting with complex key
            fah = (3, 'Fox & Hounds')
            fin.seek(0)
            e2 = coll.new_stream(fin, key=fah)
            self.assertTrue(len(coll) == 2)
            self.assertTrue(e2.key() == fah)
            # alternative read form with no stream to copy to
            sinfo = coll.read_stream(e2.key())
            # we can update a stream by using an existing key
            fin = io.BytesIO(cafe + fox)
            sinfo = odata.StreamInfo(type=params.PLAIN_TEXT,
                                     size=len(cafe))
            # the size prevents reading to the end of the stream
            coll.update_stream(fin, key=fah, sinfo=sinfo)
            sinfo = coll.read_stream(fah)
            self.assertTrue(sinfo.type == params.PLAIN_TEXT)
            self.assertTrue(sinfo.size == len(cafe))
            self.assertTrue(sinfo.md5 == hashlib.md5(cafe).digest())

    def run_combined(self):
        """Runs all individual tests combined into one

        Useful for expensive setUp/tearDown"""
        self.runtest_autokey()
        self.runtest_mediaresource()
        self.runtest_composite_slug()
        self.runtest_all_types()
        self.runtest_all_type_defaults()
        self.runtest_complex_types()
        self.runtest_only_key()
        self.runtest_compound_key()
        self.runtest_simple_select()
        self.runtest_paging()
        self.runtest_nav_o2o()
        self.runtest_nav_o2o_1()
        self.runtest_nav_zo2o()
        self.runtest_nav_zo2o_f()
        self.runtest_nav_zo2o_b()
        self.runtest_nav_many2o()
        self.runtest_nav_many2o_f()
        self.runtest_nav_many2o_b()
        self.runtest_nav_many2zo()
        self.runtest_nav_many2zo_f()
        self.runtest_nav_many2zo_b()
        self.runtest_nav_many2zo_r()
        self.runtest_nav_many2zo_rf()
        self.runtest_nav_many2zo_rb()
        self.runtest_nav_many2many()
        self.runtest_nav_many2many_1()
        self.runtest_nav_many2many_r()
        self.runtest_nav_many2many_r1()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
