#! /usr/bin/env python

import pyslet.xml20081126 as xml
import pyslet.xmlnames20091208 as xmlns

import htmlentitydefs
import string
from types import *

HTML40_PUBLICID="-//W3C//DTD HTML 4.01//EN"
XHTML_NAMESPACE="http://www.w3.org/1999/xhtml"

class XHTMLError(Exception): pass
class XHTMLValidityError(XHTMLError): pass

class XHTMLElement(xmlns.XMLNSElement):
	def __init__(self,parent):
		xmlns.XMLNSElement.__init__(self,parent)
		self.id=None
		self.styleClass=None
		self.title=None
	
	def GetAttributes(self):
		attrs=xmlns.XMLNSElement.GetAttributes(self)
		if self.id: attrs['id']=self.id
		if self.styleClass: attrs['class']=self.styleClass
		if self.title: attrs['title']=self.title
		return attrs
		
	def Set_id(self,value):
		self.id=value
		
	def Set_class(self,value):
		self.styleClass=value
		
	def Set_title(self,value):
		self.title=value
		
	def RenderText(self):
		output=[]
		children=self.GetChildren()
		for child in children:
			if type(child) in StringTypes:
				output.append(child)
			else:
				output.append(child.RenderText())
		return string.join(output,'')
		

class XHTMLFlowMixin:
	# <!ENTITY % flow "%block; | %inline;">
	pass

class XHTMLBlockMixin(XHTMLFlowMixin): pass
	# <!ENTITY % block "P | %heading; | %list; | %preformatted; | DL | DIV |
	#		NOSCRIPT | BLOCKQUOTE | FORM | HR | TABLE | FIELDSET | ADDRESS">

class XHTMLInlineMixin(XHTMLFlowMixin): pass
	# <!ENTITY % inline "#PCDATA | %fontstyle; | %phrase; | %special; | %formctrl;">

class XHTMLInlineContainer(XHTMLElement):
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,XHTMLInlineMixin):
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

	
class XHTMLFlowContainer(XHTMLElement):
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,XHTMLFlowMixin):
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			print self
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class XHTMLSpecialMixin(XHTMLInlineMixin):
	# <!ENTITY % special "A | IMG | OBJECT | BR | SCRIPT | MAP | Q | SUB | SUP | SPAN | BDO">
	pass

class XHTMLList(XHTMLBlockMixin,XHTMLElement):
	# <!ENTITY % list "UL | OL">

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,XHTMLLI):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
# Text Elements

class XHTMLPhrase(XHTMLInlineMixin,XHTMLInlineContainer):
	# <!ENTITY % phrase "EM | STRONG | DFN | CODE | SAMP | KBD | VAR | CITE | ABBR | ACRONYM" >
	# <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
	pass

class XHTMLAbbr(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'abbr')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLAcronym(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'acronym')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLAddress(XHTMLBlockMixin,XHTMLInlineContainer):
	XMLNAME=(XHTML_NAMESPACE,'address')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLBlockquote(XHTMLBlockMixin,XHTMLElement):
	# <!ELEMENT BLOCKQUOTE - - (%block;|SCRIPT)+ -- long quotation -->
	XMLNAME=(XHTML_NAMESPACE,'block')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,XHTMLBlockMixin) or issubclass(childClass,XHTMLScript):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class XHTMLBr(XHTMLSpecialMixin,XHTMLElement):
	# <!ELEMENT BR - O EMPTY                 -- forced line break -->
	XMLNAME=(XHTML_NAMESPACE,'br')
	XMLCONTENT=xmlns.XMLEmpty

class XHTMLCite(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'cite')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLCode(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'code')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLDfn(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'dfn')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLDiv(XHTMLBlockMixin,XHTMLFlowContainer):
	# <!ELEMENT DIV - - (%flow;)*            -- generic language/style container -->
	XMLNAME=(XHTML_NAMESPACE,'div')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLEm(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'em')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLHeading(XHTMLBlockMixin,XHTMLInlineContainer):
	# <!ENTITY % heading "H1|H2|H3|H4|H5|H6">
	pass

