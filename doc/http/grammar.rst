HTTP Grammar
============

.. py:module:: pyslet.http.grammar

This section defines functions for handling basic elements of the HTTP
grammar, refer to Section 2.2 of RFC2616 for details.

The HTTP protocol only deals with octets but as a convenience, and due
to the blurring of octet and character strings in Python 2.x we process
characters as if they were octets.
     
..	autofunction:: is_octet

..	autofunction:: is_char

..	autofunction:: is_upalpha

..	autofunction:: is_loalpha

..	autofunction:: is_alpha

..	autofunction:: is_digit

..	autofunction:: is_digits

..	autofunction:: is_ctl

..	autodata::CR

..	autodata::LF

..	autodata::SP

..	autodata::HT

..	autodata::DQUOTE

..	autodata::CRLF

LWS and TEXT productions are handled by :py:class:`OctetParser`

..	autofunction:: is_hex

..	autofunction:: is_hexdigits

..	autofunction:: check_token

..	autodata::SEPARATORS

..	autofunction:: is_separator

..	autofunction:: decode_quoted_string

..	autofunction:: quote_string

..	autofunction:: format_parameters


Using the Grammar
~~~~~~~~~~~~~~~~~

The functions and data definitions above are exposed to enable normative
use in other modules but use of the grammar is typically through use of
a parser.  There are two types of parser, an OctetParser that is used
for parsing raw strings (or octets) such as those obtained from the HTTP
connection itself and a WordParser that tokenizes the input string first
and then provides a higher-level word-based parser.


..	autoclass:: OctetParser
	:members:
	:show-inheritance:


..	autoclass:: WordParser
	:members:
	:show-inheritance:


..	autoclass:: BadSyntax
