XML: Parsing XML Documents
==========================

.. py:module:: pyslet.xml.parser

This module exposes a number of internal functions typically defined
privately in XML parser implementations which make it easier to reuse
concepts from XML in other modules. For example, the
:func:`IsNameStartChar` tells you if a character matches the production
for NameStartChar in the XML standard.


..	autoclass:: XMLParser
	:members:
	:show-inheritance:

..	autoclass:: ContentParticleCursor
	:members:
	:show-inheritance:


Character Classes
~~~~~~~~~~~~~~~~~

The standard defines a number of character classes (see
:class:`pyslet.unicode5.CharClass`) to assist with the parsing of XML
documents.

The bound test method of each class is exposed for convenience (you
don't need to pass an instance).  These pseudo-functions therefore all
take a single character as an argument and return True if the character
matches the class.  They will also accept None and return False in that
case.

..	function:: is_char(c)

    Tests production for [2] Char

    This test will be limited on systems with narrow python builds.

..	autofunction:: is_discouraged

..	function:: is_pubid_char(c)

    Tests production for [13] PubidChar.

..	function:: is_enc_name(c)

    Tests the second part of production [81] EncName

..	function:: is_enc_name_start(c)

    Tests the first character of production [81] EncName

..	function:: is_letter(c)

    Tests production [84] Letter.

..	function:: is_base_char(c)

    Tests production [85] BaseChar.

..	function:: is_ideographic(c)

    Tests production [86] Ideographic.

..	function:: is_combining_char(c)

    Tests production [87] CombiningChar.

..	function:: is_digit(c)

    Tests production [88] Digit.
    
..	function:: is_extender(c)

    Tests production [89] Extender.


Misc Functions
~~~~~~~~~~~~~~

..	autofunction:: is_white_space

..	autofunction:: contains_s

..	autofunction:: strip_leading_s

..	autofunction:: normalize_space

..	autofunction:: is_valid_nmtoken



Exceptions
~~~~~~~~~~

..	autoclass:: XMLFatalError
	:show-inheritance:

..	autoclass:: XMLWellFormedError
	:show-inheritance:

..	autoclass:: XMLForbiddenEntityReference
	:show-inheritance:


Misc
----

..  autofunction::  parse_xml_class