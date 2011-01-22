#! /usr/bin/env python

from xml.sax import make_parser, handler, SAXParseException
import string, types
from StringIO import StringIO
import urlparse

XML_NAMESPACE="http://www.w3.org/XML/1998/namespace"
xml_base=(XML_NAMESPACE,'base')
xml_lang=(XML_NAMESPACE,'lang')
xml_space=(XML_NAMESPACE,'space')



class XMLElement:
	def __init__(self,parent):
		self.parent=parent
		self.ns=None
		self.xmlname=None
		self.attrs={}
		self.children=[]

	def SetXMLName(self,xmlname):
		if type(xmlname) in types.StringTypes:
			self.ns=None
			self.xmlname=xmlname
		else:
			self.ns,self.xmlname=xmlname
		
	def GetBase(self):
		return self.attrs.get(xml_base,None)
	
	def SetBase(self,base):
		if base is None:
			self.attrs.pop(xml_base,None)
		else:
			self.attrs[xml_base]=base
	
	def GetLang(self):
		return self.attrs.get(xml_lang,None)
	
	def SetLang(self,lang):
		if lang is None:
			self.attrs.pop(xml_lang,None)
		else:
			self.attrs[xml_lang]=lang
	
	def GetSpace(self):
		return self.attrs.get(xml_space,None)
	
	def SetSpace(self,space):
		if base is None:
			self.attrs.pop(xml_space,None)
		else:
			self.attrs[xml_space]=space
	
	def GetAttributes(self):
		return self.attrs

	def GetAttribute(self,name):
		return self.attrs.get(name,None)

	def SetAttribute(self,name,value):
		self.attrs[name]=value
		
	def AddChild(self,child):
		self.children.append(child)
	
	def GotChildren(self):
		# called when all children have been parsed
		pass
		
	def IsMixed(self):
		for child in self.children:
			if isinstance(child,XMLElement):
				return True
		return False
		
	def GetValue(self):
		if self.IsMixed():
			raise XMLMixedContent
		elif self.children:
			return string.join(map(unicode,self.children),'')
		else:
			return None

	def SetValue(self,value):
		if self.IsMixed():
			raise XMLMixedContent
		else:
			self.children=[value]

	def ResolveURI(self,uri):
		baser=self
		baseURI=None
		while baser is not None:
			baseURI=baser.GetBase()
			if baseURI:
				uri=urlparse.urljoin(baseURI,uri)
			baser=baser.parent
		return uri


class XMLDocument:
	def __init__(self):
		self.rootElement=None

			
class XMLParser(handler.ContentHandler, handler.ErrorHandler):
	def __init__(self):
		self.parser=make_parser()
		self.parser.setFeature(handler.feature_namespaces,1)
		self.parser.setFeature(handler.feature_validation,0)
		self.parser.setContentHandler(self)
		self.parser.setErrorHandler(self)
		self.parser.setEntityResolver(self)
		self.defaultNS=None
		self.classMap={}
		
	def GetClassMap(self):
		return self.classMap
		
	def ParseString (self,src,baseURI=None):
		f=StringIO(src)
		self.baseURI=baseURI
		self.rootObject=None
		self.cObject=None
		self.objStack=[]
		self.data=[]
		self.parser.parse(f)
		return self.rootObject
		
	def startElementNS(self, name, qname, attrs):
		parent=self.cObject
		if parent:
			self.objStack.append(self.cObject)
			if self.data:
				parent.AddChild(string.join(self.data,''))
				self.data=[]
		if name[0] is None:
			name=(self.defaultNS,name[1])
		eClass=self.classMap.get(name,self.classMap.get((name[0],None),XMLElement))
		self.cObject=eClass(parent)
		self.cObject.SetXMLName(name)
		if parent is None:
			self.rootObject=self.cObject
			self.cObject.SetBase(self.baseURI)
		for attr in attrs.keys():
			if attr[0] is None:
				self.cObject.SetAttribute(attr[1],attrs[attr])
			else:
				self.cObject.SetAttribute(attr,attrs[attr])

	def characters(self,ch):
		self.data.append(ch)
			
	def endElementNS(self,name,qname):
		if self.objStack:
			parent=self.objStack.pop()
		else:
			parent=None
		if self.data:
			self.cObject.AddChild(string.join(self.data,''))
			self.data=[]
		self.cObject.GotChildren()
		if parent:
			parent.AddChild(self.cObject)
		self.cObject=parent
