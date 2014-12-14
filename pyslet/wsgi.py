#! /usr/bin/env python
"""Utilities for writing applications based on wsgi"""

import cgi
import io
import json
import mimetypes
import optparse
import os
import os.path
import random
import string
import StringIO
import sys
import threading
import time
import urllib
import urlparse

from hashlib import sha256
from wsgiref.simple_server import make_server

import pyslet.http.cookie as cookie
import pyslet.http.messages as messages
import pyslet.http.params as params
import pyslet.iso8601 as iso
import pyslet.odata2.core as core
import pyslet.odata2.csdl as edm
import pyslet.odata2.metadata as edmx
import pyslet.xml20081126.structures as xml

from pyslet.rfc2396 import URI

import logging
logging = logging.getLogger('pyslet.wsgi')


class BadRequest(Exception):
    """An exception that will generate a 400 response code"""
    pass


class PageNotAuthorized(BadRequest):
    """An exception that will generate a 403 response code"""
    pass


class PageNotFound(BadRequest):
    """An exception that will generate a 404 response code"""
    pass


class MethodNotAllowed(BadRequest):
    """An exception that will generate a 405 response code"""
    pass


class SessionError(RuntimeError):
    """Unexpected session handling error"""
    pass


def generate_key(key_length=128):
    """Generates a new key

    key_length
        The minimum key length in bits.  Defaults to 128.

    The key is returned as a sequence of 16 bit hexadecimal
    strings separated by '.' to make them easier to read and
    transcribe into other systems."""
    key = []
    if key_length < 1:
        raise ValueError("wsgi.generate_key(%i)" % key_length)
    nfours = (key_length + 15) // 16
    try:
        rbytes = os.urandom(nfours * 2)
        for i in xrange(nfours):
            four = "%02X%02X" % (
                ord(rbytes[2 * i]), ord(rbytes[2 * i + 1]))
            key.append(four)
    except NotImplementedError:
        logging.warn("urandom required for secure key generation")
        for i in xrange(nfours):
            four = []
            for j in xrange(4):
                four.append(random.choice('0123456789ABCDEF'))
            key.append(string.join(four, ''))
    return string.join(key, '.')


def key60(src):
    """Generates a non-negative 60-bit long from a source string.

    src
        A binary string.

    The idea behind this function is to create an (almost) unique
    integer from a given string.  The integer can then be used as the
    key field of an associated entity without having to create foreign
    keys that are long strings.  There is of course a small chance that
    two source strings will result in the same integer.

    The integer is calculated by truncating the SHA256 hexdigest to 15
    characters (60-bits) and then converting to long.  Future versions
    of Python promise improvements here, which would allow us to squeeze
    an extra 3 bits using int.from_bytes but alas, not in Python 2.x"""
    return long(sha256(src).hexdigest()[0:15], 16)


class WSGIContext(object):
    """A class used for managing WSGI calls

    environ
        The WSGI environment

    start_response
        The WSGI call-back

    This class acts as a holding place for information specific to each
    request being handled by a WSGI-based application.  In some
    frameworks this might be called the request object but we already
    have requests modelled in the http package and, anyway, this holds
    information about the WSGI environment and the response too."""

    #: The maximum amount of content we'll read into memory (64K)
    MAX_CONTENT = 64*1024

    def __init__(self, environ, start_response):
        #: the WSGI environ
        self.environ = environ
        #: the WSGI start_response callable
        self.start_response_method = start_response
        #: the response status code (an integer), see :meth:`set_status`
        self.status = None
        #: the response status message (a string), see :meth:`set_status`
        self.status_message = None
        #: a *list* of (name, value) tuples containing the headers to
        #: return to the client.  name and value must be strings
        self.headers = []
        self._query = None
        self._content = None
        self._form = None
        self._cookies = None

    def set_status(self, code):
        """Sets the status of the response

        code
            An HTTP *integer* response code.

        This method sets the :attr:`status_message` automatically from
        the code."""
        self.status = code
        self.status_message = messages.Response.REASON.get(code, "Unknown")

    def add_header(self, name, value):
        """Adds a header to the response

        name
            The name of the header (a string)

        value
            The value of the header (a string)"""
        self.headers.append((name, value))

    def start_response(self):
        """Calls the WSGI start_response method

        If the :attr:`status` has not been set a 500 response is
        generated.  The status string is created automatically from
        :attr:`status` and :attr:`status_message` and the headers are
        set from :attr:`headers`.

        The return value is the return value of the WSGI start_response
        call, an obsolete callable that older applications use to write
        the body data of the response.

        If you want to use the exc_info mechanism you must call
        start_response yourself directly using the value of
        :attr:`start_response_method`"""
        if self.status is None:
            self.status = 500
            self.status_message = messages.Response.REASON.get(500,
                                                               "No status")
        return self.start_response_method(
            "%i %s" % (self.status, self.status_message), self.headers)

    def get_app_root(self):
        """Returns the root of this application

        The result is a :class:`pyslet.rfc2396.URI` instance, It is
        calculated from the environment in the same way as
        :meth:`get_url` but only examines the SCRIPT_NAME portion of the
        path.

        It always ends in a trailing slash.  So if you have a script
        bound to /script/myscript.py running over http on
        www.example.com then you will get::

            http://www.example.com/script/myscript.py/

        This allows you to generate absolute URLs by resolving them relative
        to the computed application root, e.g.::

            URI.from_octets('images/counter.png').resolve(
                context.get_app_root())

        would return::

            http://www.example.com/script/myscript.py/images/counter.png

        for the above example.  This is preferable to using absolute
        paths which would strip away the SCRIPT_NAME prefix when used."""
        url = [self.environ['wsgi.url_scheme'], '://']
        url.append(self._get_authority())
        script = urllib.quote(self.environ.get('SCRIPT_NAME', ''))
        url.append(script)
        # we always add the slash, that's our root URL
        if not script or script[-1] != '/':
            url.append('/')
        return URI.from_octets(string.join(url, ''))

    def get_url(self):
        """Returns the URL used in the request

        The result is a :class:`pyslet.rfc2396.URI` instance, It is
        calculated from the environment using the algorithm described in
        URL Reconstruction section of the WSGI specification.

        Unlike the result of :meth:`get_app_root` it *doesn't*
        necessarily end with a trailing slash.  So if you have a script
        bound to /script/myscript.py running over http on
        www.example.com then you may get::

            http://www.example.com/script/myscript.py

        A good pattern to adopt when faced with a missing trailing slash
        on a URL that is intended to behave as a 'directory' is to add
        the slash to the URL and use xml:base (for XML responses) or
        HTML's <base> tag to set the root for relative links.  The
        alternative is to issue an explicit redirect but this requires
        another request from the client.

        This causes particular pain in OData services which frequently
        respond on the service script's URL without a slash but generate
        incorrect relative links to the contained feeds as a result."""
        url = [self.environ['wsgi.url_scheme'], '://']
        url.append(self._get_authority())
        url.append(urllib.quote(self.environ.get('SCRIPT_NAME', '')))
        url.append(urllib.quote(self.environ.get('PATH_INFO', '')))
        query = self.environ.get('QUERY_STRING', '')
        if query:
            url += ['?', query]
        return URI.from_octets(string.join(url, ''))

    def _get_authority(self):
        sflag = (self.environ['wsgi.url_scheme'] == 'https')
        if self.environ.get('HTTP_HOST'):
            return self.environ['HTTP_HOST']
        else:
            authority = self.environ['SERVER_NAME']
            port = self.environ['SERVER_PORT']
            if sflag:
                if port != '443':
                    return "%s:%s" % (authority, port)
            elif port != '80':
                return "%s:%s" % (authority, port)
            return authority

    def get_query(self):
        """Returns a dictionary of query parameters

        The dictionary maps parameter names onto strings.  In cases
        where multiple values have been supplied the values are comma
        separated, so a URL ending in ?option=Apple&option=Pear would
        result in the dictionary::

            {'option': 'Apple,Pear'}

        This method only computes the dictionary once, future calls
        return the same dictionary!

        Note that the dictionary does not contain any cookie values or
        form parameters."""
        if self._query is None:
            self._query = urlparse.parse_qs(
                self.environ.get('QUERY_STRING', ''))
            for n, v in self._query.items():
                self._query[n] = string.join(v, ',')
        return self._query

    def get_content(self):
        """Returns the content of the request as a string

        The content is read from the input, up to CONTENT_LENGTH bytes,
        and is returned as a string.  If the content exceeds
        :attr:`MAX_CONTENT` (default: 64K) then BadRequest is raised.

        This method can be called multiple times, the content is only
        actually read from the input the first time.  Subsequent calls
        return the same string.

        This call cannot be called on the same context as
        :meth:`get_form`, whichever is called first takes precedence.
        Calls to get_content after get_form return None."""
        if self._form is None and self._content is None:
            length = self.environ.get('CONTENT_LENGTH', '')
            if length.isdigit():
                length = int(length)
            else:
                length = 0
            if length <= self.MAX_CONTENT:
                input = self.environ['wsgi.input']
                f = StringIO.StringIO()
                while length:
                    part = input.read(length)
                    if not part:
                        break
                    f.write(part)
                    length -= len(part)
                self._content = f.getvalue()
            else:
                raise BadRequest("Too much data")
        return self._content

    def get_form(self):
        """Returns a FieldStorage object parsed from the content.

        The query string is excluded before the form is parsed as this
        only covers parameters submitted in the content of the request.
        To search the query string you will need to examine the
        dictionary returned by :meth:`get_query` too.

        This method can be called multiple times, the form is only
        actually read from the input the first time.  Subsequent calls
        return the same FieldStorage object.

        This call cannot be called on the same context as
        :meth:`get_content`, whichever is called first takes
        precedence.  Calls to get_form after get_content return None.

        Warning: get_form will only parse the form from the content if
        the request method was POST!"""
        if self._form is None and self._content is None:
            post_environ = self.environ.copy()
            post_environ['QUERY_STRING'] = ''
            self._form = cgi.FieldStorage(
                fp=post_environ['wsgi.input'], environ=post_environ,
                keep_blank_values=True)
        return self._form

    def get_form_string(self, name, max_length=0x10000):
        """Returns the value of a string parameter from the form.

        name
            The name of the parameter

        max_length (optional, defaults to 64KB)
            Due to an issue in the implementation of FieldStorage it
            isn't actually possible to definitively tell the difference
            between a file upload and an ordinary input field.  HTML5
            clarifies the situation to say that ordinary fields don't
            have a content type but FieldStorage assumes 'text/plain' in
            this case and sets the file and type attribute of the field
            anyway.

            To prevent obtuse clients sending large files disguised as
            ordinary form fields, tricking your application into loading
            them into memory, this method checks the size of any file
            attribute (if present) against max_length before returning
            the field's value.

        If the parameter is missing from the form then an empty string
        is returned."""
        form = self.get_form()
        if name in form:
            result = form[name]
            if isinstance(result, list):
                return string.join(map(lambda x: x.value, result), ',')
            else:
                if result.file:
                    # could be an ordinary field in multipart/form-data
                    # this is a bit rubbish
                    fpos = result.file.tell()
                    result.file.seek(0, io.SEEK_END)
                    fsize = result.file.tell()
                    result.file.seek(fpos)
                    if fsize > max_length:
                        raise BadRequest
                return result.value
        return ''

    def get_cookies(self):
        """Returns a dictionary of cookies from the request

        If no cookies were passed an empty dictionary is returned.

        For details of how multi-valued cookies are handled see:
        :meth:`pyslet.http.cookie.CookieParser.request_cookie_string`."""
        if self._cookies is None:
            cookie_values = self.environ.get('HTTP_COOKIE', None)
            if cookie_values is not None:
                p = cookie.CookieParser(cookie_values)
                self._cookies = p.require_cookie_string()
                for name in self._cookies:
                    value = self._cookies[name]
                    if isinstance(value, set):
                        # join the items into a single string
                        value = list(value)
                        value.sort()
                        self._cookies[name] = string.join(value, ',')
            else:
                self._cookies = {}
        return self._cookies


class DispatchNode(object):
    """An opaque class used for dispatching requests."""

    def __init__(self):
        self._handler = None
        self._wildcard = None
        self._nodes = {}


class WSGIApp(DispatchNode):
    """An object to help support WSGI-based applications.

    Instances are designed to be callable by the WSGI middle-ware, on
    creation each instance is assigned a random identifier which is used
    to provide comparison and hash implementations.  We go to this
    trouble so that derived classes can use techniques like the
    functools lru_cache decorator in future versions."""

    #: the context class to use for this application, must be (derived
    #: from) :class:`WSGIContext`
    ContextClass = WSGIContext

    #: The path to the directory for :attr:`static_files`.  Defaults to
    #: a directory called "static" in the current working directory.
    static_files = os.path.abspath("static")

    #: the directory used for storing private data, defaults to None for
    #: safety as the application can assume that this directory has been
    #: configured to allow data to be written by the application
    private_files = None

    settings_file = None
    """The path to the settings file.

    Defaults to "settings.json" in the current directory.

    The format of the settings file is a json dictionary.  The
    dictionary's keys are class names that define a scope for
    class-specific settings. The key 'WSGIApp' is reserved for settings
    defined by this class.  The defined settings are:

    level (None)
        If specified, used to set the root logging level, a value
        between 0 (NOTSET) and 50 (CRITICAL).  For more information see
        python's logging module.

    port (8080)
        The port number used by :meth:`run_server`

    interactive (False)
        Sets the behaviour of :meth:`run_server`, if specified the main
        thread prompts the user with a command line interface allowing
        you to interact with the running server.  When False, run_server
        will run forever and can only be killed by an application
        request that sets :attr:`stop` to True or by an external signal
        that kills the process."""

    #: the class settings loaded from :attr:`settings_file` by
    #: :meth:`setup`
    settings = None

    content_type = {
        'ico': params.MediaType('image', 'vnd.microsoft.icon'),
        }
    """The mime type mapping table.

    This table is used before falling back on Python's built-in
    guess_type function from the mimetypes module.  Add your own custom
    mappings here.

    It maps file extension (without the dot) on to
    :class:`~pyslet.http.params.MediaType` instances."""

    #: the maximum chunk size to read into memory when returning a
    #: (static) file.  Defaults to 64K.
    MAX_CHUNK = 0x10000

    #: the integer 'UNIX' time corresponding to 01 January 1970 00:00:00
    #: UTC the JavaScript time origin.  Most likely 0.
    js_origin = int(
        iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0, zDirection=0)
            ).get_unixtime() * 1000)

    #: a threading.RLock instance that can be used to lock the class
    #: when dealing with data that might be shared amongst threads.
    clslock = threading.RLock()

    _nextid = 1

    @classmethod
    def main(cls):
        """Runs the application

        Options are parsed from the command line and used to
        :meth:`setup` the class before an instance is created and
        launched with :meth:`run_server`."""
        parser = optparse.OptionParser()
        cls.add_options(parser)
        (options, args) = parser.parse_args()
        cls.setup(options=options, args=args)
        app = cls()
        app.run_server()

    @classmethod
    def add_options(cls, parser):
        """Defines command line options.

        parser
            An OptionParser instance, as defined by Python's built-in
            optparse module.

        The following options are added to *parser* by the base
        implementation:

        -v
            Sets the logging level to WARN, INFO or DEBUG depending on
            the number of times it is specified.  Overrides the 'level'
            setting in the settings file.

        -p, --port
            Overrides the value of the 'port' setting in the settings
            file.

        -i, --interactive
            Overrides the value of the 'interactive' setting in the
            settings file.

        --static
            Overrides the value of :attr:`static_files`.

        --private
            Overrides the value of :attr:`private_files`.

        --settings
            Sets the path to the :attr:`settings_file`.  Defaults to the
            file "settings.json" in the current working directory."
        """
        parser.add_option(
            "-v", action="count", dest="logging",
            default=0, help="increase verbosity of output up to 3x")
        parser.add_option(
            "-p", "--port", action="store", dest="port",
            default=None, help="port on which to listen")
        parser.add_option(
            "-i", "--interactive", dest="interactive", action="store_true",
            default=None,
            help="Enable interactive prompt after starting server")
        parser.add_option(
            "--static", dest="static", action="store", default=None,
            help="Path to the directory of static files")
        parser.add_option(
            "--private", dest="private", action="store", default=None,
            help="Path to the directory for data files")
        parser.add_option(
            "--settings", dest="settings", action="store", default=None,
            help="Path to the settings file")

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        """Perform one-time class setup

        options
            An optional object containing the command line options, such
            as an optparse.Values instance created by calling parse_args
            on the OptionParser instance passed to
            :meth:`add_options`.

        args
            An optional list of positional command-line arguments such
            as would be returned from parse_args after the options have
            been removed.

        All arguments are given as keyword arguments to enable use
        of super and diamond inheritance.

        The purpose of this method is to perform any actions required
        to setup the class prior to the creation of any instances.

        The default implementation loads the settings file and sets the
        value of :attr:`settings`.  If no settings file can be found
        then an empty dictionary is created and populated with any
        overrides parsed from options.

        Finally, the root logger is initialised based on the level
        setting."""
        import logging as logging_mod
        if options and options.static:
            cls.static_files = os.path.abspath(options.static)
        if options and options.private:
            cls.private_files = os.path.abspath(options.private)
        if options and options.settings:
            cls.settings_file = os.path.abspath(options.settings)
        if cls.settings_file is None:
            cls.settings_file = os.path.abspath("settings.json")
        cls.settings = {}
        if cls.settings_file:
            if os.path.isfile(cls.settings_file):
                with open(cls.settings_file, 'rb') as f:
                    cls.settings = json.load(f)
        settings = cls.settings.setdefault('WSGIApp', {})
        if options and options.logging is not None:
            settings['level'] = (
                logging_mod.ERROR, logging_mod.WARN, logging_mod.INFO,
                logging_mod.DEBUG)[min(options.logging, 3)]
        level = settings.setdefault('level', None)
        if level is not None:
            logging_mod.basicConfig(level=settings['level'])
        if options and options.port is not None:
            settings['port'] = int(options.port)
        else:
            settings.setdefault('port', 8080)
        if options and options.interactive is not None:
            settings['interactive'] = options.interactive
        else:
            settings.setdefault('interactive', False)

    def __init__(self):
        # keyword arguments end here, no more super after WSGIApp
        DispatchNode.__init__(self)
        #: flag: set to True to request :meth:`run_server` to exit
        self.stop = False
        with self.clslock:
            #: a unique ID for this instance
            self.id = WSGIApp._nextid
            WSGIApp._nextid += 1
        self.init_dispatcher()

    def __cmp__(self, other):
        if not isinstance(other, WSGIApp):
            raise TypeError
        # compare first by class name, then by instance ID
        result = cmp(self.__class__.__name__, other.__class__.__name__)
        if not result:
            result = cmp(self.id, other.id)
        return result

    def __hash__(self):
        return self.id

    def init_dispatcher(self):
        """Used to initialise the dispatcher.

        By default all requested paths generate a 404 error.  You
        register pages during :meth:`init_dispatcher` by calling
        :meth:`set_method`.  Derived classes should use super
        to pass the call to their parents."""
        pass

    def set_method(self, path, method):
        """Registers a bound method in the dispatcher

        path
            A path or path pattern

        method
            A bound method or callable with the basic signature::

                result = method(context)

        A star in the path is treated as a wildcard and matches a
        complete path segment.  A star at the end of the path (which
        must be after a '/') matches any sequence of path segments.  The
        matching sequence may be empty, in other words, "/images/*"
        matches "/images/".  In keeping with common practice a missing
        trailing slash is ignored when dispatching so "/images" will
        also be routed to a method registered with "/images/*" though if
        a separate registration is made for "/images" it will be matched
        in preference.

        Named matches always take precedence over wildcards so you can
        register "/images/*" and "/images/counter.png" and the latter
        path will be routed to its preferred handler.  Similarly you can
        register "/*/background.png" and "/home/background.png" but
        remember the '*' only matches a single path component!  There is
        no way to match background.png in any directory."""
        path = path.split('/')
        if not path:
            path = ['']
        node = self
        pleft = len(path)
        for p in path:
            pleft -= 1
            old_node = node
            if p == '*' and not pleft:
                # set a special flag, e.g., if /a/* is declared and we
                # have an unmatched /a we'll call that handler anyway
                old_node._wildcard = method
            node = old_node._nodes.get(p, None)
            if not node:
                node = DispatchNode()
                old_node._nodes[p] = node
        node._handler = method

    def call_wrapper(self, environ, start_response):
        """Alternative entry point for debugging

        Although instances are callable you may use this method instead
        as your application's entry point when debugging.

        This method will log the environ variables, the headers output
        by the application and all the data (in quoted-printable form)
        returned at DEBUG level.

        It also catches a common error, that of returning something
        other than a string for a header value or in the generated
        output.  These are logged at ERROR level and converted to
        strings before being passed to the calling framework."""
        # make a closure
        def wrap_response(status, response_headers, exc_info=None):
            if not isinstance(status, str):
                logging.error("Value for status line: %s", repr(status))
                status = str(status)
            logging.debug("*** START RESPONSE ***")
            logging.debug(status)
            new_headers = []
            for h, v in response_headers:
                if not isinstance(h, str):
                    logging.error("Header name: %s", repr(h))
                    h = str(h)
                if not isinstance(v, str):
                    logging.error("Header value: %s: %s", h, repr(v))
                    v = str(v)
                logging.debug("%s: %s", h, v)
                new_headers.append((h, v))
            return start_response(status, new_headers, exc_info)
        logging.debug("*** START REQUEST ***")
        for key in environ:
            logging.debug("%s: %s", key, str(environ[key]))
        blank = False
        for data in self(environ, wrap_response):
            if not blank:
                logging.debug("")
                blank = True
            if not isinstance(data, str):
                logging.error("Bad type for response data in %s\n%s",
                              str(environ['PATH_INFO']), repr(data))
                if isinstance(data, unicode):
                    data = data.encode('utf-8')
                else:
                    data = str(data)
            else:
                logging.debug(data.encode('quoted-printable'))
            yield data

    def __call__(self, environ, start_response):
        context = self.ContextClass(environ, start_response)
        try:
            path = context.environ['PATH_INFO'].split('/')
            if not path:
                # empty path
                path = ['']
            i = 0
            node = self
            wildcard = None
            stack = []
            while i < len(path):
                p = path[i]
                old_node = node
                wild_node = old_node._nodes.get('*', None)
                node = old_node._nodes.get(p, None)
                if node:
                    if wild_node:
                        # this is a fall-back node, push it
                        stack.append((i, wild_node, wildcard))
                elif wild_node:
                    node = wild_node
                elif wildcard:
                    # if there is an active wildcard, use it
                    break
                elif stack:
                    i, node, wildcard = stack.pop()
                else:
                    break
                if node._wildcard is not None:
                    wildcard = node._wildcard
                i += 1
            if node and node._handler is not None:
                return node._handler(context)
            if wildcard:
                return wildcard(context)
            # we didn't find a handler
            return self.error_page(context, 404)
        except MethodNotAllowed:
            return self.error_page(context, 405)
        except PageNotFound:
            return self.error_page(context, 404)
        except PageNotAuthorized:
            return self.error_page(context, 403)
        except BadRequest:
            return self.error_page(context, 400)
        except Exception as e:
            logging.exception(context.environ['PATH_INFO'])
            return self.internal_error(context, e)

    def static_page(self, context):
        """Returns a static page

        This method can be bound to any path using :meth:`set_method`
        and it will look in the :attr:`static_files` directory for that
        file.  For example, if static_files is "/var/www/html" and the
        PATH_INFO variable in the request is "/images/logo.png" then the
        path "/var/www/html/images/logo.png" will be returned.

        There are significant restrictions on the names of the path
        components.  Each component *must* match a basic label syntax
        (equivalent to the syntax of domain labels in host names) except
        the last component which must have a single '.' separating two
        valid labels.  This conservative syntax is designed to be safe
        for passing to file handling functions."""
        path = context.environ['PATH_INFO'].split('/')
        target_path = self.static_files
        if target_path is None:
            raise PageNotFound
        ext = ''
        pleft = len(path)
        for p in path:
            pleft -= 1
            if pleft:
                # ignore empty components
                if not p:
                    continue
                # this path component must be a directory we re-use the
                # ldb-label test from the cookie module to ensure we
                # have a very limited syntax.  Apologies if you wanted
                # fancy URLs.
                if not cookie.is_ldh_label(p):
                    raise PageNotFound
                target_path = os.path.join(target_path, p)
                if not os.path.isdir(target_path):
                    raise PageNotFound
            elif not p:
                # this is the directory form, e.g., /app/docs/ but we
                # don't support indexing, we're not Apache
                raise PageNotFound
            else:
                # last component must be a filename.ext form
                splitp = p.split('.')
                if (len(splitp) != 2 or
                        not cookie.is_ldh_label(splitp[0]) or
                        not cookie.is_ldh_label(splitp[1])):
                    raise PageNotFound
                filename = p
                ext = splitp[1]
                target_path = os.path.join(target_path, p)
        if not os.path.isfile(target_path):
            raise PageNotFound
        # Now the MIME mapping
        ctype = self.content_type.get(ext, None)
        if ctype is None:
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is not None:
                ctype = params.MediaType.from_str(ctype)
            if encoding is not None:
                context.add_header("Content-Encoding", encoding)
        if ctype is None:
            ctype = params.APPLICATION_OCTETSTREAM
        context.set_status(200)
        context.add_header("Content-Type", str(ctype))
        return self.file_response(context, target_path)

    def file_response(self, context, target_path):
        """Returns a file from the file system

        target_path
            The system file path of the file to be returned.

        The Content-Length header is set from the file size, the
        Last-Modified date is set from the file's st_mtime and the
        file's data is returned in chunks of :attr:`MAX_CHUNK` in the
        response.

        The status is *not* set and must have been set before calling
        this method."""
        finfo = os.stat(target_path)
        context.add_header("Content-Length", str(finfo.st_size))
        context.add_header("Last-Modified",
                           str(params.FullDate.FromUnixTime(finfo.st_mtime)))
        context.start_response()
        bleft = finfo.st_size
        with open(target_path) as f:
            while bleft:
                chunk_size = min(bleft, self.MAX_CHUNK)
                chunk = f.read(chunk_size)
                if not chunk:
                    # unexpected EOF while reading
                    raise RuntimeError("Unexpected EOF")
                bleft -= len(chunk)
                yield chunk

    def html_response(self, context, data):
        """Returns an HTML page

        data
            A string containing the HTML page data.  This may be a
            unicode or binary string.

        The Content-Type headers is set to text/html (with an explicit
        charset if data is unicode string).  The status is *not* set and
        must have been set before calling this method."""
        if isinstance(data, unicode):
            data = data.encode('utf-8')
            context.add_header("Content-Type", "text/html; charset=utf-8")
        else:
            context.add_header("Content-Type", "text/html")
        # catch the odd case where data is a subclass of str - still ok
        # but the default WSGI server uses this stronger test!
        if type(data) is not str:
            data = str(data)
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [data]

    def json_response(self, context, data):
        """Returns a JSON response

        data
            A string containing the JSON data.  This may be a unicode or
            binary string (encoded with utf-8).

        The Content-Type is set to "application/json".  The status is
        *not* set and must have been set before calling this method."""
        if isinstance(data, unicode):
            data = data.encode('utf-8')
        if type(data) is not str:
            data = str(data)
        context.add_header("Content-Type", "application/json")
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [data]

    def text_response(self, context, data):
        """Returns a plain text response

        data
            A string containing the text data.  This may be a unicode or
            binary string (encoded with US-ASCII).

        The Content-Type is set to "text/plain" (with an explicit
        charset if a unicode string is passed).  The status is *not* set
        and must have been set before calling this method.

        Warning: do not encode unicode strings before passing them to
        this method as data, if you do you risk problems with non-ASCII
        characters as the default charset for text/plain is US-ASCII and
        not UTF-8 or ISO8859-1 (latin-1)."""
        if isinstance(data, unicode):
            data = data.encode('utf-8')
            context.add_header("Content-Type", "text/plain; charset=utf-8")
        else:
            context.add_header("Content-Type", "text/plain")
        if type(data) is not str:
            data = str(data)
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [data]

    def redirect_page(self, context, location, code=303):
        """Returns a redirect response

        location
            A :class:`~pyslet.rfc2396.URI` instance or a string of
            octets.

        code (303)
            The redirect status code.  As a reminder the typical codes
            are 301 for a permanent redirect, a 302 for a temporary
            redirect and a 303 for a temporary redirect following a POST
            request.  This latter code is useful for implementing the
            widely adopted pattern of always redirecting the user after
            a successful POST request to prevent browsers prompting for
            re-submission and is therefore the default.

        This method takes care of setting the status, the Location
        header and generating a simple HTML redirection page response
        containing a clickable link to *location*."""
        data = """<html>
<head><title>Redirect</title></head>
<body>
    <p>Please <a href=%s>click here</a> if not redirected automatically</p>
</body></html>""" % xml.EscapeCharData7(str(location), True)
        context.add_header("Location", str(location))
        context.add_header("Content-Type", "text/html")
        context.add_header("Content-Length", str(len(data)))
        context.set_status(code)
        context.start_response()
        return [str(data)]

    def error_page(self, context, code=500, msg=None):
        """Generates an error response

        code (500)
            The status code to send.

        msg (None)
            An optional plain-text error message.  If not given then the
            status line is echoed in the body of the response."""
        context.set_status(code)
        if msg is None:
            msg = "%i %s" % (code, context.status_message)
            context.add_header("Content-Type", "text/plain")
        elif isinstance(msg, unicode):
            msg = msg.encode('utf-8')
            context.add_header("Content-Type", "text/plain; charset=utf-8")
        else:
            context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(msg)))
        context.start_response()
        return [str(msg)]

    def internal_error(self, context, err):
        context.set_status(500)
        data = "%i %s\r\n%s" % (context.status, context.status_message,
                                str(err))
        context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [str(data)]

    def _run_server_thread(self):
        """Starts the web server running"""
        port = self.settings['WSGIApp']['port']
        server = make_server('', port, self.call_wrapper)
        logging.info("HTTP server on port %i running", port)
        # Respond to requests until process is killed
        while not self.stop:
            server.handle_request()

    def run_server(self):
        t = threading.Thread(target=self._run_server_thread)
        t.setDaemon(True)
        t.start()
        logging.info("Starting %s server on port %s", self.__class__.__name__,
                     self.settings['WSGIApp']['port'])
        if self.settings['WSGIApp']['interactive']:
            # loop around getting commands
            while not self.stop:
                cmd = raw_input('cmd: ').lower()
                if cmd == 'stop':
                    self.stop = True
                elif cmd:
                    print "Unrecognized command: %s" % cmd
            sys.exit()
        else:
            t.join()


class Session(object):

    #: session expire after...
    SESSION_EXPIRY = 600

    #: name of session cookie
    COOKIE_SESSION = "sid"

    #: name of the test cookie
    COOKIE_TEST = "cok"

    #: the length of time to store the test cookie for
    COOKIE_TEST_AGE = 8640000    # 100 days

    @classmethod
    def from_context(cls, app, context):
        """Creates a session object from an application context

        The session id is read from the session cookie, if no cookie is
        found a new session is created and returned instead (and an
        appropriate cookie is added to the response headers)."""
        cookies = context.get_cookies()
        sid = cookies.get(Session.COOKIE_SESSION, '')
        if sid:
            entity = cls.load_entity(app, sid)
        else:
            entity = None
        if entity is None:
            with app.session_set.OpenCollection() as collection:
                # generate a new user_key
                user_key = generate_key()
                server_key = generate_key()
                entity = collection.new_entity()
                entity['UserKey'].set_from_value(user_key)
                entity['ServerKey'].set_from_value(server_key)
                entity['Expires'].set_from_value(
                    iso.TimePoint.FromUnixTime(
                        time.time() +
                        cls.SESSION_EXPIRY).WithZone(None))
                entity['Established'].set_from_value(False)
                if 'HTTP_USER_AGENT' in context.environ:
                    user_agent = context.environ['HTTP_USER_AGENT']
                    if len(user_agent) > 255:
                        user_agent = user_agent[0:255]
                    entity['UserAgent'].set_from_value(user_agent)
                collection.insert_entity(entity)
        session = cls(app, entity)
        if entity['UserKey'].value != sid:
            # set the cookie to keep the client up-to-date
            session.set_cookie(context)
        return session

    @classmethod
    def from_sid(cls, app, sid):
        """Creates a session object from a given session id

        No cookies are read or written by this method and if the session
        is not found None is returned."""
        if sid:
            entity = cls.load_entity(app, sid)
            if entity is not None:
                return cls(app, entity)
        else:
            return None

    @classmethod
    def load_entity(cls, app, sid):
        """Given a session id retrieves the session entity.

        The session id is matched against the UserKey field.  If no
        matching session is found, or the matching session has expired,
        None is returned."""
        with app.session_set.OpenCollection() as collection:
            # load the session
            now = iso.TimePoint.FromNowUTC().WithZone(None)
            param = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            param.set_from_value(sid)
            params = {'user_key': param}
            filter = core.CommonExpression.from_str(
                "UserKey eq :user_key", params)
            collection.set_filter(filter)
            slist = collection.values()
            collection.set_filter(None)
            if len(slist) > 1:
                # that's an internal error
                raise SessionError(
                    "Duplicate user_key in Sessions: %s" % sid)
            elif len(slist) == 1:
                entity = slist[0]
                if (not entity['Expires'] or
                        entity['Expires'].value < now):
                    # session has expired, remove it
                    del collection[entity.key()]
                    entity = None
                else:
                    # update the session expiry time
                    entity['Expires'].set_from_value(
                        iso.TimePoint.FromUnixTime(
                            time.time() +
                            cls.SESSION_EXPIRY).WithZone(None))
                    collection.update_entity(entity)
                return entity
            else:
                return None

    def __init__(self, app, entity):
        self.app = app
        self.sentity = entity
        self.expires = iso.TimePoint.FromUnixTime(
            time.time() + self.SESSION_EXPIRY)

    def absorb(self, new_session):
        """Merge a session into this one.

        new_session
            A session which was started by the same browser as us (in
            a mode where cookies were clocked) but now needs to be
            merged in."""
        # just delete new_session
        new_session.delete()

    def set_cookie(self, context):
        c = cookie.Section4Cookie(
            self.COOKIE_SESSION, self.sentity['UserKey'].value,
            path=str(context.get_app_root().abs_path), http_only=True)
        context.add_header('Set-Cookie', str(c))

    def get_user_key(self):
        return self.sentity['UserKey'].value

    def update_user_key(self, context):
        with self.app.session_set.OpenCollection() as collection:
            self.sentity['UserKey'].set_from_value(generate_key())
            collection.update_entity(self.sentity)
        self.set_cookie(context)

    def establish(self):
        # if this session is not yet established then establish it
        if not self.sentity['Established'].value:
            with self.app.session_set.OpenCollection() as collection:
                self.sentity['Established'].set_from_value(True)
                collection.update_entity(self.sentity)

    def is_established(self):
        return self.sentity['Established'].value

    def match_environ(self, context):
        user_agent = context.environ.get('HTTP_USER_AGENT', None)
        if user_agent and len(user_agent) > 255:
            user_agent = user_agent[0:255]
        if self.sentity['UserAgent'].value != user_agent:
            return False
        return True

    def delete(self):
        if self.sentity.exists:
            with self.app.session_set.OpenCollection() as collection:
                del collection[self.sentity.key()]

    @classmethod
    def delete_session(cls, session_set, user_key):
        with session_set.OpenCollection() as collection:
            param = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            param.set_from_value(user_key)
            params = {'user_key': param}
            filter = core.CommonExpression.from_str("UserKey eq :user_key",
                                                    params)
            collection.set_filter(filter)
            slist = collection.values()
            collection.set_filter(None)
            if len(slist):
                for sentity in slist:
                    del collection[sentity.key()]


