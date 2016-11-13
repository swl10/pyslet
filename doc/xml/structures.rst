XML: Reference
==============

.. py:module:: pyslet.xml.structures


Documents and Elements
----------------------

..	autoclass:: Node
	:members:
	:show-inheritance:
	
..	autoclass:: Document
	:members:
	:show-inheritance:

..	autoclass:: Element
	:members:
	:show-inheritance:

..  autofunction:: map_class_elements


Exceptions
~~~~~~~~~~

..	autoclass:: XMLMissingResourceError
	:show-inheritance:

..	autoclass:: XMLMissingLocationError
	:show-inheritance:

..	autoclass:: XMLUnsupportedSchemeError
	:show-inheritance:

..	autoclass:: XMLUnexpectedHTTPResponse
	:show-inheritance:



Prolog and Document Type Declaration
------------------------------------

..	autoclass:: XMLDTD
	:members:
	:show-inheritance:

..	autoclass:: XMLDeclaration
	:members:
	:show-inheritance:

..	autoclass:: ElementType
	:members:
	:show-inheritance:

..	autoclass:: XMLContentParticle
	:members:
	:show-inheritance:

..	autoclass:: XMLNameParticle
	:members:
	:show-inheritance:

..	autoclass:: XMLChoiceList
	:members:
	:show-inheritance:

..	autoclass:: XMLSequenceList
	:members:
	:show-inheritance:

..	autoclass:: XMLAttributeDefinition
	:members:
	:show-inheritance:



Physical Structures
-------------------

..	autoclass:: XMLEntity
	:members:
	:show-inheritance:

..	autoclass:: XMLDeclaredEntity
	:members:
	:show-inheritance:

..	autoclass:: XMLGeneralEntity
	:members:
	:show-inheritance:

..	autoclass:: XMLParameterEntity
	:members:
	:show-inheritance:

..	autoclass:: XMLExternalID
	:members:
	:show-inheritance:

..	autoclass:: XMLTextDeclaration
	:members:
	:show-inheritance:
		
..	autoclass:: XMLNotation
	:members:
	:show-inheritance:


Syntax
------

White Space Handling
~~~~~~~~~~~~~~~~~~~~

..	autofunction:: is_s

..	autofunction:: collapse_space


Names
~~~~~

..	function:: is_name_start_char(c)

    Tests if the character *c* matches production [4] NameStartChar.
    
..	function:: is_name_char(c)

    Tests production [4a] NameChar

..	autofunction:: is_valid_name

..	autofunction:: is_reserved_name


Character Data and Markup
~~~~~~~~~~~~~~~~~~~~~~~~~

..	autofunction:: escape_char_data

..	autofunction:: escape_char_data7


CDATA Sections
~~~~~~~~~~~~~~

..  autodata:: CDATA_START

..  autodata:: CDATA_END

..	autofunction:: escape_cdsect


Exceptions
~~~~~~~~~~

..	autoclass:: XMLError
	:show-inheritance:

..	autoclass:: XMLValidityError
	:show-inheritance:

..	autoclass:: XMLIDClashError
	:show-inheritance:

..	autoclass:: XMLIDValueError
	:show-inheritance:

..	autoclass:: DuplicateXMLNAME
	:show-inheritance:

..	autoclass:: XMLAttributeSetter
	:show-inheritance:

..	autoclass:: XMLMixedContentError
	:show-inheritance:

..	autoclass:: XMLParentError
	:show-inheritance:

..	autoclass:: XMLUnknownChild
	:show-inheritance:





