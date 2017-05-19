#! /usr/bin/env python
"""OData core elements"""

import base64
import decimal
import itertools
import json
import math
import uuid
import warnings

from . import csdl as edm
from .. import iso8601 as iso
from .. import rfc2396 as uri
from .. import rfc4287 as atom
from .. import rfc5023 as app
from ..http import grammar
from ..http import messages
from ..http import params
from ..pep8 import (
    MigratedClass,
    old_function,
    old_method,
    PEP8Compatibility)
from ..py2 import (
    dict_items,
    dict_values,
    is_text,
    SortableMixin,
    to_text,
    uempty,
    UnicodeMixin)
from ..unicode5 import CharClass
from ..xml import namespace as xmlns
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi


# : namespace for metadata, e.g., the property type attribute
ODATA_METADATA_NAMESPACE = \
    "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"

IS_DEFAULT_ENTITY_CONTAINER = (
    ODATA_METADATA_NAMESPACE, "IsDefaultEntityContainer")

MIME_TYPE = (ODATA_METADATA_NAMESPACE, "MimeType")

HttpMethod = (ODATA_METADATA_NAMESPACE, "HttpMethod")

HAS_STREAM = (ODATA_METADATA_NAMESPACE, "HasStream")

DATA_SERVICE_VERSION = (ODATA_METADATA_NAMESPACE, "DataServiceVersion")
FC_KeepInContent = (ODATA_METADATA_NAMESPACE, "FC_KeepInContent")
FC_TargetPath = (ODATA_METADATA_NAMESPACE, "FC_TargetPath")
FC_NsPrefix = (ODATA_METADATA_NAMESPACE, "FC_NsPrefix")
FC_NsUri = (ODATA_METADATA_NAMESPACE, "FC_NsUri")
FC_SourcePath = (ODATA_METADATA_NAMESPACE, "FC_SourcePath")

#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_DATASERVICES_NAMESPACE = \
    "http://schemas.microsoft.com/ado/2007/08/dataservices"
#: category scheme for type definition terms
ODATA_SCHEME = "http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"
#: link type for related entries
ODATA_RELATED = \
    "http://schemas.microsoft.com/ado/2007/08/dataservices/related/"

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


def promote_types(type_a, type_b):
    """Given two values from :py:class:`pyslet.mc_csdl.SimpleType`
    returns the common promoted type.

    If type_a and type_b are the same this is always returns that type
    code.

    Otherwise it follows numeric type promotion rules laid down in the
    specification. If the types are incompatible then an EvaluationError
    is raised."""
    if type_a == type_b:
        return type_a
    elif type_a is None:
        return type_b
    elif type_b is None:
        return type_a
    elif type_a not in NUMERIC_TYPES or type_b not in NUMERIC_TYPES:
        raise EvaluationError(
            "Incompatible types: %s and %s" %
            (edm.SimpleType.to_str(type_a),
             edm.SimpleType.to_str(type_b)))
    elif edm.SimpleType.Double in (type_a, type_b):
        return edm.SimpleType.Double
    elif edm.SimpleType.Single in (type_a, type_b):
        return edm.SimpleType.Single
    elif edm.SimpleType.Decimal in (type_a, type_b):
        return edm.SimpleType.Decimal
    elif edm.SimpleType.Int64 in (type_a, type_b):
        return edm.SimpleType.Int64
    elif edm.SimpleType.Int32 in (type_a, type_b):
        return edm.SimpleType.Int32
    elif edm.SimpleType.Int16 in (type_a, type_b):
        return edm.SimpleType.Int16
    # else must be both Byte - already got this case above


def can_cast_method_argument(type_a, type_b):
    """Given two values from :py:class:`pyslet.mc_csdl.SimpleType`
    returns True if *type_a* can be cast to *type_b*.

    If type_a and type_b are the same this is always True.

    If type_a is NULL then we return True"""
    if type_a == type_b:
        return True
    elif type_a is None:
        return True
    elif type_b == edm.SimpleType.Double:
        return type_a in NUMERIC_TYPES
    elif type_b == edm.SimpleType.Single:
        return type_a in NUMERIC_TYPES
    elif type_b == edm.SimpleType.Decimal:
        return type_a in (
            edm.SimpleType.Decimal,
            edm.SimpleType.Int64,
            edm.SimpleType.Int32,
            edm.SimpleType.Int16)
    elif type_b == edm.SimpleType.Int64:
        return type_a in NUMERIC_TYPES
    elif type_b == edm.SimpleType.Int32:
        return type_a in NUMERIC_TYPES
    elif type_b == edm.SimpleType.Int16:
        return type_a in NUMERIC_TYPES
    elif type_b == edm.SimpleType.Byte:
        return type_a in NUMERIC_TYPES
    else:
        return False


