Data Consumers
==============

Warning: the OData client doesn't support certificate validation when
accessing servers through https URLs.  This feature is coming soon...

.. toctree::
   :maxdepth: 2

Introduction
------------

Let's start with a simple illustration of how to consume data using the
DAL API by walking through the use of the OData client.

The client implementation uses Python's logging module to provide
logging, when learning about the client it may help to turn logging up
to "INFO" as it makes it clearer what the client is doing.  "DEBUG"
would show exactly what is passing over the wire.::

	>>> import logging
	>>> logging.basicConfig(level=logging.INFO)

To create a new client simply instantiate a Client object.  You can pass
the URL of the service root you wish to connect to directly to the
constructor which will then call the service to download the list of
feeds and the metadata document from which it will set the
:py:attr:`Client.model`.

	>>> from pyslet.odata2.client import Client
	>>> c = Client("http://services.odata.org/V2/Northwind/Northwind.svc/")
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/ HTTP/1.1
	INFO:root:Finished Response, status 200
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/$metadata HTTP/1.1
	INFO:root:Finished Response, status 200
	>>>

The :py:attr:`Client.feeds` attribute is a dictionary mapping the
exposed feeds (by name) onto :py:class:`~pyslet.odata2.csdl.EntitySet`
instances.  This makes it easy to open the feeds as EDM collections.  In
your code you'd typically use the with statement when opening the
collection but for clarity we'll continue on the python command line::

	>>> products = c.feeds['Products'].open()
	>>> for p in products: print p
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products HTTP/1.1
	INFO:root:Finished Response, status 200
	1
	2
	3
	... [and so on]
	...
	20
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$skiptoken=20 HTTP/1.1
	INFO:root:Finished Response, status 200
	21
	22
	23
	... [and so on]
	...
	76
	77
	>>>

Note that products behaves like a dictionary, iterating through it
iterates through the keys in the dictionary.  In this case these are the
keys of the entities in the collection of products.  Notice that the
client logs several requests to the server interspersed with the printed
output.  Subsequent requests use $skiptoken because the server is
limiting the maximum page size.  These calls are made as you iterate
through the collection allowing you to iterate through very large
collections.

The keys alone are of limited interest, let's try a similar loop but this
time we'll print the product names as well::

	>>> for k, p in products.iteritems(): print k, p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products HTTP/1.1
	INFO:root:Finished Response, status 200
	1 Chai
	2 Chang
	3 Aniseed Syrup
	...
	...
	20 Sir Rodney's Marmalade
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$skiptoken=20 HTTP/1.1
	INFO:root:Finished Response, status 200
	21 Sir Rodney's Scones
	22 Gustaf's Knäckebröd
	23 Tunnbröd
	...
	...
	76 Lakkalikööri
	77 Original Frankfurter grüne Soße
	>>>
	
Sir Rodney's Scones sound interesting, we can grab an individual record
in the usual way::

	>>> scones = products[21]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21) HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> for k, v in scones.data_items(): print k, v.value
	... 
	ProductID 21
	ProductName Sir Rodney's Scones
	SupplierID 8
	CategoryID 3
	QuantityPerUnit 24 pkgs. x 4 pieces
	UnitPrice 10.0000
	UnitsInStock 3
	UnitsOnOrder 40
	ReorderLevel 5
	Discontinued False
	>>>

Well, I've simply got to have some of these, let's use one of the navigation
properties to load information about the supplier::

	>>> supplier = scones['Supplier'].get_entity()
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)/Supplier HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> for k, v in supplier.data_items(): print k, v.value
	... 
	SupplierID 8
	CompanyName Specialty Biscuits, Ltd.
	ContactName Peter Wilson
	ContactTitle Sales Representative
	Address 29 King's Way
	City Manchester
	Region None
	PostalCode M14 GSD
	Country UK
	Phone (161) 555-4448
	Fax None
	HomePage None

Attempting to load a non existent entity results in a KeyError of
course::

	>>> p = products[211]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(211) HTTP/1.1
	INFO:root:Finished Response, status 404
	Traceback (most recent call last):
	  File "<stdin>", line 1, in <module>
	  File "/Library/Python/2.7/site-packages/pyslet/odata2/client.py", line 165, in __getitem__
		raise KeyError(key)
	KeyError: 211

Finally, when we're done, it is a good idea to close the open
collection::

	>>> products.close()

The Data Access Layer in Depth
------------------------------

In the introduction we created an OData Client object using a URL, but
in general the way you connect to a data service will vary depending on
the implementation.  The Client class itself isn't actually part of the
DAL API itself.

The API starts with a model of the *data service*.  The model is
typically parsed from an XML file. For the OData client the XML file is
obtained from the service's $metadata URL.  Here's an extract from the
Northwind $metadata file showing the definition of the data service,
I've removed the XML namespace definitions for brevity::

	<?xml version="1.0" encoding="utf-8" standalone="yes"?>
	<edmx:Edmx Version="1.0">
  		<edmx:DataServices m:DataServiceVersion="1.0">
    		<Schema Namespace="NorthwindModel">
      			<EntityType Name="Category">
      				<!-- rest of the definitions go here... -->

Each element is represented by an object in Pyslet, the starting point
for the API is the :py:class:`~pyslet.odata2.edmx.DataServices` object.
A DataServices object can contain multiple
:py:class:`~pyslet.odata2.csdl.Schema` elements, which in turn can
contain multiple :py:class:`~pyslet.odata2.csdl.EntityContainer`
elements which in turn can contain multiple
:py:class:`~pyslet.odata2.csdl.EntitySet` elements.  The following
diagram illustrates these relationships and compares them with
approximate equivalent concepts in a typical SQL-scenario.

.. image:: /images/dataservices.png

In the OData client example we used a short-cut to get to the EntitySet
objects we were interested in by using the feeds property of the client
itself.  However, we could have used the model directly as follows,
continuing with the same session::

	>>> c.model
	<pyslet.odata2.metadata.Edmx object at 0x10140a9d0>
	>>> c.model.DataServices
	<pyslet.odata2.metadata.DataServices object at 0x107fdb990>
	>>> for s in c.model.DataServices.Schema: print s.name
	... 
	NorthwindModel
	ODataWeb.Northwind.Model
	>>> c.model.DataServices['ODataWeb.Northwind.Model']
	<pyslet.odata2.csdl.Schema object at 0x10800cd90>
	>>> c.model.DataServices['ODataWeb.Northwind.Model']['NorthwindEntities']
	<pyslet.odata2.metadata.EntityContainer object at 0x10800cdd0>
	>>> c.model.DataServices['ODataWeb.Northwind.Model']['NorthwindEntities']['Products']
	<pyslet.odata2.metadata.EntitySet object at 0x10800f150>
	>>> c.feeds['Products']
	<pyslet.odata2.metadata.EntitySet object at 0x10800f150>

As you can see, the same EntitySet object can be obtained by looking it
up in the parent container which behaves like a dictionary, this in turn
can be looked up in the parent Schema which in turn can be looked up in
the DataServices enclosing object.  Elements of the model also support
deep references using dot-concatenation of names which makes the code
easier to read::

	>>> print c.model.DataServices['ODataWeb.Northwind.Model']['NorthwindEntities']['Products'].get_fqname()
	ODataWeb.Northwind.Model.NorthwindEntities.Products
	>>> c.model.DataServices['ODataWeb.Northwind.Model.NorthwindEntities.Products']
	<pyslet.odata2.metadata.EntitySet object at 0x10800f150>

When writing an application that would normally use a single database
you should pass an EntityCollection object to it as a data source rather
than the DataServices ancestor.  It is best not to pass an
implementation-specific class like the OData Client as that will make
the application dependent on a particular type of data source.


Entity Sets
~~~~~~~~~~~

The following attributes are useful for consumers of the API (and should
be treated as read only)

:py:attr:`~pyslet.odata2.csdl.EntitySet.name`
	The name of the entity set

:py:attr:`~pyslet.odata2.csdl.EntitySet.entityTypeName`
	The name of the entity set's EntityType

:py:attr:`~pyslet.odata2.csdl.EntitySet.entityType`
	The :py:class:`~pyslet.odata2.csdl.EntityType` object that defines
	the properties for entities in this set.

:py:attr:`~pyslet.odata2.csdl.EntitySet.keys`
	A list of the names of the keys for this EntitySet.  For example::

		>>> print products.keys
		[u'ProductID']

	For entity types with compound keys this list will contain multiple
	items of course.
  
The following methods are useful for consumers of the API.

:py:meth:`~pyslet.odata2.csdl.EntitySet.get_fqname`
	Returns the fully qualified name of the entity set, suitable for
	looking up the entity set in the enclosing DataServices object.

:py:meth:`~pyslet.odata2.csdl.EntitySet.get_location`
	Returns a :py:class:`pyslet.rfc2396.URI` object that represents
	this entity set::
	
		>>> print products.get_location()
		http://services.odata.org/V2/Northwind/Northwind.svc/Products

	(If there is no base URL available this will be a relative URI.)

:py:meth:`~pyslet.odata2.csdl.EntitySet.open`
	Returns a :py:class:`pyslet.odata2.csdl.EntityCollection` object
	that can be used to access the entities in the set.
	
:py:meth:`~pyslet.odata2.csdl.EntitySet.get_target`
	Returns the target entity set of a named navigation property.
	
