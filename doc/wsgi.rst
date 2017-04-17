WSGI Utilities
==============

.. py:module:: pyslet.wsgi

This module defines special classes and functions to make it easier to
write applications based on the WSGI_ specification.

..  _WSGI: https://www.python.org/dev/peps/pep-0333/


Overview
--------

WSGI applications are simple callable objects that take two arguments::

    result = application(environ, start_response)
    
In these utility classes, the arguments are encapsulated into a special
context object based on :class:`WSGIContext`.  The context object allows
you to get and set information specific to handling a single request, it
also contains utility methods that are useful for extracting information
from the URL, headers and request body and, likewise, methods that are
useful for setting the response status and headers.  Even in
multi-threaded servers, each context instance is used by a single thread.

The application callable itself is modeled by an *instance* of the class
:class:`WSGIApp`.  The instance may be called by multiple threads
simultaneously so any state stored in the application is shared across
all contexts and threads.

Many of the app class' methods take an abbreviated form of the WSGI
callable signature::

    result = wsgi_app.page_method(context)

In this pattern, wsgi_app is a :class:`WSGIApp` instance and page_method
is the name of some response generating method defined in it.

In practice, you'll derive a class from WSGIApp for your application
and, possibly, derive a class from WSGIContext too.  In the latter case,
you must set the class attribute :attr:`WSGIApp.ContextClass` to your
custom context class before creating your application instance.

The lifecycle of a script that runs your application can be summed up:

1.  Define your WSGIApp sub-class

2.  Set the values of any class attributes that are specific to a
    particular runtime environment.  For example, you'll probably want
    to set the path to the :attr:`WSGIApp.settings_file` where you can
    provide other runtime configuration options.
     
3.  Configure the class by calling the :meth:`WSGIApp.setup`
    *class* method.

4.  Create an instance of the class

5.  Start handling requests!

Here's an example::

    #
    #   Runtime configuration directives
    #
    
    #: path to settings file
    SETTINGS_FILE = '/var/www/wsgi/data/settings.json'
    
    #   Step 1: define the WSGIApp sub-class
    class MyApp(WSGIApp):
        """Your class definitions here"""

        #   Step 2: set class attributes to configured values    
        settings_file = SETTINGS_FILE
        
    #   Step 3: call setup to configure the application
    MyApp.setup()
    
    #   Step 4: create an instance
    application = MyApp()
    
    #   Step 5: start handling requests, your framework may differ!
    application.run_server()

In the last step we call a run_server method which uses Python's builtin
HTTP/WSGI server implementation.  This is suitable for testing an
application but in practice you'll probably want to deploy your
application with some other WSGI driver, such as Apache and modwsgi_

..  _modwsgi: https://code.google.com/p/modwsgi/


Testing
~~~~~~~

The core WSGIApp class has a number of methods that make it easy to test
your application from the command line, using Python's built-in support
for WSGI.  In the example above you saw how the run_server method can be
used.

There is also a facility to launch an application from the command line
with options to override several settings.  You can invoke this
behaviour simply be calling the main class method::

    from pyslet.wsgi import WSGIApp
    
    class MyApp(WSGIApp):
        """Your class definitions here"""
        pass

    if __name__ == "__main__":
        MyApp.main()

This simple example is available in the samples directory.  You can
invoke your script from the command line, --help can be used to look at
what options are available::

    $ python samples/wsgi_basic.py --help
    Usage: wsgi_basic.py [options]

    Options:
      -h, --help            show this help message and exit
      -v                    increase verbosity of output up to 3x
      -p PORT, --port=PORT  port on which to listen
      -i, --interactive     Enable interactive prompt after starting server
      --static=STATIC       Path to the directory of static files
      --private=PRIVATE     Path to the directory for data files
      --settings=SETTINGS   Path to the settings file
    
You could start a simple interactive server on port 8081 and hit
it from your web browser with the following command::
    
    $ python samples/wsgi_basic.py -ivvp8081
    INFO:pyslet.wsgi:Starting MyApp server on port 8081
    cmd: INFO:pyslet.wsgi:HTTP server on port 8081 running
    1.0.0.127.in-addr.arpa - - [11/Dec/2014 23:49:54] "GET / HTTP/1.1" 200 78
    cmd: stop

Typing 'stop' at the cmd prompt in interactive mode exits the server. 
Anything other than stop is evaluated as a python expression in the
context of a method on your application object which allows you to
interrogate you application while it is running::

    cmd: self
    <__main__.MyApp object at 0x1004c2b50>
    cmd: self.settings
    {'WSGIApp': {'interactive': True, 'static': None, 'port': 8081, 'private': None, 'level': 20}}

If you include -vvv on the launch you'll get full debugging information
including all WSGI environment information and all application output
logged to the terminal.


Handling Pages
--------------

To handle a page you need to register your page with the request
dispatcher.  You typically do this during
:meth:`WSGIApp.init_dispatcher` by calling :meth:`WSGIApp.set_method`
and passing a pattern to match in the path and a *bound* method::

    class MyApp(WSGIApp):

        def init_dispatcher(self):
            super(MyApp, self).init_dispatcher()
            self.set_method("/*", self.home)
        
        def home(self, context):
            data = "<html><head><title>Hello</title></head>" \
                "<body><p>Hello world!</p></body></html>"
            context.set_status(200)
            return self.html_response(context, data)

In this example we registered our simple 'home' method as the handler
for all paths.  The star is used instead of a complete path component
and represents a wildcard that matches any value. When used at the end
of a path it matches any (possibly empty) sequence of path components.


Data Storage
------------

Most applications will need to read from or write data to some type of
data store.  Pyslet exposes its own data access layer to web
applications, for details of the data access layer see the OData section.

To associate a data container with your application simply derive your
application from :class:`WSGIDataApp` instead of the more basic WSGIApp.

You'll need to supply a metadata XML document describing your data
schema and information about the data source in the settings file.

The minimum required to get an application working with a sqlite3 database
would be to a directory with the following layout::

    settings.json
    metadata.xml
    data/

The settings.json file would contain::

    {
    "WSGIApp": {
        "private": "data"
        },
    "WSGIDataApp": {
        "metadata": "metadata.xml"
        }
    }
    
If the settings file is in samples/wsgi_data your source might look this::

    from pyslet.wsgi import WSGIDataApp

    class MyApp(WSGIDataApp):

        settings_file = 'samples/wsgi_data/settings.json'

        # method definitions as before
        
    if __name__ == "__main__":
        MyApp.main()


To create your database the first time you will either want to run a
custom SQL script or get Pyslet to create the tables for you.  With the
script above both options can be achieved with the command line::
    
    $ python samples/wsgi_data.py --create_tables -ivvp8081

This command starts the server as before but instructs it to create the
tables in the database before running.  Obviously you can only specify
this option the first time!

Alternatively you might want to customise the table creation script,
in which case you can create a pro-forma to edit using the --sqlout
option instead::

    $ python samples/wsgi_data.py --sqlout > wsgi_data.sql


Session Management
------------------

The :class:`WSGIDataApp` is further extended by :class:`SessionApp` to
cover the common use case of needing to track information across
multiple requests from the same user session.

The approach taken requires cookies to be enabled in the user's browser.
See `Problems with Cookies`_ below for details.

A decorator, :func:`session_decorator` is defined to make it easy to
write (page) methods that depend on the existence of an active session. 
The session initiation logic is a little convoluted and is likely to
involve at least one redirect when a protected page is first requested,
but this all happens transparently to your application. You may want to
look at overriding the :meth:`ctest_page` and :meth:`cfail_page` methods
to provide more user-friendly messages in cases where cookies are
blocked.

CSRF
~~~~

Hand-in-hand with session management is defence against cross-site
request forgery (CSRF) attacks.  Relying purely on a session cookie to
identify a user is problematic because a third party site could cause
the user's browser to submit requests to your application on their
behalf.  The browser will send the session cookie even if the request
originated outside one of your application's pages.

POST requests that affect the state of the server or carry out some
other action requiring authorisation must be protected.  Requests that
simply return information (i.e., GET requests) are usually safe, even if
the response contains confidential information, as the browser prevents
the third party site from actually reading the HTML. Be careful when
returning data other than HTML though, for example, data that could be
parsed as valid JavaScript will need additional protection.  The
importance of using HTTP request methods appropriately cannot be
understated!

The most common pattern for preventing this type of fraud is to use a
special token in POST requests that can't be guessed by the third party
and isn't exposed outside the page from which the POSTed form is
supposed to originate.  If you decorate a page that is the target of a
POST request (the page that performs the action) with the session
decorator then the request will fail if a CSRF token is not included in
the request.  The token can be read from the session object and will
need to be inserted into any forms in your application.  You shouldn't
expose your CRSF token in the URL as that makes it vulnerable to being
discovered, so don't add it to forms that use the GET action.

Here's a simple example method that shows the use of the session
decorator::

    @session_decorator
    def home(self, context):
        page = """<html><head><title>Session Page</title></head><body>
            <h1>Session Page</h1>
            %s
            </body></html>"""
        with self.container['Sessions'].open() as collection:
            try:
                entity = collection[context.session.sid]
                user_name = entity['UserName'].value
            except KeyError:
                user_name = None
        if user_name:
            noform = """<p>Welcome: %s</p>"""
            page = page % (noform % xml.EscapeCharData(user_name))
        else:
            form = """<form method="POST" action="setname">
                <p>Please enter your name: <input type="text" name="name"/>
                    <input type="hidden" name=%s value=%s />
                    <input type="submit" value="Set"/></p>
                </form>"""
            page = page % (
                form % (xml.EscapeCharData(self.csrf_token, True),
                        xml.EscapeCharData(context.session.sid, True)))
        context.set_status(200)
        return self.html_response(context, page)

We've added a simple database table to store the session data with the
following entity::

    <EntityType Name="Session">
        <Key>
            <PropertyRef Name="SessionID"/>
        </Key>
        <Property Name="SessionID" Type="Edm.String"
            MaxLength="64" Nullable="false"/>
        <Property Name="UserName" Type="Edm.String"
            Nullable="true" MaxLength="256" Unicode="true"/>
    </EntityType>

Our database must also contain a small table used for key management,
see below for information about encryption.
 
Our method reads the value of this property from the database and prints
a welcome message if it is set.  If not, it prints a form allowing you
to enter your name.  Notice that we must include a hidden field
containing the CSRF token.  The name of the token parameter is given in
:attr:`SessionApp.csrf_token` and the value is read from the session
object passed in the accompanying cookie - the browser should prevent
third parties from reading the cookie's value.

The action method that processes the form looks like this::

    @session_decorator
    def setname(self, context):
        user_name = context.get_form_string('name')
        if user_name:
            with self.container['Sessions'].open() as collection:
                try:
                    entity = collection[context.session.sid]
                    entity['UserName'].set_from_value(user_name)
                    collection.update_entity(entity)
                except KeyError:
                    entity = collection.new_entity()
                    entity['SessionID'].set_from_value(context.session.sid)
                    entity['UserName'].set_from_value(user_name)
                    collection.insert_entity(entity)
        return self.redirect_page(context, context.get_app_root())

A sample application containing this code is provided and can again be
run from the command line::

    $ python samples/wsgi/wsgi_session.py --create_tables -ivvp8081


Problems with Cookies
~~~~~~~~~~~~~~~~~~~~~

There has been significant uncertainty over the use of cookies with some
browsers blocking them in certain situations and some users blocking
them entirely.  In particular, the `E-Privacy Directive`_ in the
European Union has led to a spate of scrolling consent banners and
pop-ups on website landing pages.

It is worth bearing in mind that use of cookies, as opposed to
URL-based solutions or cacheable basic basic auth credentials, is
currently considered *more* secure for passing session identifiers. 
When designing your application you need to balance the privacy rights
of your users with the need to keep their information safe and secure.
Indeed, the main provisions of the directive are about providing
security of services.  As a result, it is generally accepted that the
use of cookies for tracking sessions is essential and does not require
any special consent from the user.

By extending :class:`WSGIDataApp` this implementation always
persists session data on the server.  This gets around most of the
perceived issues with the directive and cookies but does not absolve
you and your application of the need to obtain consent from a more
general data protection perspective!

