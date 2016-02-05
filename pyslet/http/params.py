#! /usr/bin/env python

import pyslet.iso8601 as iso
import pyslet.rfc2396 as uri

from pyslet.py2 import py2, range3, dict_items, SortableMixin, is_string
from pyslet.py2 import byte, join_bytes, is_unicode, force_bytes

from pyslet.unicode5 import BasicParser

from pyslet.http.grammar import WordParser, COMMA, is_digits, quote_string
from pyslet.http.grammar import format_parameters


class Parameter(object):
    """Abstract base class for HTTP Parameters

    Provides conversion to strings based on the :meth:`to_bytes` method.
    In Python 2, also provides conversion to the unicode string type.

    The HTTP grammar and the parsers and classes that implement it all
    use binary strings but usage of byte values outside those of the US
    ASCII codepoints is discouraged and unlikely to be portable between
    systems.

    When required, Pyslet converts to character strings using the
    ISO-8859-1 (or latin-1) codec.  This ensures that the conversions
    never generate unicode decoding erros and is consistent with the
    text of RFC2616."""

    @classmethod
    def bstr(cls, arg):
        """Returns arg as a binary string"""
        if is_unicode(arg):
            return arg.encode('latin1')
        else:
            return arg

    @classmethod
    def bparameters(cls, parameters):
        """Returns a new dict of binary strings"""
        result = {}
        for k, v in dict_items(parameters):
            if is_unicode(k):
                k = k.encode('latin1')
            n, v = v
            if is_unicode(n):
                n = n.encode('latin1')
            if is_unicode(v):
                v = v.encode('latin1')
            result[k] = (n, v)
        return result

    def to_bytes(self):
        """Returns a binary string representation of the parameter

        This method should be used in preference to str for
        compatibility with Python 3."""
        raise NotImplemented

    if py2:
        def __str__(self):  # noqa
            return self.to_bytes()

        def __unicode__(self):  # noqa
            return self.to_bytes().decode('latin1')
    else:
        def __str__(self):  # noqa
            return self.to_bytes().decode('latin1')


class HTTPVersion(SortableMixin, Parameter):
    """Represents the HTTP Version.

    major
        The (optional) major version as an int

    minor
        The (optional) minor version as an int

    The default instance, HTTPVersion(), represents HTTP/1.1

    HTTPVersion objects are sortable (such that 1.1 > 1.0 and  1.2 <
    1.25).

    On conversion to a string the output is of the form::

            HTTP/<major>.<minor>

    For convenience, the constants HTTP_1p1 and HTTP_1p0 are provided
    for comparisons, e.g.::

        if HTTPVersion.from_str(version_str) < HTTP_1p1:
            # do something to support a legacy system..."""

    def __init__(self, major=1, minor=None):
        #: major protocol version (read only)
        self.major = major
        #: minor protocol version (read only)
        self.minor = minor
        if minor is None:
            self.minor = 1 if major == 1 else 0

    @classmethod
    def from_str(cls, source):
        """Constructs an :py:class:`HTTPVersion` object from a string."""
        wp = ParameterParser(source)
        result = wp.require_http_version()
        wp.require_end("HTTP version")
        return result

    def to_bytes(self):
        return b"HTTP/%i.%i" % (self.major, self.minor)

    def sortkey(self):
        return (self.major, self.minor)

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


#: A constant representing HTTP/1.1
HTTP_1p1 = HTTPVersion(1, 1)

#: A constant representing HTTP/1.0
HTTP_1p0 = HTTPVersion(1, 0)


class HTTPURL(uri.ServerBasedURL):
    """Represents http URLs"""

    #: the default HTTP port
    DEFAULT_PORT = 80

    def __init__(self, octets=b'http://localhost/'):
        super(HTTPURL, self).__init__(octets)

    def canonicalize(self):
        """Returns a canonical form of this URI

        This method is almost identical to the implementation in
        :class:`~pyslet.rfc2396.ServerBasedURL` except that a
        missing path is replaced by '/' in keeping with rules for making
        HTTP requests."""
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
            if not self.abs_path:
                new_uri.append("/")
            else:
                new_uri.append(uri.canonicalize_data(self.abs_path))
        elif self.rel_path is not None:
            new_uri.append(uri.canonicalize_data(self.rel_path))
        if self.query is not None:
            new_uri.append('?')
            new_uri.append(uri.canonicalize_data(self.query))
        if self.fragment is not None:
            new_uri.append('#')
            new_uri.append(self.fragment)
        return uri.URI.from_octets(''.join(new_uri))


uri.URI.register('http', HTTPURL)


class HTTPSURL(HTTPURL):
    """Represents https URLs"""

    #: the default HTTPS port
    DEFAULT_PORT = 443

    def __init__(self, octets=b'https://localhost/'):
        super(HTTPSURL, self).__init__(octets)


uri.URI.register('https', HTTPSURL)


class FullDate(Parameter, iso.TimePoint):
    """A special sub-class for HTTP-formatted dates

    We extend the basic ISO :class:`~pyslet.iso8601.TimePoint`,
    mixing in the :class:`Parameter` base class and providing an
    implementation of to_bytes.

    The effect is to change the way instances are formatted while
    retaining other timepoint features, including comparisons. Take care
    not to pass an instance as an argument where a plain TimePoint is
    expected as unexpected formatting errors could result.  You can
    always wrap an instance to convert between the two types::

        >>> from pyslet.iso8601 import TimePoint
        >>> from pyslet.http.params import FullDate
        >>> eagle = TimePoint.from_str('1969-07-20T15:17:40-05:00')
        >>> print eagle
        1969-07-20T15:17:40-05:00
        >>> eagle = FullDate(eagle)
        >>> print eagle
        Sun, 20 Jul 1969 20:17:40 GMT
        >>> eagle = TimePoint(eagle)
        >>> print eagle
        1969-07-20T15:17:40-05:00

    Notice that when formatting the date is *always* expressed in GMT as
    per the recommendation in the HTTP specification."""

    @classmethod
    def from_http_str(cls, source):
        """Returns an instance parsed from an HTTP formatted string

        There are three supported formats as described in the
        specification::

            "Sun, 06 Nov 1994 08:49:37 GMT"
            "Sunday, 06-Nov-94 08:49:37 GMT"
            "Sun Nov  6 08:49:37 1994"
        """
        wp = ParameterParser(source)
        tp = wp.require_fulldate()
        wp.parse_sp()
        wp.require_end("full date")
        return tp

    def to_bytes(self):
        """Formats the instance according to RFC 1123

        The format is as follows::

            Sun, 06 Nov 1994 08:49:37 GMT

        This format is also described in in RFC2616 in the production
        rfc1123-date."""
        z = self.shift_zone(0)
        (century, year, month, day,
         hour, minute, second) = z.get_calendar_time_point()
        century, decade, dyear, week, dayofweek = z.date.get_week_day()
        return b"%s, %02i %s %04i %02i:%02i:%02i GMT" % (
            ParameterParser.wkday[dayofweek - 1],
            day,
            ParameterParser.month[month - 1],
            century * 100 + year,
            hour, minute, second)


