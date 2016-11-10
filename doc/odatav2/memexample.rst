Sample Project: InMemory Data Service
=====================================

The sample code for this service is in the samples/memcache directory in
the Pyslet distribution.

This project demonstrates how to construct a simple OData service based
on the :py:class:`~pyslet.odata2.memds.InMemoryEntityContainer` class. 
We don't need any customisations, this class does everything we need
'out of the box'.

Step 1: Creating the Metadata Model
-----------------------------------

Unlike other frameworks for implementing OData services Pyslet starts
with the metadata model, it is not automatically generated: you must
write it yourself!

Fortunately, there are plenty of examples you can use as a template.  In
this sample project we'll write a very simple memory cache capable of
storing a key-value pair.  Here's our data model::

	<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
	<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"
		xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
		<edmx:DataServices m:DataServiceVersion="2.0">
			<Schema Namespace="MemCacheSchema" xmlns="http://schemas.microsoft.com/ado/2006/04/edm">
				<EntityContainer Name="MemCache" m:IsDefaultEntityContainer="true">
					<EntitySet Name="KeyValuePairs" EntityType="MemCacheSchema.KeyValuePair"/>
				</EntityContainer>
				<EntityType Name="KeyValuePair">
					<Key>
						<PropertyRef Name="Key"/>
					</Key>
					<Property Name="Key" Type="Edm.String" Nullable="false" MaxLength="256"
						Unicode="true" FixedLength="false"/>
					<Property Name="Value" Type="Edm.String" Nullable="false" MaxLength="8192"
						Unicode="true" FixedLength="false"/>
					<Property Name="Expires" Type="Edm.DateTime" Nullable="false"
						Precision="3"/>
				</EntityType>
			</Schema>
		</edmx:DataServices>
	</edmx:Edmx>

Our model has one defined EntityType called *KeyValuePair* and one
EntitySet called *KeyValuePairs* in a container called *MemCache*.  The
idea behind the model is that each key-value pair is inserted with an
expires time, after which it is safe to clean it up.

For simplicity, we'll save this model to a file and load it from the
file when our script starts up.  Here's the source code::

	import pyslet.odata2.metadata as edmx

    def load_metadata():
        """Loads the metadata file from the current directory."""
        doc = edmx.Document()
        with open('MemCacheSchema.xml', 'rb') as f:
            doc.read(f)
        return doc

The metadata module contains a Document object and the definitions of
the elements in the edmx namespace that enable us to read the XML file.

Step 2: Test the Model
----------------------

Let's write a simple test function to test our model::

    def test_data(mem_cache):
        with mem_cache.open() as collection:
            for i in range3(26):
                e = collection.new_entity()
                e.set_key(str(i))
                e['Value'].set_from_value(character(0x41 + i))
                e['Expires'].set_from_value(
                    iso.TimePoint.from_unix_time(time.time() + 10 * i))
                collection.insert_entity(e)


    def test_model():
        """Read and write some key value pairs"""
        doc = load_metadata()
        InMemoryEntityContainer(doc.root.DataServices['MemCacheSchema.MemCache'])
        mem_cache = doc.root.DataServices['MemCacheSchema.MemCache.KeyValuePairs']
        test_data(mem_cache)
        with mem_cache.open() as collection:
            for e in collection.itervalues():
                output("%s: %s (expires %s)\n" %
                       (e['Key'].value, e['Value'].value, str(e['Expires'].value)))

Our function comes in two parts (for reasons that will become clear
later).  The first function takes an EntitySet object and creates 26
key-value pairs with increasing expiry times.

The main function loads the metadata model, creates the
InMemoryEntityContainer object, calls the first function to create the
test data and then opens the *KeyValuePairs* collection itself to check
that everything is in order.  The function :func:`~pyslet.py2.output` is
just a Python 3 compatibility function (contrast with the builtin
'input') that allows us to write text to standard output.  Here's the
output from a sample run::

	>>> import memcache
	>>> memcache.test_model()
	24: Y (expires 2014-02-17T22:26:21)
	25: Z (expires 2014-02-17T22:26:31)
	20: U (expires 2014-02-17T22:25:41)
	21: V (expires 2014-02-17T22:25:51)
	22: W (expires 2014-02-17T22:26:01)
	23: X (expires 2014-02-17T22:26:11)
	1: B (expires 2014-02-17T22:22:31)
	0: A (expires 2014-02-17T22:22:21)
	3: D (expires 2014-02-17T22:22:51)
	2: C (expires 2014-02-17T22:22:41)
	5: F (expires 2014-02-17T22:23:11)
	4: E (expires 2014-02-17T22:23:01)
	7: H (expires 2014-02-17T22:23:31)
	6: G (expires 2014-02-17T22:23:21)
	9: J (expires 2014-02-17T22:23:51)
	8: I (expires 2014-02-17T22:23:41)
	11: L (expires 2014-02-17T22:24:11)
	10: K (expires 2014-02-17T22:24:01)
	13: N (expires 2014-02-17T22:24:31)
	12: M (expires 2014-02-17T22:24:21)
	15: P (expires 2014-02-17T22:24:51)
	14: O (expires 2014-02-17T22:24:41)
	17: R (expires 2014-02-17T22:25:11)
	16: Q (expires 2014-02-17T22:25:01)
	19: T (expires 2014-02-17T22:25:31)
	18: S (expires 2014-02-17T22:25:21)

It is worth pausing briefly here to look at the InMemoryEntityContainer
object. When we construct this object we pass in the EntityContainer and
it creates all the necessary storage for the EntitySets (and
AssociationSets, if required) that it contains.  It also binds internal
implementations of the EntityCollection object to the model so that, in
future, the EntitySet can be opened using the same API described
previously in :doc:`consumer`.  From this point on we don't need to
refer to the container again as we can just open the EntitySet directly
from the model.  That object is the heart of our application, blink and
you've missed it.


Step 4: Link the Data Source to the OData Server
------------------------------------------------

OData runs over HTTP so we need to assign a service root URL for the
server to run on.  We define a couple of constants to help with this::

    SERVICE_PORT = 8080
    SERVICE_ROOT = "http://localhost:%i/" % SERVICE_PORT

We're also going to use a separate thread to run the server, a global
variable helps here.  We're using Pythons wsgi interface for the server
which requires a callable object to handle requests.  The
:py:class:`~pyslet.odata2.server.Server` object implements callable
behaviour to enable this::

	import logging, threading
	from wsgiref.simple_server import make_server

	cache_app = None		#: our Server instance

    def run_cache_server():
        """Starts the web server running"""
        server = make_server('', SERVICE_PORT, cache_app)
        logging.info("Starting HTTP server on port %i..." % SERVICE_PORT)
        # Respond to requests until process is killed
        server.serve_forever()

The final part of server implementation involves loading the model,
creating the server object and then spawning the server thread::

    def main():
        """Executed when we are launched"""
        doc = load_metadata()
        InMemoryEntityContainer(doc.root.DataServices['MemCacheSchema.MemCache'])
        server = Server(serviceRoot=SERVICE_ROOT)
        server.set_model(doc)
        # The server is now ready to serve forever
        global cache_app
        cache_app = server
        t = threading.Thread(target=run_cache_server)
        t.setDaemon(True)
        t.start()
        logging.info("MemCache starting HTTP server on %s" % SERVICE_ROOT)

The Server object just takes the serviceRoot as a parameter on
construction and has a :py:meth:`~pyslet.odata2.server.Server.set_model`
method which is used to assign the metadata document to it.  That's all
you need to do to create it, it uses the same API described in
:doc:`consumer` to consume the data source and expose it via the
OData protocol.

At this stage we can test it via the terminal and a browser::

	>>> import memcache
	>>> memcache.main()
	>>>

At this point the server is running in a separate thread, listening on
port 8080. A quick check from the browser shows this to be the case,
when I hit http://localhost:8080/KeyValuePairs Firefox recognises that
the document is an Atom feed and displays the feed title.  The page
source shows::

	<?xml version="1.0" encoding="UTF-8"?>
	<feed xmlns="http://www.w3.org/2005/Atom" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xml:base="http://localhost:8080/">
		<id>http://localhost:8080/KeyValuePairs</id>
		<title type="text">MemCacheSchema.MemCache.KeyValuePairs</title>
		<updated>2014-02-17T22:41:51Z</updated>
		<link href="http://localhost:8080/KeyValuePairs" rel="self"/>
	</feed>

Looks like it is working!


Step 5: Customise the Server
----------------------------

We don't need to do much to customise our server, we'll assume that it
is only ever going to be exposed to clients we trust and so
authentication is not required or will be handled by some intermediate
proxy.

However, we do want to clean up expired entries automatically.  Let's
add one last function to our code::

	CLEANUP_SLEEP=10

    def cleanup_forever(mem_cache):
        """Runs a loop continuously cleaning up expired items"""
        now = edm.DateTimeValue()
        expires = core.PropertyExpression("Expires")
        t = core.LiteralExpression(now)
        filter = core.BinaryExpression(core.Operator.lt)
        filter.operands.append(expires)
        filter.operands.append(t)
        while True:
            now.set_from_value(iso.TimePoint.from_now_utc())
            logging.info("Cleanup thread running at %s", str(now.value))
            with mem_cache.open() as cacheEntries:
                cacheEntries.set_filter(filter)
                expired_list = list(cacheEntries)
                if expired_list:
                    logging.info("Cleaning %i cache entries", len(expired_list))
                    for expired in expired_list:
                        del cacheEntries[expired]
                cacheEntries.set_filter(None)
                logging.info(
                    "Cleanup complete, %i cache entries remain", len(cacheEntries))
            time.sleep(CLEANUP_SLEEP)

This function starts by building a filter expression manually.  Filter
expressions are just simple trees of expression objects.  We start with
a PropertyExpression that references a property named *Expires* and a
literal expression with a date-time value.  DateTimeValue is just a
sub-class of SimpleValue which was introduced in 
:doc:`consumer`.  Previously we've only seen simple values that
are part of an entity but in this case we create a standalone value to
use in the expression.  Finally, the filter expression is created as a
BinaryExpression using the less than operator and the operands appended.
The resulting expression tree looks like this:

.. image:: /images/cachefilter.png

Each time around the loop we can just update the value of the literal
expression with the current time.

This function takes an :py:class:`~pyslet.odata2.csdl.EntitySet` as a
parameter so we can open it to get the collection and then apply the
filter.  Once filtered, all matching cache entries are loaded into a
list before being deleted from the collection, one by one.

Finally, we remove the filter and report the number of remaining entries
before sleeping ready for the next run.

We'll call this function right after main, so we've got one thread
running the server and the main thread running the cleanup loop.

Now we can test, we start by firing up our server application::

	$ ./memcache.py 
	INFO:root:MemCache starting HTTP server on http://localhost:8080/
	INFO:root:Cleanup thread running at 2014-02-17T23:03:34
	INFO:root:Cleanup complete, 0 cache entries remain
	INFO:root:Starting HTTP server on port 8080...
	INFO:root:Cleanup thread running at 2014-02-17T23:03:44
	INFO:root:Cleanup complete, 0 cache entries remain

Unfortunately, we need more than a simple browser to test the
application properly.  We want to know that the key value pairs are
being created properly and for that we need a client capable of writing
to the service. Fortunately, Pyslet has an OData consumer, so we open
the interpreter in a new terminal and start interacting with our server::

	>>> from pyslet.odata2.client import Client
	>>> c=Client("http://localhost:8080/")

As soon as we start the client our server registers hits::

	INFO:root:Cleanup thread running at 2014-02-17T23:06:34
	INFO:root:Cleanup complete, 0 cache entries remain
	127.0.0.1 - - [17/Feb/2014 23:06:34] "GET / HTTP/1.1" 200 360
	127.0.0.1 - - [17/Feb/2014 23:06:34] "GET /$metadata HTTP/1.1" 200 1040
	INFO:root:Cleanup thread running at 2014-02-17T23:06:44
	INFO:root:Cleanup complete, 0 cache entries remain

Entering the data manually would be tedious but we already wrote a
suitable function for adding test data.  Because both the data source
and the OData client adhere to the same API we can simply pass the
EntitySet to our test_data function::

	>>> import memcache
	>>> memcache.test_data(c.feeds['KeyValuePairs'])
	
As we do this, the server window goes crazy as each of the POST requests
comes through::

	INFO:root:Cleanup thread running at 2014-02-17T23:08:14
	INFO:root:Cleanup complete, 0 cache entries remain
	127.0.0.1 - - [17/Feb/2014 23:08:23] "POST /KeyValuePairs HTTP/1.1" 201 717
	... [and so on]
	...
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	INFO:root:Cleanup thread running at 2014-02-17T23:08:24
	INFO:root:Cleaning 1 cache entries
	INFO:root:Cleanup complete, 19 cache entries remain
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	127.0.0.1 - - [17/Feb/2014 23:08:24] "POST /KeyValuePairs HTTP/1.1" 201 720
	INFO:root:Cleanup thread running at 2014-02-17T23:08:34
	INFO:root:Cleaning 1 cache entries
	INFO:root:Cleanup complete, 24 cache entries remain

We can then watch the data gradually decay as each entry times out in
turn.  We can easily repopulate the cache, this time let's catch it in a
browser by navigating to::
	
	http://localhost:8080/KeyValuePairs('25')?$format=json

The result is::

	{"d":{"__metadata":{"uri":"http://localhost:8080/KeyValuePairs('25')
	","type":"MemCacheSchema.KeyValuePair"},"Key":"25","Value":"Z","
	Expires":"/Date(1392679105162)/"}}

We can pick the value out directly with a URL like::

	http://localhost:8080/KeyValuePairs('25')/Value/$value

This returns the simple string 'Z'.

Conclusion
----------

It is easy to write an OData server using Pyslet!