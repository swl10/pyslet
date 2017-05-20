#! /usr/bin/env python
"""Utilities for writing applications based on wsgi"""

import base64
import binascii
import cgi
import io
import json
import logging
import mimetypes
import optparse
import os
import quopri
import random
import sys
import threading
import time
import traceback

from hashlib import sha256
from wsgiref.simple_server import make_server

from . import iso8601 as iso
from .http import (
    cookie,
    messages,
    params)
from .odata2 import (
    core as odata,
    csdl as edm,
    metadata as edmx)
from .odata2.sqlds import SQLEntityContainer
from .py2 import (
    byte_value,
    dict_items,
    force_ascii,
    force_bytes,
    input3,
    is_ascii,
    is_text,
    is_unicode,
    long2,
    parse_qs,
    range3,
    to_text,
    UnicodeMixin,
    urlencode,
    urlquote)
from .rfc2396 import (
    escape_data,
    FileURL,
    unescape_data,
    URI)
from .xml import structures as xml
from .vfs import OSFilePath


try:
    from Crypto.Cipher import AES
    from Crypto import Random
    got_crypto = True
except ImportError:
    got_crypto = False


logger = logging.getLogger('pyslet.wsgi')


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
        for i in range3(nfours):
            four = "%02X%02X" % (
                byte_value(rbytes[2 * i]), byte_value(rbytes[2 * i + 1]))
            key.append(four)
    except NotImplementedError:
        logger.warning("urandom required for secure key generation")
        for i in range3(nfours):
            four = []
            for j in range3(4):
                four.append(random.choice('0123456789ABCDEF'))
            key.append(''.join(four))
    return '.'.join(key)


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
    return long2(sha256(src).hexdigest()[0:15], 16)


class WSGIContext(object):

    """A class used for managing WSGI calls

    environ
        The WSGI environment

    start_response
        The WSGI call-back

    canonical_root
        A URL that overrides the automatically derived canonical root,
        see :class:`WSGIApp` for more details.

    This class acts as a holding place for information specific to each
    request being handled by a WSGI-based application.  In some
    frameworks this might be called the request object but we already
    have requests modelled in the http package and, anyway, this holds
    information about the WSGI environment and the response too."""

    #: The maximum amount of content we'll read into memory (64K)
    MAX_CONTENT = 64 * 1024

    def __init__(self, environ, start_response, canonical_root=None):
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
        if canonical_root is None:
            self._canonical_root = self._get_canonical_root()
        else:
            self._canonical_root = canonical_root
        self._query = None
        self._content = None
        self._form = None
        self._cookies = None

    def set_status(self, code):
        """Sets the status of the response

        code
            An HTTP *integer* response code.

        This method sets the :attr:`status_message` automatically from
        the code.  You must call this method before calling
        start_response."""
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
        url = [self._canonical_root]
        script = urlquote(self.environ.get('SCRIPT_NAME', ''))
        if not script:
            url.append('/')
        else:
            url.append(script)
            # we always add the slash, that's our root URL
            if script[-1] != '/':
                url.append('/')
        return URI.from_octets(''.join(url))

    def get_url(self):
        """Returns the URL used in the request

        The result is a :class:`pyslet.rfc2396.URI` instance, It is
        calculated from the environment using the algorithm described in
        URL Reconstruction section of the WSGI specification except
        that it ignores the Host header for security reasons.

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
        url = [self._canonical_root]
        url.append(urlquote(self.environ.get('SCRIPT_NAME', '')))
        url.append(urlquote(self.environ.get('PATH_INFO', '')))
        query = self.environ.get('QUERY_STRING', '')
        if query:
            url += ['?', query]
        return URI.from_octets(''.join(url))

    def _get_canonical_root(self):
        url = [self.environ['wsgi.url_scheme'], '://']
        sflag = (self.environ['wsgi.url_scheme'] == 'https')
        authority = self.environ['SERVER_NAME']
        port = self.environ['SERVER_PORT']
        if sflag:
            if port != '443':
                url.append("%s:%s" % (authority, port))
            else:
                url.append(authority)
        elif port != '80':
            url.append("%s:%s" % (authority, port))
        else:
            url.append(authority)
        return ''.join(url)

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
            self._query = parse_qs(
                self.environ.get('QUERY_STRING', ''))
            for n, v in list(dict_items(self._query)):
                self._query[n] = ','.join(v)
        return self._query

    def get_content(self):
        """Returns the content of the request as a string

        The content is read from the input, up to CONTENT_LENGTH bytes,
        and is returned as a binary string.  If the content exceeds
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
                f = io.BytesIO()
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
                return ','.join([x.value for x in result])
            else:
                if result.file:
                    # could be an ordinary field in multipart/form-data
                    fpos = result.file.tell()
                    result.file.seek(0, io.SEEK_END)
                    fsize = result.file.tell()
                    result.file.seek(fpos)
                    if fsize > max_length:
                        raise BadRequest
                    # result.value could be bytes or (text) str
                    value = result.value
                    if isinstance(value, bytes):
                        charset = 'ascii'
                        if result.type_options is not None:
                            charset = result.type_options.get('charset',
                                                              'ascii')
                        return value.decode(charset)
                    else:
                        return value
                return result.value
        return ''

    def get_form_long(self, name):
        """Returns the value of a (long) integer parameter from the form.

        name
            The name of the parameter

        If the parameter is missing from the form then None is returned,
        if the parameter is present but is not a valid integer then
        :class:`BadRequest` is raised."""
        value = self.get_form_string(name, 256)
        try:
            return long2(value)
        except ValueError as err:
            logging.debug("get_form_long: %s", str(err))
            raise BadRequest

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
                        self._cookies[name] = b','.join(value)
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
    #: None.  An :class:`pyslet.vfs.OSFilePath` instance.
    static_files = None

    private_files = None
    """Private data diretory

    An :class:`pyslet.vfs.OSFilePath` instance.

    The directory used for storing private data.  The directory is
    partitioned into sub-directories based on the lower-cased class name
    of the object that owns the data.  For example, if private_files is
    set to '/var/www/data' and you derive a class called 'MyApp' from
    WSGIApp you can assume that it is safe to store and retrieve private
    data files from '/var/www/data/myapp'.

    private_files defaults to None for safety.  The current WSGIApp
    implementation does not depend on any private data."""

    settings_file = None
    """The path to the settings file.  Defaults to None.

    An :class:`pyslet.vfs.OSFilePath` instance.

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

    canonical_root ("http://localhost" or "http://localhost:<port>")
        The canonical URL scheme, host (and port if required) for the
        application.  This value is passed to the context and used by
        :meth:`WSGIContext.get_url` and similar methods in preference to
        the SERVER_NAME and SEVER_PORT to construct absolute URLs
        returned or recorded by the application.  Note that the Host
        header is always ignored to prevent related `security attacks`__.

        ..  __:
            http://www.skeletonscribe.net/2013/05/practical-http-host-header-attacks.html

        If no value is given then the default is calculated taking in to
        consideration the port setting.

    interactive (False)
        Sets the behaviour of :meth:`run_server`, if specified the main
        thread prompts the user with a command line interface allowing
        you to interact with the running server.  When False, run_server
        will run forever and can only be killed by an application
        request that sets :attr:`stop` to True or by an external signal
        that kills the process.

    static (None)
        A URL to the static files (not a local file path).  This will
        normally be an absolute path or a relative path.  Relative paths
        are relative to the settings file in which the setting is
        defined. As URL syntax is used you must use the '/' as a path
        separator and add proper URL-escaping.  On Windows, UNC paths
        can be specified by putting the host name in the authority
        section of the URL.

    private (None)
        A URL to the private files.  Interpreted as per the 'static'
        setting above."""

    #: the class settings loaded from :attr:`settings_file` by
    #: :meth:`setup`
    settings = None

    #: the base URI of this class, set from the path to the settings
    #: file itself and is used to locate data files on the server.  This
    #: is a :class:`pyslet.rfc2396.FileURL` instance. Not to be confused
    #: with the base URI of resources exposed by the application this
    #: class implements!
    base = None

    #: the base URI of this class' private files.  This is set from the
    #: :attr:`private_files` member and is a
    #: :class:`pyslet.rfc2396.FileURL` instance
    private_base = None

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

    #: the integer millisecond time (since the epoch) corresponding to
    #: 01 January 1970 00:00:00 UTC the JavaScript time origin.
    js_origin = int(
        iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0, zdirection=0)
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

        -v          Sets the logging level to WARNING, INFO or DEBUG
                    depending on the number of times it is specified.
                    Overrides the 'level' setting in the settings file.

        -p, --port  Overrides the value of the 'port' setting in the
                    settings file.

        -i, --interactive   Overrides the value of the 'interactive'
                            setting in the settings file.

        --static    Overrides the value of :attr:`static_files`.

        --private   Overrides the value of :attr:`private_files`.

        --settings  Sets the path to the :attr:`settings_file`."""
        parser.add_option(
            "-v", action="count", dest="logging",
            default=None, help="increase verbosity of output up to 3x")
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
        setting.

        Derived classes should always use super to call the base
        implementation before their own setup actions are performed."""
        if options and options.static:
            cls.static_files = OSFilePath(options.static).abspath()
        if options and options.private:
            cls.private_files = OSFilePath(options.private).abspath()
        if options and options.settings:
            cls.settings_file = OSFilePath(options.settings).abspath()
        if is_text(cls.settings_file):
            cls.settings_file = OSFilePath(cls.settings_file)
        cls.settings = {}
        if cls.settings_file:
            cls.base = URI.from_virtual_path(cls.settings_file)
            if cls.settings_file.isfile():
                with cls.settings_file.open('rb') as f:
                    cls.settings = json.loads(f.read().decode('utf-8'))
        settings = cls.settings.setdefault('WSGIApp', {})
        if options and options.logging is not None:
            settings['level'] = (
                logging.ERROR, logging.WARNING, logging.INFO,
                logging.DEBUG)[min(options.logging, 3)]
        level = settings.setdefault('level', None)
        if level is not None:
            logging.basicConfig(level=settings['level'])
        if options and options.port is not None:
            settings['port'] = int(options.port)
        else:
            settings.setdefault('port', 8080)
        settings.setdefault(
            'canonical_root', "http://localhost%s" %
            ("" if settings['port'] == 80 else (":%i" % settings['port'])))
        if options and options.interactive is not None:
            settings['interactive'] = options.interactive
        else:
            settings.setdefault('interactive', False)
        url = settings.setdefault('static', None)
        if cls.static_files is None and url:
            cls.static_files = cls.resolve_setup_path(url)
        if is_text(cls.static_files):
            # catch older class definitions
            cls.static_files = OSFilePath(cls.static_files)
        url = settings.setdefault('private', None)
        if cls.private_files is None and url:
            cls.private_files = cls.resolve_setup_path(url)
        if is_text(cls.private_files):
            cls.private_files = OSFilePath(cls.private_files)
        if cls.private_files:
            cls.private_base = URI.from_virtual_path(
                cls.private_files.join(''))
        # this logging line forces the root logger to be initialised
        # with the default level as a catch all
        logging.debug("Logging configured for %s", cls.__name__)

    @classmethod
    def resolve_setup_path(cls, uri_path, private=False):
        """Resolves a settings-relative path

        uri_path
            The relative URI of a file or directory.

        private (False)
            Resolve relative to the private files directory

        Returns uri_path as an OSFilePath instance after resolving relative
        to the settings file location or to the private files location
        as indicated by the private flag.  If the required location is
        not set then uri_path must be an absolute file URL (starting
        with, e.g., file:///). On Windows systems the authority
        component of the URL may be used to specify the host name for a
        UNC path."""
        url = URI.from_octets(uri_path)
        if private and cls.private_base:
            url = url.resolve(cls.private_base)
        elif not private and cls.base:
            url = url.resolve(cls.base)
        if not url.is_absolute() and not isinstance(url, FileURL):
            raise RuntimeError("Can't resolve setup path %s" % uri_path)
        return url.get_virtual_file_path()

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
            if not is_ascii(status):
                logger.error("Value for status line: %s", repr(status))
                status = force_ascii(to_text(status))
            logger.debug("*** START RESPONSE ***")
            logger.debug(status)
            new_headers = []
            for h, v in response_headers:
                if not is_ascii(h):
                    logger.error("Header name: %s", repr(h))
                    h = force_ascii(to_text(h))
                if not is_ascii(v):
                    logger.error("Header value: %s: %s", h, repr(v))
                    v = force_ascii(to_text(v))
                logger.debug("%s: %s", h, v)
                new_headers.append((h, v))
            return start_response(status, new_headers, exc_info)
        logger.debug("*** START REQUEST ***")
        for key in environ:
            logger.debug("%s: %s", key, str(environ[key]))
        blank = False
        for data in self(environ, wrap_response):
            if not blank:
                logger.debug("")
                blank = True
            if not isinstance(data, bytes):
                logger.error("Bad type for response data in %s\n%s",
                             str(environ['PATH_INFO']), repr(data))
                if is_unicode(data):
                    data = data.encode('utf-8')
                else:
                    data = bytes(data)
            else:
                logger.debug(quopri.encodestring(data))
            yield data

    def __call__(self, environ, start_response):
        context = self.ContextClass(
            environ, start_response,
            self.settings['WSGIApp']['canonical_root'])
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
            logger.exception(context.environ['PATH_INFO'])
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
        file_path = self.static_files
        if file_path is None:
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
                if not cookie.is_ldh_label(p.encode('ascii')):
                    raise PageNotFound
                file_path = file_path.join(p)
                if not file_path.isdir():
                    raise PageNotFound
            elif not p:
                # this is the directory form, e.g., /app/docs/ but we
                # don't support indexing, we're not Apache
                raise PageNotFound
            else:
                # last component must be a filename.ext form
                splitp = p.split('.')
                if (len(splitp) != 2 or
                        not cookie.is_ldh_label(splitp[0].encode('ascii')) or
                        not cookie.is_ldh_label(splitp[1].encode('ascii'))):
                    raise PageNotFound
                filename = p
                ext = splitp[1]
                file_path = file_path.join(p)
        if not file_path.isfile():
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
        return self.file_response(context, file_path)

    def file_response(self, context, file_path):
        """Returns a file from the file system

        file_path
            The system file path of the file to be returned as an
            :class:`pyslet.vfs.OSFilePath` instance.

        The Content-Length header is set from the file size, the
        Last-Modified date is set from the file's st_mtime and the
        file's data is returned in chunks of :attr:`MAX_CHUNK` in the
        response.

        The status is *not* set and must have been set before calling
        this method."""
        if is_text(file_path):
            file_path = OSFilePath(file_path)
        finfo = file_path.stat()
        context.add_header("Content-Length", str(finfo.st_size))
        context.add_header("Last-Modified",
                           str(params.FullDate.from_unix_time(finfo.st_mtime)))
        context.start_response()
        bleft = finfo.st_size
        with file_path.open('rb') as f:
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

        The Content-Type header is set to text/html (with an explicit
        charset if data is a unicode string).  The status is *not* set and
        must have been set before calling this method."""
        if is_unicode(data):
            data = data.encode('utf-8')
            context.add_header("Content-Type", "text/html; charset=utf-8")
        else:
            context.add_header("Content-Type", "text/html")
        # catch the odd case where data is a subclass of str - still ok
        # but the default WSGI server uses this stronger test!
        if not isinstance(data, bytes):
            data = bytes(data)
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
        if is_unicode(data):
            data = data.encode('utf-8')
        if not isinstance(data, bytes):
            data = bytes(data)
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
        if is_unicode(data):
            data = data.encode('utf-8')
            context.add_header("Content-Type", "text/plain; charset=utf-8")
        else:
            context.add_header("Content-Type", "text/plain")
        if not isinstance(data, bytes):
            data = bytes(data)
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
</body></html>""" % xml.escape_char_data7(str(location), True)
        context.add_header("Location", str(location))
        context.add_header("Content-Type", "text/html")
        context.add_header("Content-Length", str(len(data)))
        context.set_status(code)
        context.start_response()
        return [force_bytes(data)]

    def error_page(self, context, code=500, msg=None):
        """Generates an error response

        code (500)
            The status code to send.

        msg (None)
            An optional plain-text error message.  If not given then the
            status line is echoed in the body of the response."""
        context.set_status(code)
        if msg is None:
            msg = force_bytes("%i %s" % (code, context.status_message))
            context.add_header("Content-Type", "text/plain")
        elif is_unicode(msg):
            try:
                msg = msg.encode('ascii')
                context.add_header("Content-Type", "text/plain")
            except UnicodeError:
                msg = msg.encode('utf-8')
                context.add_header("Content-Type", "text/plain; charset=utf-8")
        else:
            context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(msg)))
        context.start_response()
        return [msg]

    def internal_error(self, context, err):
        context.set_status(500)
        data = force_bytes(
            "%i %s\r\n%s" % (context.status, context.status_message, str(err)))
        context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(data)))
        try:
            context.start_response()
        except Exception:
            # log this error and move on as we're already returning a 500
            logging.error(
                "Error raised by WSGIApp.internal_error: %s",
                "".join(traceback.format_exception(*sys.exc_info())))
        return [data]

    def _run_server_thread(self):
        """Starts the web server running"""
        port = self.settings['WSGIApp']['port']
        server = make_server('', port, self.call_wrapper)
        logger.info("HTTP server on port %i running", port)
        # Respond to requests until process is killed
        while not self.stop:
            server.handle_request()

    def run_server(self):
        t = threading.Thread(target=self._run_server_thread)
        t.setDaemon(True)
        t.start()
        logger.info("Starting %s server on port %s", self.__class__.__name__,
                    self.settings['WSGIApp']['port'])
        if self.settings['WSGIApp']['interactive']:
            # loop around getting commands
            while not self.stop:
                cmd = input3('cmd: ')
                if cmd.lower() == 'stop':
                    self.stop = True
                elif cmd:
                    try:
                        sys.stdout.write((to_text(eval(cmd))))
                    except Exception as err:
                        sys.stdout.write("Error: %s " % to_text(err))
            sys.exit()
        else:
            t.join()


class WSGIDataApp(WSGIApp):

    """Extends WSGIApp to include a data store

    The key 'WSGIDataApp' is reserved for settings defined by this
    class in the settings file. The defined settings are:

    container (None)
        The name of the container to use for the data store.  By
        default, the default container is used.  For future
        compatibility you should not depend on using this option.

    metadata (None)
        URI of the metadata file containing the data schema.  The file
        is assumed to be relative to the settings_file.

    source_type ('sqlite')
        The type of data source to create.  The default value
        is sqlite.  A value of 'mysql' select's Pyslet's mysqldbds
        module instead.

    sqlite_path ('database.sqlite3')
        URI of the database file.  The file is assumed to be relative to
        the private_files directory, though an absolute path may be
        given.

    dbhost ('localhost')
        For mysql databases, the hostname to connect to.

    dname (None)
        The name of the database to connect to.

    dbuser (None)
        The user name to connect to the database with.

    dbpassword (None)
        The password to use in conjunction with dbuser

    keynum ('0')
        The identification number of the key to use when storing
        encrypted data in the container.

    secret (None)
        The key corresponding to keynum.  The key is read in plain text
        from the settings file and must be provided in order to use the
        :attr:`app_cipher` for managing encrypted data and secure
        hashing.  Derived classes could use an alternative mechanism for
        reading the key, for example, using the keyring_ python module.

    cipher ('aes')
        The type of cipher to use.  By default :class:`AESAppCipher` is
        used which uses AES_ internally with a 256 bit key created by
        computing the SHA256 digest of the secret string.  The only
        other supported value is 'plaintext' which does not provide any
        encryption but allows the app_cipher object to be used in cases
        where encryption may or may not be used depending on the
        deployment environment.  For example, it is often useful to turn
        off encryption in a development environment!

    when (None)
        An optional value indicating when the specified secret comes
        into operation.  The value should be a fully specified time
        point in ISO format with timezone offset, such as
        '2015-01-01T09:00:00-05:00'.  This value is used when the
        application is being restarted after a key change, for details
        see :meth:`AppCipher.change_key`.

        The use of AES requires the PyCrypto module to be installed.

    ..  _keyring:  https://pypi.python.org/pypi/keyring

    ..  _AES:
            http://en.wikipedia.org/wiki/Advanced_Encryption_Standard"""

    @classmethod
    def add_options(cls, parser):
        """Adds the following options:

        -s, --sqlout        print the suggested SQL database schema and
                            then exit.  The setting of --create is
                            ignored.

        --create_tables     create tables in the database

        -m. --memory        Use an in-memory SQLite database.  Overrides
                            any source_type and encryption setting
                            values .  Implies --create_tables"""
        super(WSGIDataApp, cls).add_options(parser)
        parser.add_option(
            "-s", "--sqlout", dest="sqlout", action="store_true",
            default=False, help="Write out SQL script and quit")
        parser.add_option(
            "--create_tables", dest="create_tables", action="store_true",
            default=False, help="Create tables in the database")
        parser.add_option(
            "-m", "--memory", dest="in_memory", action="store_true",
            default=False, help="Use in-memory sqlite database")

    #: the metadata document for the underlying data service
    metadata = None

    #: the data source object for the underlying data service the type
    #: of this object will vary depending on the source type.  For
    #: SQL-type containers this will be an instance of a class derived
    #: from :class:`~pyslet.odata2.sqlds.SQLEntityContainer`
    data_source = None

    #: the entity container (cf database)
    container = None

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        """Adds database initialisation

        Loads the :attr:`metadata` document.  Creates the
        :attr:`data_source` according to the configured :attr:`settings`
        (creating the tables only if requested in the command line
        options).  Finally sets the :attr:`container` to the entity
        container for the application.

        If the -s or --sqlout option is given in options then the data
        source's create table script is output to standard output and
        sys.exit(0) is used to terminate the process."""
        super(WSGIDataApp, cls).setup(options, args, **kwargs)
        settings = cls.settings.setdefault('WSGIDataApp', {})
        metadata_file = settings.setdefault('metadata', None)
        if metadata_file:
            metadata_file = cls.resolve_setup_path(metadata_file)
            # load the metadata document for our data layer
            cls.metadata = edmx.Document()
            with metadata_file.open('rb') as f:
                cls.metadata.read(f)
        else:
            cls.metadata = cls.load_default_metadata()
        container_name = settings.setdefault('container', None)
        if container_name:
            cls.container = cls.metadata.root.DataServices[container_name]
        else:
            cls.container = cls.metadata.root.DataServices.defaultContainer
        if options and options.create_tables:
            create_tables = True
        else:
            create_tables = False
        if options and options.in_memory:
            source_type = "sqlite"
            sqlite_path = ':memory:'
            create_tables = True
        else:
            source_type = settings.setdefault('source_type', 'sqlite')
            if source_type == 'sqlite':
                # do sqlite settings here
                if options and options.sqlout:
                    # use an in-memory database
                    sqlite_path = ':memory:'
                else:
                    sqlite_path = settings.setdefault(
                        'sqlite_path', 'database.sqlite3')
                    sqlite_path = cls.resolve_setup_path(
                        sqlite_path, private=True)
            elif source_type == 'mysql':
                dbhost = settings.setdefault('dbhost', 'localhost')
                dbname = settings.setdefault('dbname', None)
                dbuser = settings.setdefault('dbuser', None)
                dbpassword = settings.setdefault('dbpassword', None)
        if source_type == 'sqlite':
            from pyslet.odata2.sqlds import SQLiteEntityContainer
            # accepts either the string ":memory:" or an OSFilePath
            cls.data_source = SQLiteEntityContainer(
                file_path=sqlite_path, container=cls.container)
        elif source_type == 'mysql':
            from pyslet.mysqldbds import MySQLEntityContainer
            cls.data_source = MySQLEntityContainer(
                host=dbhost, user=dbuser, passwd=dbpassword, db=dbname,
                container=cls.container)
        else:
            raise ValueError("Unknown data source type: %s" % source_type)
        if isinstance(cls.data_source, SQLEntityContainer):
            if options and options.sqlout:
                out = io.StringIO()
                cls.data_source.create_all_tables(out=out)
                sys.stdout.write(out.getvalue())
                sys.exit(0)
            elif create_tables:
                cls.data_source.create_all_tables()
        settings.setdefault('keynum', 0)
        if options and options.in_memory and 'AppKeys' in cls.container:
            settings.setdefault('secret', generate_key())
            settings.setdefault('cipher', 'plaintext')
        else:
            settings.setdefault('secret', None)
            settings.setdefault('cipher', 'aes')
        settings.setdefault('when', None)

    @classmethod
    def load_default_metadata(cls):
        raise RuntimeError("No path to metadata")

    @classmethod
    def new_app_cipher(cls):
        """Creates an :class:`AppCipher` instance

        This method is called automatically on construction, you won't
        normally need to call it yourself but you may do so, for
        example, when writing a script that requires access to data
        encrypted by the application.

        If there is no 'secret' defined then None is returned.

        Reads the values from the settings file and creates an instance
        of the appropriate class based on the cipher setting value.  The
        cipher uses the 'AppKeys' entity set in :attr:`container` to store
        information about expired keys.  The AppKey entities have the
        following three properties:

        KeyNum (integer key)
            The key identification number

        KeyString (string)
            The *encrypted* secret, for example::

                '1:OBimcmOesYOt021NuPXTP01MoBOCSgviOpIL'

            The number before the colon is the key identification number
            of the secret used to encrypt the string (and will always be
            different from the KeyNum field of course).  The data after
            the colon is the base-64 encoded encrypted string.  The same
            format is used for all data enrypted by
            :class:`AppCipher` objects.  In this case the secret was the
            word 'secret' and the algorithm used is AES.

        Expires (DateTime)
            The UTC time at which this secret will expire.  After this
            time a newer key should be used for encrypting data though
            this key may of course still be used for decrypting data."""
        keynum = cls.settings['WSGIDataApp']['keynum']
        secret = cls.settings['WSGIDataApp']['secret']
        cipher = cls.settings['WSGIDataApp']['cipher']
        when = cls.settings['WSGIDataApp']['when']
        if when:
            when = iso.TimePoint.from_str(when)
        if cipher == 'plaintext':
            cipher_class = AppCipher
        elif cipher == 'aes':
            cipher_class = AESAppCipher
        else:
            # danger, raise an error
            raise RuntimeError("Unknown cipher: %s" % cipher)
        if secret:
            return cipher_class(keynum, secret.encode('utf-8'),
                                cls.container['AppKeys'], when)
        else:
            return None

    def __init__(self, **kwargs):
        super(WSGIDataApp, self).__init__(**kwargs)
        #: the application's cipher, a :class:`AppCipher` instance.
        self.app_cipher = self.new_app_cipher()


class PlainTextCipher(object):

    def __init__(self, key):
        self.key = key

    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data

    def hash(self, data):
        return sha256(data + self.key).digest()


class AESCipher(object):

    def __init__(self, key):
        self.key = sha256(key).digest()

    def encrypt(self, data):
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CFB, iv)
        return iv + cipher.encrypt(data)

    def decrypt(self, data):
        iv = data[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CFB, iv)
        return cipher.decrypt(data[AES.block_size:])

    def hash(self, data):
        return sha256(data + self.key).digest()


class AppCipher(object):

    """A cipher for encrypting application data

    key_num
        A key number

    key
        A binary string containing the application key.

    key_set
        An entity set used to store previous keys.  The entity set must
        have an integer key property 'KeyNum' and a string field
        'KeyString'.  The string field must be large enough to contain
        encrypted versions of previous keys.

    when (None)
        A fully specified :class:`pyslet.iso8601.TimePoint` at which
        time the key will become active.  If None, the key is active
        straight away.  Otherwise, the key_set is searched for a key
        that is still active and that key is used when encrypting data
        until the when time, at which point the given key takes over.

    The object wraps an underlying cipher.  Strings are encrypted using
    the cipher and then encoded using base64.  The output is then
    prefixed with an ASCII representation of the key number (key_num)
    followed by a ':'.  For example, if key_num is 7 and the cipher
    is plain-text (the default) then encrypt("Hello") results in::

        "7:SGVsbG8="

    When decrypting a string, the key number is parsed and matched
    against the key_num of the key currently in force.  If the string
    was encrypted with a different key then the key_set is used to look
    up that key (which is itself encrypted of course).  The process
    continues until a key encrypted with key_num is found.

    The upshot of this process is that you can change the key associated
    with an application.  See :meth:`change_key` for details."""

    #: the maximum age of a key, which is the number of times the key
    #: can be changed before the original key is considered too old to
    #: be used for decryption.
    MAX_AGE = 100

    def __init__(self, key_num, key, key_set, when=None):
        self.lock = threading.RLock()
        self.key_set = key_set
        self.key_num = key_num
        self.key = key
        self.ciphers = {key_num: self.new_cipher(key)}
        if when:
            # we need to find a key that hasn't expired
            with key_set.open() as keys:
                t = edm.EDMValue.from_type(edm.SimpleType.DateTime)
                t.set_from_value(time.time())
                filter = odata.CommonExpression.from_str(
                    "Expires gte :t", {'t': t})
                keys.set_filter(filter)
                # Only interested in keys that haven't expired
                old_keys = keys.values()
                if not old_keys:
                    raise RuntimeError("AppCipher: no current key")
                old_key = old_keys[0]
                self.old_num = old_key['KeyNum'].value
                self.old_key = self.decrypt(old_key['KeyString'])
                self.old_expires = when.get_unixtime()
                self.ciphers[self.old_num] = self.new_cipher(self.old_key)
        else:
            self.old_num = None
            self.old_key = None
            self.old_expires = None

    def new_cipher(self, key):
        """Returns a new cipher object with the given key

        The default implementation creates a plain-text 'cipher' and is
        not suitable for secure use of encrypt/decrypt but, with a
        sufficiently good key, may still be used for hashing."""
        return PlainTextCipher(key)

    def change_key(self, key_num, key, when):
        """Changes the key of this application.

        key_num
            The number given to the new key, must differ from the last
            :attr:`MAX_AGE` key numbers.

        key
            A binary string containing the new application key.

        when
            A fully specified :class:`pyslet.iso8601.TimePoint` at which
            point the new key will come into effect.

        Many organizations have a policy of changing keys on a routine
        basis, for example, to ensure that people who have had temporary
        access to the key only have temporary access to the data it
        protects.  This method makes it easier to implement such a
        policy for applications that use the AppCipher class.

        The existing key is encrypted with the new key and a record is
        written to the :attr:`key_set` to record the *existing* key
        number, the encrypted key string and the *when* time, which is
        treated as an expiry time in this context.

        This procedure ensures that strings encrypted with an old key
        can always be decrypted because the value of the old key can be
        looked up.  Although it is encrypted, it will be encrypted with
        a new(er) key and the procedure can be repeated as necessary
        until a key encrypted with the newest key is found.

        The key change process then becomes:

        1.  Start a utility process connected to the application's
            entity container using the existing key and then call the
            change_key method.  Pass a value for *when* that will give
            you time to reconfigure all AppCipher clients.  Assuming the
            key change is planned, a time in hours or even days ahead
            can be used.

        2.  Update or reconfigure all existing applications so that they
            will be initialised with the new key and the same value for
            *when* next time they are restarted.

        3.  Restart/refresh all running applications before the change
            over time.  As this does not need to be done simultaneously,
            a load balanced set of application servers can be cycled on
            a schedule to ensure continuous running).

        Following a key change the entity container will still contain
        data encrypted with old keys and the architecture is such that
        compromise of a key is sufficient to read all encrypted data
        with that key and all previous keys.  Therefore, changing the
        key only protects new data.

        In situations where policy dictates a key change it might make
        sense to add a facility to the application for re-encrypting
        data in the data store by going through a
        read-decrypt/encrypt-write cycle with each protected data field.
        Of course, the old key could still be used to decrypt this
        information from archived backups of the data store.
        Alternatively, if the protected data is itself subject to change
        on a routine basis you may simply rely on the natural turnover
        of data in the application.  The strategy you choose will depend
        on your application.

        The :attr:`MAX_AGE` attribute determines the maximum number of
        keys that can be in use in the data set simultaneously.
        Eventually you will have to update encrypted data in the data
        store."""
        with self.lock:
            self.old_num = self.key_num
            self.old_key = self.key
            self.old_expires = when.get_unixtime()
            # we should already have a cipher for this key
            self.key_num = key_num
            self.key = key
            cipher = self.ciphers[key_num] = self.new_cipher(key)
            # we can't use the encrypt method here as we want to force
            # use of the new key
            old_key_encrypted = "%i:%s" % (
                key_num, force_ascii(base64.b64encode(cipher.encrypt(
                    self.old_key))))
        with self.key_set.open() as keys:
            e = keys.new_entity()
            e.set_key(self.old_num)
            e['KeyString'].set_from_value(old_key_encrypted)
            e['Expires'].set_from_value(when)
            try:
                keys.insert_entity(e)
            except edm.ConstraintError:
                # Presumably this entity already exists, possible race
                # condition on change_key - load the entity from the old
                # key number to raise KeyError if not
                e = keys[self.old_num]

    def _get_current_cipher(self):
        if self.old_expires:
            if time.time() > self.old_expires:
                # the old key has finally expired
                self.old_num = None
                self.old_key = None
                self.old_expires = None
            else:
                # use the old key
                return self.old_num, self.ciphers[self.old_num]
        return self.key_num, self.ciphers[self.key_num]

    def _get_cipher(self, num):
        stack = [(num, None, None)]
        while stack:
            key_num, key_data, cipher_num = stack.pop()
            cipher = self.ciphers.get(key_num, None)
            if cipher is None:
                stack.append((key_num, key_data, cipher_num))
                with self.key_set.open() as collection:
                    try:
                        e = collection[key_num]
                        old_key_num, old_key_data = self._split_data(
                            e['KeyString'].value)
                        if len(stack) > self.MAX_AGE:
                            raise KeyError
                        stack.append((old_key_num, old_key_data, key_num))
                    except KeyError:
                        raise RuntimeError("AppCipher: key too old")
            elif key_data:
                with self.lock:
                    new_data = cipher.decrypt(key_data)
                    if cipher_num is not None:
                        self.ciphers[cipher_num] = self.new_cipher(new_data)
            else:
                return cipher

    def encrypt(self, data):
        """Encrypts data with the current key.

        data
            A binary input string.

        Returns a character string of ASCII characters suitable for
        storage."""
        with self.lock:
            num, cipher = self._get_current_cipher()
            return "%i:%s" % (
                num, force_ascii(base64.b64encode(cipher.encrypt(data))))

    def decrypt(self, data):
        """Decrypts data.

        data
            A character string containing the encrypted data

        Returns a binary string containing the decrypted data."""
        key_num, data = self._split_data(data)
        cipher = self._get_cipher(key_num)
        return cipher.decrypt(data)

    def sign(self, message):
        """Signs a message with the current key.

        message
            A binary message string.

        Returns a character string of ASCII characters containing a
        signature of the message.  It is recommended that character
        strings are encoded using UTF-8 before signing."""
        with self.lock:
            num, cipher = self._get_current_cipher()
            salt = os.urandom(4)
            hash = cipher.hash(salt + message)
            return "%i-%s-%s" % (num, force_ascii(binascii.hexlify(salt)),
                                 force_ascii(binascii.hexlify(hash)))

    def check_signature(self, signature, message=None):
        """Checks a signature returned by sign

        signature
            The ASCII signature to be checked for validity.

        message
            A binary message string.  This is optional, if None then the
            message will be extracted from the signature string
            (reversing ascii_sign).

        On success the method returns the validated message (a binary
        string) and on failure it raises ValueError."""
        num, salt, hash, smessage = self._split_signature(signature)
        try:
            num = int(num)
            salt = binascii.unhexlify(salt)
            hash = binascii.unhexlify(hash)
            if smessage:
                smessage = unescape_data(smessage)
                if message:
                    # must match exactly!
                    if message != smessage:
                        raise ValueError
                else:
                    message = smessage
            with self.lock:
                cipher = self._get_cipher(num)
                if cipher is None:
                    return ValueError
                if cipher.hash(salt + message) == hash:
                    return message
                else:
                    raise ValueError
        except TypeError:
            raise ValueError

    def ascii_sign(self, message):
        """Signs a message with the current key

        message
            A binary message string

        The difference between ascii_sign and sign is that ascii_sign
        returns the entire message, including the signature, as a
        URI-encoded character string suitable for storage and/or
        transmission.

        The message is %-encoded (as implemented by
        :func:`pyslet.rfc2396.escape_data`).  You may apply the
        corresponding unescape data function to the entire string to get
        a binary string that *contains* an exact copy of the original
        data."""
        return "%s-%s" % (self.sign(message), escape_data(message))

    def _split_data(self, data):
        data = data.split(':')
        if len(data) != 2 or not data[0].isdigit():
            raise ValueError
        key_num = int(data[0])
        try:
            data = base64.b64decode(data[1])
        except TypeError:
            raise ValueError
        return key_num, data

    def _split_signature(self, signature):
        result = []
        pos = 0
        while True:
            if len(result) == 3:
                result.append(signature[pos:])
                return result
            new_pos = signature.find('-', pos)
            if new_pos < 0:
                result.append(signature[pos:])
                while len(result) < 4:
                    result.append('')
                return result
            result.append(signature[pos:new_pos])
            pos = new_pos + 1


