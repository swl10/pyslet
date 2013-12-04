#! /usr/bin/env python

import string, types
from StringIO import StringIO
import urlparse, os, os.path
from sys import maxunicode
import codecs, random
from types import *
from copy import copy
import warnings

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
	return mimetype in XML_MIMETYPES
	
class XMLError(Exception):
	"""Base class for all exceptions raised by this module."""
	pass

class DuplicateXMLNAME(XMLError):
	"""Raised by :py:func:`MapClassElements` when attempting to declare two classes with the same XML name."""
	pass
	
class XMLAttributeSetter(XMLError): pass
class XMLForbiddenEntityReference(XMLError): pass
class XMLMissingResourceError(XMLError): pass
class XMLMissingLocationError(XMLError): pass
class XMLMixedContentError(XMLError): pass
class XMLParentError(XMLError): pass
class XMLUnimplementedError(XMLError): pass
class XMLUnexpectedError(XMLError): pass
class XMLUnexpectedHTTPResponse(XMLError): pass
class XMLUnsupportedSchemeError(XMLError): pass

class XMLFatalError(XMLError): pass
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
			q='"';qStr='&#x22;'
		elif '"' in src:
			q="'";qStr='&#x27;'
		else:
			q='"';qStr='&#x22;'
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
	

class Node(object):
	def __init__(self,parent):
		"""Base class for Element and Document shared attributes.
		
		XML documents are defined hierarchicaly, each element has a parent
		which is either another element or an XML document."""
		self.parent=parent
		"""The parent of this element, for XML documents this attribute is used
		as a sentinel to simplify traversal of the hierarchy and is set to
		None."""

	def GetChildren(self):
		"""Returns an iterator over this object's children."""
		raise NotImplementedError
	
	@classmethod
	def GetElementClass(cls,name):
		"""Returns a class object suitable for representing element *name*
		
		name is a unicode string representing the element name.
		
		The default implementation returns None - for elements this has the
		effect of deferring the call to the parent document (where this method
		is overridden to return :py:class:`Element`).

		This method is called immediately prior to :py:meth:`ChildElement` and
		(when applicable) :py:meth:`GetChildClass`.
		
		The real purpose of this method is to allow an element class to directly
		control the way the name of a child element maps to a class to represent
		it.  You would normally override this method in the :py:class:`Document`
		to map element names to classes but in some cases you may want to tweek
		the mapping at the individual element level.  For example, if the same
		element name is used for two different purposes in the same XML
		document, although confusing, this is allowed in XML schema."""
		return None

	def GetChildClass(self,stagClass):
		"""Returns the element class implied by the STag for stagClass in this context.
		
		This method is only called when the :py:attr:`XMLParser.sgmlOmittag`
		option is in effect.  It is called prior to :py:meth:`ChildElement`
		below and gives the context (the parent element or document) a chance to
		modify the child element that will be created (or reject it out-right,
		by returning None).
		
		For well-formed XML documents the default implementation is sufficient
		as it simply returns *stagClass*.
		
		The XML parser may pass None for *stagClass* indicating that PCDATA has
		been found in element content.  This method should return the first
		child element that may contain (directly or indirectly) PCDATA or None
		if no children may contain PCDATA (or SGML-style omittag is not
		supported)"""
		return stagClass

	def ChildElement(self,childClass,name=None):
		"""Returns a new child of the given class attached to this object.
		
		-	childClass is a class (or callable) used to create a new instance
			of :py:class:`Element`.
		
		-	name is the name given to the element (by the caller).  If no name
			is given then the default name for the child is used.  When the
			child returned is an existing instance, name is ignored."""
		raise NotImplementedError
			
	def ProcessingInstruction(self,target,instruction=''):
		"""Abstract method for handling processing instructions encountered by
		the parser while parsing this object's content.

		By default, processing instructions are ignored."""
		pass
		

class Document(Node):
	"""Base class for all XML documents."""
	
	def __init__(self, root=None, baseURI=None, reqManager=None, **args):
		"""Initialises a new Document from optional keyword arguments.
		
		With no arguments, a new Document is created with no baseURI
		or root element.
		
		If root is a class object (descended from Element) it is used
		to create the root element of the document.
		
		If root is an orphan instance of Element (i.e., it has no parent) is is
		used as the root element of the document and its
		:py:meth:`Element.AttachToDocument` method is called.
		
		baseURI can be set on construction (see SetBase) and a reqManager object
		can optionally be passed for managing and http(s) connections.
		"""
		Node.__init__(self,None)
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
			if isinstance(root,Element):
				# created from an instance
				if root.parent:
					raise ValueError("Element must be an orphan in Document constructor")
				self.root=root
				root.parent=self
				self.root.AttachToDocument(self)
			elif not issubclass(root,Element):
				raise ValueError
			else:
				self.root=root(self)
		self.SetBase(baseURI)
		self.idTable={}

	def GetChildren(self):
		"""If the document has a root element it is returned in a single item list,
		otherwise an empty list is returned."""
		if self.root:
			yield self.root

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
		from pyslet.xml20081126.parser import XMLParser
		return XMLParser(entity)
	
	@classmethod				
	def GetElementClass(cls,name):
		"""Returns a class object suitable for representing name
		
		name is a unicode string representing the element name.
		
		The default implementation returns Element."""
		return Element

	def ChildElement(self,childClass,name=None):
		"""Creates the root element of the given document.
		
		If there is already a root element it is detached from the document
		first using :py:meth:`Element.DetachFromDocument`."""
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
		Element.ValidationError."""
		raise XMLValidityError("%s (in %s)"%(msg,element.xmlname))
		
	def RegisterElement(self,element):
		if element.id in self.idTable:
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
		while idStr in self.idTable:
			if not idExtra:
				idExtra=random.randint(0,0xFFFF)
			idStr='%s-%X'%(baseStr,idExtra)
			idExtra=idExtra+1
		return idStr

	def Read(self,src=None,**args):
		"""Reads this document, parsing it from a source stream.

		With no arguments the document is read from the :py:attr:`baseURI` which
		must have been specified on construction or with a call to the
		:py:meth:`SetBase` method.

		You can override the document's baseURI by passing a value for *src*
		which may be an instance of :py:class:`XMLEntity` or an object that can
		be passed as a valid source to its constructor."""
		if src:
			# Read from this stream, ignore baseURI
			if isinstance(src,XMLEntity):
				self.ReadFromEntity(src)
				if src.location is not None and self.baseURI is None:
					# take our baseURI from the entity
					self.baseURI=self.SetBase(src.location)
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
		"""Creates the Document.
		
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
	
	def GenerateXML(self,escapeFunction=EscapeCharData,tab='\t'):
		if tab:
			 yield u'<?xml version="1.0" encoding="UTF-8"?>'
		else:
			yield u'<?xml version="1.0" encoding="UTF-8"?>\n'
		if self.root:
			for s in self.root.GenerateXML(escapeFunction,'',tab,root=True):
				yield s
	
	def WriteXML(self,writer,escapeFunction=EscapeCharData,tab='\t'):
		for s in self.GenerateXML(escapeFunction,tab):
			writer.write(s)
	
	def Update(self,**args):
		"""Updates the Document.
		
		Update outputs the document as an XML stream.  The stream is written
		to the baseURI which must already exist!  Currently only documents
		with file type baseURIs are supported."""
		if self.baseURI is None:
			raise XMLMissingLocationError
		elif isinstance(self.baseURI,FileURL):
			fPath=self.baseURI.GetPathname()
			if not os.path.isfile(fPath):
				raise XMLMissingResourceError(fPath)
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
		:py:class:`Document`
	
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
	if c:
		c=ord(c)
		if c>0x20:
			return False
		else:
			return c==0x20 or c==0x9 or c==0xA or c==0xD
	return False
	
def IsWhiteSpace(data):
	"""Tests if every character in *data* matches production [3] S"""
	for c in data:
		if not IsS(c):
			return False
	return True

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
	if c<=u"z":
		if c>=u"a":
			return True
		elif c<=u"Z":
			if c>=u"A":
				return True
			else:
				return c==u":"
		else:
			return c==u"_"
	else:
		return NameStartCharClass.Test(c)
	
NameCharClass=CharClass(NameStartCharClass, u'-', u'.', (u'0',u'9'),
	u'\xb7', (u'\u0300',u'\u036f'), (u'\u203f',u'\u2040'))

def IsNameChar(c):
	"""Tests if a single character *c* matches production [4a] NameChar"""
	# This is called a lot, so we take a few short cuts for commone cases
	if c:
		if c<=u"z":
			if c>=u"a":
				return True
			elif c<=u"Z":
				if c>=u"A":
					return True
				elif c<=u"9":
					if c>=u"0":
						return True
					else:
						return c in "-."
				else:
					return c==u":"
			else:
				return c==u"_"
		else:
			return NameCharClass.Test(c)
	return False
		
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
		

class XMLDTD(object):
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
		"""A dictionary of :py:class:`ElementType` definitions keyed on the
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
		
		*eType* is an :py:class:`ElementType` instance containing the element
		definition."""
		eList=self.elementList.get(eType.name,None)
		if eList is None:
			self.elementList[eType.name]=eType
	
	def GetElementType(self,elementName):
		"""Looks up an element type definition.
		
		*elementName* is the name of the element type to look up
		
		The method returns an instance of :py:class:`ElementType` or
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
		if not attributeDef.name in aList:
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
		

class XMLTextDeclaration(object):

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


class ElementType(object):

	Empty=0				#: Content type constant for EMPTY
	Any=1				#: Content type constant for ANY
	Mixed=2				#: Content type constant for mixed content
	ElementContent=3	#: Content type constant for element content
	SGMLCDATA=4			#: Additional content type constant for SGML CDATA
	
	def __init__(self):
		"""An object for representing element type definitions."""
		self.entity=None	#: The entity in which this element was declared
		self.name=None		#: The name of this element
		self.contentType=ElementType.Empty
		"""The content type of this element, one of the constants defined above."""
		self.contentModel=None
		"""A :py:class:`XMLContentParticle` instance which contains the element's
		content model or None in the case of EMPTY or ANY declarations."""
		self.particleMap=None
		"""A mapping used to validate the content model during parsing.  It maps
		the name of the first child element found to a list of
		:py:class:`XMLNameParticle` instances that can represent it in the
		content model.  For more information see
		:py:attr:`XMLNameParticle.particleMap`."""

	def BuildModel(self):
		"""Builds internal strutures to support model validation."""
		if self.contentType==self.ElementContent:
			self.particleMap={}
			if not self.contentModel.SeekParticles(self.particleMap):
				# the entire content model is optional so add ETag mapping
				self.particleMap['']=None
			exitParticles={'':None}
			self.contentModel.BuildParticleMaps(exitParticles)
		elif self.contentType==self.Mixed:
			self.particleMap={}
			self.contentModel.SeekParticles(self.particleMap)
			self.particleMap['']=None
			# always optional repeatable
			self.contentModel.BuildParticleMaps(self.particleMap)
	
	def IsDeterministic(self):
		"""Tests if the content model is deterministic.
		
		For degenerates cases (elements declared with ANY or EMPTY) the method
		always returns True."""
		if self.contentType==self.ElementContent or self.contentType==self.Mixed:
			return self.contentModel.IsDeterministic(self.particleMap)
		else:
			return True

# Constants for backwards compatibility
XMLEmpty=ElementType.Empty
XMLMixedContent=ElementType.Mixed
ElementContent=ElementType.ElementContent
SGMLCDATA=ElementType.SGMLCDATA


class Element(Node):
	"""Basic class that represents all XML elements.
	
	Some aspects of the element's XML serialisation behaviour are controlled by
	special class attributes that can be set on derived classes.
	
	XMLNAME
		the default name of the element the class represents.
	
	XMLCONTENT
		the default content model of the element; one of the
		:py:class:`ElementType` constants.
	
	ID
		the name of the ID attribute if the element has a unique ID. With this
		class attribute set, ID handling is automatic (see :py:meth:`SetID` and
		:py:attr:`id` below).

	By default, attributes are simply stored as strings mapped in an internal
	dictionary.  It is often more useful to map XML attributes on to python
	attributes, parsing and validating their values to python objects.  This
	mapping can be provided using class attributes of the form XMLATTR_aname
	where aname is the name of the attribute as it would appear in the XML
	element start or empty element tag.

	XMLATTR_aname=<string>
			
		This form creates a simple mapping from the XML attribute 'aname' to a
		python attribute with a defined name.  For example, you might want to
		create a mapping like this to avoid a python reserved word::
		
			XMLATTR_class="styleClass"
			
		This allows XML elements like this::
		
			<element class="x"/>
		
		To be parsed into python objects that behave like this::
		
			element.styleClass=="x"		# True
		
		If an instance is missing a python attribute corresponding to a defined
		XML attribute, or it's value has been set to None, then the XML
		attribute is omitted from the element's tag when generating XML output.
		 
	XMLATTR_aname=(<string>, decodeFunction, encodeFunction)

		More complex attributes can be handled by setting XMLATTR_aname to a
		tuple.  The first item is the python attribute name (as above); the
		*decodeFunction* is a simple callable that takes a string argument and
		returns the decoded value of the attribute and the *encodeFunction*
		performs the reverse transformation.

		The encode/decode functions can be None to indicate a no-operation.
		
		For example, you might want to create an integer attribute using
		something like::
		
			<!-- source XML -->
			<element apples="5"/>
			
			# class attribute definition
			XMLATTR_apples=('nApples',int,unicode)
			
			# resulting object behaves like this...
			element.nApples==5		# True
			
	XMLATTR_aname=(<string>, decodeFunction, encodeFunction, type)
	
		When XML attribute values are parsed from tags the optional
		*type* component of the tuple descriptor can be used to indicate
		a multi-valued attribute (for example, XML attributes defined
		using one of the plural forms, IDREFS, ENTITIES and NMTOKENS). 
		If the *type* value is not None then the XML attribute value is
		first split by white-space, as per the XML specification, and
		then the decode function is applied to each resulting component.
		 The instance attribute is then set depending on the value of
		*type*:
		
		types.ListType
		
			The instance attribute becomes a list, for example::
			
				<!-- source XML -->
				<element primes="2 3 5 7"/>
				
				# class attribute definition
				XMLATTR_primes=('primes',int,unicode)
				
				# resulting object behaves like this...
				element.primes==[2,3,5,7]		# True

		types.DictType
		
			The instance attribute becomes a dictionary mapping parsed values on
			to their frequency, for example::
		
				<!-- source XML -->
				<element fruit="apple pear orange pear"/>
				
				# class attribute definition
				XMLATTR_fruit=('fruit',None,None,types.DictType)
				
				# resulting object behaves like this...
				element.fruit=={'apple':1, 'orange':1, 'pear':2}		# True
		  
			In this case, the decode function (if given) must return a hashable
			object.
	
		When creating XML output the reverse transformations are
		performed using the encode functions and the type (plain, list
		or dict) of the attribute's current value.  The declared
		multi-valued type is ignored. For dictionary values the order of
		the output values may not be the same as the order originally
		read from the XML input.
		
		Warning:  Empty lists and dictionaries result in XML attribute values
		which are present but with empty strings.  If you wish to omit these
		attributes in the output XML you must set the attribute value to None in
		the instance.

	XMLAMAP
	XMLARMAP
	
		Internally, the XMLATTR_* descriptors are parsed into two mappings.
		The XMLAMAP maps XML attribute names onto a tuple of:
		
			(<python attribute name>, decodeFunction, type)
		
		The XMLARMAP maps python attribute names onto a tuple of: 

			(<xml attribute name>, encodeFunction)

		The mappings are created automatically as needed.
		
	For legacy reasons, the multi-valued rules can also be invoked by setting an
	instance member to either a list or dictionary prior to parsing the instance
	from XML (e.g., in a constructor).
	
	XML attribute names may contain many characters that are not legal in Python
	method names and automated attribute processing is not supported for these
	attributes.  In practice, the only significant limitation is the colon.  The
	common xml-prefixed attributes such as xml:lang are handled using special
	purposes methods."""

	XMLCONTENT=ElementType.Mixed		#: for consistency with the behaviour of the default methods we claim to be mixed content
	
	def __init__(self,parent,name=None):
		Node.__init__(self,parent)
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

	def __nonzero__(self):
		# All elements are considered non-zero; we implement this to reduce spurious calls
		# to __getattr__
		return True
		
	def SetXMLName(self,name):
		self.xmlname=name
	
	def GetXMLName(self):
		return self.xmlname
	
	def Reset(self,resetAttributes=False):
		"""Clears all attributes and (optional) children."""
		if resetAttributes:
			self._attrs={}
		for child in self._children:
			if isinstance(child,Element):
				child.DetachFromDocument()
				child.parent=None
		self._children=[]
		
	def GetDocument(self):
		"""Returns the document that contains the element.
		
		If the element is an orphan, or is the descendent of an orphan
		then None is returned."""
		if self.parent:
			if isinstance(self.parent,Document):
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
		
	def MangleAttributeName(self,name):
		"""Returns a mangled attribute name, used when setting attributes.
		
		If name cannot be mangled, None is returned."""
		return "XMLATTR_"+name
		
	def UnmangleAttributeName(self,mName):
		"""Returns an unmangled attribute name, used when getting attributes.

		If mName is not a mangled name, None is returned."""
		if mName.startswith('XMLATTR_'):
			return mName[8:]
		else:
			return None
	
	def _ReMap(self):
		aMap={}
		arMap={}
		nop=lambda x:x
		for mName in dir(self.__class__):
			name=self.UnmangleAttributeName(mName)
			if name:
				setter=getattr(self.__class__,mName)
				if type(setter) in StringTypes:
					# use simple attribute assignment
					attrName,encode,decode,vtype=setter,None,None,None
				elif type(setter) is TupleType:
					if len(setter)==3:
						attrName,decode,encode=setter
						vtype=None
					elif len(setter)==4:
						attrName,decode,encode,vtype=setter
					else:
						raise XMLAttributeSetter("bad XMLATTR_ definition: %s attribute of %s"%(name,self.__class__.__name__))
				else:
					raise XMLAttributeSetter("setting %s attribute of %s"%(name,self.__class__.__name__))
				if encode is None:
					encode=nop
				if decode is None:
					decode=nop
				if vtype not in (types.ListType,types.DictType,None):
					raise XMLAttributeSetter("Legacy XMLATTR_ definition: %s attribute of %s"%(name,self.__class__.__name__))
				aMap[name]=(attrName,decode,vtype)
				arMap[attrName]=(name,encode)
		setattr(self.__class__,"XMLAMAP",aMap)
		setattr(self.__class__,"XMLARMAP",arMap)
		
	def _ARMap(self):
		if "XMLARMAP" not in self.__class__.__dict__:
			self._ReMap()
		return self.__class__.XMLARMAP			 
	
	def _AMap(self):
		if "XMLAMAP" not in self.__class__.__dict__:
			self._ReMap()
		return self.__class__.XMLAMAP			 
			
	def __getattr__(self,name):
		"""Some element specifications define large numbers of optional
		attributes and it is inconvenient to write constructors to initialise
		these members in each instance and possibly wasteful of memory if a
		document contains large numbers of such elements.
		
		To obviate the need for optional attributes to be present in every
		instance this method will look up *name* in the reverse map and,
		if present, it returns None."""
		# print "Looking for %s in %s"%(name,self.__class__.__name__)
		# import traceback;traceback.print_stack()
		if name in self._ARMap():
			return None
		else:
			raise AttributeError("%s has no attribute %s"%(self.__class__.__name__,name))
	
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
		arMap=self._ARMap()
		for attrName,desc in arMap.items():
			name,encode=desc
			value=getattr(self,attrName,None)
			if type(value) is ListType:
				value=string.join(map(encode,value),' ')
			elif type(value) is DictType:
				lValue=[]
				for key,freq in value.items():
					 v=encode(key)
					 lValue=lValue+[encode(key)]*freq
				value=string.join(sorted(lValue),' ')
			elif value is not None:
				value=encode(value)
			if value is not None:
				attrs[name]=value		
		return attrs

	def SetAttribute(self,name,value):
		"""Sets the value of an attribute.
		
		If *value* is None then the attribute is removed or, if an
		XMLATTR_ mapping is in place its value is set to an empty list,
		dictionary or None as appropriate."""
		aMap=self._AMap()
		if name in aMap:
			attrName,decode,vType=aMap[name]
			if vType is ListType:
				if value is None:
					value=[]
				else:
					value=value.split()
				setattr(self,attrName,map(decode,value))
			elif vType is DictType:
				if value is None:
					value=[]
				else:
					value=value.split()
				dValue={}
				for iv in map(decode,value):
					dValue[iv]=dValue.get(iv,0)+1
				setattr(self,attrName,dValue)			
			else:
				x=getattr(self,attrName,None)
				if type(x) in (ListType,DictType):
					print "Problem setting %s in %s: single value will overwrite List or Dict"%(repr(name),repr(self.__class__.__name__))
					# print self.GetDocument()
				if value is None:
					setattr(self,attrName,None)
				else:
					setattr(self,attrName,decode(value))
		elif hasattr(self.__class__,'ID') and name==self.__class__.ID:
			self.SetID(value)
		else:
			if value is None:
				if name in self._attrs:
					del self._attrs[name]
			else:
				self._attrs[name]=value
	
	def GetAttribute(self,name):
		"""Gets the value of a single attribute as a string.
		
		If the element has no attribute with *name* then KeyError is raised."""
		if name in self._attrs:
			return self._attrs[name]
		elif hasattr(self.__class__,'ID') and name==self.__class__.ID:
			return self.id
		else:
			aMap=self._AMap()
			if name in aMap:
				attrName,decode,vType=aMap[name]
				value=getattr(self,attrName,None)
			else:
				value=None
			if value is None:
				raise KeyError("Attribute value undefined: %s"%repr(name))
			arMap=self._ARMap()
			unusedName,encode=arMap[attrName]
			if type(value) is ListType:
				value=string.join(map(encode,value),' ')
			elif type(value) is DictType:
				lValue=[]
				for key,freq in value.items():
					 v=encode(key)
					 lValue=lValue+[encode(key)]*freq
				value=string.join(sorted(lValue),' ')
			else:
				value=encode(value)
			return value

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
		"""Returns an iterable of the element's children.
		
		This method iterates through the internal list of children.
		Derived classes with custom factory elements MUST override this
		method.

		Each child is either a string type, unicode string type or
		instance of Element (or a derived class thereof).  We do not
		represent comments, processing instructions or other
		meta-markup."""
		return iter(self._children)

	def GetCanonicalChildren(self):
		"""A wrapper for :py:meth:`GetChildren` that returns an iterable
		of the element's children canonicalized for white space.
		
		We check the current setting of xml:space, returning the same list of
		children as :py:meth:`GetChildren` if 'preserve' is in force.  Otherwise
		we remove any leading space and collapse all others to a single space
		character."""
		children=self.GetChildren()
		# If there are no children there is nothing to do, so we don't catch StopIteration.
		firstChild=children.next()
		e=self
		while isinstance(e,Element):
			spc=e.GetSpace()
			if spc is not None:
				if spc=='preserve':
					yield firstChild
					while True: yield children.next()
					# will raise StopIteration and terminate method
				else:
					break
			if hasattr(e.__class__,'SGMLCDATA'):
				yield firstChild
				while True: yield children.next()
			e=e.parent
		try:
			iChild=children.next()
		except StopIteration:
			# There was only one child
			if type(firstChild) in StringTypes:
				firstChild=CollapseSpace(firstChild)
# 				if len(firstChild)>1 and firstChild[-1]==u' ':
# 					# strip the trailing space from the only child - why do we do this?
# 					firstChild=firstChild[:-1]
			yield firstChild
			return
		# Collapse strings to a single string entry and collapse spaces
		data=[]
		if type(firstChild) in StringTypes:
			data.append(firstChild)
			sMode=True
		else:
			sMode=False
			yield firstChild
		while True:
			if type(iChild) in StringTypes:
				data.append(iChild)
			else:
				if data:
					dataChild=CollapseSpace(string.join(data,''),sMode)
					if not sMode or dataChild!=u' ':
						# ignore a leading space completely
						yield dataChild
					data=[]
				yield iChild
				sMode=False
			try:
				iChild=children.next()
				continue
			except StopIteration:
				if data:
					dataChild=CollapseSpace(string.join(data,''),sMode)
					if dataChild==u' ':
						# just white space, return empty string if we're the only child for consistency
						if sMode:
							yield u''
						else:
							# strip the whole last child
							return
					elif dataChild[-1]==u' ':
						# strip the trailing space form the last child
						dataChild=dataChild[:-1]
					yield dataChild
				return
		
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
		
		name is the name given to the element (by the caller).  If no
		name is given then the default name for the child is used.  When
		the child returned is an existing instance, name is ignored.
		
		The default implementation checks for a custom factory method and calls
		it if defined and does no further processing.  A custom factory method
		is a method of the form ClassName or an attribute that is being used to
		hold instances of this child.  The attribute must already exist and can
		be one of None (optional child, new child is created), a list (optional
		repeatable child, new child is created and appended) or an instance of
		childClass (required/existing child, no new child is created, existing
		instance returned).
		
		When no custom factory method is found the class hierarchy of
		*childClass* is enumerated and the search continues for factory methods
		corresponding to these parent classes.
		
		If no custom factory method is defined then the default
		processing simply creates an instance of child (if necessary)
		and attaches it to the internal list of children."""
		if self.IsEmpty():
			self.ValidationError("Unexpected child element",name)
		child=None
		factoryName=self._FindFactory(childClass)
		try:
			if factoryName:
				factory=getattr(self,factoryName)
				if type(factory) is MethodType:
					if factoryName!=childClass.__name__:
						child=factory(childClass)
					else:
						child=factory()
				elif type(factory) is NoneType:
					child=childClass(self)
					setattr(self,factoryName,child)
				elif type(factory) is ListType:
					child=childClass(self)
					factory.append(child)
				elif isinstance(factory,childClass):
					child=factory
				else:
					raise TypeError(factoryName,repr(factory),repr(childClass))
				if child is not None:
					if name:
						child.SetXMLName(name)
					return child
			# else fall through to the default processing...
			child=childClass(self)
			self._children.append(child)
			if name:
				child.SetXMLName(name)
			return child
		except TypeError:
			import traceback;traceback.print_exc()
			raise TypeError("Can't create %s in %s"%(childClass.__name__,self.__class__.__name__))
# 		if child is None:
# 			raise TypeError("ChildElement got None: %s in %s"%(childClass.__name__,self.__class__.__name__))
	
	def DeleteChild(self,child):
		"""Deletes the given child from this element's children.
		
		We follow the same factory conventions as for child creation except
		that an attribute pointing to a single child (of this class) will be
		replaced with None.  If a custom factory method is found then the
		corresponding Delete_ClassName method must also be defined."""
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
				# Single allowable child is replaced with None
				child.DetachFromDocument()
				child.parent=None
				setattr(self,factoryName,None)
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

		**Deprecated in favour of list(FindChildrenDepthFirst(childClass,False))**
		
		All matching children are added to childList.  If specifing a max number
		of matches then the incoming list must originally be empty to prevent
		early termination.

		Note that if max is None, the default, then all children of the given
		class are returned with the proviso that nested matches are not
		included.  In other words, if the model of childClass allows further
		elements of type childClass as children (directly or indirectly) then
		only the top-level match is returned.
		
		Effectively this method provides a depth-first list of children.  For
		example, to get all <div> elements in an HTML <body> you would have to
		recurse over the resulting list calling FindChildren again until the
		list of matching children stops growing.		
		"""
		warnings.warn("Element.FindChildren is deprecated, use FindChildrenDepthFirst instead", DeprecationWarning, stacklevel=3)
		if max is not None and len(childList)>=max:
			return
		for child in self.GetChildren():
			if isinstance(child,childClass):
				childList.append(child)
			elif isinstance(child,Element):
				child.FindChildren(childClass,childList,max)
			if max is not None and len(childList)>=max:
				break

	def FindChildrenBreadthFirst(self,childClass,subMatch=True,maxDepth=1000):
		"""A generator method that iterates over children of class
		*childClass* using a breadth first scan.
		
		*childClass* may also be a tuple as per the definition of the
		builtin isinstance function in python.
		
		If *subMatch* is True (the default) then matching elements are
		also scanned for nested matches.  If False, only the outer-most
		matching element is returned.
		
		*maxDepth* controls the depth of the scan with level 1
		indicating direct children only.  It must be a positive integer
		and defaults to 1000.

		Warning: to reduce memory requirements when searching large
		documents this method performs a two-pass scan of the element's
		children, i.e., :py:meth:`GetChildren` will be called twice.
		
		Given that XML documents tend to be broader than they are deep
		:py:meth:`FindChildrenDepthFirst` is a better method to use for
		general purposes."""
		maxDepth=maxDepth-1
		for child in self.GetChildren():
			if isinstance(child,childClass):
				yield child
		if maxDepth:
			for child in self.GetChildren():
				if isinstance(child,Element) and (subMatch or not isinstance(child,childClass)):
					for c in child.FindChildrenBreadthFirst(childClass,maxDepth):
						yield c

	def FindChildrenDepthFirst(self,childClass,subMatch=True,maxDepth=1000):
		"""A generator method that iterates over children of class
		*childClass* using a depth first scan.
		
		*childClass* may also be a tuple as per the definition of the
		builtin isinstance function in python.

		If *subMatch* is True (the default) then matching elements are
		also scanned for nested matches.  If False, only the outer-most
		matching element is returned.
		
		*maxDepth* controls the depth of the scan with level 1
		indicating direct children only.  It must be a positive integer
		and defaults to 1000."""
		maxDepth=maxDepth-1
		for child in self.GetChildren():
			if isinstance(child,childClass):
				yield child
				if not subMatch:
					continue
			if isinstance(child,Element) and maxDepth>0:
				for c in child.FindChildrenDepthFirst(childClass,maxDepth):
					yield c
				
	def FindParent(self,parentClass):
		"""Finds the first parent of class parentClass of this element.
		
		If this element has no parent of the given class then None is returned."""
		parent=self.parent
		while parent and not isinstance(parent,parentClass):
			if isinstance(parent,Element):
				parent=parent.parent
			else:
				parent=None
		return parent
	
	def AttachToParent(self,parent):
		"""Called to attach an orphan element to a parent.
		
		This method does not do any special handling of child elements,
		the caller takes responsibility for ensuring that this element
		will be returned by future calls to parent.GetChildren(). 
		However,
		:py:meth:`AttachToDocument` is called to ensure id registrations
		are made."""
		if self.parent:
			raise XMLParentError("Expected orphan")
		self.parent=parent
		self.AttachToDocument()
		
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
				if isinstance(child,Element):
					child.AttachToDocument(doc)
	
	def DetachFromParent(self):
		"""Called to detach an element from its parent, making it an orphan
		
		This method does not do any special handling of child elements,
		the caller takes responsibility for ensuring that this element
		will no longer be returned by future calls to
		parent.GetChildren().  However, :py:math:`DetachFromDocument` is
		called to ensure id registrations are removed."""
		self.DetachFromDocument()
		self.parent=None
		
	def DetachFromDocument(self,doc=None):
		"""Called when an element is being detached from a document.
		
		The default implementation ensures that any ID attributes belonging
		to this element or its descendents are unregistered."""
		if doc is None:
			doc=self.GetDocument()
		if doc:
			if self.id:
				doc.UnregisterElement(self)
			for child in self.GetChildren():
				if isinstance(child,Element):
					child.DetachFromDocument(doc)
		
	def AddData(self,data):
		"""Adds a string or unicode string to this element's children.

		This method raises a ValidationError if the element cannot take data
		children."""
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

	def GenerateValue(self,ignoreElements=False):
		"""A generator function that returns the strings that compromise
		this element's value (useful when handling elements that contain
		a large amount of data).  For more information see
		:py:meth:`GetValue`.  Note that::
		
		string.join(e.GenerateValue(),u'')==e.GetValue()"""
		if not self.IsMixed():
			raise XMLMixedContentError(self.__class__.__name__)
		for child in self.GetChildren():
			if type(child) in StringTypes:
				yield unicode(child)
			elif not ignoreElements:
				raise XMLMixedContentError(str(self))
		  
	def GetValue(self,ignoreElements=False):
		"""By default, returns a single unicode string representing the element's data.
		
		The default implementation is only supported for elements where
		mixed content is permitted (:py:meth:`IsMixed`).  It uses
		:py:meth:`GetChildren` to iterate through the children.
		
		If the element is empty an empty string is returned.
		
		Derived classes may return more complex objects, such as values
		of basic python types or class instances, performing validation
		based on application-defined rules.

		If the element contains child elements then XMLMixedContentError is raised.
		You can pass *ignoreElements* as True to override this behaviour in the unlikely
		event that you want::
		
			<!-- elements like this... -->
			<data>This is <em>the</em> value</data>
		
			# to behave like this:
			data.GetValue(True)==u"This is  value" """
		return string.join(self.GenerateValue(),u'')

	def SetValue(self,value):
		"""Replaces the value of the element with the (unicode) value.
		
		The default implementation is only supported for elements where
		mixed content is permitted (:py:meth:`IsMixed`) and only affects
		the internally maintained list of children.  Elements with more
		complex mixed models MUST override this method.
		
		If *value* is None then the element becomes empty.
		
		Derived classes may allow more complex values to be set, such as
		values of basic python types or class instances depending on the
		element type being represented in the application."""
		if not self.IsMixed():
			raise XMLMixedContentError
		self.Reset(False)
		if value is None:
			self._children=[]
		else:
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
		
		XMLELement can only be compared with other Elements."""
		if not isinstance(element,Element):
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
		selfChildren=list(self.GetCanonicalChildren())
		elementChildren=list(element.GetCanonicalChildren())
		for i in xrange(len(selfChildren)):
			if i>=len(elementChildren):
				# We're bigger by virtue of having more children
				return 1
			if isinstance(selfChildren[i],Element):
				if isinstance(elementChildren[i],Element):
					result=cmp(selfChildren[i],elementChildren[i])
				else:
					# elements sort before data
					result=-1
			elif isinstance(elementChildren[i],Element):
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
		"""Creates a new instance of this element which is a deep copy of this one.
		
		*parent* is the parent node to attach the new element to.  If it
		is None then a new orphan element is created.
		
		This method mimics the process of serialisation and
		deserialisation (without the need to generate markup).  As a
		result, element attributes are serialised and deserialised to
		strings during the copy process."""
		if parent:
			e=parent.ChildElement(self.__class__,self.GetXMLName())
		else:
			e=self.__class__(None)
		attrs=self.GetAttributes()
		for aname in attrs.keys():
			e.SetAttribute(aname,attrs[aname])
		for child in self.GetChildren():
			if type(child) in types.StringTypes:
				e.AddData(child)
			else:
				child.Copy(e)
		return e
		
	def GetBase(self):
		"""Returns the value of the xml:base attribute as a string."""
		return self._attrs.get(xml_base,None)
	
	def SetBase(self,base):
		"""Sets the value of the xml:base attribute from a string.
		
		Changing the base of an element effects the interpretation of all
		relative URIs in this element and its children."""
		if base is None:
			self._attrs.pop(xml_base,None)
		else:
			self._attrs[xml_base]=str(base)

	def ResolveBase(self):
		"""Returns a fully specified URI for the base of the current element.
		
		The URI is calculated using any xml:base values of the element or its
		ancestors and ultimately relative to the baseURI.
		
		If the element is not contained by a Document, or the document does
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
			if isinstance(baser,Element):
				baser=baser.parent
			else:
				break
		return baseURI
				
	def ResolveURI(self,uri):
		"""Returns a fully specified URL, resolving uri in the current context.
		
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
		"""Returns the value of the xml:lang attribute as a string."""
		return self._attrs.get(xml_lang,None)
	
	def SetLang(self,lang):
		"""Sets the value of the xml:lang attribute from a string.
		
		See :py:meth:`ResolveLang` for how to obtain the effective language of
		an element."""
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
			if isinstance(baser,Element):
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
		
		Note: an element of undetermined content model that contains only elements
		and white space *is* pretty printed."""
		spc=self.GetSpace()
		if spc is not None and spc=='preserve':
			return False
		if hasattr(self.__class__,'SGMLCDATA'):
			return False
		if isinstance(self.parent,Element):
			spc=self.parent.PrettyPrint()
			if spc is False:
				return False
		if hasattr(self,'XMLCONTENT'):
			# if we have a defined content model then we return False for
			# mixed content.
			return self.__class__.XMLCONTENT!=XMLMixedContent
		else:
			warnings.warn("class %s: Element.PrettyPrint with undefined content models is deprecated"%self.__class__.__name__, DeprecationWarning, stacklevel=3)
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
	
	def GenerateXML(self,escapeFunction=EscapeCharData,indent='',tab='\t',root=False):
		"""A generator function that returns strings representing the
		serialised version of this element::
		
			# the element's serialised output can be obtained as a single string
			string.join(e.GenerateXML(),'')"""
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
		try:
			child=children.next()
			if type(child) in StringTypes and len(child)>0 and IsS(child[0]):
				# First character is WS, so assume pre-formatted
				indent=tab=''
			yield u'%s<%s%s>'%(ws,self.xmlname,attributes)
			if hasattr(self.__class__,'SGMLCDATA'):
				# When expressed in SGML this element would have type CDATA so put it in a CDSect
				yield EscapeCDSect(self.GetValue())
			else:
				while True:
					if type(child) in types.StringTypes:
						# We force encoding of carriage return as these are subject to removal
						yield escapeFunction(child)
						# if we have character data content skip closing ws
						ws=''
					else:
						for s in child.GenerateXML(escapeFunction,indent,tab):
							yield s
					try:
						child=children.next()
					except StopIteration:
						break
			if not tab:
				# if we weren't tabbing children we need to skip closing white space
				ws=''
			yield u'%s</%s>'%(ws,self.xmlname)
		except StopIteration:
			yield u'%s<%s%s/>'%(ws,self.xmlname,attributes)

	def WriteXML(self,writer,escapeFunction=EscapeCharData,indent='',tab='\t',root=False):
		for s in self.GenerateXML(escapeFunction,indent,tab,root):
			writer.write(s)		

	
class XMLContentParticle(object):
	
	ExactlyOnce=0	#: Occurrence constant for particles that must appear exactly once
	ZeroOrOne=1		#: Occurrence constant for '?'
	ZeroOrMore=2	#: Occurrence constant for '*'
	OneOrMore=3		#: Occurrence constant for '+'
	
	def __init__(self):
		"""An object for representing content particles."""
		self.occurrence=XMLContentParticle.ExactlyOnce
		"""One of the occurrence constants defined above."""

	def BuildParticleMaps(self,exitParticles):
		"""Abstract method that builds the particle maps for this node or its children.
		
		For more information see :py:attr:`XMLNameParticle.particleMap`.
		
		Although only name particles have particle maps this method is called
		for all particle types to allow the model to be built hierarchically
		from the root out to the terminal (name) nodes.  *exitParticles*
		provides a mapping to all the following particles outside the part of
		the hierarchy rooted at the current node that are directly reachable
		from the particles inside."""
		raise XMLUnexpectedError
		
	def SeekParticles(self,pMap):
		"""Abstract method that adds all possible entry particles to pMap.

		*pMap* is a mapping from element name to a list of
		:py:class:`XMLNameParticles XMLNameParticle`.
		
		Returns True if a required particle was added, False if all particles
		added are optional.

		Like :py:meth:`BuildParticleMaps`, this method is called for all particle
		types.  The mappings requested represent all particles inside the
		part of the hierarchy rooted at the current node that are directly
		reachable from the preceeding particles outside."""
		raise XMLUnexpectedError
	
	def AddParticles(self,srcMap,pMap):
		"""A utility method that adds particles from srcMap to pMap.
		
		Both maps are mappings from element name to a list of
		:py:class:`XMLNameParticles XMLNameParticle`. All entries in *srcMap*
		not currently in *pMap* are added."""
		for name in srcMap.keys():
			if name in pMap:
				# add items from srcMap[name] to pMap[name]
				targetList=pMap[name]
			elif name:
				# add items to a new list
				pMap[name]=targetList=[]
			else:
				# add end tag sentinel
				pMap[name]=targetList=None
			if targetList is not None:
				# this double loop looks dangerous but the lists will usually be
				# 1 or 2 particles long at most - pathological cases are possible
				# but are best dealt with elsewhere (by restricting the number
				# of particles overall, say).
				for ip in srcMap[name]:
					dup=False
					for jp in targetList:
						if ip is jp:
							dup=True
							break
					if not dup:
						targetList.append(ip)
					
	def IsDeterministic(self,pMap):
		"""A utility method for identifying deterministic particle maps.
		
		A deterministic particle map is one in which name maps uniquely to a
		single content particle.  A non-deterministic particle map contains an
		ambiguity, for example ((b,d)|(b,e)).  The particle map created by
		:py:meth:`SeekParticles` for the enclosing choice list is would have two
		entries for 'b', one to map the first particle of the first sequence and
		one to the first particle of the second sequence.
		
		Although non-deterministic content models are not allowed in SGML they
		are tolerated in XML and are only flagged as compatibility errors."""
		if pMap:
			for name in pMap.keys():
				if pMap[name] is not None and len(pMap[name])>1:
					return False
		return True

		
class XMLNameParticle(XMLContentParticle):
	def __init__(self):
		"""An object representing a content particle for a named element in the grammar"""
		XMLContentParticle.__init__(self)
		self.name=None		#: the name of the element type that matches this particle
		self.particleMap={}
		"""Each :py:class:`XMLNameParticle` has a particle map that maps the
		name of the 'next' element found in the content model to the list of
		possible :py:class:`XMLNameParticles XMLNameParticle` that represent it in the content
		model.

		The content model can be traversed using :py:class:`ContentParticleCursor`."""

	def BuildParticleMaps(self,exitParticles):
		self.particleMap={}
		if self.occurrence==XMLContentParticle.ZeroOrMore or self.occurrence==XMLContentParticle.OneOrMore:
			# repeatable element, add ourselves to the map
			self.particleMap[self.name]=[self]
		self.AddParticles(exitParticles,self.particleMap)

	def SeekParticles(self,pMap):
		if self.name in pMap:
			targetList=pMap[self.name]
			dup=False
			for p in targetList:
				if p is self:
					dup=True
			if not dup:
				targetList.append(self)
		else:
			pMap[self.name]=[self]
		return self.occurrence==XMLContentParticle.OneOrMore or self.occurrence==XMLContentParticle.ExactlyOnce
					
	def IsDeterministic(self):
		return XMLContentParticle.IsDeterministic(self,self.particleMap)


class XMLChoiceList(XMLContentParticle):
	def __init__(self):
		"""An object representing a choice list of content particles in the grammar"""
		XMLContentParticle.__init__(self)
		self.children=[]

	def BuildParticleMaps(self,exitParticles):
		newExitParticles={}
		if self.occurrence==XMLContentParticle.ZeroOrMore or self.occurrence==XMLContentParticle.OneOrMore:
			# repeatable element means all our entry points are also exit points for our children
			self.SeekParticles(newExitParticles)
		# Now add the exit points already provided
		self.AddParticles(exitParticles,newExitParticles)
		# Finally, build the maps of our children
		for child in self.children:
			child.BuildParticleMaps(newExitParticles)

	def SeekParticles(self,pMap):
		required=self.occurrence==XMLContentParticle.ExactlyOnce or self.occurrence==XMLContentParticle.OneOrMore
		for child in self.children:
			# choice means all children are included
			if not child.SeekParticles(pMap):
				# if we have just one optional child we are effectively optional
				required=False
		return required	

	def IsDeterministic(self,pMap=None):
		if pMap:
			if not XMLContentParticle.IsDeterministic(self,pMap):
				return False
		for child in self.children:
			if not child.IsDeterministic():
				return False
		return True

		
class XMLSequenceList(XMLContentParticle):
	def __init__(self):
		"""An object representing a sequence list of content particles in the grammar"""
		XMLContentParticle.__init__(self)
		self.children=[]
	
	def BuildParticleMaps(self,exitParticles):
		newExitParticles={}
		if self.occurrence==XMLContentParticle.ZeroOrMore or self.occurrence==XMLContentParticle.OneOrMore:
			# repeatable element means all our entry points are also exit points
			self.SeekParticles(newExitParticles)
		# Now add the exit points already provided
		self.AddParticles(exitParticles,newExitParticles)
		for i in xrange(len(self.children)):
			child=self.children[i]
			# The exit points of child are the entry points of child+1,
			# but if child+1 is optional then we have to include child+2, and so on...
			childExits={}
			j=i+1
			while True:
				if j<len(self.children):
					if self.children[j].SeekParticles(childExits):
						break
					else:
						j=j+1
				else:
					# all children following in the sequence are optional
					self.AddParticles(newExitParticles,childExits)
					break
			child.BuildParticleMaps(childExits)

	def SeekParticles(self,pMap):
		optional=True
		for child in self.children:
			# sequence means include all children up to and including first required child
			if child.SeekParticles(pMap):
				optional=False
				break
		optional=optional or self.occurrence==XMLContentParticle.ZeroOrOne or self.occurrence==XMLContentParticle.ZeroOrMore
		return not optional	

	def IsDeterministic(self,pMap=None):
		if pMap:
			if not XMLContentParticle.IsDeterministic(self,pMap):
				return False
		for child in self.children:
			if not child.IsDeterministic():
				return False
		return True


class ContentParticleCursor(object):
	
	StartState=0	#: State constant representing the start state
	ParticleState=1 #: State constant representing a particle
	EndState=2		#: State constant representing the end state
	
	def __init__(self,elementType):
		"""An object used to traverse an :py:class:`ElementType`'s content model.
		
		The cursor records its position within the content model by recording
		the list of particles that may represent the current child element. When
		the next start tag is found the particles' maps are used to change the
		position of the cursor.  The end of the content model is represented by
		a special entry that maps the empty string to None.

		If a start tag is found that doesn't have an entry in any of the
		particles' maps then the document is not valid.
		
		Note that this cursor is tolerant of non-deterministic models as it
		keeps track of all possible matching particles within the model."""
		self.elementType=elementType
		self.state=ContentParticleCursor.StartState
		self.pList=[]
	
	def Next(self,name=''):
		"""Called when a child element with *name* is encountered.
		
		Returns True if *name* is a valid element and advances the model.  If
		*name* is not valid then it returns False and the cursor is
		unchanged."""
		if self.state==ContentParticleCursor.StartState:
			if self.elementType.particleMap is not None:
				if name in self.elementType.particleMap:
					self.pList=self.elementType.particleMap[name]
					if self.pList is None:
						self.state=ContentParticleCursor.EndState
					else:
						if not type(self.pList) is ListType:
							self.pList=[self.pList]
						self.state=ContentParticleCursor.ParticleState
					return True
				else:
					return False
			elif self.elementType.contentType==ElementType.Any:
				# anything goes for an Any element, we stay in the start state
				if not name:
					self.state=ContentParticleCursor.EndState
				return True
			elif self.elementType.contentType in (ElementType.Empty,ElementType.SGMLCDATA):
				# empty elements, or unparsed elements, can only get an end tag
				if not name:
					self.state=ContentParticleCursor.EndState
					return True
				else:
					return False
		elif self.state==ContentParticleCursor.ParticleState:
			newPList=[]
			for p in self.pList:
				# go through all possible particles
				if name in p.particleMap:
					ps=p.particleMap[name]
					if ps is None:
						# short cut to end state
						newPList=None
						self.state=ContentParticleCursor.EndState
						break
					if type(ps) is ListType:
						newPList=newPList+ps
					else:
						newPList.append(ps)
			if newPList is None or len(newPList)>0:
				# success if we got to the end state or have found particles 
				self.pList=newPList
				return True
			else:
				return False
		else:
			# when in the end state everything is invalid
			return False

	def Expected(self):
		"""Returns a sorted list of valid element names in the current state.
		
		If the closing tag is valid it appends a representation of the closing
		tag too, e.g., </element>.  If the cursor is in the end state an empty
		list is returned."""
		expected={}
		endTag=None
		if self.state==ContentParticleCursor.StartState:
			for name in self.elementType.particleMap.keys():
				if name:
					expected[name]=True
				else:
					endTag="</%s>"%self.elementType.name
		elif self.state==ContentParticleCursor.ParticleState:
			for p in self.pList:
				for name in p.particleMap.keys():
					if name:
						expected[name]=True
					else:
						endTag="</%s>"%self.elementType.name
		result=expected.keys()
		result.sort()
		if endTag:
			result.append(endTag)
		return result
							

class XMLAttributeDefinition(object):

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
	
	TypeString={
		0:'CDATA',
		1:'ID',
		2:'IDREF',
		3:'IDREFS',
		4:'ENTITY',
		5:'ENTITIES',
		6:'NMTOKEN',
		7:'NMTOKENS',
		8:'NOTATION',
		9:'Enumeration'}
		
	Implied=0		#: Presence constant representing #IMPLIED
	Required=1		#: Presence constant representing #REQUIRED
	Fixed=2			#: Presence constant representing #FIXED
	Default=3		#: Presence constant representing a declared default value
	
	def __init__(self):
		"""An object for representing attribute declarations."""
		self.entity=None								#: the entity in which this attribute was declared
		self.name=None									#: the name of the attribute
		self.type=XMLAttributeDefinition.CData			#: One of the above type constants
		self.values=None								#: An optional dictionary of values
		self.presence=XMLAttributeDefinition.Implied	#: One of the above presence constants
		self.defaultValue=None							#: An optional default value


class XMLEntity(object):
	def __init__(self,src=None,encoding=None,reqManager=None):
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
		self.bom=False
		"""flag to indicate whether or not the byte order mark was detected.  If
		detected the flag is set to True.  An initial byte order mark is not
		reported in :py:attr:`theChar` or by the :py:meth:`NextChar` method."""
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
		elif isinstance(src,http.HTTPResponse):
			self.OpenHTTPResponse(src,encoding)
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
		if self.location is None:
			return repr(self)
		else:
			return str(self.location)
			
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
	
	def IsOpen(self):
		"""Returns True if the entity is open for reading."""
		return not (self.charSource is None)
		
	def OpenUnicode(self,src):
		"""Opens the entity from a unicode string."""
		self.encoding='utf-8'		#: a white lie to ensure that all entities have an encoding
		self.dataSource=None
		self.chunk=XMLEntity.ChunkSize
		self.charSource=StringIO(src)
		self.basePos=self.charSource.tell()
		self.Reset()

	def OpenString(self,src,encoding=None):
		"""Opens the entity from a byte string.
		
		The optional *encoding* is used to convert the string to unicode and
		defaults to None - meaning that the auto-detection method will be
		applied.
		
		The advantage of using this method instead of converting the string to
		unicode and calling :py:meth:`OpenUnicode` is that this method creates a
		unicode reader object to parse the string instead of making a copy of it
		in memory."""
		self.encoding=encoding
		self.dataSource=StringIO(src)
		if self.encoding is None:
			self.AutoDetectEncoding(self.dataSource)
		self.chunk=1
		self.charSource=codecs.getreader(self.encoding)(self.dataSource)
		self.basePos=self.charSource.tell()
		self.Reset()
	
	def OpenFile(self,src,encoding='utf-8'):
		"""Opens the entity from an existing (open) binary file.
		
		The optional *encoding* provides a hint as to the intended
		encoding of the data and defaults to UTF-8.  Unlike other Open*
		methods we do not assume that the file is seekable however, you
		may set encoding to None for a seekable file thus invoking
		auto-detection of the encoding."""
		self.encoding=encoding
		self.dataSource=src
		if self.encoding is None:
			self.AutoDetectEncoding(self.dataSource)
		self.chunk=1
		self.charSource=codecs.getreader(self.encoding)(self.dataSource)
		self.basePos=self.charSource.tell()
		self.Reset()
				
	def OpenURI(self,src,encoding=None,reqManager=None):
		"""Opens the entity from a URI passed in *src*.
		
		The file, http and https schemes are the only ones supported.
		
		The optional *encoding* provides a hint as to the intended encoding of
		the data and defaults to UTF-8.  For http(s) resources this parameter is
		only used if the charset cannot be read successfully from the HTTP
		headers.
		
		The optional *reqManager* allows you to pass an existing instance of
		:py:class:`pyslet.rfc2616.HTTPRequestManager` for handling URI with
		http or https schemes."""
		self.location=src
		if isinstance(src,FileURL):
			srcFile=open(src.GetPathname(),'rb')
			self.encoding=encoding
			if self.encoding is None:
				# Given that we know we have a file we can use some auto-detection
				# logic to discover the correct encoding
				self.AutoDetectEncoding(srcFile)
			self.OpenFile(srcFile,self.encoding)
		elif src.scheme.lower() in ['http','https']:
			if reqManager is None:
				reqManager=http.HTTPRequestManager()
			req=http.HTTPRequest(str(src))
			reqManager.ProcessRequest(req)
			if req.status==200:
				self.OpenHTTPResponse(req.response,encoding)
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
				srcFile=StringIO(req.resBody)
				if self.encoding is None:
					self.AutoDetectEncoding(srcFile)
				self.OpenFile(srcFile,self.encoding)
			elif req.status==404:
				raise XMLMissingResourceError(str(req.status)+" "+str(req.response.reason))
			else:	
				raise XMLUnexpectedHTTPResponse(str(req.status)+" "+str(req.response.reason))
		else:
			raise XMLUnsupportedScheme			
		
	def OpenHTTPResponse(self,src,encoding='utf-8'):
		"""Opens the entity from an HTTP response passed in *src*.
		
		The optional *encoding* provides a hint as to the intended encoding of
		the data and defaults to UTF-8.  This parameter is only used if the
		charset cannot be read successfully from the HTTP response headers."""
		self.encoding=encoding
		newLocation=src.GetHeader("Location")
		if newLocation:
			self.location=URIFactory.URI(newLocation.strip())
		mtype=src.GetContentType()
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
		self.OpenFile(StringIO(src.request.resBody),self.encoding)

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

	MagicTable={
		'\x00\x00\xfe\xff':('utf_32_be',4,True),		# UCS-4, big-endian machine (1234 order)
		'\xff\xfe\x00\x00':('utf_32_le',4,True),		# UCS-4, little-endian machine (4321 order)
		'\x00\x00\xff\xfe':('utf_32',4,True),			# UCS-4, unusual octet order (2143)
		'\xfe\xff\x00\x00':('utf_32',4,True),			# UCS-4, unusual octet order (3412)
		'\xfe\xff':('utf_16_be',2,True),				# UTF-16, big-endian
		'\xff\xfe':('utf_16_le',2,True),				# UTF-16, little-endian
		'\xef\xbb\xbf':('utf-8',3,True),				# UTF-8 with byte order mark
		'\x00\x00\x00\x3c':('utf_32_be',0,False),		# UCS-4 or other encoding with a big-endian 32-bit code unit
		'\x3c\x00\x00\x00':('utf_32_le',0,False),		# UCS-4 or other encoding with a little-endian 32-bit code unit
		'\x00\x00\x3c\x00':('utf_32_le',0,False),		# UCS-4 or other encoding with an unusual 32-bit code unit
		'\x00\x3c\x00\x00':('utf_32_le',0,False),		# UCS-4 or other encoding with an unusual 32-bit code unit		
		'\x00\x3c\x00\x3f':('utf_16_be',0,False),		# UTF-16BE or big-endian ISO-10646-UCS-2 or other encoding with a 16-bit code unit
		'\x3c\x00\x3f\x00':('utf_16_le',0,False),		# UTF-16LE or little-endian ISO-10646-UCS-2 or other encoding with a 16-bit code unit
		'\3c\x3f\x78\x6D':('utf_8',0,False),			# UTF-8, ISO 646, ASCII or similar
		'\4c\x6f\xa7\x94':('cp500',0,False)				# EBCDIC (in some flavor)
		}
					
	def AutoDetectEncoding(self,srcFile):
		"""Auto-detects the character encoding in *srcFile*.
		
		Should only be called for seek-able streams opened in binary mode."""
		srcFile.seek(0)
		magic=srcFile.read(4)
		while len(magic)<4:
			magic=magic+'Q'
		if magic[:2]=='\xff\xfe' or magic[:2]=='\xfe\xff':
			if magic[2:]!='\x00\x00':
				magic=magic[:2]
		elif magic[:3]=='\xef\xbb\xbf':
			magic=mage[:3]
		self.encoding,seekPos,self.bom=self.MagicTable.get(magic,('utf-8',0,False))
		srcFile.seek(seekPos)
	
	EncodingAliases={
		'iso-10646-ucs-2':('utf_16',True),	# not strictly true as UTF-16 includes surrogate processing
		'iso-10646-ucs-4':('utf_32',True),
		'utf-16':('utf_16',True),
		'utf-32':('utf_32',True),
		'cn-big5':('big5',False),			# for compatibility with some older XML documents
		'cn-gb2312':('gb2312',False)		
		}
							
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
			lencoding=encoding.lower()
			if lencoding in self.EncodingAliases:
				encoding,keepExisting=self.EncodingAliases[lencoding]
			else:
				keepExisting=False
			# Sometimes we'll change encoding but want to stick with what we have.
			# for the ucs-2 and ucs-4 encodings it is impossible for us to have
			# got to the point of parsing a declaration without knowing if we're
			# using LE or BE in the stream.  Given that these encodings map to the
			# python UTF-16 and UTF-32 we don't want to reset the stream because
			# that will force BOM detection and we may not have a BOM to detect.
			if not keepExisting:
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
			from pyslet.xml20081126.parser import XMLParser
			p=XMLParser(self)
			if p.ParseLiteral('<?xml'):
				p.ParseTextDecl(True)
			self.KeepEncoding()
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


class XMLExternalID(object):
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

			
class XMLNotation(object):
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

IdeographicCharClass=CharClass((u'\u4e00',u'\u9fa5'),u'\u3007',(u'\u3021',u'\u3029'))
LetterCharClass=CharClass(BaseCharClass,IdeographicCharClass)

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
	

def MapClassElements(classMap,scope):
	"""Searches scope and adds element name -> class mappings to classMap
	
	The search is not recursive, to add class elements from imported modules you
	must call MapClassElements for each module.
	
	Mappings are added for each class that is derived from :py:class:`Element`
	that has an XMLNAME attribute defined.  It is an error if a class is
	found with an XMLNAME that has already been mapped."""
	if type(scope) is not DictType:
		scope=scope.__dict__
	names=scope.keys()
	for name in names:
		obj=scope[name]
		if type(obj) in (ClassType,TypeType) and issubclass(obj,Element):
			if hasattr(obj,'XMLNAME'):
				if obj.XMLNAME in classMap:
					raise DuplicateXMLNAME("%s and %s have matching XMLNAMEs"%(obj.__name__,classMap[obj.XMLNAME].__name__))
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

