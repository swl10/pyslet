#! /usr/bin/env python

import string
from types import *

from pyslet.rfc2616_core import *
import pyslet.iso8601 as iso


class HTTPVersion:
	"""Represents the HTTP Version."""
	
	def __init__(self,source=None):
		self.major=1	#: major protocol version
		self.minor=1	#: minor protocol version
		if source is not None:
			self.Parse(source)
	
	def ParseWords(self,wp):
		"""Parses the protocol version from a :py:class:`WordParser` instance.
		
		If no protocol version is found HTTPParameterError is raised."""
		wp.ParseSP()
		token=wp.RequireToken("HTTP").upper()
		if token!="HTTP":
			raise HTTPParameterError("Expected 'HTTP', found %s"%repr(token))
		wp.ParseSP()
		wp.RequireSeparator('/',"HTTP/")
		wp.ParseSP()
		token=wp.RequireToken("protocol version")
		version=token.split('.')
		if len(version)!=2 or not IsDIGITS(version[0]) or not IsDIGITS(version[1]): 
			raise HTTPParameterError("Expected version, found %s"%repr(token))
		self.major=int(version[0])
		self.minor=int(version[1])
		
	def Parse(self,source):
		"""Parses the protocol version from *source*.
		
		If the protocol version is not parsed correctly HTTPParameterError is raised."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("HTTP version")
			
	def __str__(self):
		return "HTTP/%i.%i"%(self.major,self.minor)

	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=HTTPVersion(other)
		elif not isinstance(other,HTTPVersion):
			raise TypeError
		if self.major<other.major:
			return -1
		elif self.major>other.major:
			return 1
		elif self.minor<other.minor:
			return -1
		elif self.minor>other.minor:
			return 1
		else:
			return 0
			

# TODO: Special HTTP URI class with improved comparisons

HTTP_wkday=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
"""A list of day-of-week names Mon=0, Sun=6."""
HTTP_weekday=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
"""A list of long-form day-of-week names Monday=0, Sunday=6."""

HTTP_wkdayTable={}		#: A mapping from lower-case day-of-week names to integers (Mon=0, Sun=6)
for i in xrange(len(HTTP_wkday)):
	HTTP_wkdayTable[HTTP_wkday[i].lower()]=i
for i in xrange(len(HTTP_weekday)):
	HTTP_wkdayTable[HTTP_weekday[i].lower()]=i

HTTP_month=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
"""A list of month names Jan=0, Dec=11."""
HTTP_monthTable={}		#: A mapping from lower-case month names to integers (Jan=0, Dec=11)
for i in xrange(len(HTTP_month)):
	HTTP_monthTable[HTTP_month[i].lower()]=i


class FullDate(iso.TimePoint):
	"""A sub-class of :py:class:`pyslet.iso8601.TimePoint` which adds parsing
	and formatting methods for HTTP-formatted dates.
	
		*	source is an optional string to parse the date from"""

	def __init__(self,source=None):
		iso.TimePoint.__init__(self)
		if source is not None:
			self.Parse(source)
	
	def ParseWords(self,wp):
		"""Parses a :py:class:`pyslet.iso8601.TimePoint` instance from a :py:class:`WordParser` instance.
		
		There are three supported formats as described in the specification::
	
			"Sun, 06 Nov 1994 08:49:37 GMT"
			"Sunday, 06-Nov-94 08:49:37 GMT"
			"Sun Nov  6 08:49:37 1994"
		
		The first of these is the preferred format.
		
		The function returns the number of words parsed. Fatal parsing errors raise
		HTTPParameterError."""
		century=None
		year=None	
		month=None
		day=None
		hour=None
		minute=None
		second=None
		dayOfWeek=None
		wp.ParseSP()
		token=wp.RequireToken("day-of-week").lower()
		dayOfWeek=HTTP_wkdayTable.get(token,None)
		if dayOfWeek is None:
			raise HTTPParameterError("Unrecognized day of week: %s"%token)
		wp.ParseSP()
		if wp.ParseSeparator(","):
			wp.ParseSP()
			if wp.IsToken() and IsDIGITS(wp.cWord):
				# Best format 0: "Sun, 06 Nov 1994 08:49:37 GMT" - the preferred format!				
				day=wp.RequireInteger("date")
				wp.ParseSP()
				token=wp.RequireToken("month").lower()
				month=HTTP_monthTable.get(token,None)	
				if month is None:
					raise HTTPParameterError("Unrecognized month: %s"%repr(token))
				wp.ParseSP()
				year=wp.RequireInteger("year")
				century=year/100
				year=year%100
			else:
				# Alternative 1: "Sunday, 06-Nov-94 08:49:37 GMT"
				token=wp.RequireToken("DD-MMM-YY")
				sToken=token.split('-')
				if len(sToken)!=3 or not IsDIGITS(sToken[0]) or not IsDIGITS(sToken[2]):
					raise HTTPParameterError("Expected DD-MMM-YY, found %s"%repr(token))
				day=int(sToken[0])
				year=int(sToken[2])
				month=HTTP_monthTable.get(sToken[1].lower(),None)	
				if month is None:
					raise HTTPParameterError("Unrecognized month: %s"%repr(sToken[1]))				
		else:
			# "Sun Nov  6 08:49:37 1994"
			token=wp.RequireToken("month").lower()
			month=HTTP_monthTable.get(token,None)	
			if month is None:
				raise HTTPParameterError("Unrecognized month: %s"%repr(token))
			wp.ParseSP()
			day=wp.RequireInteger("date")
		wp.ParseSP()
		hour=wp.RequireInteger("hour")
		wp.RequireSeparator(':')
		minute=wp.RequireInteger("minute")
		wp.RequireSeparator(':')
		second=wp.RequireInteger("second")
		wp.ParseSP()
		if year is None:
			year=wp.RequireInteger("year")
			century=year/100
			year=year%100
		else:
			token=wp.RequireToken("GMT").upper()
			if token!="GMT":
				raise HTTPParameterError("Unrecognized timezone: %s"%repr(token))
		if century is None:
			if year<90:
				century=20
			else:
				century=19
		self.SetCalendarTimePoint(century,year,month+1,day,hour,minute,second)
		d1,d2,d3,d4,dow=self.date.GetWeekDay()
		if dow!=dayOfWeek+1:
			raise HTTPParameterError("Day-of-week mismatch, expected %s but found %s"%(HTTP_wkday[dow-1],HTTP_wkday[dayOfWeek]))
						
	def Parse(self,source):
		"""Parses a :py:class:`pyslet.iso8601.TimePoint` instance from an HTTP
		formatted string."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("full date")
	
	def __str__(self):
		"""Formats a :py:class:`pyslet.iso8601.TimePoint` instance in the
		following format::
		
			Sun, 06 Nov 1994 08:49:37 GMT
		
		Note that this overrides the default behaviour which would be to use one
		of the iso8601 formats."""
		century,year,month,day,hour,minute,second=self.GetCalendarTimePoint()
		century,decade,dyear,week,dayOfWeek=self.date.GetWeekDay()
		return "%s, %02i %s %04i %02i:%02i:%02i GMT"%(
			HTTP_wkday[dayOfWeek-1],
			day,
			HTTP_month[month-1],
			century*100+year,
			hour,minute,second)


class TransferEncoding:
	"""Represents an HTTP transfer-encoding."""
	
	def __init__(self,source=None):
		self.token="chunked"		#: the transfer-encoding token (defaults to "chunked")
		self.parameters={}			#: declared extension parameters
		if source is not None:
			self.Parse(source)
	
	def ParseWords(self,wp):
		"""Parses the transfer-encoding from a :py:class:`WordParser` instance.
		
		If no transfer-encoding is found HTTPParameterError is raised."""
		wp.ParseSP()
		self.token=wp.RequireToken("transfer-encoding").lower()
		self.parameters={}
		if self.token!="chunked":
			wp.ParseParameters(self.parameters)
		
	def Parse(self,source):
		"""Parses the transfer-encoding from a *source* string.
		
		If the protocol version is not parsed correctly HTTPParameterError is raised."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("transfer-encoding")
	
	def __str__(self):
		return self.token+FormatParameters(self.parameters)


class MediaType:
	def __init__(self,source=None):
		self.type=self.subtype=None
		self.parameters={}
		if source is not None:
			self.Parse(source)
	
	def ParseWords(self,wp):
		"""Parses a media type from a :py:class:`WordParser` instance.
		
		Enforces the following rule from the specification:
		
			Linear white space (LWS) MUST NOT be used between the type and
			subtype, nor between an attribute and its value
		
		If the media-type is not parsed correctly HTTPParameterError is raised."""
		wp.ParseSP()
		self.type=wp.RequireToken("media-type").lower()
		wp.RequireSeparator('/',"media-type")
		self.subtype=wp.RequireToken("media-subtype").lower()
		wp.ParseSP()
		self.parameters={}
		wp.ParseParameters(self.parameters,ignoreAllSpace=False)
			
	def Parse(self,source):
		"""Parses the media-type from a *source* string.
		
		If the media-type is not parsed correctly HTTPParameterError is raised."""
		wp=WordParser(source,ignoreSpace=False)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("media-type")
	
	def __str__(self):
		return string.join([self.type,'/',self.subtype],'')+FormatParameters(self.parameters)

	def __cmp__(self,other):
		"""Media-types are compared by type, subtype and ultimately parameters."""
		if not isinstance(other,MediaType):
			other=MediaType(other)
		result=cmp(self.type,other.type)
		if result:
			return result
		result=cmp(self.subtype,other.subtype)
		if result:
			return result
		return cmp(self.parameters,other.parameters)
		

class ProductToken:
	def __init__(self,source=None):
		self.token=self.version=None
		if source:
			self.Parse(source)
			
	def ParseWords(self,wp):
		"""Parses a product token from a :py:class:`WordParser` instance."""
		self.token=self.version=None
		wp.ParseSP()
		self.token=wp.RequireToken("product token")
		wp.ParseSP()
		if wp.ParseSeparator('/'):
			self.version=wp.RequireToken("product-version")
		
	def Parse(self,source):
		"""Parses the product token from a *source* string or raises HTTPParameterError."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("product token")
	
	def __str__(self):
		if self.version:
			return self.token
		else:
			return string.join((self.token,'/',self.version),'')


