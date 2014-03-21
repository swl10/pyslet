#! /usr/bin/env python

import string, logging
from types import *

from pyslet.rfc2616_core import *
from pyslet.rfc2616_params import *

import pyslet.iso8601 as iso


class MediaRange(MediaType):
	"""Represents an HTTP media-range.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries.  Quoting from the specification:
	
		"Media ranges can be overridden by more specific media ranges or specific
		media types. If more than one media range applies to a given type, the
		most specific reference has precedence."

	In other words, the following media ranges would be sorted in the
	order shown:
	
	1.	image/png
	2.	image/\*
	3.	text/plain;charset=utf-8
	4.	text/plain
	5.	text/\*
	6.	\*/\*
			
	If we have two rules with identical precedence then we sort them
	alphabetically by type; sub-type and ultimately alphabetically by
	parameters"""
	def __init__(self,type="*",subtype="*",parameters={}):
		super(MediaRange,self).__init__(type,subtype,parameters)
	
	@classmethod
	def FromString(cls,source):
		"""Creates a media-rannge from a *source* string.
		
		Unlike the parent media-type we ignore all spaces."""
		p=HeaderParser(source)
		mr=p.RequireMediaRange()
		p.RequireEnd("media-range")
		return mr
					
	def __repr__(self):
		return "MediaType(%s,%s,%s)"%(repr(self.type),repr(self.subtype),repr(self.parameters))
			
	def __cmp__(self,other):
		result=self.CompareTypes(self.type,other.type)
		if result:
			return result
		result=self.CompareTypes(self.subtype,other.subtype)
		if result:
			return result
		# more parameters means higher precedence
		result=-cmp(len(self.parameters),len(other.parameters))
		if result:
			return result
		return cmp(self.parameters,other.parameters)
			
	def CompareTypes(self,aType,bType):
		if aType=='*':
			if bType=='*':
				return 0
			else:
				return 1
		else:
			if bType=='*':
				return -1
			else:
				return cmp(aType.lower(),bType.lower())

	def MatchMediaType(self,mType):
		"""Tests whether a media-type matches this range.
		
		*mtype*
			A :py:class:`MediaType` instance to be compared to this
			range.
		
		The matching algorithm takes in to consideration wild-cards so
		that \*/\* matches all types, image/* matches any image type and
		so on.
		
		If a media-range contains parameters then each of these must be
		matched exactly in the media-type being tested. Parameter names
		are treated case-insensitively and any additional parameters in
		the media type are ignored.  As a result:
		
		*	text/plain *does not match* the range
			text/plain;charset=utf-8

		*	application/myapp;charset=utf-8;option=on *does* match the
			range application/myapp;option=on"""
		if self.type=='*':
			return True
		elif self.type.lower()!=mType.type.lower():
			return False
		if self.subtype=='*':
			return True
		elif self.subtype.lower()!=mType.subtype.lower():
			return False
		# all the parameters in the range must be matched
		for p,v in self._hp:
			if p not in mType.parameters or mType.parameters[p][1]!=v:
				# e.g. suppose we have a range type/subtype;paramA=1;paramB=2
				# then type/subtype;paramA=1 does not match (we needed paramB=2 as well)
				# and type/subtype;paramA=1;paramB=3 does not match either
				# but type/subtype;paramA=1;paramB=2;paramC=3 does match
				return False
		return True


class AcceptItem(MediaRange):
	"""Represents a single item in an Accept header
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries.
	
	Accept items are sorted by their media ranges.  Equal media ranges
	sort by *descending* qvalue, for example:
	
		text/plain;q=0.75 < text/plain;q=0.5
	
	Extension parameters are ignored in all comparisons."""
	def __init__(self,range=MediaRange(),qvalue=1.0,extensions={}):
		self.range=range		#: the :py:class:`MediaRange` instance that is acceptable
		self.q=qvalue			#: the q-value (defaults to 1.0)
		self.params=extensions	#: any accept-extension parameters
	
	@classmethod
	def FromString(cls,source):
		"""Creates a single AcceptItem instance from a *source* string."""
		p=HeaderParser(source)
		p.ParseSP()
		ai=p.RequireAcceptItem()
		p.ParseSP()
		p.RequireEnd("Accept header item")
		return ai

	def __str__(self):
		result=[str(self.range)]
		if self.params or self.q!=1.0:
			qStr="%.3f"%self.q
			qStr=qStr.rstrip('0')
			qStr=qStr.rstrip('.')
			result.append("; q=%s"%qStr)
			result.append(FormatParameters(self.params))
		return string.join(result,'')

	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=AcceptItem.FromString(other)
		elif not isinstance(other,AcceptItem):
			raise TypeError
		result=cmp(self.range,other.range)
		if result==0:
			if self.q>other.q:
				return -1
			elif self.q<other.q:
				return 1
		return result

	def __hash__(self):
		return hash(self.range,self.q)
					

class AcceptList(object):
	"""Represents the value of an Accept header
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they are constructed from
	one or more :py:class:`AcceptItem` instances.  There are no
	comparison methods.
	
	Instances behave like read-only lists implementing len, indexing and
	iteration in the usual way."""	
	def __init__(self,*args):
		self._items=list(args)
		self._items.sort()
	
	def SelectType(self,mTypeList):
		"""Returns the best match from mTypeList, a list of media-types.
		
		In the event of a tie, the first item in mTypeList is returned."""
		bestMatch=None
		bestQ=0
		for mType in mTypeList:
			# calculate a match score for each input item, highest score wins
			for aItem in self._items:
				if aItem.range.MatchMediaType(mType):
					# we break at the first match as ranges are ordered by precedence
					if aItem.q>bestQ:
						# this is the best match so far, we use strictly greater as
						# q=0 means unacceptable and input types are assumed to be
						# ordered by preference of the caller.
						bestMatch=mType
						bestQ=aItem.q
					break
		return bestMatch
		
	@classmethod
	def FromString(cls,source):
		"""Create an AcceptList from a *source* string."""
		p=HeaderParser(source)
		al=p.RequireAcceptList()
		p.RequireEnd("Accept header")
		return al
	
	def __str__(self):
		return string.join(map(str,self._items),', ')

	def __len__(self):
		return len(self._items)
	
	def __getitem__(self,index):
		return self._items[index]
	
	def __iter__(self):
		return self._items.__iter__()


class AcceptToken(object):
	"""Represents a single item in a token-based Accept-* header
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries.
	
	AcceptToken items are sorted by their token, with wild cards sorting
	behind specified tokens.  Equal values sort by *descending* qvalue,
	for example:
	
		iso-8859-2;q=0.75 < iso-8859-2;q=0.5"""
	def __init__(self,token="*",qvalue=1.0):
		self.token=token		#: the token that is acceptable or "*" for any token
		self._token=token.lower()
		self.q=qvalue			#: the q-value (defaults to 1.0)
	
	@classmethod
	def FromString(cls,source):
		"""Creates a single AcceptToken instance from a *source* string."""
		p=HeaderParser(source)
		p.ParseSP()
		at=p.RequireAcceptToken(cls)
		p.ParseSP()
		p.RequireEnd("Accept token")
		return at

	def __str__(self):
		result=[self.token]
		if self.q!=1.0:
			qStr="%.3f"%self.q
			qStr=qStr.rstrip('0')
			qStr=qStr.rstrip('.')
			result.append(";q=%s"%qStr)
		return string.join(result,'')

	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=AcceptToken.FromString(other)
		elif not isinstance(other,AcceptToken):
			raise TypeError
		if self.token=="*":
			if other.token=="*":
				result=0
			else:
				return 1
		elif other.token=="*":
			return -1
		else:
			result=cmp(self._token,other._token)
		if result==0:
			if self.q>other.q:
				return -1
			elif self.q<other.q:
				return 1
		return result

	def __hash__(self):
		return hash(self._token,self.q)


class AcceptTokenList(object):
	"""Represents the value of a token-based Accept-* header
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they are constructed from
	one or more :py:class:`AcceptToken` instances.  There are no
	comparison methods.
	
	Instances behave like read-only lists implementing len, indexing and
	iteration in the usual way."""	
	ItemClass=AcceptToken

	def __init__(self,*args):
		self._items=list(args)
		self._items.sort()
	
	def SelectToken(self,tokenList):
		"""Returns the best match from tokenList, a list of tokens.
		
		In the event of a tie, the first item in tokenList is returned."""
		bestMatch=None
		bestQ=0
		for token in tokenList:
			_token=token.lower()
			# calculate a match score for each input item, highest score wins
			for aItem in self._items:
				if aItem._token==_token or aItem._token=="*":
					# we break at the first match as accept-tokens are ordered by precedence
					# i.e., with wild-cards at the end of the list as a catch-all
					if aItem.q>bestQ:
						# this is the best match so far, we use strictly greater as
						# q=0 means unacceptable and input types are assumed to be
						# ordered by preference of the caller.
						bestMatch=token
						bestQ=aItem.q
					break
		return bestMatch
		
	@classmethod
	def FromString(cls,source):
		"""Create an AcceptTokenList from a *source* string."""
		p=HeaderParser(source)
		al=p.RequireAcceptTokenList(cls)
		p.RequireEnd("Accept header")
		return al
	
	def __str__(self):
		return string.join(map(str,self._items),', ')

	def __len__(self):
		return len(self._items)
	
	def __getitem__(self,index):
		return self._items[index]
	
	def __iter__(self):
		return self._items.__iter__()


class AcceptCharsetItem(AcceptToken):
	"""Represents a single item in an Accept-Charset header"""
	pass
						
class AcceptCharsetList(AcceptTokenList):
	"""Represents an Accept-Charset header"""
	ItemClass=AcceptCharsetItem

	def SelectToken(self,tokenList):
		"""Overridden to provide default handling of iso-8859-1"""
		bestMatch=None
		bestQ=0
		for token in tokenList:
			_token=token.lower()
			# calculate a match score for each input item, highest score wins
			match=False
			for aItem in self._items:
				if aItem._token==_token or aItem._token=="*":
					match=True
					if aItem.q>bestQ:
						bestMatch=token
						bestQ=aItem.q
					break
			if not match and _token=="iso-8859-1":
				if 1.0>bestQ:
					bestMatch=token
					bestQ=1.0
		return bestMatch
	
class AcceptEncodingItem(AcceptToken):
	"""Represents a single item in an Accept-Encoding header"""
	pass

class AcceptEncodingList(AcceptTokenList):
	"""Represents an Accept-Encoding header"""
	ItemClass=AcceptEncodingItem

	def SelectToken(self,tokenList):
		"""Overridden to provide default handling of identity"""
		bestMatch=None
		bestQ=0
		for token in tokenList:
			_token=token.lower()
			# calculate a match score for each input item, highest score wins
			match=False
			for aItem in self._items:
				if aItem._token==_token or aItem._token=="*":
					match=True
					if aItem.q>bestQ:
						bestMatch=token
						bestQ=aItem.q
					break
			if not match and _token=="identity":
				# the specification says identity is always acceptable,
				# not that it is always the best choice.  Given that it
				# explicitly says that the default charset has
				# acceptability q=1 the omission of a similar phrase
				# here suggests that we should use the lowest possible q
				# value in this case.  We do this by re-using 0 to mean
				# minimally acceptable.
				if bestQ==0:
					bestMatch=token
		return bestMatch


class AcceptLanguageItem(AcceptToken):
	"""Represents a single item in an Accept-Language header."""
	def __init__(self,token="*",qvalue=1.0):
		super(AcceptLanguageItem,self).__init__(token,qvalue)
		if self.token=="*":
			self._range=()
		else:
			self._range=tuple(self._token.split("-"))

	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=AcceptLanguageItem.FromString(other)
		elif not isinstance(other,AcceptLanguageItem):
			raise TypeError
		# sort first by length, longest first to catch most specific match
		result=cmp(len(other._range),len(self._range))
		if result==0:
			# and then secondary sort on alphabetical
			result=cmp(self._range,other._range)
		return result


class AcceptLanguageList(AcceptTokenList):
	"""Represents an Accept-Language header"""
	ItemClass=AcceptLanguageItem

	def __init__(self,*args):
		super(AcceptLanguageList,self).__init__(*args)

	def SelectToken(self,tokenList):
		"""Remapped to :py:meth:`SelectLanguage`"""
		return str(self.SelectLanguage(map(LanguageTag.FromString,tokenList)))
	
	def SelectLanguage(self,langList):
		bestMatch=None
		bestQ=0
		for lang in langList:
			# calculate a match score for each input item, highest score wins
			for aItem in self._items:
				if lang.PartialMatch(aItem._range):
					if aItem.q>bestQ:
						bestMatch=lang
						bestQ=aItem.q
					break
		return bestMatch


class AcceptRanges(object):
	"""Represents the value of an Accept-Ranges response header.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they are constructed from
	a list of string arguments.  If the argument list is empty then a
	value of "none" is assumed.
		
	Instances behave like read-only lists implementing len, indexing and
	iteration in the usual way.  Comparison methods are provided."""	
	def __init__(self,*args):
		self._ranges=args
		self._sorted=map(lambda x:x.lower(),list(args))
		if "none" in self._sorted:
			if len(self._sorted)==1:
				self._ranges=()
				self._sorted=[]
			else:
				raise SyntaxError("none is not a valid range-unit")
		self._sorted.sort()
					
	@classmethod
	def FromString(cls,source):
		"""Create an AcceptRanges value from a *source* string."""
		p=HeaderParser(source)
		ar=p.ParseTokenList()
		if not ar:
			raise SyntaxError("range-unit or none required in Accept-Ranges")
		p.RequireEnd("Accept-Ranges header")
		return AcceptRanges(*ar)
	
	def __str__(self):
		if self._ranges:
			return string.join(map(str,self._ranges),', ')
		else:
			return "none"

	def __len__(self):
		return len(self._ranges)
	
	def __getitem__(self,index):
		return self._ranges[index]
	
	def __iter__(self):
		return self._ranges.__iter__()

	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=AcceptRanges.FromString(other)
		if not isinstance(other,AcceptRanges):
			raise TypeError
		return cmp(self._sorted,other._sorted)


class Allow(object):
	"""Represents the value of an Allow entity header.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they are constructed from
	a list of string arguments which may be empty.
		
	Instances behave like read-only lists implementing len, indexing and
	iteration in the usual way.  Comparison methods are provided."""	
	def __init__(self,*args):
		self._methods=map(lambda x:x.upper(),args)
		self._sorted=list(self._methods)
		self._sorted.sort()
					
	@classmethod
	def FromString(cls,source):
		"""Create an Allow value from a *source* string."""
		p=HeaderParser(source)
		allow=p.ParseTokenList()
		p.RequireEnd("Allow header")
		return Allow(*allow)
	
	def Allowed(self,method):
		"""Tests is *method* is allowed by this value."""
		return method.upper() in self._sorted
		
	def __str__(self):
		return string.join(self._methods,', ')

	def __len__(self):
		return len(self._methods)
	
	def __getitem__(self,index):
		return self._methods[index]
	
	def __iter__(self):
		return self._methods.__iter__()

	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=Allow.FromString(other)
		if not isinstance(other,Allow):
			raise TypeError
		return cmp(self._sorted,other._sorted)


