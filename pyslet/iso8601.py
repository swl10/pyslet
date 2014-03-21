"""ISO8601 Date and Time Module

Copyright (c) 2004, University of Cambridge.

All rights reserved.

Redistribution and use of this software in source and binary forms
(where applicable), with or without modification, are permitted
provided that the following conditions are met:

 *  Redistributions of source code must retain the above copyright
    notice, this list of conditions, and the following disclaimer.

 *  Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions, and the following
    disclaimer in the documentation and/or other materials provided with
    the distribution.
    
 *  Neither the name of the University of Cambridge, nor the names of
    any other contributors to the software, may be used to endorse or
    promote products derived from this software without specific prior
    written permission.

THIS SOFTWARE IS PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""
	
from types import *
import string, warnings
from math import modf,floor
import time as pytime

from pyslet.rfc2234 import RFC2234CoreParser, IsDIGIT

class DateTimeError(Exception): pass

class TimeZoneSyntaxError(DateTimeError):
	def __init__ (self,zoneStr):
		self.zoneStr=zoneStr
	
	def __repr__ (self):
		return 'Syntax error in ISO time zone : '+self.zoneStr
	
MONTH_SIZES=(31,28,31,30,31,30,31,31,30,31,30,31)
MONTH_SIZES_LEAPYEAR=(31,29,31,30,31,30,31,31,30,31,30,31)
MONTH_OFFSETS=(0,31,59,90,120,151,181,212,243,273,304,334)

def LeapYear(year):
	"""LeapYear returns True if *year* is a leap year and False otherwise.
	
	Note that leap years famously fall on all years that divide by 4
	except those that divide by 100 but including those that divide
	by 400."""
	if year%4:			# doesn't divide by 4
		return False
	elif year%100:		# doesn't divide by 100
		return True
	elif year%400:		# doesn't divide by 400
		return False
	else:
		return True

def DayOfWeek(year,month,day):
	"""DayOfWeek returns the day of week 1-7, 1 being Monday for the given year, month
	and day"""
	num=year*365
	num=num+year//4+1
	num=num-(year//100+1)
	num=num+year//400+1
	if month<3 and LeapYear(year):
		num=num-1
	return (num+MONTH_OFFSETS[month-1]+day+4)%7+1

def WeekCount(year):
	"""Week count returns the number of calendar weeks in a year.  Most years have 52
	weeks of course, but if the year begins on a Thursday or a leap year begins on a
	Wednesday then it has 53."""
	weekday=DayOfWeek(year,1,1)
	if weekday==4:
		return 53
	elif weekday==3 and LeapYear(year):
		return 53
	else:
		return 52

def GetLocalZone():
	# returns the number of minutes ahead of UTC we are
	t=pytime.time()
	utcTuple=pytime.gmtime(t)
	utcDate=Date.FromStructTime(utcTuple)
	utcTime=Time.FromStructTime(utcTuple)
	localTuple=pytime.localtime(t)
	localDate=Date.FromStructTime(localTuple)
	localTime=Time.FromStructTime(localTuple)
	# Crude but effective, calculate the zone in force by comaring utc and local time
	if localDate==utcDate:
		zOffset=0
	elif localDate<utcDate:
		zOffset=-1440
	else:
		zOffset=1440
	zOffset+=int(localTime.GetTotalSeconds()-utcTime.GetTotalSeconds())//60
	return zOffset


class Truncation(object):
	"""Defines constants to use when formatting to truncated forms."""
	No=0		#: constant for no truncation
	Century=1	#: constant for truncating to century
	Decade=2	#: constant for truncating to decade
	Year=3		#: constant for truncating to year
	Month=4		#: constant for truncating to month
	Week=5		#: constant for truncating to week
	Hour=6		#: constant for truncating to hour
	Minute=7	#: constant for truncating to minute

NoTruncation=Truncation.No	#: a synonym for Truncation.No 


class Precision(object):
	"""Defines constants for representing reduced precision."""	
	Century=1	#: constant for century precision
	Year=2		#: constant for year precision
	Month=3		#: constant for month precision
	Week=4		#: constant for week precision
	Hour=5		#: constant for hour precision
	Minute=6	#: constant for minute precision
	Complete=7	#: constant for complete representations
	

class Date(object):
	"""A class for representing ISO dates.
	
	Values can be represent dates with reduced precision, for
	example::

		Date(century=20,year=13,month=12)
		
	represents December 2013, no specific day.
		
	There are a number of different forms of the constructor based on
	named parameters, the simplest is::
	
		Date(century=19,year=69,month=7,day=20)
	
	You can also use weekday format (note that decade must be provided
	separately)::
	
		Date(century=19,decade=6,year=9,week=29,weekday=7) 
	
	Ordinal format (where day 1 is 1st Jan)::

		Date(century=19,year=69,ordinalDay=201) 
	
	Absolute format (where day 1 is the notional 1st Jan 0001)::
	
		Date(absoluteDay=718998)

	An empty constructor is equivalent to::
	
		Date()==Date(absoluteDay=1)
				
	All constructors except the absolute form allow the passing of a
	*base* date which allows the most-significant values to be omitted,
	for example::
	
		base=Date(century=19,year=69,month=7,day=20)
		newDate=Date(day=21,base=base)	#: 21st July 1969
	
	Note that *base* always represents a date *before* the newly constructed date,
	so::
	 	
		base=Date(century=19,year=99,month=12,day=31)
		newDate=Date(day=5,base=base)
	
	constructs a Date representing the 5th January 2000"""
	def __init__(self,src=None,base=None,century=None,decade=None,year=None,month=None,day=None,week=None,weekday=None,ordinalDay=None,absoluteDay=None):
		if src is None:
			# explicit form
			if absoluteDay:
				self._SetFromAbsoluteDay(absoluteDay)
			elif decade or week or weekday:
				self._SetFromWeekDay(century,decade,year,week,weekday,base)
			elif ordinalDay:
				self._SetFromOrdinalDay(century,year,ordinalDay,base)
			elif century is None and base is None:
				# use the origin, but everything else must be None too
				if year is not None or month is not None or day is not None:
					raise DateTimeError("truncated date with no base")
				self.century=0		#: the century, 0..99
				self.year=1			#: the year, 0..99
				self.month=1		#: the month, 1..12 (for dates stored in calendar form) 
				self.week=None		#: the week (for dates stored in week form)
				self.day=1			#: the day, 1..31 (or 1..7 when :py:attr:`week` is not None)
			else:
				self._SetFromCalendarDay(century,year,month,day,base)
			self._CheckDate()
		elif isinstance(src,Date):
			self.century=src.century
			self.year=src.year
			self.month=src.month
			self.week=src.week
			self.day=src.day
		else:
			raise TypeError("Can't construct Date from %s"%repr(src))

	def _SetFromAbsoluteDay(self,absDay):
		quadCentury=146097	# 365*400+97 always holds
		century=36524		# 365*100+24 excludes centennial leap
		quadYear=1461		# 365*4+1    includes leap
		# Shift the base so that day 0 is 1st Jan 0001, makes the year calculation easier
		absDay=absDay-1
		# All quad centuries are equal
		absYear=400*(absDay//quadCentury)
		absDay=absDay%quadCentury
		# A quad century has one more day than 4 centuries because it ends in a leap year
		# We must check for this case specially to stop abother 4 complete centuries being added!
		if absDay==(quadCentury-1):
			absYear=absYear+399
			absDay=365
		else:
			absYear=absYear+100*(absDay//century)
			absDay=absDay%century
			# A century has one fewer days than 25 quad years so we are safe this time
			absYear=absYear+4*(absDay//quadYear)
			absDay=absDay%quadYear
			# However, a quad year has 1 more day than 4 years so we have a second special case
			if absDay==(quadYear-1):
				absYear=absYear+3
				absDay=365
			else:
				absYear=absYear+(absDay//365)
				absDay=absDay%365
		absYear=absYear+1
		# Finally, restore the base so that 1 is the 1st of Jan for setting the ordinal
		self._SetFromOrdinalDay(absYear//100,absYear%100,absDay+1)

	def GetAbsoluteDay (self):
		"""Return a notional day number - with 1 being the 0001-01-01 which is the base day of our calendar."""
		if not self.Complete():
			raise DateTimeError("absolute day requires complete date")
		absYear=self.century*100+self.year-1
		return (absYear//4)-(absYear//100)+(absYear//400)+(absYear*365)+self.GetOrdinalDay()[2]
	
	def _SetFromCalendarDay(self,century,year,month,day,base=None):
		self.week=None
		if century is None:
			# Truncation level>=1
			if base is None or not base.Complete():
				raise DateTimeError("truncated date with no base")
			else:
				baseCentury,baseYear,baseMonth,baseDay=base.GetCalendarDay()
				# adjust base precision
				if day is None:
					baseDay=None
					if month is None:
						baseMonth=None
			self.century=baseCentury
			if year is None:
				# Truncation level>=2
				self.year=baseYear
				if month is None:
					# Truncation level>=3
					self.month=baseMonth
					if day is None:
						raise ValueError
					else:
						self.day=day
						if self.day<baseDay:
							self._AddMonth()
				else:
					self.month=month
					self.day=day
					if self.month<baseMonth or (self.month==baseMonth and self.day<baseDay):
						self._AddYear()
			else:
				self.year=year
				self.month=month
				self.day=day
				if self.year<baseYear or (self.year==baseYear and
					(self.month<baseMonth or (self.month==baseMonth and self.day<baseDay))):
					self._AddCentury()
		else:
			self.century=century
			self.year=year
			self.month=month
			self.day=day
		
	def _AddCentury(self):
		if self.century>=99:
			raise ValueError				
		self.century+=1

	def _AddYear(self):
		if self.year>=99:
			self.year=0
			self._AddCentury()
		else:
			self.year+=1
	
	def _AddMonth(self):
		if self.month>=12:
			self.month=1
			self._AddYear()
		else:
			self.month+=1

	def GetCalendarDay(self):
		"""Returns a tuple of: (century,year,month,day)"""			
		return (self.century,self.year,self.month,self.day)
	
	def _SetFromOrdinalDay(self,century,year,ordinalDay,base=None):
		if ordinalDay is None:
			self._SetFromCalendarDay(century,year,None,None,base)
		else:
			self.week=None
			if century is None:
				if base is None or not base.Complete():
					raise DateTimeError("truncated date with no base")
				else:
					baseCentury,baseYear,baseOrdinalDay=base.GetOrdinalDay()
				self.century=baseCentury
				if year is None:
					# Truncation level==2
					self.year=baseYear
					if ordinalDay is None:
						raise ValueError
					else:
						self.day=ordinalDay
						if self.day<baseOrdinalDay:
							self._AddYear()
				else:
					self.year=year
					self.day=ordinalDay
					if self.year<baseYear or (self.year==baseYear and self.day<baseOrdinalDay):
						self._AddCentury()
			else:
				self.century=century
				self.year=year
				self.day=ordinalDay
			if self.LeapYear():
				mSizes=MONTH_SIZES_LEAPYEAR
			else:
				mSizes=MONTH_SIZES
			self.month=1
			for m in mSizes:
				if self.day>m:
					self.day=self.day-m
					self.month=self.month+1
				else:
					break

	def GetOrdinalDay(self):
		"""Returns a tuple of (century,year,ordinalDay)"""
		if self.day is None:
			if self.month is None and self.week is None:
				return (self.century,self.year,None)
			else:
				raise DateTimeError("can't get ordinal day with month or week precision")
		if self.LeapYear():
			mSizes=MONTH_SIZES_LEAPYEAR
		else:
			mSizes=MONTH_SIZES
		ordinalDay=self.day
		for m in mSizes[:self.month-1]:
			ordinalDay=ordinalDay+m
		return (self.century,self.year,ordinalDay)

	def _SetFromWeekDay (self,century,decade,year,week,weekday,base=None):
		if weekday is None:
			if week is None:
				raise DateTimeError("can't set date with year precision or less using week format")
		else:
			if weekday<=0 or weekday>7:
				raise DateTimeError("weekday %i out of range"%weekday)
		if week is not None and (week<0 or week>53):
			raise DateTimeError("week %i out of range"%week)
		if year is not None and (year<0 or year>9):
			raise DateTimeError("year %i within decade is out of range")
		if decade is not None and (decade<0 or decade>9):
			raise DateTimeError("decade %i is out of range")
		self.month=None
		if century is None:
			# Truncation
			if base is None or not base.Complete():
				raise DateTimeError("truncated date with no base")
			else:
				baseCentury,baseDecade,baseYear,baseWeek,baseWeekday=base.GetWeekDay()
				# adjust base precision
				if weekday is None:
					baseWeekday=None
			self.century=baseCentury
			if decade is None:
				if year is None:
					self.year=baseDecade*10+baseYear
					if week is None:
						self.week=baseWeek
						if weekday is None:
							raise ValueError
						else:
							self.day=weekday
							if self.day<baseWeekday:
								self._AddWeek()
					else:
						self.week=week
						self.day=weekday
						if self.week<baseWeek or (self.week==baseWeek and self.day<baseWeekday):
							self._AddYear()
				else:
					self.year=year
					self.week=week
					self.day=weekday
					if self.year<baseYear or (self.year==baseYear and (
						self.week<baseWeek or (self.week==baseWeek and self.day<baseWeekday))):
						self.year+=(baseDecade+1)*10
					else:
						self.year+=baseDecade*10
			else:
				self.year=decade*10+year
				self.week=week
				self.day=weekday
				baseYear+=baseDecade*10
				if self.year<baseYear or (self.year==baseYear and (
					self.week<baseWeek or (self.week==baseWeek and self.day<baseWeekday))):
					self._AddCentury()
		else:
			self.century=century
			self.year=decade*10+year
			self.week=week
			self.day=weekday
		if self.day is not None:
			# We must convert to calendar form
			year=self.century*100+self.year
			if self.week>WeekCount(year):
				raise DateTimeError("bad week %i for year %i"%(self.week,year))	
			self.day=4-DayOfWeek(year,1,4)+(self.week-1)*7+self.day
			if self.day<1:
				year-=1
				leap=LeapYear(year)
				if leap:
					self.day+=366
				else:
					self.day+=365
			else:
				leap=LeapYear(year)
				if leap:
					yearLength=366
				else:
					yearLength=365
				if self.day>yearLength:
					year+=1
					self.day-=yearLength
					leap=LeapYear(year)
			if leap:
				mSizes=MONTH_SIZES_LEAPYEAR
			else:
				mSizes=MONTH_SIZES
			self.month=1
			for m in mSizes:
				if self.day>m:
					self.day=self.day-m
					self.month=self.month+1
				else:
					break
			self.century=year//100
			self.year=year%100
			self.week=None
				
	def _AddWeek(self):
		if self.week>=WeekCount(self.century*100+self.year):
			self.week=1
			self._AddYear()
		else:
			self.week+=1

	def GetWeekDay(self):
		"""Returns a tuple of (century,decade,year,week,weekday), note
		that Monday is 1 and Sunday is 7"""
		if self.day is None:
			if self.week:
				return (self.century,self.year//10,self.year%10,self.week,None)
			elif self.month is None:
				if self.year is None:
					return (self.century,None,None,None,None)
				else:
					return (self.century,self.year//10,self.year%10,None,None)
			else:
				raise DateTimeError("can't get week day with month precision")
		else:
			century,year,ordinalDay=self.GetOrdinalDay()
			year+=century*100
			if LeapYear(year):
				yearLength=366
			else:
				yearLength=365
			weekday=DayOfWeek(year,self.month,self.day)
			thursday=ordinalDay+4-weekday
			if thursday<1:
				# Thursday this week was actually last year, and so we are
				# part of the last calendar week of last year too.
				# may return year==0
				year-=1
				week=WeekCount(year)
			elif thursday>yearLength:
				# Thursday this week is actually next year, and so we are
				# part of the first calendar week of next year too.
				# may return century=100
				year+=1
				week=1
			else:
				# We are part of this year, but which week?  Jan 4th is always
				# part of the first week of the year, so we calculate the ordinal
				# value of the Monay that began that week 
				yearBase=5-DayOfWeek(year,1,4)
				week=(ordinalDay-yearBase)//7+1
			return year//100,(year%100)//10,(year%10),week,weekday

	@classmethod
	def FromStructTime(cls,t):
		"""Constructs a :py:class:`Date` from a struct_time, such as
		might be returned from time.gmtime() and related functions."""
		return cls(century=t[0]//100,year=t[0]%100,month=t[1],day=t[2])
	
	def UpdateStructTime(self,t):
		"""UpdateStructTime changes the year, month, date, wday and ydat
		fields of t, a struct_time, to match the values in this date."""
		if not self.Complete():
			raise DateTimeError("UpdateStructTime requires complete date")
		t[0]=self.century*100+self.year
		t[1]=self.month
		t[2]=self.day
		t[6]=self.GetWeekDay()[4]-1
		t[7]=self.GetOrdinalDay()[2]
		
	@classmethod
	def FromNow(cls):
		"""Constructs a :py:class:`Date` from the current local time."""
		return cls.FromStructTime(pytime.localtime(pytime.time()))
					
	def Offset(self,centuries=0,years=0,months=0,weeks=0,days=0):
		"""Constructs a :py:class:`Date` from the current date + a given offset"""
		d=self
		if days or weeks:
			baseDay=self.GetAbsoluteDay()
			baseDay+=days+7*weeks
			d=type(self)(absoluteDay=baseDay)
		if months or years or centuries:
			day=self.day
			month=d.month+months
			if month>12:
				years+=(month-1)//12
				month=(month-1)%12+1
			year=d.year+years
			if year>99:
				centuries+=year//100
				year=year%100
			century=d.century+centuries
			return type(self)(century=century,year=year,month=month,day=day)
		else:
			return d

	@classmethod
	def FromString(cls,src,base=None):
		"""Parses a :py:class:`Date` instance from a *src* string."""
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			d,dFormat=p.ParseDateFormat(base)
		else:
			raise TypeError
		return d

	@classmethod
	def FromStringFormat(cls,src,base=None):
		"""Similar to :py:meth:`FromString` except that a tuple is
		returned, the first item is the resulting :py:class:`Date`
		instance, the second is a string describing the format parsed.
		For example::
		
			d,f=Date.FromStringFormat("1969-07-20")
			# f is set to "YYYY-MM-DD".	"""
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			return p.ParseDateFormat(base)
		else:
			raise TypeError

	def __str__(self):
		"""Formats the date to a string using the default, extended, calendar format."""
		return str(self.GetCalendarString())

	def __unicode__(self):
		"""Formats the date to a unicode string using the default, extended, calendar format."""
		return unicode(self.GetCalendarString())
	
	def __repr__(self):
		if self.week is None:
			return "Date(century=%s,year=%s,month=%s,day=%s)"%(str(self.century),str(self.year),str(self.month),str(self.day))
		else:
			return "Date(century=%s,decade=%s,year=%s,week=%s,weekday=%s)"%(str(self.century),str(self.year//10),str(self.year%10),str(self.week),str(self.day))
			
	def GetCalendarString(self,basic=False,truncation=NoTruncation):
		"""Formats this date using calendar form, for example 1969-07-20
		
			*basic*
				True/False, selects basic form, e.g., 19690720.  Default
				is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the date.  For example, if you
				specify :py:attr:`Truncation.Year` you'll get --07-20 or
				--0720.  Default is :py:attr:`NoTruncation`.
			
		Note that Calendar format only supports Century, Year and Month
		truncated forms."""
		if self.day is None:
			if self.month is None:
				if self.week:
					raise DateTimeError("can't get calendar string with week precision")
				if self.year is None:
					if self.century is None:
						raise DateTimeError("no date to format")
					else:
						if truncation==NoTruncation:
							return "%02i"%self.century
						else:
							raise ValueError
				else:
					if truncation==NoTruncation:
						return "%02i%02i"%(self.century,self.year)
					elif truncation==Truncation.Century:
						return "-%02i"%self.year
					else:
						raise ValueError
			else:
				if truncation==NoTruncation:
					return "%02i%02i-%02i"%(self.century,self.year,self.month)
				elif truncation==Truncation.Century:
					if basic:
						return "-%02i%02i"%(self.year,self.month)
					else:
						return "-%02i-%02i"%(self.year,self.month)
				elif truncation==Truncation.Year:
					return "--%02i"%self.month
				else:
					raise ValueError
		else:
			if truncation==NoTruncation:
				if basic:
					return "%02i%02i%02i%02i"%(self.century,self.year,self.month,self.day)
				else:
					return "%02i%02i-%02i-%02i"%(self.century,self.year,self.month,self.day)
			elif truncation==Truncation.Century:
				if basic:
					return "%02i%02i%02i"%(self.year,self.month,self.day)
				else:
					return "%02i-%02i-%02i"%(self.year,self.month,self.day)
			elif truncation==Truncation.Year:
				if basic:
					return "--%02i%02i"%(self.month,self.day)
				else:
					return "--%02i-%02i"%(self.month,self.day)
			elif truncation==Truncation.Month:
				return "---%02i"%self.day
			else:
				raise ValueError
	
	def GetOrdinalString(self,basic=False,truncation=NoTruncation):
		"""Formats this date using ordinal form, for example 1969-201
		
			*basic*
				True/False, selects basic form, e.g., 1969201.  Default
				is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the date.  For example, if you
				specify :py:attr:`Truncation.Year` you'll get -201. 
				Default is :py:attr:`NoTruncation`.
		
		Note that ordinal format only supports century and year
		truncated forms."""
		century,year,ordinalDay=self.GetOrdinalDay()
		if ordinalDay is None:
			# same as for calendar strings
			return self.GetCalendarString(basic,truncation)
		else:
			if truncation==NoTruncation:
				if basic:
					return "%02i%02i%03i"%(century,year,ordinalDay)
				else:
					return "%02i%02i-%03i"%(century,year,ordinalDay)
			elif truncation==Truncation.Century:
				if basic:
					return "%02i%03i"%(year,ordinalDay)
				else:
					return "%02i-%03i"%(year,ordinalDay)
			elif truncation==Truncation.Year:
				return "-%03i"%ordinalDay
			else:
				raise ValueError
											
	def GetWeekString(self,basic=False,truncation=NoTruncation):
		"""Formats this date using week form, for example 1969-W29-7
		
			*basic*
				True/False, selects basic form, e.g., 1969W297.  Default
				is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the date.  For example, if you
				specify :py:attr:`Truncation.Year` you'll get -W297. 
				Default is :py:attr:`NoTruncation`.
		
		Note that week format only supports century, decade, year and
		week truncated forms."""
		century,decade,year,week,day=self.GetWeekDay()
		if day is None:
			if week is None:
				# same as the calendar string
				return self.GetCalendarString(basic,truncation)
			else:
				if truncation==NoTruncation:
					if basic:
						return "%02i%i%iW%02i"%(century,decade,year,week)
					else:
						return "%02i%i%i-W%02i"%(century,decade,year,week)
				elif truncation==Truncation.Century:
					if basic:
						return "%i%iW%02i"%(decade,year,week)
					else:
						return "%i%i-W%02i"%(decade,year,week)
				elif truncation==Truncation.Decade:
					if basic:
						return "-%iW%02i"%(year,week)
					else:
						return "-%i-W%02i"%(year,week)
				elif truncation==Truncation.Year:
					return "-W%02i"%week
				else:
					raise ValueError							
		else:
			if truncation==NoTruncation:
				if basic:
					return "%02i%i%iW%02i%i"%(century,decade,year,week,day)
				else:
					return "%02i%i%i-W%02i-%i"%(century,decade,year,week,day)
			elif truncation==Truncation.Century:
				if basic:
					return "%i%iW%02i%i"%(decade,year,week,day)
				else:
					return "%i%i-W%02i-%i"%(decade,year,week,day)
			elif truncation==Truncation.Decade:
				if basic:
					return "-%iW%02i%i"%(year,week,day)
				else:
					return "-%i-W%02i-%i"%(year,week,day)	
			elif truncation==Truncation.Year:
				if basic:
					return "-W%02i%i"%(week,day)
				else:
					return "-W%02i-%i"%(week,day)	
			elif truncation==Truncation.Week:
				return "-W-%i"%day
			else:
				raise ValueError

	@classmethod	
	def FromJulian(cls,year,month,day):
		"""Constructs a :py:class:`Date` from a year, month and day
		expressed in the Julian calendar."""
		if year%4:
			mSizes=MONTH_SIZES
		else:
			mSizes=MONTH_SIZES_LEAPYEAR
		year-=1	
		for m in mSizes[:month-1]:
			day+=m
		return cls(absoluteDay=(year//4)+(year*365)+day-2)

	def GetJulianDay(self):
		"""Returns a tuple of: (year,month,day) representing the
		equivalent date in the Julian calendar."""
		quadYear=1461		# 365*4+1    includes leap
		# Returns tuple of (year,month,day)
		day=self.GetAbsoluteDay()
		# 1st Jan 0001 Gregorian -> 3rd Jan 0001 Julian
		# We would add 2 but we want to shift the base so that day 0 is 1st Jan 0001 (Julian)
		# We add the second bit after the calculation is done
		day+=1
		year=4*(day//quadYear)
		day=day%quadYear
		# A quad year has 1 more day than 4 years
		if day==(quadYear-1):
			year+=3
			day=365
		else:
			year+=day//365
			day=day%365
		# correct for base year being 1...
		year+=1
		# and base day being 1st
		day+=1
		if year%4:
			mSizes=MONTH_SIZES
		else:
			mSizes=MONTH_SIZES_LEAPYEAR
		month=1
		for m in mSizes:
			if day>m:
				day-=m
				month+=1
			else:
				break
		return (year,month,day)

	def _CheckDate(self):
		if self.century is None:
			raise DateTimeError("missing date")
		if self.century<0 or self.century>99:
			raise DateTimeError("century out of range %i"%self.century)
		if self.year is None:
			return
		if self.year<0 or self.year>99:
			raise DateTimeError("year out of range %i"%self.year)
		if self.year==0 and self.century==0:
			raise DateTimeError("illegal year 0000")
		year=self.century*100+self.year
		if self.week:
			# week form of date:
			if self.week<1 or self.week>WeekCount(year):
				raise DateTimeError("illegal week %i in year %i"%(self.week,year))
			if self.month is not None:
				raise DateTimeError("mixed week/calendar forms")
		else:
			if self.month is None:
				return
			if self.month<1 or self.month>12:
				raise DateTimeError("illegal month %i"%self.month)
			if self.day is None:
				return
			if LeapYear(year):
				monthSizes=MONTH_SIZES_LEAPYEAR
			else:
				monthSizes=MONTH_SIZES
			if self.day<1 or self.day>monthSizes[self.month-1]:
				raise DateTimeError("illegal day %i for month %i"%(self.day,self.month))

	def LeapYear(self):
		"""LeapYear returns True if this date is (in) a leap year and
		False otherwise.
		
		Note that leap years fall on all years that divide by 4 except
		those that divide by 100 but including those that divide by
		400."""
		if self.year is None:
			raise DateTimeError("Insufficient precision for leap year calculation")
		if self.year%4:			# doesn't divide by 4
			return False
		elif self.year:			# doesn't divide by 100
			return True
		elif self.century%4:	# doesn't divide by 400
			return False
		else:
			return True
	
	def Complete (self):
		"""Returns True if this date has a complete representation,
		i.e., does not use one of the reduced precision forms."""
		return self.century is not None and self.day is not None

	def GetPrecision (self):
		"""Returns one of the :py:class:`Precision` constants
		representing the precision of this date."""
		if self.day is None:
			if self.month is None:
				if self.year is None:
					if self.century is None:
						return None
					else:
						return Precision.Century
				elif self.week is None:
					return Precision.Year
				else:
					return Precision.Week
			else:
				return Precision.Month
		else:
			return Precision.Complete
	
	def __hash__(self):
		"""Date objects are immutable and so can be used as the keys in
		dictionaries provided they all share the same precision.  See
		note in :py:meth:`__cmp__` below for details.
		
		Some older functions did allow modification but these have been
		deprecated.  Use python -Wd to force warnings from these unsafe
		methods."""
		return hash((self.century,self.year,self.month,self.week,self.day))
		
	def __cmp__(self,other):
		"""Date can hold imprecise dates, which raises the problem of
		comparisons between things such as January 1985 and Week 3 1985.
		 Although at first sight it may be tempting to declare 1st April
		to be greater than March, it is harder to determine the
		relationship between 1st April and April itself.  Especially if
		a complete ordering is required.
		
		The approach taken here is to disallow comparisons between dates
		with different precions."""
		if not isinstance(other,Date):
			raise TypeError
		if self.GetPrecision()!=other.GetPrecision():
			raise ValueError("Incompatible precision for comparison: "+str(other))
		result=cmp(self.century,other.century)
		if not result:
			result=cmp(self.year,other.year)
			if not result:
				if self.month is not None:
					result=cmp(self.month,other.month)
					if not result:
						result=cmp(self.day,other.day)
				elif self.week is not None:
					result=cmp(self.week,other.week)
		return result
												
	def SetFromDate (self,src):
		warnings.warn("Date.SetFromDate is deprecated, use Date(src) instead", DeprecationWarning, stacklevel=2)		
		self.century=src.century
		self.year=src.year
		self.month=src.month
		self.week=src.week
		self.day=src.day
		
	def SetOrigin(self):
		warnings.warn("Date.SetOrigin is deprecated, use Date.Origin() instead", DeprecationWarning, stacklevel=2)		
		self.century=0
		self.year=self.month=self.day=1
		self.week=None

	def SetAbsoluteDay (self,absDay):
		warnings.warn("Date.SetAbsoluteDay is deprecated, use Date(absoluteDay=###) instead", DeprecationWarning, stacklevel=2)
		self._SetFromAbsoluteDay(absDay)
		self._CheckDate()

	def SetCalendarDay(self,century,year,month,day,base=None):
		warnings.warn("Date.SetCalendarDay is deprecated, use Date(century=##,year=##,...etc ) instead", DeprecationWarning, stacklevel=2)
		self._SetFromCalendarDay(century,year,month,day,base)
		self._CheckDate()
	
	def SetOrdinalDay(self,century,year,ordinalDay,base=None):
		warnings.warn("Date.SetOrdinalDay is deprecated, use Date(century=##,year=##,ordinalDay=##,...etc ) instead", DeprecationWarning, stacklevel=2)
		self._SetFromOrdinalDay(century,year,ordinalDay,base)
		self._CheckDate()

	def SetWeekDay (self,century,decade,year,week,weekday,base=None):
		warnings.warn("Date.SetWeekDay is deprecated, use Date(century=##,decade=##,year=##,week=##,...etc ) instead", DeprecationWarning, stacklevel=2)
		self._SetFromWeekDay(century,decade,year,week,weekday,base)
		self._CheckDate()
		
	def SetTimeTuple (self,t):
		warnings.warn("Date.SetTimeTuple is deprecated, use Date.FromStructTime(t) instead", DeprecationWarning, stacklevel=2)
		self._SetFromCalendarDay(t[0]//100,t[0]%100,t[1],t[2])
		self._CheckDate()

	def GetTimeTuple (self,t):
		warnings.warn("Date.GetTimeTuple is deprecated, use Date.UpdateStructTime(t) instead", DeprecationWarning, stacklevel=2)
		self.UpdateStructTime(t)
	
	def SetFromString(self,dateStr,base=None):
		warnings.warn("Date.SetFromString is deprecated, use Date.FromString(<string>[, base]) instead", DeprecationWarning, stacklevel=2)		
		if type(dateStr) in StringTypes:
			p=ISO8601Parser(dateStr)
			d,f=p.ParseDateFormat(base)
			self.SetFromDate(d)
			return f
		else:
			raise TypeError

	def Now (self):
		warnings.warn("Date.Now is deprecated, use Date.FromNow() instead", DeprecationWarning, stacklevel=2)
		t=pytime.localtime(pytime.time())
		self._SetFromCalendarDay(t[0]//100,t[0]%100,t[1],t[2])
		self._CheckDate()
					
	def SetJulianDay(self,year,month,day):
		warnings.warn("Date.SetJulianDay is deprecated, use Date.FromJulian() instead", DeprecationWarning, stacklevel=2)
		if year%4:
			mSizes=MONTH_SIZES
		else:
			mSizes=MONTH_SIZES_LEAPYEAR
		year-=1	
		for m in mSizes[:month-1]:
			day+=m
		self._SetFromAbsoluteDay((year//4)+(year*365)+day-2)

	def AddCentury(self):
		warnings.warn("Date.AddCentury is deprecated, use Offset(centuries=1) instead", DeprecationWarning, stacklevel=2)
		self._AddCentury()

	def AddYear(self):
		warnings.warn("Date.AddYear is deprecated, use Offset(base,years=1) instead", DeprecationWarning, stacklevel=2)
		self._AddYear()
	
	def AddMonth(self):
		warnings.warn("Date.AddMonth is deprecated, use Offset(base,months=1) instead", DeprecationWarning, stacklevel=2)
		self._AddMonth()
	
	def AddWeek(self):
		warnings.warn("Date.AddWeek is deprecated, use Date.Offset(base,weeks=1) instead", DeprecationWarning, stacklevel=2)
		self._AddWeek()
			
	def AddDays (self,days):
		warnings.warn("Date.AddDays is deprecated, use Offset(base,days=##) instead", DeprecationWarning, stacklevel=2)
		if days:
			self._SetFromAbsoluteDay(self.GetAbsoluteDay()+days)


			

class Time(object):
	"""A class for representing ISO times
	
	Values can be represent times with reduced precision, for
	example::

		Time(hour=20)
		
	represents 8pm without a specific minute/seconds value.
		
	There are a number of different forms of the constructor based on
	named parameters, the simplest is::
	
		Time(hour=20,minute=17,second=40)
	
	To indicate UTC (Zulu time) by providing a zone direction of 0::
	
		Time(hour=20,minute=17,second=40,zDirection=0)
	
	To indicate a UTC offset provide additional values for hours (and
	optionally minutes)::
	
		Time(hour=15,minute=17,second=40,zDirection=-1,zHour=5,zMinute=0)
	
	A UTC offset of 0 hours and minutes results in a value that compares
	as equal to the corresponding Zulu time but is formatted using an
	explicit offset by str() or unicode() rather than using the
	canonical "Z" form.

	You may also specify a total number of seconds past midnight (no zone):
	
		Time(totalSeconds=73060)
	
	If totalSeconds overflows an error is raised.  To create a time from
	an arbitrary number of seconds and catch overflow use Offset instead::
	
		Time(totalSeconds=159460)
		# raises DateTimeError
		
		t,overflow=Time().Offset(seconds=159460)
		# sets t to 20:40:17 and overflow=1
	
	Time supports two representations of midnight: 00:00:00 and 24:00:00
	in keeping with the ISO specification.  These are considered
	equivalent by comparisons!
			
	Truncated forms can be created directly from the base time, see
	:py:meth:`Extend` for more information."""
	def __init__(self,src=None,hour=None,minute=None,second=None,totalSeconds=None,zDirection=None,zHour=None,zMinute=None):
		if src is None:
			# explicit form
			if totalSeconds is not None:
				if zDirection is not None:
					raise DateTimeError("Zone not allowed with Time's totalSeconds constructor")
				self._SetFromTotalSeconds(totalSeconds)
			elif hour is None and minute is None and second is None:
				# use the origin
				self.hour=0				#: the hour, 0..24
				self.minute=0			#: the minute, 0..59
				self.second=0			#: the seconds, 0..60 (to include leap seconds)
				self.zDirection=None	#: an integer with the sign of the zone offset or None
				self.zOffset=None		#: the difference in minutes to UTC
			else:
				self._SetFromValues(hour,minute,second,zDirection,zHour,zMinute)
				self._CheckTime()
		elif isinstance(src,Time):
			self.hour=src.hour
			self.minute=src.minute
			self.second=src.second
			self.zDirection=src.zDirection
			self.zOffset=src.zOffset
		else:
			raise TypeError("Can't construct Time from %s"%repr(src))

	def _SetFromTotalSeconds(self,totalSeconds):
		t,overflow=type(self)().Offset(seconds=totalSeconds)
		if overflow:
			raise DateTimeError("Can't construct Time from totalSeconds=%i"%totalSeconds)
		self.hour=t.hour
		self.minute=t.minute
		self.second=t.second
		self.zDirection=self.zOffset=None

	def GetTotalSeconds(self):		
		"""Note that leap seconds are handled as if they were invisible,
		e.g., 23:00:60 returns the same total seconds as 23:00:59."""
		if not self.Complete():
			raise DateTimeError("GetTotalSeconds requires complete precision")
		if self.second==60:
			return 59+self.minute*60+self.hour*3600
		else:
			return self.second+self.minute*60+self.hour*3600

	def _SetFromValues(self,hour,minute,second,zDirection,zHour,zMinute):
		self.hour=hour
		self.minute=minute
		self.second=second
		self.zDirection=zDirection
		if zDirection is None:
			self.zOffset=None
		elif zDirection==0:
			self.zOffset=0
		elif zHour is None:
			raise DateTimeError("non-zero UTC offset requires at least hour zone precision")
		elif zMinute is None:
			self.zOffset=zHour*60
		else:
			self.zOffset=zHour*60+zMinute

	def GetTime(self):
		"""Returns a tuple of (hour,minute,second).

		Times with reduced precision will return None for second and or
		minute."""		
		return self.hour,self.minute,self.second

	def GetZone(self):
		"""Returns a tuple of::
		
		(zDirection,zOffset)
		
		zDirection is defined as per Time's constructor, zOffset is a
		non-negative integer minute offset or None, if the zone is
		unspecified for this Time."""
		return self.zDirection,self.zOffset

	def GetZoneOffset(self):
		"""Returns a single integer representing the zone offset (in
		minutes) or None if this time does not have a time zone
		offset."""
		if self.zDirection is None:
			return None
		else:
			return self.zDirection*self.zOffset
			
	def GetZone3(self):
		"""Returns a tuple of::
		
		(zDirection,zHour,zMinute)
		
		These values are defined as per Time's constructor.""" 
		zDirection=self.zDirection
		if zDirection is None:
			zHour=zMinute=None
		elif zDirection==0:
			zHour=zMinute=0
		else:
			zHour=self.zOffset//60
			zMinute=self.zOffset%60
		return zDirection,zHour,zMinute
		
	def GetCanonicalZone(self):
		"""Returns a tuple of::
		
		(zDirection,zHour,zMinute)
		
		These values are defined as per Time's constructor but zero
		offsets always return zDirection=0.  If present, the zone is
		always returned with complete (minute) precision."""
		zDirection=self.zDirection
		if zDirection is None:
			zHour=zMinute=None
		elif zDirection==0 or self.zOffset==0:
			zDirection=zHour=zMinute=0
		else:
			zHour=self.zOffset//60
			zMinute=self.zOffset%60
		return zDirection,zHour,zMinute

	def GetTimeAndZone(self):
		"""Returns a tuple of (hour,minute,second,zone direction,zone
		offset) as defined in GetTime and GetZone."""
		return self.hour,self.minute,self.second,self.zDirection,self.zOffset
		
	def Extend(self,hour=None,minute=None,second=None):
		"""Constructs a :py:class:`Time` instance from an existing time,
		extended a (possibly) truncated hour/minute/second value.
		
		The time zone is always copied if present.  The result is a
		tuple of (<Time instance>,overflow) where overflow 0 or 1
		indicating whether or not the time overflowed.  For example:: 

			# set base to 20:17:40Z
			base=Time(hour=20,minute=17,second=40,zDirection=0)
			t,overflow=base.Extend(minute=37)
			# t is 20:37:40Z, overflow is 0
			t,overflow=base.Extend(minute=7)
			# t is 21:07:40Z, overflow is 0
			t,overflow=base.Extend(hour=19,minute=7)
			# t is 19:07:40Z, overflow is 1"""
		if not self.Complete():
			raise DateTimeError("Can't construct truncated time from incomplete base: %s"%str(base))
		addMinute=addHour=0
		if hour is None:
			# Truncation of hour or more
			baseHour,baseMinute,baseSecond=self.GetTime()
			if second is None:
				baseSecond=None
				if minute is None:
					baseMinute=None
			newHour=baseHour
			if minute is None:
				# Truncation of minutes
				newMinute=baseMinute
				if second is None:
					raise ValueError
				else:
					newSecond=second
					if newSecond<baseSecond:
						addMinute=1
			else:
				newMinute=minute
				newSecond=second
				if newMinute<baseMinute or (newMinute==baseMinute and newSecond<baseSecond):
					addHour=1
		else:
			# no truncation
			newHour=hour
			newMinute=minute
			newSecond=second
		# always copy time zone from base
		zDirection,zHour,zMinute=self.GetZone3()
		newTime=type(self)(hour=newHour,minute=newMinute,second=newSecond,zDirection=zDirection,zHour=zHour,zMinute=zMinute)
		if addHour or addMinute:
			return newTime.Offset(hours=addHour,minutes=addMinute)
		else:
			return newTime,0
	
	def Offset(self,hours=0,minutes=0,seconds=0):
		"""Constructs a :py:class:`Time` instance from an existing time
		and an offset number of hours, minutes and or seconds.
		
		The time zone is always copied (if present).  The result is a
		tuple of (<Time instance>,overflow) where overflow is 0 or 1
		indicating whether or not the time overflowed.  For example::

			# set base to 20:17:40Z
			base=Time(hour=20,minute=17,second=40,zDirection=0)
			t,overflow=base.Offset(minutes=37)
			# t is 20:54:40Z, overflow is 0
			t,overflow=base.Offset(hours=4,minutes=37)
			# t is 00:54:40Z, overflow is 1"""
		days=0
		second=self.second
		if seconds:
			if second is None:
				raise DateTimeError("second precision required")
			second=second+seconds
			if type(second)==FloatType:
				fs,s=modf(second)
				s=int(s)
				minutes+=s//60
				second=float(s%60)+fs
			else:
				minutes+=second//60
				second=second%60
		minute=self.minute
		if minutes:
			if minute is None:
				raise DateTimeError("minute or second precision required")
			minute=minute+minutes
			if type(minute)==FloatType:
				if second is not None:
					raise DateTimeError("minute precision required")
				fm,m=modf(minute)
				m=int(m)
				hours+=minute//60
				minute=float(minute%60)+fm
			else:
				hours+=minute//60
				minute=minute%60
		hour=self.hour
		if hours:
			hour=hour+hours
			if type(hour)==FloatType:
				if minute is not None:
					raise DateTimeError("hour precision required")
				fh,h=modf(hour)
				h=int(h)
				days+=float(h//24)
				hour=float(hour%24)+fh
			else:
				days+=hour//24
				hour=hour%24
		# always copy time zone from base
		zDirection,zHour,zMinute=self.GetZone3()
		return type(self)(hour=hour,minute=minute,second=second,zDirection=zDirection,zHour=zHour,zMinute=zMinute),days

	def WithZone(self,zDirection,zHour=None,zMinute=None):
		"""Constructs a :py:class:`Time` instance from an existing time
		but with the time zone specified.  The time zone of the existing
		time is ignored.  Pass *zDirection*=None to strip the zone
		information completely."""
		return type(self)(hour=self.hour,minute=self.minute,second=self.second,zDirection=zDirection,zHour=zHour,zMinute=zMinute)
	
	def ShiftZone(self,zDirection,zHour=None,zMinute=None):
		"""Constructs a :py:class:`Time` instance from an existing time
		but shifted so that it is in the time zone specified.  The return
		value is a tuple of::
		
			(<Time instance>, overflow)
		
		overflow is one of -1, 0 or 1 indicating if the time over- or
		under-flowed as a result of the time zone shift."""
		if self.zOffset is None:
			raise DateTimeError("Can't shift time with unspecified zone: "+str(self))
		if zDirection is None or (zDirection!=0 and zHour is None):
			raise DateTimeError("Can't shift time to unspecified zone")
		# start by calculating the time shift
		newOffset=zDirection*((0 if zHour is None else zHour)*60+(0 if zMinute is None else zMinute))
		zShift=newOffset-self.GetZoneOffset()
		second=self.second
		if self.second is None:
			if self.minute is None:
				# hour precision only - the shift better be a whole number of hours
				if zShift%60:
					raise DateTimeError("Zone shift of %i minutes requires at least minute precision: "%zShift)
		# // and % may seem odd when negative shifting but this still works
		# shift of -105 minutes results in +15 minutes and -2 hours!
		minute=self.minute
		hour=self.hour
		if minute is not None:
			minute=minute+zShift%60
			if minute>59:
				hour+=1
				minute-=60
			elif minute<0:
				hour-=1
				minute+=60
		hour=hour+zShift//60
		if hour>23:
			hour-=24
			overflow=1
		elif hour<0:
			hour+=24
			overflow=-1
		else:
			overflow=0
		return type(self)(hour=hour,minute=minute,second=second,zDirection=zDirection,zHour=zHour,zMinute=zMinute),overflow

	@classmethod
	def FromStructTime(cls,t):
		"""Constructs a zone-less :py:class:`Time` from a struct_time,
		such as might be returned from time.gmtime() and related
		functions."""
		return cls(hour=t[3],minute=t[4],second=t[5])
	
	def UpdateStructTime(self,t):
		"""UpdateStructTime changes the hour, minute, second and isdst
		fields of t, a struct_time, to match the values in this time.
		
		isdst is always set to -1"""
		if not self.Complete():
			raise DateTimeError("UpdateStructTime requires a complete time")
		t[3]=self.hour
		t[4]=self.minute
		t[5]=self.second
		t[8]=-1
		
	@classmethod
	def FromNow(cls):
		"""Constructs a :py:class:`Time` from the current local time."""
		return cls.FromStructTime(pytime.localtime(pytime.time()))

	@classmethod
	def FromString(cls,src,base=None):
		"""Constructs a :py:class:`Time` instance from a string
		representation, truncated forms are returned as the earliest
		time on or after *base* and may have overflowed.  See
		:py:meth:`FromStringFormat` for more."""
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			t,overflow,f=p.ParseTimeFormat(base)
			return t
		else:
			raise TypeError

	def WithZoneString(self,zoneStr):
		"""Constructs a :py:class:`Time` instance from an existing time
		but with the time zone parsed from *zoneStr*.  The time zone of
		the existing time is ignored."""
		if type(zoneStr) in StringTypes:
			p=ISO8601Parser(zoneStr)
			zDirection,zHour,zMinute,format=p.ParseTimeZoneFormat()
			return self.WithZone(zDirection=zDireciton,zHour=zHour,zMinute=zMinute)
		else:
			raise TypeError
		
	def WithZoneStringFormat(self,zoneStr):
		"""Constructs a :py:class:`Time` instance from an existing time
		but with the time zone parsed from *zoneStr*.  The time zone of
		the existing time is ignored.

		Returns a tuple of: (<Time instance>,format)"""
		if type(zoneStr) in StringTypes:
			p=ISO8601Parser(zoneStr)
			zDirection,zHour,zMinute,format=p.ParseTimeZoneFormat()
			return self.WithZone(zDirection=zDirection,zHour=zHour,zMinute=zMinute),format
		else:
			raise TypeError
		
	@classmethod
	def FromStringFormat(cls,src,base=None):		
		"""Constructs a :py:class:`Time` instance from a string
		representation, truncated forms are returned as the earliest
		time on or after *base*.

		Returns a tuple of (<Time instance>,overflow,format) where
		overflow is 0 or 1 indicating whether or not a truncated form
		overflowed and format is a string representation of the format
		parsed, e.g., "hhmmss"."""
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			return p.ParseTimeFormat(base)
		else:
			raise TypeError

	def __str__(self):
		"""Formats the time to a string using the default, extended format."""
		return str(self.GetString())

	def __unicode__(self):
		"""Formats the time to a unicode string using the default, extended format."""
		return unicode(self.GetString())

	def __repr__(self):
		return "Time(hour=%s,minute=%s,second=%s,zDirection=%s,zHour=%s,zMinute=%s)"%((str(self.hour),str(self.minute),str(self.second))+tuple(map(str,self.GetZone3())))
				
	def GetString(self,basic=False,truncation=NoTruncation,ndp=0,zonePrecision=Precision.Complete,dp=","):
		"""Formats this time, including zone, for example 20:17:40
		
			*basic*
				True/False, selects basic form, e.g., 201740.  Default
				is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the time.  For example, if you
				specify :py:attr:`Truncation.Hour` you'll get -17:40 or
				-1740.  Default is :py:attr:`NoTruncation`.
			
			*ndp*
				Specifies the number of decimal places to display for
				the least significant component, the default is 0.
			
			*dp*
				The character to use as the decimal point, the default
				is the *comma*, as per the ISO standard.
			
			*zonePrecision*
				One of :py:attr:`Precision.Hour` or
				:py:attr:`Precision.Complete` to control the precision
				of the zone offset.
				
		Note that time formats only support Minute and Second truncated
		forms."""
		if ndp<0:
			warnings.warn("Replace negative ndp in Time.GetString with dp parameter instead", DeprecationWarning, stacklevel=2)
			ndp=-ndp
			dp="."
		if self.second is None:
			if self.minute is None:
				if self.hour is None:
					raise DateTimeError("no time to format")
				else:
					if truncation==NoTruncation:
						if type(self.hour) is FloatType:
							fraction,hour=modf(self.hour)
							hour=int(hour)
						else:
							fraction,hour=0,self.hour
						stem="%02i"%hour
					else:
						raise ValueError
			else:
				if type(self.minute) is FloatType:
					fraction,minute=modf(self.minute)
					minute=int(minute)
				else:
					fraction,minute=0,self.minute
				if truncation==NoTruncation:
					if basic:
						stem="%02i%02i"%(self.hour,minute)
					else:
						stem="%02i:%02i"%(self.hour,minute)
				elif truncation==Truncation.Hour:
					stem="-%02i"%minute
				else:
					raise ValueError
		else:
			if type(self.second) is FloatType:
				fraction,second=modf(self.second)
				second=int(second)
			else:
				fraction,second=0,self.second
			if truncation==NoTruncation:
				if basic:
					stem="%02i%02i%02i"%(self.hour,self.minute,second)
				else:
					stem="%02i:%02i:%02i"%(self.hour,self.minute,second)
			elif truncation==Truncation.Hour:
				if basic:
					stem="-%02i%02i"%(self.minute,second)
				else:
					stem="-%02i:%02i"%(self.minute,second)
			elif truncation==Truncation.Minute:
				stem="--%02i"%second
		if ndp:
			# to prevent truncation being caught out by sloppy machine rounding
			# we add a small time to the fraction (at most 1ns and typically less)
			fractionStr="%s%s%0*i"
			fraction+=2e-13
			fraction=int(floor(fraction*float(10L**ndp)))
			stem=fractionStr%(stem,dp,ndp,fraction)
		if truncation==NoTruncation:
			# untruncated forms can have a zone string
			stem+=self.GetZoneString(basic,zonePrecision)
		return stem
			
	def GetZoneString(self,basic=False,zonePrecision=Precision.Complete):
		"""Formats this time's zone, for example -05:00.
		
			*basic*
				True/False, selects basic form, e.g., -0500.  Default
				is False

			*zonePrecision*
				One of :py:attr:`Precision.Hour` or
				:py:attr:`Precision.Complete` to control the precision
				of the zone offset.
			
		Times constructed with a zDirection value of 0 are always
		rendered using "Z" for Zulu time (the name is taken from the
		phonetic alphabet).  To force use of the offset format you must
		construct the time with a non-zero value for zDirection."""
		if self.zDirection is None:
			return ""
		elif self.zDirection==0:
			return "Z"
		else:
			if self.zDirection>0:
				zStr="+"
			else:
				zStr="-"
			hour=self.zOffset//60
			minute=self.zOffset%60
			if zonePrecision==Precision.Complete or minute>0:
				if basic:
					return "%s%02i%02i"%(zStr,hour,minute)
				else:
					return "%s%02i:%02i"%(zStr,hour,minute)
			else:	
				if basic:
					return "%s%02i"%(zStr,hour)
				else:
					return "%s%02i"%(zStr,hour)

	def Complete(self):
		"""Returns True if this date has a complete representation,
		i.e., does not use one of the reduced precision forms.
		
		(Whether or not a time is complete refers only to the precision
		of the time value, it says nothing about the presence or absence
		of a time zone offset.)"""
		return self.hour is not None and self.minute is not None and self.second is not None
			
	def GetPrecision (self):
		"""Returns one of the :py:class:`Precision` constants
		representing the precision of this time."""
		if self.second is None:
			if self.minute is None:
				if self.hour is None:
					return None
				else:
					return Precision.Hour
			else:
				return Precision.Minute
		else:
			return Precision.Complete

	def WithPrecision(self,precision,truncate=False):
		"""Constructs a :py:class:`Time` instance from an existing time but
		with the precision specified by *precision*.
		
		*precision* is one of the :py:class:`Precision` constants, only
		hour, minute and complete precision are valid.
		
		*truncate* is True/False indicating whether or not the time
		value should be truncated so that all values are integers.  For
		example::
		
			t=Time(hour=20,minute=17,second=40)
			tm=t.WithPrecision(Precision.Minute,False)
			print tm.GetString(ndp=3)
			#	20:17,667
			tm=t.WithPrecision(Precision.Minute,True)
			print tm.GetString(ndp=3)
			#	20:17,000	"""
		hour=self.hour
		minute=self.minute
		second=self.second
		if precision==Precision.Complete:
			if second is None:
				if minute is None:
					if hour is None:
						raise DateTimeError("Missing time")
					elif type(hour) is FloatType:
						minute,hour=modf(hour)
						minute*=60.0
						hour=int(hour)
					else:
						minute=0
				if type(minute) is FloatType:
					second,minute=modf(minute)
					second*=60.0
					minute=int(minute)
				else:
					second=0
			if truncate and type(second) is FloatType:
				second=int(floor(second))
		elif precision==Precision.Minute:
			if second is None:
				if minute is None:
					if hour is None:
						raise DateTimeError("Missing time")
					elif type(hour) is FloatType:
						minute,hour=modf(hour)
						minute*=60.0
						hour=int(hour)
					else:
						minute=0
				if truncate and type(minute) is FloatType:
					minute=int(floor(minute))
			elif truncate:
				second=None
			else:
				minute=float(minute)+second/60.0
				second=None
		elif precision==Precision.Hour:
			if second is None:
				if minute is None:
					if hour is None:
						hour=0
					elif truncate and type(hour) is FloatType:
						hour=int(floor(hour))
				elif truncate:
					minute=None
				else:
					hour=float(hour)+minute/60.0
					minute=None
			elif truncate:
				minute=second=None
			else:
				hour=float(hour)+minute/60.0+second/3600.0
				minute=second=None
		else:
			raise ValueError
		zDirection,zHour,zMinute=self.GetZone3()
		return type(self)(hour=hour,minute=minute,second=second,zDirection=zDirection,zHour=zHour,zMinute=zMinute)		

	def _CheckTime(self):
		if self.zDirection is not None:
			if self.zDirection<-1 or self.zDirection>+1:
				raise DateTimeError("zone direction out of range %i"%self.zDirection)
			if self.zDirection!=0:
				if self.zOffset is None:
					raise DateTimeError("missing zone offset")
				elif self.zOffset>=1440:
					raise DateTimeError("zone offset out of range %i:%02i"%(self.zOffset//60,self.zOffset%60))
		if self.hour is None:
			raise DateTimeError("missing time")
		if self.hour<0 or self.hour>24:
			raise DateTimeError("hour out of range %i"%self.hour)
		if self.hour==24 and ((self.minute is not None and self.minute>0) or (self.second is not None and self.second>0)):
			raise DateTimeError("time overflow")
		if self.minute is None:
			return
		if not type(self.hour) is IntType:
			raise DateTimeError("bad fractional hour %s"%str(self.hour))
		if self.minute<0 or self.minute>59:
			raise DateTimeError("minute out of range %s"%str(self.minute))
		if self.second is None:
			return
		if not type(self.minute) is IntType:
			raise DateTimeError("bad fractional minute %s"%str(self.minute))
		if self.second<0 or self.second>=61:
			raise DateTimeError("second out of range %s"%str(self.second))
	
	def __hash__(self):
		"""Time objects are immutable and so can be used as the keys in
		dictionaries provided they all share the same precision.  See
		note in :py:meth:`__cmp__` below for details.
		
		Some older functions did allow modification but these have been
		deprecated.  Use python -Wd to force warnings from these unsafe
		methods.
		
		There is one subtlety to this implementation.  Times stored with
		a redundant +00:00 or -00:00 are treated the same as those with
		a zero direction (Zulu time)."""
		return hash((self.hour,self.minute,self.second,self.GetZoneOffset()))

	def __cmp__ (self,other):
		"""Time can hold partially specified times, we deal with
		comparisons in a similar way to Date.__cmp__ in that times must
		have the same precision to be comparable.  Although this
		behaviour is consistent it might seem strange at first as it
		rules out comparing 09:00:15 with 09:00 but, in effect, 09:00 is
		actually all times in the range 09:00:00-09:00:59.999....

		Zones further complicate this method but the rule is very
		simple, we only ever compare times from the same zone (or
		if both have unspecified zones)."""
		if not isinstance(other,Time):
			raise TypeError
		if self.GetPrecision()!=other.GetPrecision():
			raise ValueError("Incompatible precision for comparison: "+str(other))
		zDir=self.GetZoneOffset()
		otherZDir=other.GetZoneOffset()
		if zDir!=otherZDir:
			raise ValueError("Incompatible zone for comparison: "+str(other))
		result=cmp(self.hour,other.hour)
		if not result:
			result=cmp(self.minute,other.minute)
			if not result:
				result=cmp(self.second,other.second)
		return result
			
	def SetOrigin(self):
		warnings.warn("Time.SetOrigin is deprecated, use Time() instead", DeprecationWarning, stacklevel=2)		
		self._SetFromValues(0,0,0,None,None,None)
	
	def SetSeconds (self,s):
		warnings.warn("Time.SetSeconds is deprecated, use Time().Offset(seconds=s) instead", DeprecationWarning, stacklevel=2)		
		t,overflow=type(self)().Offset(seconds=s)
		self.SetFromTime(t)
		return overflow
# 		"""Set a fully-specified time based on s seconds past midnight.  If s is greater
# 		than or equal to the number of seconds in a normal day then the number of whole days
# 		represented is returned and the time is set to the fractional part of the day, otherwise
# 		0 is returned.  Negative numbers underflow (and return negative numbers of days)"""
# 		overflow=0
# 		if type(s) is FloatType:
# 			sFloor=floor(s)
# 			sFraction=s-sFloor
# 			s=int(sFloor)
# 		else:
# 			sFraction=None
# 		# python's div and mod make this calculation easy, s will always be +ve
# 		# and overflow will always be floored
# 		overflow=s//86400
# 		s=s%86400
# 		self.hour=int(s//3600)
# 		self.minute=int((s%3600)//60)
# 		if sFraction is None:
# 			self.second=int(s%60)
# 		else:
# 			self.second=(s%60)+sFraction
# 		self._CheckTime()
# 		return overflow

	def AddSeconds(self,s):
		warnings.warn("Time.AddSeconds is deprecated, use Time().Offset(seconds=s) instead", DeprecationWarning, stacklevel=2)		
		t,overflow=self.Offset(seconds=s)
		self.SetFromTime(t)
		return overflow
	
	def AddMinute(self):
		warnings.warn("Time.AddMinute is deprecated, use Time().Offset(minutes=1) instead", DeprecationWarning, stacklevel=2)		
		t,overflow=self.Offset(minutes=1)
		self.SetFromTime(t)
		return overflow
# 		if self.minute>=59:
# 			self.minute=0
# 			return self.AddHour()
# 		else:
# 			self.minute+=1

	def AddHour(self):
		warnings.warn("Time.AddHour is deprecated, use Time().Offset(hour=1) instead", DeprecationWarning, stacklevel=2)		
		t,overflow=self.Offset(hours=1)
		self.SetFromTime(t)
		return overflow
# 		if self.hour>=23:
# 			self.hour=0
# 			return 1
# 		else:
# 			self.hour+=1
		 	
	def SetTime(self,hour,minute,second,base=None):
		warnings.warn("Time.SetTime is deprecated, use Time(hour=##,...) or base.Extend(hour=##,...) instead", DeprecationWarning, stacklevel=2)		
		if base is None:
			t=type(self)(hour=hour,minute=minute,second=second)
			overflow=0
		else:
			t,overflow=base.Extend(hour=hour,minute=minute,second=second)
		self.SetFromTime(t)
		return overflow
# 		overflow=0
# 		if hour is None:
# 			# Truncation of hour or more
# 			if base is None or not base.Complete():
# 				raise DateTimeError("truncated time with no base")
# 			else:
# 				baseHour,baseMinute,baseSecond=base.GetTime()
# 				if second is None:
# 					baseSecond=None
# 					if minute is None:
# 						baseMinute=None
# 			self.hour=baseHour
# 			if minute is None:
# 				# Truncation of minutes
# 				self.minute=baseMinute
# 				if second is None:
# 					raise ValueError
# 				else:
# 					self.second=second
# 					if self.second<baseSecond:
# 						overflow=self.AddMinute()
# 			else:
# 				self.minute=minute
# 				self.second=second
# 				if self.minute<baseMinute or (self.minute==baseMinute and self.second<baseSecond):
# 					overflow=self.AddHour()
# 			# copy time zone from base
# 			self.zDirection=base.zDirection
# 			self.zOffset=base.zOffset
# 		else:
# 			self.hour=hour
# 			self.minute=minute
# 			self.second=second
# 		self._CheckTime()
# 		return overflow

	def SetZone(self,zDirection,hourOffset=None,minuteOffset=None):
		warnings.warn("Time.SetZone is deprecated, use WithZone(zDirection,etc...) instead", DeprecationWarning, stacklevel=2)
		t=self.WithZone(zDirection,hourOffset,minuteOffset)
		self.SetFromTime(t)
# 		self.zDirection=zDirection
# 		if zDirection is None:
# 			self.zOffset=None
# 		elif zDirection==0:
# 			self.zOffset=0
# 		elif hourOffset is None:
# 			self.zOffset=None
# 		elif minuteOffset is None:
# 			self.zOffset=hourOffset*60
# 		else:
# 			self.zOffset=hourOffset*60+minuteOffset
# 		self._CheckTime()
		
	def GetSeconds (self):
		warnings.warn("Time.GetSeconds is deprecated, use GetTotalSeconds() instead", DeprecationWarning, stacklevel=2)
		return self.GetTotalSeconds()
	
	def SetFromTime(self,src):
		warnings.warn("Time.SetFromTime is deprecated, use Time(src) instead", DeprecationWarning, stacklevel=2)		
		self.hour=src.hour
		self.minute=src.minute
		self.second=src.second
		self.zDirection=src.zDirection
		self.zOffset=src.zOffset
		
	def SetTimeTuple (self,t):
		warnings.warn("Time.SetTimeTuple is deprecated, use Time.FromStructTime(t) instead", DeprecationWarning, stacklevel=2)
		t=Time.FromStructTime(t)
		self.SetFromTime(t)
# 		self.hour=t[3]
# 		self.minute=t[4]
# 		self.second=t[5]
# 		self._CheckTime()

	def GetTimeTuple(self,t):
		warnings.warn("Time.GetTimeTuple is deprecated, use Time.UpdateStructTime(t) instead", DeprecationWarning, stacklevel=2)
		self.UpdateStructTime(t)

	def Now (self):
		warnings.warn("Time.Now is deprecated, use Time.FromNow() instead", DeprecationWarning, stacklevel=2)		
		t=Time.FromNow()
		self.SetFromTime(t)
# 		self.SetTimeTuple(pytime.localtime(pytime.time()))
	
	def SetFromString(self,src,base=None):
		warnings.warn("Time.SetFromString is deprecated, use Time.FromString(src[,base]) instead", DeprecationWarning, stacklevel=2)
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			return p.ParseTime(self,base)
		else:
			raise TypeError

	def SetZoneFromString(self,zoneStr):
		warnings.warn("Time.SetZoneFromString is deprecated, use Time.WithZoneString(t,zoneStr) instead", DeprecationWarning, stacklevel=2)
		if type(zoneStr) in StringTypes:
			p=ISO8601Parser(zoneStr)
			return p.ParseTimeZone(self)
		else:
			raise TypeError
				
	def SetPrecision(self,precision,truncate=False):
		warnings.warn("Time.SetPrecision is deprecated, use WithPrecision(precision,truncate) instead", DeprecationWarning, stacklevel=2)
		t=self.WithPrecision(precision,truncate)
		self.SetFromTime(t)
# 		if precision==Precision.Complete:
# 			if self.second is None:
# 				if self.minute is None:
# 					if self.hour is None:
# 						self.hour=0
# 						self.minute=0
# 					elif type(self.hour) is FloatType:
# 						self.minute,self.hour=modf(self.hour)
# 						self.minute*=60.0
# 						self.hour=int(self.hour)
# 					else:
# 						self.minute=0
# 				if type(self.minute) is FloatType:
# 					self.second,self.minute=modf(self.minute)
# 					self.second*=60.0
# 					self.minute=int(self.minute)
# 				else:
# 					self.second=0
# 			if truncate and type(self.second) is FloatType:
# 				self.second=int(floor(self.second))
# 		elif precision==Precision.Minute:
# 			if self.second is None:
# 				if self.minute is None:
# 					if self.hour is None:
# 						self.hour=0
# 						self.minute=0
# 					elif type(self.hour) is FloatType:
# 						self.minute,self.hour=modf(self.hour)
# 						self.minute*=60.0
# 						self.hour=int(self.hour)
# 					else:
# 						self.minute=0
# 				if truncate and type(self.minute) is FloatType:
# 					self.minute=int(floor(self.minute))
# 			elif truncate:
# 				self.second=None
# 			else:
# 				self.minute=float(self.minute)+self.second/60.0
# 				self.second=None
# 		elif precision==Precision.Hour:
# 			if self.second is None:
# 				if self.minute is None:
# 					if self.hour is None:
# 						self.hour=0
# 					elif truncate and type(self.hour) is FloatType:
# 						self.hour=int(floor(self.hour))
# 				elif truncate:
# 					self.minute=None
# 				else:
# 					self.hour=float(self.hour)+self.minute/60.0
# 					self.minute=None
# 			elif truncate:
# 				self.minute=self.second=None
# 			else:
# 				self.hour=float(self.hour)+self.minute/60.0+self.second/3600.0
# 				self.minute=self.second=None
# 		else:
# 			raise ValueError

	def ChangeZone(self,zChange):
		warnings.warn("Time.ChangeZone is deprecated, use ShiftZone(zDirection,zHour,zMinute) instead", DeprecationWarning, stacklevel=2)
		# we need to calculate the new zone from zChange
		z=self.GetZoneOffset()
		if z is None:
			raise DateTimeTimeError("Time zone required for ChangeZone "+str(self))
		newOffset=z+zChange
		if newOffset==0:
			t,overflow=self.ShiftZone(zDirection=0)
		elif newOffset<0:
			newOffset=-newOffset
			t,overflow=self.ShiftZone(zDirection=-1,zHour=newOffset//60,zMinute=newOffset%60)
		else:
			t,overflow=self.ShiftZone(zDirection=1,zHour=newOffset//60,zMinute=newOffset%60)
		self.SetFromTime(t)
		return overflow		
# 		zHours=zChange//60
# 		zMinutes=zChange%60
# 		if self.second is None:
# 			if self.minute is None:
# 				# hour precision only - zMinutes better be a whole number of hours
# 				if zMinutes:
# 					raise DateTimeError("fractional zone change requires at least minute precision")
# 		if zMinutes:
# 			self.minute+=zMinutes
# 			if self.minute>59:
# 				zHours+=1
# 				self.minute-=60
# 			elif self.minute<0:
# 				zHours-=1
# 				self.minute+=60
# 		if zHours:
# 			self.hour+=zHours
# 			if self.hour<0:
# 				self.hour+=24
# 				overflow=-1
# 			elif self.hour>23:
# 				self.hour-=24
# 				overflow=1
# 			else:
# 				overflow=0
# 		else:
# 			overflow=0
# 		# Now update the zone if it is specified
# 		if zChange and self.zDirection is not None:
# 			self.zOffset=(self.zDirection*self.zOffset)+zChange
# 			if self.zOffset<0:
# 				self.zOffset=-self.zOffset
# 				self.zDirection=-1
# 			else:
# 				self.zDirection=1
# 		self._CheckTime()
# 		return overflow

class TimePoint(object):
	"""A class for representing ISO timepoints
		
	TimePoints are constructed from a date and a time (which may or
	may not have a time zone), for example::
	
		TimePoint(date=Date(year=1969,month=7,day=20),
			time=Time(hour=20,minute=17,second=40,zDirection=0))
	
	If the date is missing then the date origin is used, Date() or
	0001-01-01.  Similarly, if the time is missing then the time origin
	is used, Time() or 00:00:00
	
	Times may be given with reduced precision but the date must be
	complete. In other words, there is no such thing as a timepoint
	with, month precision, use Date instead."""
	def __init__(self,src=None,date=None,time=None):
		if src is None:
			# explicit form
			if date is None:
				self.date=Date()
			else:
				self.date=date
			if time is None:
				self.time=Time()
			else:
				self.time=time
			self._CheckTimePoint()
		elif isinstance(src,TimePoint):
			self.date=src.date
			self.time=src.time
		else:
			raise TypeError("Can't construct TimePoint from %s"%repr(src))
	
	def GetCalendarTimePoint(self):
		"""Returns a tuple of::
		
			(century,year,month,day,hour,minute,second)"""			
		return self.date.GetCalendarDay()+self.time.GetTime()
		
	def GetOrdinalTimePoint(self):
		"""Returns a tuple of::
		
			(century,year,ordinalDay,hour,minute,second)"""			
		return self.date.GetOrdinalDay()+self.time.GetTime()
		
	def GetWeekDayTimePoint(self):
		"""Returns a tuple of::
		
			(century,decade,year,week,weekday,hour,minute,second)"""			
		return self.date.GetWeekDay()+self.time.GetTime()
		
	def GetZone(self):
		"""Returns a tuple of ::
		
			(zDirection,zOffset)
		
		See :py:meth:`Time.GetZone` for details."""
		return self.time.GetZone()
	
	def WithZone(self,zDirection,zHour=None,zMinute=None):
		"""Constructs a :py:class:`TimePoint` instance from an existing
		TimePoint but with the time zone specified.  The time zone of
		the existing TimePoint is ignored."""
		return type(self)(date=self.date,time=self.time.WithZone(zDirection=zDirection,zHour=zHour,zMinute=zMinute))
		
	def ShiftZone(self,zDirection,zHour=None,zMinute=None):
		"""Constructs a :py:class:`TimePoint` instance from an existing TimePoint
		but shifted so that it is in the time zone specified."""
		t,overflow=self.time.ShiftZone(zDirection,zHour,zMinute)
		if overflow:
			d=self.date.Offset(days=overflow)
		else:
			d=self.date
		return type(self)(date=d,time=t)
		
	def UpdateStructTime (self,t):
		"""UpdateStructTime changes the year, month, date, hour, minute
		and second fields of t, a struct_time, to match the values in
		this date."""
		self.date.UpdateStructTime(t)
		self.time.UpdateStructTime(t)
		
	@classmethod
	def FromStructTime(cls,t):
		"""Constructs a :py:class:`TimePoint` from a struct_time, such as
		might be returned from time.gmtime() and related functions."""
		return cls(date=Date.FromStructTime(t),time=Time.FromStructTime(t))

	@classmethod
	def FromString(cls,src,base=None,tDesignators="T"):
		"""Constructs a TimePoint from a string representation. 
		Truncated forms are parsed with reference to *base*."""
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			tp,f=p.ParseTimePointFormat(base,tDesignators)
			return tp
		else:
			raise TypeError

	@classmethod
	def FromStringFormat(cls,src,base=None,tDesignators="T"):		
		"""Similar to :py:meth:`FromString` except that a tuple is
		returned, the first item is the resulting :py:class:`TimePoint`
		instance, the second is a string describing the format parsed.
		For example::
		
			tp,f=TimePoint.FromStringFormat("1969-07-20T20:40:17")
			# f is set to "YYYY-MM-DDTmm:hh:ss"."""
		if type(src) in StringTypes:
			p=ISO8601Parser(src)
			return p.ParseTimePointFormat(base,tDesignators)
		else:
			raise TypeError

	def __str__(self):
		"""Formats the Timepoint to a string using the default, extended, calendar format."""
		return str(self.GetCalendarString())
		
	def __unicode__(self):
		"""Formats the Timepoint to a unicode string using the default, extended, calendar format."""
		return unicode(self.GetCalendarString())

	def __repr__(self):
		return "TimePoint(date=%s,time=%s)"%(repr(self.date),repr(self.time))

	def GetCalendarString(self,basic=False,truncation=NoTruncation,ndp=0,zonePrecision=Precision.Complete,dp=",",tDesignator="T"):
		"""Formats this TimePoint using calendar form, for example 1969-07-20T20:17:40
		
			*basic*
				True/False, selects basic form, e.g., 19690720T201740. 
				Default is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the date.  For example, if you
				specify :py:attr:`Truncation.Year` you'll get
				--07-20T20:17:40 or --0720T201740.  Default is
				:py:attr:`NoTruncation`.  Note that Calendar format only
				:supports Century, Year and Month truncated forms, the
				time component cannot be truncated.
			
			*ndp*, *dp* and *zonePrecision*
				As specified in :py:meth:`Time.GetString`"""
		return self.date.GetCalendarString(basic,truncation)+tDesignator+\
			self.time.GetString(basic,NoTruncation,ndp,zonePrecision,dp)
		
	def GetOrdinalString(self,basic=0,truncation=0,ndp=0,zonePrecision=Precision.Complete,dp=",",tDesignator="T"):
		"""Formats this TimePoint using ordinal form, for example 1969-201T20-17-40
		
			*basic*
				True/False, selects basic form, e.g., 1969201T201740. 
				Default is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the date.  For example, if you
				specify :py:attr:`Truncation.Year` you'll get
				-201T20-17-40. Default is :py:attr:`NoTruncation`.  Note
				that ordinal format only supports century and year
				truncated forms, the time component cannot be
				truncated.
			
			*ndp*, *dp* and *zonePrecision*
				As specified in :py:meth:`Time.GetString`"""
		return self.date.GetOrdinalString(basic,truncation)+tDesignator+\
			self.time.GetString(basic,NoTruncation,ndp,zonePrecision,dp)
		
	def GetWeekString(self,basic=0,truncation=0,ndp=0,zonePrecision=Precision.Complete,dp=",",tDesignator="T"):
		"""Formats this TimePoint using week form, for example 1969-W29-7T20:17:40
		
			*basic*
				True/False, selects basic form, e.g., 1969W297T201740. 
				Default is False

			*truncation*
				One of the :py:class:`Truncation` constants used to
				select truncated forms of the date.  For example, if you
				specify :py:attr:`Truncation.Year` you'll get
				-W297T20-17-40. Default is :py:attr:`NoTruncation`. 
				Note that week format only supports century, decade,
				year and week truncated forms, the time component cannot
				be truncated.

			*ndp*, *dp* and *zonePrecision*
				As specified in :py:meth:`Time.GetString`"""
		return self.date.GetWeekString(basic,truncation)+tDesignator+\
			self.time.GetString(basic,NoTruncation,ndp,zonePrecision,dp)

	@classmethod
	def FromUnixTime (cls,unixTime):
		"""Constructs a TimePoint from *unixTime*, the number of seconds
		since the time origin.  The resulting time has no zone.

		This method uses python's gmtime(0) to obtain the Unix origin
		time."""
		utcTuple=pytime.gmtime(0)
		t,overflow=Time.FromStructTime(utcTuple).Offset(seconds=unixTime)
		d=Date.FromStructTime(utcTuple).Offset(days=overflow)
		return cls(date=d,time=t)
				
	@classmethod
	def FromNow(cls):
		t=pytime.time()
		localTime=pytime.localtime(t)
		return cls.FromStructTime(localTime)
	
	@classmethod
	def FromNowUTC(cls):
		t=pytime.time()
		utcTime=pytime.gmtime(t)
		return cls.FromStructTime(utcTime).WithZone(zDirection=0)		

	def Complete (self):
		"""Returns True if this TimePoint has a complete representation,
		i.e., does not use one of the reduced precision forms.

		(Whether or not a TimePoint is complete refers only to the
		precision of the time value, it says nothing about the presence
		or absence of a time zone offset.)"""
		return self.date.Complete() and self.time.Complete()

	def GetPrecision (self):
		"""Returns one of the :py:class:`Precision` constants
		representing the precision of this TimePoint."""
		return self.time.GetPrecision()
	
	def WithPrecision(self):
		"""Constructs a :py:class:`TimePoint` instance from an existing
		TimePoint but with the precision specified by *precision*.  For
		more details see :py:meth:`Time.WithPrecision`"""
		return type(self)(date=self.date,time=self.time.WithPrecision(precision,truncate))
		
	def _CheckTimePoint(self):
		self.date._CheckDate()
		self.time._CheckTime()
		if self.date.GetPrecision()!=Precision.Complete:
			raise DateTimeError("timepoint requires complete precision for date")
	
	def __hash__(self):
		if self.time.GetZoneOffset():
			return hash(self.ShiftZone(zDirection=0))
		else:
			# no zone, or Zulu time
			return hash((self.date,self.time))

	def __cmp__ (self,other):
		"""We deal with partially specified TimePoints in the same way as
		:py:meth:`Time.__cmp__`.  However, unlike the comparison of Time
		instances, we reduce all TimePoints with time-zones to a common
		zone before doing a comparison. As a result, TimePoints which
		are equal but are expressed in different time zones will still
		compare equal."""
		if not isinstance(other,TimePoint):
			other=type(self)(other)
		# we need to follow the rules for comparing times
		if self.time.GetPrecision()!=other.time.GetPrecision():
			raise ValueError("Incompatible precision for comparison: "+str(other))
		z1=self.time.GetZoneOffset()
		z2=other.time.GetZoneOffset()
		if z1!=z2:
			if z1 is None or z2 is None:
				raise ValueError("Can't compare zone: "+str(other))
			# we need to change the timezone of other to match ours
			other=other.ShiftZone(*self.time.GetZone3())
		result=cmp(self.date,other.date)
		if not result:
			result=cmp(self.time,other.time)
		return result
	
	def SetOrigin (self):
		warnings.warn("TimePoint.SetOrigin is deprecated, use TimePoint() instead", DeprecationWarning, stacklevel=2)
		self.date=Date()
		self.time=Time()

	def SetFromTimePoint(self,t):
		warnings.warn("TimePoint.SetFromTimePoint is deprecated, use TimePoint(t.date,t.time) instead", DeprecationWarning, stacklevel=2)
		self.date=Date(t.date)
		self.time=Time(t.time)
	
	def SetCalendarTimePoint(self,century,year,month,day,hour,minute,second,base=None):
		warnings.warn("TimePoint.SetCalendarTimePoint is deprecated, use TimePoint(Date(century=...),Time(hour=...)) instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint(date=Date(century=century,year=year,month=month,day=day,base=base),
			time=Time(hour=hour,minute=minute,second=second)))
	
	def SetOrdinalTimePoint(self,century,year,ordinalDay,hour,minute,second,base=None):
		warnings.warn("TimePoint.SetOrdinalTimePoint is deprecated, use TimePoint(Date(century=...),Time(hour=...)) instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint(date=Date(century=century,year=year,ordinalDay=ordinalDay,base=base),
			time=Time(hour,minute,second)))

	def SetWeekTimePoint (self,century,decade,year,week,day,hour,minute,second,base=None):
		warnings.warn("TimePoint.SetWeekTimePoint is deprecated, use TimePoint(Date(century=...),Time(hour=...)) instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint(date=Date(century=century,decade=decade,year=year,week=week,day=day,base=base),
			time=Time(hour=hour,minute=minute,second=second)))
			
	def SetFromString(self,timePointStr,base=None):
		warnings.warn("TimePoint.SetFromString is deprecated, use TimePoint.FromString(src[,base]) instead", DeprecationWarning, stacklevel=2)
		if type(timePointStr) in StringTypes:
			p=ISO8601Parser(timePointStr)
			tp,f=p.ParseTimePointFormat(base)
			self.date=Date(tp.date)
			self.time=Time(tp.time)
		else:
			raise TypeError

	def SetZone(self,zDirection,hourOffset=None,minuteOffset=None):
		warnings.warn("TimePoint.SetZone is deprecated, use TimePoint.WithZone(zDirection, etc...) instead", DeprecationWarning, stacklevel=2)
		t=self.time.WithZone(zDirection,hourOffset,minuteOffset)
		self.SetFromTimePoint(TimePoint(date=self.date,time=t))
		
	def GetTimeTuple (self,timeTuple):
		warnings.warn("TimePoint.GetTimeTuple is deprecated, use TimePoint.UpdateStructTime(t) instead", DeprecationWarning, stacklevel=2)
		self.UpdateStructTime(timeTuple)
			
	def SetTimeTuple (self,t):
		warnings.warn("TimePoint.SetTimeTuple is deprecated, use TimePoint.FromStructTime(t) instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint.FromStructTime(t))
	
	def SetUnixTime (self,unixTime):
		warnings.warn("TimePoint.SetUnixTime is deprecated, use TimePoint.FromUnixTime(t) instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint.FromUnixTime(unixTime))
				
	def Now (self):
		warnings.warn("TimePoint.Now is deprecated, use TimePoint.FromNow() instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint.FromNow())

	def NowUTC(self):
		warnings.warn("TimePoint.NowUTC is deprecated, use TimePoint.FromNowUTC() instead", DeprecationWarning, stacklevel=2)
		self.SetFromTimePoint(TimePoint.FromNowUTC())
		
	def SetPrecision(self,precision,truncate=0):
		warnings.warn("TimePoint.SetPrecision is deprecated, use WithPrecision(precision,truncate) instead", DeprecationWarning, stacklevel=2)
		return self.SetFromTimePoint(self.WithPrecision(precision,truncate))

	def ChangeZone(self,zChange):
		warnings.warn("TimePoint.ChangeZone is deprecated, use ShiftZone() instead", DeprecationWarning, stacklevel=2)
		z=self.time.GetZoneOffset()
		if z is None:
			raise DateTimeTimeError("Time zone required for ChangeZone "+str(self))
		else:
			newOffset=z+zChange
		if newOffset==0:
			t=self.ShiftZone(zDirection=0)
		elif newOffset<0:
			newOffset=-newOffset
			t=self.ShiftZone(zDirection=-1,zHour=newOffset//60,zMinute=newOffset%60)
		else:
			t=self.ShiftZone(zDirection=1,zHour=newOffset//60,zMinute=newOffset%60)
		return self.SetFromTimePoint(t)


class Duration:
	"""A class for representing ISO durations"""
	def __init__(self,value=None):
		if type(value) in StringTypes:
			self.SetFromString(value)
		elif isinstance(value,Duration):
			self.SetFromDuration(value)
		elif value is None:
			self.SetZero()
		else:
			raise TypeError
	
	def SetZero(self):
		self.years=0
		self.months=0
		self.days=0
		self.hours=0
		self.minutes=0
		self.seconds=0
		self.weeks=None

	def SetCalendarDuration(self,years,months,days,hours,minutes,seconds):
		self.years=years
		self.months=months
		self.days=days
		self.hours=hours
		self.minutes=minutes
		self.seconds=seconds
		self.weeks=None
	
	def GetCalendarDuration(self):
		if self.weeks is None:
			return (self.years,self.months,self.days,self.hours,self.minutes,self.seconds)
		else:
			raise DateTimeError("duration mode mismatch")
			
	def SetWeekDuration(self,weeks):
		self.weeks=weeks
		self.years=self.months=self.days=self.hours=self.minutes=self.seconds=None
	
	def GetWeekDuration(self):
		if self.weeks is None:
			raise DateTimeError("duration mode mismatch")
		else:
			return self.weeks
			
	def SetFromString(self,durationStr):
		if type(durationStr) in StringTypes:
			p=ISO8601Parser(durationStr)
			return p.ParseDuration(self)
		else:
			raise TypeError

	def GetString(self,truncateZeros=0,ndp=0):
		if self.weeks is None:
			components=list(self.GetCalendarDuration())
			while components[-1] is None:
				# adjust for the precision
				components=components[:-1]
			designators='YMDHMS'
			if truncateZeros:
				for i in range(len(components)-1):
					if components[i]==0:
						components[i]=None
					else:
						break
			for i in range(len(components)):
				value=components[i]
				if value is None:
					components[i]=""
					continue
				if type(value) is FloatType:
					fraction,value=modf(value)
					value=int(value)
					if ndp:
						# to prevent truncation being caught out by sloppy machine rounding
						# we add a small time to the fraction (at most 1ns and typically less)
						if ndp>0:
							fractionStr="%i,%0*i"
						else:
							fractionStr="%i.%0*i"
							ndp=-ndp
						fraction+=2e-13
						fraction=int(floor(fraction*float(10L**ndp)))
						components[i]=fractionStr%(value,ndp,fraction)
					else:
						components[i]=str(value)
				else:
					components[i]=str(value)
				components[i]=components[i]+"YMDHMS"[i]
			datePart=string.join(components[0:3],'')
			timePart=string.join(components[3:],'')
			if timePart:
				return 'P'+datePart+'T'+timePart
			else:
				return 'P'+datePart
		else:
			pass					
				
	def SetFromDuration(self,src):
		self.years=src.years
		self.months=src.months
		self.days=src.days
		self.hours=src.hours
		self.minutes=src.minutes
		self.seconds=src.seconds
		self.weeks=src.weeks
	
	def __eq__(self,other):
		if not isinstance(other,Duration):
			other=Duration(other)
		if self.years==other.years and \
			self.months==other.months and \
			self.days==other.days and \
			self.hours==other.hours and \
			self.minutes==other.minutes and \
			self.seconds==other.seconds and \
			self.weeks==other.weeks:
			return 1
		else:
			return 0
		
					
# For compatibility
ISODate=Date
ISOTime=Time
ISOTimePoint=TimePoint

BasicDateFormats={
	"YYYYMMDD":1,
	"YYYY-MM":1,
	"YYYY":1,
	"YY":1,
	"YYMMDD":1,
	"-YYMM":1,
	"-YY":1,
	"--MMDD":1,
	"--MM":1,
	"---DD":1,
	"YYYYDDD":1,
	"YYDDD":1,
	"-DDD":1,
	"YYYYWwwD":1,
	"YYYYWww":1,
	"YYWwwD":1,
	"YYWww":1,
	"-YWwwD":1,
	"-YWww":1,
	"-WwwD":1,
	"-Www":1,
	"-W-D":1
	}

ExtendedDateFormats={
	"YYYY-MM-DD":1,
	"YYYY-MM":1,
	"YYYY":1,
	"YY":1,
	"YY-MM-DD":1,
	"-YY-MM":1,
	"-YY":1,
	"--MM-DD":1,
	"--MM":1,
	"---DD":1,
	"YYYY-DDD":1,
	"YY-DDD":1,
	"-DDD":1,
	"YYYY-Www-D":1,
	"YYYY-Www":1,
	"YY-Www-D":1,
	"YY-Www":1,
	"-Y-Www-D":1,
	"-Y-Www":1,
	"-Www-D":1,
	"-Www":1,
	"-W-D":1
	}

BasicTimeFormats={
	"hhmmss":1,
	"hhmm":1,
	"hh":1,
	"hhmmss,s":1,
	"hhmmss.s":1,
	"hhmm,m":1,
	"hhmm.m":1,
	"hh,h":1,
	"hh.h":1,
	"hhmmssZ":1,
	"hhmmZ":1,
	"hhZ":1,
	"hhmmss,sZ":1,
	"hhmmss.sZ":1,
	"hhmm,mZ":1,
	"hhmm.mZ":1,
	"hh,hZ":1,
	"hh.hZ":1,
	"hhmmss+hhmm":1,
	"hhmm+hhmm":1,
	"hh+hhmm":1,
	"hhmmss,s+hhmm":1,
	"hhmmss.s+hhmm":1,
	"hhmm,m+hhmm":1,
	"hhmm.m+hhmm":1,
	"hh,h+hhmm":1,
	"hh.h+hhmm":1,
	"hhmmss+hh":1,
	"hhmm+hh":1,
	"hh+hh":1,
	"hhmmss,s+hh":1,
	"hhmmss.s+hh":1,
	"hhmm,m+hh":1,
	"hhmm.m+hh":1,
	"hh,h+hh":1,
	"hh.h+hh":1,
	"-mmss":1,
	"-mm":1,
	"--ss":1,
	"-mmss,s":1,
	"-mm,m":1,
	"-mm.m":1,
	"--ss,s":1,
	"--ss.s":1
	}

ExtendedTimeFormats={
	"hh:mm:ss":1,
	"hh:mm":1,
	"hh":1,
	"hh:mm:ss,s":1,
	"hh:mm:ss.s":1,
	"hh:mm,m":1,
	"hh:mm.m":1,
	"hh,h":1,
	"hh.h":1,
	"hh:mm:ssZ":1,
	"hh:mmZ":1,
	"hhZ":1,
	"hh:mm:ss,sZ":1,
	"hh:mm:ss.sZ":1,
	"hh:mm,mZ":1,
	"hh:mm.mZ":1,
	"hh,hZ":1,
	"hh.hZ":1,
	"hh:mm:ss+hh:mm":1,
	"hh:mm+hh:mm":1,
	"hh+hh:mm":1,
	"hh:mm:ss,s+hh:mm":1,
	"hh:mm:ss.s+hh:mm":1,
	"hh:mm,m+hh:mm":1,
	"hh:mm.m+hh:mm":1,
	"hh,h+hh:mm":1,
	"hh.h+hh:mm":1,
	"hh:mm:ss+hh":1,
	"hh:mm+hh":1,
	"hh+hh":1,
	"hh:mm:ss,s+hh":1,
	"hh:mm:ss.s+hh":1,
	"hh:mm,m+hh":1,
	"hh:mm.m+hh":1,
	"hh,h+hh":1,
	"hh.h+hh":1,
	"-mm:ss":1,
	"-mm":1,
	"--ss":1,
	"-mm:ss,s":1,
	"-mm:ss.s":1,
	"-mm,m":1,
	"-mm.m":1,
	"--ss,s":1,
	"--ss.s":1
	}


class ISO8601Parser(RFC2234CoreParser):

	def ParseTimePointFormat(self,base=None,tDesignators="T"):
		d,df=self.ParseDateFormat(base)
		if not d.Complete():
			raise DateTimeError("incomplete date in time point %s"%str(d))
		if self.theChar not in tDesignators:
			raise DateTimeError("time-point requires time %s..."%str(d))
		tDesignator=self.theChar
		t,overflow,tf=self.ParseTimeFormat(None,tDesignators)
		if overflow:
			d=d.Offset(days=overflow)
		# check that the date format and time format are compatible, i.e., both either basic or extended
		if not ((ExtendedTimeFormats.get(tf) and ExtendedDateFormats.get(df)) or
			(BasicTimeFormats.get(tf) and BasicDateFormats.get(df))):
			raise DateTimeError("inconsistent use of basic/extended form in time point %s%s%s"%(df,tDesignator,tf))
		return TimePoint(date=d,time=t),df+tDesignator+tf
	
	def ParseTimePoint(self,timePoint,base=None,tDesignators="T"):
		warnings.warn("ISO8601Parser.ParseTimePoint is deprecated, use ParseTimePointFormat instead", DeprecationWarning, stacklevel=2)		
		date,dateFormat=self.ParseDateFormat(base)
		timePoint.date=date
		if not timePoint.date.Complete():
			raise DateTimeError("incomplete date in time point %s"%str(timePoint.date))
		if self.theChar not in tDesignators:
			raise DateTimeError("time-point requires time %s..."%str(timePoint.date))
		tDesignator=self.theChar
		t,overflow,timeFormat=self.ParseTimeFormat(None,tDesignators)
		timePoint.time=t
		# check that dateFormat and timeFormat are compatible, i.e., both either basic or extended
		if not ((ExtendedTimeFormats.get(timeFormat) and ExtendedDateFormats.get(dateFormat)) or
			(BasicTimeFormats.get(timeFormat) and BasicDateFormats.get(dateFormat))):
			raise DateTimeError("inconsistent use of basic/extended form in time point %s%s%s"%(dateFormat,tDesignator,timeFormat))
		return dateFormat+tDesignator+timeFormat
				
	def ParseDateFormat(self,base=None):
		"""Returns a tuple of (:py:class:`Date`, string).
		
		The second item in the tuple is a string representing the format
		parsed."""
		if IsDIGIT(self.theChar):
			v1=self.ParseDIGIT()
			v1=v1*10+self.ParseDIGIT()
			if IsDIGIT(self.theChar):
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v3=v3*10+self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v4=self.ParseDIGIT()
							if IsDIGIT(self.theChar):
								v4=v4*10+self.ParseDIGIT()
								return Date(century=v1,year=v2,month=v3,day=v4,base=base),"YYYYMMDD"
							else:
								return Date(century=v1,year=v2,ordinalDay=v3*10+v4,base=base),"YYYYDDD"
						else:
							return Date(year=v1,month=v2,day=v3,base=base),"YYMMDD"
					else:
						return Date(year=v1,ordinalDay=v2*10+v3,base=base),"YYDDD"
				elif self.theChar=="-":
					self.NextChar()
					if IsDIGIT(self.theChar):
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v3=v3*10+self.ParseDIGIT()
							return Date(century=v1,year=v2,ordinalDay=v3,base=base),"YYYY-DDD"
						elif self.theChar=="-":
							self.NextChar()
							v4=self.ParseDIGIT()
							v4=v4*10+self.ParseDIGIT()
							return Date(century=v1,year=v2,month=v3,day=v4,base=base),"YYYY-MM-DD"
						else:
							return Date(century=v1,year=v2,month=v3,base=base),"YYYY-MM"
					elif self.theChar=="W":
						self.NextChar()
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						if self.theChar=="-":
							self.NextChar()
							v4=self.ParseDIGIT()
							return Date(century=v1,decade=v2//10,year=v2%10,week=v3,weekday=v4,base=base),"YYYY-Www-D"
						else:
							return Date(century=v1,decade=v2//10,year=v2%10,week=v3,base=base),"YYYY-Www"
					else:
						self.SyntaxError("expected digit or W in ISO date")
				elif self.theChar=="W":
					self.NextChar()
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v4=self.ParseDIGIT()
						return Date(century=v1,decade=v2//10,year=v2%10,week=v3,weekday=v4,base=base),"YYYYWwwD"
					else:
						return Date(century=v1,decade=v2//10,year=v2%10,week=v3,base=base),"YYYYWww"""
				else:
					return Date(century=v1,year=v2,base=base),"YYYY"
			elif self.theChar=="-":
				self.NextChar()
				if IsDIGIT(self.theChar):
					"""YY-DDD, YY-MM-DD"""
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=v2*10+self.ParseDIGIT()
						return Date(year=v1,ordinalDay=v2,base=base),"YY-DDD"
					elif self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						return Date(year=v1,month=v2,day=v3,base=base),"YY-MM-DD"
					else:
						self.SyntaxError("expected digit or hyphen in ISO date")
				elif self.theChar=="W":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						return Date(decade=v1//10,year=v1%10,week=v2,weekday=v3,base=base),"YY-Www-D"
					else:
						return Date(decade=v1//10,year=v1%10,week=v2,base=base),"YY-Www"
				else:
					self.SyntaxError("expected digit or W in ISO date")
			elif self.theChar=="W":
				self.NextChar()
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					return Date(decade=v1//10,year=v1%10,week=v2,weekday=v3,base=base),"YYWwwD"
				else:
					return Date(decade=v1//10,year=v1%10,week=v2,base=base),"YYWww"			
			else:
				return Date(century=v1,base=base),"YY"				
		elif self.theChar=="-":
			self.NextChar()
			if IsDIGIT(self.theChar):
				v1=self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v2=v2*10+self.ParseDIGIT()
							return Date(year=v1,month=v2,base=base),"-YYMM"
						else:
							return Date(ordinalDay=v1*10+v2,base=base),"-DDD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						return Date(year=v1,month=v2,base=base),"-YY-MM"
					else:
						return Date(year=v1,base=base),"-YY"
				elif self.theChar=="-":
					self.NextChar()
					self.ParseTerminal("W")
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						return Date(year=v1,week=v2,weekday=v3,base=base),"-Y-Www-D"
					else:
						return Date(year=v1,week=v2,base=base),"-Y-Www"
				elif self.theChar=="W":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v3=self.ParseDIGIT()
						return Date(year=v1,week=v2,weekday=v3,base=base),"-YWwwD"
					else:
						return Date(year=v1,week=v2,base=base),"-YWww"
			elif self.theChar=="-":
				self.NextChar()
				if IsDIGIT(self.theChar):
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						return Date(month=v1,day=v2,base=base),"--MMDD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						return Date(month=v1,day=v2,base=base),"--MM-DD"
					else:
						return Date(month=v1,base=base),"--MM"
				elif self.theChar=="-":
					self.NextChar()
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					return Date(day=v1,base=base),"---DD"
				else:
					self.SyntaxError("expected digit or hyphen in truncated ISO date")
			elif self.theChar=="W":
				self.NextChar()
				if IsDIGIT(self.theChar):
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						return Date(week=v1,weekday=v2,base=base),"-WwwD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						return Date(week=v1,weekday=v2,base=base),"-Www-D"
					else:
						return Date(week=v1,base=base),"-Www"
				elif self.theChar=="-":
					self.NextChar()
					v1=self.ParseDIGIT()
					return Date(weekday=v1,base=base),"-W-D"
				else:
					self.SyntaxError("expected digit or hyphen in truncated ISO date")
			else:
				self.SyntaxError("expected digit, hyphen or W in truncated ISO date")
		else:
			self.SyntaxError("expected digit or hyphen in ISO date")

	def ParseDate(self,date,base=None):
		warnings.warn("ISO8601Parser.ParseDate is deprecated, use ParseDateFormat instead", DeprecationWarning, stacklevel=2)		
		if IsDIGIT(self.theChar):
			v1=self.ParseDIGIT()
			v1=v1*10+self.ParseDIGIT()
			if IsDIGIT(self.theChar):
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v3=v3*10+self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v4=self.ParseDIGIT()
							if IsDIGIT(self.theChar):
								v4=v4*10+self.ParseDIGIT()
								date.SetCalendarDay(v1,v2,v3,v4,base)
								return "YYYYMMDD"
							else:
								date.SetOrdinalDay(v1,v2,v3*10+v4,base)
								return "YYYYDDD"
						else:
							date.SetCalendarDay(None,v1,v2,v3,base)
							return "YYMMDD"
					else:
						date.SetOrdinalDay(None,v1,v2*10+v3,base)
						return "YYDDD"
				elif self.theChar=="-":
					self.NextChar()
					if IsDIGIT(self.theChar):
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v3=v3*10+self.ParseDIGIT()
							date.SetOrdinalDay(v1,v2,v3,base)
							return "YYYY-DDD"
						elif self.theChar=="-":
							self.NextChar()
							v4=self.ParseDIGIT()
							v4=v4*10+self.ParseDIGIT()
							date.SetCalendarDay(v1,v2,v3,v4,base)
							return "YYYY-MM-DD"
						else:
							date.SetCalendarDay(v1,v2,v3,None,base)
							return "YYYY-MM"
					elif self.theChar=="W":
						self.NextChar()
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						if self.theChar=="-":
							self.NextChar()
							v4=self.ParseDIGIT()
							date.SetWeekDay(v1,v2//10,v2%10,v3,v4,base)
							return "YYYY-Www-D"
						else:
							date.SetWeekDay(v1,v2//10,v2%10,v3,None,base)
							return "YYYY-Www"
					else:
						self.SyntaxError("expected digit or W in ISO date")
				elif self.theChar=="W":
					self.NextChar()
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v4=self.ParseDIGIT()
						date.SetWeekDay(v1,v2//10,v2%10,v3,v4,base)
						return "YYYYWwwD"
					else:
						date.SetWeekDay(v1,v2//10,v2%10,v3,None,base)
						return "YYYYWww"""
				else:
					date.SetCalendarDay(v1,v2,None,None,base)
					return "YYYY"
			elif self.theChar=="-":
				self.NextChar()
				if IsDIGIT(self.theChar):
					"""YY-DDD, YY-MM-DD"""
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=v2*10+self.ParseDIGIT()
						date.SetOrdinalDay(None,v1,v2,base)
						return "YY-DDD"
					elif self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						date.SetCalendarDay(None,v1,v2,v3,base)
						return "YY-MM-DD"
					else:
						self.SyntaxError("expected digit or hyphen in ISO date")
				elif self.theChar=="W":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						date.SetWeekDay(None,v1//10,v1%10,v2,v3,base)
						return "YY-Www-D"
					else:
						date.SetWeekDay(None,v1//10,v1%10,v2,None,base)
						return "YY-Www"
				else:
					self.SyntaxError("expected digit or W in ISO date")
			elif self.theChar=="W":
				self.NextChar()
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					date.SetWeekDay(None,v1//10,v1%10,v2,v3,base)
					return "YYWwwD"
				else:
					date.SetWeekDay(None,v1//10,v1%10,v2,None,base)
					return "YYWww"			
			else:
				date.SetCalendarDay(v1,None,None,None,base)
				return "YY"				
		elif self.theChar=="-":
			self.NextChar()
			if IsDIGIT(self.theChar):
				v1=self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v2=v2*10+self.ParseDIGIT()
							date.SetCalendarDay(None,v1,v2,None,base)
							return "-YYMM"
						else:
							date.SetOrdinalDay(None,None,v1*10+v2,base)
							return "-DDD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						date.SetCalendarDay(None,v1,v2,None,base)
						return "-YY-MM"
					else:
						date.SetCalendarDay(None,v1,None,None,base)
						return "-YY"
				elif self.theChar=="-":
					self.NextChar()
					self.ParseTerminal("W")
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						date.SetWeekDay(None,None,v1,v2,v3,base)
						return "-Y-Www-D"
					else:
						date.SetWeekDay(None,None,v1,v2,None,base)
						return "-Y-Www"
				elif self.theChar=="W":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v3=self.ParseDIGIT()
						date.SetWeekDay(None,None,v1,v2,v3,base)
						return "-YWwwD"
					else:
						date.SetWeekDay(None,None,v1,v2,None,base)
						return "-YWww"
			elif self.theChar=="-":
				self.NextChar()
				if IsDIGIT(self.theChar):
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						date.SetCalendarDay(None,None,v1,v2,base)
						return "--MMDD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						date.SetCalendarDay(None,None,v1,v2,base)
						return "--MM-DD"
					else:
						date.SetCalendarDay(None,None,v1,None,base)
						return "--MM"
				elif self.theChar=="-":
					self.NextChar()
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					date.SetCalendarDay(None,None,None,v1,base)
					return "---DD"
				else:
					self.SyntaxError("expected digit or hyphen in truncated ISO date")
			elif self.theChar=="W":
				self.NextChar()
				if IsDIGIT(self.theChar):
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						date.SetWeekDay(None,None,None,v1,v2,base)
						return "-WwwD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						date.SetWeekDay(None,None,None,v1,v2,base)
						return "-Www-D"
					else:
						date.SetWeekDay(None,None,None,v1,None,base)
						return "-Www"
				elif self.theChar=="-":
					self.NextChar()
					v1=self.ParseDIGIT()
					date.SetWeekDay(None,None,None,None,v1,base)
					return "-W-D"
				else:
					self.SyntaxError("expected digit or hyphen in truncated ISO date")
			else:
				self.SyntaxError("expected digit, hyphen or W in truncated ISO date")
		else:
			self.SyntaxError("expected digit or hyphen in ISO date")
	
	def ParseTimeFormat(self,base=None,tDesignators="T"):
		if self.theChar in tDesignators:
			self.NextChar()
			tDesignator=1
		else:
			tDesignator=0
		if IsDIGIT(self.theChar):
			v1=self.ParseDIGIT()
			v1=v1*10+self.ParseDIGIT()
			if IsDIGIT(self.theChar):
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v3=float(v3)+self.ParseFraction()
						hour,minute,second=v1,v2,v3
						tFormat="hhmmss%ss"%point
					else:
						hour,minute,second=v1,v2,v3
						tFormat="hhmmss"
				elif self.theChar=="." or self.theChar==",":
					point=self.theChar
					v2=float(v2)+self.ParseFraction()
					hour,minute,second=v1,v2,None
					tFormat="hhmm%sm"%point
				else:
					hour,minute,second=v1,v2,None
					tFormat="hhmm"
			elif self.theChar=="." or self.theChar==",":
				point=self.theChar
				v1=float(v1)+self.ParseFraction()
				hour,minute,second=v1,None,None
				tFormat="hh%sh"%point
			elif self.theChar==":":
				self.NextChar()
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if self.theChar==":":
					self.NextChar()
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v3=float(v3)+self.ParseFraction()
						hour,minute,second=v1,v2,v3
						tFormat="hh:mm:ss%ss"%point
					else:
						hour,minute,second=v1,v2,v3
						tFormat="hh:mm:ss"
				elif self.theChar=="," or self.theChar==".":
					point=self.theChar
					v2=float(v2)+self.ParseFraction()
					hour,minute,second=v1,v2,None
					tFormat="hh:mm%sm"%point
				else:
					hour,minute,second=v1,v2,None
					tFormat="hh:mm"
			else:
				hour,minute,second=v1,None,None
				tFormat="hh"
		elif self.theChar=="-":
			if tDesignator:
				self.SyntaxError("time designator T before truncated time")
			self.NextChar()
			if IsDIGIT(self.theChar):
				v1=self.ParseDIGIT()
				v1=v1*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v2=float(v2)+self.ParseFraction()
						hour,minute,second=None,v1,v2
						tFormat="-mmss%ss"%point
					else:
						hour,minute,second=None,v1,v2
						tFormat="-mmss"
				elif self.theChar=="." or self.theChar==",":
					point=self.theChar
					v1=float(v1)+self.ParseFraction()
					hour,minute,second=None,v1,None
					tFormat="-mm%sm"%point
				elif self.theChar==":":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v2=float(v2)+self.ParseFraction()
						hour,minute,second=None,v1,v2
						tFormat="-mm:ss%ss"%point
					else:
						hour,minute,second=None,v1,v2
						tFormat="-mm:ss"
				else:
					hour,minute,second=None,v1,None
					tFormat="-mm"
			elif self.theChar=="-":
				self.NextChar()
				v1=self.ParseDIGIT()
				v1=v1*10+self.ParseDIGIT()
				if self.theChar=="." or self.theChar==",":
					point=self.theChar
					v1=float(v1)+self.ParseFraction()
					hour,minute,second=None,None,v1
					tFormat="--ss%ss"%point
				else:
					hour,minute,second=None,None,v1
					tFormat="--ss"
			else:
				self.SyntaxError("expected digit or hyphen in truncated Time")
			# truncated forms cannot take timezones, return early
			t,overflow=base.Extend(hour=hour,minute=minute,second=second)
			return t,overflow,tFormat
		else:
			self.SyntaxError("expected digit or hyphen in Time")
		if self.theChar is not None and self.theChar in "Z+-":
			# can't be truncated form
			zDirection,zHour,zMinute,tzFormat=self.ParseTimeZoneFormat()
			tFormat+=tzFormat
			if not (BasicTimeFormats.get(tFormat) or ExtendedTimeFormats.get(tFormat)):
				raise DateTimeError("inconsistent use of extended/basic format in time zone")
			return Time(hour=hour,minute=minute,second=second,zDirection=zDirection,zHour=zHour,zMinute=zMinute),0,tFormat
		elif base is not None:
			t,overflow=base.Extend(hour=hour,minute=minute,second=second)
			return t,overflow,tFormat
		else:
			return Time(hour=hour,minute=minute,second=second),0,tFormat
			
	def ParseTimeZoneFormat(self):
		if self.theChar=="Z":
			self.NextChar()
			zDirection,zHour,zMinute=0,0,0
			format='Z'
		elif self.theChar=="+" or self.theChar=="-":
			if self.theChar=="+":
				v1=+1
			else:
				v1=-1
			self.NextChar()
			v2=self.ParseDIGIT()
			v2=v2*10+self.ParseDIGIT()
			if IsDIGIT(self.theChar):
				v3=self.ParseDIGIT()
				v3=v3*10+self.ParseDIGIT()
				zDirection,zHour,zMinute=v1,v2,v3
				format="+hhmm"
			elif self.theChar==":":
				self.NextChar()
				v3=self.ParseDIGIT()
				v3=v3*10+self.ParseDIGIT()
				zDirection,zHour,zMinute=v1,v2,v3
				format="+hh:mm"
			else:
				zDirection,zHour,zMinute=v1,v2,None
				format="+hh"
		return zDirection,zHour,zMinute,format
	
	def ParseTime(self,t,tBase=None,tDesignator="T"):
		warnings.warn("ISO8601Parser.ParseTime is deprecated, use ParseTimeFormat instead", DeprecationWarning, stacklevel=2)		
		if self.theChar in tDesignators:
			self.NextChar()
			tDesignator=1
		else:
			tDesignator=0
		if IsDIGIT(self.theChar):
			v1=self.ParseDIGIT()
			v1=v1*10+self.ParseDIGIT()
			if IsDIGIT(self.theChar):
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v3=float(v3)+self.ParseFraction()
						t.SetTime(v1,v2,v3)
						tFormat="hhmmss%ss"%point
					else:
						t.SetTime(v1,v2,v3)
						tFormat="hhmmss"
				elif self.theChar=="." or self.theChar==",":
					point=self.theChar
					v2=float(v2)+self.ParseFraction()
					t.SetTime(v1,v2,None)
					tFormat="hhmm%sm"%point
				else:
					t.SetTime(v1,v2,None)
					tFormat="hhmm"
			elif self.theChar=="." or self.theChar==",":
				point=self.theChar
				v1=float(v1)+self.ParseFraction()
				t.SetTime(v1,None,None)
				tFormat="hh%sh"%point
			elif self.theChar==":":
				self.NextChar()
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if self.theChar==":":
					self.NextChar()
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v3=float(v3)+self.ParseFraction()
						t.SetTime(v1,v2,v3)
						tFormat="hh:mm:ss%ss"%point
					else:
						t.SetTime(v1,v2,v3)
						tFormat="hh:mm:ss"
				elif self.theChar=="," or self.theChar==".":
					point=self.theChar
					v2=float(v2)+self.ParseFraction()
					t.SetTime(v1,v2,None)
					tFormat="hh:mm%sm"%point
				else:
					t.SetTime(v1,v2,None)
					tFormat="hh:mm"
			else:
				t.SetTime(v1,None,None)
				tFormat="hh"
		elif self.theChar=="-":
			if tDesignator:
				self.SyntaxError("time designator before truncated time")
			self.NextChar()
			if IsDIGIT(self.theChar):
				v1=self.ParseDIGIT()
				v1=v1*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v2=float(v2)+self.ParseFraction()
						t.SetTime(None,v1,v2,tBase)
						tFormat="-mmss%ss"%point
					else:
						t.SetTime(None,v1,v2,tBase)
						tFormat="-mmss"
				elif self.theChar=="." or self.theChar==",":
					point=self.theChar
					v1=float(v1)+self.ParseFraction()
					t.SetTime(None,v1,None,tBase)
					tFormat="-mm%sm"%point
				elif self.theChar==":":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="." or self.theChar==",":
						point=self.theChar
						v2=float(v2)+self.ParseFraction()
						t.SetTime(None,v1,v2,tBase)
						tFormat="-mm:ss%ss"%point
					else:
						t.SetTime(None,v1,v2,tBase)
						tFormat="-mm:ss"
				else:
					t.SetTime(None,v1,None,tBase)
					tFormat="-mm"
			elif self.theChar=="-":
				self.NextChar()
				v1=self.ParseDIGIT()
				v1=v1*10+self.ParseDIGIT()
				if self.theChar=="." or self.theChar==",":
					point=self.theChar
					v1=float(v1)+self.ParseFraction()
					t.SetTime(None,None,v1,tBase)
					tFormat="--ss%ss"%point
				else:
					t.SetTime(None,None,v1,tBase)
					tFormat="--ss"
			else:
				self.SyntaxError("expected digit or hyphen in truncated Time")
			# truncated forms cannot don't take timezones, return early
			return tFormat
		else:
			self.SyntaxError("expected digit of hyphen in Time")
		if self.theChar is not None and self.theChar in "Z+-":
			tFormat+=self.ParseTimeZone(t)
			if not (BasicTimeFormats.get(tFormat) or ExtendedTimeFormats.get(tFormat)):
				raise DateTimeError("inconsistent use of extended/basic format in time zone")
		return tFormat
			
	def ParseTimeZone(self,t):
		if self.theChar=="Z":
			self.NextChar()
			t.SetZone(0)
			format='Z'
		elif self.theChar=="+" or self.theChar=="-":
			if self.theChar=="+":
				v1=+1
			else:
				v1=-1
			self.NextChar()
			v2=self.ParseDIGIT()
			v2=v2*10+self.ParseDIGIT()
			if IsDIGIT(self.theChar):
				v3=self.ParseDIGIT()
				v3=v3*10+self.ParseDIGIT()
				t.SetZone(v1,v2,v3)
				format="+hhmm"
			elif self.theChar==":":
				self.NextChar()
				v3=self.ParseDIGIT()
				v3=v3*10+self.ParseDIGIT()
				t.SetZone(v1,v2,v3)
				format="+hh:mm"
			else:
				t.SetZone(v1,v2,None)
				format="+hh"
		return format
	
	def ParseDurationValue(self,allowFraction=True):
		"""Returns a tuple of (value, formatString) or (None,None).
		
		formatString is one of "n", "n.n" or "n,n".
		
		If allowFraction is False then a fractional format raises an error."""
		value=self.ParseDIGITRepeat()
		if value is None:
			return None,None
		if self.theChar in ".,":
			if not allowFraction:
				raise DateTimeError("fractional component in duration must have lowest order")										
			format="n"+self.theChar+"n"			
			value=value+self.ParseFraction()
		else:
			format="n"
		return value,format
			
	def ParseDuration(self,d):
		if self.theChar!='P':
			raise DateTimeError("expected duration")
		format=['P']
		values=[]
		self.NextChar()
		allowFraction=True
		value,vFormat=self.ParseDurationValue(allowFraction)
		allowFraction=allowFraction and (value is None or vFormat=="n")
		if value is not None and self.theChar=="W":
			format.append(vFormat+"W")
			self.NextChar()
			d.SetWeekDuration(value)
			return string.join(format,'')
		if value is not None and self.theChar=='Y':
			format.append(vFormat+"Y")
			self.NextChar()
			values.append(value)
			value,vFormat=self.ParseDurationValue(allowFraction)
			allowFraction=allowFraction and (value is None or vFormat=="n")
		else:
			values.append(None)
		if value is not None and self.theChar=='M':
			format.append(vFormat+"M")
			self.NextChar()
			values.append(value)
			value,vFormat=self.ParseDurationValue(allowFraction)
			allowFraction=allowFraction and (value is None or vFormat=="n")
		else:
			values.append(None)
		if value is not None and self.theChar=='D':
			format.append(vFormat+"D")
			self.NextChar()
			values.append(value)
			value,vFormat=None,None
		else:
			values.append(None)
		if value is not None:
			raise DateTimeError("expected 'T', found %s"%str(value))
		if 	self.theChar=='T':
			format.append("T")
			self.NextChar()
			value,vFormat=self.ParseDurationValue(allowFraction)
			allowFraction=allowFraction and (value is None or vFormat=="n")
			if value is not None and self.theChar=='H':
				format.append(vFormat+"H")
				self.NextChar()
				values.append(value)
				value,vFormat=self.ParseDurationValue(allowFraction)
				allowFraction=allowFraction and (value is None or vFormat=="n")
			else:
				values.append(None)
			if value is not None and self.theChar=='M':
				format.append(vFormat+"M")
				self.NextChar()
				values.append(value)
				value,vFormat=self.ParseDurationValue(allowFraction)
				allowFraction=allowFraction and (value is None or vFormat=="n")
			else:
				values.append(None)
			if value is not None and self.theChar=='S':
				format.append(vFormat+"S")
				self.NextChar()
				values.append(value)
				value,vFormat=None,None
			else:
				values.append(None)
		else:
			values=values+[None,None,None]
		if value is not None:
			raise DateTimeError("expected end of duration, found %s"%str(value))
		if len(format)==1:
			# "P" not allowed
			raise DateTimeError("duration must have at least one component")
		elif format[-1]=="T":
			# "P...T" not allowed either
			raise DateTimeError("expected time component in duration")
		# Now deal with partial precision, higher order components default to 0
		defValue=None
		for i in xrange(5,-1,-1):
			# loop backwards through the values
			if values[i] is None:
				values[i]=defValue
			else:
				defValue=0
		format=string.join(format,'')
		years,months,days,hours,minutes,seconds=values
		d.SetCalendarDuration(years,months,days,hours,minutes,seconds)
		return format
									
	def ParseFraction(self):
		if not (self.theChar=="." or self.theChar==","):
			self.SyntaxError("expected decimal sign")
		self.NextChar()
		f=0L
		fMag=1L
		while IsDIGIT(self.theChar):
			f=f*10+self.ParseDIGIT()
			fMag*=10
		if fMag==1:
			self.SyntaxError("expected decimal digit")
		return float(f)/float(fMag)
	