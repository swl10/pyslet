HTTP Messages
=============

.. py:module:: pyslet.http.messages


This modules defines objects that represent the values of HTTP messages
and message headers and a special-purpose parser for parsing them from
strings of octets.

Messages
~~~~~~~~

..	autoclass:: Request
	:members:
	:show-inheritance:

..	autoclass:: Response
	:members:
	:show-inheritance:

..	autoclass:: Message
	:members:
	:show-inheritance:


General Header Types
~~~~~~~~~~~~~~~~~~~~

..	autoclass:: CacheControl
	:members:
	:show-inheritance:


Request Header Types
~~~~~~~~~~~~~~~~~~~~

..	autoclass:: AcceptList
	:members:
	:show-inheritance:

..	autoclass:: MediaRange
	:members:
	:show-inheritance:

..	autoclass:: AcceptItem
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


Response Header Types
~~~~~~~~~~~~~~~~~~~~~

..	autoclass:: AcceptRanges
	:members:
	:show-inheritance:


Entity Header Types
~~~~~~~~~~~~~~~~~~~

..	autoclass:: Allow
	:members:
	:show-inheritance:

..	autoclass:: ContentRange
	:members:
	:show-inheritance:


Parsing Header Values
~~~~~~~~~~~~~~~~~~~~~

In most cases header values will be parsed automatically when reading
them from messages.  For completeness a header parser is exposed to
enable you to parse these values from more complex strings.

..	autoclass:: HeaderParser
	:members:
	:show-inheritance:


Exceptions
~~~~~~~~~~

..	autoclass:: HTTPException
	:show-inheritance:
