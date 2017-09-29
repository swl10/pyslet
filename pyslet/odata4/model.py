#! /usr/bin/env python

import collections
import contextlib
import logging
import weakref

from . import errors
from . import parser
from . import primitive
from . import types

from .. import rfc2396 as uri
from ..py2 import (
    is_text,
    long2,
    to_text,
    ul,
    )
from ..xml import xsdatatypes as xsi


class EntityModel(types.NameTable):

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

    def check_name(self, name):
        """EntityModels contain schemas that define namespaces

        The syntax for a namespace is a dot-separated list of simple
        identifiers."""
        if name is None:
            raise ValueError("unnamed schema")
        if not self.is_namespace(name):
            raise ValueError("%s is not a valid namespace" % name)

    def check_value(self, value):
        """EntityModels can only contain Schemas"""
        if not isinstance(value, Schema):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<EntityModel>" if self.name is None else self.name))

    def qualified_get(self, qname, default=None):
        """Looks up qualified name in this entity model.

        qname
            A string or a :class:`QualifiedName` instance.

        default (None)
            The value to return if the name is not declared."""
        if isinstance(qname, types.QualifiedName):
            namespace, name = qname
        else:
            namespace, name = self.split_qname(qname)
        try:
            return self[namespace][name]
        except KeyError:
            return default

    def qualified_tell(self, qname, callback):
        """Deferred qualified name lookup.

        Similar to :meth:`Nametable.tell` except that it waits until
        both the Schema containing qname is defined *and* the target
        name is defined within that Schema.

        If the entity model or the indicated Schema is closed without
        qname being declared then the callback is called passing None."""
        nsname, name = self.split_qname(qname)

        def _callback(ns):
            if ns is None:
                callback(None)
            else:
                ns.tell(name, callback)

        self.tell(nsname, _callback)

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
                if isinstance(item, StructuredType):
                    item.set_annotations()
                    item.check_navigation()

    def derived_types(self, base):
        """Generates all types derived from base"""
        for name, schema in self.items():
            if name != schema.name:
                # ignore schema aliases
                continue
            for n, item in schema.items():
                if isinstance(item, StructuredType) and \
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
            if schema.name != sname or schema.name in ("Edm", "odata"):
                # skip aliases and reserved schemas
                continue
            for item in schema.values():
                if isinstance(item, types.NominalType):
                    logging.debug("Binding type: %s", item.qname)
                    item.bind_to_service(self.service_ref)
        for item in self.get_container().values():
            if isinstance(item, (EntitySet, Singleton)):
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


class Schema(types.Annotatable, types.NameTable):

    """A Schema is a container for OData model definitions."""

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
            The definition of an annotation term."""
        if not isinstance(value, (types.Term,
                                  types.NominalType, EntityContainer)):
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
            if isinstance(item, types.NameTable) and not item.closed:
                logging.warning("Circular reference detected: %s", item.qname)
                if isinstance(item, (ComplexType, EntityType)):
                    try:
                        item.is_derived_from(item, strict=True)
                    except errors.InheritanceCycleDetected:
                        raise errors.InheritanceCycleDetected(
                            (errors.Requirement.et_cycle_s if
                             isinstance(item, EntityType) else
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
        complex_base = ComplexType()
        complex_base.declare(cls.edm, "ComplexType")
        complex_base.set_abstract(True)
        complex_base.close()
        entity_base = EntityType()
        entity_base.declare(cls.edm, "EntityType")
        entity_base.set_abstract(True)
        entity_base.close()
        primitive.edm_geography.declare(cls.edm, "Geography")
        primitive.edm_geometry.declare(cls.edm, "Geometry")
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
                ('GeographyPoint', primitive.edm_geography_point),
                ('GeographyLineString', primitive.edm_geography_line_string),
                ('GeographyPolygon', primitive.edm_geography_polygon),
                ('GeographyMultiPoint', primitive.edm_geography_multi_point),
                ('GeographyMultiLineString',
                 primitive.edm_geography_multi_line_string),
                ('GeographyMultiPolygon',
                 primitive.edm_geography_multi_polygon),
                ('GeographyCollection', primitive.edm_geography_collection),
                ('GeometryPoint', primitive.edm_geometry_point),
                ('GeometryLineString', primitive.edm_geometry_line_string),
                ('GeometryPolygon', primitive.edm_geometry_polygon),
                ('GeometryMultiPoint', primitive.edm_geometry_multi_point),
                ('GeometryMultiLineString',
                 primitive.edm_geometry_multi_line_string),
                ('GeometryMultiPolygon', primitive.edm_geometry_multi_polygon),
                ('GeometryCollection', primitive.edm_geometry_collection)):
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


class EnumerationType(types.NameTable, types.NominalType):

    """An EnumerationType declaration"""

    def __init__(self, base=None, **kwargs):
        super(EnumerationType, self).__init__(**kwargs)
        if base is None:
            base = edm['Int32']
        elif base not in (edm['Byte'], edm['SByte'], edm['Int16'],
                          edm['Int32'], edm['Int64']):
            raise errors.ModelError(errors.Requirement.ent_type_s % base.qname)
        #: whether or not values are being auto-assigned None means
        #: 'undetermined', only possible when there are no members
        self.assigned_values = None
        #: whether or not this type is a flags-based enumeration
        self.is_flags = False
        #: the list of members in the order they were declared
        self.members = []
        # a mapping from values to the first declared member with that
        # value
        self._valuetable = {}
        self.value_type = EnumerationValue
        super(EnumerationType, self).set_base(base)

    def set_is_flags(self):
        """Sets is_flags to True.

        If the Enumeration already has members declared will raise
        ModelError."""
        if self.members:
            raise errors.ModelError(
                "Can't set is_flags on Enumeration with existing members")
        self.assigned_values = False
        self.is_flags = True

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed member")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        if not isinstance(value, Member):
            raise TypeError("Member required, found %s" % repr(value))
        # The value of the Member must be None (for auto assigned) or a
        # valid value of the base type
        if value.value is not None:
            v = self.base()
            try:
                v.set_value(value.value)
            except ValueError as err:
                raise errors.ModelError(
                    errors.Requirement.ent_valid_value_s %
                    ("%s: %s" % (self.qname, str(err))))

    def __setitem__(self, key, value):
        self.check_value(value)
        if self.assigned_values is None:
            self.assigned_values = value.value is None
        if self.assigned_values:
            if value.value is not None:
                raise errors.ModelError(
                    "Enum member %s declared with unexpected value" %
                    value.name)
            value.value = len(self.members)
            try:
                super(EnumerationType, self).__setitem__(key, value)
            except (ValueError, TypeError):
                # remove the auto-assigned value
                value.value = None
                raise
        else:
            if value.value is None:
                if self.is_flags:
                    raise errors.ModelError(
                        errors.Requirement.ent_nonauto_value_s %
                        ("%s:%s" % (self.qname, value.name)))
                else:
                    raise errors.ModelError(
                        errors.Requirement.ent_auto_value_s %
                        ("%s:%s" % (self.qname, value.name)))
            super(EnumerationType, self).__setitem__(key, value)
        self.members.append(value)
        self._valuetable.setdefault(value.value, value)

    def lookup(self, name_or_value):
        """Looks up a Member by name or value

        Returns the :class:`Member` instance.  If name_or_value is not
        the name or the value of a member then ValueError is raised. If
        name_or_value is an integer and multiple Members match then the
        first declared Member is returned."""
        try:
            if is_text(name_or_value):
                return self[name_or_value]
            elif isinstance(name_or_value, (int, long2)):
                return self._valuetable[name_or_value]
            else:
                raise ValueError("integer or string required")
        except KeyError:
            raise ValueError(
                "%s is not defined in %s" % (name_or_value, self.name))

    def lookup_flags(self, value):
        """Returns a list of Members that comprise this value

        For use with Enumerations that have :attr:`is_flags` set to
        True. Returns a compact list of members (in declaration order)
        that combine to make the input value.

        In the simplest case, where flags are defined using 1, 2, 4,
        etc. then this will just be the list of flags corresponding to
        the bits set in value.  In more complex examples where
        Enumerations define Members that combine flags then powerful
        Members are favoured over less powerful ones.  I.e., a Member
        with value 3 will be returned in preference to a list of two
        members with values 1 and 2.

        If :attr:`is_flags` is False, throws TypeError."""
        result = []
        rmask = 0
        for m in self.members:
            if m.value & value == m.value:
                # m is a candidate for adding to the result but does it
                # add any value?  Don't add superfluous multi-flags for
                # the sake of it.
                add_m = (m.value & rmask != m.value)
                i = 0
                while i < len(result):
                    match = result[i]
                    # if match is masked by (but not equal to m) then
                    # remove it from the result.  This rule ensures that
                    # 1 and 2 will be removed in favour or 3
                    if match.value & m.value == match.value:
                        del result[i]
                        # but we better add m now!
                        add_m = True
                    else:
                        i += 1
                if add_m:
                    result.append(m)
                    # expand rmask
                    rmask |= m.value
        return result

    def value_from_str(self, src):
        """Constructs an enumeration value from a source string"""
        p = parser.Parser(src)
        v = self()
        mlist = p.require_enum_value()
        if not self.is_flags:
            if len(mlist) != 1:
                raise errors.ModelError(
                    "Enum member: expected single name or value")
            v.set_value(mlist[0])
        else:
            v.set_value(mlist)
        p.require_end()
        return v


class Member(types.Named):

    """Represents a member of an enumeration"""

    def __init__(self, **kwargs):
        super(Member, self).__init__(**kwargs)
        #: the integer value corresponding to this member
        #: defaults to None: auto-assigned when declared
        self.value = None


class EnumerationValue(types.Value):

    """Represents the value of an Enumeration type"""

    def __init__(self, type_def, pvalue=None, **kwargs):
        super(EnumerationValue, self).__init__(type_def, **kwargs)
        self.value = None
        if pvalue is not None:
            self.set_value(pvalue)

    def is_null(self):
        return self.value is None

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        elif self.type_def.is_flags:
            return ul(',').join([v.name for
                                 v in self.type_def.lookup_flags(self.value)])
        else:
            return self.type_def.lookup(self.value).name

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of an enum value is the
        qualified name of the enum type followed by the quoted enum
        value."""
        if self.value is None:
            return "null"
        else:
            return "%s'%s'" % (self.type_def.qname, to_text(self))

    def get_value(self):
        """Returns a representation of the value

        The result is a string or, for flags enumerations, a tuple
        of strings or None if the value is null."""
        if self.value is None:
            return None
        elif self.type_def.is_flags:
            return tuple(
                m.name for m in self.type_def.lookup_flags(self.value))
        else:
            return self.type_def.lookup(self.value).name

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        Accepts None (meaning null), integer, string or iterable objects
        that yield integer and/or strings (mixtures are acceptable).
        Other types raise TypeError.

        Strings and values are converted to enum members through look-up
        and (for flags) bitwise OR operation.  If a value is not
        defined in the enumeration then ValueError is raised.  Note
        that with flags enumerations you may *only* set the (integer) value
        to an integer representing multiple flags *if* that value has
        a defined name.  For example, if you have Red=1 and Blue=2 as
        members then you may::

            v.set_value(1)
            v.set_value(2)
            v.set_value((1, 2))

        however, you may *not*::

            v.set_value(3)

        This rule has implications for the use of 0 which, for a flags
        enumeration, means no flags are set.  You *must* define a member
        with value of 0 if you want to use this value.  E.g., extending
        the above example define Black=0 if you want to do this::

            v.set_value(0)"""
        if value is None:
            self.value = value
        elif is_text(value) or isinstance(value, (int, long2)):
            self.value = self.type_def.lookup(value).value
        elif self.type_def.is_flags:
            # iterate over the values
            total_value = 0
            count = 0
            try:
                for v in value:
                    count += 1
                    total_value |= self.type_def.lookup(v).value
            except TypeError:
                raise TypeError("int, str or iterable thereof required")
            if not count:
                raise ValueError("Enum member name or value expected")
            self.value = total_value
        else:
            raise TypeError("Enum member or value expected")


class CollectionType(types.NominalType):

    """Collections are treated as types in the model

    In fact, OData does not allow you to declare a named type to be a
    collection, instead, properties, navigation properties and entity
    collections define collections in terms of single-valued named types.

    To make implementing the model easier we treat these as private type
    definitions.  That is, type definitions which are never declared in
    the associated schema but are used as the type of other elements
    that are part of the model."""

    def __init__(self, item_type, **kwargs):
        super(CollectionType, self).__init__(**kwargs)
        #: the type being collected, we do not allow collections of
        #: collections
        self.item_type = item_type
        self.value_type = CollectionValue


class CompositeValue(types.Value):

    """An abstract class for values that support query options

    The :attr:`options` attribute contains query options that are in
    force for this container.  The type of options that apply will
    depend on the type of the container.  The object is either None,
    indicating that default options should be assumed or an instance of
    one of the options classes (see concrete implementations for
    details)."""

    def __init__(self, **kwargs):
        super(CompositeValue, self).__init__(**kwargs)
        #: the (system query) options that are in force
        self.options = None
        self._options_inherited = True
        #: whether or not we are a collection
        self.is_collection = True

    #: the class to use for the options attribute
    OptionsType = types.CollectionOptions

    def _clone_options(self):
        if self.options:
            self.options = self.options.clone()
        else:
            self.options = self.OptionsType()
        self._options_inherited = False

    def _set_options(self, options, type_cast=None):
        # Internal method used to implement option inheritance, this
        # ensures that one options object is shared over all values that
        # use it, e.g., when expanding a navigation property lots of
        # entity values will contain the property and inherit any
        # options set on the original expansion.
        if self.options is not None:
            raise errors.ODataError("container options already set")
        # dump all our data, this is a significant change
        self.clear_cache()
        self.options = options
        self._options_inherited = True
        if type_cast is not None:
            self.type_cast(type_cast)

    def set_options(self, options_dict):
        """Sets the options for this container

        options_dict
            A dictionary mapping option name (e.g., "$filter") to a
            character string representing the option's value as per the
            syntax for options defined in the specification.

        All existing options are cleared and replaced with those
        parsed from the new dictionary."""
        raise NotImplementedError

    def get_applicable_type(self):
        """Returns the type that any options are applicable to

        For structured types this is the type itself, for containers
        this is the type of the items they contain."""
        raise NotImplementedError

    def type_cast(self, new_type):
        """Abstract method to implement type casting of a value

        new_type
            An instance of :class:`NominalType` that *must* be in the
            same type hierarchy as the existing applicable type and
            *must* be derived from the applicable base type (used to
            create the value).

        For values of structured types the applicable type is the type
        of the value itself, for containers (e.g., collections) the
        applicable type is the type of the contained items.

        This function is used to implement a dynamic type-cast such as
        when an entity set or collection valued property is cast to a
        type derived from the type stipulated by the original
        declaration.

        In theory, primitive types (including enumeration types) can be
        cast too because Collection(Edm.PrimitiveType) is well defined
        within the model *but* there are significant restrictions in the
        specification on when this construct can be used so, in
        practice, type casts almost always relate to complex or entity
        types (or containers thereof).

        You may not cast a frozen value."""
        raise NotImplementedError

    def select(self, path):
        """Selects a structural property

        path
            As per :meth:`EntityType.split_path`.

        Can only be applied when the applicable type is an *Entity*
        type. Although it may seem well-defined to use select for
        Complex values the specification does not allow the use of
        $select/$expand on queries that identify complex values.  You
        can still select properties within complex values but you must
        do it using the full path of the property within the entity.

        This method allows you to traverse complex types *and* navigation
        properties.  This may result in an expand option being set or
        modified rather than a simple select option being set.  For
        example::

            people.select("Friends/UserName")

        might translate into an *expand* option::

            $expand=Friends($select=UserName)

        Bear in mind that, by default, there are no select rules in
        place resulting in a default set of (typically all) structural
        properties being retrieved.  Setting explicit select rules is
        used to *restrict* the set of returned properties.

        The cache is automatically cleared."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, EntityType):
            raise errors.ODataError(
                "Can't resolve select path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            path,
            context=self.service.model if self.service is not None else None,
            navigation=False)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths[:-1]:
            # add a simple expand item for each parent path if it isn't
            # already expanded
            xitem = options.get_expand_item(path)
            if xitem is None:
                xitem = options.add_expand_path(path)
            options = xitem.options
        path = paths[-1]
        options.add_select_path(path)
        self.clear_cache()

    def select_default(self, xpath=None):
        """Sets the selection to the default seletion

        Can only be applied when the applicable type is an *Entity*
        type.  The default selection is indicated by the absence of a
        $select query option.

        xpath (None)
            An optional path (see :meth:`EntityType.split_path`) to a
            navigation property.

        With no xpath, this method effectively removes the $select
        option from future queries.  With an xpath, it removes the
        $select option from the $expand rule in effect for that path. If
        xpath is given but is not expanded no action is taken."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, EntityType):
            raise errors.ODataError(
                "select requires entity type, not %s" % repr(app_type))
        if xpath:
            options = self._resolve_xpath(xpath)
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.clear_select()
        self.clear_cache()

    def expand(self, path, qualifier=None):
        """Expands a navigation property

        path
            As per :meth:`EntityType.split_path`.

        qualifier
            An optional path qualifier, one of the values from
            :class:`types.PathQualifier`.  Only $count and
            $ref are allowed.  These options determine how much data is
            retrieved for the expanded navigation property.

        This method allows you to traverse complex types *and*
        navigation properties though the path must terminate in a
        navigation property.  This may result in nested expand options
        being set, for example::

            people.expand("Friends/Friends")

        might translate into::

            $expand=Friends($expand=Friends)

        The use of path qualifiers enables you to suppress the return
        of detailed information from the service while still creating
        the indicated object in the parent entity's property dictionary.
        For example::

            people.expand("Friends", PathQualifier.ref)

        Will cause the contained entities to have a "Friends" property
        defined in their property dictionary and you'll be able to
        iterate through the resulting values and use the len function
        without causing additional service requests (assuming the result
        is within any server paging limits) but the resulting entity
        objects are only references to the associated entities. If you
        drill down on one of the associated Friends, say by accessing a
        named structural property, this will trigger the request to
        retrieve the entity itself from the data service."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, EntityType):
            raise errors.ODataError(
                "Can't resolve expand path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            path,
            context=self.service.model if self.service is not None else None,
            navigation=True)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths[:-1]:
            # add a simple expand item for each parent path if it isn't
            # already expanded
            xitem = options.get_expand_item(path)
            if xitem is None:
                xitem = options.add_expand_path(path)
            options = xitem.options
        path = paths[-1]
        options.add_expand_path(path, qualifier=qualifier)
        self.clear_cache()

    def collapse(self, path):
        """Collapses a navigation property

        path
            As per :meth:`EntityType.split_path`."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, EntityType):
            raise errors.ODataError(
                "Can't resolve expand path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            path,
            context=self.service.model if self.service is not None else None,
            navigation=True)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths[:-1]:
            xitem = options.get_expand_item(path)
            if xitem is None:
                # we're done, we weren't even expanded
                return
            options = xitem.options
        path = paths[-1]
        options.remove_expand_path(path)
        self.clear_cache()

    def set_filter(self, filter_expr, xpath=None):
        """Sets the filter for this value (or a related value)

        filter_expr
            A :class:`types.CommonExpression` instance or a string
            from which one can be parsed.

        xpath (None)
            An optional path (see :meth:`EntityType.split_path`) to a
            navigation property.  Can only be used when the applicable
            type is an entity.

            The filter is applied to the entity set(s) expanded from
            this navigation property.  If this path has not been
            expanded then :meth:`expand` is used to add it
            automatically.

        With no xpath, can only be applied to a collection or entity
        set."""
        if is_text(filter_expr):
            p = parser.Parser(filter_expr)
            filter_expr = p.require_filter()
            p.require_end()
        self.clear_cache()
        if xpath:
            options = self._resolve_xpath(xpath)
        elif not self.is_collection:
            raise errors.ODataError("%s is not a collection" % repr(self))
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.set_filter(filter_expr)

    def set_search(self, search_expr, xpath=None):
        """Sets the search expression for the result set"""
        raise NotImplementedError

    def set_orderby(self, orderby_expr, xpath=None):
        """Sets the orderby expression for the result set

        orderby_expr
            A list or iterable of :class:`types.OrderByItem` instances
            or a string from which one can be parsed.

        xpath (None)
            As per :meth:`set_filter`.

        With no xpath, can only be applied to a collection or entity
        set.  With an xpath you can also apply a filter to a
        singleton."""
        if is_text(orderby_expr):
            p = parser.Parser(orderby_expr)
            orderby_expr = p.require_orderby()
            p.require_end()
        self.clear_cache()
        if xpath:
            options = self._resolve_xpath(xpath)
        elif not self.is_collection:
            raise errors.ODataError("%s is not a collection" % repr(self))
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.set_orderby(orderby_expr)

    def set_page(self, top, skip=0, xpath=None):
        """Sets the page for the result set

        top
            An integer to limit the size of the collection or None for
            unlimited.

        skip
            An integer used to exclude items from the contained
            collection or 0 (the default) if no items should be
            excluded.

        xpath (None)
            As per :meth:`set_filter`.

        With no xpath, can only be applied to a collection or entity
        set."""
        self.clear_cache()
        if xpath:
            options = self._resolve_xpath(xpath)
        elif not self.is_collection:
            raise errors.ODataError("%s is not a collection" % repr(self))
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.set_top(top)
        if skip == 0:
            skip = None
        options.set_skip(skip)

    def get_page_size(self):
        """Returns the maximum size of a collection

        Returns the value of top previously set by set_page, None
        indicates that there is not limit on the size of the
        collection."""
        if self.options:
            return self.options.top
        else:
            return None

    def _resolve_xpath(self, xpath):
        # returns the options for this xpath expanding as required
        app_type = self.get_applicable_type()
        if not isinstance(app_type, EntityType):
            raise errors.ODataError(
                "Can't resolve expand path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            xpath, context=self.service.model if self.service is not None
            else None, navigation=True)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths:
            xitem = options.get_expand_item(path)
            if xitem is None:
                xitem = options.add_expand_path(path)
            options = xitem.options
        return options


class ContainerValue(CompositeValue):

    """Abstract value type for containers

    Containers are either collections (of primitive, complex or entity
    types) or Singletons which behave in some ways like collections of
    (up to) one entity.

    The type_def attribute points to the type of the *container*, not to
    the type of the item, a separate attribute :attr:`item_type` is used
    to point to the type definition of the contained objects."""

    def __init__(self, **kwargs):
        super(ContainerValue, self).__init__(**kwargs)
        #: the type contained by this value
        self.item_type = self.type_def.item_type

    @contextlib.contextmanager
    def loading(self, next_link=None):
        """Used during deserialization"""
        raise NotImplementedError

    def load_item(self, obj):
        """Used during deserialization"""
        raise NotImplementedError

    def get_applicable_type(self):
        """Returns the current item type"""
        return self.item_type

    def type_cast(self, new_type):
        """Constrains value to contain only objects of the given type

        See: :meth:`CompositeValue.type_cast`.

        For containers the applicable type is the item type they
        contain. The original item type is referred to as the base type
        and is always available as::

            self.type_def.item_type

        The :attr:`item_type` attribute refers to the current item type
        taking into consideration any type cast in effect.

        You can think of these container-level type-casts as if they
        were a special kind of filter on the container (hence they are
        managed in tandem with other query options).  It is important to
        be aware that with a type cast in effect you are only seeing a
        partial view of the original container's contents."""
        if self.frozen:
            raise errors.FrozenValueError
        if new_type is self.item_type:
            # nothing to do
            return
        if not new_type.is_derived_from(self.type_def.item_type):
            raise TypeError("Incompatible types: %s -> %s" %
                            (self.type_def.item_type.qname, new_type.qname))
        self.item_type = new_type
        self.clear_cache()

    def new_item(self):
        """Creates a new value suitable for this container

        This method creates a new transient value, it does not add it to
        the container.  To add the resulting value to the container use
        the appropriate container-specific action.

        You should always use this method to create a new item as it
        ensures that any options applied to the container (particularly
        select and expand options) are correctly applied to the new
        value too before it is added to the container.

        The new value will be of the type indicated by the attribute
        :attr:`item_type` so it includes any type cast that is in
        effect. Furthermore, the value is created directly to be of
        that type (it is not itself type cast) making it the base type
        for the new value.

        This is a subtle distinction but it means that the new value
        cannot be cast back to the base type of this container because a
        value of the derived type is required (by the container's type
        cast). In OData URL syntax you can see the difference in the
        position of the key predicate when the container is an entity
        set::

            service/People/Schema.Employee('kristakemp')

        illustrates the form of URL when the entity set People is type
        cast to show Employees only and the entity with key 'kristakemp'
        is looked up in the sub-set of entities of that type.

        On the other hand, the following URL shows a look up in the
        default entity set (of all People) but returning the specific
        entity with key 'kristakemp' only if it is of type Empolyee::

            service/People('kristakemp')/Schema.Employee

        (At the time of writing the Trippin service from where these
        examples were taken, doesn't handle this in the expected way and
        returns 204 No Content rather than 404 Not Found.)

        Anyway, in the latter case the type cast is applied to the
        entity and not to the entity set.  For a specific entity the
        effect is the same, the difference is whether or not the
        restriction is applied to the container value itself.

        In the rare case of a container of abstract primitive types,
        i.e., Collection(Edm.PrimitiveType), you will get back a
        :class:`primitive.PrimitiveValue` object that does not, itself,
        support further type casting (and is always null).  To put a
        concrete value into the container you will either have to cast
        the container (assuming there is a concrete class that can
        represent all items) and use this method or simply create the
        value directly from the appropriate primitive type yourself."""
        item = self.item_type()
        # now implement the entity options, select and expand
        if isinstance(item, (ComplexValue, EntityValue)):
            item._set_options(self.options)
        return item


class CollectionValue(collections.MutableSequence, ContainerValue):

    """Represents the value of a Collection

    The type_def is required on construction.  There is no default
    collection type.

    The CollectionValue object is blessed with Python's Sequence
    behaviour."""

    def __init__(self, **kwargs):
        super(CollectionValue, self).__init__(**kwargs)
        self._fullycached = True
        self._cache = []
        self._next_link = None

    def set_value(self, value):
        """Sets the value from a python 'native' value representation"""
        if value is None:
            raise TypeError("Collection values cannot be null")
        elif isinstance(value, (list, collections.Sequence)):
            with self.loading() as seq:
                for new_value in value:
                    v = seq.new_item()
                    v.set_value(new_value)
                    seq.load_item(v)
            self.touch()
        else:
            raise TypeError

    @contextlib.contextmanager
    def loading(self, next_link=None):
        self._next_link = next_link
        if self.service is None:
            # an unbound collection is simpler
            self._fullycached = True
            self._cache = []
            yield self
        else:
            # called via a _load method that has cleared cache
            yield self
            self._fullycached = next_link is None
            max_size = self.get_page_size()
            if max_size is not None:
                # we ignore next_link if we asked to limit the page
                self._fullycached = self._fullycached or \
                    len(self._cache) >= max_size
                if self._fullycached:
                    self._next_link = None
        self.clean()

    def load_item(self, obj):
        self._cache.append(obj)

    def clear_cache(self):
        """Clears the local cache for this collection

        If this collection is bound to a service then any locally cached
        information about the entities is cleared."""
        if self.service is not None:
            self._fullycached = False
            del self._cache[:]

    def reload(self):
        """Reload the contents of this collection from the service

        This collection must be bound to a service.  The cache is cleared
        and reloaded from the service."""
        if self.service is None:
            raise errors.UnboundValue
        self.clear_cache()
        self._load()

    def is_null(self):
        """CollectionValues are *never* null

        CollectionValues highlight the distinction between the default
        Python boolean test and the OData definition of null.  The
        native Python Sequence behaviour overrides the default
        :class:`types.Value` implementation of the boolean test.  In other
        words::

            if collection_value:
                # do something if a CollectionValue instance is 'True'

        will test whether or not the collection is empty, not if it's
        null."""
        return False

    def __len__(self):
        if self._fullycached:
            return len(self._cache)
        else:
            # we need to determine our contextual object and iterate it
            raise NotImplementedError

    def _is_cached(self, index):
        if isinstance(index, slice):
            if index.stop is None or index.stop < 0:
                return False
            else:
                return index.stop < len(self._cache)
        elif index < 0:
            return False
        else:
            return index < len(self._cache)

    def _check_type(self, value):
        if not value.type_def.is_derived_from(self.type_def.item_type):
            raise ValueError
        return value

    def __getitem__(self, index):
        if self._fullycached or self._is_cached(index):
            return self._cache[index]
        else:
            self._load(index)
            return self._cache[index]

    def __setitem__(self, index, value):
        if self.frozen:
            raise errors.FrozenValueError
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load()
        if isinstance(index, slice):
            # value must be an iterable of appropriate values
            self._cache[index] = [self._check_item(item) for item in value]
        else:
            self._cache[index] = self._check_type(value)
        self.touch()

    def __delitem__(self, index):
        if self.frozen:
            raise errors.FrozenValueError
        if isinstance(index, slice):
            if index.stop is None and index.step is None:
                # special case: delete everything past start.  We
                # optimise here as we don't need to load the remote data
                # just to mark it as being deleted, we have everything
                # cached that needs to be cached!
                if index.start is None or self._is_cached(index.start):
                    self._fullycached = True
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load()
        del self._cache[index]
        self.touch()

    def insert(self, index, value):
        if self.frozen:
            raise errors.FrozenValueError
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load()
        self._cache.insert(index, value)
        self.touch()

    def _load(self, index=None):
        # Load the cache up to and including index,  If index is None
        # then load the entire collection.  We always start from the
        # beginning because the remote data may have changed.
        self._fullycached = False
        del self._cache[:]
        request = self.service.get_collection(self)
        while request is not None:
            self._next_link = None
            # loading called during execution to populate _cache
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            if self._next_link:
                request = self.service.get_collection(
                    self, self._next_link)
                self._next_link = None
            else:
                request = None


