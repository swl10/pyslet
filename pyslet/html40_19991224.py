#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi

from pyslet.rfc2396 import URIFactory, EncodeUnicodeURI, FileURL

import htmlentitydefs
import string, itertools
from types import *
import os.path, shutil

HTML40_PUBLICID="-//W3C//DTD HTML 4.01//EN"
HTML40_SYSTEMID="http://www.w3.org/TR/html4/strict.dtd"

HTML40_TRANSITIONAL_PUBLICID="-//W3C//DTD HTML 4.01 Transitional//EN"
HTML40_TRANSITIONAL_SYSTEMID="http://www.w3.org/TR/1999/REC-html401-19991224/loose.dtd"

HTML40_FRAMESET_PUBLICID="-//W3C//DTD HTML 4.01 Frameset//EN"
HTML40_FRAMESET_SYSTEMID="http://www.w3.org/TR/1999/REC-html401-19991224/frameset.dtd"

HTML40_HTMLlat1_SYSTEMID="http://www.w3.org/TR/1999/REC-html401-19991224/HTMLlat1.ent"
HTML40_HTMLsymbol_SYSTEMID="http://www.w3.org/TR/1999/REC-html401-19991224/HTMLsymbol.ent"
HTML40_HTMLspecial_SYSTEMID="http://www.w3.org/TR/1999/REC-html401-19991224/HTMLspecial.ent"

XHTML_NAMESPACE="http://www.w3.org/1999/xhtml"


class NamedBoolean:
	"""An abstract class designed to make generating SGML-like single-value enumeration
	types easier, for example, attributes such as "checked" on <input>.
	
	The class is not designed to be instantiated but to act as a method of
	defining functions for decoding and encoding attribute values.

	The basic usage of this class is to derive a class from it with a single
	class member called 'name' which is the canonical representation of the
	name. You can then use it to call any of the following class methods to
	convert values between python Booleans the appropriate string
	representations (None for False and the defined name for True)."""
		
	@classmethod
	def DecodeValue(cls,src):
		"""Decodes a string returning True if it matches the name attribute
		and raising a ValueError otherwise.  If src is None then False is
		returned."""
		if src is None:
			return False
		else:
			src=src.strip()
			if src==cls.name:
				return True
			else:
				raise ValueError("Can't decode %s from %s"%(cls.__name__,src))

	@classmethod
	def DecodeLowerValue(cls,src):
		"""Decodes a string, converting it to lower case first."""
		if src is None:
			return False
		else:
			src=src.strip().lower()
			if src==cls.name:
				return True
			else:
				raise ValueError("Can't decode %s from %s"%(cls.__name__,src))
	
	@classmethod
	def DecodeUpperValue(cls,src):
		"""Decodes a string, converting it to upper case first."""
		if src is None:
			return False
		else:
			src=src.strip().upper()
			if src==cls.name:
				return True
			else:
				raise ValueError("Can't decode %s from %s"%(cls.__name__,src))
			 
	@classmethod
	def EncodeValue(cls,value):
		"""Encodes a boolean value returning either the defined name or None."""
		if value:
			return cls.name
		else:
			return None


XHTML_MIMETYPES={
	None: False,
	'text/xml': True,
	'text/html': False
	}

class XHTMLError(Exception): pass
class XHTMLValidityError(XHTMLError): pass
class XHTMLMimeTypeError(XHTMLError): pass

"""TODO: ContentType::

	<!ENTITY % ContentType "CDATA" -- media type, as per [RFC2045] --
	<!ENTITY % ContentTypes "CDATA" -- comma-separated list of media types, as per [RFC2045]	-->	"""

"""TODO: Charset::

	<!ENTITY % Charset "CDATA" -- a character encoding, as per [RFC2045] -->
	<!ENTITY % Charsets "CDATA" -- a space-separated list of character encodings, as per [RFC2045] -->	"""

"""TODO: LanguageCode::

	<!ENTITY % LanguageCode "NAME" -- a language code, as per [RFC1766] -->	"""

def DecodeCharacter(src):
	"""Decodes a Character value::
	
		<!ENTITY % Character "CDATA" -- a single character from [ISO10646] -->
	
	Returns the first character or src or None, if src is empty."""
	if len(src)>0:
		return src[0]
	else:
		return None

def EncodeCharacter(src):
	"""Encodes a Character value, a convenience function that returns src unchanged."""
	return src

			
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

	
"""TODO: Datetime::

	<!ENTITY % Datetime "CDATA" -- date and time information. ISO date format -->	"""


class HeadMiscMixin:
	"""Mixin class for misc head.misc elements::
	
		<!ENTITY % head.misc "SCRIPT|STYLE|META|LINK|OBJECT" -- repeatable head elements -->	"""
	pass


class CoreAttrsMixin:
	"""Mixin class for core attributes::

		<!ENTITY % coreattrs
		 "id          ID             #IMPLIED  -- document-wide unique id --
		  class       CDATA          #IMPLIED  -- space-separated list of classes --
		  style       %StyleSheet;   #IMPLIED  -- associated style info --
		  title       %Text;         #IMPLIED  -- advisory title --"
		  >

		<!ENTITY % StyleSheet "CDATA" -- style sheet data -->
		<!ENTITY % Text "CDATA">"""
	ID='id'
	XMLATTR_class='styleClass'
	XMLATTR_style='style'
	XMLATTR_title='title'

	def __init__(self):
		self.styleClass=None
		self.style=None
		self.title=None


