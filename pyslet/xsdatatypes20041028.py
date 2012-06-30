#! /usr/bin/env python


import string
import math
import pyslet.iso8601 as iso8601

XMLSCHEMA_NAMESPACE="http://www.w3.org/2001/XMLSchema-instance"

def DecodeBoolean(src):
	"""Decodes a boolean value from src.
	
	Returns python constants True or False.  As a convenience, if src is None
	then None is returned."""
	if src is None:
		return None
	elif src=="true":
		return True
	elif src=="false":
		return False
	elif src=="1":
		return True
	elif src=="0":
		return False
	else:
		raise ValueError

def EncodeBoolean(src):
	"""Encodes a boolean value using the canonical lexical representation.
	
	src can be anything that can be resolved to a boolean except None, which
	raises ValueError."""
	if src is None:
		raise ValueError
	elif src:
		return "true"
	else:
		return "false"


def DecodeInteger(src):
	"""Decodes an integer value from a string returning an Integer or Long
	value.

	If string is not a valid lexical representation of an integer then
	ValueError is raised."""
	sign=False
	for c in src:
		v=ord(c)
		if v==0x2B or v==0x2D:
			if sign:
				raise ValueError("Invalid lexical representation of integer: %s"%src)
			else: 
				sign=True
		elif v<0x30 or v>0x39:
			raise ValueError("Invalid lexical representation of integer: %s"%src)
		else:
			# a digit means we've got an empty sign
			sign=True
	return int(src)

def EncodeInteger(value):
	return unicode(value)


def DecodeDecimal(src):
	"""Decodes a decimal value from a string returning a float value.
	
	If string is not a valid lexical representation of an integer then
	ValueError is raised."""
	sign=False
	point=False
	digit=False
	for c in src:
		v=ord(c)
		if v==0x2B or v==0x2D:
			if sign:
				raise ValueError("Invalid lexical representation of decimal: %s"%src)
			else: 
				sign=True
		elif v==0x2E:
			if point:
				raise ValueError("Invalid lexical representation of decimal: %s"%src)
			else:
				point=True
		elif v<0x30 or v>0x39:
			raise ValueError("Invalid lexical representation of integer: %s"%src)
		else:
			# a digit means we've got an empty sign
			sign=True
			digit=True
	if not digit:
		# we must have at least one digit
		raise ValueError("Invalid lexical representation of integer: %s"%src)
	return float(src)	


def EncodeDecimal(value):
	"""Encodes a decimal value into a string."""
	raise UnimplementedError		


def DecodeFloat(src):
	try:
		return float(src)
	except:
		return None

def EncodeFloat(value):
	return unicode(value)


def DecodeDouble(src):
	"""Decodes a double value from a string returning a float."""
	s=src.lower()
	if 'e' in s:
		s=s.split('e')
		if len(s)!=2:
			raise ValueError("Invalid lexical representation of double: %s"%src)
		m,e=s
		m=DecodeDecimal(m)
		e=DecodeInteger(e)
		return m*math.pow(10,e)
	elif s in ("inf","-inf","nan"):
		return float(s)
	else:
		return DecodeDecimal(s)		
		
def EncodeDouble(value,digits=10):
	if digits<1:
		digits=1
	if value==0:
		# canonical representation of 0 is 0.0E0
		return "0.0E0"
	elif math.isnan(value):
		return "NAN"
	elif math.isinf(value):
		return "INF" if value>0 else "-INF"
	if value<0:
		sign='-'
		value=-value
	else:
		sign=''
	try:
		x=math.log10(value)
	except ValueError:
		# not sure if this is possible, a number so small log10 fails
		return "0.0E0"
	m,e=math.modf(x)
	e=int(e)
	r,m=math.modf(math.pow(10,m+digits))
	if r>=0.5:
		m=m+1
	dString=str(int(m))
	# m should originally have been in [1,10) but we need to check for over/underflow
	if len(dString)>digits+1:
		# overflow
		e=e+1
	elif len(dString)<=digits:
		# underflow - unlikely
		e=e-1
	assert dString[0]!=u'0'
	return string.join((sign,dString[0],'.',dString[1],dString[2:].rstrip(u'0'),'E',str(e)),'')

def DecodeDateTime(src):
	try:
		return iso8601.TimePoint(src)
	except:
		return None

def EncodeDateTime(value):
	return value.GetCalendarString()


class Enumeration:
	@classmethod
	def DecodeValue(cls,src):
		"""Decodes a string returning a value in this enumeration.
		
		If no legal value can be decoded then ValueError is raised."""
		try:
			src=src.strip()
			return cls.decode[src]
		except KeyError:
			raise ValueError("Can't decode %s from %s"%(cls.__name__,src))

	@classmethod
	def DecodeLowerValue(cls,src):
		"""Decodes a string, converting it first to lower case first.

		Returns a value in this enumeration.  If no legal value can be decoded
		then ValueError is raised."""
		try:
			src=src.lower()
			return cls.decode[src]
		except KeyError:
			raise ValueError("Can't decode %s from %s"%(cls.__name__,src))
	
	@classmethod
	def DecodeTitleValue(cls,src):
		"""Decodes a string, converting it to title case first.
		
		Returns a value in this enumeration.  If no legal value can be decoded
		then ValueError is raised."""
		try:
			src=src.strip()
			src=src[0].upper()+src[1:].lower()
			return cls.decode[src]
		except KeyError:
			raise ValueError("Can't decode %s from %s"%(cls.__name__,src))
	
	@classmethod
	def DecodeValueList(cls,decoder,src):
		"""Decodes a space-separated string of values using *decoder* which must
		be one of the Decode\\*Value methods of the enumeration.  The result is
		an ordered list of values (possibly containing duplicates).
		
		Example usage::
		
			fruit.DecodeValueList(fruit.DecodeLowerValue,"apples oranges, pears")
			# returns [ fruit.apples, fruit.oranges, fruit.pears ]"""
		return map(decoder,src.split())				
	
	@classmethod
	def DecodeValueDict(cls,decoder,src):
		"""Decodes a space-separated string of values using *decoder* which must
		be one of the Decode\\*Value methods of the enumeration.  The result is
		a dictionary mapping the values found as keys onto the strings used
		to represent them.  Duplicates are mapped to the first occurrence of the
		encoded value.
		
		Example usage::
		
			fruit.DecodeValueDict(fruit.DecodeLowerValue,"Apples oranges PEARS")
			# returns...
			{ fruit.apples:'Apples', fruit.oranges:'oranges', fruit.pears:'PEARS' }"""
		result={}
		for s in src.split():
			sv=decoder(s)
		if not sv in result:
			result[sv]=s
		return result
		 
	@classmethod
	def EncodeValue(cls,value):
		"""Encodes one of the enumeration constants returning a string.
		
		If value is None then the encoded default value is returned (if defined) or None."""
		return cls.encode.get(value,cls.encode.get(cls.DEFAULT,None))
	
	@classmethod
	def EncodeValueList(cls,valueList):
		"""Encodes a list of enumeration constants returning a space-separated string.
		
		If valueList is empty then an empty string is returned."""
		return string.join(map(cls.EncodeValue,valueList),' ')
	
	@classmethod
	def EncodeValueDict(cls,valueDict,sortKeys=True):
		"""Encodes a dictionary of enumeration constants returning a space-separated string.
		
		If valueDict is empty then an empty string is returned.  Note that the
		canonical representation of each value is used.  Extending the example
		given in :py:meth:`DecodeValueDict`::
		
			fruit.EncodeValueDict(fruit.DecodeValueDict(fruit.DecodeLowerValue,
				"Apples oranges PEARS"))
			# returns...
			"apples oranges pears"
		
		The order of the encoded values in the string is determined by the sort
		order of the enumeration constants.  This ensures that equivalent
		dictionaries are always encoded to equivalent strings.  In the above
		example::
		
			fruit.apples < fruit.oranges and fruit.oranges < fruit.pears
		
		If you have large lists then you can skip the sorting step by passing
		False for *sortKeys* to improve performance at the expense of a
		predictable encoding."""
		values=valueDict.keys()
		if sortKeys:
			values.sort()
		return cls.EncodeValueList(values)
							
	DEFAULT=None	#: the default value of the enumeration or None if there is no default


def MakeEnumeration(e,defaultValue=None):
	"""Adds convenience attributes to the class 'e'
	
	This function assumes that e has an attribute 'decode' that is a dictionary
	which maps strings onto enumeration values.  This function creates the reverse
	mapping called 'encode' and also defines constant attribute values that are
	equivalent to the keys of decode and can be used in code in the form e.key.
	
	If *defaultValue* is not None then it must be on of the strings in the
	decode dictionary.  It is then used to set the *DEFAULT* value."""
	setattr(e,'encode',dict(zip(e.decode.values(),e.decode.keys())))
	map(lambda x:setattr(e,x,e.decode[x]),e.decode.keys())
	if defaultValue:
		setattr(e,'DEFAULT',e.decode[defaultValue])

def MakeEnumerationAliases(e,aliases):
	"""Adds *aliases* from a dictionary, declaring additional convenience attributes.
	
	This function assumes that :py:func:`MakeEnumeration` has already been used
	to complete the declaration of the enumeration.  The aliases are added to
	the decode dictionary but, for obvious reasons, not to the encode
	dictionary."""
	for alias,key in aliases.items():
		e.decode[alias]=e.decode[key]
	map(lambda x:setattr(e,x,e.decode[x]),aliases.keys())

def MakeLowerAliases(e):
	"""Adds *aliases* by converting all keys to lower case.
	
	Assumes that :py:func:`MakeEnumeration` has already been used to complete
	the declaration of the enumeration.  You must call this function to complete
	the declaration before relying on calls to
	:py:meth:`Enumeration.DecodeLowerValue`."""
	for key in e.decode.keys():
		alias=key.lower()
		if not alias in e.decode:
			# Declare this alias
			e.decode[alias]=e.decode[key]
			setattr(e,alias,e.decode[key])				  


def WhiteSpaceReplace(value):
	output=[]
	for c in value:
		if c in u"\x09\x0A\x0D":
			output.append(unichr(0x20))
		else:
			output.append(c)
	return string.join(output,'')


def WhiteSpaceCollapse(value):
	output=[]
	gotSpace=False
	for c in value:
		if c in u"\x09\x0A\x0D\x20":
			gotSpace=True
		else:
			if output and gotSpace:
				output.append(unichr(0x20))
				gotSpace=False
			output.append(c)
	return string.join(output,'')