class OperatorCategory(xsi.Enumeration):

    """An enumeration used to represent operator categories (for precedence).
    ::

            OperatorCategory.Unary
            SimpleType.DEFAULT == None

    Note that OperatorCategory.X > OperatorCategory.Y if and only if operator X
    has higher precedence that operator Y.

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

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


class Operator(xsi.Enumeration):

    """An enumeration used to represent operators.

    Note that the expressions not, and and or have aliases "bool_not",
    "bool_and" and "bool_or" to make it easier to use Python attribute
    notation::

            Operator.mul
            Operator.DEFAULT == None
            Operator.bool_not == getattr(Operator,"not")"""

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

    aliases = {
        'boolParen': 'paren',
        'bool_paran': 'paren',
        'boolMethodCall': 'methodCall',
        'bool_method_call': 'methodCall',
        'method_call': 'methodCall',
        'boolNot': 'not',
        'bool_not': 'not',
        'boolAnd': 'and',
        'bool_and': 'and',
        'boolOr': 'or',
        'bool_or': 'or'}

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


Operator.Category = {
    Operator.paren: OperatorCategory.Grouping,
    Operator.member: OperatorCategory.Primary,
    Operator.method_call: OperatorCategory.Primary,
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
     Operator.method_call,
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


class CommonExpression(SortableMixin, UnicodeMixin, MigratedClass):

    """Represents a common expression, used by $filter and $orderby
    system query options."""

    def __init__(self, operator=None):
        self.parent = None
        self.operator = operator
        self.operands = []

    @old_method('AddOperand')
    def add_operand(self, operand):
        self.operands.append(operand)

    @old_method('Evaluate')
    def evaluate(self, context_entity):
        raise NotImplementedError

    def sortkey(self):
        """We implement comparisons based on operator precedence."""
        if self.operator is None:
            return NotImplemented
        return Operator.Category[self.operator]

    def otherkey(self, other):
        if not isinstance(other, CommonExpression) or other.operator is None:
            return NotImplemented
        return Operator.Category[other.operator]

    @staticmethod
    def from_str(src, params=None):
        p = Parser(src)
        return p.require_production_end(
            p.parse_common_expression(params),
            "commonExpression")

    @staticmethod
    @old_method('OrderByFromString')
    def orderby_from_str(src):
        p = Parser(src)
        return p.require_production_end(p.parse_orderby_option(),
                                        "orderbyOption")

    @staticmethod
    @old_method('OrderByToString')
    def orderby_to_str(orderby):
        return ', '.join(
            "%s %s" % (to_text(x[0]), "asc" if x[1] > 0 else "desc")
            for x in orderby)

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
            op = "-"
        else:
            op = "%s " % Operator.to_str(self.operator)
        rvalue = self.operands[0]
        if rvalue.operator is not None and rvalue < self:
            # right expression is weaker than us, use brackets
            result = "%s(%s)" % (op, to_text(rvalue))
        else:
            result = "%s%s" % (op, to_text(rvalue))
        return to_text(result)

    def evaluate(self, context_entity):
        rvalue = self.operands[0].evaluate(context_entity)
        return self.EvalMethod[self.operator](self, rvalue)

    def evaluate_negate(self, rvalue):
        type_code = rvalue.type_code
        if type_code in (edm.SimpleType.Byte, edm.SimpleType.Int16):
            rvalue = rvalue.simple_cast(edm.SimpleType.Int32)
        elif type_code == edm.SimpleType.Single:
            rvalue = rvalue.simple_cast(edm.SimpleType.Double)
        type_code = rvalue.type_code
        if type_code in (
                edm.SimpleType.Int32, edm.SimpleType.Int64,
                edm.SimpleType.Double, edm.SimpleType.Decimal):
            result = edm.EDMValue.from_type(type_code)
            if rvalue:
                result.set_from_value(0 - rvalue.value)
            return result
        elif type_code is None:  # -null
            return edm.EDMValue.from_type(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operand for negate")

    def evaluate_not(self, rvalue):
        if isinstance(rvalue, edm.SimpleValue):
            if rvalue:
                type_code = rvalue.type_code
                if type_code == edm.SimpleType.Boolean:
                    result = edm.EDMValue.from_type(
                        edm.SimpleType.Boolean)
                    result.set_from_value(not rvalue.value)
                    return result
                else:
                    raise EvaluationError("Illegal operand for not")
            else:
                result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
                return result
        else:
            raise EvaluationError("Illegal operand for not")


UnaryExpression.EvalMethod = {
    Operator.negate: UnaryExpression.evaluate_negate,
    Operator.boolNot: UnaryExpression.evaluate_not}


class BinaryExpression(CommonExpression):

    EvalMethod = {
    }
    """A mapping from binary operators to unbound methods that evaluate
    the operator."""

    def __init__(self, operator):
        super(BinaryExpression, self).__init__(operator)

    def __unicode__(self):
        op_prefix = op_suffix = ''
        if self.operator in Operator.IsSpecial:
            if self.operator == Operator.member:
                op = "/"
            elif self.operator in (Operator.cast, Operator.isof):
                op_prefix = "%s(" % Operator.to_str(self.operator)
                op = ","
                op_suffix = ")"
            else:
                raise ValueError(
                    "Can't format %s as a binary operator" & Operator.to_str(
                        self.operator))
        else:
            op = " %s " % Operator.to_str(self.operator)
        lvalue = self.operands[0]
        rvalue = self.operands[1]
        if lvalue.operator is not None and lvalue < self:
            # left expression is weaker than us, use brackets
            lvalue = "(%s)" % to_text(lvalue)
        else:
            lvalue = to_text(lvalue)
        if rvalue.operator is not None and rvalue < self:
            # right expression is weaker than us, use brackets
            rvalue = "(%s)" % to_text(rvalue)
        else:
            rvalue = to_text(rvalue)
        return uempty.join((op_prefix, lvalue, op, rvalue, op_suffix))

    def evaluate(self, context_entity):
        lvalue = self.operands[0].evaluate(context_entity)
        if self.operator == Operator.member:
            # Special handling for the member operator, as the left-hand
            # side of the expression returns the context for evaluating
            # the right-hand side
            if lvalue:
                return self.operands[1].evaluate(lvalue)
            else:
                # an optional navigation property is not bound to
                # an entity.  We return NULL without evaluating
                # the right hand side
                return edm.EDMValue.from_property(None)
        elif self.operator in (Operator.isof, Operator.cast):
            # Special handling due to optional first parameter to
            # signify the context entity
            if len(self.operands) == 1:
                rvalue = lvalue
                lvalue = context_entity
            else:
                rvalue = self.operands[1].evaluate(context_entity)
            return self.EvalMethod[self.operator](self, lvalue, rvalue)
        else:
            rvalue = self.operands[1].evaluate(context_entity)
            return self.EvalMethod[self.operator](self, lvalue, rvalue)

    def promote_operands(self, lvalue, rvalue):
        if isinstance(lvalue, edm.SimpleValue) and \
                isinstance(rvalue, edm.SimpleValue):
            return promote_types(lvalue.type_code, rvalue.type_code)
        else:
            raise EvaluationError(
                "Expected primitive value for %s" %
                Operator.to_str(
                    self.operator))

    def evaluate_cast(self, lvalue, rvalue):
        # rvalue is always a string literal name of the type to look up
        if not lvalue:
            # cast(NULL, <any type>) results in NULL
            try:
                type_code = edm.SimpleType.from_str(rvalue.value)
                result = edm.EDMValue.from_type(type_code)
            except ValueError:
                result = edm.SimpleValue.from_property(None)
            return result
        elif isinstance(lvalue, edm.Entity):
            # in the future we should deal with entity type inheritance
            # right now, the only thing we can cast an entity instance
            # to is itself
            name = lvalue.type_def.get_fqname()
            if name == rvalue.value:
                return lvalue
            else:
                raise EvaluationError(
                    "Can't cast %s to %s" % (name, str(rvalue.value)))
        elif isinstance(lvalue, edm.SimpleValue):
            # look up the name of the primitive type
            try:
                type_code = edm.SimpleType.from_str(rvalue.value)
            except ValueError:
                raise EvaluationError(
                    "Unrecognized type: %s" % str(rvalue.value))
            new_code = promote_types(type_code, lvalue.type_code)
            if type_code != new_code:
                raise EvaluationError(
                    "Can't cast %s to %s" %
                    (edm.SimpleType.to_str(
                        lvalue.type_code),
                        edm.SimpleType.to_str(type_code)))
            result = edm.EDMValue.from_type(type_code)
            result.set_from_value(lvalue.value)
            return result
        else:
            raise EvaluationError("Illegal operands for isof")

    def evaluate_mul(self, lvalue, rvalue):
        type_code = self.promote_operands(lvalue, rvalue)
        if type_code in (
                edm.SimpleType.Int32, edm.SimpleType.Int64,
                edm.SimpleType.Single, edm.SimpleType.Double,
                edm.SimpleType.Decimal):
            lvalue = lvalue.simple_cast(type_code)
            rvalue = rvalue.simple_cast(type_code)
            result = edm.EDMValue.from_type(type_code)
            if lvalue and rvalue:
                result.set_from_value(lvalue.value * rvalue.value)
            return result
        elif type_code is None:  # null mul null
            return edm.EDMValue.from_type(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operands for mul")

    def evaluate_div(self, lvalue, rvalue):
        try:
            type_code = self.promote_operands(lvalue, rvalue)
            if type_code in (
                    edm.SimpleType.Single, edm.SimpleType.Double,
                    edm.SimpleType.Decimal):
                lvalue = lvalue.simple_cast(type_code)
                rvalue = rvalue.simple_cast(type_code)
                result = edm.EDMValue.from_type(type_code)
                if lvalue and rvalue:
                    result.set_from_value(lvalue.value / rvalue.value)
                return result
            elif type_code in (edm.SimpleType.Int32, edm.SimpleType.Int64):
                lvalue = lvalue.simple_cast(type_code)
                rvalue = rvalue.simple_cast(type_code)
                result = edm.EDMValue.from_type(type_code)
                if lvalue and rvalue:
                    # OData doesn't really specify integer division rules so
                    # we use floating point division and truncate towards zero
                    result.set_from_value(
                        int(float(lvalue.value) / float(rvalue.value)))
                return result
            elif type_code is None:  # null div null
                return edm.EDMValue.from_type(edm.SimpleType.Int32)
            else:
                raise EvaluationError("Illegal operands for div")
        except ZeroDivisionError as e:
            raise EvaluationError(str(e))

    def evaluate_mod(self, lvalue, rvalue):
        try:
            type_code = self.promote_operands(lvalue, rvalue)
            if type_code in (
                    edm.SimpleType.Single, edm.SimpleType.Double,
                    edm.SimpleType.Decimal):
                lvalue = lvalue.simple_cast(type_code)
                rvalue = rvalue.simple_cast(type_code)
                result = edm.EDMValue.from_type(type_code)
                if lvalue and rvalue:
                    result.set_from_value(
                        math.fmod(lvalue.value, rvalue.value))
                return result
            elif type_code in (edm.SimpleType.Int32, edm.SimpleType.Int64):
                lvalue = lvalue.simple_cast(type_code)
                rvalue = rvalue.simple_cast(type_code)
                result = edm.EDMValue.from_type(type_code)
                if lvalue and rvalue:
                    # OData doesn't really specify integer division
                    # rules so we use floating point division and
                    # truncate towards zero
                    result.set_from_value(int(math.fmod(float(lvalue.value),
                                                        float(rvalue.value))))
                return result
            elif type_code is None:  # null div null
                return edm.EDMValue.from_type(edm.SimpleType.Int32)
            else:
                raise EvaluationError("Illegal operands for mod")
        except (ZeroDivisionError, ValueError) as e:
            raise EvaluationError(str(e))

    def evaluate_add(self, lvalue, rvalue):
        type_code = self.promote_operands(lvalue, rvalue)
        if type_code in (
                edm.SimpleType.Int32, edm.SimpleType.Int64,
                edm.SimpleType.Single, edm.SimpleType.Double,
                edm.SimpleType.Decimal):
            lvalue = lvalue.simple_cast(type_code)
            rvalue = rvalue.simple_cast(type_code)
            result = edm.EDMValue.from_type(type_code)
            if lvalue and rvalue:
                result.set_from_value(lvalue.value + rvalue.value)
            return result
        elif type_code is None:  # null add null
            return edm.EDMValue.from_type(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operands for add")

    def evaluate_sub(self, lvalue, rvalue):
        type_code = self.promote_operands(lvalue, rvalue)
        if type_code in (
                edm.SimpleType.Int32, edm.SimpleType.Int64,
                edm.SimpleType.Single, edm.SimpleType.Double,
                edm.SimpleType.Decimal):
            lvalue = lvalue.simple_cast(type_code)
            rvalue = rvalue.simple_cast(type_code)
            result = edm.EDMValue.from_type(type_code)
            if lvalue and rvalue:
                result.set_from_value(lvalue.value - rvalue.value)
            return result
        elif type_code is None:  # null sub null
            return edm.EDMValue.from_type(edm.SimpleType.Int32)
        else:
            raise EvaluationError("Illegal operands for sub")

    def evaluate_lt(self, lvalue, rvalue):
        return self.evaluate_relation(lvalue, rvalue, lambda x, y: x < y)

    def evaluate_gt(self, lvalue, rvalue):
        return self.evaluate_relation(lvalue, rvalue, lambda x, y: x > y)

    def evaluate_le(self, lvalue, rvalue):
        return self.evaluate_relation(lvalue, rvalue, lambda x, y: x <= y)

    def evaluate_ge(self, lvalue, rvalue):
        return self.evaluate_relation(lvalue, rvalue, lambda x, y: x >= y)

    def evaluate_relation(self, lvalue, rvalue, relation):
        type_code = self.promote_operands(lvalue, rvalue)
        if type_code in (
                edm.SimpleType.Int32, edm.SimpleType.Int64,
                edm.SimpleType.Single, edm.SimpleType.Double,
                edm.SimpleType.Decimal):
            lvalue = lvalue.simple_cast(type_code)
            rvalue = rvalue.simple_cast(type_code)
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if lvalue and rvalue:
                result.set_from_value(relation(lvalue.value, rvalue.value))
            else:
                # one of the operands is null => False
                result.set_from_value(False)
            return result
        elif type_code in (
                edm.SimpleType.String, edm.SimpleType.DateTime,
                edm.SimpleType.DateTimeOffset, edm.SimpleType.Guid):
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.set_from_value(relation(lvalue.value, rvalue.value))
            return result
        elif type_code is None:  # e.g., null lt null
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.set_from_value(False)
            return result
        else:
            raise EvaluationError(
                "Illegal operands for %s" %
                Operator.to_str(
                    self.operator))

    def evaluate_isof(self, lvalue, rvalue):
        # rvalue is always a string literal name of the type to look up
        if not lvalue:
            # isof(NULL, <any type> ) is False
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.set_from_value(False)
            return result
        elif isinstance(lvalue, edm.Entity):
            # in the future we should test the entity for inheritance
            name = lvalue.type_def.get_fqname()
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.set_from_value(name == rvalue.value)
            return result
        elif isinstance(lvalue, edm.SimpleValue):
            # look up the name of the primitive type
            try:
                type_code = edm.SimpleType.from_str(rvalue.value)
            except ValueError:
                raise EvaluationError(
                    "Unrecognized type: %s" % str(rvalue.value))
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            # we return True if the type of the target, when promoted with type
            # being tested results in the type being tested
            try:
                rvalue = (type_code == promote_types(type_code,
                                                     lvalue.type_code))
            except EvaluationError:
                # incompatible types means False
                rvalue = False
            result.set_from_value(rvalue)
            return result
        else:
            raise EvaluationError("Illegal operands for isof")

    def evaluate_eq(self, lvalue, rvalue):
        if isinstance(lvalue, edm.Entity) and isinstance(rvalue, edm.Entity):
            # we can do comparison of entities, but must be the same entity!
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if lvalue.entity_set is rvalue.entity_set:
                # now test that the keys are the same
                result.value = (lvalue.key() == rvalue.key())
            else:
                result.value = False
            return result
        else:
            type_code = self.promote_operands(lvalue, rvalue)
            if type_code in (
                    edm.SimpleType.Int32, edm.SimpleType.Int64,
                    edm.SimpleType.Single, edm.SimpleType.Double,
                    edm.SimpleType.Decimal):
                lvalue = lvalue.simple_cast(type_code)
                rvalue = rvalue.simple_cast(type_code)
                result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
                result.set_from_value(lvalue.value == rvalue.value)
                return result
            elif type_code in (
                    edm.SimpleType.String, edm.SimpleType.DateTime,
                    edm.SimpleType.DateTimeOffset, edm.SimpleType.Guid,
                    edm.SimpleType.Binary):
                result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
                result.set_from_value(lvalue.value == rvalue.value)
                return result
            elif type_code is None:  # null eq null
                result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
                result.set_from_value(True)
                return result
            else:
                raise EvaluationError("Illegal operands for eq")

    def evaluate_ne(self, lvalue, rvalue):
        result = self.evaluate_eq(lvalue, rvalue)
        result.value = not result.value
        return result

    def evaluate_and(self, lvalue, rvalue):
        """Watch out for the differences between OData 2-value logic and
        the usual SQL 3-value approach."""
        type_code = self.promote_operands(lvalue, rvalue)
        if type_code == edm.SimpleType.Boolean:
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if lvalue and rvalue:
                result.value = lvalue.value and rvalue.value
            else:
                result.value = False
            return result
        elif type_code is None:
            # null or null
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.value = False
            return result
        else:
            raise EvaluationError("Illegal operands for boolean and")

    def evaluate_or(self, lvalue, rvalue):
        """Watch out for the differences between OData 2-value logic and
        the usual SQL 3-value approach."""
        type_code = self.promote_operands(lvalue, rvalue)
        if type_code == edm.SimpleType.Boolean:
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if lvalue and rvalue:
                result.value = lvalue.value or rvalue.value
            else:
                result.value = False
            return result
        elif type_code is None:
            # null or null
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.value = False
            return result
        else:
            raise EvaluationError("Illegal operands for boolean and")

BinaryExpression.EvalMethod = {
    Operator.cast: BinaryExpression.evaluate_cast,
    Operator.mul: BinaryExpression.evaluate_mul,
    Operator.div: BinaryExpression.evaluate_div,
    Operator.mod: BinaryExpression.evaluate_mod,
    Operator.add: BinaryExpression.evaluate_add,
    Operator.sub: BinaryExpression.evaluate_sub,
    Operator.lt: BinaryExpression.evaluate_lt,
    Operator.gt: BinaryExpression.evaluate_gt,
    Operator.le: BinaryExpression.evaluate_le,
    Operator.ge: BinaryExpression.evaluate_ge,
    Operator.isof: BinaryExpression.evaluate_isof,
    Operator.eq: BinaryExpression.evaluate_eq,
    Operator.ne: BinaryExpression.evaluate_ne,
    Operator.boolAnd: BinaryExpression.evaluate_and,
    Operator.boolOr: BinaryExpression.evaluate_or}


class LiteralExpression(CommonExpression):

    """When converted to str return for example, '42L' or 'Paddy O''brian'
    - note that %-encoding is not applied"""

    def __init__(self, value):
        super(LiteralExpression, self).__init__()
        self.value = value

    def __unicode__(self):
        if not self.value:
            return "null"
        else:
            result = to_text(self.value)
            if self.value.type_code == edm.SimpleType.Binary:
                result = "X'%s'" % result
            elif self.value.type_code == edm.SimpleType.DateTime:
                result = "datetime'%s'" % result
            elif self.value.type_code == edm.SimpleType.Decimal:
                result = result + "M"
            elif self.value.type_code == edm.SimpleType.Double:
                result = result + "D"
            elif self.value.type_code == edm.SimpleType.Single:
                result = result + "F"
            elif self.value.type_code == edm.SimpleType.Guid:
                result = "guid'%s'" % result
            elif self.value.type_code == edm.SimpleType.Int64:
                result = result + "L"
            elif self.value.type_code == edm.SimpleType.Time:
                result = "time'%s'" % result
            elif self.value.type_code == edm.SimpleType.DateTimeOffset:
                result = "datetimeoffset'%s'" % result
            elif self.value.type_code == edm.SimpleType.String:
                # double up on single quotes
                result = "'%s'" % "''".join(result.split("'"))
            return result

    def evaluate(self, context_entity):
        """A literal evaluates to itself."""
        return self.value


class PropertyExpression(CommonExpression):

    def __init__(self, name):
        super(PropertyExpression, self).__init__()
        self.name = name

    def __unicode__(self):
        return to_text(self.name)

    def evaluate(self, context_entity):
        if context_entity:
            if isinstance(context_entity, edm.Entity):
                if context_entity.is_entity_collection(self.name):
                    raise EvaluationError(
                        "%s navigation property must have cardinality of "
                        "1 or 0..1" % self.name)
                else:
                    result = context_entity[self.name]
                    if isinstance(result, edm.DeferredValue):
                        result = result.get_entity()
                    if result is None:
                        # The navigation property does not point to anything,
                        # return a generic null
                        result = edm.EDMValue.from_property(None)
                    return result
            elif self.name in context_entity:
                # context_entity must be a complex value
                return context_entity[self.name]
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

    def __init__(self, method_call):
        super(CallExpression, self).__init__(Operator.method_call)
        self.method = method_call

    def __unicode__(self):
        return "%s(%s)" % (Method.to_str(self.method),
                           ','.join(to_text(x) for x in self.operands))

    def evaluate(self, context_entity):
        return self.EvalMethod[
            self.method](self, list(x.evaluate(context_entity)
                                    for x in self.operands))

    def promote_param(self, arg, type_code):
        if isinstance(arg, edm.SimpleValue):
            if can_cast_method_argument(arg.type_code, type_code):
                return arg.simple_cast(type_code)
        raise EvaluationError(
            "Expected %s value in %s()" %
            (edm.SimpleType.to_str(type_code),
             Method.to_str(
                self.method)))

    def check_strict_param(self, arg, type_code):
        if isinstance(arg, edm.SimpleValue):
            if arg.type_code == type_code:
                return arg
        raise EvaluationError(
            "Expected %s value in %s()" %
            (edm.SimpleType.to_str(type_code),
             Method.to_str(
                self.method)))

    def evaluate_endswith(self, args):
        if (len(args) == 2):
            target = self.promote_param(args[0], edm.SimpleType.String)
            prefix = self.promote_param(args[1], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if target and prefix:
                result.set_from_value(target.value.endswith(prefix.value))
            return result
        else:
            raise EvaluationError(
                "endswith() takes 2 arguments, %i given" % len(args))

    def evaluate_indexof(self, args):
        if (len(args) == 2):
            target = self.promote_param(args[0], edm.SimpleType.String)
            search_string = self.promote_param(
                args[1], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target and search_string:
                result.set_from_value(target.value.find(search_string.value))
            return result
        else:
            raise EvaluationError(
                "indexof() takes 2 arguments, %i given" % len(args))

    def evaluate_replace(self, args):
        if (len(args) == 3):
            target = self.promote_param(args[0], edm.SimpleType.String)
            search_string = self.promote_param(
                args[1], edm.SimpleType.String)
            replace_string = self.promote_param(
                args[2], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            if target and search_string and replace_string:
                result.set_from_value(
                    target.value.replace(
                        search_string.value,
                        replace_string.value))
            return result
        else:
            raise EvaluationError(
                "replace() takes 3 arguments, %i given" % len(args))

    def evaluate_startswith(self, args):
        if (len(args) == 2):
            target = self.promote_param(args[0], edm.SimpleType.String)
            prefix = self.promote_param(args[1], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if target and prefix:
                result.set_from_value(target.value.startswith(prefix.value))
            return result
        else:
            raise EvaluationError(
                "startswith() takes 2 arguments, %i given" % len(args))

    def evaluate_tolower(self, args):
        if (len(args) == 1):
            target = self.promote_param(args[0], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            if target:
                result.set_from_value(target.value.lower())
            return result
        else:
            raise EvaluationError(
                "tolower() takes 1 argument, %i given" % len(args))

    def evaluate_toupper(self, args):
        if (len(args) == 1):
            target = self.promote_param(args[0], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            if target:
                result.set_from_value(target.value.upper())
            return result
        else:
            raise EvaluationError(
                "toupper() takes 1 argument, %i given" % len(args))

    def evaluate_trim(self, args):
        if (len(args) == 1):
            target = self.promote_param(args[0], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            if target:
                result.set_from_value(target.value.strip())
            return result
        else:
            raise EvaluationError(
                "trim() takes 1 argument, %i given" % len(args))

    def evaluate_substring(self, args):
        if (len(args) == 2 or len(args) == 3):
            target = self.check_strict_param(args[0], edm.SimpleType.String)
            start = self.check_strict_param(args[1], edm.SimpleType.Int32)
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            if len(args) == 3:
                length = self.check_strict_param(
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

    def evaluate_substringof(self, args):
        if (len(args) == 2):
            search_string = self.promote_param(
                args[0], edm.SimpleType.String)
            target = self.promote_param(args[1], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            if target and search_string:
                result.set_from_value(
                    target.value.find(search_string.value) >= 0)
            return result
        else:
            raise EvaluationError(
                "substringof() takes 2 arguments, %i given" % len(args))

    def evaluate_concat(self, args):
        if (len(args) == 2):
            left_string = self.check_strict_param(
                args[0], edm.SimpleType.String)
            right_string = self.check_strict_param(
                args[1], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            if left_string and right_string:
                result.set_from_value(left_string.value + right_string.value)
            return result
        else:
            raise EvaluationError(
                "concat() takes 2 arguments, %i given" % len(args))

    def evaluate_length(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(args[0], edm.SimpleType.String)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(len(target.value))
            return result
        else:
            raise EvaluationError(
                "length() takes 1 argument, %i given" % len(args))

    def evaluate_year(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(
                    target.value.date.century * 100 + target.value.date.year)
            return result
        else:
            raise EvaluationError(
                "year() takes 1 argument, %i given" % len(args))

    def evaluate_month(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.date.month)
            return result
        else:
            raise EvaluationError(
                "month() takes 1 argument, %i given" % len(args))

    def evaluate_day(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.date.day)
            return result
        else:
            raise EvaluationError(
                "day() takes 1 argument, %i given" % len(args))

    def evaluate_hour(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.time.hour)
            return result
        else:
            raise EvaluationError(
                "hour() takes 1 argument, %i given" % len(args))

    def evaluate_minute(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.time.minute)
            return result
        else:
            raise EvaluationError(
                "minute() takes 1 argument, %i given" % len(args))

    def evaluate_second(self, args):
        if (len(args) == 1):
            target = self.check_strict_param(
                args[0], edm.SimpleType.DateTime)
            result = edm.EDMValue.from_type(edm.SimpleType.Int32)
            if target:
                result.set_from_value(target.value.time.second)
            return result
        else:
            raise EvaluationError(
                "second() takes 1 argument, %i given" % len(args))

    def evaluate_round(self, args):
        """This is a bit inefficient, but we convert to and from Decimal
        if necessary to ensure we stick to the rounding rules (even for
        binary, up for decimals)."""
        if (len(args) == 1):
            try:
                target = self.promote_param(args[0], edm.SimpleType.Decimal)
                result = edm.EDMValue.from_type(edm.SimpleType.Decimal)
                if target:
                    result.set_from_value(
                        target.value.to_integral(decimal.ROUND_HALF_UP))
            except EvaluationError:
                target = self.promote_param(args[0], edm.SimpleType.Double)
                result = edm.EDMValue.from_type(edm.SimpleType.Double)
                if target:
                    v = decimal.Decimal(str(target.value))
                    result.set_from_value(
                        float(v.to_integral(decimal.ROUND_HALF_EVEN)))
            return result
        else:
            raise EvaluationError(
                "round() takes 1 argument, %i given" % len(args))

    def evaluate_floor(self, args):
        if (len(args) == 1):
            try:
                target = self.promote_param(args[0], edm.SimpleType.Decimal)
                result = edm.EDMValue.from_type(edm.SimpleType.Decimal)
                if target:
                    result.set_from_value(
                        target.value.to_integral(decimal.ROUND_FLOOR))
            except EvaluationError:
                target = self.promote_param(args[0], edm.SimpleType.Double)
                result = edm.EDMValue.from_type(edm.SimpleType.Double)
                if target:
                    result.set_from_value(math.floor(target.value))
            return result
        else:
            raise EvaluationError(
                "floor() takes 1 argument, %i given" % len(args))

    def evaluate_ceiling(self, args):
        if (len(args) == 1):
            try:
                target = self.promote_param(args[0], edm.SimpleType.Decimal)
                result = edm.EDMValue.from_type(edm.SimpleType.Decimal)
                if target:
                    result.set_from_value(
                        target.value.to_integral(decimal.ROUND_CEILING))
            except EvaluationError:
                target = self.promote_param(args[0], edm.SimpleType.Double)
                result = edm.EDMValue.from_type(edm.SimpleType.Double)
                if target:
                    result.set_from_value(math.ceil(target.value))
            return result
        else:
            raise EvaluationError(
                "ceiling() takes 1 argument, %i given" % len(args))


CallExpression.EvalMethod = {
    Method.endswith: CallExpression.evaluate_endswith,
    Method.indexof: CallExpression.evaluate_indexof,
    Method.replace: CallExpression.evaluate_replace,
    Method.startswith: CallExpression.evaluate_startswith,
    Method.tolower: CallExpression.evaluate_tolower,
    Method.toupper: CallExpression.evaluate_toupper,
    Method.trim: CallExpression.evaluate_trim,
    Method.substring: CallExpression.evaluate_substring,
    Method.substringof: CallExpression.evaluate_substringof,
    Method.concat: CallExpression.evaluate_concat,
    Method.length: CallExpression.evaluate_length,
    Method.year: CallExpression.evaluate_year,
    Method.month: CallExpression.evaluate_month,
    Method.day: CallExpression.evaluate_day,
    Method.hour: CallExpression.evaluate_hour,
    Method.minute: CallExpression.evaluate_minute,
    Method.second: CallExpression.evaluate_second,
    Method.round: CallExpression.evaluate_round,
    Method.floor: CallExpression.evaluate_floor,
    Method.ceiling: CallExpression.evaluate_ceiling
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
        left_op = None
        right_op = None
        op_stack = []
        while True:
            self.parse_wsp()
            if params is not None and self.parse(':'):
                pname = self.parse_simple_identifier()
                if pname in params:
                    value = params[pname]
                else:
                    raise ValueError("Expected parameter name after ':'")
            else:
                value = self.parse_uri_literal()
            if value is not None:
                right_op = LiteralExpression(value)
            else:
                name = self.parse_simple_identifier()
                if name == "not":
                    self.require_production(self.parse_wsp(), "WSP after not")
                    right_op = UnaryExpression(Operator.boolNot)
                elif name == "isof":
                    self.parse_wsp()
                    right_op = self.require_production(
                        self.parse_castlike(
                            Operator.isof,
                            "isof"),
                        "isofExpression")
                elif name == "cast":
                    self.parse_wsp()
                    right_op = self.require_production(
                        self.parse_castlike(
                            Operator.cast,
                            "cast"),
                        "caseExpression")
                elif name is not None:
                    self.parse_wsp()
                    if self.match("("):
                        method_call = Method.from_str(name)
                        right_op = self.parse_method_call_expression(
                            method_call)
                    else:
                        right_op = PropertyExpression(name)
            if right_op is None:
                if self.parse("("):
                    right_op = self.require_production(
                        self.parse_common_expression(),
                        "commonExpression inside parenExpression")
                    self.require_production(
                        self.parse(")"), "closing bracket in parenExpression")
                elif self.parse("-"):
                    right_op = UnaryExpression(Operator.negate)
                elif left_op:
                    # an operator waiting for an operand is an error
                    raise ValueError(
                        "Expected expression after %s in ...%s" %
                        (Operator.to_str(
                            left_op.operator),
                            self.peek(10)))
                else:
                    # no common expression found at all
                    return None
            # if we have an unbound unary operator, skip the search for
            # a binary operator
            if not isinstance(right_op, UnaryExpression) or right_op.operands:
                operand = right_op
                self.parse_wsp()
                if self.parse("/"):
                    # Member operator is a special case as it isn't a name
                    right_op = BinaryExpression(Operator.member)
                else:
                    savepos = self.pos
                    name = self.parse_simple_identifier()
                    if name is not None:
                        try:
                            op_code = Operator.from_str(name)
                            if op_code in Operator.IsSpecial:
                                raise ValueError
                            right_op = BinaryExpression(op_code)
                        except ValueError:
                            # this is not an operator we recognise
                            name = None
                            self.setpos(savepos)
                            pass
                    # if name is None and (self.match_one(",)") or
                    # self.match_end()): indicates the end of this
                    # common expression
                    if name is None:
                        while left_op is not None:
                            left_op.add_operand(operand)
                            operand = left_op
                            if op_stack:
                                left_op = op_stack.pop()
                            else:
                                left_op = None
                        return operand
            else:
                operand = None
            # we now have:
            # left_op (may be None)
            # operand (None only if right_op is unary)
            # right_op (an operator expression, never None)
            # next job, determine who binds more tightly, left or right?
            while True:
                if left_op is None or left_op < right_op:
                    # bind the operand to the right, in cases of equal
                    # precedence we left associate 1+2-3 = (1+2)-3
                    if operand is not None:
                        right_op.add_operand(operand)
                    if left_op is not None:
                        op_stack.append(left_op)
                    left_op = right_op
                    right_op = None
                    operand = None
                    break
                else:
                    # bind the operand to the left
                    left_op.add_operand(operand)
                    operand = left_op
                    if op_stack:
                        left_op = op_stack.pop()
                    else:
                        left_op = None

    def parse_method_call_expression(self, method_call):
        method = CallExpression(method_call)
        self.require_production(
            self.parse("("), "opening bracket in methodCallExpression")
        while True:
            self.parse_wsp()
            param = self.require_production(
                self.parse_common_expression(), "methodCall argument")
            method.add_operand(param)
            self.parse_wsp()
            if self.parse(","):
                continue
            elif self.parse(")"):
                break
            else:
                raise ValueError("closing bracket in methodCallExpression")
        return method

    def parse_castlike(self, op, name):
        """Parses a cast-like expression, including 'isof'."""
        self.parse_wsp()
        if self.parse("("):
            e = BinaryExpression(op)
            first_param = self.require_production(
                self.parse_common_expression(), "%s argument" % name)
            e.add_operand(first_param)
            self.parse_wsp()
            if self.parse_one(")"):
                # first parameter omitted
                string_param = first_param
            else:
                self.require_production(self.parse(","), "',' in %s" % name)
                self.parse_wsp()
                string_param = self.require_production(
                    self.parse_common_expression(), "%s argument" % name)
                e.add_operand(string_param)
                self.parse_wsp()
                self.require_production(self.parse(")"), "')' after %s" % name)
            # Final check, the string parameter must be a string literal!
            if not isinstance(string_param, LiteralExpression) or \
                    string_param.value.type_code != edm.SimpleType.String:
                raise ValueError("%s requires string literal")
            return e
        else:
            return None

    @old_method('ParseWSP')
    def parse_wsp(self):
        """Parses WSP characters, returning the string of WSP parsed or
        None."""
        result = []
        while True:
            c = self.parse_one(" \t")
            if c:
                result.append(c)
            else:
                break
        if result:
            return ''.join(result)
        else:
            return None

    def parse_expand_option(self):
        """Parses an expand system query option, returning a list of tuples.

        E.g., "A/B,C" returns {'A': {'B'}, 'C': None }"""
        result = {}
        while True:
            parent = result
            nav_path = self.require_production(
                self.parse_simple_identifier(), "entityNavProperty")
            if nav_path not in parent:
                parent[nav_path] = None
            while self.parse("/"):
                if parent[nav_path] is None:
                    parent[nav_path] = {}
                parent = parent[nav_path]
                nav_path = self.require_production(
                    self.parse_simple_identifier(), "entityNavProperty")
                if nav_path not in parent:
                    parent[nav_path] = None
            if not self.parse(","):
                break
        self.require_end("expandQueryOp")
        return result

    def parse_orderby_option(self):
        """Parses an orderby system query option, returning a list of
        2-tuples.

        Each tuple is ( <py:class:`CommonExpression` instance>, 1 | -1 )

        The value 1 represents the default ascending order, -1 indicated
        descending."""
        result = []
        while True:
            self.parse_wsp()
            e = self.require_production(
                self.parse_common_expression(), "commonExpression")
            self.parse_wsp()
            if self.parse_insensitive("asc"):
                dir = 1
            elif self.parse_insensitive("desc"):
                dir = -1
            else:
                dir = 1
            result.append((e, dir))
            self.parse_wsp()
            if not self.parse(","):
                break
        self.require_end("orderbyQueryOp")
        return result

    def parse_select_option(self):
        """Parses a select system query option, returning a list of tuples.

        E.g., "A/*,C" returns [("A","*"),("C")]

        This is almost identical to the expand option except that '*"
        and WSP is allowed.

        selectQueryOp = "$select=" selectClause
        selectClause = [WSP] selectItem [[WSP] "," selectClause] [WSP]
        selectItem = star / selectedProperty / (selectedNavProperty
                                                ["/" selectItem])
        selectedProperty = entityProperty / entityComplexProperty
        selectedNavProperty = entityNavProperty-es / entityNavProperty-et
        star = "*"  """
        result = {}
        while True:
            parent = result
            self.parse_wsp()
            nav_path = self.require_production(
                self.parse_start_or_identifier(), "selectItem")
            if nav_path not in parent:
                parent[nav_path] = None
            while nav_path != "*" and self.parse("/"):
                if parent[nav_path] is None:
                    parent[nav_path] = {}
                parent = parent[nav_path]
                nav_path = self.require_production(
                    self.parse_start_or_identifier(), "selectItem")
                if nav_path not in parent:
                    parent[nav_path] = None
            self.parse_wsp()
            if not self.parse(","):
                break
        self.require_end("selectQueryOp")
        return result

    def parse_start_or_identifier(self):
        self.parse_wsp()
        if self.parse("*"):
            return '*'
        else:
            return self.require_production(
                self.parse_simple_identifier(),
                "selectItem")

    SimpleIdentifierStartClass = None
    SimpleIdentifierClass = None

    def parse_simple_identifier(self):
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

                [\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}
                    \p{Cf}]{0,}
                (\.[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}
                    \p{Cf}]{0,}){0,}

        Although this expression appears complex this is basically a '.'
        separated list of name components, each of which must start with
        a letter and continue with a letter, number or underscore."""
        if self.SimpleIdentifierStartClass is None:
            load_class = CharClass(CharClass.ucd_category("L"))
            load_class.add_class(CharClass.ucd_category("Nl"))
            self.__class__.SimpleIdentifierStartClass = load_class
        if self.SimpleIdentifierClass is None:
            load_class = CharClass(self.SimpleIdentifierStartClass)
            for c in ['Nd', 'Mn', 'Mc', 'Pc', 'Cf']:
                load_class.add_class(CharClass.ucd_category(c))
            self.__class__.SimpleIdentifierClass = load_class
        savepos = self.pos
        result = []
        while True:
            # each segment must start with a start character
            if self.the_char is None or \
                    not self.SimpleIdentifierStartClass.test(self.the_char):
                self.setpos(savepos)
                return None
            result.append(self.the_char)
            self.next_char()
            while self.the_char is not None and \
                    self.SimpleIdentifierClass.test(self.the_char):
                result.append(self.the_char)
                self.next_char()
            if not self.parse('.'):
                break
            result.append('.')
        return ''.join(result)

    def parse_string_uri_literal(self):
        if self.parse("'"):
            # string of utf-8 characters
            result = edm.EDMValue.from_type(edm.SimpleType.String)
            value = []
            while True:
                start_pos = self.pos
                while not self.parse("'"):
                    if self.match_end():
                        raise ValueError(
                            "Unterminated quote in literal string")
                    self.next_char()
                value.append(self.src[start_pos:self.pos - 1])
                if self.parse("'"):
                    # a repeated SQUOTE, go around again
                    continue
                break
            value = "'".join(value)
            if self.raw:
                value = value.decode('utf-8')
            result.value = value
            return result
        else:
            return None

    @old_method('ParseURILiteral')
    def parse_uri_literal(self):
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
        name_case = self.parse_simple_identifier()
        if name_case is not None:
            name = name_case.lower()
        else:
            name = None
        if name == "null":
            return edm.EDMValue.from_type(None)
        elif name is None and self.match("'"):
            return self.parse_string_uri_literal()
        elif name is None and self.match_one('-.0123456789'):
            # one of the number forms (perhaps)
            num = self.parse_numeric_literal()
            if num is None:
                # must be something like "." or "-" on its own, not a literal
                return None
            if self.parse_one("Dd"):
                result = edm.EDMValue.from_type(edm.SimpleType.Double)
                result.set_from_numeric_literal(num)
                return result
            elif self.parse_one("Ff"):
                result = edm.EDMValue.from_type(edm.SimpleType.Single)
                result.set_from_numeric_literal(num)
                return result
            elif self.parse_one("Mm"):
                result = edm.EDMValue.from_type(edm.SimpleType.Decimal)
                result.set_from_numeric_literal(num)
                return result
            elif self.parse_one("Ll"):
                result = edm.EDMValue.from_type(edm.SimpleType.Int64)
                result.set_from_numeric_literal(num)
                return result
            else:
                result = edm.EDMValue.from_type(edm.SimpleType.Int32)
                result.set_from_numeric_literal(num)
                return result
        elif name == "true":
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.value = True
            return result
        elif name == "false":
            result = edm.EDMValue.from_type(edm.SimpleType.Boolean)
            result.value = False
            return result
        elif name == "datetimeoffset" and self.match("'"):
            result = edm.EDMValue.from_type(edm.SimpleType.DateTimeOffset)
            production = "datetimeoffset literal"
            self.require("'", production)
            dto_string = self.parse_until("'")
            self.require("'", production)
            result.set_from_literal(dto_string)
            return result
        elif name == "datetime" and self.match("'"):
            production = "datetime literal"
            self.require("'", production)
            result = edm.EDMValue.from_type(edm.SimpleType.DateTime)
            value = self.require_production(
                self.parse_datetime_literal(), production)
            self.require("'", production)
            result.value = value
            return result
        elif name == "time" and self.match("'"):
            production = "time literal"
            self.require("'", production)
            result = edm.EDMValue.from_type(edm.SimpleType.Time)
            value = self.require_production(
                self.parse_time_literal(), production)
            self.require("'", production)
            result.value = value
            return result
        elif (name_case == "X" or name == "binary") and self.match("'"):
            self.require("'", "binary")
            result = edm.EDMValue.from_type(edm.SimpleType.Binary)
            value = self.parse_binary_literal()
            self.require("'", "binary literal")
            result.value = value
            return result
        elif name == "nand":
            result = edm.EDMValue.from_type(edm.SimpleType.Double)
            result.set_from_numeric_literal(
                edm.Numeric('', "nan", None, '', None))
            return result
        elif name == "nanf":
            result = edm.EDMValue.from_type(edm.SimpleType.Single)
            result.set_from_numeric_literal(
                edm.Numeric('', "nan", None, '', None))
            return result
        elif name == "infd":
            result = edm.EDMValue.from_type(edm.SimpleType.Double)
            result.value = float("INF")
            return result
        elif name == "inff":
            result = edm.EDMValue.from_type(edm.SimpleType.Single)
            result.value = float("INF")
            return result
        elif name == "guid" and self.match("'"):
            result = edm.EDMValue.from_type(edm.SimpleType.Guid)
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
                    self.require_production(self.parse_hex_digits(8, 8),
                                            "guid"))
            self.require("'", "guid")
            result.value = uuid.UUID(hex=''.join(hex))
            return result
        else:
            self.setpos(savepos)
            return None
            # raise ValueError("Expected literal: %s"%repr(self.peek(10)))


