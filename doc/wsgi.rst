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
    particular runtime environment.  For example, you might want to set
    paths to directories for storing :attr:`WSGIApp.private_files` and
    reading :attr:`WSGIApp.static_files` and so on.
     
3.  Configure the class by calling the :meth:`WSGIApp.setup`
    *class* method.

4.  Create an instance of the class

5.  Start handling requests!

Here's an example::

    #
    #   Runtime configuration directives
    #
    
    #: directory for private data
    PRIVATE_FILES = '/var/www/data'
    
    #: directory for static HTML, images, CSS etc.
    STATIC_FILES = '/var/www/html'
    
    #   Step 1: define the WSGIApp sub-class
    class MyApp(WSGIApp):
        """Your class definitions here"""
        pass
    
    #   Step 2: set class attributes to configured values    
    MyApp.private_files = PRIVATE_FILES
    MyApp.status_files = STATIC_FILES
    
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

This simple file is available in the samples directory.  You can invoke
your script from the command line, --help can be used to look at what
options are available::

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
    
You can then start a simple interactive server on port 8081 and hit
it from your web browser.  Your session might look like this::
    
    $ python samples/wsgi_basic.py -ivvp8081
    INFO:pyslet.wsgi:Starting MyApp server on port 8081
    cmd: INFO:pyslet.wsgi:HTTP server on port 8081 running
    1.0.0.127.in-addr.arpa - - [11/Dec/2014 23:49:54] "GET / HTTP/1.1" 200 78

    cmd: stop

Typing 'stop' at the cmd prompt in interactive mode exits the server. 
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

 
Reference
---------

..	autoclass:: WSGIContext
	:members:
	:show-inheritance:


..	autoclass:: WSGIApp
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