:py:meth:`~pyslet.odata2.csdl.EntitySet.get_multiplicity`
	Returns a tuple of multiplicity constants for the named navigation
	property.  Constants for these values are defined in
	:py:class:`pyslet.odata2.csdl.Multiplicity`, for example::
	
		>>> from pyslet.odata2.csdl import Multiplicity, multiplicity_to_str
		>>> print Multiplicity.ZeroToOne, Multiplicity.One, Multiplicity.Many
		0 1 2
		>>> products.get_multiplicity('Supplier')
		(2, 0)
		>>> map(lambda x:multiplicity_to_str(x),products.get_multiplicity('Supplier'))
		['*', '0..1']

:py:meth:`~pyslet.odata2.csdl.EntitySet.is_entity_collection`
	Returns True if the named navigation property points to a collection
	of entities or a single entity.  In Pyslet, you can treat all
	navigation properties as collections.  In the above example the
	collection of Supplier entities obtained by following the 'Supplier'
	navigation property of a Product entity will have at most 1 member. 
		

Entity Collections
~~~~~~~~~~~~~~~~~~

To continue with database analogy above, if EntitySets are like SQL
Tables EntityCollections are somewhat like the database cursors that you
use to actually read data - the difference is that EntityCollections can
only read entities from a single EntitySet.

An :py:class:`~pyslet.odata2.csdl.EntityCollection` may consume physical
resources (like a database connection) and so must be closed with its
:py:meth:`~pyslet.odata2.csdl.EntityCollection.close` method when you're done.
They support the context manager protocol to make this easier so you can
use them in with statements to make clean-up easier::

	with c.feeds['Products'].open() as products:
		if 42 in products:
			print "Found it!"

The close method is called automatically when the with statement
exits.

Entity collections also behave like a python dictionary of
:py:class:`~pyslet.odata2.csdl.Entity` instances keyed on a value
representing the Entity's key property or properties.  The keys are
either single values (as in the above code example) or tuples in the
case of compound keys. The order of the values in the tuple is taken
from the order of the PropertyRef definitions in the model.

There are two ways to obtain an EntityCollection object.  You can open
an entity set directly or you can open a collection by navigating from a
specific entity through a named navigation property.  Although dictionary-like
there are some differences with true dictionaries.

When you have opened a collection from the base entity set the following
rules apply:

collection[key]
	Returns a new :py:class:`~pyslet.odata2.csdl.Entity` instance by
	looking up the *key* in the collection.  As a result, subsequent
	calls will return a different object, but with the same key!
	
collection[key] = new_entity
	For an existing entity this is essentially a no-operation.  This
	form of assignment cannot be used to create a new entity in the
	collection because the act of inserting the entity may alter its key
	(for example, when the entity set represents a database table with
	an auto-generated primary key).  See below for information on how
	to create and update entities.

del collection[key]
	In contrast, del will remove an entity from the collection completely.
	
When an EntityCollection represents a collection of entities obtained by
navigation then these rules are updated as follows:		

collection[key]
	Normally returns a new :py:class:`~pyslet.odata2.csdl.Entity`
	instance by looking up the *key* in the collection but when the
	navigation property has been expanded it will return a cached Entity
	(so subsequent calls will return the same object without looking
	up the key in the data source again).
	
collection[key]=existingEntity
	Provided that *key* is the key of *existingEntity* this will add an
	existing entity to this collection, effectively creating a link from
	the entity you were navigating from to an existing entity.  

del collection[key]
	Removes the entity with *key* from this collection.  The entity is
	not deleted from its EntitySet, is merely unlinked from the entity
	you were navigating from.
	
The following attribute is useful for consumers of the API (and should
be treated as read only)

:py:attr:`~pyslet.odata2.csdl.EntityCollection.entity_set`
	The :py:class:`~pyslet.odata2.csdl.EntitySet` of this collection. In
	the case of a collection opened through navigation this is the base
	entity set. 

In addition to all the usual dictionary methods like *len*, *itervalues*
and so on, the following methods are useful for consumers of the API:

:py:meth:`~pyslet.odata2.csdl.EntityCollection.get_location`
	Returns a :py:class:`pyslet.rfc2396.URI` object that represents
	this entity collection.
	
