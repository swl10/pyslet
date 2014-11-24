#! /usr/bin/env python
"""OData core elements"""

import string
import itertools
import json
import base64
import decimal
import uuid
import math
import warnings
import io
from types import *

from pyslet.unicode5 import CharClass, DetectEncoding
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2396 as uri
import pyslet.http.grammar as grammar
import pyslet.http.params as params
import pyslet.http.messages as messages
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.iso8601 as iso

import csdl as edm


# : namespace for metadata, e.g., the property type attribute
ODATA_METADATA_NAMESPACE = "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"

IS_DEFAULT_ENTITY_CONTAINER = (
    ODATA_METADATA_NAMESPACE, u"IsDefaultEntityContainer")

MIME_TYPE = (ODATA_METADATA_NAMESPACE, u"MimeType")

HttpMethod = (ODATA_METADATA_NAMESPACE, u"HttpMethod")

HAS_STREAM = (ODATA_METADATA_NAMESPACE, u"HasStream")

DATA_SERVICE_VERSION = (ODATA_METADATA_NAMESPACE, "DataServiceVersion")
FC_KeepInContent = (ODATA_METADATA_NAMESPACE, "FC_KeepInContent")
FC_TargetPath = (ODATA_METADATA_NAMESPACE, "FC_TargetPath")
FC_NsPrefix = (ODATA_METADATA_NAMESPACE, "FC_NsPrefix")
FC_NsUri = (ODATA_METADATA_NAMESPACE, "FC_NsUri")
FC_SourcePath = (ODATA_METADATA_NAMESPACE, "FC_SourcePath")

#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_DATASERVICES_NAMESPACE = "http://schemas.microsoft.com/ado/2007/08/dataservices"
#: category scheme for type definition terms
ODATA_SCHEME = "http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"
#: link type for related entries
ODATA_RELATED = "http://schemas.microsoft.com/ado/2007/08/dataservices/related/"

ODATA_RELATED_ENTRY_TYPE = "application/atom+xml;type=entry"
ODATA_RELATED_FEED_TYPE = "application/atom+xml;type=feed"


class ODataError(Exception):

    """Base class for OData-specific errors."""
    pass


class ExpectedMediaLinkCollection(ODataError):

    """Expected a collection of media link entries

    Raised when a method reserved for media resources is called on a
    collection with an underlying entity type that was not declared to
    have an associated stream."""
    pass


class InvalidLiteral(Exception):
    pass


class InvalidServiceDocument(Exception):
    pass


class InvalidFeedDocument(Exception):
    pass


class InvalidEntryDocument(Exception):
    pass


class InvalidFeedURL(Exception):
    pass


class ServerError(Exception):
    pass


class BadURISegment(ServerError):
    pass


class MissingURISegment(ServerError):
    pass


class InvalidSystemQueryOption(ServerError):
    pass


class InvalidPathOption(ServerError):
    pass


class InvalidMethod(ServerError):
    pass


class InvalidData(ServerError):
    pass


class EvaluationError(Exception):
    pass


NUMERIC_TYPES = (
    edm.SimpleType.Double,
    edm.SimpleType.Single,
    edm.SimpleType.Decimal,
    edm.SimpleType.Int64,
    edm.SimpleType.Int32,
    edm.SimpleType.Int16,
    edm.SimpleType.Byte)


def PromoteTypes(typeA, typeB):
    """Given two values from :py:class:`pyslet.mc_csdl.SimpleType` returns the common promoted type.

    If typeA and typeB are the same this is always returns that type code.

    Otherwise it follows numeric type promotion rules laid down in the
    specification. If the types are incompatible then an EvaluationError is raised."""
    if typeA == typeB:
        return typeA
    elif typeA is None:
        return typeB
    elif typeB is None:
        return typeA
    elif typeA not in NUMERIC_TYPES or typeB not in NUMERIC_TYPES:
        raise EvaluationError(
            "Incompatible types: %s and %s" %
            (edm.SimpleType.EncodeValue(typeA),
             edm.SimpleType.EncodeValue(typeB)))
    elif edm.SimpleType.Double in (typeA, typeB):
        return edm.SimpleType.Double
    elif edm.SimpleType.Single in (typeA, typeB):
        return edm.SimpleType.Single
    elif edm.SimpleType.Decimal in (typeA, typeB):
        return edm.SimpleType.Decimal
    elif edm.SimpleType.Int64 in (typeA, typeB):
        return edm.SimpleType.Int64
    elif edm.SimpleType.Int32 in (typeA, typeB):
        return edm.SimpleType.Int32
    elif edm.SimpleType.Int16 in (typeA, typeB):
        return edm.SimpleType.Int16
    # else must be both Byte - already got this case above


def CanCastMethodArgument(typeA, typeB):
    """Given two values from :py:class:`pyslet.mc_csdl.SimpleType` returns True if *typeA* can be cast to *typeB*.

    If typeA and typeB are the same this is always True.

    If typeA is NULL then we return True"""
    if typeA == typeB:
        return True
    elif typeA is None:
        return True
    elif typeB == edm.SimpleType.Double:
        return typeA in NUMERIC_TYPES
    elif typeB == edm.SimpleType.Single:
        return typeA in NUMERIC_TYPES
    elif typeB == edm.SimpleType.Decimal:
        return typeA in (
            edm.SimpleType.Decimal,
            edm.SimpleType.Int64,
            edm.SimpleType.Int32,
            edm.SimpleType.Int16)
    elif typeB == edm.SimpleType.Int64:
        return typeA in NUMERIC_TYPES
    elif typeB == edm.SimpleType.Int32:
        return typeA in NUMERIC_TYPES
    elif typeB == edm.SimpleType.Int16:
        return typeA in NUMERIC_TYPES
    elif typeB == edm.SimpleType.Byte:
        return typeA in NUMERIC_TYPES
    else:
        return False


