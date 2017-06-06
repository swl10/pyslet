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

from ..iso8601 import (
    Date,
    DateTimeError,
    Time,
    TimePoint)
from ..py2 import (
    BoolMixin,
    long2,
    is_text,
    is_unicode,
    py2,
    range3,
    to_text,
    UnicodeMixin
    )
from ..xml import xsdatatypes as xsi
from ..unicode5 import BasicParser


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


class Named(object):

    """An abstract class for a named object"""

    def __init__(self):
        #: the name of this object
        self.name = None
        #: a weak reference to the nametable in which this object is
        #: first declared (or None if the object has not been declared)
        self.nametable = None
        #: the qualified name of this object (if declared)
        self.qname = None

    def is_owned_by(self, nametable):
        """Checks the owning nametable

        A named object may appear in multiple nametables (e.g., a Schema
        may be defined in one entity model (the owner) but referenced in
        other entity models.  This method returns True if the nametable
        argument is the nametable in which the named object was declared
        (see :meth:`declare`)."""
        return self.nametable() is nametable

    def get_qualified_name(self):
        """Returns the qualified name of this object

        Includes any nametable prefix (does not use aliases)."""
        raise NotImplementedError

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
        if value is not None:
            callback(value)
        else:
            callback_list = self._callbacks.setdefault(name, [])
            callback_list.append(callback)

    def tell_close(self, callback):
        """Notification of closure

        Calls callback (with no arguments) when the name table is
        closed.  This call is made after all unsuccessful notifications
        registered with :meth:`tell` have been made."""
        self._close_callbacks.append(callback)

    def close(self):
        """closes this name table

        Any failed notification callbacks registered will :meth:`tell`
        are triggered followed by all notification callbacks registered
        with :meth:`tell_close`.  It is safe to call close on a name
        table that is already closed (callbacks are only ever called the
        first time)."""
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
            Any named type."""
        if not isinstance(value, (Term, NominalType)):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<Schema>" if self.name is None else self.name))

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
        entity_base = NominalType()
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

    def qualified_tell(self, qname, callback):
        """Deferred qualified name lookup.

        Similar to :meth:`Nametable.tell` except that it waits until
        both the Schema containing qname is defined *and* the target
        name is defined within that Schema.

        If the entity model or the indicated Schema is closed without
        qname being declared then the callback is called passing None."""
        parts = qname.split(".")
        if len(parts) < 2:
            raise ValueError("qualified_tell requires a qualified name")
        nsname = ".".join(parts[:-1])
        name = parts[-1]
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
        for pname, p in base.items():
            self[pname] = p
        self.base = base


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


class Property(Named):

    """A Property declaration"""

    def __init__(self, type_def):
        super(Property, self).__init__()
        #: the type definition for values of this property
        self.type_def = type_def
        # by default we're nullable
        self.nullable = True


class NavigationProperty(Named):

    """A NavigationProperty declaration"""
    pass


class ComplexType(StructuredType):

    """A ComplexType declaration"""

    def __init__(self):
        super(ComplexType, self).__init__()
        self.value_type = ComplexValue


class EntityType(StructuredType):

    """An EntityType declaration"""
    pass


class EnumerationType(NominalType):

    """An EnumerationType declaration"""
    pass


class Term(Named):

    """Represents a defined term in the OData model"""
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

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = PrimitiveParser(src)
        v = p.require_double_value()
        p.require_end()
        return v


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
        p = PrimitiveParser(src)
        v = p.require_boolean_value()
        p.require_end()
        return v


class ByteValue(IntegerValue):

    """Represents a value of type Edm.Byte"""

    MIN = 0
    MAX = 255

    _pytype = int

    edm_name = 'Byte'


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
        p = PrimitiveParser(src)
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

    type_name = "Edm.Double"


class Int16Value(IntegerValue):

    MIN = -32768
    MAX = 32767

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int16'


class Int32Value(IntegerValue):

    MIN = -2147483648
    MAX = 2147483647

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int32'


class Int64Value(IntegerValue):

    MAX = 9223372036854775807
    MIN = -9223372036854775808

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int64'


class SByteValue(IntegerValue):

    MIN = -128
    MAX = 127

    _pytype = int

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = PrimitiveParser(src)
        v = p.require_sbyte_value()
        p.require_end()
        return v

    edm_name = 'SByte'


class SingleValue(FloatValue):

    """Represents a value of type Edm.Single"""

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

    edm_name = 'Single'


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
        p = PrimitiveParser(src)
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
        p = PrimitiveParser(src)
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
        p = PrimitiveParser(src)
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
        p = PrimitiveParser(src)
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


class GeographyValue(PrimitiveValue):
    pass


class GeographyPointValue(GeographyValue):

    edm_name = 'GeographyPoint'


class GeographyLineStringValue(GeographyValue):

    edm_name = 'GeographyLineString'


class GeographyPolygonValue(GeographyValue):

    edm_name = 'GeographyPolygon'


class GeographyMultiPointValue(GeographyValue):

    edm_name = 'GeographyMultiPoint'


class GeographyMultiLineStringValue(GeographyValue):

    edm_name = 'GeographyMultiLineString'


class GeographyMultiPolygonValue(GeographyValue):

    edm_name = 'GeographyMultiPolygon'


class GeographyCollectionValue(GeographyValue):

    edm_name = 'GeographyCollection'


class GeometryValue(PrimitiveValue):
    pass


class GeometryPointValue(GeometryValue):

    edm_name = 'GeometryPoint'


class GeometryLineStringValue(GeometryValue):

    edm_name = 'GeometryLineString'


class GeometryPolygonValue(GeometryValue):

    edm_name = 'GeometryPolygon'


class GeometryMultiPointValue(GeometryValue):

    edm_name = 'GeometryMultiPoint'


class GeometryMultiLineStringValue(GeometryValue):

    edm_name = 'GeometryMultiLineString'


class GeometryMultiPolygonValue(GeometryValue):

    edm_name = 'GeometryMultiPolygon'


class GeometryCollectionValue(GeometryValue):

    edm_name = 'GeometryCollection'


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
    collections we retain the same sort of distinction in that the
    CollectionValue object is not blessed with Python's Collection
    behaviour.  Collection objects must be *opened* in order to obtain
    such a representation.

    This distinction has important implications for the use of the null
    test.  A collection value is never null, so it always returns True
    in simple boolean logic tests even if the collection is empty. On
    the other hand, the object returned by :meth:`open` behaves like a
    python Collection object and will evaluate to False if it empty."""

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


class PrimitiveParser(BasicParser):

    """A Parser for the OData ABNF

    This class takes case of parsing primitive values only."""

    def require_boolean_value(self):
        v = BooleanValue()
        if self.parse_insensitive("true"):
            v.set(True)
        elif self.parse_insensitive("false"):
            v.set(False)
        else:
            self.parser_error("booleanValue")
        return v

    def require_decimal_value(self):
        v = DecimalValue()
        sign = self.parse_one('+-')
        if not sign:
            sign = ''
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            v.set(decimal.Decimal(sign + ldigits + '.' + rdigits))
        else:
            v.set(decimal.Decimal(sign + ldigits))
        return v

    def require_double_value(self):
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

    def require_sbyte_value(self):
        v = SByteValue()
        sign = self.parse_one('+-')
        if not sign:
            sign = ''
        digits = self.require_production(self.parse_digits(1, 3), "digits")
        try:
            v.set(int(sign + digits))
        except ValueError:
            self.parser_error('sbyte in range [-128, 127]')
        return v

    def require_guid_value(self):
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

    def require_date_value(self):
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

    def require_date_time_offset_value(self):
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

    def require_time_of_day_value(self):
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

    def require_year(self):
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

    def require_month(self):
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

    def require_day(self):
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

    def require_hour(self):
        digits = self.require_production(self.parse_digits(2, 2), "hour")
        hour = int(digits)
        if hour > 23:
            self.parser_error("hour in range [0..23]")
        return hour

    def require_minute(self):
        return self.require_zero_to_fifty_nine("minute")

    def require_second(self):
        return self.require_zero_to_fifty_nine("second")

    def require_zero_to_fifty_nine(self, production):
        digits = self.require_production(self.parse_digits(2, 2), production)
        i = int(digits)
        if i > 59:
            self.parser_error("%s in range [0..59]" % production)
        return i


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
