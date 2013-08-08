#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

import sys, cgi, urllib, string, itertools, traceback, StringIO, json, decimal, uuid

import pyslet.info as info
import pyslet.iso8601 as iso
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.rfc2616 as http
import pyslet.rfc2396 as uri
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
import pyslet.mc_edmx as edmx
import pyslet.mc_csdl as edm

class InvalidLiteral(Exception): pass
class InvalidServiceDocument(Exception): pass
class InvalidMetadataDocument(Exception): pass
class InvalidFeedDocument(Exception): pass
class InvalidEntryDocument(Exception): pass
class InvalidFeedURL(Exception): pass
class UnexpectedHTTPResponse(Exception): pass

class ServerError(Exception): pass
class BadURISegment(ServerError): pass
class MissingURISegment(ServerError): pass


ODATA_METADATA_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"	#: namespace for metadata, e.g., the property type attribute
IsDefaultEntityContainer=(ODATA_METADATA_NAMESPACE,u"IsDefaultEntityContainer")

ODATA_DATASERVICES_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices"		#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_SCHEME="http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"					#: category scheme for type definition terms
ODATA_RELATED="http://schemas.microsoft.com/ado/2007/08/dataservices/related/"				#: link type for related entries

ODATA_RELATED_TYPE="application/atom+xml;type=entry"

class Parser(edm.Parser):
	
	def ParseURILiteral(self):
		"""Returns a :py:class:`pyslet.mc_csdl.SimpleType` instance."""
		if self.ParseInsensitive("null"):
			return edm.SimpleValue(None)
		elif self.Parse("'"):
			# string of utf-8 characters
			result=edm.SimpleValue(edm.SimpleType.String)
			value=[]
			while True:
				startPos=self.pos
				while not self.Parse("'"):
					if self.MatchEnd():
						raise ValueError("Unterminated quote in literal string")
					self.NextChar()					
				value.append(self.src[startPos:self.pos-1])
				if self.Parse("'"):
					# a repeated SQUOTE, go around again
					continue
				break
			value=string.join(value,"'")
			if self.raw:
				value=value.decode('utf-8')
			result.simpleValue=value
			return result
		elif self.MatchDigit():
			return self.ParseNumericLiteral()
		elif self.Parse('-'):
			# one of the number forms
			if self.ParseInsensitive("inf"):
				if self.ParseOne("Dd"):
					result=edm.SimpleValue(edm.SimpleType.Double)
					result.simpleValue=float("-INF")
					return result
				elif self.ParseOne("Ff"):
					result=edm.SimpleValue(edm.SimpleType.Single)
					result.simpleValue=float("-INF")
					return result
				else:
					raise ValueError("Expected double or single -inf: -INF%s"%repr(self.Peek(1)))							
			else:
				return self.ParseNumericLiteral('-')
		elif self.ParseInsensitive("true"):
			result=edm.SimpleValue(edm.SimpleType.Boolean)
			result.simpleValue=True
			return result
		elif self.ParseInsensitive("false"):
			result=edm.SimpleValue(edm.SimpleType.Boolean)
			result.simpleValue=False
			return result
		elif self.ParseInsensitive("datetimeoffset"):
			result=edm.SimpleValue(edm.SimpleType.DateTimeOffset)
			production="datetimeoffset literal"
			self.Require("'",production)
			startPos=self.pos
			while not self.Parse("'"):
				if self.MatchEnd():
					raise ValueError("Unterminated quote in datetimeoffset string")
				self.NextChar()					
			try:
				value=iso.TimePoint(self.src[startPos:self.pos-1])
			except iso.DateTimeError,e:
				raise ValueError(str(e))
			zOffset,zDir=value.GetZone()
			if zOffset is None:
				raise ValueError("datetimeoffset requires zone specifier: %s"%str(value))
			if not value.Complete():
				raise ValueError("datetimeoffset requires a complete specification: %s"%str(value))
			result.simpleValue=value
			return result
		elif self.ParseInsensitive("datetime"):
			result=edm.SimpleValue(edm.SimpleType.DateTime)
			production="datetime literal"
			self.Require("'",production)
			year=int(self.RequireProduction(self.ParseDigits(4,4),production))
			self.Require("-",)
			month=self.RequireProduction(self.ParseInteger(1,12),"month")
			self.Require("-",production)
			day=self.RequireProduction(self.ParseInteger(1,31,2),"day")
			self.Require("T",production)
			hour=self.RequireProduction(self.ParseInteger(0,24),"hour")
			self.Require(":",production)
			minute=self.RequireProduction(self.ParseInteger(0,60,2),"minute")
			if self.Parse(":"):
				second=self.RequireProduction(self.ParseInteger(0,60,2),"second")
				if self.Parse("."):
					nano=self.ParseDigits(1,7)
					second+=float("0."+nano)					
			else:
				second=None
			self.Require("'",production)
			value=iso.TimePoint()
			try:
				value.SetCalendarTimePoint(year/100,year%100,month,day,hour,minute,second)
			except iso.DateTimeError,e:
				raise ValueError(str(e))
			result.simpleValue=value
			return result
		elif self.ParseInsensitive("time"):
			result=edm.SimpleValue(edm.SimpleType.Time)
			self.Require("'","time")
			startPos=self.pos
			while not self.Parse("'"):
				if self.MatchEnd():
					raise ValueError("Unterminated quote in time string")
				self.NextChar()					
			try:
				value=xsi.Duration(self.src[startPos:self.pos-1])
			except iso.DateTimeError,e:
				raise ValueError(str(e))			
			result.simpleValue=value
			return result
		elif self.Parse("X") or self.ParseInsensitive("binary"):
			self.Require("'","binary")
			result=edm.SimpleValue(edm.SimpleType.Binary)
			value=self.ParseBinaryLiteral()
			self.Require("'","binary literal")
			result.simpleValue=value
			return result
		elif self.Match("."):
			# One of the elided numeric forms, don't parse the point!
			return self.ParseNumericLiteral()
		elif self.ParseInsensitive("nan"):
			if self.ParseOne("Dd"):
				result=edm.SimpleValue(edm.SimpleType.Double)
				result.simpleValue=float("Nan")
				return result
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue(edm.SimpleType.Single)
				result.simpleValue=float("Nan")
				return result
			else:
				raise ValueError("Expected double or single Nan: Nan%s"%repr(self.Peek(1)))			
		elif self.ParseInsensitive("inf"):
			if self.ParseOne("Dd"):
				result=edm.SimpleValue(edm.SimpleType.Double)
				result.simpleValue=float("INF")
				return result
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue(edm.SimpleType.Single)
				result.simpleValue=float("INF")
				return result
			else:
				raise ValueError("Expected double or single inf: INF%s"%repr(self.Peek(1)))
		elif self.ParseInsensitive("guid"):
			result=edm.SimpleValue(edm.SimpleType.Guid)
			self.Require("'","guid")
			hex=[]
			hex.append(self.RequireProduction(self.ParseHexDigits(8,8),"guid"))
			self.Require("-","guid")			
			hex.append(self.RequireProduction(self.ParseHexDigits(4,4),"guid"))
			self.Require("-","guid")			
			hex.append(self.RequireProduction(self.ParseHexDigits(4,4),"guid"))
			self.Require("-","guid")			
			hex.append(self.RequireProduction(self.ParseHexDigits(4,4),"guid"))
			if self.Parse('-'):
				# this is a proper guid
				hex.append(self.RequireProduction(self.ParseHexDigits(12,12),"guid"))
			else:
				# this a broken guid, add some magic to make it right
				hex[3:3]=['FFFF']
				hex.append(self.RequireProduction(self.ParseHexDigits(8,8),"guid"))
			self.Require("'","guid")
			result.simpleValue=uuid.UUID(hex=string.join(hex,''))
			return result
		else:			
			raise ValueError("Expected literal: %s"%repr(self.Peek(10)))

	def ParseNumericLiteral(self,sign=''):
		digits=self.ParseDigits(1)
		if self.Parse("."):
			# could be a decimal
			decDigits=self.ParseDigits(1)
			if self.ParseOne("Mm"):
				result=edm.SimpleValue(edm.SimpleType.Decimal)
				# it was a decimal
				if decDigits is None:
					raise ValueError("Missing digis after '.' for decimal: %s.d"%(digits))		
				if len(digits)>29 or len(decDigits)>29:
					raise ValueError("Too many digits for decimal literal: %s.%s"%(digits,decDigits))
				result.simpleValue=decimal.Decimal("%s%s.%s"%(sign,digits,decDigits))
				return result
			elif self.ParseOne("Dd"):
				result=edm.SimpleValue(edm.SimpleType.Double)
				if digits is None:
					digits='0'
				if decDigits is None:
					decDigits='0'
				# it was a double, no length restrictions
				result.simpleValue=float("%s%s.%s"%(sign,digits,decDigits))
				return result
			elif self.ParseOne("Ee"):
				eSign=self.Parse("-")
				eDigits=self.RequireProduction(self.ParseDigits(1,3),"exponent")
				if self.ParseOne("Dd"):
					result=edm.SimpleValue(edm.SimpleType.Double)
					if digits is None:
						raise ValueError("Missing digis before '.' for expDecimal")
					if decDigits is None:
						decDigits='0'
					elif len(decDigits)>16:
						raise ValueError("Too many digits for double: %s.%s"%(digits,decDigits))
					result.simpleValue=float("%s%s.%se%s%s"%(sign,digits,decDigits,eSign,eDigits))
					return result
				elif self.ParseOne("Ff"):
					result=edm.SimpleValue(edm.SimpleType.Single)
					if digits is None:
						raise ValueError("Missing digis before '.' for expDecimal")
					if decDigits is None:
						decDigits='0'
					elif len(decDigits)>8:
						raise ValueError("Too many digits for single: %s.%s"%(digits,decDigits))					
					elif len(eDigits)>2:
						raise ValueError("Too many digits for single exponet: %s.%sE%s%s"%(digits,decDigits,eSign,eDigits))					
					result.simpleValue=float("%s%s.%se%s%s"%(sign,digits,decDigits,eSign,eDigits))
					return result
				else:
					raise ValueError("NotImplementedError")
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue(edm.SimpleType.Single)
				if digits is None:
					digits='0'
				if decDigits is None:
					decDigits='0'
				# it was a single, no length restrictions
				result.simpleValue=float("%s%s.%s"%(sign,digits,decDigits))
				return result
			else:
				raise ValueError("NotImplementedError")
		elif self.ParseOne("Mm"):
			result=edm.SimpleValue(edm.SimpleType.Decimal)
			if len(digits)>29:
				raise ValueError("Too many digits for decimal literal: %s"%digits)
			result.simpleValue=decimal.Decimal("%s%s"%(sign,digits))
			return result
		elif self.ParseOne("Ll"):
			result=edm.SimpleValue(edm.SimpleType.Int64)
			if len(digits)>19:
				raise ValueError("Too many digits for int64 literal: %s"%digits)
			result.simpleValue=long("%s%s"%(sign,digits))
			return result
		elif self.ParseOne("Dd"):
			result=edm.SimpleValue(edm.SimpleType.Double)
			if len(digits)>17:
				raise ValueError("Too many digits for double literal: %s"%digits)
			result.simpleValue=float(sign+digits)
			return result
		elif self.ParseOne("Ff"):
			result=edm.SimpleValue(edm.SimpleType.Single)
			if len(digits)>8:
				raise ValueError("Too many digits for single literal: %s"%digits)
			result.simpleValue=float(sign+digits)
			return result
		else:
			result=edm.SimpleValue(edm.SimpleType.Int32)
			# just a bunch of digits followed by something else so return int32
			if digits is None:
				raise ValueError("Digits required for integer literal: %s"%digits)				
			if len(digits)>10:
				raise ValueError("Too many digits for integer literal: %s"%digits)
			# watch out, largest negative number is larger than largest positive number!
			value=int(sign+digits)
			if value>2147483647 or value<-2147483648:
				raise ValueError("Range of int32 exceeded: %s"%(sign+digits))
			result.simpleValue=value
			return result

	
def ParseURILiteral(source):
	"""Parses a literal value from a source string.
	
	Returns a tuple of a:
	
		*	a constant from :py:class:`pyslet.mc_csdl.SimpleType`
		
		*	the value, represented with the closest python built-in type
	
	The special string "null" returns None,None"""
	p=Parser(source)
	return p.RequireProductionEnd(p.ParseURILiteral(),"uri literal")

	
def ParseDataServiceVersion(src):
	"""Parses DataServiceVersion from a header field value.
	
	Returns a triple of (integer) major version, (integer) minor version and a
	user agent string.  See section 2.2.5.3 of the specification."""
	mode="#"
	versionStr=None
	uaStr=[]
	for w in http.SplitWords(src):
		if mode=="#":
			if w[0] in http.HTTP_SEPARATORS:
				break
			else:
				# looking for the digit.digit
				versionStr=w
				mode=';'
		elif mode==';':
			if w[0]==mode:
				mode='u'
			else:
				break
		elif mode=='u':
			if w[0] in http.HTTP_SEPARATORS:
				uaStr=None
				break
			else:
				uaStr.append(w)	
	if versionStr is not None:
		v=versionStr.split('.')
		if len(v)==2 and http.IsDIGITS(v[0]) and http.IsDIGITS(v[1]):
			major=int(v[0])
			minor=int(v[1])
		else:
			versionStr=None
	if versionStr is None:
		raise ValueError("Can't read version number from DataServiceVersion: %s"%src)		
	if uaStr is None:
		raise ValueError("Can't read user agent string from DataServiceVersion: %s"%src)
	return major,minor,string.join(uaStr,' ')	


def ParseMaxDataServiceVersion(src):
	"""Parses MaxDataServiceVersion from a header field value.
	
	Returns a triple of (integer) major version, (integer) minor version and a
	user agent string.  See section 2.2.5.7 of the specification."""
	src2=src.split(';')
	versionStr=None
	uaStr=None
	if len(src2)>0:	
		words=http.SplitWords(src2[0])
		if len(words)==1:
			versionStr=words[0]
	if len(src2)>1:
		uaStr=string.join(src2[1:],';')
	if versionStr is not None:
		v=versionStr.split('.')
		if len(v)==2 and http.IsDIGITS(v[0]) and http.IsDIGITS(v[1]):
			major=int(v[0])
			minor=int(v[1])
		else:
			versionStr=None
	if versionStr is None:
		raise ValueError("Can't read version number from MaxDataServiceVersion: %s"%src)		
	if uaStr is None:
		raise ValueError("Can't read user agent string from MaxDataServiceVersion: %s"%src)
	return major,minor,uaStr	


class ODataURI:
	"""Breaks down an OData URI into its component parts.
	
	You pass the URI (or a string) to construct the object.  You may also pass
	an optional *pathPrefix* which is a string that represents the part of the
	path that will be ignored.  In other words, *pathPrefix* is the path
	component of the service root.

	There's a little bit of confusion as to whether the service root can be
	empty or not.  An empty service root will be automatically converted to '/'
	by the HTTP protocol.  As a result, the service root often appears to
	contain a trailing slash even when it is not empty.  The sample OData server
	from Microsoft issues a temporary redirect from /OData/OData.svc to add the
	trailing slash before returning the service document."""
	
	def __init__(self,dsURI,pathPrefix=''):
		if not isinstance(dsURI,uri.URI):
			dsURI=uri.URIFactory.URI(dsURI)
		self.schema=dsURI.scheme
		self.pathPrefix=pathPrefix		#: a string containing the path prefix without a trailing slash
		self.resourcePath=None			#: a string containing the resource path (or None if this is not a resource path)
		self.navPath=[]					#: a list of navigation path component strings
		self.queryOptions=[]			#: a list of raw strings containing custom query options and service op params
		self.sysQueryOptions={}			#: a dictionary of system query options
		self.paramTable={}
		if dsURI.absPath is None:
			#	relative paths are resolved relative to the pathPrefix with an added slash!
			#	so ODataURI('Products','/OData/OData.svc') is treated as '/OData/OData.svc/Products'
			dsURI=uri.URIFactory.Resolve(pathPrefix+'/',dsURI)
		if dsURI.absPath is None:
			#	both dsURI and pathPrefix are relative, this is an error
			raise ValueError("pathPrefix cannot be relative: %s"%pathPrefix)
		if pathPrefix and not dsURI.absPath.startswith(pathPrefix):
			# this is not a URI we own
			return
		if dsURI.query is not None:
			rawOptions=dsURI.query.split('&')
			for paramDef in rawOptions:
				if paramDef and paramDef[0]=='$':
					paramName=uri.UnescapeData(paramDef[:paramDef.index('=')]).decode('utf-8')
					self.sysQueryOptions[paramName]=paramDef[paramDef.index('=')+1:]
				else:
					if '=' in paramDef:
						paramName=uri.UnescapeData(paramDef[:paramDef.index('=')]).decode('utf-8')
						self.paramTable[paramName]=len(self.queryOptions)
					self.queryOptions.append(paramDef)
		self.resourcePath=dsURI.absPath[len(pathPrefix):]
		# grab the first component of the resourcePath
		if self.resourcePath=='/':
			self.navPath=[]
		else:
			components=self.resourcePath.split('/')
			self.navPath=map(self.SplitComponent,components[1:])
	
	def SplitComponent(self,component):
		"""Splits a string component into a unicode name and a keyPredicate dictionary."""
		if component.startswith('$'):
			# some type of control word
			return component,{}
		elif '(' in component and component[-1]==')':
			name=uri.UnescapeData(component[:component.index('(')]).decode('utf-8')
			keys=component[component.index('(')+1:-1]
			if keys=='':
				keys=[]
			else:
				keys=keys.split(',')
			if len(keys)==0:
				return name,{}
			elif len(keys)==1 and '=' not in keys[0]:
				return name,{u'':ParseURILiteral(keys[0]).simpleValue}
			else:
				keyPredicate={}
				for k in keys:
					nv=k.split('=')
					if len(nv)!=2:
						raise ValueError("unrecognized key predicate: %s"%repr(keys))
					kname,value=nv
					kname=uri.UnescapeData(kname).decode('utf-8')
					kvalue=ParseURILiteral(value).simpleValue
					keyPredicate[kname]=kvalue
				return name,keyPredicate
		else:
			return uri.UnescapeData(component).decode('utf-8'),{}
	
	def GetParamValue(self,paramName):
		if paramName in self.paramTable:
			paramDef=self.queryOptions[self.paramTable[paramName]]
			# must be a primitive type
			return ParseURILiteral(paramDef[paramDef.index('=')+1:])
		else:
			raise KeyError("Missing service operation, or custom parameter: %s"%paramName)
		
			
class ODataElement(xmlns.XMLNSElement):
	"""Base class for all OData specific elements."""
	pass


class Property(ODataElement):
	"""Represents each property value.
	
	The OData namesapce does not define elements in the dataservices space as
	the elements take their names from the properties themselves.  Therefore,
	the xmlname of each Property instance is the property name."""
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.edmValue=None		# an :py:class:`pyslet.mc_csdl.EDMValue` instance
	
	def GetSimpleType(self):
		type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
		if type:			
			try:
				type=edm.SimpleType.DecodeLowerValue(type.lower())
			except ValueError:
				# assume unknown, probably complex 			
				type=None
			return type
		else:
			return None
						
	def GetValue(self,value=None):
		"""Gets an appropriately typed value for the property.
		
		Overloads the basic
		:py:meth:`~pyslet.xml20081126.structures.Element.GetValue`
		implementation to transform the value into an
		:py:class:`pyslet.mc_csdl.EDMValue` instance.
		
		An optional :py:class:`pyslet.mc_csdl.EDMValue` can be passed,
		if present the instance's value is updated with the value of
		this Property element."""
		null=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'null'))
		null=(null and null.lower()=="true")
		if value is None:
			entry=self.FindParent(Entry)
			if entry and entry.entityType:
				propertyDef=entry.entityType.get(self.xmlname,None)
			else:
				propertyDef=None
			if propertyDef:
				value=propertyDef()
			else:
				pList=[]
				# picks up top-level properties only! 
				self.FindChildren(Property,pList)
				if pList:
					# we have a complex type with no definition
					value=edm.Complex()
				else:
					type=self.GetSimpleType()
					if type is None:
						# unknown simple types treated as string
						type=edm.SimpleType.String
					value=edm.SimpleValue(type,self.xmlname)
		if isinstance(value,edm.SimpleValue):
			if null:
				value.SetSimpleValue(None)
			else:
				value.SetFromLiteral(ODataElement.GetValue(self))
		else:
			# you can't have a null complex value BTW
			for child in self.GetChildren():
				if isinstance(child,Property):
					if child.xmlname in value:
						child.GetValue(value[child.xmlname])
					else:
						value.AddProperty(child.xmlname,child.GetValue())
		return value

	def SetValue(self,value):
		"""Sets the value of the property
		
		The null property is updated as appropriate.
		
		When changing the value of an existing property we must match
		the existing type.  For new property values we use the value
		type to set the type property."""
		declaredType=self.GetSimpleType()
		if isinstance(value,edm.SimpleValue):
			type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
			if declaredType is None:
				if type is None:
					self.SetAttribute((ODATA_METADATA_NAMESPACE,'type'),edm.SimpleType.EncodeValue(value.typeCode))
				else:
					# an unknown type can only be set from string, to match GetValue
					if value.tyepCode!=edm.SimpleType.String:
						raise TypeError("Incompatible property types: %s and %s"%(type,edm.SimpleType.EncodeValue(value.typeCode)))
			else:
				if declaredType!=value.typeCode:
					raise TypeError("Incompatible property types: %s and %s"%(type,edm.SimpleType.EncodeValue(value.typeCode)))
			if value:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),None)
				ODataElement.SetValue(self,unicode(value))
			else:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),"true")
				ODataElement.SetValue(self,"")
		elif isinstance(value,edm.Complex):
			type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
			if type:
				if value.typeDef and value.typeDef.name!=type:
					raise TypeError("Incompatible complex types: %s and %s"%(type,value.typeDef.name))
			elif value.typeDef:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'type'),value.typeDef.name)
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),None)
			# loop through our children and set them from this value
			keys={}
			for key in value:
				keys[key]=value[key]				
			for child in self.GetChildren():
				if isinstance(child,Property):
					if child.xmlname in keys:
						child.SetValue(keys[child.xmlname])
						del keys[child.xmlname]
					# otherwise leave the value alone
			for key in keys:
				# add any missing children
				p=self.ChildElement(self.__class__,(ODATA_DATASERVICES_NAMESPACE,key))
				p.SetValue(keys[key])
		elif value is None:
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),"true")
			ODataElement.SetValue(self,"")
		else:
			edmValue=edm.SimpleValue(edm.SimpleType.FromPythonType(type(value)))
			if declaredType is None:
				type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
				# can only set from a string (literal form)
				if edmValue.typeCode!=edm.SimpleType.String:
					raise TypeError("Incompatible property types: %s and %s"%(type,edm.SimpleType.EncodeValue(edmValue.typeCode)))
			elif edmValue.typeCode!=declaredType:
				newValue=edm.SimpleValue(declaredType)
				newValue.SetSimpleValue(edm.SimpleType.CoerceValue(declaredType,edmValue.GetSimpleValue()))
				edmValue=newValue
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),None)
			ODataElement.SetValue(self,unicode(edmValue))

			
