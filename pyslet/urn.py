#! /usr/bin/env python
"""This module implements the URN specification defined in RFC 2141"""

import string

import pyslet.rfc2396 as uri


def is_upper(c):
    """Returns True if c matches upper"""
    return c and ord(c) >= 0x41 and ord(c) <= 0x5A


def is_lower(c):
    """Returns True if c matches lower"""
    return c and ord(c) >= 0x61 and ord(c) <= 0x7A


def is_number(c):
    """Returns True if c matches number"""
    return c and ord(c) >= 0x30 and ord(c) <= 0x39


def is_letnum(c):
    """Returns True if c matches letnum"""
    return c and (is_upper(c) or is_lower(c) or is_number(c))


def is_letnumhyp(c):
    """Returns True if c matches letnumhyp"""
    return c and (is_upper(c) or is_lower(c) or is_number(c) or ord(c) == 0x2D)


def is_trans(c):
    """Returns True if c matches trans

    Note that translated characters include reserved characters, even
    though they should normally be escaped (and in the case of '%' MUST
    be escaped).  The effect is that URNs consist of runs of characters
    that match the production for trans."""
    return c and (is_upper(c) or is_lower(c) or is_number(c) or
                  is_other(c) or is_reserved(c))


def is_hex(c):
    """Returns True if c matches hex"""
    return c and (is_number(c) or (ord(c) >= 0x41 and ord(c) <= 0x46) or
                  (ord(c) >= 0x61 and ord(c) <= 0x66))


def is_other(c):
    """Returns True if c matches other"""
    return c and c in "()+,-.:=@;$_!*'"


def is_reserved(c):
    """Returns True if c matches reserved"""
    return c and c in "%/?#"


def translate_to_urnchar(src, reserved_test=is_reserved):
    """Translates a source string into URN characters

    src
        A binary or unicode string.  In the latter case the string is
        encoded with utf-8 before being translated.

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
    if isinstance(src, unicode):
        src = src.encode('utf-8')
    for c in src:
        if reserved_test(c) or is_reserved(c) or not is_trans(c):
            if ord(c):
                result.append('%%%02X' % ord(c))
            else:
                raise ValueError("Zero byte in URN")
        else:
            result.append(c)
    return string.join(result, '')


def translate_from_urnchar(src):
    """Translates a URN string into an unencoded source string

    The main purpose of this function is to remove %-encoding but it
    will also check for the illegal 0-byte and raise an error if one is
    encountered.

    Returns a binary string without %-escapes.  To convert to a human
    readable string you should decode using utf-8."""
    result = []
    pos = 0
    while pos < len(src):
        c = src[pos]
        if c == "%":
            escape = src[pos + 1:pos + 3]
            c = chr(int(escape, 16))
            pos += 3
        elif is_trans(c):
            pos += 1
        else:
            raise ValueError("Illegal character in URN: %s" % repr(c))
        if ord(c):
            result.append(c)
        else:
            raise ValueError("Zero byte in URN")
    return string.join(result, '')


def parse_urn(src):
    """Parses a run of URN characters from a string

    src
        A binary string containing URN characters

    returns the src up to, but not including, the first character that
    fails to match the production for URN char."""
    pos = 0
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
    class.

    octets
        A binary string containing the URN

    The second form of constructor allows you to construct a URN from a
    namespace identifier and a namespace-specific string, both values
    are required in this form of the constructor.

    nid
        The namespace identifier, a string.

    nss
        The namespace-specific string, encoded appropriately for
        inclusion in a URN.

    ValueError is raised if the arguments are not in the correct format
    for a URN."""

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
                    raise ValueError("Expected NID in URN: %s" %
                                     self.opaque_part)
            elif mode == 1:
                if is_letnumhyp(c):
                    if pos > 31:
                        raise ValueError("NID in URN exceeds maximum length")
                    pos += 1
                    continue
                elif c == ':':
                    self.nid = self.opaque_part[:pos]
                    mode = 2
                    pos += 1
                    cpos = pos
                    continue
                else:
                    raise ValueError("Expected ':' in URN")
            elif mode == 2:
                if is_trans(c):
                    pos += 1
                    continue
                elif c is not None:
                    raise ValueError("Unexpected data in URN: %s" %
                                     self.opaque_part)
                else:
                    self.nss = self.opaque_part[cpos:]
                    break
        if self.nid.lower() == "urn":
            raise ValueError("NID value of 'urn' is not allowed in URN")

    def canonicalize(self):
        return uri.URI.from_octets(
            "%s:%s:%s" % (self.scheme.lower(), self.nid.lower(),
                          uri.canonicalize_data(self.nss, lambda x: False)))


uri.URI.register('urn', URN)
