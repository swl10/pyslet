#! /usr/bin/env python

import logging
import math
import types
import warnings

from re import compile
from sys import maxunicode, float_info

from .. import iso8601
from ..pep8 import (
    MigratedMetaclass,
    old_function,
    old_method)
from ..py2 import (
    character,
    dict_items,
    dict_keys,
    dict_values,
    force_text,
    is_text,
    join_characters,
    py2,
    to_text,
    uempty,
    ul,
    UnicodeMixin)
from ..unicode5 import CharClass, BasicParser, ParserError
from .parser import letter
from .structures import is_valid_name, name_char


XMLSCHEMA_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
"""The namespace to use XML schema elements"""


@old_function("DecodeBoolean")
def boolean_from_str(src):
    """Decodes a boolean value from src.

    Returns python constants True or False.  As a convenience, if src is
    None then None is returned."""
    if src is None:
        return None
    elif src == "true":
        return True
    elif src == "false":
        return False
    elif src == "1":
        return True
    elif src == "0":
        return False
    else:
        raise ValueError("Can't read boolean from %s" % src)


@old_function("EncodeBoolean")
def boolean_to_str(src):
    """Encodes a boolean using the canonical lexical representation.

    src
        Anything that can be resolved to a boolean except None, which
        raises ValueError."""
    if src is None:
        raise ValueError("Can't convert None to boolean")
    elif src:
        return "true"
    else:
        return "false"


@old_function("DecodeDecimal")
def decimal_from_str(src):
    """Decodes a decimal from a string returning a python float value.

    If string is not a valid lexical representation of a decimal value
    then ValueError is raised."""
    sign = False
    point = False
    digit = False
    for c in src:
        v = ord(c)
        if v == 0x2B or v == 0x2D:
            if sign:
                raise ValueError(
                    "Invalid lexical representation of decimal: %s" % src)
            else:
                sign = True
        elif v == 0x2E:
            if point:
                raise ValueError(
                    "Invalid lexical representation of decimal: %s" % src)
            else:
                point = True
        elif v < 0x30 or v > 0x39:
            raise ValueError(
                "Invalid lexical representation of integer: %s" % src)
        else:
            # a digit means we've got an empty sign
            sign = True
            digit = True
    if not digit:
        # we must have at least one digit
        raise ValueError("Invalid lexical representation of integer: %s" % src)
    return float(src)


_uzero = ul("0")
_uone = ul("1")
_unine = ul("9")
_udot = ul(".")
_uexp = ul("E")


def _round_digits(digits):
    """Rounds a list of digits to the machine precision.  The function
    returns True if the rounding operation overflowed, this indicates
    that *digits* is one digit longer than it was when passed in."""
    if len(digits) > float_info.dig:
        # we need to add some rounding to remove spurious digits
        pos = len(digits) - 1
        while pos >= 0:
            if pos > float_info.dig:
                digits[pos] = _uzero
            elif pos == float_info.dig:
                rtest = ord(digits[pos])
                digits[pos] = _uzero
                if rtest < 0x35:
                    # no rounding needed
                    break
            elif digits[pos] == "9":
                digits[pos] = _uzero
            else:
                digits[pos] = character(ord(digits[pos]) + 1)
                # rounding done
                break
            pos = pos - 1
        if pos < 0:
            # overflow
            digits[0:0] = _uone
            return True
    else:
        return False


def _strip_zeros(digits):
    """Shortens a list of digits *digits* by stripping trailing zeros.
    *digits* may contain a point in which case one zero is always left
    after the point."""
    pos = len(digits) - 1
    while digits[pos] == '0':
        pos = pos - 1
    if digits[pos] == '.':
        # leave one zero after the point
        del digits[pos + 2:]
    else:
        del digits[pos + 1:]


@old_function("EncodeDecimal")
def decimal_to_str(value, digits=None, strip_zeros=True, **kws):
    """Encodes a decimal value into a string.

    digits
        You can control the maximum number of digits after the decimal
        point using *digits* which must be greater than 0 - None
        indicates no maximum.

    strip_zeros (aka stripZeros)
        This function always returns the canonical representation which
        means that it will strip trailing zeros in the fractional part.
        To override this behaviour and return exactly *digits* decimal
        places set *stripZeros* to False."""
    strip_zeros = kws.get('stripZeros', strip_zeros)
    if value < 0:
        sign = '-'
        value = -value
    else:
        sign = ''
    if digits is None:
        # calculate the appropriate number of digits
        try:
            x = math.log10(value)
            m, e = math.modf(x)
            e = int(e)
            # If e is 0 then we have a number in the open range [1.0,10.0)
            # which means that we need 1 fewer digits than the maximum
            # precision of float.  If e is 1 we need 2 fewer, and so on...
            # We can therefore deduce the formula for digits:
            digits = float_info.dig - (e + 1)
            if digits < 1:
                # by default we always display one digit
                digits = 1
        except ValueError:
            # not sure if this is possible, a number so small log10 fails
            value = 0.0
            digits = 1
    elif digits < 0:
        # forced to display no digits, result won't be in canonical form
        digits = 0
    if value == 0:
        # canonical representation of 0 is 0.0
        if digits is None:
            return "0.0"
        elif digits == 0:
            return "0"
        elif strip_zeros:
            return "0.0"
        else:
            return "0." + ("0" * digits)
    elif math.isnan(value) or math.isinf(value):
        raise ValueError("Invalid value for decimal: %s" %
                         double_to_str(value))
    f, i = math.modf(value * math.pow(10, digits))
    if f >= 0.5:
        i = i + 1
    dstring = list(str(int(i)))
    # assume all digits in dstring are significant
    _round_digits(dstring)
    if len(dstring) <= digits:
        # we need to zero pad on the left
        dstring[0:0] = ["0"] * (digits + 1 - len(dstring))
        dlen = digits + 1
    else:
        dlen = len(dstring)
    # now put the point in the right place
    dstring[dlen - digits:dlen - digits] = _udot
    if sign:
        dstring[0:0] = sign
    if strip_zeros:
        _strip_zeros(dstring)
    return ''.join(dstring)


_max_float = 2.0 ** 128
_min_float = 2.0 ** -149


@old_function("DecodeFloat")
def float_from_str(src):
    """Decodes a float value from a string returning a python float.

    The precision of the python float varies depending on the
    implementation. It typically exceeds the precision of the XML schema
    *float*.  We make no attempt to reduce the precision to that of
    schema's float except that we return 0.0 or -0.0 for any value that
    is smaller than the smallest possible float defined in the
    specification.  (Note that XML schema's float canonicalizes the
    representation of zero to remove this subtle distinction but it can
    be useful to preserve it for numerical operations.  Likewise, if we
    are given a representation that is larger than any valid float we
    return one of the special float values INF or -INF as appropriate."""
    s = src.lower()
    if 'e' in s:
        s = s.split('e')
        if len(s) != 2:
            raise ValueError(
                "Invalid lexical representation of double: %s" % src)
        m, e = s
        m = decimal_from_str(m)
        e = integer_from_str(e)
        result = m * math.pow(10, e)
    elif s in ("inf", "-inf", "nan"):
        return float(s)
    else:
        result = decimal_from_str(s)
    abs_result = math.fabs(result)
    if abs_result >= _max_float:
        return float("-inf") if result < 0.0 else float("inf")
    elif abs_result <= _min_float:
        # this value is too small for a float, return 0
        return -0.0 if result < 0.0 else 0.0
    else:
        return result


@old_function("EncodeFloat")
def float_to_str(value):
    """Encodes a python float value as a string.

    To reduce the chances of our output being rejected by external
    applications that are strictly bound to a 32-bit float
    representation we ensure that we don't output values that exceed the
    bounds of float defined by XML schema.

    Therefore, we convert values that are too large to INF and values
    that are too small to 0.0E0."""
    abs_value = math.fabs(value)
    if abs_value >= _max_float:
        return ul("-INF") if value < 0.0 else ul("INF")
    elif abs_value <= _min_float:
        # this value is too small for a float, return 0
        return "0.0E0"
    else:
        return double_to_str(value)


@old_function("DecodeDouble")
def double_from_str(src):
    """Decodes a double value from a string returning a python float.

    The precision of the python float varies depending on the
    implementation. It may even exceed the precision of the XML schema
    *double*.  The current implementation ignores this distinction."""
    s = src.lower()
    if 'e' in s:
        s = s.split('e')
        if len(s) != 2:
            raise ValueError(
                "Invalid lexical representation of double: %s" % src)
        m, e = s
        m = decimal_from_str(m)
        e = integer_from_str(e)
        return m * math.pow(10, e)
    elif s in ("inf", "-inf", "nan"):
        return float(s)
    else:
        return decimal_from_str(s)


@old_function("EncodeDouble")
def double_to_str(value, digits=None, strip_zeros=True, **kws):
    """Encodes a double value returning a character string.

    digits
        Controls the number of digits after the decimal point in the
        mantissa, None indicates no maximum and the precision of
        python's float is used to determine the appropriate number.  You
        may pass the value 0 in which case no digits are given after
        the point and the point itself is omitted, but such values are
        *not* in their canonical form.

    strip_zeros (aka stripZeros)
        determines whether or not trailing zeros are removed, if False
        then exactly *digits* digits will be displayed after the point.
        By default zeros are stripped (except there is always one zero
        left after the decimal point)."""
    strip_zeros = kws.get('stripZeros', strip_zeros)
    if digits is None:
        digits = float_info.dig - 2
        if digits < 0:
            # by default we show at least one digit
            digits = 1
    elif digits < 0:
        digits = 0
    if value == 0:
        # canonical representation of 0 is 0.0E0
        if digits == 0:
            return "0E0"
        elif strip_zeros:
            return "0.0E0"
        else:
            return "0." + ("0" * digits) + "E0"
    elif math.isnan(value):
        return "NAN"
    elif math.isinf(value):
        return "INF" if value > 0 else "-INF"
    if value < 0:
        sign = '-'
        value = -value
    else:
        sign = ''
    try:
        x = math.log10(value)
    except ValueError:
        # not sure if this is possible, a number so small log10 fails
        return "0.0E0"
    m, e = math.modf(x)
    e = int(e)
    r, m = math.modf(math.pow(10, m + digits))
    if r >= 0.5:
        m = m + 1
    dstring = list(str(int(m)))
    # m should originally have been in [1,10) but we need to check for
    # over/underflow
    if len(dstring) > digits + 1:
        # overflow, strip the trailing zero
        e = e + 1
        del dstring[-1]
    elif len(dstring) <= digits:
        # underflow - probably impossible, e.g,
        # pow(10,log10(1.000)+N)->999....9(.9)
        e = e - 1
        dstring.append(_unine)
    # inevitably, after this len(dstring)==digits+1
    if _round_digits(dstring):
        del dstring[-1]
    assert dstring[0] != '0'
    if len(dstring) > 1:
        dstring[1:1] = _udot
    if strip_zeros:
        _strip_zeros(dstring)
    if sign:
        dstring[0:0] = sign
    dstring.append(_uexp)
    dstring.append(str(e))
    return ''.join(dstring)


class Duration(iso8601.Duration):

    """Represents duration values.

    Extends the basic iso duration class to include negative durations."""

    def __init__(self, value=None):
        self.sign = 1       #: an integer with the sign of the duration
        if is_text(value):
            self.set_from_string(value)
        elif isinstance(value, iso8601.Duration):
            self.set_from_duration(value)
        elif value is None:
            self.set_zero()
        else:
            raise TypeError

    def __unicode__(self):
        """Formats this duration."""
        result = force_text(
            self.get_string(truncate_zeros=1, ndp=None, dp='.'))
        if self.sign < 0:
            return "-" + result
        else:
            return result

    def set_from_string(self, duration_str):
        if is_text(duration_str):
            if duration_str[0] == '-':
                self.sign = -1
                duration_str = duration_str[1:]
            else:
                self.sign = 1
            p = iso8601.ISO8601Parser(duration_str)
            return p.parse_duration(self)
        else:
            raise TypeError

    def set_from_duration(self, src):
        if isinstance(src, Duration):
            self.sign = src.sign
        else:
            self.sign = 1
        iso8601.Duration.set_from_duration(self, src)


@old_function("DecodeDateTime")
def datetime_from_str(src):
    """Returns a :py:class:`pyslet.iso8601.TimePoint` instance."""
    try:
        return iso8601.TimePoint.from_str(src)
    except iso8601.DateTimeError as e:
        raise ValueError(str(e))


@old_function("EncodeDateTime")
def datetime_to_str(value):
    """Returns the canonical lexical representation for dateTime

    value:
        An instance of :py:class:`pyslet.iso8601.TimePoint`"""
    return value.get_calendar_string()


@old_function("DecodeName")
def name_from_str(src):
    """Decodes a name from a string.

    Returns the same string or raises ValueError if src does not match
    the XML production Name."""
    if is_valid_name(src):
        return src
    else:
        raise ValueError("Invalid Name: %s" % src)


@old_function("EncodeName")
def name_to_str(src):
    """Encodes a name

    A convenience function (equivalent to :func:`pyslet.py2.to_text`."""
    return force_text(src)


@old_function('DecodeInteger')
def integer_from_str(src):
    """Decodes an integer

    If string is not a valid lexical representation of an integer then
    ValueError is raised.  This uses XML Schema's lexical rules which
    are slightly different from Python's native conversion."""
    sign = False
    for c in src:
        v = ord(c)
        if v == 0x2B or v == 0x2D:
            if sign:
                raise ValueError(
                    "Invalid lexical representation of integer: %s" % src)
            else:
                sign = True
        elif v < 0x30 or v > 0x39:
            raise ValueError(
                "Invalid lexical representation of integer: %s" % src)
        else:
            # a digit means we've got an empty sign
            sign = True
    return int(src)


@old_function('EncodeInteger')
def integer_to_str(value):
    """Encodes an integer value using the canonical lexical representation."""
    return to_text(value)


class EnumMetaClass(MigratedMetaclass):

    """Metaclass for :class:`Enumeration`

    Initialises the Enumeration immediately after the class is
    defined."""

    def __init__(self, name, bases, dct):
        # self is a class here!
        if hasattr(self, '_init_enum'):
            # EnumBase itself won't have this method!
            self._init_enum()


if py2:
    class EnumBase(object):
        __metaclass__ = EnumMetaClass
else:
    EnumBase = types.new_class("EnumBase", (object, ),
                               {'metaclass': EnumMetaClass})


class Enumeration(EnumBase):

    """Abstract class for defining enumerations

    The class is not designed to be instantiated but to act as a method
    of defining constants to represent the values of an enumeration and
    for converting between those constants and the appropriate string
    representations.

    The basic usage of this class is to derive a class from it with a single
    class member called 'decode' which is a mapping from canonical strings to
    simple integers.

    Once defined, the class will be automatically populated with a
    reverse mapping dictionary (called encode) and the enumeration
    strings will be added as attributes of the class itself.  For exampe::

        class Fruit(Enumeration):
            decode = {
                'Apple": 1,
                'Pear': 2,
                'Orange': 3}

        Fruit.Apple == 1    # True thanks to metaclass

    You can add define additional mappings by providing a second
    dictionary called aliases that maps additional names onto existing
    values.  The aliases dictionary is a mapping from strings onto the
    equivalent canonical string::

        class Vegetables(Enumeration):
            decode = {
                'Tomato': 1,
                'Potato': 2,
                'Courgette': 3}

            aliases = {
                'Zucchini': 'Courgette'}

        Vegetables.Zucchini == 3       # True thanks to metaclass

    You may also add the special key None to the aliases dictionary to
    define a default value for the enumeration.  This is mapped to an
    attribute called DEFAULT::

        class Staples(Enumeration):
            decode = {
                'Bread': 1,
                'Pasta': 2,
                'Rice': 3}

            aliases = {
                None: 'Bread'}

        Staples.DEFAULT == 1        # True thanks to metaclass"""

    @classmethod
    def _init_enum(cls):
        if not hasattr(cls, 'decode'):
            # Skip initialisation for Enumeration itself
            return
        setattr(cls, 'encode',
                dict((k, v) for (k, v) in zip(
                     dict_values(cls.decode), dict_keys(cls.decode))))
        if hasattr(cls, 'aliases'):
            for k, v in dict_items(cls.aliases):
                if k is None:
                    cls.DEFAULT = cls.decode[v]
                else:
                    cls.decode[k] = cls.decode[v]
        for k, v in dict_items(cls.decode):
            try:
                getattr(cls, k)
                logging.error("Illegal name for Enumeration: %s" % repr(k))
            except AttributeError:
                setattr(cls, k, v)

    DEFAULT = None
    """The DEFAULT value of the enumeration defaults to None"""

    @classmethod
    @old_method('DecodeValue')
    def from_str(cls, src):
        """Decodes a string returning a value in this enumeration.

        If no legal value can be decoded then ValueError is raised."""
        try:
            src = src.strip()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    @old_method('DecodeLowerValue')
    def from_str_lower(cls, src):
        """Decodes a string, converting it to lower case first.

        Returns a value in this enumeration.  If no legal value can be
        decoded then ValueError is raised."""
        try:
            src = src.strip().lower()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    @old_method('DecodeUpperValue')
    def from_str_upper(cls, src):
        """Decodes a string, converting it to upper case first.

        Returns a value in this enumeration.  If no legal value can be
        decoded then ValueError is raised."""
        try:
            src = src.strip().upper()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    @old_method('DecodeTitleValue')
    def from_str_title(cls, src):
        """Decodes a string, converting it to title case first.

        Title case is defined as an initial upper case letter with all
        other letters lower case.

        Returns a value in this enumeration.  If no legal value can be
        decoded then ValueError is raised."""
        try:
            src = src.strip()
            src = src[0].upper() + src[1:].lower()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    @old_method('DecodeValueList')
    def list_from_str(cls, decoder, src):
        """Decodes a list of values

        decoder
            One of the from_str methods.

        src
            A space-separated string of values

        The result is an ordered list of values (possibly containing
        duplicates).

        Example usage::

                Fruit.list_from_str(Fruit.from_str_title,
                                    "apple orange pear")
                # returns [ Fruit.Apple, Fruit.Orange, Fruit.Pear ]"""
        return [decoder(s) for s in src.split()]

    @classmethod
    @old_method('DecodeValueDict')
    def dict_from_str(cls, decoder, src):
        """Decodes a dictionary of values

        decoder
            One of the from_str methods

        src
            A space-separated string of values.

        The result is a dictionary mapping the values found as keys onto
        the strings used to represent them.  Duplicates are mapped to
        the first occurrence of the encoded value.

        Example usage::

            Fruit.dict_from_str(Fruit.from_str_title,
                                "Apple orange PEARS apple")
                # returns {Fruit.Apple: 'Apple', Fruit.Orange: 'orange',
                #          Fruit.Pear: 'PEARS' }"""
        result = {}
        for s in src.split():
            sv = decoder(s)
        if sv not in result:
            result[sv] = s
        return result

    @classmethod
    @old_method('EncodeValue')
    def to_str(cls, value):
        """Encodes one of the enumeration constants returning a string.

        If value is None then the encoded default value is returned (if
        defined) or None."""
        return cls.encode.get(value, cls.encode.get(cls.DEFAULT, None))

    @classmethod
    @old_method('EncodeValueList')
    def list_to_str(cls, value_list):
        """Encodes a list of enumeration constants

        value_list
            A list or iterable of integer values corresponding to
            enumeration constants.

        Returns a space-separated string.  If valueList is empty then an
        empty string is returned."""
        return ' '.join(cls.to_str(s) for s in value_list)

    @classmethod
    @old_method('EncodeValueDict')
    def dict_to_str(cls, value_dict, sort_keys=True, **kws):
        """Encodes a dictionary of enumeration constants

        value_dict
            A dictionary with integer keys corresponding to enumeration
            constant values.

        sort_keys
            Boolean indicating that the result should be sorted by
            constant value.  (Defaults to True.)

        Returns a space-separated string.  If value_dict is empty then
        an empty string is returned.  The values in the dictionary are
        ignored, the keys are used to obtain the canonical
        representation of each value.  Extending the example given in
        :py:meth:`dict_from_str`::

            Fruit.dict_to_str(
                {Fruit.Apple: 'Apple', Fruit.Orange: 'orange',
                 Fruit.Pear: 'PEARS' })
            # returns: "Apple Pear Orange"

        The order of the values in the string is determined by the sort
        order of the enumeration constants (*not* their string
        representation).  This ensures that equivalent dictionaries are
        always encoded to the same string.  In the above example::

                Fruit.Apple < Fruit.Pear < Fruit.Orange

        If you have large lists then you can skip the sorting step by
        passing False for *sort_keys* to improve performance at the
        expense of an unpredictable encoding."""
        sort_keys = kws.get('sortKeys', sort_keys)
        if sort_keys:
            return cls.list_to_str(sorted(dict_keys(value_dict)))
        else:
            return cls.list_to_str(dict_keys(value_dict))


@old_function('MakeEnumeration')
def make_enum(cls, default_value=None, **kws):
    """Deprecated function

    This function is no longer required and does nothing unless
    default_value is passed in which case it adds the DEFAULT attribute
    to the Enumeration cls as if an alias had been declared for None
    (see :class:`Enumeration` above for details)."""
    default_value = kws.get('defaultValue', default_value)
    if default_value is not None:
        warnings.warn('MakeEnumeration(%s, %s): add %s.aliases = '
                      '{None: %s} to class definition instead' %
                      (cls.__name__, repr(default_value), cls.__name__,
                       repr(default_value)))
        setattr(cls, 'DEFAULT', cls.decode[default_value])
    else:
        warnings.warn('MakeEnumeration(%s) no longer required' %
                      cls.__name__)


@old_function('MakeEnumerationAliases')
def make_enum_aliases(cls, aliases):
    """Deprecated function

    Supported for backwards compatibility, modify enum class definitions
    to include aliases as an attribute directly::

        class MyEnum(Enumeration):
            decode = {
                # strings to ints mapping
                }
            aliases = {
                # aliases to strings mapping
                }

    The new metaclass takes care of processing the aliases dictionary
    when the class is created."""
    warnings.warn('MakeEnumerationAliases(%s, {...}): add %s.aliases = '
                  '{...} to class definition instead' %
                  (cls.__name__, cls.__name__))
    for k, v in dict_items(aliases):
        if k is None:
            cls.DEFAULT = v
        else:
            cls.decode[k] = cls.decode[v]
            try:
                getattr(cls, k)
                logging.error("Illegal name for Enumeration: %s" % repr(k))
            except AttributeError:
                setattr(cls, k, cls.decode[k])


class EnumerationNoCase(Enumeration):

    """Convenience class that automatically adds lower-case aliases

    On creation, the enumeration ensures that aliases equivalent to the
    lower-cased canonical strings are defined.  Designed to be used in
    conjunction with :meth:`from_str_lower` for case insensitive
    matching of enumumeration strings."""

    @classmethod
    def _init_enum(cls):
        if not hasattr(cls, 'decode'):
            # Skip initialisation for EnumerationNoCase itself
            return
        if not hasattr(cls, 'aliases'):
            cls.aliases = {}
        for k in dict_keys(cls.decode):
            a = k.lower()
            if a != k and a not in cls.aliases:
                cls.aliases[a] = k
        super(EnumerationNoCase, cls)._init_enum()


@old_function('MakeLowerAliases')
def make_lower_aliases(cls):
    """Deprecated function

    Supported for backwards compatibility.  Use new class
    :class:`EnumerationNoCase` instead.

    Warning, the new class will only add lower-case aliases for the
    canonical strings, any additional aliases (defined in the aliases
    dictionary attribute) must already be lower-case or be defined with
    both case variants."""
    for key in list(dict_keys(cls.decode)):
        alias = key.lower()
        if alias not in cls.decode:
            # Declare this alias
            cls.decode[alias] = cls.decode[key]
            try:
                getattr(cls, alias)
                logging.error("Illegal name for Enumeration: %s" % repr(alias))
            except AttributeError:
                setattr(cls, alias, cls.decode[key])


@old_function('WhiteSpaceReplace')
def white_space_replace(value):
    """Replaces tab, line feed and carriage return with space."""
    output = []
    for c in value:
        if c in "\x09\x0A\x0D":
            output.append(character(0x20))
        else:
            output.append(c)
    return ''.join(output)


@old_function('WhiteSpaceCollapse')
def white_space_collapse(value):
    """Replaces all runs of white space with a single space. Also removes
    leading and trailing white space."""
    output = []
    got_space = False
    for c in value:
        if c in "\x09\x0A\x0D\x20":
            got_space = True
        else:
            if output and got_space:
                output.append(character(0x20))
                got_space = False
            output.append(c)
    return ''.join(output)


class RegularExpression(UnicodeMixin):

    """A regular expression as defined by XML schema.

    Regular expressions are constructed from character strings.
    Internally they are parsed and converted to Python regular
    expressions to speed up matching.

    Warning: because the XML schema expression language contains
    concepts not supported by Python the python regular expression may
    not be very readable."""

    def __init__(self, src):
        #: the original source string
        self.src = force_text(src)
        p = RegularExpressionParser(src)
        pyre = p.require_reg_exp()
        #: the compiled python regular expression
        self.p = compile(pyre)

    def __unicode__(self):
        return self.src

    def __repr__(self):
        return "RegularExpression(%s)" % repr(self.src)

    def match(self, target):
        """Returns True if the expression matches *target*."""
        m = self.p.match(target)
        if m is None or m.end(0) < len(target):
            return False
        else:
            return True


RegularExpressionError = ParserError

_upipe = ul("|")
_ustar = ul("*")
_udash = ul("-")
_uquestion = ul("?")
_uplus = ul("+")


class RegularExpressionParser(BasicParser):

    """A custom parser for XML schema regular expressions.

    The parser is initialised from a character string and always
    operates in text mode."""

    def __init__(self, source):
        source = force_text(source)
        super(RegularExpressionParser, self).__init__(source)

    def _re_escape(self, c=None):
        if c is None:
            c == self.the_char
        if c in ".^$*+?{}\\[]|()":
            return "\\" + c
        else:
            return c

    def require_reg_exp(self):
        """Parses a regExp

        Returns a unicode string representing the regular expression."""
        result = []
        while True:
            # expression ends at the end of the string or at a closing bracket
            result.append(self.require_branch())
            if self.the_char == "|":
                self.next_char()
                result.append(_upipe)
                continue
            else:
                break
        return join_characters(result)

    def require_branch(self):
        """Parses branch

        Returns a character string representing these pieces as a python
        regular expression."""
        result = []
        while self.is_char() or self.match_one(".\\[("):
            result.append(self.require_piece())
        return join_characters(result)

    def require_piece(self):
        """Parses piece

        Returns a character string representing this piece in python
        regular expression format."""
        result = self.require_atom()
        if self.match_one("?*+{"):
            n, m = self.require_quantifier()
            if n == 0:
                if m is None:
                    return result + _ustar
                elif m == 0:
                    return uempty
                elif m == 1:
                    return result + _uquestion
                else:
                    return "%s{,%i}" % (result, m)
            elif n == 1:
                if m is None:
                    return result + _uplus
                elif m == 1:
                    return result
                else:
                    return "%s{1,%i}" % (result, m)
            elif m is None:
                return "%s{%i,}" % (result, n)
            elif n == m:
                return "%s{%i}" % (result, n)
            else:
                return "%s{%i,%i}" % (result, n, m)
        else:
            return result

    def require_quantifier(self):
        """Parses quantifier

        Returns a tuple of (n, m).

        Symbolic values are expanded to the appropriate pair.  The
        second value may be None indicating unbounded."""
        if self.the_char == "?":
            self.next_char()
            return 0, 1
        elif self.the_char == "*":
            self.next_char()
            return 0, None
        elif self.the_char == "+":
            self.next_char()
            return 1, None
        elif self.the_char == "{":
            self.next_char()
            result = self.require_quantity()
            if self.the_char == "}":
                self.next_char()
                return result
            else:
                raise RegularExpressionError("Expected } at [%i]" % self.pos)
        else:
            raise RegularExpressionError(
                "Expected quantifier at [%i]" % self.pos)

    def require_quantity(self):
        """Parses quantity

        Returns a tuple of (n, m) even if an exact quantity is given.

        In other words, the exact quantity 'n' returns (n, n).  The
        second value may be None indicating unbounded."""
        n = self.require_quant_exact()
        m = None
        if self.the_char == ",":
            self.next_char()
            if self.match_one("0123456789"):
                m = self.require_quant_exact()
                if n > m:
                    raise RegularExpressionError(
                        "Illegal quantity: {%i,%i}" % (n, m))
        else:
            m = n
        return n, m

    def require_quant_exact(self):
        """Parses QuantEact

        Returns the integer value parsed."""
        result = 0
        n_digits = 0
        while self.match_one("0123456789"):
            result = result * 10 + ord(self.the_char) - 0x30
            self.next_char()
            n_digits += 1
        if n_digits == 0:
            self.parser_error("QuantExact")
        return result

    def require_atom(self):
        """Parses atom

        Returns a unicode string representing this atom as a python
        regular expression."""
        if self.is_char():
            result = self._re_escape(self.the_char)
            self.next_char()
        elif self.the_char == "(":
            # a regular expression
            self.next_char()
            result = "(%s)" % self.require_reg_exp()
            if self.the_char != ")":
                raise RegularExpressionError("Expected ) at [%i]" % self.pos)
            self.next_char()
        else:
            cclass = self.require_char_class()
            result = to_text(cclass)
        return result

    def is_char(self, c=None):
        """Parses Char

        Returns either True or False depending on whether
        :attr:`the_char` satisfies the production Char.

        The definition of this function is designed to be conservative
        with respect to the specification, which is clearly in error
        around production [10] as the prose and the BNF do not match. It
        appears that | was intended to be excluded in the prose but has
        been omitted, the reverse being true for the curly-brackets."""
        if c is None:
            c = self.the_char
        if c is None or c in ".\\?*+{}()[]|":
            return False
        else:
            return True

    def require_char_class(self):
        """Parses a charClass."""
        if self.the_char == "[":
            return self.require_char_class_expr()
        elif self.the_char == "\\":
            return self.require_char_class_esc()
        elif self.the_char == ".":
            return self.require_wildcard_esc()
        else:
            self.parser_error("charClass")

    def require_char_class_expr(self):
        """Parses charClassExpr"""
        if self.the_char == "[":
            self.next_char()
            cclass = self.require_char_group()
            if self.the_char == "]":
                self.next_char()
                return cclass
            else:
                self.parser_error("charClassExpr")
        else:
            self.parser_error("charClassExpr")

    def require_char_group(self):
        """Parses charGroup.

        This method also handles the case of a class subtraction
        directly to reduce the need for look-ahead.  If you specifically
        want to parse a subtraction you can do this with
        :py:meth:`require_char_class_sub`."""
        if self.the_char == "^":
            cclass = self.require_neg_char_group()
        else:
            cclass = self.require_pos_char_group()
        if self.the_char == "-":
            self.next_char()
            sub_class = self.require_char_class_expr()
            cclass.subtract_class(sub_class)
        return cclass

    def require_pos_char_group(self):
        """Parses posCharGroup"""
        cclass = CharClass()
        nranges = 0
        while True:
            savepos = self.pos
            if self.the_char == "-" and nranges:
                # This had better be the last hyphen in the posCharGroup
                if self.match("-["):
                    # a subtraction
                    break
                elif self.match("-]") or self.match("--["):
                    cclass.add_char(_udash)
                    self.next_char()
                    break
                else:
                    # this is all wrong
                    self.parser_error("posCharGroup")
            try:
                cclass.add_class(self.require_char_range())
                nranges += 1
                continue
            except ParserError:
                self.setpos(savepos)
                pass
            try:
                cclass.add_class(self.require_char_class_esc())
                nranges += 1
                continue
            except ParserError:
                if nranges:
                    self.setpos(savepos)
                    break
                else:
                    # We expected either a charRange or a charClassEsc
                    self.parser_error()
        return cclass

    def require_neg_char_group(self):
        """Parses negCharGroup."""
        if self.the_char == "^":
            # we have a negative range
            self.next_char()
            cclass = self.require_pos_char_group()
            cclass.negate()
            return cclass
        else:
            self.parser_error("negCharGroup")

    def require_char_class_sub(self):
        """Parses charClassSub

        This method is not normally used by the parser as in present for
        completeness.  See
        :py:meth:`require_char_group`."""
        if self.the_char == "^":
            cclass = self.require_neg_char_group()
        else:
            cclass = self.require_pos_char_group()
        if self.the_char == "-":
            self.next_char()
            sub_class = self.require_char_class_expr()
            cclass.subtract_class(sub_class)
            return cclass
        else:
            self.parser_error("charClassSub")

    def require_char_range(self):
        """Parses a charRange."""
        cclass = self.parse_production(self.require_se_range)
        if cclass is None:
            if self.is_xml_char_inc_dash():
                cclass = CharClass(self.the_char)
                self.next_char()
            else:
                self.parser_error()
        return cclass

    def require_se_range(self):
        """Parses seRange."""
        s = self.require_char_or_esc()
        if self.the_char == "-":
            self.next_char()
        else:
            self.parser_error("seRange")
        e = self.require_char_or_esc()
        if ord(s) > ord(e):
            self.parser_error("(non-empty) seRange")
        return CharClass((s, e))

    def require_char_or_esc(self):
        """Parses charOrEsc."""
        if self.is_xml_char():
            result = self.the_char
            self.next_char()
            return result
        else:
            return self.require_single_char_esc()

    def is_xml_char(self, c=None):
        if c is None:
            c = self.the_char
        return c is not None and c not in "\\-[]"

    def is_xml_char_inc_dash(self, c=None):
        if c is None:
            c = self.the_char
        return c is not None and c not in "\\[]"

    def require_char_class_esc(self):
        """Parsers charClassEsc.

        Returns a CharClass instance."""
        cclass = self.parse_production(self.require_cat_esc)
        if cclass is None:
            cclass = self.parse_production(self.require_compl_esc)
        if cclass is None:
            cclass = self.parse_production(self.require_multi_char_esc)
        if cclass is None:
            cclass = self.parse_production(self.require_single_char_esc)
            if cclass is not None:
                cclass = CharClass(cclass)
        if cclass is None:
            self.parser_error()
        else:
            return cclass

    single_char_escapes = {
        'n': character(0x0A),
        'r': character(0x0D),
        't': character(0x09),
        '\\': ul('\\'),
        '|': ul('|'),
        '.': ul('.'),
        '-': ul('-'),
        '^': ul('^'),
        '?': ul('?'),
        '*': ul('*'),
        '+': ul('+'),
        '{': ul('{'),
        '}': ul('}'),
        '(': ul('('),
        ')': ul(')'),
        '[': ul('['),
        ']': ul(']')}

    def require_single_char_esc(self):
        """Parses SingleCharEsc

        Returns a single character."""
        if self.the_char == "\\":
            self.next_char()
            if self.the_char in self.single_char_escapes:
                result = self.single_char_escapes[self.the_char]
                self.next_char()
                return result
        self.parser_error("SingleCharEsc")

    def require_cat_esc(self):
        """Parses catEsc."""
        if self.match("\\p{"):
            self.setpos(self.pos + 3)
            cclass = self.require_char_prop()
            if self.the_char == '}':
                self.next_char()
                return cclass
        self.parser_error("catEsc")

    def require_compl_esc(self):
        """Parses complEsc."""
        if self.match("\\P{"):
            self.setpos(self.pos + 3)
            cclass = CharClass(self.require_char_prop())
            if self.the_char == '}':
                self.next_char()
                cclass.negate()
                return cclass
        self.parser_error("complEsc")

    def require_char_prop(self):
        """Parses a charProp."""
        savepos = self.pos
        try:
            cclass = self.require_is_category()
        except RegularExpressionError:
            self.setpos(savepos)
            cclass = self.require_is_block()
        return cclass

    categories = {
        "L": True,
        "Lu": True,
        "Ll": True,
        "Lt": True,
        "Lm": True,
        "Lo": True,
        "M": True,
        "Mn": True,
        "Mc": True,
        "Me": True,
        "N": True,
        "Nd": True,
        "Nl": True,
        "No": True,
        "P": True,
        "Pc": True,
        "Pd": True,
        "Ps": True,
        "Pe": True,
        "Pi": True,
        "Pf": True,
        "Po": True,
        "Z": True,
        "Zs": True,
        "Zl": True,
        "Zp": True,
        "S": True,
        "Sm": True,
        "Sc": True,
        "Sk": True,
        "So": True,
        "C": True,
        "Cc": True,
        "Cf": True,
        "Co": True,
        "Cn": True
    }

    def require_is_category(self):
        """Parses IsCategory."""
        if self.the_char in self.categories:
            cat = self.the_char
            self.next_char()
            if self.the_char is not None and \
                    (cat + self.the_char) in self.categories:
                cat = cat + self.the_char
                self.next_char()
            return CharClass.ucd_category(cat)
        else:
            self.parser_error("IsCategory")

    is_block_class = CharClass(('a', 'z'), ('A', 'Z'), ('0', '9'), '-')

    def require_is_block(self):
        """Parses IsBlock."""
        block = []
        while self.is_block_class.test(self.the_char):
            block.append(self.the_char)
            self.next_char()
        block = ''.join(block)
        if block.startswith("Is"):
            try:
                return CharClass.ucd_block(block[2:])
            except KeyError:
                self.parser_error("IsBlock")
        else:
            self.parser_error("IsBlock")

    multi_char_escapes = {
        's': CharClass("\x20\t\n\r"),
        'S': CharClass("\x20\t\n\r").negate(),
        'i': CharClass(letter, '_:'),
        'I': CharClass(letter, '_:').negate(),
        'c': name_char,
        'C': CharClass(name_char).negate(),
        'd': CharClass.ucd_category('Nd'),
        'D': CharClass(CharClass.ucd_category('Nd')).negate(),
        'w': CharClass(CharClass.ucd_category('P'),
                       CharClass.ucd_category('Z'),
                       CharClass.ucd_category('C')).negate(),
        'W': CharClass(CharClass.ucd_category('P'),
                       CharClass.ucd_category('Z'),
                       CharClass.ucd_category('C'))
    }

    def require_multi_char_esc(self):
        """Parses a MultiCharEsc."""
        if self.the_char == "\\":
            self.next_char()
            try:
                result = self.multi_char_escapes[self.the_char]
                self.next_char()
                return result
            except KeyError:
                # unknown escape
                self.parser_error("MultiCharEsc")
        else:
            self.parser_error("MultiCharEsc")

    dot_class = CharClass(
        (character(0), character(9)),
        (character(11), character(12)),
        (character(14), character(maxunicode)))

    def require_wildcard_esc(self):
        """Parses '.', the wildcard CharClass"""
        if self.the_char == ".":
            self.next_char()
            return self.dot_class
        else:
            self.parser_error("WildcardEsc")
