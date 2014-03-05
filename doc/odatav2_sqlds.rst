SQL Database-based Data Services
================================

.. py:module:: pyslet.odata2.sqlds

This module defines a general (but abstract) implementation of the
EDM-based data-access-layer (DAL) using Python's DB API: 
http://www.python.org/dev/peps/pep-0249/

It also contains a concrete implementation derived from the above
that uses the standard SQLite module for storage.  For more information
about SQLite see: http://www.sqlite.org/


Data Access Layer API
---------------------

..	autoclass:: SQLCollectionMixin
	:members:
	:show-inheritance:



Misc Definitions
----------------

..	autodata:: SQL_TIMEOUT

..	autoclass:: UnparameterizedLiteral
	:members:
	:show-inheritance:

..	autodata:: SQLOperatorPrecedence


Exceptions
----------

..	autoclass:: DatabaseBusy
	:members:
	:show-inheritance:

..	autoclass:: SQLError
	:members:
	:show-inheritance:
