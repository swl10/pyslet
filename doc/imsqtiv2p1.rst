IMS Question and Test Interoperability (version 2.1)
====================================================

The IMS Question and Test Interoperability specification version 2.1 has
yet to be finalized and is currently only available as a "Public Draft
Specification" from the IMS GLC website:
http://www.imsglobal.org/question/index.html

Version 2.1 is an extension of the pre-existing version 2.0 which was
finalized in 2005.  For more information on the history of the
specification see http://en.wikipedia.org/wiki/QTI

This module implements version 2.1 of the specification in anticipation
of the finalization of the specification by the consortium.

.. toctree::
	:maxdepth: 2

	qtiv2/items
	qtiv2/tests
	qtiv2/content
	qtiv2/interactions
	qtiv2/variables
	qtiv2/processing
	qtiv2/expressions
	qtiv2/core
	qtiv2/metadata
	
.. py:module:: pyslet.qtiv2.xml

The starting point for parsing and managing QTI content::

    import pyslet.qtiv2.xml as qti


..  warning::   The structure of this module has changed in version
                Pyslet version 0.7.  You should now include
                pyslet.qtiv2.xml to get access to QTIDocument as there
                are now no names exposed directly through the older
                pyslet.imsqtiv2p1.


..	autoclass:: QTIDocument
	:members:
	:show-inheritance:

