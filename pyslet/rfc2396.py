#! /usr/bin/env python
"""This module implements the URI specification defined in RFC 2396"""

import warnings

from . import vfs

from .pep8 import old_function, PEP8Compatibility
from .py2 import (
    byte,
    byte_value,
    character,
    CmpMixin,
    is_text,
    is_unicode,
    join_bytes,
    py2,
    range3,
    to_text,
    uempty,
    ul)
from .unicode5 import CharClass


class URIException(Exception):

    """Base class for URI-related exceptions"""
    pass


class URIRelativeError(URIException):

    """Exceptions raised while resolve relative URI"""
    pass


path_sep = ul('/')
"""Constant for "/" character."""

upalpha = CharClass(('A', 'Z'))
is_upalpha = upalpha.test

lowalpha = CharClass(('a', 'z'))
is_lowalpha = lowalpha.test

alpha = CharClass(upalpha, lowalpha)
is_alpha = alpha.test

digit = CharClass(('0', '9'))
is_digit = digit.test

alphanum = CharClass(upalpha, lowalpha, digit)
is_alphanum = alphanum.test

reserved_1738 = CharClass(";/?:@&=")
is_reserved_1738 = reserved_1738.test

reserved_2396 = CharClass(";/?:@&=+$,")
is_reserved_2396 = reserved_2396.test

reserved = CharClass(";/?:@&=+$,[]")
is_reserved = reserved.test

safe_1738 = CharClass("$-_.+")
is_safe_1738 = safe_1738.test

extra_1738 = CharClass("!*'(),")
is_extra_1738 = extra_1738.test

unreserved_1738 = CharClass(alphanum, safe_1738, extra_1738)
is_unreserved_1738 = unreserved_1738.test

mark = CharClass("-_.!~*'()")
is_mark = mark.test

unreserved = CharClass(alphanum, mark)
is_unreserved = unreserved.test

allowed_1738 = CharClass(reserved_1738, unreserved_1738)
is_allowed_1738 = allowed_1738.test

allowed_2396 = CharClass(reserved_2396, unreserved)
is_allowed_2396 = allowed_2396.test

allowed = CharClass(reserved, unreserved)
is_allowed = allowed.test

hex_char = CharClass(digit, ('a', 'f'), ('A', 'F'))
is_hex = hex_char.test

control = CharClass((character(0), character(0x1f)), character(0x7f))
is_control = control.test


def is_space(c):
    """Tests production: space"""
    return c is not None and ord(c) == 0x20

delims = CharClass('<>#%"')
is_delims = delims.test

unwise_2396 = CharClass("{}|\^[]`")
is_unwise_2396 = unwise_2396.test

unwise = CharClass("{}|\^`")
is_unwise = unwise.test

scheme_char = CharClass(alphanum, "+-.")
_is_scheme_char = scheme_char.test

authority_reserved = CharClass(";:@?/")
is_authority_reserved = authority_reserved.test


@old_function('ParseURIC')
def parse_uric(source, pos=0, allowed_test=is_allowed):
    """Returns the number of URI characters in a source string

    source
        A source string (of characters)

    pos
        The place at which to start parsing (defaults to 0)

    allowed_test
        Defaults to :func:`is_allowed`

        Test function indicating if a character is allowed unencoded in
        a URI.  For stricter RFC2396 compliant parsing you may also pass
        :func:`is_allowed_2396` or :func:`is_allowed_1738`.

        For information, RFC2396 added "~" to the range of allowed
        characters and RFC2732 added "[" and "]" to support IPv6
        literals.

    This function can be used to scan a string of characters for a
    URI, for example::

        x = "http://www.pyslet.org/ is great"
        url = x[:parse_uric(x, 0)]

    It does not check the validity of the URI against the specification.
    The purpose is to allow a URI to be extracted from some source text.
    It assumes that all characters that must be encoded in URI *are*
    encoded, so characters outside the ASCII character set automatically
    terminate the URI as do any unescaped characters outside the allowed
    set (defined by the *allowed_test*).  See :func:`encode_unicode_uri`
    for details of how to create an appropriate source string in
    contexts where non-ASCII characters may be present."""
    uric = 0
    mode = None
    while pos < len(source):
        c = source[pos]
        pos += 1
        if mode is None:
            if allowed_test(c):
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


def _parse_scheme(octets):
    pos = 0
    scheme = None
    while pos < len(octets):
        c = octets[pos]
        if (pos and _is_scheme_char(c)) or is_alpha(c):
            pos += 1
        else:
            if ord(c) == 0x3A:
                # we have the scheme
                scheme = octets[0:pos]
            break
    return scheme


@old_function('CanonicalizeData')
def canonicalize_data(source, unreserved_test=is_unreserved,
                      allowed_test=is_allowed):
    """Returns the canonical form of *source* string.

    The canonical form is the same string but any unreserved characters
    represented as hex escapes in source are unencoded and any unescaped
    characters that are neither reserved nor unreserved are escaped.

    source
        A string of characters.  Characters must be in the US ASCII
        range.  Use :func:`encode_unicode_uri` first if necessary. Will
        raise UnicodeEncodeError if non-ASCII characters are encountered.

    unreserved_test
        A function with the same signature as :func:`is_unreserved`,
        which it defaults to.  By providing a different function you can
        control which characters will have their escapes removed.  It
        does not affect which unescaped characters are escaped.

        To give an example, by default the '.' is unreserved so the
        sequence %2E will be removed when canonicalizing the source.
        However, if the specific part of the URL scheme you are dealing
        with applies some reserved purpose to '.' then *source* may
        contain both encoded and unencoded versions to disambiguate its
        usage.  In this case you would want to remove '.' from the
        definition of unreserved to prevent it being unescaped.

        If you don't want any escapes removed, simply pass::

            lambda x: False

    allowed_test
        Defaults to :func:`is_allowed`

        See :func:`parse_uric` for more information.

    All hex escapes are promoted to upper case."""
    result = []
    pos = 0
    # force a unicode encoding error if necessary
    source.encode('ascii')
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
        elif not allowed_test(c):
            result.append("%%%02X" % ord(c))
            pos += 1
        else:
            result.append(c)
            pos += 1
    return ''.join(result)


@old_function('EscapeData')
def escape_data(source, reserved_test=is_reserved, allowed_test=is_allowed):
    """Performs URI escaping on source

    Returns the escaped *character* string.

    source
        The input string.  This can be a binary or character string. For
        character strings all characters must be in the US ASCII range.
        Use :func:`encode_unicode_uri` first if necessary. Will raise
        UnicodeEncodeError if non-ASCII characters are encountered. For
        binary strings there is no constraint on the range of allowable
        octets.

        ..  note::
            In Python 2 the ASCII character constraint is only applied
            when *source* is of type unicode.

    reserved_test
        Default :func:`is_reserved`, the function to test if a character
        should be escaped.  This function should take a single character
        as an argument and return True if the character must be escaped.
        Characters for which this function returns False will still be
        escaped if they are not allowed to appear unescaped in URI (see
        *allowed_test* below).

        Quoting from RFC2396:

            Characters in the "reserved" set are not reserved in all
            contexts. The set of characters actually reserved within any
            given URI component is defined by that component. In
            general, a character is reserved if the semantics of the URI
            changes if the character is replaced with its escaped
            US-ASCII encoding.

        Therefore, you may want to reduce the set of characters that are
        escaped based on the target component for the data.  Different
        rules apply to a path component compared with, for example, the
        query string.  A number of alternative test functions are
        provided to assist with escaping an alternative set of
        characters.

        For example, suppose you want to ensure that your data is
        escaped to the rules of the earlier RFC1738.  In that
        specification, a fore-runner of RFC2396, the "~" was not
        classifed as a valid URL character and required escaping.  It
        was later added to the mark category enabling it to appear
        unescaped.  To ensure that this character is escaped for
        compatibility with older systems you might do this when escaping
        data with a path component (where '~' is often used)::

            path_component = uri.escape_data(
                dir_name, reserved_test=uri.is_reserved_1738)

        In addition to escaping "~", the above will also leave "$", "+"
        and "," unescaped as they were classified as 'extra' characters
        in RFC1738 and were not reserved.

    allowed_test
        Defaults to :func:`is_allowed`

        See :func:`parse_uric` for more information.

        By default there is no difference between RFC2396 and RFC2732 in
        operation as in RFC2732 "[" and "]" are legal URI characters
        *but* they are also in the default reserved set so will be
        escaped anyway.  In RFC2396 they were escaped on the basis of
        not being allowed.

        The difference comes if you are using a reduced set of reserved
        characters.  For example::

            >>> print uri.escape_data("[file].txt")
            %5Bfile%5D.txt
            >>> print uri.escape_data(
                    "[file].txt", reserved_test=uri.is_path_segment_reserved)
            [file].txt
            >>> print uri.escape_data(
                    "[file].txt", reserved_test=uri.is_path_segment_reserved,
                    allowed_test=uri.is_allowed_2396)
            %5Bfile%5D.txt"""
    # force a unicode encoding error if necessary
    if is_unicode(source):
        source = source.encode('ascii')
    result = []
    for b in source:
        # b is a byte value but our tests are character tests
        c = character(b)
        if reserved_test(c) or not allowed_test(c):
            result.append("%%%02X" % ord(c))
        else:
            result.append(c)
    return ''.join(result)


@old_function('UnescapeData')
def unescape_data(source):
    """Performs URI unescaping

    source
        The URI-encoded string

    Removes escape sequences.  The string is returned as a *binary*
    string of octets, not a string of characters. Escape sequences such
    as %E9 will result in the byte value 233 and not the character \xe9.

    The character encoding that applies may depend on the context and it
    cannot always be assumed to be UTF-8 (though in most cases that will
    be the correct way to interpret the result)."""
    data = []
    mode = None
    pos = 0
    source.encode('ascii')
    while pos < len(source):
        c = source[pos]
        pos += 1
        if mode is None:
            if ord(c) == 0x25:
                mode = '%'
            else:
                data.append(byte(c))
        elif mode == '%':
            if is_hex(c):
                mode = c
            else:
                data.append(byte('%'))
                data.append(byte(c))
                mode = None
        else:
            if is_hex(c):
                data.append(byte(int(mode + c, 16)))
            else:
                data.append(byte('%'))
                data.append(byte(mode))
                data.append(byte(c))
            mode = None
    return join_bytes(data)


def split_server(authority):
    """Splits an authority component

    authority
        A character string containing the authority component of a URI.

    Returns a triple of::

        (userinfo, host, port)

    There is no parsing of the individual components which may or may
    not be syntactically valid according to the specification.  The
    userinfo is defined as anything up to the "@" symbol or None if
    there is no "@".  The port is defined as any digit-string (possibly
    empty) after the last ":" character or None if there is no ":" or if
    there is non-empty string containing anything other than a digit
    after the last ":".

    The return values are always character strings (or None).  There is
    no unescaping or other parsing of the values."""
    if authority is None:
        return None, None, None
    ulen = authority.find('@')
    if ulen < 0:
        userinfo = None
        hstart = 0
    else:
        userinfo = authority[:ulen]
        hstart = ulen + 1
    # the port will be on the right hand side, after a colon
    plen = authority.rfind(':')
    if plen < ulen:
        # not found, or in userinfo
        plen = -1
    if plen > -1:
        # possible port
        hstop = plen
        port = authority[plen + 1:]
        for pchar in port:
            if not is_digit(pchar):
                plen = -1
                break
    if plen > -1:
        hstop = plen
    else:
        port = None
        hstop = len(authority)
    # everything else is the host
    host = authority[hstart:hstop]
    return userinfo, host, port


path_segment_reserved = CharClass("/;=?")
is_path_segment_reserved = path_segment_reserved.test


def split_path(path, abs_path=True):
    """Splits a URI-encoded path into path segments

    path
        A character string containing the path component of a URI. If
        path is None we treat as for an empty string.

    abs_path
        A flag (defaults to True) indicating whether or not the
        path is relative or absolute.  This flag only affects
        the handling of the empty path.  An empty absolute path
        is treated as if it were '/' and returns a list containing
        a single empty path segment whereas an empty relative
        path returns a list with no path segments, in other words,
        an empty list.

    The return result is always a list of character strings split from
    *path*.  It will only end in an empty path segment if the path ends
    with a slash."""
    if path:
        if abs_path:
            if ord(path[0]) != 0x2F:
                raise ValueError("Abs path must be empty or start with /")
            return path.split("/")[1:]
        else:
            return path.split("/")
    elif not abs_path:
        # relative paths always have an empty segment
        return ['']
    else:
        return []


split_abs_path = split_path
"""Provided for backwards compatibility

Equivalent to::

    split_path(abs_path, True)"""


def split_rel_path(rel_path):
    """Provided for backwards compatibility

    Equivalent to::

        split_path(abs_path, False)"""
    return split_path(rel_path, False)


@old_function('NormalizeSegments')
def normalize_segments(path_segments):
    """Normalizes a list of path_segments

    path_segments
        A list of character strings representing path segments, for
        example, as returned by :func:`split_path`.

    Normalizing follows the rules for resolving relative URI paths, './'
    and trailing '.' are removed, 'seg/../' and trailing seg/.. are also
    removed."""
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


def _relativize_segments(path_segments, base_segments):
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


def _make_rel_path_abs(abs_path, base_path):
    """Return abs_path relative to base_path"""
    path_segments = split_abs_path(abs_path)
    normalize_segments(path_segments)
    base_segments = split_abs_path(base_path)
    normalize_segments(base_segments)
    result = _relativize_segments(path_segments, base_segments)
    return path_sep.join(result)


def _make_rel_path_rel(rel_path, base_rel_path):
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
        # e.g., c/d relative to ../a/b - not allowed
        # there is no R such that c/d = ../a/b [*] R
        raise URIRelativeError("%s [/] %s" % (rel_path, base_rel_path))
    if i:
        # we have leading '..' components, add a common path prefix and
        # re-normalize
        path_segments = ['x'] * i + path_segments
        normalize_segments(path_segments)
        base_segments = ['x'] * i + base_segments
        normalize_segments(base_segments)
    result = _relativize_segments(path_segments, base_segments)
    return path_sep.join(result)


def split_path_segment(segment):
    params = segment.split(';')
    return params[0], params[1:]


query_reserved = CharClass(";/?:@&=+,$")


@old_function('IsQueryReserved')
def is_query_reserved(c):
    return query_reserved.test(c)

is_query_reserved = query_reserved.test     # noqa (old_function in use)


@old_function('EncodeUnicodeURI')
def encode_unicode_uri(usrc):
    """Extracts a URI octet-string from a unicode string.

    usrc
        A character string

    Returns a character string with any characters outside the US-ASCII
    range replaced by URI-escaped UTF-8 sequences.  This is not a
    general escaping method.  All other characters are ignored,
    including non-URI characters like space.  It is assumed that any
    (other) characters requiring escaping are already escaped.

    The encoding algorithm used is the same as the one adopted by HTML.
    This is not part of the RFC standard which only defines the
    behaviour for streams of octets but it is in line with the approach
    adopted by the later IRI spec."""
    octets = []
    for c in usrc:
        if ord(c) > 0x7F:
            octets = octets + list(map(lambda x: "%%%2X" %
                                       byte_value(x), c.encode('UTF-8')))
        else:
            octets.append(chr(ord(c)))
    return uempty.join(octets)


class URI(CmpMixin, PEP8Compatibility):

    r"""Class to represent URI References

    You won't normally instantiate a URI directly as it represents a
    generic URI.  This class is designed to be overridden by
    scheme-specific implementations.  Use the class method
    :meth:`from_octets` to create instances.

    If you are creating your own derived classes call the parent
    contstructor to populate the attributes defined here from the URI's
    string representation passing a character string representing the
    octets of the URI.  (For backwards compatibility a binary string
    will be accepted provided it can be decoded as US ASCII characters.)
    You can override the scheme-specific part of the parsing by defining
    your own implementation of :meth:`parse_scheme_specific_part`.

    It is an error if the octets string contains characters that are not
    allowed in a URI.

    ..  note::

        The following details have changed significantly following
        updates in 0.5.20160123 to introduce support for Python 3.
        Although the character/byte/octet descriptions have changed the
        actual affect on running code is minimal when running under
        Python 2.

    Unless otherwise stated, all attributes are character strings that
    encode the 'octets' in each component of the URI.  These atrributes
    retain the %-escaping.  To obtain the actual data use
    :func:`unescape_data` to obtain the original octets (as a byte
    string).  The specification does not specify any particular encoding
    for interpreting these octets, indeed in some types of URI these
    binary components may have no character-based interpretation.

    For example, the URI "%E8%8B%B1%E5%9B%BD.xml" is a character string
    that represents a UTF-8 and URL-encoded path
    segment using the Chinese word for United Kingdom.  To obtain the
    correct unicode path segment you would first use
    :func:`unescape_data` to obtain the binary string of bytes and then
    decode with UTF-8::

        >>> src = "%E8%8B%B1%E5%9B%BD.xml"
        >>> uri.unescape_data(src).decode('utf-8')
        u'\\u82f1\\u56fd.xml'

    URI can be converted to strings but the result is a character
    string that retains any %-encoding.  Therefore, these character
    strings always use the restricted character set defined by the
    specification (a subset of US ASCII) and, in Python 2, can be freely
    converted between the str and unicode types.

    URI are immutable and can be compared and used as keys in
    dictionaries.  Two URI compare equal if their *canonical* forms
    are identical.  See :meth:`canonicalize` for more information."""

    @classmethod
    def from_octets(cls, octets, strict=False):
        """Creates an instance of :class:`URI` from a string

        ..  note::

            This method was changed in Pyslet 0.5.20160123 to introduce
            support for Python 3. It now takes either type of string but
            a character string is now *preferred*.

        This is the main method you should use for creating instances.
        It uses the URI's scheme to determine the appropriate subclass
        to create.  See :meth:`register` for more information.

        octets
            A string of characters that represents the URI's octets.  If
            a binary string is passed it is assumed to be US ASCII and
            converted to a character string.

        strict (defaults to False)
            If the character string contains characters outside of the
            US ASCII character range then :func:`encode_unicode_uri` is
            called before the string is used to create the instance.
            You can turn off this behaviour (to enable strict
            URI-parsing) by passing strict=True

        Pyslet manages the importing and registering of the following
        URI schemes using it's own classes: http, https, file and urn.
        Additional modules are loaded and schemes registered 'on demand'
        when instances of the corresponding URI are first created."""
        if is_unicode(octets):
            if not strict:
                octets = encode_unicode_uri(octets)
        else:
            octets = octets.decode('ascii')
        scheme = _parse_scheme(octets)
        if scheme is not None:
            scheme = scheme.lower()
            c = cls.scheme_class.get(scheme, None)
            if c is None:
                _load_uri_class(scheme)
                c = cls.scheme_class.get(scheme, URI)
        else:
            c = URI
        return c(octets)

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
        replaced.  The mapping is kept in the :attr:`scheme_class`
        dictionary."""
        cls.scheme_class[scheme.lower()] = uri_class

    @classmethod
    def from_virtual_path(cls, path):
        """Converts a virtual file path into a :class:`URI` instance

        path
            A :class:`pyslet.vfs.VirtualFilePath` instance representing
            a file path in a virtual file system.  The path is always
            made absolute before being converted to a :class:`FileURL`.

        The authority (host name) in the resulting URL is usually left
        blank except when running under Windows, in which case the URL
        is constructed according to the recommendations in this `blog
        post`__.  In other words, UNC paths are mapped to both the
        network location and path components of the resulting file URL.

        ..  __:
            http://blogs.msdn.com/b/ie/archive/2006/12/06/file-uris-in-windows.aspx

        For named virtual file systems (i.e., those that don't map
        directly to the functions in Python's built-in os and os.path
        modules) the file system name is used for the authority.  (If
        path is from a named virutal file system and is a UNC path then
        URIException is raised.)"""
        host = path.fs_name
        segments = []
        dirlike = path.is_dirlike()
        # check if the resulting URL should end in a slash, abspath will
        # normalise away this distinction
        path = path.abspath()
        drive, head = path.splitdrive()
        unc_flag = path.is_unc()
        while head:
            new_head, tail = head.split()
            if new_head == head:
                # We are unable to split any more from head
                if unc_flag and segments:
                    # This is the unusual case of the UNC path, first
                    # segment is machine
                    if host:
                        raise URIException("UNC hosts cannot be specified in "
                                           "named file systems.")
                    host = str(segments[0])
                    del segments[0]
                break
            else:
                segments[0:0] = [tail]
                head = new_head
        if drive:
            segments[0:0] = [drive]
        if dirlike:
            # add back the trailing slash with an empty path
            segments.append(path.empty)
        # At this point we need to convert to octets
        if host:
            host = escape_data(host, is_authority_reserved)
        for i in range3(len(segments)):
            # hard decision, should we use UTF-8 or the native file
            # system encoding?  We go with UTF-8 as this enables
            # relative URI to work portably between all systems,
            # regardless of whether the resources are hosted on an http
            # server or stored locally in the file system. This means
            # that our file URLs won't work on Windows which expects the
            # native encoding.  IRIs would solve the problem but we're
            # using RFC2396 here.
            s = to_text(segments[i]).encode('utf-8')
            segments[i] = escape_data(s, is_path_segment_reserved)
        return FileURL(ul('file://%s/%s') % (host, path_sep.join(segments)))

    @classmethod
    def from_path(cls, path):
        """Converts a local file path into a :class:`URI` instance.

        path
            A file path string.

        Uses *path* to create an instance of :class:`pyslet.vfs.OSFilePath`,
        see :meth:`from_virtual_path` for more info."""
        return cls.from_virtual_path(vfs.OSFilePath(path))

    def __init__(self, octets):
        PEP8Compatibility.__init__(self)
        if isinstance(octets, bytes):
            octets = octets.decode('ascii')
        self._canonical_octets = None
        uri_len = parse_uric(octets)
        #: The character string representing this URI's octets
        self.octets = octets[0:uri_len]
        #: The fragment string that was appended to the URI or None if
        #: no fragment was given.
        self.fragment = None
        if uri_len < len(octets):
            if ord(octets[uri_len]) == 0x23:
                frag_start = uri_len + 1
                frag_len = parse_uric(octets, frag_start)
                self.fragment = octets[frag_start:frag_start + frag_len]
                uri_len = frag_start + frag_len
        if uri_len < len(octets):
            raise URIException("URI incompletely parsed from octets: %s" %
                               octets[:uri_len])
        #: The URI scheme, if present
        self.scheme = _parse_scheme(self.octets)
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
            self._parse_relative_uri()

    if py2:
        def __str__(self):      # noqa
            return self.__unicode__().encode('ascii')
    else:
        def __str__(self):      # noqa
            return self.__unicode__()

    def __unicode__(self):
        if self.fragment is not None:
            return self.octets + '#' + self.fragment
        else:
            return self.octets

    def __hash__(self):
        return hash(self._pre_cmp(None))

    def _pre_cmp(self, other):
        if self._canonical_octets is None:
            self._canonical_octets = str(self.canonicalize())
        if other is not None:
            if not isinstance(other, URI):
                other = URI.from_octets(other)
            if other._canonical_octets is None:
                other._canonical_octets = str(other.canonicalize())
            return self._canonical_octets, other._canonical_octets
        else:
            return self._canonical_octets, None

    def __eq__(self, other):
        a, b = self._pre_cmp(other)
        return a == b

    def __lt__(self, other):
        a, b = self._pre_cmp(other)
        return a < b

    def __gt__(self, other):
        a, b = self._pre_cmp(other)
        return a > b

    def __le__(self, other):
        a, b = self._pre_cmp(other)
        return a <= b

    def __ge__(self, other):
        a, b = self._pre_cmp(other)
        return a >= b

    def parse_scheme_specific_part(self):
        """Parses the scheme specific part of the URI

        Parses the scheme specific part of the URI from
        :attr:`scheme_specific_part`. This attribute is set by the
        constructor, the role of this method is to parse this attribute
        and set any scheme-specific attribute values.

        This method should overridden by derived classes if they use a
        format other than the hierarchical URI format described in
        RFC2396.

        The default implementation implements the generic parsing of
        hierarchical URI setting the following attribute values:
        :attr:`authority`, :attr:`abs_path` and :attr:`query`.  If the
        URI is not of a hierarchical type then :attr:`opaque_part` is
        set instead.  Unset attributes have the value None."""
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

    def _parse_relative_uri(self):
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
        return URI.from_octets(''.join(new_uri))

    def get_canonical_root(self):
        """Returns a new URI comprised of the scheme and authority only.

        Only valid for absolute URI, returns None otherwise.

        The canonical root does not include a trailing slash.  The
        canonical root is used to define the domain of a resource, often
        for security purposes.

        If the URI is non-hierarchical then the just the scheme is
        returned."""
        if self.is_absolute():
            canonical_uri = self.canonicalize()
            result = [canonical_uri.scheme, ':']
            if canonical_uri.authority is not None:
                result.append('//')
                result.append(canonical_uri.authority)
            return URI.from_octets(''.join(result))
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
        actually go into the procedure for combining relative URI but
        if B is an absolute URI and R1 and R2 are relative URI then
        using the resolve operator ([*], see above)::

                U1 = B [*] R1
                U2 = U1 [*] R2
                U2 = ( B [*] R1 ) [*] R2

        The last expression prompts the issue of associativity, in other
        words, is the following expression also valid? ::

                U2 = B [*] ( R1 [*] R2 )

        For this to work it must be possible to use the resolve operator
        to combine two relative URI to make a third, which is what we
        allow here."""
        if is_text(base):
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
                    abs_path = '/' + '/'.join(segments)
                    rel_path = None
                else:
                    segments = split_rel_path(base.rel_path)[:-1]
                    segments = segments + split_rel_path(self.rel_path)
                    normalize_segments(segments)
                    abs_path = None
                    rel_path = '/'.join(segments)
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
        return URI.from_octets(''.join(result))

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

        There are some significant restrictions, URI are classified by
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
        if is_text(base):
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
                    rel_path = _make_rel_path_rel(self.rel_path, base.rel_path)
            elif base.abs_path is None:
                return URI.from_octets(str(self))
            else:
                # two absolute paths, calculate self relative to base
                abs_path = None
                rel_path = _make_rel_path_abs(self.abs_path, base.abs_path)
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
        return URI.from_octets(''.join(result))

    def match(self, other_uri):
        """Compares this URI with another

        other_uri
            Another URI instance.

        Returns True if the canonical representations of the URIs
        match."""
        return str(self.canonicalize()) == str(other_uri.canonicalize())

    def is_absolute(self):
        """Returns True if this URI is absolute

        An absolute URI is fully specified with a scheme, e.g., 'http'."""
        return self.scheme is not None

    def get_file_name(self):
        """Gets the file name associated with this resource

        Returns None if the URI scheme does not have the concept.  By
        default the file name is extracted from the last component of
        the path. Note the subtle difference between returning None and
        returning an empty string (indicating that the URI represents a
        directory-like object).

        The return result is always a character string."""
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
            file_name = unescape_data(file_name).decode('utf-8')
            return file_name
        else:
            return None


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

    """Represents server-based URI

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
        return URI.from_octets(''.join(new_uri))


class FileURL(ServerBasedURL):

    """Represents the file URL scheme defined by RFC1738

    Do not create instances directly, instead use (for example)::

        furl = URI.from_octets('file:///...')"""

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
            encoded using the native file system encoding.

        If the URL does not represent a path in the native file system
        then URIException is raised."""
        path = self.get_virtual_file_path()
        if isinstance(path, vfs.OSFilePath):
            if force8bit:
                return path.to_bytes()
            else:
                return path.path
        else:
            # this resource is not in the local file system
            raise URIException("Non local file path")

    def get_virtual_file_path(self):
        """Returns a virtual file path corresponding to this URL

        The result is a :class:`pyslet.vfs.FilePath` instance.

        The host component of the URL is used to determine which virtual
        file system the file belongs to.  If there is no virtual file
        system matching the URL's host and the native file system
        support UNC paths (i.e., is Windows) the host will be placed in
        the machine portion of the UNC path.

        Path parameters e.g., /dir/file;lang=en in the URL are
        ignored."""
        fs, unc_root = self._get_fs()
        segments = split_abs_path(self.abs_path)
        # ignore parameters in file system
        path = fs.sep.join(
            map(lambda s: fs.path_str(self._decode(s)), segments))
        if unc_root:
            # If we have a UNC root then we will have an absolute path
            vpath = fs(fs.sep.join((unc_root, path)))
        else:
            vpath = fs(path)
            if not vpath.isabs():
                # Prepend the sep if we're not absolute (most likely
                # UNIX) because it is only drive designations that do
                # not need a prefix
                vpath = fs(fs.sep.join((fs.empty, path)))
        return vpath

    def to_local_text(self):
        """Returns a locally portable version of the URL

        The result is a character string, not a URI instance.

        In Pyslet, all hiearchical URI are treated as using the UTF-8
        encoding for characters outside US ASCII.  As a result, file URL
        are expressed using percent-encoded UTF-8 multi-byte sequences.
        When converting these URLs to file paths the difference is taken
        into account correctly but if you attempt to output a URL
        generated by Pyslet and use it in another application you may
        find that the URL is not recognised.  This is paritcularly a
        problem on Windows where file URLs are expected to be encoded
        with the native file system encoding.

        The purpose of this method is to return a version of the URL
        re-encoded in the local file system encoding for portability
        such as being copy-pasted into a browser address bar."""
        fs, unc_root = self._get_fs()
        if fs.codec == 'utf-8':
            return self
        else:
            segments = split_abs_path(self.abs_path)
            for i in range3(len(segments)):
                segments[i] = escape_data(unescape_data(
                    segments[i]).decode('utf-8').encode(fs.codec))
            return ul("file://%s/%s") % (self.host, ul("/").join(segments))

    def _get_fs(self):
        # returns a tuple of file system and unc_root path
        if self.host:
            fs = vfs.get_file_system_by_name(self.host)
            if fs is None:
                if vfs.OSFilePath.supports_unc:
                    fs = vfs.OSFilePath
                    unc_root = self._decode('\\\\%s' % self.host)
                else:
                    raise ValueError(
                        "Unrecognized host in file URL: %s" % self.host)
            else:
                unc_root = self._decode('')
        else:
            fs = vfs.OSFilePath
            unc_root = self._decode('')
        return fs, unc_root

    def _decode(self, utext):
        return unescape_data(utext).decode('utf-8')


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
        import pyslet.http.params      # noqa
    elif scheme == ('urn'):
        import pyslet.urn              # noqa
    else:
        # unknown scheme, map it to URI itself to prevent repeated
        # look-ups
        URI.register(scheme, URI)


# legacy definition
URIFactory = URIFactoryClass()
