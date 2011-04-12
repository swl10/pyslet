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


#
# Functions for basic types
#
def ValidateIdentifier(value):
	"""Decodes an identifier from a string.

	<xsd:simpleType name="identifier.Type">
		<xsd:restriction base="xsd:NCName"/>
	</xsd:simpleType>
	
	This function takes a string that is supposed to match the production for
	NCName in XML and forces to to comply by replacing illegal characters with
	'_', except the ':' which is replaced with a hyphen for compatibility with
	previous versions of the QTI migraiton script.  If name starts with a valid
	name character but not a valid name start character, it is prefixed with '_'
	too."""
	if value:
		goodName=[]
		if not xmlns.IsNameStartChar(value[0]):
			goodName.append('_')
		elif value[0]==':':
			# Previous versions of the migrate script didn't catch this problem
			# as a result, we deviate from its broken behaviour or using '-'
			goodName.append('_')			
		for c in value:
			if c==':':
				goodName.append('-')
			elif xmlns.IsNameChar(c):
				goodName.append(c)
			else:
				goodName.append('_')
		return string.join(goodName,'')
	else:
		return '_'

MakeValidNCName=ValidateIdentifier

QTI_SHOW=1
QTI_HIDE=2

def DecodeShowHide(value):
	"""Decodes a showHide value from a string.

	<xsd:simpleType name="showHide.Type">
		<xsd:restriction base="xsd:NMTOKEN">
			<xsd:enumeration value="hide"/>
			<xsd:enumeration value="show"/>
		</xsd:restriction>
	</xsd:simpleType>
	"""
	if value.lower()=='hide':
		return QTI_HIDE
	elif value.lower()=='show':
		return QTI_SHOW
	else:
		raise ValueError("Can't decode show/hide from %s"%value)

def EncodeShowHide(value):
	if value:
		return ["show","hide"][value-1]
	else:
		raise ValueError("Can't encode show/hide from %i"%value)

	
	

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
		attrs['adaptive']=xsi.EncodeBoolean(self.adaptive)
		attrs['timeDependent']=xsi.EncodeBoolean(self.timeDependent)
		return attrs
		
	def Set_identifier(self,value):
		self.identifier=value
		
	def Set_title(self,value):
		self.title=value
	
	def Set_label(self,value):
		self.label=value
	
	def Set_adaptive(self,value):
		self.adaptive=xsi.DecodeBoolean(value)
		
	def Set_timeDependent(self,value):
		self.timeDependent=xsi.DecodeBoolean(value)
				
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
		self.id=ValidateIdentifier(value)
		
	def Set_class(self,value):
		self.styleClass=value
		
	def Set_label(self,value):
		self.label=value

class QTIObjectFlowMixin: pass

QTIBlockMixin=html.XHTMLBlockMixin
QTIFlowMixin=html.XHTMLFlowMixin		# xml:base is handled automatically for all elements

class QTISimpleInline(html.XHTMLInlineMixin,QTIBodyElement):
	# need to constrain content to html.XHTMLInlineMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.XHTMLInlineMixin):
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

class QTIAtomicInline(html.XHTMLInlineMixin,QTIBodyElement): pass

class QTIAtomicBlock(QTIBlockMixin,QTIBodyElement):
	# need to constrain content to html.XHTMLInlineMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.XHTMLInlineMixin):
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

#
#	INTERACTIONS
#
class QTIInteraction(QTIBodyElement):
	"""Abstract class to act as a base for all interactions.

	<xsd:attributeGroup name="interaction.AttrGroup">
		<xsd:attributeGroup ref="bodyElement.AttrGroup"/>
		<xsd:attribute name="responseIdentifier" type="identifier.Type" use="required"/>
	</xsd:attributeGroup>
	"""
	def __init__(self,parent):
		QTIBodyElement.__init__(self,parent)
		self.responseIdentifier=''
	
	def Set_responseIdentifier(self,value):
		self.responseIdentifier=ValidateIdentifier(value)

	def GetAttributes(self):
		attrs=QTIBodyElement.GetAttributes(self)
		attrs['responseIdentifier']=self.responseIdentifier
		return attrs


class QTIInlineInteration(QTIInteraction,html.XHTMLInlineMixin):
	"""Abstract class for interactions that are treated as inline."""
	pass


class QTIBlockInteraction(QTIInteraction,html.XHTMLBlockMixin):
	"""Abstract class for interactions that are treated as blocks.
	
	<xsd:group name="blockInteraction.ContentGroup">
		<xsd:sequence>
			<xsd:element ref="prompt" minOccurs="0" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	def __init__(self,parent):
		QTIInteraction.__init__(self,parent)
		self.QTIPrompt=None
	

class QTIPrompt(QTIBodyElement):
	"""The prompt used in block interactions.

	<xsd:group name="prompt.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="inlineStatic.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(IMSQTI_NAMESPACE,'prompt')
	XMLCONTENT=xmlns.XMLMixedContent

	def __init__(self,parent):
		QTIBodyElement.__init__(self,parent)

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.XHTMLInlineMixin):
			return QTIBodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise QTIValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		


