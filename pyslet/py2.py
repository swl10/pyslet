#! /usr/bin/env python
"""Experimental module for Python 2 compatibility.

The purpose of this module is to enable Pyslet to be gradually converted
to Python3 while retaining support for Python 2.7 and 2.6.  This fills a
similar role to the six module but the idea is to minimise the number of
required fixes by making the Pyslet code as Python3 native as
possible."""

import io
import sys
import types

py2 = sys.hexversion < 0x03000000
"""Unfortunately, sometimes you just need to know if you are running
under Python 2, this flag provides a common way for version specific
code to check.  (There are multiple ways of checking, this flag just
makes it easier to find places in Pyslet where we care.)"""


_sys_codec = sys.getdefaultencoding()


if py2:
    suffix = ''

    def u8(arg):
        if isinstance(arg, types.UnicodeType):
            try:
                arg.encode('ascii')
            except UnicodeEncodeError:
                raise ValueError("u8: use binary literal for non-ASCII data")
            return arg
        try:
            return arg.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError("u8: invalid utf-8 string, did you mean ul?")

    def ul(arg):
        if isinstance(arg, types.UnicodeType):
            try:
                arg.encode('latin-1')
            except UnicodeEncodeError:
                raise ValueError("ul: cannot be used with non-latin data")
            return arg
        return arg.decode('latin-1')

    def is_string(arg):
        return isinstance(arg, types.StringTypes)

    is_text = is_string

    def force_text(arg):
        if isinstance(arg, str):
            return unicode(arg)
        elif isinstance(arg, unicode):
            return arg
        else:
            raise TypeError("Expected str or unicode: %s" % repr(arg))

    def is_ascii(arg):
        return isinstance(arg, str)

    def force_ascii(arg):
        if isinstance(arg, unicode):
            return arg.encode('ascii')
        elif isinstance(arg, str):
            return arg
        else:
            raise TypeError("Expected str or unicode: %s" % repr(arg))

    to_text = unicode

    def is_unicode(arg):
        return isinstance(arg, unicode)

    def character(arg):
        if isinstance(arg, str):
            if len(arg) == 1:
                return unichr(ord(arg[0]))
            else:
                raise ValueError('Expected single character')
        else:
            return unichr(arg)

    join_characters = unicode('').join

    uempty = unicode('')

    uspace = unicode(' ')

    def force_bytes(arg):
        if isinstance(arg, unicode):
            return arg.encode('ascii')
        return arg

    to_bytes = str

    def is_byte(arg):
        return isinstance(arg, bytes) and len(arg) == 1

    def byte(arg):
        if isinstance(arg, str):
            if len(arg) == 1:
                return arg
            else:
                raise ValueError('Expected single character')
        elif isinstance(arg, types.UnicodeType):
            if len(arg) == 1:
                arg = ord(arg)
                # fall through to int tests
            else:
                raise ValueError('Expected single character')
        elif isinstance(arg, bytearray):
            if len(arg) == 1:
                return chr(arg[0])
            else:
                raise ValueError('Expected single byte')
        if isinstance(arg, (int, long)):
            if arg >= 0 and arg <= 255:
                return chr(arg)
            else:
                raise ValueError("Value out of range 0..255")
        else:
            raise TypeError('Expectected character or int')

    byte_value = ord

    join_bytes = b''.join

    def byte_to_bstr(arg):
        return arg

    buffer2 = types.BufferType

    long2 = long

    range3 = xrange

    def dict_keys(d):
        return d.iterkeys()

    def dict_values(d):
        return d.itervalues()

    def dict_items(d):
        return d.iteritems()

    import __builtin__ as builtins

    input3 = raw_input

    from urllib import (            # noqa : unused import
        urlencode,
        urlopen,
        quote as urlquote
        )
    from urlparse import parse_qs   # noqa : unused import

else:
    suffix = '3'

    def u8(arg):
        if isinstance(arg, bytes):
            return arg.decode('utf-8')
        elif isinstance(arg, str):
            # only works for ascii
            try:
                arg.encode('ascii')
            except UnicodeEncodeError:
                raise ValueError("u8: use binary literal for non-ASCII data")
            return arg
        else:
            raise TypeError

    def ul(arg):
        if isinstance(arg, bytes):
            return arg.decode('latin-1')
        elif isinstance(arg, str):
            try:
                arg.encode('latin-1')
            except UnicodeEncodeError:
                raise ValueError("ul: cannot be used with non-latin data")
            return arg
        else:
            raise TypeError

    def is_string(arg):
        return isinstance(arg, (str, bytes))

    def is_text(arg):
        return isinstance(arg, str)

    def force_text(arg):
        if not isinstance(arg, str):
            raise TypeError("Expected str: %s" % repr(arg))
        return arg

    def is_ascii(arg):
        if isinstance(arg, str):
            arg.encode('ascii')
            return True
        else:
            return False

    def force_ascii(arg):
        if isinstance(arg, bytes):
            return arg.decode('ascii')
        elif isinstance(arg, str):
            return arg
        else:
            raise TypeError("Expected str: %s" % repr(arg))

    def to_text(arg):
        if isinstance(arg, str):
            return arg
        elif isinstance(arg, bytes):
            return arg.decode('ascii')
        else:
            return str(arg)

    def is_unicode(arg):
        return isinstance(arg, str)

    character = chr

    join_characters = ''.join

    uempty = ''

    uspace = ' '

    def force_bytes(arg):
        if isinstance(arg, str):
            return arg.encode('ascii')
        return arg

    def to_bytes(arg):
        if hasattr(arg, '__bytes__'):
            return arg.__bytes__()
        else:
            return str(arg).encode('ascii')

    def is_byte(arg):
        return isinstance(arg, int) and 0 <= arg <= 255

    def byte(arg):
        if isinstance(arg, str):
            if len(arg) == 1:
                arg = ord(arg)
            else:
                raise ValueError('Expected single character')
        elif isinstance(arg, (bytes, bytearray)):
            if len(arg) == 1:
                arg = arg[0]
            else:
                raise ValueError('Expected single byte')
        if isinstance(arg, int):
            if arg >= 0 and arg <= 255:
                return arg
            else:
                raise ValueError("Value out of range 0..255")
        else:
            raise TypeError('Expectected character or int')

    byte_value = int

    join_bytes = bytes

    def byte_to_bstr(arg):
        return bytes([arg])

    buffer2 = bytes

    long2 = int

    range3 = range

    def dict_keys(d):
        return d.keys()

    def dict_values(d):
        return d.values()

    def dict_items(d):
        return d.items()

    import builtins     # noqa : unused import

    input3 = input

    from urllib.request import urlopen      # noqa : unused import
    from urllib.parse import (              # noqa : unused import
        parse_qs,
        quote as urlquote,
        urlencode
        )


class UnicodeMixin(object):

    """Mixin class to handle string formatting

    For classes that need to define a __unicode__ method of their own
    this class is used to ensure that the correct behaviour exists
    in Python versions 2 and 3.

    The mixin class implements __str__ based on your existing (required)
    __unicode__ or (optional) __bytes__ implementation.  In python 2,
    the output of __unicode__ is encoded using the default system
    encoding if no __bytes__ implementation is provided.  This may well
    generate errors but that seems more appropriate as it will catch
    cases where the *str* function has been used instead of
    :py:func:`to_text`."""

    if py2:
        def __str__(self):      # noqa
            if hasattr(self, '__bytes__'):
                return self.__bytes__()
            else:
                return self.__unicode__().encode(_sys_codec)
    else:
        def __str__(self):      # noqa
            return self.__unicode__()


class SortableMixin(object):

    """Mixin class for handling comparisons

    Utility class for helping provide comparisons that are compatible
    with Python 2 and Python 3.  Classes must define a method
    :meth:`sortkey` which returns a sortable key value representing the
    instance.

    Derived classes may optionally override the classmethod :meth:`otherkey`
    to provide an ordering against other object types.

    This mixin then adds implementations for all of the comparison
    methods: __eq__, __ne__, __lt__, __le__, __gt__, __ge__."""

    def sortkey(self):
        """Returns a value to use as a key for sorting.

        By default returns NotImplemented.  This value causes the
        comparison functions to also return NotImplemented."""
        return NotImplemented

    def otherkey(self, other):
        """Returns a value to use as a key for sorting

        The difference between this method and :meth:`sortkey` is that
        this method takes an arbitrary object and either returns the key
        to use when comparing with this instance or NotImplemented if
        the sorting is not supported.

        You don't have to override this implementation, by default it
        returns other.sortkey() if *other* is an instance of the same
        class as *self*, otherwise it returns NotImplemented."""
        if isinstance(other, self.__class__):
            return other.sortkey()
        else:
            return NotImplemented

    def __eq__(self, other):
        a = self.sortkey()
        b = self.otherkey(other)
        if NotImplemented in (a, b):
            return NotImplemented
        else:
            return a == b

    def __ne__(self, other):
        a = self.sortkey()
        b = self.otherkey(other)
        if NotImplemented in (a, b):
            return NotImplemented
        else:
            return a != b

    def __lt__(self, other):
        a = self.sortkey()
        b = self.otherkey(other)
        if NotImplemented in (a, b):
            if py2:
                raise TypeError("unorderable types: %s < %s" %
                                (repr(self), repr(other)))
            return NotImplemented
        else:
            return a < b

    def __le__(self, other):
        a = self.sortkey()
        b = self.otherkey(other)
        if NotImplemented in (a, b):
            if py2:
                raise TypeError("unorderable types: %s <= %s" %
                                (repr(self), repr(other)))
            return NotImplemented
        else:
            return a <= b

    def __gt__(self, other):
        a = self.sortkey()
        b = self.otherkey(other)
        if NotImplemented in (a, b):
            if py2:
                raise TypeError("unorderable types: %s > %s" %
                                (repr(self), repr(other)))
            return NotImplemented
        else:
            return a > b

    def __ge__(self, other):
        a = self.sortkey()
        b = self.otherkey(other)
        if NotImplemented in (a, b):
            if py2:
                raise TypeError("unorderable types: %s >= %s" %
                                (repr(self), repr(other)))
            return NotImplemented
        else:
            return a >= b


class CmpMixin(object):

    """Mixin class for handling comparisons

    For compatibility with Python 2's __cmp__ method this class defines
    an implementation of __eq__, __lt__, __le__, __gt__, __ge__ that are
    redirected to __cmp__.  These are the minimum methods required for
    Python's rich comparisons.

    In Python 2 it also provides an implementation of __ne__ that simply
    inverts the result of __eq__.  (This is not required in Python 3.)"""

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __ge__(self, other):
        return self.__cmp__(other) >= 0

    if py2:
        def __ne__(self, other):    # noqa
            return not self.__eq__(other)


class BoolMixin(object):

    """Mixin class for handling legacy __nonzero__

    For compatibility with Python 2 this class defines __nonzero__
    returning the value of the method __bool__."""

    def __nonzero__(self):
        return self.__bool__()


def output(txt):

    """Simple function for writing to stdout

    Not as sophisticated as Python 3's print function but designed to be
    more of a companion to the built in input."""
    if isinstance(sys.stdout, io.TextIOBase):
        sys.stdout.write(txt)
    else:
        sys.stdout.write(txt.encode('utf-8'))
