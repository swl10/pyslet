OData Core Classes
==================

.. py:module:: pyslet.odata2.core

This module extends the definitions in :py:mod:`pyslet.odata2.csdl` with
OData-specific functions and classes.  In most cases you won't need to
worry about which layer of the model a definition belongs to.  Where a
class is derived from one in the parent EDM the same name is used,
therefore most of the time you should look to include items from the
core module rather than from the base csdl module.


Data Model
----------

..	autoclass:: EntityCollection
	:members:
	:show-inheritance:

..	autoclass:: Entity
	:members:
	:show-inheritance:
	:special-members:

..  autoclass:: StreamInfo
	:members:
	:show-inheritance:

    
Navigation: Deferred Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~

..	autoclass:: NavigationCollection
	:members:
	:show-inheritance:

..	autoclass:: ExpandedEntityCollection
	:members:
	:show-inheritance:

