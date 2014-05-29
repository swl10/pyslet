#! /usr/bin/env python


import string
import base64
import pyslet.rfc2396 as uri
from pyslet.rfc2616_core import *
from pyslet.rfc2616_params import *


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
        self.scheme = scheme				#: the name of the schema
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
        """an optional protection space indicating the scope of this challenge."""

    @classmethod
    def FromString(cls, source):
        """Creates a Challenge from a *source* string."""
        p = AuthorizationParser(source, ignoreSpace=False)
        p.ParseSP()
        c = p.RequireChallenge()
        p.ParseSP()
        p.RequireEnd("challenge")
        return c

    @classmethod
    def ListFromString(cls, source):
        """Creates a list of Challenges from a *source* string."""
        p = AuthorizationParser(source)
        challenges = []
        while True:
            c = p.ParseProduction(p.RequireChallenge)
            if c is not None:
                challenges.append(c)
            if not p.ParseSeparator(","):
                break
        p.RequireEnd("challenge")
        return challenges

    def __str__(self):
        result = [self.scheme]
        params = []
        for pn, pv, pq in self._params:
            params.append("%s=%s" % (pn, QuoteString(pv, force=pq)))
        if params:
            result.append(string.join(params, ', '))
        return string.join(result, ' ')

    def __unicode__(self):
        return unicode(self.__str__())

    def __repr__(self):
        return "Challege(%s,%s)" % (repr(self.scheme), string.join(map(repr, self._params), ','))

    def __len__(self):
        return len(self._params)

    def __getitem__(self, index):
        if type(index) in StringTypes:
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
    :py:meth:`~pyslet.rfc2616.HTTPRequestManager.AddCredentials` for
    matching against HTTP authorization challenges.

    The built-in str function can be used to format instances according
    to the grammar defined in the specification."""

    def __init__(self):
        self.scheme = None			#: the authentication scheme
        self.protectionSpace = None
        """the protection space in which these credentials should be used.
		
		The protection space is a :py:class:`pyslet.rfc2396.URI` instance
		reduced to just the the URL scheme, hostname and port."""
        self.realm = None
        """the realm in which these credentials should be used.
		
		The realm is a simple string as returned by the HTTP server.  If
		None then these credentials will be used for any realm within
		the protection space."""

    def MatchChallenge(self, challenge):
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

    def TestURL(self, url):
        """Returns True if these credentials can be used peremptorily
        when making a request to *url*.

        url
                A :py:class:`pyslet.rfc2396.URI` instance.

        The default implementation always returns False."""
        return False

    @classmethod
    def FromWords(cls, wp):
        scheme = wp.RequireToken("Authentication Scheme").lower()
        if scheme == "basic":
            # the rest of the words represent the credentials as a base64
            # string
            credentials = BasicCredentials()
            credentials.SetBasicCredentials(wp.ParseRemainder())
        else:
            raise NotImplementedError
        return credentials

    @classmethod
    def FromHTTPString(cls, source):
        """Constructs a :py:class:`Credentials` instance from an HTTP
        formatted string."""
        wp = WordParser(source)
        credentials = cls.FromWords(wp)
        wp.RequireEnd("authorization header")
        return credentials


class BasicCredentials(Credentials):

    def __init__(self):
        Credentials.__init__(self)
        self.scheme = "Basic"
        self.userid = None
        self.password = None
        # : a list of path-prefixes for which these credentials are known to be good
        self.pathPrefixes = []

    def SetBasicCredentials(self, basicCredentials):
        credentials = base64.b64decode(basicCredentials).split(':')
        if len(credentials) == 2:
            self.userid, self.password = credentials
        else:
            raise HTTPInvalidBasicCredentials(basicCredentials)

    def Match(self, challenge=None, url=None):
        if challenge is not None:
            # must match the challenge
            if not super(BasicCredentials, self).Match(challenge):
                return False
        if url is not None:
            # must match the url
            if not self.TestURL(url):
                return False
        elif challenge is None:
            raise ValueError(
                "BasicCredentials must be matched to a challenge or a URL")
        return True

    def TestURL(self, url):
        """Given a :py:class:`~pyslet.rfc2396.URI` instance representing
        an absolute URI, checks if these credentials contain a matching
        protection space and path prefix."""
        if not url.IsAbsolute():
            raise ValueError("TestURL requires an absolute URL")
        if self.protectionSpace == url.GetCanonicalRoot() and self.TestPath(url.absPath):
            return True
        else:
            return False

    def TestPath(self, path):
        """Returns True if there is a path prefix that matches *path*"""
        path = uri.SplitPath(path)
        uri.NormalizeSegments(path)
        for p in self.pathPrefixes:
            if self.IsPrefix(p, path):
                return True
        return False

    def AddSuccessPath(self, path):
        """Adds *pathPrefix* to the list of path prefixes that these
        credentials apply to.

        If pathPrefix is a more general prefix than an existing prefix
        in the list then it replaces that prefix."""
        newPrefix = uri.SplitPath(path)
        uri.NormalizeSegments(newPrefix)
        keep = True
        i = 0
        while i < len(self.pathPrefixes):
            p = self.pathPrefixes[i]
            # p could be a prefix of newPrefix
            if self.IsPrefix(p, newPrefix):
                keep = False
                break
            elif self.IsPrefix(newPrefix, p):
                # newPrefix could be a prefix of p
                del self.pathPrefixes[i]
                continue
            i = i + 1
        if keep:
            self.pathPrefixes.append(newPrefix)

    def IsPrefix(self, prefix, path):
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


class AuthorizationParser(ParameterParser):

    def RequireChallenge(self):
        """Parses a challenge returning a :py:class:`Challenge`
        instance.  Raises SyntaxError if no challenge was found."""
        self.ParseSP()
        authScheme = self.RequireToken("auth scheme")
        params = []
        self.ParseSP()
        while self.cWord is not None:
            paramName = self.ParseToken()
            if paramName is not None:
                self.ParseSP()
                self.RequireSeparator('=')
                self.ParseSP()
                if self.IsToken():
                    paramValue = self.ParseToken()
                    forceQ = False
                else:
                    paramValue = self.RequireProduction(
                        self.ParseQuotedString(), "auth-param value")
                    forceQ = True
                params.append((paramName, paramValue, forceQ))
            self.ParseSP()
            if not self.ParseSeparator(","):
                break
        if authScheme.lower() == "basic":
            return BasicChallenge(*params)
        else:
            return Challenge(*params)
