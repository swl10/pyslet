#! /usr/bin/env python

import base64
import collections
import datetime
import decimal
import logging
import math
import sys
import uuid
import weakref

from . import geotypes as geo
from ..iso8601 import (
    Date,
    DateTimeError,
    Time,
    TimePoint)
from ..py2 import (
    BoolMixin,
    byte,
    force_text,
    is_text,
    is_unicode,
    long2,
    py2,
    range3,
    to_text,
    ul,
    UnicodeMixin
    )
from ..xml import xsdatatypes as xsi
from ..unicode5 import BasicParser, CharClass, ParserError


class ModelError(Exception):

    """Base error for OData model exceptions"""
    pass


class DuplicateNameError(ModelError):

    """Raised when a duplicate name is encountered in a name table"""
    pass


class ObjectRedclared(ModelError):

    """Raised by an attempt to redeclare an object"""
    pass


class UndeclarationError(ModelError):

    """Raised when an attempt is made to undeclare a name in a name
    table"""
    pass


class NameTableClosed(ModelError):

    """Raised when an attempt to declare a name in a closed name table
    is made"""
    pass


class PathError(Exception):

    """Raised during path traversal"""
    pass


class QualifiedName(
        UnicodeMixin,
        collections.namedtuple('QualifiedName', ['namespace', 'name'])):

    """Represents a qualified name

    This is a Python namedtuple consisting of two strings, a namespace
    and a name.  No syntax checking is done on the values at creation.
    When converting to str (and unicode for Python 2) the two components
    are joined with a "." as you'd expect."""

    __slots__ = ()

    def __unicode__(self):
        return force_text("%s.%s" % self)


class Named(object):

    """An abstract class for a named object"""

    def __init__(self):
        #: the name of this object
        self.name = None
        #: a weak reference to the nametable in which this object is
        #: first declared (or None if the object has not been declared)
        self.nametable = None
        #: the qualified name of this object (if declared) as a string
        self.qname = None

    def is_owned_by(self, nametable):
        """Checks the owning nametable

        A named object may appear in multiple nametables (e.g., a Schema
        may be defined in one entity model (the owner) but referenced in
        other entity models.  This method returns True if the nametable
        argument is the nametable in which the named object was declared
        (see :meth:`declare`)."""
        return self.nametable() is nametable

    def declare(self, nametable):
        """Declares this object in the given nametable

        Model elements can only be declared once.  Aliases are handled
        by directly assigning them in the associated NameTable, e.g.::

            schema.name = "my.long.schema.namespace"
            schema.declare(model)
            model['mlsn'] = schema      # assign the alias 'mlsn' """
        if self.nametable is None:
            if self.name is None:
                raise ValueError("%s declared with no name" % repr(self))
            # this declaration may trigger callbacks so we need to set
            # the owner now, even if the declaration later fails.
            self.nametable = weakref.ref(nametable)
            if nametable.name:
                self.qname = "%s.%s" % (nametable.name, self.name)
            try:
                nametable[self.name] = self
            except:
                self.nametable = None
                self.qname = None
                raise
        else:
            raise ObjectRedclared(
                "%s already declared" %
                (self.name if self.qname is None else self.qname))

    def root_nametable(self):
        """Returns the root table of a nametable hierarchy

        Uses the :attr:`nametable` attribute to trace back through a
        chain of containing namespaces until it finds one that has not
        been declared.

        If this object has not been declared then None is returned."""
        if self.nametable is None:
            return None
        else:
            n = self
            while n.nametable is not None:
                n = n.nametable()
            return n


class NameTable(Named, collections.MutableMapping):

    """Abstract class for managing tables of declared names

    Derived types behave like dictionaries (using Python's built-in
    MutableMapping abstract base class (ABC).  Names can only be defined
    once, they cannot be undefined and their corresponding valus cannot
    be modified.

    To declare a value simply assign it as you would in a normal
    dictionary.  Names (keys) and values are checked using abstract
    methods (see below) for validity.

    NameTables define names case-sensitively in accordance with the
    OData specification.

    NameTables are created in an open state, in which they will accept
    new declarations.  They can also be closed, after which they will
    not accept any new declarations (raising :class:`NameTabelClosedError`
    if you attempt to assign or modify a new key). """

    def __init__(self):
        self._name_table = {}
        #: whether or not this name table is closed
        self.closed = False
        super(NameTable, self).__init__()
        self._callbacks = {}
        self._close_callbacks = []

    def __getitem__(self, key):
        return self._name_table[key]

    def __setitem__(self, key, value):
        if self.closed:
            raise NameTableClosed(to_text(self.name))
        if key in self._name_table:
            raise DuplicateNameError("%s in %s" % (key, to_text(self.name)))
        self.check_name(key)
        self.check_value(value)
        self._name_table[key] = value
        for c in self._callbacks.pop(key, []):
            c(value)

    def __delitem__(self, key):
        raise UndeclarationError("%s in %s" % (key, to_text(self.name)))

    def __iter__(self):
        return iter(self._name_table)

    def __len__(self):
        return len(self._name_table)

    def check_name(self, name):
        """Abstract method to check validity of a name

        This method must raise ValueError if name is not a valid name
        for an object in this name table."""
        raise NotImplementedError

    def check_value(self, value):
        """Abstract method to check validity of a value

        This method must raise TypeError or ValueError if value is not a
        valid item for this type of name table."""
        raise NotImplementedError

    def tell(self, name, callback):
        """Deferred name lookup.

        Equivalent to::

            callback(self[name])

        *except* that if name is not yet defined it waits until name is
        defined before calling the callback.  If the name table is
        closed without name then the callback is called passing None."""
        value = self.get(name, None)
        if value is not None or self.closed:
            callback(value)
        else:
            callback_list = self._callbacks.setdefault(name, [])
            callback_list.append(callback)

    def tell_close(self, callback):
        """Notification of closure

        Calls callback (with no arguments) when the name table is
        closed.  This call is made after all unsuccessful notifications
        registered with :meth:`tell` have been made.

        If the table is already closed then callback is called
        immediately."""
        if self.closed:
            callback()
        else:
            self._close_callbacks.append(callback)

    def close(self):
        """closes this name table

        Any failed notification callbacks registered will :meth:`tell`
        are triggered followed by all notification callbacks registered
        with :meth:`tell_close`.  It is safe to call close on a name
        table that is already closed (callbacks are only ever called the
        first time) or even on one that is *being* closed.  In the
        latter case no action is taken, essentially the table is closed
        immediately, new declarations will fail and any calls to tell
        and tell_close made during queued callbacks will invoke the
        passed callback directly and nested calls to close itself do
        nothing."""
        if not self.closed:
            self.closed = True
            cbs = list(self._callbacks.values())
            self._callbacks = {}
            for callback_list in cbs:
                for c in callback_list:
                    c(None)
            cbs = self._close_callbacks
            self._close_callbacks = []
            for c in cbs:
                c()

    def reopen(self):
        """reopens this name table

        Not usually called but allows further definitions to be added to
        a closed name table."""
        self.closed = False
        self._callbacks = {}
        self._close_callbacks = []

    simple_identifier_re = xsi.RegularExpression(
        "[\p{L}\p{Nl}_][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")

    @classmethod
    def is_simple_identifier(cls, identifier):
        return cls.simple_identifier_re.match(identifier) and \
            len(identifier) <= 128

    @classmethod
    def is_namespace(cls, identifier):
        parts = identifier.split(".")
        if not parts:
            return False
        for id in parts:
            if not cls.is_simple_identifier(id):
                return False
        return True

    @classmethod
    def is_qualified_name(cls, identifier):
        parts = identifier.split(".")
        if len(parts) < 2:
            return False
        for id in parts:
            if not cls.is_simple_identifier(id):
                return False
        return True


class Annotatable(object):

    """Abstract class for model elements that can be annotated"""

    def __init__(self):
        super(Annotatable, self).__init__()
        self.annotations = Annotations()

    def annotate(self, qa):
        """Annotate this element with a qualified annotation"""
        qa.qualified_declare(self.annotations)


class Schema(Annotatable, NameTable):

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
        if not isinstance(value, (Term, NominalType, EntityContainer)):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<Schema>" if self.name is None else self.name))

    def close(self):
        """Closing the schema closes all items it contains"""
        for item in self.values():
            if isinstance(item, NameTable) and not item.closed:
                logging.warning("Cyclical reference detected: %s", item.qname)
                item.close()
        super(Schema, self).close()

    edm = None
    """The Edm schema.

    This schema contains the base type definitions of the built-in
    types in the Edm namespace."""

    @classmethod
    def edm_init(cls):
        """Creates and returns the built-in Edm schema"""
        cls.edm = Schema()
        cls.edm.name = "Edm"
        primitive_base = PrimitiveType()
        primitive_base.name = "PrimitiveType"
        primitive_base.declare(cls.edm)
        complex_base = ComplexType()
        complex_base.name = "ComplexType"
        complex_base.declare(cls.edm)
        entity_base = EntityType()
        entity_base.name = "EntityType"
        entity_base.declare(cls.edm)
        for name, vtype in (('Binary', BinaryValue),
                            ('Boolean', BooleanValue),
                            ('Byte', ByteValue),
                            ('Date', DateValue),
                            ('DateTimeOffset', DateTimeOffsetValue),
                            ('Decimal', DecimalValue),
                            ('Double', DoubleValue),
                            ('Duration', DurationValue),
                            ('Guid', GuidValue),
                            ('Int16', Int16Value),
                            ('Int32', Int32Value),
                            ('Int64', Int64Value),
                            ('SByte', SByteValue),
                            ('Single', SingleValue),
                            ('Stream', PrimitiveValue),
                            ('String', StringValue),
                            ('TimeOfDay', TimeOfDayValue)):
            primitive = PrimitiveType()
            primitive.set_base(primitive_base)
            primitive.name = name
            primitive.value_type = vtype
            primitive.declare(cls.edm)
        # set the default facets to sensible defaults
        cls.edm['DateTimeOffset'].set_precision(6)  # ms accuracy
        cls.edm['Decimal'].set_precision(None, -1)  # variable scale
        cls.edm['Duration'].set_precision(6)        # ms accuracy
        cls.edm['String'].set_unicode(True)         # unicode default
        cls.edm['TimeOfDay'].set_precision(6)       # ms accuracy
        geography_base = PrimitiveType()
        geography_base.set_base(primitive_base)
        geography_base.name = "Geography"
        geography_base.declare(cls.edm)
        for name, vtype in (('GeographyPoint', GeographyPointValue),
                            ('GeographyLineString', GeographyLineStringValue),
                            ('GeographyPolygon', GeographyPolygonValue),
                            ('GeographyMultiPoint', GeographyMultiPointValue),
                            ('GeographyMultiLineString',
                             GeographyMultiLineStringValue),
                            ('GeographyMultiPolygon',
                             GeographyMultiPolygonValue),
                            ('GeographyCollection', GeographyCollectionValue)):
            geography = PrimitiveType()
            geography.set_base(geography_base)
            geography.name = name
            geography.value_type = vtype
            geography.declare(cls.edm)
        geometry_base = PrimitiveType()
        geometry_base.set_base(primitive_base)
        geometry_base.name = "Geometry"
        geometry_base.declare(cls.edm)
        for name, vtype in (('GeometryPoint', GeometryPointValue),
                            ('GeometryLineString', GeometryLineStringValue),
                            ('GeometryPolygon', GeometryPolygonValue),
                            ('GeometryMultiPoint', GeometryMultiPointValue),
                            ('GeometryMultiLineString',
                             GeometryMultiLineStringValue),
                            ('GeometryMultiPolygon',
                             GeometryMultiPolygonValue),
                            ('GeometryCollection', GeometryCollectionValue)):
            geometry = PrimitiveType()
            geometry.set_base(geometry_base)
            geometry.name = name
            geometry.value_type = vtype
            geometry.declare(cls.edm)
        return cls.edm


class QualifiedAnnotation(Named):

    """A Qualified Annotation (applied to a model element)

    The name of this object is the qualifier used or *an empty string*
    if the annotation was applied without a qualifier."""

    def __init__(self):
        Named.__init__(self)
        #: the term that defines this annotation
        self.term = None

    def qualified_declare(self, annotations):
        """Declares this annotation in an Annotations instance."""
        if self.name is None:
            self.name = ""
        if self.term.qname is None:
            raise ValueError("%s: associated Term was not declared" %
                             self.term.name)
        a = annotations.get(self.term.qname, None)
        if a is None:
            a = Annotation()
            a.name = self.term.qname
            a.declare(annotations)
        self.declare(a)


class Annotation(NameTable):

    """An Annotation (applied to a model element).

    The name of this object is the qualified name of the term that
    defines this annotation.  The Annnotation is itself a name table
    comprising the :class:`QualifiedAnnotation` instances."""

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier

        Raises ValueError if the name is not valid (or is None).
        Empty string is allowed, as it represents no qualifier."""
        if name is None:
            raise ValueError("None is not a valid qualifier (use '')")
        elif name and not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid qualifier" % name)

    def check_value(self, value):
        if not isinstance(value, QualifiedAnnotation):
            raise TypeError(
                "QualifiedAnnotation required, found %s" % repr(value))


class Annotations(NameTable):

    """The set of Annotations applied to a model element.

    A name table that contains :class:`Annotation` instances keyed on
    the qualified name of the defining term."""

    def check_name(self, name):
        """Checks the validity of 'name' against QualifiedName

        Raises ValueError if the name is not valid (or is None)."""
        if name is None:
            raise ValueError("Annotation with no name")
        elif not self.is_qualified_name(name):
            raise ValueError("%s is not a valid qualified name" % name)

    def check_value(self, value):
        if not isinstance(value, Annotation):
            raise TypeError(
                "Annotation required, found %s" % repr(value))

    def qualified_get(self, term, qualifier=None):
        """Looks up an annotation

        Returns None if no annotation has been declared for the given
        term (and optional qualifier)."""
        try:
            a = self[term]
            return a['' if qualifier is None else qualifier]
        except KeyError:
            return None


class EntityModel(NameTable):

    """An EntityModel is a name table of OData Schemas"""
    def __init__(self):
        super(EntityModel, self).__init__()
        # all entity models have the built-in Edm namespace in scope
        self['Edm'] = edm

    def check_name(self, name):
        """EntityModels contain schemas that define namespaces

        The syntax for a namespace is a dot-separated list of simple
        identifiers."""
        if name is None:
            raise ValueError("unnamed schema")
        if not self.is_namespace(name):
            raise ValueError("%s is not a valid namespace" % name)

    def check_value(self, value):
        """EntityModels contain Schemas"""
        if not isinstance(value, Schema):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<EntityModel>" if self.name is None else self.name))

    @staticmethod
    def split_qname(qname):
        dot = qname.rfind('.')
        if dot < 1 or dot > len(qname) - 1:
            # ".name" and "name." don't count!
            raise ValueError("qualified name required: %s" % qname)
        return qname[:dot], qname[dot + 1:]

    def qualified_get(self, qname):
        """Looks up qname in this entity model.

        qname
            A string or a :class:`QualifiedName` instance.

        Returns the object it points to or raises KeyError."""
        if isinstance(qname, QualifiedName):
            namespace, name = qname
        else:
            namespace, name = self.split_qname(qname)
        return self[namespace][name]

    def qualified_tell(self, qname, callback):
        """Deferred qualified name lookup.

        Similar to :meth:`Nametable.tell` except that it waits until
        both the Schema containing qname is defined *and* the target
        name is defined within that Schema.

        If the entity model or the indicated Schema is closed without
        qname being declared then the callback is called passing None."""
        nsname, name = self.split_qname(qname)
        ns = self.get(nsname, None)
        if ns is None:
            self.tell(nsname, self._qcallback(name, callback))
        else:
            ns.tell(name, callback)

    def _qcallback(self, name, callback):

        def _qcallback_closure(ns):
            if ns is None:
                callback(None)
            else:
                ns.tell(name, callback)

        return _qcallback_closure

    def close(self):
        """Closing the entity model closes all namespaces it contains"""
        for ns in self.values():
            ns.close()
        super(EntityModel, self).close()

    def resolve_nppath(self, from_type, path):
        """Resolves a navigation property path

        from_type
            The object to start resolving from, must be a structured
            type.

        path
            An array of strings and QualifiedName instances representing
            the path.

        The rules for following navigation property paths are different
        depending on the context. In Part 3, 7.1.4 they are defined
        as follows:

            The path may traverse complex types, including derived
            complex types, but MUST NOT traverse any navigation
            properties"""
        pos = 0
        try:
            while pos < len(path):
                segment = path[pos]
                pos += 1
                if is_text(segment):
                    # must resole to a property of this type
                    p = from_type[segment]
                    if isinstance(p, NavigationProperty):
                        if pos < len(path):
                            raise PathError(
                                "Can't traverse navigation property %s" %
                                p.name)
                        return p
                    else:
                        from_type = p.type_def
                        # must be a structured type, not a primitive or
                        # collection
                        if not isinstance(from_type, StructuredType):
                            raise PathError(
                                "Can't resolve path containing: %s" %
                                repr(from_type))
                elif isinstance(segment, QualifiedName):
                    # a type-cast
                    new_type = self.qualified_get(segment)
                    if not isinstance(new_type, StructuredType):
                        raise PathError(
                            "Can't resolve path containing: %s" %
                            repr(new_type))
                    # for type-casting we allow derived types
                    if new_type.is_derived_from(from_type, strict=False):
                        from_type = new_type
                    else:
                        raise PathError(
                            "Can't resolve cast from %s to %s" %
                            (from_type.qname, new_type.qname))
                else:
                    raise TypeError(
                        "Bad path segment %s" % repr(segment))
        except KeyError as err:
            raise PathError("Path segment not found: %s" % str(err))
        # if we get here then the path finished at a complex property
        # of type-cast segment.
        raise PathError("Path did not resolve to a navigation property")


class NominalType(Named):

    """A Nominal Type

    In Pyslet, all defined types are represented in the model by
    *instances* of NominalType.  Nominal types all have a :attr:`name`
    and typically a base type.

    NominalType instances are callable, returning a :class:`Value` instance
    of an appropriate class for representing a value of the type.  The
    instance returned is a null value of this of type."""

    def __init__(self):
        super(NominalType, self).__init__()
        #: the base type (may be None for built-in abstract types)
        self.base = None
        # the class used for values of this type
        self.value_type = Value

    def __call__(self):
        return self.value_type(type_def=self)

    def set_base(self, base):
        """Sets the base type of this type

        base
            Must be of the correct type to be the base of the current
            instance.

        The default implementation raises NotImplementedError because
        NominalType itself is an abstract class."""
        raise NotImplementedError

    def is_derived_from(self, t, strict=False):
        """Returns True if this type is derived from type t

        strict
            Optional flag determining the behaviour when t
            is the type itself::

                t.is_derived_from(t, True) is False

            as t is not strictly derived from itself. By default, strict
            mode is off::

                t.is_derived_from(t) is True"""
        curr_type = self
        if not strict and t is self:
            return True
        while curr_type.base is not None:
            curr_type = curr_type.base
            if curr_type is t:
                return True
        return False


class PrimitiveType(NominalType):

    """A Primitive Type declaration

    Instances represent primitive type delcarations, such as those made
    by a TypeDefinition.  The built-in Edm Schema contains instances
    representing the base primitie types themselves."""

    # used for Decimal rounding
    dec_nleft = decimal.getcontext().Emax + 1
    dec_nright = 0
    dec_digits = (1, ) * decimal.getcontext().prec

    # used for temporal rounding
    temporal_q = decimal.Decimal((0, (1, ), 0))

    def __init__(self):
        super(PrimitiveType, self).__init__()
        self.value_type = PrimitiveValue
        self.max_length = None
        self.unicode = None
        self.precision = None
        self.scale = None
        self.srid = None

    def set_base(self, base):
        """Sets the base type of this type

        The base must also be a PrimitiveType."""
        if not isinstance(base, PrimitiveType):
            raise TypeError(
                "%s is not a suitable base for %s" % (base.qname, self.name))
        # update the value_type, impose a further restriction that the
        # incoming value_type MUST be a subclass of the previous
        # value_type.  In other words, you can't have a type based on
        # Edm.String and use set_base to 'rebase' it to Edm.Int64
        if not issubclass(base.value_type, self.value_type):
            raise TypeError(
                "Mismatched value types: can't base %s on %s" %
                (self.name, base.qname))
        self.base = base
        self.value_type = base.value_type

    def set_max_length(self, max_length):
        self.max_length = max_length

    def set_precision(self, precision, scale=None):
        if issubclass(self.value_type, DecimalValue):
            # precision must be positive (or None)
            if precision is None:
                if scale is None:
                    # both unspecified, scale implied 0 (default)
                    self.dec_nright = PrimitiveType.dec_nright
                elif scale < 0:
                    # variable scale, no limit on right digits as
                    # precision is also unlimited.
                    self.dec_nright = -(decimal.getcontext().Emin -
                                        decimal.getcontext().prec + 1)
                else:
                    # what is undefined - scale?  don't limit left
                    # digits, could perhaps throw an error here!
                    # scale must be <= precision, limit right digits
                    self.dec_nright = scale
                self.dec_nleft = PrimitiveType.dec_nleft
                self.dec_digits = PrimitiveType.dec_digits
            else:
                if precision <= 0:
                    raise ValueError(
                        "Positive integer (or None) required for "
                        "Decimal precision")
                if scale is None:
                    # just precision specified, scale is implied 0
                    self.dec_nleft = precision
                    self.dec_nright = 0
                elif scale < 0:
                    # variable scale, up to precision on the right
                    self.dec_nleft = PrimitiveType.dec_nleft
                    self.dec_nright = precision
                elif scale > precision:
                    raise ValueError("Scale exceeds precision")
                else:
                    self.dec_nleft = precision - scale
                    self.dec_nright = scale
                self.dec_digits = (1, ) * min(decimal.getcontext().prec,
                                              precision)
            self.precision = precision
            self.scale = scale
        elif issubclass(self.value_type, (DateTimeOffsetValue, DurationValue,
                                          TimeOfDayValue)):
            # precision must be non-negative (max 12)
            if precision is None:
                # no precision = 0
                self.temporal_q = decimal.Decimal((0, (1, ), 0))
                self.precision = None
            else:
                if precision < 0 or precision > 12:
                    raise ValueError(
                        "Integer from 1..12 required for temporal precision")
                # overload the class attribute
                self.temporal_q = decimal.Decimal(
                    (0, (1, ) * (precision + 1), -precision))
                self.precision = precision

    def set_unicode(self, unicode_flag):
        if issubclass(self.value_type, StringValue):
            self.unicode = unicode_flag

    def set_srid(self, srid):
        if issubclass(self.value_type, (GeographyValue, GeometryValue)):
            self.srid = srid

    def value_from_str(self, src):
        logging.debug("%s.value_from_str", self.value_type.edm_name)
        return self.value_type.from_str(src)


class EnumerationType(NameTable, NominalType):

    """An EnumerationType declaration"""

    def __init__(self, base=None):
        super(EnumerationType, self).__init__()
        if base is None:
            base = edm['Int32']
        elif base not in (edm['Byte'], edm['SByte'], edm['Int16'],
                          edm['Int32'], edm['Int64']):
            raise ValueError("Enumeration base must be integer type")
        self.base = base
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

    def set_is_flags(self):
        """Sets is_flags to True.

        If the Enumeration already has members declared will raise
        ModelError."""
        if self.members:
            raise ModelError(
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

    def __setitem__(self, key, value):
        self.check_value(value)
        if self.assigned_values is None:
            self.assigned_values = value.value is None
        if self.assigned_values:
            if value.value is not None:
                raise ModelError(
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
                raise ModelError("Enum member %s requires value" % value.name)
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
        p = ODataParser(src)
        v = self()
        mlist = p.require_enum_value()
        if not self.is_flags:
            if len(mlist) != 1:
                raise ModelError("Enum member: expected single name or value")
            v.set(mlist[0])
        else:
            v.set(mlist)
        p.require_end()
        return v


class Member(Named):

    """Represents a member of an enumeration"""

    def __init__(self):
        super(Member, self).__init__()
        #: the integer value corresponding to this member
        #: defaults to None: auto-assigned when declared
        self.value = None


class CollectionType(NominalType):

    """Collections are treated as types in the model

    In fact, OData does not allow you to declare a named type to be a
    collection, instead, properties, navigation properties and entity
    collections define collections in terms of single-valued named types.

    To make implementing the model easier we treat these as private type
    definitions.  That is, type definitions which are never declared in
    the associated schema but are used as the type of other elements
    that are part of the model."""

    def __init__(self, item_type):
        super(CollectionType, self).__init__()
        #: the type being collected, we do not allow collections of
        #: collections
        self.item_type = item_type
        self.value_type = CollectionValue


class StructuredType(NameTable, NominalType):

    """A Structured Type declaration"""

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed property")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        if not isinstance(value, (Property, NavigationProperty)):
            raise TypeError(
                "Property or NavigationProperty required, found %s" %
                repr(value))

    def set_base(self, base):
        """Sets the base type of this type

        When structured types are associated with a base type the
        properties of the base type are copied."""
        if not isinstance(base, StructuredType):
            raise TypeError(
                "%s is not a suitable base for %s" % (base.qname, self.name))
        self.base = base

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

    def close(self):
        # before we close this nametable, add in the declarataions from
        # the base type if present
        if self.base is not None:
            for pname, p in self.base.items():
                self[pname] = p
        super(StructuredType, self).close()


class Property(Named):

    """A Property declaration"""

    def __init__(self):
        super(Property, self).__init__()
        #: the type definition for values of this property
        self.type_def = None
        #: whether or not the property value can be null (or contain
        #: null in the case of a collection)
        self.nullable = True
        #: the default value of the property (primitive/enums only)
        self.default_value = None

    def set_type(self, type_def):
        self.type_def = type_def

    def set_nullable(self, nullable):
        self.nullable = nullable


class NavigationProperty(Named):

    """A NavigationProperty declaration"""

    def __init__(self):
        super(NavigationProperty, self).__init__()
        #: the type definition for values of this property
        self.type_def = None
        #: whether or not this property is a collection
        self.collection = False
        #: whether of not the linked entities are contained
        self.containment = False
        #: the partner of this navigation property
        self.partner = None
        #: reverse partners are navigation properties that point back to
        #: us, there can be more than one but if the relationship is
        #: bidirectional there will *exactly* one and it will be the
        #: same object as self.partner.
        self.reverse_partners = []

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_containment(self, contains_target):
        self.containment = contains_target

    def set_type(self, type_def, collection):
        self.type_def = type_def
        self.collection = collection

    def set_partner(self, partner):
        if self.reverse_partners:
            if len(self.reverse_partners) > 1:
                raise ModelError(
                    "%s cannot specify a partner as multiple navigation "
                    "properties already partner it" %
                    self.name)
            if self.reverse_partners[0] is not partner:
                raise ModelError(
                    "%s is already a partner of %s" %
                    (self.reverse_partners[0].name, self.name))
        self.partner = partner
        partner.reverse_partners.append(self)


class ComplexType(StructuredType):

    """A ComplexType declaration"""

    def __init__(self):
        super(ComplexType, self).__init__()
        self.value_type = ComplexValue


class EntityType(StructuredType):

    """An EntityType declaration"""
    pass


class Term(Named):

    """Represents a defined term in the OData model"""
    pass


class EntityContainer(NameTable):

    """An EntityContainer is a container for OData entities."""

    def __init__(self):
        super(EntityContainer, self).__init__()
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
        if self.extends is not None:
            for name, item in self.extends.items():
                # we tolerate cycles, which means that if an item is
                # already declared we ignore it
                old_item = self.get(name, None)
                if old_item is item:
                    continue
                self[name] = item
        super(EntityContainer, self).close()


class EntitySet(Named):

    pass


class Singleton(Named):

    pass


class Value(BoolMixin):

    """Abstract class to represent a value in OData.

    All values processed by OData classes are reprsented by instances of
    this class.  All values have an associated type definition that
    controls the range of values it can represent (see
    :class:`NominalType` and its sub-classes).

    Values are mutable so cannot be used as dictionary keys (they are
    not hashable).  They evaluate to True unless they are null, in which
    case they evaluate to False."""

    def __init__(self, type_def):
        #: the type definition that controls the value space
        self.type_def = type_def

    __hash__ = None

    def __bool__(self):
        return not self.is_null()

    def is_null(self):
        """Returns True if this object is null.

        You can use simple Python boolean evaluation with instances, the
        purpose of this method is to allow derived classes to implement
        an appropriate null test."""
        return True

    def cast(self, type_def):
        """Implements the cast function

        type_def
            An instance of :class:`NominalType`.

        Returns a new instance casting the current value to the type
        specified.  The default catch-all implementation generates
        a null value of the target type representing a failed cast."""
        return type_def()


class PrimitiveValue(UnicodeMixin, Value):

    """Class to represent a primitive value in OData.

    This class is not normally instantiated directly, use one of the
    *from\_* factory methods to construct a value of the correct
    sub-class from a string, literal or native python value.  Use one of
    the child classes directly to create a new value from an apporpriate
    python value using the default primitive type definition (i.e., with
    no additional constraining facets).  Otherwise, create instances by
    calling an instance of :class:`PrimitiveType`.

    If you do instantiate this class directly it will create a special
    type-less null value.

    When instances can be converted to strings they generate strings
    according to the primitiveValue ABNF defined in the specification.
    null values will raise a ValueError and cannot be serialised as
    strings."""

    edm_name = 'PrimitiveType'

    def __init__(self, pvalue=None, type_def=None):
        Value.__init__(
            self, edm[self.edm_name] if type_def is None else type_def)
        self.value = None
        if pvalue is not None:
            self.set(pvalue)

    def is_null(self):
        """Returns True if this object is null."""
        return self.value is None

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            # are the types compatible? lazy comparison to start with
            return self.value == other.value
        else:
            return self.value == other

    def __ne__(self, other):
        return not self == other

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(self.value)

    def set(self, value):
        """Sets the value from a python 'native' value representation

        The default implementation raises TypeError if value is anything
        other than None (as a typeless null is always null).

        Derived classes override this method to provide a more expansive
        set of value conversions from core Python types but to prevent
        mixing of python-native and odata-meta values instances of
        :class:`PrimitiveValue`, or any class derived from it, are not
        allowed and will raise TypeError.

        If the value argument is not of a suitable type for setting this
        primitive value instance then TypeError is raised.  If it is a
        suitable type but has a value out of the range permitted then
        ValueError is raised."""
        if value is None:
            self.value = None
        else:
            raise TypeError

    @classmethod
    def from_value(cls, value):
        """Constructs a primitive value from a python native value

        The returned type depends on the input value:

        None
            A type-less null (PrimitiveValue instance)
        bool
            A BooleanValue instance
        bytes (Python2 str)
            BinaryValue instance
        datetime.date instance
            A DateValue instance
        datetime.datetime instance
            A DateTimeOffsetValue instance
        datetime.time instance
            A TimeOfDayValue instance
        decimal.Decimal instance
            A DecimalValue instance
        float
            A DoubleValue instance if the value is within range,
            otherwise a DecimalValue instance.
        int
            An Int64Value instance if the value is within range,
            otherwise a DecimalValue instance.
        long (Python 2 only)
            As for int.
        pyslet.odata4.geotypes.PointLiteral instance
            If SRID=0, GeometryPointValue, otherwise a
            GeographyPointValue instance.
        pyslet.odata4.geotypes.LineStringLiteral instance
            If SRID=0, GeometryLineStringValue, otherwise a
            GeographyLineStringValue instance.
        pyslet.odata4.geotypes.PolygonLiteral instance
            If SRID=0, GeometryPolygonValue, otherwise a
            GeographyPolygonValue instance.
        pyslet.odata4.geotypes.MultiPointLiteral instance
            If SRID=0, GeometryMultiPointValue, otherwise a
            GeographyMultiPointValue instance.
        pyslet.odata4.geotypes.MultiLineStringLiteral instance
            If SRID=0, GeometryMultiLineStringValue, otherwise a
            GeographyMultiLineStringValue instance.
        pyslet.odata4.geotypes.MultiPolygonLiteral instance
            If SRID=0, GeometryMultiPolygonValue, otherwise a
            GeographyMultiPolygonValue instance.
        pyslet.odata4.geotypes.GeoCollectionLiteral instance
            If SRID=0, GeometryCollectionValue, otherwise a
            GeographyCollectionValue instance.
        pyslet.iso8601.Date instance
            A DateValue instance
        pyslet.iso8601.Time instance
            A TimeOfDayValue instance
        pyslet.iso8601.TimePoint instance
            A DateTimeOffset instance.  The input value *must* be fully
            specified and have timezone information.
        pyslet.xml.xsdatatypes.Duration instance
            A DurationValue instance
        str (Python2 unicode only)
            A StringValue instance
        uuid.UUID instance
            A GuidValue instance

        All other input values raise TypeError."""
        if value is None:
            result = PrimitiveValue()
        elif value is True or value is False:
            result = BooleanValue()
            result.value = value
        elif is_unicode(value):
            result = StringValue()
            result.value = value
        elif isinstance(value, bytes):
            result = BinaryValue()
            result.value = value
        elif isinstance(value, decimal.Decimal):
            result = DecimalValue()
            result.value = value
        elif isinstance(value, int) or isinstance(value, long2):
            if value > Int64Value.MAX or value < Int64Value.MIN:
                result = DecimalValue.from_value(value)
            else:
                result = Int64Value()
                result.value = value
        elif isinstance(value, float):
            if value > DoubleValue.MAX or value < DoubleValue.MIN:
                result = DecimalValue.from_value(value)
            else:
                result = DoubleValue()
                result.value = value
        # warning: datetime() is derived from date(), check this first!
        elif isinstance(value, (TimePoint, datetime.datetime)):
            result = DateTimeOffsetValue()
            result.set(value)
        elif isinstance(value, (Date, datetime.date)):
            result = DateValue()
            result.set(value)
        elif isinstance(value, (Time, datetime.time)):
            result = TimeOfDayValue()
            result.set(value)
        elif isinstance(value, xsi.Duration):
            result = DurationValue()
            result.set(value)
        elif isinstance(value, uuid.UUID):
            result = GuidValue()
            result.set(value)
        elif isinstance(value, geo.PointLiteral):
            if value.srid:
                result = GeographyPointValue()
            else:
                result = GeometryPointValue()
            result.set(value)
        elif isinstance(value, geo.LineStringLiteral):
            if value.srid:
                result = GeographyLineStringValue()
            else:
                result = GeometryLineStringValue()
            result.set(value)
        elif isinstance(value, geo.PolygonLiteral):
            if value.srid:
                result = GeographyPolygonValue()
            else:
                result = GeometryPolygonValue()
            result.set(value)
        elif isinstance(value, geo.MultiPointLiteral):
            if value.srid:
                result = GeographyMultiPointValue()
            else:
                result = GeometryMultiPointValue()
            result.set(value)
        elif isinstance(value, geo.MultiLineStringLiteral):
            if value.srid:
                result = GeographyMultiLineStringValue()
            else:
                result = GeometryMultiLineStringValue()
            result.set(value)
        elif isinstance(value, geo.MultiPolygonLiteral):
            if value.srid:
                result = GeographyMultiPolygonValue()
            else:
                result = GeometryMultiPolygonValue()
            result.set(value)
        elif isinstance(value, geo.GeoCollectionLiteral):
            if value.srid:
                result = GeographyCollectionValue()
            else:
                result = GeometryCollectionValue()
            result.set(value)
        else:
            raise TypeError
        return result

    @classmethod
    def from_str(cls, src):
        """Constructs a primitive value from a source string

        This is an abstract method, each primitive type has its own
        parsing rules and its values can only be constructed from
        strings in a typed context.  Contrast this with the method
        :meth:`from_literal`."""
        raise NotImplementedError

    @classmethod
    def from_literal(cls, src):
        """Constructs a primitive value from a literal string

        Literal strings can appear directly in expressions and may or
        may not be explicitly typed.  The ABNF is ambiguous where
        numeric literals are concerned.  You may :meth:`cast` the result
        to the required value type if required."""
        raise NotImplementedError

    def cast(self, type_def):
        """Implements the cast function

        Any primitive type can be cast to a String using the ABNF
        format."""
        result = type_def()
        if isinstance(result, type(self)):
            try:
                result.set(self.value)
            except ValueError:
                # bounds exceeded perhaps
                pass
        elif isinstance(result, StringValue):
            try:
                result.set(to_text(self))
            except ValueError:
                # bounds must be exceeded
                pass
            return result
        return result


class NumericValue(PrimitiveValue):

    """Abstract class for representing all numeric primitives"""

    if py2:
        _num_types = (int, long2, float, decimal.Decimal)
    else:
        _num_types = (int, float, decimal.Decimal)

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(self.value)

    def cast(self, type_def):
        """Implements the numeric cast exceptions"""
        if issubclass(type_def.value_type, NumericValue):
            result = type_def()
            try:
                result.set(self.value)
                if issubclass(type_def.value_type, FloatValue) and \
                        result.value is not None:
                    if math.isinf(result.value):
                        if not isinstance(self, FloatValue) or \
                                not math.isinf(self.value):
                            # only allow inf from inf!
                            result.value = None
            except ValueError:
                # bounds exception
                pass
            return result
        else:
            return PrimitiveValue.cast(self, type_def)


class IntegerValue(NumericValue):

    """Abstract class for representing all integer primitives

    All types of IntegerValue can be set from numeric values of the
    following types: int, long (Python 2), float and Decimal. The native
    bool is also an int (isinstance(True, int) is True!) so these value
    are also accepted as synonymous for 0 and 1 in the usual way but
    non-numeric types are not allowed (even if they have a valid
    __bool__/__nonzero__ implementation).

    Rounding is towards zero where necessary.  If the value does not fit
    in the valid range for the sub-class then ValueError is raised.  The
    class attributes MIN and MAX are defined to contain the minimum and
    maximum values.  For signed values, MIN is the largest representable
    negative value."""

    _pytype = None      # override for each integer type

    def set(self, value):
        if isinstance(value, self._num_types):
            v = self._pytype(value)
            if v < self.MIN or v > self.MAX:
                raise ValueError(
                    "%s out of range for %s" % (repr(value), self.edm_name))
            else:
                self.value = v

        elif value is None:
            self.value = None
        else:
            raise TypeError(
                "can't set %s from %s" % (self.edm_name, repr(value)))


class FloatValue(NumericValue):

    """Abstract class for representing all floating-point primitives

    Both types of FloatValue can be set from numeric values of the
    following types: int (bool, see :class:`IntegerValue`), long (Python
    2), float and Decimal.

    If the value does not fit in the valid range for the sub-class then
    the value is set to one of the signed infinity values inf or -inf
    that are supported by OData.  ValueError is never raised.  The class
    attributes MIN and MAX are defined to contain the minimum and
    maximum representable values and DECIMAL_MIN and DECIMAL_MAX are
    defined to hold the Decimal representations of those values."""

    _inf = float('inf')
    _negative_inf = float('-inf')

    def set(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, decimal.Decimal):
            if value > self.DECIMAL_MAX:
                self.value = self._inf
            elif value < self.DECIMAL_MIN:
                self.value = self._negative_inf
            else:
                self.value = float(value)
        elif isinstance(value, self._num_types):
            try:
                value = float(value)
                if math.isnan(value) or math.isinf(value):
                    self.value = value
                elif value > self.MAX:
                    self.value = self._inf
                elif value < self.MIN:
                    self.value = self._negative_inf
                else:
                    self.value = value
            except OverflowError:
                # Yes: integers can be bigger than floats!
                if value > 0:
                    self.value = self._inf
                else:
                    self.value = self._negative_inf
        else:
            raise TypeError(
                "can't set %s from %s" % (self.edm_name, repr(value)))


class BinaryValue(PrimitiveValue):

    """Represents a value of type Edm.Binary

    The value member of a BinaryValue is either None or of type bytes.

    Binary literals are base64url encoded binary-strings as per
    http://tools.ietf.org/html/rfc4648#section-5

    Binary values can also be set from most Python types, character
    strings are UTF-8 encoded, any other types are converted using the
    builtin bytes function.  For consistency, BinaryValues can *not* be
    set from instances of PrimitiveValue."""

    edm_name = 'Binary'

    def set(self, value=None):
        if value is None:
            self.value = None
        else:
            if isinstance(value, bytes):
                new_value = value
            elif is_unicode(value):
                new_value = value.encode("utf-8")
            elif isinstance(value, PrimitiveValue):
                raise TypeError
            else:
                new_value = bytes(value)
            # check limits
            if self.type_def.max_length and len(new_value) > \
                    self.type_def.max_length:
                raise ValueError("MaxLength exceeded for binary value")
            self.value = new_value

    @classmethod
    def from_str(cls, src):
        p = ODataParser(src)
        v = p.require_binary_value()
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(base64.urlsafe_b64encode(self.value))


class BooleanValue(PrimitiveValue):

    """Represents a value of type Edm.Boolean

    The value member of a BooleanValue is either None, True or False.

    Boolean literals are one of the strings "true" or "false"

    Boolean values can be set from any other input type (except
    PrimitiveValue instances), the resulting value is the logical
    evaluation of the input value.  E.g., empty strings and lists are
    False, non-zero integer values True, etc."""

    edm_name = 'Boolean'

    def set(self, value=None):
        if value is None or value is True or value is False:
            self.value = value
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            self.value = True if value else False

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return "true" if self.value else "false"

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax is case insenstive for the values "true" and
        "false" but case sensitive for the value 'null'."""
        p = ODataParser(src)
        v = p.require_boolean_value()
        p.require_end()
        return v


