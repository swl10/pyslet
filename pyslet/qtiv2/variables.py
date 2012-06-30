#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2616 as http
from pyslet.rfc2396  import URI, URIFactory
import pyslet.qtiv2.core as core

import string, itertools
from types import BooleanType,IntType,LongType,FloatType,StringTypes,DictType,TupleType,ListType


class BaseType(xsi.Enumeration):
	"""A base-type is simply a description of a set of atomic values (atomic to
	this specification). Note that several of the baseTypes used to define the
	runtime data model have identical definitions to those of the basic data
	types used to define the values for attributes in the specification itself.
	The use of an enumeration to define the set of baseTypes used in the runtime
	model, as opposed to the use of classes with similar names, is designed to
	help distinguish between these two distinct levels of modelling::
	
	<xsd:simpleType name="baseType.Type">
		<xsd:restriction base="xsd:NMTOKEN">
			<xsd:enumeration value="boolean"/>
			<xsd:enumeration value="directedPair"/>
			<xsd:enumeration value="duration"/>
			<xsd:enumeration value="file"/>
			<xsd:enumeration value="float"/>
			<xsd:enumeration value="identifier"/>
			<xsd:enumeration value="integer"/>
			<xsd:enumeration value="pair"/>
			<xsd:enumeration value="point"/>
			<xsd:enumeration value="string"/>
			<xsd:enumeration value="uri"/>
		</xsd:restriction>
	</xsd:simpleType>
	
	Defines constants for the above base types.  Usage example::

		BaseType.float
	
	There is no default::
		
		BaseType.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'boolean':1,
		'directedPair':2,
		'duration':3,
		'file':4,
		'float':5,
		'identifier':6,
		'integer':7,
		'pair':8,
		'point':9,
		'string':10,
		'uri':11
		}
xsi.MakeEnumeration(BaseType)
xsi.MakeLowerAliases(BaseType)


class Cardinality(xsi.Enumeration):
	"""An expression or itemVariable can either be single-valued or
	multi-valued. A multi-valued expression (or variable) is called a container.
	A container contains a list of values, this list may be empty in which case
	it is treated as NULL. All the values in a multiple or ordered container are
	drawn from the same value set::

	<xsd:simpleType name="cardinality.Type">
		<xsd:restriction base="xsd:NMTOKEN">
			<xsd:enumeration value="multiple"/>
			<xsd:enumeration value="ordered"/>
			<xsd:enumeration value="record"/>
			<xsd:enumeration value="single"/>
		</xsd:restriction>
	</xsd:simpleType>
	
	Defines constants for the above carinalities.  Usage example::

		Cardinality.multiple
	
	There is no default::
		
		Cardinality.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'multiple':1,
		'ordered':2,
		'record':3,
		'single':4
		}
xsi.MakeEnumeration(Cardinality)

		
class ValueElement(core.QTIElement):
	"""A class that can represent a single value of any baseType in variable
	declarations and result reports::
	
		<xsd:attributeGroup name="value.AttrGroup">
			<xsd:attribute name="fieldIdentifier" type="identifier.Type" use="optional"/>
			<xsd:attribute name="baseType" type="baseType.Type" use="optional"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'value')
	XMLATTR_baseType=('baseType',BaseType.DecodeLowerValue,BaseType.EncodeValue)
	XMLATTR_fieldIdentifier=('fieldIdentifier',core.ValidateIdentifier,lambda x:x)
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.fieldIdentifier=None
		self.baseType=None


class Value(object):
	"""Represents a single value in the processing model.
	
	This class is the heart of the QTI processing model.  This is an abstract
	base class of a class hierarchy that represents the various types of value
	that may be encountered when processing."""
	
	def __init__(self):
		self.baseType=None
		"""One of the :py:class:`BaseType` constants or None if the baseType is unknown.
		
		An unknown baseType acts like a wild-card.  It means that the baseType
		is not determined and could potentially be any of the
		:py:class:`BaseType` values. This distinction has implications for the
		way evaluation is done.  A value with a baseType of None will not raise
		TypeErrors during evaluation if the cardinalities match the context. 
		This allows expressions which contain types bound only at runtime to be
		evaluated for validity checking."""
		self.value=None
		"""The value of the variable.  The following representations are used
		for values of single cardinality:

		NULL value
			Represented by None
		
		boolean
			One of the built-in Python values True and False
			
		directedPair
			A tuple of strings (<source identifier>, <destination identifier>)
			
		duration
			real number of seconds
			
		file
			a file like object (supporting seek)
		
		float
			real number
			
		identifier
			A text string
		
		integer
			A plain python integer (QTI does not support long integer values)
			
		pair
			A *sorted* tuple of strings (<identifier A>, <identifier B>).  We
			sort the identifiers in a pair by python's native string sorting to
			ensure that pair values are comparable.
			
		point
			A tuple of integers (<x-coordinate>, <y-coordinate>)
		
		string
			A python string
			
		uri
			An instance of :py:class:`~pyslet.rfc2396.URI`
		
		For containers, we use the following structures:
		
		ordered
			A list of one of the above value types.
			
		multiple:
			A dictionary with keys that are one of the above value types and
			values that indicate the frequency of that value in the container.
		
		record:
			A dictionary with keys that are the field identifiers and
			values that Value instances."""
			
	def SetValue(self,value):
		"""Sets the value.
		
		All single values can be set from a single text string corresponding to
		their XML schema defined lexical values (*without* character level
		escaping).  If v is a single Value instance then the following always
		leaves v unchanged::
		
			v.SetValue(unicode(v))
			
		Value instances can also be set from values of the appropriate type as
		described in :py:attr:`value`.  For base types that are represented with
		tuples we also accept and convert lists.
		
		Containers values cannot be set from strings."""
		if value is None:
			self.value=None
		else:
			self.ValueError(value)
	
	def ValueError(self,value):
		"""Raises a ValueError with a debug-friendly message string."""
		raise ValueError("Can't set value of %s %s from %s"%(Cardinality.EncodeValue(self.Cardinality()),
			BaseType.EncodeValue(self.baseType),repr(value)))
		
	def Cardinality(self):
		"""Returns the cardinality of this value.  One of the :py:class:`Cardinality` constants."""
		raise NotImplementedError
		 
	def IsNull(self):
		"""Returns True is this value is NULL, as defined by the QTI specification."""
		return self.value is None
	
	def __nonzero__(self):
		"""The python non-zero test is equivalent to the non-NULL test in QTI."""
		return self.value is not None
				
	def __unicode__(self):
		"""Creates a string representation of the object.  The NULL value returns None."""
		if self.value is None:
			return u''
		else:
			raise NotImplementedError("Serialization of %s"%self.__class__.__name__)

	@classmethod
	def NewValue(cls,baseType,value=None):
		"""Creates a new instance with *baseType* and *value*"""
		if baseType is None:
			return Value()
		elif baseType==BaseType.boolean:
			return BooleanValue(value)
		elif baseType==BaseType.directedPair:
			return DirectedPairValue(value)
		elif baseType==BaseType.duration:
			return DurationValue(value)
		elif baseType==BaseType.file:
			return FileValue(value)
		elif baseType==BaseType.float:
			return FloatValue(value)
		elif baseType==BaseType.identifier:
			return IdentifierValue(value)
		elif baseType==BaseType.integer:
			return IntegerValue(value)
		elif baseType==BaseType.pair:
			return PairValue(value)
		elif baseType==BaseType.point:
			return PointValue(value)
		elif baseType==BaseType.string:
			return StringValue(value)
		elif baseType==BaseType.uri:
			return URIValue(value)
		else:
			raise ValueError("Unknown base type: %s"%BaseType.EncodeValue(baseType))			

	@classmethod
	def NewContainer(cls,cardinality,baseType=None):
		"""Creates a new container instance with *cardinality* and *baseType*."""
		if cardinality==Cardinality.single:
			raise ValueError("Error: use NewValue to create single values")
		elif cardinality==Cardinality.ordered:
			return OrderedContainer(baseType)
		elif cardinality==Cardinality.multiple:
			return MultipleContainer(baseType)
		elif cardinality==Cardinality.record:
			return RecordContainer()	 
		else:
			raise ValueError("Unknown cardinality")
			

class SingleValue(Value):
	"""Represents all values with single cardinality."""
	
	def Cardinality(self):
		return Cardinality.single


class BooleanValue(SingleValue):
	"""Represents single values of type :py:class:`BaseType.boolean`."""
	
	def __init__(self,value=None):
		super(BooleanValue,self).__init__()
		self.baseType=BaseType.boolean
		if value is not None:
			 self.SetValue(value)
			
	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return xsi.EncodeBoolean(self.value)

	def SetValue(self,value):
		"""If value is a string it will be decoded according to the rules for representing
		boolean values.  Booleans and integers can be used directly in the normal python
		way but other values will raise ValueError.  To take advantage of a non-zero test
		you must explicitly force it to be a boolean.  For example::
		
			# x is a value of unknown type with non-zero test implemented
			v=BooleanValue()
			v.SetValue(True if x else False)"""
		if value is None:
			self.value=None
		elif type(value) is BooleanType:
			self.value=value
		elif type(value) in (IntType,LongType):
			self.value=True if value else False
		elif type(value) in StringTypes:
			self.value=xsi.DecodeBoolean(value)
		else:
			self.ValueError(value)


class DirectedPairValue(SingleValue):
	"""Represents single values of type :py:class:`BaseType.directedPair`."""
	
	def __init__(self,value=None):
		super(DirectedPairValue,self).__init__()
		self.baseType=BaseType.directedPair
		if value is not None:
			 self.SetValue(value)
	
	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return string.join(self.value,' ')
	
	def SetValue(self,value,nameCheck=False):
		"""See comment on :py:meth:`Identifier.SetValue` for usage of *nameCheck*.
		
		Note that if value is a string then nameCheck is ignored and identifier
		validation is always performed."""
		if value is None:
			self.value=None
		else:
			if type(value) in StringTypes:
				value=string.split(value)
				nameCheck=True
			if type(value) in (ListType,TupleType):
				if len(value)!=2:
					raise ValueError("%s expected 2 values: %s"%(BaseType.EncodeValue(self.baseType),repr(value)))
				for v in value:
					if type(v) not in StringTypes or (nameCheck and not xmlns.IsValidNCName(v)):
						raise ValueError("Illegal identifier %s"%repr(v))
				self.value=(unicode(value[0]),unicode(value[1]))												
			else:
				self.ValueError(value)


class FileValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.file`."""
	
	def __init__(self):
		super(FileValue,self).__init__()
		self.baseType=BaseType.file
		self.contentType=http.HTTPMediaType("application/octet-stream")
		"""The content type of the file, a :py:class:`pyslet.rfc2616.HTTPMediaType` instance."""
		self.fileName="data.bin"
		"""The file name to use for the file."""
		
	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			raise NotImplementedError("String serialization of BaseType.file.")

	def SetValue(self,value,type="application/octet-stream",name="data.bin"):
		"""Sets a file value from a file like object or a string.
		
		There are some important and subtle distinctions in this method.
		
		If value is a Unicode text string then it is parsed according to the
		MIME-like format defined in the QTI specification.  The values of
		*type* and *name* are only used as defaults if those values cannot
		be read from the value's headers.
		
		If value is a plain string then it is assumed to represent the file's
		data directly, *type* and *name* are used to interpret the data.
		Other file type objects are set in the same way."""
		self.contentType=type
		self.fileName=name
		if value is None:
			self.value=None
		elif type(value) is FileType:
			self.value=value
		elif type(value) is StringType:
			self.value=StringIO.StringIO(value)
		elif type(value) is UnicodeType:
			# Parse this value from the MIME stream.
			raise NotImplementedError("String deserialization of BaseType.file.")
		else:
			self.ValueError(value)


class FloatValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.float`."""
	
	def __init__(self,value=None):
		super(FloatValue,self).__init__()
		self.baseType=BaseType.float
		if value is not None:
			 self.SetValue(value)

	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return xsi.EncodeDouble(self.value)

	def SetValue(self,value):
		"""This method will *not* convert integers to float values, you must do
		this explicitly if you want automatic conversion, for example::
		
			# x is a numeric value that may be float or integer
			v=FloatValue()
			v.SetValue(float(x))"""
		if value is None:
			self.value=None
		elif type(value) is FloatType:
			self.value=value
		elif type(value) in StringTypes:
			self.value=xsi.DecodeDouble(value)
		else:
			self.ValueError(value)

		
class DurationValue(FloatValue):
	"""Represents single value of type :py:class:`BaseType.duration`."""
	
	def __init__(self,value=None):
		super(DurationValue,self).__init__()
		self.baseType=BaseType.duration
		if value is not None:
			 self.SetValue(value)

	
class IdentifierValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.identifier`."""
	
	def __init__(self,value=None):
		super(IdentifierValue,self).__init__()
		self.baseType=BaseType.identifier
		if value is not None:
			 self.SetValue(value)

	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return unicode(self.value)

	def SetValue(self,value,nameCheck=True):
		"""In general, to speed up computation we do not check the validity of
		identifiers unless parsing the value from a string representation (such
		as a value read from an XML input document).

		As values of baseType identifier are represented natively as strings we
		cannot tell if this method is being called with an existing,
		name-checked value or a new value being parsed from an external source.
		To speed up computation you can suppress the name check in the first
		case by setting *nameCheck* to False (the default is True)."""
		if value is None:
			self.value=None
		elif type(value) in StringTypes:
			if not nameCheck or xmlns.IsValidNCName(value):
				self.value=unicode(value)
			else:
				raise ValueError("Illegal identifier %s"%repr(value))
		else:
			self.ValueError(value)


class IntegerValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.integer`."""
	
	def __init__(self,value=None):
		super(IntegerValue,self).__init__()
		self.baseType=BaseType.integer
		if value is not None:
			 self.SetValue(value)

	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return xsi.EncodeInteger(self.value)

	def SetValue(self,value):
		"""Note that integers and floats are distinct types in QTI: we do not
		accept floats where we would expect integers or *vice versa*.  However,
		integers are accepted from long or plain integer values provided they
		are within the ranges specified in the QTI specification:
		-2147483648...2147483647."""
		if value is None:
			self.value=None
		elif type(value) in (IntType,LongType):
			# python integers may be bigger than 32bits
			if value<-2147483648 or value > 2147483647:
				raise ValueError("Integer range: %s"%repr(value))
			else:
				self.value=int(value)
		elif type(value) in StringTypes:
			self.value=xsi.DecodeInteger(value)
		else:
			self.ValueError(value)

		
class PairValue(DirectedPairValue):
	"""Represents single values of type :py:class:`BaseType.pair`."""
	
	def __init__(self,value=None):
		super(PairValue,self).__init__()
		self.baseType=BaseType.pair
		if value is not None:
			 self.SetValue(value)

	def SetValue(self,value,nameCheck=True):
		"""Overrides DirectedPair's implementation to force a predictable ordering on the identifiers."""
		super(PairValue,self).SetValue(value,nameCheck)
		if self.value and self.value[0]>self.value[1]:
			self.value=(self.value[1],self.value[0])
		
				
				
class PointValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.point`."""
	
	def __init__(self,value=None):
		super(PointValue,self).__init__()
		self.baseType=BaseType.point
		if value is not None:
			 self.SetValue(value)

	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return string.join(map(xsi.EncodeInteger,self.value),' ')

	def SetValue(self,value):
		if value is None:
			self.value=None
		else:
			if type(value) in StringTypes:
				value=map(xsi.DecodeInteger,string.split(value))
			if type(value) in (ListType,TupleType):
				if len(value)!=2:
					raise ValueError("%s expected 2 values: %s"%(BaseType.EncodeValue(self.baseType),repr(value)))
				for v in value:
					if type(v) not in (IntType,LongType):
						raise ValueError("Illegal type for point coordinate %s"%repr(type(v)))
					elif v<-2147483648 or v>2147483647:
						raise ValueError("Integer coordinate range: %s"%repr(v))
				self.value=(int(value[0]),int(value[1]))
			else:
				self.ValueError(value)

		
class StringValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.string`."""
	
	def __init__(self,value=None):
		super(StringValue,self).__init__()
		self.baseType=BaseType.string
		if value is not None:
			 self.SetValue(value)

	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return unicode(self.value)

	def SetValue(self,value):
		if value is None:
			self.value=None
		elif type(value) in StringTypes:
			self.value=unicode(value)
			if len(self.value)==0:
				self.value=None
		else:
			self.ValueError(value)										

		
class URIValue(SingleValue):
	"""Represents single value of type :py:class:`BaseType.uri`."""
	
	def __init__(self,value=None):
		super(URIValue,self).__init__()
		self.baseType=BaseType.uri
		if value is not None:
			 self.SetValue(value)
		
	def __unicode__(self):
		if self.value is None:
			return u''
		else:
			return unicode(self.value)

	def SetValue(self,value):
		"""Sets a uri value from a string or another URI instance."""
		if value is None:
			self.value=None
		elif type(value) in StringTypes:
			self.value=URIFactory.URI(value)
		elif isinstance(value,URI):
			self.value=value
		else:
			self.ValueError(value)


class Container(Value):
	"""An abstract class for all container types.

	By default containers are empty (and are treated as NULL values).  You can
	force the type of an empty container by passing a baseType constant to the
	constructor.  This will cause the container to generate TypeError if used in
	a context where the specified baseType is not allowed."""
	
	def __init__(self,baseType=None):
		super(Container,self).__init__()
		self.baseType=baseType

	def GetValues(self):
		"""Returns an iterable of the container's values."""			 	
		return

	def __unicode__(self):
		"""For single values we return a representation suitable for use as the
		content of a single XML element.  For containers this option is not
		open to us because they are always represented by multiple elements.
		
		We therefore opt for a minimal representation."""
		if self.baseType is None:
			return u"%s container of unknown base type"%Cardinality.EncodeValue(self.Cardinality)
		else:
			return u"%s container of base type %s"%(Cardinality.EncodeValue(self.Cardinality),
				BaseType.EncodeValue(self.baseType))
			

class OrderedContainer(Container):
	"""Represents containers with ordered :py:class:`Cardinality`."""
	
	def Cardinality(self):
		return Cardinality.ordered
	
	def SetValue(self,value,baseType=None):
		"""Sets the value of this container from a list, tuple or other
		iterable. The list must contain valid representations of *baseType*,
		items may be None indicating a NULL value in the list.  In accordance
		with the specification's multiple operator NULL values are ignored.
				
		If the input list of values empty, or contains only NULL values then the
		resulting container is empty.
		
		If *baseType* is None the base type specified when the container was
		constructed is assumed."""
		if baseType is not None:
			self.baseType=baseType
		if value is None:
			self.value=None
		else:
			# assume that value is iterable
			self.value=[]
			for v in value:
				if v is None:
					# ignore NULLs					
					continue
				if self.baseType is None:
					# wild-card lists only work if they're empty!
					raise ValueError("Can't create non-empty ordered container without a base type")
				vAdd=Value.NewValue(self.baseType,v)
				self.value.append(vAdd.value)
			if not self.value:
				self.value=None
	
	def GetValues(self):
		"""Returns an iterable of values in the ordered container."""
		if self.value is None:
			return
		for v in self.value:
			yield v

		
class MultipleContainer(Container):
	"""Represents containers with multiple :py:class:`Cardinality`."""
	
	def Cardinality(self):
		return Cardinality.multiple
	
	def SetValue(self,value,baseType=None):
		"""Sets the value of this container from a list, tuple or other
		iterable. The list must contain valid representations of *baseType*,
		items may be None indicating a NULL value in the list.  In accordance
		with the specification's multiple operator NULL values are ignored.
				
		If the input list of values empty, or contains only NULL values then the
		resulting container is empty.

		If *baseType* is None the base type specified when the container was
		constructed is assumed."""
		if baseType is not None:
			self.baseType=baseType
		if value is None:
			self.value=None
		else:
			self.value={}
			for v in value:
				if v is None:
					# ignore NULLs					
					continue
				if self.baseType is None:
					# wild-card lists only work if they're empty!
					raise ValueError("Can't create non-empty multiple container without a base type")
				vAdd=Value.NewValue(self.baseType,v)
				self.value[vAdd.value]=self.value.get(vAdd.value,0)+1
			if not self.value:
				self.value=None

	def GetValues(self):
		"""Returns an iterable of values in the ordered container."""
		if self.value is None:
			return
		keys=self.value.keys()
		keys.sort()
		for k in keys:
			for i in xrange(self.value[k]):
				yield k


class RecordContainer(Container):
	"""Represents containers with record :py:class:`Cardinality`."""
	
	def __init__(self):
		super(Container,self).__init__()

	def Cardinality(self):
		return Cardinality.record
	
	def SetValue(self,value):
		"""Sets the value of this container from an existing dictionary in which
		the keys are the field identifiers and the values are :py:class:`Value`
		instances. You cannot parse containers from strings.
				
		Records are always treated as having a wild-card base type.
		
		If the input *value* contains any keys which map to None or to a NULL
		value then these fields are omitted from the resulting value."""
		if value is None:
			self.value=None
		else:
			newValue={}
			if type(value) is DictType:
				valueDict=value
				fieldList=value.keys()
			else:
				raise ValueError("RecordContainer.SetValue expected dictionary, found %s"%repr(value)) 
			for f in fieldList:
				v=value[f]
				if v is None:
					continue
				if not isinstance(v,SingleValue):
					raise ValueError("Single value required, found %s"%repr(v))
				if not v:
					# ignore NULL, no need to type check in records
					continue
				newValue[f]=value[f]
			if newValue:
				self.value=newValue
			else:
				self.value=None
	
	def __len__(self):
		if self.value:
			return len(self.value)
		else:
			return 0
			
	def __getitem__(self,fieldIdentifier):
		"""Returns the :py:class:`Value` instance corresponding to
		*fieldIdentifier* or raises KeyError if there is no field with that
		name."""
		if self.value:
			return self.value[fieldIdentifier]
		else:
			raise KeyError(fieldIdentifier)
			
	def __setitem__(self,fieldIdentifier,value):
		"""Sets the value in the named field to *value*.
		
		We add some special behaviour here.  If *value* is None or is a NULL
		value then we remove the field with the give name.  In other words::
		
			r=RecordContainer()
			r['pi']=FloatValue(3.14)
			r['pi']=FloatValue()     # a NULL value
			print r['pi']            # raises KeyError"""
		if value is None:
			if self.value and fieldIdentifier in self.value:
				del self.value[fieldIdentifier]
		elif isinstance(value,SingleValue):
			if not value:
				if self.value and fieldIdentifier in self.value:
					del self.value[fieldIdentifier]
			else:
				if self.value is None:
					self.value={fieldIdentifier:value}
				else:
					self.value[fieldIdentifier]=value		
		else:
			raise ValueError("Single value required, found %s"%repr(v))	

	def __delitem__(self,fieldIdentifier):
		if self.value:
			del self.value[fieldIdentifier]
		else:
			raise KeyError(fieldIdentifier)
	
	def __iter__(self):
		if self.value:
			return iter(self.value)
		else:
			return iter([])

	def __contains__(self,fieldIdentifier):
		if self.value:
			return fieldIdentifier in self.value
		else:
			return False

				
class VariableDeclaration(core.QTIElement):
	"""Item variables are declared by variable declarations... The purpose of the
	declaration is to associate an identifier with the variable and to identify
	the runtime type of the variable's value::

		<xsd:attributeGroup name="variableDeclaration.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
			<xsd:attribute name="cardinality" type="cardinality.Type" use="required"/>
			<xsd:attribute name="baseType" type="baseType.Type" use="optional"/>
		</xsd:attributeGroup>
		
		<xsd:group name="variableDeclaration.ContentGroup">
			<xsd:sequence>
				<xsd:element ref="defaultValue" minOccurs="0" maxOccurs="1"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLATTR_baseType=('baseType',BaseType.DecodeLowerValue,BaseType.EncodeValue)	
	XMLATTR_cardinality=('cardinality',Cardinality.DecodeLowerValue,Cardinality.EncodeValue)	
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.identifier=''
		self.cardinality=0
		self.baseType=None
		self.DefaultValue=None
	
	def __cmp__(self,other):
		if isinstance(other,VariableDeclaration):
			return cmp(self.identifier,other.identifier)
		else:
			raise TypeError("Can't compare VariableDeclaration with %s"%repr(other))

	def GetChildren(self):
		if self.DefaultValue: yield self.DefaultValue
		for child in core.QTIElement.GetChildren(self): yield child

	def GetDefaultValue(self):
		"""Returns a :py:class:`Value` instance representing the default value
		or None if there is no default value."""
		if self.DefaultValue:
			if self.cardinality==Cardinality.single:
				value=Value.NewValue(self.baseType,self.DefaultValue.ValueElement[0].GetValue())
			else:
				value=Value.NewContainer(self.cardinality,self.baseType)
				if isinstance(value,RecordContainer):
					# handle record processing
					for v in self.DefaultValue.ValueElement:
						value[v.fieldIdentifier]=Value.NewValue(v.baseType,v.GetValue())	
				else:
					# handle multiple and ordered processing
					value.SetValue(map(lambda v:v.GetValue(),self.DefaultValue.ValueElement))
		else:
			# generate NULL values with the correct cardinality and base type
			if self.cardinality==Cardinality.single:
				value=Value.NewValue(self.baseType)
			else:
				value=Value.NewContainer(self.cardinality,self.baseType)
		return value
			

class DefaultValue(core.QTIElement):
	"""Represents the defaultValue element.
		
	<xsd:attributeGroup name="defaultValue.AttrGroup">
		<xsd:attribute name="interpretation" type="string.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="defaultValue.ContentGroup">
		<xsd:sequence>
			<xsd:element ref="value" minOccurs="1" maxOccurs="unbounded"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'defaultValue')
	XMLATTR_interpretation='interpretation'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.interpretation=None
		self.ValueElement=[]
	
	def GetChildren(self):
		return itertools.chain(
			self.ValueElement,
			core.QTIElement.GetChildren(self))


class Mapping(core.QTIElement):
	"""A special class used to create a mapping from a source set of any
	baseType (except file and duration) to a single float::
		
		<xsd:attributeGroup name="mapping.AttrGroup">
			<xsd:attribute name="lowerBound" type="float.Type" use="optional"/>
			<xsd:attribute name="upperBound" type="float.Type" use="optional"/>
			<xsd:attribute name="defaultValue" type="float.Type" use="required"/>
		</xsd:attributeGroup>
		
		<xsd:group name="mapping.ContentGroup">
			<xsd:sequence>
				<xsd:element ref="mapEntry" minOccurs="1" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'mapping')
	XMLATTR_lowerBound=('lowerBound',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLATTR_upperBound=('upperBound',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLATTR_defaultValue=('defaultValue',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.lowerBound=None
		self.upperBound=None
		self.defaultValue=0.0
		self.MapEntry=[]
		self.baseType=BaseType.string
		self.map={}
	
	def GetChildren(self):
		return iter(self.MapEntry)

	def ContentChanged(self):
		"""Builds an internal dictionary of the values being mapped.
		
		In order to fully specify the mapping we need to know the baseType of
		the source values.  (The targets are always floats.)  We do this based
		on our parent, orphan Mapping elements are treated as mappings from
		source strings."""
		if isinstance(self.parent,ResponseDeclaration):
			self.baseType=self.parent.baseType
		elif isinstance(self.parent,CategorizedStatistic):
			self.baseType=BaseType.integer
		else:
			self.baseType=BaseType.string
		self.map={}
		for me in self.MapEntry:
			v=Value.NewValue(self.baseType,me.mapKey)
			self.map[v.value]=me.mappedValue
					
	def MapValue(self,value):
		"""Maps an instance of :py:class:`Value` with the same base type as the
		mapping to an instance of :py:class:`Value` with base type float."""
		nullFlag=False
		if not value:
			srcValues=[]
			nullFlag=True
		elif value.Cardinality()==Cardinality.single:
			srcValues=[value.value]
		elif value.Cardinality()==Cardinality.ordered:
			srcValues=value.value
		elif value.Cardinality()==Cardinality.multiple:
			srcValues=value.value.keys()
		else:
			raise ValueError("Can't map %s"%repr(value))
		result=0.0
		beenThere={}
		dstValue=FloatValue(0.0)
		if value.baseType is None:
			# a value of unknown type results in NULL
			nullFlag=True
		for v in srcValues:
			if v in beenThere:
				# If a container contains multiple instances of the same value then that value is counted once only
				continue
			else:
				beenThere[v]=True
			result=result+self.map.get(v,self.defaultValue)
		if nullFlag:
			# We save the NULL return up to the end to ensure that we generate errors
			# in the case where a container contains mixed or mismatching values.
			return dstValue
		else:
			if self.lowerBound is not None and result<self.lowerBound:
				result=self.lowerBound
			elif self.upperBound is not None and result>self.upperBound:
				result=self.upperBound
			dstValue.SetValue(result)
			return dstValue


class MapEntry(core.QTIElement):
	"""An entry in a :py:class:`Mapping`::
		
		<xsd:attributeGroup name="mapEntry.AttrGroup">
			<xsd:attribute name="mapKey" type="valueType.Type" use="required"/>
			<xsd:attribute name="mappedValue" type="float.Type" use="required"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'mapEntry')
	XMLATTR_mapKey='mapKey'
	XMLATTR_mappedValue=('mappedValue',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLCONTENT=xml.ElementType.Empty

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.mapKey=None			#: The source value
		self.mappedValue=0.0		#: The mapped value
		

class ResponseDeclaration(VariableDeclaration):
	"""Represents a responseDeclaration.
	
	<xsd:group name="responseDeclaration.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="variableDeclaration.ContentGroup"/>
			<xsd:element ref="correctResponse" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="mapping" minOccurs="0" maxOccurs="1"/>
			<xsd:element ref="areaMapping" minOccurs="0" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'responseDeclaration')
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		VariableDeclaration.__init__(self,parent)
		self.CorrectResponse=None
		self.Mapping=None
		self.AreaMapping=None
	
	def GetChildren(self):
		for child in VariableDeclaration.GetChildren(self): yield child
		if self.CorrectResponse: yield self.CorrectResponse
		if self.Mapping: yield self.Mapping
		if self.AreaMapping: yield self.AreaMapping
		
	def ContentChanged(self):
		self.parent.RegisterDeclaration(self)

		
class OutcomeDeclaration(VariableDeclaration):
	"""Represents an outcomeDeclaration.

	<xsd:attributeGroup name="outcomeDeclaration.AttrGroup">
		<xsd:attributeGroup ref="variableDeclaration.AttrGroup"/>
		<xsd:attribute name="view" use="optional">
			<xsd:simpleType>
				<xsd:list itemType="view.Type"/>
			</xsd:simpleType>
		</xsd:attribute>
		<xsd:attribute name="interpretation" type="string.Type" use="optional"/>
		<xsd:attribute name="longInterpretation" type="uri.Type" use="optional"/>
		<xsd:attribute name="normalMaximum" type="float.Type" use="optional"/>
		<xsd:attribute name="normalMinimum" type="float.Type" use="optional"/>
		<xsd:attribute name="masteryValue" type="float.Type" use="optional"/>
	</xsd:attributeGroup>
	
	<xsd:group name="outcomeDeclaration.ContentGroup">
		<xsd:sequence>
			<xsd:group ref="variableDeclaration.ContentGroup"/>
			<xsd:group ref="lookupTable.ElementGroup" minOccurs="0" maxOccurs="1"/>
		</xsd:sequence>
	</xsd:group>
	"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'outcomeDeclaration')
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLATTR_interpretation='interpretation'
	XMLATTR_longInterpretation='longInterpretation'
	XMLATTR_normalMaximum=('normalMaximum',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLATTR_normalMinimum=('normalMinimum',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLATTR_masteryValue=('masteryValue',xsi.DecodeFloat,xsi.EncodeFloat)
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		VariableDeclaration.__init__(self,parent)
		self.view={}
		self.interpretation=None
		self.longInterpretation=None
		self.normalMaximum=None
		self.normalMinimum=None
		self.masteryValue=None
		self.lookupTable=None
	
	def MatchTable(self):
		child=MatchTable(self)
		self.lookupTable=child
		return child
	
	def QTIInterpolationTable(self):
		child=QTIInterpolationTable(self)
		self.lookupTable=child
		return child
	
	def GetChildren(self):
		for child in VariableDeclaration.GetChildren(self): yield child
		if self.lookupTable: yield self.lookupTable
	
	def ContentChanged(self):
		self.parent.RegisterDeclaration(self)
		