Conceptual Schema Definition Language (CSDL)
============================================

.. py:module:: pyslet.mc_csdl

This module defines functions and classes for working with the data based on
Microsoft's Conceptual Schema Definition File Format:
http://msdn.microsoft.com/en-us/library/dd541474.aspx


Reference
---------

..	autoclass:: ERStore
	:members:
	:show-inheritance:


Elements
~~~~~~~~

..	autoclass:: Schema
	:members:
	:show-inheritance:

..	autoclass:: Type
	:members:
	:show-inheritance:

..	autoclass:: EntityType
	:members:
	:show-inheritance:

..	autoclass:: Property
	:members:
	:show-inheritance:

..	autoclass:: NavigationProperty
	:members:
	:show-inheritance:

..	autoclass:: Key
	:members:
	:show-inheritance:

..	autoclass:: PropertyRef
	:members:
	:show-inheritance:

..	autoclass:: ComplexType
	:members:
	:show-inheritance:

..	autoclass:: Association
	:members:
	:show-inheritance:


..	autoclass:: CSDLElement
	:members:
	:show-inheritance:





Basic Data Types
~~~~~~~~~~~~~~~~

..	autofunction:: ValidateSimpleIdentifier

..	autoclass:: NameTableMixin
	:members:
	:show-inheritance:
	:special-members:

..	autoclass:: SimpleType
	:members:
	:show-inheritance:


There are a number of functions that are used internally for decoding and
encoding values that represent these simple types to and from the appropriate
python types.  The Decode functions require a string as input (and it should be
a Unicode string) and return a value of the appropriate python type.  It is
possible that code might read a value from an XML stream and by-pass the
decoding functions, therefore, the Encode functions will take values of the
appropriate python type *and* also accept undecoded (Unicode) strings.  In the
latter case the string is decoded and then encoded to force a canonical
representation in any subsequent XML output.

..	autofunction:: DecodeBinary

..	autofunction:: EncodeBinary

..	autofunction:: DecodeBoolean

..	autofunction:: EncodeBoolean

..	autofunction:: DecodeByte

..	autofunction:: EncodeByte

..	autofunction:: DecodeDateTime

..	autofunction:: EncodeDateTime

..	autofunction:: DecodeDateTimeOffset

..	autofunction:: EncodeDateTimeOffset

..	autofunction:: DecodeGuid

..	autofunction:: EncodeGuid

..	autofunction:: DecodeInt16

..	autofunction:: EncodeInt16

..	autofunction:: DecodeInt32

..	autofunction:: EncodeInt32

..	autofunction:: DecodeInt64

..	autofunction:: EncodeInt64

..	autofunction:: DecodeSByte

..	autofunction:: EncodeSByte


Exceptions
~~~~~~~~~~

..	autoclass:: DuplicateName
	:members:
	:show-inheritance:

..	autoclass:: IncompatibleNames
	:members:
	:show-inheritance:

..	autoclass:: ContainerExists
	:members:
	:show-inheritance:


Constants
~~~~~~~~~

..	autodata:: EDM_NAMESPACE
