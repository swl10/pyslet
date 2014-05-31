#! /usr/bin/env python
"""This module implements the CSDL specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541211.aspx
http://msdn.microsoft.com/en-us/library/dd541474(v=prot.10)"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.rfc2396 as uri
import pyslet.rfc2616 as http
import pyslet.xsdatatypes20041028 as xsi
from pyslet.vfs import OSFilePath
import pyslet.iso8601 as iso8601
import logging

import string
import itertools
import StringIO
import sys
import copy
import decimal
import hashlib
import uuid
import math
import collections
import warnings
import pickle
import datetime
from types import BooleanType, FloatType, StringTypes, StringType, UnicodeType, BooleanType, IntType, LongType, TupleType, DictType


#: Namespace to use for CSDL elements
EDM_NAMESPACE = "http://schemas.microsoft.com/ado/2009/11/edm"
EDM_NAMESPACE_ALIASES = [
    "http://schemas.microsoft.com/ado/2006/04/edm",     #: CSDL Schema 1.0
    "http://schemas.microsoft.com/ado/2007/05/edm",     #: CSDL Schema 1.1
    "http://schemas.microsoft.com/ado/2008/09/edm"]     #: CSDL Schema 2.0

NAMESPACE_ALIASES = {
    EDM_NAMESPACE: EDM_NAMESPACE_ALIASES
}


SimpleIdentifierRE = xsi.RegularExpression(
    r"[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")


def ValidateSimpleIdentifier(identifier):
    """Validates a simple identifier, returning the identifier unchanged or
    raising ValueError."""
    if SimpleIdentifierRE.Match(identifier):
        return identifier
    else:
        raise ValueError(
            "Can't parse SimpleIdentifier from :%s" % repr(identifier))


class EDMError(Exception):

    """General exception for all CSDL model errors."""
    pass


class DuplicateName(EDMError):

    """Raised by :py:class:`NameTableMixin` when attempting to declare a name in
    a context where the name is already declared.

    This might be raised if your metadata document incorrectly defines
    two objects with the same name in the same scope, for example"""
    pass


class IncompatibleNames(DuplicateName):

    """A special type of :py:class:`DuplicateName` exception raised by
    :py:class:`NameTableMixin` when attempting to declare a name which
    might hide, or be hidden by, another name already declared.

    CSDL's definition of SimpleIdentifier allows '.' to be used in names but
    also uses it for qualifying names.  As a result, it is possible to define a
    scope with a name like "My.Scope" which precludes the later definition of a
    scope called simply "My" (and vice versa)."""
    pass


class ModelIncomplete(EDMError):

    """Raised when a model element has a missing reference.

    For example, an
    :py:class:`EntitySet` that is bound to an undeclared
    ::py:class:`EntityType`."""
    pass


class ModelConstraintError(EDMError):

    """Raised when an issue in the model other than completeness
    prevents an action being performed.

    For example, an entity type that is dependent on two unbound
    principals (so can never be inserted)."""


class NonExistentEntity(EDMError):

    """Raised when attempting to perform a restricted operation on an
    entity that doesn't exist yet.  For example, getting the value of a
    navigation property."""
    pass


class EntityExists(EDMError):

    """Raised when attempting to perform a restricted operation on an
    entity that already exists.  For example, inserting it into the base
    collection."""
    pass


class ConstraintError(EDMError):

    """General error raised when a constraint has been violated."""
    pass


class ConcurrencyError(ConstraintError):

    """Raised when attempting to perform an update on an entity and a violation
    of a concurrency control constraint is encountered."""
    pass


class NavigationError(ConstraintError):

    """Raised when attempting to perform an operation on an entity and a
    violation of a navigation property's relationship is encountered.
    For example, adding multiple links when only one is allowed or
    failing to add a link when one is required."""
    pass

NavigationConstraintError = NavigationError


class DictionaryLike(object):

    """An abstract class for behaving like a dictionary.

    Derived classes must override :py:meth:`__iter__` and :py:meth:`__getitem__`
    and if the dictionary is writable :py:meth:`__setitem__` and probably
    :py:meth:`__delitem__` too.  These methods all raise NotImplementedError by
    default.

    Dervied classes should also override :py:meth:`__len__` and
    :py:meth:`clear` as the default implementations are inefficient.

    A note on thread safety.  Unlike native Python dictionaries,
    DictionaryLike objects can not be treated as thread safe for
    updates.  The implementations of the read-only methods (including
    the iterators) are designed to be thread safe so, once populated,
    they can be safely shared.  Derived classes should honour this
    contract when implementing :py:meth:`__iter__`,
    :py:meth:`__getitem__` and :py:meth:`__len__` or clearly document
    that the object is not thread-safe at all.

    Finally, one other difference worth noting is touched on in a comment
    from the following question on Stack Overflow:
    http://stackoverflow.com/questions/3358770/python-dictionary-is-thread-safe

    This question is about whether a dictionary can be modified during
    iteration.  Although not typically a thread-safety issue the commenter
    says:

            I think they are related. What if one thread iterates and the
            other modifies the dict?

    To recap, native Python dictionaries limit the modifications you can make
    during iteration, quoting from the docs:

            The dictionary p should not be mutated during iteration. It is
            safe (since Python 2.1) to modify the values of the keys as you
            iterate over the dictionary, but only so long as the set of keys
            does not change

    You should treat DictionaryLike objects with the same respect but
    the behaviour is not defined at this abstract class level and will
    vary depending on the implementation.  Derived classes are only
    dictionary-like, they are not actually Python dictionaries!"""

    def __getitem__(self, key):
        """Implements self[key]

        This method must be overridden to make a concrete implementation"""
        raise NotImplementedError

    def __setitem__(self, key, value):
        """Implements assignment to self[key]

        This method must be overridden if you want your dictionary-like
        object to be writeable."""
        raise NotImplementedError

    def __delitem__(self, key):
        """Implements del self[key]

        This method should be overridden if you want your
        dictionary-like object to be writeable."""
        raise NotImplementedError

    def __iter__(self):
        """Returns an object that implements the iterable protocol on the keys

        This method must be overridden to make a concrete implementation"""
        raise NotImplementedError

    def __len__(self):
        """Implements len(self)

        The default implementation simply counts the keys returned by __iter__
        and should be overridden with a more efficient implementation if
        available."""
        count = 0
        for k in self:
            count += 1
        return count

    def __contains__(self, key):
        """Implements: key in self

        The default implementation uses __getitem__ and returns False if it
        raises a KeyError."""
        try:
            e = self[key]
            return True
        except KeyError:
            return False

    def iterkeys(self):
        """Returns an iterable of the keys, simple calls __iter__"""
        return self.__iter__()

    def itervalues(self):
        """Returns an iterable of the values.

        The default implementation is a generator function that iterates
        over the keys and uses __getitem__ to yield each value."""
        for k in self:
            yield self[k]

    def keys(self):
        """Returns a list of keys.

        This is a copy of the keys in no specific order.  Modifications to this
        list do not affect the object.  The default implementation uses
        :py:meth:`iterkeys`"""
        return list(self.iterkeys())

    def values(self):
        """Returns a list of values.

        This is a copy of the values in no specific order.  Modifications to
        this list do not affect the object.  The default implementation uses
        :py:meth:`itervalues`."""
        return list(self.itervalues())

    def iteritems(self):
        """Returns an iterable of the key,value pairs.

        The default implementation is a generator function that uses
        :py:meth:`__iter__` and __getitem__ to yield the pairs."""
        for k in self:
            yield k, self[k]

    def items(self):
        """Returns a list of key,value pair tuples.

        This is a copy of the items in no specific order.  Modifications to this
        list do not affect the object.  The default implementation uses
        :py:class:`iteritems`."""
        return list(self.iteritems())

    def has_key(self, key):
        """Equivalent to: key in self"""
        return key in self

    def get(self, key, default=None):
        """Equivalent to: self[key] if key in self else default.

        Implemented using __getitem__"""
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, value=None):
        """Equivalent to: self[key] if key in self else value; ensuring
        self[key]=value

        Implemented using __getitem__ and __setitem__."""
        try:
            e = self[key]
            return e
        except KeyError:
            self[key] = value
            return value

    def pop(self, key, value=None):
        """Equivalent to: self[key] if key in self else value; ensuring key not
        in self.

        Implemented using __getitem__ and __delitem__."""
        try:
            e = self[key]
            del self[key]
            return e
        except KeyError:
            return value

    def clear(self):
        """Removes all items from the object.

        The default implementation uses :py:meth:`keys` and deletes the items
        one-by-one with __delitem__.  It does this to avoid deleting objects
        while iterating as the results are generally undefined.  A more
        efficient implementation is recommended."""
        for k in self.keys():
            try:
                del self[k]
            except KeyError:
                pass

    def popitem(self):
        """Equivalent to: self[key] for some random key; removing key.

        This is a rather odd implementation but to avoid iterating over
        the whole object we create an iterator with __iter__, use
        __getitem__ once and then discard it.  If an object is found we
        use __delitem__ to delete it, otherwise KeyError is raised."""
        value = None
        for k in self:
            value = self[k]
            break
        if value is None:
            raise KeyError
        else:
            del self[k]
            return k, value

    def bigclear(self):
        """Removes all the items from the object (alternative for large
        dictionary-like objects).

        This is an alternative implementation more suited to objects with very
        large numbers of keys.  It uses :py:meth:`popitem` repeatedly until
        KeyError is raised.  The downside is that popitem creates (and discards)
        one iterator object for each item it removes.  The upside is that we
        never load the list of keys into memory."""
        try:
            while True:
                self.popitem()
        except KeyError:
            pass

    def copy(self):
        """Makes a shallow copy of this object.

        This method must be overridden if you want your dictionary-like
        object to support the copy operation."""
        raise NotImplementedError

    def update(self, items):
        """Iterates through *items* using __setitem__ to add them to the
        set."""
        for key, value in items:
            self[key] = value


class NameTableMixin(DictionaryLike):

    """A mix-in class to help other objects become named scopes.

    Using this mix-in the class behaves like a read-only named
    dictionary with string keys and object values.  If the dictionary
    contains a value that is itself a NameTableMixin then keys can be
    compounded to look-up items in sub-scopes.

    For example, if the name table contains a value with key "X" that is
    itself a name table containing a value with key "Y" then both "X"
    and "X.Y" are valid keys, the latter performing a 'deep lookup' in
    the nested scope."""

    def __init__(self):
        #: the name of this name table (in the context of its parent)
        self.name = ""
        self.nameTable = {}     #: a dictionary mapping names to child objects

    def __getitem__(self, key):
        """Looks up *key* in :py:attr:`nameTable` and, if not found, in
        each child scope with a name that is a valid scope prefix of
        key.  For example, if key is "My.Scope.Name" then a child scope
        with name "My.Scope" would be searched for "Name" or a child
        scope with name "My" would be searched for "Scope.Name"."""
        result = self.nameTable.get(key, None)
        if result is None:
            scope, key = self._SplitKey(key)
            if scope is not None:
                return scope[key]
            raise KeyError("%s not declared in scope %s" % (key, self.name))
        else:
            return result

    def __iter__(self):
        """Yields all keys defined in this scope and all compounded keys
        from nested scopes.  For example, a child scope with name
        "My.Scope" which itself has a child "Name" would generate two
        keys: "My.Scope" and "My.Scope.Name"."""
        for key in self.nameTable:
            yield key
        for value in self.nameTable.itervalues():
            if isinstance(value, NameTableMixin):
                for key in value:
                    yield value.name + "." + key

    def __len__(self):
        """Returns the number of keys in this scope including all
        compounded keys from nested scopes."""
        result = len(self.nameTable)
        for value in self.nameTable.itervalues():
            if isinstance(value, NameTableMixim):
                result = result + len(value)

    def _SplitKey(self, key):
        sKey = key.split(".")
        pathLen = 1
        while pathLen < len(sKey):
            scope = self.nameTable.get(string.join(sKey[:pathLen], "."), None)
            if isinstance(scope, NameTableMixin):
                return scope, string.join(sKey[pathLen:], ".")
            pathLen += 1
        return None, key

    def Declare(self, value):
        """Declares a value in this named scope.

        *value* must have a name attribute which is used to declare it
        in the scope; duplicate keys are not allowed and will raise
        :py:class:`DuplicateKey`.

        Values are always declared in the top-level scope, even if they
        contain the compounding character '.', however, you cannot
        declare "X" if you have already declared "X.Y" and vice versa."""
        if value.name in self.nameTable:
            raise DuplicateName(
                "%s already declared in scope %s" % (value.name, self.name))
        prefix = value.name + "."
        for key in self.nameTable:
            if key.startswith(prefix) or value.name.startswith(key + "."):
                # Can't declare "X.Y" if "X.Y.Z" exists already and
                # Can't declare "X.Y.Z" if "X.Y" exists already
                raise IncompatibleNames(
                    "Can't declare %s; %s already declared in scope %s" %
                    (value.name, key, self.name))
        self.nameTable[value.name] = value

    def Undeclare(self, value):
        """Removes a value from the named scope.

        Values can only be removed from the top-level scope."""
        if value.name in self.nameTable:
            del self.nameTable[value.name]
        else:
            raise KeyError("%s not declared in scope %s" %
                           (value.name, self.name))


class SimpleType(xsi.Enumeration):

    """SimpleType defines constants for the core data types defined by CSDL
    ::

            SimpleType.Boolean
            SimpleType.DEFAULT == None

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`

    The canonical names for these constants uses the Edm prefix, for
    example, "Edm.String".  As a result, the class has attributes of the form
    "SimpleType.Edm.Binary" which are inaccessible to python unless
    getattr is used.  To workaround this problem (and because the Edm.
    prefix seems to be optional) we also define aliases without the Edm.
    prefix. As a result you can use, e.g., SimpleType.Int32 as the symbolic
    representation in code but the following are all True::

            SimpleType.DecodeValue(u"Edm.Int32")==SimpleType.Int32
            SimpleType.DecodeValue(u"Int32")==SimpleType.Int32
            SimpleType.EncodeValue(SimpleType.Int32)==u"Edm.Int32"  """
    decode = {
        'Edm.Binary': 1,
        'Edm.Boolean': 2,
        'Edm.Byte': 3,
        'Edm.DateTime': 4,
        'Edm.DateTimeOffset': 5,
        'Edm.Time': 6,
        'Edm.Decimal': 7,
        'Edm.Double': 8,
        'Edm.Single': 9,
        'Edm.Guid': 10,
        'Edm.Int16': 11,
        'Edm.Int32': 12,
        'Edm.Int64': 13,
        'Edm.String': 14,
        'Edm.SByte': 15
    }

    PythonType = {}
    """A python dictionary that maps a type code (defined by the types
    module) to a constant from this class indicating a safe
    representation in the EDM.  For example::
    
        SimpleType.PythonType[types.IntType]==SimpleType.Int64"""

#   @classmethod
#   def CoerceValue(cls,typeCode,value):
#       """Takes one of the type code constants and a python native value and returns the
#       value coerced to the best python value type for this type code."""
#       if typeCode==cls.Binary:
#           return str(value)
#       elif typeCode==cls.Boolean:
#           return bool(value)
#       elif typeCode in (cls.Byte,cls.Int16,cls.Int32,cls.SByte):
#           return int(value)
#       elif typeCode in (cls.DateTime,cls.DateTimeOffset):
#           if isinstance(value,iso8601.TimePoint):
#               return value
#           elif type(value) in StringTypes:
#               return iso8601.TimePoint.FromString(value)
#           else:
#               raise ValueError("Coercion to TimePoint failed: %s"%repr(value))
#       elif typeCode==cls.Decimal:
#           return decimal.Decimal(value)
#       elif typeCode in (cls.Double,cls.Single):
#           return float(value)
#       elif typeCode==cls.Guid:
#           if isinstance(value,uuid.UUID):
#               return value
#           else:
#               return uuid.UUID(value)
#       elif typeCode==cls.String:
#           return unicode(value)
#       elif typeCode==cls.Time:
#           raise "TODO"
#       else:
#           raise ValueError(typeCode)

xsi.MakeEnumeration(SimpleType)
xsi.MakeEnumerationAliases(SimpleType, {
    'Binary': 'Edm.Binary',
    'Boolean': 'Edm.Boolean',
    'Byte': 'Edm.Byte',
    'DateTime': 'Edm.DateTime',
    'Decimal': 'Edm.Decimal',
    'Double': 'Edm.Double',
    'Single': 'Edm.Single',
    'Guid': 'Edm.Guid',
    'Int16': 'Edm.Int16',
    'Int32': 'Edm.Int32',
    'Int64': 'Edm.Int64',
    'SByte': 'Edm.SByte',
    'String': 'Edm.String',
    'Time': 'Edm.Time',
    'DateTimeOffset': 'Edm.DateTimeOffset'})
xsi.MakeLowerAliases(SimpleType)

SimpleType.PythonType = {
    BooleanType: SimpleType.Boolean,
    FloatType: SimpleType.Double,
    IntType: SimpleType.Int64,
    LongType: SimpleType.Decimal,
    StringType: SimpleType.String,
    UnicodeType: SimpleType.String}


Numeric = collections.namedtuple(
    'Numeric', "sign lDigits rDigits eSign eDigits")


class Parser(xsi.BasicParser):

    """A CSDL-specific parser, mainly for decoding literal values of
    simple types.

    The individual parsing methods may raise ValueError in cases where
    parsed value has a value that is out of range."""

    def ParseBinaryLiteral(self):
        """Parses a binary literal, returning a binary string"""
        #   binaryLiteral = hexDigPair
        #   hexDigPair = 2*HEXDIG [hexDigPair]"""
        output = []
        hexStr = self.ParseHexDigits(0)
        if hexStr is None:
            return ''
        if len(hexStr) % 2:
            raise ValueError(
                "Trailing nibble in binary literal: '%s'" % hexStr[-1])
        i = 0
        while i < len(hexStr):
            output.append(chr(int(hexStr[i:i + 2], 16)))
            i = i + 2
        return string.join(output, '')

    def ParseBooleanLiteral(self):
        """Parses a boolean literal returning True, False or None if no boolean
        literal was found."""
        if self.ParseInsensitive("true"):
            return True
        elif self.ParseInsensitive("false"):
            return False
        else:
            return None

    def ParseByteLiteral(self):
        """Parses a byteLiteral, returning a python integer.

        We are generous in what we accept, ignoring leading zeros.  Values
        outside the range for byte return None."""
        return self.ParseInteger(0, 255)

    def ParseDateTimeLiteral(self):
        """Parses a DateTime literal, returning a :py:class:`pyslet.iso8601.TimePoint` instance.

        Returns None if no DateTime literal can be parsed.  This is a
        generous way of parsing iso8601-like values, it accepts omitted
        zeros in the date, such as 4-7-2001."""
        savePos = self.pos
        try:
            production = "dateTimeLiteral"
            year = int(self.RequireProduction(self.ParseDigits(4, 4), "year"))
            self.Require("-",)
            month = self.RequireProduction(self.ParseInteger(1, 12), "month")
            self.Require("-", production)
            day = self.RequireProduction(self.ParseInteger(1, 31, 2), "day")
            self.Require("T", production)
            hour = self.RequireProduction(self.ParseInteger(0, 24), "hour")
            self.Require(":", production)
            minute = self.RequireProduction(
                self.ParseInteger(0, 60, 2), "minute")
            if self.Parse(":"):
                second = self.RequireProduction(
                    self.ParseInteger(0, 60, 2), "second")
                if self.Parse("."):
                    nano = self.ParseDigits(1, 7)
                    second += float("0." + nano)
            else:
                second = 0
        except ValueError:
            self.SetPos(savePos)
            return None
        try:
            value = iso8601.TimePoint(
                date=iso8601.Date(
                    century=year // 100, year=year %
                    100, month=month, day=day), time=iso8601.Time(
                    hour=hour, minute=minute, second=second, zDirection=None))
        except iso8601.DateTimeError as e:
            raise ValueError(str(e))
        return value

    def ParseGuidLiteral(self):
        """Parses a Guid literal, returning a UUID instance from the
        uuid module.

        Returns None if no Guid can be parsed."""
        savePos = self.pos
        try:
            production = "guidLiteral"
            # dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents
            # [A-Fa-f0-9]
            guid = []
            guid.append(
                self.RequireProduction(self.ParseHexDigits(8, 8), production))
            self.RequireProduction(self.Parse('-'))
            guid.append(
                self.RequireProduction(self.ParseHexDigits(4, 4), production))
            self.RequireProduction(self.Parse('-'))
            guid.append(
                self.RequireProduction(self.ParseHexDigits(4, 4), production))
            self.RequireProduction(self.Parse('-'))
            guid.append(
                self.RequireProduction(self.ParseHexDigits(4, 4), production))
            self.RequireProduction(self.Parse('-'))
            guid.append(
                self.RequireProduction(
                    self.ParseHexDigits(
                        12,
                        12),
                    production))
            value = uuid.UUID(string.join(guid, ''))
        except ValueError:
            self.SetPos(savePos)
            return None
        return value

    def ParseNumericLiteral(self):
        """Parses a numeric literal returning a named tuple of strings::

                ( sign, lDigits, rDigits, expSign, eDigits )

        An empty string indicates a component that was not present
        except that rDigits will be None if no decimal point was
        present.  Likewise, eDigits may be None indicating that no
        exponent was found.

        Although both lDigits and rDigits can be empty they will never
        *both* be empty strings. If there are no digits present then the
        method returns None, rather than a tuple.  Therefore, forms like
        "E+3" are not treated as being numeric literals whereas, perhaps
        oddly, 1E+ is parsed as a numeric literal (even though it will
        raise ValueError later when setting any of the numeric value
        types).

        Representations of infinity and not-a-number result in lDigits
        being set to 'inf' and 'nan' respectively.  They always result
        in rDigits and eDigits being None."""
        savePos = self.pos
        eSign = ''
        rDigits = eDigits = None
        sign = self.ParseOne("-")
        if sign is None:
            sign = ""
        if self.ParseInsensitive("inf"):
            lDigits = "inf"
        elif self.ParseInsensitive("nan"):
            lDigits = "nan"
        else:
            lDigits = self.ParseDigits(0)
            if self.Parse('.'):
                rDigits = self.ParseDigits(0)
            if not lDigits and not rDigits:
                self.SetPos(savePos)
                return None
            if self.ParseOne('eE'):
                eSign = self.ParseOne("-")
                if eSign is None:
                    eSign = '+'
                eDigits = self.ParseDigits(0)
        return Numeric(sign, lDigits, rDigits, eSign, eDigits)

    def ParseTimeLiteral(self):
        """Parses a Time literal, returning a :py:class:`pyslet.iso8601.Time` instance.

        Returns None if no Time literal can be parsed.  This is a
        generous way of parsing iso8601-like values, it accepts omitted
        zeros in the leading field, such as 7:45:00."""
        savePos = self.pos
        try:
            production = "timeLiteral"
            hour = self.RequireProduction(self.ParseInteger(0, 24), "hour")
            self.Require(":", production)
            minute = self.RequireProduction(
                self.ParseInteger(0, 60, 2), "minute")
            if self.Parse(":"):
                second = self.RequireProduction(
                    self.ParseInteger(0, 60, 2), "second")
                if self.Parse("."):
                    nano = self.ParseDigits(1, 7)
                    second += float("0." + nano)
            else:
                second = 0
        except ValueError:
            self.SetPos(savePos)
            return None
        try:
            value = iso8601.Time(
                hour=hour, minute=minute, second=second, zDirection=None)
        except iso8601.DateTimeError as e:
            raise ValueError(str(e))
        return value


class EDMValue(object):

    """Abstract class to represent a value in the EDMModel.

    This class is used to wrap or 'box' instances of a value.  In
    particular, it can be used in a context where that value can have
    either a simple or complex type."""

    def __init__(self, pDef=None):
        self.pDef = pDef
        """An optional :py:class:`Property` instance from the metadata
        model defining this value's type"""

    __hash__ = None
    """EDM values are mutable so may not be used as dictionary keys,
    this is enforced by setting __hash__ to None"""

    _TypeClass = {
    }

    def __nonzero__(self):
        """EDMValue instances are treated as being non-zero if :py:meth:`IsNull`
        returns False."""
        return not self.IsNull()

    def IsNull(self):
        """Returns True if this object is Null."""
        return True

    @classmethod
    def NewValue(cls, pDef):
        """Constructs an instance of the correct child class of
        :py:class:`EDMValue` to represent a value defined by
        :py:class:`Property` instance *pDef*.

        We support a special case for creating a type-less NULL.  If you
        pass None for pDef then a type-less
        :py:class:`SipmleValue` is instantiated."""
        if pDef is None:
            return SimpleValue(None)
        elif pDef.simpleTypeCode is not None:
            return cls._TypeClass[pDef.simpleTypeCode](pDef)
        elif pDef.complexType:
            return Complex(pDef)
        else:
            raise ModelIncomplete(
                "Property %s not bound to a type" % pDef.name)

    @classmethod
    def NewSimpleValue(cls, typeCode):
        """Constructs an instance of the correct child class of
        :py:class:`EDMValue` to represent an (undeclared) simple
        value of :py:class:`SimpleType` *typeCode*."""
        if typeCode is None:
            result = SimpleValue(None)
        else:
            result = cls._TypeClass[typeCode](None)
        # hack the type code after construction to save on overhead of another
        # constructor
        result.typeCode = typeCode
        return result

    @classmethod
    def NewSimpleValueFromValue(cls, value):
        """Constructs an instance of the correct child class of
        :py:class:`EDMValue` to hold *value*.

        *value* may be any of the types listed in
        :py:class:`SimpleValue`."""
        if isinstance(value, uuid.UUID):
            result = cls.NewSimpleValue(SimpleType.Guid)
        elif isinstance(value, iso8601.TimePoint):
            # if it has an offset
            if value.GetZone()[0] is None:
                # no timezone
                result = cls.NewSimpleValue(SimpleType.DateTime)
            else:
                result = cls.NewSimpleValue(SimpleType.DateTimeOffset)
        elif isinstance(value, decimal.Decimal):
            result = cls.NewSimpleValue(SimpleType.Decimal)
        elif isinstance(value, datetime.datetime):
            result = cls.NewSimpleValue(SimpleType.DateTime)
        else:
            t = SimpleType.PythonType.get(type(value), None)
            if t is not None:
                result = cls.NewSimpleValue(t)
            else:
                raise ValueError(
                    "Can't construct SimpleValue from %s" % repr(value))
        result.SetFromValue(value)
        return result


class SimpleValue(EDMValue):

    """An abstract class that represents a value of a simple type in the EDMModel.

    This class is not designed to be instantiated directly, use one of
    the factory methods in :py:class:`EdmValue` to construct one of the
    specific child classes."""

    def __init__(self, pDef=None):
        EDMValue.__init__(self, pDef)
        if pDef:
            #: the :py:class:`SimpleType` code
            self.typeCode = pDef.simpleTypeCode
        else:
            self.typeCode = None
        #: an optional :py:class:`pyslet.rfc2616.MediaType` representing this value
        self.mType = None
        self.value = None
        """The actual value or None if this instance represents a NULL value
    
        The python type used for *value* depends on typeCode as follows:
    
        * Edm.Boolean: one of the Python constants True or False
    
        * Edm.Byte, Edm.SByte, Edm.Int16, Edm.Int32: int

        * Edm.Int64: long

        * Edm.Double, Edm.Single: python float

        * Edm.Decimal: python Decimal instance (from decimal module)

        * Edm.DateTime, Edm.DateTimeOffset: py:class:`pyslet.iso8601.TimePoint` instance
    
        * Edm.Time: py:class:`pyslet.iso8601.Time` instance (not a Duration, note corrected v2 specification of OData)

        * Edm.Binary: raw string

        * Edm.String: unicode string

        * Edm.Guid: python UUID instance (from uuid module)
    
        For future compatibility, this attribute should only be updated
        using
        :py:meth:`SetFromValue` or one of the other related methods."""

    def IsNull(self):
        return self.value is None

    def SimpleCast(self, typeCode):
        """Returns a new :py:class:`SimpleValue` instance created from *typeCode*

        The value of the new instance is set using :py:meth:`Cast`"""
        targetValue = EDMValue.NewSimpleValue(typeCode)
        return self.Cast(targetValue)

    def Cast(self, targetValue):
        """Updates and returns *targetValue* a :py:class:`SimpleValue` instance.

        The value of targetValue is replaced with a value cast from this
        instance's value.

        If the types are incompatible a TypeError is raised, if the
        values are incompatible then ValueError is raised.

        NULL values can be cast to any value type."""
        if self.typeCode == targetValue.typeCode:
            targetValue.value = self.value
        else:
            # newValue=EDMValue.NewValue(newTypeCode,self.name)
            if self.typeCode is not None:
                targetValue.SetFromValue(copy.deepcopy(self.value))
        return targetValue

    def SetFromSimpleValue(self, newValue):
        """The reverse of the :py:meth:`Cast` method, sets this value to
        the value of *newValue* casting as appropriate."""
        newValue.Cast(self)

    def __eq__(self, other):
        """Instances compare equal only if they of the same type and
        have values that compare equal."""
        if isinstance(other, SimpleValue):
            # are the types compatible? lazy comparison to start with
            return self.typeCode == other.typeCode and self.value == other.value
        else:
            return self.value == other

    def __ne__(self, other):
        return not self == other

    def __unicode__(self):
        """Formats this value into its literal form.

        NULL values cannot be represented in literal form and will raise
        ValueError."""
        if self.value is None:
            raise ValueError("%s is NULL" % self.name)
        return unicode(self.value)

    def SetFromLiteral(self, value):
        """Decodes a value from the value's literal form.

        You can get the literal form of a value using the unicode function."""
        raise NotImplementedError

    def SetNull(self):
        """Sets the value to NULL"""
        self.value = None

    def SetFromValue(self, newValue):
        """Sets the value from a python variable coercing *newValue* if
        necessary to ensure it is of the correct type for the value's
        :py:attr:`typeCode`."""
        if newValue is None:
            self.value = None
        else:
            raise NotImplementedError

    @classmethod
    def Copy(cls, value):
        """Constructs a new SimpleValue instance by copying *value*"""
        if self.pDef:
            result = value.__class__(self.pDef)
        else:
            result = EdmValue.NewSimpleValue(self.typeCode)
        result.value = value.value
        return result


class BinaryValue(SimpleValue):

    """Represents a :py:class:`SimpleValue` of type Edm.Binary.

    Binary literals allow content in the following form::

                    [A-Fa-f0-9][A-Fa-f0-9]*

    Binary values can be set from any Python type, though anything other
    than a binary string is set to its pickled representation.  There is
    no reverse facility for reading an object from the pickled value."""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        input = StringIO.StringIO(self.value)
        output = StringIO.StringIO()
        while True:
            byte = input.read(1)
            if len(byte):
                output.write("%02X" % ord(byte))
            else:
                break
        return unicode(output.getvalue())

    def SetFromLiteral(self, value):
        p = Parser(value)
        self.value = p.RequireProductionEnd(
            p.ParseBinaryLiteral(), "binaryLiteral")

    def SetFromValue(self, newValue):
        if isinstance(newValue, StringType):
            self.value = newValue
        elif newValue is None:
            self.value = None
        else:
            self.value = pickle.dumps(newValue)


class BooleanValue(SimpleValue):

    """Represents a simple value of type Edm.Boolean

    Boolean literals are one of::

                    true | false

    Boolean values can be set from their Python equivalents and from any
    int, long, float or Decimal where the non-zero test is used to set
    the value."""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return u"true" if self.value else u"false"

    def SetFromLiteral(self, value):
        testValue = value.lower()
        if testValue == u"true":
            self.value = True
        elif testValue == u"false":
            self.value = False
        else:
            raise ValueError("Failed to parse boolean literal from %s" % value)

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
            self.value = (newValue != 0)
        elif isinstance(newValue, BooleanType):
            self.value = newValue
        else:
            raise TypeError("Can't set Boolean from %s" % str(newValue))


class NumericValue(SimpleValue):

    """An abstract class that represents all numeric simple values.

    The literal forms of numeric values are parsed in a two-stage
    process.  Firstly the utility class :py:class:`Parser` is used to
    obtain a numeric tuple and then the value is set using
    :py:meth:`SetFromNumericLiteral`

    All numeric types may have their value set directly from int, long,
    float or Decimal.

    Integer representations are rounded towards zero using the python
    *int* or *long* functions when necessary."""

    def SetToZero(self):
        """Set this value to the default representation of zero"""
        self.SetFromValue(0)

    def SetFromLiteral(self, value):
        p = Parser(value)
        nValue = p.RequireProductionEnd(p.ParseNumericLiteral(), "byteLiteral")
        self.SetFromNumericLiteral(nValue)

    def SetFromNumericLiteral(self, numericValue):
        """Decodes a value from a numeric tuple as returned by
        :py:meth:`Parser.ParseNumericLiteral`."""
        raise NotImplementedError

    def JoinNumericLiteral(self, numericValue):
        r = []
        r.append(numericValue.sign)
        r.append(numericValue.lDigits)
        if numericValue.rDigits is not None:
            r.append('.')
            r.append(numericValue.rDigits)
        if numericValue.eDigits is not None:
            r.append('E')
            r.append(numericValue.eSign)
            r.append(numericValue.eDigits)
        return string.join(r, '')


class ByteValue(NumericValue):

    """Represents a simple value of type Edm.Byte

    Byte literals must not have a sign, decimal point or exponent.

    Byte values can be set from an int, long, float or Decimal"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return xsi.EncodeInteger(self.value)

    def SetFromNumericLiteral(self, numericValue):
        if (numericValue.sign or                    # no sign allowed at all
                not numericValue.lDigits or             # must be left digits
                # must not be nan or inf
                numericValue.lDigits.isalpha() or
                # must not have '.' or rDigits
                numericValue.rDigits is not None or
                numericValue.eDigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Byte: %s" %
                             self.JoinNumericLiteral(numericValue))
        self.SetFromValue(int(numericValue.lDigits))

    def SetFromValue(self, newValue):
        """*newValue* must be of type int, long, float or Decimal."""
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
            if newValue < 0 or newValue > 255:
                raise ValueError("Illegal value for Byte: %s" % str(newValue))
            self.value = int(newValue)
        else:
            raise TypeError("Can't set Byte from %s" % str(newValue))


class DateTimeValue(SimpleValue):

    """Represents a simple value of type Edm.DateTime

    DateTime literals allow content in the following form::

            yyyy-mm-ddThh:mm[:ss[.fffffff]]

    DateTime values can be set from an instance of
    :py:class:`iso8601.TimePoint` or type int, long, float or Decimal.

    Any zone specifier is ignored.  There is *no* conversion to UTC, the
    value simply becomes a local time in an unspecified zone.  This is a
    weakness of the EDM, it is good practice to limit use of the
    DateTime type to UTC times.

    When set from a numeric value, the value must be non-negative.  Unix
    time is assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.FromUnixTime` factory method of
    TimePoint for information.

    If a property definition was set on construction then the defined
    precision is used when representing the value as a unicode string.
    For example, if the property has precision 3 then the output of the
    unicode conversion will appear in the following form::

            1969-07-20T20:17:40.000"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        precision = None
        if self.pDef:
            # check the precision before formatting
            precision = self.pDef.precision
        if precision is None:
            precision = 0
        return self.value.GetCalendarString(ndp=precision, dp=u".")

    def SetFromLiteral(self, value):
        p = Parser(value)
        self.value = p.RequireProductionEnd(
            p.ParseDateTimeLiteral(), "DateTime")

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, iso8601.TimePoint):
            self.value = newValue.WithZone(zDirection=None)
        elif (isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType)) and newValue >= 0:
            self.value = iso8601.TimePoint.FromUnixTime(float(newValue))
        elif isinstance(newValue, datetime.datetime):
            self.value = iso8601.TimePoint(
                date=iso8601.Date(
                    century=newValue.year //
                    100,
                    year=newValue.year %
                    100,
                    month=newValue.month,
                    day=newValue.day),
                time=iso8601.Time(
                    hour=newValue.hour,
                    minute=newValue.minute,
                    second=newValue.second,
                    zDirection=None))
        else:
            raise TypeError("Can't set DateTime from %s" % repr(newValue))


class DateTimeOffsetValue(SimpleValue):

    """Represents a simple value of type Edm.DateTimeOffset

    DateTimeOffset literals are defined in terms of the XMLSchema
    lexical representation.

    DateTimeOffset values can be set from an instance of
    :py:class:`iso8601.TimePoint` or type int, long, float or Decimal.

    TimePoint instances must have a zone specifier.  There is *no*
    automatic assumption of UTC.

    When set from a numeric value, the value must be non-negative.  Unix
    time *in UTC* assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.FromUnixTime` factory method of
    TimePoint for information.

    If a property definition was set on construction then the defined
    precision is used when representing the value as a unicode string.
    For example, if the property has precision 3 then the output of the
    unicode conversion will appear in the following form::

            1969-07-20T15:17:40.000-05:00

    It isn't completely clear if the canonical representation of UTC
    using 'Z' instead of an offset is intended or widely supported so we
    always use an offset::

            1969-07-20T20:17:40.000+00:00"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        precision = None
        if self.pDef:
            # check the precision before formatting
            precision = self.pDef.precision
        if precision is None:
            precision = 0
        result = self.value.GetCalendarString(ndp=precision, dp=u".")
        if result[-1] == "Z":
            # the specification is not clear if the Z form is supported, use
            # numbers for safety
            result = result[:-1] + "+00:00"
        return result

    def SetFromLiteral(self, value):
        try:
            value = iso8601.TimePoint.FromString(value)
        except iso8601.DateTimeError as e:
            raise ValueError(str(e))
        self.SetFromValue(value)

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, iso8601.TimePoint):
            zDir, zOffset = newValue.GetZone()
            if zOffset is None:
                raise ValueError(
                    "DateTimeOffset requires a time zone specifier: %s" %
                    newValue)
            if not newValue.Complete():
                raise ValueError(
                    "DateTimeOffset requires a complete representation: %s" %
                    str(newValue))
            self.value = newValue
        elif (isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType)) and newValue >= 0:
            self.value = iso8601.TimePoint.FromUnixTime(float(newValue))
        else:
            raise TypeError("Can't set DateTimeOffset from %s" % str(newValue))


class TimeValue(SimpleValue):

    u"""Represents a simple value of type Edm.Time

    Time literals allow content in the form:

            hh:mm:ss.sss

    Time values can be set from an instance of
    :py:class:`pyslet.iso8601.Time`, int, long, float or
    Decimal.

    When set from a numeric value the value must be in the range
    0..86399.9\u0305 and is treated as an elapsed time in seconds since
    midnight.

    If a property definition was set on construction then the defined
    precision is used when representing the value as a unicode string.
    For example, if the property has precision 3 then the output of the
    unicode conversion will appear in the following form::

            20:17:40.000"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        precision = None
        if self.pDef:
            # check the precision before formatting
            precision = self.pDef.precision
        if precision is None:
            precision = 0
        return self.value.GetString(ndp=precision, dp=u".")

    def SetFromLiteral(self, value):
        p = Parser(value)
        self.value = p.RequireProductionEnd(p.ParseTimeLiteral(), "Time")

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, iso8601.Time):
            self.value = newValue
        elif (isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType)) and newValue >= 0:
            if newValue < 0:
                raise "Can't set Time from %.3f"
            tValue = iso8601.Time()
            if type(newValue) in (IntType, LongType):
                tValue, days = tValue.Offset(newValue)
            else:
                tValue, days = tValue.Offset(float(newValue))
            if days > 0:
                raise "Can't set Time from %.3f (overflow)"
            self.value = tValue
        else:
            raise TypeError("Can't set Time from %s" % repr(newValue))


