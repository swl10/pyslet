#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

import sys
import urllib
import logging
import pyslet.info as info
import pyslet.rfc2396 as uri
import pyslet.rfc2616 as http
import pyslet.xml20081126.structures as xml
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app

import core
import csdl as edm
import metadata as edmx


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


class MediaLinkEntry(core.Entity):

    def __init__(self, entitySet, client):
        core.Entity.__init__(self, entitySet)
        self.client = client

    def GetStreamType(self):
        """Returns the content type of the entity's media stream by issuing a HEAD request."""
        streamURL = str(self.GetLocation()) + "/$value"
        request = http.HTTPRequest(str(streamURL), 'HEAD')
        request.SetHeader('Accept', '*/*')
        self.client.ProcessRequest(request)
        if request.status == 404:
            return None
        elif request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        return request.response.GetContentType()

    def GetStreamSize(self):
        """Returns the size of the entity's media stream in bytes by issuing a HEAD request."""
        streamURL = str(self.GetLocation()) + "/$value"
        request = http.HTTPRequest(str(streamURL), 'HEAD')
        request.SetHeader('Accept', '*/*')
        self.client.ProcessRequest(request)
        if request.status == 404:
            return None
        elif request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        return request.response.GetContentLength()

    def GetStreamGenerator(self):
        """A generator function that yields blocks (strings) of data from the entity's media stream."""
        streamURL = str(self.GetLocation()) + "/$value"
        request = http.HTTPRequest(str(streamURL), 'GET')
        request.SetHeader('Accept', '*/*')
        self.client.ProcessRequest(request)
        if request.status == 404:
            return
        elif request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        yield request.resBody


class ClientCollection(core.EntityCollection):

    def __init__(self, client, baseURI=None, **kwArgs):
        super(ClientCollection, self).__init__(**kwArgs)
        if baseURI is None:
            self.baseURI = self.entitySet.GetLocation()
        else:
            self.baseURI = baseURI
        self.client = client

    def NewEntity(self, autoKey=False):
        """Returns an OData aware instance"""
        if self.IsMediaLinkEntryCollection():
            return MediaLinkEntry(self.entitySet, self.client)
        else:
            return core.Entity(self.entitySet)

    def Expand(self, expand, select=None):
        """Sets the expand and select query options for this collection.

        We override this implementation to ensure that the keys are
        always selected in each entity set."""
        self.AddKeys(self.entitySet, expand, select)
        self.entitySet.entityType.ValidateExpansion(expand, select)
        self.expand = expand
        self.select = select

    @classmethod
    def AddKeys(cls, entitySet, expand, select):
        if select is None or u"*" in select:
            pass
        else:
            # force the keys to be in the selection
            for k in entitySet.keys:
                select[k] = None
        # now we look for anything that is being expanded
        if expand is not None:
            for np, expansion in expand.iteritems():
                if select and np in select:
                    # recurse
                    cls.AddKeys(
                        entitySet.NavigationTarget(np), expansion, select[np])
                else:
                    # not being expanded
                    pass

    def RaiseError(self, request):
        """Given a :py:class:`pyslet.rfc2616.HTTPRequest` object
        containing an unexpected status in the response, parses an error
        response and raises an error accordingly."""
        if request.status == 404:
            # translates in to a key error
            eType = KeyError
        elif request.status == 405:
            # indicates the URL doesn't support the operation, for example
            # an attempt to POST to a navigation property that the server
            # doesn't support perhaps
            eType = NotImplementedError
        elif request.status == 401:
            eType = AuthorizationRequired
        elif request.status >= 400 and request.status < 500:
            eType = edm.ConstraintError
        else:
            eType = UnexpectedHTTPResponse
        debugMsg = None
        if request.resBody:
            doc = core.Document()
            doc.Read(src=request.resBody)
            if isinstance(doc.root, core.Error):
                errorMsg = "%s: %s" % (
                    doc.root.Code.GetValue(), doc.root.Message.GetValue())
                if doc.root.InnerError is not None:
                    debugMsg = doc.root.InnerError.GetValue()
            else:
                errorMsg = request.response.reason
        else:
            errorMsg = request.response.reason
        if eType == KeyError:
            logging.info("404: %s", errorMsg)
        else:
            logging.info("%i: %s", request.status, errorMsg)
            if debugMsg:
                logging.debug(debugMsg)
        raise eType(errorMsg)

    def InsertEntity(self, entity):
        if entity.exists:
            raise edm.EntityExists(str(entity.GetLocation()))
        doc = core.Document(root=core.Entry(None, entity))
        data = str(doc)
        request = http.HTTPRequest(str(self.baseURI), 'POST', reqBody=data)
        request.SetContentType(
            http.MediaType.FromString(core.ODATA_RELATED_ENTRY_TYPE))
        self.client.ProcessRequest(request)
        if request.status == 201:
            # success, read the entity back from the response
            doc = core.Document()
            doc.Read(request.resBody)
            entity.exists = True
            doc.root.GetValue(entity)
            # so which bindings got handled?  Assume all of them
            for k, dv in entity.NavigationItems():
                dv.bindings = []
        else:
            self.RaiseError(request)

    def __len__(self):
        # use $count
        feedURL = self.baseURI
        sysQueryOptions = {}
        if self.filter is not None:
            sysQueryOptions[
                core.SystemQueryOption.filter] = unicode(self.filter)
        if sysQueryOptions:
            feedURL = uri.URIFactory.URI(
                str(feedURL) + "/$count?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
        else:
            feedURL = uri.URIFactory.URI(str(feedURL) + "/$count")
        request = http.HTTPRequest(str(feedURL))
        request.SetHeader('Accept', 'text/plain')
        self.client.ProcessRequest(request)
        if request.status == 200:
            return int(request.resBody)
        else:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))

    def entityGenerator(self):
        feedURL = self.baseURI
        sysQueryOptions = {}
        if self.filter is not None:
            sysQueryOptions[
                core.SystemQueryOption.filter] = unicode(self.filter)
        if self.expand is not None:
            sysQueryOptions[
                core.SystemQueryOption.expand] = core.FormatExpand(self.expand)
        if self.select is not None:
            sysQueryOptions[
                core.SystemQueryOption.select] = core.FormatSelect(self.select)
        if self.orderby is not None:
            sysQueryOptions[
                core.SystemQueryOption.orderby] = core.CommonExpression.OrderByToString(self.orderby)
        if sysQueryOptions:
            feedURL = uri.URIFactory.URI(
                str(feedURL) + "?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
        while True:
            request = http.HTTPRequest(str(feedURL))
            request.SetHeader('Accept', 'application/atom+xml')
            self.client.ProcessRequest(request)
            if request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(baseURI=feedURL)
            doc.Read(request.resBody)
            if isinstance(doc.root, atom.Feed):
                if len(doc.root.Entry):
                    for e in doc.root.Entry:
                        entity = core.Entity(self.entitySet)
                        entity.exists = True
                        e.GetValue(entity)
                        yield entity
                else:
                    break
            else:
                raise core.InvalidFeedDocument(str(feedURL))
            feedURL = None
            for link in doc.root.Link:
                if link.rel == "next":
                    feedURL = link.ResolveURI(link.href)
                    break
            if feedURL is None:
                break

    def itervalues(self):
        return self.entityGenerator()

    def TopMax(self, topmax):
        raise NotImplementedError("OData client can't override topmax")

    def SetPage(self, top, skip=0, skiptoken=None):
        self.top = top
        self.skip = skip
        self.skiptoken = skiptoken  # opaque in the client implementation

    def iterpage(self, setNextPage=False):
        feedURL = self.baseURI
        sysQueryOptions = {}
        if self.filter is not None:
            sysQueryOptions[
                core.SystemQueryOption.filter] = unicode(self.filter)
        if self.expand is not None:
            sysQueryOptions[
                core.SystemQueryOption.expand] = core.FormatExpand(self.expand)
        if self.select is not None:
            sysQueryOptions[
                core.SystemQueryOption.select] = core.FormatSelect(self.select)
        if self.orderby is not None:
            sysQueryOptions[
                core.SystemQueryOption.orderby] = core.CommonExpression.OrderByToString(self.orderby)
        if self.top is not None:
            sysQueryOptions[core.SystemQueryOption.top] = unicode(self.top)
        if self.skip is not None:
            sysQueryOptions[core.SystemQueryOption.skip] = unicode(self.skip)
        if self.skiptoken is not None:
            sysQueryOptions[core.SystemQueryOption.skiptoken] = self.skiptoken
        if sysQueryOptions:
            feedURL = uri.URIFactory.URI(
                str(feedURL) + "?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
        request = http.HTTPRequest(str(feedURL))
        request.SetHeader('Accept', 'application/atom+xml')
        self.client.ProcessRequest(request)
        if request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        doc = core.Document(baseURI=feedURL)
        doc.Read(request.resBody)
        if isinstance(doc.root, atom.Feed):
            if len(doc.root.Entry):
                for e in doc.root.Entry:
                    entity = core.Entity(self.entitySet)
                    entity.exists = True
                    e.GetValue(entity)
                    yield entity
            feedURL = self.nextSkiptoken = None
            for link in doc.root.Link:
                if link.rel == "next":
                    feedURL = link.ResolveURI(link.href)
                    break
            if feedURL is not None:
                # extract the skiptoken from this link
                feedURL = core.ODataURI(feedURL, self.client.pathPrefix)
                self.nextSkiptoken = feedURL.sysQueryOptions.get(
                    core.SystemQueryOption.skiptoken, None)
            if setNextPage:
                if self.nextSkiptoken is not None:
                    self.skiptoken = self.nextSkiptoken
                    self.skip = None
                elif self.skip is not None:
                    self.skip += len(doc.root.Entry)
                else:
                    self.skip = len(doc.root.Entry)
        else:
            raise core.InvalidFeedDocument(str(feedURL))

    def __getitem__(self, key):
        entityURL = str(
            self.baseURI) + core.ODataURI.FormatKeyDict(self.entitySet.GetKeyDict(key))
        sysQueryOptions = {}
        if self.filter is not None:
            sysQueryOptions[
                core.SystemQueryOption.filter] = unicode(self.filter)
        if self.expand is not None:
            sysQueryOptions[
                core.SystemQueryOption.expand] = core.FormatExpand(self.expand)
        if self.select is not None:
            sysQueryOptions[
                core.SystemQueryOption.select] = core.FormatSelect(self.select)
        if sysQueryOptions:
            entityURL = uri.URIFactory.URI(
                entityURL + "?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
        request = http.HTTPRequest(str(entityURL))
        request.SetHeader('Accept', 'application/atom+xml;type=entry')
        self.client.ProcessRequest(request)
        if request.status == 404:
            raise KeyError(key)
        elif request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        doc = core.Document(baseURI=entityURL)
        doc.Read(request.resBody)
        if isinstance(doc.root, atom.Entry):
            entity = core.Entity(self.entitySet)
            entity.exists = True
            doc.root.GetValue(entity)
            return entity
        elif isinstance(doc.root, core.Error):
            raise KeyError(key)
        else:
            raise core.InvalidEntryDocument(str(entityURL))


class EntityCollection(ClientCollection, core.EntityCollection):

    """An entity collection that provides access to entities stored
    remotely and accessed through *client*."""

    def UpdateEntity(self, entity):
        if not entity.exists:
            raise edm.NonExistentEntity(str(entity.GetLocation()))
        doc = core.Document(root=core.Entry)
        doc.root.SetValue(entity, True)
        data = str(doc)
        request = http.HTTPRequest(
            str(entity.GetLocation()), 'PUT', reqBody=data)
        request.SetContentType(
            http.MediaType.FromString(core.ODATA_RELATED_ENTRY_TYPE))
        self.client.ProcessRequest(request)
        if request.status == 204:
            # success, nothing to read back but we're not done
            # we've only updated links to existing entities on properties with
            # single cardinality
            for k, dv in entity.NavigationItems():
                if not dv.bindings or dv.isCollection:
                    continue
                # we need to know the location of the target entity set
                binding = dv.bindings[-1]
                if isinstance(binding, edm.Entity) and binding.exists:
                    dv.bindings = []
            # now use the default method to finish the job
            self.UpdateBindings(entity)
            return
        else:
            self.RaiseError(request)

    def __delitem__(self, key):
        entity = self.NewEntity()
        entity.SetKey(key)
        request = http.HTTPRequest(str(entity.GetLocation()), 'DELETE')
        self.client.ProcessRequest(request)
        if request.status == 204:
            # success, nothing to read back
            return
        else:
            self.RaiseError(request)


class NavigationCollection(ClientCollection, core.NavigationCollection):

    def __init__(self, fromEntity, name, **kwArgs):
        if kwArgs.pop('baseURI', None):
            logging.warn(
                'OData Client NavigationCollection ignored baseURI argument')
        navPath = uri.EscapeData(name.encode('utf-8'))
        location = str(fromEntity.GetLocation())
        super(NavigationCollection, self).__init__(fromEntity=fromEntity,
                                                   name=name, baseURI=uri.URIFactory.URI(location + "/" + navPath), **kwArgs)
        self.isCollection = self.fromEntity[name].isCollection
        self.linksURI = uri.URIFactory.URI(location + "/$links/" + navPath)

    def InsertEntity(self, entity):
        """Inserts *entity* into this collection.

        OData servers don't all support insert directly into a
        navigation property so we risk transactional inconsistency here
        by overriding the default implementation to performs a two stage
        insert/create link process unless this is a required link for
        *entity*, in which case we figure out the back-link, bind
        *fromEntity* and then do the reverse insert which is more likely
        to be supported.

        If there is no back-link we resort to an insert against the
        navigation property itself."""
        if self.fromEnd.associationEnd.multiplicity == edm.Multiplicity.One:
            # we're in trouble, entity can't exist without linking to us
            # so we try a deep link
            backLink = self.entitySet.linkEnds[self.fromEnd.otherEnd]
            if backLink:
                # there is a navigation property going back
                entity[backLink].BindEntity(self.fromEntity)
                with self.entitySet.OpenCollection() as baseCollection:
                    baseCollection.InsertEntity(entity)
                return
            elif self.isCollection:
                # if there is no back link we'll have to do an insert
                # into this end using a POST to the navigation property.
                # Surely anyone with a model like this will support such
                # an implicit link.
                return super(NavigationCollection, self).InsertEntity(entity)
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
                    "Can't insert an entity into a 1-(0..)1 relationship without a back-link")
        else:
            with self.entitySet.OpenCollection() as baseCollection:
                baseCollection.InsertEntity(entity)
                # this link may fail, which isn't what the caller wanted
                # but it seems like a bad idea to try deleting the
                # entity at this stage.
                self[entity.Key()] = entity

    def __len__(self):
        if self.isCollection:
            return super(NavigationCollection, self).__len__()
        else:
            # This is clumsy as we grab the entity itself
            entityURL = str(self.baseURI)
            sysQueryOptions = {}
            if self.filter is not None:
                sysQueryOptions[
                    core.SystemQueryOption.filter] = unicode(self.filter)
            if sysQueryOptions:
                entityURL = uri.URIFactory.URI(
                    entityURL + "?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
            request = http.HTTPRequest(str(entityURL))
            request.SetHeader('Accept', 'application/atom+xml;type=entry')
            self.client.ProcessRequest(request)
            if request.status == 404:
                # if we got a 404 from the underlying system we're done
                return 0
            elif request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(baseURI=entityURL)
            doc.Read(request.resBody)
            if isinstance(doc.root, atom.Entry):
                entity = core.Entity(self.entitySet)
                entity.exists = True
                doc.root.GetValue(entity)
                return 1
            else:
                raise core.InvalidEntryDocument(str(entityURL))

    def entityGenerator(self):
        if self.isCollection:
            for entity in super(NavigationCollection, self).entityGenerator():
                yield entity
        else:
            # The baseURI points to a single entity already, we must not add
            # the key
            entityURL = str(self.baseURI)
            sysQueryOptions = {}
            if self.filter is not None:
                sysQueryOptions[
                    core.SystemQueryOption.filter] = unicode(self.filter)
            if self.expand is not None:
                sysQueryOptions[
                    core.SystemQueryOption.expand] = core.FormatExpand(self.expand)
            if self.select is not None:
                sysQueryOptions[
                    core.SystemQueryOption.select] = core.FormatSelect(self.select)
            if sysQueryOptions:
                entityURL = uri.URIFactory.URI(
                    entityURL + "?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
            request = http.HTTPRequest(str(entityURL))
            request.SetHeader('Accept', 'application/atom+xml;type=entry')
            self.client.ProcessRequest(request)
            if request.status == 404:
                return
            elif request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(baseURI=entityURL)
            doc.Read(request.resBody)
            if isinstance(doc.root, atom.Entry):
                entity = core.Entity(self.entitySet)
                entity.exists = True
                doc.root.GetValue(entity)
                yield entity
            else:
                raise core.InvalidEntryDocument(str(entityURL))

    def __getitem__(self, key):
        if self.isCollection:
            return super(NavigationCollection, self).__getitem__(key)
        else:
            # The baseURI points to a single entity already, we must not add
            # the key
            entityURL = str(self.baseURI)
            sysQueryOptions = {}
            if self.filter is not None:
                sysQueryOptions[
                    core.SystemQueryOption.filter] = unicode(self.filter)
            if self.expand is not None:
                sysQueryOptions[
                    core.SystemQueryOption.expand] = core.FormatExpand(self.expand)
            if self.select is not None:
                sysQueryOptions[
                    core.SystemQueryOption.select] = core.FormatSelect(self.select)
            if sysQueryOptions:
                entityURL = uri.URIFactory.URI(
                    entityURL + "?" + core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
            request = http.HTTPRequest(str(entityURL))
            request.SetHeader('Accept', 'application/atom+xml;type=entry')
            self.client.ProcessRequest(request)
            if request.status == 404:
                raise KeyError(key)
            elif request.status != 200:
                raise UnexpectedHTTPResponse(
                    "%i %s" % (request.status, request.response.reason))
            doc = core.Document(baseURI=entityURL)
            doc.Read(request.resBody)
            if isinstance(doc.root, atom.Entry):
                entity = core.Entity(self.entitySet)
                entity.exists = True
                doc.root.GetValue(entity)
                if entity.Key() == key:
                    return entity
                else:
                    raise KeyError(key)
            elif isinstance(doc.root, core.Error):
                raise KeyError(key)
            else:
                raise core.InvalidEntryDocument(str(entityURL))

    def __setitem__(self, key, entity):
        if not isinstance(entity, edm.Entity) or entity.entitySet is not self.entitySet:
            raise TypeError
        if key != entity.Key():
            raise ValueError
        if not entity.exists:
            raise edm.NonExistentEntity(str(entity.GetLocation()))
        if not self.isCollection:
            request = http.HTTPRequest(str(self.baseURI), 'GET')
            self.client.ProcessRequest(request)
            if request.status == 200:
                # this collection is not empty, which will be an error
                # unless it already contains entity, in which case it's
                # a no-op
                existingEntity = self.NewEntity()
                doc = core.Document()
                doc.Read(request.resBody)
                existingEntity.exists = True
                doc.root.GetValue(existingEntity)
                if existingEntity.Key() == entity.Key():
                    return
                else:
                    raise edm.NavigationError(
                        "Navigation property %s already points to an entity (use Replace to update it)" % self.name)
            elif request.status != 404:
                # some type of error
                self.RaiseError(request)
            doc = core.Document(root=core.URI)
            doc.root.SetValue(str(entity.GetLocation()))
            data = str(doc)
            request = http.HTTPRequest(str(self.linksURI), 'PUT', reqBody=data)
            request.SetContentType(
                http.MediaType.FromString('application/xml'))
            self.client.ProcessRequest(request)
            if request.status == 204:
                return
            else:
                self.RaiseError(request)
        else:
            doc = core.Document(root=core.URI)
            doc.root.SetValue(str(entity.GetLocation()))
            data = str(doc)
            request = http.HTTPRequest(
                str(self.linksURI), 'POST', reqBody=data)
            request.SetContentType(
                http.MediaType.FromString('application/xml'))
            self.client.ProcessRequest(request)
            if request.status == 204:
                return
            else:
                self.RaiseError(request)

    def Replace(self, entity):
        if not entity.exists:
            raise edm.NonExistentEntity(str(entity.GetLocation()))
        if self.isCollection:
            # inherit the implementation
            super(NavigationCollection, self).Replace(entity)
        else:
            if not isinstance(entity, edm.Entity) or entity.entitySet is not self.entitySet:
                raise TypeError
            doc = core.Document(root=core.URI)
            doc.root.SetValue(str(entity.GetLocation()))
            data = str(doc)
            request = http.HTTPRequest(str(self.linksURI), 'PUT', reqBody=data)
            request.SetContentType(
                http.MediaType.FromString('application/xml'))
            self.client.ProcessRequest(request)
            if request.status == 204:
                return
            else:
                self.RaiseError(request)

    def __delitem__(self, key):
        if self.isCollection:
            entity = self.NewEntity()
            entity.SetKey(key)
            request = http.HTTPRequest(
                str(self.linksURI) + core.ODataURI.FormatEntityKey(entity), 'DELETE')
        else:
            # danger, how do we know that key really is the right one?
            request = http.HTTPRequest(str(self.linksURI), 'DELETE')
        self.client.ProcessRequest(request)
        if request.status == 204:
            # success, nothing to read back
            return
        else:
            self.RaiseError(request)


class Client(app.Client):

    """An OData client.

    Can be constructed with an optional URL specifying the service root of an
    OData service.  The URL is passed directly to :py:meth:`LoadService`."""

    def __init__(self, serviceRoot=None):
        app.Client.__init__(self)
        #: a :py:class:`pyslet.rfc5023.Service` instance describing this service
        self.service = None
        # : a :py:class:`pyslet.rfc2396.URI` instance pointing to the service root
        self.serviceRoot = None
        self.pathPrefix = None  # : a path prefix string of the service root
        #: a dictionary of feed titles, mapped to :py:class:`csdl.EntitySet` instances
        self.feeds = {}
        #: a :py:class:`metadata.Edmx` instance containing the model for the service
        self.model = None
        if serviceRoot is not None:
            self.LoadService(serviceRoot)

    def LoadService(self, serviceRoot):
        """Configures this client to use the service at *serviceRoot*

        *serviceRoot* is a string or :py:class:`pyslet.rfc2396.URI` instance."""
        if isinstance(serviceRoot, uri.URI):
            self.serviceRoot = serviceRoot
        else:
            self.serviceRoot = uri.URIFactory.URI(serviceRoot)
        request = http.HTTPRequest(str(self.serviceRoot))
        request.SetHeader('Accept', 'application/atomsvc+xml')
        self.ProcessRequest(request)
        if request.status != 200:
            raise UnexpectedHTTPResponse(
                "%i %s" % (request.status, request.response.reason))
        doc = core.Document(baseURI=self.serviceRoot)
        doc.Read(request.resBody)
        if isinstance(doc.root, app.Service):
            self.service = doc.root
            self.serviceRoot = uri.URIFactory.URI(doc.root.ResolveBase())
            self.feeds = {}
            self.model = None
            for w in self.service.Workspace:
                for f in w.Collection:
                    url = f.GetFeedURL()
                    if f.Title:
                        self.feeds[f.Title.GetValue()] = url
        else:
            raise InvalidServiceDocument(str(serviceRoot))
        self.pathPrefix = self.serviceRoot.absPath
        if self.pathPrefix[-1] == u"/":
            self.pathPrefix = self.pathPrefix[:-1]
        metadata = uri.URIFactory.Resolve(serviceRoot, '$metadata')
        doc = edmx.Document(baseURI=metadata, reqManager=self)
        defaultContainer = None
        try:
            doc.Read()
            if isinstance(doc.root, edmx.Edmx):
                self.model = doc.root
                for s in self.model.DataServices.Schema:
                    for container in s.EntityContainer:
                        if container.IsDefaultEntityContainer():
                            prefix = ""
                            defaultContainer = container
                        else:
                            prefix = container.name + "."
                        for es in container.EntitySet:
                            fTitle = prefix + es.name
                            if fTitle in self.feeds:
                                if self.feeds[fTitle] == es.GetLocation():
                                    self.feeds[fTitle] = es
            else:
                raise DataFormatError(str(metadata))
        except xml.XMLError, e:
            # Failed to read the metadata document, there may not be one of
            # course
            raise DataFormatError(str(e))
        # Missing feeds are pruned from the list, perhaps the service advertises them
        # but if we don't have a model of them we can't use of them
        for f in self.feeds.keys():
            if isinstance(self.feeds[f], uri.URI):
                logging.info(
                    "Can't find metadata definition of feed: %s", str(self.feeds[f]))
                del self.feeds[f]
            else:
                # Bind our EntityCollection class
                entitySet = self.feeds[f]
                entitySet.Bind(EntityCollection, client=self)
                for np in entitySet.entityType.NavigationProperty:
                    entitySet.BindNavigation(
                        np.name, NavigationCollection, client=self)
                logging.debug(
                    "Registering feed: %s", str(self.feeds[f].GetLocation()))

    def QueueRequest(self, request, timeout=60):
        # 		if not request.HasHeader("Accept"):
        # 			request.SetHeader('Accept','application/xml')
        request.SetHeader(
            'DataServiceVersion', '2.0; pyslet %s' % info.version)
        request.SetHeader(
            'MaxDataServiceVersion', '2.0; pyslet %s' % info.version)
        super(Client, self).QueueRequest(request, timeout)
