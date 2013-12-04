#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

import sys, urllib
import pyslet.info as info
import pyslet.rfc2396 as uri
import pyslet.rfc2616 as http
import pyslet.xml20081126.structures as xml
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app

import core
import metadata as edmx


class EntityCollection(core.EntityCollection):
	"""An entity collection that provides access to entities stored
	remotely and accessed through *client*."""
	
	def __init__(self,entitySet,client):
		super(EntityCollection,self).__init__(entitySet)
		self.client=client
		
	def __len__(self):
		# use $count
		feedURL=self.entitySet.GetLocation()
		sysQueryOptions={}
		if self.filter is not None:
			sysQueryOptions[core.SystemQueryOption.filter]=unicode(self.filter)
		if sysQueryOptions:
			feedURL=uri.URIFactory.URI(str(feedURL)+"/$count?"+core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
		else:
			feedURL=uri.URIFactory.URI(str(feedURL)+"/$count")
		request=http.HTTPRequest(str(feedURL))
		request.SetHeader('Accept','text/plain')
		self.client.ProcessRequest(request)
		if request.status==200:
			return int(request.resBody)
		else:
			raise UnexpectedHTTPResponse("%i %s"%(req.status,req.response.reason))	

	def entityGenerator(self):
		feedURL=self.entitySet.GetLocation()
		sysQueryOptions={}
		if self.filter is not None:
			sysQueryOptions[core.SystemQueryOption.filter]=unicode(self.filter)
		if self.orderby is not None:
			sysQueryOptions[core.SystemQueryOption.orderby]=core.CommonExpression.OrderByToString(self.orderby)
		if sysQueryOptions:
			feedURL=uri.URIFactory.URI(str(feedURL)+"?"+core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
		while True:
			doc=core.Document(baseURI=feedURL,reqManager=self.client)
			doc.Read()
			if isinstance(doc.root,atom.Feed):
				if len(doc.root.Entry):
					for e in doc.root.Entry:
						entity=core.Entity(self.entitySet)
						entity.exists=True
						e.GetValue(entity)
						yield entity
				else:
					break
			else:
				raise InvalidFeedDocument(str(feedURL))
			feedURL=None
			for link in doc.root.Link:
				if link.rel=="next":
					feedURL=link.ResolveURI(link.href)
					break
			if feedURL is None:
				break
		
	def itervalues(self):
		return self.ExpandEntities(
			self.entityGenerator())
	
	def __getitem__(self,key):
		entityURL=str(self.entitySet.GetLocation())+core.ODataURI.FormatKeyDict(self.entitySet.GetKeyDict(key))
		sysQueryOptions={}
		if self.filter is not None:
			sysQueryOptions[core.SystemQueryOption.filter]=unicode(self.filter)
		if sysQueryOptions:
			entityURL=uri.URIFactory.URI(entityURL+"?"+core.ODataURI.FormatSysQueryOptions(sysQueryOptions))
		doc=core.Document(baseURI=entityURL,reqManager=self.client)
		try:
			doc.Read()
			if isinstance(doc.root,atom.Entry):
				entity=core.Entity(self.entitySet)
				entity.exists=True
				doc.root.GetValue(entity)
				return entity
			elif isinstance(doc.root,core.Error):
				raise KeyError(key)
			else:
				raise core.InvalidEntryDocument(str(entityURL))
		except xml.XMLMissingResourceError:
			raise KeyError(key)

class Client(app.Client):
	"""An OData client.
	
	Can be constructed with an optional URL specifying the service root of an
	OData service."""
	
	def __init__(self,serviceRoot):
		app.Client.__init__(self)
		self.SetLog(http.HTTP_LOG_ERROR,sys.stdout)
		self.service=None		#: a :py:class:`pyslet.rfc5023.Service` instance describing this service
		self.serviceRoot=None	#: a :py:class:`pyslet.rfc2396.URI` instance pointing to the service root
		if isinstance(serviceRoot,uri.URI):
			self.serviceRoot=serviceRoot
		else:
			self.serviceRoot=uri.URIFactory.URI(serviceRoot)
		self.feeds={}			#: a dictionary of feed titles, mapped to entity sets
		self.model=None			#: a :py:class:`metadata.Edmx` instance containing the model for the service
		self.pageSize=None
		"""the default number of entries to retrieve with each request
		
		None indicates no restriction, request all entries."""
		self.LoadService(serviceRoot)
		
	def LoadService(self,serviceRoot):
		"""Adds the feeds defined by the URL *serviceRoot* to this client."""
		doc=core.Document(baseURI=self.serviceRoot,reqManager=self)
		doc.Read()
		if isinstance(doc.root,app.Service):
			self.service=doc.root
			self.serviceRoot=uri.URIFactory.URI(doc.root.ResolveBase())
			for w in self.service.Workspace:
				for f in w.Collection:
					url=f.GetFeedURL()
					if f.Title:
						self.feeds[f.Title.GetValue()]=url
		else:
			raise InvalidServiceDocument(str(serviceRoot))
		metadata=uri.URIFactory.Resolve(serviceRoot,'$metadata')
		doc=edmx.Document(baseURI=metadata,reqManager=self)
		defaultContainer=None
		try:
			doc.Read()
			if isinstance(doc.root,edmx.Edmx):
				self.model=doc.root
				for s in self.model.DataServices.Schema:
					for container in s.EntityContainer:
						if container.IsDefaultEntityContainer():
							prefix=""
							defaultContainer=container
						else:
							prefix=container.name+"."
						for es in container.EntitySet:
							fTitle=prefix+es.name
							if fTitle in self.feeds:
								if self.feeds[fTitle]==es.GetLocation():
									self.feeds[fTitle]=es
			else:
				raise InvalidMetadataDocument(str(metadata))
		except xml.XMLError,e:
			# Failed to read the metadata document, there may not be one of course
			raise InvalidMetadataDocument(str(e))
		# Missing feeds are pruned from the list, perhaps the service advertises them
		# but if we don't have a model of them we can't use of them
		for f in self.feeds.keys():
			if isinstance(self.feeds[f],uri.URI):
				self.Log(http.HTTP_LOG_INFO,"Can't find metadata definition of feed: %s"%str(self.feeds[f]))
				del self.feeds[f]
			else:
				# Bind our EntityCollection class
				self.feeds[f].Bind(EntityCollection,client=self)
				self.Log(http.HTTP_LOG_DETAIL,"Registering feed: %s"%str(self.feeds[f].GetLocation()))
				
	def LookupEntityType(self,entityTypeName):
		"""Returns the :py:class:`EntityType` instance associated with the fully qualified *entityTypeName*"""
		entityType=None
		if entityTypeName==self._cacheTerm:
			# time saver as most feeds are just lists of the same type
			entityType=self._cacheType
		else:
			name=entityTypeName.split('.')
			if name[0] in self.schemas:
				try:
					entityType=self.schemas[name[0]][string.join(name[1:],'.')]
				except KeyError:
					pass
			# we cache both positive and negative results
			self._cacheTerm=entityTypeName
			self._cacheType=entityType
		return entityType

	def AssociateEntityType(self,entry):
		for c in entry.Category:
			entry.entityType=None
			if c.scheme==ODATA_SCHEME and c.term:
				entry.entityType=self.LookupEntityType(c.term)
			
	def RetrieveFeed(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns a :py:class:`pyslet.rfc4287.Feed` object representing it."""
		doc=core.Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Feed):
			for e in doc.root.Entry:
				self.AssociateEntityType(e)
			return doc.root
		else:
			raise InvalidFeedDocument(str(feedURL))
	
	def RetrieveEntries(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns an iterable yielding :py:class:`Entry` instances.
		
		This method uses the :py:attr:`pageSize` attribute to set the paging of
		the data.  (The source may restrict the number of return values too). 
		It hides the details required to iterate through the entire list of
		entries with the caveat that there is no guarantee that the results will
		be consistent.  If the data source is being updated or reconfigured it
		is possible that the some entries may be skipped or duplicated as a result
		of being returned by different HTTP requests."""
		if self.pageSize:
			skip=0
			page=self.pageSize
		else:
			skip=page=None
		if odataQuery is None:
			odataQuery={}
		while True:
			if page:
				if skip:
					odataQuery['$skip']=str(skip)				
			doc=core.Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
			doc.Read()
			if isinstance(doc.root,atom.Feed):
				if len(doc.root.Entry):
					for e in doc.root.Entry:
						self.AssociateEntityType(e)
						yield e
				else:
					break
			else:
				raise InvalidFeedDocument(str(feedURL))
			if page:
				skip=skip+page
			else:
				# check for 'next' link
				feedURL=None
				for link in doc.root.Link:
					if link.rel=="next":
						feedURL=link.ResolveURI(link.href)
						break
				if feedURL is None:
					break
						
	def Entry(self,entityTypeName=None):
		"""Returns a new :py:class:`Entry` suitable for passing to :py:meth:`AddEntry`.
		
		The optional *entityTypeName* is the name of an EntityType to bind this
		entry to.  The name must be the fully qualified name of a type in one of
		the namespaces.  A Category instance is added to the Entry to represent this
		binding."""
		if entityTypeName:
			entityType=self.LookupEntityType(entityTypeName)
			if entityType is None:
				raise KeyError("Undeclared Type: %s"%entityTypeName)
		else:
			entityType=None
		e=Entry(None)
		e.entityType=entityType
		if entityType:
			c=e.ChildElement(atom.Category)
			c.scheme=ODATA_SCHEME
			c.term=entityTypeName				
		return e		
				
	def AddEntry(self,feedURL,entry):
		"""Given a feed URL, adds an :py:class:`Entry` to it
		
		Returns the new entry as returned by the OData service.  *entry* must be
		an orphan element."""
		doc=core.Document(root=entry,reqManager=self)
		req=http.HTTPRequest(str(feedURL),"POST",unicode(doc).encode('utf-8'))
		mtype=http.HTTPMediaType()
		mtype.SetMimeType(atom.ATOM_MIMETYPE)
		mtype.parameters['charset']=('Charset','utf-8')
		req.SetHeader("Content-Type",mtype)
		self.ProcessRequest(req)
		if req.status==201:
			newDoc=core.Document()
			e=xml.XMLEntity(req.response)
			newDoc.ReadFromEntity(e)
			if isinstance(newDoc.root,atom.Entry):
				return newDoc.root
			else:
				raise core.InvalidEntryDocument(str(entryURL))
		else:
			raise UnexpectedHTTPResponse("%i %s"%(req.status,req.response.reason))	
			
	def RetrieveEntry(self,entryURL):
		"""Given an entryURL URL, returns the :py:class:`Entry` instance"""
		doc=core.Document(baseURI=entryURL,reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Entry):
			self.AssociateEntityType(doc.root)
			return doc.root
		else:
			raise core.InvalidEntryDocument(str(entryURL))
			
	def _AddParams(self,baseURL,odataQuery=None):
		if baseURL.query is None:
			query={}
		else:
			query=cgi.parse_qs(baseURL.query)
		if self.pageSize:
			query["$top"]=str(self.pageSize)
		if odataQuery:
			for k in odataQuery.keys():
				query[k]=odataQuery[k]
		if query:
			if baseURL.absPath is None:
				raise InvalidFeedURL(str(baseURL))
			return uri.URIFactory.Resolve(baseURL,baseURL.absPath+"?"+urllib.urlencode(query))
		else:
			return baseURL

	def QueueRequest(self,request):
		if not request.HasHeader("Accept"):
			request.SetHeader('Accept','application/xml')
		request.SetHeader('DataServiceVersion','2.0; pyslet %s'%info.version)
		request.SetHeader('MaxDataServiceVersion','2.0; pyslet %s'%info.version)
		app.Client.QueueRequest(self,request)


