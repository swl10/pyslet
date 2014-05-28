#! /usr/bin/env python
"""OData server implementation."""

from types import *
import sys
import cgi
import urllib
import string
import itertools
import traceback
import StringIO
import json
import base64
import decimal
import uuid
import math
import warnings
import logging

import pyslet.info as info
import pyslet.iso8601 as iso
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.rfc2616 as http
import pyslet.rfc2396 as uri
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
from pyslet.unicode5 import CharClass, DetectEncoding
import csdl as edm

from core import *
import metadata as edmx


class WSGIWrapper(object):

    def __init__(self, environ, start_response, responseHeaders):
        """A simple wrapper class for a wsgi application.

        Allows additional responseHeaders to be added to the wsgi response."""
        self.environ = environ
        self.start_response = start_response
        self.responseHeaders = responseHeaders

    def call(self, application):
        """Calls wsgi *application*"""
        return application(self.environ, self.start_response_wrapper)

    def start_response_wrapper(self, status, response_headers, exc_info=None):
        """Traps start_response and adds the additional headers."""
        response_headers = response_headers + self.responseHeaders
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
        http.MediaRange.FromString('application/atom+xml'),
        http.MediaRange.FromString('application/xml'),
        http.MediaRange.FromString('text/xml')]

    JSONRanges = [
        http.MediaRange.FromString('application/json')
    ]

    DefaultAcceptList = http.AcceptList.FromString(
        "application/atom+xml, "
        "application/atomsvc+xml, "
        "application/xml; q=0.9, "
        "text/xml; q=0.8, "
        "text/plain; q=0.7, "
        "*/*; q=0.6")

    ErrorTypes = [
        http.MediaType.FromString('application/atom+xml'),
        http.MediaType.FromString('application/xml'),
        http.MediaType.FromString('application/json')]

    RedirectTypes = [
        http.MediaType.FromString('text/html'),
        http.MediaType.FromString('text/plain'),
        http.MediaType.FromString('application/xml')]

    FeedTypes = [		# in order of preference if there is a tie
        http.MediaType.FromString('application/atom+xml'),
        http.MediaType.FromString('application/atom+xml;type=feed'),
        http.MediaType.FromString('application/xml'),
        http.MediaType.FromString('text/xml'),
        http.MediaType.FromString('application/json'),
        http.MediaType.FromString('text/plain')]

    EntryTypes = [  # in order of preference if there is a tie
        http.MediaType.FromString('application/atom+xml'),
        http.MediaType.FromString('application/atom+xml;type=entry'),
        http.MediaType.FromString('application/xml'),
        http.MediaType.FromString('text/xml'),
        http.MediaType.FromString('application/json'),
        http.MediaType.FromString('text/plain')]

    ValueTypes = [  # in order of preference if there is a tie
        http.MediaType.FromString('application/xml'),
        http.MediaType.FromString('text/xml'),
        http.MediaType.FromString('application/json'),
        http.MediaType.FromString('text/plain')]

    ServiceRootTypes = [  # in order of preference if there is a tie
        http.MediaType.FromString('application/atomsvc+xml'),
        http.MediaType.FromString('application/json'),
        http.MediaType.FromString('application/xml'),
        http.MediaType.FromString('text/plain')]

    MetadataTypes = [  # in order of preference if there is a tie
        http.MediaType.FromString('application/xml'),
        http.MediaType.FromString('text/xml'),
        http.MediaType.FromString('text/plain')]

    DereferenceBinaryRanges = [
        http.MediaRange.FromString('application/octet-stream'),
        http.MediaRange.FromString('octet/stream')]

    DereferenceTypes = [  # in order of preference
        http.MediaType.FromString('text/plain;charset=utf-8'),
        http.MediaType.FromString('application/octet-stream'),
        http.MediaType.FromString('octet/stream')]
    # we allow the last one in case someone read the spec literally!

    StreamTypes = [
        http.MediaType.FromString('application/octet-stream'),
        http.MediaType.FromString('octet/stream')]
    # we allow the last one in case someone read the spec literally!

    def __init__(self, serviceRoot="http://localhost"):
        if serviceRoot[-1] != '/':
            serviceRoot = serviceRoot + '/'
        app.Server.__init__(self, serviceRoot)
        if self.serviceRoot.relPath is not None:
            # The service root must be absolute (or missing completely)!
            raise ValueError("serviceRoot must not be relative")
        if self.serviceRoot.absPath is None:
            self.pathPrefix = ''
        else:
            self.pathPrefix = self.serviceRoot.absPath
        # pathPrefix must not have a tailing slash, even if this makes it an
        # empty string
        if self.pathPrefix[-1] == '/':
            self.pathPrefix = self.pathPrefix[:-1]
        # : a single workspace that contains all collections
        self.ws = self.service.ChildElement(app.Workspace)
        self.ws.ChildElement(atom.Title).SetValue("Default")
        #: a :py:class:`metadata.Edmx` instance; the model for the service
        self.model = None
        #: the maximum number of entities to return per request
        self.topmax = 100

    def SetModel(self, model):
        """Sets the model for the server from a parentless
        :py:class:`~pyslet.odatav2_metadata.Edmx` instance or an Edmx
        :py:class:`~pyslet.odatav2_metadata.Document` instance."""
        if isinstance(model, edmx.Document):
            doc = model
            model = model.root
        elif isinstance(model, edmx.Edmx):
            # create a document to hold the model
            doc = edmx.Document(root=model)
        else:
            raise TypeError("Edmx document or instance required for model")
        # update the base URI of the metadata document to identify this service
        doc.SetBase(self.serviceRoot)
        if self.model:
            # get rid of the old model
            for c in self.ws.Collection:
                c.DetachFromDocument()
                c.parent = None
            self.ws.Collection = []
        for s in model.DataServices.Schema:
            for container in s.EntityContainer:
                if container.IsDefaultEntityContainer():
                    prefix = ""
                else:
                    prefix = container.name + "."
                # define one feed for each entity set, prefixed with the name
                # of the entity set
                for es in container.EntitySet:
                    feed = self.ws.ChildElement(app.Collection)
                    feed.href = prefix + es.name
                    feed.ChildElement(atom.Title).SetValue(prefix + es.name)
                    # update the locations following SetBase above
                    es.SetLocation()
        self.model = model

    def __call__(self, environ, start_response):
        """wsgi interface for the server."""
        responseHeaders = []
        try:
            version = self.CheckCapabilityNegotiation(
                environ, start_response, responseHeaders)
            if version is None:
                return self.ODataError(
                    ODataURI('error'),
                    environ,
                    start_response,
                    "DataServiceVersionMismatch",
                    "Maximum supported protocol version: 2.0")
            appPath = environ.get('SCRIPT_NAME', "")
            path = appPath + environ['PATH_INFO']
            query = environ.get('QUERY_STRING', None)
            if query is not None:
                path = path + '?' + query
            request = ODataURI(path, self.pathPrefix, version)
            if request.resourcePath is None:
                # this is not a URI for us, pass to our superclass
                wrapper = WSGIWrapper(environ, start_response, responseHeaders)
                # super essentially allows us to pass a bound method of
                # our parent that we ourselves are hiding.
                return wrapper.call(super(Server, self).__call__)
            elif request.resourcePath == '':
                # An empty resource path means they hit the service root,
                # redirect
                location = str(self.serviceRoot)
                r = html.HTML(None)
                r.Head.Title.SetValue('Redirect')
                div = r.Body.ChildElement(html.Div)
                div.AddData(u"Moved to: ")
                anchor = div.ChildElement(html.A)
                anchor.href = self.serviceRoot
                anchor.SetValue(location)
                responseType = self.ContentNegotiation(
                    request, environ, self.RedirectTypes)
                if responseType is None:
                    # this is a redirect response, default to text/plain anyway
                    responseType = http.MediaType.FromString('text/plain')
                if responseType == "text/plain":
                    data = str(r.RenderText())
                else:
                    data = str(r)
                responseHeaders.append(("Content-Type", str(responseType)))
                responseHeaders.append(("Content-Length", str(len(data))))
                responseHeaders.append(("Location", location))
                start_response(
                    "%i %s" % (307, "Temporary Redirect"), responseHeaders)
                return [data]
            else:
                return self.HandleRequest(
                    request, environ, start_response, responseHeaders)
        except InvalidSystemQueryOption as e:
            return self.ODataError(
                ODataURI('error'),
                environ,
                start_response,
                "InvalidSystemQueryOption",
                "Invalid System Query Option: %s" %
                str(e))
        except InvalidPathOption as e:
            return self.ODataError(
                ODataURI('error'),
                environ,
                start_response,
                "Bad Request",
                "Path option is invalid or "
                "incompatible with this form of URI: %s" % str(e),
                400)
        except InvalidMethod as e:
            return self.ODataError(
                ODataURI('error'),
                environ,
                start_response,
                "Bad Request",
                "Method not allowed: %s" %
                str(e),
                400)
        except ValueError as e:
            traceback.print_exception(*sys.exc_info())
            # This is a bad request
            return self.ODataError(
                ODataURI('error'),
                environ,
                start_response,
                "ValueError",
                str(e))
        except:
            eInfo = sys.exc_info()
            traceback.print_exception(*eInfo)
            # return self.HandleError(ODataURI('error'),environ,start_response)
            return self.ODataError(
                ODataURI('error'),
                environ,
                start_response,
                "UnexpectedError",
                "%s: %s" %
                (eInfo[0],
                 eInfo[1]),
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
        responseHeaders = []
        e = Error(None)
        e.ChildElement(Code).SetValue(subCode)
        e.ChildElement(Message).SetValue(message)
        responseType = self.ContentNegotiation(
            request, environ, self.ErrorTypes)
        if responseType is None:
            # this is an error response, default to text/plain anyway
            responseType = http.MediaType.FromString('text/plain')
        elif responseType == "application/atom+xml":
            # even if you didn't ask for it, you get application/xml in this
            # case
            responseType = "application/xml"
        if responseType == "application/json":
            data = str(string.join(e.GenerateStdErrorJSON(), ''))
        else:
            data = str(e)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (code, subCode), responseHeaders)
        return [data]

    def GetResourceFromURI(self, href):
        """Returns the resource object represented by *href*

        href
            A :py:class:`pyslet.rfc2396.URI` instance

        The URI must not use path, or system query options but must
        identify an enity set, entity, complex or simple value."""
        if not href.IsAbsolute():
            # resolve relative to the service root
            href = URIFactory.Resolve(self.serviceRoot, href)
        # check the canonical roots
        if not self.serviceRoot.GetCanonicalRoot().Match(
                href.GetCanonicalRoot()):
            # This isn't even for us
            return None
        request = ODataURI(href, self.pathPrefix)
        return self.GetResource(request)[0]

    def GetResource(self, odataURI):
        resource = self.model
        noNavPath = (resource is None)
        parentEntity = None
        for segment in odataURI.navPath:
            name, keyPredicate = segment
            if noNavPath:
                raise BadURISegment(name)
            if isinstance(resource, edmx.Edmx):
                try:
                    resource = resource.DataServices.SearchContainers(name)
                except KeyError as e:
                    raise MissingURISegment(str(e))
                if isinstance(resource, edm.FunctionImport):
                    # TODO: grab the params from the query string
                    resource = resource.Execute({})
                    # If this does not identify a collection of entities it
                    # must be the last path segment
                    if not isinstance(resource, edm.EntityCollection):
                        noNavPath = True
                        # 10-14 have identical constraints, treat them the same
                        odataURI.ValidateSystemQueryOptions(10)
                elif isinstance(resource, edm.EntitySet):
                    resource = resource.OpenCollection()
                else:
                    # not the right sort of thing
                    raise MissingURISegment(name)
                if isinstance(resource, edm.EntityCollection):
                    if keyPredicate:
                        # the keyPredicate can be passed directly as the key
                        try:
                            collection = resource
                            resource = collection[
                                collection.entitySet.GetKey(keyPredicate)]
                            collection.close()
                        except KeyError as e:
                            raise MissingURISegment(
                                "%s%s" %
                                (name, ODataURI.FormatKeyDict(keyPredicate)))
                elif resource is None:
                    raise MissingURISegment(name)
            elif isinstance(resource,
                            (edm.EntityCollection, edm.FunctionCollection)):
                # bad request, because the collection must be the last
                # thing in the path
                raise BadURISegment(
                    "%s since the object's parent is a collection" % name)
            elif isinstance(resource, edm.Entity):
                if name not in resource:
                    raise MissingURISegment(name)
                # set the parent entity
                parentEntity = resource
                resource = resource[name]
                if isinstance(resource, edm.DeferredValue):
                    if resource.isCollection:
                        if keyPredicate:
                            try:
                                with resource.OpenCollection() as collection:
                                    resource = collection[
                                        collection.entitySet.GetKey(
                                            keyPredicate)]
                            except KeyError as e:
                                raise MissingURISegment(name)
                        else:
                            resource = resource.OpenCollection()
                    else:
                        # keyPredicate not allowed here!
                        if keyPredicate:
                            raise BadURISegment(
                                "%s (keyPredicate not allowed "
                                "for a navigation property that identifies a "
                                "single entity)" %
                                name)
                        resource = resource.GetEntity()
                        # if resource is None: See the resolution:
                        # https://tools.oasis-open.org/issues/browse/ODATA-412
            elif isinstance(resource, edm.Complex):
                if name in resource:
                    # This is a regular property of the ComplexType
                    resource = resource[name]
                else:
                    raise MissingURISegment(name)
            elif resource is None:
                raise MissingURISegment(
                    "%s, property cannot be resolved "
                    "as the parent entity does not exist" %
                    name)
            else:
                # Any other type is just a property or simple-type
                raise BadURISegment(name)
        if isinstance(resource, edm.EntityCollection):
            odataURI.ValidateSystemQueryOptions(1)  # includes 6 Note 2
        elif isinstance(resource, edm.Entity):
            if odataURI.pathOption == PathOption.value:
                odataURI.ValidateSystemQueryOptions(17)  # media resource value
            elif odataURI.pathOption != PathOption.links:
                odataURI.ValidateSystemQueryOptions(2)  # includes 6 Note 1
        elif isinstance(resource, edm.Complex):
            odataURI.ValidateSystemQueryOptions(3)
        elif isinstance(resource, edm.SimpleValue):
            # 4 & 5 are identical
            odataURI.ValidateSystemQueryOptions(4)
        elif resource is None and parentEntity is not None:
            # there is a very specific use case here, use of
            # <entity>/$links/<nav-et> where the link is NULL
            if not odataURI.pathOption == PathOption.links:
                # <entity>/<nav-et> where the link is NULL raises a 404
                # See the resolution:
                # https://tools.oasis-open.org/issues/browse/ODATA-412
                raise MissingURISegment(
                    "no entity is linked by this navigation property")
        return resource, parentEntity

    def SetETag(self, entity, responseHeaders):
        etag = entity.ETag()
        if etag is not None:
            s = "%s" if entity.ETagIsStrong() else "W/%s"
            etag = s % http.QuoteString(
                string.join(map(ODataURI.FormatLiteral, etag), ','))
            responseHeaders.append(("ETag", etag))

    def HandleRequest(self, request, environ, start_response, responseHeaders):
        """Handles an OData request.

        *request*
            An :py:class:`ODataURI` instance with a non-empty resourcePath."""
        method = environ["REQUEST_METHOD"].upper()
        try:
            resource, parentEntity = self.GetResource(request)
            if request.pathOption == PathOption.metadata:
                return self.ReturnMetadata(
                    request, environ, start_response, responseHeaders)
            elif request.pathOption == PathOption.batch:
                return self.ODataError(
                    request,
                    environ,
                    start_response,
                    "Bad Request",
                    "Batch requests not supported",
                    404)
            elif request.pathOption == PathOption.count:
                if isinstance(resource, edm.Entity):
                    return self.ReturnCount(
                        1, request, environ, start_response, responseHeaders)
                elif isinstance(resource, edm.EntityCollection):
                    return self.ReturnCount(
                        len(resource),
                        request,
                        environ,
                        start_response,
                        responseHeaders)
                else:
                    raise BadURISegment(
                        "$count must be applied to "
                        "an EntitySet or single EntityType instance")
            elif request.pathOption == PathOption.links:
                # parentEntity will be source entity
                # request.linksProperty is the name of the navigation
                # property in the source entity
                # resource will be the target entity, a collection or
                # None
                if not isinstance(parentEntity, Entity):
                    raise BadURISegment("$links must be preceded by a "
                                        "single EntityType instance")
                if method == "GET":
                    # open the collection and select the key properties only
                    if isinstance(resource, edm.EntityCollection):
                        with resource as collection:
                            collection.SelectKeys()
                            collection.SetPage(
                                request.sysQueryOptions.get(
                                    SystemQueryOption.top, None),
                                request.sysQueryOptions.get(
                                    SystemQueryOption.skip, None),
                                request.sysQueryOptions.get(
                                    SystemQueryOption.skiptoken, None))
                            inlineCount = request.sysQueryOptions.get(
                                SystemQueryOption.inlinecount, None)
                            collection.SetInlineCount(
                                inlineCount == InlineCount.allpages)
                            return self.ReturnLinks(
                                collection,
                                request,
                                environ,
                                start_response,
                                responseHeaders)
                    elif isinstance(resource, Entity):
                        # should have just a single link
                        return self.ReturnLink(
                            resource,
                            request,
                            environ,
                            start_response,
                            responseHeaders)
                    else:
                        # resource is None - no linked entity
                        raise MissingURISegment(
                            "%s, no entity is related" % request.linksProperty)
                elif method == "POST":
                    if resource is None:
                        # can you POST to Orders(1)/$links/Customer ? - only if
                        # it is currently NULL (0..1)
                        resource = parentEntity[
                            request.linksProperty].OpenCollection()
                    if isinstance(resource, edm.EntityCollection):
                        with resource as collection:
                            targetEntity = self.ReadEntityFromLink(environ)
                            collection[targetEntity.Key()] = targetEntity
                        return self.ReturnEmpty(
                            start_response, responseHeaders)
                    else:
                        # you can't POST to a single link that already exists
                        raise BadURISegment("%s is already linked, use PUT "
                                            "instead of POST to update it" %
                                            request.linksProperty)
                elif method == "PUT":
                    if parentEntity[request.linksProperty].isCollection:
                        raise BadURISegment(
                            "%s: can't update a link with multiplicity *" %
                            request.linksProperty)
                    with parentEntity[
                            request.linksProperty].OpenCollection() as \
                            collection:
                        targetEntity = self.ReadEntityFromLink(environ)
                        collection.Replace(targetEntity)
                    return self.ReturnEmpty(start_response, responseHeaders)
                elif method == "DELETE":
                    if isinstance(resource, edm.EntityCollection):
                        raise BadURISegment(
                            "%s: DELETE must specify a single link" %
                            request.linksProperty)
                    elif resource is None:
                        raise MissingURISegment(
                            "%s, no entity is related" % request.linksProperty)
                    with parentEntity[
                            request.linksProperty].OpenCollection() as \
                            collection:
                        del collection[resource.Key()]
                    return self.ReturnEmpty(start_response, responseHeaders)
                else:
                    raise InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.Entity):
                if method == "GET":
                    if request.pathOption == PathOption.value:
                        if resource.typeDef.HasStream():
                            return self.ReturnStream(
                                resource,
                                request,
                                environ,
                                start_response,
                                responseHeaders)
                        else:
                            raise BadURISegment(
                                "$value cannot be used since "
                                "the entity is not a media stream")
                    else:
                        self.ExpandResource(resource, request.sysQueryOptions)
                        return self.ReturnEntity(
                            resource,
                            request,
                            environ,
                            start_response,
                            responseHeaders)
                elif method == "PUT":
                    if request.pathOption == PathOption.value:
                        if resource.typeDef.HasStream():
                            if "CONTENT_TYPE" in environ:
                                resourceType = http.MediaType.FromString(
                                    environ["CONTENT_TYPE"])
                            else:
                                resourceType = http.MediaType.FromString(
                                    'application/octet-stream')
                            input = app.InputWrapper(environ)
                            resource.SetStreamFromGenerator(
                                resourceType, input.iterblocks())
                            self.SetETag(resource, responseHeaders)
                            return self.ReturnEmpty(
                                start_response, responseHeaders)
                        else:
                            raise BadURISegment(
                                "$value cannot be used since the entity is "
                                "not a media stream")
                    else:
                        # update the entity from the request
                        self.ReadEntity(resource, environ)
                        resource.Update()
                        # now we've updated the entity it is safe to calculate
                        # the ETag
                        self.SetETag(resource, responseHeaders)
                        return self.ReturnEmpty(
                            start_response, responseHeaders)
                elif method == "DELETE":
                    if request.pathOption == PathOption.value:
                        raise BadURISegment(
                            "$value cannot be used with DELETE")
                    resource.Delete()
                    return self.ReturnEmpty(start_response, responseHeaders)
                else:
                    raise InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.EntityCollection):
                if method == "GET":
                    self.ExpandResource(resource, request.sysQueryOptions)
                    resource.Filter(
                        request.sysQueryOptions.get(
                            SystemQueryOption.filter,
                            None))
                    resource.OrderBy(
                        request.sysQueryOptions.get(
                            SystemQueryOption.orderby,
                            None))
                    resource.SetPage(
                        request.sysQueryOptions.get(
                            SystemQueryOption.top, None),
                        request.sysQueryOptions.get(
                            SystemQueryOption.skip, None),
                        request.sysQueryOptions.get(
                            SystemQueryOption.skiptoken, None))
                    inlineCount = request.sysQueryOptions.get(
                        SystemQueryOption.inlinecount, None)
                    resource.SetInlineCount(
                        inlineCount == InlineCount.allpages)
                    return self.ReturnEntityCollection(
                        resource,
                        request,
                        environ,
                        start_response,
                        responseHeaders)
                elif (method == "POST" and
                      resource.IsMediaLinkEntryCollection()):
                    # POST of a media resource
                    entity = resource.NewEntity()
                    if "HTTP_SLUG" in environ:
                        slug = environ["HTTP_SLUG"]
                        for k, v in entity.DataItems():
                            # catch property-level feed customisation here
                            propertyDef = entity.typeDef[k]
                            if (propertyDef.GetTargetPath() ==
                                    [(atom.ATOM_NAMESPACE, "title")]):
                                entity[k].SetFromValue(slug)
                                break
                    resource.InsertEntity(entity)
                    if "CONTENT_TYPE" in environ:
                        resourceType = http.MediaType.FromString(
                            environ["CONTENT_TYPE"])
                    else:
                        resourceType = http.MediaType.FromString(
                            'application/octet-stream')
                    input = app.InputWrapper(environ)
                    entity.SetStreamFromGenerator(
                        resourceType, input.iterblocks())
                    responseHeaders.append(
                        ('Location', str(entity.GetLocation())))
                    return self.ReturnEntity(
                        entity,
                        request,
                        environ,
                        start_response,
                        responseHeaders,
                        201,
                        "Created")
                elif method == "POST":
                    # POST to an ordinary entity collection
                    entity = resource.NewEntity()
                    # read the entity from the request
                    self.ReadEntity(entity, environ)
                    resource.InsertEntity(entity)
                    responseHeaders.append(
                        ('Location', str(entity.GetLocation())))
                    return self.ReturnEntity(
                        entity,
                        request,
                        environ,
                        start_response,
                        responseHeaders,
                        201,
                        "Created")
                else:
                    raise InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.EDMValue):
                if method == "GET":
                    if request.pathOption == PathOption.value:
                        if resource:
                            return self.ReturnDereferencedValue(
                                parentEntity,
                                resource,
                                request,
                                environ,
                                start_response,
                                responseHeaders)
                        else:
                            raise MissingURISegment(
                                "%s (NULL)" % resource.pDef.name)
                    else:
                        return self.ReturnValue(
                            parentEntity,
                            resource,
                            request,
                            environ,
                            start_response,
                            responseHeaders)
                elif method == "PUT":
                    if request.pathOption == PathOption.value:
                        if resource:
                            self.ReadDereferencedValue(resource, environ)
                        else:
                            raise MissingURISegment(
                                "%s (NULL)" % resource.pDef.name)
                    else:
                        self.ReadValue(resource, environ)
                    parentEntity.Update()
                    self.SetETag(parentEntity, responseHeaders)
                    return self.ReturnEmpty(start_response, responseHeaders)
                elif method == "DELETE":
                    if request.pathOption == PathOption.value:
                        raise BadURISegment(
                            "$value cannot be used with DELETE")
                    # make this one NULL, only if it is nullable
                    if resource.pDef and not resource.pDef.nullable:
                        raise InvalidMethod(
                            "DELETE failed, %s property is not nullable" %
                            resource.pDef.name)
                    resource.value = None
                    parentEntity.Update()
                    return self.ReturnEmpty(start_response, responseHeaders)
                else:
                    raise InvalidMethod("%s not supported here" % method)
            elif isinstance(resource, edm.FunctionCollection):
                return self.ReturnCollection(
                    resource,
                    request,
                    environ,
                    start_response,
                    responseHeaders)
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
                        request, environ, start_response, responseHeaders)
                else:
                    # override the default handling of service root to improve
                    # content negotiation
                    data = unicode(self.serviceDoc).encode('utf-8')
                    responseHeaders.append(("Content-Type", str(responseType)))
                    responseHeaders.append(("Content-Length", str(len(data))))
                    start_response("200 Ok", responseHeaders)
                    return [data]
        except MissingURISegment as e:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Resource not found",
                "Resource not found for segment %s" %
                str(e),
                404)
        except BadURISegment as e:
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
            expand = sysQueryOptions.get(SystemQueryOption.expand, None)
            select = sysQueryOptions.get(SystemQueryOption.select, None)
            if expand is None and select is None:
                return
            if not isinstance(resource, (EntityCollection, Entity)):
                raise InvalidSystemQueryOption("$select/$expand not allowed")
            resource.Expand(expand, select)
        except ValueError as e:
            raise InvalidSystemQueryOption(
                "$select/$expand error: %s" % str(e))

    def ReturnJSONRoot(
            self, request, environ, start_response, responseHeaders):
        data = str('{"d":%s}' % json.dumps(
            {'EntitySets': map(lambda x: x.href, self.ws.Collection)}))
        responseHeaders.append(("Content-Type", "application/json"))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReturnMetadata(
            self, request, environ, start_response, responseHeaders):
        doc = self.model.GetDocument()
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
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReturnLinks(
            self, entities, request, environ, start_response, responseHeaders):
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
                entities.GenerateLinkCollJSON(request.version), ''))
        else:
            doc = Document(root=Links)
            for e in entities.itervalues():
                child = doc.root.ChildElement(URI)
                child.SetValue(str(self.serviceRoot) + "%s(%s)" %
                               (e.entitySet.name, repr(e.Key())))
            data = str(doc)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReadEntityFromLink(self, environ):
        input = self.ReadXMLOrJSON(environ)
        if isinstance(input, Document):
            if isinstance(input.root, URI):
                return self.GetResourceFromURI(
                    uri.URIFactory.URI(input.root.GetValue()))
            else:
                raise InvalidData(
                    "Unable to parse link from request body (found <%s>)" %
                    doc.root.xmlname)
        else:
            # must be a json object
            try:
                return self.GetResourceFromURI(
                    uri.URIFactory.URI(input['uri']))
            except KeyError:
                raise InvalidData(
                    "Unable to parse link from JSON request body (found %s )" %
                    str(input)[
                        :256])

    def ReturnLink(
            self, entity, request, environ, start_response, responseHeaders):
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
            data = str('{"d":%s}' % entity.LinkJSON())
        else:
            doc = Document(root=URI)
            doc.root.SetValue(str(entity.GetLocation()))
            data = str(doc)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReturnEntityCollection(
            self, entities, request, environ, start_response, responseHeaders):
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
        if responseType == "application/json":
            data = str('{"d":%s}' % string.join(
                entities.GenerateEntitySetInJSON(request.version), ''))
        else:
            # Here's a challenge, we want to pull data through the feed
            # by yielding strings just load in to memory at the moment
            entities.TopMax(self.topmax)
            f = Feed(None, entities)
            doc = Document(root=f)
            f.collection = entities
            f.SetBase(str(self.serviceRoot))
            data = str(doc)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReadXMLOrJSON(self, environ):
        """Reads either an XML document or a JSON object from environ."""
        atomFlag = None
        encoding = None
        if "CONTENT_TYPE" in environ:
            requestType = http.MediaType.FromString(environ["CONTENT_TYPE"])
            for r in self.AtomRanges:
                if r.MatchMediaType(requestType):
                    atomFlag = True
                    break
            if atomFlag is None:
                for r in self.JSONRanges:
                    if r.MatchMediaType(requestType):
                        atomFlag = False
                        break
            encoding = requestType.parameters.get('charset', (None, None))[1]
        input = app.InputWrapper(environ)
        unicodeInput = None
        if encoding is None:
            # read a line, at most 4 bytes
            encoding = DetectEncoding(input.readline(4))
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
                raise InvalidData("Unable to parse request body")
            unicodeInput.seek(0)
        if atomFlag:
            # read atom file
            doc = Document()
            doc.Read(src=xml.XMLEntity(src=input, encoding=encoding))
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
        if isinstance(input, Document):
            if isinstance(input.root, Entry):
                # we have an entry, which is a relief!
                input.root.GetValue(entity, self.GetResourceFromURI, True)
            else:
                raise InvalidData("Unable to parse atom Entry from request "
                                  "body (found <%s>)" % doc.root.xmlname)
        else:
            # must be a json object
            entity.SetFromJSONObject(input, self.GetResourceFromURI, True)

    def ReturnEntity(self, entity, request, environ, start_response,
                     responseHeaders, status=200, statusMsg="Success"):
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
                       string.join(entity.GenerateEntityTypeInJSON(), ''))
        else:
            doc = Document(root=Entry)
            e = doc.root
            e.SetBase(str(self.serviceRoot))
            e.SetValue(entity)
            data = str(doc)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        self.SetETag(entity, responseHeaders)
        start_response("%i %s" % (status, statusMsg), responseHeaders)
        return [data]

    def ReturnStream(
            self, entity, request, environ, start_response, responseHeaders):
        """Returns a media stream."""
        types = [entity.GetStreamType()] + self.StreamTypes
        responseType = self.ContentNegotiation(request, environ, types)
        if responseType is None:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Not Acceptable",
                'media stream type refused, try application/octet-stream',
                406)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", entity.GetStreamSize()))
        self.SetETag(entity, responseHeaders)
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return entity.GetStreamGenerator()

    def ReadValue(self, value, environ):
        input = self.ReadXMLOrJSON(environ)
        if isinstance(input, Document):
            if isinstance(input.root, Property):
                input.root.GetValue(value)
            else:
                raise InvalidData(
                    "Unable to parse property from request body (found <%s>)" %
                    doc.root.xmlname)
        else:
            if isinstance(value, edm.SimpleValue):
                ReadEntityPropertyInJSON1(value, input)
            else:
                ReadEntityCTInJSON(value, input)

    def ReturnValue(
            self,
            entity,
            value,
            request,
            environ,
            start_response,
            responseHeaders):
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
                    data = '{"d":%s}' % EntityCTInJSON2(value)
                else:
                    data = '{"d":%s}' % EntityCTInJSON(value)
            else:
                if request.version == 2:
                    # the spec goes a bit weird here, tripping up over
                    # brackets!
                    data = '{"d":%s}' % EntityPropertyInJSON2(value)
                else:
                    data = '{"d":{%s}}' % EntityPropertyInJSON(value)
        else:
            e = Property(None)
            e.SetXMLName((ODATA_DATASERVICES_NAMESPACE, value.pDef.name))
            doc = Document(root=e)
            e.SetValue(value)
            data = str(doc)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        if entity is not None:
            self.SetETag(entity, responseHeaders)
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReadDereferencedValue(self, value, environ):
        encoding = None
        if "CONTENT_TYPE" in environ:
            requestType = http.MediaType.FromString(environ["CONTENT_TYPE"])
        if value.mType is None:
            acceptType = False
            if isinstance(value, edm.BinaryValue):
                if requestType:
                    for r in DeferenceBinaryRanges:
                        if r.MatchMediaType(requestType):
                            acceptType = True
                else:
                    acceptType = True
            elif requestType:
                acceptType = http.MediaRange.FromString(
                    "text/plain").MatchMediaType(requestType)
            else:
                # by default, http messages are iso-8859-1
                requestType = http.MediaType.FromString(
                    "text/plain; charset=iso-8859-1")
                acceptType = True
        else:
            if requestType:
                acceptType = http.MediaRange.FromString(
                    value.mType).MatchMediaType(requestType)
            else:
                # assume the user knows what they're doing!
                requestType = value.mType
                acceptType = True
        if not acceptType:
            raise InvalidData("Unable to parse property value from request "
                              "body (found <%s>)" % str(requestType))
        data = app.InputWrapper(environ).read()
        if requestType.type == "text":
            encoding = requestType.parameters.get('charset', (None, None))[1]
            if encoding is None:
                encoding = "iso-8859-1"
            data = data.decode(encoding)
        if isinstance(value, edm.BinaryValue):
            value.value = data
        else:
            value.SetFromLiteral(data)

    def ReturnDereferencedValue(
            self,
            entity,
            value,
            request,
            environ,
            start_response,
            responseHeaders):
        """Returns a dereferenced property value."""
        if value.mType is None:
            if isinstance(value, edm.BinaryValue):
                mTypes = self.StreamTypes
                data = value.value
            else:
                mTypes = self.DereferenceTypes
                data = unicode(value).encode('utf-8')
        else:
            mTypes = [value.mType]
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
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        if entity is not None:
            self.SetETag(entity, responseHeaders)
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReturnCollection(
            self,
            collection,
            request,
            environ,
            start_response,
            responseHeaders):
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
            e = Collection(None)
            e.SetXMLName((ODATA_METADATA_NAMESPACE, collection.name))
            doc = Document(root=e)
            for value in collection:
                p = e.ChildElement(Property)
                p.SetXMLName((ODATA_DATASERVICES_NAMESPACE, value.pDef.name))
                p.SetValue(value)
            data = str(doc)
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReturnCount(
            self, number, request, environ, start_response, responseHeaders):
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
        responseHeaders.append(("Content-Type", str(responseType)))
        responseHeaders.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (200, "Success"), responseHeaders)
        return [data]

    def ReturnEmpty(
            self,
            start_response,
            responseHeaders,
            status=204,
            statusMsg="No content"):
        """Returns no content."""
        responseHeaders.append(("Content-Length", "0"))
        start_response("%i %s" % (status, statusMsg), responseHeaders)
        return []

    def ContentNegotiation(self, request, environ, mTypeList):
        """Returns the best match for the Accept header.

        Given a list of media types, examines the Accept header and
        returns the best match.  If there is no match then None is
        returned.  We also handle an accept list override in the form of
        acceptList, e.g., parsed from the $format parameter."""
        aList = request.sysQueryOptions.get(SystemQueryOption.format, None)
        if aList is None:
            if "HTTP_ACCEPT" in environ:
                try:
                    aList = http.AcceptList.FromString(environ["HTTP_ACCEPT"])
                except http.HTTPParameterError:
                    # we'll treat this as a missing Accept header
                    aList = self.DefaultAcceptList
            else:
                aList = self.DefaultAcceptList
        returnType = aList.SelectType(mTypeList)
        logging.debug("Content negotiation request: %s", str(aList))
        logging.debug("Content negotiation result: picked %s from %s", repr(
            returnType), repr(mTypeList))
        return returnType

    def CheckCapabilityNegotiation(
            self, environ, start_response, responseHeaders):
        """Checks if we can handle this request

        Sets the protocol version in *responseHeaders* if we can handle
        this request.

        Returns None if the application should continue to handle the
        request, otherwise it returns an iterable object suitable for
        the wsgi return value.

        responseHeaders
            a list which contains the proposed response headers.

        In the event of a protocol version mismatch a "400
        DataServiceVersion mismatch" error response is generated."""
        ua = sa = None
        if "HTTP_DATASERVICEVERSION" in environ:
            major, minor, ua = ParseDataServiceVersion(
                environ["HTTP_DATASERVICEVERSION"])
        else:
            major = 2
            minor = 0
        if "HTTP_MAXDATASERVICEVERSION" in environ:
            maxMajor, maxMinor, sa = ParseMaxDataServiceVersion(
                environ["HTTP_MAXDATASERVICEVERSION"])
        else:
            maxMajor = major
            maxMinor = minor
        if major > 2 or (major == 2 and minor > 0):
            # we can't cope with this request
            return None
        elif maxMajor >= 2:
            responseHeaders.append(
                ('DataServiceVersion', '2.0; pyslet %s' % info.version))
            return 2
        else:
            responseHeaders.append(
                ('DataServiceVersion', '1.0; pyslet %s' % info.version))
            return 1


class ReadOnlyServer(Server):

    def HandleRequest(self, request, environ, start_response, responseHeaders):
        """Handles an OData request.

        *request*
            An :py:class:`ODataURI` instance with a non-empty resourcePath.

        If the method is anything other than GET or HEAD a 403 response
        is returned"""
        method = environ["REQUEST_METHOD"].upper()
        if method in ("GET", "HEAD"):
            return super(ReadOnlyServer, self).HandleRequest(
                request, environ, start_response, responseHeaders)
        else:
            return self.ODataError(
                request,
                environ,
                start_response,
                "Unauthorised",
                "Method not allowed",
                403)
