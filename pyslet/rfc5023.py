#! /usr/bin/env python
"""This module implements the Atom Publishing Protocol specification defined in RFC 5023

References:

IRIs [RFC3987]; cf URI [RFC3986]
Before an IRI in a document is used by HTTP, the IRI is first converted to a
URI according to the procedure defined in Section 3.1 of [RFC3987]

xml:base attribute [W3C.REC-xmlbase-20010627]
xml:lang attribute [W3C.REC-xml-20040204], Section 2.12
"""

from pyslet import xml20081126 as xml
from pyslet import rfc4287 as atom
from pyslet import rfc2616 as http


APP_NAMESPACE="http://www.w3.org/2007/app"
ATOMSVC_MIMETYPE="application/atomsvc+xml"
ATOMCAT_MIMETYPE="application/atomcat+xml"

app_accept=(APP_NAMESPACE,'accept')
app_categories=(APP_NAMESPACE,'categories')
app_collection=(APP_NAMESPACE,'collection')
app_service=(APP_NAMESPACE,'service')
app_workspace=(APP_NAMESPACE,'workspace')


class APPElement(xml.XMLElement):
	"""Basic element to represent all APP elements; not that xml:base, xml:lang and xml:space
	are handled by the XMLElement mix-in class.
	
	appCommonAttributes =
		attribute xml:base { atomURI }?,
		attribute xml:lang { atomLanguageTag  }?,
		attribute xml:space {"default"|"preserved"}?,
		undefinedAttribute*
	"""  
	def __init__(self,parent):
		xml.XMLElement.__init__(self,parent)
		self.SetXMLName((APP_NAMESPACE,None))


class APPAccept(APPElement):
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.SetXMLName(app_accept)

	
class APPCategories(APPElement):
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.SetXMLName(app_categories)
		self.categoryList=[]
		
	def GetHREF(self):
		return self.attrs.get("href",None)
		
	def GetFixed(self):
		return self.attrs.get("fixed",None)
	
	def IsFixed(self):
		return self.attrs.get("fixed","no")=="yes"
		
	def GetScheme(self):
		return self.attrs.get("scheme",None)
		
	def GetCategoryList(self):
		return self.categoryList

	def AddChild(self,child):
		if isinstance(child,atom.AtomCategory):
			self.categoryList.append(child)
		else:
			APPElement.AddChild(self,child)
		
class APPService(APPElement):
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.SetXMLName(app_service)
		self.workspaces=[]
		
	def GetWorkspaces(self):
		return self.workspaces

	def AddChild(self,child):
		if isinstance(child,APPWorkspace):
			self.workspaces.append(child)
		else:
			APPElement.AddChild(self,child)

class APPWorkspace(APPElement):
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.SetXMLName(app_workspace)
		self.title=None
		self.collections=[]
		
	def GetCollections(self):
		return self.collections

	def GetTitle(self):
		return self.title
	
	def SetTitle(self,title):
		self.title=title

	def AddChild(self,child):
		if isinstance(child,atom.AtomTitle):
			self.title=child
		elif isinstance(child,APPCollection):
			self.collections.append(child)
		else:
			APPElement.AddChild(self,child)


class APPCollection(APPElement):
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.SetXMLName(app_collection)
		self.title=None
		self.acceptList=[]
		self.categories=APPCategories(None)
		
	def GetHREF(self):
		return self.attrs.get("href",None)
		
	def GetTitle(self):
		return self.title
	
	def SetTitle(self,title):
		self.title=title

	def GetAcceptList(self):
		return self.acceptList

	def GetCategories(self):
		return self.categories

	def AddChild(self,child):
		if isinstance(child,atom.AtomTitle):
			self.title=child
		elif isinstance(child,APPCategories):
			self.categories=child
		elif isinstance(child,APPAccept):
			self.acceptList.append(child)
		else:
			APPElement.AddChild(self,child)

	def GetFeedURL(self):
		return self.ResolveURI(self.GetHREF())

		
class APPParser(atom.AtomParser):
	def __init__(self):
		atom.AtomParser.__init__(self)
		self.defaultNS=APP_NAMESPACE
		self.classMap[app_accept]=APPAccept
		self.classMap[app_categories]=APPCategories
		self.classMap[app_collection]=APPCollection
		self.classMap[app_service]=APPService
		self.classMap[app_workspace]=APPWorkspace


class APPClient(http.HTTPRequestManager):
	def __init__(self):
		http.HTTPRequestManager.__init__(self)
		self.parser=APPParser()
	
	def Get(self,url):
		req=http.HTTPRequest(url)
		self.ProcessRequest(req)
		if req.status==200:
			mtype=req.response.GetContentType()
			if mtype is None:
				# We'll attempt to do this with xml and utf8
				charset='utf8'
				raise UnimplementedError
			else:
				mimetype=mtype.type.lower()+'/'+mtype.subtype.lower()
				if mimetype in (ATOMSVC_MIMETYPE,ATOMCAT_MIMETYPE,atom.ATOM_MIMETYPE,'application/xml','text/xml'):
					return self.parser.ParseString(req.resBody,req.requestURI)
				else:
					print mimetype
					raise UnknownContentType
		else:
			raise UnexpectedHTTPResponse
			