class QTIChoice(QTIBodyElement):		
	"""The base class used for all choices.

	<xsd:attributeGroup name="choice.AttrGroup">
		<xsd:attributeGroup ref="bodyElement.AttrGroup"/>
		<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		<xsd:attribute name="fixed" type="boolean.Type" use="optional"/>
		<xsd:attribute name="templateIdentifier" type="identifier.Type" use="optional"/>
		<xsd:attribute name="showHide" type="showHide.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	def __init__(self,parent):
		QTIBodyElement.__init__(self,parent)
		self.identifier=''
		self.fixed=None
		self.templateIdentifier=None
		self.showHide=None
	
	def Set_identifier(self,value):
		self.identifier=ValidateIdentifier(value)
	
	def Set_fixed(self,value):
		self.fixed=xsi.DecodeBoolean(value)
	
	def Set_templateIdentifier(self,value):
		self.templateIdentifier=ValidateIdentifier(value)
	
	def Set_showHide(self,value):
		self.showHide=DecodeShowHide(value)
	
	def GetAttributes(self):
		attrs=QTIBodyElement.GetAttributes(self)
		attrs['identifier']=self.identifier
		if self.fixed is not None: attrs['fixed']=xsi.EncodeBoolean(self.fixed)
		if self.templateIdentifier: attrs['templateIdentifier']=self.templateIdentifier
		if self.showHide is not None: attrs['showHide']=EncodeShowHide(self.showHide)
		return attrs


class QTIAssociableChoice(QTIChoice):
	"""The base class used for choices used in associations.
	
	<xsd:attributeGroup name="associableChoice.AttrGroup">
		<xsd:attributeGroup ref="choice.AttrGroup"/>
		<xsd:attribute name="matchGroup" use="optional">
			<xsd:simpleType>
				<xsd:list itemType="identifier.Type"/>
			</xsd:simpleType>
		</xsd:attribute>
	</xsd:attributeGroup>
	"""
	def __init__(self,parent):
		QTIChoice.__init__(self,parent)
		self.matchGroup=[]
	
	def Set_matchGroup(self,value):
		self.matchGroup=map(ValidateIdentifier,value.split())
	
	def GetAttributes(self):
		attrs=QTIChoice.GetAttributes(self)
		if self.matchGroup: attrs['matchGroup']=string.join(self.matchGroup,' ')
		return attrs


#
#		SIMPLE INTERACTIONS
#

class QTIChoiceInteraction(QTIBlockInteraction):
	"""Represents the choiceInteraction element.
	
	<xsd:attributeGroup name="choiceInteraction.AttrGroup">
		<xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
		<xsd:attribute name="shuffle" type="boolean.Type" use="required"/>
		<xsd:attribute name="maxChoices" type="integer.Type" use="required"/>
		<xsd:attribute name="minChoices" type="integer.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="choiceInteraction.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="blockInteraction.ContentGroup"/>
			<xsd:element ref="simpleChoice" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(IMSQTI_NAMESPACE,'choiceInteraction')
	XMLCONTENT=xmlns.XMLElementContent

	def __init__(self,parent):
		QTIBlockInteraction.__init__(self,parent)
		self.shuffle=False
		self.maxChoices=1
		self.minChoices=None
		self.QTISimpleChoice=[]
		
	def Set_shuffle(self,value):
		self.shuffle=xsi.DecodeBoolean(value)
	
	def Set_maxChoices(self,value):
		self.maxChoices=xsi.DecodeInteger(value)
	
	def Set_minChoices(self,value):
		self.minChoices=xsi.DecodeInteger(value)
	
	def GetAttributes(self):
		attrs=QTIBlockInteraction.GetAttributes(self)
		attrs['shuffle']=xsi.EncodeBoolean(self.shuffle)
		attrs['maxChoices']=xsi.EncodeInteger(self.maxChoices)
		if self.minChoices is not None:
			attrs['minChoices']=xsi.EncodeInteger(self.minChoices)
		return attrs

	def GetChildren(self):
		return QTIBlockInteraction.GetChildren(self)+self.QTISimpleChoice
		

class QTISimpleChoice(QTIChoice):
	"""Represents the simpleChoice element.

	<xsd:group name="simpleChoice.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="flowStatic.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(IMSQTI_NAMESPACE,'simpleChoice')
	XMLCONTENT=xmlns.XMLMixedContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.XHTMLFlowMixin):
			return QTIChoice.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise QTIValidityError("%s in %s"%(repr(name),self.__class__.__name__))		
	
	
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