class XHTMLH1(XHTMLHeading):
	XMLNAME=(XHTML_NAMESPACE,'h1')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLH2(XHTMLHeading):
	XMLNAME=(XHTML_NAMESPACE,'h2')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLH3(XHTMLHeading):
	XMLNAME=(XHTML_NAMESPACE,'h3')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLH4(XHTMLHeading):
	XMLNAME=(XHTML_NAMESPACE,'h4')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLH5(XHTMLHeading):
	XMLNAME=(XHTML_NAMESPACE,'h5')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLH6(XHTMLHeading):
	XMLNAME=(XHTML_NAMESPACE,'h6')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLKbd(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'kbd')
	XMLCONTENT=xmlns.XMLMixedContent
	
class XHTMLP(XHTMLBlockMixin,XHTMLInlineContainer):
	# <!ELEMENT P - O (%inline;)*            -- paragraph -->
	XMLNAME=(XHTML_NAMESPACE,'p')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLPre(XHTMLBlockMixin,XHTMLInlineContainer):
	# <!ENTITY % pre.exclusion "IMG|OBJECT|BIG|SMALL|SUB|SUP">
	# <!ELEMENT PRE - - (%inline;)* -(%pre.exclusion;) -- preformatted text -->
	XMLNAME=(XHTML_NAMESPACE,'pre')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLQ(XHTMLSpecialMixin,XHTMLInlineContainer):
	# <!ELEMENT Q - - (%inline;)*            -- short inline quotation -->
	XMLNAME=(XHTML_NAMESPACE,'q')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLSamp(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'samp')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLSpan(XHTMLSpecialMixin,XHTMLInlineContainer):
	# <!ELEMENT SPAN - - (%inline;)*         -- generic language/style container -->
	XMLNAME=(XHTML_NAMESPACE,'span')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLStrong(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'strong')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLVar(XHTMLPhrase):
	XMLNAME=(XHTML_NAMESPACE,'var')
	XMLCONTENT=xmlns.XMLMixedContent

# List Elements

class XHTMLDL(XHTMLBlockMixin,XHTMLElement):
	# <!ELEMENT DL - - (DT|DD)+              -- definition list -->
	XMLNAME=(XHTML_NAMESPACE,'dl')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(XHTMLDT,XHTMLDD)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

class XHTMLDT(XHTMLInlineContainer):
	# <!ELEMENT DT - O (%inline;)*           -- definition term -->
	XMLNAME=(XHTML_NAMESPACE,'dt')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLDD(XHTMLFlowContainer):
	# <!ELEMENT DD - O (%flow;)*             -- definition description -->
	XMLNAME=(XHTML_NAMESPACE,'dd')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLOL(XHTMLList):
	# <!ELEMENT OL - - (LI)+                 -- ordered list -->
	XMLNAME=(XHTML_NAMESPACE,'ol')
	XMLCONTENT=xmlns.XMLElementContent
	
class XHTMLUL(XHTMLList):
	# <!ELEMENT UL - - (LI)+                 -- ordered list -->
	XMLNAME=(XHTML_NAMESPACE,'ul')
	XMLCONTENT=xmlns.XMLElementContent
	
class XHTMLLI(XHTMLFlowContainer):
	# <!ELEMENT LI - O (%flow;)*             -- list item -->
	XMLNAME=(XHTML_NAMESPACE,'li')
	XMLCONTENT=xmlns.XMLElementContent
	
# Object Elements

class XHTMLObject(XHTMLSpecialMixin,XHTMLElement):
	# <!ELEMENT OBJECT - - (PARAM | %flow;)*
	XMLNAME=(XHTML_NAMESPACE,'object')
	XMLCONTENT=xmlns.XMLMixedContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(XHTMLFlowMixin,XHTMLParam)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class XHTMLParam(XHTMLElement):
	# <!ELEMENT PARAM - O EMPTY              -- named property value -->
	XMLNAME=(XHTML_NAMESPACE,'param')
	XMLCONTENT=xmlns.XMLEmpty
	
# Presentation Elements

class XHTMLFontStyle(XHTMLInlineMixin,XHTMLInlineContainer):
	# <!ENTITY % fontstyle "TT | I | B | BIG | SMALL">
	# <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
	pass

class XHTMLB(XHTMLFontStyle):
	XMLNAME=(XHTML_NAMESPACE,'b')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLBig(XHTMLFontStyle):
	XMLNAME=(XHTML_NAMESPACE,'big')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLHR(XHTMLBlockMixin,XHTMLElement):
	# <!ELEMENT HR - O EMPTY -- horizontal rule -->
	XMLNAME=(XHTML_NAMESPACE,'hr')
	XMLCONTENT=xmlns.XMLEmpty

class XHTMLI(XHTMLFontStyle):
	XMLNAME=(XHTML_NAMESPACE,'i')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLSmall(XHTMLFontStyle):
	XMLNAME=(XHTML_NAMESPACE,'small')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLSub(XHTMLSpecialMixin,XHTMLInlineContainer):
	# <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
	XMLNAME=(XHTML_NAMESPACE,'sub')
	XMLCONTENT=xmlns.XMLMixedContent
	
class XHTMLSup(XHTMLSpecialMixin,XHTMLInlineContainer):
	# <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
	XMLNAME=(XHTML_NAMESPACE,'sup')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLTT(XHTMLFontStyle):
	XMLNAME=(XHTML_NAMESPACE,'tt')
	XMLCONTENT=xmlns.XMLMixedContent

# Table Elements

class XHTMLTable(XHTMLBlockMixin,XHTMLElement):
	# <!ELEMENT TABLE - - (CAPTION?, (COL*|COLGROUP*), THEAD?, TFOOT?, TBODY+)>
	XMLNAME=(XHTML_NAMESPACE,'table')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(XHTMLCaption,XHTMLCol,XHTMLColGroup,XHTMLTHead,XHTMLTFoot,XHTMLTBody)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif issubclass(childClass,XHTMLTR):
			# TBODY can have it's start tag omitted
			tbody=self.ChildElement(XHTMLTBody)
			return tbody.ChildElement(childClass)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))

class XHTMLCaption(XHTMLInlineContainer):
	# <!ELEMENT CAPTION  - - (%inline;)*     -- table caption -->
	XMLNAME=(XHTML_NAMESPACE,'caption')
	XMLCONTENT=xmlns.XMLMixedContent

class XHTMLTRContainer(XHTMLElement):
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,XHTMLTR):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
		
class XHTMLTHead(XHTMLTRContainer):
	# <!ELEMENT THEAD    - O (TR)+           -- table header -->
	XMLNAME=(XHTML_NAMESPACE,'thead')
	XMLCONTENT=xmlns.XMLElementContent

class XHTMLTFoot(XHTMLTRContainer):
	# <!ELEMENT TFOOT    - O (TR)+           -- table footer -->
	XMLNAME=(XHTML_NAMESPACE,'tfoot')
	XMLCONTENT=xmlns.XMLElementContent

class XHTMLTBody(XHTMLTRContainer):
	# <!ELEMENT TBODY    O O (TR)+           -- table body -->
	XMLNAME=(XHTML_NAMESPACE,'tbody')
	XMLCONTENT=xmlns.XMLElementContent

class XHTMLColGroup(XHTMLElement):
	# <!ELEMENT COLGROUP - O (COL)*          -- table column group -->
	XMLNAME=(XHTML_NAMESPACE,'colgroup')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,XHTMLCol):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class XHTMLCol(XHTMLBlockMixin,XHTMLElement):
	# <!ELEMENT COL      - O EMPTY           -- table column -->
	XMLNAME=(XHTML_NAMESPACE,'col')
	XMLCONTENT=xmlns.XMLEmpty

class XHTMLTR(XHTMLElement):
	# <!ELEMENT TR       - O (TH|TD)+        -- table row -->
	XMLNAME=(XHTML_NAMESPACE,'tr')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(XHTMLTH,XHTMLTD)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class XHTMLTH(XHTMLFlowContainer):
	# <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
	XMLNAME=(XHTML_NAMESPACE,'th')
	XMLCONTENT=xmlns.XMLMixedContent
	
class XHTMLTD(XHTMLFlowContainer):
	# <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
	XMLNAME=(XHTML_NAMESPACE,'td')
	XMLCONTENT=xmlns.XMLMixedContent
	
# Image Element

class XHTMLImg(XHTMLSpecialMixin,XHTMLElement):
	# <!ELEMENT IMG - O EMPTY                -- Embedded image -->
	XMLNAME=(XHTML_NAMESPACE,'img')
	XMLCONTENT=xmlns.XMLEmpty

# Hypertext Element

class XHTMLA(XHTMLSpecialMixin,XHTMLInlineContainer):
	# <!ELEMENT A - - (%inline;)* -(A)       -- anchor -->
	XMLNAME=(XHTML_NAMESPACE,'a')
	XMLCONTENT=xmlns.XMLMixedContent


class HTMLParser(xml.XMLParser):
	def __init__(self,entity=None):
		xml.XMLParser.__init__(self,entity)
	
	def LookupEntity(self,name):
		codepoint=htmlentitydefs.name2codepoint.get(name,None)
		if codepoint is None:
			return ''
		else:
			return unichr(codepoint)
			
	def ParseHTMLFragment(self):
		fragment=[]
		element=None
		eData=[]
		while self.theChar is not None:
			data=self.ParseCharData()
			if data:
				if element:
					element.AddData(data)
				else:
					fragment.append(data)
				data=None
			name=None
			if self.theChar=='<':
				self.entity.StartLookahead()
				self.NextChar()
				if self.theChar=='!':
					self.NextChar()
					if self.theChar=='-':
						self.Rewind()
						self.ParseComment()
					else:
						self.Rewind()
						data=self.ParseCDATA()
				elif self.theChar=='?':
					self.Rewind()
					self.ParsePI()
				else:
					self.Rewind()
					name,attrs,tagType=self.ParseTag()
					if tagType!=xml.XMLParser.ETag:
						eClass=XHTMLDocument.classMap.get((XHTML_NAMESPACE,name.lower()),None)
						if eClass is None:
							if element is not None and issubclass(element.__class__,(XHTMLInlineContainer,XHTMLFlowContainer)):
								# try a span with a class attribute
								eClass=XHTMLSpan
							else:
								eClass=XHTMLDiv
							classValue=name
						else:
							classValue=None
						newElement=None
						while element is not None:
							try:
								newElement=element.ChildElement(eClass)
								break
							except XHTMLValidityError:
								# we can't go in here
								element=element.parent
								continue
						if newElement is None:		
							newElement=eClass(None)
							fragment.append(newElement)
						if classValue is None:
							newElement.SetXMLName((XHTML_NAMESPACE,name))
						else:
							newElement.SetAttribute('class',name)
						for attr in attrs.keys():
							newElement.SetAttribute(attr.lower(),attrs[attr])						
						if tagType!=xml.XMLParser.EmptyElemTag and eClass.XMLCONTENT!=xmlns.XMLEmpty:
							# A non-empty element becomes the current element
							element=newElement
					elif tagType==xml.XMLParser.ETag:
						# we need to close this element
						newElement=element
						while newElement is not None:
							if newElement.xmlname==name.lower():
								# close this tag
								element=newElement.parent
								break
							newElement=newElement.parent
						# if there is no match we ignore the closing tag	
			elif self.theChar=='&':
				data=self.ParseReference()
			if data:
				if element:
					element.AddData(data)
				else:
					fragment.append(data)
				data=None
		return fragment


class XHTMLDocument(xmlns.XMLNSDocument):
	classMap={}


xmlns.MapClassElements(XHTMLDocument.classMap,globals())
