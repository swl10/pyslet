#! /usr/bin/env python


from . import errors
from . import model as csdl
from . import parser
from . import types

from ..py2 import (
    to_text,
    )
from ..rfc2396 import (
    escape_data,
    unescape_data,
    URI,
    )
from ..unicode5 import ParserError


class DataService(object):

    """Represents a Data service

    The service is the object used to make requests using the protocol
    documented in OData Part 1.  The OData specification binds the
    protocol to HTTP to make a RESTful web service but this class
    represents only the abstract protocol allowing it to be bound to a
    wider range of data services.  Concrete implementations are provided
    for mapping the service to HTTP (as per the specification) and
    SQL-based database servers.

    In most cases you won't need to call the DataService methods
    directly as the objects defined by the model will make the
    appropriate calls to read and write data as they are used.  You can
    discover the exposed entity sets through the :attr:`container` and
    use them directly to initiate requests.  The exceptions to this are
    when you want to use advanced features of the protocol such as batch
    requests or asynchronous execution."""

    def __init__(self):
        #: the entity model exposed by this service
        self.model = None
        #: the entity container exposed by this service
        self.container = None
        self.conventional_ids = True
        """Whether or not entity IDs are formed conventionally

        A value of True means that we will calculate entity IDs by
        appending key-predicates to entity set names.  Strictly speaking
        this setting should default to False as the specification states:

            Services are strongly encouraged to use the canonical URL
            for an entity as defined in OData-URL as its entity-id, but
            clients cannot assume...

        Oh but we do assume I'm afraid!  It goes on...

            Services that use the standard URL conventions for
            entity-ids annotate their entity container with the term
            Core.ConventionalIDs

        In our defence, the word MUST is not used (*cannot* is merely
        guidance) so we don't treat this as a requirement.  Services
        don't seem to use this annotation in practice, despite following
        the conventions, but if they do provide an annotation value we
        abide by it."""
        self.dereferenceable_ids = True
        """Whether or not entity IDs can be used as read/edit URLs

        A value of True means that we will use entity ids directly as if
        they were edit (or read) URLs.  An explicitly defined edit/read
        URL in the payload will still override this behaviour but if
        we've calculated an ID for an entity without ever having
        received it from the service (see :attr:`conventional_ids`) then
        we are as good as saying that entity IDs, read and edit URLs are
        all identical and calculable from the entity set name and key
        value.

        We default to True as most services do following the URL
        conventions even though the following clause suggests that False
        would be the correct default:

            clients cannot assume the entity-id can be used to locate
            the entity unless the Core.DereferenceableIDs term is
            applied to the entity container

        Again, we honour the annotation's value if it is present.  A
        value of False means we will use the $entity service end-point
        to retrieve entities passing the entity ID in the $id query
        parameter instead of just using the ID as the entity's URL
        directly"""
        #: the metadata document URL (the base for all contexts)
        self.context_base = None
        self._service_canonical_root = ""
        self._service_root_path = []
        #: the URL of the service root *as a character string*
        self.service_root = "/"
        self._entity_url = None
        #: the metadata document associated with this service, a
        #: :class:`metadata.CSDLDocument` instance.
        self.metadata = None
        #: a DataService instance that allows the protocol to be used to
        #: query to this service's entity model
        self.metadata_service = None

    def set_context_base(self, url):
        """Sets the context_base URL for this service

        url
            A :class:`pyslet.rfc2396.URI` instance representing the
            context base for this service, i.e., the URL of the
            $metadata document.

        This method also sets the :attr:`service_root` attribute."""
        self.context_base = url
        # calculate the service root information
        self._service_canonical_root = url.get_canonical_root()
        path = url.abs_path.split("/")
        self._service_root_path = [
            # ignore the leading / and the trailing $metadata
            unescape_data(p).decode('utf-8') for p in path[1:-1]]
        r = list(escape_data(p.encode('utf-8'))
                 for p in self._service_root_path)
        r.insert(0, str(self._service_canonical_root))
        r.append("")
        self.service_root = "/".join(r)

    def set_container(self, container):
        self.container = container
        # look for interesting annotations
        tag = self.container.annotations.qualified_get(
            "Org.OData.Core.V1.DereferenceableIDs")
        if tag and tag.value:
            self.dereferenceable_ids = tag.value.get_value()
        tag = self.container.annotations.qualified_get(
            "Org.OData.Core.V1.ConventionalIDs")
        if tag and tag.value:
            # we have a tag with a non-null value
            self.conventional_ids = tag.value.get_value()

    def root_url(self):
        """Creates an OData URL representing the service root"""
        return ODataURL(self)

    def url_from_str(self, src):
        """Creates an OData URL from a character src string

        src
            A character string representing the *encoded* URL."""
        try:
            split = src.index(":")
        except ValueError:
            raise errors.URLError("Service root must end in '/' (%s)" % src)
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
                raise errors.URLError(
                    "Service root must end in '/' (%s)" % src)
            authority = "//" + path[0]
        else:
            authority = ""
            path = hpart.split("/")
            if len(path) < 2:
                raise errors.URLError(
                    "Service root must end in '/' (%s)" % src)
        canonical_root = URI.from_octets(
            scheme + ':' + authority).get_canonical_root()
        if self._service_canonical_root and \
                self._service_canonical_root != canonical_root:
            raise errors.URLError("URL path is not in service canonical root")
        path = [unescape_data(p).decode('utf-8') for p in path[1:]]
        if self._service_root_path:
            i = 0
            while i < len(self._service_root_path):
                if i >= len(path) or self._service_root_path[i] != path[i]:
                    raise errors.URLError("URL path is not in service root")
                i += 1
            path = path[len(self._service_root_path):]
        url = ODataURL(self)
        url.set_resource_path(path)
        url.set_fragment(fragment)
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
                url.set_query_option(
                    unescape_data(name).decode('utf-8'),
                    unescape_data(value).decode('utf-8'))
        return url

    def open(self, name):
        """Opens an item advertised by this service

        The return type depends on the type of the item being exposed.
        For an EntitySet the return type is an
        :class:`model.EntitySetValue` object, for a Singleton the return
        type is an :class:`model.Entity`.

        The returned objects are bound to this service and all data
        access operations are performed using the methods defined by the
        service."""
        item = self.container[name]
        return item.open()

    def get_entity_by_key(
            self, entity_set_value, key, select=None, expand=None):
        """Creates a request to get an entity by key

        entity_set_value
            An EntitySetValue object bound to this service.  This can be
            an entity set exposed by the service in the container or an
            entity collection obtained through navigation.

        key
            The key of the desired entity.  The key is used to look up
            the entity in the entity set.

        Returns a :class:`DataRequest` instance.  When executed, the
        result of of the request is an entity object or an appropriate
        exception."""
        raise NotImplementedError

    def get_entity(self, entity, select=None, expand=None):
        """Creates a request to retrieve an existing entity

        entity
            An entity value object previously returned by the service.

        The entity is reloaded (according to any select/expand options).
        This form of request may also be used in cases where the entity
        object has been returned with no properties (an entity
        reference).  It will load the selected properties allowing the
        values to be accessed.

        Returns a :class:`DataRequest` instance.  When executed, the
        result of the request is the original entity object updated with
        the current values of the requested properties."""
        raise NotImplementedError

    def get_entity_as_type(
            self, entity, entity_type, select=None, expand=None):
        """Creates a request to an existing entity

        entity
            An entity value object previously returned by the service,
            typically this objet will have no property values and be an
            entity reference only.

        entity_type
            An EntityType object representing the type of entity to
            return.
        """
        raise NotImplementedError

    def get_entity_ref(self, entity):
        """Creates a request to get the reference to an existing entity."""
        raise NotImplementedError

    def get_entity_media(self, entity):
        """Creates a request to an entity's media stream

        entity
            An entity object previously returned by the service. The
            entity must be of a type that has a media stream.

        Returns a :class:`DataRequest` instance."""
        raise NotImplementedError

    def get_property(self, entity, path):
        """Creates a request for an individual property

        entity
            The entity object that contains the property

        path
            The path to the property being requested as an iterable
            list of strings.

        Returns a :class:`DataRequest` instance.  When executed, the
        result is an instance of the appropriate value object, this
        value is also used to update the original entity instance."""
        raise NotImplementedError

    def get_property_value(self, entity, path):
        """Creates a request for an individual property value

        entity
            The entity object that contains the property

        path
            The path to the property being requested as an iterable
            list of strings.

        Returns a :class:`DataRequest` instance.  When executed, the
        result is the appropriate Python 'native' object as described in
        the model.  This value is also used to update the property of
        the original entity instance."""
        raise NotImplementedError

    def get_entity_collection(
            self, entity_set, filter=None, params=None, orderby=None,
            top=None, skip=None, count=None, search=None):
        """Creates a request for a collection of entities

        entity_set
            An EntitySetValue object bound to this service."""
        raise NotImplementedError

    def get_entityref_collection(
            self, entity_set, filter=None, params=None, orderby=None,
            top=None, skip=None, count=None, search=None):
        """Creates a request for a collection of entity references"""
        raise NotImplementedError

    def get_item_count(
            self, collection, filter=None, params=None, search=None):
        """Creates a request for the number of items in a collection"""
        raise NotImplementedError

    def create_entity(self, entity_collection, entity):
        raise NotImplementedError

    def update_entity(self, entity, merge=True):
        raise NotImplementedError

    def upsert_entity(self, entity, merge=True):
        #: entity may not exist
        raise NotImplementedError

    def delete_entity(self, entity):
        raise NotImplementedError

    def add_entity_ref(self, entity_collection, entity):
        raise NotImplementedError

    def remove_entity_ref(self, entity_collection, entity):
        raise NotImplementedError

    def set_entity_ref(self, entity_ref):
        raise NotImplementedError

    def delete_entity_ref(self, entity_ref):
        raise NotImplementedError

    def create_media_entity(self, entity_collection, sinfo, s):
        raise NotImplementedError

    def update_media_entity_stream(self, entity, sinfo, s):
        raise NotImplementedError

    # delete_media_entity is the same as delete_entity

    def update_stream_property(self, entity, path, sinfo, s):
        raise NotImplementedError

    def delete_stream_property(self, entity, path):
        raise NotImplementedError

    def update_property(self, entity, path, value):
        raise NotImplementedError

    def update_property_value(self, entity, path, value):
        raise NotImplementedError

    def delete_property(self, entity, path):
        raise NotImplementedError

    def update_complex_property(self, entity, path, value, merge=True):
        raise NotImplementedError

    def new_batch(self):
        """Creates a new batch request"""
        raise NotImplementedError

    def new_change_set(self):
        """Creates a new changeset request"""
        raise NotImplementedError

    # concurrency: match: etag or any; no-match: etag or any
    # isolation: snapshots?


class DataRequest(object):

    """Represents a request to the Data service

    This is an abstract class.  Concrete implementations of a data
    service will use their own derived classes to bind each request to a
    particular protocol.  For example, the OData client extends this
    class to hold information about the HTTP message that will be sent
    to the server when the request is executed.

    You create DataRequest instances using the appropriate method of the
    DataService."""

    def __init__(self, service, target):
        #: the service that created this request
        self.service = service
        #: the target of the request
        self.target = target
        #: the result of the request (type is request specific).  If the
        #: the request failed the result will be an instance of
        #: :class:`ServiceError`
        self.result = None
        #: if the result is a partial result then next_request is a data
        #: service request suitable for retrieving the next part of the
        #: result
        self.next_request = None
        #: optional search criteria
        self.search = None
        #: optional filter expression
        self.filter = None
        #: optional count request
        self.count = None
        #: optional orderby expression
        self.orderby = None
        #: optional skip number
        self.skip = None
        #: optional top number
        self.top = None
        #: optional expand expression
        self.expand = None
        #: optional select expression
        self.select = None
        #: optional custom parameters
        self.params = {}

    def set_filter(self, filter=None):
        """Adds or removes a filter to this request"""
        if filter is not None:
            raise NotImplementedError

    def set_params(self, params=None):
        """Adds custom parameters to this request"""
        if params is not None:
            raise NotImplementedError

    def execute_request(self, track_changes=None, callback=None):
        """Executes a previously created request"""
        raise NotImplementedError

    def terminate_request(self):
        """Cancels a request previously executed aynchronously (i.e.,
        using a callback)."""
        raise NotImplementedError

    def get_value_url(self, value, edit=False):
        """Calculates the read or edit link of a value

        We follow the guidance in Part 1; 4.2 when determining the link
        for a property of an entity.  For entity sets we use the URLs
        returned in the service document.  For entities we use follow
        the annotation conventions in JSON 4.5.8; other payload types
        ensure they generate the appropriate annotations during
        deserialization."""
        url = None
        if value.parent:
            # this is a named property of an entity or structured type
            p = value.parent()
            if p is None:
                raise errors.ServiceError("Value has expired")
            path = [value.name]
            if value.name not in p.base_def:
                # tricky, need the navigation property declaration
                # which requires a look-up in the parent's type
                path.insert(0, p.type_def[value.name].nametable().qname)
            entity = p.get_entity(path)
            url = self.get_value_url(entity, edit=edit)
            for seg in path:
                url.add_path_segment(seg)
        elif isinstance(value, csdl.EntitySetValue) and value.entity_set:
            # this is just an entity set read/edit url in service doc
            url = self.service.url_from_str(
                to_text(value.entity_set.get_url()))
        elif isinstance(value, csdl.EntityValue):
            if not edit:
                # check for an explicit readLink
                read_link = value.annotations.qualified_get("odata.readLink")
                if read_link and not read_link.value.is_null():
                    url = self.service.url_from_str(
                        to_text(read_link.value.get_value()))
            if not url:
                edit_link = value.annotations.qualified_get("odata.editLink")
                if edit_link and not edit_link.value.is_null():
                    url = self.service.url_from_str(
                        to_text(edit_link.value.get_value()))
            if not url:
                # default is the entity-id with a cast if required
                id = value.annotations.qualified_get("odata.id")
                if id:
                    if id.value.is_null():
                        # transient entity!
                        raise errors.ServiceError(
                            "Can't read or edit a transient entity")
                    url = self.service.url_from_str(
                        to_text(id.value.get_value()))
                    if value.entity_set.entity_type is not value.type_def:
                        url.add_path_segment(value.type_def.qname)
            if not url and value.entity_set:
                # if there is no id then we must have all the key fields
                # AND the url is just the canonical url
                url = self.service.url_from_str(
                    to_text(value.entity_set.get_url()))
                key = value.type_def.get_key_dict(value.get_key())
                url.add_key_predicate(key)
            else:
                raise errors.ServiceError("Can't read or edit unbound entity")
        else:
            raise errors.ServiceError("Can't calculate target URL")
        return url


class ChangeSet(DataRequest):

    """Represents a change set

    A change set is a group of DataRequest instances that will be
    invoked as an atomic group."""
    pass


class BatchRequest(DataRequest):

    """Represents a batch

    A batch is a group of DataRequest instances that will be invoked
    as a group."""
    pass


class RequestExpired(errors.ServiceError):

    """Raised when a request that has expired is executed"""

    def __init__(self, message=None):
        super(errors.ServiceError, self).__init__(message, 410, "Gone")


class EntityNotFound(errors.ServiceError):

    """Raised when the requested entity does not exist or is null"""

    def __init__(self, message=None):
        super(errors.ServiceError, self).__init__(message, 404, "Not Found")


class NotAMediaStream(errors.ServiceError):

    """Raised when the requested entity is not a media stream but the
    request requires one."""

    def __init__(self, message=None):
        super(errors.ServiceError, self).__init__(message, 400, "Bad Request")


class PropertyNotAvailable(errors.ServiceError):

    """Raised when the requested property value is not available, for
    example due to permissions."""

    def __init__(self, message=None):
        super(errors.ServiceError, self).__init__(message, 404, "Not Found")


class ResourcePathSegment(object):

    """Object representing a single resource path segment

    There are two attributes.  The name attribute contains one of a
    string (containing a simple identifier or $special name) or a
    :class:`csdl.QualifiedName` instance.

    The params attribute contains a dictionary that maps strings (simple
    identifier parameter names) on to :class:`csdl.Value` instances or
    strings representing parameter aliases (starting '@').  In the
    special case of a key with a single property value the empty string
    is used as the dictionary key."""

    def __init__(self):
        self.name = None
        self.params = {}


class ODataURL(object):

    """Represents an OData URL"""

    def __init__(self, service):
        #: the context (EntityModel) that defines the service
        self.service = service
        #: the resource path, an array of decoded text strings
        self.resource_path = []
        #: the resource path as an array of ResourcePathSegment instances
        self.resource_path_segments = []
        #: the query options, a dictionary mapping text -> text strings
        self.query_options = {}
        #: the property options represented in the query
        self.p_options = types.PropertyOptions()
        #: the fragment
        self.fragment = None

    def __str__(self):
        url = self.service.service_root + "/".join(
            escape_data(p) for p in self.resource_path)
        if self.query_options:
            url = url + "?" + "&".join(
                escape_data(n) + "=" + escape_data(v)
                for n, v in self.query_options.items())
        if self.fragment:
            url = url + '#' + self.fragment
        return url

    def set_resource_path(self, path):
        """Set the resource path from a list

        The list elements are either decoded character strings
        representing the individual segments *or* they are
        :class:`ResourcePathSegment` instances representing interpreted
        path segments."""
        self.resource_path = []
        self.resource_path_segments = []
        for seg in path:
            self.add_path_segment(seg)

    def add_path_segment(self, segment):
        """Adds a resource path segment

        segment
            Either a decoded character string *or* a
            :class:`ResourcePathSegment` instance representing an
            interpreted path segment."""
        if isinstance(segment, ResourcePathSegment):
            seg_str = str(segment)
            seg_obj = segment
        else:
            try:
                seg_obj = self.path_segment_from_str(segment)
            except ParserError as err:
                raise errors.URLError(to_text(err))
            seg_str = segment
        self.resource_path.append(seg_str)
        self.resource_path_segments.append(seg_obj)

    def add_key_predicate(self, key_dict):
        """Adds a key predicate to the last segment in the resource path"""
        index = len(self.resource_path_segments) - 1
        seg = self.resource_path_segments[index]
        if seg.params:
            raise errors.URLError("URL already has a key predicate")
        seg.params = key_dict
        # update the formatted version of this segment
        if len(key_dict) > 1:
            kp_str = "(%s)" % ",".join(
                "%s=%s" % (n, v.literal_string()) for n, v in key_dict)
        else:
            kp_str = "(%s)" % key_dict[""].literal_string()
        self.resource_path[index] += kp_str

    def set_query_option(self, name, value):
        """Set a query option from a decoded name/value pair"""
        if name == '$select':
            p = parser.Parser(value)
            select = p.require_select()
            p.require_end()
            self.p_options.select = select
        self.query_options[name] = value

    def set_fragment(self, fragment):
        """Set the fragment from an *encoded* character string"""
        self.fragment = fragment

    def path_segment_from_str(self, segment):
        """Returns a decoded resource path segment

        index
            Integer index of the path segment

        Returns a :class:`ResourcePathSegment` instance."""
        result = ResourcePathSegment()
        p = parser.Parser(segment)
        if p.parse("$"):
            # special name
            result.name = "$" + p.require_odata_identifier()
            p.require_end()
            return result
        result.name = p.parse_production(p.require_qualified_name)
        if result.name is None:
            result.name = p.require_odata_identifier()
        if p.parse("("):
            # parse the parameters
            while True:
                # start with name=value
                save_pos = p.pos
                pname = p.parse_production(p.require_odata_identifier)
                if pname and p.parse("="):
                    if p.parse("@"):
                        pvalue = "@" + p.require_odata_identifier()
                    else:
                        pvalue = p.require_primitive_literal()
                    result.params[pname] = pvalue
                    if not p.parse(","):
                        break
                else:
                    # a primitive_literal may look like a key or
                    # function parameter name, e.g., key property
                    # stupidly named "null" or "inf"
                    p.setpos(save_pos)
                    pvalue = p.require_primitive_literal()
                    result.params[""] = pvalue
                    break
            p.require(")")
            p.require_end()
        return result
