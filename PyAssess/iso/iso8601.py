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
import string
from math import modf,floor
import time as pytime

from PyAssess.ietf.rfc2234 import RFC2234CoreParser, IsDIGIT

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
	"""Leapyear returns 1 if year is a leap year and 0 otherwise.  Note that leap years
	famously fall on all years that divide by 4 except those that divide by 100 but
	including those that divide by 400."""
	if year%4:
		return 0
	elif year%100:
		return 1
	elif year%400:
		return 0
	else:
		return 1

def DayOfWeek(year,month,day):
	"""DayOfWeek returns the day of week 1-7, 1 being Monday for the given year, month
	and day"""
	num=year*365
	num=num+year/4+1
	num=num-(year/100+1)
	num=num+year/400+1
	if month<3 and LeapYear(year):
		num=num-1
	return (num+MONTH_OFFSETS[month-1]+day+4)%7+1

def WeekCount(year):
	"""Week count returns the number of calendar weeks in a year.  Most years have 52
	weeks of course, but if the year begins on a Thursday or a leap year begins on a
	Wednesday then it has 53."""
	dow=DayOfWeek(year,1,1)
	if dow==4:
		return 53
	elif dow==3 and LeapYear(year):
		return 53
	else:
		return 52

def GetLocalZone():
	# returns the number of minutes ahead of UTC we are
	t=pytime.time()
	utcTuple=pytime.gmtime(t)
	utcTime,utcDate=Time(),Date()
	utcTime.SetTimeTuple(utcTuple)
	utcDate.SetTimeTuple(utcTuple)
	localTuple=pytime.localtime(t)
	localTime,localDate=Time(),Date()
	localTime.SetTimeTuple(localTuple)
	localDate.SetTimeTuple(localTuple)
	# Crude but effective, calculate the zone in force by comaring utc and local time
	if localDate==utcDate:
		zOffset=0
	elif localDate<utcDate:
		zOffset=-1440
	else:
		zOffset=1440
	zOffset+=int(localTime.GetSeconds()-utcTime.GetSeconds())/60
	return zOffset
			
class Date:
	"""A class for representing ISO dates"""
	
	def __init__(self,value=None,baseDate=None):
		if type(value) in (StringType,UnicodeType):
			self.SetFromString(value,baseDate)
		elif isinstance(value,Date):
			self.SetFromDate(value)
		elif value is None:
			self.SetOrigin()
		else:
			TypeError

	def SetOrigin(self):
		self.century=0
		self.year=self.month=self.day=1
		self.week=None
		
	def GetCalendarDay (self):
		return (self.century,self.year,self.month,self.day)
	
	def SetCalendarDay(self,century,year,month,day,baseDate=None):
		self.week=None
		if century is None:
			# Truncation level>=1
			if baseDate is None or not baseDate.Complete():
				raise DateTimeError("truncated date with no base")
			else:
				baseCentury,baseYear,baseMonth,baseDay=baseDate.GetCalendarDay()
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
							self.AddMonth()
				else:
					self.month=month
					self.day=day
					if self.month<baseMonth or (self.month==baseMonth and self.day<baseDay):
						self.AddYear()
			else:
				self.year=year
				self.month=month
				self.day=day
				if self.year<baseYear or (self.year==baseYear and
					(self.month<baseMonth or (self.month==baseMonth and self.day<baseDay))):
					self.AddCentury()
		else:
			self.century=century
			self.year=year
			self.month=month
			self.day=day
		self.CheckDate()
		
	def GetOrdinalDay(self):
		"""Returns a 3-tuple of century, year and ordinal day of year"""
		if self.day is None:
			if self.month is None and self.week is None:
				return (self.century,self.year,None)
			else:
				raise DateTimeError("can't get ordinal day with month or week precision")
		if LeapYear(self.century*100+self.year):
			mSizes=MONTH_SIZES_LEAPYEAR
		else:
			mSizes=MONTH_SIZES
		ordinalDay=self.day
		for m in mSizes[:self.month-1]:
			ordinalDay=ordinalDay+m
		return (self.century,self.year,ordinalDay)

	def SetOrdinalDay(self,century,year,ordinalDay,baseDate=None):
		if ordinalDay is None:
			self.SetCalendarDay(century,year,None,None,baseDate)
		else:
			self.week=None
			if century is None:
				if baseDate is None or not baseDate.Complete():
					raise DateTimeError("truncated date with no base")
				else:
					baseCentury,baseYear,baseOrdinalDay=baseDate.GetOrdinalDay()
				self.century=baseCentury
				if year is None:
					# Truncation level==2
					self.year=baseYear
					if ordinalDay is None:
						raise ValueError
					else:
						self.day=ordinalDay
						if self.day<baseOrdinalDay:
							self.AddYear()
				else:
					self.year=year
					self.day=ordinalDay
					if self.year<baseYear or (self.year==baseYear and self.day<baseOrdinalDay):
						self.AddCentury()
			else:
				self.century=century
				self.year=year
				self.day=ordinalDay
			if LeapYear(self.century*100+self.year):
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
			self.CheckDate()

	def GetWeekDay(self):
		"""Returns a 5-tuple of century, decade, year, week number, day-of-week (1==Monday, 7=Sunday)"""
		if self.day is None:
			if self.week:
				return (self.century,self.year/10,self.year%10,self.week,None)
			elif self.month is None:
				if self.year is None:
					return (self.century,None,None,None,None)
				else:
					return (self.century,self.year/10,self.year%10,None,None)
			else:
				raise DateTimeError("can't get week day with month precision")
		else:
			century,year,ordinalDay=self.GetOrdinalDay()
			year+=century*100
			if LeapYear(year):
				yearLength=366
			else:
				yearLength=365
			dow=DayOfWeek(year,self.month,self.day)
			thursday=ordinalDay+4-dow
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
				week=(ordinalDay-yearBase)/7+1
			return year/100,(year%100)/10,(year%10),week,dow

	def SetWeekDay (self,century,decade,year,week,day,baseDate=None):
		if day is None:
			if week is None:
				raise DateTimeError("can't set date with year precision or less with SetWeekDay")
		else:
			if day<0 or day>7:
				raise DateTimeError("weekday %i out of range"%day)
		if week is not None and (week<0 or week>53):
			raise DateTimeError("week %i out of range"%week)
		if year is not None and (year<0 or year>9):
			raise DateTimeError("year %i within decade is out of range")
		if decade is not None and (decade<0 or decade>9):
			raise DateTimeError("decade %i is out of range")
		self.month=None
		if century is None:
			# Truncation
			if baseDate is None or not baseDate.Complete():
				raise DateTimeError("truncated date with no base")
			else:
				baseCentury,baseDecade,baseYear,baseWeek,baseDay=baseDate.GetWeekDay()
				# adjust base precision
				if day is None:
					baseDay=None
			self.century=baseCentury
			if decade is None:
				if year is None:
					self.year=baseDecade*10+baseYear
					if week is None:
						self.week=baseWeek
						if day is None:
							raise ValueError
						else:
							self.day=day
							if self.day<baseDay:
								self.AddWeek()
					else:
						self.week=week
						self.day=day
						if self.week<baseWeek or (self.week==baseWeek and self.day<baseDay):
							self.AddYear()
				else:
					self.year=year
					self.week=week
					self.day=day
					if self.year<baseYear or (self.year==baseYear and (
						self.week<baseWeek or (self.week==baseWeek and self.day<baseDay))):
						self.year+=(baseDecade+1)*10
					else:
						self.year+=baseDecade*10
			else:
				self.year=decade*10+year
				self.week=week
				self.day=day
				baseYear+=baseDecade*10
				if self.year<baseYear or (self.year==baseYear and (
					self.week<baseWeek or (self.week==baseWeek and self.day<baseDay))):
					self.AddCentury()
		else:
			self.century=century
			self.year=decade*10+year
			self.week=week
			self.day=day
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
			self.century=year/100
			self.year=year%100
			self.week=None
		self.CheckDate()
				
	def GetTimeTuple (self,timeTuple):
		"""GetTimeTuple changes the year, month and date fields of timeTuple"""
		if not self.Complete():
			raise DateTimeError("GetTimeTuple requires complete date")
		timeTuple[0]=self.century*100+self.year
		timeTuple[1]=self.month
		timeTuple[2]=self.day
		
	def SetTimeTuple (self,timeTuple):
		self.century=timeTuple[0]/100
		self.year=timeTuple[0]%100
		self.month=timeTuple[1]
		self.day=timeTuple[2]
		self.CheckDate()
			
	def GetAbsoluteDay (self):
		"""Return a notional day number - with 1 being the 0001-01-01 which is the base day of our calendar."""
		if not self.Complete():
			raise DateTimeError("absolute day requires complete date")
		absYear=self.century*100+self.year-1
		return (absYear/4)-(absYear/100)+(absYear/400)+(absYear*365)+self.GetOrdinalDay()[2]
	
	def SetAbsoluteDay (self,absDay):
		quadCentury=146097	# 365*400+97 always holds
		century=36524		# 365*100+24 excludes centennial leap
		quadYear=1461		# 365*4+1    includes leap
		# Shift the base so that day 0 is 1st Jan 0001, makes the year calculation easier
		absDay=absDay-1
		# All quad centuries are equal
		absYear=400*(absDay/quadCentury)
		absDay=absDay%quadCentury
		# A quad century has one more day than 4 centuries because it ends in a leap year
		# We must check for this case specially to stop abother 4 complete centuries be added!
		if absDay==(quadCentury-1):
			absYear=absYear+399
			absDay=365
		else:
			absYear=absYear+100*(absDay/century)
			absDay=absDay%century
			# A century has one fewer days than 25 quad years so we are safe this time
			absYear=absYear+4*(absDay/quadYear)
			absDay=absDay%quadYear
			# However, a quad year has 1 more day than 4 years so we have a second special case
			if absDay==(quadYear-1):
				absYear=absYear+3
				absDay=365
			else:
				absYear=absYear+(absDay/365)
				absDay=absDay%365
		absYear=absYear+1
		# Finally, return the base so that 1 is the 1st of Jan for setting the ordinal
		self.SetOrdinalDay(absYear/100,absYear%100,absDay+1)

	def SetJulianDay(self,year,month,day):
		if year%4:
			mSizes=MONTH_SIZES
		else:
			mSizes=MONTH_SIZES_LEAPYEAR
		year-=1	
		for m in mSizes[:month-1]:
			day+=m
		self.SetAbsoluteDay((year/4)+(year*365)+day-2)

	def GetJulianDay(self):
		quadYear=1461		# 365*4+1    includes leap
		# Returns tuple of (year,month,day)
		day=self.GetAbsoluteDay()
		# 1st Jan 0001 Gregorian -> 3rd Jan 0001 Julian
		# We would add 2 but we want to shift the base so that day 0 is 1st Jan 0001 (Julian)
		# We add the second bit after the calculation is done
		day+=1
		year=4*(day/quadYear)
		day=day%quadYear
		# A quad year has 1 more day than 4 years
		if day==(quadYear-1):
			year+=3
			day=365
		else:
			year+=day/365
			day=day%365
		# correct for base year being 1...
		year+=1
		# and base day being being 1st
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

	NoTruncation=0
	CenturyTruncation=1
	DecadeTruncation=2
	YearTruncation=3
	MonthTruncation=4
	WeekTruncation=5
	
	def __str__(self):
		return self.GetCalendarString()
		
	def GetCalendarString(self,basic=0,truncation=0):
		if self.day is None:
			if self.month is None:
				if self.week:
					raise DateTimeError("can't get calendar string with week precision")
				if self.year is None:
					if self.century is None:
						raise DateTimeError("no date to format")
					else:
						if truncation==Date.NoTruncation:
							return "%02i"%self.century
						else:
							raise ValueError
				else:
					if truncation==Date.NoTruncation:
						return "%02i%02i"%(self.century,self.year)
					elif truncation==Date.CenturyTruncation:
						return "-%02i"%self.year
					else:
						raise ValueError
			else:
				if truncation==Date.NoTruncation:
					return "%02i%02i-%02i"%(self.century,self.year,self.month)
				elif truncation==Date.CenturyTruncation:
					if basic:
						return "-%02i%02i"%(self.year,self.month)
					else:
						return "-%02i-%02i"%(self.year,self.month)
				elif truncation==Date.YearTruncation:
					return "--%02i"%self.month
				else:
					raise ValueError
		else:
			if truncation==Date.NoTruncation:
				if basic:
					return "%02i%02i%02i%02i"%(self.century,self.year,self.month,self.day)
				else:
					return "%02i%02i-%02i-%02i"%(self.century,self.year,self.month,self.day)
			elif truncation==Date.CenturyTruncation:
				if basic:
					return "%02i%02i%02i"%(self.year,self.month,self.day)
				else:
					return "%02i-%02i-%02i"%(self.year,self.month,self.day)
			elif truncation==Date.YearTruncation:
				if basic:
					return "--%02i%02i"%(self.month,self.day)
				else:
					return "--%02i-%02i"%(self.month,self.day)
			elif truncation==Date.MonthTruncation:
				return "---%02i"%self.day
			else:
				raise ValueError
	
	def GetOrdinalString(self,basic=0,truncation=0):
		century,year,ordinalDay=self.GetOrdinalDay()
		if ordinalDay is None:
			# same as for calendar strings
			return self.GetCalendarString(basic,truncation)
		else:
			if truncation==Date.NoTruncation:
				if basic:
					return "%02i%02i%03i"%(century,year,ordinalDay)
				else:
					return "%02i%02i-%03i"%(century,year,ordinalDay)
			elif truncation==Date.CenturyTruncation:
				if basic:
					return "%02i%03i"%(year,ordinalDay)
				else:
					return "%02i-%03i"%(year,ordinalDay)
			elif truncation==Date.YearTruncation:
				return "-%03i"%ordinalDay
			else:
				raise ValueError
											
	def GetWeekString(self,basic=0,truncation=0):
		century,decade,year,week,day=self.GetWeekDay()
		if day is None:
			if week is None:
				# same as the calendar string
				return self.GetCalendarString(basic,truncation)
			else:
				if truncation==Date.NoTruncation:
					if basic:
						return "%02i%i%iW%02i"%(century,decade,year,week)
					else:
						return "%02i%i%i-W%02i"%(century,decade,year,week)
				elif truncation==Date.CenturyTruncation:
					if basic:
						return "%i%iW%02i"%(decade,year,week)
					else:
						return "%i%i-W%02i"%(decade,year,week)
				elif truncation==Date.DecadeTruncation:
					if basic:
						return "-%iW%02i"%(year,week)
					else:
						return "-%i-W%02i"%(year,week)
				elif truncation==Date.YearTruncation:
					return "-W%02i"%week
				else:
					raise ValueError							
		else:
			if truncation==Date.NoTruncation:
				if basic:
					return "%02i%i%iW%02i%i"%(century,decade,year,week,day)
				else:
					return "%02i%i%i-W%02i-%i"%(century,decade,year,week,day)
			elif truncation==Date.CenturyTruncation:
				if basic:
					return "%i%iW%02i%i"%(decade,year,week,day)
				else:
					return "%i%i-W%02i-%i"%(decade,year,week,day)
			elif truncation==Date.DecadeTruncation:
				if basic:
					return "-%iW%02i%i"%(year,week,day)
				else:
					return "-%i-W%02i-%i"%(year,week,day)	
			elif truncation==Date.YearTruncation:
				if basic:
					return "-W%02i%i"%(week,day)
				else:
					return "-W%02i-%i"%(week,day)	
			elif truncation==Date.WeekTruncation:
				return "-W-%i"%day
			else:
				raise ValueError

	def SetFromString(self,dateStr,baseDate=None):
		if type(dateStr) in StringTypes:
			p=ISO8601Parser(dateStr)
			return p.ParseDate(self,baseDate)
		else:
			raise TypeError

	def SetFromDate (self,src):
		self.century=src.century
		self.year=src.year
		self.month=src.month
		self.week=src.week
		self.day=src.day
		
	def CheckDate(self):
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

	def Complete (self):
		return self.century is not None and self.day is not None

	CenturyPrecision=1
	YearPrecision=2
	MonthPrecision=3
	WeekPrecision=4
	CompletePrecision=5
	
	def GetPrecision (self):
		if self.day is None:
			if self.month is None:
				if self.year is None:
					if self.century is None:
						return None
					else:
						return Date.CenturyPrecision
				elif self.week is None:
					return Date.YearPrecision
				else:
					return Date.WeekPrecision
			else:
				return Date.MonthPrecision
		else:
			return Date.CompletePrecision
		
	def __cmp__ (self,other):
		"""Date can hold imprecise dates, which raises the problem of comparisons
		between things such as January 1985 and Week 3 1985.  Although at first site it
		may be tempting to declare 1st April to be greater than March, it is harder to
		determine the relationship between 1st April and April itself.  Especially if
		a complete ordering is required."""
		if not isinstance(other,Date):
			other=Date(other)
		if self.GetPrecision()!=other.GetPrecision():
			raise ValueError(str(other))
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
												
	def AddCentury(self):
		if self.century>=99:
			raise ValueError				
		self.century+=1

	def AddYear(self):
		if self.year>=99:
			self.year=0
			self.AddCentury()
		else:
			self.year+=1
	
	def AddMonth(self):
		if self.month>=12:
			self.month=1
			self.AddYear()
		else:
			self.month+=1
	
	def AddWeek(self):
		if self.week>=WeekCount(self.century*100+self.year):
			self.week=1
			self.AddYear()
		else:
			self.week+=1
			
	def AddDays (self,days):
		if days:
			self.SetAbsoluteDay(self.GetAbsoluteDay()+days)

	def Now (self):
		self.SetTimeTuple(pytime.localtime(pytime.time()))
					

