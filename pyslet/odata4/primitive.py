#! /usr/bin/env python

import base64
import datetime
import decimal
import logging
import math
import sys
import uuid

from . import errors
from . import geotypes as geo
from . import parser
from . import types

from ..iso8601 import (
    Date,
    DateTimeError,
    Time,
    TimePoint)
from ..py2 import (
    is_text,
    is_unicode,
    long2,
    py2,
    to_text,
    )
from ..xml import xsdatatypes as xsi


class PrimitiveType(types.Annotatable, types.NominalType):

    """A Primitive Type declaration

    Instances represent primitive type delcarations, such as those made
    by a TypeDefinition.  The built-in Edm Schema contains instances
    representing the base primitie types themselves and properties use
    this class to create undeclared types to constrain their values.

    The base type, and facet values are frozen when the type is first
    declared and the methods that modify them will raise errors if
    called after that."""

    # used for Decimal rounding, overridden by instance variables for
    # actual Decimal types.
    dec_nleft = decimal.getcontext().Emax + 1
    dec_nright = 0
    dec_digits = (1, ) * decimal.getcontext().prec

    # default used for temporal rounding (no fractional seconds)
    temporal_q = decimal.Decimal((0, (1, ), 0))

    def __init__(self, **kwargs):
        super(PrimitiveType, self).__init__(**kwargs)
        self.value_type = PrimitiveValue
        #: the specified MaxLength facet or None if unspecified
        self.max_length = None
        self._max_length = 0
        #: the specified Unicode facet or None if unspecified
        self.unicode = None
        self._unicode = True
        #: the specified Precision facet or None if unspecified
        self.precision = None
        #: the specified Scale facet or None if unspecified
        self.scale = None
        #: the specified SRID facet or None if unspecified.  The value
        #: -1 means variable
        self.srid = None
        self._srid = 0

    def set_base(self, base):
        """Sets the base type of this type

        The base must also be a PrimitiveType."""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not isinstance(base, PrimitiveType):
            raise TypeError(
                "%s is not a suitable base for a PrimitiveType" % base.qname)
        # TODO: if not base.name:
        #    raise errors.ObjectNotDeclaredError("Base type must be declared")
        # update the value_type, impose a further restriction that the
        # new value_type (copied from base) MUST be a subclass of the
        # previous value_type.  In other words, you can't have a type
        # based on Edm.String and use set_base to 'rebase' it to
        # Edm.Int64
        if not issubclass(base.value_type, self.value_type):
            raise TypeError(
                "Mismatched value types: can't base %s on %s" %
                (self.name, base.qname))
        self.value_type = base.value_type
        if issubclass(self.value_type, GeographyValue) and self.srid is None:
            # unspecified SRID, default for Geography is 4326
            self.set_srid(4326, can_override=True)
        elif issubclass(self.value_type,
                        (DateTimeOffsetValue, DurationValue,
                         TimeOfDayValue)):
            # weak value
            self.set_precision(0, can_override=True)
        # now copy over strongly specified facets
        if base.max_length is not None:
            self.set_max_length(base.max_length)
        if base.unicode is not None:
            self.set_unicode(base.unicode)
        if base.precision is not None or base.scale is not None:
            self.set_precision(base.precision, base.scale)
        if base.srid is not None:
            self.set_srid(base.srid)
        super(PrimitiveType, self).set_base(base)

    def set_max_length(self, max_length, can_override=False):
        """Sets the MaxLength facet of this type.

        max_length
            A positive integer or 0 indicating 'max'

        can_override
            Used to control whether or not sub-types can override the
            value.  Defaults to False.  The value True is used to set
            limits on the primitives of the builtin Edm namespace which
            can be overridden by sub-types and/or property
            definitions.

        Can only be set for primitive types with underlying type Binary,
        Stream or String."""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not issubclass(
                self.value_type,
                (BinaryValue, StreamValue, StringValue)):
            logging.warning("MaxLength cannot be specified for %s",
                            self.value_type.__name__)
            return
        if max_length < 0:
            raise ValueError(
                "MaxLength facet must be a positive integer or 'max': %s" %
                repr(max_length))
        if can_override:
            # sets a weak value, ignored if already specified
            if self.max_length is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.max_length is not None:
                raise errors.ModelError(
                    errors.Requirement.td_facet_s % "MaxLength")
            self.max_length = max_length
        self._max_length = max_length

    def set_unicode(self, unicode_facet, can_override=False):
        """Sets the Unicode facet of this type

        unicode_facet
            A boolean

        can_override
            See :meth:`set_max_length` for details

        Can only be set on primitive types with underlying type
        String."""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not issubclass(self.value_type, StringValue):
            logging.warning("Unicode facet cannot be specified for %s",
                            self.value_type.__name__)
            return
        if can_override:
            # sets a weak value, ignored if already specified
            if self.unicode is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.unicode is not None:
                raise errors.ModelError(
                    errors.Requirement.td_facet_s % "Unicode")
            self.unicode = unicode_facet
        self._unicode = unicode_facet

    def set_precision(self, precision, scale=None, can_override=False):
        """Sets the Precision and (optionally) Scale facets

        precision
            A non-negative integer

        scale
            An non-negative integer or -1 indicating variable scale

        can_override
            See :meth:`set_max_length` for details

        Precision and Scale can only be set on primitive types with
        underlying type Decimal.  Precision on its own can be set on
        types with underlying temporal type.

        There is no explicit constraint in the specification that says
        you cannot set Scale without Precision for Decimal types.
        Therefore we allow prevision=None and use our default internal
        limit (typically 28 in the Python decimal module) instead.

        """
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if issubclass(self.value_type, DecimalValue):
            if precision is not None:
                if precision <= 0:
                    raise errors.ModelError(
                        errors.Requirement.decimal_precision)
                if scale is not None and scale > precision:
                    raise errors.ModelError(
                        errors.Requirement.scale_gt_precision)
        elif issubclass(self.value_type,
                        (DateTimeOffsetValue, DurationValue,
                         TimeOfDayValue)):
            if precision is not None and (precision < 0 or precision > 12):
                raise errors.ModelError(
                    errors.Requirement.temporal_precision)
        if can_override:
            # weak values are overridden by existing strong values
            if self.precision is not None:
                precision = self.precision
            if self.scale is not None:
                scale = self.scale
        else:
            # strong values
            if precision is None:
                precision = self.precision
            else:
                if self.precision is not None:
                    raise errors.ModelError(
                        errors.Requirement.td_facet_s % "Precision")
                self.precision = precision
            if scale is None:
                scale = self.scale
            else:
                if self.scale is not None:
                    raise errors.ModelError(
                        errors.Requirement.td_facet_s % "Scale")
                self.scale = scale
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
                if scale is None:
                    # just precision specified, scale is implied 0
                    self.dec_nleft = precision
                    self.dec_nright = 0
                elif scale < 0:
                    # variable scale, up to precision on the right
                    self.dec_nleft = PrimitiveType.dec_nleft
                    self.dec_nright = precision
                else:
                    self.dec_nleft = precision - scale
                    self.dec_nright = scale
                self.dec_digits = (1, ) * min(decimal.getcontext().prec,
                                              precision)
        elif issubclass(self.value_type,
                        (DateTimeOffsetValue, DurationValue,
                         TimeOfDayValue)):
            # precision must be non-negative (max 12)
            if precision is None:
                # no precision = 0
                self.temporal_q = decimal.Decimal((0, (1, ), 0))
            else:
                # overload the class attribute
                self.temporal_q = decimal.Decimal(
                    (0, (1, ) * (precision + 1), -precision))
        elif scale is not None:
            logging.warning("Precision/Scale cannot be specified for %s",
                            self.value_type.__name__)
        else:
            logging.warning("Precision cannot be specified for %s",
                            self.value_type.__name__)

    def set_srid(self, srid, can_override=False):
        """Sets the SRID facet of this property

        srid
            A non-negative integer or -1 for variable

        can_override
            See :meth:`set_max_length` for details"""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not issubclass(self.value_type,
                          (GeographyValue, GeometryValue)):
            logging.warning("SRID cannot be specified for %s",
                            self.value_type.__name__)
            return
        if srid < -1:
            raise errors.ModelError(errors.Requirement.srid_value)
        if can_override:
            # sets a weak value, ignored if already specified
            if self.srid is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.srid is not None:
                raise errors.ModelError(errors.Requirement.td_facet_s % "SRID")
            self.srid = srid
        self._srid = srid

    def match(self, other):
        """Returns True if this primitive type matches other

        Other must also be a PrimtiveType.  PrimitiveTypes match if they
        use the same underlying value type and any constrained facets
        are constrained in the same way.  If a facet is specified by
        only one of the types they are considered matching."""
        if not isinstance(other, PrimitiveType):
            return False
        if self.value_type is not other.value_type:
            return False
        if issubclass(self.value_type, StringValue):
            if self.unicode is None or other.unicode is None:
                # if either values are unspecified consider it a match
                return True
            if self.max_length is None or other.max_length is None:
                return True
            return (self.unicode == other.unicode and
                    self.max_length == other.max_length)
        elif issubclass(self.value_type, DecimalValue):
            return (self.dec_nleft == other.dec_nleft and
                    self.dec_nright == other.dec_nright and
                    self.dec_digits == other.dec_digits)
        elif issubclass(self.value_type,
                        (DateTimeOffsetValue, DurationValue,
                         TimeOfDayValue)):
            return self.temporal_q == other.temporal_q
        elif issubclass(self.value_type,
                        (GeographyValue, GeometryValue)):
            return self.srid == other.srid
        else:
            return True


class PrimitiveValue(types.Value):

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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_primitive_type
        super(PrimitiveValue, self).__init__(type_def=type_def, **kwargs)
        self.value = None
        if value is not None:
            self.set_value(value)

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

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string differs from the basic text representation
        for some primitive value types where there would be an ambiguity
        in representation.  The default implementation assumes they are
        the same so this implementation is overridden in the types that
        require qualification."""
        if self.is_null():
            return "null"
        else:
            return to_text(self)

    def get_value(self):
        """Returns a python 'native' value representation"""
        return self.value

    def set_value(self, value):
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
        if self.frozen:
            raise errors.FrozenValueError
        elif value is None:
            self.value = None
        else:
            raise TypeError("Can't set %s from %s" %
                            (str(self.type_def), repr(value)))
        self.touch()

    def touch(self):
        """Implements touch behaviour

        If this primitive value is the value of a commplex or entity
        property then touch the parent too."""
        super(PrimitiveValue, self).touch()
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
            result.set_value(value)
        elif isinstance(value, (Date, datetime.date)):
            result = DateValue()
            result.set_value(value)
        elif isinstance(value, (Time, datetime.time)):
            result = TimeOfDayValue()
            result.set_value(value)
        elif isinstance(value, xsi.Duration):
            result = DurationValue()
            result.set_value(value)
        elif isinstance(value, uuid.UUID):
            result = GuidValue()
            result.set_value(value)
        elif isinstance(value, geo.PointLiteral):
            if value.srid:
                result = GeographyPointValue()
            else:
                result = GeometryPointValue()
            result.set_value(value)
        elif isinstance(value, geo.LineStringLiteral):
            if value.srid:
                result = GeographyLineStringValue()
            else:
                result = GeometryLineStringValue()
            result.set_value(value)
        elif isinstance(value, geo.PolygonLiteral):
            if value.srid:
                result = GeographyPolygonValue()
            else:
                result = GeometryPolygonValue()
            result.set_value(value)
        elif isinstance(value, geo.MultiPointLiteral):
            if value.srid:
                result = GeographyMultiPointValue()
            else:
                result = GeometryMultiPointValue()
            result.set_value(value)
        elif isinstance(value, geo.MultiLineStringLiteral):
            if value.srid:
                result = GeographyMultiLineStringValue()
            else:
                result = GeometryMultiLineStringValue()
            result.set_value(value)
        elif isinstance(value, geo.MultiPolygonLiteral):
            if value.srid:
                result = GeographyMultiPolygonValue()
            else:
                result = GeometryMultiPolygonValue()
            result.set_value(value)
        elif isinstance(value, geo.GeoCollectionLiteral):
            if value.srid:
                result = GeographyCollectionValue()
            else:
                result = GeometryCollectionValue()
            result.set_value(value)
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
        if isinstance(result, StringValue):
            try:
                result.set_value(to_text(self))
            except ValueError:
                # bounds must be exceeded, return typed null
                pass
            return result
        else:
            return super(PrimitiveValue, self).cast(type_def)

    @classmethod
    def edm_type(cls):
        type_def = PrimitiveType()
        if cls is PrimitiveValue:
            type_def.set_abstract(True)
        else:
            type_def.set_base(edm_primitive_type)
            type_def.value_type = cls
        return type_def


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
                result.set_value(self.value)
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
            return super(NumericValue, self).cast(type_def)


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

    def set_value(self, value):
        if isinstance(value, self._num_types):
            v = self._pytype(value)
            if v < self.MIN or v > self.MAX:
                raise ValueError(
                    "%s out of range for %s" %
                    (repr(value), to_text(self.type_def)))
            else:
                self.value = v
        elif value is None:
            self.value = None
        else:
            raise TypeError(
                "can't set %s from %s" %
                (to_text(self.type_def), repr(value)))
        self.touch()


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

    def set_value(self, value):
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
                "can't set %s from %s" % (repr(self), repr(value)))
        self.touch()


class BinaryValue(PrimitiveValue):

    """Represents a value of type Edm.Binary

    The value member of a BinaryValue is either None or of type bytes.

    Binary literals are base64url encoded binary-strings as per
    http://tools.ietf.org/html/rfc4648#section-5

    Binary values can also be set from most Python types, character
    strings are UTF-8 encoded, any other types are converted using the
    builtin bytes function.  For consistency, BinaryValues can *not* be
    set from instances of PrimitiveValue."""

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_binary
        super(BinaryValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value=None):
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
            if self.type_def._max_length and len(new_value) > \
                    self.type_def._max_length:
                raise ValueError("MaxLength exceeded for binary value")
            self.value = new_value
        self.touch()

    @classmethod
    def from_str(cls, src):
        p = parser.Parser(src)
        v = cls(p.require_binary_value())
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(base64.urlsafe_b64encode(self.value))

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of a binary value is wrapped
        in the binary'' qualifier."""
        if self.value is None:
            return "null"
        else:
            return "binary'%s'" % to_text(self)


