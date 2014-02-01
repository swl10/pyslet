Entity Data Model (EDM)
=======================

.. py:module:: pyslet.odata2.csdl

This module defines functions and classes for working with data based on
Microsoft's Entity Data Model (EDM) as documented by the Conceptual
Schema Definition Language and associated file format:
http://msdn.microsoft.com/en-us/library/dd541474.aspx


Reference
---------

..	autoclass:: EDMValue
	:members:
	:show-inheritance:

..	autoclass:: SimpleValue
	:members:
	:show-inheritance:

..	autoclass:: Complex
	:members:
	:show-inheritance:

..	autoclass:: Entity
	:members:
	:show-inheritance:

..	autoclass:: EntityCollection
	:members:
	:show-inheritance:


Elements
~~~~~~~~

..	autoclass:: EntitySet
	:members:
	:show-inheritance:

..	autoclass:: EntityContainer
	:members:
	:show-inheritance:

..	autoclass:: Schema
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

..	autoclass:: NavigationProperty
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


Exceptions
~~~~~~~~~~

..	autoclass:: EDMError
	:members:
	:show-inheritance:

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


Constants
~~~~~~~~~

..	autodata:: EDM_NAMESPACE
