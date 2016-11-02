#! /usr/bin/env python

import random
import math

from . import core
from . import variables
from ..pep8 import old_method
from ..py2 import (
    dict_keys,
    dict_values,
    range3,
    uempty)
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi


class Expression(core.QTIElement):

    """Abstract class for all expression elements."""

    @old_method('Evaluate')
    def evaluate(self, state):
        """Evaluates this expression in the context of the session *state*."""
        raise NotImplementedError("Evaluation of %s" % self.__class__.__name__)

    def integer_or_template_ref(self, state, value):
        """Given a value of type integerOrTemplateRef this method returns the
        corresponding integer by looking up the value, if necessary, in
        *state*.  If value is a variable reference to a variable with NULL
        value then None is returned."""
        ref = core.GetTemplateRef(value)
        if ref:
            if state.IsTemplate(ref):
                v = state[ref]
                if isinstance(v, variables.IntegerValue):
                    return v.value
                else:
                    raise core.ProcessingError(
                        "Bad reference: %s is not an integer variable" % ref)
            else:
                raise core.ProcessingError(
                    "Bad reference: %s is not a template variable" % ref)
        else:
            return xsi.integer_from_str(value)

    def float_or_template_ref(self, state, value):
        """Given a value of type floatOrTemplateRef this method returns the
        corresponding float by looking up the value, if necessary, in
        *state*.  If value is a variable reference to a variable with NULL
        value then None is returned."""
        ref = core.GetTemplateRef(value)
        if ref:
            if state.IsTemplate(ref):
                v = state[ref]
                if isinstance(v, variables.FloatValue):
                    return v.value
                else:
                    raise core.ProcessingError(
                        "Bad reference: %s is not a float variable" % ref)
            else:
                raise core.ProcessingError(
                    "Bad reference: %s is not a template variable" % ref)
        else:
            return xsi.double_from_str(value)

    def string_or_template_ref(self, state, value):
        """Given a value of type stringOrTemplateRef this method returns the
        corresponding string by looking up the value, if necessary, in
        *state*.  If value is a variable reference to a variable with NULL
        value then None is returned.  Note that unlike the integer and float
        expansions this expansion will not raise an error if *value* is a
        syntactically valid reference to a non-existent template variable, as
        per this condition in the specification.

                "if a string attribute appears to be a reference to a template
                variable but there is no variable with the given name it should
                be treated simply as string value"
        """
        ref = core.GetTemplateRef(value)
        if ref:
            if state.IsTemplate(ref):
                v = state[ref]
                if isinstance(v, variables.StringValue):
                    return v.value
                else:
                    raise core.ProcessingError(
                        "Bad reference: %s is not a string variable" % ref)
            else:
                return value
        else:
            return value


class BaseValue(Expression):

    """The simplest expression returns a single value from the set defined by
    the given baseType
    ::

            <xsd:attributeGroup name="baseValue.AttrGroup">
                    <xsd:attribute name="baseType" type="baseType.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:complexType name="baseValue.Type">
                    <xsd:simpleContent>
                            <xsd:extension base="xsd:string">
                                    <xsd:attributeGroup
                                    ref="baseValue.AttrGroup"/>
                            </xsd:extension>
                    </xsd:simpleContent>
            </xsd:complexType>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'baseValue')
    XMLATTR_baseType = (
        'baseType',
        variables.BaseType.from_str_lower,
        variables.BaseType.to_str)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.baseType = variables.BaseType.string

    def evaluate(self, state):
        return variables.SingleValue.NewValue(self.baseType, self.get_value())


class Variable(Expression):

    """This expression looks up the value of an itemVariable that has been
    declared in a corresponding variableDeclaration or is one of the built-in
    variables::

            <xsd:attributeGroup name="variable.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                    use="required"/>
                    <xsd:attribute name="weightIdentifier"
                    type="identifier.Type" use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'variable')
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_weightIdentifier = (
        'weightIdentifier', core.ValidateIdentifier, lambda x: x)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.identifier = ''
        self.weightIdentifier = None

    def evaluate(self, state):
        try:
            return state[self.identifier]
        except KeyError:
            raise core.ProcessingError(
                "%s has not been declared" % self.identifier)


class Default(Expression):

    """This expression looks up the declaration of an itemVariable and returns
    the associated defaultValue or NULL if no default value was declared::

            <xsd:attributeGroup name="default.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'default')
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.identifier = ''

    def evaluate(self, state):
        try:
            state.GetDeclaration(self.identifier)
            return state[self.identifier + ".DEFAULT"]
        except KeyError:
            raise core.ProcessingError(
                "%s has not been declared" % self.identifier)


class Correct(Expression):

    """This expression looks up the declaration of a response variable and
    returns the associated correctResponse or NULL if no correct value was
    declared::

            <xsd:attributeGroup name="correct.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'correct')
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.identifier = ''

    def evaluate(self, state):
        try:
            d = state.GetDeclaration(self.identifier)
            if isinstance(d, variables.ResponseDeclaration):
                return state[self.identifier + ".CORRECT"]
            elif state.IsResponse(self.identifier):
                raise core.ProcessingError(
                    "Can't get the correct value of a built-in response %s" %
                    self.identifier)
            else:
                raise core.ProcessingError(
                    "%s is not a response variable" % self.identifier)
        except KeyError:
            raise core.ProcessingError(
                "%s has not been declared" % self.identifier)


class MapResponse(Expression):

    """This expression looks up the value of a response variable and then
    transforms it using the associated mapping, which must have been declared.
    The result is a single float::

            <xsd:attributeGroup name="mapResponse.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'mapResponse')
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.identifier = ''

    def evaluate(self, state):
        try:
            d = state.GetDeclaration(self.identifier)
            if isinstance(d, variables.ResponseDeclaration):
                if d.Mapping is None:
                    raise core.ProcessingError(
                        "%s has no mapping" % self.identifier)
                return d.Mapping.MapValue(state[self.identifier])
            elif state.IsResponse(self.identifier):
                raise core.ProcessingError(
                    "Can't map built-in response %s" % self.identifier)
            else:
                raise core.ProcessingError(
                    "%s is not a response variable" % self.identifier)
        except KeyError:
            raise core.ProcessingError(
                "%s has not been declared" % self.identifier)


class MapResponsePoint(Expression):

    """This expression looks up the value of a response variable that must be of
    base-type point, and transforms it using the associated areaMapping::

            <xsd:attributeGroup name="mapResponsePoint.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'mapResponsePoint')
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.identifier = ''

    def evaluate(self, state):
        try:
            d = state.GetDeclaration(self.identifier)
            if isinstance(d, variables.ResponseDeclaration):
                if d.baseType is not variables.BaseType.point:
                    raise core.ProcessingError(
                        "%s does not have point type" % self.identifier)
                elif d.AreaMapping is None:
                    raise core.ProcessingError(
                        "%s has no areaMapping" % self.identifier)
                width, height = d.get_stage_dimensions()
                return d.AreaMapping.MapValue(
                    state[
                        self.identifier],
                    width,
                    height)
            elif state.IsResponse(self.identifier):
                raise core.ProcessingError(
                    "Can't map built-in response %s" % self.identifier)
            else:
                raise core.ProcessingError(
                    "%s is not a response variable" % self.identifier)
        except KeyError:
            raise core.ProcessingError(
                "%s has not been declared" % self.identifier)


class Null(Expression):

    """null is a simple expression that returns the NULL value - the null value is
    treated as if it is of any desired baseType
    ::

            <xsd:complexType name="null.Type"/>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'null')
    XMLCONTENT = xml.XMLEmpty

    def evaluate(self, state):
        return variables.Value()


class RandomInteger(Expression):

    """Selects a random integer from the specified range [min,max] satisfying
    min + step * n for some integer n::

            <xsd:attributeGroup name="randomInteger.AttrGroup">
                    <xsd:attribute name="min" type="integerOrTemplateRef.Type"
                    use="required"/>
                    <xsd:attribute name="max" type="integerOrTemplateRef.Type"
                    use="required"/>
                    <xsd:attribute name="step" type="integerOrTemplateRef.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'randomInteger')
    XMLATTR_min = 'min'
    XMLATTR_max = 'max'
    XMLATTR_step = 'step'
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.min = "0"
        self.max = None
        self.step = "1"

    def evaluate(self, state):
        min = self.integer_or_template_ref(state, self.min)
        max = self.integer_or_template_ref(state, self.max)
        step = self.integer_or_template_ref(state, self.step)
        return variables.IntegerValue(
            min +
            step *
            random.randint(
                0,
                (max -
                 min) //
                step))


class RandomFloat(Expression):

    """Selects a random float from the specified range [min,max]
    ::

            <xsd:attributeGroup name="randomFloat.AttrGroup">
                    <xsd:attribute name="min" type="floatOrTemplateRef.Type"
                    use="required"/>
                    <xsd:attribute name="max" type="floatOrTemplateRef.Type"
                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'randomFloat')
    XMLATTR_min = 'min'
    XMLATTR_max = 'max'
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.min = "0"
        self.max = None

    def evaluate(self, state):
        min = self.float_or_template_ref(state, self.min)
        max = self.float_or_template_ref(state, self.max)
        # strictly speaking, we can never return max, but due to possible
        # rounding this point is academic
        return variables.FloatValue(min + random.random() * (max - min))


class NOperator(Expression):

    """An abstract class to help implement operators which take multiple
    sub-expressions."""
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.Expression = []

    def get_children(self):
        return iter(self.Expression)

    @old_method('EvaluateChildren')
    def evaluate_children(self, state):
        """Evaluates all child expressions, returning an iterable of
        :py:class:`Value` instances."""
        for e in self.Expression:
            yield e.evaluate(state)


class UnaryOperator(Expression):

    """An abstract class to help implement unary operators."""
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        Expression.__init__(self, parent)
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression


class Multiple(NOperator):

    """The multiple operator takes 0 or more sub-expressions all of which must
    have either single or multiple cardinality::

            <xsd:group name="multiple.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'multiple')

    def evaluate(self, state):
        # We are going to recurse through the sub-expressions evaluating as we
        # go...
        base_type = None
        values = list(self.evaluate_children(state))
        vinput = []
        for v in values:
            if v.baseType is None:
                continue
            if base_type is None:
                base_type = v.baseType
            elif base_type != v.baseType:
                raise core.ProcessingError(
                    "Mixed containers are not allowed: expected %s, found %s" %
                    (variables.BaseType.to_str(base_type),
                     variables.BaseType.to_str(
                        v.baseType)))
            if not v:
                # ignore NULL
                continue
            if v.Cardinality() == variables.Cardinality.single:
                vinput.append(v.value)
            elif v.Cardinality() == variables.Cardinality.multiple:
                # apologies for the obscure code, but this turns {'x':2,'y':3}
                # into ['y', 'y', 'y', 'x', 'x']
                vinput = vinput + list(v.get_values())
            else:
                raise core.ProcessingError(
                    "Ordered or Record values not allowed in Mutiple")
        # finally we have a matching list of input values
        result = variables.MultipleContainer(base_type)
        result.set_value(vinput)
        return result


class Ordered(NOperator):

    """The multiple operator takes 0 or more sub-expressions all of which must
    have either single or multiple cardinality::

            <xsd:group name="ordered.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'ordered')

    def evaluate(self, state):
        # We are going to recurse through the sub-expressions evaluating as we
        # go...
        base_type = None
        values = list(self.evaluate_children(state))
        vinput = []
        for v in values:
            if v.baseType is None:
                continue
            if base_type is None:
                base_type = v.baseType
            elif base_type != v.baseType:
                raise core.ProcessingError(
                    "Mixed containers are not allowed: expected %s, found %s" %
                    (variables.BaseType.to_str(base_type),
                     variables.BaseType.to_str(
                        v.baseType)))
            if not v:
                # ignore NULL
                continue
            if v.Cardinality() == variables.Cardinality.single:
                vinput.append(v.value)
            elif v.Cardinality() == variables.Cardinality.ordered:
                vinput = vinput + list(v.value)
            else:
                raise core.ProcessingError(
                    "Multiple or Record values not allowed in Ordered")
        # finally we have a matching list of input values
        result = variables.OrderedContainer(base_type)
        result.set_value(vinput)
        return result


class ContainerSize(UnaryOperator):

    """The containerSize operator takes a sub-expression with any base-type and
    either multiple or ordered cardinality::

            <xsd:group name="containerSize.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'containerSize')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        if value.Cardinality() == variables.Cardinality.ordered:
            if value:
                return variables.IntegerValue(len(value.value))
            else:
                return variables.IntegerValue(0)
        elif value.Cardinality() == variables.Cardinality.multiple:
            if value:
                # multiple containers are kept as a mapping to value
                # frequencies
                sum = 0
                for v in dict_values(value.value):
                    sum += v
                return variables.IntegerValue(sum)
            else:
                return variables.IntegerValue(0)
        else:
            raise core.ProcessingError(
                "Ordered or Multiple value required for containerSize")


