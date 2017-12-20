#! /usr/bin/env python

import base64
import datetime
import decimal
import logging
import math
import sys
import uuid

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

from . import (
    data,
    errors,
    geotypes as geo,
    names,
    parser,
    types,
    )


class PrimitiveValue(data.Value):

    """Class to represent a primitive value in OData.

    This class is not normally instantiated directly, use one of the
    *from\_* factory methods to construct a value of the correct
    sub-class from a string, literal or native python value.  Use one of
    the child classes directly to create a new value from an apporpriate
    python value using the default primitive type definition (i.e., with
    no additional constraining facets).  Otherwise, create instances by
    calling an instance of :class:`types.PrimitiveType`.

    If you do instantiate this class directly it will create a special
    type-less null value.

    When instances can be converted to strings they generate strings
    according to the primitiveValue ABNF defined in the specification.
    null values will raise a ValueError and cannot be serialised as
    strings."""

    #: Boolean indicating whether or not this value can be used in an
    #: entity key
    key_type = False

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.PrimitiveType` instance."""
        return types.PrimitiveType(value_type=cls)

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
        require qualification.

        One notable difference is that, unlike the default string
        conversion function, the null value *does* have a literal
        representation and will return 'null'."""
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
    def compatible(cls, other):
        """Returns True if primitive types are compatible

        By default, returns True only if other is the same class but
        overridden to implement class-specific rules such as
        compatibility of numeric types."""
        return cls is other

    @classmethod
    def edm_type(cls):
        type_def = cls.new_type()
        if cls is PrimitiveValue:
            type_def.set_abstract(True)
        else:
            type_def.set_base(edm_primitive_type)
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

    def assign(self, value):
        """Sets this value from another Value instance.."""
        if value.is_null():
            self.set_value(None)
        elif isinstance(value, NumericValue):
            # Numeric primitive types are cast to each other with
            # appropriate rounding. The cast fails if the integer part
            # doesn't fit into target type.
            self.set_value(value.get_value())
        else:
            raise TypeError(
                "Can't assign %s from %s" %
                (to_text(self.type_def), to_text(value.type_def)))

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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a NumericValue sub-class"""
        return issubclass(other, NumericValue)


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

    key_type = True

    @classmethod
    def new_type(cls):
        return types.IntegerType(value_type=cls)

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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.BinaryType` instance."""
        return types.BinaryType(value_type=cls)

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

    key_type = True

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

    def assign(self, value):
        """Sets this value from another Value instance.."""
        if value.is_null():
            self.set_value(None)
        elif isinstance(value, BooleanValue):
            self.set_value(value.get_value())
        else:
            raise TypeError(
                "Can't assign %s from %s" %
                (to_text(self.type_def), to_text(value.type_def)))

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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.DecimalType` instance."""
        return types.DecimalType(value_type=cls)

    key_type = True

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
            self.value = self.type_def.round(decimal.Decimal(value))
        elif isinstance(value, decimal.Decimal):
            self.value = self.type_def.round(value)
        elif isinstance(value, float):
            self.value = self.type_def.round(decimal.Decimal(repr(value)))
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
        type_def = cls.new_type()
        type_def.set_base(edm_primitive_type)
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

    key_type = True

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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.DateTimeOffsetType` instance."""
        return types.DateTimeOffsetType(value_type=cls)

    key_type = True

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
                        s = self.type_def.truncate(59.999999999999)
                    else:
                        s = 59
                elif isinstance(s, float):
                    s = self.type_def.truncate(s)
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
                    second=self.type_def.truncate(
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
                    self.type_def.truncate(value))
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
        type_def = cls.new_type()
        type_def.set_base(edm_primitive_type)
        type_def.set_precision(6, can_override=True)
        return type_def


class DurationValue(PrimitiveValue):

    """Represents a value of type Edm.Duration

    The value member of a DurationValue is either None or an instance of
    :class:`pyslet.xml.xsdatatypes.Duration`.

    Duration literals allow a reduced range of values as values expressed
    in terms of years, months or weeks are not allowed.

    Duration values can be set from an existing Duration only."""

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.DurationType` instance."""
        return types.DurationType(value_type=cls)

    key_type = True

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
                    self.value.seconds = self.type_def.truncate(
                        self.value.seconds)
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
        type_def = cls.new_type()
        type_def.set_base(edm_primitive_type)
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

    key_type = True

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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.StreamType` instance."""
        return types.StreamType(value_type=cls)

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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.StringType` instance."""
        return types.StringType(value_type=cls)

    key_type = True

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

    def assign(self, value):
        """Sets this value from another Value instance.."""
        if value.is_null():
            self.set_value(None)
        elif isinstance(value, StringValue):
            self.set_value(value.get_value())
        elif isinstance(value, PrimitiveValue):
            # Primitive types are cast to Edm.String or a type
            # definition based on it by using the literal representation
            # used in payloads
            self.set_value(to_text(value))
        else:
            raise TypeError(
                "Can't assign %s from %s" %
                (to_text(self.type_def), to_text(value.type_def)))

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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.PrimitiveType` instance."""
        return types.TimeOfDayType(value_type=cls)

    key_type = True

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
                        s = self.type_def.truncate(59.999999999999)
                    else:
                        s = 59
                elif isinstance(s, float):
                    s = self.type_def.truncate(s)
                self.value = Time(hour=h, minute=m, second=s)
        elif isinstance(value, datetime.time):
            self.value = Time(
                hour=value.hour, minute=value.minute,
                second=self.type_def.truncate(value.second))
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
        type_def = types.TimeOfDayType(value_type=cls)
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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a PointValue sub-class"""
        return issubclass(other, PointValue)


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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a LineStringValue sub-class"""
        return issubclass(other, LineStringValue)


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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a PolygonValue sub-class"""
        return issubclass(other, PolygonValue)


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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a MultiPointValue sub-class"""
        return issubclass(other, MultiPointValue)


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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a MultiLineStringValue sub-class"""
        return issubclass(other, MultiLineStringValue)


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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a MultiPolygonValue sub-class"""
        return issubclass(other, MultiPolygonValue)


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

    @classmethod
    def compatible(cls, other):
        """Returns True if other is also a GeoCollectionValue sub-class"""
        return issubclass(other, GeoCollectionValue)


class GeographyValue(PrimitiveValue):

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.GeographyType` instance."""
        return types.GeographyType(value_type=cls)

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of geography values are
        wrapped in the geography'' qualifier."""
        if self.value is None:
            return "null"
        else:
            return "geography'%s'" % to_text(self)

    @classmethod
    def edm_type(cls):
        type_def = cls.new_type()
        if cls is GeographyValue:
            type_def.set_base(edm_primitive_type)
            type_def.set_abstract(True)
        else:
            type_def.set_base(edm_geography)
        # type_def.set_srid(4326, can_override=True)
        return type_def


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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.GeometryType` instance."""
        return types.GeometryType(value_type=cls)

    def literal_string(self):
        """Returns the literal string representation of the value

        The literal string representation of geography values are
        wrapped in the geometry'' qualifier."""
        if self.value is None:
            return "null"
        else:
            return "geometry'%s'" % to_text(self)

    @classmethod
    def edm_type(cls):
        type_def = cls.new_type()
        if cls is GeometryValue:
            type_def.set_base(edm_primitive_type)
            type_def.set_abstract(True)
        else:
            type_def.set_base(edm_geometry)
        # type_def.set_srid(0, can_override=True)
        return type_def


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


class PathValue(PrimitiveValue):

    """Class to represent a path-type value in OData"""

    def assign(self, value):
        """Sets this value from another PathValue instance.

        The path type must match exactly."""
        if value.is_null():
            self.set_value(None)
        elif type(self) is type(value):
            self.set_value(value.get_value())
        else:
            raise TypeError(
                "Can't assign path %s from %s" %
                (to_text(self.type_def), to_text(value.type_def)))


class AnnotationPathValue(PathValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_annotation_path
        super(AnnotationPathValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        AnnotationPaths can be set from path tuples or from strings that
        can be converted to path tuples using
        :func:`names.annotation_path_from_str`. Path tuples are checked to
        ensure that they terminate in a term reference."""
        if self.frozen:
            raise errors.FrozenValueError
        if is_text(value):
            value = names.annotation_path_from_str(value)
        if value is None:
            self.value = None
        elif isinstance(value, tuple):
            happy_ending = False
            for seg in value:
                if isinstance(seg, names.QualifiedName):
                    happy_ending = False
                    continue
                elif isinstance(seg, names.TermRef):
                    happy_ending = True
                    continue
                elif is_text(seg):
                    if names.simple_identifier_from_str(seg):
                        happy_ending = False
                        continue
                    raise ValueError("%s is not a valid path segment" % seg)
                else:
                    raise TypeError(
                        "%s is not a valid path segment" % repr(seg))
            if not happy_ending:
                raise ValueError(
                    errors.Requirement.annotation_path_s % repr(value))
            self.value = value
        else:
            raise ValueError(
                "Can't set AnnotationPath with %s" % str(value))
        self.touch()


class NavigationPropertyPathValue(PathValue):

    def __init__(self, value=None, type_def=None, **kwargs):
        if type_def is None:
            type_def = edm_navigation_property_path
        super(NavigationPropertyPathValue, self).__init__(
            value=value, type_def=type_def, **kwargs)

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        NavigationPropertyPaths can be set from path tuples or from
        strings that can be converted to path tuples using
        :func:`names.path_from_str`."""
        if self.frozen:
            raise errors.FrozenValueError
        if is_text(value):
            value = names.path_from_str(value)
        if value is None:
            self.value = None
        elif isinstance(value, tuple):
            for seg in value:
                if isinstance(seg, (names.QualifiedName, names.TermRef)):
                    continue
                elif is_text(seg):
                    if names.simple_identifier_from_str(seg):
                        continue
                    raise ValueError("%s is not a valid path segment" % seg)
                else:
                    raise TypeError(
                        "%s is not a valid path segment" % repr(seg))
            self.value = value
        else:
            raise ValueError(
                "Can't set NavigationPropertyPath with %s" % str(value))
        self.touch()


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
# vocabulary only types are derived from StringValue
edm_annotation_path = AnnotationPathValue.edm_type()
edm_navigation_property_path = NavigationPropertyPathValue.edm_type()
edm_property_path = StringValue.edm_type()
