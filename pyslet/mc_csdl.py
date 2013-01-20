#! /usr/bin/env python
"""This module implements the CSDL specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541211.aspx
http://msdn.microsoft.com/en-us/library/dd541474(v=prot.10)"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.rfc2396 as uri
import pyslet.xsdatatypes20041028 as xsi
from pyslet.vfs import OSFilePath

import string, itertools, sqlite3, hashlib, StringIO, time, sys
from types import StringTypes, StringType, UnicodeType, IntType, LongType


EDM_NAMESPACE="http://schemas.microsoft.com/ado/2009/11/edm"		#: Namespace to use for CSDL elements

EDM_NAMESPACE_ALIASES={
	EDM_NAMESPACE: [
		"http://schemas.microsoft.com/ado/2006/04/edm",		#: CSDL Schema 1.0
		"http://schemas.microsoft.com/ado/2007/05/edm",		#: CSDL Schema 1.1
		"http://schemas.microsoft.com/ado/2008/09/edm"]		#: CSDL Schema 2.0
	}


SimpleIdentifierRE=xsi.RegularExpression(r"[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")

def ValidateSimpleIdentifier(identifier):
	"""Validates a simple identifier, returning the identifier unchanged or
	raising ValueError."""
	if SimpleIdentifierRE.Match(identifier):
		return identifier
	else:
		raise ValueError("Can't parse SimpleIdentifier from :%s"%repr(identifier))


class DuplicateName(Exception):
	"""Raised by :py:class:`NameTableMixin` when attempting to declare a name in
	a context where the name is already declared."""
	pass


class IncompatibleNames(DuplicateName):
	"""A special type of :py:class:`DuplicateName` exception raised by
	:py:class:`NameTableMixin` when attempting to declare a name which
	might hide, or be hidden by, another name already declared.
	
	CSDL's definition of SimpleIdentifier allows '.' to be used in names but
	also uses it for qualifying names.  As a result, it is possible to define a
	scope with a name like "My.Scope" which precludes the later definition of a
	scope called simply "My" (and vice versa)."""
	pass


class ContainerExists(Exception):
	"""Raised by :py:meth:`ERStore.CreateContainer` when the container already
	exists."""
	pass


class StorageError(Exception): pass


class NameTableMixin(object):
	"""A mix-in class to help other objects become named scopes.
	
	Using this mix-in the class behaves like a named dictionary with string keys
	and object value.  If the dictionary contains a value that is itself a
	NameTableMixin then keys can be compounded to look-up items in
	sub-scopes.
	
	For example, if the name table contains a value with key "X"
	that is itself a name table containing a value with key "Y" then both "X"
	and "X.Y" are valid keys."""
	
	def __init__(self):
		self.name=""			#: the name of this name table (in the context of its parent)
		self.nameTable={}		#: a dictionary mapping names to child objects
	
	def __len__(self):
		"""Returns the total number of names in this scope, including the sum of
		the lengths of all child scopes."""
		count=len(self.nameTable)
		for value in self.nameTable.itervalues():
			if isinstance(value,NameTableMixin):
				count=count+len(value)
		return count
	
	def SplitKey(self,key):
		sKey=key.split(".")
		pathLen=1
		while pathLen<len(sKey):
			scope=self.nameTable.get(string.join(sKey[:pathLen],"."),None)
			if isinstance(scope,NameTableMixin):
				return scope,string.join(sKey[pathLen:],".")
			pathLen+=1
		return None,key
		
	def __getitem__(self,key):
		"""Looks up *key* in :py:attr:`nameTable` and, if not found, in each
		child scope with a name that is a valid scope prefix of key.  For
		example, if key is "My.Scope.Name" then a child scope with name
		"My.Scope" would be searched for "Name" or a child scope with name "My"
		would be searched for "Scope.Name"."""
		result=self.nameTable.get(key,None)
		if result is None:
			scope,key=self.SplitKey(key)
			if scope is not None:
				return scope[key]
			raise KeyError("%s not declared in scope %s"%(key,self.name))					
		else:
			return result
			
	def __setitem__(self,key,value):
		"""Raises NotImplementedError.
		
		To add items to the name table you must use the :py:meth:`Declare` method."""
		raise NotImplementedError

	def Declare(self,value):
		"""Declares a value in this name table.
		
		*value* must have a name attribute which is used to declare it in the
		name table; duplicate keys are not allowed and will raise
		:py:class:`DuplicateKey`.

		Values are always declared in the top-level name table, even if they
		contain the compounding character '.', however, you cannot declare "X"
		if you have already declared "X.Y" and vice versa."""
		if value.name in self.nameTable:
			raise DuplicateName("%s already declared in scope %s"%(value.name,self.name))
		prefix=value.name+"."
		for key in self.nameTable:
			if key.startswith(prefix) or value.name.startswith(key+"."):
				# Can't declare "X.Y" if "X.Y.Z" exists already and
				# Can't declare "X.Y.Z" if "X.Y" exists already
				raise IncompatibleNames("Can't declare %s; %s already declared in scope %s"%(value.name,key,self.name))
		self.nameTable[value.name]=value
	
	def Undeclare(self,value):
		"""Removes a value from the name table."""
		if value.name in self.nameTable:
			del self.nameTable[value.name]
		else:
			raise KeyError("%s not declared in scope %s"%(value.name,self.name))
		
	def __delitem__(self,key):
		"""Raises NotImplementedError.
		
		To remove a name from the name table you must use the
		:py:meth:`Undeclare` method."""
		raise NotImplementedError
	
	def __iter__(self):
		for key in self.nameTable:
			yield key
		for value in self.nameTable.itervalues():
			if isinstance(value,NameTableMixin):
				for key in value:
					yield value.name+"."+key
				
	def __contains__(self,key):
		result=self.nameTable.get(key,None)
		if result is None:
			scope,key=self.SplitKey(key)
			if scope is not None:
				return key in scope
			return False					
		else:
			return True
	
	iterkeys=__iter__

	def keys(self):
		return list(self.iterkeys())

	def itervalues(self):
		for value in self.nameTable.itervalues():
			yield value
		for value in self.nameTable.itervalues():
			if isinstance(value,NameTableMixin):
				for v in value:
					yield v
	
	def values(self):
		return list(self.itervalues())

	def iteritems(self):
		for item in self.nameTable.iteritems():
			yield item
		for value in self.nameTable.itervalues():
			if isinstance(value,NameTableMixin):
				for item in value.iteritems():
					yield value.name+"."+item[0],item[1]

	def items(self):
		return list(self.iteritems())
	
	def has_key(self,key):
		return key in self
	
	def get(self,key,default=None):
		try:
			return self[key]
		except KeyError:
			return default
	
	def clear(self):
		raise NotImplementedError

	def setdefault(self,k,x=None):
		raise NotImplementedError
	
	def pop(self,k,x=None):
		raise NotImplementedError

	def popitem(self):
		raise NotImplementedError
		
	def copy(self):	
		raise NotImplementedError

	def update(self):
		raise NotImplementedError


class SimpleType(xsi.Enumeration):
	"""SimpleType defines constants for the core data types defined by CSDL
	::
		
		SimpleType.boolean	
		SimpleType.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'Edm.Binary':1,
		'Edm.Boolean':2,
		'Edm.Byte':3,
		'Edm.DateTime':4,
		'Edm.DateTimeOffset':5,
		'Edm.Time':6,
		'Edm.Decimal':7,
		'Edm.Double':8,
		'Edm.Single':9,
		'Edm.Guid':10,
		'Edm.Int16':11,
		'Edm.Int32':12,
		'Edm.Int64':13,
		'Edm.String':14,
		'Edm.SByte':15
		}
