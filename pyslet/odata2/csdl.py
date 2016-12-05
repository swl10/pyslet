#! /usr/bin/env python
"""This module implements the CSDL specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541211.aspx
http://msdn.microsoft.com/en-us/library/dd541474(v=prot.10)"""

import collections
import copy
import datetime
import decimal
import hashlib
import io
import itertools
import logging
import math
import pickle
import random
import uuid
import warnings

from .. import iso8601
from ..pep8 import (
    MigratedClass,
    old_function,
    old_method,
    PEP8Compatibility)
from ..py2 import (
    BoolMixin,
    byte,
    byte_value,
    dict_items,
    dict_values,
    is_text,
    join_bytes,
    long2,
    py2,
    range3,
    SortableMixin,
    to_text,
    u8,
    uempty,
    ul,
    UnicodeMixin)
from ..xml import structures as xml
from ..xml import namespace as xmlns
from ..xml import xsdatatypes as xsi


udp = ul(".")

#: Namespace to use for CSDL elements
EDM_NAMESPACE = "http://schemas.microsoft.com/ado/2009/11/edm"
EDM_NAMESPACE_ALIASES = [
    "http://schemas.microsoft.com/ado/2006/04/edm",     #: CSDL Schema 1.0
    "http://schemas.microsoft.com/ado/2007/05/edm",     #: CSDL Schema 1.1
    "http://schemas.microsoft.com/ado/2008/09/edm"]     #: CSDL Schema 2.0

NAMESPACE_ALIASES = {
    EDM_NAMESPACE: EDM_NAMESPACE_ALIASES
}


SIMPLE_IDENTIFIER_RE = xsi.RegularExpression(
    r"[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")

SIMPLE_IDENTIFIER_COMPATIBILITY_RE = xsi.RegularExpression(
    r"[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Pd}\p{Cf}]{0,}")

_simple_identifier_re = SIMPLE_IDENTIFIER_RE


def set_simple_identifier_re(pattern):
    global _simple_identifier_re
    result = _simple_identifier_re
    _simple_identifier_re = pattern
    return result


@old_function('ValidateSimpleIdentifier')
def validate_simple_identifier(identifier):
    """Validates a simple identifier, returning the identifier unchanged or
    raising ValueError."""
    if _simple_identifier_re.match(identifier):
        return identifier
    else:
        raise ValueError(
            "Can't parse SimpleIdentifier from :%s" % repr(identifier))


class EDMError(Exception):

    """General exception for all CSDL model errors."""
    pass


class ModelError(EDMError):

    """Exception for all model-related errors."""
    pass


class DuplicateName(ModelError):

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


class ModelIncomplete(ModelError):

    """Raised when a model element has a missing reference.

    For example, an
    :py:class:`EntitySet` that is bound to an undeclared
    ::py:class:`EntityType`."""
    pass


class ModelConstraintError(ModelError):

    """Raised when an issue in the model other than completeness
    prevents an action being performed.

    For example, an entity type that is dependent on two unbound
    principals (so can never be inserted)."""


class InvalidMetadataDocument(ModelError):

    """Raised by general CSDL model violations."""
    pass


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

    Python 3 note: the dictionary interface has changed in Python 3 with
    the introduction of the dictionary view object and the corresponding
    change in behaviour of the keys, values and items methods.  This
    class has not changed so is currently Python 2 dictionary like only.
    It is envisaged that when Pyslet is extended to include support for
    OData 4 a more Python3-friendly class will be used.

    Derived classes must override :py:meth:`__iter__` and
    :py:meth:`__getitem__` and if the dictionary is writable
    :py:meth:`__setitem__` and probably
    :py:meth:`__delitem__` too.  These methods all raise
    :NotImplementedError by default.

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

    Finally, one other difference worth noting is touched on in a
    comment from the following question on Stack Overflow:
    http://stackoverflow.com/questions/3358770/python-dictionary-is-thread-safe

    This question is about whether a dictionary can be modified during
    iteration.  Although not typically a thread-safety issue the
    commenter says:

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
        object to be writable."""
        raise NotImplementedError

    def __delitem__(self, key):
        """Implements del self[key]

        This method should be overridden if you want your
        dictionary-like object to be writable."""
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
            self[key]
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

        This is a copy of the items in no specific order.  Modifications
        to this list do not affect the object.  The default
        implementation uses
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

        This is an alternative implementation more suited to objects
        with very large numbers of keys.  It uses :py:meth:`popitem`
        repeatedly until KeyError is raised.  The downside is that
        popitem creates (and discards) one iterator object for each item
        it removes.  The upside is that we never load the list of keys
        into memory."""
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
        #: a dictionary mapping names to child objects
        self.nameTable = {}

    def __getitem__(self, key):
        """Looks up *key* in :py:attr:`nameTable` and, if not found, in
        each child scope with a name that is a valid scope prefix of
        key.  For example, if key is "My.Scope.Name" then a child scope
        with name "My.Scope" would be searched for "Name" or a child
        scope with name "My" would be searched for "Scope.Name"."""
        result = self.nameTable.get(key, None)
        if result is None:
            scope, key = self._split_key(key)
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
        for value in dict_values(self.nameTable):
            if isinstance(value, NameTableMixin):
                for key in value:
                    yield value.name + "." + key

    def __len__(self):
        """Returns the number of keys in this scope including all
        compounded keys from nested scopes."""
        result = len(self.nameTable)
        for value in dict_values(self.nameTable):
            if isinstance(value, NameTableMixin):
                result = result + len(value)
        return result

    def _split_key(self, key):
        skey = key.split(".")
        path_len = 1
        while path_len < len(skey):
            scope = self.nameTable.get(".".join(skey[:path_len]), None)
            if isinstance(scope, NameTableMixin):
                return scope, ".".join(skey[path_len:])
            path_len += 1
        return None, key

    def declare(self, value):
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

    def undeclare(self, value):
        """Removes a value from the named scope.

        Values can only be removed from the top-level scope."""
        if value.name in self.nameTable:
            del self.nameTable[value.name]
        else:
            raise KeyError("%s not declared in scope %s" %
                           (value.name, self.name))


class SimpleType(xsi.EnumerationNoCase):

    """SimpleType defines constants for the core data types defined by CSDL
    ::

            SimpleType.Boolean
            SimpleType.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`

    The canonical names for these constants uses the Edm prefix, for
    example, "Edm.String".  As a result, the class has attributes of the form
    "SimpleType.Edm.Binary" which are inaccessible to python unless
    getattr is used.  To workaround this problem (and because the Edm.
    prefix seems to be optional) we also define aliases without the Edm.
    prefix. As a result you can use, e.g., SimpleType.Int32 as the symbolic
    representation in code but the following are all True::

            SimpleType.from_str("Edm.Int32") == SimpleType.Int32
            SimpleType.from_str("Int32") == SimpleType.Int32
            SimpleType.to_str(SimpleType.Int32) == "Edm.Int32"  """
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

    aliases = {
        'binary': 'Edm.Binary',
        'Binary': 'Edm.Binary',
        'boolean': 'Edm.Boolean',
        'Boolean': 'Edm.Boolean',
        'byte': 'Edm.Byte',
        'Byte': 'Edm.Byte',
        'datetime': 'Edm.DateTime',
        'DateTime': 'Edm.DateTime',
        'decimal': 'Edm.Decimal',
        'Decimal': 'Edm.Decimal',
        'double': 'Edm.Double',
        'Double': 'Edm.Double',
        'single': 'Edm.Single',
        'Single': 'Edm.Single',
        'guid': 'Edm.Guid',
        'Guid': 'Edm.Guid',
        'int16': 'Edm.Int16',
        'Int16': 'Edm.Int16',
        'int32': 'Edm.Int32',
        'Int32': 'Edm.Int32',
        'int64': 'Edm.Int64',
        'Int64': 'Edm.Int64',
        'sbyte': 'Edm.SByte',
        'SByte': 'Edm.SByte',
        'string': 'Edm.String',
        'String': 'Edm.String',
        'time': 'Edm.Time',
        'Time': 'Edm.Time',
        'datetimeoffset': 'Edm.DateTimeOffset',
        'DateTimeOffset': 'Edm.DateTimeOffset'}

    PythonType = {}
    """A python dictionary that maps a type code (defined by the types
    module) to a constant from this class indicating a safe
    representation in the EDM.  For example::

        SimpleType.PythonType[int]==SimpleType.Int64"""


SimpleType.PythonType = {
    bool: SimpleType.Boolean,
    float: SimpleType.Double,
    int: SimpleType.Int64,
    str: SimpleType.String}

if py2:
    SimpleType.PythonType[long2] = SimpleType.Decimal
    SimpleType.PythonType[type(uempty)] = SimpleType.String
else:
    SimpleType.PythonType[bytes] = SimpleType.Binary


Numeric = collections.namedtuple(
    'Numeric', "sign ldigits rdigits esign edigits")


class Parser(xsi.BasicParser):

    """A CSDL-specific parser, mainly for decoding literal values of
    simple types.

    The individual parsing methods may raise ValueError in cases where
    parsed value has a value that is out of range."""

    def parse_binary_literal(self):
        """Parses a binary literal, returning a binary string"""
        #   binaryLiteral = hexDigPair
        #   hexDigPair = 2*HEXDIG [hexDigPair]"""
        output = []
        hex_str = self.parse_hex_digits(1)
        if hex_str is None:
            return ''
        if len(hex_str) % 2:
            raise ValueError(
                "Trailing nibble in binary literal: '%s'" % hex_str[-1])
        i = 0
        while i < len(hex_str):
            output.append(byte(int(hex_str[i:i + 2], 16)))
            i = i + 2
        return join_bytes(output)

    def parse_boolean_literal(self):
        """Parses a boolean literal returning True, False or None if no boolean
        literal was found."""
        if self.parse_insensitive("true"):
            return True
        elif self.parse_insensitive("false"):
            return False
        else:
            return None

    def parse_byte_literal(self):
        """Parses a byteLiteral, returning a python integer.

        We are generous in what we accept, ignoring leading zeros.  Values
        outside the range for byte return None."""
        return self.parse_integer(0, 255)

    def parse_datetime_literal(self):
        """Parses a DateTime literal, returning a
        :py:class:`pyslet.iso8601.TimePoint` instance.

        Returns None if no DateTime literal can be parsed.  This is a
        generous way of parsing iso8601-like values, it accepts omitted
        zeros in the date, such as 4-7-2001."""
        savepos = self.pos
        try:
            production = "dateTimeLiteral"
            year = int(
                self.require_production(self.parse_digits(4, 4), "year"))
            self.require("-",)
            month = self.require_production(self.parse_integer(1, 12), "month")
            self.require("-", production)
            day = self.require_production(self.parse_integer(1, 31, 2), "day")
            self.require("T", production)
            hour = self.require_production(self.parse_integer(0, 24), "hour")
            self.require(":", production)
            minute = self.require_production(
                self.parse_integer(0, 60, 2), "minute")
            if self.parse(":"):
                second = self.require_production(
                    self.parse_integer(0, 60, 2), "second")
                if self.parse("."):
                    nano = self.parse_digits(1, 7)
                    second += float("0." + nano)
            else:
                second = 0
            zpos = self.pos
            try:
                # parse and discard a zone specifier
                z = self.parse_one("Zz+-")
                if z == "+" or z == "-":
                    zh = self.require_production(self.parse_integer(0, 24),
                                                 "zhour")
                    self.require(":")
                    zm = self.require_production(self.parse_integer(0, 24),
                                                 "zminute")
                    logging.warning(
                        "DateTime ignored zone offset: %s%.2i:%.2i",
                        z, zh, zm)
            except ValueError:
                self.setpos(zpos)
                pass
        except ValueError:
            self.setpos(savepos)
            return None
        try:
            value = iso8601.TimePoint(
                date=iso8601.Date(
                    century=year // 100, year=year %
                    100, month=month, day=day), time=iso8601.Time(
                    hour=hour, minute=minute, second=second, zdirection=None))
        except iso8601.DateTimeError as e:
            raise ValueError(str(e))
        return value

    def parse_guid_literal(self):
        """Parses a Guid literal, returning a UUID instance from the
        uuid module.

        Returns None if no Guid can be parsed."""
        savepos = self.pos
        try:
            production = "guidLiteral"
            # dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents
            # [A-Fa-f0-9]
            guid = []
            guid.append(self.require_production(self.parse_hex_digits(8, 8),
                                                production))
            self.require_production(self.parse('-'))
            guid.append(self.require_production(self.parse_hex_digits(4, 4),
                                                production))
            self.require_production(self.parse('-'))
            guid.append(self.require_production(self.parse_hex_digits(4, 4),
                                                production))
            self.require_production(self.parse('-'))
            guid.append(self.require_production(self.parse_hex_digits(4, 4),
                                                production))
            self.require_production(self.parse('-'))
            guid.append(
                self.require_production(
                    self.parse_hex_digits(
                        12,
                        12),
                    production))
            value = uuid.UUID(''.join(guid))
        except ValueError:
            self.setpos(savepos)
            return None
        return value

    def parse_numeric_literal(self):
        """Parses a numeric literal returning a named tuple of strings::

                ( sign, ldigits, rdigits, expSign, edigits )

        An empty string indicates a component that was not present
        except that rdigits will be None if no decimal point was
        present.  Likewise, edigits may be None indicating that no
        exponent was found.

        Although both ldigits and rdigits can be empty they will never
        *both* be empty strings. If there are no digits present then the
        method returns None, rather than a tuple.  Therefore, forms like
        "E+3" are not treated as being numeric literals whereas, perhaps
        oddly, 1E+ is parsed as a numeric literal (even though it will
        raise ValueError later when setting any of the numeric value
        types).

        Representations of infinity and not-a-number result in ldigits
        being set to 'inf' and 'nan' respectively.  They always result
        in rdigits and edigits being None."""
        savepos = self.pos
        esign = ''
        rdigits = edigits = None
        sign = self.parse_one("-")
        if sign is None:
            sign = ""
        if self.parse_insensitive("inf"):
            ldigits = "inf"
        elif self.parse_insensitive("nan"):
            ldigits = "nan"
        else:
            ldigits = self.parse_digits(0)
            if self.parse('.'):
                rdigits = self.parse_digits(0)
            if not ldigits and not rdigits:
                self.setpos(savepos)
                return None
            if self.parse_one('eE'):
                esign = self.parse_one("-")
                if esign is None:
                    esign = '+'
                edigits = self.parse_digits(0)
        return Numeric(sign, ldigits, rdigits, esign, edigits)

    def parse_time_literal(self):
        """Parses a Time literal, returning a :py:class:`pyslet.iso8601.Time` instance.

        Returns None if no Time literal can be parsed.  This is a
        generous way of parsing iso8601-like values, it accepts omitted
        zeros in the leading field, such as 7:45:00."""
        savepos = self.pos
        try:
            production = "timeLiteral"
            hour = self.require_production(self.parse_integer(0, 24), "hour")
            self.require(":", production)
            minute = self.require_production(
                self.parse_integer(0, 60, 2), "minute")
            if self.parse(":"):
                second = self.require_production(
                    self.parse_integer(0, 60, 2), "second")
                if self.parse("."):
                    nano = self.parse_digits(1, 7)
                    second += float("0." + nano)
            else:
                second = 0
        except ValueError:
            self.setpos(savepos)
            return None
        try:
            value = iso8601.Time(
                hour=hour, minute=minute, second=second, zdirection=None)
        except iso8601.DateTimeError as e:
            raise ValueError(str(e))
        return value


class EDMValue(BoolMixin, PEP8Compatibility):

    """Abstract class to represent a value in the EDMModel.

    This class is used to wrap or 'box' instances of a value.  In
    particular, it can be used in a context where that value can have
    either a simple or complex type.

    EDMValue instances are treated as being non-zero if
    :py:meth:`is_null` returns False."""

    def __init__(self, p_def=None):
        # unlikely that people will have derived classes here
        PEP8Compatibility.__init__(self)
        self.p_def = p_def
        """An optional :py:class:`Property` instance from the metadata
        model defining this value's type"""

    __hash__ = None
    """EDM values are mutable so may not be used as dictionary keys,
    this is enforced by setting __hash__ to None"""

    _TypeClass = {
    }

    def __bool__(self):
        return not self.is_null()

    def is_null(self):
        """Returns True if this object is Null."""
        return True

    @classmethod
    @old_method('NewValue')
    def from_property(cls, p_def):
        """Constructs an instance of the correct child class of
        :py:class:`EDMValue` to represent a value defined by
        :py:class:`Property` instance *p_def*.

        We support a special case for creating a type-less NULL.  If you
        pass None for p_def then a type-less
        :py:class:`SipmleValue` is instantiated."""
        if p_def is None:
            return SimpleValue(None)
        elif p_def.simpleTypeCode is not None:
            return cls._TypeClass[p_def.simpleTypeCode](p_def)
        elif p_def.complexType:
            return Complex(p_def)
        else:
            raise ModelIncomplete(
                "Property %s not bound to a type" % p_def.name)

    @classmethod
    @old_method('NewSimpleValue')
    def from_type(cls, type_code):
        """Constructs an instance of the correct child class of
        :py:class:`EDMValue` to represent an (undeclared) simple
        value of :py:class:`SimpleType` *type_code*."""
        if type_code is None:
            result = SimpleValue(None)
        else:
            result = cls._TypeClass[type_code](None)
        # hack the type code after construction to save on overhead of another
        # constructor
        result.type_code = type_code
        return result

    @classmethod
    @old_method('NewSimpleValueFromValue')
    def from_value(cls, value):
        """Constructs an instance of the correct child class of
        :py:class:`EDMValue` to hold *value*.

        *value* may be any of the types listed in
        :py:class:`SimpleValue`."""
        if isinstance(value, uuid.UUID):
            result = cls.from_type(SimpleType.Guid)
        elif isinstance(value, iso8601.TimePoint):
            # if it has an offset
            if value.get_zone()[0] is None:
                # no timezone
                result = cls.from_type(SimpleType.DateTime)
            else:
                result = cls.from_type(SimpleType.DateTimeOffset)
        elif isinstance(value, decimal.Decimal):
            result = cls.from_type(SimpleType.Decimal)
        elif isinstance(value, datetime.datetime):
            result = cls.from_type(SimpleType.DateTime)
        else:
            t = SimpleType.PythonType.get(type(value), None)
            if t is not None:
                result = cls.from_type(t)
            else:
                raise ValueError(
                    "Can't construct SimpleValue from %s" % repr(value))
        result.set_from_value(value)
        return result


class SimpleValue(UnicodeMixin, EDMValue):

    """An abstract class that represents a value of a simple type in the EDMModel.

    This class is not designed to be instantiated directly, use one of
    the factory methods in :py:class:`EDMValue` to construct one of the
    specific child classes."""

    def __init__(self, p_def=None):
        EDMValue.__init__(self, p_def)
        if p_def:
            #: the :py:class:`SimpleType` code
            self.type_code = p_def.simpleTypeCode
        else:
            self.type_code = None
        #: an optional :py:class:`pyslet.http.params.MediaType` representing
        #: this value
        self.mtype = None
        self.value = None
        """The actual value or None if this instance represents a NULL value

        The python type used for *value* depends on type_code as follows:

        Edm.Boolean:
            one of the Python constants True or False

        Edm.Byte, Edm.SByte, Edm.Int16, Edm.Int32:
            int

        Edm.Int64:
            int (Python 2: long)

        Edm.Double, Edm.Single:
            python float

        Edm.Decimal:
            python Decimal instance (from decimal module)

        Edm.DateTime, Edm.DateTimeOffset:
            py:class:`pyslet.iso8601.TimePoint` instance

        Edm.Time:
            py:class:`pyslet.iso8601.Time` instance (not a Duration,
            note corrected v2 specification of OData)

        Edm.Binary:
            binary string

        Edm.String:
            character string (unicode in Python 2)

        Edm.Guid:
            python UUID instance (from uuid module)

        For future compatibility, this attribute should only be updated
        using :py:meth:`set_from_value` or one of the other related
        methods."""

    @old_method('IsNull')
    def is_null(self):
        return self.value is None

    def simple_cast(self, type_code):
        """Returns a new :py:class:`SimpleValue` instance created from *type_code*

        The value of the new instance is set using :py:meth:`cast`"""
        target_value = EDMValue.from_type(type_code)
        return self.cast(target_value)

    def cast(self, target_value):
        """Updates and returns *target_value* a :py:class:`SimpleValue` instance.

        The value of target_value is replaced with a value cast from this
        instance's value.

        If the types are incompatible a TypeError is raised, if the
        values are incompatible then ValueError is raised.

        NULL values can be cast to any value type."""
        if self.type_code == target_value.type_code:
            target_value.value = self.value
        else:
            # new_value=EDMValue.from_property(newTypeCode,self.name)
            if self.type_code is not None:
                target_value.set_from_value(copy.deepcopy(self.value))
        return target_value

    @old_method('SetFromSimpleValue')
    def set_from_simple_value(self, new_value):
        """The reverse of the :py:meth:`cast` method, sets this value to
        the value of *new_value* casting as appropriate."""
        new_value.cast(self)

    def __eq__(self, other):
        """Instances compare equal only if they are of the same type and
        have values that compare equal."""
        if isinstance(other, SimpleValue):
            # are the types compatible? lazy comparison to start with
            return self.type_code == other.type_code and \
                self.value == other.value
        else:
            return self.value == other

    def __ne__(self, other):
        return not self == other

    def __unicode__(self):
        """Formats this value into its literal form.

        NULL values cannot be represented in literal form and will raise
        ValueError."""
        if self.value is None:
            if self.p_def:
                raise ValueError("%s is NULL" % self.p_def.name)
            else:
                raise ValueError("NULL value has no text representation")
        return to_text(self.value)

    def set_from_literal(self, value):
        """Decodes a value from the value's literal form.

        You can get the literal form of a value using the unicode function."""
        raise NotImplementedError

    def set_default_value(self):
        if self.p_def and self.p_def.defaultValue is not None:
            self.set_from_literal(self.p_def.defaultValue)
        elif self.p_def and not self.p_def.nullable:
            # no default, not nullable - this is a ConstrainError
            raise ConstraintError(
                "%s: Non-nullable property has no default value" %
                self.p_def.name)
        else:
            self.value = None

    def set_null(self):
        """Sets the value to NULL"""
        self.value = None

    def set_from_value(self, new_value):
        """Sets the value from a python variable coercing *new_value* if
        necessary to ensure it is of the correct type for the value's
        :py:attr:`type_code`."""
        if new_value is None:
            self.value = None
        else:
            raise NotImplementedError

    def set_random_value(self, base=None):
        """Sets a random value based

        base
            a :py:class:`SimpleValue` instance of the same type that may
            be used as a base or stem or the random value generated or
            may be ignored, depending on the value type."""
        raise NotImplementedError

    @classmethod
    def copy(cls, value):
        """Constructs a new SimpleValue instance by copying *value*"""
        if value.p_def:
            result = value.__class__(value.p_def)
        else:
            result = EDMValue.from_type(value.type_code)
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
        input = io.BytesIO(self.value)
        output = io.StringIO()
        while True:
            b = input.read(1)
            if len(b):
                output.write(ul("%02X") % byte_value(b[0]))
            else:
                break
        return output.getvalue()

    def set_from_literal(self, value):
        p = Parser(value)
        self.value = p.require_production_end(
            p.parse_binary_literal(), "binaryLiteral")

    def set_from_value(self, new_value):
        if isinstance(new_value, bytes):
            self.value = new_value
        elif isinstance(new_value, bytearray):
            self.value = bytes(new_value)
        elif new_value is None:
            self.value = None
        elif isinstance(new_value, str):
            raise ValueError(
                "Can't set BinaryValue from character string: %s" %
                repr(new_value))
        else:
            self.value = pickle.dumps(new_value)


class BooleanValue(SimpleValue):

    """Represents a simple value of type Edm.Boolean

    Boolean literals are one of::

                    true | false

    Boolean values can be set from their Python equivalents and from any
    int, (Python 2 long,) float or Decimal where the non-zero test is
    used to set the value."""

    utrue = ul("true")
    ufalse = ul("false")

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return self.utrue if self.value else self.ufalse

    def set_from_literal(self, value):
        test_value = value.lower()
        if test_value == self.utrue:
            self.value = True
        elif test_value == self.ufalse:
            self.value = False
        else:
            raise ValueError("Failed to parse boolean literal from %s" % value)

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)):
            self.value = (new_value != 0)
        elif isinstance(new_value, bool):
            self.value = new_value
        else:
            raise TypeError("Can't set Boolean from %s" % repr(new_value))


class NumericValue(SimpleValue):

    """An abstract class that represents all numeric simple values.

    The literal forms of numeric values are parsed in a two-stage
    process.  Firstly the utility class :py:class:`Parser` is used to
    obtain a numeric tuple and then the value is set using
    :py:meth:`set_from_numeric_literal`

    All numeric types may have their value set directly from int,
    (Python 2 long,) float or Decimal.

    Integer representations are rounded towards zero using the python
    *int* (or Python 2 *long*) functions when necessary."""

    @old_method('SetToZero')
    def set_to_zero(self):
        """Set this value to the default representation of zero"""
        self.set_from_value(0)

    @old_method('SetFromLiteral')
    def set_from_literal(self, value):
        p = Parser(value)
        nvalue = p.require_production_end(
            p.parse_numeric_literal(), "byteLiteral")
        self.set_from_numeric_literal(nvalue)

    @old_method('SetFromNumericLiteral')
    def set_from_numeric_literal(self, num):
        """Decodes a value from a numeric tuple as returned by
        :py:meth:`Parser.parse_numeric_literal`."""
        raise NotImplementedError

    def join_numeric_literal(self, num):
        r = []
        r.append(num.sign)
        r.append(num.ldigits)
        if num.rdigits is not None:
            r.append('.')
            r.append(num.rdigits)
        if num.edigits is not None:
            r.append('E')
            r.append(num.esign)
            r.append(num.edigits)
        return ''.join(r)


class ByteValue(NumericValue):

    """Represents a simple value of type Edm.Byte

    Byte literals must not have a sign, decimal point or exponent.

    Byte values can be set from an int, (Python 2: long,) float or
    Decimal"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return xsi.integer_to_str(self.value)

    def set_from_numeric_literal(self, num):
        if (num.sign or                    # no sign allowed at all
                not num.ldigits or             # must be left digits
                # must not be nan or inf
                num.ldigits.isalpha() or
                # must not have '.' or rdigits
                num.rdigits is not None or
                num.edigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Byte: %s" %
                             self.join_numeric_literal(num))
        self.set_from_value(int(num.ldigits))

    def set_from_value(self, new_value):
        """*new_value* must be of type int, (Python 2: long,) float or
        Decimal."""
        if new_value is None:
            self.value = None
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)):
            if new_value < 0 or new_value > 255:
                raise ValueError("Illegal value for Byte: %s" % str(new_value))
            self.value = int(new_value)
        else:
            raise TypeError("Can't set Byte from %s" % str(new_value))


class DateTimeValue(SimpleValue):

    """Represents a simple value of type Edm.DateTime

    DateTime literals allow content in the following form::

            yyyy-mm-ddThh:mm[:ss[.fffffff]]

    DateTime values can be set from an instance of
    :py:class:`iso8601.TimePoint` or type int, (Python 2: long,) float,
    Decimal or the standard Python date.datetime and date.date
    instances. In the case of date.date, the new value represents
    midnight at the beginning of the specified day.

    Any zone specifier is ignored.  There is *no* conversion to UTC, the
    value simply becomes a local time in an unspecified zone.  This is a
    weakness of the EDM, it is good practice to limit use of the
    DateTime type to UTC times.

    When set from a numeric value, the value must be non-negative.  Unix
    time is assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.from_unix_time` factory method of
    TimePoint for information.

    If a property definition was set on construction then the defined
    precision is used when representing the value as a character string.
    For example, if the property has precision 3 then the output of the
    string conversion will appear in the following form::

            1969-07-20T20:17:40.000"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        precision = None
        if self.p_def:
            # check the precision before formatting
            precision = self.p_def.precision
        if precision is None:
            precision = 0
        return self.value.get_calendar_string(ndp=precision, dp=udp)

    def set_from_literal(self, value):
        p = Parser(value)
        self.value = p.require_production_end(
            p.parse_datetime_literal(), "DateTime")

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, iso8601.TimePoint):
            self.value = new_value.with_zone(zdirection=None)
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)) and \
                new_value >= 0:
            self.value = iso8601.TimePoint.from_unix_time(
                float(new_value)).with_zone(None)
        elif isinstance(new_value, datetime.datetime):
            self.value = iso8601.TimePoint(
                date=iso8601.Date(
                    century=new_value.year // 100,
                    year=new_value.year % 100,
                    month=new_value.month,
                    day=new_value.day),
                time=iso8601.Time(
                    hour=new_value.hour,
                    minute=new_value.minute,
                    second=new_value.second +
                    (new_value.microsecond / 1000000.0),
                    zdirection=None))
        elif isinstance(new_value, datetime.date):
            self.value = iso8601.TimePoint(
                date=iso8601.Date(
                    century=new_value.year // 100,
                    year=new_value.year % 100,
                    month=new_value.month,
                    day=new_value.day))
        else:
            raise TypeError("Can't set DateTime from %s" % repr(new_value))


class DateTimeOffsetValue(SimpleValue):

    """Represents a simple value of type Edm.DateTimeOffset

    DateTimeOffset literals are defined in terms of the XMLSchema
    lexical representation.

    DateTimeOffset values can be set from an instance of
    :py:class:`iso8601.TimePoint` or type int, (Python 2: long,) float
    or Decimal.

    TimePoint instances must have a zone specifier.  There is *no*
    automatic assumption of UTC.

    When set from a numeric value, the value must be non-negative.  Unix
    time *in UTC* assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.from_unix_time` factory method of
    TimePoint for information.

    If a property definition was set on construction then the defined
    precision is used when representing the value as a character string.
    For example, if the property has precision 3 then the output of the
    string conversion will appear in the following form::

            1969-07-20T15:17:40.000-05:00

    It isn't completely clear if the canonical representation of UTC
    using 'Z' instead of an offset is intended or widely supported so we
    always use an offset::

            1969-07-20T20:17:40.000+00:00"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        precision = None
        if self.p_def:
            # check the precision before formatting
            precision = self.p_def.precision
        if precision is None:
            precision = 0
        result = self.value.get_calendar_string(ndp=precision, dp=udp)
        if result[-1] == "Z":
            # the specification is not clear if the Z form is supported, use
            # numbers for safety
            result = result[:-1] + "+00:00"
        return result

    def set_from_literal(self, value):
        try:
            value = iso8601.TimePoint.from_str(value)
        except iso8601.DateTimeError as e:
            raise ValueError(str(e))
        self.set_from_value(value)

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, iso8601.TimePoint):
            zdir, zoffset = new_value.get_zone()
            if zoffset is None:
                raise ValueError(
                    "DateTimeOffset requires a time zone specifier: %s" %
                    new_value)
            if not new_value.complete():
                raise ValueError(
                    "DateTimeOffset requires a complete representation: %s" %
                    str(new_value))
            self.value = new_value
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)) and \
                new_value >= 0:
            self.value = iso8601.TimePoint.from_unix_time(float(new_value))
        else:
            raise TypeError(
                "Can't set DateTimeOffset from %s" % str(new_value))


class TimeValue(SimpleValue):

    u8(b"""Represents a simple value of type Edm.Time

    Time literals allow content in the form:

            hh:mm:ss.sss

    Time values can be set from an instance of
    :py:class:`pyslet.iso8601.Time`, int, (Python 2: long,) float or
    Decimal and from datetime.timedelta values.

    When set from a numeric value the value must be in the range
    0..86399.9\xcc\x85 and is treated as an elapsed time in seconds since
    midnight.

    If a property definition was set on construction then the defined
    precision is used when representing the value as a character string.
    For example, if the property has precision 3 then the output of the
    string conversion will appear in the following form::

            20:17:40.000""")

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        precision = None
        if self.p_def:
            # check the precision before formatting
            precision = self.p_def.precision
        if precision is None:
            precision = 0
        return self.value.get_string(ndp=precision, dp=udp)

    def set_from_literal(self, value):
        p = Parser(value)
        self.value = p.require_production_end(p.parse_time_literal(), "Time")

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, iso8601.Time):
            self.value = new_value
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)) and \
                new_value >= 0:
            if new_value < 0:
                raise ValueError(
                    "Can't set Time from %.3f" % float(new_value))
            tvalue = iso8601.Time()
            if isinstance(new_value, (int, long2)):
                tvalue, days = tvalue.offset(seconds=new_value)
            else:
                tvalue, days = tvalue.offset(seconds=float(new_value))
            if days > 0:
                raise ValueError(
                    "Can't set Time from %.3f (overflow)" % float(new_value))
            self.value = tvalue
        elif isinstance(new_value, datetime.timedelta):
            seconds = new_value.seconds
            if new_value.microseconds:
                seconds = seconds + (new_value.microseconds / 1000000.0)
            tvalue = iso8601.Time()
            tvalue, days = tvalue.offset(seconds=seconds)
            if days > 0 or new_value.days:
                raise ValueError(
                    "Can't set Time from %s (non-zero days)" %
                    repr(new_value))
            self.value = tvalue
        else:
            raise TypeError("Can't set Time from %s" % repr(new_value))


class DecimalValue(NumericValue):

    """Represents a simple value of type Edm.Decimal

    Decimal literals must not use exponent notation and there must be no
    more than 29 digits to the left and right of the decimal point.

    Decimal values can be set from int, (Python 2: long,) float or
    Decimal values."""
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
        return to_text(d.__format__('f'))

    def set_from_numeric_literal(self, num):
        dstr = self.join_numeric_literal(num)
        if ((num.ldigits and (num.ldigits.isalpha() or
                              len(num.ldigits) > 29)) or
                (num.rdigits and len(num.rdigits) > 29) or num.rdigits == "" or
                num.edigits is not None):
            # inf and nan not allowed
            # limit left digits
            # limit right digits
            # ensure decimals if '.' is present
            # do not allow exponent
            raise ValueError("Illegal literal for Decimal: %s" % dstr)
        self.set_from_value(decimal.Decimal(dstr))

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
            return
        elif isinstance(new_value, decimal.Decimal):
            d = new_value
        elif isinstance(new_value, float):
            d = decimal.Decimal(str(new_value))
        elif isinstance(new_value, (int, long2)):
            d = decimal.Decimal(new_value)
        else:
            raise TypeError("Can't set Decimal from %s" % str(new_value))
        if self.abs(d) > self.Max:
            # too big for CSDL decimal forms
            raise ValueError("Value exceeds limits for Decimal: %s" % str(d))
        # in the interests of maintaining accuracy we don't limit the
        # precision of the value at this point
        self.value = d


class FloatValue(NumericValue):

    """Abstract class that represents one of Edm.Double or Edm.Single.

    Values can be set from int, (Python 2: long,) float or Decimal.

    There is no hard-and-fast rule about the representation of float in
    Python and we may refuse to accept values that fall within the
    accepted ranges defined by the CSDL if float cannot hold them.  That
    said, you won't have this problem in practice.

    The derived classes :py:class:`SingleValue` and
    :py:class:`DoubleValue` only differ in the Max value used
    when range checking.

    Values are formatted using Python's default string conversion."""

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, decimal.Decimal):
            # deal with py26 decimal bug!
            # see http://bugs.python.org/issue2531
            if new_value < -self.MaxD or new_value > self.MaxD:
                raise ValueError(
                    "Value for Double out of range: %s" % str(new_value))
            self.value = float(new_value)
        elif isinstance(new_value, (int, long2)):
            if new_value < -self.Max or new_value > self.Max:
                raise ValueError(
                    "Value for Double out of range: %s" % str(new_value))
            self.value = float(new_value)
        elif isinstance(new_value, float):
            if math.isnan(new_value) or math.isinf(new_value):
                self.value = new_value
            elif new_value < -self.Max or new_value > self.Max:
                raise ValueError("Value out of range: %s" % str(new_value))
            else:
                self.value = new_value
        else:
            raise TypeError(
                "Can't set floating-point value from %s" % str(new_value))


class DoubleValue(FloatValue):

    """Represents a simple value of type Edm.Double"""

    Max = None
    """the largest positive double value

    This value is set dynamically on module load, theoretically it may
    be set lower than the maximum allowed by the specification if
    Python's native float is of insufficient precision but this is
    unlikely to be an issue."""

    MaxD = None
    """the largest positive double value converted to decimal form"""

    # Min=2**-1074  #: the smallest positive double value

    def set_from_numeric_literal(self, num):
        dstr = self.join_numeric_literal(num)
        if num.ldigits and num.ldigits.isalpha():
            if num.ldigits == "nan":
                if num.sign:
                    raise ValueError(
                        "Illegal literal, nan must not be negative: %s" % dstr)
                self.value = float("Nan")
            elif num.sign == "-":
                self.value = float("-INF")
            else:
                self.value = float("INF")
        elif (num.rdigits is None or       # integer form or
                num.edigits is not None):      # exponent form; limit digits
            ndigits = len(num.ldigits)
            if num.rdigits:
                ndigits += len(num.rdigits)
            if ndigits > 17:
                raise ValueError("Too many digits for double: %s" % dstr)
            if (num.edigits == '' or (num.edigits and (len(num.edigits) > 3 or
                                                       not num.ldigits))):
                # empty exponent not allowed
                # long exponent not allowed
                # exponent requires digits to left of point
                raise ValueError("Illegal exponent form for double: %s" % dstr)
        self.set_from_value(float(dstr))


for i in range3(1023, 0, -1):
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

DoubleValue.MaxD = decimal.Decimal(str(DoubleValue.Max))


class SingleValue(FloatValue):

    """Represents a simple value of type Edm.Single"""

    Max = None
    """the largest positive single value

    This value is set dynamically on module load, theoretically it may
    be set lower than the maximum allowed by the specification if
    Python's native float is of insufficient precision but this is very
    unlikely to be an issue unless you've compiled Python on in a very
    unusual environment."""

    MaxD = None
    """the largest positive single value converted to Decimal"""

    # Min=2.0**-149             #: the smallest positive single value

    def set_from_numeric_literal(self, num):
        """Decodes a Single value from a :py:class:`Numeric` literal."""
        dstr = self.join_numeric_literal(num)
        if num.ldigits and num.ldigits.isalpha():
            if num.ldigits == "nan":
                if num.sign:
                    raise ValueError(
                        "Illegal literal, nan must not be negative: %s" % dstr)
                self.value = float("Nan")
            elif num.sign == "-":
                self.value = float("-INF")
            else:
                self.value = float("INF")
        elif num.rdigits is None:
            # integer form
            if len(num.ldigits) > 8:
                raise ValueError("Too many digits for single: %s" % dstr)
        elif num.edigits is not None:
            # exponent form
            ndigits = len(num.ldigits)
            if num.rdigits:
                ndigits += len(num.rdigits)
            if ndigits > 9:
                raise ValueError("Too many digits for single: %s" % dstr)
            if (num.edigits == '' or (num.edigits and (len(num.edigits) > 2 or
                                                       not num.ldigits))):
                # empty exponent not allowed
                # long exponent not allowed
                # exponent requires digits to left of point
                raise ValueError("Illegal exponent form for single: %s" % dstr)
        self.set_from_value(float(dstr))


for i in range3(127, 0, -1):
    try:
        SingleValue.Max = (2 - 2 ** -23) * 2 ** i
        break
    except OverflowError:
        # worrying this probably means float is too small for this application
        if i == 127:
            logging.warning("float may be less than singe precision!")
        continue

SingleValue.MaxD = decimal.Decimal(str(SingleValue.Max))


class GuidValue(SimpleValue):

    """Represents a simple value of type Edm.Guid

    Guid literals allow content in the following form:
    dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents [A-Fa-f0-9].

    Guid values can also be set directly from either binary or hex
    strings. Binary strings must be of length 16 and are passed as raw
    bytes to the UUID constructor, hexadecimal strings must be of length
    32 characters.  (In Python 2 both str and unicode types are accepted
    as hexadecimal strings, the length being used to determine if the
    source is a binary or hexadecimal representation.)"""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return to_text(self.value)

    def set_from_literal(self, value):
        p = Parser(value)
        self.value = p.require_production_end(p.parse_guid_literal(), "Guid")

    def set_from_value(self, new_value):
        """*new_value* must be an instance of Python's UUID class

        We also support setting from a raw string of exactly 16 bytes in
        length or a text string of exactly 32 bytes (the latter is
        treated as the hex representation)."""
        if new_value is None:
            self.value = None
        elif isinstance(new_value, uuid.UUID):
            self.value = new_value
        elif isinstance(new_value, bytes) and len(new_value) == 16:
            self.value = uuid.UUID(bytes=new_value)
        elif is_text(new_value) and len(new_value) == 32:
            self.value = uuid.UUID(hex=new_value)
        else:
            raise TypeError("Can't set Guid from %s" % repr(new_value))


class Int16Value(NumericValue):

    """Represents a simple value of type Edm.Int16"""

    def set_from_numeric_literal(self, num):
        if (not num.ldigits or             # must be left digits
                # must not be nan or inf
                num.ldigits.isalpha() or
                # must not have '.' or rdigits
                num.rdigits is not None or
                num.edigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Int16: %s" %
                             self.join_numeric_literal(num))
        self.set_from_value(int(self.join_numeric_literal(num)))

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)):
            if new_value < -32768 or new_value > 32767:
                raise ValueError(
                    "Illegal value for Int16: %s" % str(new_value))
            self.value = int(new_value)
        else:
            raise TypeError("Can't set Int16 from %s" % str(new_value))


class Int32Value(NumericValue):

    """Represents a simple value of type Edm.Int32"""

    def set_from_numeric_literal(self, num):
        if (not num.ldigits or             # must be left digits
                # must not be more than 10 digits
                len(num.ldigits) > 10 or
                # must not be nan or inf
                num.ldigits.isalpha() or
                # must not have '.' or rdigits
                num.rdigits is not None or
                num.edigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Int32: %s" %
                             self.join_numeric_literal(num))
        self.set_from_value(int(self.join_numeric_literal(num)))

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)):
            if new_value < -2147483648 or new_value > 2147483647:
                raise ValueError(
                    "Illegal value for Int32: %s" % str(new_value))
            self.value = int(new_value)
        else:
            raise TypeError("Can't set Int32 from %s" % str(new_value))

    def set_random_value(self, base=None):
        if base and base.value < 0:
            self.set_from_value(-random.getrandbits(31))
        else:
            self.set_from_value(random.getrandbits(31))


class Int64Value(NumericValue):

    """Represents a simple value of type Edm.Int64"""

    def set_from_numeric_literal(self, num):
        if (not num.ldigits or             # must be left digits
                # must not be more than 19 digits
                len(num.ldigits) > 19 or
                # must not be nan or inf
                num.ldigits.isalpha() or
                # must not have '.' or rdigits
                num.rdigits is not None or
                num.edigits is not None):      # must not have an exponent
            raise ValueError("Illegal literal for Int64: %s" %
                             self.join_numeric_literal(num))
        self.set_from_value(int(self.join_numeric_literal(num)))

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)):
            if new_value < -9223372036854775808 or \
                    new_value > 9223372036854775807:
                raise ValueError(
                    "Illegal value for Int64: %s" % str(new_value))
            self.value = long2(new_value)
        else:
            raise TypeError("Can't set Int64 from %s" % str(new_value))

    def set_random_value(self, base=None):
        if base and base.value < 0:
            self.set_from_value(-random.getrandbits(63))
        else:
            self.set_from_value(random.getrandbits(63))


class StringValue(SimpleValue):

    """Represents a simple value of type Edm.String"

    The literal form of a string is the string itself.

    Values may be set from any string or object which supports
    conversion to character string."""

    def __unicode__(self):
        if self.value is None:
            raise ValueError("%s is Null" % self.name)
        return to_text(self.value)

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        else:
            self.value = to_text(new_value)

    @old_method('SetFromLiteral')
    def set_from_literal(self, value):
        self.value = value

    def set_random_value(self, base=None):
        if base:
            base = base.value
        else:
            base = ''
        rbytes = 8
        if self.p_def:
            # how much of base do
            if rbytes > self.p_def.maxLength:
                rbytes = self.p_def.maxLength
            if (self.p_def.fixedLength and
                    rbytes + len(base) < self.p_def.maxLength):
                rbytes = self.maxLength - len(base)
            elif len(base) + rbytes > self.p_def.maxLength:
                # shorten base
                base = base[:self.p_def.maxLength - rbytes]
        value = [base]
        for r in range3(rbytes):
            value.append("%X" % random.randint(0, 15))
        self.set_from_value(''.join(value))


class SByteValue(NumericValue):

    """Represents a simple value of type Edm.SByte"""

    def set_from_numeric_literal(self, num):
        if (not num.ldigits or              # must be left digits
                num.ldigits.isalpha() or    # must not be nan or inf
                num.rdigits is not None or  # must not have '.' or rdigits
                num.edigits is not None):   # must not have an exponent
            raise ValueError("Illegal literal for SByte: %s" %
                             self.join_numeric_literal(num))
        self.set_from_value(int(self.join_numeric_literal(num)))

    def set_from_value(self, new_value):
        if new_value is None:
            self.value = None
        elif isinstance(new_value, (int, long2, float, decimal.Decimal)):
            if new_value < -128 or new_value > 127:
                raise ValueError(
                    "Illegal value for SByte: %s" % str(new_value))
            self.value = int(new_value)
        else:
            raise TypeError("Can't set SByte from %s" % str(new_value))


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


class TypeInstance(DictionaryLike, PEP8Compatibility):

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
        PEP8Compatibility.__init__(self)
        #: the definition of this type
        self.type_def = type_def
        self.data = {}
        if type_def is not None:
            for p in self.type_def.Property:
                self.data[p.name] = p()

    @old_method('AddProperty')
    def add_property(self, pname, pvalue):
        self.data[pname] = pvalue

    def __getitem__(self, name):
        return self.data[name]

    def __iter__(self):
        for p in self.type_def.Property:
            yield p.name

    def __len__(self):
        return len(self.type_def.Property)


class Complex(EDMValue, TypeInstance):

    """Represents a single instance of a :py:class:`ComplexType`."""

    def __init__(self, p_def=None):
        EDMValue.__init__(self, p_def)
        TypeInstance.__init__(
            self, None if p_def is None else p_def.complexType)

    @old_method('IsNull')
    def is_null(self):
        """Complex values are never NULL"""
        return False

    def set_null(self):
        """Sets all simple property values to NULL recursively"""
        for k, v in self.iteritems():
            v.set_null()

    def set_default_value(self):
        """Sets all simple property values to defaults recursively"""
        for k, v in self.iteritems():
            v.set_default_value()

    def merge(self, new_value):
        """Sets this value from *new_value* which must be a
        :py:class:`Complex` instance.

        There is no requirement that *new_value* is of the same type,
        but it must be broadly compatible, which is defined as:

                Any named property present in both the current value and
                *new_value* must be of compatible types.

        Any named property in the current value which is not present in
        *new_value* is left unchanged by this method.

        Null values are not merged."""
        for k, v in self.iteritems():
            nv = new_value.get(k, None)
            if not nv:
                continue
            if isinstance(v, Complex):
                if isinstance(nv, Complex):
                    v.merge(nv)
                else:
                    raise ValueError(
                        "Can't set Complex property from %s" % repr(nv))
            elif isinstance(nv, Complex):
                continue
            else:
                v.set_from_simple_value(nv)