:py:meth:`~pyslet.odata2.csdl.EntityCollection.get_title`
	Returns a user-friendly title to represent this entity collection.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.new_entity`
	Creates a new entity suitable for inserting into this collection.
	The entity does not exist until it is inserted with insert_entity.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.copy_entity`
	Creates a new entity by copying all non-key properties from another
	entity. The entity does not exist until it is inserted with
	insert_entity.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.insert_entity`
	Inserts an entity previously created by new_entity or copy_entity.
	When inserting an entity any active filter is ignored.
	
	Warning: an active filter may result in a paradoxical KeyError::
	
		import pyslet.odata2.core as core
		with people.open() as collection:
			collection.set_filter(
			    core.CommonExpression.from_str("startswith(Name,'D')"))
			new_entity = collection.new_entity()
			new_entity['Key'].set_from_value(1)
			new_entity['Name'].set_from_value(u"Steve")
			collection.insert_entity(new_entity)
			# new_entity now exists in the base collection but... 
			e1 = collection[1]
			# ...raises KeyError as new_entity did not match the filter!
	
	It is recommended that collections used to insert entities are not
	filtered.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.update_entity`
	Updates an existing entity following changes to the Entity's values.
	You can't update the values of key properties.  To change the key
	you will need to create a new entity with copy_entity, insert the new
	entity and then remove the old one.  Like insert_entity, the current
	filter is ignored.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.set_page`
	Sets the top and skip values for this collection, equivalent to the
	$top and $skip options in OData. This value only affects calls to
	iterpage.  See `Paging`_ for more information.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.iterpage`
	Iterates through a subset of the entities returned by itervalues
	defined by the top and skip values.  See `Paging`_ for more
	information.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.set_filter`
	Sets the filter for this collection, equivalent to the $filter
	option in OData. Once set this value effects all future entities
	returned from the collection (with the exception of new_entity).  See
	`Filtering Collections`_ for more information.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.set_orderby`
	Sets the filter for this collection, equivalent to the $orderby
	option in OData. Once set this value effects all future iterations
	through the collection.  See `Ordering Collections`_ for more
	information.

:py:meth:`~pyslet.odata2.csdl.EntityCollection.set_expand`
	Sets expand and select options for this collection, equivalent to
	the $expand and $select system query options in OData.  Once set
	these values effect all future entities returned from the collection
	(with the exception of new_entity).  See `Expand and Select`_ for
	more information.

Paging
++++++

*Supported from build 0.4.20140215 onwards*

The $top/$skip options in OData are a useful way to restrict the amount
of data that an OData server returns.  The collection dictionary always
behaves as if it contains all entities so the value returned by *len*
doesn't change if you set top and skip values and nor does the set of
entities returned by itervalues and similar methods.

In most cases, the server will impose a reasonable maximum on each
request using server-enforced paging.  However, you may wish to set a
smaller *top* value or simply have more control over the automatic
paging implemented by the default iterators. 

To iterate through a single page of entities you'll start by using the
the :py:meth:`~pyslet.odata2.csdl.EntityCollection.set_page` method to
specify values for top and, optinally, skip.  You must then use the
:py:meth:`~pyslet.odata2.csdl.EntityCollection.iterpage` method to 
iterate through the entities in just that page.  The *set_next*
boolean parameter indicates whether or not the next call to iterpage
iterates over the same page or the next page of the collection.

To continue the example above, in which *products* is an open collection
from the Northwind data service::

	>>> products.set_page(5,50)
	>>> for p in products.iterpage(True): print p.key(), p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$skip=50&$top=5 HTTP/1.1
	INFO:root:Finished Response, status 200
	51 Manjimup Dried Apples
	52 Filo Mix
	53 Perth Pasties
	54 Tourtière
	55 Pâté chinois
	>>> for p in products.iterpage(True): print p.key(), p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$skip=55&$top=5 HTTP/1.1
	INFO:root:Finished Response, status 200
	56 Gnocchi di nonna Alice
	57 Ravioli Angelo
	58 Escargots de Bourgogne
	59 Raclette Courdavault
	60 Camembert Pierrot

In some cases, the server will restrict the page size and fewer entities
will be returned than expected, in these cases the skiptoken is used
automatically when the next page is requested::

	>>> products.set_page(30, 50)
	>>> for p in products.iterpage(True): print p.key(), p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$skip=50&$top=30 HTTP/1.1
	INFO:root:Finished Response, status 200
	51 Manjimup Dried Apples
	52 Filo Mix
	53 Perth Pasties
	... [and so on]
	...
	69 Gudbrandsdalsost
	70 Outback Lager
	>>> for p in products.iterpage(True): print p.key(), p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$top=30&$skiptoken=70 HTTP/1.1
	INFO:root:Finished Response, status 200
	71 Flotemysost
	72 Mozzarella di Giovanni
	73 Röd Kaviar
	74 Longlife Tofu
	75 Rhönbräu Klosterbier
	76 Lakkalikööri
	77 Original Frankfurter grüne Soße


Filtering Collections
+++++++++++++++++++++

By default, an entity collection contains all items in the entity set
or, if the collection was obtained by navigation, all items linked to
the entity by the property being navigated.  Filtering a collection
(potentially) selects a sub-set of the these entities based on a filter
expression. 