Perhaps more onerous, but less discussed, is the obligation to
remove 'traffic data', sometimes referred to as metadata, about the
transmission of a communication.  For this reason, we don't store the
originating IP address of the session even though doing so might
actually increase security.  As always, it's a balance.
    
..  _`E-Privacy Directive`:
    http://en.wikipedia.org/wiki/Directive_on_Privacy_and_Electronic_Communications#Cookies

Finally, by relying on cookies we will sometimes fall foul of browser
attempts to automate the privacy preferences of their users.  The most
common scenario is when our application is opened in a frame within
another application.  In this case, some browsers will apply a much
stricter policy on blocking cookies.  For example, Microsoft's Internet
Explorer (from version 6) requires the implementation of the P3P_
standard for communicating privacy information.  Although some sites
have chosen to fake a policy to trick the browser into accepting their
cookies this has resulted in legal action so is not to be recommended.

See: http://msdn.microsoft.com/en-us/library/ms537343(v=VS.85).aspx

..  _P3P: http://www.w3.org/P3P/

To maximise the chances of being able to create a session this class
uses automatic redirection to test for cookie storage and a
mechanism for transferring the session to a new window if it detects
that cookies are blocked.

For a more detailed explanation of how this is achieved see my blog
post `Putting Cookies in the Frame`_

In many cases, once the application has been opened in a new window and
the test cookie has been set successfully, future framed calls to the
application *will* receive cookies and the user experience will be much
smoother.
 
..  _`Putting Cookies in the Frame`:
    http://swl10.blogspot.co.uk/2014/11/lti-tools-putting-cookies-in-frame.html


Encrypting Data
---------------

Sometimes you'll want to encrypt sensitive data stored in a data store
to prevent, say, a database administrator from being able to read it. 
This module provides a utility class called :class:`AppCipher` which is
designed to make this easier.

An AppCipher is initialised with a key.  There are various strategies
for storing keys for application use, in the simplest case you might
read the key from a configuration file that is only available on the
application server and not to the database administrator, say.

To assist with key management AppCipher will store old keys (suitably
encrypted) in the data store using an entity with the following
properties::

    <EntityType Name="AppKey">
        <Key>
            <PropertyRef Name="KeyNum"/>
        </Key>
        <Property Name="KeyNum" Nullable="false" Type="Edm.Int32"/>
        <Property Name="KeyString" Nullable="false"
            Type="Edm.String" MaxLength="256" Unicode="false"/>
    </EntityType>

SessionApp's require an AppCipher to be specified in the settings and an
AppKeys entity set in the data store to enable signing of the session
cookie (to guard against cookie tampering).

The default implementation of AppCipher does not use any encryption (it
merely obfuscates the input using base64 encoding) so to be useful
you'll need to use a class derived from AppCipher.  If you have the
Pycrypto_ module installed you can use the :class:`AESAppCipher` class
to use the AES algorithm to encrypt the data.

..  _Pycrypto: https://pypi.python.org/pypi/pycrypto

For details, see the reference section below.



 
Reference
---------

..	autoclass:: WSGIContext
	:members:
	:show-inheritance:

..	autoclass:: WSGIApp
	:members:
	:show-inheritance:

..	autoclass:: WSGIDataApp
	:members:
	:show-inheritance:

..  autofunction:: session_decorator

..	autoclass:: SessionContext
	:members:
	:show-inheritance:

..	autoclass:: SessionApp
	:members:
	:show-inheritance:

..	autoclass:: AppCipher
	:members:
	:show-inheritance:

..	autoclass:: AESAppCipher
	:members:
	:show-inheritance:



Utility Functions
~~~~~~~~~~~~~~~~~

..	autofunction::	generate_key

..	autofunction::	key60


Exceptions
~~~~~~~~~~

If thrown while handling a WSGI request these errors will be caught by
the underlying handlers and generate calls to to 
:meth:`WSGIApp.error_page` with an appropriate 4xx response code.

..	autoclass:: BadRequest
	:show-inheritance:

..	autoclass:: PageNotAuthorized
	:show-inheritance:

..	autoclass:: PageNotFound
	:show-inheritance:

..	autoclass:: MethodNotAllowed
	:show-inheritance:


Other sub-classes of Exception are caught and generate 500 errors:

..	autoclass:: SessionError
	:show-inheritance:



