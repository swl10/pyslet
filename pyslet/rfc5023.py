#! /usr/bin/env python
"""Implements the Atom Publishing Protocol defined in RFC 5023

References:

IRIs [RFC3987]; cf URI [RFC3986]
Before an IRI in a document is used by HTTP, the IRI is first converted to a
URI according to the procedure defined in Section 3.1 of [RFC3987]

xml:base attribute [W3C.REC-xmlbase-20010627]
xml:lang attribute [W3C.REC-xml-20040204], Section 2.12
"""

import sys
import io
import traceback

from . import pep8
from . import rfc2396 as uri
from . import rfc4287 as atom
from .http import client as http
from .py2 import (
    byte,
    byte_value,
    character,
    is_text,
    SortableMixin,
    to_text,
    uempty,
    UnicodeMixin)
from .xml import structures as xml
from .xml import namespace as xmlns


#: The namespace to use for Atom Publishing Protocol elements
APP_NAMESPACE = "http://www.w3.org/2007/app"
#: The mime type for service documents
ATOMSVC_MIMETYPE = "application/atomsvc+xml"
#: The mime type for category documents
ATOMCAT_MIMETYPE = "application/atomcat+xml"

APP_MIMETYPES = {
    ATOMSVC_MIMETYPE: True,
    ATOMCAT_MIMETYPE: True,
    atom.ATOM_MIMETYPE: True
}


def parse_yes_no(src):
    return src.strip().lower() == 'yes'


def format_yes_no(value):
    if value:
        return 'yes'
    else:
        return 'no'


class APPElement(xmlns.XMLNSElement):

    """Base class for all APP elements.

    All APP elements can have xml:base, xml:lang and/or xml:space attributes.
    These are handled by the base
    :py:class:`~pyslet.xml.structures.Element` base class."""
    pass


class Accept(APPElement):

    """Represents the accept element."""
    XMLNAME = (APP_NAMESPACE, 'accept')


class Categories(APPElement):

    """The root of a Category Document.

    A category document is a document that describes the categories
    allowed in a collection."""
    XMLNAME = (APP_NAMESPACE, 'categories')

    XMLATTR_href = ('href', uri.URI.from_octets, str)
    XMLATTR_fixed = ('fixed', parse_yes_no, format_yes_no)
    XMLATTR_scheme = 'scheme'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        APPElement.__init__(self, parent)
        self.href = None
        #: an optional :py:class:`~pyslet.rfc2396.URI` to the category
        self.fixed = None
        #: indicates whether the list of categories is a fixed set. By
        #: default they're open.
        self.scheme = None
        #: identifies the default scheme for categories defined by this
        #: element
        self.Category = []
        #: the list of categories, instances of
        #: :py:class:~pyslet.rfc4287.Category

    def get_children(self):  # noqa
        for child in self.Category:
            yield child
        for child in APPElement.get_children(self):
            yield child


class Service(APPElement):

    """The container for service information

    Associated with one or more Workspaces."""
    XMLNAME = (APP_NAMESPACE, 'service')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        APPElement.__init__(self, parent)
        self.Workspace = []		#: a list of :py:class:`Workspace` instances

    def get_children(self):  # noqa
        for child in APPElement.get_children(self):
            yield child
        for child in self.Workspace:
            yield child


class Workspace(APPElement):

    """Workspaces are server-defined groups of Collections."""
    XMLNAME = (APP_NAMESPACE, 'workspace')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        APPElement.__init__(self, parent)
        self.Title = None			#: the title of this workspace
        self.Collection = []		#: a list of :py:class:`Collection`

    def get_children(self):  # noqa
        for child in APPElement.get_children(self):
            yield child
        if self.Title:
            yield self.Title
        for child in self.Collection:
            yield child


class Collection(APPElement):

    """Describes a collection (feed)."""
    XMLNAME = (APP_NAMESPACE, 'collection')
    XMLCONTENT = xml.ElementContent

    XMLATTR_href = ('href', uri.URI.from_octets, str)

    def __init__(self, parent):
        APPElement.__init__(self, parent)
        self.href = None
        #: the URI of the collection (feed)
        self.Title = None
        #: the human readable title of the collection
        self.Accept = []
        #: list of :py:class:`Accept` media ranges that can be posted to
        #: the collection
        self.Categories = []
        # : list of :py:class:`Categories` that can be applied to
        # : members of the collection

    def get_children(self):  # noqa
        for child in APPElement.get_children(self):
            yield child
        if self.Title:
            yield self.Title
        for child in self.Accept:
            yield child
        for child in self.Categories:
            yield child

    @pep8.old_method('GetFeedURL')
    def get_feed_url(self):
        """Returns a fully resolved URL for the collection (feed)."""
        return self.resolve_uri(self.href)


