#! /usr/bin/env python
"""OData server implementation."""

from pyslet.py26 import *       # noqa

import sys
import string
import traceback
import json
import logging
import base64

import pyslet.info as info
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.http.grammar as grammar
import pyslet.http.params as params
import pyslet.http.messages as messages
import pyslet.rfc2396 as uri
import pyslet.xml.structures as xml
import pyslet.html401 as html
from pyslet.unicode5 import detect_encoding
import csdl as edm
import core as core
import metadata as edmx

# from core import *


class WSGIWrapper(object):

    def __init__(self, environ, start_response, response_headers):
        """A simple wrapper class for a wsgi application.

        Allows additional response headers to be added to the wsgi response."""
        self.environ = environ
        self.start_response = start_response
        self.response_headers = response_headers

    def call(self, application):
        """Calls wsgi *application*"""
        return application(self.environ, self.start_response_wrapper)

    def start_response_wrapper(self, status, response_headers, exc_info=None):
        """Traps start_response and adds the additional headers."""
        response_headers = response_headers + self.response_headers
        return self.start_response(status, response_headers, exc_info)


class Server(app.Server):

    """Extends py:class:`pyselt.rfc5023.Server` to provide an OData
    server.

    We do some special processing of the serviceRoot before passing it
    to the parent construtor as in OData it cannot end in a trailing
    slash.  If it does, we strip the slash from the root and use that as
    our OData service root.

    But... we always pass a URI with a trailing slash to the parent
    constructor following the example set by
    http://services.odata.org/OData/OData.svc and issue a temporary
    redirect when we receive requests for the OData service root to the
    OData URI consisting of the service root + a resource path
    consisting of a single '/'.

    This makes the links in the service document much clearer and easier
    to generate but more importantly, it deals with the awkward case of
    a service root consisting of just scheme and authority (e.g.,
    http://odata.example.com ).  This type of servie root cannot be
    obtained with a simple HTTP request as the trailing '/' is implied
    (and no redirection is necessary)."""

    AtomRanges = [
        messages.MediaRange.from_str('application/atom+xml'),
        messages.MediaRange.from_str('application/xml'),
        messages.MediaRange.from_str('text/xml')]

    JSONRanges = [
        messages.MediaRange.from_str('application/json')
    ]

    DefaultAcceptList = messages.AcceptList.from_str(
        "application/atom+xml, "
        "application/atomsvc+xml, "
        "application/xml; q=0.9, "
        "text/xml; q=0.8, "
        "text/plain; q=0.7, "
        "*/*; q=0.6")

    ErrorTypes = [
        params.MediaType.from_str('application/atom+xml'),
        params.MediaType.from_str('application/xml'),
        params.MediaType.from_str('application/json')]

    RedirectTypes = [
        params.MediaType.from_str('text/html'),
        params.MediaType.from_str('text/plain'),
        params.MediaType.from_str('application/xml')]

    FeedTypes = [		# in order of preference if there is a tie
        params.MediaType.from_str('application/atom+xml'),
        params.MediaType.from_str('application/atom+xml;type=feed'),
        params.MediaType.from_str('application/xml'),
        params.MediaType.from_str('text/xml'),
        params.MediaType.from_str('application/json'),
        params.MediaType.from_str('text/plain')]

    EntryTypes = [  # in order of preference if there is a tie
        params.MediaType.from_str('application/atom+xml'),
        params.MediaType.from_str('application/atom+xml;type=entry'),
        params.MediaType.from_str('application/xml'),
        params.MediaType.from_str('text/xml'),
        params.MediaType.from_str('application/json'),
        params.MediaType.from_str('text/plain')]

    ValueTypes = [  # in order of preference if there is a tie
        params.MediaType.from_str('application/xml'),
        params.MediaType.from_str('text/xml'),
        params.MediaType.from_str('application/json'),
        params.MediaType.from_str('text/plain')]

    ServiceRootTypes = [  # in order of preference if there is a tie
        params.MediaType.from_str('application/atomsvc+xml'),
        params.MediaType.from_str('application/json'),
        params.MediaType.from_str('application/xml'),
        params.MediaType.from_str('text/plain')]

    MetadataTypes = [  # in order of preference if there is a tie
        params.MediaType.from_str('application/xml'),
        params.MediaType.from_str('text/xml'),
        params.MediaType.from_str('text/plain')]

    DereferenceBinaryRanges = [
        messages.MediaRange.from_str('application/octet-stream'),
        messages.MediaRange.from_str('octet/stream')]

    DereferenceTypes = [  # in order of preference
        params.MediaType.from_str('text/plain;charset=utf-8'),
        params.MediaType.from_str('application/octet-stream'),
        params.MediaType.from_str('octet/stream')]
    # we allow the last one in case someone read the spec literally!

    StreamTypes = [
        params.MediaType.from_str('application/octet-stream'),
        params.MediaType.from_str('octet/stream')]
    # we allow the last one in case someone read the spec literally!

    def __init__(self, serviceRoot="http://localhost"):
        if serviceRoot[-1] != '/':
            serviceRoot = serviceRoot + '/'
        app.Server.__init__(self, serviceRoot)
        if self.serviceRoot.rel_path is not None:
            # The service root must be absolute (or missing completely)!
            raise ValueError("serviceRoot must not be relative")
        if self.serviceRoot.abs_path is None:
            self.pathPrefix = ''
        else:
            self.pathPrefix = self.serviceRoot.abs_path
        # pathPrefix must not have a tailing slash, even if this makes it an
        # empty string
        if self.pathPrefix[-1] == '/':
            self.pathPrefix = self.pathPrefix[:-1]
        # : a single workspace that contains all collections
        self.ws = self.service.add_child(app.Workspace)
        self.ws.add_child(atom.Title).set_value("Default")
        #: a :py:class:`metadata.Edmx` instance; the model for the service
        self.model = None
        #: the maximum number of entities to return per request
        self.topmax = 100

    def SetModel(self, model):
        """Sets the model for the server from a parentless
        :py:class:`~pyslet.odatav2.metadata.Edmx` instance or an Edmx
        :py:class:`~pyslet.odatav2.metadata.Document` instance."""
        if isinstance(model, edmx.Document):
            doc = model
            model = model.root
        elif isinstance(model, edmx.Edmx):
            # create a document to hold the model
            doc = edmx.Document(root=model)
        else:
            raise TypeError("Edmx document or instance required for model")
        # update the base URI of the metadata document to identify this service
        doc.set_base(self.serviceRoot)
        if self.model:
            # get rid of the old model
            for c in self.ws.Collection:
                c.detach_from_doc()
                c.parent = None
            self.ws.Collection = []
        for s in model.DataServices.Schema:
            for container in s.EntityContainer:
                if container.is_default_entity_container():
                    prefix = ""
                else:
                    prefix = container.name + "."
                # define one feed for each entity set, prefixed with the name
                # of the entity set
                for es in container.EntitySet:
                    feed = self.ws.add_child(app.Collection)
                    feed.href = prefix + es.name
                    feed.add_child(atom.Title).set_value(prefix + es.name)
                    # update the locations following SetBase above
                    es.set_location()
        self.model = model

    @classmethod
    def encode_pathinfo(cls, pathinfo):
        """Encodes PATHINFO using URL-encoding

        According to RC3875_ the PATHINFO CGI variable contains an
        unencoded path string.  That means that reserved characters
        escaped in the original URL will be unescaped in PATHINFO.  This
        causes problems in OData because the path component of the URL
        may contain arbitrary strings (as keys).  Unfortunately there is
        no other CGI variable that communicates the original requested
        URL, so we are stuck with interpreting PATHINFO.  In fact, the
        constraints on identifiers mean that there are only two problem
        cases.

        1.  %2F in the URL becomes / and is mistaken for a path
            separator.  This can only occur within a quoted string so we
            scan the URL and determine whether or not we are in a quoted
            string, if we are, we percent-encode path-segment reserved
            characters.

        2.  The second issue is the quote character itself.  Depending on
            which version of the URI spec you are working to it may be
            escaped or not.  OData originally attempted to double-up on
            the escaping mechanism and use 'O%27Toole' as the way to
            include a quote in a quoted string.  Sadly this will break
            for us because we'll receive 'O'Toole' instead but it breaks
            for many client anyway as unescaped quotes are often
            replaced with %27 anyway.

            Fortunately it never really worked that way in practice
            anyway and the more recent specs use quote doubling
            'O''Toole' which is much more robust.  This enables us to
            determine if we are in a quoted string or not simply by
            counting, and hence deal with issue 1.

        ..  _RFC3875 http://www.ietf.org/rfc/rfc3875"""
        if isinstance(pathinfo, unicode):
            pathinfo = pathinfo.encode('utf-8')
        qmode = False
        result = []
        for c in pathinfo:
            if qmode:
                # we need to quote reserved characters
                if uri.is_path_segment_reserved(c) or not (
                        uri.is_unreserved(c) or uri.is_reserved(c)):
                    result.append("%%%02X" % ord(c))
                else:
                    result.append(c)
                if c == "'":
                    qmode = False
            elif c == "'":
                result.append(c)
                qmode = True
            elif c == '?':
                # we continue to escape '?' as it must have been escaped
                # in the original URI
                result.append('%3F')
            elif not (uri.is_unreserved(c) or uri.is_reserved(c)):
                result.append("%%%02X" % ord(c))
            else:
                # leave '/', ';' and '=' unescaped
                result.append(c)
        return string.join(result, '')

    def __call__(self, environ, start_response):
        """wsgi interface for the server."""
        response_headers = []
        try:
            version = self.CheckCapabilityNegotiation(
                environ, start_response, response_headers)
            if version is None:
                return self.ODataError(
                    core.ODataURI('error'),
                    environ,
                    start_response,
                    "DataServiceVersionMismatch",
                    "Maximum supported protocol version: 2.0")
            appPath = environ.get('SCRIPT_NAME', "")
            path = appPath + environ['PATH_INFO']
            # we have to URL-encode PATH_INFO
            path = self.encode_pathinfo(path)
            query = environ.get('QUERY_STRING', None)
            if query:
                path = path + '?' + query
            request = core.ODataURI(path, self.pathPrefix, version)
            if request.resourcePath is None:
                # this is not a URI for us, pass to our superclass
                wrapper = WSGIWrapper(
                    environ, start_response, response_headers)
                # super essentially allows us to pass a bound method of
                # our parent that we ourselves are hiding.
                return wrapper.call(super(Server, self).__call__)
            elif request.resourcePath == '':
                # An empty resource path means they hit the service root,
                # redirect
                location = str(self.serviceRoot)
                r = html.HTML(None)
                r.Head.Title.set_value('Redirect')
                div = r.Body.add_child(html.Div)
                div.add_data(u"Moved to: ")
                anchor = div.add_child(html.A)
                anchor.href = self.serviceRoot
                anchor.set_value(location)
                responseType = self.ContentNegotiation(
                    request, environ, self.RedirectTypes)
                if responseType is None:
                    # this is a redirect response, default to text/plain anyway
                    responseType = params.MediaType.from_str('text/plain')
                if responseType == "text/plain":
                    data = str(r.plain_text())
                else:
                    data = str(r)
                response_headers.append(("Content-Type", str(responseType)))
                response_headers.append(("Content-Length", str(len(data))))
                response_headers.append(("Location", location))
                start_response(
                    "%i %s" % (307, "Temporary Redirect"), response_headers)
                return [data]
            else:
                return self.HandleRequest(
                    request, environ, start_response, response_headers)
        except core.InvalidSystemQueryOption as e:
            return self.ODataError(
                core.ODataURI('error'),
                environ,
                start_response,
                "InvalidSystemQueryOption",
                u"Invalid System Query Option: %s" % unicode(e))
        except core.InvalidPathOption as e:
            return self.ODataError(
                core.ODataURI('error'),
                environ,
                start_response,
                "Bad Request",
                u"Path option is invalid or "
                "incompatible with this form of URI: %s" % unicode(e),
                400)
        except core.InvalidMethod as e:
            return self.ODataError(
                core.ODataURI('error'),
                environ,
                start_response,
                "Bad Request",
                u"Method not allowed: %s" % unicode(e),
                400)
        except ValueError as e:
            traceback.print_exception(*sys.exc_info())
            # This is a bad request
            return self.ODataError(
                core.ODataURI('error'),
                environ,
                start_response,
                "ValueError",
                unicode(e))
        except:
            eInfo = sys.exc_info()
            traceback.print_exception(*eInfo)
            # return self.HandleError(core.ODataURI('error'),
            #   environ,start_response)
            return self.ODataError(
                core.ODataURI('error'),
                environ,
                start_response,
                "UnexpectedError",
                u"%s: %s" % (eInfo[0], eInfo[1]),
                500)

    def ODataError(
            self,
            request,
            environ,
            start_response,
            subCode,
            message='',
            code=400):
        """Generates ODataError, typically as the result of a bad request."""
        response_headers = []
        e = core.Error(None)
        e.add_child(core.Code).set_value(subCode)
        e.add_child(core.Message).set_value(message)
        responseType = self.ContentNegotiation(
            request, environ, self.ErrorTypes)
        if responseType is None:
            # this is an error response, default to text/plain anyway
            responseType = params.MediaType.from_str('text/plain')
        elif responseType == "application/atom+xml":
            # even if you didn't ask for it, you get application/xml in this
            # case
            responseType = "application/xml"
        if responseType == "application/json":
            data = str(string.join(e.GenerateStdErrorJSON(), ''))
        else:
            data = str(e)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (code, subCode), response_headers)
        return [data]

    def GetResourceFromURI(self, href):
        """Returns the resource object represented by *href*

        href
            A :py:class:`pyslet.rfc2396.URI` instance

        The URI must not use path, or system query options but must
        identify an enity set, entity, complex or simple value."""
        if not href.is_absolute():
            # resolve relative to the service root
            href = href.resolve(self.serviceRoot)
        # check the canonical roots
        if not self.serviceRoot.get_canonical_root().match(
                href.get_canonical_root()):
            # This isn't even for us
            return None
        request = core.ODataURI(href, self.pathPrefix)
        return self.GetResource(request)[0]

    def GetResource(self, odataURI):
        resource = self.model
        noNavPath = (resource is None)
        parentEntity = None
        for segment in odataURI.navPath:
            name, keyPredicate = segment
            if noNavPath:
                raise core.BadURISegment(name)
            if isinstance(resource, edmx.Edmx):
                try:
                    resource = resource.DataServices.search_containers(name)
                except KeyError as e:
                    raise core.MissingURISegment(str(e))
                if isinstance(resource, edm.FunctionImport):
                    # TODO: grab the params from the query string
                    params = {}
                    for p in resource.values():
                        # these are the parameters
                        if p.mode in (edm.ParameterMode.In,
                                      edm.ParameterMode.InOut):
                            params[p.name] = p.typeRef(
                                odataURI.get_param_value(p.name))
                    resource = resource.execute(params)
                    # If this does not identify a collection of entities it
                    # must be the last path segment
                    if not isinstance(resource, edm.EntityCollection):
                        noNavPath = True
                        # 10-14 have identical constraints, treat them the same
                        odataURI.ValidateSystemQueryOptions(10)
                elif isinstance(resource, edm.EntitySet):
                    resource = resource.open()
                else:
                    # not the right sort of thing
                    raise core.MissingURISegment(name)
                if isinstance(resource, edm.EntityCollection):
                    if keyPredicate:
                        # the keyPredicate can be passed directly as the key
                        try:
                            collection = resource
                            resource = collection[
                                collection.entity_set.get_key(keyPredicate)]
                            collection.close()
                        except KeyError as e:
                            raise core.MissingURISegment(
                                "%s%s" %
                                (name, core.ODataURI.FormatKeyDict(keyPredicate)))
                elif resource is None:
                    raise core.MissingURISegment(name)
            elif isinstance(resource,
                            (edm.EntityCollection, edm.FunctionCollection)):
                # bad request, because the collection must be the last
                # thing in the path
                raise core.BadURISegment(
                    "%s since the object's parent is a collection" % name)
            elif isinstance(resource, edm.Entity):
                if name not in resource:
                    raise core.MissingURISegment(name)
                # set the parent entity
                parentEntity = resource
                resource = resource[name]
                if isinstance(resource, edm.DeferredValue):
                    if resource.isCollection:
                        if keyPredicate:
                            try:
                                with resource.open() as collection:
                                    resource = collection[
                                        collection.entity_set.get_key(
                                            keyPredicate)]
                            except KeyError as e:
                                raise core.MissingURISegment(name)
                        else:
                            resource = resource.open()
                    else:
                        # keyPredicate not allowed here!
                        if keyPredicate:
                            raise core.BadURISegment(
                                "%s (keyPredicate not allowed "
                                "for a navigation property that identifies a "
                                "single entity)" %
                                name)
                        resource = resource.get_entity()
                        # if resource is None: See the resolution:
                        # https://tools.oasis-open.org/issues/browse/ODATA-412
            elif isinstance(resource, edm.Complex):
                if name in resource:
                    # This is a regular property of the ComplexType
                    resource = resource[name]
                else:
                    raise core.MissingURISegment(name)
            elif resource is None:
                raise core.MissingURISegment(
                    "%s, property cannot be resolved "
                    "as the parent entity does not exist" %
                    name)
            else:
                # Any other type is just a property or simple-type
                raise core.BadURISegment(name)
        if isinstance(resource, edm.EntityCollection):
            odataURI.ValidateSystemQueryOptions(1)  # includes 6 Note 2
        elif isinstance(resource, edm.Entity):
            if odataURI.pathOption == core.PathOption.value:
                odataURI.ValidateSystemQueryOptions(17)  # media resource value
            elif odataURI.pathOption != core.PathOption.links:
                odataURI.ValidateSystemQueryOptions(2)  # includes 6 Note 1
        elif isinstance(resource, edm.Complex):
            odataURI.ValidateSystemQueryOptions(3)
        elif isinstance(resource, edm.SimpleValue):
            # 4 & 5 are identical
            odataURI.ValidateSystemQueryOptions(4)
        elif resource is None and parentEntity is not None:
            # there is a very specific use case here, use of
            # <entity>/$links/<nav-et> where the link is NULL
            if not odataURI.pathOption == core.PathOption.links:
                # <entity>/<nav-et> where the link is NULL raises a 404
                # See the resolution:
                # https://tools.oasis-open.org/issues/browse/ODATA-412
                raise core.MissingURISegment(
                    "no entity is linked by this navigation property")
        return resource, parentEntity

    def set_etag(self, entity, response_headers):
        etag = entity.etag()
        if etag is not None:
            s = "%s" if entity.etag_is_strong() else "W/%s"
            etag = s % grammar.quote_string(
                string.join(map(core.ODataURI.FormatLiteral, etag), ','))
            response_headers.append(("ETag", etag))

    def HandleRequest(
            self,
            request,
            environ,
            start_response,
            response_headers):
        """Handles an OData request.

        *request*
            An :py:class:`core.ODataURI` instance with a non-empty
            resourcePath."""
        method = environ["REQUEST_METHOD"].upper()
        try:
            resource, parentEntity = self.GetResource(request)
            if request.pathOption == core.PathOption.metadata:
                return self.ReturnMetadata(
                    request, environ, start_response, response_headers)
            elif request.pathOption == core.PathOption.batch:
                return self.ODataError(
                    request,
                    environ,
                    start_response,
                    "Bad Request",
                    "Batch requests not supported",
                    404)
            elif request.pathOption == core.PathOption.count:
                if isinstance(resource, edm.Entity):
                    return self.ReturnCount(
                        1, request, environ, start_response, response_headers)
                elif isinstance(resource, edm.EntityCollection):
                    resource.set_filter(
                        request.sysQueryOptions.get(
                            core.SystemQueryOption.filter,
                            None))
                    return self.ReturnCount(
                        len(resource),
                        request,
                        environ,
                        start_response,
                        response_headers)
                else:
                    raise core.BadURISegment(
                        "$count must be applied to "
                        "an EntitySet or single EntityType instance")
            elif request.pathOption == core.PathOption.links:
                # parentEntity will be source entity
                # request.linksProperty is the name of the navigation
                # property in the source entity
                # resource will be the target entity, a collection or
                # None
                if not isinstance(parentEntity, edm.Entity):
                    raise core.BadURISegment("$links must be preceded by a "
                                             "single EntityType instance")
                if method == "GET":
                    # open the collection and select the key properties only
                    if isinstance(resource, edm.EntityCollection):
                        with resource as collection:
                            collection.select_keys()
                            collection.set_page(
                                request.sysQueryOptions.get(
                                    core.SystemQueryOption.top, None),
                                request.sysQueryOptions.get(
                                    core.SystemQueryOption.skip, None),
                                request.sysQueryOptions.get(
                                    core.SystemQueryOption.skiptoken, None))
                            inlinecount = request.sysQueryOptions.get(
                                core.SystemQueryOption.inlinecount, None)
                            collection.set_inlinecount(
                                inlinecount == core.InlineCount.allpages)
                            return self.ReturnLinks(
                                collection,
                                request,
                                environ,
                                start_response,
                                response_headers)
                    elif isinstance(resource, edm.Entity):
                        # should have just a single link
                        return self.ReturnLink(
                            resource,
                            request,
                            environ,
                            start_response,
                            response_headers)
                    else:
                        # resource is None - no linked entity
                        raise core.MissingURISegment(
                            "%s, no entity is related" % request.linksProperty)
                elif method == "POST":
                    if resource is None:
                        # can you POST to Orders(1)/$links/Customer ? - only if
                        # it is currently NULL (0..1)
                        resource = parentEntity[
                            request.linksProperty].open()
                    if isinstance(resource, edm.EntityCollection):
                        with resource as collection:
                            targetEntity = self.ReadEntityFromLink(environ)
                            collection[targetEntity.key()] = targetEntity
                        return self.ReturnEmpty(
                            start_response, response_headers)
                    else:
                        # you can't POST to a single link that already exists
                        raise core.BadURISegment(
                            "%s is already linked, use PUT "
                            "instead of POST to update it" %
                            request.linksProperty)
                elif method == "PUT":
                    if parentEntity[request.linksProperty].isCollection:
                        raise core.BadURISegment(
                            "%s: can't update a link with multiplicity *" %
                            request.linksProperty)
                    with parentEntity[
                            request.linksProperty].open() as \
                            collection:
                        targetEntity = self.ReadEntityFromLink(environ)
                        collection.replace(targetEntity)
                    return self.ReturnEmpty(start_response, response_headers)
                elif method == "DELETE":
                    if isinstance(resource, edm.EntityCollection):
                        raise core.BadURISegment(
                            "%s: DELETE must specify a single link" %
                            request.linksProperty)
                    elif resource is None:
                        raise core.MissingURISegment(
                            "%s, no entity is related" % request.linksProperty)
                    with parentEntity[
                            request.linksProperty].open() as \
                            collection:
                        del collection[resource.key()]
                    return self.ReturnEmpty(start_response, response_headers)
                else:
                    raise core.InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.Entity):
                if method == "GET" or method == "HEAD":
                    if request.pathOption == core.PathOption.value:
                        if resource.type_def.has_stream():
                            return self.ReturnStream(
                                resource,
                                request,
                                environ,
                                start_response,
                                response_headers,
                                method)
                        else:
                            raise core.BadURISegment(
                                "$value cannot be used since "
                                "the entity is not a media stream")
                    else:
                        self.ExpandResource(resource, request.sysQueryOptions)
                        return self.ReturnEntity(
                            resource,
                            request,
                            environ,
                            start_response,
                            response_headers)
                elif method == "PUT":
                    if request.pathOption == core.PathOption.value:
                        if resource.type_def.has_stream():
                            sinfo = core.StreamInfo()
                            if "CONTENT_TYPE" in environ:
                                sinfo.type = params.MediaType.from_str(
                                    environ["CONTENT_TYPE"])
                            input = messages.WSGIInputWrapper(environ)
                            with resource.entity_set.open() as coll:
                                coll.update_stream(input,
                                                   resource.key(),
                                                   sinfo)
                                # need to update the resource as some fields
                                # may have changed
                                resource = coll[resource.key()]
                            self.set_etag(resource, response_headers)
                            return self.ReturnEmpty(
                                start_response, response_headers)
                        else:
                            raise core.BadURISegment(
                                "$value cannot be used since the entity is "
                                "not a media stream")
                    else:
                        # update the entity from the request
                        self.ReadEntity(resource, environ)
                        resource.commit()
                        # now we've updated the entity it is safe to calculate
                        # the ETag
                        self.set_etag(resource, response_headers)
                        return self.ReturnEmpty(
                            start_response, response_headers)
                elif method == "DELETE":
                    if request.pathOption == core.PathOption.value:
                        raise core.BadURISegment(
                            "$value cannot be used with DELETE")
                    resource.delete()
                    return self.ReturnEmpty(start_response, response_headers)
                else:
                    raise core.InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.EntityCollection):
                if method == "GET":
                    self.ExpandResource(resource, request.sysQueryOptions)
                    resource.set_filter(
                        request.sysQueryOptions.get(
                            core.SystemQueryOption.filter,
                            None))
                    resource.set_orderby(
                        request.sysQueryOptions.get(
                            core.SystemQueryOption.orderby,
                            None))
                    resource.set_page(
                        request.sysQueryOptions.get(
                            core.SystemQueryOption.top, None),
                        request.sysQueryOptions.get(
                            core.SystemQueryOption.skip, None),
                        request.sysQueryOptions.get(
                            core.SystemQueryOption.skiptoken, None))
                    inlinecount = request.sysQueryOptions.get(
                        core.SystemQueryOption.inlinecount, None)
                    resource.set_inlinecount(
                        inlinecount == core.InlineCount.allpages)
                    return self.ReturnEntityCollection(
                        resource,
                        request,
                        environ,
                        start_response,
                        response_headers)
                elif (method == "POST" and
                        resource.is_medialink_collection()):
                    # POST of a media resource
                    sinfo = core.StreamInfo()
                    if "CONTENT_TYPE" in environ:
                        sinfo.type = params.MediaType.from_str(
                            environ["CONTENT_TYPE"])
                    if "HTTP_LAST_MODIFIED" in environ:
                        sinfo.modified = params.FullDate.from_http_str(
                            environ["HTTP_LAST_MODIFIED"])
                    input = messages.WSGIInputWrapper(environ)
                    if "HTTP_SLUG" in environ:
                        slug = app.Slug(environ["HTTP_SLUG"])
                        # if the slug is a bracketed string treat it
                        # as the key predicate
                        key = None
                        kp = slug.slug.strip()
                        if kp and kp[0] == '(' and kp[-1] == ')':
                            try:
                                name, kp = core.ODataURI.SplitSegment(kp)
                                # kp is a dictionary for the entity key
                                key = resource.entity_set.get_key(kp)
                            except ValueError:
                                pass
                        if not key:
                            key = resource.entity_set.extract_key(slug.slug)
                    else:
                        slug = key = None
                    entity = resource.new_stream(input, sinfo=sinfo, key=key)
                    if slug:
                        for k, v in entity.data_items():
                            # catch property-level feed customisation here
                            propertyDef = entity.type_def[k]
                            if (propertyDef.get_target_path() ==
                                    [(atom.ATOM_NAMESPACE, "title")]):
                                entity[k].set_from_value(slug.slug)
                                resource.update_entity(entity)
                                break
                    response_headers.append(
                        ('Location', str(entity.get_location())))
                    return self.ReturnEntity(
                        entity,
                        request,
                        environ,
                        start_response,
                        response_headers,
                        201,
                        "Created")
                elif method == "POST":
                    # POST to an ordinary entity collection
                    entity = resource.new_entity()
                    # read the entity from the request
                    self.ReadEntity(entity, environ)
                    resource.insert_entity(entity)
                    response_headers.append(
                        ('Location', str(entity.get_location())))
                    return self.ReturnEntity(
                        entity,
                        request,
                        environ,
                        start_response,
                        response_headers,
                        201,
                        "Created")
                else:
                    raise core.InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.EDMValue):
                if method == "GET":
                    if request.pathOption == core.PathOption.value:
                        if resource:
                            return self.ReturnDereferencedValue(
                                parentEntity,
                                resource,
                                request,
                                environ,
                                start_response,
                                response_headers)
                        else:
                            raise core.MissingURISegment(
                                "%s (NULL)" % resource.p_def.name)
                    else:
                        return self.ReturnValue(
                            parentEntity,
                            resource,
                            request,
                            environ,
                            start_response,
                            response_headers)
                elif method == "PUT":
                    if request.pathOption == core.PathOption.value:
                        if resource:
                            self.ReadDereferencedValue(resource, environ)
                        else:
                            raise core.MissingURISegment(
                                "%s (NULL)" % resource.p_def.name)
                    else:
                        self.ReadValue(resource, environ)
                    parentEntity.commit()
                    self.set_etag(parentEntity, response_headers)
                    return self.ReturnEmpty(start_response, response_headers)
                elif method == "DELETE":
                    if request.pathOption == core.PathOption.value:
                        raise core.BadURISegment(
                            "$value cannot be used with DELETE")
                    # make this one NULL, only if it is nullable
                    if resource.p_def and not resource.p_def.nullable:
                        raise core.InvalidMethod(
                            "DELETE failed, %s property is not nullable" %
                            resource.p_def.name)
                    resource.value = None
                    parentEntity.commit()
                    return self.ReturnEmpty(start_response, response_headers)
                else:
                    raise core.InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.FunctionCollection):
                return self.ReturnCollection(
                    resource,
                    request,
                    environ,
                    start_response,
                    response_headers)
            else:
                # None or the DataService object: means we are trying to get
                # the service root
                responseType = self.ContentNegotiation(
                    request, environ, self.ServiceRootTypes)
                if responseType is None:
                    return self.ODataError(
                        request,
                        environ,
                        start_response,
                        "Not Acceptable",
                        'atomsvc+xml or json formats supported',
                        406)
                elif responseType == "application/json":
                    return self.ReturnJSONRoot(
                        request, environ, start_response, response_headers)
                else:
                    # override the default handling of service root to improve
                    # content negotiation
                    data = unicode(self.serviceDoc).encode('utf-8')
                    response_headers.append(
                        ("Content-Type", str(responseType)))
                    response_headers.append(("Content-Length", str(len(data))))
                    start_response("200 Ok", response_headers)
                    return [data]
        except core.MissingURISegment as e:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Resource not found",
                "Resource not found for segment %s" %
                str(e),
                404)
        except core.BadURISegment as e:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Bad Request",
                "Resource not found for segment %s" %
                str(e),
                400)
        except edm.NavigationError as e:
            return self.ODataError(
                request,
                environ,
                start_response,
                "NavigationError",
                str(e),
                403)
        except edm.ConstraintError as e:
            return self.ODataError(
                request,
                environ,
                start_response,
                "ConstraintError",
                str(e),
                403)
        except NotImplementedError as e:
            return self.ODataError(
                request,
                environ,
                start_response,
                "NotImplementedError",
                str(e),
                405)

    def ExpandResource(self, resource, sysQueryOptions):
        try:
            expand = sysQueryOptions.get(core.SystemQueryOption.expand, None)
            select = sysQueryOptions.get(core.SystemQueryOption.select, None)
            if expand is None and select is None:
                return
            if not isinstance(resource, (edm.EntityCollection, edm.Entity)):
                raise core.InvalidSystemQueryOption(
                    "$select/$expand not allowed")
            if isinstance(resource, edm.EntityCollection):
                resource.set_expand(expand, select)
            else:
                resource.expand(expand, select)
        except ValueError as e:
            raise core.InvalidSystemQueryOption(
                "$select/$expand error: %s" % str(e))

    def ReturnJSONRoot(
            self, request, environ, start_response, response_headers):
        data = str('{"d":%s}' % json.dumps(
            {'EntitySets': map(lambda x: x.href, self.ws.Collection)}))
        response_headers.append(("Content-Type", "application/json"))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReturnMetadata(
            self, request, environ, start_response, response_headers):
        doc = self.model.get_document()
        responseType = self.ContentNegotiation(
            request, environ, self.MetadataTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml or plain text formats supported',
                406)
        data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReturnLinks(
            self,
            entities,
            request,
            environ,
            start_response,
            response_headers):
        responseType = self.ContentNegotiation(
            request, environ, self.ValueTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml, json or plain text formats supported',
                406)
        if responseType == "application/json":
            data = str('{"d":%s}' % string.join(
                entities.generate_link_coll_json(request.version), ''))
        else:
            doc = core.Document(root=core.Links)
            for e in entities.itervalues():
                child = doc.root.add_child(core.URI)
                child.set_value(str(self.serviceRoot) + "%s(%s)" %
                                (e.entity_set.name, repr(e.key())))
            data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReadEntityFromLink(self, environ):
        input = self.ReadXMLOrJSON(environ)
        if isinstance(input, core.Document):
            if isinstance(input.root, core.URI):
                return self.GetResourceFromURI(
                    uri.URI.from_octets(input.root.get_value()))
            else:
                raise core.InvalidData(
                    "Unable to parse link from request body (found <%s>)" %
                    doc.root.xmlname)
        else:
            # must be a json object
            try:
                return self.GetResourceFromURI(
                    uri.URI.from_octets(input['uri']))
            except KeyError:
                raise core.InvalidData(
                    "Unable to parse link from JSON request body (found %s )" %
                    str(input)[
                        :256])

    def ReturnLink(
            self, entity, request, environ, start_response, response_headers):
        responseType = self.ContentNegotiation(
            request, environ, self.ValueTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml, json or plain text formats supported',
                406)
        if responseType == "application/json":
            data = str('{"d":%s}' % entity.link_json())
        else:
            doc = core.Document(root=core.URI)
            doc.root.set_value(str(entity.get_location()))
            data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReturnEntityCollection(
            self,
            entities,
            request,
            environ,
            start_response,
            response_headers):
        """Returns an iterable of Entities."""
        responseType = self.ContentNegotiation(
            request, environ, self.FeedTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml, json or plain text formats supported',
                406)
        entities.set_topmax(self.topmax)
        if responseType == "application/json":
            data = str('{"d":%s}' % string.join(
                entities.generate_entity_set_in_json(request.version), ''))
        else:
            # Here's a challenge, we want to pull data through the feed
            # by yielding strings just load in to memory at the moment
            f = core.Feed(None, entities)
            doc = core.Document(root=f)
            f.collection = entities
            f.set_base(str(self.serviceRoot))
            data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReadXMLOrJSON(self, environ):
        """Reads either an XML document or a JSON object from environ."""
        atomFlag = None
        encoding = None
        if "CONTENT_TYPE" in environ:
            requestType = params.MediaType.from_str(environ["CONTENT_TYPE"])
            for r in self.AtomRanges:
                if r.match_media_type(requestType):
                    atomFlag = True
                    break
            if atomFlag is None:
                for r in self.JSONRanges:
                    if r.match_media_type(requestType):
                        atomFlag = False
                        break
            encoding = requestType.parameters.get('charset', (None, None))[1]
        input = messages.WSGIInputWrapper(environ)
        unicodeInput = None
        if encoding is None:
            # read a line, at most 4 bytes
            encoding = detect_encoding(input.readline(4))
            if encoding is None:
                encoding = 'iso-8859-1'
            input.seek(0)
        if atomFlag is None:
            # we still need to figure out what we have here
            if encoding.lower() in ("utf_8", "utf-8"):
                unicodeInput = input
            else:
                unicodeInput = codecs.getreader(encoding)(input)
            b = '\x00'
            while ord(b) < 0x20:
                b = unicodeInput.read(1)
                if len(b) == 0:
                    # empty file
                    break
            if b == u'<':
                atomFlag = True
            elif b in u'{[':
                atomFlag = False
            else:
                raise core.InvalidData("Unable to parse request body")
            unicodeInput.seek(0)
        if atomFlag:
            # read atom file
            doc = core.Document()
            doc.read(src=xml.XMLEntity(src=input, encoding=encoding))
            return doc
        else:
            if unicodeInput is None:
                if encoding.lower() in ("utf_8", "utf-8"):
                    unicodeInput = input
                else:
                    unicodeInput = codecs.getreader(encoding)(input)
            return json.load(unicodeInput)

    def ReadEntity(self, entity, environ):
        input = self.ReadXMLOrJSON(environ)
        if isinstance(input, core.Document):
            if isinstance(input.root, core.Entry):
                # we have an entry, which is a relief!
                input.root.get_value(entity, self.GetResourceFromURI, True)
            else:
                raise core.InvalidData(
                    "Unable to parse atom Entry from request "
                    "body (found <%s>)" % doc.root.xmlname)
        else:
            # must be a json object
            entity.set_from_json_object(input, self.GetResourceFromURI, True)

    def ReturnEntity(self, entity, request, environ, start_response,
                     response_headers, status=200, statusMsg="Success"):
        """Returns a single Entity."""
        responseType = self.ContentNegotiation(
            request, environ, self.EntryTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml, json or plain text formats supported',
                406)
        # Here's a challenge, we want to pull data through the feed by
        # yielding strings just load in to memory at the moment
        if responseType == "application/json":
            data = str('{"d":%s}' %
                       string.join(entity.generate_entity_type_in_json(), ''))
        else:
            doc = core.Document(root=core.Entry)
            e = doc.root
            e.set_base(str(self.serviceRoot))
            e.set_value(entity)
            data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        self.set_etag(entity, response_headers)
        start_response("%i %s" % (status, statusMsg), response_headers)
        return [data]

    def ReturnStream(self, entity, request, environ, start_response,
                     response_headers, method):
        """Returns a media stream."""
        coll = entity.entity_set.open()
        try:
            if method == "GET":
                sinfo, sgen = coll.read_stream_close(entity.key())
            else:
                sinfo = coll.read_stream(entity.key())
                sgen = []
                coll.close()
        except Exception:
            coll.close()
            raise
        types = [sinfo.type] + self.StreamTypes
        responseType = self.ContentNegotiation(request, environ, types)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'media stream type refused, try application/octet-stream',
                406)
        response_headers.append(("Content-Type", str(responseType)))
        if sinfo.size is not None:
            response_headers.append(("Content-Length", str(sinfo.size)))
        if sinfo.modified is not None:
            response_headers.append(("Last-Modified",
                                     str(params.FullDate(src=sinfo.modified))))
        if sinfo.md5 is not None:
            response_headers.append(("Content-MD5",
                                     base64.b64encode(sinfo.md5)))
        self.set_etag(entity, response_headers)
        start_response("%i %s" % (200, "Success"), response_headers)
        return sgen

    def ReadValue(self, value, environ):
        input = self.ReadXMLOrJSON(environ)
        if isinstance(input, core.Document):
            if isinstance(input.root, core.Property):
                input.root.get_value(value)
            else:
                raise core.InvalidData(
                    "Unable to parse property from request body (found <%s>)" %
                    input.root.xmlname)
        else:
            if isinstance(value, edm.SimpleValue):
                core.ReadEntityPropertyInJSON1(value, input)
            else:
                core.ReadEntityCTInJSON(value, input)

    def ReturnValue(
            self,
            entity,
            value,
            request,
            environ,
            start_response,
            response_headers):
        """Returns a single property value."""
        responseType = self.ContentNegotiation(
            request, environ, self.ValueTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml, json or plain text formats supported',
                406)
        if responseType == "application/json":
            if isinstance(value, edm.Complex):
                if request.version == 2:
                    data = '{"d":%s}' % core.EntityCTInJSON2(value)
                else:
                    data = '{"d":%s}' % core.EntityCTInJSON(value)
            else:
                if request.version == 2:
                    # the spec goes a bit weird here, tripping up over
                    # brackets!
                    data = '{"d":%s}' % core.EntityPropertyInJSON2(value)
                else:
                    data = '{"d":{%s}}' % core.EntityPropertyInJSON(value)
        else:
            e = core.Property(None)
            e.set_xmlname((core.ODATA_DATASERVICES_NAMESPACE, value.p_def.name))
            doc = core.Document(root=e)
            e.set_value(value)
            data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        if entity is not None:
            self.set_etag(entity, response_headers)
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReadDereferencedValue(self, value, environ):
        encoding = None
        if "CONTENT_TYPE" in environ:
            requestType = params.MediaType.from_str(environ["CONTENT_TYPE"])
        if value.mtype is None:
            acceptType = False
            if isinstance(value, edm.BinaryValue):
                if requestType:
                    for r in DeferenceBinaryRanges:
                        if r.match_media_type(requestType):
                            acceptType = True
                else:
                    acceptType = True
            elif requestType:
                acceptType = messages.MediaRange.from_str(
                    "text/plain").match_media_type(requestType)
            else:
                # by default, http messages are iso-8859-1
                requestType = params.MediaType.from_str(
                    "text/plain; charset=iso-8859-1")
                acceptType = True
        else:
            if requestType:
                acceptType = messages.MediaRange.from_str(
                    value.mtype).match_media_type(requestType)
            else:
                # assume the user knows what they're doing!
                requestType = value.mtype
                acceptType = True
        if not acceptType:
            raise core.InvalidData(
                "Unable to parse property value from request "
                "body (found <%s>)" % str(requestType))
        data = messages.WSGIInputWrapper(environ).read()
        if requestType.type == "text":
            encoding = requestType.parameters.get('charset', (None, None))[1]
            if encoding is None:
                encoding = "iso-8859-1"
            data = data.decode(encoding)
        if isinstance(value, edm.BinaryValue):
            value.value = data
        else:
            value.set_from_literal(data)

    def ReturnDereferencedValue(
            self,
            entity,
            value,
            request,
            environ,
            start_response,
            response_headers):
        """Returns a dereferenced property value."""
        if value.mtype is None:
            if isinstance(value, edm.BinaryValue):
                mTypes = self.StreamTypes
                data = value.value
            else:
                mTypes = self.DereferenceTypes
                data = unicode(value).encode('utf-8')
        else:
            mTypes = [value.mtype]
            data = unicode(value).encode('utf-8')
        responseType = self.ContentNegotiation(request, environ, mTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                '$value requires plain text or octet-stream formats',
                406)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        if entity is not None:
            self.set_etag(entity, response_headers)
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReturnCollection(
            self,
            collection,
            request,
            environ,
            start_response,
            response_headers):
        """Returns a collection of values."""
        responseType = self.ContentNegotiation(
            request, environ, self.ValueTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'xml, json or plain text formats supported',
                406)
        if responseType == "application/json":
            data = '{"d":%s}' % string.join(
                collection.GenerateCollectionInJSON(request.version))
        else:
            e = core.Collection(None)
            e.set_xmlname((core.ODATA_METADATA_NAMESPACE, collection.name))
            doc = core.Document(root=e)
            for value in collection:
                p = e.add_child(core.Property)
                p.set_xmlname((core.ODATA_DATASERVICES_NAMESPACE,
                               value.p_def.name))
                p.set_value(value)
            data = str(doc)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReturnCount(
            self, number, request, environ, start_response, response_headers):
        """Returns the single value number."""
        responseType = self.ContentNegotiation(
            request, environ, self.DereferenceTypes)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                '$count requires plain text or octet-stream formats',
                406)
        data = str(number)
        response_headers.append(("Content-Type", str(responseType)))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), response_headers)
        return [data]

    def ReturnEmpty(
            self,
            start_response,
            response_headers,
            status=204,
            statusMsg="No content"):
        """Returns no content."""
        response_headers.append(("Content-Length", "0"))
        start_response("%i %s" % (status, statusMsg), response_headers)
        return []

    def ContentNegotiation(self, request, environ, mtype_list):
        """Returns the best match for the Accept header.

        Given a list of media types, examines the Accept header and
        returns the best match.  If there is no match then None is
        returned.  We also handle an accept list override in the form of
        acceptList, e.g., parsed from the $format parameter."""
        alist = request.sysQueryOptions.get(core.SystemQueryOption.format,
                                            None)
        if alist is None:
            if "HTTP_ACCEPT" in environ:
                try:
                    alist = messages.AcceptList.from_str(
                        environ["HTTP_ACCEPT"])
                except grammar.BadSyntax:
                    # we'll treat this as a missing Accept header
                    alist = self.DefaultAcceptList
            else:
                alist = self.DefaultAcceptList
        returnType = alist.select_type(mtype_list)
        logging.debug("Content negotiation request: %s", str(alist))
        logging.debug("Content negotiation result: picked %s from %s", repr(
            returnType), repr(mtype_list))
        return returnType

    def CheckCapabilityNegotiation(
            self, environ, start_response, response_headers):
        """Checks if we can handle this request

        Sets the protocol version in *response_headers* if we can handle
        this request.

        Returns None if the application should continue to handle the
        request, otherwise it returns an iterable object suitable for
        the wsgi return value.

        response_headers
            a list which contains the proposed response headers.

        In the event of a protocol version mismatch a "400
        DataServiceVersion mismatch" error response is generated."""
        ua = sa = None
        if "HTTP_DATASERVICEVERSION" in environ:
            major, minor, ua = core.ParseDataServiceVersion(
                environ["HTTP_DATASERVICEVERSION"])
        else:
            major = 2
            minor = 0
        if "HTTP_MAXDATASERVICEVERSION" in environ:
            maxMajor, maxMinor, sa = core.ParseMaxDataServiceVersion(
                environ["HTTP_MAXDATASERVICEVERSION"])
        else:
            maxMajor = major
            maxMinor = minor
        if major > 2 or (major == 2 and minor > 0):
            # we can't cope with this request
            return None
        elif maxMajor >= 2:
            response_headers.append(
                ('DataServiceVersion', '2.0; pyslet %s' % info.version))
            return 2
        else:
            response_headers.append(
                ('DataServiceVersion', '1.0; pyslet %s' % info.version))
            return 1


class ReadOnlyServer(Server):

    def HandleRequest(
            self,
            request,
            environ,
            start_response,
            response_headers):
        """Handles an OData request.

        *request*
            An :py:class:`core.ODataURI` instance with a non-empty
            resourcePath.

        If the method is anything other than GET or HEAD a 403 response
        is returned"""
        method = environ["REQUEST_METHOD"].upper()
        if method in ("GET", "HEAD"):
            return super(ReadOnlyServer, self).HandleRequest(
                request, environ, start_response, response_headers)
        else:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Unauthorised",
                "Method not allowed",
                403)
