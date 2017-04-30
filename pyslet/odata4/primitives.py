#! /usr/bin/env python

import base64
import copy
import datetime
import logging
import sys

from decimal import Decimal

from ..iso8601 import (
    Date,
    Time,
    TimePoint)
from ..py2 import (
    BoolMixin,
    long2,
    is_unicode,
    py2,
    to_text,
    UnicodeMixin
    )


class Value(BoolMixin):

    """Abstract class to represent a value in OData.

    All values processed by OData classes are reprsented by instances of
    this class.

    Values are mutable so cannot be used as dictionary keys (they are
    not hashable).  They evaluate to True unless they are null, in which
    case they evaluate to False."""

    __hash__ = None

    def __bool__(self):
        return not self.is_null()

    def is_null(self):
        """Returns True if this object is null.

        You can use simple Python boolean evaluation with instances, the
        purpose of this method is to allow derived classes to implement
        an appropriate null test."""
        return True


class PrimitiveValue(UnicodeMixin, Value):

    """Class to represent a primitive value in OData.

    This class is not designed to be instantiated directly, use one of
    the factory methods to construct a value of the type-specific child
    classes when you don't know what type of value you need.

    If you do instantiate this class directly it will create a special
    type-less null value.

    Instances compare equal only if they are of the same sub-type and
    have values that compare equal.  For completeness, a type-less null
    will compare equal to any null value.

    When instances can be converted to strings they generate strings
    according to the primitiveValue ABNF defined in the specification.
    Note that null values will raise an error and cannot be converted."""

    #: the name of this primitive type, e.g., "Edm.Int32"
    type_name = None

    def __init__(self):
        self.value = None

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

    def __bytes__(self):
        return to_text(self).encode('utf-8')

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(self.value)

    def set(self, value):
        """Sets the value of this primitive.

        The default implementation does nothing (as a typeless null is
        always null).

        It is always possible to use a derived class' implementation to
        make a deep copy of a value of that type.  E.g.::

            v1 = BooleanValue()
            # set v1 to whatever you want
            v2 = BooleanValue()
            v2.set(v1)
            # v2 always has a deep copy of v1's value
            v2 = PrimitiveValue.from_value(v1)
            # v2 is a new instance with a deep copy of v1's value

        Otherwise, if value is a primitive value of a different type the
        rules for the OData cast function are followed.

        Derived classes override this method to provide a more expansive
        set of value conversions from core Python types.

        If the set fails then the value is set to null."""
        pass

    def set_default_value(self):
        """Sets this primitive value to a default"""
        self.value = None

    @classmethod
    def from_value(cls, value):
        """Constructs a primitive value from a source value

        The returned type depends on the input value:

        None
            A type-less null (PrimitiveValue instance)
        PrimitiveValue instance (or any subclass)
            An instance of the same class with a deep copy of its value
        bool
            A BooleanValue instance
        bytes (Python2 str)
            BinaryValue instance
        datetime.date instance
            A DateValue instance
        datetime.datetime instance
            A DateTimeOffsetValue instance
        decimal.Decimal instance
            A DecimalValue instance
        float
            A DoubleValue instance
        int
            An Int64Value instance if the value is within range,
            otherwise a DecimalValue instance.
        long (Python 2 only)
            As for int.
        pyslet.iso8601.Date instance
            A DateValue instance
        pyslet.iso8601.TimePoint instance
            A DateTimeOffset instance.  The input value *must* be fully
            specified and have timezone information.
        str (Python2 unicode only)
            A StringValue instance
        uuid.UUID instance
            A GuidValue instance"""
        if value is None:
            result = PrimitiveValue()
        elif isinstance(value, PrimitiveValue):
            result = value.__class__()
            result.value = copy.deepcopy(value.value)
        elif value is True or value is False:
            result = BooleanValue()
            result.value = value
        elif isinstance(value, bytes):
            result = BinaryValue()
            result.value = value
        elif isinstance(value, Decimal):
            result = DecimalValue()
            result.value = value
        elif isinstance(value, int) or isinstance(value, long2):
            if value > Int64Value.MAX or value < Int64Value.MIN:
                result = DecimalValue.from_value(value)
            else:
                result = Int64Value()
                result.value = value
        # warning: datetime() is derived from date(), check this first!
        elif isinstance(value, (TimePoint, datetime.datetime)):
            result = DateTimeOffsetValue()
            result.set(value)
        elif isinstance(value, (Date, datetime.date)):
            result = DateValue()
            result.set(value)
        else:
            raise ValueError
        return result


class NumericValue(PrimitiveValue):

    """Abstract class for representing all numeric primitives"""

    if py2:
        _num_types = (int, long2, float, Decimal)
    else:
        _num_types = (int, float, Decimal)

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(self.value)


class IntegerValue(NumericValue):

    """Abstract class for representing all integer primitives"""

    _pytype = None      # override for each integer type

    def set(self, value):
        if isinstance(value, NumericValue):
            # numeric types can be cast
            value = value.value
        if isinstance(value, self._num_types):
            v = self._pytype(value)
            if v < self.MIN or v > self.MAX:
                self.value = None
            else:
                self.value = v

        else:
            self.value = None


class FloatValue(NumericValue):

    """Abstract class for representing all floating-point primitives"""

    def set(self, value):
        if isinstance(value, NumericValue):
            # numeric types can be cast
            value = value.value
        if isinstance(value, Decimal):
            if value > self.DECIMAL_MAX or value < self.DECIMAL_MIN:
                self.value = None
            else:
                self.value = float(value)
        elif isinstance(value, self._num_types):
            try:
                value = float(value)
                if value > self.MAX or value < self.MIN:
                    self.value = None
                else:
                    self.value = value
            except OverflowError:
                # Yes: integers can be bigger than floats!
                self.value = None
        else:
            self.value = None


class BinaryValue(PrimitiveValue):

    """Represents a value of type Edm.Binary

    The value member of a BinaryValue is either None or of type bytes.

    Binary literals are base64url encoded binary-strings as per
    http://tools.ietf.org/html/rfc4648#section-5

    Binary values can be set from most Python types, character strings
    are UTF-8 encoded, types that can be converted to other primitives
    are converted according to their syntax defined by the ABNF.  Any
    other types are converted using the builtin bytes function."""

    type_name = "Edm.Binary"

    def set(self, value=None):
        if value is None:
            self.value = None
        elif isinstance(value, bytes):
            self.value = value
        elif is_unicode(value):
            self.value = value.encode("utf-8")
        elif isinstance(value, BinaryValue):
            self.value = value.value
        elif isinstance(value, PrimitiveValue):
            self.value = None
        else:
            try:
                value = bytes(PrimitiveValue.from_value(value))
            except ValueError:
                value = bytes(value)
            self.value = value

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(base64.urlsafe_b64encode(self.value))


class BooleanValue(PrimitiveValue):

    """Represents a value of type Edm.Boolean

    The value member of a BooleanValue is either None, True or False.

    Boolean literals are one of the strings "true" or "false"

    Boolean values can be set from any other input type, the resulting
    value is the logical evaluation of the input value.  E.g., empty
    strings and lists are False, non-zero integer values True, etc.

    In the special case where the input value is a PrimitiveValue
    instance the input value's value is tested rather than the default
    boolean test which just checks if the value is non-null."""

    type_name = "Edm.Boolean"

    def set(self, value=None):
        if value is None or value is True or value is False:
            self.value = value
        elif isinstance(value, BooleanValue):
            self.value = value.value
        elif isinstance(value, PrimitiveValue):
            self.value = None
        else:
            self.value = True if value else False

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return "true" if self.value else "false"


class ByteValue(IntegerValue):

    type_name = "Edm.Byte"

    MIN = 0
    MAX = 255

    _pytype = int


class DecimalValue(NumericValue):

    type_name = "Edm.Decimal"

    def set(self, value):
        if isinstance(value, NumericValue):
            # numeric types can be cast
            value = value.value
        if isinstance(value, bool):
            # special case to as Decimal('True') is not allowed
            self.value = Decimal(value)
        elif isinstance(value, self._num_types):
            self.value = Decimal(str(value))
        else:
            self.value = None