class DeferredValue(MigratedClass):

    """Represents the value of a navigation property."""

    def __init__(self, name, from_entity):
        #: the name of the associated navigation property
        self.name = name
        #: the entity that contains this value
        self.from_entity = from_entity
        #: the definition of the navigation property
        self.p_def = self.from_entity.type_def[name]
        fromM, targetM = self.from_entity.entity_set.get_multiplicity(
            self.name)
        #: True if this deferred value represents a (single) required entity
        self.isRequired = (targetM == Multiplicity.One)
        #: True if this deferred value represents a collection
        self.isCollection = (targetM == Multiplicity.Many)
        self.isExpanded = False
        """True if this deferred value has been expanded.

        An expanded navigation property will return a read-only
        :py:class:`ExpandedEntityCollection` when
        :py:meth:`open` is called."""
        self.bindings = []
        """The list of entity instances or keys to bind to *from_entity*
        when it is inserted or next updated."""
        self.expanded = None

    @old_method('Target')
    def target(self):
        """Returns the target entity set of this navigation (without
        opening the collection)."""
        return self.from_entity.entity_set.get_target(self.name)

    @old_method('GetEntity')
    def get_entity(self):
        """Returns a single entity instance or None.

        If this deferred value represents an entity collection then
        NavigationError is raised."""
        if self.isCollection:
            raise NavigationError(
                "%s.%s is a collection" %
                (self.from_entity.entity_set.name, self.name))
        with self.open() as collection:
            values = collection.values()
            if len(values) == 1:
                return values[0]
            elif len(values) == 0:
                return None
            else:
                raise NavigationError(
                    "Navigation property %s of %s[%s] is not a collection "
                    "but it yielded multiple entities" %
                    (self.name, self.from_entity.entity_set.name,
                     str(self.from_entity.key())))

    @old_method('OpenCollection')
    def open(self):
        """Opens the collection associated with this navigation property.

        Returns an :py:class:`EntityCollection` instance which must be
        closed when it is no longer needed.  This is best achieved with
        the Python with statement using the collection's context-manager
        behaviour.  For example::

            with customer['Orders'].open() as orders:
                    # do something with the orders"""
        if self.from_entity.exists:
            if self.isExpanded:
                return self.expanded
            else:
                collection = self.from_entity.entity_set.open_navigation(
                    self.name, self.from_entity)
                return collection
        else:
            raise NonExistentEntity(
                "Attempt to navigate a non-existent entity: %s.%s" %
                (self.from_entity.type_def.name, self.name))

    def set_expansion_values(self, values):
        """Sets the expansion of this deferred value

        values
            A list of :class:`Entity` instances.

        No call to the underlying data-layer is made, it is assumed that
        values is an appropriate representation of the data that would
        be obtained by executing::

            with self.open() as coll:
                return coll.values()

        The purpose of this method is to allow the re-use of a value
        list that has been obtained previously without having to consult
        the data source again."""
        self.set_expansion(ExpandedEntityCollection(
            from_entity=self.from_entity,
            name=self.name,
            entity_set=self.target(),
            entity_list=values))

    @old_method('SetExpansion')
    def set_expansion(self, expanded):
        """Sets the expansion for this deferred value to the
        :py:class:`ExpandedEntityCollection` given.

        If *expanded* is None then the expansion is removed
        and future calls to :py:meth:`OpenColection` will yield a
        (dynamically created) entity collection."""
        if expanded is None:
            self.isExpanded = False
            self.expanded = None
        else:
            if not isinstance(expanded, ExpandedEntityCollection):
                raise TypeError
            self.isExpanded = True
            self.expanded = expanded

    def expand_collection(self, expand, select):
        """A convenience function of use to data providers.

        Expands this navigation property, further expanding the
        resulting collection of entities using the given *expand* and
        *select* options (see :py:meth:`EntityCollection.set_expand` for
        details)."""
        with self.from_entity.entity_set.open_navigation(
                self.name, self.from_entity) as collection:
            collection.set_expand(expand, select)
            self.set_expansion(collection.expand_collection())

    @old_method('BindEntity')
    def bind_entity(self, target):
        """Binds a *target* entity to this navigation property.

        *target* is either the entity you're binding or its key in the
        target entity set. For example::

                customer['Orders'].bind(1)

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

    def check_navigation_constraint(self):
        """Checks if this navigation property :py:attr:`isRequired` and
        raises :py:class:`NavigationConstraintError` if it has not been
        bound with :py:meth:`bind_entity`.

        This method is only intended to be called on non-existent
        entities."""
        if self.isRequired:
            if not self.bindings:
                raise NavigationConstraintError(
                    "Required navigation property %s of %s is not bound" %
                    (self.name, self.from_entity.entity_set.name))

    def update_bindings(self):
        """Iterates through :py:attr:`bindings` and generates
        appropriate calls to update the collection.

        Unlike the parent Entity's :py:meth:`Entity.commit` method,
        which updates all data and navigation values simultaneously,
        this method can be used to selectively update a single
        navigation property."""
        if self.bindings:
            # get an entity collection for this navigation property
            with self.open() as collection:
                while self.bindings:
                    binding = self.bindings[0]
                    if not isinstance(binding, Entity):
                        # just a key, we'll grab the entity first
                        # which will generate KeyError if it doesn't
                        # exist
                        with collection.entity_set.open() as \
                                base_collection:
                            base_collection.select_keys()
                            binding = base_collection[binding]
                    if binding.exists:
                        if self.isCollection:
                            # use __setitem__ to add this entity to the entity
                            # collection
                            collection[binding.key()] = binding
                        else:
                            # use replace to replace the current binding
                            collection.replace(binding)
                    else:
                        # we need to insert this entity, which will
                        # automatically link to us
                        collection.insert_entity(binding)
                    # success, trim bindings now in case we get an error
                    self.bindings = self.bindings[1:]

    @old_method('ClearBindings')
    def clear_bindings(self):
        """Removes any (unsaved) entity bindings from this navigation
        property."""
        self.bindings = []


class Entity(SortableMixin, TypeInstance):

    """Represents a single instance of an :py:class:`EntityType`.

    Entity instance must only be created by data providers, a child
    class may be used with data provider-specific functionality.  Data
    consumers should use the :py:meth:`EntityCollection.new_entity` or
    :py:class:`EntityCollection.copy_entity` methods to create instances.

    *   entity_set is the entity set this entity belongs to

    Entity instances extend :py:class:`TypeInstance`'s dictionary-like
    behaviour to include all properties.  As a result the dictionary
    values are one of :py:class:`SimpleValue`, :py:class:`Complex` or
    py:class:`DeferredValue` instances.

    Property values are created on construction and cannot be assigned
    directly. To update a simple value use the value's
    :py:meth:`SimpleValue.set_from_value` method::

            e['Name'].set_from_value("Steve")
                    # update simple property Name
            e['Address']['City'].set_from_value("Cambridge")
                    # update City in complex property Address

    A simple valued property that is NULL is still a
    :py:class:`SimpleValue` instance, though it will behave as
    0 in tests::

            e['Name'].set_from_value(None)    # set to NULL
            if e['Name']:
                    print "Will not print!"

    Navigation properties are represented as :py:class:`DeferredValue`
    instances.  A deferred value can be opened in a similar way to an
    entity set::

            # open the collection obtained from navigation property Friends
            with e['Friends'].open() as friends:
                    # iterate through all the friends of entity e
                    for friend in friends:
                            print friend['Name']

    A convenience method is provided when the navigation property points
    to a single entity (or None) by definition::

            mum=e['Mother'].get_entity()     # may return None

    In the EDM one or more properties are marked as forming the entity's
    key.  The entity key is unique within the entity set.  On
    construction, an Entity instance is marked as being 'non-existent',
    :py:attr:`exists` is set to False.  This is consistent with the fact
    that the data properties of an entity are initialised to their
    default values, or NULL if there is no default specified in the
    model. Entity instances returned as values in collection objects
    have exists set to True.

    Entities from the same entity set can be compared (unlike
    :class:`Complex` instances), comparison is done by :meth:`key`.
    Therefore, two instances that represent that same entity will
    compare equal.

    If an entity does not exist, open will fail if called on
    one of its navigation properties with :py:class:`NonExistentEntity`.

    You can use :py:meth:`is_entity_collection` to determine if a property
    will return an :py:class:`EntityCollection` without the cost of
    accessing the data source itself."""

    def __init__(self, entity_set):
        self.entity_set = entity_set
        TypeInstance.__init__(self, entity_set.entityType)
        #: whether or not the instance exists in the entity set
        self.exists = False
        #: the set of selected property names or None if all properties
        #: are selected
        self.selected = None
        if self.type_def is None:
            raise ModelIncomplete("Unbound EntitySet: %s (%s)" % (
                self.entity_set.name, self.entity_set.entityTypeName))
        for np in self.type_def.NavigationProperty:
            self.data[np.name] = DeferredValue(np.name, self)

    def sortkey(self):
        return self.key()

    def otherkey(self, other):
        # entity > None would always return True, but we really
        # wanted to ensure that entity == None always returned False!
        #
        # if other is None:
        #    return 1
        if (not isinstance(other, Entity) or
                other.entity_set is not self.entity_set):
            return NotImplemented
        return other.key()

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

    @old_method('DataKeys')
    def data_keys(self):
        """Iterates through the names of this entity's data properties only

        The order of the names is always the order they are defined in
        the metadata model."""
        for p in self.type_def.Property:
            yield p.name

    def data_items(self):
        """Iterator that yields tuples of (key,value) for this entity's
        data properties only.

        The order of the items is always the order they are defined in
        the metadata model."""
        for p in self.type_def.Property:
            yield p.name, self[p.name]

    def merge(self, fromvalue):
        """Sets this entity's value from *fromvalue* which must be a
        :py:class:`TypeInstance` instance.  In other words, it may
        be either an Entity or a Complex value.

        There is no requirement that *fromvalue* be of the same type,
        but it must be broadly compatible, which is defined as:

                Any named property present in both the current value and
                *fromvalue* must be of compatible types.

        Any named property in the current value which is not present in
        *fromvalue* is left unchanged by this method.

        Null values in fromvalue are not copied."""
        for k, v in self.data_items():
            if k in self.entity_set.keys:
                continue
            nv = fromvalue.get(k, None)
            if not nv:
                continue
            if isinstance(v, Complex):
                if isinstance(nv, Complex):
                    v.merge(nv)
                else:
                    continue
            elif isinstance(nv, Complex):
                continue
            else:
                v.set_from_simple_value(nv)

    @old_method('NavigationKeys')
    def navigation_keys(self):
        """Iterates through the names of this entity's navigation properties only.

        The order of the names is always the order they are defined in
        the metadata model."""
        for np in self.type_def.NavigationProperty:
            yield np.name

    @old_method('NavigationItems')
    def navigation_items(self):
        """Iterator that yields tuples of (key,deferred value) for this
        entity's navigation properties only.

        The order of the items is always the order they are defined in
        the metadata model."""
        for np in self.type_def.NavigationProperty:
            yield np.name, self[np.name]

    @old_method('CheckNavigationConstraints')
    def check_navigation_constraints(self, ignore_end=None):
        """For entities that do not yet exist, checks that each of the
        required navigation properties has been bound (with
        :py:meth:`DeferredValue.bind_entity`).

        If a required navigation property has not been bound then
        :py:class:`NavigationConstraintError` is raised.

        If the entity already exists, :py:class:`EntityExists` is
        raised.

        For data providers, *ignore_end* may be set to an association set
        end bound to this entity's entity set.  Any violation of the
        related association is ignored."""
        if self.exists:
            raise EntityExists(
                "check_navigation_constraints: entity %s already exists" % str(
                    self.get_location()))
        bad_end = self.entity_set.unboundPrincipal
        if bad_end and bad_end != ignore_end:
            raise NavigationConstraintError(
                "entity %s has an unbound principal" %
                str(self.get_location()))
        ignore_name = self.entity_set.linkEnds.get(ignore_end, None)
        for name, np in self.navigation_items():
            if name != ignore_name:
                np.check_navigation_constraint()

    def __len__(self):
        return len(self.type_def.Property) + \
            len(self.type_def.NavigationProperty)

    @old_method('IsNavigationProperty')
    def is_navigation_property(self, name):
        """Returns true if name is the name of a navigation property,
        False otherwise."""
        try:
            p_def = self.type_def[name]
            return isinstance(p_def, NavigationProperty)
        except KeyError:
            return False

    @old_method('IsEntityCollection')
    def is_entity_collection(self, name):
        """Returns True if *name* is the name of a navigation property
        that points to an entity collection, False otherwise."""
        return self.is_navigation_property(
            name) and self.entity_set.is_entity_collection(name)

    def __getitem__(self, name):
        if name in self.data:
            return self.data[name]
        else:
            raise KeyError(name)

    def update(self):
        warnings.warn(
            "Entity.Update is deprecated, use commit instead\n",
            DeprecationWarning,
            stacklevel=3)
        return self.commit()

    def commit(self):
        """Updates this entity following modification.

        You can use select rules to provide a hint about which fields
        have been updated.  By the same logic, you cannot update a
        property that is not selected!

        The default implementation opens a collection object from the
        parent entity set and calls
        :py:meth:`EntityCollection.update_entity`."""
        with self.entity_set.open() as collection:
            collection.update_entity(self)

    @old_method('Delete')
    def delete(self):
        """Deletes this entity from the parent entity set.

        The default implementation opens a collection object from the
        parent entity set and uses the del operator.

        Data providers must ensure that the entity's :py:attr:`exists`
        flag is set to False after deletion."""
        with self.entity_set.open() as collection:
            del collection[self.key()]
        self.exists = False

    def key(self):
        """Returns the entity key as a single python value or a tuple of
        python values for compound keys.

        The order of the values is always the order of the PropertyRef
        definitions in the associated EntityType's :py:class:`key`."""
        if len(self.type_def.Key.PropertyRef) == 1:
            result = self[self.type_def.Key.PropertyRef[0].name].value
            if result is None:
                raise KeyError("Entity with NULL key not allowed")
            return result
        else:
            k = []
            null_flag = True
            for pRef in self.type_def.Key.PropertyRef:
                result = self[pRef.name].value
                k.append(result)
                if result is not None:
                    null_flag = False
            if null_flag:
                raise KeyError("Entity with NULL key not allowed")
            return tuple(k)

    def set_key(self, key):
        """Sets this entity's key from a single python value or tuple.

        The entity must be non-existent or :py:class:`EntityExists` is
        raised."""
        if self.exists:
            raise EntityExists("set_key not allowed; %s[%s] already exists" % (
                self.entity_set.name, str(self.key())))
        if len(self.type_def.Key.PropertyRef) == 1:
            self[self.type_def.Key.PropertyRef[0].name].set_from_value(key)
        else:
            k = iter(key)
            for pRef in self.type_def.Key.PropertyRef:
                self[pRef.name].set_from_value(next(k))

    def auto_key(self, base=None):
        """Sets the key to a random value

        base
            An optional key suggestion which can be used to influence
            the choice of automatically generated key."""
        if base:
            if len(self.type_def.Key.PropertyRef) > 1:
                base = iter(base)
            else:
                base = iter([base])
        for pRef in self.type_def.Key.PropertyRef:
            if base is not None:
                bv = self.type_def[pRef.name]()
                bv.set_from_value(next(base))
            else:
                bv = None
            v = self[pRef.name]
            v.set_random_value(bv)

    @old_method('KeyDict')
    def key_dict(self):
        """Returns the entity key as a dictionary mapping key property
        names onto :py:class:`SimpleValue` instances."""
        k = {}
        for pRef in self.type_def.Key.PropertyRef:
            k[pRef.name] = self[pRef.name]
        return k

    @old_method('Expand')
    def expand(self, expand, select=None):
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
        expand method call.

        The selection rules in effect are saved in the :py:attr:`select`
        member and can be tested using :py:meth:`is_selected`."""
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
                for k in self.data_keys():
                    self.selected.add(k)
            else:
                # Force unselected values to NULL
                for k, v in self.data_items():
                    if k not in self.entity_set.keys and \
                            k not in self.selected:
                        v.set_null()
        # Now expand this entity's navigation properties
        if expand:
            for k, v in self.navigation_items():
                if k in expand:
                    if k in select:
                        sub_select = select[k]
                        if sub_select is None:
                            # $select=Orders&$expand=Orders/OrderLines
                            # => $select=Orders/*
                            sub_select = {'*': None}
                    else:
                        sub_select = None
                    v.expand_collection(expand[k], sub_select)

    def Expanded(self, name):   # noqa
        warnings.warn("Entity.Expanded is deprecated, use, e.g., "
                      "customer['Orders'].isExpanded instead",
                      DeprecationWarning, stacklevel=3)
        return self[name].isExpanded

    @old_method('Selected')
    def is_selected(self, name):
        """Returns true if the property *name* is selected in this entity.

        You should not rely on the value of a unselected property, in most
        cases it will be set to NULL."""
        return self.selected is None or name in self.selected

    @old_method('ETag')
    def etag(self):
        """Returns a list of EDMValue instance values to use for optimistic
        concurrency control or None if the entity does not support it (or if
        all concurrency tokens are NULL or unselected)."""
        etag = []
        for p_def in self.type_def.Property:
            if p_def.concurrencyMode == ConcurrencyMode.Fixed and \
                    self.is_selected(p_def.name):
                token = self[p_def.name]
                if token:
                    # only append non-null values
                    etag.append(token)
        if etag:
            return etag
        else:
            return None

    @old_method('ETagValues')
    def etag_values(self):
        """Returns a list of EDMValue instance values that may be used
        for optimistic concurrency control.  The difference between this
        method and :py:meth:`etag` is that this method returns all
        values even if they are NULL or unselected.  If there are no
        concurrency tokens then an empty list is returned."""
        etag = []
        for p_def in self.type_def.Property:
            if p_def.concurrencyMode == ConcurrencyMode.Fixed:
                token = self[p_def.name]
                etag.append(token)
        return etag

    def generate_ctoken(self):
        """Returns a hash object representing this entity's value.

        The hash is a SHA256 obtained by concatenating the literal
        representations of all data properties (strings are UTF-8
        encoded) except the keys and properties which have Fixed
        concurrency mode."""
        h = hashlib.sha256()
        key = self.key_dict()
        for p_def in self.type_def.Property:
            if p_def.concurrencyMode == ConcurrencyMode.Fixed:
                continue
            elif p_def.name in key:
                continue
            v = self[p_def.name]
            if isinstance(v, Complex):
                self._complex_ctoken(h, v)
            elif not v:
                continue
            else:
                h.update(to_text(v).encode('utf-8'))
        return h

    def _complex_ctoken(self, h, ct):
        for p_def in ct.type_def.Property:
            # complex types can't have properties used as concurrency
            # tokens or keys
            v = ct[p_def.name]
            if isinstance(v, Complex):
                self._complex_ctoken(h, v)
            elif not v:
                continue
            else:
                h.update(to_text(v).encode('utf-8'))

    @old_method('SetConcurrencyTokens')
    def set_concurrency_tokens(self):
        """A utility method for data providers.

        Sets all :py:meth:`etag_values` using the following algorithm:

        1.  Binary values are set directly from the output of
                :py:meth:`generate_ctoken`

        2.  String values are set from the hexdigest of the output
                :py:meth:`generate_ctoken`

        3.  Integer values are incremented.

        4.  DateTime and DateTimeOffset values are set to the current
                time in UTC (and nudged by 1s if necessary)

        5.  Guid values are set to a new random (type 4) UUID.

        Any other type will generate a ValueError."""
        for t in self.etag_values():
            if isinstance(t, BinaryValue):
                h = self.generate_ctoken().digest()
                if t.p_def.maxLength is not None and \
                        t.p_def.maxLength < len(h):
                    # take the right-most bytes
                    h = h[len(h) - t.p_def.maxLength:]
                if t.p_def.fixedLength:
                    if t.p_def.maxLength > len(h):
                        # we need to zero-pad our binary string
                        h = h.ljust(t.p_def.maxLength, '\x00')
                t.set_from_value(h)
            elif isinstance(t, StringValue):
                h = self.generate_ctoken().hexdigest()
                if t.p_def.maxLength is not None and \
                        t.p_def.maxLength < len(h):
                    # take the right-most bytes
                    h = h[len(h) - t.p_def.maxLength:]
                if t.p_def.fixedLength:
                    if t.p_def.maxLength > len(h):
                        # we need to zero-pad our binary string
                        h = h.ljust(t.p_def.maxLength, '0')
                t.set_from_value(h)
            elif isinstance(t, (Int16Value, Int32Value, Int64Value)):
                if t:
                    t.set_from_value(t.value + 1)
                else:
                    t.set_from_value(1)
            elif isinstance(t, (DateTimeValue, DateTimeOffsetValue)):
                old_t = t.value
                t.set_from_value(iso8601.TimePoint.from_now_utc())
                if t.value == old_t:
                    # that was quick, push it 1s into the future
                    new_time, overflow = t.value.time.offset(seconds=1)
                    t.set_from_value(iso8601.TimePoint(
                        date=t.value.date.offset(days=overflow),
                        time=new_time))
            elif isinstance(t, GuidValue):
                old_t = t.value
                while t.value == old_t:
                    t.set_from_value(uuid.uuid4())
            else:
                raise ValueError(
                    "Can't auto generate concurrency token for %s" %
                    t.p_def.type)

    @old_method('ETagIsStrong')
    def etag_is_strong(self):
        """Tests the strength of this entity's etag

        Defined by RFC2616::

            A "strong entity tag" MAY be shared by two entities of a
            resource only if they are equivalent by octet equality.

        The default implementation returns False which is consistent
        with the implementation of :py:meth:`generate_ctoken` as that
        does not include the key fields."""
        return False


class EntityCollection(DictionaryLike, PEP8Compatibility):

    """Represents a collection of entities from an :py:class:`EntitySet`.

    To use a database analogy, EntitySet's are like tables whereas
    EntityCollections are more like the database cursors that you use to
    execute data access commands.  An entity collection may consume
    physical resources (like a database connection) and so should be
    closed with the :py:meth:`close` method when you're done.

    Entity collections support the context manager protocol in python so
    you can use them in with statements to make clean-up easier::

            with entity_set.open() as collection:
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
    :py:meth:`Entity.key` method.

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
                        # paramA and paramB are examples of how to
                        # consume private keyword arguments in this
                        # method so that they aren't passed on to the
                        # next __init__
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
        PEP8Compatibility.__init__(self)
        if kwargs:
            logging.debug("Unabsorbed kwargs in EntityCollection constructor")
        #: the entity set from which the entities are drawn
        self.entity_set = entity_set
        # : the name of :py:attr:`entity_set`
        self.name = self.entity_set.name
        #: the expand query option in effect
        self.expand = None
        #: the select query option in effect
        self.select = None
        #: a filter or None for no filter (see :py:meth:`check_filter`)
        self.filter = None
        #: a list of orderby rules or None for no ordering
        self.orderby = None
        #: the skip query option in effect
        self.skip = None
        #: the top query option in effect
        self.top = None
        #: the provider-enforced maximum page size in effect
        self.topmax = None
        self.skiptoken = None
        self.nextSkiptoken = None
        self.inlinecount = False
        """True if inlinecount option is in effect

        The inlinecount option is used to alter the representation of
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

    def get_location(self):
        """Returns the location of this collection as a
        :py:class:`~pyslet.rfc2396.URI` instance.

        By default, the location is given as the location of the
        :py:attr:`entity_set` from which the entities are drawn."""
        return self.entity_set.get_location()

    def get_title(self):
        """Returns a user recognisable title for the collection.

        By default this is the fully qualified name of the entity set
        in the metadata model."""
        return self.entity_set.get_fqname()

    @old_method('Expand')
    def set_expand(self, expand, select=None):
        """Sets the expand and select query options for this collection.

        The expand query option causes the named navigation properties
        to be expanded and the associated entities to be loaded in to
        the entity instances before they are returned by this collection.

        expand
            A dictionary of expand rules.  Expansions can be chained,
            represented by the dictionary entry also being a dictionary::

                # expand the Customer navigation property...
                {'Customer': None }
                # expand the Customer and Invoice navigation properties
                {'Customer': None, 'Invoice': None}
                # expand the Customer property and then the Orders
                # property within Customer
                {'Customer': {'Orders': None}}

        The select query option restricts the properties that are set in
        returned entities.  The *select* option is a similar dictionary
        structure, the main difference being that it can contain the
        single key '*' indicating that all *data* properties are
        selected."""
        self.entity_set.entityType.validate_expansion(expand, select)
        self.expand = expand
        self.select = select
        self.lastEntity = None

    @old_method('SelectKeys')
    def select_keys(self):
        """Sets the select rule to select the key property/properties only.

        Any expand rule is removed."""
        select = {}
        for k in self.entity_set.keys:
            select[k] = None
        self.set_expand(None, select)

    def expand_entities(self, entity_iterable):
        """Utility method for data providers.

        Given an object that iterates over all entities in the
        collection, returns a generator function that returns expanded
        entities with select rules applied according to
        :py:attr:`expand` and :py:attr:`select` rules.

        Data providers should use a better method of expanded entities
        if possible as this implementation simply iterates through the
        entities and calls :py:meth:`Entity.expand` on each one."""
        for e in entity_iterable:
            if self.expand or self.select:
                e.expand(self.expand, self.select)
            yield e

    @old_method('Filter')
    def set_filter(self, filter):   # noqa
        """Sets the filter object for this collection

        See :py:meth:`check_filter` for more information."""
        self.filter = filter
        self.set_page(None)
        self.lastEntity = None

    def filter_entities(self, entity_iterable):
        """Utility method for data providers.

        Given an object that iterates over all entities in the
        collection, returns a generator function that returns only those
        entities that pass through the current :py:attr:`filter` object.

        Data providers should use a better method of filtering entities
        if possible as this implementation simply iterates through the
        entities and calls :py:meth:`check_filter` on each one."""
        for e in entity_iterable:
            if self.check_filter(e):
                yield e

    def check_filter(self, entity):
        """Checks *entity* against the current filter object and returns
        True if it passes.

        This method is really a placeholder.  Filtering is not covered
        in the CSDL model itself but is a feature of the OData
        :py:mod:`pyslet.odata2.core` module.

        See
        :py:meth:`pyslet.odata2.core.EntityCollectionMixin.check_filter`
        for more.  The implementation in the case class simply raises
        NotImplementedError if a filter has been set."""
        if self.filter is None:
            return True
        else:
            raise NotImplementedError("Collection does not support filtering")

    @old_method('OrderBy')
    def set_orderby(self, orderby):
        """Sets the orderby rules for this collection.

        orderby
            A list of tuples, each consisting of::

                (an order object as used by :py:meth:`calculate_order_key` ,
                 1 | -1 )"""
        self.orderby = orderby
        self.set_page(None)

    def calculate_order_key(self, entity, order_object):
        """Given an entity and an order object returns the key used to
        sort the entity.

        This method is really a placeholder.  Ordering is not covered
        in the CSDL model itself but is a feature of the OData
        :py:mod:`pyslet.odata2.core` module.

        See
        :py:meth:`pyslet.odata2.core.EntityCollectionMixin.calculate_order_key`
        for more.  The implementation in the case class simply raises
        NotImplementedError."""
        raise NotImplementedError("Collection does not support ordering")

    def order_entities(self, entity_iterable):
        """Utility method for data providers.

        Given an object that iterates over the entities in random order,
        returns a generator function that returns the same entities in
        sorted order (according to the :py:attr:`orderby` object).

        This implementation simply creates a list and then sorts it
        based on the output of :py:meth:`calculate_order_key` so is not
        suitable for use with long lists of entities.  However, if no
        ordering is required then no list is created."""
        elist = None
        if self.paging:
            elist = list(entity_iterable)
            elist.sort(key=lambda x: x.key())
        if self.orderby:
            if elist is None:
                elist = list(entity_iterable)
            # we avoid Py3 warnings by doing multiple sorts with a key function
            for rule, ruleDir in reversed(self.orderby):
                elist.sort(key=lambda x: self.calculate_order_key(
                    x, rule), reverse=True if ruleDir < 0 else False)
        if elist:
            for e in elist:
                yield e
        else:
            for e in entity_iterable:
                yield e

    @old_method('SetInlineCount')
    def set_inlinecount(self, inlinecount):
        """Sets the inline count flag for this collection."""
        self.inlinecount = inlinecount

    def new_entity(self):
        """Returns a new py:class:`Entity` instance suitable for adding
        to this collection.

        The data properties of the entity are set to null, *not* to their
        default values, even if the property is marked as not nullable.

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

    @old_method('CopyEntity')
    def copy_entity(self, entity):
        """Creates a new *entity* copying the value from *entity*

        The key is not copied and is initially set to NULL."""
        new_entity = self.new_entity()
        new_entity.merge(entity)
        return new_entity

    def insert_entity(self, entity):
        """Inserts *entity* into this entity set.

        After a successful call to insert_entity:

        1.  *entity* is updated with any auto-generated values such as
                an autoincrement correct key.

        2.  :py:attr:`exists` is set to True for *entity*

        Data providers must override this method if the collection is
        writable.

        If the call is unsuccessful then *entity* should be discarded as
        its associated bindings may be in a misleading state (when
        compared to the state of the data source itself).

        A general :py:class:`ConstraintError` will be raised when the
        insertion violates model constraints (including an attempt to
        create two entities with duplicate keys)."""
        raise NotImplementedError

    def update_entity(self, entity, merge=True):
        """Updates *entity* which must already be in the entity set.

        The optional merge parameter can be used to force replace
        semantics instead of the default merge.  When merging, any
        unselected data properties are left unchanced.  With merge=False
        unselected data properties are *replaced* with their default
        values as defined by the underlying container.  You will have to
        read back the entity (without a select filter) to obtain those
        defaults as the values in the entity objects.

        Data providers must override this method if the collection is
        writable."""
        raise NotImplementedError

    def update_bindings(self, entity):
        """Iterates through the :py:meth:`Entity.navigation_items` and
        generates appropriate calls to create/update any pending
        bindings.

        Unlike the :py:meth:`commit` method, which updates all data and
        navigation values simultaneously, this method can be used to
        selectively update just the navigation properties."""
        for k, dv in entity.navigation_items():
            dv.update_bindings()

    def __getitem__(self, key):
        # key=self.entity_set.get_key(key)
        logging.warning(
            "EntityCollection.__getitem__ without override in %s",
            self.__class__.__name__)
        if self.lastEntity and self.lastEntity.key() == key:
            result = self.lastEntity
            return result
        for e in self.itervalues():
            self.lastEntity = e
            if e.key() == key:
                return e
        raise KeyError(to_text(key))

    def __setitem__(self, key, value):
        if not isinstance(value, Entity) or \
                value.entity_set is not self.entity_set:
            raise TypeError
        if key != value.key():
            raise ValueError
        if key not in self:
            raise KeyError(to_text(key))

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

    @old_method('TopMax')
    def set_topmax(self, topmax):
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
            emin = int(self.skiptoken, 16)
        except (TypeError, ValueError):
            # not a skip token we recognise, do nothing
            emin = None
        if emin is None:
            emin = 0
        if self.skip is not None:
            emin = self.skip + emin
        if self.topmax:
            if self.top is None or self.top > self.topmax:
                # may be truncated
                emax = emin + self.topmax
                self.nextSkiptoken = "%X" % (emin + self.topmax)
            else:
                # top not None and <= topmax
                emax = emin + self.top
        else:
            # no forced paging
            if self.top is None:
                emax = None
            else:
                emax = emin + self.top
        try:
            self.paging = True
            if emax is None:
                for e in self.itervalues():
                    self.lastEntity = e
                    if i >= emin:
                        yield e
                    i = i + 1
            else:
                for e in self.itervalues():
                    self.lastEntity = e
                    if i < emin:
                        i = i + 1
                    elif i < emax:
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

    def itervalues(self):
        """Iterates over the collection.

        The collection is filtered as defined by :py:meth:`set_filter` and
        sorted according to any rules defined by :py:meth:`set_orderby`.

        Entities are also expanded and selected according to the rules
        defined by :py:class:`set_expand`.

        Data providers must override this implementation which, by
        default, returns no entities (simulating an empty collection)."""
        return []

    def __iter__(self):
        for e in self.itervalues():
            self.lastEntity = e
            yield e.key()
        self.lastEntity = None

    def iteritems(self):
        for e in self.itervalues():
            self.lastEntity = e
            yield e.key(), e


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
        #: the source entity
        self.from_entity = from_entity
        #: the :py:class:`AssociationSetEnd` that represents the source
        #: of this association
        self.from_end = self.from_entity.entity_set.navigation[self.name]
        #: the navigation property's definition in the metadata model
        self.p_def = self.from_entity.type_def[name]
        self.fromMultiplicity, self.toMultiplicity = \
            self.from_entity.entity_set.get_multiplicity(self.name)
        """The endpoint multiplicities of this link.  Values are defined
        by :py:class:`Multiplicity`"""

    def expand_collection(self):
        return ExpandedEntityCollection(
            from_entity=self.from_entity,
            name=self.name,
            entity_set=self.entity_set,
            entity_list=self.values())

    def insert_entity(self, entity):
        """Inserts a new *entity* into the target entity set *and*
        simultaneously creates a link to it from the source entity."""
        with self.entity_set.open() as base_collection:
            base_collection.insert_entity(entity)
            self[entity.key()] = entity

    def update_entity(self, entity, merge=True):
        with self.entity_set.open() as base_collection:
            base_collection.update_entity(entity, merge)

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
        equivalent to __setitem__(entity.key(),entity).

        Although for some collections this is equivalent to
        :py:meth:`clear` followed by __setitem__, this method must be
        used to combine these operations into a single call when the
        collection is required to contain exactly one link at all
        times."""
        self.clear()
        self[entity.key()] = entity


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

    The named argument *entity_list* passed to this constructor is a
    simple python list of the entities the expanded collection contains.
    Internally a dictionary of the entities is built to speed up access
    by key."""

    def __init__(self, entity_list, **kwargs):
        super(ExpandedEntityCollection, self).__init__(**kwargs)
        self.entity_list = entity_list
        self.entityDict = {}
        for e in self.entity_list:
            # Build a dictionary
            self.entityDict[e.key()] = e

    def itervalues(self):
        return self.order_entities(
            self.expand_entities(
                self.filter_entities(
                    self.entity_list)))

    def __getitem__(self, key):
        result = self.entityDict[key]
        if self.check_filter(result):
            if self.expand or self.select:
                result.expand(self.expand, self.select)
            return result
        raise KeyError("%s" % to_text(key))