class AESAppCipher(AppCipher):

    """A cipher object that uses AES to encrypt the data

    The Pycrypto module must be installed to use this class.

    The key is hashed using the SHA256 algorithm to obtain a 32 byte
    value for the AES key.  The encrypted strings contain random
    initialisation vectors so repeated calls won't generate the same
    encrypted values.  The CFB mode of operation is used."""

    def new_cipher(self, key):
        return AESCipher(key)


class CookieSession(UnicodeMixin):

    """A session object

    Used to persist a small amount of information in the user's browser
    making the session stateful.  The purpose of the session cookie is
    to hold information that does not need to be kept secret from the
    user's browser but which can be verified through cookie signing
    (outside the scope of this class).

    Bear in mind that, when serialised and signed the session data must
    fit comfortably into a cookie.  Space in cookies is severely
    restricted so we only store information in the session that can't be
    looked up quickly in an external data store.  Although this class
    can be extended to add additional information in most cases you
    won't need to do this and can instead use the session id as a key
    for loading any additional information.

    The session can be initialised from an optional character string
    which, if provided, is parsed for the session information.
    Otherwise the session object is generated with a new randomly
    selected ID.

    Session lifecycle

    When a session is first created it is in an unestablished state. In
    this state the session ID is not fixed and the session data may be
    exposed in a URL.  Once established, the session ID will be fixed
    and it must not be exposed in a URL.  Strict limits are placed on
    the allowable age of an unestablished session and, as an additional
    security measure, they are tied to a fixed User-Agent string.

    The :class:`SessionApp` class and the associated decorator take care
    of most of the complexity and they allow you to create pages that
    will only be returned to the user once a session has been
    established.  At that point you can read/write protected information
    indexed using the session id.

    If you need to store protected information before the session is
    established (only necessary when users might initiate your
    application using an authenticated POST request from a third party
    system) then you will need to:

        1   Create the protected information record and index it using
            the unestablished session id.
        2   When the session is established you'll need to update the
            session id used to index any protected information thereby
            isolating the unestablished session id.  This can be done by
            overriding :meth:`SessionApp.establish_session`

    Merging Sessions

    In some unusual cases a new session may need to be merged into an
    existing one (e.g., when cookies are blocked in frames but not when
    the user opens a new window from the frame).  In cases like this you
    may want to override :meth:`SessionApp.merge_session` to reconcile
    the two sessions prior to the newer session being discarded."""

    def __init__(self, src=None):
        if src:
            fields = src.split('-')
            if len(fields) >= 3:
                self.sid = fields[0]
                self.established = (fields[1] == '1')
                self.last_seen = iso.TimePoint.from_str(fields[2])
            else:
                raise ValueError("Bad CookieSession: %s" % src)
        else:
            self.sid = generate_key()
            self.established = False
            self.last_seen = iso.TimePoint.from_now_utc()

    def __unicode__(self):
        return "%s-%s-%s" % (self.sid, '1' if self.established else '0',
                             self.last_seen.get_calendar_string(basic=True))

    def establish(self):
        if self.established:
            raise ValueError("Session already established: %s" % self.sid)
        self.sid = generate_key()
        self.established = True
        return self.sid

    def seen_now(self):
        self.last_seen = iso.TimePoint.from_now_utc()

    def age(self):
        return iso.TimePoint.from_now_utc().get_unixtime() - \
            self.last_seen.get_unixtime()


