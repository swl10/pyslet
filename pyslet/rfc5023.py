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
	XMLNAME=(APP_NAMESPACE,'accept')

	
class APPCategories(APPElement):
	XMLNAME=(APP_NAMESPACE,'categories')
	
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
		
	def AtomCategory(self):
		child=atom.AtomCategory(self)
		self.categoryList.append(child)
		return child
		
		
class APPService(APPElement):
	XMLNAME=(APP_NAMESPACE,'service')
	
	def __init__(self,parent):
		APPElement.__init__(self,parent)
		self.workspaces=[]
		
	def GetChildren(self):
		children=APPElement.GetChildren(self)+self.workspaces
		return children

	def APPWorkspace(self):
		child=APPWorkspace(self)
		self.workspaces.append(child)
		return child
		

class APPWorkspace(APPElement):
	XMLNAME=(APP_NAMESPACE,'workspace')
	
	def __init__(self,parent):
		APPElement.__init__(self,parent)
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
		
	def AtomTitle(self):
		self.title=atom.AtomTitle(self)
		return self.title
	
	def APPCollection(self):
		child=APPCollection(self)
		self.collections.append(child)
		return child
		


class APPCollection(APPElement):
	XMLNAME=(APP_NAMESPACE,'collection')
	
	def __init__(self,parent):	
		APPElement.__init__(self,parent)
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
		
	def AtomTitle(self):
		child=atom.AtomTitle(self)
		self.title=child
		return self.title
		
	def APPCategories(self):
		return self.categories

	def APPAccept(self):
		child=APPAccept(self)
		self.acceptList.append(child)
		return child
		
	def GetFeedURL(self):
		return self.ResolveURI(self.href)

		
class APPDocument(atom.AtomDocument):
	classMap={}
	
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


xmlns.MapClassElements(APPDocument.classMap,globals())
				

class APPClient(http.HTTPRequestManager):
	def __init__(self):
		http.HTTPRequestManager.__init__(self)
				
