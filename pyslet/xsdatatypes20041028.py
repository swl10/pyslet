#! /usr/bin/env python


import string
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
	try:
		return int(src)
	except:
		return None

def EncodeInteger(value):
	return unicode(value)


def DecodeFloat(src):
	try:
		return float(src)
	except:
		return None

def EncodeFloat(value):
	return unicode(value)


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
	def EncodeValue(cls,value):
		"""Encodes one of the enumeration constants returning a string.
		
		If value is None then the encoded default value is returned (if defined) or None."""
		return cls.encode.get(value,cls.encode.get(cls.DEFAULT,None))
	
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