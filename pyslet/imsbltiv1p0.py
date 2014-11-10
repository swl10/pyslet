#! /usr/bin/env python
"""This module implements the Basic LTI 1.0 specification defined by IMS GLC

This is an experimental module and subject to significant change in future
releases.  Use with caution.
"""

import os
import random
import string
import time

from pyslet.pep8 import renamed_method


BLTI_VERSION = "LTI-1p0"
BLTI_LAUNCH_REQUEST = "basic-lti-launch-request"


class BLTIError(Exception):
    """Base class for BLTI errors."""
    pass


class BLTIDuplicateKeyError(BLTIError):
    pass


class BLTIOAuthParameterError(BLTIError):
    pass


class BLTIAuthenticationError(BLTIError):
    """Error raised when a launch request cannot be authorized."""
    pass


try:
    from oauth import oauth

    class BLTIConsumer(oauth.OAuthConsumer):
        """Represents a Tool Consumer."""

        def __init__(self, key, secret):
            oauth.OAuthConsumer.__init__(self, key, secret)
            self.nonces = []

        @renamed_method
        def CheckNonce(self, nonce):    # noqa
            pass

        def check_nonce(self, nonce):
            """True if the nonce has been checked in the last 90 mins"""
            now = time.time()
            old = now - 5400.0
            trim = 0
            for n, t in self.nonces:
                if t < old:
                    trim = trim + 1
                else:
                    break
            if trim:
                self.nonces = self.nonces[trim:]
            for n, t in self.nonces:
                if n == nonce:
                    return True
            self.nonces.append((nonce, now))

    class BLTIToolProvider(oauth.OAuthDataStore):
        """Represents a Tool Provider."""

        def __init__(self):
            self.consumers = {}
            #: A dictionary of :class:`BLTIConsumer` instances keyed on
            #: the consumer key
            self.oauth_server = oauth.OAuthServer(self)
            self.oauth_server.add_signature_method(
                oauth.OAuthSignatureMethod_PLAINTEXT())
            self.oauth_server.add_signature_method(
                oauth.OAuthSignatureMethod_HMAC_SHA1())

        @renamed_method
        def GenerateKey(self, key_length=128):   # noqa
            pass

        def generate_key(self, key_length=128):
            """Generates a new key

            key_length
                The minimum key length in bits.  Defaults to 128.

            The key is returned as a sequence of 16 bit hexadecimal
            strings separated by '.' to make them easier to read and
            transcribe into other systems."""
            key = []
            nfours = (key_length + 1) // 16
            try:
                rbytes = os.urandom(nfours * 2)
                for i in xrange(nfours):
                    four = "%02X%02X" % (
                        ord(rbytes[2 * i]), ord(rbytes[2 * i + 1]))
                    key.append(four)
            except NotImplementedError:
                for i in xrange(nfours):
                    four = []
                    for j in xrange(4):
                        four.append(random.choice('0123456789ABCDEFG'))
                    key.append(string.join(four, ''))
            return string.join(key, '.')

        @renamed_method
        def NewConsumer(self, key=None):    # noqa
            pass

        def new_consumer(self, key=None):
            """Creates a new BLTIConsumer instance

            The new instance is added to the dictionary of consumers
            authorized to use this tool.  The consumer key and secret
            are automatically generated using :meth:`generate_key` but
            key can be passed as an argument instead."""
            if key is None:
                key = self.generate_key()
            elif key in self.consumers:
                raise BLTIDuplicateKeyError(key)
            secret = self.generate_key()
            self.consumers[key] = BLTIConsumer(key, secret)
            return key, secret

        def lookup_consumer(self, key):
            return self.consumers.get(key, None)

        def lookup_nonce(self, oauth_consumer, oauth_token, nonce):
            if oauth_consumer.CheckNonce(nonce):
                return nonce
            else:
                return None

        @renamed_method
        def LoadFromFile(self, f):  # noqa
            pass

        def load_from_file(self, f):
            """Loads the list of trusted consumers

            The consumers are loaded from a simple file of key, secret
            pairs formatted as::

                <consumer key> [SPACE]+ <consumer secret>

            Lines starting with a '#' are ignored as comments."""
            lines = f.readlines()
            for line in lines:
                if line and line[0] == '#':
                    continue
                fields = line.split()
                if len(fields) >= 2:
                    if fields[0] in self.consumers:
                        raise BLTIDuplicateKeyError(fields[0])
                    self.consumers[fields[0]] = BLTIConsumer(
                        fields[0], fields[1])

        @renamed_method
        def SaveToFile(self, f):    # noqa
            pass

        def save_to_file(self, f):
            """Saves the list of trusted consumers

            The consumers are saved in a simple file suitable for
            reading with :meth:`load_from_file`."""
            keys = self.consumers.keys()
            keys.sort()
            for key in keys:
                f.write("%s %s\n" % (key, self.consumers[key].secret))

        @renamed_method
        def Launch(self, command, url, headers, query_string):  # noqa
            pass

        def launch(self, command, url, headers, query_string):
            """Checks a launch request for authorization

            Returns a BLTIConsumer instance and a dictionary of
            parameters on success. If the incoming request is not
            authorized then :class:`BLTIAuthenticationError` is
            raised."""
            oauth_request = oauth.OAuthRequest.from_request(
                command, url, headers=headers, query_string=query_string)
            try:
                if oauth_request:
                    # verify the request has been oauth authorized,
                    # copied from verify_request but we omit the token
                    # as BLTI does not use it. consumer, token, params =
                    # self.oauth_server.verify_request(oauth_request)
                    # version = self.oauth_server._get_version(oauth_request)
                    consumer = self.oauth_server._get_consumer(oauth_request)
                    self.oauth_server._check_signature(
                        oauth_request, consumer, None)
                    parameters = oauth_request.get_nonoauth_parameters()
                    return consumer, parameters
                else:
                    raise BLTIOAuthParameterError
            except oauth.OAuthError, err:
                raise BLTIAuthenticationError(err.message)

except ImportError:
    oauth = None
