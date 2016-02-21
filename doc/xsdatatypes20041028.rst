XML Schema Datatypes
====================

.. py:module:: pyslet.xsdatatypes20041028

This module implements some useful concepts drawn from http://www.w3.org/TR/xmlschema-2/

One of the main purposes of this module is to provide classes and functions for
converting data between python-native representations of the value-spaces
defined by this specification and the lexical representations defined in the
specification.

The result is typically a pair of DecodeX and EncodeX functions that are used to
define custom attribute handling in classes that are derived from
:py:class:`~pyslet.xml.structures.Element`.  For example::

	import xsdatatypes20041028 as xsi
	
	class MyElement(XMLElement):
		XMLATTR_flag=('flag',xsi.DecodeBoolean,xsi.EncodeBoolean)


Primitive Datatypes
-------------------

..	autofunction:: DecodeBoolean

..	autofunction:: EncodeBoolean

..	autofunction:: DecodeDecimal

..	autofunction:: EncodeDecimal

..	autofunction:: DecodeFloat

..	autofunction:: EncodeFloat

..	autofunction:: DecodeDouble

..	autofunction:: EncodeDouble

..	autofunction:: DecodeDateTime

..	autofunction:: EncodeDateTime


Derived Datatypes
-----------------

..	autofunction:: DecodeName

..	autofunction:: EncodeName

..	autofunction:: DecodeInteger

..	autofunction:: EncodeInteger


Constraining Facets
-------------------

Enumeration
~~~~~~~~~~~

..	autoclass:: Enumeration
	:members:
	:show-inheritance:

..	autofunction:: MakeEnumeration

..	autofunction:: MakeEnumerationAliases

..	autofunction:: MakeLowerAliases

..	autofunction:: MakeEnumeration

..	autofunction:: MakeEnumeration

WhiteSpace
~~~~~~~~~~~

..	autofunction:: WhiteSpaceReplace

..	autofunction:: WhiteSpaceCollapse


Regular Expressions
-------------------

Appendix F of the XML Schema datatypes specification defines a regular
expression language.  This language differs from the native Python regular
expression language but it is close enough to enable us to define a wrapper
class which parses schema regular expressions and converts them to equivalent
python regular expressions.

..	autoclass:: RegularExpression
	:members:
	:show-inheritance:

For completeness we also document the parser we use to do the conversion, it
draws heavily on the :py:class:`pyslet.unicode5.CharClass` concept.
 
..	autoclass:: RegularExpressionParser
	:members:
	:show-inheritance:

