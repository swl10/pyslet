#! /usr/bin/env python

import logging

from ..py2 import (
    is_text,
    to_text
    )
from ..rfc2396 import URI
from ..vfs import OSFilePath
from ..xml import namespace as xmlns
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi

from . import (
    data,
    errors,
    model as odata,
    names,
    primitive,
    types,
    )


PACKAGING_NAMESPACE = 'http://docs.oasis-open.org/odata/ns/edmx'
EDMX1_NAMESPACE = 'http://schemas.microsoft.com/ado/2007/06/edmx'
EDM_NAMESPACE = 'http://docs.oasis-open.org/odata/ns/edm'

_edmx_version = {
    PACKAGING_NAMESPACE: (4, 0),
    EDMX1_NAMESPACE: (1, 0)
    }


def edmx_version(ns):
    if is_text(ns):
        ns = URI.from_octets(ns)
    if not isinstance(ns, URI):
        raise TypeError
    ns = ns.canonicalize()
    return _edmx_version.get(str(ns), None)


EDM10_NAMESPACE = 'http://schemas.microsoft.com/ado/2006/04/edm'
EDM11_NAMESPACE = 'http://schemas.microsoft.com/ado/2007/05/edm'
EDM12_NAMESPACE = 'http://schemas.microsoft.com/ado/2008/01/edm'
EDM20_NAMESPACE = 'http://schemas.microsoft.com/ado/2008/09/edm'
EDM30_NAMESPACE = 'http://schemas.microsoft.com/ado/2009/11/edm'

_edm_version = {
    EDM_NAMESPACE: (4, 0),
    EDM30_NAMESPACE: (3, 0),
    EDM20_NAMESPACE: (2, 0),
    EDM12_NAMESPACE: (1, 2),
    EDM11_NAMESPACE: (1, 1),
    EDM10_NAMESPACE: (1, 0)
    }


def edm_version(ns):
    if is_text(ns):
        ns = URI.from_octets(ns)
    if not isinstance(ns, URI):
        raise TypeError
    ns = ns.canonicalize()
    return _edm_version.get(str(ns), None)


def validate_namespace(value):
    if names.QNameTable.is_namespace(value):
        return value
    else:
        raise ValueError(
            "Can't parse Namespace from :%s" % repr(value))


def validate_qualified_name(value):
    if names.QNameTable.is_namespace(value) and "." in value:
        return value
    else:
        raise ValueError(
            "Can't parse Qualified Name from :%s" % repr(value))


def type_name_from_str(value):
    """A type name is a qualified name or a Collection()

    We represent these names as a tuple of (qualified name, flag) where
    the flag is True if this is a collection."""
    if value.startswith("Collection(") and value.endswith(")"):
        qname = value[11:-1]
        collection = True
    else:
        qname = value
        collection = False
    validate_qualified_name(qname)
    return qname, collection


def type_name_to_str(value):
    qname, collection = value
    if collection:
        return "Collection(%s)" % qname
    else:
        return qname


def max_from_str(value):
    """MaxLength can be a positive integer or 'max'

    The schema disagrees with the specification here as it allows
    non-negative integers but we go with the specification and
    return 0 for 'max'."""
    if value == "max":
        return 0
    else:
        return xsi.integer_from_str(value)


def max_to_str(value):
    if value <= 0:
        return 'max'
    else:
        return xsi.integer_to_str(value)


def nonneg_variable_from_str(value):
    """Can be a non-negative integer or 'variable'

    We return -1 for 'variable'."""
    if value == "variable":
        return -1
    else:
        value = xsi.integer_from_str(value)
        if value < 0:
            raise ValueError("non-negative value required: %i" % value)
        return value


def nonneg_variable_to_str(value):
    if value < 0:
        return 'variable'
    else:
        return xsi.integer_to_str(value)


scale_from_str = nonneg_variable_from_str
scale_to_str = nonneg_variable_to_str

srid_from_str = nonneg_variable_from_str
srid_to_str = nonneg_variable_to_str


class CSDLElement(xmlns.XMLNSElement):
    XMLCONTENT = xml.ElementType.ElementContent

    def get_entity_model(self):
        edmx = self.find_parent(Edmx)
        if edmx:
            return edmx.entity_model
        else:
            return None

    def get_schema(self):
        schema = self.find_parent(Schema)
        if schema:
            return schema.get_schema()
        else:
            return None

    def get_container(self):
        container = self.find_parent(EntityContainer)
        if container:
            return container.get_container()
        else:
            return None

    def get_annotation_target(self):
        """Returns a model element suitale for annotation

        Overridden in classes that create model elements that can be
        annotated.  The default implementation returns None."""
        return None


class ReferenceContent(object):

    """Abstract mixin class for elements allowed in Reference"""
    pass


class SchemaContent(object):

    """Abstract mixin class for elements allowed in Schema"""
    pass


class EntityTypeContent(object):

    """Abstract mixin class for elements allowed in EntityType"""
    pass


class ComplexTypeContent(object):

    """Abstract mixin class for elements allowed in ComplexType"""
    pass


class NavigationPropertyContent(object):

    """Abstract mixin class for elements allowed in NavigationProperty"""
    pass


class EnumTypeContent(object):

    """Abstract mixin class for elements allowed in EnumType"""
    pass


class ActionFunctionContent(object):

    """Abstract mixin class for elements allowed in Action or Function"""
    pass


class RecordContent(object):

    """Abstract mixin class for elements allowed in Record"""
    pass


class EntityContainerContent(object):

    """Abstract mixin class for elements allowed in EntityContainer"""
    pass


class AnnotatedNavigationContent(object):

    """Abstract mixin class for elements allowed in EntitySet/Singleton"""
    pass


class FacetsMixin(object):

    XMLATTR_MaxLength = ('max_length', max_from_str, max_to_str)
    XMLATTR_Precision = ('precision', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_Scale = ('scale', scale_from_str, scale_to_str)
    XMLATTR_SRID = ('srid', srid_from_str, srid_to_str)

    def __init__(self):
        self.max_length = None
        self.precision = None
        self.scale = None           # negative value indicates variable
        self.srid = None

    def set_type_facets(self, ptype):
        # sets the facets of a primitive type based on the attribute
        # values
        changed = False
        if self.max_length is not None:
            ptype.set_max_length(self.max_length)
            changed = True
        if self.precision is not None or self.scale is not None:
            ptype.set_precision(self.precision, self.scale)
            changed = True
        if self.srid is not None:
            ptype.set_srid(self.srid)
            changed = True
        return changed

    def create_type(self, type_obj):
        if isinstance(type_obj, types.PrimitiveType):
            # add the facets to this type
            ptype = type_obj.derive_type()
            if self.set_type_facets(ptype):
                return ptype
        return type_obj


class GInlineExpressionsMixin(object):

    """Abstract class for holding attribution declarations.

    No constructor is provided as these are left to the automated
    handling of default attributes in XML elements."""

    # constant expressions
    XMLATTR_Binary = ('binary_value', primitive.BinaryValue.from_str, str)
    XMLATTR_Bool = ('bool_value', primitive.BooleanValue.from_str, str)
    XMLATTR_Date = ('date_value', primitive.DateValue.from_str, str)
    XMLATTR_DateTimeOffset = ('date_time_offset_value',
                              primitive.DateTimeOffsetValue.from_str, str)
    XMLATTR_Decimal = ('decimal_value', primitive.DecimalValue.from_str, str)
    XMLATTR_Duration = (
        'duration_value', primitive.DurationValue.from_str, str)
    XMLATTR_EnumMember = ('enum_member', names.EnumLiteral.from_xml_str,
                          names.EnumLiteral.to_xml_str)
    XMLATTR_Float = ('float_value', primitive.FloatValue.from_str, str)
    XMLATTR_Guid = ('guid_value', primitive.GuidValue.from_str, str)
    XMLATTR_Int = ('int_value', primitive.Int64Value.from_str, str)
    XMLATTR_String = ('string_value', primitive.StringValue.from_str, str)
    XMLATTR_TimeOfDay = (
        'time_of_day_value', primitive.TimeOfDayValue.from_str, str)
    # dynamic expressions
    XMLATTR_AnnotationPath = (
        'annotation_path', names.annotation_path_from_str,
        names.annotation_path_to_str)
    XMLATTR_NavigationPropertyPath = (
        'navigation_property_path', names.path_from_str, names.path_to_str)
    XMLATTR_Path = ('path', names.path_from_str, names.path_to_str)
    XMLATTR_PropertyPath = (
        'property_path', names.path_from_str, names.path_to_str)
    XMLATTR_UrlRef = ('url_ref', URI.from_octets, str)

    def get_inline_expression(self):
        result = None
        for a in (
                self.binary_value, self.bool_value, self.date_value,
                self.date_time_offset_value, self.decimal_value,
                self.duration_value, self.float_value, self.guid_value,
                self.int_value, self.string_value, self.time_of_day_value):
            if a is None:
                continue
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), to_text(a)))
            else:
                result = types.LiteralExpression(a.get_value())
        if self.enum_member:
            # the odd case of the enum_member, must be looked up
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), self.enum_member))
            result = types.LiteralExpression(self.enum_member)
        if self.annotation_path:
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), to_text(self.annotation_path)))
            result = types.APathExpression(self.annotation_path)
        if self.path:
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), to_text(self.path)))
            result = types.PathExpression(self.path)
        if self.property_path:
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), to_text(self.property_path)))
            result = types.PPathExpression(self.property_path)
        if self.navigation_property_path:
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), to_text(self.navigation_property_path)))
            result = types.NPPathExpression(self.navigation_property_path)
        if self.url_ref:
            if result is not None:
                raise errors.ModelError(
                    "Ambiguous attribute notation for Annotation (%s & %s)" %
                    (to_text(result), to_text(self.url_ref)))
            result = types.URLRefExpression(self.url_ref)
        return result


class GExpression(CSDLElement):

    """Abstract class for element expression constructs"""

    def get_expression(self):
        raise NotImplementedError(repr(self.__class__))


class Annotation(
        ActionFunctionContent,
        AnnotatedNavigationContent,
        ComplexTypeContent,
        EntityContainerContent,
        EntityTypeContent,
        EnumTypeContent,
        NavigationPropertyContent,
        ReferenceContent,
        SchemaContent,
        GInlineExpressionsMixin,
        RecordContent,
        CSDLElement):

    """Represents the Annotation element."""
    XMLNAME = (EDM_NAMESPACE, 'Annotation')

    XMLATTR_Term = ('term_qname', names.QualifiedName.from_str, to_text)
    XMLATTR_Qualifier = ('qualifier', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        # no need to initialise the *Content classes
        self.term_qname = None
        self.term = None
        self.qualifier = None
        self.Annotation = []
        self.GExpression = None
        self._targets = []

    def content_changed(self):
        if self.term_qname is None:
            raise errors.ModelError(errors.Requirement.annotation_term)
        # we will need to look up this term
        em = self.get_entity_model()
        if em is None:
            return

        def term_declared(term):
            self.term = term
            if not isinstance(term, types.Term):
                raise errors.ModelError(
                    errors.Requirement.annotation_term_declared_s %
                    to_text(self.term_qname))
            if not isinstance(self.parent, Annotations):
                target = self.parent.get_annotation_target()
                if target is not None:
                    self._targets.append((target, self.qualifier))
                else:
                    logging.warning(
                        "Ignored inline Annotation on: %s" % repr(self.parent))
            # apply the annotation only when the model is closed, this
            # is required because expressions can't be evaluated until
            # the model is complete (due to the potential for name
            # resolution of enums, paths, etc).
            em.tell_close(self.apply)

        em.qualified_tell(self.term_qname, term_declared)

    def annotate_target(self, target, qualifier=None):
        # only called when the model is already closed!
        if self.qualifier is not None:
            if qualifier is not None:
                raise errors.ModelError(
                    errors.Requirement.annotation_qualifier_s %
                    ("%s#%s" % (to_text(self.term_qname), qualifier)))
            qualifier = self.qualifier
        self._targets.append((target, qualifier))
        if self.term is not None:
            # term is already declared
            self.apply()

    def apply(self):
        # apply the contents to the annotation
        expr = self.get_inline_expression()
        if self.GExpression:
            if expr is not None:
                raise errors.ODataError(
                    "Ambiguous annotation, element notation conflicts "
                    "with inline value")
            expr = self.GExpression.get_expression()
        for target, qualifier in self._targets:
            if self.term.applies_to and \
                    target.csdl_name not in self.term.applies_to:
                raise errors.ModelError(
                    errors.Requirement.annotation_applies_s %
                    ("<%s> %s" %
                     (target.csdl_name, to_text(self.term_qname))))
            a = types.Annotation(self.term, qualifier=qualifier)
            if expr is not None:
                a.set_expression(expr)
                # does this expression work in the context of target?
                tcheck = odata.TypeChecker(target)
                atype = tcheck.evaluate(expr)
                # is atype type-compatible with the Term's type?
                if atype is not None and \
                        not self.term.type_def.compatible(atype):
                    raise errors.ModelError(
                        "Annotation %s on %s is not type compatible with term "
                        "definition (%r)" % (to_text(a.get_term_ref()),
                                             to_text(target), to_text(atype)))
            target.annotate(a)
        self._targets = []

    def get_children(self):
        for a in self.Annotation:
            yield a
        if self.GExpression:
            yield self.GExpression
        for child in super(CSDLElement, self).get_children():
            yield child


class Annotated(CSDLElement):

    """Abstract class for elements that contain only annotations"""

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.Annotation = []

    def get_children(self):
        for a in self.Annotation:
            yield a
        for child in super(Annotated, self).get_children():
            yield child


class ConstantExpression(GExpression):
    XMLCONTENT = xml.ElementType.Mixed

    def get_expression(self):
        return types.LiteralExpression(self.get_value())


class BinaryConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Binary')

    def get_value(self):
        try:
            return primitive.BinaryValue.from_str(
                super(BinaryConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_binary_s % to_text(err))


class BoolConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Bool')

    def get_value(self):
        try:
            return primitive.BooleanValue.from_str(
                super(BoolConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_bool_s % to_text(err))


class DateConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Date')

    def get_value(self):
        try:
            return primitive.DateValue.from_str(
                super(DateConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_date_s % to_text(err))


class DateTimeOffsetConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'DateTimeOffset')

    def get_value(self):
        try:
            return primitive.DateTimeOffsetValue.from_str(
                super(DateTimeOffsetConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_datetime_s % to_text(err))


class DecimalConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Decimal')

    def get_value(self):
        try:
            return primitive.DecimalValue.from_str(
                super(DecimalConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_decimal_s % to_text(err))


class DurationConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Duration')

    def get_value(self):
        try:
            return primitive.DurationValue.from_str(
                super(DurationConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_duration_s % to_text(err))


class EnumMemberConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'EnumMember')

    def __init__(self, parent):
        ConstantExpression.__init__(self, parent)
        self.enum_def = None
        self._values = []

    def get_value(self):
        value = super(EnumMemberConstant, self).get_value()
        try:
            result = names.EnumLiteral.from_xml_str(value)
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_enum_s % to_text(err))
        em = self.get_entity_model()

        def enum_check():
            # defer this check until the model closes
            try:
                em.get_enum_value(result)
            except TypeError as err:
                raise errors.ModelError(
                    errors.Requirement.annotation_enum_s % to_text(err))
            except ValueError as err:
                raise errors.ModelError(
                    errors.Requirement.annotation_enum_member_s % to_text(err))

        em.tell_close(enum_check)
        return result


class FloatConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Float')

    def get_value(self):
        try:
            return primitive.DoubleValue.from_str(
                super(FloatConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_float_s % to_text(err))


class GuidConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Guid')

    def get_value(self):
        try:
            return primitive.GuidValue.from_str(
                super(GuidConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_guid_s % to_text(err))


class IntConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Int')

    def get_value(self):
        try:
            return primitive.Int64Value.from_str(
                super(IntConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_int_s % to_text(err))


class StringConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'String')

    def get_value(self):
        return primitive.StringValue.from_str(
            super(StringConstant, self).get_value()).get_value()


class TimeOfDayConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'TimeOfDay')

    def get_value(self):
        try:
            return primitive.TimeOfDayValue.from_str(
                super(TimeOfDayConstant, self).get_value()).get_value()
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_time_s % to_text(err))


class PathExpression(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'Path')
    XMLCONTENT = xml.ElementType.Mixed

    def get_expression(self):
        return types.PathExpression(
            names.path_from_str(super(PathExpression, self).get_value()))


class AnnotationPath(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'AnnotationPath')
    XMLCONTENT = xml.ElementType.Mixed

    def get_expression(self):
        try:
            return types.APathExpression(
                names.annotation_path_from_str(self.get_value()))
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.annotation_path_s % to_text(err))


class AnnotatedExpression(GExpression):

    def __init__(self, parent):
        GExpression.__init__(self, parent)
        self.function = None
        self.Annotation = []
        self.GExpression = []   # different rules apply to num children

    def get_children(self):
        for a in self.Annotation:
            yield a
        for e in self.GExpression:
            yield e
        for child in super(AnnotatedExpression, self).get_children():
            yield child


class Apply(AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'Apply')

    XMLATTR_Function = ('function', names.QualifiedName.from_str, to_text)

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        self.function = None

    def get_expression(self):
        if not self.function:
            raise errors.ModelError(errors.Requirement.annotation_func_name)
        if self.function.namespace == "odata" and self.function.name not in (
                "concat", "fillUriTemplate", "uriEncode"):
            raise errors.ModelError(
                errors.Requirement.annotation_func_additional_s %
                to_text(self.function))
        if not self.GExpression:
            raise errors.ModelError(
                errors.Requirement.annotation_apply_expr_s %
                to_text(self.function))
        if self.function.namespace == "odata":
            fname = to_text(self.function)
        else:
            # always called on model close so should be OK
            fname = to_text(self.get_model().canonicalize_qname(self.function))
        expr = types.CallExpression(fname)
        if self.function.name == "fillUriTemplate":
            if self.GExpression:
                expr.add_operand(self.GExpression[0].get_expression())
            for e in self.GExpression[1:]:
                bind = types.BinaryExpression(types.Operator.bind)
                if not isinstance(e, LabeledElement):
                    raise errors.ModelError(
                        errors.
                        Requirement.annotation_fill_uri_template_args_s %
                        to_text(e))
                bind.add_operand(types.NameExpression(e.name))
                bind.add_operand(e.get_expression())
                expr.add_operand(bind)
        elif self.function.name == "concat":
            if len(self.GExpression) < 2:
                raise errors.ModelError(
                    errors.Requirement.annotation_concat_args_s %
                    ("%i found" % len(self.GExpression)))
            for e in self.GExpression:
                expr.add_operand(e.get_expression())
        else:
            for e in self.GExpression:
                expr.add_operand(e.get_expression())
        return expr


class CastOrIsOfExpression(FacetsMixin, AnnotatedExpression):

    XMLATTR_Type = ('type_name', names.TypeName.from_str, to_text)

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        FacetsMixin.__init__(self)
        self.type_name = None


class CastExpression(CastOrIsOfExpression):
    XMLNAME = (EDM_NAMESPACE, 'Cast')

    def get_expression(self):
        if self.type_name:
            qname, collection = self.type_name
        else:
            qname, collection = "", False
        if collection or not qname or len(self.GExpression) != 1:
            raise errors.ModelError(errors.Requirement.cast_signature)
        expr = types.CallExpression("cast")
        expr.add_operand(self.GExpression[0].get_expression())
        em = self.get_entity_model()

        def set_type(type_obj):
            # set the expression type object
            if type_obj is None or not isinstance(
                    type_obj, (types.PrimitiveType, types.ComplexType,
                               types.EnumerationType)):
                raise errors.ModelError(
                    errors.Requirement.cast_type % to_text(self.type_name))
            to_type = self.create_type(type_obj)
            expr.add_operand(types.TypeExpression(to_type))

        # we return this expression incomplete, the Type may be added
        # later when the type referred to is defined
        em.qualified_tell(qname, set_type)
        return expr


class CollectionExpression(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'Collection')

    def __init__(self, parent):
        GExpression.__init__(self, parent)
        self.GExpression = []

    def get_children(self):
        for e in self.GExpression:
            yield e
        for child in super(CollectionExpression, self).get_children():
            yield child

    def get_expression(self):
        expr = types.CollectionExpression()
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class IfExpression(AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'If')

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)

    def get_expression(self):
        expr = types.IfExpression()
        if len(self.GExpression) < 3:
            if len(self.GExpression) < 2 or \
                    not isinstance(self.parent, CollectionExpression):
                raise errors.ModelError(errors.Requirement.if_three)
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class TwoChildrenExpression(AnnotatedExpression):

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        self.GExpression = []

    def get_children(self):
        for e in self.GExpression:
            yield e
        for child in super(CollectionExpression, self).get_children():
            yield child


class EqExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Eq')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.eq)
        if len(self.GExpression) != 2:
            raise errors.ModelError(
                errors.Requirement.annotation_comparison_s %
                ("%i found" % len(self.GExpression)))
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class NeExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Ne')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.ne)
        if len(self.GExpression) != 2:
            raise errors.ModelError(
                errors.Requirement.annotation_comparison_s %
                ("%i found" % len(self.GExpression)))
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class GeExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Ge')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.ge)
        if len(self.GExpression) != 2:
            raise errors.ModelError(
                errors.Requirement.annotation_comparison_s %
                ("%i found" % len(self.GExpression)))
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class GtExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Gt')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.gt)
        if len(self.GExpression) != 2:
            raise errors.ModelError(
                errors.Requirement.annotation_comparison_s %
                ("%i found" % len(self.GExpression)))
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class LeExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Le')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.le)
        if len(self.GExpression) != 2:
            raise errors.ModelError(
                errors.Requirement.annotation_comparison_s %
                ("%i found" % len(self.GExpression)))
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class LtExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Lt')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.lt)
        if len(self.GExpression) != 2:
            raise errors.ModelError(
                errors.Requirement.annotation_comparison_s %
                ("%i found" % len(self.GExpression)))
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class AndExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'And')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.bool_and)
        if len(self.GExpression) != 2:
            raise errors.ModelError(errors.Requirement.annotation_and_or)
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class OrExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Or')

    def get_expression(self):
        expr = types.BinaryExpression(types.Operator.bool_or)
        if len(self.GExpression) != 2:
            raise errors.ModelError(errors.Requirement.annotation_and_or)
        for e in self.GExpression:
            expr.add_operand(e.get_expression())
        return expr


class OneChildExpression(AnnotatedExpression):

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        self.GExpression = None

    def get_children(self):
        if self.GExpression:
            yield self.GExpression
        for child in super(CollectionExpression, self).get_children():
            yield child


class NotExpression(OneChildExpression):
    XMLNAME = (EDM_NAMESPACE, 'Not')

    def get_expression(self):
        expr = types.UnaryExpression(types.Operator.bool_not)
        if self.GExpression is None:
            raise errors.ModelError(errors.Requirement.annotation_not)
        expr.add_operand(self.GExpression.get_expression())
        return expr


class IsOfExpression(CastOrIsOfExpression):
    XMLNAME = (EDM_NAMESPACE, 'IsOf')

    def get_expression(self):
        if self.type_name:
            qname, collection = self.type_name
        else:
            qname, collection = "", False
        if collection or not qname or len(self.GExpression) != 1:
            raise errors.ModelError(errors.Requirement.isof_test_type)
        expr = types.CallExpression("isof")
        expr.add_operand(self.GExpression[0].get_expression())
        em = self.get_entity_model()

        def set_type(type_obj):
            # set the expression type object
            if type_obj is None:
                raise errors.ModelError(
                    errors.Requirement.isof_type_scope_s %
                    to_text(self.type_name))
            test_type = self.create_type(type_obj)
            expr.add_operand(types.TypeExpression(test_type))

        # we return this expression incomplete, the Type may be added
        # later when the type referred to is defined
        em.qualified_tell(qname, set_type)
        return expr


class LabeledElement(GInlineExpressionsMixin, AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'LabeledElement')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        self.name = None
        self._labeled_expr = None

    def content_changed(self):
        if self.name is None:
            raise errors.ModelError(errors.Requirement.label_name)
        if self._labeled_expr is None:
            # we will need to declare this expression
            s = self.get_schema()
            if s:
                label = types.LabeledExpression()
                label.set_expression(self.get_expression())
                try:
                    label.declare(s, self.name)
                except errors.DuplicateNameError:
                    raise errors.DuplicateNameError(
                        errors.Requirement.type_qname_s % self.name)
                self._labeled_expr = label

    def get_expression(self):
        expr = self.get_inline_expression()
        if (len(self.GExpression) + (0 if expr is None else 1) != 1):
            raise errors.ModelError(
                errors.Requirement.label_expr_s % self.name)
        if expr is None:
            expr = self.GExpression[0].get_expression()
        return expr


class LabeledElementReference(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'LabeledElementReference')
    XMLCONTENT = xml.ElementType.Mixed

    def get_value(self):
        return names.QualifiedName.from_str(
            super(LabeledElementReference, self).get_value())

    def set_value(self, value):
        if is_text(value):
            names.QualifiedName.from_str(value)
            super(LabeledElementReference, self).set_value(value)
        elif isinstance(value, names.QualifiedName):
            super(LabeledElementReference, self).set_value(to_text(value))
        else:
            raise ValueError("<LabelElementReference> requires QualifiedName")

    def get_expression(self):
        qname = self.get_value()
        if not qname:
            raise errors.ModelError(
                errors.Requirement.label_ref_s % to_text(qname))
        expr = types.ReferenceExpression(qname)
        em = self.get_entity_model()

        def check_ref(label):
            # set the expression from the labelled item
            if not isinstance(label, types.LabeledExpression):
                raise errors.ModelError(
                    errors.Requirement.label_ref_s % to_text(qname))

        em.qualified_tell(qname, check_ref)
        return expr


class NullExpression(GExpression, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Null')

    def get_expression(self):
        return types.LiteralExpression(None)


class NavigationPropertyPath(PathExpression):
    XMLNAME = (EDM_NAMESPACE, 'NavigationPropertyPath')

    def get_expression(self):
        try:
            return types.NPPathExpression(
                names.path_from_str(self.get_value()))
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.navigation_path_s % to_text(err))


class PropertyPathExpression(PathExpression):
    XMLNAME = (EDM_NAMESPACE, 'PropertyPath')

    def get_expression(self):
        try:
            return types.PPathExpression(
                names.path_from_str(self.get_value()))
        except ValueError as err:
            raise errors.ModelError(
                errors.Requirement.property_path_s % to_text(err))


class RecordExpression(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'Record')

    XMLATTR_Type = ('type_name', validate_qualified_name, None)

    def __init__(self, parent):
        GExpression.__init__(self, parent)
        self.type_name = None
        self.RecordContent = []

    def get_children(self):
        for rc in self.RecordContent:
            yield rc
        for child in super(CSDLElement, self).get_children():
            yield child

    def get_expression(self):
        expr = types.RecordExpression()
        for e in self.RecordContent:
            if isinstance(e, Annotation):
                continue
            if not isinstance(e, PropertyValue):
                raise errors.ModelError(
                    errors.Requirement.record_args_s % to_text(e))
            bind = types.BinaryExpression(types.Operator.bind)
            bind.add_operand(types.NameExpression(e.property))
            bind.add_operand(e.get_expression())
            expr.add_operand(bind)
        return expr


class PropertyValue(RecordContent, GInlineExpressionsMixin,
                    AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'PropertyValue')

    XMLATTR_Property = ('property', names.simple_identifier_from_str, None)
    XMLATTR_Type = ('type_name', validate_qualified_name, None)

    def get_expression(self):
        expr = self.get_inline_expression()
        if (len(self.GExpression) + (0 if expr is None else 1) != 1):
            raise errors.ModelError(
                errors.Requirement.property_expr_s % self.name)
        if expr is None:
            expr = self.GExpression[0].get_expression()
        return expr