class OperatorCategory(xsi.Enumeration):

    """An enumeration used to represent operator categories (for precedence).
    ::

            OperatorCategory.Unary
            SimpleType.DEFAULT == None

    Note that OperatorCategory.X > OperatorCategory.Y if and only if operator X
    has higher precedence that operator Y.

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""

    decode = {
        "Grouping": 10,
        "Primary": 9,
        "Unary": 8,
        "Multiplicative": 7,
        "Additive": 6,
        "Relational": 5,
        "Equality": 4,
        "ConditionalAnd": 3,
        "ConditionalOr": 2
    }
xsi.MakeEnumeration(OperatorCategory)


class Operator(xsi.Enumeration):

    """An enumeration used to represent operators.

    Note that the expressions not, and and or have aliases "boolNot",
    "boolAnd" and "boolOr" to make it easier to use Python attribute
    notation::

            Operator.mul
            Operator.DEFAULT == None
            Operator.boolNot == getattr(Operator,"not")

    """

    decode = {
        'paren': 20,
        'member': 19,
        'methodCall': 18,
        'negate': 17,
        'not': 16,
        'cast': 15,
        'mul': 14,
        'div': 13,
        'mod': 12,
        'add': 11,
        'sub': 10,
        'lt': 9,
        'gt': 8,
        'le': 7,
        'ge': 6,
        'isof': 5,
        'eq': 4,
        'ne': 3,
        'and': 2,
        'or': 1,
    }

    Category = {
    }
    """A mapping from an operator to an operator category identifier
    which can be compared for precedence testing::
    
        Operator.Category.[opA] > Operator.Category.[opB]
    
    if and only if opA has higher precedence than opB."""

    IsSpecial = None
    """A set of Operator values that are special, in that they do no
    describe the simple pattern::
    
        [lvalue] opname right-value
    
    For example, isof, negate, method, etc..."""

xsi.MakeEnumeration(Operator)
xsi.MakeEnumerationAliases(Operator, {
    'boolParen': 'paren',
    'boolMethodCall': 'methodCall',
    'boolNot': 'not',
    'boolAnd': 'and',
    'boolOr': 'or'})

Operator.Category = {
    Operator.paren: OperatorCategory.Grouping,
    Operator.member: OperatorCategory.Primary,
    Operator.methodCall: OperatorCategory.Primary,
    Operator.negate: OperatorCategory.Unary,
    Operator.boolNot: OperatorCategory.Unary,
    Operator.cast: OperatorCategory.Unary,
    Operator.mul: OperatorCategory.Multiplicative,
    Operator.div: OperatorCategory.Multiplicative,
    Operator.mod: OperatorCategory.Multiplicative,
    Operator.add: OperatorCategory.Additive,
    Operator.sub: OperatorCategory.Additive,
    Operator.lt: OperatorCategory.Relational,
    Operator.gt: OperatorCategory.Relational,
    Operator.le: OperatorCategory.Relational,
    Operator.ge: OperatorCategory.Relational,
    Operator.isof: OperatorCategory.Relational,
    Operator.eq: OperatorCategory.Equality,
    Operator.ne: OperatorCategory.Equality,
    Operator.boolAnd: OperatorCategory.ConditionalAnd,
    Operator.boolOr: OperatorCategory.ConditionalOr}

Operator.IsSpecial = set(
    (Operator.paren,
     Operator.member,
     Operator.methodCall,
     Operator.negate,
     Operator.cast,
     Operator.isof))


class Method(xsi.Enumeration):

    """An enumeration used to represent method calls.
    ::

            Method.endswith
            Method.DEFAULT == None
    """

    decode = {
        'endswith': 1,
        'indexof': 2,
        'replace': 3,
        'startswith': 4,
        'tolower': 5,
        'toupper': 6,
        'trim': 7,
        'substring': 8,
        'substringof': 9,
        'concat': 10,
        'length': 11,
        'year': 12,
        'month': 13,
        'day': 14,
        'hour': 15,
        'minute': 16,
        'second': 17,
        'round': 18,
        'floor': 19,
        'ceiling': 20
    }
xsi.MakeEnumeration(Method)


class CommonExpression(object):

    """Represents a common expression, used by $filter and $orderby system query options."""

    def __init__(self, operator=None):
        self.parent = None
        self.operator = operator
        self.operands = []

    def AddOperand(self, operand):
        self.operands.append(operand)

    def Evaluate(self, contextEntity):
        raise NotImplementedError

    def __cmp__(self, other):
        """We implement __cmp__ based on operator precedence."""
        if other.operator is None or self.operator is None:
            raise ValueError("Expression without operator cannot be compared")
        return cmp(
            Operator.Category[
                self.operator], Operator.Category[
                other.operator])

    @staticmethod
    def from_str(src, params=None):
        p = Parser(src)
        return p.require_production_end(
            p.ParseCommonExpression(params),
            "commonExpression")

    @staticmethod
    def OrderByFromString(src):
        p = Parser(src)
        return p.require_production_end(p.ParseOrderbyOption(), "orderbyOption")

    @staticmethod
    def OrderByToString(orderby):
        return string.join(map(lambda x: "%s %s" % (
            unicode(x[0]), "asc" if x[1] > 0 else "desc"), orderby), ', ')

    def __unicode__(self):
        raise NotImplementedError


class UnaryExpression(CommonExpression):

    EvalMethod = {
    }
    """A mapping from unary operator constants to unbound methods that
    evaluate the operator."""

    def __init__(self, operator):
        super(UnaryExpression, self).__init__(operator)

    def __unicode__(self):
        if self.operator == Operator.negate:
            op = u"-"
        else:
            op = u"%s " % Operator.EncodeValue(self.operator)
        rValue = self.operands[0]
        if rValue.operator is not None and rValue < self:
            # right expression is weaker than us, use brackets
            result = "%s(%s)" % (op, unicode(rValue))
        else:
            result = "%s%s" % (op, unicode(rValue))
        return result

    def Evaluate(self, contextEntity):
        rValue = self.operands[0].Evaluate(contextEntity)
        return self.EvalMethod[self.operator](self, rValue)

    def EvaluateNegate(self, rValue):
        typeCode = rValue.typeCode
        if typeCode in (edm.SimpleType.Byte, edm.SimpleType.Int16):
            rValue = rValue.SimpleCast(edm.SimpleType.Int32)
        elif typeCode == edm.SimpleType.Single:
            rValue = rValue.SimpleCast(edm.SimpleType.Double)
        typeCode = rValue.typeCode
        if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Double, edm.SimpleType.Decimal):
            result = edm.EDMValue.NewSimpleValue(typeCode)
            if rValue:
                result.set_from_value(0 - rValue.value)
            return result
        elif typeCode is None:  # -null
            return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operand for negate")

    def EvaluateNot(self, rValue):
        if isinstance(rValue, edm.SimpleValue):
            if rValue:
                typeCode = rValue.typeCode
                if typeCode == edm.SimpleType.Boolean:
                    result = edm.EDMValue.NewSimpleValue(
                        edm.SimpleType.Boolean)
                    result.set_from_value(not rValue.value)
                    return result
                else:
                    raise EvaluationError("Illegal operand for not")
            else:
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
                return result
        else:
            raise EvaluationError("Illegal operand for not")


UnaryExpression.EvalMethod = {
    Operator.negate: UnaryExpression.EvaluateNegate,
    Operator.boolNot: UnaryExpression.EvaluateNot}


class BinaryExpression(CommonExpression):

    EvalMethod = {
    }
    """A mapping from binary operators to unbound methods that evaluate
    the operator."""

    def __init__(self, operator):
        super(BinaryExpression, self).__init__(operator)

    def __unicode__(self):
        opPrefix = opSuffix = ''
        if self.operator in Operator.IsSpecial:
            if self.operator == Operator.member:
                op = u"/"
            elif self.operator in (Operator.cast, Operator.isof):
                opPrefix = u"%s(" % Operator.EncodeValue(self.operator)
                op = ","
                opSuffix = ")"
            else:
                raise ValueError(
                    "Can't format %s as a binary operator" & Operator.EncodeValue(
                        self.operator))
        else:
            op = u" %s " % Operator.EncodeValue(self.operator)
        lValue = self.operands[0]
        rValue = self.operands[1]
        if lValue.operator is not None and lValue < self:
            # left expression is weaker than us, use brackets
            lValue = "(%s)" % unicode(lValue)
        else:
            lValue = unicode(lValue)
        if rValue.operator is not None and rValue < self:
            # right expression is weaker than us, use brackets
            rValue = "(%s)" % unicode(rValue)
        else:
            rValue = unicode(rValue)
        return string.join((opPrefix, lValue, op, rValue, opSuffix), '')

    def Evaluate(self, contextEntity):
        lValue = self.operands[0].Evaluate(contextEntity)
        if self.operator == Operator.member:
            # Special handling for the member operator, as the left-hand
            # side of the expression returns the context for evaluating
            # the right-hand side
            return self.operands[1].Evaluate(lValue)
        elif self.operator in (Operator.isof, Operator.cast):
            # Special handling due to optional first parameter to
            # signify the context entity
            if len(self.operands) == 1:
                rValue = lValue
                lValue = contextEntity
            else:
                rValue = self.operands[1].Evaluate(contextEntity)
            return self.EvalMethod[self.operator](self, lValue, rValue)
        else:
            rValue = self.operands[1].Evaluate(contextEntity)
            return self.EvalMethod[self.operator](self, lValue, rValue)

    def PromoteOperands(self, lValue, rValue):
        if isinstance(lValue, edm.SimpleValue) and isinstance(rValue, edm.SimpleValue):
            return PromoteTypes(lValue.typeCode, rValue.typeCode)
        else:
            raise EvaluationError(
                "Expected primitive value for %s" %
                Operator.EncodeValue(
                    self.operator))

    def EvaluateCast(self, lValue, rValue):
        # rValue is always a string literal name of the type to look up
        if not lValue:
            # cast(NULL, <any type>) results in NULL
            try:
                typeCode = edm.SimpleType.DecodeValue(rValue.value)
                result = edm.EDMValue.NewSimpleValue(typeCode)
            except ValueError:
                result = edm.SimpleValue.NewValue(None)
            return result
        elif isinstance(lValue, edm.Entity):
            # in the future we should deal with entity type inheritance
            # right now, the only thing we can cast an entity instance
            # to is itself
            name = lValue.type_def.GetFQName()
            if name == rValue.value:
                return lValue
            else:
                raise EvaluationError(
                    "Can't cast %s to %s" % (name, str(rValue.value)))
        elif isinstance(lValue, edm.SimpleValue):
            # look up the name of the primitive type
            try:
                typeCode = edm.SimpleType.DecodeValue(rValue.value)
            except ValueError:
                raise EvaluationError(
                    "Unrecognized type: %s" % str(rValue.value))
            newCode = PromoteTypes(typeCode, lValue.typeCode)
            if typeCode != newCode:
                raise EvaluationError(
                    "Can't cast %s to %s" %
                    (edm.SimpleType.EncodeValue(
                        lValue.typeCode),
                        edm.SimpleType.EncodeValue(typeCode)))
            result = edm.EDMValue.NewSimpleValue(typeCode)
            result.set_from_value(lValue.value)
            return result
        else:
            raise EvaluationError("Illegal operands for isof")

    def EvaluateMul(self, lValue, rValue):
        typeCode = self.PromoteOperands(lValue, rValue)
        if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
                        edm.SimpleType.Double, edm.SimpleType.Decimal):
            lValue = lValue.SimpleCast(typeCode)
            rValue = rValue.SimpleCast(typeCode)
            result = edm.EDMValue.NewSimpleValue(typeCode)
            if lValue and rValue:
                result.set_from_value(lValue.value * rValue.value)
            return result
        elif typeCode is None:  # null mul null
            return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operands for mul")

    def EvaluateDiv(self, lValue, rValue):
        try:
            typeCode = self.PromoteOperands(lValue, rValue)
            if typeCode in (edm.SimpleType.Single, edm.SimpleType.Double, edm.SimpleType.Decimal):
                lValue = lValue.SimpleCast(typeCode)
                rValue = rValue.SimpleCast(typeCode)
                result = edm.EDMValue.NewSimpleValue(typeCode)
                if lValue and rValue:
                    result.set_from_value(lValue.value / rValue.value)
                return result
            elif typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64):
                lValue = lValue.SimpleCast(typeCode)
                rValue = rValue.SimpleCast(typeCode)
                result = edm.EDMValue.NewSimpleValue(typeCode)
                if lValue and rValue:
                    # OData doesn't really specify integer division rules so
                    # we use floating point division and truncate towards zero
                    result.set_from_value(
                        int(float(lValue.value) / float(rValue.value)))
                return result
            elif typeCode is None:  # null div null
                return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            else:
                raise EvaluationError("Illegal operands for div")
        except ZeroDivisionError as e:
            raise EvaluationError(str(e))

    def EvaluateMod(self, lValue, rValue):
        try:
            typeCode = self.PromoteOperands(lValue, rValue)
            if typeCode in (edm.SimpleType.Single, edm.SimpleType.Double, edm.SimpleType.Decimal):
                lValue = lValue.SimpleCast(typeCode)
                rValue = rValue.SimpleCast(typeCode)
                result = edm.EDMValue.NewSimpleValue(typeCode)
                if lValue and rValue:
                    result.set_from_value(
                        math.fmod(lValue.value, rValue.value))
                return result
            elif typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64):
                lValue = lValue.SimpleCast(typeCode)
                rValue = rValue.SimpleCast(typeCode)
                result = edm.EDMValue.NewSimpleValue(typeCode)
                if lValue and rValue:
                    # OData doesn't really specify integer division rules so
                    # we use floating point division and truncate towards zero
                    result.set_from_value(
                        int(math.fmod(float(lValue.value), float(rValue.value))))
                return result
            elif typeCode is None:  # null div null
                return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            else:
                raise EvaluationError("Illegal operands for div")
        except (ZeroDivisionError, ValueError) as e:
            raise EvaluationError(str(e))

    def EvaluateAdd(self, lValue, rValue):
        typeCode = self.PromoteOperands(lValue, rValue)
        if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
                        edm.SimpleType.Double, edm.SimpleType.Decimal):
            lValue = lValue.SimpleCast(typeCode)
            rValue = rValue.SimpleCast(typeCode)
            result = edm.EDMValue.NewSimpleValue(typeCode)
            if lValue and rValue:
                result.set_from_value(lValue.value + rValue.value)
            return result
        elif typeCode is None:  # null add null
            return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operands for add")

    def EvaluateSub(self, lValue, rValue):
        typeCode = self.PromoteOperands(lValue, rValue)
        if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
                        edm.SimpleType.Double, edm.SimpleType.Decimal):
            lValue = lValue.SimpleCast(typeCode)
            rValue = rValue.SimpleCast(typeCode)
            result = edm.EDMValue.NewSimpleValue(typeCode)
            if lValue and rValue:
                result.set_from_value(lValue.value - rValue.value)
            return result
        elif typeCode is None:  # null sub null
            return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operands for sub")

    def EvaluateLt(self, lValue, rValue):
        return self.EvaluateRelation(lValue, rValue, lambda x, y: x < y)

    def EvaluateGt(self, lValue, rValue):
        return self.EvaluateRelation(lValue, rValue, lambda x, y: x > y)

    def EvaluateLe(self, lValue, rValue):
        return self.EvaluateRelation(lValue, rValue, lambda x, y: x <= y)

    def EvaluateGe(self, lValue, rValue):
        return self.EvaluateRelation(lValue, rValue, lambda x, y: x >= y)

    def EvaluateRelation(self, lValue, rValue, relation):
        typeCode = self.PromoteOperands(lValue, rValue)
        if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
                        edm.SimpleType.Double, edm.SimpleType.Decimal):
            lValue = lValue.SimpleCast(typeCode)
            rValue = rValue.SimpleCast(typeCode)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if lValue and rValue:
                result.set_from_value(relation(lValue.value, rValue.value))
            else:
                # one of the operands is null => False
                result.set_from_value(False)
            return result
        elif typeCode in (edm.SimpleType.String, edm.SimpleType.DateTime, edm.SimpleType.Guid):
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.set_from_value(relation(lValue.value, rValue.value))
            return result
        elif typeCode is None:  # e.g., null lt null
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.set_from_value(False)
            return result
        else:
            raise EvaluationError(
                "Illegal operands for %s" %
                Operator.EncodeValue(
                    self.operator))

    def EvaluateIsOf(self, lValue, rValue):
        # rValue is always a string literal name of the type to look up
        if not lValue:
            # isof(NULL, <any type> ) is False
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.set_from_value(False)
            return result
        elif isinstance(lValue, edm.Entity):
            # in the future we should test the entity for inheritance
            name = lValue.type_def.GetFQName()
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.set_from_value(name == rValue.value)
            return result
        elif isinstance(lValue, edm.SimpleValue):
            # look up the name of the primitive type
            try:
                typeCode = edm.SimpleType.DecodeValue(rValue.value)
            except ValueError:
                raise EvaluationError(
                    "Unrecognized type: %s" % str(rValue.value))
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            # we return True if the type of the target, when promoted with type
            # being tested results in the type being tested
            try:
                rValue = (typeCode == PromoteTypes(typeCode, lValue.typeCode))
            except EvaluationError:
                # incompatible types means False
                rValue = False
            result.set_from_value(rValue)
            return result
        else:
            raise EvaluationError("Illegal operands for isof")

    def EvaluateEq(self, lValue, rValue):
        if isinstance(lValue, edm.Entity) and isinstance(rValue, edm.Entity):
            # we can do comparison of entities, but must be the same entity!
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if lValue.entity_set is rValue.entity_set:
                # now test that the keys are the same
                result.value = (lValue.key() == rValue.key())
            else:
                result.value = False
            return result
        else:
            typeCode = self.PromoteOperands(lValue, rValue)
            if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
                            edm.SimpleType.Double, edm.SimpleType.Decimal):
                lValue = lValue.SimpleCast(typeCode)
                rValue = rValue.SimpleCast(typeCode)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
                result.set_from_value(lValue.value == rValue.value)
                return result
            elif typeCode in (edm.SimpleType.String, edm.SimpleType.DateTime, edm.SimpleType.Guid, edm.SimpleType.Binary):
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
                result.set_from_value(lValue.value == rValue.value)
                return result
            elif typeCode is None:  # null eq null
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
                result.set_from_value(True)
                return result
            else:
                raise EvaluationError("Illegal operands for add")

    def EvaluateNe(self, lValue, rValue):
        result = self.EvaluateEq(lValue, rValue)
        result.value = not result.value
        return result

    def EvaluateAnd(self, lValue, rValue):
        """Watch out for the differences between OData 2-value logic and
        the usual SQL 3-value approach."""
        typeCode = self.PromoteOperands(lValue, rValue)
        if typeCode == edm.SimpleType.Boolean:
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if lValue and rValue:
                result.value = lValue.value and rValue.value
            else:
                result.value = False
            return result
        elif typeCode is None:
            # null or null
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.value = False
            return result
        else:
            raise EvaluationError("Illegal operands for boolean and")

    def EvaluateOr(self, lValue, rValue):
        """Watch out for the differences between OData 2-value logic and
        the usual SQL 3-value approach."""
        typeCode = self.PromoteOperands(lValue, rValue)
        if typeCode == edm.SimpleType.Boolean:
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if lValue and rValue:
                result.value = lValue.value or rValue.value
            else:
                result.value = False
            return result
        elif typeCode is None:
            # null or null
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.value = False
            return result
        else:
            raise EvaluationError("Illegal operands for boolean and")

BinaryExpression.EvalMethod = {
    Operator.cast: BinaryExpression.EvaluateCast,
    Operator.mul: BinaryExpression.EvaluateMul,
    Operator.div: BinaryExpression.EvaluateDiv,
    Operator.mod: BinaryExpression.EvaluateMod,
    Operator.add: BinaryExpression.EvaluateAdd,
    Operator.sub: BinaryExpression.EvaluateSub,
    Operator.lt: BinaryExpression.EvaluateLt,
    Operator.gt: BinaryExpression.EvaluateGt,
    Operator.le: BinaryExpression.EvaluateLe,
    Operator.ge: BinaryExpression.EvaluateGe,
    Operator.isof: BinaryExpression.EvaluateIsOf,
    Operator.eq: BinaryExpression.EvaluateEq,
    Operator.ne: BinaryExpression.EvaluateNe,
    Operator.boolAnd: BinaryExpression.EvaluateAnd,
    Operator.boolOr: BinaryExpression.EvaluateOr}


class LiteralExpression(CommonExpression):

    def __init__(self, value):
        super(LiteralExpression, self).__init__()
        self.value = value

    def __unicode__(self):
        """Return, for example, 42L or 'Paddy O''brian' - note that %-encoding is not applied"""
        if not self.value:
            return "null"
        else:
            result = unicode(self.value)
            if self.value.typeCode == edm.SimpleType.Binary:
                result = "X'%s'" % result
            elif self.value.typeCode == edm.SimpleType.DateTime:
                result = "datetime'%s'" % result
            elif self.value.typeCode == edm.SimpleType.Decimal:
                result = result + "M"
            elif self.value.typeCode == edm.SimpleType.Double:
                result = result + "D"
            elif self.value.typeCode == edm.SimpleType.Single:
                result = result + "F"
            elif self.value.typeCode == edm.SimpleType.Guid:
                result = "guid'%s'" % result
            elif self.value.typeCode == edm.SimpleType.Int64:
                result = result + "L"
            elif self.value.typeCode == edm.SimpleType.Time:
                result = "time'%s'" % result
            elif self.value.typeCode == edm.SimpleType.DateTimeOffset:
                result = "datetimeoffset'%s'" % result
            elif self.value.typeCode == edm.SimpleType.String:
                # double up on single quotes
                result = "'%s'" % string.join(result.split("'"), "''")
            return result

    def Evaluate(self, contextEntity):
        """A literal evaluates to itself."""
        return self.value


class PropertyExpression(CommonExpression):

    def __init__(self, name):
        super(PropertyExpression, self).__init__()
        self.name = name

    def __unicode__(self):
        return unicode(self.name)

    def Evaluate(self, contextEntity):
        if contextEntity:
            if isinstance(contextEntity, edm.Entity):
                if contextEntity.IsEntityCollection(self.name):
                    raise EvaluationError(
                        "%s navigation property must have cardinality of 1 or 0..1" %
                        self.name)
                else:
                    result = contextEntity[self.name]
                    if isinstance(result, edm.DeferredValue):
                        result = result.GetEntity()
                    if result is None:
                        # The navigation property does not point to anything,
                        # return a generic null
                        result = edm.EDMValue.NewValue(None)
                    return result
            elif self.name in contextEntity:
                # contextEntity must be a complex value
                return contextEntity[self.name]
            else:
                raise EvaluationError("Undefined property: %s" % self.name)
        else:
            raise EvaluationError(
                "Evaluation of %s member: no entity in context" % self.name)


class CallExpression(CommonExpression):

    EvalMethod = {
    }
    """A mapping from method calls to unbound methods that evaluate
    the method."""

    def __init__(self, methodCall):
        super(CallExpression, self).__init__(Operator.methodCall)
        self.method = methodCall

    def __unicode__(self):
        return "%s(%s)" % (Method.EncodeValue(self.method), string.join(
            map(lambda x: unicode(x), self.operands), ','))

    def Evaluate(self, contextEntity):
        return self.EvalMethod[
            self.method](
            self, map(
                lambda x: x.Evaluate(contextEntity), self.operands))

    def PromoteParameter(self, arg, typeCode):
        if isinstance(arg, edm.SimpleValue):
            if CanCastMethodArgument(arg.typeCode, typeCode):
                return arg.SimpleCast(typeCode)
        raise EvaluationError(
            "Expected %s value in %s()" %
            (edm.SimpleType.EncodeValue(typeCode),
             Method.EncodeValue(
                self.method)))

    def CheckStrictParameter(self, arg, typeCode):
        if isinstance(arg, edm.SimpleValue):
            if arg.typeCode == typeCode:
                return arg
        raise EvaluationError(
            "Expected %s value in %s()" %
            (edm.SimpleType.EncodeValue(typeCode),
             Method.EncodeValue(
                self.method)))

    def EvaluateEndswith(self, args):
        if (len(args) == 2):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            prefix = self.PromoteParameter(args[1], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if target and prefix:
                result.set_from_value(target.value.endswith(prefix.value))
            return result
        else:
            raise EvaluationError(
                "endswith() takes 2 arguments, %i given" % len(args))

    def EvaluateIndexof(self, args):
        if (len(args) == 2):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            searchString = self.PromoteParameter(
                args[1], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target and searchString:
                result.set_from_value(target.value.find(searchString.value))
            return result
        else:
            raise EvaluationError(
                "indexof() takes 2 arguments, %i given" % len(args))

    def EvaluateReplace(self, args):
        if (len(args) == 3):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            searchString = self.PromoteParameter(
                args[1], edm.SimpleType.String)
            replaceString = self.PromoteParameter(
                args[2], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            if target and searchString and replaceString:
                result.set_from_value(
                    target.value.replace(
                        searchString.value,
                        replaceString.value))
            return result
        else:
            raise EvaluationError(
                "replace() takes 3 arguments, %i given" % len(args))

    def EvaluateStartswith(self, args):
        if (len(args) == 2):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            prefix = self.PromoteParameter(args[1], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if target and prefix:
                result.set_from_value(target.value.startswith(prefix.value))
            return result
        else:
            raise EvaluationError(
                "startswith() takes 2 arguments, %i given" % len(args))

    def EvaluateTolower(self, args):
        if (len(args) == 1):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            if target:
                result.set_from_value(target.value.lower())
            return result
        else:
            raise EvaluationError(
                "tolower() takes 1 argument, %i given" % len(args))

    def EvaluateToupper(self, args):
        if (len(args) == 1):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            if target:
                result.set_from_value(target.value.upper())
            return result
        else:
            raise EvaluationError(
                "toupper() takes 1 argument, %i given" % len(args))

    def EvaluateTrim(self, args):
        if (len(args) == 1):
            target = self.PromoteParameter(args[0], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            if target:
                result.set_from_value(target.value.strip())
            return result
        else:
            raise EvaluationError(
                "trim() takes 1 argument, %i given" % len(args))

    def EvaluateSubstring(self, args):
        if (len(args) == 2 or len(args) == 3):
            target = self.CheckStrictParameter(args[0], edm.SimpleType.String)
            start = self.CheckStrictParameter(args[1], edm.SimpleType.Int32)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            if len(args) == 3:
                length = self.CheckStrictParameter(
                    args[2], edm.SimpleType.Int32)
            else:
                length = None
            if target and start:
                if length:
                    result.set_from_value(
                        target.value[start.value:start.value + length.value])
                else:
                    result.set_from_value(target.value[start.value:])
            return result
        else:
            raise EvaluationError(
                "substring() takes 2 or 3 arguments, %i given" % len(args))

    def EvaluateSubstringof(self, args):
        if (len(args) == 2):
            searchString = self.PromoteParameter(
                args[0], edm.SimpleType.String)
            target = self.PromoteParameter(args[1], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            if target and searchString:
                result.set_from_value(
                    target.value.find(searchString.value) >= 0)
            return result
        else:
            raise EvaluationError(
                "substringof() takes 2 arguments, %i given" % len(args))

    def EvaluateConcat(self, args):
        if (len(args) == 2):
            leftString = self.CheckStrictParameter(
                args[0], edm.SimpleType.String)
            rightString = self.CheckStrictParameter(
                args[1], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            if leftString and rightString:
                result.set_from_value(leftString.value + rightString.value)
            return result
        else:
            raise EvaluationError(
                "concat() takes 2 arguments, %i given" % len(args))

    def EvaluateLength(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(args[0], edm.SimpleType.String)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(len(target.value))
            return result
        else:
            raise EvaluationError(
                "length() takes 1 argument, %i given" % len(args))

    def EvaluateYear(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(
                    target.value.date.century * 100 + target.value.date.year)
            return result
        else:
            raise EvaluationError(
                "year() takes 1 argument, %i given" % len(args))

    def EvaluateMonth(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.date.month)
            return result
        else:
            raise EvaluationError(
                "month() takes 1 argument, %i given" % len(args))

    def EvaluateDay(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.date.day)
            return result
        else:
            raise EvaluationError(
                "day() takes 1 argument, %i given" % len(args))

    def EvaluateHour(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.time.hour)
            return result
        else:
            raise EvaluationError(
                "hour() takes 1 argument, %i given" % len(args))

    def EvaluateMinute(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.time.minute)
            return result
        else:
            raise EvaluationError(
                "minute() takes 1 argument, %i given" % len(args))

    def EvaluateSecond(self, args):
        if (len(args) == 1):
            target = self.CheckStrictParameter(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.time.second)
            return result
        else:
            raise EvaluationError(
                "second() takes 1 argument, %i given" % len(args))

    def EvaluateRound(self, args):
        """This is a bit inefficient, but we convert to and from Decimal
        if necessary to ensure we stick to the rounding rules (even for
        binary, up for decimals)."""
        if (len(args) == 1):
            try:
                target = self.PromoteParameter(args[0], edm.SimpleType.Decimal)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
                if target:
                    result.set_from_value(
                        target.value.to_integral(decimal.ROUND_HALF_UP))
            except EvaluationError:
                target = self.PromoteParameter(args[0], edm.SimpleType.Double)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
                if target:
                    v = decimal.Decimal(str(target.value))
                    result.set_from_value(
                        float(v.to_integral(decimal.ROUND_HALF_EVEN)))
            return result
        else:
            raise EvaluationError(
                "round() takes 1 argument, %i given" % len(args))

    def EvaluateFloor(self, args):
        if (len(args) == 1):
            try:
                target = self.PromoteParameter(args[0], edm.SimpleType.Decimal)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
                if target:
                    result.set_from_value(
                        target.value.to_integral(decimal.ROUND_FLOOR))
            except EvaluationError:
                target = self.PromoteParameter(args[0], edm.SimpleType.Double)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
                if target:
                    result.set_from_value(math.floor(target.value))
            return result
        else:
            raise EvaluationError(
                "floor() takes 1 argument, %i given" % len(args))

    def EvaluateCeiling(self, args):
        if (len(args) == 1):
            try:
                target = self.PromoteParameter(args[0], edm.SimpleType.Decimal)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
                if target:
                    result.set_from_value(
                        target.value.to_integral(decimal.ROUND_CEILING))
            except EvaluationError:
                target = self.PromoteParameter(args[0], edm.SimpleType.Double)
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
                if target:
                    result.set_from_value(math.ceil(target.value))
            return result
        else:
            raise EvaluationError(
                "ceiling() takes 1 argument, %i given" % len(args))


CallExpression.EvalMethod = {
    Method.endswith: CallExpression.EvaluateEndswith,
    Method.indexof: CallExpression.EvaluateIndexof,
    Method.replace: CallExpression.EvaluateReplace,
    Method.startswith: CallExpression.EvaluateStartswith,
    Method.tolower: CallExpression.EvaluateTolower,
    Method.toupper: CallExpression.EvaluateToupper,
    Method.trim: CallExpression.EvaluateTrim,
    Method.substring: CallExpression.EvaluateSubstring,
    Method.substringof: CallExpression.EvaluateSubstringof,
    Method.concat: CallExpression.EvaluateConcat,
    Method.length: CallExpression.EvaluateLength,
    Method.year: CallExpression.EvaluateYear,
    Method.month: CallExpression.EvaluateMonth,
    Method.day: CallExpression.EvaluateDay,
    Method.hour: CallExpression.EvaluateHour,
    Method.minute: CallExpression.EvaluateMinute,
    Method.second: CallExpression.EvaluateSecond,
    Method.round: CallExpression.EvaluateRound,
    Method.floor: CallExpression.EvaluateFloor,
    Method.ceiling: CallExpression.EvaluateCeiling
}


class Parser(edm.Parser):
        
    def parse_common_expression(self, params=None):
        """Returns a :py:class:`CommonExpression` instance
        
        params (Default: None)
            A dictionary of :class:`~pyslet.odata2.edm.SimpleValue`
            instances keyed on a string that will be used as
            a parameter name.
        
        This type of parameterization is stricter than the untyped form
        used in Python's DB API.  You must create instances of the
        required types and add them to the dictionary.  You can then use
        :meth:`~pyslet.odata2.edm.SimpleValue.set_from_value` directly
        on the values in the dictionary to set parameter values prior to
        evaluating the expression or using it in a collection filter."""
        leftOp = None
        rightOp = None
        opStack = []
        while True:
            self.ParseWSP()
            if params is not None and self.parse(':'):
                pname = self.ParseSimpleIdentifier()
                if pname in params:
                    value = params[pname]
                else:
                    raise ValueError("Expected parameter name after ':'")
            else:
                value = self.ParseURILiteral()
            if value is not None:
                rightOp = LiteralExpression(value)
            else:
                name = self.ParseSimpleIdentifier()
                if name == "not":
                    self.require_production(self.ParseWSP(), "WSP after not")
                    rightOp = UnaryExpression(Operator.boolNot)
                elif name == "isof":
                    self.ParseWSP()
                    rightOp = self.require_production(
                        self.ParseCastLike(
                            Operator.isof,
                            "isof"),
                        "isofExpression")
                elif name == "cast":
                    self.ParseWSP()
                    rightOp = self.require_production(
                        self.ParseCastLike(
                            Operator.cast,
                            "cast"),
                        "caseExpression")
                elif name is not None:
                    self.ParseWSP()
                    if self.match("("):
                        methodCall = Method.DecodeValue(name)
                        rightOp = self.ParseMethodCallExpression(methodCall)
                    else:
                        rightOp = PropertyExpression(name)
            if rightOp is None:
                if self.parse("("):
                    rightOp = self.require_production(
                        self.ParseCommonExpression(),
                        "commonExpression inside parenExpression")
                    self.require_production(
                        self.parse(")"), "closing bracket in parenExpression")
                elif self.parse("-"):
                    rightOp = UnaryExpression(Operator.negate)
                elif leftOp:
                    # an operator waiting for an operand is an error
                    raise ValueError(
                        "Expected expression after %s in ...%s" %
                        (Operator.EncodeValue(
                            leftOp.operator),
                            self.peek(10)))
                else:
                    # no common expression found at all
                    return None
            # if we already have a (unary) operator, skip the search for a
            # binary operator
            if not isinstance(rightOp, UnaryExpression):
                operand = rightOp
                self.ParseWSP()
                if self.parse("/"):
                    # Member operator is a special case as it isn't a name
                    rightOp = BinaryExpression(Operator.member)
                else:
                    savepos = self.pos
                    name = self.ParseSimpleIdentifier()
                    if name is not None:
                        try:
                            opCode = Operator.DecodeValue(name)
                            if opCode in Operator.IsSpecial:
                                raise ValueError
                            rightOp = BinaryExpression(opCode)
                        except ValueError:
                            # this is not an operator we recognise
                            name = None
                            self.setpos(savepos)
                            pass
                    # if name is None and (self.MatchOne(",)") or self.MatchEnd()):
                    # indicates the end of this common expression
                    if name is None:
                        while leftOp is not None:
                            leftOp.AddOperand(operand)
                            operand = leftOp
                            if opStack:
                                leftOp = opStack.pop()
                            else:
                                leftOp = None
                        return operand
            else:
                operand = None
            # we now have:
            # leftOp (may be None)
            # operand (None only if rightOp is unary)
            # rightOp (an operator expression, never None)
            # next job, determine who binds more tightly, left or right?
            while True:
                if leftOp is None or leftOp < rightOp:
                    # bind the operand to the right, in cases of equal
                    # precedence we left associate 1+2-3 = (1+2)-3
                    if operand is not None:
                        rightOp.AddOperand(operand)
                    if leftOp is not None:
                        opStack.append(leftOp)
                    leftOp = rightOp
                    rightOp = None
                    operand = None
                    break
                else:
                    # bind the operand to the left
                    leftOp.AddOperand(operand)
                    operand = leftOp
                    if opStack:
                        leftOp = opStack.pop()
                    else:
                        leftOp = None

    def ParseMethodCallExpression(self, methodCall):
        method = CallExpression(methodCall)
        self.require_production(
            self.parse("("), "opening bracket in methodCallExpression")
        while True:
            self.ParseWSP()
            param = self.require_production(
                self.ParseCommonExpression(), "methodCall argument")
            method.AddOperand(param)
            self.ParseWSP()
            if self.parse(","):
                continue
            elif self.parse(")"):
                break
            else:
                raise ValueError("closing bracket in methodCallExpression")
        return method

    def ParseCastLike(self, op, name):
        """Parses a cast-like expression, including 'isof'."""
        self.ParseWSP()
        if self.parse("("):
            e = BinaryExpression(op)
            firstParam = self.require_production(
                self.ParseCommonExpression(), "%s argument" % name)
            e.AddOperand(firstParam)
            self.ParseWSP()
            if self.parse_one(")"):
                # first parameter omitted
                stringParam = firstParam
            else:
                self.require_production(self.parse(","), "',' in %s" % name)
                self.ParseWSP()
                stringParam = self.require_production(
                    self.ParseCommonExpression(), "%s argument" % name)
                e.AddOperand(stringParam)
                self.ParseWSP()
                self.require_production(self.parse(")"), "')' after %s" % name)
            # Final check, the string parameter must be a string literal!
            if not isinstance(stringParam, LiteralExpression) or stringParam.value.typeCode != edm.SimpleType.String:
                raise ValueError("%s requires string literal")
            return e
        else:
            return None

    def ParseWSP(self):
        """Parses WSP characters, returning the string of WSP parsed or None."""
        result = []
        while True:
            c = self.parse_one(" \t")
            if c:
                result.append(c)
            else:
                break
        if result:
            return string.join(result, '')
        else:
            return None

    def ParseExpandOption(self):
        """Parses an expand system query option, returning a list of tuples.

        E.g., "A/B,C" returns {'A': {'B'}, 'C': None }"""
        result = {}
        while True:
            parent = result
            navPath = self.require_production(
                self.ParseSimpleIdentifier(), "entityNavProperty")
            if navPath not in parent:
                parent[navPath] = None
            while self.parse("/"):
                if parent[navPath] is None:
                    parent[navPath] = {}
                parent = parent[navPath]
                navPath = self.require_production(
                    self.ParseSimpleIdentifier(), "entityNavProperty")
                if navPath not in parent:
                    parent[navPath] = None
            if not self.parse(","):
                break
        self.require_end("expandQueryOp")
        return result

    def ParseOrderbyOption(self):
        """Parses an orderby system query option, returning a list of 2-tuples.

        Each tuple is ( <py:class:`CommonExpression` instance>, 1 | -1 )

        The value 1 represents the default ascending order, -1 indicated descending."""
        result = []
        while True:
            self.ParseWSP()
            e = self.require_production(
                self.ParseCommonExpression(), "commonExpression")
            self.ParseWSP()
            if self.parse_insensitive("asc"):
                dir = 1
            elif self.parse_insensitive("desc"):
                dir = -1
            else:
                dir = 1
            result.append((e, dir))
            self.ParseWSP()
            if not self.parse(","):
                break
        self.require_end("orderbyQueryOp")
        return result

    def ParseSelectOption(self):
        """Parses a select system query option, returning a list of tuples.

        E.g., "A/*,C" returns [("A","*"),("C")]

        This is almost identical to the expand option except that '*"
        and WSP is allowed.

        selectQueryOp = "$select=" selectClause
        selectClause = [WSP] selectItem [[WSP] "," selectClause] [WSP]
        selectItem = star / selectedProperty / (selectedNavProperty ["/" selectItem])
        selectedProperty = entityProperty / entityComplexProperty
        selectedNavProperty = entityNavProperty-es / entityNavProperty-et
        star = "*"  """
        result = {}
        while True:
            parent = result
            self.ParseWSP()
            navPath = self.require_production(
                self.ParseStarOrIdentifier(), "selectItem")
            if navPath not in parent:
                parent[navPath] = None
            while navPath != "*" and self.parse("/"):
                if parent[navPath] is None:
                    parent[navPath] = {}
                parent = parent[navPath]
                navPath = self.require_production(
                    self.ParseStarOrIdentifier(), "selectItem")
                if navPath not in parent:
                    parent[navPath] = None
            self.ParseWSP()
            if not self.parse(","):
                break
        self.require_end("selectQueryOp")
        return result

    def ParseStarOrIdentifier(self):
        self.ParseWSP()
        if self.parse("*"):
            return '*'
        else:
            return self.require_production(
                self.ParseSimpleIdentifier(),
                "selectItem")

    SimpleIdentifierStartClass = None
    SimpleIdentifierClass = None

    def ParseSimpleIdentifier(self):
        """Parses a SimpleIdentifier

        Although the OData specification simply says that these
        identifiers are *pchar the ABNF is confusing because it relies
        on WSP which can only exist after percent encoding has been
        removed.  There is also the implicit assumption that characters
        that might be confused with operators will be percent-encoded if
        they appear in identifiers, again problematic if percent
        encoding has already been removed.

        Later versions of the specification have clarified this and it
        is clear that identifiers must be parsable after
        percent-decoding.  It's a bit of a moot point though because, in
        reality, the identifiers refer to named objects in the entity
        model and this defines the uncode pattern for identifiers as
        follows::

                [\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}(\.[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}){0,}

        Although this expression appears complex this is basically a '.'
        separated list of name components, each of which must start with
        a letter and continue with a letter, number or underscore."""
        if self.SimpleIdentifierStartClass is None:
            self.SimpleIdentifierStartClass = CharClass(
                CharClass.UCDCategory(u"L"))
            self.SimpleIdentifierStartClass.AddClass(
                CharClass.UCDCategory(u"Nl"))
        if self.SimpleIdentifierClass is None:
            self.SimpleIdentifierClass = CharClass(
                self.SimpleIdentifierStartClass)
            for c in ['Nd', 'Mn', 'Mc', 'Pc', 'Cf']:
                self.SimpleIdentifierClass.AddClass(CharClass.UCDCategory(c))
        savepos = self.pos
        result = []
        while True:
            # each segment must start with a start character
            if self.the_char is None or not self.SimpleIdentifierStartClass.Test(self.the_char):
                self.setpos(savepos)
                return None
            result.append(self.the_char)
            self.next_char()
            while self.the_char is not None and self.SimpleIdentifierClass.Test(self.the_char):
                result.append(self.the_char)
                self.next_char()
            if not self.parse('.'):
                break
            result.append('.')
        return string.join(result, '')

    def ParseStringURILiteral(self):
        if self.parse("'"):
            # string of utf-8 characters
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            value = []
            while True:
                startPos = self.pos
                while not self.parse("'"):
                    if self.MatchEnd():
                        raise ValueError(
                            "Unterminated quote in literal string")
                    self.next_char()
                value.append(self.src[startPos:self.pos - 1])
                if self.parse("'"):
                    # a repeated SQUOTE, go around again
                    continue
                break
            value = string.join(value, "'")
            if self.raw:
                value = value.decode('utf-8')
            result.value = value
            return result
        else:
            return None

    def ParseURILiteral(self):
        """Parses a URI literal.
        
        Returns a :py:class:`pyslet.mc_csdl.SimpleType` instance or None
        if no value can be parsed.

        Important: do not confuse a return value of (the Python object)
        None with a :py:class:`pyslet.mc_csdl.SimpleValue` instance that
        tests False.  The latter is returned when the URI-literal string
        'null' is parsed.

        If a URI literal value is partially parsed but is badly formed,
        a ValueError is raised."""
        savepos = self.pos
        nameCase = self.ParseSimpleIdentifier()
        if nameCase is not None:
            name = nameCase.lower()
        else:
            name = None
        if name == "null":
            return edm.EDMValue.NewSimpleValue(None)
        elif name is None and self.match("'"):
            return self.ParseStringURILiteral()
        elif name is None and self.MatchOne('-.0123456789'):
            # one of the number forms (perhaps)
            num = self.ParseNumericLiteral()
            if num is None:
                # must be something like "." or "-" on its own, not a literal
                return None
            if self.parse_one("Dd"):
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
                result.SetFromNumericLiteral(num)
                return result
            elif self.parse_one("Ff"):
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Single)
                result.SetFromNumericLiteral(num)
                return result
            elif self.parse_one("Mm"):
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
                result.SetFromNumericLiteral(num)
                return result
            elif self.parse_one("Ll"):
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int64)
                result.SetFromNumericLiteral(num)
                return result
            else:
                result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
                result.SetFromNumericLiteral(num)
                return result
        elif name == "true":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.value = True
            return result
        elif name == "false":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
            result.value = False
            return result
        elif name == "datetimeoffset":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.DateTimeOffset)
            production = "datetimeoffset literal"
            self.require("'", production)
            dtoString = self.parse_until("'")
            self.require("'", production)
            result.SetFromLiteral(dtoString)
            return result
        elif name == "datetime":
            production = "datetime literal"
            self.require("'", production)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.DateTime)
            value = self.require_production(
                self.ParseDateTimeLiteral(), production)
            self.require("'", production)
            result.value = value
            return result
        elif name == "time":
            production = "time literal"
            self.require("'", production)
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Time)
            value = self.require_production(
                self.ParseTimeLiteral(), production)
            self.require("'", production)
            result.value = value
            return result
        elif nameCase == "X" or name == "binary":
            self.require("'", "binary")
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Binary)
            value = self.ParseBinaryLiteral()
            self.require("'", "binary literal")
            result.value = value
            return result
        elif name == "nand":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
            result.SetFromNumericLiteral(
                edm.Numeric('', "nan", None, '', None))
            return result
        elif name == "nanf":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Single)
            result.SetFromNumericLiteral(
                edm.Numeric('', "nan", None, '', None))
            return result
        elif name == "infd":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
            result.value = float("INF")
            return result
        elif name == "inff":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Single)
            result.value = float("INF")
            return result
        elif name == "guid":
            result = edm.EDMValue.NewSimpleValue(edm.SimpleType.Guid)
            self.require("'", "guid")
            hex = []
            hex.append(
                self.require_production(self.parse_hex_digits(8, 8), "guid"))
            self.require("-", "guid")
            hex.append(
                self.require_production(self.parse_hex_digits(4, 4), "guid"))
            self.require("-", "guid")
            hex.append(
                self.require_production(self.parse_hex_digits(4, 4), "guid"))
            self.require("-", "guid")
            hex.append(
                self.require_production(self.parse_hex_digits(4, 4), "guid"))
            if self.parse('-'):
                # this is a proper guid
                hex.append(
                    self.require_production(
                        self.parse_hex_digits(
                            12,
                            12),
                        "guid"))
            else:
                # this a broken guid, add some magic to make it right
                hex[3:3] = ['FFFF']
                hex.append(
                    self.require_production(self.parse_hex_digits(8, 8), "guid"))
            self.require("'", "guid")
            result.value = uuid.UUID(hex=string.join(hex, ''))
            return result
        else:
            self.setpos(savepos)
            return None
            # raise ValueError("Expected literal: %s"%repr(self.peek(10)))


def ParseURILiteral(source):
    """Parses a literal value from a source string.

    Returns a tuple of a:

            *   a constant from :py:class:`pyslet.mc_csdl.SimpleType`

            *   the value, represented with the closest python built-in type

    The special string "null" returns None,None"""
    p = Parser(uri.unescape_data(source).decode('utf-8'))
    return p.require_production_end(p.ParseURILiteral(), "uri literal")


def ParseDataServiceVersion(src):
    """Parses DataServiceVersion from a header field value.

    Returns a triple of (integer) major version, (integer) minor version and a
    user agent string.  See section 2.2.5.3 of the specification."""
    mode = "#"
    versionStr = None
    uaStr = []
    p = params.ParameterParser(src)
    versionStr = p.require_token("data service version")
    v = versionStr.split('.')
    if len(v) == 2 and grammar.is_digits(v[0]) and grammar.is_digits(v[1]):
        major = int(v[0])
        minor = int(v[1])
    else:
        raise grammar.BadSyntax(
            "Expected data service version, found %s" % versionStr)
    if p.parse_separator(";"):
        while p.the_word is not None:
            t = p.parse_token()
            if t:
                uaStr.append(t)
            else:
                break
    # we are generous in what we accept, don't bother checking for the end
    return major, minor, string.join(uaStr, ' ')


def ParseMaxDataServiceVersion(src):
    """Parses MaxDataServiceVersion from a header field value.

    Returns a triple of (integer) major version, (integer) minor version and a
    user agent string.  See section 2.2.5.7 of the specification."""
    src = src.split(';')
    versionStr = None
    uaStr = None
    if len(src) > 0:
        p = params.ParameterParser(src[0])
        versionStr = p.require_token("data service version")
        v = versionStr.split('.')
        if len(v) == 2 and grammar.is_digits(v[0]) and grammar.is_digits(v[1]):
            major = int(v[0])
            minor = int(v[1])
        else:
            raise grammar.BadSyntax(
                "Expected max data service version, found %s" % versionStr)
    else:
        raise grammar.BadSyntax("Expected max data service version")
    uaStr = string.join(src[1:], ';')
    return major, minor, uaStr


class SystemQueryOption(xsi.Enumeration):

    """SystemQueryOption defines constants for the OData-defined system query options

    Note that these options are enumerated without their '$' prefix::

            SystemQueryOption.filter
            SystemQueryOption.DEFAULT == None

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'expand': 1,
        'filter': 2,
        'orderby': 3,
        'format': 4,
        'skip': 5,
        'top': 6,
        'skiptoken': 7,
        'inlinecount': 8,
        'select': 9
    }

