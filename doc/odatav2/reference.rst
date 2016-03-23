OData Reference
===============

The basic API for the DAL is defined by the Entity Data Model (EDM)
defined in :py:mod:`pyslet.odata2.csdl`, which is extended by some core
OData-specific features defined in
:py:mod:`pyslet.odata2.core` and :py:mod:`pyslet.odata2.metadata`.  With
these three modules it is possible to create derived classes that
implement the Data Access Layer API in a variety of different storage
scenarios.


.. toctree::
   :maxdepth: 2

   csdl
   core
   metadata
   client
   memds
   sqlds
   server

