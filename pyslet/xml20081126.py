#! /usr/bin/env python

import string, types
from StringIO import StringIO
import urlparse, os, os.path
from sys import maxunicode
import codecs, random
from types import *
from copy import copy

from pyslet.rfc2396 import URIFactory, URI, FileURL

xml_base='xml:base'
xml_lang='xml:lang'
xml_space='xml:space'

XML_MIMETYPES={
	'text/xml':True,
	'application/xml':True,
	'text/application+xml':True	
	}

def ValidateXMLMimeType(mimetype):
	return XML_MIMETYPES.has_key(mimetype)
	
class XMLError(Exception): pass

class XMLAttributeSetter(XMLError): pass
class XMLContentTypeError(XMLError): pass
class XMLForbiddenEntityReference(XMLError): pass
class XMLMissingFileError(XMLError): pass
class XMLMissingLocationError(XMLError): pass
class XMLMixedContentError(XMLError): pass
class XMLParentError(XMLError): pass
class XMLUnimplementedError(XMLError): pass
class XMLUnexpectedError(XMLError): pass
class XMLUnexpectedHTTPResponse(XMLError): pass
class XMLUnsupportedSchemeError(XMLError): pass

class XMLFatalError(XMLError): pass
class XMLCommentError(XMLFatalError): pass
class XMLWellFormedError(XMLFatalError): pass

class XMLValidityError(XMLError): pass
class XMLIDClashError(XMLValidityError): pass
class XMLIDValueError(XMLValidityError): pass


class XMLUnknownChild(XMLError): pass

from pyslet.unicode5 import CharClass
from pyslet import rfc2616 as http


def EscapeCharData(src,quote=False):
	"""Returns a unicode string with XML reserved characters escaped.
	
	We also escape return characters to prevent them being ignored.  If quote
	is True then the string is returned as a quoted attribute value."""
	data=[]
	apos=0;quot=0
	for c in src:
		if c=='&':
			data.append('&amp;')
		elif c=='<':
			data.append('&lt;')
		elif c=='>':
			data.append('&gt;')
		elif c=='\r':
			data.append('&#xD;')
		elif c=='"':
			quot+=1
			data.append(c)
		elif c=="'":
			apos+=1
			data.append(c)
		else:
			data.append(c)
	if quote:
		if quot>apos:
			if apos:
				# escape apos
				for i in xrange(len(data)):
					if data[i]=="'":
						data[i]='&apos;'
			data=["'"]+data+["'"]
		else:
			if quot:
				# escape quot
				for i in xrange(len(data)):
					if data[i]=='"':
						data[i]='&quot;'
			data=['"']+data+['"']
	return string.join(data,'')								


def EscapeCharData7(src,quote=False):
	"""Returns a unicode string with reserved and non-ASCII characters escaped."""
	dst=[]
	if quote:
		if "'" in src:
			q='"';qStr='&#x22'
		elif '"' in src:
			q="'";qStr='&#x27'
		else:
			q='"';qStr='&#x22'
		dst.append(q)
	else:
		q=None;qStr=''
	for c in src:
		if ord(c)>0x7F:
			if ord(c)>0xFF:
				if ord(c)>0xFFFF:
					if ord(c)>0xFFFFFF:
						dst.append("&#x%08X;"%ord(c))
					else:
						dst.append("&#x%06X;"%ord(c))
				else:
						dst.append("&#x%04X;"%ord(c))
			else:
					dst.append("&#x%02X;"%ord(c))
		elif c=='<':
			dst.append("&lt;")
		elif c=='&':
			dst.append("&amp;")
		elif c=='>':
			dst.append("&gt;")
		elif c=='\r':
			dst.append("&#xD;")
		elif c==q:
			dst.append(qStr)
		else:
			dst.append(c)
	if quote:
		dst.append(q)	
	return string.join(dst,'')
	

class XMLContextMixin:
	def __init__(self,parent):
		"""Mixin class for XMLElement and XMLDocument shared attributes.
		
		XML documents are defined hierarchicaly, each element has a parent
		which is either another element or an XML document."""
		self.parent=parent
		"""The parent of this element, for XML documents this attribute is used
		as a sentinel to simplify traversal of the hierarchy and is set to
		None."""

	def GetChildren(self):
		"""Returns a list of this object's children."""
		raise NotImplementedError
	
	def GetChildClass(self,stagClass):
		"""Returns the element class implied by the STag for stagClass in this context.
		
		This method is only called when the :py:attr:`XMLParser.sgmlOmittag`
		option is in effect.  It is called prior to :py:meth:`ChildElement`
		below and gives the context (the parent element or document) a chance to
		modify the child element that will be created (or reject it out-right,
		byre returning None).
		
		For well-formed XML documents the default implementation is sufficient
		as it simply returns *stagClass*.
		
		The XML parser may pass None for *stagClass* indicating that PCDATA has
		been found in element content.  This method should return the first
		child element that may contain (directly or indirectly) PCDATA or None
		if no children may contain PCDATA"""
		return stagClass

	def ChildElement(self,childClass,name=None):
		"""Returns a new child of the given class attached to this object.
		
		-	childClass is a class (or callable) used to create a new instance
			of :py:class:`XMLElement`.
		
		-	name is the name given to the element (by the caller).  If no name is 
			given then the default name for the child should be used.  When the
			child returned is an existing instance, name is ignored."""
		raise NotImplementedError
			
	def ProcessingInstruction(self,target,instruction=''):
		"""Abstract method for handling processing instructions encountered by
		the parser while parsing this object's content.

		By default, processing instructions are ignored."""
		pass
		

class XMLDocument(XMLContextMixin):
	"""Base class for all XML documents."""
	
	def __init__(self, root=None, baseURI=None, reqManager=None, **args):
		"""Initialises a new XMLDocument from optional keyword arguments.
		
		With no arguments, a new XMLDocument is created with no baseURI
		or root element.
		
		If root is a class object (descended from XMLElement) it is used
		to create the root element of the document.
		
		baseURI can be set on construction (see SetBase) and a reqManager object
		can optionally be passed for managing and http(s) connections.
		"""
		XMLContextMixin.__init__(self,None)
		self.reqManager=reqManager
		self.baseURI=None
		"""The base uri of the document."""
		self.lang=None
		"""The default language of the document."""
		self.declaration=None
		"""The XML declaration (or None if no XMLDeclaration is used)"""
		self.dtd=None
		"""The dtd associated with the document."""
		self.root=None
		"""The root element or None if no root element has been created yet."""
		if root:
			if not issubclass(root,XMLElement):
				raise ValueError
			self.root=root(self)
		self.SetBase(baseURI)
		self.idTable={}

	def GetChildren(self):
		"""If the document has a root element it is returned in a single item list,
		otherwise an empty list is returned."""
		if self.root:
			return [self.root]
		else:
			return []

	def __str__(self):
		"""Returns the XML document as a string"""
		s=StringIO()
		self.WriteXML(s,EscapeCharData7)
		return str(s.getvalue())
	
	def __unicode__(self):
		"""Returns the XML document as a unicode string"""
		s=StringIO()
		self.WriteXML(s,EscapeCharData)
		return unicode(s.getvalue())

	def XMLParser(self,entity):
		"""Returns an :py:class:`XMLParser` instance suitable for parsing this type of document.
		
		This method allows some document classes to override the parser used to
		parse them.  This method is only used when parsing existing document
		instances (see :py:meth:`Read` for more information).

		Classes that override this method may still register themselves with
		:py:func:`RegisterDocumentClass` but if they do then the default
		:py:class:`XMLParser` object will be used when the this document class
		is automatically created when parsing an unidentified XML stream."""
		return XMLParser(entity)
					
	def GetElementClass(self,name):
		"""Returns a class object suitable for representing name
		
		name is a unicode string representing the element name.
		
		The default implementation returns XMLElement."""
		return XMLElement

	def ChildElement(self,childClass,name=None):
		"""Creates the root element of the given document.
		
		If there is already a root element it is detached from the document
		first using :py:meth:`XMLElement.DetachFromDocument`."""
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
		
		*baseURI* should be an instance of :py:class:`pyslet.rfc2396.URI` or an
		object that can be passed to its constructor.
		
		Relative file paths are resolved relative to the current working
		directory immediately and the absolute URI is recorded as the document's
		*baseURI*."""
		if baseURI is None:
			self.baseURI=None
		else:
			if isinstance(baseURI,URI):
				self.baseURI=baseURI
			else:
				self.baseURI=URIFactory.URI(baseURI)
			if not self.baseURI.IsAbsolute():
				cwd=URIFactory.URLFromPathname(os.path.join(os.getcwd(),os.curdir))
				self.baseURI=self.baseURI.Resolve(cwd)
			
	def GetBase(self):
		"""Returns a string representation of the document's baseURI."""
		if self.baseURI is None:
			return None
		else:
			return str(self.baseURI)
	
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
		raise XMLValidityError("%s (in %s)"%(msg,element.xmlname))
		
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

	def Read(self,src=None,**args):
		if src:
			# Read from this stream, ignore baseURI
			if isinstance(src,XMLEntity):
				self.ReadFromEntity(src)
			else:
				self.ReadFromStream(src)
		elif self.baseURI is None:
			raise XMLMissingLocationError
		else:
			e=XMLEntity(self.baseURI,reqManager=self.reqManager)
			self.ReadFromEntity(e)
	
	def ReadFromStream(self,src):
		self.data=[]
		e=XMLEntity(src,reqManager=self.reqManager)
		self.ReadFromEntity(e)
		
	def ReadFromEntity(self,e):
		self.data=[]
		parser=self.XMLParser(e)
		parser.ParseDocument(self)
					
	def Create(self,dst=None,**args):
		"""Creates the XMLDocument.
		
		Create outputs the document as an XML stream.  The stream is written
		to the baseURI by default but if the 'dst' argument is provided then
		it is written directly to there instead.  dst can be any object that
		supports the writing of unicode strings.
		
		Currently only documents with file type baseURIs are supported.  The
		file's parent directories are created if required.  The file is
		always written using the UTF-8 as per the XML standard."""
		if dst:
			self.WriteXML(dst)
		elif self.baseURI is None:
			raise XMLMissingLocationError
		elif isinstance(self.baseURI,FileURL):
			fPath=self.baseURI.GetPathname()
			fdir,fname=os.path.split(fPath)
			if not os.path.isdir(fdir):
				os.makedirs(fdir)
			f=codecs.open(fPath,'wb','utf-8')
			try:
				self.WriteXML(f)
			finally:
				f.close()
		else:
			raise XMLUnsupportedSchemeError(self.baseURI.scheme)
	
	def WriteXML(self,writer,escapeFunction=EscapeCharData,tab='\t'):
		if tab:
			writer.write(u'<?xml version="1.0" encoding="UTF-8"?>')
		else:
			writer.write(u'<?xml version="1.0" encoding="UTF-8"?>\n')
		if self.root:
			self.root.WriteXML(writer,escapeFunction,'',tab,root=True)
	
	def Update(self,**args):
		"""Updates the XMLDocument.
		
		Update outputs the document as an XML stream.  The stream is written
		to the baseURI which must already exist!  Currently only documents
		with file type baseURIs are supported."""
		if self.baseURI is None:
			raise XMLMissingLocationError
		elif isinstance(self.baseURI,FileURL):
			fPath=self.baseURI.GetPathname()
			if not os.path.isfile(fPath):
				raise XMLMissingFileError(fPath)
			f=codecs.open(fPath,'wb','utf-8')
			try:
				self.WriteXML(f)
			finally:
				f.close()
		else:
			raise XMLUnsupportedSchemeError(self.baseURI.scheme)		
	
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


def RegisterDocumentClass(docClass,rootName,publicID=None,systemID=None):
	"""Registers a document class for use by :py:meth:`XMLParser.ParseDocument`.
	
	This module maintains a single table of document classes which can be
	used to identify the correct class to use to represent a document based
	on the information obtained from the DTD.
	
	-	*docClass*
		is the class object being registered, it must be derived from
		:py:class:`XMLDocument`
	
	-	*rootName*
		is the name of the root element or None if this class can be used with
		any root element.
	
	-	*publicID*
		is the public ID of the doctype, or None if any doctype can be used with
		this document class.
	
	-	*systemID*
		is the system ID of the doctype, this will usually be None indicating
		that the document class can match any system ID."""
	XMLParser.DocumentClassTable[(rootName,publicID,systemID)]=docClass

		
def IsChar(c):
	"""Tests if the character *c* matches the production for [2] Char.
	
	If *c* is None IsChar returns False."""
	return c and (ord(c)==0x9 or ord(c)==0xA or ord(c)==0xD or
		(ord(c)>=0x20 and ord(c)<=0xD7FF) or
		(ord(c)>=0xE000 and ord(c)<=0xFFFD) or
		(ord(c)>=0x10000 and ord(c)<=0x10FFFF))

# DiscouragedCharClass=ParseXMLClass("""[#x7F-#x84] | [#x86-#x9F] | [#xFDD0-#xFDEF] |
# 	[#x1FFFE-#x1FFFF] | [#x2FFFE-#x2FFFF] | [#x3FFFE-#x3FFFF] |
# 	[#x4FFFE-#x4FFFF] | [#x5FFFE-#x5FFFF] | [#x6FFFE-#x6FFFF] |
# 	[#x7FFFE-#x7FFFF] | [#x8FFFE-#x8FFFF] | [#x9FFFE-#x9FFFF] |
# 	[#xAFFFE-#xAFFFF] | [#xBFFFE-#xBFFFF] | [#xCFFFE-#xCFFFF] |
# 	[#xDFFFE-#xDFFFF] | [#xEFFFE-#xEFFFF] | [#xFFFFE-#xFFFFF] |
# 	[#x10FFFE-#x10FFFF]""")

DiscouragedCharClass=CharClass((u'\x7f',u'\x84'), (u'\x86',u'\x9f'), (u'\ufdd0',u'\ufdef'))

def IsDiscouraged(c):
	"""Tests if the character *c* is one of the characters discouraged in the specification.
	
	Note that this test is currently limited to the range of unicode characters
	available in the narrow python build."""
	return DiscouragedCharClass.Test(c)
	
	
def IsS(c):
	"""Tests if a single character *c* matches production [3] S"""
	return c and (ord(c)==0x9 or ord(c)==0xA or ord(c)==0xD or ord(c)==0x20)

def ContainsS(data):
	"""Tests if data contains any characters matching production [3] S"""
	for c in data:
		if IsS(c):
			return True
	return False
	
def StripLeadingS(data):
	"""Returns data with leading S removed."""
	s=0
	for c in data:
		if IsS(c):
			s+=1
		else:
			break
	if s:
		return data[s:]
	else:
		return data

def NormalizeSpace(data):
	"""Returns data normalized according to the further processing rules for attribute-value normalization:
	
	"...by discarding any leading and trailing space (#x20) characters, and by
	replacing sequences of space (#x20) characters by a single space (#x20)
	character"	"""
	result=[]
	sCount=2	# 0=no space; 1=add space; 2=don't add space 
	for c in data:
		if c==' ':
			if sCount==0:
				sCount=1
		else:
			if sCount==1:
				result.append(' ')
			result.append(c)
			sCount=0
	return string.join(result,'')			
			
def CollapseSpace(data,sMode=True,sTest=IsS):
	"""Returns data with all spaces collapsed to a single space.
	
	sMode determines the fate of any leading space, by default it is True and
	leading spaces are ignored provided the string has some non-space
	characters.

	You can override the test of what consitutes a space by passing a function
	for sTest, by default we use IsS.

	Note on degenerate case: this function is intended to be called with
	non-empty strings and will never *return* an empty string.  If there is no
	data then a single space is returned (regardless of sMode)."""
	result=[]
	for c in data:
		if sTest(c):
			if not sMode:
				result.append(u' ')
			sMode=True
		else:
			sMode=False
			result.append(c)
	if result:
		return string.join(result,'')
	else:
		return ' '


NameStartCharClass=CharClass(u':', (u'A',u'Z'), u'_', (u'a',u'z'),
	(u'\xc0',u'\xd6'), (u'\xd8',u'\xf6'),
	(u'\xf8',u'\u02ff'), (u'\u0370',u'\u037d'), (u'\u037f',u'\u1fff'),
	(u'\u200c',u'\u200d'), (u'\u2070',u'\u218f'), (u'\u2c00',u'\u2fef'),
	(u'\u3001',u'\ud7ff'), (u'\uf900',u'\ufdcf'), (u'\ufdf0',u'\ufffd'))

def IsNameStartChar(c):
	"""Tests if the character *c* matches production [4] NameStartChar."""
	return NameStartCharClass.Test(c)
	
NameCharClass=CharClass(NameStartCharClass, u'-', u'.', (u'0',u'9'),
	u'\xb7', (u'\u0300',u'\u036f'), (u'\u203f',u'\u2040'))

def IsNameChar(c):
	"""Tests if a single character *c* matches production [4a] NameChar"""
	return NameCharClass.Test(c)

def IsValidName(name):
	"""Tests if name is a string matching production [5] Name"""
	if name:
		if not IsNameStartChar(name[0]):
			return False
		for c in name[1:]:
			if not IsNameChar(c):
				return False
		return True
	else:
		return False

def IsReservedName(name):
	"""Tests if name is reserved for future standardization, e.g., if it begins with 'xml'."""
	if name:
		return name[:3].lower()=='xml'
	else:
		return False


PubidCharClass=CharClass(u' ',u'\x0d',u'\x0a', (u'0',u'9'), (u'A',u'Z'), 
	(u'a',u'z'), "-'()+,./:=?;!*#@$_%")

def IsPubidChar(c):
	"""Tests if the character *c* matches production for [13] PubidChar."""
	return PubidCharClass.Test(c)


def EscapeCDSect(src):
	"""Returns a unicode string enclosed in <!CDATA[[ ]]> with ]]> 
	by the clumsy sequence: ]]>]]&gt;<!CDATA[[
	
	Degenerate case: an empty string is returned as an empty string
	"""
	data=src.split(u']]>')
	if data:
		result=[u'<!CDATA[[',data[0]]
		for d in data[1:]:
			result.append(u']]>]]&gt;<!CDATA[[')
			result.append(d)
		result.append(u']]>')
		return string.join(result,u'')
	else:
		return u''
		

class XMLDTD:
	def __init__(self):
		"""An object that models a document type declaration.
		
		The document type declaration acts as a container for the
		entity, element and attribute declarations used in a document.
		"""
		self.name=None			#: The declared Name of the root element
		self.externalID=None	#: An :py:class:`XMLExternalID` instance (may be None)
		self.parameterEntities={}
		"""A dictionary of XMLParameterEntity instances keyed on entity name."""
		self.generalEntities={}
		"""A dictionary of XMLGeneralEntity instances keyed on entity name."""
		self.notations={}
		"""A dictionary of XMLNotation instances keyed on notation name."""
		self.elementList={}
		"""A dictionary of :py:class:`XMLElementType` definitions keyed on the
		name of element."""
		self.attributeLists={}
		"""A dictionary of dictionaries, keyed on element name.  Each of the
		resulting dictionaries is a dictionary of
		:py:class:`XMLAttributeDefinition` keyed on attribute name."""

	def DeclareEntity(self,entity):
		"""Declares an entity in this document.
		
		The same method is used for both general and parameter entities.  The
		value of *entity* can be either an :py:class:`XMLGeneralEntity` or an
		:py:class:`XMLParameterEntity` instance."""
		if isinstance(entity,XMLGeneralEntity):
			self.generalEntities[entity.name]=entity
		elif isinstance(entity,XMLParameterEntity):
			self.parameterEntities[entity.name]=entity
		else:
			raise ValueError

	def GetParameterEntity(self,name):
		"""Returns the parameter entity definition matching *name*.
		
		Returns an instance of :py:class:`XMLParameterEntity`.  If no parameter
		has been declared with *name* then None is returned."""
		return self.parameterEntities.get(name,None)
			
	def GetEntity(self,name):
		"""Returns the general entity definition matching *name*.
		
		Returns an instance of :py:class:`XMLGeneralEntity`.  If no general has
		been declared with *name* then None is returned."""
		return self.generalEntities.get(name,None)

	def DeclareNotation(self,notation):
		"""Declares a notation for this document.
		
		The value of *notation* must be a :py:class:`XMLNotation` instance."""
		self.notations[notation.name]=notation

	def GetNotation(self,name):
		"""Returns the notation declaration matching *name*.
		
		Returns an instance of :py:class:`XMLNotation`.  If no notation has
		been declared with *name* then None is returned."""
		return self.notations.get(name,None)

	def DeclareElementType(self,eType):
		"""Declares an element type.
		
		*eType* is an :py:class:`XMLElementType` instance containing the element
		definition."""
		eList=self.elementList.get(eType.name,None)
		if eList is None:
			self.elementList[eType.name]=eType
	
	def GetElementType(self,elementName):
		"""Looks up an element type definition.
		
		*elementName* is the name of the element type to look up
		
		The method returns an instance of :py:class:`XMLElementType` or
		None if no element with that name has been declared."""
		return self.elementList.get(elementName,None)

	def DeclareAttribute(self,elementName,attributeDef):
		"""Declares an attribute.
		
		-	*elementName*
			is the name of the element type which should have this attribute
			applied
		-	*attributeDef*
			is an :py:class:`XMLAttributeDefinition` instance describing the
			attribute being declared."""
		aList=self.attributeLists.get(elementName,None)
		if aList is None:
			self.attributeLists[elementName]=aList={}
		if not aList.has_key(attributeDef.name):
			aList[attributeDef.name]=attributeDef
		
	def GetAttributeList(self,name):
		"""Returns a dictionary of attribute definitions for the element type *name*.
		
		If there are no attributes declared for this element type, None is
		returned."""		
		return self.attributeLists.get(name,None)

	def GetAttributeDefinition(self,elementName,attributeName):
		"""Looks up an attribute definition.
		
		*elementName* is the name of the element type in which to search
		
		*attributeName* is the name of the attribute to search for.
		
		The method returns an instance of :py:class:`XMLAttributeDefinition` or
		None if no attribute matching this description has been declared."""		
		aList=self.attributeLists.get(name,None)
		if aList:
			return aList.get(attributeName,None)
		else:
			return None
		

class XMLTextDeclaration:

	def __init__(self,version="1.0",encoding="UTF-8"):
		"""Represents the text components of an XML declaration.
		
		Both *version* and *encoding* are optional, though one or other are
		required depending on the context in which the declaration will be
		used."""
		self.version=version
		self.encoding=encoding


class XMLDeclaration(XMLTextDeclaration):

	def __init__(self,version,encoding="UTF-8",standalone=False):
		"""Represents a full XML declaration.
	
		Unlike the parent class, :py:class:`XMLTextDeclaration`, the version is
		required. *standalone* defaults to False as this is the assumed value if
		there is no standalone declaration."""
		XMLTextDeclaration.__init__(self,version,encoding)
		self.standalone=standalone
		"""Whether an XML document is standalone."""


class XMLElement(XMLContextMixin):
	#XMLCONTENT=None
	
	def __init__(self,parent,name=None):
		XMLContextMixin.__init__(self,parent)
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
	
	def GetXMLName(self):
		return self.xmlname
	
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
		for a in dir(self.__class__):
			if a.startswith('XMLATTR_'):
				required=False
				setter=getattr(self.__class__,a)
				if type(setter) in StringTypes:
					# use simple attribute assignment
					name,encode=setter,lambda x:x
				elif type(setter) is TupleType:
					if len(setter)==3:
						name,decode,encode=setter
					elif len(setter)==4:
						name,decode,encode,required=setter
					else:
						raise XMLAttributeSetter("bad XMLATTR_ definition: %s attribute of %s"%(name,self.__class__.__name__))
				else:
					raise XMLAttributeSetter("setting %s attribute of %s"%(name,self.__class__.__name__))				
				value=getattr(self,name,None)
				if type(value) is ListType:
					value=string.join(map(encode,value),' ')
					if not value and not required:
						value=None
				elif type(value) is DictType:
					value=string.join(sorted(map(encode,value.keys())),' ')
					if not value and not required:
						value=None
				elif value is not None:
					value=encode(value)
				if value is not None:
					attrs[a[8:]]=value
		return attrs

	def SetAttribute(self,name,value):
		"""Sets the value of an attribute.
		
		The attribute name is assumed to be a string or unicode string.
		
		The default implementation checks for a custom setter which can be defined
		in one of three ways.
		
		(1) For simple assignement of the string value to an attribute of the
		instance just add an attribute to the class of the form
		XMLATTR_xmlname='member' where 'xmlname' is the attribute name used in
		the XML tag and 'member' is the attribute name to use in the instance.

		(2) More complex attributes can be handled by setting XMLATTR_xmlname to
		a tuple of ('member',decodeFunction,encodeFunction) where the
		decodeFunction is a simple function that take a string argument and
		returns the decoded value of the attribute, the encodeFunction performs
		the reverse transformation.
		
		In cases (1) and (2), once the member name has been determined the
		existing value of the member is used to determine how to set the value:
		
		List: split the value by whitespace and assign list of decoded values

		Dict: split the value by whitespace and create a mapping from decoded
		values to the original text used to represent it in the attribute.		

		Any other type: the member is set to the decoded value
		
		A values of None or a missing member is as treated as for 'any other type'.
		
		(3) Finally, if the *instance* has a method called Set_xmlname then that
		is called with the value.
		
		In the first two cases, GetAttributes will handle the generation of the
		attribute automatically, in the third case you must override the
		GetAttributes method to set the attributes appropriately during
		serialization back to XML.
		
		XML attribute names may contain many characters that are not legal in
		Python method names but, in practice, the only significant limitation is
		the colon.  This is replaced by '_' before searching for a custom setter.
		
		If no custom setter is defined then the default processing stores the
		attribute in a local dictionary, a copy of which can be obtained with
		the GetAttributes method.  Additionally, if the class has an ID
		attribute it is used as the name of the attribute that represents the
		element's ID.  ID handling is performed automatically at document level
		and the element's 'id' attribute is set accordingly."""
		setter=getattr(self,"XMLATTR_"+name,None)
		if setter is None:
			setter=getattr(self,"Set_"+name,None)
			if setter is None:
				if hasattr(self.__class__,'ID') and name==self.__class__.ID:
					self.SetID(value)
				else:
					self._attrs[name]=value
			else:
				setter(value)
		else:
			if type(setter) in StringTypes:
				# use simple attribute assignment
				name,decode=setter,lambda x:x
			elif type(setter) is TupleType:
				if len(setter)==3:
					name,decode,encode=setter
				else:
					# we ignore required when setting
					name,decode,encode,required=setter
			else:
				raise XMLAttributeSetter("setting %s attribute of %s"%(name,self.__class__.__name__))
			x=getattr(self,name,None)
			if type(x) is ListType:
				setattr(self,name,map(decode,value.split()))
			elif type(x) is DictType:
				value=value.split()
				setattr(self,name,dict(zip(map(decode,value),value)))
			else:
				setattr(self,name,decode(value))
	
	def IsValidName(self,value):
		return IsValidName(value)

	def IsEmpty(self):
		"""Returns True/False indicating whether this element *must* be empty.
		
		If the class defines the XMLCONTENT attribute then the model is taken
		from there and this method returns True only if XMLCONTENT is XMLEmpty.
		
		Otherwise, the method defaults to False"""
		if hasattr(self.__class__,'XMLCONTENT'):
			return self.__class__.XMLCONTENT==XMLEmpty
		else:
			return False
		
	def IsMixed(self):
		"""Indicates whether or not the element *may* contain mixed content.
		
		If the class defines the XMLCONTENT attribute then the model is taken
		from there and this method returns True only if XMLCONTENT is
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

	def GetCanonicalChildren(self):
		"""Returns a list of the element's children canonicalized for white space.
		
		We check the current setting of xml:space, returning the same list
		of children as GetChildren if 'preserve' is in force.  Otherwise we
		remove any leading space and collapse all others to a single space character."""
		children=self.GetChildren()
		if len(children)==0:
			return children
		e=self
		while isinstance(e,XMLElement):
			spc=e.GetSpace()
			if spc is not None:
				if spc=='preserve':
					return children
				else:
					break
			if hasattr(e.__class__,'SGMLCDATA'):
				return children
			e=e.parent
		if len(children)==1:
			child=children[0]
			if type(child) in StringTypes:
				children[0]=CollapseSpace(child)
				if len(children[0])>1 and children[0][-1]==' ':
					# strip the trailing space form the only child
					children[0]=children[0][:-1]				
		else:
			# Collapse strings to a single string entry and collapse spaces
			i=0
			while i<len(children):
				iChild=children[i]
				j=i
				while j<len(children):
					jChild=children[j]
					if type(jChild) in StringTypes:
						j=j+1
					else:
						break
				if j>i:
					# We need to collapse these children
					data=CollapseSpace(string.join(children[i:j],''),i==0)
					if i==0 and data==' ':
						# prune a leading space completely...
						del children[i:j]
					else:
						children[i:j]=[data]
				i=i+1
		if len(children)>1:
			if type(children[-1]) in StringTypes:
				if children[-1]==' ':
					# strip the whole last child
					del children[-1]
				elif children[-1][-1]==' ':
					# strip the trailing space form the last child
					children[-1]=children[-1][:-1]
		return children
		
	def _FindFactory(self,childClass):
		if hasattr(self,childClass.__name__):
			return childClass.__name__
		else:
			for parent in childClass.__bases__:
				fName=self._FindFactory(parent)
				if fName:
					return fName
			return None
				
	def ChildElement(self,childClass,name=None):
		"""Returns a new child of the given class attached to this element.
		
		A new child is created and attached to the element's model unless the
		model supports a single element of the given childClass and the element
		already exists, in which case the existing instance is returned.
		
		childClass is a class (or callable) used to create a new instance.
		
		name is the name given to the element (by the caller).  If no name is
		given then the default name for the child should be used.  When the
		child returned is an existing instance, name is ignored.
		
		The default implementation checks for a custom factory method and calls
		it if defined and does no further processing.  A custom factory method
		is a method of the form ClassName or an attribute that is being used to
		hold instances of this child.  The attribute must already exist and can
		be one of None (optional child, new child is created), a list (optional
		repeatable child, new child is created and appended) or an instance of
		childClass (required/existing child, no new child is created, existing
		instance returned).
		
		When no custom factory method is found the class hierarchy is also searched
		enabling generic members/methods to be used to hold similar objects.
		
		If no custom factory method is defined then the default processing
		simply creates an instance of child (if necessary) and attaches it to
		the local list of children."""
		if self.IsEmpty():
			self.ValidationError("Unexpected child element",name)
		factoryName=self._FindFactory(childClass)
		if factoryName:
			factory=getattr(self,factoryName)
			if type(factory) is MethodType:
				if factoryName!=childClass.__name__:
					child=factory(childClass)
				else:
					child=factory()
				if name:
					child.SetXMLName(name)
				return child
			elif type(factory) is NoneType:
				child=childClass(self)
				setattr(self,factoryName,child)
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
	
	def DeleteChild(self,child):
		"""Deletes the given child from this element's children.
		
		We follow the same factory conventions as for child creation except
		that an attribute pointing to a single child (or this class) will be
		replaced with None.  If a custom factory method is found then the
		corresponding Delete_ClassName method must also be defined.
		"""
		if self.IsEmpty():
			raise XMLUnknownChild(child.xmlname)
		factoryName=self._FindFactory(child.__class__)
		if factoryName:
			factory=getattr(self,factoryName)
			if type(factory) is MethodType:
				deleteFactory=getattr(self,"Delete_"+factoryName)
				deleteFactory(child)
			elif type(factory) is NoneType:
				raise XMLUnknownChild(child.xmlname)
			elif type(factory) is ListType:
				match=False
				for i in xrange(len(factory)):
					if factory[i] is child:
						child.DetachFromDocument()
						child.parent=None
						del factory[i]
						match=True
						break
				if not match:
					raise XMLUnknownChild(child.xmlname)
			elif factory is child:
				child.DetachFromDocument()
				child.parent=None
				factory=None
			else:
				raise TypeError
		else:
			match=False
			for i in xrange(len(self._children)):
				if self._children[i] is child:
					child.DetachFromDocument()
					child.parent=None
					del self._children[i]
					match=True
					break
			if not match:
				raise XMLUnknownChild(child.xmlname)
		
	def FindChildren(self,childClass,childList,max=None):
		"""Finds up to max children of class childClass from the element and
		its children.

		All matching children are added to childList.  If specifing a max number
		of matches then the incoming list must originally be empty to prevent
		early termination.

		Note that if max is None, the default, then all children of the given
		class are returned with the proviso that nested matches are not
		included.  In other words, if the model of childClass allows further
		elements of type childClass as children (directly or indirectly) then
		only the top-level match is returned.
		
		Effectively this method provides a breadth-first list of children.  For
		example, to get all <div> elements in an HTML <body> you would have to
		recurse over the resulting list calling FindChildren again until the
		list of matching children stops growing.		
		"""
		children=self.GetChildren()
		if max is not None and len(childList)>=max:
			return
		for child in children:
			if isinstance(child,childClass):
				childList.append(child)
			elif isinstance(child,XMLElement):
				child.FindChildren(childClass,childList,max)
			if max is not None and len(childList)>=max:
				break

	def FindParent(self,parentClass):
		"""Finds the first parent of class parentClass of this element.
		
		If this element has no parent of the given class then None is returned."""
		parent=self.parent
		while parent and not isinstance(parent,parentClass):
			if isinstance(parent,XMLElement):
				parent=parent.parent
			else:
				parent=None
		return parent
					
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
		
		This method should raise a ValidationError if the element cannot take
		data children, however, if *suggestClass* is True then the method may
		optionally return a class object (derived from :py:class:`XMLElement`)
		suggesting an element to create to contain the data.  This behaviour is
		intended to be used in conjunction with the
		:py:attr:`XMLParser.sgmlOmittag` parsing option.  For example,
		attempting to add data to an HTML Body element would result in the
		suggestion to create a P element."""
		assert(type(data) in StringTypes)
		if self.IsMixed():
			if self._children and type(self._children[-1]) in StringTypes:
				# To ease the comparison function we collapse string children
				self._children[-1]=self._children[-1]+data
			else:
				self._children.append(data)
		else:
			ws=True
			for c in data:
				if not IsS(c):
					ws=False;
					break
			if not ws:
				self.ValidationError("Unexpected data",data)
		
	def ContentChanged(self):
		"""Notifies an element that its content has changed.
		
		The default implementation tidies up the list of children to make
		future comparisons simpler and faster."""
		newChildren=[]
		dataChildren=[]
		for child in self._children:
			if type(child) in StringTypes:
				dataChildren.append(child)
			elif len(dataChildren)==1:
				newChildren.append(dataChildren[0])
				newChildren.append(child)
				dataChildren=[]
			elif len(dataChildren)>1:
				newChildren.append(string.join(dataChildren,''))
				newChildren.append(child)
				dataChildren=[]
			else:
				newChildren.append(child)
		if len(dataChildren)==1:
			newChildren.append(dataChildren[0])
		elif len(dataChildren)>1:	
			newChildren.append(string.join(dataChildren,''))
		self._children=newChildren				

	def GetValue(self,ignoreElements=False):
		"""Returns a single unicode string representing the element's data.
		
		If the element contains child elements and ignoreElements is False
		then XMLMixedContentError is raised.
		
		If the element is empty an empty string is returned."""		
		children=self.GetChildren()
		if not ignoreElements:
			for child in children:
				if not type(child) in StringTypes:
					raise XMLMixedContentError(str(self))
		if children:
			return string.join(map(unicode,children),'')
		else:
			return ''

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
			raise XMLValidityError(msg)
			

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
		selfChildren=self.GetCanonicalChildren()
		elementChildren=element.GetCanonicalChildren()
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
		"""Returns the XML element as a string.
		
		We force use of character references for all non-ascii characters in data
		but this isn't enough to guarantee success.  We will still get an encoding
		error if non-ascii characters have been used in markup names as such files
		cannot be encoded in US-ASCII."""
		s=StringIO()
		self.WriteXML(s,EscapeCharData7,root=True)
		return str(s.getvalue())
	
	def __unicode__(self):
		"""Returns the XML element as a unicode string"""
		s=StringIO()
		self.WriteXML(s,EscapeCharData,root=True)
		return unicode(s.getvalue())
		
	def Copy(self,parent=None):
		"""Creates a new instance of this element which is a deep copy of this one."""
		if parent:
			e=parent.ChildElement(self.__class__,self.GetXMLName())
		else:
			e=self.__class__(None)
		attrs=self.GetAttributes()
		for aname in attrs.keys():
			e.SetAttribute(aname,attrs[aname])
		children=self.GetChildren()
		for child in children:
			if type(child) in types.StringTypes:
				e.AddData(child)
			else:
				child.Copy(e)
		return e
		
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
		r"""Returns a fully specified URL, resolving uri in the current context.
		
		The uri is resolved relative to the xml:base values of the element's
		ancestors and ultimately relative to the document's baseURI."""
		baseURI=self.ResolveBase()
		if baseURI:
			return URIFactory.Resolve(baseURI,uri)
		elif isinstance(uri,URI):
			return uri
		else:
			return URIFactory.URI(uri)
	
	def RelativeURI(self,href):
		"""Returns href expressed relative to the element's base.

		If href is a relative URI then it is converted to a fully specified URL
		by interpreting it as being the URI of a file expressed relative to the
		current working directory.

		If the element does not have a fully-specified base URL then href is
		returned as a fully-specified URL itself."""
		result=[]
		if not isinstance(href,URI):
			href=URIFactory.URI(href)
		if not href.IsAbsolute():
			href=href.Resolve(URIFactory.URLFromPathname(os.getcwd()))
		base=self.ResolveBase()
		if base is not None:
			return URIFactory.Relative(href,base)
		else:
			return href

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

	def PrettyPrint(self):
		"""Indicates if this element's content should be pretty-printed.
		
		This method is used when formatting XML files to text streams.  The
		behaviour can be affected by the xml:space attribute or by derived
		classes that can override the default behaviour.
		
		If this element has xml:space set to 'preserve' then we return False.
		If self.parent.PrettyPrint() returns False then we return False.
		
		Otherwise we return False if we know the element is (or should be) mixed
		content, True otherwise.
		
		Note: an element on undetermined content model that contains only elements
		and white space *is* pretty printed."""
		spc=self.GetSpace()
		if spc is not None and spc=='preserve':
			return False
		if hasattr(self.__class__,'SGMLCDATA'):
			return False
		if isinstance(self.parent,XMLElement):
			spc=self.parent.PrettyPrint()
			if spc is False:
				return False
		if hasattr(self.__class__,'XMLCONTENT'):
			# if we have a defined content model then we return False for
			# mixed content.
			return self.__class__.XMLCONTENT!=XMLMixedContent
		else:
			children=self.GetChildren()
			for child in self.GetChildren():
				if type(child) in StringTypes:
					for c in child:
						if not IsS(c):
							return False
		return True
		
	def WriteXMLAttributes(self,attributes,escapeFunction=EscapeCharData,root=False):
		"""Adds strings representing the element's attributes
		
		attributes is a list of unicode strings.  Attributes should be appended
		as strings of the form 'name="value"' with values escaped appropriately
		for XML output."""
		attrs=self.GetAttributes()
		keys=attrs.keys()
		self.SortNames(keys)
		for a in keys:
			attributes.append(u'%s=%s'%(a,escapeFunction(attrs[a],True)))
				
	def WriteXML(self,writer,escapeFunction=EscapeCharData,indent='',tab='\t',root=False):
		if tab:
			ws='\n'+indent
			indent=indent+tab
		else:
			ws=''
		if not self.PrettyPrint():
			# inline all children
			indent=''
			tab=''
		attributes=[]
		self.WriteXMLAttributes(attributes,escapeFunction,root=root)
		if attributes:
			attributes[0:0]=['']
			attributes=string.join(attributes,' ')
		else:
			attributes=''
		children=self.GetCanonicalChildren()
		if children:
			if type(children[0]) in StringTypes and len(children[0])>0 and IsS(children[0][0]):
				# First character is WS, so assume pre-formatted
				indent=tab=''
			writer.write(u'%s<%s%s>'%(ws,self.xmlname,attributes))
			if hasattr(self.__class__,'SGMLCDATA'):
				# When expressed in SGML this element would have type CDATA so put it in a CDSect
				writer.write(EscapeCDSect(self.GetValue()))
			else:
				for child in children:
					if type(child) in types.StringTypes:
						# We force encoding of carriage return as these are subject to removal
						writer.write(escapeFunction(child))
						# if we have character data content skip closing ws
						ws=''
					else:
						child.WriteXML(writer,escapeFunction,indent,tab)
			if not tab:
				# if we weren't tabbing children we need to skip closing white space
				ws=''
			writer.write(u'%s</%s>'%(ws,self.xmlname))
		else:
			writer.write(u'%s<%s%s/>'%(ws,self.xmlname,attributes))


class XMLElementType:

	Empty=0				#: Content type constant for EMPTY
	Any=1				#: Content type constant for ANY
	Mixed=2				#: Content type constant for mixed content
	ElementContent=3	#: Content type constant for element content
	SGMLCDATA=4			#: Additional content type constant for SGML CDATA
	
	def __init__(self):
		"""An object for representing element type definitions."""
		self.entity=None	#: The entity in which this element was declared
		self.name=None		#: The name of this element
		self.contentType=XMLElementType.Empty
		"""The content type of this element, one of the constants defined above."""
		self.contentModel=None
		"""A :py:class:`XMLContentParticle` instance which contains the element's
		content model or None in the case of EMPTY or ANY declarations."""

# Constants for backwards compatibility
XMLEmpty=XMLElementType.Empty
XMLMixedContent=XMLElementType.Mixed
XMLElementContent=XMLElementType.ElementContent
SGMLCDATA=XMLElementType.SGMLCDATA
		
	
class XMLContentParticle:
	
	ExactlyOnce=0	#: Occurrence constant for particles that must appear exactly once
	ZeroOrOne=1		#: Occurrence constant for '?'
	ZeroOrMore=2	#: Occurrence constant for '*'
	OneOrMore=3		#: Occurrence constant for '+'
	
	def __init__(self):
		"""An object for representing content particles."""
		self.occurrence=XMLContentParticle.ExactlyOnce
		"""One of the occurrence constants defined above."""
			

class XMLNameParticle(XMLContentParticle):
	def __init__(self):
		"""An object representing a content particle for a named element in the grammar"""
		XMLContentParticle.__init__(self)
		self.name=None		#: the name of the element type that matches this particle
	

class XMLChoiceList(XMLContentParticle):
	def __init__(self):
		"""An object representing a choice list of content particles in the grammar"""
		XMLContentParticle.__init__(self)
		self.children=[]
	

class XMLSequenceList(XMLContentParticle):
	def __init__(self):
		"""An object representing a sequence list of content particles in the grammar"""
		XMLContentParticle.__init__(self)
		self.children=[]
	
	
class XMLAttributeDefinition:

	CData=0			#: Type constant representing CDATA
	ID=1			#: Type constant representing ID
	IDRef=2			#: Type constant representing IDREF
	IDRefs=3		#: Type constant representing IDREFS
	Entity=4		#: Type constant representing ENTITY
	Entities=5		#: Type constant representing ENTITIES
	NmToken=6		#: Type constant representing NMTOKEN
	NmTokens=7		#: Type constant representing NMTOKENS
	Notation=8		#: Type constant representing NOTATION
	Enumeration=9	#: Type constant representing an enumeration
	
	Implied=0		#: Presence constant representing #IMPLIED
	Required=1		#: Presence constant representing #REQUIRED
	Fixed=2			#: Presence constant representing #FIXED
	Default=3		#: Presence constant representing a declared default value
	
	def __init__(self):
		"""An object for representing attribute declarations."""
		self.entity=None								#: the entity in which this attribute was declared
		self.type=XMLAttributeDefinition.CData			#: One of the above type constants
		self.values=None								#: An optional list of values
		self.presence=XMLAttributeDefinition.Implied	#: One of the above presence constants
		self.defaultValue=None							#: An optional default value


class XMLEntity:
	def __init__(self,src=None,encoding='utf-8',reqManager=None):
		"""An object representing an entity.
		
		This object serves two purposes, it acts as both the object used to
		store information about declared entities and also as a parser for feeding
		unicode characters to the main :py:class:`XMLParser`.
		
		Optional *src*, *encoding* and *reqManager* parameters can be provided,
		if src is not None then these parameters are used to open the entity
		reader immediately using one of the Open methods described below.
		
		*src* may be a unicode string, a byte string, an instance of
		:py:class:`pyslet.rfc2396.URI` or any object that supports file-like
		behaviour.  If using a file, the file must support seek behaviour."""
		self.location=None		#: the location of this entity (used as the base URI to resolve relative links)
		self.mimetype=None		#: the mime type of the entity, if known, or None
		self.encoding=None		#: the encoding of the entity (text entities)
		self.dataSource=None	#: a file like object from which the entity's data is read
		self.charSource=None
		"""A unicode data reader used to read characters from the entity.  If
		None, then the entity is closed."""
		self.theChar=None		#: the character at the current position in the entity
		self.lineNum=None		#: the current line number within the entity (first line is line 1)
		self.linePos=None		#: the current character position within the entity (first char is 1)
		self.buffText=''		#: used by :py:meth:`XMLParser.PushEntity`
		self.basePos=None
		self.charSeek=None
		self.chunk=None
		self.chars=''
		self.charPos=None
		self.ignoreLF=None
		self.flags={}
		if type(src) is UnicodeType:
			self.OpenUnicode(src)
		elif isinstance(src,URI):
			self.OpenURI(src,encoding,reqManager)
		elif type(src) is StringType:
			self.OpenString(src,encoding)
		elif not src is None:
			self.OpenFile(src,encoding)
	
	ChunkSize=4096
	"""Characters are read from the dataSource in chunks.  The default chunk size is 4KB.
	
	In fact, in some circumstances the entity reader starts more cautiously.  If
	the entity reader expects to read an XML or Text declaration, which may have
	an encoding declaration then it reads one character at a time until the
	declaration is complete.  This allows the reader to change to the encoding
	in the declaration without causing errors caused by reading too many
	characters using the wrong codec.  See :py:meth:`ChangeEncoding` and
	:py:meth:`KeepEncoding` for more information."""
	
	def GetName(self):
		"""Abstract method to return a name to represent this entity in logs and error messages."""
		return repr(self)
			
	def IsExternal(self):
		"""Returns True if this is an external entity.
		
		The default implementation returns True if *location* is not None, False otherwise."""
		return self.location is not None

	def Open(self):
		"""Opens the entity for reading.
		
		The default implementation uses :py:meth:`OpenURI` to open the entity
		from :py:attr:`location` if available, otherwise it raises
		UnimplementedError."""
		if self.location:
			self.OpenURI(self.location)
		else:
			raise UnimplementedError
	
	def OpenUnicode(self,src):
		"""Opens the entity from a unicode string."""
		self.encoding=None
		self.dataSource=None
		self.chunk=XMLEntity.ChunkSize
		self.charSource=StringIO(src)
		self.basePos=self.charSource.tell()
		self.Reset()

	def OpenString(self,src,encoding='utf-8'):
		"""Opens the entity from a byte string.
		
		The optional *encoding* is used to convert the string to unicode and
		defaults to UTF-8.
		
		The advantage of using this method instead of converting the string to
		unicode and calling :py:meth:`OpenUnicode` is that this method creates
		unicode reader object to parse the string instead of making a copy of it
		in memory."""
		self.encoding=encoding
		self.dataSource=StringIO(src)
		self.chunk=1
		self.charSource=codecs.getreader(self.encoding)(self.dataSource)
		self.basePos=self.charSource.tell()
		self.Reset()
	
	def OpenFile(self,src,encoding='utf-8'):
		"""Opens the entity from an existing (open) file.
		
		The optional *encoding* provides a hint as to the intended encoding of
		the data and defaults to UTF-8."""
		self.encoding=encoding
		self.dataSource=src
		self.chunk=1
		self.charSource=codecs.getreader(self.encoding)(self.dataSource)
		self.basePos=self.charSource.tell()
		self.Reset()
				
	def OpenURI(self,src,encoding='utf-8',reqManager=None):
		"""Opens the entity from a URI passed in *src*.
		
		The file, http and https schemes are the only ones supported.
		
		The optional *encoding* provides a hint as to the intended encoding of
		the data and defaults to UTF-8.  For http(s) resources this parameter is
		only used if the charset cannot be read successfully from the HTTP
		headers.
		
		The optional *reqManager* allows you to pass an existing instance of
		:py:class:`pyslet.rfc2616.HTTPRequestManager` for handling URI with
		http or https schemes."""
		self.encoding=encoding
		self.location=src
		if isinstance(src,FileURL):
			self.OpenFile(open(src.GetPathname(),'rb'),self.encoding)
		elif src.scheme.lower() in ['http','https']:
			if reqManager is None:
				reqManager=http.HTTPRequestManager()
			req=http.HTTPRequest(str(src))
			reqManager.ProcessRequest(req)
			if req.status==200:
				mtype=req.response.GetContentType()
				if mtype is None:
					# We'll attempt to do this with xml and utf8
					charset='utf8'
					raise UnimplementedError
				else:
					self.mimetype=mtype.type.lower()+'/'+mtype.subtype.lower()
					respEncoding=mtype.parameters.get('charset',None)
					if respEncoding is None and mtype.type.lower()=='text':
						# Text types default to iso-8859-1
						respEncoding=('text-default',"iso-8859-1")
					if respEncoding is not None:
						self.encoding=respEncoding[1].lower()
				#print "...reading %s stream with charset=%s"%(self.mimetype,self.encoding)
				self.OpenFile(StringIO(req.resBody),self.encoding)
			else:
				raise XMLUnexpectedHTTPResponse(str(req.status))
		else:
			raise XMLUnsupportedScheme			
		
	def Reset(self):
		"""Resets an open entity, causing it to return to the first character in the entity."""
		if self.charSource is None:
			self.theChar=None
			self.basePos=None
		else:
			self.charSource.seek(self.basePos)
			self.theChar=''
		self.lineNum=1
		self.linePos=0
		self.chars=''
		self.charSeek=self.basePos
		self.charPos=-1
		self.ignoreLF=False
		self.NextChar()
		# python handles the utf-16 BOM automatically but we have to skip it for utf-8
		if self.theChar==u'\ufeff' and self.encoding is not None and self.encoding.lower()=='utf-8':
			self.NextChar()
	
	def GetPositionStr(self):
		"""Returns a short string describing the current line number and character position.
		
		For example, if the current character is pointing to character 6 of line
		4 then it will return the string 'Line 4.6'"""
		return "Line %i.%i"%(self.lineNum,self.linePos)
		
	def NextChar(self):
		"""Advances to the next character in an open entity.
		
		This method takes care of the End-of-Line handling rules for XML which force
		us to remove any CR characters and replace them with LF if they appear on their
		own or to silenty drop them if they appear as part of a CR-LF combination."""
		if self.theChar is None:
			return
		self.charPos=self.charPos+1
		self.linePos=self.linePos+1
		if self.charPos>=len(self.chars):
			self.charSeek=self.charSource.tell()
			self.chars=self.charSource.read(self.chunk)
			self.charPos=0
		if self.charPos>=len(self.chars):
			self.theChar=None
		else:
			self.theChar=self.chars[self.charPos]
			if self.theChar=='\x0D':
				# change to a line feed and ignore the next line feed
				self.theChar='\x0A'
				self.ignoreLF=True
				self.NextLine()
			elif self.theChar=='\x0A':
				if self.ignoreLF:
					self.ignoreLF=False
					self.NextChar()
				else:
					self.NextLine()
			else:
				self.ignoreLF=False
				
	def ChangeEncoding(self,encoding):
		"""Changes the encoding used to interpret the entity's stream.
		
		In many cases we can only guess at the encoding used in a file or other
		byte stream.  However, XML has a mechanism for declaring the encoding as
		part of the XML or Text declaration.  This declaration can typically be
		parsed even if the encoding has been guessed incorrectly initially. This
		method allows the XML parser to notify the entity that a new encoding
		has been declared and that future characters should be interpreted with
		this new encoding.
		
		You can only change the encoding once.  This method calls
		:py:meth:`KeepEncoding` once the encoding has been changed."""
		if self.dataSource:
			self.encoding=encoding
			# Need to rewind and re-read the current buffer
			self.charSource.seek(self.charSeek)
			self.charSource=codecs.getreader(self.encoding)(self.dataSource)
			self.chars=self.charSource.read(len(self.chars))
			# We assume that charPos will still point to the correct next character
			self.theChar=self.chars[self.charPos]
		self.KeepEncoding()
	
	def KeepEncoding(self):
		"""Tells the entity parser that the encoding will not be changed again.
		
		This entity parser starts in a cautious mode, parsing the entity one
		character a time to avoid errors caused by buffering with the wrong
		encoding.  This method should be called once the encoding is determined
		so that the entity parser can use its internal character buffer."""
		self.chunk=XMLEntity.ChunkSize

	def NextLine(self):
		"""Called when the entity reader detects a new line.
		
		This method increases the internal line count and resets the
		character position to the beginning of the line.  You will not
		normally need to call this directly as line handling is done
		automatically by :py:meth:`NextChar`."""
		self.lineNum=self.lineNum+1
		self.linePos=0
		
	def Close(self):
		"""Closes the entity."""
		if self.charSource is not None:
			self.charSource.close()
			self.charSource=None
		if self.dataSource is not None:
			self.dataSource.close()
			self.dataSource=None
		self.theChar=None
		self.lineNum=None
		self.linePos=None


class XMLDeclaredEntity(XMLEntity):
	def __init__(self,name=None,definition=None):
		"""Abstract class for representing declared entities."""
		XMLEntity.__init__(self)
		self.entity=None	#: the entity in which this entity was declared
		self.name=name		#: the name of the declared entity
		self.definition=definition
		"""The definition of the entity is either a string or an instance of
		XMLExternalID, depending on whether the entity is an internal or
		external entity respectively."""
	
	def GetName(self):
		"""Returns a representation of the entitiy's name suitable for logging/error reporting."""
		return self.name

	def IsExternal(self):
		"""Returns True if this is an external entity."""
		return isinstance(self.definition,XMLExternalID)

	def Open(self):
		"""Opens the entity for reading.
		
		External entities must be parsed for text declarations before the
		replacement text is encountered.  This requires a small amount of
		look-ahead which may result in some characters needing to be re-parsed. 
		We pass this to future parsers using :py:attr:`buffText`."""
		if type(self.definition) is StringType:
			self.OpenString(self.definition)
		elif type(self.definition) is UnicodeType:
			self.OpenUnicode(self.definition)
		elif isinstance(self.definition,XMLExternalID):
			XMLEntity.Open(self)	# open from location or raise UnimplementedError
			# Now to handle the text declaration
			p=XMLParser(self)
			if p.ParseLiteral('<?xml'):
				p.ParseTextDecl(True)
			# at this point we may have some left over text in p's buffer
			# we can't push it back down the pipe so need to handle here
			self.buffText=p.GetBuff()
		else:
			raise XMLError("Bad Entity Definition") 

		
class XMLGeneralEntity(XMLDeclaredEntity):
	def	__init__(self,name=None,definition=None,notation=None):
		"""An object for representing general entities.
		
		A general entity can be constructed with an optional *name*,
		*definition* and *notation*, used to initialise the following fields."""
		XMLDeclaredEntity.__init__(self,name,definition)
		self.notation=notation		#: the notation name for external unparsed entities

	def GetName(self):
		"""Returns the name of the entity formatted as a general entity reference."""
		return "&%s;"%self.name


class XMLParameterEntity(XMLDeclaredEntity):
	def	__init__(self,name=None,definition=None):
		"""An object for representing parameter entities.
		
		A parameter entity can be constructed with an optional *name* and
		*definition*, used to initialise the following two fields."""
		XMLDeclaredEntity.__init__(self,name,definition)
		self.peEnd=None
	
	def NextChar(self):
		"""Overrridden to provide trailing space during special parameter entity handling."""
		XMLEntity.NextChar(self)
		if self.theChar is None and self.peEnd:
			self.theChar=self.peEnd
			self.peEnd=None

	def OpenAsPE(self):
		"""Opens the parameter entity for reading in the context of a DTD.
		
		This special method implements the rule that the replacement text of a parameter
		entity, when included as a PE, must be enlarged by the attachment of a leading
		and trailing space."""
		self.Open()
		self.buffText=u' '+self.buffText
		self.peEnd=u" "		

	def GetName(self):
		"""Returns the name of the entity formatted as a parameter entity reference."""
		return "%%%s;"%self.name


class XMLExternalID:
	"""Used to represent external references to entities."""
	
	def __init__(self,public=None,system=None):
		"""Returns an instance of XMLExternalID.  One of *public* and *system* should be provided."""
		self.public=public	#: the public identifier, may be None
		self.system=system	#: the system identifier, may be None.

	def GetLocation(self,base=None):
		"""Returns the absolute URI where the external entity can be found.
		
		Returns a :py:class:`pyslet.rfc2396.URI` resolved against :py:attr:`base` if
		applicable.  If there is no system identifier then None is returned."""
		if self.system:
			if base:
				location=URIFactory.Resolve(base,URIFactory.URI(self.system))
			else:
				location=URIFactory.URI(self.system)
			if not location.IsAbsolute():
				cwd=URIFactory.URLFromPathname(os.path.join(os.getcwd(),os.curdir))
				location=location.Resolve(cwd)
			if location.IsAbsolute():
				return location
		return None

			
class XMLNotation:
	"""Represents an XML Notation"""

	def __init__(self,name,externalID):
		"""Returns an XMLNotation instance.
		
		*externalID* is a :py:class:`XMLExternalID` instance in which one of
		*public* or *system* must be provided."""
		self.name=name					#: the notation name 
		self.externalID=externalID		#: the external ID of the notation (an XMLExternalID instance)


def IsLetter(c):
	"""Tests if the character *c* matches production [84] Letter."""
	return IsBaseChar(c) or IsIdeographic(c)

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

def IsBaseChar(c):
	"""Tests if the character *c* matches production [85] BaseChar."""
	return BaseCharClass.Test(c)

def IsIdeographic(c):
	"""Tests if the character *c* matches production [86] Ideographic."""
	return c and ((ord(c)>=0x4E00 and ord(c)<=0x9FA5) or ord(c)==0x3007 or
		(ord(c)>=0x3021 and ord(c)<=0x3029))

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

def IsCombiningChar(c):
	"""Tests if the character *c* matches production [87] CombiningChar."""
	return CombiningCharClass.Test(c)

DigitClass=CharClass((u'0',u'9'), (u'\u0660',u'\u0669'),
	(u'\u06f0',u'\u06f9'), (u'\u0966',u'\u096f'), (u'\u09e6',u'\u09ef'),
	(u'\u0a66',u'\u0a6f'), (u'\u0ae6',u'\u0aef'), (u'\u0b66',u'\u0b6f'),
	(u'\u0be7',u'\u0bef'), (u'\u0c66',u'\u0c6f'), (u'\u0ce6',u'\u0cef'),
	(u'\u0d66',u'\u0d6f'), (u'\u0e50',u'\u0e59'), (u'\u0ed0',u'\u0ed9'),
	(u'\u0f20',u'\u0f29'))

def IsDigit(c):
	"""Tests if the character *c* matches production [88] Digit."""
	return DigitClass.Test(c)

ExtenderClass=CharClass(u'\xb7', (u'\u02d0',u'\u02d1'), u'\u0387', u'\u0640',
u'\u0e46', u'\u0ec6', u'\u3005', (u'\u3031',u'\u3035'), (u'\u309d',u'\u309e'),
(u'\u30fc',u'\u30fe'))

def IsExtender(c):
	"""Tests if the character *c* matches production [89] Extender."""
	return ExtenderClass.Test(c)


EncNameStartCharClass=CharClass((u'A',u'Z'), (u'a',u'z'))

EncNameCharClass=CharClass(u'-', u'.', (u'0',u'9'), (u'A',u'Z'), u'_', 
	(u'a',u'z'))

	
class XMLParser:
	
	DocumentClassTable={}
	"""A dictionary mapping doctype parameters onto class objects.
	
	For more information about how this is used see :py:meth:`GetDocumentClass` and
	:py:func:`RegisterDocumentClass`."""
	
	RefModeNone=0				#: Default constant used for setting :py:attr:`refMode` 
	RefModeInContent=1			#: Treat references as per "in Content" rules
	RefModeInAttributeValue=2	#: Treat references as per "in Attribute Value" rules
	RefModeAsAttributeValue=3	#: Treat references as per "as Attribute Value" rules
	RefModeInEntityValue=4		#: Treat references as per "in EntityValue" rules
	RefModeInDTD=5				#: Treat references as per "in DTD" rules
	
	PredefinedEntities={
		'lt':'<',
		'gt':'>',
		'apos':"'",
		'quot':'"',
		'amp':'&'}
	"""A mapping from the names of the predefined entities (lt, gt, amp, apos, quot) to their
	replacement characters."""

	def __init__(self,entity):
		"""Returns an XMLParser object constructed from the :py:class:`XMLEntity` to parse.
			
		XMLParser objects are used to parse entities for the constructs defined
		by the numbered productions in the XML specification.

		XMLParser has a number of optional attributes, all of which default to
		False. If any option is set to True then the resulting parser will not
		behave as a conforming XML processor."""
		self.checkValidity=False
		"""checks XML validity constraints
		
		If *checkValidity* is True, and all other options are left at their
		default (False) setting then the parser will behave as a validating XML
		parser."""
		self.valid=None
		"""Flag indicating if the document is valid, only set if :py:attr:`checkValidity` is True."""
		self.validityErrors=[]
		"""A list of validity errors discovered during parsing, only populated if :py:attr:`checkValidity` is True."""
		self.raiseValidityErrors=False		#: treats validity errors as fatal errors
		self.dontCheckWellFormedness=False	#: provides a loose parser for XML-like documents
		self.sgmlNamecaseGeneral=False		#: option that simulates SGML's NAMECASE GENERAL YES
		self.sgmlNamecaseEntity=False		#: option that simulates SGML's NAMECASE ENTITY YES
		self.sgmlOmittag=False				#: option that simulates SGML's OMITTAG YES
		self.sgmlShorttag=False				#: option that simulates SGML's SHORTTAG YES
		self.sgmlContent=False
		"""This option simulates some aspects of SGML content handling based on class
		attributes of the element being parsed.
		
		-	Element classes with XMLCONTENT=:py:data:`XMLEmpty` are treated
			as elements declared EMPTY, these elements are treated as if they
			were introduced with an empty element tag even if they weren't, as per SGML's
			rules.  Note that this SGML feature "has nothing to do with markup
			minimization" (i.e., :py:attr:`sgmlOmittag`.)
		"""
		self.refMode=XMLParser.RefModeNone
		"""The current parser mode for interpreting references.

		XML documents can contain five different types of reference: parameter
		entity, internal general entity, external parsed entity, (external)
		unparsed entity and character entity.

		The rules for interpreting these references vary depending on the
		current mode of the parser, for example, in content a reference to an
		internal entity is replaced, but in the definition of an entity value it
		is not.  This means that the behaviour of the :py:meth:`ParseReference`
		method will differ depending on the mode.

		The parser takes care of setting the mode automatically but if you wish
		to use some of the parsing methods in isolation to parse fragments of
		XML documents, then you will need to set the *refMode* directly using
		one of the RefMode* family of constants defined above."""
		self.entity=entity					#: The current entity being parsed
		self.entityStack=[]
		if self.entity:
			self.theChar=self.entity.theChar	#: the current character; None indicates end of stream
		else:
			self.theChar=None
		self.buff=[]
		self.stagBuffer=None
		self.declaration=None
		"""The declaration parsed or None.""" 
		self.dtd=None
		"""The documnet type declaration of the document being parsed.
		
		This member is initialised to None as well-formed XML documents are not
		required to have an associated dtd."""
		self.doc=None
		"""The document being parsed."""
		self.docEntity=entity
		"""The document entity."""
		self.element=None
		"""The current element being parsed."""
		self.elementType=None
		"""The element type of the current element."""
		self.dataCount=0
		self.noPERefs=False
		
	def GetContext(self):
		if self.element is None:
			return self.doc
		else:
			return self.element

	def NextChar(self):
		"""Moves to the next character in the stream.

		The current character can always be read from :py:attr:`theChar`.  If
		there are no characters left in the current entity then entities are
		popped from an internal entity stack automatically."""
		if self.buff:
			self.buff=self.buff[1:]
		if self.buff:
			self.theChar=self.buff[0]
		else:	
			self.entity.NextChar()
			self.theChar=self.entity.theChar
			while self.theChar is None and self.entityStack:
				self.entity.Close()
				self.entity=self.entityStack.pop()
				self.theChar=self.entity.theChar

	def BuffText(self,unusedChars):
		if unusedChars:
			if self.buff:
				self.buff=list(unusedChars)+self.buff
			else:
				self.buff=list(unusedChars)
				if self.entity.theChar is not None:
					self.buff.append(self.entity.theChar)
			self.theChar=self.buff[0]
	
	def GetBuff(self):
		if len(self.buff)>1:
			return string.join(self.buff[1:],'')
		else:
			return ''

	def PushEntity(self,entity):
		"""Starts parsing *entity*

		:py:attr:`theChar` is set to the current character in the entity's
		stream.  The current entity is pushed onto an internal stack and will be
		resumed when this entity has been parsed completely.
		
		Note that in the degenerate case where the entity being pushed is empty
		(or is already positioned at the end of the file) then PushEntity does
		nothing."""
		if entity.theChar is not None:
			self.entityStack.append(self.entity)
			self.entity=entity
			self.entity.flags={}
			self.theChar=self.entity.theChar			
		if entity.buffText:
			self.BuffText(entity.buffText)
			
	def GetExternalEntity(self):
		"""Returns the external entity currently being parsed.
		
		If no external entity is being parsed then None is returned."""
		if self.entity.IsExternal():
			return self.entity
		else:
			i=len(self.entityStack)
			while i:
				i=i-1
				e=self.entityStack[i]
				if e.IsExternal():
					return e
		return None
				
	def WellFormednessError(self,msg="well-formedness error",errorClass=XMLWellFormedError):
		"""Raises an XMLWellFormedError error.

		Called by the parsing methods whenever a well-formedness constraint is
		violated. The method takes an optional message string, *msg* and an
		optional error class which must be a class object derived from
		py:class:`XMLWellFormednessError`.

		The method raises an instance of *errorClass* and does not return.  This
		method can be overridden by derived parsers to implement more
		sophisticated error logging."""
		raise errorClass("%s: %s"%(self.entity.GetPositionStr(),msg))

	def ValidityError(self,msg="validity error",error=XMLValidityError):
		"""Called when the parser encounters a validity error.
		
		The method takes an optional message string, *msg* and an optional error
		class or instance which must be a (class) object derived from
		py:class:`XMLValidityError`.

		The behaviour varies depending on the setting of the
		:py:attr:`checkValidity` and :py:attr:`raiseValidityErrors` options. The
		default (both False) causes validity errors to be ignored.  When
		checking validity an error message is logged to
		:py:attr:`validityErrors` and :py:attr:`valid` is set to False. 
		Furthermore, if :py:attr:`raiseValidityErrors` is True *error* is raised
		(or a new instance of *error* is raised) and parsing terminates.

		This method can be overridden by derived parsers to implement more
		sophisticated error logging."""
		if self.checkValidity:
			self.valid=False
			if isinstance(error,XMLValidityError):
				self.validityErrors.append("%s: %s (%s)"%(self.entity.GetPositionStr(),msg,str(error)))
				if self.raiseValidityErrors:
					raise error
			elif issubclass(error,XMLValidityError):
				msg="%s: %s"%(self.entity.GetPositionStr(),msg)
				self.validityErrors.append(msg)
				if self.raiseValidityErrors:
					raise error(msg)
			else:
				raise TypeError("ValidityError expected class or instance of XMLValidityError (found %s)"%repr(error))

	def ParseLiteral(self,match):
		"""Parses a literal string, passed in *match*.
		
		Returns True if *match* is successfully parsed and False otherwise. 
		There is no partial matching, if *match* is not found then the parser is
		left in its original position."""
		matchLen=0
		for m in match:
			if m!=self.theChar and (not self.sgmlNamecaseGeneral or
				self.theChar is None or
				m.lower()!=self.theChar.lower()):
				self.BuffText(match[:matchLen])
				break
			matchLen+=1
			self.NextChar()
		return matchLen==len(match)

	def ParseRequiredLiteral(self,match,production="Literal String"):
		"""Parses a required literal string raising a wellformed error if not matched.
		
		*production* is an optional string describing the context in which the
		literal was expected.
		"""
		if not self.ParseLiteral(match):
			self.WellFormednessError("%s: Expected %s"%(production,match))

	def ParseDecimalDigits(self):
		"""Parses a, possibly empty, string of decimal digits matching [0-9]*."""
		data=[]
		while self.theChar is not None and self.theChar in "0123456789":
			data.append(self.theChar)
			self.NextChar()
		return string.join(data,'')

	def ParseRequiredDecimalDigits(self,production="Digits"):
		"""Parses a required sring of decimal digits matching [0-9]+.
		
		*production* is an optional string describing the context in which the
		digits were expected."""
		digits=self.ParseDecimalDigits()
		if not digits:
			self.WellFormednessError(production+": Expected [0-9]+")
		return digits

	def ParseHexDigits(self):
		"""Parses a, possibly empty, string of hexadecimal digits matching [0-9a-fA-F]."""
		data=[]
		while self.theChar is not None and self.theChar in "0123456789abcdefABCDEF":
			data.append(self.theChar)
			self.NextChar()
		return string.join(data,'')

	def ParseRequiredHexDigits(self,production="Hex Digits"):
		"""Parses a required sring of hexadecimal digits matching [0-9a-fA-F].
		
		*production* is an optional string describing the context in which the
		hexadecimal digits were expected."""
		digits=self.ParseHexDigits()
		if not digits:
			self.WellFormednessError(production+": Expected [0-9a-fA-F]+")
		return digits
							
	def ParseQuote(self,q=None):
		"""Parses the quote character, *q*, or one of "'" or '"' if q is None.
		
		Returns the character parsed or raises a well formed error."""
		if q:
			if self.theChar==q:
				self.NextChar()
				return q
			else:
				self.WellFormednessError("Expected %s"%q)
		elif self.theChar=='"' or self.theChar=="'":
			q=self.theChar
			self.NextChar()
			return q
		else:
			self.WellFormednessError("Expected '\"' or \"'\"")

	def ParseDocument(self,doc=None):
		"""[1] document: parses an XMLDocument.
		
		*doc* is the :py:class:`XMLDocument` instance that will be parsed.  The
		declaration, dtd and elements are added to this document.  If *doc* is
		None then a new instance is created using :py:meth:`GetDocumentClass` to
		identify the correct class to use to represent the document based on
		information in the prolog or, if the prolog lacks a declaration, the
		root element.

		This method returns the document that was parsed, an instance of
		:py:class:`XMLDocument`."""
		self.refMode==XMLParser.RefModeInContent
		self.doc=doc
		if self.checkValidity:
			self.valid=True
		else:
			self.valid=None
		self.validityErrors=[]
		self.ParseProlog()
		if self.doc is None:
			if self.dtd.name is not None:
				# create the document based on information in the DTD
				self.doc=self.GetDocumentClass(self.dtd)()
		self.ParseElement()
		self.ParseMisc()
		if self.theChar is not None and not self.dontCheckWellFormedness:
			self.WellFormednessError("Unparsed characters in entity after document: %s"%repr(self.theChar))

	def GetDocumentClass(self,dtd):
		"""Returns a class object derived from :py:class:`XMLDocument` suitable
		for representing a document with the given document type declaration.

		In cases where no doctype declaration is made a dummy declaration is
		created based on the name of the root element.  For example, if the root
		element is called "database" then the dtd is treated as if it was
		declared as follows::

		<!DOCTYPE database>
		
		This default implementation uses the following three pieces of
		information to locate class registered with
		:py:func:`RegisterDocumentClass`.  The PublicID, SystemID and the name
		of the root element.  If an exact match is not found then wildcard
		matches are attempted, ignoring the SystemID, PublicID and finally the
		root element in turn.  If a document class still cannot be found then
		wildcard matches are tried matching *only* the PublicID, SystemID and
		root element in turn.

		If no document class cab be found, :py:class:`XMLDocument` is
		returned."""
		rootName=dtd.name
		if dtd.externalID is None:
			publicID=None
			systemID=None
			docClass=XMLParser.DocumentClassTable.get((rootName,None,None),None)
		else:
			publicID=dtd.externalID.public
			systemID=dtd.externalID.system
			docClass=XMLParser.DocumentClassTable.get((rootName,publicID,systemID),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((rootName,publicID,None),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((rootName,None,systemID),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((None,publicID,systemID),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((None,publicID,None),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((None,None,systemID),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((rootName,None,None),None)
		if docClass is None:
			docClass=XMLDocument
		return docClass

	#	Production [2] is implemented with the function IsChar

	def ParseS(self):
		"""[3] S: Parses white space from the stream matching the production for S.
		
		If there is no white space at the current position then an empty string
		is returned.
		
		The productions in the specification do not make explicit mention of 
		parameter entity references, they are covered by the general statement
		that "Parameter entity references are recognized anwhere in the DTD..."
		In practice, this means that while parsing the DTD, anywhere that an S
		is permitted a parameter entity reference may also be recognized.  This
		method implements this behaviour, recognizing parameter entity references
		within S when :py:attr:`refMode` is :py:attr:`RefModeInDTD`."""
		s=[]
		sLen=0
		while True:
			if IsS(self.theChar):
				s.append(self.theChar)
				self.NextChar()
			elif self.theChar=='%' and self.refMode==XMLParser.RefModeInDTD:
				self.NextChar()
				if IsNameStartChar(self.theChar):
					self.ParsePEReference(True)
				else:
					# '%' followed by anything other than name start is not a reference.
					self.BuffText('%')
					break
			else:
				break
			sLen+=1
		return string.join(s,'')

	def ParseRequiredS(self,production="[3] S"):
		"""[3] S: Parses required white space from the stream.
		
		If there is no white space then a well-formedness error is raised. 
		*production* is an optional string describing the context in which the
		space was expected."""
		if not self.ParseS() and not self.dontCheckWellFormedness:
			self.WellFormednessError(production+": Expected white space character")		
	
	# Production [4] is implemented with the function IsNameStartChar
	# Production [4a] is implemented with the function IsNameChar.
	
	def ParseName(self):
		"""[5] Name: parses a Name
		
		The name is returned as a unicode string.  If no Name can be parsed then
		None is returned."""
		name=[]
		if IsNameStartChar(self.theChar):
			name.append(self.theChar)
			self.NextChar()
			while IsNameChar(self.theChar):
				name.append(self.theChar)
				self.NextChar()
		if name:
			return string.join(name,'')
		else:
			return None

	def ParseRequiredName(self,production="Name"):
		"""[5] Name: Parses a required Name.
		
		If no name can be parsed then a well-formed error is raised."""
		name=self.ParseName()
		if name is None:
			self.WellFormednessError(production+": Expected NameStartChar")
		return name
		
	def ParseNames(self):
		""" [6] Names: parses a list of Names.
		
		This method returns a tuple of unicode strings.  If no names can be
		parsed then None is returned."""
		names=[]
		name=self.ParseName()
		if name is None:
			return None
		names.append(name)
		while self.theChar==u' ':
			self.NextChar()
			name=self.ParseName()
			if name is None:
				self.BuffText(u' ')
				break
			names.append(name)
		if names:
			return names
		else:
			return None
	
	def ParseNmtoken(self):
		"""[7] Nmtoken: parses a single Nmtoken.
		
		If no Nmtoken can be parsed then None is returned."""
		nmtoken=[]
		while IsNameChar(self.theChar):
			nmtoken.append(self.theChar)
			self.NextChar()
		if nmtoken:
			return string.join(nmtoken,'')
		else:
			return None

	def ParseNmtokens(self):
		"""[8] Nmtokens: parses a list of Nmtokens.
		
		This method returns a tuple of unicode strings.  If no tokens can be
		parsed then None is returned."""
		nmtokens=[]
		nmtoken=self.ParseNmtoken()
		if nmtoken is None:
			return None
		nmtokens.append(nmtoken)
		while self.theChar==u' ':
			self.NextChar()
			nmtoken=self.ParseNmtoken()
			if nmtoken is None:
				self.BuffText(u' ')
				break
			nmtokens.append(nmtoken)
		if nmtokens:
			return nmtokens
		else:
			return None
	
	def ParseEntityValue(self):
		"""[9] EntityValue: parses an EntityValue, returning it as a unicode string.
		
		This method automatically expands other parameter entity references but
		does not expand general or character references."""
		saveMode=self.refMode
		qEntity=self.entity
		q=self.ParseQuote()
		self.refMode=XMLParser.RefModeInEntityValue
		value=[]
		while True:
			if self.theChar=='&':
				value.append(self.ParseReference())
			elif self.theChar=='%':
				self.ParsePEReference()
			elif self.theChar==q:
				if self.entity is qEntity:
					self.NextChar()
					break
				else:
					# a quote but in a different entity is treated as data
					value.append(self.theChar)
					self.NextChar()
			elif IsChar(self.theChar):
				value.append(self.theChar)
				self.NextChar()
			elif self.theChar is None:
				self.WellFormednessError("Incomplete EntityValue")
			else:
				self.WellFormednessError("Unexpected data in EntityValue")
		self.refMode=saveMode
		return string.join(value,'')

	def ParseAttValue(self):
		"""[10] AttValue: parses an attribute value.
		
		The value is returned without the surrounding quotes and with any references
		expanded.
		
		The behaviour of this method is affected significantly by the setting of
		the :py:attr:`dontCheckWellFormedness` flag.  When set, attribute values
		can be parsed without surrounding quotes.  For compatibility with SGML
		these values should match one of the formal value types (e.g., Name) but
		this is not enforced so values like width=100% can be parsed without
		error."""
		production="[10] AttValue"
		value=[]
		try:
			q=self.ParseQuote()
			end=''
		except XMLWellFormedError:
			if not self.dontCheckWellFormedness:
				raise
			q=None
			end='<"\'> \t\r\n'
		qEntity=self.entity
		while True:
			try:
				if self.theChar is None:
					self.WellFormednessError(production+":EOF in AttValue")
				elif self.theChar==q:
					if self.entity is qEntity:
						self.NextChar()
						break
					else:
						value.append(self.theChar)
						self.NextChar()
				elif self.theChar in end and self.entity is qEntity:
					# only when not checking well-formedness mode only
					break
				elif self.theChar=='&':
					refData=self.ParseReference()
					value.append(refData)
				elif IsS(self.theChar):
					value.append(unichr(0x20))
					self.NextChar()
				elif self.theChar=='<':
					self.WellFormednessError(production+": Unescaped < in AttValue")
				else:
					value.append(self.theChar)
					self.NextChar()
			except XMLWellFormedError:
				if not self.dontCheckWellFormedness:
					raise
				elif self.theChar=='<':
					value.append(self.theChar)
					self.NextChar()
				elif self.theChar is None:
					break
		return string.join(value,'')

	def ParseSystemLiteral(self):
		"""[11] SystemLiteral: Parses a literal value matching the production for SystemLiteral.
		
		The value of the literal is returned as a string *without* the enclosing
		quotes."""
		production="[11] SystemLiteral"
		q=self.ParseQuote()
		value=[]
		while True:
			if self.theChar==q:
				self.NextChar()
				break
			elif IsChar(self.theChar):
				value.append(self.theChar)
				self.NextChar()
			elif self.theChar is None:
				self.WellFormednessError(production+": Unexpected end of file")
			else:
				self.WellFormednessError(production+": Illegal character %s"%repr(self.theChar))
		return string.join(value,'')
		
	def ParsePubidLiteral(self):
		"""[12] PubidLiteral: Parses a literal value matching the production for PubidLiteral.

		The value of the literal is returned as a string *without* the enclosing
		quotes."""
		production="[12] PubidLiteral"
		q=self.ParseQuote()
		value=[]
		while True:
			if self.theChar==q:
				self.NextChar()
				break
			elif IsPubidChar(self.theChar):
				value.append(self.theChar)
				self.NextChar()
			elif self.theChar is None:
				self.WellFormednessError(production+": Unexpected End of file")
			else:
				self.WellFormednessError(production+": Illegal character %s"%repr(self.theChar))
		return string.join(value,'')

	def ParseCharData(self):
		"""[14] CharData: parses a run of character data
		
		The method adds the parsed data to the current element.  In the default
		parsing mode it returns None.
		
		When the parser option :py:class:`sgmlOmittag` is selected the method
		returns any parsed character data that could not be added to the current
		element due to a model violation.  Note that in this SGML-like mode any
		S is treated as being in the current element as the violation doesn't
		occurr until the first non-S character (so any implied start tag is
		treated as being immediately prior to the first non-S)."""
		data=[]
		while self.theChar is not None:
			if self.theChar=='<' or self.theChar=='&':
				break
			if self.theChar==']':
				if self.ParseLiteral(']]>'):
					self.BuffText(']]>')
					break
			data.append(self.theChar)
			self.NextChar()
			if len(data)>=XMLEntity.ChunkSize:
				data=string.join(data,'')
				try:
					self.HandleData(data)
				except XMLValidityError:
					if self.sgmlOmittag:
						return StripLeadingS(data)
					raise
				data=[]				
		data=string.join(data,'')
		try:
			self.HandleData(data)
		except XMLValidityError:
			if self.sgmlOmittag:
				return StripLeadingS(data)
			raise
		return None
		
	def ParseComment(self,gotLiteral=False):
		"""[15] Comment: parses a comment.
		
		If *gotLiteral* is True then the method assumes that the '<!--' literal
		has already been parsed."""
		production="[15] Comment"
		data=[]
		nHyphens=0
		if not gotLiteral:
			self.ParseRequiredLiteral('<!--',production)
		cEntity=self.entity
		while self.theChar is not None:
			if self.theChar=='-':
				self.NextChar()
				nHyphens+=1
				if nHyphens>2 and not self.dontCheckWellFormedness:
					self.WellFormednessError("-- in Comment")
			elif self.theChar=='>':
				if nHyphens==2:
					self.CheckPEBetweenDeclarations(cEntity)
					self.NextChar()
					break
				elif nHyphens<2:
					self.NextChar()
					data.append('-'*nHyphens+'>')
					nHyphens=0
				else: # we must be in dontCheckWellFormedness here, we don't need to check.
					data.append('-'*(nHyphens-2))
					self.NextChar()
					break
			elif IsS(self.theChar):
				if nHyphens<2:
					data.append('-'*nHyphens+self.theChar)
					nHyphens=0
				# space does not change the hyphen count
				self.NextChar()
			else:
				if nHyphens:
					if nHyphens>=2 and not self.dontCheckWellFormedness:
						self.WellFormednessError("-- in Comment")
					data.append('-'*nHyphens)									
					nHyphens=0
				data.append(self.theChar)
				self.NextChar()
		return string.join(data,'')
				
	def ParsePI(self,gotLiteral=False):
		"""[16] PI: parses a processing instruction.

		This method calls the
		:py:meth:`XMLContextMixin.ProcessingInstruction` of the current
		element or of the document if no element has been parsed yet.
		
		If *gotLiteral* is True the method assumes the '<?' literal has already
		been parsed."""
		production="[16] PI"
		data=[]
		if not gotLiteral:
			self.ParseRequiredLiteral('<?',production)
		dEntity=self.entity
		target=self.ParsePITarget()
		if self.ParseS():
			while self.theChar is not None:
				if self.theChar=='?':
					self.NextChar()
					if self.theChar=='>':
						self.NextChar()
						break
					else:
						# just a single '?'
						data.append('?')
				data.append(self.theChar)
				self.NextChar()
		else:
			self.CheckPEBetweenDeclarations(dEntity)
			self.ParseRequiredLiteral('?>',production)
		if self.element:
			self.element.ProcessingInstruction(target,string.join(data,''))
		elif self.doc:
			self.doc.ProcessingInstruction(target,string.join(data,''))

	def ParsePITarget(self):
		"""[17] PITarget: parses a processing instruction target name"""
		name=self.ParseName()
		if name.lower()=='xml':
			self.BuffText(name)
			self.WellFormednessError("[17] PITarget: Illegal target: %s"%name)
		return name
		
	def ParseCDSect(self,gotLiteral=False,cdEnd=u']]>'):
		"""[18] CDSect: parses a CDATA section.
		
		This method adds any parsed data to the current element.
		
		If *gotLiteral* is True then the method assumes the initial literal has
		already been parsed.  (By default, CDStart.)  The literal used to
		signify the end of the CDATA section can be overridden by passing an
		alternative literal in *cdEnd*."""
		production="[18] CDSect"
		data=[]
		if not gotLiteral:
			self.ParseCDStart()
		self.ParseCData(cdEnd)
		self.ParseRequiredLiteral(cdEnd,production)

	def ParseCDStart(self):
		"""[19] CDStart: parses the literal that starts a CDATA section."""
		self.ParseRequiredLiteral('<![CDATA[',"[19] CDStart")
		
	def ParseCData(self,cdEnd=']]>'):
		"""[20] CData: parses a run of CData up to but not including *cdEnd*.
		
		This method adds any parsed data to the current element."""
		data=[]
		while self.theChar is not None:
			if self.ParseLiteral(cdEnd):
				self.BuffText(cdEnd)
				break
			data.append(self.theChar)
			self.NextChar()
			if len(data)>=XMLEntity.ChunkSize:
				data=string.join(data,'')
				self.HandleData(data)
				data=[]				
		data=string.join(data,'')
		self.HandleData(data)
		
	def ParseCDEnd(self):
		"""[21] CDEnd: parses the end of a CDATA section."""
		self.ParseRequiredLiteral(']]>',"[21] CDEnd")
		
	def ParseProlog(self):
		"""[22] prolog: parses the document prolog, including the XML declaration and dtd."""
		production="[22] prolog"
		if self.ParseLiteral('<?xml'):
			self.ParseXMLDecl(True)
		else:
			self.declaration=None
		self.entity.KeepEncoding()
		self.ParseMisc()
		if self.ParseLiteral('<!DOCTYPE'):
			self.ParseDoctypedecl(True)
			self.ParseMisc()
		else:
			self.ValidityError(production+": missing document type declaration")
			self.dtd=XMLDTD()
		
	def ParseXMLDecl(self,gotLiteral=False):
		"""[23] XMLDecl: parses an XML declaration.
		
		This method returns an :py:class:`XMLDeclaration` instance.  Also, if an
		encoding is given in the declaration then the method changes the
		encoding of the current entity to match.  For more information see
		:py:meth:`XMLEntity.ChangeEncoding`.
		
		If *gotLiteral* is True the initial literal '<?xml' is assumed to have
		already been parsed."""
		production='[23] XMLDecl'
		if not gotLiteral:
			self.ParseRequiredLiteral('<?xml',production)
		version=self.ParseVersionInfo()
		encoding=None
		standalone=False
		if self.ParseS():
			if self.ParseLiteral('encoding'):
				encoding=self.ParseEncodingDecl(True)
				if self.ParseS():
					if self.ParseLiteral('standalone'):
						standalone=self.ParseSDDecl(True)
			elif self.ParseLiteral('standalone'):
				standalone=self.ParseSDDecl(True)
		self.ParseS()
		self.ParseRequiredLiteral('?>',production)
		if encoding is not None and self.entity.encoding.lower()!=encoding.lower():
			self.entity.ChangeEncoding(encoding)
		self.declaration=XMLDeclaration(version,encoding,standalone)
		return self.declaration
		
	def ParseVersionInfo(self,gotLiteral=False):
		"""[24] VersionInfo: parses XML version number.
		
		The version number is returned as a string.  If *gotLiteral* is True then
		it is assumed that the preceding white space and 'version' literal have
		already been parsed."""
		production="[24] VersionInfo"
		if not gotLiteral:
			self.ParseRequiredS(production)
			self.ParseRequiredLiteral('version',production)
		self.ParseEq(production)
		q=self.ParseQuote()
		self.ParseRequiredLiteral(u'1.')
		digits=self.ParseRequiredDecimalDigits(production)
		version="1."+digits
		self.ParseQuote(q)
		return version

	def ParseEq(self,production="[25] Eq"):
		"""[25] Eq: parses an equal sign, optionally surrounded by white space"""
		self.ParseS()
		self.ParseRequiredLiteral(u'=',production)
		self.ParseS()
		
	def ParseVersionNum(self):
		"""[26] VersionNum: parses the XML version number, returns it as a string."""
		production="[26] VersionNum"
		self.ParseRequiredLiteral('1.',production)
		return '1.'+self.ParseRequiredDecimalDigits(production)
		
	def ParseMisc(self):
		"""[27] Misc: parses multiple Misc items.
		
		This method parses everything that matches the production Misc*"""
		production="[27] Misc"
		while True:
			if IsS(self.theChar):
				self.NextChar()
				continue
			elif self.ParseLiteral('<!--'):
				self.ParseComment(True)
				continue
			elif self.ParseLiteral('<?'):
				self.ParsePI(True)
				continue
			else:
				break
		
	def ParseDoctypedecl(self,gotLiteral=False):
		"""[28] doctypedecl: parses a doctype declaration.
		
		This method creates a new instance of :py:class:`XMLDTD` and assigns it
		to :py:attr:`dtd`, it also returns this instance as the result.
		
		If *gotLiteral* is True the method assumes that the initial literal
		'<!DOCTYPE' has already been parsed."""
		production="[28] doctypedecl"
		if not gotLiteral:
			self.ParseRequiredLiteral('<!DOCTYPE',production)
		saveMode=self.refMode
		self.refMode=XMLParser.RefModeInDTD
		self.dtd=XMLDTD()
		self.ParseRequiredS(production)
		self.dtd.name=self.ParseRequiredName(production)
		if self.ParseS():
			# could be an ExternalID
			if self.theChar!='[' and self.theChar!='>':
				self.dtd.externalID=self.ParseExternalID()
				self.ParseS()
		if self.ParseLiteral('['):
			self.ParseIntSubset()
			self.ParseRequiredLiteral(']',production)
			self.ParseS()
		if self.dtd.externalID:
			# Before we parse the closing literal we load any external subset
			src=self.ResolveExternalID(self.dtd.externalID)
			if src:
				externalDTDSubset=XMLEntity(src)
				self.PushEntity(externalDTDSubset)
				self.ParseExtSubset()
		self.ParseRequiredLiteral('>',production)
		self.refMode=saveMode
		return self.dtd
		
	def ParseDeclSep(self):
		"""[28a] DeclSep: parses a declaration separator."""
		gotSep=False
		while True:
			if self.theChar=='%':
				refEntity=self.entity
				self.ParsePEReference()
				if self.entity is not refEntity:
					# we have a new entity, flag it as being opened in DeclSep
					self.entity.flags['DeclSep']=True
				gotSep=True
			elif IsS(self.theChar):
				self.NextChar()
				gotSep=True
			else:
				break
		if not gotSep:
			self.WellFormednessError("[28a] DeclSep: expected PEReference or S, found %s"%repr(self.theChar))
	
	def ParseIntSubset(self):
		"""[28b] intSubset: parses an internal subset."""
		subsetEntity=self.entity
		while True:
			if self.theChar=='<':
				self.noPERefs=(self.GetExternalEntity() is subsetEntity)
				self.ParseMarkupDecl()
				self.noPERefs=False
			elif self.theChar=='%' or IsS(self.theChar):
				self.ParseDeclSep()
			else:
				break
		
	def ParseMarkupDecl(self,gotLiteral=False):
		"""[29] markupDecl: parses a markup declaration.
		
		Returns True if a markupDecl was found, False otherwise."""
		production="[29] markupDecl"
		if not gotLiteral:
			self.ParseRequiredLiteral('<',production)
		if self.theChar=='?':
			self.NextChar()
			self.ParsePI(True)
		elif self.theChar=='!':
			self.NextChar()
			if self.theChar=='-':
				self.ParseRequiredLiteral('--',production)
				self.ParseComment(True)
			elif self.ParseLiteral('ELEMENT'):
				self.ParseElementDecl(True)
			elif self.ParseLiteral('ATTLIST'):
				self.ParseAttlistDecl(True)
			elif self.ParseLiteral('ENTITY'):
				self.ParseEntityDecl(True)
			elif self.ParseLiteral('NOTATION'):
				self.ParseNotationDecl(True)
			else:
				self.WellFormednessError(production+": expected markup declaration")
		else:
			self.WellFormednessError(production+": expected markup declaration")
	
	def ParseExtSubset(self):
		"""[30] extSubset: parses an external subset"""
		if self.ParseLiteral('<?xml'):
			self.ParseTextDecl(True)
		self.ParseExtSubsetDecl()
			
	def ParseExtSubsetDecl(self):
		"""[31] extSubsetDecl: parses declarations in the external subset."""
		initialStack=len(self.entityStack)
		while len(self.entityStack)>=initialStack:
			literalEntity=self.entity
			if self.theChar=='%' or IsS(self.theChar):
				self.ParseDeclSep()
			elif self.ParseLiteral("<!["):
				self.ParseConditionalSect(literalEntity)
			elif self.theChar=='<':
				self.ParseMarkupDecl()
			else:
				break

	def CheckPEBetweenDeclarations(self,checkEntity):
		"""[31] extSubsetDecl: checks the well-formedness constraint on use of PEs between declarations.
		
		*checkEntity* is the entity we should still be in!"""
		if self.checkValidity and self.entity is not checkEntity:
			self.ValidityError("Proper Declaration/PE Nesting: found '>' in entity %s"%self.entity.GetName())					
		if not self.dontCheckWellFormedness and self.entity is not checkEntity and checkEntity.flags.get('DeclSep',False):
			# a badly nested declaration in an entity opened within a DeclSep is a well-formedness error
			self.WellFormednessError("[31] extSubsetDecl: failed for entity %s included in a DeclSep"%checkEntity.GetName())
	
	def ParseSDDecl(self,gotLiteral=False):
		"""[32] SDDecl: parses a standalone declaration
		
		Returns True if the document should be treated as standalone; False otherwise."""
		production="[32] SDDecl"
		if not gotLiteral:
			self.ParseRequiredS(production)
			self.ParseRequiredLiteral('standalone',production)
		self.ParseEq(production)
		q=self.ParseQuote()
		if self.theChar==u'y':
			result=True
			match=u'yes'
		else:
			result=False
			match=u'no'
		self.ParseRequiredLiteral(match,production)
		self.ParseQuote(q)
		return result
		
	def ParseElement(self):
		"""[39] element: parses an element, including its content.
		
		The class used to represent the element is determined by calling the
		:py:meth:`XMLDocument.GetElementClass` method of the current document.
		If there is no document yet then a new document is created automatically
		(see :py:meth:`ParseDocument` for more information).
		
		The element is added as a child of the current element using
		:py:meth:`XMLContextMixin.ChildElement`.
		
		The method returns:
		
		-	True: indicates that an element was parsed normally
		-	False: indicates that the element is not allowed in this context
		
		The second case only occurs when the :py:attr:`sgmlOmittag` option is in
		use and it indicates that the content of the enclosing element has
		ended.  The Tag is buffered so that it can be reparsed when the stack of
		nested :py:meth:`ParseContent` and :py:meth:`ParseElement` calls is
		unwound to the point where it is allowed by the context."""
		production="[39] element"
		saveElement=self.element
		saveElementType=self.elementType
		if self.sgmlOmittag and self.theChar!='<':
			# Leading data means the start tag was omitted (perhaps at the start of the doc)
			name=None
			attrs={}
			empty=False
		else:
			name,attrs,empty=self.ParseSTag()
			if self.checkValidity:
				if saveElement is None and self.dtd.name is not None and self.dtd.name!=name:
					self.ValidityError("Root Element Type: expected element %s"%self.dtd.name)
				aList=self.dtd.GetAttributeList(name)
				self.elementType=self.dtd.GetElementType(name)
				if aList:
					for a in aList.keys():
						aDef=aList[a]
						checkStandalone=self.declaration and self.declaration.standalone and aDef.entity is not self.docEntity
						value=attrs.get(a,None)
						if value is None:
							# check for default
							if aDef.presence==XMLAttributeDefinition.Default:
								attrs[a]=aDef.defaultValue
								if checkStandalone:
									self.ValidityError("Standalone Document Declaration: specification for attribute %s required (externally defined default)"%a)
						else:
							if aDef.type!=XMLAttributeDefinition.CData:
								# ...then the XML processor must further process the normalized attribute value by
								# discarding any leading and trailing space (#x20) characters, and by replacing
								# sequences of space (#x20) characters by a single space (#x20) character.
								newValue=NormalizeSpace(value)
								if checkStandalone and newValue!=value:
									self.ValidityError("Standalone Document Declaration: specification for attribute %s altered by normalization (externally defined tokenized type)"%a)
								attrs[a]=newValue
				if self.elementType:
					pass
				else:
					self.ValidityError("Element Valid: element %s is not declared"%name) 
			if self.stagBuffer:
				name,attrs,empty=self.stagBuffer
				self.stagBuffer=None
		elementClass,elementName,bufferTag=self.GetSTagClass(name,attrs)
		if elementClass:
			if bufferTag and name:
				# elementClass represents an omitted start tag
				self.stagBuffer=(name,attrs,empty)
				# This strange text is a valid start tag that ensures we'll be called again
				self.BuffText("<:>")
				# omitted start tags introduce element that have no attributes and must not be empty
				attrs={}
				empty=False
		else:
			# this start tag indicates an omitted end tag: always buffered
			if name:
				self.stagBuffer=(name,attrs,empty)
				self.BuffText("<:>")
			return False
		if self.element is None:
			self.element=self.doc.ChildElement(elementClass,elementName)
		else:
			self.element=self.element.ChildElement(elementClass,elementName)
		if self.sgmlContent and getattr(elementClass,'XMLCONTENT',XMLMixedContent)==XMLEmpty:
			empty=True
		for attr in attrs.keys():
			try:
				self.element.SetAttribute(attr,attrs[attr])
			except XMLValidityError:
				if self.raiseValidityErrors:
					raise
# 		if attrs.get('href','')=='#fragment-1':
# 			import pdb;pdb.set_trace()
		if not empty:
			saveDataCount=self.dataCount
			if self.sgmlContent and getattr(self.element,'SGMLCONTENT',None)==XMLElementType.SGMLCDATA:
				# Alternative parsing of SGMLCDATA elements...
				# SGML says that the content ends at the first ETAGO
				while True:
					self.ParseCData('</')
					if self.theChar is None:
						break
					self.ParseRequiredLiteral('</',"SGML CDATA Content:")
					endName=self.ParseName()
					if endName!=name:
						# but this is such a common error we ignore it
						self.element.AddData('</'+endName)
					else:
						self.ParseS()
						self.ParseRequiredLiteral('>',"SGML CDATA ETag:")
						break
			else:
				while self.ParseContent():		# otherwise content detected end of element (so end tag was omitted)
					endName=self.ParseETag()
					if endName==name:
						break
					spuriousTag=True
					if self.sgmlOmittag:
						# do we have a matching open element?
						if self.dontCheckWellFormedness:
							# by starting the check at the current element we allow
							# mismatched but broadly equivalent STags and ETags
							iElement=self.element
						else:
							iElement=self.element.parent
						while isinstance(iElement,XMLElement):
							if self.MatchXMLName(iElement,endName):
								spuriousTag=False
								# push a closing tag back onto the parser
								self.BuffText('</%s>'%endName)
								break
							else:
								iElement=iElement.parent
					if spuriousTag:
						if self.dontCheckWellFormedness:
							# ignore spurious end tags, we probably inferred them earlier
							continue
						else:
							self.WellFormednessError("Element Type Mismatch: found </%s>, expected <%s/>"%(endName,name))
					else:
						break
			if name is None and self.dataCount==saveDataCount:
				# This element was triggered by data which elementClass was supposed to consume
				# It didn't consume any data so we raise an error here to prevent a loop
				raise XMLFatalError(production+": element implied by PCDATA had empty content %s"%self.element) 
		self.element.ContentChanged()
		self.element=saveElement
		self.elementType=saveElementType
		return True

	def MatchXMLName(self,element,name):
		"""Tests if *name* is a possible name for this element.
		
		This method is used by the parser to determine if an end tag is the end
		tag of this element.  It is provided a separate method to allow it to be
		overridden by derived parsers"""
		return element.GetXMLName()==name

	def GetSTagClass(self,name,attrs=None):
		"""[40] STag: returns information suitable for starting element *name* with
		attributes *attrs* in the current context
		
		If there is no :py:class:`XMLDocument` instance yet this method assumes
		that it is being called for the root element and selects an appropriate
		class based on the contents of the prolog and/or *name*.
		
		When using the :py:attr:`sgmlOmittag` option *name* may be None
		indicating that the method should return information about the element
		implied by PCDATA in the current context (only called when an attempt to
		add data to the current context has already failed).
		
		The result is a triple of:
		
		-	elementClass:
			the element class that this STag must introduce or None if this STag
			does not belong (directly or indirectly) in the current context
		-	elementName:
			the name of the element (to pass to ChildElement) or None to use the
			default
		-	buffFlag:
			True indicates an omitted tag and that the triggering STag (i.e.,
			the STag with name *name*) should be buffered.
		"""
		if self.doc is None:
			if self.dtd is None:
				self.dtd=XMLDTD()
			if self.dtd.name is None:
				self.dtd.name=name
			elif name is None:
				# document starts with PCDATA, use name declared in DOCTYPE
				name=self.dtd.name
			self.doc=self.GetDocumentClass(self.dtd)()
		context=self.GetContext()
		if self.sgmlOmittag:
			if name:
				stagClass=self.doc.GetElementClass(name)
			else:
				stagClass=None
			elementClass=context.GetChildClass(stagClass)
			if elementClass is not stagClass:
				return elementClass,None,True
			else:
				return elementClass,name,False
		else:
			return self.doc.GetElementClass(name),name,False
	
	def ParseSTag(self):
		"""[40] STag, [44] EmptyElemTag: parses a start tag or an empty element tag.
		
		This method returns a triple of name, attrs, emptyFlag where:
		
		-	*name* 
			is the name of the element parsed.
		-	*attrs*
			is a dictionary of attribute values keyed by attribute name
		-	*emptyFlag*
			is a boolean; True indicates that the tag was an empty element
			tag."""
		production="[40] STag"
		empty=False
		self.ParseRequiredLiteral('<')
		name=self.ParseRequiredName()
		attrs={}
		while True:
			try:
				s=self.ParseS()
				if self.theChar=='>':
					self.NextChar()
					break
				elif self.theChar=='/':
					self.ParseRequiredLiteral('/>')
					empty=True
					break
				if s:
					aName,aValue=self.ParseAttribute()
					attrs[aName]=aValue
				else:
					self.WellFormednessError("Expected S, '>' or '/>', found '%s'"%self.theChar)
			except XMLWellFormedError:
				if not self.dontCheckWellFormedness:
					raise
				# spurious character inside a start tag, in compatibility mode we
				# just discard it and keep going
				self.NextChar()
				continue
		return name,attrs,empty

	def ParseAttribute(self):
		"""[41] Attribute: parses an attribute
		
		Returns *name*, *value* where:
		
		-	name 
			is the name of the attribute or None if :py:attr:`sgmlShorttag` is
			True and a short form attribute value was supplied.
		-	value is the attribute value.
		
		If :py:attr:`dontCheckWellFormedness` the parser uses a very generous
		form of parsing attribute values to accomodate common syntax errors."""
		production="[41] Attribute"
		name=self.ParseRequiredName(production)
		if self.sgmlShorttag:
			# name on its own may be OK
			s=self.ParseS()
			if self.theChar!='=':
				self.BuffText(s)
				return '@'+name,name
		self.ParseEq(production)
		value=self.ParseAttValue()
		return name,value
	
	def ParseETag(self,gotLiteral=False):
		"""[42] ETag: parses an end tag
		
		If *gotLiteral* is True then the method assumes the initial '</' literal
		has been parsed alread.
		
		The method returns the name of the end element parsed."""
		production="[42] ETag"
		if not gotLiteral:
			self.ParseRequiredLiteral('</')
		name=self.ParseRequiredName(production)
		self.ParseS()
		if self.dontCheckWellFormedness:
			# ignore all rubbish in end tags
			while self.theChar is not None:
				if self.theChar=='>':
					self.NextChar()
					break
				self.NextChar()
		else:	
			self.ParseRequiredLiteral('>',production)
		return name
							
	def ParseContent(self):
		"""[43] content: parses the content of an element.
		
		The method returns:
		
		-	True:
			indicates that the content was parsed normally
		-	False:
			indicates that the content contained data or markup not allowed in
			this context
		
		The second case only occurs when the :py:attr:`sgmlOmittag` option is in
		use and it indicates that the enclosing element has ended (i.e., the
		element's ETag has been omitted).  See py:meth:`ParseElement` for more
		information."""			
		while True:
			if self.theChar=='<':
				# element, CDSect, PI or Comment
				self.NextChar()
				if self.theChar=='!':
					# CDSect or Comment
					self.NextChar()
					if self.theChar=='-':
						self.ParseRequiredLiteral('--')
						self.ParseComment(True)
						if self.checkValidity and self.elementType.contentType==XMLElementType.Empty:
							self.ValidityError("Element Valid: comment not allowed in element declared EMPTY: %s"%self.elementType.name)
					elif self.theChar=='[':
						self.ParseRequiredLiteral('[CDATA[')
						# can CDATA sections imply missing markup?
						if self.sgmlOmittag and not self.element.IsMixed():
							# CDATA can only be put in elements that can contain data!
							self.BuffText('<![CDATA[')
							self.UnhandledData('')
						else:
							self.ParseCDSect(True)
					else:
						self.WellFormednessError("Expected Comment or CDSect")
				elif self.theChar=='?':
					# PI
					self.NextChar()
					self.ParsePI(True)
					if self.checkValidity and self.elementType.contentType==XMLElementType.Empty:
						self.ValidityError("Element Valid: processing instruction not allowed in element declared EMPTY: %s"%self.elementType.name)
				elif self.theChar!='/':
					# element
					self.BuffText('<')
					if not self.ParseElement():
						return False
				else:
					# end of content
					self.BuffText('<')
					break
			elif self.theChar=='&':
				# Reference
				if self.sgmlOmittag and not self.element.IsMixed():
					# we step in before resolving the reference, just in case
					# this reference results in white space that is supposed
					# to be the first data character after the omitted tag.
					self.UnhandledData('')
				else:					
					data=self.ParseReference()
					if self.checkValidity and self.elementType.contentType==XMLElementType.Empty:
						self.ValidityError("Element Valid: reference not allowed in element declared EMPTY: %s"%self.elementType.name)
					self.HandleData(data)
			elif self.theChar is None:
				# end of entity
				if self.sgmlOmittag:
					return False
				else:
					# leave the absence of an end tag for ParseElement to worry about
					return True
			else:
				pcdata=self.ParseCharData()
				if pcdata and not self.UnhandledData(pcdata):
					# indicates end of the containing element
					return False
		return True

	def HandleData(self,data):
		"""[43] content: handles character data in content."""
		if data and self.element:
			if self.checkValidity and self.elementType:
				checkStandalone=self.declaration and self.declaration.standalone and self.elementType.entity is not self.docEntity
				if checkStandalone and self.elementType.contentType==XMLElementType.ElementContent and ContainsS(data):
					self.ValidityError("Standalone Document Declaration: white space not allowed in element %s (externally defined as element content)"%self.elementType.name)
				if self.elementType.contentType==XMLElementType.Empty:
					self.ValidityError("Element Valid: content not allowed in element declared EMPTY: %s"%self.elementType.name)
			self.element.AddData(data)
			self.dataCount+=len(data)
		
	def UnhandledData(self,data):
		"""[43] content: manages unhandled data in content.
		
		This method is only called when the :py:attr:`sgmlOmittag` option is in use.
		It processes *data* that occurs in a context where data is not allowed.
		
		It returns a boolean result:
		
		-	True:
			the data was consumed by a sub-element (with an omitted start tag)
		-	False:
			the data has been buffered and indicates the end of the current
			content (an omitted end tag)."""
		if data:
			self.BuffText(EscapeCharData(data))
		# Two choices: PCDATA starts a new element or ends this one
		elementClass,elementName,ignore=self.GetSTagClass(None)
		if elementClass:
			return self.ParseElement()
		else:
			return False
		
	def ParseEmptyElemTag(self):
		"""[44] EmptyElemTag: there is no method for parsing empty element tags alone.
		
		This method raises NotImplementedError.  Instead, you should call
		:py:meth:`ParseSTag` and examine the result.  If it returns False then
		an empty element was parsed."""
		raise NotImplementedError
		
	def ParseElementDecl(self,gotLiteral=False):
		"""[45] elementdecl: parses an element declaration
		
		If *gotLiteral* is True the method assumes that the '<!ELEMENT' literal
		has already been parsed."""
		production="[45] elementdecl"
		eType=XMLElementType()
		if not gotLiteral:
			self.ParseRequiredLiteral('<!ELEMENT',production)
		eType.entity=self.entity
		self.ParseRequiredS(production)
		eType.name=self.ParseRequiredName(production)
		self.ParseRequiredS(production)
		self.ParseContentSpec(eType)
		self.ParseS()
		self.ParseRequiredLiteral('>',production)
		self.CheckPEBetweenDeclarations(eType.entity)
		if self.checkValidity and self.dtd:
			self.dtd.DeclareElementType(eType)
			
	def ParseContentSpec(self,eType):
		"""[46] contentspec: parses the content specification for an element type """
		production="[46] contentspec"
		if self.ParseLiteral('EMPTY'):
			eType.contentType=XMLElementType.Empty
			eType.contentModel=None
		elif self.ParseLiteral('ANY'):
			eType.contentType=XMLElementType.Any
			eType.contentModel=None
		elif self.ParseLiteral('('):
			self.ParseS()
			if self.ParseLiteral('#PCDATA'):
				eType.contentType=XMLElementType.Mixed
				eType.contentModel=self.ParseMixed(True)
			else:
				eType.contentType=XMLElementType.ElementContent
				eType.contentModel=self.ParseChildren(True)
		else:
			self.WellFormednessError(production,": expected 'EMPTY', 'ANY' or '('")
			
	def ParseChildren(self,gotLiteral=False):
		"""[47] children: parses an element content model comprising children.
		
		If *gotLiteral* is True the method assumes that the initial '(' literal
		has already been parsed, including any following white space.
		
		The method returns an instance of :py:class:`XMLContentParticle`."""
		production="[47] children"
		if not gotLiteral:
			if not self.ParseLiteral('('):
				self.WellFormednessError(production+": expected choice or seq")
			self.ParseS()
		# choice or seq
		firstChild=self.ParseCP()
		self.ParseS()
		if self.theChar==',' or self.theChar==')':
			cp=self.ParseSeq(firstChild)
		elif self.theChar=='|':
			cp=self.ParseChoice(firstChild)
		else:
			self.WellFormednessError(production+": expected seq or choice")
		if self.theChar=='?':
			cp.occurrence=XMLContentParticle.ZeroOrOne
			self.NextChar()
		elif self.theChar=='*':
			cp.occurrence=XMLContentParticle.ZeroOrMore
			self.NextChar()
		elif self.theChar=='+':
			cp.occurrence=XMLContentParticle.OneOrMore
			self.NextChar()
		return cp
		
	def ParseCP(self):
		"""[48] cp: parses a content particle"""
		production="[48] cp"
		if self.ParseLiteral('('):
			# choice or seq
			self.ParseS()
			firstChild=self.ParseCP()
			self.ParseS()
			if self.theChar==',' or self.theChar==')':
				cp=self.ParseSeq(firstChild)
			elif self.theChar=='|':
				cp=self.ParseChoice(firstChild)
			else:
				self.WellFormednessError(production+": expected seq or choice")
		else:
			cp=XMLNameParticle()
			cp.name=self.ParseRequiredName(production)
		if self.theChar=='?':
			cp.occurrence=XMLContentParticle.ZeroOrOne
			self.NextChar()
		elif self.theChar=='*':
			cp.occurrence=XMLContentParticle.ZeroOrMore
			self.NextChar()
		elif self.theChar=='+':
			cp.occurrence=XMLContentParticle.OneOrMore
			self.NextChar()
		return cp
	
	def ParseChoice(self,firstChild=None):
		"""[49] choice: parses a sequence of content particles.
		
		*firstChild* is an optional :py:class:`XMLContentParticle` instance.  If
		present the method assumes that the first particle and any following
		white space has already been parsed."""
		production="[49] choice"
		cp=XMLChoiceList()
		if firstChild is None:
			self.ParseRequiredLiteral('(',production)
			self.ParseS()
			firstChild=self.ParseCP()
			self.ParseS()
		cp.children.append(firstChild)
		while True:
			if self.theChar=='|':
				self.NextChar()
			elif self.theChar==')':
				if len(cp.children)>1:
					self.NextChar()
					break
				else:
					self.WellFormednessError(production+": Expected '|', found %s"%repr(self.theChar))
			else:
				self.WellFormednessError(production+": Expected '|' or ')', found %s"%repr(self.theChar))
			self.ParseS()
			cp.children.append(self.ParseCP())
			self.ParseS()			
		return cp

	def ParseSeq(self,firstChild=None):
		"""[50] seq: parses a sequence of content particles.
		
		*firstChild* is an optional :py:class:`XMLContentParticle` instance.  If
		present the method assumes that the first particle and any following
		white space has already been parsed."""
		production="[50] seq"
		cp=XMLSequenceList()
		if firstChild is None:
			self.ParseRequiredLiteral('(',production)
			self.ParseS()
			firstChild=self.ParseCP()
			self.ParseS()
		cp.children.append(firstChild)
		while True:
			if self.theChar==',':
				self.NextChar()
			elif self.theChar==')':
				self.NextChar()
				break
			else:
				self.WellFormednessError(production+": Expected ',' or ')', found %s"%repr(self.theChar))
			self.ParseS()
			cp.children.append(self.ParseCP())
			self.ParseS()			
		return cp

	def ParseMixed(self,gotLiteral=False):
		"""[51] Mixed: parses a mixed content type.
		
		If *gotLiteral* is True the method assumes that the #PCDATA literal
		has already been parsed.
		
		Returns an instance of :py:class:`XMLChoiceList` with occurrence
		:py:attr:`XMLContentParticle.ZeroOrMore` representing the list of
		elements that may appear in the mixed content model. If the mixed model
		contains #PCDATA only then the choice list will be empty."""
		production="[51] Mixed"
		cp=XMLChoiceList()
		cp.occurrence=XMLContentParticle.ZeroOrMore
		if not gotLiteral:
			self.ParseRequiredLiteral('(',production)
			self.ParseS()
			self.ParseRequiredLiteral('#PCDATA',production)
		while True:
			self.ParseS()
			if self.theChar==')':
				break
			elif self.theChar=='|':
				self.NextChar()
				self.ParseS()
				cpChild=XMLNameParticle()
				cpChild.name=self.ParseRequiredName(production)
				cp.children.append(cpChild)
				continue
			else:
				self.WellFormednessError(production+": Expected '|' or ')'")
		if len(cp.children):
			self.ParseRequiredLiteral(')*')
		else:
			self.ParseRequiredLiteral(')')
			self.ParseLiteral('*')
		return cp
		
	def ParseAttlistDecl(self,gotLiteral=False):
		"""[52] AttlistDecl: parses an attribute list definition.
		
		If *gotLiteral* is True the method assumes that the '<!ATTLIST' literal
		has already been parsed.
		"""
		production="[52] AttlistDecl"
		dEntity=self.entity
		if not gotLiteral:
			self.ParseRequiredLiteral("<!ATTLIST",production)
		self.ParseRequiredS(production)
		name=self.ParseRequiredName(production)
		while True:
			if self.ParseS():
				if self.theChar=='>':
					break
				a=self.ParseAttDef(True)
				if self.dtd:
					a.entity=dEntity
					self.dtd.DeclareAttribute(name,a)
			else:
				break
		self.CheckPEBetweenDeclarations(dEntity)
		self.ParseRequiredLiteral('>',production)	
	
	def ParseAttDef(self,gotS=False):
		"""[53] AttDef: parses an attribute definition.

		If *gotS* is True the method assumes that the leading S has already been
		parsed.
		
		Returns an instance of :py:class:`XMLAttributeDefinition`."""
		production="[53] AttDef"
		if not gotS:
			self.ParseRequiredS(production)
		a=XMLAttributeDefinition()
		a.name=self.ParseRequiredName(production)
		self.ParseRequiredS(production)
		self.ParseAttType(a)
		self.ParseRequiredS(production)
		self.ParseDefaultDecl(a)
		return a
		
	def ParseAttType(self,a):
		"""[54] AttType: parses an attribute type.
		
		*a* must be an :py:class:`XMLAttributeDefinition` instance.  This method sets the
		:py:attr:`XMLAttributeDefinition.type` and :py:attr:`XMLAttributeDefinition.values`
		fields of *a*.
		
		Note that, to avoid unnecessary look ahead, this method does not call
		:py:meth:`ParseStringType` or :py:meth:`ParseEnumeratedType`."""
		production="[54] AttType"
		if self.ParseLiteral('CDATA'):
			a.type=XMLAttributeDefinition.CData
			a.values=None
		elif self.ParseLiteral('NOTATION'):
			a.type=XMLAttributeDefinition.Notation
			a.values=self.ParseNotationType(True)
		elif self.theChar=='(':
			a.type=XMLAttributeDefinition.Enumeration
			a.values=self.ParseEnumeration()
		else:
			self.ParseTokenizedType(a)

	def ParseStringType(self,a):
		"""[55] StringType: parses an attribute's string type.
		
		This method is provided for completeness.  It is not called during normal
		parsing operations.
		
		*a* must be an :py:class:`XMLAttributeDefinition` instance.  This method sets the
		:py:attr:`XMLAttributeDefinition.type` and :py:attr:`XMLAttributeDefinition.values`
		fields of *a*."""
		production="[55] StringType"
		self.ParseRequiredLiteral('CDATA',production)
		a.type=XMLAttributeDefinition.CData
		a.values=None

	def ParseTokenizedType(self,a):
		"""[56] TokenizedType: parses an attribute's tokenized type.
		
		*a* must be an :py:class:`XMLAttributeDefinition` instance.  This method sets the
		:py:attr:`XMLAttributeDefinition.type` and :py:attr:`XMLAttributeDefinition.values`
		fields of *a*."""
		production="[56] TokenizedType"
		if self.ParseLiteral('ID'):
			if self.ParseLiteral('REF'):
				if self.ParseLiteral('S'):
					a.type=XMLAttributeDefinition.IDRefs
				else:
					a.type=XMLAttributeDefinition.IDRef
			else:
				a.type=XMLAttributeDefinition.ID
		elif self.ParseLiteral('ENTIT'):
			if self.ParseLiteral('Y'):
				a.type=XMLAttributeDefinition.Entity
			elif self.ParseLiteral('IES'):
				a.type=XMLAttributeDefinition.Entities
			else:
				self.WellFormednessError(production+": Expected 'ENTITY' or 'ENTITIES'")
		elif self.ParseLiteral('NMTOKEN'):
			if self.ParseLiteral('S'):
				a.type=XMLAttributeDefinition.NmTokens
			else:
				a.type=XMLAttributeDefinition.NmToken
		else:
			self.WellFormednessError(production+": Expected 'ID', 'IDREF', 'IDREFS', 'ENTITY', 'ENTITIES', 'NMTOKEN' or 'NMTOKENS'")
		a.values=None
		
	def ParseEnumeratedType(self,a):
		"""[57] EnumeratedType: parses an attribute's enumerated type.
		
		This method is provided for completeness.  It is not called during normal
		parsing operations.
		
		*a* must be an :py:class:`XMLAttributeDefinition` instance.  This method sets the
		:py:attr:`XMLAttributeDefinition.type` and :py:attr:`XMLAttributeDefinition.values`
		fields of *a*."""
		if self.ParseLiteral('NOTATION'):
			a.type=XMLAttributeDefinition.Notation
			a.values=self.ParseNotationType(True)
		elif self.theChar=='(':
			a.type=XMLAttributeDefinition.Enumeration
			a.values=self.ParseEnumeration()
		else:
			self.WellFormednessError("[57] EnumeratedType: expected 'NOTATION' or Enumeration")
			
	def ParseNotationType(self,gotLiteral=False):
		"""[58] NotationType: parses a notation type.
		
		If *gotLiteral* is True the method assumes that the leading 'NOTATION' literal
		has already been parsed.

		Returns a list of strings representing the names of the declared notations being
		referred to."""
		production="[58] NotationType"
		value=[]
		if not gotLiteral:
			self.ParseRequiredLiteral('NOTATION',production)
		self.ParseRequiredS(production)
		self.ParseRequiredLiteral('(',production)
		while True:
			self.ParseS()
			name=self.ParseRequiredName(production)
			value.append(name)
			self.ParseS()
			if self.theChar=='|':
				self.NextChar()
				continue
			elif self.theChar==')':
				self.NextChar()
				break
			else:
				self.WellFormednessError(production+": expected '|' or ')', found %s"%repr(self.theChar))
		return value	
		
	def ParseEnumeration(self):
		"""[59] Enumeration: parses an enumeration.
		
		Returns a list of strings representing the tokens in the enumeration."""
		production="[59] Enumeration"
		value=[]
		self.ParseRequiredLiteral('(',production)
		while True:
			self.ParseS()
			token=self.ParseNmtoken()
			if token:
				value.append(token)
			else:
				self.WellFormednessError(production+": expected Nmtoken")
			self.ParseS()
			if self.theChar=='|':
				self.NextChar()
				continue
			elif self.theChar==')':
				self.NextChar()
				break
			else:
				self.WellFormednessError(production+": expected '|' or ')', found %s"%repr(self.theChar))
		return value	
		
	def ParseDefaultDecl(self,a):
		"""[60] DefaultDecl: parses an attribute's default declaration.
		
		*a* must be an :py:class:`XMLAttributeDefinition` instance.  This method sets the
		:py:attr:`XMLAttributeDefinition.presence` and :py:attr:`XMLAttributeDefinition.defaultValue`
		fields of *a*."""
		if self.ParseLiteral('#REQUIRED'):
			a.presence=XMLAttributeDefinition.Required
			a.defaultValue=None
		elif self.ParseLiteral('#IMPLIED'):
			a.presence=XMLAttributeDefinition.Implied
			a.defaultValue=None
		else:
			if self.ParseLiteral('#FIXED'):
				a.presence=XMLAttributeDefinition.Fixed
				self.ParseRequiredS("[60] DefaultDecl")
			else:
				a.presence=XMLAttributeDefinition.Default
			a.defaultValue=self.ParseAttValue()
			
	def ParseConditionalSect(self,gotLiteralEntity=None):
		"""[61] conditionalSect: parses a conditional section.
		
		If *gotLiteralEntity* is set to an :py:class:`XMLEntity` object the
		method assumes that the initial literal '<![' has already been parsed
		from that entity."""
		production="[61] conditionalSect"
		if gotLiteralEntity is None:
			gotLiteralEntity=self.entity
			self.ParseRequiredLiteral('<![',production)
		self.ParseS()
		if self.ParseLiteral('INCLUDE'):
			self.ParseIncludeSect(gotLiteralEntity)
		elif self.ParseLiteral('IGNORE'):
			self.ParseIgnoreSect(gotLiteralEntity)
		else:
			self.WellFormednessError(production+": Expected INCLUDE or IGNORE")
		
	def ParseIncludeSect(self,gotLiteralEntity=None):
		"""[62] includeSect: parses an included section.
		
		If *gotLiteralEntity* is set to an :py:class:`XMLEntity` object the
		method assumes that the production, up to and including the keyword
		'INCLUDE' has already been parsed and that the opening '<![' literal was
		parsed from that entity."""
		production="[62] includeSect"
		if gotLiteralEntity is None:
			gotLiteralEntity=self.entity
			self.ParseRequiredLiteral('<![',production)
			self.ParseS()
			self.ParseRequiredLiteral('INCLUDE',production)
		self.ParseS()
		if self.checkValidity and not self.entity is gotLiteralEntity:
			self.ValidityError(production+": Proper Conditional Section/PE Nesting")
		self.ParseRequiredLiteral('[',production)
		self.ParseExtSubsetDecl()
		if self.checkValidity and not self.entity is gotLiteralEntity:
			self.ValidityError(production+": Proper Conditional Section/PE Nesting")
		self.ParseRequiredLiteral(']]>',production)
		
	def ParseIgnoreSect(self,gotLiteralEntity=None):
		"""[63] ignoreSect: parses an ignored section.
		
		If *gotLiteralEntity* is set to an :py:class:`XMLEntity` object the method
		assumes that the production, up to and including the keyword 'IGNORE' has already
		been parsed and that the opening '<![' literal was parsed from that entity."""
		production="[63] ignoreSect"
		if gotLiteralEntity is None:
			gotLiteralEntity=self.entity
			self.ParseRequiredLiteral('<![',production)
			self.ParseS()
			self.ParseRequiredLiteral('IGNORE',production)
		self.ParseS()
		if self.checkValidity and not self.entity is gotLiteralEntity:
			self.ValidityError(production+": Proper Conditional Section/PE Nesting")
		self.ParseRequiredLiteral('[',production)
		self.ParseIgnoreSectContents()
		if self.checkValidity and not self.entity is gotLiteralEntity:
			self.ValidityError(production+": Proper Conditional Section/PE Nesting")
		self.ParseRequiredLiteral(']]>',production)		
		
	def ParseIgnoreSectContents(self):
		"""[64] ignoreSectContents: parses the contents of an ignored section.
		
		The method returns no data."""
		self.ParseIgnore()
		if self.ParseLiteral('<!['):
			self.ParseIgnoreSectContents()
			self.ParseRequiredLiteral(']]>',"[64] ignoreSectContents")
			self.ParseIgnore()
		
	def ParseIgnore(self):
		"""[65] Ignore: parses a run of characters in an ignored section.
		
		This method returns no data."""
		while IsChar(self.theChar):
			if self.theChar=='<' and self.ParseLiteral('<!['):
				self.BuffText(u'<![')
				break
			elif self.theChar==']' and self.ParseLiteral(']]>'):
				self.BuffText(u']]>')
				break
			else:
				self.NextChar()
			
	def ParseCharRef(self,gotLiteral=False):
		"""[66] CharRef: parses a character reference.
		
		If *gotLiteral* is True the method assumes that the leading '&' literal
		has already been parsed.

		The method returns a unicode string containing the character referred
		to."""
		production="[66] CharRef"
		if not gotLiteral:
			self.ParseRequiredLiteral('&',production)
		self.ParseRequiredLiteral('#',production)
		if self.ParseLiteral('x'):
			qualifier='x'
			digits=self.ParseRequiredHexDigits(production)
			data=unichr(int(digits,16))
		else:
			qualifier=''
			digits=self.ParseRequiredDecimalDigits(production)
			data=unichr(int(digits))
		self.ParseRequiredLiteral(';',production)
		if self.refMode==XMLParser.RefModeInDTD:
			raise XMLForbiddenEntityReference("&#%s%s; forbidden by context"%(qualifier,digits))
		elif self.refMode==XMLParser.RefModeAsAttributeValue:
			data="&#%s%s;"%(qualifier,digits)
		elif not IsChar(data):
			raise XMLWellFormedError("[66] CharRef: illegal reference to non-Char &#%s%s;"%(qualifier,digits))
		return data
						
	def ParseReference(self):
		"""[67] Reference: parses a reference.
		
		This method returns any data parsed as a result of the reference.  For a
		character reference this will be the character referred to.  For a
		general entity the data returned will depend on the parsing context. For
		more information see :py:meth:`ParseEntityRef`."""
		self.ParseRequiredLiteral('&',"[67] Reference")
		if self.theChar=='#':
			return self.ParseCharRef(True)
		else:
			return self.ParseEntityRef(True)
		
	def ParseEntityRef(self,gotLiteral=False):
		"""[68] EntityRef: parses a general entity reference.
		
		If *gotLiteral* is True the method assumes that the leading '&' literal
		has already been parsed.
		
		This method returns any data parsed as a result of the reference.  For
		example, if this method is called in a context where entity references
		are bypassed then the string returned will be the literal characters
		parsed, e.g., "&ref;".

		If the entity reference is parsed successfully in a context where Entity
		references are recognized, the reference is looked up according to the
		rules for validating and non-validating parsers and, if required by the
		parsing mode, the entity is opened and pushed onto the parser so that
		parsing continues with the first character of the entity's replacement
		text.
		
		A special case is made for the predefined entities.  When parsed in a
		context where entity references are recognized these entities are
		expanded immediately and the resulting character returned.  For example,
		the entity &amp; returns the '&' character instead of pushing an entity
		with replacement text '&#38;'.
		
		Inclusion of an unescaped & is common so when we are not checking well-
		formedness we treat '&' not followed by a name as if it were '&amp;'.
		Similarly we are generous about the missing ';'."""
		production="[68] EntityRef"
		if not gotLiteral:
			self.ParseRequiredLiteral('&',production)
		if self.dontCheckWellFormedness:
			name=self.ParseName()
			if not name:
				return '&'
		else:
			name=self.ParseRequiredName(production)
		if self.dontCheckWellFormedness:
			self.ParseLiteral(';')
		else:
			self.ParseRequiredLiteral(';',production)
		if self.refMode==XMLParser.RefModeInEntityValue:
			return "&%s;"%name
		elif self.refMode in (XMLParser.RefModeAsAttributeValue,XMLParser.RefModeInDTD):
			raise XMLForbiddenEntityReference("&%s; forbidden by context"%name)
		else:
			data=self.LookupPredefinedEntity(name)
			if data is not None:
				return data
			else:
				e=None
				if self.dtd:
					e=self.dtd.GetEntity(name)
					if self.declaration and self.declaration.standalone and e.entity is not self.docEntity:
						self.ValidityError("Standalone Document Declaration: reference to entity %s not allowed (externally defined)"%e.GetName())
				if e is not None:
					e.Open()
					self.PushEntity(e)
					return ''
				else:
					self.WellFormednessError(production+": Undeclared general entity %s"%name)
	
	def LookupPredefinedEntity(self,name):
		"""Utility function used to look up pre-defined entities, e.g., "lt"
		
		This method can be overridden by variant parsers to implement other pre-defined
		entity tables."""
		return XMLParser.PredefinedEntities.get(name,None)
		
	def ParsePEReference(self,gotLiteral=False):
		"""[69] PEReference: parses a parameter entity reference.
		
		If *gotLiteral* is True the method assumes that the initial '%' literal
		has already been parsed.
		
		This method returns any data parsed as a result of the reference.  Normally
		this will be an empty string because the method is typically called in
		contexts where PEReferences are recognized.  However, if this method is
		called in a context where PEReferences are not recognized the returned
		string will be the literal characters parsed, e.g., "%ref;"

		If the parameter entity reference is parsed successfully in a context
		where PEReferences are recognized, the reference is looked up according
		to the rules for validating and non-validating parsers and, if required
		by the parsing mode, the entity is opened and pushed onto the parser so
		that parsing continues with the first character of the entity's
		replacement text."""
		production="[69] PEReference"
		if not gotLiteral:
			self.ParseRequiredLiteral('%',production)
		name=self.ParseRequiredName(production)
		self.ParseRequiredLiteral(';',production)
		if self.refMode in (XMLParser.RefModeNone,XMLParser.RefModeInContent,
			XMLParser.RefModeInAttributeValue,XMLParser.RefModeAsAttributeValue):
			return "%%%s;"%name
		else:
			if self.noPERefs:
				self.WellFormednessError(production+": PE referenced in Internal Subset, %%%s;"%name)
			if self.dtd:
				e=self.dtd.GetParameterEntity(name)
				if self.declaration and self.declaration.standalone and e.entity is not self.docEntity:
					self.ValidityError("Standalone Document Declaration: reference to entity %s not allowed (externally defined)"%e.GetName())
			else:
				e=None
			if e is None:
				self.WellFormednessError(production+": Undeclared parameter entity %s"%name)
			if self.refMode==XMLParser.RefModeInEntityValue:
				# Parameter entities are fed back into the parser somehow
				e.Open()
				self.PushEntity(e)
			elif self.refMode==XMLParser.RefModeInDTD:
				e.OpenAsPE()
				self.PushEntity(e)
			return ''
	
	def ParseEntityDecl(self,gotLiteral=False):
		"""[70] EntityDecl: parses an entity declaration.
		
		Returns an instance of either :py:class:`XMLGeneralEntity` or
		:py:class:`XMLParameterEntity` depending on the type of entity parsed. 
		If *gotLiteral* is True the method assumes that the leading '<!ENTITY'
		literal has already been parsed."""
		production="[70] EntityDecl"
		if not gotLiteral:
			self.ParseRequiredLiteral('<!ENTITY',production)
		dEntity=self.entity
		xEntity=self.GetExternalEntity()
		self.ParseRequiredS(production)
		if self.theChar=='%':
			e=self.ParsePEDecl(True)
		else:
			e=self.ParseGEDecl(True)
		if e.IsExternal():
			# Resolve the external ID relative to xEntity
			e.location=self.ResolveExternalID(e.definition,xEntity)
		if self.dtd:
			e.entity=dEntity
			self.dtd.DeclareEntity(e)
		return e
		
	def ParseGEDecl(self,gotLiteral=False):
		"""[71] GEDecl: parses a general entity declaration.
		
		Returns an instance of :py:class:`XMLGeneralEntity`.  If *gotLiteral* is
		True the method assumes that the leading '<!ENTITY' literal *and the
		required S* have already been parsed."""
		production="[71] GEDecl"
		dEntity=self.entity
		ge=XMLGeneralEntity()
		if not gotLiteral:
			self.ParseRequiredLiteral('<!ENTITY',production)
			self.ParseRequiredS(production)
		ge.name=self.ParseRequiredName(production)
		self.ParseRequiredS(production)
		self.ParseEntityDef(ge)
		self.ParseS()
		self.CheckPEBetweenDeclarations(dEntity)
		self.ParseRequiredLiteral('>',production)
		return ge
		
	def ParsePEDecl(self,gotLiteral=False):
		"""[72] PEDecl: parses a parameter entity declaration.
		
		Returns an instance of :py:class:`XMLParameterEntity`.  If *gotLiteral*
		is True the method assumes that the leading '<!ENTITY' literal *and the
		required S* have already been parsed."""
		production="[72] PEDecl"
		dEntity=self.entity
		pe=XMLParameterEntity()
		if not gotLiteral:
			self.ParseRequiredLiteral('<!ENTITY',production)
			self.ParseRequiredS(production)
		self.ParseRequiredLiteral('%',production)
		self.ParseRequiredS(production)
		pe.name=self.ParseRequiredName(production)
		self.ParseRequiredS(production)
		self.ParsePEDef(pe)
		self.ParseS()
		self.CheckPEBetweenDeclarations(dEntity)
		self.ParseRequiredLiteral('>',production)
		return pe
			
	def ParseEntityDef(self,ge):
		"""[73] EntityDef: parses the definition of a general entity.
		
		The general entity being parsed must be passed in *ge*.  This method
		sets the :py:attr:`XMLGeneralEntity.definition` and
		:py:attr:`XMLGeneralEntity.notation` fields from the parsed entity
		definition."""
		ge.definition=None
		ge.notation=None
		if self.theChar=='"' or self.theChar=="'":
			ge.definition=self.ParseEntityValue()
		elif self.theChar=='S' or self.theChar=='P':
			ge.definition=self.ParseExternalID()
			s=self.ParseS()
			if s:
				if self.ParseLiteral('NDATA'):
					ge.notation=self.ParseNDataDecl(True)
				else:
					self.BuffText(s)
		else:
			self.WellFormednessError("[73] EntityDef: Expected EntityValue or ExternalID")
		
	def ParsePEDef(self,pe):
		"""[74] PEDef: parses a parameter entity definition.
		
		The parameter entity being parsed must be passed in *pe*.  This method
		sets the :py:attr:`XMLParameterEntity.definition` field from the parsed
		parameter entity definition."""
		pe.definition=None
		if self.theChar=='"' or self.theChar=="'":
			pe.definition=self.ParseEntityValue()
		elif self.theChar=='S' or self.theChar=='P':
			pe.definition=self.ParseExternalID()
		else:
			self.WellFormednessError("[74] PEDef: Expected EntityValue or ExternalID")
				
	def ParseExternalID(self,allowPublicOnly=False):
		"""[75] ExternalID: parses an external ID returning an XMLExternalID instance.
		
		An external ID must have a SYSTEM literal, and may have a PUBLIC identifier.
		If *allowPublicOnly* is True then the method will also allow an external
		identifier with a PUBLIC identifier but no SYSTEM literal.  In this mode
		the parser behaves as it would when parsing the production::

			(ExternalID | PublicID) S?"""
		if allowPublicOnly:
			production="[75] ExternalID | [83] PublicID"
		else:
			production="[75] ExternalID"
		if self.ParseLiteral('SYSTEM'):
			pubID=None
			allowPublicOnly=False
		elif self.ParseLiteral('PUBLIC'):
			self.ParseRequiredS(production)
			pubID=self.ParsePubidLiteral()
		else:
			self.WellFormednessError(production+": Expected 'PUBLIC' or 'SYSTEM'")
		if (allowPublicOnly):
			if self.ParseS():
				if self.theChar=='"' or self.theChar=="'":
					systemID=self.ParseSystemLiteral()
				else:
					# we've consumed the trailing S, not a big deal
					systemID=None
			else:
				# just a PublicID
				systemID=None
		else:
			self.ParseRequiredS(production)
			systemID=self.ParseSystemLiteral()
		# catch for dontCheckWellFormedness ??
		return XMLExternalID(pubID,systemID)
	
	def ResolveExternalID(self,externalID,entity=None):
		"""[75] ExternalID: resolves an external ID, returning a URI reference.
		
		Returns an instance of :py:class:`pyslet.rfc2396.URI` or None if the
		external ID cannot be resolved.
		
		*entity* can be used to force the resolution of relative URI to be
		relative to the base of the given entity.  If it is None then the
		currently open external entity (where available) is used instead.
		
		The default implementation simply calls
		:py:meth:`XMLExternalID.GetLocation` with the entities base URL and
		ignores the public ID.  Derived parsers may recognize public identifiers
		and resolve accordingly."""
		base=None
		if entity is None:
			entity=self.GetExternalEntity()
		if entity:
			base=entity.location
		return externalID.GetLocation(base)
		
	def ParseNDataDecl(self,gotLiteral=False):
		"""[76] NDataDecl: parses an unparsed entity notation reference.
		
		Returns the name of the notation used by the unparsed entity as a string
		without the preceding 'NDATA' literal."""
		production="[76] NDataDecl"
		if not gotLiteral:
			self.ParseRequiredS(production)
			self.ParseRequiredLiteral('NDATA',production)
		self.ParseRequiredS(production)
		return self.ParseRequiredName(production)

	def ParseTextDecl(self,gotLiteral=False):
		"""[77] TextDecl: parses a text declataion.
		
		Returns an XMLTextDeclaration instance."""
		production="[77] TextDecl"
		if not gotLiteral:
			self.ParseRequiredLiteral("<?xml",production)
		self.ParseRequiredS(production)
		if self.ParseLiteral('version'):
			version=self.ParseVersionInfo(True)
			encoding=self.ParseEncodingDecl()
		elif self.ParseLiteral('encoding'):
			version=None
			encoding=self.ParseEncodingDecl(True)
		else:
			self.WellFormednessError(production+": Expected 'version' or 'encoding'")
		self.ParseS()
		self.ParseRequiredLiteral('?>',production)
		return XMLTextDeclaration(version,encoding)
		
	def ParseEncodingDecl(self,gotLiteral=False):
		"""[80] EncodingDecl: parses an encoding declaration
		
		Returns the declaration name without the enclosing quotes.  If *gotLiteral* is
		True then the method assumes that the literal 'encoding' has already been parsed."""
		production="[80] EncodingDecl"
		if not gotLiteral:
			self.ParseRequiredS(production)
			self.ParseRequiredLiteral('encoding',production)
		self.ParseEq(production)
		q=self.ParseQuote()
		encName=self.ParseEncName()
		if not encName:
			self.WellFormednessError("Expected EncName")
		self.ParseQuote(q)
		return encName

	def ParseEncName(self):
		"""[81] EncName: parses an encoding declaration name
		
		Returns the encoding name as a string or None if no valid encoding name
		start character was found."""
		name=[]
		if EncNameStartCharClass.Test(self.theChar):
			name.append(self.theChar)
			self.NextChar()
			while EncNameCharClass.Test(self.theChar):
				name.append(self.theChar)
				self.NextChar()
		if name:
			return string.join(name,'')
		else:
			return None
			
	def ParseNotationDecl(self,gotLiteral=False):
		"""[82] NotationDecl: Parses a notation declaration matching production NotationDecl
		
		This method assumes that the literal '<!NOTATION' has already been parsed.  It
		declares the notation in the :py:attr:`dtd`."""
		production="[82] NotationDecl"
		dEntity=self.entity
		if not gotLiteral:
			self.ParseRequiredLiteral("<!NOTATION",production)
		self.ParseRequiredS(production)
		name=self.ParseRequiredName(production)
		self.ParseRequiredS(production)
		xID=self.ParseExternalID(True)
		self.ParseS()
		self.CheckPEBetweenDeclarations(dEntity)
		self.ParseRequiredLiteral('>')
		if self.dtd:
			self.dtd.DeclareNotation(XMLNotation(name,xID))

	def ParsePublicID(self):
		"""[83] PublicID: Parses a literal matching the production for PublicID.
		
		The literal string is returned without the PUBLIC prefix or the
		enclosing quotes."""
		production="[83] PublicID"
		self.ParseRequiredLiteral('PUBLIC',production)
		self.ParseRequiredS(production)
		return self.ParsePubidLiteral()		
					

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


def OptionalAppend(itemList,newItem):
	"""A convenience function which appends newItem to itemList if newItem is not None""" 
	if newItem is not None:
		itemList.append(newItem)

