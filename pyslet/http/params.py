#! /usr/bin/env python

import string
import types

import pyslet.iso8601 as iso
import pyslet.rfc2396 as uri

from pyslet.http.grammar import *       # noqa


class HTTPVersion(object):

    """Represents the HTTP Version.

    major
        The (optional) major version

    minor
        The (optional) minor version

    The default instance, HTTPVersion(), represents HTTP/1.1

    HTTPVersion objects are immutable, they define comparison functions
    (such that 1.1 > 1.0 and  1.2 < 1.25) and a hash implementation is
    provided.

    On conversion to a string the output is of the form::

            HTTP/<major>.<minor>

    For convenience, the constants HTTP_1p1 and HTTP_1p0 are provided
    for comparisons, e.g.::

        if HTTPVersion.from_str(version_str) == HTTP_1p0:
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
        result = wp.require_production(wp.parse_http_version(), "HTTP Version")
        wp.require_end("HTTP version")
        return result

    def __str__(self):
        return "HTTP/%i.%i" % (self.major, self.minor)

    def __hash__(self):
        return hash((self.major, self.minor))

    def __cmp__(self, other):
        if not isinstance(other, HTTPVersion):
            raise TypeError
        if self.major < other.major:
            return -1
        elif self.major > other.major:
            return 1
        elif self.minor < other.minor:
            return -1
        elif self.minor > other.minor:
            return 1
        else:
            return 0

#: A constant representing HTTP/1.1
HTTP_1p1 = HTTPVersion(1, 1)

#: A constant representing HTTP/1.0
HTTP_1p0 = HTTPVersion(1, 0)

#: symbolic name for the default HTTP port
HTTP_PORT = 80

#: symbolic name for the default HTTPS port
HTTPS_PORT = 443


class HTTPURL(uri.ServerBasedURL):

    """Represents http URLs"""

    #: the default HTTP port
    DEFAULT_PORT = HTTP_PORT

    def __init__(self, octets='http://localhost/'):
        super(HTTPURL, self).__init__(octets)

    def canonicalize(self):
        """Returns a canonical form of this URI"""
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
        if self.absPath is not None:
            if not self.absPath:
                new_uri.append("/")
            else:
                new_uri.append(uri.CanonicalizeData(self.absPath))
        elif self.relPath is not None:
            new_uri.append(uri.CanonicalizeData(self.relPath))
        if self.query is not None:
            new_uri.append('?')
            new_uri.append(uri.CanonicalizeData(self.query))
        if self.fragment is not None:
            new_uri.append('#')
            new_uri.append(self.fragment)
        return uri.URIFactory.URI(string.join(new_uri, ''))


class HTTPSURL(HTTPURL):

    """Represents https URLs"""

    #: the default HTTPS port
    DEFAULT_PORT = HTTPS_PORT

    def __init__(self, octets='https://localhost/'):
        super(HTTPSURL, self).__init__(octets)


uri.URIFactory.Register('http', HTTPURL)
uri.URIFactory.Register('https', HTTPSURL)


class FullDate(iso.TimePoint):

    """A special sub-class for HTTP-formatted dates"""

    @classmethod
    def from_http_str(cls, source):
        """Returns an instance parsed from an HTTP formatted string"""
        wp = ParameterParser(source)
        tp = wp.require_fulldate()
        wp.parse_sp()
        wp.require_end("full date")
        return tp

    def __str__(self):
        """Formats the instance according to RFC 1123

        The format is as follows::

            Sun, 06 Nov 1994 08:49:37 GMT

        This format is also described in in RFC2616 in the production
        rfc1123-date.

        Note that this overrides the default behaviour which would be to
        use one of the iso8601 output formats."""
        z = self.ShiftZone(0)
        (century, year, month, day,
         hour, minute, second) = z.GetCalendarTimePoint()
        century, decade, dyear, week, dayofweek = z.date.GetWeekDay()
        return "%s, %02i %s %04i %02i:%02i:%02i GMT" % (
            ParameterParser.wkday[dayofweek - 1],
            day,
            ParameterParser.month[month - 1],
            century * 100 + year,
            hour, minute, second)

    def __unicode(self):
        """See __str__"""
        return unicode(str(self))


class TransferEncoding(object):

    """Represents an HTTP transfer-encoding.

    token
        The transfer encoding identifier, defaults to "chunked"

    parameters
        A parameter dictionary mapping parameter names to tuples
        of strings: (parameter name, parameter value)

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    Instances are immutable, they define comparison methods and a hash
    implementation."""

    def __init__(self, token="chunked", parameters={}):
        token = token.lower()
        if token == "chunked":
            #: the lower-cased transfer-encoding token (defaults to "chunked")
            self.token = "chunked"
            #: declared extension parameters
            self.parameters = {}
        else:
            self.token = token
            self.parameters = parameters
        self._hp = map(lambda x: (x[0], x[1][1]), self.parameters.items())
        self._hp.sort()
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
            if p.parse_separator(','):
                continue
            else:
                te = p.require_transfer_encoding()
                telist.append(te)
        return telist

    def __str__(self):
        return self.token + format_parameters(self.parameters)

    def __eq__(self, other):
        if type(other) in types.StringTypes:
            other = TransferEncoding.from_str(other)
        if not isinstance(other, TransferEncoding):
            raise TypeError
        return hash(self) == hash(other)

    def __cmp__(self, other):
        if type(other) in types.StringTypes:
            other = TransferEncoding.from_str(other)
        if not isinstance(other, TransferEncoding):
            raise TypeError
        return cmp((self.token, self._hp), (other.token, other._hp))

    def __hash__(self):
        return hash((self.token, self._hp))


class Chunk(object):

    """Represents an HTTP chunk header

    size
        The size of this chunk (defaults to 0)

    extensions
        A parameter dictionary mapping parameter names to tuples
        of strings: (chunk-ext-name, chunk-ext-val)

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.  The resulting string
    does *not* include the trailing CRLF.

    Instances are immutable, they define comparison methods and a hash
    implementation."""

    def __init__(self, size=0, extensions=None):
        #: the chunk-size
        self.size = size
        #: declared extension parameters
        if extensions is None:
            self.extensions = {}
        else:
            self.extensions = extensions
        self._cx = map(lambda x: (x[0], x[1][1]), self.extensions.items())
        self._cx.sort()

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

    def __str__(self):
        return "%X%s" % (self.size, format_parameters(self.extensions))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __cmp__(self, other):
        if type(other) in types.StringTypes:
            other = self.from_str(other)
        if not isinstance(Chunk):
            raise TypeError
        return cmp((self.size, self._cx), (other.size, other._cx))

    def __hash__(self):
        return hash((self.size, self._cx))


class MediaType(object):

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
    Media-types are compared by type, subtype and ultimately
    parameters."""

    def __init__(self, type="application", subtype="octet-stream",
                 parameters={}):
        self.type = type
        self.subtype = subtype
        self.parameters = parameters
        self._hp = map(lambda x: (x[0], x[1][1]), self.parameters.items())
        self._hp.sort()

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

    def __str__(self):
        return (string.join([self.type, '/', self.subtype], '') +
                format_parameters(self.parameters))

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return "MediaType(%s,%s,%s)" % (repr(self.type),
                                        repr(self.subtype),
                                        repr(self.parameters))

    def __getitem__(self, key):
        if key in self.parameters:
            return self.parameters[key][1]
        else:
            raise KeyError("MediaType instance has no parameter %s" %
                           repr(key))

    def __cmp__(self, other):
        if type(other) in types.StringTypes:
            other = MediaType.from_str(other)
        if not isinstance(other, MediaType):
            raise TypeError
        result = cmp(self.type.lower(), other.type.lower())
        if result:
            return result
        result = cmp(self.subtype.lower(), other.subtype.lower())
        if result:
            return result
        return cmp(self._hp, other._hp)

    def __hash__(self):
        return hash((self.type.lower(), self.subtype.lower(), self._hp))


#: A predefined constant for application/octet-stream
APPLICATION_OCTETSTREAM = MediaType('application', 'octet-stream')

#: A predefined constant for text/plain
PLAIN_TEXT = MediaType('text', 'plain')


class ProductToken(object):

    """Represents an HTTP product token.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    Instances are immutable, they define comparison methods and a hash
    implementation.

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
    compatible with these rules."""

    def __init__(self, token=None, version=None):
        #: the product's token
        self.token = token
        #: the product's version
        self.version = version
        if self.version is not None:
            # explode the version string
            self._version = self.explode(self.version)
        else:
            self._version = ()

    @classmethod
    def explode(cls, version):
        """Returns an exploded version string.

        Version strings are split by dot and then by runs of non-digit
        characters resulting in a list of tuples.  Examples will help::

                explode("2.15")==((2),(15))
                explode("2.17b3")==((2),(17,"b",3))
                explode("2.b3")==((2),(-1,"b",3))

        Note that a missing leading numeric component is treated as -1
        to force "a3" to sort before "0a3"."""
        exploded = []
        p = BasicParser(version)
        while p.the_char is not None:
            # parse an item
            vitem = []
            modifier = []
            while not p.match(".") and not p.MatchEnd():
                num = p.parse_integer()
                if num is None:
                    if not vitem:
                        vitem.append(-1)
                    modifier.append(p.the_char)
                    p.NextChar()
                else:
                    if modifier:
                        vitem.append(string.join(modifier, ''))
                        modifier = []
                    vitem.append(num)
            if modifier:
                vitem.append(string.join(modifier, ''))
            exploded.append(tuple(vitem))
            p.Parse(".")
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

    def __str__(self):
        if self.version is None:
            return self.token
        else:
            return string.join((self.token, '/', self.version), '')

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return "ProductToken(%s,%s)" % (repr(self.token), repr(self.version))

    def __cmp__(self, other):
        if type(other) in types.StringTypes:
            other = ProductToken.from_str(other)
        elif not isinstance(other, ProductToken):
            raise TypeError
        result = cmp(self.token, other.token)
        if result:
            return result
        iversion = 0
        while True:
            if iversion < len(self._version):
                v = self._version[iversion]
            else:
                v = None
            if iversion < len(other._version):
                vother = other._version[iversion]
            else:
                vother = None
            # a missing component sorts before
            if v is None:
                if vother is None:
                    # both missing, must be equal.  Note that this
                    # means that "01" is treated equal to "1"
                    return 0
                else:
                    return -1
            elif vother is None:
                return 1
            # now loop through the sub-components and compare them
            jversion = 0
            while True:
                if jversion < len(v):
                    vv = v[jversion]
                else:
                    vv = None
                if jversion < len(vother):
                    vvother = vother[jversion]
                else:
                    vvother = None
                if vv is None:
                    if vvother is None:
                        break
                    else:
                        # "1.0">"1.0a"
                        return 1
                elif vvother is None:
                    # "1.0a"<"1.0"
                    return -1
                # 1.0 < 1.1 and 1.0a<1.0b
                result = cmp(vv, vvother)
                if result:
                    return result
                jversion += 1
            iversion += 1
        # we can't get here
        return 0

    def __hash__(self):
        # despite the complex comparison function versions can only be
        # equal if they have exactly the same version
        return hash((self.token, self._version))


