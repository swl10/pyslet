#! /usr/bin/env python
"""This module implements the CSDL specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541474(v=prot.10)"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.rfc2396 as uri
import pyslet.xsdatatypes20041028 as xsi


CSDL_NAMESPACE="http://schemas.microsoft.com/ado/2009/11/edm"		#: Namespace to use for CSDL elements

class CSDLElement(xmlns.XMLNSElement):
	pass

class Using(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'Using')

class Assocation(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'Assocation')

class ComplexType(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'ComplexType')


class Property(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'Property')
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"


class EntityType(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'EntityType')

	XMLATTR_Name='name'
	XMLATTR_BaseType='baseType'
	XMLATTR_Abstract=('abstract',xsi.DecodeBoolean,xsi.EncodeBoolean)
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.baseType=None
		self.abstract=False
		self.Documentation=None
		self.Key=None
		self.Property=[]
		self.NavigationProperty=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
		
	def GetChildren(self):
		children=[]
		return children+CSDLElement.GetChildren(self)

	
class EntityContainer(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'EntityContainer')

class Function(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'Function')

class Annotations(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'Annotations')

class ValueTerm(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'ValueTerm')

class AnnotationElement(CSDLElement):
	XMLNAME=(CSDL_NAMESPACE,'AnnotationElement')


class Schema(CSDLElement):
	"""Represents the Edmx root element."""
	XMLNAME=(CSDL_NAMESPACE,'Schema')

	XMLATTR_Namespace='namespace'
	XMLATTR_Alias='alias'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
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
		self.AnnotationElement=[]
	
	def GetChildren(self):
		children=self.Using+self.Association+self.ComplexType+self.EntityType+self.EntityContainer+\
			self.Function+self.Annotations+self.ValueTerm+self.AnnotationElement
		return children+CSDLElement.GetChildren(self)
	
		