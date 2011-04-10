#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml20081126 as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsdatatypes
import pyslet.html40_19991224 as html

xsi=xsdatatypes

import string
import os.path, urllib, urlparse
from types import StringTypes

IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/imsqti_v2p1"
IMSQTI_SCHEMALOCATION="http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
IMSQTI_ITEM_RESOURCETYPE="imsqti_item_xmlv2p1"


class QTIError(Exception): pass
class QTIDeclarationError(QTIError): pass
class QTIValidityError(QTIError): pass

QTI_HTMLProfile=[
	'abbr','acronym','address','blockquote','br','cite','code','dfn','div',
	'em','h1','h2','h3','h4','h5','h6','kbd','p','pre','q','samp','span',
	'strong','var','dl','dt','dd','ol','ul','li','object','param','b','big',
	'hr','i','small','sub','sup','tt','caption','col','colgroup','table',
	'tbody','tfoot','thead','td','th','tr','img','a']

def FixHTMLNamespace(e):
	"""Fixes e and all children to be in the QTINamespace"""
	if e.ns==html.XHTML_NAMESPACE:
		name=(IMSQTI_NAMESPACE,e.xmlname.lower())
		if QTIDocument.classMap.has_key(name):
			e.SetXMLName(name)
	children=e.GetChildren()
	for e in children:
		if type(e) in StringTypes:
			continue
		FixHTMLNamespace(e)
		
	
def MakeValidNCName(name):
	"""This function takes a string that is supposed to match the production for
	NCName in XML and forces to to comply by replacing illegal characters with
	'_', except the ':' which is replaced with a hyphen for compatibility with
	previous versions of the QTI migraiton script.  If name starts with a valid
	name character but not a valid name start character, it is prefixed with '_'
	too."""
	if name:
		goodName=[]
		if not xmlns.IsNameStartChar(name[0]):
			goodName.append('_')
		elif name[0]==':':
			# Previous versions of the migrate script didn't catch this problem
			# as a result, we deviate from its broken behaviour or using '-'
			goodName.append('_')			
		for c in name:
			if c==':':
				goodName.append('-')
			elif xmlns.IsNameChar(c):
				goodName.append(c)
			else:
				goodName.append('_')
		return string.join(goodName,'')
	else:
		return '_'


class QTIElement(xmlns.XMLNSElement):
	"""Basic element to represent all QTI elements""" 
	
	def AddToCPResource(self,cp,resource,baseURI):
		"""Adds any linked files that exist on the local file system to the content package."""
		for child in self.GetChildren():
			if isinstance(child,QTIElement):
				child.AddToCPResource(cp,resource,baseURI)


class QTIAssessmentItem(QTIElement):
	"""
	<xsd:attributeGroup name="assessmentItem.AttrGroup">
		<xsd:attribute name="identifier" type="string.Type" use="required"/>
		<xsd:attribute name="title" type="string.Type" use="required"/>
		<xsd:attribute name="label" type="string256.Type" use="optional"/>
		<xsd:attribute ref="xml:lang"/>
		<xsd:attribute name="adaptive" type="boolean.Type" use="required"/>
		<xsd:attribute name="timeDependent" type="boolean.Type" use="required"/>
		<xsd:attribute name="toolName" type="string256.Type" use="optional"/>
		<xsd:attribute name="toolVersion" type="string256.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="assessmentItem.ContentGroup">
		<xsd:sequence>
			<xsd:element ref="responseDeclaration" minOccurs="0" maxOccurs="unbounded"/>
			<xsd:element ref="outcomeDeclaration" minOccurs="0" maxOccurs="unbounded"/>
			<xsd:element ref="templateDeclaration" minOccurs="0" maxOccurs="unbounded"/>
			<xsd:element ref="templateProcessing" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="stylesheet" minOccurs="0" maxOccurs="unbounded"/>
			<xsd:element ref="itemBody" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="responseProcessing" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="modalFeedback" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(IMSQTI_NAMESPACE,'assessmentItem')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.metadata=QTIMetadata(None)
		self.identifier=None
		self.title=None
		self.label=None
		self.adaptive=False
		self.timeDependent=False
		self.declarations={}
		self.QTIItemBody=None
		
	def GetAttributes(self):
		attrs=QTIElement.GetAttributes(self)
		if self.identifier:
			attrs['identifier']=self.identifier
		if self.title:
			attrs['title']=self.title
		if self.label:
			attrs['label']=self.label
		attrs['adaptive']=xsdatatypes.EncodeBoolean(self.adaptive)
		attrs['timeDependent']=xsdatatypes.EncodeBoolean(self.timeDependent)
		return attrs
		
	def Set_identifier(self,value):
		self.identifier=value
		
	def Set_title(self,value):
		self.title=value
	
	def Set_label(self,value):
		self.label=value
	
	def Set_adaptive(self,value):
		self.adaptive=xsdatatypes.DecodeBoolean(value)
		
	def Set_timeDependent(self,value):
		self.timeDependent=xsdatatypes.DecodeBoolean(value)
				
	def GetChildren(self):
		children=[]
		vars=self.declarations.keys()
		vars.sort()
		for v in vars:
			children.append(self.declarations[v])
		xmlns.OptionalAppend(children,self.QTIItemBody)
		return children+QTIElement.GetChildren(self)
	
	def QTIResponseDeclaration(self):
		# Not linked properly to us until it is finished.
		return QTIResponseDeclaration(self)
		
	def RegisterDeclaration(self,declaration):
		if self.declarations.has_key(declaration.identifier):
			raise QTIDeclarationError
		else:
			self.declarations[declaration.identifier]=declaration
		
	def AddToContentPackage(self,cp,lom,dName=None):
		"""Adds a resource and associated files to the content package."""
		resourceID=cp.manifest.GetUniqueID(self.identifier)
		resource=cp.manifest.root.resources.CPResource()
		resource.SetID(resourceID)
		resource.Set_type(IMSQTI_ITEM_RESOURCETYPE)
		resourceMetadata=resource.CPMetadata()
		resourceMetadata.AdoptChild(lom)
		resourceMetadata.AdoptChild(self.metadata.Copy())
		# Security alert: we're leaning heavily on MakeValidNCName assuming it returns a good file name
		fPath=MakeValidNCName(resourceID).encode('utf-8')+'.xml'
		if dName:
			fPath=os.path.join(dName,fPath)
		fPath=cp.GetUniqueFile(fPath)
		# This will be the path to the file in the package
		fullPath=os.path.join(cp.dPath,fPath)
		uri='file://'+urllib.pathname2url(fullPath)
		# Turn this file path into a relative URL in the context of the new resource
		href=resource.RelativeURI(uri)
		f=cp.CPFile(resource,href)
		resource.SetEntryPoint(f)
		for child in self.GetChildren():
			if isinstance(child,QTIElement):
				child.AddToCPResource(cp,resource,uri)
		return uri
	
		

class QTIResponseDeclaration(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'responseDeclaration')
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.identifier=None
	
	def GetAttributes(self):
		attrs=QTIElement.GetAttributes(self)
		if self.identifier:
			attrs['identifier']=self.identifier
		return attrs
		
	def Set_identifier(self,value):
		self.identifier=value
	
	def GotChildren(self):
		self.parent.RegisterDeclaration(self)


class QTIBodyElement(QTIElement):
	"""Abstract class to represent elements within content.
	
	<xsd:attributeGroup name="bodyElement.AttrGroup">
		<xsd:attribute name="id" type="identifier.Type" use="optional"/>
		<xsd:attribute name="class" use="optional">
			<xsd:simpleType>
				<xsd:list itemType="styleclass.Type"/>
			</xsd:simpleType>
		</xsd:attribute>
		<xsd:attribute ref="xml:lang"/>
		<xsd:attribute name="label" type="string256.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.id=None
		self.styleClass=None
		self.label=None
	
	def GetAttributes(self):
		attrs=QTIElement.GetAttributes(self)
		if self.id: attrs['id']=self.id
		if self.styleClass: attrs['class']=self.styleClass
		if self.label: attrs['label']=self.label
		return attrs
		
	def Set_id(self,value):
		self.id=value
		
	def Set_class(self,value):
		self.styleClass=value
		
	def Set_label(self,value):
		self.label=value

class QTIObjectFlowMixin: pass
QTIInlineMixin=html.XHTMLInlineMixin
QTIBlockMixin=html.XHTMLBlockMixin
QTIFlowMixin=html.XHTMLFlowMixin		# xml:base is handled automatically for all elements

class QTISimpleInline(QTIInlineMixin,QTIBodyElement):
	# need to constrain content to QTIInlineMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,QTIInlineMixin):
			return QTIBodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise QTIValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		

class QTISimpleBlock(QTIBlockMixin,QTIBodyElement):
	# need to constrain content to QTIBlockMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,QTIBlockMixin):
			return QTIBodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise QTIValidityError("%s in %s"%(repr(name),self.__class__.__name__))		

class QTIAtomicInline(QTIInlineMixin,QTIBodyElement): pass

class QTIAtomicBlock(QTIBlockMixin,QTIBodyElement):
	# need to constrain content to QTIInlineMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,QTIInlineMixin):
			return QTIBodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise QTIValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))

	
class QTIItemBody(QTIBodyElement):
	"""Represents the itemBody element.
	
	<xsd:attributeGroup name="itemBody.AttrGroup">
		<xsd:attributeGroup ref="bodyElement.AttrGroup"/>
	</xsd:attributeGroup>
	
	<xsd:group name="itemBody.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="block.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""	
	XMLNAME=(IMSQTI_NAMESPACE,'itemBody')
	XMLCONTENT=xmlns.XMLElementContent	


class QTIRubricBlock(QTISimpleBlock):
	"""Represent the rubricBlock element.

	<xsd:attributeGroup name="rubricBlock.AttrGroup">
		<xsd:attributeGroup ref="simpleBlock.AttrGroup"/>
		<xsd:attribute name="view" use="required">
			<xsd:simpleType>
				<xsd:list itemType="view.Type"/>
			</xsd:simpleType>
		</xsd:attribute>
	</xsd:attributeGroup>
	
	<xsd:group name="rubricBlock.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="simpleBlock.ContentGroup"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(IMSQTI_NAMESPACE,'rubricBlock')
	XMLCONTENT=xmlns.XMLElementContent

	QTI_VIEWS={
		"author":'author',
		"candidate":'candidate',
		"proctor":'proctor',
		"scorer":'scorer',
		"testconstructor":'testConstructor',
		"tutor":'tutor'		
		}
		
	def __init__(self,parent):
		QTISimpleBlock.__init__(self,parent)
		self.view={}
	
	def GetAttributes(self):
		attrs=QTISimpleBlock.GetAttributes(self)
		viewpoints=self.view.keys()
		viewpoints.sort()
		attrs['view']=string.join(viewpoints,' ')
		return attrs
		
	def Set_view(self,value):
		self.view={}
		viewpoints=value.split()
		for view in viewpoints:
			self.AddView(view)
	
	def AddView(self,view):
		view=view.strip()
		value=QTIRubricBlock.QTI_VIEWS.get(view.lower(),'')
		if value:
			self.view[value]=1
		else:
			raise ValueError("illegal value for view: %s"%view)

		
class QTIMetadata(QTIElement):
	"""Represents the qtiMetadata element used in content packages.
	
	<xsd:group name="qtiMetadata.ContentGroup">
		<xsd:sequence>
			<xsd:element ref="itemTemplate" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="timeDependent" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="composite" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="interactionType" minOccurs="0" maxOccurs="unbounded"/>
			<xsd:element ref="feedbackType" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="solutionAvailable" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="toolName" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="toolVersion" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="toolVendor" minOccurs="0" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""	
	XMLNAME=(IMSQTI_NAMESPACE,'qtiMetadata')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QMDItemTemplate=None
		self.QMDTimeDependent=None
		self.QMDComposite=None
		self.QMDInteractionType=[]
		self.QMDFeedbackType=None
		self.QMDSolutionAvailable=None
		self.QMDToolName=None
		self.QMDToolVersion=None
		self.QMDToolVendor=None
	
	def GetChildren(self):
		children=[]
		xmlns.OptionalAppend(children,self.QMDItemTemplate)
		xmlns.OptionalAppend(children,self.QMDTimeDependent)
		xmlns.OptionalAppend(children,self.QMDComposite)
		children=children+self.QMDInteractionType
		xmlns.OptionalAppend(children,self.QMDFeedbackType)
		xmlns.OptionalAppend(children,self.QMDSolutionAvailable)
		xmlns.OptionalAppend(children,self.QMDToolName)
		xmlns.OptionalAppend(children,self.QMDToolVersion)
		xmlns.OptionalAppend(children,self.QMDToolVendor)
		return children+QTIElement.GetChildren(self)

class QMDItemTemplate(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'itemTemplate')

class QMDTimeDependent(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'timeDependent')

class QMDComposite(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'composite')

class QMDInteractionType(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'interactionType')

class QMDFeedbackType(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'feedbackType')

class QMDSolutionAvailable(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'solutionAvailable')

class QMDToolName(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'toolName')

class QMDToolVersion(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'toolVersion')

class QMDToolVendor(QTIElement):
	XMLNAME=(IMSQTI_NAMESPACE,'toolVendor')

		
class QTIDocument(xmlns.XMLNSDocument):
	classMap={}
	
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,defaultNS=IMSQTI_NAMESPACE,**args)
		self.SetNSPrefix(xsi.XMLSCHEMA_NAMESPACE,'xsi')
		if isinstance(self.root,QTIElement):
			self.root.SetAttribute((xsi.XMLSCHEMA_NAMESPACE,'schemaLocation'),IMSQTI_NAMESPACE+' '+IMSQTI_SCHEMALOCATION)
			
	def GetElementClass(self,name):
		return QTIDocument.classMap.get(name,QTIDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	def AddToContentPackage(self,cp,metadata,dName=None):
		"""Copies this QTI document into a content package and returns the resource ID used.
		
		An optional directory name can be specified in which to put the resource files."""
		if not isinstance(self.root,QTIAssessmentItem):
			print self.root
			raise TypeError
		# We call the elemement's AddToContentPackage method which returns the new base URI
		# of the document.
		baseURI=self.root.AddToContentPackage(cp,metadata,dName)
		self.SetBase(baseURI)
		# Finish by writing out the document to the new baseURI
		self.Create()

xmlns.MapClassElements(QTIDocument.classMap,globals())
# also add in the profile of HTML but with the namespace rewritten to ours
for name in QTI_HTMLProfile:
	eClass=html.XHTMLDocument.classMap.get((html.XHTML_NAMESPACE,name),None)
	if eClass:
		QTIDocument.classMap[(IMSQTI_NAMESPACE,name)]=eClass
