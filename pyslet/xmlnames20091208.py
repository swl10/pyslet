#! /usr/bin/env python

from pyslet.xml20081126 import *

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


class XMLNSParser(XMLParser):

	def __init__(self,entity=None):
		XMLParser.__init__(self,entity)
		self.nsStack=[]
	
	def ExpandQName(self,qname,useDefault=True):
		xname=qname.split(':')
		if len(xname)==1:
			if qname=='xmlns':
				return (XMLNS_NAMESPACE,'')
			elif useDefault:
				nsURI=None
				for ns in self.nsStack:
					nsURI=ns.get('',None)
					if nsURI:
						break
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
				nsURI=None
				for ns in self.nsStack:
					nsURI=ns.get(nsprefix,None)
					if nsURI:
						break
				return (nsURI,local)		
		else:
			# something wrong with this element
			raise XMLNSError("Illegal QName: %s"%qname)
			
	def ParseElement(self):
		"""[39] element ::= EmptyElemTag | STag content ETag
		
		We override this one method to handle namespaces.  The method
		used is a two-pass scan of the attributes, the first time
		we identify any namespace declarations and add a new dictionary
		to a stack of namespace dictionaries.  The second pass is used
		to create a new dictionary for the attributes using expanded
		names."""
		qname,attrs,empty=self.ParseSTag()
		# go through and find namespace declarations
		ns={}
		nsAttrs={}
		for aname in attrs.keys():
			if aname.startswith('xmlns'):
				if len(aname)==5:
					# default ns declaration
					ns['']=attrs[aname]
				elif aname[5]==':':
					# ns prefix declaration
					ns[aname[6:]]=attrs[aname]
		if ns:
			self.nsStack[0:0]=[ns]
		for aname in attrs.keys():
			expandedName=self.ExpandQName(aname,False)
			if expandedName[0]!=XMLNS_NAMESPACE:
				# hide xmlns: attributes from the document
				nsAttrs[expandedName]=attrs[aname]
		expandedName=self.ExpandQName(qname)
		if empty:
			self.doc.startElementNS(expandedName,qname,nsAttrs)
			self.doc.endElementNS(expandedName,qname)
		else:
			self.doc.startElementNS(expandedName,qname,nsAttrs)
			self.ParseContent()
			endQName=self.ParseETag()
			if qname!=endQName:
				raise XMLWellFormedError("Expected <%s/>"%qname)
			self.doc.endElementNS(expandedName,qname)
		if ns:
			self.nsStack=self.nsStack[1:]
		return qname
	

class XMLNSElement(XMLElement):
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
		XMLElement.__init__(self,parent,name)

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
		
		Overrides the default behaviour by accepting a (ns,name) tuple
		in addition to a plain string/unicode string name.
		
		Custom setters are called using the inherited behaviour only for attributes
		with no namespace.  Also, XML namespace generates custom setter calls of the
		form Set_xml_aname for compatibility with the default implementation.
		
		Custom setter cannot be defined for attriubtes from other namespaces,
		these are subjet to default processing defined by XMLElement's
		SetAttribute implementation."""
		if type(name) in types.StringTypes:
			ns=None
			aname=name
		else:
			ns,aname=name
		if ns is None:
			if getattr(self,"XMLATTR_"+aname,False) or getattr(self,"Set_"+aname,False):
				return XMLElement.SetAttribute(self,aname,value)				
		elif ns==XML_NAMESPACE:
			if getattr(self,"Set_xml_"+aname,False):
				return XMLElement.SetAttribute(self,'xml_'+aname,value)		
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
				
	def GetNSPrefix(self,ns,nsList):
		for i in xrange(len(nsList)):
			if nsList[i][0]==ns:
				# Now run backwards to check that prefix is not in use
				used=False
				j=i
				while j:
					j=j-1
					if nsList[j][1]==nsList[i][1]:
						used=True
						break
				if not used:
					return nsList[i][1]
		return None
	
	def SetNSPrefix(self,ns,prefix,attributes,nsList,escapeFunction):
		if not prefix:
			# None or empty string: so we don't make this the default if it has
			# a preferred prefix defined in the document.
			doc=self.GetDocument()
			if doc:
				newprefix=doc.SuggestPrefix(ns)
				for nsi,prefixi in nsList:
					if prefixi==newprefix:
						newprefix=None
						break
				if newprefix:
					prefix=newprefix
		if prefix is None:
			prefix=self.SuggestNewPrefix(nsList)
		if prefix:
			aname='xmlns:'+prefix
			prefix=prefix+':'
			nsList[0:0]=[(ns,prefix)]
		else:
			nsList[0:0]=[(ns,'')]
			aname='xmlns'
		attributes.append('%s=%s'%(aname,escapeFunction(ns,True)))
		return prefix
	
	def SuggestNewPrefix(self,nsList,stem='ns'):
		"""Return an unused prefix of the form stem#, stem defaults to ns.
		
		We could be more economical here, sometimes one declaration hides another
		allowing us to reuse a prefix with a lower index, however this is likely
		to be too confusing as it will lead to multiple namespaces being bound to
		the same prefix in the same document (which we only allow for the default
		namespace).  We don't prevent the reverse though, if a namespace prefix
		has been hidden by being redeclared some other way, we may be forced to
		assign it a new prefix and hence have multiple prefixes bound to the same
		namespace in the same document."""
		i=0
		ns=1
		prefix="%s%i:"%(stem,ns)
		while i<len(nsList):
			if nsList[i][1]==prefix:
				i=0
				ns=ns+1
				prefix="%s%i:"%(stem,ns)
			else:
				i=i+1
		return "%s%i"%(stem,ns)
		
	def WriteXMLAttributes(self,attributes,nsList,escapeFunction=EscapeCharData):
		"""Adds strings representing the element's attributes
		
		attributes is a list of unicode strings.  Attributes should be appended
		as strings of the form 'name="value"' with values escaped appropriately
		for XML output.
		
		ns is a dictionary of pre-existing declared namespace prefixes.  This
		includes any declarations made by the current element."""
		attrs=self.GetAttributes()
		keys=attrs.keys()
		keys.sort()
		for a in keys:
			if type(a) in types.StringTypes:
				aname=a
				prefix=''
			else:
				ns,aname=a
				prefix=self.GetNSPrefix(ns,nsList)
			if prefix is None:
				prefix=self.SetNSPrefix(ns,None,attributes,nsList,escapeFunction)
			attributes.append(u'%s%s=%s'%(prefix,aname,escapeFunction(attrs[a],True)))
			
	def WriteXML(self,writer,escapeFunction=EscapeCharData,indent='',tab='\t',nsList=None):
		if tab:
			ws='\n'+indent
			indent=indent+tab
		else:
			ws=''
		if not self.PrettyPrint():
			# inline all children
			indent=''
			tab=''
		if nsList is None:
			nsList=[(XML_NAMESPACE,"xml:")]
		attributes=[]
		nsListLen=len(nsList)
		if self.ns:
			# look up the element prefix
			prefix=self.GetNSPrefix(self.ns,nsList)
			if prefix is None:
				# We need to declare our namespace
				prefix=self.SetNSPrefix(self.ns,'',attributes,nsList,escapeFunction)
		else:
			prefix=''
		self.WriteXMLAttributes(attributes,nsList,escapeFunction)
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
			for child in children:
				if type(child) in types.StringTypes:
					# We force encoding of carriage return as these are subject to removal
					writer.write(escapeFunction(child))
					# if we have character data content skip closing ws
					ws=''
				else:
					child.WriteXML(writer,escapeFunction,indent,tab,nsList)
			if not tab:
				# if we weren't tabbing children we need to skip closing white space
				ws=''
			writer.write(u'%s</%s%s>'%(ws,prefix,self.xmlname))
		else:
			writer.write(u'%s<%s%s%s/>'%(ws,prefix,self.xmlname,attributes))
		nsList=nsList[-nsListLen:]


class XMLNSDocument(XMLDocument):
	def __init__(self, defaultNS=None, **args):
		"""Initialises a new XMLDocument from optional keyword arguments.
		
		In addition to the named arguments supported by XMLElement, the
		defaultNS used for elements without an associated namespace
		can be specified on construction."""
		self.defaultNS=defaultNS
		self.prefixTable={}
		self.nsTable={}
		XMLDocument.__init__(self,**args)
		self.parser.setFeature(handler.feature_namespaces,1)
		
	def SetDefaultNS(self,ns):
		self.defaultNS=ns
	
	def SetNSPrefix(self,ns,prefix):
		"""Sets the preferred prefix for the given namespace, ns.
		
		If the prefix or the ns has already been mapped then ValueError is
		raised."""
		if self.prefixTable.has_key(prefix):
			raise ValueError
		self.prefixTable[prefix]=ns
		self.nsTable[ns]=prefix

	def SuggestPrefix(self,ns):
		return self.nsTable.get(ns,None)
		
	def GetElementClass(self,name):
		"""Returns a class object suitable for representing <name>
		
		name is a tuple of (namespace, name), this overrides the
		behaviour of XMLDocument, in which name is a string.
		
		The default implementation returns XMLNSElement."""
		return XMLNSElement
				
	def ReadFromEntity(self,e):
		self.cObject=self
		self.objStack=[]
		self.data=[]
		parser=XMLNSParser(e)
		parser.ParseDocument(self)

	def startElementNS(self, name, qname, attrs):
		parent=self.cObject
		self.objStack.append(self.cObject)
		if self.data:
			parent.AddData(string.join(self.data,''))
			self.data=[]
		if name[0] is None:
			name=(self.defaultNS,name[1])
		eClass=self.GetElementClass(name)
		try:
			self.cObject=parent.ChildElement(eClass,name)
		except TypeError:
			raise TypeError("Can't create %s in %s"%(eClass.__name__,parent.__class__.__name__))
		if self.cObject is None:
			raise ValueError("None when creating %s in %s"%(eClass.__name__,parent.__class__.__name__))
		for attr in attrs.keys():
			if attr[0] is None:
				self.cObject.SetAttribute(attr[1],attrs[attr])
			else:
				self.cObject.SetAttribute(attr,attrs[attr])

	def endElementNS(self,name,qname):
		if self.objStack:
			parent=self.objStack.pop()
		else:
			parent=None
		if self.data:
			self.cObject.AddData(string.join(self.data,''))
			self.data=[]
		self.cObject.GotChildren()
		self.cObject=parent