class Dir(xsi.Enumeration):
	"""Enumeration for weak/neutral text values."""
	decode={
		'ltr':1,
		'rtl':2
		}
xsi.MakeEnumeration(Dir)


class I18nMixin:
	"""Mixin class for i18n attributes::
	
		<!ENTITY % i18n
		 "lang        %LanguageCode; #IMPLIED  -- language code --
		  dir         (ltr|rtl)      #IMPLIED  -- direction for weak/neutral text --"
		  >

		<!ENTITY % LanguageCode "NAME"
			-- a language code, as per [RFC1766]
			-->"""
	XMLATTR_lang=('htmlLang',xsi.DecodeName,xsi.EncodeName)
	XMLATTR_dir=('dir',Dir.DecodeLowerValue,Dir.EncodeValue)
	
	def __init__(self):
		self.htmlLange=None
		self.dir=Dir.DEFAULT


class EventsMixin:
	"""Mixin class for event attributes
	::

		<!ENTITY % Script "CDATA" -- script expression -->

		<!ENTITY % events
		 "onclick     %Script;       #IMPLIED  -- a pointer button was clicked --
		  ondblclick  %Script;       #IMPLIED  -- a pointer button was double clicked--
		  onmousedown %Script;       #IMPLIED  -- a pointer button was pressed down --
		  onmouseup   %Script;       #IMPLIED  -- a pointer button was released --
		  onmouseover %Script;       #IMPLIED  -- a pointer was moved onto --
		  onmousemove %Script;       #IMPLIED  -- a pointer was moved within --
		  onmouseout  %Script;       #IMPLIED  -- a pointer was moved away --
		  onkeypress  %Script;       #IMPLIED  -- a key was pressed and released --
		  onkeydown   %Script;       #IMPLIED  -- a key was pressed down --
		  onkeyup     %Script;       #IMPLIED  -- a key was released --"
		  >"""
	XMLATTR_onClick='onClick'
	XMLATTR_ondblclick='ondblclick'
	XMLATTR_onmousedown='onmousedown'
	XMLATTR_onmouseup='onmouseup'
	XMLATTR_onmouseover='onmouseover'
	XMLATTR_onmousemove='onmousemove'
	XMLATTR_onmouseout='onmouseout'
	XMLATTR_onkeypress='onkeypress'
	XMLATTR_onkeydown='onkeydown'
	XMLATTR_onkeyup='onkeyup'
	
	def __init__(self):
		self.onClick=None
		self.ondblclick=None
		self.onmousedown=None
		self.onmouseup=None
		self.onmouseover=None
		self.onmousemove=None
		self.onmouseout=None
		self.onkeypress=None
		self.onkeydown=None
		self.onkeyup=None
		

class AttrsMixin(CoreAttrsMixin,I18nMixin,EventsMixin):
	"""Mixin class for common attributes
	::

		<!ENTITY % attrs "%coreattrs; %i18n; %events;">"""
	
	def __init__(self):
		CoreAttrsMixin.__init__(self)
		I18nMixin.__init__(self)
		EventsMixin.__init__(self)

		
"""sgmlOmittag Feature:

Empty elements are handled by a simple XMLCONTENT attribute:

<!ELEMENT BASEFONT - O EMPTY           -- base font size -->
<!ELEMENT BR - O EMPTY                 -- forced line break -->
<!ELEMENT IMG - O EMPTY                -- Embedded image -->
<!ELEMENT HR - O EMPTY -- horizontal rule -->
<!ELEMENT INPUT - O EMPTY              -- form control -->
<!ELEMENT FRAME - O EMPTY              -- subwindow -->
<!ELEMENT ISINDEX - O EMPTY            -- single line prompt -->
<!ELEMENT BASE - O EMPTY               -- document base URI -->
<!ELEMENT META - O EMPTY               -- generic metainformation -->
<!ELEMENT AREA - O EMPTY               -- client-side image map area -->
<!ELEMENT LINK - O EMPTY               -- a media-independent link -->
<!ELEMENT PARAM - O EMPTY              -- named property value -->
<!ELEMENT COL      - O EMPTY           -- table column -->

Missing start tags must be handled in the context where these elements may occur:

<!ELEMENT BODY O O (%flow;)* +(INS|DEL) -- document body -->
<!ELEMENT TBODY    O O (TR)+           -- table body -->
<!ELEMENT HEAD O O (%head.content;) +(%head.misc;) -- document head -->
<!ELEMENT HTML O O (%html.content;)    -- document root element -->

Missing end tags must be handled in the elements themselves:

<!ELEMENT P - O (%inline;)*            -- paragraph -->
<!ELEMENT DT - O (%inline;)*           -- definition term -->
<!ELEMENT DD - O (%flow;)*             -- definition description -->
<!ELEMENT LI - O (%flow;)*             -- list item -->
<!ELEMENT OPTION - O (#PCDATA)         -- selectable choice -->
<!ELEMENT THEAD    - O (TR)+           -- table header -->
<!ELEMENT TFOOT    - O (TR)+           -- table footer -->
<!ELEMENT COLGROUP - O (COL)*          -- table column group -->
<!ELEMENT TR       - O (TH|TD)+        -- table row -->
<!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
"""

class LengthType:
	"""Represents the HTML Length::
	
		<!ENTITY % Length "CDATA" -- nn for pixels or nn% for percentage length -->

	* value can be either an integer value or another LengthType instance.
	
	* if value is an integer then valueType can be used to select Pixel or Percentage
	
	By default values are assumed to be Pixel lengths."""

	Pixel=0
	"""data constant used to indicate pixel co-ordinates"""

	Percentage=1
	"""data constant used to indicate relative (percentage) co-ordinates"""

	def __init__(self,value,valueType=None):
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

	def GetValue(self,dim=None):
		"""Returns the value of the Length, *dim* is the size of the dimension
		used for interpreting percentage values.  I.e., 100% will return
		*dim*."""
		if self.type==self.Percentage:
			if dim is None:
				raise ValueError("Relative length without dimension")
			else:
				return (self.value*dim+50)//100
		else:
			return self.value

	def Add(self,value):
		"""Adds *value* to the length.
		
		If value is another LengthType instance then its value is added to the
		value of this instances' value only if the types match.  If value is an
		integer it is assumed to be a value of pixel type - a mismatch raises
		ValueError."""
		if isinstance(value,LengthType):
			if self.type==value.type:
				self.value+=value.value
			else:
				raise ValueError("Can't add lengths of different types: %s+%s"%(str(self),str(value)))
		elif self.type==LengthType.Pixel:
			self.value+=value
		else:
			raise ValueError("Can't add integer to Percentage length value: %s+&i"%(str(self),value))

			
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
	
	Instances can be initialized from an existing list of :py:class:`LengthType`.
	
	If *values* is a list of integers then it is converted to a list of
	:py:class:`LengthType` instances."""
	def __init__(self,values=None):
		if values:
			self.values=[]
			for v in values:
				if isinstance(v,LengthType):
					self.values.append(v)
				else:
					self.values.append(LengthType(v))
			"""A list of LengthType values."""
		else:
			self.values=[]

	def __unicode__(self):
		"""Formats the Coords as comma-separated unicode string of Length values."""
		return string.join(map(lambda x:unicode(x),self.values),u',')
	
	def __str__(self):
		"""Formats the Coords as a comma-separated string of Length values."""
		return string.join(map(lambda x:str(x),self.values),',')
	
	def __len__(self):
		return len(self.values)

	def __getitem__(self,index):
		return self.values[index]
	
	def __setitem__(self,index,value):
		if isinstance(value,LengthType):
			self.values[index]=value
		else:
			self.values[index]=LengthType(value)
		
	def __iter__(self):
		return iter(self.values)

	def TestRect(self,x,y,width,height):
		"""Tests an x,y point against a rect with these coordinates.
		
		HTML defines the rect co-ordinates as: left-x, top-y, right-x, bottom-y"""
		if len(self.values)<4:
			raise ValueError("Rect test requires 4 coordinates: %s"%str(self.values))
		x0=self.values[0].GetValue(width)
		y0=self.values[1].GetValue(height)
		x1=self.values[2].GetValue(width)
		y1=self.values[3].GetValue(height)
		# swap the coordinates so that x0,y0 really is the top-left
		if x0>x1:
			xs=x0;x0=x1;x1=xs
		if y0>y1:
			ys=y0;y0=y1;y1=ys
		if x<x0 or y<y0:
			return False
		if x>=x1 or y>=y1:
			return False
		return True
		
	def TestCircle(self,x,y,width,height):
		"""Tests an x,y point against a circle with these coordinates.
		
		HTML defines a circle as: center-x, center-y, radius.
		
		The specification adds the following note:
			
			When the radius value is a percentage value, user agents should
			calculate the final radius value based on the associated object's
			width and height. The radius should be the smaller value of the two."""
		if len(self.values)<3:
			raise ValueError("Circle test requires 3 coordinates: %s"%str(self.values))
		if width<height:
			rMax=width
		else:
			rMax=height
		dx=x-self.values[0].GetValue(width)
		dy=y-self.values[1].GetValue(height)
		r=self.values[2].GetValue(rMax)
		return dx*dx+dy*dy<=r*r
	
	def TestPoly(self,x,y,width,height):
		"""Tests an x,y point against a poly with these coordinates.
		
		HTML defines a poly as: x1, y1, x2, y2, ..., xN, yN.
		
		The specification adds the following note:
		
			The first x and y coordinate pair and the last should be the same to
			close the polygon. When these coordinate values are not the same,
			user agents should infer an additional coordinate pair to close the
			polygon.
		
		The algorithm used is the "Ray Casting" algorithm described here:
		http://en.wikipedia.org/wiki/Point_in_polygon"""
		if len(self.values)<6:
			# We need at least six coordinates - to make a triangle
			raise ValueError("Poly test requires as least 3 coordinates: %s"%str(self.values))
		if len(self.values)%2:
			# We also need an even number of coordinates!
			raise ValueError("Poly test requires an even number of coordinates: %s"%str(self.values))
		# We build an array of y-values and clean up the missing end point problem
		vertex=[]
		i=0
		for v in self.values:
			if i%2:
				# this is a y coordinate
				vertex.append((lastX,v.GetValue(height)))
			else:
				# this is an x coordinate
				lastX=v.GetValue(width)
			i=i+1
		if vertex[0][0]!=vertex[-1][0] or vertex[0][1]!=vertex[-1][1]:
			# first point is not the same as the last point
			vertex.append(vertex[0])
		# We now have an array of vertex coordinates ready for the Ray Casting algorithm
		# We start from negative infinity with a horizontal ray passing through x,y
		nCrossings=0
		for i in xrange(len(vertex)-1):
			# we use a horizontal ray passing through the point x,y
			x0,y0=vertex[i]
			x1,y1=vertex[i+1]
			i+=1
			if y0==y1:
				# ignore horizontal edges
				continue
			if y0>y1:
				# swap the vertices so that x1,y1 has the higher y value
				xs,ys=x0,y0
				x0,y0=x1,y1
				x1,y1=xs,ys
			if y<y0 or y>=y1:
				# A miss, or at most a touch on the lower (higher y value) vertex
				continue
			elif y==y0:
				# The ray at most touches the upper vertex
				if x>=x0:
					# upper vertex intersection, or a miss
					nCrossings+=1
				continue
			if x<x0 and x<x1:
				# This edge is off to the right, a miss
				continue
			# Finally, we have to calculate an intersection
			xHit=float(y-y0)*float(x1-x0)/float(y1-y0)+float(x0)
			if xHit<=float(x):
				nCrossings+=1
		return nCrossings%2!=0
			
			 		
					
