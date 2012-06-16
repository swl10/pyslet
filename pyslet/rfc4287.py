#! /usr/bin/env python
"""This module implements the Atom 1.0 specification defined in RFC 4287

References:

IRIs [RFC3987]; cf URI [RFC3986]
(1) when an IRI that is not also a URI is given for dereferencing,
it MUST be mapped to a URI using the steps in Section 3.1 of [RFC3987]
(2) when an IRI is serving as an atom:id value, it MUST NOT be so mapped,
so that the comparison works as described in Section 4.2.6.1.

xml:base attribute [W3C.REC-xmlbase-20010627]
xml:lang attribute [W3C.REC-xml-20040204], Section 2.12

A Date construct is an element whose content MUST conform to the "date-time" production in [RFC3339]
"""

import string, types, itertools
import pyslet.info
import pyslet.iso8601 as iso8601
import pyslet.html40_19991224 as html
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2396 as uri

ATOM_NAMESPACE="http://www.w3.org/2005/Atom"		#: The namespace to use for Atom Document elements
ATOM_MIMETYPE="application/atom+xml"				#: The mime type for Atom Document

_ATOM_TEXT_TYPES={'text':1,'html':1,'xhtml':1}

class AtomElement(xmlns.XMLNSElement):
	"""Base class for all APP elements.
	
	All atom elements can have xml:base and xml:lang attributes, these are
	handled by the :py:class:`~pyslet.xml20081126.structures.Element` base
	class.
	
	See :py:meth:`~pyslet.xml20081126.structures.Element.GetLang` and
	:py:meth:`~pyslet.xml20081126.structures.Element.SetLang`,
	:py:meth:`~pyslet.xml20081126.structures.Element.GetBase` and
	:py:meth:`~pyslet.xml20081126.structures.Element.SetBase`"""
	pass
	
	
class TextType(xsi.Enumeration):
	"""text type enumeration::
		
		 "text" | "html" | "xhtml"
		 
	This enumeration is used for setting the :py:attr:`Text.type` attribute.
	
	Usage: TextType.text, TextType.html, TextType.xhtml"""
	decode={
		'text':1,
		'html':2,
		'xhtml':3
		}
xsi.MakeEnumeration(TextType)


class Text(AtomElement):
	"""Base class for atomPlainTextConstruct and atomXHTMLTextConstruct."""
	
	XMLATTR_type=('type',TextType.DecodeLowerValue,TextType.EncodeValue)

	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.type=TextType.text

	def SetValue(self,value,type=TextType.text):
		"""Sets the value of the element.  *type* must be a value from the :py:class:`TextType` enumeration
		
		Overloads the basic
		:py:meth:`~pyslet.xml20081126.structures.Element.SetValue`
		implementation, adding an additional *type* attribute to enable the
		value to be set to either a plain TextType.text, TextType.html or
		TextType.xhtml value.  In the case of an xhtml type, *value* is parsed
		for the required XHTML div element and this becomes the only child of
		the element.  Given that the div itself is not considered to be part
		of the content the value can be given without the enclosing div, in
		which case it is generated automatically."""
		if type==TextType.text or type==TextType.html:
			AtomElement.SetValue(self,value)
			self.type=type
		elif type==TextType.xhtml:
			e=xml.XMLEntity(value)
			doc=html.XHTMLDocument(baseURI=self.ResolveBase())
			doc.ReadFromEntity(e)
			div=list(doc.root.Body.GetChildren())
			if len(div)==1 and isinstance(div[0],html.Div):
				div=div[0]
				# We remove our existing content
				self.SetValue(None)
				# And do a deep copy of the div instead
				newDiv=div.Copy(self)
			else:
				newDiv=self.ChildElement(html.Div)
				for divChild in div:
					if isinstance(divChild,xml.Element):
						divChild.Copy(newDiv)
					else:
						newDiv.AddData(divChild)
			newDiv.MakePrefix(html.XHTML_NAMESPACE,'')
			self.type=type
		else:
			raise ValueError("Expected text or html identifiers, found %s"%str(type))

	def GetValue(self):
		"""Gets a single unicode string representing the value of the element.
		
		Overloads the basic
		:py:meth:`~pyslet.xml20081126.structures.Element.GetValue`
		implementation to add support for text of type xhtml.
		
		When getting the value of TextType.xhtml text the child div element is
		not returned as it is not considered to be part of the content."""
		if self.type==TextType.text or self.type==TextType.html:
			return AtomElement.GetValue(self)
		elif self.type==TextType.xhtml:
			# concatenate all children, but should be just a single div
			result=[]
			valueChildren=list(self.GetChildren())
			if len(valueChildren) and isinstance(valueChildren[0],html.Div):
				valueChildren=list(valueChildren[0].GetChildren())
			for c in valueChildren:
				result.append(unicode(c))
			return string.join(result,'')
		else:
			raise ValueError("Unknown text type: %s"%str(self.type))

	