xsi.MakeEnumeration(SystemQueryOption)


class InlineCount(xsi.Enumeration):

    """inlinecount defines constants for the $inlinecount system query option::

            InlineCount.allpages
            InlineCount.none
            InlineCount.DEFAULT == None

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'allpages': 1,
        'none': 2
    }
xsi.MakeEnumeration(InlineCount)


class PathOption(xsi.Enumeration):

    """PathOption defines constants for the $-special values that might
    be found in the resource path, for example::

            PathOption.links
            PathOption.DEFAULT == None

    Note that these options are mutually exclusive!

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'metadata': 1,
        'batch': 2,
        'count': 3,
        'value': 4,
        'links': 5
    }
xsi.MakeEnumeration(PathOption)

#   URI1: http://host/service.svc/Customers :   Entity Set
#   URI2: http://host/service.svc/Customers('ALFKI')    :   Entity
#   URI3: http://host/service.svc/Customers('ALFKI')/Address    :   Complex Property
#   URI4: http://host/service.svc/Customers('ALFKI')/Address/Name   :   Complex+Simple Property
#           http://host/service.svc/Customers('ALFKI')/Address/Name/$value
#   URI5: http://host/service.svc/Customers('ALFKI')/CompanyName    :   Simple Property
#           http://host/service.svc/Customers('ALFKI')/CompanyName/$value
#   URI6: http://host/service.svc/Customers('ALFKI')/Orders :   Navigation property
#   URI7: http://host/service.svc/Customers('ALFKI')/$links/Orders  : links
#   URI8: http://host/service.svc/$metadata :   metadata
#   URI9: http://host/service.svc/$batch    :   batch
#   URI10: http://host/service.svc/EtFunction   : function returning entity
#   URI11: http://host/service.svc/CollCtFunction   : function returning collection of complex
#   URI12: http://host/service.svc/CtFunction   : function returning complex
#   URI13: http://host/service.svc/CollPrimFunction : function returning collection of simple values
#   URI14: http://host/service.svc/PrimFunction : function returning simple value
#   URI15: http://host/service.svc/Customers/$count : count
#   URI16: http://host/service.svc/Customers('ALFKI')/$count    : count=1
#   URI17: http://host/service.svc/Documents(1)/$value  : media resource

SupportedSystemQueryOptions = {
    1: set((
        SystemQueryOption.expand,
        SystemQueryOption.filter,
        SystemQueryOption.format,
        SystemQueryOption.orderby,
        SystemQueryOption.skip,
        SystemQueryOption.top,
        SystemQueryOption.skiptoken,
        SystemQueryOption.inlinecount,
        SystemQueryOption.select)),
    2: set((
        SystemQueryOption.expand,
        SystemQueryOption.filter,
        SystemQueryOption.format,
        SystemQueryOption.select)),
    3: set((
        SystemQueryOption.filter,
        SystemQueryOption.format)),
    4: set((
        SystemQueryOption.format,)),
    5: set((
        SystemQueryOption.format,)),
    61: set((
            SystemQueryOption.expand,
            SystemQueryOption.filter,
            SystemQueryOption.format,
            SystemQueryOption.select)),
    62: set((
            SystemQueryOption.expand,
            SystemQueryOption.filter,
            SystemQueryOption.format,
            SystemQueryOption.orderby,
            SystemQueryOption.skip,
            SystemQueryOption.top,
            SystemQueryOption.skiptoken,
            SystemQueryOption.inlinecount,
            SystemQueryOption.select)),
    7: set((
        SystemQueryOption.format,
        SystemQueryOption.skip,
        SystemQueryOption.top,
        SystemQueryOption.skiptoken,
        SystemQueryOption.inlinecount)),
    8: set(),
    9: set(),
    10: set((
            SystemQueryOption.format,)),
    11: set((
            SystemQueryOption.format,)),
    12: set((
            SystemQueryOption.format,)),
    13: set((
            SystemQueryOption.format,)),
    14: set((
            SystemQueryOption.format,)),
    15: set((
            SystemQueryOption.expand,
            SystemQueryOption.filter,
            SystemQueryOption.orderby,
            SystemQueryOption.skip,
            SystemQueryOption.top)),
    16: set((
            SystemQueryOption.expand,
            SystemQueryOption.filter)),
    17: set((
            SystemQueryOption.format,))
}
"""A mapping from URI format number to a set of supported system query options.

Note that URI6 is split into 61 and 62 based on the notes in the specification"""


def FormatExpand(expand):
    """Returns a unicode string representation of the *expand* rules."""
    result = sorted(_FormatExpandList(expand))
    return string.join(result, ',')


def _FormatExpandList(expand):
    """Returns a list of unicode strings representing the *expand* rules."""
    result = []
    for k, v in expand.iteritems():
        if not v:
            result.append(k)
        else:
            result = result + map(lambda x: "%s/%s" %
                                  (k, x), _FormatExpandList(v))
    return result


def FormatSelect(select):
    """Returns a unicode string representation of the *select* rules."""
    return FormatExpand(select)     # same implementation as expand