def DecodeCoords(value):
	"""Decodes coords from an attribute value string into a Coords instance."""
	if ',' in value:
		coords=value.split(',')
	else:
		coords=[]
	return Coords(map(lambda x:DecodeLength(x.strip()),coords))

def EncodeCoords(coords):
	"""Encodes a Coords instance as an attribute value string."""
	return unicode(coords)
			

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
	
	def RenderHTML(self,parent,profile,arg):
		"""Renders this HTML element to an external document represented by the *parent* node.
		
		*profile* is a dictionary mapping the names of allowed HTML elements to
		a list of allowed attributes.  This allows the caller to filter out
		unwanted elements and attributes.
		
		*arg* allows an additional argument to be passed through the HTML tree to any non-HTML
		nodes contained by it."""
		# the default implementation creates a node under parent if our name is in the profile
		if self.xmlname in profile:
			newChild=parent.ChildElement(self.__class__)
			aList=profile[self.xmlname]
			attrs=self.GetAttributes()
			for aName in attrs.keys():
		 		ns,name=aName
		 		if ns is None and name in aList:
		 			# this one is included
		 			newChild.SetAttribute(aName,attrs[aName])
		 	for child in self.GetChildren():
		 		if type(child) in StringTypes:
		 			newChild.AddData(child)
		 		else:
		 			child.RenderHTML(newChild,profile,arg)
	
	def RenderText(self):
		output=[]
		for child in self.GetChildren():
			if type(child) in StringTypes:
				output.append(child)
			else:
				output.append(child.RenderText())
		return string.join(output,'')
	

class FlowMixin:
	"""Mixin class for flow elements::
		
		<!ENTITY % flow "%block; | %inline;">
	"""
	pass

class BlockMixin(FlowMixin):
	"""Mixin class for block elements::
		
		<!ENTITY % block "P | %heading; | %list; | %preformatted; | DL | DIV |
			NOSCRIPT | BLOCKQUOTE | FORM | HR | TABLE | FIELDSET | ADDRESS">
	"""
	pass

class InlineMixin(FlowMixin):
	"""Mixin class for inline elements::
		
		<!ENTITY % inline "#PCDATA | %fontstyle; | %phrase; | %special; | %formctrl;">	"""
	pass


class InlineContainer(XHTMLElement):

	def GetChildClass(self,stagClass):
		"""If we get something other than PCDATA, an inline or unknown element, assume end"""
		if stagClass is None or issubclass(stagClass,InlineMixin) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

	def ChildElement(self,childClass,name=None):
		""""""
		if issubclass(childClass,InlineMixin) or not issubclass(childClass,XHTMLElement):
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		