class StructuredType(types.NameTable, types.NominalType):

    """A Structured Type declaration

    Structured types are nametables in their own right, behaving as
    dictionaries with property names as keys and :class:`Property` (or
    :class:`NavigationProperty`) instances as the dictionary values.

    While the declaration's nametable is open new properties can be
    added but once it is closed the type is considered complete.  There
    are some restrictions on which operations are allowed on
    complete/incomplete type declarations.  The most important being
    that the you can't use a type as a base type until is complete."""

    def __init__(self, **kwargs):
        super(StructuredType, self).__init__(**kwargs)
        #: whether or not this is an open type, None indicates undetermined
        self.open_type = None

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed property")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a name

        By default we qualify name by prefixing with the name of this
        NameTable (type) and "/" as per the representation of property
        paths. If this NameTable has not been declared then name is
        returned unchanged."""
        if self.name:
            return self.name + "/" + name
        else:
            return name

    def check_value(self, value):
        if not isinstance(value, (Property, NavigationProperty)):
            raise TypeError(
                "Property or NavigationProperty required, found %s" %
                repr(value))

    def set_base(self, base):
        """Sets the base type of this type

        When structured types are associated with a base type the
        properties of the base type are copied on closure, therefore the
        type must be incomplete when the base is set and the base MUST
        be closed before the derived type."""
        if not isinstance(base, type(self)):
            raise TypeError(
                "%s is not a suitable base for %s" % (base.qname, self.name))
        if self.closed:
            raise errors.ModelError(
                "Can't set base on %s (declaration is complete)" % self.qname)
        super(StructuredType, self).set_base(base)

    def set_abstract(self, abstract):
        if self.closed:
            raise errors.ModelError(
                "Can't set abstract on %s (declaration is complete)" %
                self.qname)
        self.abstract = abstract

    def set_open_type(self, open_type):
        if self.closed:
            raise errors.ModelError(
                "Can't set open_type on %s (declaration is complete)" %
                self.qname)
        self.open_type = open_type

    def navigation_properties(self):
        """Generates all navigation properties of this type

        This iterator will traverse complex types but *not* collections
        of complex types.  It yields tuples of (path, nav property)."""
        for n, p in self.items():
            if isinstance(p, NavigationProperty):
                yield n, p
            elif isinstance(p.type_def, ComplexType):
                for nn, np in p.type_def.navigation_properties():
                    yield "%s/%s" % (n, nn), np

    def check_navigation(self):
        for n, p in self.items():
            if isinstance(p, Property) and \
                    isinstance(p.type_def, CollectionType) and \
                    isinstance(p.type_def.item_type, ComplexType):
                # a collection of complex values
                for path, np in p.type_def.item_type.navigation_properties():
                    logging.debug("Checking %s.%s for containment" %
                                  (self.name, path))
                    if np.containment:
                        raise errors.ModelError(
                            errors.Requirement.nav_contains_s % p.qname)

    def close(self):
        # before we close this nametable, add in the declarataions from
        # the base type if present
        if self.closed:
            return
        if self.base is not None:
            if not self.base.closed:
                raise errors.ModelError(
                    "Base type is incomplete: %s" % self.qname)
            if self.base.open_type is not None:
                if self.base.open_type is True and self.open_type is False:
                    if isinstance(self, EntityType):
                        raise errors.ModelError(
                            errors.Requirement.et_open_base_s % self.qname)
                    elif isinstance(self, ComplexType):
                        raise errors.ModelError(
                            errors.Requirement.ct_open_base_s % self.qname)
                    else:
                        raise errors.ModelError
                if self.open_type is None:
                    self.open_type = self.base.open_type
            else:
                # no base type
                if self.open_type is None:
                    self.open_type = False
            # add the base names
            for pname, p in self.base.items():
                try:
                    p.declare(self, pname)
                except errors.DuplicateNameError:
                    raise errors.DuplicateNameError(
                        errors.Requirement.property_unique_s %
                        ("%s/%s" % (self.qname, pname)))
        # The types of all our structural properties MUST also be
        # complete.
        for pname, p in self.items():
            if isinstance(p, Property):
                t = p.type_def
                if t is None:
                    raise errors.ModelError("%s is undefined" % p.qname)
                if isinstance(t, CollectionType):
                    t = t.item_type
                if isinstance(t, StructuredType) and not t.closed:
                    raise errors.ModelError("%s is incomplete" % p.qname)
        super(StructuredType, self).close()

    def set_annotations(self):
        """Called during EntityModel closure

        Properties that refer to TypeDefinitions need to have
        annotations copied as these Annotations "are considered applied
        wherever the type definition is used".
        """
        try:
            for pname, p in self.items():
                if isinstance(p, Property):
                    if not p.is_owned_by(self):
                        # inherited
                        continue
                    t = p.type_def
                    if isinstance(t, CollectionType):
                        t = t.item_type
                    # this type is just the wrapper of the real type
                    t = t.base
                    if isinstance(t, primitive.PrimitiveType):
                        for annotation in t.annotations.values():
                            logging.debug(
                                "Annotating %s with %s", p.qname,
                                annotation.name)
                            annotation.declare(p.annotations, annotation.name)
        except errors.DuplicateNameError as err:
            raise errors.ModelError(
                errors.Requirement.td_annotation_s % to_text(err))

    def canonical_get(self, name, base_type=None):
        """Does a canonical lookup of a named property

        Returns a tuple of instances: (StructuredType, Property) after
        looking up a named property.

        The type returned is the most general type containing the named
        property.  This may be the current type but it may also be one
        of of the current types base types if the property is inherited.

        The optional base_type argument allows you to terminate the
        search early: if name is defined in base_type then base_type is
        returned even if the property was actually defined in one of
        *its* base types.

        This method is used in situations where a type-cast segment is
        given for a property, for example, suppose we have a type
        hierarchy of TypeC derived from TypeB which is, in turn, derived
        from TypeA. If property B is defined on TypeB then::

            TypeC.canonical_get("B")    # returns (TypeB, PropertyB)"""
        match_property = self[name]
        if base_type is not None and name in base_type:
            return (base_type, match_property)
        match_type = self
        ctype = self.base_type
        while ctype is not None and name in ctype:
            match_type = ctype
            ctype = ctype.base_type
        return (match_type, match_property)

    def resolve_sproperty_path(self, path, inheritance=True):
        """Resolves a property path

        path
            An array of strings representing the path.  There must be at
            least one segment.

        inheritance (default True)
            Whether or not to search inherited properties.  By default
            we do search them, the use cases for searching the set of
            limited properties defined by this entity type itself are
            limited to validation scenarios.  This restriction applies
            to the entity being searched, not to the types of complex
            properties (if any).

        This method will not resolve qualified names in the path so all
        items MUST be simple identifiers representing properties defined
        in the correspondig structural type.  In the simplest case path
        will comprise a single identifier of a primitive property but it
        may refer to complex properties (recursively) though not
        properties of derived complex properties.  The path MUST NOT
        include navigation properties.

        The upshot is that we return a property declaration of a
        structural property that is guaranteed to be valid for all
        instances of this structural type.

        This method can only be called once the type is complete."""
        if not self.closed:
            raise errors.ModelError("%s is incomplete" % self.qname)
        if not path:
            raise ValueError("Can't resolve empty property path")
        pos = 0
        t = self
        p = None
        try:
            while pos < len(path):
                logging.debug("resolve_sproperty_path searching in %s for %s",
                              t.qname, str(path[pos:]))
                if isinstance(t, CollectionType):
                    raise errors.PathError(
                        "%s is a collection" % p.qname)
                segment = path[pos]
                pos += 1
                if is_text(segment):
                    # must resole to a property of the current type
                    p = t[segment]
                    if isinstance(p, NavigationProperty):
                        raise errors.PathError(
                            "%s is a navigation property" % p.qname)
                    if not inheritance:
                        if not p.is_owned_by(t):
                            raise errors.PathError("%s is inherited" % p.qname)
                        inheritance = True
                    t = p.type_def
                else:
                    raise TypeError(
                        "Bad path segment %s" % repr(segment))
        except KeyError as err:
            raise errors.PathError("Path segment not found: %s" % str(err))
        return p

    def resolve_nppath(self, path, context, follow_containment=False,
                       require_containment=False):
        """Resolves a navigation property path

        path
            A list of strings and QualifiedName instances representing
            the path.  Any redundant segments are removed from the path
            during resolution ensuring that, on success, it is the
            canonical path to the returned navigation property.

        context
            The entity model within which to resolve qualified names.
            This won't necessarily be the entity model containing the
            definition of the EntityType itself as the type may be used
            through a reference in a separate schema that defines
            addition sub-types, changing the outcome of the path
            resolution algorithm.

        follow_containment
            A boolean, defaulting to False: don't traverse containinment
            navigation properties.  In this configuration the method
            behaves as per the resolution of partner paths in entity
            type definitions.  When set to True containment navigation
            properties are traversed (but will only be returned subject
            to require_containment below) as per the resolution of
            navigation binding paths.

        require_containment
            A boolean, defaulting to False: the resulting path must be a
            containment navigation property.  With both
            follow_containment and require_containment set the method
            behaves as per the resolution of a target path (excluding
            the entity set or singleton segments).

        The rules for following navigation property paths are different
        depending on the context. In Part 3, 7.1.4 they are defined
        as follows:

            The path may traverse complex types, including derived
            complex types, but MUST NOT traverse any navigation
            properties

        Whereas in Part 3, 13.4.1:

            The path can traverse one or more containment navigation
            properties but the last segment MUST be a non-containment
            navigation property and there MUST NOT be any
            non-containment navigation properties prior to the final
            segment"""
        pos = 0
        old_type = None
        from_type = self
        try:
            while pos < len(path):
                segment = path[pos]
                pos += 1
                if is_text(segment):
                    # must resolve to a property of this type
                    p = from_type[segment]
                    if old_type is not None:
                        # check the previous cast
                        best_type = from_type
                        base_type = from_type.base
                        while (best_type is not old_type and
                                segment in base_type):
                            best_type = base_type
                            base_type = base_type.base
                        if best_type is old_type:
                            # unnecessary cast
                            pos -= 1
                            del path[pos - 1]
                            from_type = old_type
                        elif best_type is not from_type:
                            # cast was over-specific, modify it
                            path[pos - 2] = best_type.get_qname()
                            from_type = best_type
                        old_type = None
                    if isinstance(p, NavigationProperty):
                        if follow_containment:
                            # navigation binding path
                            if p.containment:
                                if pos >= len(path):
                                    if require_containment:
                                        return p
                                    # or last segment can't be containment
                                    raise errors.ModelError(
                                        errors.Requirement.
                                        nav_contains_binding_s % self.qname)
                                from_type = p.entity_type
                                # continue to resolve
                            else:
                                # must be last segment
                                if pos < len(path):
                                    raise errors.ModelError(
                                        errors.Requirement.
                                        navbind_noncontain_s % self.qname)
                                if require_containment:
                                    raise errors.PathError(self.qname)
                                return p
                        else:
                            # partner path
                            if pos < len(path):
                                raise errors.ModelError(
                                    errors.Requirement.nav_partner_nav_s %
                                    p.name)
                            return p
                    else:
                        from_type = p.type_def
                        # must be a structured type, not a primitive or
                        # collection
                        if not isinstance(from_type, StructuredType):
                            raise errors.PathError(
                                "Can't resolve path containing: %s" %
                                repr(from_type))
                elif isinstance(segment, types.QualifiedName):
                    # a type-cast
                    new_type = context.qualified_get(segment)
                    if not isinstance(new_type, StructuredType):
                        raise errors.PathError(
                            "Can't resolve path containing: %s" %
                            repr(new_type))
                    if new_type.is_derived_from(from_type, strict=False):
                        # any derived type or the same type at this stage
                        old_type = from_type
                        from_type = new_type
                    else:
                        raise errors.PathError(
                            "Can't resolve cast from %s to %s" %
                            (from_type.qname, new_type.qname))
                else:
                    raise TypeError(
                        "Bad path segment %s" % repr(segment))
        except KeyError as err:
            raise errors.PathError("Path segment not found: %s" % str(err))
        # if we get here then the path finished at a complex property
        # or type-cast segment.
        raise errors.PathError("Path did not resolve to a navigation property")

    @staticmethod
    def path_to_str(path):
        """Static method for converting a path to a string

        path
            An array of strings and/or :class:`types.QualifiedName` named
            tuples.

        Returns a simple string representation with all components
        separated by "/"
        """
        return "/".join(
            [segment if is_text(segment) else
             (segment.namespace + "." + segment.name) for segment in path])


class Property(types.Annotatable, types.Named):

    """A Property declaration

    Properties are defined within a structured type.  The corresponding
    :class:`StructuredType` object therefore becomes the namespace in
    :which the
    property is first declared and the qname attribute is composed of
    the the type's qualified name and the property's name separated by a
    '/'.  The same property is also declared in any derived types as an
    alias."""

    def __init__(self, **kwargs):
        super(Property, self).__init__(**kwargs)
        #: the target structural type of this property
        self.structural_type = None
        #: whether or not this property points to a collection
        self.collection = None
        #: the type definition for values of this property
        self.type_def = None
        #: whether or not the property value can be null (or contain
        #: null in the case of a collection)
        self.nullable = True
        #: the default value of the property (primitive/enums only)
        self.default_value = None

    def set_type(self, structural_type, collection=False):
        self.structural_type = structural_type
        self.collection = collection
        if collection:
            self.type_def = CollectionType(item_type=structural_type)
        else:
            self.type_def = structural_type

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_default(self, default_value):
        self.default_value = default_value

    def __call__(self, parent_ref):
        value = self.type_def()
        if self.default_value:
            value.assign(self.default_value)
            value.clean()
        elif isinstance(value, ComplexValue) and not self.nullable:
            # a non-nullable complex value is set to be non-null
            # directly but there are no property values yet (the cache
            # is empty and will be created later)
            value.null = False
        value.set_parent(parent_ref, self.name)
        return value


class OnDeleteAction(xsi.Enumeration):

    """An enumeration used to represent OnDelete actions.
    ::

            OnDeleteAction.Cascade
            OnDeleteAction.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "Cascade": 1,
        "None": 2,
        "SetNull": 3,
        "SetDefault": 4
    }


class NavigationProperty(types.Named):

    """A NavigationProperty declaration"""

    def __init__(self, **kwargs):
        super(NavigationProperty, self).__init__(**kwargs)
        #: the target entity type of this property
        self.entity_type = None
        #: whether or not this property points to a collection
        self.collection = None
        #: The type definition to use for values of this navigation property.
        #: For collections, this is a :class:`CollectionType`.
        self.type_def = None
        #: The type definition to use for bound values of this
        #: navigation property.  For collections, this is an
        #: :class:`EntitySetType`.
        self.bound_def = None
        #: by default, navigation properties are nullable
        self.nullable = None
        #: whether of not the linked entities are contained
        self.containment = False
        #: the partner of this navigation property
        self.partner = None
        #: reverse partners are navigation properties that point back to
        #: us, there can be more than one but if the relationship is
        #: bidirectional there will *exactly* one and it will be the
        #: same object as self.partner.
        self.reverse_partners = []

    def set_type(self, entity_type, collection, contains_target=False):
        self.containment = contains_target
        self.entity_type = entity_type
        if collection:
            if self.nullable is not None:
                raise errors.ModelError(
                    errors.Requirement.nav_collection_exists_s % self.qname)
            # use a collection for unbound value creation, if values of
            # this property appear in contexts where they are bound to
            # an entity set then we will upgrade to an EntitySetValue at
            # that time.
            self.type_def = CollectionType(item_type=entity_type)
            self.bound_def = EntitySetType(entity_type=entity_type)
        else:
            if self.nullable is None:
                self.nullable = True
            if self.containment:
                self.type_def = entity_type
            else:
                self.type_def = SingletonType(entity_type=entity_type)
            self.bound_def = self.type_def
        self.collection = collection

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_partner(self, partner):
        if self.reverse_partners:
            if len(self.reverse_partners) > 1:
                raise errors.ModelError(
                    errors.Requirement.nav_partner_bidirection_s %
                    ("%s has multiple partners" % self.qname))
            if self.reverse_partners[0] is not partner:
                raise errors.ModelError(
                    errors.Requirement.nav_partner_bidirection_s %
                    ("%s is already partnered" % self.qname))
        self.partner = partner
        partner.reverse_partners.append(self)

    def add_constraint(self, dependent_path, principal_path):
        if self.nametable is None:
            raise errors.ObjectNotDeclaredError
        dependent_entity = self.nametable()
        principal_entity = self.entity_type
        try:
            dependent_property = dependent_entity.resolve_sproperty_path(
                dependent_path)
        except errors.PathError as err:
            raise errors.ModelError(
                errors.Requirement.refcon_ppath_s %
                ("%s: %s" % (self.qname, str(err))))
        try:
            principal_property = principal_entity.resolve_sproperty_path(
                principal_path)
        except errors.PathError as err:
            raise errors.ModelError(
                errors.Requirement.refcon_rppath_s %
                ("%s: %s" % (self.qname, str(err))))
        # these must be primitive properties
        if not isinstance(dependent_property.type_def,
                          primitive.PrimitiveType):
            raise errors.ModelError(
                errors.Requirement.refcon_ppath_s % self.qname)
        # the types of these properties MUST match
        if not dependent_property.type_def.match(principal_property.type_def):
            raise errors.ModelError(
                errors.Requirement.refcon_match_s % self.qname)
        if ((self.nullable is True or principal_property.nullable is True) and
                dependent_property.nullable is False):
            raise errors.ModelError(
                errors.Requirement.refcon_match_null_s % self.qname)
        if ((self.nullable is False and
                principal_property.nullable is False) and
                dependent_property.nullable is not False):
            raise errors.ModelError(
                errors.Requirement.refcon_match_notnull_s % self.qname)

    def add_action(self, action):
        pass

    def __call__(self, parent_ref, qualifier=None):
        if self.containment:
            # simpler case, we contain the entity (or collection)
            value = self.type_def()
            if not self.nullable:
                value.null = False
        else:
            # harder case, are we bound?
            p = parent_ref()
            path = [self.name]
            if self.name not in p.base_def:
                path.insert(0, self.nametable().qname)
            entity = p.get_entity(path)
            if entity.entity_binding is not None:
                target_set = entity.entity_binding.resolve_binding(tuple(path))
                if target_set:
                    value = self.bound_def()
                    value.set_entity_binding(target_set)
                else:
                    value = self.type_def()
            else:
                value = self.type_def()
        value.set_parent(parent_ref, self.name)
        return value


class StructuredValue(collections.Mapping, CompositeValue):

    """Abstract class that represents the value of a structured type

    Instances behave like dictionaries of property values keyed on
    property name.  On construction the value is *empty* (len returns 0)
    and evaluates to null.  The value automatically becomes non-null if
    you set a property value, directly using assignment::

        value['StringProperty'] = primitive.StringValue("Hello")

    or if you explicitly request the creation of property defaults::

        value.set_defaults()

    You can set a value back to null using::

        value.set_value(None).

    The range of properties that you can get and set is determined by
    the select/expand options that are in effect for the value.  These
    are typically set on creation and will vary depending on the
    context. For example, the :meth:`EntityContainerValue.new_item`
    method will create a new entity (a structured type) using the
    select/expand rules that are in effect for that container.

    If you create a transient value of a structured type directly by
    calling a type instance then all structural properties are selected.

    Recall that Value instances are either bound (to a service) or are
    transient.  Some operations are not permitted on bound values, for
    more details see the appropriate methods and the notes in the
    derived classes :class:`EntityValue` and :class:`ComplexValue`.

    In keeping with the other composite Value classes, structured values
    maintain an internal cache of the property values so you only
    generate one call to the underlying service to populate them. You
    may explicitly clear the cache to force a call to the service.

    The type definition used to create a structured value instance is
    considered special and is remembered as the :attr:`base_def` of the
    value throughout the value's life.  The actual type may change to a
    value derived from it but it may never be changed to a type that is
    more abstract.

    The following types may appear as values of properties:

    :class:`PrimitiveValue`
        For single valued primitive properties

    :class:`EnumerationValue`
        For single valued enumeration properties

    :class:`ComplexValue`
        For single valued complex propeties

    :class:`CollectionValue` (of any of the above)
        For collection valued structural properties.

    :class:`EntityValue`
        For single valued navigation properties that *contain* their
        target entity.

    :class:`SingletonValue`
        For single valued navigation properties that do *not contain*
        their target entity.

    :class:`EntitySetValue`
        For collection-valued navigation properties whether or not they
        contain the target entities.

    :class:`CollectionValue` (of :class:`EntityValue`)
        The rare case in which a collection valued navigation property
        is neither contained nor successfully bound to an entity set.
        Such properties are discouraged but not disallowed by the
        specification. The simpler collection results because there is
        no guarantee that all entities in the collection come from the
        same entity set and hence no guarantee that the keys are unique."""

    def __init__(self, **kwargs):
        super(StructuredValue, self).__init__(**kwargs)
        #: the (initial) base type definition
        self.base_def = self.type_def
        self.null = True
        self._cache = None
        self._loading = False

    def get_applicable_type(self):
        """Returns the *current* type definition"""
        return self.type_def

    def type_cast(self, new_type):
        """Casts this value to a new type

        You may not cast a *bound* structured value.  This restriction
        is imposed by the specification, to change the type of a complex
        value you must replace the value completely rather than modify
        in place. To change the type of an existing entity you would
        need to remove it and reinsert a new value of the desired type;
        this operation is not possible if keys are assigned
        automatically by the data service.

        The property dictionary is updated to reflect the change in type
        taking in to consideration any options applied to this value.
        The values of existing properties are not modified but bear in
        mind that, in the unusual case of a cast to a more general type,
        properties not defined in the new type are *removed* from the
        property dictionary.

        You can always obtain the (original) base type of the value from
        the attribute :attr:`base_type`."""
        if self.frozen:
            raise errors.FrozenValueError
        if self.service is not None and not self._loading:
            raise errors.BoundValue("type_cast on bound value")
        if new_type is self.type_def:
            # nothing to do
            return
        if not new_type.is_derived_from(self.base_def):
            raise TypeError("Incompatible types: %s -> %s" %
                            (self.base_type.qname, new_type.qname))
        self.type_def = new_type
        # a transient value, modify the values in place
        self._init_cache(clear=False)

    def clear_cache(self):
        """Clears the local cache of property values."""
        if self.service is not None:
            self._cache = None
        else:
            # otherwise, update the properties to reflect any changes in
            # the select/expand rules
            self._init_cache(clear=False)

    def _init_cache(self, clear=True):
        # a null value should have no properties: nothing to do!
        if self.null:
            return
        if self._cache is None or clear:
            self._cache = {}
        self_ref = weakref.ref(self)
        for ptype in self.type_def.values():
            if isinstance(ptype, Property):
                if isinstance(ptype.structural_type, ComplexType):
                    # a complex (or complex collection) property
                    self._init_complex(ptype, self_ref)
                else:
                    # simple case, a primitive property
                    self._init_primitive(ptype, self_ref)
            else:
                self._init_navigation(ptype, self_ref)

    def _init_primitive(self, ptype, self_ref):
        selected = True
        pname = ptype.name
        if self.options:
            if pname not in self.base_def:
                # this is a property of a derived type so the select path
                # MUST be qualified with the name of this type
                qname = ptype.nametable().qname
            else:
                qname = None
            selected = self.options.selected(qname, pname)
        if selected:
            if pname not in self:
                self._cache[pname] = ptype(self_ref)
        else:
            if pname in self:
                del self._cache[pname]

    def _init_complex(self, ptype, self_ref):
        pname = ptype.name
        if self.options:
            if pname not in self.base_def:
                qname = ptype.nametable().qname
            else:
                qname = None
            options, qname = self.options.complex_selected(qname, pname)
            if options:
                if pname not in self:
                    self._cache[pname] = p = ptype(self_ref)
                    p._set_options(options)
                    if qname:
                        type_def = self.options.resolve_type(qname)
                        p.type_cast(type_def)
            elif pname in self:
                del self._cache[pname]
        elif pname not in self:
            # default selected if there are no options
            self._cache[pname] = ptype(self_ref)

    def _init_navigation(self, ptype, self_ref):
        pname = ptype.name
        if self.options:
            if pname not in self.base_def:
                qname = ptype.nametable().qname
            else:
                qname = None
            selected = self.options.selected(qname, pname, nav=True)
            xitem = self.options.nav_expanded(qname, pname)
            if xitem is not None:
                if pname not in self:
                    self._cache[pname] = p = ptype(self_ref, xitem.qualifier)
                    if xitem.type_cast:
                        type_cast = p.type_cast(
                            self.options.resolve_type(xitem.type_cast))
                    else:
                        type_cast = None
                    p._set_options(xitem.options, type_cast=type_cast)
            elif selected:
                # just selected for link, same as no qualifier
                # service request will be deferred
                if pname not in self:
                    self._cache[pname] = p = ptype(self_ref)
            elif pname in self:
                del self._cache[pname]
        elif pname in self:
            # default is not selected if there are no options
            del self._cache[pname]

    def bind_to_service(self, service):
        """Binds this value to a specific OData service

        Binds all properties recursively."""
        if self.service is not None:
            raise errors.BoundValue(to_text(self))
        self.service = service
        if self._cache is not None:
            for pvalue in self._cache.values():
                pvalue.bind_to_service(service)

    def _load_cache(self):
        # load the cache
        self._init_cache()
        if self.service is not None:
            # load the entity from the service
            self.reload()

    @contextlib.contextmanager
    def loading(self):
        self.null = False
        if self._cache is None:
            # creating the cache (with defaults) prevents the mapping
            # methods from attempting a reload
            self._init_cache()
        try:
            self._loading = True
            yield self
        finally:
            self._loading = False
        # just deserialized so mark as clean
        self.clean()

    def __len__(self):
        if self.null:
            return 0
        if self._cache is None:
            self._load_cache()
        return len(self._cache)

    def __getitem__(self, key):
        if self.null:
            raise KeyError
        if self._cache is None:
            self._load_cache()
        return self._cache[key]

    def __iter__(self):
        if self.null:
            return
        if self._cache is None:
            self._load_cache()
        for k in self._cache:
            yield k

    def is_null(self):
        """Returns True if this object is null."""
        return self.null

    def set_defaults(self):
        """Sets default values for all properties

        For a null value his method automatically triggers the creation
        of the selected/expanded property values in the property
        dictionary with their default values set.  The structured value
        as a whole is marked as being dirty but the individual values
        are not.  This is an important distinction as when creating a
        new entity defaults are *not* sent to the service.  If a service
        lies about the default that will be used for a property then the
        property value may be different from the default immediately
        after creation.  If you want to force the published default to
        be used for any reason you should mark the individual property
        as being dirty too by calling :meth:`types.Value.touch` on it
        prior to creation.  If you want to force all published defaults
        to be used then you can call this method twice as on the second
        invocation the value will be non-null and the following rules
        will apply...

        For a non-null value all properties with defined defaults are
        set to their default values (and marked as dirty), including
        recursively through complex children.  Values without defaults
        defined are left unmodified."""
        if self.frozen:
            raise errors.FrozenValueError
        elif self.null:
            self.null = False
            self._init_cache()
            self.touch()
        else:
            for ptype in self.type_def.values():
                if isinstance(ptype, Property):
                    if isinstance(ptype.structural_type, ComplexType):
                        # a complex (or complex collection) property
                        self[ptype.name].set_defaults()
                    else:
                        # simple case, a primitive property
                        if ptype.default_value is not None:
                            self[ptype.name].set_value(
                                ptype.default_value.get_value())

    def select_value(self, value):
        """Sets the value from a python 'native' value representation

        This is wrapper for :meth:`set_value` that imposes the
        additional constraint that all structural properties with keys
        in *value* are selected and any structural properties with keys
        that are missing from *value* are unselected.  The upshot is
        that the structured value becomes a 'tight fit' around the
        incoming value with no default values.  This method is also
        strict about extraneous data, any data in *value* that cannot be
        accommodated in the structured value will raise ValueError.  In
        cases where there is a collection of complex values then all
        dict/mapping items in the corresponding list must contain an
        identical set of keys.

        One use case for using this method (instead of set_value) would
        be if there are computed defaults in your data service.  That
        is, structural properties that are marked as non-nullable in the
        model but which can be omitted on insert without generating an
        error.  Such values can be safely omitted from the value
        dictionary in order to invoke the server-side computed defaults.
        An obvious example is auto-generated key fields."""
        if value is None:
            self.null = True
            self.clear_cache()
            self.touch()
        elif isinstance(value, (dict, collections.Mapping)):
            selected = self._subselect(self.type_def, value)
            if self._options_inherited:
                self._clone_options()
            self.options.clear_select()
            for path in selected:
                self.options.add_select_path(path)
            self.set_value(value)
        else:
            raise ValueError

    def _subselect(self, ctype, value):
        if value is None:
            # a complex type set to null, no need to sub-select
            return []
        elif not value:
            # a complex type set to {} perhaps, we can't select no
            # properties so this is an error
            raise ValueError("no properties to select for %s" % ctype.qname)
        elif isinstance(value, (dict, collections.Mapping)):
            selected = []
            unselected = 0
            vkeys = set(value.keys())
            for pname, ptype in ctype.items():
                vkeys.discard(pname)
                if not isinstance(ptype, Property):
                    continue
                if pname not in value:
                    unselected += 1
                    continue
                if isinstance(ptype.structural_type, ComplexType):
                    if ptype.collection:
                        # never null, but need to intersect selects
                        subselect = self._subselect_intersect(
                            ptype.structural_type, value[pname])
                    else:
                        subselect = self._subselect(
                            ptype.structural_type, value[pname])
                    if subselect:
                        unselected += 1
                        for s in subselect:
                            s.insert(0, pname)
                        selected += subselect
                        continue
                # we're just selected
                selected.append([pname])
            if vkeys:
                raise ValueError(
                    "unused fields in value: %s" % ", ".join(list(vkeys)))
            if unselected:
                # if there is anything unselected then we return the
                # select rules
                if not selected:
                    raise ValueError(
                        "no properties to select for %s" % ctype.qname)
                return selected
            else:
                # everything is selected, we can return an empty list
                # meaning default (all properties)
                return []
        else:
            raise ValueError

    def _subselect_intersect(self, ctype, value):
        if value is None:
            # collections can never be null
            raise ValueError("collections cannot be null")
        elif not value:
            # an empty list perhaps, no need to sub-select
            return []
        elif isinstance(value, (list, tuple, collections.Sequence)):
            subselect = sorted(self._subselect(ctype, value[0]))
            for v in value[1:]:
                # All items in the list must be the same!
                vselect = sorted(self._subselect(ctype, v))
                if vselect != subselect:
                    raise ValueError(
                        "set_value: incompatible selections in collection")
            return subselect
        else:
            raise ValueError("list or sequenced required")

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        None sets a null value.

        A dict or dict-like object will update all (selected)
        *structural* properties of this value from the corresponding
        values in the dictionary.  If a property has not corresponding
        entry in *value* then it is set to its default (or null).

        We deal with one special case here, if the incoming dictionary
        contains another :class:`Value` instance then
        :meth:`types.Value.get_value` is used to extract its value
        before passing it to the corresponding set_value method of this
        object's property.  The upshot is that you may pass another
        entity or complex value to set_value but that, unlike
        :meth:`assign`, no type checking it performed and the operation
        succeeds provided that the underlying value types are
        compatible."""
        if self.frozen:
            raise errors.FrozenValueError
        if value is None:
            self.null = True
            self.clear_cache()
            self.touch()
        elif isinstance(value, (dict, collections.Mapping)):
            self.null = False
            self._init_cache(clear=False)
            for pname, pvalue in self.items():
                ptype = self.type_def[pname]
                if isinstance(ptype, Property):
                    new_value = value.get(pname, None)
                    if new_value is None:
                        if isinstance(pvalue, CollectionValue):
                            del pvalue[:]
                        elif isinstance(ptype.structural_type, ComplexType):
                            if ptype.nullable:
                                pvalue.set_value(None)
                            else:
                                pvalue.set_defaults()
                        else:
                            if ptype.default_value is not None:
                                pvalue.set_value(
                                    ptype.default_value.get_value())
                            else:
                                pvalue.set_value(None)
                    else:
                        if isinstance(new_value, types.Value):
                            new_value = new_value.get_value()
                        pvalue.set_value(new_value)
        else:
            raise TypeError

    def assign(self, value):
        """Sets this value from another Value instance.

        If value is null then this instance is set to null.  Otherwise
        the incoming value must be of the same type as, or a type
        derived from, the object being assigned.  The values of all
        properties present in the dictionary are assigned from the
        values with the same name in the other value instance.  Missing
        values are set to null.

        The assign operation does not change the type of a value.  You
        can do that using :meth:`set_type`."""
        if self.frozen:
            raise errors.FrozenValueError
        if value.is_null():
            self.set_value(None)
        elif value.type_def.is_derived_from(self.type_def):
            if self.null:
                self.set_defaults()
            for pname, pvalue in self.items():
                new_value = value.get(pname, None)
                if new_value is None:
                    pvalue.set(None)
                else:
                    pvalue.assign(new_value)
            self.touch()
        else:
            return super(StructuredValue, self).assign(value)

    def commit(self):
        """Pushes changes to this entity"""
        if self.service is not None:
            # we're bound, push to the service
            if isinstance(self, EntityValue):
                request = self.service.update_entity(self)
            else:
                request = self.service.update_property(self)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
        else:
            self.rclean()

    def rclean(self):
        for pvalue in self.values():
            if isinstance(pvalue, StructuredValue):
                pvalue.rclean()
            else:
                pvalue.clean()
        self.clean()