@old_function('ParseURILiteral')
def uri_literal_from_str(source):
    """Parses a URI-literal value from a source string.

    source
        A URI-encoded character string

    Returns a :class:`~pyslet.odata2.csdl.SimpleValue` instance."""
    p = Parser(uri.unescape_data(source).decode('utf-8'))
    return p.require_production_end(p.parse_uri_literal(), "uri literal")


@old_function('FormatURILiteral')
def uri_literal_to_str(value, query=True):
    """Formats a simple value as a URI-encoded literal

    value
        A :class:`~pyslet.odata2.csdl.SimpleValue` instance.

    Returns a URI-encoded character string."""
    return uri.escape_data(ODataURI.format_literal(value).encode('utf-8'),
                           uri.is_query_reserved if query else uri.is_reserved)


def parse_dataservice_version(src):
    """Parses DataServiceVersion from a header field value.

    Returns a triple of (integer) major version, (integer) minor version
    and a user agent string.  See section 2.2.5.3 of the
    specification."""
    version_str = None
    ua_str = []
    p = params.ParameterParser(src)
    version_str = p.require_token("data service version")
    v = version_str.split(b'.')
    if len(v) == 2 and grammar.is_digits(v[0]) and grammar.is_digits(v[1]):
        major = int(v[0])
        minor = int(v[1])
    else:
        raise grammar.BadSyntax(
            "Expected data service version, found %s" % version_str)
    if p.parse_separator(";"):
        while p.the_word is not None:
            t = p.parse_token()
            if t:
                ua_str.append(t)
            else:
                break
    # we are generous in what we accept, don't bother checking for the end
    return major, minor, ' '.join(ua_str)


