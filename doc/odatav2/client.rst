OData Client
============

.. py:module:: pyslet.odata2.client

Overview
--------

Warning: this client doesn't support certificate validation when accessing
servers through https URLs.  This feature is coming soon...


Using the Client
----------------

The client implementation uses Python's logging module to provide logging, when learning
about the client it may help to turn logging up to "INFO" as it makes it clearer what the
client is doing.  "DEBUG" would show exactly what is passing over the wire.::

	>>> import logging
	>>> logging.basicConfig(level=logging.INFO)

To create a new client simply instantiate a Client object.  You can pass
the URL of the service root you wish to connect to directly to the
constructor which will then call the service to download the list of
feeds and the metadata document from which it will set the
:py:attr:`Client.model`.

	>>> from pyslet.odata2.client import Client
	>>> c=Client("http://services.odata.org/V2/Northwind/Northwind.svc/")
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

	>>> products=c.feeds['Products'].open()
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

	>>> for k,p in products.iteritems(): print k,p['ProductName'].value
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

	>>> scones=products[21]
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21) HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> for k,v in scones.data_items(): print k,v.value
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

	>>> supplier=scones['Supplier'].get_entity()
	INFO:root:Sending request to services.odata.org
	INFO:root:GET /V2/Northwind/Northwind.svc/Products(21)/Supplier HTTP/1.1
	INFO:root:Finished Response, status 200
	>>> for k,v in supplier.data_items(): print k,v.value
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

	>>> p=products[211]
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

	 
Reference
---------

..	autoclass:: Client
	:members:
	:show-inheritance:


Exceptions
----------

..	autoclass:: ClientException
	:members:
	:show-inheritance:

..	autoclass:: AuthorizationRequired
	:members:
	:show-inheritance:

..	autoclass:: UnexpectedHTTPResponse
	:members:
	:show-inheritance:
