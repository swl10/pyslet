#! /usr/bin/env python
"""This module implements the URN specification defined in RFC 2141"""

from . import rfc2396 as uri

from .py2 import (
    byte,
    byte_value,
    is_unicode,
    join_bytes,
    join_characters)
from .unicode5 import CharClass


is_upper = uri.is_upalpha

is_lower = uri.is_lowalpha

is_number = uri.is_digit

is_letnum = uri.is_alphanum

letnumhyp = CharClass(uri.alphanum, '-')
is_letnumhyp = letnumhyp.test

reserved = CharClass("%/?#")
is_reserved = reserved.test

other = CharClass("()+,-.:=@;$_!*'")
is_other = other.test

trans = CharClass(uri.alphanum, other, reserved)
is_trans = trans.test

is_hex = uri.is_hex


def translate_to_urnchar(src, reserved_test=is_reserved):
    """Translates a source string into URN characters

    src
        A binary or unicode string.  In the latter case the string is
        encoded with utf-8 as part of being translated, in the former
        case it must be a valid UTF-8 string of bytes.

    reserved_test
        A function that tests if a character is reserved.  It defaults
        to :func:`is_reserved` but can be any function that takes a
        single argument and returns a boolean.  You can't prevent a
        character from being encoded with this function (even if you
        pass lambda x:False, but you can add additional characters to
        the list of those that should be escaped.  For example, to
        encode the '.' character you could pass::

            lambda x: x=='.'

    The result is a URI-encode string suitable for adding to the
    namespace-specific part of a URN."""
    result = []
    if not is_unicode(src):
        src = src.decode('utf-8')
    for c in src:
        if reserved_test(c) or is_reserved(c) or not is_trans(c):
            if ord(c):
                for b in c.encode('utf-8'):
                    result.append('%%%02X' % byte_value(b))
            else:
                raise ValueError("Zero byte in URN")
        else:
            result.append(c)
    return join_characters(result)


def translate_from_urnchar(src):
    """Translates a URN string into an unencoded source string

    The main purpose of this function is to remove %-encoding but it
    will also check for the illegal 0-byte and raise an error if one is
    encountered.

    Returns a character string *without* %-escapes.  As part of the
    conversion the implicit UTF-8 encoding is removed."""
    result = []
    pos = 0
    zbyte = byte(0)
    while pos < len(src):
        c = src[pos]
        if c == "%":
            escape = src[pos + 1:pos + 3]
            c = byte(int(escape, 16))
            pos += 3
        elif is_trans(c):
            c = byte(c)
            pos += 1
        else:
            raise ValueError("Illegal character in URN: %s" % repr(c))
        if c != zbyte:
            result.append(c)
        else:
            raise ValueError("Zero byte in URN")
    return join_bytes(result).decode('utf-8')


def parse_urn(src):
    """Parses a run of URN characters from a string

    src
        A character string containing URN characters.  Will accept
        binary strings encoding ASCII characters (only).

    returns the src up to, but not including, the first character that
    fails to match the production for URN char (as a character string)."""
    pos = 0
    if isinstance(src, bytes):
        src = src.decode('ascii')
    while pos < len(src):
        c = src[pos]
        if is_trans(c):
            pos += 1
            continue
        else:
            break
    src = src[:pos]
    return src


class URN(uri.URI):

    """Represents a URN

    There are two forms of constructor, the first uses a single
    positional argument and matches the constructor for the base URI
    class.  This enables URNs to be created automatically from
    :meth:`~pyslet.rfc2396.URI.from_octets`.

    octets
        A character string containing the URN

    The second form of constructor allows you to construct a URN from a
    namespace identifier and a namespace-specific string, both values
    are required in this form of the constructor.

    nid
        The namespace identifier, a string.

    nss
        The namespace-specific string, encoded appropriately for
        inclusion in a URN.

    ValueError is raised if the arguments are not passed correctly,
    :class:`~pyslet.rfc2396.URIException` is raised if there a problem
    parsing or creating the URN itself."""

    def __init__(self, octets=None, nid=None, nss=None):
        #: the namespace identifier for this URN
        self.nid = None
        #: the namespace specific part of the URN
        self.nss = None
        if octets is not None:
            # parse it from the octets
            super(URN, self).__init__(octets)
        else:
            if nid is None or nss is None:
                raise ValueError("octets, nid or nss required")
            super(URN, self).__init__("urn:%s:%s" % (nid, nss))

    def parse_scheme_specific_part(self):
        super(URN, self).parse_scheme_specific_part()
        pos = 0
        self.nid = self.nss = None
        mode = 0
        cpos = None
        while True:
            if pos < len(self.opaque_part):
                c = self.opaque_part[pos]
            else:
                c = None
            if mode == 0:
                if is_letnum(c):
                    mode = 1
                    pos += 1
                    continue
                else:
                    raise uri.URIException("Expected NID in URN: %s" %
                                           self.opaque_part)
            elif mode == 1:
                if is_letnumhyp(c):
                    if pos > 31:
                        raise uri.URIException(
                            "NID in URN exceeds maximum length")
                    pos += 1
                    continue
                elif c == ':':
                    self.nid = self.opaque_part[:pos]
                    mode = 2
                    pos += 1
                    cpos = pos
                    continue
                else:
                    raise uri.URIException("Expected ':' in URN")
            elif mode == 2:
                if is_trans(c):
                    pos += 1
                    continue
                elif c is not None:
                    raise uri.URIException("Unexpected data in URN: %s" %
                                           self.opaque_part)
                else:
                    self.nss = self.opaque_part[cpos:]
                    break
        if self.nid.lower() == "urn":
            raise uri.URIException("NID value of 'urn' is not allowed in URN")

    def canonicalize(self):
        return uri.URI.from_octets(
            "%s:%s:%s" % (self.scheme.lower(), self.nid.lower(),
                          uri.canonicalize_data(self.nss, lambda x: False)))


uri.URI.register('urn', URN)
