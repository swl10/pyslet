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

..	autofunction::	translate_to_urnchar(src, reserved_test=is_reserved)

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

..	function::	is_upper(c)

    Returns True if c matches upper

..	function::	is_lower(c)

    Returns True if c matches lower

..	function::	is_number(c)

    Returns True if c matches number

..	function::	is_letnum(c)

    Returns True if c matches letnum
    
..	autofunction::	is_letnumhyp(c)

    Returns True if c matches letnumhyp
    
..	function::	is_reserved(c)

    Returns True if c matches reserved

    The reserved characters are::

        "%" | "/" | "?" | "#"
    
..	function::	is_other(c)

    Returns True if c matches other

    The other characters are::

        "(" | ")" | "+" | "," | "-" | "." | ":" | "=" | "@" | ";" | "$" |
        "_" | "!" | "*" | "'"

..	function::	is_trans(c)

    Returns True if c matches trans

    Note that translated characters include reserved characters, even though
    they should normally be escaped (and in the case of '%' MUST be
    escaped).  The effect is that URNs consist of runs of characters that
    match the production for trans.

..	function::	is_hex(c)

    Returns True if c matches hex

