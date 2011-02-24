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

import string, types

import pyslet.iso8601 as iso8601
import pyslet.xmlnames20091208 as xmlns

ATOM_NAMESPACE="http://www.w3.org/2005/Atom"
atom_author=(ATOM_NAMESPACE,'author')
atom_entry=(ATOM_NAMESPACE,'entry')
atom_category=(ATOM_NAMESPACE,"category")
atom_content=(ATOM_NAMESPACE,"content")
atom_contributor=(ATOM_NAMESPACE,"contributor")
atom_feed=(ATOM_NAMESPACE,'feed')
atom_generator=(ATOM_NAMESPACE,'generator')
atom_icon=(ATOM_NAMESPACE,'icon')
atom_id=(ATOM_NAMESPACE,'id')
atom_link=(ATOM_NAMESPACE,'link')
atom_logo=(ATOM_NAMESPACE,'logo')
atom_name=(ATOM_NAMESPACE,'name')
atom_rights=(ATOM_NAMESPACE,'rights')
atom_source=(ATOM_NAMESPACE,'source')
atom_subtitle=(ATOM_NAMESPACE,'subtitle')
atom_summary=(ATOM_NAMESPACE,'summary')
atom_title=(ATOM_NAMESPACE,'title')
atom_updated=(ATOM_NAMESPACE,'updated')

ATOM_MIMETYPE="application/atom+xml"

_ATOM_TEXT_TYPES={'text':1,'html':1,'xhtml':1}

class AtomElement(xmlns.XMLNSElement):
	"""Basic element to represent all Atom elements; not that xml:base and xml:lang are handled by
	the XMLElement mix-in class.
	
	atomCommonAttributes =
		attribute xml:base { atomUri }?,
		attribute xml:lang { atomLanguageTag }?,
		undefinedAttribute*
	"""  
	pass
	
	
class AtomId(AtomElement):
	XMLNAME=atom_id

class AtomName(AtomElement):
	XMLNAME=atom_name

class AtomText(AtomElement):
	"""
	atomPlainTextConstruct =
		atomCommonAttributes,
		attribute type { "text" | "html" }?,
		text

	atomXHTMLTextConstruct =
		atomCommonAttributes,
		attribute type { "xhtml" },
		xhtmlDiv

	atomTextConstruct = atomPlainTextConstruct | atomXHTMLTextConstruct
	"""	
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent,name)
		self.type='text'

	def SetValue(self,value,type='text'):
		self.Set_type(type)
		AtomElement.SetValue(self,value)
	
	def GetAttributes(self):
		attrs=AtomElement.GetAttributes(self)
		if self.type:
			attrs['type']=self.type
		return attrs
		
	def Set_type(self,value):
		if value is None:
			self.type=None
		elif _ATOM_TEXT_TYPES.get(value,None):
			self.type=value
		else:
			raise ValueError		

class AtomTitle(AtomText):
	XMLNAME=atom_title

class AtomSubtitle(AtomText):
	XMLNAME=atom_subtitle

class AtomSummary(AtomText):
	XMLNAME=atom_summary

class AtomRights(AtomText):
	XMLNAME=atom_rights

	
class AtomDate(AtomElement):
	"""
		atomDateConstruct =
			atomCommonAttributes,
			xsd:dateTime"""
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent,name)
		self.date=iso8601.TimePoint()
	
	def GetValue(self):
		return self.date
		
	def GotChildren(self):
		# called when all children have been parsed
		self.date.SetFromString(AtomElement.GetValue(self))

class AtomUpdated(AtomDate):
	XMLNAME=atom_updated

		
class AtomLink(AtomElement):
	XMLNAME=atom_link
	
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent,name)
		self.href=None
		self.hreflang=None
		self.rel=None
		self.type=None
	
	def GetAttributes(self):
		attrs=AtomElement.GetAttributes(self)
		if self.href:
			attrs['href']=self.href
		if self.hreflang:
			attrs['hreflang']=self.hreflang
		if self.rel:
			attrs['rel']=self.rel
		if self.type:
			attrs['type']=self.type
		return attrs
		
	def Set_href(self,value):
		self.href=value
		
	def Set_hreflang(self,value):
		self.hreflang=value
		
	def Set_rel(self,value):
		self.rel=value
		
	def Set_type(self,value):
		self.type=value
		

class AtomIcon(AtomElement):
	"""
	atomIcon = element atom:icon {
		atomCommonAttributes,
		(atomUri)
		}"""
	XMLNAME=atom_icon
   
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent)
		self.uri=None

	def GetAttributes(self):
		attrs=AtomElement.GetAttributes(self)
		if self.uri:
			attrs['uri']=self.uri
		return attrs

	def Set_uri(self,value):
		self.uri=value

class AtomLogo(AtomIcon):
	XMLNAME=atom_logo


class AtomGenerator(AtomElement):
	"""
	atomGenerator = element atom:generator {
		atomCommonAttributes,
		attribute uri { atomUri }?,
		attribute version { text }?,
		text
	}"""
	XMLNAME=atom_generator
	
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent)
		self.uri=None
		self.version=None

	def GetAttributes(self):
		attrs=AtomElement.GetAttributes(self)
		if self.uri:
			attrs['uri']=self.uri
		if self.version:
			attrs['version']=self.version
		return attrs

	def Set_uri(self,value):
		self.uri=value
	
	def Set_version(self,value):
		self.version=value
			

class AtomContent(AtomElement):
	XMLNAME=atom_content
	

class AtomEntity(AtomElement):
	"""Used to model feed, entry and source: more complex constructs which can have their own metadata."""
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent,name)
		self.metadata={}

	def GetAuthors(self):
		return self.metadata.get('author',[])
			
	def GetCategories(self):
		return self.metadata.get('category',[])
		
	def GetContributors(self):
		return self.metadata.get('contributor',[])

	def GetId(self):
		return self.metadata.get('id',None)
		
	def GetLinks(self):
		return self.metadata.get('link',[])

	def GetRights(self):
		return self.metadata.get('rights',None)

	def GetTitle(self):
		return self.metadata.get('title',None)
	
	def GetUpdated(self):
		return self.metadata.get('updated',None)
		
	def GetChildren(self):
		children=[]
		keys=self.metadata.keys()
		keys.sort()
		for key in keys:
			value=self.metadata[key]
			if type(value) is types.ListType:
				children=children+value
			else:
				children.append(value)
		return children+AtomElement.GetChildren(self)
	
	def SingleMetadata(self,childClass,name):
		child=childClass(self,name)
		oldChild=self.metadata.get(child.xmlname,None)
		if oldChild:
			oldChild.DetachFromDocument()
		self.metadata[child.xmlname]=child
		return child
	
	def MultipleMetadata(self,childClass,name):
		child=childClass(self,name)
		if self.metadata.has_key(child.xmlname):
			self.metadata[child.xmlname].append(child)
		else:
			self.metadata[child.xmlname]=[child]
		return child
		
	def AtomAuthor(self,name=None):
		return self.MultipleMetadata(AtomAuthor,name)
		
	def AtomCategory(self,name=None):
		return self.MultipleMetadata(AtomCategory,name)
		
	def AtomContributor(self,name=None):
		return self.MultipleMetadata(AtomContributor,name)
		
	def AtomId(self,name=None):
		return self.SingleMetadata(AtomId,name)
	
	def AtomLink(self,name=None):
		return self.MultipleMetadata(AtomLink,name)
	
	def AtomRights(self,name=None):
		return self.SingleMetadata(AtomRights,name)
	
	def AtomTitle(self,name=None):
		return self.SingleMetadata(AtomTitle,name)
	
	def AtomUpdated(self,name=None):
		return self.SingleMetadata(AtomUpdated,name)
	

class AtomPerson(AtomElement):
	"""atomPersonConstruct =
		atomCommonAttributes,
		(element atom:name { text }
			& element atom:uri { atomUri }?
			& element atom:email { atomEmailAddress }?
			& extensionElement*)
	"""
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent,name)
		self.name=None
		self.uri=None
		self.email=None

	def GetChildren(self):
		children=[]
		if self.name:
			children.append(self.name)
		if self.uri:
			children.append(self.uri)
		if self.email:
			children.append(self.email)
		return children+AtomElement.GetChildren(self)
		
	def AtomName(self,name=None):
		if self.name:
			child=self.name
		else:
			child=AtomName(self,name)
			self.name=child
		return child

	def AtomURI(self,name=None):
		if self.uri:
			child=self.uri
		else:
			child=AtomURI(self,name)
			self.uri=child
		return child
		
	def AtomEmail(self,name=None):
		if self.email:
			child=self.email
		else:
			child=AtomEmail(self,name)
			self.email=child
		return child

	
class AtomAuthor(AtomPerson):
	XMLNAME=atom_author

class AtomContributor(AtomPerson):
	XMLNAME=atom_contributor
	
class AtomCategory(AtomElement):
	XMLNAME=atom_category
	
	def __init__(self,parent,name=None):
		AtomElement.__init__(self,parent,name)
		self.scheme=None
		self.term=None
	
	def GetAttributes(self):
		attrs=AtomElement.GetAttributes(self)
		if self.scheme:
			attrs['scheme']=self.scheme
		if self.term:
			attrs['term']=self.term
		return attrs
		
	def Set_scheme(self,value):
		self.scheme=value

	def Set_term(self,value):
		self.term=value

		
class AtomSource(AtomEntity):
	"""
	element atom:source {
         atomCommonAttributes,
         (atomAuthor*
          & atomCategory*
          & atomContributor*
          & atomGenerator?
          & atomIcon?
          & atomId?
          & atomLink*
          & atomLogo?
          & atomRights?
          & atomSubtitle?
          & atomTitle?
          & atomUpdated?
          & extensionElement*)
      }
	"""
	XMLNAME=atom_source

	def GetGenerator(self):
		return self.metadata.get('generator',None)
		
	def GetIcon(self):
		return self.metadata.get('icon',None)
		
	def GetLogo(self):
		return self.metadata.get('logo',None)
		
	def GetSubtitle(self):
		return self.metadata.get('subtitle',None)
	
	def AtomGenerator(self,name=None):
		return self.SingleMetadata(AtomGenerator,name)

	def AtomIcon(self,name=None):
		return self.SingleMetadata(AtomIcon,name)
		
	def AtomLogo(self,name=None):
		return self.SingleMetadata(AtomLogo,name)
	
	def AtomSubtitle(self,name=None):
		return self.SingleMetadata(AtomSubtitle,name)
	
			
class AtomFeed(AtomSource):
	"""Represents an Atom feed.
	
		element atom:feed {
			atomCommonAttributes,
			(atomAuthor*
			& atomCategory*
			& atomContributor*
			& atomGenerator?
			& atomIcon?
			& atomId
			& atomLink*
			& atomLogo?
			& atomRights?
			& atomSubtitle?
			& atomTitle
			& atomUpdated
			& extensionElement*),
			atomEntry*
		}
	"""
	XMLNAME=atom_feed
	
	def __init__(self,parent,name=None):
		AtomSource.__init__(self,parent,name)
		self.entries=[]

	def GetChildren(self):
		children=AtomEntity.GetChildren(self)
		return children+self.entries

	def AtomEntry(self,name=None):
		child=AtomEntry(self,name)
		self.entries.append(child)
		return child

		
class AtomEntry(AtomEntity):
	"""
		element atom:entry {
			atomCommonAttributes,
			(atomAuthor*
			& atomCategory*
			& atomContent?
			& atomContributor*
			& atomId
			& atomLink*
			& atomPublished?
			& atomRights?
			& atomSource?
			& atomSummary?
			& atomTitle
			& atomUpdated
			& extensionElement*)
		}
	"""
	XMLNAME=atom_entry

	def __init__(self,parent,name=None):
		AtomEntity.__init__(self,parent,name)
		self.content=None
		
	def GetPublished(self):
		return self.metadata.get('published',[])
		
	def GetSource(self):
		return self.metadata.get('source',None)
			
	def GetSummary(self):
		return self.metadata.get('summary',None)
					
	def GetContent(self):
		return self.content

	def GetChildren(self):
		children=AtomEntity.GetChildren(self)
		if self.content:
			children.append(self.content)
		return children
	
	def AtomPublished(self,name=None):
		return self.SingleMetadata(AtomPublished,name)
		
	def AtomSource(self,name=None):
		return self.SingleMetadata(AtomSource,name)
		
	def AtomSummary(self,name=None):
		return self.SingleMetadata(AtomSummary,name)
		
	def AtomContent(self,name):
		if self.content:
			return self.content
		else:
			child=AtomContent(self,name)
			self.content=child
			return child
				

class AtomDocument(xmlns.XMLNSDocument):
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,defaultNS=ATOM_NAMESPACE,**args)

	def GetElementClass(self,name):
		return AtomDocument.classMap.get(name,AtomDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	classMap={
		atom_author:AtomAuthor,
		atom_category:AtomCategory,
		atom_content:AtomContent,
		atom_contributor:AtomContributor,
		atom_entry:AtomEntry,
		atom_feed:AtomFeed,
		atom_generator:AtomGenerator,
		atom_icon:AtomIcon,
		atom_id:AtomId,
		atom_link:AtomLink,
		atom_logo:AtomLogo,
		atom_name:AtomName,
		atom_rights:AtomRights,
		atom_source:AtomSource,
		atom_subtitle:AtomSubtitle,
		atom_summary:AtomSummary,
		atom_title:AtomTitle,
		atom_updated:AtomUpdated			
		}