xsi.MakeEnumeration(SimpleType)
xsi.MakeEnumerationAliases(SimpleType,{
	'Binary':'Edm.Binary',
	'Boolean':'Edm.Boolean',
	'Byte':'Edm.Byte',
	'DateTime':'Edm.DateTime',
	'Decimal':'Edm.Decimal',
	'Double':'Edm.Double',
	'Single':'Edm.Single',
	'Guid':'Edm.Guid',
	'Int16':'Edm.Int16',
	'Int32':'Edm.Int32',
	'Int64':'Edm.Int64',
	'SByte':'Edm.SByte',
	'String':'Edm.String',
	'Time':'Edm.Time',
	'DateTimeOffset':'Edm.DateTimeOffset'})
xsi.MakeLowerAliases(SimpleType)
	
"""
String allows any sequence of UTF-8 characters.
Int allows content in the following form: [-] [0-9]+.
Decimal allows content in the following form: [0-9]+.[0-9]+M|m.
"""

def DecodeBinary(value):
	"""Binary allows content in the following form: [A-Fa-f0-9][A-Fa-f0-9]*.

	String types are parsed from hex strings as per the above format, everything
	else is converted to a unicode string and is then encoded with utf-8.

	The result is always a byte string."""
	if type(value) in StringTypes:
		input=StringIO.StringIO(value)
		output=StringIO.StringIO()
		while True:
			hexString=''
			while len(hexString)<2:			
				hexByte=input.read(1)
				if len(hexByte):
					if uri.IsHex(hexByte):
						hexString=hexString+hexByte
					elif xmlns.IsS(hexByte):
						# generous in ignoring spaces
						continue
					else:
						raise ValueError("Illegal character in binary string: %s"%repr(hexByte))
				elif len(hexString)==1:
					raise ValueError("Odd hex-digit found in binary string")
				else:
					break
			if hexString:
				output.write(chr(int(hexString,16)))
			else:
				break
			return output.getvalue()
	else:
		raise ValueError("String type required: %s"%repr(value))

def EncodeBinary(value):
	"""If value is a binary string, outputs a unicode string containing a hex representation.
	
	If value is a unicode string then it is assumed to be a hex string and is validated
	as such."""
	if type(value) is not StringType:
		if type(value) is UnicodeType:
			value=DecodeBinary(value)
		else:
			ValueError("String or Unicode type required: %s"%repr(value))
	input=StringIO.StringIO(value)
	output=StringIO.StringIO()
	while True:
		byte=input.read(1)
		if len(byte):
			output.write("%2X"%ord(byte))
		else:
			break
	return unicode(output.getvalue())


def DecodeBoolean(value):
	"""Bool allows content in the following form: true | false.

	The result is always one of True or False."""
	if type(value) in StringTypes:
		sValue=value.strip().lower()
		if sValue=="true":
			return True
		elif sValue=="false":
			return False
		else:
			raise ValueError("Illegal value for Edm.Boolean: %s"%value)
	else:
		raise ValueError("String type required: %s"%repr(value))
		

def EncodeBoolean(value):
	"""Returns one of 'true' or 'false'.
	
	String types are decoded, other types are tested for non-zero."""
	if type(value) in StringTypes:
		value=DecodeBoolean(value)
	if value:
		return u"true"
	else:
		return u"false"


def DecodeByte(value):
	"""Special case of int; Int allows content in the following form: [-] [0-9]+.
	
	String types are parsed using XML schema's rules, everything else is
	coerced to int using Python's built-in function.
	
	Values outside of the allowable range for byte [0-255] raise ValueError.
	
	The result is a python int."""
	if type(value) in StringTypes:
		byteValue=xsi.DecodeInteger(value)
	else:
		byteValue=int(value)
	if byteValue<0 or byteValue>255:
		raise ValueError("Illegal value for byte: %i"%byteValue)
	return byteValue	 

def EncodeByte(value):
	"""Returns a unicode string representation of *value*"""
	return xsi.EncodeInteger(value)


def DecodeDateTime(value):
	"""DateTime allows content in the following form: yyyy-mm-ddThh:mm[:ss[.fffffff]].
	
	The result is an :py:class:`iso8601.TimePoint` instance representing a time
	with an unspecified zone.  If a zone is given then ValueError is raised.
	
	If value is numeric it is treated as a unix time."""
	if type(value) in StringTypes:
		dtValue=iso8601.TimePoint(value)
		zDir,zOffset=dtValue.GetZone()
		if zOffset is not None:
			raise ValueError("Timezone offset not allowed in DateTime value: %s"%value)
	else:
		try:
			uValue=float(value)
			if uValue>0:
				dtValue=iso8601()
				dtValue.SetUnixTime(uValue)
				dtValue.SetZone(None)
			else:
				raise ValueError("Can't parse DateTime from negative value: %f"%uValue)
		except:
			raise ValueError("Can't parse DateTime value from: %s"%repr(value))
	return dtValue

def EncodeDateTime(value):
	"""Returns a unicode string representation of *value* which must be an
	:py:class:`iso8601.TimePoint` instance."""
	return unicode(value)


def DecodeDateTimeOffset(value):
	"""DateTimeOffset allows content in the following form: yyyy-mm-ddThh:mm[:ss[.fffffff]] zzzzzz.
	
	The result is an :py:class:`iso8601.TimePoint` instance representing a time
	with a specified zone.
	
	If value is numeric it is treated as a unix time with zero offset."""
	if type(value) in StringTypes:
		# remove the extra space that appears in this format
		dValue=string.join(string.split(value),'')
		dtValue=iso8601.TimePoint(value)
		zDir,zOffset=dtValue.GetZone()
		if zOffset is None:
			raise ValueError("Timezone offset required in DateTimeOffset value: %s"%value)
	else:
		try:
			uValue=float(value)
			if uValue>0:
				dtValue=iso8601()
				dtValue.SetUnixTime(uValue)
			else:
				raise ValueError("Can't parse DateTimeOffset from negative value: %f"%uValue)
		except:
			raise ValueError("Can't parse DateTimeOffset value from: %s"%repr(value))
	return dtValue

def EncodeDateTimeOffset(value):
	"""Returns a unicode string representation of *value* which must be an
	:py:class:`iso8601.TimePoint` instance."""
	zStr=dtValue.time.GetZoneString()
	if zStr=="Z":
		# not clear if they support the Z form of the timezone offset, use numbers for safety
		zStr="+00:00"
	dtValue.SetZone(None)		
	return string.join((unicode(value),zStr),' ')


def DecodeGuid(value):
	"""Guid allows content in the following form:
	dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents [A-Fa-f0-9].
	
	Returns a built-in python uuid.UUID instance, unicode strings are passed
	directly to UUID's constructor.  Non-unicode strings with length<32 are
	passed as binary bytes, otherwise they are passed has hex.  If value is
	an integer it is passed as an int to the constructor."""
	if type(value) is UnicodeType:
		return uuid.UUID(value)
	elif type(value) is StringType:
		if len(value)<32:
			return uuid.UUID(bytes=value)
		else:
			return uuid.UUID(value)
	elif type(value) in (IntType,LongType):
		return uuid.UUID(int=value)
	else:
		raise ValueError("Can't declde Guid from %s"%repr(value))

def EncodeGuid(value):
	"""Returns a unicode representation of *value* which must be a python UUID
	instance or something that can be passed to DecodeGuid to create one."""
	if isinstance(value,uuid.UUID):
		return unicode(value)
	else:
		return unicode(DecodeGuid(value))

		
def DecodeInt16(value):
	"""Special case of int; Int allows content in the following form: [-] [0-9]+.
	
	String types are parsed using XML schema's rules, everything else is
	coerced to int using Python's built-in function.
	
	Values outside of the allowable range for int16 [-32768,32767] raise ValueError.
	
	The result is a python int."""
	if type(value) in StringTypes:
		int16Value=xsi.DecodeInteger(value)
	else:
		int16Value=int(value)
	if int16Value<-32768 or int16Value>32767:
		raise ValueError("Illegal value for int16: %i"%int16Value)
	return int16Value	 

def EncodeInt16(value):
	"""Returns a unicode string representation of *value*"""
	return xsi.EncodeInteger(value)


def DecodeInt32(value):
	"""Special case of int; Int allows content in the following form: [-] [0-9]+.
	
	String types are parsed using XML schema's rules, everything else is
	coerced to int using Python's built-in function.
	
	Values outside of the allowable range for int32 [-2147483648,2147483647] raise ValueError.
	
	The result is a python int."""
	if type(value) in StringTypes:
		int32Value=xsi.DecodeInteger(value)
	else:
		int32Value=int(value)
	if int32Value<-2147483648 or int32Value>2147483647:
		raise ValueError("Illegal value for int32: %i"%int32Value)
	return int32Value	 

def EncodeInt32(value):
	"""Returns a unicode string representation of *value*"""
	return xsi.EncodeInteger(value)


def DecodeInt64(value):
	"""Special case of int; Int allows content in the following form: [-] [0-9]+.
	
	String types are parsed using XML schema's rules, everything else is
	coerced to long using Python's built-in function.
	
	Values outside of the allowable range for int64 [-9223372036854775808,9223372036854775807] raise ValueError.
	
	The result is a python long."""
	if type(value) in StringTypes:
		int64Value=xsi.DecodeInteger(value)
	else:
		int64Value=long(value)
	if int64Value<-9223372036854775808L or int64Value>9223372036854775807L:
		raise ValueError("Illegal value for int64: %i"%int64Value)
	return int64Value	 

def EncodeInt64(value):
	"""Returns a unicode string representation of *value*"""
	return xsi.EncodeInteger(value)


def DecodeSByte(value):
	"""Special case of int; Int allows content in the following form: [-] [0-9]+.
	
	String types are parsed using XML schema's rules, everything else is
	coerced to long using Python's built-in function.
	
	Values outside of the allowable range for SByte [-128,127] raise ValueError.
	
	The result is a python int."""
	if type(value) in StringTypes:
		sByteValue=xsi.DecodeInteger(value)
	else:
		sByteValue=int(value)
	if sByteValue<-128 or sByteValue>127:
		raise ValueError("Illegal value for SByte: %i"%sByteValue)
	return sByteValue	 

def EncodeSByte(value):
	"""Returns a unicode string representation of *value*"""
	return xsi.EncodeInteger(value)


SimpleTypeCodec={
	SimpleType.Binary:(DecodeBinary,EncodeBinary),
	SimpleType.Boolean:(DecodeBoolean,EncodeBoolean),
	SimpleType.Byte:(DecodeByte,EncodeByte),
	SimpleType.DateTime:(DecodeDateTime,EncodeDateTime),
	SimpleType.DateTimeOffset:(DecodeDateTimeOffset,EncodeDateTimeOffset),
	SimpleType.Double:(xsi.DecodeDouble,xsi.EncodeDouble),
	SimpleType.Single:(xsi.DecodeFloat,xsi.EncodeFloat),
	SimpleType.Guid:(DecodeGuid,EncodeGuid),
	SimpleType.Int16:(DecodeInt16,EncodeInt16),
	SimpleType.Int32:(DecodeInt32,EncodeInt32),
	SimpleType.Int64:(DecodeInt64,EncodeInt64),
	SimpleType.String:(lambda x:x,lambda x:x),
	SimpleType.SByte:(DecodeSByte,EncodeSByte)
	}
	

class CSDLElement(xmlns.XMLNSElement):
	pass


class Using(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Using')


class Property(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Property')

	XMLATTR_Name='name'
	XMLATTR_Type='type'
	XMLATTR_Nullable=('nullable',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_DefaultValue='defaultValue'
	XMLATTR_MaxLength=('maxLength',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_FixedLength=('fixedLength',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_Precision='precision'
	XMLATTR_Scale='scale'
	XMLATTR_Unicode='unicode'
	XMLATTR_Collation='collation'
	XMLATTR_SRID='SRID'
	XMLATTR_CollectionKind='collectionKind'
	XMLATTR_ConcurrencyMode='concurrencyMode'

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.type="Edm.String"
		self.typeCode=None
		self.nullable=True
		self.defaultValue=None
		self.maxLength=None
		self.fixedLength=None
		self.precision=None
		self.scale=None
		self.unicode=None
		self.collation=None
		self.SRID=None
		self.collectionKind=None
		self.concurrencyMode=None
		self.TypeRef=None
		self.Documentation=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]

	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	def ContentChanged(self):		
		super(Property,self).ContentChanged()
		try:
			self.typeCode=SimpleType.DecodeLowerValue(self.type)
		except ValueError:
			# must be a complex type defined elsewhere
			self.typeCode=None

	def DecodeValue(self,value):
		"""Decodes a value from a string used in a serialised form.
		
		The returned type depends on the property's :py:attr:`typeCode`."""
		if value is None:
			return None
		decoder,encoder=SimpleTypeCodec.get(self.typeCode,(None,None))
		if decoder is None:
			# treat as per string
			return value
		else:
			return decoder(value)


	def EncodeValue(self,value):
		"""Encodes a value as a string ready to use in a serialised form.
		
		The input type depends on the property's :py:attr:`typeCode`"""
		if value is None:
			return None
		decoder,encoder=SimpleTypeCodec.get(self.typeCode,(None,None))
		if encoder is None:
			# treat as per string
			return value
		else:
			return encoder(value)
				
			
	def UpdateFingerprint(self,h):
		h.update("Property:")
		h.update(self.name)
		h.update(";")
		h.update(self.type)
		h.update(";")
		h.update("True" if self.nullable else "False")
		h.update(";")
		h.update("NULL" if self.defaultValue is None else self.defaultValue)
		h.update(";")

		
class NavigationProperty(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'NavigationProperty')
	
	XMLATTR_Name='name'
	XMLATTR_Relationship='relationship'
	XMLATTR_ToRole='toRole'
	XMLATTR_FromRole='fromRole'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"
		self.relationship=None
		self.toRole=None
		self.fromRole=None
		self.Documentation=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]

	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	def UpdateFingerprint(self,h):
		h.update("NavigationProperty:")
		h.update(self.name)
		h.update(";")
		h.update(self.relationship)
		h.update(";")
		h.update(self.toRole)
		h.update(";")
		h.update(self.fromRole)
		h.update(";")


class Key(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Key')

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.PropertyRef=[]	

	def UpdateFingerprint(self,h):
		h.update("Key:")
		for pr in self.PropertyRef:
			pr.UpdateFingerprint(h)
		h.update(";")

	def GetChildren(self):
		for child in self.PropertyRef: yield child


class PropertyRef(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'PropertyRef')
	
	XMLATTR_Name='name'

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name='Default'

	def UpdateFingerprint(self,h):
		h.update(self.name)
		h.update(";")


class Type(NameTableMixin,CSDLElement):
	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_BaseType='baseType'
	XMLATTR_Abstract=('abstract',xsi.DecodeBoolean,xsi.EncodeBoolean)
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		NameTableMixin.__init__(self)
		self.name="Default"
		self.baseType=None
		self.abstract=False
		self.Documentation=None
		self.Property=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
		
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.Property,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	def ContentChanged(self):
		for p in self.Property:
			self.Declare(p)

		
class EntityType(Type):
	XMLNAME=(EDM_NAMESPACE,'EntityType')
	XMLCONTENT=xmlns.ElementType.ElementContent
	
	def __init__(self,parent):
		Type.__init__(self,parent)
		self.Key=None
		self.NavigationProperty=[]
		
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		if self.Key: yield self.Key
		for child in itertools.chain(
			self.Property,
			self.NavigationProperty,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	def ContentChanged(self):
		super(EntityType,self).ContentChanged()
		for np in self.NavigationProperty:
			self.Declare(np)

	def UpdateFingerprint(self,h):
		if self.Key:
			self.Key.UpdateFingerprint(h)
		h.update("EntityType:")
		h.update(self.name)
		h.update(";")
		for p in self.Property+self.NavigationProperty:
			p.UpdateFingerprint(h)
	
class ComplexType(Type):
	XMLNAME=(EDM_NAMESPACE,'ComplexType')

	def UpdateFingerprint(self,h):
		h.update("ComplexType:")
		h.update(self.name)
		h.update(";")
		for p in self.Property:
			p.UpdateFingerprint(h)


class Multiplicity:
	ZeroToOne=0
	One=1
	Many=2
	Encode={0:'0..1',1:'1',2:'*'}
	
MutliplicityMap={
	'0..1': Multiplicity.ZeroToOne,
	'1': Multiplicity.One,
	'*': Multiplicity.Many
	}

def DecodeMultiplicity(src):
	return MutliplicityMap.get(src.strip(),None)

def EncodeMultiplicity(value):
	return Multiplicity.Encode.get(value,'')


class Association(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Association')
	XMLATTR_Name='name'

	def __init__(self,parent):
		super(Association,self).__init__(parent)
		self.name="Default"
		self.Documentation=None
		self.End=[]
		self.ReferentialConstraint=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
		
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in self.End: yield child
		if self.ReferentialConstraint: yield self.ReferentialConstraint
		for child in itertools.chain(
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	def UpdateFingerprint(self,h):
		h.update("Association:")
		h.update(self.name)
		h.update(";")
		for e in self.End:
			e.UpdateFingerprint(h)

			
class End(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'End')
	
	XMLATTR_Type='type'
	XMLATTR_Role='role'
	XMLATTR_Multiplicity=('multiplicity',DecodeMultiplicity,EncodeMultiplicity)
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.type=None
		self.role=None
		self.multiplicity=1
		self.Documentation=None
		self.OnDelete=None
	
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		if self.OnDelete: yield self.OnDelete
		for child in CSDLElement.GetChildren(self): yield child

	def UpdateFingerprint(self,h):
		h.update("End:")
		h.update(self.type)
		h.update(";")
		h.update(EncodeMultiplicity(self.multiplicity))


class EntityContainer(NameTableMixin,CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'EntityContainer')

	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_Extends='extends'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		NameTableMixin.__init__(self)
		self.name="Default"
		self.Documentation=None
		self.FunctionImport=[]
		self.EntitySet=[]
		self.AssociationSet=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
	
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.FunctionImport,
			self.EntitySet,
			self.AssociationSet,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child		

	def ContentChanged(self):
		for t in self.EntitySet+self.AssociationSet:
			self.Declare(t)

	def UpdateFingerprint(self,h):
		h.update("EntityContainer:")
		h.update(self.name)
		h.update(";")
		for t in self.EntitySet+self.AssociationSet:
			t.UpdateFingerprint(h)


class EntitySet(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'EntitySet')	
	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_EntityType='entityType'
	XMLCONTENT=xmlns.ElementType.ElementContent

	def __init__(self,parent):
		super(EntitySet,self).__init__(parent)
		self.name="Default"
		self.entityType=""
		self.Documentation=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
	
	def GetChilren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child		
		
	def UpdateFingerprint(self,h):
		h.update("EntitySet:")
		h.update(self.name)
		h.update(";")
		h.update(self.entityType)
		h.update(";")

		
class Function(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Function')

class Annotations(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Annotations')

class ValueTerm(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'ValueTerm')


class Schema(NameTableMixin,CSDLElement):
	"""Represents the Edmx root element."""
	XMLNAME=(EDM_NAMESPACE,'Schema')

	XMLATTR_Namespace='name'
	XMLATTR_Alias='alias'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		NameTableMixin.__init__(self)
		self.name="Default"
		self.alias=None
		self.Using=[]
		self.Association=[]
		self.ComplexType=[]
		self.EntityType=[]
		self.EntityContainer=[]
		self.Function=[]
		self.Annotations=[]
		self.ValueTerm=[]
	
	def GetChildren(self):
		return itertools.chain(
			self.Using,
			self.Association,
			self.ComplexType,
			self.EntityType,
			self.EntityContainer,
			self.Function,
			self.Annotations,
			self.ValueTerm,
			CSDLElement.GetChildren(self))

	def ContentChanged(self):
		for t in self.EntityType+self.ComplexType+self.Association+self.EntityContainer:
			self.Declare(t)

	def UpdateFingerprint(self,h):
		h.update("Schema:")
		h.update(self.name)
		h.update(";")
		for t in self.EntityType+self.ComplexType+self.Association+self.EntityContainer:
			t.UpdateFingerprint(h)
		

class Document(xmlns.XMLNSDocument):
	"""Represents an EDM document."""

	classMap={}

	def __init__(self,**args):
		xmlns.XMLNSDocument.__init__(self,**args)
		self.defaultNS=EDM_NAMESPACE
		self.MakePrefix(EDM_NAMESPACE,'edm')

	def GetElementClass(self,name):
		"""Overrides :py:meth:`pyslet.xmlnames20091208.XMLNSDocument.GetElementClass` to look up name."""
		eClass=Document.classMap.get(name,Document.classMap.get((name[0],None),xmlns.XMLNSElement))
		return eClass
	
xmlns.MapClassElements(Document.classMap,globals(),EDM_NAMESPACE_ALIASES)


class ERStore(NameTableMixin):
	"""Abstract class used to represent entity-relation stores, i.e.,
	(collections of) databases.
	
	This object inherits from the basic :py:class:`NameTableMixin`, each
	declared schema represents a top-level name within the ERStore."""
	
	def __init__(self):
		NameTableMixin.__init__(self)
		self.containers={}
		"""A dictionary mapping :py:class:`EntityContainer` (database) names to
		an implementation specific value used to locate the data in the
		entity-relation store."""
		self.fingerprint=''	#: the fingerprint of this store, used for version control
	
	def UpdateFingerprint(self):
		schemas=self.nameTable.keys()
		schemas.sort()
		h=hashlib.sha256()
		for sName in schemas:
			self.nameTable[sName].UpdateFingerprint(h)
		containers=self.containers.keys()
		for cName in containers:
			# hide implementation specific details from the fingerprint
			h.update("EntityContainer:")
			h.update(cName)
			h.update(";")
		self.fingerprint=h.hexdigest()
			
	def AddSchema(self,s):
		"""Adds an additional schema to this store.
		
		Adds the definitions in s to this store.  This method is *not* thread-safe.
		After calling this method the store's fingerprint will be different.
		
		This method call is not thread-safe."""		
		if not isinstance(s,Schema):
			raise TypeError("Schema required: %s"%repr(s))
		self.Declare(s)
		self.UpdateFingerprint()
		
	def UpgradeSchema(self,newS):
		"""Upgrades an existing schema to reflect the new definitions in *newS*.
		
		A schema with the same name must have already been added to this store.
		Any created containers are upgraded, within the limits of the underlying
		storage system.  Adding/removing :py:class:`EntitySet` definitions or
		adding, removing and in some cases modifying underlying
		:py:class:`Property` definitions is also possible.
		
		This method call is not thread-safe."""
		raise NotImplementedError

	def CreateContainer(self,containerName):
		"""Initialises the :py:class:`EntityContainer` with *containerName*.
		
		Before you can read or write entities from/to an :py:class:`EntitySet`
		in the store you must initialise the :py:class:`EntityContainer` that
		contains it.  For example, a SQL-backed data store would use this
		opportunity to create tables to hold the entity sets in the
		container.
		
		This method call is not thread-safe."""
		c=self[containerName]
		if not isinstance(c,EntityContainer):
			raise ValueError("%s is not an EntityContainer"%containerName)
		# Now have we already created this container?
		if containerName in self.containers:
			raise ContainerExists("Container %s has already been created")
		# default implementation just uses "True"
		self.containers[containerName]=True

	def EntityReader(self,entitySetName):
		"""A generator function that iterates over all matching entities
		in the given :py:class:`EntitySet`.
		
		Each entity is returned as a dictionary mapping property names to values
		(None representing a null value).  Values are type-cast to appropriate
		python types."""
		while False:
			yield None
		raise NotImplementedError
	
	def InsertEntity(self,entitySetName,values):
		"""Adds an entity to an :py:class:`EntitySet`.
		
		The entity's property values are represented in a dictionary or
		dictionary-like object *values* keyed on property name."""
		raise NotImplementedError

	def DecodeLiteral(self,edmType,value):
		if value is None:
			return None
		decoder,encoder=SimpleTypeCodec.get(edmType,(None,None))
		if decoder is None:
			# treat as per string
			return value
		else:
			return decoder(value)
			
		
class SQLiteDB(ERStore):
	
	SQLType={
		"edm.boolean":"BOOLEAN",
		"edm.datetime":"DATETIME",
		"edm.single":"REAK",
		"edm.double":"DOUBLE",
		"edm.guid":"VARCHAR(36)",
		"edm.sbyte":"INTEGER",
		"edm.int16":"INTEGER",
		"edm.int32":"INTEGER",
		"edm.int64":"INTEGER",
		"edm.byte":"TINYINT",
		"edm.string":"TEXT",
		"edm.stream":"BLOB"
		}
		
	def __init__(self,fPath):
		super(SQLiteDB,self).__init__()
		if not isinstance(fPath,OSFilePath):
			raise TypeError("SQLiteDB requires an os file path")
		self.db=sqlite3.connect(str(fPath))
		self.LoadInternalTables()
		self.tableNames={}

	def BuildTableNames(self):
		self.tableNames={}
		for cName,cPrefix in self.containers.items():
			# for each container, add the table names
			c=self[cName]
			for es in c.EntitySet:
				self.tableNames[cName+"."+es.name]=cPrefix+es.name
	
	def DumpTables(self):
		c=self.db.cursor()
		query="""SELECT name FROM sqlite_master WHERE type='table'"""
		c.execute(query)
		for row in c:
			print row[0]
							
	def LoadInternalTables(self):
		"""Loads the internal data definitions from the database."""
		query="""SELECT name FROM sqlite_master WHERE type='table'"""
		c=self.db.cursor()
		done=commit=False
		while not done:
			done=True
			csdl_tables={}
			c.execute(query)
			for row in c:
				csdl_tables[row[0].lower()]=True
			if "csdl_schemas" not in csdl_tables:
				c.execute("""CREATE TABLE csdl_schemas (
					name TEXT,
					src TEXT)""")
				done=False
			if "csdl_containers" not in csdl_tables:
				c.execute("""CREATE TABLE csdl_containers (
					name TEXT,
					prefix NVARCHAR(8))""")
				done=False
			if "csdl_fingerprint" not in csdl_tables:
				c.execute("""CREATE TABLE csdl_fingerprint (
					fingerprint TEXT,
					timestamp INTEGER)""")
				c.execute("""INSERT INTO csdl_fingerprint (fingerprint,timestamp) VALUES ( '', 0 )""")
				done=False
			if not done:
				if not commit:
					self.db.commit()
					commit=True
				else:
					raise StorageError("Can't create internal database tables")
		self.LoadSchemas(c)
		self.LoadContainers(c)
		self.CheckFingerprint(c)		
	
	def LoadSchemas(self,c):
		query="""SELECT name, src FROM csdl_schemas"""
		c.execute(query)
		try:
			for row in c:
				doc=Document()
				doc.Read(src=row[1])
				if not isinstance(doc.root,Schema):
					raise StorageError("Failure to read XML object for Schema(name=%s)"%repr(row[0]))
				if doc.root.name!=row[0]:
					raise StorageError("Namespace mismatch for Schema(name=%s)"%repr(row[0]))
				self.Declare(doc.root)
		finally:
			if self.nameTable:
				self.UpdateFingerprint()
			
	def LoadContainers(self,c):
		query="""SELECT name, prefix FROM csdl_containers"""
		c.execute(query)
		try:
			for row in c:
				name=row[0]
				prefix=row[1]
				try:
					container=self[name]
					if not isinstance(container,EntityContainer):
						raise StorageError("Object type mismatch for EntityContainer(name=%s)"%repr(name))
					self.containers[name]=prefix
				except KeyError:
					raise StorageError("No definition for container %s"%name)
		finally:
			if self.containers:
				self.BuildTableNames()
				self.UpdateFingerprint()

	def CheckFingerprint(self,c):
		query="""SELECT fingerprint, timestamp FROM csdl_fingerprint"""
		c.execute(query)
		fp,latest=self.ReadFingerprint(c)
		if fp!=self.fingerprint:
			import pdb;pdb.set_trace()
			raise StorageError("Fingerprint mismatch: found %s expected %s"%(repr(fp),repr(self.fingerprint)))

	def ReadFingerprint(self,c):
		query="""SELECT fingerprint, timestamp FROM csdl_fingerprint"""
		c.execute(query)
		fp=''
		latest=0
		for row in c:
			if row[1]>latest:
				fp=row[0]
				latest=row[1]
		return fp,latest
	
	def WriteFingerprint(self,c):
		fp,latest=self.ReadFingerprint(c)
		query="""UPDATE csdl_fingerprint SET fingerprint=?, timestamp=?"""
		now=int(time.time())
		if latest>=now:
			# step in to the future
			now=latest+1
		c.execute(query,(self.fingerprint,now))
			
	def AddSchema(self,s):
		"""Adds an additional schema to this store.
		
		Updates the internal tables to save the schema source and store the new fingerprint"""		
		if not isinstance(s,Schema):
			raise TypeError("Schema required: %s"%repr(s))
		self.Declare(s)
		self.UpdateFingerprint()
		try:
			output=StringIO.StringIO()
			output.write(str(s))
			src=output.getvalue()
			query="""INSERT INTO csdl_schemas (name, src) VALUES ( ?, ?)"""
			c=self.db.cursor()
			c.execute(query,(s.name,src))
			self.WriteFingerprint(c)
			self.db.commit()
		except:
			# remove s from the list of schemas in the event of an error
			self.Undeclare(s)
			self.UpdateFingerprint()
			raise

	def UpgradeSchema(self,newS):
		"""Upgrades an existing schema to reflect the new definitions in *newS*."""
		if not isinstance(newS,Schema):
			raise TypeError("Schema required: %s"%repr(newS))
		oldS=self[newS.name]
		if not isinstance(oldS,Schema):
			raise TypeError("Schema required: %s"%repr(oldS))
		output=StringIO.StringIO()
		output.write(str(newS))
		src=output.getvalue()
		scopePrefix=newS.name+"."
		c=self.db.cursor()
		# transaction=[("BEGIN TRANSACTION",())]
		transaction=[]
		for containerName in self.containers:
			oldContainer=self[containerName]
			tablePrefix=self.containers[containerName]
			if not containerName.startswith(scopePrefix):
				# the EntityContainer is not in this scope, but definitions might be
				for oldT in oldContainer.EntitySet:
					if oldT.entityType.startswith(scopePrefix):
						# the entity type is in the new scope, may have changed
						newType=newS[oldT.entityType[len(scopePrefix):]]
						oldType=self[oldT.entityType]
						transaction=transaction+self.UpdateTable(tablePrefix+oldT.name,oldType,newType)					
			else:
				# the EntityContainer is in this scope, it may have changed
				newContainer=newS[containerName[len(scopePrefix):]]
				for oldT in oldContainer.EntitySet:
					if oldT.name in newContainer:
						# This table is in the new scope too
						newT=newContainer[oldT.name]
						if newT.entityType.startswith(scopePrefix):
							# the entity type is in the new scope too
							newType=newS[newT.entityType[len(scopePrefix):]]
							oldType=self[oldT.entityType]
							transaction=transaction+self.UpdateTable(tablePrefix+oldT.name,oldType,newType)
					else:
						# Drop this one
						transaction=transaction+self.DropTable(tablePrefix+oldT.name)
				for newT in newContainer.EntitySet:
					if newT.name in oldContainer:
						continue
					else:
						# new table not in old container
						if newT.entityType.startswith(scopePrefix):
							newType=newS[newT.entityType[len(scopePrefix):]]
						else:
							newType=self[newT.entityType]
						transaction=transaction+self.CreateTable(tablePrefix+newT.name,newType)
		# transaction.append(("COMMIT",()))
		for t,tParams in transaction:
			print "%s %s"%(t,repr(tParams))
			c.execute(t,tParams)
		self.Undeclare(oldS)
		self.Declare(newS)
		self.UpdateFingerprint()
		query="""UPDATE csdl_schemas SET src=? WHERE name=?"""
		c.execute(query,(src,newS.name))
		self.WriteFingerprint(c)
		self.db.commit()		
			
	def MangleContainerName(self,containerName):	
		prefix=[]
		if containerName.lower()!=containerName:
			# mixed case, pick out first letter and next two upper case letters
			prefix.append(containerName[0])
			for c in containerName[1:]:
				if c.isupper():
					prefix.append(c)
					if len(prefix)>=3:
						break
		if len(prefix)<3 and "_" in containerName:
			# grab the first letter and each letter after an underscore
			if containerName[0]!="_":
				prefix=[containerName[0]]
				grab=False
			else:
				prefix=[]
				grab=True
			for c in containerName[1:]:
				if c=="_":
					grab=True
				elif grab:
					prefix.append(c)
					if len(prefix)>=3:
						break
					grab=False
		if len(prefix)<3:
			# grab the first three significant characters
			gotLetter=False
			prefix=[]
			for c in containerName:
				if c.isalpha():
					prefix.append(c.lower())
					if len(prefix)>=3:
						break
		# Now scan the containers for a match
		i=0
		basePrefix=string.join(prefix,'')
		prefix=basePrefix+"_"
		while prefix in self.containers.values():
			i=i+1
			prefix="%s%i_"%(basePrefix,i)
		return prefix
		
	def CreateContainer(self,containerName):
		container=self[containerName]
		if not isinstance(container,EntityContainer):
			raise ValueError("%s is not an EntityContainer"%containerName)
		# Now have we already created this container?
		if containerName in self.containers:
			raise ContainerExists("Container %s has already been created")
		# Mangle the containerName to get the table prefix
		prefix=self.MangleContainerName(containerName)
		# At this point we'll try and create each table
		c=self.db.cursor()
		# transaction=[("BEGIN TRANSACTION",())]  CREATE TABLE can't be transacted
		transaction=[]
		query="""INSERT INTO csdl_containers (name, prefix) VALUES ( ?, ?)"""
		for t in container.EntitySet:
			eType=self[t.entityType]
			transaction=transaction+self.CreateTable(prefix+t.name,eType)
			# self.CreateTable(c,t,prefix)
		# transaction.append(("COMMIT",()))
		for t,tParams in transaction:
			print "%s %s"%(t,repr(tParams))
			c.execute(t,tParams)
		self.containers[containerName]=prefix
		self.UpdateFingerprint()
		c.execute(query,(containerName,prefix))
		self.WriteFingerprint(c)
		self.db.commit()
		self.BuildTableNames()
		
	def MapType(self,typeName):
		return self.SQLType[typeName.lower()]
	
	def EncodeLiteral(self,sqlType,value):
		"""
		"edm.datetime":"DATETIME",
		"edm.single":"REAK",
		"edm.double":"DOUBLE",
		"edm.guid":"VARCHAR(36)",
		"edm.byte":"TINYINT",
		"edm.string":"TEXT",
		"edm.stream":"BLOB"
		"""
		if value is None:
			return "NULL"
		elif sqlType=="BOOLEAN":
			if value:
				return "TRUE"
			else:
				return "FALSE"
		elif sqlType=="INTEGER":
			return int(value)
		else:
			raise NotImplementedError("Literal of type %s"%sqlType)
	
	def CreateTable(self,tName,eType):
		if '"' in tName:
			raise ValueError("Illegal table name: %s"%repr(tName))
		if not isinstance(eType,EntityType):
			# we can't create a table from something other than an EntityType
			raise ValueError("%s is not an EntityType"%eType)
		query=['CREATE TABLE "%s" ('%tName]
		qParams=[]
		columns=[]
		for p in eType.Property:
			sqlType=self.MapType(p.type)
			column=[]
			column.append('"%s" %s'%(p.name,sqlType))
			if not p.nullable:
				column.append(' NOT NULL')
			if p.defaultValue is not None:
				column.append(' DEFAULT %s'%self.EncodeLiteral(sqlType,p.defaultValue))
			columns.append(string.join(column,''))
# 		if eType.Key:
#			column=[]
# 			column.append('PRINARY KEY (')
#			pk=[]
# 			for pr in eType.Key.PropertyRef:
# 				pk.append('"%s"'%pr.name)
#			columns.append(string.join(pk,', '))
#			column.append(')')
#			columns.append(string.join(column,''))
		query.append(string.join(columns,', '))
		query.append(')')
		query=string.join(query,'')
		return [(string.join(query,''),qParams)]
		
	def UpdateTable(self,name,oldType,newType):
		"""Returns a list of queries/param tuples that will transform the table
		*name* from *oldType* to *newType*"""
		result=[]
		if '"' in name:
			raise ValueError("Illegal table name: %s"%repr(name))
		if not isinstance(oldType,EntityType):
			raise ValueError("%s is not an EntityType"%repr(oldType))
		if not isinstance(newType,EntityType):
			raise ValueError("%s is not an EntityType"%repr(newType))
		for oldP in oldType.Property:
			if oldP.name in newType:
				newP=newType[oldP.name]
				# this one is in the new type
				oldSQLType=self.MapType(oldP.type)
				newSQLType=self.MapType(newP.type)
				if newP.nullable != oldP.nullable or newP.defaultValue != oldP.defaultValue:
					raise StorageError("Can't alter column constraints for %s.%s"%(oldType.name,oldP.name))
				if newSQLType!=oldSQLType:
					result.append(('ALTER TABLE "%s" ALTER COLUMN "%s" %s'%(name,oldP.name,newSQLType),()))
			else:
				# drop this column
				result.append(('ALTER TABLE "%s" DROP COLUMN "%s"'%(name,oldP.name),()))
		for newP in newType.Property:
			if newP.name in oldType:
				continue
			else:
				# add this column
				newSQLType=self.MapType(newP.type)
				query=['ALTER TABLE "%s" ADD COLUMN "%s" %s'%(name,newP.name,newSQLType)]
				qParams=[]
				if not newP.nullable:
					query.append(' NOT NULL')
				if newP.defaultValue is not None:
					query.append(' DEFAULT %s'%self.EncodeLiteral(newSQLType,newP.defaultValue))
				result.append((string.join(query,''),qParams))
		return result

				
	def DropTable(self,name):
		if '"' in name:
			raise ValueError("Illegal table name: %s"%repr(name))
		return ('DROP TABLE "%s"'%name,())

		
	def EntityReader(self,entitySetName):
		t=self[entitySetName]
		if not isinstance(t,EntitySet):
			raise ValueError("%s must be an EntitySet"%entitySetName)
		# Look up the TABLE name in the databse
		tName=self.tableNames[entitySetName]
		eType=self[t.entityType]
		if not isinstance(eType,EntityType):
			raise ValueError("%s is not an EntityType"%t.entityType)
		transaction=[]
		query=['SELECT ']
		valueNames=[]
		qParams=[]
		for p in eType.Property:
			valueNames.append('"%s"'%p.name)
		query.append(string.join(valueNames,", "))
		query.append(' FROM "%s"'%tName)
		transaction.append((string.join(query,''),qParams))
		try:
			c=self.db.cursor()
			for t,tParams in transaction:
				print "%s %s"%(t,repr(tParams))
				c.execute(t,tParams)
				for row in c:
					result={}
					i=0
					for p in eType.Property:
						result[p.name]=self.DecodeLiteral(p.typeCode,row[i])
						i=i+1
					yield result
		except:
			raise StorageError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
	
	def InsertEntity(self,entitySetName,values):
		t=self[entitySetName]
		if not isinstance(t,EntitySet):
			raise ValueError("%s must be an EntitySet"%entitySetName)
		# Look up the TABLE name in the databse
		tName=self.tableNames[entitySetName]
		eType=self[t.entityType]
		if not isinstance(eType,EntityType):
			raise ValueError("%s is not an EntityType"%t.entityType)
		transaction=[]
		query=['INSERT INTO "%s" ('%tName]
		valueNames=[]
		qParams=[]
		for p in eType.Property:
			if p.name in values:
				valueNames.append('"%s"'%p.name)
				qParams.append(values[p.name])
		query.append(string.join(valueNames,", "))
		query.append(') VALUES (')
		query.append(string.join(['?']*len(valueNames),", "))
		query.append(')')
		transaction.append((string.join(query,''),qParams))
		try:
			c=self.db.cursor()
			for t,tParams in transaction:
				print "%s %s"%(t,repr(tParams))
				c.execute(t,tParams)
			self.db.commit()
		except:
			raise StorageError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	def close(self):
		if self.db is not None:
			self.db.close()
			self.db=None
		