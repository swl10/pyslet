#! /usr/bin/env python
"""Utilities to aid interaction with the unicode database"""

from sys import maxunicode
from pickle import dump,load
from urllib import urlopen
import types, string, os.path

CHINESE_TEST=u'\u82f1\u56fd'

UCDDatabaseURL="http://www.unicode.org/Public/UNIDATA/UnicodeData.txt"
UCDBlockDatabaseURL="http://www.unicode.org/Public/UNIDATA/Blocks.txt"
UCDCategories={}
UCDBlocks={}

CATEGORY_FILE="unicode5_catogories.pck"
BLOCK_FILE="unicode5_blocks.pck"


MagicTable={
	'\x00\x00\xfe\xff':'utf_32_be',			# UCS-4, big-endian machine (1234 order)
	'\xff\xfe\x00\x00':'utf_32_le',			# UCS-4, little-endian machine (4321 order)
	'\x00\x00\xff\xfe':'utf_32',			# UCS-4, unusual octet order (2143)
	'\xfe\xff\x00\x00':'utf_32',			# UCS-4, unusual octet order (3412)
	'\xfe\xff\x2a\x2a':'utf_16_be',			# UTF-16, big-endian
	'\xff\xfe\x2a\x2a':'utf_16_le',			# UTF-16, little-endian
	'\x00\x00\x00\x2a':'utf_32_be',			# UCS-4 or other encoding with a big-endian 32-bit code unit
	'\x2a\x00\x00\x00':'utf_32_le',			# UCS-4 or other encoding with a little-endian 32-bit code unit
	'\x00\x00\x2a\x00':'utf_32_le',			# UCS-4 or other encoding with an unusual 32-bit code unit
	'\x00\x2a\x00\x00':'utf_32_le',			# UCS-4 or other encoding with an unusual 32-bit code unit		
	'\x00\x2a\x00\x2a':'utf_16_be',			# UTF-16BE or big-endian ISO-10646-UCS-2 or other encoding with a 16-bit code unit
	'\x2a\x00\x2a\x00':'utf_16_le',			# UTF-16LE or little-endian ISO-10646-UCS-2 or other encoding with a 16-bit code unit
	'\x2a\x2a\x2a\x2a':'utf_8'				# UTF-8, ISO 646, ASCII or similar
	}
	
def DetectEncoding(magic):
	"""Given a raw string of bytes this function looks at (up to) four
	bytes and returns a best guess at the unicode encoding being used
	for the data."""
	if magic[0:3]=='\xef\xbb\xbf':
		# catch this odd one first
		return 'utf_8_sig'
	# now we're only interested in a handful of values
	keepers="\x00\xfe\xff"
	key=[]
	for i in xrange(4):
		# star - as good as any
		if i>=len(magic):
			key.append('\x2a')
		elif magic[i] in keepers:
			key.append(magic[i])
		else:
			key.append('\x2A')
	key=string.join(key,'')
	if key in MagicTable:
		return MagicTable[key]
	else:
		return None


class CharClass:
	"""Represents a class of unicode characters.
	
	A class of characters is represented internally by a list of character ranges
	that define the class.  This is efficient because most character classes are
	defined in blocks of characters.
	
	For the constructor, String arguments add all characters in the string to
	the class.  For example, CharClass('abcxyz') creates a class comprising two
	ranges: a-c and x-z.
	
	Tuple/List arguments can be used to pass pairs of characters that define
	a range.  For example, CharClass(('a','z')) creates a class comprising the
	letters a-z.
	
	Instances of CharClass can also be used in the constructor to add an
	existing class."""
	
	@classmethod
	def UCDCategory(cls,category):
		"""Returns the character class representing the Unicode category.
		
		You must not modify the returned instance, if you want to derive a
		character class from one of the standard Unicode categories then you
		should create a copy by passing the result of this class method to the
		CharClass constructor, e.g. to create a class of all general controls
		and the space character::
		
			c=CharClass(CharClass.UCDCategory(u"Cc"))
			c.AddChar(u" ")"""
		global UCDCategories
		if not UCDCategories:
			# The category table is empty, so we need to load it
			LoadCategoryTable()
		return UCDCategories[category]
		
	@classmethod
	def UCDBlock(cls,blockName):
		"""Returns the character class representing the Unicode block.
		
		You must not modify the returned instance, if you want to derive a
		character class from one of the standard Unicode blocks then you
		should create a copy by passing the result of this class method to the
		CharClass constructor, e.g. to create a class combining all Basic Latin characters
		and those in the Latin-1 Supplement::
		
			c=CharClass(CharClass.UCDBlock(u"Basic Latin"))
			c.AddClass(CharClass.UCDBlock(u"Latin-1 Supplement")"""
		global UCDBlocks
		if not UCDBlocks:
			# The block table is empty, so we need to load it
			LoadBlockTable()
		return UCDBlocks[_NormalizeBlockName(blockName)]
		
	def __init__(self,*args):
		self.ranges=[]
		for arg in args:
			if type(arg) in types.StringTypes:
				# Each character in the string is put in the class
				for c in arg:
					self.AddChar(c)
			elif type(arg) in (types.TupleType,types.ListType):
				self.AddRange(arg[0],arg[1])
			elif isinstance(arg,CharClass):
				self.AddClass(arg)
			else:
				raise ValueError
	
	def __repr__(self):
		"""Create a representation of the class suitable for pasting into python code"""
		result=['CharClass(']
		firstRange=True
		for r in self.ranges:
			if firstRange:
				firstRange=False
			else:
				result.append(', ')
			if r[0]==r[1]:
				result.append(repr(r[0]))
			else:
				result.append('(')
				result.append(repr(r[0]))
				result.append(',')
				result.append(repr(r[1]))
				result.append(')')
		result.append(')')
		return string.join(result,'')
	
	_SetControls={
		u"\x07":"\\a",
		u"\x08":"\\b",
		u"\x09":"\\t",
		u"\x0A":"\\n",
		u"\x0B":"\\v",
		u"\x0C":"\\f",
		u"\x0D":"\\r"	}

	def _SetEscape(self,c):
		"""Escapes characters for inclusion in a set, i.e., -, \,  and ]"""
		if c in u"-\\]":
			return u"\\"+c
		else:
			return self._SetControls.get(c,c)
	
	_ReControls={
		u"\x07":"\\a",
		u"\x09":"\\t",
		u"\x0A":"\\n",
		u"\x0B":"\\v",
		u"\x0C":"\\f",
		u"\x0D":"\\r"	}
		
	def _ReEscape(self,c):
		"""Escapes characters for inclusion in a regular expression outside a set"""
		if c in u".^$*+?{}\\[]|()":
			return u"\\"+c
		else:
			return self._ReControls.get(c,c)
			
	def __unicode__(self):
		"""Returns a Python regular expression representing this range."""
		result=[]
		if len(self.ranges)==0:
			# we generally try and avoid representing maxunicode in a range
			# by using negation.  However, in the case of an empty range
			# we have no choice.
			return u"[^\\x00-%s]"%unichr(maxunicode)
		elif self.ranges[-1][1]==unichr(maxunicode):
			# to avoid maxunicode we negate this range
			neg=CharClass(self)
			neg.Negate()
			result=unicode(neg)
			if result[0]=="[":
				return "[^%s]"%result[1:-1]
			elif result[0]=="\\":
				# we may not need the escape
				if result=="\\]":
					return "[^\\]]"
				elif result in self._ReControls.values():
					return "[^%s]"%result
				else:
					return "[^%s]"%result[1]
			else:
				return "[^%s]"%result
		if len(self.ranges)==1:
			r=self.ranges[0]
			if r[0]==r[1]:
				# a single character
				return self._ReEscape(r[0])
		addCaret=False
		for r in self.ranges:
			if r[0]=="^":
				addCaret=True
				r0=u"_"
			else:
				r0=r[0]
			if ord(r0)>ord(r[1]):
				continue
			elif r0==r[1]:
				# just a singleton
				result.append(self._SetEscape(r0))
			elif ord(r0)+1==ord(r[1]):
				# a dumb range, remove the hyphen
				result.append("%s%s"%(self._SetEscape(r0),self._SetEscape(r[1])))
			else:
				result.append("%s-%s"%(self._SetEscape(r0),self._SetEscape(r[1])))
		if addCaret:
			result.append(u'^')
		return u"[%s]"%string.join(result,u"")				
					
	def FormatRe(self):
		"""Create a representation of the class suitable for putting in [] in a
		python regular expression"""
		pyCharSet=[]
		for a,z in self.ranges:
			pyCharSet.append(self.FormatReChar(a))
			if a==z:
				continue
			if ord(z)>ord(a)+1:
				pyCharSet.append('-')
			pyCharSet.append(self.FormatReChar(z))
		return string.join(pyCharSet,'')
	
	def FormatReChar(self,c):
		if c in "-]\\":
			# prepen a backslash
			return "\\"+c
		else:
			return c
			
	def __eq__(self,other):
		"""Compares two character classes for equality."""
		return self.ranges==other.ranges
	
	def AddRange(self,a,z):
		"""Adds a range of characters from a to z to the class"""
		if z<a:
			x=z;z=a;a=x
		a=unicode(a);z=unicode(z)
		if self.ranges:
			matchA,indexA=self.BisectionSearch(a,0,len(self.ranges)-1)
			matchZ,indexZ=self.BisectionSearch(z,0,len(self.ranges)-1)
			if matchA:
				if matchZ:
					# Both ends of the new range are already matched
					if indexA==indexZ:
						# Nothing to do
						return
					else:
						# We need to join the ranges from indexA to and including indexZ
						self.ranges[indexA:indexZ+1]=[[self.ranges[indexA][0],self.ranges[indexZ][1]]]
				else:
					# Note that at this point, indexZ must be > indexA
					# We need to join the ranges from indexA up to but *not* including indexZ
					# extending the last range to include z
					self.ranges[indexA:indexZ]=[[self.ranges[indexA][0],z]]
			elif matchZ:
				# We need to join the ranges from indexA up to and including indexZ
				# extending the first range to include a (works even if indexA==indexZ)
				self.ranges[indexA:indexZ+1]=[[a,self.ranges[indexZ][1]]]
			else:
				# We need to join the ranges from indexA to indexZ-1, extending them to include
				# a and z respectively.  Note that if indexA==indexZ then no ranges are joined
				# and the slice assignment simply inserts a new range.
				self.ranges[indexA:indexZ]=[[a,z]]
			self.Merge(indexA)
		else:
			self.ranges=[[a,z]]
		
	def SubtractRange(self,a,z):
		"""Subtracts a range of characters from the character class"""
		if z<a:
			x=z;z=a;a=x
		a=unicode(a);z=unicode(z)
		if self.ranges:
			matchA,indexA=self.BisectionSearch(a,0,len(self.ranges)-1)
			matchZ,indexZ=self.BisectionSearch(z,0,len(self.ranges)-1)
			if matchA:
				if matchZ:
					# Both ends of the new range are matched
					if indexA==indexZ:
						# a-z is entirely within a single range 
						A,Z=self.ranges[indexA]
						if ord(A)==ord(Z) or (ord(A)==ord(a) and ord(Z)==ord(z)):
							# This is either a singleton range, so a==z must be true too!
							# or we have an exact range match
							del self.ranges[indexA]
						elif ord(A)==ord(a):
							# Remove the left portion of the range
							self.ranges[indexA][0]=unichr(ord(z)+1)
						elif ord(Z)==ord(z):
							# Remove the right portion of the range
							self.ranges[indexA][1]=unichr(ord(a)-1)
						else:
							# We need to split this range
							self.ranges[indexA][1]=unichr(ord(a)-1)
							self.ranges.insert(indexA+1,[unichr(ord(z)+1),Z])
					else:
						# We need to trim indexA and indexZ and remove all ranges between
						A,Z=self.ranges[indexA]
						if ord(A)==ord(Z) or ord(a)==ord(A):
							# remove this entire range
							snipA=indexA
						else:
							# Remove the right portion of the range
							self.ranges[indexA][1]=unichr(ord(a)-1)
							snipA=indexA+1
						A,Z=self.ranges[indexZ]
						if ord(A)==ord(Z) or ord(z)==ord(Z):
							# remove this entire range
							snipZ=indexZ+1
						else:
							# Remove the left portion of the range
							self.ranges[indexZ][0]=unichr(ord(z)+1)
							snipZ=indexZ
						if snipZ>=snipA:
							del self.ranges[snipA:snipZ]
				else:
					# We need to trim indexA and delete up to, but not including, indexZ
					A,Z=self.ranges[indexA]
					if ord(A)==ord(Z) or ord(a)==ord(A):
						snip=indexA
					else:
						self.ranges[indexA][1]=unichr(ord(a)-1)
						snip=indexA+1
					del self.ranges[snip:indexZ]
			elif matchZ:
				# We need to trim indexZ and delete to the left up to and including indexA
				A,Z=self.ranges[indexZ]
				if ord(A)==ord(Z) or ord(z)==ord(Z):
					snip=indexZ+1
				else:
					self.ranges[indexZ][0]=unichr(ord(z)+1)
					snip=indexZ
				del self.ranges[indexA:snip]
			else:
				# We need to remove the ranges from indexA to indexZ-1. Note that if
				# indexA==indexZ then no ranges are removed
				del self.ranges[indexA:indexZ]
	
	def AddChar(self,c):
		"""Adds a single character to the character class"""
		c=unicode(c)
		if self.ranges:
			match,index=self.BisectionSearch(c,0,len(self.ranges)-1)
			if not match:
				self.ranges.insert(index,[c,c])
				self.Merge(index)
		else:
			self.ranges=[[c,c]]
	
	def SubtractChar(self,c):
		"""Subtracts a single character from the character class"""
		c=unicode(c)
		if self.ranges:
			match,index=self.BisectionSearch(c,0,len(self.ranges)-1)
			if match:
				a,z=self.ranges[index]
				if ord(a)==ord(z):
					# This is a singleton range
					del self.ranges[index]
				elif ord(a)==ord(c):
					self.ranges[index][0]=unichr(ord(a)+1)
				elif ord(z)==ord(c):
					self.ranges[index][1]=unichr(ord(z)-1)
				else:
					# We need to split this range
					self.ranges[index][1]=unichr(ord(c)-1)
					self.ranges.insert(index+1,[unichr(ord(c)+1),z])
	
	def AddClass(self,c):
		"""Adds all the characters in c to the character class (union operation)"""
		if self.ranges:
			for r in c.ranges:
				self.AddRange(r[0],r[1])
		else:
			# take a short cut here, if we have no ranges yet just copy them
			for r in c.ranges:
				self.ranges.append(r)
							
	def SubtractClass(self,c):
		"""Subtracts all the characters in c from the character class"""
		for r in c.ranges:
			self.SubtractRange(r[0],r[1])
	
	def Negate(self):
		"""Negates this character class"""
		max=CharClass([unichr(0),unichr(maxunicode)])
		max.SubtractClass(self)
		self.ranges=max.ranges
				
	def Merge(self,index):
		"""Used internally to merge the range at index with its neighbours if possible"""
		a,z=self.ranges[index]
		indexA=indexZ=index
		if indexA>0:
			ap=self.ranges[indexA-1][1]
			if ord(ap)>=ord(a)-1:
				# Left merge
				indexA=indexA-1
		elif indexZ<len(self.ranges)-1:
			zn=self.ranges[indexZ+1][0]
			if ord(zn)<=ord(z)+1:
				# Right merge
				indexZ=indexZ+1
		if indexA!=indexZ:
			# Do the merge
			self.ranges[indexA:indexZ+1]=[[self.ranges[indexA][0],self.ranges[indexZ][1]]]
		
	def Test(self,c):
		"""Test a unicode character, return True if the character is in the class.

		If c is None False is returned."""
		if c is None:
			return False
		elif self.ranges:
			match,index=self.BisectionSearch(c,0,len(self.ranges)-1)
			return match
		else:
			return False

	def BisectionSearch(self,c,rmin,rmax):
		"""Performs a recursive bisection search on the character class for c.
		
		c is the character to search for
		rmin and rmax define a slice on the list of ranges in which to search
		
		The result is a tuple comprising a flag indicating if c is in the part
		of the class being searched and an integer index of the range into which c
		falls or, if c was not found, then it is the index at which a new range
		(containing only c) should be inserted."""
		#print self.ranges
		#print "Searching in %i,%i"%(rmin,rmax)
		if rmin==rmax:
			# is c in this range
			if c>self.ranges[rmin][1]:
				return (False,rmin+1)
			elif c<self.ranges[rmin][0]:
				return (False,rmin)
			else:
				return (True,rmin)
		else:
			rtry=(rmin+rmax)//2
			if c<=self.ranges[rtry][1]:
				return self.BisectionSearch(c,rmin,rtry)
			else:
				return self.BisectionSearch(c,rtry+1,rmax)


def LoadCategoryTable():
	"""Loads the category table from a resource file."""
	global UCDCategories
	f=file(os.path.join(os.path.dirname(__file__),CATEGORY_FILE),'r')
	UCDCategories=load(f)
	f.close()


def _GetCatClass(catName):
	global UCDCategories
	if catName in UCDCategories:
		return UCDCategories[catName]
	else:
		cat=CharClass()
		UCDCategories[catName]=cat
		return cat
	
def ParseCategoryTable():
	global UCDCategories
	UCDCategories={}
	nextCode=0
	mark=None
	markMajorCategory=None
	markMinorCategory=None
	nMajorCat=_GetCatClass(u'C')
	nMinorCat=_GetCatClass(u'Cn')
	for line in urlopen(UCDDatabaseURL).readlines():
		# disregard any comments
		line=line.split('#')[0]
		if not line:
			continue
		fields=line.split(';')
		codePoint=int(fields[0],16)
		assert codePoint>=nextCode,"Unicode database error: code points went backwards: at %08X"%codePoint
		if codePoint>maxunicode:
			print "Warning: category table limited by narrow python build"
			break
		category=fields[2].strip()
		assert len(category)==2,"Unexpected category field"
		majorCategory=_GetCatClass(category[0])
		minorCategory=_GetCatClass(category)
		charName=fields[1].strip()
		if mark is None:
			if charName[0]=='<' and charName[-6:]=="First>":
				mark=codePoint
				markMajorCategory=majorCategory
				markMinorCategory=minorCategory
			else:
				majorCategory.AddChar(unichr(codePoint))
				minorCategory.AddChar(unichr(codePoint))
			if codePoint>nextCode:
				# we have skipped a load of code-points
				nMajorCat.AddRange(unichr(nextCode),unichr(codePoint-1))
				nMinorCat.AddRange(unichr(nextCode),unichr(codePoint-1))
		else:
			# end a marked range
			assert minorCategory==markMinorCategory, "Unicode character range end-points with non-matching general categories"
			markMajorCategory.AddRange(unichr(mark),unichr(codePoint))
			markMinorCategory.AddRange(unichr(mark),unichr(codePoint))
			mark=None
			markMajorCategory=None
			markMinorCategory=None
		nextCode=codePoint+1
	# when we finally exit from this loop we should not be in a marked range
	assert mark is None,"Unicode database ended during character range definition: %08X-?"%mark
	f=file(os.path.join(os.path.dirname(__file__),CATEGORY_FILE),'w')
	dump(UCDCategories,f)
	f.close()


def LoadBlockTable():
	"""Loads the block table from a resource file."""
	global UCDBlocks
	f=file(os.path.join(os.path.dirname(__file__),BLOCK_FILE),'r')
	UCDBlocks=load(f)
	f.close()


def _NormalizeBlockName(blockName):
	"""Implements Unicode name normalization for block names.
	
	Removes white space, '-', '_' and forces lower case.""" 
	blockName=string.join(blockName.split(),'')
	blockName=blockName.replace('-','')
	return blockName.replace('_','').lower()

	
def ParseBlockTable():
	global UCDBlocks
	UCDBlocks={}
	narrowWarning=False
	for line in urlopen(UCDBlockDatabaseURL).readlines():
		line=line.split('#')[0].strip()
		if not line:
			continue
		fields=line.split(';')
		codePoints=fields[0].strip().split('..')
		codePoint0=int(codePoints[0],16)
		codePoint1=int(codePoints[1],16)
		# the Unicode standard tells us to remove -, _ and any whitespace before case-ignore comparison
		blockName=_NormalizeBlockName(fields[1])
		if codePoint0>maxunicode:
			if not narrowWarning:
				print "Warning: block table limited by narrow python build"
			narrowWarning=True
			continue
		elif codePoint1>maxunicode:
			codePoint1=maxunicode
			if not narrowWarning:
				print "Warning: block table limited by narrow python build"
			narrowWarning=True
		UCDBlocks[blockName]=CharClass((unichr(codePoint0),unichr(codePoint1)))
	f=file(os.path.join(os.path.dirname(__file__),BLOCK_FILE),'w')
	dump(UCDBlocks,f)
	f.close()


class BasicParser(object):
	"""An abstract class for parsing unicode strings."""

	def __init__(self,source):
		self.raw=type(source) is not types.UnicodeType
		"""Indicates if source is being parsed raw (as OCTETS or plain ASCII
		characters, or as Unicode characters.  This may affect the
		interpretation of some productions."""
		self.src=source		#: the string being parsed
		self.pos=-1			#: the position of the current character
		self.theChar=None
		"""The current character or None if the parser is positioned outside the
		src string."""
		self.NextChar()
	
	def SetPos(self,newPos):
		"""Sets the position of the parser to *newPos*"""
		self.pos=newPos-1
		self.NextChar()

	def NextChar(self):
		"""Points the parser at the next character, updating *pos* and *theChar*."""
		self.pos+=1
		if self.pos>=0 and self.pos<len(self.src):
			self.theChar=self.src[self.pos]
		else:
			self.theChar=None

	def Peek(self,nChars):
		"""Returns a string consisting of the next *nChars* characters.
		
		If there are less than nChars remaining then a shorter string is returned."""
		return self.src[self.pos:self.pos+nChars]
	
	def RequireProduction(self,result,production=None):
		"""Returns *result* if not None or raises ValueError.
		
		*	production can be used to customize the error message."""
		if result is None:
			if production is None:
				raise ValueError("Error at ...%s"%self.Peek(10))
			else:
				raise ValueError("Expected %s at ...%s"%(production,self.Peek(10)))
		else:
			return result

	def ParseProduction(self,requireMethod,*args):
		"""Executes the bound method *requireMethod* passing *args*.
		
		If successful the result of the method is returned.  If
		ValueError is raised, the exception is caught, the parser
		rewound and None is returned."""
		savePos=self.pos
		try:
			return requireMethod(*args)
		except ValueError:
			self.SetPos(savePos)
			return None
			
	def RequireProductionEnd(self,result,production=None):
		"""Returns *result* if not None and parsing is complete or raises ValueError.
		
		*	production can be used to customize the error message."""
		result=self.RequireProduction(result,production)
		self.RequireEnd(production)
		return result
				
	def Match(self,matchString):
		"""Returns true if *matchString* is at the current position"""
		if self.theChar is None:
			return False
		else:
			return self.src[self.pos:self.pos+len(matchString)]==matchString
			
	def Parse(self,matchString):
		"""Returns *matchString* if *matchString* is at the current position.
		
		Advances the parser to the first character after matchString.  Returns
		an *empty string* otherwise"""
		if self.Match(matchString):
			self.SetPos(self.pos+len(matchString))
			return matchString
		else:
			return ''

	def ParseUntil(self,matchString):
		"""Returns all characters up until the first instance of *matchString*.
		
		Advances the parser to the first character *of* matchString.  If
		matchString is not found then all the remaining characters in
		the source are parsed."""
		matchPos=self.src.find(matchString,self.pos)
		if matchPos==-1:
			result=self.src[self.pos:]
			self.SetPos(len(self.src))
		else:
			result=self.src[self.pos:matchPos]
			self.SetPos(matchPos)
		return result
			
	def Require(self,matchString,production=None):
		"""Parses *matchString* or raises ValueError.
		
		*	production can be used to customize the error message."""
		if not self.Parse(matchString):
			tail="%s, found %s"%(repr(matchString),repr(self.Peek(len(matchString))))
			if production is None:
				raise ValueError("Expected %s"%tail)
			else:
				raise ValueError("%s: expected %s"%(production,tail))
			
	def MatchOne(self,matchChars):
		"""Returns true if one of *matchChars* is at the current position"""
		if self.theChar is None:
			return False
		else:
			return self.theChar in matchChars

	def ParseOne(self,matchChars):
		"""Parses one of *matchChars*.  Returns the character or None if no match is found."""
		if self.MatchOne(matchChars):
			result=self.theChar
			self.NextChar()
			return result
		else:
			return None

	def MatchInsensitive(self,lowerString):
		"""Returns true if *lowerString* is at the current position (ignoring case).
		
		*lowerString* must be a lower-cased string."""
		if self.theChar is None:
			return False
		else:
			return self.src[self.pos:self.pos+len(lowerString)].lower()==lowerString
			
	def ParseInsensitive(self,lowerString):
		"""Returns *lowerString* if *lowerString* is at the current position (ignoring case).
		
		Advances the parser to the first character after matchString.  Returns
		an *empty string* otherwise.  *lowerString& must be a lower-cased
		string."""
		if self.MatchInsensitive(lowerString):
			self.SetPos(self.pos+len(lowerString))
			return lowerString
		else:
			return ''

	def MatchDigit(self):
		"""Returns true if the current character is a digit"""
		return self.MatchOne("0123456789")

	def ParseDigit(self):
		"""Parses a digit character.  Returns the digit, or None if no digit is found."""
		return self.ParseOne("0123456789")

	def ParseDigits(self,min,max=None):
		"""Parses min digits, and up to max digits, returning the string of digits.
		
		If *max* is None then there is no maximum.
		
		If min digits can't be parsed then None is returned."""
		savePos=self.pos
		result=[]
		while max is None or len(result)<max:
			d=self.ParseDigit()
			if d is None:
				break
			else:
				result.append(d)
		if len(result)<min:
			self.SetPos(savePos)
			return None
		return string.join(result,'')

	def ParseInteger(self,min=None,max=None,maxDigits=None):
		"""Parses an integer (or long) with value between min and max, returning the integer.
		
		*	*min* can be None to indicate no lower limit
		
		*	*max* can be None to indicate no upper limit
		
		*	*maxDigits* sets a limit on the number of digits
		
		If a suitable integer can't be parsed then None is returned."""
		savePos=self.pos
		d=self.ParseDigits(1,maxDigits)
		if d is None:
			return None
		else:
			d=int(d)
			if (min is not None and d<min) or (max is not None and d>max):
				self.SetPos(savePos)
				return None
			return d			
				
	def MatchHexDigit(self):
		"""Returns true if the current character is a hex-digit"""
		return self.MatchOne("0123456789ABCDEFabcdef")

	def ParseHexDigit(self):
		"""Parses a hex-digit character.  Returns the digit, or None if no digit is found."""
		return self.ParseOne("0123456789ABCDEFabcdef")

	def ParseHexDigits(self,min,max=None):
		"""Parses min hex digits, and up to max hex digits, returning the string of hex digits.
		
		If *max* is None then there is no maximum.
		
		If min digits can't be parsed then None is returned."""
		savePos=self.pos
		result=[]
		while max is None or len(result)<max:
			d=self.ParseHexDigit()
			if d is None:
				break
			else:
				result.append(d)
		if len(result)<min:
			self.SetPos(savePos)
			return None
		return string.join(result,'')

	def MatchEnd(self):
		return self.theChar is None
	
	def RequireEnd(self,production=None):
		if self.theChar is not None:
			if production:
				tail=" after %s"%production
			else:
				tail=""
			raise ValueError("Spurious data%s, found %s"%(tail,repr(self.Peek(10))))


