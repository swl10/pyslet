Core Types and Utilities
------------------------

.. py:module:: pyslet.qtiv1.core

This module contains a number core classes used to support the standard.


Enumerations
~~~~~~~~~~~~

Where the DTD defines enumerated attribute values we define special enumeration classes.
These follow a common pattern in which the values are represented by constant members of
the class.  The classes are not designed to be instantiated but they do define class
methods for decoding and encoding from and to text strings.
 
..	autoclass::	Action
	:show-inheritance:

..	autoclass::	Area
	:show-inheritance:

..	autofunction:: MigrateV2AreaCoords

..	autoclass::	FeedbackStyle
	:show-inheritance:

..	autoclass::	FeedbackType
	:show-inheritance:

..	autoclass::	FIBType
	:show-inheritance:

..	autoclass::	MDOperator
	:show-inheritance:

..	autoclass::	NumType
	:show-inheritance:

..	autoclass::	Orientation
	:show-inheritance:

..	autofunction:: MigrateV2Orientation

..	autoclass::	PromptType
	:show-inheritance:

..	autoclass::	RCardinality
	:show-inheritance:

..	autofunction:: MigrateV2Cardinality

..	autodata:: TestOperator

..	autoclass::	VarType
	:show-inheritance:

..	autofunction:: MigrateV2VarType

..	autoclass::	View
	:show-inheritance:

..	autofunction:: MigrateV2View


Utility Functions
~~~~~~~~~~~~~~~~~

..	autofunction:: MakeValidName

..	autofunction:: ParseYesNo

..	autofunction:: FormatYesNo


Constants
~~~~~~~~~

..	autodata:: QTI_SOURCE


Exceptions
~~~~~~~~~~

..	autoclass:: QTIError
	:show-inheritance:

..	autoclass:: QTIUnimplementedError
	:show-inheritance:


Abstract Elements
~~~~~~~~~~~~~~~~~

..	autoclass:: QTIElement
	:members:
	:show-inheritance:

..	autoclass:: ObjectMixin
	:members:
	:show-inheritance:

..	autoclass:: SectionItemMixin
	:members:
	:show-inheritance:

..	autoclass:: SectionMixin
	:members:
	:show-inheritance:


