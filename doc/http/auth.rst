HTTP Authentication
===================

.. py:module:: pyslet.http.auth

Pyslet's http sub-package contains an auth module that supports
RFC2617_.  This module adds core support for HTTP's simple
challenge-response authentication.

..  _RFC2617: http://www.ietf.org/rfc/rfc2617.txt

Adding Credentials to an HTTP Request
-------------------------------------

The simplest way to do basic authentication is to simply add a
preformatted Authorization header to each request.  For example, if you
need to send a request to a website and you know that it requires you to
pass your basic auth credentials you could just do something like this::

    import pyslet.http.client as http
    c = http.Client()
    r = http.ClientRequest('https://www.example.com/mypage')
    r.set_header("Authorization", 'Basic Sm9oblNtaXRoOnNlY3JldA==')
    c.process_request(r)

Calculating the correctly formatted value for the Authorization header
can be simplified by creating a :class:`BasicCredentials` object::
    
    import pyslet.http.auth as auth
    credentials = auth.BasicCredentials()
    credentials.userid = "JohnSmith"
    credentials.password = "secret"
    str(credentials)

    'Basic Sm9oblNtaXRoOnNlY3JldA=='

As you can see, the credentials object takes care of the syntax for you.
The userid and password are character strings but you should be aware
that only characters in the ISO-8859-1 character set can be used in user
names and passwords.

If you don't want to add the Authorization header yourself you can
delegate responsibility to the http client itself.  Before you do that
though you have to add an additional piece of information to your
credentials objects: the protection space.  A protection space is simply
the combination of the http scheme (http/https), the host and any
optional port information.  You can calculate the protection space
associated with a URL using Pyslet's URI object::

    from pyslet.rfc2396 import URI
    uri = URI.from_octets(
        'https://www.example.com:443/mypage').get_canonical_root()
    str(uri)
    
    'https://www.example.com'

Notice that the :meth:`~pyslet.rfc2396.URI.get_canonical_root` method
takes care of figuring out default ports and removing the path for you
so you can get the protection space for any http-based URL.  By setting
the protectionSpace attribute on the BasicCredentials object you tell
the client which sites it should offer the credentials to::

    credentials.protectionSpace = uri
    c.add_credentials(credentials)
    r = http.ClientRequest('https://www.example.com/mypage')
    c.process_request(r)

The HTTP client has a credential store and an add_credentials method.
Once added, the following happens when a 401 response is received:

    1.  The client iterates through any received challenges
    2.  Each challenge is matched against the stored credentials
    3.  If matching credentials are found then an Authorization header
        is added and the request resent
    4.  If the request receives another 401 response indicating that the
        attempt to authenticate failed then the credentials are removed
        from the store and we go back to (1)

This process terminates when there are no more credentials that match
any of the challenges or when a code other than 401 is received.

If the matching credentials are BasicCredentials (and that's the only
type Pyslet supports out of the box), then some additional logic gets
activated on success. RFC 2617 says that for basic authentication, a
challenge implies that all paths "at or deeper than the depth of the
last symbolic element in the path field" fall into the same protection
space. Therefore, when credentials are used successfully, Pyslet adds
the path to the credentials using BasicCredentials.add_success_path.
Next time a request is sent to a URL on the same server with a path that
meets this criterium the Authorization header will be added
automatically without waiting for a 401 challenge response.

You can simulate this behaviour yourself if you want to pre-empt a 401
response completely.  You just need to add a suitable path to the
credentials *before* you add them to the client. So if you know your
credentials are good for everything in /website/~user/ you could
continue the above code like this::

    credentials.add_success_path('/website/~user/')

That last slash is really important, if you leave it off it will add
everything in '/website/' to your protection space which is probably not
what you want.


Class Reference
---------------

..	autoclass:: Credentials
	:members:
	:show-inheritance:

..	autoclass:: BasicCredentials
	:members:
	:show-inheritance:

..	autoclass:: Challenge
	:members:
	:show-inheritance:

..	autoclass:: BasicChallenge
	:members:
	:show-inheritance:



