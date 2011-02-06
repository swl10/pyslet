#! /usr/bin/env python

from xml.sax import make_parser, handler, SAXParseException, saxutils
import string, types
from StringIO import StringIO
import urlparse, urllib,  os.path
from sys import maxunicode
import codecs, random

xml_base='xml:base'
xml_lang='xml:lang'
xml_space='xml:space'

XML_MIMETYPES={
	'text/xml':True,
	'application/xml':True,
	'text/application+xml':True	
	}
	
class XMLError(Exception): pass

class XMLContentTypeError(XMLError): pass
class XMLIDClashError(XMLError): pass
class XMLIDValueError(XMLError): pass
class XMLMissingLocationError(XMLError): pass
class XMLMixedContentError(XMLError): pass
class XMLUnexpectedHTTPResponse(XMLError): pass
class XMLUnsupportedSchemeError(XMLError): pass

from pyslet.unicode5 import CharClass
from pyslet import rfc2616 as http

NameStartCharClass=CharClass(u':', (u'A',u'Z'), u'_', (u'a',u'z'),
	(u'\xc0',u'\xd6'), (u'\xd8',u'\xf6'),
	(u'\xf8',u'\u02ff'), (u'\u0370',u'\u037d'), (u'\u037f',u'\u1fff'),
	(u'\u200c',u'\u200d'), (u'\u2070',u'\u218f'), (u'\u2c00',u'\u2fef'),
	(u'\u3001',u'\ud7ff'), (u'\uf900',u'\ufdcf'), (u'\ufdf0',u'\ufffd'))

NameCharClass=CharClass(NameStartCharClass, u'-', u'.', (u'0',u'9'),
	u'\xb7', (u'\u0300',u'\u036f'), (u'\u203f',u'\u2040'))

BaseCharClass=CharClass((u'A',u'Z'), (u'a',u'z'), (u'\xc0',u'\xd6'),
	(u'\xd8',u'\xf6'), (u'\xf8',u'\u0131'), (u'\u0134',u'\u013e'),
	(u'\u0141',u'\u0148'), (u'\u014a',u'\u017e'), (u'\u0180',u'\u01c3'),
	(u'\u01cd',u'\u01f0'), (u'\u01f4',u'\u01f5'), (u'\u01fa',u'\u0217'),
	(u'\u0250',u'\u02a8'), (u'\u02bb',u'\u02c1'), u'\u0386', (u'\u0388',u'\u038a'),
	u'\u038c', (u'\u038e',u'\u03a1'), (u'\u03a3',u'\u03ce'), (u'\u03d0',u'\u03d6'),
	u'\u03da', u'\u03dc', u'\u03de', u'\u03e0', (u'\u03e2',u'\u03f3'),
	(u'\u0401',u'\u040c'), (u'\u040e',u'\u044f'), (u'\u0451',u'\u045c'),
	(u'\u045e',u'\u0481'), (u'\u0490',u'\u04c4'), (u'\u04c7',u'\u04c8'),
	(u'\u04cb',u'\u04cc'), (u'\u04d0',u'\u04eb'), (u'\u04ee',u'\u04f5'),
	(u'\u04f8',u'\u04f9'), (u'\u0531',u'\u0556'), u'\u0559', (u'\u0561',u'\u0586'),
	(u'\u05d0',u'\u05ea'), (u'\u05f0',u'\u05f2'), (u'\u0621',u'\u063a'),
	(u'\u0641',u'\u064a'), (u'\u0671',u'\u06b7'), (u'\u06ba',u'\u06be'),
	(u'\u06c0',u'\u06ce'), (u'\u06d0',u'\u06d3'), u'\u06d5', (u'\u06e5',u'\u06e6'),
	(u'\u0905',u'\u0939'), u'\u093d', (u'\u0958',u'\u0961'), (u'\u0985',u'\u098c'),
	(u'\u098f',u'\u0990'), (u'\u0993',u'\u09a8'), (u'\u09aa',u'\u09b0'), u'\u09b2',
	(u'\u09b6',u'\u09b9'), (u'\u09dc',u'\u09dd'), (u'\u09df',u'\u09e1'),
	(u'\u09f0',u'\u09f1'), (u'\u0a05',u'\u0a0a'), (u'\u0a0f',u'\u0a10'),
	(u'\u0a13',u'\u0a28'), (u'\u0a2a',u'\u0a30'), (u'\u0a32',u'\u0a33'),
	(u'\u0a35',u'\u0a36'), (u'\u0a38',u'\u0a39'), (u'\u0a59',u'\u0a5c'), u'\u0a5e',
	(u'\u0a72',u'\u0a74'), (u'\u0a85',u'\u0a8b'), u'\u0a8d', (u'\u0a8f',u'\u0a91'),
	(u'\u0a93',u'\u0aa8'), (u'\u0aaa',u'\u0ab0'), (u'\u0ab2',u'\u0ab3'),
	(u'\u0ab5',u'\u0ab9'), u'\u0abd', u'\u0ae0', (u'\u0b05',u'\u0b0c'),
	(u'\u0b0f',u'\u0b10'), (u'\u0b13',u'\u0b28'), (u'\u0b2a',u'\u0b30'),
	(u'\u0b32',u'\u0b33'), (u'\u0b36',u'\u0b39'), u'\u0b3d', (u'\u0b5c',u'\u0b5d'),
	(u'\u0b5f',u'\u0b61'), (u'\u0b85',u'\u0b8a'), (u'\u0b8e',u'\u0b90'),
	(u'\u0b92',u'\u0b95'), (u'\u0b99',u'\u0b9a'), u'\u0b9c', (u'\u0b9e',u'\u0b9f'),
	(u'\u0ba3',u'\u0ba4'), (u'\u0ba8',u'\u0baa'), (u'\u0bae',u'\u0bb5'),
	(u'\u0bb7',u'\u0bb9'), (u'\u0c05',u'\u0c0c'), (u'\u0c0e',u'\u0c10'),
	(u'\u0c12',u'\u0c28'), (u'\u0c2a',u'\u0c33'), (u'\u0c35',u'\u0c39'),
	(u'\u0c60',u'\u0c61'), (u'\u0c85',u'\u0c8c'), (u'\u0c8e',u'\u0c90'),
	(u'\u0c92',u'\u0ca8'), (u'\u0caa',u'\u0cb3'), (u'\u0cb5',u'\u0cb9'), u'\u0cde',
	(u'\u0ce0',u'\u0ce1'), (u'\u0d05',u'\u0d0c'), (u'\u0d0e',u'\u0d10'),
	(u'\u0d12',u'\u0d28'), (u'\u0d2a',u'\u0d39'), (u'\u0d60',u'\u0d61'),
	(u'\u0e01',u'\u0e2e'), u'\u0e30', (u'\u0e32',u'\u0e33'), (u'\u0e40',u'\u0e45'),
	(u'\u0e81',u'\u0e82'), u'\u0e84', (u'\u0e87',u'\u0e88'), u'\u0e8a', u'\u0e8d',
	(u'\u0e94',u'\u0e97'), (u'\u0e99',u'\u0e9f'), (u'\u0ea1',u'\u0ea3'), u'\u0ea5',
	u'\u0ea7', (u'\u0eaa',u'\u0eab'), (u'\u0ead',u'\u0eae'), u'\u0eb0',
	(u'\u0eb2',u'\u0eb3'), u'\u0ebd', (u'\u0ec0',u'\u0ec4'), (u'\u0f40',u'\u0f47'),
	(u'\u0f49',u'\u0f69'), (u'\u10a0',u'\u10c5'), (u'\u10d0',u'\u10f6'), u'\u1100',
	(u'\u1102',u'\u1103'), (u'\u1105',u'\u1107'), u'\u1109', (u'\u110b',u'\u110c'),
	(u'\u110e',u'\u1112'), u'\u113c', u'\u113e', u'\u1140', u'\u114c', u'\u114e',
	u'\u1150', (u'\u1154',u'\u1155'), u'\u1159', (u'\u115f',u'\u1161'), u'\u1163',
	u'\u1165', u'\u1167', u'\u1169', (u'\u116d',u'\u116e'), (u'\u1172',u'\u1173'),
	u'\u1175', u'\u119e', u'\u11a8', u'\u11ab', (u'\u11ae',u'\u11af'),
	(u'\u11b7',u'\u11b8'), u'\u11ba', (u'\u11bc',u'\u11c2'), u'\u11eb', u'\u11f0',
	u'\u11f9', (u'\u1e00',u'\u1e9b'), (u'\u1ea0',u'\u1ef9'), (u'\u1f00',u'\u1f15'),
	(u'\u1f18',u'\u1f1d'), (u'\u1f20',u'\u1f45'), (u'\u1f48',u'\u1f4d'),
	(u'\u1f50',u'\u1f57'), u'\u1f59', u'\u1f5b', u'\u1f5d', (u'\u1f5f',u'\u1f7d'),
	(u'\u1f80',u'\u1fb4'), (u'\u1fb6',u'\u1fbc'), u'\u1fbe', (u'\u1fc2',u'\u1fc4'),
	(u'\u1fc6',u'\u1fcc'), (u'\u1fd0',u'\u1fd3'), (u'\u1fd6',u'\u1fdb'),
	(u'\u1fe0',u'\u1fec'), (u'\u1ff2',u'\u1ff4'), (u'\u1ff6',u'\u1ffc'), u'\u2126',
	(u'\u212a',u'\u212b'), u'\u212e', (u'\u2180',u'\u2182'), (u'\u3041',u'\u3094'),
	(u'\u30a1',u'\u30fa'), (u'\u3105',u'\u312c'), (u'\uac00',u'\ud7a3'))

CombiningCharClass=CharClass((u'\u0300',u'\u0345'), (u'\u0360',u'\u0361'),
	(u'\u0483',u'\u0486'), (u'\u0591',u'\u05a1'), (u'\u05a3',u'\u05b9'),
	(u'\u05bb',u'\u05bd'), u'\u05bf', (u'\u05c1',u'\u05c2'), u'\u05c4',
	(u'\u064b',u'\u0652'), u'\u0670', (u'\u06d6',u'\u06e4'), (u'\u06e7',u'\u06e8'),
	(u'\u06ea',u'\u06ed'), (u'\u0901',u'\u0903'), u'\u093c', (u'\u093e',u'\u094d'),
	(u'\u0951',u'\u0954'), (u'\u0962',u'\u0963'), (u'\u0981',u'\u0983'), u'\u09bc',
	(u'\u09be',u'\u09c4'), (u'\u09c7',u'\u09c8'), (u'\u09cb',u'\u09cd'), u'\u09d7',
	(u'\u09e2',u'\u09e3'), u'\u0a02', u'\u0a3c', (u'\u0a3e',u'\u0a42'),
	(u'\u0a47',u'\u0a48'), (u'\u0a4b',u'\u0a4d'), (u'\u0a70',u'\u0a71'),
	(u'\u0a81',u'\u0a83'), u'\u0abc', (u'\u0abe',u'\u0ac5'), (u'\u0ac7',u'\u0ac9'),
	(u'\u0acb',u'\u0acd'), (u'\u0b01',u'\u0b03'), u'\u0b3c', (u'\u0b3e',u'\u0b43'),
	(u'\u0b47',u'\u0b48'), (u'\u0b4b',u'\u0b4d'), (u'\u0b56',u'\u0b57'),
	(u'\u0b82',u'\u0b83'), (u'\u0bbe',u'\u0bc2'), (u'\u0bc6',u'\u0bc8'),
	(u'\u0bca',u'\u0bcd'), u'\u0bd7', (u'\u0c01',u'\u0c03'), (u'\u0c3e',u'\u0c44'),
	(u'\u0c46',u'\u0c48'), (u'\u0c4a',u'\u0c4d'), (u'\u0c55',u'\u0c56'),
	(u'\u0c82',u'\u0c83'), (u'\u0cbe',u'\u0cc4'), (u'\u0cc6',u'\u0cc8'),
	(u'\u0cca',u'\u0ccd'), (u'\u0cd5',u'\u0cd6'), (u'\u0d02',u'\u0d03'),
	(u'\u0d3e',u'\u0d43'), (u'\u0d46',u'\u0d48'), (u'\u0d4a',u'\u0d4d'), u'\u0d57',
	u'\u0e31', (u'\u0e34',u'\u0e3a'), (u'\u0e47',u'\u0e4e'), u'\u0eb1',
	(u'\u0eb4',u'\u0eb9'), (u'\u0ebb',u'\u0ebc'), (u'\u0ec8',u'\u0ecd'),
	(u'\u0f18',u'\u0f19'), u'\u0f35', u'\u0f37', u'\u0f39', (u'\u0f3e',u'\u0f3f'),
	(u'\u0f71',u'\u0f84'), (u'\u0f86',u'\u0f8b'), (u'\u0f90',u'\u0f95'), u'\u0f97',
	(u'\u0f99',u'\u0fad'), (u'\u0fb1',u'\u0fb7'), u'\u0fb9', (u'\u20d0',u'\u20dc'),
	u'\u20e1', (u'\u302a',u'\u302f'), (u'\u3099',u'\u309a'))

DigitClass=CharClass((u'0',u'9'), (u'\u0660',u'\u0669'),
	(u'\u06f0',u'\u06f9'), (u'\u0966',u'\u096f'), (u'\u09e6',u'\u09ef'),
	(u'\u0a66',u'\u0a6f'), (u'\u0ae6',u'\u0aef'), (u'\u0b66',u'\u0b6f'),
	(u'\u0be7',u'\u0bef'), (u'\u0c66',u'\u0c6f'), (u'\u0ce6',u'\u0cef'),
	(u'\u0d66',u'\u0d6f'), (u'\u0e50',u'\u0e59'), (u'\u0ed0',u'\u0ed9'),
	(u'\u0f20',u'\u0f29'))

ExtenderClass=CharClass(u'\xb7', (u'\u02d0',u'\u02d1'), u'\u0387', u'\u0640',
u'\u0e46', u'\u0ec6', u'\u3005', (u'\u3031',u'\u3035'), (u'\u309d',u'\u309e'),
(u'\u30fc',u'\u30fe'))

def IsChar(c):
	return c and (ord(c)==0x9 or ord(c)==0xA or ord(c)==0xD or
		(ord(c)>=0x20 and ord(c)<=0xD7FF) or
		(ord(c)>=0xE000 and ord(c)<=0xFFFD) or
		(ord(c)>=0x10000 and ord(c)<=0x10FFFF))

def IsSpace(c):
	return c and (ord(c)==0x9 or ord(c)==0xA or ord(c)==0xD or ord(c)==0x20)

def IsLetter(c):
	return IsBaseChar(c) or IsIdeographic(c)

def IsBaseChar(c):
	return BaseCharClass.Test(c)

def IsIdeographic(c):
	return c and ((ord(c)>=0x4E00 and ord(c)<=0x9FA5) or ord(c)==0x3007 or
		(ord(c)>=0x3021 and ord(c)<=0x3029))

def IsCombiningChar(c):
	return CombiningCharClass.Test(c)

def IsDigit(c):
	return DigitClass.Test(c)

def IsExtender(c):
	return ExtenderClass.Test(c)

def IsNameStartChar(c):
	return NameStartCharClass.Test(c)
	
def IsNameChar(c):
	return NameCharClass.Test(c)

def IsValidName(name):
	if name:
		if not IsNameStartChar(name[0]):
			return False
		for c in name[1:]:
			if not IsNameChar(c):
				return False
		return True
	else:
		return False

class XMLElement:
	def __init__(self,parent):
		self.parent=parent
		if hasattr(self.__class__,'XMLNAME'):
			self.xmlname=self.__class__.XMLNAME
		else:
			self.xmlname=None
		self.attrs={}
		self.children=[]
			
	def SetXMLName(self,xmlname):
		self.xmlname=xmlname

	def GetDocument(self):
		if self.parent:
			if isinstance(self.parent,XMLDocument):
				return self.parent
			else:
				return self.parent.GetDocument()
		else:
			return None

	def GetChildren(self):
		return self.children
		
	def GetBase(self):
		return self.attrs.get(xml_base,None)
	
	def SetBase(self,base):
		if base is None:
			self.attrs.pop(xml_base,None)
		else:
			self.attrs[xml_base]=str(base)
	
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
		if space is None:
			self.attrs.pop(xml_space,None)
		else:
			self.attrs[xml_space]=space
	
	def GetAttributes(self):
		return self.attrs

	def GetAttribute(self,name):
		return self.attrs.get(name,None)

	def SetAttribute(self,name,value):
		oldValue=self.attrs.pop(name,None)
		if hasattr(self.__class__,'ID') and name==self.__class__.ID:
			# This is an ID attribute
			if not self.IsValidName(value):
				raise XMLIDValueError(value)
			doc=self.GetDocument()
			if doc and value!=oldValue:
				if oldValue:
					doc.UnregisterElementID(oldValue)
				doc.RegisterElementID(self,value)
		self.attrs[name]=value
				
	def IsValidName(self,value):
		return IsValidName(value)
	
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
			raise XMLMixedContentError
		elif self.children:
			return string.join(map(unicode,self.children),'')
		else:
			return None

	def SetValue(self,value):
		if self.IsMixed():
			raise XMLMixedContentError
		else:
			self.children=[value]

	def ResolveURI(self,uri):
		"""Returns a fully specified URL, resolving URI in the current context.
		
		The uri is resolved relative to the xml:base values of the element's
		ancestors and ultimately relative to the document's baseURI.
		
		The result is a string (of bytes), not a unicode string.  Likewise, uri
		must be passed in as a string of bytes.

		The reason for this restriction is best illustrated with an example:
		
		The URI %E8%8B%B1%E5%9B%BD.xml is a UTF-8 and URL-encoded path segment
		using the Chinese word for United Kingdom.  When we remove the URL-encoding
		we get the string '\xe8\x8b\xb1\xe5\x9b\xbd.xml' which must be interpreted
		with utf-8 to get the intended path segment value: u'\u82f1\u56fd'.  However,
		if the URL was marked as being a unicode string of characters then this second
		stage would not be carried out and the result would be the unicode string
		u'\xe8\x8b\xb1\xe5\x9b\xbd', which is a meaningless string of 6
		characters taken from the European Latin-1 character set."""
		baser=self
		baseURI=None
		while True:
			baseURI=baser.GetBase()
			if baseURI:
				uri=urlparse.urljoin(baseURI,str(uri))
			if isinstance(baser,XMLElement):
				baser=baser.parent
			else:
				break
		return uri

	def WriteXMLAttributes(self,attributes):
		"""Adds strings representing the element's attributes
		
		attributes is a list of unicode strings.  Attributes should be appended
		as strings of the form 'name="value"' with values escaped appropriately
		for XML output."""
		keys=self.attrs.keys()
		keys.sort()
		for a in keys:
			attributes.append('%s=%s'%(a,saxutils.quoteattr(self.attrs[a])))
		
	def WriteXML(self,f):
		attributes=[]
		self.WriteXMLAttributes(attributes)
		if attributes:
			attributes[0:0]=['']
			attributes=string.join(attributes,' ')
		else:
			attributes=''
		if self.children:
			f.write('<%s%s>'%(self.xmlname,attributes))
			for child in self.children:
				if type(child) in types.StringTypes:
					f.write(child)
				else:
					child.WriteXML(f)
			f.write('</%s>'%self.xmlname)
		else:
			f.write('<%s%s/>'%(self.xmlname,attributes))
				

class XMLDocument(handler.ContentHandler, handler.ErrorHandler):
	def __init__(self, root=None, baseURI=None, defaultNS=None, **args):
		"""Initialises a new XMLDocument from optional keyword arguments.
		
		With no arguments, a new XMLDocument is created with no baseURI
		or root element.
		
		If root is a class object (descended from XMLElement) it is used
		to create the root element of the document.
		
		baseURI can be set on construction (see SetBase)
		
		The defaultNS used for elements without an associated namespace
		can be specified on construction."""
		self.defaultNS=defaultNS
		self.parser=make_parser()
		self.parser.setFeature(handler.feature_namespaces,0)
		self.parser.setFeature(handler.feature_validation,0)
		self.parser.setContentHandler(self)
		self.parser.setErrorHandler(self)
		self.baseURI=None
		if root:
			if not issubclass(root,XMLElement):
				raise ValueError
			self.rootElement=root(self)
		else:
			self.rootElement=None
		self.SetBase(baseURI)
		#self.parser.setEntityResolver(self)
		self.idTable={}
		
	def SetDefaultNS(self,ns):
		self.defaultNS=ns
	
	def ValidateMimeType(self,mimetype):
		return XML_MIMETYPES.has_key(mimetype)
		
	def GetElementClass(self,name):
		"""Returns a class object suitable for representing name
		
		name is a tuple of (namespace, name)
		
		The default implementation returns XMLElement."""
		return XMLElement
				
	def SetBase(self,baseURI):
		"""Sets the baseURI of the document to the given URI.
		
		If the baseURI is a local file or relative path then the file path
		is updated to point to the file."""
		self.baseURI=baseURI
		if self.baseURI:
			base='file://'+urllib.pathname2url(os.getcwd())+'/'
			self.baseURI=urlparse.urljoin(base,self.baseURI)
			self.url=urlparse.urlsplit(self.baseURI)
		else:
			self.url=None
			
	def GetBase(self):
		return self.baseURI
		
	def AddChild(self,child):
		if isinstance(child,XMLElement):
			self.rootElement=child
	
	def RegisterElementID(self,element,id):
		if self.idTable.has_key(id):
			raise XMLIDClashError
		else:
			self.idTable[id]=element
	
	def UnregisterElementID(self,id):
		del self.idTable[id]
	
	def GetElementByID(self,id):
		return self.idTable.get(id,None)
	
	def GetUniqueID (self,baseStr=None):
		if not baseStr:
			baseStr='%X'%random.randint(0,0xFFFF)
		idStr=baseStr
		idExtra=0
		while self.idTable.has_key(idStr):
			if not idExtra:
				idExtra=random.randint(0,0xFFFF)
			idStr='%s-%X'%(baseStr,idExtra)
			idExtra=idExtra+1
		return idStr

	def Read(self,src=None,reqManager=None,**args):
		if src:
			# Read from this stream, ignore baseURI
			self.ReadFromStream(src)
		elif self.baseURI is None:
			raise XMLMissingLocationError
		elif self.url.scheme=='file':
			#f=codecs.open(urllib.url2pathname(self.url.path),'rb','utf-8')
			f=open(urllib.url2pathname(self.url.path),'rb')
			try:
				self.ReadFromStream(f)
			finally:
				f.close()
		elif self.url.scheme in ['http','https']:
			if reqManager is None:
				reqManager=http.HTTPRequestManager()
			req=http.HTTPRequest(self.baseURI)
			reqManager.ProcessRequest(req)
			if req.status==200:
				mtype=req.response.GetContentType()
				if mtype is None:
					# We'll attempt to do this with xml and utf8
					charset='utf8'
					raise UnimplementedError
				else:
					mimetype=mtype.type.lower()+'/'+mtype.subtype.lower()
					if not self.ValidateMimeType(mimetype):
						raise XMLContentTypeError(mimetype)
					self.ReadFromStream(StringIO(req.resBody))
			else:
				raise XMLUnexpectedHTTPResponse(str(req.status))
		else:
			raise XMLUnsupportedScheme
	
	def ReadFromStream(self,src):
		self.cObject=self
		self.objStack=[]
		self.data=[]
		self.parser.parse(src)
		
	def startElement(self, name, attrs):
		parent=self.cObject
		self.objStack.append(self.cObject)
		if self.data:
			parent.AddChild(string.join(self.data,''))
			self.data=[]
		#print name, qname, attrs
		#eClass=self.classMap.get(name,self.classMap.get((name[0],None),XMLElement))
		eClass=self.GetElementClass(name)
		self.cObject=eClass(parent)
		self.cObject.SetXMLName(name)
		for attr in attrs.keys():
			self.cObject.SetAttribute(attr,attrs[attr])

	def characters(self,ch):
		self.data.append(ch)
			
	def endElement(self,name):
		if self.objStack:
			parent=self.objStack.pop()
		else:
			parent=None
		if self.data:
			self.cObject.AddChild(string.join(self.data,''))
			self.data=[]
		self.cObject.GotChildren()
		parent.AddChild(self.cObject)
		self.cObject=parent
			
	def Create(self,dst=None,**args):
		if dst:
			self.WriteToStream(dst)
		elif self.baseURI is None:
			raise XMLMissingLocationError
		elif self.url.scheme=='file':
			f=codecs.open(urllib.url2pathname(self.url.path),'wb','utf-8')
			try:
				self.WriteToStream(f)
			finally:
				f.close()
		else:
			raise XMLUnsupportedSchemeError
	
	def WriteToStream(self,f):
		f.write('<?xml version="1.0" encoding="utf-8"?>\n')
		if self.rootElement:
			self.rootElement.WriteXML(f)
	
	def Update(self,reqManager=None):
		pass
	
	def Delete(self,reqManager=None):
		pass
		

def ParseXMLClass(classDefStr):
	"""The purpose of this function is to provide a convenience for creating character
	class definitions from the XML specification documents.  The format of those
	declarations is along these lines (this is the definition for Char):

	#x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
	
	We parse strings in this format into a character class and then print out a
	declaration of it suitable for including in code."""
	c=CharClass()
	definitions=classDefStr.split('|')
	for d in definitions:
		hexStr=[]
		for di in d:
			if di in '[]#x':
				continue
			else:
				hexStr.append(di)
		rangeDef=map(lambda x:int(x,16),string.split(string.join(hexStr,''),'-'))
		if len(rangeDef)==1:
			a=rangeDef[0]
			if a>maxunicode:
				print "Warning: character outside narrow python build (%X)"%a
			else:
				c.AddChar(unichr(a))
		elif len(rangeDef)==2:
			a,b=rangeDef
			if a>maxunicode:
				print "Warning: character range outside narrow python build (%X-%X)"%(a,b)
			elif b>maxunicode:
				print "Warning: character range truncated due to narrow python build (%X-%X)"%(a,b)
				b=maxunicode
				c.AddRange(unichr(a),unichr(b))
			else:
				c.AddRange(unichr(a),unichr(b))			
	print repr(c)