class LanguageTag(object):

    """Represents an HTTP language-tag.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    Instances are immutable, they define comparison methods and a hash
    implementation."""

    def __init__(self, primary, *subtags):
        self.primary = primary
        self.subtags = subtags
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
        for i in xrange(len(range)):
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

    def __str__(self):
        return string.join([self.primary] + list(self.subtags), '-')

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return (
            "LanguageTag(%s)" %
            string.join(map(repr, [self.primary] + list(self.subtags)), ','))

    def __cmp__(self, other):
        """Language tags are compared case insensitive."""
        if type(other) in types.StringTypes:
            other = LanguageTag.from_str(other)
        if not isinstance(other, LanguageTag):
            raise TypeError
        return cmp(self._tag, other._tag)

    def __hash__(self):
        return hash(self._tag)


class EntityTag:

    """Represents an HTTP entity-tag.

    tag
        The opaque tag

    weak
        A boolean indicating if the entity-tag is a weak or strong
        entity tag.  Defaults to True.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    Instances are immutable, they define comparison methods and a hash
    implementation."""

    def __init__(self, tag, weak=True):
        #: True if this is a weak tag
        self.weak = weak
        #: the opaque tag
        self.tag = tag

    @classmethod
    def from_str(cls, source):
        """Creates an entity-tag from a *source* string."""
        p = ParameterParser(source)
        et = p.require_entity_tag()
        p.require_end("entity-tag")
        return et

    def __str__(self):
        if self.weak:
            return "W/" + quote_string(self.tag)
        else:
            return quote_string(self.tag)

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return ("EntityTag(%s,%s)" %
                (repr(self.tag), "True" if self.week else "False"))

    def __cmp__(self, other):
        """Entity-tags are compared case sensitive."""
        if type(other) in StringTypes:
            other = EntityTag.from_str(other)
        if not isinstance(other, EntityTag):
            raise TypeError
        result = cmp(self.tag, other.tag)
        if not result:
            # sorts strong tags before weak ones
            result = cmp(self.weak, other.weak)
        return result

    def __hash__(self):
        return hash((self.tag, self.weak))


class ParameterParser(WordParser):

    """An extended parser for parameter values

    This parser defines attributes for dealing with English date names
    that are useful beyond the basic parsing functions to allow the
    formatting of date information in English regardless of the
    locale."""

    def parse_http_version(self):
        """Parses an :py:class:`HTTPVersion` instance

        Returns None if no version was found."""
        savepos = self.pos
        try:
            self.parse_sp()
            token = self.require_token("HTTP").upper()
            if token != "HTTP":
                raise BadSyntax("Expected 'HTTP', found %s" % repr(token))
            self.parse_sp()
            self.require_separator('/', "HTTP/")
            self.parse_sp()
            token = self.require_token("protocol version")
            version = token.split('.')
            if (len(version) != 2 or not is_digits(version[0]) or
                    not is_digits(version[1])):
                raise BadSyntax("Expected version, found %s" % repr(token))
            return HTTPVersion(major=int(version[0]), minor=int(version[1]))
        except BadSyntax:
            self.setpos(savepos)
            return None

    #: A list of English day-of-week abbreviations: wkday[0] == "Mon",
    #: etc.
    wkday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    #: A list of English day-of-week full names: weekday[0] == "Monday"
    weekday = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
               "Saturday", "Sunday"]

    _wkdayTable = {}

    #: A list of English month names: month[0] == "Jan", etc.
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    _monthTable = {}

    def require_fulldate(self):
        """Parses a :py:class:`FullDate` instance.

        Raises :py:class:`BadSyntax` if none is found.

        There are three supported formats as described in the
        specification::

            "Sun, 06 Nov 1994 08:49:37 GMT"
            "Sunday, 06-Nov-94 08:49:37 GMT"
            "Sun Nov  6 08:49:37 1994"

        The first of these is the preferred format."""
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
            raise BadSyntax("Unrecognized day of week: %s" % token)
        self.parse_sp()
        if self.parse_separator(","):
            self.parse_sp()
            if self.is_token() and is_digits(self.the_word):
                # Best format 0: "Sun, 06 Nov 1994 08:49:37 GMT" - the
                # preferred format!
                day = self.require_integer("date")
                self.parse_sp()
                token = self.require_token("month").lower()
                month = self._monthTable.get(token, None)
                if month is None:
                    raise BadSyntax("Unrecognized month: %s" % repr(token))
                self.parse_sp()
                year = self.require_integer("year")
                century = year // 100
                year = year % 100
            else:
                # Alternative 1: "Sunday, 06-Nov-94 08:49:37 GMT"
                token = self.require_token("DD-MMM-YY")
                stoken = token.split('-')
                if (len(stoken) != 3 or not is_digits(stoken[0]) or
                        not is_digits(stoken[2])):
                    raise BadSyntax("Expected DD-MMM-YY, found %s" %
                                    repr(token))
                day = int(stoken[0])
                year = int(stoken[2])
                month = self._monthTable.get(stoken[1].lower(), None)
                if month is None:
                    raise BadSyntax(
                        "Unrecognized month: %s" % repr(stoken[1]))
        else:
            # "Sun Nov  6 08:49:37 1994"
            token = self.require_token("month").lower()
            month = self._monthTable.get(token, None)
            if month is None:
                raise BadSyntax("Unrecognized month: %s" % repr(token))
            self.parse_sp()
            day = self.require_integer("date")
        self.parse_sp()
        hour = self.require_integer("hour")
        self.require_separator(':')
        minute = self.require_integer("minute")
        self.require_separator(':')
        second = self.require_integer("second")
        self.parse_sp()
        if year is None:
            year = self.require_integer("year")
            century = year // 100
            year = year % 100
        else:
            token = self.require_token("GMT").upper()
            if token != "GMT":
                raise BadSyntax("Unrecognized timezone: %s" % repr(token))
        if century is None:
            if year < 90:
                century = 20
            else:
                century = 19
        tp = FullDate(
            date=iso.Date(century=century, year=year, month=month + 1,
                          day=day),
            time=iso.Time(hour=hour, minute=minute, second=second,
                          zDirection=0))
        d1, d2, d3, d4, dow = tp.date.GetWeekDay()
        if dow != dayofweek + 1:
            raise BadSyntax("Day-of-week mismatch, expected %s but found %s" %
                            (self.wkday[dow - 1], self.wkday[dayofweek]))
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
        """Parses a :py:class:`TransferEncoding` instance

        Returns None if no transfer-encoding was found."""
        self.parse_sp()
        token = self.require_token("transfer-encoding").lower()
        if token != "chunked":
            parameters = {}
            self.parse_parameters(parameters)
            return TransferEncoding(token, parameters)
        else:
            return TransferEncoding()

    def require_chunk(self):
        """Parses a chunk header

        Returns a :py:class:`Chunk` instance or None if no chunk was
        found."""
        self.parse_sp()
        size = self.require_hexinteger("chunk-size")
        extensions = {}
        self.parse_parameters(extensions)
        return Chunk(size, extensions)

    def require_media_type(self):
        """Parses a :py:class:`MediaType` instance.

        Raises BadSyntax if no media-type was found."""
        self.parse_sp()
        type = self.require_token("media-type").lower()
        self.require_separator('/', "media-type")
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
        if self.parse_separator('/'):
            version = self.require_token("product-version")
        else:
            version = None
        return ProductToken(token, version)

    def parse_qvalue(self):
        """Parses a qvalue returning a float

        Returns None if no qvalue was found."""
        if self.is_token():
            q = None
            qsplit = self.the_word.split('.')
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
        tag = self.require_token("languaget-tag").split('-')
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
            if w.upper() != "W":
                raise BadSyntax(
                    "Expected W/ or quoted string for entity-tag")
            self.require_separator("/", "entity-tag")
            self.parse_sp()
            w = True
        else:
            w = False
        tag = self.require_production(self.parse_quoted_string(), "entity-tag")
        self.parse_sp()
        return EntityTag(tag, w)


for i in xrange(len(ParameterParser.wkday)):
    ParameterParser._wkdayTable[ParameterParser.wkday[i].lower()] = i
for i in xrange(len(ParameterParser.weekday)):
    ParameterParser._wkdayTable[ParameterParser.weekday[i].lower()] = i
for i in xrange(len(ParameterParser.month)):
    ParameterParser._monthTable[ParameterParser.month[i].lower()] = i
