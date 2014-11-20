#! /usr/bin/env python
"""This module implements the URI specification defined in RFC 2396"""
import string
import os
import os.path
import sys
import warnings

from types import UnicodeType

import pyslet.vfs as vfs

from pyslet.pep8 import renamed_function, PEP8Compatibility


class URIException(Exception):
    pass


class URIRelativeError(URIException):
    pass


def is_up_alpha(c):
    return c and (ord(c) >= 0x41 and ord(c) <= 0x5A)


def is_low_alpha(c):
    return c and (ord(c) >= 0x61 and ord(c) <= 0x7A)


def is_alpha(c):
    return is_up_alpha(c) or is_low_alpha(c)


def is_digit(c):
    return c and (ord(c) >= 0x30 and ord(c) <= 0x39)


def is_alpha_num(c):
    return is_up_alpha(c) or is_low_alpha(c) or is_digit(c)


def is_reserved(c):
    # ;/?:@&=+$,
    return c and ord(c) in (0x3B, 0x2F, 0x3F, 0x3A, 0x40, 0x26, 0x3D,
                            0x2B, 0x24, 0x2C)


def is_unreserved(c):
    return is_alpha_num(c) or is_mark(c)


def is_mark(c):
    # -_.!~*'()
    return c and ord(c) in (0x2D, 0x5F, 0x2E, 0x21, 0x7E, 0x2A,
                            0x27, 0x28, 0x29)


def is_hex(c):
    return c and (is_digit(c) or
                  (ord(c) >= 0x41 and ord(c) <= 0x46) or
                  (ord(c) >= 0x61 and ord(c) <= 0x66))


def is_control(c):
    return c and (ord(c) < 0x20 or ord(c) == 0x7F)


def is_space(c):
    return c and ord(c) == 0x20


def is_delims(c):
    return c and ord(c) in (0x3C, 0x3E, 0x23, 0x25, 0x22)


def is_unwise(c):
    return c and ord(c) in (0x7B, 0x7D, 0x7C, 0x5C, 0x5E, 0x5B, 0x5D, 0x60)


def is_scheme_char(c):
    return is_alpha_num(c) or (c and ord(c) in (0x2B, 0x2D, 0x2E))


def is_authority_reserved(c):
    return (c and ord(c) in (0x3B, 0x3A, 0x40, 0x3F, 0x2F))


def parse_uric(source, pos=0):
    """Returns the number of URI characters in source

    source
        A source string

    pos
        The place at which to start parsing (defaults to 0)"""
    uric = 0
    mode = None
    while pos < len(source):
        c = source[pos]
        pos += 1
        if mode is None:
            if is_reserved(c) or is_unreserved(c):
                uric += 1
            elif ord(c) == 0x25:  # % escape
                mode = '%'
            else:
                break
        elif mode == '%':
            if is_hex(c):
                mode = c
            else:
                break
        else:
            if is_hex(c):
                mode = None
                uric += 3
            else:
                break
    return uric


@renamed_function
def ParseURIC(source, pos=0):      # noqa
    pass


def parse_scheme(octets):
    pos = 0
    scheme = None
    while pos < len(octets):
        c = octets[pos]
        if (pos and is_scheme_char(c)) or is_alpha(c):
            pos += 1
        else:
            if ord(c) == 0x3A:
                # we have the scheme
                scheme = octets[0:pos]
            break
    return scheme


def canonicalize_data(source, unreserved_test=is_unreserved):
    """Returns the canonical form of *source* string.

    unreserved_test
        A function with the same signature as :func:`is_unreserved`,
        which it defaults to.  By providing a different function you can
        control which characters will have their escapes removed.

    The canonical form is the same string but any unreserved characters
    represented as hex escapes in source are unencoded and any unescaped
    characters that are neither reserved nor unreserved are escaped.

    All hex escapes are promoted to upper case."""
    result = []
    pos = 0
    while pos < len(source):
        c = source[pos]
        if c == "%":
            escape = source[pos + 1:pos + 3]
            c = chr(int(escape, 16))
            if unreserved_test(c):
                result.append(c)
            else:
                result.append("%%%02X" % ord(c))
            pos += 3
        elif not (is_unreserved(c) or is_reserved(c)):
            result.append("%%%02X" % ord(c))
            pos += 1
        else:
            result.append(c)
            pos += 1
    return string.join(result, '')


@renamed_function
def CanonicalizeData(source):      # noqa
    pass


def escape_data(source, reserved_test=is_reserved):
    """Performs URI escaping on source

    source
        The input string

    reserved_test
        Default :func:`is_reserved`, the function to test if a character
        should be escaped.  This function should take a single character
        as an argument and return True if the character must be escaped.
        Characters for which this function returns False will still be
        escaped if they are neither unreserved nor reserved characters.

    Returns the escaped string."""
    result = []
    for c in source:
        if reserved_test(c) or not (is_unreserved(c) or is_reserved(c)):
            # short-circuit boolean means we don't evaluate is_reserved
            # twice in default case
            result.append("%%%02X" % ord(c))
        else:
            result.append(c)
    return string.join(result, '')


@renamed_function
def EscapeData(source, reserved_test=is_reserved):      # noqa
    pass