class FunctionEntityCollection(EntityCollection):

    """Represents the collection of entities returned by a specific
    execution of a :py:class:`FunctionImport`"""

    def __init__(self, function, params, **kwargs):
        if function.is_entity_collection():
            self.function = function
            self.params = params
            super(FunctionEntityCollection, self).__init__(
                entity_set=self.function.entity_set, **kwargs)
        else:
            raise TypeError(
                "Function call does not return a collection of entities")

    def set_expand(self, expand, select=None):
        """This option is not supported on function results"""
        raise NotImplementedError("Expand/Select option on Function result")

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
        if function.is_collection():
            if function.is_entity_collection():
                raise TypeError("FunctionCollection must not return a "
                                "collection of entities")
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

    def update_type_refs(self, scope, stop_on_errors=False):
        """Updates inter-type references

        Abstract method, called on a type definition, or type containing
        object.

        scope
            The :py:class:`NameTableMixin` object *containing* the
            top-level :py:class:`Schema` object(s).

        stop_on_errors
            Determines the handling of missing keys.  If stop_on_errors
            is False (the default) missing keys are ignored (internal
            object references are set to None).  If stop_on_errors is
            True KeyError is raised.

        The CSDL model makes heavy use of named references between
        objects. The purpose of this method is to use the *scope* object
        to look up inter-type references and to set or update any
        corresponding internal object references."""
        pass

    def update_set_refs(self, scope, stop_on_errors=False):
        """Updates inter-object references

        Abstract method, called on a set declaration, or set containing
        object to update all its inter-object references.

        This method works in a very similar way to
        :py:meth:`update_type_refs` but it is called afterwards.  This
        two-pass approach ensures that set declarations are linked after
        *all* type definitions have been updated in all schemas that are
        in scope."""
        pass


class Documentation(CSDLElement):

    """Used to document elements in the metadata model"""
    XMLNAME = (EDM_NAMESPACE, 'Documentation')
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        self.Summary = None
        self.LongDescription = None

    def get_children(self):
        if self.Summary:
            yield self.Summary
        if self.LongDescription:
            yield self.LongDescription


class Summary(CSDLElement):

    """Used to document elements in the metadata model"""
    XMLNAME = (EDM_NAMESPACE, 'Summary')
    XMLCONTENT = xml.ElementType.Mixed


class LongDescription(CSDLElement):

    """Used to document elements in the metadata model"""
    XMLNAME = (EDM_NAMESPACE, 'LongDescription')
    XMLCONTENT = xml.ElementType.Mixed


class TypeRef(object):

    """Represents a type reference.

    Created from a formatted string type definition and a scope (in
    which type definitions are looked up).

    TypeRef objects are callable with an optional
    :py:class:`SimpleValue` or :py:class:`TypeInstance` object.
    Calling a TypeRef returns an instance of the type referred to with a
    default value (typically NULL) or a value set from the optional
    parameter."""

    def __init__(self, type_def, scope):
        #: True if this type is a collection type
        self.collection = False
        #: a :py:class:`SimpleType` value if this is a primitive type
        self.simpleTypeCode = None
        #: a :py:class:`ComplexType` or :py:class:`EntityType` instance.
        self.type_def = None
        if "(" in type_def and type_def[-1] == ')':
            if type_def[:type_def.index('(')].lower() != "collection":
                raise KeyError("%s is not a valid type" % type_def)
            self.collection = True
            type_name = type_def[type_def.index('(') + 1:-1]
        else:
            type_name = type_def
        try:
            self.simpleTypeCode = SimpleType.from_str_lower(type_name)
        except ValueError:
            # must be a complex or entity type defined in scope
            self.simpleTypeCode = None
            self.type_def = scope[type_name]
            if not isinstance(self.type_def, (ComplexType, EntityType)):
                raise KeyError("%s is not a valid type" % type_name)

    def __call__(self, value=None):
        if self.simpleTypeCode is not None:
            result = SimpleValue.from_type(self.simpleTypeCode)
            if isinstance(value, SimpleValue):
                result.set_from_simple_value(value)
            elif value is not None:
                raise ValueError(
                    "Can't set %s from %s" %
                    (SimpleType.to_str(self.simpleTypeCode),
                     repr(value)))
        else:
            raise NotImplementedError("Parameter value of non-primitive type")
        return result


class Using(CSDLElement):
    XMLNAME = (EDM_NAMESPACE, 'Using')

#: we define the constant MAX to represent the special 'max' value of
#: maxLength
MAX = -1


@old_function('DecodeMaxLength')
def maxlength_from_str(value):
    """Decodes a maxLength value from a character string.

    "The maxLength facet accepts a value of the literal string "max" or
    a positive integer with value ranging from 1 to 2^31"

    The value 'max' is returned as the value :py:data:`MAX`"""
    if value.lower() == "max":
        return MAX
    else:
        result = xsi.integer_from_str(value)
        if result < 1:
            raise ValueError("Can't read maxLength from %s" % repr(value))
        return result


@old_function('EncodeMaxLength')
def maxlength_to_str(value):
    """Encodes a maxLength value as a character string."""
    if value == MAX:
        return "max"
    else:
        return xsi.integer_to_str(value)


