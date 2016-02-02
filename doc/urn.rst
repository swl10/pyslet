Uniform Resource Names (RFC2141)
================================

.. py:module:: pyslet.urn

This module defines functions and classes for working with URI as
defined by RFC2141: http://www.ietf.org/rfc/rfc2141.txt


Creating URN Instances
----------------------

URN instances are created automatically by the
:meth:`~pyslet.rfc2396.URI.from_octets` method and no special action
is required when parsing them from character strings.

If you are in a URN specific context you may perform a looser parse of a
URN from a surrounding character stream using :func:`parse_urn` but the
return result is a character string rather than a URN instance.

Finally, you can construct a URN from a namespace identifier and
namespace specific string directly.  The resulting object can then be
converted directly to a well-formatted URN using string conversion or
used in any context where a URI instance is required.
 
..  autofunction::  parse_urn


URN
---

..	autoclass:: URN
	:members:
	:show-inheritance:


Translating to and from Text
----------------------------

..	autofunction::	translate_to_urnchar

..	autofunction::	translate_from_urnchar


Basic Syntax
------------

The module defines a number of character classes (see
:class:`pyslet.unicode5.CharClass`) to assist with the parsing of URN. 

The bound test method of each class is exposed for convenience (you
don't need to pass an instance).  These pseudo-functions therefore all
take a single character as an argument and return True if the character
matches the class.  They will also accept None and return False in that
case.

..	autofunction::	is_upper

..	autofunction::	is_lower

..	autofunction::	is_number

..	autofunction::	is_letnum

..	autofunction::	is_letnumhyp

..	autofunction::	is_reserved

..	autofunction::	is_other

..	autofunction::	is_trans

..	autofunction::	is_hex

