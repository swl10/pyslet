#! /usr/bin/env python

from ..py2 import (
    is_text,
    to_text,
    uempty,
    )
from . import (
    comex,
    data,
    errors,
    model,
    names,
    primitive,
    types,
    )


try:
    from uritemplate import URITemplate
except ImportError:
    URITemplate = None


class ContextualProcessor(comex.ExpressionProcessor):

    """An abstract class used to process expressions

    The special value $it, used in inline expressions, represents a
    Value object that provides the immediate context for the
    evaluation.  We generalise this concept to allow elements in the
    metadata model to be '$it' too (with a more limited set of valid
    expression types) so that the same evaluator can be used for
    expressions declared in the metadata model (in applied Annotations).

    If $it is a bound Value instance then the owning service's model is
    used for any required name look-ups.  If $it is a metadata model
    element then the EntityModel in which $it was originally defined is
    used as the context for look-ups.  Similarly, if $it is an unbound
    Value then the EntityModel in which its type was originally defined
    is used.  These rules impose some technical limitations as the use
    of Reference/Include could be used to engineer a situation in which
    a name is undefined at the point of use but such models are clearly
    against the spirit, if not the letter, of the specification and
    should not cause difficulties in practice.

    You may override the model used for qualified name look-ups using
    the optional em argument.

    For completeness, we allow the special case where $it is null (or
    omitted) to allow constant expressions to be evaluated.  Expressions
    that require an EntityModel (including Enumeration constants) will
    raise an evaluation exception when $it is null."""

    def reference(self, qname):
        """Evaluates a labeled reference to an expression

        qname is always a :types:`QualifiedName` instance.  We provide
        an implementation here that looks up the name in the current
        model and then returns the result of evaluating the labeled
        expression."""
        if self.em is None:
            raise errors.ExpressionError(
                "No scope to evaluate %s" % to_text(qname))
        else:
            label = self.em.qualified_get(qname)
            if not isinstance(label, types.LabeledExpression):
                raise errors.ExpressionError(
                    errors.Requirement.label_ref_s % to_text(qname))
            return self.evaluate(label.expression)


