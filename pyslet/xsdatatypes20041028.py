#! /usr/bin/env python


import string
import math
from sys import maxunicode, float_info
from re import compile
from types import *

import pyslet.iso8601 as iso8601
from pyslet.xml20081126.structures import IsValidName, LetterCharClass, NameCharClass
from pyslet.unicode5 import CharClass, BasicParser

XMLSCHEMA_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"


def DecodeBoolean(src):
    """Decodes a boolean value from src.

    Returns python constants True or False.  As a convenience, if src is None
    then None is returned."""
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
        raise ValueError


def EncodeBoolean(src):
    """Encodes a boolean value using the canonical lexical representation.

    src can be anything that can be resolved to a boolean except None, which
    raises ValueError."""
    if src is None:
        raise ValueError
    elif src:
        return "true"
    else:
        return "false"


def DecodeDecimal(src):
    """Decodes a decimal value from a string returning a python float value.

    If string is not a valid lexical representation of a decimal value then
    ValueError is raised."""
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


def _RoundDigits(digits):
    """Rounds a list of digits to the machine precision.  The function returns
    True if the rounding operation overflowed, this indicates that *digits* is
    one digit longer than it was when passed in."""
    if len(digits) > float_info.dig:
        # we need to add some rounding to remove spurious digits
        pos = len(digits) - 1
        while pos >= 0:
            if pos > float_info.dig:
                digits[pos] = u"0"
            elif pos == float_info.dig:
                rTest = ord(digits[pos])
                digits[pos] = u"0"
                if rTest < 0x35:
                    # no rounding needed
                    break
            elif digits[pos] == u"9":
                digits[pos] = u"0"
            else:
                digits[pos] = unichr(ord(digits[pos]) + 1)
                # rounding done
                break
            pos = pos - 1
        if pos < 0:
            # overflow
            digits[0:0] = u"1"
            return True
    else:
        return False


def _StripZeros(digits):
    """Shortens a list of digits *digits* by stripping trailing zeros. *digits*
    may contain a point in which case one zero is always left after the
    point."""
    pos = len(digits) - 1
    while digits[pos] == u'0':
        pos = pos - 1
    if digits[pos] == '.':
        # leave one zero after the point
        del digits[pos + 2:]
    else:
        del digits[pos + 1:]


def EncodeDecimal(value, digits=None, stripZeros=True):
    """Encodes a decimal value into a string.

    You can control the maximum number of digits after the decimal point using
    *digits* which must be greater than 0 - None indicates no maximum.  This
    function always returns the canonical representation which means that it
    will strip trailing zeros in the fractional part.  To override this
    behaviour and return exactly *digits* decimal places set *stripZeros* to
    False."""
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
        elif stripZeros:
            return "0.0"
        else:
            return "0." + ("0" * digits)
    elif math.isnan(value) or math.isinf(value):
        raise ValueError("Invalid value for decimal: %s" % EncodeDouble(value))
    f, i = math.modf(value * math.pow(10, digits))
    if f >= 0.5:
        i = i + 1
    dString = list(str(int(i)))
    # assume all digits in dString are significant
    _RoundDigits(dString)
    if len(dString) <= digits:
        # we need to zero pad on the left
        dString[0:0] = ["0"] * (digits + 1 - len(dString))
        dLen = digits + 1
    else:
        dLen = len(dString)
    # now put the point in the right place
    dString[dLen - digits:dLen - digits] = u"."
    if sign:
        dString[0:0] = sign
    if stripZeros:
        _StripZeros(dString)
    return string.join(dString, '')


_MaxFloat = 2.0 ** 128
_MinFloat = 2.0 ** -149


def DecodeFloat(src):
    """Decodes a float value from a string returning a python float.

    The precision of the python float varies depending on the implementation. It
    typically exceeds the precision of the XML schema *float*.  We make no
    attempt to reduce the precision to that of schema's float except that we
    return 0.0 or -0.0 for any value that is smaller than the smallest possible
    float defined in the specification.  (Note that XML schema's float
    canonicalizes the representation of zero to remove this subtle distinction
    but it can be useful to preserve it for numerical operations.  Likewise, if
    we are given a representation that is larger than any valid float we return
    one of the special float values INF or -INF as appropriate."""
    s = src.lower()
    if 'e' in s:
        s = s.split('e')
        if len(s) != 2:
            raise ValueError(
                "Invalid lexical representation of double: %s" % src)
        m, e = s
        m = DecodeDecimal(m)
        e = DecodeInteger(e)
        result = m * math.pow(10, e)
    elif s in ("inf", "-inf", "nan"):
        return float(s)
    else:
        result = DecodeDecimal(s)
    absResult = math.fabs(result)
    if absResult >= _MaxFloat:
        return float("-inf") if result < 0.0 else float("inf")
    elif absResult <= _MinFloat:
        # this value is too small for a float, return 0
        return -0.0 if result < 0.0 else 0.0
    else:
        return result


def EncodeFloat(value):
    """Encodes a python float value as a string.

    To reduce the chances of our output being rejected by external applications
    that are strictly bound to a 32-bit float representation we ensure that we
    don't output values that exceed the bounds of float defined by XML schema.

    Therefore, we convert values that are too large to INF and values that are
    too small to 0.0E0."""
    absValue = math.fabs(value)
    if absValue >= _MaxFloat:
        return u"-INF" if value < 0.0 else u"INF"
    elif absValue <= _MinFloat:
        # this value is too small for a float, return 0
        return "0.0E0"
    else:
        return EncodeDouble(value)


def DecodeDouble(src):
    """Decodes a double value from a string returning a python float.

    The precision of the python float varies depending on the implementation. It
    may even exceed the precision of the XML schema *double*.  The current
    implementation ignores this distinction."""
    s = src.lower()
    if 'e' in s:
        s = s.split('e')
        if len(s) != 2:
            raise ValueError(
                "Invalid lexical representation of double: %s" % src)
        m, e = s
        m = DecodeDecimal(m)
        e = DecodeInteger(e)
        return m * math.pow(10, e)
    elif s in ("inf", "-inf", "nan"):
        return float(s)
    else:
        return DecodeDecimal(s)


def EncodeDouble(value, digits=None, stripZeros=True):
    """Encodes a double value returning a unicode string.

    *digits* controls the number of digits after the decimal point in the
    mantissa, None indicates no maximum and the precision of python's float is
    used to determine the appropriate number.  You may pass the value 0 - in
    which case no digits are given after the point and the point itself is
    omitted, but such values are *not* in their canonical form.

    *stripZeros* determines whether or not trailing zeros are removed, if False
    then exactly *digits* digits will be displayed after the point.  By default
    zeros are stripped (except there is always one zero left after the decimal
    point)."""
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
        elif stripZeros:
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
    dString = list(str(int(m)))
    # m should originally have been in [1,10) but we need to check for
    # over/underflow
    if len(dString) > digits + 1:
        # overflow, strip the trailing zero
        e = e + 1
        del dString[-1]
    elif len(dString) <= digits:
        # underflow - probably impossible, e.g,
        # pow(10,log10(1.000)+N)->999....9(.9)
        e = e - 1
        dString.append(u"9")
    # inevitably, after this len(dString)==digits+1
    if _RoundDigits(dString):
        del dString[-1]
    assert dString[0] != u'0'
    if len(dString) > 1:
        dString[1:1] = u"."
    if stripZeros:
        _StripZeros(dString)
    if sign:
        dString[0:0] = sign
    dString.append(u"E")
    dString.append(str(e))
    return string.join(dString, '')


class Duration(iso8601.Duration):

    """Represents duration values.

    Extends the basic iso duration class to include negative durations."""

    def __init__(self, value=None):
        self.sign = 1		#: an integer with the sign of the duration
        if type(value) in StringTypes:
            self.set_from_string(value)
        elif isinstance(value, iso8601.Duration):
            self.set_from_duration(value)
        elif value is None:
            self.set_zero()
        else:
            raise TypeError

    def __str__(self):
        return str(unicode(self))

    def __unicode__(self):
        """Formats this duration."""
        result = unicode(self.get_string())
        if self.sign < 0:
            return u"-" + result
        else:
            return result

    def set_from_string(self, duration_str):
        if type(duration_str) in StringTypes:
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


def EncodeDateTime(value):
    """Returns the canonical lexical representation of a
    :py:class:`pyslet.iso8601.TimePoint` instance."""
    return value.get_calendar_string()


def DecodeDateTime(src):
    """Returns an :py:class:`pyslet.iso8601.TimePoint` instance."""
    try:
        return iso8601.TimePoint.from_str(src)
    except:
        return None


def EncodeDateTime(value):
    """Returns the canonical lexical representation of a
    :py:class:`pyslet.iso8601.TimePoint` instance."""
    return value.get_calendar_string()


def DecodeName(src):
    """Decodes a name from a string.  Returns the same string or raised ValueError."""
    if IsValidName(src):
        return src
    else:
        raise ValueError("Invalid Name: %s" % src)


def EncodeName(src):
    """A convenience function, returns src unchanged."""
    return src


def DecodeInteger(src):
    """Decodes an integer value from a string returning an Integer or Long
    value.

    If string is not a valid lexical representation of an integer then
    ValueError is raised."""
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


def EncodeInteger(value):
    """Encodes an integer value using the canonical lexical representation."""
    return unicode(value)


class Enumeration:

    """An abstract class designed to make generating enumeration types easier. 
    The class is not designed to be instantiated but to act as a method of
    defining constants to represent the values of an enumeration.

    The basic usage of this class is to derive a class from it with a single
    class member called 'decode' which is a mapping from canonical strings to
    simple integers.  You then call the function :py:func:`MakeEnumeration` to
    complete the declaration, after which, you can use the enumeration as if you
    had defined the constants as class members and call any of the following
    class methods to convert enumeration values to and from their string
    representations."""

    # : the default value of the enumeration or None if there is no default
    DEFAULT = None

    @classmethod
    def DecodeValue(cls, src):
        """Decodes a string returning a value in this enumeration.

        If no legal value can be decoded then ValueError is raised."""
        try:
            src = src.strip()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    def DecodeLowerValue(cls, src):
        """Decodes a string, converting it to lower case first.

        Returns a value in this enumeration.  If no legal value can be decoded
        then ValueError is raised."""
        try:
            src = src.strip().lower()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    def DecodeUpperValue(cls, src):
        """Decodes a string, converting it to upper case first.

        Returns a value in this enumeration.  If no legal value can be decoded
        then ValueError is raised."""
        try:
            src = src.strip().upper()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    def DecodeTitleValue(cls, src):
        """Decodes a string, converting it to title case first.

        Returns a value in this enumeration.  If no legal value can be decoded
        then ValueError is raised."""
        try:
            src = src.strip()
            src = src[0].upper() + src[1:].lower()
            return cls.decode[src]
        except KeyError:
            raise ValueError("Can't decode %s from %s" % (cls.__name__, src))

    @classmethod
    def DecodeValueList(cls, decoder, src):
        """Decodes a space-separated string of values using *decoder* which must
        be one of the Decode\\*Value methods of the enumeration.  The result is
        an ordered list of values (possibly containing duplicates).

        Example usage::

                fruit.DecodeValueList(fruit.DecodeLowerValue,"apples oranges, pears")
                # returns [ fruit.apples, fruit.oranges, fruit.pears ]"""
        return map(decoder, src.split())

    @classmethod
    def DecodeValueDict(cls, decoder, src):
        """Decodes a space-separated string of values using *decoder* which must
        be one of the Decode\\*Value methods of the enumeration.  The result is
        a dictionary mapping the values found as keys onto the strings used
        to represent them.  Duplicates are mapped to the first occurrence of the
        encoded value.

        Example usage::

                fruit.DecodeValueDict(fruit.DecodeLowerValue,"Apples oranges PEARS")
                # returns...
                { fruit.apples:'Apples', fruit.oranges:'oranges', fruit.pears:'PEARS' }"""
        result = {}
        for s in src.split():
            sv = decoder(s)
        if not sv in result:
            result[sv] = s
        return result

    @classmethod
    def EncodeValue(cls, value):
        """Encodes one of the enumeration constants returning a string.

        If value is None then the encoded default value is returned (if defined) or None."""
        return cls.encode.get(value, cls.encode.get(cls.DEFAULT, None))

    @classmethod
    def EncodeValueList(cls, valueList):
        """Encodes a list of enumeration constants returning a space-separated string.

        If valueList is empty then an empty string is returned."""
        return string.join(map(cls.EncodeValue, valueList), ' ')

    @classmethod
    def EncodeValueDict(cls, valueDict, sortKeys=True):
        """Encodes a dictionary of enumeration constants returning a space-separated string.

        If valueDict is empty then an empty string is returned.  Note that the
        canonical representation of each value is used.  Extending the example
        given in :py:meth:`DecodeValueDict`::

                fruit.EncodeValueDict(fruit.DecodeValueDict(fruit.DecodeLowerValue,
                        "Apples oranges PEARS"))
                # returns...
                "apples oranges pears"

        The order of the encoded values in the string is determined by the sort
        order of the enumeration constants.  This ensures that equivalent
        dictionaries are always encoded to equivalent strings.  In the above
        example::

                fruit.apples < fruit.oranges and fruit.oranges < fruit.pears

        If you have large lists then you can skip the sorting step by passing
        False for *sortKeys* to improve performance at the expense of a
        predictable encoding."""
        values = valueDict.keys()
        if sortKeys:
            values.sort()
        return cls.EncodeValueList(values)


def MakeEnumeration(e, defaultValue=None):
    """Adds convenience attributes to the class 'e'

    This function assumes that e has an attribute 'decode' that is a dictionary
    which maps strings onto enumeration values.  This function creates the reverse
    mapping called 'encode' and also defines constant attribute values that are
    equivalent to the keys of decode and can be used in code in the form e.key.

    If *defaultValue* is not None then it must be on of the strings in the
    decode dictionary.  It is then used to set the *DEFAULT* value."""
    setattr(e, 'encode', dict(zip(e.decode.values(), e.decode.keys())))
    map(lambda x: setattr(e, x, e.decode[x]), e.decode.keys())
    if defaultValue:
        setattr(e, 'DEFAULT', e.decode[defaultValue])


def MakeEnumerationAliases(e, aliases):
    """Adds *aliases* from a dictionary, declaring additional convenience attributes.

    This function assumes that :py:func:`MakeEnumeration` has already been used
    to complete the declaration of the enumeration.  The aliases are added to
    the decode dictionary but, for obvious reasons, not to the encode
    dictionary."""
    for alias, key in aliases.items():
        e.decode[alias] = e.decode[key]
    map(lambda x: setattr(e, x, e.decode[x]), aliases.keys())


def MakeLowerAliases(e):
    """Adds *aliases* by converting all keys to lower case.

    Assumes that :py:func:`MakeEnumeration` has already been used to complete
    the declaration of the enumeration.  You must call this function to complete
    the declaration before relying on calls to
    :py:meth:`Enumeration.DecodeLowerValue`."""
    for key in e.decode.keys():
        alias = key.lower()
        if not alias in e.decode:
            # Declare this alias
            e.decode[alias] = e.decode[key]
            setattr(e, alias, e.decode[key])


def WhiteSpaceReplace(value):
    """Replaces tab, line feed and carriage return with space."""
    output = []
    for c in value:
        if c in u"\x09\x0A\x0D":
            output.append(unichr(0x20))
        else:
            output.append(c)
    return string.join(output, '')


def WhiteSpaceCollapse(value):
    """Replaces all runs of white space with a single space. Also removes
    leading and trailing white space."""
    output = []
    gotSpace = False
    for c in value:
        if c in u"\x09\x0A\x0D\x20":
            gotSpace = True
        else:
            if output and gotSpace:
                output.append(unichr(0x20))
                gotSpace = False
            output.append(c)
    return string.join(output, '')


