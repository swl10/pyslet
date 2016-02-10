HTTP Cookies
============

.. py:module:: pyslet.http.cookie

This module contains classes for handling Cookies, as defined by RFC6265_
HTTP State Management Mechanism

..  _RFC6265: http://tools.ietf.org/html/rfc6265


Client Scenarios
----------------

By default, Pyslet's HTTP client does not support cookies.  Adding
support, if you want it, is done with the :class:`CookieStore` class. 
All you need to do is create an instance and add it to the client before
processing any requests::

    import pyslet.http.client as http
    
    client = http.Client()
    cookie_store = http.cookie.CookieStore()
    client.set_cookie_store(cookie_store)

Support for cookies is then transparently added to each request.

By default, the CookieStore object does not support domain cookies
because it doesn't know which domains are effectively top level domains
(TLDs) so treats all domains as effective TLDs. Domain cookies can't be
stored for TLDs as this would allow a website at www.exampleA.com to set
*or overwrite* a cookie in the 'com' domain which would then be sent to
www.exampleB.com.  There are lots of reasons why this is a bad idea,
websites could disrupt each others operation or worse, compromise
security and user privacy.

For most applications you can fix this by creating exceptions for
domains you want your client to trust.  For example, if you want to
interact with www.example.com and www2.example.com you might want to
allow domain cookies for example.com, knowing that the effective TLD in
this case is simply 'com'.

    cookie_store.add_private_suffix('example.com')

If you want to emulate the behaviour of real browsers you will need to
upload a proper database of effective TLDs.  For more information see
:meth:`CookieStore.fetch_public_suffix_list` and
:meth:`CookieStore.set_public_list`.  Be warned, the public suffix
list changes routinely and you'll want to ensure you have the latest
values loaded.


Web Application Scenarios
-------------------------

If you are writing a web application you may want to handle cookies
directly by adding response headers explicitly to a response object
provided by your web framework.

There are two classes for representing cookie definitions, you should
use the stricter :class:`Section4Cookie` when creating cookies as this
follows the recommended syntax in the RFC and will catch problems such
as attempting to set a cookie value containing a comma.  Although user
agents are supposed to cope with such values some systems are now
rejecting cookies that do not adhere to the stricter section 4
definitions.

The following code creates a cookie called SID with a maximum lifespan
of 15 minutes::

    import pyslet.http.cookie as cookie
    
    c = cookie.Section4Cookie("SID", "31d4d96e407aad42", max_age=15*60,
                              path="/", http_only=True, secure=True)
    print c

It outputs the text required to set the Set-Cookie header::

    SID=31d4d96e407aad42; Path=/; Max-Age=900; Secure; HttpOnly

You may want to add additional attributes such as an expires time for
backwards compatibility or a domain to allow the cookie to be sent to
other websites in a shared domain.  See :class:`Cookie` for details.


Reference
---------

..	autoclass:: Cookie
	:members:
	:show-inheritance:


..	autoclass:: Section4Cookie
	:members:
	:show-inheritance:


Client Support
~~~~~~~~~~~~~~

User agents that support cookies are obliged to keep a cookie store in
which cookies can be saved and retrieved keyed on their domain, path and
cookie name.

Pyslet's approach is to provide an in-memory store with nodes defined
for each domain (host) that a cookie has been associated with or which
is the target of a public or private suffix rule.  Nodes are also
created for any implied parent domains and the result is a tree-like
structure of dictionaries that can be quickly searched for each request.

..	autoclass:: CookieStore
	:members:
	:show-inheritance:


Syntax
~~~~~~

The following basic functions can be used to test characters against the
syntax productions defined in the specification.  In each case, if the
argument is None then False is returned.

..	autoclass:: CookieParser
	:members:
	:show-inheritance:


Date and Time
+++++++++++++

..	autofunction:: split_year

..	autofunction:: split_month

..	autofunction:: split_day_of_month

..	autofunction:: split_time


Basic Syntax
++++++++++++

These functions follow the pattern of behaviour defined in the
:doc:`grammar` module, taking a *byte* as an argument.  They will all
return False if the argument is None.

..	autofunction:: is_delimiter

..	autofunction:: is_non_delimiter

..	autofunction:: is_non_digit

..	autofunction:: is_cookie_octet


Domain Name Syntax
++++++++++++++++++

..	autofunction:: domain_in_domain

..	autofunction:: split_domain

..  autofunction:: encode_domain

..	autofunction:: is_ldh_label

..	autofunction:: is_rldh_label

..	autofunction:: is_a_label



Exceptions
~~~~~~~~~~

..	autoclass:: CookieError
	:members:
	:show-inheritance:
