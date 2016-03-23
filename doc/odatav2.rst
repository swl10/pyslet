..  _odatav2:

The Open Data Protocol (OData)
==============================

This sub-package defines functions and classes for working with OData, a
data access protocol based on Atom and Atom Pub: http://www.odata.org/

This sub-package only deals with version 2 of the protocol *at the moment*.

OData is not an essential part of supporting the Standards for Learning,
Education and Training (SLET) that gives pyslet its name, though I have
actively promoted its use in these communities.  As technical standards
move towards using REST-ful web services it makes sense to converge
around some common patterns for common use cases.  Many of the protocols
now being worked on are much more like basic data-access layers spread
over the web between two co-operating systems.  HTTP on its own is often
good enough for these applications but when the data lends itself to
tabular representations I think the OData standard is the best protocol
available.

The purpose of this group of modules is to make is easy to use the
conventions of the OData protocol as a general purpose data-access layer
(DAL) for Python applications.  To get started, look at the
:doc:`odatav2/consumer` section which gives a high-level overview of the
API with examples that use Microsoft's Northwind data-service.

If you are interested in writing an OData provider, or you simply want
to use these classes to implement a data access layer for your own
application then look in :doc:`odatav2/provider`.

.. toctree::
   :maxdepth: 2

   odatav2/consumer
   odatav2/provider
   odatav2/reference

