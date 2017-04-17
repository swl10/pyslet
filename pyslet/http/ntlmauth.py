#! /usr/bin/env python

import base64

import ntlm3.ntlm as ntlm

from .auth import Challenge, Credentials


class NTLMChallenge(Challenge):

    """Represents an NTLM authentication challenge."""

    #: NTLM is unparsable as it does not adhere to RFC2617
    can_parse = False

    def __init__(self, auth_data=b''):
        super(NTLMChallenge, self).__init__("NTLM")
        # a default realm will have been added, remove it
        del self._pdict['realm']
        self._params = []
        #: base64 encoded binary string containing ntlm-data
        auth_data = auth_data.strip()
        if auth_data:
            self.auth_data = auth_data
            self.server_challenge, self.flags = \
                ntlm.parse_NTLM_CHALLENGE_MESSAGE(auth_data)
        else:
            # empty auth_data is the same as no auth data
            self.auth_data = None
            self.server_challenge = None
            self.flags = None

    def to_bytes(self):
        result = [self.scheme.encode('ascii')]
        if self.auth_data:
            result.append(self.auth_data)
        return b' '.join(result)

    def __repr__(self):
        return "NTLMChallenge(%s)" % (repr(self.auth_data)
                                      if self.auth_data else "")


Challenge.register('NTLM', NTLMChallenge)


class NegotiateChallenge(Challenge):

    """Represents an NTLM negotiate challenge."""

    #: Negotiate is unparsable as it does not adhere to RFC2617
    can_parse = False

    def __init__(self, data=None):
        super(NegotiateChallenge, self).__init__("Negotiate")
        # a default realm will have been added, remove it
        del self._pdict['realm']
        self._params = []

    def to_bytes(self):
        return self.scheme.encode('ascii')

    def __repr__(self):
        return "NegotiateChallenge()"


Challenge.register('Negotiate', NegotiateChallenge)


class NTLMCredentials(Credentials):

    """Represents a set of base NTLM credentials."""

    def __init__(self):
        Credentials.__init__(self)
        self.scheme = "NTLM"
        self.userid = None
        self.password = None
        self.domain = ''

    def set_ntlm_credentials(self, user, password):
        user_parts = user.split('\\')
        if len(user_parts) > 1:
            self.userid = user_parts[1]
            self.domain = user_parts[0].upper()
        else:
            self.userid = user
            self.domain = ''
        self.password = password

    def get_response(self, challenge=None):
        """Creates a type-1 negotiate message"""
        if challenge is None or (isinstance(challenge, NTLMChallenge) and
                                 not challenge.auth_data):
            # start a new authentication session
            return NTLMCredentialsType1(self)
        else:
            # any other type of NTLM challenge is a failure at this point
            return None

    def to_bytes(self):
        raise ValueError("NTLM base credentials have no str representation")


class NTLMCredentialsType1(Credentials):

    """Represents a type-1 negotiate message."""

    def __init__(self, base):
        Credentials.__init__(self)
        self.base = base
        self.scheme = "NTLM"
        if base.domain:
            self.type1_flags = ntlm.NTLM_TYPE1_FLAGS
            self.user = "%s\\%s" % (self.base.domain, self.base.userid)
        else:
            self.type1_flags = ntlm.NTLM_TYPE1_FLAGS & \
                ~ntlm.NTLM_NegotiateOemDomainSupplied
            self.user = self.base.userid

    def to_bytes(self):
        format = [self.scheme.encode('ascii'), b' ']
        auth = ntlm.create_NTLM_NEGOTIATE_MESSAGE(self.user, self.type1_flags)
        format.append(auth)
        return b''.join(format)

    def get_response(self, challenge=None):
        """Creates a type-3 response message"""
        if isinstance(challenge, NTLMChallenge) and challenge.server_challenge:
            # start a new authentication session
            return NTLMCredentialsType3(self, challenge)
        else:
            # any other type of NTLM challenge is a failure at this point
            return None


class NTLMCredentialsType3(Credentials):

    """Represents a type-3 response message

    Last step in NTLM authentication, any challenge at this point
    terminates the session so no need to override get_response."""

    def __init__(self, type1, type2):
        Credentials.__init__(self)
        self.base = type1.base
        self.type1 = type1
        self.type2 = type2
        self.scheme = "NTLM"

    def to_bytes(self):
        format = [self.scheme.encode('ascii'), b' ']
        auth = ntlm.create_NTLM_AUTHENTICATE_MESSAGE(
            self.type2.server_challenge, self.type1.user, self.base.domain,
            self.base.password, self.type2.flags)
        format.append(auth)
        return b''.join(format)


class NTLMParsedCredentials(Credentials):

    """Represents a parsed NTLM Authorization header

    We don't support the server side of this protocol so any attempt to
    parse NTLM credentials from an authorization header just results in
    a class that contains the binary NTLM data sent in the original
    message."""

    def __init__(self, auth_data=b''):
        Credentials.__init__(self)
        self.scheme = "NTLM"
        #: base64 encoded binary string containing ntlm-data
        self.auth_data = auth_data.strip()
        self.msg = base64.b64decode(self.auth_data)
        if len(self.msg) < 12 or self.msg[0:8] != b"NTLMSSP\x00":
            raise TypeError

    def to_bytes(self):
        result = [self.scheme.encode('ascii')]
        if self.auth_data:
            result.append(self.auth_data)
        return b' '.join(result)

    def __repr__(self):
        return "NTLMParsedCredentials(%s)" % (repr(self.auth_data)
                                              if self.auth_data else "")

    @classmethod
    def from_words(cls, wp):
        data = wp.parse_remainder()
        try:
            return cls(data)
        except TypeError:

            raise ValueError("bad NTLM message")

Credentials.register('NTLM', NTLMParsedCredentials)
