XML: Namespaces
===============

.. py:module:: pyslet.xml.namespace

Documents and Elements
----------------------

..	autoclass:: NSNode
	:members:
	:show-inheritance:
	
..	autoclass:: NSDocument
	:members:
	:show-inheritance:

..	autoclass:: NSElement
	:members:
	:show-inheritance:

..  autofunction:: map_class_elements


Backwards Compatibility
~~~~~~~~~~~~~~~~~~~~~~~

..  class:: XMLNSDocument

Alias for :class:`NSDocument`

..  class:: XMLNSElement

Alias for :class:`NSElement`


Namespace URIs
--------------

..  autodata:: XML_NAMESPACE

..  autodata:: XMLNS_NAMESPACE

..  autodata:: NO_NAMESPACE

..  autofunction:: match_expanded_names


Parsing
-------

..  autofunction:: is_valid_ncname

..	autoclass:: XMLNSParser
	:members:
	:show-inheritance:
	

Exceptions
----------

..	autoclass:: XMLNSError
	:show-inheritance:
