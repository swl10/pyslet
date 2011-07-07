#! /usr/bin/env python

import pyslet.xml20081126 as xml
import pyslet.xmlnames20091208 as xmlns
from pyslet.rfc2396 import URIFactory, EncodeUnicodeURI, FileURL

import htmlentitydefs
import string
from types import *
import os.path, shutil

HTML40_PUBLICID="-//W3C//DTD HTML 4.01//EN"
XHTML_NAMESPACE="http://www.w3.org/1999/xhtml"

class XHTMLError(Exception): pass
class XHTMLValidityError(XHTMLError): pass


class LengthType:
	"""Represents the HTML Length::
	
	<!ENTITY % Length "CDATA" -- nn for pixels or nn% for percentage length -->
	"""
	Pixel=0
	"""data constant used to indicate pixel co-ordinates"""
	Percentage=1
	"""data constant used to indicate relative (percentage) co-ordinates"""

	def __init__(self,value,valueType=None):
		"""	* value can be either an integer value or another LengthType instance.
	* if value is an integer then valueType can be used to select Pixel or Percentage
	
	By default values are assumed to be Pixel lengths."""
		if isinstance(value,LengthType):
			self.type=value.type
			"""type is one of the the LengthType constants: Pixel or Percentage"""
			self.value=value.value
			"""value is the integer value of the length"""
		else:
			self.type=LengthType.Pixel if valueType is None else valueType 
			self.value=value

	def __str__(self):
		"""Formats the length as a string of form nn for pixels or nn% for percentage."""
		if self.type==LengthType.Percentage:
			return str(self.value)+'%'
		else:
			return str(self.value)
	
	def __unicode__(self):
		"""Formats the length as a unicode string of form nn for pixels or nn% for percentage."""
		if self.type==LengthType.Percentage:
			return unicode(self.value)+'%'
		else:
			return unicode(self.value)

		
def DecodeLength(strValue):
	"""Parses a length from a string returning an instance of LengthType"""
	valueType=None
	value=None
	try:
		strValue=strValue.strip()
		v=[]
		for c in strValue:
			if valueType is None and c.isdigit():
				v.append(c)
			elif c==u"%":
				valueType=LengthType.Percentage
				break
			else:
				valueType=LengthType.Pixel
		if valueType is None:
			valueType=LengthType.Pixel
		value=int(string.join(v,''))
		if value<0:
			raise ValueError
		return LengthType(value,valueType)
	except ValueError:
		raise XHTMLValidityError("Failed to read length from %s"%strValue)

def EncodeLength(length):
	"""Encodes a length value as a unicode string from an instance of LengthType."""
	if length is None:
		return None
	else:
		return unicode(length)


class Coords:
	"""Represents HTML Coords values::
	
	<!ENTITY % Coords "CDATA" -- comma-separated list of lengths -->
	"""
	def __init__(self,values=None):
		"""Instances can be initialized from an existing list of values."""
		if values:
			self.values=values
			"""A list of LengthType values."""
		else:
			self.values=[]

	def __unicode__(self):
		"""Formats the Coords as comma-separated unicode string of Length values."""
		return string.join(map(lambda x:unicode(x),self.values),u',')
	
	def __str__(self):
		"""Formats the Coords as a comma-separated string of Length values."""
		return string.join(map(lambda x:str(x),self.values),',')
		
def DecodeCoords(value):
	"""Decodes coords from an attribute value string into a Coords instance."""
	return Coords(map(lambda x:DecodeLength(x.strip()),value.split(',')))

def EncodeCoords(coords):
	"""Encodes a Coords instance as an attribute value string."""
	return unicode(coords)
			

def DecodeURI(src):
	"""Decodes a URI from src::
	
	<!ENTITY % URI "CDATA"  -- a Uniform Resource Identifier -->
	
	Note that we adopt the algorithm recommended in Appendix B of the specification,
	which involves replacing non-ASCII characters with percent-encoded UTF-sequences.
	
	For more information see :func:`psylet.rfc2396.EncodeUnicodeURI`
	"""
	return URIFactory.URI(EncodeUnicodeURI(src))

def EncodeURI(uri):
	"""Encoding a URI means just converting it into a string.
	
	By definition, a URI will only result in ASCII characters that can be freely converted
	to Unicode by the default encoding.  However, it does mean that this function doesn't
	adhere to the principal of using the ASCII encoding only at the latest possible time."""
	return unicode(str(uri))

	
class XHTMLElement(xmlns.XMLNSElement):
	ID='id'
	XMLATTR_class='styleClass'
	XMLATTR_title='title'
	XMLCONTENT=xmlns.XMLMixedContent
	
	def __init__(self,parent):
		xmlns.XMLNSElement.__init__(self,parent)
		self.styleClass=None
		self.title=None
	
	def AddToCPResource(self,cp,resource,beenThere):
		"""See :py:meth:`pyslet.imsqtiv2p1.QTIElement.AddToCPResource`  """
		for child in self.GetChildren():
			if hasattr(child,'AddToCPResource'):
				child.AddToCPResource(cp,resource,beenThere)
	
	def RenderText(self):
		output=[]
		children=self.GetChildren()
		for child in children:
			if type(child) in StringTypes:
				output.append(child)
			else:
				output.append(child.RenderText())
		return string.join(output,'')
	

class FlowMixin:
	# <!ENTITY % flow "%block; | %inline;">
	pass

class BlockMixin(FlowMixin): pass
	# <!ENTITY % block "P | %heading; | %list; | %preformatted; | DL | DIV |
	#		NOSCRIPT | BLOCKQUOTE | FORM | HR | TABLE | FIELDSET | ADDRESS">

class InlineMixin(FlowMixin): pass
	# <!ENTITY % inline "#PCDATA | %fontstyle; | %phrase; | %special; | %formctrl;">

class InlineContainer(XHTMLElement):
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,InlineMixin):
			return XHTMLElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

	
class FlowContainer(XHTMLElement):
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,FlowMixin):
			return XHTMLElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			# This child cannot go in here
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

	def PrettyPrint(self):
		"""Deteremins if this flow-container should be pretty printed.
		
		We suppress pretty printing if we have any non-trivial data children or
		if we have any inline child elements."""
		children=self.GetChildren()
		for child in children:
			if type(child) in StringTypes:
				for c in child:
					if not xml.IsS(c):
						return False
			#elif isinstance(child,InlineMixin):
			#	return False
		return True
	
class SpecialMixin(InlineMixin):
	"""..	::
	
	Strict:	<!ENTITY % special "A | IMG | OBJECT | BR | SCRIPT | MAP | Q | SUB | SUP | SPAN | BDO">
	Loose:	<!ENTITY % special "A | IMG | APPLET | OBJECT | FONT | BASEFONT | BR | SCRIPT | MAP
				| Q | SUB | SUP | SPAN | BDO | IFRAME">
	"""
	pass

