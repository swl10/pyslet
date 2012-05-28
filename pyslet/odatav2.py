#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

import sys, cgi, urllib

import pyslet.iso8601 as iso
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.rfc2616 as http
import pyslet.rfc2396 as uri
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi

class InvalidServiceDocument(Exception): pass
class InvalidFeedDocument(Exception): pass
class InvalidEntryDocument(Exception): pass
class InvalidFeedURL(Exception): pass
class UnexpectedHTTPResponse(Exception): pass


ODATA_METADATA_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
ODATA_DATASERVICES_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices"

ODATA_RELATED="http://schemas.microsoft.com/ado/2007/08/dataservices/related/"
ODATA_RELATED_TYPE="application/atom+xml;type=entry"

class ODataElement(xmlns.XMLNSElement):
	"""Base class for all OData specific elements."""
	pass


class Property(ODataElement):
	"""Represents each property.
	
	The OData namesapce does not define elements in the dataservices space as
	the elements take their names from the properties themselves.  Therefore,
	the xmlname of each Property instance is the property name."""
	
	Conversions={
		"Edm.Boolean":(xsi.DecodeBoolean,xsi.EncodeBoolean),
		"Edm.DateTime":(xsi.DecodeDateTime,xsi.EncodeDateTime),		
		"Edm.Decimal":(xsi.DecodeFloat,xsi.EncodeFloat),
		"Edm.Double":(xsi.DecodeFloat,xsi.EncodeFloat),
		"Edm.Int16":(xsi.DecodeInteger,xsi.EncodeInteger),
		"Edm.Int32":(xsi.DecodeInteger,xsi.EncodeInteger),
		"Edm.Int64":(xsi.DecodeInteger,xsi.EncodeInteger),
		}
		
	def GetValue(self):
		"""Gets an appropriately typed value for the property.
		
		Overloads the basic
		:py:meth:`~pyslet.xml20081126.structures.Element.GetValue`
		implementation to add support for type attribute."""
		value=ODataElement.GetValue(self)
		type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
		if type:
			convert=self.Conversions.get(type,None)
			if convert:
				return convert[0](value)
		return value

	def SetValue(self,value):
		type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
		if type:
			convert=self.Conversions.get(type,None)
			if convert:
				value=convert[1](value)
		ODataElement.SetValue(self,value)

			
class Properties(ODataElement):
	"""Represents the properties element."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'properties')
	
	PropertyClass=Property
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Property=[]

	def GetChildren(self):
		return self.Property+ODataElement.GetChildren(self)
		
		
class Content(atom.Content):
	"""Overrides the default :py:class:`pyslet.rfc4287.Content` class to add OData handling."""
		
	def __init__(self,parent):
		atom.Content.__init__(self,parent)
		self.type='application/xml'
		self.Properties=None		#: the optional properties element

	def GetChildren(self):
		children=atom.Content.GetChildren(self)
		xml.OptionalAppend(children,self.Properties)
		return children

	
class Entry(atom.Entry):
	"""Overrides the default :py:class:`pyslet.rfc4287.Entry` class to add OData handling."""
	
	ContentClass=Content
	
	def __init__(self,parent):
		atom.Entry.__init__(self,parent)
		self._properties={}
	
	def ContentChanged(self):
		atom.Entry.ContentChanged(self)
		self._properties={}
		if self.Content and self.Content.Properties:
			for p in self.Content.Properties.Property:
				self._properties[p.xmlname]=(p,p.GetValue())
			
	def __getitem__(self,key):
		return self._properties[key][1]

	def __setitem__(self,key,value):
		if self._properties.has_key(key):
			p=self._properties[key][0]
		else:
			ps=self.ChildElement(self.ContentClass).ChildElement(Properties)
			p=ps.ChildElement(ps.PropertyClass,(ODATA_DATASERVICES_NAMESPACE,key))
		p.SetValue(value)
		self._properties[key]=(p,value)

	def AddLink(self,linkTitle,linkURI):
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
		self.pageSize=None
		"""the default number of entries to retrieve with each request
		
		None indicates no restriction, request all entries."""		
		if serviceRoot:
			self.AddService(serviceRoot)
		
	def AddService(self,serviceRoot):
		"""Adds the feeds defined by the URL *serviceRoot* to this client."""
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
	
	def RetrieveFeed(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns a :py:class:`pyslet.rfc4287.Feed` object representing it."""
		doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Feed):
			return doc.root
		else:
			raise InvalidFeedDocument(str(feedURL))
	
	def RetrieveEntries(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns an iterable yielding :py:class:`pyslet.rfc4287.Entry` instances."""
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
						
			
	def AddEntry(self,feedURL,entry):
		"""Given a feed URL, adds a :py:class:`pyslet.rfc4287.Entry` to it
		
		Returns the new entry as returned by the OData service."""
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
		"""Given an entryURL URL, returns the :py:class:`pyslet.rfc4287.Entry` instance"""
		doc=Document(baseURI=entryURL,reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Entry):
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
		
xmlns.MapClassElements(Document.classMap,globals())
		
		
		
		