def unescape_data(source):
    """Performs URI unescaping

    source
        The URI-encoded string

    Returns the string with escape characters removed.  The string is
    still a binary string of octets, this function does remove any
    character encoding that may apply."""
    data = []
    mode = None
    pos = 0
    while pos < len(source):
        c = source[pos]
        pos += 1
        if mode is None:
            if ord(c) == 0x25:
                mode = '%'
            else:
                data.append(c)
        elif mode == '%':
            if is_hex(c):
                mode = c
            else:
                data.append('%')
                data.append(c)
                mode = None
        else:
            if is_hex(c):
                data.append(chr(int(mode + c, 16)))
            else:
                data.append('%')
                data.append(mode)
            mode = None
    return string.join(data, '')


@renamed_function
def UnescapeData(source):      # noqa
    pass


def split_server(authority):
    userinfo = None
    host = None
    port = None
    if authority is not None:
        if authority:
            mode = None
            pos = 0
            while True:
                if pos < len(authority):
                    c = authority[pos]
                else:
                    c = None
                if mode is None:
                    if c is None:
                        host = authority
                        break
                    elif ord(c) == 0x40:
                        userinfo = authority[:pos]
                        mode = 'h'
                        hstart = pos + 1
                    elif ord(c) == 0x3A:
                        # could be in userinfo or start of port
                        host = authority[:pos]
                        mode = 'p'
                        pstart = pos + 1
                    pos += 1
                elif mode == 'h':
                    if c is None:
                        host = authority[hstart:]
                        break
                    elif ord(c) == 0x3A:
                        host = authority[hstart:pos]
                        mode = 'p'
                        pstart = pos + 1
                    pos += 1
                elif mode == 'p':
                    if c is None:
                        port = authority[pstart:]
                        break
                    elif ord(c) == 0x40 and userinfo is None:
                        # must have been username:pass@
                        userinfo = authority[:pos]
                        host = None
                        mode = 'h'
                        hstart = pos + 1
                    elif not is_digit(c):
                        if userinfo is None:
                            # probably username:pass...
                            host = None
                            mode = 'u'
                        else:
                            # userinfo@host:123XX - bad port, stop parsing
                            port = authority[pstart:pos]
                            break
                    pos += 1
                elif mode == 'u':
                    # username:pass...
                    if c is None:
                        userinfo = authority
                        host = ''
                        break
                    elif ord(c) == 0x40:
                        userinfo = authority[:pos]
                        mode = 'h'
                        hstart = pos + 1
                    pos += 1
        else:
            host = ''
    return userinfo, host, port


def is_path_segment_reserved(c):
    return (c and ord(c) in (0x2F, 0x3B, 0x3D, 0x3F))


def split_path(path, abs_path=True):
    segments = []
    if path:
        pos = 0
        if abs_path:
            seg_start = None
        else:
            seg_start = 0
        while True:
            if pos < len(path):
                c = path[pos]
                if ord(c) == 0x2F:
                    if seg_start is not None:
                        segments.append(path[seg_start:pos])
                    seg_start = pos + 1
                pos += 1
            else:
                if seg_start is not None:
                    segments.append(path[seg_start:pos])
                break
    elif not abs_path:
        # relative paths always have an empty segment
        segments.append('')
    return segments


def split_abs_path(abs_path):
    return split_path(abs_path, True)


def split_rel_path(rel_path):
    return split_path(rel_path, False)


def normalize_segments(path_segments):
    """Normalizes a list of path_segments, as returned by Split*Path methods.

    Normalizing follows the rules for resolving relative URI paths, './'
    and trailing '.' are removed, 'seg/../' and trailing seg/.. are
    also removed."""
    i = 0
    while i < len(path_segments):
        if path_segments[i] == '.':
            if i + 1 >= len(path_segments):
                path_segments[i] = ''
            else:
                del path_segments[i]
        elif (path_segments[i] == '..' and
                (i > 0 and path_segments[i - 1] != '..')):
            if i + 1 >= len(path_segments):
                path_segments[i] = ''
                del path_segments[i - 1]
            else:
                del path_segments[i]
                del path_segments[i - 1]
                i -= 1
        else:
            i += 1
    if path_segments and path_segments[-1] == '..':
        # special case of trailing '..' gets an extra slash for consistency
        path_segments.append('')


@renamed_function
def NormalizeSegments(path_segments):     # noqa
    pass


def relativize_segments(path_segments, base_segments):
    result = []
    pos = 0
    while pos < len(base_segments):
        if result:
            result = ['..'] + result
        else:
            if (pos >= len(path_segments) or
                    base_segments[pos] != path_segments[pos]):
                result = result + path_segments[pos:]
        pos = pos + 1
    if not result and len(path_segments) > len(base_segments):
        # full match but path_segments is longer
        return path_segments[len(base_segments) - 1:]
    elif result == ['']:
        return ['.'] + result
    else:
        return result


def make_rel_path_abs(abs_path, base_path):
    """Return abs_path relative to base_path"""
    path_segments = split_abs_path(abs_path)
    normalize_segments(path_segments)
    base_segments = split_abs_path(base_path)
    normalize_segments(base_segments)
    result = relativize_segments(path_segments, base_segments)
    return string.join(result, '/')


def make_rel_path_rel(rel_path, base_rel_path):
    """Return rel_path relative to base_rel_path"""
    path_segments = split_rel_path(rel_path)
    normalize_segments(path_segments)
    base_segments = split_rel_path(base_rel_path)
    normalize_segments(base_segments)
    # At this point there are no '.' components, but there may be leading '..'
    i = 0
    while i < len(path_segments):
        if path_segments[i] == '..':
            i += 1
        else:
            break
    j = 0
    while j < len(base_segments):
        if base_segments[j] == '..':
            j += 1
        else:
            break
    if j > i:
        i = j
    if i:
        # we have leading '..' components, add a common path prefix and
        # re-normalize
        path_segments = ['x'] * i + path_segments
        normalize_segments(path_segments)
        base_segments = ['x'] * i + base_segments
        normalize_segments(base_segments)
    result = relativize_segments(path_segments, base_segments)
    return string.join(result, '/')


def split_path_segment(segment):
    pchar = ''
    params = []
    pos = 0
    mode = None
    while True:
        if pos < len(segment):
            c = segment[pos]
        else:
            c = None
        if mode is None:
            if c is None:
                pchar = segment
                break
            elif ord(c) == 0x3B:
                mode = ';'
                pchar = segment[:pos]
                pstart = pos + 1
            pos += 1
        elif mode == ';':
            if c is None:
                params.append(segment[pstart:])
                break
            elif ord(c) == 0x3B:
                params.append(segment[pstart:pos])
                pstart = pos + 1
            pos += 1
    return pchar, params


def is_query_reserved(c):
    return (c and ord(c) in (0x3B, 0x2F, 0x3F, 0x3A, 0x40, 0x26, 0x3D,
                             0x2B, 0x2C, 0x24))


@renamed_function
def IsQueryReserved(c):     # noqa
    pass


def encode_unicode_uri(usrc):
    """Extracts a URI octet-string from a unicode string.

    The encoding algorithm used is the same as the one adopted by HTML:
    utf-8 and then %-escape. This is not part of the RFC standard which
    only defines the behaviour for streams of octets but it is in line
    with the approach adopted by the later IRI spec."""
    octets = []
    for c in usrc:
        if ord(c) > 0x7F:
            octets = octets + map(lambda x: "%%%2X" %
                                  ord(x), c.encode('UTF-8'))
        else:
            octets.append(chr(ord(c)))
    return string.join(octets, '')


@renamed_function
def EncodeUnicodeURI(usrc):     # noqa
    pass


