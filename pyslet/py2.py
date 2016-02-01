#! /usr/bin/env python
"""Experimental module for Python 2 compatibility.

The purpose of this module is to enable Pyslet to be gradually converted
to Python3 while retaining support for Python 2.7 and 2.6.  This fills a
similar role to the six module but the idea is to minimise the number of
required fixes by making the Pyslet code as Python3 native as
possible."""

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

    empty_text = unicode("")

    def is_text(arg):
        return isinstance(arg, types.StringTypes)

    def force_text(arg):
        if isinstance(arg, str):
            return unicode(arg)
        elif isinstance(arg, unicode):
            return arg
        else:
            raise TypeError("Expected str: %s" % repr(arg))

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

    def force_bytes(arg):
        if isinstance(arg, unicode):
            return arg.encode('ascii')
        return arg

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

    range3 = xrange

    def dict_keys(d):
        return d.iterkeys()

    def dict_values(d):
        return d.itervalues()

    import __builtin__ as builtins

    from urllib import urlopen

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

    empty_text = ""

    def is_text(arg):
        return isinstance(arg, str)

    def force_text(arg):
        if not isinstance(arg, str):
            raise TypeError("Expected str: %s" % repr(arg))
        return arg

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

    def force_bytes(arg):
        if isinstance(arg, str):
            return arg.encode('ascii')
        return arg

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

    range3 = range

    def dict_keys(d):
        return d.keys()

    def dict_values(d):
        return d.values()

    import builtins     # noqa : unused import

    from urllib.request import urlopen      # noqa : unused import


class UnicodeMixin(object):

    """Mixin class to handle string formatting

    For classes that need to define a __unicode__ method of their own
    this class is used to ensure that the correct behaviour exists
    in Python versions 2 and 3.

    The mixin class implements __str__ based on your existing
    __unicode__ implementation.  In python 2, the output is encoded
    using the default system encoding.  This may well generate errors but
    that seems more appropriate as it will catch cases where the *str*
    function has been used instead of :py:func:`to_text`."""

    if py2:
        def __str__(self):      # noqa
            return self.__unicode__().encode(_sys_codec)
    else:
        def __str__(self):      # noqa
            return self.__unicode__()


class CmpMixin(object):

    """Mixin class for handling comparisons

    For compatibility with Python 2's __cmp__ method this class defines
    an implementation of __eq__, __lt__ and __le__ that are redirected
    to __cmp__.  These are the minimum methods required for Python's
    rich comparisons.

    In Python 2 it also provides an implementation of __ne__ that simply
    inverts the result of __eq__.  (This is not required in Python 3.)"""

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    if py2:
        def __ne__(self, other):    # noqa
            return not self.__eq__(other)
