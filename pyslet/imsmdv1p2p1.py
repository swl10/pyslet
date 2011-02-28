#! /usr/bin/env python
"""This module implements the IMS LRM 1.2.1 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns

IMSLRM_NAMESPACE="http://www.imsglobal.org/xsd/imsmd_v1p2"
IMSLRM_SCHEMALOCATION="http://www.imsglobal.org/xsd/imsmd_v1p2p4.xsd"

IMSLRM_NAMESPACE_ALIASES={
#	"http://www.imsproject.org/metadata":"1.1",
#	"http://www.imsproject.org/metadata/":"1.1",
	"http://www.imsproject.org/xsd/imsmd_rootv1p2":IMSLRM_NAMESPACE,
	"http://www.imsglobal.org/xsd/imsmd_rootv1p2p1":IMSLRM_NAMESPACE}

lrm_aggregationlevel=(IMSLRM_NAMESPACE,'aggregationlevel')
lrm_annotation=(IMSLRM_NAMESPACE,'annotation')
lrm_catalogentry=(IMSLRM_NAMESPACE,'catalogentry')
lrm_classification=(IMSLRM_NAMESPACE,'classification')
lrm_coverage=(IMSLRM_NAMESPACE,'coverage')
lrm_description=(IMSLRM_NAMESPACE,'description')
lrm_educational=(IMSLRM_NAMESPACE,'educational')
lrm_general=(IMSLRM_NAMESPACE,'general')
lrm_identifier=(IMSLRM_NAMESPACE,'identifier')
lrm_keyword=(IMSLRM_NAMESPACE,'keyword')
lrm_language=(IMSLRM_NAMESPACE,'language')
lrm_langstring=(IMSLRM_NAMESPACE,'langstring')
lrm_lifecycle=(IMSLRM_NAMESPACE,'lifecycle')
lrm_lom=(IMSLRM_NAMESPACE,'lom')
lrm_metametadata=(IMSLRM_NAMESPACE,'metametadata')
lrm_relation=(IMSLRM_NAMESPACE,'relation')
lrm_structure=(IMSLRM_NAMESPACE,'structure')
lrm_technical=(IMSLRM_NAMESPACE,'technical')
lrm_title=(IMSLRM_NAMESPACE,'title')

lrm_wildcard=(IMSLRM_NAMESPACE,None)
	
md_lom=(IMSLRM_NAMESPACE,'lom')

class LRMException(Exception): pass

class LRMElement(xmlns.XMLNSElement):
	"""Basic element to represent all CP elements"""
	pass

class LOM(LRMElement):
	XMLNAME=md_lom
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
	XMLNAME=lrm_general
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
	

class LangString(LRMElement):
	XMLNAME=lrm_langstring
		
class LangStringList(LRMElement):	

	def __init__(self,parent):
		LRMElement.__init__(self,parent)
		self.langStrings=[]

	def GetChildren(self):
		return self.langStrings
	
	def LangString(self):
		s=LangString(self)
		self.langStrings.append(s)
		return s
		

class LOMIdentifier(LRMElement):
	XMLNAME=lrm_identifier
	
class LOMTitle(LRMElement):
	XMLNAME=lrm_title

class LOMCatalogEntry(LRMElement):
	XMLNAME=lrm_catalogentry

class LOMLanguage(LRMElement):
	XMLNAME=lrm_language
	
class LOMDescription(LangStringList):
	XMLNAME=lrm_description
	XMLCONTENT=xmlns.XMLElementContent

class LOMKeyword(LangStringList):
	XMLNAME=lrm_keyword

class LOMCoverage(LangStringList):
	XMLNAME=lrm_coverage

class LOMStructure(LangStringList):
	XMLNAME=lrm_structure

class LOMAggregationLevel(LangStringList):
	XMLNAME=lrm_aggregationlevel


class LOMLifecycle(LRMElement):
	XMLNAME=lrm_lifecycle
	
class LOMMetaMetadata(LRMElement):
	XMLNAME=lrm_metametadata
	
class LOMTechnical(LRMElement):
	XMLNAME=lrm_technical
	
class LOMEducational(LRMElement):
	XMLNAME=lrm_educational
	
class LOMRelation(LRMElement):
	XMLNAME=lrm_relation
	
class LOMAnnotation(LRMElement):
	XMLNAME=lrm_annotation
	
class LOMClassification(LRMElement):
	XMLNAME=lrm_classification
	
	
classMap={
	lrm_wildcard:LRMElement,
	lrm_aggregationlevel:LOMAggregationLevel,
	lrm_annotation:LOMAnnotation,
	lrm_catalogentry:LOMCatalogEntry,
	lrm_classification:LOMClassification,
	lrm_coverage:LOMCoverage,
	lrm_description:LOMDescription,
	lrm_educational:LOMEducational,
	lrm_general:LOMGeneral,
	lrm_identifier:LOMIdentifier,
	lrm_keyword:LOMKeyword,
	lrm_language:LOMLanguage,
	lrm_langstring:LangString,
	lrm_lifecycle:LOMLifecycle,
	lrm_lom:LOM,
	lrm_metametadata:LOMMetaMetadata,
	lrm_relation:LOMRelation,
	lrm_structure:LOMStructure,
	lrm_technical:LOMTechnical,
	lrm_title:LOMTitle
	}

def GetElementClass(name):
	ns,xmlname=name
	if IMSLRM_NAMESPACE_ALIASES.has_key(ns):
		ns=IMSLRM_NAMESPACE_ALIASES[ns]
	return classMap.get((ns,xmlname),classMap.get((ns,None),xmlns.XMLNSElement))