class UrlRef(OneChildExpression):
    XMLNAME = (EDM_NAMESPACE, 'UrlRef')


RESERVED_ALIASES = ("Edm", "odata", "System", "Transient")


class Edmx(CSDLElement):

    """Represents the Edmx root element."""
    XMLNAME = (PACKAGING_NAMESPACE, 'Edmx')

    XMLATTR_Version = 'version'

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.version = "4.0"
        self.Reference = []
        self.DataServices = DataServices(self)
        # a name table containing all namespaces in this model
        self.entity_model = odata.EntityModel()

    def content_changed(self):
        if self.version != "4.0":
            raise errors.ModelError(errors.Requirement.edmx_version)
        # DataServices is instantiated automatically but if the element
        # was missing during parsing it won't be closed.
        if not self.DataServices._closed:
            raise errors.ModelError(errors.Requirement.csdl_data_services)
        been_there = set()
        for r in self.Reference:
            uri = str(r.resolve_uri(r.uri))
            if uri in been_there:
                raise errors.ModelError(errors.Requirement.unique_reference)
            been_there.add(uri)
        # every model has the 'Edm' and 'odata' schemas declared
        # automatically by the EntityModel constructor but the Core and
        # Capabilities schemas should be included by Reference.  If they
        # weren't, but they've been referenced, we auto-include them (by
        # full name and alias) because there appears to be some
        # confusion over whether they need to be Referenced or not and
        # some schemas just use them as if they were also built-in.
        if self.entity_model.waiting(
                'Org.OData.Core.V1') or self.entity_model.waiting('Core'):
            core = self.entity_model.get('Org.OData.Core.V1')
            if core is None:
                core = CSDLDocument.load_core()
            self.entity_model.setdefault('Org.OData.Core.V1', core)
            self.entity_model.setdefault('Core', core)
        if self.entity_model.waiting(
                'Org.OData.Capabilities.V1') or \
                self.entity_model.waiting('Capabilities'):
            capabilities = self.entity_model.get('Org.OData.Capabilities.V1')
            if capabilities is None:
                capabilities = CSDLDocument.load_capabilities()
            self.entity_model.setdefault(
                'Org.OData.Capabilities.V1', capabilities)
            self.entity_model.setdefault('Capabilities', capabilities)
        # close the entity model
        self.entity_model.close()

    def get_children(self):
        for child in self.Reference:
            yield child
        yield self.DataServices
        for child in CSDLElement.get_children(self):
            yield child


class DataServices(CSDLElement):
    XMLNAME = (PACKAGING_NAMESPACE, 'DataServices')

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.Schema = []
        self._closed = False

    def content_changed(self):
        if self._closed:
            # if we're already closed this means we got a second element
            raise errors.ModelError(errors.Requirement.csdl_data_services)
        else:
            self._closed = True
        if not self.Schema:
            raise errors.ModelError(errors.Requirement.schemas)

    def get_children(self):
        for s in self.Schema:
            yield s
        for child in super(DataServices, self).get_children():
            yield child


class Reference(CSDLElement):
    XMLNAME = (PACKAGING_NAMESPACE, 'Reference')

    XMLATTR_Uri = ('uri', URI.from_octets, to_text)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.uri = None
        self.ref_model = None
        self.ReferenceContent = []

    def get_ref_model(self):
        if self.uri is None:
            raise errors.ModelError(errors.Requirement.reference_uri)
        if self.ref_model is None:
            ref = self.resolve_uri(self.uri)
            ref_doc = CSDLDocument(base_uri=ref)
            ref_doc.read()
            self.ref_model = ref_doc.root.entity_model
        return self.ref_model

    def content_changed(self):
        got_child = False
        for rc in self.ReferenceContent:
            if isinstance(rc, (Include, IncludeAnnotations)):
                got_child = True
        if not got_child:
            raise errors.ModelError(errors.Requirement.reference)

    def get_children(self):
        for rc in self.ReferenceContent:
            yield rc
        for child in super(Reference, self).get_children():
            yield child


class Include(ReferenceContent, CSDLElement):
    XMLNAME = (PACKAGING_NAMESPACE, 'Include')

    XMLATTR_Namespace = ('namespace', validate_namespace, None)
    XMLATTR_Alias = ('alias', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.namespace = None
        self.alias = None

    def content_changed(self):
        if self.namespace is None:
            raise errors.ModelError(errors.Requirement.include_namespace)
        ref_model = self.parent.get_ref_model()
        try:
            ns = ref_model[self.namespace]
            # check that ns is not just referenced in ref_model
            if not ns.is_owned_by(ref_model):
                raise KeyError
        except KeyError:
            raise errors.ModelError(
                errors.Requirement.include_schema_s % self.namespace)
        em = self.get_entity_model()
        if em is not None:
            try:
                if self.alias is not None:
                    if self.alias in RESERVED_ALIASES:
                        raise errors.ModelError(
                            errors.Requirement.reserved_namespace_s %
                            self.namespace)
                    em[self.alias] = ns
            except errors.DuplicateNameError as err:
                raise errors.DuplicateNameError(
                    errors.Requirement.unique_namespace_s % to_text(err))
            try:
                # cf Schema, we do not change the owner of ns here
                em[ns.name] = ns
            except errors.DuplicateNameError:
                raise errors.DuplicateNameError(
                    errors.Requirement.unique_include_s % ns.name)


class IncludeAnnotations(ReferenceContent, CSDLElement):
    XMLNAME = (PACKAGING_NAMESPACE, 'IncludeAnnotations')

    XMLATTR_TermNamespace = ('term_namespace', validate_namespace, None)
    XMLATTR_Qualifier = ('qualifier', names.simple_identifier_from_str, None)
    XMLATTR_TargetNamespace = ('target_namespace', validate_namespace, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.term_namespace = None
        self.qualifier = None
        self.target_namespace = None

    def content_changed(self):
        if self.term_namespace is None:
            raise errors.ModelError(errors.Requirement.term_namespace)


class Schema(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Schema')

    XMLATTR_Namespace = ('namespace', validate_namespace, None)
    XMLATTR_Alias = ('alias', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.namespace = None
        self.alias = None
        self.SchemaContent = []
        self._schema = None

    def get_schema(self):
        if self._schema is None:
            if self.namespace is None:
                raise errors.ModelError(errors.Requirement.schema_name)
            if self.namespace in RESERVED_ALIASES:
                raise errors.ModelError(
                    errors.Requirement.reserved_schema_s % self.namespace)
            self._schema = odata.Schema()
            em = self.get_entity_model()
            # This is the first declaration of this schema, it sets the
            # owning namespace; cf Include that merely makes a reference.
            try:
                self._schema.declare(em, self.namespace)
            except errors.DuplicateNameError:
                raise errors.DuplicateNameError(
                    errors.Requirement.schema_unique_s % self.namespace)
            if self.alias is not None:
                if self.alias in RESERVED_ALIASES:
                    raise errors.ModelError(
                        errors.Requirement.reserved_alias_s % self.alias)
                try:
                    em[self.alias] = self._schema
                except errors.DuplicateNameError:
                    # what are we colliding with?
                    dup = em[self.alias]
                    if self.alias == dup.name:
                        raise errors.ModelError(
                            errors.Requirement.unique_namespace_s % self.alias)
                    else:
                        # dup is an alias itself
                        raise errors.ModelError(
                            errors.Requirement.unique_alias_s % self.alias)
        return self._schema

    def get_annotation_target(self):
        return self.get_schema()

    def content_changed(self):
        logging.debug("Closing schema: %s" % self.namespace)
        s = self.get_schema()
        s.close()

    def get_children(self):
        for sc in self.SchemaContent:
            yield sc
        for child in super(Schema, self).get_children():
            yield child


class Type(CSDLElement):

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self._type_obj = None

    def get_type(self):
        if self._type_obj is None:
            if self.name is None:
                if isinstance(self, EntityType):
                    raise errors.ModelError(errors.Requirement.et_name)
                elif isinstance(self, ComplexType):
                    raise errors.ModelError(errors.Requirement.ct_name)
                elif isinstance(self, EnumType):
                    raise errors.ModelError(errors.Requirement.ent_name)
                else:
                    raise ValueError("Unnamed type (%s)" % repr(self))
            self._type_obj = self.get_type_obj()
            s = self.get_schema()
            if s is not None:
                try:
                    self._type_obj.declare(s, self.name)
                except errors.DuplicateNameError:
                    dup = s[self.name]
                    if isinstance(dup, types.NominalType):
                        raise errors.DuplicateNameError(
                            errors.Requirement.type_qname_s % self.name)
                    else:
                        raise errors.DuplicateNameError(
                            errors.Requirement.unique_schema_child_s %
                            self.name)
        return self._type_obj

    def content_changed(self):
        # trigger declaration
        self.get_type()

    def get_annotation_target(self):
        return self.get_type()


class DerivableType(Type):

    XMLATTR_BaseType = ('base_type_name', validate_qualified_name, None)
    XMLATTR_Abstract = ('abstract', xsi.boolean_from_str, xsi.boolean_to_str)
    # we move OpenType here as it is identical in the two base classes
    XMLATTR_OpenType = ('open_type', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        Type.__init__(self, parent)
        self.base_type_name = None
        self.abstract = False
        # the schema provides for a default of False here but we
        # actually want to distinguish between False and not specified.
        # The specification implies that if not specified the value is
        # inherited from the base type.
        self.open_type = None
        self._dependencies = 1

    def add_dependency(self):
        self._dependencies += 1

    def remove_dependency(self):
        self._dependencies -= 1
        if self._dependencies <= 0:
            # that was the last dependency, close this type
            t = self.get_type()
            t.close()

    def content_changed(self):
        t = self.get_type()
        if self.base_type_name is not None:
            em = self.get_entity_model()
            self.add_dependency()
            em.qualified_tell(
                self.base_type_name, self._set_base_type_callback)
        elif isinstance(t, types.EntityType):
            t.set_base(odata.edm['EntityType'])
        elif isinstance(t, types.ComplexType):
            t.set_base(odata.edm['ComplexType'])
        # we start with a single dependency: waiting for this method!
        self.remove_dependency()

    def _set_base_type_callback(self, base_type_obj):
        if base_type_obj is None:
            raise errors.ModelError("%s is not declared" % self.base_type_name)

        def _set_base():
            t = self.get_type()
            t.set_base(base_type_obj)
            self.remove_dependency()

        # we need to wait for our base to be closed before we can be
        # closed
        base_type_obj.tell_close(_set_base)


class ComplexType(SchemaContent, DerivableType):
    XMLNAME = (EDM_NAMESPACE, 'ComplexType')

    def __init__(self, parent):
        DerivableType.__init__(self, parent)
        self.ComplexTypeContent = []

    def get_type_obj(self):
        t = types.ComplexType(value_type=data.ComplexValue)
        t.set_abstract(self.abstract)
        if self.open_type is not None:
            t.set_open_type(self.open_type)
        return t

    def get_children(self):
        for cc in self.ComplexTypeContent:
            yield cc
        for child in super(ComplexType, self).get_children():
            yield child


class EntityType(SchemaContent, DerivableType):
    XMLNAME = (EDM_NAMESPACE, 'EntityType')

    XMLATTR_HasStream = ('has_stream', xsi.boolean_from_str,
                         xsi.boolean_to_str)

    def __init__(self, parent):
        DerivableType.__init__(self, parent)
        self.has_stream = False
        self.EntityTypeContent = []

    def get_type_obj(self):
        t = types.EntityType(value_type=data.EntityValue)
        t.set_abstract(self.abstract)
        if self.open_type is not None:
            t.set_open_type(self.open_type)
        return t

    def get_children(self):
        for sc in self.EntityTypeContent:
            yield sc
        for child in super(EntityType, self).get_children():
            yield child


class Key(EntityTypeContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Key')

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.PropertyRef = []

    def get_children(self):
        for p in self.PropertyRef:
            yield p
        for child in super(Key, self).get_children():
            yield child

    def content_changed(self):
        t = self.get_type_context()
        if t is not None:
            if not self.PropertyRef:
                raise errors.ModelError(
                    errors.Requirement.et_key_ref_s % t.qname)
            for pr in self.PropertyRef:
                # convert the path into an array
                if pr.name is None:
                    raise errors.ModelError(
                        errors.Requirement.key_name_s % t.qname)
                t.add_key(pr.name, pr.alias)

    def get_type_context(self):
        if not isinstance(self.parent, EntityType):
            return None
        return self.parent.get_type()


class PropertyRef(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'PropertyRef')

    XMLATTR_Name = ('name', names.path_from_str, names.path_to_str)
    XMLATTR_Alias = ('alias', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.alias = None


class PropertyFacetsMixin(FacetsMixin):

    """Mixin class for property facets

    In the schema this TPropertyFacetAttributes is always used
    immediately after TFacetAttributes as if it were a dervied type.
    For convenience we actually make it a derived class here."""
    XMLATTR_Unicode = ('unicode', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self):
        super(PropertyFacetsMixin, self).__init__()
        self.unicode = None

    def set_type_facets(self, ptype):
        # overridden to add unicode facet
        super(PropertyFacetsMixin, self).set_type_facets(ptype)
        if self.unicode is not None:
            ptype.set_unicode(self.unicode)


class CommonPropertyMixin(PropertyFacetsMixin):

    """Mixin class for common property attributes

    The specification and schema disagree here.  In the schema the
    Nullable property defaults to true but the specification goes to
    some lengths to explain that a missing Nullable property on a
    property with a Collection type means that it is unknown whether or
    not the collection may contain null values.  We go with the
    specification here and handle the defaulting of Nullable (for
    non-Collection properties) later."""
    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_DefaultValue = 'default_value'

    def __init__(self):
        PropertyFacetsMixin.__init__(self)
        self.name = None
        self.type_name = None
        self.type_obj = None
        self.nullable = None
        self.default_value = None


class Property(ComplexTypeContent, EntityTypeContent, CommonPropertyMixin,
               Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Property')

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        CommonPropertyMixin.__init__(self)
        self._p = None

    def content_changed(self):
        self.get_property()

    def get_property(self):
        if self._p is not None:
            return self._p
        if self.name is None:
            raise errors.ModelError(errors.Requirement.property_name)
        if self.type_name is None:
            raise errors.ModelError(
                errors.Requirement.property_type_s % self.name)
        qname, collection = self.type_name
        if self.nullable is None and not collection:
            # default nullability
            self.nullable = True
        t = self.get_type_context()
        if t is not None:
            self._p = types.Property()
            self._p.set_nullable(self.nullable)
            try:
                self._p.declare(t, self.name)
            except errors.DuplicateNameError:
                raise errors.DuplicateNameError(
                    errors.Requirement.property_unique_s %
                    ("%s:%s" % (t.name, self.name)))
            except ValueError as err:
                # we already validated name as a simple identifier
                raise errors.ModelError(err)
            # look-up the type_name, will trigger type binding now or later
            em = self.get_entity_model()
            # delay closure of this type until we've resolved the type
            # of the property and (in the case of complex types) that
            # type is closed.  This ensures that circular complex types
            # are caught properly and that all property paths of closed
            # entity types can be resolved, even if they traverse
            # complex types.
            self.parent.add_dependency()
            em.qualified_tell(qname, self.set_type)
        return self._p

    def get_annotation_target(self):
        return self.get_property()

    def set_type(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(
                type_obj, (types.PrimitiveType, types.ComplexType)):
            raise errors.ModelError(
                errors.Requirement.property_type_declared_s %
                self.type_name[0])
        qname, collection = self.type_name
        ptype = self.create_type(type_obj)
        self._p.set_type(ptype, collection)
        if isinstance(type_obj, types.EnumerationType):

            def enumeration_callback():
                if not collection and self.default_value is not None:
                    default_value = ptype()
                    default_value.value_from_str(self.default_value)
                    self._p.set_default(default_value)
                self.parent.remove_dependency()

            type_obj.tell_close(enumeration_callback)
        elif isinstance(type_obj, types.PrimitiveType):
            if not collection and self.default_value is not None:
                try:
                    default_value = ptype.value_type.from_str(
                        self.default_value)
                except ValueError as err:
                    raise errors.ModelError(
                        errors.Requirement.primitive_default_s % to_text(err))
                self._p.set_default(default_value)
            # declaration complete (primitive and collection of primitive)
            self.parent.remove_dependency()
        else:

            def complex_callback():
                # ComplexType has been closed, remove dependency so
                # that our parent type can close
                self.parent.remove_dependency()

            type_obj.tell_close(complex_callback)

    def get_type_context(self):
        if not isinstance(self.parent, (ComplexType, EntityType)):
            return None
        return self.parent.get_type()


class NavigationProperty(ComplexTypeContent, EntityTypeContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'NavigationProperty')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_Partner = ('partner', names.path_from_str, names.path_to_str)
    XMLATTR_ContainsTarget = ('contains_target', xsi.boolean_from_str,
                              xsi.boolean_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.type_name = None
        self.nullable = None
        self.partner = None
        self.contains_target = False
        self.NavigationPropertyContent = []
        self._np = None

    def content_changed(self):
        if self.name is None:
            raise errors.ModelError(errors.Requirement.nav_name)
        if self.type_name is None:
            raise errors.ModelError(errors.Requirement.nav_type_s % self.name)
        self._np = types.NavigationProperty()
        qname, collection = self.type_name
        if collection:
            if self.nullable is not None:
                raise errors.ModelError(
                    errors.Requirement.nav_collection_exists_s % self.name)
        elif self.nullable is None:
            # default nullability
            self.nullable = True
        self._np.set_nullable(self.nullable)
        t = self.get_type_context()
        if t is not None:
            if self.partner is not None and \
                    not isinstance(t, types.EntityType):
                raise errors.ModelError(
                    errors.Requirement.nav_partner_complex_s %
                    ("%s/%s" % (t.name, self.name)))
            try:
                self._np.declare(t, self.name)
            except errors.DuplicateNameError:
                raise errors.DuplicateNameError(
                    errors.Requirement.property_unique_s %
                    ("%s/%s" % (t.name, self.name)))
            except ValueError as err:
                raise errors.ModelError(err)
        # look-up the type_name, will trigger type binding now or later
        em = self.get_entity_model()
        em.qualified_tell(qname, self._set_type_callback)
        if self.partner is not None:
            # we need to resolve the partner path, wait for all
            # declarations to have been made.
            em.tell_close(self._set_partner_callback)

    def _set_type_callback(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(type_obj, types.EntityType):
            raise errors.ModelError(
                errors.Requirement.nav_type_resolved_s % self.name)
        self._np.set_type(type_obj, self.type_name[1], self.contains_target)
        # now wait for both the containing type and the target type
        # to be closed before resolving referential constraints
        t = self.get_type_context()
        names.NameTable.tell_all_closed(
            (t, type_obj), self._resolve_constraints)

    def _resolve_constraints(self):
        for item in self.NavigationPropertyContent:
            if isinstance(item, ReferentialConstraint):
                item.add_constraint(self._np)
            elif isinstance(item, OnDelete):
                item.add_action(self._np)

    def _set_partner_callback(self):
        em = self.get_entity_model()
        try:
            # the path resolution takes care of one of our constraints
            target = self._np.entity_type.resolve_nppath(
                self.partner, em, follow_containment=False)
        except errors.PathError as err:
            raise errors.ModelError(
                errors.Requirement.nav_partner_path_s %
                ("%s, %s" % (self.name, to_text(err))))
        t = self.get_type_context()
        if not isinstance(t, types.EntityType):
            # Unexpected: partners can only be specified for entity types
            raise errors.ModelError("Expected EntityType: %s" % t.qname)
        if not t.is_derived_from(target.entity_type):
            raise errors.ModelError(
                errors.Requirement.nav_partner_type_s % self.name)
        if target.partner is not None and target.partner is not self._np:
            raise errors.ModelError(
                errors.Requirement.nav_partner_bidirection_s % self.name)
        if self._np.containment:
            if t.is_derived_from(self._np.entity_type) or \
                    self._np.entity_type.is_derived_from(t):
                # this relationship is recursive
                if target.collection:
                    raise errors.ModelError(
                        errors.Requirement.nav_rcontains_s % self.name)
                if not target.nullable:
                    raise errors.ModelError(
                        errors.Requirement.nav_rcontains_s % self.name)
            else:
                if target.nullable:
                    raise errors.ModelError(
                        errors.Requirement.nav_nrcontains_s % self.name)
        if target.containment:
            # Our entity type is contained by the target
            t.set_contained()
        self._np.set_partner(target)

    def get_children(self):
        for npc in self.NavigationPropertyContent:
            yield npc
        for child in super(NavigationProperty, self).get_children():
            yield child

    def get_type_context(self):
        if not isinstance(self.parent, (ComplexType, EntityType)):
            return None
        return self.parent.get_type()


class ReferentialConstraint(NavigationPropertyContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'ReferentialConstraint')

    XMLATTR_Property = ('property', names.path_from_str, names.path_to_str)
    XMLATTR_ReferencedProperty = ('referenced_property', names.path_from_str,
                                  names.path_to_str)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        self.property = None
        self.referenced_property = None

    def add_constraint(self, np):
        # the dependent entity is the one defining the navigation
        # property, there's an odd case where the navigation property is
        # defined on a complex type because we don't know which entities
        # that type will be included in so can't possible resolve the
        # Property path based on the *entity*, we must assume the intent
        # of the specification was to have the property path to be
        # resolved relative to the structured type that contains the
        # navigation property only.
        if self.property is None:
            raise odata.errors.ModelError(
                errors.Requirement.refcon_property_s % np.qname)
        if self.referenced_property is None:
            raise odata.errors.ModelError(
                errors.Requirement.refcon_refprop_s % np.qname)
        np.add_constraint(self.property, self.referenced_property)


class OnDelete(NavigationPropertyContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'OnDelete')

    XMLATTR_Action = ('action', odata.OnDeleteAction.from_str, str)
    # enumeration: Cascade, None, SetDefault, SetNull

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        self.action = None

    def add_action(self, np):
        if self.action is None:
            raise odata.errors.ModelError(errors.Requirement.ondelete_value)
        np.add_action(self.action)


class TypeDefinition(SchemaContent, PropertyFacetsMixin, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'TypeDefinition')

    XMLATTR_Name = ('type_name', names.simple_identifier_from_str, None)
    XMLATTR_UnderlyingType = ('underlying_type', validate_qualified_name, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        PropertyFacetsMixin.__init__(self)
        self.type_name = None
        self._type_obj = None
        self.underlying_type = None     # must be a primitive type

    def content_changed(self):
        self.get_type()

    def get_type(self):
        # trigger declaration
        if self._type_obj is None:
            if self.type_name is None:
                raise errors.ModelError(errors.Requirement.td_name)
            if self.underlying_type is None:
                raise errors.ModelError(
                    errors.Requirement.td_qname_s % self.type_name)
            em = self.get_entity_model()
            # we are only interested in the Edm namespace which will
            # already be loaded, no need wait...
            base_type = em.qualified_get(self.underlying_type)
            if not isinstance(base_type, types.PrimitiveType):
                raise errors.ModelError(
                    errors.Requirement.td_qname_s % self.type_name)
            # Must be in the Edm namespace
            if not base_type.nametable() is odata.edm:
                raise errors.ModelError(
                    errors.Requirement.td_redef_s % self.type_name)
            self._type_obj = base_type.derive_type()
            if self.max_length is not None:
                self._type_obj.set_max_length(self.max_length)
            if self.unicode is not None:
                self._type_obj.set_unicode(self.unicode)
            if self.precision is not None or self.scale is not None:
                self._type_obj.set_precision(self.precision, self.scale)
            if self.srid is not None:
                self._type_obj.set_srid(self.srid)
            s = self.get_schema()
            if s is not None:
                try:
                    self._type_obj.declare(s, self.type_name)
                except errors.DuplicateNameError:
                    dup = s[self.type_name]
                    if isinstance(dup, types.NominalType):
                        raise errors.DuplicateNameError(
                            errors.Requirement.type_qname_s % self.type_name)
                    else:
                        raise errors.DuplicateNameError(
                            errors.Requirement.unique_schema_child_s %
                            self.type_name)
        return self._type_obj

    def get_annotation_target(self):
        return self.get_type()


class EnumType(SchemaContent, Type):
    XMLNAME = (EDM_NAMESPACE, 'EnumType')

    XMLATTR_IsFlags = ('is_flags', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_UnderlyingType = ('underlying_type', type_name_from_str,
                              type_name_to_str)

    def __init__(self, parent):
        Type.__init__(self, parent)
        self.is_flags = None
        self.underlying_type = None     # must be a primitive type
        self.EnumTypeContent = []
        self._ent = None

    def get_children(self):
        for etc in self.EnumTypeContent:
            yield etc
        for child in super(EnumType, self).get_children():
            yield child

    def content_changed(self):
        t = self.get_type()
        # we're done with declaring this type
        t.close()

    def get_type_obj(self):
        if self._ent is not None:
            return self._ent
        if self.underlying_type is not None:
            em = self.get_entity_model()
            qname, collection = self.underlying_type
            if collection:
                raise errors.ModelError(
                    errors.Requirement.ent_type_s % self.underlying_type)
            # we are only interested in the Edm namespace which will
            # already be loaded, no need wait...
            base_type = em.qualified_get(qname)
            if base_type is None:
                raise errors.ModelError(errors.Requirement.ent_type_s % qname)
        else:
            base_type = None
        self._ent = odata.EnumerationValue.new_type()
        # types.EnumerationType(
        #    value_type=odata.EnumerationValue, underlying_type=base_type)
        if base_type:
            self._ent.set_underlying_type(base_type)
        if self.is_flags:
            self._ent.set_is_flags()
        return self._ent


class Member(EnumTypeContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Member')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Value = ('value', xsi.integer_from_str, xsi.integer_to_str)
    # long

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        self.name = None
        self.value = None

    def content_changed(self):
        if self.name is None:
            raise errors.ModelError(errors.Requirement.ent_member_name)
        m = types.Member()
        m.value = self.value
        t = self.get_type_context()
        if t is not None:
            try:
                m.declare(t, self.name)
            except errors.DuplicateNameError:
                raise errors.DuplicateNameError(
                    errors.Requirement.ent_member_unique_s %
                    ("%s:%s" % (t.name, self.name)))

    def get_type_context(self):
        if not isinstance(self.parent, EnumType):
            return None
        return self.parent.get_type()


class ReturnType(FacetsMixin, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'ReturnType')

    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        FacetsMixin.__init__(self)
        self.type_name = None
        self.nullable = None

    def content_changed(self):
        if not isinstance(self.parent, ActionFunction):
            return
        c = self.parent.get_callable()
        if c is not None:
            em = self.get_entity_model()
            qname, collection = self.type_name

            def set_return_type(type_obj):
                type_def = self.create_type(type_obj)
                if collection:
                    type_def = type_def.collection_type()
                c.set_return_type(type_def)
                if self.nullable is not None:
                    c.set_nullable(self.nullable)
                self.parent.remove_dependency()

            self.parent.add_dependency()
            em.qualified_tell(qname, set_return_type)


class ActionFunction(CSDLElement):

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.ActionFunctionContent = []
        self.ReturnType = None
        self._dependencies = 1
        self._callable = None

    def add_dependency(self):
        self._dependencies += 1

    def remove_dependency(self):
        self._dependencies -= 1
        if self._dependencies <= 0:
            # that was the last dependency, declare this callable
            c = self.get_callable()
            # do not accept any more parameters
            c.close()
            s = self.get_schema()
            if s is not None:
                c.declare_overload(s, self.name)

    def get_children(self):
        for afc in self.ActionFunctionContent:
            yield afc
        if self.ReturnType:
            yield self.ReturnType
        for child in super(EnumType, self).get_children():
            yield child

    def get_callable(self):
        raise NotImplementedError

    def content_changed(self):
        self.get_callable()
        self.remove_dependency()


class Parameter(ActionFunctionContent, FacetsMixin, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Parameter')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.type_name = None
        self.nullable = None
        self._parameter = None

    def get_parameter(self):
        if self._parameter is None:
            if self.name is None:
                raise errors.ModelError("Parameter with no name")
            c = self.parent.get_callable()
            self._parameter = odata.Parameter()
            c.add_parameter(self._parameter, self.name)
        return self._parameter

    def content_changed(self):
        if not isinstance(self.parent, ActionFunction):
            return
        p = self.get_parameter()
        c = self.parent.get_callable()
        if c is not None:
            em = self.get_entity_model()
            qname, collection = self.type_name

            def set_type(type_obj):
                type_def = self.create_type(type_obj)
                p.set_type(type_def, collection)
                if self.nullable is not None:
                    p.set_nullable(self.nullable)
                self.parent.remove_dependency()

            self.parent.add_dependency()
            em.qualified_tell(qname, set_type)


class Action(SchemaContent, ActionFunction):
    XMLNAME = (EDM_NAMESPACE, 'Action')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_EntitySetPath = (
        'entity_set_path', names.path_from_str, names.path_to_str)
    XMLATTR_IsBound = ('is_bound', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        ActionFunction.__init__(self, parent)
        self.name = None
        self.entity_set_path = None
        self.is_bound = False

    def get_callable(self):
        if self._callable is None:
            if self.name is None:
                raise errors.ModelError("Action requires Name")
            self._callable = odata.Action(value_type=odata.CallableType)
            self._callable.set_is_bound(self.is_bound)
            if self.entity_set_path:
                self._callable.set_entity_set_path(self.entity_set_path)
        return self._callable


class Function(SchemaContent, ActionFunction):
    XMLNAME = (EDM_NAMESPACE, 'Function')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_EntitySetPath = (
        'entity_set_path', names.path_from_str, names.path_to_str)
    XMLATTR_IsBound = ('is_bound', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_IsComposable = ('is_composable', xsi.boolean_from_str,
                            xsi.boolean_to_str)

    def __init__(self, parent):
        ActionFunction.__init__(self, parent)
        # ReturnType is required
        self.ReturnType = ReturnType(self)
        self.name = None
        self.entity_set_path = None
        self.is_bound = False
        self.is_composable = False

    def get_callable(self):
        if self._callable is None:
            if self.name is None:
                raise errors.ModelError("Function requires Name")
            self._callable = odata.Function(value_type=odata.CallableValue)
            self._callable.set_is_bound(self.is_bound)
            if self.entity_set_path:
                self._callable.set_entity_set_path(self.entity_set_path)
            self._callable.set_is_composable(self.is_composable)
        return self._callable


class Term(SchemaContent, FacetsMixin, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Term')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_BaseTerm = ('base_term', validate_qualified_name, None)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_DefaultValue = 'default_value'
    XMLATTR_AppliesTo = 'applies_to'    # TODO: enumeration

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        self.name = None
        self.type_name = None
        self.base_term = None
        self.nullable = None
        self.default_value = None
        self.applies_to = None
        self._term = None

    def content_changed(self):
        self.get_term()

    def get_term(self):
        if self._term is not None:
            return self._term
        if self.name is None:
            raise errors.ModelError(errors.Requirement.term_name)
        if self.type_name is None:
            raise errors.ModelError(errors.Requirement.term_type_s % self.name)
        em = self.get_entity_model()
        s = self.get_schema()
        qname, collection = self.type_name
        if self.nullable is None and not collection:
            # default nullability
            self.nullable = True
        self._term = types.Term()
        self._term.set_nullable(self.nullable)
        if self.applies_to:
            self._term.set_applies_to(self.applies_to.split())

        def set_type(type_obj):
            # delay declaration of the term until the type is defined
            # this ensures that annotations that refer to this
            # definition can use declaration as a trigger
            if type_obj is None or not isinstance(
                    type_obj, (types.PrimitiveType, types.StructuredType,
                               types.EnumerationType)):
                raise errors.ModelError(
                    errors.Requirement.term_type_s %
                    ("%s not declared" % qname))
            ttype = self.create_type(type_obj)
            if collection:
                ttype = ttype.collection_type()
            self._term.set_type(ttype)
            if isinstance(type_obj, types.PrimitiveType):
                if not collection and self.default_value is not None:
                    try:
                        default_value = ttype()
                        default_value.assign(
                            ttype.value_type.from_str(self.default_value))
                    except ValueError as err:
                        raise errors.ModelError(
                            errors.Requirement.term_prim_default_s %
                            to_text(err))
                    self._term.set_default(default_value)
                if s is not None:
                    # declare this Term within the namespace
                    self._term.declare(s, self.name)
            else:
                # structured types and enumerations must be closed
                # before we declare this term so that we can create
                # values from them straight away (default enum values
                # also require the enum to be closed!)

                def type_closed():
                    if isinstance(ttype, types.EnumerationType):
                        if self.default_value is not None:
                            default_value = ttype.value_from_str(
                                self.default_value)
                            self._term.set_default(default_value)
                    if s is not None:
                        self._term.declare(s, self.name)

                type_obj.tell_close(type_closed)

        def set_base(term_obj):
            if term_obj is None or not isinstance(term_obj, types.Term):
                raise errors.ModelError(
                    errors.Requirement.term_base_s %
                    ("%s not declared" % self.base_term))
            self._term.set_base(term_obj)
            # now set the underlying type
            em.qualified_tell(qname, set_type)

        if self.base_term:
            em.qualified_tell(self.base_term, set_base)
        else:
            em.qualified_tell(qname, set_type)
        return self._term

    def get_annotation_target(self):
        return self.get_term()


class Annotations(SchemaContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Annotations')

    XMLATTR_Target = 'target'   # Edm.PropertyPath is just a string
    XMLATTR_Qualifier = ('qualifier', names.simple_identifier_from_str, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        # at least one annotation required!
        self.target = None
        self.qualifier = None

    def content_changed(self):
        if not len(self.Annotation):
            raise errors.ModelError(errors.Requirement.annotations_children)
        if not self.target:
            raise errors.ModelError(errors.Requirement.annotations_target)
        em = self.get_entity_model()

        def resolve_target():
            # called then the model is closed
            path = self.target.split("/")
            target = em.qualified_get(path[0])
            container_target = None
            if target is None:
                raise errors.ModelError(
                    errors.Requirement.annotations_target_s % self.target)
            for p in path[1:]:
                if isinstance(target, types.Property):
                    # swap the property for the properties underlying
                    # type
                    target = target.structural_type
                elif isinstance(target, types.NavigationProperty):
                    # swap the navigation property for the underlying
                    # entity type
                    target = target.entity_type
                elif isinstance(target, (odata.EntitySet, odata.Singleton)):
                    # swap EntitySet/Singleton for the underlying entity
                    # type BUT record this part of the target because
                    # the annotation is stored in a special way in this
                    # case
                    container_target = target
                    target = target.entity_type
                try:
                    if "." in p:
                        # this is a type cast segment
                        if isinstance(types.StructuredType):
                            new_target = em.qualified_get(p)
                            if new_target.is_derived_from(target):
                                target = new_target
                                continue
                        raise KeyError("Bad type cast %s" % p)
                    elif isinstance(
                            target,
                            (odata.ActionOverload, odata.FunctionOverload)):
                        # applies to all overloads defining the parameter
                        new_target = []
                        for t in target.callables:
                            param = t.get(p, None)
                            if param:
                                new_target.append(param)
                    elif isinstance(
                            target,
                            (types.StructuredType, odata.EntityContainer,
                             types.EnumerationType)):
                        target = target[p]
                    else:
                        raise KeyError("Bad segment %s" % p)
                except KeyError as e:
                    raise errors.ModelError(
                        errors.Requirement.annotations_target_s %
                        ("%s:%s" % (self.target, to_text(e))))
            # now apply the annotations to this target
            if isinstance(
                    target,
                    (odata.ActionOverload, odata.FunctionOverload)):
                # expand to a list of Functions and Actions
                target = [c for c in target.callables]
            elif not isinstance(target, list):
                # simply the following loops
                target = [target]
            logging.info("Target: %s", repr(target))
            for a in self.Annotation:
                for t in target:
                    if container_target is not None:
                        # Annotations for properties and navigation
                        # properties of singletons and entity sets
                        # override annotations on the declarations in
                        # the structured type
                        raise NotImplementedError
                    else:
                        a.annotate_target(t, self.qualifier)

        em.tell_close(resolve_target)


class EntityContainer(SchemaContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'EntityContainer')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Extends = ('extends', validate_qualified_name, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.extends = None
        self.EntityContainerContent = []
        self._container = None

    def get_children(self):
        for ec in self.EntityContainerContent:
            yield ec
        for child in super(EntityContainer, self).get_children():
            yield child

    def content_changed(self):
        # force declaration of container
        ec = self.get_container()
        if self.extends is not None:
            em = self.get_entity_model()
            em.qualified_tell(
                self.extends, self._set_extends_callback)
        else:
            # safe to close the container now
            ec.close()

    def _set_extends_callback(self, extends_obj):
        if extends_obj is None:
            raise errors.ModelError("%s is not declared" % self.extends)
        ec = self.get_container()
        try:
            ec.set_extends(extends_obj)
        except errors.DuplicateNameError as err:
            raise errors.DuplicateNameError(
                "[%s] TBC" % to_text(err))
        # close this container when the 'base' container closes
        extends_obj.tell_close(ec.close)

    def get_container(self):
        if self._container is None:
            self._container = odata.EntityContainer()
            schema = self.get_schema()
            try:
                self._container.declare(schema, self.name)
            except errors.DuplicateNameError:
                raise errors.ModelError(
                    errors.Requirement.container_name_s % self.name)
        return self._container


class AnnotatedNavigation(CSDLElement):

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.AnnotatedNavigationContent = []

    def get_children(self):
        for ec in self.AnnotatedNavigationContent:
            yield ec
        for child in super(AnnotatedNavigation, self).get_children():
            yield child


class EntitySet(EntityContainerContent, AnnotatedNavigation):
    XMLNAME = (EDM_NAMESPACE, 'EntitySet')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_EntityType = ('type_name', validate_qualified_name, None)
    XMLATTR_IncludeInServiceDocument = (
        'include_in_service_document', xsi.boolean_from_str,
        xsi.boolean_to_str)

    def __init__(self, parent):
        AnnotatedNavigation.__init__(self, parent)
        self.name = None
        self.type_name = None
        self._type_obj = None
        self.include_in_service_document = True
        self._es = None

    def content_changed(self):
        self.get_entity_set()

    def get_entity_set(self):
        if self._es is not None:
            return self._es
        if self.name is None:
            raise errors.ModelError(errors.Requirement.entity_set_name)
        if self.type_name is None:
            raise errors.ModelError(
                errors.Requirement.entity_set_type_s % self.name)
        container = self.get_container()
        if container is not None:
            # declare this EntitySet within the container
            self._es = odata.EntitySet()
            try:
                self._es.declare(container, self.name)
            except errors.DuplicateNameError as err:
                raise errors.ModelError(
                    errors.Requirement.container_names_s % to_text(err))
        self._es.set_in_service(self.include_in_service_document)
        # look-up the type_name, will trigger type binding now or later
        em = self.get_entity_model()
        em.qualified_tell(self.type_name, self._find_type_callback)
        return self._es

    def _find_type_callback(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(type_obj, types.EntityType):
            raise errors.ModelError(
                errors.Requirement.entity_set_type_s %
                ("%s(%s)" % (self.name, self.type_name)))
        self._type_obj = type_obj
        type_obj.tell_close(self._set_type_callback)

    def _set_type_callback(self):
        self._es.set_type(self._type_obj)

    def get_annotation_target(self):
        return self.get_entity_set()


class NavigationPropertyBinding(AnnotatedNavigationContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'NavigationPropertyBinding')

    XMLATTR_Path = ('path', names.path_from_str, names.path_to_str)
    XMLATTR_Target = ('target', names.path_from_str, names.path_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.path = None
        self.target = None

    def content_changed(self):
        """Adds this binding to the parent entity set"""
        if self.path is None:
            raise errors.ModelError(
                errors.Requirement.navbinding_path_s % "None")
        if self.target is None:
            raise errors.ModelError(
                errors.Requirement.navbinding_target_s % "None")
        if not isinstance(self.parent, EntitySet):
            return None
        entity_set = self.parent.get_entity_set()
        entity_set.add_navigation_binding(self.path, self.target)


class ActionFunctionImportMixin(object):

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_EntitySet = ('entity_set', names.path_from_str, names.path_to_str)
    XMLATTR_IncludeInServiceDocument = (
        'include_in_service_document', xsi.boolean_from_str,
        xsi.boolean_to_str)

    def __init__(self):
        self.name = None
        self.entity_set = None
        self.include_in_service_document = False
        self._import = None

    def content_changed(self):
        self.get_import()


class ActionImport(EntityContainerContent, ActionFunctionImportMixin,
                   Annotated):
    XMLNAME = (EDM_NAMESPACE, 'ActionImport')

    XMLATTR_Action = ('action', validate_qualified_name, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        ActionFunctionImportMixin.__init__(self)
        self.action = None

    def get_import(self):
        if self._import is not None:
            return self._import
        if self.name is None:
            raise errors.ModelError("Action requires Name")
        if self.action is None:
            raise errors.ModelError("Action requires action")
        container = self.get_container()
        if container is not None:
            # declare this ActionImport within the container
            self._import = odata.ActionImport()
            try:
                self._import.declare(container, self.name)
            except errors.DuplicateNameError as err:
                raise errors.ModelError(
                    errors.Requirement.container_names_s % to_text(err))
        self._import.set_in_service(self.include_in_service_document)
        em = self.get_entity_model()

        def found_callable(callable):
            if not isinstance(callable, odata.ActionOverload):
                # not the right sort of thing
                raise errors.ModelError("Expected Action")
            schema = callable.nametable()

            def check_callable():
                action_def = callable.get_unbound_action()
                if action_def is None:
                    raise errors.ModelError(
                        "ActionImport require unbound Action")
                self._import.set_action(action_def)

            schema.tell_close(check_callable)

        em.qualified_tell(self.action, found_callable)
        return self._import


class FunctionImport(EntityContainerContent, ActionFunctionImportMixin,
                     Annotated):
    XMLNAME = (EDM_NAMESPACE, 'FunctionImport')

    XMLATTR_Function = ('function', validate_qualified_name, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        ActionFunctionImportMixin.__init__(self)
        self.function = None

    def get_import(self):
        if self._import is not None:
            return self._import
        if self.name is None:
            raise errors.ModelError("Function requires Name")
        if self.function is None:
            raise errors.ModelError("Function requires function")
        container = self.get_container()
        if container is not None:
            # declare this FunctionImport within the container
            self._import = odata.FunctionImport()
            try:
                self._import.declare(container, self.name)
            except errors.DuplicateNameError as err:
                raise errors.ModelError(
                    errors.Requirement.container_names_s % to_text(err))
        self._import.set_in_service(self.include_in_service_document)
        em = self.get_entity_model()

        def found_callable(callable):
            if not isinstance(callable, odata.FunctionOverload):
                # not the right sort of thing
                raise errors.ModelError("Expected Function")
            schema = callable.nametable()

            def check_callable():
                if not callable.is_unbound():
                    raise errors.ModelError(
                        "FunctionImport requires unbound Function")
                self._import.set_function_overload(callable)

            schema.tell_close(check_callable)

        em.qualified_tell(self.function, found_callable)
        return self._import


class Singleton(EntityContainerContent, AnnotatedNavigation):
    XMLNAME = (EDM_NAMESPACE, 'Singleton')

    XMLATTR_Name = ('name', names.simple_identifier_from_str, None)
    XMLATTR_Type = ('type_name', validate_qualified_name, None)

    def __init__(self, parent):
        AnnotatedNavigation.__init__(self, parent)
        self.name = None
        self.type_name = None
        self._s = None
        self._type_obj = None

    def content_changed(self):
        if self.name is None:
            raise errors.ModelError(errors.Requirement.singleton_name)
        if self.type_name is None:
            raise errors.ModelError(
                errors.Requirement.singleton_type_s % self.name)
        container = self.get_container()
        if container is not None:
            # declare this Singleton within the container
            self._s = odata.Singleton()
            try:
                self._s.declare(container, self.name)
            except errors.DuplicateNameError as err:
                raise errors.ModelError(
                    errors.Requirement.container_names_s % to_text(err))
        # look-up the type_name, will trigger type binding now or later
        em = self.get_entity_model()
        em.qualified_tell(self.type_name, self._find_type_callback)

    def _find_type_callback(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(type_obj, types.EntityType):
            raise errors.ModelError(
                errors.Requirement.singleton_type_s %
                ("%s(%s)" % (self.name, self.type_name)))
        self._type_obj = type_obj
        type_obj.tell_close(self._set_type_callback)

    def _set_type_callback(self):
        self._s.set_type(self._type_obj)


class CSDLDocument(xmlns.XMLNSDocument):

    """Represents a CSDL document."""

    class_map = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        self.default_ns = EDM_NAMESPACE
        self.make_prefix(PACKAGING_NAMESPACE, 'edmx')
        self.make_prefix(EDM_NAMESPACE, '')

    @classmethod
    def get_element_class(cls, name):
        """Overridden to look up name in the class map"""
        eclass = CSDLDocument.class_map.get(
            name, CSDLDocument.class_map.get(
                (name[0], None), xmlns.XMLNSElement))
        return eclass

    def add_child(self, child_class, name=None):
        if child_class is not Edmx:
            raise errors.ModelError(errors.Requirement.csdl_root)
        return super(CSDLDocument, self).add_child(child_class, name=name)

    @classmethod
    def load_core(cls):
        """Loads and returns the built-in Org.OData.Core.V1 schema"""
        uri = URI.from_virtual_path(
            OSFilePath(__file__).split()[0].join("core.xml"))
        doc = cls(base_uri=uri)
        doc.read()
        return doc.root.entity_model["Core"]

    @classmethod
    def load_capabilities(cls):
        """Loads and returns the built-in Org.OData.Capabilities.V1 schema"""
        uri = URI.from_virtual_path(
            OSFilePath(__file__).split()[0].join("capabilities.xml"))
        doc = cls(base_uri=uri)
        doc.read()
        return doc.root.entity_model["Capabilities"]


xmlns.map_class_elements(CSDLDocument.class_map, globals())
