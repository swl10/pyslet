#! /usr/bin/env python
"""This module implements the IMS LRM 1.2.1 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns

try:
	import vobject
except ImportError:
	vobject=None

	
IMSLRM_NAMESPACE="http://www.imsglobal.org/xsd/imsmd_v1p2"
IMSLRM_SCHEMALOCATION="http://www.imsglobal.org/xsd/imsmd_v1p2p4.xsd"

IMSLRM_NAMESPACE_ALIASES={
#	"http://www.imsproject.org/metadata":"1.1",
#	"http://www.imsproject.org/metadata/":"1.1",
	"http://www.imsproject.org/xsd/imsmd_rootv1p2":IMSLRM_NAMESPACE,
	"http://www.imsglobal.org/xsd/imsmd_rootv1p2p1":IMSLRM_NAMESPACE}

LOM_SOURCE="LOMv1.0"
LOM_UNKNOWNSOURCE="None"


class LRMException(Exception): pass

class LRMElement(xmlns.XMLNSElement):
	"""Basic element to represent all CP elements"""
	pass

class LangString(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'langstring')
	def __init__(self,parent,value=None):
		LRMElement.__init__(self,parent)
		if value is not None:
			self.SetValue(value)
		
class LangStringList(LRMElement):	

	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.langStrings=[]

	def GetChildren(self):
		return self.langStrings
	
	def LangString(self,value=None):
		s=LangString(self,value)
		self.langStrings.append(s)
		return s

	def GetLangString(self,lang=None):
		if lang is None:
			for s in self.langStrings:
				if s.GetLang() is None:
					return s
			return None
		else:
			for s in self.langStrings:
				if s.GetLang()==lang:
					return s
			lang=lang.split('-')[0]
			for s in self.langStrings:
				sLang=s.GetLang().split('-')[0]
				if sLang==lang:
					return s
		return None

	def AddString(self,lang,value):
		s=self.GetLangString(lang)
		if s is None:
			s=self.LangString(value)
			if lang:
				s.SetLang(lang)
		else:
			s.AddData('; '+value)			
		return s

			
class LRMSource(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'source')

	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LangString=LangString(self)
	
	def GetChildren(self):
		return [self.LangString]

		
class LRMValue(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'value')

	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LangString=LangString(self)
	
	def GetChildren(self):
		return [self.LangString]

	
class LRMSourceValue(LRMElement):
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LRMSource=LRMSource(self)
		self.LRMValue=LRMValue(self)
	
	def GetChildren(self):
		return [self.LRMSource,self.LRMValue]

		
class LOM(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'lom')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.general=None
		self.lifecycle=None
		self.metametadata=None
		self.technical=None
		self.educational=None
		self.rights=None
		self.relations=[]
		self.annotations=[]
		self.classifications=[]
	
	def GetChildren(self):
		children=[]
		if self.general: 
			children.append(self.general)
		if self.lifecycle: 
			children.append(self.lifecycle)
		if self.metametadata: 
			children.append(self.metametadata)
		if self.technical: 
			children.append(self.technical)
		if self.educational: 
			children.append(self.educational)
		if self.rights: 
			children.append(self.rights)
		return children+self.relations+self.annotations+self.classifications+LRMElement.GetChildren(self)
		
	def LOMGeneral(self):
		if not self.general:
			self.general=LOMGeneral(self)
		return self.general
	
	def LOMLifecycle(self):
		if not self.lifecycle:
			self.lifecycle=LOMLifecycle(self)
		return self.lifecycle
	
	def LOMMetaMetadata(self):
		if not self.metametadata:
			self.metametadata=LOMMetaMetadata(self)
		return self.metametadata
	
	def LOMTechnical(self):
		if not self.technical:
			self.technical=LOMTechnical(self)
		return self.technical
	
	def LOMEducational(self):
		if not self.educational:
			self.educational=LOMEducational(self)
		return self.educational
	
	def LOMRelation(self):
		r=LOMRelation(self)
		self.relations.append(r)
		return r

	def LOMAnnotation(self):
		a=LOMAnnotation(self)
		self.annotations.append(a)
		return a
		
	def LOMClassification(self):
		c=LOMClassification(self)
		self.classifications.append(c)
		return c

class LOMGeneral(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'general')
	XMLCONTENT=xmlns.XMLElementContent

	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.identifier=None
		self.title=None
		self.catalogEntries=[]
		self.languages=[]
		self.description=[]
		self.keywords=[]
		self.coverage=[]
		self.structure=None
		self.aggregationLevel=None
	
	def GetChildren(self):
		children=[]
		if self.identifier:
			children.append(self.identifier)
		if self.title:
			children.append(self.title)
		children=children+self.catalogEntries+self.languages+self.description+self.keywords+self.coverage
		if self.structure:
			children.append(self.structure)
		if self.aggregationLevel:
			children.append(self.aggregationLevel)
		return children+LRMElement.GetChildren(self)

	def LOMIdentifier(self):
		if not self.identifier:
			self.identifier=LOMIdentifier(self)
		return self.identifier
	
	def LOMTitle(self):
		if not self.title:
			self.title=LOMTitle(self)
		return self.title
	
	def LOMCatalogEntry(self):
		c=LOMCatalogEntry(self)
		self.catalogEntries.append(c)
		return c

	def LOMLanguage(self):
		l=LOMLanguage(self)
		self.languages.append(l)
		return l

	def LOMDescription(self):
		d=LOMDescription(self)
		self.description.append(d)
		return d
	
	def LOMKeyword(self):
		kw=LOMKeyword(self)
		self.keywords.append(kw)
		return kw
	
	def LOMCoverage(self):
		c=LOMCoverage(self)
		self.coverage.append(c)
		return c

	def LOMStructure(self):
		if not self.structure:
			self.structure=LOMStructure(self)
		return self.structure
	
	def LOMAggregationLevel(self):
		if not self.aggregationLevel:
			self.aggregationLevel=LOMAggregationLevel(self)
		return self.aggregationLevel
	

class LOMIdentifier(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'identifier')
	
class LOMTitle(LangStringList):
	XMLNAME=(IMSLRM_NAMESPACE,'title')

class LOMCatalogEntry(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'catalogentry')

class LOMLanguage(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'language')
	
class LOMDescription(LangStringList):
	XMLNAME=(IMSLRM_NAMESPACE,'description')
	XMLCONTENT=xmlns.XMLElementContent

class LOMKeyword(LangStringList):
	XMLNAME=(IMSLRM_NAMESPACE,'keyword')

class LOMCoverage(LangStringList):
	XMLNAME=(IMSLRM_NAMESPACE,'coverage')

class LOMStructure(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'structure')

class LOMAggregationLevel(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'aggregationlevel')

class LOMLifecycle(LRMElement):
	"""
	<xsd:sequence>
		<xsd:element ref = "version" minOccurs = "0"/>
		<xsd:element ref = "status" minOccurs = "0"/>
		<xsd:element ref = "contribute" minOccurs = "0" maxOccurs = "unbounded"/>
		<xsd:group ref = "grp.any"/>
	</xsd:sequence>
	"""	
	XMLNAME=(IMSLRM_NAMESPACE,'lifecycle')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LOMVersion=None
		self.LOMStatus=None
		self.LOMContribute=[]
	
	def GetChildren(self):
		children=[]
		xmlns.OptionalAppend(children,self.LOMVersion)
		xmlns.OptionalAppend(children,self.LOMStatus)
		return children+self.LOMContribute+LRMElement.GetChildren(self)

class LOMVersion(LangStringList):
	XMLNAME=(IMSLRM_NAMESPACE,'version')

class LOMStatus(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'status')
	
class LOMContribute(LRMElement):
	"""
	<xsd:sequence>
		<xsd:element ref = "role"/>
		<xsd:element ref = "centity" minOccurs = "0" maxOccurs = "unbounded"/>
		<xsd:element ref = "date" minOccurs = "0"/>
		<xsd:group ref = "grp.any"/>
	</xsd:sequence>
	"""
	XMLNAME=(IMSLRM_NAMESPACE,'contribute')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LOMRole=LOMRole(self)
		self.LOMCEntity=[]
		self.LOMDate=None
	
	def GetChildren(self):
		children=[self.LOMRole]+self.LOMCEntity
		xmlns.OptionalAppend(children,self.LOMDate)
		return children+LRMElement.GetChildren(self)

class LOMRole(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'role')

class LOMCEntity(LRMElement):
	"""
	"""
	XMLNAME=(IMSLRM_NAMESPACE,'centity')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LOMVCard=LOMVCard(self)
	
	def GetChildren(self):
		return [self.LOMVCard]+LRMElement.GetChildren(self)

class LOMVCard(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'vcard')

	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.vcard=None
	
	def GetValue(self):
		return self.vcard
	
	def SetValue(self,vcard):
		self.vcard=vcard
		LRMElement.SetValue(self,vcard.serialize())
		
	def GotChildren(self):
		# called when all children have been parsed
		if vobject is not None:
			src=LRMElement.GetValue(self)
			if src is not None and src.strip():
				self.vcard=vobject.readOne(src)
			else:
				self.vcard=None
				
class LOMMetaMetadata(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'metametadata')
	
class LOMTechnical(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'technical')
	
class LOMEducational(LRMElement):
	"""
    <xsd:complexType name="educationalType" mixed="true">
      <xsd:sequence>
         <xsd:element ref="interactivitytype" minOccurs="0"/>
         <xsd:element ref="learningresourcetype" minOccurs="0" maxOccurs="unbounded"/>
         <xsd:element ref="interactivitylevel" minOccurs="0"/>
         <xsd:element ref="semanticdensity" minOccurs="0"/>
         <xsd:element ref="intendedenduserrole" minOccurs="0" maxOccurs="unbounded"/>
         <xsd:element ref="context" minOccurs="0" maxOccurs="unbounded"/>
         <xsd:element ref="typicalagerange" minOccurs="0" maxOccurs="unbounded"/>
         <xsd:element ref="difficulty" minOccurs="0"/>
         <xsd:element ref="typicallearningtime" minOccurs="0"/>
         <xsd:element ref="description" minOccurs="0"/>
         <xsd:element ref="language" minOccurs="0" maxOccurs="unbounded"/>
         <xsd:group ref="grp.any"/>
      </xsd:sequence>
    </xsd:complexType>
	"""	
	XMLNAME=(IMSLRM_NAMESPACE,'educational')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LOMInteractivityType=None
		self.LOMLearningResourceType=[]
		self.LOMInteractivityLevel=None
		self.LOMSemanticDensity=None
		self.LOMIntendedEndUserRole=[]
		self.LOMContext=[]
		self.LOMTypicalAgeRange=[]
		self.LOMDifficulty=None
		self.LOMTypicalLearningTime=None
		self.LOMDescription=None
		self.LOMLanguage=[]

	def GetChildren(self):
		children=[]
		xmlns.OptionalAppend(children,self.LOMInteractivityType)
		children=children+self.LOMLearningResourceType
		xmlns.OptionalAppend(children,self.LOMInteractivityLevel)
		xmlns.OptionalAppend(children,self.LOMSemanticDensity)
		children=children+self.LOMIntendedEndUserRole+self.LOMContext+self.LOMTypicalAgeRange
		xmlns.OptionalAppend(children,self.LOMDifficulty)
		xmlns.OptionalAppend(children,self.LOMTypicalLearningTime)
		xmlns.OptionalAppend(children,self.LOMDescription)
		children=children+self.LOMLanguage+LRMElement.GetChildren(self)
		return children

		
class LOMInteractivityType(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'interactivitytype')
	
class LOMLearningResourceType(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'learningresourcetype')

class LOMInteractivityLevel(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'interactivitylevel')

class LOMSemanticDensity(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'semanticdensity')

class LOMIntendedEndUserRole(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'intendedenduserrole')

class LOMContext(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'context')

class LOMTypicalAgeRange(LangStringList):
	XMLNAME=(IMSLRM_NAMESPACE,'typicalagerange')

class LOMDifficulty(LRMSourceValue):
	XMLNAME=(IMSLRM_NAMESPACE,'difficulty')

class LOMTypicalLearningTime(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'typicallearningimte')


class LOMRelation(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'relation')
	
class LOMAnnotation(LRMElement):
	""" 
	<xsd:complexType name="annotationType" mixed="true">
      <xsd:sequence>
         <xsd:element ref="person" minOccurs="0"/>
         <xsd:element ref="date" minOccurs="0"/>
         <xsd:element ref="description" minOccurs="0"/>
         <xsd:group ref="grp.any"/>
      </xsd:sequence>
	</xsd:complexType>
	"""
	XMLNAME=(IMSLRM_NAMESPACE,'annotation')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.LOMPerson=None
		self.LOMDate=None
		self.LOMDescription=None
	
	def GetChildren(self):
		children=[]
		xmlns.OptionalAppend(children,self.LOMPerson)
		xmlns.OptionalAppend(children,self.LOMDate)
		xmlns.OptionalAppend(children,self.LOMDescription)
		return children+LRMElement.GetChildren(self)

	
class LOMClassification(LRMElement):
	XMLNAME=(IMSLRM_NAMESPACE,'classification')
	
	
classMap={
	(IMSLRM_NAMESPACE,None):LRMElement
	}

xmlns.MapClassElements(classMap,globals())

def GetElementClass(name):
	ns,xmlname=name
	if IMSLRM_NAMESPACE_ALIASES.has_key(ns):
		ns=IMSLRM_NAMESPACE_ALIASES[ns]
	return classMap.get((ns,xmlname),classMap.get((ns,None),xmlns.XMLNSElement))
