#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

import sys, cgi, urllib, string, itertools

import pyslet.iso8601 as iso
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.rfc2616 as http
import pyslet.rfc2396 as uri
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.mc_edmx as edmx
import pyslet.mc_csdl as edm

class InvalidServiceDocument(Exception): pass
class InvalidMetadataDocument(Exception): pass
class InvalidFeedDocument(Exception): pass
class InvalidEntryDocument(Exception): pass
class InvalidFeedURL(Exception): pass
class UnexpectedHTTPResponse(Exception): pass


ODATA_METADATA_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"	#: namespace for metadata, e.g., the property type attribute
IsDefaultEntityContainer=(ODATA_METADATA_NAMESPACE,u"IsDefaultEntityContainer")

ODATA_DATASERVICES_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices"		#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_SCHEME="http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"					#: category scheme for type definition terms
ODATA_RELATED="http://schemas.microsoft.com/ado/2007/08/dataservices/related/"				#: link type for related entries

ODATA_RELATED_TYPE="application/atom+xml;type=entry"


class ODataElement(xmlns.XMLNSElement):
	"""Base class for all OData specific elements."""
	pass


class Property(ODataElement):
	"""Represents each property.
	
	The OData namesapce does not define elements in the dataservices space as
	the elements take their names from the properties themselves.  Therefore,
	the xmlname of each Property instance is the property name."""
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.typeCode=None		# a value from :py:class:`pyslet.mc_csdl.SimpleType`
	
	def ContentChanged(self):
		ODataElement.ContentChanged(self)
		type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
		if type:
			try:
				self.typeCode=edm.SimpleType.DecodeLowerValue(type.lower())
			except ValueError:
				pass
			
	def GetValue(self):
		"""Gets an appropriately typed value for the property.
		
		Overloads the basic
		:py:meth:`~pyslet.xml20081126.structures.Element.GetValue`
		implementation to add support for type attribute."""
		value=ODataElement.GetValue(self)
		if self.typeCode is not None:
			decoder,encoder=edm.SimpleTypeCodec.get(self.typeCode,(None,None))
			if decoder:
				return decoder(value)
		return value

	def SetValue(self,value):
		"""Sets the value of the property using the conversion indicated by the type attribute, if present
		
		When creating new entries you won't necessarily know the required type,
		in which case the value is simply converted to a string using the
		default string conversion method defined by the python object in
		question."""
		if self.typeCode is not None:
			decoder,encoder=edm.SimpleTypeCodec.get(self.typeCode,(None,None))
			if encoder:
				value=encoder(value)
		ODataElement.SetValue(self,value)

			
class Properties(ODataElement):
	"""Represents the properties element."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'properties')
	
	PropertyClass=Property
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Property=[]

	def GetChildren(self):
		return itertools.chain(
			self.Property,
			ODataElement.GetChildren(self))
		
		
class Content(atom.Content):
	"""Overrides the default :py:class:`pyslet.rfc4287.Content` class to add OData handling."""
		
	def __init__(self,parent):
		atom.Content.__init__(self,parent)
		self.type='application/xml'
		self.Properties=None		#: the optional properties element containing the entry's property values

	def GetChildren(self):
		for child in atom.Content.GetChildren(self): yield child
		if self.Properties: yield self.Properties

	
class Entry(atom.Entry):
	"""Overrides the default :py:class:`pyslet.rfc4287.Entry` class to add OData handling."""
	
	ContentClass=Content
	
	def __init__(self,parent):
		atom.Entry.__init__(self,parent)
		self.entityType=None		#: :py:class:`pyslet.mc_csdl.EntityType` instance describing the entry
		self._properties={}
	
	def ContentChanged(self):
		atom.Entry.ContentChanged(self)
		self._properties={}
		if self.Content and self.Content.Properties:
			for p in self.Content.Properties.Property:
				self._properties[p.xmlname]=(p,p.GetValue())
			
	def __getitem__(self,key):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to read property values.
		
		Returns the value of the property with *key*.  The type of the value
		will be the type specified by the type attribute on the property."""
		return self._properties[key][1]

	def __setitem__(self,key,value):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to set property values.
		
		Sets the property *key* to *value*.  The type of value should be
		compatible with the type expected by the :py:class:`Property` type (as
		indicated by the type attribute).  When setting new properties *value*
		the type is not specified and is treated as text - see
		:py:meth:`Property.SetValue` for more information."""
		if key in self._properties:
			p=self._properties[key][0]
		else:
			ps=self.ChildElement(self.ContentClass).ChildElement(Properties)
			p=ps.ChildElement(ps.PropertyClass,(ODATA_DATASERVICES_NAMESPACE,key))
		p.SetValue(value)
		self._properties[key]=(p,value)

	def AddLink(self,linkTitle,linkURI):
		"""Adds a link with name *linkTitle* to the entry with *linkURI*."""
		l=self.ChildElement(self.LinkClass)
		l.href=linkURI
		l.rel=ODATA_RELATED+linkTitle
		l.title=linkTitle
		l.type=ODATA_RELATED_TYPE


class Client(app.Client):
	"""An OData client.
	
	Can be constructed with an optional URL specifying the service root of an
	OData service."""
	
	def __init__(self,serviceRoot=None):
		app.Client.__init__(self)
		self.SetLog(http.HTTP_LOG_ERROR,sys.stdout)
		self.feeds=[]		#: a list of feeds associated with this client
		self.feedTitles={}	#: a dictionary of feed titles, mapped to collection URLs
		self.schemas={}		#: a dictionary of namespaces mapped to Schema instances
		self.pageSize=None
		"""the default number of entries to retrieve with each request
		
		None indicates no restriction, request all entries."""		
		if serviceRoot:
			self.SetService(serviceRoot)
		else:
			self.serviceRoot=None	#: the URI of the service root
		# Initialise a simple cache of type name -> EntityType definition
		self._cacheTerm=None
		self._cacheType=None
		
	def SetService(self,serviceRoot):
		"""Adds the feeds defined by the URL *serviceRoot* to this client."""
		self.feeds=[]
		self.feedTitles={}
		self.schems={}
		doc=Document(baseURI=serviceRoot,reqManager=self)
		doc.Read()
		if isinstance(doc.root,app.Service):
			for w in doc.root.Workspace:
				for f in w.Collection:
					url=f.GetFeedURL()
					if f.Title:
						self.feedTitles[f.Title.GetValue()]=url
					self.feeds.append(url)
		else:
			raise InvalidServiceDocument(str(serviceRoot))
		metadata=uri.URIFactory.Resolve(serviceRoot,'$metadata')
		doc=edmx.Document(baseURI=metadata,reqManager=self)
		try:
			doc.Read()
			if isinstance(doc.root,edmx.Edmx):
				for s in doc.root.DataServices.Schema:
					self.schemas[s.name]=s
		except xml.XMLError:
			# Failed to read the metadata document, there may not be one of course
			pass
		# reset the cache
		self._cacheTerm=None
		self._cacheType=None
		self.serviceRoot=uri.URIFactory.URI(serviceRoot)

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
		doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
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
			doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
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
		doc=Document(root=entry,reqManager=self)
		req=http.HTTPRequest(str(feedURL),"POST",unicode(doc).encode('utf-8'))
		mtype=http.HTTPMediaType()
		mtype.SetMimeType(atom.ATOM_MIMETYPE)
		mtype.parameters['charset']=('Charset','utf-8')
		req.SetHeader("Content-Type",mtype)
		self.ProcessRequest(req)
		if req.status==201:
			newDoc=Document()
			e=xml.XMLEntity(req.response)
			newDoc.ReadFromEntity(e)
			if isinstance(newDoc.root,atom.Entry):
				return newDoc.root
			else:
				raise InvalidEntryDocument(str(entryURL))
		else:
			raise UnexpectedHTTPResponse("%i %s"%(req.status,req.response.reason))	
			
	def RetrieveEntry(self,entryURL):
		"""Given an entryURL URL, returns the :py:class:`Entry` instance"""
		doc=Document(baseURI=entryURL,reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Entry):
			self.AssociateEntityType(doc.root)
			return doc.root
		else:
			raise InvalidEntryDocument(str(entryURL))
			
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
		request.SetHeader('Accept','application/xml')
		request.SetHeader('DataServiceVersion','2.0')
		request.SetHeader('MaxDataServiceVersion','2.0')
		app.Client.QueueRequest(self,request)


class Server(app.Server):
	def __init__(self,serviceRoot="http://localhost/"):
		app.Server.__init__(self,serviceRoot)
		ws=self.service.ChildElement(app.Workspace)
		ws.ChildElement(atom.Title).SetValue("Default")
		
	
class Document(app.Document):
	"""Class for working with OData documents."""
	classMap={}
	
	def __init__(self,**args):
		app.Document.__init__(self,**args)
		self.MakePrefix(ODATA_METADATA_NAMESPACE,'m')
		self.MakePrefix(ODATA_DATASERVICES_NAMESPACE,'d')
	
	def GetElementClass(self,name):
		"""Returns the OData, APP or Atom class used to represent name.
		
		Overrides :py:meth:`~pyslet.rfc5023.Document.GetElementClass` to allow
		custom implementations of the Atom or APP classes to be created and
		to cater for OData-specific elements."""
		if name[0]==ODATA_DATASERVICES_NAMESPACE:
			return Property
		result=Document.classMap.get(name,None)
		if result is None:
			result=app.Document.GetElementClass(self,name)
		return result


class ODataStoreClient(edm.ERStore):
	"""Provides an implementation of ERStore based on OData."""

	def __init__(self,serviceRoot=None):
		edm.ERStore.__init__(self)
		self.client=Client(serviceRoot)
		self.defaultContainer=None		#: the default entity container
		for s in self.client.schemas:
			# if the client has a $metadata document we'll use it
			schema=self.client.schemas[s]
			self.AddSchema(schema)
			# search for the default entity container
			for container in schema.EntityContainer:
				try:
					if container.GetAttribute(IsDefaultEntityContainer)=="true":
						if self.defaultContainer is None:
							self.defaultContainer=container
						else:
							raise InvalidMetadataDocument("Multiple default entity containers defined")
				except KeyError:
					pass									
				
	def EntityReader(self,entitySetName):
		"""Iterates over the entities in the given entity set (feed)."""
		feedURL=None
		if self.defaultContainer:
			if entitySetName in self.defaultContainer:
				# use this as the name of the feed directly
				# get the entity type from the entitySet definition
				entitySet=self.defaultContainer[entitySetName]
				entityType=self[entitySet.entityType]
				feedURL=uri.URIFactory.Resolve(self.client.serviceRoot,entitySetName)
		if feedURL is None:
			raise NotImplementedError("Entity containers other than the default") 
		for entry in self.client.RetrieveEntries(feedURL):
			values={}
			for p in entityType.Property:
				v=entry[p.name]
				values[p.name]=v
			yield values

			
xmlns.MapClassElements(Document.classMap,globals())