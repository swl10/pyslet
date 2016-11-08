#! /usr/bin/env python

import time
import logging
import threading
import os.path

from .. import iso8601 as iso
from ..py2 import (
    byte,
    byte_value,
    dict_values,
    is_unicode,
    join_bytes,
    to_bytes)

from . import grammar
from . import params


def is_cookie_octet(b):
    """Tests a byte against production coookie_octet"""
    if b is not None:
        return 0x20 < byte_value(b) < 0x7F and b not in b'",;\\'
    else:
        return False

HYPHEN = byte('-')
FULL_STOP = byte('.')


def is_ldh_label(label):
    """Tests a binary string against the definition of LDH label

    LDH Label is defined in RFC5890_ as being the classic label syntax
    defined in RFC1034_ and updated in RFC1123_.  To cut a long story
    short the update in question is described as follows:

        One aspect of host name syntax is hereby changed: the
        restriction on the first character is relaxed to allow either a
        letter or a digit.

    ..  _RFC5890: http://tools.ietf.org/html/rfc5890

    ..  _RFC1034: http://tools.ietf.org/html/rfc1034

    ..  _RFC1123: http://tools.ietf.org/html/rfc1123

    Although not spelled out there this would make the updated syntax::

        <label> ::= <let-dig> [ [ <ldh-str> ] <let-dig> ]
        <ldh-str> ::= <let-dig-hyp> | <let-dig-hyp> <ldh-str>
        <let-dig-hyp> ::= <let-dig> | "-"
        <let-dig> ::= <letter> | <digit>"""
    allow_hyphen = False
    trailing_hyphen = False
    if not label or len(label) > 63:
        return False
    for b in label:
        if (grammar.is_alpha(b) or grammar.is_digit(b) or
                (allow_hyphen and b == HYPHEN)):
            trailing_hyphen = (b == HYPHEN)
            allow_hyphen = True
        else:
            return False
    return not trailing_hyphen


def is_rldh_label(label):
    """Tests a binary string against the definition of R-LDH label

    As defined by RFC5890_

        Reserved LDH labels, known as "tagged domain names" in some
        other contexts, have the property that they contain "--" in the
        third and fourth characters but which otherwise conform to LDH
        label rules.

        Non-Reserved LDH labels are the set of valid LDH labels that do
        not have "--" in the third and fourth positions.

    Therefore you can test for a NR-LDH label simply by using the *not*
    operator."""
    return is_ldh_label(label) and label[2:4] == b'--'


def is_a_label(label):
    """Test a binary string against the definition of A-label.

    As defined by RFC5890_

    In fact, this function currently only tests for being an XN--
    label.

        the class of labels that begin with the prefix "xn--" (case
        independent), but otherwise conform to the rules for LDH labels
        [is called "XN-labels"]...

        The XN-labels that are valid Punycode output are known as
        "A-labels" if they also meet the other criteria for IDNA-validity

    So bear in mind that (a) the remainder of the label may fail to
    decode properly when passed to the punycode algorithm and (b) even
    if it does decode it may result in a string that is not actually a
    valid U-Label."""
    return is_ldh_label(label) and label[:4].lower() == b'xn--'


def split_domain(domain_str, allow_wildcard=False):
    """Splits a domain string

    domain_str
        A character string, or a UTF-8 encoded binary string.

    allow_wildcard (Default: False)
        Allows the use of a single '*' character as a domain label for
        the purposes of parsing wildcard domain definitions.

    Returns a list of lower cased *ASCII* labels as character strings,
    converting U-Labels to ACE form (xn--) in the process.  For example::

        >>> split_domain('example.COM')
        >>> ['example', 'com']
        >>> split_domain(u'\\u98df\\u72ee.com.cn')
        >>> ['xn--85x722f', 'com', 'cn']

    Raises ValueError if domain_str is not valid."""
    if is_unicode(domain_str):
        domain_str = domain_str.encode('utf-8')
    domain = domain_str.split(b'.')
    result = []
    for label in domain:
        if is_ldh_label(label):
            result.append(label.lower())
        elif allow_wildcard and label == b'*':
            result.append(b'*')
        else:
            # some high-bit values
            try:
                alabel = b"xn--%s" % label.decode('utf-8').encode('punycode')
                if not is_ldh_label(alabel):
                    raise ValueError("bad label in domain: %s" % domain_str)
            except UnicodeError:
                raise ValueError("bad label in domain: %s" % repr(domain_str))
            result.append(alabel.lower())
    return [r.decode('ascii') for r in result]


def domain_in_domain(subdomain, domain):
    """Returns try if subdomain is a sub-domain of domain.

    subdomain
        A *reversed* list of strings returned by :func:`split_domain`

    domain
        A *reversed* list of strings as returned by :func:`split_domain`

    For example::

        >>> domain_in_domain(['com', 'example'],
        ...                  ['com', 'example', 'www'])
        True"""
    if len(subdomain) <= len(domain):
        i = 0
        for d in subdomain:
            if d != domain[i]:
                return False
            i += 1
        return True
    else:
        return False


def encode_domain(domain, allow_wildcard=False):
    """Returns domain correctly encoded as a binary string

    domain
        A binary or character string containing a representation of a
        domain using either U-Labels or ACE form for non-ASCII
        characters.

    allow_wildcard (Default: False)
        Allows the use of a single '*' character as a domain label for
        the purposes of encoding wildcard domain definitions.

    The result is a character string containing only ASCII encoded
    characters."""
    return '.'.join(split_domain(domain, allow_wildcard))


def is_delimiter(b):
    """Tests a character against the production delimiter

    This production is from the weaker section 5 syntax of RFC6265."""
    if b is not None:
        b = byte_value(b)
        return (b == 0x09 or
                (0x20 <= b <= 0x2F) or (0x3B <= b <= 0x40) or
                (0x5B <= b <= 0x60) or (0x7B <= b <= 0x7E))
    else:
        return False


def is_non_delimiter(b):
    """Tests a character against the production non-delimiter

    The result differs from using *not is_delimiter* only in the
    handling of None which will return False when passed to either
    function."""
    if b is not None:
        return not is_delimiter(b)
    else:
        return False


def is_non_digit(b):
    """Tests a character against the production non-digit."""
    if b is not None:
        return not grammar.is_digit(b)
    else:
        return False


def split_year(year_str):
    """Parses a year from a binary string

    Uses the generous rules in section 5.1 and returns a year value,
    adjusted using the 2-digit year algorithm documented there.

    If a year value can't be found ValueError is raised."""
    digits = []
    for b in year_str:
        if grammar.is_digit(b):
            digits.append(b)
            if len(digits) > 4:
                raise ValueError("Can't read year from %s" % year_str)
        else:
            break
    if len(digits) < 2:
        raise ValueError("Can't read year from %s" % year_str)
    year = int(join_bytes(digits))
    if year > 69 and year < 100:
        year += 1900
    elif year < 70:
        year += 2000
    return year


MONTHS = {
    b"jan": 1,
    b"feb": 2,
    b"mar": 3,
    b"apr": 4,
    b"may": 5,
    b"jun": 6,
    b"jul": 7,
    b"aug": 8,
    b"sep": 9,
    b"oct": 10,
    b"nov": 11,
    b"dec": 12}


def split_month(month_str):
    """Parses a month from a string

    Uses the generous rules in section 5.1 and returns a month value
    from 1 (January) to 12 (December).

    If a month value can't be found ValueError is raised."""
    try:
        return MONTHS[month_str[0:3].lower()]
    except KeyError:
        raise ValueError("Can't read month from %s" % month_str)


def split_day_of_month(dom_str):
    """Parses a day-of-month from a binary string

    Users the generous rules in section 5.1 and returns a single integer
    or raises ValueError if a valid day of month can't be found."""
    digits = []
    for b in dom_str:
        if grammar.is_digit(b):
            digits.append(b)
            if len(digits) > 2:
                raise ValueError("Can't read day-of-month from %s" % dom_str)
        else:
            break
    if len(digits) < 1:
        raise ValueError("Can't read day-of-month from %s" % dom_str)
    return int(join_bytes(digits))


def split_time(time_str):
    """Parses a time from a binary string

    Users the generous rules in section 5.1 and returns a triple
    of hours, minutes, seconds.  These values are unchecked!

    If the time can't be found ValueError is raised."""
    components = []
    digits = []
    for b in time_str:
        if grammar.is_digit(b):
            digits.append(b)
            if len(digits) > 2:
                raise ValueError("Can't read time from %s" % time_str)
        else:
            if len(digits) < 1:
                raise ValueError("Missing time-value in %s" % time_str)
            components.append(int(join_bytes(digits)))
            digits = []
            if len(components) == 3 or b != grammar.COLON:
                break
    if digits:
        components.append(int(join_bytes(digits)))
    if (len(components) != 3):
        raise ValueError("Can't read time from %s" % time_str)
    return tuple(components)


class CookieError(ValueError):

    """Raised when an operation violates RFC6265_ rules."""
    pass


class CookieParser(grammar.OctetParser):

    """General purpose class for parsing RFC6265_ productions

    Unlike the basic syntax functions these methods allow a longer
    string, such as that received from an HTTP header, to be parsed into
    its component parts.

    Methods follow inherited naming conventions, require\\_ methods
    raise a ValueError if the production is not matched whereas parse\\_
    methods optionally parse a production if it is present and return
    None if not present."""

    def require_set_cookie_string(self, strict=False):
        """Parses the set-cookie-string production

        strict (Default: False)
            Use the stricter section 4 syntax rules instead of the more
            permissive algorithm described in section 5.2

        This is the format of the Set-Cookie header, it returns a
        :class:`Cookie` instance or None if this cookie definition
        should be ignored."""
        if strict:
            return self._require_set_cookie_string_strict()
        try:
            name, value = self.require_name_value_pair()
        except ValueError:
            name, value = None, None
        if self.parse(b';'):
            attrs = self.parse_until(None)
        else:
            attrs = None
        if not name:
            # ignore this definition!
            return None
        expires = max_age = domain = path = None
        secure = http_only = False
        while attrs is not None:
            pos = attrs.find(b';')
            if pos < 0:
                av = attrs
                attrs = None
            else:
                av = attrs[:pos]
                attrs = attrs[pos + 1:]
            pos = av.find(b'=')
            if pos < 0:
                aname = av
                avalue = ''
            else:
                aname = av[:pos].strip()
                avalue = av[pos + 1:].strip()
            aname_lower = aname.lower()
            if aname_lower == b"expires":
                p = CookieParser(avalue)
                expires = p.require_cookie_date()
            elif aname_lower == b"max-age":
                if avalue and avalue[0] == HYPHEN:
                    if len(avalue) == 1:
                        avalue = b"0"
                    else:
                        for c in avalue[1:]:
                            if not grammar.is_digit(c):
                                avalue = ''
                                break
                else:
                    for c in avalue:
                        if not grammar.is_digit(c):
                            avalue = ''
                            break
                if avalue:
                    max_age = int(avalue)
            elif aname_lower == b'domain':
                if avalue:
                    if avalue[0] == FULL_STOP:
                        domain = avalue[1:].lower()
                    else:
                        domain = avalue.lower()
                    domain = Cookie.cstr(domain)
            elif aname_lower == b"path":
                if avalue and avalue[0] == grammar.SOLIDUS:
                    path = Cookie.cstr(avalue)
            elif aname_lower == b"secure":
                secure = True
            elif aname_lower == b"httponly":
                http_only = True
        return Cookie(name, value, expires=expires, max_age=max_age,
                      domain=domain, path=path, secure=secure,
                      http_only=http_only)

    def require_cookie_string(self, strict=False):
        """Parses the value of a Cookie header.

        strict (Default: False)
            Indicates if stricter section 4 parsing is required.

        Returns a dictionary of values, the keys are the names of the
        cookies in the cookie string and the values are either strings
        or, in the case of multiply defined names, sets of strings.  We
        use sets as the specification makes it clear that you should not
        rely on the order of such definitions.  All strings (including
        cookie names) are binary strings."""
        while True:
            # loop around in case of double folds, this is the
            # difference between OWS and LWS
            if not self.parse_lws():
                break
        cookie_list = {}
        try:
            savepos = self.pos
            while True:
                if strict:
                    name, value = self.require_cookie_pair()
                else:
                    name, value = self.require_name_value_pair()
                if name in cookie_list:
                    values = cookie_list[name]
                    if not isinstance(values, set):
                        values = set((values, ))
                        cookie_list[name] = values
                    values.add(value)
                else:
                    cookie_list[name] = value
                savepos = self.pos
                if self.parse(b';'):
                    # bit generous here, accept multiple spaces
                    if strict:
                        self.require(b' ')
                    else:
                        while self.the_char is not None:
                            if not self.parse_one(b' \t'):
                                break
                    continue
                else:
                    break
            while True:
                # more OWS
                if not self.parse_lws():
                    break
        except ValueError:
            self.setpos(savepos)
        return cookie_list

    def _require_set_cookie_string_strict(self):
        name, value = self.require_cookie_pair()
        expires = max_age = domain = path = None
        secure = http_only = False
        extensions = []
        while self.parse(b';'):
            # we just parsed a ';' which must be followed by SP
            if not self.parse(b' '):
                self.setpos(self.pos - 1)
                break
            if self.parse_insensitive(b'expires='):
                sane_date = self.parse_sane_cookie_date()
                if ((self.the_char is None or
                        self.the_char == grammar.SEMICOLON) and
                        sane_date is not None):
                    expires = sane_date
                    continue
            elif self.parse_insensitive(b'max-age='):
                digits = self.parse_digits(min=1)
                if digits and digits[0] != '0':
                    max_age = int(digits)
                    continue
            elif self.parse_insensitive(b'domain='):
                domain = self.parse_until(b';')
                domain = Cookie.cstr(domain)
                continue
            elif self.parse_insensitive(b'path='):
                path = Cookie.cstr(self.parse_until(b';'))
                continue
            elif self.parse_insensitive(b'secure'):
                if self.the_char is None or self.the_char == grammar.SEMICOLON:
                    secure = True
                    continue
            elif self.parse_insensitive(b'httponly'):
                if self.the_char is None or self.the_char == grammar.SEMICOLON:
                    http_only = True
                    continue
            # extension
            extensions.append(self.parse_cookie_av())
        return Section4Cookie(
            name, value, expires=expires, max_age=max_age,
            domain=domain, path=path, secure=secure,
            http_only=http_only, extensions=extensions)

    def require_name_value_pair(self):
        """Returns a (name, value) pair

        Parsed according to the looser section 5 syntax so will allow
        almost anything as a name and value provided it has an '='."""
        nvpair = self.parse_until(b';')
        pos = nvpair.find(b'=')
        if pos < 0:
            raise ValueError("Expected '=' in name-value-pair: %s" % nvpair)
        name = nvpair[:pos].strip()
        value = nvpair[pos + 1:].strip()
        return name, value

    def require_cookie_pair(self):
        """Returns a (name, value) pair parsed according to cookie-pair

        Parsed according to the stricter section 4 syntax so will only
        accept valid tokens as names, the '=' is required and the value
        must be parseable with :meth:`require_cookie_value`."""
        name = self.require_production(self.parse_token())
        self.require(b'=')
        value = self.require_cookie_value()
        return name, value

    def parse_cookie_pair(self):
        """See: :meth:`require_cookie_pair`

        If not parsed returns (None, None) rather than just None."""
        result = self.parse_production(self.require_cookie_pair)
        if result is None:
            return None, None
        else:
            return result

    def require_cookie_value(self):
        """Returns a cookie-value (binary) string.

        Parsed according to the stricter section 4 syntax so will not
        allow whitespace, comma, semicolon or backslash characters and
        will only allow double-quote when it is used to completely
        "enclose" the value, in which case the double-quotes are still
        considered to be part of the value string."""
        value = []
        if self.parse(b'"'):
            dqflag = True
        else:
            dqflag = False
        while self.the_char is not None and is_cookie_octet(self.the_char):
            value.append(self.the_char)
            self.next_char()
        if dqflag:
            self.require(b'"')
            value[0:0] = (grammar.DQUOTE, )
            value.append(grammar.DQUOTE)
            value = join_bytes(value)
        else:
            value = join_bytes(value)
        return value

    def parse_cookie_av(self):
        """Parses a cookie-av string.

        This production is effectively the production for extension-av
        in the stricter section 4 syntax.  Effectively it returns
        everything up to but not including the next ';' or CTL
        character.

        It never returns None, if nothing is found it returns an empty
        string instead."""
        av = []
        while self.the_char is not None and self.the_char != grammar.SEMICOLON:
            if grammar.is_ctl(self.the_char):
                break
            else:
                av.append(self.the_char)
                self.next_char()
        return join_bytes(av)

    def parse_sane_cookie_date(self):
        """Parses the sane-cookie-date production.

        This is the stricter syntax defined in section 4.  The returns
        result is a :class:`~params.FullDate` instance."""
        savepos = self.pos
        date_str = self.parse_until(b'GMT')
        date_str = date_str + self.parse(b'GMT')
        try:
            return params.FullDate.from_http_str(date_str)
        except ValueError:
            self.setpos(savepos)
            return None

    def parse_cookie_date_tokens(self):
        """Parses a date-token-list

        This uses the weak section 5.1 syntax

        It never returns None, if there are no tokens then it returns an
        empty list.  Delimiters are always discarded."""
        token_list = []
        while is_delimiter(self.the_char):
            self.next_char()
        while self.the_char is not None:
            token = []
            while is_non_delimiter(self.the_char):
                token.append(self.the_char)
                self.next_char()
            token_list.append(join_bytes(token))
            while is_delimiter(self.the_char):
                self.next_char()
        return token_list

    def require_cookie_date(self):
        """Parses a date value

        This uses the weak section 5.1 syntax and the algorithm
        described there.  It absorbs almost all errors returning None if
        this date value should be ignored - but warnings are logged to
        alert you to the failure.  The implications of replacing a date
        with None in this syntax are typically that a cookie that is
        supposed to be persistent become session only.  However, if this
        was an attempt to remove a cookie with a very early date then
        the failure could cause more problems.

        If successful, it returns a :class:`~params.FullDate`
        instance."""
        token_list = self.parse_cookie_date_tokens()
        time_str = None
        dom_str = None
        month_str = None
        year_str = None
        hour = minute = second = day = month = year = None
        for token in token_list:
            if not time_str:
                try:
                    hour, minute, second = split_time(token)
                    time_str = token
                    continue
                except ValueError:
                    pass
            if not dom_str:
                try:
                    day = split_day_of_month(token)
                    dom_str = token
                    continue
                except ValueError:
                    pass
            if not month_str:
                try:
                    month = split_month(token)
                    month_str = token
                    continue
                except ValueError:
                    pass
            if not year_str:
                try:
                    year = split_year(token)
                    year_str = token
                    continue
                except ValueError:
                    pass
        if not time_str:
            logging.warning("No time found in %s", b''.join(token_list))
            return None
        if not dom_str:
            logging.warning(
                "No day of month found in %s", b''.join(token_list))
            return None
        if not month_str:
            logging.warning("No month found in %s", b''.join(token_list))
            return None
        if not year_str:
            logging.warning("No year found in %s", b''.join(token_list))
            return None
        if day < 1 or day > 31:
            logging.warning("Bad day found in %s", b''.join(token_list))
            return None
        if year < 1601:
            logging.warning("Cookie too old: %s", b''.join(token_list))
            return None
        if hour > 23 or minute > 59 or second > 59:
            logging.warning("Bad time found in: %s", b''.join(token_list))
            return None
        century = year // 100
        year = year % 100
        try:
            return params.FullDate(
                date=iso.Date(century=century, year=year, month=month,
                              day=day),
                time=iso.Time(hour=hour, minute=minute, second=second,
                              zdirection=0))
        except iso.DateTimeError:
            logging.warning("Bad cookie date: %s", b''.join(token_list))
            return None


class Cookie(params.Parameter):

    """Represents the definition of a cookie

    Where binary strings are required, character strings will be
    accepted and converted using UTF-8 but non-ASCII characters are
    *not* portable and should be avoided.

    name
        The name of the cookie as a binary string.

    value
        The value of the cookie as a binary string.

    path (optional)
        A character string containing the path of the cookie.  If None
        then the 'directory' of the page that returned the cookie will
        be used by the client.

    domain (optional)
        A character string containing the domain of the cookie.  If None
        then the host name of the server that returned the cookie will
        be used by the client and the cookie will be treated as 'host
        only'.

    expires (optional)
        An :class:`~pyslet.iso8601.TimePoint` instance.  If None then the
        cookie will be treated as a session cookie by the client.

    max_age (optional)
        An integer, the length of time before the cookie expires in
        seconds.  Overrides the expires value.  If None then the value
        of expires is used instead, if both are None then the cookie
        will be treated as a session cookie by the client.

    secure (Default: False)
        Whether or not the cookie should be exposed only over secure
        protocols, such as https.

    http_only (Default: False)
        Whether or not the cookie should be exposed only via the HTTP
        protocol.  Recommended value: True!

    extensions
        A list of binary strings containing attribute extensions.  The
        strings should be of the form name=value but this is not
        enforced.

    Instances can be converted to strings using the builtin str function
    and the output that results is a valid Set-Cookie header value."""

    def __init__(self, name, value, path=None, domain=None, expires=None,
                 max_age=None, secure=False, http_only=False, extensions=None):
        now = time.time()
        #: the cookie's name
        self.name = self.bstr(name)
        #: the cookie's name
        self.value = self.bstr(value)
        #: the cookie's path
        self.path = path
        if domain:
            if domain[0:1] == '.':
                # strip leading '.'
                domain = domain[1:]
            elif domain[-1:] == '.':
                domain = None
        #: the cookie's domain
        self.domain = domain
        #: the cookie's secure flag
        self.secure = secure
        #: the cookie's httponly flag
        self.http_only = http_only
        #: the creation time of the cookie, initialised to the current
        #: time as returned by the builtin time.time function.
        self.creation_time = now
        #: the last access time of the cookie, initialised to the
        #: current time as returned by the builtin time.time function.
        self.access_time = now
        if max_age is None:
            #: the max_age value
            self.max_age = None
            if expires is None:
                #: the expiry time of the cookie, as an integer
                #: compatible with the value returned by time.time
                self.expires_time = None
            else:
                self.expires_time = expires.get_unixtime()
        else:
            if max_age <= 0:
                self.expires_time = 0
            else:
                self.expires_time = now + max_age
            self.max_age = max_age
        #: the expires value as passed to the constructor, this is
        #: preserved and is used when serialising the definition even if
        #: Max-Age is also in effect.  Some older clients may not
        #: support Max-Age and they will look at the Expires time
        #: instead.
        self.expires = expires
        #: the list of extensions
        if extensions:
            self.extensions = [self.bstr(e) for e in extensions]
        else:
            self.extensions = None

    @classmethod
    def bstr(cls, arg):
        """Overridden to use UTF-8 for binary encoding of arguments

        This method is used to convert arguments provided in
        constructors to the binary strings required by some attributes.
        The default implementation uses ISO-8859-1 in keeping with the
        general HTTP specification (although no encoding is portable
        across a wide range of browser and server implementations).

        We override it here for Cookies because the cookie specification
        hints that UTF-8 would be an appropriate choice for displaying
        binary information found in cookies."""
        if is_unicode(arg):
            return arg.encode('utf-8')
        else:
            return arg

    @classmethod
    def cstr(cls, value):
        """Used to interpret binary strings in cookies

        This method can be used as a default way of interpreting binary
        information found in cookies.  It tries to decode using UTF-8
        but, if that fails, it reverts to the default HTTP encoding of
        ISO-8859-1.  It is used sparingly, in most cases binary values
        are left uninterpreted but attributes such as the path and
        domain must be interpreted in relation to components of the URL
        and URLs use characters.

        For clarity, a domain name containing non-ASCII characters
        (U-labels) that has simply been UTF-8 encoded will be converted
        back to the original form (with U-labels) whereas the same
        domain correctly encoded in ACE format (xn--) will be unchanged
        by this decoding."""
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.decode('iso-8859-1')

    def to_bytes(self):
        components = [b"%s=%s" % (self.name, self.value)]
        if self.path:
            components.append(b"Path=%s" % self.path.encode('ascii'))
        if self.domain:
            components.append(b"Domain=%s" %
                              encode_domain(self.domain).encode('ascii'))
        if self.expires is not None:
            components.append(b"Expires=%s" % to_bytes(self.expires))
        if self.max_age is not None:
            components.append(b"Max-Age=%s" % to_bytes(self.max_age))
        if self.secure:
            components.append(b"Secure")
        if self.http_only:
            components.append(b"HttpOnly")
        if self.extensions:
            components = components + self.extensions
        return b'; '.join(components)

    @classmethod
    def from_str(cls, src):
        """Creates a new instance from a src string

        The string is parsed using the generous parsing rules of Section
        5 of the specification.  Returns a new instance."""
        p = CookieParser(src)
        result = p.require_set_cookie_string()
        p.require_end("Set-Cookie string")
        return result

    def is_persistent(self):
        """Returns True if there is no expires time on this cookie.

        The expires time is calculated from either the max_age or
        expires attributes."""
        return self.expires_time is not None

    def is_hostonly(self):
        """Returns True if this cookie is 'host only'

        In other words, it should only be sent to the host that
        set the cookie originally."""
        return self.domain is None

    def touch(self, now=None):
        """Updates the cookie's last access time.

        now (optional)
            Time value to use. This can be in the past or the future and
            improves performance when updating multiple cookies
            simultaneously."""
        if now is None:
            now = time.time()
        self.access_time = now

    def expired(self, now=None):
        """Returns True if the cookie has expired

        now (optional)
            Time value at which to test, this can be in the past or the
            future and is largely provided to aid testing and also to
            improve performance when a large number of cookies need to
            be tested sequentially."""
        if now is None:
            now = time.time()
        if self.expires_time is None:
            return False
        else:
            return now > self.expires_time


class Section4Cookie(Cookie):

    """Represents a strict cookie definition

    The purpose of this class is wrap :class:`Cookie` to enforce
    more validation rules on the definition to ensure that the
    cookie adheres to section 4 syntax, and not just the broader
    section 5 syntax.

    Names are checked for token validity, values are checked against the
    syntax for cookie-value and the attributes are checked against the
    other constraints in the specification.

    The built-in str function will return a string that is valid against
    the section 4 syntax."""

    def __init__(self, *args, **kwargs):
        super(Section4Cookie, self).__init__(*args, **kwargs)
        # check that name is a token
        # TODO
        # check that value is a valid value
        # TODO
        # check that domain is a valid domain
        # TODO
        # check that path is a valid path
        # TODO
        # check that expires date is in UTC and is post-1600
        if self.extensions:
            attrs = set()
            if self.domain:
                attrs.add(b'domain')
            if self.path:
                attrs.add(b'path')
            if self.max_age is not None:
                attrs.add(b'max_age')
            if self.expires is not None:
                attrs.add(b'expires')
            if self.secure:
                attrs.add(b'secure')
            if self.http_only:
                attrs.add(b'httponly')
            for ext in self.extensions:
                if not ext:
                    continue
                ext = ext.split(b'=')[0].lower()
                if ext:
                    if ext in attrs:
                        raise CookieError("Duplicate attribute: %s" % ext)
                    attrs.add(ext)

    @classmethod
    def from_str(cls, src):
        """Creates a new instance from a src string

        Overridden to provide stricter parsing.  This may still appear
        more generous than expected because the strict syntax allows an
        unrestricted set of attribute extensions so unrecognised
        attributes will often be recorded but not in any useful way."""
        p = CookieParser(src)
        result = p.require_set_cookie_string(strict=True)
        p.require_end("Set-Cookie string")
        return result


class CookieDNode(object):

    def __init__(self, name):
        self.name = name
        self.public = True
        self.private = False
        self.public_depth = 0
        self.nodes = {}
        self.cookies = {}


class CookieStore(object):

    """An object that provides in-memory storage for cookies.

    There are no initialisation options.  By default, the cookie storage
    will refuse all 'domain' cookies.  That is, cookies that have a
    domain attribute.  If a domain cookie is received from a host that
    exactly matches its domain attribute then it is converted to a
    host-only cookie and *is* stored.

    This behaviour can be changed by adding exclusions (in the form of
    calls to :meth:`add_private_suffix`) or by loading in a new public
    prefix database using :meth:`set_public_list`."""

    def __init__(self):
        self.lock = threading.RLock()
        self.nodes = {}
        # effectively infinity, all domains are public we accept no
        # domain cookies at all
        self.public_depth = 255

    def set_cookie(self, url, c):
        """Store a cookie.

        urL
            A :class:`~pyslet.rfc2396.URI` instance representing the
            resource that is setting the cookie.

        c
            A :class:`Cookie` instance, typically parsed from a
            Set-Cookie header returned when requesting the resource at
            url.

        If the cookie can't be set then :class:`CookieError` is raised.
        Reasons why a cookie might be refused are a mismatch between a
        domain attribute and the url, or an attempt to set a cookie in a
        public domain, such as 'co.uk'."""
        # start with the domain of the cookie
        if not isinstance(url, params.HTTPURL) and c.http_only:
            raise CookieError(
                "Can't set http_only cookie with this protocol: %s" %
                url.scheme)
        try:
            host_str = url.host
            host = split_domain(host_str)
            host.reverse()
        except ValueError:
            # the domain is an IP address, match whole
            host = [host]
        domain = c.domain
        if domain is None:
            domain_str = host_str
            domain = host
        else:
            domain_str = domain
            domain = split_domain(domain)
            domain.reverse()
            if not domain_in_domain(domain, host):
                # you can't set this cookie from host
                raise CookieError(
                    "Can't set cookie for %s from %s" %
                    (domain_str, host_str))
        # check the path
        if c.path is None:
            if url.abs_path and url.abs_path[0] == '/':
                path = url.abs_path.split('/')
                if len(path) > 2:
                    c.path = '/'.join(path[:-1])
                else:
                    c.path = '/'
            else:
                c.path = '/'
        # now find the domain node and insert the cookie
        with self.lock:
            dnode = self
            for d in domain:
                old_node = dnode
                dnode = old_node.nodes.get(d, None)
                if dnode is None:
                    dnode = self._expand_node(old_node, d)
            if dnode.public:
                # if this is a public node, check host
                if len(domain) == len(host):
                    # force the cookie to be host only
                    c.domain = None
                else:
                    # ignore the cookie
                    raise CookieError(
                        "Cookie for public domain %s ignored" % domain_str)
            old_cookie = dnode.cookies.get((c.name, c.path), None)
            if old_cookie is not None:
                c.creation_time = old_cookie.creation_time
                del dnode.cookies[(c.name, c.path)]
            if not c.expired():
                dnode.cookies[(c.name, c.path)] = c

    def search(self, url):
        """Searches for cookies that match a resource

        url
            A :class:`~pyslet.rfc2396.URI` instance representing the
            resource that we want to find cookies for.

        The return result is a sorted list of :class:`Cookie` objects.
        The sort order is defined in the specification, longer paths are
        sorted first, otherwise older cookies are listed before newer
        ones.

        Expired cookies are automatically removed from the repository
        and all cookies returned have their access time updated to the
        current time."""
        try:
            host_str = url.host
            host = split_domain(host_str)
            host.reverse()
        except ValueError:
            # the domain is an IP address, match whole
            host = [host]
        matched = []
        dpos = 0
        now = time.time()
        with self.lock:
            dnode = self
            for d in host:
                old_node = dnode
                dnode = old_node.nodes.get(d, None)
                if dnode is None:
                    break
                dpos += 1
                # True if we are matching the full host
                host_match = (dpos == len(host))
                # all cookies in dnode should be considered
                expired = []
                for c in dict_values(dnode.cookies):
                    if c.expired(now):
                        expired.append(c)
                        continue
                    if c.domain is None and not host_match:
                        continue
                    # do a path match
                    if url.abs_path is None:
                        continue
                    if len(url.abs_path) < len(c.path):
                        continue
                    if not (url.abs_path.startswith(c.path) and
                            (c.path[-1] == '/' or
                             url.abs_path[len(c.path):len(c.path) + 1] ==
                             '/')):
                        continue
                    # we have a domain and path match
                    if c.secure and not isinstance(url, params.HTTPSURL):
                        continue
                    if c.http_only and not isinstance(url, params.HTTPURL):
                        continue
                    matched.append(c)
                # clean up expired cookies
                for c in expired:
                    del dnode.cookies[(c.name, c.path)]
                for c in matched:
                    c.touch(now)
        matched.sort(key=lambda x: (-len(x.path), x.creation_time))
        return matched

    def expire_cookies(self, now=None, dnode=None):
        """Expire stored cookies.

        now (optional)
            The time at which to expire the cookies, defaults to the
            current time.  This can be used to expire cookies based on
            some past or future point.

        Iterates through all stored cookies and removes any that have
        expired."""
        with self.lock:
            if dnode is None:
                dnode = self
            if now is None:
                now = time.time()
            old_node = dnode
            for dnode in dict_values(old_node.nodes):
                # all cookies in dnode should be considered
                expired = []
                for c in dict_values(dnode.cookies):
                    if c.expired(now):
                        expired.append(c)
                        continue
                # clean up expired cookies
                for c in expired:
                    del dnode.cookies[(c.name, c.path)]
                # now recurse
                self.expire_cookies(now, dnode)

    def end_session(self, now=None, dnode=None):
        """Expire all session cookies.

        now (optional)
            The time at which to expire cookies.  See
            :meth:`expire_cookies` for details.

        Iterates through all stored cookies and removes any session
        cookies *in addition*  to any that have expired."""
        with self.lock:
            if dnode is None:
                dnode = self
            if now is None:
                now = time.time()
            old_node = dnode
            for dnode in dict_values(old_node.nodes):
                # all cookies in dnode should be considered
                expired = []
                for c in dict_values(dnode.cookies):
                    if c.expired(now) or not c.is_persistent():
                        expired.append(c)
                        continue
                # clean up expired cookies
                for c in expired:
                    del dnode.cookies[(c.name, c.path)]
                # now recurse
                self.end_session(now, dnode)

    def add_public_suffix(self, suffix):
        """Marks a domain suffix as being public.

        suffix
            A string: a public suffix, may contain wild-card
            characters to match any entire label, for example:
            "*.uk", "*.tokyo.jp", "com"

        Once a domain suffix is marked as being public *future* cookies
        will not be stored against that suffix (except in the unusual
        case where a cookie is 'host only' and the host name is a public
        suffix)."""
        domain = split_domain(suffix, allow_wildcard=True)
        domain.reverse()
        with self.lock:
            dnode = self
            dcount = len(domain)
            for d in domain:
                old_node = dnode
                dnode = old_node.nodes.get(d, None)
                if dnode is None:
                    if d == '*':
                        # wild card handling
                        if dcount == 1:
                            # rule finished with a wild card
                            if old_node.public_depth < 1:
                                old_node.public_depth = 1
                            # mark everthing at this level public
                            for child in dict_values(old_node.nodes):
                                if not child.private:
                                    child.public = True
                        else:
                            # create a wild node
                            dnode = self._expand_node(old_node, d)
                    else:
                        # create a new node
                        dnode = self._expand_node(old_node, d)
                        # force this to be public
                        dnode.public = True
                elif dcount == 1:
                    # this is the last label in the suffix, mark it
                    # as public if it isn't explicitly private
                    if not dnode.private:
                        dnode.public = True
                    if d == '*':
                        # mark all children public too
                        for child in dict_values(old_node.nodes):
                            if not child.private:
                                child.public = True
                dcount -= 1

    def add_private_suffix(self, suffix):
        """Marks a domain suffix as being private.

        suffix
            A string: a public suffix, may contain wild-card
            characters to match any entire label, for example:
            "example.co.uk", "\\*.tokyo.jp", "com"

        This method is required to override an existing public rule,
        thereby ensuring that *future* cookies can be stored against
        domains matching this suffix."""
        domain = split_domain(suffix, allow_wildcard=True)
        domain.reverse()
        with self.lock:
            dnode = self
            dcount = len(domain)
            for d in domain:
                old_node = dnode
                dnode = old_node.nodes.get(d, None)
                if dnode is None:
                    if d == '*':
                        # wild card handling
                        if dcount == 1:
                            # rule finished with a wild card - this is
                            # supposed to be an exception to a previous wild
                            # card rule so assume all domains here are
                            # excepted and hence private
                            old_node.public_depth = 0
                            # mark everthing at this level private
                            for child in dict_values(old_node.nodes):
                                child.private = True
                                child.public = False
                        else:
                            # create a wild node
                            dnode = self._expand_node(old_node, d)
                    else:
                        # create a new node
                        dnode = self._expand_node(old_node, d)
                        if dcount == 1:
                            # private node
                            dnode.private = True
                            dnode.public = False
                elif dcount == 1:
                    # this is the last label in the suffix, mark it
                    # as private
                    dnode.private = True
                    dnode.public = False
                    if d == '*':
                        # mark all children public too
                        for child in dict_values(old_node.nodes):
                            child.private = True
                            child.public = False
                dcount -= 1

    @classmethod
    def fetch_public_suffix_list(
            cls, fpath,
            src="https://publicsuffix.org/list/effective_tld_names.dat",
            overwrite=False):
        """Fetches the public suffix list and saves to fpath

        fpath
            A local file path to save the file in

        src
            A string or :class:`~pyslet.rfc2396.URI` instance pointing
            at the file to retrieve.  It default to the data file
            https://publicsuffix.org/list/effective_tld_names.dat

        overwrite (Default: False)
            A flag to force an overwrite of an existing file at fpath,
            by default, if fpath already exists this method returns
            without doing anything."""
        from . import client as http
        if not os.path.exists(fpath):
            c = http.Client()
            request = http.ClientRequest(src)
            c.process_request(request)
            if request.status == 200 and request.res_body:
                with open(fpath, 'wb') as f:
                    f.write(request.res_body)
            else:
                logging.error("Failed to download list from %s", str(src))
            c.close()

    def set_public_list(self, black_list, tld_depth=1):
        """Loads a new public suffix list

        black_list
            A string containing a list of public suffixes in the format
            defined by: https://publicsuffix.org/list/

        tld_depth (Default: 1)
            The depth of domain that will be automatically treated as
            public.  The default is 1, meaning that all top-level domains
            will be treated as public.

        This methods loads data from a public list using calls to
        :meth:`add_public_prefix` and :meth:`add_private_prefix`, the
        latter being for exclusion rules.

        If you use the full list published by the Public Suffix List
        project it is safe to use the default tld_depth value of 1:

        https://publicsuffix.org/list/effective_tld_names.dat

        If you want to load a much smaller list then you should focus
        on a large value for tld_depth (255 for example) and documenting
        exclusions only.  For example::

            // Exclusion list
            // Accept domain cookies for example.com, example.co.uk
            !example.com
            !example.co.uk"""
        self.public_depth = tld_depth
        lines = black_list.splitlines()
        for line in lines:
            if not line or line[0:2] == '//':
                continue
            line = line.split()
            line = line[0]
            if not line:
                continue
            try:
                if line[0:1] == '!':
                    self.add_private_suffix(line[1:])
                else:
                    self.add_public_suffix(line)
            except ValueError:
                logging.warning("Ignoring bad rule in black_list: %s",
                                line)

    def test_public_domain(self, domain_str):
        """Test if a domain is public

        domain_str
            A domain string, e.g., "www.example.com"

        Returns True if this domain is marked as public, False
        otherwise."""
        domain = split_domain(domain_str)
        domain.reverse()
        with self.lock:
            dnode = self
            dcount = len(domain)
            for d in domain:
                old_node = dnode
                dnode = old_node.nodes.get(d, None)
                if dnode is None:
                    # dcount is the number of labels left in domain
                    if dcount > old_node.public_depth:
                        return False
                    else:
                        return True
                elif dcount == 1:
                    # last label, this domain matches this rule exactly
                    return dnode.public
                dcount -= 1

    def get_registered_domain(self, domain_str, u_labels=False):
        """Returns the publicly registered portion of a domain

        domain_str
            A domain string, e.g., "www.example.com"

        u_labels (Default: False)
            Flag indicating whether or not to return unicode
            labels instead of encoded ASCII Labels.

        Compares this domain against the database of public domains and
        returns the publicly registered part of the domain.  For
        example, www.example.com would typically return example.com and
        www.example.co.uk would typically return example.co.uk.

        If domain_str is already a publicly registered domain then it
        returns None. If domain_str is itself None, None is also
        returned.

        Initially, all domains are marked as public so this function
        will always return None.  It iss intended for use after a public
        list has been loaded, such as the public suffix list (see
        :meth:`set_public_list`)."""
        if domain_str is None:
            return None
        domain = split_domain(domain_str)
        domain.reverse()
        if domain and domain[-1] == '':
            # ignore domains with a leading '.'
            return None
        with self.lock:
            dnode = self
            dcount = len(domain)
            matched = []
            for d in domain:
                old_node = dnode
                dnode = old_node.nodes.get(d, None)
                if dnode is None:
                    # dcount is the number of labels left in domain
                    if dcount > old_node.public_depth:
                        # private domain with public prefix
                        matched = matched + domain[
                            -dcount:len(domain) - dcount +
                            old_node.public_depth + 1]
                    else:
                        # public domain
                        matched = None
                    break
                elif not dnode.public:
                    # that's it, don't add any more labels after this one
                    matched.append(d)
                    break
                elif dcount == 1:
                    # last label, this domain matches this rule exactly
                    matched = None
                    break
                matched.append(d)
                dcount -= 1
        if matched is None:
            return None
        matched.reverse()
        if u_labels:
            matched = [u[4:].decode('punycode') if is_a_label(u) else
                       u.decode('utf-8') for u in matched]
        return '.'.join(matched)

    def check_public_suffix(self, domain_str, match_str):
        """See Public Suffix Test Data for details.

        http://mxr.mozilla.org/mozilla-central/source/netwerk/test/unit/data/test_psl.txt?raw=1

        Returns True if there is a match, False otherwise. Negative
        results are logged at ERROR level.  Used for testing the public
        suffixes loaded with :meth:`set_public_list`."""
        matched = self.get_registered_domain(
            domain_str, is_unicode(match_str))
        if matched is None:
            if match_str is None:
                return True
            else:
                logging.error("Bad match: %s and %s; found None",
                              domain_str, match_str)
                return False
        elif match_str != matched:
            logging.error("Bad match: %s and %s; found %s",
                          domain_str, match_str, repr(matched))
            return False
        else:
            return True

    def _copy_node(self, src_node, label=None):
        if label is None:
            label = src_node.name
        dnode = CookieDNode(label)
        dnode.public = src_node.public
        dnode.private = src_node.private
        dnode.public_depth = src_node.public_depth
        for src_child in dict_values(src_node.nodes):
            child = self._copy_node(src_child)
            dnode.nodes[child.name] = child
        return dnode

    def _expand_node(self, from_node, label):
        # create a new node
        if label != '*' and '*' in from_node.nodes:
            # expand by copying the wild node
            wild_node = from_node.nodes['*']
            # copies any children too, feels painful but there won't
            # often be children and when then is there won't be many
            dnode = self._copy_node(wild_node, label)
        else:
            dnode = CookieDNode(label)
            # expand by copying information from parent
            if from_node.public_depth:
                dnode.public = True
                dnode.public_depth = from_node.public_depth - 1
            else:
                dnode.public = False
                dnode.public_depth = 0
        from_node.nodes[label] = dnode
        return dnode
