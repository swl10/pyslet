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
atom_feed=(ATOM_NAMESPACE,'feed')
atom_generator=(ATOM_NAMESPACE,'generator')
atom_id=(ATOM_NAMESPACE,'id')
atom_link=(ATOM_NAMESPACE,'link')
atom_name=(ATOM_NAMESPACE,'name')
atom_rights=(ATOM_NAMESPACE,'rights')
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
	def __init__(self,parent):
		xmlns.XMLNSElement.__init__(self,parent)
		self.SetXMLName((ATOM_NAMESPACE,None))
		
class AtomSingle:
	"""Mix-in class to identify single-valued metadata classes"""
	pass

class AtomMultiple:
	"""Mix-in class to identity multi-valued metadata classes"""
	pass
	
class AtomId(AtomElement,AtomSingle):
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.SetXMLName(atom_id)	
			
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
	def __init__(self,parent,value=None,type='text'):
		AtomElement.__init__(self,parent)
		if value is not None:
			self.SetValue(value)
		self.attrs['type']=type

	def GetType(self):
		return self.attrs['type']
	
	def SetType(self,type):
		if _ATOM_TEXT_TYPES.get(type,None):
			self.attrs['type']=type
		else:
			raise ValueError		

class AtomTitle(AtomText,AtomSingle):
	def __init__(self,parent,value=None,type='text'):
		AtomText.__init__(self,parent,value,type)
		self.SetXMLName(atom_title)

class AtomName(AtomText,AtomSingle):
	def __init__(self,parent,value=None,type='text'):
		AtomText.__init__(self,parent,value,type)
		self.SetXMLName(atom_name)

class AtomSubtitle(AtomText,AtomSingle):
	def __init__(self,parent,value=None,type='text'):
		AtomText.__init__(self,parent,value,type)
		self.SetXMLName(atom_subtitle)

class AtomRights(AtomText,AtomSingle):
	def __init__(self,parent,value=None,type='text'):
		AtomText.__init__(self,parent,value,type)
		self.SetXMLName(atom_rights)

class AtomSummary(AtomText,AtomSingle):
	def __init__(self,parent,value=None,type='text'):
		AtomText.__init__(self,parent,value,type)
		self.SetXMLName(atom_summary)


class AtomDate(AtomElement):
	"""
		atomDateConstruct =
			atomCommonAttributes,
			xsd:dateTime"""
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.date=iso8601.TimePoint()
	
	def GetValue(self):
		return self.date
		
	def GotChildren(self):
		# called when all children have been parsed
		self.date.SetFromString(AtomElement.GetValue(self))


class AtomUpdated(AtomDate,AtomSingle):
	def __init__(self,parent):
		AtomDate.__init__(self,parent)
		self.SetXMLName(atom_updated)

		
class AtomLink(AtomElement,AtomMultiple):
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.SetXMLName(atom_link)
		
	def GetHref(self):
		return self.attrs.get('href',None)

	def GetHrefLang(self):
		return self.attrs.get('hreflang',None)

	def GetRel(self):
		return self.attrs.get('rel',None)

	def GetType(self):
		return self.attrs.get('type',None)


class AtomGenerator(AtomElement,AtomSingle):
	"""
	atomGenerator = element atom:generator {
		atomCommonAttributes,
		attribute uri { atomUri }?,
		attribute version { text }?,
		text
	}"""
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.SetXMLName(atom_generator)
		
	def GetURI(self):
		return self.attrs.get('uri',None)
	
	def GetVersion(self):
		return self.attrs.get('version',None)
	

class AtomContent(AtomElement):
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.SetXMLName(atom_content)


class AtomEntity(AtomElement):
	"""Used to model more complex constructs which can have their own metadata"""
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.metadata={}

	def GetMetadata(self):
		return self.metadata
	
	def GetExtensionElement(self,key):
		return self.metadata.get(key,None)
		
	def AddChild(self,child):
		if isinstance(child,AtomSingle):
			self.metadata[child.xmlname]=child
		elif isinstance(child,AtomMultiple):
			if self.metadata.has_key(child.xmlname):
				self.metadata[child.xmlname].append(child)
			else:
				self.metadata[child.xmlname]=[child]
		elif isinstance(child,xmlns.XMLNSElement):
			key=(child.ns,child.xmlname)
			if self.metadata.has_key(key):
				self.metadata[key].append(child)
			else:
				self.metadata[key]=[child]
		else:
			AtomElement.AddChild(self,child)


