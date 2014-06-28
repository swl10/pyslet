Hypertext Transfer Protocol (RFC2616)
=====================================

.. py:module:: pyslet.rfc2617

This sub-package defines functions and classes for working with HTTP as
defined by RFC2616: http://www.ietf.org/rfc/rfc2616.txt and RFC2617:
http://www.ietf.org/rfc/rfc2616.txt

The purpose of this module is to expose some of the basic constructs
(including the synax of protocol components) to allow them to be used
normatively in other contexts.  The module also contains a functional
HTTP client designed to support non-blocking and persistent HTTP client
operations.

.. toctree::
   :maxdepth: 2

   http/grammar
   http/params


HTTP Messages
-------------

..	autoclass:: HTTPMessage
	:members:
	:show-inheritance:


Sending Requests
----------------

..	autoclass:: HTTPRequestManager
	:members:
	:show-inheritance:

..	autoclass:: Connection
	:members:
	:show-inheritance:

..	autoclass:: SecureConnection
	:members:
	:show-inheritance:


HTTP Headers
------------

This section defines objects that represent the values of HTTP headers
and a special-purpose parser for parsing them from strings of octets.

..	autoclass:: AcceptList
	:members:
	:show-inheritance:

..	autoclass:: AcceptItem
	:members:
	:show-inheritance:

..	autoclass:: MediaRange
	:members:
	:show-inheritance:

..	autoclass:: AcceptCharsetItem
	:members:
	:show-inheritance:

..	autoclass:: AcceptCharsetList
	:members:
	:show-inheritance:

..	autoclass:: AcceptEncodingItem
	:members:
	:show-inheritance:

..	autoclass:: AcceptEncodingList
	:members:
	:show-inheritance:

..	autoclass:: AcceptLanguageItem
	:members:
	:show-inheritance:

..	autoclass:: AcceptLanguageList
	:members:
	:show-inheritance:

..	autoclass:: AcceptToken
	:members:
	:show-inheritance:

..	autoclass:: AcceptTokenList
	:members:
	:show-inheritance:

..	autoclass:: AcceptRanges
	:members:
	:show-inheritance:

..	autoclass:: Allow
	:members:
	:show-inheritance:

..	autoclass:: CacheControl
	:members:
	:show-inheritance:

..	autoclass:: ContentRange
	:members:
	:show-inheritance:

..	autoclass:: HeaderParser
	:members:
	:show-inheritance:



Exceptions
----------

..	autoclass:: HTTPException
	:show-inheritance:


Misc Definitions
----------------

..	autodata:: HTTP_PORT

..	autodata:: HTTPS_PORT

..	autodata:: HTTP_VERSION

..	autodata:: USER_AGENT

..	autodata:: SOCKET_CHUNK