class Properties(ODataElement):
	"""Represents the properties element."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'properties')
	
	PropertyClass=Property
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Property=[]

	def GetChildren(self):
		return itertools.chain(
			self.Property,
			ODataElement.GetChildren(self))
		
		
class Content(atom.Content):
	"""Overrides the default :py:class:`pyslet.rfc4287.Content` class to add OData handling."""
		
	def __init__(self,parent):
		atom.Content.__init__(self,parent)
		self.type='application/xml'
		self.Properties=None		#: the optional properties element containing the entry's property values

	def GetChildren(self):
		for child in atom.Content.GetChildren(self): yield child
		if self.Properties: yield self.Properties

	
class Entry(atom.Entry):
	"""Overrides the default :py:class:`pyslet.rfc4287.Entry` class to add OData handling.
	
	In addition to the default *parent* element an Entry can be passed
	an optional `pyslet.mc_csdl.Entity` instance.  If present, it is
	used to construct the Entry representation of the entity."""
	
	ContentClass=Content
	
	def __init__(self,parent,entity=None):
		atom.Entry.__init__(self,parent)
		self.entityType=None		#: :py:class:`pyslet.mc_csdl.EntityType` instance describing the entry
		self._properties={}
		if entity is not None:
			self.entityType=entity.typeDef
			for k in entity:
				self[k]=entity[k]
	
	def ContentChanged(self):
		atom.Entry.ContentChanged(self)
		self._properties={}
		if self.Content and self.Content.Properties:
			for p in self.Content.Properties.Property:
				self._properties[p.xmlname]=p
			
	def __getitem__(self,key):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to read property values.
		
		Returns the value of the property with *key* as a
		`pyslet.mc_csdl.EDMValue` instance."""
		return self._properties[key].GetValue()

	def __setitem__(self,key,value):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to set property values.
		
		Sets the property *key* to *value*.  If *value* is not an
		:py:class:`pyslet.mc_csdl.EDMValue` instance it will be coerced
		to an appropriate value on a best-effort basis.
		
		For existing properties, the *value* must be a compatible type
		and will be coerced to match the property's defined type if
		necessary.  See
		:py:meth:`Property.SetValue` for more information."""
		if key in self._properties:
			p=self._properties[key].SetValue(value)
		else:
			ps=self.ChildElement(self.ContentClass).ChildElement(Properties)
			p=ps.ChildElement(ps.PropertyClass,(ODATA_DATASERVICES_NAMESPACE,key))
			p.SetValue(value)
			self._properties[key]=p

	def AddLink(self,linkTitle,linkURI):
		"""Adds a link with name *linkTitle* to the entry with *linkURI*."""
		l=self.ChildElement(self.LinkClass)
		l.href=linkURI
		l.rel=ODATA_RELATED+linkTitle
		l.title=linkTitle
		l.type=ODATA_RELATED_TYPE

	def SetValue(self,entity):
		"""Sets the value of this Entry to represent *entity*, a :py:class:`pyslet.mc_csdl.TypeInstance` instance."""
		# start by removing the existing properties
		if self.Content and self.Content.Properties:
			self.Content.DeleteChild(self.Content.Properties)
		self.entityType=entity.typeDef
		for key in entity:
			self[key]=entity[key]
		self.ContentChanged()


class URI(ODataElement):
	"""Represents a single URI in the XML-response to $links requests"""
	XMLNAME=(ODATA_DATASERVICES_NAMESPACE,'uri')
	

class Links(ODataElement):
	"""Represents a list of links in the XML-response to $links requests"""
	XMLNAME=(ODATA_DATASERVICES_NAMESPACE,'links')
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.URI=[]

	def GetChildren(self):
		return itertools.chain(
			self.URI,
			ODataElement.GetChildren(self))


class EntitySet(edm.EntitySet):
	"""We override EntitySet inorder to provide some documented signatures for
	sets of media-stream entities."""
	
	def GetStreamType(self,entity):
		"""Returns the content type of the entity's media stream.
		
		Must return a :py:class:`pyslet.rfc2616.MediaType` instance."""
		raise NotImplementedError
	
	def GetStreamSize(self,entity):
		"""Returns the size of the entity's media stream in bytes."""
		raise NotImplementedError
		
	def GetStreamGenerator(self,entity):
		"""A generator function that yields blocks (strings) of data from the entity's media stream."""
		raise NotImplementedError

		