class FormCtrlMixin(InlineMixin):
	# <!ENTITY % formctrl "INPUT | SELECT | TEXTAREA | LABEL | BUTTON">
	pass

class Ins(FlowContainer):
	"""Represents the INS element::
	
	<!-- INS/DEL are handled by inclusion on BODY -->
	<!ELEMENT (INS|DEL) - - (%flow;)*      -- inserted text, deleted text -->
	<!ATTLIST (INS|DEL)
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  cite        %URI;          #IMPLIED  -- info on reason for change --
	  datetime    %Datetime;     #IMPLIED  -- date and time of change --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'ins')
	XMLCONTENT=xmlns.XMLMixedContent


class Del(FlowContainer):
	"""Represents the DEL element::
	
	<!-- INS/DEL are handled by inclusion on BODY -->
	<!ELEMENT (INS|DEL) - - (%flow;)*      -- inserted text, deleted text -->
	<!ATTLIST (INS|DEL)
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  cite        %URI;          #IMPLIED  -- info on reason for change --
	  datetime    %Datetime;     #IMPLIED  -- date and time of change --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'del')
	XMLCONTENT=xmlns.XMLMixedContent
	

class List(BlockMixin,XHTMLElement):
	# <!ENTITY % list "UL | OL">

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,LI):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif issubclass(childClass,FlowMixin):
			child=xmlns.XMLNSElement.ChildElement(self,LI)
			return child.ChildElement(childClass)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
# Text Elements

class Phrase(InlineMixin,InlineContainer):
	# <!ENTITY % phrase "EM | STRONG | DFN | CODE | SAMP | KBD | VAR | CITE | ABBR | ACRONYM" >
	# <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
	pass

class Abbr(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'abbr')
	XMLCONTENT=xmlns.XMLMixedContent

class Acronym(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'acronym')
	XMLCONTENT=xmlns.XMLMixedContent

class Address(BlockMixin,InlineContainer):
	XMLNAME=(XHTML_NAMESPACE,'address')
	XMLCONTENT=xmlns.XMLMixedContent

class Blockquote(BlockMixin,XHTMLElement):
	# <!ELEMENT BLOCKQUOTE - - (%block;|SCRIPT)+ -- long quotation -->
	XMLNAME=(XHTML_NAMESPACE,'blockquote')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,BlockMixin) or issubclass(childClass,Script):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

class Font(SpecialMixin,InlineContainer):
	"""Font element::
	
	<!ELEMENT FONT - - (%inline;)*         -- local change to font -->
	<!ATTLIST FONT
	  %coreattrs;                          -- id, class, style, title --
	  %i18n;		               -- lang, dir --
	  size        CDATA          #IMPLIED  -- [+|-]nn e.g. size="+1", size="4" --
	  color       %Color;        #IMPLIED  -- text color --
	  face        CDATA          #IMPLIED  -- comma-separated list of font names --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'font')
	XMLCONTENT=xmlns.XMLMixedContent
	
class Br(SpecialMixin,XHTMLElement):
	# <!ELEMENT BR - O EMPTY                 -- forced line break -->
	XMLNAME=(XHTML_NAMESPACE,'br')
	XMLCONTENT=xmlns.XMLEmpty

class Cite(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'cite')
	XMLCONTENT=xmlns.XMLMixedContent

class Code(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'code')
	XMLCONTENT=xmlns.XMLMixedContent

class Dfn(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'dfn')
	XMLCONTENT=xmlns.XMLMixedContent

class Div(BlockMixin,FlowContainer):
	# <!ELEMENT DIV - - (%flow;)*            -- generic language/style container -->
	XMLNAME=(XHTML_NAMESPACE,'div')
	XMLCONTENT=xmlns.XMLMixedContent
		
class Em(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'em')
	XMLCONTENT=xmlns.XMLMixedContent

class Heading(BlockMixin,InlineContainer):
	# <!ENTITY % heading "H1|H2|H3|H4|H5|H6">
	pass

class H1(Heading):
	XMLNAME=(XHTML_NAMESPACE,'h1')
	XMLCONTENT=xmlns.XMLMixedContent

class H2(Heading):
	XMLNAME=(XHTML_NAMESPACE,'h2')
	XMLCONTENT=xmlns.XMLMixedContent

class H3(Heading):
	XMLNAME=(XHTML_NAMESPACE,'h3')
	XMLCONTENT=xmlns.XMLMixedContent

class H4(Heading):
	XMLNAME=(XHTML_NAMESPACE,'h4')
	XMLCONTENT=xmlns.XMLMixedContent

class H5(Heading):
	XMLNAME=(XHTML_NAMESPACE,'h5')
	XMLCONTENT=xmlns.XMLMixedContent

class H6(Heading):
	XMLNAME=(XHTML_NAMESPACE,'h6')
	XMLCONTENT=xmlns.XMLMixedContent

class Kbd(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'kbd')
	XMLCONTENT=xmlns.XMLMixedContent
	
class P(BlockMixin,InlineContainer):
	# <!ELEMENT P - O (%inline;)*            -- paragraph -->
	XMLNAME=(XHTML_NAMESPACE,'p')
	XMLCONTENT=xmlns.XMLMixedContent

class Pre(BlockMixin,InlineContainer):
	# <!ENTITY % pre.exclusion "IMG|OBJECT|BIG|SMALL|SUB|SUP">
	# <!ELEMENT PRE - - (%inline;)* -(%pre.exclusion;) -- preformatted text -->
	XMLNAME=(XHTML_NAMESPACE,'pre')
	XMLCONTENT=xmlns.XMLMixedContent

	def PrettyPrint(self):
		return False

class Q(SpecialMixin,InlineContainer):
	# <!ELEMENT Q - - (%inline;)*            -- short inline quotation -->
	XMLNAME=(XHTML_NAMESPACE,'q')
	XMLCONTENT=xmlns.XMLMixedContent

class Samp(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'samp')
	XMLCONTENT=xmlns.XMLMixedContent

class Span(SpecialMixin,InlineContainer):
	# <!ELEMENT SPAN - - (%inline;)*         -- generic language/style container -->
	XMLNAME=(XHTML_NAMESPACE,'span')
	XMLCONTENT=xmlns.XMLMixedContent

class Strong(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'strong')
	XMLCONTENT=xmlns.XMLMixedContent

class Var(Phrase):
	XMLNAME=(XHTML_NAMESPACE,'var')
	XMLCONTENT=xmlns.XMLMixedContent

# List Elements

class DL(BlockMixin,XHTMLElement):
	# <!ELEMENT DL - - (DT|DD)+              -- definition list -->
	XMLNAME=(XHTML_NAMESPACE,'dl')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(DT,DD)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

class DT(InlineContainer):
	# <!ELEMENT DT - O (%inline;)*           -- definition term -->
	XMLNAME=(XHTML_NAMESPACE,'dt')
	XMLCONTENT=xmlns.XMLMixedContent

class DD(FlowContainer):
	# <!ELEMENT DD - O (%flow;)*             -- definition description -->
	XMLNAME=(XHTML_NAMESPACE,'dd')
	XMLCONTENT=xmlns.XMLMixedContent

class OL(List):
	# <!ELEMENT OL - - (LI)+                 -- ordered list -->
	XMLNAME=(XHTML_NAMESPACE,'ol')
	XMLCONTENT=xmlns.XMLElementContent
	
class UL(List):
	# <!ELEMENT UL - - (LI)+                 -- ordered list -->
	XMLNAME=(XHTML_NAMESPACE,'ul')
	XMLCONTENT=xmlns.XMLElementContent
	
class LI(FlowContainer):
	# <!ELEMENT LI - O (%flow;)*             -- list item -->
	XMLNAME=(XHTML_NAMESPACE,'li')
	XMLCONTENT=xmlns.XMLMixedContent


# Form Elements

class Form(BlockMixin,XHTMLElement):
	"""Represents the form element::

	<!ELEMENT FORM - - (%block;|SCRIPT)+ -(FORM) -- interactive form -->
	<!ATTLIST FORM
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  action      %URI;          #REQUIRED -- server-side form handler --
	  method      (GET|POST)     GET       -- HTTP method used to submit the form--
	  enctype     %ContentType;  "application/x-www-form-urlencoded"
	  accept      %ContentTypes; #IMPLIED  -- list of MIME types for file upload --
	  name        CDATA          #IMPLIED  -- name of form for scripting --
	  onsubmit    %Script;       #IMPLIED  -- the form was submitted --
	  onreset     %Script;       #IMPLIED  -- the form was reset --
	  accept-charset %Charsets;  #IMPLIED  -- list of supported charsets --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'form')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(BlockMixin,Script)):
			return XHTMLElement.ChildElement(self,childClass,name)
		elif issubclass(childClass,FlowMixin):
			child=XHTMLElement.ChildElement(self,Div)
			return child.ChildElement(childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		


class Label(FormCtrlMixin,InlineContainer):
	"""Label element::
	
	<!ELEMENT LABEL - - (%inline;)* -(LABEL) -- form field label text -->
	<!ATTLIST LABEL
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  for         IDREF          #IMPLIED  -- matches field ID value --
	  accesskey   %Character;    #IMPLIED  -- accessibility key character --
	  onfocus     %Script;       #IMPLIED  -- the element got the focus --
	  onblur      %Script;       #IMPLIED  -- the element lost the focus --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'label')
	XMLCONTENT=xmlns.XMLMixedContent

"""	
<!ENTITY % InputType
  "(TEXT | PASSWORD | CHECKBOX |
    RADIO | SUBMIT | RESET |
    FILE | HIDDEN | IMAGE | BUTTON)"
   >
"""

class Input(FormCtrlMixin,XHTMLElement):
	"""Represents the input element::

	<!-- attribute name required for all but submit and reset -->
	<!ELEMENT INPUT - O EMPTY              -- form control -->
	<!ATTLIST INPUT
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  type        %InputType;    TEXT      -- what kind of widget is needed --
	  name        CDATA          #IMPLIED  -- submit as part of form --
	  value       CDATA          #IMPLIED  -- Specify for radio buttons and checkboxes --
	  checked     (checked)      #IMPLIED  -- for radio buttons and check boxes --
	  disabled    (disabled)     #IMPLIED  -- unavailable in this context --
	  readonly    (readonly)     #IMPLIED  -- for text and passwd --
	  size        CDATA          #IMPLIED  -- specific to each type of field --
	  maxlength   NUMBER         #IMPLIED  -- max chars for text fields --
	  src         %URI;          #IMPLIED  -- for fields with images --
	  alt         CDATA          #IMPLIED  -- short description --
	  usemap      %URI;          #IMPLIED  -- use client-side image map --
	  ismap       (ismap)        #IMPLIED  -- use server-side image map --
	  tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
	  accesskey   %Character;    #IMPLIED  -- accessibility key character --
	  onfocus     %Script;       #IMPLIED  -- the element got the focus --
	  onblur      %Script;       #IMPLIED  -- the element lost the focus --
	  onselect    %Script;       #IMPLIED  -- some text was selected --
	  onchange    %Script;       #IMPLIED  -- the element value was changed --
	  accept      %ContentTypes; #IMPLIED  -- list of MIME types for file upload --
	  %reserved;                           -- reserved for possible future use --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'input')
	XMLCONTENT=xmlns.XMLEmpty


class Select(FormCtrlMixin,XHTMLElement):
	"""Select element::

	<!ELEMENT SELECT - - (OPTGROUP|OPTION)+ -- option selector -->
	<!ATTLIST SELECT
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  name        CDATA          #IMPLIED  -- field name --
	  size        NUMBER         #IMPLIED  -- rows visible --
	  multiple    (multiple)     #IMPLIED  -- default is single selection --
	  disabled    (disabled)     #IMPLIED  -- unavailable in this context --
	  tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
	  onfocus     %Script;       #IMPLIED  -- the element got the focus --
	  onblur      %Script;       #IMPLIED  -- the element lost the focus --
	  onchange    %Script;       #IMPLIED  -- the element value was changed --
	  %reserved;                           -- reserved for possible future use --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'select')
	XMLCONTENT=xmlns.XMLElementContent
	  
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.options=[]
	
	def OptGroup(self):
		child=OptGroup(self)
		self.options.append(child)
		return child
		
	def Option(self):
		child=Option(self)
		self.options.append(child)
		return child

	def GetChildren(self):
		return self.options


class OptGroup(XHTMLElement):
	"""OptGroup element::
	
	<!ELEMENT OPTGROUP - - (OPTION)+ -- option group -->
	<!ATTLIST OPTGROUP
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  disabled    (disabled)     #IMPLIED  -- unavailable in this context --
	  label       %Text;         #REQUIRED -- for use in hierarchical menus --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'optgroup')
	XMLCONTENT=xmlns.XMLElementContent

	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.Option=[]
	
	def GetChildren(self):
		return self.Option


