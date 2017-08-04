#! /usr/bin/env python

from .errors import (
    ServiceError
    )


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
        #: the metadata document URL (the base for all contexts)
        self.context_base = None
        #: the metadata document associated with this service, a
        #: :class:`metadata.CSDLDocument` instance.
        self.metadata = None
        #: a DataService instance that allows the protocol to be used to
        #: query to this service's entity model
        self.metadata_service = None

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
            self, entity_collection, key, select=None, expand=None):
        """Creates a request to get an entity by key

        entity_collection
            Any entity collection.  This can be an entity set exposed by
            the service in the container or an entity collection
            obtained through navigation.

        key
            The key of the desired entity.  The key is used to look up
            the entity in the entity set.

        Returns a :class:`DataRequest` instance.  When executed, the
        result of of the request is an entity object or an appropriate
        exception."""
        raise NotImplementedError

    def get_entity(self, entity, select=None, expand=None):
        """Creates a request to an existing entity

        entity
            An entity value object previously returned by the service.

        The entity is reloaded (according to any select/expand options).
        This form of request may also be used in cases the entity object
        has been returned with no properties (an entity reference).  It
        will load the properties allowing the values to be accessed.

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


class RequestExpired(ServiceError):

    """Raised when a request that has expired is executed"""

    def __init__(self, message=None):
        super(ServiceError, self).__init__(message, 410, "Gone")


class EntityNotFound(ServiceError):

    """Raised when the requested entity does not exist or is null"""

    def __init__(self, message=None):
        super(ServiceError, self).__init__(message, 404, "Not Found")


class NotAMediaStream(ServiceError):

    """Raised when the requested entity is not a media stream but the
    request requires one."""

    def __init__(self, message=None):
        super(ServiceError, self).__init__(message, 400, "Bad Request")


class PropertyNotAvailable(ServiceError):

    """Raised when the requested property value is not available, for
    example due to permissions."""

    def __init__(self, message=None):
        super(ServiceError, self).__init__(message, 404, "Not Found")
