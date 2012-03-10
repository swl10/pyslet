#! /usr/bin/env python

from pyslet.xml20081126.structures import *
from pyslet.xml20081126.parser import *

XML_NAMESPACE=u"http://www.w3.org/XML/1998/namespace"
XMLNS_NAMESPACE=u"http://www.w3.org/2000/xmlns/"
xmlns_base=(XML_NAMESPACE,'base')
xmlns_lang=(XML_NAMESPACE,'lang')
xmlns_space=(XML_NAMESPACE,'space')

class XMLNSError(XMLFatalError): pass


def IsValidNCName(name):
	if name:
		if not IsNameStartChar(name[0]) or name[0]==":":
			return False
		for c in name[1:]:
			if not IsNameChar(c) or c==":":
				return False
		return True
	else:
		return False


def AttributeNameKey(aname):
	"""A nasty function to make sorting attribute names predictable."""
	if type(aname) in StringTypes:
		return (None,unicode(aname))
	else:
		return aname


class XMLNSElementContainerMixin:
	"""Mixin class for shared attributes of elements and the document."""
	
	def __init__(self):
		self.prefixToNS={}
		"""A dictionary of mappings from namespace prefixes to namespace URIs."""
		self.nsToPrefix={}
		"""A dictionary of mappings from namespace URIs to prefixes."""

	def ResetPrefixMap(self,recursive=False):
		self.prefixToNS={}
		self.nsToPrefix={}
		if recursive:
			for child in self.GetChildren():
				if type(child) not in StringTypes:
					child.ResetPrefixMap(True)

	def GetPrefix(self,ns):
		"""Returns the prefix to use for the given namespace in the current
		context or None if no prefix is currently in force."""
		if ns==XML_NAMESPACE:
			return 'xml'
		prefix=None
		ei=self
		while prefix is None and ei is not None:
			prefix=ei.nsToPrefix.get(ns,None)
			if prefix is not None:
				# this is the prefix to use, unless it has been reused...
				ej=self
				while ej is not ei:
					if ej.prefixToNS.get(prefix,None) is not None:
						# so prefix has been reused, keep searching
						prefix=None
						break
					ej=ej.parent
			ei=ei.parent
		return prefix	
	
	def GetNS(self,prefix=''):
		"""Returns the namespace associated with prefix in the current context.
		
		Thie element searches back through the hierarchy until it fund the
		namespace in force or returns None if no definition for this prefix
		can be found."""
		if prefix=='xml':
			return XML_NAMESPACE
		ns=None
		ei=self
		while ei is not None:
			ns=ei.prefixToNS.get(prefix,None)
			if ns:
				break
			if prefix=='':
				ns=getattr(ei,'DefaultNS',None)
				if ns:
					break
			ei=ei.parent
		return ns

	def NewPrefix(self,stem='ns'):
		"""Return an unused prefix of the form stem#, stem defaults to ns.
		
		We could be more economical here, sometimes one declaration hides another
		allowing us to reuse a prefix with a lower index, however this is likely
		to be too confusing as it will lead to multiple namespaces being bound to
		the same prefix in the same document (which we only allow for the default
		namespace).  We don't prevent the reverse though, if a namespace prefix
		has been hidden by being redeclared some other way, we may be forced to
		assign it a new prefix and hence have multiple prefixes bound to the same
		namespace in the same document."""
		ns=1
		prefix=''
		while True:
			prefix="%s%s"%(stem,ns)
			if self.GetNS(prefix) is not None:
				ns=ns+1
			else:
				break
		return prefix
				
	def MakePrefix(self,ns,prefix=None):
		"""Creates a new mapping from ns to the given prefix."""
		if prefix is None:
			prefix=self.NewPrefix()
		if self.prefixToNS.has_key(prefix):
			raise ValueError
		self.prefixToNS[prefix]=ns
		self.nsToPrefix[ns]=prefix
		return prefix

	def GetPrefixMap(self):
		"""Returns the complete prefix to ns mapping in force at this element"""
		prefixMap={}
		ei=self
		while ei is not None:
			prefixList=ei.prefixToNS.keys()
			for prefix in prefixList:
				if not prefixMap.has_key(prefix):
					prefixMap[prefix]=ei.prefixToNS[prefix]
			ei=ei.parent
		return prefixMap

	def WriteNSAttributes(self,attributes,escapeFunction=EscapeCharData,root=False):
		"""Adds strings representing any namespace attributes"""
		nsAttributes=[]
		if root:
			prefixMap=self.GetPrefixMap()
		else:
			prefixMap=self.prefixToNS
		prefixList=prefixMap.keys()
		prefixList.sort()
		for prefix in prefixList:
			if prefix:
				nsAttributes.append(u'xmlns:%s=%s'%(prefix,escapeFunction(prefixMap[prefix],True)))
			else:
				nsAttributes.append(u'xmlns=%s'%escapeFunction(prefixMap[prefix],True))
		attributes[0:0]=nsAttributes
				
		
class XMLNSElement(XMLNSElementContainerMixin,Element):
	def __init__(self,parent,name=None):
		if type(name) in types.StringTypes:
			self.ns=None
		elif name is None:
			if hasattr(self.__class__,'XMLNAME'):
				self.ns,name=self.__class__.XMLNAME
			else:
				self.ns=self.name=None
		else:
			self.ns,name=name
		Element.__init__(self,parent,name)
		XMLNSElementContainerMixin.__init__(self)
		
	def SetXMLName(self,name):
		if type(name) in StringTypes:
			self.ns=None
			self.xmlname=name
		else:
			self.ns,self.xmlname=name

	def GetXMLName(self):
		return (self.ns,self.xmlname)

	def SetAttribute(self,name,value):
		"""Sets the value of an attribute.
		
		Overrides the default behaviour by accepting a (ns,name) tuple in
		addition to a plain string/unicode string name.  This method also
		catches the new namespace prefix mapping for the element which is placed
		in a special attribute by :py:meth:`XMLNSParser.ParseNSAttributes`.
		
		Custom setters are called using the inherited behaviour only for attributes
		with no namespace.  Also, XML namespace generates custom setter calls of the
		form Set_xml_aname for compatibility with the default implementation.
		
		Custom setter cannot be defined for attriubtes from other namespaces,
		these are subjet to default processing defined by Element's
		SetAttribute implementation."""
		if type(name) in types.StringTypes:
			if name==".ns":
				self.prefixToNS=nsMap=value
				self.nsToPrefix=dict(zip(nsMap.values(),nsMap.keys()))
				return
			ns=None
			aname=name
		else:
			ns,aname=name
		if ns is None:
			if getattr(self,"XMLATTR_"+aname,False) or getattr(self,"Set_"+aname,False):
				return Element.SetAttribute(self,aname,value)				
		elif ns==XML_NAMESPACE:
			if getattr(self,"Set_xml_"+aname,False):
				return Element.SetAttribute(self,'xml_'+aname,value)		
		if hasattr(self.__class__,'ID') and name==self.__class__.ID:
			self.SetID(value)
		else:
			self._attrs[name]=value

	def IsValidName(self,value):
		return IsValidNCName(value)

	def SortNames(self,nameList):
		nameList.sort(key=AttributeNameKey)

	def GetBase(self):
		return self._attrs.get(xmlns_base,None)
	
	def SetBase(self,base):
		if base is None:
			self._attrs.pop(xmlns_base,None)
		else:
			self._attrs[xmlns_base]=base
	
	def GetLang(self):
		return self._attrs.get(xmlns_lang,None)
	
	def SetLang(self,lang):
		if lang is None:
			self._attrs.pop(xmlns_lang,None)
		else:
			self._attrs[xmlns_lang]=lang
	
	def GetSpace(self):
		return self._attrs.get(xmlns_space,None)
	
	def SetSpace(self,space):
		if space is None:
			self._attrs.pop(xmlns_space,None)
		else:
			self._attrs[xmlns_space]=space
	
	def CheckOther(self,child,ns):
		"""Checks child to ensure it satisfies ##other w.r.t. the given ns"""
		return isinstance(child,XMLNSElement) and child.ns!=ns
					
	def WriteXMLAttributes(self,attributes,escapeFunction=EscapeCharData,root=False):
		"""Adds strings representing the element's attributes
		
		attributes is a list of unicode strings.  Attributes should be appended
		as strings of the form 'name="value"' with values escaped appropriately
		for XML output."""
		attrs=self.GetAttributes()
		keys=attrs.keys()
		keys.sort()
		for a in keys:
			if type(a) in types.StringTypes:
				aname=a
				prefix=''
			else:
				ns,aname=a
				prefix=self.GetPrefix(ns)
			if prefix is None:
				prefix=self.MakePrefix(ns)
			if prefix:
				prefix=prefix+':'
			attributes.append(u'%s%s=%s'%(prefix,aname,escapeFunction(attrs[a],True)))
		self.WriteNSAttributes(attributes,escapeFunction=EscapeCharData,root=root)
		
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
		if self.ns:
			# look up the element prefix
			prefix=self.GetPrefix(self.ns)
			if prefix is None:
				# We need to declare our namespace
				prefix=self.MakePrefix(self.ns,'')
		else:
			prefix=''
		if prefix:
			prefix=prefix+':'
		self.WriteXMLAttributes(attributes,escapeFunction,root=root)
		if attributes:
			attributes[0:0]=['']
			attributes=string.join(attributes,' ')
		else:
			attributes=''
		children=self.GetCanonicalChildren()
		if children:
			if type(children[0]) in StringTypes and len(children[0]) and IsS(children[0][0]):
				# First character is WS, so assume pre-formatted.
				indent=tab=''			
			writer.write(u'%s<%s%s%s>'%(ws,prefix,self.xmlname,attributes))
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
			writer.write(u'%s</%s%s>'%(ws,prefix,self.xmlname))
		else:
			writer.write(u'%s<%s%s%s/>'%(ws,prefix,self.xmlname,attributes))


class XMLNSDocument(XMLNSElementContainerMixin,Document):

	DefaultNS=None
	"""A special class attribute used to set the default namespace for elements
	created within the document that are parsed without an effective namespace
	declaration."""
	
	def __init__(self, **args):
		"""Initialises a new Document from optional keyword arguments."""
		Document.__init__(self,**args)
		XMLNSElementContainerMixin.__init__(self)

	def XMLParser(self,entity):
		"""Namespace documents use the special :py:class:`XMLNSParser`."""
		return XMLNSParser(entity)
		
	def GetElementClass(self,name):
		"""Returns a class object suitable for representing <name>
		
		name is a tuple of (namespace, name), this overrides the
		behaviour of Document, in which name is a string.
		
		The default implementation returns XMLNSElement."""
		return XMLNSElement
				

class XMLNSParser(XMLParser):

	def __init__(self,entity=None):
		"""A special parser for parsing documents that may use namespaces."""
		XMLParser.__init__(self,entity)
		
	def ExpandQName(self,qname,nsDefs,useDefault=True):
		"""Expands a QName, returning a (namespace, name) tuple.
		
		- *qname* is the qualified name
		- *nsDefs* is a mapping of prefix to namespace URIs used to expand the name
		- *useDefault* will return the default namespace for an unqualified name
		
		If *nsDefs* does not contain a suitable namespace definition then the
		context's existing prefix mapping is used, its parent's, and so on.

		If *useDefault* is False an unqualified name is returned with an None as
		the namespace (this is used when expanded attribute names)."""
		context=self.GetContext()
		xname=qname.split(':')
		if len(xname)==1:
			if qname=='xmlns':
				return (XMLNS_NAMESPACE,'')
			elif useDefault:
				nsURI=nsDefs.get('',None)
				if nsURI is None and context:
					nsURI=context.GetNS('')
				return (nsURI,qname)
			else:
				return (None,qname)
		elif len(xname)==2:
			nsprefix,local=xname
			if nsprefix=='xml':
				return (XML_NAMESPACE,local)
			elif nsprefix=='xmlns':
				return (XMLNS_NAMESPACE,local)
			else:
				nsURI=nsDefs.get(nsprefix,None)
				if nsURI is None and context:
					nsURI=context.GetNS(nsprefix)
				return (nsURI,local)		
		else:
			# something wrong with this element
			raise XMLNSError("Illegal QName: %s"%qname)

	def MatchXMLName(self,element,qname):
		"""Tests if *qname* is a possible name for this element.
		
		This method is used by the parser to determine if an end tag is the end
		tag of this element."""
		return element.GetXMLName()==self.ExpandQName(qname,{},True)

	def ParseNSAttributes(self,attrs):
		"""Takes a dictionary of attributes as returned by ParseSTag and finds
		any namespace prefix mappings returning them as a dictionary of
		prefix:namespace suitable for passing to :py:meth:`ExpandQName`.

		It also removes the namespace declarations from attrs and expands the
		attribute names into (ns,name) pairs.

		Finally, it declares a special attribute called '.ns' with the parsed
		prefix mapping dictionary as its value enabling the prefix mapping to be
		passed transparently to :py:meth:`XMLNSElement.SetAttribute` by
		:py:class:`XMLParser`. """
		ns={}
		for aname in attrs.keys():
			if aname.startswith('xmlns'):
				if len(aname)==5:
					# default ns declaration
					ns['']=attrs[aname]
				elif aname[5]==':':
					# ns prefix declaration
					ns[aname[6:]]=attrs[aname]
				del attrs[aname]
		for aname in attrs.keys():
			expandedName=self.ExpandQName(aname,ns,False)
			if expandedName[0]:
				# leave attributes with no namespace as strings, not tuples
				attrs[expandedName]=attrs[aname]
				del attrs[aname]
		# Finally, we hide the ns object in the list of attributes so we can retrieve it later
		# Note that '.' is not a valid NameStartChar so we will never collide with a real attribute
		attrs[".ns"]=ns
		return ns
		
	def GetSTagClass(self,qname,attrs=None):
		"""[40] STag: returns information suitable for starting element *name* in the current context
		
		Overridden to allow for namespace handling.
		"""
		if self.doc is None:
			if self.dtd is None:
				self.dtd=XMLDTD()
			if self.dtd.name is None:
				self.dtd.name=qname
			elif qname is None:
				# document starts with PCDATA, use name declared in DOCTYPE
				qname=self.dtd.name
		# go through attributes and process namespace declarations
		if attrs:
			ns=self.ParseNSAttributes(attrs)
		else:
			ns={}
		if qname:
			expandedName=self.ExpandQName(qname,ns)
		else:
			expandedName=None
		if self.doc is None:
			# we use the expanded name to find the document class, not the DTD
			documentClass=self.GetNSDocumentClass(expandedName)
			self.doc=documentClass()
		else:
			documentClass=self.doc.__class__
		context=self.GetContext()
		if qname and expandedName[0] is None:
			expandedName=(documentClass.DefaultNS,expandedName[1])
		if self.sgmlOmittag:
			if qname:
				stagClass=self.doc.GetElementClass(expandedName)
			else:
				stagClass=None
			elementClass=context.GetChildClass(stagClass)
			if elementClass is not stagClass:
				return elementClass,None,True
			else:
				return elementClass,expandedName,False
		else:
			return self.doc.GetElementClass(expandedName),expandedName,False
		
	NSDocumentClassTable={}
	"""A dictionary of class objects keyed on tuples of (namespace,element name).
	
	For more information see :py:meth:`GetNSDocumentClass` and
	:py:func:`RegisterNSDocumentClass`"""

	def GetNSDocumentClass(self,expandedName):
		"""Returns a class object derived from :py:class:`XMLNSDocument` suitable
		for representing a document with the given expanded name.

		This default implementation uses the expanded name to locate a class
		registered with :py:func:`RegisterNSDocumentClass`.  If an exact match
		is not found then wildcard matches are tried matching *only* the
		namespace and root element name in turn.

		If no document class can be found, :py:class:`XMLNSDocument` is
		returned."""
		rootName=dtd.name
		if expandedName[0] is None:
			docClass=XMLParser.NSDocumentClassTable.get(expandedName,None)
		else:
			docClass=XMLParser.NSDocumentClassTable.get(expandedName,None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((expandedName[0],None),None)
			if docClass is None:
				docClass=XMLParser.DocumentClassTable.get((None,expandedName[1]),None)
		if docClass is None:
			docClass=XMLNSDocument
		return docClass
	
def RegisterNSDocumentClass(docClass,expandedName):
	"""Registers a document class for use by :py:meth:`XMLNSParser.ParseElement`.
	
	This module maintains a single table of document classes which can be
	used to identify the correct class to use to represent a document based
	on the namespace and name of the root element (the expanded name).
	
	- *docClass* is the class object being registered, it must be derived from
	:py:class:`XMLNSDocument`

	- *expandedName* is a tuple of (namespace,name) representing the name of the
	root element.  If either (or both) components are None a wildcard is
	registered that will match any corresponding value.	"""
	XMLNSParser.NSDocumentClassTable[expandedName]=docClass