class BlockContainer(XHTMLElement):
	"""Abstract class for all HTML elements that contain %block;|SCRIPT"""
	XMLCONTENT=xmlns.XMLMixedContent
	
	def GetChildClass(self,stagClass):
		"""If we get inline data in this context we force it to wrap in DIV"""
		if stagClass is None or issubclass(stagClass,InlineMixin):
			return Div
		elif issubclass(stagClass,(BlockMixin,Script)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,(BlockMixin,Script)) or not issubclass(childClass,XHTMLElement):
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		
	
	
class FlowContainer(XHTMLElement):
	"""Abstract class for all HTML elements that contain %flow;"""
	XMLCONTENT=xmlns.XMLMixedContent
	
	def GetChildClass(self,stagClass):
		"""If we get something other than, PCDATA, a flow or unknown element, assume end"""
		if stagClass is None or issubclass(stagClass,FlowMixin) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,FlowMixin) or not issubclass(childClass,XHTMLElement):
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			raise XHTMLValidityError("%s in %s"%(childClass.__name__,self.__class__.__name__))		

	def PrettyPrint(self):
		"""Deteremins if this flow-container should be pretty printed.
		
		We suppress pretty printing if we have any non-trivial data children or
		if we have any inline child elements."""
		for child in self.GetChildren():
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

	def GetChildClass(self,stagClass):
		"""If we get raw data in this context we assume an LI even though STag is compulsory."""
		if stagClass is None or issubclass(stagClass,FlowMixin):
			return LI
		elif issubclass(stagClass,LI) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

	
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
	XMLCONTENT=xmlns.ElementContent

	def GetChildClass(self,stagClass):
		"""If we get raw data in this context we assume a P to move closer to strict DTD
		(loose DTD allows any flow so raw data would be OK)."""
		if stagClass is None:
			return P
		elif issubclass(stagClass,(BlockMixin,Script)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None


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

	def GetChildClass(self,stagClass):
		"""End tag can be omitted."""
		if stagClass and issubclass(stagClass,InlineMixin):
			return stagClass
		else:
			return None

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
	XMLCONTENT=xmlns.ElementContent

	def GetChildClass(self,stagClass):
		"""If we get raw data in this context we assume a DD"""
		if stagClass is None:
			return DD
		elif issubclass(stagClass,(DT,DD)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

class DT(InlineContainer):
	# <!ELEMENT DT - O (%inline;)*           -- definition term -->
	XMLNAME=(XHTML_NAMESPACE,'dt')
	XMLCONTENT=xmlns.XMLMixedContent

	def GetChildClass(self,stagClass):
		"""End tag can be omitted."""
		if stagClass and issubclass(stagClass,InlineMixin):
			return stagClass
		else:
			return None

class DD(FlowContainer):
	# <!ELEMENT DD - O (%flow;)*             -- definition description -->
	XMLNAME=(XHTML_NAMESPACE,'dd')
	XMLCONTENT=xmlns.XMLMixedContent

class OL(List):
	# <!ELEMENT OL - - (LI)+                 -- ordered list -->
	XMLNAME=(XHTML_NAMESPACE,'ol')
	XMLCONTENT=xmlns.ElementContent
	
class UL(List):
	# <!ELEMENT UL - - (LI)+                 -- ordered list -->
	XMLNAME=(XHTML_NAMESPACE,'ul')
	XMLCONTENT=xmlns.ElementContent
	
class LI(FlowContainer):
	# <!ELEMENT LI - O (%flow;)*             -- list item -->
	XMLNAME=(XHTML_NAMESPACE,'li')
	XMLCONTENT=xmlns.XMLMixedContent


# Form Elements

class Method(xsi.Enumeration):
	"""HTTP method used to submit a form.  Usage example::

		Method.POST
	
	Note that::
		
		Method.DEFAULT == GET

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'GET':1,
		'POST':2
		}
xsi.MakeEnumeration(Method,"GET")


class Form(BlockMixin,BlockContainer):
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
	XMLATTR_action=('action',DecodeURI,EncodeURI)
	XMLATTR_method=('method',Method.DecodeUpperValue,Method.EncodeValue)
	XMLATTR_enctype='enctype'
	XMLATTR_accept='accept'
	XMLATTR_name='name'
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		BlockContainer.__init__(self,parent)
		self.action=None
		self.method=Method.DEFAULT
		self.enctype="application/x-www-form-urlencoded"
		self.accept=None
		self.name=None
		

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


class InputType(xsi.Enumeration):
	"""The type of widget needed for an input element.  Usage example::

		InputType.radio
	
	Note that::
		
		InputType.DEFAULT == InputType.text

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'text':1,
		'password':2,
		'checkbox':3,
		'radio':4,
		'submit':5,
		'reset':6,
		'file':7,
		'hidden':8,
		'image':9,
		'button':10
		}
xsi.MakeEnumeration(InputType,"text")


class Checked(NamedBoolean):
	"""Used for the checked attribute."""
	name="checked"

class Disabled(NamedBoolean):
	"""Used for the disabled attribute."""
	name="disabled"

class ReadOnly(NamedBoolean):
	"""Used for the readonly attribute."""
	name="readonly"

class IsMap(NamedBoolean):
	"""Used for the ismap attribute."""
	name="ismap"

	
class Input(FormCtrlMixin,AttrsMixin,XHTMLElement):
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
	XMLATTR_type=('type',InputType.DecodeLowerValue,InputType.EncodeValue)
	XMLATTR_name='name'
	XMLATTR_value='value'
	XMLATTR_checked=('checked',Checked.DecodeLowerValue,Checked.EncodeValue)
	XMLATTR_disabled=('disabled',Disabled.DecodeLowerValue,Disabled.EncodeValue)
	XMLATTR_readonly=('readonly',ReadOnly.DecodeLowerValue,ReadOnly.EncodeValue)
	XMLATTR_size='size'
	XMLATTR_maxLength=('maxLength',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_src=('src',DecodeURI,EncodeURI)
	XMLATTR_alt='alt'
	XMLATTR_usemap=('usemap',DecodeURI,EncodeURI)
	XMLATTR_ismap=('ismap',IsMap.DecodeLowerValue,IsMap.EncodeValue)
	XMLATTR_tabindex=('tabindex',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_accesskey=('accesskey',DecodeCharacter,EncodeCharacter)
	XMLATTR_onfocus='onfocus'
	XMLATTR_onblur='onblur'
	XMLATTR_onselect='onselect'
	XMLATTR_onchange='onchange'
	XMLATTR_accept='accept'
	
	XMLCONTENT=xmlns.XMLEmpty

	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		AttrsMixin.__init__(self)
		self.type=InputType.DEFAULT
		self.name=None
		self.value=None
		self.checked=False
		self.disabled=False
		self.readonly=False
		self.size=None
		self.maxLength=None
		self.src=None
		self.alt=None
		self.usemap=None
		self.ismap=False
		self.tabindex=None
		self.accesskey=None
		self.onfocus=None
		self.onblur=None
		self.onselect=None
		self.onchange=None
		self.accept=None
		

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
	XMLCONTENT=xmlns.ElementContent
	  
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
		return iter(self.options)


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
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.Option=[]
	
	def GetChildren(self):
		return iter(self.Option)


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
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		FlowContainer.__init__(self,parent)
		self.Legend=Legend(self)
	
	def GetChildren(self):
		yield self.Legend
		for child in FlowContainer.GetChildren(self): yield child

	def GetChildClass(self,stagClass):
		if stagClass is not None and issubclass(stagClass,Legend):
			return stagClass
		else:
			return FlowContainer.GetChildClass(self,stagClass)

	def ChildElement(self,childClass,name=None):
		if issubclass(childClass,Legend):
			return XHTMLElement.ChildElement(self,childClass,name)
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


class ButtonType(xsi.Enumeration):
	"""The type action required for a form button."""
	decode={
		'button':1,
		'submit':2,
		'reset':3
		}
xsi.MakeEnumeration(ButtonType,"submit")


class Button(AttrsMixin,FormCtrlMixin,FlowContainer):
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
	XMLATTR_name='name'
	XMLATTR_value='value'
	XMLATTR_type=('type',ButtonType.DecodeLowerValue,ButtonType.EncodeValue)
	XMLATTR_disabled=('disabled',Disabled.DecodeLowerValue,Disabled.EncodeValue)
	XMLATTR_tabindex=('tabindex',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_accesskey=('accesskey',DecodeCharacter,EncodeCharacter)
	XMLATTR_onfocus='onfocus'
	XMLATTR_onblur='onblur'
	XMLCONTENT=xmlns.XMLMixedContent

	def __init__(self,parent):
		FlowContainer.__init__(self,parent)
		AttrsMixin.__init__(self)
		self.name=None
		self.value=None
		self.type=ButtonType.DEFAULT
		self.disabled=False
		self.tabindex=None
		self.accesskey=None
		self.onfocus=None
		self.onblur=None

# Object Elements

class Object(SpecialMixin,HeadMiscMixin,XHTMLElement):
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

	def GetChildClass(self,stagClass):
		"""stagClass should not be None"""
		if stagClass is None:
			raise XHTMLError("Object: Unexpected None in GetChildClass")
		elif issubclass(stagClass,(Param,FlowMixin)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

	def AddToCPResource(self,cp,resource,beenThere):
		if isinstance(self.data,FileURL):
			f=beenThere.get(str(self.data),None)
			if f is None:
				f=cp.FileCopy(resource,self.data)
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
	XMLCONTENT=xmlns.ElementContent

	def GetChildClass(self,stagClass):
		"""PCDATA triggers the TBody"""
		if stagClass is None or issubclass(stagClass,TR):
			return TBody
		elif issubclass(stagClass,(Caption,Col,ColGroup,THead,TFoot,TBody)) or not issubclass(stagClass,XHTMLElement):
			return stagClass		
		else:
			return None


class Caption(InlineContainer):
	# <!ELEMENT CAPTION  - - (%inline;)*     -- table caption -->
	XMLNAME=(XHTML_NAMESPACE,'caption')
	XMLCONTENT=xmlns.XMLMixedContent

class TRContainer(XHTMLElement):
	def GetChildClass(self,stagClass):
		"""PCDATA or TH|TD trigger TR"""
		if stagClass is None or issubclass(stagClass,(TH,TD)):
			return TR
		elif issubclass(stagClass,(TR)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None
		
class THead(TRContainer):
	# <!ELEMENT THEAD    - O (TR)+           -- table header -->
	XMLNAME=(XHTML_NAMESPACE,'thead')
	XMLCONTENT=xmlns.ElementContent

class TFoot(TRContainer):
	# <!ELEMENT TFOOT    - O (TR)+           -- table footer -->
	XMLNAME=(XHTML_NAMESPACE,'tfoot')
	XMLCONTENT=xmlns.ElementContent

class TBody(TRContainer):
	# <!ELEMENT TBODY    O O (TR)+           -- table body -->
	XMLNAME=(XHTML_NAMESPACE,'tbody')
	XMLCONTENT=xmlns.ElementContent

class ColGroup(XHTMLElement):
	# <!ELEMENT COLGROUP - O (COL)*          -- table column group -->
	XMLNAME=(XHTML_NAMESPACE,'colgroup')
	XMLCONTENT=xmlns.ElementContent

	def GetChildClass(self,stagClass):
		"""PCDATA in ColGroup ends the ColGroup"""
		if stagClass is None:
			return None
		elif issubclass(stagClass,(Col)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None

	
class Col(BlockMixin,XHTMLElement):
	# <!ELEMENT COL      - O EMPTY           -- table column -->
	XMLNAME=(XHTML_NAMESPACE,'col')
	XMLCONTENT=xmlns.XMLEmpty

class TR(XHTMLElement):
	# <!ELEMENT TR       - O (TH|TD)+        -- table row -->
	XMLNAME=(XHTML_NAMESPACE,'tr')
	XMLCONTENT=xmlns.ElementContent

	def GetChildClass(self,stagClass):
		"""PCDATA in TR starts a TD"""
		if stagClass is None:
			return TD
		elif issubclass(stagClass,(TH,TD)) or not issubclass(stagClass,XHTMLElement):
			return stagClass
		else:
			return None
	
class TH(FlowContainer):
	# <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
	XMLNAME=(XHTML_NAMESPACE,'th')
	XMLCONTENT=xmlns.XMLMixedContent
	
class TD(FlowContainer):
	# <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
	XMLNAME=(XHTML_NAMESPACE,'td')
	XMLCONTENT=xmlns.XMLMixedContent


# Link Element

class Link(HeadMiscMixin,XHTMLElement):
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
				f=cp.FileCopy(resource,self.src)
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
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		FrameElement.__init__(self,parent)
		self.FrameElement=[]
		self.NoFrames=None

	def GetChildren(self):
		for child in self.FrameElement: yield child
		if self.NoFrames: yield self.NoFrames
		

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
		
	def GetChildClass(self,stagClass):
		"""In a FRAMESET document, any element in NOFRAMES introduces Body"""
		if self.FindParent(Frameset):
			return Body
		else:
			return stagClass
			if issubclass(stagClass,FlowMixin) or not issubclass(stagClass,XHTMLElement):
					return stagClass
			else:
				return None

	def GetChildren(self):
		if self.Body:
			yield Body
		else:
			for child in FlowContainer.GetChildren(self): yield child
			

# Document Head

class HeadContentMixin:
	"""Mixin class for HEAD content elements::
	
		<!ENTITY % head.content "TITLE & BASE?">
	"""
	pass

class Head(XHTMLElement):
	"""Represents the HTML head structure::

		<!ELEMENT HEAD O O (%head.content;) +(%head.misc;) -- document head -->
		<!ATTLIST HEAD
		  %i18n;                               -- lang, dir --
		  profile     %URI;          #IMPLIED  -- named dictionary of meta info --
		  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'head')
	XMLATTR_profile=('profile',DecodeURI,EncodeURI)
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.profile=None
		self.Title=Title(self)
		self.Base=None
		self.HeadMiscMixin=[]
		
	def GetChildClass(self,stagClass):
		if stagClass is None:
			# PCDATA in Head indicates end of Head, start of Body
			return None
		elif issubclass(stagClass,(HeadContentMixin,HeadMiscMixin,NoScript)):
			# We add NoScript for future HTML5 compatibility
			return stagClass
		else:
			# anything else terminates HEAD
			return None
		
	def GetChildren(self):
		yield self.Title
		if self.Base: yield self.Base
		for child in itertools.chain(
			self.HeadMiscMixin,
			XHTMLElement.GetChildren(self)):
			yield child


class Title(HeadContentMixin,XHTMLElement):
	"""Represents the title element::

	<!ELEMENT TITLE - - (#PCDATA) -(%head.misc;) -- document title -->
	<!ATTLIST TITLE %i18n>
	"""
	XMLNAME=(XHTML_NAMESPACE,'title')
	XMLCONTENT=xmlns.XMLMixedContent


class Meta(HeadMiscMixin,XHTMLElement):
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

	
class Base(HeadContentMixin,XHTMLElement):
	"""Represents the base element::

	<!ELEMENT BASE - O EMPTY               -- document base URI -->
	<!ATTLIST BASE
	  href        %URI;          #REQUIRED -- URI that acts as base URI --
	  >
	"""
	XMLNAME=(XHTML_NAMESPACE,'base')
	XMLCONTENT=xmlns.XMLEmpty


class Style(HeadMiscMixin,XHTMLElement):
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
	SGMLCONTENT=xmlns.SGMLCDATA

	
class Script(SpecialMixin,HeadMiscMixin,XHTMLElement):
	"""Represents the script element::

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
	SGMLCONTENT=xmlns.SGMLCDATA
	
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
	
	def ChildElement(self,childClass,name=None):
		if self.FindParent(Head) and issubclass(childClass,(Link,Style,Meta)):
			# HTML5 compatibility, bypass normal FlowContainer handling.
			return XHTMLElement.ChildElement(self,childClass,name)
		else:
			return FlowContainer.ChildElement(self,childClass,name)


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
	XMLCONTENT=xmlns.ElementContent

	def GetChildClass(self,stagClass):
		"""Handled omitted tags"""
		if stagClass is None:
			# data in Body implies DIV
			return Div
		elif issubclass(stagClass,(BlockMixin,Script,Ins,Del)) or not issubclass(stagClass,XHTMLElement):
			# children of another namespace can go in here too
			return stagClass
		elif issubclass(stagClass,FlowMixin):
			# allowed by loose DTD but we encapsulate in Flow to satisfy strict
			return Div
		elif issubclass(stagClass,(Head,HeadMiscMixin,HeadContentMixin)):
			# Catch HEAD content appearing in BODY and force HEAD, BODY, HEAD, BODY,... to catch all.
			return None
		else:
			raise XHTMLValidityError("%s in %s"%(stagClass.__name__,self.__class__.__name__))		
				
	
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
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		XHTMLElement.__init__(self,parent)
		self.Head=Head(self)
		self.Body=Body(self)

	def GetChildClass(self,stagClass):
		"""Overridden to ensure we always return either HEAD or BODY, we can accommodate any tag!"""
		if stagClass and issubclass(stagClass,(Head,HeadContentMixin,Style,Meta,Link)):
			# possibly missing STag for HEAD; we leave out Script
			return Head
		else:
			# Script, Object (and may be NoScript) are ambiguous but we infer body by default
			return Body
		
	def GetChildren(self):
		yield self.Head
		yield self.Body
	
	
class HTMLParser(xmlns.XMLNSParser):
	def __init__(self,entity=None,xmlHint=False):
		xmlns.XMLNSParser.__init__(self,entity)
		self.xmlFlag=xmlHint
		"""A flag that indicates if the parser is in xml mode."""
		
	def LookupPredefinedEntity(self,name):
		codepoint=htmlentitydefs.name2codepoint.get(name,None)
		if codepoint is None:
			return None
		else:
			return unichr(codepoint)

	def ParseProlog(self):
		"""[22] prolog: parses the document prolog, including the XML declaration and dtd.
		
		We override this method to enable us to dynamically set the parser options
		based on the presence of an XML declaration or DOCTYPE."""
		production="[22] prolog"
		if self.ParseLiteral('<?xml'):
			self.ParseXMLDecl(True)
		else:
			self.declaration=None
			self.sgmlNamecaseGeneral=True
			self.sgmlOmittag=True
			self.sgmlContent=True
			self.dontCheckWellFormedness=True
		self.entity.KeepEncoding()
		# we inline ParseMisc to capture all the white space
		s=[]
		while True:
			if xml.IsS(self.theChar):
				s.append(self.theChar)
				self.NextChar()
				continue
			elif self.ParseLiteral('<!--'):
				self.ParseComment(True)
				continue
			elif self.ParseLiteral('<?'):
				self.ParsePI(True)
				continue
			else:
				break
		if self.ParseLiteral('<!DOCTYPE'):
			self.ParseDoctypedecl(True)
			self.ParseMisc()
		else:
			self.dtd=xml.XMLDTD()
			if self.sgmlNamecaseGeneral:
				self.dtd.name='HTML'
				# no XML declaration, and no DOCTYPE, are we at the first element?
				if self.theChar!='<':
					# this document starts with character data but we want to fore
					# any leading space to be included, as that is usually the
					# intention of authors writing HTML fragments,
					# particularly as they are typically in <![CDATA[ sections in the
					# enclosing document, e.g.,
					# <tag>Yes I<htmlFrag><![CDATA[ <b>did</b>]]></htmlFrag></tag>
					# we do this by tricking the parser with a character reference
					if s:
						s[0]="&#x%02X;"%ord(s[0])
					self.BuffText(string.join(s,''))
			else:
				self.dtd.name='html'
		

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
	
	DefaultNS=XHTML_NAMESPACE	#: the default namespace for HTML elements 
	
	def __init__(self,**args):
		xmlns.XMLNSDocument.__init__(self,**args)
		self.p=None
	
	def XMLParser(self,entity):
		"""We override the basic XML parser to use a custom parser that is
		intelligent about the use of omitted tags, elements defined to have
		CDATA content and other SGML-based variations.  Note that if the
		document starts with an XML declaration then the normal XML parser is
		used instead.
		
		You won't normally need to call this method as it is invoked automatically
		when you call :meth:`pyslet.xml20081126.XMLDocument.Read`.
		
		The result is always a proper element hierarchy rooted in an HTML node,
		even if no tags are present at all the parser will construct an HTML
		document containing a single Div element to hold the parsed text."""
		xmlHint=XHTML_MIMETYPES.get(entity.mimetype,None)
		if xmlHint is not None:				
			return HTMLParser(entity,xmlHint)
		else:
			raise XHTMLMimeTypeError(entity.mimetype)

	def GetChildClass(self,stagClass):
		"""Always returns HTML."""
		return HTML
		
	def GetElementClass(self,name):
		eClass=XHTMLDocument.classMap.get(name,None)
		if eClass is None:
			lcName=(name[0],name[1].lower())
			eClass=XHTMLDocument.classMap.get(lcName,xmlns.XMLNSElement)
		return eClass
		

xmlns.MapClassElements(XHTMLDocument.classMap,globals())
