#! /usr/bin/env python

import collections
import contextlib
import logging
import weakref

from .. import rfc2396 as uri
from ..py2 import (
    is_text,
    long2,
    to_text,
    uempty,
    ul,
    )
from ..xml import xsdatatypes as xsi

from . import (
    data,
    errors,
    names,
    parser,
    primitive,
    types,
    )


try:
    from uritemplate import URITemplate
except ImportError:
    URITemplate = None


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
                                  CallableOverload,
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
        data.edm_complex_type.declare(cls.edm, "ComplexType")
        data.edm_entity_type.declare(cls.edm, "EntityType")
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
                ('GeometryCollection', primitive.edm_geometry_collection),
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


class EnumerationValue(primitive.PrimitiveValue):

    """Represents the value of an Enumeration type"""

    #: enumeration values are allowed as keys
    key_type = True

    @classmethod
    def new_type(cls):
        type_def = types.EnumerationType(
            value_type=cls, underlying_type=primitive.edm_int32)
        # all enumeration types are derived from primitive type
        type_def.set_base(primitive.edm_primitive_type)
        return type_def

    def __init__(self, value=None, **kwargs):
        super(EnumerationValue, self).__init__(**kwargs)
        self.value = None
        if value is not None:
            self.set_value(value)

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

    def value_from_str(self, src):
        """Constructs an enumeration value from a source string"""
        p = parser.Parser(src)
        mlist = p.require_enum_value()
        p.require_end()
        if not self.type_def.is_flags:
            if len(mlist) != 1:
                raise errors.ModelError(
                    "Enum member: expected single name or value")
            self.set_value(mlist[0])
        else:
            self.set_value(mlist)


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


class CallableType(names.NameTable, types.NominalType):

    """An abstract class for Actions and Functions

    Actions and Functions are treated as named types within the model
    though, due to overloading, they are declared directly in the
    enclosing schema but instead are grouped into
    :class:`CallableOverload` instances before being declared to enable
    disambiguation."""

    def __init__(self, **kwargs):
        super(CallableType, self).__init__(**kwargs)
        #: a weak reference to the Overload that contains us
        self.value_type = CallableValue
        self.overload = None
        self.is_bound = False
        self.return_type = None
        self.nullable = True
        self.params = []
        self.entity_set_path = None

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed parameter")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a (parameter) name

        By default we qualify name by prefixing with the name of this
        NameTable (type) and ":" rather than "/" to emphasize that
        parameters are not separately addressable within the model.  If
        this NameTable has not been declared then name is returned
        unchanged."""
        if self.name:
            return self.name + ":" + name
        else:
            return name

    def check_value(self, value):
        if not isinstance(value, Parameter):
            raise TypeError(
                "Parameter required, found %s" % repr(value))

    def set_is_bound(self, is_bound):
        self.is_bound = is_bound

    def binding(self):
        """Returns the type we are bound to"""
        if self.is_bound:
            return self.params[0].type_def
        else:
            return None

    def set_return_type(self, return_type):
        """Sets the return type for this callable

        If the return_type is a structured type (or collection thereof)
        it must be closed before it can be used as the return type of an
        action or function."""
        if isinstance(return_type, types.CollectionType):
            check_type = return_type.item_type
        else:
            check_type = return_type
        if isinstance(check_type, types.StructuredType) and \
                not check_type.closed:
            raise errors.ModelError("Type%s is still open" % check_type.qname)
        self.return_type = return_type

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_entity_set_path(self, path):
        self.entity_set_path = path

    def add_parameter(self, p, name):
        """Adds a parameter to this callable"""
        p.declare(self, name)
        self.params.append(p)

    #: the class used for Overload groups
    OverloadClass = None

    def declare_overload(self, schema, name):
        """Declares this callable in the given Schema

        Declarations of callables are special due to overloading rules,
        they do not appear in their parent's name table in the normal
        way but as part of an Overload object."""
        if name in schema:
            # add this declaration to the existing group
            fgroup = schema[name]
        else:
            fgroup = self.OverloadClass()
            fgroup.declare(schema, name)
        self.name = name
        self.qname = schema.qualify_name(name)
        self.overload = weakref.ref(fgroup)
        try:
            fgroup.overload(self)
        except:
            self.name = None
            self.qname = None
            self.overload = None
            raise

    def is_action(self):
        """Returns True if this CallableType is an action"""
        return isinstance(self, Action)


class CallableValue(collections.Mapping, data.Value):

    """Abstract class that represents a function or action call

    This class represents the invocation of the callable, *not* the
    result.  As such it behaves like a dictionary of non-binding
    parameter values keyed on parameter name.  On construction the value
    is pre-populated with parameter values set to null.  The value
    itself is never null.

    The type_def of a callable value is the :class:`CallableType` object
    that declares its signature.  There is no equivalent object in the
    OData URL syntax because a callable with parameters is implicitly
    called and resolves to the return value.  This object behaves more
    like a bound-method in Python except that it is bound to all
    parameters at once.  To obtain the return value you have to call the
    object.

    To call the value you use Python's call syntax (the parameters are
    already bound to the object so there are no parameters).  The call
    is made immediately and the return value is a :class:`Value`
    instance of the appropriate return type.  The result of a callable
    is *never* cached so calling it multiple times will call the service
    multiple times, each time returning a new object.

    For composable functions the return value is bound to the service
    via the parent callable and can be reloaded (reinvoking the function)
    to refresh its value.

    For non-composable functions and actions a transient result is
    typically returned (i.e., a value that is not bound to the service
    and cannot be reloaded).  An action *may* return a bound entity of
    course but, in that case, the entity is bound through the owning
    entity set and reloading its value will not invoke the action a
    second time.  For example, an action that exists for the purposes of
    creating an entity in an entity set in a special way will return a
    bound entity but reloading that entity will not cause it to be
    recreated.

    Composable functions that return entities or collections may have
    query options applied but these options are applied to the return
    value *not* to the callable.  To create the return value without
    calling the function you use the :meth:`deferred_call` method."""

    def __init__(self, **kwargs):
        super(CallableValue, self).__init__(**kwargs)
        self.binding = None
        self._params = {}
        plist = self.type_def.params
        if self.type_def.is_bound:
            plist = plist[1:]
        for p in plist:
            self._params[p.name] = p()

    def is_null(self):
        """Callable values are never null."""
        return False

    def set_callable_binding(self, binding):
        self.binding = binding

    def __len__(self):
        return len(self._params)

    def __getitem__(self, key):
        return self._params[key]

    def __iter__(self):
        for k in self._params:
            yield k

    def new_return_value(self):
        """Creates and returns a new return value"""
        if self.type_def.return_type:
            return self.type_def.return_type()
        else:
            return None

    def __call__(self):
        if self.service is None:
            raise errors.UnboundValue(to_text(self))
        if self.type_def.is_action():
            request = self.service.call_action(self)
        else:
            request = self.service.call_function(self)
        request.execute_request()
        if isinstance(request.result, Exception):
            raise request.result
        if isinstance(self.type_def, Function):
            # the result of this function is parented to allow reloading
            request.result.set_parent(weakref.ref(self), name="")
        return request.result


class CallableOverload(names.Named):

    def __init__(self, **kwargs):
        super(CallableOverload, self).__init__(**kwargs)
        self.callables = []

    def overload(self, callable):
        raise NotImplementedError

    def is_action(self):
        """Returns True if this CallableType is an action"""
        return isinstance(self, ActionOverload)


class ActionOverload(CallableOverload):

    def __init__(self, **kwargs):
        super(ActionOverload, self).__init__(**kwargs)
        self.bindings = {}

    def overload(self, action):
        if action.is_bound:
            # action name and binding parameter type
            key = to_text(action.binding())
        else:
            key = ""
        if key in self.bindings:
            raise errors.ModelError("Illegal overload: %s" % to_text(key))
        else:
            self.bindings[key] = action
            self.callables.append(action)

    def get_unbound_action(self):
        if self.name:
            return self.bindings.get("", None)
        else:
            return None

    def resolve(self, binding):
        """Resolves this action call

        binding
            The target of the call for a bound call, None if the
            call is being made unbound.

        Returns the matching :class:`Action` declaration.

        The most specific binding is always returned so if an action is
        overloaded such that one declaration has a binding parameter of
        type Schema.Employee and another Schema.Person (where Person is
        the base type of Employee) then passing an Employee value for
        *binding* will always match the function with binding parameter
        of type Employee."""
        if binding:
            # create a set of strings to match the binding working
            # backwards through the base types.  E.g.,
            # ["Schema.Person", "Edm.EntityType"]
            bound_type = binding.type_def
            blist = [to_text(b) for b in bound_type.declared_bases()]
        else:
            blist = [""]
        for bname in blist:
            a = self.bindings.get(bname, None)
            if a is not None:
                return a
        return None


class FunctionOverload(CallableOverload):

    def __init__(self, **kwargs):
        super(FunctionOverload, self).__init__(**kwargs)
        self.bound_type = None
        self.unbound_type = None
        self.name_bindings = {}
        self.type_bindings = {}

    def overload(self, function):
        if function.is_bound:
            if self.bound_type:
                if to_text(self.bound_type) != to_text(function.return_type):
                    raise errors.ModelError("Illegal overload")
            else:
                self.bound_type = function.return_type
            binding = to_text(function.binding())
            non_binding_params = function.params[1:]
        else:
            if self.unbound_type:
                if to_text(self.unbound_type) != to_text(function.return_type):
                    raise errors.ModelError("Illegal overload")
            else:
                self.unbound_type = function.return_type
            binding = ""
            non_binding_params = function.params
        name_key = tuple(
            [binding] + sorted([p.name for p in non_binding_params]))
        type_key = tuple(
            [binding] + [to_text(p.type_def) for p in non_binding_params])
        if name_key in self.name_bindings or type_key in self.type_bindings:
            raise errors.ModelError("Illegal overload")
        self.name_bindings[name_key] = function
        self.type_bindings[type_key] = function
        self.callables.append(function)

    def is_unbound(self):
        """Returns True if this Function can be called unbound"""
        return self.unbound_type is not None

    def resolve(self, binding, params):
        """Resolves this function call

        binding
            The target of the call for a bound call, None if the
            call is being made unbound.

        params
            Optional list or iterable of parameter names representing
            non-binding parameters.  This list is only required if the
            function is overloaded *for the same binding* parameter.
            The order of the parameter names in the iterable is
            disregarded when resolving overloads.

        Returns the matching :class:`Function` declaration.

        The most specific binding is always returned so if a function is
        overloaded such that one declaration has a binding parameter of
        type Schema.Employee and another Schema.Person (where Person is
        the base type of Employee) then passing an Employee value for
        *binding* will always match the function with binding parameter
        of type Employee even if the names of the non-binding parameters
        are otherwise the same.  This means that the params list may be
        omitted even when the binding parameter matches multiple
        overloads of the binding parameter via the type hierarchy."""
        if binding:
            # create a set of strings to match the binding working
            # backwards through the base types.  E.g.,
            # ["Schema.Person", "Edm.EntityType"]
            bound_type = binding.type_def
            blist = [to_text(b) for b in bound_type.declared_bases()]
        else:
            blist = [""]
        if params is not None:
            pnames = sorted(params)
            for bname in blist:
                f = self.name_bindings.get(tuple([bname] + pnames), None)
                if f is not None:
                    return f
        else:
            best_depth = None
            fmatch = None
            for nb, f in self.name_bindings.items():
                binding = nb[0]
                try:
                    depth = blist.index(binding)
                    if best_depth is None or depth < best_depth:
                        best_depth = depth
                        fmatch = f
                    elif depth == best_depth:
                        # Two functions with the same binding (but
                        # different sets of named parameters) is
                        # ambiguous
                        raise errors.ODataError(
                            "Overloaded callable requires params list for "
                            "disambiguation: %s" % self.qname)
                except ValueError:
                    continue
            return fmatch
        return None


class Action(CallableType):

    csdl_name = "Action"

    OverloadClass = ActionOverload


class Function(CallableType):

    csdl_name = "Function"

    def __init__(self, **kwargs):
        super(Function, self).__init__(**kwargs)
        #: whether or not we are composable
        self.is_composable = False

    OverloadClass = FunctionOverload

    def set_is_composable(self, is_composable):
        self.is_composable = is_composable


class Parameter(types.Annotatable, names.Named):

    """A Parameter declaration

    Parameters are defined within callables (Action or Function).  The
    corresponding :class:`CallableType` therefore becomes the namespace
    in which the parameter is first declared and the qname attribute
    is composed of the callable's qualified name and the parameter's name
    separated by ':' (we avoid '/' just to emphasize that parameters are
    not individually addressable within the model)."""

    csdl_name = "Parameter"

    def __init__(self, **kwargs):
        super(Parameter, self).__init__(**kwargs)
        #: the base parameter type
        self.param_type = None
        #: whether or not this parameter requires a collection
        self.collection = None
        #: the type definition for parameter values
        self.type_def = None
        #: whether or not the parameter value can be null (or contain
        #: null in the case of a collection)
        self.nullable = True

    def set_type(self, param_type, collection=False):
        self.param_type = param_type
        self.collection = collection
        if collection:
            self.type_def = param_type.collection_type()
        else:
            self.type_def = param_type

    def set_nullable(self, nullable):
        if self.collection:
            raise errors.ModelError(
                "collection parameters may not specify nullable")
        self.nullable = nullable

    def __call__(self):
        value = self.type_def()
        if not self.collection and not self.nullable:
            if isinstance(self.param_type, types.StructuredType):
                value.set_defaults()
        return value


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

    def indexable_by_key(self):
        """Whether or not this entity set is indexable by key

        Deteremined by the Org.OData.Capabilities.V1.IndexableByKey
        annotation on the entity set.

        If this annotation has not been applied to the EntitySet, the
        usual case, then we return True despite encouragement in the
        specification to return False.  In practice, this annotation is
        not widely used despite (almost?) all services exposing
        indexable entity sets."""
        a = self.annotations.qualified_get(
            "Org.OData.Capabilities.V1.IndexableByKey")
        if a is None:
            return True
        else:
            result = Evaluator.evaluate_annotation(a, self).get_value()
            if result is None:
                return True
            else:
                return result

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


class ExpressionProcessor(object):

    """An abstract class used to process expression

    The processing of expressions involves traversing the expression
    tree to obtain an evaluated result.  The evaluator works by calling
    the basic expression objects defined in the underlying types module
    which then call the appropriate method in this object to transform
    or compose any input arguments into a result.

    The most obvious implementation is the :class:`Evaluator` class that
    results in a :class:`data.Value` object but this technique allows
    alternative evaluators that return something other than Value
    objects with their own implementations of the methods in this class
    to provide an alternative result from the same expression: for
    example, to return a string representation of the expression or to
    build a query that represents the expression suitable for accessing
    some other data storage system (like SQL).

    Expressions in OData are very general and can touch all of the
    concepts within the model.  Some expressions contain qualified names
    that must be looked up in the context of a specific EntityModel.  A
    notable example is the way enumeration constants are represented in
    OData.

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

    def __init__(self, it=None, em=None):
        self.it = primitive.PrimitiveValue() if it is None else it
        if em is not None:
            self.em = em
        elif isinstance(self.it, data.Value):
            if self.it.service:
                self.em = self.it.service().model
            else:
                # unbound value, use type
                self.em = self.it.type_def.get_model()
        elif isinstance(self.it, types.NominalType):
            self.em = self.it.get_model()
        elif isinstance(self.it, EntityContainer):
            self.em = self.it.get_model()
        elif isinstance(self.it, (types.Property, types.NavigationProperty)):
            if self.it.nametable is not None:
                self.em = self.it.nametable().get_model()
            else:
                self.em = None
        else:
            self.em = None
        self.scope_stack = []
        self.scope = {}

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
        """Binds a named result in the current scope"""
        if name in self.scope:
            raise errors.ExpressionError("Duplicate name in scope: %s" % name)
        self.scope[name] = result

    def primitive(self, value):
        """Evaluates a primitive literal

        value is always an instance of the python type representing the
        primitive literal (None represents null)."""
        raise NotImplementedError("%s.primitive" % self.__class__.__name__)

    def reference(self, qname):
        """Evaluates a labeled reference to an expression

        qname is always a :types:`QualifiedName` instance.  Unusually, a
        default implementation is provided that looks up the name in the
        current model and then returns the result of evaluating the
        labeled expression."""
        if self.em is None:
            raise errors.ExpressionError(
                "No scope to evaluate %s" % to_text(qname))
        else:
            label = self.em.qualified_get(qname)
            if not isinstance(label, types.LabeledExpression):
                raise errors.ExpressionError(
                    errors.Requirement.label_ref_s % to_text(qname))
            return self.evaluate(label.expression)

    def annotation_path(self, value):
        """Evaluates an annotation path

        value is always a path tuple returned from the function
        :func:`names.annotation_path_from_str` (None represents
        null)."""
        raise NotImplementedError(
            "%s.annotation_path" % self.__class__.__name__)

    def navigation_path(self, path):
        """Evaluates a navigation path

        *path* is always a path tuple returned from the function
        :func:`names.path_from_str` (None represents null)."""
        raise NotImplementedError(
            "%s.navigation_path" % self.__class__.__name__)

    def property_path(self, value):
        """Evaluates a property path

        value is always a path tuple returned from the function
        :func:`names.path_from_str` (None represents null)."""
        raise NotImplementedError(
            "%s.property_path" % self.__class__.__name__)

    def resolve_path(self, path):
        """Evaluates a path

        path
            A path tuple.

        The path is evaluated in the current context (:attr:`it`).
        If the path is not valid, for example, it contains a reference
        to a property that is not declared in the current context, then
        a :class:`errors.PathError` *must* be raised."""
        raise NotImplementedError(
            "%s.resolve_path" % self.__class__.__name__)

    def collection(self, items):
        """Evaluates the collection operator

        items
            The items in the collection, obtained as the result of
            evaluating the arguments.  Note that values may be None
            indicating that the item is conditionally included in the
            collection and has been skipped."""
        raise NotImplementedError(
            "%s.collection" % self.__class__.__name__)

    def record(self, arg_dict):
        """Evaluates the record operator

        arg_dict
            A python dictionary mapping variable names onto the result
            of evaluating the remaining arguments to the function.

        Only used in the context of annotations."""
        raise NotImplementedError(
            "%s.record" % self.__class__.__name__)

    def bool_test(self, q, a, b=None):
        """Evaluates a or b depending on boolean value q

        This operation is used in annotation expressions, introduced by
        the <If> element."""
        raise NotImplementedError(
            "%s.bool_test" % self.__class__.__name__)

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

    def isof(self, type_name, expression=None):
        """Evaluates the isof operation

        type_name
            A :class:`names.QualifiedName` instance containing the
            name of the type to test.

        expression (None)
            The result of evaluating the expression argument or None if
            this is the single-argument form of isof, in which case the
            result of processing $it should be used instead.

        Notice that the arguments are turned around to enable the
        expression to be optional in the python binding."""
        raise NotImplementedError(
            "%s.isof" % self.__class__.__name__)

    def isof_type(self, type_def, expression):
        """Evaluates the isof operation (post lookup)

        Similar to :meth:`isof` except used to evaluate the IsOf element
        in an Annotation definition.  The expression is *required* and
        the first argument is a type instance and not a qualified name
        because the IsOf element can impose additional constraints on
        the base type and so may require the test of an unamed type
        derived from a primitive."""
        raise NotImplementedError(
            "%s.isof_type" % self.__class__.__name__)

    def odata_concat(self, args):
        """Evaluates the client-side odata.concat function

        Only used in the context of annotations, args is a list of the
        results of evaluating the argument expressions."""
        raise NotImplementedError(
            "%s.odata_concat" % self.__class__.__name__)

    def odata_fill_uri_template(self, template, arg_dict):
        """Evaluates the client-side odata.fileUriTemplate function

        template
            The *result* of evaluating the first argument to the
            function.

        arg_dict
            A python dictionary mapping variable names onto the result
            of evaluating the remaining arguments to the function.

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


class TypeChecker(ExpressionProcessor):

    """An object used for type-checking expressions

    This object evaluates expressions to type objects rather than
    to actual values."""

    def primitive(self, value):
        """Returns a :class:`primitive.PrimitiveType` instance.

        The value None returns None!"""
        if value is None:
            return None
        else:
            return primitive.PrimitiveValue.from_value(value).type_def

    def property_path(self, value):
        """Always returns Edm.PropertyPath"""
        return primitive.edm_property_path

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
        elif isinstance(it, (Singleton, EntitySet)):
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

    def resolve_path(self, path):
        """Returns the type of the property with *path*"""
        it = self.it
        if isinstance(it, data.Value):
            it = it.type_def
        for seg in path:
            if is_text(seg):
                logging.debug("TypeChecking: %s[%s]", to_text(it), seg)
                # this is a regular property to look up
                try:
                    it = it[seg].type_def
                except KeyError:
                    raise errors.PathError(names.path_to_str(path))
                logging.debug("              = %s", to_text(it))
            else:
                raise NotImplementedError(
                    "Path resolution of: %s" % to_text(seg))
            if isinstance(it, types.SingletonType):
                it = it.item_type
            elif isinstance(it, types.EntitySetType):
                it = it.item_type.collection_type()
        return it

    def collection(self, items):
        """Returns a :class:`types.CollectionType`

        The collection's item type is set from common base type of all
        the items.  You cannot have collections of collections or mix
        incompatible types."""
        item_type = None
        for item in items:
            if item is None:
                continue
            if item_type is None:
                item_type = item
            else:
                item_type = item_type.common_ancestor(item)
                if item_type is None:
                    # incompatible types
                    raise errors.ModelError(
                        errors.Requirement.collection_expression_s %
                        ("%s in list of %s" %
                         (to_text(item), to_text(item_type))))
        return item_type.collection_type()

    def record(self, arg_dict):
        """Returns Edm.ComplexType"""
        return edm['ComplexType']

    def bool_test(self, q, a, b=None):
        """Checks that q is boolean

        We also insist that a and b are compatible types and return the
        most specific common ancestor type.  For example, if b is
        derived from a, then we would return a."""
        if q and not q.compatible(primitive.edm_boolean):
            raise errors.ExpressionError(
                errors.Requirement.if_test_s % to_text(q))
        if a is None:
            return b
        elif b is None:
            return a
        else:
            return a.common_ancestor(b)

    def _bool_expr(self, a, b):
        """Checks that a and b are boolean compatible

        Always returns Edm.Boolean"""
        if a and not a.compatible(primitive.edm_boolean):
            raise errors.ExpressionError(
                errors.Requirement.annotation_and_or % to_text(a))
        if b and not b.compatible(primitive.edm_boolean):
            raise errors.ExpressionError(
                errors.Requirement.annotation_and_or % to_text(b))
        return primitive.edm_boolean

    def bool_and(self, a, b):
        return self._bool_expr(a, b)

    def bool_or(self, a, b):
        return self._bool_expr(a, b)

    def bool_not(self, op):
        return self._bool_expr(op, None)

    def _compare_expr(self, a, b):
        """Checks that a and b are compatible

        Always returns Edm.Boolean"""
        if a and b and not a.compatible(b):
            raise errors.ExpressionError(
                errors.Requirement.annotation_comparison_s %
                ("%s/%s" % (to_text(a), to_text(b))))
        return primitive.edm_boolean

    def eq(self, a, b):
        return self._compare_expr(a, b)

    def ne(self, a, b):
        return self._compare_expr(a, b)

    def gt(self, a, b):
        return self._compare_expr(a, b)

    def ge(self, a, b):
        return self._compare_expr(a, b)

    def lt(self, a, b):
        return self._compare_expr(a, b)

    def le(self, a, b):
        return self._compare_expr(a, b)

    def cast_type(self, type_def, expression):
        """Always returns type_def; checks expression"""
        if expression is not None and not expression.compatible(type_def):
            # can expression be cast to type_def?
            # this is a weaker test than compatibility because any
            # primitive can be cast to a string
            if not isinstance(expression, types.PrimitiveType) or \
                    not type_def.is_derived_from(primitive.edm_string):
                raise errors.ExpressionError(
                    "Can't cast %s to %s" %
                    (to_text(expression), to_text(type_def)))
        return type_def

    def isof_type(self, type_def, expression):
        """Always returns Edm.Boolean"""
        return primitive.edm_boolean

    def odata_concat(self, args):
        """Checks that all args are primitives

        Always returns Edm.String"""
        for arg in args:
            if arg and not isinstance(arg, types.PrimitiveType):
                raise errors.ExpressionError(
                    errors.Requirement.annotation_concat_args_s % to_text(arg))
        return primitive.edm_string

    def odata_fill_uri_template(self, template, arg_dict):
        """Checks template and args; returns Edm.String"""
        if template and not template.compatible(primitive.edm_string):
            raise errors.ExpressionError(
                errors.Requirement.annotation_fill_uri_template_args_s %
                repr(template))
        for k, v in arg_dict.items():
            if v is None or isinstance(v, types.PrimitiveType):
                continue
            elif isinstance(v, types.CollectionType):
                if isinstance(v.item_type, primitive.PrimitiveType) or \
                        isinstance(v.item_type, types.ComplexType):
                    continue
                else:
                    raise errors.ExpressionError(
                        "fillUriTemplate requires PrimitiveType, "
                        "Collection(PrimitiveType) or "
                        "Collection(ComplexType): %s" % repr(v))
        return primitive.edm_string

    def odata_uri_encode(self, value):
        """Returns Edm.String; checks value is primitive"""
        if value and not isinstance(value, types.PrimitiveType):
            raise errors.ExpressionError(
                "uriEncode requires primitive value, not %s" %
                repr(value))
        return primitive.edm_string


class Evaluator(ExpressionProcessor):

    """An object used to evaluate expressions"""

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

    def primitive(self, value):
        """Returns a :class:`primitive.PrimitiveValue` instance."""
        return primitive.PrimitiveValue.from_value(value)

    def annotation_path(self, value):
        """Returns a :class:`primitive.AnnotationPath` instance"""
        return primitive.AnnotationPathValue(value)

    def navigation_path(self, path):
        """Returns a :class:`primitive.NavigationPath` instance"""
        return primitive.NavigationPropertyPathValue(path)

    def resolve_path(self, path):
        """Returns the Value of the property with *path*"""
        it = self.it
        for seg in path:
            if is_text(seg):
                # this is a regular property to look up
                try:
                    if isinstance(it, data.StructuredValue):
                        it = it[seg]
                    else:
                        raise KeyError
                except KeyError:
                    raise errors.PathError(names.path_to_str(path))
                if isinstance(it, data.SingletonValue):
                    # a single-valued navigation property: get the
                    # actual value
                    it = it()
            else:
                raise NotImplementedError(
                    "Path resolution of: %s" % to_text(seg))
        return it

    def collection(self, items):
        """Returns a :class:`CollectionValue`

        The collection's item type is set from common base type of all
        the items.  You cannot have collections of collections or mix
        incompatible types."""
        item_type = None
        for item in items:
            if item is None:
                continue
            if item_type is None:
                item_type = item.type_def
            elif item.type_def.is_derived_from(item_type):
                continue
            elif item_type.is_derived_from(item.type_def):
                item_type = item.type_def
            else:
                # incompatible types
                raise errors.ModelError(
                    errors.Requirement.collection_expression_s %
                    ("%s in list of %s" %
                     (to_text(item.type_def), to_text(item_type))))
        value = item_type.collection_type()()
        for item in items:
            if item is None:
                continue
            value.append(item)
        return value

    def record(self, arg_dict):
        """Returns a :class:`data.ComplexValue` instance.

        The return value is a collection of property values notionally
        contained in an open complex type with no defined properties."""
        t = types.ComplexType(value_type=data.ComplexValue)
        t.set_open_type(True)
        t.close()
        value = t()
        for k, v in arg_dict.items():
            value[k] = v
        return value

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

    def cast(self, type_name, expression=None):
        """See :meth:`types.Values.cast` for more information

        The *type_name* is looked in the current context with the
        exception of type's in the Edm namespace itself which are always
        resolved to the built-in types even if there is no metadata
        model in the current processing context.  This ensures that
        expressions such as "cast(Edm.Decimal,3.125)" can be evaluated
        without requiring a context to be created specially."""
        if type_name.namespace == "Edm":
            # special case, we don't need a context
            type_def = edm[type_name.name]
        elif self.em is None:
            # look up the type in the context
            raise errors.ExpressionError(
                "cast to %s requires an evaluation context" %
                to_text(type_name))
        else:
            type_def = self.em.qualified_get(type_name)
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
            type_def = edm[type_name.name]
        elif self.em is None:
            # look up the type in the context
            raise errors.ExpressionError(
                "isof(%s) requires an evaluation context" %
                to_text(type_name))
        else:
            type_def = self.em.qualified_get(type_name)
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

    def odata_concat(self, args):
        """Returns a :class:`primitive.StringValue` instance."""
        result = []
        for arg in args:
            if not isinstance(
                    arg,
                    (primitive.PrimitiveValue, EnumerationValue)):
                raise errors.ExpressionError(
                    errors.Requirement.annotation_concat_args_s % repr(arg))
            result.append(to_text(arg))
        return primitive.StringValue(uempty.join(result))

    def odata_fill_uri_template(self, template, arg_dict):
        """Returns a :class:`primitive.StringValue` instance.

        This function is implemented using the uritemplate module
        available from PyPi.  This function represents a corner case
        within the OData model so we don't require uritemplate as a
        dependency.  If it is not present an EvaluationError is
        raised."""
        args = {}
        if not isinstance(template, primitive.StringValue):
            raise errors.ExpressionError(
                errors.Requirement.annotation_fill_uri_template_args_s %
                repr(template))
        for k, v in arg_dict.items():
            if isinstance(
                    v, (primitive.PrimitiveValue, EnumerationValue)):
                args[k] = to_text(v)
            elif isinstance(v, data.CollectionValue):
                if isinstance(
                        v.item_type,
                        (primitive.PrimitiveType, types.EnumerationType)):
                    args[k] = [to_text(i) for i in v]
                elif isinstance(v.item_type, types.ComplexType):
                    arg_list = []
                    for iv in v:
                        kv = sorted(iv.keys())[:2]
                        if len(kv) != 2:
                            raise errors.ExpressionError(
                                "Key-value map requires ComplexValue with at "
                                "least two properties" % repr(iv))
                        arg_list.append((kv[0], to_text(iv[kv[1]])))
                    args[k] = arg_list
                else:
                    raise errors.ExpressionError(
                        "fillUriTemplate requires PrimitiveType, "
                        "Collection(PrimitiveType) or "
                        "Collection(ComplexType): %s" % repr(v))
        if URITemplate is None:
            raise errors.ExpressionError(
                "fillUriTemplate not supported, try: pip install uritemplate")
        else:
            t = URITemplate(template.get_value())
            return primitive.StringValue(t.expand(**args))

    def odata_uri_encode(self, value):
        """Returns a :class:`primitive.StringValue` instance.

        See :meth:`primitive.PrimitiveValue.literal_string` for more
        information."""
        if not isinstance(value, primitive.PrimitiveValue):
            raise errors.ExpressionError(
                "uriEncode requires primitive value, not %s" %
                repr(value))
        return primitive.StringValue(value.literal_string())


data.Value.Evaluator = Evaluator

edm = Schema.edm_init()
odata = Schema.odata_init()