class DecimalValue(NumericValue):

    """Represents a simple value of type Edm.Decimal

    Decimal literals must not use exponent notation and there must be no
    more than 29 digits to the left and right of the decimal point.

    Decimal values can be set from int, long, float or Decimal values."""
    Max = decimal.Decimal(
        10) ** 29 - 1     # max decimal in the default context
    # min decimal for string representation
    Min = decimal.Decimal(10) ** -29

    @classmethod
    def abs(cls, d):
        if d < 0:
            return -d
        else:
            return d

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        t = self.value.as_tuple()
        if t.exponent < -29:
            # CSDL expects a 29-digit limit to the right of the point
            d = self.value.quantize(decimal.Decimal(10) ** -29)
        elif t.exponent + len(t.digits) > 29:
            # CSDL expects a 29-digit limit to the left of the point
            raise ValueError(
                "Value exceeds limits for Decimal: %s" % str(self.value))
        else:
            d = self.value
        # now ensure there is no exponent in the format
        return unicode(d.__format__('f'))

    def SetFromNumericLiteral(self, numericValue):
        dStr = self.JoinNumericLiteral(numericValue)
        if ((numericValue.lDigits and
                (numericValue.lDigits.isalpha() or                  # inf and nan not allowed
                 len(numericValue.lDigits) > 29)) or                # limit left digits
                (numericValue.rDigits and
                 len(numericValue.rDigits) > 29) or             # limit right digits
                # ensure decimals if '.' is present
                numericValue.rDigits == "" or
                numericValue.eDigits is not None):                  # do not allow exponent
            raise ValueError("Illegal literal for Decimal: %s" % dStr)
        self.SetFromValue(decimal.Decimal(dStr))

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
            return
        elif isinstance(newValue, decimal.Decimal):
            d = newValue
        elif type(newValue) in (IntType, LongType, FloatType):
            d = decimal.Decimal(newValue)
        else:
            raise TypeError("Can't set Decimal from %s" % str(newValue))
        if self.abs(d) > self.Max:
            # too big for CSDL decimal forms
            raise ValueError("Value exceeds limits for Decimal: %s" % str(d))
        # in the interests of maintaining accuracy we don't limit the
        # precision of the value at this point
        self.value = d


class FloatValue(NumericValue):

    """Abstract class that represents one of Edm.Double or Edm.Single.

    Values can be set from int, long, float or Decimal.

    There is no hard-and-fast rule about the representation of float in
    Python and we may refuse to accept values that fall within the
    accepted ranges defined by the CSDL if float cannot hold them.  That
    said, you won't have this problem in practice.

    The derived classes :py:class:`SingleValue` and
    :py:class:`DoubleValue` only differ in the Max value used
    when range checking.

    Values are formatted using Python's default unicode conversion."""

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType):
            if newValue < -self.Max or newValue > self.Max:
                raise ValueError(
                    "Value for Double out of range: %s" % str(newValue))
            self.value = float(newValue)
        elif isinstance(newValue, FloatType):
            if math.isnan(newValue) or math.isinf(newValue):
                self.value = newValue
            elif newValue < -self.Max or newValue > self.Max:
                raise ValueError("Value out of range: %s" % str(newValue))
            else:
                self.value = newValue
        else:
            raise TypeError(
                "Can't set floating-point value from %s" % str(newValue))


class DoubleValue(FloatValue):

    """Represents a simple value of type Edm.Double"""

    Max = None
    """the largest positive double value
    
    This value is set dynamically on module load, theoretically it may
    be set lower than the maximum allowed by the specification if
    Python's native float is of insufficient precision but this is
    unlikely to be an issue."""
    # Min=2**-1074  #: the smallest positive double value

    def SetFromNumericLiteral(self, numericValue):
        dStr = self.JoinNumericLiteral(numericValue)
        if numericValue.lDigits and numericValue.lDigits.isalpha():
            if numericValue.lDigits == "nan":
                if numericValue.sign:
                    raise ValueError(
                        "Illegal literal, nan must not be negative: %s" % dStr)
                self.value = float("Nan")
            elif numericValue.sign == "-":
                self.value = float("-INF")
            else:
                self.value = float("INF")
        elif (numericValue.rDigits is None or       # integer form or
                numericValue.eDigits is not None):      # exponent form; limit digits
            nDigits = len(numericValue.lDigits)
            if numericValue.rDigits:
                nDigits += len(numericValue.rDigits)
            if nDigits > 17:
                raise ValueError("Too many digits for double: %s" % dStr)
            if (numericValue.eDigits == '' or                   # empty exponent not allowed
                    (numericValue.eDigits and
                     (len(numericValue.eDigits) > 3 or          # long exponent not allowed
                      not numericValue.lDigits))):          # exponent requires digits to left of point
                raise ValueError("Illegal exponent form for double: %s" % dStr)
        self.SetFromValue(float(dStr))


for i in xrange(1023, 0, -1):
    try:
        DoubleValue.Max = (2 - 2 ** -52) * 2 ** i
        break
    except OverflowError:
        # worrying this probably means float is too small for this application
        if i == 1023:
            logging.warning("float may be less than double precision")
        elif i == 127:
            logging.warning("float may be less than singe precision!")
        continue


class SingleValue(FloatValue):

    """Represents a simple value of type Edm.Single"""

    Max = None
    """the largest positive single value
    
    This value is set dynamically on module load, theoretically it may
    be set lower than the maximum allowed by the specification if
    Python's native float is of insufficient precision but this is very
    unlikely to be an issue unless you've compiled Python on in a very
    unusual environment."""
    # Min=2.0**-149             #: the smallest positive single value

    def SetFromNumericLiteral(self, numericValue):
        """Decodes a Single value from a :py:class:`Numeric` literal."""
        dStr = self.JoinNumericLiteral(numericValue)
        if numericValue.lDigits and numericValue.lDigits.isalpha():
            if numericValue.lDigits == "nan":
                if numericValue.sign:
                    raise ValueError(
                        "Illegal literal, nan must not be negative: %s" % dStr)
                self.value = float("Nan")
            elif numericValue.sign == "-":
                self.value = float("-INF")
            else:
                self.value = float("INF")
        elif numericValue.rDigits is None:
            # integer form
            if len(numericValue.lDigits) > 8:
                raise ValueError("Too many digits for single: %s" % dStr)
        elif numericValue.eDigits is not None:
            # exponent form
            nDigits = len(numericValue.lDigits)
            if numericValue.rDigits:
                nDigits += len(numericValue.rDigits)
            if nDigits > 9:
                raise ValueError("Too many digits for single: %s" % dStr)
            if (numericValue.eDigits == '' or                   # empty exponent not allowed
                    (numericValue.eDigits and
                     (len(numericValue.eDigits) > 2 or          # long exponent not allowed
                      not numericValue.lDigits))):          # exponent requires digits to left of point
                raise ValueError("Illegal exponent form for single: %s" % dStr)
        self.SetFromValue(float(dStr))


for i in xrange(127, 0, -1):
    try:
        SingleValue.Max = (2 - 2 ** -23) * 2 ** i
        break
    except OverflowError:
        # worrying this probably means float is too small for this application
        if i == 127:
            logging.warning("float may be less than singe precision!")
        continue


class GuidValue(SimpleValue):

    """Represents a simple value of type Edm.Guid

    Guid literals allow content in the following form:
    dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents [A-Fa-f0-9].

    Guid values can also be set directly from either binary or hex
    strings. Binary strings must be of length 16 and are passed as raw
    bytes to the UUID constructor, hexadecimal strings can be string or
    unicode strings and must be of length 32 characters."""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return unicode(self.value)

    def SetFromLiteral(self, value):
        p = Parser(value)
        self.value = p.RequireProductionEnd(p.ParseGuidLiteral(), "Guid")

    def SetFromValue(self, newValue):
        """*newValue* must be an instance of Python's UUID class

        We also support setting from a raw string of exactly 16 bytes in
        length or a text string of exactly 32 bytes (the latter is
        treated as the hex representation)."""
        if newValue is None:
            self.value = None
        elif isinstance(newValue, uuid.UUID):
            self.value = newValue
        elif isinstance(newValue, StringType) and len(newValue) == 16:
            self.value = uuid.UUID(bytes=newValue)
        elif type(newValue) in StringTypes and len(newValue) == 32:
            self.value = uuid.UUID(hex=newValue)
        else:
            raise TypeError("Can't set Guid from %s" % repr(newValue))


class Int16Value(NumericValue):

    """Represents a simple value of type Edm.Int16"""

    def SetFromNumericLiteral(self, numericValue):
        if (not numericValue.lDigits or             # must be left digits
                # must not be nan or inf
                numericValue.lDigits.isalpha() or
                # must not have '.' or rDigits
                numericValue.rDigits is not None or
                numericValue.eDigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Int16: %s" %
                             self.JoinNumericLiteral(numericValue))
        self.SetFromValue(int(self.JoinNumericLiteral(numericValue)))

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
            if newValue < -32768 or newValue > 32767:
                raise ValueError("Illegal value for Int16: %s" % str(newValue))
            self.value = int(newValue)
        else:
            raise TypeError("Can't set Int16 from %s" % str(newValue))


class Int32Value(NumericValue):

    """Represents a simple value of type Edm.Int32"""

    def SetFromNumericLiteral(self, numericValue):
        if (not numericValue.lDigits or             # must be left digits
                # must not be more than 10 digits
                len(numericValue.lDigits) > 10 or
                # must not be nan or inf
                numericValue.lDigits.isalpha() or
                # must not have '.' or rDigits
                numericValue.rDigits is not None or
                numericValue.eDigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Int32: %s" %
                             self.JoinNumericLiteral(numericValue))
        self.SetFromValue(int(self.JoinNumericLiteral(numericValue)))

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
            if newValue < -2147483648 or newValue > 2147483647:
                raise ValueError("Illegal value for Int32: %s" % str(newValue))
            self.value = int(newValue)
        else:
            raise TypeError("Can't set Int32 from %s" % str(newValue))


class Int64Value(NumericValue):

    """Represents a simple value of type Edm.Int64"""

    def SetFromNumericLiteral(self, numericValue):
        if (not numericValue.lDigits or             # must be left digits
                # must not be more than 19 digits
                len(numericValue.lDigits) > 19 or
                # must not be nan or inf
                numericValue.lDigits.isalpha() or
                # must not have '.' or rDigits
                numericValue.rDigits is not None or
                numericValue.eDigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Int64: %s" %
                             self.JoinNumericLiteral(numericValue))
        self.SetFromValue(int(self.JoinNumericLiteral(numericValue)))

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
            if newValue < -9223372036854775808 or newValue > 9223372036854775807:
                raise ValueError("Illegal value for Int64: %s" % str(newValue))
            self.value = long(newValue)
        else:
            raise TypeError("Can't set Int64 from %s" % str(newValue))


class StringValue(SimpleValue):

    """Represents a simple value of type Edm.String"

    The literal form of a string is the string itself.

    Values may be set from any string or object which supports the
    native unicode function."""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return unicode(self.value)

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, UnicodeType):
            self.value = newValue
        else:
            self.value = unicode(newValue)

    def SetFromLiteral(self, value):
        self.value = value


class SByteValue(NumericValue):

    """Represents a simple value of type Edm.SByte"""

    def SetFromNumericLiteral(self, numericValue):
        if (not numericValue.lDigits or             # must be left digits
                # must not be nan or inf
                numericValue.lDigits.isalpha() or
                # must not have '.' or rDigits
                numericValue.rDigits is not None or
                numericValue.eDigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for SByte: %s" %
                             self.JoinNumericLiteral(numericValue))
        self.SetFromValue(int(self.JoinNumericLiteral(numericValue)))

    def SetFromValue(self, newValue):
        if newValue is None:
            self.value = None
        elif isinstance(newValue, decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
            if newValue < -128 or newValue > 127:
                raise ValueError("Illegal value for SByte: %s" % str(newValue))
            self.value = int(newValue)
        else:
            raise TypeError("Can't set SByte from %s" % str(newValue))


EDMValue._TypeClass = {
    SimpleType.Binary: BinaryValue,
    SimpleType.Boolean: BooleanValue,
    SimpleType.Byte: ByteValue,
    SimpleType.DateTime: DateTimeValue,
    SimpleType.DateTimeOffset: DateTimeOffsetValue,
    SimpleType.Time: TimeValue,
    SimpleType.Decimal: DecimalValue,
    SimpleType.Double: DoubleValue,
    SimpleType.Single: SingleValue,
    SimpleType.Guid: GuidValue,
    SimpleType.Int16: Int16Value,
    SimpleType.Int32: Int32Value,
    SimpleType.Int64: Int64Value,
    SimpleType.String: StringValue,
    SimpleType.SByte: SByteValue
}


class TypeInstance(DictionaryLike):

    """Abstract class to represents a single instance of a
    :py:class:`ComplexType` or :py:class:`EntityType`.

    Behaves like a read-only dictionary mapping property names onto
    :py:class:`EDMValue` instances.  (You can change the value of a
    property using the methods of :py:class:`EDMValue` and its
    descendants.)

    Unlike regular Python dictionaries, iteration over the of keys in
    the dictionary (the names of the properties) is always done in the
    order in which they are declared in the type definition."""

    def __init__(self, type_def=None):
        self.type_def = type_def      #: the definition of this type
        self.data = {}
        if type_def is not None:
            for p in self.type_def.Property:
                self.data[p.name] = p()

    def AddProperty(self, pName, pValue):
        self.data[pName] = pValue

    def __getitem__(self, name):
        return self.data[name]

    def __iter__(self):
        for p in self.type_def.Property:
            yield p.name

    def __len__(self):
        return len(self.type_def.Property)


class Complex(EDMValue, TypeInstance):

    """Represents a single instance of a :py:class:`ComplexType`."""

    def __init__(self, pDef=None):
        EDMValue.__init__(self, pDef)
        TypeInstance.__init__(self, None if pDef is None else pDef.complexType)

    def IsNull(self):
        """Complex values are never NULL"""
        return False

    def SetNull(self):
        """Sets all simple property values to NULL recursively"""
        for k, v in self.iteritems():
            v.SetNull()

    def SetFromComplex(self, newValue):
        """Sets this value from *newValue* which must be a
        :py:class:`Complex` instance.

        There is no requirement that *newValue* is of the same type,
        but it must be broadly compatible, which is defined as:

                Any named property present in both the current value and
                *newValue* must be of compatible types.

        Any named property in the current value which is not present in
        *newValue* is left unchanged by this method."""
        for k, v in self.iteritems():
            nv = newValue.get(k, None)
            if nv is None:
                continue
            if isinstance(v, Complex):
                if isinstance(nv, Complex):
                    self[k].SetFromComplex(v)
                else:
                    raise ValueError(
                        "Can't set Complex property from %s" % repr(nv))
            elif isinstance(nv, Complex):
                continue
            else:
                self[k].SetFromSimpleValue(v)


class DeferredValue(object):

    """Represents the value of a navigation property."""

    def __init__(self, name, from_entity):
        #: the name of the associated navigation property
        self.name = name
        #: the entity that contains this value
        self.from_entity = from_entity
        #: the definition of the navigation property
        self.pDef = self.from_entity.type_def[name]
        fromM, targetM = self.from_entity.entity_set.NavigationMultiplicity(
            self.name)
        #: True if this deferred value represents a (single) required entity
        self.isRequired = (targetM == Multiplicity.One)
        #: True if this deferred value represents a collection
        self.isCollection = (targetM == Multiplicity.Many)
        self.isExpanded = False
        """True if this deferred value has been expanded.
        
        An expanded navigation property will return a read-only
        :py:class:`ExpandedEntityCollection` when
        :py:meth:`OpenCollection` is called."""
        self.bindings = []
        """The list of entity instances or keys to bind to *from_entity*
        when it is inserted or next updated."""
        self.expandedCollection = None

    def Target(self):
        """Returns the target entity set of this navigation (without opening the collection)."""
        return self.from_entity.entity_set.NavigationTarget(self.name)

    def GetEntity(self):
        """Returns a single entity instance or None.

        If this deferred value represents an entity collection then
        NavigationError is raised."""
        if self.isCollection:
            raise NavigationError(
                "%s.%s is a collection" %
                (self.from_entity.entity_set.name, self.name))
        with self.OpenCollection() as collection:
            values = collection.values()
            if len(values) == 1:
                return values[0]
            elif len(values) == 0:
                return None
            else:
                raise NavigationError(
                    "Navigation property %s of %s[%s] is not a collection but it yielded multiple entities" %
                    (self.name, self.from_entity.entity_set.name, str(
                        self.from_entity.Key())))

    def OpenCollection(self):
        """Opens the collection associated with this navigation property.

        Returns an :py:class:`EntityCollection` instance which must be closed
        when it is no longer needed.  This is best achieved with the
        Python with statement using the collection's context-manager
        behaviour.  For example::

                with customer['Orders'].OpenCollection() as orders:
                        # do something with the orders"""
        if self.from_entity.exists:
            if self.isExpanded:
                return self.expandedCollection
            else:
                collection = self.from_entity.entity_set.OpenNavigation(
                    self.name, self.from_entity)
                return collection
        else:
            raise NonExistentEntity(
                "Attempt to navigate a non-existent entity: %s.%s" %
                (self.from_entity.type_def.name, self.name))

    def SetExpansion(self, expandedCollection):
        """Sets the expansion for this deferred value to the :py:class:`ExpandedEntityCollection` given.

        If *expandedCollection* is None then the expansion is removed
        and future calls to :py:meth:`OpenColection` will yield a
        (dynamically created) entity collection."""
        if expandedCollection is None:
            self.isExpanded = False
            self.expandedCollection = None
        else:
            if not isinstance(expandedCollection, ExpandedEntityCollection):
                raise TypeError
            self.isExpanded = True
            self.expandedCollection = expandedCollection

    def ExpandCollection(self, expand, select):
        """A convenience function of use to data providers.

        Expands this navigation property, further expanding the
        resulting collection of entities using the given *expand* and
        *select* options (see :py:meth:`EntityCollection.Expand` for
        details)."""
        with self.from_entity.entity_set.OpenNavigation(self.name, self.from_entity) as collection:
            collection.Expand(expand, select)
            self.SetExpansion(collection.ExpandCollection())

    def BindEntity(self, target):
        """Binds a *target* entity to this navigation property.

        *target* is either the entity you're binding or its key in the
        target entity set. For example::

                customer['Orders'].Bind(1)

        binds the entity represented by 'customer' to the Order entity
        with key 1.

        Just as for updates to data property values, the binding
        information is saved and acted upon when the entity is next
        updated or, for non-existent entities, inserted into the entity
        set.

        If you attempt to bind to a target entity that doesn't exist the
        target entity will be created automatically when the source
        entity is updated or inserted."""
        if self.isCollection:
            self.bindings.append(target)
        else:
            self.bindings = [target]

    def CheckNavigationConstraint(self):
        """Checks if this navigation property :py:attr:`isRequired` and
        raises :py:class:`NavigationConstraintError` if it has not been
        bound with :py:meth:`BindEntity`.

        This method is only intended to be called on non-existent
        entities."""
        if self.isRequired:
            if not self.bindings:
                raise NavigationConstraintError(
                    "Required navigation property %s of %s is not bound" %
                    (self.name, self.from_entity.entity_set.name))

    def update_bindings(self):
        """Iterates through :py:attr:`bindings` and generates appropriate calls
        to update the collection.

        Unlike the parent Entity's :py:meth:`Entity.Update` method, which updates all
        data and navigation values simultaneously, this method can be used to selectively
        update a single navigation property."""
        if self.bindings:
            # get an entity collection for this navigation property
            with self.OpenCollection() as collection:
                while self.bindings:
                    binding = self.bindings[0]
                    if not isinstance(binding, Entity):
                        # just a key, we'll grab the entity first
                        # which will generate KeyError if it doesn't
                        # exist
                        with collection.entity_set.OpenCollection() as baseCollection:
                            baseCollection.SelectKeys()
                            binding = baseCollection[binding]
                    if binding.exists:
                        if self.isCollection:
                            # use __setitem__ to add this entity to the entity
                            # collection
                            collection[binding.Key()] = binding
                        else:
                            # use replace to replace the current binding
                            collection.replace(binding)
                    else:
                        # we need to insert this entity, which will
                        # automatically link to us
                        collection.insert_entity(binding)
                    # success, trim bindings now in case we get an error
                    self.bindings = self.bindings[1:]

    def ClearBindings(self):
        """Removes any (unsaved) entity bindings from this navigation
        property."""
        self.bindings = []


class Entity(TypeInstance):

    """Represents a single instance of an :py:class:`EntityType`.

    Entity instance must only be created by data providers, a child
    class may be used with data provider-specific functionality.  Data
    consumers should use the :py:meth:`EntityCollection.new_entity` or
    :py:class:`EntityCollection.CopyEntity` methods to create instances.

    *   entity_set is the entity set this entity belongs to

    Entity instances extend :py:class:`TypeInstance`'s dictionary-like
    behaviour to include all properties.  As a result the dictionary
    values are one of :py:class:`SimpleValue`, :py:class:`Complex` or
    py:class:`DeferredValue` instances.

    Property values are created on construction and cannot be assigned
    directly. To update a simple value use the value's
    :py:meth:`SimpleValue.SetFromPyVaue` method::

            e['Name'].SetFromValue("Steve")
                    # update simple property Name
            e['Address']['City'].SetFromValue("Cambridge")
                    # update City in complex property Address

    A simple valued property that is NULL is still a
    :py:class:`SimpleValue` instance, though it will behave as
    0 in tests::

            e['Name'].SetFromValue(None)    # set to NULL
            if e['Name']:
                    print "Will not print!"

    Navigation properties are represented as :py:class:`DeferredValue`
    instances.  A deferred value can be opened in a similar way to an
    entity set::

            # open the collection obtained from navigation property Friends
            with e['Friends'].OpenCollection() as friends:
                    # iterate through all the friends of entity e
                    for friend in friends:
                            print friend['Name']

    A convenience method is provided when the navigation property points
    to a single entity (or None) by definition::

            mum=e['Mother'].GetEntity()     # may return None

    In the EDM one or more properties are marked as forming the entity's
    key.  The entity key is unique within the entity set.  On
    construction, an Entity instance is marked as being 'non-existent',
    :py:attr:`exists` is set to False.  This is consistent with the fact
    that the data properties of an entity are initialised to their
    default values, or NULL if there is no default specified in the
    model. Entity instances returned as values in collection objects
    have exists set to True.

    If an entity does not exist, OpenCollection will fail if called on
    one of its navigation properties with :py:class:`NonExistentEntity`.

    You can use :py:meth:`IsEntityCollection` to determine if a property
    will return an :py:class:`EntityCollection` without the cost of
    accessing the data source itself."""

    def __init__(self, entity_set):
        self.entity_set = entity_set
        TypeInstance.__init__(self, entity_set.entityType)
        #: whether or not the instance exists in the entity set
        self.exists = False
        #: the set of selected property names or None if all properties are selected
        self.selected = None
        if self.type_def is None:
            raise ModelIncomplete("Unbound EntitySet: %s (%s)" % (
                self.entity_set.name, self.entity_set.entityTypeName))
        for np in self.type_def.NavigationProperty:
            self.data[np.name] = DeferredValue(np.name, self)

    def __iter__(self):
        """Iterates over the property names, including the navigation
        properties.

        Unlike native Python dictionaries, the order in which the
        properties are iterated over is defined.  The regular property
        names are yielded first, followed by the navigation properties.
        Within these groups properties are yielded in the order they
        were declared in the metadata model."""
        for p in self.type_def.Property:
            yield p.name
        for p in self.type_def.NavigationProperty:
            yield p.name

    def DataKeys(self):
        """Iterates through the names of this entity's data properties only

        The order of the names is always the order they are defined in
        the metadata model."""
        for p in self.type_def.Property:
            yield p.name

    def DataItems(self):
        """Iterator that yields tuples of (key,value) for this entity's
        data properties only.

        The order of the items is always the order they are defined in
        the metadata model."""
        for p in self.type_def.Property:
            yield p.name, self[p.name]

    def SetFromEntity(self, newValue):
        """Sets this entity's value from *newValue* which must be a
        :py:class:`TypeInstance` instance.  In other words, it may
        be either an Entity or a Complex value.

        There is no requirement that *newValue* be of the same type,
        but it must be broadly compatible, which is defined as:

                Any named property present in both the current value and
                *newValue* must be of compatible types.

        Any named property in the current value which is not present in
        *newValue* is left unchanged by this method."""
        for k, v in self.DataItems():
            if k in self.entity_set.keys:
                continue
            newValue = newValue.get(k, None)
            if newValue is None:
                continue
            if isinstance(v, Complex):
                if isinstance(newValue, Complex):
                    self[k].SetFromComplex(v)
                else:
                    continue
            elif isinstance(newValue, Complex):
                continue
            else:
                self[k].SetFromSimpleValue(v)

    def NavigationKeys(self):
        """Iterates through the names of this entity's navigation properties only.

        The order of the names is always the order they are defined in
        the metadata model."""
        for np in self.type_def.NavigationProperty:
            yield np.name

    def NavigationItems(self):
        """Iterator that yields tuples of (key,deferred value) for this
        entity's navigation properties only.

        The order of the items is always the order they are defined in
        the metadata model."""
        for np in self.type_def.NavigationProperty:
            yield np.name, self[np.name]

    def CheckNavigationConstraints(self, ignoreEnd=None):
        """For entities that do not yet exist, checks that each of the
        required navigation properties has been bound (with
        :py:meth:`DeferredValue.BindEntity`).

        If a required navigation property has not been bound then
        :py:class:`NavigationConstraintError` is raised.

        If the entity already exists, :py:class:`EntityExists` is
        raised.

        For data providers, *ignoreEnd* may be set to an association set
        end bound to this entity's entity set.  Any violation of the
        related association is ignored."""
        if self.exists:
            raise EntityExists(
                "CheckNavigationConstraints: entity %s already exists" % str(
                    self.GetLocation()))
        badEnd = self.entity_set.unboundPrincipal
        if badEnd and badEnd != ignoreEnd:
            raise NavigationConstraintError(
                "entity %s has an unbound principal" % str(self.GetLocation()))
        ignoreName = self.entity_set.linkEnds.get(ignoreEnd, None)
        for name, np in self.NavigationItems():
            if name != ignoreName:
                np.CheckNavigationConstraint()

    def __len__(self):
        return len(self.type_def.Property) + \
            len(self.type_def.NavigationProperty)

    def IsNavigationProperty(self, name):
        """Returns true if name is the name of a navigation property,
        False otherwise."""
        try:
            pDef = self.type_def[name]
            return isinstance(pDef, NavigationProperty)
        except KeyError:
            return False

    def IsEntityCollection(self, name):
        """Returns True if *name* is the name of a navigation property
        that points to an entity collection, False otherwise."""
        return self.IsNavigationProperty(
            name) and self.entity_set.IsEntityCollection(name)

    def __getitem__(self, name):
        if name in self.data:
            return self.data[name]
        else:
            raise KeyError(name)

    def Update(self):
        """Updates this entity following modification.

        You can use select rules to provide a hint about which fields
        have been updated.  By the same logic, you cannot update a
        property that is not selected!

        The default implementation opens a collection object from the
        parent entity set and calls
        :py:meth:`EntityCollection.update_entity`."""
        with self.entity_set.OpenCollection() as collection:
            collection.update_entity(self)

    def Delete(self):
        """Deletes this entity from the parent entity set.

        The default implementation opens a collection object from the
        parent entity set and uses the del operator.

        Data providers must ensure that the entity's :py:attr:`exists`
        flag is set to False after deletion."""
        with self.entity_set.OpenCollection() as collection:
            del collection[self.Key()]

    def Key(self):
        """Returns the entity key as a single python value or a tuple of
        python values for compound keys.

        The order of the values is always the order of the PropertyRef
        definitions in the associated EntityType's :py:class:`Key`."""
        if len(self.type_def.Key.PropertyRef) == 1:
            result = self[self.type_def.Key.PropertyRef[0].name].value
            if result is None:
                raise KeyError("Entity with NULL key not allowed")
            return result
        else:
            k = []
            nullFlag = True
            for pRef in self.type_def.Key.PropertyRef:
                result = self[pRef.name].value
                k.append(result)
                if result is not None:
                    nullFlag = False
            if nullFlag:
                raise KeyError("Entity with NULL key not allowed")
            return tuple(k)

    def SetKey(self, key):
        """Sets this entity's key from a single python value or tuple.

        The entity must be non-existent or :py:class:`EntityExists` is raised."""
        if self.exists:
            raise EntityExists("SetKey not allowed; %s[%s] already exists" % (
                self.entity_set.name, str(self.Key())))
        if len(self.type_def.Key.PropertyRef) == 1:
            self[self.type_def.Key.PropertyRef[0].name].SetFromValue(key)
        else:
            k = iter(key)
            for pRef in self.type_def.Key.PropertyRef:
                self[pRef.name].SetFromValue(k.next())

    def KeyDict(self):
        """Returns the entity key as a dictionary mapping key property
        names onto :py:class:`SimpleValue` instances."""
        k = {}
        for pRef in self.type_def.Key.PropertyRef:
            k[pRef.name] = self[pRef.name]
        return k

    def Expand(self, expand, select=None):
        """Expands and selects properties of the entity according to the
        given *expand* and *select* rules (if any).

        Data consumers will usually apply expand rules to a collection
        which will then automatically ensure that all entities returned
        by the collection have been expanded.

        If, as a result of *select*, a non-key property is unselected
        then its value is set to NULL.  (Properties that comprise the
        key are never NULL.)

        If a property that is being expanded is also subject to one or
        more selection rules these are passed along with any chained
        Expand method call.

        The selection rules in effect are saved in the :py:attr:`select`
        member and can be tested using :py:meth:`Selected`."""
        if select is None:
            self.selected = None
            select = {}  # use during expansion
        else:
            self.selected = set()
            for k in self:
                if k in select:
                    self.selected.add(k)
            if "*" in select:
                # add all non-navigation items
                for k in self.DataKeys():
                    self.selected.add(k)
            else:
                # Force unselected values to NULL
                for k, v in self.DataItems():
                    if k not in self.entity_set.keys and k not in self.selected:
                        v.SetNull()
        # Now expand this entity's navigation properties
        if expand:
            for k, v in self.NavigationItems():
                if k in expand:
                    if k in select:
                        subSelect = select[k]
                        if subSelect is None:
                            # $select=Orders&$expand=Orders/OrderLines => $select=Orders/*
                            subSelect = {'*': None}
                    else:
                        subSelect = None
                    v.ExpandCollection(expand[k], subSelect)

    def Expanded(self, name):
        warnings.warn(
            "Entity.Expanded is deprecated, use, e.g., customer['Orders'].isExpanded instead",
            DeprecationWarning,
            stacklevel=3)
        return self[name].isExpanded

    def Selected(self, name):
        """Returns true if the property *name* is selected in this entity.

        You should not rely on the value of a unselected property, in most
        cases it will be set to NULL."""
        return self.selected is None or name in self.selected

    def ETag(self):
        """Returns a list of EDMValue instance values to use for optimistic
        concurrency control or None if the entity does not support it (or if
        all concurrency tokens are NULL or unselected)."""
        etag = []
        for pDef in self.type_def.Property:
            if pDef.concurrencyMode == ConcurrencyMode.Fixed and self.Selected(pDef.name):
                token = self[pDef.name]
                if token:
                    # only append non-null values
                    etag.append(token)
        if etag:
            return etag
        else:
            return None

    def ETagValues(self):
        """Returns a list of EDMValue instance values that may be used
        for optimistic concurrency control.  The difference between this
        method and :py:meth:`ETag` is that this method returns all
        values even if they are NULL or unselected.  If there are no
        concurrency tokens then an empty list is returned."""
        etag = []
        for pDef in self.type_def.Property:
            if pDef.concurrencyMode == ConcurrencyMode.Fixed:
                token = self[pDef.name]
                etag.append(token)
        return etag

    def GenerateConcurrencyHash(self):
        """Returns a hash object representing this entity's value.

        The hash is a SHA256 obtained by concatenating the literal
        representations of all data properties (strings are UTF-8
        encoded) except the keys and properties which have Fixed
        concurrency mode."""
        h = hashlib.sha256()
        key = self.KeyDict()
        for pDef in self.type_def.Property:
            if pDef.concurrencyMode == ConcurrencyMode.Fixed:
                continue
            elif pDef.name in key:
                continue
            v = self[pDef.name]
            if isinstance(v, Complex):
                self.UpdateComplexHash(h, v)
            elif not v:
                continue
            else:
                h.update(unicode(v).encode('utf-8'))
        return h

    def UpdateComplexHash(self, h, ct):
        for pDef in ct.type_def.Property:
            # complex types can't have properties used as concurrency tokens or
            # keys
            v = ct[pDef.name]
            if isinstance(v, Complex):
                self.UpdateComplexHash(h, v)
            elif not v:
                continue
            else:
                h.update(unicode(v).encode('utf-8'))

    def SetConcurrencyTokens(self):
        """A utility method for data providers.

        Sets all :py:meth:`ETagValues` using the following algorithm:

        1.  Binary values are set directly from the output of
                :py:meth:`GenerateConcurrencyHash`

        2.  String values are set from the hexdigest of the output
                :py:meth:`GenerateConcurrencyHash`

        3.  Integer values are incremented.

        4.  DateTime and DateTimeOffset values are set to the current
                time in UTC (and nudged by 1s if necessary)

        5.  Guid values are set to a new random (type 4) UUID.

        Any other type will generate a ValueError."""
        for t in self.ETagValues():
            if isinstance(t, BinaryValue):
                h = self.GenerateConcurrencyHash().digest()
                if t.pDef.maxLength is not None and t.pDef.maxLength < len(h):
                    # take the right-most bytes
                    h = h[len(h) - t.pDef.maxLength:]
                if t.pDef.fixedLength:
                    if t.pDef.maxLength > len(h):
                        # we need to zero-pad our binary string
                        h = h.ljust(t.pDef.maxLength, '\x00')
                t.SetFromValue(h)
            elif isinstance(t, StringValue):
                h = self.GenerateConcurrencyHash().hexdigest()
                if t.pDef.maxLength is not None and t.pDef.maxLength < len(h):
                    # take the right-most bytes
                    h = h[len(h) - t.pDef.maxLength:]
                if t.pDef.fixedLength:
                    if t.pDef.maxLength > len(h):
                        # we need to zero-pad our binary string
                        h = h.ljust(t.pDef.maxLength, '0')
                t.SetFromValue(h)
            elif isinstance(t, (Int16Value, Int32Value, Int64Value)):
                if t:
                    t.SetFromValue(t.value + 1)
                else:
                    t.SetFromValue(1)
            elif isinstance(t, (DateTimeValue, DateTimeOffset)):
                oldT = t.value
                t.SetFromValue(iso8601.TimePoint.FromNowUTC())
                if t.value == oldT:
                    # that was quick, push it 1s into the future
                    newTime, overflow = t.value.time.Offset(seconds=1)
                    t.SetFromValue(
                        date=t.value.date.Offset(days=overflow), time=newTime)
            elif isinstance(t, GuidValue):
                oldT = t.value
                while t.value == oldT:
                    t.SetFromValue(uuid.uuid4())
            else:
                raise ValueError(
                    "Can't auto generate concurrency token for %s" %
                    t.pDef.type)

    def ETagIsStrong(self):
        """Returns True if this entity's etag is a strong entity tag as defined
        by RFC2616::

                A "strong entity tag" MAY be shared by two entities of a
                resource only if they are equivalent by octet equality.

        The default implementation returns False which is consistent
        with the implementation of :py:meth:`GenerateConcurrencyHash`
        as that does not include the key fields."""
        return False


class EntityCollection(DictionaryLike):

    """Represents a collection of entities from an :py:class:`EntitySet`.

    To use a database analogy, EntitySet's are like tables whereas
    EntityCollections are more like the database cursors that you use to
    execute data access commands.  An entity collection may consume
    physical resources (like a database connection) and so should be
    closed with the :py:meth:`close` method when you're done.

    Entity collections support the context manager protocol in python so
    you can use them in with statements to make clean-up easier::

            with entity_set.OpenCollection() as collection:
                    if 42 in collection:
                            print "Found it!"

    The close method is called automatically when the with statement
    exits.

    Entity collections also behave like a python dictionary of
    :py:class:`Entity` instances keyed on a value representing the
    Entity's key property or properties.  The keys are either single
    values (as in the above code example) or tuples in the case of
    compound keys. The order of the values in the tuple is taken from
    the order of the :py:class:`PropertyRef` definitions in the metadata
    model.  You can obtain an entity's key from the
    :py:meth:`Entity.Key` method.

    When an EntityCollection represents an entire entity set you cannot
    use dictionary assignment to modify the collection.  You must use
    :py:meth:`insert_entity` instead where the reasons for this
    restriction are expanded on.

    For consistency with python dictionaries the following statement is
    permitted, though it is effectively a no-operation::

            etColl[key]=entity

    The above statement raises KeyError if *entity* is *not* a member of
    the entity set.  If *key* does not match the entity's key then
    ValueError is raised.

    Although you can't add an entity with assignment you can delete an
    entity with the delete operator::

            del etColl[key]

    Deletes the entity with *key* from the entity set.

    These two operations have a different meaning when a collection
    represents the subset of entities obtained through navigation.  See
    :py:class:`NavigationCollection` for details.

    *Notes for data providers*

    Derived classes MUST call super in their __init__ method to ensure
    the proper construction of the parent collection class.  The proper
    way to do this is::

            class MyCollection(EntityCollection):

                    def __init__(self,paramA,paramsB,**kwargs):
                            # paramA and paramB are examples of how to consume
                            # private keyword arguments in this method so that they
                            # aren't passed on to the next __init__
                            super(MyCollection,self).__init__(**kwargs)

    All collections require a named entity_set argument, an
    :py:class:`EntitySet` instance from which all entities in the
    collection are drawn.

    Derived classes MUST also override :py:meth:`itervalues`.  The
    implementation of itervalues must return an iterable object that
    honours the value of the expand query option, the current filter and
    the orderby rules.

    Derived classes SHOULD also override :py:meth:`__getitem__` and
    :py:meth:`__len__` as the default implementations are very
    inefficient, particularly for non-trivial entity sets.

    Writeable data sources must override py:meth:`__delitem__`.

    If a particular operation is not supported for some data-service
    specific reason then NotImplementedError must be raised.

    Writeable entity collections SHOULD override :py:meth:`clear` as the
    default implementation is very inefficient."""

    def __init__(self, entity_set, **kwargs):
        if kwargs:
            logging.debug("Unabsorbed kwargs in EntityCollection constructor")
        #: the entity set from which the entities are drawn
        self.entity_set = entity_set
        self.name = self.entity_set.name  # : the name of :py:attr:`entity_set`
        self.expand = None              #: the expand query option in effect
        self.select = None              #: the select query option in effect
        #: a filter or None for no filter (see :py:meth:`CheckFilter`)
        self.filter = None
        #: a list of orderby rules or None for no ordering
        self.orderby = None
        self.skip = None                    #: the skip query option in effect
        self.top = None                 #: the top query option in effect
        #: the provider-enforced maximum page size in effect
        self.topmax = None
        self.skiptoken = None
        self.nextSkiptoken = None
        self.inlineCount = False
        """True if inlineCount option is in effect
        
        The inlineCount option is used to alter the representation of
        the collection and, if set, indicates that the __len__ method
        will be called before iterating through the collection itself."""
        self.lastEntity = None
        self.paging = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def close(self):
        pass

    def __del__(self):
        self.close()

    def GetLocation(self):
        """Returns the location of this collection as a
        :py:class:`~pyslet.rfc2396.URI` instance.

        By default, the location is given as the location of the
        :py:attr:`entity_set` from which the entities are drawn."""
        return self.entity_set.GetLocation()

    def GetTitle(self):
        """Returns a user recognisable title for the collection.

        By default this is the fully qualified name of the entity set
        in the metadata model."""
        return self.entity_set.GetFQName()

    def Expand(self, expand, select=None):
        """Sets the expand and select query options for this collection.

        The expand query option causes the named navigation properties
        to be expanded and the associated entities to be loaded in to
        the entity instances before they are returned by this collection.

        *expand* is a dictionary of expand rules.  Expansions can be chained,
        represented by the dictionary entry also being a dictionary::

                # expand the Customer navigation property...
                { 'Customer': None }
                # expand the Customer and Invoice navigation properties
                { 'Customer':None, 'Invoice':None }
                # expand the Customer property and then the Orders property within Customer
                { 'Customer': {'Orders':None} }

        The select query option restricts the properties that are set in
        returned entities.  The *select* option is a similar dictionary
        structure, the main difference being that it can contain the
        single key '*' indicating that all *data* properties are
        selected."""
        self.entity_set.entityType.ValidateExpansion(expand, select)
        self.expand = expand
        self.select = select
        self.lastEntity = None

    def SelectKeys(self):
        """Sets the select rule to select the key property/properties only.

        Any expand rule is removed."""
        select = {}
        for k in self.entity_set.keys:
            select[k] = None
        self.Expand(None, select)

    def ExpandEntities(self, entityIterable):
        """Utility method for data providers.

        Given an object that iterates over all entities in the
        collection, returns a generator function that returns expanded
        entities with select rules applied according to
        :py:attr:`expand` and :py:attr:`select` rules.

        Data providers should use a better method of expanded entities
        if possible as this implementation simply iterates through the
        entities and calls :py:meth:`Entity.Expand` on each one."""
        for e in entityIterable:
            if self.expand or self.select:
                e.Expand(self.expand, self.select)
            yield e

    def set_filter(self, filter):   # noqa
        """Sets the filter object for this collection, see :py:meth:`CheckFilter`."""
        self.filter = filter
        self.set_page(None)
        self.lastEntity = None

    def Filter(self, filter):
        warnings.warn("EntityCollection.Filter is deprecated, use set_filter",
                      DeprecationWarning,
                      stacklevel=2)
        return self.set_filter(filter)

    def FilterEntities(self, entityIterable):
        """Utility method for data providers.

        Given an object that iterates over all entities in the
        collection, returns a generator function that returns only those
        entities that pass through the current :py:attr:`filter` object.

        Data providers should use a better method of filtering entities
        if possible as this implementation simply iterates through the
        entities and calls :py:meth:`CheckFilter` on each one."""
        for e in entityIterable:
            if self.CheckFilter(e):
                yield e

    def CheckFilter(self, entity):
        """Checks *entity* against the current filter object and returns
        True if it passes.

        This method is really a placeholder.  Filtering is not covered
        in the CSDL model itself but is a feature of the OData
        :py:mod:`pyslet.odata2.core` module.

        See
        :py:meth:`pyslet.odata2.core.EntityCollectionMixin.CheckFilter`
        for more.  The implementation in the case class simply raises
        NotImplementedError if a filter has been set."""
        if self.filter is None:
            return True
        else:
            raise NotImplementedError("Collection does not support filtering")

    def set_orderby(self, orderby):
        """Sets the orderby rules for this collection.

        *orderby* is a list of tuples, each consisting of::

                ( an order object as used by :py:meth:`CalculateOrderKey` , 1 | -1 )"""
        self.orderby = orderby
        self.set_page(None)

    def OrderBy(self, orderby):  # noqa
        warnings.warn(
            "EntityCollection.OrderBy is deprecated, use set_orderby",
            DeprecationWarning,
            stacklevel=2)
        return self.set_orderby(orderby)

    def CalculateOrderKey(self, entity, orderObject):
        """Given an entity and an order object returns the key used to
        sort the entity.

        This method is really a placeholder.  Ordering is not covered
        in the CSDL model itself but is a feature of the OData
        :py:mod:`pyslet.odata2.core` module.

        See
        :py:meth:`pyslet.odata2.core.EntityCollectionMixin.CalculateOrderKey`
        for more.  The implementation in the case class simply raises
        NotImplementedError."""
        raise NotImplementedError("Collection does not support ordering")

    def OrderEntities(self, entityIterable):
        """Utility method for data providers.

        Given an object that iterates over the entities in random order,
        returns a generator function that returns the same entities in
        sorted order (according to the :py:attr:`orderby` object).

        This implementation simply creates a list and then sorts it
        based on the output of :py:meth:`CalculateOrderKey` so is not
        suitable for use with long lists of entities.  However, if no
        ordering is required then no list is created."""
        eList = None
        if self.paging:
            eList = list(entityIterable)
            eList.sort(key=lambda x: x.Key())
        if self.orderby:
            if eList is None:
                eList = list(entityIterable)
            # we avoid Py3 warnings by doing multiple sorts with a key function
            for rule, ruleDir in reversed(self.orderby):
                eList.sort(key=lambda x: self.CalculateOrderKey(
                    x, rule), reverse=True if ruleDir < 0 else False)
        if eList:
            for e in eList:
                yield e
        else:
            for e in entityIterable:
                yield e

    def SetInlineCount(self, inlineCount):
        """Sets the inline count flag for this collection."""
        self.inlineCount = inlineCount

    def new_entity(self):
        """Returns a new py:class:`Entity` instance suitable for adding
        to this collection.

        The properties of the entity are set to their defaults, or to
        null if no default is defined (even if the property is marked
        as not nullable).

        The entity is not considered to exist until it is actually added
        to the collection.  At this point we deviate from
        dictionary-like behaviour, Instead of using assignment you must
        call :py:meth:`insert_entity`.::

                e=collection.new_entity()
                e["ID"]=1000
                e["Name"]="Fred"
                assert 1000 not in collection
                collection[1000]=e          # raises KeyError

        The correct way to add the entity is::

                collection.insert_entity(e)

        The first block of code is prone to problems as the key 1000 may
        violate the collection's key allocation policy so we raise
        KeyError when assignment is used to insert a new entity to the
        collection. This is consistent with the concept behind OData and
        Atom where new entities are POSTed to collections and the ID and
        resulting entity are returned to the caller on success because
        the service may have modified them to satisfy service-specific
        constraints."""
        return Entity(self.entity_set)

    def NewEntity(self, entity): # noqa
        warnings.warn("EntityCollection.NewEntity is deprecated, "
                      "use new_entity", DeprecationWarning,
                      stacklevel=2)
        self.new_entity(entity)
        
    def CopyEntity(self, entity):
        """Creates a new *entity* copying the value from *entity*

        The key is not copied and is initially set to NULL."""
        newEntity = self.new_entity()
        newEntity.SetFromEntity(entity)
        return newEntity

    def insert_entity(self, entity):
        """Inserts *entity* into this entity set.

        After a successful call to insert_entity:

        1.  *entity* is updated with any auto-generated values such as
                an autoincrement correct key.

        2.  :py:attr:`exists` is set to True for *entity*

        Data providers must override this method if the collection is
        writeable.

        If the call is unsuccessful then *entity* should be discarded as
        its associated bindings may be in a misleading state (when
        compared to the state of the data source itself).

        A general :py:class:`ConstraintError` will be raised when the
        insertion violates model constraints (including an attempt to
        create two entities with duplicate keys)."""
        raise NotImplementedError

    def InsertEntity(self, entity): # noqa
        warnings.warn("EntityCollection.InsertEntity is deprecated, "
                      "use insert_entity", DeprecationWarning,
                      stacklevel=2)
        self.insert_entity(entity)
        
    def update_entity(self, entity):
        """Updates *entity* which must already be in the entity set.

        Data providers must override this method if the collection is
        writeable."""
        raise NotImplementedError

    def UpdateEntity(self, entity): # noqa
        warnings.warn("EntityCollection.UpdateEntity is deprecated, "
                      "use update_entity", DeprecationWarning,
                      stacklevel=2)
        self.update_entity(entity)
        
    def update_bindings(self, entity):
        """Iterates through the :py:meth:`Entity.NavigationItems` and
        generates appropriate calls to create/update any pending
        bindings.

        Unlike the :py:meth:`Update` method, which updates all data and
        navigation values simultaneously, this method can be used to
        selectively update just the navigation properties."""
        for k, dv in entity.NavigationItems():
            dv.update_bindings()

    def UpdateBindings(self, entity): # noqa
        warnings.warn("EntityCollection.UpdateBindings is deprecated, "
                      "use update_entity", DeprecationWarning,
                      stacklevel=2)
        self.update_bindings(entity)
        
    def __getitem__(self, key):
        # key=self.entity_set.GetKey(key)
        logging.warning(
            "EntityCollection.__getitem__ without override in %s",
            self.__class__.__name__)
        if self.lastEntity and self.lastEntity.Key() == key:
            result = self.lastEntity
            return result
        for e in self.itervalues():
            self.lastEntity = e
            if e.Key() == key:
                return e
        raise KeyError(unicode(key))

    def __setitem__(self, key, value):
        if not isinstance(value, Entity) or value.entity_set is not self.entity_set:
            raise TypeError
        if key != value.Key():
            raise ValueError
        if key not in self:
            raise KeyError(unicode(key))

    def __delitem__(self, key):
        raise NotImplementedError

    def set_page(self, top, skip=0, skiptoken=None):
        """Sets the page parameters that determine the next page
        returned by :py:meth:`iterpage`.

        The skip and top query options are integers which determine the
        number of entities returned (top) and the number of entities
        skipped (skip).

        *skiptoken* is an opaque token previously obtained from a call
        to :py:meth:`next_skiptoken` on a similar collection which
        provides an index into collection prior to any additional *skip*
        being applied."""
        self.top = top
        self.skip = skip
        self.skiptoken = skiptoken
        self.nextSkiptoken = None

    def SetPage(self, top, skip=0, skiptoken=None):  # noqa
        warnings.warn("EntityCollection.SetPage is deprecated, use set_page",
                      DeprecationWarning,
                      stacklevel=2)
        return self.set_page(top, skip, skiptoken)

    def TopMax(self, topmax):
        """Sets the maximum page size for this collection.

        Data consumers should use :py:meth:`set_page` to control paging,
        however data providers can use this method to force the
        collection to limit the size of a page to at most topmax
        entities.  When topmax is in force and is less than the top
        value set in :py:meth:`set_page`,
        :py:meth:`next_skiptoken` will return a suitable value for
        identifying the next page in the collection immediately after a
        complete iteration of :py:meth:`iterpage`.

        Provider enforced paging is optional, if it is not supported
        NotImplementedError must be raised."""
        self.topmax = topmax

    def iterpage(self, set_next=False):
        """Returns an iterable subset of the values returned by
        :py:meth:`itervalues`

        The subset is defined by the top, skip and skiptoken values set
        with :py:meth:`set_page`

        If *set_next* is True then the page is automatically advanced
        so that the next call to iterpage iterates over the next page.

        Data providers should override this implementation for a more
        efficient implementation.  The default implementation simply
        wraps :py:meth:`itervalues`."""
        if self.top == 0:
            # end of paging
            return
        i = 0
        self.nextSkiptoken = None
        try:
            eMin = int(self.skiptoken, 16)
        except (TypeError, ValueError):
            # not a skip token we recognise, do nothing
            eMin = None
        if eMin is None:
            eMin = 0
        if self.skip is not None:
            eMin = self.skip + eMin
        if self.topmax:
            if self.top is None or self.top > self.topmax:
                # may be truncated
                eMax = eMin + self.topmax
                self.nextSkiptoken = "%X" % (eMin + self.topmax)
            else:
                # top not None and <= topmax
                eMax = eMin + self.top
        else:
            # no forced paging
            if self.top is None:
                eMax = None
            else:
                eMax = eMin + self.top
        try:
            self.paging = True
            if eMax is None:
                for e in self.itervalues():
                    self.lastEntity = e
                    if i >= eMin:
                        yield e
                    i = i + 1
            else:
                for e in self.itervalues():
                    self.lastEntity = e
                    if i < eMin:
                        i = i + 1
                    elif i < eMax:
                        yield e
                        i = i + 1
                    else:
                        # stop the iteration now
                        if set_next:
                            # set the next skiptoken
                            if self.nextSkiptoken is None:
                                self.skip = i
                                self.skiptoken = None
                            else:
                                self.skip = None
                                self.skiptoken = self.nextSkiptoken
                        return
        finally:
            self.paging = False
        # no more pages
        if set_next:
            self.top = self.skip = 0
            self.skiptoken = None

    def next_skiptoken(self):
        """Following a complete iteration of the generator returned by
        :py:meth:`iterpage`, this method returns the skiptoken which
        will generate the next page or None if all requested entities
        were returned."""
        return self.nextSkiptoken

    def NextSkipToken(self):  # noqa
        warnings.warn(
            "EntityCollection.NextSkipToken is deprecated, use next_skiptoken",
            DeprecationWarning,
            stacklevel=2)
        return self.next_skiptoken()

    def itervalues(self):
        """Iterates over the collection.

        The collection is filtered as defined by :py:meth:`set_filter` and
        sorted according to any rules defined by :py:meth:`set_orderby`.

        Entities are also expanded and selected according to the rules
        defined by :py:class:`Expand`.

        Data providers must override this implementation which, by
        default, returns no entities (simulating an empty collection)."""
        return []

    def __iter__(self):
        for e in self.itervalues():
            self.lastEntity = e
            yield e.Key()
        self.lastEntity = None

    def iteritems(self):
        for e in self.itervalues():
            self.lastEntity = e
            yield e.Key(), e


class NavigationCollection(EntityCollection):

    """Represents the collection of entities returned by a *navigation*
    property.

    These collections behave in the same way as entity collections
    opened from the base :py:class:`EntitySet` with the following
    exceptions::

            etColl[key]=entity

    Adds a link to *entity* from the source entity used to open the
    navigation collection.  If *key* does not match *entity*'s key then
    ValueError is raised. The entity must already exist and be a member
    of the base entity set, otherwise KeyError is raised.

    This class is used even if the navigation property is declared to
    return a single entity, rather than a collection.  In this case
    assignment will only work if the collection is currently empty. To
    *replace* an existing link use :py:meth:`replace`.

            del etColl[key]

    Deletes the link from the source entity to the entity with *key*. If
    no such link exists, KeyError is raised.

    Thie behaviour differs from the base :py:class:`EntityCollection`
    behaviour where the del operator removes the entity completely from
    the entity container.  In this case the entity still exists in the
    parent entity set, only the link is removed.

    Notes for data providers

    On construction:

    *   *entity_set* is the entity set containing the target entities,
            the collection behaves like a subset of this entity set.  It is
            passed to super

    Named arguments specific to this class:

    *   *from_entity* is the source entity being navigated

    *   *name* is the name of the navigation property being navigated

    Writeable collections must override the :py:meth:`__setitem__`
    method."""

    def __init__(self, from_entity, name, **kwargs):
        super(NavigationCollection, self).__init__(**kwargs)
        #: the name of the navigation property
        self.name = name
        self.from_entity = from_entity                    #: the source entity
        # : the :py:class:`AssociationSetEnd` that represents the source of this association
        self.from_end = self.from_entity.entity_set.navigation[self.name]
        #: the navigation property's definition in the metadata model
        self.pDef = self.from_entity.type_def[name]
        self.fromMultiplicity, self.toMultiplicity = self.from_entity.entity_set.NavigationMultiplicity(
            self.name)
        """The endpoint multiplicities of this link.  Values are defined
        by :py:class:`Multiplicity`"""

    def ExpandCollection(self):
        return ExpandedEntityCollection(
            from_entity=self.from_entity,
            name=self.name,
            entity_set=self.entity_set,
            entityList=self.values())

    def insert_entity(self, entity):
        """Inserts a new *entity* into the target entity set *and*
        simultaneously creates a link to it from the source entity."""
        with self.entity_set.OpenCollection() as baseCollection:
            baseCollection.insert_entity(entity)
            self[entity.Key()] = entity

    def update_entity(self, entity):
        with self.entity_set.OpenCollection() as baseCollection:
            baseCollection.update_entity(entity)

    def __setitem__(self, key, value):
        raise NotImplementedError(
            "Entity collection %s[%s] is read-only" %
            (self.entity_set.name, self.name))

    def __delitem__(self, key):
        raise NotImplementedError(
            "Entity collection %s[%s] is read-only" %
            (self.entity_set.name, self.name))

    def replace(self, entity):
        """This method replaces all links with a link to the single
        item, *entity*.  If the collection was empty then this is
        equivalent to __setitem__(entity.Key(),entity).

        Although for some collections this is equivalent to
        :py:meth:`clear` followed by __setitem__, this method must be
        used to combine these operations into a single call when the
        collection is required to contain exactly one link at all
        times."""
        self.clear()
        self[entity.Key()] = entity

    def Replace(self, entity): # noqa
        warnings.warn("NavigationCollection.Replace is deprecated, "
                      "use replace", DeprecationWarning,
                      stacklevel=2)
        self.replace(entity)
        

class ExpandedEntityCollection(NavigationCollection):

    """A special sub-class of :py:class:`NavigationCollection`
    used when a navigation property has been expanded.

    An expanded entity collection is a read-only, cached view of the
    entities linked from the source entity.

    Warning: although you may apply a filter and orderby rules to an
    expanded collection these are evaluated on the local copy and are
    not passed to the data source.  As a result, there may be
    differences in the way these options behave due to different
    expression semantics.

    Note for data providers:

    The named argument *entityList* passed to this constructor is a
    simple python list of the entities the expanded collection contains.
    Internally a dictionary of the entities is built to speed up access
    by key."""

    def __init__(self, entityList, **kwargs):
        super(ExpandedEntityCollection, self).__init__(**kwargs)
        self.entityList = entityList
        self.entityDict = {}
        for e in self.entityList:
            # Build a dictionary
            self.entityDict[e.Key()] = e

    def itervalues(self):
        return self.OrderEntities(
            self.ExpandEntities(
                self.FilterEntities(
                    self.entityList)))

    def __getitem__(self, key):
        result = self.entityDict[key]
        if self.CheckFilter(result):
            if self.expand or self.select:
                result.Expand(self.expand, self.select)
            return result
        raise KeyError("%s" % unicode(key))


class FunctionEntityCollection(EntityCollection):

    """Represents the collection of entities returned by a specific execution of a :py:class:`FunctionImport`"""

    def __init__(self, function, params, **kwargs):
        if function.IsEntityCollection():
            self.function = function
            self.params = params
            super(FunctionEntityCollection, self).__init__(
                entity_set=self.function.entity_set, **kwargs)
        else:
            raise TypeError(
                "Function call does not return a collection of entities")

    def Expand(self, expand, select=None):
        """This option is not supported on function results"""
        raise NotImplmentedError("Expand/Select option on Function result")

    def __setitem__(self, key, value):
        raise NotImplementedError(
            "Function %s is read-only" % self.function.name)

    def __delitem__(self, key):
        raise NotImplementedError(
            "Function %s is read-only" % self.function.name)


class FunctionCollection(object):

    """Represents a collection of :py:class:`EDMValue`.

    These objects are iterable, but are not list or dictionary-like, in
    other words, you can iterate over the collection but you can't
    address an individual item using an index or a slice."""

    def __init__(self, function, params):
        if function.IsCollection():
            if function.IsEntityCollection():
                raise TypeError(
                    "FunctionCollection must not return a collection of entities")
            self.function = function
            self.params = params
            self.name = function.name
        else:
            raise TypeError(
                "Function call does not return a collection of entities")

    def __iter__(self):
        raise NotImplementedError(
            "Unbound FunctionCollection: %s" % self.function.name)


class CSDLElement(xmlns.XMLNSElement):

    """All elements in the metadata model inherit from this class."""

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        """Called on a type definition, or type containing object to update all
        its inter-type references.

        *   scope is the :py:class:`NameTableMixin` object *containing* the
                top-level :py:class:`Schema` object(s).

        *   stopOnErrors determines the handling of missing keys.  If
                stopOnErrors is False missing keys are ignored (internal object
                references are set to None).  If stopOnErrors is True KeyError is
                raised.

        The CSDL model makes heavy use of named references between objects. The
        purpose of this method is to use the *scope* object to look up
        inter-type references and to set or update any corresponding internal
        object references."""
        pass

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        """Called on a set declaration, or set containing object to update all
        its inter-object references.

        This method works in a very similar way to :py:meth:`UpdateTypeRefs` but
        it is called afterwards.  This two-pass approach ensures that set
        declarations are linked after *all* type definitions have been updated
        in all schemas that are in scope."""
        pass


class Documentation(CSDLElement):

    """Used to document elements in the metadata model"""
    XMLNAME = (EDM_NAMESPACE, 'Documentation')
    XMLCONTENT = xmlns.ElementType.ElementContent


class TypeRef(object):

    """Represents a type reference.

    Created from a formatted string type definition and a scope (in
    which type definitions are looked up)."""

    def __init__(self, type_def, scope):
        self.collection = False     #: True if this type is a collection type
        # : a :py:class:`SimpleType` value if this is a scalar type
        self.simpleTypeCode = None
        #: a :py:class:`ComplexType` or :py:class:`EntityType` instance.
        self.type_def = None
        if "(" in type_def and type_def[-1] == ')':
            if type_def[:type_def.index('(')].lower() != u"collection":
                raise KeyError("%s is not a valid type" % type_def)
            self.collection = True
            typeName = type_def[type_def.index('(') + 1:-1]
        else:
            typeName = type_def
        try:
            self.simpleTypeCode = SimpleType.DecodeLowerValue(typeName)
        except ValueError:
            # must be a complex or entity type defined in scope
            self.simpleTypeCode = None
            self.type_def = scope[typeName]
            if not isinstance(self.type_def, (ComplexType, EntityType)):
                raise KeyError("%s is not a valid type" % typeName)


class Using(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Using')

#: we define the constant MAX to represent the spacial 'max' value of maxLength
MAX = -1


def DecodeMaxLength(value):
    """Decodes a maxLength value from a unicode string.

    "The maxLength facet accepts a value of the literal string "max" or a
    positive integer with value ranging from 1 to 2^31"

    The value 'max' is returned as the value :py:data:`MAX`"""
    if value.lower() == "max":
        return MAX
    else:
        result = xsi.DecodeInteger(value)
        if result < 1:
            raise ValueError("Can't read maxLength from %s" % repr(value))
        return result


def EncodeMaxLength(value):
    """Encodes a maxLength value as a unicode string."""
    if value == MAX:
        return "max"
    else:
        return xsi.EncodeInteger(value)


class ConcurrencyMode(xsi.Enumeration):

    """ConcurrencyMode defines constants for the concurrency modes defined by CSDL
    ::

            ConcurrencyMode.Fixed
            ConcurrencyMode.DEFAULT == ConcurrencyMode.none

    Note that although 'Fixed' and 'None' are the correct values
    lower-case aliases are also defined to allow the value 'none' to be
    accessible through normal attribute access.  In most cases you won't
    need to worry as a test such as the following is sufficient:

            if property.concurrencyMode==ConcurrencyMode.Fixed:
                    # do something with concurrency tokens

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'None': 1,
        'Fixed': 2
    }
xsi.MakeEnumeration(ConcurrencyMode)
xsi.MakeLowerAliases(ConcurrencyMode)


class Property(CSDLElement):

    """Models a property of an :py:class:`EntityType` or
    :py:class:`ComplexType`.

    Instances of this class are callable, taking an optional string
    literal.  They return a new
    :py:class:`EDMValue` instance with a value set from the
    optional literal or NULL if no literal was supplied.  Complex values
    can't be created from a literal."""

    XMLNAME = (EDM_NAMESPACE, 'Property')

    XMLATTR_Name = 'name'
    XMLATTR_Type = 'type'
    XMLATTR_Nullable = ('nullable', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLATTR_DefaultValue = 'defaultValue'
    XMLATTR_MaxLength = ('maxLength', DecodeMaxLength, EncodeMaxLength)
    XMLATTR_FixedLength = ('fixedLength', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLATTR_Precision = ('precision', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_Scale = ('scale', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_Unicode = ('unicode', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLATTR_Collation = 'collation'
    XMLATTR_SRID = 'SRID'
    XMLATTR_CollectionKind = 'collectionKind'
    XMLATTR_ConcurrencyMode = (
        'concurrencyMode',
        ConcurrencyMode.DecodeLowerValue,
        ConcurrencyMode.EncodeValue)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = "Default"           #: the declared name of the property
        self.type = "Edm.String"        #: the name of the property's type
        # : one of the :py:class:`SimpleType` constants if the property has a simple type
        self.simpleTypeCode = None
        #: the associated :py:class:`ComplexType` if the property has a complex type
        self.complexType = None
        #: if the property may have a null value
        self.nullable = True
        #: a string containing the default value for the property or None if no default is defined
        self.defaultValue = None
        #: the maximum length permitted for property values
        self.maxLength = None
        #: a boolean indicating that the property must be of length :py:attr:`maxLength`
        self.fixedLength = None
        #: a positive integer indicating the maximum number of decimal digits (decimal values)
        self.precision = None
        #: a non-negative integer indicating the maximum number of decimal digits to the right of the point
        self.scale = None
        #: a boolean indicating that a string property contains unicode data
        self.unicode = None
        self.collation = None
        self.SRID = None
        self.collectionKind = None
        self.concurrencyMode = None
        self.TypeRef = None
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        try:
            self.simpleTypeCode = SimpleType.DecodeLowerValue(self.type)
            self.complexType = None
        except ValueError:
            # must be a complex type defined elsewhere
            self.simpleTypeCode = None
            try:
                self.complexType = scope[self.type]
                if not isinstance(self.complexType, ComplexType):
                    raise KeyError(
                        "%s is not a simple or ComplexType" % self.type)
            except KeyError:
                self.complexType = None
                if stopOnErrors:
                    raise

    def __call__(self, literal=None):
        result = EDMValue.NewValue(self)
        if isinstance(result, SimpleValue) and literal is not None:
            result.SetFromLiteral(literal)
        return result


class NavigationProperty(CSDLElement):

    """Models a navigation property of an :py:class:`EntityType`."""
    XMLNAME = (EDM_NAMESPACE, 'NavigationProperty')

    XMLATTR_Name = 'name'
    XMLATTR_Relationship = 'relationship'
    XMLATTR_ToRole = 'toRole'
    XMLATTR_FromRole = 'fromRole'

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the declared name of the navigation property
        self.name = "Default"
        # : the name of the association described by this link
        self.relationship = None
        # : the :py:class:`Association` described by this link
        self.association = None
        self.fromRole = None        #: the name of this link's source role
        self.toRole = None      #: the name of this link's target role
        #: the :py:class:`AssociationEnd` instance representing this link's source
        self.from_end = None
        #: the :py:class:`AssociationEnd` instance representing this link's target
        self.toEnd = None
        #: the :py:class:`NavigationProperty` that provides the back link (or None, if this link is one-way)
        self.backLink = None
        self.Documentation = None  # : the optional :py:class:`Documentation`
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        # must be a complex type defined elsewhere
        self.association = self.from_end = self.toEnd = None
        try:
            self.association = scope[self.relationship]
            if not isinstance(self.association, Association):
                raise KeyError("%s is not an association" % self.relationship)
            self.from_end = self.association[self.fromRole]
            if self.from_end is None or not isinstance(self.from_end, AssociationEnd):
                raise KeyError(
                    "%s is not a valid end-point for %s" %
                    (self.fromRole, self.relationship))
            self.toEnd = self.association[self.toRole]
            if self.toEnd is None or not isinstance(self.toEnd, AssociationEnd):
                raise KeyError(
                    "%s is not a valid end-point for %s" %
                    (self.fromRole, self.relationship))
        except KeyError:
            self.association = self.from_end = self.toEnd = None
            if stopOnErrors:
                raise


class Key(CSDLElement):

    """Models the key fields of an :py:class:`EntityType`"""
    XMLNAME = (EDM_NAMESPACE, 'Key')

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.PropertyRef = []       #: a list of :py:class:`PropertyRef`

    def GetChildren(self):
        for child in self.PropertyRef:
            yield child

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        for pr in self.PropertyRef:
            pr.UpdateTypeRefs(scope, stopOnErrors)


class PropertyRef(CSDLElement):

    """Models a reference to a single property within a :py:class:`Key`."""
    XMLNAME = (EDM_NAMESPACE, 'PropertyRef')

    XMLATTR_Name = 'name'

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = 'Default'       #: the name of this (key) property
        #: the :py:class:`Property` instance of this (key) property
        self.property = None

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        """Sets :py:attr:`property`"""
        self.property = None
        try:
            type_def = self.FindParent(EntityType)
            if type_def is None:
                raise KeyError(
                    "PropertyRef %s has no parent EntityType" % self.name)
            self.property = type_def[self.name]
            if not isinstance(self.property, Property):
                raise KeyError("%s is not a Property" % self.name)
        except KeyError:
            self.property = None
            if stopOnErrors:
                raise


class Type(NameTableMixin, CSDLElement):

    """An abstract class for both Entity and Complex types.

    Types inherit from :py:class:`NameTableMixin` to allow them to
    behave as scopes in their own right.  The named properties are
    declared in the type's scope enabling you so use them as
    dictionaries to look up property definitions.

    Because of the way nested scopes work, this means that you
    can concatenate names to do a deep look up, for example, if
    Person is a defined type::

            Person['Address']['City'] is Person['Address.City']"""
    XMLATTR_Name = ('name', ValidateSimpleIdentifier, None)
    XMLATTR_BaseType = 'baseType'
    XMLATTR_Abstract = ('abstract', xsi.DecodeBoolean, xsi.EncodeBoolean)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        self.name = "Default"       #: the declared name of this type
        self.baseType = None        #: the name of the base-type for this type
        self.abstract = False
        self.Documentation = None  # : the optional :py:class:`Documentation`
        self.Property = []      #: a list of :py:class:`Property`
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.Property,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def ContentChanged(self):
        for p in self.Property:
            self.Declare(p)

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        for p in self.Property:
            p.UpdateTypeRefs(scope, stopOnErrors)

    def GetFQName(self):
        """Returns the full name of this type, including the schema namespace prefix."""
        schema = self.FindParent(Schema)
        if schema is None:
            return name
        else:
            return string.join((schema.name, '.', self.name), '')


class EntityType(Type):

    """Models the key and the collection of properties that define a set
    of :py:class:`Entity`"""

    XMLNAME = (EDM_NAMESPACE, 'EntityType')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        Type.__init__(self, parent)
        self.Key = None             #: the :py:class:`Key`
        # : a list of :py:class:`NavigationProperty`
        self.NavigationProperty = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        if self.Key:
            yield self.Key
        for child in itertools.chain(
                self.Property,
                self.NavigationProperty,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def ContentChanged(self):
        super(EntityType, self).ContentChanged()
        for np in self.NavigationProperty:
            self.Declare(np)

    def ValidateExpansion(self, expand, select):
        """A utility method for data providers.

        Checks the expand and select options, as described in
        :py:meth:`EntityCollection.Expand` for validity raising
        ValueError if they violate the OData specification.

        Specifically the following are checked:

        1.  That "*" only ever appears as the last item in a select
                path

        2.  That nothing appears after a simple property in a select
                path

        3.  That all names are valid property names

        4.  That all expanded names are those of navigation properties"""
        if expand is None:
            expand = {}
        if select is None:
            select = {}
        for name, value in select.iteritems():
            if name == "*":
                # must be the last item in the selectItem
                if value is not None:
                    raise ValueError("selectItem after *")
            else:
                try:
                    p = self[name]
                    if isinstance(p, Property):
                        if value is not None:
                            raise ValueError(
                                "selectItem after selectedProperty %s" % name)
                    elif isinstance(p, NavigationProperty):
                        # for a navigation property, we have to find the target
                        # entity type
                        if name in expand:
                            subExpand = expand[name]
                        else:
                            subExpand = None
                        p.toEnd.entityType.ValidateExpansion(subExpand, value)
                    else:
                        raise KeyError
                except KeyError:
                    raise ValueError(
                        "%s is not a property of %s" % (name, self.name))
        for name, value in expand.iteritems():
            try:
                p = self[name]
                if isinstance(p, NavigationProperty):
                    # only navigation properties need apply
                    if name in select:
                        # then we've already been here
                        pass
                    else:
                        p.toEnd.entityType.ValidateExpansion(value, None)
                else:
                    raise KeyError
            except KeyError:
                raise ValueError(
                    "%s is not a navigation property of %s" %
                    (name, self.name))

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        super(EntityType, self).UpdateTypeRefs(scope, stopOnErrors)
        for p in self.NavigationProperty:
            p.UpdateTypeRefs(scope, stopOnErrors)
        self.Key.UpdateTypeRefs(scope, stopOnErrors)


class ComplexType(Type):

    """Models the collection of properties that define a
    :py:class:`Complex` value.

    This class is a trivial sub-class of :py:class:`Type`"""
    XMLNAME = (EDM_NAMESPACE, 'ComplexType')


class Multiplicity:

    """Defines constants for representing association end multiplicities."""
    ZeroToOne = 0  # :  0..1
    One = 1  # :    1
    Many = 2  # :   \*
    Encode = {0: '0..1', 1: '1', 2: '*'}

MutliplicityMap = {
    '0..1': Multiplicity.ZeroToOne,
    '1': Multiplicity.One,
    '*': Multiplicity.Many
}


def DecodeMultiplicity(src):
    """Decodes a :py:class:`Multiplicity` value from a unicode string.

    The valid strings are "0..1", "1" and "*" """
    return MutliplicityMap.get(src.strip(), None)


def EncodeMultiplicity(value):
    """Encodes a :py:class:`Multiplicity` value as a unicode string."""
    return Multiplicity.Encode.get(value, '')


class Association(NameTableMixin, CSDLElement):

    """Models an association.

    This class inherits from :py:class:`NameTableMixin` to enable it to
    behave like a scope in its own right.  The contained
    :py:class:`AssociationEnd` instances are declared in the association
    scope by role name."""
    XMLNAME = (EDM_NAMESPACE, 'Association')
    XMLATTR_Name = 'name'

    def __init__(self, parent):
        NameTableMixin.__init__(self)
        CSDLElement.__init__(self, parent)
        #: the name declared for this association
        self.name = "Default"
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        #: a list of :py:class:`AssociationEnd` instances
        self.AssociationEnd = []
        self.ReferentialConstraint = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    @classmethod
    def GetElementClass(cls, name):
        if xmlns.NSEqualNames((EDM_NAMESPACE, 'End'), name, EDM_NAMESPACE_ALIASES):
            return AssociationEnd
        else:
            return None

    def ContentChanged(self):
        for ae in self.AssociationEnd:
            self.Declare(ae)

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in self.AssociationEnd:
            yield child
        if self.ReferentialConstraint:
            yield self.ReferentialConstraint
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        for iEnd in self.AssociationEnd:
            iEnd.UpdateTypeRefs(scope, stopOnErrors)
        # now go through the navigation properties of the two entity types
        # searching for the properties that refer to this association
        # Once we find them, set the back-link
        npList = []
        for iEnd in self.AssociationEnd:
            for np in iEnd.entityType.NavigationProperty:
                if scope[np.relationship] is self:
                    npList.append(np)
                    break
        if len(npList) == 2:
            # Not always the case, the link may only be navigable one way
            npList[0].backLink = npList[1]
            npList[1].backLink = npList[0]


class AssociationEnd(CSDLElement):

    """Models one end of an :py:class:`Association`."""
    # XMLNAME=(EDM_NAMESPACE,'End')

    XMLATTR_Role = 'name'
    XMLATTR_Type = 'type'
    XMLATTR_Multiplicity = (
        'multiplicity', DecodeMultiplicity, EncodeMultiplicity)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the role-name given to this end of the link
        self.name = None
        #: name of the entity type this end links to
        self.type = None
        self.entityType = None  # : :py:class:`EntityType` this end links to
        self.multiplicity = 1       #: a :py:class:`Multiplicity` constant
        #: the other :py:class:`AssociationEnd` of this link
        self.otherEnd = None
        self.Documentation = None  # : the optional :py:class:`Documentation`
        self.OnDelete = None

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        if self.OnDelete:
            yield self.OnDelete
        for child in CSDLElement.GetChildren(self):
            yield child

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        try:
            self.entityType = self.otherEnd = None
            self.entityType = scope[self.type]
            if not isinstance(self.entityType, EntityType):
                raise "AssociationEnd not bound to EntityType (%s)" % self.type
            if not isinstance(self.parent, Association) or not len(self.parent.AssociationEnd) == 2:
                raise ModelIncomplete(
                    "AssociationEnd has missing or incomplete parent (Role=%s)" %
                    self.name)
            for iEnd in self.parent.AssociationEnd:
                if iEnd is self:
                    continue
                else:
                    self.otherEnd = iEnd
        except KeyError:
            self.entityType = self.otherEnd = None
            if stopOnErrors:
                raise


class EntityContainer(NameTableMixin, CSDLElement):

    """Models an entity container in the metadata model.

    An EntityContainer inherits from :py:class:`NameTableMixin` to
    enable it to behave like a scope.  The :py:class:`EntitySet`
    instances and :py:class:`AssociationSet` instances it contains are
    declared within the scope."""
    XMLNAME = (EDM_NAMESPACE, 'EntityContainer')
    XMLATTR_Name = ('name', ValidateSimpleIdentifier, None)
    XMLATTR_Extends = 'extends'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        self.name = "Default"           #: the declared name of the container
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        self.FunctionImport = []
        #: a list of :py:class:`EntitySet` instances
        self.EntitySet = []
        #: a list of :py:class:`AssociationSet` instances
        self.AssociationSet = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.EntitySet,
                self.AssociationSet,
                self.FunctionImport,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def ContentChanged(self):
        for t in self.EntitySet + self.AssociationSet + self.FunctionImport:
            self.Declare(t)

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        for child in self.EntitySet + self.AssociationSet + self.FunctionImport:
            child.UpdateSetRefs(scope, stopOnErrors)
        for child in self.EntitySet:
            child.UpdateNavigation()


class EntitySet(CSDLElement):

    """Represents an EntitySet in the metadata model."""
    XMLNAME = (EDM_NAMESPACE, 'EntitySet')
    XMLATTR_Name = ('name', ValidateSimpleIdentifier, None)
    XMLATTR_EntityType = 'entityTypeName'
    XMLCONTENT = xmlns.ElementType.ElementContent

# EntityCollectionClass=EntityCollection  #: the class to use for
# representing entity collections

    def __init__(self, parent):
        super(EntitySet, self).__init__(parent)
        #: the declared name of the entity set
        self.name = "Default"
        #: the name of the entity type of this set's elements
        self.entityTypeName = ""
        #: the :py:class:`EntityType` of this set's elements
        self.entityType = None
        #: a list of the names of this entity set's keys in their declared order
        self.keys = []
        #: a mapping from navigation property names to :py:class:`AssociationSetEnd` instances
        self.navigation = {}
        self.linkEnds = {}
        """A mapping from :py:class:`AssociationSetEnd` instances that
        reference this entity set to navigation property names (or None
        if this end of the association is not bound to a named
        navigation property)"""
        self.unboundPrincipal = None
        """An :py:class:`AssociationSetEnd` that represents our end of
        an association with an unbound principal or None if all
        principals are bound.
        
        What does that mean?  It means that there is an association set
        bound to us where the other role has a multiplicity of 1
        (required) but our entity type does not have a navigation
        property bound to the association.  As a result, our entities
        can only be created by a deep insert from the principal (the
        entity set at the other end of the association).
        
        Clear as mud?  An example may help.  Suppose that each Order
        entity must have an associated Customer but (perhaps perversely)
        there is no navigation link from Order to Customer, only from
        Customer to Order.  Attempting to create an Order in the base
        collection of Orders will always fail::
        
            with Orders.OpenCollection() as collection:
                order=collection.new_entity()
                # set order fields here
                collection.insert_entity(order)
                # raises ConstraintError as order is not bound to a customer

        Instead, you have to create new orders from a Customer entity::
        
            with Customers.OpenCollection() as collectionCustomers:
                # get the existing customer
                customer=collectionCustomers['ALFKI']
                with customer['Orders'].OpenCollection() as collectionOrders:
                    # create a new order
                    order=collectionOrders.new_entity()
                    # ... set order details here
                    collectionOrders.insert_entity(order)

        You can also use a deep insert::
        
            with Customers.OpenCollection() as collectionCustomers,
                    Orders.OpenCollection() as collectionOrders:
                customer=collectionCustomers.new_entity()
                # set customer details here
                order=collectionOrders.new_entity()
                # set order details here
                customer['Orders'].BindEntity(order)
                collectionCustomers.insert_entity(customer)
        
        For the avoidance of doubt, an entity set can't have two unbound
        principals because if it did you would never be able to create
        entities in it!"""
        self.binding = (EntityCollection, {})
        self.navigationBindings = {}
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []
        self.location = None

    def GetFQName(self):
        """Returns the fully qualified name of this entity set."""
        name = []
        if isinstance(self.parent, EntityContainer):
            if isinstance(self.parent.parent, Schema):
                name.append(self.parent.parent.name)
            name.append(self.parent.name)
        name.append(self.name)
        return string.join(name, '.')

    def GetLocation(self):
        """Returns a :py:class:`pyslet.rfc2396.URI` instance
        representing the location for this entity set."""
        return self.location

    def SetLocation(self):
        """Sets the location of this entity set by resolving a relative
        path consisting of::

                [ EntityContainer.name '.' ] name

        The resolution of URIs is done in accordance with the XML
        specification, so is affected by any xml:base attributes set on
        parent elements or by the original base URI used to load the
        metadata model.  If no base URI can be found then the location
        remains expressed in relative terms."""
        container = self.FindParent(EntityContainer)
        if container:
            path = container.name + '.' + self.name
        else:
            path = self.name
        self.location = self.ResolveURI(path)

    def ContentChanged(self):
        super(EntitySet, self).ContentChanged()
        self.SetLocation()

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        try:
            self.entityType = scope[self.entityTypeName]
            if not isinstance(self.entityType, EntityType):
                raise KeyError("%s is not an EntityType" % self.entityTypeName)
            self.keys = []
            for kp in self.entityType.Key.PropertyRef:
                self.keys.append(kp.name)
        except KeyError:
            logging.error(
                "EntitySet %s has undeclared type: %s",
                self.name,
                self.entityTypeName)
            self.entityType = None
            if stopOnErrors:
                raise

    def UpdateNavigation(self):
        container = self.FindParent(EntityContainer)
        if container and self.entityType:
            for association_set in container.AssociationSet:
                for iEnd in association_set.AssociationSetEnd:
                    if iEnd.entity_set is self:
                        # there is no requirement that says every
                        # AssociationSetEnd must be represented by a
                        # corresponding navigation property.
                        navName = None
                        for np in self.entityType.NavigationProperty:
                            if iEnd.associationEnd is np.from_end:
                                navName = np.name
                                break
                        if navName:
                            self.navigation[navName] = iEnd
                        elif iEnd.otherEnd.associationEnd.multiplicity == Multiplicity.One:
                            if self.unboundPrincipal is None:
                                self.unboundPrincipal = iEnd
                            else:
                                raise ModelConstraintError(
                                    "Entity set %s has more than one unbound principal" %
                                    self.name)
                        self.linkEnds[iEnd] = navName
            for np in self.entityType.NavigationProperty:
                if np.name not in self.navigation:
                    raise ModelIncomplete(
                        "Navigation property %s in EntitySet %s is not bound to an association set" %
                        (np.name, self.name))

    def KeyKeys(self):
        warnings.warn(
            "EntitySet.KeyKeys is deprecated, use keys attribute instead",
            DeprecationWarning,
            stacklevel=2)
        return self.keys

    def GetKey(self, keylike):
        """Extracts a key value suitable for using as a key in an
        :py:class:`EntityCollection` based on this entity set.

        Keys are represented as python values (as described in
        :py:class:`SimpleValue`) or as tuples of python values in the
        case of compound keys.  The order of the values in a compound
        key is the order in which the Key properties are defined in the
        corresponding EntityType definition.

        If *keylike* is already in the correct format for this entity
        type then it is returned unchanged.

        If the key is single-valued and *keylike* is a tuple containing
        a single value then the single value is returned without the
        tuple wrapper.

        If *keylike* is a dictionary, or an :py:class:`Entity` instance,
        which maps property names to values (or to
        :py:class:`SimpleValue` instances) the key is calculated from it
        by extracting the key properties.  As a special case, a value
        mapped with a dictionary key of the empty string is assumed to
        be the value of the key property for an entity type with a
        single-valued key, but only if the key property's name is not
        itself in the dictionary.

        If *keylike* cannot be turned in to a valid key the KeyError is
        raised."""
        if isinstance(keylike, TupleType):
            if len(self.entityType.Key.PropertyRef) == 1:
                if len(keylike) == 1:
                    return keylike[0]
                else:
                    raise KeyError(
                        "Unexpected compound key: %s" % repr(keylike))
            else:
                return keylike
        elif isinstance(keylike, DictType) or isinstance(keylike, Entity):
            k = []
            for kp in self.entityType.Key.PropertyRef:
                try:
                    kv = keylike[kp.name]
                except KeyError:
                    if len(self.entityType.Key.PropertyRef) == 1:
                        # a single key, look up the empty string instead
                        if '' in keylike:
                            kv = keylike['']
                        else:
                            raise
                    else:
                        raise
                if isinstance(kv, SimpleValue):
                    kv = kv.value
                k.append(kv)
            if len(k) == 1:
                return k[0]
            else:
                return tuple(k)
        else:
            #: assume it is of the correct type to be the key
            return keylike

    def GetKeyDict(self, key):
        """Given a key from this entity set, returns a key dictionary.

        The result is a mapping from named properties to
        :py:class:`SimpleValue` instances.  As a special case, if a
        single property defines the entity key it is represented using
        the empty string, *not* the property name."""
        keyDict = {}
        if not isinstance(key, TupleType):
            noName = True
            key = (key,)
        else:
            noName = False
        ki = iter(key)
        for kp in self.entityType.Key.PropertyRef:
            k = ki.next()
            #   create a new simple value to hold k
            kv = kp.property()
            kv.SetFromValue(k)
            if noName:
                keyDict[''] = kv
            else:
                keyDict[kp.property.name] = kv
        return keyDict

    def Bind(self, entityCollectionBinding, **extraArgs):
        """Binds this entity set to a specific class or callable used by
        :py:meth:`OpenCollection`

        *entityCollectionBinding* must be a class (or other callable)
        that returns an :py:class:`EntityCollection` instance, by
        default we are bound to the default EntityCollection class which
        behaves like an empty collection.

        *extraArgs* is a python dict of named arguments to pass to the
        binding callable"""
        self.binding = entityCollectionBinding, extraArgs

    def OpenCollection(self):
        """Returns an :py:class:`EntityCollection` instance suitable for
        accessing the entities themselves."""
        cls, extraArgs = self.binding
        return cls(entity_set=self, **extraArgs)

    def BindNavigation(self, name, entityCollectionBinding, **extraArgs):
        """Binds the navigation property *name* to a class or callable
        used by :py:meth:`OpenNavigation`

        *entityCollectionBinding* must be a class (or other callable)
        that returns a :py:class:`NavigationCollection` instance.
        By default we are bound to the default
        NavigationCollection class which behaves like an empty
        collection.

        *extraArgs* is a python dict of named arguments to pass to the
        binding callable"""
        self.navigationBindings[name] = (entityCollectionBinding, extraArgs)

    def OpenNavigation(self, name, sourceEntity):
        """Returns a :py:class:`NavigationCollection` instance
        suitable for accessing the entities obtained by navigating from
        *sourceEntity*, an :py:class:`Entity` instance, via the
        navigation property with *name*."""
        cls, extraArgs = self.navigationBindings[name]
        linkEnd = self.navigation[name]
        toEntitySet = linkEnd.otherEnd.entity_set
        return cls(
            from_entity=sourceEntity,
            name=name,
            entity_set=toEntitySet,
            **extraArgs)

    def NavigationTarget(self, name):
        """Returns the target entity set of navigation property *name*"""
        linkEnd = self.navigation[name]
        return linkEnd.otherEnd.entity_set

    def NavigationMultiplicity(self, name):
        """Returns the :py:class:`Multiplicity` of both the source and
        the target of the named navigation property, as a
        tuple, for example, if *customers* is an entity set from
        the sample OData service::

                customers.NavigationMultiplicity['Orders']==(Multiplicity.ZeroToOne,Multiplicity.Many)"""
        linkEnd = self.navigation[name]
        return linkEnd.associationEnd.multiplicity, linkEnd.otherEnd.associationEnd.multiplicity

    def IsEntityCollection(self, name):
        """Returns True if more than one entity is possible when navigating the named property."""
        return self.NavigationMultiplicity(name)[1] == Multiplicity.Many


class AssociationSet(CSDLElement):

    """Represents an association set in the metadata model.

    The purpose of the association set is to bind the ends of an
    association to entity sets in the container.

    Contrast this with the association element which merely describes
    the association between entity types.

    At first sight this part of the entity data model can be confusing
    but imagine an entity container that contains two entity sets
    that have the same entity type.  Any navigation properties that
    reference this type will need to be explicitly bound to one or
    other of the entity sets in the container.

            As an aside, it isn't really clear if the model was intended to
            be used this way.  It may have been intended that the entity type
            in the definition of an entity set should be unique within the
            scope of the entity container."""
    XMLNAME = (EDM_NAMESPACE, 'AssociationSet')
    XMLATTR_Name = ('name', ValidateSimpleIdentifier, None)
    XMLATTR_Association = 'associationName'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the declared name of this association set
        self.name = "Default"
        #: the name of the association definition
        self.associationName = ""
        self.association = None     #: the :py:class:`Association` definition
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        # : a list of :py:class:`AssociationSetEnd` instances
        self.AssociationSetEnd = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    @classmethod
    def GetElementClass(cls, name):
        if xmlns.NSEqualNames((EDM_NAMESPACE, 'End'), name, EDM_NAMESPACE_ALIASES):
            return AssociationSetEnd
        else:
            return None

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.AssociationSetEnd,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        try:
            self.association = scope[self.associationName]
            if not isinstance(self.association, Association):
                raise KeyError("%s is not an Association" %
                               self.associationName)
            for iEnd in self.AssociationSetEnd:
                iEnd.UpdateSetRefs(scope, stopOnErrors)
        except KeyError:
            self.association = None
            if stopOnErrors:
                raise


class AssociationSetEnd(CSDLElement):

    """Represents the links between two actual sets of entities in the
    metadata model.

    The :py:meth:`GetQualifiedName` method defines the identity of this
    element.  The built-in Python hash function returns a hash based on
    this value and the associated comparison functions are also
    implemented enabling these elements to be added to ordinary Python
    dictionaries.

    Oddly, role names are sometimes treated as optional but it can make
    it a challenge to work out which end of the association is which
    when we are actually using the model if one or both are missing.
    The algorithm we use is to use role names if either are given,
    otherwise we match the entity types.  If these are also identical
    then the choice is arbitrary.  To prevent confusion missing role
    names are filled in when the metadata model is loaded."""
    # XMLNAME=(EDM_NAMESPACE,'End')
    XMLATTR_Role = 'name'
    XMLATTR_EntitySet = 'entitySetName'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the role-name given to this end of the link
        self.name = None
        #: name of the entity set this end links to
        self.entitySetName = None
        #: :py:class:`EntitySet` this end links to
        self.entity_set = None
        # : :py:class:`AssociationEnd` that defines this end of the link
        self.associationEnd = None
        #: the other :py:class:`AssociationSetEnd` of this link
        self.otherEnd = None
        #: the optional :py:class:`Documentation`
        self.Documentation = None

    def GetQualifiedName(self):
        """A utility function to return a qualified name.

        The qualified name comprises the name of the parent
        :py:class:`AssociationSet` and the role name."""
        if isinstance(self.parent, AssociationSet):
            return self.parent.name + "." + self.name
        else:
            return "." + self.name

    def __hash__(self):
        return hash(self.GetQualifiedName())

    def __eq__(self, other):
        if isinstance(other, AssociationSetEnd):
            return cmp(self.GetQualifiedName(), other.GetQualifiedName()) == 0
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __cmp__(self, other):
        if isinstance(other, AssociationSetEnd):
            return cmp(self.GetQualifiedName(), other.GetQualifiedName())
        else:
            raise TypeError

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in CSDLElement.GetChildren(self):
            yield child

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        try:
            self.entity_set = self.otherEnd = self.associationEnd = None
            container = self.FindParent(EntityContainer)
            if container:
                self.entity_set = container[self.entitySetName]
            if not isinstance(self.entity_set, EntitySet):
                raise ModelIncomplete(
                    "AssociationSetEnd not bound to EntitySet (%s)" %
                    self.entitySetName)
            if not isinstance(self.parent, AssociationSet) or not len(self.parent.AssociationSetEnd) == 2:
                raise ModelIncomplete(
                    "AssociationSetEnd has missing or incomplete parent (Role=%s)" %
                    self.name)
            for iEnd in self.parent.AssociationSetEnd:
                if iEnd is self:
                    continue
                else:
                    self.otherEnd = iEnd
            for iEnd in self.parent.association.AssociationEnd:
                if self.name:
                    if self.name == iEnd.name:
                        # easy case, names match
                        self.associationEnd = iEnd
                        break
                elif self.otherEnd.name:
                    if self.otherEnd.name == iEnd.name:
                        # so we match the end of iEnd!
                        self.associationEnd = iEnd.otherEnd
                        # Fix up the role name while we're at it
                        self.name = self.associationEnd.name
                        break
                else:
                    # hard case, two blank associations
                    if iEnd.entityType is self.entity_set.entityType:
                        self.associationEnd = iEnd
                        self.name = self.associationEnd.name
                        break
            if self.associationEnd is None:
                raise ModelIncomplete(
                    "Failed to match AssociationSetEnds to their definitions: %s" %
                    self.parent.name)
        except KeyError:
            self.entity_set = self.otherEnd = self.associationEnd = None
            if stopOnErrors:
                raise


class FunctionImport(CSDLElement):

    """Represents a FunctionImport in an entity collection."""
    XMLNAME = (EDM_NAMESPACE, 'FunctionImport')

    XMLATTR_Name = ('name', ValidateSimpleIdentifier, None)
    XMLATTR_ReturnType = 'returnType'
    XMLATTR_EntitySet = 'entitySetName'

    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the declared name of this function import
        self.name = "Default"
        self.returnType = ""            #: the return type of the function
        #: reference to the return type definition
        self.returnTypeRef = None
        #: the name of the entity set from which the return values are taken
        self.entitySetName = ''
        #: the :py:class:`EntitySet` corresponding to :py:attr:`entitySetName`
        self.entity_set = None
        #: a callable to use when executing this function (see :py:meth:`Bind`)
        self.binding = None, {}
        self.Documentation = None
        self.ReturnType = []
        self.Parameter = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.ReturnType,
                self.Parameter,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        """Sets :py:attr:`entity_set` if applicable"""
        try:
            self.entity_set = None
            self.returnTypeRef = TypeRef(self.returnType, scope)
            if self.entitySetName:
                container = self.FindParent(EntityContainer)
                if container:
                    self.entity_set = container[self.entitySetName]
                if not isinstance(self.entity_set, EntitySet):
                    raise KeyError("%s is not an EntitySet" %
                                   self.entitySetName)
            else:
                if isinstance(self.returnTypeRef.type_def, EntityType) and self.returnTypeRef.collection:
                    raise KeyError(
                        "Return type %s requires an EntitySet" %
                        self.returnType)
            for p in self.Parameter:
                p.UpdateSetRefs(scope, stopOnErrors)
        except KeyError:
            self.returnTypeRef = self.entity_set = None
            if stopOnErrors:
                raise

    def IsCollection(self):
        """Returns True if this FunctionImport returns a collection."""
        return self.returnTypeRef.collection

    def IsEntityCollection(self):
        """Returns True if this FunctionImport returns a collection of entities."""
        return self.entity_set is not None and self.returnTypeRef.collection

    def Bind(self, callable, **extraArgs):
        """Binds this instance of FunctionImport to a callable with the
        following signature and the appropriate return type as per the
        :py:meth:`Execute` method:

        callable(:py:class:`FunctionImport` instance, params dictionary, **extraArgs)

        Note that a derived class of :py:class:`FunctionEntityCollection` can
        be used directly."""
        self.binding = callable, extraArgs

    def Execute(self, params):
        """Executes this function (with optional params), returning one of the
        following, depending on the type of function:

        *   An instance of :py:class:`EDMValue`

        *   An instance of :py:class:`Entity`

        *   An instance of :py:class:`FunctionCollection`

        *   An instance of :py:class:`FunctionEntityCollection`  """
        f, extraArgs = self.binding
        if f is not None:
            return f(self, params, **extraArgs)
        else:
            raise NotImplementedError("Unbound FunctionImport: %s" % self.name)


class ParameterMode(xsi.Enumeration):

    """ParameterMode defines constants for the parameter modes defined by CSDL
    ::

            ParameterMode.In
            ParameterMode.DEFAULT == None

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'In': 1,
        'Out': 2,
        'InOut': 3
    }
xsi.MakeEnumeration(ParameterMode)
xsi.MakeLowerAliases(SimpleType)


class Parameter(CSDLElement):

    """Represents a Parameter in a function import."""
    XMLNAME = (EDM_NAMESPACE, 'Parameter')

    XMLATTR_Name = ('name', ValidateSimpleIdentifier, None)
    XMLATTR_Type = 'type'
    XMLATTR_Mode = (
        'mode', ParameterMode.DecodeValue, ParameterMode.EncodeValue)
    XMLATTR_MaxLength = ('maxLength', DecodeMaxLength, EncodeMaxLength)
    XMLATTR_Precision = 'precision'
    XMLATTR_Scale = 'scale'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.name = "Default"           #: the declared name of this parameter
        #: the type of the parameter, a scalar type, ComplexType or EntityType (or a Collection)
        self.type = ""
        self.typeRef = None         #: reference to the type definition
        #: one of the :py:class:`ParameterMode` constants
        self.mode = None
        self.maxLength = None           #: the maxLength facet of the parameter
        self.precision = None           #: the precision facet of the parameter
        self.scale = None               #: the scale facet of the parameter
        self.Documentation = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def GetChildren(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.GetChildren(self)):
            yield child

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        """Sets type information for the parameter"""
        try:
            self.typeRef = TypeRef(self.type, scope)
        except KeyError:
            self.typeRef = None
            if stopOnErrors:
                raise


class Function(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Function')


class Annotations(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Annotations')


class ValueTerm(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'ValueTerm')


class Schema(NameTableMixin, CSDLElement):

    """Represents the Edm root element.

    Schema instances are based on :py:class:`NameTableMixin` allowing
    you to look up the names of declared Associations, ComplexTypes,
    EntityTypes, EntityContainers and Functions using dictionary-like
    methods."""
    XMLNAME = (EDM_NAMESPACE, 'Schema')
    XMLATTR_Namespace = 'name'
    XMLATTR_Alias = 'alias'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        self.name = "Default"       #: the declared name of this schema
        self.alias = None
        self.Using = []
        #: a list of :py:class:`Association` instances
        self.Association = []
        #: a list of :py:class:`ComplexType` instances
        self.ComplexType = []
        #: a list of :py:class:`EntityType` instances
        self.EntityType = []
        # : a list of :py:class:`EntityContainer` instances
        self.EntityContainer = []
        self.Function = []
        self.Annotations = []
        self.ValueTerm = []

    def GetChildren(self):
        return itertools.chain(
            self.EntityType,
            self.ComplexType,
            self.Association,
            self.Function,
            self.EntityContainer,
            self.Using,
            self.Annotations,
            self.ValueTerm,
            CSDLElement.GetChildren(self))

    def ContentChanged(self):
        for t in self.EntityType + self.ComplexType + self.Association + self.Function + self.EntityContainer:
            self.Declare(t)

    def UpdateTypeRefs(self, scope, stopOnErrors=False):
        for t in self.EntityType + self.ComplexType + self.Association + self.Function:
            t.UpdateTypeRefs(scope, stopOnErrors)

    def UpdateSetRefs(self, scope, stopOnErrors=False):
        for t in self.EntityContainer:
            t.UpdateSetRefs(scope, stopOnErrors)


class Document(xmlns.XMLNSDocument):

    """Represents an EDM document."""

    classMap = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        self.defaultNS = EDM_NAMESPACE
        self.MakePrefix(EDM_NAMESPACE, 'edm')

    @classmethod
    def GetElementClass(cls, name):
        """Overrides :py:meth:`pyslet.xmlnames20091208.XMLNSDocument.GetElementClass` to look up name."""
        eClass = Document.classMap.get(
            name, Document.classMap.get((name[0], None), xmlns.XMLNSElement))
        return eClass

xmlns.MapClassElements(Document.classMap, globals(), NAMESPACE_ALIASES)
