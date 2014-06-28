HTTP Protocol Parameters
========================

.. py:module:: pyslet.http.params

This section defines functions for handling basic parameters used by
HTTP.  Refer to Section 3 of RFC2616 for details.

The approach taken by this module is provide classes for each of the
parameter types.  Most classes have a class method 'from_str' which
returns a new instance parsed from a string and performs the reverse
transformation to the builtin str function.  Instances are generally
immutable objects which is consistent with them representing values of
parameters in the protocol.


..	autoclass:: HTTPVersion
	:members:
	:show-inheritance:

..	autodata::HTTP_1p1

..	autodata::HTTP_1p0

..	autoclass:: HTTPURL
	:members:
	:show-inheritance:

..	autoclass:: HTTPSURL
	:members:
	:show-inheritance:

..	autoclass:: FullDate
	:members:
	:show-inheritance:

..	autoclass:: TransferEncoding
	:members:
	:show-inheritance:

..	autoclass:: Chunk
	:members:
	:show-inheritance:

..	autoclass:: MediaType
	:members:
	:show-inheritance:

..	autodata::APPLICATION_OCTETSTREAM

..	autodata::PLAIN_TEXT

..	autoclass:: ProductToken
	:members:
	:show-inheritance:

..	autoclass:: LanguageTag
	:members:
	:show-inheritance:

..	autoclass:: EntityTag
	:members:
	:show-inheritance:


Parsing Parameter Values
~~~~~~~~~~~~~~~~~~~~~~~~

In most cases parameter values will be parsed directly by the class
methods provided in the parameter types themselves.  For completeness a
parameter parser is exposed to enable you to parse these values from
more complex strings.

..	autoclass:: ParameterParser
	:members:
	:show-inheritance:
	
