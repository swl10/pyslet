#! /usr/bin/env python

import logging

from . import (
    data,
    errors,
    metadata as csdlxml,
    model as csdl,
    parser,
    )
from .payload import Payload
from .service import (
    DataRequest,
    DataService,
    ODataURL
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
    URI,
    )
from ..xml.structures import XMLEntity


BOM = u8(b'\xef\xbb\xbf')


class ClientError(errors.ODataError):

    """Base class for all client-specific exceptions."""
    pass


class UnexpectedHTTPResponse(errors.ServiceError):

    """The server returned an unexpected response code, typically a 500
    internal server error.  The error message contains details of the
    error response returned."""
    pass


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
            self.set_context_base(
                URI.from_octets('$metadata').resolve(self.svc_root))
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
            self.set_container(self.model.get_container())
            self.metadata = doc

    def get_entity_collection(self, entity_set, next_link=None):
        """Creates a request to get a collection of entities"""
        request = IterateEntitiesRequest(self, entity_set, url=next_link)
        return request

    def get_singleton(self, singleton):
        """Creates a request for an entity singleton"""
        request = SingletonRequest(self, singleton)
        return request

    def get_entity_by_key(self, entity_set, key):
        """Creates a request to get an entity by key"""
        request = EntityByKeyRequest(self, (entity_set, key))
        return request

    def get_entity(self, entity):
        """Creates a request to get an entity (reload)"""
        request = EntityRequest(self, entity)
        return request

    def get_collection(self, collection, next_link=None):
        """Creates a request to get a general collection"""
        request = IterateRequest(self, collection, url=next_link)
        return request

    def get_item_count(self, collection):
        """Creates a request for the number of items in a collection"""
        request = CountRequest(self, collection)
        return request

    def get_property(self, pvalue):
        """Creates a request for an individual property"""
        request = PropertyRequest(self, pvalue)
        return request

    def create_entity(self, entity_collection, entity, omit_clean=False):
        """Create a request to create an entity in a collection"""
        request = InsertEntityRequest(self, (entity_collection, entity))
        request.omit_clean = omit_clean
        return request

    def update_entity(self, entity, merge=True):
        """Create a request to update an entity"""
        if merge:
            request = PatchEntityRequest(self, entity)
        else:
            raise NotImplementedError
        return request

    def delete_entity_by_key(self, entity_set, key):
        """Deletes an entity from an entity set"""
        request = DeleteByKeyRequest(self, (entity_set, key))
        return request

    def delete_entity(self, entity):
        """Create a request to delete an entity"""
        request = DeleteEntityRequest(self, entity)
        return request

    def call_function(self, function):
        """Creates a request for an unbound function call"""
        request = FunctionCallRequest(self, function)
        return request

    def call_action(self, action):
        """Creates a request for an unbound function call"""
        request = ActionCallRequest(self, action)
        return request


class ClientDataRequest(DataRequest):

    """Represents a request to an OData service"""

    def __init__(self, client, target, url=None):
        super(ClientDataRequest, self).__init__(client, target)
        #: the OData url (split into components) we're using
        self.url = url
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
        self.url = self.service.get_value_url(self.target)
        if self.target.item_type is not self.target.type_def.item_type:
            # add a type_cast segment to the URL
            self.url.add_path_segment(self.target.item_type.qname)
        self.url.add_path_segment("$count")
        # add in any specified query options...
        if self.target.options:
            self.url.add_filter(self.target.options.filter)
            self.url.add_search(self.target.options.search)
            self.url.add_orderby(self.target.options.orderby)
        # add in custom parameters
        if self.params:
            for name, value in self.params:
                self.url.query_options[name] = value
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
            p = parser.Parser(text_data)
            v = p.require_int64_value()
            p.require_end()
            self.result = v


class IterateEntitiesRequest(ClientDataRequest):

    def create_request(self):
        # target is an entity set value
        if self.url is None:
            self.url = self.service.get_value_url(self.target)
            if self.target.item_type is not self.target.type_def.item_type:
                # add a type_cast segment to the URL
                self.url.add_path_segment(self.target.item_type.qname)
            # add in any specified query options...
            # TODO: add all collection options to the URL in one go...
            if self.target.options:
                self.url.set_select(self.target.options.select)
                self.url.set_expand(self.target.options.expand)
                self.url.add_skip(self.target.options.skip)
                self.url.add_top(self.target.options.top)
                self.url.add_filter(self.target.options.filter)
                self.url.add_search(self.target.options.search)
                self.url.add_orderby(self.target.options.orderby)
            # add in custom parameters
            if self.params:
                for name, value in self.params:
                    self.url.query_options[name] = value
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        payload = Payload.from_message(
            self.http_request.url, self.http_request.response, self.service)
        payload.obj_from_bytes(self.target, self.http_request.res_body)


class SingletonRequest(ClientDataRequest):

    def create_request(self):
        # target is a singleton value
        self.url = self.service.get_value_url(self.target)
        if self.target.item_type is not self.target.type_def.item_type:
            # add a type_cast segment to the URL
            self.url.add_path_segment(self.target.item_type.qname)
        # add in any specified query options...
        if self.target.options:
            self.url.set_select(self.target.options.select)
            self.url.set_expand(self.target.options.expand)
        # add in custom parameters
        if self.params:
            for name, value in self.params:
                self.url.query_options[name] = value
        self.entity = self.target.new_item()
        self.entity.bind_to_service(self.service)
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status == 204:
            # relationship terminates on a single entity but none is
            # related: No content
            self.result = None
        elif self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
        else:
            payload = Payload.from_message(
                self.http_request.url, self.http_request.response,
                self.service)
            payload.obj_from_bytes(self.entity, self.http_request.res_body)
            self.result = self.entity


class EntityByKeyRequest(ClientDataRequest):

    def create_request(self):
        # target is a tuple of entity set and key
        target_set, target_key = self.target
        entity_type = target_set.item_type
        key = entity_type.get_key_dict(target_key)
        if self.service.indexable_by_key(target_set) and \
                (target_set.options is None or
                 target_set.options.filter is None):
            # we are bound to an entity set (even if we are actually a
            # navigation property) that is indexable by key so we will
            # just use the key-predicate form of index look-up note that:
            # People('steve')?$filter=UserName eq 'dave'
            # is not allowed in OData v4 so if a filter is in force we
            # will convert this to (TODO):
            # People?$filter=UserName eq 'steve' and UserName eq 'dave'
            self.url = self.service.get_value_url(target_set)
            if entity_type is not target_set.type_def.item_type:
                self.url.add_path_segment(target_set.item_type.qname)
            self.url.add_key_predicate(key)
            if target_set.options:
                self.url.set_select(target_set.options.select)
                self.url.set_expand(target_set.options.expand)
        elif not self.service.conventional_ids or target_set.name or \
                not (target_set.options is None or
                     target_set.options.filter is None):
            # Problem #1: we don't know the id of the entity or we
            # are indexing a navigation property or otherwise filtered
            # entity set, turn the key dictionary into a filter and
            # filter the entity set, it's the only way
            raise NotImplementedError("Entity by key without conventional IDs")
        else:
            id = self.service.get_value_url(target_set)
            id.add_key_predicate(key)
            if self.service.derefenceable_ids:
                self.url = id
            else:
                # Problem #2: we don't know the read URL so we need to use the
                # $entity endpoint to resolve this as if it were an entity
                # reference...
                self.url = self.service.root_url()
                self.url.add_path_segment("$entity")
                self.url.add_query_option("$id", to_text(id))
            self.url.set_select(target_set.options.select)
            self.url.set_expand(target_set.options.expand)
        self.entity = target_set.new_item()
        self.entity.bind_to_service(self.service)
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status == 404:
            self.result = errors.ServiceError(
                "Entity does not exist", 404,
                self.http_request.response.reason)
            return
        elif self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        payload = Payload.from_message(
            self.http_request.url, self.http_request.response, self.service)
        payload.obj_from_bytes(self.entity, self.http_request.res_body)
        self.result = self.entity


class DeleteByKeyRequest(ClientDataRequest):

    def create_request(self):
        # target is a tuple of entity set and key
        target_set, target_key = self.target
        entity_type = target_set.item_type
        key = entity_type.get_key_dict(target_key)
        id = None
        if self.service.indexable_by_key(target_set):
            # we are bound to an entity set (even if we are actually a
            # navigation property) that is indexable by key so we will
            # just use the key-predicate to get the entity reference
            # using the set we're bound to
            id = self.service.url_from_str(
                to_text(target_set.entity_binding.get_url()))
            id.add_key_predicate(key)
        if target_set.parent is not None:
            # we're a navigation property
            parent = target_set.parent()
            np = parent.type_def[target_set.name]
            if np.containment:
                if self.service.conventional_ids:
                    id = self.service.get_value_url(target_set)
                    id.add_key_predicate(key)
                    self.url = id
            elif id:
                # navigation property, not contained
                # just delete the reference
                self.url = self.service.get_value_url(target_set)
                self.url.set_id(id)
        else:
            # delete this entity from it's owning entity set
            self.url = id
        if not self.url:
            raise errors.ODataError("Can't resolve entity reference")
        self.http_request = http.ClientRequest(str(self.url), method="DELETE")

    def set_response(self):
        if self.http_request.status == 404:
            self.result = errors.ServiceError(
                "Entity does not exist", 404,
                self.http_request.response.reason)
            return
        elif self.http_request.status in (412, 428):
            self.result = errors.OptimisticConcurrencyError()
        elif self.http_request.status != 204:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        else:
            self.result = None


class PropertyRequest(ClientDataRequest):

    def create_request(self):
        # target is a property value (primitive or complex)
        self.url = self.service.get_value_url(self.target)
        # add in any specified query options...
        # you can't add select to a complex property
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        payload = Payload.from_message(
            self.http_request.url, self.http_request.response, self.service)
        payload.obj_from_bytes(self.target, self.http_request.res_body)
        self.result = self.target


class IterateRequest(ClientDataRequest):

    def create_request(self):
        # target is a collection
        if self.url is None:
            self.url = self.service.get_value_url(self.target)
            if self.target.item_type is not self.target.type_def.item_type:
                # add a type_cast segment to the URL
                self.url.add_path_segment(self.target.item_type.qname)
            # add in any specified query options...
            # TODO: add all collection options to the URL in one go...
            if self.target.options:
                self.url.add_skip(self.target.options.skip)
                self.url.add_top(self.target.options.top)
                self.url.add_filter(self.target.options.filter)
                self.url.add_search(self.target.options.search)
                self.url.add_orderby(self.target.options.orderby)
            # add in custom parameters
            if self.params:
                for name, value in self.params:
                    self.url.query_options[name] = value
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        if self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        payload = Payload.from_message(
            self.http_request.url, self.http_request.response, self.service)
        payload.obj_from_bytes(self.target, self.http_request.res_body)


class InsertEntityRequest(ClientDataRequest):

    def __init__(self, *args, **kwargs):
        super(InsertEntityRequest, self).__init__(*args, **kwargs)
        self.omit_clean = False

    def create_request(self):
        # target is an entity set (or collection) and an entity
        target_collection, entity = self.target
        self.url = self.service.get_value_url(target_collection)
        payload = Payload(self)
        # create the payload to POST
        jbytes = payload.to_json(
            entity, type_def=target_collection.type_def.item_type,
            patch=self.omit_clean)
        jbytes = jbytes.getvalue()
        self.http_request = http.ClientRequest(
            str(self.url), "POST", entity_body=jbytes)
        self.http_request.set_content_type(payload.get_media_type())
        self.http_request.set_header("Prefer", "return=representation")

    def set_response(self):
        entity = self.target[1]
        # we want to receive maximum information back from the service
        # so remove any narrow selection
        entity.select_default()
        if self.http_request.status == 204:
            # TODO: no content returned, use Location header to set id
            # and decipher key if available
            self.result = entity
        elif self.http_request.status == 201:
            # should have a representation in the response
            if self.http_request.res_body:
                payload = Payload.from_message(
                    self.http_request.url, self.http_request.response,
                    self.service)
                payload.obj_from_bytes(entity, self.http_request.res_body)
            self.result = entity
        else:
            self.result = UnexpectedHTTPResponse(
                "Failed to insert entity",
                self.http_request.status, self.http_request.response.reason)


class EntityRequest(ClientDataRequest):

    def create_request(self):
        # target is an entity value
        self.url = self.service.get_value_url(self.target, edit=True)
        self.http_request = http.ClientRequest(str(self.url), "GET")

    def set_response(self):
        if self.http_request.status == 404:
            self.result = errors.ServiceError(
                "Entity does not exist", 404,
                self.http_request.response.reason)
            return
        elif self.http_request.status != 200:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        payload = Payload.from_message(
            self.http_request.url, self.http_request.response, self.service)
        payload.obj_from_bytes(self.target, self.http_request.res_body)
        self.result = self.target


class PatchEntityRequest(ClientDataRequest):

    def create_request(self):
        # target is an entity value
        self.url = self.service.get_value_url(self.target, edit=True)
        payload = Payload(self)
        # create the payload for PATCH, suppress the odata.type
        jbytes = payload.to_json(
            self.target, type_def=self.target.type_def, patch=True)
        jbytes = jbytes.getvalue()
        self.http_request = http.ClientRequest(
            str(self.url), "PATCH", entity_body=jbytes)
        self.http_request.set_content_type(payload.get_media_type())
        odata_etag = self.target.get_annotation("@odata.etag")
        if odata_etag:
            # add an If-Match header
            self.http_request.set_header(
                "If-Match", odata_etag.get_value())

    def set_response(self):
        if self.http_request.status in (412, 428):
            self.result = errors.OptimisticConcurrencyError()
        elif self.http_request.status < 200 or self.http_request.status >= 400:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
        else:
            self.result = None
            self.target.rclean()
            # remove any etag after a successful patch and clean
            self.target.remove_updatable_annotation("@odata.etag")


class DeleteEntityRequest(ClientDataRequest):

    def create_request(self):
        # target is an entity value
        self.url = self.service.get_value_url(self.target, edit=True)
        self.http_request = http.ClientRequest(
            str(self.url), "DELETE")
        odata_etag = self.target.get_annotation("@odata.etag")
        if odata_etag:
            # add an If-Match header
            self.http_request.set_header(
                "If-Match", odata_etag.get_value())

    def set_response(self):
        if self.http_request.status == 404:
            self.result = errors.ServiceError(
                "Entity does not exist", 404,
                self.http_request.response.reason)
            return
        elif self.http_request.status in (412, 428):
            self.result = errors.OptimisticConcurrencyError()
        elif self.http_request.status != 204:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url),
                self.http_request.status, self.http_request.response.reason)
            return
        else:
            self.result = None


class FunctionCallRequest(ClientDataRequest):

    def create_request(self):
        # target is a CallableValue
        function = self.target
        if isinstance(function.binding, csdl.FunctionImport):
            # unbound call, use name of FunctionImport
            self.url = ODataURL(self.service)
            self.url.add_path_segment(function.binding.name)
        else:
            # add this function call to the URL of the binding
            self.url = self.service.get_value_url(function.binding)
            self.url.add_path_segment(function.type_def.qname)
        self.url.add_inline_params(function)
        self.http_request = http.ClientRequest(str(self.url))

    def set_response(self):
        # create a null/empty return value
        function = self.target
        return_value = function.new_return_value()
        collection = isinstance(return_value, data.CollectionValue)
        if self.http_request.status == 204:
            # single-valued function (with a nullable return-type)
            if not collection:
                self.result = UnexpectedHTTPResponse(
                    to_text(self.url), self.http_request.status,
                    self.http_request.response.reason)
            else:
                self.result = return_value
        elif self.http_request.status >= 400:
            # single valued function with a non-nullable return type
            if not collection:
                self.result = None
            else:
                self.result = UnexpectedHTTPResponse(
                    to_text(self.url), self.http_request.status,
                    self.http_request.response.reason)
        elif self.http_request.status == 200:
            # read the result
            if self.http_request.res_body:
                payload = Payload.from_message(
                    self.http_request.url, self.http_request.response,
                    self.service)
                payload.obj_from_bytes(
                    return_value, self.http_request.res_body)
            self.result = return_value
        else:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url), self.http_request.status,
                self.http_request.response.reason)


class ActionCallRequest(ClientDataRequest):

    def create_request(self):
        # target is a CallableValue
        action = self.target
        if isinstance(action.binding, csdl.ActionImport):
            # unbound call, use name of ActionImport
            self.url = ODataURL(self.service)
            self.url.add_path_segment(action.binding.name)
        else:
            # add this action call to the URL of the binding
            self.url = self.service.get_value_url(action.binding)
            self.url.add_path_segment(action.type_def.qname)
        payload = Payload(self)
        # create the payload for POST
        jbytes = payload.to_json(self.target)
        jbytes = jbytes.getvalue()
        self.http_request = http.ClientRequest(
            str(self.url), "POST", entity_body=jbytes)
        self.http_request.set_content_type(payload.get_media_type())

    def set_response(self):
        # create a null/empty return value
        action = self.target
        return_value = action.new_return_value()
        collection = isinstance(return_value, data.CollectionValue)
        if self.http_request.status == 204:
            # nullable or no return value
            if collection:
                self.result = UnexpectedHTTPResponse(
                    to_text(self.url), self.http_request.status,
                    self.http_request.response.reason)
            else:
                self.result = return_value
        elif self.http_request.status == 200:
            # read the result
            if self.http_request.res_body:
                payload = Payload.from_message(
                    self.http_request.url, self.http_request.response,
                    self.service)
                payload.obj_from_bytes(
                    return_value, self.http_request.res_body)
            self.result = return_value
        else:
            self.result = UnexpectedHTTPResponse(
                to_text(self.url), self.http_request.status,
                self.http_request.response.reason)