class MediaRange(MediaType):

	def MatchMediaType(self,mType):
		"""Tests whether this media type matches this range."""
		if self.type=='*':
			return True
		elif self.type!=mType.type:
			return False
		if self.subtype=='*':
			return True
		elif self.subtype!=mType.subtype:
			return False
		# all the parameters in the range must be matched
		for p,v in self.parameters.items():
			if p not in mType.parameters or mType.parameters[p]!=v:
				# e.g. suppose we have a range type/subtype;paramA=1;paramB=2
				# then type/subtype;paramA=1 does not match (we needed paramB=2 as well)
				# and type/subtype;paramA=1;paramB=3 does not match either
				# but type/subtype;paramA=1;paramB=2;paramC=3 does match
				return False
		return True
				
	def ParseWords(self,wp):
		"""Parses a media range from a :py:class:`WordParser` instance.
		
		If the media-range is not parsed correctly HTTPParameterError is raised."""
		wp.ParseSP()
		self.type=wp.RequireToken("media-range").lower()
		wp.RequireSeparator('/',"media-range")
		self.subtype=wp.RequireToken("media-range-subtype").lower()
		wp.ParseSP()
		self.parameters={}
		wp.ParseParameters(self.parameters,ignoreAllSpace=False,qMode='q')
			
	def Parse(self,source):
		"""Parses the media-range from a *source* string.
		
		If the media-range is not parsed correctly HTTPParameterError is raised."""
		wp=WordParser(source)
		self.ParseWords(wp)
		wp.ParseSP()
		wp.RequireEnd("media-range")

	def __cmp__(self,other):
		"""Quoting from the specification:
		
		"Media ranges can be overridden by more specific media ranges or specific
		media types. If more than one media range applies to a given type, the
		most specific reference has precedence."

		So */* is lower than match/* which is lower than match/match which, in
		turn is lower than match/match;param=x, which is lower than
		match/match;paramA=x;paramB=y and so on.
		
		If we have two rules with identical precedence then we sort them
		alphabetically by type; sub-type and ultimately alphabetically by
		parameters"""
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
				return cmp(aType,bType)
			
class Accept(object):
	pass
		
	