class ByteValue(IntegerValue):

    """Represents a value of type Edm.Byte"""

    MIN = 0
    MAX = 255

    _pytype = int

    edm_name = 'Byte'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_byte_value()
        p.require_end()
        return v


class DecimalValue(NumericValue):

    """Represents a value of type Edm.Decimal

    Can be set from numeric values of the
    following types: int (bool, see :class:`IntegerValue` for details),
    long (Python 2), float and Decimal."""

    edm_name = 'Decimal'

    def _round(self, value):
        precision = len(self.type_def.dec_digits)
        vt = value.as_tuple()
        vprec = len(vt.digits)
        # check bounds on exponent
        if vt.exponent + vprec > self.type_def.dec_nleft:
            raise ValueError("Value too large for scaled Decimal")
        if vt.exponent + vprec >= precision:
            # negative scale results in integer (perhaps with trailing
            # zeros)
            q = decimal.Decimal(
                (0, self.type_def.dec_digits, vprec + vt.exponent - precision))
        else:
            # some digits to the right of the decimal point, this needs
            # a litte explaining.  We take the minimum of:
            #   1. the specified max scale in the type
            #   2. the number of digits to the right of the point in the
            #      original value (-vt.exponent) - to prevent spurious 0s
            #   3. the number of digits to the right of the point after
            #      rounding to the current precision - to prevent us
            #      exceeding precision
            rdigits = min(self.type_def.dec_nright, -vt.exponent,
                          max(0, precision - (vprec + vt.exponent)))
            q = decimal.Decimal((0, self.type_def.dec_digits, -rdigits))
        return value.quantize(q, rounding=decimal.ROUND_HALF_UP)

    def set(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, (int, bool, long2)):
            self.value = self._round(decimal.Decimal(value))
        elif isinstance(value, decimal.Decimal):
            self.value = self._round(value)
        elif isinstance(value, float):
            self.value = self._round(decimal.Decimal(repr(value)))
        else:
            raise TypeError("Can't set Decimal from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax requires at least one digit before the decimal
        point and, if a point is given, at least one digit after it.

        The ABNF allows the use of the %-encoded sequence %2B to
        represent the + sign but we do not allow it here on the
        assumption that the value has already been unencoded.  That
        means that we won't allow '%2B1' to be interpreted as +1 when it
        is used in XML attribute/element values or JSON decimal strings
        which I assume is what is intended."""
        p = ODataParser(src)
        v = p.require_decimal_value()
        p.require_end()
        return v


class DoubleValue(FloatValue):

    """Represents a value of type Edm.Double"""

    edm_name = 'Double'

    try:
        MAX = (2 - 2 ** -52) * 2 ** 1023
    except OverflowError:
        try:
            MAX = (2 - 2 ** -23) * 2 ** 127
            logging.warning(
                "IEEE 754 binary64 not supported, using binary32 instead")
        except OverflowError:
            try:
                MAX = (2 - 2 ** -10) * 2 ** 15
                logging.warning(
                    "IEEE 754 binary32 not supported, using binary16 instead")
            except OverflowError:
                logging.error("IEEE 754 binary16 not supported""")
                raise

    MIN = -MAX

    DECIMAL_MAX = decimal.Decimal(repr(MAX))
    DECIMAL_MIN = decimal.Decimal(repr(MIN))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_double_value()
        p.require_end()
        return v


class Int16Value(IntegerValue):

    MIN = -32768
    MAX = 32767

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int16'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_int16_value()
        p.require_end()
        return v


class Int32Value(IntegerValue):

    MIN = -2147483648
    MAX = 2147483647

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int32'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_int32_value()
        p.require_end()
        return v


class Int64Value(IntegerValue):

    MAX = 9223372036854775807
    MIN = -9223372036854775808

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int64'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_int64_value()
        p.require_end()
        return v


class SByteValue(IntegerValue):

    MIN = -128
    MAX = 127

    _pytype = int

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_sbyte_value()
        p.require_end()
        return v

    edm_name = 'SByte'


class SingleValue(FloatValue):

    """Represents a value of type Edm.Single"""

    edm_name = 'Single'

    try:
        MAX = (2 - 2 ** -23) * 2 ** 127
    except OverflowError:
        try:
            MAX = (2 - 2 ** -10) * 2 ** 15
            logging.warning(
                "IEEE 754 binary32 not supported, using binary16 instead")
        except OverflowError:
            logging.error("IEEE 754 binary16 not supported""")
            raise

    MIN = -MAX

    DECIMAL_MAX = decimal.Decimal(repr(MAX))
    DECIMAL_MIN = decimal.Decimal(repr(MIN))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_single_value()
        p.require_end()
        return v


class DateValue(PrimitiveValue):

    """Represents a value of type Edm.Date

    The value member of a DateValue is either None or an instance of
    :class:`pyslet.iso8601.Date`.

    Date literals allow an expanded range of dates with a potentially
    unlimited range using ISO 8601 extended format (using hyphen
    separators).  As a result, Date instances always have xdigits set to
    -1.

    Date values can be set from an instance of
    :py:class:`iso8601.Date` though the date must be complete (i.e., it
    must have day precision). The standard Python datetime.date type may
    also be used, the datetime.datetime type is defined to be a subclass
    of datetime.date so can also be used (the time component being
    discarded)."""

    edm_name = 'Date'

    def set(self, value):
        if isinstance(value, Date):
            # force xdigits=-1, must be complete
            if not value.complete():
                raise ValueError("Can't set Date from %s" % str(value))
            else:
                self.value = value.expand(xdigits=-1)
        elif isinstance(value, datetime.date):
            bce, c, y = Date.split_year(value.year)
            self.value = Date(bce=bce, century=c, year=y, month=value.month,
                              day=value.day, xdigits=-1)
        elif value is None:
            self.value = None
        else:
            raise TypeError("Can't set Date from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_date_value()
        p.require_end()
        return v


def _struncate(temporal_q, s):
    # truncate a seconds value to the active temporal precision
    if isinstance(s, float):
        s = decimal.Decimal(
            repr(s)).quantize(temporal_q, rounding=decimal.ROUND_DOWN)
        if temporal_q.as_tuple().exponent == 0:
            return int(s)
        else:
            return float(s)
    else:
        return s


class DateTimeOffsetValue(PrimitiveValue):

    """Represents a value of type Edm.DateTimeOffset

    The value member of a DateTimeOffsetValue is either None or an
    instance of :class:`pyslet.iso8601.TimePoint`.  OData excludes leap
    seconds.

    DateTimeOffset literals allow an expanded range of dates with
    potentially unlimited range (as per :class:`DateValue`).  As a
    result, the date component of the TimePoint is always in expanded
    form supporting a variable number of leading century digits.

    DateTimeOffset values can be set from an instance of
    :py:class:`iso8601.TimePoint` though the value must be complete
    (have second precision) and have a valid timezone.  There is *no*
    automatic assumption of UTC when setting from TimePoint instances.

    The standard python datetime.datetime and datetime.date can also be
    used. Values are *assumed* to be in UTC if utcoffset returns None.
    The standard python date object is set by extending it to be the
    beginning of the UTC day 00:00:00Z on that date.

    Finally, positive numeric values are accepted and interpreted as
    unix times (seconds since the epoch).  UTC is assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.from_unix_time` factory method of
    TimePoint for more information."""

    edm_name = 'DateTimeOffset'

    def set(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, TimePoint):
            # force xdigits=-1, must be complete
            if not value.complete():
                raise ValueError(
                    "Can't set DateTimeOffset from %s" % str(value))
            elif value.time.get_zone()[0] is None:
                raise ValueError(
                    "Missing timezone in %s" % str(value))
            else:
                # handle precision
                h, m, s = value.time.get_time()
                zd, zh, zm = value.time.get_zone3()
                if h == 24:
                    h = 0
                    date = value.date.offset(days=1)
                else:
                    date = value.date
                if s >= 60:
                    # leap second!
                    if isinstance(s, float):
                        # max precision
                        s = _struncate(
                            self.type_def.temporal_q, 59.999999999999)
                    else:
                        s = 59
                elif isinstance(s, float):
                    s = _struncate(self.type_def.temporal_q, s)
                self.value = TimePoint(
                    date=date.expand(xdigits=-1),
                    time=Time(hour=h, minute=m, second=s, zdirection=zd,
                              zhour=zh, zminute=zm))
        elif isinstance(value, datetime.datetime):
            # the timezone information is probably missing, assume UTC!
            zdirection = 0
            zhour = zminute = None
            zoffset = value.utcoffset()
            if zoffset is not None:
                zoffset = zoffset.total_seconds()
                if zoffset is None:
                    zoffset = 0
                if zoffset < 0:
                    zdirection = -1
                    zoffset = -zoffset
                elif zoffset:
                    zdirection = 1
                zminute = zoffset // 60     # discard seconds
                zhour = zminute // 60
                zminute = zminute % 60
            bce, c, y = Date.split_year(value.year)
            self.value = TimePoint(
                date=Date(
                    bce=bce, century=c, year=y,
                    month=value.month,
                    day=value.day,
                    xdigits=-1),
                time=Time(
                    hour=value.hour,
                    minute=value.minute,
                    second=_struncate(
                        self.type_def.temporal_q,
                        value.second + (value.microsecond / 1000000.0)),
                    zdirection=zdirection,
                    zhour=zhour,
                    zminute=zminute))
        elif isinstance(value, datetime.date):
            bce, c, y = Date.split_year(value.year)
            self.value = TimePoint(
                date=Date(
                    bce=bce, century=c, year=y,
                    month=value.month,
                    day=value.day,
                    xdigits=-1),
                time=Time(
                    hour=0,
                    minute=0,
                    second=0,
                    zdirection=0))
        elif isinstance(value, (int, long2, float, decimal.Decimal)):
            if value >= 0:
                self.value = TimePoint.from_unix_time(
                    _struncate(self.type_def.temporal_q, value))
            else:
                raise ValueError(
                    "Can't set DateTimeOffset from %s" % str(value))
        else:
            raise TypeError("Can't set DateTimeOffset from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_date_time_offset_value()
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        h, m, s = self.value.time.get_time()
        if isinstance(s, float):
            return self.value.get_calendar_string(ndp=6, dp='.')
        else:
            return self.value.get_calendar_string(ndp=0)


class DurationValue(PrimitiveValue):

    """Represents a value of type Edm.Duration

    The value member of a DurationValue is either None or an instance of
    :class:`pyslet.xml.xsdatatypes.Duration`.

    Duration literals allow a reduced range of values as values expressed
    in terms of years, months or weeks are not allowed.

    Duration values can be set from an existing Duration only."""

    edm_name = 'Duration'

    def set(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, xsi.Duration):
            try:
                d = value.get_calender_duration()
                if d[0] or d[1]:
                    raise ValueError("Can't set Duration from %s" % str(value))
                else:
                    self.value = xsi.Duration(value)
                    self.value.seconds = _struncate(
                        self.type_def.temporal_q, self.value.seconds)
            except DateTimeError:
                # must be a week-based value
                raise ValueError("Can't set Duration from %s" % str(value))
        else:
            raise TypeError("Can't set Duration from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax follows XML schema convention of an optional sign
        followed by an ISO-type duration specified in days, hours,
        minutes and seconds."""
        p = ODataParser(src)
        v = p.require_duration_value()
        p.require_end()
        return v


class GuidValue(PrimitiveValue):

    """Represents a value of type Edm.Guid

    The value member of a GuidValue is either None or an instance of
    Python's built-in UUID class.

    Guid literals allow content in the following form:
    dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents
    [A-Fa-f0-9].

    Guid values can also be set directly from either binary or hex
    strings. Binary strings must be of length 16 and are passed as raw
    bytes to the UUID constructor, hexadecimal strings must be of length
    32 characters.  (In Python 2 both str and unicode types are accepted
    as hexadecimal strings, the length being used to determine if the
    source is a binary or hexadecimal representation.)"""
    pass

    edm_name = 'Guid'

    def set(self, value=None):
        if value is None:
            self.value = None
        elif isinstance(value, bytes) and len(value) == 16:
            self.value = uuid.UUID(bytes=value)
        elif is_text(value) and len(value) == 32:
            self.value = uuid.UUID(hex=value)
        elif is_text(value):
            raise ValueError("Can't set Guid from %s" % str(value))
        elif isinstance(value, uuid.UUID):
            self.value = value
        else:
            raise TypeError("Can't set Guid from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_guid_value()
        p.require_end()
        return v


class StringValue(PrimitiveValue):

    """Represents a value of type Edm.String

    The value member of a StringValue is either None or a character
    string (Python 2, unicode).

    The literal form of a string is the string itself.

    Values may be set from any character string or object which supports
    conversion to character string (using the builtin str/unicode
    function) with the exception of instances of PrimitiveValue which
    raise TypeError for consistency and to prevent confusion with the
    OData-defined cast operation.

    Special rules apply to the use of binary strings (bytes) to set
    string values.  A raw bytes object must be an ASCII-encodable
    string, otherwise ValueError is raised.  This applies to both
    Python 2 and Python 3!"""

    edm_name = 'String'

    def set(self, value=None):
        if value is None:
            self.value = None
        else:
            if isinstance(value, bytes):
                try:
                    new_value = value.decode('ascii')
                except UnicodeDecodeError:
                    raise ValueError(
                        "Can't set String from non-ascii bytes %s" %
                        str(value))
            elif is_unicode(value):
                new_value = value
            elif isinstance(value, PrimitiveValue):
                raise TypeError("Can't set String from %s" % repr(value))
            else:
                new_value = to_text(value)
            # check limits
            if self.type_def.unicode is False:
                try:
                    value.encode('ascii')
                except UnicodeEncodeError:
                    raise ValueError(
                        "Can't store non-ascii text in Edm.String type with "
                        "Unicode=False")
            if self.type_def.max_length and len(new_value) > \
                    self.type_def.max_length:
                raise ValueError("MaxLength exceeded for binary value")
            self.value = new_value

    @classmethod
    def from_str(cls, src):
        return cls(src)


class TimeOfDayValue(PrimitiveValue):

    """Represents a value of type Edm.TimeOfDay

    The value member of a TimeOfDayValue is either None or an instance
    of :class:`pyslet.iso8601.Time` with no zone specification.  OData
    excludes leap seconds.

    TimeOfDay literals use the extended ISO form with a '.' as decimal
    indicator if (optional) fractional seconds are used.

    TimeOfDay values can be set from an instance of
    :py:class:`iso8601.Time` though the value must be complete
    (have second precision) and have no timezone.  There is *no*
    automatic removal of timezone information to prevent accidentally
    introducing unintended mixed-zone comparison bugs.

    The standard python datetime.time can also be used provided
    utcoffset() returns None.

    Finally, positive numeric values are accepted and interpreted as
    seconds since midnight but must be in the range 0 up to (but not
    including) 86400.  See the :py:class:`~pyslet.iso8601.Time` for more
    information."""

    edm_name = 'TimeOfDay'

    def set(self, value):
        if isinstance(value, Time):
            # no zone allowed
            if not value.complete():
                raise ValueError(
                    "Can't set TimeOfDay from incomplete %s" % str(value))
            elif value.get_zone()[0] is not None:
                raise ValueError(
                    "Can't set TimeOfDay with timezone %s" % str(value))
            else:
                h, m, s = value.get_time()
                if h == 24:
                    # This is not allowed in OData
                    raise ValueError(
                        "Can't set TimeOfDay from %s" % str(value))
                if s >= 60:
                    # leap second!
                    if isinstance(s, float):
                        # max precision
                        s = _struncate(self.type_def.temporal_q,
                                       59.999999999999)
                    else:
                        s = 59
                elif isinstance(s, float):
                    s = _struncate(self.type_def.temporal_q, s)
                self.value = Time(hour=h, minute=m, second=s)
        elif isinstance(value, datetime.time):
            self.value = Time(
                hour=value.hour, minute=value.minute,
                second=_struncate(self.type_def.temporal_q, value.second))
        elif value is None:
            self.value = None
        else:
            raise TypeError("Can't set TimeOfDay from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_time_of_day_value()
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        h, m, s = self.value.get_time()
        if isinstance(s, float):
            return self.value.get_string(ndp=6, dp='.')
        else:
            return self.value.get_string(ndp=0)


class PointValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.PointLiteral):
            self.value = value
        elif isinstance(value, geo.Point):
            # a Point without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.PointLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_point_literal()
        p.require_end()
        return cls(v)


class LineStringValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.LineStringLiteral):
            self.value = value
        elif isinstance(value, geo.LineString):
            # a LineString without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.LineStringLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_line_string_literal()
        p.require_end()
        return cls(v)


class PolygonValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.PolygonLiteral):
            # validate this literal
            self.value = value
        elif isinstance(value, geo.Polygon):
            # a Polygon without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.PolygonLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_polygon_literal()
        p.require_end()
        return cls(v)


class MultiPointValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiPointLiteral):
            self.value = value
        elif isinstance(value, geo.MultiPoint):
            # a MultiPoint without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.MultiPointLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_multi_point_literal()
        p.require_end()
        return cls(v)


class MultiLineStringValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiLineStringLiteral):
            self.value = value
        elif isinstance(value, geo.MultiLineString):
            # a MultiLineString without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.MultiLineStringLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_multi_line_string_literal()
        p.require_end()
        return cls(v)


class MultiPolygonValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiPolygonLiteral):
            self.value = value
        elif isinstance(value, geo.MultiPolygon):
            # a MultiPolygon without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.MultiPolygonLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_multi_polygon_literal()
        p.require_end()
        return cls(v)


class GeoCollectionValue(object):

    def set(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.GeoCollectionLiteral):
            self.value = value
        elif isinstance(value, geo.GeoCollection):
            # a GeoCollection without a CRS acquires the default
            srid = self.type_def.srid
            if srid is None:
                srid = 4326 if isinstance(self, GeographyValue) else 0
            self.value = geo.GeoCollectionLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_collection_literal()
        p.require_end()
        return cls(v)


class GeographyValue(PrimitiveValue):
    pass


class GeographyPointValue(PointValue, GeographyValue):

    edm_name = 'GeographyPoint'


class GeographyLineStringValue(LineStringValue, GeographyValue):

    edm_name = 'GeographyLineString'


class GeographyPolygonValue(PolygonValue, GeographyValue):

    edm_name = 'GeographyPolygon'


class GeographyMultiPointValue(MultiPointValue, GeographyValue):

    edm_name = 'GeographyMultiPoint'


class GeographyMultiLineStringValue(MultiLineStringValue, GeographyValue):

    edm_name = 'GeographyMultiLineString'


class GeographyMultiPolygonValue(MultiPolygonValue, GeographyValue):

    edm_name = 'GeographyMultiPolygon'


class GeographyCollectionValue(GeoCollectionValue, GeographyValue):

    edm_name = 'GeographyCollection'


class GeometryValue(PrimitiveValue):
    pass


class GeometryPointValue(PointValue, GeometryValue):

    edm_name = 'GeometryPoint'


class GeometryLineStringValue(LineStringValue, GeometryValue):

    edm_name = 'GeometryLineString'


class GeometryPolygonValue(PolygonValue, GeometryValue):

    edm_name = 'GeometryPolygon'


class GeometryMultiPointValue(MultiPointValue, GeometryValue):

    edm_name = 'GeometryMultiPoint'


class GeometryMultiLineStringValue(MultiLineStringValue, GeometryValue):

    edm_name = 'GeometryMultiLineString'


class GeometryMultiPolygonValue(MultiPolygonValue, GeometryValue):

    edm_name = 'GeometryMultiPolygon'


class GeometryCollectionValue(GeoCollectionValue, GeometryValue):

    edm_name = 'GeometryCollection'


class EnumerationValue(UnicodeMixin, Value):

    """Represents the value of an Enumeration type"""

    def __init__(self, type_def, pvalue=None):
        Value.__init__(self, type_def)
        self.value = None
        if pvalue is not None:
            self.set(pvalue)

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        elif self.type_def.is_flags:
            return ul(',').join([v.name for
                                 v in self.type_def.lookup_flags(self.value)])
        else:
            return self.type_def.lookup(self.value).name

    def set(self, value):
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

            v.set(1)
            v.set(2)
            v.set((1, 2))

        however, you may *not*::

            v.set(3)

        This rule has implications for the use of 0 which, for a flags
        enumeration, means no flags are set.  You *must* define a member
        with value of 0 if you want to use this value.  E.g., extending
        the above example define Black=0 if you want to do this::

            v.set(0)"""
        if is_text(value) or isinstance(value, (int, long2)):
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


class CollectionValue(Value):

    """Represents the value of a Collection

    The type_def is required on construction.  There is no default
    collection type.

    It is important to understand the distinction between the object
    that represents a value in the OData model and the Python-like
    object that can be used to access a native representation of that
    value.

    In the case of primitive types the distinction is made using the
    :attr:`PrimitiveValue.value` attribute that contains a Python-native
    value representing the value (or None if the value is a null).  For
    collections we retain the same sort of distinction.  The
    CollectionValue object is not blessed with Python's Collection
    behaviour but must be *opened* in order to obtain such a
    representation.

    This distinction has important implications for the use of the null
    test.  A collection value is never null, so it always returns True
    in simple boolean logic tests even if the collection is empty. On
    the other hand, the object returned by :meth:`open` behaves like a
    python Collection object and will evaluate to False if it is
    empty."""

    def __init__(self, type_def):
        Value.__init__(self, type_def)

    def is_null(self):
        """CollectionValues are *never* null"""
        return False


class ComplexValue(Value, collections.Mapping):

    """Represents the value of a Complex type

    Instances behave like dictionaries of property values."""

    def __init__(self, type_def=None):
        if type_def is not None and not isinstance(type_def, ComplexType):
            raise ModelError("ComplexValue required ComplexType: %s" %
                             repr(type_def))
        Value.__init__(self, type_def=edm['ComplexType'] if type_def is None
                       else type_def)
        self._value_table = {}
        # create all the values
        for name, property in type_def.items():
            self._value_table[name] = property.type_def()

    def __getitem__(self, key):
        return self._value_table[key]

    def __iter__(self):
        return iter(self._value_table)

    def __len__(self):
        return len(self._value_table)


_oid_start_char = CharClass("_")
_oid_start_char.add_class(CharClass.ucd_category("L"))
_oid_start_char.add_class(CharClass.ucd_category("Nl"))

_oid_char = CharClass()
for c in ("L", "Nl", "Nd", "Mn", "Mc", "Pc", "Cf"):
    _oid_char.add_class(CharClass.ucd_category(c))


class ODataParser(BasicParser):

    """A Parser for the OData ABNF

    This class takes case of parsing primitive values only."""

    # Line 252
    def require_expand_path(self):
        """Parses production expandPath

        The syntax is a bit obscure from the definition due to
        the equivalence of many of the constructs but it
        reduces to::

            [ qualifiedName "/" ] odataIdentifier
                *( "/" [ qualifiedName "/" ] odataIdentifier )
                [ "/" qualifiedName ]

        We return a list of strings and/or :class:`QualifiedName`
        instances containing the path elements without separators. The
        is no ambiguity as the path can neither start nor end in a
        separator."""
        result = []
        qname = self.parse_production(self.require_qualified_name)
        if qname:
            result.append(qname)
            self.require("/")
            result.append(self.require_odata_identifier())
        else:
            result.append(self.require_odata_identifier())
        while self.parse("/"):
            qname = self.parse_production(self.require_qualified_name)
            if qname:
                result.append(qname)
                if self.parse("/"):
                    result.append(self.require_odata_identifier())
                else:
                    break
            else:
                result.append(self.require_odata_identifier())
        return result

    # Line 701-704
    def require_qualified_name(self):
        """Parses productions of the form qualified<type>Name

        Returns a named tuple of (namespace, name).

        Although split out in the ABNF these definitions are all
        equivalent and can't be differentiated in the syntax without
        reference to a specific model."""
        result = []
        result.append(self.require_odata_identifier())
        self.require(".")
        result.append(self.require_odata_identifier())
        while self.parse("."):
            result.append(self.require_odata_identifier())
        return QualifiedName(".".join(result[:-1]), result[-1])

    # Line 707
    def require_namespace(self):
        """Parses procution namespace

        Returns a string representing the namespace.  This method is
        greedy, it will parse as many identifiers as it can."""
        result = []
        result.append(self.require_odata_identifier())
        while self.parse("."):
            result.append(self.require_odata_identifier())
        return ".".join(result)

    # Line 720
    def require_odata_identifier(self):
        result = []
        if not _oid_start_char.test(self.the_char):
            self.parser_error("simple identifier")
        result.append(self.the_char)
        self.next_char()
        while _oid_char.test(self.the_char):
            result.append(self.the_char)
            self.next_char()
        if len(result) > 128:
            self.parser_error("simple identifier; 128 chars or fewer")
        return ''.join(result)

    # Line 856
    #: Matches production: nullValue
    null_value = 'null'

    # Line 859
    def require_binary(self):
        """Parses production: binary

        Returns a :class:`BinaryValue` instance or raises a parser
        error."""
        # binary = "binary" SQUOTE binaryValue SQUOTE
        self.require_production(self.parse_insensitive("binary"), "binary")
        self.require("'")
        v = self.require_binary_value()
        self.require("'")
        return v

    # Line 860
    def require_binary_value(self):
        """Parses production: binaryValue

        Returns a :class:`BinaryValue` instance or raises a parser
        error."""
        result = bytearray()
        while self.base64_char.test(self.the_char):
            result.append(byte(self.the_char))
            self.next_char()
        # in OData, the trailing "=" are optional but if given they must
        # result in the correct length string.
        pad = len(result) % 4
        if pad == 3:
            self.parse('=')
            result.append(byte('='))
        elif pad == 2:
            self.parse('==')
            result.append(byte('='))
            result.append(byte('='))
        return BinaryValue(base64.urlsafe_b64decode(bytes(result)))

    # Line 863
    #: a character class representing production base64char
    base64_char = CharClass(('A', 'Z'), ('a', 'z'), ('0', '9'), '-', '_')

    # Line 865
    def require_boolean_value(self):
        """Parses production: booleanValue

        Returns a :class:`BooleanValue` instance or raises a parser
        error."""
        v = BooleanValue()
        if self.parse_insensitive("true"):
            v.set(True)
        elif self.parse_insensitive("false"):
            v.set(False)
        else:
            self.parser_error("booleanValue")
        return v

    # Line 867
    def require_decimal_value(self):
        """Parses production: decimalValue

        Returns a :class:`DecimalValue` instance or raises a parser
        error."""
        v = DecimalValue()
        sign = self.parse_sign()
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            v.set(decimal.Decimal(sign + ldigits + '.' + rdigits))
        else:
            v.set(decimal.Decimal(sign + ldigits))
        return v

    # Line 869
    def require_double_value(self):
        """Parses production: doubleValue

        Returns a :class:`DoubleValue` instance or raises a parser
        error."""
        v = DoubleValue()
        sign = self.parse_one('+-')
        if not sign:
            if self.parse('INF'):
                v.set(float('inf'))
                return v
            elif self.parse('NaN'):
                v.set(float('nan'))
                return v
            sign = ''
        elif sign == '-' and self.parse('INF'):
            v.set(float('-inf'))
            return v
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            dec = sign + ldigits + '.' + rdigits
        else:
            dec = sign + ldigits
        if self.parse_insensitive('e'):
            sign = self.parse_one('+-')
            if not sign:
                sign = ''
            edigits = self.require_production(self.parse_digits(1), "exponent")
            exp = 'E' + sign + edigits
        else:
            exp = ''
        v.set(float(dec + exp))
        return v

    # Line 870
    def require_single_value(self):
        """Parses production: singleValue

        Returns a :class:`SingleValue` instance or raises a parser
        error."""
        v = SingleValue()
        v.set(self.require_double_value().value)
        return v

    # Line 873
    def require_guid_value(self):
        """Parses production: guidValue

        Returns a :class:`GuidValue` instance or raises a parser
        error."""
        hex_parts = []
        part = self.parse_hex_digits(8, 8)
        if not part:
            self.parser_error("8HEXDIG")
        hex_parts.append(part)
        for i in range3(3):
            self.require('-')
            part = self.parse_hex_digits(4, 4)
            if not part:
                self.parser_error("4HEXDIG")
            hex_parts.append(part)
        self.require('-')
        part = self.parse_hex_digits(12, 12)
        if not part:
            self.parser_error("12HEXDIG")
        hex_parts.append(part)
        result = GuidValue()
        result.set(uuid.UUID(hex=''.join(hex_parts)))
        return result

    # Line 875
    def require_byte_value(self):
        """Parses production: byteValue

        Returns a :class:`ByteValue` instance of raises a parser
        error."""
        #   1*3DIGIT
        digits = self.require_production(self.parse_digits(1, 3), "byteValue")
        v = ByteValue()
        try:
            v.set(int(digits))
        except ValueError:
            self.parser_error('byte in range [0, 255]')
        return v

    # Line 876
    def require_sbyte_value(self):
        """Parses production: sbyteValue

        Returns a :class:`SByteValue` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 3), "sbyteValue")
        v = SByteValue()
        try:
            v.set(int(sign + digits))
        except ValueError:
            self.parser_error('sbyte in range [-128, 127]')
        return v

    # Line 877
    def require_int16_value(self):
        """Parses production: int16Value

        Returns a :class:`Int16Value` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 5), "int16Value")
        v = Int16Value()
        try:
            v.set(int(sign + digits))
        except ValueError:
            self.parser_error('int16Value in range [-32768, 32767]')
        return v

    # Line 878
    def require_int32_value(self):
        """Parses production: int32Value

        Returns a :class:`Int32Value` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(
            self.parse_digits(1, 10), "int32Value")
        v = Int32Value()
        try:
            v.set(int(sign + digits))
        except ValueError:
            self.parser_error('int32Value in range [-2147483648, 2147483647]')
        return v

    # Line 879
    def require_int64_value(self):
        """Parses production: int64Value

        Returns a :class:`Int64Value` instance or raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 19),
                                         "int64Value")
        v = Int64Value()
        try:
            v.set(int(sign + digits))
        except ValueError:
            self.parser_error('int64Value in range [-9223372036854775808, '
                              '9223372036854775807]')
        return v

    # Line 881
    def require_string(self):
        """Parses production: string

        Returns a :class:`StringValue` instance or raises a parser
        error. Note that this is the literal quoted form of the string
        for use in URLs, string values in XML and JSON payloads are
        represented using native representations.  It is assumed that
        the input *has already* been decoded from the URL and is
        represented as a character string (it may also contain non-ASCII
        characters interpreted from the URL in an appropriate way)."""
        result = []
        self.require("'")
        while self.the_char is not None:
            if self.parse("'"):
                if self.parse("'"):
                    # an escaped single quote
                    result.append("'")
                else:
                    break
            else:
                result.append(self.the_char)
                self.next_char()
        return "".join(result)

    # Line 884
    def require_date_value(self):
        """Parses the production: dateValue

        Returns a :class:`DateValue` instance or raises a parser
        error."""
        year = self.require_year()
        self.require('-')
        month = self.require_month()
        self.require('-')
        day = self.require_day()
        bce, c, y = Date.split_year(year)
        result = DateValue()
        try:
            result.set(Date(bce=bce, century=c, year=y, month=month, day=day,
                            xdigits=-1))
            return result
        except DateTimeError:
            self.parser_error("valid dateValue")

    # Line 886
    def require_date_time_offset_value(self):
        """Parses production: dateTimeOffsetValue

        Returns a :class:`DateTimeOffsetValue` instance or raises a
        parser error."""
        year = self.require_year()
        self.require('-')
        month = self.require_month()
        self.require('-')
        day = self.require_day()
        bce, c, y = Date.split_year(year)
        self.require('T')
        hour = self.require_hour()
        self.require(':')
        minute = self.require_minute()
        if self.parse(':'):
            second = self.require_second()
            if self.parse('.'):
                fraction = self.require_production(self.parse_digits(1, 12))
                second = float(second) + float('0.' + fraction)
            else:
                second = int(second)
        else:
            second = 0
        if self.parse('Z'):
            zdirection = zhour = zminute = 0
        else:
            if self.parse('+'):
                zdirection = 1
            else:
                self.require('-')
                zdirection = -1
            zhour = self.require_hour()
            self.require(':')
            zminute = self.require_minute()
        result = DateTimeOffsetValue()
        try:
            result.set(
                TimePoint(
                    date=Date(bce=bce, century=c, year=y, month=month, day=day,
                              xdigits=-1),
                    time=Time(hour=hour, minute=minute, second=second,
                              zdirection=zdirection, zhour=zhour,
                              zminute=zminute)))
            return result
        except DateTimeError:
            self.parser_error("valid dateTimeOffsetValue")

    # Line 889
    def require_duration_value(self):
        """Parses production: durationValue

        Returns a :class:`DurationValue` instance or raises a parser
        error."""
        sign = self.parse_sign_int()
        self.require("P")
        digits = self.parse_digits(1)
        if digits:
            self.require("D")
            days = int(digits)
        else:
            days = 0
        hours = minutes = seconds = 0
        if self.parse("T"):
            # time fields
            digits = self.parse_digits(1)
            if digits and self.parse("H"):
                hours = int(digits)
                digits = None
            if not digits:
                digits = self.parse_digits(1)
            if digits and self.parse('M'):
                minutes = int(digits)
                digits = None
            if not digits:
                digits = self.parse_digits(1)
            if digits:
                if self.parse('.'):
                    rdigits = self.require_production(
                        self.parse_digits(1), "fractional seconds")
                    self.require("S")
                    seconds = float(digits + "." + rdigits)
                elif self.parse("S"):
                    seconds = int(digits)
        d = xsi.Duration()
        d.sign = sign
        d.days = days
        d.hours = hours
        d.minutes = minutes
        d.seconds = seconds
        return DurationValue(d)

    # Line 893
    def require_time_of_day_value(self):
        """Parses production: timeOfDayValue

        Returns a :class:`TimeOfDayValue` instance or raises a parser
        error."""
        hour = self.require_hour()
        self.require(':')
        minute = self.require_minute()
        if self.parse(':'):
            second = self.require_second()
            if self.parse('.'):
                fraction = self.require_production(self.parse_digits(1, 12))
                second = float(second) + float('0.' + fraction)
            else:
                second = int(second)
        else:
            second = 0
        result = TimeOfDayValue()
        try:
            result.set(Time(hour=hour, minute=minute, second=second))
            return result
        except DateTimeError:
            self.parser_error("valid timeOfDayValue")

    # Line 896
    def require_zero_to_fifty_nine(self, production):
        """Parses production: zeroToFiftyNine

        Returns an integer in the range 0..59 or raises a parser
        error."""
        digits = self.require_production(self.parse_digits(2, 2), production)
        i = int(digits)
        if i > 59:
            self.parser_error("%s in range [0..59]" % production)
        return i

    # Line 897
    def require_year(self):
        """Parses production: year

        Returns an integer representing the parsed year or raises a
        parser error."""
        if self.parse('-'):
            sign = -1
        else:
            sign = 1
        if self.parse('0'):
            digits = self.parse_digits(3, 3)
        else:
            digits = self.parse_digits(4)
        if not digits:
            self.parser_error("year")
        return sign * int(digits)

    # Line 898
    def require_month(self):
        """Parses production: month

        Returns an integer representing the month or raises a parser
        error."""
        if self.parse('0'):
            digits = self.parse_digit()
        elif self.parse('1'):
            digits = '1' + self.require_production(
                self.parse_one("012"), "month")
        else:
            digits = None
        if not digits:
            self.parser_error("month")
        return int(digits)

    # Line 900
    def require_day(self):
        """Parses production: day

        Returns an integer representing the day or raises a parser
        error."""
        if self.parse("0"):
            digits = self.parse_digit()
        else:
            d = self.parse_one("12")
            if d:
                digits = d + self.require_production(
                    self.parse_digit(), "day")
            elif self.parse("3"):
                digits = '3' + self.require_production(
                    self.parse_one("01"), "day")
            else:
                digits = None
        if not digits:
            self.parser_error("day")
        return int(digits)

    # Line 903
    def require_hour(self):
        """Parses production: hour

        Returns an integer representing the hour or raises a parser
        error."""
        digits = self.require_production(self.parse_digits(2, 2), "hour")
        hour = int(digits)
        if hour > 23:
            self.parser_error("hour in range [0..23]")
        return hour

    # Line 905
    def require_minute(self):
        """Parses production: minute

        Returns an integer representation of the minute or raises a
        parser error."""
        return self.require_zero_to_fifty_nine("minute")

    # Line 906
    def require_second(self):
        """Parses production: second

        Returns an integer representation of the second or raises a
        parser error."""
        return self.require_zero_to_fifty_nine("second")

    # Line 910
    def require_enum_value(self):
        """Parses production: enumValue

        Returns a non-empty *list* of strings and/or integers or raises
        a parser error."""
        result = []
        result.append(self.require_single_enum_value())
        while self.parse(","):
            # no need to use look ahead
            result.append(self.require_single_enum_value())
        return result

    # Line 911
    def require_single_enum_value(self):
        """Parses production: singleEnumValue

        Reuturns either a simple identifier string, an integer or raises
        a parser error."""
        name = self.parse_production(self.require_odata_identifier)
        if name:
            return name
        else:
            return self.require_int64_value()

    # Line 915
    def require_full_collection_literal(self):
        """Parses production: fullCollectionLiteral

        Returns a :class:`geotypes.GeoCollectionLiteral` instance, a
        named tuple consisting of 'srid' and 'items' members."""
        srid = self.require_srid_literal()
        items = self.require_collection_literal()
        return geo.GeoCollectionLiteral(srid, items)

    # Line 916
    def require_collection_literal(self):
        """Parses production: collectionLiteral

        Returns a :class:`geotypes.GeoCollection` instance."""
        self.require_production(
            self.parse_insensitive("collection("), "collectionLiteral")
        items = [self.require_geo_literal()]
        while self.parse(self.COMMA):
            items.append(self.require_geo_literal())
        self.require(self.CLOSE)
        return geo.GeoCollection(items)

    # Line 917
    def require_geo_literal(self):
        """Parses production: geoLiteral

        Returns a :class:`geotypes.GeoItem` instance."""
        item = self.parse_production(self.require_collection_literal)
        if not item:
            item = self.parse_production(self.require_line_string_literal)
        if not item:
            item = self.parse_production(self.require_multi_point_literal)
        if not item:
            item = self.parse_production(
                self.require_multi_line_string_literal)
        if not item:
            item = self.parse_production(
                self.require_multi_polygon_literal)
        if not item:
            item = self.parse_production(self.require_point_literal)
        if not item:
            item = self.parse_production(self.require_polygon_literal)
        if not item:
            self.parser_error("geoLiteral")
        return item

    # Line 926
    def require_full_line_string_literal(self):
        """Parses production: fullLineStringLiteral

        Returns a :class:`geotypes.LineStringLiteral` instance, a named
        tuple consisting of 'srid' and 'line_string' members."""
        srid = self.require_srid_literal()
        l = self.require_line_string_literal()
        return geo.LineStringLiteral(srid, l)

    # Line 927
    def require_line_string_literal(self):
        """Parses production: lineStringLiteral

        Returns a :class:`geotypes.LineString` instance."""
        self.require_production(
            self.parse_insensitive("linestring"), "lineStringLiteral")
        return self.require_line_string_data()

    # Line 928
    def require_line_string_data(self):
        """Parses production: lineStringData

        Returns a :class:`geotypes.LineString` instance."""
        self.require(self.OPEN)
        coords = []
        coords.append(self.require_position_literal())
        while self.parse(self.COMMA):
            coords.append(self.require_position_literal())
        self.require(self.CLOSE)
        return geo.LineString(coords)

    # Line 931
    def require_full_multi_line_string_literal(self):
        """Parses production: fullMultiLineStringLiteral

        Returns a :class:`geotypes.MultiLineStringLiteral` instance."""
        srid = self.require_srid_literal()
        ml = self.require_multi_line_string_literal()
        return geo.MultiLineStringLiteral(srid, ml)

    # Line 932
    def require_multi_line_string_literal(self):
        """Parses production: multiLineStringLiteral

        Returns a :class:`geotypes.MultiLineString` instance."""
        try:
            self.require_production(
                self.parse_insensitive("multilinestring("),
                "MultiLineStringLiteral")
            # may be empty
            line_strings = []
            l = self.parse_production(self.require_line_string_data)
            if l:
                line_strings.append(l)
                while self.parse(self.COMMA):
                    line_strings.append(self.require_line_string_data())
            self.require(self.CLOSE)
        except ParserError:
            self.parser_error()
        return geo.MultiLineString(line_strings)

    # Line 935
    def require_full_multi_point_literal(self):
        """Parses production: fullMultiPointLiteral

        Returns a :class:`geotypes.MultiPointLiteral` instance."""
        srid = self.require_srid_literal()
        mp = self.require_multi_point_literal()
        return geo.MultiPointLiteral(srid, mp)

    # Line 936
    def require_multi_point_literal(self):
        """Parses production: multiPointLiteral

        Returns a :class:`geotypes.MultiPoint` instance."""
        self.require_production(
            self.parse_insensitive("multipoint("), "MultiPointLiteral")
        # may be empty
        points = []
        p = self.parse_production(self.require_point_data)
        if p:
            points.append(p)
            while self.parse(self.COMMA):
                points.append(self.require_point_data())
        self.require(self.CLOSE)
        return geo.MultiPoint(points)

    # Line 939
    def require_full_multi_polygon_literal(self):
        """Parses production: fullMultiPolygonLiteral

        Returns a :class:`geotypes.MultiPolygonLiteral` instance."""
        srid = self.require_srid_literal()
        mp = self.require_multi_polygon_literal()
        return geo.MultiPolygonLiteral(srid, mp)

    # Line 940
    def require_multi_polygon_literal(self):
        """Parses production: multiPolygonLiteral

        Returns a :class:`geotypes.MultiPolygon` instance."""
        try:
            self.require_production(
                self.parse_insensitive("multipolygon("), "MultiPolygonLiteral")
            # may be empty
            polygons = []
            p = self.parse_production(self.require_polygon_data)
            if p:
                polygons.append(p)
                while self.parse(self.COMMA):
                    polygons.append(self.require_polygon_data())
            self.require(self.CLOSE)
        except ParserError:
            self.parser_error()
        return geo.MultiPolygon(polygons)

    # Line 943
    def require_full_point_literal(self):
        """Parses production: fullPointLiteral

        Returns a :class:`geotypes.PointLiteral` instance, a named tuple
        consisting of "srid" and "point" members."""
        srid = self.require_srid_literal()
        p = self.require_point_literal()
        return geo.PointLiteral(srid, p)

    # Line 944
    def require_srid_literal(self):
        """Parses production: sridLiteral

        Returns an integer reference for the SRID or raises a parser
        error."""
        self.require_production(
            self.parse_insensitive("srid"), "SRID")
        self.require(self.EQ)
        digits = self.require_production(self.parse_digits(1, 5))
        self.require(self.SEMI)
        return int(digits)

    # Line 945
    def require_point_literal(self):
        """Parses production: pointLiteral

        Reuturns a Point instance."""
        self.require_production(
            self.parse_insensitive("point"), "pointLiteral")
        return self.require_point_data()

    # Line 946
    def require_point_data(self):
        """Parses production: pointData

        Returns a :class:`geotypes.Point` instance."""
        self.require(self.OPEN)
        coords = self.require_position_literal()
        self.require(self.CLOSE)
        return geo.Point(*coords)

    # Line 947
    def require_position_literal(self):
        """Parses production: positionLiteral

        Returns a tuple of two float values or raises a parser error.
        Although the ABNF refers to "longitude then latitude" this
        production is used for all co-ordinate reference systems in both
        Geography and Geometry types so we make no such judgement
        ourselves and simply return an unamed tuple."""
        d1 = self.require_double_value()
        self.require(self.SP)
        d2 = self.require_double_value()
        return (d1.value, d2.value)

    # Line 950
    def require_full_polygon_literal(self):
        """Parses production: fullPolygonLiteral

        Returns a :class:`geotypes.PolygonLiteral` instance."""
        srid = self.require_srid_literal()
        p = self.require_polygon_literal()
        return geo.PolygonLiteral(srid, p)

    # Line 951
    def require_polygon_literal(self):
        """Parses production: polygonLiteral

        Returns a :class:`geotypes.Polygon` instance."""
        self.require_production(
            self.parse_insensitive("polygon"), "polygonLiteral")
        return self.require_polygon_data()

    # Line 952
    def require_polygon_data(self):
        """Parses production: polygonData

        Returns a :class:`geotypes.Polygon` instance."""
        self.require(self.OPEN)
        rings = []
        rings.append(self.require_ring_literal())
        while self.parse(self.COMMA):
            rings.append(self.require_ring_literal())
        self.require(self.CLOSE)
        return geo.Polygon(rings)

    # Line 953
    def require_ring_literal(self):
        """Parses production: ringLiteral

        Returns a :class:`geotypes.Ring` instance."""
        self.require(self.OPEN)
        coords = []
        coords.append(self.require_position_literal())
        while self.parse(self.COMMA):
            coords.append(self.require_position_literal())
        self.require(self.CLOSE)
        return geo.Ring(coords)

    # Line 1052
    def parse_sign(self):
        """Parses production: SIGN (aka sign)

        This production is typically optional so we either return "+",
        "-" or "" depending on the sign character parsed.  The ABNF
        allows for the percent encoded value "%2B" instead of "+" but we
        assume that percent-encoding has been removed before parsing.
        (That may not be true in XML documents but it seems
        unintentional to allow this form in that context.)"""
        sign = self.parse_one('+-')
        return sign if sign else ''

    # Line 1050
    COMMA = ul(",")

    # Line 1051
    EQ = ul("=")

    # Line 1052
    def parse_sign_int(self):
        """Parses production: SIGN (aka sign)

        Returns the integer 1 or -1 depending on the sign.  If no sign
        is parsed then 1 is returned."""
        sign = self.parse_one('+-')
        return -1 if sign == "-" else 1

    # Line 1053
    SEMI = ul(";")

    # Line 1057
    OPEN = ul("(")
    # Line 1058
    CLOSE = ul(")")

    # Line 1162
    SP = ul(" ")


edm = Schema.edm_init()


class DocumentSchemas(NameTable):

    """A name table of schema names (and aliases)"""

    def check_name(self):
        """Checks the name against edm:TNamespaceName

        From the spec:

            Non-normatively speaking it is a dot-separated sequence of
            SimpleIdentifiers with a maximum length of 511 Unicode
            characters."""
        raise NotImplementedError