class Client(app.Client):
	"""An OData client.
	
	Can be constructed with an optional URL specifying the service root of an
	OData service."""
	
	def __init__(self,serviceRoot=None):
		app.Client.__init__(self)
		self.SetLog(http.HTTP_LOG_ERROR,sys.stdout)
		self.feeds=[]		#: a list of feeds associated with this client
		self.feedTitles={}	#: a dictionary of feed titles, mapped to collection URLs
		self.schemas={}		#: a dictionary of namespaces mapped to Schema instances
		self.pageSize=None
		"""the default number of entries to retrieve with each request
		
		None indicates no restriction, request all entries."""		
		if serviceRoot:
			self.SetService(serviceRoot)
		else:
			self.serviceRoot=None	#: the URI of the service root
		# Initialise a simple cache of type name -> EntityType definition
		self._cacheTerm=None
		self._cacheType=None
		
	def SetService(self,serviceRoot):
		"""Adds the feeds defined by the URL *serviceRoot* to this client."""
		self.feeds=[]
		self.feedTitles={}
		self.schems={}
		doc=Document(baseURI=serviceRoot,reqManager=self)
		doc.Read()
		if isinstance(doc.root,app.Service):
			for w in doc.root.Workspace:
				for f in w.Collection:
					url=f.GetFeedURL()
					if f.Title:
						self.feedTitles[f.Title.GetValue()]=url
					self.feeds.append(url)
		else:
			raise InvalidServiceDocument(str(serviceRoot))
		metadata=uri.URIFactory.Resolve(serviceRoot,'$metadata')
		doc=edmx.Document(baseURI=metadata,reqManager=self)
		try:
			doc.Read()
			if isinstance(doc.root,edmx.Edmx):
				for s in doc.root.DataServices.Schema:
					self.schemas[s.name]=s
		except xml.XMLError:
			# Failed to read the metadata document, there may not be one of course
			pass
		# reset the cache
		self._cacheTerm=None
		self._cacheType=None
		self.serviceRoot=uri.URIFactory.URI(serviceRoot)

	def LookupEntityType(self,entityTypeName):
		"""Returns the :py:class:`EntityType` instance associated with the fully qualified *entityTypeName*"""
		entityType=None
		if entityTypeName==self._cacheTerm:
			# time saver as most feeds are just lists of the same type
			entityType=self._cacheType
		else:
			name=entityTypeName.split('.')
			if name[0] in self.schemas:
				try:
					entityType=self.schemas[name[0]][string.join(name[1:],'.')]
				except KeyError:
					pass
			# we cache both positive and negative results
			self._cacheTerm=entityTypeName
			self._cacheType=entityType
		return entityType

	def AssociateEntityType(self,entry):
		for c in entry.Category:
			entry.entityType=None
			if c.scheme==ODATA_SCHEME and c.term:
				entry.entityType=self.LookupEntityType(c.term)
			
	def RetrieveFeed(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns a :py:class:`pyslet.rfc4287.Feed` object representing it."""
		doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Feed):
			for e in doc.root.Entry:
				self.AssociateEntityType(e)
			return doc.root
		else:
			raise InvalidFeedDocument(str(feedURL))
	
	def RetrieveEntries(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns an iterable yielding :py:class:`Entry` instances.
		
		This method uses the :py:attr:`pageSize` attribute to set the paging of
		the data.  (The source may restrict the number of return values too). 
		It hides the details required to iterate through the entire list of
		entries with the caveat that there is no guarantee that the results will
		be consistent.  If the data source is being updated or reconfigured it
		is possible that the some entries may be skipped or duplicated as a result
		of being returned by different HTTP requests."""
		if self.pageSize:
			skip=0
			page=self.pageSize
		else:
			skip=page=None
		if odataQuery is None:
			odataQuery={}
		while True:
			if page:
				if skip:
					odataQuery['$skip']=str(skip)				
			doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
			doc.Read()
			if isinstance(doc.root,atom.Feed):
				if len(doc.root.Entry):
					for e in doc.root.Entry:
						self.AssociateEntityType(e)
						yield e
				else:
					break
			else:
				raise InvalidFeedDocument(str(feedURL))
			if page:
				skip=skip+page
			else:
				# check for 'next' link
				feedURL=None
				for link in doc.root.Link:
					if link.rel=="next":
						feedURL=link.ResolveURI(link.href)
						break
				if feedURL is None:
					break
						
	
	def Entry(self,entityTypeName=None):
		"""Returns a new :py:class:`Entry` suitable for passing to :py:meth:`AddEntry`.
		
		The optional *entityTypeName* is the name of an EntityType to bind this
		entry to.  The name must be the fully qualified name of a type in one of
		the namespaces.  A Category instance is added to the Entry to represent this
		binding."""
		if entityTypeName:
			entityType=self.LookupEntityType(entityTypeName)
			if entityType is None:
				raise KeyError("Undeclared Type: %s"%entityTypeName)
		else:
			entityType=None
		e=Entry(None)
		e.entityType=entityType
		if entityType:
			c=e.ChildElement(atom.Category)
			c.scheme=ODATA_SCHEME
			c.term=entityTypeName				
		return e		
				
	def AddEntry(self,feedURL,entry):
		"""Given a feed URL, adds an :py:class:`Entry` to it
		
		Returns the new entry as returned by the OData service.  *entry* must be
		an orphan element."""
		doc=Document(root=entry,reqManager=self)
		req=http.HTTPRequest(str(feedURL),"POST",unicode(doc).encode('utf-8'))
		mtype=http.HTTPMediaType()
		mtype.SetMimeType(atom.ATOM_MIMETYPE)
		mtype.parameters['charset']=('Charset','utf-8')
		req.SetHeader("Content-Type",mtype)
		self.ProcessRequest(req)
		if req.status==201:
			newDoc=Document()
			e=xml.XMLEntity(req.response)
			newDoc.ReadFromEntity(e)
			if isinstance(newDoc.root,atom.Entry):
				return newDoc.root
			else:
				raise InvalidEntryDocument(str(entryURL))
		else:
			raise UnexpectedHTTPResponse("%i %s"%(req.status,req.response.reason))	
			
	def RetrieveEntry(self,entryURL):
		"""Given an entryURL URL, returns the :py:class:`Entry` instance"""
		doc=Document(baseURI=entryURL,reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Entry):
			self.AssociateEntityType(doc.root)
			return doc.root
		else:
			raise InvalidEntryDocument(str(entryURL))
			
	def _AddParams(self,baseURL,odataQuery=None):
		if baseURL.query is None:
			query={}
		else:
			query=cgi.parse_qs(baseURL.query)
		if self.pageSize:
			query["$top"]=str(self.pageSize)
		if odataQuery:
			for k in odataQuery.keys():
				query[k]=odataQuery[k]
		if query:
			if baseURL.absPath is None:
				raise InvalidFeedURL(str(baseURL))
			return uri.URIFactory.Resolve(baseURL,baseURL.absPath+"?"+urllib.urlencode(query))
		else:
			return baseURL

	def QueueRequest(self,request):
		request.SetHeader('Accept','application/xml')
		request.SetHeader('DataServiceVersion','2.0; pyslet %s'%info.version)
		request.SetHeader('MaxDataServiceVersion','2.0; pyslet %s'%info.version)
		app.Client.QueueRequest(self,request)


class Error(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'error')
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Code=Code(self)
		self.Message=Message(self)
		self.InnerError=None
	
	def GetChildren(self):
		yield self.Code
		yield self.Message
		if self.InnerError: yield self.InnerError

	def JSONDict(self):
		"""Returns a dictionary representation of this object."""
		d={}
		d['code']=self.Code.GetValue()
		d['message']=self.Message.GetValue()
		if self.InnerError:
			d['innererror']=self.InnerError.GetValue()
		return {'error':d}


class Code(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'code')
	
class Message(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'message')
	
class InnerError(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'innererror')


class ODataJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if hasattr(obj,'JSONDict'):
			return obj.JSONDict()
		else:
			return json.JSONEncoder.default(self, obj)	


class WSGIWrapper(object):
	def __init__(self,environ,start_response,responseHeaders):
		"""A simple wrapper class for a wsgi application.
		
		Allows additional responseHeaders to be added to the wsgi response."""
		self.environ=environ
		self.start_response=start_response
		self.responseHeaders=responseHeaders
	
	def call(self,application):
		"""Calls wsgi *application*"""
		return application(self.environ,self.start_response_wrapper)

	def start_response_wrapper(self,status,response_headers,exc_info=None):
		"""Traps the start_response callback and adds the additional headers."""
		response_headers=response_headers+self.responseHeaders
		return self.start_response(status,response_headers,exc_info)

		
class Server(app.Server):
	"""Extends py:class:`pyselt.rfc5023.Server` to provide an OData server.
	
	We do some special processing of the serviceRoot before passing it to the
	parent construtor as in OData it cannot end in a trailing slash.  If it
	does, we strip the slash from the root and use that as our OData service
	root.
	
	But... we always pass a URI with a trailing slash to the parent constructor
	following the example set by http://services.odata.org/OData/OData.svc and
	issue a temporary redirect when we receive requests for the OData service
	root to the OData URI consisting of the service root + a resource path
	consisting of a single '/'.
	
	This makes the links in the service document much clearer and easier to
	generate but more importantly, it deals with the awkward case of a service
	root consisting of just scheme and authority (e.g., http://odata.example.com
	).  This type of servie root cannot be obtained with a simple HTTP request
	as the trailing '/' is implied (and no redirection is necessary)."""
	
	DefaultAcceptList=http.AcceptList("application/atom+xml, application/xml; q=0.9, text/xml; q=0.8, text/plain; q=0.7, application/octet-stream; q=0.6")
	ErrorTypes=[
		http.MediaType('application/atom+xml'),
		http.MediaType('application/xml'),
		http.MediaType('application/json')]
	
	RedirectTypes=[
		http.MediaType('text/html'),
		http.MediaType('text/plain')]
			
	FeedTypes=[		# in order of preference if there is a tie
		http.MediaType('application/atom+xml'),
		http.MediaType('application/atom+xml;type=feed'),
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
	
	EntryTypes=[	# in order of preference if there is a tie
		http.MediaType('application/atom+xml'),
		http.MediaType('application/atom+xml;type=entry'),
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
			
	ValueTypes=[	# in order of preference if there is a tie
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
	
	MetadataTypes=[	# in order of preference if there is a tie
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('text/plain')]
	
	DereferenceTypes=[	# in order of preference
		http.MediaType('text/plain;charset=utf-8'),
		http.MediaType('application/octet-stream'),
		http.MediaType('octet/stream')]		# we allow this one in case someone read the spec literally!
		
	StreamTypes=[
		http.MediaType('application/octet-stream'),
		http.MediaType('octet/stream')]		# we allow this one in case someone read the spec literally!

	def __init__(self,serviceRoot="http://localhost"):
		if serviceRoot[-1]!='/':
			serviceRoot=serviceRoot+'/'
		app.Server.__init__(self,serviceRoot)
		if self.serviceRoot.relPath is not None:
			# The service root must be absolute (or missing completely)!
			raise ValueError("serviceRoot must not be relative")
		if self.serviceRoot.absPath is None:
			self.pathPrefix=''
		else:
			self.pathPrefix=self.serviceRoot.absPath
		# pathPrefix must not have a tailing slash, even if this makes it an empty string
		if self.pathPrefix[-1]=='/':
			self.pathPrefix=self.pathPrefix[:-1]		
		self.ws=self.service.ChildElement(app.Workspace)	#: a single workspace that contains all collections
		self.ws.ChildElement(atom.Title).SetValue("Default")
		self.model=None					#: a :py:class:`pyslet.mc_edmx.Edmx` instance containing the model for the service
		self.defaultContainer=None		#: the default entity container
		
	def SetModel(self,model):
		"""Sets the model for the server from a parentless
		:py:class:`pyslet.mc_edmx.Edmx` instance or an Edmx
		:py:class:`pyslet.mc_edmx.Document` instance."""
		if isinstance(model,edmx.Document):
			model=model.root
		elif isinstance(model,edmx.Edmx):
			# create a document to hold the model
			doc=edmx.Document(root=model)
		else:
			raise TypeError("Edmx document or instance required for model")
		if self.model:
			# get rid of the old model
			for c in self.ws.Collection:
				c.DetachFromDocument()
				c.parent=None
			self.ws.Collection=[]
			self.defaultContainer=None
		for s in model.DataServices.Schema:
			for container in s.EntityContainer:
				# is this the default entity container?
				prefix=container.name+"."
				try:
					if container.GetAttribute(IsDefaultEntityContainer)=="true":
						prefix=""
						self.defaultContainer=container
				except KeyError:
					pass
				# define one feed for each entity set, prefixed with the name of the entity set
				for es in container.EntitySet:
					feed=self.ws.ChildElement(app.Collection)
					feed.href=prefix+es.name
					feed.ChildElement(atom.Title).SetValue(prefix+es.name)
		self.model=model
		
	def __call__(self,environ, start_response):
		"""wsgi interface for the server."""
		responseHeaders=[]
		try:
			result=self.CheckCapabilityNegotiation(environ,start_response,responseHeaders)
			if result is None:
				request=ODataURI(environ['PATH_INFO'],self.pathPrefix)
				if request.resourcePath is None:
					# this is not a URI for us, pass to our superclass
					wrapper=WSGIWrapper(environ,start_response,responseHeaders)
					# super essentially allows us to pass a bound method of our parent
					# that we ourselves are hiding.
					return wrapper.call(super(Server,self).__call__)
				elif request.resourcePath=='':
					# An empty resource path means they hit the service root, redirect
					location=str(self.serviceRoot)
					r=html.HTML(None)
					r.Head.Title.SetValue('Redirect')
					div=r.Body.ChildElement(html.Div)
					div.AddData(u"Moved to: ")
					anchor=div.ChildElement(html.A)
					anchor.href=self.serviceRoot
					anchor.SetValue(location)
					responseType=self.ContentNegotiation(environ,self.RedirectTypes)
					if responseType is None:
						# this is a redirect response, default to text/plain anyway
						responseType=http.MediaType('text/plain')
					if responseType=="text/plain":
						data=r.RenderText()
					else:
						data=str(r)
					responseHeaders.append(("Content-Type",str(responseType)))
					responseHeaders.append(("Content-Length",str(len(data))))
					responseHeaders.append(("Location",location))
					start_response("%i %s"%(307,"Temporary Redirect"),responseHeaders)
					return [data]
				else:
					return self.HandleRequest(request,environ,start_response,responseHeaders)
			else:
				return result
		except ValueError,e:
			traceback.print_exception(*sys.exc_info())
			# This is a bad request
			return HandleODataError(environ,start_response,"ValueError",str(e))
		except:
			traceback.print_exception(*sys.exc_info())
			return self.HandleError(environ,start_response)

	def ODataError(self,environ,start_response,subCode,message='',code=400):
		"""Generates and ODataError, typically as the result of a bad request."""
		responseHeaders=[]
		e=Error(None)
		e.ChildElement(Code).SetValue(subCode)
		e.ChildElement(Message).SetValue(message)
		responseType=self.ContentNegotiation(environ,self.ErrorTypes)
		if responseType is None:
			# this is an error response, default to text/plain anyway
			responseType=http.MediaType('text/plain')
		elif responseType=="application/atom+xml":
			# even if you didn't ask for it, you get application/xml in this case
			responseType="application/xml"
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			data=str(e)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(code,subCode),responseHeaders)
		return [data]
		
	def HandleRequest(self,requestURI,environ,start_response,responseHeaders):
		"""Handles a request that has been identified as being an OData request.
		
		*	*requestURI* is an :py:class:`ODataURI` instance with a non-empty resourcePath."""
		focus=None
		METADATA=1
		LINKS=2
		VALUE=3
		BATCH=4
		COUNT=5
		control=None
		path=[]
		try:
			for component in requestURI.navPath:
				name,keyPredicate=component
				if control==VALUE:
					# bad request, because $value must be the last thing in the path
					raise BadURISegment("%s since the object's parent is a dereferenced value"%name)							
				elif control==METADATA:
					# bad request, because $metadata must be the only thing in the path
					raise BadURISegment("%s since $metadata must be the only path component"%name)													
				elif control==BATCH:
					# bad request, because $batch must be the only thing in the path
					raise BadURISegment("%s since $batch must be the only path component"%name)
				elif control==COUNT:
					# bad request, because $count must be the only thing in the path
					raise BadURISegment("%s since $count must be the last path component"%name)																		
				if focus is None:
					es=None
					if name=='$metadata':
						control=METADATA
						continue
					elif name=='$batch':
						control=BATCH
						continue
					elif name in self.defaultContainer:
						es=self.defaultContainer[name]
					else:
						for s in self.model.DataServices.Schema:
							if name in s:
								es=s[name]
								container=es.FindParent(edm.EntityContainer)
								if container is self.defaultContainer:
									es=None
								break
					if isinstance(es,edm.FunctionImport) and es.IsEntityCollection():
						# TODO: grab the params from the query string
						params={}
						es=es.Execute(params)	
					if isinstance(es,edm.EntitySet) or isinstance(es,edm.FunctionEntitySet):
						if keyPredicate:
							# the keyPredicate can be passed directly as the key
							try:
								focus=es[keyPredicate]
								path=["%s(%s)"%(es.name,repr(focus.Key()))]
							except KeyError,e:
								raise MissingURISegment(name)
						else:
							# return this entity set
							focus=es
							path.append(es.name)
					else:
						# Attempt to use the name of some other object type, bad request
						raise MissingURISegment(name)
				elif isinstance(focus,edm.EntitySet) or isinstance(focus,edm.DynamicEntitySet):
					if name=="$count":
						control=COUNT
						continue
					else:
						# bad request, because the collection must be the last thing in the path
						raise BadURISegment("%s since the object's parent is a collection"%name)
				elif isinstance(focus,edm.Entity):
					if name in focus:
						if control:
							raise BadURISegment(name)
						# This is just a regular or dynamic property name
						focus=focus[name]
						path.append(name)
					elif name.startswith("$"):
						if control:
							raise BadURISegment(name)
						if name=="$links":
							control=LINKS
						elif name=="$count":
							control=COUNT
						elif name=="$value":
							hasStream=focus.typeDef.GetNSAttribute((ODATA_METADATA_NAMESPACE,'HasStream'))
							hasStream=(hasStream and hasStream.lower()=="true")
							if hasStream:
								control=VALUE
							else:
								raise BadURISegment("%s since the entity is not a media stream"%name)
						else:
							raise BadURISegment(name)
					else:
						if control and control!=LINKS:
							raise BadURISegment("unexpected segment %s after system path component"%name)							
						try:
							# should be a navigation property
							if focus.IsEntityCollection(name):
								es=focus.Navigate(name)
								if keyPredicate:
									if control==LINKS:
										raise BadURISegment(name)
									try:
										focus=es[keyPredicate]
										path=["%s(%s)"%(es.name,repr(focus.Key()))]
									except KeyError,e:
										raise MissingURISegment(name)
								else:
									# return this entity set
									focus=es
									path.append(es.name)
							else:
								focus=focus.Navigate(name)
								# should be None or a specific entity this time
								if focus is None:
									raise MissingURISegment(name)
								elif keyPredicate:
									if control==LINKS:
										raise BadURISegment(name)
									# the key must match that of the entity
									if focus.Key()!=keyPredicate:
										raise MissingURISegment(name)
								path=["%s(%s)"%(focus.entitySet.name,repr(focus.Key()))]
						except KeyError:
							raise MissingURISegment(name)
				elif isinstance(focus,edm.Complex):
					if name in focus:
						# This is a regular property of the ComplexType
						focus=focus[name]
						path.append(name)
					elif name=="$value":
						raise NotImplementedError("$value")
					else:
						raise MissingURISegment(name)
				else:
					# Any other type is just a property or simple-type
					if name=="$value":
						control=VALUE
					else:
						raise BadURISegment(name)
			path=string.join(path,'/')
		except MissingURISegment,e:
			return self.ODataError(environ,start_response,"Bad Request","Resource not found for component %s"%str(e),404)
		except BadURISegment,e:
			return self.ODataError(environ,start_response,"Bad Request","Resource not found for component %s"%str(e),400)
		if control==METADATA:
			return self.ReturnMetadata(environ,start_response,responseHeaders)
		elif control==BATCH:
			return self.ODataError(environ,start_response,"Bad Request","Batch requests not supported",404)
		elif isinstance(focus,edm.Entity):
			if control==COUNT:
				return self.ReturnCount(1,environ,start_response,responseHeaders)
			elif control==LINKS:
				return self.ReturnLink(focus,environ,start_response,responseHeaders)				
			elif control==VALUE:
				return self.ReturnStream(focus,environ,start_response,responseHeaders)								
			else:
				return self.ReturnEntity(path,focus,environ,start_response,responseHeaders)
		elif isinstance(focus,edm.EDMValue):
			if control==VALUE:
				return self.ReturnDereferencedValue(focus,environ,start_response,responseHeaders)
			else:
				return self.ReturnValue(focus,environ,start_response,responseHeaders)
		elif isinstance(focus,edm.EntitySet) or isinstance(focus,edm.DynamicEntitySet):
			if control==COUNT:
				return self.ReturnCount(len(focus),environ,start_response,responseHeaders)
			elif control==LINKS:
				return self.ReturnLinks(focus,environ,start_response,responseHeaders)				
			else:
				return self.ReturnCollection(path,focus,environ,start_response,responseHeaders)
		elif focus is not None:
			raise NotImplementedError("property value or media resource")
		else:	
			# an empty navPath means we are trying to get the service root
			wrapper=WSGIWrapper(environ,start_response,responseHeaders)
			# super essentially allows us to pass a bound method of our parent
			# that we ourselves are hiding.
			return wrapper.call(super(Server,self).__call__)
	
	def ReturnMetadata(self,environ,start_response,responseHeaders):
		doc=self.model.GetDocument()
		responseType=self.ContentNegotiation(environ,self.MetadataTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml or plain text formats supported',406)
		data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
			
	def ReturnLinks(self,entities,environ,start_response,responseHeaders):
		doc=Document(root=Links)
		for e in entities.itervalues():
			child=doc.root.ChildElement(URI)
			child.SetValue(str(self.serviceRoot)+"%s(%s)"%(e.entitySet.name,repr(e.Key())))
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(links,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
		
	def ReturnLink(self,entity,environ,start_response,responseHeaders):
		doc=Document(root=URI)
		doc.root.SetValue(str(self.serviceRoot)+"%s(%s)"%(entity.entitySet.name,repr(entity.Key())))
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(doc.root,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
			
	def ReturnCollection(self,path,entities,environ,start_response,responseHeaders):
		"""Returns an iterable of Entities."""
		doc=Document(root=atom.Feed)
		f=doc.root
		#f.MakePrefix(ODATA_DATASERVICES_NAMESPACE,u'd')
		#f.MakePrefix(ODATA_METADATA_NAMESPACE,u'm')
		f.SetBase(str(self.serviceRoot))
		# f.ChildElement(atom.Title).SetValue(entities.GetTitle())
		f.ChildElement(atom.AtomId).SetValue(str(self.serviceRoot)+path)
		# f.ChildElement(atom.Updated).SetValue(entities.GetUpdated())
		for e in entities.itervalues():
			entry=f.ChildElement(atom.Entry)
			entry.ChildElement(atom.AtomId).SetValue(str(self.serviceRoot)+"%s(%s)"%(e.entitySet.name,repr(e.Key())))		
		# do stuff with the entries themselves, add link elements etc
		responseType=self.ContentNegotiation(environ,self.FeedTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(f,cls=ODataJSONEncoder)
		else:
			# Here's a challenge, we want to pull data through the feed by yielding strings
			# just load in to memory at the moment
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnEntity(self,path,entity,environ,start_response,responseHeaders):
		"""Returns a single Entity."""
		doc=Document(root=Entry)
		e=doc.root
		e.SetBase(str(self.serviceRoot))
		e.ChildElement(atom.AtomId).SetValue(str(self.serviceRoot)+path)
		e.SetValue(entity)
		# TODO: do stuff with the entries themselves, add link elements etc
		responseType=self.ContentNegotiation(environ,self.EntryTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			# Here's a challenge, we want to pull data through the feed by yielding strings
			# just load in to memory at the moment
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]

	def ReturnStream(self,entity,environ,start_response,responseHeaders):
		"""Returns a media stream."""
		types=[entity.entitySet.GetStreamType(entity)]+self.StreamTypes
		responseType=self.ContentNegotiation(environ,types)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'media stream type refused, try application/octet-stream',406)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",entity.entitySet.GetStreamSize(entity)))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return entity.entitySet.GetStreamGenerator(entity)

	def ReturnValue(self,value,environ,start_response,responseHeaders):
		"""Returns a single property value."""
		e=Property(None)
		e.SetXMLName((ODATA_DATASERVICES_NAMESPACE,value.name))
		doc=Document(root=e)
		e.SetValue(value)
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnDereferencedValue(self,value,environ,start_response,responseHeaders):
		"""Returns a dereferenced property value."""
		responseType=self.ContentNegotiation(environ,self.DereferenceTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'$value requires plain text or octet-stream formats',406)
		data=unicode(value).encode('utf-8')
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnCount(self,number,environ,start_response,responseHeaders):
		"""Returns the single value number."""
		responseType=self.ContentNegotiation(environ,self.DereferenceTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'$count requires plain text or octet-stream formats',406)
		data=str(number)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ContentNegotiation(self,environ,mTypeList):
		"""Given a list of media types, examines the Accept header and returns the best match.
		
		If there is no match then None is returned."""
		if "HTTP_Accept" in environ:
			try:
				aList=http.AcceptList(environ["HTTP_Accept"])
			except http.HTTPParameterError:
				# we'll treat this as a missing Accept header
				aList=self.DefaultAcceptList
		else:
			aList=self.DefaultAcceptList
		return aList.SelectType(mTypeList)
			
	def CheckCapabilityNegotiation(self,environ,start_response,responseHeaders):
		"""Sets the protocol version in *responseHeaders* if we can handle this request.
		
		Returns None if the application should continue to handle the request, otherwise
		it returns an iterable object suitable for the wsgi return value.
		
		*	responseHeaders is a list which contains the proposed response headers.

		In the event of a protocol version mismatch a "400 DataServiceVersion
		mismatch" error response is generated."""
		ua=sa=None
		if "HTTP_DataServiceVersion" in environ:
			major,minor,ua=ParseDataServiceVersion(environ["HTTP_DataServiceVersion"])
		else:
			major=2
			minor=0
		if "HTTP_MaxDataServiceVersion" in environ:
			maxMajor,maxMinor,sa=ParseMaxDataServiceVersion(environ["HTTP_MaxDataServiceVersion"])
		else:
			maxMajor=major
			maxMinor=minor
		if major>2 or (major==2 and minor>0):
			# we can't cope with this request
			return self.ODataError(environ,start_response,"DataServiceVersionMismatch","Maximum supported protocol version: 2.0")
		if maxMajor>=2:
			responseHeaders.append(('DataServiceVersion','2.0; pyslet %s'%info.version))
		else:
			responseHeaders.append(('DataServiceVersion','1.0; pyslet %s'%info.version))
		return None
			
	
class Document(app.Document):
	"""Class for working with OData documents."""
	classMap={}
	
	def __init__(self,**args):
		app.Document.__init__(self,**args)
		self.MakePrefix(ODATA_METADATA_NAMESPACE,'m')
		self.MakePrefix(ODATA_DATASERVICES_NAMESPACE,'d')
	
	def GetElementClass(self,name):
		"""Returns the OData, APP or Atom class used to represent name.
		
		Overrides :py:meth:`~pyslet.rfc5023.Document.GetElementClass` to allow
		custom implementations of the Atom or APP classes to be created and
		to cater for OData-specific elements."""
		result=Document.classMap.get(name,None)
		if result is None:
			if name[0]==ODATA_DATASERVICES_NAMESPACE:
				result=Property
			else:
				result=app.Document.GetElementClass(self,name)
		return result


class ODataStoreClient(edm.ERStore):
	"""Provides an implementation of ERStore based on OData."""

	def __init__(self,serviceRoot=None):
		edm.ERStore.__init__(self)
		self.client=Client(serviceRoot)
		self.defaultContainer=None		#: the default entity container
		for s in self.client.schemas:
			# if the client has a $metadata document we'll use it
			schema=self.client.schemas[s]
			self.AddSchema(schema)
			# search for the default entity container
			for container in schema.EntityContainer:
				try:
					if container.GetAttribute(IsDefaultEntityContainer)=="true":
						if self.defaultContainer is None:
							self.defaultContainer=container
						else:
							raise InvalidMetadataDocument("Multiple default entity containers defined")
				except KeyError:
					pass									
				
	def EntityReader(self,entitySetName):
		"""Iterates over the entities in the given entity set (feed)."""
		feedURL=None
		if self.defaultContainer:
			if entitySetName in self.defaultContainer:
				# use this as the name of the feed directly
				# get the entity type from the entitySet definition
				entitySet=self.defaultContainer[entitySetName]
				entityType=self[entitySet.entityTypeName]
				feedURL=uri.URIFactory.Resolve(self.client.serviceRoot,entitySetName)
		if feedURL is None:
			raise NotImplementedError("Entity containers other than the default") 
		for entry in self.client.RetrieveEntries(feedURL):
			values={}
			for p in entityType.Property:
				v=entry[p.name]
				values[p.name]=v
			yield values

			
xmlns.MapClassElements(Document.classMap,globals())