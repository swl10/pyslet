#! /usr/bin/env python

import base64

from ..py2 import is_string, range3
from .. import rfc2396 as uri
from .grammar import (
    BadSyntax,
    COMMA,
    EQUALS_SIGN,
    quote_string)
from .params import Parameter, ParameterParser


class Challenge(Parameter):

    """Represents an HTTP authentication challenge.

    Instances are created from a scheme and a variable length list of
    3-tuples containing parameter (name, value, qflag) values.  The
    types of the items are as follows:

        name
            A character string containing the token that names the
            parameter

        value
            A binary string representing the parameter value.

        qflag
            a boolean indicating that the value must always be quoted,
            even if it is a valid token.

    All Challenges require a realm parameter, if omitted a realm of
    "Default" is used.

    Instances behave like read-only lists of (name,value) pairs
    implementing len, indexing and iteration in the usual way. Instances
    also support basic key lookup of parameter names by implementing
    __contains__ and __getitem__ (which returns the parameter value and
    raises KeyError for undefined parameters).  Name look-up handles
    case sensitivity by looking first for a case-sensitive match and
    then for a case insensitive match.  Instances are not truly
    dictionary like."""

    #: A dictionary mapping lower-case auth schemes onto the special
    #: classes used to represent their challenge messages
    scheme_class = {}

    #: a scheme-specific flag indicating whether of not the scheme is
    #: parsable.  Some schemes use the WWW-Authenticate header but do
    #: not adhere to the syntax past the scheme name.
    can_parse = True

    @classmethod
    def register(cls, scheme, challenge_class):
        """Registers a class to represent a challenge in scheme

        scheme
            A string representing an auth scheme, e.g., 'Basic'.  The
            string is converted to lower-case before it is registered
            to allow for case insensitive look-up.

        challenge_class
            A class derived from Challenge that is used to represent a
            Challenge issued using that scheme

        If a class has already been registered for the scheme it is
        replaced.  The mapping is kept in the :attr:`scheme_class`
        dictionary."""
        cls.scheme_class[scheme.lower()] = challenge_class

    def __init__(self, scheme, *params):
        self.scheme = scheme     #: the name of the schema
        self._params = list(params)
        self._pdict = {}
        for i in range3(len(self._params)):
            pn, pv, pq = self._params[i]
            if not isinstance(pv, bytes):
                # need to munge this value
                pv = self.bstr(pv)
                self._params[i] = (pn, pv, pq)
            self._pdict[pn] = pv
            _pn = pn.lower()
            if _pn not in self._pdict:
                self._pdict[_pn] = pv
        if "realm" not in self._pdict:
            self._params.append(("realm", b"Default", True))
            self._pdict["realm"] = b"Default"
        self.protectionSpace = None
        """an optional protection space indicating the scope of this
        challenge.  When the HTTP client receives a challenge this is
        set to the URL representing the scheme/host/port of the
        server."""

    @classmethod
    def from_str(cls, source):
        """Creates a Challenge from a *source* string."""
        p = AuthorizationParser(source, ignore_sp=False)
        p.parse_sp()
        c = p.require_challenge()
        p.parse_sp()
        p.require_end("challenge")
        return c

    @classmethod
    def list_from_str(cls, source):
        """Creates a list of Challenges from a *source* string."""
        p = AuthorizationParser(source)
        challenges = []
        while True:
            c = p.parse_production(p.require_challenge)
            if c is not None:
                challenges.append(c)
            if not p.parse_separator(COMMA):
                break
        p.require_end("challenge")
        return challenges

    def to_bytes(self):
        result = [self.scheme.encode('ascii')]
        params = []
        for pn, pv, pq in self._params:
            params.append(b"%s=%s" % (pn.encode('ascii'),
                                      quote_string(pv, force=pq)))
        if params:
            result.append(b', '.join(params))
        return b' '.join(result)

    def __repr__(self):
        return "Challege(%s, %s)" % (repr(self.scheme),
                                     ','.join(repr(p) for p in self._params))

    def __len__(self):
        return len(self._params)

    def __getitem__(self, index):
        if is_string(index):
            # look up by key, case sensitive first
            result = self._pdict.get(index, None)
            if result is None:
                result = self._pdict.get(index.lower(), None)
            if result is None:
                raise KeyError(index)
            return result
        else:
            return self._params[index]

    def __iter__(self):
        return self._params.__iter__()

    def __contains__(self, key):
        return key in self._pdict or key.lower() in self._pdict


class BasicChallenge(Challenge):

    """Represents an HTTP Basic authentication challenge."""

    def __init__(self, *params):
        super(BasicChallenge, self).__init__("Basic", *params)


Challenge.register('Basic', BasicChallenge)


class Credentials(Parameter):

    """An abstract class that represents a set of HTTP authentication
    credentials.

    Instances are typically created and then added to a request manager
    object using
    :py:meth:`~pyslet.http.client.Client.add_credentials` for
    matching against HTTP authorization challenges.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification."""

    #: A dictionary mapping lower-case auth schemes onto the special
    #: classes used to represent their credential messages
    scheme_class = {}

    @classmethod
    def register(cls, scheme, credential_class):
        """Registers a class to represent credentials in scheme

        scheme
            A string representing an auth scheme, e.g., 'Basic'.  The
            string is converted to lower-case before it is registered
            to allow for case insensitive look-up.

        credential_class
            A class derived from Credentials that is used to represent a
            set of base Credentials in that scheme.  The class must have
            a :meth:`from_words` class method.

        If a class has already been registered for the scheme it is
        replaced.  The mapping is kept in the :attr:`scheme_class`
        dictionary."""
        cls.scheme_class[scheme.lower()] = credential_class

    def __init__(self):
        self.base = None
        """The base credentials

        By default, new instances are 'base' credentials and this
        attribute will be None.  When credentials are traded in response
        to a challenge they become session credentials and base contains
        the original 'base' credentials object from which the proffered
        credentials were derived."""
        self.scheme = None          #: the authentication scheme
        self.protectionSpace = None
        """the protection space in which these credentials should be used.

        The protection space is a :py:class:`pyslet.rfc2396.URI` instance
        reduced to just the the URL scheme, hostname and port."""
        self.realm = None
        """the realm in which these credentials should be used.

        The realm is a simple string as returned by the HTTP server.  If
        None then these credentials will be used for any realm within
        the protection space."""

    def match_challenge(self, challenge):
        """Returns True if these credentials can be used in response
        to *challenge*.

        challenge
                A :py:class:`Challenge` instance

        The match is successful if the authentication scheme, the
        protection space and the realms match the corresponding values
        in the challenge."""
        if self.scheme != challenge.scheme:
            return False
        if self.protectionSpace != challenge.protectionSpace:
            return False
        if self.realm:
            if self.realm != challenge["realm"]:
                return False
        return True

    def test_url(self, url):
        """Returns True if these credentials can be used peremptorily
        when making a request to *url*.

        url
                A :py:class:`pyslet.rfc2396.URI` instance.

        The default implementation always returns False."""
        return False

    @classmethod
    def from_words(cls, wp):
        credentials = BasicCredentials()
        credentials.set_basic_credentials(wp.parse_remainder())
        return credentials

    @classmethod
    def from_str(cls, source):
        """Constructs a :py:class:`Credentials` instance from an HTTP
        formatted string."""
        p = AuthorizationParser(source, ignore_sp=False)
        p.parse_sp()
        credentials = p.require_credentials()
        p.parse_sp()
        p.require_end("authorization header")
        return credentials

    def get_response(self, challenge=None):
        """Creates a new set of credentials from a challenge

        challenge (None)
            A :py:class:`Challenge` instance containing a challenge that
            has been received from the server.  If these credentials are
            being used pre-emptively (based on the target URL) then
            challenge will be None.

        This is an abstract method, by default None is returned.

        For base credentials, this method must return a new credentials
        object to be used in a new authentication session or None if
        these credentials cannot be used in response to *challenge*. If
        there is no challenge, return a new credentials object that can
        be used pre-emptively.

        For session credentials (instances returned by a previous call)
        this method must return a new credentials object, the same
        credentials object with updated state or None if the challenge
        indicates that the authentication session has failed.  (If there
        is no challenge, the credentials should be returned unchanged.)

        In all cases, the returned object must have :attr:`base` set to
        the original base credentials used to initiate the
        authentication session."""
        return None


class BasicCredentials(Credentials):

    def __init__(self):
        Credentials.__init__(self)
        self.scheme = "Basic"
        self.userid = None
        self.password = None
        # a list of path-prefixes for which these credentials are known
        # to be good
        self.path_prefixes = []

    def set_basic_credentials(self, basic_credentials):
        credentials = base64.b64decode(basic_credentials).split(b':')
        if len(credentials) == 2:
            self.userid = credentials[0].decode('iso-8859-1')
            self.password = credentials[1].decode('iso-8859-1')
        else:
            raise ValueError(basic_credentials)

    def match(self, challenge=None, url=None):
        if challenge is not None:
            # must match the challenge
            if not super(BasicCredentials, self).match(challenge):
                return False
        if url is not None:
            # must match the url
            if not self.test_url(url):
                return False
        elif challenge is None:
            raise ValueError(
                "BasicCredentials must be matched to a challenge or a URL")
        return True

    def test_url(self, url):
        """Given a :py:class:`~pyslet.rfc2396.URI` instance representing
        an absolute URI, checks if these credentials contain a matching
        protection space and path prefix."""
        if not url.is_absolute():
            raise ValueError("test_url requires an absolute URL")
        if (self.protectionSpace == url.get_canonical_root() and
                self.test_path(url.abs_path)):
            return True
        else:
            return False

    def test_path(self, path):
        """Returns True if there is a path prefix that matches *path*"""
        path = uri.split_path(path)
        uri.normalize_segments(path)
        for p in self.path_prefixes:
            if self.is_prefix(p, path):
                return True
        return False

    def add_success_path(self, path):
        """Updates credentials based on success at path

        path
            A string of octets representing the path that these
            credentials have been used for with a successful result.

        This method implements the requirement that paths "at or deeper
        than the depth of the last symbolic element in the path field"
        should be treated as being part of the same protection space.

        The path is reduced to a path prefix by removing the last
        symbolic element and then it is tested against existing prefixes
        to ensure that the most general prefix is being stored, for
        example, if path is "/website/document" it will replace any
        existing prefixes of the form "/website/folder." with the common
        prefix "/website"."""
        if not path:
            # empty path, treat as entire space!
            path = "/"
        new_prefix = uri.split_path(path)
        if new_prefix[-1]:
            new_prefix[-1] = ""
        uri.normalize_segments(new_prefix)
        keep = True
        i = 0
        while i < len(self.path_prefixes):
            p = self.path_prefixes[i]
            # p could be a prefix of new_prefix
            if self.is_prefix(p, new_prefix):
                keep = False
                break
            elif self.is_prefix(new_prefix, p):
                # new_prefix could be a prefix of p
                del self.path_prefixes[i]
                continue
            i = i + 1
        if keep:
            self.path_prefixes.append(new_prefix)

    def is_prefix(self, prefix, path):
        if len(prefix) > len(path):
            return False
        i = 0
        while i < len(prefix):
            # note that an empty segment matches anything (except nothing)
            if prefix[i] and prefix[i] != path[i]:
                return False
            i = i + 1
        return True

    def to_bytes(self):
        format = [self.scheme.encode('ascii'), b' ']
        if self.userid is not None and self.password is not None:
            format.append(
                base64.b64encode((self.userid + ":" +
                                  self.password).encode('iso-8859-1')))
        return b''.join(format)

    def get_response(self, challenge=None):
        if challenge and not self.match_challenge(challenge):
            # the challenge must actually match
            return None
        if not self.base:
            # base credentials
            sc = BasicCredentials()
            sc.base = self
            sc.scheme = "Basic"
            sc.userid = self.userid
            sc.password = self.password
            sc.realm = self.realm if challenge is None else challenge["realm"]
            # success paths are used only by the base credentials
            return sc
        else:
            if challenge:
                return None
            else:
                return self

Credentials.register('Basic', BasicCredentials)


class AuthorizationParser(ParameterParser):

    def require_challenge(self):
        """Parses a challenge returning a :py:class:`Challenge`
        instance.  Raises BadSyntax if no challenge was found.

        This method is complicated by the possibility that a server will
        send multiple challenges.  Strictly speaking this is bad because
        the syntax includes commas despite the fact that multiple
        headers may be combined with a comma.

        We support two different types of challenge, those that are
        parsable and those that are not.  In the former case we parse
        comma-separated parameters until we find something that doesn't
        match the name=value syntax.  In the latter case we consume all
        the words until we find a comma."""
        self.parse_sp()
        auth_scheme = self.require_token("auth scheme").decode('ascii')
        lu_scheme = auth_scheme.lower()
        cls = Challenge.scheme_class.get(lu_scheme, Challenge)
        params = []
        if cls is Challenge:
            # unregistered challenges require the scheme as the first param
            params.append(auth_scheme)
        self.parse_sp()
        if not cls.can_parse:
            # consume everything up until we find a comma
            words = []
            while self.the_word is not None and self.the_word is not COMMA:
                w = self.parse_word_as_bstr()
                words.append(w)
            params.append(b''.join(words))
        else:
            expect_comma = False
            while self.the_word is not None:
                savepos = self.pos
                try:
                    if expect_comma:
                        self.require_separator(COMMA)
                        self.parse_sp()
                    param_name = self.require_token().decode('ascii')
                    self.parse_sp()
                    self.require_separator(EQUALS_SIGN)
                    self.parse_sp()
                    if self.is_token():
                        param_value = self.parse_token()
                        forceq = False
                    else:
                        param_value = self.require_production(
                            self.parse_quoted_string(), "auth-param value")
                        forceq = True
                    params.append((param_name, param_value, forceq))
                    self.parse_sp()
                    expect_comma = True
                except BadSyntax:
                    self.setpos(savepos)
                    break
        return cls(*params)

    def require_credentials(self):
        """Parses credentials returning a :py:class:`Credentials`
        instance.  Raises BadSyntax if no credentials were found."""
        self.parse_sp()
        auth_scheme = self.require_token(
            "Authentication Scheme").decode('ascii')
        lu_scheme = auth_scheme.lower()
        cls = Credentials.scheme_class.get(lu_scheme, Credentials)
        self.parse_sp()
        return cls.from_words(self)
