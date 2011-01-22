from xml.sax import make_parser, handler
from string import join, split

import sys, os

from common import *
from PyAssess.w3c.xml import CheckName
from PyAssess.w3c.xmlschema import ParseBoolean, ParseFloat, ParseInteger
from PyAssess.w3c.xmlnamespaces import XMLNamespace
from PyAssess.ietf.rfc2396 import URIReference

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
		
	def SetIdentifier(self,identifier):
		if type(identifier) in StringTypes:
			self.identifer=identifier
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
		
def ParseQTIInteger(valueData):
	value=ParseInteger(valueData)
	if value>2147483647L or value<-2147483648:
		raise ValueError("%s exceeds maximum integer size defined by QTI"%valueData)
	return value

def ParseValue(baseType,valueData):
	if baseType==BaseType.Identifier:
		return ParseIdentifier(valueData)
	elif baseType==BaseType.Boolean:
		return ParseBoolean(valueData)
	elif baseType==BaseType.Integer:
		return ParseQTIInteger(valueData)
	elif baseType==BaseType.Float:
		return ParseFloat(valueData)
	elif baseType==BaseType.String:
		return ParseString(valueData)
	elif baseType==BaseType.Point:
		return ParsePoint(valueData)
	elif baseType==BaseType.Pair:
		return ParsePair(valueData)
	elif baseType==BaseType.DirectedPair:
		return ParsePair(valueData)
	elif baseType==BaseType.Duration:
		return ParseDuration(valueData)
	elif baseType==BaseType.File:
		return ParseFile(valueData)
	elif baseType==BaseType.URI:
		return ParseURI(valueData)
	else:
		raise ValueError




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
		# By default, this is an error
		raise IMSQTIError("Bad child for %s: %s"%(self.xmlName,child.xmlName))

	def PreserveSpace(self):
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
	
class SimpleBlock(BlockStatic,BodyElement,FlowStatic):
	def AddChild(self,child):
		if isinstance(child,Block):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)
	
class AtomicInline(BodyElement,FlowStatic,InlineStatic):
	pass

class AtomicBlock(BlockStatic,BodyElement,FlowStatic):
	def AddChild(self,child):
		if isinstance(child,Inline):
			self.children.append(child)
		else:
			BodyElement.AddChild(self,child)

class TextRun(FlowStatic,InlineStatic):
	xmlName="#PCDATA"

	def __init__(self,parent,text):
		self.parent=parent
		if isinstance(parent,BodyElement):
			parent.AddChild(self)
		else:
			raise TypeError("TextRun not in bodyElement")
		self.text=text

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
	pass

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

	def Render(self,view):
		view.RenderChoiceInteraction(self)
	
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
		self.variableDeclaration=None
		self.responseDeclaration=None
		self.outcomeDeclaration=None
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
				method=self.startMethods.get(localName)
				if method:
					method(self,ns,localName,attrs)
				elif self.xhtmlClasses.has_key(localName):
					if self.bodyElement:
						newBodyElement=self.xhtmlClasses[localName](self.bodyElement)
						self.StartBodyElement(newBodyElement,attrs)
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

	def characters(self,content):
		self.data.append(content)
	
	def StartSkipped(self,ns,localName,attrs):
		self.skipping+=1
		print "Skipping element <%s>"%localName
	
	def StartBodyElement(self,newBodyElement,attrs):
		if self.bodyElement:
			if self.data:
				self.ProcessTextRun()
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
			self.ProcessTextRun()
		self.bodyElement=self.bodyElement.parent
	
	def ProcessTextRun(self):
		data=join(self.data,'')
		self.data=[]
		if data.strip():
			# non trivial data gets added to bodyElement
			TextRun(self.bodyElement,data)
		elif self.bodyElement.PreserveSpace():
			TextRun(self.bodyElement,data)
	
	def StartHypertextLink(self,ns,localName,attrs):
		if self.bodyElement:
			link=HypertextLink(self.bodyElement,attrs.get((None,'href')))
			link.SetType(attrs.get((None,'type')))
			self.StartBodyElement(link,attrs)
			
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
				
	def StartCorrectResponse(self,ns,localName,attrs):
		if self.responseDeclaration:
			self.responseDeclaration.SetCorrectInterpretation(attrs.get((None,'interpretation')))
			self.PrepareValue()
		else:
			raise IMSQTIError("<correctResponse> not inside <responseDeclaration>")
	
	def EndCorrectResponse(self,ns,localName):
		if self.value is None:
			raise IMSQTIError("expected <value>")
		self.responseDeclaration.SetCorrectValue(self.value)
	
	def StartDefaultValue(self,ns,localName,attrs):
		if self.variableDeclaration:
			self.variableDeclaration.SetDefaultInterpretation(attrs.get((None,'interpretation')))
			self.PrepareValue()
		else:
			raise IMSQTIError("<defaultValue> not in variable declaration")
		
	def EndDefaultValue(self,ns,localName):
		if self.value is None:
			raise IMSQTIError("expected <value>")
		self.variableDeclaration.SetDefaultValue(self.value)
	
	def StartImage(self,ns,localname,attrs):
		image=Image(self.bodyElement,attrs.get((None,'src')),attrs.get((None,'alt')))
		image.SetLongDesc(attrs.get((None,'longdesc')))
		image.SetHeight(attrs.get((None,'height')))
		image.SetWidth(attrs.get((None,'width')))
		self.StartBodyElement(image,attrs)		
		
	def StartItemBody(self,ns,localname,attrs):
		itemBody=self.item.CreateBody()
		self.StartBodyElement(itemBody,attrs)
		
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
		self.outcomeDeclaration=OutcomeDeclaration(attrs.get((None,'identifier')),
			ParseCardinality(attrs.get((None,'cardinality'))),
			ParseBaseType(attrs.get((None,'baseType'))))
		self.outcomeDeclaration.SetInterpretation(attrs.get((None,'interpretation')))
		self.outcomeDeclaration.SetLongInterpretation(attrs.get((None,'longInterpretation')))
		interpretation=attrs.get((None,'interpretation'))
		if interpretation is not None:
			self.outcomeDeclaration.SetNormalMaximum(ParseFloat(interpretation))
		self.valueCardinality=self.outcomeDeclaration.cardinality
		self.valueBaseType=self.outcomeDeclaration.baseType
		self.variableDeclaration=self.outcomeDeclaration
		
	def EndOutcomeDeclaration(self,ns,localName):
		self.outcomeDeclaration=None
		self.valueCardinality=None
		self.valueBaseType=None
		self.variableDeclaration=None			
	
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
				
	def StartResponseDeclaration(self,ns,localName,attrs):
		self.responseDeclaration=ResponseDeclaration(attrs.get((None,'identifier')),
			ParseCardinality(attrs.get((None,'cardinality'))),
			ParseBaseType(attrs.get((None,'baseType'))))
		# Use these to provide a context for any contained values
		self.valueCardinality=self.responseDeclaration.cardinality
		self.valueBaseType=self.responseDeclaration.baseType
		self.variableDeclaration=self.responseDeclaration
	
	def EndResponseDeclaration(self,ns,localName):
		self.item.DeclareVariable(self.responseDeclaration)
		self.responseDeclaration=None
		self.valueCardinality=None
		self.valueBaseType=None
		self.variableDeclaration=None			
	
	def StartResponseProcessing(self,ns,localName,attrs):
		responseProcessing=self.item.CreateResponseProcessing()
		responseProcessing.SetTemplate(attrs.get((None,'template')))
		responseProcessing.SetTemplateLocation(attrs.get((None,'templateLocation')))
		
	def StartSimpleChoice(self,ns,localName,attrs):
		if self.bodyElement:
			choice=SimpleChoice(self.bodyElement,attrs.get((None,'identifier')))
			fixed=attrs.get((None,'fixed'))
			if fixed is not None:
				choice.SetFixed(ParseBoolean(fixed))
			self.StartBodyElement(choice,attrs)
	
	def StartStylesheet(self,ns,localName,attrs):
		stylesheet=Stylesheet(attrs.get((None,'href')),attrs.get((None,'type')))
		stylesheet.SetMedia(attrs.get((None,'media')))
		stylesheet.SetTitle(attrs.get((None,'title')))
		self.item.AddStylesheet(stylesheet)
		
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
							
	startMethods={
		'a':StartHypertextLink,
		'blockquote':StartBlockquote,
		'choiceInteraction':StartChoiceInteraction,
		'correctResponse':StartCorrectResponse,
		'defaultValue':StartDefaultValue,
		'img':StartImage,
		'itemBody':StartItemBody,
		'object':StartObject,
		'outcomeDeclaration':StartOutcomeDeclaration,
		'orderInteraction':StartOrderInteraction,
		'param':StartParam,
		'prompt':StartPrompt,
		'q':StartQuotation,
		'responseDeclaration':StartResponseDeclaration,
		'responseProcessing':StartResponseProcessing,
		'simpleChoice':StartSimpleChoice,
		'stylesheet':StartStylesheet,
		'table':StartTable,
		'td':StartTableDataCell,
		'th':StartTableHeadCell,
		'value':StartValue
		}
	
	endMethods={
		'choiceInteraction':EndBodyElement,
		'correctResponse':EndCorrectResponse,
		'defaultValue':EndDefaultValue,
		'itemBody':EndBodyElement,
		'outcomeDeclaration':EndOutcomeDeclaration,
		'orderInteraction':EndBodyElement,
		'prompt':EndBodyElement,
		'responseDeclaration':EndResponseDeclaration,
		'simpleChoice':EndBodyElement,
		'value':EndValue
		}