class Time:
	"""A class for representing ISO times"""

	def __init__(self,value=None,tBase=None):
		if type(value) in StringTypes:
			# The zone may be untouched by SetFromString
			self.zDirection=self.zOffset=None
			self.SetFromString(value,tBase)
		elif isinstance(value,Time):
			self.SetFromTime(value)
		elif value is None:
			self.SetOrigin()
		else:
			raise TypeError
				
	def SetOrigin(self):
		self.hour=self.minute=self.second=0
		self.zDirection=self.zOffset=None
	
	def GetTime (self):
		return self.hour,self.minute,self.second
		
	def SetTime(self,hour,minute,second,baseTime=None):
		overflow=0
		if hour is None:
			# Truncation of hour or more
			if baseTime is None or not baseTime.Complete():
				raise DateTimeError("truncated time with no base")
			else:
				baseHour,baseMinute,baseSecond=baseTime.GetTime()
				if second is None:
					baseSecond=None
					if minute is None:
						baseMinute=None
			self.hour=baseHour
			if minute is None:
				# Truncation of minutes
				self.minute=baseMinute
				if second is None:
					raise ValueError
				else:
					self.second=second
					if self.second<baseSecond:
						overflow=self.AddMinute()
			else:
				self.minute=minute
				self.second=second
				if self.minute<baseMinute or (self.minute==baseMinute and self.second<baseSecond):
					overflow=self.AddHour()
			# copy time zone from base
			self.zDirection=baseTime.zDirection
			self.zOffset=baseTime.zOffset
		else:
			self.hour=hour
			self.minute=minute
			self.second=second
		self.CheckTime()
		return overflow

	def GetZone(self):
		return self.zDirection,self.zOffset
	
	def SetZone(self,zDirection,hourOffset=None,minuteOffset=None):
		self.zDirection=zDirection
		if zDirection is None:
			self.zOffset=None
		elif zDirection==0:
			self.zOffset=0
		elif hourOffset is None:
			self.zOffset=None
		elif minuteOffset is None:
			self.zOffset=hourOffset*60
		else:
			self.zOffset=hourOffset*60+minuteOffset
		self.CheckZone()
		
	def GetTimeTuple(self,timeTuple):
		"""GetTimeTuple changes the hour, minute and second fields of timeTuple"""
		if not self.Complete():
			raise DateTimeError("GetTimeTuple require complete time")
		timeTuple[3]=self.hour
		timeTuple[4]=self.minute
		timeTuple[5]=self.second

	def SetTimeTuple (self,timeTuple):
		self.hour=timeTuple[3]
		self.minute=timeTuple[4]
		self.second=timeTuple[5]
		self.CheckTime()

	def SetFromTime(self,src):
		self.hour=src.hour
		self.minute=src.minute
		self.second=src.second
		self.zDirection=src.zDirection
		self.zOffset=src.zOffset
		
	NoTruncation=0
	HourTruncation=1
	MinuteTruncation=2
	
	def GetString(self,basic=0,truncation=0,ndp=0,zonePrecision=1):
		if self.second is None:
			if self.minute is None:
				if self.hour is None:
					raise DateTimeError("no time to format")
				else:
					if truncation==Time.NoTruncation:
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
				if truncation==Time.NoTruncation:
					if basic:
						stem="%02i%02i"%(self.hour,minute)
					else:
						stem="%02i:%02i"%(self.hour,minute)
				elif truncation==Time.HourTruncation:
					stem="-%02i"%minute
				else:
					raise ValueError
		else:
			if type(self.second) is FloatType:
				fraction,second=modf(self.second)
				second=int(second)
			else:
				fraction,second=0,self.second
			if truncation==Time.NoTruncation:
				if basic:
					stem="%02i%02i%02i"%(self.hour,self.minute,second)
				else:
					stem="%02i:%02i:%02i"%(self.hour,self.minute,second)
			elif truncation==Time.HourTruncation:
				if basic:
					stem="-%02i%02i"%(self.minute,second)
				else:
					stem="-%02i:%02i"%(self.minute,second)
			elif truncation==Time.MinuteTruncation:
				stem="--%02i"%second
		if ndp:
			# to prevent truncation being caught out by sloppy machine rounding
			# we add a small time to the fraction (at most 1ns and typically less)
			if ndp>0:
				fractionStr="%s,%0*i"
			else:
				fractionStr="%s.%0*i"
				ndp=-ndp
			fraction+=2e-13
			fraction=int(floor(fraction*float(10L**ndp)))
			stem=fractionStr%(stem,ndp,fraction)
		if truncation==Time.NoTruncation:
			# untruncated forms can have a zone string
			stem+=self.GetZoneString(basic,zonePrecision)
		return stem
				
	def SetFromString(self,timeStr,baseTime=None):
		if type(timeStr) in StringTypes:
			p=ISO8601Parser(timeStr)
			return p.ParseTime(self,baseTime)
		else:
			raise TypeError
			
	ZoneFullPrecision=1
	ZoneHourPrecision=0

	def GetZoneString(self,basic=0,zonePrecision=1):
		if self.zDirection is None:
			return ""
		elif self.zDirection==0:
			return "Z"
		else:
			if self.zDirection>0:
				zStr="+"
			else:
				zStr="-"
			hour=self.zOffset/60
			minute=self.zOffset%60
			if zonePrecision==Time.ZoneFullPrecision or minute>0:
				if basic:
					return "%s%02i%02i"%(zStr,hour,minute)
				else:
					return "%s%02i:%02i"%(zStr,hour,minute)
			else:	
				if basic:
					return "%s%02i"%(zStr,hour)
				else:
					return "%s%02i"%(zStr,hour)

	def SetZoneFromString(self,zoneStr):
		if type(zoneStr) in StringTypes:
			p=ISO8601Parser(zoneStr)
			return p.ParseTimeZone(self)
		else:
			raise TypeError

	def CheckTime(self):
		self.CheckZone()
		if self.hour is None:
			raise DateTimeError("missing time")
		if self.hour<0 or self.hour>24:
			raise DateTimeError("hour out of range %i"%self.hour)
		if self.hour==24 and (self.minute>0 or self.second>0):
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
	
	def CheckZone(self):
		if self.zDirection is not None:
			if self.zDirection<-1 or self.zDirection>+1:
				raise DateTimeError("zone direction out of range %i"%self.zDirection)
			if self.zDirection!=0:
				if self.zOffset is None:
					raise DateTimeError("missing zone offset")
				elif self.zOffset>=1440:
					raise DateTimeError("zone offset out of range %i:%02i"%(self.zOffset/60,self.zOffset%60))

	def Complete(self):
		return self.hour is not None and self.minute is not None and self.second is not None
		
	def Now (self):
		self.SetTimeTuple(pytime.localtime(pytime.time()))
	
	HourPrecision=1
	MinutePrecision=2
	CompletePrecision=3
	
	def GetPrecision (self):
		if self.second is None:
			if self.minute is None:
				if self.hour is None:
					return None
				else:
					return Time.HourPrecision
			else:
				return Time.MinutePrecision
		else:
			return Time.CompletePrecision

	def SetPrecision(self,precision,truncate=0):
		if precision==Time.CompletePrecision:
			if self.second is None:
				if self.minute is None:
					if self.hour is None:
						self.hour=0
						self.minute=0
					elif type(self.hour) is FloatType:
						self.minute,self.hour=modf(self.hour)
						self.minute*=60.0
						self.hour=int(self.hour)
					else:
						self.minute=0
				if type(self.minute) is FloatType:
					self.second,self.minute=modf(self.minute)
					self.second*=60.0
					self.minute=int(self.minute)
				else:
					self.second=0
			if truncate and type(self.second) is FloatType:
				self.second=int(floor(self.second))
		elif precision==Time.MinutePrecision:
			if self.second is None:
				if self.minute is None:
					if self.hour is None:
						self.hour=0
						self.minute=0
					elif type(self.hour) is FloatType:
						self.minute,self.hour=modf(self.hour)
						self.minute*=60.0
						self.hour=int(self.hour)
					else:
						self.minute=0
				if truncate and type(self.minute) is FloatType:
					self.minute=int(floor(self.minute))
			elif truncate:
				self.second=None
			else:
				self.minute=float(self.minute)+self.second/60.0
				self.second=None
		elif precision==Time.HourPrecision:
			if self.second is None:
				if self.minute is None:
					if self.hour is None:
						self.hour=0
					elif truncate and type(self.hour) is FloatType:
						self.hour=int(floor(self.hour))
				elif truncate:
					self.minute=None
				else:
					self.hour=float(self.hour)+self.minute/60.0
					self.minute=None
			elif truncate:
				self.minute=self.second=None
			else:
				self.hour=float(self.hour)+self.minute/60.0+self.second/3600.0
				self.minute=self.second=None
		else:
			raise ValueError

				
	def __cmp__ (self,other):
		"""Time can hold partially specified times, we deal with comparisons in a similar
		way to Date.__cmp__.  Although this behaviour is consistent it might seem strange
		at first as it rules out comparing 09:00:15 with 09:00.  Recall though that 09:00 is
		actually all times in the range [09:00:00-09:00:59] if this behaviour seems strange.
		The SetPrecision method should be used to reduce precision to the lowest common
		denominator before ordering times of mixed precision.  In some circumstances it may
		be appropriate to extend the precision in a context where 09:00 means 09:00:00 or
		to use decimization when reducing precision causing 09:00:15 to become 09:00,25 which
		will sort as expected - treating 09:00 as 09:00,0 automatically.
		Zones further complicate this method but the rule is very simple, we only ever compare
		times from the same zone, but we will convert the other time to the zone of this
		time if we can.  We can never compare times with unspecified zones with those with
		specified ones"""
		if not isinstance(other,Time):
			other=Time(other)
		if self.GetPrecision()!=other.GetPrecision():
			raise ValueError(str(other))
		if type(self.zDirection)!=type(other.zDirection):
			raise ValueError(str(other))
		if self.zDirection is not None:
			z=self.zDirection*self.zOffset
			zOther=other.zDirection*other.zOffset
			if z!=zOther:
				# we need to change the timezone of 'other'
				other=Time(other)
				overflow=other.ChangeZone(z-zOther)
				if overflow:
					return -overflow
		result=cmp(self.hour,other.hour)
		if not result:
			result=cmp(self.minute,other.minute)
			if not result:
				result=cmp(self.second,other.second)
		return result

	def ChangeZone(self,zChange):
		# even if / and % are defined differently from what you expect
		# we know that they are consistent so can proceed like this
		zHours=zChange/60
		zMinutes=zChange%60
		if self.second is None:
			if self.minute is None:
				# hour precision only - zMinutes better be a whole number of hours
				if zMinutes:
					raise DateTimeError("fractional zone change requires at least minute precision")
		if zMinutes:
			self.minute+=zMinutes
			if self.minute>59:
				zHours+=1
				self.minute-=60
			elif self.minute<0:
				zHours-=1
				self.minute+=60
		if zHours:
			self.hour+=zHours
			if self.hour<0:
				self.hour+=24
				overflow=-1
			elif self.hour>23:
				self.hour-=24
				overflow=1
			else:
				overflow=0
		else:
			overflow=0
		# Now update the zone if it is specified
		if zChange and self.zDirection is not None:
			self.zOffset=(self.zDirection*self.zOffset)+zChange
			if self.zOffset<0:
				self.zOffset=-self.zOffset
				self.zDirection=-1
			else:
				self.zDirection=1
		self.CheckTime()
		return overflow
			
	def GetSeconds (self):
		"""Note that leap seconds and midnight ensure that t.SetSeconds(t.GetSeconds()) is in
		no way an identity transformation on complete times."""
		if not self.Complete():
			raise DateTimeError("GetSeconds requires complete precision")
		if self.second==60:
			return 59+self.minute*60+self.hour*3600
		else:
			return self.second+self.minute*60+self.hour*3600
	
	def SetSeconds (self,s):
		"""Set a fully-specified time based on s seconds past midnight.  If s is greater
		than or equal to the number of seconds in a normal day then the number of whole days
		represented is returned and the time is set to the fractional part of the day, otherwise
		0 is returned.  Negative numbers underflow (and return negative numbers of days"""
		overflow=0
		if type(s) is FloatType:
			sFloor=floor(s)
			sFraction=s-sFloor
			s=int(sFloor)
		else:
			sFraction=None
		# python's div and mod make this calculation easy, s will always be +ve
		# and overflow will always be floored
		overflow=s/86400
		s=s%86400
		self.hour=s/3600
		self.minute=(s%3600)/60
		if sFraction is None:
			self.second=s%60
		else:
			self.second=(s%60)+sFraction
		self.CheckTime()	
		return overflow
	
	def AddHour(self):
		if self.hour>=23:
			self.hour=0
			return 1
		else:
			self.hour+=1
		 
	def AddMinute(self):
		if self.minute>=59:
			self.minute=0
			return self.AddHour()
		else:
			self.minute+=1
	
	def AddSeconds (self,s):
		self.SetSeconds(self.GetSeconds()+s)


class TimePoint:
	"""A class for representing ISO timepoints"""

	def __init__(self,arg=None,baseDate=None):
		if type(arg) in StringTypes:
			self.SetOrigin()
			self.SetFromString(arg,baseDate)
		elif isinstance(arg,TimePoint):
			self.SetFromTimePoint(arg)
		elif arg is None:
			self.SetOrigin()
		else:
			raise TypeError
				
	def SetOrigin (self):
		self.date=Date()
		self.time=Time()

	def GetCalendarTimePoint (self):
		return self.date.GetCalendarDay()+self.time.GetTime()
		
	def SetCalendarTimePoint(self,century,year,month,day,hour,minute,second,baseDate=None):
		self.date.SetCalendarDay(century,year,ordinalDay,baseDate)
		self.time.SetTime(hour,minute,second)
		self.CheckTimePoint()
	
	def GetOrdinalTimePoint(self):
		return self.date.GetOrdinalDay()+self.time.GetTime()
		
	def SetOrdinalTimePoint(self,century,year,ordinalDay,hour,minute,second,baseDate=None):
		self.date.SetOrdinalDay(century,year,ordinalDay,baseDate)
		self.time.SetTime(hour,minute,second)
		self.CheckTimePoint()
		
	def GetWeekDay(self):
		return self.date.GetWeekDay()+self.time.GetTime()
		
	def SetWeekTimePoint (self,century,decade,year,week,day,hour,minute,second,baseDate=None):
		self.date.SetWeekDay(century,decade,year,week,day,baseDate)
		self.time.SetTime(hour,minute,second)
		self.CheckTimePoint()
	
	def GetZone(self):
		return self.time.GetZone()
	
	def SetZone(self,zDirection,hourOffset=None,minuteOffset=None):
		self.time.SetZone()
		
	def SetFromTimePoint(self,src):
		self.date=Date(src.date)
		self.time=Time(src.time)
	
	def GetTimeTuple (self,timeTuple):
		self.date.GetTimeTuple(timeTuple)
		self.time.GetTimeTuple(timeTuple)
	
	def SetTimeTuple (self,timeTuple):
		self.date.SetTimeTuple(timeTuple)
		self.time.SetTimeTuple(timeTuple)

	def GetCalendarString(self,basic=0,truncation=0,ndp=0,zonePrecision=1):
		return self.date.GetCalendarString(basic,truncation)+'T'+\
			self.time.GetString(basic,Time.NoTruncation,ndp,zonePrecision)
		
	def GetOrdinalString(self,basic=0,truncation=0,ndp=0,zonePrecision=1):
		return self.date.GetOrdinalString(basic,truncation)+'T'+\
			self.time.GetString(basic,Time.NoTruncation,ndp,zonePrecision)
		
	def GetWeekString(self,basic=0,truncation=0,ndp=0,zonePrecision=1):
		return self.date.GetWeekString(basic,truncation)+'T'+\
			self.time.GetString(basic,Time.NoTruncation,ndp,zonePrecision)
		
	def SetFromString(self,timePointStr,baseDate=None):
		if type(timePointStr) in StringTypes:
			p=ISO8601Parser(timePointStr)
			return p.ParseTimePoint(self,baseDate)
		else:
			raise TypeError
			
	def SetUnixTime (self,unixTime):
		utcTuple=pytime.gmtime(0)
		self.date.SetTimeTuple(utcTuple)
		self.time.SetTimeTuple(utcTuple)
		self.time.SetZone(0)
		self.date.AddDays(self.time.AddSeconds(unixTime))
				
	def Complete (self):
		return self.date.Complete() and self.time.Complete()

	def Now (self):
		t=pytime.time()
		localTuple=time.localtime(t)
		self.date.SetTimeTuple(localTuple)
		self.time.SetTimeTuple(localTuple)
	
	def NowUTC(self):
		t=pytime.time()
		utcTuple=pytime.gmtime(t)
		self.date.SetTimeTuple(utcTuple)
		self.time.SetTimeTuple(utcTuple)
		self.time.SetZone(0)
		
	def GetPrecision (self):
		return self.time.GetPrecision()
	
	def SetPrecision(self,precision,truncate=0):
		self.time.SetPrecision(precision,truncate)
		
	def CheckTimePoint(self):
		self.CheckDate()
		self.CheckTime()
		if self.date.GetPrecision()!=Date.CompletePrecision:
			raise DateTimeError("timepoint requires complete precision for date")
	
	def __cmp__ (self,other):
		if not isinstance(other,TimePoint):
			other=TimePoint(other)
		# we need to follow the rules for comparing times
		if self.time.GetPrecision()!=other.time.GetPrecision():
			raise ValueError(str(other))
		zDirection1,zOffset1=self.time.GetZone()
		zDirection2,zOffset2=other.time.GetZone()
		if type(zDirection1)!=type(zDirection2):
			# must either both have zones, or neither have zones
			raise ValueError
		if zDirection1 is not None:
			z,zOther=zDirection1*zOffset1,zDirection2*zOffset2
			if z!=zOther:
				# we need to change the timezone of 'other', copy it first
				other=TimePoint(other)
				other.ChangeZone(z-zOther)
		result=cmp(self.date,other.date)
		if not result:
			result=cmp(self.time,other.time)
		return result
			
	def ChangeZone(self,zChange):
		overflow=self.time.ChangeZone(zChange)
		if overflow:
			self.date.AddDays(overflow)


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

	def ParseTimePoint(self,timePoint,baseDate=None):
		dateFormat=self.ParseDate(timePoint.date,baseDate)
		if not timePoint.date.Complete():
			raise DateTimeError("incomplete date in time point")
		if self.theChar!="T":
			raise DateTimeError("time-point requires time")
	
		timeFormat=self.ParseTime(timePoint.time)
		# check that dateFormat and timeFormat are compatible, i.e., both either basic or extended
		if not ((ExtendedTimeFormats.get(timeFormat) and ExtendedDateFormats.get(dateFormat)) or
			(BasicTimeFormats.get(timeFormat) and BasicDateFormats.get(dateFormat))):
			raise DateTimeError("inconsistent use of basic/extended form in time point %s%s%s"%(dateFormat,'T',timeFormat))
		return dateFormat+'T'+timeFormat
				
	def ParseDate(self,date,baseDate=None):
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
								date.SetCalendarDay(v1,v2,v3,v4,baseDate)
								return "YYYYMMDD"
							else:
								date.SetOrdinalDay(v1,v2,v3*10+v4,baseDate)
								return "YYYYDDD"
						else:
							date.SetCalendarDay(None,v1,v2,v3,baseDate)
							return "YYMMDD"
					else:
						date.SetOrdinalDay(None,v1,v2*10+v3,baseDate)
						return "YYDDD"
				elif self.theChar=="-":
					self.NextChar()
					if IsDIGIT(self.theChar):
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						if IsDIGIT(self.theChar):
							v3=v3*10+self.ParseDIGIT()
							date.SetOrdinalDay(v1,v2,v3,baseDate)
							return "YYYY-DDD"
						elif self.theChar=="-":
							self.NextChar()
							v4=self.ParseDIGIT()
							v4=v4*10+self.ParseDIGIT()
							date.SetCalendarDay(v1,v2,v3,v4,baseDate)
							return "YYYY-MM-DD"
						else:
							date.SetCalendarDay(v1,v2,v3,None,baseDate)
							return "YYYY-MM"
					elif self.theChar=="W":
						self.NextChar()
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						if self.theChar=="-":
							self.NextChar()
							v4=self.ParseDIGIT()
							date.SetWeekDay(v1,v2/10,v2%10,v3,v4,baseDate)
							return "YYYY-Www-D"
						else:
							date.SetWeekDay(v1,v2/10,v2%10,v3,None,baseDate)
							return "YYYY-Www"
					else:
						self.SyntaxError("expected digit or W in ISO date")
				elif self.theChar=="W":
					self.NextChar()
					v3=self.ParseDIGIT()
					v3=v3*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v4=self.ParseDIGIT()
						date.SetWeekDay(v1,v2/10,v2%10,v3,v4,baseDate)
						return "YYYYWwwD"
					else:
						date.SetWeekDay(v1,v2/10,v2%10,v3,None,baseDate)
						return "YYYYWww"""
				else:
					date.SetCalendarDay(v1,v2,None,None,baseDate)
					return "YYYY"
			elif self.theChar=="-":
				self.NextChar()
				if IsDIGIT(self.theChar):
					"""YY-DDD, YY-MM-DD"""
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=v2*10+self.ParseDIGIT()
						date.SetOrdinalDay(None,v1,v2,baseDate)
						return "YY-DDD"
					elif self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						v3=v3*10+self.ParseDIGIT()
						date.SetCalendarDay(None,v1,v2,v3,baseDate)
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
						date.SetWeekDay(None,v1/10,v1%10,v2,v3,baseDate)
						return "YY-Www-D"
					else:
						date.SetWeekDay(None,v1/10,v1%10,v2,None,baseDate)
						return "YY-Www"
				else:
					self.SyntaxError("expected digit or W in ISO date")
			elif self.theChar=="W":
				self.NextChar()
				v2=self.ParseDIGIT()
				v2=v2*10+self.ParseDIGIT()
				if IsDIGIT(self.theChar):
					v3=self.ParseDIGIT()
					date.SetWeekDay(None,v1/10,v1%10,v2,v3,baseDate)
					return "YYWwwD"
				else:
					date.SetWeekDay(None,v1/10,v1%10,v2,None,baseDate)
					return "YYWww"			
			else:
				date.SetCalendarDay(v1,None,None,None,baseDate)
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
							date.SetCalendarDay(None,v1,v2,None,baseDate)
							return "-YYMM"
						else:
							date.SetOrdinalDay(None,None,v1*10+v2,baseDate)
							return "-DDD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						date.SetCalendarDay(None,v1,v2,None,baseDate)
						return "-YY-MM"
					else:
						date.SetCalendarDay(None,v1,None,None,baseDate)
						return "-YY"
				elif self.theChar=="-":
					self.NextChar()
					self.ParseTerminal("W")
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if self.theChar=="-":
						self.NextChar()
						v3=self.ParseDIGIT()
						date.SetWeekDay(None,None,v1,v2,v3,baseDate)
						return "-Y-Www-D"
					else:
						date.SetWeekDay(None,None,v1,v2,None,baseDate)
						return "-Y-Www"
				elif self.theChar=="W":
					self.NextChar()
					v2=self.ParseDIGIT()
					v2=v2*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v3=self.ParseDIGIT()
						date.SetWeekDay(None,None,v1,v2,v3,baseDate)
						return "-YWwwD"
					else:
						date.SetWeekDay(None,None,v1,v2,None,baseDate)
						return "-YWww"
			elif self.theChar=="-":
				self.NextChar()
				if IsDIGIT(self.theChar):
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					if IsDIGIT(self.theChar):
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						date.SetCalendarDay(None,None,v1,v2,baseDate)
						return "--MMDD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						v2=v2*10+self.ParseDIGIT()
						date.SetCalendarDay(None,None,v1,v2,baseDate)
						return "--MM-DD"
					else:
						date.SetCalendarDay(None,None,v1,None,baseDate)
						return "--MM"
				elif self.theChar=="-":
					self.NextChar()
					v1=self.ParseDIGIT()
					v1=v1*10+self.ParseDIGIT()
					date.SetCalendarDay(None,None,None,v1,baseDate)
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
						date.SetWeekDay(None,None,None,v1,v2,baseDate)
						return "-WwwD"
					elif self.theChar=="-":
						self.NextChar()
						v2=self.ParseDIGIT()
						date.SetWeekDay(None,None,None,v1,v2,baseDate)
						return "-Www-D"
					else:
						date.SetWeekDay(None,None,None,v1,None,baseDate)
						return "-Www"
				elif self.theChar=="-":
					self.NextChar()
					v1=self.ParseDIGIT()
					date.SetWeekDay(None,None,None,None,v1,baseDate)
					return "-W-D"
				else:
					self.SyntaxError("expected digit or hyphen in truncated ISO date")
			else:
				self.SyntaxError("expected digit, hyphen or W in truncated ISO date")
		else:
			self.SyntaxError("expected digit or hyphen in ISO date")
	
	def ParseTime(self,t,tBase=None):
		if self.theChar=="T":
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
	
	def ParseDuration(self,d):
		if self.theChar!='P':
			raise DateTimeError("expected duration")
		format='P'
		self.NextChar()
		needValue=1
		value=None
		weekFlag=0
		if self.theChar=="T":
			# straight into time components
			self.NextChar()
			values=[0,0,0]
			fields="HMS"
			format="PT"
		else:
			values=[]
			fields="YMDHMS"
		for c in fields:
			if value is None:
				value=self.ParseDIGITRepeat()
				if value is None:
					# end of the duration
					if needValue:
						raise DateTimeError("expected number in duration")
					else:
						break
				else:
					needValue=0
			if self.theChar in ".,":
				fractionFormat=self.theChar+"n"
				value=value+self.ParseFraction()
			else:
				fractionFormat=''
			if self.theChar==c:
				self.NextChar()
				values.append(value)
				format+="n"+fractionFormat+c
				value=None
				if c=='D':
					# the next value must be preceded by 'T'
					if self.theChar=="T":
						self.NextChar()
						# 'T' must be followed by a value
						needValue=1
						format+='T'
					else:
						break
			elif self.theChar=='W' and c=="Y":
				# this is a week duration instead
				values.append(value)
				format+="n"+fractionFormat+c
				weekFlag=1
				break
			else:
				values.append(0)
				continue
		if value is not None:
			raise DateTimeError("unrecognized units in duration")
		for i in range(len(values)-1):
			if type(values[i]) is FloatType:
				raise DateTimeError("decimal fraction must be least significant part of duration")
		if weekFlag:
			d.SetWeekDuration(values[0])
		else:
			while len(values)<6:
				values.append(None)
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
	