class TypeChecker(ContextualProcessor):

    """An object used for type-checking expressions

    This object evaluates expressions to type objects rather than to
    actual values.  This is extension of the basic concept of inline
    expression evaluation that is useful for type-checking expressions.
    Instead of a Value instance the implicit variable is typically a
    type instance (NominalType) instead.

    it (None)
        The implicit variable may be any :class:`types.Annotable` object
        (typically a NominalType).  It may *not* be a Value instance. If
        not specified then a special :class:`types.NullType` instance is
        used instead.

    model (None)
        The context in which to look up names is passed in *model*, if
        not specified it is assumed to be the model exposed by the
        service the type is bound to.  For unbound Annotable objects the
        model in which the object was first declared is used instead."""

    def __init__(self, it=None, model=None, **kwargs):
        if isinstance(it, data.Value):
            raise errors.ExpressionError(
                "TypeChecker requires model element, not value: %r" % it)
        elif it is None:
            # default implicit variable is null
            super(TypeChecker, self).__init__(
                it=types.NullType.edm_base, model=model, **kwargs)
        else:
            if (isinstance(it, types.NominalType) and
                    it.service_ref is not None):
                if model is None:
                    model = it.service_ref().model
            elif isinstance(it, types.Annotatable):
                if model is None:
                    model = it.get_model()
            else:
                raise errors.ExpressionError(
                    "bad context for TypeChecker: %r" % it)
            super(TypeChecker, self).__init__(it=it, model=model, **kwargs)

    def null(self):
        return types.NullType.edm_base

    def boolean(self, value):
        return types.BooleanType.edm_base

    def guid(self, value):
        return types.GuidType.edm_base

    def date(self, value):
        return types.DateType.edm_base

    def date_time_offset(self, value, literal):
        return types.DateTimeOffsetType.edm_base

    def time_of_day(self, value, literal):
        return types.TimeOfDayType.edm_base

    def decimal(self, value):
        return types.DecimalType.edm_base

    def double(self, value):
        return types.DoubleType.edm_base

    def int64(self, value):
        return types.Int64Type.edm_base

    def string(self, value):
        return types.StringType.edm_base

    def duration(self, value, literal):
        return types.DurationType.edm_base

    def binary(self, value):
        return types.BinaryType.edm_base

    def enum(self, value):
        # we need to look up type definition for this.
        if self.em is None:
            raise errors.ExpressionError(
                "enum %s requires an evaluation context" %
                to_text(value))
        type_def = self.em.qualified_get(value.qname)
        if not isinstance(type_def, types.EnumerationType):
            raise errors.ExpressionError(
                "%s is not an EnumType" % to_text(value.qname))
        return type_def

    def geography(self, value, literal):
        # lazy implementation: create the value and return it's type
        return primitive.GeographyValue.from_value(value).type_def

    def geometry(self, value, literal):
        # lazy implementation: create the value and return it's type
        return primitive.GeometryValue.from_value(value).type_def

    # parameter: inheritied

    def root(self):
        if self.em is not None:
            container = self.em.get_container()
        else:
            container = None
        if container is None:
            raise errors.ExpressionError("$root requires service context")
        # we return the container itself, not 'type of container' as
        # subsequent paths components will have to resolve in this
        # context to an entity set, singleton, etc.  $root on its own is
        # not a valid expression
        return container

    def implicit_variable(self):
        return self.it

    def collection(self, expr_list):
        """Returns a :class:`types.CollectionType`

        The collection's item type is set from the common base type of
        all the items.  You cannot have collections of collections or
        mix incompatible types."""
        type_list = []
        for expr in expr_list:
            item = self.evaluate(expr)
            if item is None or isinstance(item, types.NullType):
                # None means skip this item, null is also ignored
                # because it can't affect the collection type.
                continue
            if not isinstance(item, types.NominalType):
                raise errors.ExpressionError(
                    errors.Requirement.collection_expression_s %
                    ("%s in collection" % to_text(item)))
            type_list.append(item)
        return types.CollectionType.from_types(type_list)

    def record(self, expr_list):
        """Returns Edm.ComplexType

        Also checks that the members can be evaluated and that there
        are no duplicate names"""
        bound_names = set()
        for name, expr in expr_list:
            if name in bound_names:
                raise errors.ExpressionError(
                    "Duplicate property name in record")
            bound_names.add(name)
            # any type is OK here so we don't need the result
            self.evaluate(expr)
        return model.edm['ComplexType']

    def member(self, segment):
        """Returns the type of the object obtained by path traversal"""
        if self.context is None:
            raise errors.PathError(
                "%s requires context" % to_text(segment))
        if is_text(segment):
            if isinstance(self.context, types.StructuredType):
                try:
                    result = self.context[segment].type_def
                except KeyError as err:
                    raise errors.PathError(err)
            elif isinstance(self.context, model.EntityContainer):
                try:
                    result = self.context[segment]
                except KeyError as err:
                    raise errors.PathError(err)
                if not isinstance(result, (model.Singleton, model.EntitySet)):
                    raise errors.ExpressionError(
                        "Can't navigate %s in root expresison" %
                        to_text(result))
                result = result.type_def
            else:
                raise errors.PathError(
                    "Can't navigate %s/%s", to_text(self.context), segment)
        elif isinstance(segment, names.QualifiedName):
            if self.em is None:
                raise errors.ExpressionError(
                    "%s requires an entity model context" %
                    to_text(segment))
            type_def = self.em.qualified_get(segment)
            if isinstance(type_def, types.StructuredType):
                # this is a type cast
                if isinstance(self.context, types.StructuredType):
                    if type_def.is_derived_from(self.context):
                        result = type_def
                    else:
                        raise errors.PathError(
                            "Can't cast %s/%s", to_text(self.context),
                            to_text(segment))
                else:
                    raise errors.PathError(
                        "Can't navigate %s/%s", to_text(self.context),
                        to_text(segment))
            elif isinstance(type_def, types.FunctionOverload):
                # for a bound function we must be followed by arguments
                # but the current context is effectively the first
                # argument so we push it onto a binding stack
                self.binding.append(self.context)
                result = type_def
            else:
                raise errors.PathError(
                    "Path resolution of: %r" % type_def)
        else:
            raise errors.ExpressionError(
                "Path resolution of: %s" % to_text(segment))
        if isinstance(result, types.SingletonType):
            return result.item_type
        else:
            return result

    def member_args(self, args):
        if isinstance(self.context, types.FunctionOverload):
            binding = self.binding.pop()
            # grab the argument names only for now
            params = [a.name for a in args.operands]
            call = self.context.resolve(binding, params)
            if call is None and binding is not None:
                # try an unbound function
                call = self.context.resolve(None, params)
            if call is None:
                raise errors.ExpressionError(
                    "Can't resolve Function %s(%r)" %
                    (to_text(self.context), params))
            # we become the return type
            return call.return_type
        else:
            if isinstance(self.context, types.EntitySetType):
                entity_type = self.context.item_type
            elif (isinstance(self.context, types.CollectionType) and
                    isinstance(self.context.item_type, types.EntityType)):
                # a collection of entities might be bound in practice
                # so just check the key can be used as a key
                entity_type = self.context.item_type
            else:
                raise errors.ExpressionError(
                    "member_args(%s,...)" % to_text(self.context))
            # evaluate the args as a key
            key_dict = entity_type.get_key_type_dict()
            if len(args.operands) != len(key_dict):
                raise errors.ExpressionError(
                    "key mismatch for %s" % to_text(entity_type))
            if len(key_dict) == 1:
                def_key_name = next(iter(key_dict))
            key_done = set()
            for arg in args.operands:
                if isinstance(arg, comex.BindExpression):
                    key_name, key_type = self.evaluate(arg)
                else:
                    key_name, key_type = def_key_name, self.evaluate(arg)
                if key_name in key_done or key_name not in key_dict:
                    raise errors.ExpressionError(
                        "bad key for %s" % to_text(entity_type))
                key_done.add(key_name)
                if isinstance(key_type, types.NullType):
                    continue
                # key_type must be compatible with the type in key_dict
                if not key_dict[key_name].compatible(key_type):
                    raise errors.ExpressionError(
                        "key type mismatch for %s(%s)" %
                        (to_text(entity_type), key_name))
            return entity_type

    def member_count(self):
        if isinstance(self.context, types.CollectionType):
            return types.Int64Type.edm_base
        else:
            raise errors.ExpressionError(
                "$count not allowed after %s" % to_text(self.context))

    def member_any(self, lambda_name=None, lambda_expression=None):
        if isinstance(self.context, types.CollectionType):
            if lambda_name is not None:
                with self.set_lambda_context(
                        lambda_name, self.context.item_type):
                    result = self.evaluate(lambda_expression)
                # must be a boolean or any_type
                if not (result.is_derived_from(types.BooleanType.edm_base) or
                        result is None):
                    raise errors.ExpressionError(
                        "lambda expression must be boolean, not %r" % result)
            return types.BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "any() not allowed after %s" % to_text(self.context))

    def member_all(self, lambda_name, lambda_expression):
        if isinstance(self.context, types.CollectionType):
            with self.set_lambda_context(
                    lambda_name, self.context.item_type):
                result = self.evaluate(lambda_expression)
            # must be a boolean or any_type
            if not (result.is_derived_from(types.BooleanType.edm_base) or
                    result is None):
                raise errors.ExpressionError(
                    "lambda expression must be boolean, not %r" % result)
            return types.BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "all(...) not allowed after %s" % to_text(self.context))

    def mindatetime(self):
        return types.DateTimeOffsetType.edm_base

    def maxdatetime(self):
        return types.DateTimeOffsetType.edm_base

    def now(self):
        return types.DateTimeOffsetType.edm_base

    def length(self, value):
        # check that value is string or any
        if (value is not None and
                not value.compatible(types.StringType.edm_base) and
                not isinstance(value, types.CollectionType)):
            raise errors.ExpressionError(
                "length requires Edm.String or Collection not %s" %
                to_text(value))
        return types.Int64Type.edm_base

    def _string_method(self, value, method_name):
        # check that value is string or any
        if (value is not None and
                not value.compatible(types.StringType.edm_base)):
            raise errors.ExpressionError(
                "%s requires Edm.String not %s" %
                (method_name, to_text(value)))
        return types.StringType.edm_base

    def tolower(self, value):
        return self._string_method(value, "tolower")

    def toupper(self, value):
        return self._string_method(value, "toupper")

    def trim(self, value):
        return self._string_method(value, "trim")

    def _date_method(self, value, method_name):
        # check that value is Date, DateTimeOffset or any
        if (value is not None and
                not value.compatible(types.DateTimeOffsetType.edm_base) and
                not value.compatible(types.DateType.edm_base)):
            raise errors.ExpressionError(
                "%s requires Edm.Date or Edm.DateTimeOffset not %s" %
                (method_name, to_text(value)))
        return primitive.edm_int32

    def year(self, value):
        return self._date_method(value, "year")

    def month(self, value):
        return self._date_method(value, "month")

    def day(self, value):
        return self._date_method(value, "day")

    def _time_method(self, value, method_name):
        # check that value is TimeOfDay, DateTimeOffset or any
        if (value is not None and
                not value.compatible(types.DateTimeOffsetType.edm_base) and
                not value.compatible(types.TimeOfDayType.edm_base)):
            raise errors.ExpressionError(
                "%s requires Edm.TimeOfDay or Edm.DateTimeOffset not %s" %
                (method_name, to_text(value)))
        return primitive.edm_int32

    def hour(self, value):
        return self._time_method(value, "hour")

    def minute(self, value):
        return self._time_method(value, "minute")

    def second(self, value):
        return self._time_method(value, "second")

    def fractionalseconds(self, value):
        # check that value is TimeOfDay, DateTimeOffset or any
        if (value is not None and
                not value.compatible(types.DateTimeOffsetType.edm_base) and
                not value.compatible(types.TimeOfDayType.edm_base)):
            raise errors.ExpressionError(
                "fractionalseconds requires Edm.TimeOfDay or "
                "Edm.DateTimeOffset not %s" % to_text(value))
        return types.DecimalType.edm_base

    def totalseconds(self, value):
        # check that value is Duration or any
        if (value is not None and
                not value.compatible(types.DurationType.edm_base)):
            raise errors.ExpressionError(
                "totalseconds requires Edm.Duration not %s" % to_text(value))
        return types.DecimalType.edm_base

    def date_method(self, value):
        # check that value is DateTimeOffset or any
        if (value is not None and
                not value.compatible(types.DateTimeOffsetType.edm_base)):
            raise errors.ExpressionError(
                "date requires Edm.DateTimeOffset not %s" % to_text(value))
        return types.DateType.edm_base

    def time(self, value):
        # check that value is DateTimeOffset or any
        if (value is not None and
                not value.compatible(types.DateTimeOffsetType.edm_base)):
            raise errors.ExpressionError(
                "time requires Edm.DateTimeOffset not %s" % to_text(value))
        return types.TimeOfDayType.edm_base

    def totaloffsetminutes(self, value):
        # check that value is DateTimeOffset or any
        if (value is not None and
                not value.compatible(types.DateTimeOffsetType.edm_base)):
            raise errors.ExpressionError(
                "totaloffsetminutes requires Edm.DateTimeOffset not %s" %
                to_text(value))
        return primitive.edm_int32

    def _math(self, value, method_name):
        if isinstance(value, types.FloatType):
            # forces a float
            return types.DoubleType.edm_base
        elif value.compatible(types.DecimalType.edm_base):
            return types.DecimalType.edm_base
        else:
            raise errors.ExpressionError(
                "%s requires numeric type not %s" %
                (method_name, to_text(value)))

    def round(self, value):
        return self._math(value, "round")

    def floor(self, value):
        return self._math(value, "floor")

    def ceiling(self, value):
        return self._math(value, "ceiling")

    def geo_length(self, value):
        # check that value is GeographyLineString, GeometryLineString or any
        if (value is not None and
                not value.compatible(
                    types.GeographyLineStringType.edm_base) and
                not value.compatible(types.GeometryLineStringType.edm_base)):
            raise errors.ExpressionError(
                "geo_length requires Edm.GeographyLineString or "
                "Edm.GeometryLineString not %s" % to_text(value))
        return types.DoubleType.edm_base

    def _string_test_method(self, a, b, method_name):
        # check that values are string or any
        if ((a is not None and
                not a.compatible(types.StringType.edm_base)) or
                (b is not None and
                 not b.compatible(types.StringType.edm_base))):
            raise errors.ExpressionError(
                "%s requires Edm.Strings not (%s, %s)" %
                (method_name, to_text(a), to_text(b)))
        return types.BooleanType.edm_base

    def contains(self, a, b):
        return self._string_test_method(a, b, "contains")

    def startswith(self, a, b):
        return self._string_test_method(a, b, "startswith")

    def endswith(self, a, b):
        return self._string_test_method(a, b, "endswith")

    def indexof(self, a, b):
        # check that values are string or any
        if ((a is not None and
                not a.compatible(types.StringType.edm_base)) or
                (b is not None and
                 not b.compatible(types.StringType.edm_base))):
            raise errors.ExpressionError(
                "indexof requires Edm.Strings not (%s, %s)" %
                (to_text(a), to_text(b)))
        return primitive.edm_int32

    def concat(self, a, b):
        # check that values are string or any
        if ((a is not None and
                not a.compatible(types.StringType.edm_base)) or
                (b is not None and
                 not b.compatible(types.StringType.edm_base))):
            raise errors.ExpressionError(
                "concat requires Edm.Strings not (%s, %s)" %
                (to_text(a), to_text(b)))
        return types.StringType.edm_base

    def geo_distance(self, a, b):
        if ((a is not None and
                not a.compatible(types.GeographyPointType.edm_base) and
                not a.compatible(types.GeometryPointType.edm_base)) or
                (b is not None and
                 not b.compatible(types.GeographyPointType.edm_base) and
                 not b.compatible(types.GeometryPointType.edm_base))):
            raise errors.ExpressionError(
                "geo.distance requires GeoPoint not (%s, %s)" %
                (to_text(a), to_text(b)))
        return types.DoubleType.edm_base

    def geo_intersects(self, a, b):
        if ((a is not None and
                not a.compatible(types.GeographyPointType.edm_base) and
                not a.compatible(types.GeometryPointType.edm_base)) or
                (b is not None and
                 not b.compatible(types.GeographyPolygonType.edm_base) and
                 not b.compatible(types.GeometryPolygonType.edm_base))):
            raise errors.ExpressionError(
                "geo.intersects requires (GeoPoint,GeoPolygon) not (%s, %s)" %
                (to_text(a), to_text(b)))
        return types.BooleanType.edm_base

    def substring(self, a, b, c=None):
        # check that values are string or any
        if ((a is not None and not a.compatible(types.StringType.edm_base)) or
                (b is not None and
                 not b.compatible(types.Int64Type.edm_base)) or
                (c is not None and
                 not c.compatible(types.Int64Type.edm_base))):
            raise errors.ExpressionError(
                "substring requires (Edm.String,Edm.Int32[,Edm.Int32]) not "
                "(%s, %s%s)" % (to_text(a), to_text(b),
                                "" if c is None else ",%s" % to_text(c)))
        return types.StringType.edm_base

    def bool_and(self, a, b):
        if isinstance(a, types.NominalType):
            return a.and_type(b)
        else:
            raise errors.ExpressionError(errors.Requirement.annotation_and_or)

    def bool_or(self, a, b):
        if isinstance(a, types.NominalType):
            return a.or_type(b)
        else:
            raise errors.ExpressionError(errors.Requirement.annotation_and_or)

    def bool_not(self, op):
        if isinstance(op, types.NominalType):
            return op.not_type()
        else:
            raise errors.ExpressionError(errors.Requirement.annotation_and_or)

    def eq(self, a, b):
        if isinstance(a, types.NominalType):
            return a.eq_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s eq %s" % (to_text(a), to_text(b)))

    def ne(self, a, b):
        if isinstance(a, types.NominalType):
            return a.ne_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s ne %s" % (to_text(a), to_text(b)))

    def gt(self, a, b):
        if isinstance(a, types.NominalType):
            return a.gt_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s gt %s" % (to_text(a), to_text(b)))

    def ge(self, a, b):
        if isinstance(a, types.NominalType):
            return a.ge_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s ge %s" % (to_text(a), to_text(b)))

    def lt(self, a, b):
        if isinstance(a, types.NominalType):
            return a.lt_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s lt %s" % (to_text(a), to_text(b)))

    def le(self, a, b):
        if isinstance(a, types.NominalType):
            return a.le_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s le %s" % (to_text(a), to_text(b)))

    def has(self, a, b):
        if isinstance(a, types.NominalType):
            return a.has_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s has %s" % (to_text(a), to_text(b)))

    def add(self, a, b):
        if isinstance(a, types.NominalType):
            return a.add_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s add %s" % (to_text(a), to_text(b)))

    def sub(self, a, b):
        if isinstance(a, types.NominalType):
            return a.sub_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s sub %s" % (to_text(a), to_text(b)))

    def mul(self, a, b):
        if isinstance(a, types.NominalType):
            return a.mul_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s mul %s" % (to_text(a), to_text(b)))

    def div(self, a, b):
        if isinstance(a, types.NominalType):
            return a.div_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s div %s" % (to_text(a), to_text(b)))

    def mod(self, a, b):
        if isinstance(a, types.NominalType):
            return a.mod_type(b)
        else:
            raise errors.ExpressionError(
                "bad types for operator: %s mod %s" % (to_text(a), to_text(b)))

    def negate(self, value):
        if isinstance(value, types.NominalType):
            return value.negate_type()
        else:
            raise errors.ExpressionError(
                "bad types for operator: -%s" % to_text(value))

    # TODO: cast

    def cast_type(self, type_def, expression):
        """Always returns type_def; checks expression"""
        if expression is not None and not expression.compatible(type_def):
            # can expression be cast to type_def?
            # this is a weaker test than compatibility because any
            # primitive can be cast to a string
            if not isinstance(expression, types.PrimitiveType) or \
                    not type_def.is_derived_from(types.StringType.edm_base):
                raise errors.ExpressionError(
                    "Can't cast %s to %s" %
                    (to_text(expression), to_text(type_def)))
        return type_def

    # TODO: isof

    def isof_type(self, type_def, expression):
        """Always returns Edm.Boolean"""
        return types.BooleanType.edm_base

    # TODO: reference

    def bool_test(self, q, a, b=None):
        """Checks that q is boolean

        We also insist that a and b are compatible types and return the
        most specific common ancestor type.  For example, if b is
        derived from a, then we would return a."""
        if q and not q.compatible(types.BooleanType.edm_base):
            raise errors.ExpressionError(
                errors.Requirement.if_test_s % to_text(q))
        if a is None:
            return b
        elif b is None:
            return a
        else:
            return a.common_ancestor(b)

    def odata_concat(self, args):
        """Checks that all args are primitives

        Always returns Edm.String"""
        for arg in args:
            if arg and not isinstance(arg, types.PrimitiveType):
                raise errors.ExpressionError(
                    errors.Requirement.annotation_concat_args_s % to_text(arg))
        return types.StringType.edm_base

    def odata_fill_uri_template(self, template, args):
        """Checks template and args; returns Edm.String"""
        if template and not template.compatible(types.StringType.edm_base):
            raise errors.ExpressionError(
                errors.Requirement.annotation_fill_uri_template_args_s %
                repr(template))
        bound_names = set()
        for arg in args:
            if not isinstance(arg, comex.BindExpression):
                raise errors.ExpressionError(
                    "Expected bind in odata.fillUriTemplate, not %r" % arg)
            name, vtype = self.evaluate(arg)
            if name in bound_names:
                raise errors.ExpressionError(
                    "Duplicate binding in odata.fillUriTemplate: %s" % name)
            bound_names.add(name)
            if vtype is None or isinstance(vtype, types.PrimitiveType):
                continue
            elif isinstance(vtype, types.CollectionType):
                if isinstance(vtype.item_type, primitive.PrimitiveType) or \
                        isinstance(vtype.item_type, types.ComplexType):
                    continue
                else:
                    raise errors.ExpressionError(
                        "fillUriTemplate requires PrimitiveType, "
                        "Collection(PrimitiveType) or "
                        "Collection(ComplexType): %r" % vtype)
        return types.StringType.edm_base

    def odata_uri_encode(self, value):
        """Returns Edm.String; checks value is primitive"""
        if value and not isinstance(value, types.PrimitiveType):
            raise errors.ExpressionError(
                "uriEncode requires primitive value, not %s" %
                repr(value))
        return types.StringType.edm_base

    def path_expr(self, path):
        """Returns the type of the property with *path*"""
        it = self.it
        if isinstance(it, data.Value):
            it = it.type_def
        for seg in path:
            if is_text(seg):
                # this is a regular property to look up
                try:
                    it = it[seg].type_def
                except KeyError:
                    raise errors.PathError(names.path_to_str(path))
            else:
                raise NotImplementedError(
                    "Path resolution of: %s" % to_text(seg))
            if isinstance(it, types.SingletonType):
                it = it.item_type
            elif isinstance(it, types.EntitySetType):
                it = it.item_type.collection_type()
        return it

    def annotation_path(self, value):
        """Always returns Edm.AnnotationPath"""
        return primitive.edm_annotation_path

    def navigation_path(self, path):
        """Always returns Edm.NavigationPath

        Checks that the value is a valid navigation path in the current
        context."""
        it = self.it
        if isinstance(it, data.Value):
            it = it.type_def
        elif isinstance(it, (model.Singleton, model.EntitySet)):
            it = it.entity_type
        nav_path = False
        for seg in path:
            if is_text(seg):
                # this is a regular property to look up
                try:
                    it = it[seg]
                except KeyError:
                    raise errors.PathError(
                        errors.Requirement.navigation_path_s %
                        names.path_to_str(path))
                nav_path = isinstance(it, types.NavigationProperty)
                it = it.type_def
            else:
                raise NotImplementedError(
                    "Path resolution of: %s" % to_text(seg))
            if isinstance(it, types.CollectionType):
                it = it.item_type
            elif isinstance(it, (types.SingletonType, types.EntitySetType)):
                it = it.item_type
        if not nav_path:
            raise errors.PathError(
                errors.Requirement.navigation_path_s %
                names.path_to_str(path))
        return primitive.edm_navigation_property_path

    def property_path(self, value):
        """Always returns Edm.PropertyPath"""
        return primitive.edm_property_path

    # TODO: word
    # TODO: phrase


class Evaluator(ContextualProcessor):

    """An object used to evaluate expressions

    it
        The implicit variable, see :class:`comex.ExpressionProcessor`
        for more information.  If omitted a null value is used instead.

    model
        If omitted, the model is inferred from the implicit variable if
        it is a Value bound to a service.  If the Value is unbound then
        the Value's type is used to infer the model instead.  For
        Annotatable objects the rules are applied as for
        :class:`TypeChecker`"""

    def __init__(self, it=None, model=None, **kwargs):
        it = types.NullType.edm_base() if it is None else it
        if model is not None:
            pass
        elif isinstance(it, data.Value):
            # not actually annotatable, split out for clarity
            model = it.get_model()
        elif isinstance(it, (types.Annotatable)):
            model = it.get_model()
        else:
            raise errors.ExpressionError("Unexpected context %r" % it)
        super(Evaluator, self).__init__(it=it, model=model, **kwargs)

    @classmethod
    def evaluate_annotation(cls, a, it):
        """Evaluates an annotation

        This is a class method, if the annotation has no associated
        expression the annotation term's default is used or null is
        returned.  Otherwise the annotation expression is evaluated in
        the context of the :class:`data.Value` instance passed in
        *it*."""
        if a.expression is None:
            # get the declaring term's default (or null)
            return a.term().get_default()
        else:
            return cls(it).evaluate(a.expression)

    def null(self):
        return types.NullType.edm_base()

    def boolean(self, value):
        return primitive.BooleanValue(value)

    def guid(self, value):
        return primitive.GuidValue(value)

    def date(self, value):
        return primitive.DateValue(value)

    def date_time_offset(self, value, literal):
        return primitive.DateTimeOffsetValue(value)

    def time_of_day(self, value, literal):
        return primitive.TimeOfDayValue(value)

    def decimal(self, value):
        return primitive.DecimalValue(value)

    def double(self, value):
        return primitive.DoubleValue(value)

    def int64(self, value):
        return primitive.Int64Value(value)

    def string(self, value):
        return primitive.StringValue(value)

    def duration(self, value, literal):
        return primitive.DurationValue(value)

    def binary(self, value):
        return primitive.BinaryValue(value)

    def enum(self, value):
        # we need to look up type definition for this.
        if self.em is None:
            raise errors.ExpressionError(
                "enum %s requires an evaluation context" %
                to_text(value))
        type_def = self.em.qualified_get(value.qname)
        if not isinstance(type_def, types.EnumerationType):
            raise errors.ExpressionError(
                "%s is not an EnumType" % to_text(value.qname))
        return type_def(value.value)

    def geography(self, value, literal):
        return primitive.GeographyValue.from_value(value)

    def geometry(self, value, literal):
        return primitive.GeometryValue.from_value(value)

    # parameter: inheritied

    def root(self):
        if self.em is not None:
            container = self.em.get_container()
        else:
            container = None
        if container is None:
            raise errors.ExpressionError("$root requires service context")
        return container

    def implicit_variable(self):
        return self.it

    def collection(self, expr_list):
        """Returns a :class:`CollectionValue`

        The collection's item type is set from common base type of all
        the items.  You cannot have collections of collections or mix
        incompatible types."""
        value_list = []
        for expr in expr_list:
            item = self.evaluate(expr)
            if item is None:
                # two-argument bool_test evaluated False, skip adding
                # this item to the collection
                continue
            else:
                value_list.append(item)
        return data.CollectionValue.from_values(value_list)

    def record(self, expr_list):
        """Returns a :class:`data.ComplexValue` instance.

        The return value is a collection of property values notionally
        contained in an open complex type with no defined properties."""
        t = types.ComplexType(value_type=data.ComplexValue)
        t.set_open_type(True)
        t.close()
        value = t()
        for name, expr in expr_list:
            if name in value:
                raise errors.ExpressionError(
                    "Duplicate property name in record")
            value[name] = self.evaluate(expr)
        return value

    def member(self, segment):
        """Returns the value obtained by path traversal"""
        if is_text(segment):
            if isinstance(self.context, data.StructuredValue):
                try:
                    if self.context.is_null():
                        if segment in self.context.type_def:
                            # valid path segment, update our null
                            result = self.context.type_def[segment].type_def()
                        else:
                            raise KeyError
                    else:
                        result = self.context[segment]
                except KeyError as err:
                    if segment in self.context.type_def:
                        # this is a property that was not selected
                        self.context.select('*')
                        self.context.select(segment)
                        result = self.context[segment]
                    else:
                        raise errors.PathError(segment)
            elif isinstance(self.context, model.EntityContainer):
                try:
                    result = self.context[segment]
                except KeyError as err:
                    raise errors.PathError(err)
                if not isinstance(result, (model.Singleton, model.EntitySet)):
                    raise errors.ExpressionError(
                        "Can't navigate %s in root expresison" %
                        to_text(result))
                # call the EntitySet or Singleton to obtain the
                # EntitySetValue or SingletonValue
                result = result()
            else:
                raise errors.PathError(
                    "Can't navigate %r/%s" % (self.context, segment))
        elif isinstance(segment, names.QualifiedName):
            if self.em is None:
                raise errors.ExpressionError(
                    "%s requires an entity model context" %
                    to_text(segment))
            type_def = self.em.qualified_get(segment)
            if isinstance(type_def, types.StructuredType):
                if isinstance(self.context.type_def, types.StructuredType):
                    # this is a type cast, the context must be a value
                    # of this type, if it isn't then we return null
                    # of the appropriate type!
                    if self.context.type_def.is_derived_from(type_def):
                        # no change in context
                        result = self.context
                    else:
                        result = type_def()
                # elif: TODO, you can type_cast a collection, special
                # treatment is required as we can't have null collections
                else:
                    # you can't add a type cast to a non structured type
                    raise errors.PathError(
                        "Can't navigate %s/%s", to_text(self.context.type_def),
                        to_text(segment))
            elif isinstance(type_def, types.FunctionOverload):
                self.binding.append(self.context)
                result = type_def
            else:
                raise errors.PathError(
                    "Path resolution of: %r" % type_def)
        else:
            raise errors.ExpressionError(
                "Path resolution of: %s" % to_text(segment))
        return result

    def member_args(self, args):
        if isinstance(self.context, types.FunctionOverload):
            binding = self.binding.pop()
            # grab the argument names only for now
            params = [a.name for a in args.operands]
            call = None
            if binding is not None:
                try:
                    call = binding.get_callable(self.context.qname, params)
                except errors.ODataError:
                    raise errors.PathError(
                        "Can't resolve Function %s(%r)" %
                        (to_text(self.context), params))
            else:
                # look for the unbound function
                call_type = self.context.resolve(None, params)
                if call_type is None:
                    raise errors.ExpressionError(
                        "Can't resolve Function %s(%r)" %
                        (to_text(self.context), params))
                call = call_type()
            # we now have a callable but we need to set the parameter
            # values from the arguments in the expression
            for a in args.operands:
                name, value = self.evaluate(a)
                call[name].assign(value)
            return call()
        else:
            if isinstance(self.context, data.EntitySetValue):
                entity_type = self.context.type_def.item_type
            elif (isinstance(self.context, data.CollectionValue) and
                    isinstance(self.context.type_def.item_type,
                               types.EntityType)):
                # a collection of entities might be bound in practice
                # or just badly defined in the metadata, we have a
                # method for that...
                entity_type = self.context.type_def.item_type
            else:
                raise errors.ExpressionError(
                    "member_args(%s,...)" % to_text(self.context))
            # evaluate the args as a key
            key_dict = entity_type.get_key_dict()
            if len(args.operands) != len(key_dict):
                raise errors.ExpressionError(
                    "key mismatch for %s" % to_text(entity_type))
            if len(key_dict) == 1:
                def_key_name = next(iter(key_dict))
            key_done = set()
            for arg in args.operands:
                if isinstance(arg, comex.BindExpression):
                    key_name, key_value = self.evaluate(arg)
                else:
                    key_name, key_value = def_key_name, self.evaluate(arg)
                if key_name in key_done or key_name not in key_dict:
                    raise errors.ExpressionError(
                        "bad key for %s" % to_text(entity_type))
                key_done.add(key_name)
                try:
                    key_dict[key_name].assign(key_value)
                except (ValueError, TypeError):
                    raise errors.ExpressionError(
                        "key mismatch for %s(%s)" %
                        (to_text(entity_type), key_name))
            key = entity_type.get_key_from_dict(key_dict)
            if isinstance(self.context, data.EntitySetValue):
                return self.context[key]
            else:
                # CollectionValue
                self.context.set_key_filter(key)
                return self.context[0]

    # TODO: member_count

    # TODO: member_any

    # TODO: member_all

    # TODO: mindatetime
    # TODO: maxdatetime
    # TODO: now
    # TODO: length
    # TODO: tolower
    # TODO: toupper
    # TODO: trim
    # TODO: year
    # TODO: month
    # TODO: day
    # TODO: hour
    # TODO: minute
    # TODO: second
    # TODO: fractionalseconds
    # TODO: totalseconds
    # TODO: date_method
    # TODO: time
    # TODO: totaloffsetminutes
    # TODO: round
    # TODO: floor
    # TODO: ceiling
    # TODO: geo_length
    # TODO: contains
    # TODO: startswith
    # TODO: endswith
    # TODO: indexof
    # TODO: concat
    # TODO: geo_distance
    # TODO: geo_intersects
    # TODO: substring

    def bool_and(self, a, b):
        if a.is_null() and b.is_null():
            return primitive.BooleanValue(None)
        elif a.is_null():
            if (b.get_value() is False):
                return primitive.BooleanValue(False)
            else:
                return primitive.BooleanValue(None)
        elif b.is_null():
            if (a.get_value() is False):
                return primitive.BooleanValue(False)
            else:
                return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(a.get_value() and b.get_value())

    def bool_or(self, a, b):
        if a.is_null() and b.is_null():
            return primitive.BooleanValue(None)
        elif a.is_null():
            if (b.get_value() is True):
                return primitive.BooleanValue(True)
            else:
                return primitive.BooleanValue(None)
        elif b.is_null():
            if (a.get_value() is True):
                return primitive.BooleanValue(True)
            else:
                return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(a.get_value() or b.get_value())

    def bool_not(self, op):
        if op.is_null():
            return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(not op.get_value())

    def eq(self, a, b):
        if a.is_null() and b.is_null():
            return primitive.BooleanValue(True)
        elif a.is_null() or b.is_null():
            return primitive.BooleanValue(False)
        else:
            return primitive.BooleanValue(a.get_value() == b.get_value())

    def ne(self, a, b):
        if a.is_null() and b.is_null():
            return primitive.BooleanValue(False)
        elif a.is_null() or b.is_null():
            return primitive.BooleanValue(True)
        else:
            return primitive.BooleanValue(a.get_value() != b.get_value())

    def gt(self, a, b):
        if a.is_null() or b.is_null():
            return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(a.get_value() > b.get_value())

    def ge(self, a, b):
        if a.is_null() and b.is_null():
            return primitive.BooleanValue(True)
        elif a.is_null() or b.is_null():
            return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(a.get_value() >= b.get_value())

    def lt(self, a, b):
        if a.is_null() or b.is_null():
            return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(a.get_value() < b.get_value())

    def le(self, a, b):
        if a.is_null() and b.is_null():
            return primitive.BooleanValue(True)
        elif a.is_null() or b.is_null():
            return primitive.BooleanValue(None)
        else:
            return primitive.BooleanValue(a.get_value() <= b.get_value())

    # TODO: has

    # TODO: add
    # TODO: sub
    # TODO: mul
    # TODO: div
    # TODO: mod
    # TODO: negate

    def cast(self, type_name, expression=None):
        """See :meth:`types.Values.cast` for more information

        The *type_name* is looked up in the current context with the
        exception of types in the Edm namespace itself which are always
        resolved to the built-in types even if there is no metadata
        model in the current processing context.  This ensures that
        expressions such as "cast(Edm.Decimal,3.125)" can be evaluated
        without requiring a context to be created specially."""
        if type_name.namespace == "Edm":
            # special case, we don't need a context
            type_def = model.edm[type_name.name]
        elif self.em is None:
            # look up the type in the context
            raise errors.ExpressionError(
                "cast to %s requires an evaluation context" %
                to_text(type_name))
        else:
            type_def = self.em.qualified_get(type_name)
            if not isinstance(type_def, types.NominalType):
                raise errors.ExpressionError(
                    "cast requires type not %s" % to_text(type_name))
        if expression is None:
            expression = self.it
        return expression.cast(type_def)

    def cast_type(self, type_def, expression):
        """Implemented using :meth:`data.Value.cast`"""
        return expression.cast(type_def)

    def isof(self, type_name, expression=None):
        """See :meth:`cast` for more information"""
        if type_name.namespace == "Edm":
            # special case, we don't need a context
            type_def = model.edm[type_name.name]
        elif self.em is None:
            # look up the type in the context
            raise errors.ExpressionError(
                "isof(%s) requires an evaluation context" %
                to_text(type_name))
        else:
            type_def = self.em.qualified_get(type_name)
            if not isinstance(type_def, types.NominalType):
                raise errors.ExpressionError(
                    "isof requires type not %s" % to_text(type_name))
        if expression is None:
            expression = self.it
        return primitive.BooleanValue(
            expression.type_def.is_derived_from(type_def))

    def isof_type(self, type_def, expression):
        """See :meth:`isof` for more information"""
        # firstly, we take the most-specific named type represented by
        # type_def
        if isinstance(expression, primitive.PrimitiveValue):
            return primitive.BooleanValue(
                expression.type_def.derived_match(type_def))
        else:
            named_type = list(type_def.declared_bases())[0]
            return primitive.BooleanValue(
                expression.type_def.is_derived_from(named_type))

    # TODO: reference

    def bool_test(self, q, a, b=None):
        """Results in a or b depending on the result of q.

        There is no indication in the specification on the correct
        handling of null so we logically extend the rules for and/or: if
        q evaluates to null then we return a type-less null.

        Because of the way the expression tree is evaluated we treat
        this operation like a function if(q, a, b) and hence both a and
        b are evaluated every time, even though the result of one of
        them (or both if q is null) is discarded.  There are no
        side-effects to worry about and this expression element is
        unlikely to be used in perforance critical situations so this
        seems acceptable.

        Although b is optional it will be returned even if it is null
        when q is False.  We have a separate check that the
        two-parameter form of <If> is only used inside collections
        (where None is skipped) so other method implementations need not
        concern themselves with the possibility of an unexpected None
        input."""
        if not isinstance(q, primitive.BooleanValue):
            raise errors.ExpressionError(
                errors.Requirement.if_test_s % repr(q))
        if q.is_null():
            return primitive.PrimitiveValue(None)
        elif q.get_value() is True:
            return a
        else:
            return b

    def odata_concat(self, args):
        """Returns a :class:`primitive.StringValue` instance."""
        result = []
        for arg in args:
            if not isinstance(
                    arg,
                    (primitive.PrimitiveValue, primitive.EnumerationValue)):
                raise errors.ExpressionError(
                    errors.Requirement.annotation_concat_args_s % repr(arg))
            result.append(to_text(arg))
        return primitive.StringValue(uempty.join(result))

    def odata_fill_uri_template(self, template, args):
        """Returns a :class:`primitive.StringValue` instance.

        This function is implemented using the uritemplate module
        available from PyPi.  This function represents a corner case
        within the OData model so we don't require uritemplate as a
        dependency.  If it is not present an EvaluationError is
        raised."""
        bindings = {}
        if not isinstance(template, primitive.StringValue):
            raise errors.ExpressionError(
                errors.Requirement.annotation_fill_uri_template_args_s %
                repr(template))
        for arg in args:
            if not isinstance(arg, comex.BindExpression):
                raise errors.ExpressionError(
                    "Expected bind in odata.fillUriTemplate, not %r" % arg)
            name, value = self.evaluate(arg)
            if name in bindings:
                raise errors.ExpressionError(
                    "Duplicate binding in odata.fillUriTemplate: %s" % name)
            if isinstance(
                    value, (primitive.PrimitiveValue,
                            primitive.EnumerationValue)):
                bindings[name] = to_text(value)
            elif isinstance(value, data.CollectionValue):
                if isinstance(
                        value.item_type,
                        (primitive.PrimitiveType, types.EnumerationType)):
                    bindings[name] = [to_text(i) for i in value]
                elif isinstance(value.item_type, types.ComplexType):
                    arg_list = []
                    for v in value:
                        kv = sorted(v.keys())[:2]
                        if len(kv) != 2:
                            raise errors.ExpressionError(
                                "Key-value map requires ComplexValue with at "
                                "least two properties" % repr(v))
                        arg_list.append((to_text(v[kv[0]]), to_text(v[kv[1]])))
                    bindings[name] = arg_list
                else:
                    raise errors.ExpressionError(
                        "fillUriTemplate requires PrimitiveType, "
                        "Collection(PrimitiveType) or "
                        "Collection(ComplexType): %s" % repr(value))
        if URITemplate is None:
            raise errors.ExpressionError(
                "fillUriTemplate not supported, try: pip install uritemplate")
        else:
            t = URITemplate(template.get_value())
            return primitive.StringValue(t.expand(**bindings))

    def odata_uri_encode(self, value):
        """Returns a :class:`primitive.StringValue` instance.

        See :meth:`primitive.PrimitiveValue.literal_string` for more
        information."""
        if not isinstance(value, primitive.PrimitiveValue):
            raise errors.ExpressionError(
                "uriEncode requires primitive value, not %s" %
                repr(value))
        return primitive.StringValue(value.literal_string())

    def path_expr(self, path):
        """Returns the Value of the path expression *path*

        This evaluation follows """
        it = self.it
        for seg in path:
            if is_text(seg):
                # this is a regular property to look up
                try:
                    if isinstance(it, data.StructuredValue):
                        it = it[seg]
                        if isinstance(it, data.SingletonValue):
                            # no keyPredicate: implicit call
                            it = it()
                    elif isinstance(it, model.EntityContainer):
                        child = it[seg]
                        if isinstance(child,
                                      (model.EntitySet, model.Singleton)):
                            it = child()
                        else:
                            raise KeyError(
                                "Unexpected container child %r" % child)
                    elif isinstance(it, data.SingletonValue):
                        it = it()[seg]
                    elif isinstance(it, data.EntitySetValue):
                        # create a collection of values
                        raise NotImplementedError(
                            "Path resolution of %r/%s" % (it, seg))
                    else:
                        raise errors.PathError("%r/%s" % (it, seg))
                except KeyError:
                    raise errors.PathError(names.path_to_str(path))
            else:
                raise NotImplementedError(
                    "Path resolution of: %s" % to_text(seg))
        return it

    def annotation_path(self, value):
        """Returns a :class:`primitive.AnnotationPath` instance"""
        return primitive.AnnotationPathValue(value)

    def navigation_path(self, path):
        """Returns a :class:`primitive.NavigationPath` instance"""
        return primitive.NavigationPropertyPathValue(path)

    def property_path(self, value):
        """Returns a :class:`primitive.PropertyPath` instance"""
        return primitive.PropertyPathValue(value)

    # TODO: word
    # TODO: phrase


data.Value.Evaluator = Evaluator
