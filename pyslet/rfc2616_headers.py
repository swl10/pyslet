#! /usr/bin/env python

import string
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
	def FromString(self,source):
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
			if qStr[-2:]=='00':
				qStr=qStr[:-2]
			elif qStr[-1:]:
				qStr=qStr[:-1]
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

		