def session_decorator(page_method):
    """Decorates a web method with session handling

    page_method
        An unbound method with signature: page_method(obj, context)
        which performs the WSGI protocol and returns the page
        generator.

    Our decorator just calls :meth:`SessionContext.session_wrapper`."""

    def method_call(self, context):
        # There's a smarter way to do this but this is easier to read
        # and understand I think...
        return self.session_wrapper(context, lambda x: page_method(self, x))
        # for more info see:
        # http://stackoverflow.com/questions/1015307/python-bind-an-unbound-method

    return method_call


class SessionContext(WSGIContext):

    """Extends the base class with a session object."""

    def __init__(self, environ, start_response, canonical_root=None):
        WSGIContext.__init__(self, environ, start_response, canonical_root)
        #: a session object, or None if no session available
        self.session = None
        self.session_cookie = None

    def start_response(self):
        """Saves the session cookie."""
        if self.session_cookie:
            # update the browser cookie
            self.add_header('Set-Cookie', str(self.session_cookie))
        return super(SessionContext, self).start_response()


class SessionApp(WSGIDataApp):

    """Extends WSGIDataApp to include session handling.

    These sessions require support for cookies. The SessionApp class
    itself uses two cookies purely for session tracking.

    The key 'SessionApp' is reserved for settings defined by this
    class in the settings file. The defined settings are:

    timeout (600)
        The number of seconds after which an inactive session will time
        out and no longer be accessible to the client.

    cookie ('sid')
        The name of the session cookie.

    cookie_test ('ctest')
        The name of the test cookie.  This cookie is set with a longer
        lifetime and acts both as a test of whether cookies are
        supported or not and can double up as an indicator of whether
        user consent has been obtained for any extended use of cookies.
        It defaults to the value '0', indicating that cookies can be
        stored but that no special consent has been obtained.

    cookie_test_age (8640000)
        The age of the test cookie (in seconds).  The default value is
        equivalent to 100 days.  If you use the test cookie to record
        consent to some cookie policy you should ensure that when you
        set the value you use a reasonable lifespan.

    csrftoken ('csrftoken')
        The name of the form field containing the CSRF token"""

    _session_timeout = None
    _session_cookie = None
    _test_cookie = None

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        """Adds database initialisation"""
        super(SessionApp, cls).setup(options, args, **kwargs)
        settings = cls.settings.setdefault('SessionApp', {})
        cls._session_timeout = settings.setdefault('timeout', 600)
        cls._session_cookie = force_bytes(
            settings.setdefault('cookie', 'sid'))
        cls._test_cookie = force_bytes(
            settings.setdefault('cookie_test', 'ctest'))
        cls.csrf_token = settings.setdefault('crsf_token', 'csrftoken')
        settings.setdefault('cookie_test_age', 8640000)

    @classmethod
    def load_default_metadata(cls):
        mdir = OSFilePath(__file__).abspath().split()[0]
        metadata_file = mdir.join('wsgi_metadata.xml').abspath()
        metadata = edmx.Document()
        with metadata_file.open('rb') as f:
            metadata.read(f)
        return metadata

    #: The name of our CSRF token
    csrf_token = None

    #: Extended context class
    ContextClass = SessionContext

    #: The session class to use, must be (derived from) :class:`Session`
    SessionClass = CookieSession

    def init_dispatcher(self):
        """Adds pre-defined pages for this application

        These pages are mapped to /ctest and /wlaunch.  These names are
        not currently configurable.  See :meth:`ctest` and
        :meth:`wlaunch` for more information."""
        WSGIApp.init_dispatcher(self)
        self.set_method('/ctest', self.ctest)
        self.set_method('/wlaunch', self.wlaunch)

    def session_wrapper(self, context, page_method):
        """Called by the session_decorator

        Uses :meth:`set_session` to ensure the context has a session
        object.  If this request is a POST then the form is parsed and
        the CSRF token checked for validity."""
        if context.session is None:
            cookies = context.get_cookies()
            csrf_match = ""
            s_signed = cookies.get(self._session_cookie, b'').decode('ascii')
            self.set_session(context)
            if context.environ['REQUEST_METHOD'].upper() == 'POST':
                # check the CSRF token
                if s_signed:
                    try:
                        s_msg = self.app_cipher.check_signature(s_signed)
                        csrf_match = self.SessionClass(
                            s_msg.decode('utf-8')).sid
                    except ValueError:
                        # we'll warn about this in a moment anyway
                        pass
                token = context.get_form_string(self.csrf_token)
                # we accept a token even if the session expired but this
                # form is unlikely to do much with a new session.  The
                # point is we compare to the cookie received and not the
                # actual session key as this may have changed
                if not token or token != csrf_match:
                    logger.warning(
                        "%s\nSecurity threat intercepted; "
                        "POST token mismatch, possible CSRF attack\n"
                        "cookie=%s; token=%s",
                        context.environ.get('PATH_INFO', ''),
                        csrf_match, token)
                    return self.error_page(context, 403)
        return self.session_page(context, page_method, context.get_url())

    def set_session(self, context):
        """Sets the session object in the context

        The session is read from the session cookie, established and
        marked as being seen now.  If no cookie is found a new session
        is created.  In both cases a cookie header is set to update the
        cookie in the browser."""
        context.session = None
        cookies = context.get_cookies()
        s_signed = cookies.get(self._session_cookie, b'').decode('ascii')
        if s_signed and self._test_cookie in cookies:
            try:
                s_msg = self.app_cipher.check_signature(s_signed)
                context.session = self.SessionClass(s_msg.decode('utf-8'))
                if context.session.established:
                    if context.session.age() > self._session_timeout:
                        context.session = None
                elif context.session.age() > 120:
                    # You have 2 minutes to establish a session
                    context.session = None
                if context.session:
                    # successfully read a session from the cookie this
                    # session can now be established
                    if not context.session.established:
                        self.establish_session(context)
                    context.session.seen_now()
                    self.set_session_cookie(context)
            except ValueError:
                # start a new session
                logger.warning(
                    "%s\nSecurity threat intercepted; "
                    "session tampering detected\n"
                    "cookie=%s",
                    context.environ.get('PATH_INFO', ''),
                    s_signed)
                pass
        if context.session is None:
            context.session = self.SessionClass()
            self.set_session_cookie(context)

    def set_session_cookie(self, context):
        """Adds the session cookie to the response headers

        The cookie is bound to the path returned by
        :meth:`WSGIContext.get_app_root` and is marked as being
        http_only and is marked secure if we have been accessed through
        an https URL.

        You won't normally have to call this method but you may want to
        override it if your application wishes to override the cookie
        settings."""
        root = context.get_app_root()
        msg = to_text(context.session).encode('utf-8')
        context.session_cookie = cookie.Section4Cookie(
            self._session_cookie,
            self.app_cipher.ascii_sign(msg).encode('ascii'),
            path=str(root.abs_path), http_only=True,
            secure=root.scheme.lower() == 'https')

    def clear_session_cookie(self, context):
        """Removes the session cookie"""
        root = context.get_app_root()
        context.session_cookie = cookie.Section4Cookie(
            self._session_cookie,
            b'', path=str(root.abs_path), http_only=True,
            secure=root.scheme.lower() == 'https', max_age=0)

    def set_test_cookie(self, context, value="0"):
        """Adds the test cookie"""
        c = cookie.Section4Cookie(
            self._test_cookie, value,
            path=str(context.get_app_root().abs_path),
            max_age=self.settings['SessionApp']['cookie_test_age'])
        context.add_header('Set-Cookie', str(c))

    def establish_session(self, context):
        """Mark the session as established

        This will update the session ID, override this method to update
        any data store accordingly if you are already associating
        protected information with the session to prevent it becoming
        orphaned."""
        context.session.establish()

    def merge_session(self, context, merge_session):
        """Merges a session into the session in the context

        Override this method to update any data store.  If you are
        already associating protected information with merge_session you
        need to transfer it to the context session.

        The default implementation does nothing and merge_session is
        simply discarded."""
        pass

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
            not established yet and a redirect to the test page needs to
            be implemented.

        This method is only called *after* the session has been created,
        in other words, context.session must be a valid session.

        This method either calls the page_method (after ensuring that
        the session is established) or initiates a redirection sequence
        which culminates in a request to return_path."""
        # has the user been here before?
        cookies = context.get_cookies()
        if self._test_cookie not in cookies:
            # no they haven't, set a cookie and redirect
            c = cookie.Section4Cookie(
                self._test_cookie, "0",
                path=str(context.get_app_root().abs_path),
                max_age=self.settings['SessionApp']['cookie_test_age'])
            context.add_header('Set-Cookie', str(c))
            # add in the User-Agent and return path to the signature
            # when in the query to help prevent an open redirect
            # (strength in depth - first line of defence)
            return_path_str = str(return_path)
            s = to_text(context.session)
            msg = s + return_path_str + context.environ.get(
                'HTTP_USER_AGENT', '')
            sig = self.app_cipher.sign(msg.encode('utf-8'))
            query = urlencode(
                {'return': return_path_str, 's': s, 'sig': sig})
            ctest = URI.from_octets('ctest?' + query).resolve(
                context.get_app_root())
            return self.redirect_page(context, ctest)
        return page_method(context)

    def ctest(self, context):
        """The cookie test handler

        This page takes three query parameters:

        return
            The return URL the user originally requested

        s
            The session that should be received in a cookie

        sig
            The session signature which includes the the User-Agent at
            the end of the message.

        framed (optional)
            An optional parameter, if present and equal to '1' it means
            we've already attempted to load the page in a new window so
            if we still can't read cookies we'll return the
            :meth:`cfail_page`.

        If cookies cannot be read back from the context this page will
        call the :meth:`ctest_page` to provide an opportunity to open
        the application in a new window (or :meth:`cfail_page` if this
        possibility has already been exhausted.

        If cookies are successfully read, they are compared with the
        expected values (from the query) and the user is returned to the
        return URL with an automatic redirect.  The return URL must be
        within the same application (to prevent 'open redirect' issues)
        and, to be extra safe, we change the user-visible session ID as
        we've exposed the previous value in the URL which makes it more
        liable to snooping."""
        cookies = context.get_cookies()
        logger.debug("cookies: %s", repr(cookies))
        query = context.get_query()
        logger.debug("query: %s", repr(query))
        if 'return' not in query or 's' not in query or 'sig' not in query:
            # missing required parameters
            return self.error_page(context, 400)
        qmsg = query['s']
        qsig = query['sig']
        return_path = query['return']
        if self._test_cookie not in cookies:
            # cookies are blocked
            if query.get('framed', '0') == '1':
                # we've been through the wlaunch sequence already
                # just fail
                return self.cfail_page(context)
            wlaunch = URI.from_octets('wlaunch').resolve(
                context.get_app_root())
            return self.ctest_page(
                context, str(wlaunch), return_path, qmsg, qsig)
        ua = context.environ.get('HTTP_USER_AGENT', '')
        try:
            self.app_cipher.check_signature(
                qsig, (qmsg + return_path + ua).encode('utf-8'))
            qsession = self.SessionClass(qmsg)
            if qsession.established:
                raise ValueError
        except ValueError:
            logger.warning("%s\nSecurity threat intercepted in ctest; "
                           "query tampering detected\n"
                           "s=%s; sig=%s;\nUserAgent: %s",
                           context.environ.get('PATH_INFO', ''),
                           qmsg, qsig, ua)
            self.clear_session_cookie(context)
            return self.error_page(context, 400)
        cmsg_signed = cookies.get(
            self._session_cookie, b'MISSING').decode('ascii')
        try:
            cmsg = self.app_cipher.check_signature(cmsg_signed)
            csession = self.SessionClass(cmsg.decode('utf-8'))
            if csession.established:
                raise ValueError
        except ValueError:
            logger.warning("%s\nSecurity threat intercepted in ctest; "
                           "cookie tampering detected\n"
                           "cookie=%s\nUserAgent: %s",
                           context.environ.get('PATH_INFO', ''),
                           cmsg, ua)
            self.clear_session_cookie(context)
            return self.error_page(context, 400)
        if csession.sid != qsession.sid or csession.established:
            # we got a cookie, but not the one we expected.  Possible
            # foul play so kill the session.  Established sessions must
            # never make it to this page as they've been exposed in the
            # URL.
            logger.warning("%s\nSecurity threat intercepted in ctest; "
                           "session mismatch, possible fixation attack\n"
                           "cookie=%s; query=%s",
                           context.environ.get('PATH_INFO', ''),
                           cmsg, qmsg)
            self.clear_session_cookie(context)
            return self.error_page(context, 400)
        if not self.check_redirect(context, return_path):
            self.clear_session_cookie(context)
            return self.error_page(context, 400)
        # we have matching session ids and the redirect checks out, we
        # now load the session from the cookie for real.  This repeats
        # the validity check but also adds the session timeout checks.
        # This will result in an established session or, if the test
        # page sequence was too slow, a new session that will be
        # established when the return_path calls set_session.
        self.set_session(context)
        return self.redirect_page(context, return_path)

    def ctest_page(self, context, target_url, return_url, s, sig):
        """Returns the cookie test page

        Called when cookies are blocked (perhaps in a frame).

        context
            The request context

        target_url
            A string containing the base link to the wlaunch page.  This
            page can opened in a new window (which may get around the
            cookie restrictions).  You must pass the return_url and the
            sid values as the 'return' and 'sid' query parameters
            respectively.

        return_url
            A string containing the URL the user originally requested,
            and the location they should be returned to when the session
            is established.

        s
            The session

        sig
            The session signature

        You may want to override this implementation to provide a more
        sophisticated page.  The default simply presents the target_url
        with added "return", "s" and "sig" parameters as a simple
        hypertext link that will open in a new window.

        A more sophisticated application might render a button or a form
        but bear in mind that browsers that cause this page to load are
        likely to prevent automated ways of opening this link."""
        query = urlencode({'return': return_url, 's': s, 'sig': sig})
        target_url = str(target_url) + '?' + query
        data = """<html>
    <head><title>Cookie Test Page</title></head>
    <body>
    <p>Cookie test failed: try opening in a <a href=%s
    target="_blank" id="wlaunch">new window</a></p></body>
</html>""" % xml.escape_char_data7(str(target_url), True)
        context.set_status(200)
        return self.html_response(context, data)

    def wlaunch(self, context):
        """Handles redirection to a new window

        The query parameters must contain:

        return
            The return URL the user originally requested

        s
            The session that should also be received in a cookie

        sig
            The signature of the session, return URL and User-Agent

        This page initiates the redirect sequence again, but this time
        setting the framed query parameter to prevent infinite
        redirection loops."""
        cookies = context.get_cookies()
        logger.debug("cookies: %s", repr(cookies))
        query = context.get_query()
        if 'return' not in query or 's' not in query or 'sig' not in query:
            # missing required parameters
            return self.error_page(context, 400)
        logger.debug("query: %s", repr(query))
        qmsg = query['s']
        qsig = query['sig']
        return_path = query['return']
        ua = context.environ.get('HTTP_USER_AGENT', '')
        # load the session from the query initially
        try:
            self.app_cipher.check_signature(
                qsig, (qmsg + return_path + ua).encode('utf-8'))
            qsession = self.SessionClass(qmsg)
            if qsession.established:
                raise ValueError
        except ValueError:
            logger.warning("%s\nSecurity threat intercepted in wlaunch; "
                           "query tampering detected\n"
                           "s=%s; sig=%s;\nUserAgent: %s",
                           context.environ.get('PATH_INFO', ''),
                           qmsg, qsig, ua)
            self.clear_session_cookie(context)
            return self.error_page(context, 400)
        if not self.check_redirect(context, return_path):
            return self.error_page(context, 400)
        if self._test_cookie not in cookies:
            # no cookies, either the user has never been here before or
            # cookies are blocked completely, reuse the unestablished
            # session from the query and go back to the test page
            context.session = qsession
            self.set_session_cookie(context)
            self.set_test_cookie(context)
            query = urlencode(
                {'return': return_path, 's': qmsg, 'sig': qsig,
                 'framed': '1'})
            ctest = URI.from_octets('ctest?' + query).resolve(
                context.get_app_root())
            return self.redirect_page(context, ctest)
        # so cookies were blocked in the frame but now we're in a new
        # window, suddenly, they appear.  Merge our new session into the
        # old one if the old one was already established
        self.set_session(context)
        # merge qsession into the one found in the older cookie (no need
        # to establish it)
        self.merge_session(context, qsession)
        return self.redirect_page(context, return_path)

    def cfail_page(self, context):
        """Called when cookies are blocked completely.

        The default simply returns a plain text message stating that
        cookies are blocked.  You may want to include a page here with
        information about how to enable cookies, a link to the privacy
        policy for your application to help people make an informed
        decision to turn on cookies, etc."""
        context.set_status(200)
        data = b"Page load failed: blocked cookies"
        context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [data]

    def check_redirect(self, context, target_path):
        """Checks a target path for an open redirect

        target_path
            A string or :class:`~pyslet.rfc2396.URI` instance.

        Returns True if the redirect is *safe*.

        The test ensures that the canonical root of our application
        matches the canonical root of the target.  In other words, it
        must have the same scheme and matching authority (host/port)."""
        if target_path:
            if not isinstance(target_path, URI):
                target_path = URI.from_octets(target_path)
            if (target_path.get_canonical_root() !=
                    context.get_app_root().get_canonical_root()):
                # catch the open redirect here, nice try!
                logger.warning("%s\nSecurity threat intercepted; "
                               "external redirect, possible phishing attack\n"
                               "requested redirect to %s",
                               str(context.get_url()), str(target_path))
                return False
            else:
                return True
        else:
            return False
