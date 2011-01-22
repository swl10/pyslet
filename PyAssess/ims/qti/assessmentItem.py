from xml.sax import make_parser, handler
from string import join, split
from random import choice
from copy import copy

import sys, os

from common import *
from PyAssess.w3c.xmlnamespaces import XMLNamespace
from PyAssess.w3c.xmlschema import RegularExpression

class AssessmentItem:
	def __init__(self,identifier,title,adaptive,timeDependent):
		self.SetIdentifier(identifier)
		self.SetTitle(title)
		self.label=None
		self.language=None
		self.SetAdaptive(adaptive)
		self.SetTimeDependent(timeDependent)
		self.toolName=None
		self.toolVersion=None
		self.stylesheet=[]
		self.itemBody=None
		self.variables={}
		self.responseProcessing=None
		
	def SetIdentifier(self,identifier):
		if type(identifier) in StringTypes:
			self.identifier=identifier
		else:
			raise TypeError	
	
	def SetTitle(self,title):
		if type(title) in StringTypes:
			self.title=title
		else:
			raise TypeError
	
	def SetLabel(self,label):
		if label is None:
			self.label=None
		elif type(label) in StringTypes:
			self.label=label
		else:
			raise TypeError
	
	def SetLanguage(self,language):
		if language is None:
			self.language=None
		else:
			if not isinstance(language,LanguageTag):
				language=LanguageTag(language)
			self.language=language

	def SetAdaptive(self,adaptive):
		if adaptive in (0,1):
			self.adaptive=adaptive
		else:
			raise ValueError
	
	def SetTimeDependent(self,timeDependent):
		if timeDependent in (0,1):
			self.timeDependent=timeDependent
		else:
			raise ValueError
	
	def SetToolName(self,toolName):
		if toolName is None:
			self.toolName=None
		elif type(toolName) in StringTypes:
			self.toolName=toolName
		else:
			raise TypeError
	
	def SetToolVersion(self,toolVersion):
		if toolVersion is None:
			self.toolVersion=None
		elif type(toolVersion) in StringTypes:
			self.toolVersion=toolVersion
		else:
			raise TypeError
	
	def DeclareVariable(self,declaration):
		self.variables[declaration.identifier]=declaration
			
	def LookupVariableDeclaration(self,varName):
		return self.variables.get(varName)
	
	def AddStylesheet(self,stylesheet):
		if isinstance(stylesheet,Stylesheet):
			self.stylesheet.append(stylesheet)
		else:
			raise TypeError
	
	def CreateBody(self):
		self.itemBody=ItemBody(self)
		return self.itemBody

	def RenderBody(self,view):
		if self.itemBody:
			self.itemBody.Render(view)
			
	def CreateResponseProcessing(self):
		self.responseProcessing=ResponseProcessing()
		return self.responseProcessing


class VariableDeclaration:
	def __init__(self,identifier,cardinality,baseType=None):
		self.SetIdentifier(identifier)
		self.SetCardinality(cardinality)
		self.SetBaseType(baseType)
		self.defaultValue=None
		self.defaultInterpretation=None
		
	def SetIdentifier(self,identifier):
		if type(identifier) in StringTypes:
			self.identifier=ParseIdentifier(identifier)
		else:
			raise TypeError
	
	def SetCardinality(self,cardinality):
		if type(cardinality) is IntType:
			if cardinality>0 and cardinality<=Cardinality.MaxValue:
				self.cardinality=cardinality
			else:
				raise ValueError
		elif type(cardinality) in StringTypes:
			self.cardinality=ParseCardinality(cardinality)
		else:
			raise TypeError
		if self.cardinality==Cardinality.Record:
			self.baseType=None
				
	def SetBaseType(self,baseType):
		if self.cardinality!=Cardinality.Record:
			# for Records, we ignore baseType
			if type(baseType) is IntType:
				if baseType>0 and baseType<=BaseType.MaxValue:
					self.baseType=baseType
				else:
					raise ValueError
			elif type(baseType) in StringTypes:
				self.baseType=ParseBaseType(baseType)
			else:
				raise TypeError
				
	def SetDefaultInterpretation(self,interpretation):
		if interpretation is None or type(interpretation) in StringTypes:
			self.defaultInterpretation=interpretation
		else:
			raise TypeError
			
	def SetDefaultValue(self,value):
		if value is None:
			self.defaultValue=None
		else:
			CheckValue(self.cardinality,self.baseType,value)
			self.defaultValue=value
			

class ResponseDeclaration(VariableDeclaration):
	def __init__(self,identifier,cardinality,baseType=None):
		VariableDeclaration.__init__(self,identifier,cardinality,baseType)
		self.correctInterpretation=None
		self.correctValue=None
		self.mapping=None
		
	def SetCorrectInterpretation(self,interpretation):
		if interpretation is None or type(interpretation) in StringTypes:
			self.correctInterpretation=interpretation
		else:
			raise TypeError
			
	def SetCorrectValue(self,value):
		if value is None:
			self.correctValue=None
		else:
			CheckValue(self.cardinality,self.baseType,value)
			self.correctValue=value

	def CreateMapping(self):
		self.mapping=Mapping(self.baseType)
		return self.mapping
		
class Mapping:
	def __init__(self,baseType,defaultValue=0.0):
		self.baseType=baseType
		self.lowerBound=None
		self.upperBound=None
		self.SetDefaultValue(defaultValue)
		self.mapEntry={}

	def SetLowerBound(self,lowerBound):
		if type(lowerBound) is FloatType:
			self.lowerBound=lowerBound
		else:
			raise TypeError
						
	def SetUpperBound(self,upperBound):
		if type(upperBound) is FloatType:
			self.upperBound=upperBound
		else:
			raise TypeError
						
	def SetDefaultValue(self,defaultValue):
		if type(defaultValue) is FloatType:
			self.defaultValue=defaultValue
		else:
			raise TypeError
	
	def AddMapEntry(self,mapKey,mappedValue):
		if type(mappedValue) is FloatType:
			CheckValue(Cardinality.Single,self.baseType,mapKey)
			if self.mapEntry.get(mapKey) is not None:
				raise IMSQTIError("duplicate mapKey: %s"%str(mapKey))
			self.mapEntry[mapKey]=mappedValue

	def MapValue(self,value):
		if type(value) is ListType:
			result=0.0
			vMapped={}
			for v in value:
				if vMapped.has_key(v):
					continue
				vMapped[v]=1
				vMappedValue=self.mapEntry.get(v)
				if vMappedValue is None and self.defaultValue:
					vMappedValue=self.defaultValue
				result+=vMappedValue
		else:
			result=self.mapEntry.get(value)
			if result is None and self.defaultValue:
				result=self.defaultValue
		if result is not None and self.lowerBound and \
			result<self.lowerBound:
			result=self.lowerBound
		if result is not None and self.upperBound and \
			result>self.upperBound:
			result=self.upperBound
		return result
		
class OutcomeDeclaration(VariableDeclaration):
	def __init__(self,identifier,cardinality,baseType=None):
		VariableDeclaration.__init__(self,identifier,cardinality,baseType)
		self.interpretation=None
		self.longInterpretation=None
		self.normalMaximum=None

	def SetInterpretation(self,interpretation):
		if interpretation is None or type(interpretation) in StringTypes:
			self.interpretation=interpretation
		else:
			raise TypeError

	def SetLongInterpretation(self,interpretation):
		if isinstance(interpretation,URIReference) or interpretation is None:
			self.longInterpretation=interpretation
		else:
			self.longInterpretation=URIReference(interpretation)
	
	def SetNormalMaximum(self,normalMaximum):
		if normalMaximum is None:
			self.normalMaximum=None
		elif type(normalMaximum) in (FloatType,IntType,LongType):
			self.normalMaximum=float(normalMaximum)
		else:
			raise TypeError


class Stylesheet:
	def __init__(self,href,mimeType):
		self.href=self.SetHref(href)
		self.type=self.SetType(mimeType)
		self.media=None
		self.title=None
	
	def SetHref(self,href):
		if isinstance(href,URIReference):
			self.href=href
		else:
			self.href=URIReference(href)

	def SetType(self,mimeType):
		if type(mimeType) in StringTypes:
			self.type=mimeType
		else:
			raise TypeError

	def SetMedia(self,media):
		if type(media) in StringTypes or media is None:
			self.media=media
		else:
			raise TypeError
				
	def SetTitle(self,title):
		if type(title) in StringTypes or title is None:
			self.media=title
		else:
			raise TypeError
				

class BodyElement:
	def __init__(self,parent):
		self.parent=parent
		if isinstance(parent,BodyElement):
			parent.AddChild(self)
		self.id=None
		self.styleclass=[]
		self.language=None
		self.label=None
		self.children=[]

	def SetId(self,id):
		if type(id) in StringTypes:
			self.id=ParseIdentifier(id)
		elif id is None:
			self.id=None
		else:
			raise TypeError

	def SetClass(self,styleclass):
		if type(styleclass) in (TupleType,ListType):
			if split(join(styleclass,' '))!=styleclass:
				raise ValueError("class cannot contain space")	
			self.styleclass=styleclass
		elif type(styleclass) in StringTypes:
			if len(split(styleclass))>1:
				raise ValueError("class cannot contain space")
			self.styleclass=[styleclass]
		elif styleclass is None:
			self.styleclass=[]
		else:
			raise TypeError
			
	def SetLanguage(self,language):
		if language is None:
			self.language=None
		else:
			if not isinstance(language,LanguageTag):
				language=LanguageTag(language)
			self.language=language
		
	def SetLabel(self,label):
		if label is None:
			self.label=None
		elif type(label) in StringTypes:
			self.label=label
		else:
			raise TypeError

	def GetParentItem(self):
		if isinstance(self.parent,AssessmentItem):
			return self.parent
		else:
			return self.parent.GetParentItem()
			
	def AddChild(self,child):
		# By default, this is an error, unless it is ignorable space
		if not isinstance(child,TextRun) or child.text.strip():
			raise IMSQTIError("Bad child for %s: %s"%(self.xmlName,child.xmlName))

	def PreserveSpace(self):
		return 0
	
	def MixedContent(self):
		return 0
		
	def RenderChildren(self,view):
		for child in self.children:
			child.Render(view)

	def Render(self,view):
		getattr(view,self.renderMethod)(self)
		
class ItemBody(BodyElement):
	xmlName="itemBody"
	renderMethod="RenderItemBody"
	
	def AddChild(self,child):
		if isinstance(child,Block):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
	
class ObjectFlow: pass
		
class Inline: pass

class Block: pass

class Flow(ObjectFlow): pass

class InlineStatic(Inline): pass

class BlockStatic(Block): pass

class FlowStatic(Flow): pass

class SimpleInline(BodyElement,FlowStatic,InlineStatic):
	def AddChild(self,child):
		if isinstance(child,Inline):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		
	