class DoubleValue(FloatValue):

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

    DECIMAL_MAX = Decimal(str(MAX))
    DECIMAL_MIN = Decimal(str(MIN))

    type_name = "Edm.Double"


class Int16Value(IntegerValue):

    type_name = "Edm.Int16"

    MIN = -32768
    MAX = 32767

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int


class Int32Value(IntegerValue):

    type_name = "Edm.Int32"

    MIN = -2147483648
    MAX = 2147483647

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int


class Int64Value(IntegerValue):

    MAX = 9223372036854775807
    MIN = -9223372036854775808

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int


class SByteValue(IntegerValue):

    type_name = "Edm.SByte"

    MIN = -128
    MAX = 127

    _pytype = int


class SingleValue(FloatValue):

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

    DECIMAL_MAX = Decimal(str(MAX))
    DECIMAL_MIN = Decimal(str(MIN))

    type_name = "Edm.Single"


class DateValue(PrimitiveValue):

    """Represents a value of type Edm.Date

    The value member of a DateValue is either None or an instance of
    :class:`pyslet.iso8601.Date`.

    Date literals allow an expanded range of dates with potentially
    unlimited range using ISO 8601 extended format (using hyphen
    separators).  As a result, Date instances always have xdigits set to
    -1.

    Date values can be set from an instance of
    :py:class:`iso8601.Date` or the standard Python date.date instances."""

    type_name = "Edm.Date"

    def set(self, value):
        if isinstance(value, DateValue):
            self.value = value.value
        elif isinstance(value, Date):
            # force xdigits=-1, must be complete
            if not value.complete():
                self.value = None
            else:
                self.value = value.expand(xdigits=-1)
        elif isinstance(value, datetime.date):
            bce, c, y = Date.split_year(value.year)
            self.value = Date(bce=bce, century=c, year=y, month=value.month,
                              day=value.day, xdigits=-1)
        else:
            self.value = None


class DateTimeOffsetValue(PrimitiveValue):

    """Represents a value of type Edm.DateTimeOffsetValue

    The value member of a DateTimeOffsetValue is either None or an
    instance of :class:`pyslet.iso8601.TimePoint`.  OData excludes leap
    seconds.

    DateTimeOffset literals allow an expanded range of dates with
    potentially unlimited range (as per :class:`DateValue`).  As a
    result, the date component of the TimePoint is always in expanded
    form supporting a variable number of leading century digits.

    DateTimeOffset values can be set from an instance of
    :py:class:`iso8601.TimePoint`, the standard python
    datetime.datetime, datetime.date, type int, (Python 2: long,) float
    or Decimal.

    TimePoint instances must have a zone specifier.  There is *no*
    automatic assumption of UTC.

    The standard python datetime is assumed to be in UTC if utcoffset
    returns None.  The standard python date object is set by extending
    it to be the beginning of the UTC day 00:00:00Z on that date.

    When set from a numeric value, the value must be non-negative.  Unix
    time *in UTC* is assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.from_unix_time` factory method of
    TimePoint for more information."""

    type_name = "Edm.DateTimeOffset"

    def set(self, value):
        if isinstance(value, DateTimeOffsetValue):
            # representations must be complete
            self.value = value.value
        elif isinstance(value, TimePoint):
            # force xdigits=-1, must be complete
            if not value.complete():
                self.value = None
            elif value.time.get_time()[2] == 60:
                # leap second!
                self.value = TimePoint(date=value.date.expand(xdigits=-1),
                                       time=value.time.offset(seconds=-1)[0])
            else:
                self.value = value.expand(xdigits=-1)
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
                    second=value.second +
                    (value.microsecond / 1000000.0),
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
        elif isinstance(value, (int, long2, float, Decimal)) and \
                value >= 0:
            self.value = TimePoint.from_unix_time(float(value))
        else:
            self.value = None