class AtomId(AtomElement):
	"""A permanent, universally unique identifier for an entry or feed."""
	XMLNAME=(ATOM_NAMESPACE,'id')


class Name(AtomElement):
	"""A human-readable name for a person."""
	XMLNAME=(ATOM_NAMESPACE,'name')


class Title(Text):
	"""A :py:class:`Text` construct that conveys a human-readable title for an entry or feed."""
	XMLNAME=(ATOM_NAMESPACE,'title')


class Subtitle(Text):
	"""A :py:class:`Text` construct that conveys a human-readable description or subtitle for a feed."""
	XMLNAME=(ATOM_NAMESPACE,'subtitle')


class Summary(Text):
	"""A :py:class:`Text` construct that conveys a short summary, abstract, or excerpt of an entry."""
	XMLNAME=(ATOM_NAMESPACE,'summary')


class Rights(Text):
	"""A Text construct that conveys information about rights held in and over an entry or feed."""
	XMLNAME=(ATOM_NAMESPACE,'rights')

	
class Date(AtomElement):
	"""An element conforming to the definition of date-time in RFC3339.
	
	This class is modeled using the iso8601 module."""
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.date=iso8601.TimePoint()		#: a :py:class:`~pyslet.iso8601.TimePoint` instance representing this date
	
	def GetValue(self):
		"""Overrides :py:meth:`~pyslet.xml20081126.structures.Element.GetValue`, returning a :py:class:`pyslet.iso8601.TimePoint` instance."""
		return self.date
	
	def SetValue(self,value):
		"""Overrides :py:meth:`~pyslet.xml20081126.structures.Element.SetValue`, enabling the value to be set from a :py:class:`pyslet.iso8601.TimePoint` instance.
		
		If *value* is a string the behaviour is unchanged, if *value* is a
		TimePoint instance then it is formatted using the extended format of ISO
		8601 in accordance with the requirements of the Atom specification."""
		if isinstance(value,iso8601.TimePoint):
			self.date=value
			AtomElement.SetValue(self,value.GetCalendarString())
		else:
			AtomElement.SetValue(self,value)
			self.ContentChanged()
		
	def ContentChanged(self):
		"""Re-reads the value of the element and sets :py:attr:`date` accordingly."""
		self.date.SetFromString(AtomElement.GetValue(self))


class Updated(Date):
	"""A Date construct indicating the most recent instant in time when an entry or feed was modified in a way the publisher considers significant."""
	XMLNAME=(ATOM_NAMESPACE,'updated')


class Published(Date):
	"""A Date construct indicating an instant in time associated with an event early in the life cycle of the entry."""
	XMLNAME=(ATOM_NAMESPACE,"published")

			
class Link(AtomElement):
	"""A reference from an entry or feed to a Web resource."""
	XMLNAME=(ATOM_NAMESPACE,'link')	
	XMLATTR_href=('href',uri.URIFactory.URI,str)
	XMLATTR_rel='rel'
	XMLATTR_type='type'
	XMLATTR_hreflang='hreflang'
	XMLATTR_title='title'
	XMLATTR_length=('length',xsi.DecodeInteger,xsi.EncodeInteger)

	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.href=None		#: a :py:class:`~pyslet.rfc2396.URI` instance, the link's IRI
		self.rel=None		#: a string indicating the link relation type
		self.type=None		#: an advisory media type
		self.hreflang=None	#: the language of the resource pointed to by :py:attr:`href`
		self.title=None		#: human-readable information about the link
		self.length=None	#: an advisory length of the linked content in octets
				

class Icon(AtomElement):
	"""Identifies an image that provides iconic visual identification for a feed."""
	XMLNAME=(ATOM_NAMESPACE,'icon')
   
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.uri=None		#: a :py:class:`~pyslet.rfc2396.URI` instance representing the URI of the icon

	def GetValue(self):
		"""Overrides :py:meth:`~pyslet.xml20081126.structures.Element.GetValue`, returning a :py:class:`pyslet.rfc2396.URI` instance."""
		return self.uri
	
	def SetValue(self,value):
		"""Overrides :py:meth:`~pyslet.xml20081126.structures.Element.SetValue`, enabling the value to be set from a :py:class:`pyslet.rfc2396.URI` instance.
		
		If *value* is a string it is used to set the element's content,
		:py:meth:`ContentChanged` is then called to update the value of
		:py:attr:`uri`.  If *value* is a URI instance then :py:attr:`uri` is set
		directory and it is then converted to a string and used to set the
		element's content."""
		if isinstance(value,uri.URI):
			self.uri=value
			AtomElement.SetValue(self,str(value))
		else:
			AtomElement.SetValue(self,value)
			self.ContentChanged()
		
	def ContentChanged(self):
		"""Re-reads the value of the element and sets :py:attr:`uri` accordingly.""" 
		self.uri=uri.URIFactory.URI(AtomElement.GetValue(self))


class Logo(Icon):
	"""An image that provides visual identification for a feed."""
	XMLNAME=(ATOM_NAMESPACE,'logo')


class Generator(AtomElement):
	"""Identifies the agent used to generate a feed, for debugging and other purposes."""
	XMLNAME=(ATOM_NAMESPACE,'generator')
	XMLATTR_uri=('uri',uri.URIFactory.URI,str)
	XMLATTR_version='version'
	
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.uri=None			#: the uri of the tool used to generate the feed
		self.version=None		#: the version of the tool used to generate the feed

	def SetPysletInfo(self):
		"""Sets this generator to a default representation of this Pyslet module."""
		self.uri=uri.URIFactory.URI(pyslet.info.home)
		self.version=pyslet.info.version
		self.SetValue(pyslet.info.title)


def DecodeContentType(src):
	try:
		return TextType.DecodeLowerValue(src)
	except ValueError:
		return src.strip()

def EncodeContentType(value):
	if type(value) in types.StringTypes:
		return value
	else:
		return TextType.EncodeValue(value)
		
class Content(Text):
	"""Contains or links to the content of the entry.
	
	Although derived from :py:class:`Text` this class overloads the meaning of
	the :py:attr:`Text.type` attribute allowing it to be a media type."""
	XMLNAME=(ATOM_NAMESPACE,"content")
	XMLATTR_src=('src',uri.URIFactory.URI,str)
	XMLATTR_type=('type',DecodeContentType,EncodeContentType)

	def __init__(self,parent):
		Text.__init__(self,parent)
		self.src=None			#: link to remote content

	def GetValue(self):
		"""Gets a single unicode string representing the value of the element.
		
		Overloads the basic
		:py:meth:`~Text.GetValue`, if :py:attr:`type` is a media type rather
		than one of the text types then a ValueError is raised."""
		if type(self.type) in types.StringTypes:
			raise ValueError("Can't get value of non-text content")
		else:
			Text.GetValue(self)


class URI(AtomElement):
	"""An IRI associated with a person"""
	XMLNAME=(ATOM_NAMESPACE,'uri')


class Email(AtomElement):
	"""An e-mail address associated with a person"""
	XMLNAME=(ATOM_NAMESPACE,'email')


class Person(AtomElement):
	"""An element that describes a person, corporation, or similar entity"""
	NameClass=Name
	URIClass=URI
	
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.Name=self.NameClass(self)
		self.URI=None
		self.Email=None

	def GetChildren(self):
		if self.Name: yield self.Name
		if self.URI: yield self.URI
		if self.Email: yield self.Email
		for child in AtomElement.GetChildren(self): yield child
		
	
class Author(Person):
	"""A Person construct that indicates the author of the entry or feed."""
	XMLNAME=(ATOM_NAMESPACE,'author')


class Contributor(Person):
	"""A Person construct that indicates a person or other entity who contributed to the entry or feed."""
	XMLNAME=(ATOM_NAMESPACE,"contributor")

	
class Category(AtomElement):
	"""Information about a category associated with an entry or feed."""
	XMLNAME=(ATOM_NAMESPACE,"category")
	XMLATTR_term='term'
	XMLATTR_scheme='scheme'
	XMLATTR_label='label'
	
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.term=None		#: a string that identifies the category to which the entry or feed belongs
		self.scheme=None
		"""an IRI that identifies a categorization scheme.
		
		This is not converted to a :py:class:`pyslet.rfc2396.URI` instance as it
		is not normally resolved to a resource.  Instead it defines a type of
		namespace."""		
		self.label=None		#: a human-readable label for display in end-user applications
	
	
class Entity(AtomElement):
	"""Base class for feed, entry and source elements."""

	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.AtomId=None
		"""the atomId of the object
		
		Note that we qualify the class name used to represent the id to avoid
		confusion with the existing 'id' attribute in
		:py:class:`~pyslet.xml20081126.structures.Element`."""
		self.Author=[]		#: atomAuthor
		self.Category=[]	#: atomCategory
		self.Contributor=[]	#: atomContributor
		self.Link=[]		#: atomLink
		self.Rights=None	#: atomRights
		self.Title=None		#: atomTitle
		self.Updated=None	#: atomUpdated

	def GetChildren(self):
		if self.AtomId: yield self.AtomId
		if self.Title: yield self.Title
		if self.Rights: yield self.Rights
		if self.Updated: yield self.Updated
		for child in itertools.chain(
			self.Link,
			self.Author,
			self.Contributor,
			self.Category,
			AtomElement.GetChildren(self)):
			yield child
	
		
class Source(Entity):
	"""Metadata from the original source feed of an entry.
	
	This class is also used a base class for :py:class:`Feed`."""
	XMLNAME=(ATOM_NAMESPACE,'source')

	def __init__(self,parent):
		Entity.__init__(self,parent)
		self.Generator=None		#: atomGenerator
		self.Icon=None			#: atomIcon
		self.Logo=None			#: atomLogo
		self.Subtitle=None		#: atomSubtitle
		
	def GetChildren(self):
		for child in Entity.GetChildren(self): yield child
		if self.Generator: yield self.Generator
		if self.Icon: yield self.Icon
		if self.Logo: yield self.Logo
		if self.Subtitle: yield self.Subtitle
		
							
class Feed(Source):
	"""Represents an Atom feed.
	
	This is the document (i.e., top-level) element of an Atom Feed Document,
	acting as a container for metadata and data associated with the feed"""
	XMLNAME=(ATOM_NAMESPACE,'feed')
	AtomIdClass=AtomId
	TitleClass=Title
	UpdatedClass=Updated
	
	def __init__(self,parent):
		Source.__init__(self,parent)
		self.AtomId=self.AtomIdClass(self)
		self.Title=self.TitleClass(self)
		self.Updated=self.UpdatedClass(self)
		now=iso8601.TimePoint()
		now.NowUTC()
		self.Updated.SetValue(now)
		self.Entry=[]		#: atomEntry

	def GetChildren(self):
		for child in itertools.chain(
			Source.GetChildren(self),
			self.Entry):
			yield child

		
class Entry(Entity):
	"""An individual entry, acting as a container for metadata and data associated with the entry."""
	XMLNAME=(ATOM_NAMESPACE,'entry')
	AtomIdClass=AtomId
	TitleClass=Title
	UpdatedClass=Updated
	LinkClass=Link
	
	def __init__(self,parent):
		Entity.__init__(self,parent)
		self.AtomId=self.AtomIdClass(self)
		self.Title=self.TitleClass(self)
		self.Updated=self.UpdatedClass(self)
		now=iso8601.TimePoint()
		now.NowUTC()
		self.Updated.SetValue(now)
		self.Content=None
		self.Published=None
		self.Source=None
		self.Summary=None
							
	def GetChildren(self):
		for child in Entity.GetChildren(self): yield child
		if self.Content: yield self.Content
		if self.Published: yield self.Published
		if self.Source: yield self.Source
		if self.Summary: yield self.Summary
			

class AtomDocument(xmlns.XMLNSDocument):
	classMap={}
	
	DefaultNS=ATOM_NAMESPACE
	
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,defaultNS=ATOM_NAMESPACE,**args)

	def GetElementClass(self,name):
		return AtomDocument.classMap.get(name,AtomDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

xmlns.MapClassElements(AtomDocument.classMap,globals())
