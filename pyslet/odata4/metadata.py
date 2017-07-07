#! /usr/bin/env python

import logging

from . import model as odata
from .errors import (
    DuplicateNameError,
    InheritanceCycleDetected,
    ModelError,
    Requirement,
    )
from ..py2 import (
    is_text,
    to_text
    )
from ..rfc2396 import URI
from ..xml import namespace as xmlns
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi


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


def validate_simple_identifier(value):
    if odata.NameTable.is_simple_identifier(value):
        return value
    else:
        raise ValueError(
            "Can't parse SimpleIdentifier from :%s" % repr(value))


def validate_namespace(value):
    if odata.NameTable.is_namespace(value):
        return value
    else:
        raise ValueError(
            "Can't parse Namespace from :%s" % repr(value))


def validate_qualified_name(value):
    if odata.NameTable.is_namespace(value) and "." in value:
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


def path_from_str(value):
    # TODO
    return value


def path_to_str(path):
    # TODO
    return path


def path_expression_from_str(value):
    # TODO
    return value


def path_expression_to_str(path):
    # TODO
    return path


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


class GInlineExpressionsMixin(object):

    """Abstract class for holding attribution declarations.

    No constructor is provided as these are left to the automated
    handling of default attributes in XML elements."""

    # constant expressions
    XMLATTR_Binary = ('binary_value', odata.BinaryValue.from_str, str)
    XMLATTR_Bool = ('bool_value', odata.BooleanValue.from_str, str)
    XMLATTR_Date = ('date_value', odata.DateValue.from_str, str)
    XMLATTR_DateTimeOffset = ('date_time_offset_value',
                              odata.DateTimeOffsetValue.from_str, str)
    XMLATTR_Decimal = ('decimal_value', odata.DecimalValue.from_str, str)
    XMLATTR_Duration = ('duration_value', odata.DurationValue.from_str, str)
    XMLATTR_EnumMember = ('enum_member', None, None, list)
    XMLATTR_Float = ('float_value', odata.FloatValue.from_str, str)
    XMLATTR_Guid = ('guid_value', odata.GuidValue.from_str, str)
    XMLATTR_Int = ('int_value', odata.Int64Value.from_str, str)
    XMLATTR_String = ('string_value', odata.StringValue.from_str, str)
    XMLATTR_TimeOfDay = ('time_of_day_value', odata.TimeOfDayValue.from_str,
                         str)
    # dynamic expressions
    XMLATTR_AnnotationPath = ('annotation_path', path_expression_from_str, str)
    XMLATTR_NavigationPropertyPath = (
        'navigation_property_path', path_expression_from_str, str)
    XMLATTR_Path = ('path', path_expression_from_str, str)
    XMLATTR_PropertyPath = ('property_path', path_expression_from_str, str)
    XMLATTR_UrlRef = ('url_ref', URI.from_octets, str)


class GExpression(CSDLElement):

    """Abstract class for element expression constructs"""
    pass


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
        CSDLElement):

    """Represents the Annotation element."""
    XMLNAME = (EDM_NAMESPACE, 'Annotation')

    XMLATTR_Term = ('term_qname', validate_qualified_name, None)
    XMLATTR_Qualifier = ('qualifier', validate_simple_identifier, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        # no need to initialise the *Content classes
        self.term_qname = None
        self.term = None
        self.qualifier = None
        self.Annotation = []
        self.GExpression = None

    def content_changed(self):
        if self.term_qname is None:
            raise ModelError("Annotation.Term is required")
        # we will need to look up this term
        em = self.get_entity_model()
        if em is not None:
            em.qualified_tell(self.term_qname, self._set_term)

    def _set_term(self, term):
        self.term = term
        if term is not None and self.parent:
            target = self.parent.get_annotation_target()
            if target is not None:
                a = odata.QualifiedAnnotation()
                a.term = term
                target.annotate(a, self.qualifier)
            else:
                logging.warning("Ignored Annotation: %s" % term.qname)

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


class BinaryConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Binary')

    def get_value(self):
        return odata.BinaryValue.from_str(
            super(BinaryConstant, self).get_value())


class BoolConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Bool')

    def get_value(self):
        return odata.BooleanValue.from_str(
            super(BoolConstant, self).get_value())


class DateConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Date')

    def get_value(self):
        return odata.DateValue.from_str(
            super(DateConstant, self).get_value())


class DateTimeOffsetConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'DateTimeOffset')

    def get_value(self):
        return odata.DateTimeOffsetValue.from_str(
            super(DateTimeOffsetConstant, self).get_value())


class DecimalConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Decimal')

    def get_value(self):
        return odata.DecimalValue.from_str(
            super(DecimalConstant, self).get_value())


class DurationConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Duration')

    def get_value(self):
        return odata.DurationValue.from_str(
            super(DurationConstant, self).get_value())


class EnumMemberConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'EnumMember')

    def get_value(self):
        return [path_from_str(i) for i in
                super(EnumMemberConstant, self).get_value().split()]

    def set_value(self, value):
        if isinstance(value, list):
            super(EnumMemberConstant, self).set_value(
                " ".join(path_to_str(i) for i in value))
        elif is_text(value):
            super(EnumMemberConstant, self).set_value(value)
        else:
            raise ValueError("EnumMember expects str or list")


class FloatConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Float')

    def get_value(self):
        return odata.DoubleValue.from_str(
            super(FloatConstant, self).get_value())


class GuidConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Guid')

    def get_value(self):
        return odata.GuidValue.from_str(
            super(GuidConstant, self).get_value())


class IntConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'Int')

    def get_value(self):
        return odata.Int64Value.from_str(
            super(IntConstant, self).get_value())


class StringConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'String')

    def get_value(self):
        return odata.StringValue.from_str(
            super(StringConstant, self).get_value())


class TimeOfDayConstant(ConstantExpression):
    XMLNAME = (EDM_NAMESPACE, 'TimeOfDay')

    def get_value(self):
        return odata.TimeOfDayValue.from_str(
            super(TimeOfDayConstant, self).get_value())


class PathExpression(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'Path')

    def get_value(self):
        return path_expression_from_str(
            super(PathExpression, self).get_value())


class AnnotationPath(PathExpression):
    XMLNAME = (EDM_NAMESPACE, 'AnnotationPath')


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

    XMLATTR_Function = 'function'

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        self.function = None


class CastOrIsOfExpression(FacetsMixin, AnnotatedExpression):

    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        FacetsMixin.__init__(self)
        self.type_name = None


class CastExpression(CastOrIsOfExpression):
    XMLNAME = (EDM_NAMESPACE, 'Cast')


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


class IfExpression(AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'If')

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)


class TwoChildrenExpression(AnnotatedExpression):
    pass


class EqExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Eq')


class NeExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Ne')


class GeExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Ge')


class GtExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Gt')


class LeExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Le')


class LtExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Lt')


class AndExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'And')


class OrExpression(TwoChildrenExpression):
    XMLNAME = (EDM_NAMESPACE, 'Or')


class OneChildExpression(AnnotatedExpression):
    pass


class NotExpression(OneChildExpression):
    XMLNAME = (EDM_NAMESPACE, 'Not')


class IsOfExpression(CastOrIsOfExpression):
    XMLNAME = (EDM_NAMESPACE, 'IsOf')


class LabeledElement(GInlineExpressionsMixin, AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'LabeledElement')

    XMLATTR_Name = ('name', validate_simple_identifier, None)

    def __init__(self, parent):
        AnnotatedExpression.__init__(self, parent)
        self.name = None


class LabeledElementReference(GExpression):
    XMLNAME = (EDM_NAMESPACE, 'LabeledElementReference')

    def get_value(self):
        return validate_qualified_name(
            super(LabeledElementReference, self).get_value())

    def set_value(self, value):
        return super(LabeledElementReference, self).set_value(
            validate_qualified_name(value))


class NullExpression(GExpression, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Null')


class NavigationPropertyPath(PathExpression):
    XMLNAME = (EDM_NAMESPACE, 'NavigationPropertyPath')


# see above for PathExpression


class PropertyPathExpression(PathExpression):
    XMLNAME = (EDM_NAMESPACE, 'PropertyPath')


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


class PropertyValue(RecordContent, GInlineExpressionsMixin,
                    AnnotatedExpression):
    XMLNAME = (EDM_NAMESPACE, 'PropertyValue')

    XMLATTR_Property = ('property', validate_simple_identifier, None)
    XMLATTR_Type = ('type_name', validate_qualified_name, None)


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
            raise ModelError(Requirement.edmx_version)
        # DataServices is instantiated automatically but if the element
        # was missing during parsing it won't be closed.
        if not self.DataServices._closed:
            raise ModelError(Requirement.csdl_data_services)
        been_there = set()
        for r in self.Reference:
            uri = str(r.resolve_uri(r.uri))
            if uri in been_there:
                raise ModelError(Requirement.unique_reference)
            been_there.add(uri)
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
            raise ModelError(Requirement.csdl_data_services)
        else:
            self._closed = True
        if not self.Schema:
            raise ModelError(Requirement.schemas)

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
            raise ModelError(Requirement.reference_uri)
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
            raise ModelError(Requirement.reference)

    def get_children(self):
        for rc in self.ReferenceContent:
            yield rc
        for child in super(Reference, self).get_children():
            yield child


class Include(ReferenceContent, CSDLElement):
    XMLNAME = (PACKAGING_NAMESPACE, 'Include')

    XMLATTR_Namespace = ('namespace', validate_namespace, None)
    XMLATTR_Alias = ('alias', validate_simple_identifier, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.namespace = None
        self.alias = None

    def content_changed(self):
        if self.namespace is None:
            raise ModelError(Requirement.include_namespace)
        ref_model = self.parent.get_ref_model()
        try:
            ns = ref_model[self.namespace]
            # check that ns is not just referenced in ref_model
            if not ns.is_owned_by(ref_model):
                raise KeyError
        except KeyError:
            raise ModelError(
                Requirement.include_schema_s % self.namespace)
        em = self.get_entity_model()
        if em is not None:
            try:
                if self.alias is not None:
                    if self.alias in RESERVED_ALIASES:
                        raise ModelError(
                            Requirement.reserved_namespace_s % self.namespace)
                    em[self.alias] = ns
            except DuplicateNameError as err:
                raise DuplicateNameError(
                    Requirement.unique_namespace_s % str(err))
            try:
                # cf Schema, we do not change the owner of ns here
                em[ns.name] = ns
            except DuplicateNameError:
                raise DuplicateNameError(
                    Requirement.unique_include_s % ns.name)


class IncludeAnnotations(ReferenceContent, CSDLElement):
    XMLNAME = (PACKAGING_NAMESPACE, 'IncludeAnnotations')

    XMLATTR_TermNamespace = ('term_namespace', validate_namespace, None)
    XMLATTR_Qualifier = ('qualifier', validate_simple_identifier, None)
    XMLATTR_TargetNamespace = ('target_namespace', validate_namespace, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.term_namespace = None
        self.qualifier = None
        self.target_namespace = None

    def content_changed(self):
        if self.term_namespace is None:
            raise ModelError(Requirement.term_namespace)


class Schema(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Schema')

    XMLATTR_Namespace = ('namespace', validate_namespace, None)
    XMLATTR_Alias = ('alias', validate_simple_identifier, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.namespace = None
        self.alias = None
        self.SchemaContent = []
        self._schema = None

    def get_schema(self):
        if self._schema is None:
            if self.namespace is None:
                raise ModelError(Requirement.schema_name)
            if self.namespace in RESERVED_ALIASES:
                raise ModelError(
                    Requirement.reserved_schema_s % self.namespace)
            self._schema = odata.Schema()
            em = self.get_entity_model()
            # This is the first declaration of this schema, it sets the
            # owning namespace; cf Include that merely makes a reference.
            try:
                self._schema.declare(em, self.namespace)
            except DuplicateNameError:
                raise DuplicateNameError(
                    Requirement.schema_unique_s % self.namespace)
            if self.alias is not None:
                if self.alias in RESERVED_ALIASES:
                    raise ModelError(Requirement.reserved_alias_s % self.alias)
                try:
                    em[self.alias] = self._schema
                except DuplicateNameError:
                    # what are we colliding with?
                    dup = em[self.alias]
                    if self.alias == dup.name:
                        raise ModelError(
                            Requirement.unique_namespace_s % self.alias)
                    else:
                        # dup is an alias itself
                        raise ModelError(
                            Requirement.unique_alias_s % self.alias)
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

    XMLATTR_Name = ('name', validate_simple_identifier, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self._type_obj = None

    def get_type(self):
        if self._type_obj is None:
            if self.name is None:
                if isinstance(self, EntityType):
                    raise ModelError(Requirement.et_name)
                elif isinstance(self, ComplexType):
                    raise ModelError(Requirement.ct_name)
                elif isinstance(self, EnumType):
                    raise ModelError(Requirement.ent_name)
                else:
                    raise ValueError("Unnamed type (%s)" % repr(self))
            self._type_obj = self.get_type_obj()
            s = self.get_schema()
            if s is not None:
                try:
                    self._type_obj.declare(s, self.name)
                except DuplicateNameError:
                    dup = s[self.name]
                    if isinstance(dup, odata.NominalType):
                        raise DuplicateNameError(
                            Requirement.type_qname_s % self.name)
                    else:
                        raise DuplicateNameError(
                            Requirement.unique_schema_child_s % self.name)
        return self._type_obj

    def content_changed(self):
        # trigger declaration
        self.get_type()


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
        t.set_abstract(self.abstract)
        if self.open_type is not None:
            t.set_open_type(self.open_type)
        if self.base_type_name is not None:
            em = self.get_entity_model()
            self.add_dependency()
            em.qualified_tell(
                self.base_type_name, self._set_base_type_callback)
        # we start with a single dependency: waiting for this method!
        self.remove_dependency()

    def _set_base_type_callback(self, base_type_obj):
        if base_type_obj is None:
            raise ModelError("%s is not declared" % self.base_type_name)
        t = self.get_type()
        try:
            t.set_base(base_type_obj)
        except InheritanceCycleDetected:
            if isinstance(self, EntityType):
                raise InheritanceCycleDetected(
                    Requirement.et_cycle_s % t.qname)
            elif isinstance(self, ComplexType):
                raise InheritanceCycleDetected(
                    Requirement.ct_cycle_s % t.qname)
            else:
                raise
        # we need to wait for our base to be closed before we can be
        # closed
        base_type_obj.tell_close(self.remove_dependency)


class ComplexType(SchemaContent, DerivableType):
    XMLNAME = (EDM_NAMESPACE, 'ComplexType')

    def __init__(self, parent):
        DerivableType.__init__(self, parent)
        self.ComplexTypeContent = []

    def get_type_obj(self):
        return odata.ComplexType()

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
        return odata.EntityType()

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
                raise ModelError(Requirement.et_key_ref_s % t.qname)
            for pr in self.PropertyRef:
                # convert the path into an array
                if pr.name is None:
                    raise ModelError(Requirement.key_name_s % t.qname)
                p = odata.ODataParser(pr.name)
                try:
                    pr_path = p.require_expand_path()
                    p.require_end()
                except ValueError as err:
                    raise odata.PathError(
                        "Failed to parse Key property path in %s; %s" %
                        (t.qname, to_text(err)))
                t.add_key(pr_path, pr.alias)

    def get_type_context(self):
        if not isinstance(self.parent, EntityType):
            return None
        return self.parent.get_type()


class PropertyRef(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'PropertyRef')

    XMLATTR_Name = ('name', path_from_str, path_to_str)
    XMLATTR_Alias = ('alias', validate_simple_identifier, None)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.alias = None


class PropertyFacetsMixin(object):

    XMLATTR_Unicode = ('unicode', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self):
        self.unicode = None


class CommonPropertyMixin(FacetsMixin, PropertyFacetsMixin):

    """Mixin class for common property attributes

    The specification and schema disagree here.  In the schema the
    Nullable property defaults to true but the specification goes to
    some lengths to explain that a missing Nullable property on a
    property with a Collection type means that it is unknown whether or
    not the collection may contain null values.  We go with the
    specification here and handle the defaulting of Nullable (for
    non-Collection properties) later."""
    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_DefaultValue = 'default_value'

    def __init__(self):
        FacetsMixin.__init__(self)
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
            raise ModelError(Requirement.property_name)
        if self.type_name is None:
            raise ModelError(Requirement.property_type_s % self.name)
        qname, collection = self.type_name
        if self.nullable is None and not collection:
            # default nullability
            self.nullable = True
        t = self.get_type_context()
        if t is not None:
            self._p = odata.Property()
            self._p.set_nullable(self.nullable)
            try:
                self._p.declare(t, self.name)
            except DuplicateNameError:
                raise DuplicateNameError(
                    Requirement.property_unique_s %
                    ("%s:%s" % (t.name, self.name)))
            except ValueError as err:
                # we already validated name as a simple identifier
                raise ModelError(err)
            # look-up the type_name, will trigger type binding now or later
            em = self.get_entity_model()
            # delay closure of this type until we've resolved the type
            # of the property and (in the case of complex types) that
            # type is closed.  This ensures that circular complex types
            # are caught properly and that all property paths of closed
            # entity types can be resolved, even if they traverse
            # complex types.
            self.parent.add_dependency()
            em.qualified_tell(qname, self._set_type_callback)
        return self._p

    def get_annotation_target(self):
        return self.get_property()

    def _set_type_callback(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(
                type_obj, (odata.PrimitiveType, odata.ComplexType,
                           odata.EnumerationType)):
            raise ModelError(
                Requirement.property_type_declared_s % self.type_name[0])
        qname, collection = self.type_name
        if isinstance(type_obj, odata.PrimitiveType):
            # add the facets to this type
            ptype = odata.PrimitiveType()
            ptype.set_base(type_obj)
            if self.max_length is not None:
                ptype.set_max_length(self.max_length)
            if self.unicode is not None:
                ptype.set_unicode(self.unicode)
            if self.precision is not None or self.scale is not None:
                ptype.set_precision(self.precision, self.scale)
            if self.srid is not None:
                ptype.set_srid(self.srid)
            type_obj = ptype
            default_value = None
            if collection:
                # can't specify default for a collection
                type_obj = odata.CollectionType(type_obj)
            else:
                if self.default_value is not None:
                    try:
                        default_value = type_obj.value_from_str(
                            self.default_value)
                    except ValueError as err:
                        raise ModelError(
                            Requirement.primitive_default_s % str(err))
            self._p.set_type(type_obj)
            if default_value is not None:
                self._p.default_value = default_value
            self.parent.remove_dependency()
        else:
            if collection:
                self._p.set_type(odata.CollectionType(type_obj))
            else:
                self._p.set_type(type_obj)
            if isinstance(type_obj, odata.EnumerationType):
                type_obj.tell_close(self._enumeration_callback)
            else:
                # ComplexType
                type_obj.tell_close(self._complex_callback)

    def _enumeration_callback(self):
        # EnumerationType has been closed, set default and remove
        # dependency so that our parent type can close
        type_obj = self._p.type_def
        if not isinstance(type_obj, odata.CollectionType):
            if self.default_value is not None:
                self._p.default_value = type_obj.value_from_str(
                    self.default_value)
        self.parent.remove_dependency()

    def _complex_callback(self):
        # ComplexType has been closed.  Check this complex type to see
        # if it contains a containment navigation property.  Remove
        # dependency so that our parent type can close
        type_obj = self._p.type_def
        if isinstance(type_obj, odata.CollectionType):
            for path, np in self._p.type_def.item_type.navigation_properties():
                logging.debug(
                    "Checking %s.%s for containment" % (self.name, path))
                if np.containment:
                    raise ModelError(Requirement.nav_contains_s % self.name)
        self.parent.remove_dependency()

    def get_type_context(self):
        if not isinstance(self.parent, (ComplexType, EntityType)):
            return None
        return self.parent.get_type()


class NavigationProperty(ComplexTypeContent, EntityTypeContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'NavigationProperty')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_Partner = ('partner', path_from_str, path_to_str)
    XMLATTR_ContainsTarget = ('contains_target', xsi.boolean_from_str,
                              xsi.boolean_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.type_name = None
        self.nullable = None
        self.partner = None
        self._partner_path = None
        self.contains_target = False
        self.NavigationPropertyContent = []
        self._np = None

    def content_changed(self):
        if self.name is None:
            raise ModelError(Requirement.nav_name)
        if self.type_name is None:
            raise ModelError(Requirement.nav_type_s % self.name)
        # check syntax of partner, if present
        if self.partner is not None:
            p = odata.ODataParser(self.partner)
            try:
                self._partner_path = p.require_expand_path()
                p.require_end()
                logging.debug("Partner %s", to_text(self._partner_path))
            except ValueError as err:
                raise odata.PathError(
                    "Failed to parse Partner path in %s; %s" %
                    (self.name, to_text(err)))
        else:
            self._partner_path = None
        self._np = odata.NavigationProperty()
        qname, collection = self.type_name
        if collection:
            if self.nullable is not None:
                raise ModelError(
                    Requirement.nav_collection_exists_s % self.name)
        elif self.nullable is None:
            # default nullability
            self.nullable = True
        self._np.set_nullable(self.nullable)
        self._np.set_containment(self.contains_target)
        t = self.get_type_context()
        if t is not None:
            if self.partner is not None and \
                    not isinstance(t, odata.EntityType):
                raise ModelError(
                    Requirement.nav_partner_complex_s %
                    ("%s/%s" % (t.name, self.name)))
            try:
                self._np.declare(t, self.name)
            except DuplicateNameError:
                raise DuplicateNameError(
                    Requirement.property_unique_s %
                    ("%s/%s" % (t.name, self.name)))
            except ValueError as err:
                raise ModelError(err)
        # look-up the type_name, will trigger type binding now or later
        em = self.get_entity_model()
        em.qualified_tell(qname, self._set_type_callback)
        if self._partner_path is not None:
            # we need to resolve the partner path, wait for all
            # declarations to have been made.
            em.tell_close(self._set_partner_callback)

    def _set_type_callback(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(type_obj, odata.EntityType):
            raise ModelError(Requirement.nav_type_resolved_s % self.name)
        self._np.set_type(type_obj, self.type_name[1])
        # now wait for both the containing type and the target type
        # to be closed before resolving referential constraints
        t = self.get_type_context()
        odata.NameTable.tell_all_closed(
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
            target = em.resolve_nppath(
                self._np.entity_type, self._partner_path)
        except odata.PathError as err:
            raise ModelError(Requirement.nav_partner_path_s %
                             ("%s, %s" % (self.name, to_text(err))))
        t = self.get_type_context()
        if not isinstance(t, odata.EntityType):
            # Unexpected: partners can only be specified for entity types
            raise ModelError("Expected EntityType: %s" % t.qname)
        if not t.is_derived_from(target.entity_type):
            raise ModelError(Requirement.nav_partner_type_s % self.name)
        if target.partner is not None and target.partner is not self._np:
            raise ModelError(Requirement.nav_partner_bidirection_s % self.name)
        if self._np.containment:
            if t.is_derived_from(self._np.entity_type) or \
                    self._np.entity_type.is_derived_from(t):
                # this relationship is recursive
                if isinstance(target.type_def, odata.CollectionType):
                    raise ModelError(Requirement.nav_rcontains_s % self.name)
                if not target.nullable:
                    raise ModelError(Requirement.nav_rcontains_s % self.name)
            else:
                if target.nullable:
                    raise ModelError(Requirement.nav_nrcontains_s % self.name)
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

    XMLATTR_Property = ('property', path_from_str, path_to_str)
    XMLATTR_ReferencedProperty = ('referenced_property', path_from_str,
                                  path_to_str)

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
            raise odata.ModelError(Requirement.refcon_property_s % np.qname)
        p = odata.ODataParser(self.property)
        try:
            dpath = p.require_expand_path()
            p.require_end()
        except ValueError as err:
            raise odata.ModelError(
                Requirement.refcon_ppath_s % ("%s: %s" % (np.qname, str(err))))
        if self.referenced_property is None:
            raise odata.ModelError(Requirement.refcon_refprop_s % np.qname)
        p = odata.ODataParser(self.referenced_property)
        try:
            ppath = p.require_expand_path()
            p.require_end()
        except ValueError as err:
            raise odata.ModelError(
                Requirement.refcon_rpath_s % ("%s: %s" % (np.qname, str(err))))
        np.add_constraint(dpath, ppath)


class OnDelete(NavigationPropertyContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'OnDelete')

    XMLATTR_Action = ('action', odata.OnDeleteAction.from_str, str)
    # enumeration: Cascade, None, SetDefault, SetNull

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        self.action = None

    def add_action(self, np):
        if self.action is None:
            raise odata.ModelError(Requirement.ondelete_value)
        np.add_action(self.action)


class TypeDefinition(SchemaContent, FacetsMixin, PropertyFacetsMixin,
                     Annotated):
    XMLNAME = (EDM_NAMESPACE, 'TypeDefinition')

    XMLATTR_Name = ('type_name', validate_simple_identifier, None)
    XMLATTR_UnderlyingType = ('underlying_type', validate_qualified_name, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        FacetsMixin.__init__(self)
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
                raise ModelError(Requirement.td_name)
            if self.underlying_type is None:
                raise ModelError(Requirement.td_qname_s % self.type_name)
            em = self.get_entity_model()
            # we are only interested in the Edm namespace which will
            # already be loaded, no need wait...
            base_type = em.qualified_get(self.underlying_type)
            if not isinstance(base_type, odata.PrimitiveType):
                raise ModelError(Requirement.td_qname_s % self.type_name)
            # Must be in the Edm namespace
            if not base_type.nametable() is odata.edm:
                raise ModelError(Requirement.td_redef_s % self.type_name)
            self._type_obj = odata.PrimitiveType()
            self._type_obj.set_base(base_type)
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
                except DuplicateNameError:
                    dup = s[self.type_name]
                    if isinstance(dup, odata.NominalType):
                        raise DuplicateNameError(
                            Requirement.type_qname_s % self.type_name)
                    else:
                        raise DuplicateNameError(
                            Requirement.unique_schema_child_s % self.type_name)
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
                raise ModelError(Requirement.ent_type_s % self.underlying_type)
            # we are only interested in the Edm namespace which will
            # already be loaded, no need wait...
            base_type = em.qualified_get(qname)
            if base_type is None:
                raise ModelError(Requirement.ent_type_s % qname)
        else:
            base_type = None
        self._ent = odata.EnumerationType(base_type)
        if self.is_flags:
            self._ent.set_is_flags()
        return self._ent


class Member(EnumTypeContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Member')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Value = ('value', xsi.integer_from_str, xsi.integer_to_str)
    # long

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        self.name = None
        self.value = None

    def content_changed(self):
        if self.name is None:
            raise ModelError(Requirement.ent_member_name)
        m = odata.Member()
        m.value = self.value
        t = self.get_type_context()
        if t is not None:
            try:
                m.declare(t, self.name)
            except DuplicateNameError:
                raise DuplicateNameError(
                    Requirement.ent_member_unique_s %
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


class ActionFunction(CSDLElement):

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.ActionFunctionContent = []
        self.ReturnType = None

    def get_children(self):
        for afc in self.ActionFunctionContent:
            yield afc
        if self.ReturnType:
            yield self.ReturnType
        for child in super(EnumType, self).get_children():
            yield child


class Parameter(ActionFunctionContent, FacetsMixin, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Parameter')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Type = ('type_name', type_name_from_str, type_name_to_str)
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = None
        self.type_name = None
        self.nullable = None


class Action(SchemaContent, ActionFunction):
    XMLNAME = (EDM_NAMESPACE, 'Action')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_EntitySetPath = ('entity_set_path', path_from_str, path_to_str)
    XMLATTR_IsBound = ('is_bound', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        ActionFunction.__init__(self, parent)
        self.name = None
        self.entity_set_path = None
        self.is_bound = False


class Function(SchemaContent, ActionFunction):
    XMLNAME = (EDM_NAMESPACE, 'Function')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_EntitySetPath = ('entity_set_path', path_from_str, path_to_str)
    XMLATTR_IsBound = ('is_bound', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_IsComposable = ('is_composable', xsi.boolean_from_str,
                            xsi.boolean_to_str)

    def __init__(self, parent):
        ActionFunction.__init__(self, parent)
        # ReturnType is required
        self.ReturnType = ReturnType()
        self.name = None
        self.entity_set_path = None
        self.is_bound = False
        self.is_composable = False


class Term(SchemaContent, FacetsMixin, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Term')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
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

    def content_changed(self):
        s = self.get_schema()
        if s is not None:
            # declare this Term within the namespace
            term = odata.Term()
            term.declare(s, self.name)


class Annotations(SchemaContent, Annotated):
    XMLNAME = (EDM_NAMESPACE, 'Annotations')

    XMLATTR_Target = ('target', path_from_str, path_to_str)
    XMLATTR_Qualifier = ('qualifier', validate_simple_identifier, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        # at least one annotation required!
        self.target = None
        self.qualifier = None


class EntityContainer(SchemaContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'EntityContainer')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
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
            raise ModelError("%s is not declared" % self.extends)
        ec = self.get_container()
        try:
            ec.set_extends(extends_obj)
        except DuplicateNameError as err:
            raise DuplicateNameError(
                "[%s] TBC" % str(err))
        # close this container when the 'base' container closes
        extends_obj.tell_close(ec.close)

    def get_container(self):
        if self._container is None:
            self._container = odata.EntityContainer()
            schema = self.get_schema()
            try:
                self._container.declare(schema, self.name)
            except DuplicateNameError:
                raise ModelError(
                    "P3 13.1 Entity set, singleton, action import, and "
                    "function import names MUST be unique within an entity "
                    "container (%s)" % self.name)
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

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_EntityType = ('type_name', validate_qualified_name, None)
    XMLATTR_IncludeInServiceDocument = (
        'include_in_service_document', xsi.boolean_from_str,
        xsi.boolean_to_str)

    def __init__(self, parent):
        AnnotatedNavigation.__init__(self, parent)
        self.name = None
        self.type_name = None
        self.include_in_service_document = True
        self._es = None

    def content_changed(self):
        if self.name is None:
            raise ModelError(
                "P3 13.2.1 Missing or invalid Name for EntitySet %s" %
                self.name)
        if self.type_name is None:
            raise ModelError(
                "P3 13.2.2 The EntitySet element MUST include an EntityType "
                "attribute whose value is [a] QualifiedName")
        container = self.get_container()
        if container is not None:
            # declare this EntitySet within the container
            self._es = odata.EntitySet()
            try:
                self._es.declare(container, self.name)
            except DuplicateNameError as err:
                raise ModelError(
                    "P3 13.1 Entity set, singleton, action import, and "
                    "function import names MUST be unique within an entity "
                    "container (%s)" % str(err))
        # look-up the type_name, will trigger type binding now or later
        em = self.get_entity_model()
        em.qualified_tell(self.type_name, self._set_type_callback)

    def _set_type_callback(self, type_obj):
        # set self.type_obj
        if type_obj is None or not isinstance(type_obj, odata.EntityType):
            raise ModelError(
                "P3 13.2.2 The EntitySet element MUST include an EntityType "
                "attribute whose value is the QualifiedName of an entity "
                "type in scope [%s]" % self.type_name)
        # An EntityType is only closed after it's base type has closed.
        # Therefore, we can safely determine if a key has been defined.
        if not type_obj.key_defined():
            raise ModelError(
                "P3 13.2.2 The entity type named by the EntityType attribute "
                "MAY be abstract but MUST have a key defined [%s]" %
                self.type_name)
        self._es.set_type(type_obj)

    def get_type(self):
        if self._es is None:
            return None
        else:
            return self._es.entity_type


class NavigationPropertyBinding(AnnotatedNavigationContent, CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'NavigationPropertyBinding')

    XMLATTR_Path = ('path', path_from_str, path_to_str)
    XMLATTR_Target = ('target', path_from_str, path_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.path = None
        self._navpath = None
        self.target = None

    def content_changed(self):
        """Triggers the resolution of this binding

        The binding itself cannot be resolved until the entire entity
        model is complete as it involves traversing a navigation path."""
        em = self.get_entity_model()
        if self.path is None:
            raise ModelError(
                "P3 13.4.2 A navigation property binding MUST name a "
                "navigation property in the Path attribute")
        p = odata.ODataParser(self.path)
        try:
            self._navpath = p.require_expand_path()
            p.require_end()
            logging.debug("Path %s", to_text(self._navpath))
        except ValueError as err:
            raise odata.PathError(
                "Failed to parse Navigation path from %s; %s" %
                (self.path, to_text(err)))
        em.tell_close(self.resolve_path)

    def resolve_path(self):
        em = self.get_entity_model()
        t = self.get_type_context()
        if t is None:
            raise ModelError("Can't bind navigation in undeclared type")
        try:
            # the path resolution takes care of one of our constraints
            np = em.resolve_nppath(t, self._navpath)
        except odata.PathError as err:
            raise ModelError(
                "P3 13.4.2 A navigation property binding MUST name a "
                "navigation property in the Path attribute (%s)" %
                to_text(err))
        if np.containment:
            raise ModelError(Requirement.nav_contains_binding_s % self.path)

    def get_type_context(self):
        if not isinstance(self.parent, EntitySet):
            return None
        return self.parent.get_type()


class ActionFunctionImportMixin(object):

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_EntitySet = ('entity_set', path_from_str, path_to_str)
    XMLATTR_IncludeInServiceDocument = (
        'include_in_service_document', xsi.boolean_from_str,
        xsi.boolean_to_str)

    def __init__(self):
        self.name = None
        self.entity_set = None
        self.include_in_service_document = False


class ActionImport(EntityContainerContent, ActionFunctionImportMixin,
                   Annotated):
    XMLNAME = (EDM_NAMESPACE, 'ActionImport')

    XMLATTR_action = ('action', validate_qualified_name, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        ActionFunctionImportMixin.__init__(self)
        self.action = None


class FunctionImport(EntityContainerContent, ActionFunctionImportMixin,
                     Annotated):
    XMLNAME = (EDM_NAMESPACE, 'FunctionImport')

    XMLATTR_action = ('function', validate_qualified_name, None)

    def __init__(self, parent):
        Annotated.__init__(self, parent)
        ActionFunctionImportMixin.__init__(self)
        self.function = None


class Singleton(EntityContainerContent, AnnotatedNavigation):
    XMLNAME = (EDM_NAMESPACE, 'Singleton')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Type = ('type_name', validate_qualified_name, None)

    def __init__(self, parent):
        AnnotatedNavigation.__init__(self, parent)
        self.name = None
        self.type_name = None

    def content_changed(self):
        container = self.get_container()
        if container is not None:
            # declare this Singleton within the container
            s = odata.Singleton()
            try:
                s.declare(container, self.name)
            except DuplicateNameError as err:
                raise ModelError(
                    "P3 13.1 Entity set, singleton, action import, and "
                    "function import names MUST be unique within an entity "
                    "container (%s)" % str(err))


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
            raise ModelError(Requirement.csdl_root)
        return super(CSDLDocument, self).add_child(child_class, name=name)


xmlns.map_class_elements(CSDLDocument.class_map, globals())
