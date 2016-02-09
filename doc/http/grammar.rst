HTTP Grammar
============

.. py:module:: pyslet.http.grammar

Using the Grammar
~~~~~~~~~~~~~~~~~

The functions and data definitions here are exposed to enable normative
use in other modules.  Use of the grammar itself is typically through
use of a parser.  There are two types of parser, an OctetParser that is
used for parsing raw strings (or octets, represented by bytes in Python)
such as those obtained from the HTTP connection itself and a WordParser
that tokenizes the input string first and then provides a higher-level
word-based parser.


..	autoclass:: OctetParser
	:members:
	:show-inheritance:


..	autoclass:: WordParser
	:members:
	:show-inheritance:


Basic Syntax
~~~~~~~~~~~~

This section defines functions for handling basic elements of the HTTP
grammar, refer to Section 2.2 of RFC2616 for details.

The HTTP protocol only deals with octets so the following functions take
a single byte as an argument and return True if the byte matches the
production and False otherwise.  As a convenience they all accept None
as an argument and will return False.

A byte is defined as the type returned by indexing a binary string and
is therefore an integer in the range 0..255 in Python 3 and a single
character string in Python 2.

     
..	autofunction:: is_octet

..	autofunction:: is_char

..	autofunction:: is_upalpha

..	autofunction:: is_loalpha

..	autofunction:: is_alpha

..	autofunction:: is_digit

..	autofunction:: is_digits

..	autofunction:: is_ctl

..	autofunction:: is_separator

..	autofunction:: is_hex


The following constants are defined to speed up comparisons, in each
case they are the byte (see above) corresponding to the syntax elements
defined in the specification.

..	autodata::CR

..	autodata::LF

..	autodata::SP

..	autodata::HT

..	autodata::DQUOTE

And similarly, these byte constants are not defined in the grammar but
are useful for comparisons.  Again they are the byte representing these
separators and will have a different type in Python 2 and 3.

..	autodata::LEFT_PARENTHESIS

..	autodata::RIGHT_PARENTHESIS

..	autodata::LESSTHAN_SIGN

..	autodata::GREATERTHAN_SIGN

..	autodata::COMMERCIAL_AT

..	autodata::COMMA

..	autodata::SEMICOLON

..	autodata::COLON

..	autodata::REVERSE_SOLIDUS

..	autodata::SOLIDUS

..	autodata::LEFT_SQUARE_BRACKET

..	autodata::RIGHT_SQUARE_BRACKET

..	autodata::QUESTION_MARK

..	autodata::EQUALS_SIGN

..	autodata::LEFT_CURLY_BRACKET

..	autodata::RIGHT_CURLY_BRACKET


The following binary string constant is defined for completeness:

..	autodata::CRLF

There are no special definitions for LWS and TEXT, these productions are
handled by :py:class:`OctetParser`

The following functions operate on binary strings.  Note that in Python
2 a byte is also a binary string (of length 1) but in Python 3 a byte is
not a valid string.  Use :func:`pyslet.py2.byte_to_bstr` if you need to
create a binary string from a single byte.

..	autofunction:: is_hexdigits

..	autofunction:: check_token

..	autofunction:: decode_quoted_string

..	autofunction:: quote_string


Misc Functions
~~~~~~~~~~~~~~

..	autofunction:: format_parameters


Exceptions
~~~~~~~~~~

..	autoclass:: BadSyntax
