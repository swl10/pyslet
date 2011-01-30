#! /usr/bin/env python
"""Utilities to aid interaction with the unicode database


"""

from sys import maxunicode
import types, string

CHINESE_TEST=u'\u82f1\u56fd'

class CharClass:
	"""Represents a class of unicode characters.
	
	A class of characters is represented internally by a list of character ranges
	that define the class.  This is efficient because most character classes are
	defined in blocks of characters."""
	
	def __init__(self,*args):
		"""Constructs a character class from a variable number of arguments.
		
		String arguments add all characters in the string to the class.  For example,
		CharClass('abcxyz') creates a class comprising two ranges: a-c and x-z.
		
		Tuple/List arguments can be used to pass pairs of characters that define
		a range.  For example, CharClass(('a','z')) creates a class comprising the
		letters a-z.
		
		Instances of CharClass can be used to add an existing class."""
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
	
	def AddClass(self,c):
		"""Adds all the characters in c to the character class (union operation)"""
		for r in c.ranges:
			self.AddRange(r[0],r[1])
			
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
		"""Test a unicode character, return True if the character is in the class"""
		if self.ranges:
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
			rtry=(rmin+rmax)/2
			if c<=self.ranges[rtry][1]:
				return self.BisectionSearch(c,rmin,rtry)
			else:
				return self.BisectionSearch(c,rtry+1,rmax)
