#! /usr/bin/env python

from pyslet.xml20081126 import *

XML_NAMESPACE="http://www.w3.org/XML/1998/namespace"
xmlns_base=(XML_NAMESPACE,'base')
xmlns_lang=(XML_NAMESPACE,'lang')
xmlns_space=(XML_NAMESPACE,'space')

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


class XMLNSElement(XMLElement):
	def __init__(self,parent):
		XMLElement.__init__(self,parent)
		self.ns=None

	def SetXMLName(self,xmlname):
		if type(xmlname) in types.StringTypes:
			self.ns=None
			self.xmlname=xmlname
		else:
			self.ns,self.xmlname=xmlname

	def GetBase(self):
		return self.attrs.get(xmlns_base,None)
	
	def SetBase(self,base):
		if base is None:
			self.attrs.pop(xmlns_base,None)
		else:
			self.attrs[xmlns_base]=base
	
	def GetLang(self):
		return self.attrs.get(xmlns_lang,None)
	
	def SetLang(self,lang):
		if lang is None:
			self.attrs.pop(xmlns_lang,None)
		else:
			self.attrs[xmlns_lang]=lang
	
	def GetSpace(self):
		return self.attrs.get(xmlns_space,None)
	
	def SetSpace(self,space):
		if space is None:
			self.attrs.pop(xmlns_space,None)
		else:
			self.attrs[xmlns_space]=space
	
	def IsValidName(self,value):
		return IsValidNCName(value)
	
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
	
	def SetNSPrefix(self,ns,prefix,attributes,nsList):
		if prefix:
			aname='xmlns:'+prefix
			prefix=prefix+':'
			nsList[0:0]=[(ns,prefix)]
		else:
			nsList[0:0]=[(ns,'')]
			aname='xmlns'
		attributes.append('%s=%s'%(aname,saxutils.quoteattr(ns)))
		return prefix
		
	def WriteXMLAttributes(self,attributes,nsList):
		"""Adds strings representing the element's attributes
		
		attributes is a list of unicode strings.  Attributes should be appended
		as strins of the form 'name="value"' with values escaped appropriately
		for XML output.
		
		ns is a dictionary of pre-existing declared namespace prefixes.  This
		includes any declarations made by the current element."""
		keys=self.attrs.keys()
		keys.sort()
		for a in keys:
			if type(a) in types.StringTypes:
				aname=a
				prefix=''
			else:
				ns,aname=a
				prefix=self.GetNSPrefix(ns,nsList)
				if prefix is None:
					prefix=self.SetNSPrefix(ns,'???',attributes,nsList)
			attributes.append('%s%s=%s'%(prefix,aname,saxutils.quoteattr(self.attrs[a])))
		
	def WriteXML(self,f,nsList=None):
		if nsList is None:
			nsList=[(XML_NAMESPACE,"xml:")]
		attributes=[]
		nsListLen=len(nsList)
		if self.ns:
			# look up the element prefix
			prefix=self.GetNSPrefix(self.ns,nsList)
			if prefix is None:
				# We need to declare our namespace
				prefix=self.SetNSPrefix(self.ns,'',attributes,nsList)
		else:
			prefix=''
		self.WriteXMLAttributes(attributes,nsList)
		if attributes:
			attributes[0:0]=['']
			attributes=string.join(attributes,' ')
		else:
			attributes=''
		if self.children:
			f.write('<%s%s%s>'%(prefix,self.xmlname,attributes))
			for child in self.children:
				if type(child) in types.StringTypes:
					f.write(child)
				else:
					child.WriteXML(f,nsList)
			f.write('</%s>'%self.xmlname)
		else:
			f.write('<%s%s%s/>'%(prefix,self.xmlname,attributes))
		nsList=nsList[-nsListLen:]


class XMLNSDocument(XMLDocument):
	def __init__(self, defaultNS=None, **args):
		"""Initialises a new XMLDocument from optional keyword arguments.
		
		In addition to the named arguments supported by XMLElement, the
		defaultNS used for elements without an associated namespace
		can be specified on construction."""
		self.defaultNS=defaultNS
		XMLDocument.__init__(self,**args)
		self.parser.setFeature(handler.feature_namespaces,1)
		
	def SetDefaultNS(self,ns):
		self.defaultNS=ns
		
	def GetElementClass(self,name):
		"""Returns a class object suitable for representing <name>
		
		name is a tuple of (namespace, name), this overrides the
		behaviour of XMLDocument, in which name is a string.
		
		The default implementation returns XMLNSElement."""
		return XMLNSElement
				
	def startElementNS(self, name, qname, attrs):
		parent=self.cObject
		self.objStack.append(self.cObject)
		if self.data:
			parent.AddChild(string.join(self.data,''))
			self.data=[]
		if name[0] is None:
			name=(self.defaultNS,name[1])
		#print name, qname, attrs
		#eClass=self.classMap.get(name,self.classMap.get((name[0],None),XMLElement))
		eClass=self.GetElementClass(name)
		self.cObject=eClass(parent)
		self.cObject.SetXMLName(name)
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
			self.cObject.AddChild(string.join(self.data,''))
			self.data=[]
		self.cObject.GotChildren()
		parent.AddChild(self.cObject)
		self.cObject=parent