class Option(XHTMLElement):
	"""Option element::
	
	<!ELEMENT OPTION - O (#PCDATA)         -- selectable choice -->
	<!ATTLIST OPTION
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  selected    (selected)     #IMPLIED
	  disabled    (disabled)     #IMPLIED  -- unavailable in this context --
	  label       %Text;         #IMPLIED  -- for use in hierarchical menus --
	  value       CDATA          #IMPLIED  -- defaults to element content --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'option')
	XMLCONTENT=xmlns.XMLMixedContent


class TextArea(FormCtrlMixin,XHTMLElement):
	"""TextArea element::

	<!ELEMENT TEXTAREA - - (#PCDATA)       -- multi-line text field -->
	<!ATTLIST TEXTAREA
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  name        CDATA          #IMPLIED
	  rows        NUMBER         #REQUIRED
	  cols        NUMBER         #REQUIRED
	  disabled    (disabled)     #IMPLIED  -- unavailable in this context --
	  readonly    (readonly)     #IMPLIED
	  tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
	  accesskey   %Character;    #IMPLIED  -- accessibility key character --
	  onfocus     %Script;       #IMPLIED  -- the element got the focus --
	  onblur      %Script;       #IMPLIED  -- the element lost the focus --
	  onselect    %Script;       #IMPLIED  -- some text was selected --
	  onchange    %Script;       #IMPLIED  -- the element value was changed --
	  %reserved;                           -- reserved for possible future use --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'textarea')
	XMLCONTENT=xmlns.XMLMixedContent


class FieldSet(BlockMixin,FlowContainer):
	"""fieldset element::
	
	<!ELEMENT FIELDSET - - (#PCDATA,LEGEND,(%flow;)*) -- form control group -->
	<!ATTLIST FIELDSET
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'fieldset')
	XMLCONTENT=xmlns.XMLElementContent

	def __init__(self,parent):
		FlowContainer.__init__(self,parent)
		self.Legend=Legend(self)
	
	def GetChildren(self):
		children=[self.Legend]+FlowContainer.GetChildren(self)
		return children

	def ChildElement(self,childClass,name=None):
		if childClass is Legend:
			return self.Legend
		else:
			return FlowContainer.ChildElement(self,childClass,name)
		

class Legend(InlineContainer):
	"""legend element::

	<!ELEMENT LEGEND - - (%inline;)*       -- fieldset legend -->
	
	<!ATTLIST LEGEND
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  accesskey   %Character;    #IMPLIED  -- accessibility key character --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'legend')
	XMLCONTENT=xmlns.XMLMixedContent


class Button(FormCtrlMixin,FlowContainer):
	"""button element::

	<!ELEMENT BUTTON - - (%flow;)* -(A|%formctrl;|FORM|FIELDSET) -- push button -->
	<!ATTLIST BUTTON
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  name        CDATA          #IMPLIED
	  value       CDATA          #IMPLIED  -- sent to server when submitted --
	  type        (button|submit|reset) submit -- for use as form button --
	  disabled    (disabled)     #IMPLIED  -- unavailable in this context --
	  tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
	  accesskey   %Character;    #IMPLIED  -- accessibility key character --
	  onfocus     %Script;       #IMPLIED  -- the element got the focus --
	  onblur      %Script;       #IMPLIED  -- the element lost the focus --
	  %reserved;                           -- reserved for possible future use --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'button')
	XMLCONTENT=xmlns.XMLMixedContent


# Object Elements

class Object(SpecialMixin,XHTMLElement):
	"""Represents the object element::
	
	<!ELEMENT OBJECT - - (PARAM | %flow;)*

	<!ATTLIST OBJECT
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  declare     (declare)      #IMPLIED  -- declare but don't instantiate flag --
	  classid     %URI;          #IMPLIED  -- identifies an implementation --
	  codebase    %URI;          #IMPLIED  -- base URI for classid, data, archive--
	  data        %URI;          #IMPLIED  -- reference to object's data --
	  type        %ContentType;  #IMPLIED  -- content type for data --
	  codetype    %ContentType;  #IMPLIED  -- content type for code --
	  archive     CDATA          #IMPLIED  -- space-separated list of URIs --
	  standby     %Text;         #IMPLIED  -- message to show while loading --
	  height      %Length;       #IMPLIED  -- override height --
	  width       %Length;       #IMPLIED  -- override width --
	  usemap      %URI;          #IMPLIED  -- use client-side image map --
	  name        CDATA          #IMPLIED  -- submit as part of form --
	  tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
	  %reserved;                           -- reserved for possible future use --
	  >
	"""	
	XMLNAME=(XHTML_NAMESPACE,'object')
	XMLATTR_data=('data',DecodeURI,EncodeURI)
	XMLATTR_type='type'
	XMLATTR_height=('height',DecodeLength,EncodeLength)
	XMLATTR_width=('width',DecodeLength,EncodeLength)
	XMLATTR_usemap=('usemap',DecodeURI,EncodeURI)	
	XMLATTR_name='name'
	XMLCONTENT=xmlns.XMLMixedContent
	
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.data=None
		self.type=None
		self.height=None
		self.width=None
		self.usemap=None
		self.name=None

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(FlowMixin,Param)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		

	def AddToCPResource(self,cp,resource,beenThere):
		if isinstance(self.data,FileURL):
			f=beenThere.get(str(self.data),None)
			if f is None:
				f=cp.CPFileCopy(resource,self.data)
				beenThere[str(self.data)]=f
			newData=f.ResolveURI(f.href)
			self.data=self.RelativeURI(newData)		

	
class Param(XHTMLElement):
	# <!ELEMENT PARAM - O EMPTY              -- named property value -->
	XMLNAME=(XHTML_NAMESPACE,'param')
	XMLCONTENT=xmlns.XMLEmpty
	
# Presentation Elements

class FontStyle(InlineMixin,InlineContainer):
	# strict:	<!ENTITY % fontstyle "TT | I | B | BIG | SMALL">
	# loose:	<!ENTITY % fontstyle "TT | I | B | U | S | STRIKE | BIG | SMALL">
	# <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
	pass

class B(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'b')
	XMLCONTENT=xmlns.XMLMixedContent

class Big(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'big')
	XMLCONTENT=xmlns.XMLMixedContent

class HR(BlockMixin,XHTMLElement):
	# <!ELEMENT HR - O EMPTY -- horizontal rule -->
	XMLNAME=(XHTML_NAMESPACE,'hr')
	XMLCONTENT=xmlns.XMLEmpty

class I(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'i')
	XMLCONTENT=xmlns.XMLMixedContent

class S(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'s')
	XMLCONTENT=xmlns.XMLMixedContent

class Small(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'small')
	XMLCONTENT=xmlns.XMLMixedContent

class Strike(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'strike')
	XMLCONTENT=xmlns.XMLMixedContent

class Sub(SpecialMixin,InlineContainer):
	# <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
	XMLNAME=(XHTML_NAMESPACE,'sub')
	XMLCONTENT=xmlns.XMLMixedContent
	
class Sup(SpecialMixin,InlineContainer):
	# <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
	XMLNAME=(XHTML_NAMESPACE,'sup')
	XMLCONTENT=xmlns.XMLMixedContent

class TT(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'tt')
	XMLCONTENT=xmlns.XMLMixedContent

class U(FontStyle):
	XMLNAME=(XHTML_NAMESPACE,'u')
	XMLCONTENT=xmlns.XMLMixedContent

# Table Elements

class Table(BlockMixin,XHTMLElement):
	# <!ELEMENT TABLE - - (CAPTION?, (COL*|COLGROUP*), THEAD?, TFOOT?, TBODY+)>
	XMLNAME=(XHTML_NAMESPACE,'table')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(Caption,Col,ColGroup,THead,TFoot,TBody)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif issubclass(childClass,TR):
			# TBODY can have it's start tag omitted
			tbody=self.ChildElement(TBody)
			return tbody.ChildElement(childClass)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))

class Caption(InlineContainer):
	# <!ELEMENT CAPTION  - - (%inline;)*     -- table caption -->
	XMLNAME=(XHTML_NAMESPACE,'caption')
	XMLCONTENT=xmlns.XMLMixedContent

class TRContainer(XHTMLElement):
	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,TR):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
		
class THead(TRContainer):
	# <!ELEMENT THEAD    - O (TR)+           -- table header -->
	XMLNAME=(XHTML_NAMESPACE,'thead')
	XMLCONTENT=xmlns.XMLElementContent

class TFoot(TRContainer):
	# <!ELEMENT TFOOT    - O (TR)+           -- table footer -->
	XMLNAME=(XHTML_NAMESPACE,'tfoot')
	XMLCONTENT=xmlns.XMLElementContent

class TBody(TRContainer):
	# <!ELEMENT TBODY    O O (TR)+           -- table body -->
	XMLNAME=(XHTML_NAMESPACE,'tbody')
	XMLCONTENT=xmlns.XMLElementContent

class ColGroup(XHTMLElement):
	# <!ELEMENT COLGROUP - O (COL)*          -- table column group -->
	XMLNAME=(XHTML_NAMESPACE,'colgroup')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,Col):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class Col(BlockMixin,XHTMLElement):
	# <!ELEMENT COL      - O EMPTY           -- table column -->
	XMLNAME=(XHTML_NAMESPACE,'col')
	XMLCONTENT=xmlns.XMLEmpty

class TR(XHTMLElement):
	# <!ELEMENT TR       - O (TH|TD)+        -- table row -->
	XMLNAME=(XHTML_NAMESPACE,'tr')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(TH,TD)):
			return xmlns.XMLNSElement.ChildElement(self,childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
	
class TH(FlowContainer):
	# <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
	XMLNAME=(XHTML_NAMESPACE,'th')
	XMLCONTENT=xmlns.XMLMixedContent
	
class TD(FlowContainer):
	# <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
	XMLNAME=(XHTML_NAMESPACE,'td')
	XMLCONTENT=xmlns.XMLMixedContent


# Link Element

class Link(XHTMLElement):
	"""Represents the LINK element::
	
	<!ELEMENT LINK - O EMPTY               -- a media-independent link -->
	<!ATTLIST LINK
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  charset     %Charset;      #IMPLIED  -- char encoding of linked resource --
	  href        %URI;          #IMPLIED  -- URI for linked resource --
	  hreflang    %LanguageCode; #IMPLIED  -- language code --
	  type        %ContentType;  #IMPLIED  -- advisory content type --
	  rel         %LinkTypes;    #IMPLIED  -- forward link types --
	  rev         %LinkTypes;    #IMPLIED  -- reverse link types --
	  media       %MediaDesc;    #IMPLIED  -- for rendering on these media --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'link')
	XMLCONTENT=xmlns.XMLEmpty

	
