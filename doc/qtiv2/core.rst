Core Types and Utilities
------------------------

.. py:module:: pyslet.qtiv2.core

This module contains a number core classes used to support the standard.


Constants
~~~~~~~~~

..	autodata:: IMSQTI_NAMESPACE

..	autodata:: IMSQTI_SCHEMALOCATION

..	autodata:: IMSQTI_ITEM_RESOURCETYPE


XML Basics
~~~~~~~~~~

..	autoclass:: QTIElement
	:members:
	:show-inheritance:


Exceptions
~~~~~~~~~~

..	autoclass:: QTIError
	:show-inheritance:

..	autoclass:: DeclarationError
	:show-inheritance:

..	autoclass:: ProcessingError
	:show-inheritance:

..	autoclass:: SelectionError
	:show-inheritance:


Basic Data Types
~~~~~~~~~~~~~~~~

Basic data types in QTI v2 are a mixture of custom types and basic types defined externally,
for example, by XMLSchema.

The external types used are:

boolean
	Represented by python's boolean values True and False.  See
	:py:func:`~pyslet.xml.xsdatatypes.boolean_from_str` and
	:py:func:`~pyslet.xml.xsdatatypes.boolean_to_str`

coords
	Defined as part of support for HTML.  See :py:class:`~pyslet.html401.Coords`

date
	Although QTI draws on the definitions in XML schema it restricts values to
	those from the nontimezoned timeline.  This restriction is effectively implemented
	in the basic :py:class:`~pyslet.iso8601.Date` class.

datetime:
	See :py:func:`~pyslet.xml.xsdatatypes.DecodeDateTime` and
	:py:func:`~pyslet.xml.xsdatatypes.EncodeDateTime`

duration:
	Earlier versions of QTI drew on the ISO8601 representation of duration but
	QTI v2 simplifies this with a basic representation in seconds bound to XML
	Schema's double type which we, in turn, represent with python's float.  See
	:py:func:`~pyslet.xml.xsdatatypes.double_from_str` and
	:py:func:`~pyslet.xml.xsdatatypes.double_to_str`

float:
	implemented by python's float.  Note that this is defined as having
	"machine-level double precision" and the python specification goes on to
	warn that "You are at the mercy of the underlying machine architecture". See
	:py:func:`~pyslet.xml.xsdatatypes.double_from_str` and
	:py:func:`~pyslet.xml.xsdatatypes.double_to_str`

identifier:
	represented by python's (unicode) string.  The type is effectively just the
	NCName from the XML namespace specification.  See
	:py:func:`pyslet.xml.namespace.IsValidNCName`.
	
	..	autofunction:: ValidateIdentifier

integer:
	XML schema's integer, implemented by python's integer.  See
	:py:func:`~pyslet.xml.xsdatatypes.DecodeInteger` and
	:py:func:`~pyslet.xml.xsdatatypes.integer_to_str`

language:
	Currently implemented as a simple python string.

length:
	Defined as part of support for HTML.  See :py:class:`~pyslet.html401.LengthType`

mimeType:
	Currently implemented as a simple python string

string:
	XML schema string becomes python's unicode string

string256:
	Length restriction not yet implemented, see string above.

styleclass:
	Inherited from HTML, implemented with a simple (unicode) string.

uri:
	In some instances this is implemented as a simple (unicode) string, for example, in cases
	where a URI is being used as global identifier.  In contexts where the URI will need to
	be interpreted it is implemented with instances of :py:class:`pyslet.rfc2396.URI`.
	

QTI-specific types:

..	autoclass:: Orientation
	:show-inheritance:
	
..	autoclass:: Shape
	:show-inheritance:

..	autoclass:: ShowHide
	:show-inheritance:

..	autoclass:: View
	:show-inheritance:

The QTI specification lists valueType as a basic data type.  In pyslet this is
implemented as a core part of the processing model.  See
:py:class:`pyslet.qtiv2.variables.Value` for details.