class CacheControl(object):
	"""Represents the value of a Cache-Control general header.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they are constructed from
	a list of arguments which must not be empty.  Arguments are treated
	as follows:
	
	string
		a simple directive with no parmeter
	2-tuple of string and non-tuple
		a directive with a simple parameter
	2-tuple of string and tuple
		a directive with a quoted list-style parameter
		
	Instances behave like read-only lists implementing len, indexing and
	iteration in the usual way.  Instances also support basic key lookup
	of directive names by implementing __contains__ and __getitem__
	(which returns None for defined directives with no parameter and
	raises KeyError for undefined directives.  Instances are not truly
	dictionary like."""	
	def __init__(self,*args):
		self._directives=[]
		self._values={}
		if not len(args):
			raise TypeError("At least one directive required for Cache-Control")
		for a in args:
			if type(a)==TupleType:
				# must be a 2-tuple
				d,v=a
			else:
				d,v=a,None
			d=d.lower()
			self._directives.append(d)
			self._values[d]=v
					
	@classmethod
	def FromString(cls,source):
		"""Create a Cache-Control value from a *source* string."""
		p=HeaderParser(source)
		cc=p.ParseCacheControl()
		p.RequireEnd("Cache-Control header")
		return cc
	
	def __str__(self):
		result=[]
		for d in self._directives:
			v=self._values[d]
			if v is None:
				result.append(d)
			elif type(v)==TupleType:
				result.append("%s=%s"%(d,QuoteString(string.join(map(str,v),", "))))
			else:
				result.append("%s=%s"%(d,QuoteString(str(v),force=False)))
		return string.join(result,", ")

	def __len__(self):
		return len(self._directives)
	
	def __getitem__(self,index):
		if type(index) in StringTypes:
			# look up by key
			return self._values[index.lower()]
		else:
			d=self._directives[index]
			v=self._values[d]
			if v is None:
				return d
			else:
				return (d,v)
	
	def __iter__(self):
		for d in self._directives:
			v=self._values[d]
			if v is None:
				yield d
			else:
				yield (d,v)

	def __contains__(self,key):
		return key.lower() in self._values


class ContentRange(object):
	"""Represents a single content range
	
	firstByte
		Specifies the first byte of the range
	
	lastByte
		Specifies the last byte of the range
	
	totalLength
		Specifies the total length of the entity
	
	With no arguments an invalid range representing an unsatisfied
	range request from an entity of unknown length is created.

	If firstByte is specified on construction lastByte must also
	be specified or TypeError is raised.
		
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable."""
	def __init__(self,firstByte=None,lastByte=None,totalLength=None):
		self.firstByte=firstByte		#: first byte in the range
		self.lastByte=lastByte			#: last byte in the range
		self.totalLength=totalLength	#: total length of the entity or None if not known
		if self.firstByte is not None and self.lastByte is None:
			raise TypeError("ContentRange: lastByte must not be None when firstByte=%i"%self.firstByte)
	
	@classmethod
	def FromString(cls,source):
		"""Creates a single ContentRange instance from a *source* string."""
		p=HeaderParser(source)
		p.ParseSP()
		cr=p.RequireContentRangeSpec()
		p.ParseSP()
		p.RequireEnd("Content-Range specification")
		return cr

	def __str__(self):
		result=["bytes "]
		if self.firstByte is None:
			result.append('*')
		else:
			result.append("%i-%i"%(self.firstByte,self.lastByte))
		result.append("/")
		if self.totalLength is None:
			result.append("*")
		else:
			result.append(str(self.totalLength))
		return string.join(result,'')

	def __len__(self):
		if self.firstByte is not None:
			result=self.lastByte-self.firstByte+1
			if result>0:
				return result
		raise ValueError("Invalid content-range for len")

	def IsValid(self):
		"""Returns True if this range is valid, False otherwise.
		
		A valid range is any non-empty byte range wholly within the entity
		described by the total length.  Unsatisfied content ranges
		are treated as *invalid*."""
		return self.firstByte is not None and self.firstByte<=self.lastByte and self.firstByte>=0 and (
			self.totalLength is None or self.lastByte<self.totalLength)