Filter expressions are set using the
:py:meth:`~pyslet.odata2.csdl.EntityCollection.set_filter` method of the
collection.  Once a filter is set, the dictionary methods, and iterpage,
will only return entities that match the filter.

The easiest way to set a filter is to compile one directly from a string
representation using OData's query language.  For example::

	>>> import pyslet.odata2.core as core
	>>> filter = core.CommonExpression.from_str("substringof('one',ProductName)")
	>>> products.set_filter(filter)
	>>> for p in products.itervalues(): print p.key(), p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$filter=substringof('one'%2CProductName) HTTP/1.1
	INFO:root:Finished Response, status 200
	21 Sir Rodney's Scones
	32 Mascarpone Fabioli

To remove a filter, set the filter expression to None::

	>>> products.set_filter(None)


Ordering Collections
++++++++++++++++++++

Like OData and python dictionaries, this API does not specify a default
order in which entities will be returned by the iterators.  However,
unlike python dictionaries you can control this order using an orderby
option. 

OrderBy expressions are set using the
:py:meth:`~pyslet.odata2.csdl.EntityCollection.set_orderby` method of the
collection.  Once an order by expression is set, the dictionary methods,
and iterpage, will return entities in the order specified.

The easiest way to define an ordering is to compile one directly from a
string representation using OData's query language.  For example::

	>>> ordering=core.CommonExpression.orderby_from_str("ProductName desc")
	>>> products.set_orderby(ordering)
	>>> for p in products.itervalues(): print p.key(), p['ProductName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$orderby=ProductName%20desc HTTP/1.1
	INFO:root:Finished Response, status 200
	47 Zaanse koeken
	64 Wimmers gute Semmelknödel
	63 Vegie-spread
	50 Valkoinen suklaa
	7 Uncle Bob's Organic Dried Pears
	23 Tunnbröd
	... [and so on]
	...
	56 Gnocchi di nonna Alice
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products?$orderby=ProductName%20desc&$skiptoken='Gnocchi%20di%20nonna%20Alice',56 HTTP/1.1
	INFO:root:Finished Response, status 200
	15 Genen Shouyu
	33 Geitost
	71 Flotemysost
	... [and so on]
	...
	40 Boston Crab Meat
	3 Aniseed Syrup
	17 Alice Mutton

To remove an ordering, set the orderby expression to None::

	>>> products.Orderby(None)


Expand and Select
+++++++++++++++++

Expansion and selection are two interrelated concepts in the API. 
Expansion allows you to follow specified navigation properties
retrieving the entities they link to in the same way that simple and
complex property values are retrieved.

Expand options are represented by nested dictionaries of strings.  For
example, to expand the Supplier navigation property of Products you
would use a dictionary like this:: 

	expansion={'Supplier':None}

The value in the dictionary is either None, indicating no further
expansion, or another dictionary specifying the expansion to apply to
any linked Suppliers::

	>>> products.set_expand({'Supplier':None}, None)
	>>> scones = products[21]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)?$expand=Supplier HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> supplier=scones['Supplier'].get_entity()
	>>> for k, v in supplier.data_items(): print k, v.value
	... 
	SupplierID 8
	CompanyName Specialty Biscuits, Ltd.
	ContactName Peter Wilson
	ContactTitle Sales Representative
	Address 29 King's Way
	City Manchester
	Region None
	PostalCode M14 GSD
	Country UK
	Phone (161) 555-4448
	Fax None
	HomePage None

A critical point to note is that applying an expansion to a collection
means that linked entities are retrieved at the same time as the entity
they are linked to and cached.  In the example above, the get_entity call
does not generate a call to the server.  Compare this with the same code
executed without the expansion::

	>>> products.set_expand(None, None)
	>>> scones = products[21]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21) HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> supplier = scones['Supplier'].get_entity()
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)/Supplier HTTP/1.1
	INFO:root:Finished Response, status 200

The select option complements expansion, narrowing down the simple and
complex properties that are retrieved from the data source.  You specify
a select option in a similar way, using nested dictionaries.  Simple and
complex properties must always map to None, for a more complex example
with navigation properties see below.  Suppose we are only interested in
the product name::

	>>> products.set_expand(None, {'ProductName':None})
	>>> scones = products[21]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)?$select=ProductID%2CProductName HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> for k, v in scones.data_items(): print k, v.value
	... 
	ProductID 21
	ProductName Sir Rodney's Scones
	SupplierID None
	CategoryID None
	QuantityPerUnit None
	UnitPrice None
	UnitsInStock None
	UnitsOnOrder None
	ReorderLevel None
	Discontinued None

In Pyslet, the values of the key properties are *always* retrieved, even
if they are not selected.  This is required to maintain the
dictionary-like behaviour of the collection.  An entity retrieved this
way has NULL values for any properties that weren't retrieved.  The
:py:meth:`~pyslet.odata2.csdl.Entity.is_selected` method allows you to
determine if a value is NULL in the data source or NULL because it is
not selected::

	>>> for k, v in scones.data_items(): 
	...  if scones.is_selected(k): print k, v.value
	... 
	ProductID 21
	ProductName Sir Rodney's Scones

The expand and select options can be combined in complex ways::

	>>> products.set_expand({'Supplier':None}, {'ProductName':None, 'Supplier':{'Phone':None}})
	>>> scones = products[21]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)?$expand=Supplier&$select=ProductID%2CProductName%2CSupplier%2FPhone%2CSupplier%2FSupplierID HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> supplier = scones['Supplier'].get_entity()
	>>> for k, v in scones.data_items():
	...  if scones.is_selected(k): print k, v.value
	... 
	ProductID 21
	ProductName Sir Rodney's Scones
	>>> for k, v in supplier.data_items():
	...  if supplier.is_selected(k): print k, v.value
	... 
	SupplierID 8
	Phone (161) 555-4448

  
Entity Objects
~~~~~~~~~~~~~~

Continuing further with the database analogy and
:py:class:`~pyslet.odata2.csdl.Entity` is like a single record.

Entity instances behave like a read-only dictionary mapping property
names onto their values.  The values are either SimpleValue_, Complex_
or DeferredValue_ instances.  All property values are created on
construction and cannot be assigned.  To update a SimpleValue, whether
it is a direct child or part of a Complex value, use its
:py:meth:`~pyslet.odata2.csdl.SimpleValue.set_from_value` method::
	
	entity['Name'].set_from_value("Steve")
	entity['Address']['City'].set_from_value("Cambridge")
	
The following attributes are useful for consumers of the API (and should
be treated as read only):

:py:attr:`~pyslet.odata2.csdl.Entity.entity_set`
	The :py:class:`~pyslet.odata2.csdl.EntitySet` to which this entity
	belongs.

:py:attr:`~pyslet.odata2.csdl.Entity.type_def`
	The :py:class:`~pyslet.odata2.csdl.EntityType` which defines this
	entity's type.

:py:attr:`~pyslet.odata2.csdl.Entity.exists`
	True if this entity exists in the collection, i.e., it was returned
	by one of the dictionary methods of an entity collection such as
	*itervalues* or [key] look-up.

The following methods are useful for consumers of the API:

:py:meth:`~pyslet.odata2.csdl.Entity.key`
	Returns the entity's key, as a single python value or tuple in the
	case of compound keys
	
:py:meth:`~pyslet.odata2.core.Entity.get_location`
	Returns a :py:class:`pyslet.rfc2396.URI` object that represents this
	entity::
	
		>>> print scones.get_location()
		http://services.odata.org/V2/Northwind/Northwind.svc/Products(21)

:py:meth:`~pyslet.odata2.csdl.Entity.data_keys`
	Iterates over the simple and complex property names::
	
		>>> list(scones.data_keys())
		[u'ProductID', u'ProductName', u'SupplierID', u'CategoryID', u'QuantityPerUnit', u'UnitPrice', u'UnitsInStock', u'UnitsOnOrder', u'ReorderLevel', u'Discontinued']

:py:meth:`~pyslet.odata2.csdl.Entity.data_items`
	Iterates over tuples of simple and complex property (name,value)
	pairs. See above for examples of usage.

:py:meth:`~pyslet.odata2.csdl.Entity.is_selected`
	Tests if the given data property is selected. 

:py:meth:`~pyslet.odata2.csdl.Entity.navigation_keys`
	Iterates over the navigation property names::
	
		>>> list(scones.navigation_keys())
		[u'Category', u'Order_Details', u'Supplier']

:py:meth:`~pyslet.odata2.csdl.Entity.navigation_items`
	Iterates over tuples of navigation property (name,DeferredValue)
	pairs.

:py:meth:`~pyslet.odata2.csdl.Entity.is_navigation_property`
	Tests if a navigation property with the given name exists 


The following methods can be used only on entities that exists, i.e.,
entities that have been returned from one of the collection's dictionary
methods:

:py:meth:`~pyslet.odata2.csdl.Entity.commit`
	Normally you'll use the the update_entity method of an open
	EntityCollection but in cases where the originating collection is no
	longer open this method can be used as a convenience method for
	opening the base collection, updating the entity and then closing
	the collection collection again.

:py:meth:`~pyslet.odata2.csdl.Entity.delete`
	Deletes this entity from the base entity set.  If you already have
	the base entity set open it is more efficient to use the *del*
	operator but if the collection is no longer open or the entity was
	obtained from a collection opened through navigation then this
	method can be used to delete the entity.

The following method can only be used on entities that don't exist,
i.e., entities returned from the collection's new_entity or copy_entity
methods that have not been inserted.
 
:py:meth:`~pyslet.odata2.csdl.Entity.set_key`
	Sets the entity's key


SimpleValue
+++++++++++

Simple property values are represented by (sub-classes of)
:py:class:`~pyslet.odata2.csdl.SimpleValue`, they share a number of
common methods:

:py:meth:`~pyslet.odata2.csdl.SimpleValue.is_null`
	Returns True if this value is NULL.  This method is also used
	by Python's non-zero test so::
	
		if entity['Property']:
			print entity['Property'].value
			# prints even if value is 0

	will print the Property value of entity if it is non-NULL.  In
	particular, it will print empty strings or other representations of
	zero.  If you want to exclude these from the test you should test
	the value attribute directly::

		if entity['Property'].value:
			print entity['Property'].value
			# will not print if value is 0
	
:py:meth:`~pyslet.odata2.csdl.SimpleValue.set_from_value`
	Updates the value, coercing the argument to the correct type and
	range checking its value.

:py:meth:`~pyslet.odata2.csdl.SimpleValue.SetFromSimpleValue`
	Updates the value from another SimpleValue, if the types match then
	the value is simply copied, otherwise the value is coerced using
	set_from_value.

:py:meth:`~pyslet.odata2.csdl.SimpleValue.set_from_literal`
	Updates the value by parsing it from a (unicode) string.  This is
	the opposite to the unicode function.  The literal form is the form
	used when serializing the value to XML (but does not include XML
	character escaping).

:py:meth:`~pyslet.odata2.csdl.SimpleValue.set_null`
	Updates the value to NULL
	
The value attribute is always an immutable value in python and so can be
used as a key in your own dictionaries.  The following list describes
the mapping from the EDM-defined simple types to their corresponding
native Python types.

Edm.Boolean:
	one of the Python constants True or False
	
Edm.Byte, Edm.SByte, Edm.Int16, Edm.Int32:
	int

Edm.Int64:
	long

Edm.Double, Edm.Single:
	python float

Edm.Decimal:
	python Decimal instance (from the built-in decimal module)

Edm.DateTime, Edm.DateTimeOffset:
	py:class:`pyslet.iso8601.TimePoint` instance
	
	This is a custom object in Pyslet, see `Working with Dates`_ for
	more information.
	
Edm.Time:
	py:class:`pyslet.iso8601.Time` instance
	
	Early versions of the OData specification incorrectly mapped this
	type to the XML Schema duration.  The use of a Time object to
	represent it, rather than a duration, reflects this correction.

	See `Working with Dates`_ for more information.

Edm.Binary:
	raw string
	
Edm.String:
	unicode string

Edm.Guid:
	Python UUID instance (from the built-in uuid module)


Complex
+++++++

Complex values behave like dictionaries of data properties.  They do not
have keys or navigation properties.  They are never NULL, is_null and the
Python non-zero test will always return True.

:py:meth:`~pyslet.odata2.csdl.SimpleValue.set_null`
	Although a Complex value can never be NULL, this method will set all
	of its data properties (recursively if necessary) to NULL


DeferredValue
+++++++++++++

Navigation properties are represented as :py:class:`DeferredValue`
instances.  All deferred values can be treated as an entity collection
and opened in a similar way to an entity set::

	>>> sconeSuppliers=scones['Supplier'].open()
	>>> for s in sconeSuppliers.itervalues(): print s['CompanyName'].value
	... 
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)/Supplier HTTP/1.1
	INFO:root:Finished Response, status 200
	Specialty Biscuits, Ltd.
	>>> 

For reading, a collection opened from a deferred value behaves in
exactly the same way as a collection opened from a base entity set. 
However, for writing there are some difference described above in
`Entity Collections`_.

If you use the dictionary methods to update the collection the changes
are made straight away by accessing the data source directly.  If you
want to make a number of changes simultaneously, or you want to link
entities to entities that don't yet exist, then you should use the
bind_entity method described below instead.  This method defers the
changes until the parent entity is updated (or inserted, in the case of
non-existent entities.)

Read-only attributes useful to data consumers:
 
:py:attr:`~pyslet.odata2.csdl.DeferredValue.name`
	The name of the navigation property

:py:attr:`~pyslet.odata2.csdl.DeferredValue.from_entity`
	The parent entity of this navigation property

:py:attr:`~pyslet.odata2.csdl.DeferredValue.p_def`
	The :py:class:`~pyslet.odata2.csdl.NavigationProperty` that defines
	this navigation property in the model.

:py:attr:`~pyslet.odata2.csdl.DeferredValue.isRequired`
	True if the target of this property has multiplicity 1, i.e., it is
	required.

:py:attr:`~pyslet.odata2.csdl.DeferredValue.isCollection`
	True if the target of this property has multiplicity *

:py:attr:`~pyslet.odata2.csdl.DeferredValue.isExpanded`
	True if this navigation property has been expanded.  Expanded
	navigation keep a cached version of the target collection.  Although
	you can open it and use it in the same way any other collection the
	values returned are returned from the cache and not by accessing the
	data source.

Methods useful to data consumers:

:py:meth:`~pyslet.odata2.csdl.DeferredValue.open`
	Returns an :py:class:`pyslet.odata2.csdl.EntityCollection` object
	that can be used to access the target entities.

:py:meth:`~pyslet.odata2.csdl.DeferredValue.get_entity`
	Convenience method that returns the entity that is the target of the
	link when the target has multiplicity 1 or 0..1.  If no entity is
	linked by the association then None is returned.

:py:meth:`~pyslet.odata2.csdl.DeferredValue.bind_entity`
	Marks the target entity for addition to this navigation collection
	on next update or insert.  If this navigation property is not a
	collection then the target entity will replace any existing target
	of the link.

:py:meth:`~pyslet.odata2.csdl.DeferredValue.target`
	The target entity set of this navigation property.


Working with Dates
++++++++++++++++++

In the EDM there are two types of date, DateTime and DateTimeOffset. 
The first represents a time-point in an implicit zone and the second
represents a time-point with the zone offset explicitly set.

Both types are represented by the custom :py:class:pyslet.iso8601.TimePoint`
class in Pyslet.

*time module from build 0.4.20140217 onwards*

Interacting with Python's time module is done using the struct_time type,
or lists that have values corresponding to those in struct_time::

	>>> import time
	>>> orders = c.feeds['Orders'].open()
	>>> orders.set_page(5)
	>>> top = list(orders.iterpage())
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Orders?$skip=0&$top=5 HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> print top[0]['OrderDate'].value
	1996-07-04T00:00:00
	>>> t = [None]*9
	>>> top[0]['OrderDate'].value.update_struct_time(t)
	>>> t
	[1996, 7, 4, 0, 0, 0, 3, 186, -1]
	>>> time.strftime("%a, %d %b %Y %H:%M:%S",t)
	'Thu, 04 Jul 1996 00:00:00'

You can set values obtained from the time module in a similar way::

	>>> import pyslet.iso8601 as iso
	>>> t = time.gmtime(time.time())
	>>> top[0]['OrderDate'].set_from_value(iso.TimePoint.from_struct_time(t))
	>>> print top[0]['OrderDate'].value
	2014-02-17T21:51:41

But if you just want a timestamp use one of the built-in factory
methods::

	>>> top[0]['OrderDate'].set_from_value(iso.TimePoint.from_now_utc())
	>>> print top[0]['OrderDate'].value
	2014-02-17T21:56:23

In future versions, look out for better support for datetime and
calendar module conversion methods.


Working with Media Resources
++++++++++++++++++++++++++++

OData is based on Atom and the Atom Publishing Protocol (APP) and
inherits the concept of media resources and media link entries from
those specifications.

In OData, an entity can be declared as a media link entry indicating
that the main purpose of the entity is to hold a media stream.  If the
entity with the following URL is a media link entry::

    http://host/Documents(123) 

then the following URL provides access to the associated media resource::

    http://host/Documents(123)/$value

In the DAL this behaviour is modelled by operations on the *collection*
containing the entities.  The methods you'll use are:

:py:meth:`~pyslet.odata2.core.EntityCollection.is_medialink_collection`
	Returns True if the entities are media link entries

:py:meth:`~pyslet.odata2.core.EntityCollection.read_stream`
	Reads information about a stream, optionally copying the stream's
	data to a file-like object.

:py:meth:`~pyslet.odata2.core.EntityCollection.new_stream`
	Creates a new media resource, copying the stream's data from a
	file-like object.
	
	This method implicitly creates an associated media link entry and
	returns the resulting :py:class:`~pyslet.odata2.csdl.Entity` object.
	By its nature, APP does not guarantee the URL that will be used to
	store a posted resource.  The implication for OData is that you
	can't specify the key that will be used for the media resource's
	entry, though this method does allow you to supply a hint.

:py:meth:`~pyslet.odata2.core.EntityCollection.udpate_stream`
	Updates a media resource, copying the stream's new data from a
	file-like object.

If a collection is a collection of media link entries then the behaviour
of :py:meth:~pyslet.odata2.core.EntityCollection.insert_entity` is
modified as entities are created implicitly when a new stream is added
to the collection.  In this case, insert_entity creates an empty stream
of type application/octet-stream and then merges the property values
from the entity being inserted into the new media link entry created for
the stream.
 

	




	
	
