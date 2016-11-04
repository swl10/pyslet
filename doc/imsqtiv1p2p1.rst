IMS Question and Test Interoperability (version 1.2)
====================================================

The IMS Question and Test Interoperability (QTI) specification version 1.2 was
finalized in 2002.  After a gap of 1-2 years work started on a major revision,
culminating in version 2 of the specification, published first in 2005.  For
information about the history of the specification see
http://en.wikipedia.org/wiki/QTI - official information about the specification
is available from the IMS GLC: http://www.imsglobal.org/question/index.html

The purpose of this module is to allow documents in QTI v1 format to be parsed
and then transformed into objects representing the QTI v2 data model where more
sophisticated processing can be performed.  Effectively, the native model of
assessment items in Pyslet (and in the PyAssess package it supersedes) is QTI v2
and this module simply provides an import capability for legacy data marked up
as QTI v1 items.

Class methods or functions with names beginning migrate\_... use a common
pattern for performing the conversion.  Errors and warnings are logged
during conversion to a list passed in as the *log* parameter.

.. toctree::
   :maxdepth: 2

   qtiv1/core
   qtiv1/common
   
.. py:module:: pyslet.qtiv1.xml

The starting point for parsing and managing QTI v1 content.

..	autoclass:: QTIDocument
	:members:
	:show-inheritance:


QuesTestInterop Elements
------------------------

..	autoclass:: QuesTestInterop
	:members:
	:show-inheritance:


.. py:module:: pyslet.qtiv1.objectbank

Object Bank Elements
--------------------

..	autoclass:: ObjectBank
	:members:
	:show-inheritance:


.. py:module:: pyslet.qtiv1.assessment

Assessment Elements
-------------------

..	autoclass:: Assessment
	:members:
	:show-inheritance:

..	autoclass:: AssessmentControl
	:members:
	:show-inheritance:

..	autoclass:: AssessProcExtension
	:members:
	:show-inheritance:

..	autoclass:: AssessFeedback
	:members:
	:show-inheritance:





