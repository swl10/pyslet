#! /usr/bin/env python

import logging
import weakref

from .. import rfc2396 as uri
from ..py2 import (
    is_text,
    to_text,
    )

from . import (
    data,
    errors,
    names,
    primitive,
    types,
    )


class EntityModel(names.QNameTable):

    """An EntityModel is the starting point for an OData service

    The EntityModel behaves like a mapping of namespace names (as text
    strings) on to :class:`Schema` instances.  """

    def __init__(self, **kwargs):
        super(EntityModel, self).__init__(**kwargs)
        #: a weak reference to the service this model is bound to
        self.service_ref = None
        # all entity models have the built-in Edm namespace in scope
        self['Edm'] = edm
        self['odata'] = odata

    def check_value(self, value):
        """EntityModels can only contain Schemas"""
        if not isinstance(value, Schema):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<EntityModel>" if self.name is None else self.name))

    def close(self):
        """Overridden to perform additional validation checks

        The EntityModel is always closed to prevent the caller making
        future declarations in this model.  The following conditions
        will result in an error being raised.

            1. All declared Schema objects MUST be closed
            2. There MUST NOT be any disallowed circular type references
        """
        super(EntityModel, self).close()
        for s in self.values():
            if not s.closed:
                raise errors.ModelError("Schema %s is still open" % s.name)
        # Closing the entity model triggers any pending references to
        # undeclared schemas to be terminated.  The Schemas themselves
        # should all be closed at this point but circular references may
        # still be open and waiting for closure.
        for s in self.values():
            s.detect_circular_refs()
        for s in self.values():
            for item in s.values():
                if isinstance(item, types.StructuredType):
                    item.set_annotations()
                    item.check_navigation()

    def get_enum_value(self, eliteral):
        """Returns the value of an enumeration literal

        eliteral is a tuple of type :class:`names.EnumLiteral`, the
        result is an EnumerationValue or an error if the enumeration is
        not declared or cannot be parsed from the given names or values.

        If the literal does not correspond to a declared EnumType then a
        TypeError is raised.  If the literal's value does not correspond
        to a valid member (or members) then a ValueError is raised."""
        enum_def = self.qualified_get(eliteral.qname)
        if not isinstance(enum_def, types.EnumerationType):
            raise TypeError(
                "%s is not an EnumType" % to_text(eliteral.qname))
        result = enum_def()
        if not enum_def.is_flags:
            if len(eliteral.value != 1):
                raise ValueError(
                    "%s requires a single member" % to_text(eliteral.qname))
            result.set_value(eliteral.value[0])
        else:
            result.set_value(eliteral.value)
        return result

    def derived_types(self, base):
        """Generates all types derived from base"""
        for name, schema in self.items():
            if name != schema.name:
                # ignore schema aliases
                continue
            for n, item in schema.items():
                if isinstance(item, types.StructuredType) and \
                        item.is_derived_from(base, strict=True):
                    yield item

    def bind_to_service(self, service):
        """Binds this EntityModel to a data service

        The act of binding an EntityModel to a data service binds
        all type definitions within the model to the same service
        enabling these types to be referred to with globally unique
        identifiers (the URLs used for @odata.type annotations) in
        OData payloads.

        The service should not be confused with the metadata document
        that contains a type definition.  Although every service must
        have a metadata document the reverse is not true: a metadata
        document may just be a CSDL document with a URL that contains
        common definitions included by reference.  (The standard OData
        vocabularies are an example.)

        On a more technical note: a common type defined in a metadata
        document that is reused by multiple services will have a
        different identity in each service, as represented by the
        @odata.type value used to describe the type of values.  As a
        result, each type definition can only be bound to one service!
        The CSDL parser in the metadata module handles this for you by
        creating separate instances of each Schema object loaded by
        reference so that applications that manage multiple services
        sharing common definitions do not violate this constraint.

        There is one special case: the Edm Schema object is only loaded
        once and the definitions within it are *never* bound to the
        service.  This is consistent with the way these types are handled
        by the specification:

            For built-in primitive types the value is the unqualified
            name of the primitive type, specified as a URI fragment

        In other words, types like Edm.String have the *same* identity
        in all services and are represented by the URL fragment
        #String."""
        self.service_ref = weakref.ref(service)
        for sname, schema in self.items():
            if schema.name != sname or schema.name in (
                    "Edm", "odata", "Org.OData.Core.V1",
                    "Org.OData.Capabilities.V1"):
                # skip aliases and reserved schemas
                continue
            for item in schema.values():
                if isinstance(item, types.NominalType):
                    logging.debug("Binding type: %s", item.qname)
                    item.bind_to_service(self.service_ref)
        for item in self.get_container().values():
            if isinstance(
                    item,
                    (EntitySet, Singleton, FunctionImport, ActionImport)):
                item.bind_to_service(self.service_ref)

    def get_context_url(self):
        """Returns the context URL of this model

        The model *must* have been bound to a service for have a context
        url."""
        if self.service_ref is None or self.service_ref() is None:
            raise errors.UnboundValue("Unbound EntityModel has no context")
        return self.service_ref().context_base

    def get_container(self):
        """Returns the required container for this model

        The requirement to define an entity container is not applied to
        all entity models.  Models only designed to be included by
        reference do not need to define a container."""
        container = None
        for name, schema in self.items():
            if name != schema.name or not schema.is_owned_by(self):
                # ignore aliases and schemas included by reference
                continue
            for n, item in schema.items():
                if isinstance(item, EntityContainer):
                    if container is not None:
                        raise errors.ModelError(
                            errors.Requirement.one_container)
                    container = item
        return container


class Schema(types.Annotatable, names.NameTable):

    """A Schema is a container for OData model definitions."""

    csdl_name = "Schema"

    def check_name(self, name):
        """Checks the validity of 'name' against SimpleIdentifier

        Raises ValueError if the name is not valid (or is None).

        From the spec:

            A nominal type has a name that MUST be a
            edm:TSimpleIdentifier."""
        if name is None:
            raise ValueError("unnamed type")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        """The following types may be declared in a Schema:

        NominalType
            Any named type.

        EntityContainer
            A container of entities.

        Term
            The definition of an annotation term.

        CallableOverload
            The definition of (a group of overloaded) Function or Action

        LabeledExpression
            A labelled expression (used in Annotations)."""
        if not isinstance(value, (types.Term,
                                  types.NominalType, EntityContainer,
                                  types.CallableOverload,
                                  types.LabeledExpression)):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<Schema>" if self.name is None else self.name))

    def detect_circular_refs(self):
        """Detects any circular references

        In fact, this method searches for any objects with NameTables
        that are still open and warns that they may be part of a circular
        chain of references.  For EntityTypes we check for inheritance
        cycles specifically, otherwise we then intervene by closing one
        of the objects arbitrarily which should resolve the problem.

        Although undesirable, circular references are tolerated in
        EntityContainers (the specification uses the language SHOULD NOT
        rather than MUST NOT). In cases like these objects end up
        containing the union of the two sets of definitions."""
        for item in self.values():
            if isinstance(item, names.NameTable) and not item.closed:
                logging.warning("Circular reference detected: %s", item.qname)
                if isinstance(item, (types.ComplexType, types.EntityType)):
                    try:
                        item.is_derived_from(item, strict=True)
                    except errors.InheritanceCycleDetected:
                        raise errors.InheritanceCycleDetected(
                            (errors.Requirement.et_cycle_s if
                             isinstance(item, types.EntityType) else
                             errors.Requirement.ct_cycle_s) % item.qname)
                item.close()

    def get_model(self):
        """Returns the entity model that defines this Schema.

        If this Schema has not been declared yet then None is
        returned."""
        if self.nametable is not None:
            return self.nametable()

    edm = None
    """The Edm schema.

    This schema contains the base type definitions of the built-in
    types in the Edm namespace."""

    @classmethod
    def edm_init(cls):
        """Creates and returns the built-in Edm schema"""
        cls.edm = Schema()
        cls.edm.name = "Edm"
        cls.edm.qname = "Edm"
        primitive.edm_primitive_type.declare(cls.edm, "PrimitiveType")
        types.ComplexType.edm_base.declare(cls.edm, "ComplexType")
        data.edm_entity_type.declare(cls.edm, "EntityType")
        primitive.edm_geography.declare(cls.edm, "Geography")
        types.GeometryType.edm_base.declare(cls.edm, "Geometry")
        for name, vtype in (
                ('Binary', primitive.edm_binary),
                ('Boolean', primitive.edm_boolean),
                ('Byte', primitive.edm_byte),
                ('Date', primitive.edm_date),
                ('DateTimeOffset', primitive.edm_date_time_offset),
                ('Decimal', primitive.edm_decimal),
                ('Double', primitive.edm_double),
                ('Duration', primitive.edm_duration),
                ('Guid', primitive.edm_guid),
                ('Int16', primitive.edm_int16),
                ('Int32', primitive.edm_int32),
                ('Int64', primitive.edm_int64),
                ('SByte', primitive.edm_sbyte),
                ('Single', primitive.edm_single),
                ('Stream', primitive.edm_stream),
                ('String', primitive.edm_string),
                ('TimeOfDay', primitive.edm_time_of_day),
                ('GeographyPoint', types.GeographyPointType.edm_base),
                ('GeographyLineString',
                 types.GeographyLineStringType.edm_base),
                ('GeographyPolygon', types.GeographyPolygonType.edm_base),
                ('GeographyMultiPoint',
                 types.GeographyMultiPointType.edm_base),
                ('GeographyMultiLineString',
                 types.GeographyMultiLineStringType.edm_base),
                ('GeographyMultiPolygon',
                 types.GeographyMultiPolygonType.edm_base),
                ('GeographyCollection',
                 types.GeographyCollectionType.edm_base),
                ('GeometryPoint', types.GeometryPointType.edm_base),
                ('GeometryLineString', types.GeometryLineStringType.edm_base),
                ('GeometryPolygon', types.GeometryPolygonType.edm_base),
                ('GeometryMultiPoint', types.GeometryMultiPointType.edm_base),
                ('GeometryMultiLineString',
                 types.GeometryMultiLineStringType.edm_base),
                ('GeometryMultiPolygon',
                 types.GeometryMultiPolygonType.edm_base),
                ('GeometryCollection', types.GeometryCollectionType.edm_base),
                # Vocabulary terms can also use the following...
                ('AnnotationPath', primitive.edm_annotation_path),
                ('PropertyPath', primitive.edm_property_path),
                ('NavigationPropertyPath',
                 primitive.edm_navigation_property_path),
                ):
            vtype.declare(cls.edm, name)
        cls.edm.close()
        return cls.edm

    odata = None
    """The odata schema.

    This schema contains the builtin term definitions."""

    @classmethod
    def odata_init(cls):
        """Creates and returns the built-in odata schema"""
        cls.odata = Schema()
        cls.odata.name = "odata"
        cls.odata.qname = "odata"
        for tname in (
                "associationLink",
                "bind",
                "context",
                "deltaLink",
                "editLink",
                "etag",
                "id",
                "mediaContentType",
                "mediaEditLink",
                "mediaEtag",
                "mediaReadLink",
                "metadataEtag",
                "navigationLink",
                "nextLink",
                "type",
                ):
            term = types.Term()
            term.set_type(cls.edm["String"])
            term.declare(cls.odata, tname)
        term = types.Term()
        term.set_type(cls.edm["Int64"])
        term.declare(cls.odata, "count")
        cls.odata.close()
        return cls.odata


class EntityContainer(types.Annotatable, names.NameTable):

    """An EntityContainer is a container for OData entities."""

    csdl_name = "EntityContainer"

    def __init__(self, **kwargs):
        super(EntityContainer, self).__init__(**kwargs)
        #: the entity container we are extending
        self.extends = None

    def check_name(self, name):
        """Checks the validity of 'name' against SimpleIdentifier

        Raises ValueError if the name is not valid (or is None).

        From the spec:

            The edm:EntityContainer element MUST provide a unique
            SimpleIdentifier value for the Name attribute."""
        if name is None:
            raise ValueError("unnamed container")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        """The following types may be declared in an EntityContainer:

        EntitySet, Singleton, ActionImport and FunctionImport."""
        if not isinstance(value, (EntitySet, Singleton, ActionImport,
                                  FunctionImport)):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<EntityContainer>" if self.name is None else self.name))

    def set_extends(self, extends):
        """Sets the container that this container extends"""
        if not isinstance(extends, EntityContainer):
            raise TypeError(
                "%s must be an entity container" % extends.qname)
        self.extends = extends

    def close(self):
        # before we close this nametable, add in the declarataions from
        # the extended container if present
        logging.debug("Closing EntityContainer %s", self.qname)
        if self.extends is not None:
            for name, item in self.extends.items():
                # we tolerate cycles, which means that if an item is
                # already declared we ignore it
                old_item = self.get(name, None)
                if old_item is item:
                    continue
                self[name] = item
        super(EntityContainer, self).close()
        # resolve the navigation bindings of each entity set relative
        # to the defining model.
        model = self.get_model()
        for name, item in self.items():
            if isinstance(item, EntitySet):
                item.bind_navigation(model)

    def get_model(self):
        """Returns the entity model that defines this container.

        The container must have been declared within a Schema which, in
        turn, must have been declared within an EntityModel.  Otherwise
        None is returned."""
        if self.nametable is not None:
            schema = self.nametable()
            return schema.get_model()


class NavigationBinding(object):

    """Represents a navigation property binding"""

    def __init__(self):
        #: the navigation property path
        self.np_path = None
        #: the navigation property definition
        self.np = None
        #: the target (an EntitySet or Singleton)
        self.target = None
        #: the target path within instances of the target
        self.target_path = None


class EntityBinding(types.Annotatable, names.Named):

    """Represents an EntitySet or Singleton in the OData model

    Abstract class covering shared aspects of these two constructs."""

    def __init__(self, **kwargs):
        super(EntityBinding, self).__init__(**kwargs)
        #: the entity type of the entities in this context
        self.entity_type = None
        #: the type definition for values of this entity context
        self.type_def = None
        #: the service we're bound to
        self.service_ref = None
        self._nb_list = []
        #: navigation bindings, mapping from path tuple to
        #: NavigationBinding instance
        self.navigation_bindings = {}
        # the URL of this entity context within a published container
        self.url = None

    def get_model(self):
        if self.nametable is not None:
            # we are declared in an EntityContainer
            self.nametable().get_model()
        else:
            return None

    def set_type(self, entity_type):
        """Sets the entity type

        The entity_type must be closed before it can be used as the type
        of an entity set or singleton."""
        if not entity_type.closed:
            raise errors.ModelError(
                "Type %s is still open" % entity_type.qname)
        self.entity_type = entity_type

    def add_navigation_binding(self, path, target):
        """Adds a navigation binding to this entity context

        path
            A path tuple that defines a path to the navigation property
            being bound.

        target
            A path tuple that defines a path to the target entity set."""
        nb = NavigationBinding()
        nb.np_path = list(path)
        nb.target_path = list(target)
        self._nb_list.append(nb)

    def bind_navigation(self, model):
        """Binds navigation paths to target entity sets

        This method is called when the enclosing EntityContainer is
        closed but we must wait for the model itself to close before we
        can resolve the navigation bindings to ensure that qualified
        names can be resolved in the paths."""

        def model_closed():
            logging.debug("Resolving bindings for %s", self.qname)
            if self.entity_type is None:
                raise errors.ModelError("%s has no EntityType" % self.qname)
            for nb in self._nb_list:
                try:
                    self.entity_type.resolve_nppath(
                        nb.np_path, model, follow_containment=True)
                    # freeze the path into a tuple
                    nb.np_path = tuple(nb.np_path)
                    if nb.np_path in self.navigation_bindings:
                        raise errors.ModelError(
                            errors.Requirement.navbinding_unique_s % (
                                self.qname + "/" +
                                types.StructuredType.path_to_str(nb.np_path)))
                    nb.target = self.resolve_target_path(
                        nb.target_path, model)
                    logging.debug("Binding %s to %s/%s", to_text(nb.np_path),
                                  nb.target.qname,
                                  types.StructuredType.path_to_str(
                                    nb.target_path))
                    self.navigation_bindings[nb.np_path] = nb
                except errors.PathError as err:
                    # takes care of most of our constraints at once
                    raise errors.ModelError(
                        errors.Requirement.navbinding_path_s % to_text(err))

        if self.nametable is not None:
            model = self.nametable().get_model()
            model.tell_close(model_closed)

    def resolve_target_path(self, path, context):
        """Resolves a target path relative to this entity set

        path
            A list of string and/or :class:`names.QualifiedName` that
            resolves to an entity set.  Redundant path segments will be
            removed so that this becomes a canonical path on return (see
            below).

        context
            The model within which to resolve qualified names.

        Returns the EntitySet or Singleton object the path resolves to
        and updates path so that it contains a path from that item's
        entity type to the target containment navigation property.  The
        path list will be empty on return if the target is the EntitySet
        or Singleton itself."""
        if self.name is None or self.nametable is None:
            return errors.ObjectNotDeclaredError
        if len(path) == 1 and is_text(path[0]):
            # a SimpleIdentifier, must be in the same container
            container = self.nametable()
            if path[0] not in container:
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s" % (self.qname, path[0])))
            target = container[path[0]]
            del path[0]
            return target
        else:
            # a QualifiedName refers to a container, it must be followed
            # by the simple identifier of an EntitySet or a Singleton
            if len(path) < 2 or \
                    not isinstance(path[0], names.QualifiedName) or \
                    not is_text(path[1]):
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s" %
                     (self.qname, types.StructuredType.path_to_str(path))))
            try:
                container = context.qualified_get(path[0])
                target = container[path[1]]
                del path[0:2]
                if len(path):
                    # we need to find a containment navigation property
                    # we don't need to retain the definition at this point
                    target.entity_type.resolve_nppath(
                        path, context, follow_containment=True,
                        require_containment=True)
                return target
            except errors.PathError as err:
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    to_text(err))
            except KeyError as err:
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s (%s)" %
                     (self.qname, types.StructuredType.path_to_str(path),
                      to_text(err))))

    def resolve_binding(self, path):
        """Returns the target entity set of a navigation property

        path
            A tuple of strings that specifies the canonical path to the
            navigation property."""
        nb = self.navigation_bindings.get(path, None)
        if nb:
            return nb.target
        else:
            return None

    def bind_to_service(self, service_ref):
        """Binds this EntitySet to an data service

        service_ref
            A weak reference to the service

        An EntitySet can only be bound to a single service."""
        self.service_ref = service_ref

    def get_url(self):
        """Return a URI for this entity context

        An EntitySet has a URL if it is advertised by the service,
        otherwise it does not have a URL and None is returned.
        Singletons SHOULD always have a URL as they are all exposed in
        the service document.  By default the URI is a relative URI
        consisting of just the entity set name.  The default url may be
        overridden using :meth:`set_url`."""
        if not self.in_service:
            return None
        elif self.url is not None:
            return self.url
        else:
            return uri.URI.from_octets(
                uri.escape_data(self.name.encode('utf-8')))

    def set_url(self, url):
        self.url = url


class EntitySet(EntityBinding):

    """Represents an EntitySet in the OData model.

    Calling an instance returns an :class:`data.EntitySetValue` bound to the
    service containing the EntitySet."""

    csdl_name = "EntitySet"

    def __init__(self, **kwargs):
        super(EntitySet, self).__init__(**kwargs)
        #: whether to advertise in the service document
        self.in_service = True

    def set_type(self, entity_type):
        """Sets the entity type for this entity set

        The entity_type must be closed before it can be used as the type
        of an entity set."""
        if not entity_type.key_defined():
            raise errors.ModelError(
                errors.Requirement.entity_set_abstract_s % self.qname)
        super(EntitySet, self).set_type(entity_type)
        self.type_def = types.EntitySetType(
            entity_type=entity_type, value_type=data.EntitySetValue)

    def set_in_service(self, in_service):
        """Sets whether or not to advertise this entity set

        in_service
            Boolean value, True meaning advertise in the service
            document"""
        self.in_service = in_service

    def set_url(self, url):
        if not self.in_service:
            raise errors.ModelError("EntitySet not advertised in service")
        else:
            self.url = url

    def __call__(self):
        esv = self.type_def()
        esv.set_entity_binding(self)
        if self.service_ref is not None:
            esv.bind_to_service(self.service_ref())
        return esv


class Singleton(EntityBinding):

    """Represents a Singleton in the OData model."""

    csdl_name = "Singleton"

    def __init__(self, **kwargs):
        super(Singleton, self).__init__(**kwargs)

    def set_type(self, entity_type):
        """Sets the entity type for this entity

        The entity_type must be closed before it can be used as the type
        of a singleton."""
        super(Singleton, self).set_type(entity_type)
        self.type_def = types.SingletonType(
            entity_type=entity_type, value_type=data.SingletonValue)

    def get_url(self):
        """Return a URI for this singleton

        Singletons are always advertised by the service so always have a
        URL.  By default the URI is a relative URI consisting of just
        the singleton's name.  The default url may be overridden using
        :meth:`set_url`."""
        if self.url is not None:
            return self.url
        else:
            return uri.URI.from_octets(
                uri.escape_data(self.name.encode('utf-8')))

    def __call__(self):
        sv = self.type_def()
        sv.set_entity_binding(self)
        if self.service_ref is not None:
            sv.bind_to_service(self.service_ref())
        sv.freeze()
        return sv


class ActionImport(types.Annotatable, names.Named):

    csdl_name = "ActionImport"

    def __init__(self, **kwargs):
        super(ActionImport, self).__init__(**kwargs)
        self.action_def = None
        self.service_ref = None
        self.in_service = False

    def set_action(self, action_def):
        self.action_def = action_def

    def set_in_service(self, in_service):
        self.in_service = in_service

    def bind_to_service(self, service_ref):
        """Binds this FunctionImport to a data service

        service_ref
            A weak reference to the service

        A ActionImport can only be bound to a single service."""
        self.service_ref = service_ref

    def get_url(self):
        """Return a URI for this ActionImport

        ActionImports that are bound to a service have a URL comprised
        of the service root followed by the ActionImport name.  By
        default the URI is a relative URI consisting of just the
        ActionImport name."""
        if not self.in_service:
            return None
        else:
            return uri.URI.from_octets(
                uri.escape_data(self.name.encode('utf-8'))).resolve(
                    self.service_ref().context_base)

    def __call__(self):
        """Returns a :class:`CallableValue` instance"""
        if not self.service_ref:
            raise errors.UnboundValue(
                "Can't call %s in unbound EntityModel" % self.name)
        if self.action_def is None:
            raise errors.ODataError("No matching Action declared")
        avalue = self.action_def()
        avalue.set_callable_binding(self)
        avalue.bind_to_service(self.service_ref())
        return avalue


class FunctionImport(types.Annotatable, names.Named):

    csdl_name = "FunctionImport"

    def __init__(self, **kwargs):
        super(FunctionImport, self).__init__(**kwargs)
        self.function_def = None
        self.service_ref = None
        self.in_service = False
        # the URL of this FunctionImport within a published container
        self.url = None

    def set_function_overload(self, function_def):
        self.function_def = function_def

    def set_in_service(self, in_service):
        self.in_service = in_service

    def bind_to_service(self, service_ref):
        """Binds this FunctionImport to a data service

        service_ref
            A weak reference to the service

        A FunctionImport can only be bound to a single service."""
        self.service_ref = service_ref

    def get_url(self):
        """Return a URI for this FunctionImport

        FunctionImports that are bound to a service have a URL comprised
        of the service root followed by the FunctionImport name.  By
        default the URI is a relative URI consisting of just the
        FunctionImport name."""
        if not self.in_service:
            return None
        elif self.url is not None:
            return self.url
        else:
            return uri.URI.from_octets(
                uri.escape_data(self.name.encode('utf-8')))

    def set_url(self, url):
        self.url = url

    def __call__(self, params=None):
        """Returns a :class:`CallableValue` instance

        params
            An optional list of parameter names used for disambiguation
            in cases where the FunctionImport points to an overloaded
            function.  If the Function is not overloaded this may be
            omitted."""
        if not self.service_ref:
            raise errors.UnboundValue(
                "Can't call %s in unbound EntityModel" % self.name)
        f_def = self.function_def.resolve(None, params)
        if f_def is None:
            raise errors.ODataError("No matching Function declared")
        fvalue = f_def()
        fvalue.set_callable_binding(self)
        fvalue.bind_to_service(self.service_ref())
        return fvalue


edm = Schema.edm_init()
odata = Schema.odata_init()