class BooleanValue(PrimitiveValue):

    """Represents a value of type Edm.Boolean

    The value member of a BooleanValue is either None, True or False.

    Boolean literals are one of the strings "true" or "false"

    Boolean values can be set from any other input type (except
    PrimitiveValue instances), the resulting value is the logical
    evaluation of the input value.  E.g., empty strings and lists are
    False, non-zero integer values True, etc."""

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_boolean
        super(BooleanValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value=None):
        if value is None or value is True or value is False:
            self.value = value
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            self.value = True if value else False
        self.touch()

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return "true" if self.value else "false"

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax is case insenstive for the values "true" and
        "false" but case sensitive for the value 'null'."""
        p = parser.Parser(src)
        v = cls(p.require_boolean_value())
        p.require_end()
        return v


class ByteValue(IntegerValue):

    """Represents a value of type Edm.Byte"""

    MIN = 0
    MAX = 255

    _pytype = int

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_byte
        super(ByteValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_byte_value())
        p.require_end()
        return v


class DecimalValue(NumericValue):

    """Represents a value of type Edm.Decimal

    Can be set from numeric values of the
    following types: int (bool, see :class:`IntegerValue` for details),
    long (Python 2), float and Decimal."""

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_decimal
        super(DecimalValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

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

    def set_value(self, value):
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
        self.touch()

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
        p = parser.Parser(src)
        v = cls(p.require_decimal_value())
        p.require_end()
        return v

    @classmethod
    def edm_type(cls):
        type_def = PrimitiveType()
        type_def.set_base(edm_primitive_type)
        type_def.value_type = cls
        type_def.set_precision(None, -1, can_override=True)
        return type_def


class DoubleValue(FloatValue):

    """Represents a value of type Edm.Double"""

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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_double
        super(DoubleValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_double_value())
        p.require_end()
        return v


class Int16Value(IntegerValue):

    MIN = -32768
    MAX = 32767

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_int16
        super(Int16Value, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_int16_value())
        p.require_end()
        return v


class Int32Value(IntegerValue):

    MIN = -2147483648
    MAX = 2147483647

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_int32
        super(Int32Value, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_int32_value())
        p.require_end()
        return v


class Int64Value(IntegerValue):

    MAX = 9223372036854775807
    MIN = -9223372036854775808

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_int64
        super(Int64Value, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_int64_value())
        p.require_end()
        return v


class SByteValue(IntegerValue):

    MIN = -128
    MAX = 127

    _pytype = int

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_sbyte
        super(SByteValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_sbyte_value())
        p.require_end()
        return v


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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_single
        super(SingleValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_single_value())
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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_date
        super(DateValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value):
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
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_date_value())
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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_date_time_offset
        super(DateTimeOffsetValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value):
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
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_date_time_offset_value())
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

    @classmethod
    def edm_type(cls):
        type_def = PrimitiveType()
        type_def.set_base(edm_primitive_type)
        type_def.value_type = cls
        type_def.set_precision(6, can_override=True)
        return type_def


class DurationValue(PrimitiveValue):

    """Represents a value of type Edm.Duration

    The value member of a DurationValue is either None or an instance of
    :class:`pyslet.xml.xsdatatypes.Duration`.

    Duration literals allow a reduced range of values as values expressed
    in terms of years, months or weeks are not allowed.

    Duration values can be set from an existing Duration only."""

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_duration
        super(DurationValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value):
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
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax follows XML schema convention of an optional sign
        followed by an ISO-type duration specified in days, hours,
        minutes and seconds."""
        p = parser.Parser(src)
        v = cls(p.require_duration_value())
        p.require_end()
        return v

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of a duration value is wrapped
        in the duration'' qualifier."""
        if self.value is None:
            return "null"
        else:
            return "duration'%s'" % to_text(self)

    @classmethod
    def edm_type(cls):
        type_def = PrimitiveType()
        type_def.set_base(edm_primitive_type)
        type_def.value_type = cls
        type_def.set_precision(6, can_override=True)
        return type_def


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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_guid
        super(GuidValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value=None):
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
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_guid_value())
        p.require_end()
        return v


class StreamValue(PrimitiveValue):

    """Represents a value of type Edm.Stream

    The value member of a StreamValue is either None or a StreamInfo
    instance (TODO) containing the stream's metadata.

        The values for stream properties do not appear in the entity
        payload. Instead, the values are read or written through URLs.
    """
    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_stream
        super(StreamValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_string
        super(StringValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value=None):
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
            if not self.type_def._unicode:
                try:
                    value.encode('ascii')
                except UnicodeEncodeError:
                    raise ValueError(
                        "Can't store non-ascii text in Edm.String type "
                        "that " "does not accept Unicode characters")
            if self.type_def._max_length and len(new_value) > \
                    self.type_def._max_length:
                raise ValueError("MaxLength exceeded for string value")
            self.value = new_value
        self.touch()

    @classmethod
    def from_str(cls, src):
        return cls(src)

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of a string value is wrapped
        in '' with any quotes in the string being doubled."""
        if self.value is None:
            return "null"
        else:
            return "'%s'" % to_text(self).replace("'", "''")


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

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_time_of_day
        super(TimeOfDayValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value):
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
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_time_of_day_value())
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

    @classmethod
    def edm_type(cls):
        type_def = PrimitiveType()
        type_def.set_base(edm_primitive_type)
        type_def.value_type = cls
        type_def.set_precision(6, can_override=True)
        return type_def


class PointValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.PointLiteral):
            self.value = value
        elif isinstance(value, geo.Point):
            # a Point without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.PointLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_point_literal())
        p.require_end()
        return v


class LineStringValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.LineStringLiteral):
            self.value = value
        elif isinstance(value, geo.LineString):
            # a LineString without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.LineStringLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_line_string_literal())
        p.require_end()
        return v


class PolygonValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.PolygonLiteral):
            # validate this literal
            self.value = value
        elif isinstance(value, geo.Polygon):
            # a Polygon without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.PolygonLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_polygon_literal())
        p.require_end()
        return v


class MultiPointValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiPointLiteral):
            self.value = value
        elif isinstance(value, geo.MultiPoint):
            # a MultiPoint without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.MultiPointLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_multi_point_literal())
        p.require_end()
        return v


class MultiLineStringValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiLineStringLiteral):
            self.value = value
        elif isinstance(value, geo.MultiLineString):
            # a MultiLineString without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.MultiLineStringLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_multi_line_string_literal())
        p.require_end()
        return v


class MultiPolygonValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiPolygonLiteral):
            self.value = value
        elif isinstance(value, geo.MultiPolygon):
            # a MultiPolygon without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.MultiPolygonLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_multi_polygon_literal())
        p.require_end()
        return v


class GeoCollectionValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.GeoCollectionLiteral):
            self.value = value
        elif isinstance(value, geo.GeoCollection):
            # a GeoCollection without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.GeoCollectionLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))
        self.touch()

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = parser.Parser(src)
        v = cls(p.require_full_collection_literal())
        p.require_end()
        return v


class GeographyValue(PrimitiveValue):

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of geography values are
        wrapped in the geography'' qualifier."""
        if self.value is None:
            return "null"
        else:
            return "geography'%s'" % to_text(self)


class GeographyPointValue(PointValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_point
        super(GeographyPointValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeographyLineStringValue(LineStringValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_line_string
        super(GeographyLineStringValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeographyPolygonValue(PolygonValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_polygon
        super(GeographyPolygonValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeographyMultiPointValue(MultiPointValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_multi_point
        super(GeographyMultiPointValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeographyMultiLineStringValue(MultiLineStringValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_multi_line_string
        super(GeographyMultiLineStringValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeographyMultiPolygonValue(MultiPolygonValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_multi_polygon
        super(GeographyMultiPolygonValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeographyCollectionValue(GeoCollectionValue, GeographyValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geography_collection
        super(GeographyCollectionValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryValue(PrimitiveValue):

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of geography values are
        wrapped in the geometry'' qualifier."""
        if self.value is None:
            return "null"
        else:
            return "geometry'%s'" % to_text(self)