class ConcurrencyMode(xsi.EnumerationNoCase):

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

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'None': 1,
        'Fixed': 2
    }


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
    XMLATTR_Nullable = ('nullable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_DefaultValue = 'defaultValue'
    XMLATTR_MaxLength = ('maxLength', maxlength_from_str, maxlength_to_str)
    XMLATTR_FixedLength = (
        'fixedLength', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_Precision = ('precision', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_Scale = ('scale', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_Unicode = ('unicode', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_Collation = 'collation'
    XMLATTR_SRID = 'SRID'
    XMLATTR_CollectionKind = 'collectionKind'
    XMLATTR_ConcurrencyMode = (
        'concurrencyMode',
        ConcurrencyMode.from_str_lower,
        ConcurrencyMode.to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the declared name of the property
        self.name = "Default"
        #: the name of the property's type
        self.type = "Edm.String"
        #: one of the :py:class:`SimpleType` constants if the property
        #: has a simple type
        self.simpleTypeCode = None
        #: the associated :py:class:`ComplexType` if the property has a
        #: complex type
        self.complexType = None
        #: if the property may have a null value
        self.nullable = True
        #: a string containing the default value for the property or
        #: None if no default is defined
        self.defaultValue = None
        #: the maximum length permitted for property values
        self.maxLength = None
        #: a boolean indicating that the property must be of length
        #: :py:attr:`maxLength`
        self.fixedLength = None
        #: a positive integer indicating the maximum number of decimal
        #: digits (decimal values)
        self.precision = None
        #: a non-negative integer indicating the maximum number of
        #: decimal digits to the right of the point
        self.scale = None
        #: a boolean indicating that a string property contains unicode
        #: data
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

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def update_type_refs(self, scope, stop_on_errors=False):
        try:
            self.simpleTypeCode = SimpleType.from_str_lower(self.type)
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
                if stop_on_errors:
                    raise

    def __call__(self, literal=None):
        result = EDMValue.from_property(self)
        if isinstance(result, SimpleValue) and literal is not None:
            result.set_from_literal(literal)
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
        #: the name of this link's source role
        self.fromRole = None
        #: the name of this link's target role
        self.toRole = None
        #: the :py:class:`AssociationEnd` instance representing this
        #: link's source
        self.from_end = None
        #: the :py:class:`AssociationEnd` instance representing this
        #: link's target
        self.to_end = None
        #: flag set if :py:attr:`Association` is ambiguous within the
        #: parent EntityType, :py:attr:`backLink` will never be set!
        self.ambiguous = False
        #: the :py:class:`NavigationProperty` that provides the back
        #: link (or None, if this link is one-way)
        self.backLink = None
        # : the optional :py:class:`Documentation`
        self.Documentation = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def update_type_refs(self, scope, stop_on_errors=False):
        # must be a complex type defined elsewhere
        self.association = self.from_end = self.to_end = None
        try:
            self.association = scope[self.relationship]
            if not isinstance(self.association, Association):
                raise KeyError("%s is not an association" % self.relationship)
            self.from_end = self.association[self.fromRole]
            if self.from_end is None or not isinstance(self.from_end,
                                                       AssociationEnd):
                raise KeyError(
                    "%s is not a valid end-point for %s" %
                    (self.fromRole, self.relationship))
            self.to_end = self.association[self.toRole]
            if self.to_end is None or not isinstance(self.to_end,
                                                     AssociationEnd):
                raise KeyError(
                    "%s is not a valid end-point for %s" %
                    (self.fromRole, self.relationship))
        except KeyError:
            self.association = self.from_end = self.to_end = None
            if stop_on_errors:
                raise

    def mark_as_ambiguous(self):
        self.ambiguous = True
        self.backLink = None


class Key(CSDLElement):

    """Models the key fields of an :py:class:`EntityType`"""
    XMLNAME = (EDM_NAMESPACE, 'Key')

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: a list of :py:class:`PropertyRef`
        self.PropertyRef = []

    def get_children(self):
        for child in self.PropertyRef:
            yield child

    def update_type_refs(self, scope, stop_on_errors=False):
        for pr in self.PropertyRef:
            pr.update_type_refs(scope, stop_on_errors)


class PropertyRef(CSDLElement):

    """Models a reference to a single property within a :py:class:`Key`."""
    XMLNAME = (EDM_NAMESPACE, 'PropertyRef')

    XMLATTR_Name = 'name'

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the name of this (key) property
        self.name = 'Default'
        #: the :py:class:`Property` instance of this (key) property
        self.property = None

    def update_type_refs(self, scope, stop_on_errors=False):
        """Sets :py:attr:`property`"""
        self.property = None
        try:
            type_def = self.find_parent(EntityType)
            if type_def is None:
                raise KeyError(
                    "PropertyRef %s has no parent EntityType" % self.name)
            self.property = type_def[self.name]
            if not isinstance(self.property, Property):
                raise KeyError("%s is not a Property" % self.name)
        except KeyError:
            self.property = None
            if stop_on_errors:
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
    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_BaseType = 'baseType'
    XMLATTR_Abstract = ('abstract', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        #: the declared name of this type
        self.name = "Default"
        #: the name of the base-type for this type
        self.baseType = None
        self.abstract = False
        # : the optional :py:class:`Documentation`
        self.Documentation = None
        #: a list of :py:class:`Property`
        self.Property = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.Property,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def content_changed(self):
        for p in self.Property:
            self.declare(p)

    def update_type_refs(self, scope, stop_on_errors=False):
        for p in self.Property:
            p.update_type_refs(scope, stop_on_errors)

    @old_method('GetFQName')
    def get_fqname(self):
        """Returns the full name of this type

        Includes the schema namespace prefix."""
        schema = self.find_parent(Schema)
        if schema is None:
            return self.name
        else:
            return ''.join((schema.name, '.', self.name))


class EntityType(Type):

    """Models the key and the collection of properties that define a set
    of :py:class:`Entity`"""

    XMLNAME = (EDM_NAMESPACE, 'EntityType')
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        Type.__init__(self, parent)
        #: the :py:class:`Key`
        self.Key = None
        # : a list of :py:class:`NavigationProperty`
        self.NavigationProperty = []

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        if self.Key:
            yield self.Key
        for child in itertools.chain(
                self.Property,
                self.NavigationProperty,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def content_changed(self):
        super(EntityType, self).content_changed()
        for np in self.NavigationProperty:
            self.declare(np)

    @old_method('ValidateExpansion')
    def validate_expansion(self, expand, select):
        """A utility method for data providers.

        Checks the expand and select options, as described in
        :py:meth:`EntityCollection.set_expand` for validity raising
        ValueError if they violate the OData specification.

        Specifically the following are checked:

        1.  That "*" only ever appears as the last item in a select path

        2.  That nothing appears after a simple property in a select path

        3.  That all names are valid property names

        4.  That all expanded names are those of navigation properties"""
        if expand is None:
            expand = {}
        if select is None:
            select = {}
        for name, value in dict_items(select):
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
                            sub_expand = expand[name]
                        else:
                            sub_expand = None
                        p.to_end.entityType.validate_expansion(sub_expand,
                                                               value)
                    else:
                        raise KeyError
                except KeyError:
                    raise ValueError(
                        "%s is not a property of %s" % (name, self.name))
        for name, value in dict_items(expand):
            try:
                p = self[name]
                if isinstance(p, NavigationProperty):
                    # only navigation properties need apply
                    if name in select:
                        # then we've already been here
                        pass
                    else:
                        p.to_end.entityType.validate_expansion(value, None)
                else:
                    raise KeyError
            except KeyError:
                raise ValueError(
                    "%s is not a navigation property of %s" %
                    (name, self.name))

    def update_type_refs(self, scope, stop_on_errors=False):
        super(EntityType, self).update_type_refs(scope, stop_on_errors)
        for p in self.NavigationProperty:
            p.update_type_refs(scope, stop_on_errors)
        # at this point we loop through the navigation properties again
        # looking for duplicates.  These need to be marked on the entity
        # type as they can never be partnered and will require temporary
        # AssociationSets to be created in any container that binds the
        # type to an EntitySet
        aroles = {}
        # aroles maps AssociationEnds onto navigation properties
        for p in self.NavigationProperty:
            if p.from_end is not None:
                if p.from_end not in aroles:
                    aroles[p.from_end] = [p]
                else:
                    aroles[p.from_end].append(p)
        # now if there are any duplicates these are ambiguous references
        # and need to be marked as such
        for arole, plist in dict_items(aroles):
            if len(plist) > 1:
                # these are all duplicates!
                for p in plist:
                    logging.warning(
                        "Ambiguous navigation: %s.%s", self.name, p.name)
                    p.mark_as_ambiguous()
        self.Key.update_type_refs(scope, stop_on_errors)


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


@old_function('DecodeMultiplicity')
def multiplictiy_from_str(src):
    """Decodes a :py:class:`Multiplicity` value from a character string.

    The valid strings are "0..1", "1" and "*" """
    return MutliplicityMap.get(src.strip(), None)


@old_function('EncodeMultiplicity')
def multiplicity_to_str(value):
    """Encodes a :py:class:`Multiplicity` value as a character string."""
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
    def get_element_class(cls, name):
        if xmlns.match_expanded_names((EDM_NAMESPACE, 'End'), name,
                                      EDM_NAMESPACE_ALIASES):
            return AssociationEnd
        else:
            return None

    def content_changed(self):
        for ae in self.AssociationEnd:
            self.declare(ae)

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in self.AssociationEnd:
            yield child
        if self.ReferentialConstraint:
            yield self.ReferentialConstraint
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    @old_method('GetFQName')
    def get_fqname(self):
        """Returns the full name of this association

        The result includes the schema namespace prefix."""
        schema = self.find_parent(Schema)
        if schema is None:
            return self.name
        else:
            return ''.join((schema.name, '.', self.name))

    def update_type_refs(self, scope, stop_on_errors=False):
        for iEnd in self.AssociationEnd:
            iEnd.update_type_refs(scope, stop_on_errors)
        # now go through the navigation properties of the two entity
        # types searching for the properties that refer to this
        # association Once we find them, set the back-link
        np_list = []
        for iEnd in self.AssociationEnd:
            for np in iEnd.entityType.NavigationProperty:
                if scope[np.relationship] is self and not np.ambiguous:
                    np_list.append(np)
                    break
        if len(np_list) == 2:
            # Not always the case, the link may only be navigable one way
            np_list[0].backLink = np_list[1]
            np_list[1].backLink = np_list[0]


class AssociationEnd(CSDLElement):

    """Models one end of an :py:class:`Association`.

    We define a hash method to allow AssociationEnds to be used as keys
    in a dictionary."""
    # XMLNAME=(EDM_NAMESPACE,'End')

    XMLATTR_Role = 'name'
    XMLATTR_Type = 'type'
    XMLATTR_Multiplicity = (
        'multiplicity', multiplictiy_from_str, multiplicity_to_str)

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the role-name given to this end of the link
        self.name = None
        #: name of the entity type this end links to
        self.type = None
        #: :py:class:`EntityType` this end links to
        self.entityType = None
        #: a :py:class:`Multiplicity` constant
        self.multiplicity = 1
        #: the other :py:class:`AssociationEnd` of this link
        self.otherEnd = None
        # : the optional :py:class:`Documentation`
        self.Documentation = None
        self.OnDelete = None

    def get_qualified_name(self):
        """A utility function to return a qualified name.

        The qualified name comprises the name of the parent
        :py:class:`Association` and the role name."""
        if isinstance(self.parent, Association):
            return self.parent.name + "." + self.name
        else:
            return "." + self.name

    def __hash__(self):
        return hash(self.get_qualified_name())

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        if self.OnDelete:
            yield self.OnDelete
        for child in CSDLElement.get_children(self):
            yield child

    def update_type_refs(self, scope, stop_on_errors=False):
        try:
            self.entityType = self.otherEnd = None
            self.entityType = scope[self.type]
            if not isinstance(self.entityType, EntityType):
                raise "AssociationEnd not bound to EntityType (%s)" % self.type
            if not isinstance(self.parent, Association) or \
                    not len(self.parent.AssociationEnd) == 2:
                raise ModelIncomplete(
                    "AssociationEnd has missing or incomplete parent "
                    "(Role=%s)" % self.name)
            for iEnd in self.parent.AssociationEnd:
                if iEnd is self:
                    continue
                else:
                    self.otherEnd = iEnd
        except KeyError:
            self.entityType = self.otherEnd = None
            if stop_on_errors:
                raise


class EntityContainer(NameTableMixin, CSDLElement):

    """Models an entity container in the metadata model.

    An EntityContainer inherits from :py:class:`NameTableMixin` to
    enable it to behave like a scope.  The :py:class:`EntitySet`
    instances and :py:class:`AssociationSet` instances it contains are
    declared within the scope."""
    XMLNAME = (EDM_NAMESPACE, 'EntityContainer')
    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Extends = 'extends'
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        #: the declared name of the container
        self.name = "Default"
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        self.FunctionImport = []
        #: a list of :py:class:`EntitySet` instances
        self.EntitySet = []
        #: a list of :py:class:`AssociationSet` instances
        self.AssociationSet = []
        #: a list of auto-generated :py:class:`AssociationSet` instances
        self._AssociationSet = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.EntitySet,
                self.AssociationSet,
                self.FunctionImport,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def content_changed(self):
        for t in self.EntitySet + self.AssociationSet + self.FunctionImport:
            self.declare(t)

    def find_entitysets(self, entity_type):
        """Returns a list of all entity sets with a given type

        entity_type
            An :py:class:`EntityType` instance.

        Returns an empty list if no declared EntitySets have
        this type."""
        result = []
        for child in self.EntitySet:
            if child.entityType is entity_type:
                result.append(child)
        return result

    def add_auto_aset(self, association_set):
        self._AssociationSet.append(association_set)
        scope = self.find_parent(Schema)
        if scope:
            scope = scope.parent
        if scope:
            association_set.update_set_refs(scope, True)

    def update_set_refs(self, scope, stop_on_errors=False):
        for child in itertools.chain(self.EntitySet, self.AssociationSet,
                                     self.FunctionImport):
            child.update_set_refs(scope, stop_on_errors)
        for child in self.EntitySet:
            child.update_navigation()

    def validate(self):
        for child in self.FunctionImport:
            child.validate()


class EntitySet(CSDLElement):

    """Represents an EntitySet in the metadata model."""
    XMLNAME = (EDM_NAMESPACE, 'EntitySet')
    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_EntityType = 'entityTypeName'
    XMLCONTENT = xml.ElementType.ElementContent

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
        #: a list of the names of this entity set's keys in their
        #: declared order
        self.keys = []
        #: a mapping from navigation property names to
        #: :py:class:`AssociationSetEnd` instances
        self.navigation = {}
        self.linkEnds = {}
        """A mapping from :py:class:`AssociationSetEnd` instances that
        reference this entity set to navigation property names (or None
        if this end of the association is not bound to a named
        navigation property)"""
        self.bad_principal = False
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
        Customer to Order.  For the Order entity, the Customer is the
        principal as Orders can only be exist when they are associated
        with a Customer.

        Attempting to create an Order in the base collection of Orders
        will always fail::

            with Orders.open() as collection:
                order=collection.new_entity()
                # set order fields here
                collection.insert_entity(order)
                # raises ConstraintError as order is not bound to a customer

        Instead, you have to create new orders from a Customer entity::

            with Customers.open() as collectionCustomers:
                # get the existing customer
                customer=collectionCustomers['ALFKI']
                with customer['Orders'].open() as collectionOrders:
                    # create a new order
                    order=collectionOrders.new_entity()
                    # ... set order details here
                    collectionOrders.insert_entity(order)

        You can also use a deep insert::

            with Customers.open() as collectionCustomers,
                    Orders.open() as collectionOrders:
                customer=collectionCustomers.new_entity()
                # set customer details here
                order=collectionOrders.new_entity()
                # set order details here
                customer['Orders'].bind_entity(order)
                collectionCustomers.insert_entity(customer)

        For the avoidance of doubt, an entity set can't have two unbound
        principals because if it did you would never be able to create
        entities in it!"""
        self.binding = (EntityCollection, {})
        self.navigation_bindings = {}
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []
        self.location = None

    @old_method('GetFQName')
    def get_fqname(self):
        """Returns the fully qualified name of this entity set."""
        name = []
        if isinstance(self.parent, EntityContainer):
            if isinstance(self.parent.parent, Schema):
                name.append(self.parent.parent.name)
            name.append(self.parent.name)
        name.append(self.name)
        return '.'.join(name)

    @old_method('GetLocation')
    def get_location(self):
        """Returns a :py:class:`pyslet.rfc2396.URI` instance
        representing the location for this entity set."""
        return self.location

    @old_method('SetLocation')
    def set_location(self):
        """Sets the location of this entity set

        Resolves a relative path consisting of::

            [ EntityContainer.name '.' ] name

        The resolution of URIs is done in accordance with the XML
        specification, so is affected by any xml:base attributes set on
        parent elements or by the original base URI used to load the
        metadata model.  If no base URI can be found then the location
        remains expressed in relative terms."""
        container = self.find_parent(EntityContainer)
        if container:
            path = container.name + '.' + self.name
        else:
            path = self.name
        self.location = self.resolve_uri(path)

    def content_changed(self):
        super(EntitySet, self).content_changed()
        self.set_location()

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def update_set_refs(self, scope, stop_on_errors=False):
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
            if stop_on_errors:
                raise

    def set_unbound_principal(self, aset_end):
        logging.warning("Entity set %s has an unbound principal: %s",
                        self.name, aset_end.otherEnd.entity_set.name)
        if not self.bad_principal and self.unboundPrincipal is None:
            self.unboundPrincipal = aset_end
        else:
            # so the model is dumb, we have two unbound principals
            if self.unboundPrincipal:
                self.bad_principal = True
                from_end = self.unboundPrincipal
                self.unboundPrincipal = None
                from_end.drop_principal()
            aset_end.drop_principal()

    def update_navigation(self):
        container = self.find_parent(EntityContainer)
        if container and self.entityType:
            # first loop deals with ambiguous navigation properties
            for np in self.entityType.NavigationProperty:
                if not np.ambiguous:
                    continue
                # find the target set and make sure it is unique
                if np.from_end and np.to_end and np.to_end.entityType:
                    esets = container.find_entitysets(np.to_end.entityType)
                    if len(esets) > 1:
                        # can't be done!
                        raise ModelConstraintError(
                            "Property %s.%s has an ambiguous target set" %
                            (self.name, np.name))
                    # eset = esets[0]
                else:
                    continue
                # create a unique name
                stem = "%s_%s" % (self.name, np.name)
                as_name = stem
                i = 0
                while as_name in container:
                    i += 1
                    as_name = "%s_%i" % (stem, i)
                # auto-generate an AssociationSet
                association_set = AssociationSet(container)
                association_set.name = as_name
                association_set.associationName = \
                    np.to_end.parent.get_fqname()
                from_end = association_set.add_child(AssociationSetEnd)
                from_end.name = np.from_end.name
                from_end.entitySetName = self.name
                to_end = association_set.add_child(AssociationSetEnd)
                to_end.name = np.to_end.name
                to_end.entitySetName = np.to_end.entityType.name
                # add the auto-generated set to the container
                # automatically updates set references
                container.add_auto_aset(association_set)
                self.navigation[np.name] = from_end
                self.linkEnds[from_end] = np.name
                # if our end is required then we are the unbound
                # principal of the other entity set
                if from_end.associationEnd.multiplicity == Multiplicity.One:
                    to_end.entity_set.set_unbound_principal(to_end)
            for association_set in container.AssociationSet:
                for iEnd in association_set.AssociationSetEnd:
                    if iEnd.entity_set is self:
                        # there is no requirement that says every
                        # AssociationSetEnd must be represented by a
                        # corresponding navigation property.
                        nav_name = None
                        for np in self.entityType.NavigationProperty:
                            if np.ambiguous:
                                # ignore ambiguous navigation properties
                                continue
                            if iEnd.associationEnd is np.from_end:
                                nav_name = np.name
                                break
                        if nav_name:
                            self.navigation[nav_name] = iEnd
                        elif iEnd.otherEnd.associationEnd.multiplicity == \
                                Multiplicity.One:
                            self.set_unbound_principal(iEnd)
                        self.linkEnds[iEnd] = nav_name
            for np in self.entityType.NavigationProperty:
                if np.name not in self.navigation:
                    raise ModelIncomplete(
                        "Navigation property %s in EntitySet %s is not bound "
                        "to an association set" % (np.name, self.name))

    @old_method('KeyKeys')
    def key_keys(self):
        warnings.warn(
            "EntitySet.key_keys is deprecated, use keys attribute instead",
            DeprecationWarning,
            stacklevel=2)
        return self.keys

    @old_method('GetKey')
    def get_key(self, keylike):
        """Extracts a key from a *keylike* argument

        keylike
            A value suitable for using as a key in an
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
        if isinstance(keylike, tuple):
            if len(self.entityType.Key.PropertyRef) == 1:
                if len(keylike) == 1:
                    return keylike[0]
                else:
                    raise KeyError(
                        "Unexpected compound key: %s" % repr(keylike))
            else:
                return keylike
        elif isinstance(keylike, (dict, Entity)):
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

    def extract_key(self, keyvalue):
        """Extracts a key value from *keylike*.

        Unlike get_key, this method attempts to convert the data in
        *keyvalue* into the correct format for the key.  For compound
        keys *keyvalue* must be a suitable list or tuple or compatible
        iterable supporting the len method.  Dictionaries are not
        supported.

        If keyvalue cannot be converted into a suitable representation
        of the key then None is returned."""
        klen = len(self.entityType.Key.PropertyRef)
        if klen == 1:
            kv = self.entityType[self.keys[0]]()
            try:
                if is_text(keyvalue):
                    kv.set_from_literal(keyvalue)
                else:
                    kv.set_from_value(keyvalue)
            except (TypeError, ValueError):
                return None
            return kv.value
        elif klen == len(keyvalue):
            i = 0
            result = []
            for kvi in keyvalue:
                kv = self.entityType[self.keys[i]]()
                try:
                    if is_text(kvi):
                        kv.set_from_literal(kvi)
                    else:
                        kv.set_from_value(kvi)
                except (TypeError, ValueError):
                    return None
                result.append(kv.value)
            return tuple(result)

    def key_dict(self, key):
        """Given a key from this entity set, returns a key dictionary.

        The result is a mapping from named properties to
        :class:`SimpleValue` instances.  The property name is always used
        as the key in the mapping, even if the key refers to a single
        property.  This contrasts with :meth:`get_key_dict`."""
        key_dict = {}
        if not isinstance(key, tuple):
            key = (key,)
        ki = iter(key)
        for kp in self.entityType.Key.PropertyRef:
            k = next(ki)
            #   create a new simple value to hold k
            kv = kp.property()
            kv.set_from_value(k)
            key_dict[kp.property.name] = kv
        return key_dict

    @old_method('GetKeyDict')
    def get_key_dict(self, key):
        """Given a key from this entity set, returns a key dictionary.

        The result is a mapping from named properties to
        :py:class:`SimpleValue` instances.  As a special case, if a
        single property defines the entity key it is represented using
        the empty string, *not* the property name."""
        key_dict = {}
        if not isinstance(key, tuple):
            no_name = True
            key = (key,)
        else:
            no_name = False
        ki = iter(key)
        for kp in self.entityType.Key.PropertyRef:
            k = next(ki)
            #   create a new simple value to hold k
            kv = kp.property()
            kv.set_from_value(k)
            if no_name:
                key_dict[''] = kv
            else:
                key_dict[kp.property.name] = kv
        return key_dict

    def bind(self, binding, **kws):
        """Binds this entity set to a collection class

        binding
            Must be a class (or other callable) that returns an
            :py:class:`EntityCollection` instance, by default we are
            bound to the default EntityCollection class which behaves
            like an empty collection.

        kws
            A python dict of named arguments to pass to the binding
            callable"""
        self.binding = binding, kws

    @old_method('OpenCollection')
    def open(self):
        """Opens this entity set

        Returns an :py:class:`EntityCollection` instance suitable for
        accessing the entities themselves."""
        cls, kws = self.binding
        return cls(entity_set=self, **kws)

    @old_method('BindNavigation')
    def bind_navigation(self, name, binding, **kws):
        """Binds the navigation property *name*.

        binding
            Must be a class (or other callable) that returns a
            :py:class:`NavigationCollection` instance. By default we are
            bound to the default NavigationCollection class which
            behaves like an empty collection.

        kws
            A python dict of named arguments to pass to the binding
            callable"""
        self.navigation_bindings[name] = (binding, kws)

    @old_method('OpenNavigation')
    def open_navigation(self, name, source_entity):
        """Opens a navigation collection

        Returns a :py:class:`NavigationCollection` instance suitable for
        accessing the entities obtained by navigating from
        *source_entity*, an :py:class:`Entity` instance, via the
        navigation property with *name*."""
        cls, kws = self.navigation_bindings[name]
        link_end = self.navigation[name]
        to_entity_set = link_end.otherEnd.entity_set
        return cls(
            from_entity=source_entity,
            name=name,
            entity_set=to_entity_set,
            **kws)

    @old_method('NavigationTarget')
    def get_target(self, name):
        """Returns the target entity set of navigation property *name*"""
        link_end = self.navigation[name]
        return link_end.otherEnd.entity_set

    @old_method('NavigationMultiplicity')
    def get_multiplicity(self, name):
        """Gets the multiplicities of a named navigation properly

        Returns the :py:class:`Multiplicity` of both the source and the
        target of the named navigation property, as a tuple, for
        example, if *customers* is an entity set from the sample OData
        service::

            customers.get_multiplicity['Orders'] == \
                (Multiplicity.ZeroToOne, Multiplicity.Many)"""
        link_end = self.navigation[name]
        return link_end.associationEnd.multiplicity, \
            link_end.otherEnd.associationEnd.multiplicity

    @old_method('IsEntityCollection')
    def is_entity_collection(self, name):
        """Tests the multiplicity of a named navigation property

        Returns True if more than one entity is possible when navigating
        the named property."""
        return self.get_multiplicity(name)[1] == Multiplicity.Many


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
    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Association = 'associationName'
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the declared name of this association set
        self.name = "Default"
        #: the name of the association definition
        self.associationName = ""
        #: the :py:class:`Association` definition
        self.association = None
        #: the optional :py:class:`Documentation`
        self.Documentation = None
        # : a list of :py:class:`AssociationSetEnd` instances
        self.AssociationSetEnd = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    @classmethod
    def get_element_class(cls, name):
        if xmlns.match_expanded_names((EDM_NAMESPACE, 'End'),
                                      name, EDM_NAMESPACE_ALIASES):
            return AssociationSetEnd
        else:
            return None

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.AssociationSetEnd,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def update_set_refs(self, scope, stop_on_errors=False):
        try:
            self.association = scope[self.associationName]
            if not isinstance(self.association, Association):
                raise KeyError("%s is not an Association" %
                               self.associationName)
            for iEnd in self.AssociationSetEnd:
                iEnd.update_set_refs(scope, stop_on_errors)
        except KeyError:
            self.association = None
            if stop_on_errors:
                raise


class AssociationSetEnd(SortableMixin, CSDLElement):

    """Represents the links between two entity sets

    The :py:meth:`get_qualified_name` method defines the identity of
    this element.  The built-in Python hash function returns a hash
    based on this value and the associated comparison functions are also
    implemented enabling these elements to be added to ordinary Python
    dictionaries.

    Oddly, role names are sometimes treated as optional but it can make
    it a challenge to work out which end of the association is which
    when we are actually using the model if one or both are missing. The
    algorithm we use is to use role names if either are given, otherwise
    we match the entity types.  If these are also identical then the
    choice is arbitrary.  To prevent confusion missing role names are
    filled in when the metadata model is loaded."""
    # XMLNAME=(EDM_NAMESPACE,'End')
    XMLATTR_Role = 'name'
    XMLATTR_EntitySet = 'entitySetName'
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the role-name given to this end of the link
        self.name = None
        #: name of the entity set this end links to
        self.entitySetName = None
        #: :py:class:`EntitySet` this end links to
        self.entity_set = None
        #: :py:class:`AssociationEnd` that defines this end of the link
        self.associationEnd = None
        #: the other :py:class:`AssociationSetEnd` of this link
        self.otherEnd = None
        #: the optional :py:class:`Documentation`
        self.Documentation = None

    @old_method('GetQualifiedName')
    def get_qualified_name(self):
        """A utility function to return a qualified name.

        The qualified name comprises the name of the parent
        :py:class:`AssociationSet` and the role name."""
        if isinstance(self.parent, AssociationSet):
            return self.parent.name + "." + self.name
        else:
            return "." + self.name

    def sortkey(self):
        return self.get_qualified_name()

    def __hash__(self):
        return hash(self.sortkey())

#     def __eq__(self, other):
#         if isinstance(other, AssociationSetEnd):
#             return cmp(self.get_qualified_name(),
#                        other.get_qualified_name()) == 0
#         else:
#             return False
#
#     def __ne__(self, other):
#         return not self.__eq__(other)
#
#     def __cmp__(self, other):
#         if isinstance(other, AssociationSetEnd):
#             return cmp(self.get_qualified_name(), other.get_qualified_name())
#         else:
#             raise TypeError

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in CSDLElement.get_children(self):
            yield child

    def drop_principal(self):
        if self.associationEnd.multiplicity == Multiplicity.ZeroToOne:
            logging.error(
                "Entity set %s has more than one unbound principal "
                "changing multiplicity from 0..1 to * and "
                "dropping multiplicity of %s to 0..1.  Continuing...",
                self.entity_set.name, self.otherEnd.name)
            self.associationEnd.multiplicity = Multiplicity.Many
            self.otherEnd.associationEnd.multiplicity = Multiplicity.ZeroToOne
#             raise ModelConstraintError(
#                 "Entity set %s has more than one unbound principal" %
#                 self.entity_set.name)
        else:
            logging.error(
                "Entity set %s has more than one unbound principal\n"
                "dropping multiplicity of %s to 0..1.  Continuing",
                self.entity_set.name, self.otherEnd.name)
            self.otherEnd.associationEnd.multiplicity = Multiplicity.ZeroToOne

    def update_set_refs(self, scope, stop_on_errors=False):
        try:
            self.entity_set = self.otherEnd = self.associationEnd = None
            container = self.find_parent(EntityContainer)
            if container:
                self.entity_set = container[self.entitySetName]
            if not isinstance(self.entity_set, EntitySet):
                raise ModelIncomplete(
                    "AssociationSetEnd not bound to EntitySet (%s)" %
                    self.entitySetName)
            if not isinstance(self.parent, AssociationSet) or \
                    not len(self.parent.AssociationSetEnd) == 2:
                raise ModelIncomplete(
                    "AssociationSetEnd has missing or incomplete "
                    "parent (Role=%s)" % self.name)
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
                    "Failed to match AssociationSetEnds to their "
                    "definitions: %s" % self.parent.name)
        except KeyError:
            self.entity_set = self.otherEnd = self.associationEnd = None
            if stop_on_errors:
                raise


class FunctionImport(NameTableMixin, CSDLElement):

    """Represents a FunctionImport in an entity collection."""
    XMLNAME = (EDM_NAMESPACE, 'FunctionImport')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_ReturnType = 'returnType'
    XMLATTR_EntitySet = 'entitySetName'

    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        #: the declared name of this function import
        self.name = "Default"
        #: the return type of the function
        self.returnType = ""
        #: reference to the return type definition
        self.returnTypeRef = None
        #: the name of the entity set from which the return values are
        #: taken
        self.entitySetName = ''
        #: the :py:class:`EntitySet` corresponding to
        #: :py:attr:`entitySetName`
        self.entity_set = None
        #: a callable to use when executing this function (see
        #: :py:meth:`bind`)
        self.binding = None, {}
        self.Documentation = None
        self.ReturnType = []
        self.Parameter = []
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.ReturnType,
                self.Parameter,
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def content_changed(self):
        super(FunctionImport, self).content_changed()
        for p in self.Parameter:
            self.declare(p)

    def update_set_refs(self, scope, stop_on_errors=False):
        """Sets :py:attr:`entity_set` if applicable"""
        try:
            self.entity_set = None
            self.returnTypeRef = TypeRef(self.returnType, scope)
            if self.entitySetName:
                container = self.find_parent(EntityContainer)
                if container:
                    self.entity_set = container[self.entitySetName]
                if not isinstance(self.entity_set, EntitySet):
                    raise KeyError("%s is not an EntitySet" %
                                   self.entitySetName)
#             else:
#                 if isinstance(self.returnTypeRef.type_def, EntityType) and \
#                         self.returnTypeRef.collection:
#                     raise KeyError(
#                         "Return type %s requires an EntitySet" %
#                         self.returnType)
            for p in self.Parameter:
                p.update_set_refs(scope, stop_on_errors)
        except KeyError:
            self.returnTypeRef = self.entity_set = None
            if stop_on_errors:
                raise

    def validate(self):
        """Validates this FunctionImport"""
        # If the return type of FunctionImport is a collection of
        # entities, the EntitySet attribute MUST be defined
        if (self.returnTypeRef.collection and
                isinstance(self.returnTypeRef.type_def, EntityType) and
                self.entity_set is None):
            raise ModelIncomplete(
                "FunctionImport %s must be bound to an entity set" %
                self.name)
        # If the return type of FunctionImport is of ComplexType or
        # scalar type, the EntitySet attribute MUST NOT be defined
        if ((self.returnTypeRef.simpleTypeCode is not None or
             isinstance(self.returnTypeRef.type_def, ComplexType)) and
                self.entity_set is not None):
            raise InvalidMetadataDocument(
                "FunctionImport %s must not be bound to an entity set" %
                self.name)
        # Parameter element names inside a FunctionImport MUST NOT
        # collide - checked during the initial parse

    @old_method('IsCollection')
    def is_collection(self):
        """Returns True if the return type is a collection."""
        return self.returnTypeRef.collection

    @old_method('IsEntityCollection')
    def is_entity_collection(self):
        """Returns True if the return type is a collection of entities."""
        return self.entity_set is not None and self.returnTypeRef.collection

    def bind(self, callable, **kws):
        """Binds this instance to a callable.

        The callable must have the following signature and the
        appropriate return type as per the
        :py:meth:`execute` method:

        callable(:py:class:`FunctionImport` instance, params dictionary, **kws)

        A derived class of :py:class:`FunctionEntityCollection` can be
        used directly."""
        self.binding = callable, kws

    @old_method('Execute')
    def execute(self, params):
        """Executes this function (with optional params)

        Returns one of the following, depending on the type of function:

        *   An instance of :py:class:`EDMValue`

        *   An instance of :py:class:`Entity`

        *   An instance of :py:class:`FunctionCollection`

        *   An instance of :py:class:`FunctionEntityCollection`  """
        f, kws = self.binding
        if f is not None:
            return f(self, params, **kws)
        else:
            raise NotImplementedError("Unbound FunctionImport: %s" % self.name)


class ParameterMode(xsi.EnumerationNoCase):

    """Defines constants for the parameter modes defined by CSDL
    ::

        ParameterMode.In
        ParameterMode.DEFAULT == None

    For more methods see
    :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'In': 1,
        'Out': 2,
        'InOut': 3
    }


class Parameter(CSDLElement):

    """Represents a Parameter in a function import."""
    XMLNAME = (EDM_NAMESPACE, 'Parameter')

    XMLATTR_Name = ('name', validate_simple_identifier, None)
    XMLATTR_Type = 'type'
    XMLATTR_Mode = (
        'mode', ParameterMode.from_str, ParameterMode.to_str)
    XMLATTR_MaxLength = ('maxLength', maxlength_from_str, maxlength_to_str)
    XMLATTR_Precision = 'precision'
    XMLATTR_Scale = 'scale'
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        #: the declared name of this parameter
        self.name = "Default"
        #: the type of the parameter, a scalar type, ComplexType or
        #: EntityType (or a Collection)
        self.type = ""
        #: reference to the type definition
        self.typeRef = None
        #: one of the :py:class:`ParameterMode` constants
        self.mode = None
        #: the maxLength facet of the parameter
        self.maxLength = None
        #: the precision facet of the parameter
        self.precision = None
        #: the scale facet of the parameter
        self.scale = None
        self.Documentation = None
        self.TypeAnnotation = []
        self.ValueAnnotation = []

    def get_children(self):
        if self.Documentation:
            yield self.Documentation
        for child in itertools.chain(
                self.TypeAnnotation,
                self.ValueAnnotation,
                CSDLElement.get_children(self)):
            yield child

    def update_set_refs(self, scope, stop_on_errors=False):
        """Sets type information for the parameter"""
        try:
            self.typeRef = TypeRef(self.type, scope)
        except KeyError:
            self.typeRef = None
            if stop_on_errors:
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
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        CSDLElement.__init__(self, parent)
        NameTableMixin.__init__(self)
        #: the declared name of this schema
        self.name = "Default"
        self.alias = None
        self.Documentation = None
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

    def get_children(self):
        return itertools.chain(
            self.EntityType,
            self.ComplexType,
            self.Association,
            self.Function,
            self.EntityContainer,
            self.Using,
            self.Annotations,
            self.ValueTerm,
            CSDLElement.get_children(self))

    def content_changed(self):
        for t in itertools.chain(
                self.EntityType, self.ComplexType, self.Association,
                self.Function, self.EntityContainer):
            self.declare(t)

    def update_type_refs(self, scope, stop_on_errors=False):
        # it is important that we process EntityType before Association!
        for t in itertools.chain(self.EntityType, self.ComplexType,
                                 self.Association, self.Function):
            t.update_type_refs(scope, stop_on_errors)

    def update_set_refs(self, scope, stop_on_errors=False):
        for t in self.EntityContainer:
            t.update_set_refs(scope, stop_on_errors)

    def validate(self):
        for child in self.EntityContainer:
            child.validate()


class Document(xmlns.XMLNSDocument):

    """Represents an EDM document."""

    class_map = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        self.defaultNS = EDM_NAMESPACE
        self.make_prefix(EDM_NAMESPACE, 'edm')

    @classmethod
    def get_element_class(cls, name):
        """Looks up the name in :attr:`class_map`"""
        eclass = Document.class_map.get(
            name, Document.class_map.get((name[0], None), xmlns.XMLNSElement))
        return eclass

xmlns.map_class_elements(Document.class_map, globals(), NAMESPACE_ALIASES)