class SimpleBlock(BlockStatic,BodyElement,FlowStatic):
	def AddChild(self,child):
		if isinstance(child,Block):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
	
	def MixedContent(self):
		return 1
		
class AtomicInline(BodyElement,FlowStatic,InlineStatic):
	pass

class AtomicBlock(BlockStatic,BodyElement,FlowStatic):
	def AddChild(self,child):
		if isinstance(child,Inline):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		

class TextRun(FlowStatic,InlineStatic):
	xmlName="#PCDATA"

	def __init__(self,parent,text):
		self.parent=parent
		self.text=text
		if isinstance(parent,BodyElement):
			parent.AddChild(self)
		else:
			raise TypeError("TextRun not in bodyElement")

	def Render(self,view):
		view.RenderText(self.text)
		

#################
# Text Elements #
#################

class Abbreviation(SimpleInline):
	xmlName="abbr"
	renderMethod="RenderAbbreviation"
	
class Acronym(SimpleInline):
	xmlName="acronym"
	renderMethod="RenderAcronym"
	
class Address(AtomicBlock):
	xmlName="address"
	renderMethod="RenderAddress"
	
class Blockquote(SimpleBlock):
	xmlName="blockquote"
	renderMethod="RenderBlockquote"
	
	def __init__(self,parent):
		BodyElement.__init__(self,parent)
		self.cite=None
		
	def SetCite(self,cite):
		if isinstance(cite,URIReference) or cite is None:
			self.cite=cite
		else:
			self.cite=URIReference(cite)	
		
class LineBreak(AtomicInline):
	xmlName="br"
	renderMethod="RenderLineBreak"
		
class Citation(SimpleInline):
	xmlName="cite"
	renderMethod="RenderCitation"
	
class CodeFragment(SimpleInline):
	xmlName="code"
	renderMethod="RenderCodeFragment"
	
class Definition(SimpleInline):
	xmlName="dfn"
	renderMethod="RenderDefinition"
	
class Div(BlockStatic,BodyElement,FlowStatic):
	xmlName="div"
	renderMethod="RenderDiv"
	
	def AddChild(self,child):
		if isinstance(child,Flow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		
class Emphasis(SimpleInline):
	xmlName="em"
	renderMethod="RenderEmphasis"
					
class Heading1(AtomicBlock):
	xmlName="h1"
	renderMethod="RenderHeading1"
						
class Heading2(AtomicBlock):
	xmlName="h2"
	renderMethod="RenderHeading2"
						
class Heading3(AtomicBlock):
	xmlName="h3"
	renderMethod="RenderHeading3"
						
class Heading4(AtomicBlock):
	xmlName="h4"
	renderMethod="RenderHeading4"
						
class Heading5(AtomicBlock):
	xmlName="h5"
	renderMethod="RenderHeading5"
						
class Heading6(AtomicBlock):
	xmlName="h6"
	renderMethod="RenderHeading6"
	
class KeyboardInput(SimpleInline):
	xmlName="kbd"
	renderMethod="RenderKeyboardInput"
	
class Paragraph(AtomicBlock):
	xmlName="p"
	renderMethod="RenderParagraph"
				
class PreformattedText(AtomicBlock):
	xmlName="pre"
	renderMethod="RenderPreformattedText"
	
class Quotation(SimpleInline):
	xmlName="q"
	renderMethod="RenderQuotation"
	
	def __init__(self,parent):
		BodyElement.__init__(self,parent)
		self.cite=None
		
	def SetCite(self,cite):
		if isinstance(cite,URIReference) or cite is None:
			self.cite=cite
		else:
			self.cite=URIReference(cite)		

class SampleOutput(SimpleInline):
	xmlName="samp"
	renderMethod="RenderSampleOutput"
	
class Span(SimpleInline):
	xmlName="span"
	renderMethod="RenderSpan"
	
class StrongEmphasis(SimpleInline):
	xmlName="strong"
	renderMethod="RenderStrongEmphasis"
	
class ProgramVariable(SimpleInline):
	xmlName="var"
	renderMethod="RenderProgramVariable"
	

#################
# List Elements #
#################

class DefinitionList(BlockStatic,BodyElement,FlowStatic):
	xmlName="dl"
	renderMethod="RenderDefinitionList"
	
	def AddChild(self,child):
		if isinstance(child,DefinitionListItem):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
	
class DefinitionListItem(BodyElement):
	def MixedContent(self):
		return 1
		
class DefinitionTerm(DefinitionListItem):
	xmlName="dt"
	renderMethod="RenderDefinitionTerm"
	
	def AddChild(self,child):
		if isinstance(child,Inline):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
			
class DefinitionItem(DefinitionListItem):
	xmlName="dd"
	renderMethod="RenderDefinitionItem"
	
	def AddChild(self,child):
		if isinstance(child,Flow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
			
class OrderedList(BlockStatic,BodyElement,FlowStatic):
	xmlName="ol"
	renderMethod="RenderOrderedList"
	
	def AddChild(self,child):
		if isinstance(child,ListItem):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

class UnorderedList(BlockStatic,BodyElement,FlowStatic):
	xmlName="ul"
	renderMethod="RenderUnorderedList"
	
	def AddChild(self,child):
		if isinstance(child,ListItem):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

class ListItem(BodyElement):
	xmlName="li"
	renderMethod="RenderListItem"
	
	def AddChild(self,child):
		if isinstance(child,Flow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
			
	def MixedContent(self):
		return 1
		

###################
# Object Elements #
###################

class Object(BodyElement,FlowStatic,InlineStatic):
	xmlName="object"

	def __init__(self,parent,data,type):
		BodyElement.__init__(self,parent)
		self.SetData(data)
		self.SetType(type)
		self.width=self.height=None
		self.params={}
		
	def SetData(self,data):
		if isinstance(data,URIReference):
			self.data=data
		else:
			self.data=URIReference(data)

	def SetType(self,mimeType):
		# Currently tracked as a string but we need to parse mimeTypes at some point
		if type(mimeType) in StringTypes:
			self.type=mimeType
		else:
			raise TypeError

	def SetHeight(self,height):
		if isinstance(height,Length) or height is None:
			self.height=height
		else:
			self.height=Length(height)
	
	def SetWidth(self,width):
		if isinstance(width,Length) or width is None:
			self.width=width
		else:
			self.width=Length(width)			

	def AddParam(self,param):
		self.params[param.name]=param
		
	def AddChild(self,child):
		if isinstance(child,ObjectFlow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		
	def Render(self,view):
		# to do: resolve the parameter values against any session variables
		try:
			view.RenderObject(self)
		except NotImplementedError:
			if self.children:
				self.RenderChildren(view)
			else:
				raise
			
class ParamType:
	"""ParaType Enumeration"""
	data=1
	ref=2
	
	MaxValue=2
	
	Strings={
		'DATA':data,
		'REF':ref
		}

def ParseParamType(paramType):
	if not ParamType.Strings.has_key(paramType):
		raise ValueError
	return ParamType.Strings[paramType]


class Param(ObjectFlow):
	xmlName="param"

	def __init__(self,name,value,valuetype=ParamType.data):
		self.SetName(name)
		self.SetValue(value)
		self.SetValueType(valuetype)
		self.type=None
		
	def SetName(self,name):
		if type(name) in StringTypes:
			self.name=name
		else:
			raise TypeError
		
	def SetValue(self,value):
		if type(value) in StringTypes:
			self.value=value
		else:
			raise TypeError

	def SetValueType(self,valueType):
		if type(valueType) is IntType:
			if valueType>0 and valueType<=ParamType.MaxValue:
				self.valueType=valueType
			else:
				raise ValueError
		elif type(valueType) in StringTypes:
			self.valueType=ParseParamType(valueType)
		else:
			raise TypeError

	def SetType(self,mimeType):
		# Currently tracked as a string but we need to parse mimeTypes at some point
		if type(mimeType) in StringTypes or mimeType is None:
			self.type=mimeType
		else:
			raise TypeError

#########################
# Presentation Elements #
#########################

class Bold(SimpleInline):
	xmlName="b"
	renderMethod="RenderBold"
	
class Big(SimpleInline):
	xmlName="big"
	renderMethod="RenderBig"
	
class HorizontalRule(BlockStatic,BodyElement,FlowStatic):
	xmlName="hr"
	renderMethod="RenderHorizontalRule"
	
class Italic(SimpleInline):
	xmlName="i"
	renderMethod="RenderItalic"
	
class Small(SimpleInline):
	xmlName="small"
	renderMethod="RenderSmall"
	
class Subscript(SimpleInline):
	xmlName="sub"
	renderMethod="RenderSubscript"
	
class Superscript(SimpleInline):
	xmlName="sup"
	renderMethod="RenderSuperscript"
	
class Teletype(SimpleInline):
	xmlName="tt"
	renderMethod="RenderTeletype"

##################
# Table Elements #
##################

class Caption(BodyElement):
	xmlName="caption"

	def AddChild(self,child):
		if isinstance(child,Inline):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		

class Column(BodyElement):
	xmlName="col"

	def __init__(self,parent,span=1):
		BodyElement.__init__(self,parent)
		self.SetSpan(span)
	
	def SetSpan(self,span):
		if type(span) in (IntType,LongType):
			self.span=span
		else:
			raise TypeError


class ColumnGroup(BodyElement):
	xmlName="colgroup"

	def __init__(self,parent,span=1):
		BodyElement.__init__(self,parent)
		self.SetSpan(span)
		self.col=[]
		
	def SetSpan(self,span):
		if type(span) in (IntType,LongType):
			self.span=span
		else:
			raise TypeError

	def AddChild(self,child):
		if isinstance(child,Column):
			self.col.append(child)
		else:
			BodyElement.AddChild(self,child)

		
class Table(BlockStatic,BodyElement,FlowStatic):
	xmlName="table"
	renderMethod="RenderTable"
	
	def __init__(self,parent):
		BodyElement.__init__(self,parent)
		self.summary=None
		self.caption=None
		self.colgroup=[]
		self.col=[]
		self.head=None
		self.foot=None
		self.body=[]
	
	def SetSummary(self,summary):
		if type(summary) in StringTypes or summary is None:
			self.summary=summary
		else:
			raise TypeError
		
	def AddChild(self,child):
		if isinstance(child,Caption):
			self.caption=child
		elif isinstance(child,ColumnGroup):
			if self.col:
				raise IMSQTIError("can't add colgroup to table containing col")
			self.colgroup.append(child)
		elif isinstance(child,Column):
			if self.colgroup:
				raise IMSQTIError("can't add col to table containing colgroup")
			self.col.append(child)
		elif isinstance(child,TableHead):
			self.head=child
		elif isinstance(child,TableFoot):
			self.foot=child
		elif isinstance(child,TableBody):
			self.body.append(child)
		else:
			BodyElement.AddChild(self,child)

		
class TableCellScope:
	"""TabelCellScope Enumeration"""
	Row=1
	Col=2
	RowGroup=3
	ColGroup=4
	
	MaxValue=4
	
	Strings={
		'row':Row,
		'col':Col,
		'rowgroup':RowGroup,
		'colgroup':ColGroup
		}
		

def ParseTableCellScope(scope):
	if not TableCellScope.Strings.has_key(scope):
		raise ValueError
	return TableCellScope.Strings[scope]


class TableCell(BodyElement):
	def __init__(self,parent):
		BodyElement.__init__(self,parent)
		self.headers=[]
		self.scope=None
		self.abbr=None
		self.axis=[]
		self.rowspan=1
		self.colspan=1

	def SetHeaders(self,headers):
		if type(headers) in (TupleType,ListType):
			for header in headers:
				if not CheckName(header):
					raise ValueError("%s - header reference does not match XML Name"%header)
			self.headers=headers
		elif type(headers) in StringTypes:
			if not CheckName(headers):
				raise ValueError("%s - header reference does not match XML Name"%headers)
			self.headers=[headers]
		elif headers is None:
			self.headers=[]
		else:
			raise TypeError
	
	def SetScope(self,scope):
		if type(scope) is IntType:
			if scope>0 and scope<=TableCellScope.MaxValue:
				self.scope=scope
			else:
				raise ValueError
		elif type(scope) in StringTypes:
			self.scope=ParseTableCellScope(scope)
		else:
			raise TypeError

	def SetAbbr(self,abbr):
		if type(abbr) in StringTypes or abbr is None:
			self.abbr=abbr
		else:
			raise TypeError
	
	def SetAxis(self,axis):
		if type(axis) in (TupleType,ListType):
			if split(join(axis,','))!=axis:
				raise ValueError("category name cannot contain comma")	
			self.axis=axis
		elif type(axis) in StringTypes:
			if len(split(axis))>1:
				raise ValueError("category name cannot contain comma")
			self.axis=[axis]
		elif axis is None:
			self.axis=[]
		else:
			raise TypeError
	
	def SetRowSpan(self,span):
		if type(span) in (IntType,LongType):
			self.rowspan=span
		else:
			raise TypeError

	def SetColSpan(self,span):
		if type(span) in (IntType,LongType):
			self.colspan=span
		else:
			raise TypeError

	def AddChild(self,child):
		if isinstance(child,Flow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		

class TableHead(BodyElement):
	xmlName="thead"

	def AddChild(self,child):
		if isinstance(child,TableRow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

class TableBody(BodyElement):
	xmlName="tbody"

	def AddChild(self,child):
		if isinstance(child,TableRow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

class TableFoot(BodyElement):
	xmlName="tfoot"

	def AddChild(self,child):
		if isinstance(child,TableRow):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

class TableRow(BodyElement):
	xmlName="tr"

	def AddChild(self,child):
		if isinstance(child,TableCell):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
	
class TableDataCell(TableCell):
	xmlName="td"

class TableHeadCell(TableCell):
	xmlName="th"


#################
# Image Element #
#################

class Image(AtomicInline):
	xmlName="img"

	def __init__(self,parent,src,alt):
		BodyElement.__init__(self,parent)
		self.SetSrc(src)
		self.SetAlt(alt)
		self.longdesc=None
		self.height=self.width=None

	def SetSrc(self,src):
		if isinstance(src,URIReference):
			self.src=src
		else:
			self.src=URIReference(src)

	def SetAlt(self,alt):
		if type(alt) in StringTypes:
			self.alt=alt
		else:
			raise TypeError
	
	def SetLongDesc(self,longdesc):
		if isinstance(longdesc,URIReference) or longdesc is None:
			self.longdesc=longdesc
		else:
			self.longdesc=URIReference(longdesc)
	
	def SetHeight(self,height):
		if isinstance(height,Length) or height is None:
			self.height=height
		else:
			self.height=Length(height)
	
	def SetWidth(self,width):
		if isinstance(width,Length) or width is None:
			self.width=width
		else:
			self.width=Length(width)			

	def Render(self,view):
		try:
			view.RenderImage(self)
		except NotImplementedError:
			if self.alt:
				view.RenderText(self.alt)
			else:
				raise

class Length:
	def __init__(self,value,isPercent=None):
		if type(value) in StringTypes:
			if value[-1]=='%':
				self.isPercent=1
				self.value=ParseInteger(value[:-1])
			else:
				self.isPercent=0
				self.value=ParseInteger(value)
		elif type(value) in (IntType,LongType):
			if isPercent is None:
				raise ValueError
			self.value=value
			self.isPercent=isPercent
		elif isinstance(value,Length):
			self.value=value.value
			self.isPercent=value.isPercent
		else:
			raise TypeError


#####################
# Hypertext Element #
#####################

class HypertextLink(SimpleInline):
	xmlName="a"
	renderMethod="RenderHypertextLink"
	
	def __init__(self,parent,href):
		searchParent=parent
		while searchParent:
			if isinstance(searchParent,AssessmentItem):
				break
			elif isinstance(searchParent,HypertextLink):
				raise IMSQTIError("hypertext link cannot be descended from another link")
			else:
				searchParent=searchParent.parent
		BodyElement.__init__(self,parent)
		self.SetHref(href)
		self.type=None
	
	def SetHref(self,href):
		if isinstance(href,URIReference):
			self.href=href
		else:
			self.href=URIReference(href)
	
	def SetType(self,mimeType):
		# Currently tracked as a string but we need to parse mimeTypes at some point
		if type(mimeType) in StringTypes or mimeType is None:
			self.type=mimeType
		else:
			raise TypeError
					

################
# Interactions #
################

class Interaction(BodyElement):
	def __init__(self,parent,responseIdentifier):
		BodyElement.__init__(self,parent)
		self.SetResponseIdentifier(responseIdentifier)
		self.item=self.GetParentItem()

	def SetResponseIdentifier(self,responseIdentifier):
		if type(responseIdentifier) in StringTypes:
			self.responseIdentifier=ParseIdentifier(responseIdentifier)
		else:
			raise TypeError

class BlockInteraction(Block,Flow,Interaction):
	def __init__(self,parent,responseIdentifier):
		Interaction.__init__(self,parent,responseIdentifier)
		self.prompt=Prompt(self)
		self.children=[]
		
	def AddChild(self,child):
		if isinstance(child,Prompt):
			pass
		else:
			raise IMSQTIError("Interaction takes no children")

class Prompt(BodyElement):
	def AddChild(self,child):
		if isinstance(child,InlineStatic):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

	def MixedContent(self):
		return 1
		

class Choice(BodyElement):
	def __init__(self,parent,identifier):
		BodyElement.__init__(self,parent)
		self.SetIdentifier(identifier)
		self.fixed=0
	
	def SetIdentifier(self,identifier):
		if type(identifier) in StringTypes:
			self.identifier=ParseIdentifier(identifier)
		else:
			raise TypeError

	def SetFixed(self,fixed):
		if fixed:
			self.fixed=1
		else:
			self.fixed=0
	
class ChoiceInteraction(BlockInteraction):
	renderMethod="RenderChoiceInteraction"
	
	def __init__(self,parent,responseIdentifier,shuffle=0,maxChoices=1):
		BlockInteraction.__init__(self,parent,responseIdentifier)
		self.SetShuffle(shuffle)
		self.SetMaxChoices(maxChoices)
		decl=self.item.LookupVariableDeclaration(responseIdentifier)
		if not isinstance(decl,ResponseDeclaration):
			raise IMSQTIError("%s is not a declared response variable"%responseIdentifier)
		if not (decl.baseType==BaseType.Identifier and
			decl.cardinality in (Cardinality.Single,Cardinality.Multiple)):
			raise IMSQTIError("%s: The choiceInteraction must be bound to a \
				responseVariable with a baseType of identifier and single or \
				multiple cardinality."%responseIdentifier)
		
	def SetShuffle(self,shuffle):
		if shuffle:
			self.shuffle=1
		else:
			self.shuffle=0

	def SetMaxChoices(self,maxChoices):
		if type(maxChoices) in (IntType,LongType):
			if maxChoices<0:
				raise ValueError("Negative value for max choices: %i"%maxChoices)
			if maxChoices!=1:
				decl=self.item.LookupVariableDeclaration(self.responseIdentifier)
				if decl.cardinality!=Cardinality.Multiple:
					raise IMSQTIError("%s:  If maxChoices is greater than 1 (or 0) \
						then the interaction must be bound to a response with multiple \
						cardinality."%self.responseIdentifier)
			self.maxChoices=maxChoices
		else:
			raise TypeError

	def AddChild(self,child):
		if isinstance(child,SimpleChoice):
			self.children.append(child)
		else:
			BlockInteraction.AddChild(self,child)

	def Select(self,choice,session):
		"""Select returns 0 if the selection would cause maxChoices
		to be exceeded, but only in the multiple cardinality case.  For
		single cardinality cases (in which maxChoices is always 1) the
		new selection simply replaces the old."""
		value=session.GetResponseValue(self.responseIdentifier)
		if value[0]==Cardinality.Single:
			value[2]=choice.identifier
		else:
			if value[2] is None:
				# First selection always works
				value[2]=[choice.identifier]
			elif choice.identifier in value[2]:
				# Unselecting always works
				value[2].remove(choice.identifier)
			elif self.maxChoices==0 or len(value[2])<self.maxChoices:
				# Room for one more selection
				value[2].append(choice.identifier)
			else:
				# This selection exceeds maxChoices
				return 0
		return 1		
			
class OrderInteraction(BlockInteraction):
	renderMethod="RenderOrderInteraction"

	def __init__(self,parent,responseIdentifier,shuffle=0):
		BlockInteraction.__init__(self,parent,responseIdentifier)
		self.SetShuffle(shuffle)
		self.orientation=None
		decl=self.item.LookupVariableDeclaration(responseIdentifier)
		if not isinstance(decl,ResponseDeclaration):
			raise IMSQTIError("%s is not a declared response variable"%responseIdentifier)
		if not (decl.baseType==BaseType.Identifier and
			decl.cardinality==Cardinality.Ordered):
			raise IMSQTIError("%s: The orderInteraction must be bound to a \
				responseVariable with a baseType of identifier and ordered \
				cardinality only."%responseIdentifier)
		
	def SetShuffle(self,shuffle):
		if shuffle:
			self.shuffle=1
		else:
			self.shuffle=0

	def SetOrientation(self,orientation):
		if orientation in (Orientation.Vertical,Orientation.Horizontal,None):
			self.orientation=orientation
		else:
			raise TypeError
			
	def AddChild(self,child):
		if isinstance(child,SimpleChoice):
			self.children.append(child)
		else:
			BlockInteraction.AddChild(self,child)
	
		
class SimpleChoice(Choice):
	def AddChild(self,child):
		if isinstance(child,FlowStatic):
			self.children.append(child)
		else:
			raise IMSQTIError("Bad child for simpleChoice")
			
	def MixedContent(self):
		return 1

class StringInteraction:
	def __init__(self,stringIdentifier):
		self.base=10
		self.SetStringIdentifier(stringIdentifier)
		self.expectedLength=None
		self.patternMask=None
		self.placeholderText=None
		
	def SetBase(self,base):
		if type(base) in (IntType,LongType):
			if base<2:
				raise ValueError("Bad value for base: %i"%base)
			self.base=base
		elif base is None:
			self.base=None
		else:
			raise TypeError
		
	def SetStringIdentifier(self,stringIdentifier):
		if type(stringIdentifier) in StringTypes:
			stringIdentifier=ParseIdentifier(stringIdentifier)
			decl=self.item.LookupVariableDeclaration(stringIdentifier)
			if not isinstance(decl,ResponseDeclaration):
				raise IMSQTIError("%s is not a declared response variable"%stringIdentifier)
			if not (decl.baseType==BaseType.String):
				raise IMSQTIError("%s used as stringIdentifier must be bound to base type string"%
					stringIdentifier)
			self.stringIdentifier=stringIdentifier
		elif stringIdentifier is None:
			self.stringIdentifier=None
		else:
			raise TypeError

	def SetExpectedLength(self,expectedLength):
		if type(expectedLength) in (IntType,LongType):
			if expectedLength<1:
				raise ValueError("Bad value for expectedLength: %i"%expectedLength)
			self.expectedLength=expectedLength
		elif expectedLength is None:
			self.expectedLength=None
		else:
			raise TypeError
	
	def SetPatternMask(self,patternMask):
		if type(patternMask) in StringTypes:
			self.patternMask=RegularExpression(patternMask)
		elif isinstance(patternMask,RegularExpression):
			self.patternMask=patternMask
		elif patternMask is None:
			self.patternMask=None
		else:
			raise TypeError
	
	def SetPlaceholderText(self,placeholderText):
		if type(placeholderText) in StringTypes or placeholderText is None:
			self.placeholderText=placeholderText
		else:
			raise TypeError


class ExtendedTextInteraction(BlockInteraction,StringInteraction):
	renderMethod="RenderExtendedTextInteraction"
	
	def __init__(self,parent,responseIdentifier,stringIdentifier=None):
		BlockInteraction.__init__(self,parent,responseIdentifier)
		decl=self.item.LookupVariableDeclaration(responseIdentifier)
		if not isinstance(decl,ResponseDeclaration):
			raise IMSQTIError("%s is not a declared response variable"%responseIdentifier)
		if not (decl.baseType in (BaseType.String,BaseType.Integer,BaseType.String) and
			decl.cardinality in (Cardinality.Single,Cardinality.Multiple,Cardinality.Ordered)):
			raise IMSQTIError("%s: stringInteraction must be bound to string or integer response type with single, multiple or ordered cardinality"%responseIdentifier)
		StringInteraction.__init__(self,stringIdentifier)
		self.maxStrings=1
		self.expectedLines=None
		
	def SetStringIdentifier(self,stringIdentifier):
		if type(stringIdentifier) in StringTypes:
			stringIdentifier=ParseIdentifier(stringIdentifier)
			responseDecl=self.item.LookupVariableDeclaration(self.responseIdentifier)
			stringDecl=self.item.LookupVariableDeclaration(stringIdentifier)
			if not isinstance(stringDecl,ResponseDeclaration):
				raise IMSQTIError("%s is not a declared response variable"%stringIdentifier)
			if not (stringDecl.baseType==BaseType.String and responseDecl.baseType!=BaseType.String
				and stringDecl.cardinality==responseDecl.cardinality):
				raise IMSQTIError("%s used as stringIdentifier must be bound to a string with matching cardinality"%stringIdentifier)
			self.stringIdentifier=stringIdentifier
		elif stringIdentifier is None:
			self.stringIdentifier=None
		else:
			raise TypeError
			
	def SetMaxStrings(self,maxStrings):
		if type(maxStrings) in (IntType,LongType):
			if maxStrings<1:
				raise ValueError("Bad value for maxStrings: %i"%base)
			elif maxStrings>1:
				# check we are bound to a container
				decl=self.item.LookupVariableDeclaration(self.responseIdentifier)
				if decl.cardinality==Cardinality.Single:
					raise IMSQTIError("%s: maxStrings mismatched with response cardinality"%self.responseIdentifier)								 
			self.maxStrings=maxStrings
		elif maxStrings is None:
			self.maxStrings=None
		else:
			raise TypeError
		
	def SetExpectedLines(self,expectedLines):
		if type(expectedLines) in (IntType,LongType):
			if expectedLines<1:
				raise ValueError("Bad value for expectedLines: %i"%expectedLines)
			self.expectedLines=expectedLines
		elif expectedLines is None:
			self.expectedLines=None
		else:
			raise TypeError
	

#######################
# Response Processing #
#######################

class ResponseProcessing:
	def __init__(self):
		self.template=None
		self.templateLocation=None
		self.responseRule=[]
	
	def SetTemplate(self,template):
		if isinstance(template,URIReference) or template is None:
			self.template=template
		else:
			self.template=URIReference(template)
	
	def SetTemplateLocation(self,templateLocation):
		if isinstance(templateLocation,URIReference) or templateLocation is None:
			self.templateLocation=templateLocation
			
		else:
			self.templateLocation=URIReference(templateLocation)

	def AddResponseRule(self,responseRule):
		if isinstance(responseRule,ResponseRule):
			self.responseRule.append(responseRule)
		else:
			raise TypeError

	def Run(self,session):
		for rule in self.responseRule:
			if rule.Run(session):
				break
		

class ResponseRule:
	def Run(self,session): raise NotImplementedError
	
class ExitResponse(ResponseRule):
	def Run(self,session):
		return 1
	
class ExpressionContainer:
	def AddExpression(self,expression):
		raise IMSQTIError("expression not allowed here")
	

class SetOutcomeValue(ResponseRule,ExpressionContainer):
	def __init__(self,item,identifier):
		self.SetIdentifier(item,identifier)
		self.expression=None
	
	def SetIdentifier(self,item,identifier):
		if type(identifier) in StringTypes:
			decl=item.LookupVariableDeclaration(identifier)
			if not isinstance(decl,OutcomeDeclaration):
				raise IMSQTIError("%s is not a declared outcome variable"%identifier)
			self.identifier=identifier
			self.decl=decl
		else:
			raise TypeError

	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				self.expression=expression
				try:
					self.Run(None)
				except IMSQTIError:
					self.expression=None
					raise
			else:
				raise IMSQTIError("setOutcomeValue can contain only 1 sub-expression")
		else:
			raise TypeError

	def Run(self,session):
		cardinality,baseType,value=self.expression.Evaluate(session)
		if session:
			currValue=session.GetOutcomeValue(self.identifier)
		else:
			currValue=[self.decl.cardinality,self.decl.baseType,None]
		if currValue[0]!=cardinality:
			raise IMSQTIError("cardinality mismatch in setOutcomeVariable")
		if not CompareBaseTypes(currValue[1],baseType):
			raise IMSQTIError("baseType mismatch in setOutcomeVariable")
		currValue[2]=value
		
class ResponseCondition(ResponseRule):
	def __init__(self):
		self.parts=[]

	def AddResponseConditionPart(self,part):
		if len(self.parts)==0:
			if not isinstance(part,ResponseIf):
				raise IMSQTIError("responseCondition must start with responseIf")
		elif isinstance(self.parts[-1],ResponseElse):
			raise IMSQTIError("responseElse must be last part of responseCondition")
		self.parts.append(part)
		  			
	def Run(self,session):
		for part in self.parts:
			if part.expression:
				value=part.expression.Evaluate(session)
				if not CompareBaseTypes(value[1],BaseType.Boolean):
					raise IMSQTIError("expression did not evaluate to a boolean")
				runRules=value[2]
			else:
				runRules=1
			if runRules:
				for rule in part.responseRule:
					if rule.Run(session):
						return 1
				return 0
		return 0


class ResponseConditionPart(ExpressionContainer):
	def __init__(self):
		self.expression=None
		self.responseRule=[]
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if cardinality!=Cardinality.Single:
					raise IMSQTIError("cardinality mismatch in responseCondition part")
				if not CompareBaseTypes(baseType,BaseType.Boolean):
					raise IMSQTIError("baseType mismatch in responseCondition part")
				self.expression=expression
			else:
				raise IMSQTIError("too many expressions in responseCondition part")
		else:
			raise TypeError

	def AddResponseRule(self,responseRule):
		if isinstance(responseRule,ResponseRule):
			self.responseRule.append(responseRule)
		else:
			raise TypeError
			
class ResponseIf(ResponseConditionPart): pass

class ResponseElseIf(ResponseConditionPart): pass

class ResponseElse(ResponseConditionPart):
	def AddExpression(self,expression):
		raise IMSQTIError("responseElse cannot contain expression")

class Expression:
	def Evaluate(self,session): raise NotImplementedError
	
class BaseValue(Expression):
	def __init__(self,baseType):
		self.SetBaseType(baseType)
		self.value=None
	
	def SetBaseType(self,baseType):
		if type(baseType) is IntType:
			if baseType>0 and baseType<=BaseType.MaxValue:
				self.baseType=baseType
			else:
				raise ValueError
		elif type(baseType) in StringTypes:
			self.baseType=ParseBaseType(baseType)
		else:
			raise TypeError

	def SetValue(self,value):
		CheckValue(Cardinality.Single,self.baseType,value)
		self.value=value
	
	def Evaluate(self,session):
		return (Cardinality.Single,self.baseType,self.value)
			
class AndOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.children=[]
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			self.children.append(expression)
			try:
				self.Evaluate(None)
			except IMSQTIError:
				del self.children[-1]
				raise
		else:
			raise TypeError
						
	def Evaluate(self,session):
		result=1
		for child in self.children:
			cardinality,baseType,value=child.Evaluate(session)
			if cardinality!=Cardinality.Single:
				raise IMSQTIError("expected single cardinality in and operator")
			if not CompareBaseTypes(baseType,BaseType.Boolean):
				raise IMSQTIError("expected boolean in and operator")
			if value==0:
				result=0
				break
			elif value is None:
				result=None
				break
		return (Cardinality.Single,BaseType.Boolean,result)

class OrOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.children=[]
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			self.children.append(expression)
			try:
				self.Evaluate(None)
			except IMSQTIError:
				del self.children[-1]
				raise
		else:
			raise TypeError
						
	def Evaluate(self,session):
		result=0
		for child in self.children:
			cardinality,baseType,value=child.Evaluate(session)
			if cardinality!=Cardinality.Single:
				raise IMSQTIError("expected single cardinality in and operator")
			if not CompareBaseTypes(baseType,BaseType.Boolean):
				raise IMSQTIError("expected boolean in and operator")
			if value==1:
				result=1
				break
			elif value is None:
				result=None
		return (Cardinality.Single,BaseType.Boolean,result)

class NotOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.expression=None
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				try:
					self.expression=expression
					self.Evaluate(None)
				except IMSQTIError:
					self.expression=None
					raise
			else:
				raise IMSQTIError("not operator takes exactly one sub-expression")
		else:
			raise TypeError
						
	def Evaluate(self,session):
		cardinality,baseType,value=self.expression.Evaluate(session)
		if cardinality!=Cardinality.Single:
			raise IMSQTIError("cardinality mismatch in not operator")
		if not CompareBaseTypes(baseType,BaseType.Boolean):
			raise IMSQTIError("not operator expected boolean sub-expression")
		if value is None:
			result=None
		else:
			result=not value
		return (Cardinality.Single,BaseType.Boolean,result)

class AnyNOperator(Expression,ExpressionContainer):
	def __init__(self,min,max):
		self.children=[]
		self.SetMinMax(min,max)
	
	def SetMinMax(self,min,max):
		if type(min) in (IntType,LongType) and type(max) in (IntType,LongType):
			if min<max and min>0:
				self.min=min
				self.max=max
			else:
				raise ValueError
		else:
			raise TypeError
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			self.children.append(expression)
			try:
				self.Evaluate(None)
			except IMSQTIError:
				del self.children[-1]
				raise
		else:
			raise TypeError
						
	def Evaluate(self,session):
		nTrue=0
		nFalse=0
		nNull=0
		for child in self.children:
			cardinality,baseType,value=child.Evaluate(session)
			if cardinality!=Cardinality.Single:
				raise IMSQTIError("expected single cardinality in anyN operator")
			if not CompareBaseTypes(baseType,BaseType.Boolean):
				raise IMSQTIError("expected boolean in anyN operator")
			if value==1:
				nTrue+=1
			elif value==0:
				nFalse+=1
			else:
				nNull+=1
		if nTrue>self.max:
			result=0
		elif nTrue>=self.min:
			if nTrue+nNull>self.max:
				result=None
			else:
				result=1
		elif nTrue+nNull>=self.min:
			result=None
		else:
			result=0
		return (Cardinality.Single,BaseType.Boolean,result)

class NullOperator(Expression):
	def Evaluate(self,session):
		return (Cardinality.Single,None,None)
			
class IsNullOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.expression=None
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				self.expression=expression
			else:
				raise IMSQTIError("isNull can contain only a single expression")
		else:
			raise TypeError

	def Evaluate(self,session):
		cardinality,baseType,value=self.expression.Evaluate(session)
		if value in (None,"",[],{}):
			result=1
		else:
			result=0
		return (Cardinality.Single,BaseType.Boolean,result)
		
class MultipleOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.children=[]
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			self.children.append(expression)
			try:
				self.Evaluate(None)
			except IMSQTIError:
				del self.children[-1]
				raise
		else:
			raise TypeError
	
	def Evaluate(self,session):
		result=[]
		resultType=None
		for child in self.children:
			cardinality,baseType,value=child.Evaluate(session)
			if not (cardinality in (Cardinality.Single,Cardinality.Multiple)):
				raise IMSQTIError("cardinality mismatch in multiple operator")
			if not CompareBaseTypes(baseType,resultType):
				raise IMSQTIError("baseType mismatch in multiple operator")
			if resultType is None:
				resultType=baseType
			if cardinality==Cardinality.Single:
				result.append(value)
			else:
				result=result+value
		return (Cardinality.Multiple,resultType,result)
		
class OrderedOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.children=[]
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			self.children.append(expression)
			try:
				self.Evaluate(None)
			except IMSQTIError:
				del self.children[-1]
				raise
		else:
			raise TypeError
					
	def Evaluate(self,session):
		result=[]
		resultType=None
		for child in self.children:
			cardinality,baseType,value=child.Evaluate(session)
			if not (cardinality in (Cardinality.Single,Cardinality.Ordered)):
				raise IMSQTIError("cardinality mismatch in ordered operator")
			if not CompareBaseTypes(baseType,resultType):
				raise IMSQTIError("baseType mismatch in ordered operator")
			if resultType is None:
				resultType=baseType
			if cardinality==Cardinality.Single:
				result.append(value)
			else:
				result=result+value
		return (Cardinality.Ordered,resultType,result)
		
class MemberOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.member=None
		self.container=None
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.member is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if cardinality!=Cardinality.Single:
					raise IMSQTIError("cardinality mismatch in member operator")
				if baseType==BaseType.Duration:
					raise IMSQTIError("member operator cannot be used with duration type")
				self.member=expression
			elif self.container is None:
				self.container=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.container=None
					raise
			else:
				raise IMSQTIError("member operator takes only 2 sub-expressions")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		mCardinality,mBaseType,mValue=self.member.Evaluate(session)
		cCardinality,cBaseType,cValue=self.container.Evaluate(session)
		if mCardinality!=Cardinality.Single or not (
			cCardinality in (Cardinality.Multiple,Cardinality.Ordered)):
			raise IMSQTIError("cardinality mismatch in member operator")
		if mBaseType==BaseType.Duration:
			raise IMSQTIError("member operator cannot be used with duration type")
		if not CompareBaseTypes(mBaseType,cBaseType):
			raise IMSQTIError("type mismatch in member operator")
		if mValue is None or not cValue:
			result=None
		else:
			result=0
			for v in cValue:
				if mValue==v:
					result=1
					break
		return (Cardinality.Single,BaseType.Boolean,result)
				
class IndexOperator(Expression,ExpressionContainer):
	def __init__(self,n):
		self.SetN(n)
		self.expression=None
	
	def SetN(self,n):
		if type(n) in (IntType,LongType):
			if n>0:
				self.n=n
			else:
				raise ValueError
		else:
			raise TypeError
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				self.expression=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.expression=None
					raise
			else:
				raise IMSQTIError("index operator takes only 1 sub-expression")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		cardinality,baseType,value=self.expression.Evaluate(session)
		if cardinality!=Cardinality.Ordered:
			raise IMSQTIError("index operator requires sub-expression with ordered cardinality")
		if value is None or self.n>len(value):
			result=None
		else:
			result=value[self.n-1]
		return (Cardinality.Single,baseType,result)
				
class FieldValueOperator(Expression,ExpressionContainer):
	def __init__(self,fieldIdentifier):
		self.SetFieldIdentifier(fieldIdentifier)
		self.expression=None
	
	def SetFieldIdentifier(self,fieldIdentifier):
		if type(fieldIdentifier) in StringTypes:
			self.fieldIdentifier=ParseIdentifier(fieldIdentifier)
		else:
			raise TypeError
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				self.expression=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.expression=None
					raise
			else:
				raise IMSQTIError("fieldValue operator takes only 1 sub-expression")
		else:
			raise TypeError
						
	def Evaluate(self,session):
		cardinality,baseType,value=self.expression.Evaluate(session)
		if cardinality!=Cardinality.Record:
			raise IMSQTIError("fieldValue operator requires sub-expression with record cardinality")
		if value is None:
			result=None
		else:
			value=value.get(self.fieldIdentifier)
			if value is None:
				result=None
			else:
				baseType=value[0]
				result=value[1]
		return (Cardinality.Single,baseType,result)
						
class RandomOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.expression=None
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expression is None:
				self.expression=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.expression=None
					raise
			else:
				raise IMSQTIError("random operator takes only 1 sub-expression")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		cardinality,baseType,value=self.expression.Evaluate(session)
		if not (cardinality in (Cardinality.Multiple,Cardinality.Ordered)):
			raise IMSQTIError("random operator requires sub-expression with multiple or ordered cardinality")
		if not value:
			result=None
		else:
			result=choice(value)
		return (Cardinality.Single,baseType,result)

class DeleteOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.unwanted=None
		self.container=None
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.unwanted is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if cardinality!=Cardinality.Single:
					raise IMSQTIError("cardinality mismatch in delete operator")
				self.unwanted=expression
			elif self.container is None:
				self.container=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.container=None
					raise
			else:
				raise IMSQTIError("delete operator takes only 2 sub-expressions")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		dCardinality,dBaseType,dValue=self.unwanted.Evaluate(session)
		cCardinality,cBaseType,cValue=self.container.Evaluate(session)
		if dCardinality!=Cardinality.Single or not (
			cCardinality in (Cardinality.Multiple,Cardinality.Ordered)):
			raise IMSQTIError("cardinality mismatch in delete operator")
		if not CompareBaseTypes(dBaseType,cBaseType):
			raise IMSQTIError("type mismatch in delete operator")
		if dValue is None or not cValue:
			result=None
		else:
			result=[]
			for v in cValue:
				if dValue==v:
					continue
				result.append(v)
		return (cCardinality,cBaseType,result)

class ContainsOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.container=None
		self.subContainer=None
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.container is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if not (cardinality in (Cardinality.Multiple,Cardinality.Ordered)):
					raise IMSQTIError("cardinality mismatch in contains operator")
				if baseType==BaseType.Duration:
					raise IMSQTIError("contains operator cannot be used with duration type")
				self.container=expression
			elif self.subContainer is None:
				self.subContainer=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.subContainer=None
					raise
			else:
				raise IMSQTIError("contains operator takes only 2 sub-expressions")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		cCardinality,cBaseType,cValue=self.container.Evaluate(session)
		subCardinality,subBaseType,subValue=self.subContainer.Evaluate(session)
		if cCardinality!=subCardinality or not (
			cCardinality in (Cardinality.Multiple,Cardinality.Ordered)):
			raise IMSQTIError("cardinality mismatch in contains operator")
		if cBaseType==BaseType.Duration or subBaseType==BaseType.Duration:
			raise IMSQTIError("contains operator cannot be used with duration type")
		if not CompareBaseTypes(cBaseType,subBaseType):
			raise IMSQTIError("type mismatch in contains operator")
		if not cValue or not subValue:
			result=None
		elif cCardinality==Cardinality.Multiple:
			# fairly dumb algorithm, make a shallow copy of container and remove
			# items from subContainer in turn until you get a result
			cValue=copy(cValue)
			result=1
			for v in subValue:
				try:
					index=cValue.index(v)
				except ValueError:
					result=0
					break
				del cValue[index]	
		else: # ordered
			# really dumb algorithm, performs badly with large containers
			result=0
			for i in range(0,len(cValue)-len(subValue),1):
				if cValue[i:i+len(subValue)]==subValue:
					result=1
					break
		return (Cardinality.Single,BaseType.Boolean,result)

class StringMatchOperator(Expression,ExpressionContainer):
	def __init__(self,caseSensitive,substring):
		self.stringValueA=None
		self.stringValueB=None
		self.SetCaseSensitive(caseSensitive)
		self.SetSubstring(substring)
	
	def SetCaseSensitive(self,caseSensitive):
		if caseSensitive in (0,1):
			self.caseSensitive=caseSensitive
		else:
			raise ValueError
		
	def SetSubstring(self,substring):
		if substring in (0,1):
			self.substring=substring
		else:
			raise ValueError
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.stringValueA is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if cardinality!=Cardinality.Single:
					raise IMSQTIError("cardinality mismatch in stringMatch operator")
				if not CompareBaseTypes(baseType,BaseType.String):
					raise IMSQTIError("baseType mismatch in stringMatch operator")
				self.stringValueA=expression
			elif self.stringValueB is None:
				self.stringValueB=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.stringValueB=None
					raise
			else:
				raise IMSQTIError("stringMatch operator takes excactly 2 sub-expressions")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		aCardinality,aBaseType,aValue=self.stringValueA.Evaluate(session)
		bCardinality,bBaseType,bValue=self.stringValueB.Evaluate(session)
		if aCardinality!=bCardinality and aCardinality!=Cardinality.Single:
			raise IMSQTIError("cardinality mismatch in stringMatch operator")
		if not (CompareBaseTypes(aBaseType,BaseType.String) and
			CompareBaseTypes(bBaseType,BaseType.String)):
			raise IMSQTIError("baseType mismatch in stringMatch operator")
		if not aValue or not bValue:
			result=None
		else:
			if not self.caseSensitive:
				aValue=aValue.lower()
				bValue=bValue.lower()
			if self.substring:
				result=aValue.find(bValue)>=0
			else:
				result=(aValue==bValue)
		return (Cardinality.Single,BaseType.Boolean,result)


class SubstringOperator(Expression,ExpressionContainer):
	def __init__(self,caseSensitive):
		self.stringValue=None
		self.subStringValue=None
		self.SetCaseSensitive(caseSensitive)
	
	def SetCaseSensitive(self,caseSensitive):
		if caseSensitive in (0,1):
			self.caseSensitive=caseSensitive
		else:
			raise ValueError
		
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.subStringValue is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if cardinality!=Cardinality.Single:
					raise IMSQTIError("cardinality mismatch in substring operator")
				if not CompareBaseTypes(baseType,BaseType.String):
					raise IMSQTIError("baseType mismatch in substring operator")
				self.subStringValue=expression
			elif self.stringValue is None:
				self.stringValue=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.stringValue=None
					raise
			else:
				raise IMSQTIError("substring operator takes excactly 2 sub-expressions")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		sCardinality,sBaseType,sValue=self.stringValue.Evaluate(session)
		subCardinality,subBaseType,subValue=self.subStringValue.Evaluate(session)
		if sCardinality!=subCardinality and sCardinality!=Cardinality.Single:
			raise IMSQTIError("cardinality mismatch in substring operator")
		if not (CompareBaseTypes(sBaseType,BaseType.String) and
			CompareBaseTypes(subBaseType,BaseType.String)):
			raise IMSQTIError("baseType mismatch in substring operator")
		if not sValue or not subValue:
			result=None
		else:
			if not self.caseSensitive:
				sValue=sValue.lower()
				subValue=subValue.lower()
			result=sValue.find(subValue)>=0
		return (Cardinality.Single,BaseType.Boolean,result)
								
class MatchOperator(Expression,ExpressionContainer):
	def __init__(self):
		self.expressionA=None
		self.expressionB=None
	
	def AddExpression(self,expression):
		if isinstance(expression,Expression):
			if self.expressionA is None:
				cardinality,baseType,value=expression.Evaluate(None)
				if baseType==BaseType.Duration:
					raise IMSQTIError("match operator cannot be used with duration type")
				self.expressionA=expression
			elif self.expressionB is None:
				self.expressionB=expression
				try:
					self.Evaluate(None)
				except IMSQTIError:
					self.expressionB=None
					raise
			else:
				raise IMSQTIError("match operator takes excactly 2 sub-expressions")
		else:
			raise TypeError
					
	def Evaluate(self,session):
		aCardinality,aBaseType,aValue=self.expressionA.Evaluate(session)
		bCardinality,bBaseType,bValue=self.expressionB.Evaluate(session)
		if aCardinality!=bCardinality:
			raise IMSQTIError("cardinality mismatch in match operator")
		if aBaseType==BaseType.Duration or bBaseType==BaseType.Duration:
			raise IMSQTIError("match operator cannot be used with duration type")
		if not CompareBaseTypes(aBaseType,bBaseType):
			raise IMSQTIError("baseType mismatch in match operator")
		if IsNullValue(aValue) or IsNullValue(bValue):
			result=None
		else:
			result=MatchValues(aCardinality,aBaseType,aValue,bValue)
		return (Cardinality.Single,BaseType.Boolean,result)
								
class VariableOperator(Expression):
	def __init__(self,item,identifier):
		self.SetIdentifier(item,identifier)
	
	def SetIdentifier(self,item,identifier):
		if type(identifier) in StringTypes:
			decl=item.LookupVariableDeclaration(identifier)
			if not decl:
				raise IMSQTIError("%s is not a declared variable"%identifier)
			self.identifier=identifier
			self.decl=decl
		else:
			raise TypeError

	def Evaluate(self,session):
		if session:
			return session.GetVariableValue(self.identifier)
		else:
			return (self.decl.cardinality,self.decl.baseType,None)
			
class DefaultOperator(VariableOperator):
	def Evaluate(self,session):
		return (self.decl.cardinality,self.decl.baseType,self.decl.defaultValue)
		
class CorrectOperator(VariableOperator):
	def SetIdentifier(self,item,identifier):
		if type(identifier) in StringTypes:
			decl=item.LookupVariableDeclaration(identifier)
			if not isinstance(decl,ResponseDeclaration):
				raise IMSQTIError("%s is not a declared response variable"%identifier)
			self.identifier=identifier
			self.decl=decl
		else:
			raise TypeError

	def Evaluate(self,session):
		return (self.decl.cardinality,self.decl.baseType,self.decl.correctValue)
		
class MapResponseOperator(VariableOperator):
	def SetIdentifier(self,item,identifier):
		if type(identifier) in StringTypes:
			decl=item.LookupVariableDeclaration(identifier)
			if not isinstance(decl,ResponseDeclaration):
				raise IMSQTIError("%s is not a declared response variable"%identifier)
			if decl.mapping is None:
				raise IMSQTIError("%s has no defined mapping"%identifier)
			self.identifier=identifier
			self.decl=decl
		else:
			raise TypeError

	def Evaluate(self,session):
		if session:
			return (Cardinality.Single,BaseType.Float,
				self.decl.mapping.MapValue(session.GetVariableValue(self.identifier)[2]))
		else:
			return (Cardinality.Single,BaseType.Float,None)		

	
##############
# XML Parser #
##############

class AssessmentItemParser(handler.ContentHandler, handler.ErrorHandler):
	def __init__(self):
		self.parser=make_parser()
		self.parser.setFeature(handler.feature_namespaces,1)
		self.parser.setContentHandler(self)
		self.parser.setErrorHandler(self)

	def ReadAssessmentItem(self,f):
		self.ResetParser()
		self.parser.parse(f)
		return self.item
	
	def ResetParser(self):
		self.item=None
		self.cObject=None
		self.objectStack=[]
		self.valueCardinality=None
		self.valueBaseType=None
		self.bodyElement=None
		self.qtiNamespace=None
		self.qtiVersion=None
		self.skipping=0
		self.data=[]
		
	def PrepareValue(self):
		if self.valueCardinality==Cardinality.Record:
			self.value={}
		elif self.valueCardinality in (Cardinality.Multiple,Cardinality.Ordered):
			self.value=[]
		else:
			self.value=None
		
	def startElementNS(self,name,qname,attrs):
		ns,localName=name
		if self.item:
			if self.skipping:
				self.skipping+=1
			elif ns==self.qtiNamespace:
				# make sure we collect any data *before* we start the new element
				# when handling mixed content model (i.e., body elements)
				if self.bodyElement:
					if self.data:
						self.ProcessTextRun()
				method=self.startMethods.get(localName)
				if method:
					method(self,ns,localName,attrs)
				elif self.xhtmlClasses.has_key(localName):
					if self.bodyElement:
						newBodyElement=self.xhtmlClasses[localName](self.bodyElement)
						self.StartBodyElement(newBodyElement,attrs)
				elif self.operatorClasses.has_key(localName):
					if isinstance(self.cObject,ExpressionContainer):
						self.PushObject(self.operatorClasses[localName]())
					else:
						raise IMSQTIError("expression not allowed here")					
				else:
					raise IMSQTIError("Unknown QTI element <%s>"%localName)
			else:
				self.StartSkipped(ns,localName,attrs)
		else:
			if localName!="assessmentItem":
				raise IMSQTIError("expected <assessmentItem>, found <%s>"%localName)
			self.qtiVersion=IMSQTINamespaces.get(ns)
			self.qtiNamespace=ns
			self.item=AssessmentItem(attrs.get((None,'identifier')),
				attrs.get((None,'title')),ParseBoolean(attrs.get((None,'adaptive'))),
				ParseBoolean(attrs.get((None,'timeDependent'))))
			self.item.SetLabel(attrs.get((None,'label')))
			self.item.SetLanguage(attrs.get((XMLNamespace,"lang")))
			self.item.SetToolName(attrs.get((None,'toolName')))		
			self.item.SetToolVersion(attrs.get((None,'toolVersion')))
			
	def endElementNS(self,name,qname):
		ns,localName=name
		if self.skipping:
			self.skipping-=1
		elif ns==self.qtiNamespace:
			method=self.endMethods.get(localName)
			if method:
				method(self,ns,localName)
			elif self.xhtmlClasses.has_key(localName):
				self.EndBodyElement(ns,localName)
			elif self.operatorClasses.has_key(localName):
				self.EndOperator(ns,localName)
				
	def characters(self,content):
		self.data.append(content)
	
	def PushObject(self,newObject):
		self.objectStack.append(self.cObject)
		self.cObject=newObject
	
	def PopObject(self):
		oldObject=self.cObject
		self.cObject=self.objectStack.pop()
		return oldObject
					
	def StartSkipped(self,ns,localName,attrs):
		self.skipping+=1
		print "Skipping element <%s>"%localName
	
	def StartBodyElement(self,newBodyElement,attrs):
		self.data=[]
		self.bodyElement=newBodyElement
		self.bodyElement.SetId(attrs.get((None,'id')))
		styleclass=attrs.get((None,'class'))
		if styleclass is not None:
			self.bodyElement.SetClass(split(styleclass))
		self.bodyElement.SetLanguage(attrs.get((XMLNamespace,"lang")))
		self.bodyElement.SetLabel(attrs.get((None,'label')))
		
	def EndBodyElement(self,ns,localName):
		if self.data:
			self.ProcessTextRun(1)
		self.bodyElement=self.bodyElement.parent
		if not isinstance(self.bodyElement,BodyElement):
			self.bodyElement=None
			
	def EndOperator(self,ns,localName):
		operator=self.PopObject()
		self.cObject.AddExpression(operator)
					
	def ProcessTextRun(self,trailing=0):
		data=join(self.data,'')
		self.data=[]
		if self.bodyElement.PreserveSpace():
			TextRun(self.bodyElement,data)
		elif self.bodyElement.MixedContent():
			trailer=leader=''
			rsData=data.rstrip()
			if len(rsData)!=len(data) and not trailing:
				# trailing space is ignored if we are the last data in an element 
				trailer=' '
			lsData=data.lstrip()
			if len(lsData)!=len(data) and not self.bodyElement.children:
				# leading space is ignored if we are the first data in an element
				leader=' '
			data=join(data.split(),' ')
			TextRun(self.bodyElement,leader+data+trailer)			
			
	def StartAnyNOperator(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.PushObject(AnyNOperator(ParseInteger(attrs.get((None,'min'))),
				ParseInteger(attrs.get((None,'max')))))
		else:
			raise IMSQTIError("<anyN> not allowed here")

	def StartBaseValue(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.PushObject(BaseValue(attrs.get((None,'baseType'))))
			self.data=[]
		else:
			raise IMSQTIError("<baseValue> not allowed here")
	
	def EndBaseValue(self,ns,localName):
		baseValue=self.PopObject()
		baseValue.SetValue(ParseValue(baseValue.baseType,join(self.data,'')))
		self.cObject.AddExpression(baseValue)
		
	def StartBlockquote(self,ns,localName,attrs):
		if self.bodyElement:
			blockquote=Blockquote(self.bodyElement)
			blockquote.SetCite(attrs.get((None,'cite')))
			self.StartBodyElement(blockquote,attrs)
				
	def StartChoiceInteraction(self,ns,localName,attrs):
		shuffle=attrs.get((None,'shuffle'))
		if shuffle is None:
			shuffle=0
		else:
			shuffle=ParseBoolean(shuffle)
		maxChoices=attrs.get((None,'maxChoices'))
		if maxChoices is None:
			maxChoices=1
		else:
			maxChoices=ParseInteger(maxChoices)
		interaction=ChoiceInteraction(self.bodyElement,attrs.get((None,'responseIdentifier')),
			shuffle,maxChoices)
		self.StartBodyElement(interaction,attrs)
				
	def StartCorrectOperator(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.cObject.AddExpression(CorrectOperator(self.item,attrs.get((None,'identifier'))))
		else:
			raise IMSQTIError("<correct> not allowed here")
			
	def StartCorrectResponse(self,ns,localName,attrs):
		if isinstance(self.cObject,ResponseDeclaration):
			self.cObject.SetCorrectInterpretation(attrs.get((None,'interpretation')))
			self.PrepareValue()
		else:
			raise IMSQTIError("<correctResponse> not inside <responseDeclaration>")
	
	def EndCorrectResponse(self,ns,localName):
		if self.value is None:
			raise IMSQTIError("expected <value>")
		self.cObject.SetCorrectValue(self.value)
	
	def StartDefaultOperator(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.cObject.AddExpression(DefaultOperator(self.item,attrs.get((None,'identifier'))))
		else:
			raise IMSQTIError("<default> not allowed here")
			
	def StartDefaultValue(self,ns,localName,attrs):
		if isinstance(self.cObject,VariableDeclaration):
			self.cObject.SetDefaultInterpretation(attrs.get((None,'interpretation')))
			self.PrepareValue()
		else:
			raise IMSQTIError("<defaultValue> not in variable declaration")
		
	def EndDefaultValue(self,ns,localName):
		if self.value is None:
			raise IMSQTIError("expected <value>")
		self.cObject.SetDefaultValue(self.value)
	
	def StartExitResponse(self,ns,localName,attrs):
		if isinstance(self.cObject,(ResponseProcessing,ResponseConditionPart)):
			self.cObject.AddResponseRule(ExitResponse())
		else:
			raise IMSQTIError("<exitResponse> not allowed here")
	
	def StartExtendedTextInteraction(self,ns,localName,attrs):
		interaction=ExtendedTextInteraction(self.bodyElement,attrs.get((None,'responseIdentifier')),
			attrs.get((None,'stringIdentifier')))
		base=attrs.get((None,'base'))
		if base is not None:
			interaction.SetBase(ParseQTIInteger(base))
		expectedLength=attrs.get((None,'expectedLength'))
		if expectedLength is not None:
			interaction.SetExpectedLength(ParseQTIInteger(expectedLength))
		expectedLines=attrs.get((None,'expectedLines'))
		if expectedLines is not None:
			interaction.SetExpectedLines(ParseQTIInteger(expectedLines))
		interaction.SetPatternMask(attrs.get((None,'patternMask')))
		maxStrings=attrs.get((None,'maxStrings'))
		if maxStrings is not None:
			interaction.SetMaxStrings(ParseQTIInteger(maxStrings))
		interaction.SetPlaceholderText(attrs.get((None,'placeholderText')))
		self.StartBodyElement(interaction,attrs)
					
	def StartFieldValue(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.PushObject(FieldValueOperator(attrs.get((None,'fieldIdentifier'))))
		else:
			raise IMSQTIError("<fieldValue> not allowed here")
				
	def StartHypertextLink(self,ns,localName,attrs):
		if self.bodyElement:
			link=HypertextLink(self.bodyElement,attrs.get((None,'href')))
			link.SetType(attrs.get((None,'type')))
			self.StartBodyElement(link,attrs)
	
	def StartImage(self,ns,localname,attrs):
		image=Image(self.bodyElement,attrs.get((None,'src')),attrs.get((None,'alt')))
		image.SetLongDesc(attrs.get((None,'longdesc')))
		image.SetHeight(attrs.get((None,'height')))
		image.SetWidth(attrs.get((None,'width')))
		self.StartBodyElement(image,attrs)		
		
	def StartIndex(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.PushObject(IndexOperator(ParseInteger(attrs.get((None,'n')))))
		else:
			raise IMSQTIError("<index> not allowed here")
				
	def StartItemBody(self,ns,localname,attrs):
		itemBody=self.item.CreateBody()
		self.StartBodyElement(itemBody,attrs)
	
	def StartMapEntry(self,ns,localName,attrs):
		if isinstance(self.cObject,Mapping):
			self.cObject.AddMapEntry(ParseValue(self.cObject.baseType,attrs.get((None,'mapKey'))),
				ParseFloat(attrs.get((None,'mappedValue'))))

	def StartMapping(self,ns,localName,attrs):
		if isinstance(self.cObject,ResponseDeclaration):
			mapping=self.cObject.CreateMapping()
			mapping.SetDefaultValue(ParseFloat(attrs.get((None,'defaultValue'))))
			bound=attrs.get((None,'lowerBound'))
			if bound is not None:
				mapping.SetLowerBound(ParseFloat(bound))
			bound=attrs.get((None,'upperBound'))
			if bound is not None:
				mapping.SetUpperBound(ParseFloat(bound))
			self.PushObject(mapping)
		else:
			raise IMSQTIError("<mapping> not allowed here")

	def EndMapping(self,ns,localName):
		mapping=self.PopObject()
					
	def StartMapResponse(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.cObject.AddExpression(MapResponseOperator(self.item,attrs.get((None,'identifier'))))
		else:
			raise IMSQTIError("<mapResponse> not allowed here")

	def StartObject(self,ns,localname,attrs):
		object=Object(self.bodyElement,attrs.get((None,'data')),attrs.get((None,'type')))
		object.SetHeight(attrs.get((None,'height')))
		object.SetWidth(attrs.get((None,'width')))
		self.StartBodyElement(object,attrs)
		
	def StartOrderInteraction(self,ns,localName,attrs):
		shuffle=attrs.get((None,'shuffle'))
		if shuffle is None:
			shuffle=0
		else:
			shuffle=ParseBoolean(shuffle)
		interaction=OrderInteraction(self.bodyElement,attrs.get((None,'responseIdentifier')),
			shuffle)
		orientation=attrs.get((None,'orientation'))
		if orientation is not None:
			orientation=ParseOrientation(orientation)
		interaction.SetOrientation(orientation)
		self.StartBodyElement(interaction,attrs)
	
	def StartOutcomeDeclaration(self,ns,localName,attrs):
		baseType=attrs.get((None,'baseType'))
		if baseType is not None:
			baseType=ParseBaseType(baseType)
		outcomeDeclaration=OutcomeDeclaration(attrs.get((None,'identifier')),
			ParseCardinality(attrs.get((None,'cardinality'))),baseType)
		outcomeDeclaration.SetInterpretation(attrs.get((None,'interpretation')))
		outcomeDeclaration.SetLongInterpretation(attrs.get((None,'longInterpretation')))
		interpretation=attrs.get((None,'interpretation'))
		if interpretation is not None:
			outcomeDeclaration.SetNormalMaximum(ParseFloat(interpretation))
		self.valueCardinality=outcomeDeclaration.cardinality
		self.valueBaseType=outcomeDeclaration.baseType
		self.PushObject(outcomeDeclaration)
		
	def EndOutcomeDeclaration(self,ns,localName):
		self.item.DeclareVariable(self.cObject)
		self.valueCardinality=None
		self.valueBaseType=None
		self.PopObject()			
	
	def StartParam(self,ns,localName,attrs):
		if isinstance(self.bodyElement,Object):
			param=Param(attrs.get((None,'name')),attrs.get((None,'value')),
				attrs.get((None,'valuetype')))
			param.SetType(attrs.get((None,'type')))
			self.bodyElement.AddParam(param)
		
	def StartPrompt(self,ns,localName,attrs):
		if isinstance(self.bodyElement,BlockInteraction):
			self.bodyElement=self.bodyElement.prompt
						
	def StartQuotation(self,ns,localName,attrs):
		if self.bodyElement:
			q=Quotation(self.bodyElement)
			q.SetCite(attrs.get((None,'cite')))
			self.StartBodyElement(q,attrs)
	
	def StartResponseCondition(self,ns,localName,attrs):
		if isinstance(self.cObject,(ResponseProcessing,ResponseConditionPart)):
			self.PushObject(ResponseCondition())
		else:
			raise IMSQTIError("<responseCondition> not allowed here")
			 
	def EndResponseCondition(self,ns,localName):
		responseCondition=self.PopObject()
		self.cObject.AddResponseRule(responseCondition)
				
	def StartResponseDeclaration(self,ns,localName,attrs):
		baseType=attrs.get((None,'baseType'))
		if baseType is not None:
			baseType=ParseBaseType(baseType)
		responseDeclaration=ResponseDeclaration(attrs.get((None,'identifier')),
			ParseCardinality(attrs.get((None,'cardinality'))),baseType)
		# Use these to provide a context for any contained values
		self.valueCardinality=responseDeclaration.cardinality
		self.valueBaseType=responseDeclaration.baseType
		self.PushObject(responseDeclaration)
	
	def EndResponseDeclaration(self,ns,localName):
		self.item.DeclareVariable(self.cObject)
		self.valueCardinality=None
		self.valueBaseType=None
		self.PopObject()
	
	def StartResponseIf(self,ns,localName,attrs):
		if isinstance(self.cObject,ResponseCondition):
			self.PushObject(ResponseIf())
	
	def StartResponseElseIf(self,ns,localName,attrs):
		if isinstance(self.cObject,ResponseCondition):
			self.PushObject(ResponseElseIf())
	
	def StartResponseElse(self,ns,localName,attrs):
		if isinstance(self.cObject,ResponseCondition):
			self.PushObject(ResponseElse())
	
	def EndResponseConditionPart(self,ns,localName):
		part=self.PopObject()
		self.cObject.AddResponseConditionPart(part)
		
	def StartResponseProcessing(self,ns,localName,attrs):
		responseProcessing=self.item.CreateResponseProcessing()
		responseProcessing.SetTemplate(attrs.get((None,'template')))
		responseProcessing.SetTemplateLocation(attrs.get((None,'templateLocation')))
		self.PushObject(responseProcessing)

	def EndResponseProcessing(self,ns,localName):
		self.PopObject()
		
	def StartSetOutcomeValue(self,ns,localName,attrs):
		if isinstance(self.cObject,(ResponseProcessing,ResponseConditionPart)):
			self.PushObject(SetOutcomeValue(self.item,attrs.get((None,'identifier'))))
		else:
			raise IMSQTIError("<setOutcomeValue> not allowed here")

	def EndSetOutcomeValue(self,ns,localName):
		rule=self.PopObject()
		self.cObject.AddResponseRule(rule)
			
	def StartSimpleChoice(self,ns,localName,attrs):
		if self.bodyElement:
			choice=SimpleChoice(self.bodyElement,attrs.get((None,'identifier')))
			fixed=attrs.get((None,'fixed'))
			if fixed is not None:
				choice.SetFixed(ParseBoolean(fixed))
			self.StartBodyElement(choice,attrs)
	
	def StartStringMatchOperator(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.PushObject(StringMatchOperator(ParseBoolean(attrs.get((None,'caseSensitive'))),
				ParseBoolean(attrs.get((None,'substring')))))
		else:
			raise IMSQTIError("<stringMatch> not allowed here")

	def StartStylesheet(self,ns,localName,attrs):
		stylesheet=Stylesheet(attrs.get((None,'href')),attrs.get((None,'type')))
		stylesheet.SetMedia(attrs.get((None,'media')))
		stylesheet.SetTitle(attrs.get((None,'title')))
		self.item.AddStylesheet(stylesheet)
		
	def StartSubstring(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.PushObject(SubstringOperator(ParseBoolean(attrs.get((None,'caseSensitive')))))
		else:
			raise IMSQTIError("<substring> not allowed here")
				
	def StartTable(self,ns,localName,attrs):
		if self.bodyElement:
			table=Table(self.bodyElement)
			table.SetSummary(attrs.get((None,'summary')))
			self.StartBodyElement(table,attrs)
	
	def StartTableCell(self,tableCell,attrs):
		headers=attrs.get((None,'headers'))
		if headers is not None:
			tableCell.SetHeaders(split(headers))
		if attrs.has_key((None,'scope')):
			tableCell.SetScope(ParseTableCellScope(attrs[(None,'scope')]))
		tableCell.SetAbbr(attrs.get((None,'abbr')))
		axis=attrs.get((None,'axis'))
		if axis is not None:
			tableCell.SetAxis(split(axis,','))
		span=attrs.get((None,'rowspan'))
		if span is not None:
			tableCell.SetRowSpan(ParseInteger(span))
		span=attrs.get((None,'colspan'))
		if span is not None:
			tableCell.SetColSpan(ParseInteger(span))
		self.StartBodyElement(tableCell,attrs)
	
	def StartTableDataCell(self,ns,localName,attrs):
		if self.bodyElement:
			cell=TableDataCell(self.bodyElement)
			self.StartTableCell(cell,attrs)
								
	def StartTableHeadCell(self,ns,localName,attrs):
		if self.bodyElement:
			cell=TableHeadCell(self.bodyElement)
			self.StartTableCell(cell,attrs)
								
	def StartValue(self,ns,localName,attrs):
		if self.valueCardinality==Cardinality.Record:
			self.valueBaseType=ParseBaseType(attrs.get((None,'baseType')))
			self.valueFieldIdentifier=attrs.get((None,'fieldIdentifier'))
		self.data=[]
	
	def EndValue(self,ns,localName):
		value=ParseValue(self.valueBaseType,join(self.data,''))
		if self.valueCardinality==Cardinality.Record:
			self.value[self.valueFieldIdentifier]=(self.valueBaseType,value)
		elif self.valueCardinality in (Cardinality.Multiple,Cardinality.Ordered):
			self.value.append(value)
		elif self.value is None:
			self.value=value
		else:
			raise IMSQTIError("multiple values given where single cardinality expected")
		
	def StartVariable(self,ns,localName,attrs):
		if isinstance(self.cObject,ExpressionContainer):
			self.cObject.AddExpression(VariableOperator(self.item,attrs.get((None,'identifier'))))
		else:
			raise IMSQTIError("<variable> not allowed here")
			
	# This dictionary contains all XHTML elements derived from BodyElement
	xhtmlClasses={
		# Text Elements
		'abbr':Abbreviation,
		'acronym':Acronym,
		'address':Address,
		'blockquote':Blockquote,
		'br':LineBreak,
		'cite':Citation,
		'code':CodeFragment,
		'dfn':Definition,
		'div':Div,
		'em':Emphasis,
		'h1':Heading1,
		'h2':Heading2,
		'h3':Heading3,
		'h4':Heading4,
		'h5':Heading5,
		'h6':Heading6,
		'kbd':KeyboardInput,
		'p':Paragraph,
		'pre':PreformattedText,
		'q':Quotation,
		'samp':SampleOutput,
		'span':Span,
		'strong':StrongEmphasis,
		'var':ProgramVariable,
		# List Elements
		'dl':DefinitionList,
		'dt':DefinitionTerm,
		'dd':DefinitionItem,
		'ol':OrderedList,
		'ul':UnorderedList,
		'li':ListItem,
		# object elements
		'object':Object,
		# presentation elements
		'b':Bold,
		'big':Big,
		'hr':HorizontalRule,
		'i':Italic,
		'small':Small,
		'sub':Subscript,
		'sup':Superscript,
		'tt':Teletype,
		# table elements,
		'caption':Caption,
		'col':Column,
		'colgroup':ColumnGroup,
		'table':Table,
		'tbody':TableBody,
		'td':TableDataCell,
		'tfoot':TableFoot,
		'th':TableHeadCell,
		'thead':TableHead,
		'tr':TableRow,
		# image element
		'img':Image,
		# hypertext element
		'a':HypertextLink
		}

	# This dictionary contains all operator elements that contain sub-expressions
	operatorClasses={
		'and':AndOperator,
		'anyN':AnyNOperator,
		'contains':ContainsOperator,
		'delete':DeleteOperator,
		'fieldValue':FieldValueOperator,
		'index':IndexOperator,
		'isNull':IsNullOperator,
		'match':MatchOperator,
		'member':MemberOperator,
		'multiple':MultipleOperator,
		'not':NotOperator,
		'null':NullOperator,
		'or':OrOperator,
		'ordered':OrderedOperator,
		'random':RandomOperator,
		'stringMatch':StringMatchOperator,
		'substring':SubstringOperator
		}
								
	startMethods={
		'a':StartHypertextLink,
		'anyN':StartAnyNOperator,
		'baseValue':StartBaseValue,
		'blockquote':StartBlockquote,
		'choiceInteraction':StartChoiceInteraction,
		'correct':StartCorrectOperator,
		'correctResponse':StartCorrectResponse,
		'default':StartDefaultOperator,
		'defaultValue':StartDefaultValue,
		'exitResponse':StartExitResponse,
		'extendedTextInteraction':StartExtendedTextInteraction,
		'fieldValue':StartFieldValue,
		'index':StartIndex,
		'img':StartImage,
		'itemBody':StartItemBody,
		'mapEntry':StartMapEntry,
		'mapping':StartMapping,
		'mapResponse':StartMapResponse,
		'object':StartObject,
		'outcomeDeclaration':StartOutcomeDeclaration,
		'orderInteraction':StartOrderInteraction,
		'param':StartParam,
		'prompt':StartPrompt,
		'q':StartQuotation,
		'responseCondition':StartResponseCondition,
		'responseDeclaration':StartResponseDeclaration,
		'responseElse':StartResponseElse,
		'responseElseIf':StartResponseElseIf,
		'responseIf':StartResponseIf,
		'responseProcessing':StartResponseProcessing,
		'setOutcomeValue':StartSetOutcomeValue,
		'simpleChoice':StartSimpleChoice,
		'stringMatch':StartStringMatchOperator,
		'stylesheet':StartStylesheet,
		'substring':StartSubstring,
		'table':StartTable,
		'td':StartTableDataCell,
		'th':StartTableHeadCell,
		'value':StartValue,
		'variable':StartVariable
		}
	
	endMethods={
		'baseValue':EndBaseValue,
		'choiceInteraction':EndBodyElement,
		'correctResponse':EndCorrectResponse,
		'defaultValue':EndDefaultValue,
		'extendedTextInteraction':EndBodyElement,
		'itemBody':EndBodyElement,
		'mapping':EndMapping,
		'outcomeDeclaration':EndOutcomeDeclaration,
		'orderInteraction':EndBodyElement,
		'prompt':EndBodyElement,
		'responseCondition':EndResponseCondition,
		'responseDeclaration':EndResponseDeclaration,
		'responseElse':EndResponseConditionPart,
		'responseElseIf':EndResponseConditionPart,
		'responseIf':EndResponseConditionPart,
		'responseProcessing':EndResponseProcessing,
		'setOutcomeValue':EndSetOutcomeValue,
		'simpleChoice':EndBodyElement,
		'value':EndValue
		}