class ComplexType(StructuredType):

    """A ComplexType declaration"""

    def __init__(self, **kwargs):
        super(ComplexType, self).__init__(**kwargs)
        self.value_type = ComplexValue

    def check_name(self, name):
        """Overridden to add a check against the declared name"""
        if self.name is not None and self.name == name:
            raise ValueError(errors.Requirement.ct_same_name_s % name)
        super(ComplexType, self).check_name(name)

    def __setitem__(self, key, value):
        if isinstance(value, types.Named) and value.is_owned_by(self):
            # we own this property, it must not share our name
            if self.name is not None and self.name == value.name:
                raise ValueError(errors.Requirement.ct_same_name_s % self.name)
        return super(ComplexType, self).__setitem__(key, value)


class ComplexValue(StructuredValue):

    """Represents the value of a Complex type

    Instances behave like dictionaries of property values."""

    def __init__(self, type_def=None, **kwargs):
        if type_def is not None and not isinstance(type_def, ComplexType):
            raise errors.ModelError(
                "ComplexValue required ComplexType: %s" % repr(type_def))
        super(ComplexValue, self).__init__(
            type_def=edm['ComplexType'] if type_def is None else type_def,
            **kwargs)

    def touch(self):
        """Implements touch behaviour

        If this complex value is the value of a commplex or entity
        property then touch the parent too."""
        super(ComplexValue, self).touch()
        if self.parent:
            self.parent().touch()

    def reload(self):
        """Reloads this value from the service

        The value must be bound."""
        if self.service is None or self.parent is None:
            raise errors.UnboundValue
        request = self.service.get_property(self)
        request.execute_request()
        if isinstance(request.result, Exception):
            raise request.result


class EntityType(StructuredType):

    """An EntityType declaration"""

    def __init__(self, **kwargs):
        super(EntityType, self).__init__(**kwargs)
        self.value_type = EntityValue
        #: This entity type's key.  This attribute is only set if the
        #: key is defined by this entity type itself, keys can also
        #: be inherited.
        self.key = []
        self._key = []
        #: A dictionary mapping the short name of each key property to a
        #: tuple of (path, Property) where path is an array of simple
        #: identifier strings and Property is the declaration of the
        #: property.
        self.key_dict = {}
        self._key_dict = {}
        #: whether or not instances of this EntityType are contained
        #: None indicates undetermined.
        self.contained = None

    def check_name(self, name):
        """Overridden to add a check against the declared name"""
        if self.name is not None and self.name == name:
            raise ValueError(errors.Requirement.et_same_name_s % name)
        super(EntityType, self).check_name(name)

    def __setitem__(self, key, value):
        if isinstance(value, types.Named) and value.is_owned_by(self):
            # we own this property, it must not share our name
            if self.name is not None and self.name == value.name:
                raise ValueError(errors.Requirement.et_same_name_s % self.name)
        return super(EntityType, self).__setitem__(key, value)

    def declare(self, nametable, name):
        """Overridden to add a check against the declared name"""
        p = self.get(name, None)
        if p is not None and p.is_owned_by(self):
            # A property we own cannot share our name
            raise ValueError(errors.Requirement.et_same_name_s % name)
        super(EntityType, self).declare(nametable, name)

    def add_key(self, path, alias=None):
        if self.closed:
            raise errors.ModelError(
                "Can't add key to complete EntityType %s" % self.qname)
        if len(path) > 1:
            # this is a complex path, alias is required
            if alias is None:
                raise errors.ModelError(
                    errors.Requirement.key_alias_s %
                    ("%s: %s" % (self.qname, "/".join(path))))
        else:
            if alias is not None:
                raise errors.ModelError(
                    errors.Requirement.key_noalias_s %
                    ("%s: %s" % (self.qname, alias)))
            alias = path[0]
        # we'll check the validity of the key itself on closure
        self.key.append((alias, path))

    def key_defined(self):
        """Returns True if this type defines or inherits a key"""
        t = self
        while isinstance(t, EntityType):
            if t.key:
                return True
            else:
                t = t.base
        return False

    def get_key_dict(self, key):
        """Creates a key dictionary representingn *key*

        key
            A simple value (e.g., a python int or tuple for a composite
            key) representing the key of an entity of this type.

        Returns a dictionary of Value instances representing the key."""
        if not isinstance(key, tuple):
            key = (key, )
        if len(key) != len(self._key):
            raise errors.ODataError("invalid key for %s" % str(self))
        key_dict = {}
        for key_info, key_value in zip(self._key, key):
            name, path = key_info
            value = self._key_dict[name][1].type_def()
            value.set_value(key_value)
            if len(key) == 1:
                key_dict[""] = value
            else:
                key_dict[name] = value
        return key_dict

    def set_contained(self):
        """Marks this entity type as being contained by another.

        This property is inherited and can only be set once within an
        entity type hierarchy.  The property can only be set *after* the
        type has been closed (ensuring the entity hierarchy is complete
        back to the root)"""
        if not self.closed:
            raise errors.ModelError(
                "Can't set contained on incomplete type %s" % self.qname)
        if self.contained is False:
            # a derived type has already indicated containment
            raise errors.ModelError(
                errors.Requirement.nav_multi_contains_s % self.qname)
        t = self.base
        while isinstance(t, EntityType):
            if t.contained:
                raise errors.ModelError(
                    errors.Requirement.nav_multi_contains_s % self.qname)
            else:
                t.contained = False
                t = t.base
        self.contained = True

    def close(self):
        """Overridden to catch additional EntityType constraints"""
        if not self.abstract and not self.key_defined():
            raise errors.ModelError(
                errors.Requirement.et_abstract_key_s % self.qname)
        if self.base is not None:
            # if we are abstract, our base MUST also be abstract
            if self.abstract and not self.base.abstract:
                raise errors.ModelError(
                    errors.Requirement.et_abstract_base_s % self.qname)
            if self.key and self.base.key_defined():
                raise errors.ModelError(
                    errors.Requirement.et_abstract_no_key_s % self.qname)
        # Now ready to close
        super(EntityType, self).close()
        # Post-closure validity checks...
        for name, path in self.key:
            try:
                kp = self.resolve_sproperty_path(path, inheritance=False)
            except errors.PathError as err:
                raise errors.ModelError(
                    errors.Requirement.key_path_s %
                    ("%s: %s" % (self.qname, str(err))))
            if isinstance(kp.type_def, EnumerationType) or (
                    isinstance(kp.type_def, primitive.PrimitiveType) and
                    issubclass(kp.type_def.value_type, (
                        primitive.BooleanValue, primitive.DateValue,
                        primitive.DateTimeOffsetValue, primitive.DecimalValue,
                        primitive.DurationValue, primitive.GuidValue,
                        primitive.IntegerValue, primitive.StringValue,
                        primitive.TimeOfDayValue))):
                if kp.nullable:
                    raise errors.ModelError(
                        errors.Requirement.key_nullable_s % kp.qname)
                if len(path) > 1 and (name in self or name in self.key_dict):
                    raise errors.ModelError(
                        errors.Requirement.key_alias_unique_s % name)
                # this one's OK
                self.key_dict[name] = (path, kp)
            else:
                raise errors.ModelError(
                    errors.Requirement.key_type_s % kp.qname)
        # set inherited key properties so we don't have to recurse every
        # time we need to look up the key
        t = self
        while isinstance(t, EntityType):
            if t.key:
                self._key = t.key
                self._key_dict = t.key_dict
                break
            else:
                t = t.base

    def split_path(self, path, context=None, navigation=False):
        """Splits a path at navigation boundaries

        path
            A list or other iterable returning identifiers (as strings),
            :class:`QualifiedName` tuples or the special value "*".
            Alternatively, a string is also accepted for convenience and
            this will be split into path components.

        context
            The context in which to look up qualified names.  Required
            if the path contains type cast segments.

        navigation (False)
            Set to True to indicate that only navigation property paths
            should be returned in the last path tuple.

        Returns a sequence of path tuples, each containing simple
        identifiers (as strings) or :class:`types.QualifiedName`
        instances. The sequence consists of optional paths to navigation
        properties that are traversed by the path, followed by the
        terminal property path that may be navigation or structural and
        may contain a trailing type-cast segment.

        The returned paths are canonicalised automatically (removing or
        reducing spurious type-casts)."""
        path = types.get_path(path)
        result = []
        i = 0
        p = None
        while i < len(path):
            if p is None:
                # first time around
                ctype = ctype_cast = self
            elif isinstance(p, Property):
                # nothing is allowed after a primitive property and this
                # can't be complex (as the inner loop only terminates on
                # a complex property if it runs out of segments).
                raise errors.PathError(
                    "Bad select property: %s" % self.path_to_str(path))
            else:
                # type of preceding navigation property
                ctype = ctype_cast = p.entity_type
                p = None
            xpath = []
            while i < len(path):
                seg = path[i]
                if is_text(seg):
                    # plain identifier, should be a property of the
                    # current type
                    ptype, p = ctype_cast.canonical_get(seg, ctype)
                    if ptype is not ctype:
                        # automatically minimises the cast
                        xpath.append(ptype.get_qname())
                    xpath.append(seg)
                    i += 1
                    if isinstance(p, Property) and isinstance(
                            p.structural_type, ComplexType):
                        ctype = ctype_cast = p.structural_type
                        continue
                    break
                else:
                    # this is a type-cast segment, must have a context
                    if context is None:
                        raise errors.PathError(
                            "Type cast segment requires context")
                    new_type = context.qualified_get(seg)
                    if not new_type.is_derived_from(ctype_cast):
                        raise errors.PathError(
                            "Incompatible types for cast: %s" % to_text(seg))
                    ctype_cast = new_type
                    i += 1
            if not xpath:
                # the path consists only of type cast segments, must
                # be the trailing type-cast
                if result:
                    result[-1].append(ctype_cast.get_qname())
                    break
                else:
                    raise errors.PathError(
                        "Expected property path: %s" % self.path_to_str(path))
            if isinstance(p, Property):
                if navigation:
                    raise errors.PathError(
                        "Expected navigation or complex property: %s" % seg)
                if ctype_cast is not ctype:
                    # loop completed with a type cast of a complex property
                    xpath.append(ctype_cast.get_qname())
            result.append(xpath)
        return result


class EntityValue(StructuredValue):

    """Represents the value of an Entity type, i.e., an Entity.

    There is no special representation of an entity reference.  Entity
    references are just bound entity values with an empty cache.  Any
    operation on the property values (including use of len) will cause
    the cache to be loaded by retrieving the entity from the data
    service.  For references, the entity is identified by its id which
    is stored in the odata.id annotation when the entity is bound to the
    service."""

    def __init__(self, type_def=None, **kwargs):
        if type_def is not None and not isinstance(type_def, EntityType):
            raise errors.ModelError(
                "EntityValue requires EntityType: %s" % repr(type_def))
        super(EntityValue, self).__init__(
            type_def=edm['EntityType'] if type_def is None else type_def,
            **kwargs)
        self.entity_binding = None

    def set_entity_binding(self, entity_binding):
        if self.service is not None:
            raise errors.BoundValue(
                "set_entity_binding(%s)" % repr(entity_binding))
        self.entity_binding = entity_binding

    def get_entity(self, path, ignore_containment=True):
        """Returns self

        See: :meth:`StructuredType.get_entity` for more information."""
        if self.parent is None or not ignore_containment:
            return self
        else:
            return super(EntityValue, self).get_entity(
                path, ignore_containment)

    def get_path(self, path):
        """Returns the value of the property pointed to by path

        path
            A list of strings."""
        v = self
        for p in path:
            v = self[p]
        return v

    def get_key(self):
        """Returns this entity's key (as a tuple if composite)"""
        t = self.type_def
        key = None
        while isinstance(t, EntityType):
            if t.key:
                key = t.key
                break
            else:
                t = t.base
        if not key:
            raise errors.ModelError("Entity has no key!")
        if len(key) > 1:
            return tuple(self.get_path(p).value for a, p in key)
        else:
            return self.get_path(key[0][1]).value

    def get_ref(self):
        """Return a reference to this entity

        The entity value must be bound to a service as references only
        have meaning in the context of a service."""
        if self.service is None:
            raise errors.UnboundValue
        return self.service.get_entity_ref(self)


class EntityContainer(types.Annotatable, types.NameTable):

    """An EntityContainer is a container for OData entities."""

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
        if not isinstance(value, (EntitySet, Singleton)):
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


class EntityBinding(types.Annotatable, types.Named):

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
            An array of strings/QualifiedName instances that define a
            path to the navigation property being bound.

        target
            An array of strings that define a path to the target entity
            set."""
        nb = NavigationBinding()
        nb.np_path = path
        nb.target_path = target
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
                                StructuredType.path_to_str(nb.np_path)))
                    nb.target = self.resolve_target_path(
                        nb.target_path, model)
                    logging.debug("Binding %s to %s/%s", to_text(nb.np_path),
                                  nb.target.qname,
                                  StructuredType.path_to_str(nb.target_path))
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
            A list of string and/or :class:`types.QualifiedName` that
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
                    not isinstance(path[0], types.QualifiedName) or \
                    not is_text(path[1]):
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s" %
                     (self.qname, StructuredType.path_to_str(path))))
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
                     (self.qname, StructuredType.path_to_str(path),
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

    Calling an instance returns an :class:`EntitySetValue` bound to the
    service containing the EntitySet."""

    def __init__(self, **kwargs):
        super(EntitySet, self).__init__(**kwargs)
        #: whether to advertise in the service document
        self.in_service = True
        # whether or not we are indexable
        self.indexable_by_key = True

    def annotate(self, qa, target=None):
        """Override to intercept some special values"""
        super(EntitySet, self).annotate(qa, target)
        if qa.qname == "Org.OData.Capabilities.V1.IndexableByKey":
            if qa.value:
                self.indexable_by_key = qa.value.get_value()

    def set_type(self, entity_type):
        """Sets the entity type for this entity set

        The entity_type must be closed before it can be used as the type
        of an entity set."""
        if not entity_type.key_defined():
            raise errors.ModelError(
                errors.Requirement.entity_set_abstract_s % self.qname)
        super(EntitySet, self).set_type(entity_type)
        self.type_def = EntitySetType(entity_type=entity_type)

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


class EntitySetType(types.NominalType):

    """Collections of entities that can be accessed by key

    This type is used as the type of entity sets and navigation
    properties when they contain their values *or* dynamically when they
    are bound to a target entity set (which *should* be the case but is
    not guaranteed by the specification).

    The dfference between an EntitySetType and the weaker CollectionType
    is that they can only aggregate entities (of the same type) and
    those entities must all have unique keys allowing value of
    EntitSetType (instances of :class:`EntitySetValue` to behave like
    dictionaries).

    Instances take two additional (but optional) keyword arguments when
    called: type_cast and options.  See :meth:`EntitySet.open` for more
    information."""

    def __init__(self, entity_type, **kwargs):
        super(EntitySetType, self).__init__(**kwargs)
        #: the type being collected, we do not allow collections of
        #: collections
        self.item_type = entity_type
        self.value_type = EntitySetValue
        # used as the type for ordered (sub)collections of this entity set
        self.collection_type = CollectionType(item_type=entity_type)


class EntityContainerValue(ContainerValue):

    """Abstract class for a value that contains an entity or entities

    This class is used as the base class for representing *any* object
    that contains one or more entities.  This is a base class for
    :class:`EntitySetValue` and :class:`SingletonValue` that are used
    to represent the values of declared EntitySets and Singletons but it
    also includes the values of navigation properties that refer to a
    subset of entities from a declared EntitySet (including single
    valued navigation properties that are treated as Singletons)."""

    def __init__(self, **kwargs):
        super(EntityContainerValue, self).__init__(**kwargs)
        if not isinstance(self.item_type, EntityType):
            raise errors.ODataError(
                "EntityType required: %s" % self.item_type.qname)
        #: the optional entity set or singleton we're bound to
        self.entity_binding = None

    OptionsType = types.EntityOptions

    def set_entity_binding(self, entity_binding):
        """Binds this value to an entity set or singleton

        When creating an EntitySetValue providing a view on an EntitySet
        exposed by a service the value is *bound*, not just to the
        service, but to the entity set itself (similarly for
        SingletonValue and singletons).  This further constrains the
        entities that the value can contain to be both of the entity
        type (as per :attr:`item_type`) *and* to come from a specific
        entity_set. (It is possible for a model to define multiple
        distinct entity sets that contain entities of the same type.)
        The same is true for navigation properties that are bound to
        entity sets using navigation bindings.

        You don't normally need to call this method yourself, values are
        automatically bound to the appropriate entity context when they
        are added to the container immediately prior to binding them to
        the service itself (see :meth:`bind_to_service`).

        Once set, you can't change the entity context that a value is
        bound to. Also, you can't bind a value to an entity context
        after it has been bound to a service."""
        if self.service is not None:
            raise errors.BoundValue(
                "set_entity_binding(%s)" % repr(entity_binding))
        self.entity_binding = entity_binding

    def new_item(self):
        """Creates an entity suitable for this entity set

        If this value is bound to an entity set then the entity value
        returned is also bound to that entity set, in addition to
        inheriting any select/expand options that may be set on the
        parent."""
        entity = self.item_type()
        # now implement the entity options, select and expand
        if self.entity_binding is not None:
            entity.set_entity_binding(self.entity_binding)
        entity._set_options(self.options)
        return entity


class EntitySetValue(collections.MutableMapping, EntityContainerValue):

    """Represents the value of an entity set

    This class is used to represent *any* set of entities.  This could
    be the set of entities exposed directly by an EntitySet in a
    service's container or a restricted set of entities obtained by
    navigation.  You can even instantiate it directly to create a
    temporary entity set that is not backed by a data service at all.

    The implementation inherits from Python's abstract MutableMapping
    with the Entity keys as keys and the Entity instances as values.
    The difference between an ordinary mapping and an EntitySet is that
    iterating the items results in a predictable order."""

    def __init__(self, **kwargs):
        super(EntitySetValue, self).__init__(**kwargs)
        self._fullycached = True
        self._keys = []
        self._cache = {}
        self._key_lock = 1
        self._next_link = None

    def _clone_options(self):
        if self.options:
            self.options = self.options.clone()
        else:
            self.options = types.CollectionOptions()
        self._options_inherited = False

    def bind_to_service(self, service):
        """Binds this EntitySetValue to a data service

        This entity set value must be empty to be bound.

        Once bound, the EntitySetValue automatically creates and
        executes requests to the underlying data service and caches the
        resulting information for speed."""
        if self._keys:
            raise errors.ServiceError(
                "EntitySetValue must be empty to be bound")
        self._fullycached = False
        self._cache.clear()
        super(EntitySetValue, self).bind_to_service(service)

    def clear_cache(self):
        if self.service is not None:
            self._fullycached = False
            self._cache.clear()
            del self._keys[:]
            self._key_lock += 1

    @contextlib.contextmanager
    def loading(self, next_link=None):
        self._next_link = next_link
        if self.service is None:
            # an unbound entity set is simpler
            self._fullycached = True
            self._cache.clear()
            del self._keys[:]
            self._key_lock += 1
            yield self
        else:
            yield self
            self._fullycached = next_link is None
            max_size = self.get_page_size()
            if max_size is not None:
                # we ignore next_link if we asked to limit the page
                self._fullycached = self._fullycached or \
                    len(self._cache) == max_size
        self.clean()

    def load_item(self, e):
        """Only used during deserialization"""
        k = e.get_key()
        self._keys.append(k)
        self._cache[k] = e

    def __len__(self):
        if self._fullycached:
            return len(self._keys)
        else:
            request = self.service.get_item_count(self)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            return request.result

    def __getitem__(self, key):
        result = self._cache.get(key, None)
        if result is None:
            if self._fullycached:
                raise KeyError
            else:
                # cache fault, load from source
                request = self.service.get_entity_by_key(self, key)
                request.execute_request()
                if isinstance(request.result, errors.ServiceError):
                    if request.result.http_code == 404:
                        raise KeyError
                if isinstance(request.result, Exception):
                    raise request.result
                e = request.result
                k = e.get_key()
                # we don't know where in the sequence this key belongs
                # self._keys.append(k)
                self._cache[k] = e
                return e
        return result

    def __setitem__(self, key, value):
        # entity_set[key] = entity
        raise NotImplementedError

    def __delitem__(self, key):
        # del entity_set[key]
        if self._fullycached and self.service is not None:
            if key in self._cache:
                del self._cache[key]
                self._keys.remove(key)
            else:
                raise KeyError
        else:
            # this is enough to discard our cache completely
            self.clear_cache()
            request = self.service.delete_entity_by_key(self, key)
            request.execute_request()
            if isinstance(request.result, errors.ServiceError):
                if request.result.http_code == 404:
                    raise KeyError
            if isinstance(request.result, Exception):
                raise request.result

    def __iter__(self):
        self._key_lock += 1
        key_lock = self._key_lock
        if self._fullycached:
            for k in self._keys:
                yield k
                if key_lock != self._key_lock:
                    raise errors.ODataError("Stale iterator detected")
        else:
            self._keys = []
            self._cache.clear()
            request = self.service.get_entity_collection(self)
            i = 0
            while request is not None:
                self._next_link = None
                request.execute_request()
                if isinstance(request.result, Exception):
                    raise request.result
                if self._next_link:
                    request = self.service.get_entity_collection(
                        self, self._next_link)
                    self._next_link = None
                else:
                    request = None
                while i < len(self._keys):
                    yield self._keys[i]
                    if key_lock != self._key_lock:
                        raise errors.ODataError("Stale iterator detected")
                    i += 1

    def insert(self, entity):
        # entity must be of the correct type
        if not entity.type_def.is_derived_from(self.item_type):
            raise TypeError
        if self.service is None:
            k = entity.get_key()
            if k in self._cache:
                raise KeyError
            self._key_lock += 1
            self._keys.append(k)
            self._cache[k] = entity
        else:
            # TODO: check we're not being filtered
            request = self.service.create_entity(self, entity)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            # critical, update the key as it may have been computed
            k = entity.get_key()
            self._cache[k] = entity
            self._key_lock += 1


class Singleton(EntityBinding):

    """Represents a Singleton in the OData model."""

    def __init__(self, **kwargs):
        super(Singleton, self).__init__(**kwargs)

    def set_type(self, entity_type):
        """Sets the entity type for this entity

        The entity_type must be closed before it can be used as the type
        of a singleton."""
        super(Singleton, self).set_type(entity_type)
        self.type_def = SingletonType(entity_type=entity_type)

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
        return sv


class SingletonType(types.NominalType):

    """The type of an object that contains a single entity

    This type is used as the type of singletons and navigation
    properties to single entities (when they do not contain their
    values)."""

    def __init__(self, entity_type, **kwargs):
        super(SingletonType, self).__init__(**kwargs)
        #: the type of the entity, we do not allow singletons of
        #: collection types
        self.item_type = entity_type
        self.value_type = SingletonValue


class SingletonValue(EntityContainerValue):
    """Represents the value of a Singleton

    Whereas an :class:`EntitySetValue` follows Python's mutable mapping
    protocol a Singleton contains at most one entity, it is therefore
    callable instead.  I.e., calling an EntitySetValue returns the
    entity it contains or None if the Singleton is nullable and does not
    contain an entity.  Note that Singletons exposed by the container
    itself are *never* nullable."""

    def __init__(self, **kwargs):
        super(SingletonValue, self).__init__(**kwargs)
        self.is_collection = False
        self._cache = None

    def bind_to_service(self, service):
        """Binds this singleton to a data service

        The singleton must be empty to be bound.

        Once bound, the SingletonValue automatically creates and
        executes requests to the underlying data service and caches the
        resulting information for speed."""
        if self._cache:
            raise errors.ServiceError(
                "SingletonValue must be empty to be bound")
        self._cache = None
        super(SingletonValue, self).bind_to_service(service)

    def clear_cache(self):
        if self.service is not None:
            self._cache = None

    def __call__(self):
        result = self._cache
        if result is None:
            # cache fault, load from source
            request = self.service.get_singleton(self)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            e = request.result
            self._cache = e
            return e
        return result


edm = Schema.edm_init()
odata = Schema.odata_init()