class HeaderParser(ParameterParser):
	"""A special parser extended to include methods for parsing HTTP headers."""

	def ParseMediaRange(self):
		savePos=self.pos
		try:
			return self.RequireMediaRange()
		except SyntaxError:
			self.SetPos(savePos)
			return None
	
	def RequireMediaRange(self):
		"""Parses a media range returning a :py:class:`MediaRange`
		instance.  Raises SyntaxError if no media-type was found."""		
		self.ParseSP()
		type=self.RequireToken("media-type").lower()
		self.RequireSeparator('/',"media-type")
		subtype=self.RequireToken("media-subtype").lower()
		self.ParseSP()
		parameters={}
		self.ParseParameters(parameters,ignoreAllSpace=False,qMode='q')
		return MediaRange(type,subtype,parameters)
	
	def RequireAcceptItem(self):
		"""Parses a single item from an Accept header, returning a
		:py:class:`AcceptItem` instance.  Raises SyntaxError if no
		item was found."""
		self.ParseSP()
		extensions={}
		range=self.RequireMediaRange()
		self.ParseSP()
		if self.ParseSeparator(';'):
			self.ParseSP()
			qParam=self.RequireToken("q parameter")
			if qParam.lower()!='q':
				raise SyntaxError("Unrecognized q-parameter: %s"%qParam)
			self.ParseSP()
			self.RequireSeparator('=',"q parameter")
			self.ParseSP()
			qvalue=self.ParseQualityValue()
			if qvalue is None:
				raise SyntaxError("Unrecognized q-value: %s"%repr(self.cWord))
			self.ParseParameters(extensions)
		else:
			qvalue=1.0
		return AcceptItem(range,qvalue,extensions)

	def RequireAcceptList(self):
		"""Parses a list of accept items, returning a
		:py:class:`AcceptList` instance.  Raises SyntaxError if no valid
		items were found."""
		items=[]
		self.ParseSP()
		while self.cWord:
			a=self.ParseProduction(self.RequireAcceptItem)
			if a is None:
				break
			items.append(a)
			self.ParseSP()
			if not self.ParseSeparator(','):
				break
		if items:
			return AcceptList(*items)
		else:
			raise SyntaxError("Expected Accept item")

	def RequireAcceptToken(self,cls=AcceptToken):
		"""Parses a single item from a token-based Accept header,
		returning a :py:class:`AcceptToken` instance.  Raises
		SyntaxError if no item was found.
		
		cls
			An optional sub-class of :py:class:`AcceptToken` to create
			instead."""
		self.ParseSP()
		token=self.RequireToken()
		self.ParseSP()
		if self.ParseSeparator(';'):
			self.ParseSP()
			qParam=self.RequireToken("q parameter")
			if qParam.lower()!='q':
				raise SyntaxError("Unrecognized q-parameter: %s"%qParam)
			self.ParseSP()
			self.RequireSeparator('=',"q parameter")
			self.ParseSP()
			qvalue=self.ParseQualityValue()
			if qvalue is None:
				raise SyntaxError("Unrecognized q-value: %s"%repr(self.cWord))
		else:
			qvalue=1.0
		return cls(token,qvalue)

	def RequireAcceptTokenList(self,cls=AcceptTokenList):
		"""Parses a list of token-based accept items, returning an
		:py:class:`AcceptTokenList` instance.  If no
		tokens were found then an *empty* list is returned.
		
		cls
			An optional sub-class of :py:class:`AcceptTokenList` to
			create instead."""
		items=[]
		self.ParseSP()
		while self.cWord:
			a=self.ParseProduction(self.RequireAcceptToken,cls.ItemClass)
			if a is None:
				break
			items.append(a)
			self.ParseSP()
			if not self.ParseSeparator(','):
				break
		return cls(*items)

	def RequireContentRangeSpec(self):
		"""Parses a content-range-spec, returning an
		:py:class:`ContentRange` instance."""
		self.ParseSP()
		unit=self.RequireToken("bytes-unit")
		if unit.lower()!='bytes':
			raise SyntaxError("Unrecognized unit in content-range: %s"%unit)
		self.ParseSP()
		spec=self.RequireToken()
		# the spec must be an entire token, '-' is not a separator
		if spec=="*":
			firstByte=lastByte=None
		else:
			spec=spec.split('-')
			if len(spec)!=2 or not IsDIGITS(spec[0]) or not IsDIGITS(spec[1]):
				raise SyntaxError("Expected digits or * in byte-range-resp-spec")
			firstByte=int(spec[0])
			lastByte=int(spec[1])
		self.ParseSP()	
		self.RequireSeparator('/',"byte-content-range-spec")
		self.ParseSP()
		totalLength=self.RequireToken()
		if totalLength=="*":
			totalLength=None
		elif IsDIGITS(totalLength):
			totalLength=int(totalLength)
		else:
			raise SyntaxError("Expected digits or * for instance-length")
		return ContentRange(firstByte,lastByte,totalLength)
		