class IsNull(UnaryOperator):

    """The isNull operator takes a sub-expression with any base-type and
    cardinality
    ::

            <xsd:group name="isNull.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'isNull')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        if value:
            return variables.BooleanValue(False)
        else:
            return variables.BooleanValue(True)


class Index(UnaryOperator):

    """The index operator takes a sub-expression with an ordered container value
    and any base-type
    ::

            <xsd:attributeGroup name="index.AttrGroup">
                    <xsd:attribute name="n" type="integer.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="index.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'index')
    XMLATTR_n = ('n', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        UnaryOperator.__init__(self, parent)
        self.n = None

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        if value.Cardinality() == variables.Cardinality.ordered:
            result = variables.SingleValue.NewValue(value.baseType)
            if value:
                if self.n < 1:
                    raise core.ProcessingError(
                        "Index requires n>0, found %i" % self.n)
                elif self.n <= len(value.value):
                    result.set_value(value.value[self.n - 1])
            return result
        else:
            # wrong cardinality
            raise core.ProcessingError(
                "Index requires ordered value, found %s" %
                variables.Cardinality.to_str(
                    value.Cardinality()))


class FieldValue(UnaryOperator):

    """The field-value operator takes a sub-expression with a record container
    value. The result is the value of the field with the specified
    fieldIdentifier::

            <xsd:attributeGroup name="fieldValue.AttrGroup">
                    <xsd:attribute name="fieldIdentifier"
                    type="identifier.Type" use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="fieldValue.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'fieldValue')
    XMLATTR_fieldIdentifier = (
        'fieldIdentifier', core.ValidateIdentifier, lambda x: x)

    def __init__(self, parent):
        UnaryOperator.__init__(self, parent)
        self.fieldIdentifier = ''

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        if value.Cardinality() == variables.Cardinality.record:
            if self.fieldIdentifier in value:
                return value[self.fieldIdentifier]
            else:
                return variables.SingleValue()
        else:
            # wrong cardinality
            raise core.ProcessingError(
                "fieldValue requires record value, found %s" %
                variables.Cardinality.to_str(
                    value.Cardinality()))


class Random(UnaryOperator):

    """The random operator takes a sub-expression with a multiple or ordered
    container value and any base-type. The result is a single value randomly
    selected from the container::

            <xsd:group name="random.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'random')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        if value.Cardinality() == variables.Cardinality.ordered:
            result = variables.SingleValue.NewValue(value.baseType)
            if value:
                # randomly pick one of these values
                result.set_value(random.choice(value.value))
            return result
        elif value.Cardinality() == variables.Cardinality.multiple:
            result = variables.SingleValue.NewValue(value.baseType)
            if value:
                result.set_value(random.choice(list(value.get_values())))
            return result
        elif value.Cardinality() is None:
            return variables.SingleValue()
        else:
            # wrong cardinality
            raise core.ProcessingError(
                "Random requires multiple or ordered value, found %s" %
                variables.Cardinality.to_str(
                    value.Cardinality()))


class Member(NOperator):

    """The member operator takes two sub-expressions which must both have the
    same base-type. The first sub-expression must have single cardinality and
    the second must be a multiple or ordered container. The result is a single
    boolean with a value of true if the value given by the first sub-expression
    is in the container defined by the second sub-expression::

            <xsd:group name="member.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'member')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "Member requires two sub-expressions, found %i" % len(values))
        singleValue, containerValue = values
        if singleValue.baseType is None or containerValue.baseType is None:
            return variables.BooleanValue()
        if singleValue.baseType != containerValue.baseType:
            raise core.ProcessingError(
                "Mismatched base types for member operator")
        if singleValue.baseType == variables.BaseType.duration:
            raise core.ProcessingError(
                "Member operator must not be used on duration values")
        if singleValue and containerValue:
            if singleValue.Cardinality() != variables.Cardinality.single:
                raise core.ProcessingError(
                    "Expected single value, found %s" %
                    variables.Cardinality.to_str(
                        singleValue.Cardinality()))
            if containerValue.Cardinality() == variables.Cardinality.ordered:
                return variables.BooleanValue(
                    singleValue.value in containerValue.value)
            elif (containerValue.Cardinality() ==
                  variables.Cardinality.multiple):
                return variables.BooleanValue(
                    singleValue.value in containerValue.value)
            else:
                raise core.ProcessingError(
                    "Expected ordered or multiple value, found %s" %
                    variables.Cardinality.to_str(
                        containerValue.Cardinality()))
        else:
            return variables.BooleanValue()


class Delete(NOperator):

    """The delete operator takes two sub-expressions which must both have the
    same base-type. The first sub-expression must have single cardinality and
    the second must be a multiple or ordered container. The result is a new
    container derived from the second sub-expression with all instances of the
    first sub-expression removed::

            <xsd:group name="delete.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'delete')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "Delete requires two sub-expressions, found %i" % len(values))
        singleValue, containerValue = values
        if containerValue.baseType is None:
            return variables.Container.NewValue(
                containerValue.Cardinality(),
                singleValue.baseType)
        elif singleValue.baseType is None:
            return variables.Container.NewValue(
                containerValue.Cardinality(),
                containerValue.baseType)
        elif singleValue.baseType != containerValue.baseType:
            raise core.ProcessingError(
                "Mismatched base types for delete operator")
        if singleValue.baseType == variables.BaseType.duration:
            raise core.ProcessingError(
                "Delete operator must not be used on duration values")
        if singleValue.Cardinality() not in (variables.Cardinality.single,
                                             None):
            raise core.ProcessingError(
                "Expected single value, found %s" %
                variables.Cardinality.to_str(
                    singleValue.Cardinality()))
        if containerValue.Cardinality() not in (variables.Cardinality.ordered,
                                                variables.Cardinality.multiple,
                                                None):
            raise core.ProcessingError(
                "Expected ordered or multiple value, found %s" %
                variables.Cardinality.to_str(
                    containerValue.Cardinality()))
        result = variables.Container.NewValue(
            containerValue.Cardinality(), containerValue.baseType)
        if singleValue and containerValue:
            # we treat multiple and ordered the same, less efficient as we
            # enumerate all members
            vresult = []
            for v in containerValue.get_values():
                if singleValue.value != v:
                    vresult.append(v)
            result.set_value(vresult)
            return result
        else:
            return result


class Contains(NOperator):

    """The contains operator takes two sub-expressions which must both have the
    same base-type and cardinality -- either multiple or ordered. The result is
    a single boolean with a value of true if the container given by the first
    sub-expression contains the value given by the second sub-expression and
    false if it doesn't::

            <xsd:group name="contains.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'contains')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "Contains requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        base_type = variables.check_base_types(v1.baseType, v2.baseType)
        cardinality = variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality())
        if base_type == variables.BaseType.duration:
            raise core.ProcessingError(
                "Contains operator must not be used on duration values")
        if cardinality is None or base_type is None:
            return variables.BooleanValue()
        if v1 and v2:
            if cardinality == variables.Cardinality.ordered:
                # we use a naive implementation here as we don't expect large
                # containers
                imax = len(v2.value) - len(v1.value)
                for i in range3(imax + 1):
                    # try a match starting at i
                    match = True
                    for iv1, iv2 in zip(v1.value,
                                        v2.value[i:i + len(v1.value)]):
                        if iv1 != iv2:
                            match = False
                            break
                    if match:
                        return variables.BooleanValue(True)
                return variables.BooleanValue(False)
            elif cardinality == variables.Cardinality.multiple:
                # this is much easier to do
                match = True
                for iv1 in v1.value:
                    if v2.value.get(iv1, 0) < v1.value[iv1]:
                        # no match
                        match = False
                        break
                return variables.BooleanValue(match)
            else:
                raise core.ProcessingError(
                    "Expected ordered or multiple value, found %s" %
                    variables.Cardinality.to_str(cardinality))
        else:
            return variables.BooleanValue()


class SubString(NOperator):

    """The substring operator takes two sub-expressions which must both have an
    effective base-type of string and single cardinality. The result is a
    single boolean with a value of true if the first expression is a substring
    of the second expression and false if it isn't::

            <xsd:attributeGroup name="substring.AttrGroup">
                    <xsd:attribute name="caseSensitive" type="boolean.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="substring.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'substring')
    XMLATTR_caseSensitive = (
        'caseSensitive', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        NOperator.__init__(self, parent)
        self.caseSensitive = True

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "substring requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        variables.check_base_types(
            v1.baseType, v2.baseType, variables.BaseType.string)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            if self.caseSensitive:
                return variables.BooleanValue(v1.value in v2.value)
            else:
                return variables.BooleanValue(
                    v1.value.lower() in v2.value.lower())
        else:
            return variables.BooleanValue()


class Not(UnaryOperator):

    """The not operator takes a single sub-expression with a base-type of
    boolean and single cardinality. The result is a single boolean with a value
    obtained by the logical negation of the sub-expression's value::

            <xsd:group name="not.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'not')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.boolean)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value:
            return variables.BooleanValue(not value.value)
        else:
            return variables.BooleanValue()


class And(NOperator):

    """The and operator takes one or more sub-expressions each with a base-type
    of boolean and single cardinality. The result is a single boolean which is
    true if all sub-expressions are true and false if any of them are false::

            <xsd:group name="and.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'and')

    def evaluate(self, state):
        # We are going to recurse through the sub-expressions evaluating as we
        # go...
        values = list(self.evaluate_children(state))
        variables.check_cardinalities(variables.Cardinality.single,
                                      *[x.Cardinality() for x in values])
        variables.check_base_types(variables.BaseType.boolean,
                                   *[x.baseType for x in values])
        result = True
        for v in values:
            if v.value is False:
                return variables.BooleanValue(False)
            elif v.value is None:
                result = None
        return variables.BooleanValue(result)


class Or(NOperator):

    """The or operator takes one or more sub-expressions each with a base-type
    of boolean and single cardinality. The result is a single boolean which is
    true if any of the sub-expressions are true and false if all of them are
    false::

            <xsd:group name="or.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'or')

    def evaluate(self, state):
        # We are going to recurse through the sub-expressions evaluating as we
        # go...
        values = list(self.evaluate_children(state))
        variables.check_cardinalities(variables.Cardinality.single,
                                      *[x.Cardinality() for x in values])
        variables.check_base_types(variables.BaseType.boolean,
                                   *[x.baseType for x in values])
        result = False
        for v in values:
            if v.value:
                return variables.BooleanValue(True)
            elif v.value is None:
                result = None
        return variables.BooleanValue(result)


class AnyN(NOperator):

    """The anyN operator takes one or more sub-expressions each with a base-type
    of boolean and single cardinality. The result is a single boolean which is
    true if at least min of the sub-expressions are true and at most max of the
    sub-expressions are true::

            <xsd:attributeGroup name="anyN.AttrGroup">
                    <xsd:attribute name="min" type="integerOrTemplateRef.Type"
                    use="required"/>
                    <xsd:attribute name="max" type="integerOrTemplateRef.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="anyN.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'anyN')
    XMLATTR_min = 'min'
    XMLATTR_max = 'max'

    def __init__(self, parent):
        NOperator.__init__(self, parent)
        self.min = None
        self.max = None

    def evaluate(self, state):
        # We are going to recurse through the sub-expressions evaluating as we
        # go...
        min = self.integer_or_template_ref(state, self.min)
        max = self.integer_or_template_ref(state, self.max)
        values = list(self.evaluate_children(state))
        variables.check_cardinalities(variables.Cardinality.single,
                                      *[x.Cardinality() for x in values])
        variables.check_base_types(variables.BaseType.boolean,
                                   *[x.baseType for x in values])
        ntrue = nnull = 0
        for v in values:
            if v.value:
                ntrue += 1
            elif v.value is None:
                nnull += 1
        # The hard part is figuring out what to return!
        if ntrue >= min:
            # could be True
            if ntrue > max:
                # we overshot
                result = False
            elif ntrue + nnull > max:
                # we could still overshoot
                result = None
            else:
                result = True
        elif ntrue + nnull >= min:
            # we could still be True
            result = None
        else:
            result = False
        return variables.BooleanValue(result)


class Match(NOperator):

    """The match operator takes two sub-expressions which must both have the
    same base-type and cardinality. The result is a single boolean with a value
    of true if the two expressions represent the same value and false if they
    do not::

            <xsd:group name="match.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'match')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "Match requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        try:
            return variables.BooleanValue(v1 == v2)
        except variables.NullResult as null:
            return null.value


class StringMatch(NOperator):

    """The stringMatch operator takes two sub-expressions which must have single
    and a base-type of string. The result is a single boolean with a value of
    true if the two strings match::

            <xsd:attributeGroup name="stringMatch.AttrGroup">
                    <xsd:attribute name="caseSensitive" type="boolean.Type"
                    use="required"/>
                    <xsd:attribute name="substring" type="boolean.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="stringMatch.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'stringMatch')
    XMLATTR_caseSensitive = (
        'caseSensitive', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_substring = ('substring', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        NOperator.__init__(self, parent)
        self.caseSensitive = True
        self.substring = None

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "stringMatch requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        variables.check_base_types(
            v1.baseType, v2.baseType, variables.BaseType.string)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            if not self.caseSensitive:
                v1v = v1.value.lower()
                v2v = v2.value.lower()
            else:
                v1v = v1.value
                v2v = v2.value
            if self.substring:
                return variables.BooleanValue(v1v in v2v)
            else:
                return variables.BooleanValue(v1v == v2v)
        else:
            return variables.BooleanValue()


class PatternMatch(UnaryOperator):

    """The patternMatch operator takes a sub-expression which must have single
    cardinality and a base-type of string. The result is a single boolean with
    a value of true if the sub-expression matches the regular expression given
    by pattern and false if it doesn't::

            <xsd:attributeGroup name="patternMatch.AttrGroup">
                    <xsd:attribute name="pattern"
                    type="stringOrTemplateRef.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="patternMatch.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'patternMatch')
    XMLATTR_pattern = 'pattern'

    def __init__(self, parent):
        UnaryOperator.__init__(self, parent)
        self.pattern = uempty

    def evaluate(self, state):
        pattern = self.string_or_template_ref(state, self.pattern)
        value = self.Expression.evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.string)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value:
            try:
                re = xsi.RegularExpression(pattern)
                return variables.BooleanValue(re.match(value.value))
            except xsi.RegularExpressionError:
                # illegal regular expression results in NULL
                return variables.BooleanValue()
        else:
            return variables.BooleanValue()


class ToleranceMode(xsi.Enumeration):

    """When comparing two floating point numbers for equality it is often
    desirable to have a tolerance to ensure that spurious errors in scoring are
    not introduced by rounding errors. The tolerance mode determines whether
    the comparison is done exactly, using an absolute range or a relative
    range::

            <xsd:simpleType name="toleranceMode.Type">
                    <xsd:restriction base="xsd:NMTOKEN">
                            <xsd:enumeration value="absolute"/>
                            <xsd:enumeration value="exact"/>
                            <xsd:enumeration value="relative"/>
                    </xsd:restriction>
            </xsd:simpleType>

    Defines constants for the above modes.  Usage example::

            ToleranceMode.exact

    The default value is exact::

            ToleranceMode.DEFAULT == ToleranceMode.exact

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'absolute': 1,
        'exact': 2,
        'relative': 3
    }
    aliases = {
        None: 'exact'
    }


class Equal(NOperator):

    """The equal operator takes two sub-expressions which must both have single
    cardinality and have a numerical base-type. The result is a single boolean
    with a value of true if the two expressions are numerically equal and false
    if they are not::

            <xsd:attributeGroup name="equal.AttrGroup">
                    <xsd:attribute name="toleranceMode"
                                   type="toleranceMode.Type" use="required"/>
                    <xsd:attribute name="tolerance" use="optional">
                            <xsd:simpleType>
                                    <xsd:list
                                    itemType="floatOrTemplateRef.Type"/>
                            </xsd:simpleType>
                    </xsd:attribute>
                    <xsd:attribute name="includeLowerBound" type="boolean.Type"
                    use="optional"/>
                    <xsd:attribute name="includeUpperBound" type="boolean.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="equal.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'equal')
    XMLATTR_toleranceMode = (
        'toleranceMode',
        ToleranceMode.from_str_lower,
        ToleranceMode.to_str)
    XMLATTR_tolerance = 'tolerance'
    XMLATTR_includeLowerBound = (
        'includeLowerBound', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_includeUpperBound = (
        'includeUpperBound', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        NOperator.__init__(self, parent)
        self.toleranceMode = ToleranceMode.exact
        self.tolerance = []
        self.includeLowerBound = True
        self.includeUpperBound = True

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "equal requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            if self.toleranceMode == ToleranceMode.exact:
                return variables.BooleanValue(v1v == v2v)
            else:
                if len(self.tolerance) == 0:
                    raise core.ProcessingError(
                        "Inexact equal test requires specificed tolerance.")
                t0 = self.float_or_template_ref(state, self.tolerance[0])
                if len(self.tolerance) > 1:
                    t1 = self.float_or_template_ref(state, self.tolerance[1])
                else:
                    t1 = t0
                if self.toleranceMode == ToleranceMode.absolute:
                    lower_bound = v1v - t0
                    upper_bound = v1v + t1
                else:
                    # relative
                    lower_bound = v1v * (1 - t0 / 100.0)
                    upper_bound = v1v * (1 + t1 / 100.0)
                if self.includeUpperBound:
                    if self.includeLowerBound:
                        result = (v2v >= lower_bound and v2v <= upper_bound)
                    else:
                        result = (v2v > lower_bound and v2v <= upper_bound)
                else:
                    if self.includeLowerBound:
                        result = (v2v >= lower_bound and v2v < upper_bound)
                    else:
                        result = (v2v > lower_bound and v2v < upper_bound)
                return variables.BooleanValue(result)
        else:
            return variables.BooleanValue()


class RoundingMode(xsi.Enumeration):

    """Numbers are rounded to a given number of significantFigures or
    decimalPlaces::

            <xsd:simpleType name="roundingMode.Type">
                    <xsd:restriction base="xsd:NMTOKEN">
                            <xsd:enumeration value="decimalPlaces"/>
                            <xsd:enumeration value="significantFigures"/>
                    </xsd:restriction>
            </xsd:simpleType>

    Defines constants for the above modes.  Usage example::

            RoundingMode.decimalPlaces

    The default value is significantFigures::

            RoundingMode.DEFAULT == RoundingMode.significantFigures

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'decimalPlaces': 1,
        'significantFigures': 2
    }
    aliases = {
        None: 'significantFigures'
    }


class EqualRounded(NOperator):

    """The equalRounded operator takes two sub-expressions which must both have
    single cardinality and have a numerical base-type. The result is a single
    boolean with a value of true if the two expressions are numerically equal
    after rounding and false if they are not::

            <xsd:attributeGroup name="equalRounded.AttrGroup">
                    <xsd:attribute name="roundingMode" type="roundingMode.Type"
                    use="required"/>
                    <xsd:attribute name="figures"
                                   type="integerOrTemplateRef.Type"
                                   use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="equalRounded.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                       minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'equalRounded')
    XMLATTR_roundingMode = (
        'roundingMode', RoundingMode.from_str, RoundingMode.to_str)
    XMLATTR_figures = 'figures'

    def __init__(self, parent):
        NOperator.__init__(self, parent)
        self.roundingMode = RoundingMode.DEFAULT
        self.figures = None

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "equalRounded requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            figures = self.integer_or_template_ref(state, self.figures)
            if self.roundingMode == RoundingMode.decimalPlaces:
                return variables.BooleanValue(
                    xsi.decimal_to_str(
                        v1v,
                        figures,
                        False) == xsi.decimal_to_str(
                        v2v,
                        figures,
                        False))
            else:
                # for sig fig, we need to use the double form
                return variables.BooleanValue(
                    xsi.double_to_str(
                        v1v,
                        figures -
                        1) == xsi.double_to_str(
                        v2v,
                        figures -
                        1))
        else:
            return variables.BooleanValue()


class Inside(UnaryOperator, core.ShapeElementMixin):

    """The inside operator takes a single sub-expression which must have a
    baseType of point. The result is a single boolean with a value of true if
    the given point is inside the area defined by shape and coords. If the
    sub-expression is a container the result is true if any of the points are
    inside the area::

            <xsd:attributeGroup name="inside.AttrGroup">
                    <xsd:attribute name="shape" type="shape.Type"
                    use="required"/>
                    <xsd:attribute name="coords" type="coords.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="inside.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'inside')

    def __init__(self, parent):
        UnaryOperator.__init__(self, parent)
        core.ShapeElementMixin.__init__(self)

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.point)
        if value.Cardinality() == variables.Cardinality.single:
            if value:
                return variables.BooleanValue(
                    self.TestPoint(
                        value.value,
                        None,
                        None))
            else:
                return variables.BooleanValue()
        elif value.Cardinality() in (variables.Cardinality.ordered,
                                     variables.Cardinality.multiple):
            if value:
                if value.Cardinality() == variables.Cardinality.multiple:
                    vlist = list(dict_keys(value.value))
                else:
                    vlist = value.value
                for value in vlist:
                    if self.TestPoint(value, None, None):
                        return variables.BooleanValue(True)
                return variables.BooleanValue(False)
            else:
                return variables.BooleanValue()
        elif value.Cardinality() is None:
            return variables.BooleanValue()
        else:
            raise core.ProcessingError("Record values not allowed in Inside")


class LT(NOperator):

    """The lt operator takes two sub-expressions which must both have single
    cardinality and have a numerical base-type. The result is a single boolean
    with a value of true if the first expression is numerically less than the
    second and false if it is greater than or equal to the second::

            <xsd:group name="lt.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'lt')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "lt requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            return variables.BooleanValue(v1v < v2v)
        else:
            return variables.BooleanValue()


class GT(NOperator):

    """The gt operator takes two sub-expressions which must both have single
    cardinality and have a numerical base-type. The result is a single boolean
    with a value of true if the first expression is numerically greater than
    the second and false if it is less than or equal to the second::

            <xsd:group name="gt.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'gt')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "gt requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            return variables.BooleanValue(v1v > v2v)
        else:
            return variables.BooleanValue()


class LTE(NOperator):

    """The lte operator takes two sub-expressions which must both have single
    cardinality and have a numerical base-type. The result is a single boolean
    with a value of true if the first expression is numerically less than or
    equal to the second and false if it is greater than the second::

            <xsd:group name="lte.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'lte')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "lte requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            return variables.BooleanValue(v1v <= v2v)
        else:
            return variables.BooleanValue()


class GTE(NOperator):

    """The gte operator takes two sub-expressions which must both have single
    cardinality and have a numerical base-type. The result is a single boolean
    with a value of true if the first expression is numerically less than or
    equal to the second and false if it is greater than the second::

            <xsd:group name="durationGTE.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'gte')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "gte requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            return variables.BooleanValue(v1v >= v2v)
        else:
            return variables.BooleanValue()


class DurationLT(NOperator):

    """The durationLT operator takes two sub-expressions which must both have
    single cardinality and base-type duration. The result is a single boolean
    with a value of true if the first duration is shorter than the second and
    false if it is longer than (or equal) to the second::

            <xsd:group name="durationLT.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'durationLT')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "lt requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_base_types(
            v1.baseType, v2.baseType, variables.BaseType.duration)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            return variables.BooleanValue(v1v < v2v)
        else:
            return variables.BooleanValue()


class DurationGTE(NOperator):

    """The durationGTE operator takes two sub-expressions which must both have
    single cardinality and base-type duration. The result is a single boolean
    with a value of true if the first duration is longer (or equal, within the
    limits imposed by truncation) than the second and false if it is shorter
    than the second::

            <xsd:group name="durationGTE.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'durationGTE')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "gte requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_base_types(
            v1.baseType, v2.baseType, variables.BaseType.duration)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            # grab two floats
            v1v = float(v1.value)
            v2v = float(v2.value)
            return variables.BooleanValue(v1v >= v2v)
        else:
            return variables.BooleanValue()


class Sum(NOperator):

    """The sum operator takes 1 or more sub-expressions which all have single
    cardinality and have numerical base-types. The result is a single float or,
    if all sub-expressions are of integer type, a single integer that
    corresponds to the sum of the numerical values of the sub-expressions::

            <xsd:group name="sum.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'sum')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) < 1:
            raise core.ProcessingError(
                "sum requires at least one sub-expression, found %i" %
                len(values))
        variables.check_cardinalities(variables.Cardinality.single,
                                      *[x.cardinality() for x in values])
        base_type = variables.check_numerical_types(
            *[x.baseType for x in values])
        if base_type is None:
            # there are no values to add up, we don't know what type we are
            return variables.SingleValue()
        sum = 0
        for v in values:
            if v:
                sum = sum + v.value
            else:
                if base_type == variables.BaseType.float:
                    return variables.FloatValue()
                else:
                    return variables.IntegerValue()
        if base_type == variables.BaseType.float:
            return variables.FloatValue(float(sum))
        else:
            # sum will still be of type integer at this point
            return variables.IntegerValue(sum)


class Product(NOperator):

    """The product operator takes 1 or more sub-expressions which all have
    single cardinality and have numerical base-types. The result is a single
    float or, if all sub-expressions are of integer type, a single integer that
    corresponds to the product of the numerical values of the sub-expressions::

            <xsd:group name="product.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'product')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) < 1:
            raise core.ProcessingError(
                "product requires at least one sub-expression, found %i" %
                len(values))
        variables.check_cardinalities(variables.Cardinality.single,
                                      *[x.cardinality() for x in values])
        base_type = variables.check_numerical_types(
            *[x.baseType for x in values])
        if base_type is None:
            # there are no values to multiply, we don't know what type we are
            return variables.SingleValue()
        product = 1
        for v in values:
            if v:
                product = product * v.value
            else:
                if base_type == variables.BaseType.float:
                    return variables.FloatValue()
                else:
                    return variables.IntegerValue()
        if base_type == variables.BaseType.float:
            return variables.FloatValue(float(product))
        else:
            # sum will still be of type integer at this point
            return variables.IntegerValue(product)


class Subtract(NOperator):

    """The subtract operator takes 2 sub-expressions which all have single
    cardinality and numerical base-types. The result is a single float or, if
    both sub-expressions are of integer type, a single integer that corresponds
    to the first value minus the second::

            <xsd:group name="subtract.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'subtract')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "subtract requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        base_type = variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if base_type is None:
            # there are no values to subtract, we don't know what type we are
            return variables.SingleValue()
        if v1 and v2:
            # grab two floats
            if base_type == variables.BaseType.float:
                v1v = float(v1.value)
                v2v = float(v2.value)
                return variables.FloatValue(v1v - v2v)
            else:
                return variables.IntegerValue(v1.value - v2.value)
        else:
            if base_type == variables.BaseType.float:
                return variables.FloatValue()
            else:
                return variables.IntegerValue()


class Divide(NOperator):

    """The divide operator takes 2 sub-expressions which both have single
    cardinality and numerical base-types. The result is a single float that
    corresponds to the first expression divided by the second expression::

            <xsd:group name="divide.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'divide')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "divide requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            v1v = float(v1.value)
            v2v = float(v2.value)
            try:
                return variables.FloatValue(v1v / v2v)
            except ZeroDivisionError:
                # if [the second value] is zero or the resulting value is
                # outside the value set defined by float (not including
                # positive and negative infinity) then the operator should
                # result in NULL
                return variables.FloatValue()
        else:
            return variables.FloatValue()


class Power(NOperator):

    """The power operator takes 2 sub-expression which both have single
    cardinality and numerical base-types. The result is a single float that
    corresponds to the first expression raised to the power of the second::

            <xsd:group name="power.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'power')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "power requires two sub-expressions, found %i" % len(values))
        v1, v2 = values
        variables.check_numerical_types(v1.baseType, v2.baseType)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            v1v = float(v1.value)
            v2v = float(v2.value)
            try:
                return variables.FloatValue(math.pow(v1v, v2v))
            except ValueError:
                # If the resulting value is outside the value set defined by
                # float (not including positive and negative infinity) then the
                # operator shall result in NULL
                return variables.FloatValue()
        else:
            return variables.FloatValue()


class IntegerDivide(NOperator):

    """The integer divide operator takes 2 sub-expressions which both have
    single cardinality and base-type integer. The result is the single integer
    that corresponds to the first expression (x) divided by the second
    expression (y) rounded down to the greatest integer (i) such that
    i<=(x/y)::

            <xsd:group name="integerDivide.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'integerDivide')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "integerDivide requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        variables.check_base_types(
            v1.baseType, v2.baseType, variables.BaseType.integer)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            try:
                return variables.IntegerValue(v1.value // v2.value)
            except ZeroDivisionError:
                return variables.IntegerValue()
        else:
            return variables.IntegerValue()


class IntegerModulus(NOperator):

    """The integer modulus operator takes 2 sub-expressions which both have
    single cardinality and base-type integer. The result is the single integer
    that corresponds to the remainder when the first expression (x) is divided
    by the second expression (y). If z is the result of the corresponding
    integerDivide operator then the result is x-z*y::

            <xsd:group name="integerModulus.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="2" maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'integerModulus')

    def evaluate(self, state):
        values = list(self.evaluate_children(state))
        if len(values) != 2:
            raise core.ProcessingError(
                "integerModulus requires two sub-expressions, found %i" %
                len(values))
        v1, v2 = values
        variables.check_base_types(
            v1.baseType, v2.baseType, variables.BaseType.integer)
        variables.check_cardinalities(
            v1.Cardinality(), v2.Cardinality(), variables.Cardinality.single)
        if v1 and v2:
            try:
                return variables.IntegerValue(v1.value % v2.value)
            except ZeroDivisionError:
                return variables.IntegerValue()
        else:
            return variables.IntegerValue()


class Truncate(UnaryOperator):

    """The truncate operator takes a single sub-expression which must have
    single cardinality and base-type float. The result is a value of base-type
    integer formed by truncating the value of the sub-expression towards zero::

            <xsd:group name="truncate.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'truncate')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.float)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value:
            return variables.IntegerValue(int(value.value))
        else:
            return variables.IntegerValue()


class Round(UnaryOperator):

    """The round operator takes a single sub-expression which must have single
    cardinality and base-type float. The result is a value of base-type integer
    formed by rounding the value of the sub-expression. The result is the
    integer n for all input values in the range [n-0.5,n+0.5)::

            <xsd:group name="round.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'round')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.float)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value:
            return variables.IntegerValue(int(math.floor(value.value + 0.5)))
        else:
            return variables.IntegerValue()


class IntegerToFloat(UnaryOperator):

    """The integer to float conversion operator takes a single sub-expression
    which must have single cardinality and base-type integer. The result is a
    value of base type float with the same numeric value::

            <xsd:group name="integerToFloat.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'integerToFloat')

    def evaluate(self, state):
        value = self.Expression.evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.integer)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value:
            return variables.FloatValue(float(value.value))
        else:
            return variables.FloatValue()


class CustomOperator(NOperator):

    """The custom operator provides an extension mechanism for defining
    operations not currently supported by this specification::

            <xsd:attributeGroup name="customOperator.AttrGroup">
                    <xsd:attribute name="class" type="identifier.Type"
                    use="optional"/>
                    <xsd:attribute name="definition" type="uri.Type"
                    use="optional"/>
                    <xsd:anyAttribute namespace="##other"/>
            </xsd:attributeGroup>

            <xsd:group name="customOperator.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'customOperator')
    XMLATTR_class = "customClass"
    XMLATTR_definition = 'definition'

    def __init__(self, parent):
        NOperator.__init__(self, parent)
        self.customClass = None
        self.definition = None

    def evaluate(self, state):
        raise core.ProcessingError(
            "customOperator.%s not supported" %
            (self.customClass
                if self.customClass is not None
                else "<unknown>"))
