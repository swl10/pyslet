The Open Data Protocol (OData)
==============================

This sub-package defines functions and classes for working with OData, a
data access protocol based on Atom and Atom Pub: http://www.odata.org/

This sub-package only deals with version 2 of the protocol.

.. toctree::
   :maxdepth: 2

   odatav2_csdl
   odatav2_core
   odatav2_client
   odatav2_memds
   odatav2_sqlds
   odatav2_server

	
Background
----------

OData is not an essential part of supporting the Standards for Learning,
Education and Training (SLET) that gives pyslet its name, though I have
actively promoted its use in these communities.  As technical standards
move towards using REST-ful web services it makes sense to converge
around some common patterns for common use cases.  For example, resource
discovery might well benefit from an approach based on the ideas of the
semantic web and there has already been some activity and investigation
in this direction.  However, many of the protocols now being worked on
are much more like basic data-access layers spread over the web between
two co-operating systems.  HTTP on its own is often good enough for
these applications but when the data lends itself to tabular
representations I think the OData standard is the best protocol
available.

The purpose of this group of modules is to make is easy to use the
conventions of the OData protocol as a data-access layer (DAL) for
python.  The basic API for the DAL is defined by the Entity Data Model
(EDM) defined in :py:mod:`pyslet.odatav2.csdl`, which is extended by
some core OData-specific features defined in
:py:mod:`pyslet.odatav2.core`.  With these two modules it is possible to
create derived classes that implement the API in a variety of different
storage scenarios.  There are three implementations included in this
package:

1.	OData Client - an implementation of the DAL that makes calls over
	the web to an OData server.  Defined in the module
	:py:mod:`pyslet.odatav2.client`.

2.	In-memory data service - an implementation of the DAL that stores
	all entities and associations in python dictionaries.  Defined in
	the module :py:mod:`pyslet.odatav2.memds`

3.	SQL data service - an implementation of the DAL that maps on to
	python's database API.  Defined in the module
	:py:mod:`pyslet.odatav2.sqlds`.  In practice, the classes defined
	by this module will normally need to be sub-classed to deal with
	database-specific issues.  This can't be helped, the DB API does a
	good job at dealing with most issues, such as variation in
	parameterization conventions and expected data types, but SQL
	connection parameters and the occasional different in the SQL syntax
	mean there is likely to be a small amount of work to do.  Don't be
	put off, a full implementation for SQLite is provided and a quick
	look at the source code for that should give you courage to tackle
	any modifications necessary for your favourite database.  Using this
	DAL API is much easier than having to do these tweaks when they are
	distributed throughout your code in embedded SQL-statements.
	
The idea behind the DAL is that these implementations can be used
interchangeably, you can test your application using an in-memory or
SQLite storage implementation to check it is working before pointing it
at your OData server using the client implementation.  Of course, the
reason I wrote the DAL this way was because I like OData as an
interoperability protocol but I also needed a more flexible DAL for the
QTI migration tool. This way of framing the API allowed me to 'kill two
birds with one stone'.

The package also contains an OData server implementation which allows
you to expose your DAL over the web directly (see
:py:mod:`pyslet.odata2.server`.  The server is compatible with any of
the implementations so if you want to create an OData proxy by exposing
an OData client you can.  Why would you want to do this?

One of the big challenges for the OData protocol is web-security in the
end user's browser.   By supporting JSON over the wire OData sends out a
clear signal that using it directly from a Javascript on a web page
should be possible.  But in practice, this only works well for
unauthenticated (and hence read-only) OData services.  If you want to
write more exciting applications you leave yourself open to all manner
of browser-based attacks that could expose your data to unauthorised bad
guys.  To mitigate these risks browsers are increasingly locking down
the browser to make it harder for cross-site exploits to happen, which
is a good thing. The downside is that it makes it harder for your
web-application to talk to an OData server unless they are both hosted
on the same domain.  An OData proxy can be co-located with your
application to overcome this problem.  A dumb proxy is probably best
implemented by the web-server, rather than a full-blown web application
but the classes defined in this package are a good starting point for
writing a more intelligent proxy such as one that checks for a valid
session with your application before proxying the request.
 
