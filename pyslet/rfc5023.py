#! /usr/bin/env python
"""This module implements the Atom Publishing Protocol specification defined in RFC 5023

References:

IRIs [RFC3987]; cf URI [RFC3986]
Before an IRI in a document is used by HTTP, the IRI is first converted to a
URI according to the procedure defined in Section 3.1 of [RFC3987]

xml:base attribute [W3C.REC-xmlbase-20010627]
xml:lang attribute [W3C.REC-xml-20040204], Section 2.12
"""

import pyslet.xmlnames20091208 as xmlns
from pyslet import rfc4287 as atom
from pyslet import rfc2616 as http


APP_NAMESPACE="http://www.w3.org/2007/app"
ATOMSVC_MIMETYPE="application/atomsvc+xml"
ATOMCAT_MIMETYPE="application/atomcat+xml"
APP_MIMETYPES={
	ATOMSVC_MIMETYPE:True,
	ATOMCAT_MIMETYPE:True,
	atom.ATOM_MIMETYPE:True
	}
	
app_accept=(APP_NAMESPACE,'accept')
app_categories=(APP_NAMESPACE,'categories')
app_collection=(APP_NAMESPACE,'collection')
app_service=(APP_NAMESPACE,'service')
app_workspace=(APP_NAMESPACE,'workspace')


class APPElement(xmlns.XMLNSElement):
	"""Basic element to represent all APP elements; not that xml:base, xml:lang and xml:space
	are handled by the XMLElement mix-in class.
	
	appCommonAttributes =
		attribute xml:base { atomURI }?,
		attribute xml:lang { atomLanguageTag  }?,
		attribute xml:space {"default"|"preserved"}?,
		undefinedAttribute*
	"""  
	def __init__(self,parent):
		xmlns.XMLNSElement.__init__(self,parent)
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

		
class APPDocument(atom.AtomDocument):
	def __init__(self,**args):
		""""""
		atom.AtomDocument.__init__(self,**args)
		self.defaultNS=APP_NAMESPACE
	
	def ValidateMimeType(self,mimetype):
		return APP_MIMETYPES.has_key(mimetype) or atom.AtomDocument.ValidateMimeType(self,mimetype)
		
	def GetElementClass(self,name):
		if name[0]==APP_NAMESPACE:
			return APPDocument.classMap.get(name,atom.AtomDocument.classMap.get((name[0],None),APPElement))
		else:
			return atom.AtomDocument.GetElementClass(self,name)
		
	classMap={
		app_accept:APPAccept,
		app_categories:APPCategories,
		app_collection:APPCollection,
		app_service:APPService,
		app_workspace:APPWorkspace
		}
		


class APPClient(http.HTTPRequestManager):
	def __init__(self):
		http.HTTPRequestManager.__init__(self)
				
