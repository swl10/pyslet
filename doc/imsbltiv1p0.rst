IMS Basic Learning Tools Interoperability (version 1.0)
=======================================================

The IMS Basic Learning Tools Interoperability (BLTI) specification was
released in 2010. The purpose of the specification is to provide a link
between tool consumers (such as Learning Management Systems and portals)
and Tools (such as specialist assessment management systems).  Official
information about the specification is available from the IMS GLC under
the general name LTI_:

..  _LTI:  http://www.imsglobal.org/lti/

This module implements the Basic LTI specification documented in
the `Best Practice Guide`_

..  _Best Practice Guide:
    http://www.imsglobal.org/lti/blti/bltiv1p0/ltiBLTIimgv1p0.html

This module requires the oauthlib_ module to be installed.  The oauthlib
module is available from PyPi.

..  _oauthlib: https://pypi.python.org/pypi/oauthlib

.. py:module:: pyslet.imsbltiv1p0

This module is written from the point of view of the Tool Provider. 
There are a number of pre-defined classes to help you implement LTI in
your own Python applications.

Classes
-------
    
The :class:`ToolProviderApp` class is a mini-web framework in itself
which makes writing LTI tools much easier.  The framework does *not*
include a page templating language but it should be easy to integrate
with your templating system of choice.

Instances of ToolProviderApp are callable objects that support the WSGI
protocol for ease of integration into a wide variety of deployment
scenarios.

The base class implementation takes care of many aspects of your LTI
tool:

1.  Application settings are read from a JSON-encoded settings file.

2.  Data storage is configured using one of the concrete implementations
    of Pyslet's own data access layer API.  No SQL necessary in your
    code, minimising the risk of SQL injection vulnerabilities!

3.  Session handling: the base class handles the setting of a session
    cookie and an initial set of redirects to ensure that cookies are
    being supported properly by the browser.  If session handling is
    broken a fail page method is called.  The session logic contains
    special measures to prevent common session-related attacks (such as
    session fixation, hijacking and cross-site request forgery) and the
    redirection sequence is designed to overcome limitaions imposed by
    broswer restrictions on third party cookies or P3P-related policy
    issues by providing a user-actionable flow, opening your tool in a
    new window if necessary.  End user messages are customisable. 

4.  Launch authorisation is handled automatically, launch requests are
    checked using OAuth for validity and rejected automatically if
    invalid. Successful requests are automatically redirected to a
    resource-specific page.

5.  Each resource is given its own path in your application of the form
    /<script.wsgi>/resource/<id>/ allowing you to spread your tool
    application across multiple pages if necessary. A special method,
    :meth:`ToolProviderApp.load_visit`, is provided to extract the
    resource ID from the URL path and load the corresponding entity from
    the data store.  This method also loads the related entities for the
    the context, user and visit entities from the session according to
    the parameters passed in the original launch.

6.  An overridable tool permission model is provided with a default
    implementation that provides read/write/configure permissions to
    Instructors (and sub-roles) and read permissions to Learners (and
    sub-roles).  This enables your tool to simply test a permission bit
    at runtime to determine whether or not to display certain page
    elements.
    
7.  Tools can be launched multiple times in the same browser session.
    Authorisations remain active allowing the user to interact with your
    tool in separate tabs or even in multiple iframes on the same page.
    Authorisations are automatically expired if a conflicting launch
    request is received.  In other words, if a browser session receives
    a new launch from the same consumer but for a different user then
    all the previous user's activity is automatically logged out.

8.  Consumer secrets can be encrypted when persisted in the data store
    using an application key.  By default the application key is
    configured in the settings file.  (The PyCrypto module is required
    for encryption.)
 
The :class:`ToolConsumer` and :class:`ToolProvider` classes are largely
for internal use.  You may want to use them if you are integrating the
basic LTI functionality into a different web framework, they contain
utility methods for reading information from the data store.  You would
use the :meth:`ToolProvider.launch` method in your application when the
user POSTs to your launch endpoint to check that the LTI launch has been
authorised.


The Data Model
--------------

Implementing LTI requires some data storage to persist information
between HTTP requests.  This module is written using Pyslet's own data
access layer, based on the concepts of OData.  For more information see 
:ref:`odatav2`.

A sample metadata file describing the required elements of the model is
available as part of Pyslet itself.  The entity sets (cf SQL Tables) it
describes are as follows:

AppKeys
    This entity set is used to store information about encryption keys
    used to encrypt the consumer secrets in the data store.  For more
    information see :class:`pyslet.wsgi.WSGIDataApp`

Silos
    This entity set is the root of the information space for each tool.
    LTI tools tend to be multi-tenanted, that is, the same tool
    application can be used by multiple consumers with complete
    isolation between each consumer's data.  The Silo provides this
    level of protection.  Normally, each Silo will link to a single
    consumer but there may be cases where two or more consumers should
    share some data, in these cases a single Silo may link to multiple
    consumers.
    
Consumers
    This entity set contains information about the tool consumers.  Each
    consumer is identified by a consumer key and access is protected
    using a consumer secret (which can be stored in an encrypted form in
    the data store).

Nonces
    LTI tools are launched from the consumer using OAuth.  The protocol
    requires the use of a nonce (number used once only) to prevent the
    launch request being 'replayed' by an unauthorised person.  This
    entity set is used to record which nonces have been used and when.

Resources
    The primary launch concept in LTI is the resource.  Every launch must
    have a resource_link_id which identifies the specific 'place' or
    'page' in which the tool has been placed.

Contexts
    LTI defines a context as an optional course or group-like
    organisation that provides context for a launch request.  The
    context provides another potential scope for sharing data across
    launches.

Users
    An LTI launch is typically identifed with a specific user of the
    Tool Consumer (though this isn't required).  Information about the
    users is recorded in the data store so that they can be associated
    with any data generated by the tool using simple extensions to the
    data model.

Visits
    Each time someone launches your tool a visit entity is created with
    information about the resource, the context and the user.

Sessions
    Used to store information about the browser session, see
    :class:`pyslet.wsgi.SessionApp` for details.  The basic session
    entity is extended to link to the visits that are active (i.e.,
    currently authorised) for this session. 

These entities are related using navigation properties enabling you to
determine, for example, which Consumer a Resource belongs to, which
Visits are active in a Session, and so on.    

You can extend the core model by adding additional data properties
(which should be nullable) or by adding optional navigation properties.
For example, you might create an entity set to store information created
by users of the tool and add a navigation property from the User entity
to your new entity to indicate ownership.  The sample Noticeboard
application uses this technique and can be used as a guide.


Hello LTI
~~~~~~~~~

Writing your first LTI tool is easy::

    from optparse import OptionParser
    import pyslet.imsbltiv1p0 as lti

    if __name__ == '__main__':
        parser = OptionParser()
        lti.ToolProviderApp.add_options(parser)
        (options, args) = parser.parse_args()
        lti.ToolProviderApp.setup(options, args)
        app = lti.ToolProviderApp()
        app.run_server()

Save this script as mytool.py and run it from the command line like
this::

    $ python mytool.py --help

Built-in to the WSGI base classes is support for running your tool from
the command line during development.  The script above just uses
Python's builtin options parsing feature to set up the tool class before
creating an instance (the WSGI callable object) and running a basic WSGI
server using Python's builtin wsgiref module.

Try running your application with the -m and --create_silo options to
use an in-memory SQLite data store and a default consumer.

    $ python mytool.py -m

The script may print a warning message to the console warning you that
the in-memory database does not support multiple connections, it then
just sits waiting for connections on the default port, 8080.  The
default consumer has key '12345' and secret 'secret' (these can be
changed using a configuration file!).  The launch URL for your running
tool is::

    http://localhost:8080/launch

If you try it in the IMS test consumer at:
http://www.imsglobal.org/developers/LTI/test/v1p1/lms.php you should
get something that looks a bit like this:

.. image:: /images/weeklyblog.png

For a more complete example see the `NoticeBoard Sample LTI Tool`.


Reference
---------

..	autoclass:: ToolProviderApp
	:members:
	:show-inheritance:

..	autoclass:: ToolProviderContext
	:members:
	:show-inheritance:

..	autoclass:: ToolConsumer
	:members:
	:show-inheritance:

..	autoclass:: ToolProvider
	:members:
	:show-inheritance:


Metadata
~~~~~~~~

..  autofunction:: load_metadata


Constants and Data
~~~~~~~~~~~~~~~~~~

..  autodata:: LTI_VERSION

..  autodata:: LTI_MESSAGE_TYPE

..  autodata:: SYSROLE_HANDLES

..  autodata:: INSTROLE_HANDLES

..  autodata:: ROLE_HANDLES

..  autofunction:: split_role

..  autofunction:: is_subrole

..  autodata:: CONTEXT_TYPE_HANDLES


Exceptions
~~~~~~~~~~

..	autoclass:: LTIError
	:show-inheritance:


..	autoclass:: LTIAuthenticationError
	:show-inheritance:


..	autoclass:: LTIProtocolError
	:show-inheritance:


Legacy Classes
~~~~~~~~~~~~~~

Earlier Pyslet versions contained a very rudimentary memory based LTI
tool provider implementation based on the older oauth module. These
classes have been superceded but the main BLTIToolProvider class has
been refactored as a derived class of :class:`ToolProvider` using a
SQLite ':memory:' database (instead of a Python dictionary) and the
existing method signatures should continue to work as before.

The only change you'll need to make is to install the newer oauthlib_.
Bear in mind that these classes are now deprecated and you should
refactor to use the base :class:`ToolProvider` class directly for future
compatibility.  Please raise an issue on GitHub if you anticipate
problems.

..	autoclass:: BLTIToolProvider
	:members:
	:show-inheritance:
