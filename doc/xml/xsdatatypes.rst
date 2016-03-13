XML: Schema Datatypes
=====================

.. py:module:: pyslet.xml.xsdatatypes

This module implements some useful concepts drawn from
http://www.w3.org/TR/xmlschema-2/

One of the main purposes of this module is to provide classes and
functions for converting data between python-native representations of
the value-spaces defined by this specification and the lexical
representations defined in the specification.

The result is typically a pair of x_from_str/x_to_str functions that are
used to define custom attribute handling in classes that are derived from
:py:class:`~pyslet.xml.structures.Element`.  For example::

	import xml.xsdatatypes as xsi
	
	class MyElement(XMLElement):
	    XMLNAME = "MyElement"
		XMLATTR_flag=('flag', xsi.boolean_from_str, xsi.boolean_to_str)

In this example, an element like this::

    <MyElement flag="1">...</MyElement>

Would cause the instance of MyElement representing this element to have
it's flag attribute set to the Python constant True instead of a string
value.  Also, when serializing the element instance the flag attribute's
value would be converted to the canonical representation, which in this
case would be the string "true".  Finally, these functions raise
ValueError when conversion fails, an error which the XML parser will
escalate to an XML validation error (allowing the document to be
rejected in strict parsing modes).

    
Namespace
---------

The XML schema namespace is typically used with the prefix xsi.

..  autodata:: XMLSCHEMA_NAMESPACE


Primitive Datatypes
-------------------

XML schema's boolean trivially maps to Python's True/False

..	autofunction:: boolean_from_str

..	autofunction:: boolean_to_str

The decimal, float and double types are represented by Python's native
float type but the function used to encode and decode them from strings
differ from native conversion to adhere more closely to the schema
specification and to ensure that, by default, canonical lexical
representations are used.

..	autofunction:: decimal_from_str

..	autofunction:: decimal_to_str

..	autofunction:: float_from_str

..	autofunction:: float_to_str

..	autofunction:: double_from_str

..	autofunction:: double_to_str

..	autoclass:: Duration
	:members:
	:show-inheritance:

dateTime values are represented by :class:`pyslet.iso8601.TimePoint`
instances.  These functions are provided for convenience in custom
attribute mappings.

..	autofunction:: datetime_from_str

..	autofunction:: datetime_to_str


Derived Datatypes
-----------------

dateTime values are represented by :class:`pyslet.iso8601.TimePoint`
instances.  These functions are provided for convenience in custom
attribute mappings.

Name represents XML Names, the native Python character string is used.

..	autofunction:: name_from_str

..	autofunction:: name_to_str

Integer is represented by the native Python integer.

..	autofunction:: integer_from_str

..	autofunction:: integer_to_str


Constraining Facets
-------------------

Enumeration
~~~~~~~~~~~

..	autoclass:: Enumeration
	:members:
	:show-inheritance:

..	autoclass:: EnumerationNoCase
	:members:
	:show-inheritance:


WhiteSpace
~~~~~~~~~~~

..	autofunction:: white_space_replace

..	autofunction:: white_space_collapse


Regular Expressions
-------------------

Appendix F of the XML Schema datatypes specification defines a regular
expression language.  This language differs from the native Python
regular expression language but it is close enough to enable us to
define a wrapper class which parses schema regular expressions and
converts them to equivalent python regular expressions.

..	autoclass:: RegularExpression
	:members:
	:show-inheritance:

For completeness we also document the parser we use to do the
conversion, it draws heavily on the
:py:class:`pyslet.unicode5.CharClass` concept.
 
..	autoclass:: RegularExpressionParser
	:members:
	:show-inheritance:


Backwards Compatibility
-----------------------

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

..	autofunction:: DecodeName

..	autofunction:: EncodeName

..	autofunction:: DecodeInteger

..	autofunction:: EncodeInteger

..  autofunction:: make_enum

..	autofunction:: MakeEnumeration

..  autofunction:: make_enum_aliases

..	autofunction:: MakeEnumerationAliases

..  autofunction:: make_lower_aliases

..	autofunction:: MakeLowerAliases



