Item Variables
--------------

.. py:module:: pyslet.qtiv2.variables

This module contains the basic run-time data model.  Although the specification
does contain elements to represent the values of variables set at runtime the
XML schema sometimes relies too much on context for an efficient implementation.
For example, a <value> element is always a value of a specific base type but the
base type is rarely specified on the value element itself as it is normally
implicit in the context. such as a variable declaration.

Although the expression model does contain an element that provides a more
complete representation of single values (namely <baseValue>) we decide to make
the distinction in this module with :py:class:`ValueElement` representing the
element and the abstract :py:class:`Value` being used as the root of the runtime
object model.

For example, to get the default value of a variable from a variable declaration
you'll use the :py:meth:`~VariableDeclaration.GetDefaultValue` method and it
will return a :py:class:`Value` instance which could be of any cardinality or
base type.


..	autoclass:: VariableDeclaration
	:members:
	:show-inheritance:

..	autoclass:: ValueElement
	:members:
	:show-inheritance:

..	autoclass:: DefaultValue
	:members:
	:show-inheritance:

..	autoclass:: Cardinality
	:show-inheritance:

..	autoclass:: BaseType
	:show-inheritance:

..	autoclass:: Mapping
	:members:
	:show-inheritance:

..	autoclass:: MapEntry
	:members:
	:show-inheritance:



Runtime Object Model
~~~~~~~~~~~~~~~~~~~~

..	autoclass:: Value
	:members:
	:show-inheritance:

..	autoclass:: SingleValue
	:members:
	:show-inheritance:

..	autoclass:: BooleanValue
	:members:
	:show-inheritance:

..	autoclass:: DirectedPairValue
	:members:
	:show-inheritance:

..	autoclass:: DurationValue
	:members:
	:show-inheritance:

..	autoclass:: FileValue
	:members:
	:show-inheritance:

..	autoclass:: FloatValue
	:members:
	:show-inheritance:

..	autoclass:: IdentifierValue
	:members:
	:show-inheritance:

..	autoclass:: IntegerValue
	:members:
	:show-inheritance:

..	autoclass:: PairValue
	:members:
	:show-inheritance:

..	autoclass:: PointValue
	:members:
	:show-inheritance:

..	autoclass:: StringValue
	:members:
	:show-inheritance:

..	autoclass:: URIValue
	:members:
	:show-inheritance:

..	autoclass:: Container
	:members:
	:show-inheritance:

..	autoclass:: OrderedContainer
	:members:
	:show-inheritance:

..	autoclass:: MultipleContainer
	:members:
	:show-inheritance:

..	autoclass:: RecordContainer
	:members:
	:show-inheritance:




