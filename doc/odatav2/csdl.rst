Entity Data Model (EDM)
=======================

.. py:module:: pyslet.odata2.csdl

This module defines functions and classes for working with data based on
Microsoft's Entity Data Model (EDM) as documented by the Conceptual
Schema Definition Language and associated file format:
http://msdn.microsoft.com/en-us/library/dd541474.aspx

The classes in this model fall in to two categories.  The data classes
represent the actual data objects, like simple and complex values,
entities and collections.  The metadata classes represent the elements
of the metadata model like entity types, property definitions,
associations, entity sets and so on.  The metadata elements have direct
XML representations, the data classes do not.

.. toctree::
   :maxdepth: 2


Data Model
----------

..	autoclass:: EntityCollection
	:members:
	:show-inheritance:

..	autoclass:: Entity
	:members:
	:show-inheritance:
	:special-members:

..	autoclass:: SimpleValue
	:members:
	:show-inheritance:
	:special-members:

..	autoclass:: NumericValue
	:members:
	:show-inheritance:

..	autoclass:: FloatValue
	:members:
	:show-inheritance:


Primitive SimpleTypes
~~~~~~~~~~~~~~~~~~~~~

Simple values can be created directly using one of the type-specific
classes below.

..	autoclass:: BinaryValue
	:show-inheritance:

..	autoclass:: BooleanValue
	:show-inheritance:

..	autoclass:: ByteValue
	:show-inheritance:

..	autoclass:: DateTimeValue
	:show-inheritance:

..	autoclass:: DateTimeOffsetValue
	:show-inheritance:

..	autoclass:: DecimalValue
	:show-inheritance:

..	autoclass:: DoubleValue
	:show-inheritance:
	:members:

..	autoclass:: GuidValue
	:show-inheritance:

..	autoclass:: Int16Value
	:show-inheritance:

..	autoclass:: Int32Value
	:show-inheritance:

..	autoclass:: Int64Value
	:show-inheritance:

..	autoclass:: SByteValue
	:show-inheritance:

..	autoclass:: SingleValue
	:show-inheritance:
	:members:

..	autoclass:: StringValue
	:show-inheritance:

..	autoclass:: TimeValue
	:show-inheritance:


Complex Types
~~~~~~~~~~~~~

..	autoclass:: Complex
	:members:
	:show-inheritance:


Navigation: Deferred Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~

..	autoclass:: DeferredValue
	:members:
	:show-inheritance:

..	autoclass:: NavigationCollection
	:members:
	:show-inheritance:

..	autoclass:: ExpandedEntityCollection
	:members:
	:show-inheritance:


Supporting Classes
~~~~~~~~~~~~~~~~~~

..	autoclass:: EDMValue
	:members:
	:show-inheritance:
	:special-members:

..	autoclass:: TypeInstance
	:members:
	:show-inheritance:


Metadata Model
--------------

..	autoclass:: CSDLElement
	:show-inheritance:

..	autoclass:: Schema
	:members:
	:show-inheritance:

..	autoclass:: EntityContainer
	:members:
	:show-inheritance:

..	autoclass:: EntitySet
	:members:
	:show-inheritance:

..	autoclass:: AssociationSet
	:members:
	:show-inheritance:

..	autoclass:: AssociationSetEnd
	:members:
	:show-inheritance:

..	autoclass:: Type
	:members:
	:show-inheritance:

..	autoclass:: EntityType
	:members:
	:show-inheritance:

..	autoclass:: Key
	:members:
	:show-inheritance:

..	autoclass:: PropertyRef
	:members:
	:show-inheritance:

..	autoclass:: Property
	:members:
	:show-inheritance:

..	autoclass:: ComplexType
	:members:
	:show-inheritance:

..	autoclass:: NavigationProperty
	:members:
	:show-inheritance:

..	autoclass:: Association
	:members:
	:show-inheritance:

..	autoclass:: AssociationEnd
	:members:
	:show-inheritance:

..	autoclass:: Documentation
	:show-inheritance:


Misc Definitions
----------------

..	autofunction:: validate_simple_identifier

..	autoclass:: SimpleType
	:members:
	:show-inheritance:

..	autoclass:: ConcurrencyMode
	:members:
	:show-inheritance:

..	autofunction::	maxlength_from_str

..	autofunction::	maxlength_to_str

..	autodata::	MAX

..	autoclass:: Multiplicity
	:members:
	:show-inheritance:

..	autofunction::	multiplictiy_from_str

..	autofunction::	multiplicity_to_str

..	autoclass:: Parser
	:members:
	:show-inheritance:


Utility Classes
---------------

These classes are not specific to the EDM but are used to support the
implementation. They are documented to allow them to be reused in other
modules.

..	autoclass:: NameTableMixin
	:members:
	:show-inheritance:
	:special-members:

..	autoclass:: DictionaryLike
	:members:
	:show-inheritance:
	:special-members:


Exceptions
----------


..	autoclass:: NonExistentEntity
	:members:
	:show-inheritance:

..	autoclass:: EntityExists
	:members:
	:show-inheritance:

..	autoclass:: ConstraintError
	:members:
	:show-inheritance:

..	autoclass:: NavigationError
	:members:
	:show-inheritance:

..	autoclass:: ConcurrencyError
	:members:
	:show-inheritance:

..	autoclass:: ModelIncomplete
	:members:
	:show-inheritance:

..	autoclass:: ModelConstraintError
	:members:
	:show-inheritance:

..	autoclass:: DuplicateName
	:members:
	:show-inheritance:

..	autoclass:: IncompatibleNames
	:members:
	:show-inheritance:

..	autoclass:: InvalidMetadataDocument
	:members:
	:show-inheritance:

..	autoclass:: EDMError
	:members:
	:show-inheritance:


Constants
~~~~~~~~~

..	autodata:: EDM_NAMESPACE
