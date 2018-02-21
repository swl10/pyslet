#! /usr/bin/env python

import base64
import contextlib
import json
import math

from ..py2 import (
    force_ascii,
    is_text,
    SortableMixin,
    to_text,
    )
from ..xml import xsdatatypes as xsi

from . import (
    errors,
    names,
    )


class Operator(xsi.Enumeration):
    """Enumeration for operators

    ::

            Operator.eq
            Operator.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "eq": 1,
        "ne": 2,
        "lt": 3,
        "le": 4,
        "gt": 5,
        "ge": 6,
        "has": 7,
        "and": 8,
        "or": 9,
        "add": 10,
        "sub": 11,
        "mul": 12,
        "div": 13,
        "mod": 14,
        "not": 15,
        "negate": 16,
        "isof": 17,
        "cast": 18,
        "member": 19,
        "call": 20,
        "lambda_bind": 21,
        "bind": 22,
        "collection": 23,
        "record": 24,
        "member_bind": 25,
        "if": 26,
        "args": 27,
        "atom": 100
    }

    aliases = {
        'bool_not': 'not',
        'bool_and': 'and',
        'bool_or': 'or',
        'bool_test': 'if',
        }


class Method(xsi.Enumeration):
    """Enumeration for method names

    ::

            Operator.indexof
            Operator.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "indexof": 1,
        "tolower": 2,
        "toupper": 3,
        "trim": 4,
        "substring": 5,
        "concat": 6,
        "length": 7,
        "year": 8,
        "month": 9,
        "day": 10,
        "hour": 11,
        "minute": 12,
        "second": 13,
        "fractionalseconds": 14,
        "totalseconds": 15,
        "date": 16,
        "time": 17,
        "round": 18,
        "floor": 19,
        "ceiling": 20,
        "totaloffsetminutes": 21,
        "mindatetime": 22,
        "maxdatetime": 23,
        "now": 24,
        "endswith": 25,
        "startswith": 26,
        "contains": 27,
        "geo.distance": 28,
        "geo.length": 29,
        "geo.intersects": 30,
        }

    aliases = {
        'geo_distance': 'geo.distance',
        'geo_length': 'geo.length',
        'geo_intersects': 'geo.intersects',
        }


class CommonExpression(SortableMixin):

    """Abstract class for all expression objects."""

    def sortkey(self):
        # by default, expressions have max precedence
        return 100

    def otherkey(self, other):
        if isinstance(other, CommonExpression):
            return other.sortkey()
        else:
            return NotImplemented

    def evaluate(self, evaluator):
        raise NotImplementedError("Evaluation of %s" % repr(self))

    def is_common(self):
        """Returns True if we match commonExpr in the ABNF

        Although this abstract class describes common expressions it is
        not the case that all instances are valid common expressions.
        There are some obvious exceptions, such as binary operators with
        incomplete argument lists, and some less obvious problems such
        as expressions like $root which, on their own, are not actually
        expressions even though they are represented here as an
        evaluable path segment."""
        return False

    def is_bool_common(self):
        """Returns True if we match boolCommonExpr in the ABNF

        This test is not really a syntax checker as the original ABNF
        in 4.0 is flawed and is being replaced in 4.01 with a simple
        statement that any commonExpr is a boolCommonExpr if it results
        in a boolean value.

        By following this more generous interpretation we only return
        False when we are not a valid commonExpr or when we know that
        the expression cannot result in a boolean, e.g., a primitive
        literal integer is not a boolean.  This has some surprising
        implications, strings like "INF" are ambiguous and could refer
        to properties or the built-in floating point infinity, as a
        result they return True because the "INF" property could be
        Edm.Boolean: the interpretation will depend on the context in
        which the expression is evaluated."""
        return False

    def is_root(self):
        """Returns True if we match rootExpr in the ABNF

        The root expression is always a MemberExpression where the left
        node is a RootExpression and the right node is either (i) an
        IdentifierExpression or (ii) a CallExpression (matching
        entitySetName keyPredicate) or (iii) another MemberExpression
        with left node matching (i) or (ii) and right node matching
        memberExpr."""
        return False

    def is_first_member(self):
        """Returns True if we match firstMemberExpr in the ABNF

        All member expressions are first member expressions so we
        test :meth:`is_member` here.  Other possibilities are
        (i) the implicit variable $it; (ii) an identifier of
        a lambda variable or (iii) a MemberExpression where
        the left node is (i) or (ii) and the right node is
        a member expression.

        Note that (ii) is indistinguishable from a memberExpr itself (we
        can't look up the tree to validate that we're in an appropriate
        lambda context)."""
        return self.is_member()

    def is_member(self):
        """Returns True if we match memberExpr in the ABNF

        A memberExpr is either a (i) propertyPathExpr (see below), (ii)
        a boundFunctionExpr or (iii) it's a MemberExpression (with a
        left node that's a QNameExpression and a right node that is (i)
        or (ii)."""
        return self.is_property_path() or self.is_function()

    def is_property_path(self):
        """Returns True if we match propertyPathExpr in ABNF

        The ambiguity between CallExpression and collection navigation
        in the syntax allows schemas to define navigation properties
        with names that hide built in method names.  We take a fairly
        strict approach during evaluation, if there is a navigation
        property in scope then it will always be matched in preference
        to the built-in method.  As a result, use of a built in method
        in a query context where its name is hidden will always be
        interpreted as navigation even if (as is likely) the method call
        arguments do not match the expected key predicate.  This
        behaviour is designed to ensure consistency in evaluation even
        when new built in methods are added to the OData specifiation
        itself."""
        return False

    def is_collection_path(self):
        """Returns True if we match collectionPathExpr in ABNF

        By default, we just check if we're a boundFunctionExpr, other
        classes override for other rules."""
        return self.is_function()

    def is_function(self):
        """Returns True if we match functionExpr/boundFunctionExpr in ABNF."""
        return False

    def is_function_parameter(self):
        """Returns True if we match functionParameter in ABNF."""
        return False

    def is_search(self):
        """Returns True if we match searchExpr in ABNF."""
        return False


class LiteralExpression(CommonExpression):

    """Class representing a literal expression

    For example, values matching primitiveLiteral in the ABNF.  We
    actually store the expression's value 'unboxed', that is, as a raw
    value rather than a transient :class:`data.Value` instance."""

    def __init__(self, value):
        self.value = value

    def is_common(self):
        """Returns True: all primitive literals satisfy commonExpr"""
        return True

    def evaluate(self, evaluator):
        raise NotImplementedError("Evaluation of %s" % repr(self))


class NullExpression(LiteralExpression):

    """Class representing a null literal"""

    def __init__(self):
        self.value = None

    def evaluate(self, evaluator):
        return evaluator.null()


class BooleanExpression(LiteralExpression):

    """Class representing a boolean literal"""

    def is_bool_common(self):
        return True

    def evaluate(self, evaluator):
        return evaluator.boolean(self.value)


class GuidExpression(LiteralExpression):

    """Class representing a guid literal"""

    def evaluate(self, evaluator):
        return evaluator.guid(self.value)


class DateExpression(LiteralExpression):

    """Class representing a date literal"""

    def evaluate(self, evaluator):
        return evaluator.date(self.value)


class DateTimeOffsetExpression(LiteralExpression):

    """Class representing a dateTimeOffset literal"""

    def __init__(self, value, literal=None):
        super(DateTimeOffsetExpression, self).__init__(value)
        if literal is None:
            self.literal = value.get_calendar_string(ndp=6, dp='.')
        else:
            self.literal = literal

    def evaluate(self, evaluator):
        return evaluator.date_time_offset(self.value, self.literal)


class TimeOfDayExpression(LiteralExpression):

    """Class representing a timeOfDay literal"""

    def __init__(self, value, literal=None):
        super(TimeOfDayExpression, self).__init__(value)
        if literal is None:
            self.literal = value.get_string(ndp=6, dp='.')
        else:
            self.literal = literal

    def evaluate(self, evaluator):
        return evaluator.time_of_day(self.value, self.literal)


class DecimalExpression(LiteralExpression):

    def evaluate(self, evaluator):
        return evaluator.decimal(self.value)


class DoubleExpression(LiteralExpression):

    """Class representing a double literal

    To preserve accuracy we allow the value to be a Decimal or a
    float."""

    def evaluate(self, evaluator):
        return evaluator.double(self.value)


class Int64Expression(LiteralExpression):

    def evaluate(self, evaluator):
        return evaluator.int64(self.value)


class StringExpression(LiteralExpression):

    def evaluate(self, evaluator):
        return evaluator.string(self.value)


class DurationExpression(LiteralExpression):

    """Class representing a duration literal"""

    def __init__(self, value, literal=None):
        super(DurationExpression, self).__init__(value)
        if literal is None:
            self.literal = value.get_string(truncate_zeros=True, ndp=6, dp='.')
        else:
            self.literal = literal

    def evaluate(self, evaluator):
        return evaluator.duration(self.value, self.literal)


class BinaryDataExpression(LiteralExpression):

    def evaluate(self, evaluator):
        return evaluator.binary(self.value)


class EnumExpression(LiteralExpression):

    def evaluate(self, evaluator):
        return evaluator.enum(self.value)


class GeographyExpression(LiteralExpression):

    def __init__(self, value, literal=None):
        super(GeographyExpression, self).__init__(value)
        if literal is None:
            self.literal = to_text(value)
        else:
            self.literal = literal

    def evaluate(self, evaluator):
        return evaluator.geography(self.value, self.literal)


class GeometryExpression(LiteralExpression):

    def __init__(self, value, literal=None):
        super(GeometryExpression, self).__init__(value)
        if literal is None:
            self.literal = to_text(value)
        else:
            self.literal = literal

    def evaluate(self, evaluator):
        return evaluator.geometry(self.value, self.literal)


class ParameterExpression(CommonExpression):

    """Class representing a parameter reference"""

    def __init__(self, name):
        self.name = name

    def is_common(self):
        """Returns True: all parameter aliases satsify commonExpr"""
        return True

    def is_bool_common(self):
        """Returns True: parameters may resolve to booleans"""
        return True

    def evaluate(self, evaluator):
        return evaluator.parameter(self.name)


class RootExpression(CommonExpression):

    """Class representing $root path segment in expressions."""

    def evaluate(self, evaluator):
        return evaluator.root()


class ItExpression(CommonExpression):

    """Class representing $it path segment in expressions."""

    def is_common(self):
        return True

    def is_bool_common(self):
        """Returns True: $it could refer to a boolean"""
        return True

    def is_first_member(self):
        return True

    def evaluate(self, evaluator):
        return evaluator.implicit_variable()


class IdentifierExpression(CommonExpression):

    """Class representing a simple odataIdentifier in an expression

    Taken in isolation, an identifier expression is evaluated using the
    :meth:`ExpressionProcessor.first_member` expression but if that
    fails then it checks if the identifier is actually one of the
    reserved names: INF, NaN, true, false or null.

    The implications of this rule is that you can hide reserved names
    using similarly named properties.  This type of thing happens quite
    a lot in contexts where a mapping is created automatically for a
    schema that was not originally designed with the target language's
    reserved words in mind.  You can workaround the problem for "true"
    and "false" as the ABNF defines these case *insensitive* whereas
    properties are case sensitive, hence using "TRUE" and "FALSE" would
    ensure they are interpreted as the built in booleans in expressions
    where "true" is ambiguous."""

    def __init__(self, identifier):
        self.identifier = identifier

    def is_common(self):
        """Returns True: all identifiers satsify commonExpr"""
        return True

    def is_bool_common(self):
        """Returns True: all identifiers could result in booleans"""
        return True

    def is_member(self):
        """Returns True: all identifiers are valid member expressions"""
        return True

    def is_property_path(self):
        """Returns True: all identifiers are valid property paths"""
        return True

    def evaluate(self, evaluator):
        try:
            return evaluator.first_member(self.identifier)
        except errors.PathError:
            if self.identifier == 'INF':
                return evaluator.double(float('inf'))
            elif self.identifier == 'NaN':
                return evaluator.double(float('nan'))
            elif self.identifier.lower() == 'true':
                # case insensitive ABNF!
                return evaluator.boolean(True)
            elif self.identifier.lower() == 'false':
                # case insensitive in ABNF!
                return evaluator.boolean(False)
            elif self.identifier == 'null':
                return evaluator.null()
            else:
                raise


class QNameExpression(CommonExpression):

    """Class representing a qualified name in an expression"""

    def __init__(self, qname):
        self.identifier = qname

    def evaluate(self, evaluator):
        return evaluator.first_member(self.identifier)


class TermRefExpression(CommonExpression):

    """Class representing an annotation term refererence"""

    def __init__(self, term_ref):
        self.identifier = term_ref


class OperatorExpression(CommonExpression):

    """Class representing an operator expression"""

    def __init__(self, op_code):
        self.op_code = op_code
        self.operands = []

    precedence = {
        Operator.lambda_bind: -1,       # ':' in 'any(x:x eq 5)'
        Operator.bind: -1,              # '=' in 'Product(ID=2)'
        Operator.bool_test: 0,          # <If> element
        Operator.bool_or: 1,
        Operator.bool_and: 2,
        Operator.ne: 3,
        Operator.eq: 3,
        Operator.gt: 4,
        Operator.ge: 4,
        Operator.lt: 4,
        Operator.le: 4,
        Operator.isof: 4,
        Operator.add: 5,
        Operator.sub: 5,
        Operator.mul: 6,
        Operator.div: 6,
        Operator.mod: 6,
        Operator.negate: 7,
        Operator.bool_not: 7,
        Operator.cast: 7,
        Operator.member: 8,
        Operator.has: 8,
        Operator.collection: 8,
        Operator.record: 8,
        Operator.call: 9,
        Operator.atom: 100,
        }

    def sortkey(self):
        return self.precedence.get(self.op_code, 0)

    def add_operand(self, operand):
        self.operands.append(operand)

    @classmethod
    def binary_format(cls, a, b, op, op_pattern):
        """Formats a binary expression

        a and b are previous obtained results (tuples of operator and
        string generated by ExpressionFormatter), op is the joining
        operator and op_pattern is the string pattern to use.  This
        method takes responsibility for checking the precedence of op
        against the (weakest) operators in the two expressions and
        bracketing as necessary.

        It returns a tuple or op (unchanged) and the formatted string
        created from op_pattern."""
        aop, astr = a
        p = cls.precedence[op]
        if p > cls.precedence[aop]:
            astr = "(%s)" % astr
        bop, bstr = b
        if p > cls.precedence[bop]:
            bstr = "(%s)" % bstr
        return op, op_pattern % (astr, bstr)

    @classmethod
    def unary_format(cls, value, op, op_pattern):
        """Formats a binary expression

        value is previously obtained result (tuples of operator and
        string generated by ExpressionFormatter), op is the unary
        operator and op_pattern is the string pattern to use.  This
        method takes responsibility for checking the precedence of op
        against the operator of the value and bracketing as necessary.

        It returns a tuple or op (unchanged) and the formatted string
        created from op_pattern."""
        vop, vstr = value
        p = cls.precedence[op]
        if p > cls.precedence[vop]:
            vstr = "(%s)" % vstr
        return op, op_pattern % vstr

    def evaluate(self, evaluator):
        raise NotImplementedError(
            "Evaluation of %s" % Operator.to_str(self.op_code))


class CollectionExpression(OperatorExpression):

    """Class representing an expression that evaluates to a collection

    In inline syntax, JSON formatted collections must contain literal
    expressions (directly or indirectly through other collections/record
    expressions) or rootExprs evaluating to paths of entities for
    navigation. When used in Annotations we are more liberal and use
    this node to express the <Collection> element which may contain
    arbitrary common expressions as the elements."""

    def __init__(self):
        OperatorExpression.__init__(self, Operator.collection)

    def is_common(self):
        """Returns True: all collections satsify commonExpr"""
        return True

    def evaluate(self, evaluator):
        return evaluator.collection(self.operands)


class RecordExpression(OperatorExpression):

    """Class representing an expression that evaluates to a Record

    In inline syntax, JSON formatted objects must contain literal
    expressions (directly or indirectly through other collections/record
    expressions) or rootExprs evaluating to paths of entities for
    navigation.  When used in Annotations we are more liberal and use
    this node to express the <Record> element which may contain
    arbitrary common expressions in the bindings."""

    def __init__(self):
        OperatorExpression.__init__(self, Operator.record)

    def is_common(self):
        """Returns True: all collections satsify commonExpr"""
        return True

    def add_operand(self, operand):
        if not isinstance(operand, MemberBindExpression):
            raise ValueError(
                "record required MemberBindExpression not %r" % operand)
        super(RecordExpression, self).add_operand(operand)

    def evaluate(self, evaluator):
        bindings = []
        for arg in self.operands:
            name = arg.name
            name = name if is_text(name) else to_text(name)
            bindings.append((name, arg.operands[0]))
        return evaluator.record(bindings)


class BindBaseExpression(OperatorExpression):

    name_class = IdentifierExpression

    def add_operand(self, operand):
        if self.name is None:
            # first operand must be an identifier or a term reference!
            if isinstance(operand, self.name_class):
                self.name = operand.identifier
            else:
                raise ValueError(
                    "bind expression requires identifier not %r" % operand)
        else:
            if len(self.operands):
                raise ValueError("bind expression must be single-valued")
            super(BindBaseExpression, self).add_operand(operand)


class MemberBindExpression(BindBaseExpression):

    name_class = (IdentifierExpression, TermRefExpression)

    def __init__(self):
        OperatorExpression.__init__(self, Operator.member_bind)
        self.name = None

    def evaluate(self, evaluator):
        raise errors.ExpressionError("record member expression out of context")


class BinaryExpression(OperatorExpression):

    """Class representing binary operator expression"""

    def __init__(self, op_code):
        OperatorExpression.__init__(self, op_code)
        self.bracket_hint = False

    def add_operand(self, operand):
        if len(self.operands) > 1:
            raise ValueError("binary operator already bound")
        super(BinaryExpression, self).add_operand(operand)


class MemberExpression(BinaryExpression):

    """Class representing the "/" used in path expressions

    Member expressions are unusual in that the expression trees are
    rotated to force right-associativity.  This is done automatically
    during construction.  This makes the implementations of the
    production test methods much easier!."""

    def __init__(self):
        BinaryExpression.__init__(self, Operator.member)

    def add_operand(self, operand):
        if isinstance(operand, MemberExpression):
            if not self.operands:
                # first time around, rotate to force right-associative
                # evaluation
                self.operands.append(operand._rotate())
                self.operands.append(operand)
            elif len(self.operands) == 1:
                super(MemberExpression, self).add_operand(operand)
            else:
                # add the operand to our right-hand child
                self.operands[1].add_operand(operand)
        elif len(self.operands) > 1:
            self.operands[1].add_operand(operand)
        else:
            super(MemberExpression, self).add_operand(operand)

    def _rotate(self):
        # return our left operand
        lop = self.operands[0]
        rop = self.operands[1]
        if isinstance(rop, MemberExpression):
            self.operands[0] = rop._rotate()
        else:
            del self.operands[0]
        return lop

    def _next_node(self):
        rnode = self.operands[1]
        if isinstance(rnode, MemberExpression):
            if len(rnode.operands) == 2:
                return rnode.operands
            else:
                return None, None
        else:
            return rnode, None

    def is_common(self):
        """Returns True if we're a rootExpr or firstMemberExpr"""
        if len(self.operands) == 2:
            return self.is_first_member() or self.is_root()
        else:
            return False

    def is_bool_common(self):
        return self.is_common()

    def is_root(self):
        """Returns True if we match rootExpr in the ABNF

        The root expression is always a MemberExpression where the left
        node is a RootExpression and the next node is either (i) an
        IdentifierExpression or (ii) a CallExpression (with operands
        matching keyPredicate).  Any trailing expression must match
        memberExpr (via rule singleNavigationExpr)."""
        if len(self.operands) != 2:
            return False
        if not isinstance(self.operands[0], RootExpression):
            return False
        next_node, trailer = self._next_node()
        if isinstance(next_node, IdentifierExpression) or (
                isinstance(next_node, CallExpression) and
                next_node.is_id_and_key()):
            return trailer is None or trailer.is_member()
        else:
            return False

    def is_first_member(self):
        if len(self.operands) != 2:
            return False
        if self.is_member():
            # lambdaVariableExpr is just odataIdentifier and will be
            # caught here as memberExpr may be just a propertyPathExpr
            # which itself matches:
            # odataIdentifier "/" memberExpr
            return True
        else:
            lnode = self.operands[0]
            rnode = self.operands[1]
            if not isinstance(lnode, ItExpression):
                return False
            return rnode.is_member()

    def is_member(self):
        # a propertyPathExpr or boundFunctionExpr optionally preceeded
        # by qualifiedEntityTypeName
        if len(self.operands) != 2:
            return False
        if self.is_property_path() or self.is_function():
            return True
        lnode = self.operands[0]
        rnode = self.operands[1]
        if isinstance(lnode, QNameExpression):
            return rnode.is_property_path() or rnode.is_function()
        else:
            return False

    def is_property_path(self):
        """Matches propertyPathExpr.

        A complex syntax but reduces to an odataIdentifier optionally
        followed by one of::

            collectionNavigationExpr
            singleNavigationExpr -- which is just "/" memberExpr
            collectionPathExpr
            complexPathExpr -- which is effectively "/" memberExpr
            singlePathExpr -- which is just boundFunctionExpr

        We further optimise because all boundFunctionExprs are
        memberExprs::

            odataIdentifier (
                memberExpr \
                collectionNavigationExpr \
                collectionPathExpr)

        Expanding just collectionNavigationExpr::

            [ "/" qualifiedEntityTypeName ] (
                keyPredicate [ singleNavigationExpr ] /
                collectionPathExpr )

            "/" qualifiedEntityTypeName keyPredicate
                [ singleNavigationExpr ] /
            "/" qualifiedEntityTypeName collectionPathExpr /
            keyPredicate [ singleNavigationExpr ] /
            collectionPathExpr -- already covered

        In our expression tree, keyPredicates are attached to their
        preceeding syntax production so this translates the combined
        rule into...

            IdentifierExpression (
                node.is_member /
                CallExpression.is_qname_and_key [ node.is_member ] /
                QNameExpression node.is_collection_path /
                node.is_collection_path
                ) /
            CallExpression.is_id_and_key [ node.is_member ]

        The last case is only partly handled here, when there is no
        trailing path CallExpression handles the rule directly."""
        if len(self.operands) != 2:
            return False
        lnode = self.operands[0]
        rnode = self.operands[1]
        if isinstance(lnode, IdentifierExpression):
            if rnode.is_member() or rnode.is_collection_path():
                return True
            next_node, trailer = self._next_node()
            if (isinstance(next_node, CallExpression) and
                    next_node.is_qname_and_key() and
                    (trailer is None or trailer.is_member())):
                return True
            if (isinstance(next_node, QNameExpression) and
                    (trailer is not None and trailer.is_collection_path())):
                return True
        elif (isinstance(lnode, CallExpression) and
                lnode.is_id_and_key()):
            return rnode.is_member()
        return False

    def is_function(self):
        """Matches functionExpr/boundFunctionExpr.

        A complex syntax but reduces to a qualified name with function
        parameters optionally followed by one of::

            collectionNavigationExpr
            singleNavigationExpr
            collectionPathExpr
            complexPathExpr
            singlePathExpr

        This rule is therefore very similar to :meth:`is_property_path`
        but there is an important difference in the special case where a
        bound function call rerurns an entity set that is followed
        immediately by a keyPredicate (allowed through
        collectionNavigationExpr). In that special case we must be
        followed by singleNavigationExpr (aka memberExpr).  The
        is_function on CallExpression takes an additional argument to
        help us make this distinction.

            CallExpression.is_function(with_key=True) node.is_member

            CallExpression.is_function(with_key=False)
                node.is_member /
                CallExpression.is_qname_and_key [ node.is_member ] /
                QNameExpression node.is_collection_path /
                node.is_collection_path
                )"""
        if len(self.operands) != 2:
            return False
        lnode = self.operands[0]
        rnode = self.operands[1]
        if not isinstance(lnode, CallExpression):
            return False
        if lnode.is_function(with_key=True):
            return rnode.is_member()
        elif lnode.is_function():
            if rnode.is_member() or rnode.is_collection_path():
                return True
            next_node, trailer = self._next_node()
            if (isinstance(next_node, CallExpression) and
                    next_node.is_qname_and_key() and
                    (trailer is None or trailer.is_member())):
                return True
            if (isinstance(next_node, QNameExpression) and
                    (trailer is not None and trailer.is_collection_path())):
                return True
        return False

    def evaluate(self, evaluator):
        lnode = self.operands[0]
        if isinstance(lnode, IdentifierExpression):
            # special handling, we don't need the default fall backs
            # because this must be a first member expression
            context = evaluator.first_member(lnode.identifier)
        else:
            context = lnode.evaluate(evaluator)
        with evaluator.new_context(context):
            return self.evaluate_path_node(self.operands[1], evaluator)

    def evaluate_path_node(self, node, evaluator):
        if isinstance(node, MemberExpression):
            # onwards evaluation of this path
            lnode = node.operands[0]
            if isinstance(lnode, IdentifierExpression):
                context = evaluator.member(lnode.identifier)
            else:
                context = node.evaluate_path_node(node.operands[0], evaluator)
            with evaluator.new_context(context):
                return self.evaluate_path_node(node.operands[1], evaluator)
        elif isinstance(node, (IdentifierExpression, QNameExpression)):
            return evaluator.member(node.identifier)
        elif isinstance(node, CallExpression):
            return node.evaluate_path_node(evaluator)
        elif isinstance(node, CountExpression):
            return evaluator.member_count()
        else:
            raise errors.ExpressionError("%r in path" % node)


class CountExpression(CommonExpression):

    """Class representing $count path segment in expressions.

    Only occurrs within a MemberExpression, evaluation is handled
    there."""

    def is_collection_path(self):
        return True


class CallExpression(BinaryExpression):

    def __init__(self):
        OperatorExpression.__init__(self, Operator.call)
        self.method = None

    def add_operand(self, operand):
        if self.operands:
            if not isinstance(operand, ArgsExpression):
                raise ValueError("CallExpression requires Args")
        else:
            if not isinstance(
                    operand,
                    (IdentifierExpression, QNameExpression, CallExpression)):
                raise ValueError("%r is not callable" % operand)
            if isinstance(operand, (IdentifierExpression, QNameExpression)):
                identifier = to_text(operand.identifier)
                try:
                    self.method = Method.from_str(identifier)
                    if Method.to_str(self.method) != identifier:
                        # we don't want aliases
                        self.method = None
                except ValueError:
                    pass
        super(CallExpression, self).add_operand(operand)

    def is_id_and_key(self):
        """Tests odataIdentifier keyPredicate

        Only defined for CallExpression nodes.  The name of this call
        must be an identifier and the arguments must match keyPredicate
        (see :meth:`ArgsExpression.is_key_predicate`)."""
        if len(self.operands) != 2:
            return False
        name = self.operands[0]
        args = self.operands[1]
        return (isinstance(name, IdentifierExpression) and
                args.is_key_predicate())

    def is_qname_and_key(self):
        if len(self.operands) != 2:
            return False
        name = self.operands[0]
        args = self.operands[1]
        return (isinstance(name, QNameExpression) and
                args.is_key_predicate())

    def is_method_call(self):
        """Tests methodCallExpr"""
        args = self.operands[1]
        return (self.method is not None and args.is_method_parameters())

    def is_type_call(self):
        """Tests isofExpr and castExpr"""
        name = self.operands[0]
        args = self.operands[1]
        return (isinstance(name, IdentifierExpression) and
                name.identifier in ("cast", "isof") and args.is_type_args())

    def is_common(self):
        """Returns True if we match one of the standalone call forms

        The standalone forms are::

            firstMemberExpr
            functionExpr
            methodCallExpr
            castExpr
            isofExpr

        The first production covers all paths but the one that results
        in a standalone CallExpression is::

            entityColNavigationProperty keyPredicate"""
        if len(self.operands) == 2:
            return (self.is_id_and_key() or self.is_function() or
                    self.is_method_call() or self.is_type_call())
        else:
            return False

    def is_bool_common(self):
        """Returns True if we may be a boolean expression

        Given that navigation properties can hide built-in methods any
        call that could match navigation(key) returns True, otherwise
        any functionExpr returns True but method calls with more than
        one parameter only return True if they are known to be boolean
        expressions."""
        if len(self.operands) == 2:
            if self.is_function():
                return True
            if self.is_method_call() and (
                    self.method in (Method.endswith, Method.startswith,
                                    Method.contains, Method.geo_intersects)):
                return True
            if self.is_type_call() and self.operands[0].identifier == "isof":
                return True
        return False

    def is_property_path(self):
        return self.is_id_and_key()

    def is_function(self, with_key=False):
        """Tests functionExpr/boundFunctionExpr

        We take an additional parameter:

        with_key
            An optional boolean constraining whether or not an
            additional keyPredicate is required (True).  The
            default is False indicating that a keyPredicate may
            or may not be present."""
        if len(self.operands) != 2:
            return False
        lnode = self.operands[0]
        args = self.operands[1]
        if isinstance(lnode, QNameExpression):
            return not with_key and args.is_function_parameters()
        elif isinstance(lnode, CallExpression) and args.is_key_predicate():
            name = lnode.operands[0]
            args = lnode.operands[1]
            return (isinstance(name, QNameExpression) and
                    args.is_function_parameters())
        else:
            return False

    def is_collection_path(self):
        if len(self.operands) != 2:
            return False
        name = self.operands[0]
        args = self.operands[1]
        if (isinstance(name, IdentifierExpression) and
                isinstance(args, ArgsExpression)):
            return ((name.identifier == "any" and args.is_any()) or
                    (name.identifier == "all" and args.is_all()))
        else:
            return self.is_function()

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("Incomplete Call node")
        lnode = self.operands[0]
        args = self.operands[1]
        if isinstance(lnode, QNameExpression):
            if lnode.identifier.namespace == "odata":
                return self.evaluate_odata(
                    lnode.identifier.name, args, evaluator)
            elif lnode.identifier.namespace == "geo" and \
                    self.method is not None:
                args = args.evaluate(evaluator)
                return self.evaluate_method(args, evaluator)
            else:
                # function(params)
                try:
                    f = evaluator.first_member(lnode.identifier)
                    with evaluator.new_context(f):
                        return evaluator.member_args(args)
                except errors.PathError:
                    if evaluator.context is None:
                        raise
                    # we couldn't find a bound function in the current
                    # context so try an unbound function instead.
                    with evaluator.new_context(None):
                        f = evaluator.first_member(lnode.identifier)
                        with evaluator.new_context(f):
                            return evaluator.member_args(args)
        elif isinstance(lnode, IdentifierExpression):
            # any and all cannot appear standalone
            if ((lnode.identifier == "any" and args.is_any()) or
                    (lnode.identifier == "all" and args.is_all())):
                raise errors.ExpressionError("any and all outside path")
            if lnode.identifier in ("cast", "isof"):
                type_arg, expr_arg = args.get_type_args()
                if type_arg is not None:
                    if expr_arg is not None:
                        expr_arg = expr_arg.evaluate(evaluator)
                    if lnode.identifier == "cast":
                        return evaluator.cast(type_arg.identifier, expr_arg)
                    else:
                        return evaluator.isof(type_arg.identifier, expr_arg)
            # ambiguity between entity_collection(key) and method()
            if args.is_key_predicate():
                try:
                    collection = evaluator.first_member(lnode.identifier)
                    with evaluator.new_context(collection):
                        return evaluator.member_args(args)
                except errors.PathError:
                    pass
            # guess we're a method call then
            return self.evaluate_method(args.evaluate(evaluator), evaluator)
        elif isinstance(lnode, CallExpression):
            # must be function(params)(key)
            collection = evaluator.evaluate(lnode)
            with evaluator.new_context(collection):
                return evaluator.member_args(args)
        else:
            raise errors.ExpressionError("%r in CallExpression" % lnode)

    def evaluate_method(self, args, evaluator):
        if len(args) == 0:
            if self.method == Method.mindatetime:
                return evaluator.mindatetime()
            elif self.method == Method.maxdatetime:
                return evaluator.maxdatetime()
            elif self.method == Method.now:
                return evaluator.now()
        elif len(args) == 1:
            if self.method == Method.length:
                return evaluator.length(*args)
            elif self.method == Method.tolower:
                return evaluator.tolower(*args)
            elif self.method == Method.toupper:
                return evaluator.toupper(*args)
            elif self.method == Method.trim:
                return evaluator.trim(*args)
            elif self.method == Method.year:
                return evaluator.year(*args)
            elif self.method == Method.month:
                return evaluator.month(*args)
            elif self.method == Method.day:
                return evaluator.day(*args)
            elif self.method == Method.hour:
                return evaluator.hour(*args)
            elif self.method == Method.minute:
                return evaluator.minute(*args)
            elif self.method == Method.second:
                return evaluator.second(*args)
            elif self.method == Method.fractionalseconds:
                return evaluator.fractionalseconds(*args)
            elif self.method == Method.totalseconds:
                return evaluator.totalseconds(*args)
            elif self.method == Method.date:
                return evaluator.date_method(*args)
            elif self.method == Method.time:
                return evaluator.time(*args)
            elif self.method == Method.totaloffsetminutes:
                return evaluator.totaloffsetminutes(*args)
            elif self.method == Method.round:
                return evaluator.round(*args)
            elif self.method == Method.floor:
                return evaluator.floor(*args)
            elif self.method == Method.ceiling:
                return evaluator.ceiling(*args)
            elif self.method == Method.geo_length:
                return evaluator.geo_length(*args)
        elif len(args) == 2:
            if self.method == Method.contains:
                return evaluator.contains(*args)
            elif self.method == Method.startswith:
                return evaluator.startswith(*args)
            elif self.method == Method.endswith:
                return evaluator.endswith(*args)
            elif self.method == Method.indexof:
                return evaluator.indexof(*args)
            elif self.method == Method.concat:
                return evaluator.concat(*args)
            elif self.method == Method.geo_distance:
                return evaluator.geo_distance(*args)
            elif self.method == Method.geo_intersects:
                return evaluator.geo_intersects(*args)
            elif self.method == Method.substring:
                return evaluator.substring(*args)
        elif len(args) == 3:
            if self.method == Method.substring:
                return evaluator.substring(*args)
        if self.method is None:
            raise errors.ExpressionError(
                "bad method %s" % self.operands[0].identifier)
        else:
            raise errors.ExpressionError(
                "argument list incompatible with %s" %
                Method.to_str(self.method))

    def evaluate_odata(self, name, args, evaluator):
        if name == "concat":
            # must be at least 2 arguments
            if len(args.operands) < 2:
                raise errors.ExpressionError(
                    "odata.concat requires two or more arguments")
            return evaluator.odata_concat(args.evaluate(evaluator))
        elif name == "fillUriTemplate":
            # must be at least 1 argument
            if not len(args.operands):
                raise errors.ExpressionError(
                    "odata.fillUriTemplate requires at least one argument")
            # first argument is template
            template = args.operands[0].evaluate(evaluator)
            # now the remainder should be values with assigned names
            return evaluator.odata_fill_uri_template(
                template, args.operands[1:])
        elif name == "uriEncode":
            # must be exactly 1 argument
            if not len(args.operands) == 1:
                raise errors.ExpressionError(
                    "odata.uriEncode requires exactly one argument")
            return evaluator.odata_uri_encode(
                args.operands[0].evaluate(evaluator))
        elif name == "cast" or name == "isof":
            if len(args.operands) != 2:
                raise errors.ExpressionError(
                    "odata.%s requires two arguments" % name)
            value = args.operands[0].evaluate(evaluator)
            type_arg = args.operands[1]
            if not isinstance(type_arg, TypeExpression):
                raise errors.ExpressionError(
                    "odata.%s(expression, type) expected type instance, "
                    "not %s" % (name, repr(type_arg)))
            if name == "cast":
                return evaluator.cast_type(
                    type_arg.type_def, value)
            else:
                return evaluator.isof_type(
                    type_arg.type_def, value)
        else:
            raise errors.ExpressionError(
                "Unknown client-side function odata.%s" % name)

    def evaluate_path_node(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("Incomplete Call node")
        lnode = self.operands[0]
        args = self.operands[1]
        if isinstance(lnode, QNameExpression):
            # ambiguity between type_cast(key) and function(params)
            set_or_f = evaluator.member(lnode.identifier)
            with evaluator.new_context(set_or_f):
                return evaluator.member_args(args)
        elif isinstance(lnode, IdentifierExpression):
            if lnode.identifier == "any" and args.is_any():
                return evaluator.member_any(*args.get_lambda_args())
            elif lnode.identifier == "all" and args.is_all():
                return evaluator.member_all(*args.get_lambda_args())
            else:
                # no ambiguity must be entity_collection(key)
                collection = evaluator.member(lnode.identifier)
                with evaluator.new_context(collection):
                    return evaluator.member_args(args)
        elif isinstance(lnode, CallExpression):
            # must be function(params)(key)
            collection = lnode.evaluate_path_node(evaluator)
            with evaluator.new_context(collection):
                return evaluator.member_args(args)
        else:
            raise errors.ExpressionError("%r in CallExpression" % lnode)


class ArgsExpression(OperatorExpression):

    """Class representing an argument list

    Used for function calls, key predicates and the any/all constructs.

    This may sound strange but the syntax is overlapping and we can't
    tell if Products(3) is the entity with key 3 in the navigation
    property "Products" or a method call of a method called Products.  As
    a result, it is possible to name navigation properties in such a way
    as to hide single-valued methods like year, month, length, etc.
    When evaluating a CallExpression containing a single
    primitiveLiteral argument"""

    def __init__(self):
        OperatorExpression.__init__(self, Operator.args)

    def is_key_predicate(self):
        """Returns True if these arguments match keyPredicate"""
        if len(self.operands) > 1:
            skip_id = False
        elif len(self.operands) == 1:
            skip_id = True
        else:
            return False    # keyPredicate requires at least one param
        for op in self.operands:
            if skip_id and isinstance(op, LiteralExpression):
                return True
            if isinstance(op, BindExpression):
                rop = op.operands[0]
                if not isinstance(rop, LiteralExpression):
                    return False
            else:
                return False
        return True

    def is_function_parameters(self):
        """Returns True if parameters match functionExprParameters"""
        for op in self.operands:
            if not op.is_function_parameter():
                return False
        return True

    def is_method_parameters(self):
        """Returns True if parameters are all commonExpr"""
        for op in self.operands:
            if not op.is_common():
                return False
        return True

    def is_any(self):
        """Returns True if our arguments match anyExpr"""
        if len(self.operands) > 1:
            return False
        elif self.operands:
            return (isinstance(self.operands[0], LambdaBindExpression) and
                    len(self.operands[0].operands) == 1 and
                    self.operands[0].operands[0].is_bool_common())
        else:
            # any() is valid syntax
            return True

    def is_all(self):
        """Returns True if our arguments match allExpr"""
        if len(self.operands) > 1:
            return False
        elif self.operands:
            return (isinstance(self.operands[0], LambdaBindExpression) and
                    len(self.operands[0].operands) == 1 and
                    self.operands[0].operands[0].is_bool_common())
        else:
            # all() is *not* valid syntax
            return False

    def get_type_args(self):
        if len(self.operands) == 1:
            expr_arg = None
            type_arg = self.operands[0]
        elif len(self.operands) == 2:
            expr_arg, type_arg = self.operands
        else:
            expr_arg, type_arg = None, None
        return type_arg, expr_arg

    def is_type_args(self):
        """Returns True if our arguments match isof or cast args"""
        type_arg, expr_arg = self.get_type_args()
        if expr_arg is not None and not expr_arg.is_common():
            return False
        return isinstance(type_arg, QNameExpression)

    def get_lambda_args(self):
        if self.operands:
            e = self.operands[0]
            return e.name, e.operands[0]
        else:
            return None, None

    def evaluate(self, evaluator):
        """Evaluates each argument in turn"""
        result = []
        for op in self.operands:
            result.append(op.evaluate(evaluator))
        return result


class BindExpression(BindBaseExpression):

    def __init__(self):
        OperatorExpression.__init__(self, Operator.bind)
        self.name = None

    def is_function_parameter(self):
        return self.name and (
            len(self.operands) == 1 and self.operands[0].is_common())

    def evaluate(self, evaluator):
        if len(self.operands) != 1:
            raise errors.ExpressionError("incomplete bind")
        result = self.operands[0].evaluate(evaluator)
        return evaluator.bind(self.name, result)


class LambdaBindExpression(BindBaseExpression):

    def __init__(self):
        OperatorExpression.__init__(self, Operator.lambda_bind)
        self.name = None

    def evaluate(self, evaluator):
        raise errors.ExpressionError("lambda expression out of context")


class BoolBaseExpression(BinaryExpression):

    def is_common(self):
        return len(self.operands) == 2

    def is_bool_common(self):
        return len(self.operands) == 2


class LogicalBaseExpression(BoolBaseExpression):

    def add_operand(self, operand):
        if not operand.is_bool_common():
            raise ValueError(
                "%r in %s" % (operand, Operator.to_str(self.op_code)))
        super(LogicalBaseExpression, self).add_operand(operand)


class AndExpression(LogicalBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.bool_and)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete and")
        return evaluator.bool_and(
            *(op.evaluate(evaluator) for op in self.operands))


class OrExpression(LogicalBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.bool_or)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete or")
        return evaluator.bool_or(
            *(op.evaluate(evaluator) for op in self.operands))


class EqExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.eq)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete eq")
        return evaluator.eq(
            *(op.evaluate(evaluator) for op in self.operands))


class NeExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.ne)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete ne")
        return evaluator.ne(
            *(op.evaluate(evaluator) for op in self.operands))


class LtExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.lt)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete lt")
        return evaluator.lt(
            *(op.evaluate(evaluator) for op in self.operands))


class LeExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.le)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete le")
        return evaluator.le(
            *(op.evaluate(evaluator) for op in self.operands))


class GtExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.gt)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete gt")
        return evaluator.gt(
            *(op.evaluate(evaluator) for op in self.operands))


class GeExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.ge)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete ge")
        return evaluator.ge(
            *(op.evaluate(evaluator) for op in self.operands))


class HasExpression(BoolBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.has)

    def add_operand(self, operand):
        if len(self.operands) == 1 and not isinstance(operand, EnumExpression):
            raise ValueError(
                "has operator requires enum not %r" % operand)
        super(HasExpression, self).add_operand(operand)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete has")
        return evaluator.has(
            *(op.evaluate(evaluator) for op in self.operands))


class AddExpression(BinaryExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.add)

    def is_common(self):
        return len(self.operands) == 2

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete add")
        return evaluator.add(
            *(op.evaluate(evaluator) for op in self.operands))


class SubExpression(BinaryExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.sub)

    def is_common(self):
        return len(self.operands) == 2

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete sub")
        return evaluator.sub(
            *(op.evaluate(evaluator) for op in self.operands))


class MulExpression(BinaryExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.mul)

    def is_common(self):
        return len(self.operands) == 2

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete mul")
        return evaluator.mul(
            *(op.evaluate(evaluator) for op in self.operands))


class DivExpression(BinaryExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.div)

    def is_common(self):
        return len(self.operands) == 2

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete div")
        return evaluator.div(
            *(op.evaluate(evaluator) for op in self.operands))


class ModExpression(BinaryExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.mod)

    def is_common(self):
        return len(self.operands) == 2

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete mod")
        return evaluator.mod(
            *(op.evaluate(evaluator) for op in self.operands))


class UnaryExpression(OperatorExpression):

    """Class representing unary operator expression"""

    def add_operand(self, operand):
        if len(self.operands):
            raise ValueError("unary operator already bound")
        super(UnaryExpression, self).add_operand(operand)


class NotExpression(UnaryExpression):

    def __init__(self):
        UnaryExpression.__init__(self, Operator.bool_not)

    def add_operand(self, operand):
        if not operand.is_bool_common():
            raise ValueError("%r in not" % operand)
        super(NotExpression, self).add_operand(operand)

    def is_common(self):
        return len(self.operands) == 1

    def is_bool_common(self):
        return len(self.operands) == 1

    def evaluate(self, evaluator):
        if len(self.operands) != 1:
            raise errors.ExpressionError("incomplete not")
        return evaluator.bool_not(self.operands[0].evaluate(evaluator))


class NegateExpression(UnaryExpression):

    def __init__(self):
        UnaryExpression.__init__(self, Operator.negate)

    def add_operand(self, operand):
        if not operand.is_common():
            raise ValueError("%r in negate expression" % operand)
        super(NegateExpression, self).add_operand(operand)

    def is_common(self):
        return len(self.operands) == 1

    def evaluate(self, evaluator):
        if len(self.operands) != 1:
            raise errors.ExpressionError("incomplete negate")
        return evaluator.negate(self.operands[0].evaluate(evaluator))


class ReferenceExpression(QNameExpression):

    """Class representing a reference to a labeled expression"""

    def is_common(self):
        return True

    def is_bool_common(self):
        return True

    def evaluate(self, evaluator):
        return evaluator.reference(self.identifier)


class TypeExpression(CommonExpression):

    """Class representing a Type in an expression

    Used only in the odata.cast and odata.isof methods used internally
    to represent the use of <Edm.Cast> and <Edm.IsOf> annotation
    expressions respectively."""

    def __init__(self, type_def):
        self.type_def = type_def


class IfExpression(OperatorExpression):

    """Class representing the <If> annotationexpression

    Not used in inline syntax."""

    def __init__(self):
        OperatorExpression.__init__(self, Operator.bool_test)

    def add_operand(self, operand):
        if not self.operands:
            # First expression must be bool
            if not operand.is_bool_common():
                raise ValueError("%r cannot be test in <If> expression" %
                                 operand)
        elif len(self.operands) < 3:
            # Subsequent expressions must be common
            if not operand.is_common():
                raise ValueError(
                    "<If> expression requires common result, not %r" % operand)
        else:
            raise ValueError(
                "<If> expression requires 2 or 3 arguments")
        super(IfExpression, self).add_operand(operand)

    def is_common(self):
        return len(self.operands) == 3

    def is_bool_common(self):
        if len(self.operands) == 3:
            for op in self.operands[1:3]:
                if not op.is_bool_common():
                    return False
            return True
        else:
            return False

    def evaluate(self, evaluator):
        items = [i.evaluate(evaluator) for i in self.operands]
        if len(items) in (2, 3):
            return evaluator.bool_test(*items)
        else:
            raise errors.ExpressionError(
                "<If> requires 3 or 2 child elements")


class PathExpression(CommonExpression):

    """An expression that evaluates a path

    We actually store the expression's value as a tuple (as per the
    return value of :func:`path_expr_from_str`) but when evaluated a
    path expression is evaluated in the current context by path
    traversal in a similar way to MemberExpression.

    Path expressions are not used in inline URL expressions and should
    not be confused with the member operator '/' which is used within
    rootExpr and firstMemberExpr for inline paths.

    Path expressions are actually defined for use in annotation
    expressions and don't support use of key predicates in collection
    paths; instead they allow you to define collections 'on the fly'
    through paths like Products/Name creating a collection of Names
    created by taking the Name of each Product in a collection of
    Products.

    Path expressions also support the looking up of navigation property
    annotations using the TargetedTermRef syntax."""

    def __init__(self, path):
        self.path = path

    def is_common(self):
        return True

    def is_bool_common(self):
        return True

    def evaluate(self, evaluator):
        return evaluator.path_expr(self.path)


class AnnotationPathExpression(PathExpression):

    """An expression that evaluates to an AnnotationPath

    Not used in inline syntax where paths are decomposed and evaluated
    using the notional member operator.  The :attr:`path` attribute set
    on creation must be compatible with the return value of
    :func:`annotation_path_from_str`."""

    def is_bool_common(self):
        return False

    def evaluate(self, evaluator):
        return evaluator.annotation_path(self.path)


class NavigationPropertyPathExpression(PathExpression):

    """An expression that evaluates to a NavigationPropertyPath."""

    def is_bool_common(self):
        return False

    def evaluate(self, evaluator):
        return evaluator.navigation_path(self.path)


class PropertyPathExpression(PathExpression):

    """An expression that evaluates to a PropertyPath."""

    def is_bool_common(self):
        return False

    def evaluate(self, evaluator):
        return evaluator.property_path(self.path)


class WordExpression(CommonExpression):

    """Class representing a search word in an expression

    Only used in search expressions, not valid in common expressions."""

    def __init__(self, word):
        self.word = word

    def is_search(self):
        return True

    def evaluate(self, evaluator):
        return evaluator.word(self.word)


class PhraseExpression(CommonExpression):

    """Class representing a search phrase in an expression

    Only used in search expressions, not valid in common expressions."""

    def __init__(self, phrase):
        self.phrase = phrase

    def is_search(self):
        return True

    def evaluate(self, evaluator):
        return evaluator.word(self.word)


class SearchBaseExpression(BinaryExpression):

    def add_operand(self, operand):
        if not operand.is_search():
            raise ValueError(
                "%r in %s" % (operand, Operator.to_str(self.op_code)))
        super(SearchBaseExpression, self).add_operand(operand)

    def is_search(self):
        return len(self.operands) == 2


class SearchAndExpression(SearchBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.bool_and)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete AND")
        return evaluator.bool_and(
            *(op.evaluate(evaluator) for op in self.operands))


class SearchOrExpression(SearchBaseExpression):

    def __init__(self):
        BinaryExpression.__init__(self, Operator.bool_or)

    def evaluate(self, evaluator):
        if len(self.operands) != 2:
            raise errors.ExpressionError("incomplete OR")
        return evaluator.bool_or(
            *(op.evaluate(evaluator) for op in self.operands))


class SearchNotExpression(UnaryExpression):

    def __init__(self):
        UnaryExpression.__init__(self, Operator.bool_not)

    def add_operand(self, operand):
        if not operand.is_search():
            raise ValueError("%r in NOT" % operand)
        super(SearchNotExpression, self).add_operand(operand)

    def is_search(self):
        return len(self.operands) == 1

    def evaluate(self, evaluator):
        if len(self.operands) != 1:
            raise errors.ExpressionError("incomplete NOT")
        return evaluator.bool_not(self.operands[0].evaluate(evaluator))


class ExpressionProcessor(object):

    """An abstract class used to process expressions

    The processing of expressions involves traversing the expression
    tree to obtain an evaluated result.  The evaluator works by calling
    the basic expression objects which then call the appropriate method
    in this object to transform or compose any input arguments into a
    result.

    The most obvious implementation is the :class:`evaluator.Evaluator`
    class that results in a :class:`data.Value` object but this
    technique allows alternative evaluators that return something other
    than Value objects with their own implementations of the methods in
    this class to provide an alternative result from the same
    expression: for example, to return a string representation of the
    expression as in the :class:`ExpressionFormatter` class defined by
    this module.  The technique can be extended to build a query that
    represents the expression suitable for accessing some other data
    storage system (like SQL).

    Expressions in OData are very general and can touch all of the
    concepts within the model.  Some expressions contain qualified names
    that must be looked up in a specific EntityModel.  A notable example
    is the way enumeration constants are represented in OData.  The
    model argument is used to set the entity model in which look-ups are
    made.  If it is None then it may be inferred from the implicit
    variable, if it cannot be inferred all look-ups will fail.

    The special value $it, used in inline expressions, represents the
    implicit variable for the processing and is usually obtained from
    the resource path of the OData URL.  For an evaluator, this is
    typically the Value object the resource path refers to or, if the
    Value is a collection, the current item within the collection being
    inspected.  We generalise this concept to allow elements in the
    metadata model to be '$it' too (with a more limited set of valid
    expression types) so that the same evaluation process can be used
    for expressions declared in the metadata model (in applied
    Annotations).

    The implicit variable defines an evaluation context that is used for
    looking up member names.  The evaluation context may be changed
    during evaluation (e.g., when traversing paths in expressions) but
    the implicit variable ($it) is fixed and always evaluates to the
    value passed.

    For completeness, we allow the special case where $it is null (or
    omitted) to allow constant expressions to be evaluated."""

    def __init__(self, it=None, model=None):
        self.params = {}
        #: the implicit context for evaluation (from the resource path)
        self.it = it
        #: the current context for evaluation, may be altered during
        #: processing using the context manager :meth:`new_context`.
        self.context = it
        self._context_stack = []
        self._lambda_stack = []
        self.binding = []
        self.em = model

    def declare_param(self, name, expression):
        """Declares a named parameter

        name
            An odataIdentifier with the name of the parameter (not
            including the '@' prefix.

        expression
            A common expression to be evaluated in place of references
            to this parameter.

        Named parameters are introduced using @name notation in the URL
        query itself (in this case, the @ does not refer to an
        annotation).

        They define sub-expressions that are evaluated when the
        parameter is referred to (and hence can be reused).

        Undeclared parameters are treated as null.  You can't undeclare
        a parameter (use a new expression processor if you need to) but
        you can achieve a similar effect using the NullExpression as
        redeclaring a parameter will replace the existing declaration::

            e.declare_param("param", NullExpression())"""
        self.params[name] = expression

    @contextlib.contextmanager
    def new_context(self, context):
        self._context_stack.append(self.context)
        self.context = context
        try:
            yield self
        finally:
            self.context = self._context_stack.pop()

    @contextlib.contextmanager
    def set_lambda_context(self, name, context):
        self._lambda_stack.append((name, context))
        # remove the context as it isn't clear what the context would be
        # in a lambda expression: e.g., Friends/any(f:f/Name eq Name)
        # Name of what?
        self._context_stack.append(self.context)
        self.context = None
        try:
            yield self
        finally:
            self.context = self._context_stack.pop()
            self._lambda_stack.pop()

    def get_lambda_context(self, name):
        context = None
        for lname, lcontext in self._lambda_stack:
            if lname == name:
                context = lcontext
        return context

    def evaluate(self, expression):
        """Evaluates a common expression

        The method triggers the processing of the expression tree,
        recursively processing all nodes and returning the result
        of processing the top node (the expresison object itself).

        The type of the result is not constrained by this class, the
        default :class:`Evaluator` class results in a
        :class:`data.Value` instance.

        The evaluation of an expression may raise an expression error if
        the expression can't be evaluated."""
        return expression.evaluate(self)

    def null(self):
        """Evaluates null"""
        raise NotImplementedError("%s.null" % self.__class__.__name__)

    def boolean(self, value):
        """Evaluates a boolean value

        value
            One of the Python constants True or False."""
        raise NotImplementedError("%s.boolean" % self.__class__.__name__)

    def guid(self, value):
        """Evaluates a guid value

        value
            A Python UUID instance."""
        raise NotImplementedError("%s.guid" % self.__class__.__name__)

    def date(self, value):
        """Evaluates a date value

        value
            A :class:`pyslet.iso8601.Date` instance."""
        raise NotImplementedError("%s.date" % self.__class__.__name__)

    def date_time_offset(self, value, literal):
        """Evaluates a dateTimeOffset value

        value
            A :class:`pyslet.iso8601.TimePoint` instance.

        literal
            The formatted value."""
        raise NotImplementedError(
            "%s.date_time_offset" % self.__class__.__name__)

    def time_of_day(self, value, literal):
        """Evaluates a timeOfDay value

        value
            A :class:`pyslet.iso8601.Time` instance.

        literal
            The formatted value."""
        raise NotImplementedError(
            "%s.time_of_day" % self.__class__.__name__)

    def decimal(self, value):
        """Evaluates a decimal value

        value
            A Python Decimal instance."""
        raise NotImplementedError(
            "%s.decimal" % self.__class__.__name__)

    def double(self, value):
        """Evaluates a double literal

        value
            A Python float *or* Decimal value"""
        raise NotImplementedError(
            "%s.double" % self.__class__.__name__)

    def int64(self, value):
        """Evaluates an int64 value

        value
            A Python int (or Python 2 long)."""
        raise NotImplementedError(
            "%s.int64" % self.__class__.__name__)

    def string(self, value):
        """Evaluates a string value

        value
            A Python str (or Python 2 unicode)."""
        raise NotImplementedError(
            "%s.string" % self.__class__.__name__)

    def duration(self, value, literal):
        """Evaluates a duration value

        value
            A :class:`pyslet.xml.xsdatatypes.Duration` instance.

        literal
            The formatted value."""
        raise NotImplementedError(
            "%s.duration" % self.__class__.__name__)

    def binary(self, value):
        """Evaluates a binary (data) value

        value
            A Python bytes object (or Python 2 str)."""
        raise NotImplementedError(
            "%s.binary" % self.__class__.__name__)

    def enum(self, value):
        """Evaluates an enum value

        value
            A :class:`names.EnumLiteral` instance."""
        raise NotImplementedError(
            "%s.enum" % self.__class__.__name__)

    def geography(self, value, literal):
        """Evaluates a geography value

        value
            An instance of one of the geotype literal objects.

        literal
            The formatted value."""
        raise NotImplementedError(
            "%s.geography" % self.__class__.__name__)

    def geometry(self, value, literal):
        """Evaluates a geometry value

        value
            An instance of one of the geotype literal objects.

        literal
            The formatted value."""
        raise NotImplementedError(
            "%s.geometry" % self.__class__.__name__)

    def parameter(self, name):
        """Evaluates a named parameter

        name
            Always the name of the parameter

        We provide a default implementation which looks up the named
        parameter and evaluates the resulting expression in its place
        in an empty context."""
        expr = self.params.get(name, None)
        if expr is None:
            return self.evaluate(NullExpression())
        else:
            with self.new_context(None):
                return self.evaluate(expr)

    def root(self):
        """Evaluates $root"""
        raise NotImplementedError(
            "%s.root" % self.__class__.__name__)

    def implicit_variable(self):
        """Evaluates $it"""
        raise NotImplementedError(
            "%s.implicit_variable" % self.__class__.__name__)

    def lambda_variable(self, name):
        """Evaluates an inscope variable

        A default implementation is provided returning the context value
        pushed as the value of the lambda variable with *name*.  See
        :meth:`push_lambda_variable` for more information."""
        result = None
        for lname, lcontext in self.lambda_stack:
            if lname == name:
                result = lcontext
        return result

    def collection(self, expr_list):
        """Evaluates the collection operator

        expr_list
            A list of expressions to evaluate to yield the items in the
            collection.  The list is passed prior to evaluation for two
            reasons: (i) to handle the special case of the <If>
            expression indicating that that item should be skipped and
            (ii) to enable literals to be handled according to the JSON
            rules when formatting."""
        raise NotImplementedError(
            "%s.collection" % self.__class__.__name__)

    def record(self, expr_list):
        """Evaluates the record operator

        expr_list
            A list of tuples consisting of (name, expr) where name is
            the name being bound in the record (as a string) and expr is
            the unevaluated expression to bind to it.  The evaluation is
            deferred primarily to enable literals to be handled
            according to the JSON rules when formatting."""
        raise NotImplementedError(
            "%s.record" % self.__class__.__name__)

    def first_member(self, segment):
        """Evaluates the first member operator

        segment
            An identifier or QualifiedName containing the first part of
            a path.

        A default implementation is provided that will look up lambda
        variables (returning the lambda context object).

        For other types of segment it simply calls :meth:`member`.  For
        information about exception paths see the description there."""
        if is_text(segment):
            context = self.get_lambda_context(segment)
            if context is not None:
                # lambda variables override everything
                return context
        return self.member(segment)

    def member(self, segment):
        """Evaluates the member operator

        segment
            An identifier or QualifiedName containing the next part of
            the path.

        The return value is the next context for evaluation.

        If the segment is an identifier and there is property defined in
        the current context *and the current context does not support
        dynamic properties* then a PathError is raised as the expression
        is considered malformed.

        If the context is null then valid property names are resolved to
        null values of the appropriate property type.  This creates some
        awkward cases.  A dynamic property has an unknown type and so
        cannot be resolved any further, similarly, collections are never
        null, they can only be empty.  In these cases, a NullPath error
        is raised as processing of any additional path segments is not
        possible and the specification indicates that the path as a
        whole evaluates to null."""
        raise NotImplementedError(
            "%s.member" % self.__class__.__name__)

    def member_args(self, args):
        """Evaluates function call and key resolution

        context
            The result of evaluating the path up to this member operator.

        args
            An :class:`ArgsExpression` instance containing the arguments
            to be applied.

        This method is used in all situations where arguments apply
        within a path, so the arguments could describe a key-predicate
        (when context is a collection) or the parameters to a bound
        function."""
        raise NotImplementedError(
            "%s.member_args" % self.__class__.__name__)

    def member_count(self):
        """Evaluates $count

        context
            The result of evaluating the path up to this point."""
        raise NotImplementedError(
            "%s.member_count" % self.__class__.__name__)

    def member_any(self, lambda_name=None, lambda_expression=None):
        """Evaluates any()

        context
            The result of evaluating the path up to this point.

        lambda_name
            The name of the lambda variable or None if there is
            no lambda expression.

        lambda_expression
            An unevaluated lambda expression that may contain the lambda
            variable."""
        raise NotImplementedError(
            "%s.member_any" % self.__class__.__name__)

    def member_all(self, lambda_name, lambda_expression):
        """Evaluates all()

        context
            The result of evaluating the path up to this point."""
        raise NotImplementedError(
            "%s.member_all" % self.__class__.__name__)

    @contextlib.contextmanager
    def new_scope(self):
        """A context manager that defines a new scope

        During evaluation, scopes are used when assignment expressions
        are expected, for example, when processing key predicates or
        call-type expressions that take named arguments rather than
        positional arguments.

        The return value is the dictionary in which the results of any
        bind operations (see: :meth:`bind`) are declared.  E.g.::

            with evaluator.new_scope() as scope:
                # evaluate assignment expressions, e.g., a=1
            # scope can now be used, e.g., scope['a'] would be an
            # Int64Value instance with value 1 after evaluation in the
            # above example."""
        self.scope_stack.append(self.scope)
        self.scope = {}
        try:
            yield self.scope
        finally:
            self.scope = self.scope_stack.pop()

    def bind(self, name, result):
        """Binds a result to a name

        Used in situations where param=value is evaluated explicitly,
        such as function parameters and keyPredicates.

        Unusually, a default implementation is provided that simply
        returns a tuple of (name, result) as this method is only used
        indirectly by member_args and by odata_fill_uri_template."""
        return name, result

    def mindatetime(self):
        """Evaluates mindatetime()"""
        raise NotImplementedError(
            "%s.mindatetime" % self.__class__.__name__)

    def maxdatetime(self):
        """Evaluates maxdatetime()"""
        raise NotImplementedError(
            "%s.maxdatetime" % self.__class__.__name__)

    def now(self):
        """Evaluates now()"""
        raise NotImplementedError(
            "%s.now" % self.__class__.__name__)

    def length(self, value):
        """Evaluates length(value): the length of a value"""
        raise NotImplementedError(
            "%s.length" % self.__class__.__name__)

    def tolower(self, value):
        """Evaluates tolower(value): the lower cased value"""
        raise NotImplementedError(
            "%s.tolower" % self.__class__.__name__)

    def toupper(self, value):
        """Evaluates toupper(value): the upper cased value"""
        raise NotImplementedError(
            "%s.toupper" % self.__class__.__name__)

    def trim(self, value):
        """Evaluates trim(value): the trimmed value"""
        raise NotImplementedError(
            "%s.trim" % self.__class__.__name__)

    def year(self, value):
        """Evaluates year(value): the year part of value"""
        raise NotImplementedError(
            "%s.year" % self.__class__.__name__)

    def month(self, value):
        """Evaluates month(value): the month part of value"""
        raise NotImplementedError(
            "%s.month" % self.__class__.__name__)

    def day(self, value):
        """Evaluates day(value): the day part of value"""
        raise NotImplementedError(
            "%s.day" % self.__class__.__name__)

    def hour(self, value):
        """Evaluates hour(value): the hour part of value"""
        raise NotImplementedError(
            "%s.hour" % self.__class__.__name__)

    def minute(self, value):
        """Evaluates minute(value): the minute part of value"""
        raise NotImplementedError(
            "%s.minute" % self.__class__.__name__)

    def second(self, value):
        """Evaluates second(value): the second part of value"""
        raise NotImplementedError(
            "%s.second" % self.__class__.__name__)

    def fractionalseconds(self, value):
        """Evaluates fractionalseconds(value)

        The fractionalseconds part of value"""
        raise NotImplementedError(
            "%s.fractionalseconds" % self.__class__.__name__)

    def totalseconds(self, value):
        """Evaluates totalseconds(value)

        The totalseconds represented by value"""
        raise NotImplementedError(
            "%s.totalseconds" % self.__class__.__name__)

    def date_method(self, value):
        """Evaluates date(value): the date part of value"""
        raise NotImplementedError(
            "%s.date_method" % self.__class__.__name__)

    def time(self, value):
        """Evaluates time(value): the time part of value"""
        raise NotImplementedError(
            "%s.time" % self.__class__.__name__)

    def totaloffsetminutes(self, value):
        """Evaluates totaloffsetminutes(value)"""
        raise NotImplementedError(
            "%s.totaloffsetminutes" % self.__class__.__name__)

    def round(self, value):
        """Evaluates round(value)"""
        raise NotImplementedError(
            "%s.round" % self.__class__.__name__)

    def floor(self, value):
        """Evaluates floor(value)"""
        raise NotImplementedError(
            "%s.floor" % self.__class__.__name__)

    def ceiling(self, value):
        """Evaluates ceiling(value)"""
        raise NotImplementedError(
            "%s.ceiling" % self.__class__.__name__)

    def geo_length(self, value):
        """Evaluates geo.length(value)"""
        raise NotImplementedError(
            "%s.geo_length" % self.__class__.__name__)

    def contains(self, a, b):
        """Evaluates contains(a, b)"""
        raise NotImplementedError(
            "%s.contains" % self.__class__.__name__)

    def startswith(self, a, b):
        """Evaluates startswith(a, b)"""
        raise NotImplementedError(
            "%s.startswith" % self.__class__.__name__)

    def endswith(self, a, b):
        """Evaluates endswith(a, b)"""
        raise NotImplementedError(
            "%s.endswith" % self.__class__.__name__)

    def indexof(self, a, b):
        """Evaluates indexof(a, b)"""
        raise NotImplementedError(
            "%s.indexof" % self.__class__.__name__)

    def concat(self, a, b):
        """Evaluates concat(a, b)"""
        raise NotImplementedError(
            "%s.concat" % self.__class__.__name__)

    def geo_distance(self, a, b):
        """Evaluates geo.distance(a, b)"""
        raise NotImplementedError(
            "%s.geo_distance" % self.__class__.__name__)

    def geo_intersects(self, a, b):
        """Evaluates geo.intersects(a, b)"""
        raise NotImplementedError(
            "%s.geo_intersects" % self.__class__.__name__)

    def substring(self, a, b, c=None):
        """Evaluates substring(a, b[, c])"""
        raise NotImplementedError(
            "%s.substring" % self.__class__.__name__)

    def bool_and(self, a, b):
        """Evaluates boolean AND of two previously obtained results"""
        raise NotImplementedError(
            "%s.bool_and" % self.__class__.__name__)

    def bool_or(self, a, b):
        """Evaluates boolean OR of two previously obtained results"""
        raise NotImplementedError(
            "%s.bool_or" % self.__class__.__name__)

    def bool_not(self, op):
        """Evaluates boolean NOT of a previously obtained result"""
        raise NotImplementedError(
            "%s.bool_not" % self.__class__.__name__)

    def eq(self, a, b):
        """Evaluates the equality of two previously obtained results"""
        raise NotImplementedError(
            "%s.eq" % self.__class__.__name__)

    def ne(self, a, b):
        """Evaluates the not-equal operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.ne" % self.__class__.__name__)

    def gt(self, a, b):
        """Evaluates the greater-than operator for two previously
        obtained results"""
        raise NotImplementedError(
            "%s.gt" % self.__class__.__name__)

    def ge(self, a, b):
        """Evaluates the greater-than or equal operator for two
        previously obtained results"""
        raise NotImplementedError(
            "%s.ge" % self.__class__.__name__)

    def lt(self, a, b):
        """Evaluates the less-than operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.lt" % self.__class__.__name__)

    def le(self, a, b):
        """Evaluates the less-than or equal operator for two
        previously obtained results"""
        raise NotImplementedError(
            "%s.le" % self.__class__.__name__)

    def has(self, a, b):
        """Evaluates the has operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.has" % self.__class__.__name__)

    def add(self, a, b):
        """Evaluates the add operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.add" % self.__class__.__name__)

    def sub(self, a, b):
        """Evaluates the sub operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.sub" % self.__class__.__name__)

    def mul(self, a, b):
        """Evaluates the mul operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.mul" % self.__class__.__name__)

    def div(self, a, b):
        """Evaluates the div operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.div" % self.__class__.__name__)

    def mod(self, a, b):
        """Evaluates the mod operator for two previously obtained
        results"""
        raise NotImplementedError(
            "%s.mod" % self.__class__.__name__)

    def negate(self, value):
        """Evaluates the - operator for a previously obtained
        result"""
        raise NotImplementedError(
            "%s.negate" % self.__class__.__name__)

    def cast(self, type_name, expression=None):
        """Evaluates the cast operation

        type_name
            A :class:`names.QualifiedName` instance containing the
            name of the type to cast to.

        expression (None)
            The result of evaluating the expression argument or None if
            this is the single-argument form of cast, in which case the
            result of processing $it should be used instead.

        Notice that the arguments are turned around to enable the
        expression to be optional in the python binding."""
        raise NotImplementedError(
            "%s.cast" % self.__class__.__name__)

    def cast_type(self, type_def, expression):
        """Evaluates the cast operation (post lookup)

        Similar to :meth:`cast` except used to evaluate the Cast element
        in an Annotation definition.  The expression is *required* and
        the first argument is a type instance and not a qualified name
        because the Cast element can impose additional constraints on
        the base type and so may require a cast to an unamed type
        derived from a primitive."""
        raise NotImplementedError(
            "%s.cast_type" % self.__class__.__name__)

    def isof(self, type_name, value=None):
        """Evaluates the isof operation

        type_name
            A :class:`names.QualifiedName` instance containing the
            name of the type to test.

        value (None)
            The result of evaluating the expression argument or None if
            this is the single-argument form of isof, in which case the
            result of processing $it should be used instead.

        Notice that the arguments are turned around to enable the
        expression to be optional in the python binding."""
        raise NotImplementedError(
            "%s.isof" % self.__class__.__name__)

    def isof_type(self, type_def, value):
        """Evaluates the isof operation (post lookup)

        Similar to :meth:`isof` except used to evaluate the IsOf element
        in an Annotation definition.  The value is *required* and
        the first argument is a type instance and not a qualified name
        because the IsOf element can impose additional constraints on
        the base type and so may require the test of an unamed type
        derived from a primitive."""
        raise NotImplementedError(
            "%s.isof_type" % self.__class__.__name__)

    def reference(self, qname):
        """Evaluates a labeled reference to an expression

        qname is always a :names:`QualifiedName` instance."""
        raise NotImplementedError("%s.reference" % self.__class__.__name__)

    def bool_test(self, q, a, b=None):
        """Evaluates a or b depending on boolean value q

        This operation is used in annotation expressions, introduced by
        the <If> element."""
        raise NotImplementedError(
            "%s.bool_test" % self.__class__.__name__)

    def odata_concat(self, args):
        """Evaluates the client-side odata.concat function

        Only used in the context of annotations, args is a list of the
        results of evaluating the argument expressions."""
        raise NotImplementedError(
            "%s.odata_concat" % self.__class__.__name__)

    def odata_fill_uri_template(self, template, args):
        """Evaluates the client-side odata.fileUriTemplate function

        template
            The *result* of evaluating the first argument to the
            function.

        args
            A list of *expressions* containing the remaining arguments.

        Only used in the context of annotations."""
        raise NotImplementedError(
            "%s.odata_fill_uri_template" % self.__class__.__name__)

    def odata_uri_encode(self, value):
        """Evaluates the uriEncode client-side function

        This function appears to be a bit of a misnomer.  The intent is
        to format a primitive value using the literal representation
        *ready* for URI-encoding.  It should not do any percent-encoding
        of characters not allowed in URLs.  This isn't clear from the
        description in the specification but the intended use can be
        deduced from the example given there where it is used in
        combinaion with fillUriTemplate which *does* do
        percent-encoding."""
        raise NotImplementedError(
            "%s.odata_uri_encode" % self.__class__.__name__)

    def path_expr(self, path):
        """Evaluates a path expression

        path
            Always a path tuple.

        The path is evaluated in the current context (:attr:`it`). If
        the path is not valid, for example, it contains a reference to a
        property that is not declared in the current context, then a
        :class:`errors.PathError` *must* be raised.

        The evaluation differs from the member methods used for path
        traversal in inline expressions because it follows the rules for
        traversing paths defined in the CSDL.  These rules are used in
        annotations and allow collections of entities to be traversed by
        property name (and not by key) to obtain collections of the
        corresponding property values."""
        raise NotImplementedError(
            "%s.path_expr" % self.__class__.__name__)

    def annotation_path(self, path):
        """Evaluates an annotation path

        path
            Always a path tuple returned from the function
            :func:`names.annotation_path_from_str`

        The path is evaluated in the current context (:attr:`it`) and
        may raise :class:`errors.PathError` even though the value of an
        annotation path is just the path itself."""
        raise NotImplementedError(
            "%s.annotation_path" % self.__class__.__name__)

    def navigation_path(self, path):
        """Evaluates a navigation path

        path
            Always a path tuple returned from the function
            :func:`names.navigation_path_from_str`

        The path is evaluated in the current context (:attr:`it`) and
        may raise :class:`errors.PathError` even though the value of a
        navigation path is just the path itself."""
        raise NotImplementedError(
            "%s.navigation_path" % self.__class__.__name__)

    def property_path(self, path):
        """Evaluates a property path

        path
            Always a path tuple returned from the function
            :func:`names.property_path_from_str`

        The path is evaluated in the current context (:attr:`it`) and
        may raise :class:`errors.PathError` even though the value of a
        property path is just the path itself."""
        raise NotImplementedError(
            "%s.property_path" % self.__class__.__name__)

    def word(self, value):
        """Evaluates a word expression

        value is always a string containing the word.  Only used in
        search expressions."""
        raise NotImplementedError("%s.word" % self.__class__.__name__)


class ExpressionFormatter(ExpressionProcessor):

    def null(self):
        return Operator.atom, "null"

    def boolean(self, value):
        return Operator.atom, "true" if value else "false"

    def guid(self, value):
        return Operator.atom, to_text(value).upper()

    def date(self, value):
        return Operator.atom, to_text(value)

    def date_time_offset(self, value, literal):
        return Operator.atom, literal

    def time_of_day(self, value, literal):
        return Operator.atom, literal

    def decimal(self, value):
        return Operator.atom, to_text(value)

    def double(self, value):
        if isinstance(value, float):
            if math.isnan(value):
                literal = "NaN"
            elif math.isinf(value):
                literal = "INF" if value > 0 else "-INF"
            else:
                literal = to_text(value)
        else:
            literal = to_text(value)
        return Operator.atom, literal

    def int64(self, value):
        return Operator.atom, to_text(value)

    def string(self, value):
        value = "'%s'" % value.replace("'", "''")
        return Operator.atom, value

    def duration(self, value, literal):
        return Operator.atom, "duration'%s'" % literal

    def binary(self, value):
        return Operator.atom, \
            "binary'%s'" % force_ascii(base64.b64encode(value))

    def enum(self, value):
        return Operator.atom, to_text(value)

    def geography(self, value, literal):
        return Operator.atom, "geography'%s'" % literal

    def geometry(self, value, literal):
        return Operator.atom, "geometry'%s'" % literal

    def parameter(self, name):
        return Operator.atom, "@" + name

    def root(self):
        return Operator.atom, "$root"

    def implicit_variable(self):
        return Operator.atom, "$it"

    def collection(self, expr_list):
        items = []
        for expr in expr_list:
            # we don't need to deal with <If> because we are only
            # formatting the expression so will render all items
            items.append(self._item_in_json(expr))
        return Operator.collection, "[%s]" % ",".join(items)

    def record(self, expr_list):
        items = []
        for name, expr in expr_list:
            # we don't need to deal with <If> because we are only
            # formatting the expression so will render all items
            items.append(
                "%s:%s" % (json.dumps(name), self._item_in_json(expr)))
        return Operator.record, "{%s}" % ",".join(items)

    def _item_in_json(self, expr):
        # Formats expr for a JSON expression, used by collection and
        # record
        if isinstance(expr, BooleanExpression):
            # special rules for true and false
            if expr.value:
                return 'true'
            else:
                return 'false'
        elif isinstance(expr, NullExpression):
            return 'null'
        elif isinstance(expr, (DoubleExpression, Int64Expression,
                               StringExpression)):
            return json.dumps(expr.value)
        elif isinstance(expr, DecimalExpression):
            return to_text(expr.value)
        elif isinstance(expr, LiteralExpression):
            # any other kind of literal is formatted and then JSON
            # encoded: a sort of double encoding which does create
            # an ambiguity on decoding between plain string forms
            # that happen to match primitive literal
            op, expr_str = self.evaluate(expr)
            return json.dumps(expr_str)
        elif expr.is_root():
            # these go in completely unencoded
            op, expr_str = self.evaluate(expr)
            return expr_str
        else:
            # This expression is not legal in a URL but is legal
            # in an annotation, for convenience we provide a
            # plain rendering of the expression in the JSON
            # form using angle brackets as a hint
            op, expr_str = self.evaluate(expr)
            return "<%s>" % expr_str

    def first_member(self, segment):
        return Operator.atom, to_text(segment)

    def member(self, segment):
        if self.context:
            return Operator.member, ("%s/%s" %
                                     (self.context[1], to_text(segment)))
        else:
            return Operator.atom, to_text(segment)

    def member_args(self, args):
        args = args.evaluate(self)
        return Operator.member, "%s(%s)" % (
            self.context[1], ",".join(a[1] for a in args))

    def member_count(self):
        return Operator.member, "%s/$count" % self.context[1]

    def member_any(self, lambda_name, lambda_expression):
        if lambda_name is None:
            return Operator.member, "%s/any()" % self.context[1]
        else:
            return Operator.member, "%s/any(%s:%s)" % (
                self.context[1], lambda_name,
                self.evaluate(lambda_expression)[1])

    def member_all(self, lambda_name, lambda_expression):
        return Operator.member, "%s/all(%s:%s)" % (
            self.context[1], lambda_name, self.evaluate(lambda_expression)[1])

    def bind(self, name, result):
        return Operator.bind, "%s=%s" % (name, result[1])

    def mindatetime(self):
        return Operator.call, "mindatetime()"

    def maxdatetime(self):
        return Operator.call, "maxdatetime()"

    def now(self):
        return Operator.call, "now()"

    def length(self, value):
        return Operator.call, "length(%s)" % value[1]

    def tolower(self, value):
        return Operator.call, "tolower(%s)" % value[1]

    def toupper(self, value):
        return Operator.call, "toupper(%s)" % value[1]

    def trim(self, value):
        return Operator.call, "trim(%s)" % value[1]

    def year(self, value):
        return Operator.call, "year(%s)" % value[1]

    def month(self, value):
        return Operator.call, "month(%s)" % value[1]

    def day(self, value):
        return Operator.call, "day(%s)" % value[1]

    def hour(self, value):
        return Operator.call, "hour(%s)" % value[1]

    def minute(self, value):
        return Operator.call, "minute(%s)" % value[1]

    def second(self, value):
        return Operator.call, "second(%s)" % value[1]

    def fractionalseconds(self, value):
        return Operator.call, "fractionalseconds(%s)" % value[1]

    def totalseconds(self, value):
        return Operator.call, "totalseconds(%s)" % value[1]

    def date_method(self, value):
        return Operator.call, "date(%s)" % value[1]

    def time(self, value):
        return Operator.call, "time(%s)" % value[1]

    def totaloffsetminutes(self, value):
        return Operator.call, "totaloffsetminutes(%s)" % value[1]

    def round(self, value):
        return Operator.call, "round(%s)" % value[1]

    def floor(self, value):
        return Operator.call, "floor(%s)" % value[1]

    def ceiling(self, value):
        return Operator.call, "ceiling(%s)" % value[1]

    def geo_length(self, value):
        return Operator.call, "geo.length(%s)" % value[1]

    def contains(self, a, b):
        return Operator.call, "contains(%s,%s)" % (a[1], b[1])

    def startswith(self, a, b):
        return Operator.call, "startswith(%s,%s)" % (a[1], b[1])

    def endswith(self, a, b):
        return Operator.call, "endswith(%s,%s)" % (a[1], b[1])

    def indexof(self, a, b):
        return Operator.call, "indexof(%s,%s)" % (a[1], b[1])

    def concat(self, a, b):
        return Operator.call, "concat(%s,%s)" % (a[1], b[1])

    def geo_distance(self, a, b):
        return Operator.call, "geo.distance(%s,%s)" % (a[1], b[1])

    def geo_intersects(self, a, b):
        return Operator.call, "geo.intersects(%s,%s)" % (a[1], b[1])

    def substring(self, a, b, c=None):
        if c is None:
            return Operator.call, "substring(%s,%s)" % (a[1], b[1])
        else:
            return Operator.call, "substring(%s,%s,%s)" % (a[1], b[1], c[1])

    def bool_and(self, a, b):
        """Formats a and b"""
        return OperatorExpression.binary_format(
            a, b, Operator.bool_and, "%s and %s")

    def bool_or(self, a, b):
        """Formats a or b"""
        return OperatorExpression.binary_format(
            a, b, Operator.bool_or, "%s or %s")

    def bool_not(self, a):
        """Formats not a"""
        return OperatorExpression.unary_format(a, Operator.bool_not, "not %s")

    def eq(self, a, b):
        """Formats a eq b"""
        return OperatorExpression.binary_format(
            a, b, Operator.eq, "%s eq %s")

    def ne(self, a, b):
        """Formats a ne b"""
        return OperatorExpression.binary_format(
            a, b, Operator.ne, "%s ne %s")

    def gt(self, a, b):
        """Formats a gt b"""
        return OperatorExpression.binary_format(
            a, b, Operator.gt, "%s gt %s")

    def ge(self, a, b):
        """Formats a ge b"""
        return OperatorExpression.binary_format(
            a, b, Operator.ge, "%s ge %s")

    def lt(self, a, b):
        """Formats a lt b"""
        return OperatorExpression.binary_format(
            a, b, Operator.lt, "%s lt %s")

    def le(self, a, b):
        """Formats a le b"""
        return OperatorExpression.binary_format(
            a, b, Operator.le, "%s le %s")

    def has(self, a, b):
        """Formats a has b"""
        return OperatorExpression.binary_format(
            a, b, Operator.has, "%s has %s")

    def add(self, a, b):
        """Formats a add b"""
        return OperatorExpression.binary_format(
            a, b, Operator.add, "%s add %s")

    def sub(self, a, b):
        """Formats a sub b"""
        return OperatorExpression.binary_format(
            a, b, Operator.sub, "%s sub %s")

    def mul(self, a, b):
        """Formats a mul b"""
        return OperatorExpression.binary_format(
            a, b, Operator.mul, "%s mul %s")

    def div(self, a, b):
        """Formats a div b"""
        return OperatorExpression.binary_format(
            a, b, Operator.div, "%s div %s")

    def mod(self, a, b):
        """Formats a mod b"""
        return OperatorExpression.binary_format(
            a, b, Operator.mod, "%s mod %s")

    def negate(self, value):
        """Formats -value"""
        return OperatorExpression.unary_format(value, Operator.negate, "-%s")

    def isof(self, type_name, value=None):
        if value is None:
            return Operator.call, "isof(%s)" % to_text(type_name)
        else:
            return (Operator.call,
                    "isof(%s,%s)" % (value[1], to_text(type_name)))

    def isof_type(self, type_def, value):
        return (Operator.call, "isof(%s,%s)" % (value[1], repr(type_def)))

    def cast(self, type_name, value=None):
        if value is None:
            return Operator.call, "cast(%s)" % to_text(type_name)
        else:
            return (Operator.call,
                    "cast(%s,%s)" % (value[1], to_text(type_name)))

    def cast_type(self, type_def, value):
        return (Operator.call, "cast(%s,%s)" % (value[1], repr(type_def)))

    def reference(self, qname):
        """Provide a text rendering for convenience"""
        return Operator.atom, to_text(qname)

    def bool_test(self, q, a, b=None):
        """Provide a test rendering for convenience"""
        if b is None:
            return Operator.call, "if(%s,%s)" % (q[1], a[1])
        else:
            return Operator.call, "if(%s,%s,%s)" % (q[1], a[1], b[1])

    def odata_concat(self, args):
        """Provide a text rendering for convenience

        odata.concat is not parsable in the general commonExpr syntax
        but is used in annotation expressions, it makes sense to provide
        a compact rendering for informational logging."""
        return (Operator.call,
                "odata.concat(%s)" % ",".join(arg[1] for arg in args))

    def odata_fill_uri_template(self, template, args):
        """Provide a text rendering for convenience

        See comment in :meth:`odata_concat`."""
        args = [template[1]] + [arg.evaluate(self) for arg in args]
        return Operator.call, "odata.fillUriTemplate(%s)" % ",".join(args)

    def odata_uri_encode(self, value):
        """Provide a text rendering for convenience

        See comment in :meth:`odata_concat`."""
        return Operator.call, "odata.uriEncode(%s)" % value[1]

    def path_expr(self, path):
        """Formats a path expression

        Not used in inline expressions so we provide a rendering for
        convenience only using angle brackets."""
        return Operator.member, \
            "<Path>%s</Path>" % names.path_expr_to_str(path)

    def annotation_path(self, path):
        """Formats an annotation path expression

        Not used in inline expressions so we provide a rendering for
        convenience only using angle brackets."""
        return Operator.member, \
            "<AnnotationPath>%s</AnnotationPath>" % \
            names.annotation_path_to_str(path)

    def navigation_path(self, path):
        """Formats a navigation property path expression

        Not used in inline expressions so we provide a rendering for
        convenience only using angle brackets."""
        return Operator.member, \
            "<NavigationPropertyPath>%s</NavigationPropertyPath>" % \
            names.navigation_path_to_str(path)

    def property_path(self, path):
        """Formats a property path expression

        Not used in inline expressions so we provide a rendering for
        convenience only using angle brackets."""
        return Operator.member, "<PropertyPath>%s</PropertyPath>" % \
            names.property_path_to_str(path)


class SearchFormatter(ExpressionProcessor):

    def word(self, word):
        return Operator.atom, word

    def bool_and(self, a, b):
        """Formats a and b"""
        return OperatorExpression.binary_format(
            a, b, Operator.bool_and, "%s AND %s")

    def bool_or(self, a, b):
        """Formats a or b"""
        return OperatorExpression.binary_format(
            a, b, Operator.bool_or, "%s OR %s")

    def bool_not(self, a):
        """Formats not a"""
        return OperatorExpression.binary_format(
            a, (Operator.atom, ""), Operator.bool_not, "NOT %s%s")
