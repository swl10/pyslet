#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsdatatypes
import pyslet.html40_19991224 as html
import pyslet.rfc2396 as uri

xsi=xsdatatypes

import string, itertools
import os.path, sys
from types import StringTypes

import pyslet.qtiv2.core as core
import pyslet.qtiv2.variables as variables
import pyslet.qtiv2.expressions as expressions





QTI_HTMLProfile=[
	'abbr','acronym','address','blockquote','br','cite','code','dfn','div',
	'em','h1','h2','h3','h4','h5','h6','kbd','p','pre','q','samp','span',
	'strong','var','dl','dt','dd','ol','ul','li','object','param','b','big',
	'hr','i','small','sub','sup','tt','caption','col','colgroup','table',
	'tbody','tfoot','thead','td','th','tr','img','a']

def FixHTMLNamespace(e):
	"""Fixes e and all children to be in the QTINamespace"""
	if e.ns==html.XHTML_NAMESPACE:
		name=(core.IMSQTI_NAMESPACE,e.xmlname.lower())
		if name in QTIDocument.classMap:
			e.SetXMLName(name)
	for e in e.GetChildren():
		if type(e) in StringTypes:
			continue
		FixHTMLNamespace(e)


MakeValidNCName=core.ValidateIdentifier


class Orientation:
	decode={
		'horizontal':1,
		'vertical':2
		}
xsi.MakeEnumeration(Orientation)
		
def DecodeOrientation(value):
	"""Decodes an orientation value from a string.

	<xsd:simpleType name="orientation.Type">
		<xsd:restriction base="xsd:NMTOKEN">
			<xsd:enumeration value="horizontal"/>
			<xsd:enumeration value="vertical"/>
		</xsd:restriction>
	</xsd:simpleType>
	"""
	try:
		return Orientation.decode[value.lower()]
	except KeyError:
		raise ValueError("Can't decode orientation from %s"%value)

def EncodeOrientation(value):
	return Orientation.encode.get(value,None)


def CalculateShapeBounds(shape,coords):
	"""Calculates a bounding rectangle from a Shape value and a list of *pixel* coordinates."""
	if shape==core.Shape.circle:
		return [coords[0]-coords[2],coords[1]-coords[2],coords[0]+coords[2],coords[1]+coords[2]]
	elif shape==core.Shape.default:
		return [0,0,1024,768]
	elif shape==core.Shape.ellipse:
		return [coords[0]-coords[2],coords[1]-coords[3],coords[0]+coords[2],coords[1]+coords[3]]
	elif shape==core.Shape.poly:
		output=[coords[0],coords[1],coords[0],coords[1]]
		i=1
		while 2*i+1<len(coords):
			x=coords[2*i]
			y=coords[2*i+1]
			if x<output[0]:
				output[0]=x
			elif x>output[2]:
				output[2]=x
			if y<output[1]:
				output[1]=y
			elif y>output[3]:
				output[3]=y
		return output
	elif shape==core.Shape.rect:
		return [coords[0],coords[1],coords[2],coords[3]]
	else:
		raise ValueError("Unknown value for shape: %s"%str(shape))


def OffsetShape(shape,coords,xOffset,yOffset):
	"""Interprets the shape coords relative to the given offset and maps them back to the origin.
	
	In other words, xOffset and yOffset are subtracted from the coordinates."""
	if shape==core.Shape.circle:
		coords[0]-=xOffset
		coords[1]-=yOffset
	elif shape==core.Shape.default:
		pass
	elif shape==core.Shape.ellipse:
		coords[0]-=xOffset
		coords[1]-=yOffset
	elif shape==core.Shape.poly:
		i=0
		while 2*i+1<len(coords):
			coords[2*i]-=xOffset
			coords[2*i+1]-=yOffset
	elif shape==core.Shape.rect:
		coords[0]-=xOffset
		coords[1]-=yOffset
		coords[2]-=xOffset
		coords[3]-=yOffset
	else:
		raise ValueError("Unknown value for shape: %s"%str(shape))
		

class QTIShowHide:
	decode={
		'show':1,
		'hide':2
		}
xsi.MakeEnumeration(QTIShowHide)
		
def DecodeShowHide(value):
	"""Decodes a showHide value from a string.

	<xsd:simpleType name="showHide.Type">
		<xsd:restriction base="xsd:NMTOKEN">
			<xsd:enumeration value="hide"/>
			<xsd:enumeration value="show"/>
		</xsd:restriction>
	</xsd:simpleType>
	"""
	try:
		return QTIShowHide.decode[value.lower()]
	except KeyError:
		raise ValueError("Can't decode show/hide from %s"%value)

def EncodeShowHide(value):
	return QTIShowHide.encode.get(value,None)


class TextFormat:
	fixups={
		'preformatted':'preFormatted'
		}
	decode={
		'plain':1,
		'preFormatted':2,
		'xhtml':3
		}
xsi.MakeEnumeration(TextFormat)

def DecodeTextFormat(value):
	try:
		return TextFormat.decode[value]
	except KeyError:
		value=value.lower()
		value=TextFormat.fixups.get(value,value)
	try:
		return TextFormat.decode[value]
	except KeyError:
		raise ValueError("Can't decode textFormat from %s"%value)

def EncodeTextFormat(value):
	return TextFormat.encode.get(value,None)
		

class QTIAssessmentItem(core.QTIElement):
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
	XMLNAME=(core.IMSQTI_NAMESPACE,'assessmentItem')
	XMLATTR_adaptive=('adaptive',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_identifier='identifier'		
	XMLATTR_label='label'
	XMLATTR_timeDependent=('timeDependent',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_title='title'	
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.identifier=None
		self.title=None
		self.label=None
		self.adaptive=False
		self.timeDependent=False
		self.ResponseDeclaration=[]
		self.OutcomeDeclaration=[]
		self.TemplateDeclaration=[]
		self.TemplateProcessing=None
		self.StyleSheet=[]
		self.ItemBody=None
		self.ResponseProcessing=None
		self.QTIModalFeedback=[]
		self.declarations={}		#: a dictionary of variable declarations
		self.metadata=QTIMetadata(None)
		
	def GetChildren(self):
		for d in self.ResponseDeclaration: yield d
		for d in self.OutcomeDeclaration: yield d
		for d in self.TemplateDeclaration: yield d
		if self.ItemBody: yield self.ItemBody
		if self.ResponseProcessing: yield self.ResponseProcessing
		for child in self.QTIModalFeedback: yield child
	
	def ContentChanged(self):
		self.SortDeclarations()
		
	def RegisterDeclaration(self,declaration):
		if declaration.identifier in self.declarations:
			raise core.QTIDeclarationError
		else:
			self.declarations[declaration.identifier]=declaration
	
	def IsDeclared(self,identifier):
		return identifier in self.declarations
	
	def GetDeclaration(self,identifier):
		return self.declarations.get(identifier,None)

	def SortDeclarations(self):
		"""Sort each of the variable declaration lists so that they are in
		identifier order.  This is not essential but it does help ensure that
		output is predictable. This method is called automatically when reading
		items from XML files."""
		self.ResponseDeclaration.sort()
		self.OutcomeDeclaration.sort()
		self.TemplateDeclaration.sort()
			
	def AddToContentPackage(self,cp,lom,dName=None):
		"""Adds a resource and associated files to the content package."""
		resourceID=cp.manifest.GetUniqueID(self.identifier)
		resource=cp.manifest.root.Resources.ChildElement(cp.manifest.root.Resources.ResourceClass)
		resource.SetID(resourceID)
		resource.type=core.IMSQTI_ITEM_RESOURCETYPE
		resourceMetadata=resource.ChildElement(resource.MetadataClass)
		#resourceMetadata.AdoptChild(lom)
		#resourceMetadata.AdoptChild(self.metadata.Copy())
		lom.Copy(resourceMetadata)
		self.metadata.Copy(resourceMetadata)
		# Security alert: we're leaning heavily on MakeValidNCName assuming it returns a good file name
		fPath=(MakeValidNCName(resourceID)+'.xml').encode(sys.getfilesystemencoding())
		if dName:
			fPath=os.path.join(dName,fPath)
		fPath=cp.GetUniqueFile(fPath)
		# This will be the path to the file in the package
		fullPath=os.path.join(cp.dPath,fPath)
		base=uri.URIFactory.URLFromPathname(fullPath)
		if isinstance(self.parent,xml.Document):
			# we are the root so we change the document base
			self.parent.SetBase(base)
		else:
			self.SetBase(base)
		# Turn this file path into a relative URL in the context of the new resource
		href=resource.RelativeURI(base)
		f=cp.File(resource,href)
		resource.SetEntryPoint(f)
		for child in self.GetChildren():
			if isinstance(child,core.QTIElement):
				child.AddToCPResource(cp,resource,{})
		return resource
	
		



			
class BodyElement(core.QTIElement):
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
	XMLATTR_id=('id',core.ValidateIdentifier,lambda x:x)		
	XMLATTR_label='label'
	XMLATTR_class='styleClass'

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.id=None
		self.styleClass=None
		self.label=None
	
		
# xml:base is handled automatically for all elements
class QTIObjectFlowMixin: pass


class QTISimpleInline(html.InlineMixin,BodyElement):
	# need to constrain content to html.InlineMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.InlineMixin):
			return BodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise core.QTIValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		

class SimpleBlock(html.BlockMixin,BodyElement):
	# need to constrain content to html.BlockMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.BlockMixin):
			return BodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise core.QTIValidityError("%s in %s"%(repr(name),self.__class__.__name__))		

class QTIAtomicInline(html.InlineMixin,BodyElement): pass

class QTIAtomicBlock(html.BlockMixin,BodyElement):
	# need to constrain content to html.InlineMixin
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.InlineMixin):
			return BodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise core.QTIValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))


class QTIFlowContainerMixin:
	"""Mixin class used for objects that can contain flows."""

	def PrettyPrint(self):
		"""Deteremins if this flow-container-like object should be pretty printed.
		
		This is the same algorithm we use in HTML flow containers, suppressing pretty
		printing if we have inline elements (ignoring non-trivial data)."""
		for child in self.GetChildren():
			if type(child) in StringTypes:
				for c in child:
					if not xml.IsS(c):
						return False
			elif isinstance(child,html.InlineMixin):
				return False
		return True

	
class ItemBody(BodyElement):
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
	XMLNAME=(core.IMSQTI_NAMESPACE,'itemBody')
	XMLCONTENT=xmlns.ElementContent	


class RubricBlock(SimpleBlock):
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
	XMLNAME=(core.IMSQTI_NAMESPACE,'rubricBlock')
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue,True)
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		SimpleBlock.__init__(self,parent)
		self.view={}
	
	def AddView(self,view):
		if type(view) in StringTypes:
			view=core.View.DecodeLowerValue(view.strip())
		viewValue=core.View.EncodeValue(view)
		if viewValue:	
			self.view[view]=viewValue
		else:
			raise ValueError("illegal value for view: %s"%view)


#
#	INTERACTIONS
#
class QTIInteraction(BodyElement):
	"""Abstract class to act as a base for all interactions.

	<xsd:attributeGroup name="interaction.AttrGroup">
		<xsd:attributeGroup ref="bodyElement.AttrGroup"/>
		<xsd:attribute name="responseIdentifier" type="identifier.Type" use="required"/>
	</xsd:attributeGroup>
	"""
	XMLATTR_responseIdentifier=('responseIdentifier',core.ValidateIdentifier,lambda x:x)

	def __init__(self,parent):
		BodyElement.__init__(self,parent)
		self.responseIdentifier=''
	

class InlineInteraction(html.InlineMixin,QTIInteraction):
	"""Abstract class for interactions that are treated as inline."""
	pass


class BlockInteraction(html.BlockMixin,QTIInteraction):
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
	
	def GetChildren(self):
		if self.QTIPrompt: yield self.QTIPrompt


class QTIPrompt(BodyElement):
	"""The prompt used in block interactions.

	<xsd:group name="prompt.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="inlineStatic.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'prompt')
	XMLCONTENT=xmlns.XMLMixedContent

	def __init__(self,parent):
		BodyElement.__init__(self,parent)

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.InlineMixin):
			return BodyElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise core.QTIValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		


class QTIChoice(BodyElement):		
	"""The base class used for all choices.

	<xsd:attributeGroup name="choice.AttrGroup">
		<xsd:attributeGroup ref="bodyElement.AttrGroup"/>
		<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		<xsd:attribute name="fixed" type="boolean.Type" use="optional"/>
		<xsd:attribute name="templateIdentifier" type="identifier.Type" use="optional"/>
		<xsd:attribute name="showHide" type="showHide.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	XMLATTR_fixed=('fixed',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLATTR_showHide=('showHide',DecodeShowHide,EncodeShowHide)
	XMLATTR_templateIdentifier=('templateIdentifier',core.ValidateIdentifier,lambda x:x)
	
	def __init__(self,parent):
		BodyElement.__init__(self,parent)
		self.identifier=''
		self.fixed=None
		self.templateIdentifier=None
		self.showHide=None


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
	XMLATTR_matchGroup=('matchGroup',core.ValidateIdentifier,lambda x:x)
	
	def __init__(self,parent):
		QTIChoice.__init__(self,parent)
		self.matchGroup=[]
	