class ODataURI:

    """Breaks down an OData URI into its component parts.

    If the URI passed in is not a valid ODataURI then a
    :py:class:`ServerError` (or a derived exception class) is raised.

    You pass the URI (or a string) to construct the object.  You may also pass
    an optional *pathPrefix* which is a string that represents the part of the
    path that will be ignored.  In other words, *pathPrefix* is the path
    component of the service root.

    There's a little bit of confusion as to whether the service root can be
    empty or not.  An empty service root will be automatically converted to '/'
    by the HTTP protocol.  As a result, the service root often appears to
    contain a trailing slash even when it is not empty.  The sample OData server
    from Microsoft issues a temporary redirect from /OData/OData.svc to add the
    trailing slash before returning the service document."""

    def __init__(self, dsURI, pathPrefix='', version=2):
        if not isinstance(dsURI, uri.URI):
            dsURI = uri.URI.from_octets(dsURI)
        #: a :py:class:`pyslet.rfc2396.URI` instance representing the
        #: whole URI
        self.uri = dsURI
        #: the OData version of this request
        self.version = version
        #: a string containing the path prefix without a trailing slash
        self.pathPrefix = pathPrefix
        #: a string containing the resource path (or None if this is not
        #: a resource path)
        self.resourcePath = None
        #: a list of navigation path segment strings
        self.navPath = []
        #: the path option in effect or None if no path option was given
        self.pathOption = None
        #: the name of the navigation property following $links (no None)
        self.linksProperty = None
        #: a list of raw strings containing custom query options and
        #: service op params
        self.queryOptions = []
        #: a dictionary mapping :py:class:`SystemQueryOption` constants
        #: to their values
        self.sysQueryOptions = {}
        self.paramTable = {}
        if dsURI.abs_path is None:
            # relative paths are resolved relative to the pathPrefix
            # with an added slash! so
            # ODataURI('Products','/OData/OData.svc') is treated as
            # '/OData/OData.svc/Products'
            dsURI = dsURI.resolve(pathPrefix + '/')
        if dsURI.abs_path is None:
            #   both dsURI and pathPrefix are relative, this is an error
            raise ValueError("pathPrefix cannot be relative: %s" % pathPrefix)
        if pathPrefix and not dsURI.abs_path.startswith(pathPrefix):
            # this is not a URI we own
            return
        #
        #   Unpack the query
        if dsURI.query is not None:
            rawOptions = dsURI.query.split('&')
            for paramDef in rawOptions:
                if paramDef.startswith('$'):
                    param_name = uri.unescape_data(
                        paramDef[1:paramDef.index('=')]).decode('utf-8')
                    param, param_value = self.ParseSystemQueryOption(
                        param_name, uri.unescape_data(
                            paramDef[
                                paramDef.index('=') + 1:]).decode('utf-8'))
                    self.sysQueryOptions[param] = param_value
                else:
                    if '=' in paramDef:
                        param_name = uri.unescape_data(
                            paramDef[:paramDef.index('=')]).decode('utf-8')
                        self.paramTable[param_name] = len(self.queryOptions)
                    self.queryOptions.append(paramDef)
        #
        #   Unpack the resource path
        self.resourcePath = dsURI.abs_path[len(pathPrefix):]
        if self.resourcePath == '/':
            self.navPath = []
        else:
            segments = self.resourcePath.split('/')
            self.navPath = []
            for segment in segments[1:]:
                if self.pathOption == PathOption.links:
                    if self.linksProperty is not None:
                        raise InvalidPathOption(
                            "A navigation property preceded by $links must be the last path segment, found %s" %
                            segment)
                    elif segment.startswith("$"):
                        raise InvalidPathOption(
                            "A navigation property is required after $links, found %s" %
                            segment)
                    npSegment = self.SplitSegment(segment)
                    self.navPath.append(npSegment)
                    self.linksProperty = npSegment[0]
                elif segment.startswith("$"):
                    try:
                        pathOption = PathOption.DecodeLowerValue(segment[1:])
                    except KeyError:
                        raise InvalidPathOption(segment)
                    if self.pathOption is not None:
                        raise InvalidPathOption(
                            "%s must not be used with $%s" %
                            (segment,
                             PathOption.EncodeValue(
                                 self.pathOption)))
                    if self.navPath and self.pathOption in (PathOption.batch, PathOption.metadata):
                        raise InvalidPathOption(
                            "$%s must be the only path segment" %
                            PathOption.EncodeValue(
                                self.pathOption))
                    elif self.pathOption == PathOption.links:
                        if not self.navPath:
                            raise InvalidPathOption(
                                "resource path must not start with $links")
                    self.pathOption = pathOption
                else:
                    # count, value, batch and metadata must be the last segment
                    if self.pathOption in (PathOption.count, PathOption.value, PathOption.batch, PathOption.metadata):
                        raise InvalidPathOption(
                            "$%s must be the last path segment" %
                            PathOption.EncodeValue(
                                self.pathOption))
                    self.navPath.append(self.SplitSegment(segment))
            if self.pathOption == PathOption.links and self.linksProperty is None:
                raise InvalidPathOption(
                    "$links must not be the last path segment")
        if self.pathOption:
            if self.pathOption == PathOption.links:
                self.ValidateSystemQueryOptions(7)
            elif self.pathOption == PathOption.metadata:
                self.ValidateSystemQueryOptions(8)
            elif self.pathOption == PathOption.batch:
                self.ValidateSystemQueryOptions(9)
            elif self.pathOption == PathOption.count:
                if self.navPath and self.navPath[-1][1]:
                    self.ValidateSystemQueryOptions(16)
                else:
                    self.ValidateSystemQueryOptions(15)

    def ParseSystemQueryOption(self, param_name, param_value):
        """Returns a tuple of :py:class:`SystemQueryOption` constant and
        an appropriate representation of the value:

        *   filter: an instance of :py:class:`CommonExpression`

        *   expand: a list of expand options, see
            py:meth:`pyslet.mc_csdl.Entity.Expand`

        *   format: a list of :py:meth:`pyslet.http.params.MediaType`
            instances (of length 1)

        *   other options return a the param_value unchanged at the moment"""
        try:
            param = SystemQueryOption.DecodeValue(param_name)
            # Now parse the parameter value
            paramParser = Parser(param_value)
            if param == SystemQueryOption.filter:
                value = paramParser.require_production_end(
                    paramParser.ParseCommonExpression(),
                    "boolCommonExpression")
            elif param == SystemQueryOption.expand:
                value = paramParser.require_production_end(
                    paramParser.ParseExpandOption(), "expand query option")
            elif param == SystemQueryOption.format:
                # ("json" / "atom" / "xml" /
                # <a data service specific value indicating a format specific to the specific data service> /
                # <An IANA-defined [IANA-MMT] content type>)
                # first up, let's see if this is a valid MediaType
                try:
                    value = messages.AcceptList.from_str(param_value)
                except grammar.BadSyntax:
                    pLower = param_value.lower()
                    if pLower == "atom":
                        value = messages.AcceptList.from_str(
                            'application/atom+xml')
                    elif pLower == "json":
                        value = messages.AcceptList.from_str(
                            'application/json')
                    elif pLower == "xml":
                        value = messages.AcceptList.from_str('application/xml')
                    else:
                        raise InvalidSystemQueryOption(
                            "Unsupported $format : %s" % param_value)
            elif param == SystemQueryOption.orderby:
                value = paramParser.require_production_end(
                    paramParser.ParseOrderbyOption(), "orderby query option")
            elif param == SystemQueryOption.skip:
                value = paramParser.require_production_end(
                    paramParser.parse_integer(), "skip query option")
            elif param == SystemQueryOption.top:
                value = paramParser.require_production_end(
                    paramParser.parse_integer(), "top query option")
            elif param == SystemQueryOption.inlinecount:
                value = InlineCount.DecodeLowerValue(param_value)
            elif param == SystemQueryOption.select:
                value = paramParser.require_production_end(
                    paramParser.ParseSelectOption(), "selection query option")
            else:
                value = param_value
        except ValueError as e:
            raise InvalidSystemQueryOption("$%s : %s" % (param_name, str(e)))
        return param, value

    def ValidateSystemQueryOptions(self, uriNum):
        rules = SupportedSystemQueryOptions[uriNum]
        for p in self.sysQueryOptions:
            if p not in rules:
                raise InvalidSystemQueryOption(
                    '$%s cannot be used with this form of URI' %
                    SystemQueryOption.EncodeValue(p))

    def SplitSegment(self, segment):
        """Splits a string segment into a unicode name and a keyPredicate dictionary."""
        if segment.startswith('$'):
            # some type of control word
            return segment, None
        elif '(' in segment and segment[-1] == ')':
            name = uri.unescape_data(
                segment[:segment.index('(')]).decode('utf-8')
            keys = segment[segment.index('(') + 1:-1]
            if keys == '':
                keys = []
            else:
                keys = keys.split(',')
            if len(keys) == 0:
                return name, {}
            elif len(keys) == 1 and '=' not in keys[0]:
                return name, {u'': ParseURILiteral(keys[0])}
            else:
                keyPredicate = {}
                for k in keys:
                    nv = k.split('=')
                    if len(nv) != 2:
                        raise ValueError(
                            "unrecognized key predicate: %s" % repr(keys))
                    kname, value = nv
                    kname = uri.unescape_data(kname).decode('utf-8')
                    kvalue = ParseURILiteral(value)
                    keyPredicate[kname] = kvalue
                return name, keyPredicate
        else:
            return uri.unescape_data(segment).decode('utf-8'), None

    def get_param_value(self, param_name):
        if param_name in self.paramTable:
            paramDef = self.queryOptions[self.paramTable[param_name]]
            # must be a primitive type
            return ParseURILiteral(paramDef[paramDef.index('=') + 1:])
        else:
            # missing parameter is equivalent to NULL
            return edm.SimpleValue.NewSimpleValue(None)

    @classmethod
    def FormatKeyDict(cls, d):
        """Returns a URI formatted and URI escaped, entity key.

        For example, (42L), or ('Salt%20%26%20Pepper')."""
        if len(d) == 1:
            keyStr = "(%s)" % cls.FormatLiteral(d.values()[0])
        else:
            keyStr = []
            for k, v in d.iteritems():
                keyStr.append("%s=%s" % (k, cls.FormatLiteral(v)))
            keyStr = "(%s)" % string.join(keyStr, ",")
        return uri.escape_data(keyStr.encode('utf-8'))

    @classmethod
    def FormatEntityKey(cls, entity):
        return cls.FormatKeyDict(entity.KeyDict())

    @staticmethod
    def FormatLiteral(value):
        """Returns a URI-literal-formatted value as a *unicode* string.  For example, u"42L" or u"'Paddy O''brian'" """
        return unicode(LiteralExpression(value))

    @staticmethod
    def FormatSysQueryOptions(sysQueryOptions):
        return string.join(
            map(lambda x: "$%s=%s" % (
                str(SystemQueryOption.EncodeValue(x[0])),
                uri.escape_data(x[1].encode('utf-8'))),
                sysQueryOptions.items()),
            '&')


class StreamInfo(object):

    """Represents information about a media resource stream."""

    def __init__(self, type=params.APPLICATION_OCTETSTREAM,
                 created=None, modified=None, size=None):
        #: the media type, a :py:class:`~pyslet.http.params.MediaType`
        #: instance
        self.type = type
        #: the optional creation time, a fully specified
        #: :py:class:`~pyslet.iso8601.TimePoint` instance that
        #: includes a zone
        self.created = created
        #: the optional modification time, a fully specified
        #: :py:class:`~pyslet.iso8601.TimePoint` instance that
        #: includes a zone
        self.modified = modified
        #: the size of the stream (in bytes), None if not known
        self.size = size
        #: the 16 byte binary MD5 checksum of the stream, None if not
        #: known
        self.md5 = None


class Entity(edm.Entity):

    """We override Entity in order to provide OData serialisation."""

    def get_location(self):
        return uri.URI.from_octets(
            str(self.entity_set.get_location()) + ODataURI.FormatEntityKey(self))

    def get_content_type(self):
        with self.entity_set.OpenCollection() as collection:
            return collection.read_stream(self.key()).type

    def GetStreamType(self):    # noqa
        warnings.warn("Entity.GetStreamType is deprecated, "
                      "use collection.read_stream(key).type",
                      DeprecationWarning, stacklevel=2)
        with self.entity_set.OpenCollection() as collection:
            return collection.read_stream(self.key()).type

    def GetStreamSize(self):    # noqa
        warnings.warn("Entity.GetStreamSize is deprecated, "
                      "use collection.read_stream(key).size",
                      DeprecationWarning, stacklevel=2)
        with self.entity_set.OpenCollection() as collection:
            return collection.read_stream(self.key()).size

    def GetStreamGenerator(self):   # noqa
        warnings.warn("Entity.GetStreamGenerator is deprecated, "
                      "use collection.read_stream_close(key)",
                      DeprecationWarning, stacklevel=2)
        collection = self.entity_set.OpenCollection()
        try:
            return collection.read_stream_close(self.key())[1]
        except Exception:
            collection.close()
            raise

    def set_from_json_object(self, obj, entity_resolver=None,
                             for_update=False):
        """Sets the value from a JSON representation.

        obj
            A python dictionary parsed from a JSON representation

        entity_resolver
            An optional callable that takes a URI object and returns the
            entity object it points to.  This is used for resolving
            links when creating or updating entities from a JSON source.

        for_update
            An optional boolean (defaults to False) that indicates if an
            *existing* entity is being deserialised for update or just
            for read access.  When True, new bindings are added to the
            entity for links provided in the obj.  If the entity doesn't
            exist then this argument is ignored."""
        for k, v in self.data_items():
            if k in obj:
                if isinstance(v, edm.SimpleValue):
                    ReadEntityPropertyValueInJSON(v, obj[k])
                else:
                    # assume a complex value then
                    ReadEntityCTValue(v, obj[k])
            else:
                v.set_from_value(None)
        if self.exists == False:
            # we need to look for any link bindings
            for navProperty in self.NavigationKeys():
                if navProperty not in obj:
                    continue
                links = obj[navProperty]
                if not self.IsEntityCollection(navProperty):
                    # wrap singletons for convenience
                    links = (links,)
                targetSet = self.entity_set.NavigationTarget(navProperty)
                with targetSet.OpenCollection() as collection:
                    for link in links:
                        if len(link) == 1 and '__metadata' in link:
                            # bind to an existing entity
                            href = uri.URI.from_octets(
                                link['__metadata']['uri'])
                            if entity_resolver is not None:
                                if not href.is_absolute():
                                    #   we'll assume that the base URI is the
                                    #   location of this entity once it is
                                    #   created.  Witness this thread:
                                    #   http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                                    href = href.resolve(self.get_location())
                                targetEntity = entity_resolver(href)
                                if isinstance(targetEntity, Entity) and targetEntity.entity_set is targetSet:
                                    self[navProperty].BindEntity(targetEntity)
                                else:
                                    raise InvalidData(
                                        "Resource is not a valid target for %s: %s" %
                                        (navProperty, str(href)))
                            else:
                                raise InvalidData(
                                    "No context to resolve entity URI: %s" %
                                    str(link))
                        else:
                            # full inline representation is expected for deep
                            # insert
                            targetEntity = collection.new_entity()
                            targetEntity.set_from_json_object(
                                link, entity_resolver)
                            self[navProperty].BindEntity(targetEntity)
        elif for_update:
            # we need to look for any updated link bindings
            for navProperty in self.NavigationKeys():
                if navProperty not in obj or self.IsEntityCollection(navProperty):
                    # missing or can't be updated these this way
                    continue
                link = obj[navProperty]
                if '__metadata' in link:
                    targetSet = self.entity_set.NavigationTarget(navProperty)
                    # bind to an existing entity
                    href = uri.URI.from_octets(link['__metadata']['uri'])
                    if entity_resolver is not None:
                        if not href.is_absolute():
                            #   we'll assume that the base URI is the
                            #   location of this entity.  Witness this thread:
                            #   http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                            href = href.resolve(self.get_location())
                        targetEntity = entity_resolver(href)
                        if isinstance(targetEntity, Entity) and targetEntity.entity_set is targetSet:
                            self[navProperty].BindEntity(targetEntity)
                        else:
                            raise InvalidData(
                                "Resource is not a valid target for %s: %s" %
                                (navProperty, str(href)))
                    else:
                        raise InvalidData(
                            "No context to resolve entity URI: %s" % str(link))

    def generate_entity_type_in_json(self, for_update=False, version=2):
        """Returns a JSON-encoded string representing this entity

        for_update
            A boolean, defaults to False, indicating that the output
            JSON should include any unsaved bindings

        version
            Defaults to version 2 output"""
        location = str(self.get_location())
        mediaLinkResource = self.type_def.has_stream()
        yield '{"__metadata":{'
        yield '"uri":%s' % json.dumps(location)
        yield ',"type":%s' % json.dumps(self.entity_set.entityType.GetFQName())
        etag = self.ETag()
        if etag:
            s = "" if self.ETagIsStrong() else "W/"
            yield ',"etag":%s' % json.dumps(s + grammar.quote_string(string.join(map(ODataURI.FormatLiteral, etag), ',')))
        if mediaLinkResource:
            yield ',"media_src":%s' % json.dumps(location + "/$value")
            yield ',"content_type":%s' % json.dumps(str(self.get_content_type()))
            yield ',"edit_media":%s' % json.dumps(location + "/$value")
            if etag:
                s = "" if self.ETagIsStrong() else "W/"
                yield ',"media_etag":%s' % json.dumps(s + grammar.quote_string(string.join(map(ODataURI.FormatLiteral, etag), ',')))
        yield '}'
        for k, v in self.data_items():
            # watch out for unselected properties
            if self.Selected(k):
                yield ','
                if isinstance(v, edm.SimpleValue):
                    yield EntityPropertyInJSON(v)
                else:
                    yield EntityCTBody(v)
        if self.exists and not for_update:
            for navProperty, navValue in self.NavigationItems():
                if self.Selected(navProperty):
                    yield ', %s' % json.dumps(navProperty)
                    if navValue.isExpanded:
                        yield ':'
                        if navValue.isCollection:
                            with navValue.OpenCollection() as collection:
                                for y in collection.generate_entity_set_in_json(version):
                                    yield y
                        else:
                            entity = navValue.GetEntity()
                            if entity:
                                for y in entity.generate_entity_type_in_json(False, version):
                                    yield y
                            else:
                                yield json.dumps(None)
                    else:
                        yield ':{"__deferred":{"uri":%s}}' % json.dumps(location + '/' + navProperty)
        elif for_update:
            for k, dv in self.NavigationItems():
                if not dv.bindings or dv.isCollection:
                    # nothing to do here, we can't update this type of
                    # navigation property
                    continue
                # we need to know the location of the target entity set
                targetSet = dv.Target()
                binding = dv.bindings[-1]
                if isinstance(binding, Entity):
                    if binding.exists:
                        href = str(targetSet.get_location()) + \
                            ODataURI.FormatEntityKey(binding)
                    else:
                        # we can't create new entities on update
                        continue
                else:
                    href = str(
                        targetSet.get_location()) + ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
                yield ', %s:{"__metadata":{"uri":%s}}' % (json.dumps(k), json.dumps(href))
        else:
            for k, dv in self.NavigationItems():
                if not dv.bindings:
                    continue
                targetSet = dv.Target()
                yield ', %s :[' % json.dumps(k)
                sep = False
                for binding in dv.bindings:
                    if sep:
                        yield ', '
                    else:
                        sep = True
                    if isinstance(binding, Entity):
                        if binding.exists:
                            href = str(targetSet.get_location()) + \
                                ODataURI.FormatEntityKey(binding)
                        else:
                            # we need to yield the entire entity instead
                            for s in binding.generate_entity_type_in_json():
                                yield s
                            href = None
                    else:
                        href = str(
                            targetSet.get_location()) + ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
                    if href:
                        yield '{ "__metadata":{"uri":%s}}' % json.dumps(href)
                yield ']'
        yield '}'

    def link_json(self):
        """Returns a JSON-serialised link to this entity"""
        return '{"uri":%s}' % json.dumps(str(self.get_location()))


def EntityCTInJSON2(complexValue):
    """Return a version 2 JSON complex entity."""
    return '{"results":%s}' % EntityCTInJSON(complexValue)


def ReadEntityCTInJSON2(complexValue, obj):
    if "results" in obj and isinstance(obj["results"], DictType):
        obj = obj["results"]
        ReadEntityCTInJSON(complexValue, obj)


def EntityCTInJSON(complexValue):
    """Return a version 1 JSON complex entity - specification seems to be incorrect here."""
    return '{%s}' % EntityCTBody(complexValue)


def ReadEntityCTInJSON(complexValue, obj):
    if complexValue.pDef.name in obj:
        ReadEntityCTValue(complexValue, obj[complexValue.pDef.name])


def EntityCTBody(complexValue):
    return "%s:%s" % (json.dumps(
        complexValue.pDef.name),
        EntityCTValueToJSON(complexValue))


def EntityCTValueToJSON(complexValue):
    result = []
    for k, v in complexValue.iteritems():
        if isinstance(v, edm.SimpleValue):
            value = EntityPropertyInJSON(v)
        else:
            value = EntityCTBody(v)
        result.append(value)
    return "{%s}" % string.join(result, ',')


def ReadEntityCTValue(complexValue, obj):
    for k, v in complexValue.iteritems():
        if k in obj:
            if isinstance(v, edm.SimpleValue):
                ReadEntityPropertyValueInJSON(v, obj[k])
            else:
                ReadEntityCTValue(v, obj[k])
        else:
            v.set_from_value(None)


TICKS_PER_DAY = 86400000
BASE_DAY = iso.Date.from_str('1970-01-01').GetAbsoluteDay()


def EntityPropertyInJSON2(simpleValue):
    """Return a version 2 JSON simple value."""
    return '{"results":{%s}}' % EntityPropertyInJSON(simpleValue)


def EntityPropertyInJSON1(simpleValue):
    """Returns a version 1 JSON simple value.

    Not defined by the specification but useful for generating request/response bodies."""
    return '{%s}' % EntityPropertyInJSON(simpleValue)


def ReadEntityPropertyInJSON1(simpleValue, obj):
    if simpleValue.pDef.name in obj:
        ReadEntityPropertyValueInJSON(simpleValue, obj[simpleValue.pDef.name])


def EntityPropertyInJSON(simpleValue):
    return "%s:%s" % (json.dumps(
        simpleValue.pDef.name),
        EntityPropertyValueInJSON(simpleValue))


def EntityPropertyValueInJSON(v):
    if not v:
        return 'null'
    elif isinstance(v, edm.BinaryValue):
        # unusual representation as we use base64 encoding
        return json.dumps(base64.b64encode(v.value))
    elif isinstance(v, (edm.BooleanValue, edm.ByteValue, edm.Int16Value, edm.Int32Value, edm.SByteValue)):
        # naked representation
        return unicode(v)
    elif isinstance(v, edm.DateTimeValue):
        # a strange format based on ticks, by definition, DateTime has no
        # offset
        ticks = (v.value.date.GetAbsoluteDay() - BASE_DAY) * \
            TICKS_PER_DAY + int(v.value.time.GetTotalSeconds() * 1000)
        return json.dumps("/Date(%i)/" % ticks)
    elif isinstance(v, (edm.DecimalValue, edm.DoubleValue, edm.GuidValue, edm.Int64Value, edm.SingleValue, edm.StringValue, edm.TimeValue)):
        # just use the literal form as a json string
        return json.dumps(unicode(v))
    elif isinstance(v, (edm.DateTimeOffsetValue)):
        # a strange format based on ticks, by definition, DateTime has no
        # offset
        ticks = (v.value.date.GetAbsoluteDay() - BASE_DAY) * \
            TICKS_PER_DAY + int(v.value.time.GetTotalSeconds() * 1000)
        dir, offset = v.GetZone()
        if dir > 0:
            s = u"+"
        else:
            s = u"-"
        return json.dumps("/Date(%i%s%04i)/" % (ticks, s, offset))
    else:
        raise ValueError("SimpleValue: %s" % repr(v))


