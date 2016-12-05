#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined
by Microsoft."""

import io
import logging

from . import core
from . import csdl as edm
from . import metadata as edmx
from .. import info
from .. import rfc2396 as uri
from .. import rfc4287 as atom
from .. import rfc5023 as app
from ..http import client as http
from ..http import params
from ..http import messages
from ..pep8 import old_method
from ..py2 import (
    dict_items,
    dict_keys,
    to_text)
from ..xml import structures as xml


class ClientException(Exception):

    """Base class for all client-specific exceptions."""
    pass


class AuthorizationRequired(ClientException):

    """The server returned a response code of 401 to the request."""
    pass


class UnexpectedHTTPResponse(ClientException):

    """The server returned an unexpected response code, typically a 500
    internal server error.  The error message contains details of the
    error response returned."""
    pass


class DataFormatError(ClientException):

    """Invalid or other input that could not be parsed."""
    pass


class ClientCollection(core.EntityCollection):

    def __init__(self, client, base_uri=None, **kwargs):
        super(ClientCollection, self).__init__(**kwargs)
        if base_uri is None:
            self.base_uri = self.entity_set.get_location()
        else:
            self.base_uri = base_uri
        self.client = client

    def set_expand(self, expand, select=None):
        """Sets the expand and select query options for this collection.

        We override this implementation to ensure that the keys are
        always selected in each entity set."""
        self.add_keys(self.entity_set, expand, select)
        self.entity_set.entityType.validate_expansion(expand, select)
        self.expand = expand
        self.select = select

    @classmethod
    def add_keys(cls, entity_set, expand, select):
        if select is None or "*" in select:
            pass
        else:
            # force the keys to be in the selection
            for k in entity_set.keys:
                select[k] = None
        # now we look for anything that is being expanded
        if expand is not None:
            for np, expansion in dict_items(expand):
                if select and np in select:
                    # recurse
                    cls.add_keys(
                        entity_set.get_target(np), expansion, select[np])
                else:
                    # not being expanded
                    pass

    @old_method('RaiseError')
    def raise_error(self, request):
        """Given a :py:class:`pyslet.http.messages.Message` object
        containing an unexpected status in the response, parses an error
        response and raises an error accordingly."""
        if request.status == 404:
            # translates in to a key error
            etype = KeyError
        elif request.status == 405:
            # indicates the URL doesn't support the operation, for example
            # an attempt to POST to a navigation property that the server
            # doesn't support perhaps
            etype = NotImplementedError
        elif request.status == 401:
            etype = AuthorizationRequired
        elif request.status >= 400 and request.status < 500:
            etype = edm.ConstraintError
        else:
            etype = UnexpectedHTTPResponse
        debug_msg = None
        if request.res_body:
            doc = core.Document()
            doc.read(src=request.res_body)
            if isinstance(doc.root, core.Error):
                error_msg = "%s: %s" % (
                    doc.root.Code.get_value(), doc.root.Message.get_value())
                if doc.root.InnerError is not None:
                    debug_msg = doc.root.InnerError.get_value()
            else:
                error_msg = request.response.reason
        else:
            error_msg = request.response.reason
        if etype == KeyError:
            logging.info("404: %s", error_msg)
        else:
            logging.info("%i: %s", request.status, error_msg)
            if debug_msg:
                logging.debug(debug_msg)
        raise etype(error_msg)

    def insert_entity(self, entity):
        if entity.exists:
            raise edm.EntityExists(str(entity.get_location()))
        if self.is_medialink_collection():
            # insert a blank stream and then update
            mle = self.new_stream(src=io.BytesIO(),
                                  sinfo=core.StreamInfo(size=0))
            entity.set_key(mle.key())
            # 2-way merge
            mle.merge(entity)
            entity.merge(mle)
            entity.exists = True
            self.update_entity(entity)
        else:
            doc = core.Document(root=core.Entry(None, entity))
            data = str(doc).encode('utf-8')
            request = http.ClientRequest(
                str(self.base_uri), 'POST', entity_body=data)
            request.set_content_type(
                params.MediaType.from_str(core.ODATA_RELATED_ENTRY_TYPE))
            self.client.process_request(request)
            if request.status == 201:
                # success, read the entity back from the response
                doc = core.Document()
                doc.read(request.res_body)
                entity.exists = True
                doc.root.get_value(entity)
                # so which bindings got handled?  Assume all of them
                for k, dv in entity.navigation_items():
                    dv.bindings = []
            else:
                self.raise_error(request)

    def __len__(self):
        # use $count
        feed_url = self.base_uri
        sys_query_options = {}
        if self.filter is not None:
            sys_query_options[
                core.SystemQueryOption.filter] = to_text(self.filter)
        if sys_query_options:
            feed_url = uri.URI.from_octets(
                str(feed_url) +
                "/$count?" +
                core.ODataURI.format_sys_query_options(sys_query_options))
        else:
            feed_url = uri.URI.from_octets(str(feed_url) + "/$count")
        request = http.ClientRequest(str(feed_url))
        request.set_header('Accept', 'text/plain')
        self.client.process_request(request)
        if request.status == 200:
            return int(request.res_body)
        else:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))

    def entity_generator(self):
        feed_url = self.base_uri
        sys_query_options = {}
        if self.filter is not None:
            sys_query_options[
                core.SystemQueryOption.filter] = to_text(self.filter)
        if self.expand is not None:
            sys_query_options[core.SystemQueryOption.expand] = \
                core.format_expand(self.expand)
        if self.select is not None:
            sys_query_options[core.SystemQueryOption.select] = \
                core.format_select(self.select)
        if self.orderby is not None:
            sys_query_options[
                core.SystemQueryOption.orderby] = \
                core.CommonExpression.OrderByToString(self.orderby)
        if sys_query_options:
            feed_url = uri.URI.from_octets(
                str(feed_url) + "?" +
                core.ODataURI.format_sys_query_options(sys_query_options))
        while True:
            request = http.ClientRequest(str(feed_url))
            request.set_header('Accept', 'application/atom+xml')
            self.client.process_request(request)
            if request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(base_uri=feed_url)
            doc.read(request.res_body)
            if isinstance(doc.root, atom.Feed):
                if len(doc.root.Entry):
                    for e in doc.root.Entry:
                        entity = core.Entity(self.entity_set)
                        entity.exists = True
                        e.get_value(entity)
                        yield entity
                else:
                    break
            else:
                raise core.InvalidFeedDocument(str(feed_url))
            feed_url = None
            for link in doc.root.Link:
                if link.rel == "next":
                    feed_url = link.resolve_uri(link.href)
                    break
            if feed_url is None:
                break

    def itervalues(self):
        return self.entity_generator()

    def set_topmax(self, topmax):
        raise NotImplementedError("OData client can't override topmax")

    def set_page(self, top, skip=0, skiptoken=None):
        self.top = top
        self.skip = skip
        self.skiptoken = skiptoken  # opaque in the client implementation

    def iterpage(self, set_next=False):
        feed_url = self.base_uri
        sys_query_options = {}
        if self.filter is not None:
            sys_query_options[
                core.SystemQueryOption.filter] = to_text(self.filter)
        if self.expand is not None:
            sys_query_options[core.SystemQueryOption.expand] = \
                core.format_expand(self.expand)
        if self.select is not None:
            sys_query_options[core.SystemQueryOption.select] = \
                core.format_select(self.select)
        if self.orderby is not None:
            sys_query_options[core.SystemQueryOption.orderby] = \
                core.CommonExpression.OrderByToString(self.orderby)
        if self.top is not None:
            sys_query_options[core.SystemQueryOption.top] = to_text(self.top)
        if self.skip is not None:
            sys_query_options[core.SystemQueryOption.skip] = to_text(self.skip)
        if self.skiptoken is not None:
            sys_query_options[core.SystemQueryOption.skiptoken] = \
                self.skiptoken
        if sys_query_options:
            feed_url = uri.URI.from_octets(
                str(feed_url) + "?" +
                core.ODataURI.format_sys_query_options(sys_query_options))
        request = http.ClientRequest(str(feed_url))
        request.set_header('Accept', 'application/atom+xml')
        self.client.process_request(request)
        if request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        doc = core.Document(base_uri=feed_url)
        doc.read(request.res_body)
        if isinstance(doc.root, atom.Feed):
            if len(doc.root.Entry):
                for e in doc.root.Entry:
                    entity = core.Entity(self.entity_set)
                    entity.exists = True
                    e.get_value(entity)
                    yield entity
            feed_url = self.nextSkiptoken = None
            for link in doc.root.Link:
                if link.rel == "next":
                    feed_url = link.resolve_uri(link.href)
                    break
            if feed_url is not None:
                # extract the skiptoken from this link
                feed_url = core.ODataURI(feed_url, self.client.path_prefix)
                self.nextSkiptoken = feed_url.sys_query_options.get(
                    core.SystemQueryOption.skiptoken, None)
            if set_next:
                if self.nextSkiptoken is not None:
                    self.skiptoken = self.nextSkiptoken
                    self.skip = None
                elif self.skip is not None:
                    self.skip += len(doc.root.Entry)
                else:
                    self.skip = len(doc.root.Entry)
        else:
            raise core.InvalidFeedDocument(str(feed_url))

    def __getitem__(self, key):
        sys_query_options = {}
        if self.filter is not None:
            sys_query_options[core.SystemQueryOption.filter] = "%s and %s" % (
                core.ODataURI.key_dict_to_query(self.entity_set.key_dict(key)),
                to_text(self.filter))
            entity_url = str(self.base_uri)
        else:
            entity_url = (str(self.base_uri) + core.ODataURI.format_key_dict(
                self.entity_set.get_key_dict(key)))
        if self.expand is not None:
            sys_query_options[core.SystemQueryOption.expand] = \
                core.format_expand(self.expand)
        if self.select is not None:
            sys_query_options[core.SystemQueryOption.select] = \
                core.format_select(self.select)
        if sys_query_options:
            entity_url = uri.URI.from_octets(
                entity_url +
                "?" +
                core.ODataURI.format_sys_query_options(sys_query_options))
        request = http.ClientRequest(str(entity_url))
        if self.filter:
            request.set_header('Accept', 'application/atom+xml')
        else:
            request.set_header('Accept', 'application/atom+xml;type=entry')
        self.client.process_request(request)
        if request.status == 404:
            raise KeyError(key)
        elif request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        doc = core.Document(base_uri=entity_url)
        doc.read(request.res_body)
        if isinstance(doc.root, atom.Entry):
            entity = core.Entity(self.entity_set)
            entity.exists = True
            doc.root.get_value(entity)
            return entity
        elif isinstance(doc.root, atom.Feed):
            nresults = len(doc.root.Entry)
            if nresults == 0:
                raise KeyError(key)
            elif nresults == 1:
                e = doc.root.Entry[0]
                entity = core.Entity(self.entity_set)
                entity.exists = True
                e.get_value(entity)
                return entity
            else:
                raise UnexpectedHTTPResponse("%i entities returned from %s" %
                                             nresults, entity_url)
        elif isinstance(doc.root, core.Error):
            raise KeyError(key)
        else:
            raise core.InvalidEntryDocument(str(entity_url))

    def new_stream(self, src, sinfo=None, key=None):
        """Creates a media resource"""
        if not self.is_medialink_collection():
            raise core.ExpectedMediaLinkCollection
        if sinfo is None:
            sinfo = core.StreamInfo()
        if sinfo.size is not None and sinfo.size == 0:
            src = b''
        request = http.ClientRequest(
            str(self.base_uri), 'POST', entity_body=src)
        request.set_content_type(sinfo.type)
        if sinfo.size is not None:
            request.set_content_length(sinfo.size)
        if sinfo.modified is not None:
            request.set_last_modified(params.FullDate(src=sinfo.modified))
        if isinstance(key, tuple):
            # composite key
            request.set_header(
                "Slug",
                core.ODataURI.format_key_dict(self.entity_set.key_dict(key)))
        else:
            # single string is sent 'as is'
            request.set_header("Slug", str(app.Slug(to_text(key))))
        self.client.process_request(request)
        if request.status == 201:
            # success, read the entity back from the response
            doc = core.Document()
            doc.read(request.res_body)
            entity = self.new_entity()
            entity.exists = True
            doc.root.get_value(entity)
            return entity
        else:
            self.raise_error(request)

    def update_stream(self, src, key, sinfo=None):
        """Updates an existing media resource.

        The parameters are the same as :py:meth:`new_stream` except that
        the key must be present and must be an existing key in the
        collection."""
        if not self.is_medialink_collection():
            raise core.ExpectedMediaLinkCollection
        stream_url = str(self.base_uri) + core.ODataURI.format_key_dict(
            self.entity_set.get_key_dict(key)) + "/$value"
        if sinfo is None:
            sinfo = core.StreamInfo()
        request = http.ClientRequest(stream_url, 'PUT', entity_body=src)
        request.set_content_type(sinfo.type)
        if sinfo.size is not None:
            request.set_content_length(sinfo.size)
        if sinfo.modified is not None:
            request.set_last_modified(params.FullDate(src=sinfo.modified))
        self.client.process_request(request)
        if request.status == 204:
            # success, read the entity back from the response
            return
        else:
            self.raise_error(request)

    def read_stream(self, key, out=None):
        """Reads a media resource"""
        if not self.is_medialink_collection():
            raise core.ExpectedMediaLinkCollection
        stream_url = str(self.base_uri) + core.ODataURI.format_key_dict(
            self.entity_set.get_key_dict(key)) + "/$value"
        if out is None:
            request = http.ClientRequest(stream_url, 'HEAD')
        else:
            request = http.ClientRequest(stream_url, 'GET', res_body=out)
        request.set_accept("*/*")
        self.client.process_request(request)
        if request.status == 200:
            # success, read the entity information back from the response
            sinfo = core.StreamInfo()
            sinfo.type = request.response.get_content_type()
            sinfo.size = request.response.get_content_length()
            sinfo.modified = request.response.get_last_modified()
            sinfo.created = sinfo.modified
            sinfo.md5 = request.response.get_content_md5()
            return sinfo
        elif request.status == 404:
            # sort of success, we return an empty stream
            sinfo = core.StreamInfo()
            sinfo.size = 0
            return sinfo
        else:
            self.raise_error(request)

    def read_stream_close(self, key):
        """Creates a generator for a media resource."""
        if not self.is_medialink_collection():
            raise core.ExpectedMediaLinkCollection
        stream_url = str(self.base_uri) + core.ODataURI.format_key_dict(
            self.entity_set.get_key_dict(key)) + "/$value"
        swrapper = EntityStream(self)
        request = http.ClientRequest(stream_url, 'GET', res_body=swrapper)
        request.set_accept("*/*")
        swrapper.start_request(request)
        return swrapper.sinfo, swrapper.data_gen()


class EntityStream(io.RawIOBase):

    def __init__(self, collection):
        self.collection = collection
        self.request = None
        self.sinfo = None
        self.data = []

    def start_request(self, request):
        self.request = request
        # now loop until we get the first write or until there nothing
        # to do!
        self.collection.client.queue_request(self.request)
        while self.collection.client.thread_task():
            if self.data:
                if self.request.response.status == 200:
                    break
                else:
                    # discard data received before the response status
                    logging.debug("EntityStream discarding data... %i",
                                  sum(len(x) for x in self.data))
                    self.data = []
        if self.request.response.status == 200:
            self.sinfo = core.StreamInfo()
            self.sinfo.type = request.response.get_content_type()
            self.sinfo.size = request.response.get_content_length()
            self.sinfo.modified = request.response.get_last_modified()
            self.sinfo.created = self.sinfo.modified
            self.sinfo.md5 = request.response.get_content_md5()
        elif self.request.status == 404:
            # sort of success, we return an empty stream
            self.sinfo = core.StreamInfo()
            self.sinfo.size = 0
        else:
            # unexpected HTTP response
            self.collection.raise_error(self.request)

    def data_gen(self):
        """Generates the data written to the stream.

        Rather than call process_request which would spool all the data
        into the stream before returning, we split apart the individual
        calls to handle the request to enable us to yield data as soon
        as it is available without needing the full stream in memory."""
        yield_data = (self.request.response.status == 200)
        while self.data or self.collection.client.thread_task():
            for chunk in self.data:
                if chunk:
                    logging.debug("EntityStream: writing %i bytes", len(chunk))
                    if yield_data:
                        yield chunk
            self.data = []
        # that's all the data consumed, request is finished
        self.collection.close()

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def write(self, b):
        if not isinstance(b, bytes):
            raise TypeError("write requires bytes, not %s" % repr(type(b)))
        if b:
            logging.debug("EntityStream: reading %i bytes", len(b))
            self.data.append(b)
        return len(b)


class EntityCollection(ClientCollection, core.EntityCollection):

    """An entity collection that provides access to entities stored
    remotely and accessed through *client*."""

    def update_entity(self, entity, merge=True):
        if not entity.exists:
            raise edm.NonExistentEntity(str(entity.get_location()))
        doc = core.Document(root=core.Entry)
        if entity.selected is None:
            # a merge with all properties selected is a replace
            merge = False
        doc.root.set_value(entity, True)
        data = str(doc).encode('utf-8')
        request = http.ClientRequest(
            str(entity.get_location()), 'MERGE' if merge else 'PUT',
            entity_body=data)
        request.set_content_type(
            params.MediaType.from_str(core.ODATA_RELATED_ENTRY_TYPE))
        self.client.process_request(request)
        if request.status == 204:
            # success, nothing to read back but we're not done
            # we've only updated links to existing entities on properties with
            # single cardinality
            for k, dv in entity.navigation_items():
                if not dv.bindings or dv.isCollection:
                    continue
                # we need to know the location of the target entity set
                binding = dv.bindings[-1]
                if isinstance(binding, edm.Entity) and binding.exists:
                    dv.bindings = []
            # now use the default method to finish the job
            self.update_bindings(entity)
            return
        else:
            self.raise_error(request)

    def __delitem__(self, key):
        entity = self.new_entity()
        entity.set_key(key)
        request = http.ClientRequest(str(entity.get_location()), 'DELETE')
        self.client.process_request(request)
        if request.status == 204:
            # success, nothing to read back
            return
        else:
            self.raise_error(request)


class NavigationCollection(ClientCollection, core.NavigationCollection):

    def __init__(self, from_entity, name, **kwargs):
        if kwargs.pop('baseURI', None):
            logging.warn(
                'OData Client NavigationCollection ignored baseURI argument')
        nav_path = uri.escape_data(name.encode('utf-8'))
        location = str(from_entity.get_location())
        super(NavigationCollection, self).__init__(
            from_entity=from_entity, name=name,
            base_uri=uri.URI.from_octets(location + "/" + nav_path), **kwargs)
        self.isCollection = self.from_entity[name].isCollection
        self.linksURI = uri.URI.from_octets(location + "/$links/" + nav_path)

    def insert_entity(self, entity):
        """Inserts *entity* into this collection.

        OData servers don't all support insert directly into a
        navigation property so we risk transactional inconsistency here
        by overriding the default implementation to performs a two stage
        insert/create link process unless this is a required link for
        *entity*, in which case we figure out the back-link, bind
        *from_entity* and then do the reverse insert which is more likely
        to be supported.

        If there is no back-link we resort to an insert against the
        navigation property itself."""
        if self.from_end.associationEnd.multiplicity == edm.Multiplicity.One:
            # we're in trouble, entity can't exist without linking to us
            # so we try a deep link
            back_link = self.entity_set.linkEnds[self.from_end.otherEnd]
            if back_link:
                # there is a navigation property going back
                entity[back_link].bind_entity(self.from_entity)
                with self.entity_set.open() as baseCollection:
                    baseCollection.insert_entity(entity)
                return
            elif self.isCollection:
                # if there is no back link we'll have to do an insert
                # into this end using a POST to the navigation property.
                # Surely anyone with a model like this will support such
                # an implicit link.
                return super(NavigationCollection, self).insert_entity(entity)
            else:
                # if the URL for this navigation property represents a
                # single entity then you're out of luck.  You can't POST
                # to, for example, Orders(12345)/Invoice if there can
                # only be one Invoice.  We only get here if Invoice
                # requires an Order but doesn't have a navigation
                # property to bind it to so we are definitely in the
                # weeds.  But attempting to insert Invoice without the
                # link seems fruitless
                raise NotImplementedError(
                    "Can't insert an entity into a 1-(0..)1 relationship "
                    "without a back-link")
        else:
            with self.entity_set.open() as baseCollection:
                baseCollection.insert_entity(entity)
                # this link may fail, which isn't what the caller wanted
                # but it seems like a bad idea to try deleting the
                # entity at this stage.
                self[entity.key()] = entity

    def __len__(self):
        if self.isCollection:
            return super(NavigationCollection, self).__len__()
        else:
            # This is clumsy as we grab the entity itself
            entity_url = str(self.base_uri)
            sys_query_options = {}
            if self.filter is not None:
                sys_query_options[
                    core.SystemQueryOption.filter] = to_text(self.filter)
            if sys_query_options:
                entity_url = uri.URI.from_octets(
                    entity_url +
                    "?" +
                    core.ODataURI.format_sys_query_options(sys_query_options))
            request = http.ClientRequest(str(entity_url))
            request.set_header('Accept', 'application/atom+xml;type=entry')
            self.client.process_request(request)
            if request.status == 404:
                # if we got a 404 from the underlying system we're done
                return 0
            elif request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(base_uri=entity_url)
            doc.read(request.res_body)
            if isinstance(doc.root, atom.Entry):
                entity = core.Entity(self.entity_set)
                entity.exists = True
                doc.root.get_value(entity)
                return 1
            else:
                raise core.InvalidEntryDocument(str(entity_url))

    def entity_generator(self):
        if self.isCollection:
            for entity in super(NavigationCollection, self).entity_generator():
                yield entity
        else:
            # The base_uri points to a single entity already, we must not add
            # the key
            entity_url = str(self.base_uri)
            sys_query_options = {}
            if self.filter is not None:
                sys_query_options[
                    core.SystemQueryOption.filter] = to_text(self.filter)
            if self.expand is not None:
                sys_query_options[
                    core.SystemQueryOption.expand] = core.format_expand(
                    self.expand)
            if self.select is not None:
                sys_query_options[
                    core.SystemQueryOption.select] = core.format_select(
                    self.select)
            if sys_query_options:
                entity_url = uri.URI.from_octets(
                    entity_url +
                    "?" +
                    core.ODataURI.format_sys_query_options(sys_query_options))
            request = http.ClientRequest(str(entity_url))
            request.set_header('Accept', 'application/atom+xml;type=entry')
            self.client.process_request(request)
            if request.status == 404:
                return
            elif request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(base_uri=entity_url)
            doc.read(request.res_body)
            if isinstance(doc.root, atom.Entry):
                entity = core.Entity(self.entity_set)
                entity.exists = True
                doc.root.get_value(entity)
                yield entity
            else:
                raise core.InvalidEntryDocument(str(entity_url))

    def __getitem__(self, key):
        if self.isCollection:
            return super(NavigationCollection, self).__getitem__(key)
        else:
            # The base_uri points to a single entity already, we must not add
            # the key
            entity_url = str(self.base_uri)
            sys_query_options = {}
            if self.filter is not None:
                sys_query_options[
                    core.SystemQueryOption.filter] = to_text(self.filter)
            if self.expand is not None:
                sys_query_options[
                    core.SystemQueryOption.expand] = core.format_expand(
                    self.expand)
            if self.select is not None:
                sys_query_options[
                    core.SystemQueryOption.select] = core.format_select(
                    self.select)
            if sys_query_options:
                entity_url = uri.URI.from_octets(
                    entity_url + "?" +
                    core.ODataURI.format_sys_query_options(sys_query_options))
            request = http.ClientRequest(str(entity_url))
            request.set_header('Accept', 'application/atom+xml;type=entry')
            self.client.process_request(request)
            if request.status == 404:
                raise KeyError(key)
            elif request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(base_uri=entity_url)
            doc.read(request.res_body)
            if isinstance(doc.root, atom.Entry):
                entity = core.Entity(self.entity_set)
                entity.exists = True
                doc.root.get_value(entity)
                if entity.key() == key:
                    return entity
                else:
                    raise KeyError(key)
            elif isinstance(doc.root, core.Error):
                raise KeyError(key)
            else:
                raise core.InvalidEntryDocument(str(entity_url))

    def __setitem__(self, key, entity):
        if not isinstance(entity, edm.Entity) or \
                entity.entity_set is not self.entity_set:
            raise TypeError
        if key != entity.key():
            raise ValueError
        if not entity.exists:
            raise edm.NonExistentEntity(str(entity.get_location()))
        if not self.isCollection:
            request = http.ClientRequest(str(self.base_uri), 'GET')
            self.client.process_request(request)
            if request.status == 200:
                # this collection is not empty, which will be an error
                # unless it already contains entity, in which case it's
                # a no-op
                existing_entity = self.new_entity()
                doc = core.Document()
                doc.read(request.res_body)
                existing_entity.exists = True
                doc.root.get_value(existing_entity)
                if existing_entity.key() == entity.key():
                    return
                else:
                    raise edm.NavigationError(
                        "Navigation property %s already points to an entity "
                        "(use replace to update it)" % self.name)
            elif request.status != 404:
                # some type of error
                self.raise_error(request)
            doc = core.Document(root=core.URI)
            doc.root.set_value(str(entity.get_location()))
            data = str(doc).encode('utf-8')
            request = http.ClientRequest(
                str(self.linksURI), 'PUT', entity_body=data)
            request.set_content_type(
                params.MediaType.from_str('application/xml'))
            self.client.process_request(request)
            if request.status == 204:
                return
            else:
                self.raise_error(request)
        else:
            doc = core.Document(root=core.URI)
            doc.root.set_value(str(entity.get_location()))
            data = str(doc).encode('utf-8')
            request = http.ClientRequest(
                str(self.linksURI), 'POST', entity_body=data)
            request.set_content_type(
                params.MediaType.from_str('application/xml'))
            self.client.process_request(request)
            if request.status == 204:
                return
            else:
                self.raise_error(request)

    def replace(self, entity):
        if not entity.exists:
            raise edm.NonExistentEntity(str(entity.get_location()))
        if self.isCollection:
            # inherit the implementation
            super(NavigationCollection, self).replace(entity)
        else:
            if not isinstance(entity, edm.Entity) or \
                    entity.entity_set is not self.entity_set:
                raise TypeError
            doc = core.Document(root=core.URI)
            doc.root.set_value(str(entity.get_location()))
            data = str(doc).encode('utf-8')
            request = http.ClientRequest(
                str(self.linksURI), 'PUT', entity_body=data)
            request.set_content_type(
                params.MediaType.from_str('application/xml'))
            self.client.process_request(request)
            if request.status == 204:
                return
            else:
                self.raise_error(request)

    def __delitem__(self, key):
        if self.isCollection:
            entity = self.new_entity()
            entity.set_key(key)
            request = http.ClientRequest(
                str(self.linksURI) + core.ODataURI.format_entity_key(entity),
                'DELETE')
        else:
            # danger, how do we know that key really is the right one?
            request = http.ClientRequest(str(self.linksURI), 'DELETE')
        self.client.process_request(request)
        if request.status == 204:
            # success, nothing to read back
            return
        else:
            self.raise_error(request)


class Client(app.Client):

    """An OData client.

    Can be constructed with an optional URL specifying the service root of an
    OData service.  The URL is passed directly to :py:meth:`LoadService`."""

    def __init__(self, service_root=None, **kwargs):
        app.Client.__init__(self, **kwargs)
        service_root = kwargs.get('serviceRoot', service_root)
        #: a :py:class:`pyslet.rfc5023.Service` instance describing this
        #: service
        self.service = None
        # : a :py:class:`pyslet.rfc2396.URI` instance pointing to the
        # : service root
        self.service_root = None
        # a path prefix string of the service root
        self.path_prefix = None
        #: a dictionary of feed titles, mapped to
        #: :py:class:`csdl.EntitySet` instances
        self.feeds = {}
        #: a :py:class:`metadata.Edmx` instance containing the model for
        #: the service
        self.model = None
        if service_root is not None:
            self.LoadService(service_root)

    @old_method('LoadService')
    def load_service(self, service_root, metadata=None):
        """Configures this client to use the service at *service_root*

        service_root
            A string or :py:class:`pyslet.rfc2396.URI` instance.  The
            URI may now point to a local file though this must have an
            xml:base attribute to point to the true location of the
            service as calls to the feeds themselves require the use of
            http(s).

        metadata (None)
            A :py:class:`pyslet.rfc2396.URI` instance pointing to the
            metadata file.  This is usually derived automatically by
            adding $metadata to the service root but some services have
            inconsistent metadata models.  You can download a copy,
            modify the model and use a local copy this way instead,
            e.g., by passing something like::

                URI.from_path('metadata.xml')

            If you use a local copy you must add an xml:base attribute
            to the root element indicating the true location of the
            $metadata file as the client uses this information to match
            feeds with the metadata model."""
        if isinstance(service_root, uri.URI):
            self.service_root = service_root
        else:
            self.service_root = uri.URI.from_octets(service_root)
        doc = core.Document(base_uri=self.service_root)
        if isinstance(self.service_root, uri.FileURL):
            # load the service root from a file instead
            doc.read()
        else:
            request = http.ClientRequest(str(self.service_root))
            request.set_header('Accept', 'application/atomsvc+xml')
            self.process_request(request)
            if request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc.read(request.res_body)
        if isinstance(doc.root, app.Service):
            self.service = doc.root
            self.service_root = uri.URI.from_octets(doc.root.resolve_base())
            self.feeds = {}
            self.model = None
            for w in self.service.Workspace:
                for f in w.Collection:
                    url = f.get_feed_url()
                    if f.Title:
                        self.feeds[f.Title.get_value()] = url
        else:
            raise core.InvalidServiceDocument(str(service_root))
        self.path_prefix = self.service_root.abs_path
        if self.path_prefix[-1] == "/":
            self.path_prefix = self.path_prefix[:-1]
        if metadata is None:
            metadata = uri.URI.from_octets('$metadata').resolve(
                self.service_root)
        doc = edmx.Document(base_uri=metadata, reqManager=self)
        try:
            doc.read()
            if isinstance(doc.root, edmx.Edmx):
                self.model = doc.root
                for s in self.model.DataServices.Schema:
                    for container in s.EntityContainer:
                        if container.is_default_entity_container():
                            prefix = ""
                        else:
                            prefix = container.name + "."
                        for es in container.EntitySet:
                            ftitle = prefix + es.name
                            if ftitle in self.feeds:
                                if self.feeds[ftitle] == es.get_location():
                                    self.feeds[ftitle] = es
            else:
                raise DataFormatError(str(metadata))
        except xml.XMLError as e:
            # Failed to read the metadata document, there may not be one of
            # course
            raise DataFormatError(str(e))
        # Missing feeds are pruned from the list, perhaps the service
        # advertises them but if we don't have a model of them we can't
        # use of them
        for f in list(dict_keys(self.feeds)):
            if isinstance(self.feeds[f], uri.URI):
                logging.info(
                    "Can't find metadata definition of feed: %s", str(
                        self.feeds[f]))
                del self.feeds[f]
            else:
                # bind our EntityCollection class
                entity_set = self.feeds[f]
                entity_set.bind(EntityCollection, client=self)
                for np in entity_set.entityType.NavigationProperty:
                    entity_set.bind_navigation(
                        np.name, NavigationCollection, client=self)
                logging.debug(
                    "Registering feed: %s", str(self.feeds[f].get_location()))

    ACCEPT_LIST = messages.AcceptList(
        messages.AcceptItem(messages.MediaRange('application', 'atom+xml')),
        messages.AcceptItem(messages.MediaRange('application', 'atomsvc+xml')),
        messages.AcceptItem(messages.MediaRange('application', 'atomcat+xml')),
        messages.AcceptItem(messages.MediaRange('application', 'xml')))

    def queue_request(self, request, timeout=60):
        if not request.has_header("Accept"):
            request.set_accept(self.ACCEPT_LIST)
        request.set_header(
            'DataServiceVersion', '2.0; pyslet %s' % info.version)
        request.set_header(
            'MaxDataServiceVersion', '2.0; pyslet %s' % info.version)
        super(Client, self).queue_request(request, timeout)