def session_decorator(page_method):
    """Decorates a web method with session handling

    page_method
        An unbound method with signature: page_method(obj, context)
        which performs the WSGI protocol and returns the page
        generator."""

    def method_call(self, context):
        # There's a smarter way to do this but this is easier to read
        # and understand I think...
        return self.session_wrapper(context, lambda x: page_method(self, x))
        # for more info see:
        # http://stackoverflow.com/questions/1015307/python-bind-an-unbound-method

    return method_call


class SessionContext(WSGIContext):

    def __init__(self, environ, start_response):
        WSGIContext.__init__(self, environ, start_response)
        #: a session object, or None if no session available
        self.session = None


class SessionApp(WSGIApp):

    #: The name of our CSRF token
    CSRF_TOKEN = "csrftoken"

    #: Extended context class
    ContextClass = SessionContext

    #: The session class to use, must be (derived from) :class:`Session`
    SessionClass = Session

    def __init__(self, session_set):
        WSGIApp.__init__(self)
        #: the entity set used to store sessions
        self.session_set = session_set

    def init_dispatcher(self):
        WSGIApp.init_dispatcher(self)
        self.set_method('/ctest', self.ctest)
        self.set_method('/wlaunch', self.wlaunch)

    def session_page(self, context, page_method, return_path):
        """Returns a session protected page

        context
            The :class:`WSGIContext` object

        page_method
            A function or *bound* method that will handle the page.
            Must have the signature::

                page_method(context)

            and return the generator for the page as per the WSGI
            specification.

        return_path
            A :class:`pyslet.rfc2396.URI` instance pointing at the page
            that will be returned by page_method, used if the session is
            not established yet and a test page redirect needs to be
            implemented.

        This method is only called *after* the session has been created,
        in other words, context.session must be a valid session.

        This method either calls the page_method or returns a
        redirection sequence which culminates in a request to
        return_path."""
        # has the user been here before?
        cookies = context.get_cookies()
        if Session.COOKIE_TEST not in cookies:
            # no they haven't, set a cookie and redirect
            c = cookie.Section4Cookie(
                Session.COOKIE_TEST, "0",
                path=str(context.get_app_root().abs_path),
                max_age=Session.COOKIE_TEST_AGE)
            context.add_header('Set-Cookie', str(c))
            query = urllib.urlencode(
                {'return': str(return_path),
                 'sid': context.session.get_user_key()})
            ctest = URI.from_octets('ctest?' + query).resolve(
                context.get_app_root())
            return self.redirect_page(context, ctest)
        context.session.establish()
        return page_method(context)

    def session_wrapper(self, context, page_method):
        if context.session is None:
            context.session = self.SessionClass.from_context(self, context)
            sid = context.session.get_user_key()
            if context.environ['REQUEST_METHOD'].upper() == 'POST':
                # check the CSRF token
                token = context.get_form_string(self.CSRF_TOKEN)
                # we accept a token even if the session expired but this
                # form is unlikely to do much with a new session.  The point
                # is we compare to the cookie received and not the actual
                # session key as this may have changed
                if not token or token != sid:
                    logging.warn("%s\nSecurity threat intercepted; "
                                 "POST token mismatch, possible CSRF attack\n"
                                 "session=%s; token=%s",
                                 context.environ.get('PATH_INFO', ''),
                                 context.session.get_user_key(), token)
                    return self.error_page(context, 403)
        return self.session_page(context, page_method, context.get_url())

    def ctest_page(self, context, target_url, return_url, sid):
        query = urllib.urlencode({'return': return_url, 'sid': sid})
        target_url = str(target_url) + '?' + query
        data = """<html>
    <head><title>Cookie Test Page</title></head>
    <body>
    <p>Cookie test failed: try opening in a <a href=%s
    target="_blank" id="wlaunch">new window</a></p></body>
</html>""" % xml.EscapeCharData7(str(target_url), True)
        context.set_status(200)
        return self.html_response(context, data)

    def cfail_page(self, context):
        context.set_status(200)
        data = "Page load failed: blocked cookies"
        context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [str(data)]

    def ctest(self, context):
        cookies = context.get_cookies()
        logging.debug("cookies: %s", repr(cookies))
        query = context.get_query()
        logging.debug("query: %s", repr(query))
        if 'return' not in query or 'sid' not in query:
            # missing required parameters
            return self.error_page(context, 400)
        if Session.COOKIE_TEST not in cookies:
            # cookies are blocked
            if query.get('framed', '0') == '1':
                # we've been through the wlaunch sequence already
                # just fail
                return self.cfail_page(context)
            wlaunch = URI.from_octets('wlaunch').resolve(
                context.get_app_root())
            return self.ctest_page(
                context, str(wlaunch), query['return'], query['sid'])
        sid = query['sid']
        return_path = query['return']
        user_key = cookies.get(Session.COOKIE_SESSION, 'MISSING')
        if user_key != sid:
            # we got a cookie, but not the one we expected.  Possible
            # foul play so remove both sessions and die
            if user_key:
                Session.delete_session(self.session_set, user_key)
            if sid:
                Session.delete_session(self.session_set, sid)
            # go to an error page
            logging.warn("%s\nSecurity threat intercepted; "
                         "session mismatch, possible fixation attack\n"
                         "cookie=%s; qparam=%s",
                         context.environ.get('PATH_INFO', ''),
                         user_key, sid)
            return self.error_page(context, 400)
        if not self.check_redirect(context, return_path):
            return self.error_page(context, 400)
        # we have matching session ids and the redirect checks out
        context.session = self.SessionClass.from_context(self, context)
        if context.session.get_user_key() == sid:
            # but we've exposed the user_key in the URL which is bad.
            # Let's rewrite that now for safety (without changing
            # session).
            user_key = context.session.update_user_key(context)
        return self.redirect_page(context, return_path)

    def wlaunch(self, context):
        context.get_app_root()
        cookies = context.get_cookies()
        logging.debug("cookies: %s", repr(cookies))
        query = context.get_query()
        if 'return' not in query or 'sid' not in query:
            # missing required parameters
            return self.error_page(context, 400)
        logging.debug("query: %s", repr(query))
        # load the session from the query initially
        sid = query['sid']
        qsession = self.SessionClass.from_sid(self, sid)
        if (qsession is not None and
                (qsession.is_established() or
                 not qsession.match_environ(context))):
            # we're still trying to establish a session here so this
            # is a surprising result.  Perhaps an attacker has
            # injected their own established session ID here?
            Session.delete_session(self.session_set, sid)
            logging.warn("Security threat intercepted in wlaunch; "
                         "unexpected session injected in query, "
                         "possible fixation attack\n"
                         "session=%s", sid)
            return self.error_page(context, 400)
        return_path = query['return']
        if not self.check_redirect(context, return_path):
            return self.error_page(context, 400)
        if Session.COOKIE_TEST not in cookies:
            # no cookies, either the user has never been here before or
            # cookies are blocked completely, test again
            if qsession is not None:
                # reuse the unestablished session from the query
                # BTW, if you delete the test cookie it could kill your
                # session!
                context.session = qsession
                context.session.set_cookie(context)
            else:
                context.session = self.SessionClass.from_context(self, context)
            c = cookie.Section4Cookie(
                Session.COOKIE_TEST, "0",
                path=str(context.get_app_root().abs_path),
                max_age=Session.COOKIE_TEST_AGE)
            context.add_header('Set-Cookie', str(c))
            query = urllib.urlencode(
                {'return': return_path,
                 'sid': context.session.get_user_key(),
                 'framed': '1'})
            ctest = URI.from_octets('ctest?' + query).resolve(
                context.get_app_root())
            return self.redirect_page(context, ctest)
        # so cookies were blocked in the frame but now we're in a new
        # window, suddenly, they appear.  Merge our new session into the
        # old one if the old one was already established
        context.session = self.SessionClass.from_context(self, context)
        if (context.session.is_established() and qsession is not None):
            # established, matching session.  Merge!
            context.session.absorb(qsession)
        # now we finally have a session
        if context.session.get_user_key() == sid:
            # this session id was exposed in the query, change it
            context.session.update_user_key(context)
        return self.redirect_page(context, return_path)

    def check_redirect(self, context, target_path):
        if target_path:
            if not isinstance(target_path, URI):
                target_path = URI.from_octets(target_path)
            if (target_path.get_canonical_root() !=
                    context.get_app_root().get_canonical_root()):
                # catch the open redirect here, nice try!
                logging.warn("%s\nSecurity threat intercepted; "
                             "external redirect, possible phishing attack\n"
                             "requested redirect to %s",
                             str(context.get_url()), str(target_path))
                return False
            else:
                return True
        else:
            return False


class DBAppMixin(object):

    @classmethod
    def add_options(cls, parser):
        super(DBAppMixin, cls).add_options(parser)
        parser.add_option(
            "-s", "--sqlout", dest="sqlout",
            default=None, help="Write out SQL script and quit")
        parser.add_option(
            "-m", "--memory", dest="in_memory", action="store_true",
            default=False, help="Use in-memory sqlite database")

    def set_options2(self, options, args):
        super(DBAppMixin, self).set_options2(options, args)
        if options.sqlout is not None:
            # implies in_memory
            if options.sqlout == '-':
                out = StringIO.StringIO()
                self.dbinit_sqlite(in_memory=True, sql_out=out)
                print out.getvalue()
            else:
                with open(options.sqlout, 'wb') as f:
                    self.dbinit_sqlite(in_memory=True, sql_out=f)
            sys.exit(0)
        elif options.in_memory:
            self.dbinit_sqlite(in_memory=True)
        else:
            self.dbinit_sqlite(in_memory=False)

    def __init__(self, metadata_path, container_name):
        if not os.path.isabs(metadata_path):
            metadata_path = os.path.join(self.private_files, metadata_path)
        #: the metadata document for our data layer
        self.doc = self._load_metadata(metadata_path)
        #: the entity container for our database
        self.container = self.doc.root.DataServices[container_name]
        #: the concrete database object
        self.dbcontainer = None

    def _load_metadata(self, path):
        """Loads the metadata file from path."""
        doc = edmx.Document()
        with open(path, 'rb') as f:
            doc.Read(f)
        return doc

    def dbinit_sqlite(self, in_memory=False, sql_out=None):
        from pyslet.odata2.sqlds import SQLiteEntityContainer
        if in_memory:
            path = ":memory:"
            initdb = True
        else:
            path = os.path.join(self.private_files, 'nbdatabase.db')
            initdb = not os.path.isfile(path)
        self.dbcontainer = SQLiteEntityContainer(
            file_path=path, container=self.container)
        if sql_out is not None:
            # write the sql create script to sql_out
            self.dbcontainer.create_all_tables(out=sql_out)
        elif initdb:
            self.dbcontainer.create_all_tables()
