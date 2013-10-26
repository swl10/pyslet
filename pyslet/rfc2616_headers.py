#! /usr/bin/env python

import string
from types import *

from pyslet.rfc2616_core import *
from pyslet.rfc2616_params import *

import pyslet.iso8601 as iso


class AcceptItem(object):

	def __init__(self,source=None):
		self.range=MediaRange()
		self.q=1.0
		self.params={}
	
	def ParseWords(self,wp):
		"""Parses this AcceptList from a :py:class:`WordParser` instance.
		
		If no valid Accept header value is found HTTPParameterError is raised."""
		wp.ParseSP()
		self.params={}
		self.range.ParseWords(wp)
		wp.ParseSP()
		if wp.ParseSeparator(';'):
			wp.ParseSP()
			qParam=wp.RequireToken("q parameter")
			if qParam.lower()!='q':
				raise HTTPParameterError("Unrecognized q-parameter: %s"%qParam)
			wp.ParseSP()
			wp.RequireSeparator('=',"q parameter")
			wp.ParseSP()
			self.q=wp.ParseQualityValue()
			if self.q is None:
				raise HTTPParameterError("Unrecognized q-value: %s"%repr(wp.cWord))
			wp.ParseParameters(self.params)
		else:
			self.q=1.0
			
	def Parse(self,source):
		"""Parses a single AcceptItem instance from a *source* string.
		
		If the source does not contain a valid accept list item HTTPParameterError is raised."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("Accept header item")

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
		"""If we have two identical ranges, ultimately we sort by the q-value
		itself."""
		if not isinstance(other,AcceptItem):
			raise TypeError
		result=cmp(self.range,other.range)
		if result==0:
			if self.q>other.q:
				return -1
			elif self.q<other.q:
				return 1
		return result

					
class AcceptList(object):

	def __init__(self,source=None):
		self.aList=[]
		if source is not None:
			self.Parse(source)
	
	def SelectType(self,mTypeList):
		"""Returns the best match from mTypeList, a list of media-types.
		
		In the event of a tie, the first item in mTypeList is returned."""
		bestMatch=None
		bestQ=0
		for mType in mTypeList:
			# calculate a match score for each input item, highest score wins
			for aItem in self.aList:
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
		
	def ParseWords(self,wp):
		"""Parses this AcceptList from a :py:class:`WordParser` instance.
		
		If no valid Accept header value is found HTTPParameterError is raised."""
		wp.ParseSP()
		while wp.cWord:
			a=AcceptItem()
			a.ParseWords(wp)
			wp.ParseSP()
			self.aList.append(a)
			if not wp.ParseSeparator(','):
				break
		# Finally we should sort the result list
		self.sort()

	def Parse(self,source):
		"""Parses this AcceptList from a *source* string.
		
		If the source does not contain a valid accept list HTTPParameterError is raised."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("Accept header")

	def sort(self):
		self.aList.sort()
		
	def __len__(self):
		return len(self.aList)
	
	def __getitem__(self,index):
		return self.aList[index]
	
	def __str__(self):
		return string.join(map(str,self.aList),', ')
		