class TransferEncoding(SortableMixin, Parameter):
    """Represents an HTTP transfer-encoding.

    token
        The transfer encoding identifier, defaults to "chunked"

    parameters
        A parameter dictionary mapping parameter names to tuples
        of strings: (parameter name, parameter value)

    When sorted, the order in which parameters were parsed is ignored.
    Instances are supported first by token and then by alphabetical
    parameter name, value pairs."""

    def __init__(self, token=b"chunked", parameters={}):
        token = self.bstr(token).lower()
        if token == b"chunked":
            #: the lower-cased transfer-encoding token (defaults to "chunked")
            self.token = b"chunked"
            #: declared extension parameters
            self.parameters = {}
        else:
            self.token = token
            if parameters:
                self.parameters = self.bparameters(parameters)
            else:
                self.parameters = {}
        self._hp = sorted((p[0], p[1][1]) for p in dict_items(self.parameters))
        self._hp = tuple(self._hp)

    @classmethod
    def from_str(cls, source):
        """Parses the transfer-encoding from a *source* string.

        If the encoding is not parsed correctly BadSyntax is raised."""
        p = ParameterParser(source)
        te = p.require_transfer_encoding()
        p.require_end("transfer-encoding")
        return te

    @classmethod
    def list_from_str(cls, source):
        """Creates a list of transfer-encodings from a string

        Transfer-encodings are comma-separated"""
        telist = []
        p = ParameterParser(source)
        p.parse_sp()
        while p.the_word is not None:
            if p.parse_separator(COMMA):
                continue
            else:
                te = p.require_transfer_encoding()
                telist.append(te)
        return telist

    def to_bytes(self):
        return self.token + format_parameters(self.parameters)

    def sortkey(self):
        return (self.token, self._hp)

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


class Chunk(SortableMixin, Parameter):
    """Represents an HTTP chunk header

    size
        The size of this chunk (defaults to 0)

    extensions
        A parameter dictionary mapping parameter names to tuples
        of strings: (chunk-ext-name, chunk-ext-val)

    For completeness, instances are sortable by size and then by
    alphabetical parameter name, value pairs."""

    def __init__(self, size=0, extensions=None):
        #: the chunk-size
        self.size = size
        #: declared extension parameters
        if extensions:
            self.extensions = self.bparameters(extensions)
        else:
            self.extensions = {}
        self._cx = sorted((p[0], p[1][1]) for p in dict_items(self.extensions))

    @classmethod
    def from_str(cls, source):
        """Parses the chunk header from a *source* string of *TEXT*.

        If the chunk header is not parsed correctly BadSyntax is raised.
        The header includes the chunk-size and any chunk-extension
        parameters but it does *not* include the trailing CRLF or the
        chunk-data"""
        p = ParameterParser(source)
        chunk = p.require_chunk()
        p.require_end("chunk")
        return chunk

    def to_bytes(self):
        return b"%X%s" % (self.size, format_parameters(self.extensions))

    def sortkey(self):
        return (self.size, self._cx)

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


class MediaType(SortableMixin, Parameter):
    """Represents an HTTP media-type.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    type
        The type code string, defaults to 'application'

    subtype
        The sub-type code, defaults to 'octet-stream'

    parameters
        A dictionary such as would be returned by
        :py:meth:`grammar.WordParser.parse_parameters` containing the
        media type's parameters.

    Instances are immutable and support parameter value access by
    lower-case key, returning the corresponding value or raising
    KeyError.  E.g., mtype['charset']

    Instances also define comparison methods and a hash implementation.
    Media-types are compared by (lower case) type, subtype and ultimately
    parameters."""

    def __init__(self, type=b"application", subtype=b"octet-stream",
                 parameters={}):
        self.type = self.bstr(type)
        self.subtype = self.bstr(subtype)
        if parameters:
            self.parameters = self.bparameters(parameters)
        else:
            self.parameters = {}
        self._hp = sorted((p[0], p[1][1]) for p in dict_items(self.parameters))

    @classmethod
    def from_str(cls, source):
        """Creates a media-type from a *source* string.

        Enforces the following rule from the specification:

            Linear white space (LWS) MUST NOT be used between the type
            and subtype, nor between an attribute and its value"""
        p = ParameterParser(source, ignore_sp=False)
        mt = p.require_media_type()
        p.parse_sp()
        p.require_end("media-type")
        return mt

    def to_bytes(self):
        return (b''.join([self.type, b'/', self.subtype]) +
                format_parameters(self.parameters))

    def __repr__(self):
        return "MediaType(%s, %s, %s)" % (repr(self.type),
                                          repr(self.subtype),
                                          repr(self.parameters))

    def __getitem__(self, key):
        if is_unicode(key):
            key = key.encode('latin1')
        if key in self.parameters:
            return self.parameters[key][1]
        else:
            raise KeyError("MediaType instance has no parameter %s" %
                           repr(key))

    def sortkey(self):
        return (self.type.lower(), self.subtype.lower(), self._hp)

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