class URI(PEP8Compatibility):

    r"""Class to represent URI References

        You won't normally instantiate a URI directly as it represents a
        less powerful generic URI.  This class is designed to be
        overridden by scheme-specific implementations.  Use the class
        method :meth:`from_octets` to create instances.

        Unless otherwise stated, all attributes use binary strings
        comprised of octets (bytes) which are defined as URI
        'characters' in the specification.  They are typically
        represented by their corresponding characters in the US ASCII
        character set.

        URIs can be converted to strings (of bytes) using str but not
        unicode strings (see below).  The string form is used in
        comparisons.

        The reason for this restriction is best illustrated with an
        example:

        The URI %E8%8B%B1%E5%9B%BD.xml is a UTF-8 and URL-encoded path
        segment using the Chinese word for United Kingdom.  When we
        remove the URL-encoding we get the string
        '\\xe8\\x8b\\xb1\\xe5\\x9b\\xbd.xml' which must be interpreted
        with utf-8 to get the intended path segment value:
        u'\\u82f1\\u56fd.xml'. However, if the URL was marked as being a
        unicode string of characters then this second stage would not be
        carried out and the result would be the unicode string
        u'\\xe8\\x8b\\xb1\\xe5\\x9b\\xbd', which is a meaningless string
        of 6 characters taken from the European Latin-1 character
        set."""

    def __init__(self, octets):
        PEP8Compatibility.__init__(self)
        uri_len = parse_uric(octets)
        #: The octet string representing this URI
        self.octets = octets[0:uri_len]
        #: The fragment string that was appended to the URI or None if
        #: no fragment was given.
        self.fragment = None
        if uri_len < len(octets):
            if ord(octets[uri_len]) == 0x23:
                self.fragment = octets[uri_len + 1:]
            else:
                raise URIException(
                    "URI incompletely parsed from octets: %s" % octets)
        #: The URI scheme, if present
        self.scheme = parse_scheme(self.octets)
        #: The scheme specific part of the URI
        self.scheme_specific_part = None
        #: None if the URI is hierarchical, otherwise the same as
        #: scheme_specific_part
        self.opaque_part = None
        #: The authority (e.g., host name) of a hierarchical URI
        self.authority = None
        #: The absolute path of a hierarchical URI (None if the path is
        #: relative)
        self.abs_path = None
        #: The relative path of a hierarchical URI (None if the path is
        #: absolute)
        self.rel_path = None
        #: The optional query associated with a hierarchical URI
        self.query = None
        if self.scheme is not None:
            self.scheme_specific_part = self.octets[len(self.scheme) + 1:]
        if self.is_absolute():
            self.rel_path = None
            self.parse_scheme_specific_part()
        else:
            self.opaque_part = None
            self.parse_relative_uri()

    def parse_scheme_specific_part(self):
        pos = 0
        mode = ':'
        self.opaque_part = self.authority = self.abs_path = self.query = None
        while True:
            if pos < len(self.scheme_specific_part):
                c = self.scheme_specific_part[pos]
            else:
                c = None
            if mode == ':':
                # Is this a hier_part or opaque_part?
                if c is None:
                    # Empty scheme-specific part; neither opaque nor
                    # hierarchical
                    break
                elif ord(c) == 0x2F:
                    mode = '/'
                else:
                    self.opaque_part = self.scheme_specific_part
                    break
                pos += 1
            elif mode == '/':
                # Is this a net_path or abs_path
                if c is None:
                    # Single '/' is an abs_path
                    self.abs_path = '/'
                    break
                elif ord(c) == 0x2F:
                    mode = 'a'
                    astart = pos + 1
                elif ord(c) == 0x3F:
                    # special case, abs_path is /
                    self.abs_path = '/'
                    mode = '?'
                    qstart = pos + 1
                else:
                    mode = 'p'
                    pstart = pos - 1
                pos += 1
            elif mode == 'a':
                # parse authority
                if c is None:
                    self.authority = self.scheme_specific_part[astart:pos]
                    break
                elif ord(c) == 0x2F:
                    self.authority = self.scheme_specific_part[astart:pos]
                    mode = 'p'
                    pstart = pos
                elif ord(c) == 0x3F:
                    self.authority = self.scheme_specific_part[astart:pos]
                    mode = '?'
                    qstart = pos + 1
                pos += 1
            elif mode == 'p':
                # parse abs_path
                if c is None:
                    self.abs_path = self.scheme_specific_part[pstart:pos]
                    break
                elif ord(c) == 0x3F:
                    self.abs_path = self.scheme_specific_part[pstart:pos]
                    mode = '?'
                    qstart = pos + 1
                pos += 1
            elif mode == '?':
                # query string is everything up to the end of the URI
                if c is None:
                    self.query = self.scheme_specific_part[qstart:pos]
                    break
                pos += 1

    def parse_relative_uri(self):
        pos = 0
        self.authority = self.abs_path = self.rel_path = self.query = None
        mode = None
        while True:
            if pos < len(self.octets):
                c = self.octets[pos]
            else:
                c = None
            if mode is None:
                # net_path, abs_path or rel_path ?
                if c is None:
                    # An empty URI is a same document reference
                    self.rel_path = ''
                    break
                elif ord(c) == 0x2F:
                    mode = '/'
                elif ord(c) == 0x3F:
                    # the RFC is ambiguous here, seems rel_path can be empty
                    # afterall
                    self.rel_path = ''
                    mode = '?'
                    qstart = pos + 1
                else:
                    mode = 'r'
                    rstart = pos
                pos += 1
            elif mode == '/':
                # Is this a net_path or abs_path
                if c is None:
                    # Single '/' is an abs_path
                    self.abs_path = '/'
                    break
                elif ord(c) == 0x2F:
                    mode = 'a'
                    astart = pos + 1
                elif ord(c) == 0x3F:
                    # special case, abs_path is /
                    self.abs_path = '/'
                    mode = '?'
                    qstart = pos + 1
                else:
                    mode = 'p'
                    pstart = pos - 1
                pos += 1
            elif mode == 'a':
                # parse authority
                if c is None:
                    self.authority = self.octets[astart:pos]
                    break
                elif ord(c) == 0x2F:
                    self.authority = self.octets[astart:pos]
                    mode = 'p'
                    pstart = pos
                elif ord(c) == 0x3F:
                    self.authority = self.octets[astart:pos]
                    mode = '?'
                    qstart = pos + 1
                pos += 1
            elif mode == 'p':
                # parse abs_path
                if c is None:
                    self.abs_path = self.octets[pstart:pos]
                    break
                elif ord(c) == 0x3F:
                    self.abs_path = self.octets[pstart:pos]
                    mode = '?'
                    qstart = pos + 1
                pos += 1
            elif mode == 'r':
                # parse rel_path
                if c is None:
                    self.rel_path = self.octets[rstart:pos]
                    break
                elif ord(c) == 0x3F:
                    self.rel_path = self.octets[rstart:pos]
                    mode = '?'
                    qstart = pos + 1
                pos += 1
            elif mode == '?':
                # query string is everything up to the end of the URI
                if c is None:
                    self.query = self.octets[qstart:pos]
                    break
                pos += 1

    def get_file_name(self):
        """Returns the file name associated with this resource or None if the
        URL scheme does not have the concept.  By default the file name is
        extracted from the last component of the path. Note the subtle
        difference between returning None and returning an empty string
        (indicating that the URI represents a directory-like object)."""
        if self.abs_path:
            segments = split_abs_path(self.abs_path)
        elif self.rel_path:
            segments = split_rel_path(self.rel_path)
        else:
            segments = []
        file_name = None
        # we loop around until we have a non-empty file_name
        while file_name is None:
            if segments:
                file_name = segments.pop()
            else:
                break
        if file_name is not None:
            file_name = unicode(unescape_data(file_name), 'utf-8')
            return file_name
        else:
            return None

    def get_canonical_root(self):
        """Returns a new URI comprised of the scheme and authority only.

        Only valid for absolute URIs."""
        if self.is_absolute():
            canonical_uri = self.canonicalize()
            result = [canonical_uri.scheme, ':']
            if canonical_uri.authority is not None:
                result.append('//')
                result.append(canonical_uri.authority)
            return URI.from_octets(string.join(result, ''))
        else:
            return None

    def resolve(self, base, current_doc_ref=None):
        """Resolves a relative URI against a base URI

        base
            A :py:class:`URI` instance representing the base URI
            against which to resolve this URI.  You may also
            pass a URI string for this parameter.

        current_doc_ref
            The optional *current_doc_ref* allows you to handle the
            special case of resolving the empty URI.  Strictly speaking,
            fragments are not part of the URI itself so a relative URI
            consisting of the empty string, or a relative URI consisting
            of just a fragment both refer to the current document.  By
            default, *current_doc_ref* is assumed to be the same as
            *base* but there are cases where the base URI is not the
            same as the URI used to originally retrieve the document and
            this optional parameter allows you to cope with those cases.

        Returns a new :py:class:`URI` instance.

        If the base URI is also relative then the result is a relative
        URI, otherwise the result is an absolute URI.  The RFC does not
        actually go into the procedure for combining relative URIs but
        if B is an absolute URI and R1 and R2 are relative URIs then
        using the resolve operator::

                U1 = B [*] R1
                U2 = U1 [*] R2
                U2 = ( B [*] R1 ) [*] R2

        The last expression prompts the issue of associativity, in other
        words, is the following expression also valid? ::

                U2 = B [*] ( R1 [*] R2 )

        For this to work it must be possible to use the resolve operator
        to combine two relative URIs to make a third, which is what we
        allow here."""
        if isinstance(base, (str, unicode)):
            base = URI.from_octets(base)
        if current_doc_ref is None:
            current_doc_ref = base
        if (not(self.abs_path or self.rel_path) and
                self.scheme is None and self.authority is None and
                self.query is None):
            # current document reference, just change the fragment
            if self.fragment is None:
                return URI.from_octets(current_doc_ref.octets)
            else:
                return URI.from_octets(
                    current_doc_ref.octets + '#' + self.fragment)
        if self.scheme is not None:
            return URI.from_octets(str(self))
        scheme = base.scheme
        authority = None
        if self.authority is None:
            authority = base.authority
            if self.abs_path is None:
                if base.abs_path is not None:
                    segments = split_abs_path(base.abs_path)[:-1]
                    segments = segments + split_rel_path(self.rel_path)
                    normalize_segments(segments)
                    abs_path = '/' + string.join(segments, '/')
                    rel_path = None
                else:
                    segments = split_rel_path(base.rel_path)[:-1]
                    segments = segments + split_rel_path(self.rel_path)
                    normalize_segments(segments)
                    abs_path = None
                    rel_path = string.join(segments, '/')
                    if rel_path == '':
                        # degenerate case, as we are relative we won't prefix
                        # with /
                        rel_path = './'
            else:
                abs_path = self.abs_path
                rel_path = None
        else:
            authority = self.authority
            abs_path = self.abs_path
            rel_path = None
        result = []
        if scheme is not None:
            result.append(scheme)
            result.append(':')
        if authority is not None:
            result.append('//')
            result.append(authority)
        if abs_path is not None:
            result.append(abs_path)
        elif rel_path is not None:
            result.append(rel_path)
        if self.query is not None:
            result.append('?')
            result.append(self.query)
        if self.fragment is not None:
            result.append('#')
            result.append(self.fragment)
        return URI.from_octets(string.join(result, ''))

    def relative(self, base):
        """Calculates a URI expressed relative to *base*.

        base
            A :py:class:`URI` instance representing the base URI against
            which to calculate the relative URI.  You may also pass a
            URI string for this parameter.

        Returns a new :py:class:`URI` instance.

        As we allow the :meth:`resolve` method for two relative paths it
        makes sense for the Relative operator to also be defined::

            R3 = R1 [*] R2
            R3 [/] R1 = R2

        There are some significant restrictions, URIs are classified by
        how specified they are with:

            absolute URI > authority > absolute path > relative path

        If R is absolute, or simply more specified than B on the
        above scale and::

            U = B [*] R

        then U = R regardless of the value of B and therefore::

            U [/] B = U if B is less specified than U

        Also note that if U is a relative URI then B cannot be absolute.
        In fact B must always be less than, or equally specified to U
        because B is the base URI from which U has been derived::

            U [/] B = undefined if B is more specified than U

        Therefore the only interesting cases are when B is equally
        specified to U.  To give a concrete example::

            U = /HD/User/setting.txt
            B = /HD/folder/file.txt

            /HD/User/setting.txt [\] /HD/folder/file.txt = ../User/setting.txt
            /HD/User/setting.txt = /HD/folder/file.txt [*] ../User/setting.txt

        And for relative paths::

            U = User/setting.txt
            B = User/folder/file.txt

            User/setting.txt [\] User/folder/file.txt = ../setting.txt
            User/setting.txt = User/folder/file.txt [*] ../setting.txt"""
        if self.opaque_part is not None:
            # This is not a hierarchical URI so we can ignore base
            return URI.from_octets(str(self))
        if isinstance(base, (str, unicode)):
            base = URI.from_octets(base)
        if self.scheme is None:
            if base.scheme is not None:
                raise URIRelativeError(str(base))
        elif base.scheme is None or self.scheme.lower() != base.scheme.lower():
            return URI.from_octets(str(self))
        # continuing with equal schemes; scheme will not be shown in result
        if self.authority is None:
            if base.authority is not None:
                raise URIRelativeError(str(base))
        if self.authority != base.authority:
            authority = self.authority
            abs_path = self.abs_path
            rel_path = self.rel_path
        else:
            # equal or empty authorities
            authority = None
            if self.abs_path is None:
                if base.abs_path is not None:
                    raise URIRelativeError(str(base))
                abs_path = None
                if self.rel_path is None:
                    raise URIRelativeError(str(base))
                if base.rel_path is None:
                    rel_path = self.rel_path
                else:
                    # two relative paths, calculate self relative to base
                    # we add a common leading segment to re-use the abs_path
                    # routine
                    rel_path = make_rel_path_rel(self.rel_path, base.rel_path)
            elif base.abs_path is None:
                return URI.from_octets(str(self))
            else:
                # two absolute paths, calculate self relative to base
                abs_path = None
                rel_path = make_rel_path_abs(self.abs_path, base.abs_path)
                # todo: /a/b relative to /c/d really should be '/a/b'
                # and not ../a/b in particular, drive letters look wrong
                # in relative paths: ../C:/Program%20Files/
        result = []
        if authority is not None:
            result.append('//')
            result.append(authority)
        if abs_path is not None:
            result.append(abs_path)
        elif rel_path is not None:
            result.append(rel_path)
        if self.query is not None:
            result.append('?')
            result.append(self.query)
        if self.fragment is not None:
            result.append('#')
            result.append(self.fragment)
        return URI.from_octets(string.join(result, ''))

    def __str__(self):
        if self.fragment is not None:
            return self.octets + '#' + self.fragment
        else:
            return self.octets

    def __cmp__(self, other_uri):
        if not isinstance(other_uri, URI):
            other_uri = URI.from_octets(other_uri)
        return cmp(str(self.canonicalize()), str(other_uri.canonicalize()))

    def canonicalize(self):
        """Returns a canonical form of this URI

        For unknown schemes we simply convert the scheme to lower case
        so that, for example, X-scheme:data becomes x-scheme:data.

        Derived classes should apply their own transformation rules."""
        new_uri = []
        if self.scheme is not None:
            new_uri.append(self.scheme.lower())
            new_uri.append(':')
            new_uri.append(self.scheme_specific_part)
        else:
            # we don't need to look inside the URI
            new_uri.append(self.octets)
        if self.fragment:
            new_uri.append('#')
            new_uri.append(self.fragment)
        return URI.from_octets(string.join(new_uri, ''))

    def match(self, other_uri):
        """Compares this URI against other_uri returning True if they match."""
        return str(self.canonicalize()) == str(other_uri.canonicalize())

    def is_absolute(self):
        """Returns True if this URI is absolute

        An absolute URI is fully specified with a scheme, e.g., 'http'."""
        return self.scheme is not None

    #: A dictionary mapping lower-case URI schemes onto the special
    #: classes used to represent them
    scheme_class = {}

    @classmethod
    def register(cls, scheme, uri_class):
        """Registers a class to represent a scheme

        scheme
            A string representing a URI scheme, e.g., 'http'.  The
            string is converted to lower-case before it is registered.

        uri_class
            A class derived from URI that is used to represent URI
            from scheme

        If a class has already been registered for the scheme it is
        replaced."""
        cls.scheme_class[scheme.lower()] = uri_class

    @classmethod
    def from_octets(cls, octets):
        """Creates an instance of :class:`URI` from a string

        octets
            A string of bytes that represents the URI.  If a unicode
            string is passed it is converted to a string of bytes
            (octets) using :func:`encode_unicode_uri` first."""
        if isinstance(octets, unicode):
            octets = encode_unicode_uri(octets)
        scheme = parse_scheme(octets)
        if scheme is not None:
            scheme = scheme.lower()
            c = cls.scheme_class.get(scheme, None)
            if c is None:
                _load_uri_class(scheme)
                c = cls.scheme_class.get(scheme, URI)
        else:
            c = URI
        return c(octets)

    @classmethod
    def from_path(cls, path):
        """Converts a local file path into a :class:`URI` instance.

        path
            A file path string.  If the path is not absolute it is made
            absolute by resolving it relative to the current working
            directory before converting it to a URI.

        Under Windows, the URL is constructed according to the
        recommendations in this blog post:
        http://blogs.msdn.com/b/ie/archive/2006/12/06/file-uris-in-windows.aspx
        In other words, UNC paths are mapped to both the network
        location and path components of the resulting file URL."""
        host = ''
        segments = []
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        drive, head = os.path.splitdrive(path)
        while head:
            new_head, tail = os.path.split(head)
            if new_head == head:
                # We are unable to split any more from head
                break
            else:
                segments[0:0] = [tail]
                if new_head == '\\\\':
                    # This is the unusual case of the UNC path, first
                    # segment is machine
                    host = segments[0]
                    del segments[0]
                    break
                head = new_head
        if drive:
            segments[0:0] = [drive]
        # At this point we need to convert to octets
        c = sys.getfilesystemencoding()
        if type(host) is UnicodeType:
            host = escape_data(host.encode(c), is_authority_reserved)
        for i in xrange(len(segments)):
            # we always use utf-8 in URL path segments to make URLs portable
            if type(segments[i]) is UnicodeType:
                segments[i] = escape_data(
                    segments[i].encode('utf-8'), is_path_segment_reserved)
            else:
                segments[i] = escape_data(
                    unicode(segments[i], c).encode('utf-8'),
                    is_path_segment_reserved)
        return FileURL('file://%s/%s' % (host, string.join(segments, '/')))

    @classmethod
    def from_virtual_path(cls, path):
        """Converts a virtual file path into a :class:`URI` instance

        path
            A :class:`pyslet.vfs.FilePath` instance representing
            a file path in a virtual file system.

        The authority (host name) in the resulting URL is set from the
        name of the virtual file system.  If the path is flagged as
        being a UNC path and it has a non-empty machine name then
        ValueError is raised. """
        host = path.fsName
        segments = []
        if not path.isabs():
            path = path.abspath()
        drive, head = path.splitdrive()
        unc_flag = path.IsUNC()
        while head:
            new_head, tail = head.split()
            if new_head == head:
                # We are unable to split any more from head
                if unc_flag and segments:
                    # This is the unusual case of the UNC path, first
                    # segment is machine
                    if host:
                        raise ValueError("UNC hosts cannot be specified in "
                                         "named file systems.")
                    host = str(segments[0])
                    del segments[0]
                break
            else:
                segments[0:0] = [tail]
                head = new_head
        if drive:
            segments[0:0] = [drive]
        # At this point we need to convert to octets
        if host:
            host = escape_data(host, is_authority_reserved)
        for i in xrange(len(segments)):
            # we always use utf-8 in URL path segments to make URLs
            # portable
            segments[i] = escape_data(unicode(segments[i]).encode('utf-8'),
                                      is_path_segment_reserved)
        return FileURL('file://%s/%s' % (host, string.join(segments, '/')))


class URIFactoryClass(PEP8Compatibility):

    def __init__(self):
        PEP8Compatibility.__init__(self)
        self.urlClass = {}

    def register(self, scheme, uri_class):
        warnings.warn(
            "URIFactory.Register is deprecated, use URI.register instead",
            DeprecationWarning,
            stacklevel=3)
        URI.register(scheme, uri_class)

    def uri(self, octets):
        warnings.warn(
            "URIFactory.URI is deprecated, use URI.from_octets instead",
            DeprecationWarning,
            stacklevel=3)
        return URI.from_octets(octets)

    def url_from_pathname(self, path):
        warnings.warn(
            "URIFactory.URLFromPathname is deprecated, "
            "use URI.from_path instead", DeprecationWarning, stacklevel=3)
        return URI.from_path(path)

    def url_from_virtual_file_path(self, path):
        warnings.warn(
            "URIFactory.URLFromVirtualFilePath is deprecated, "
            "use URI.from_virtual_path instead", DeprecationWarning,
            stacklevel=3)
        return URI.from_virtual_path(path)

    def resolve(self, b, r):
        warnings.warn(
            "URIFactory.resolve(b, r) is deprecated, "
            "use r.resolve(b) or URI.from_octets(r).resolve(b) instead",
            DeprecationWarning, stacklevel=3)
        if isinstance(r, URI):
            return r.resolve(b)
        else:
            return URI.from_octets(r).resolve(b)

    def relative(self, u, b):
        warnings.warn(
            "URIFactory.relative(u, b) is deprecated, "
            "use u.relative(b) or URI.from_octets(u).relative(b) instead",
            DeprecationWarning, stacklevel=3)
        if isinstance(u, URI):
            return u.relative(b)
        else:
            return URI.from_octets(u).relative(b)


class ServerBasedURL(URI):

    """Represents server-based URIs

    A server-based URI is one of the form::

        <scheme> '://' [<userinfo> '@'] <host> [':' <port>] <path>"""

    #: the default port for this type of URL
    DEFAULT_PORT = None

    def __init__(self, octets):
        super(ServerBasedURL, self).__init__(octets)
        self.userinfo, self.host, self.port = split_server(self.authority)

    def get_addr(self):
        """Returns a hostname and integer port tuple

        The format is suitable for socket operations.  The main purpose
        of this method is to determine if the port is set on the URL
        and, if it isn't, to return the default port for this URL type
        instead."""
        hostname = self.host
        if self.port:
            # custom port, perhaps
            port = int(self.port)
        else:
            port = self.DEFAULT_PORT
        return hostname, port

    def canonicalize(self):
        """Returns a canonical form of this URI

        In addition to returning the scheme in lower-case form, this
        method forces the host to be lower case and removes the port
        specifier if it matches the :attr:`DEFAULT_PORT` for this type
        or URI.

        No transformation is performed on the path component."""
        new_uri = []
        if self.scheme is not None:
            new_uri.append(self.scheme.lower())
            new_uri.append(':')
        if self.authority is not None:
            new_uri.append('//')
            if self.userinfo is not None:
                new_uri.append(self.userinfo)
                new_uri.append('@')
            new_uri.append(self.host.lower())
            if self.port:  # port could be an empty string
                port = int(self.port)
                if port != self.DEFAULT_PORT:
                    new_uri.append(':')
                    new_uri.append("%i" % int(self.port))
        if self.abs_path is not None:
            new_uri.append(self.abs_path)
        elif self.rel_path is not None:
            new_uri.append(self.rel_path)
        if self.query is not None:
            new_uri.append('?')
            new_uri.append(self.query)
        if self.fragment is not None:
            new_uri.append('#')
            new_uri.append(self.fragment)
        return URI.from_octets(string.join(new_uri, ''))


class FileURL(ServerBasedURL):

    """Represents the file URL scheme defined by RFC1738

    The initialisation string is optional, if omitted the URL will
    represent the root of the default file system::

        file:///"""

    def __init__(self, octets='file:///'):
        super(FileURL, self).__init__(octets)

    def get_pathname(self, force8bit=False):
        """Returns the system path name corresponding to this file URL

        If the system supports unicode file names (as reported by
        os.path.supports_unicode_filenames) then get_pathname also
        returns a unicode string, otherwise it returns an 8-bit string
        encoded in the underlying file system encoding.

        force8bit
            There are some libraries (notably sax) that will fail when
            passed files opened using unicode paths.  The force8bit flag
            can be used to force get_pathname to return a byte string
            encoded using the native file system encoding."""
        c = sys.getfilesystemencoding()
        if os.path.supports_unicode_filenames and not force8bit:
            decode = lambda s: unicode(unescape_data(s), 'utf-8')
        else:
            decode = lambda s: unicode(unescape_data(s), 'utf-8').encode(c)
        if self.host and hasattr(os.path, 'splitunc'):
            unc_root = decode('\\\\%s' % self.host)
        else:
            unc_root = decode('')
        segments = split_abs_path(self.abs_path)
        # ignore parameters in file system
        path = string.join(map(decode, segments), os.sep)
        if unc_root:
            # If we have a UNC root then we will have an absolute path
            path = string.join((unc_root, path), os.sep)
        elif not os.path.isabs(path):
            # Otherwise, prepend the sep if we're not absolute (most
            # likely UNIX) Note that drive designations do not need a
            # prefix
            path = string.join(('', path), os.sep)
        return path

    def get_virtual_file_path(self):
        """Returns a virtual file path corresponding to this URL

        The result is a :class:`pyslet.vfs.FilePath` instance.

        The host component of the URL is used to determine which virtual
        file system the file belongs to.  If there is no virtual file
        system matching the URL's host and the default virtual file
        system support UNC paths (i.e., is Windows) the host will be
        placed in the machine portion of the UNC path.

        Path parameters e.g., /dir/file;lang=en in the URL are
        ignored."""
        decode = lambda s: unicode(unescape_data(s), 'utf-8')
        if self.host:
            fs = vfs.GetFileSystemByName(self.host)
            if fs is None:
                if vfs.defaultFS.supports_unc:
                    fs = vfs.defaultNS
                    unc_root = decode('\\\\%s' % self.host)
                else:
                    raise ValueError(
                        "Unrecognized host in file URL: %s" % self.host)
            else:
                unc_root = decode('')
        else:
            fs = vfs.defaultFS
            unc_root = decode('')
        segments = split_abs_path(self.abs_path)
        # ignore parameters in file system
        path = string.join(map(decode, segments), fs.sep)
        if unc_root:
            # If we have a UNC root then we will have an absolute path
            vpath = fs(string.join((unc_root, path), fs.sep))
        else:
            vpath = fs(path)
            if not vpath.isabs():
                # Prepend the sep if we're not absolute (most likely
                # UNIX) because it is only drive designations that do
                # not need a prefix
                vpath = fs(string.join(('', path), fs.sep))
        return vpath


URI.register('file', FileURL)


def _load_uri_class(scheme):
    # we now import any other modules that define URI classes, this
    # ensures that they will be registered in the same way as FileURL is
    # registered here.
    #
    # WARNING: ideally this would be a recursive import, unfortunately
    # recursive imports don't really work across packages (for complex
    # reasons) so we wrap this functionality into a function that is
    # called only if we find a URI with a scheme we don't understand
    if scheme in ('http', 'https'):
        import http.params      # noqa
    elif scheme == ('urn'):
        import urn              # noqa
    else:
        # unknown scheme, map it to URI itself to prevent repeated
        # look-ups
        URI.register(scheme, URI)


# legacy definition
URIFactory = URIFactoryClass()