class AtomPerson(AtomEntity):
	"""atomPersonConstruct =
		atomCommonAttributes,
		(element atom:name { text }
			& element atom:uri { atomUri }?
			& element atom:email { atomEmailAddress }?
			& extensionElement*)
	"""
	def __init__(self,parent):
		AtomEntity.__init__(self,parent)
	
	def GetName(self):
		return self.metadata.get('name',None)
	
	def GetURI(self):
		return self.metadata.get('uri',None)
	
	def GetEmail(self):
		return self.metadata.get('email',None)


class AtomAuthor(AtomPerson,AtomMultiple):
	def __init__(self,parent):
		AtomPerson.__init__(self,parent)
		self.SetXMLName(atom_author)

	
class AtomCategory(AtomElement):
	def __init__(self,parent):
		AtomElement.__init__(self,parent)
		self.SetXMLName(atom_category)

	def GetScheme(self):
		return self.attrs.get('scheme',None)
	
	def GetTerm(self):
		return self.attrs.get('term',None)
		
class AtomFeed(AtomEntity):
	"""
	atomFeed =
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
	def __init__(self,parent):
		AtomEntity.__init__(self,parent)
		self.SetXMLName(atom_feed)
		self.entries=[]

	def GetAuthors(self):
		return self.metadata.get('author',[])
			
	def GetCategories(self):
		return self.metadata.get('category',[])
		
	def GetContributors(self):
		return self.metadata.get('contributor',[])

	def GetGenerator(self):
		return self.metadata.get('generator',None)
		
	def GetIcon(self):
		return self.metadata.get('icon',None)
		
	def GetId(self):
		return self.metadata.get('id',None)
		
	def GetLinks(self):
		return self.metadata.get('link',[])

	def GetLogo(self):
		return self.metadata.get('logo',None)
		
	def GetRights(self):
		return self.metadata.get('rights',None)
		
	def GetSubtitle(self):
		return self.metadata.get('subtitle',None)
	
	def GetTitle(self):
		return self.metadata.get('title',None)
	
	def GetUpdated(self):
		return self.metadata.get('updated',None)
		
	def GetEntries(self):
		return self.entries
	
	def AddChild(self,child):
		if isinstance(child,AtomEntry):
			self.entries.append(child)
		else:
			AtomEntity.AddChild(self,child)

	
class AtomEntry(AtomEntity):
	"""
		atomEntry =
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
	def __init__(self,parent):
		AtomEntity.__init__(self,parent)
		self.SetXMLName(atom_entry)
		self.content=None
		
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

	def GetPublished(self):
		return self.metadata.get('published',[])
		
	def GetRights(self):
		return self.metadata.get('rights',None)

	def GetSource(self):
		return self.metadata.get('source',None)
			
	def GetSummary(self):
		return self.metadata.get('summary',None)
					
	def GetTitle(self):
		return self.metadata.get('title',None)
	
	def GetUpdated(self):
		return self.metadata.get('updated',None)
		
	def GetContent(self):
		return self.content
			
	def AddChild(self,child):
		if isinstance(child,AtomContent):
			self.content=child
		else:
			AtomEntity.AddChild(self,child)


class AtomDocument(xmlns.XMLNSDocument):
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,defaultNS=ATOM_NAMESPACE,**args)

	def GetElementClass(self,name):
		return AtomDocument.classMap.get(name,AtomDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	classMap={
		atom_author:AtomAuthor,
		atom_category:AtomCategory,
		atom_entry:AtomEntry,
		atom_feed:AtomFeed,
		atom_generator:AtomGenerator,
		atom_id:AtomId,
		atom_link:AtomLink,
		atom_name:AtomName,
		atom_rights:AtomRights,
		atom_subtitle:AtomSubtitle,
		atom_summary:AtomSummary,
		atom_title:AtomTitle,
		atom_updated:AtomUpdated			
		}