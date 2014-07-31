HTTP Client
===========

.. py:module:: pyslet.http.client


Sending Requests
----------------

Here is a simple example of Pyslet's HTTP support in action from the
python interpreter::

    >>> import pyslet.http.client as http
    >>> c = http.Client()
    >>> r = http.ClientRequest('http://odata.pyslet.org')
    >>> c.process_request(r)
    >>> r.response.status
    200
    >>> print r.response.get_content_type()
    text/html; charset=UTF-8
    >>> print r.response.entity_body.getvalue()
    <html>
    <head><title>Pyslet Home</title></head>
    <body>
    <p><a href="http://qtimigration.googlecode.com/"><img src="logoc-large.png" width="1024"/></a></p>
    </body>
    </html>
    >>> c.close()

In its simplest form there are three steps required to make an HTTP
request, firstly you need to create a Client object.  The purpose of the
Client object is sending requests and receiving responses.  The second
step is to create a ClientRequest object describing the request you want
to make.  For a simple GET request you only need to specify the URL. The
third step is to instruct the Client to process the request.  Once this
method returns you can examine the request's associated response. The
response's entity body is written to a StringIO object by default.

The request and response objects are both derived classes of a basic
HTTP Message class.  This class has methods for getting and setting
headers.  You can use the basic
:py:meth:`~pyslet.http.messages.Message.get_header` and
:py:meth:`~pyslet.http.messages.Message.set_header` to set headers from
strings or, where provided, you can use special wrapper methods such as
:py:meth:`~pyslet.http.messages.Message.get_content_type` to get and set
headers using special-purpose class objects that represent parsed forms
of the expected value.  In the case of Content-Type headers the result
is a :py:meth:`~pyslet.http.params.MediaType` object.  Providing these
special object types is one of the main reasons why Pyslet's HTTP
support is different from other clients.  By exposing these structures
you can reuse HTTP concepts in other contexts, particularly useful when
other technical specifications make normative references to them.

Here is a glimpse of what you can do with a parsed media type,
continuing the above example::

    >>> type = r.response.get_content_type()
    >>> type
    MediaType('text','html',{'charset': ('charset', 'UTF-8')})
    >>> type.type
    'text'
    >>> type.subtype
    'html'
    >>> type['charset']
    'UTF-8'
    >>> type['name']
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "pyslet/http/params.py", line 382, in __getitem__
        repr(key))
    KeyError: "MediaType instance has no parameter 'name'"
    >>> 

There are lots of other special get\_ and set\_ methods on the
:py:class:`~pyslet.http.messages.Message`,
:py:class:`~pyslet.http.messages.Request`
and :py:class:`~pyslet.http.messages.Response` objects.

Pipelining
----------

One of the use cases that Pyslet's HTTP client is designed to cover is
reusing an HTTP connection to make multiple requests to the same host.
The example above takes care to close the Client object when we're done
because otherwise it would leave the connection to the server open ready
for another request.


Reference
---------

The client module imports the grammar, params, messages and auth modules
and these can therefore be accessed using a single import in your code. 
For example::

    import pyslet.http.client as http    
    type = http.params.MediaType('application', 'xml')

For more details of the objects exposed by those modules see
:py:mod:`pyslet.http.grammar`, :py:mod:`pyslet.http.params`,
:py:mod:`pyslet.http.messages` and :py:mod:`pyslet.http.auth`.


..	autoclass:: Client
	:members:
	:show-inheritance:

..	autoclass:: ClientRequest
	:members:
	:show-inheritance:

..	autoclass:: ClientResponse
	:members:
	:show-inheritance:


Exceptions
----------

..	autoclass:: RequestManagerBusy
	:members:
	:show-inheritance:
