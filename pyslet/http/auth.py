#! /usr/bin/env python


import string
import base64
import types

import pyslet.rfc2396 as uri
import pyslet.http.grammar as grammar
import pyslet.http.params as params


class Challenge(object):

    """Represents an HTTP authentication challenge.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    Instances are created from a scheme and a variable length list of
    3-tuples containing parameter (name,value,qflag) values.  qflag is a
    boolean indicating that the value must always be quoted, even if is
    a valid token.

    Instances behave like read-only lists of (name,value) pairs
    implementing len, indexing and iteration in the usual way. Instances
    also support basic key lookup of parameter names by implementing
    __contains__ and __getitem__ (which returns the parameter value and
    raises KeyError for undefined parameters).  Name look-up handles
    case sensitivity by looking first for a case-sensitive match and
    then for a case insensitive match.  Instances are not truly
    dictionary like."""

    def __init__(self, scheme, *params):
        self.scheme = scheme                #: the name of the schema
        self._params = list(params)
        self._pdict = {}
        for pn, pv, pq in self._params:
            self._pdict[pn] = pv
            _pn = pn.lower()
            if _pn not in self._pdict:
                self._pdict[_pn] = pv
        if "realm" not in self._pdict:
            self._params.append(("realm", "Default", True))
            self._pdict["realm"] = "Default"
        self.protectionSpace = None
        """an optional protection space indicating the scope of this
        challenge."""

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
            if not p.parse_separator(","):
                break
        p.require_end("challenge")
        return challenges

    def __str__(self):
        result = [self.scheme]
        params = []
        for pn, pv, pq in self._params:
            params.append("%s=%s" % (pn, grammar.quote_string(pv, force=pq)))
        if params:
            result.append(string.join(params, ', '))
        return string.join(result, ' ')

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return "Challege(%s,%s)" % (repr(self.scheme),
                                    string.join(map(repr, self._params), ','))

    def __len__(self):
        return len(self._params)

    def __getitem__(self, index):
        if type(index) in types.StringTypes:
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


class Credentials(object):

    """An abstract class that represents a set of HTTP authentication
    credentials.

    Instances are typically created and then added to a request manager
    object using
    :py:meth:`~pyslet.rfc2616.HTTPRequestManager.add_credentials` for
    matching against HTTP authorization challenges.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification."""

    def __init__(self):
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
            if self.realm != challenge.realm:
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
        scheme = wp.require_token("Authentication Scheme").lower()
        if scheme == "basic":
            # the rest of the words represent the credentials as a base64
            # string
            credentials = BasicCredentials()
            credentials.set_basic_credentials(wp.parse_remainder())
        else:
            raise NotImplementedError
        return credentials

    @classmethod
    def from_str(cls, source):
        """Constructs a :py:class:`Credentials` instance from an HTTP
        formatted string."""
        wp = grammar.WordParser(source)
        credentials = cls.from_words(wp)
        wp.require_end("authorization header")
        return credentials


class BasicCredentials(Credentials):

    def __init__(self):
        Credentials.__init__(self)
        self.scheme = "Basic"
        self.userid = None
        self.password = None
        # a list of path-prefixes for which these credentials are known
        # to be good
        self.pathPrefixes = []

    def set_basic_credentials(self, basic_credentials):
        credentials = base64.b64decode(basic_credentials).split(':')
        if len(credentials) == 2:
            self.userid, self.password = credentials
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
        if not url.IsAbsolute():
            raise ValueError("test_url requires an absolute URL")
        if (self.protectionSpace == url.GetCanonicalRoot() and
                self.test_path(url.absPath)):
            return True
        else:
            return False

    def test_path(self, path):
        """Returns True if there is a path prefix that matches *path*"""
        path = uri.SplitPath(path)
        uri.NormalizeSegments(path)
        for p in self.pathPrefixes:
            if self.is_prefix(p, path):
                return True
        return False

    def add_success_path(self, path):
        """Adds *pathPrefix* to the list of path prefixes that these
        credentials apply to.

        If pathPrefix is a more general prefix than an existing prefix
        in the list then it replaces that prefix."""
        new_prefix = uri.SplitPath(path)
        uri.NormalizeSegments(new_prefix)
        keep = True
        i = 0
        while i < len(self.pathPrefixes):
            p = self.pathPrefixes[i]
            # p could be a prefix of new_prefix
            if self.is_prefix(p, new_prefix):
                keep = False
                break
            elif self.is_prefix(new_prefix, p):
                # new_prefix could be a prefix of p
                del self.pathPrefixes[i]
                continue
            i = i + 1
        if keep:
            self.pathPrefixes.append(new_prefix)

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

    def __str__(self):
        format = [self.scheme, ' ']
        if self.userid is not None and self.password is not None:
            format.append(base64.b64encode(self.userid + ":" + self.password))
        return string.join(format, '')


class AuthorizationParser(params.ParameterParser):

    def require_challenge(self):
        """Parses a challenge returning a :py:class:`Challenge`
        instance.  Raises BadSyntax if no challenge was found."""
        self.parse_sp()
        auth_scheme = self.require_token("auth scheme")
        params = []
        self.parse_sp()
        while self.the_word is not None:
            param_name = self.parse_token()
            if param_name is not None:
                self.parse_sp()
                self.require_separator('=')
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
            if not self.parse_separator(","):
                break
        if auth_scheme.lower() == "basic":
            return BasicChallenge(*params)
        else:
            return Challenge(*params)
