from types import StringTypes, IntType, LongType, FloatType, TupleType, ListType, DictType
from copy import copy
from string import join

from PyAssess.w3c.xml import IsChar, IsLetter, IsDigit, IsCombiningChar, IsExtender, CheckName, Element, Attribute
from PyAssess.w3c.xmlschema import ParseBoolean, FormatBoolean, ParseFloat, FormatFloat, FormatDecimal, ParseInteger, FormatInteger
from PyAssess.ietf.rfc2396 import URIReference

IMSQTINamespace="http://www.imsglobal.org/xsd/imsqti_v2p1"
IMSQTISchemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"

IMSQTINamespaces={
	"http://www.imsglobal.org/xsd/imsqti_v2p0":"2.0",
	"http://www.imsglobal.org/xsd/imsqti_v2p1":"2.1"
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
	
	Values={
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

	Strings=dict(zip(Values.values(),Values.keys()))
		
def ParseBaseType(baseType):
	if not BaseType.Values.has_key(baseType):
		raise ValueError
	return BaseType.Values[baseType]

def CompareBaseTypes(baseTypeA,baseTypeB):
	return baseTypeA is None or baseTypeB is None or baseTypeA==baseTypeB

class Cardinality:
	"""Cardinality Enumeration"""
	Single=1
	Multiple=2
	Ordered=3
	Record=4
	
	MaxValue=4
	
	Values={
		'single':Single,
		'multiple':Multiple,
		'ordered':Ordered,
		'record':Record}

	Strings=dict(zip(Values.values(),Values.keys()))

def ParseCardinality(cardinality):
	if not Cardinality.Values.has_key(cardinality):
		raise ValueError
	return Cardinality.Values[cardinality]


class Orientation:
	"""Orientation enumeration"""
	Vertical=1
	Horizontal=2
	
	MaxValue=2
	
	Values={
		'vertical':Vertical,
		'horizontal':Horizontal
		}

	Strings=dict(zip(Values.values(),Values.keys()))

def ParseOrientation(orientation):
	if not Orientation.Values.has_key(orientation):
		raise ValueError
	return Orientation.Values[orientation]


class View:
	"""View enumeration"""
	Author=1
	Candidate=2
	Proctor=4
	Scorer=8
	TestConstructor=16
	Tutor=32
	
	All=63
	
	MaxValue=63
	
	Values={
		'author':Author,
		'candidate':Candidate,
		'proctor':Proctor,
		'scorer':Scorer,
		'testConstructor':TestConstructor,
		'tutor':Tutor
		}
	
	Strings=dict(zip(Values.values(),Values.keys()))

def ParseView(view):
	vValue=0
	view=view.split()
	for v in view:
		if not View.Values.has_key(v):
			raise ValueError
		vValue+=View.Values[v]
	return vValue

def FormatView(view):
	vMask=1
	viewStr=[]
	while vMask<View.MaxValue:
		if vMask&view:
			viewStr.append(View.Strings[vMask])
		vMask=vMask*2
	return join(viewStr,' ')	

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
		
def ParseIdentifier(identifier):
	if not len(identifier) or not (IsLetter(identifier[0]) or identifier[0]=='_'):
		raise ValueError
	for c in identifier[1:]:
		if not (IsLetter(c) or c=="_" or c=='-' or c=='.' or IsDigit(c) or
			IsCombiningChar(c) or IsExtender(c)):
			raise ValueError
	return identifier

def ParseQTIInteger(valueData):
	value=ParseInteger(valueData)
	if value>2147483647L or value<-2147483648:
		raise ValueError("%s exceeds maximum integer size defined by QTI"%valueData)
	return value

def ParseString(valueData):
	for c in valueData:
		if not IsChar(c):
			raise ValueError
	return valueData

def ParsePair(valueData):
	pair=valueData.split()
	if len(pair)!=2:
		raise ValueError("pair requires exactly 2 identifiers: %s"%valueData)
	return (ParseIdentifier(pair[0]),ParseIdentifier(pair[1]))

def ParsePoint(valueData):
	point=valueData.split()
	if len(point)!=2:
		raise IMSQTIError("point requires exactly 2 integers: %s"%valueData)
	return (ParseQTIInteger(point[0].strip()),ParseQTIInteger(point[1].strip()))

def ParseURI(valueData):
	return URIReference(valueData)
		
def CheckValue(cardinality,baseType,value):
	try:
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
				if not (t in (ListType,TupleType) and len(value)==2):
					raise ValueError
				for v in value:
					if not type(v) in (IntType,LongType):
						raise ValueError
			elif baseType in (BaseType.Pair,BaseType.DirectedPair):
				if not (t in (ListType,TupleType) and len(value)==2):
					raise ValueError
				for v in value:
					if not type(v) in StringTypes:
						raise ValueError
			elif baseType==BaseType.Duration:
				if not isinstance(value,Duration):
					raise ValueError
			elif baseType==BaseType.URI:
				if not isinstance(value,URIReference):
					raise ValueError
			else:
				raise ValueError
		elif cardinality in (Cardinality.Multiple,Cardinality.Ordered):
			if t is not ListType:
				raise ValueError
			for v in value:
				CheckValue(Cardinality.Single,baseType,v)
		elif cardinality==Cardinality.Record:
			if not type(value) is DictType:
				raise ValueError
			for v in value.values():
				if not type(v) in (ListType,TupleType) or len(v)!=2:
					raise ValueError
				CheckValue(Cardinality.Single,v[0],v[1])
		else:
			raise ValueError
	except:
		import pdb;pdb.set_trace()
		
def IsNullValue(value):
	return value in (None,"",[],{})
			
def MatchValues(cardinality,baseType,valueA,valueB):
	"""In the future this could be improved by definining classes with suitable
	comparison methods for those types that are not directly representable
	in Python, that way we could use simple comparison in both ordered and record
	cases."""
	if cardinality==Cardinality.Single:
		if valueA==valueB:
			return 1
		elif baseType==BaseType.Pair and (valueA[0]==valueB[1] and valueA[1]==valueB[0]):
			return 1
		else:
			return 0
	elif cardinality==Cardinality.Multiple:
		# fairly dumb algorithm, check the lengths are the same, then make a shallow
		# copy of valueA and remove each item from valueB from valueA in turn
		if len(valueA)!=len(valueB):
			return 0
		valueA=copy(valueA)
		for vB in valueB:
			index=-1
			for i in range(len(valueA)):
				if MatchValues(Cardinality.Single,baseType,valueA[i],VB):
					index=i
					break
			if index<0:
				# not found
				return 0
			del valueA[index]
		return 1
	elif cardinality==Cardinality.Ordered:
		if len(valueA)!=len(valueB):
			return 0
		for i in range(len(valueA)):
			if not MatchValues(Cardinality.Single,baseType,valueA[i],valueB[i]):
				return 0
		return 1
	elif cardinality==Cardinality.Record:
		keysA=valueA.keys()
		keysB=valueB.keys()
		keysA.sort()
		keysB.sort()
		if keysA!=keysB:
			return 0
		for k in keysA:
			baseTypeA,vA=valueA[k]
			baseTypeB,vB=valueB[k]
			if baseTypeA!=baseTypeB or not MatchValues(Cardinality.Single,baseTypeA,vA,vB):
				 return 0
		return 1
	else:
		raise ValueError

def FormatValue(baseType,value):
	if baseType in (BaseType.Identifier,BaseType.String,BaseType.File):
		return value
	elif baseType==BaseType.Boolean:
		return FormatBoolean(value)
	elif baseType==BaseType.Integer:
		return FormatInteger(value)
	elif baseType==BaseType.Float:
		return FormatQTIFloat(value)
	elif baseType==BaseType.Point:
		return FormatInteger(value[0])+' '+FormatInteger(value[1])
	elif baseType in (BaseType.Pair,BaseType.DirectedPair):
		return value[0]+' '+value[1]
	elif baseType==BaseType.Duration:
		return FormatDuration(value)
	elif baseType==BaseType.URI:
		return str(value)
	else:
		raise ValueError

def FormatQTIFloat(value):
	if value<1e-4 or value>1e10:
		return FormatFloat(value)
	else:
		return FormatDecimal(value)
			
def WriteXMLValue(xf,cardinality,baseType,value):
	if cardinality==Cardinality.Single:
		xf.AppendStartTag(Element(IMSQTINamespace,'value'))
		xf.AppendData(FormatValue(baseType,value))
		xf.AppendEndTag()
	elif cardinality in (Cardinality.Multiple,Cardinality.Ordered):
		for v in value:
			xf.AppendStartTag(Element(IMSQTINamespace,'value'))
			xf.AppendData(FormatValue(baseType,v))
			xf.AppendEndTag()
	elif cardinality==Cardinality.Record:
		keys=value.keys()
		keys.sort()
		for vID in keys:
			v=value[vID]
			xf.AppendStartTag(Element(IMSQTINamespace,'value',[
				Attribute('','fieldIdentifier',vID),
				Attribute('','baseType',BaseType.Strings[v[0]])]))
			xf.AppendData(FormatValue(v[0],v[1]))
			xf.AppendEndTag()
	else:
		raise ValueError
