OData Providers
===============

The approach to writing a data access layer (DAL) taken by Pyslet is to
use the Entity Data Model (EDM), and the extensions defined by OData,
and to encapsulate them in an API defined by a set of abstract Python
classes.  The :doc:`consumer` section goes through this API from
the point of view of the consumer and provides a good primer for
understanding what is required from a provider.

Pyslet includes three derived classes that implement the API in a
variety of different storage scenarios:

1.	OData Client - an implementation of the DAL that makes calls over
	the web to an OData server.  Defined in the module
	:py:mod:`pyslet.odatav2.client` and used in the examples in
	the section :doc:`consumer`.

2.	In-memory data service - an implementation of the DAL that stores
	all entities and associations in python dictionaries.  Defined in
	the module :py:mod:`pyslet.odatav2.memds`.

3.	SQL data service - an implementation of the DAL that maps on to
	python's database API.  Defined in the module
	:py:mod:`pyslet.odatav2.sqlds`.  In practice, the classes defined
	by this module will normally need to be sub-classed to deal with
	database-specific issues but a full implementation for SQLite is
	provided and a quick look at the source code for that should give
	you courage to tackle any modifications necessary for your favourite
	database. Using this DAL API is much easier than having to do these
	tweaks when they are distributed throughout your code in embedded
	SQL-statements.
	
A high-level plan for writing an OData provider would therefore be:

0.	Identify the underlying DAL class that is most suited to your needs
	or, if there isn't one, create a new DAL implementation using the
	existing implementations as a guide.

1.	Create a metadata document to describe your data model

2.	Write a test program that uses the DAL classes directly to validate
	that your model and the DAL implementation are working correctly

3.	Create :py:class:`pyslet.odata2.server.Server` that is bound to your
	model test it with an OData client to ensure that it works as
	expected. 

4.	Finally, create a sub-class of the server with any specific
	customisations needed by your application: mainly to implement your
	applications authentication and authorization model.  (For a
	read-only service there may be nothing to do here.)

Of course, if all you want to do is use these interfaces as a DAL in
your own application you can stop at item 3 above.

.. toctree::
   :maxdepth: 2

   memexample
   sqlexample
   customexample


Which DAL Implementation?
-------------------------

Transient Data
++++++++++++++

If your data is relatively small and transient then you could use the in
memory implementation of the DAL API directly.  This is the easiest
route to creating a new OData provider as you won't need to override any
of of the implementations.

Look at the example project :doc:`memexample` to see how easy it
is to create a useful in-memory key-value store.


SQL
+++

If your data is currently in a SQL database, or if you intend to write a
read-only data source and you could easily put your data into a SQL
database, then you should use the Python DB ABI-based implementation as
a starting point.

If your data is in a database other than a SQLite database you will have
to provide a few tweaks by deriving a new class from
:py:class:`~pyslet.odata2.sqlds.SQLEntityContainer`.  This can't be helped,
the DB API does a good job at dealing with most issues, such as
variation in parameterization conventions and expected data types, but
SQL connection parameters and the occasional differences in the SQL
syntax mean there is likely to be a small amount of work to do.

A look at the customisations required for
:py:class:`~pyslet.odata2.sqlds.SQLiteEntityContainer` where a handful of
methods have had to be overridden should point the way.  You may want to
override the default
:py:class:`~pyslet.odata2.sqlds.SQLEntityCollection` object too where
functions and operators from the the expression language can be mapped
on to parameterized SQL queries.

Once you have a class that can connect to your chosen database move on to
:doc:`sqlexample`.


Customer Provider
+++++++++++++++++

Writing a customer provider isn't as hard as you might think, provided
your data set is of a mangeable size then you can use the built-in
behaviour of the base classes to take care of almost all the API's
needs.  You just need to expose the entity values themselves by
implementing a couple of methods!

Look at the example project :doc:`customexample` to see how you
can write a simple application that exposes a download-directory to the
web using OData (providing a little more metadata than is easily
obtainable from plain HTTP.)

An OData Proxy
++++++++++++++

Finally, the OData client implementation of the DAL API opens the
possibility of writing an OData proxy server.  Why would you do this?

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
on the same domain.

An OData proxy can be co-located with your application to overcome this
problem.  A dumb proxy is probably best implemented by the web-server,
rather than a full-blown web application but the classes defined in this
package are a good starting point for writing a more intelligent proxy
such as one that checks for a valid session with your application before
proxying the request.

The implementation isn't trivial because the identities of the entities
created by the client (as reported by
:py:meth:`~pyslet.odata2.csdl.Entity.get_location`) are the URLs of the
entities as they appear in the remote data service whereas the OData
proxy needs to serve up entities with identities with URLs that appear
under its service root.  As a result, you need to create a copy of the
client's model and implement proxy classes that implement the API by
pulling and pushing entities into the client.  This isn't as much work
as it sounds and you probably want to do it anyway so that your proxy
can add value, such as hiding parts of the model that shouldn't be
proxied, adding constraints for authorisation, etc.

I'm the process of developing a set of proxy classes to act as a good
starting point for this type of application.  Watch this space, or reach
out to me via the `Pyslet home page
<https://code.google.com/p/qtimigration/>`_.
 
 
