#! /usr/bin/env python

from xml.sax import make_parser, handler, SAXParseException, saxutils
import string, types
from StringIO import StringIO
import urlparse, urllib,  os.path
from sys import maxunicode
import codecs, random
from types import *
from copy import copy

xml_base='xml:base'
xml_lang='xml:lang'
xml_space='xml:space'

XML_MIMETYPES={
	'text/xml':True,
	'application/xml':True,
	'text/application+xml':True	
	}

XMLMixedContent=0
XMLElementContent=1
XMLEmpty=2
	
class XMLError(Exception): pass

class XMLContentTypeError(XMLError): pass
class XMLIDClashError(XMLError): pass
class XMLIDValueError(XMLError): pass
class XMLMissingLocationError(XMLError): pass
class XMLMixedContentError(XMLError): pass
class XMLParentError(XMLError): pass
class XMLUnexpectedHTTPResponse(XMLError): pass
class XMLUnsupportedSchemeError(XMLError): pass
class XMLValidationError(XMLError): pass

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

def IsS(c):
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

def NormPath(urlPath):
	"""Normalizes a URL path, removing '.' and '..' components.
	
	An empty string (which tends to be a relative URL matching the current URL
	exactly) is returned unchanged.  The string "./" is also returned unchanged
	to avoid confusion with the empty string."""
	components=urlPath.split('/')
	pos=0
	while pos<len(components):
		if components[pos]=='.':
			# We can always remove '.', though "./" will need fixing later
			del components[pos]
		elif components[pos]=='':
			if pos>0 and pos<len(components)-1:
				# Remove "//"
				del components[pos]
			else:
				pos=pos+1
		elif components[pos]=='..':
			if pos>0 and components[pos-1] and components[pos-1]!='..':
				# remove "dir/.."
				del components[pos-1:pos+1]
				pos=pos-1
			else:
				pos=pos+1
		else:
			pos=pos+1
	if components==['']:
		return "./"
	else:
		return string.join(components,'/')


def RelPath(basePath,urlPath,touchRoot=False):
	"""Return urlPath relative to basePath"""
	basePath=NormPath(basePath).split('/')
	urlPath=NormPath(urlPath).split('/')
	if basePath[0]:
		raise XMLURLPathError(string.join(basePath,'/'))
	if urlPath[0]:
		raise XMLURLPathError(string.join(urlPath,'/'))
	result=[]
	pos=1
	while pos<len(basePath):
		if result:
			if pos==2 and not touchRoot:
				result=['']+result
				break
			result=['..']+result
		else:
			if pos>=len(urlPath) or basePath[pos]!=urlPath[pos]:
				result=result+urlPath[pos:]
		pos=pos+1
	if not result and len(urlPath)>len(basePath):
		# full match but urlPath is longer
		return string.join(urlPath[len(basePath)-1:],'/')
	elif result==['']:
		return "./"
	else:
		return string.join(result,'/')		


def OptionalAppend(itemList,newItem):
	"""A convenience function which appends newItem to itemList if newItem is not None""" 
	if newItem is not None:
		itemList.append(newItem)

		
class XMLElement:
	def __init__(self,parent,name=None):
		self.parent=parent
		if name is None:
			if hasattr(self.__class__,'XMLNAME'):
				self.xmlname=self.__class__.XMLNAME
			else:
				self.xmlname=None
		else:
			self.xmlname=name
		self.id=None
		self._attrs={}
		self._children=[]

	def SetXMLName(self,name):
		self.xmlname=name
		
	def GetDocument(self):
		"""Returns the document that contains the element.
		
		If the element is an orphan, or is the descendent of an orphan
		then None is returned."""
		if self.parent:
			if isinstance(self.parent,XMLDocument):
				return self.parent
			else:
				return self.parent.GetDocument()
		else:
			return None

	def SetID(self,id):
		"""Sets the id of the element, registering the change with the enclosing document.
		
		If the id is already taken then XMLIDClashError is raised."""
		if not self.IsValidName(id):
			raise XMLIDValueError(id)
		doc=self.GetDocument()
		if doc:
			doc.UnregisterElement(self)
			self.id=id
			doc.RegisterElement(self)
		else:
			self.id=id
		
	def GetAttributes(self):
		"""Returns a dictionary object that maps attribute names onto values.
		
		Each attribute value is represented as a (possibly unicode) string.
		Derived classes should override this method if they define any custom
		attribute setters.
		
		The dictionary returned represents a copy of the information in the element
		and so may be modified by the caller."""
		attrs=copy(self._attrs)
		if self.id:
			attrs[self.__class__.ID]=self.id
		return attrs

	def SetAttribute(self,name,value):
		"""Sets the value of an attribute.
		
		The attribute name is assumed to be a string or unicode string.  The
		default implementation checks for a custom setter and calls it if
		defined and does no further processing.  A custom setter is a method of
		the form Set_aname.
		
		XML attribute names may contain many characters that are not legal in
		Python method names but, in practice, the only significant limitation is
		the colon.  This is replaced by '_' before searching for a custom setter.
		
		If no custom setter is defined then the default processing stores the
		attribute in a local dictionary, a copy of which can be obtained with
		the GetAttributes method.  Additionally, if the class has an ID
		attribute it is used as the name of the attribute that represents the
		element's ID.  ID handling is performed automatically at document level
		and the element's 'id' attribute set accordingly."""
		setter=getattr(self,"Set_"+name,None)
		if setter is None:
			if hasattr(self.__class__,'ID') and name==self.__class__.ID:
				self.SetID(value)
			else:
				self._attrs[name]=value
		else:
			setter(value)
	
	def IsValidName(self,value):
		return IsValidName(value)

	def IsEmpty(self):
		"""Returns True/False indicating whether this element *must* be empty.
		
		If the class defines the XMLCONTENT attribute then the model is taken
		from there and this method return True only if XMLCONTENT is XMLEmpty.
		
		Otherwise, the method defaults to False"""
		if hasattr(self.__class__,'XMLCONTENT'):
			return self.__class__.XMLCONTENT==XMLEmpty
		else:
			return False
		
	def IsMixed(self):
		"""Indicates whether or not the element *may* contain mixed content.
		
		If the class defines the XMLCONTENT attribute then the model is taken
		from there and this method return True only if XMLCONTENT is
		XMLMixedContent.
		
		Otherwise, the method default ot True"""
		if hasattr(self.__class__,'XMLCONTENT'):
			return self.__class__.XMLCONTENT==XMLMixedContent
		else:
			return True

	def GetChildren(self):
		"""Returns a list of the element's children.
		
		This method returns a copy of local list of children and so may be
		modified by the caller.  Derived classes with custom factory methods
		must override this method.

		Each child is either a string type, unicode string type or instance of
		XMLElement (or a derived class thereof)"""
		return copy(self._children)

	def ChildElement(self,childClass,name=None):
		"""Returns a new child of the given class attached to this element.
		
		A new child is created and attached to the element's model unless the
		model supports a single element of the given childClass and the element
		already exists, in which case the existing instance is returned.
		
		childClass is a class (or callable) used to create a new instance.
		
		name is the name given to the element (by the caller).  If no name is
		given then the default name for the child should be used.  When the
		child returned is an existing instance name is ignored.
		
		The default implementation checks for a custom factory method and calls
		it if defined and does no further processing.  A custom factory method
		is a method of the form ClassName or an attribute that is being used to
		hold instances of this child.  The attribute must already exist and can
		be one of None (optional child, new child is created), a list (optional
		repeatable child, new child is created and appended) or an instance of
		childClass (required child, no new child is created, existing instance
		returned).
		
		If no custom factory method is defined then the default processing
		simply creates an instance of child (if necessary) and attaches it to
		the local list of children."""
		if self.IsEmpty():
			self.ValidationError("Unexpected child element",name)
		if hasattr(self,childClass.__name__):
			factory=getattr(self,childClass.__name__)
			if type(factory) is MethodType:
				child=factory()
				if name:
					child.SetXMLName(name)
				return child
			elif type(factory) is NoneType:
				child=childClass(self)
				setattr(self,childClass.__name__,child)
			elif type(factory) is ListType:
				child=childClass(self)
				factory.append(child)
			elif type(factory) is InstanceType and isinstance(factory,childClass):
				child=factory
			else:
				raise TypeError
		else:
			try:
				child=childClass(self)
			except TypeError:
				raise TypeError("Can't create %s in %s"%(childClass.__name__,self.__class__.__name__))
			self._children.append(child)
		if name:
			child.SetXMLName(name)
		return child
			
	def AdoptChild(self,child):
		"""Attaches an existing orphan child element to this one.
		
		The default implementation checks for a custom adoption method and
		calls it if defined and does no further processing.  A custom adoption
		method is a method of the form Adopt_ClassName.
		
		If a custom factory method is defined for the class of child but not a
		custom adoption method then TypeError is raised.  You are not required
		to provide a custom adoption method but you must do so if you wish to
		support the adoption of elements that would other require a custom
		factory to instantiate.
		
		If no custom adoption method or custom factory exists and the element is
		not empty then the child is added to the local list of children."""
		if child.parent:
			raise XMLParentError
		elif self.IsEmpty():
			self.ValidationError("Unexpected child element",child.xmlname)
		factory=getattr(self,child.__class__.__name__,None)
		adopter=getattr(self,"Adopt_"+child.__class__.__name__,None)
		if adopter is None:
			if factory:
				raise TypeError
			child.parent=self
			child.AttachToDocument()
			self._children.append(child)
		else:
			return adopter(child)
			
	def AttachToDocument(self,doc=None):
		"""Called when the element is first attached to a document.
		
		The default implementation ensures that any ID attributes belonging
		to this element or its descendents are registered."""
		if doc is None:
			doc=self.GetDocument()
		if doc:
			if self.id:
				doc.RegisterElement(self)
			for child in self.GetChildren():
				if isinstance(child,XMLElement):
					child.AttachToDocument(doc)
	
	def DetachFromDocument(self,doc=None):
		"""Called when an element is being detached from a document.
		
		The default implementation ensure that an ID attributes belonging
		to this element or its descendents are unregistered."""
		if doc is None:
			doc=self.GetDocument()
		if doc:
			if self.id:
				doc.UnregisterElement(self)
			for child in self.GetChildren():
				if isinstance(child,XMLElement):
					child.DetachFromDocument(doc)
		
	def AddData(self,data):
		"""Adds a string or unicode string to this element's children.
		
		If the element does not have mixed content then the data is ignored if
		it is white space, otherwise, ValidationError is called with the
		offending data."""
		if self.IsMixed():
			self._children.append(data)
		else:
			ws=True
			for c in data:
				if not IsS(c):
					ws=False
			if not ws:
				self.ValidationError("Unexpected data",data)

	def GotChildren(self):
		"""Notifies an element that all children have been added or created."""
		pass
	
	def GetValue(self):
		"""Returns a single unicode string representing the element's data.
		
		If the element contains child elements XMLMixedContentError is raised.
		
		If the element is empty None is returned."""		
		children=self.GetChildren()
		for child in children:
			if not type(child) in StringTypes:
				raise XMLMixedContentError
		if children:
			return string.join(map(unicode,children),'')
		else:
			return None

	def SetValue(self,value):
		"""Replaces the value of the element with the (unicode) value.
		
		If the element has mixed content then XMLMixedContentError is
		raised."""
		if not self.IsMixed():
			raise XMLMixedContentError
		children=self.GetChildren()
		if len(children)!=len(self._children):
			raise XMLMixedContentError
		for child in children:
			if isinstance(child,XMLElement):
				child.DetachFromDocument()
				child.parent=None
		self._children=[unicode(value)]

	def ValidationError(self,msg,data=None,aname=None):
		"""Indicates that a validation error occurred in this element.
		
		An error message indicates the nature of the error.

		The data that caused the error may be given in data.
		
		Furthermore, the  attribute name may also be given indicating that the
		offending data was in an attribute of the element and not the element
		itself."""
		doc=self.GetDocument()
		if doc:
			doc.ValidationError(msg,self,data,aname)
		else:
			raise XMLValidationError(msg)
			

	def SortNames(self,nameList):
		"""Given a list of element or attribute names, sorts them in a predictable order
		
		The default implementation assumes that the names are strings or unicode strings
		so uses the default sort method."""
		nameList.sort()
		
	def __cmp__(self,element):
		"""Compares element with this one.
		
		XMLELement can only be compared with other XMLElements."""
		if not isinstance(element,XMLElement):
			raise TypeError
		#print "Comparing: <%s>, <%s>"%(str(self.xmlname),str(element.xmlname))
		result=cmp(self.xmlname,element.xmlname)
		if result:
			return result
		# sort and compare all attributes
		selfAttrs=self.GetAttributes()
		selfAttrNames=selfAttrs.keys()
		self.SortNames(selfAttrNames)
		elementAttrs=element.GetAttributes()
		elementAttrNames=elementAttrs.keys()
		element.SortNames(elementAttrNames)
		#print "Comparing attributes: \n%s\n...\n%s"%(str(selfAttrNames),str(elementAttrNames))
		for i in xrange(len(selfAttrNames)):
			if i>=len(elementAttrNames):
				# We're bigger by virtue of having more attributes!
				return 1
			selfAName=selfAttrNames[i]
			elementAName=elementAttrNames[i]
			result=cmp(selfAName,elementAName)
			if result:
				return result
			result=cmp(selfAttrs[selfAName],elementAttrs[selfAName])
			if result:
				return result
		if len(elementAttrNames)>len(selfAttrNames):
			# They're bigger by virtue of having more attributes!
			return -1
		selfChildren=self.GetChildren()
		elementChildren=element.GetChildren()
		for i in xrange(len(selfChildren)):
			if i>=len(elementChildren):
				# We're bigger by virtue of having more children
				return 1
			if isinstance(selfChildren[i],XMLElement):
				if isinstance(elementChildren[i],XMLElement):
					result=cmp(selfChildren[i],elementChildren[i])
				else:
					# elements sort before data
					result=-1
			elif isinstance(elementChildren[i],XMLElement):
				result=1
			else:
				# Data sorts by string comparison
				result=cmp(selfChildren[i],elementChildren[i])
			if result:
				return result
		if len(elementChildren)>len(selfChildren):
			return -1
		# Name, all attributes and child elements match!!
		return 0
	
	def __str__(self):
		"""Returns the XML element as a string"""
		s=StringIO()
		self.WriteXML(s)
		return s.getvalue()
		
	def GetBase(self):
		return self._attrs.get(xml_base,None)
	
	def SetBase(self,base):
		if base is None:
			self._attrs.pop(xml_base,None)
		else:
			self._attrs[xml_base]=str(base)

	def ResolveBase(self):
		"""Returns a fully specified URI for the base of the current element.
		
		The URI is calculated using any xml:base values of the element or its
		ancestors and ultimately relative to the baseURI.
		
		If the element is not contained by an XMLDocument, or the document does
		not have a fully specified baseURI then the return result may be a
		relative path or even None, if no base information is available."""
		baser=self
		baseURI=None
		while baser:
			rebase=baser.GetBase()
			if baseURI:
				baseURI=urlparse.urljoin(rebase,baseURI)
			else:
				baseURI=rebase
			if isinstance(baser,XMLElement):
				baser=baser.parent
			else:
				break
		return baseURI
				
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
		baseURI=self.ResolveBase()
		if baseURI:
			return urlparse.urljoin(baseURI,str(uri))
		else:
			return uri
	
	def RelativeURI(self,href):
		"""Returns href expressed relative to the element's base.

		If href is a relative URI then it is converted to a fully specified URL
		by interpreting it as being the URI of a file expressed relative to the
		current working directory.

		If the element does not have a fully-specified base URL then href is
		returned as a fully-specified URL itself."""
		result=[]
		hrefBase='file://'+urllib.pathname2url(os.getcwd())+'/'
		href=urlparse.urljoin(hrefBase,href)
		hrefParts=urlparse.urlsplit(href)
		baseParts=urlparse.urlsplit(self.ResolveBase())
		if not baseParts.scheme or baseParts.scheme!=hrefParts.scheme:
			return href
		if baseParts.scheme not in ('file','http','https'):
			raise XMLUnsupportedSchemeError(self.url.scheme)
		result.append('')
		if baseParts.netloc!=hrefParts.netloc:
			result=result+list(hrefParts[1:])
			return urlparse.urlunsplit(result)
		result.append('')
		if baseParts.path!=hrefParts.path:
			result.append(RelPath(baseParts.path,hrefParts.path))
			result=result+list(hrefParts[3:])
			return urlparse.urlunsplit(result)
		result.append('')
		if baseParts.query!=hrefParts.query:
			result=result+list(hrefParts[3:])
			return urlparse.urlunsplit(result)
		result.append('')
		if baseParts.fragment!=hrefParts.fragment:
			result=result+list(hrefParts[4:])
			return urlparse.urlunsplit(result)
		# href is exactly base!
		return ""		

	def GetLang(self):
		return self._attrs.get(xml_lang,None)
	
	def SetLang(self,lang):
		if lang is None:
			self._attrs.pop(xml_lang,None)
		else:
			self._attrs[xml_lang]=lang

	def ResolveLang(self):
		"""Returns the effective language for the current element.
		
		The language is resolved using the xml:lang value of the element or its
		ancestors.  If no xml:lang is in effect then None is returned."""
		baser=self
		baseLang=None
		while baser:
			lang=baser.GetLang()
			if lang:
				return lang
			if isinstance(baser,XMLElement):
				baser=baser.parent
			else:
				break
		return None
	
	def GetSpace(self):
		return self._attrs.get(xml_space,None)
	
	def SetSpace(self,space):
		if space is None:
			self._attrs.pop(xml_space,None)
		else:
			self._attrs[xml_space]=space
	
	def WriteXMLAttributes(self,attributes):
		"""Adds strings representing the element's attributes
		
		attributes is a list of unicode strings.  Attributes should be appended
		as strings of the form 'name="value"' with values escaped appropriately
		for XML output."""
		attrs=self.GetAttributes()
		keys=attrs.keys()
		self.SortNames(keys)
		for a in keys:
			attributes.append('%s=%s'%(a,saxutils.quoteattr(attrs[a])))
		
	def WriteXML(self,f,indent='',tab='\t'):
		if tab:
			ws='\n'+indent
			indent=indent+tab
		else:
			ws=''
		if hasattr(self.__class__,'XMLMIXED') and self.__class__.XMLMIXED:
			# inline all children
			indent=''
			tab=''
		attributes=[]
		self.WriteXMLAttributes(attributes)
		if attributes:
			attributes[0:0]=['']
			attributes=string.join(attributes,' ')
		else:
			attributes=''
		children=self.GetChildren()
		if children:
			if type(children[0]) in StringTypes and len(children[0])>0 and IsS(children[0][0]):
				# First character is WS, so assume pre-formatted
				indent=tab=''
			f.write('%s<%s%s>'%(ws,self.xmlname,attributes))
			for child in children:
				if type(child) in types.StringTypes:
					# We force encoding of carriage return as these are subject to removal
					f.write(saxutils.escape(child,{'\r':'&#xD;'}))
					# if we have character data content skip closing ws
					ws=''
				else:
					child.WriteXML(f,indent,tab)
			f.write('%s</%s>'%(ws,self.xmlname))
		else:
			f.write('%s<%s%s/>'%(ws,self.xmlname,attributes))
				

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
		self.lang=None
		if root:
			if not issubclass(root,XMLElement):
				raise ValueError
			self.root=root(self)
		else:
			self.root=None
		self.SetBase(baseURI)
		#self.parser.setEntityResolver(self)
		self.idTable={}

	def __str__(self):
		"""Returns the XML document as a string"""
		s=StringIO()
		self.WriteXML(s)
		return s.getvalue()
				
	def SetDefaultNS(self,ns):
		self.defaultNS=ns
	
	def ValidateMimeType(self,mimetype):
		return XML_MIMETYPES.has_key(mimetype)
		
	def GetElementClass(self,name):
		"""Returns a class object suitable for representing name
		
		name is a unicode string representing the element name.
		
		The default implementation returns XMLElement."""
		return XMLElement

	def ChildElement(self,childClass,name=None):
		"""Creates the root element of the given document.
		
		The signature of this method matches the ChildElement method of
		XMLElement but no custom factory method mechanism exists.  If there
		is already a root element it is detached from the document first."""
		if self.root:
			self.root.DetachFromDocument()
			self.root.parent=None
			self.root=None
		child=childClass(self)
		if name:
			child.SetXMLName(name)
		self.root=child
		return self.root
		
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
	
	def SetLang(self,lang):
		"""Sets the default language for the document."""
		self.lang=lang
	
	def GetLang(self):
		"""Returns the default language for the document."""
		return self.lang
		
	def ValidationError(self,msg,element,data=None,aname=None):
		"""Called when a validation error is triggered by element.

		This method is designed to be overriden to implement custom error
		handling or logging (which is likely to be added in future to this
		module).

		msg contains a brief message suitable for describing the error in a log
		file.  data and aname have the same meanings as
		XMLElement.ValidationError."""
		pass
		
	def RegisterElement(self,element):
		if self.idTable.has_key(element.id):
			raise XMLIDClashError
		else:
			self.idTable[element.id]=element
	
	def UnregisterElement(self,element):
		if element.id:
			del self.idTable[element.id]
	
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
			parent.AddData(string.join(self.data,''))
			self.data=[]
		eClass=self.GetElementClass(name)
		self.cObject=parent.ChildElement(eClass,name)
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
			self.cObject.AddData(string.join(self.data,''))
			self.data=[]
		self.cObject.GotChildren()
		self.cObject=parent
			
	def Create(self,dst=None,**args):
		if dst:
			self.WriteXML(dst)
		elif self.baseURI is None:
			raise XMLMissingLocationError
		elif self.url.scheme=='file':
			fPath=urllib.url2pathname(self.url.path)
			fdir,fname=os.path.split(fPath)
			if not os.path.isdir(fdir):
				os.makedirs(fdir)
			f=codecs.open(fPath,'wb','utf-8')
			try:
				self.WriteXML(f)
			finally:
				f.close()
		else:
			raise XMLUnsupportedSchemeError(self.url.scheme)
	
	def WriteXML(self,f,tab='\t'):
		if tab:
			f.write('<?xml version="1.0" encoding="utf-8"?>')
		else:
			f.write('<?xml version="1.0" encoding="utf-8"?>\n')
		if self.root:
			self.root.WriteXML(f,'',tab)
	
	def Update(self,reqManager=None):
		pass
	
	def Delete(self,reqManager=None):
		pass

	def DiffString(self,otherDoc,before=10,after=5):
		"""Compares this document to otherDoc and returns first point of difference."""
		lines=str(self).split('\n')
		otherLines=str(otherDoc).split('\n')
		output=[]
		i=0
		iDiff=None
		while i<len(lines) and i<len(otherLines):
			if i>=len(lines):
				line=''
			else:
				line=lines[i]
			if i>=len(otherLines):
				otherLine=''
			else:
				otherLine=otherLines[i]
			if line==otherLine:
				i=i+1
				continue
			else:
				# The strings differ from here.
				iDiff=i
				break
		if iDiff is None:
			return None
		for i in xrange(iDiff-before,iDiff):
			if i<0:
				continue
			if i>=len(lines):
				line='[%3i] **EOF**'%i
			else:
				line='[%3i] '%i+lines[i]
			output.append(line)
		output.append('>>>>> Showing %i lines of difference'%after)
		for i in xrange(iDiff,iDiff+after):
			if i>=len(lines):
				line='[%3i] **EOF**'%i
			else:
				line='[%3i] '%i+repr(lines[i])
			output.append(line)
		output.append('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
		for i in xrange(iDiff,iDiff+after):
			if i>=len(otherLines):
				line='[%3i] **EOF**'%i
			else:
				line='[%3i] '%i+repr(otherLines[i])
			output.append(line)
		return string.join(output,'\n')


def MapClassElements(classMap,namespace):
	"""Searches namespace and adds element name -> class mappings to classMap
	
	If namespace is none the current namespace is searched.  The search is
	not recursive, to add class elements from imported modules you must call
	MapClassElements for each module."""
	if type(namespace) is not DictType:
		namespace=namespace.__dict__
	names=namespace.keys()
	for name in names:
		obj=namespace[name]
		if type(obj) is ClassType and issubclass(obj,XMLElement):
			if hasattr(obj,'XMLNAME'):
				classMap[obj.XMLNAME]=obj


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