class GeometryPointValue(PointValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_point
        super(GeometryPointValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryLineStringValue(LineStringValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_line_string
        super(GeometryLineStringValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryPolygonValue(PolygonValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_polygon
        super(GeometryPolygonValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryMultiPointValue(MultiPointValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_multi_point
        super(GeometryMultiPointValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryMultiLineStringValue(MultiLineStringValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_multi_line_string
        super(GeometryMultiLineStringValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryMultiPolygonValue(MultiPolygonValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_multi_polygon
        super(GeometryMultiPolygonValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


class GeometryCollectionValue(GeoCollectionValue, GeometryValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_geometry_collection
        super(GeometryCollectionValue, self).__init__(
            value=value, type_def=type_def, **kwargs)


edm_primitive_type = PrimitiveValue.edm_type()
edm_binary = BinaryValue.edm_type()
edm_boolean = BooleanValue.edm_type()
edm_byte = ByteValue.edm_type()
edm_date = DateValue.edm_type()
edm_date_time_offset = DateTimeOffsetValue.edm_type()
edm_decimal = DecimalValue.edm_type()
edm_double = DoubleValue.edm_type()
edm_duration = DurationValue.edm_type()
edm_guid = GuidValue.edm_type()
edm_int16 = Int16Value.edm_type()
edm_int32 = Int32Value.edm_type()
edm_int64 = Int64Value.edm_type()
edm_single = SingleValue.edm_type()
edm_sbyte = SByteValue.edm_type()
edm_stream = StreamValue.edm_type()
edm_string = StringValue.edm_type()
edm_time_of_day = TimeOfDayValue.edm_type()
edm_geography = GeographyValue.edm_type()
edm_geography_point = GeographyPointValue.edm_type()
edm_geography_line_string = GeographyLineStringValue.edm_type()
edm_geography_polygon = GeographyPolygonValue.edm_type()
edm_geography_multi_point = GeographyMultiPointValue.edm_type()
edm_geography_multi_line_string = GeographyMultiLineStringValue.edm_type()
edm_geography_multi_polygon = GeographyMultiPolygonValue.edm_type()
edm_geography_collection = GeographyCollectionValue.edm_type()
edm_geometry = GeometryValue.edm_type()
edm_geometry_point = GeometryPointValue.edm_type()
edm_geometry_line_string = GeometryLineStringValue.edm_type()
edm_geometry_polygon = GeometryPolygonValue.edm_type()
edm_geometry_multi_point = GeometryMultiPointValue.edm_type()
edm_geometry_multi_line_string = GeometryMultiLineStringValue.edm_type()
edm_geometry_multi_polygon = GeometryMultiPolygonValue.edm_type()
edm_geometry_collection = GeometryCollectionValue.edm_type()