class Document(atom.AtomDocument):

    """Class for working with APP documents.

    This call can represent both APP and Atom documents."""
    classMap = {}

    def __init__(self, **args):
        atom.AtomDocument.__init__(self, **args)
        self.defaultNS = APP_NAMESPACE

    def ValidateMimeType(self, mimetype):   # noqa
        """Checks *mimetype* against the APP or Atom specifications."""
        return (mimetype in APP_MIMETYPES or
                atom.AtomDocument.ValidateMimeType(self, mimetype))

    @classmethod
    def get_element_class(cls, name):
        """Returns the APP or Atom class used to represent name.

        Overrides
        :py:meth:`~pyslet.rfc4287.AtomDocument.get_element_class` when the
        namespace is :py:data:`APP_NAMESPACE`."""
        if name[0] == APP_NAMESPACE:
            return cls.classMap.get(
                name, atom.AtomDocument.classMap.get((name[0], None),
                                                     APPElement))
        else:
            return atom.AtomDocument.get_element_class(name)

xmlns.map_class_elements(Document.classMap, globals())


class Slug(UnicodeMixin, SortableMixin):

    """Represents an HTTP slug header value.

    slug
            The opaque slug as a unicode string

    The built-in str function can be used to format instances according
    to the grammar defined in the specification.

    Instances must be treated as immutable, they define comparison
    methods and a hash implementation to allow them to be used as keys
    in dictionaries."""

    def __init__(self, slug):
        self.slug = slug		#: the slug value

    @classmethod
    def from_str(cls, source):
        """Creates a slug from a *source* string."""
        return cls(uri.unescape_data(source).decode('utf-8'))

    escape_byte = byte('%')

    def __unicode__(self):
        result = []
        for c in self.slug.encode('utf-8'):
            cv = byte_value(c)
            if c == self.escape_byte or cv < 0x20 or cv > 0x7E:
                result.append("%%%02X" % cv)
            else:
                result.append(character(c))
        return uempty.join(result)

    def __repr__(self):
        return "Slug(%s)" % repr(self.slug)

    def sortkey(self):
        return self.slug

    def otherkey(self, other):
        if is_text(other):
            other = self.from_str(other)
        if isinstance(other, self.__class__):
            return other.sortkey()
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.slug)


class Client(http.Client):

    def __init__(self, **kwargs):
        http.Client.__init__(self, **kwargs)

    def queue_request(self, request, timeout=60):
        # if there is no Accept header, add one
        if not request.has_header('Accept'):
            request.set_header('Accept', ','.join(
                (atom.ATOM_MIMETYPE, ATOMSVC_MIMETYPE, ATOMCAT_MIMETYPE)),
                True)
        super(Client, self).queue_request(request, timeout)


class Server(pep8.PEP8Compatibility):

    def __init__(self, service_root='http://localhost/', **kwargs):
        pep8.PEP8Compatibility.__init__(self)
        service_root = kwargs.get('serviceRoot', service_root)
        if not isinstance(service_root, uri.URI):
            #: the canonical URL of the service root
            self.service_root = \
                uri.URI.from_octets(service_root).canonicalize()
        else:
            self.service_root = service_root.canonicalize()
        #: the :py:class:`Service` instance that describes this service.
        self.serviceDoc = Document(root=Service, base_uri=self.service_root)
        self.service = self.serviceDoc.root
        # make the base explicit in the document
        self.service.set_base(str(self.service_root))
        #: set this to True to expose python tracebacks in 500
        #: responses, defaults to False
        self.debugMode = False

    def __call__(self, environ, start_response):
        """wsgi interface for calling instances of this Atom server object.

        We add an additional optional parameter *response_headers*"""
        response_headers = []
        if environ['SCRIPT_NAME'] + environ['PATH_INFO'] == \
                self.service_root.abs_path:
            data = to_text(self.serviceDoc).encode('utf-8')
            response_headers.append(("Content-Type", ATOMSVC_MIMETYPE))
            response_headers.append(("Content-Length", str(len(data))))
            start_response("200 Ok", response_headers)
            return [data]
        else:
            return self.HandleMissing(environ, start_response)

    def handle_missing(self, environ, start_response):
        response_headers = []
        data = "This server supports the Atom Publishing Protocol\r\n"\
            "For service information see: %s" % str(self.service_root)
        response_headers.append(("Content-Length", str(len(data))))
        response_headers.append(("Content-Type", 'text/plain'))
        start_response("404 Not found", response_headers)
        return [data]

    def handle_error(self, environ, start_response, code=500):
        """Designed to be called by an otherwise uncaught exception.

        Generates a 500 response by default."""
        response_headers = []
        cdata = io.BytesIO()
        if self.debugMode:
            traceback.print_exception(*sys.exc_info(), file=cdata)
        else:
            cdata.write("Sorry, there was an internal error "
                        "while processing this request")
        response_headers.append(("Content-Type", 'text/plain'))
        response_headers.append(("Content-Length", str(len(cdata.getvalue()))))
        start_response("%i Unexpected error" % code, response_headers)
        return [cdata.getvalue()]