#
#		SIMPLE INTERACTIONS
#

class QTIChoiceInteraction(BlockInteraction):
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
	XMLNAME=(core.IMSQTI_NAMESPACE,'choiceInteraction')
	XMLATTR_maxChoices=('maxChoices',xsi.DecodeInteger,xsi.EncodeInteger)	
	XMLATTR_minChoices=('minChoices',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_shuffle=('shuffle',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		BlockInteraction.__init__(self,parent)
		self.shuffle=False
		self.maxChoices=1
		self.minChoices=None
		self.QTISimpleChoice=[]
		
	def GetChildren(self):
		for child in itertools.chain(
			BlockInteraction.GetChildren(self),
			self.QTISimpleChoice):
			yield child


class QTISimpleChoice(QTIFlowContainerMixin,QTIChoice):
	"""Represents the simpleChoice element.

	<xsd:group name="simpleChoice.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="flowStatic.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'simpleChoice')
	XMLCONTENT=xmlns.XMLMixedContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.FlowMixin):
			return QTIChoice.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise core.QTIValidityError("%s in %s"%(repr(name),self.__class__.__name__))		


#
#		TEXT-BASED INTERACTIONS
#
class StringInteractionMixin:
	"""Represents the stringInteraction element::
	
	<xsd:attributeGroup name="stringInteraction.AttrGroup">
		<xsd:attribute name="base" type="integer.Type" use="optional"/>
		<xsd:attribute name="stringIdentifier" type="identifier.Type" use="optional"/>
		<xsd:attribute name="expectedLength" type="integer.Type" use="optional"/>
		<xsd:attribute name="patternMask" type="string.Type" use="optional"/>
		<xsd:attribute name="placeholderText" type="string.Type" use="optional"/>
	</xsd:attributeGroup>
	"""	
	XMLATTR_base=('base',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_stringIdentifier='stringIdentifier'
	XMLATTR_expectedLength=('expectedLength',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_patternMask='patternMask'
	XMLATTR_placeholderText='placeholderText'	

	def __init__(self):
		self.base=None
		self.stringIdentifier=None
		self.expectedLength=None
		self.patternMask=None
		self.placeholderText=None
	

class TextEntryInteraction(StringInteractionMixin,InlineInteraction):
	"""Represents the textEntryInteraction element"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'textEntryInteraction')
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		InlineInteraction.__init__(self,parent)
		StringInteractionMixin.__init__(self)


class ExtendedTextInteraction(StringInteractionMixin,BlockInteraction):
	"""Represents the extendedTextInteraction element::

	<xsd:attributeGroup name="extendedTextInteraction.AttrGroup">
		<xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
		<xsd:attributeGroup ref="stringInteraction.AttrGroup"/>
		<xsd:attribute name="maxStrings" type="integer.Type" use="optional"/>
		<xsd:attribute name="minStrings" type="integer.Type" use="optional"/>
		<xsd:attribute name="expectedLines" type="integer.Type" use="optional"/>
		<xsd:attribute name="format" type="textFormat.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'extendedTextInteraction')
	XMLATTR_maxStrings=('maxStrings',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_minStrings=('minStrings',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_expectedLines=('expectedLines',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_format=('format',DecodeTextFormat,EncodeTextFormat)	
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		BlockInteraction.__init__(self,parent)
		StringInteractionMixin.__init__(self)
		self.maxStrings=None
		self.minStrings=None
		self.expectedLines=None
		self.format=None

		
#
#		GRAPHICAL INTERACTIONS
#
class QTIHotspotMixin:
	"""Represent the hotspot abstract class::
	
	<xsd:attributeGroup name="hotspot.AttrGroup">
		<xsd:attribute name="shape" type="shape.Type" use="required"/>
		<xsd:attribute name="coords" type="coords.Type" use="required"/>
		<xsd:attribute name="hotspotLabel" type="string256.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	XMLATTR_shape=('shape',core.Shape.DecodeLowerValue,core.Shape.EncodeValue)
	XMLATTR_coords=('coords',html.DecodeCoords,html.EncodeCoords)
	XMLATTR_hotspotLabel='hotspotLabel'
	
	def __init__(self):
		self.shape=None
		self.coords=html.Coords()
		self.hotspotLabel=None
	

class QTIHotspotChoice(QTIHotspotMixin,QTIChoice):
	"""Represents the hotspotChoide class."""
	XMLNAME=(core.IMSQTI_NAMESPACE,'hotspotChoice')
	XMLCONTENT=xmlns.XMLEmpty
	def __init__(self,parent):
		QTIChoice.__init__(self,parent)
		QTIHotspotMixin.__init__(self)
	

class QTIGraphicInteraction(BlockInteraction):
	"""Represents the abstract graphicInteraction class::
	
	<xsd:attributeGroup name="graphicInteraction.AttrGroup">
		<xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
	</xsd:attributeGroup>
	
	<xsd:group name="graphicInteraction.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="blockInteraction.ContentGroup"/>
			<xsd:element ref="object" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		BlockInteraction.__init__(self,parent)
		self.Object=html.Object(self)
		FixHTMLNamespace(self.Object)
	
	def GetChildren(self):
		for child in BlockInteraction.GetChildren(self): yield child
		yield self.Object


class QTIHotspotInteraction(QTIGraphicInteraction):
	"""Represents the hotspotInteraction element::

	<xsd:attributeGroup name="hotspotInteraction.AttrGroup">
		<xsd:attributeGroup ref="graphicInteraction.AttrGroup"/>
		<xsd:attribute name="maxChoices" type="integer.Type" use="required"/>
		<xsd:attribute name="minChoices" type="integer.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="hotspotInteraction.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="graphicInteraction.ContentGroup"/>
			<xsd:element ref="hotspotChoice" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'hotspotInteraction')
	XMLATTR_maxChoices=('maxChoices',xsi.DecodeInteger,xsi.EncodeInteger)	
	XMLATTR_minChoices=('minChoices',xsi.DecodeInteger,xsi.EncodeInteger)

	def __init__(self,parent):
		QTIGraphicInteraction.__init__(self,parent)
		self.maxChoices=1
		self.minChoices=None
		self.QTIHotspotChoice=[]
	
	def GetChildren(self):
		return itertools.chain(
			QTIGraphicInteraction.GetChildren(self),
			self.QTIHotspotChoice)


class QTISelectPointInteraction(QTIGraphicInteraction):
	"""Represents the selectPointInteraction element::
	
	<xsd:attributeGroup name="selectPointInteraction.AttrGroup">
		<xsd:attributeGroup ref="graphicInteraction.AttrGroup"/>
		<xsd:attribute name="maxChoices" type="integer.Type" use="required"/>
		<xsd:attribute name="minChoices" type="integer.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'selectPointInteraction')
	XMLATTR_maxChoices=('maxChoices',xsi.DecodeInteger,xsi.EncodeInteger)	
	XMLATTR_minChoices=('minChoices',xsi.DecodeInteger,xsi.EncodeInteger)

	def __init__(self,parent):
		QTIGraphicInteraction.__init__(self,parent)
		self.maxChoices=1
		self.minChoices=None


#
#		MISCELLANEOUS INTERACTIONS
#
class SliderInteraction(BlockInteraction):
	"""Represents the sliderInteraction element::

	<xsd:attributeGroup name="sliderInteraction.AttrGroup">
		<xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
		<xsd:attribute name="lowerBound" type="float.Type" use="required"/>
		<xsd:attribute name="upperBound" type="float.Type" use="required"/>
		<xsd:attribute name="step" type="integer.Type" use="optional"/>
		<xsd:attribute name="stepLabel" type="boolean.Type" use="optional"/>
		<xsd:attribute name="orientation" type="orientation.Type" use="optional"/>
		<xsd:attribute name="reverse" type="boolean.Type" use="optional"/>
	</xsd:attributeGroup>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'sliderInteraction')
	XMLATTR_lowerBound=('lowerBound',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLATTR_upperBound=('upperBound',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLATTR_step=('step',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_stepLabel=('stepLabel',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_orientation=('orientation',DecodeOrientation,EncodeOrientation)
	XMLATTR_reverse=('reverse',xsi.DecodeBoolean,xsi.EncodeBoolean)
	
	def __init__(self,parent):
		BlockInteraction.__init__(self,parent)
		self.lowerBound=None
		self.upperBound=None
		self.step=None
		self.stepLabel=False
		self.orientation=None
		self.reverse=None

		
#
#	RESPONSE PROCESSING
#

#
#		Generalized Response Processing
#
class ResponseProcessing(core.QTIElement):
	"""Represents the responseProcessing element.

	<xsd:attributeGroup name="responseProcessing.AttrGroup">
		<xsd:attribute name="template" type="uri.Type" use="optional"/>
		<xsd:attribute name="templateLocation" type="uri.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="responseProcessing.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="responseRule.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'responseProcessing')
	XMLATTR_template='template'
	XMLATTR_templateLocation='templateLocation'
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.template=None
		self.templateLocation=None
		self.ResponseRule=[]
		
	def GetChildren(self):
		return itertools.chain(
			self.ResponseRule,
			core.QTIElement.GetChildren(self))


class ResponseRule(core.QTIElement):
	"""Abstract class to represent response rules."""
	pass


class ResponseCondition(ResponseRule):
	"""Represents responseRule element.

	<xsd:group name="responseCondition.ContentGroup">
		<xsd:sequence>
			<xsd:element ref="responseIf" minOccurs="1" maxOccurs="1"/>
			<xsd:element ref="responseElseIf" minOccurs="0" maxOccurs="unbounded"/>
			<xsd:element ref="responseElse" minOccurs="0" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'responseCondition')
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		ResponseRule.__init__(self,parent)
		self.ResponseIf=ResponseIf(self)
		self.ResponseElseIf=[]
		self.ResponseElse=None
	
	def GetChildren(self):
		if self.ResponseIf: yield self.ResponseIf
		for child in self.ResponseElseIf: yield child
		if self.ResponseElse: yield self.ResponseElse
	

class ResponseIf(core.QTIElement):
	"""Represents the responseIf element.

	<xsd:group name="responseIf.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
			<xsd:group ref="responseRule.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'responseIf')
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.Expression=None
		self.ResponseRule=[]
	
	def GetChildren(self):
		if self.Expression: yield self.Expression
		for child in self.ResponseRule: yield child


class ResponseElse(core.QTIElement):
	"""Represents the responseElse element.

	<xsd:group name="responseElse.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="responseRule.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'responseElse')
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.ResponseRule=[]
	
	def GetChildren(self):
		return iter(self.ResponseRule)


class ResponseElseIf(ResponseIf):
	"""Represents the responseElseIf element.

	<xsd:group name="responseElseIf.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
			<xsd:group ref="responseRule.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'responseElseIf')



class QTISetOutcomeValue(ResponseRule):
	"""Represents the setOutcomeValue element.

	<xsd:attributeGroup name="setOutcomeValue.AttrGroup">
		<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
	</xsd:attributeGroup>
	
	<xsd:group name="setOutcomeValue.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'setOutcomeValue')
	XMLATTR_identifier='identifier'
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		ResponseRule.__init__(self,parent)
		self.identifier=''
		self.Expression=None
	
	def GetChildren(self):
		if self.Expression: yield self.Expression

	
#
#	RESPONSE PROCESSING
#
class QTIModalFeedback(QTIFlowContainerMixin,core.QTIElement):
	"""Represents the modalFeedback element.

	<xsd:attributeGroup name="modalFeedback.AttrGroup">
		<xsd:attribute name="outcomeIdentifier" type="identifier.Type" use="required"/>
		<xsd:attribute name="showHide" type="showHide.Type" use="required"/>
		<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		<xsd:attribute name="title" type="string.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="modalFeedback.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="flowStatic.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'modalFeedback')
	XMLATTR_outcomeIdentifier=('outcomeIdentifier',core.ValidateIdentifier,lambda x:x)
	XMLATTR_showHide=('showHide',DecodeShowHide,EncodeShowHide)
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLATTR_title='title'
	XMLCONTENT=xmlns.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.outcomeIdentifier=None
		self.showHide=None
		self.identifier=None
		self.title=None

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,html.FlowMixin):
			return core.QTIElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise core.QTIValidityError("%s in %s"%(repr(name),self.__class__.__name__))		

	
#
#	EXPRESSIONS
#
	
#
#		expressions.Expressions Used only in Outcomes Processing
#


#
#		Operators
#
class ExpressionList(expressions.Expression):
	"""An abstract class to help implement binary+ operators."""
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		expressions.Expression.__init__(self,parent)
		self.Expression=[]
	
	def GetChildren(self):
		return iter(self.Expression)


class QTIUnaryExpression(expressions.Expression):
	"""An abstract class to help implement unary operators."""
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		expressions.Expression.__init__(self,parent)
		self.Expression=None
	
	def GetChildren(self):
		if self.Expression: yield self.Expression


class QTIMultiple(ExpressionList):
	"""Represents the multiple operator.

	<xsd:group name="multiple.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'multiple')

		
class QTIOrdered(ExpressionList):
	"""Represents the ordered operator.

	<xsd:group name="ordered.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'ordered')

			
class QTIContainerSize(QTIUnaryExpression):
	"""Represents the containerSize operator.

	<xsd:group name="containerSize.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'containerSize')

			
class QTIIsNull(QTIUnaryExpression):
	"""Represents the isNull operator.

	<xsd:group name="isNull.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'isNull')

			
class QTIIndex(QTIUnaryExpression):
	"""Represents the index operator.

	<xsd:attributeGroup name="index.AttrGroup">
		<xsd:attribute name="n" type="integer.Type" use="required"/>
	</xsd:attributeGroup>
	
	<xsd:group name="index.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'index')
	XMLATTR_n=('n',xsi.DecodeInteger,xsi.EncodeInteger)

	def __init__(self,parent):
		QTIUnaryExpression.__init__(self,parent)
		self.n=None

	
class QTIFieldValue(QTIUnaryExpression):
	"""Represents the fieldValue operator.

	<xsd:attributeGroup name="fieldValue.AttrGroup">
		<xsd:attribute name="fieldIdentifier" type="identifier.Type" use="required"/>
	</xsd:attributeGroup>
	
	<xsd:group name="fieldValue.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'fieldValue')
	XMLATTR_fieldIdentifier=('fieldIdentifier',core.ValidateIdentifier,lambda x:x)

	def __init__(self,parent):
		QTIUnaryExpression.__init__(self,parent)
		self.fieldIdentifier=''


class QTIRandom(QTIUnaryExpression):
	"""Represents the random operator.

	<xsd:group name="random.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'random')

				
class QTIMember(ExpressionList):
	"""Represents the member operator.

	<xsd:group name="member.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'member')

	
class QTIDelete(ExpressionList):
	"""Represents the delete operator.

	<xsd:group name="delete.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'delete')


class QTIContains(ExpressionList):
	"""Represents the contains operator.

	<xsd:group name="contains.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'contains')


class QTISubstring(ExpressionList):
	"""Represents the substring operator.

	<xsd:attributeGroup name="substring.AttrGroup">
		<xsd:attribute name="caseSensitive" type="boolean.Type" use="required"/>
	</xsd:attributeGroup>
	
	<xsd:group name="substring.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'substring')
	XMLATTR_caseSensitive=('caseSensitive',xsi.DecodeBoolean,xsi.EncodeBoolean)

	def __init__(self,parent):
		ExpressionList.__init__(self,parent)
		self.caseSensitive=True


class Not(QTIUnaryExpression):
	"""Represents the not operator.

	<xsd:group name="not.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'not')

				
class And(ExpressionList):
	"""Represents the and operator.

	<xsd:group name="and.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'and')


class Or(ExpressionList):
	"""Represents the or operator.

	<xsd:group name="or.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'or')


class QTIAnyN(ExpressionList):
	"""Represents the anyN operator.

	<xsd:attributeGroup name="anyN.AttrGroup">
		<xsd:attribute name="min" type="integerOrTemplateRef.Type" use="required"/>
		<xsd:attribute name="max" type="integerOrTemplateRef.Type" use="required"/>
	</xsd:attributeGroup>
	
	<xsd:group name="anyN.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'anyN')
	XMLATTR_min='min'
	XMLATTR_max='max'

	def __init__(self,parent):
		ExpressionList.__init__(self,parent)
		self.min=''
		self.max=''


class Match(ExpressionList):
	"""Represents the match operator.

	<xsd:group name="match.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'match')


class QTIStringMatch(ExpressionList):
	"""Represents the stringMatch operator.
	
	<xsd:attributeGroup name="stringMatch.AttrGroup">
		<xsd:attribute name="caseSensitive" type="boolean.Type" use="required"/>
		<xsd:attribute name="substring" type="boolean.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="stringMatch.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'stringMatch')
	XMLATTR_caseSensitive=('caseSensitive',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_substring=('substring',xsi.DecodeBoolean,xsi.EncodeBoolean)
	
	def __init__(self,parent):
		ExpressionList.__init__(self,parent)
		self.caseSensitive=None
		self.substring=False
		

class QTIInside(QTIUnaryExpression):
	"""Represents the inside operator::

	<xsd:attributeGroup name="inside.AttrGroup">
		<xsd:attribute name="shape" type="shape.Type" use="required"/>
		<xsd:attribute name="coords" type="coords.Type" use="required"/>
	</xsd:attributeGroup>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'inside')
	XMLATTR_shape=('shape',core.Shape.DecodeLowerValue,core.Shape.EncodeValue)
	XMLATTR_coords=('coords',html.DecodeCoords,html.EncodeCoords)
	
	def __init__(self,parent):
		QTIUnaryExpression.__init__(self,parent)
		self.shape=None
		self.coords=html.Coords()
		

class LT(ExpressionList):
	"""Represents the lt operator::

	<xsd:group name="lt.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'lt')


class GT(ExpressionList):
	"""Represents the gt operator::

	<xsd:group name="gt.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'gt')


class LTE(ExpressionList):
	"""Represents the lte operator::

	<xsd:group name="lte.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'lte')


class GTE(ExpressionList):
	"""Represents the gte operator::

	<xsd:group name="gte.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'gte')


class QTISum(ExpressionList):
	"""Represents the sum operator::

	<xsd:group name="sum.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'sum')
	
	
class QTIProduct(ExpressionList):
	"""Represents the product operator::

	<xsd:group name="product.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'product')
	
	
class QTISubtract(ExpressionList):
	"""Represents the subtract operator::

	<xsd:group name="subtract.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'subtract')
	
	
class QTIDivide(ExpressionList):
	"""Represents the divide operator::

	<xsd:group name="divide.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'divide')
	
	
class QTIPower(ExpressionList):
	"""Represents the power operator::

	<xsd:group name="power.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'power')
	
	
class QTIIntegerDivide(ExpressionList):
	"""Represents the integerDivide operator::

	<xsd:group name="integerDivide.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'integerDivide')
	
	
class QTIIntegerModulus(ExpressionList):
	"""Represents the integerModulus operator::

	<xsd:group name="integerModulus.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="expression.ElementGroup" minOccurs="2" maxOccurs="2"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'integerModulus')
	
	
#
#	METADATA
#
class QTIMetadata(core.QTIElement):
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
	XMLNAME=(core.IMSQTI_NAMESPACE,'qtiMetadata')
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
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
		if self.QMDItemTemplate: yield self.QMDItemTemplate
		if self.QMDTimeDependent: yield self.QMDTimeDependent
		if self.QMDComposite: yield self.QMDComposite
		for child in self.QMDInteractionType: yield child
		if self.QMDFeedbackType: yield self.QMDFeedbackType
		if self.QMDSolutionAvailable: yield self.QMDSolutionAvailable
		if self.QMDToolName: yield self.QMDToolName
		if self.QMDToolVersion: yield self.QMDToolVersion
		if self.QMDToolVendor: yield self.QMDToolVendor
		for child in core.QTIElement.GetChildren(self): yield child

class QMDItemTemplate(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'itemTemplate')

class QMDTimeDependent(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'timeDependent')

class QMDComposite(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'composite')

class QMDInteractionType(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'interactionType')

class QMDFeedbackType(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'feedbackType')

class QMDSolutionAvailable(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'solutionAvailable')

class QMDToolName(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'toolName')

class QMDToolVersion(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'toolVersion')

class QMDToolVendor(core.QTIElement):
	XMLNAME=(core.IMSQTI_NAMESPACE,'toolVendor')

		
class QTIDocument(xmlns.XMLNSDocument):
	classMap={}
	
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,defaultNS=core.IMSQTI_NAMESPACE,**args)
		self.MakePrefix(xsi.XMLSCHEMA_NAMESPACE,'xsi')
		if isinstance(self.root,core.QTIElement):
			self.root.SetAttribute((xsi.XMLSCHEMA_NAMESPACE,'schemaLocation'),core.IMSQTI_NAMESPACE+' '+core.IMSQTI_SCHEMALOCATION)
			
	def GetElementClass(self,name):
		return QTIDocument.classMap.get(name,QTIDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	def AddToContentPackage(self,cp,metadata,dName=None):
		"""Copies this QTI document into a content package and returns the resource ID used.
		
		An optional directory name can be specified in which to put the resource files."""
		if not isinstance(self.root,QTIAssessmentItem):
			print self.root
			raise TypeError
		# We call the elemement's AddToContentPackage method which returns the new resource
		# The document's base is automatically set to the URI of the resource entry point
		resource=self.root.AddToContentPackage(cp,metadata,dName)
		# Finish by writing out the document to the new baseURI
		self.Create()
		return resource

xmlns.MapClassElements(QTIDocument.classMap,globals())
xmlns.MapClassElements(QTIDocument.classMap,variables)
# also add in the profile of HTML but with the namespace rewritten to ours
for name in QTI_HTMLProfile:
	eClass=html.XHTMLDocument.classMap.get((html.XHTML_NAMESPACE,name),None)
	if eClass:
		QTIDocument.classMap[(core.IMSQTI_NAMESPACE,name)]=eClass
	else:
		print "Failed to map XHTML element name %s"%name