#! /usr/bin/env python
"""This module implements the CSDL specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541474(v=prot.10)"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.rfc2396 as uri
import pyslet.xsdatatypes20041028 as xsi

import itertools

EDM_NAMESPACE="http://schemas.microsoft.com/ado/2009/11/edm"		#: Namespace to use for CSDL elements

EDM_NAMESPACE_ALIASES={
	EDM_NAMESPACE: [
		"http://schemas.microsoft.com/ado/2006/04/edm",		#: CSDL Schema 1.0
		"http://schemas.microsoft.com/ado/2007/05/edm",		#: CSDL Schema 1.1
		"http://schemas.microsoft.com/ado/2008/09/edm"]		#: CSDL Schema 2.0
	}

	
class CSDLElement(xmlns.XMLNSElement):
	pass

class Using(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Using')

class Assocation(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Assocation')

class Property(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Property')

	XMLATTR_Name='name'
	XMLATTR_Type='type'
	XMLATTR_Nullable=('nullable',xsi.DecodeBoolean,xsi.DecodeBoolean)
	XMLATTR_DefaultValue='defaultValue'
	XMLATTR_MaxLength=('maxLength',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_FixedLength=('fixedLength',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_Precision='precision'
	XMLATTR_Scale='scale'
	XMLATTR_Unicode='unicode'
	XMLATTR_Collation='collation'
	XMLATTR_SRID='SRID'
	XMLATTR_CollectionKind='collectionKind'
	XMLATTR_ConcurrencyMode='concurrencyMode'

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.type="Edm.String"
		self.nullable=True
		self.defaultValue=None
		self.maxLength=None
		self.fixedLength=None
		self.precision=None
		self.scale=None
		self.unicode=None
		self.collation=None
		self.SRID=None
		self.collectionKind=None
		self.concurrencyMode=None
		self.TypeRef=None
		self.Documentation=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]


class NavigationProperty(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'NavigationProperty')
	
	XMLATTR_Name='name'
	XMLATTR_Relationship='relationship'
	XMLATTR_ToRole='toRole'
	XMLATTR_FromRole='fromRole'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.relationship=None
		self.toRole=None
		self.fromRole=None
		self.Documentation=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]


class EntityKey(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'EntityKey')

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.PropertyRef=[]	


class PropertyRef(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'PropertyRef')
	
	XMLATTR_Name='name'

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name='Default'


class Type(CSDLElement):
	XMLATTR_Name='name'
	XMLATTR_BaseType='baseType'
	XMLATTR_Abstract=('abstract',xsi.DecodeBoolean,xsi.EncodeBoolean)
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.baseType=None
		self.abstract=False
		self.Documentation=None
		self.Property=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
		
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.Property,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

		
class EntityType(Type):
	XMLNAME=(EDM_NAMESPACE,'EntityType')

	def __init__(self,parent):
		Type.__init__(self,parent)
		self.Key=None
		self.NavigationProperty=[]
		
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		if self.Key: yield self.Key
		for child in itertools.chain(
			self.Property,
			self.NavigationProperty,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	
class ComplexType(Type):
	XMLNAME=(EDM_NAMESPACE,'ComplexType')


class Multiplicity:
	ZeroToOne=0
	One=1
	Many=2
	Encode={0:'0..1',1:'1',2:'*'}
	
MutliplicityMap={
	'0..1': Multiplicity.ZeroToOne,
	'1': Multiplicity.One,
	'*': Multiplicity.Many
	}

def DecodeMultiplicity(src):
	return MutliplicityMap.get(src.strip(),None)

def EncodeMultiplicity(value):
	return Multiplicity.Encode.get(value,'')


class End(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'End')
	
	XMLATTR_Type='type'
	XMLATTR_Role='role'
	XMLATTR_Multiplicity=('multiplicity',DecodeMultiplicity,EncodeMultiplicity)
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.type=None
		self.role=None
		self.multiplicity=1
		self.Documentation=None
		self.OnDelete=None
	
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		if self.OnDelete: yield self.OnDelete
		for child in CSDLElement.GetChildren(self): yield child


class Association(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Association')

	XMLATTR_Name='name'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.Documentation=None
		self.End=[]
		self.ReferentialConstraint=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]

	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in self.End: yield child
		if self.ReferentialConstraint: yield self.ReferentialConstraint
		for child in itertools.chain(
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child


class EntityContainer(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'EntityContainer')

class Function(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Function')

class Annotations(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Annotations')

class ValueTerm(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'ValueTerm')


class Schema(CSDLElement):
	"""Represents the Edmx root element."""
	XMLNAME=(EDM_NAMESPACE,'Schema')

	XMLATTR_Namespace='namespace'
	XMLATTR_Alias='alias'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.nameTable={}
		self.namespace="Default"
		self.alias=None
		self.Using=[]
		self.Assocation=[]
		self.ComplexType=[]
		self.EntityType=[]
		self.EntityContainer=[]
		self.Function=[]
		self.Annotations=[]
		self.ValueTerm=[]
	
	def __getitem__(self,key):
		return self.nameTable[key]
			
	def GetChildren(self):
		return itertools.chain(
			self.Using,
			self.Association,
			self.ComplexType,
			self.EntityType,
			self.EntityContainer,
			self.Function,
			self.Annotations,
			self.ValueTerm,
			CSDLElement.GetChildren(self))

	def ContentChanged(self):
		for t in self.EntityType+self.ComplexType:
			self.nameTable[t.name]=t
		