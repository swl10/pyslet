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

..	autofunction:: is_char

..	autofunction:: is_discouraged

..	autofunction:: is_pubid_char

..	autofunction:: is_enc_name

..	autofunction:: is_enc_name_start

..	autofunction:: is_letter

..	autofunction:: is_base_char

..	autofunction:: is_ideographic

..	autofunction:: is_combining_char

..	autofunction:: is_digit

..	autofunction:: is_extender


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