#: A predefined constant for application/octet-stream
APPLICATION_OCTETSTREAM = MediaType(b'application', b'octet-stream')

#: A predefined constant for text/plain
PLAIN_TEXT = MediaType(b'text', b'plain')


class ProductToken(SortableMixin, Parameter):
    """Represents an HTTP product token.

    The comparison operations use a more interesting sort than plain
    text on version in order to provide a more intuitive ordering.  As
    it is common practice to use dotted decimal notation for versions
    (with some alphanumeric modifiers) the version string is exploded
    (see :py:meth:`explode`) internally on construction and this
    exploded value is used in comparisons.  The upshot is that version
    1.0.3 sorts before 1.0.10 as you would expect and 1.0a < 1.0 <
    1.0.3a3 < 1.0.3a20 < 1.0.3b1 < 1.0.3; there are limits to this
    algorithm.  1.0dev > 1.0b1 even though it looks like it should be
    the other way around.  Similarly 1.0-live < 1.0-prod etc.

    You shouldn't use this comparison as a definitive way to determine
    that one release is more recent or up-to-date than another unless
    you know that the product in question uses a numbering scheme
    compatible with these rules.  On the other hand, it can be useful
    when sorting lists for human consumption."""

    def __init__(self, token=None, version=None):
        #: the product's token
        self.token = self.bstr(token)
        #: the product's version
        self.version = self.bstr(version)
        if self.version is not None:
            # explode the version string
            self._version = self.explode(self.version)
        else:
            self._version = ()

    @classmethod
    def explode(cls, version):
        """Returns an exploded version string.

        Version strings are split by dot and then by runs of non-digit
        characters resulting in a list of tuples.  Numbers that have
        modified are treated as if they had a ~ suffix.  This ensures
        that when sorting, 1.0 > 1.0a (i.e., qualifiers indicate earlier
        releases, ~ being the ASCII character with the largest
        codepoint).

        Examples will help::

                explode("2.15")==((2, "~"),(15, "~"))
                explode("2.17b3")==((2, "~"),(17, "b", 3, "~"))
                explode("2.b3")==((2, "~"),(-1, "b", 3, "~"))

        Note that a missing leading numeric component is treated as -1
        to force "a3" to sort before "0a3"."""
        exploded = []
        p = BasicParser(force_bytes(version))
        while p.the_char is not None:
            # parse an item
            vitem = []
            modifier = []
            while not p.match(b".") and not p.match_end():
                num = p.parse_integer()
                if num is None:
                    if not vitem:
                        vitem.append(-1)
                    modifier.append(p.the_char)
                    p.next_char()
                else:
                    if modifier:
                        vitem.append(join_bytes(modifier))
                        modifier = []
                    vitem.append(num)
            if modifier:
                vitem.append(join_bytes(modifier))
            elif vitem:
                # forces 1.0 > 1.0b
                vitem.append(b'~')
            exploded.append(tuple(vitem))
            p.parse(b".")
        return tuple(exploded)

    @classmethod
    def from_str(cls, source):
        """Creates a product token from a *source* string."""
        p = ParameterParser(source)
        p.parse_sp()
        pt = p.require_product_token()
        p.parse_sp()
        p.require_end("product token")
        return pt

    @classmethod
    def list_from_str(cls, source):
        """Creates a list of product tokens from a *source* string.

        Individual tokens are separated by white space."""
        ptlist = []
        p = ParameterParser(source)
        p.parse_sp()
        while p.the_word is not None:
            ptlist.append(p.require_product_token())
            p.parse_sp()
        p.require_end("product token")
        return ptlist

    def to_bytes(self):
        if self.version is None:
            return self.token
        else:
            return b''.join((self.token, b'/', self.version))

    def __repr__(self):
        return "ProductToken(%s, %s)" % (repr(self.token), repr(self.version))

    def sortkey(self):
        return (self.token, self._version)

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


class LanguageTag(SortableMixin, Parameter):
    """Represents an HTTP language-tag.

    Language tags are compared by lower casing all components and then
    sorting by primary tag, then by each sub-tag. Note that en sorts
    before en-US."""

    def __init__(self, primary, *subtags):
        self.primary = self.bstr(primary)
        self.subtags = tuple([self.bstr(t) for t in subtags])
        tags = [primary.lower()]
        for sub in subtags:
            tags.append(sub.lower())
        self._tag = tuple(tags)

    def partial_match(self, range):
        """True if this tag is a partial match against *range*

        range
            A tuple of lower-cased subtags.  An empty tuple matches all
            instances.

        For example::

            lang=LanguageTag("en",("US","Texas"))
            lang.partial_match(())==True
            lang.partial_match(("en",)==True
            lang.partial_match(("en","us")==True
            lang.partial_match(("en","us","texas")==True
            lang.partial_match(("en","gb")==False
            lang.partial_match(("en","us","tex")==False"""
        if len(range) > len(self._tag):
            return False
        for i in range3(len(range)):
            if self._tag[i] != range[i]:
                return False
        return True

    @classmethod
    def from_str(cls, source):
        """Creates a language tag from a *source* string.

        Enforces the following rules from the specification:

                White space is not allowed within the tag"""
        p = ParameterParser(source, ignore_sp=False)
        p.parse_sp()
        t = p.require_language_tag()
        p.parse_sp()
        p.require_end("language tag")
        return t

    @classmethod
    def list_from_str(cls, source):
        """Creates a list of language tags from a *source* string."""
        p = ParameterParser(source, ignore_sp=False)
        tags = []
        while True:
            p.parse_sp()
            t = p.parse_production(p.require_language_tag)
            if t is not None:
                tags.append(t)
            p.parse_sp()
            if not p.parse_separator(","):
                break
        p.parse_sp()
        p.require_end("language tag")
        return tags

    def to_bytes(self):
        return b'-'.join([self.primary] + list(self.subtags))

    def __repr__(self):
        return (
            "LanguageTag(%s)" % b','.join(
                [repr(tag) for tag in [self.primary] + list(self.subtags)]))

    def sortkey(self):
        return self._tag

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


class EntityTag(SortableMixin, Parameter):
    """Represents an HTTP entity-tag.

    tag
        The opaque tag

    weak
        A boolean indicating if the entity-tag is a weak or strong
        entity tag.  Defaults to True.

    Instances are compared by tag and then, if the tags match, by
    wheather the tag is weak or not."""

    def __init__(self, tag, weak=True):
        #: True if this is a weak tag
        self.weak = weak
        #: the opaque tag
        self.tag = self.bstr(tag)

    @classmethod
    def from_str(cls, source):
        """Creates an entity-tag from a *source* string."""
        p = ParameterParser(source)
        et = p.require_entity_tag()
        p.require_end("entity-tag")
        return et

    def to_bytes(self):
        if self.weak:
            return b"W/" + quote_string(self.tag)
        else:
            return quote_string(self.tag)

    def __repr__(self):
        return ("EntityTag(%s,%s)" %
                (repr(self.tag), "True" if self.week else "False"))

    def sortkey(self):
        return (self.tag, self.weak)

    def otherkey(self, other):
        if isinstance(other, self.__class__):
            return other.sortkey()
        elif is_string(other):
            return self.from_str(other).sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())


SLASH = byte('/')
COLON = byte(':')


class ParameterParser(WordParser):
    """An extended parser for parameter values

    This parser defines attributes for dealing with English date names
    that are useful beyond the basic parsing functions to allow the
    formatting of date information in English regardless of the
    locale."""

    def require_http_version(self):
        """Parses an :py:class:`HTTPVersion` instance

        Returns an :class:`HTTPVersion` instance."""
        self.parse_sp()
        token = self.require_token(b"HTTP").upper()
        if token != b"HTTP":
            self.parser_error('HTTP')
        self.parse_sp()
        self.require_separator(SLASH, "HTTP/")
        self.parse_sp()
        token = self.require_token("protocol version")
        version = token.split(b'.')
        if (len(version) != 2 or not is_digits(version[0]) or
                not is_digits(version[1])):
            self.parser_error('version')
        return HTTPVersion(major=int(version[0]), minor=int(version[1]))

    #: A list of English day-of-week abbreviations: wkday[0] == "Mon",
    #: etc.
    wkday = [b"Mon", b"Tue", b"Wed", b"Thu", b"Fri", b"Sat", b"Sun"]

    #: A list of English day-of-week full names: weekday[0] == "Monday"
    weekday = [b"Monday", b"Tuesday", b"Wednesday", b"Thursday", b"Friday",
               b"Saturday", b"Sunday"]

    _wkdayTable = {}

    #: A list of English month names: month[0] == "Jan", etc.
    month = [b"Jan", b"Feb", b"Mar", b"Apr", b"May", b"Jun",
             b"Jul", b"Aug", b"Sep", b"Oct", b"Nov", b"Dec"]

    _monthTable = {}

    def require_fulldate(self):
        """Parses a :py:class:`FullDate` instance.

        Returns a :class:`FullDate` instance or raises
        :py:class:`~pyslet.http.grammar.BadSyntax` if none is found."""
        century = None
        year = None
        month = None
        day = None
        hour = None
        minute = None
        second = None
        dayofweek = None
        self.parse_sp()
        token = self.require_token("day-of-week").lower()
        dayofweek = self._wkdayTable.get(token, None)
        if dayofweek is None:
            self.parser_error("day of week")
        self.parse_sp()
        if self.parse_separator(COMMA):
            self.parse_sp()
            if self.is_token() and is_digits(self.the_word):
                # Best format 0: "Sun, 06 Nov 1994 08:49:37 GMT" - the
                # preferred format!
                day = self.require_integer("date")
                self.parse_sp()
                token = self.require_token("month").lower()
                month = self._monthTable.get(token, None)
                if month is None:
                    self.parser_error("month")
                self.parse_sp()
                year = self.require_integer("year")
                century = year // 100
                year = year % 100
            else:
                # Alternative 1: "Sunday, 06-Nov-94 08:49:37 GMT"
                token = self.require_token("DD-MMM-YY")
                stoken = token.split(b'-')
                if (len(stoken) != 3 or not is_digits(stoken[0]) or
                        not is_digits(stoken[2])):
                    self.parser_error("DD-MMM-YY")
                day = int(stoken[0])
                year = int(stoken[2])
                month = self._monthTable.get(stoken[1].lower(), None)
                if month is None:
                    self.parser_error("month")
        else:
            # "Sun Nov  6 08:49:37 1994"
            token = self.require_token("month").lower()
            month = self._monthTable.get(token, None)
            if month is None:
                self.parser_error("month")
            self.parse_sp()
            day = self.require_integer("date")
        self.parse_sp()
        hour = self.require_integer("hour")
        self.require_separator(COLON)
        minute = self.require_integer("minute")
        self.require_separator(COLON)
        second = self.require_integer("second")
        self.parse_sp()
        if year is None:
            year = self.require_integer("year")
            century = year // 100
            year = year % 100
        else:
            token = self.require_token("GMT").upper()
            if token != b"GMT":
                self.parser_error("timezone")
        if century is None:
            if year < 90:
                century = 20
            else:
                century = 19
        tp = FullDate(
            date=iso.Date(century=century, year=year, month=month + 1,
                          day=day),
            time=iso.Time(hour=hour, minute=minute, second=second,
                          zdirection=0))
        d1, d2, d3, d4, dow = tp.date.get_week_day()
        if dow != dayofweek + 1:
            self.parser_error("matching day-of-week")
        return tp

    #: Parses a delta-seconds value, see
    #: :py:meth:`WordParser.parse_integer`
    parse_delta_seconds = WordParser.parse_integer

    #: Parses a charset, see :py:meth:`WordParser.parse_tokenlower`
    parse_charset = WordParser.parse_tokenlower

    #: Parses a content-coding, see
    #: :py:meth:`WordParser.parse_tokenlower`
    parse_content_coding = WordParser.parse_tokenlower

    def require_transfer_encoding(self):
        """Parses a :py:class:`TransferEncoding` instance"""
        self.parse_sp()
        token = self.require_token("transfer-encoding").lower()
        if token != b"chunked":
            parameters = {}
            self.parse_parameters(parameters)
            return TransferEncoding(token, parameters)
        else:
            return TransferEncoding()

    def require_chunk(self):
        """Parses a chunk header

        Returns a :py:class:`Chunk` instance."""
        self.parse_sp()
        size = self.require_hexinteger("chunk-size")
        extensions = {}
        self.parse_parameters(extensions)
        return Chunk(size, extensions)

    def require_media_type(self):
        """Parses a :py:class:`MediaType` instance."""
        self.parse_sp()
        type = self.require_token("media-type").lower()
        self.require_separator(SLASH, "media-type")
        subtype = self.require_token("media-subtype").lower()
        self.parse_sp()
        parameters = {}
        self.parse_parameters(parameters, ignore_allsp=False)
        return MediaType(type, subtype, parameters)

    def require_product_token(self):
        """Parses a :py:class:`ProductToken` instance.

        Raises BadSyntax if no product token was found."""
        self.parse_sp()
        token = self.require_token("product token")
        self.parse_sp()
        if self.parse_separator(SLASH):
            version = self.require_token("product-version")
        else:
            version = None
        return ProductToken(token, version)

    def parse_qvalue(self):
        """Parses a qvalue returning a float

        Returns None if no qvalue was found."""
        if self.is_token():
            q = None
            qsplit = self.the_word.split(b'.')
            if len(qsplit) == 1:
                if is_digits(qsplit[0]):
                    q = float(qsplit[0])
            elif len(qsplit) == 2:
                if is_digits(qsplit[0]) and is_digits(qsplit[1]):
                    q = float("%.3f" % float(self.the_word))
            if q is None:
                return None
            else:
                if q > 1.0:
                    # be generous if the value has overflowed
                    q = 1.0
                self.parse_word()
                return q
        else:
            return None

    def require_language_tag(self):
        """Parses a language tag returning a :py:class:`LanguageTag`
        instance.  Raises BadSyntax if no language tag was
        found."""
        self.parse_sp()
        tag = self.require_token("languaget-tag").split(b'-')
        self.parse_sp()
        return LanguageTag(tag[0], *tag[1:])

    def require_entity_tag(self):
        """Parses an entity-tag returning a :py:class:`EntityTag`
        instance.  Raises BadSyntax if no language tag was
        found."""
        self.parse_sp()
        w = self.parse_token()
        self.parse_sp()
        if w is not None:
            if w.upper() != b"W":
                self.parser_error("entity-tag")
            self.require_separator(SLASH, "entity-tag")
            self.parse_sp()
            w = True
        else:
            w = False
        tag = self.require_production(self.parse_quoted_string(), "entity-tag")
        self.parse_sp()
        return EntityTag(tag, w)


for i in range3(len(ParameterParser.wkday)):
    ParameterParser._wkdayTable[ParameterParser.wkday[i].lower()] = i
for i in range3(len(ParameterParser.weekday)):
    ParameterParser._wkdayTable[ParameterParser.weekday[i].lower()] = i
for i in range3(len(ParameterParser.month)):
    ParameterParser._monthTable[ParameterParser.month[i].lower()] = i