def parse_max_dataservice_version(src):
    """Parses MaxDataServiceVersion from a header field value.

    Returns a triple of (integer) major version, (integer) minor version and a
    user agent string.  See section 2.2.5.7 of the specification."""
    src = src.split(';')
    version_str = None
    ua_str = None
    if len(src) > 0:
        p = params.ParameterParser(src[0])
        version_str = p.require_token("data service version")
        v = version_str.split(b'.')
        if len(v) == 2 and grammar.is_digits(v[0]) and grammar.is_digits(v[1]):
            major = int(v[0])
            minor = int(v[1])
        else:
            raise grammar.BadSyntax(
                "Expected max data service version, found %s" % version_str)
    else:
        raise grammar.BadSyntax("Expected max data service version")
    ua_str = ';'.join(src[1:])
    return major, minor, ua_str


class SystemQueryOption(xsi.Enumeration):

    """SystemQueryOption defines constants for the OData-defined system
    query options

    Note that these options are enumerated without their '$' prefix::

            SystemQueryOption.filter
            SystemQueryOption.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
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


class InlineCount(xsi.Enumeration):

    """inlinecount defines constants for the $inlinecount system query option::

            InlineCount.allpages
            InlineCount.none
            InlineCount.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'allpages': 1,
        'none': 2
    }


class PathOption(xsi.Enumeration):

    """PathOption defines constants for the $-special values that might
    be found in the resource path, for example::

            PathOption.links
            PathOption.DEFAULT == None

    Note that these options are mutually exclusive!

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'metadata': 1,
        'batch': 2,
        'count': 3,
        'value': 4,
        'links': 5
    }


SupportedSystemQueryOptions = {
    # URI1: http://host/service.svc/Customers: Entity Set
    1: set((SystemQueryOption.expand,
            SystemQueryOption.filter,
            SystemQueryOption.format,
            SystemQueryOption.orderby,
            SystemQueryOption.skip,
            SystemQueryOption.top,
            SystemQueryOption.skiptoken,
            SystemQueryOption.inlinecount,
            SystemQueryOption.select)),
    # URI2: http://host/service.svc/Customers('ALFKI'): Entity
    2: set((SystemQueryOption.expand,
            SystemQueryOption.filter,
            SystemQueryOption.format,
            SystemQueryOption.select)),
    # URI3: http://host/service.svc/Customers('ALFKI')/Address: Complex
    #   Property
    3: set((SystemQueryOption.filter,
            SystemQueryOption.format)),
    # URI4: http://host/service.svc/Customers('ALFKI')/Address/Name:
    #       http://host/service.svc/Customers('ALFKI')/Address/Name/$value:
    #   Complex+Simple Property
    4: set((SystemQueryOption.format,)),
    # URI5: http://host/service.svc/Customers('ALFKI')/CompanyName:
    #       http://host/service.svc/Customers('ALFKI')/CompanyName/$value
    #   Simple Property
    5: set((SystemQueryOption.format,)),
    # URI6: http://host/service.svc/Customers('ALFKI')/Orders:
    #   Navigation property
    61: set((SystemQueryOption.expand,
             SystemQueryOption.filter,
             SystemQueryOption.format,
             SystemQueryOption.select)),
    62: set((SystemQueryOption.expand,
             SystemQueryOption.filter,
             SystemQueryOption.format,
             SystemQueryOption.orderby,
             SystemQueryOption.skip,
             SystemQueryOption.top,
             SystemQueryOption.skiptoken,
             SystemQueryOption.inlinecount,
             SystemQueryOption.select)),
    # URI7: http://host/service.svc/Customers('ALFKI')/$links/Orders: links
    7: set((SystemQueryOption.format,
            SystemQueryOption.skip,
            SystemQueryOption.top,
            SystemQueryOption.skiptoken,
            SystemQueryOption.inlinecount)),
    # URI8: http://host/service.svc/$metadata: metadata
    8: set(),
    # URI9: http://host/service.svc/$batch: batch
    9: set(),
    # URI10: http://host/service.svc/EtFunction: function returning entity
    10: set((SystemQueryOption.format,)),
    # URI11: http://host/service.svc/CollCtFunction: function returning
    #   collection of complex
    11: set((SystemQueryOption.format,)),
    # URI12: http://host/service.svc/CtFunction: function returning complex
    12: set((SystemQueryOption.format,)),
    # URI13: http://host/service.svc/CollPrimFunction: function
    #   returning collection of simple values
    13: set((SystemQueryOption.format,)),
    # URI14: http://host/service.svc/PrimFunction: function returning
    #   simple value
    14: set((SystemQueryOption.format,)),
    # URI15: http://host/service.svc/Customers/$count: count
    15: set((SystemQueryOption.expand,
             SystemQueryOption.filter,
             SystemQueryOption.orderby,
             SystemQueryOption.skip,
             SystemQueryOption.top)),
    # URI16: http://host/service.svc/Customers('ALFKI')/$count: count=1
    16: set((SystemQueryOption.expand,
             SystemQueryOption.filter)),
    # URI17: http://host/service.svc/Documents(1)/$value: media resource
    17: set((SystemQueryOption.format,))
}
"""A mapping from URI format number to a set of supported system query
options.

