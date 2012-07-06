#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi

import string


IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/imsqti_v2p1"
"""The namespace used to recognise elements in XML documents."""

IMSQTI_SCHEMALOCATION="http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
"""The location of the QTI 2.1 schema file on the IMS website."""

IMSQTI_ITEM_RESOURCETYPE="imsqti_item_xmlv2p1"
"""The resource type to use for the QTI 2.1 items when added to content packages."""


class QTIError(Exception):
	"""Abstract class used for all QTI v2 exceptions."""
	pass

class QTIDeclarationError(QTIError):
	"""Error raised when a variable declaration is invalid."""
	pass

class ProcessingError(QTIError):
	"""Error raised when an invalid processing element is encountered."""
	pass

class QTIValidityError(QTIError): pass


class Shape(xsi.Enumeration):
	"""A value of a shape is always accompanied by coordinates and an associated
	image which provides a context for interpreting them::

		<xsd:simpleType name="shape.Type">
			<xsd:restriction base="xsd:NMTOKEN">
				<xsd:enumeration value="circle"/>
				<xsd:enumeration value="default"/>
				<xsd:enumeration value="ellipse"/>
				<xsd:enumeration value="poly"/>
				<xsd:enumeration value="rect"/>
			</xsd:restriction>
		</xsd:simpleType>
	
	Defines constants for the above types of Shape.  Usage example::

		Shape.Circle
	
	Note that::
		
		Shape.DEFAULT == Shape.default

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'circle':1,
		'default':2,
		'ellipse':3,
		'poly':4,
		'rect':5
		}
xsi.MakeEnumeration(Shape,'default')


class View(xsi.Enumeration):
	"""Used to represent roles when restricting view::
	
		<xsd:simpleType name="view.Type">
			<xsd:restriction base="xsd:NMTOKEN">
				<xsd:enumeration value="author"/>
				<xsd:enumeration value="candidate"/>
				<xsd:enumeration value="proctor"/>
				<xsd:enumeration value="scorer"/>
				<xsd:enumeration value="testConstructor"/>
				<xsd:enumeration value="tutor"/>
			</xsd:restriction>
		</xsd:simpleType>

	Defines constants for the above views.  Usage example::

		View.candidate
	
	There is no default view.  Views are represented in XML as space-separated
	lists of values.  Typical usage::
		
		view=View.DecodeValueDict("tutor scorer")
		# returns...
		{ View.tutor:'tutor', View.scorer:'scorer' }
		View.EncodeValueDict(view)
		# returns...
		"scorer tutor"

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'author':1,
		'candidate':2,
		'proctor':3,
		'scorer':4,
		'testConstructor':5,
		'tutor':6
		}
xsi.MakeEnumeration(View)
xsi.MakeLowerAliases(View)


class QTIElement(xmlns.XMLNSElement):
	"""Basic element to represent all QTI elements""" 
	
	def AddToCPResource(self,cp,resource,beenThere):
		"""We need to add any files with URL's in the local file system to the
		content package.

		beenThere is a dictionary we use for mapping URLs to File objects so
		that we don't keep adding the same linked resource multiple times.

		This implementation is a little more horrid, we avoid circular module
		references by playing dumb about our children.  HTML doesn't actually
		know anything about QTI even though QTI wants to define children for
		some XHTML elements so we pass the call only to "CP-Aware" elements."""
		for child in self.GetChildren():
			if hasattr(child,'AddToCPResource'):
				child.AddToCPResource(cp,resource,beenThere)


def ValidateIdentifier(value,prefix='_'):
	"""Decodes an identifier from a string::

		<xsd:simpleType name="identifier.Type">
			<xsd:restriction base="xsd:NCName"/>
		</xsd:simpleType>
	
	This function takes a string that is supposed to match the production for
	NCName in XML and forces it to comply by replacing illegal characters with
	'_', except the ':' which is replaced with a hyphen for compatibility with
	previous versions of the QTI migraiton script.  If name starts with a valid
	name character but not a valid name start character, it is prefixed with '_'
	too, but the prefix string used can be overridden."""
	if value:
		goodName=[]
		if not xmlns.IsNameStartChar(value[0]):
			goodName.append(prefix)
		elif value[0]==':':
			# Previous versions of the migrate script didn't catch this problem
			# as a result, we deviate from its broken behaviour of using '-'
			# by using the prefix too.
			goodName.append(prefix)			
		for c in value:
			if c==':':
				goodName.append('-')
			elif xmlns.IsNameChar(c):
				goodName.append(c)
			else:
				goodName.append('_')
		return string.join(goodName,'')
	else:
		return prefix


def GetTemplateRef(value):
	"""Given a string used to set an attribute of an *...orTemplateRef* type
	this function returns the name of the variable being referred to or None if
	the value does not look like a template variable reference."""
	if value.startswith('{') and value.endswith('}'):
		idValue=value[1:-1]
		if xsi.IsValidNCName(idValue):
			return idValue
	return None