def ReadEntityPropertyValueInJSON(v, jsonValue):
    """Given a simple property value parsed from a json representation,
    *jsonValue* and a :py:class:`SimpleValue` instance, *v*, update *v*
    to reflect the parsed value."""
    if jsonValue is None:
        v.set_from_value(None)
    elif isinstance(v, edm.BinaryValue):
        v.set_from_value(base64.b64decode(jsonValue))
    elif isinstance(v, (edm.BooleanValue, edm.ByteValue, edm.Int16Value, edm.Int32Value, edm.SByteValue)):
        v.set_from_value(jsonValue)
    elif isinstance(v, edm.DateTimeValue):
        if jsonValue.startswith("/Date(") and jsonValue.endswith(")/"):
            ticks = int(jsonValue[6:-2])
            t, overflow = iso.Time().Offset(seconds=ticks / 1000.0)
            d = iso.Date(absoluteDay=BASE_DAY + overflow)
            v.set_from_value(iso.TimePoint(date=d, time=t))
        else:
            raise ValueError("Illegal value for DateTime: %s" % jsonValue)
    elif isinstance(v, (edm.DecimalValue, edm.DoubleValue, edm.GuidValue, edm.Int64Value, edm.SingleValue, edm.StringValue, edm.TimeValue)):
        # just use the literal form as a json string
        v.SetFromLiteral(jsonValue)
    elif isinstance(v, (edm.DateTimeOffsetValue)):
        if jsonValue.startswith("/Date(") and jsonValue.endswith(")/"):
            ticks = int(jsonValue[6:-2])
            if '+' in ticks:
                # split by +
                ticks = ticks.split('+')
                zDir = 1
            elif '-' in ticks:
                # split by -
                ticks = ticks.split('-')
                zDir = -1
            else:
                zDir = 0
            if zDir:
                if len(ticks) != 2:
                    raise ValueError(
                        "Illegal value for DateTimeOffset: %s" % jsonValue)
                zOffset = int(ticks[1])
            else:
                zOffset = 0
            t, overflow = Time().Offset(
                seconds=int(ticks[0]) / 1000.0).WithZone(zDir, zOffset // 60, zOffset % 60)
            d = Date(absoluteDay=BASE_DAY + overflow)
            v.set_from_value(iso.TimePoint(date=d, time=t))
        else:
            raise ValueError(
                "Illegal value for DateTimeOffset: %s" % jsonValue)
    else:
        raise ValueError("Expected SimpleValue: %s" % repr(v))


class EntityCollection(edm.EntityCollection):

    """EntityCollections that provide OData-specific options

    Our definition of EntityCollection is designed for use with Python's
    diamond inheritance model.  We inherit directly from the basic
    :py:class:`pyslet.odata2.csdl.EntityCollection` object, providing
    additional methods that support the expression model defined by
    OData, media link entries and JSON encoding."""

    def get_next_page_location(self):
        """Returns the location of this page of the collection

        The result is a :py:class:`rfc2396.URI` instance."""
        token = self.next_skiptoken()
        if token is not None:
            baseURL = self.get_location()
            sysQueryOptions = {}
            if self.filter is not None:
                sysQueryOptions[
                    SystemQueryOption.filter] = unicode(self.filter)
            if self.expand is not None:
                sysQueryOptions[
                    SystemQueryOption.expand] = FormatExpand(self.expand)
            if self.select is not None:
                sysQueryOptions[
                    SystemQueryOption.select] = FormatSelect(self.select)
            if self.orderby is not None:
                sysQueryOptions[
                    SystemQueryOption.orderby] = CommonExpression.OrderByToString(
                    self.orderby)
            sysQueryOptions[SystemQueryOption.skiptoken] = unicode(token)
            return uri.URI.from_octets(
                str(baseURL) +
                "?" +
                ODataURI.FormatSysQueryOptions(sysQueryOptions))
        else:
            return None

    def new_entity(self):
        """Returns an OData aware instance"""
        return Entity(self.entity_set)

    def is_medialink_collection(self):
        """Returns True if this is a collection of Media-Link Entries"""
        return self.entity_set.entityType.has_stream()

    def new_stream(self, src, sinfo=None, key=None):
        """Creates a media resource.

        src
            A file-like object from which the stream's data will be read.

        sinfo
            A :py:class:`StreamInfo` object containing metadata about
            the stream.  If the size field of sinfo is set then *at
            most* sinfo.size bytes are read from src. Otherwise src is
            read until the end of the file.

        key
            The key associated with the stream being written.  This
            value is taken as a suggestion for the key to use, its use
            is not guaranteed.  The key actually used to store the
            stream can be obtained from the resulting entity.

        Returns the media-link entry :py:class:`Entity`"""
        if not self.is_medialink_collection():
            raise ExpectedMediaLinkCollection
        raise NotImplementedError

    def update_stream(self, src, key, sinfo=None):
        """Updates an existing media resource.

        The parameters are the same as :py:meth:`new_stream` except that
        the key must be present and must be an existing key in the
        collection."""
        if not self.is_medialink_collection():
            raise ExpectedMediaLinkCollection
        raise NotImplementedError

    def read_stream(self, key, out=None):
        """Reads a media resource.

        key
            The key associated with the stream being read.

        out
            An optional file like object to which the stream's data will
            be written. If no output file is provided then no data is
            written.

        The return result is the :py:class:`StreamInfo` class describing
        the stream."""
        if not self.is_medialink_collection():
            raise ExpectedMediaLinkCollection
        raise NotImplementedError

    def read_stream_close(self, key):
        """Creates a generator for a media resource.

        key
            The key associated with the stream being read.

        The return result is a tuple of the :py:class:`StreamInfo` class
        describing the stream and a generator that yields the stream's
        data.

        The collection is closed by the generator when the iteration is
        complete (or when the generator is destroyed)."""
        if not self.is_medialink_collection():
            raise ExpectedMediaLinkCollection
        raise NotImplementedError

    def check_filter(self, entity):
        """Checks *entity* against any filter and returns True if it passes.

        The *filter* object must be an instance of
        py:class:`CommonExpression` that returns a Boolean value.

        *boolExpression* is a :py:class:`CommonExpression`.  """
        if self.filter is None:
            return True
        else:
            result = self.filter.Evaluate(entity)
            if isinstance(result, edm.BooleanValue):
                return result.value         #: NULL treated as False
            else:
                raise ValueError("Boolean required for filter expression")

    def calculate_order_key(self, entity, orderObject):
        """Evaluates orderObject as an instance of py:class:`CommonExpression`."""
        return orderObject.Evaluate(entity).value

    def generate_entity_set_in_json(self, version=2):
        """Generates JSON serialised form of this collection."""
        if version < 2:
            yield "["
        else:
            yield "{"
            if self.inlinecount:
                yield '"__count":%s,' % json.dumps(len(self))
            yield '"results":['
        sep = False
        for entity in self.iterpage():
            if not sep:
                sep = True
            else:
                yield ','
            for s in entity.generate_entity_type_in_json(False, version):
                yield s
        if version < 2:
            yield "]"
        else:
            # add a next link if necessary
            nextLink = self.get_next_page_location()
            if nextLink is not None:
                yield '],"__next":{"uri":%s}}' % json.dumps(str(nextLink))
            else:
                yield ']}'

    def generate_link_coll_json(self, version=2):
        """Generates JSON serialised collection of links"""
        if version < 2:
            yield "["
        else:
            yield "{"
            if self.inlinecount:
                yield '"__count":%s,' % json.dumps(len(self))
            yield '"results":['
        sep = False
        for entity in self.iterpage():
            if not sep:
                sep = True
            else:
                yield ','
            yield '{"uri":%s}' % json.dumps(str(entity.get_location()))
        if version < 2:
            yield "]"
        else:
            # add a next link if necessary
            skiptoken = self.next_skiptoken()
            if skiptoken is not None:
                yield '],"__next":{"uri":%s}}' % json.dumps(str(self.get_location()) +
                                                            "?$skiptoken=%s" % uri.escape_data(skiptoken, uri.is_query_reserved))
            else:
                yield ']}'


class NavigationCollection(EntityCollection, edm.NavigationCollection):

    """NavigationCollections that provide OData-specific options.

    This class uses Python's diamond inheritance model

    .. image:: /images/navcollection.png

    This allows us to inherit from both the OData-specific form of
    EntityCollection and NavigationCollection.  This is illustrated in
    the above diagram which shows the method resolution order reading
    from the bottom of the diagram.  The default object is omitted.

    This technique is repeated in specific implementations of the API
    where common collection behaviour is implemented in a class that
    inherits from :py:class:`EntityCollection` and then mixed in to a
    new class derived from :py:class:`NavigationCollection`."""

    def expand_collection(self):
        """Return an expanded version of this collection

        Returns an instance of an OData-specific
        :py:class:`ExpandedEntityCollection`."""
        return ExpandedEntityCollection(
            from_entity=self.from_entity,
            name=self.name,
            entity_set=self.entity_set,
            entityList=self.values())

    def get_location(self):
        """Returns the location of this collection as a
        :py:class:`rfc2396.URI` instance.

        We override the location based on the source entity set + the fromKey."""
        return uri.URI.from_octets(string.join([
            str(self.from_entity.get_location()),
            '/',
            uri.escape_data(self.name)], ''))

    def get_title(self):
        return self.name


class ExpandedEntityCollection(EntityCollection, edm.ExpandedEntityCollection):

    """Expanded collections with OData-specific behaviour.

    This class uses diamond inheritance in a similar way to
    :py:class:`NavigationCollection`"""
    pass


class FunctionEntityCollection(EntityCollection, edm.FunctionEntityCollection):

    """We override FunctionEntityCollection in order to include the OData-specific behaviour.

    This class uses diamond inheritance in a similar way to
    :py:class:`NavigationCollection`"""
    pass


class FunctionCollection(edm.FunctionCollection):

    """We override FunctionCollection in order to inclue the OData-specific behaviour."""

    def GenerateCollectionInJSON(self, version=2):
        """Generates JSON serialised form of this collection."""
        if version < 2:
            yield "["
        else:
            yield "{"
            yield '"results":['
        sep = False
        for value in self:
            if not sep:
                sep = True
            else:
                yield ','
            if isinstance(value, edm.SimpleValue):
                yield EntityPropertyValueInJSON(value)
            else:
                yield EntityCTValueToJSON(value)
        if version < 2:
            yield "]"
        else:
            yield ']}'


class ODataElement(xmlns.XMLNSElement):

    """Base class for all OData specific elements."""
    pass


class Property(ODataElement):

    """Represents each property value.

    The OData namesapce does not define elements in the dataservices space as
    the elements take their names from the properties themselves.  Therefore,
    the xmlname of each Property instance is the property name."""

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        # an :py:class:`pyslet.mc_csdl.EDMValue` instance
        self.edmValue = None

    def GetSimpleType(self):
        type = self.GetNSAttribute((ODATA_METADATA_NAMESPACE, 'type'))
        if type:
            try:
                type = edm.SimpleType.DecodeLowerValue(type.lower())
            except ValueError:
                # assume unknown, probably complex
                type = None
            return type
        else:
            return None

    def GetValue(self, value=None):
        """Gets an appropriately typed value for the property.

        Overloads the basic
        :py:meth:`~pyslet.xml20081126.structures.Element.GetValue`
        implementation to transform the value into an
        :py:class:`pyslet.mc_csdl.EDMValue` instance.

        An optional :py:class:`pyslet.mc_csdl.EDMValue` can be passed,
        if present the instance's value is updated with the value of
        this Property element."""
        null = self.GetNSAttribute((ODATA_METADATA_NAMESPACE, 'null'))
        null = (null and null.lower() == "true")
        if value is None:
            entry = self.FindParent(Entry)
            if entry and entry.entityType:
                propertyDef = entry.entityType.get(self.xmlname, None)
            else:
                propertyDef = None
            if propertyDef:
                value = propertyDef()
            else:
                # picks up top-level properties only!
                pList = list(self.FindChildrenBreadthFirst(Property, False))
                if pList:
                    # we have a complex type with no definition
                    value = edm.Complex()
                else:
                    type = self.GetSimpleType()
                    if type is None:
                        # unknown simple types treated as string
                        type = edm.SimpleType.String
                    p = edm.Property(None)
                    p.name = self.xmlname
                    p.simpleTypeCode = type
                    value = edm.EDMValue.NewValue(p)
        if isinstance(value, edm.SimpleValue):
            if null:
                value.value = None
            else:
                value.SetFromLiteral(ODataElement.GetValue(self))
        else:
            # you can't have a null complex value BTW
            for child in self.GetChildren():
                if isinstance(child, Property):
                    if child.xmlname in value:
                        child.GetValue(value[child.xmlname])
                    else:
                        value.AddProperty(child.xmlname, child.GetValue())
        return value

    def SetValue(self, value):
        """Sets the value of the property

        The null property is updated as appropriate.

        When changing the value of an existing property we must match
        the existing type.  For new property values we use the value
        type to set the type property."""
        # start with a clean slate, remove attributes too
        self.reset(True)
        if isinstance(value, edm.SimpleValue):
            if self.parent is None:
                # If we have no parent then we set the type attribute
                self.SetAttribute(
                    (ODATA_METADATA_NAMESPACE,
                     'type'),
                    edm.SimpleType.EncodeValue(
                        value.typeCode))
            if value:
                ODataElement.SetValue(self, unicode(value))
            else:
                self.SetAttribute((ODATA_METADATA_NAMESPACE, 'null'), "true")
        elif isinstance(value, edm.Complex):
            if value.type_def:
                self.SetAttribute(
                    (ODATA_METADATA_NAMESPACE, 'type'), value.type_def.name)
            else:
                raise ValueError(
                    "Complex-valued properties must have a defined type")
            # loop through our children and set them from this value
            for key, v in value.iteritems():
                child = self.ChildElement(
                    self.__class__, (ODATA_DATASERVICES_NAMESPACE, key))
                child.SetValue(v)
        elif value is None:
            # this is a special case, meaning Null
            self.SetAttribute((ODATA_METADATA_NAMESPACE, 'null'), "true")
        else:
            raise TypeError("Expected EDMValue instance")


class Properties(ODataElement):

    """Represents the properties element."""
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'properties')
    XMLCONTENT = xml.ElementType.ElementContent

    PropertyClass = Property

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.Property = []

    def GetChildren(self):
        return itertools.chain(
            self.Property,
            ODataElement.GetChildren(self))


class Collection(ODataElement):

    """Represents the result of a service operation that returns a collection of values."""
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'collection')

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.Property = []

    def GetChildren(self):
        return itertools.chain(
            self.Property,
            ODataElement.GetChildren(self))


class Content(atom.Content):

    """Overrides the default :py:class:`pyslet.rfc4287.Content` class to add OData handling."""

    def __init__(self, parent):
        atom.Content.__init__(self, parent)
        self.type = 'application/xml'
        #: the optional properties element containing the entry's property values
        self.Properties = None

    def GetChildren(self):
        for child in atom.Content.GetChildren(self):
            yield child
        if self.Properties:
            yield self.Properties


class Feed(atom.Feed):

    """Overrides the default :py:class:`pyslet.rfc4287.Feed` class to add OData handling."""

    def __init__(self, parent, collection=None):
        super(Feed, self).__init__(parent)
        #: the collection this feed represents
        self.collection = collection
        if self.collection is not None:
            location = str(self.collection.get_location())
            self.AtomId.SetValue(location)
            self.Title.SetValue(self.collection.get_title())
            link = self.ChildElement(self.LinkClass)
            link.href = location
            link.rel = "self"
        self.Count = None

    def GetChildren(self):
        """Overridden to add generation of entries dynamically from :py:attr:`collection`.

        The collection's
        :py:meth:`pyslet.mc_csdl.EntityCollection.iterpage` method is
        used to iterate over the entities."""
        for child in super(Feed, self).GetChildren():
            yield child
        if self.Count:
            yield self.Count
        if self.collection is not None:
            if self.collection.inlinecount:
                count = Count(self)
                count.SetValue(len(self.collection))
                yield count
            for entity in self.collection.iterpage():
                yield Entry(self, entity)
            # add a next link if necessary
            nextLink = self.collection.get_next_page_location()
            if nextLink is not None:
                link = Link(self)
                link.rel = "next"
                link.href = str(nextLink)
                yield link

    def AttachToDocument(self, doc=None):
        """Overridden to prevent unnecessary iterations through the set of children.

        Our children do not have XML IDs"""
        return

    def DetachFromDocument(self, doc=None):
        """Overridden to prevent unnecessary iterations through the set of children.

        Our children do not have XML IDs"""
        return


class Inline(ODataElement):

    """Implements inline handling of expanded links."""
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'inline')
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(Inline, self).__init__(parent)
        self.Feed = None
        self.Entry = None

    def GetChildren(self):
        if self.Feed:
            yield self.Feed
        if self.Entry:
            yield self.Entry
        for child in super(Inline, self).GetChildren():
            yield child


class Count(ODataElement):

    """Implements inlinecount handling."""
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'count')

    def SetValue(self, new_value):
        super(Count, self).SetValue(str(new_value))

    def GetValue(self):
        return int(super(Count, self).GetValue())


class Link(atom.Link):

    """Overrides the default :py:class:`pyslet.rfc4287.Link` class to add OData handling."""
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(Link, self).__init__(parent)
        self.Inline = None

    def GetChildren(self):
        if self.Inline:
            yield self.Inline
        for child in super(Link, self).GetChildren():
            yield child

    def Expand(self, expansion):
        """Expands this element based on expansion."""
        inline = self.ChildElement(Inline)
        if isinstance(expansion, Entity):
            # it is hard to calculate the id
            entry = inline.ChildElement(Entry)
            entry.SetValue(expansion)
        elif expansion:
            # we only add the feed if it is non-empty
            feed = inline.ChildElement(Feed)
            feed.collection = expansion
            feed.ChildElement(atom.AtomId).SetValue(self.href)

    def LoadExpansion(self, deferred, exists=True):
        """Given a :py:class:`csdl.DeferredProperty` instance, adds an expansion if one is present in the link"""
        if self.Inline is not None:
            targetEntitySet = deferred.Target()
            with targetEntitySet.OpenCollection() as collection:
                if self.Inline.Entry is not None:
                    entity = collection.new_entity()
                    entity.exists = exists
                    self.Inline.Entry.GetValue(entity)
                    entries = [entity]
                elif self.Inline.Feed is not None:
                    entries = []
                    for entry in self.Inline.Feed.FindChildrenDepthFirst(Entry, subMatch=False):
                        entity = collection.new_entity()
                        entity.exists = exists
                        entry.GetValue(entity)
                        entries.append(entity)
                deferred.SetExpansion(
                    ExpandedEntityCollection(
                        from_entity=deferred.from_entity,
                        name=deferred.name,
                        entity_set=targetEntitySet,
                        entityList=entries))


class Entry(atom.Entry):

    """Overrides the default :py:class:`pyslet.rfc4287.Entry` class to add OData handling.

    In addition to the default *parent* element an Entry can be passed
    an optional `pyslet.mc_csdl.Entity` instance.  If present, it is
    used to construct the content of the entity.

    Finally, if *id* is also passed it is treated as the base URI of the entry and
    used to create the <id> and associated links."""
    ContentClass = Content
    LinkClass = Link

    def __init__(self, parent, entity=None):
        atom.Entry.__init__(self, parent)
        #: :py:class:`pyslet.mc_csdl.EntityType` instance describing the entry
        self.entityType = None
        #: properties element will be a direct child for media link entries
        self.Properties = None
        #: the etag associated with this entry or None if optimistic concurrency is not supported
        self.etag = None
        self._properties = {}
        if entity is not None:
            self.SetValue(entity)

    def reset(self):
        if self.Properties:
            self.Properties.DetachFromParent()
            self.Properties = None
        self.etag = None
        self._properties = {}
        super(Entry, self).reset()

    def GetChildren(self):
        """Replaces the implementation in atom.Entry completed so that
        we can put the content last.  You never know, it is possible
        that someone will parse the metadata and properties and decide
        they don't want the content element and close the connection.
        The other way around might be annoying for large media
        resources."""
        for child in atom.Entity.GetChildren(self):
            yield child
        if self.Published:
            yield self.Published
        if self.Source:
            yield self.Source
        if self.Summary:
            yield self.Summary
        if self.Properties:
            yield self.Properties
        if self.Content:
            yield self.Content

    def content_changed(self):
        atom.Entry.content_changed(self)
        self._properties = {}
        if self.Content and self.Content.Properties:
            pList = self.Content.Properties
        else:
            pList = self.Properties
        if pList:
            for p in pList.Property:
                self._properties[p.xmlname] = p

    def __getitem__(self, key):
        """Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to read property values.

        Returns the value of the property with *key* as a
        `pyslet.mc_csdl.EDMValue` instance."""
        return self._properties[key].GetValue()

    def __setitem__(self, key, value):
        """Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to set property values.

        Sets the property *key* to *value*.  See
        :py:meth:`Property.SetValue` for more information."""
        if key in self._properties:
            p = self._properties[key].SetValue(value)
        else:
            if self.Properties is None:
                ps = self.ChildElement(
                    self.ContentClass).ChildElement(Properties)
            else:
                ps = self.Properties
            p = ps.ChildElement(
                ps.PropertyClass, (ODATA_DATASERVICES_NAMESPACE, key))
            p.SetValue(value)
            self._properties[key] = p

    def ResolveTargetPath(self, targetPath, prefix, ns):
        doc = self.GetDocument()
        targetElement = self
        for ename in targetPath:
            newTargetElement = None
            for eTest in targetElement.GetChildren():
                if eTest.GetXMLName() == ename:
                    newTargetElement = eTest
                    break
            if newTargetElement is None:
                # we need to create a new element
                eClass = targetElement.get_element_class(ename)
                if eClass is None and doc:
                    eClass = doc.get_element_class(ename)
                if eClass is None:
                    eClass = Document.get_element_class(ename)
                newTargetElement = targetElement.ChildElement(eClass, ename)
                if ename[0] == ns and newTargetElement.GetPrefix(ename[0]) is None:
                    # No prefix exists for this namespace, make one
                    newTargetElement.MakePrefix(ns, prefix)
            targetElement = newTargetElement
        return targetElement

    def GetValue(self, entity, entity_resolver=None, for_update=False):
        """Update *entity* to reflect the value of this Entry.

        *entity* must be an :py:class:`pyslet.mc_csdl.Entity`
        instance.  It is required but is also returned for consistency
        with the behaviour of the overridden method.

        When reading entities that don't yet exist, or values
        *for_update* an entity_resolver may be required.  It is a callable
        that accepts a single parameter of type
        :py:class:`pyslet.rfc2396.URI` and returns a an object
        representing the resource it points to."""
        selected = set()
        unselected = set()
        for k, v in entity.data_items():
            # catch property-level feed customisation here
            propertyDef = entity.type_def[k]
            targetPath = propertyDef.get_target_path()
            if targetPath and not propertyDef.keep_in_content():
                # This value needs to be read from somewhere special
                prefix, ns = propertyDef.get_fc_ns_prefix()
                targetElement = self.ResolveTargetPath(targetPath, prefix, ns)
                if isinstance(targetElement, atom.Date):
                    dtOffset = targetElement.GetValue()
                    if isinstance(v, edm.DateTimeOffsetValue):
                        v.set_from_value(dtOffset)
                    elif isinstance(v, edm.DateTimeValue):
                        # strip the zone and use that
                        v.set_from_value(dtOffset.WithZone(zDirection=None))
                    elif isinstance(v, edm.StringValue):
                        v.SetFromLiteral(str(dtOffset))
                    else:
                        # give up, treat this value as NULL
                        v.set_from_value(None)
                else:
                    # now we need to grab the actual value, only interested in
                    # data
                    data = []
                    for child in targetElement.GetChildren():
                        if type(child) in StringTypes:
                            data.append(child)
                    v.SetFromLiteral(string.join(data, ''))
                    selected.add(k)
            else:
                # and watch out for unselected properties
                if k in self._properties:
                    self._properties[k].GetValue(v)
                    selected.add(k)
                else:
                    # Property is not selected!
                    v.set_from_value(None)
                    unselected.add(k)
        # Now set this entity's select property...
        if not unselected:
            entity.selected = None
        else:
            entity.selected = selected
        if entity.exists == False:
            # we need to look for any link bindings
            for link in self.Link:
                if not link.rel.startswith(ODATA_RELATED):
                    continue
                navProperty = link.rel[len(ODATA_RELATED):]
                if not entity.IsNavigationProperty(navProperty):
                    continue
                targetSet = entity.entity_set.NavigationTarget(navProperty)
                # we have a navigation property we understand
                if link.Inline is not None:
                    with targetSet.OpenCollection() as collection:
                        if entity.IsEntityCollection(navProperty):
                            for entry in link.Inline.Feed.FindChildrenDepthFirst(Entry, subMatch=False):
                                # create a new entity from the target entity
                                # set
                                targetEntity = collection.new_entity()
                                entry.GetValue(targetEntity, entity_resolver)
                                entity[navProperty].BindEntity(targetEntity)
                        elif link.Inline.Entry is not None:
                            targetEntity = collection.new_entity()
                            link.Inline.Entry.GetValue(
                                targetEntity, entity_resolver)
                            entity[navProperty].BindEntity(targetEntity)
                elif entity_resolver is not None:
                    #   this is the tricky bit, we need to resolve
                    #   the URI to an entity key
                    href = link.ResolveURI(link.href)
                    if not href.is_absolute():
                        #   we'll assume that the base URI is the
                        #   location of this entity once it is
                        #   created.  Witness this thread:
                        #   http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                        href = href.resolve(entity.get_location())
                    targetEntity = entity_resolver(href)
                    if isinstance(targetEntity, Entity) and targetEntity.entity_set is targetSet:
                        entity[navProperty].BindEntity(targetEntity)
                    else:
                        raise InvalidData(
                            "Resource is not a valid target for %s: %s" %
                            (navProperty, str(href)))
                else:
                    raise InvalidData(
                        "No context to resolve entity URI: %s" % str(
                            link.href))
        elif for_update:
            # we need to look for any updated link bindings
            for link in self.Link:
                if not link.rel.startswith(ODATA_RELATED):
                    continue
                navProperty = link.rel[len(ODATA_RELATED):]
                if not entity.IsNavigationProperty(navProperty) or entity[navProperty].isCollection:
                    continue
                targetSet = entity.entity_set.NavigationTarget(navProperty)
                # we have a navigation property we can update
                if entity_resolver is not None:
                    #   this is the tricky bit, we need to resolve
                    #   the URI to an entity key
                    href = link.ResolveURI(link.href)
                    if not href.is_absolute():
                        #   we'll assume that the base URI is the location of this entity
                        #   Witness this thread:
                        #   http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                        href = href.resolve(entity.get_location())
                    targetEntity = entity_resolver(href)
                    if isinstance(targetEntity, Entity) and targetEntity.entity_set is targetSet:
                        entity[navProperty].BindEntity(targetEntity)
                    else:
                        raise InvalidData(
                            "Resource is not a valid target for %s: %s" %
                            (navProperty, str(href)))
                else:
                    raise InvalidData(
                        "No context to resolve entity URI: %s" % str(
                            link.href))
        else:
            # entity exists, look to see if it has been expanded
            for link in self.Link:
                if not link.rel.startswith(ODATA_RELATED):
                    continue
                navProperty = link.rel[len(ODATA_RELATED):]
                if not entity.IsNavigationProperty(navProperty):
                    continue
                targetSet = entity.entity_set.NavigationTarget(navProperty)
                link.LoadExpansion(entity[navProperty])
        return entity

    def SetValue(self, entity, for_update=False):
        """Sets the value of this Entry to represent *entity*, a :py:class:`pyslet.mc_csdl.Entity` instance."""
        # start with a reset
        self.reset()
        mediaLinkResource = entity.type_def.has_stream()
        self.etag = entity.ETag()
        # Now set the new property values, starting with entity-type level feed customisation
        # seems odd that there can only be one of these but, hey...
        cat = self.ChildElement(atom.Category)
        cat.term = entity.type_def.GetFQName()
        cat.scheme = ODATA_SCHEME
        targetPath = entity.type_def.get_target_path()
        if targetPath:
            prefix, ns = entity.type_def.get_fc_ns_prefix()
            targetElement = self.ResolveTargetPath(targetPath, prefix, ns)
            source_path = entity.type_def.get_source_path()
            if source_path:
                v = entity
                for p in source_path:
                    if isinstance(v, (edm.Entity, edm.Complex)):
                        v = v[p]
                    else:
                        v = None
                        break
                if isinstance(targetElement, atom.Date) and v:
                    if isinstance(v, edm.DateTimeOffsetValue):
                        targetElement.SetValue(unicode(v))
                    elif isinstance(v, edm.DateTimeValue):
                        # assume UTC
                        dtOffset = v.value.WithZone(zDirection=0)
                        targetElement.SetValue(unicode(dtOffset))
                    elif isinstance(v, edm.StringValue):
                        try:
                            dtOffset = iso8601.TimePoint.from_str(v.value)
                            if dtOffset.GetZone()[0] is None:
                                dtOffset = dtOffset.WithZone(zDirection=0)
                            targetElement.SetValue(unicode(dtOffset))
                        except iso8601.DateTimeError:
                            # do nothing
                            pass
                elif isinstance(v, edm.SimpleValue) and v:
                    targetElement.AddData(unicode(v))
        # now do the links
        location = str(entity.get_location())
        self.ChildElement(atom.AtomId).SetValue(location)
        if entity.exists and not for_update:
            link = self.ChildElement(self.LinkClass)
            link.href = location
            link.rel = "edit"
            if mediaLinkResource:
                link = self.ChildElement(self.LinkClass)
                link.href = location + "/$value"
                link.rel = "edit-media"
                if self.etag:
                    s = "" if entity.ETagIsStrong() else "W/"
                    link.SetAttribute(
                        (ODATA_METADATA_NAMESPACE,
                         'etag'),
                        s +
                        grammar.quote_string(
                            string.join(
                                map(
                                    ODataURI.FormatLiteral,
                                    self.etag),
                                ',')))
            for navProperty, navValue in entity.NavigationItems():
                link = self.ChildElement(self.LinkClass)
                link.href = location + '/' + navProperty
                link.rel = ODATA_RELATED + navProperty
                link.title = navProperty
                if navValue.isCollection:
                    link.type = ODATA_RELATED_FEED_TYPE
                else:
                    link.type = ODATA_RELATED_ENTRY_TYPE
                if navValue.isExpanded:
                    # This property has been expanded
                    if navValue.isCollection:
                        link.Expand(navValue.OpenCollection())
                    else:
                        link.Expand(navValue.GetEntity())
        elif for_update:
            # This is a special form of representation which only represents the
            # navigation properties with single cardinality
            for k, dv in entity.NavigationItems():
                if not dv.bindings or dv.isCollection:
                    # nothing to do here, we can't update this type of
                    # navigation property
                    continue
                # we need to know the location of the target entity set
                targetSet = dv.Target()
                binding = dv.bindings[-1]
                if isinstance(binding, Entity):
                    if binding.exists:
                        href = str(targetSet.get_location()) + \
                            ODataURI.FormatEntityKey(binding)
                    else:
                        # we can't create new entities on update
                        continue
                else:
                    href = str(
                        targetSet.get_location()) + ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
                link = self.ChildElement(self.LinkClass)
                link.rel = ODATA_RELATED + k
                link.title = k
                link.href = href
        else:
            # entity does not exist...
            for k, dv in entity.NavigationItems():
                if not dv.bindings:
                    continue
                targetSet = dv.Target()
                feed = []
                for binding in dv.bindings:
                    if isinstance(binding, Entity):
                        if binding.exists:
                            href = str(targetSet.get_location()) + \
                                ODataURI.FormatEntityKey(binding)
                        else:
                            feed.append(binding)
                            href = None
                    else:
                        href = str(
                            targetSet.get_location()) + ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
                    if href:
                        link = self.ChildElement(self.LinkClass)
                        link.rel = ODATA_RELATED + k
                        link.title = k
                        link.href = href
                if feed:
                    link = self.ChildElement(self.LinkClass)
                    link.rel = ODATA_RELATED + k
                    link.title = k
                    link.href = location + '/' + k
                    if dv.isCollection:
                        feed = ExpandedEntityCollection(
                            from_entity=entity,
                            name=k,
                            entity_set=targetSet,
                            entityList=feed)
                        link.Expand(feed)
                    elif len(feed) > 1:
                        raise NavigationError(
                            "Multiple bindings found for navigation property %s.%s" %
                            (entity_set.name, k))
                    else:
                        link.Expand(feed[0])
        # Now set the new property values in the properties element
        if mediaLinkResource:
            self.ChildElement(Properties)
            # and populate the content element itself
            content = self.ChildElement(Content)
            content.SetAttribute('src', location + "/$value")
            content.type = str(entity.get_content_type())
        else:
            self.ChildElement(Content).ChildElement(Properties)
        for k, v in entity.data_items():
            # catch property-level feed customisation here
            propertyDef = entity.type_def[k]
            targetPath = propertyDef.get_target_path()
            if targetPath:
                # This value needs to go somewhere special
                prefix, ns = propertyDef.get_fc_ns_prefix()
                targetElement = self.ResolveTargetPath(targetPath, prefix, ns)
                self.SetFCValue(targetElement, v)
                if not propertyDef.keep_in_content():
                    continue
            # and watch out for unselected properties
            if entity.Selected(k):
                self[k] = v
        self.content_changed()

    def SetFCValue(self, targetElement, v):
        if isinstance(targetElement, atom.Date) and v:
            if isinstance(v, edm.DateTimeOffsetValue):
                targetElement.SetValue(unicode(v))
            elif isinstance(v, edm.DateTimeValue):
                # assume UTC
                dtOffset = v.value.WithZone(zDirection=0)
                targetElement.SetValue(unicode(dtOffset))
            elif isinstance(v, edm.StringValue):
                try:
                    dtOffset = iso8601.TimePoint.from_str(v.value)
                    if dtOffset.GetZone()[0] is None:
                        dtOffset = dtOffset.WithZone(zDirection=0)
                    targetElement.SetValue(unicode(dtOffset))
                except iso8601.DateTimeError:
                    # do nothing
                    pass
        elif isinstance(v, edm.SimpleValue) and v:
            targetElement.AddData(unicode(v))


class URI(ODataElement):

    """Represents a single URI in the XML-response to $links requests"""
    XMLNAME = (ODATA_DATASERVICES_NAMESPACE, 'uri')


class Links(ODataElement):

    """Represents a list of links in the XML-response to $links requests"""
    XMLNAME = (ODATA_DATASERVICES_NAMESPACE, 'links')

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.URI = []

    def GetChildren(self):
        return itertools.chain(
            self.URI,
            ODataElement.GetChildren(self))


class Error(ODataElement):
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'error')
    XMLCONTENT = xmlns.ElementContent

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.Code = Code(self)
        self.Message = Message(self)
        self.InnerError = None

    def GetChildren(self):
        yield self.Code
        yield self.Message
        if self.InnerError:
            yield self.InnerError

    def GenerateStdErrorJSON(self):
        yield '{"error":{"code":%s,"message":%s' % (
            json.dumps(self.Code.GetValue()),
            json.dumps(self.Message.GetValue()))
        if self.InnerError:
            yield ',"innererror":%s' % json.dumps(self.InnerError.GetValue())
        yield '}}'


class Code(ODataElement):
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'code')


class Message(ODataElement):
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'message')


class InnerError(ODataElement):
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'innererror')


class Document(app.Document):

    """Class for working with OData documents."""
    classMap = {}

    def __init__(self, **args):
        app.Document.__init__(self, **args)
        self.MakePrefix(ODATA_METADATA_NAMESPACE, 'm')
        self.MakePrefix(ODATA_DATASERVICES_NAMESPACE, 'd')

    @classmethod
    def get_element_class(cls, name):
        """Returns the OData, APP or Atom class used to represent name.

        Overrides :py:meth:`~pyslet.rfc5023.Document.get_element_class` to allow
        custom implementations of the Atom or APP classes to be created and
        to cater for OData-specific elements."""
        result = Document.classMap.get(name, None)
        if result is None:
            if name[0] == ODATA_DATASERVICES_NAMESPACE:
                result = Property
            else:
                result = app.Document.get_element_class(name)
        return result

xmlns.MapClassElements(Document.classMap, globals())
