#! /usr/bin/env python

import logging

from . import metadata as csdlxml
from . import model as csdl
from .errors import (
    ODataError,
    ServiceError,
    URLError,
    )
from .payload import Payload
from .service import (
    DataRequest,
    DataService,
    )

from ..http import client as http
from ..http.params import (
    HTTPURL,
    )
from ..py2 import (
    is_text,
    to_text,
    u8,
    )
from ..rfc2396 import (
    escape_data,
    unescape_data,
    URI,
    )
from ..xml.structures import XMLEntity


BOM = u8(b'\xef\xbb\xbf')


class ClientError(ODataError):

    """Base class for all client-specific exceptions."""
    pass


class UnexpectedHTTPResponse(ServiceError):

    """The server returned an unexpected response code, typically a 500
    internal server error.  The error message contains details of the
    error response returned."""
    pass


class ODataURL(object):

    """Represents an OData URL"""

    def __init__(self):
        #: the service root of this URL, an encoded URL string
        self.service_root = "/"
        #: the resource path, an array of decoded text strings
        self.resource_path = []
        #: the query options, a dictionary mapping text -> text strings
        self.query_options = {}
        #: the fragment
        self.fragment = None

    def __str__(self):
        url = self.service_root + "/".join(
            escape_data(p) for p in self.resource_path)
        if self.query_options:
            url = url + "?" + "&".join(
                escape_data(n) + "=" + escape_data(v)
                for n, v in self.query_options.items())
        if self.fragment:
            url = url + '#' + self.fragment
        return url

    @classmethod
    def from_str(cls, src):
        try:
            split = src.index(":")
        except ValueError:
            raise URLError("Service root must end in '/' (%s)" % src)
        scheme = src[:split]
        rest = src[split + 1:]
        split = rest.find("?")
        if split < 0:
            # no query
            query = ""
            split = rest.find("#")
            if split < 0:
                # no fragment
                fragment = ""
                hpart = rest
            else:
                hpart = rest[:split]
                fragment = rest[split + 1:]

        else:
            hpart = rest[:split]
            rest = rest[split + 1:]
            split = rest.find("#")
            if split < 0:
                fragment = ""
                query = rest
            else:
                query = rest[:split]
                fragment = rest[split + 1:]
        if hpart.startswith("//"):
            # authority is present
            path = hpart[2:].split("/")
            if len(path) < 2:
                raise URLError("Service root must end in '/' (%s)" % src)
            authority = "//" + path[0]
        else:
            authority = ""
            path = hpart.split("/")
            if len(path) < 2:
                raise URLError("Service root must end in '/' (%s)" % src)
        path = path[1:]
        url = cls()
        url.service_root = scheme + ':' + authority + '/'
        url.resource_path = [unescape_data(p).decode('utf-8') for p in path]
        url.fragment = fragment
        # second stage, split the query
        if query:
            options = query.split('&')
            for nv in options:
                split = nv.find('=')
                if split < 0:
                    name = nv
                    value = ""
                else:
                    name = nv[:split]
                    value = nv[split + 1:]
                url.query_options[unescape_data(name).decode('utf-8')] = \
                    unescape_data(value).decode('utf-8')
        return url


class Client(DataService):

    """An OData client

    This class implements the OData protocol providing a concrete
    implementation of the class:`service.DataService` class for
    accessing data via the http-based OData protocol.

    The constructor takes an optional svc_root parameter that, if
    provided, will be used to call :meth:`load_service` immediately."""

    def __init__(self, svc_root=None):
        super(Client, self).__init__()
        #: the http client to use for requests
        self.http = http.Client()
        #: the service root URL
        self.svc_root = None
        if svc_root is not None:
            self.load_service(svc_root)

    def load_service(self, svc_root, metadata=None):
        """Loads the service document

        This must be done before you can use the client create
        any requests.

        svc_root
             A string or :class:`pyslet.rfc2396.URI` instance pointing
             at the service root (redirections are followed so the
             actual service root used for subsequent requests may
             differ).  This may be the URI of a local file but the file
             MUST define the actual service root of the remote service
             using http or https.

        metadata (optional)
            A string, :class:`pyslet.rfc2396.URI` instance or a
            :class:`pyslet.vfs.VirtualFilePath` instance that will be
            used to load the service metadata instead of loading the
            metadata from the URL defined by the protocol."""
        if is_text(svc_root):
            svc_root = URI.from_octets(svc_root)
        if isinstance(svc_root, HTTPURL):
            # load in the service root
            request = http.ClientRequest(str(svc_root))
            # request.set_header('Accept', 'application/atomsvc+xml')
            self.http.process_request(request)
            if request.status != 200:
                raise UnexpectedHTTPResponse(
                    "Failed to load service document",
                    request.status, request.response.reason)
            # the request may have been redirected so read back
            # the service root from the request
            self.svc_root = request.url
            self.context_base = URI.from_octets(
                '$metadata').resolve(self.svc_root)
            if is_text(metadata):
                metadata = URI.from_octets(metadata)
            if isinstance(metadata, URI) and not metadata.is_absolute():
                metadata = metadata.resolve(self.svc_root)
            if metadata is None:
                metadata = self.context_base
            self.load_metadata(metadata)
            payload = Payload.from_message(
                request.url, request.response, self)
            payload.obj_from_bytes(self.model, request.res_body)

    def load_metadata(self, metadata=None):
        """Loads the service metadata

        metadata
            A :class:`pyslet.rfc2396.URI` instance or a
            :class:`pyslet.vfs.VirtualFilePath` instance that will be
            used to load the service metadata instead of the default
            location.

        The true location of the metadata document is always considered
        to be <service root>$metadata (the service root always ends in
        '/') so the base URI of the metadata document is set accordingly
        even if the metadata parameter points to a different location."""
        doc = csdlxml.CSDLDocument(
            base_uri=self.context_base, reqManager=self.http)
        if metadata is None:
            metadata = self.context_base
        if isinstance(metadata, URI):
            request = http.ClientRequest(str(metadata))
            self.http.process_request(request)
            if request.status != 200:
                raise UnexpectedHTTPResponse(
                    "Failed to load service metadata",
                    request.status, request.response.reason)
            ftype = request.response.get_content_type()
            logging.info("Service metadata format: %s", str(ftype))
            doc.read_from_entity(
                XMLEntity(src=request.response, encoding="utf-8"))
        else:
            raise NotImplementedError
        if isinstance(doc.root, csdlxml.Edmx):
            self.model = doc.root.entity_model
            self.container = self.model.get_container()
            self.metadata = doc

    def resolve_type(self, type_url):
        """Returns a type definition from an odata.type URL"""
        # express this relative to our context
        if type_url.fragment:
            # if this is a simple identifier we have a built-in
            # primitive type
            if csdl.NameTable.is_simple_identifier(type_url.fragment):
                # ignore the actual URL
                return self.model["Edm"].get(type_url.fragment, None)
            else:
                qname, collection = csdlxml.type_name_from_str(
                    type_url.fragment)
                type_context = str(type_url).split('#')[0]
                if type_context == self.context_base:
                    type_def = self.model.qualified_get(qname)
                    if collection:
                        return csdl.CollectionType(type_def)
                    else:
                        return type_def
                else:
                    raise NotImplemented("Cross-service type references")
        else:
            raise ServiceError("Invalid odata.type: %s" % str(type_url))

    def get_item_count(
            self, collection, filter=None, params=None, search=None):
        """Creates a request for the number of items in a collection"""
        request = CountRequest(self, collection)
        request.set_filter(filter)
        request.set_params(params)
        return request

    def get_entity_collection(
            self, entity_set, filter=None, params=None, orderby=None,
            top=None, skip=None, count=None, search=None):
        request = IterateRequest(self, entity_set)
        request.set_filter(filter)
        request.set_params(params)
        return request


class ClientDataRequest(DataRequest):

    """Represents a request to an OData service"""

    def __init__(self, client, target):
        super(ClientDataRequest, self).__init__(client, target)
        #: the OData url (split into components) we're using
        self.url = None
        #: the HTTP request we'll use to execute this request
        self.http_request = None

    def execute_request(self, track_changes=None, callback=None):
        if track_changes is not None or callback is not None:
            raise NotImplementedError
        if self.http_request is None:
            self.create_request()
        self.service.http.process_request(self.http_request)
        self.set_response()

    def create_request(self):
        """Creates an HTTP request object for this request"""
        raise NotImplementedError

    def set_response(self):
        """Reads the HTTP response for this request"""
        raise NotImplementedError


class CountRequest(ClientDataRequest):

    def create_request(self):
        self.url = ODataURL.from_str(to_text(self.target.get_url()))
        # target is an addressable Collection
        self.url.resource_path.append("$count")
        # add in any specified query options...
        if self.filter is not None:
            self.request_url.query_options["$filter"] = to_text(filter)
        # add in custom parameters
        if self.params:
            for name, value in self.params:
                self.request_url.query_options[name] = value
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        ftype = self.http_request.response.get_content_type()
        if ftype.type == "text" and ftype.subtype == "plain":
            try:
                charset = ftype["charset"].lower()
            except KeyError:
                charset = "utf_8_sig"
            text_data = self.http_request.res_body.decode(charset)
            # now read a primitive value
            p = csdl.ODataParser(text_data)
            v = p.require_int64_value()
            p.require_end()
            self.result = v.value


class IterateRequest(ClientDataRequest):

    def create_request(self):
        # target is an entity set
        self.url = ODataURL.from_str(to_text(self.target.get_url()))
        # add in any specified query options...
        if self.filter is not None:
            self.request_url.query_options["$filter"] = to_text(filter)
        # add in custom parameters
        if self.params:
            for name, value in self.params:
                self.request_url.query_options[name] = value
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        payload = Payload.from_message(
            self.http_request.url, self.http_request.response, self.service)
        self.result = payload.obj_from_bytes(
            self.target, self.http_request.res_body)
        # was there a next link?
        next_link = self.result.annotations.qualified_get("odata.nextLink")
        if next_link is not None:
            self.next_request = IterateRequest(self.service, self.target)
            self.next_request.url = self.url
            self.next_request.http_request = http.ClientRequest(
                str(next_link.value))