# Image Element

class Img(SpecialMixin,XHTMLElement):
	"""Represents the <img> element::
	
	<!ELEMENT IMG - O EMPTY                -- Embedded image -->
	<!ATTLIST IMG
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  src         %URI;          #REQUIRED -- URI of image to embed --
	  alt         %Text;         #REQUIRED -- short description --
	  longdesc    %URI;          #IMPLIED  -- link to long description
											  (complements alt) --
	  name        CDATA          #IMPLIED  -- name of image for scripting --
	  height      %Length;       #IMPLIED  -- override height --
	  width       %Length;       #IMPLIED  -- override width --
	  usemap      %URI;          #IMPLIED  -- use client-side image map --
	  ismap       (ismap)        #IMPLIED  -- use server-side image map --
	  >"""
	XMLNAME=(XHTML_NAMESPACE,'img')
	XMLCONTENT=xmlns.XMLEmpty
	XMLATTR_src=('src',DecodeURI,EncodeURI)
	XMLATTR_alt='alt'
	XMLATTR_longdesc=('longdesc',DecodeURI,EncodeURI)
	XMLATTR_name='name'
	XMLATTR_height=('height',DecodeLength,EncodeLength)
	XMLATTR_width=('width',DecodeLength,EncodeLength)
	XMLATTR_usemap=('usemap',DecodeURI,EncodeURI)
	XMLATTR_ismap=('ismap',lambda x:x.strip().lower()=='ismap',lambda x:'ismap' if x else None)
	
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.src=None
		self.alt=''
		self.londesc=None
		self.name=None
		self.height=None
		self.width=None
		self.usemap=None
		self.ismap=False

	def AddToCPResource(self,cp,resource,beenThere):
		if isinstance(self.src,FileURL):
			f=beenThere.get(str(self.src),None)
			if f is None:
				f=cp.CPFileCopy(resource,self.src)
				beenThere[str(self.src)]=f
			newSrc=f.ResolveURI(f.href)
			# Finally, we need change our src attribute
			self.src=self.RelativeURI(newSrc)		
		
# Hypertext Element

class A(SpecialMixin,InlineContainer):
	"""The HTML anchor element::

	<!ELEMENT A - - (%inline;)* -(A)       -- anchor -->
	<!ATTLIST A
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  charset     %Charset;      #IMPLIED  -- char encoding of linked resource --
	  type        %ContentType;  #IMPLIED  -- advisory content type --
	  name        CDATA          #IMPLIED  -- named link end --
	  href        %URI;          #IMPLIED  -- URI for linked resource --
	  hreflang    %LanguageCode; #IMPLIED  -- language code --
	  target      %FrameTarget;  #IMPLIED  -- render in this frame --
	  rel         %LinkTypes;    #IMPLIED  -- forward link types --
	  rev         %LinkTypes;    #IMPLIED  -- reverse link types --
	  accesskey   %Character;    #IMPLIED  -- accessibility key character --
	  shape       %Shape;        rect      -- for use with client-side image maps --
	  coords      %Coords;       #IMPLIED  -- for use with client-side image maps --
	  tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
	  onfocus     %Script;       #IMPLIED  -- the element got the focus --
	  onblur      %Script;       #IMPLIED  -- the element lost the focus --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'a')
	XMLATTR_charset='charset'
	XMLATTR_type='type'
	XMLATTR_name='name'
	XMLATTR_href=('href',DecodeURI,EncodeURI)
	XMLATTR_hreflang='hrefLang'
	XMLATTR_target='target'
	XMLATTR_rel='rel'
	XMLATTR_rev='rev'
	XMLATTR_accesskey='accessKey'
	XMLATTR_shape='shape'
	XMLATTR_coords='coords'
	XMLATTR_tabindex='tabIndex'
	XMLATTR_onfocus='onFocus'
	XMLATTR_onblur='onBlur'
	XMLCONTENT=xmlns.XMLMixedContent

	def __init__(self,parent):
		InlineContainer.__init__(self,parent)
		self.charset=None
		self.type=None
		self.name=None
		self.href=None
		self.hrefLang=None
		self.target=None
		self.rel=None
		self.rev=None
		self.accessKey=None
		self.shape=None
		self.coords=None
		self.tabIndex=None
		self.onFocus=None
		self.onBlur=None

# Frames

class FrameElement(XHTMLElement):
	pass
	
class Frameset(FrameElement):
	"""Frameset element::

	<!ELEMENT FRAMESET - - ((FRAMESET|FRAME)+ & NOFRAMES?) -- window subdivision-->
	<!ATTLIST FRAMESET
	  %coreattrs;                          -- id, class, style, title --
	  rows        %MultiLengths; #IMPLIED  -- list of lengths,
											  default: 100% (1 row) --
	  cols        %MultiLengths; #IMPLIED  -- list of lengths,
											  default: 100% (1 col) --
	  onload      %Script;       #IMPLIED  -- all the frames have been loaded  -- 
	  onunload    %Script;       #IMPLIED  -- all the frames have been removed -- 
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'frameset')
	XMLCONTENT=xmlns.XMLElementContent

	def __init__(self,parent):
		FrameElement.__init__(self,parent)
		self.FrameElement=[]
		self.NoFrames=None

	def GetChildren(self):
		children=self.FrameElement[:]
		xml.OptionalAppend(children,self.NoFrames)
		return children
		

class Frame(FrameElement):
	"""Frame element:
	<!-- reserved frame names start with "_" otherwise starts with letter -->
	<!ELEMENT FRAME - O EMPTY              -- subwindow -->
	<!ATTLIST FRAME
	  %coreattrs;                          -- id, class, style, title --
	  longdesc    %URI;          #IMPLIED  -- link to long description
											  (complements title) --
	  name        CDATA          #IMPLIED  -- name of frame for targetting --
	  src         %URI;          #IMPLIED  -- source of frame content --
	  frameborder (1|0)          1         -- request frame borders? --
	  marginwidth %Pixels;       #IMPLIED  -- margin widths in pixels --
	  marginheight %Pixels;      #IMPLIED  -- margin height in pixels --
	  noresize    (noresize)     #IMPLIED  -- allow users to resize frames? --
	  scrolling   (yes|no|auto)  auto      -- scrollbar or none --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'frame')
	XMLCONTENT=xmlns.XMLEmpty

	
class IFrame(SpecialMixin,FlowContainer):
	"""Represents the iframe element::

	<!ELEMENT IFRAME - - (%flow;)*         -- inline subwindow -->
	<!ATTLIST IFRAME
	  %coreattrs;                          -- id, class, style, title --
	  longdesc    %URI;          #IMPLIED  -- link to long description
											  (complements title) --
	  name        CDATA          #IMPLIED  -- name of frame for targetting --
	  src         %URI;          #IMPLIED  -- source of frame content --
	  frameborder (1|0)          1         -- request frame borders? --
	  marginwidth %Pixels;       #IMPLIED  -- margin widths in pixels --
	  marginheight %Pixels;      #IMPLIED  -- margin height in pixels --
	  scrolling   (yes|no|auto)  auto      -- scrollbar or none --
	  align       %IAlign;       #IMPLIED  -- vertical or horizontal alignment --
	  height      %Length;       #IMPLIED  -- frame height --
	  width       %Length;       #IMPLIED  -- frame width --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'iframe')
	XMLCONTENT=xmlns.XMLMixedContent


class NoFrames(FlowContainer):
	"""Represents the NOFRAMES element::

	In a frameset document:
	<!ENTITY % noframes.content "(BODY) -(NOFRAMES)">

	In a regular document:	
	<!ENTITY % noframes.content "(%flow;)*">
	
	<!ELEMENT NOFRAMES - - %noframes.content;
	 -- alternate content container for non frame-based rendering -->
	<!ATTLIST NOFRAMES
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  >
	"""
	def __init__(self,parent):
		FlowContainer.__init__(self,parent)
		self.Body=None
		
	def ChildElement(self,childClass,name=None):
		if self.FindParent(Frameset):
			if childClass is Body:
				return XHTMLElement.ChildElement(self,childClass,name)
			else:
				# Body can have it's start tag omitted
				XHTMLElement.ChildElement(self,Body)
				sefl.Body.ChildElement(childClass,name)
		else:
			FlowContainer.ChildElement(self,childClass,name)

	def GetChildren(self):
		if self.Body:
			return [self.Body]
		else:
			return FlowContainer.GetChildren(self)
			

# Document Head

