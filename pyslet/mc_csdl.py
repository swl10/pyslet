#! /usr/bin/env python
"""This module implements the CSDL specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541211.aspx
http://msdn.microsoft.com/en-us/library/dd541474(v=prot.10)"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.rfc2396 as uri
import pyslet.rfc2616 as http
import pyslet.xsdatatypes20041028 as xsi
from pyslet.vfs import OSFilePath
import pyslet.iso8601 as iso8601

import string, itertools, sqlite3, hashlib, StringIO, time, sys, copy, decimal, math, collections
from types import BooleanType, FloatType, StringTypes, StringType, UnicodeType, BooleanType, IntType, LongType, TupleType, DictType


EDM_NAMESPACE="http://schemas.microsoft.com/ado/2009/11/edm"		#: Namespace to use for CSDL elements
EDM_NAMESPACE_ALIASES=[
	"http://schemas.microsoft.com/ado/2006/04/edm",		#: CSDL Schema 1.0
	"http://schemas.microsoft.com/ado/2007/05/edm",		#: CSDL Schema 1.1
	"http://schemas.microsoft.com/ado/2008/09/edm"]		#: CSDL Schema 2.0

NAMESPACE_ALIASES={
	EDM_NAMESPACE:EDM_NAMESPACE_ALIASES
	}


SimpleIdentifierRE=xsi.RegularExpression(r"[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")

def ValidateSimpleIdentifier(identifier):
	"""Validates a simple identifier, returning the identifier unchanged or
	raising ValueError."""
	if SimpleIdentifierRE.Match(identifier):
		return identifier
	else:
		raise ValueError("Can't parse SimpleIdentifier from :%s"%repr(identifier))


class EDMError(Exception):
	"""General exception for all CSDL model errors."""
	pass


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

class ModelIncomplete(EDMError):
	"""Raised when attempting to use model element with a missing reference.
	
	For example, attempting to create an :py:class:`Entity` in an
	:py:class:`EntitySet` that is bound to an undeclared :py:class:`EntityType`.
	
	References are checked using :py:meth:`CSDLElement.UpdateTypeRefs` and
	:py:meth:`CSDLElement.UpdateSetRefs` which, to increase tolerance of badly
	defined schemas, ignore errors by default. Should an area of the model that
	was incomplete be encountered later then ModelIncomplete will be raised."""
	pass

	
class ContainerExists(Exception):
	"""Raised by :py:meth:`ERStore.CreateContainer` when the container already
	exists."""
	pass


class StorageError(Exception): pass

class DictionaryLike(object):
	"""A new-style class for behaving like a dictionary.
	
	Derived classes must override :py:meth:`__iter__` and :py:meth:`__getitem__`
	and if the dictionary is writable :py:meth:`__setitem__` and probably
	:py:meth:`__delitem__` too.  These methods all raise NotImplementedError by
	default.
	
	They should also override :py:meth:`__len__` and :py:meth:`clear` as the
	default implementations are inefficient."""
	
	def __getitem__(self,key):
		"""Implements self[key]"""
		raise NotImplementedError
	
	def __setitem__(self,key,value):
		"""Implements assignment to self[key]"""
		raise NotImplementedError
		
	def __delitem__(self,key):
		"""Implements del self[key]"""
		raise NotImplementedError
	
	def __iter__(self):
		"""Returns an object that implements the iterable protocol on the keys"""
		raise NotImplementedError
				
	def __len__(self):
		"""Implements len(self)
		
		The default implementation simply counts the keys returned by __iter__
		and should be overridden with a more efficient implementation if
		available."""
		count=0
		for k in self:
			count+=1
		return count
	
	def __contains__(self,key):
		"""Implements: key in self
		
		The default implementation uses __getitem__ and returns False if it
		raises a KeyError."""
		try:
			e=self[key]
			return True
		except KeyError:
			return False
	
	def iterkeys(self):
		"""Returns an iterable of keys, simple calls __iter__"""
		return self.__iter__()

	def itervalues(self):
		"""Returns an iterable of values.
		
		The default implementation is a generator function that iterates over
		the keys and uses __getitem__ to return the value."""
		for k in self:
			yield self[k] 
		
	def keys(self):
		"""Returns a list of keys.
		
		This is a copy of the keys in no specific order.  Modifications to this
		list do not affect the object.  The default implementation uses
		:py:meth:`iterkeys`"""
		return list(self.iterkeys())
	
	def values(self):
		"""Returns a list of values.
		
		This is a copy of the values in no specific order.  Modifications to
		this list do not affect the object.  The default implementation uses
		:py:meth:`itervalues`."""
		return list(self.itervalues())

	def iteritems(self):
		"""Returns an iterable of key,value pairs.
		
		The default implementation is a generator function that uses
		:py:meth:`__iter__` and __getitem__"""
		for k in self:
			yield k,self[k]

	def items(self):
		"""Returns a list of key,value pair tuples.

		This is a copy of the items in no specific order.  Modifications to this
		list do not affect the object.  The default implementation users
		:py:class:`iteritems`."""
		return list(self.iteritems())
	
	def has_key(self,key):
		"""Equivalent to: key in self"""
		return key in self
	
	def get(self,key,default=None):
		"""Equivalent to: self[key] if key in self else default.
		
		Implemented using __getitem__"""
		try:
			return self[key]
		except KeyError:
			return default
	
	def setdefault(self,key,value=None):
		"""Equivalent to: self[key] if key in self else value; ensuring
		self[key]=value

		Implemented using __getitem__ and __setitem__."""
		try:
			e=self[key]
			return e
		except KeyError:
			self[key]=value
			return value
	
	def pop(self,key,value=None):
		"""Equivalent to: self[key] if key in self else value; ensuring key not
		in self.

		Implemented using __getite__ and __delitem__."""
		try:
			e=self[key]
			del self[key]
			return e
		except KeyError:
			return value

	def clear(self):
		"""Removes all items from the object.
		
		The default implementation uses :py:meth:`keys` and deletes the items
		one-by-one with __delitem__.  It does this to avoid deleting objects
		while iterating as the results are generally undefined.  A more
		efficient implementation is recommended."""
		for k in self.keys():
			del self[k]

	def popitem(self):
		"""Equivalent to: self[key] for some random key; removing key.
		
		This is a rather odd implementation but to avoid iterating over the
		whole object we create an iterator with __iter__, use __getitem__ and
		__delitem__ to pop the first item and then discard the iterator."""
		for k in self:
			value=self[k]
			del self[k]
			return k,value
		raise KeyError
				
	def bigclear(self):
		"""Removes all the items from the object (alternative for large
		dictionary-like objects).
		
		This is an alternative implementation more suited to objects with very
		large numbers of keys.  It uses :py:meth:`popitem` repeatedly until
		KeyError is raised.  The downside is that popitem creates (and discards)
		one iterator object for each item it removes.  The upside is that we
		never load the list of keys into memory."""
		try:
			while True:
				self.popitem()
		except KeyError:
			pass
		
	def copy(self):
		"""Makes a shallow copy of this object: raises NotImplementedError."""
		raise NotImplementedError

	def update(self,items):
		"""Calls clear to remove items and then iterates through *items* using
		__setitem__ to add them to the set."""
		self.clear()
		for key,value in items:
			self[key]=value

	
class NameTableMixin(DictionaryLike):
	"""A mix-in class to help other objects become named scopes.
	
	Using this mix-in the class behaves like a read-only named dictionary with
	string keys and object value.  If the dictionary contains a value that is
	itself a NameTableMixin then keys can be compounded to look-up items in
	sub-scopes.
	
	For example, if the name table contains a value with key "X"
	that is itself a name table containing a value with key "Y" then both "X"
	and "X.Y" are valid keys."""
	
	def __init__(self):
		self.name=""			#: the name of this name table (in the context of its parent)
		self.nameTable={}		#: a dictionary mapping names to child objects
	
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
			
	def __iter__(self):
		for key in self.nameTable:
			yield key
		for value in self.nameTable.itervalues():
			if isinstance(value,NameTableMixin):
				for key in value:
					yield value.name+"."+key
				
	def SplitKey(self,key):
		sKey=key.split(".")
		pathLen=1
		while pathLen<len(sKey):
			scope=self.nameTable.get(string.join(sKey[:pathLen],"."),None)
			if isinstance(scope,NameTableMixin):
				return scope,string.join(sKey[pathLen:],".")
			pathLen+=1
		return None,key
		
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
			

class SimpleType(xsi.Enumeration):
	"""SimpleType defines constants for the core data types defined by CSDL
	::
		
		SimpleType.Boolean	
		SimpleType.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`
	
	[Aside: I'm not that happy with this definition.  In order to ensure that
	the encode function produces the "Edm.X" form of the name the deocde
	dictionary is initialised with these forms.  As a result, the class has
	attributes of the form "SimpleType.Edm.Binary" which are inaccessible to
	python unless getattr is used.  To workaround this problem (and because the
	Edm. prefix seems to be optional) we also define aliases without the Edm.
	prefix. As a result, you can use SimpleType.Binary as the symbolic (integer)
	representation of the enumeration value.]"""
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
	
	PythonType={}
		
	@classmethod
	def FromPythonType(cls,t):
		"""Takes a python type (as returned by the built-in type
		function) and returns the most appropriate constant value."""
		return cls.PythonType[t]
	
	@classmethod
	def CoerceValue(cls,typeCode,value):
		"""Takes one of the type code constants and a python native value and returns the
		value coerced to the best python value type for this type code."""
		if typeCode==cls.Binary:
			return str(value)
		elif typeCode==cls.Boolean:
			return bool(value)
		elif typeCode in (cls.Byte,cls.Int16,cls.Int32,cls.SByte):
			return int(value)
		elif typeCode in (cls.DateTime,cls.DateTimeOffset):
			if isinstance(value,iso8601.TimePoint):
				return value
			else:
				return iso8601.TimePoint(value)
		elif typeCode==cls.Decimal:
			return decimal.Decimal(value)
		elif typeCode in (cls.Double,cls.Single):
			return float(value)
		elif typeCode==cls.Guid:
			if isinstance(value,uuid.UUID):
				return value
			else:
				return uuid.UUID(value)
		elif typeCode==cls.String:
			return unicode(value)
		elif typeCode==cls.Time:
			raise "TODO"
		else:
			raise ValueError(typeCode)
			
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

SimpleType.PythonType={
	BooleanType:SimpleType.Boolean,
	FloatType:SimpleType.Double,
	IntType:SimpleType.Int64,
	LongType:SimpleType.Decimal,
	StringType:SimpleType.String,
	UnicodeType:SimpleType.String }


Numeric=collections.namedtuple('Numeric',"sign lDigits rDigits eSign eDigits")

class Parser(xsi.BasicParser):
	"""A CSDL-specific parser, mainly for decoding literal values of simple types.
	
	These productions are documented using the ABNF from the OData
	specification. Clearly they should match the requirements of the CSDL
	document itself."""
	
	def ParseBinaryLiteral(self):
		"""Parses a binary literal, returning a raw binary string::
		
		binaryLiteral = hexDigPair
		hexDigPair = 2*HEXDIG [hexDigPair]"""		
		output=[]
		hexStr=self.ParseHexDigits(0)
		if hexStr is None:
			return ''
		if len(hexStr)%2:
			raise ValueError("Trailing nibble in binary literal: '%s'"%hexStr[-1])
		i=0
		while i<len(hexStr):
			output.append(chr(int(hexStr[i:i+2],16)))
			i=i+2
		return string.join(output,'')
	
	def ParseBooleanLiteral(self):
		"""Parses a boolean literal returning True, False or None if no boolean
		literal was found."""
		if self.ParseInsensitive("true"):
			return True
		elif self.ParseInsensitive("false"):
			return False
		else:
			return None

	def ParseByteLiteral(self):
		"""Parses a byteLiteral, returning a python integer.
		
		We are generous in what we accept, ignoring leading zeros.  Values
		outside the range for byte return None."""
		return self.ParseInteger(0,255)

	def ParseDateTimeLiteral(self):
		"""Parses a DateTime literal, returning a :py:class:`pyslet.iso8601.TimePoint` instance.
		
		Returns None if no DateTime literal can be parsed.  This is a
		generous way of parsing iso860-like values, it accepts omitted
		zeros in the date, such as 4-7-2001."""
		savePos=self.pos
		try:
			production="dateTimeLiteral"
			year=int(self.RequireProduction(self.ParseDigits(4,4),"year"))
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
				second=0
		except ValueError:
			self.SetPos(savePos)
			return None
		try:
			value=iso8601.TimePoint()
			value.SetCalendarTimePoint(year//100,year%100,month,day,hour,minute,second)
		except iso8601.DateTimeError as e:
			raise ValueError(str(e))
		return value
	
	def ParseNumericLiteral(self):
		"""Parses a numeric literal returning a named tuple of strings::
		
			( sign, lDigits, rDigits, expSign, eDigits )
		
		An empty string indicates a component that was not present except that
		rDigits will be None if no decimal point
		was present.  Likewise, eDigits may be None indicating that no
		exponent was found.
		
		Although both lDigits and rDigits can be empty they will never
		*both* be empty strings. If there are no digits present then the
		method returns None, rather than a tuple.  Therefore, forms like
		"E+3" are not treated as being numeric literals whereas, perhaps
		oddly, 1E+ is parsed as a numeric literal (even though it will
		raise ValueError later when setting any of the numeric value
		types).
		
		Representations of infinity and not-a-number result in lDigits
		being set to 'inf' and 'nan' respectively.  They always result
		in rDigits and eDigits being None."""
		savePos=self.pos
		eSign=''
		rDigits=eDigits=None
		sign=self.ParseOne("-")
		if sign is None:
			sign=""
		if self.ParseInsensitive("inf"):
			lDigits="inf"
		elif self.ParseInsensitive("nan"):
			lDigits="nan"
		else:
			lDigits=self.ParseDigits(0)
			if self.Parse('.'):
				rDigits=self.ParseDigits(0)
			if not lDigits and not rDigits:
				self.SetPos(savePos)
				return None
			if self.ParseOne('eE'):
				eSign=self.ParseOne("-")
				if eSign is None:
					eSign='+'
				eDigits=self.ParseDigits(0)
		return Numeric(sign,lDigits,rDigits,eSign,eDigits)

	
			
"""
String allows any sequence of UTF-8 characters.
Int allows content in the following form: [-] [0-9]+.
Decimal allows content in the following form: [0-9]+.[0-9]+M|m.
"""

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

SimpleTypeCodec={
	SimpleType.Guid:(DecodeGuid,EncodeGuid),
	SimpleType.String:(lambda x:x,lambda x:x),
	}


class EDMValue(object):
	"""Represents a value in the EDMModel.
	
	This class is not part of the declared metadata model but is used to wrap or
	'box' instances of a value.  In particular, it can be used in a context
	where that value can have either a simple or complex type.
	
	The optional name attribute may be used when serialising the value out of
	context."""
	def __init__(self,name=None):
		self.name=name		#: the name of the value (e.g., a property name)

	__hash__=None
	#: EDM values are mutable so may not be used as dictionary keys, enforced by setting __hash__ to None

	def __nonzero__(self):
		"""EDMValue instances are treated as being non-zero if :py:meth:`IsNull`
		returns False."""
		return not self.IsNull()
		
	def IsNull(self):
		"""Returns True if this object is Null."""
		return True
		

class SimpleValue(EDMValue):
	"""Represents a value of a simple type in the EDMModel.
	
	This class is not designed to be instantiated directly, instead use
	the class method :py:meth:`NewValue` (with the same signature) to
	construct one of the specific child classes.
		
	The pyValue attribute is the python value or None if this value is NULL
	
	The python type used for pyValue depends on typeCode as follows:
	
	* Edm.Boolean: one of the Python constants True or False
	
	* Edm.Byte, Edm.SByte, Edm.Int16, Edm.Int32: int

	* Edm.Int64: long

	* Edm.Double, Edm.Single: python float

	* Edm.Decimal: python Decimal instance (from decimal module)

	* Edm.DateTime, Edm.DateTimeOffset: py:class:`pyslet.iso8601.TimePoint` instance
	
	* Edm.Time:	py:class:`pyslet.iso*601.Time` instance (TBC)

	* Edm.Binary: raw string

	* Edm.String: unicode string

	* Edm.Guid: python UUID instance (from uuid module)
	
	The value of *pyValue* can be assigned directly to alter the value
	of instance but if you violate the above type rules then you are
	likely to generate unexpected exceptions elsewhere."""
	
	_TypeClass={
		}
	
	@classmethod
	def NewValue(cls,typeCode,name=None):
		"""Constructs an instance of the correct child class of
		:py:class:`SimpleValue` to represent the type with *typeCode*.

		*	typeCode is one of the :py:class:`SimpleType` constants
	
		*	name is the (optional) name of the property this value represents
		
		We support a special case for creating a type-less NULL.  If you
		pass None for the typeCode then a type-less
		:py:class:`SipmleValue` is instantiated."""		
		if typeCode is None:
			return SimpleValue(None,name)
		else:
			return cls._TypeClass[typeCode](name)
		
	def __init__(self,typeCode,name=None):
		EDMValue.__init__(self,name)
		self.typeCode=typeCode		#: the :py:class:`SimpleType` code
		self.mType=None				#: a :py:class:`pyslet.rfc2616.MediaType` representing this value
		self.pyValue=None			#: the value, as represented using the closest python type

	def IsNull(self):
		return self.pyValue is None
	
	def Cast(self,newTypeCode):
		"""Returns a new :py:class:`SimpleValue` of type *newTypeCode* casting the value accordingly.
		
		If the types are incompatible a TypeError is raised, if the
		values are incompatible then ValueError is raised.
		
		Special case: if the value is already of the specified type then
		no new instance is created and the return value is the object
		itself.
		
		Also, NULL values can be cast to any value type.  The result is
		a typed NULL."""
		if self.typeCode==newTypeCode:
			return self
		else:
			newValue=SimpleValue.NewValue(newTypeCode,self.name)
			if self.typeCode is not None:
				newValue.SetFromPyValue(copy.deepcopy(self.pyValue))
			return newValue
					
	def __eq__(self,other):
		if isinstance(other,SimpleValue):
			# are the types compatible? lazy comparison to start with
			return self.typeCode==other.typeCode and self.pyValue==other.pyValue			
		else:
			return self.pyValue==other
	
	def __ne__(self,other):
		return not self==other
		
	def __unicode__(self):
		"""Formats this value into its literal form.
		
		Note that Null values cannot be represented in literal form and will
		raise ValueError."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name) 
		decoder,encoder=SimpleTypeCodec.get(self.typeCode,(unicode,unicode))
		return encoder(self.pyValue)

	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form.
		
		You can get the literal form of a value using the unicode function."""
		decoder,encoder=SimpleTypeCodec.get(self.typeCode,(unicode,unicode))
		self.pyValue=decoder(value)		

	def SetFromPyValue(self,newValue):
		"""Sets the value from a python variable coercing *newValue* if
		necessary to ensure it is of the correct type for the value's
		:py:attr:`typeCode`."""
		if newValue is None:
			self.pyValue=None
		else:
			raise NotImplementedError


class BinaryValue(SimpleValue):
	"""Represents a simple value of type Edm.Binary"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Binary,name)

	def __unicode__(self):
		"""Formats this value into its literal form, the hex-string representation."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name) 
		input=StringIO.StringIO(self.pyValue)
		output=StringIO.StringIO()
		while True:
			byte=input.read(1)
			if len(byte):
				output.write("%02X"%ord(byte))
			else:
				break
		return unicode(output.getvalue())

	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form.
		
		Binary literals allow content in the following form::

			[A-Fa-f0-9][A-Fa-f0-9]*"""
		p=Parser(value)
		self.pyValue=p.RequireProductionEnd(p.ParseBinaryLiteral(),"binaryLiteral")

	def SetFromPyValue(self,newValue):
		"""Sets the value from a raw python string.
		
		If *newValue* is anything other than a binary string then the
		value is set to its pickled representation.  There is no reverse
		facility for reading an object from the pickled value.  Clearly
		the purpose of the binary data type is to store this type of
		serialised data but it needs using with caution due to security
		risks around unpickling data from an untrusted source."""
		if type(newValue) is StringType:
			self.pyValue=newValue
		elif newValue is None:
			self.pyValue=None
		else:
			self.pyValue=pickle.dumps(newValue)

		
class BooleanValue(SimpleValue):
	"""Represents a simple value of type Edm.Boolean"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Boolean,name)

	def __unicode__(self):
		"""Formats this value into its literal form, the unicode strings true or false."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name)
		return u"true" if self.pyValue else u"false"

	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form.
		
		Bool allows content in the following form::
		
			true | false"""
		testValue=value.lower()
		if testValue==u"true":
			self.pyValue=True
		elif testValue==u"false":
			self.pyValue=False
		else:
			raise ValueError("Failed to parse boolean literal from %s"%value)

	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
			self.pyValue=(newValue!=0)
		elif type(newValue)==BooleanType:
			self.pyValue=newValue
		else:
			raise TypeError("Can't set Boolean from %s"%str(newValue))	


class NumericValue(SimpleValue):
	"""An abstract class for Numeric values."""
	
	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form.
		
		This method is common to all numeric types, it calls
		:py:meth:`SetFromNumericLiteral`"""
		p=Parser(value)
		nValue=p.RequireProductionEnd(p.ParseNumericLiteral(),"byteLiteral")
		self.SetFromNumericLiteral(nValue)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes a value from a :py:class:`Numeric` literal."""
		raise NotImplementedError
		
	def JoinNumericLiteral(self,numericValue):
		r=[]
		r.append(numericValue.sign)
		r.append(numericValue.lDigits)
		if numericValue.rDigits is not None:
			r.append('.')
			r.append(numericValue.rDigits)
		if numericValue.eDigits is not None:
			r.append('E')
			r.append(numericValue.eSign)
			r.append(numericValue.eDigits)
		return string.join(r,'')


class ByteValue(NumericValue):
	"""Represents a simple value of type Edm.Byte"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Byte,name)

	def __unicode__(self):
		"""Formats this value into its literal form."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name)
		return xsi.EncodeInteger(self.pyValue)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes a Byte value from a :py:class:`Numeric` literal."""
		if (numericValue.sign or 					# no sign allowed at all
			not numericValue.lDigits or 			# must be left digits
			numericValue.lDigits.isalpha() or		# must not be nan or inf
			numericValue.rDigits is not None or 	# must not have '.' or rDigits
			numericValue.eDigits is not None):		# must not have an exponent
			raise ValueError("Illegal literal for Byte: %s"%self.JoinNumericLiteral(numericValue))
		self.SetFromPyValue(int(numericValue.lDigits))		
		
	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
			if newValue<0 or newValue>255:
				raise ValueError("Illegal value for Byte: %s"%str(newValue))
			self.pyValue=int(newValue)
		else:
			raise TypeError("Can't set Byte from %s"%str(newValue))	

		
class DateTimeValue(SimpleValue):
	"""Represents a simple value of type Edm.DateTime"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.DateTime,name)

	def __unicode__(self):
		"""Formats this value into its literal form."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name)
		return unicode(self.pyValue)

	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form.
		
		DateTime allows content in the following form::
		
			yyyy-mm-ddThh:mm[:ss[.fffffff]]"""
		p=Parser(value)
		self.pyValue=p.RequireProductionEnd(p.ParseDateTimeLiteral(),"DateTime")

	def SetFromPyValue(self,newValue):
		"""*newValue* must be an instance of
		:py:class:`iso8601.TimePoint` or type int, long, float or
		Decimal.
		
		Numeric forms are treated as Unix time values and must be
		non-negative.  If newValue is a TimePoint instance then any zone
		specifier is removed from it.  There is *no* conversion to UTC,
		the value simply becomes a local time in an unspecified zone."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,iso8601.TimePoint):
			newValue.SetZone(None)
			self.pyValue=newValue			
		elif (isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType)) and newValue>=0:
			dtValue=iso8601.TimePoint()
			dtValue.SetUnixTime(float(newValue))
			dtValue.SetZone(None)
			self.pyValue=dtValue
		else:
			raise TypeError("Can't set DateTime from %s"%str(newValue))

		
class DateTimeOffsetValue(SimpleValue):
	"""Represents a simple value of type Edm.DateTimeOffset"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.DateTimeOffset,name)

	def __unicode__(self):
		"""Formats this value into its literal form."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name)
		result=unicode(self.pyValue)
		if result[-1]=="Z":
			# the specification is not clear if the Z form is supported, use numbers for safety
			result=result[:-1]+"+00:00"
		return result

	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form.
		
		DateTimeOffset uses the XMLSchema lexical representation.  We are generous
		in what we accept!"""
		try:
			value=iso8601.TimePoint(value)
		except iso8601.DateTimeError as e:
			raise ValueError(str(e))
		self.SetFromPyValue(value)

	def SetFromPyValue(self,newValue):
		"""*newValue* must be an instance of
		:py:class:`iso8601.TimePoint` or type int, long, float or
		Decimal.
		
		Numeric forms are treated as Unix time values in the UTC zone.
		If newValue is a TimePoint instance then it must have a zone
		specifier.  There is *no* automatic assumption of UTC."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,iso8601.TimePoint):
			zDir,zOffset=newValue.GetZone()
			if zOffset is None:
				raise ValueError("DateTimeOffset requirea a time zone specifier: %s"%newValue)
			if not newValue.Complete():
				raise ValueError("DateTimeOffset requires a complete representation: %s"%str(newValue))
			self.pyValue=newValue	
		elif (isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType)) and newValue>=0:
			dtValue=iso8601.TimePoint()
			dtValue.SetUnixTime(float(newValue))
			self.pyValue=dtValue
		else:
			raise TypeError("Can't set DateTimeOffset from %s"%str(newValue))

		
class TimeValue(SimpleValue):
	"""Represents a simple value of type Edm.Time"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Time,name)

		
class DecimalValue(NumericValue):
	"""Represents a simple value of type Edm.Decimal"""

	Max=decimal.Decimal(10)**29-1		#: max decimal in the default context
	Min=decimal.Decimal(10)**-29		#: min decimal for string representation
	
	@classmethod
	def abs(cls,d):
		if d<0:
			return -d
		else:
			return d
			
	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Decimal,name)

	def __unicode__(self):
		"""Formats this value into its literal form."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name)
		t=self.pyValue.as_tuple()
		if t.exponent<-29:
			# CSDL expects a 29-digit limit to the right of the point
			d=self.pyValue.quantize(decimal.Decimal(10)**-29)
		elif t.exponent+len(t.digits)>29:
			# CSDL expects a 29-digit limit to the left of the point
			raise ValueError("Value exceeds limits for Decimal: %s"%str(self.pyValue))
		else:
			d=self.pyValue
		# now ensure there is no exponent in the format
		return unicode(d.__format__('f'))

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes a Decimal value from a :py:class:`Numeric` literal.
		
		We impose the rule that no exponent notation is allowed and that
		numbers must be limited to 29 digits to the left and right of
		the point.  Also, if there is a point, there must be digits to
		the right of it."""
		dStr=self.JoinNumericLiteral(numericValue)
		if ((numericValue.lDigits and 
			 (numericValue.lDigits.isalpha() or					# inf and nan not allowed
			 	len(numericValue.lDigits)>29)) or				# limit left digits
			 (numericValue.rDigits and 
			 	len(numericValue.rDigits)>29) or				# limit right digits
			 numericValue.rDigits=="" or						# ensure decimals if '.' is present
			 numericValue.eDigits is not None):					# do not allow exponent
			raise ValueError("Illegal literal for Decimal: %s"%dStr)
		self.SetFromPyValue(decimal.Decimal(dStr))		
		
	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal."""
		if newValue is None:
			self.pyValue=None
			return
		elif isinstance(newValue,decimal.Decimal):
			d=newValue
		elif type(newValue) in (IntType, LongType, FloatType):
			d=decimal.Decimal(newValue)
		else:
			raise TypeError("Can't set Decimal from %s"%str(newValue))	
		if self.abs(d)>self.Max:
			# too big for CSDL decimal forms
			raise ValueError("Value exceeds limits for Decimal: %s"%str(d))
		# in the interests of maintaining accuracy we don't limit the
		# precision of the value at this point
		self.pyValue=d		


class FloatValue(NumericValue):
	"""Represents one of Edm.Double or Edm.Single.
	
	This is an abstract class.  The derived classes SingleValue and
	DoubleValue differ in their Max and Min values used when setting the
	value."""
	
	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal.
		
		There is no hard-and-fast rule about the representation of float
		in Python and we may refuse to accept values that fall within
		the accepted ranges defined by the CSDL if float cannot hold
		them.  That said, you won't have this problem in practice."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType):
			if newValue<-self.Max or newValue>self.Max:
				raise ValueError("Value for Double out of range: %s"%str(newValue))
			self.pyValue=float(newValue)
		elif type(newValue) is FloatType:
			if math.isnan(newValue) or math.isinf(newValue):
				self.pyValue=newValue
			elif newValue<-self.Max or newValue>self.Max:
				raise ValueError("Value out of range: %s"%str(newValue))
			else:
				self.pyValue=newValue			
		else:
			raise TypeError("Can't set floating-point value from %s"%str(newValue))	

			
class DoubleValue(FloatValue):
	"""Represents a simple value of type Edm.Double"""

	Max=None		#: the largest positive double value
	Min=2**-1074	#: the smallest positive double value
	
	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Double,name)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes a Double value from a :py:class:`Numeric` literal."""
		dStr=self.JoinNumericLiteral(numericValue)
		if numericValue.lDigits and numericValue.lDigits.isalpha():
			if numericValue.lDigits=="nan":
				if numericValue.sign:
					raise ValueError("Illegal literal, nan must not be negative: %s"%dStr)
				self.pyValue=float("Nan")
			elif numericValue.sign=="-":
				self.pyValue=float("-INF")
			else:
				self.pyValue=float("INF")
		elif (numericValue.rDigits is None or		# integer form or 
			numericValue.eDigits is not None):		# exponent form; limit digits
			nDigits=len(numericValue.lDigits)
			if numericValue.rDigits:
				nDigits+=len(numericValue.rDigits)
			if nDigits>17:
				raise ValueError("Too many digits for double: %s"%dStr)
			if (numericValue.eDigits=='' or					# empty exponent not allowed
				(numericValue.eDigits and
					(len(numericValue.eDigits)>3 or			# long exponent not allowed
					not numericValue.lDigits))):			# exponent requires digits to left of point			
				raise ValueError("Illegal exponent form for double: %s"%dStr)				
		self.SetFromPyValue(float(dStr))



for i in xrange(1023,0,-1):
	try:
		DoubleValue.Max=(2-2**-52)*2**i
		break
	except OverflowError:
		# worrying this probably means float is too small for this application
		if i==1023:
			print "Warning: float may be less than double precision"
		elif i==127:
			print "Warning: float may be less than singe precision!"
		continue

		
class SingleValue(FloatValue):
	"""Represents a simple value of type Edm.Single"""
	
	Max=None					#: the largest positive single value
	Min=2.0**-149				#: the smallest positive single value

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Single,name)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes a Single value from a :py:class:`Numeric` literal."""
		dStr=self.JoinNumericLiteral(numericValue)
		if numericValue.lDigits and numericValue.lDigits.isalpha():
			if numericValue.lDigits=="nan":
				if numericValue.sign:
					raise ValueError("Illegal literal, nan must not be negative: %s"%dStr)
				self.pyValue=float("Nan")
			elif numericValue.sign=="-":
				self.pyValue=float("-INF")
			else:
				self.pyValue=float("INF")
		elif numericValue.rDigits is None:
			# integer form
			if len(numericValue.lDigits)>8:
				raise ValueError("Too many digits for single: %s"%dStr)
		elif numericValue.eDigits is not None:
			# exponent form
			nDigits=len(numericValue.lDigits)
			if numericValue.rDigits:
				nDigits+=len(numericValue.rDigits)
			if nDigits>9:
				raise ValueError("Too many digits for single: %s"%dStr)
			if (numericValue.eDigits=='' or					# empty exponent not allowed
				(numericValue.eDigits and
					(len(numericValue.eDigits)>2 or			# long exponent not allowed
					not numericValue.lDigits))):			# exponent requires digits to left of point			
				raise ValueError("Illegal exponent form for single: %s"%dStr)				
		self.SetFromPyValue(float(dStr))


for i in xrange(127,0,-1):
	try:
		SingleValue.Max=(2-2**-23)*2**i
		break
	except OverflowError:
		# worrying this probably means float is too small for this application
		if i==127:
			print "Warning: float may be less than singe precision!"
		continue

		
class GuidValue(SimpleValue):
	"""Represents a simple value of type Edm.Guid"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Guid,name)

		
class Int16Value(NumericValue):
	"""Represents a simple value of type Edm.Int16"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Int16,name)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes an Int16 value from a :py:class:`Numeric` literal."""
		if (not numericValue.lDigits or 			# must be left digits
			numericValue.lDigits.isalpha() or		# must not be nan or inf
			numericValue.rDigits is not None or 	# must not have '.' or rDigits
			numericValue.eDigits is not None):		# must not have an exponent
			raise ValueError("Illegal literal for Int16: %s"%self.JoinNumericLiteral(numericValue))
		self.SetFromPyValue(int(self.JoinNumericLiteral(numericValue)))		

	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal.
		
		If the value is a float or fractional Decimal then it is rounded
		towards zero using the python *int* function."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
			if newValue<-32768 or newValue>32767:
				raise ValueError("Illegal value for Int16: %s"%str(newValue))
			self.pyValue=int(newValue)
		else:
			raise TypeError("Can't set Int16 from %s"%str(newValue))	

		
class Int32Value(NumericValue):
	"""Represents a simple value of type Edm.Int32"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Int32,name)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes an Int32 value from a :py:class:`Numeric` literal."""
		if (not numericValue.lDigits or 			# must be left digits
			len(numericValue.lDigits)>10 or			# must not be more than 10 digits
			numericValue.lDigits.isalpha() or		# must not be nan or inf
			numericValue.rDigits is not None or 	# must not have '.' or rDigits
			numericValue.eDigits is not None):		# must not have an exponent
			raise ValueError("Illegal literal for Int32: %s"%self.JoinNumericLiteral(numericValue))
		self.SetFromPyValue(int(self.JoinNumericLiteral(numericValue)))		

	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal.
		
		If the value is a float or fractional Decimal then it is rounded
		towards zero using the python *int* function."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
			if newValue<-2147483648 or newValue>2147483647:
				raise ValueError("Illegal value for Int32: %s"%str(newValue))
			self.pyValue=int(newValue)
		else:
			raise TypeError("Can't set Int32 from %s"%str(newValue))	

		
class Int64Value(NumericValue):
	"""Represents a simple value of type Edm.Int64"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.Int64,name)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes an Int64 value from a :py:class:`Numeric` literal."""
		if (not numericValue.lDigits or 			# must be left digits
			len(numericValue.lDigits)>19 or			# must not be more than 19 digits
			numericValue.lDigits.isalpha() or		# must not be nan or inf
			numericValue.rDigits is not None or 	# must not have '.' or rDigits
			numericValue.eDigits is not None):		# must not have an exponent
			raise ValueError("Illegal literal for Int64: %s"%self.JoinNumericLiteral(numericValue))
		self.SetFromPyValue(int(self.JoinNumericLiteral(numericValue)))		

	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal.
		
		If the value is a float or fractional Decimal then it is rounded
		towards zero using the python *long* function."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
			if newValue<-9223372036854775808L or newValue>9223372036854775807L:
				raise ValueError("Illegal value for Int64: %s"%str(newValue))
			self.pyValue=long(newValue)
		else:
			raise TypeError("Can't set Int64 from %s"%str(newValue))	

		
class StringValue(SimpleValue):
	"""Represents a simple value of type Edm.String"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.String,name)

	def __unicode__(self):
		"""Formats this value into its literal form."""
		if self.pyValue is None:
			raise ValueError("%s is Null"%self.name)
		return unicode(self.pyValue)

	def SetFromPyValue(self,newValue):
		"""*newValue* must be a string, or have a suitable unicode conversion method."""
		if newValue is None:
			self.pyValue=None
		elif type(newValue)==UnicodeType:
			self.pyValue=newValue
		else:
			self.pyValue=unicode(newValue)

	def SetFromLiteral(self,value):
		"""Decodes a value from the value's literal form - which is the identity."""
		self.pyValue=value

		
class SByteValue(NumericValue):
	"""Represents a simple value of type Edm.SByte"""

	def __init__(self,name=None):
		SimpleValue.__init__(self,SimpleType.SByte,name)

	def SetFromNumericLiteral(self,numericValue):
		"""Decodes an SByte value from a :py:class:`Numeric` literal."""
		if (not numericValue.lDigits or 			# must be left digits
			numericValue.lDigits.isalpha() or		# must not be nan or inf
			numericValue.rDigits is not None or 	# must not have '.' or rDigits
			numericValue.eDigits is not None):		# must not have an exponent
			raise ValueError("Illegal literal for SByte: %s"%self.JoinNumericLiteral(numericValue))
		self.SetFromPyValue(int(self.JoinNumericLiteral(numericValue)))		

	def SetFromPyValue(self,newValue):
		"""*newValue* must be of type int, long, float or Decimal.
		
		If the value is a float or fractional Decimal then it is rounded
		towards zero using the python *int* function."""
		if newValue is None:
			self.pyValue=None
		elif isinstance(newValue,decimal.Decimal) or type(newValue) in (IntType, LongType, FloatType):
			if newValue<-128 or newValue>127:
				raise ValueError("Illegal value for SByte: %s"%str(newValue))
			self.pyValue=int(newValue)
		else:
			raise TypeError("Can't set SByte from %s"%str(newValue))	


SimpleValue._TypeClass={
	SimpleType.Binary:BinaryValue,
	SimpleType.Boolean:BooleanValue,
	SimpleType.Byte:ByteValue,
	SimpleType.DateTime:DateTimeValue,
	SimpleType.DateTimeOffset:DateTimeOffsetValue,
	SimpleType.Time:TimeValue,
	SimpleType.Decimal:DecimalValue,
	SimpleType.Double:DoubleValue,
	SimpleType.Single:SingleValue,
	SimpleType.Guid:GuidValue,
	SimpleType.Int16:Int16Value,
	SimpleType.Int32:Int32Value,
	SimpleType.Int64:Int64Value,
	SimpleType.String:StringValue,
	SimpleType.SByte:SByteValue
	}

	
class TypeInstance(DictionaryLike):
	"""Abstract class to represents a single instance of a
	:py:class:`ComplexType` or :py:class:`EntityType`.
	
	Behaves like a read-only dictionary mapping property names onto
	:py:class:`EDMValue` instances.  (You can change the value of a property
	using the methods of :py:class:`EDMValue` and its descendants.)
	
	TODO: In the future, open types will allow items to be set or deleted."""
	def __init__(self,typeDef=None):
		self.typeDef=typeDef		#: the definition of this type
		self.data={}				#: a dictionary to hold this instances' property values
		if typeDef is not None:
			for p in self.typeDef.Property:
				self.CreateProperty(p)

	def CreateProperty(self,p):
		"""Given a :py:class:`Property` instance creates a new value in the value dictionary"""
		self.data[p.name]=p()
		
	def AddProperty(self,pName,pValue):
		"""Adds a property with name *pName* and value *pValue* to this instance."""
		self.data[pName]=pValue
		
	def __getitem__(self,name):
		"""Returns the value corresponding to property *name*."""
		return self.data[name]
	
# 	def __setitem__(self,name,value):
# 		"""Sets the value of the property *name*. TODO: dynamic properties only
# 		
# 		If name is not the name of a recognized property KeyError is raised.
# 		
# 		*value* must be a :py:class:`EDMValue` instance of a type that
# 		matches the declaration of the proerty.  The value's name attribute is
# 		set to *name* on success."""
# 		if name in self.data:
# 			oldValue=self.data[name]
# 			if value.__class__ is not oldValue.__class__:
# 				raise TypeError("%s required for property %s"%
# 				self.data[name]
# 			self.data[name]=value
# 		else:
# 			raise KeyError("%s is not a property of %s"%(name,self.typeDef.name))
			
	def __iter__(self):
		"""Iterates over the property names in the order they are declared in the type definition."""
		for p in self.typeDef.Property:
			yield p.name
				
	def __len__(self):
		"""Returns the number of properties in the type."""
		return len(self.typeDef.Property)

# 	def update(self,items):
# 		"""Overridden to remove the call to clear"""
# 		for key,value in items:
# 			self[key]=value


class Complex(EDMValue,TypeInstance):
	"""Represents a single instance of a :py:class:`ComplexType`.
	
	*	name is the (optional) name of the value
	
	*	complexType is the type of object this is an instance of"""

	def __init__(self,complexType=None,name=None):
		EDMValue.__init__(self,name)
		TypeInstance.__init__(self,complexType)
	
	def IsNull(self):
		"""Complex values are never Null"""
		return False


class CSDLElement(xmlns.XMLNSElement):
	
	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		"""Called on a type definition, or type containing object to update all
		its inter-type references.
		
		*	scope is the :py:class:`NameTableMixin` object *containing* the
			top-level :py:class:`Schema` object(s).

		*	stopOnErrors determines the handling of missing keys.  If
			stopOnErrors is False missing keys are ignored (internal object
			references are set to None).  If stopOnErrors is True KeyError is
			raised.
			 
		The CSDL model makes heavy use of named references between objects. The
		purpose of this method is to use the *scope* object to look up
		inter-type references and to set or update any corresponding internal
		object references."""
		pass

	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""Called on a set declaration, or set containing object to update all
		its inter-object references.
		
		This method works in a very similar way to :py:meth:`UpdateTypeRefs` but
		it is called afterwards.  This two-pass approach ensures that set
		declarations are linked after *all* type definitions have been updated
		in all schemas that are in scope."""
		pass


class TypeRef:
	"""Represents a type reference.
	
	Created from a formatted string type definition and a scope (in which
	definitions are looked up)."""
	
	def __init__(self,typeDef,scope):
		self.collection=False		#: True if this type is a collection type
		self.simpleTypeCode=None	#: a :py:class:`SimpleType` value if this is a scalar type
		self.typeDef=None			#: a :py:class:`ComplexType` or :py:class:`EntityType` instance.
		if "(" in typeDef and typeDef[-1]==')':
			if typeDef[:typeDef.index('(')].lower()!=u"collection":
				raise KeyError("%s is not a valid type"%typeDef)
			self.collection=True
			typeName=typeDef[typeDef.index('(')+1:-1]
		else:
			typeName=typeDef
		try:
			self.simpleTypeCode=SimpleType.DecodeLowerValue(typeName)
		except ValueError:
			# must be a complex or entity type defined in scope
			self.simpleTypeCode=None
			self.typeDef=scope[typeName]
			if not isinstance(self.typeDef,(ComplexType,EntityType)):
				raise KeyError("%s is not a valid type"%typeName)
	

class Using(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Using')


MAX=-1		#: we define the constant MAX to represent the spacial 'max' value of maxLength

def DecodeMaxLength(value):
	"""Decodes a maxLength value from a unicode string.
	
	"The maxLength facet accepts a value of the literal string "max" or a
	positive integer with value ranging from 1 to 2^31"
	
	The value 'max' is returned as the value :py:data:`MAX`"""
	if value.lower()=="max":
		return MAX
	else:
		result=xsi.DecodeInteger(value)
		if result<1:
			raise ValueError("Can't read maxLength from %s"%repr(value))
		return result


def EncodeMaxLength(value):
	"""Encodes a maxLength value as a unicode string."""
	if value==MAX:
		return "max"
	else:
		return xsi.EncodeInteger(value)

	
class Property(CSDLElement):
	"""Models a property of an :py:class:`EntityType` or :py:class:`ComplexType`."""

	XMLNAME=(EDM_NAMESPACE,'Property')

	XMLATTR_Name='name'
	XMLATTR_Type='type'
	XMLATTR_Nullable=('nullable',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_DefaultValue='defaultValue'
	XMLATTR_MaxLength=('maxLength',DecodeMaxLength,EncodeMaxLength)
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
		self.name="Default"			#: the declared name of the property
		self.type="Edm.String"		#: the name of the property's type
		self.simpleTypeCode=None	#: one of the :py:class:`SimpleType` constants if the property has a simple type
		self.complexType=None		#: the associated :py:class:`ComplexType` if the property has a complex type
		self.nullable=True			#: if the property may have a null value
		self.defaultValue=None		#: a string containing the default value for the property or None if no default is defined
		self.maxLength=None			#: the maximum length permitted for property values 
		self.fixedLength=None		#: a boolean indicating that the property must be of length :py:attr:`maxLength`
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

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`simpleTypeCode` and :py:attr:`complexType`."""
		try:
			self.simpleTypeCode=SimpleType.DecodeLowerValue(self.type)
			self.complexType=None
		except ValueError:
			# must be a complex type defined elsewhere
			self.simpleTypeCode=None
			try:
				self.complexType=scope[self.type]
				if not isinstance(self.complexType,ComplexType):
					raise KeyError("%s is not a simple or ComplexType"%self.type)
			except KeyError:
				self.complexType=None		
				if stopOnErrors:
					raise
	
	def __call__(self,literal=None):
		"""Returns a new :py:class:`EDMValue` instance (from a literal).
		
		Complex values can't be created from a simple literal form."""
		if self.simpleTypeCode is not None:
			result=SimpleValue.NewValue(self.simpleTypeCode,self.name)
			if literal is not None:
				result.SetFromLiteral(literal)
		elif self.complexType is not None:
			result=Complex(self.complexType,self.name)
		else:
			raise ModelIncomplete("Property %s not bound to a type"%self.name)
		return result
			
	def DecodeValue(self,value):
		"""Decodes a value from a string used in a serialised form.
		
		The returned type depends on the property's :py:attr:`simpleTypeCode`."""
		if value is None:
			return None
		decoder,encoder=SimpleTypeCodec.get(self.simpleTypeCode,(None,None))
		if decoder is None:
			# treat as per string
			return value
		else:
			return decoder(value)

	def EncodeValue(self,value):
		"""Encodes a value as a string ready to use in a serialised form.
		
		The input type depends on the property's :py:attr:`simpleTypeCode`"""
		if value is None:
			return None
		decoder,encoder=SimpleTypeCodec.get(self.simpleTypeCode,(None,None))
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
		self.name="Default"		#: the declared name of the navigation property
		self.relationship=None	#: the name of the association described by this link
		self.association=None	#: the :py:class:`Association` described by this link 
		self.fromRole=None		#: the name of this link's source role
		self.toRole=None		#: the name of this link's target role
		self.fromEnd=None		#: the :py:class:`AssociationEnd` instance representing this link's source
		self.toEnd=None			#: the :py:class:`AssociationEnd` instance representing this link's target
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

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`association`, :py:attr:`fromEnd` and :py:attr:`toEnd`."""
		# must be a complex type defined elsewhere
		self.association=self.fromEnd=self.toEnd=None
		try:
			self.association=scope[self.relationship]
			if not isinstance(self.association,Association):
				raise KeyError("%s is not an association"%self.relationship)
			self.fromEnd=self.association[self.fromRole]
			if self.fromEnd is None or not isinstance(self.fromEnd,AssociationEnd):
				raise KeyError("%s is not a valid end-point for %s"%(self.fromRole,self.relationship))
			self.toEnd=self.association[self.toRole]
			if self.toEnd is None or not isinstance(self.toEnd,AssociationEnd):
				raise KeyError("%s is not a valid end-point for %s"%(self.fromRole,self.relationship))
		except KeyError:
			self.association=self.fromEnd=self.toEnd=None
			if stopOnErrors:
				raise
		
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

	def GetChildren(self):
		for child in self.PropertyRef: yield child

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		for pr in self.PropertyRef:
			pr.UpdateTypeRefs(scope,stopOnErrors)

	def UpdateFingerprint(self,h):
		h.update("Key:")
		for pr in self.PropertyRef:
			pr.UpdateFingerprint(h)
		h.update(";")



class PropertyRef(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'PropertyRef')
	
	XMLATTR_Name='name'

	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name='Default'		#: the name of this (key) property
		self.property=None		#: the :py:class:`Property` instance of this (key) property

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`property`"""
		self.property=None
		try:
			typeDef=self.FindParent(EntityType)
			if typeDef is None:
				raise KeyError("PropertyRef %s has no parent EntityType"%self.name)
			self.property=typeDef[self.name]
			if not isinstance(self.property,Property):
				raise KeyError("%s is not a Property"%self.name)
		except KeyError:
			self.property=None
			if stopOnErrors:
				raise

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
		self.name="Default"		#: the declared name of this type
		self.baseType=None		#: the name of the base-type for this type
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

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		for p in self.Property:
			p.UpdateTypeRefs(scope,stopOnErrors)
	
	def GetFQName(self):
		"""Returns the full name of this type, including the schema namespace prefix."""
		schema=self.FindParent(Schema)
		if schema is None:
			return name
		else:
			return string.join((schema.name,'.',self.name),'')
		
		
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

	def ValidateExpansion(self,expand,select):
		if expand is None:
			expand={}
		if select is None:
			select={}
		for name,value in select.iteritems():
			if name=="*":
				# must be the last item in the selectItem
				if value is not None:
					raise ValueError("selectItem after *")
			else:
				try:
					p=self[name]
					if isinstance(p,Property):
						if value is not None:
							raise ValueError("selectItem after selectedProperty %s"%name)
					elif isinstance(p,NavigationProperty):
						# for a navigation property, we have to find the target entity type
						if name in expand:
							subExpand=expand[name]
						else:
							subExpand=None
						p.toEnd.entityType.ValidateExpansion(subExpand,value)
					else:
						raise KeyError
				except KeyError:
					raise ValueError("%s is not a property of %s"%(name,self.name))
		for name,value in expand.iteritems():
			try:
				p=self[name]
				if isinstance(p,NavigationProperty):
					# only navigation properties need apply
					if name in select:
						# then we've already been here
						pass
					else:					
						p.toEnd.entityType.ValidateExpansion(value,None)
				else:
					raise KeyError
			except KeyError:
				raise ValueError("%s is not a navigation property of %s"%(name,self.name))
					
	def UpdateFingerprint(self,h):
		if self.Key:
			self.Key.UpdateFingerprint(h)
		h.update("EntityType:")
		h.update(self.name)
		h.update(";")
		for p in self.Property+self.NavigationProperty:
			p.UpdateFingerprint(h)

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		super(EntityType,self).UpdateTypeRefs(scope,stopOnErrors)
		for p in self.NavigationProperty:
			p.UpdateTypeRefs(scope,stopOnErrors)
		self.Key.UpdateTypeRefs(scope,stopOnErrors)

	
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


class Association(NameTableMixin,CSDLElement):
	"""Models an association; behaves as dictionary of AssociationEnd keyed on role name."""
	XMLNAME=(EDM_NAMESPACE,'Association')
	XMLATTR_Name='name'

	def __init__(self,parent):
		NameTableMixin.__init__(self)
		CSDLElement.__init__(self,parent)
		self.name="Default"			#: the name declared for this association
		self.Documentation=None
		self.AssociationEnd=[]
		self.ReferentialConstraint=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
	
	@classmethod
	def GetElementClass(cls,name):
		if xmlns.NSEqualNames((EDM_NAMESPACE,'End'),name,EDM_NAMESPACE_ALIASES):
			return AssociationEnd
		else:
			return None
		
	def ContentChanged(self):
		for ae in self.AssociationEnd:
			self.Declare(ae)
		
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in self.AssociationEnd: yield child
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
		for e in self.AssociationEnd:
			e.UpdateFingerprint(h)

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		for iEnd in self.AssociationEnd:
			iEnd.UpdateTypeRefs(scope,stopOnErrors)

			
class AssociationEnd(CSDLElement):
	# XMLNAME=(EDM_NAMESPACE,'End')
	
	XMLATTR_Role='name'
	XMLATTR_Type='type'
	XMLATTR_Multiplicity=('multiplicity',DecodeMultiplicity,EncodeMultiplicity)
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name=None			#: the role-name given to this end of the link
		self.type=None			#: name of the entity type this end links to
		self.entityType=None	#: :py:class:`EntityType` this end links to
		self.multiplicity=1		#: a :py:class:`Multiplicity` constant
		self.otherEnd=None		#: the other :py:class:`AssociationEnd` of this link
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

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`entityType` and :py:attr:`otherEnd`."""
		try:
			self.entityType=self.otherEnd=None
			self.entityType=scope[self.type]
			if not isinstance(self.entityType,EntityType):
				raise "AssociationEnd not bound to EntityType (%s)"%self.type
			if not isinstance(self.parent,Association) or not len(self.parent.AssociationEnd)==2:
				raise ModelIncomplete("AssociationEnd has missing or incomplete parent (Role=%s)"%self.name)
			for iEnd in self.parent.AssociationEnd:
				if iEnd is self:
					continue
				else:
					self.otherEnd=iEnd
		except KeyError:
			self.entityType=self.otherEnd=None
			if stopOnErrors:
				raise


class EntityContainer(NameTableMixin,CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'EntityContainer')

	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_Extends='extends'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		NameTableMixin.__init__(self)
		self.name="Default"			#: the declared name of the container
		self.Documentation=None
		self.FunctionImport=[]
		self.EntitySet=[]
		self.AssociationSet=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
	
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.EntitySet,
			self.AssociationSet,
			self.FunctionImport,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child		

	def ContentChanged(self):
		for t in self.EntitySet+self.AssociationSet+self.FunctionImport:
			self.Declare(t)

	def UpdateFingerprint(self,h):
		h.update("EntityContainer:")
		h.update(self.name)
		h.update(";")
		for t in self.EntitySet+self.AssociationSet:
			t.UpdateFingerprint(h)

	def UpdateSetRefs(self,scope,stopOnErrors=False):
		for child in self.EntitySet+self.AssociationSet+self.FunctionImport:
			child.UpdateSetRefs(scope,stopOnErrors)
		for child in self.EntitySet:
			child.UpdateNavigation()
					
	
class Entity(TypeInstance):
	"""Represents a single instance of an :py:class:`EntityType`.
	
	*	entitySet is the entity set this entity belongs to
	
	Behaves like a read-only dictionary mapping property names onto
	values.
	
	On construction, an entity contains keys (and values) for its simple
	and complex properties, inheriting this behaviour from
	:py:class:`TypeInstance`.  The dictionary itself does not
	support assignment, to update values use an appropriate method of
	the :py:class:`EDMValue` object.  For example::
	
		e['Name'].SetFromPyValue("Steve")

	You can expand the entity's dictionary to include keys for
	navigation properties or remove keys for unused properties using
	:py:meth:`Expand`"""
	def __init__(self,entitySet):
		self.entitySet=entitySet
		TypeInstance.__init__(self,entitySet.entityType)
		self.expand=None		#: the expand rules in effect for this entity
		self.select=None		#: the select rules in effect for this entity
		self._selectAll=True
		if self.typeDef is None:
			raise ModelIncomplete("Unbound EntitySet: %s (%s)"%(self.entitySet.name,self.entitySet.entityTypeName))
		
	def Key(self):
		"""Returns the entity key as a single python value or a tuple of
		python values for compound keys.
		
		The order of the values is the order of the PropertyRef definitions
		in the associated EntityType's :py:class:`Key`."""
		if len(self.typeDef.Key.PropertyRef)==1:
			return self[self.typeDef.Key.PropertyRef[0].name].pyValue
		else:
			k=[]
			for pRef in self.typeDef.Key.PropertyRef:
				k.append(self[pRef.name].pyValue)
			return tuple(k)
	
	def KeyDict(self):
		"""Returns the entity key as a dictionary mapping key property
		names onto :py:class:`SimpleValue` instances."""
		k={}
		for pRef in self.typeDef.Key.PropertyRef:
			k[pRef.name]=self[pRef.name]
		return k
				
	def Navigation(self):
		"""Iterates through the names of this entity's navigation properties."""
		for np in self.typeDef.NavigationProperty:
			yield np.name
			
	def IsEntityCollection(self,name):
		"""Returns True if more than one entity is possible when navigating the named property."""
		return self.entitySet.IsEntityCollection(name)
			
	def Navigate(self,name):
		"""Returns one of:
		
		*	None
				
		*	An instance of :py:class:`Entity`
				
		*	An instance of :py:class:`EntityCollection`

		The entities returned are those linked to this entity by the
		named navigation property.

		You can use :py:meth:`IsEntityCollection` to determine which
		form of response is expected.

		This method is a simple wrapper for
		:py:meth:`EntitySet.Navigate`."""
		result=self.entitySet.Navigate(name,self)
		if result is not None:
			if self.expand and name in self.expand:
				expand=self.expand[name]
			else:
				expand=None
			if self.select and name in self.select:
				select=self.select[name]
			else:
				select=None
			result.Expand(expand,select)
		return result
	
	def Expand(self,expand, select=None):
		"""Expands *entity* according to the given expand rules (if any).

		*expand* is a dictionary of expand rules.  Expansions can be chained,
		represented by the dictionary entry also being a dictionary::
				
			# expand the Customer navigation property...
			{ 'Customer': None }
			# expand the Customer and Invoice navigation properties
			{ 'Customer':None, 'Invoice':None }
			# expand the Customer property and then the Orders property within Customer
			{ 'Customer': {'Orders':None} }
		
		The expansion rule in effect are saved in the :py:attr:`expand`
		member and are tested using :py:meth:`Expanded`.
		
		The *select* option is a similar dictionary structure that can
		be used to filter the properties in the entity.  If a property
		that is being expanded is also subject to one or more selection
		rules these are passed along with the chained Expand call.
		
		The selection rules in effect are saved in the :py:attr:`select`
		member and can be tested using :py:meth:`Selected`."""
		self.select=select
		self.expand=expand
		if self.select is None:
			self._selectAll=True
		else:
			self._selectAll=u"*" in select
	
	def Expanded(self,name):
		"""Returns true if the property *name* should be expanded by
		the expansion rules in this entity."""
		return self.expand and name in self.expand
		
	def Selected(self,name):
		"""Returns true if the property *name* is selected by the
		selection rules in this entity.
		
		The entity always has keys for its simple and complex properties
		but whether or not the dictionary values represent the true value
		of the property *may* depend on whether the property is selected.
		In particular, a property value that is Null may indicate that the
		named property has a Null value or simply that it hasn't been
		selected::
		
			if e['Name']:
				print "Name is not NULL"
			elif e.Selected('Name'):
				print "Name is NULL"
				# we know because it has been selected
			else:
				print "NULL status of Name is unknown"
				# we don't know because it hasn't been selected
		"""
		if self._selectAll:
			return True
		else:
			return self.select and name in self.select
	
	def ETag(self):
		"""Returns an EDMValue instance to use as in optimistic
		concurrency control or None if the entity does not support it."""
		for pDef in self.typeDef.Property:
			if pDef.concurrencyMode and pDef.concurrencyMode.lower()=="fixed":
				etag=self[pDef.name]
				if etag:
					return etag
		return None

	def ETagIsStrong(self):
		"""Returns True if this entity's etag is a strong entity tag as defined
		by RFC2616::
		
		A "strong entity tag" MAY be shared by two entities of a
		resource only if they are equivalent by octet equality.
		
		The default implementation returns False."""
		return False
		

class EntitySet(CSDLElement):
	"""Represents an EntitySet in the CSDL model."""
	XMLNAME=(EDM_NAMESPACE,'EntitySet')	
	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_EntityType='entityTypeName'
	XMLCONTENT=xmlns.ElementType.ElementContent

#	EntityCollectionClass=EntityCollection	#: the class to use for representing entity collections
	
	def __init__(self,parent):
		super(EntitySet,self).__init__(parent)
		self.name="Default"				#: the declared name of the entity set
		self.entityTypeName=""			#: the name of the entity type of this set's elements 
		self.entityType=None			#: the :py:class:`EntityType` of this set's elements
		self.navigation={}				#: a mapping from navigation property names to AssociationSetEnd instances
		self.binding=(EntityCollection,{})
		"""A class (or callable) and a dict of named arguments to pass
		to it that returns a
		:py:class:`EntityCollection` instance, by default we are bound
		to the default EntityCollection class which is always empty! You
		can change the binding using the :py:meth:`Bind` method."""  
		self.navigationBindings={}
		"""A mapping from navigation property names to a tuple
		comprising a class (or callable) and a dict of named arguments
		to pass to it that returns a
		:py:class:`NavigationEntityCollection` instance and a list of
		extra arguments to pass to it.  By default we are bound to the
		default NavigationEntityCollection class which is always empty.
		You can change the bindings using the :py:meth:`BindNavigation`
		method."""
		self.Documentation=None
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
		self.location=""			#: see :py:meth:`SetLocation`

	def GetFQName(self):
		"""Returns the fully qualified name of this entity set."""
		name=[]
		if isinstance(self.parent,EntityContainer):
			if isinstance(self.parent.parent,Schema):
				name.append(self.parent.parent.name)
			name.append(self.parent.name)
		name.append(self.name)
		return string.join(name,'.')
		
	def SetLocation(self):
		"""Sets :py:attr:`location` to a URI derived by resolving a relative path consisting
		of::
		
			[ EntityContainer.name '.' ] name"""
		container=self.FindParent(EntityContainer)
		if container:
			path=container.name+'.'+self.name
		else:
			path=self.name
		self.location=self.ResolveURI(path)

	def ContentChanged(self):
		super(EntitySet,self).ContentChanged()
		self.SetLocation()
				
	def GetChilren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child		
		
	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`entityType`"""
		try:
			self.entityType=scope[self.entityTypeName]
			if not isinstance(self.entityType,EntityType):
				raise KeyError("%s is not an EntityType"%self.entityTypeName)
		except KeyError:
			self.entityType=None
			if stopOnErrors:
				raise
	
	def UpdateNavigation(self):
		"""Called after UpdateTypeRefs once references have been updated for all
		association sets in this container."""
		container=self.FindParent(EntityContainer)
		if container:
			for np in self.entityType.NavigationProperty:
				# now look for an AssociationSet in our container that references the same association
				if np.association is None:
					continue
				for associationSet in container.AssociationSet:
					if np.association is associationSet.association:
						for iEnd in associationSet.AssociationSetEnd:
							if iEnd.associationEnd is np.fromEnd:
								self.navigation[np.name]=iEnd
								break
			
	def UpdateFingerprint(self,h):
		h.update("EntitySet:")
		h.update(self.name)
		h.update(";")
		h.update(self.entityTypeName)
		h.update(";")
	
	def GetKey(self,keylike):
		"""Extracts a key value suitable for using as a key in an
		:py:class:`EntityCollection` based on this entity set.
		
		Keys are represented as python values (as described in
		:py:class:`SimpleValue`) or as tuples of python values in the
		case of compound keys.  The order of the values in a compound
		key is the order in which the Key properties are defined in the
		corresponding EntityType definition. 
		
		If *keylike* is already in the correct format for this entity
		type then it is returned unchanged.
		
		If the key is single-valued and *keylike* is a tuple containing
		a single value then the single value is returned without the
		tuple wrapper.
	
		If *keylike* is a dictionary, or an :py:class:`Entity` instance,
		which maps property names to values (or to
		:py:class:`SimpleValue` instances) the key is calculated from it
		by extracting the key properties.  As a special case, a value
		mapped with a dictionary key of the empty string is assumed to
		be the value of the key property for an entity type with a
		single-valued key, but only if the key property's name is not
		itself in the dictionary.

		If *keylike* cannot be turned in to a valid key the KeyError is
		raised."""
		if type(keylike) is TupleType:
			if len(self.entityType.Key.PropertyRef)==1:
				if len(keylike)==1:
					return keylike[0]
				else:
					raise KeyError("Unexpected compound key: %s"%repr(keylike))
		elif type(keylike) is DictType or isinstance(keylike,Entity):
			k=[]
			for kp in self.entityType.Key.PropertyRef:
				try:
					kv=keylike[kp.name]
				except KeyError:
					if len(self.entityType.Key.PropertyRef)==1:
						# a single key, look up the empty string instead
						if '' in keylike:
							kv=keylike['']
						else:
							raise
					else:
						raise	
				if isinstance(kv,SimpleValue):
					kv=kv.pyValue					
				k.append(kv)
			if len(k)==1:
				return k[0]
			else:
				return tuple(k)
		else:
			return keylike
				
	def GetLinkEnd(self,name):
		"""Returns an AssociationSetEnd from a navigation property name."""
		return self.navigation[name]

	def Bind(self,entityCollectionBinding,**extraArgs):
		"""Binds this entity set to a specific class or callable used by :py:meth:`GetCollection`""" 
		self.binding=entityCollectionBinding,extraArgs
		
	def GetCollection(self):
		"""Returns an :py:class:`EntityCollection` instance suitable for
		accessing the entities themselves.
		
		This method must be overridden to return a concrete
		implementation of an entity collection.  The default
		implementation returns an instance of the (almost abstract)
		EntityCollection."""
		cls,extraArgs=self.binding
		return cls(self,**extraArgs)
	
	def BindNavigation(self,name,entityCollectionBinding,**extraArgs):
		"""Binds the navigation property *name* to a class or callable
		used by :py:meth:`Navigate`"""
		self.navigationBindings[name]=(entityCollectionBinding,extraArgs)

	def IsEntityCollection(self,name):
		"""Returns True if more than one entity is possible when navigating the named property."""
		linkEnd=self._getLinkEnd(name)
		return linkEnd.otherEnd.associationEnd.multiplicity==Multiplicity.Many
			
	def Navigate(self,name,sourceEntity,expand=None):
		"""See :py:meth:`Entity.Navigate` for more information.
		
		The entities returned are those linked, by this navigation property, from the
		entity with *key*.
		
		You can use :py:meth:`IsEntityCollection` to determine which
		form of response is expected."""
		cls,extraArgs=self.navigationBindings[name]
		linkEnd=self._getLinkEnd(name)
		toEntitySet=linkEnd.otherEnd.entitySet
		if linkEnd.otherEnd.associationEnd.multiplicity==Multiplicity.Many:
			return cls(name,sourceEntity,toEntitySet,**extraArgs)
		else:
			collection=list(cls(name,sourceEntity,toEntitySet,**extraArgs).itervalues())
			if len(collection)==1:
				return collection[0]
			elif len(collection)==0:
				return None
			else:
				raise KeyError("Navigation error: %s yielded multiple entities"%name)
	
	def _getLinkEnd(self,name):
		try:
			linkEnd=self.navigation[name]
		except KeyError:
			if name in self.entityType:
				np=self.entityType[name]
				if isinstance(np,NavigationProperty):
					# This should have worked but the link must be incomplete
					raise ModelIncomplete("Unbound NavigationProperty: %s (%s)"%(np.name,np.relationship))
			raise
		return linkEnd
									

class AssociationSet(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'AssociationSet')
	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_Association='associationName'
	XMLCONTENT=xmlns.ElementType.ElementContent
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"			#: the declared name of this association set
		self.associationName=""		#: the name of the association definition
		self.association=None		#: the :py:class:`Association` definition
		self.Documentation=None
		self.AssociationSetEnd=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
	
	@classmethod
	def GetElementClass(cls,name):
		if xmlns.NSEqualNames((EDM_NAMESPACE,'End'),name,EDM_NAMESPACE_ALIASES):
			return AssociationSetEnd
		else:
			return None
		
	def GetChilren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.AssociationSetEnd,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child		

	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`association`"""
		try:
			self.association=scope[self.associationName]
			if not isinstance(self.association,Association):
				raise KeyError("%s is not an Association"%self.associationName)
			for iEnd in self.AssociationSetEnd:
				iEnd.UpdateSetRefs(scope,stopOnErrors)
		except KeyError:
			self.association=None
			if stopOnErrors:
				raise
		
	def UpdateFingerprint(self,h):
		h.update("AssociationSet:")
		h.update(self.name)
		h.update(";")
		h.update(self.associationName)
		h.update(";")
				

class AssociationSetEnd(CSDLElement):
	"""The AssociationSetEnd represents the links between two actual sets of entities.
	
	This class must be overridden by a data service that wishes to
	support navigation properties.  In effect, the AssociationSetEnd is
	the index that allows two EntitySets to be joined.  They are
	directional, it is not required to support bi-directional
	associations.  The navigation itself is done using the
	:py:meth:`Navigate` method.""" 
	# XMLNAME=(EDM_NAMESPACE,'End')
	
	XMLATTR_Role='name'
	XMLATTR_EntitySet='entitySetName'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name=None				#: the role-name given to this end of the link
		self.entitySetName=None		#: name of the entity set this end links to
		self.entitySet=None			#: :py:class:`EntitySet` this end links to
		self.associationEnd=None	#: :py:class:`AssociationEnd` that defines this end of the link
		self.otherEnd=None			#: the other :py:class:`AssociationSetEnd` of this link
		self.Documentation=None
	
	def GetChildren(self):
		if self.Documentation: yield self.Documentation
		for child in CSDLElement.GetChildren(self): yield child

# 	def IsEntityCollection(self):
# 		"""Returns True if navigating via this association set can yield multiple entities."""
# 		return self.otherEnd.associationEnd.multiplicity==Multiplicity.Many
# 				   
	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`entitySet`, :py:attr:`otherEnd` and :py:attr:`associationEnd`.
		
		Role names on AssociationSetName are marked as optional but it can make
		it a challenge to work out which end of the association is which if one
		or both are missing.  In fact, it would be possible to have two
		identical Ends!  The algorithm we use is to use Role names if either are
		given, otherwise we match the entity types (if these are also identical
		then the choice is arbitrary). When we're done, we copy any missing Role
		names across to reduce confusion."""
		try:
			self.entitySet=self.otherEnd=self.associationEnd=None
			container=self.FindParent(EntityContainer)
			if container:
				self.entitySet=container[self.entitySetName]
			if not isinstance(self.entitySet,EntitySet):
				raise ModelIncomplete("AssociationSetEnd not bound to EntitySet (%s)"%self.entitySetName)
			if not isinstance(self.parent,AssociationSet) or not len(self.parent.AssociationSetEnd)==2:
				raise ModelIncomplete("AssociationSetEnd has missing or incomplete parent (Role=%s)"%self.name)
			for iEnd in self.parent.AssociationSetEnd:
				if iEnd is self:
					continue
				else:
					self.otherEnd=iEnd
			for iEnd in self.parent.association.AssociationEnd:
				if self.name:
					if self.name==iEnd.name:
						# easy case, names match
						self.associationEnd=iEnd
						break
				elif self.otherEnd.name:
					if self.otherEnd.name==iEnd.name:
						# so we match the end of iEnd!
						self.associationEnd=iEnd.otherEnd
						# Fix up the role name while we're at it
						self.name=self.associationEnd.name
						break
				else:
					# hard case, two blank associations
					if iEnd.entityType is self.entitySet.entityType:
						self.associationEnd=iEnd
						self.name=self.associationEnd.name
						break
			if self.associationEnd is None:
				raise ModelIncomplete("Failed to match AssociationSetEnds to their definitions: %s"%self.parent.name)
		except KeyError:
			self.entitySet=self.otherEnd=self.associationEnd=None
			if stopOnErrors:
				raise


class EntityCollection(DictionaryLike):
	"""Represents a collection of entities from an :py:class:`EntitySet`.

	To use a database analogy, EntitySet's are like tables whereas
	EntityCollections are somewhat like database cursors you use to read
	data from those tables.
	
	Entity collections behave like a python dictionary of
	:py:class:`Entity` instances keyed on a value representing the
	Entity's key property or properties.  The keys are either single
	values of the key property or tuples in the case of compound keys.
	The order of the values in the tuple is taken from the order of the
	PropertyRef definitions in the Entity's Key.

	You can obtain a canonical representation of the key from an
	:py:class:`Entity` instance or other dictionary like object using
	the :py:meth:`EntitySet.GetKey` method.
	
	Derived classes MUST override :py:meth:`itervalues` and for
	writeable data sources,	:py:meth:`__setitem__` and
	py:meth:`__delitem__`.
	
	The implementation of itervalues must return an iterable object that
	honours the value of the expand query option.

	Derived classes SHOULD also override :py:meth:`__getitem__`,
	:py:meth:`__len__` and :py:meth:`clear` as the default
	implementations are very inefficient.
		
	Helper methods are provided if no native optimisations for query
	options are available though."""
	def __init__(self,entitySet):
		self.entitySet=entitySet		#: the entity set from which the entities are drawn
		self.name=self.entitySet.name	#: the name of :py:attr:`entitySet`
		self.expand=None				#: the expand query option in effect
		self.select=None				#: the select query option in effect
		self.filter=None				#: a filter or None for no filter (see :py:meth:`CheckFilter`)
		self.orderby=None				#: a list of orderby rules
		self.skip=None					#: the skip query option in effect
		self.top=None					#: the top query option in effect
		self.topmax=None				#: the forced maximum page size in effect
		self.skiptoken=None				#: the skiptoken option in effect
		self.nextSkiptoken=None
		self.count=None
		"""the size of this collection, initially None
		
		As there may be a penalty for calculating the overall size of
		the collection this attribute is initialised to None and updated by __len__
		the first time it is called and then used to prevent unnecessary
		recalculation.

		If any options affecting the size of the collection are altered
		then count should be reset to None to force __len__ to
		recalculate the size of the collection."""
		self.inlineCount=False
		"""True if inlineCount option is in effect 
		
		The inlineCount option is used to alter the representation of
		the collection and, if set, indicates that the __len__ method
		will be called before iterating through the collection itself."""
		self.lastYielded=None
		self.lastGot=None
	
	def GetLocation(self):
		"""Returns the location of this collection as a
		:py:class:`rfc2396.URI` instance.
		
		By default, the location is given as the location of the
		:py:attr:`entitySet` from which the entities are drawn."""
		return self.entitySet.location
	
	def GetTitle(self):
		"""Returns a user recognisable title for the collection.
		
		By default this is the fully qualified name of the entity set."""
		return self.entitySet.GetFQName()
			
	def Expand(self,expand,select=None):
		"""Sets the expand and select query options for this collection.
		
		The expand query option causes the named navigation properties
		to be expanded and the associated entities to be loaded in to
		the entity instances returned by this collection.
		
		The select query option restricts the properties that are set in
		returned entities.
		
		For more details, see :py:meth:`Entity.Expand`"""
		self.expand=expand
		self.select=select

	def ExpandEntities(self,entityIterable):
		"""Given an object that iterates over all entities in the
		collection, returns a generator function that returns those
		entities expanded and selected according to :py:attr:`expand`
		and :py:attr:`select` rules."""
		for e in entityIterable:
			if self.expand:
				e.Expand(self.expand,self.select)
			yield e
			
	def Filter(self,filter):
		"""Sets the filter object for this collection, see :py:meth:`CheckFilter`."""
		self.filter=filter
		self.count=None
		
	def FilterEntities(self,entityIterable):
		"""Given an object that iterates over all entities in the
		collection, returns a generator function that returns only those
		entities that pass through the current :py:attr:`filter` object."""
		for e in entityIterable:
			if self.CheckFilter(e):
				yield e
		
	def CheckFilter(self,entity):
		"""Checks *entity* against the current filter object and returns
		True if it passes.
		
		The default implementation does not actually support any filters
		so if a filter object has been defined, NotImplementedError is
		raised."""
		if self.filter is None:
			return True
		else:
			raise NotImplementedError("Collection does not support filtering")

	def OrderBy(self,orderby):
		"""Sets the orderby rules for this collection.
		
		*orderby* is a list of tuples, each consisting of::
		
			 ( an order object as used by :py:meth:`CalculateOrderKey` , 1 | -1 )"""
		self.orderby=orderby

	def CalculateOrderKey(self,entity,orderObject):
		"""Given an entity and an order object returns the key used to sort the entity.
		
		The default implementation does not actually support any custom
		orderings so if an orderby rule is defined, NotImplementedError
		is raised."""
		raise NotImplementedError("Collection does not support ordering")
		
	def OrderEntities(self,entityIterable):
		"""Given an object that iterates over the entities in random
		order, returns a generator function that returns the same
		entities in sorted order (according to :py:attr:`orderby` object
		or the entity keys if there is no custom ordering and top or
		skip has been specified).
		
		This implementation simply creates a list and then sorts it so
		is not suitable for use with long lists of entities.  However, if
		no ordering is required then no list is created."""
		if self.orderby:
			eList=list(entityIterable)
			# we avoid Py3 warnings by doing multiple sorts with a key function 
			for rule,ruleDir in reversed(self.orderby):
				eList.sort(key=lambda x:self.CalculateOrderKey(x,rule),reverse=True if ruleDir<0 else False)
			for e in eList:
				yield e		
		elif self.skip is not None or self.top is not None:
			# a skip or top option forces ordering by the key
			eList=list(entityIterable)
			eList.sort(key=lambda x:x.Key()) 
			for e in eList:
				yield e			
		else:
			for e in entityIterable:
				yield e

	def Skip(self,skip):
		"""Sets the skip option for this collection.
		
		The skip query option is an integer (or None to remove the
		option) which seeks in to the entity collection.  The
		implementation of
		:py:meth:`itervalues` must honour the skip value."""
		self.skip=skip		
	
	def Top(self,top):
		"""Sets the top option for this collection.
		
		The top query option is an integer (or None to remove the
		option) which limits the number of entities in the entity
		collection.  The implementation of
		:py:meth:`itervalues` must honour the top value."""
		self.top=top		
	
	def TopMax(self,topmax):
		"""Sets the maximum page size for this collection.
		
		This forces the collection to limit the size of a page to at
		most topmax entities.  When topmax is in force
		:py:meth:`NextSkipToken` will return a suitable value for
		identifying the next page in the collection immediately after a
		complete iteration of :py:meth:`iterpage`."""
		self.topmax=topmax
		
	def SkipToken(self,skiptoken):
		"""Sets the skip token for this collection.
		
		By default, we treat the skip token exactly the same as the skip
		value itself except that we obscure it slightly by treating it
		as a hex value."""
		if skiptoken is None:
			self.skiptoken=None
		else:
			try:
				self.skiptoken=int(skiptoken,16)
			except ValueError:
				# not a skip token we recognise, do nothing
				self.skiptoken=None
		
	def SetInlineCount(self,inlineCount):
		"""Sets the inline count flag for this collection."""
		self.inlineCount=inlineCount
	
	def NewEntity(self):
		"""Returns a new py:class:`Entity` instance suitable for adding
		to this collection.
		
		The properties of the entity are set to their defaults, or to
		null if no default is defined (even if the property is marked
		as not nullable).
		
		The entity is not considered to exist until it is actually added
		to the collection.  At this point we deviate from
		dictionary-like behaviour::
		
			e=collection.NewEntity()
			e["ID"]=1000
			e["Name"]="Fred"
			assert 1000 not in collection
			collection[1000]=e		# raises KeyError
			
		The above code is prone to problems as the key 1000 may violate
		the collection's key allocation policy so we raise KeyError when
		assignment is used to insert a new entity to the collection.
		
		Instead, you should call :py:meth:`InsertEntity`."""
		return Entity(self.entitySet)	
	
	def InsertEntity(self,entity):
		"""Inserts *entity* into this entity set.
		
		*entity* must be updated with any auto-generated values such as
		the correct key."""
		raise NotImplementedError
		
	def __getitem__(self,key):
		"""Returns the py:class:`Entity` instance corresponding to *key*
		
		Raises KeyError if the entity with *key* is not in this
		collection.
		
		Derived classes SHOULD override this behaviour.  The default
		implementation is very basic.  We iterate through the entire
		collection looking for the entity with the matching key.
		
		This implementation favours a smaller memory-footprint over
		execution speed.  We do implement a couple of minor
		optimizations to prevent itervalues being called unnecessarily,
		we cache the last entity returned and also the last entity
		yielded by iterkeys."""
		key=self.entitySet.GetKey(key)
		if self.lastYielded and self.lastYielded.Key()==key:
			self.lastGot=self.lastYielded
			return self.lastYielded
		elif self.lastGot and self.lastGot.Key()==key:
			return self.lastGot
		else:
			for e in self.itervalues():
				if e.Key()==key:
					self.lastGot=e
					return e
		raise KeyError(unicode(key))
						
	def __setitem__(self,key,value):
		"""Not implemented"""
		raise NotImplementedError
		
	def __delitem__(self,key):
		"""Not implemented"""
		raise NotImplementedError
	
	def GetPageStart(self):
		"""Returns the index of the start of the collection's current page.
		
		Takes in to consideration both the requested skip value and any
		skiptoken that may be in force."""
		skip=self.skiptoken
		if skip is None:
			skip=0
		if self.skip is None:
			return skip
		else:
			return self.skip+skip
	
	def iterpage(self):
		"""Returns an iterable subset of the values returned by :py:meth:`itervalues`
		
		The subset is defined by the top, skip (and skiptoken) attributes.
		
		Iterpage should be overridden by derived classes for a more
		efficient implementation.  The default implementation simply
		wraps :py:meth:`itervalues`."""
		i=0
		possibleSkiptoken=None
		eMin=self.GetPageStart()
		if self.topmax:
			if self.top is None or self.top>self.topmax:
				# may be truncated
				eMax=eMin+self.topmax
				possibleSkiptoken=eMin+self.topmax
			else:
				# top not None and <= topmax
				eMax=eMin+self.top
		else:
			# no forced paging
			if self.top is None:
				eMax=None
			else:
				eMax=eMin+self.top
		if eMax is None:
			for e in self.itervalues():
				if i>=eMin:
					yield e
				i=i+1
		else:
			for e in self.itervalues():
				if i<eMin:
					i=i+1
				elif i<eMax:
					yield e
					i=i+1
				else:
					# stop the iteration now, set the nextSkiptoken
					self.nextSkiptoken=possibleSkiptoken
					return
		
	def NextSkipToken(self):
		"""Following a complete iteration of the generator returned by
		:py:meth:`iterpage` returns the skiptoken which will generate
		the next page or None if all requested entities have been
		returned."""
		if self.nextSkiptoken is None:
			return None
		else:
			return "%X"%self.nextSkiptoken

	def __len__(self):
		"""Implements len(self) using :py:attr:`count` as a cache."""
		if self.count is None:
			self.count=super(EntityCollection,self).__len__()
		return self.count

	def itervalues(self):
		"""Must be overridden to execute an appropriate query to return
		the collection of entities.
		
		The default implementation returns an empty list."""
		return []
		
	def __iter__(self):
		"""The default implementation uses :py:meth:`itervalues` and :py:meth:`Entity.Key`"""
		for e in self.itervalues():
			self.lastYielded=e
			yield e.Key()
		self.lastYielded=None


class NavigationEntityCollection(EntityCollection):
	"""Represents the collection of entities returned by a navigation property.
	
	*fromKey* is the key in from source entity set and *toEntitySet* is
	the target entity set.  We inherit basic behaviour from
	:py:class:`EntityCollection` acting, in effect, as a special subset
	of *toEntitySet*.
	
	This class is used even when the navigation property is declared to
	return a single entity, rather than a collection.  In which case
	anything after the first entity in the resulting collection is
	ignored."""
	def __init__(self,name,fromEntity,toEntitySet):
		super(NavigationEntityCollection,self).__init__(toEntitySet)
		self.name=name					#: the name of this collection
		self.fromEntity=fromEntity		#: the source entity 
		

class FunctionImport(CSDLElement):
	"""Represents a FunctionImport in an entity collection."""
	XMLNAME=(EDM_NAMESPACE,'FunctionImport')

	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_ReturnType='returnType'
	XMLATTR_EntitySet='entitySetName'
	
	XMLCONTENT=xmlns.ElementType.ElementContent
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"			#: the declared name of this function import
		self.returnType=""			#: the return type of the function
		self.returnTypeRef=None		#: reference to the return type definition
		self.entitySetName=''		#: the name of the entity set from which the return values are taken
		self.entitySet=None			#: the :py:class:`EntitySet` corresponding to :py:attr:`entitySetName`
		self.binding=None,{}		#: a callable to use when executing this function (see :py:meth:`Bind`)
		self.Documentation=None
		self.ReturnType=[]
		self.Parameter=[]
		self.TypeAnnotation=[]
		self.ValueAnnotation=[]
	
	def GetChilren(self):
		if self.Documentation: yield self.Documentation
		for child in itertools.chain(
			self.ReturnType,
			self.Parameter,
			self.TypeAnnotation,
			self.ValueAnnotation,
			CSDLElement.GetChildren(self)):
			yield child

	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""Sets :py:attr:`entitySet` if applicable"""
		try:
			self.entitySet=None
			self.returnTypeRef=TypeRef(self.returnType,scope)
			if self.entitySetName:
				container=self.FindParent(EntityContainer)
				if container:
					self.entitySet=container[self.entitySetName]
				if not isinstance(self.entitySet,EntitySet):
					raise KeyError("%s is not an EntitySet"%self.entitySetName)
			else:
				if isinstance(self.returnTypeRef.typeDef,EntityType) and self.returnTypeRef.collection:
					raise KeyError("Return type %s requires an EntitySet"%self.returnType) 
			for p in self.Parameter:
				p.UpdateSetRefs(scope,stopOnErrors)
		except KeyError:
			self.returnTypeRef=self.entitySet=None
			if stopOnErrors:
				raise
	
	def IsCollection(self):
		"""Returns True if this FunctionImport returns a collection."""
		return self.returnTypeRef.collection
		
	def IsEntityCollection(self):
		"""Returns True if this FunctionImport returns a collection of entities."""
		return self.entitySet is not None and self.returnTypeRef.collection
		
	def Bind(self,callable,**extraArgs):
		"""Binds this instance of FunctionImport to a callable with the
		following signature and the appropriate return type as per the
		:py:meth:`Execute` method:
		
		callable(:py:class:`FunctionImport` instance, params dictionary, **extraArgs)
		
		Note that a derived class of :py:class:`FunctionEntityCollection` can
		be used directly."""
		self.binding=callable,extraArgs
		
	def Execute(self,params):
		"""Executes this function (with optional params), returning one of the
		following, depending on the type of function:
		
		*	An instance of :py:class:`EDMValue`
		
		*	An instance of :py:class:`Entity`
		
		*	An instance of :py:class:`FunctionCollection`
		
		*	An instance of :py:class:`FunctionEntityCollection`  """
		f,extraArgs=self.binding
		if f is not None:
			return f(self,params,**extraArgs)
		else:
			raise NotImplementedError("Unbound FunctionImport: %s"%self.name)
		 		

class FunctionEntityCollection(EntityCollection):
	"""Represents the collection of entities returned by a specific execution of a :py:class:`FunctionImport`"""

	def __init__(self,function,params):
		if function.IsEntityCollection():
			self.function=function
			self.params=params
			EntityCollection.__init__(self,self.function.entitySet)
		else:
			raise TypeError("Function call does not return a collection of entities") 

	def Expand(self,expand,select=None):
		"""This option is not supported on function results"""
		raise NotImplmentedError("Expand/Select option on Function result")


class FunctionCollection(object):
	"""Represents a collection of :py:class:`EDMValue`.
	
	These objects are iterable, but are not list or dictionary-like, in
	other words, you can iterate over the collection but you can't
	address an individual item using an index or a slice."""

	def __init__(self,function,params):
		if function.IsCollection():
			if function.IsEntityCollection():
				raise TypeError("FunctionCollection must not return a collection of entities")
			self.function=function
			self.params=params
			self.name=function.name
		else:
			raise TypeError("Function call does not return a collection of entities") 

	def __iter__(self):
		raise NotImplementedError("Unbound FunctionCollection: %s"%self.function.name)

	
class ParameterMode(xsi.Enumeration):
	"""ParameterMode defines constants for the parameter modes defined by CSDL
	::
		
		ParameterMode.In	
		ParameterMode.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'In':1,
		'Out':2,
		'InOut':3
		}
xsi.MakeEnumeration(ParameterMode)
xsi.MakeLowerAliases(SimpleType)


class Parameter(CSDLElement):
	"""Represents a Parameter in a function import."""
	XMLNAME=(EDM_NAMESPACE,'Parameter')

	XMLATTR_Name=('name',ValidateSimpleIdentifier,None)
	XMLATTR_Type='type'
	XMLATTR_Mode=('mode',ParameterMode.DecodeValue,ParameterMode.EncodeValue)
	XMLATTR_MaxLength=('maxLength',DecodeMaxLength,EncodeMaxLength)
	XMLATTR_Precision='precision'
	XMLATTR_Scale='scale'
	XMLCONTENT=xmlns.ElementType.ElementContent
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		self.name="Default"			#: the declared name of this parameter
		self.type=""				#: the type of the parameter, a scalar type, ComplexType or EntityType (or a Collection)
		self.typeRef=None			#: reference to the type definition
		self.mode=None				#: one of the :py:class:`ParameterMode` constants
		self.maxLength=None			#: the maxLength facet of the parameter
		self.precision=None			#: the precision facet of the parameter
		self.scale=None				#: the scale facet of the parameter
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

	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""Sets type information for the parameter"""
		try:
			self.typeRef=TypeRef(self.type,scope)
		except KeyError:
			self.typeRef=None
			if stopOnErrors:
				raise

class Function(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Function')

class Annotations(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'Annotations')

class ValueTerm(CSDLElement):
	XMLNAME=(EDM_NAMESPACE,'ValueTerm')


class Schema(NameTableMixin,CSDLElement):
	"""Represents the Edm root element.
	
	Schema instances are based on :py:class:`NameTableMixin` allowing you to
	look up the names of declared Associations, ComplexTypes, EntityTypes,
	EntityContainers and Functions using dictionary-like methods."""
	XMLNAME=(EDM_NAMESPACE,'Schema')
	XMLATTR_Namespace='name'
	XMLATTR_Alias='alias'
	
	def __init__(self,parent):
		CSDLElement.__init__(self,parent)
		NameTableMixin.__init__(self)
		self.name="Default"		#: the declared name of this schema
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
			self.EntityType,
			self.ComplexType,
			self.Association,
			self.Function,
			self.EntityContainer,
			self.Using,
			self.Annotations,
			self.ValueTerm,
			CSDLElement.GetChildren(self))

	def ContentChanged(self):
		for t in self.EntityType+self.ComplexType+self.Association+self.Function+self.EntityContainer:
			self.Declare(t)

	def UpdateTypeRefs(self,scope,stopOnErrors=False):
		for t in self.EntityType+self.ComplexType+self.Association+self.Function:
			t.UpdateTypeRefs(scope,stopOnErrors)
		
	def UpdateSetRefs(self,scope,stopOnErrors=False):
		for t in self.EntityContainer:
			t.UpdateSetRefs(scope,stopOnErrors)
		
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

	@classmethod
	def GetElementClass(cls,name):
		"""Overrides :py:meth:`pyslet.xmlnames20091208.XMLNSDocument.GetElementClass` to look up name."""
		eClass=Document.classMap.get(name,Document.classMap.get((name[0],None),xmlns.XMLNSElement))
		return eClass
	
xmlns.MapClassElements(Document.classMap,globals(),NAMESPACE_ALIASES)


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
					if oldT.entityTypeName.startswith(scopePrefix):
						# the entity type is in the new scope, may have changed
						newType=newS[oldT.entityTypeName[len(scopePrefix):]]
						oldType=self[oldT.entityTypeName]
						transaction=transaction+self.UpdateTable(tablePrefix+oldT.name,oldType,newType)					
			else:
				# the EntityContainer is in this scope, it may have changed
				newContainer=newS[containerName[len(scopePrefix):]]
				for oldT in oldContainer.EntitySet:
					if oldT.name in newContainer:
						# This table is in the new scope too
						newT=newContainer[oldT.name]
						if newT.entityTypeName.startswith(scopePrefix):
							# the entity type is in the new scope too
							newType=newS[newT.entityTypeName[len(scopePrefix):]]
							oldType=self[oldT.entityTypeName]
							transaction=transaction+self.UpdateTable(tablePrefix+oldT.name,oldType,newType)
					else:
						# Drop this one
						transaction=transaction+self.DropTable(tablePrefix+oldT.name)
				for newT in newContainer.EntitySet:
					if newT.name in oldContainer:
						continue
					else:
						# new table not in old container
						if newT.entityTypeName.startswith(scopePrefix):
							newType=newS[newT.entityTypeName[len(scopePrefix):]]
						else:
							newType=self[newT.entityTypeName]
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
			eType=self[t.entityTypeName]
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
		eType=self[t.entityTypeName]
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
						result[p.name]=self.DecodeLiteral(p.simpleTypeCode,row[i])
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
		eType=self[t.entityTypeName]
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
		