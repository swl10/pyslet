from types import StringTypes, IntType, LongType, TupleType, ListType

from PyAssess.w3c.xml import IsLetter, IsDigit, IsCombiningChar, IsExtender

IMSQTINamespace="http://www.imsglobal.org/xsd/imsqti_v2p0"

IMSQTINamespaces={
	"http://www.imsglobal.org/xsd/imsqti_v2p0":"2.0"
	}

class IMSQTIError(Exception): pass


class BaseType:
	"""BaseType enumeration"""
	Identifier=1
	Boolean=2
	Integer=3
	Float=4
	String=5
	Point=6
	Pair=7
	DirectedPair=8
	Duration=9
	File=10
	URI=11
		
	MaxValue=11
	
	Strings={
		'identifier':Identifier,
		'boolean':Boolean,
		'integer':Integer,
		'float':Float,
		'string':String,
		'point':Point,
		'pair':Pair,
		'directedPair':DirectedPair,
		'duration':Duration,
		'file':File,
		'uri':URI
		}

		
def ParseBaseType(baseType):
	if not BaseType.Strings.has_key(baseType):
		raise ValueError
	return BaseType.Strings[baseType]

class Cardinality:
	"""Cardinality Enumeration"""
	Single=1
	Multiple=2
	Ordered=3
	Record=4
	
	MaxValue=4
	
	Strings={
		'single':Single,
		'multiple':Multiple,
		'ordered':Ordered,
		'record':Record}


def ParseCardinality(cardinality):
	if not Cardinality.Strings.has_key(cardinality):
		raise ValueError
	return Cardinality.Strings[cardinality]


def ParseIdentifier(identifier):
	if not len(identifier) or not (IsLetter(identifier[0]) or identifier[0]=='_'):
		raise ValueError
	for c in identifier[1:]:
		if not (IsLetter(c) or c=="_" or c=='-' or c=='.' or IsDigit(c) or
			IsCombiningChar(c) or IsExtender(c)):
			raise ValueError
	return identifier


class Orientation:
	"""Orientation enumeration"""
	Vertical=1
	Horizontal=2
	
	MaxValue=2
	
	Strings={
		'vertical':Vertical,
		'horizontal':Horizontal
		}

def ParseOrientation(orientation):
	if not Orientation.Strings.has_key(orientation):
		raise ValueError
	return Orientation.Strings[orientation]

		
def CheckValue(cardinality,baseType,value):
	t=type(value)
	if cardinality==Cardinality.Single:
		if baseType in (BaseType.Identifier,BaseType.String,BaseType.File):
			if not t in StringTypes:
				raise ValueError
		elif baseType==BaseType.Boolean:
			if not t is IntType:
				raise ValueError
		elif baseType==BaseType.Integer:
			if not t in (IntType,LongType):
				raise ValueError
		elif baseType==BaseType.Float:
			if not t is FloatType:
				raise ValueError
		elif baseType==BaseType.Point:
			if not t in (ListType,TupleType) and not len(value)==2:
				raise ValueError
			for v in value:
				if not type(value) in (IntType,LongType):
					raise ValueError
		elif baseType in (BaseType.Pair,BaseType.DirectedPair):
			if not t in (ListType,TupleType) and not len(value)==2:
				raise ValueError
			for v in value:
				if not type(value) in StringTypes:
					raise ValueError
		elif baseType==BaseType.Duration:
			if not isinstance(value,Duration):
				raise ValueError
		elif baseTYpe==BaseType.URI:
			if not isinstance(value.URIReference):
				raise ValueError
		else:
			raise ValueError
	elif cardinality in (Cardinality.Multiple,Cardinality.Ordered):
		if not t in (ListType,TupleType):
			raise ValueError
		for v in value:
			CheckValue(Cardinality.Single,baseType,v)
	elif cardinality==Cardinality.Record:
		if not type(value) is DictionaryType:
			raise ValueError
		for v in value.values():
			if not type(v) in (ListType,TupleType) or len(v)!=2:
				raise ValueError
			CheckValue(Cardinality.Single,v[0],v[1])
	else:
		raise ValueError
	