class RegularExpression:

    """Models a regular expression as defined by XML schema.

    Regular expressions are constructed from unicode source strings. Internally
    they are parsed and converted to Python regular expressions to speed up
    matching.  Warning: because the XML schema expression language contains
    concepts not supported by Python the python regular expression may not be
    very readable."""

    def __init__(self, src):
        p = RegularExpressionParser(src)
        pyre = p.ParseRegExp()
        self.p = compile(pyre)  # : the compiled python regular expression
        self.src = src			#: the original source string

    def __str__(self):
        return self.src

    def __repr__(self):
        return "RegularExpression(%s)" % repr(self.src)

    def match(self, target):
        """A convenience function, returns True if the expression matches *target*."""
        m = self.p.match(target)
        if m is None or m.end(0) < len(target):
            # print "No match"
            return 0
        else:
            # print "match"
            return 1


class RegularExpressionError(Exception):
    pass


sClass = CharClass(u'\x09', u'\x0A', u'\x0D', u' ')
SClass = CharClass(sClass)
SClass.Negate()
iClass = CharClass(LetterCharClass, u'_', u':')
IClass = CharClass(iClass)
IClass.Negate()
CClass = CharClass(NameCharClass)
CClass.Negate()
dClass = CharClass.UCDCategory('Nd')
DClass = CharClass(dClass)
DClass.Negate()
WClass = CharClass(CharClass.UCDCategory(
    'P'), CharClass.UCDCategory('Z'), CharClass.UCDCategory('C'))
wClass = CharClass(WClass)
wClass.Negate()


class RegularExpressionParser(BasicParser):

    """A custom parser for XML schema regular expressions.

    The parser is initialised from a source string, the string to be parsed."""

    def _REEscape(self, c=None):
        if c is None:
            c == self.the_char
        if c in u".^$*+?{}\\[]|()":
            return "\\" + c
        else:
            return c

    def ParseRegularExpression(self):
        return self.src

    def ParseRegExp(self):
        """Returns a unicode string representing the regular expression."""
        result = []
        while True:
            # expression ends at the end of the string or at a closing bracket
            result.append(self.ParseBranch())
            if self.the_char == u"|":
                self.next_char()
                result.append(u"|")
                continue
            else:
                break
        return string.join(result, '')

    def ParseBranch(self):
        """Returns a unicode string representing this piece as a python regular expression."""
        result = []
        while self.IsChar() or self.MatchOne(u".\\[("):
            result.append(self.ParsePiece())
        return string.join(result, '')

    def ParsePiece(self):
        result = self.ParseAtom()
        if self.MatchOne("?*+{"):
            n, m = self.ParseQuantifier()
            if n == 0:
                if m is None:
                    return result + u"*"
                elif m == 0:
                    return u""
                elif m == 1:
                    return result + u"?"
                else:
                    return "%s{,%i}" % (result, m)
            elif n == 1:
                if m is None:
                    return result + u"+"
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

    def ParseQuantifier(self):
        """Returns a tuple of n,m.

        Symbolic values are expanded to the appropriate pair.  The second
        value may be None indicating unbounded."""
        if self.the_char == u"?":
            self.next_char()
            return 0, 1
        elif self.the_char == u"*":
            self.next_char()
            return 0, None
        elif self.the_char == u"+":
            self.next_char()
            return 1, None
        elif self.the_char == u"{":
            self.next_char()
            result = self.ParseQuantity()
            if self.the_char == u"}":
                self.next_char()
                return result
            else:
                raise RegularExpressionError("Expected } at [%i]" % self.pos)
        else:
            raise RegularExpressionError(
                "Expected quantifier at [%i]" % self.pos)

    def ParseQuantity(self):
        """Returns a tuple of n,m even if an exact quantity is given.

        In other words, the exact quantity 'n' returns n,n.  The second
        value may be None indicated unbounded."""
        n = self.ParseQuantExact()
        m = None
        if self.the_char == u",":
            self.next_char()
            if self.MatchOne(u"0123456789"):
                m = self.ParseQuantExact()
                if n > m:
                    raise RegularExpressionError(
                        "Illegal quantity: {%i,%i}" % (n, m))
        else:
            m = n
        return n, m

    def ParseQuantExact(self):
        """Returns an integer."""
        result = 0
        nDigits = 0
        while self.MatchOne(u"0123456789"):
            result = result * 10 + ord(self.the_char) - 0x30
            self.next_char()
            nDigits += 1
        if nDigits == 0:
            raise RegularExpressionError("Expected digit at [%i]" % self.pos)
        return result

    def ParseAtom(self):
        """Returns a unicode string representing this atom as a python regular expression."""
        if self.IsChar():
            result = self._REEscape(self.the_char)
            self.next_char()
        elif self.the_char == "(":
            # a regular expression
            self.next_char()
            result = "(%s)" % self.ParseRegExp()
            if self.the_char != ")":
                raise RegularExpressionError("Expected ) at [%i]" % self.pos)
            self.next_char()
        else:
            cClass = self.ParseCharClass()
            result = unicode(cClass)
        return result

    def IsChar(self, c=None):
        """The definition of this function is designed to be conservative with
        respect to the specification, which is clearly in error around
        production [10] as the prose and the BNF do not match.  It appears that
        | was intended to be excluded in the prose but has been omitted, the
        reverse being true for the curly-brackets."""
        if c is None:
            c = self.the_char
        if c is None or c in ".\\?*+{}()[]|":
            return False
        else:
            return True

    def ParseCharClass(self):
        """Returns a CharClass instance representing this class."""
        if self.the_char == u"[":
            return self.ParseCharClassExpr()
        elif self.the_char == u"\\":
            return self.ParseCharClassEsc()
        elif self.the_char == u".":
            return self.ParseWildcardEsc()
        else:
            raise RegularExpressionError(
                "Expected [, \\ or . at [%i]" % self.pos)

    def ParseCharClassExpr(self):
        """Returns a CharClass instance representing this class expression."""
        if self.the_char == "[":
            self.next_char()
            cClass = self.ParseCharGroup()
            if self.the_char == "]":
                self.next_char()
                return cClass
            else:
                raise RegularExpressionError("Expected ] at [%i]" % self.pos)
        else:
            raise RegularExpressionError("Expected [ at [%i]" % self.pos)

    def ParseCharGroup(self):
        """Returns a CharClass representing this group.  This method also
        handles the case of a class subtraction directly to reduce the need for
        look-ahead.  If you specifically want to parse a subtraction you can do
        this with :py:meth:`ParseCharClassSub`."""
        if self.the_char == u"^":
            cClass = self.ParseNegCharGroup()
        else:
            cClass = self.ParsePosCharGroup()
        if self.the_char == u"-":
            self.next_char()
            subClass = self.ParseCharClassExpr()
            cClass.SubtractClass(subClass)
        return cClass

    def ParsePosCharGroup(self):
        """Returns a CharClass representing a positive range"""
        cClass = CharClass()
        nRanges = 0
        while True:
            savepos = self.pos
            if self.the_char == u"-" and nRanges:
                # This had better be the last hyphen in the posCharGroup
                if self.match(u"-["):
                    # a subtraction
                    break
                elif self.match(u"-]") or self.match(u"--["):
                    cClass.AddChar(u"-")
                    self.next_char()
                    break
                else:
                    # this is all wrong
                    raise RegularExpressionError(
                        "hyphen must be first or last character in posCharGroup [%i]" % self.pos)
            try:
                cClass.AddClass(self.ParseCharRange())
                nRanges += 1
                continue
            except RegularExpressionError:
                self.setpos(savepos)
                pass
            try:
                cClass.AddClass(self.ParseCharClassEsc())
                nRanges += 1
                continue
            except RegularExpressionError:
                if nRanges:
                    self.setpos(savepos)
                    break
                else:
                    # We expected either a charRange or a charClassEsc
                    raise RegularExpressionError(
                        "Expected charRange or charClassEsc at [%i]" % self.pos)
        return cClass

    def ParseNegCharGroup(self):
        """Returns a CharClass representing this range."""
        if self.the_char == u"^":
            # we have a negative range
            self.next_char()
            cClass = self.ParsePosCharGroup()
            cClass.Negate()
            return cClass
        else:
            raise RegularExpressionError(
                "Expected negCharGroup at [%i]" % self.pos)

    def ParseCharClassSub(self):
        """Returns a CharClass representing this range - this method is not
        normally used by the parser as in present for completeness.  See
        :py:meth:`ParseCharGroup`."""
        if self.the_char == u"^":
            cClass = self.ParseNegCharGroup()
        else:
            cClass = self.ParsePosCharGroup()
        if self.the_char == u"-":
            self.next_char()
            subClass = self.ParseCharClassExpr()
            cClass.SubtractClass(subClass)
            return cClass
        else:
            raise RegularExpressionError("Expected - at [%i]" % self.pos)

    def ParseCharRange(self):
        """Returns a CharClass representing this range."""
        savepos = self.pos
        try:
            cClass = self.ParseSERange()
        except RegularExpressionError:
            self.setpos(savepos)
            if self.IsXmlCharIncDash():
                cClass = CharClass(self.the_char)
                self.next_char()
            else:
                raise
        return cClass

    def ParseSERange(self):
        """Returns a CharClass representing this range."""
        s = self.ParseCharOrEsc()
        if self.the_char == u"-":
            self.next_char()
        else:
            raise RegularExpressionError(
                "Expected '-' in seRange [%i]" % self.pos)
        e = self.ParseCharOrEsc()
        if ord(s) > ord(e):
            raise RegularExpressionError(
                "Empty SERange: %s-%s" % (repr(s), repr(e)))
        return CharClass((s, e))

    def ParseCharOrEsc(self):
        """Returns a single unicode character."""
        if self.IsXmlChar():
            result = self.the_char
            self.next_char()
            return result
        else:
            return self.ParseSingleCharEsc()

    def IsXmlChar(self, c=None):
        if c is None:
            c = self.the_char
        return c is not None and c not in "\\-[]"

    def IsXmlCharIncDash(self, c=None):
        if c is None:
            c = self.the_char
        return c is not None and c not in "\\[]"

    def ParseCharClassEsc(self):
        """Returns a CharClass instance representing one of the escape sequences."""
        if self.match(u"\\p"):
            cClass = self.ParseCatEsc()
        elif self.match(u"\\P"):
            cClass = self.ParseComplEsc()
        elif self.the_char == u"\\":
            try:
                savepos = self.pos
                cClass = self.ParseMultiCharEsc()
            except RegularExpressionError:
                self.setpos(savepos)
                cClass = CharClass(self.ParseSingleCharEsc())
        else:
            raise RegularExpressionError(
                "Expected charClassEsc at [%i]" % self.pos)
        return cClass

    SingleCharEscapes = {
        u'n': unichr(0x0A),
        u'r': unichr(0x0D),
        u't': unichr(0x09),
        u'\\': u'\\',
        u'|': u'|',
        u'.': u'.',
        u'-': u'-',
        u'^': u'^',
        u'?': u'?',
        u'*': u'*',
        u'+': u'+',
        u'{': u'{',
        u'}': u'}',
        u'(': u'(',
        u')': u')',
        u'[': u'[',
        u']': u']'
    }

    def ParseSingleCharEsc(self):
        """Returns a single unicode character parsed from a single char escape."""
        if self.the_char == u"\\":
            self.next_char()
            if self.the_char in self.SingleCharEscapes:
                result = self.SingleCharEscapes[self.the_char]
                self.next_char()
                return result
        raise RegularExpressionError(
            "Expected single character escape at [%i]" % self.pos)

    def ParseCatEsc(self):
        """Returns a CharClass, parsing a category escape."""
        if self.match("\\p{"):
            self.setpos(self.pos + 3)
            cClass = self.ParseCharProp()
            if self.the_char == '}':
                self.next_char()
                return cClass
        raise RegularExpressionError("Expected \\p{...} at [%i]" % self.pos)

    def ParseComplEsc(self):
        """Returns a CharClass, parsing the complement of a category escape."""
        if self.match("\\P{"):
            self.setpos(self.pos + 3)
            cClass = CharClass(self.ParseCharProp())
            if self.the_char == '}':
                self.next_char()
                cClass.Negate()
                return cClass
        raise RegularExpressionError("Expected \\P{...} at [%i]" % self.pos)

    def ParseCharProp(self):
        """Returns a CharClass, parsing an IsCategory or IsBlock."""
        savepos = self.pos
        try:
            cClass = self.ParseIsCategory()
        except RegularExpressionError:
            self.setpos(savepos)
            cClass = self.ParseIsBlock()
        return cClass

    Categories = {
        u"L": True,
        u"Lu": True,
        u"Ll": True,
        u"Lt": True,
        u"Lm": True,
        u"Lo": True,
        u"M": True,
        u"Mn": True,
        u"Mc": True,
        u"Me": True,
        u"N": True,
        u"Nd": True,
        u"Nl": True,
        u"No": True,
        u"P": True,
        u"Pc": True,
        u"Pd": True,
        u"Ps": True,
        u"Pe": True,
        u"Pi": True,
        u"Pf": True,
        u"Po": True,
        u"Z": True,
        u"Zs": True,
        u"Zl": True,
        u"Zp": True,
        u"S": True,
        u"Sm": True,
        u"Sc": True,
        u"Sk": True,
        u"So": True,
        u"C": True,
        u"Cc": True,
        u"Cf": True,
        u"Co": True,
        u"Cn": True
    }

    def ParseIsCategory(self):
        """Returns a CharClass corresponding to one of the character categories
        or raises an error."""
        if self.the_char in self.Categories:
            cat = self.the_char
            self.next_char()
            if self.the_char is not None and (cat + self.the_char) in self.Categories:
                cat = cat + self.the_char
                self.next_char()
            return CharClass.UCDCategory(cat)
        else:
            raise RegularExpressionError(
                "Expected category name [%i]" % self.pos)

    IsBlockClass = CharClass(
        (u'a', u'z'),
        (u'A', u'Z'),
        (u'0', u'9'),
        u'-')

    def ParseIsBlock(self):
        """Returns a CharClass corresponding to one of the Unicode blocks."""
        block = []
        while self.IsBlockClass.Test(self.the_char):
            block.append(self.the_char)
            self.next_char()
        block = string.join(block, '')
        if block.startswith("Is"):
            try:
                return CharClass.UCDBlock(block[2:])
            except KeyError:
                raise RegularExpressionError(
                    "Invalid IsBlock name: %s" % block[2:])
        else:
            raise RegularExpressionError("Expected IsBlock [%i]" % self.pos)

    MultiCharEscapes = {
        's': sClass,
        'S': SClass,
        'i': iClass,
        'I': IClass,
        'c': NameCharClass,
        'C': CClass,
        'd': dClass,
        'D': DClass,
        'w': wClass,
        'W': WClass
    }

    def ParseMultiCharEsc(self):
        """Returns a CharClass corresponding to one of the multichar escapes, if parsed."""
        if self.the_char == u"\\":
            self.next_char()
            try:
                result = self.MultiCharEscapes[self.the_char]
                self.next_char()
                return result
            except KeyError:
                # unknown escape
                raise RegularExpressionError(
                    "Unknown multichar escape at [%i], \\%s" % (self.pos, repr(self.the_char)))
        else:
            raise RegularExpressionError("Expected '\\' at [%i]" % self.pos)

    DotClass = CharClass(
        (unichr(0), unichr(9)),
        (unichr(11), unichr(12)),
        (unichr(14), unichr(maxunicode)))

    def ParseWildcardEsc(self):
        """Returns a CharClass corresponding to the wildcard '.' character if parsed."""
        if self.the_char == u".":
            self.next_char()
            return self.DotClass
        else:
            raise RegularExpressionError("Expected '.' at [%i]" % self.pos)
