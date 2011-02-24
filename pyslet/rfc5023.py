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
	pass


class APPAccept(APPElement):
	XMLNAME=app_accept

	
class APPCategories(APPElement):
	XMLNAME=app_categories
	
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.href=None
		self.fixed=None
		self.scheme=None
		self.categoryList=[]

	def Set_href(self,value):
		self.href=value
	
	def Set_fixed(self,value):
		self.fixed=(value=="yes")

	def Set_scheme(self,value):
		self.scheme=value

	def GetChildren(self):
		children=self.categoryList+APPElement.GetChildren(self)
		return children
		
	def AtomCategory(self,name):
		child=atom.AtomCategory(self,name)
		self.categoryList.append(child)
		return child
		
		
class APPService(APPElement):
	XMLNAME=app_service
	
	def __init__(self,parent,name=None):
		APPElement.__init__(self,parent,name)
		self.workspaces=[]
		
	def GetChildren(self):
		children=APPElement.GetChildren(self)+self.workspaces
		return children

	def APPWorkspace(self,name=None):
		child=APPWorkspace(self,name)
		self.workspaces.append(child)
		return child
		

class APPWorkspace(APPElement):
	XMLNAME=app_workspace
	
	def __init__(self,parent,name=None):
		APPElement.__init__(self,parent,name)
		self.title=None
		self.collections=[]
		
	def GetCollections(self):
		return self.collections

	def GetTitle(self):
		return self.title
	
	def SetTitle(self,title):
		self.title=title

	def GetChildren(self):
		children=APPElement.GetChildren(self)
		if self.title:
			children.append(self.title)
		children=children+self.collections
		return self.collections
		
	def AtomTitle(self,name=None):
		self.title=atom.AtomTitle(self,name)
		return self.title
	
	def APPCollection(self,name=None):
		child=APPCollection(self,name)
		self.collections.append(child)
		return child
		


class APPCollection(APPElement):
	XMLNAME=app_collection
	
	def __init__(self,parent,name=None):	
		APPElement.__init__(self,parent,name)
		self.href=None
		self.title=None
		self.acceptList=[]
		self.categories=APPCategories(None)
	
	def GetAttributes(self):
		attrs=APPElement.GetAttributes(self)
		if self.href:
			attrs['href']=self.href
		return attrs
		
	def Set_href(self,value):
		self.href=value

	def GetChildren(self):
		children=APPElement.GetChildren(self)
		if self.title:
			children.append(self.title)
		children=children+self.acceptList
		children.append(self.categories)
		return children
		
	def AtomTitle(self,name):
		child=atom.AtomTitle(self,name)
		self.title=child
		return self.title
		
	def APPCategories(self,name):
		return self.categories

	def APPAccept(self,name):
		child=APPAccept(self,name)
		self.acceptList.append(child)
		return child
		
	def GetFeedURL(self):
		return self.ResolveURI(self.href)

		
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
				