class Head(XHTMLElement):
	"""Represents the HTML head structure::

	<!-- %head.misc; defined earlier on as "SCRIPT|STYLE|META|LINK|OBJECT" -->
	<!ENTITY % head.content "TITLE & BASE?">
	
	<!ELEMENT HEAD O O (%head.content;) +(%head.misc;) -- document head -->
	<!ATTLIST HEAD
	  %i18n;                               -- lang, dir --
	  profile     %URI;          #IMPLIED  -- named dictionary of meta info --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'head')
	XMLATTR_profile=('profile',DecodeURI,EncodeURI)
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.profile=None
		self.Title=Title(self)
		self.Base=None

	def GetChildren(self):
		children=[self.Title]
		xml.OptionalAppend(children,self.Base)
		return children+XHTMLElement.GetChildren(self)

class Title(XHTMLElement):
	"""Represents the title element::

	<!ELEMENT TITLE - - (#PCDATA) -(%head.misc;) -- document title -->
	<!ATTLIST TITLE %i18n>
	"""
	XMLNAME=(XHTML_NAMESPACE,'title')
	XMLCONTENT=xmlns.XMLMixedContent


class Meta(XHTMLElement):
	"""Represents the meta element::

	<!ELEMENT META - O EMPTY               -- generic metainformation -->
	<!ATTLIST META
	  %i18n;                               -- lang, dir, for use with content --
	  http-equiv  NAME           #IMPLIED  -- HTTP response header name  --
	  name        NAME           #IMPLIED  -- metainformation name --
	  content     CDATA          #REQUIRED -- associated information --
	  scheme      CDATA          #IMPLIED  -- select form of content --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'meta')
	XMLCONTENT=xmlns.XMLEmpty

	
class Base(XHTMLElement):
	"""Represents the base element::

	<!ELEMENT BASE - O EMPTY               -- document base URI -->
	<!ATTLIST BASE
	  href        %URI;          #REQUIRED -- URI that acts as base URI --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'base')
	XMLCONTENT=xmlns.XMLEmpty


class Style(XHTMLElement):
	"""Represents the style element::

	<!ELEMENT STYLE - - %StyleSheet        -- style info -->
	<!ATTLIST STYLE
	  %i18n;                               -- lang, dir, for use with title --
	  type        %ContentType;  #REQUIRED -- content type of style language --
	  media       %MediaDesc;    #IMPLIED  -- designed for use with these media --
	  title       %Text;         #IMPLIED  -- advisory title --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'style')
	XMLCONTENT=xmlns.XMLMixedContent
	SGMLCDATA=True

	
class Script(SpecialMixin,XHTMLElement):
	"""Represents the script element::

	<!ENTITY % Script "CDATA" -- script expression -->
	<!ELEMENT SCRIPT - - %Script;          -- script statements -->
	<!ATTLIST SCRIPT
	  charset     %Charset;      #IMPLIED  -- char encoding of linked resource --
	  type        %ContentType;  #REQUIRED -- content type of script language --
	  src         %URI;          #IMPLIED  -- URI for an external script --
	  defer       (defer)        #IMPLIED  -- UA may defer execution of script --
	  event       CDATA          #IMPLIED  -- reserved for possible future use --
	  for         %URI;          #IMPLIED  -- reserved for possible future use --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'script')
	XMLCONTENT=xmlns.XMLMixedContent
	SGMLCDATA=True
	
class NoScript(BlockMixin,FlowContainer):
	"""Represents the noscript element::

	<!ELEMENT NOSCRIPT - - (%flow;)*
	  -- alternate content container for non script-based rendering -->
	<!ATTLIST NOSCRIPT
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'noscript')
	XMLCONTENT=xmlns.XMLMixedContent
	

# Document Body

class Body(XHTMLElement):
	"""Represents the HTML BODY structure::

	<!ELEMENT BODY O O (%block;|SCRIPT)+ +(INS|DEL) -- document body -->
	<!ATTLIST BODY
	  %attrs;                              -- %coreattrs, %i18n, %events --
	  onload          %Script;   #IMPLIED  -- the document has been loaded --
	  onunload        %Script;   #IMPLIED  -- the document has been removed --
	"""
	XMLNAME=(XHTML_NAMESPACE,'body')
	XMLCONTENT=xmlns.XMLElementContent

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(BlockMixin,Script,Ins,Del)):
			return XHTMLElement.ChildElement(self,childClass,name)
		elif issubclass(childClass,FlowMixin):
			child=XHTMLElement.ChildElement(self,Div)
			return child.ChildElement(childClass,name)
		elif not issubclass(childClass,XHTMLElement):
			# children of another namespace can go in here
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s(%s) in %s"%(childClass.__name__,name,self.__class__.__name__))		
		
	
# Document Structures

class HTML(XHTMLElement):
	"""Represents the HTML document strucuture::

	<!ENTITY % html.content "HEAD, BODY">
	
	<!ELEMENT HTML O O (%html.content;)    -- document root element -->
	<!ATTLIST HTML
	  %i18n;                               -- lang, dir --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'html')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.Head=Head(self)
		self.Body=Body(self)

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(Head,Body)):
			return XHTMLElement.ChildElement(self,childClass,name)
		elif issubclass(childClass,(Title,Base,Script,Style,Meta,Link,Object)):
			# Head can have it's start tag omitted
			return self.Head.ChildElement(childClass)
		else:
			# ...as can Body
			return self.Body.ChildElement(childClass)

	def GetChildren(self):
		return [self.Head,self.Body]
	
	
class HTMLParser(xmlns.XMLNSParser):
	def __init__(self,entity=None):
		xmlns.XMLNSParser.__init__(self,entity)
		self.xmlFlag=False
		"""A flag that indicates if the parser is in xml mode."""
		
	def LookupEntity(self,name):
		codepoint=htmlentitydefs.name2codepoint.get(name,None)
		if codepoint is None:
			return ''
		else:
			return unichr(codepoint)

	def ParseHTMLDocument(self,doc):
		self.doc=doc
		self.xmlFlag=False
		match=self.ParseLiteral('<?xml')
		if match:
			self.ParseXMLDecl()
			self.xmlFlag=True
		else:
			self.compatibilityMode=True		
		self.entity.chunk=xml.XMLEntity.CHUNKSIZE
		s=self.ParseMisc()
		match=self.ParseLiteral('<!DOCTYPE')
		if match:
			s=None
			self.ParseDoctypeDecl()
			self.ParseMisc()
		if self.xmlFlag:
			self.ParseElement()			
			self.ParseMisc()
			if self.theChar is not None:
				raise XMLWellFormedError("Unparsed characters in entity after document")
		else:
			# with no xml declaration we revert to a more pragmatic parsing regime
			if s and self.theChar!='<':
				# if we matched any of the DOCTYPE literal we discard the space
				# otherwise we push the space back into the parser so that we
				# can treat it as content.
				self.BuffText(s)
			self.cdataEnd=None
			self.ParseHTMLContent()
			
	def ParseHTMLContent(self):
		foundElement=False
		while self.theChar is not None:
			data=self.ParseCharData()
			if data:
				if foundElement:
					self.doc.characters(data)
				elif xmlns.CollapseSpace(data)!=u" ":
					foundElement=True
					self.doc.startElementNS(HTML.XMLNAME,'html',{})
					self.doc.startElementNS(Div.XMLNAME,'div',{})
					self.doc.characters(data)
				data=None
			name=None
			if self.theChar=='<':
				self.NextChar()
				if self.theChar=='!':
					self.NextChar()
					if self.theChar=='-':
						if self.ParseLiteral('--'):
							self.ParseComment()
						else:
							data='<!'
					elif self.theChar=='[':
						if self.ParseLiteral('[CDATA['):
							data=self.ParseCDSect()
						else:
							data='<!'
					else:
						data='<!'
				elif self.theChar=='?':
					self.NextChar()
					self.ParsePI()
				elif self.theChar=='/':
					self.BuffText('<')
					name=self.ParseETag()
					self.doc.endElementNS((None,name),name)
				else:	
					self.BuffText('<')
					qname,attrs,empty=self.ParseSTag()
					foundElement=True
					ns=self.ParseNSAttributes(attrs)
					expandedName=self.ExpandQName(qname,ns)
					self.doc.startElementNS(expandedName,qname,attrs)
					self.doc.cObject.SetPrefixMap(ns)
					if empty or (isinstance(self.doc.cObject,XHTMLElement) and
						self.doc.cObject.__class__.XMLCONTENT==xmlns.XMLEmpty):
						self.doc.endElementNS(expandedName,qname)
			elif self.theChar=='&':
				data=self.ParseReference()	
			if data:
				if foundElement:
					self.doc.characters(data)
				elif xmlns.CollapseSpace(data)!=u" ":
					foundElement=True
					self.doc.startElementNS(HTML.XMLNAME,'html',{})
					self.doc.startElementNS(Div.XMLNAME,'div',{})
					self.doc.characters(data)
				data=None
		# when we reach the end of the stream we end the HTML element on the
		# 'one for luck' principle (spurious end tags are ignored by XHTMLDocument)
		self.doc.endElementNS(HTML.XMLNAME,'html')


class XHTMLDocument(xmlns.XMLNSDocument):
	"""Represents an HTML document.
	
	Although HTML documents are not always represented using XML they can be,
	and therefore we base our implementation on the
	:class:`pyslet.xmlnames20091208.XMLNSDocument` class - a namespace-aware
	variant of the basic :class:`pyslet.xml20081126.XMLDocument` class."""
	
	classMap={}
	"""Data member used to store a mapping from element names to the classes
	used to represent them.  This mapping is initialized when the module is
	loaded."""
	
	def __init__(self,**args):
		xmlns.XMLNSDocument.__init__(self,defaultNS=XHTML_NAMESPACE,**args)
		self.p=None
		
	def ReadFromEntity(self,e):
		"""We override the basic XML parsing to use a custom parser that is
		intelligent about the use of omitted tags, elements defined to have
		CDATA content and other SGML-based variations.  Note that if the
		document starts with an XML declaration then the normal XML parser is
		used instead.
		
		You won't normally need to call this method as it is invoked automatically
		when you call :meth:`pyslet.xml20081126.XMLDocument.Read`.
		
		The result is always a proper element hierarchy rooted in an HTML node,
		even if no tags are present at all the parser will construct an HTML
		document containing a single Div element to hold the parsed text."""
		self.cObject=self
		self.data=[]
		self.p=HTMLParser(e)
		self.p.ParseHTMLDocument(self)

	def GetElementClass(self,name):
		return XHTMLDocument.classMap.get(name,xmlns.XMLNSElement)

	def startElementNS(self, name, qname, attrs):
		if self.p.xmlFlag:
			xmlns.XMLNSDocument.startElementNS(self,name,qname,attrs)
			return
		parent=self.cObject
		if self.data:
			data=string.join(self.data,'')
			if isinstance(parent,xmlns.XMLNSElement):
				parent.AddData(data)
			elif xml.CollapseSpace(data)!=u" ":
				raise XHTMLValidityError("Unexpected document-level data: %s"%data)
			self.data=[]
		if name[0] is None:
			name=(self.defaultNS,name[1].lower())
		elif name[0]==XHTML_NAMESPACE:
			# any element in the XHTML namespace is lower-cased before lookup
			name=(XHTML_NAMESPACE,name[1].lower())		
		eClass=self.GetElementClass(name)
		try:
			if isinstance(parent,xml.XMLDocument):
				if eClass is HTML:
					self.cObject=parent.ChildElement(HTML)
				elif issubclass(eClass,XHTMLElement):
					parent=parent.ChildElement(HTML)
					self.cObject=parent.ChildElement(eClass)
				else:
					self.cObject=parent.ChildElement(eClass,name)
			elif issubclass(eClass,XHTMLElement):
				# Handle omitted tags
				self.cObject=None
				while isinstance(parent,xml.XMLElement):
					try:
						self.cObject=parent.ChildElement(eClass)
						break
					except XHTMLValidityError:
						# we can't go in here, close parent
						parent.GotChildren()
						parent=parent.parent
						continue
				if self.cObject is None:
					# so this is rubbish that we can't even add it to an HTML node?
					import pdb;pdb.set_trace()
					raise XHTMLValidityError("Found spurious element <%s>"%str(qname))
			else:
				print "Unknown element in HTML: %s"%str(name)
				self.cObject=parent.ChildElement(eClass,name)				
		except TypeError:
			raise TypeError("Can't create %s in %s"%(eClass.__name__,parent.__class__.__name__))
		if self.cObject is None:
			raise ValueError("None when creating %s in %s"%(eClass.__name__,parent.__class__.__name__))
		for attr in attrs.keys():
			try:
				if attr[0] is None:
					self.cObject.SetAttribute(attr[1],attrs[attr])
				else:
					self.cObject.SetAttribute(attr,attrs[attr])
			except xml.XMLIDClashError:
				# ignore ID clashes as they are common in HTML it seems
				continue
		if hasattr(eClass,'SGMLCDATA'):
			# This is a CDATA section...
			while self.p.theChar is not None:
				data=self.p.ParseCDSect('</')
				if data:
					self.cObject.AddData(data)
				eName=self.p.ParseName()
				if eName and eName.lower()==qname.lower():
					s=self.p.ParseS()
					self.p.ParseRequiredLiteral('>')
					break
				else:
					# This is an error, a CDATA element ends at the first ETAGO
					# but it seems it is a common error so forgive and forget
					if eName is None:
						eName=''
					self.cObject.AddData('</%s'%eName)
			self.endElementNS(name,qname)
			
	def endElementNS(self,name,qname):
		if self.p.xmlFlag:
			xmlns.XMLNSDocument.endElementNS(self,name,qname)
			return
		if name[0] is None:
			name=(self.defaultNS,name[1].lower())
		if self.data:
			data=string.join(self.data,'')
			if isinstance(self.cObject,xmlns.XMLNSElement):
				self.cObject.AddData(data)
			elif xml.CollapseSpace(data)!=u" ":
				raise XHTMLValidityError("Unexpected document-level data: %s"%data)
			self.data=[]
		# do we have a matching open element?
		e=self.cObject
		while isinstance(e,xml.XMLElement):
			if e.GetXMLName()==name:
				break
			else:
				e=e.parent
		if isinstance(e,xml.XMLElement):
			# Yes, repeat the process closing as we go.
			e=self.cObject
			while isinstance(e,xml.XMLElement):
				e.GotChildren()
				if e.GetXMLName()==name:
					# close this tag
					self.cObject=e.parent
					break
				else:
					e=e.parent
		else:
			# silently ignore mimatched closing tags, we'll get these anyway if someone
			# has used <br /> style notation because we know br is empty so closed it
			# during startElementNS ourselves - the parser follows this up with a second
			# call which we safely ignore because empty elements can't have instances of
			# themselves as parents (because they're empty!)
			pass

xmlns.MapClassElements(XHTMLDocument.classMap,globals())