Note that URI6 is split into 61 and 62 based on the notes in the
specification"""


def format_expand(expand):
    """Returns a unicode string representation of the *expand* rules."""
    result = sorted(_format_expand_list(expand))
    return ','.join(result)


def _format_expand_list(expand):
    """Returns a list of unicode strings representing the *expand* rules."""
    result = []
    for k, v in dict_items(expand):
        if not v:
            result.append(k)
        else:
            result = result + list("%s/%s" % (k, x)
                                   for x in _format_expand_list(v))
    return result


def format_select(select):
    """Returns a unicode string representation of the *select* rules."""
    return format_expand(select)     # same implementation as expand


class ODataURI(PEP8Compatibility):

    """Breaks down an OData URI into its component parts.

    If the URI passed in is not a valid ODataURI then a
    :py:class:`ServerError` (or a derived exception class) is raised.

    You pass the URI (or a string) to construct the object.  You may
    also pass an optional *path_prefix* which is a string that represents
    the part of the path that will be ignored.  In other words,
    *path_prefix* is the path component of the service root.

    There's a little bit of confusion as to whether the service root can
    be empty or not.  An empty service root will be automatically
    converted to '/' by the HTTP protocol.  As a result, the service
    root often appears to contain a trailing slash even when it is not
    empty.  The sample OData server from Microsoft issues a temporary
    redirect from /OData/OData.svc to add the trailing slash before
    returning the service document."""

    def __init__(self, ds_uri, path_prefix='', version=2):
        if not isinstance(ds_uri, uri.URI):
            ds_uri = uri.URI.from_octets(ds_uri)
        #: a :py:class:`pyslet.rfc2396.URI` instance representing the
        #: whole URI
        self.uri = ds_uri
        #: the OData version of this request
        self.version = version
        #: a string containing the path prefix without a trailing slash
        self.path_prefix = path_prefix
        #: a string containing the resource path (or None if this is not
        #: a resource path)
        self.resource_path = None
        #: a list of navigation path segment strings
        self.nav_path = []
        #: the path option in effect or None if no path option was given
        self.path_option = None
        #: the name of the navigation property following $links (no None)
        self.links_property = None
        #: a list of raw strings containing custom query options and
        #: service op params
        self.query_options = []
        #: a dictionary mapping :py:class:`SystemQueryOption` constants
        #: to their values
        self.sys_query_options = {}
        self.param_table = {}
        if ds_uri.abs_path is None:
            # relative paths are resolved relative to the path_prefix
            # with an added slash! so
            # ODataURI('Products','/OData/OData.svc') is treated as
            # '/OData/OData.svc/Products'
            ds_uri = ds_uri.resolve(path_prefix + '/')
        if ds_uri.abs_path is None:
            #   both ds_uri and path_prefix are relative, this is an error
            raise ValueError("path_prefix cannot be relative: %s" %
                             path_prefix)
        if path_prefix and not ds_uri.abs_path.startswith(path_prefix):
            # this is not a URI we own
            return
        #
        #   Unpack the query
        if ds_uri.query is not None:
            raw_options = ds_uri.query.split('&')
            for param_def in raw_options:
                if param_def.startswith('$'):
                    param_name = uri.unescape_data(
                        param_def[1:param_def.index('=')]).decode('utf-8')
                    param, param_value = self.parse_sys_query_option(
                        param_name, uri.unescape_data(
                            param_def[
                                param_def.index('=') + 1:]).decode('utf-8'))
                    self.sys_query_options[param] = param_value
                else:
                    if '=' in param_def:
                        param_name = uri.unescape_data(
                            param_def[:param_def.index('=')]).decode('utf-8')
                        self.param_table[param_name] = len(self.query_options)
                    self.query_options.append(param_def)
        #
        #   Unpack the resource path
        self.resource_path = ds_uri.abs_path[len(path_prefix):]
        if self.resource_path == '/':
            self.nav_path = []
        else:
            segments = self.resource_path.split('/')
            self.nav_path = []
            for segment in segments[1:]:
                if self.path_option == PathOption.links:
                    if self.links_property is not None:
                        raise InvalidPathOption(
                            "A navigation property preceded by $links must "
                            "be the last path segment, found %s" % segment)
                    elif segment.startswith("$"):
                        raise InvalidPathOption(
                            "A navigation property is required after $links, "
                            "found %s" % segment)
                    np_segment = self.split_segment(segment)
                    self.nav_path.append(np_segment)
                    self.links_property = np_segment[0]
                elif segment.startswith("$"):
                    try:
                        path_option = PathOption.from_str_lower(segment[1:])
                    except KeyError:
                        raise InvalidPathOption(segment)
                    if self.path_option is not None:
                        raise InvalidPathOption(
                            "%s must not be used with $%s" %
                            (segment,
                             PathOption.to_str(
                                 self.path_option)))
                    if self.nav_path and self.path_option in (
                            PathOption.batch, PathOption.metadata):
                        raise InvalidPathOption(
                            "$%s must be the only path segment" %
                            PathOption.to_str(
                                self.path_option))
                    elif self.path_option == PathOption.links:
                        if not self.nav_path:
                            raise InvalidPathOption(
                                "resource path must not start with $links")
                    self.path_option = path_option
                else:
                    # count, value, batch and metadata must be the last segment
                    if self.path_option in (
                            PathOption.count, PathOption.value,
                            PathOption.batch, PathOption.metadata):
                        raise InvalidPathOption(
                            "$%s must be the last path segment" %
                            PathOption.to_str(
                                self.path_option))
                    self.nav_path.append(self.split_segment(segment))
            if self.path_option == PathOption.links and \
                    self.links_property is None:
                raise InvalidPathOption(
                    "$links must not be the last path segment")
        if self.path_option:
            if self.path_option == PathOption.links:
                self.validate_sys_query_options(7)
            elif self.path_option == PathOption.metadata:
                self.validate_sys_query_options(8)
            elif self.path_option == PathOption.batch:
                self.validate_sys_query_options(9)
            elif self.path_option == PathOption.count:
                if self.nav_path and self.nav_path[-1][1]:
                    self.validate_sys_query_options(16)
                else:
                    self.validate_sys_query_options(15)

    def parse_sys_query_option(self, param_name, param_value):
        """Returns a tuple of :py:class:`SystemQueryOption` constant and
        an appropriate representation of the value:

        *   filter: an instance of :py:class:`CommonExpression`

        *   expand: a list of expand options, see
            py:meth:`pyslet.mc_csdl.Entity.expand`

        *   format: a list of :py:meth:`pyslet.http.params.MediaType`
            instances (of length 1)

        *   other options return a the param_value unchanged at the moment"""
        try:
            param = SystemQueryOption.from_str(param_name)
            # Now parse the parameter value
            param_parser = Parser(param_value)
            if param == SystemQueryOption.filter:
                value = param_parser.require_production_end(
                    param_parser.parse_common_expression(),
                    "boolCommonExpression")
            elif param == SystemQueryOption.expand:
                value = param_parser.require_production_end(
                    param_parser.parse_expand_option(), "expand query option")
            elif param == SystemQueryOption.format:
                # ("json" / "atom" / "xml" / <a data service specific
                # value indicating a format specific to the specific
                # data service> / <An IANA-defined [IANA-MMT] content
                # type>) first up, let's see if this is a valid MediaType
                try:
                    value = messages.AcceptList.from_str(param_value)
                except grammar.BadSyntax:
                    plower = param_value.lower()
                    if plower == "atom":
                        value = messages.AcceptList.from_str(
                            'application/atom+xml')
                    elif plower == "json":
                        value = messages.AcceptList.from_str(
                            'application/json')
                    elif plower == "xml":
                        value = messages.AcceptList.from_str('application/xml')
                    else:
                        raise InvalidSystemQueryOption(
                            "Unsupported $format : %s" % param_value)
            elif param == SystemQueryOption.orderby:
                value = param_parser.require_production_end(
                    param_parser.parse_orderby_option(),
                    "orderby query option")
            elif param == SystemQueryOption.skip:
                value = param_parser.require_production_end(
                    param_parser.parse_integer(), "skip query option")
            elif param == SystemQueryOption.top:
                value = param_parser.require_production_end(
                    param_parser.parse_integer(), "top query option")
            elif param == SystemQueryOption.inlinecount:
                value = InlineCount.from_str_lower(param_value)
            elif param == SystemQueryOption.select:
                value = param_parser.require_production_end(
                    param_parser.parse_select_option(),
                    "selection query option")
            else:
                value = param_value
        except ValueError as e:
            raise InvalidSystemQueryOption("$%s : %s" % (param_name, str(e)))
        return param, value

    def validate_sys_query_options(self, uri_num):
        rules = SupportedSystemQueryOptions[uri_num]
        for p in self.sys_query_options:
            if p not in rules:
                raise InvalidSystemQueryOption(
                    '$%s cannot be used with this form of URI' %
                    SystemQueryOption.to_str(p))

    @classmethod
    def split_segment(cls, segment):
        """Splits a string segment into a unicode name and a
        key_predicate dictionary."""
        segment = uri.unescape_data(segment).decode('utf-8')
        if segment.startswith('$'):
            # some type of control word
            return segment, None
        elif '(' in segment and segment[-1] == ')':
            name = segment[:segment.index('(')]
            keys = segment[segment.index('(') + 1:-1]
            if keys == '':
                keys = []
            else:
                qmode = False
                vstring = []
                keylist = []
                kname = ''
                for c in keys:
                    if c == "'":
                        qmode = not qmode
                    if c == ',' and not qmode:
                        keylist.append((kname, ''.join(vstring)))
                        kname = ''
                        vstring = []
                    elif c == '=' and not qmode:
                        kname = ''.join(vstring)
                        vstring = []
                    else:
                        vstring.append(c)
                if vstring or kname:
                    keylist.append((kname, ''.join(vstring)))
                keys = keylist
            if len(keys) == 0:
                return name, {}
            elif len(keys) == 1:
                return name, {keys[0][0]: uri_literal_from_str(keys[0][1])}
            else:
                key_predicate = {}
                for k in keys:
                    if not k[0]:
                        raise ValueError(
                            "unrecognized key predicate: %s" % repr(keys))
                    kname, value = k
                    kvalue = uri_literal_from_str(value)
                    key_predicate[kname] = kvalue
                return name, key_predicate
        else:
            return segment, None

    def get_param_value(self, param_name):
        if param_name in self.param_table:
            param_def = self.query_options[self.param_table[param_name]]
            # must be a primitive type
            return uri_literal_from_str(param_def[param_def.index('=') + 1:])
        else:
            # missing parameter is equivalent to NULL
            return edm.SimpleValue.from_type(None)

    @classmethod
    @old_method('FormatKeyDict')
    def format_key_dict(cls, d):
        """Returns a URI formatted and URI escaped, entity key.

        For example, (42L), or ('Salt%20%26%20Pepper')."""
        if len(d) == 1:
            key_str = "(%s)" % cls.format_literal(list(dict_values(d))[0])
        else:
            key_str = []
            for k, v in dict_items(d):
                key_str.append("%s=%s" % (k, cls.format_literal(v)))
            key_str = "(%s)" % ",".join(key_str)
        return uri.escape_data(key_str.encode('utf-8'))

    @classmethod
    def key_dict_to_query(cls, d):
        """Returns a query corresponding to a key dictionary

        The result is a unicode string, it is *not* URI escaped.  For
        example, it might return "ID eq 42L" or "KeyStr eq
        'Salt%20%26%20Pepper'", in cases with composite keys the
        expressions are joined with the and operator."""
        key_str = []
        for k, v in dict_items(d):
            key_str.append("%s eq %s" % (k, cls.format_literal(v)))
        return " and ".join(key_str)

    @classmethod
    @old_method('FormatEntityKey')
    def format_entity_key(cls, entity):
        return cls.format_key_dict(entity.key_dict())

    @staticmethod
    @old_method('FormatLiteral')
    def format_literal(value):
        """Returns a URI-literal-formatted value as a character string.
        For example, "42L" or "'Paddy O''brian'"
        """
        return to_text(LiteralExpression(value))

    @staticmethod
    def format_sys_query_options(sys_query_options):
        return '&'.join(
            "$%s=%s" % (str(SystemQueryOption.to_str(x[0])),
                        uri.escape_data(x[1].encode('utf-8')))
            for x in dict_items(sys_query_options))


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
        return uri.URI.from_octets(str(self.entity_set.get_location()) +
                                   ODataURI.format_entity_key(self))

    def get_content_type(self):
        with self.entity_set.open() as collection:
            return collection.read_stream(self.key()).type

    def GetStreamType(self):    # noqa
        warnings.warn("Entity.GetStreamType is deprecated, "
                      "use collection.read_stream(key).type",
                      DeprecationWarning, stacklevel=2)
        with self.entity_set.open() as collection:
            return collection.read_stream(self.key()).type

    def GetStreamSize(self):    # noqa
        warnings.warn("Entity.GetStreamSize is deprecated, "
                      "use collection.read_stream(key).size",
                      DeprecationWarning, stacklevel=2)
        with self.entity_set.open() as collection:
            return collection.read_stream(self.key()).size

    def GetStreamGenerator(self):   # noqa
        warnings.warn("Entity.GetStreamGenerator is deprecated, "
                      "use collection.read_stream_close(key)",
                      DeprecationWarning, stacklevel=2)
        collection = self.entity_set.open()
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
                    simple_value_from_json(v, obj[k])
                else:
                    # assume a complex value then
                    complex_value_from_json(v, obj[k])
            else:
                v.set_from_value(None)
        if self.exists is False:
            # we need to look for any link bindings
            for nav_property in self.navigation_keys():
                if nav_property not in obj:
                    continue
                links = obj[nav_property]
                if not self.is_entity_collection(nav_property):
                    # wrap singletons for convenience
                    links = (links,)
                target_set = self.entity_set.get_target(nav_property)
                with target_set.open() as collection:
                    for link in links:
                        if len(link) == 1 and '__metadata' in link:
                            # bind to an existing entity
                            href = uri.URI.from_octets(
                                link['__metadata']['uri'])
                            if entity_resolver is not None:
                                if not href.is_absolute():
                                    # we'll assume that the base URI is
                                    # the location of this entity once
                                    # it is created.  Witness this
                                    # thread:
                                    # http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                                    href = href.resolve(self.get_location())
                                target_entity = entity_resolver(href)
                                if isinstance(target_entity, Entity) and \
                                        target_entity.entity_set is target_set:
                                    self[nav_property].bind_entity(
                                        target_entity)
                                else:
                                    raise InvalidData(
                                        "Resource is not a valid target for "
                                        "%s: %s" % (nav_property, str(href)))
                            else:
                                raise InvalidData(
                                    "No context to resolve entity URI: %s" %
                                    str(link))
                        else:
                            # full inline representation is expected for deep
                            # insert
                            target_entity = collection.new_entity()
                            target_entity.set_from_json_object(
                                link, entity_resolver)
                            self[nav_property].bind_entity(target_entity)
        elif for_update:
            # we need to look for any updated link bindings
            for nav_property in self.navigation_keys():
                if nav_property not in obj or \
                        self.is_entity_collection(nav_property):
                    # missing or can't be updated these this way
                    continue
                link = obj[nav_property]
                if '__metadata' in link:
                    target_set = self.entity_set.get_target(nav_property)
                    # bind to an existing entity
                    href = uri.URI.from_octets(link['__metadata']['uri'])
                    if entity_resolver is not None:
                        if not href.is_absolute():
                            #   we'll assume that the base URI is the
                            #   location of this entity.  Witness this thread:
                            #   http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                            href = href.resolve(self.get_location())
                        target_entity = entity_resolver(href)
                        if isinstance(target_entity, Entity) and \
                                target_entity.entity_set is target_set:
                            self[nav_property].bind_entity(target_entity)
                        else:
                            raise InvalidData(
                                "Resource is not a valid target for %s: %s" %
                                (nav_property, str(href)))
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
        media_link_resource = self.type_def.has_stream()
        yield '{"__metadata":{'
        yield '"uri":%s' % json.dumps(location)
        yield ',"type":%s' % json.dumps(
            self.entity_set.entityType.get_fqname())
        etag = self.etag()
        if etag:
            yield ',"etag":%s' % json.dumps(
                Entity.format_etag(etag, self.etag_is_strong()))
        if media_link_resource:
            yield ',"media_src":%s' % json.dumps(location + "/$value")
            yield ',"content_type":%s' % json.dumps(
                str(self.get_content_type()))
            yield ',"edit_media":%s' % json.dumps(location + "/$value")
            if etag:
                yield ',"media_etag":%s' % \
                    json.dumps(Entity.format_etag(etag, self.etag_is_strong()))
        yield '}'
        for k, v in self.data_items():
            # watch out for unselected properties
            if self.is_selected(k):
                yield ','
                if isinstance(v, edm.SimpleValue):
                    yield simple_property_to_json_str(v)
                else:
                    yield complex_property_to_json_str(v)
        if self.exists and not for_update:
            for nav_property, navValue in self.navigation_items():
                if self.is_selected(nav_property):
                    yield ', %s' % json.dumps(nav_property)
                    if navValue.isExpanded:
                        yield ':'
                        if navValue.isCollection:
                            with navValue.open() as collection:
                                for y in collection.\
                                        generate_entity_set_in_json(version):
                                    yield y
                        else:
                            entity = navValue.get_entity()
                            if entity:
                                for y in entity.generate_entity_type_in_json(
                                        False, version):
                                    yield y
                            else:
                                yield json.dumps(None)
                    else:
                        yield ':{"__deferred":{"uri":%s}}' % \
                            json.dumps(location + '/' + nav_property)
        elif for_update:
            for k, dv in self.navigation_items():
                if not dv.bindings or dv.isCollection:
                    # nothing to do here, we can't update this type of
                    # navigation property
                    continue
                # we need to know the location of the target entity set
                target_set = dv.target()
                binding = dv.bindings[-1]
                if isinstance(binding, Entity):
                    if binding.exists:
                        href = str(target_set.get_location()) + \
                            ODataURI.format_entity_key(binding)
                    else:
                        # we can't create new entities on update
                        continue
                else:
                    href = str(target_set.get_location()) + \
                        ODataURI.format_key_dict(
                            target_set.get_key_dict(binding))
                yield ', %s:{"__metadata":{"uri":%s}}' % (
                    json.dumps(k), json.dumps(href))
        else:
            for k, dv in self.navigation_items():
                if not dv.bindings:
                    continue
                target_set = dv.target()
                yield ', %s :[' % json.dumps(k)
                sep = False
                for binding in dv.bindings:
                    if sep:
                        yield ', '
                    else:
                        sep = True
                    if isinstance(binding, Entity):
                        if binding.exists:
                            href = str(target_set.get_location()) + \
                                ODataURI.format_entity_key(binding)
                        else:
                            # we need to yield the entire entity instead
                            for s in binding.generate_entity_type_in_json():
                                yield s
                            href = None
                    else:
                        href = str(target_set.get_location()) + \
                            ODataURI.format_key_dict(
                                target_set.get_key_dict(binding))
                    if href:
                        yield '{ "__metadata":{"uri":%s}}' % json.dumps(href)
                yield ']'
        yield '}'

    def link_json(self):
        """Returns a JSON-serialised link to this entity"""
        return '{"uri":%s}' % json.dumps(str(self.get_location()))

    @staticmethod
    def format_etag(etag, strong):
        s = "" if strong else "W/"
        return s + grammar.quote_string(
            b','.join(ODataURI.format_literal(x).encode('ascii')
                      for x in etag)).decode('ascii')


def complex_property_to_json_v2(complex_value):
    """Return a version 2 JSON complex entity."""
    return '{"results":%s}' % complex_property_to_json_v1(complex_value)


# def ReadEntityCTInJSON2(complex_value, obj):
#     if "results" in obj and isinstance(obj["results"], DictType):
#         obj = obj["results"]
#         complex_property_from_json(complex_value, obj)


def complex_property_to_json_v1(complex_value):
    """Return a version 1 JSON complex entity - specification seems to
    be incorrect here."""
    return '{%s}' % complex_property_to_json_str(complex_value)


def complex_property_from_json(complex_value, obj):
    if complex_value.p_def.name in obj:
        complex_value_from_json(complex_value, obj[complex_value.p_def.name])


def complex_property_to_json_str(complex_value):
    return "%s:%s" % (json.dumps(
        complex_value.p_def.name),
        complex_value_to_json_str(complex_value))


def complex_value_to_json_str(complex_value):
    result = []
    for k, v in complex_value.iteritems():
        if isinstance(v, edm.SimpleValue):
            value = simple_property_to_json_str(v)
        else:
            value = complex_property_to_json_str(v)
        result.append(value)
    return "{%s}" % ','.join(result)


def complex_value_from_json(complex_value, obj):
    for k, v in complex_value.iteritems():
        if k in obj:
            if isinstance(v, edm.SimpleValue):
                simple_value_from_json(v, obj[k])
            else:
                complex_value_from_json(v, obj[k])
        else:
            v.set_from_value(None)


TICKS_PER_DAY = 86400000
BASE_DAY = iso.Date.from_str('1970-01-01').get_absolute_day()


def simple_property_to_json_v2(simple_value):
    """Return a version 2 JSON simple value."""
    return '{"results":{%s}}' % simple_property_to_json_str(simple_value)


def simple_property_to_json_v1(simple_value):
    """Returns a version 1 JSON simple value.

    Not defined by the specification but useful for generating
    request/response bodies."""
    return '{%s}' % simple_property_to_json_str(simple_value)


def simple_property_from_json(simple_value, obj):
    if simple_value.p_def.name in obj:
        simple_value_from_json(simple_value, obj[simple_value.p_def.name])


def simple_property_to_json_str(simple_value):
    return "%s:%s" % (json.dumps(
        simple_value.p_def.name),
        simple_value_to_json_str(simple_value))


def simple_value_to_json_str(v):
    """Formats a simple value for JSON.

    The value is converted into a serialised value (a text string) ready
    for encoding to bytes and output in a JSON stream.  It is not
    intended to be further encoded by the json module, this differs from
    the :func:`simple_value_from_json` function which is called after
    the json module has parsed it from the original stream."""
    if not v:
        return 'null'
    elif isinstance(v, edm.BinaryValue):
        # unusual representation as we use base64 encoding
        return json.dumps(base64.b64encode(v.value).decode('ascii'))
    elif isinstance(v, (edm.BooleanValue, edm.ByteValue, edm.Int16Value,
                        edm.Int32Value, edm.SByteValue)):
        # naked representation
        return to_text(v)
    elif isinstance(v, edm.DateTimeValue):
        # a strange format based on ticks, by definition, DateTime has no
        # offset
        ticks = (v.value.date.get_absolute_day() - BASE_DAY) * \
            TICKS_PER_DAY + int(v.value.time.get_total_seconds() * 1000)
        return '"\\/Date(%i)\\/"' % ticks
    elif isinstance(v, (edm.DecimalValue, edm.DoubleValue, edm.GuidValue,
                        edm.Int64Value, edm.SingleValue, edm.StringValue,
                        edm.TimeValue)):
        # just use the literal form as a json string
        return json.dumps(to_text(v))
    elif isinstance(v, (edm.DateTimeOffsetValue)):
        # a strange format based on ticks, by definition, DateTime has no
        # offset
        ticks = (v.value.date.get_absolute_day() - BASE_DAY) * \
            TICKS_PER_DAY + int(v.value.time.get_total_seconds() * 1000)
        dir, offset = v.value.get_zone()
        if dir > 0:
            s = "+"
        else:
            s = "-"
        return '"\\/Date(%i%s%04i)\\/"' % (ticks, s, offset)
    else:
        raise ValueError("SimpleValue: %s" % repr(v))


def parse_asp_dot_net_date(src):
    """Parses a date string in ASP.Net AJAX format.

    We assume that the string has already be deserialised by json.loads
    so it does not have enclosing quotes or redundant backslash
    characters.

    Returns an :class:`~pyslet.iso8601.TimePoint` instance with a
    timezone.  If the src value has no offset the resulting TimePoint is
    in UTC."""
    if not (src.startswith("/Date(") and src.endswith(")/")):
        raise ValueError
    ticks = src[6:-2]
    if '+' in ticks:
        # split by +
        ticks = ticks.split('+')
        zdir = 1
    elif '-' in ticks:
        # split by -
        ticks = ticks.split('-')
        zdir = -1
    else:
        zdir = 0
    if zdir:
        if len(ticks) != 2:
            raise ValueError
        zoffset = int(ticks[1])
    else:
        zoffset = 0
    t, overflow = iso.Time().offset(
        seconds=int(ticks[0]) / 1000.0)
    t = t.with_zone(zdir, zoffset // 60, zoffset % 60)
    d = iso.Date(absolute_day=BASE_DAY + overflow)
    return iso.TimePoint(date=d, time=t)


def simple_value_from_json(v, json_value):
    """Given a simple property value parsed from a json representation,
    *json_value* and a :py:class:`SimpleValue` instance, *v*, update *v*
    to reflect the parsed value."""
    if json_value is None:
        v.set_from_value(None)
    elif isinstance(v, edm.BinaryValue):
        v.set_from_value(base64.b64decode(json_value))
    elif isinstance(v, (edm.BooleanValue, edm.ByteValue, edm.Int16Value,
                        edm.Int32Value, edm.SByteValue)):
        v.set_from_value(json_value)
    elif isinstance(v, edm.DateTimeValue):
        if json_value.startswith("/Date("):
            try:
                v.set_from_value(
                    parse_asp_dot_net_date(json_value).shift_zone(0))
            except ValueError:
                raise ValueError(
                    "Bad value for DateTime: %s" % json_value)
        else:
            try:
                d = iso.TimePoint.from_str(json_value)
                zdir, zoffset = d.get_zone()
                if zdir is not None:
                    # shift to UTC and strip zone
                    d = d.shift_zone(0).with_zone(None)
                v.set_from_value(d)
            except ValueError:
                raise ValueError(
                    "Unrecognized value for DateTime: %s" % json_value)
    elif isinstance(v, (edm.DecimalValue, edm.DoubleValue, edm.GuidValue,
                        edm.Int64Value, edm.SingleValue, edm.StringValue,
                        edm.TimeValue)):
        # just use the literal form as a json string
        v.set_from_literal(json_value)
    elif isinstance(v, (edm.DateTimeOffsetValue)):
        if json_value.startswith("/Date("):
            try:
                v.set_from_value(parse_asp_dot_net_date(json_value))
            except ValueError:
                raise ValueError(
                    "Bad value for DateTimeOffset: %s" % json_value)
        else:
            try:
                d = iso.TimePoint.from_str(json_value)
                zdir, zoffset = d.get_zone()
                if zdir is None:
                    # assume UTC
                    d = d.with_zone(0)
                v.set_from_value(d)
            except ValueError:
                raise ValueError(
                    "Unrecognized value for DateTimeOffset: %s" % json_value)
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
            base_url = self.get_location()
            sys_query_options = {}
            if self.filter is not None:
                sys_query_options[
                    SystemQueryOption.filter] = to_text(self.filter)
            if self.expand is not None:
                sys_query_options[
                    SystemQueryOption.expand] = format_expand(self.expand)
            if self.select is not None:
                sys_query_options[
                    SystemQueryOption.select] = format_select(self.select)
            if self.orderby is not None:
                sys_query_options[
                    SystemQueryOption.orderby] = \
                    CommonExpression.orderby_to_str(self.orderby)
            sys_query_options[SystemQueryOption.skiptoken] = to_text(token)
            return uri.URI.from_octets(
                str(base_url) +
                "?" +
                ODataURI.format_sys_query_options(sys_query_options))
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
            result = self.filter.evaluate(entity)
            if isinstance(result, edm.BooleanValue):
                return result.value         #: NULL treated as False
            else:
                raise ValueError("Boolean required for filter expression")

    def calculate_order_key(self, entity, order_object):
        """Evaluates order_object as an instance of
        py:class:`CommonExpression`."""
        return order_object.evaluate(entity).value

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
            next_link = self.get_next_page_location()
            if next_link is not None:
                yield '],"__next":{"uri":%s}}' % json.dumps(str(next_link))
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
                yield '],"__next":{"uri":%s}}' % json.dumps(
                    str(self.get_location()) + "?$skiptoken=%s" %
                    uri.escape_data(skiptoken, uri.is_query_reserved))
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
            entity_list=self.values())

    def get_location(self):
        """Returns the location of this collection as a
        :py:class:`rfc2396.URI` instance.

        We override the location based on the source entity set + the
        fromKey."""
        return uri.URI.from_octets(''.join([
            str(self.from_entity.get_location()),
            '/', uri.escape_data(self.name)]))

    def get_title(self):
        return self.name


class ExpandedEntityCollection(EntityCollection, edm.ExpandedEntityCollection):

    """Expanded collections with OData-specific behaviour.

    This class uses diamond inheritance in a similar way to
    :py:class:`NavigationCollection`"""
    pass


class FunctionEntityCollection(EntityCollection, edm.FunctionEntityCollection):

    """We override FunctionEntityCollection in order to include the
    OData-specific behaviour.

    This class uses diamond inheritance in a similar way to
    :py:class:`NavigationCollection`"""
    pass


class FunctionCollection(edm.FunctionCollection):

    """We override FunctionCollection in order to inclue the
    OData-specific behaviour."""

    def generate_collection_in_json(self, version=2):
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
                yield simple_value_to_json_str(value)
            else:
                yield complex_value_to_json_str(value)
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

    def get_simple_type(self):
        try:
            type = self.get_attribute((ODATA_METADATA_NAMESPACE, 'type'))
        except KeyError:
            type = None
        if type:
            try:
                type = edm.SimpleType.from_str_lower(type.lower())
            except ValueError:
                # assume unknown, probably complex
                type = None
            return type
        else:
            return None

    def get_value(self, value=None):
        """Gets an appropriately typed value for the property.

        Overloads the basic
        :py:meth:`~pyslet.xml.structures.Element.get_value`
        implementation to transform the value into an
        :py:class:`pyslet.mc_csdl.EDMValue` instance.

        An optional :py:class:`pyslet.mc_csdl.EDMValue` can be passed,
        if present the instance's value is updated with the value of
        this Property element."""
        try:
            null = self.get_attribute((ODATA_METADATA_NAMESPACE, 'null'))
            null = (null and null.lower() == "true")
        except KeyError:
            null = False
        if value is None:
            entry = self.find_parent(Entry)
            if entry and entry.entityType:
                property_def = entry.entityType.get(self.xmlname, None)
            else:
                property_def = None
            if property_def:
                value = property_def()
            else:
                # picks up top-level properties only!
                plist = list(self.find_children_breadth_first(Property, False))
                if plist:
                    # we have a complex type with no definition
                    value = edm.Complex()
                else:
                    type = self.get_simple_type()
                    if type is None:
                        # unknown simple types treated as string
                        type = edm.SimpleType.String
                    p = edm.Property(None)
                    p.name = self.xmlname
                    p.simpleTypeCode = type
                    value = edm.EDMValue.from_property(p)
        if isinstance(value, edm.SimpleValue):
            if null:
                value.value = None
            else:
                value.set_from_literal(ODataElement.get_value(self))
        else:
            # you can't have a null complex value BTW
            for child in self.get_children():
                if isinstance(child, Property):
                    if child.xmlname in value:
                        child.get_value(value[child.xmlname])
                    else:
                        value.add_property(child.xmlname, child.get_value())
        return value

    def set_value(self, value):
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
                self.set_attribute(
                    (ODATA_METADATA_NAMESPACE,
                     'type'),
                    edm.SimpleType.to_str(
                        value.type_code))
            if value:
                ODataElement.set_value(self, to_text(value))
            else:
                self.set_attribute((ODATA_METADATA_NAMESPACE, 'null'), "true")
        elif isinstance(value, edm.Complex):
            if value.type_def:
                self.set_attribute(
                    (ODATA_METADATA_NAMESPACE, 'type'), value.type_def.name)
            else:
                raise ValueError(
                    "Complex-valued properties must have a defined type")
            # loop through our children and set them from this value
            for key, v in value.iteritems():
                child = self.add_child(
                    self.__class__, (ODATA_DATASERVICES_NAMESPACE, key))
                child.set_value(v)
        elif value is None:
            # this is a special case, meaning Null
            self.set_attribute((ODATA_METADATA_NAMESPACE, 'null'), "true")
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

    def get_children(self):
        return itertools.chain(
            self.Property,
            ODataElement.get_children(self))


class Collection(ODataElement):

    """Represents the result of a service operation that returns a
    collection of values."""
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'collection')

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.Property = []

    def get_children(self):
        return itertools.chain(
            self.Property,
            ODataElement.get_children(self))


class Content(atom.Content):

    """Overrides the default :py:class:`pyslet.rfc4287.Content` class to
    add OData handling."""

    def __init__(self, parent):
        atom.Content.__init__(self, parent)
        self.type = 'application/xml'
        #: the optional properties element containing the entry's
        #: property values
        self.Properties = None

    def get_children(self):
        for child in atom.Content.get_children(self):
            yield child
        if self.Properties:
            yield self.Properties


class Feed(atom.Feed):

    """Overrides the default :py:class:`pyslet.rfc4287.Feed` class to
    add OData handling."""

    def __init__(self, parent, collection=None):
        super(Feed, self).__init__(parent)
        #: the collection this feed represents
        self.collection = collection
        if self.collection is not None:
            location = str(self.collection.get_location())
            self.AtomId.set_value(location)
            self.Title.set_value(self.collection.get_title())
            link = self.add_child(self.LinkClass)
            link.href = location
            link.rel = "self"
        self.Count = None

    def get_children(self):
        """Overridden to add generation of entries dynamically from
        :py:attr:`collection`.

        The collection's
        :py:meth:`pyslet.mc_csdl.EntityCollection.iterpage` method is
        used to iterate over the entities."""
        for child in super(Feed, self).get_children():
            yield child
        if self.Count:
            yield self.Count
        if self.collection is not None:
            if self.collection.inlinecount:
                count = Count(self)
                count.set_value(len(self.collection))
                yield count
            for entity in self.collection.iterpage():
                yield Entry(self, entity)
            # add a next link if necessary
            next_link = self.collection.get_next_page_location()
            if next_link is not None:
                link = Link(self)
                link.rel = "next"
                link.href = str(next_link)
                yield link

    def attach_to_doc(self, doc=None):
        """Overridden to prevent unnecessary iterations through the set
        of children.

        Our children do not have XML IDs"""
        return

    def detach_from_doc(self, doc=None):
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

    def get_children(self):
        if self.Feed:
            yield self.Feed
        if self.Entry:
            yield self.Entry
        for child in super(Inline, self).get_children():
            yield child


class Count(ODataElement):

    """Implements inlinecount handling."""
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'count')

    def set_value(self, new_value):
        super(Count, self).set_value(str(new_value))

    def get_value(self):
        return int(super(Count, self).get_value())


class Link(atom.Link):

    """Overrides the default :py:class:`pyslet.rfc4287.Link` class to
    add OData handling."""
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(Link, self).__init__(parent)
        self.Inline = None

    def get_children(self):
        if self.Inline:
            yield self.Inline
        for child in super(Link, self).get_children():
            yield child

    def expand(self, expansion):
        """Expands this element based on expansion."""
        inline = self.add_child(Inline)
        if isinstance(expansion, Entity):
            # it is hard to calculate the id
            entry = inline.add_child(Entry)
            entry.set_value(expansion)
        elif expansion:
            # we only add the feed if it is non-empty
            feed = inline.add_child(Feed)
            feed.collection = expansion
            feed.add_child(atom.AtomId).set_value(self.href)

    def load_expansion(self, deferred, exists=True):
        """Given a :py:class:`csdl.DeferredProperty` instance, adds an
        expansion if one is present in the link"""
        if self.Inline is not None:
            target_entity_set = deferred.target()
            with target_entity_set.open() as collection:
                if self.Inline.Entry is not None:
                    entity = collection.new_entity()
                    entity.exists = exists
                    self.Inline.Entry.get_value(entity)
                    entries = [entity]
                elif self.Inline.Feed is not None:
                    entries = []
                    for entry in self.Inline.Feed.find_children_depth_first(
                            Entry, sub_match=False):
                        entity = collection.new_entity()
                        entity.exists = exists
                        entry.get_value(entity)
                        entries.append(entity)
                deferred.set_expansion(
                    ExpandedEntityCollection(
                        from_entity=deferred.from_entity,
                        name=deferred.name,
                        entity_set=target_entity_set,
                        entity_list=entries))


class Entry(atom.Entry):

    """Overrides the default Entry class to add OData handling.

    In addition to the default *parent* element an Entry can be passed
    an optional `pyslet.mc_csdl.Entity` instance.  If present, it is
    used to construct the content of the entity.

    Finally, if *id* is also passed it is treated as the base URI of the
    entry and used to create the <id> and associated links.

    Entry instances can be suffixed with, e.g., ['PropertyName'] to get
    and set property values.  See :py:meth:`Property.get_value` and
    :py:meth:`Property.set_value` for more information."""
    ContentClass = Content
    LinkClass = Link

    def __init__(self, parent, entity=None):
        atom.Entry.__init__(self, parent)
        #: :py:class:`pyslet.mc_csdl.EntityType` instance describing the
        #: entry
        self.entityType = None
        #: properties element will be a direct child for media link
        #: entries
        self.Properties = None
        #: the etag associated with this entry or None if optimistic
        #: concurrency is not supported
        self.etag = None
        self._properties = {}
        if entity is not None:
            self.set_value(entity)

    def reset(self):
        if self.Properties:
            self.Properties.detach_from_parent()
            self.Properties = None
        self.etag = None
        self._properties = {}
        super(Entry, self).reset()

    def get_children(self):
        """Replaces the implementation in atom.Entry completed so that
        we can put the content last.  You never know, it is possible
        that someone will parse the metadata and properties and decide
        they don't want the content element and close the connection.
        The other way around might be annoying for large media
        resources."""
        for child in atom.Entity.get_children(self):
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
            plist = self.Content.Properties
        else:
            plist = self.Properties
        if plist:
            for p in plist.Property:
                self._properties[p.xmlname] = p

    def __getitem__(self, key):
        return self._properties[key].get_value()

    def __setitem__(self, key, value):
        if key in self._properties:
            p = self._properties[key].set_value(value)
        else:
            if self.Properties is None:
                ps = self.add_child(
                    self.ContentClass).add_child(Properties)
            else:
                ps = self.Properties
            p = ps.add_child(
                ps.PropertyClass, (ODATA_DATASERVICES_NAMESPACE, key))
            p.set_value(value)
            self._properties[key] = p

    def resolve_target_path(self, target_path, prefix, ns):
        doc = self.get_document()
        target_element = self
        for ename in target_path:
            new_target_element = None
            for eTest in target_element.get_children():
                if eTest.get_xmlname() == ename:
                    new_target_element = eTest
                    break
            if new_target_element is None:
                # we need to create a new element
                eclass = target_element.get_element_class(ename)
                if eclass is None and doc:
                    eclass = doc.get_element_class(ename)
                if eclass is None:
                    eclass = Document.get_element_class(ename)
                new_target_element = target_element.add_child(eclass, ename)
                if ename[0] == ns and \
                        new_target_element.get_prefix(ename[0]) is None:
                    # No prefix exists for this namespace, make one
                    new_target_element.make_prefix(ns, prefix)
            target_element = new_target_element
        return target_element

    def get_value(self, entity, entity_resolver=None, for_update=False):
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
            property_def = entity.type_def[k]
            target_path = property_def.get_target_path()
            if target_path and not property_def.keep_in_content():
                # This value needs to be read from somewhere special
                prefix, ns = property_def.get_fc_ns_prefix()
                target_element = self.resolve_target_path(target_path, prefix,
                                                          ns)
                if isinstance(target_element, atom.Date):
                    dt_offset = target_element.get_value()
                    if isinstance(v, edm.DateTimeOffsetValue):
                        v.set_from_value(dt_offset)
                    elif isinstance(v, edm.DateTimeValue):
                        # strip the zone and use that
                        v.set_from_value(dt_offset.with_zone(zdirection=None))
                    elif isinstance(v, edm.StringValue):
                        v.set_from_literal(str(dt_offset))
                    else:
                        # give up, treat this value as NULL
                        v.set_from_value(None)
                else:
                    # now we need to grab the actual value, only interested in
                    # data
                    data = []
                    for child in target_element.get_children():
                        if is_text(child):
                            data.append(child)
                    v.set_from_literal(''.join(data))
                    selected.add(k)
            else:
                # and watch out for unselected properties
                if k in self._properties:
                    self._properties[k].get_value(v)
                    selected.add(k)
                else:
                    # Property is not selected, make it NULL if not a key
                    if k not in entity.entity_set.keys:
                        v.set_null()
                    unselected.add(k)
        # Now set this entity's select property...
        if not unselected:
            entity.selected = None
        else:
            entity.selected = selected
        if entity.exists is False:
            # we need to look for any link bindings
            for link in self.Link:
                if not link.rel.startswith(ODATA_RELATED):
                    continue
                nav_property = link.rel[len(ODATA_RELATED):]
                if not entity.is_navigation_property(nav_property):
                    continue
                target_set = entity.entity_set.get_target(nav_property)
                # we have a navigation property we understand
                if link.Inline is not None:
                    with target_set.open() as collection:
                        if entity.is_entity_collection(nav_property):
                            for entry in link.Inline.Feed.\
                                    find_children_depth_first(Entry,
                                                              sub_match=False):
                                # create a new entity from the target entity
                                # set
                                target_entity = collection.new_entity()
                                entry.get_value(target_entity, entity_resolver)
                                entity[nav_property].bind_entity(target_entity)
                        elif link.Inline.Entry is not None:
                            target_entity = collection.new_entity()
                            link.Inline.Entry.get_value(
                                target_entity, entity_resolver)
                            entity[nav_property].bind_entity(target_entity)
                elif entity_resolver is not None:
                    #   this is the tricky bit, we need to resolve
                    #   the URI to an entity key
                    href = link.resolve_uri(link.href)
                    if not href.is_absolute():
                        #   we'll assume that the base URI is the
                        #   location of this entity once it is
                        #   created.  Witness this thread:
                        #   http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                        href = href.resolve(entity.get_location())
                    target_entity = entity_resolver(href)
                    if isinstance(target_entity, Entity) and \
                            target_entity.entity_set is target_set:
                        entity[nav_property].bind_entity(target_entity)
                    else:
                        raise InvalidData(
                            "Resource is not a valid target for %s: %s" %
                            (nav_property, str(href)))
                else:
                    raise InvalidData(
                        "No context to resolve entity URI: %s" % str(
                            link.href))
        elif for_update:
            # we need to look for any updated link bindings
            for link in self.Link:
                if not link.rel.startswith(ODATA_RELATED):
                    continue
                nav_property = link.rel[len(ODATA_RELATED):]
                if not entity.is_navigation_property(nav_property) or \
                        entity[nav_property].isCollection:
                    continue
                target_set = entity.entity_set.get_target(nav_property)
                # we have a navigation property we can update
                if entity_resolver is not None:
                    #   this is the tricky bit, we need to resolve
                    #   the URI to an entity key
                    href = link.resolve_uri(link.href)
                    if not href.is_absolute():
                        # we'll assume that the base URI is the location
                        # of this entity
                        # Witness this thread:
                        # http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
                        href = href.resolve(entity.get_location())
                    target_entity = entity_resolver(href)
                    if isinstance(target_entity, Entity) and \
                            target_entity.entity_set is target_set:
                        entity[nav_property].bind_entity(target_entity)
                    else:
                        raise InvalidData(
                            "Resource is not a valid target for %s: %s" %
                            (nav_property, str(href)))
                else:
                    raise InvalidData(
                        "No context to resolve entity URI: %s" % str(
                            link.href))
        else:
            # entity exists, look to see if it has been expanded
            for link in self.Link:
                if not link.rel.startswith(ODATA_RELATED):
                    continue
                nav_property = link.rel[len(ODATA_RELATED):]
                if not entity.is_navigation_property(nav_property):
                    continue
                target_set = entity.entity_set.get_target(nav_property)
                link.load_expansion(entity[nav_property])
        return entity

    def set_value(self, entity, for_update=False):
        """Sets the value of this Entry to represent *entity*

        entity
            A :py:class:`pyslet.mc_csdl.Entity` instance."""
        # start with a reset
        self.reset()
        media_link_resource = entity.type_def.has_stream()
        self.etag = entity.etag()
        # Now set the new property values, starting with entity-type
        # level feed customisation seems odd that there can only be one
        # of these but, hey...
        cat = self.add_child(atom.Category)
        cat.term = entity.type_def.get_fqname()
        cat.scheme = ODATA_SCHEME
        target_path = entity.type_def.get_target_path()
        if target_path:
            prefix, ns = entity.type_def.get_fc_ns_prefix()
            target_element = self.resolve_target_path(target_path, prefix, ns)
            source_path = entity.type_def.get_source_path()
            if source_path:
                v = entity
                for p in source_path:
                    if isinstance(v, (edm.Entity, edm.Complex)):
                        v = v[p]
                    else:
                        v = None
                        break
                if isinstance(target_element, atom.Date) and v:
                    if isinstance(v, edm.DateTimeOffsetValue):
                        target_element.set_value(to_text(v))
                    elif isinstance(v, edm.DateTimeValue):
                        # assume UTC
                        dt_offset = v.value.with_zone(zdirection=0)
                        target_element.set_value(to_text(dt_offset))
                    elif isinstance(v, edm.StringValue):
                        try:
                            dt_offset = iso.TimePoint.from_str(v.value)
                            if dt_offset.get_zone()[0] is None:
                                dt_offset = dt_offset.with_zone(zdirection=0)
                            target_element.set_value(to_text(dt_offset))
                        except iso.DateTimeError:
                            # do nothing
                            pass
                elif isinstance(v, edm.SimpleValue) and v:
                    target_element.add_data(to_text(v))
        # now do the links
        location = str(entity.get_location())
        self.add_child(atom.AtomId).set_value(location)
        if entity.exists and not for_update:
            link = self.add_child(self.LinkClass)
            link.href = location
            link.rel = "edit"
            if media_link_resource:
                link = self.add_child(self.LinkClass)
                link.href = location + "/$value"
                link.rel = "edit-media"
                if self.etag:
                    link.set_attribute(
                        (ODATA_METADATA_NAMESPACE, 'etag'),
                        Entity.format_etag(self.etag,
                                           entity.etag_is_strong()))
            for nav_property, navValue in entity.navigation_items():
                link = self.add_child(self.LinkClass)
                link.href = location + '/' + nav_property
                link.rel = ODATA_RELATED + nav_property
                link.title = nav_property
                if navValue.isCollection:
                    link.type = ODATA_RELATED_FEED_TYPE
                else:
                    link.type = ODATA_RELATED_ENTRY_TYPE
                if navValue.isExpanded:
                    # This property has been expanded
                    if navValue.isCollection:
                        link.expand(navValue.open())
                    else:
                        link.expand(navValue.get_entity())
        elif for_update:
            # This is a special form of representation which only
            # represents the navigation properties with single
            # cardinality
            for k, dv in entity.navigation_items():
                if not dv.bindings or dv.isCollection:
                    # nothing to do here, we can't update this type of
                    # navigation property
                    continue
                # we need to know the location of the target entity set
                target_set = dv.target()
                binding = dv.bindings[-1]
                if isinstance(binding, Entity):
                    if binding.exists:
                        href = str(target_set.get_location()) + \
                            ODataURI.format_entity_key(binding)
                    else:
                        # we can't create new entities on update
                        continue
                else:
                    href = str(target_set.get_location()) + \
                        ODataURI.format_key_dict(
                            target_set.get_key_dict(binding))
                link = self.add_child(self.LinkClass)
                link.rel = ODATA_RELATED + k
                link.title = k
                link.href = href
        else:
            # entity does not exist...
            for k, dv in entity.navigation_items():
                if not dv.bindings:
                    continue
                target_set = dv.target()
                feed = []
                for binding in dv.bindings:
                    if isinstance(binding, Entity):
                        if binding.exists:
                            href = str(target_set.get_location()) + \
                                ODataURI.format_entity_key(binding)
                        else:
                            feed.append(binding)
                            href = None
                    else:
                        href = str(target_set.get_location()) + \
                            ODataURI.format_key_dict(
                                target_set.get_key_dict(binding))
                    if href:
                        link = self.add_child(self.LinkClass)
                        link.rel = ODATA_RELATED + k
                        link.title = k
                        link.href = href
                if feed:
                    link = self.add_child(self.LinkClass)
                    link.rel = ODATA_RELATED + k
                    link.title = k
                    link.href = location + '/' + k
                    if dv.isCollection:
                        feed = ExpandedEntityCollection(
                            from_entity=entity,
                            name=k,
                            entity_set=target_set,
                            entity_list=feed)
                        link.expand(feed)
                    elif len(feed) > 1:
                        raise edm.NavigationError(
                            "Multiple bindings found for navigation property "
                            "%s.%s" % (entity.entity_set.name, k))
                    else:
                        link.expand(feed[0])
        # Now set the new property values in the properties element
        if media_link_resource:
            self.add_child(Properties)
            # and populate the content element itself
            content = self.add_child(Content)
            content.set_attribute('src', location + "/$value")
            content.type = str(entity.get_content_type())
        else:
            self.add_child(Content).add_child(Properties)
        for k, v in entity.data_items():
            # catch property-level feed customisation here
            property_def = entity.type_def[k]
            target_path = property_def.get_target_path()
            if target_path:
                # This value needs to go somewhere special
                prefix, ns = property_def.get_fc_ns_prefix()
                target_element = self.resolve_target_path(target_path, prefix,
                                                          ns)
                self.set_fcvalue(target_element, v)
                if not property_def.keep_in_content():
                    continue
            # and watch out for unselected properties
            if entity.is_selected(k):
                self[k] = v
        self.content_changed()

    def set_fcvalue(self, target_element, v):
        if isinstance(target_element, atom.Date) and v:
            if isinstance(v, edm.DateTimeOffsetValue):
                target_element.set_value(to_text(v))
            elif isinstance(v, edm.DateTimeValue):
                # assume UTC
                dt_offset = v.value.with_zone(zdirection=0)
                target_element.set_value(to_text(dt_offset))
            elif isinstance(v, edm.StringValue):
                try:
                    dt_offset = iso.TimePoint.from_str(v.value)
                    if dt_offset.get_zone()[0] is None:
                        dt_offset = dt_offset.with_zone(zdirection=0)
                    target_element.set_value(to_text(dt_offset))
                except iso.DateTimeError:
                    # do nothing
                    pass
        elif isinstance(v, edm.SimpleValue) and v:
            target_element.add_data(to_text(v))


class URI(ODataElement):

    """Represents a single URI in the XML-response to $links requests"""
    XMLNAME = (ODATA_DATASERVICES_NAMESPACE, 'uri')


class Links(ODataElement):

    """Represents a list of links in the XML-response to $links requests"""
    XMLNAME = (ODATA_DATASERVICES_NAMESPACE, 'links')

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.URI = []

    def get_children(self):
        return itertools.chain(
            self.URI,
            ODataElement.get_children(self))


class Error(ODataElement):
    XMLNAME = (ODATA_METADATA_NAMESPACE, 'error')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        ODataElement.__init__(self, parent)
        self.Code = Code(self)
        self.Message = Message(self)
        self.InnerError = None

    def get_children(self):
        yield self.Code
        yield self.Message
        if self.InnerError:
            yield self.InnerError

    @old_method('GenerateStdErrorJSON')
    def generate_std_error_json(self):
        yield '{"error":{"code":%s,"message":%s' % (
            json.dumps(self.Code.get_value()),
            json.dumps(self.Message.get_value()))
        if self.InnerError:
            yield ',"innererror":%s' % json.dumps(self.InnerError.get_value())
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
        self.make_prefix(ODATA_METADATA_NAMESPACE, 'm')
        self.make_prefix(ODATA_DATASERVICES_NAMESPACE, 'd')

    @classmethod
    def get_element_class(cls, name):
        """Returns the OData, APP or Atom class used to represent name.

        Overrides :py:meth:`~pyslet.rfc5023.Document.get_element_class`
        to allow custom implementations of the Atom or APP classes to be
        created and to cater for OData-specific elements."""
        result = Document.classMap.get(name, None)
        if result is None:
            if name[0] == ODATA_DATASERVICES_NAMESPACE:
                result = Property
            else:
                result = app.Document.get_element_class(name)
        return result

xmlns.map_class_elements(Document.classMap, globals())
