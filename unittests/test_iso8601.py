#! /usr/bin/env python

"""Runs unit tests on the pyslet.iso8601 module"""

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(DateTests),
		unittest.makeSuite(TimeTests),
		unittest.makeSuite(ParserTests),
		unittest.makeSuite(TimePointTests),
		unittest.makeSuite(DurationTests)
		))

from pyslet.iso8601 import *

class DateTests(unittest.TestCase):
	def setUp(self):
		pass
	
	def testConstructor(self):
		date=Date()
		self.assertTrue(date.GetCalendarDay()==(0,1,1,1),"empty constructor results in the origin")
		base=Date(century=19,year=69,month=7,day=20)
		self.assertTrue(base.GetCalendarDay()==(19,69,7,20),"explicit constructor")
		date=Date(base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"copy constructor")
		date=Date(src=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"copy constructor, named parameter")
		date=Date.FromString("19690720")
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"string constructor")
		date=Date.FromString(u"1969-07-20")
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"unicode constructor")
		date=Date.FromString("--0720",base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"truncated year")

	def testCalendarDay(self):
		"""Test Get and Set Calendar day"""
		date=Date()
		base=Date()
		baseOverflow=Date()
		base=Date(century=19,year=69,month=7,day=20)
		baseOverflow=Date(century=19,year=69,month=7,day=21)
		date=Date(century=19,year=69,month=7,day=20)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"simple case")
		try:
			date=Date(year=69,month=7,day=20)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		date=Date(year=69,month=7,day=20,base=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"truncated century")
		date=Date(year=69,month=7,day=20,base=baseOverflow)
		self.assertTrue(date.GetCalendarDay()==(20,69,7,20),"truncated century with overflow")
		date=Date(month=7,day=20,base=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"truncated year")
		date=Date(month=7,day=20,base=baseOverflow)
		self.assertTrue(date.GetCalendarDay()==(19,70,7,20),"truncated year with overflow")
		date=Date(day=20,base=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"truncated month")
		date=Date(day=20,base=baseOverflow)
		self.assertTrue(date.GetCalendarDay()==(19,69,8,20),"truncated month with overflow")
		date=Date(century=19,year=69,month=7)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,None),"month precision")
		date=Date(century=19,year=69)
		self.assertTrue(date.GetCalendarDay()==(19,69,None,None),"year precision")
		date=Date(century=19)
		self.assertTrue(date.GetCalendarDay()==(19,None,None,None),"century precision")
		baseOverflow=Date(century=19,year=69,month=8,day=1)
		date=Date(year=69,month=7,base=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,None),"month precision, truncated century")
		date=Date(year=69,month=7,base=baseOverflow)
		self.assertTrue(date.GetCalendarDay()==(20,69,7,None),"month precision, truncated century with overflow")
		date=Date(month=7,base=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,7,None),"month precision, truncated year")
		date=Date(month=7,base=baseOverflow)
		self.assertTrue(date.GetCalendarDay()==(19,70,7,None),"month precision, truncated year with overflow")
		baseOverflow=Date(century=19,year=69,month=1,day=1)
		date=Date(year=69,base=base)
		self.assertTrue(date.GetCalendarDay()==(19,69,None,None),"year precision, truncated century")
		date=Date(year=68,base=baseOverflow)
		self.assertTrue(date.GetCalendarDay()==(20,68,None,None),"year precision, truncated century with overflow")
		try:
			date=Date(century=100,year=69,month=7,day=20)
			self.fail("bad century")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,year=100,month=7,day=20)
			self.fail("bad year")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,year=69,month=13,day=20)
			self.fail("bad month")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,year=0,month=2,day=29)
			self.fail("bad day")
		except DateTimeError:
			pass
		
	def testOrdinalDay(self):
		"""Test Get and Set Ordinal day"""
		date=Date()
		base=Date()
		baseOverflow=Date()
		base=Date(century=19,year=69,month=7,day=20)
		baseOverflow=Date(century=19,year=69,month=7,day=21)
		date=Date(century=19,year=69,ordinalDay=201)
		self.assertTrue(date.GetOrdinalDay()==(19,69,201),"simple case ")
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"calendar cross check")
		date=Date(century=19,year=69,ordinalDay=1)
		self.assertTrue(date.GetCalendarDay()==(19,69,1,1),"calendar cross check Jan 1st")
		date=Date(century=19,year=68,ordinalDay=366)
		self.assertTrue(date.GetCalendarDay()==(19,68,12,31),"calendar cross check Dec 31st (leap)")
		date=Date(century=19,year=69,ordinalDay=365)
		self.assertTrue(date.GetCalendarDay()==(19,69,12,31),"calendar cross check Dec 31st (non-leap)")
		try:
			date=Date(year=69,ordinalDay=201)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		date=Date(year=69,ordinalDay=201,base=base)
		self.assertTrue(date.GetOrdinalDay()==(19,69,201),"truncated century")
		date=Date(year=69,ordinalDay=201,base=baseOverflow)
		self.assertTrue(date.GetOrdinalDay()==(20,69,201),"truncated century with overflow")
		date=Date(ordinalDay=201,base=base)
		self.assertTrue(date.GetOrdinalDay()==(19,69,201),"truncated year")
		date=Date(ordinalDay=201,base=baseOverflow)
		self.assertTrue(date.GetOrdinalDay()==(19,70,201),"truncated year with overflow")
		date=Date(century=19,decade=6,year=9,week=29)
		try:
			date.GetOrdinalDay()
			self.fail("ordinal day with week precision")
		except DateTimeError:
			pass
		date=Date(century=19,year=69,month=7)
		try:
			date.GetOrdinalDay()
			self.fail("ordinal day with month precision")
		except DateTimeError:
			pass	
		date=Date(century=19,year=69)
		self.assertTrue(date.GetOrdinalDay()==(19,69,None),"year precision")
		date=Date(century=19)
		self.assertTrue(date.GetOrdinalDay()==(19,None,None),"century precision")
		baseOverflow=Date(century=19,year=69,month=1,day=1)
		date=Date(year=69,base=base)
		self.assertTrue(date.GetOrdinalDay()==(19,69,None),"year precision, truncated century")
		date=Date(year=68,base=baseOverflow)
		self.assertTrue(date.GetOrdinalDay()==(20,68,None),"year precision, truncated century with overflow")
		try:
			date=Date(century=100,year=69,ordinalDay=201)
			self.fail("bad century")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,year=100,ordinalDay=201)
			self.fail("bad year")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,year=68,ordinalDay=367)
			self.fail("bad ordinal - leap")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,year=69,ordinalDay=366)
			self.fail("bad ordinal - non-leap")
		except DateTimeError:
			pass

	def testWeekDay(self):
		"""Test Get and Set Week day"""
		date=Date()
		base=Date(century=19,year=69,month=7,day=20)
		baseOverflow=Date(century=19,year=69,month=7,day=21)
		date=Date(century=19,decade=6,year=9,week=29,weekday=7)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,7),"simple case")
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"calendar cross check")
		date=Date(century=19,decade=6,year=9,week=1,weekday=1)
		self.assertTrue(date.GetCalendarDay()==(19,68,12,30),"calendar cross check underflow")
		date=Date(century=19,decade=7,year=0,week=53,weekday=5)
		self.assertTrue(date.GetCalendarDay()==(19,71,1,1),"calendar cross check overflow")
		try:
			date=Date(decade=6,year=9,week=29,weekday=7)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		date=Date(decade=6,year=9,week=29,weekday=7,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,7),"truncated century")
		date=Date(decade=6,year=9,week=29,weekday=7,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(20,6,9,29,7),"truncated century with overflow")
		date=Date(year=9,week=29,weekday=7,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,7),"truncated decade")
		date=Date(year=9,week=29,weekday=7,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(19,7,9,29,7),"truncated decade with overflow")
		date=Date(week=29,weekday=7,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,7),"truncated year")
		date=Date(week=29,weekday=7,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(19,7,0,29,7),"truncated year with overflow")
		date=Date(weekday=7,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,7),"truncated week")
		date=Date(weekday=1,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(19,6,9,30,1),"truncated week with overflow")		
		date=Date(century=19,decade=6,year=9,week=29)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,None),"week precision")
		date=Date(century=19,year=69,month=7)
		try:
			date.GetWeekDay()
			self.fail("month precision")			
		except DateTimeError:
			pass
		try:
			date=Date(century=19,decade=6,year=9)
			self.fail("year precision")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,decade=6)
			self.fail("decade precision")
		except DateTimeError:
			pass
		baseOverflow=Date(century=19,decade=6,year=9,week=30,weekday=1)
		date=Date(decade=6,year=9,week=29,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,None),"week precision, truncated century")
		date=Date(decade=6,year=9,week=29,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(20,6,9,29,None),"week precision, truncated century with overflow")
		date=Date(year=9,week=29,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,None),"week precision, truncated decade")
		date=Date(year=9,week=29,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(19,7,9,29,None),"week precision, truncated decade with overflow")
		date=Date(week=29,base=base)
		self.assertTrue(date.GetWeekDay()==(19,6,9,29,None),"week precision, truncated year")
		date=Date(week=29,base=baseOverflow)
		self.assertTrue(date.GetWeekDay()==(19,7,0,29,None),"week precision, truncated year with overflow")
		try:
			date=Date(decade=6,year=9,base=base)
			self.fail("year precision, truncated century")
		except DateTimeError:
			pass
		try:
			date=Date(decade=6,base=base)
			self.fail("decade precision, truncated century")
		except DateTimeError:
			pass
		try:
			date=Date(century=100,decade=6,year=9,week=29,weekday=7)
			self.fail("bad century")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,decade=10,year=9,week=29,weekday=7)
			self.fail("bad decade")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,decade=6,year=10,week=29,weekday=7)
			self.fail("bad year")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,decade=6,year=8,week=53,weekday=1)
			self.fail("bad week")
		except DateTimeError:
			pass
		try:
			date=Date(century=19,decade=6,year=8,week=52,weekday=8)
			self.fail("bad day")
		except DateTimeError:
			pass
	
	def testTimeTuple(self):
		"""Test Get and Set TimeTuple"""
		"""Note that a time-tuple is a 9-field tuple of:
		year
		month [1,12]
		day [1,31]
		hour [0,20]
		minute [0.59]
		second [0,61]
		weekday [0,6], Monday=0
		Julian day [1,366]
		daylight savings (0,1, or -1)
		We only ever read the first three fields, but we must update
		them all when writing, and we don't allow reduced precision as
		this is not needed for interacting with the functions in the
		time module."""
		date=Date.FromStructTime([1969,7,20,None,None,None,None,None,None])
		timeTuple=[None]*9
		date.UpdateStructTime(timeTuple)
		self.assertTrue(timeTuple==[1969,7,20,None,None,None,6,201,None],"simple case")
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20),"calendar cross-check")
		date=Date(century=19,year=69,month=7)
		try:
			date.UpdateStructTime(timeTuple)
			self.fail("month precision")
		except DateTimeError:
			pass
	
	def testAbsoluteDays(self):
		"""Test Get and Set Absolute Day"""
		date=Date()
		# check the 1st January each from from 0001 (the base day) through 2049
		absDay=1
		for year in xrange(1,1740):
			date=Date(absoluteDay=absDay)
			self.assertTrue(date.GetCalendarDay()==(year//100,year%100,1,1),"%04i-01-01 check"%year)
			self.assertTrue(date.GetAbsoluteDay()==absDay,"%04i-01-01 symmetry check"%year)
			absDay+=365
			if (year%4==0 and (not year%100==0 or year%400==0)):
				absDay+=1
		# check each day in a sample (leap) year
		date=Date(century=19,year=68,month=1,day=1)
		absDay=date.GetAbsoluteDay()
		for i in xrange(366):
			date=Date(absoluteDay=absDay)
			self.assertTrue(date.GetOrdinalDay()==(19,68,i+1),"1968=%03i check"%(i+1))
			self.assertTrue(date.GetAbsoluteDay()==absDay,"1968-%03i symmetry check"%(i+1))
			absDay+=1
								
	def testSetFromString(self):
		date=Date.FromString("19690720")
		self.assertTrue(date.GetCalendarDay()==(19,69,7,20))

	def testGetPrecision(self):
		date=Date(century=19,year=69,month=7,day=20)
		self.assertTrue(date.GetPrecision()==Precision.Complete,"complete precision")
		date=Date(century=19,year=69,month=7)
		self.assertTrue(date.GetPrecision()==Precision.Month,"month precision")
		date=Date(century=19,year=69)
		self.assertTrue(date.GetPrecision()==Precision.Year,"year precision")
		date=Date(century=19)
		self.assertTrue(date.GetPrecision()==Precision.Century,"century precision")
		date=Date(century=19,decade=6,year=9,week=29,weekday=7)
		self.assertTrue(date.GetPrecision()==Precision.Complete,"complete precision (weekday)")
		date=Date(century=19,decade=6,year=9,week=29)
		self.assertTrue(date.GetPrecision()==Precision.Week,"week precision")
	
	def testComparisons(self):
		"""Test the comparison methods"""
		self.assertTrue(Date.FromString("19690720")==Date.FromString("19690720"),"simple equality")
		self.assertTrue(Date.FromString("19690720")<Date.FromString("19690721"),"simple inequality")
		self.assertTrue(Date.FromString("1969W29")==Date.FromString("1969W29"),"equality with week precision")
		self.assertTrue(Date.FromString("1969W29")<Date.FromString("1969W30"),"inequality with week precision")
		self.assertTrue(Date.FromString("1969-07")==Date.FromString("1969-07"),"equality with month precision")
		self.assertTrue(Date.FromString("1969-07")<Date.FromString("1969-08"),"inequality with month precision")
		self.assertTrue(Date.FromString("1969")==Date.FromString("1969"),"equality with year precision")
		self.assertTrue(Date.FromString("1969")<Date.FromString("1970"),"inequality with year precision")
		self.assertTrue(Date.FromString("19")==Date.FromString("19"),"equality with century precision")
		self.assertTrue(Date.FromString("19")<Date.FromString("20"),"inequality with century precision")
		try:
			Date.FromString("1969-W29")==Date.FromString("1969-07")
			self.fail("precision mismatch")
		except ValueError:
			pass

	def testGetCalendarStrings(self):
		"""GetCalendarString tests"""
		self.assertTrue(Date.FromString("19690720").GetCalendarString()=="1969-07-20","default test")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(1)=="19690720","basic test")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(0)=="1969-07-20","extended test")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(1,NoTruncation)=="19690720","basic, no truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(0,NoTruncation)=="1969-07-20","extended, no truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(1,Truncation.Century)=="690720","basic, century truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(0,Truncation.Century)=="69-07-20","extended, century truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(1,Truncation.Year)=="--0720","basic, year truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(0,Truncation.Year)=="--07-20","extended, year truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(1,Truncation.Month)=="---20","basic, month truncation")
		self.assertTrue(Date.FromString("19690720").GetCalendarString(0,Truncation.Month)=="---20","extended, month truncation")
		self.assertTrue(Date.FromString("1969-07").GetCalendarString(1,NoTruncation)=="1969-07","basic, month precision, no truncation")
		self.assertTrue(Date.FromString("1969-07").GetCalendarString(0,NoTruncation)=="1969-07","extended, month precision, no truncation")
		self.assertTrue(Date.FromString("1969-07").GetCalendarString(1,Truncation.Century)=="-6907","basic, month precision, century truncation")
		self.assertTrue(Date.FromString("1969-07").GetCalendarString(0,Truncation.Century)=="-69-07","extended, month precision, century truncation")
		self.assertTrue(Date.FromString("1969-07").GetCalendarString(1,Truncation.Year)=="--07","basic, month precision, year truncation")
		self.assertTrue(Date.FromString("1969-07").GetCalendarString(0,Truncation.Year)=="--07","extended, month precision, year truncation")
		self.assertTrue(Date.FromString("1969").GetCalendarString(1,NoTruncation)=="1969","basic, year precision, no truncation")
		self.assertTrue(Date.FromString("1969").GetCalendarString(0,NoTruncation)=="1969","extended, year precision, no truncation")
		self.assertTrue(Date.FromString("1969").GetCalendarString(1,Truncation.Century)=="-69","basic, year precision, century truncation")
		self.assertTrue(Date.FromString("1969").GetCalendarString(0,Truncation.Century)=="-69","extended, year precision, century truncation")
		self.assertTrue(Date.FromString("19").GetCalendarString(1,NoTruncation)=="19","basic, century precision, no truncation")
		self.assertTrue(Date.FromString("19").GetCalendarString(0,NoTruncation)=="19","extended, century precision, no truncation")
	
	def testGetOrdinalStrings(self):
		"""GetOrdinalString tests"""
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString()=="1969-201","default test")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(1)=="1969201","basic test")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(0)=="1969-201","extended test")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(1,NoTruncation)=="1969201","basic, no truncation")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(0,NoTruncation)=="1969-201","extended, no truncation")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(1,Truncation.Century)=="69201","basic, century truncation")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(0,Truncation.Century)=="69-201","extended, century truncation")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(1,Truncation.Year)=="-201","basic, year truncation")
		self.assertTrue(Date.FromString("1969-201").GetOrdinalString(0,Truncation.Year)=="-201","extended, year truncation")
		self.assertTrue(Date.FromString("1969").GetOrdinalString(1,NoTruncation)=="1969","basic, year precision, no truncation")
		self.assertTrue(Date.FromString("1969").GetOrdinalString(0,NoTruncation)=="1969","extended, year precision, no truncation")
		self.assertTrue(Date.FromString("1969").GetOrdinalString(1,Truncation.Century)=="-69","basic, year precision, century truncation")
		self.assertTrue(Date.FromString("1969").GetOrdinalString(0,Truncation.Century)=="-69","extended, year precision, century truncation")
		self.assertTrue(Date.FromString("19").GetOrdinalString(1,NoTruncation)=="19","basic, century precision, no truncation")
		self.assertTrue(Date.FromString("19").GetOrdinalString(0,NoTruncation)=="19","extended, century precision, no truncation")
			
	def testGetWeekStrings(self):
		"""GetWeekString tests"""
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString()=="1969-W29-7","default test")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(1)=="1969W297","basic test")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(0)=="1969-W29-7","extended test")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(1,NoTruncation)=="1969W297","basic, no truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(0,NoTruncation)=="1969-W29-7","extended, no truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(1,Truncation.Century)=="69W297","basic, century truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(0,Truncation.Century)=="69-W29-7","extended, century truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(1,Truncation.Decade)=="-9W297","basic, decade truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(0,Truncation.Decade)=="-9-W29-7","extended, decade truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(1,Truncation.Year)=="-W297","basic, year truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(0,Truncation.Year)=="-W29-7","extended, year truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(1,Truncation.Week)=="-W-7","basic, week truncation")
		self.assertTrue(Date.FromString("1969-W29-7").GetWeekString(0,Truncation.Week)=="-W-7","extended, week truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(1,NoTruncation)=="1969W29","basic, week precision, no truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(0,NoTruncation)=="1969-W29","extended, week precision, no truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(1,Truncation.Century)=="69W29","basic, week precision, century truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(0,Truncation.Century)=="69-W29","extended, week precision, century truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(1,Truncation.Decade)=="-9W29","basic, week precision, decade truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(0,Truncation.Decade)=="-9-W29","extended, week precision, decade truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(1,Truncation.Year)=="-W29","basic, week precision, year truncation")
		self.assertTrue(Date.FromString("1969-W29").GetWeekString(0,Truncation.Year)=="-W29","extended, week precision, year truncation")
		self.assertTrue(Date.FromString("1969").GetWeekString(1,NoTruncation)=="1969","basic, year precision, no truncation")
		self.assertTrue(Date.FromString("1969").GetWeekString(0,NoTruncation)=="1969","extended, year precision, no truncation")
		self.assertTrue(Date.FromString("1969").GetWeekString(1,Truncation.Century)=="-69","basic, year precision, century truncation")
		self.assertTrue(Date.FromString("1969").GetWeekString(0,Truncation.Century)=="-69","extended, year precision, century truncation")
		self.assertTrue(Date.FromString("19").GetWeekString(1,NoTruncation)=="19","basic, century precision, no truncation")
		self.assertTrue(Date.FromString("19").GetWeekString(0,NoTruncation)=="19","extended, century precision, no truncation")
	
	def testNow(self):
		# This is a weak test
		date=Date.FromNow()
		self.assertTrue(date>Date.FromString("20050313"),"now test")


class TimeTests(unittest.TestCase):
	def testConstructor(self):
		t=Time()
		self.assertTrue(t.GetTime()==(0,0,0),"empty constructor")
		tBase=Time(hour=20,minute=17,second=40)
		t=Time(tBase)
		self.assertTrue(t.GetTime()==(20,17,40),"copy constructor")
		t=Time.FromString("201740")
		self.assertTrue(t.GetTime()==(20,17,40),"string constructor")
		t=Time.FromString(u"20:17:40")
		self.assertTrue(t.GetTime()==(20,17,40),"unicode constructor")
		t=Time.FromString("-1740",tBase)
		self.assertTrue(t.GetTime()==(20,17,40),"truncated hour")
		tBase=Time(hour=20,minute=20,second=30)
		tBase=tBase.WithZone(zDirection=+1,zHour=1)
		t=Time(tBase)
		self.assertTrue(t.GetTime()==(20,20,30) and t.GetZone()==(+1,60),"check zone copy on constructor")
	
	def testTime(self):
		"""Test Get and Set time methods"""
		t=Time()
		tBase=Time()
		tBaseOverflow=Time()
		tBase=Time(hour=20,minute=17,second=40)
		tBaseOverflow=Time(hour=23,minute=20,second=51)
		t=Time(hour=20,minute=17,second=40)
		self.assertTrue(t.GetTime()==(20,17,40),"simple case")
		t=Time(hour=20,minute=17,second=40.5)
		self.assertTrue(t.GetTime()==(20,17,40.5),"fractional seconds")
		try:
			t=Time(minute=20,second=50)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		t,overflow=tBase.Extend(None,47,40)
		self.assertTrue(t.GetTime()==(20,47,40) and not overflow,"truncated hour")
		t,overflow=tBaseOverflow.Extend(None,20,50)
		self.assertTrue(t.GetTime()==(0,20,50) and overflow,"truncated hour with overflow")
		t,overflow=tBase.Extend(None,None,50)
		self.assertTrue(t.GetTime()==(20,17,50) and not overflow,"truncated minute")
		t,overflow=tBaseOverflow.Extend(None,None,50)
		self.assertTrue(t.GetTime()==(23,21,50) and not overflow,"truncated minute with overflow")
		t=Time(hour=20,minute=17)
		self.assertTrue(t.GetTime()==(20,17,None),"minute precision")
		t=Time(hour=20,minute=17.67)
		self.assertTrue(t.GetTime()==(20,17.67,None),"fractional minute precision")
		t=Time(hour=20)
		self.assertTrue(t.GetTime()==(20,None,None),"hour precision")
		t=Time(hour=20.3)
		self.assertTrue(t.GetTime()==(20.3,None,None),"fractional hour precision")
		t,overflow=tBase.Extend(None,20,None)
		self.assertTrue(t.GetTime()==(20,20,None) and not overflow,"minute precision, truncated hour")
		t,overflow=tBaseOverflow.Extend(None,19,None)
		self.assertTrue(t.GetTime()==(0,19,None) and overflow,"minute precision, truncated hour with overflow")
		t=Time(hour=24,minute=0,second=0.0)
		self.assertTrue(t.GetTime()==(24,0,0),"midnight alternate representation")
		try:
			t=Time(hour=25,minute=20,second=50)
			self.fail("bad hour")
		except DateTimeError:
			pass
		try:
			t=Time(hour=20.3,minute=20,second=50)
			self.fail("bad fractional hour")
		except DateTimeError:
			pass
		try:
			t=Time(hour=0,minute=60,second=50)
			self.fail("bad minute")
		except DateTimeError:
			pass
		try:
			t=Time(hour=0,minute=59,second=61)
			self.fail("bad second")
		except DateTimeError:
			pass
		try:
			t=Time(hour=24,minute=0,second=0.5)
			self.fail("bad midnight")
		except DateTimeError:
			pass
	
	def testTimeZone(self):
		"""Test Get and Set TimeZone and correct copy behaviour"""
		t=Time()
		self.assertTrue(t.GetZone()==(None,None),"unknown zone")
		t=t.WithZone(zDirection=0)
		self.assertTrue(t.GetZone()==(0,0),"UTC")
		t=t.WithZone(zDirection=+1,zHour=0,zMinute=0)
		self.assertTrue(t.GetZone()==(+1,0),"UTC, positive offset form")
		t=t.WithZone(zDirection=-1,zHour=0,zMinute=0)
		self.assertTrue(t.GetZone()==(-1,0),"UTC, negative offset form")
		t=Time(hour=15,minute=27,second=46)
		t=t.WithZone(zDirection=+1,zHour=1,zMinute=0)
		self.assertTrue(t.GetZone()==(+1,60),"plus one hour")
		t=t.WithZone(zDirection=-1,zHour=5,zMinute=0)
		self.assertTrue(t.GetZone()==(-1,300),"minus five hours")
		t=t.WithZone(zDirection=+1,zHour=1)
		self.assertTrue(t.GetZone()==(+1,60),"plus one hour, hour precision")
		t=t.WithZone(zDirection=-1,zHour=5)
		self.assertTrue(t.GetZone()==(-1,300),"minus five hours, hour precision")
		tBase=Time(hour=20,minute=20,second=30)
		tBase=t.WithZone(zDirection=+1,zHour=1)
		t,overflow=tBase.Extend(minute=20,second=30)
		self.assertTrue(t.GetZone()==(+1,60),"zone copy on SetTime with truncation")
		try:
			t=t.WithZone(zDirection=-2,zHour=3)
			self.fail("bad direction")
		except DateTimeError:
			pass
		try:
			t=t.WithZone(zDirection=+1)
			self.fail("bad offset")
		except DateTimeError:
			pass
		try:
			t=t.WithZone(zDirection=-1,zHour=24,zMinute=0)
			self.fail("large offset")
		except DateTimeError:
			pass

	def testTimeTuple(self):
		"""Test Get and Set TimeTuple"""
		"""To refresh, a time-tuple is a 9-field tuple of:
		year
		month [1,12]
		day [1,31]
		hour [0,20]
		minute [0.59]
		second [0,61]
		weekday [0,6], Monday=0
		Julian day [1,366]
		daylight savings (0,1, or -1)
		"""
		t=Time.FromStructTime([1969,7,20,20,17,40,None,None,None])
		timeTuple=[None]*9
		t.UpdateStructTime(timeTuple)
		self.assertTrue(timeTuple==[None,None,None,20,17,40,None,None,-1],"simple case")
		self.assertTrue(t.GetTime()==(20,17,40),"time cross-check")
		t=Time(hour=20,minute=20)
		try:
			t.UpdateStructTime(timeTuple)
			self.fail("minute precision")
		except DateTimeError:
			pass
	
	def testSeconds(self):
		"""Test Get and Set seconds"""
		self.assertTrue(Time.FromString("000000").GetTotalSeconds()==0,"zero test")
		self.assertTrue(Time.FromString("201740").GetTotalSeconds()==73060,"sample test")
		self.assertTrue(Time.FromString("240000").GetTotalSeconds()==86400,"full day")
		# leap second is equivalent to the second before, not the second after!
		self.assertTrue(Time.FromString("235960").GetTotalSeconds()==86399,"leap second before midnight")
		t=Time()
		t,overflow=Time().Offset(seconds=0)
		self.assertTrue(t.GetTime()==(0,0,0) and not overflow,"set zero")
		t,overflow=Time().Offset(seconds=73060)
		self.assertTrue(t.GetTime()==(20,17,40) and not overflow,"set sample time")
		t,overflow=Time().Offset(seconds=73060.5)
		self.assertTrue(t.GetTime()==(20,17,40.5) and not overflow,"set sample time with fraction")
		t,overflow=Time().Offset(seconds=86400)
		self.assertTrue(t.GetTime()==(0,0,0) and overflow==1,"set midnight end of day")
		t,overflow=Time().Offset(seconds=677860)
		self.assertTrue(t.GetTime()==(20,17,40) and overflow==7,"set sample time next week")
		t,overflow=Time().Offset(seconds=-531740)
		self.assertTrue(t.GetTime()==(20,17,40) and overflow==-7,"set sample time last week")
				
	def testGetStrings(self):
		"""GetString tests"""
		self.assertTrue(Time.FromString("201740").GetString()=="20:17:40","default test")
		self.assertTrue(Time.FromString("201740").GetString(1)=="201740","basic test")
		self.assertTrue(Time.FromString("201740").GetString(0)=="20:17:40","extended test")
		self.assertTrue(Time.FromString("201740").GetString(1,NoTruncation)=="201740","basic, no truncation")
		self.assertTrue(Time.FromString("201740").GetString(0,NoTruncation)=="20:17:40","extended, no truncation")
		self.assertTrue(Time.FromString("201740,5").GetString(1,NoTruncation)=="201740","basic, fractional seconds, default decimals")
		self.assertTrue(Time.FromString("201740,5").GetString(1,NoTruncation,1)=="201740,5","basic, fractional seconds")
		self.assertTrue(Time.FromString("201740,5").GetString(1,NoTruncation,1,dp=".")=="201740.5","basic, fractional seconds, alt point")
		self.assertTrue(Time.FromString("201740,567").GetString(0,NoTruncation,2)=="20:17:40,56","extended, fractional seconds with decimals")
		self.assertTrue(Time.FromString("201740,567").GetString(0,NoTruncation,2,dp=".")=="20:17:40.56","extended, fractional seconds with decimals and alt point")
		self.assertTrue(Time.FromString("201740").GetString(1,Truncation.Hour)=="-1740","basic, hour truncation")
		self.assertTrue(Time.FromString("201740").GetString(0,Truncation.Hour)=="-17:40","extended, hour truncation")
		self.assertTrue(Time.FromString("201740").GetString(1,Truncation.Minute)=="--40","basic, minute truncation")
		self.assertTrue(Time.FromString("201740").GetString(0,Truncation.Minute)=="--40","extended, minute truncation")
		self.assertTrue(Time.FromString("2017").GetString(1,NoTruncation)=="2017","basic, minute precision, no truncation")
		self.assertTrue(Time.FromString("2017").GetString(0,NoTruncation)=="20:17","extended, minute precision, no truncation")
		self.assertTrue(Time.FromString("2017,8").GetString(1,NoTruncation,3)=="2017,800","basic, fractional minute precision, no truncation")
		self.assertTrue(Time.FromString("2017,895").GetString(0,NoTruncation,3)=="20:17,895","extended, fractinoal minute precision, no truncation")
		self.assertTrue(Time.FromString("20").GetString(1,NoTruncation)=="20","basic, hour precision, no truncation")
		self.assertTrue(Time.FromString("20").GetString(0,NoTruncation)=="20","extended, hour precision, no truncation")
		self.assertTrue(Time.FromString("20,3").GetString(1,NoTruncation,3)=="20,300","basic, fractional hour precision")
		self.assertTrue(Time.FromString("20,345").GetString(0,NoTruncation,3)=="20,345","extended, fractinoal hour precision")
		self.assertTrue(Time.FromString("2017").GetString(1,Truncation.Hour)=="-17","basic, minute precision, hour truncation")
		self.assertTrue(Time.FromString("2017").GetString(0,Truncation.Hour)=="-17","extended, minute precision, hour truncation")
		self.assertTrue(Time.FromString("2017,667").GetString(1,Truncation.Hour,3)=="-17,667","basic, fractional minute precision, hour truncation")
		self.assertTrue(Time.FromString("211740+0100").GetString()=="21:17:40+01:00","default test with zone offset")
		self.assertTrue(Time.FromString("211740+0100").GetString(1)=="211740+0100","basic test with zone offset")
		self.assertTrue(Time.FromString("211740+0100").GetString(0)=="21:17:40+01:00","extended test with zone offset")
		self.assertTrue(Time.FromString("201740Z").GetString(1)=="201740Z","basic test with Z")
		self.assertTrue(Time.FromString("201740Z").GetString(0)=="20:17:40Z","extended test with Z")
		self.assertTrue(Time.FromString("151740-0500").GetString(0,NoTruncation,0,Precision.Hour)=="15:17:40-05",
			"extended test with zone hour precision")
		
	def testSetFromString(self):
		"""Test the basic SetFromString method (exercised more fully by parser tests)"""
		t=Time.FromString("201740")
		self.assertTrue(t.GetTime()==(20,17,40))
	
	def testGetPrecision(self):
		"""Test the precision constants"""
		t=Time(hour=20,minute=17,second=40)
		self.assertTrue(t.GetPrecision()==Precision.Complete,"complete precision")
		t=Time(hour=20,minute=20)
		self.assertTrue(t.GetPrecision()==Precision.Minute,"minute precision")
		t=Time(hour=20)
		self.assertTrue(t.GetPrecision()==Precision.Hour,"hour precision")
	
	def testSetPrecision(self):
		"""Test the setting of the precision"""
		t=Time(hour=20,minute=17,second=40)
		t=t.WithPrecision(Precision.Minute)
		h,m,s=t.GetTime()
		self.assertTrue((h,"%f"%m,s)==(20,"17.666667",None),"reduce to minute precision")
		t=t.WithPrecision(Precision.Hour)
		h,m,s=t.GetTime()
		self.assertTrue(("%f"%h,m,s)==("20.294444",None,None),"reduce to hour precision")
		t=t.WithPrecision(Precision.Minute)
		h,m,s=t.GetTime()
		self.assertTrue((h,"%f"%m,s)==(20,"17.666667",None),"extend to minute precision")
		t=t.WithPrecision(Precision.Complete)
		h,m,s=t.GetTime()
		self.assertTrue((h,m,"%f"%s)==(20,17,"40.000000"),"extend to complete precision")
		t=Time(hour=20,minute=17,second=40)
		t=t.WithPrecision(Precision.Minute,1)
		self.assertTrue(t.GetTime()==(20,17,None),"reduce to integer minute precision")
		t=t.WithPrecision(Precision.Hour,1)
		self.assertTrue(t.GetTime()==(20,None,None),"reduce to integer hour precision")
		t=t.WithPrecision(Precision.Minute,1)
		self.assertTrue(t.GetTime()==(20,0,None),"extend to integer minute precision")
		t=t.WithPrecision(Precision.Complete,1)
		self.assertTrue(t.GetTime()==(20,0,0),"extend to integer complete precision")
		t=Time(hour=20,minute=17,second=40.5)
		t=t.WithPrecision(Precision.Complete,1)
		self.assertTrue(t.GetTime()==(20,17,40),"integer complete precision")
		t=Time(hour=20,minute=17.666668)
		t=t.WithPrecision(Precision.Minute,1)
		self.assertTrue(t.GetTime()==(20,17,None),"integer minute precision")
		t=Time(hour=20.294444)
		t=t.WithPrecision(Precision.Hour,1)
		self.assertTrue(t.GetTime()==(20,None,None),"integer hour precision")
		
	def testComparisons(self):
		"""Test the comparison methods"""
		self.assertTrue(Time.FromString("201740")==Time.FromString("201740"),"simple equality")
		self.assertTrue(Time.FromString("201740")<Time.FromString("201751"),"simple inequality")
		self.assertTrue(Time.FromString("2017")==Time.FromString("2017"),"equality with minute precision")
		self.assertTrue(Time.FromString("2017")<Time.FromString("2021"),"inequality with minute precision")
		self.assertTrue(Time.FromString("20")==Time.FromString("20"),"equality with hour precision")
		self.assertTrue(Time.FromString("20")<Time.FromString("24"),"inequality with hour precision")
		self.assertTrue(Time.FromString("201740Z")==Time.FromString("201740Z"),"simple equality with matching zone")
		self.assertTrue(Time.FromString("201740Z")<Time.FromString("201751Z"),"simple inequality with matching zone")
		self.assertTrue(Time.FromString("201740Z")==Time.FromString("201740+00"),"simple equality with positive zone")
		self.assertTrue(Time.FromString("201740Z")<Time.FromString("211740-00"),"simple inequality with negative zone")
		self.assertTrue(Time.FromString("201740Z")>Time.FromString("201739-00"),"inequality with non matching zone and overflow")
		try:
			Time.FromString("201740")==Time.FromString("2017")
			self.fail("precision mismatch")
		except ValueError:
			pass
		try:
			Time.FromString("201740Z")==Time.FromString("201740")
			self.fail("zone unspecified mismatch")
		except ValueError:
			pass
		try:
			Time.FromString("201740+00")==Time.FromString("211740+01")
			self.fail("zone specified mismatch")
		except ValueError:
			pass

	def testNow(self):
		# A very weak test, how do we know the real time?
		t=Time.FromNow()

		
class TimePointTests(unittest.TestCase):
	def setUp(self):
		pass
			
	def tearDown(self):
		pass

	def testConstructor(self):
		t=TimePoint()
		self.assertTrue(t.GetCalendarTimePoint()==(0,1,1,1,0,0,0) and t.time.GetZone()==(None,None),"empty constructor")
		base=TimePoint()
		base.date=Date(century=19,year=69,month=7,day=20)
		base.time=Time(hour=20,minute=17,second=40)
		base.time=base.time.WithZone(zDirection=0)
		t=TimePoint(base)
		self.assertTrue(t.time.GetTime()==(20,17,40) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,69,7,20),"copy constructor")
		t=TimePoint.FromString("19690720T201740Z")
		self.assertTrue(t.time.GetTime()==(20,17,40) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,69,7,20),"string constructor")
		t=TimePoint.FromString(u"19690720T201740Z")
		self.assertTrue(t.time.GetTime()==(20,17,40) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,69,7,20),"unicode constructor")
		base=Date(t.date)
		t=TimePoint.FromString("--0720T201740Z",base)
		self.assertTrue(t.time.GetTime()==(20,17,40) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,69,7,20),"truncated year")

	def testGetStrings(self):
		"""GetString tests"""
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetCalendarString()=="1969-07-20T20:17:40Z","default test")
		self.assertTrue(TimePoint.FromString("19690720T211740+0100").GetCalendarString(1)=="19690720T211740+0100","basic test")
		self.assertTrue(TimePoint.FromString("19690720T211740+0100").GetCalendarString(0)=="1969-07-20T21:17:40+01:00","extended test")
		self.assertTrue(TimePoint.FromString("19690720T201740").GetCalendarString(1,NoTruncation)=="19690720T201740","basic, no truncation")
		self.assertTrue(TimePoint.FromString("19690720T201740").GetCalendarString(0,NoTruncation)=="1969-07-20T20:17:40","extended, no truncation")
		self.assertTrue(TimePoint.FromString("19690720T201740").GetCalendarString(1,Truncation.Month)=="---20T201740","basic, month truncation")
		self.assertTrue(TimePoint.FromString("19690720T201740").GetCalendarString(0,Truncation.Month)=="---20T20:17:40","extended, month truncation")
		self.assertTrue(TimePoint.FromString("19690720T211740+0100").GetCalendarString(0,NoTruncation,3,Precision.Hour)==
			"1969-07-20T21:17:40,000+01","fractional seconds and time zone precision control")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetOrdinalString()=="1969-201T20:17:40Z","default ordinal test")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetOrdinalString(1)=="1969201T201740Z","basic ordinal test")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetOrdinalString(0)=="1969-201T20:17:40Z","extended ordinal test")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetOrdinalString(1,NoTruncation)=="1969201T201740Z","basic ordinal, no truncation")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetOrdinalString(0,NoTruncation)=="1969-201T20:17:40Z","extended ordinal, no truncation")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetWeekString()=="1969-W29-7T20:17:40Z","default week test")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetWeekString(1)=="1969W297T201740Z","basic week test")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetWeekString(0)=="1969-W29-7T20:17:40Z","extended week test")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetWeekString(1,NoTruncation)=="1969W297T201740Z","basic week, no truncation")
		self.assertTrue(TimePoint.FromString("19690720T201740Z").GetWeekString(0,NoTruncation)=="1969-W29-7T20:17:40Z","extended week, no truncation")

	def testComparisons(self):
		"""Test the comparison methods"""
		self.assertTrue(TimePoint.FromString("19690720T201740")==TimePoint.FromString("19690720T201740"),"simple equality")
		self.assertTrue(TimePoint.FromString("19690720T201740")<TimePoint.FromString("19690720T201751"),"simple inequality")
		self.assertTrue(TimePoint.FromString("19680407T201751")<TimePoint.FromString("19690720T201740"),"whole day inequality")
		self.assertTrue(TimePoint.FromString("19690720T2017")==TimePoint.FromString("19690720T2017"),"equality with minute precision")
		self.assertTrue(TimePoint.FromString("19690720T201740Z")==TimePoint.FromString("19690720T201740Z"),"simple equality with matching zone")
		self.assertTrue(TimePoint.FromString("19690720T201740Z")<TimePoint.FromString("19690720T201751Z"),"simple inequality with matching zone")
		self.assertTrue(TimePoint.FromString("19690720T201740Z")==TimePoint.FromString("19690720T211740+01"),"simple equality with non matching zone")
		self.assertTrue(TimePoint.FromString("19690720T201740Z")>TimePoint.FromString("19690720T201740+01"),"simple inequality with non matching zone")
		self.assertTrue(TimePoint.FromString("19690720T201740Z")<TimePoint.FromString("19690720T201740-01"),"inequality with non matching zone and overflow")
		try:
			TimePoint.FromString("19690720T201740")==TimePoint.FromString("19690720T2017")
			self.fail("precision mismatch")
		except ValueError:
			pass
		try:
			TimePoint.FromString("19690720T201740Z")==TimePoint.FromString("19690720T201740")
			self.fail("zone unspecified mismatch")
		except ValueError:
			pass

	def testHash(self):
		"""Test the ability to hash TimePoints"""
		d={}
		d[TimePoint.FromString("19690720T201740")]=True
		self.assertTrue(TimePoint.FromString("19690720T201740") in d)
		self.assertFalse(TimePoint.FromString("19680720T201740") in d)
		d={}
		d[TimePoint.FromString("19690720T201740Z")]=True
		self.assertTrue(TimePoint.FromString("19690720T201740Z") in d)
		self.assertTrue(TimePoint.FromString("19690720T201740+00") in d)
		self.assertTrue(TimePoint.FromString("19690720T201740+0000") in d)
		self.assertTrue(TimePoint.FromString("19690720T211740+0100") in d)
		self.assertTrue(TimePoint.FromString("19690720T151740-0500") in d)
		self.assertFalse(TimePoint.FromString("19690720T201740-0500") in d)
		self.assertFalse(TimePoint.FromString("19690720T201740+0100") in d)
		
class DurationTests(unittest.TestCase):
	def testConstructor(self):
		"""Duration constructor tests."""
		d=Duration()
		self.assertTrue(d.GetCalendarDuration()==(0,0,0,0,0,0),"empty constructor")
		dCopy=Duration()
		dCopy.SetCalendarDuration(36,11,13,10,5,0)
		d=Duration(dCopy)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5,0),"copy constructor")
		d=Duration("P36Y11M13DT10H5M0S")
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5,0),"string constructor")
		d=Duration(u"P36Y11M13DT10H5M0S")
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5,0),"unicode constructor")

	def testCalendarDuration(self):
		"""Test Get and Set Calendar Durations"""
		d=Duration()
		d.SetCalendarDuration(36,11,13,10,5,0)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5,0),"simple case")
		d.SetCalendarDuration(36,11,13,10,5,0.5)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5,0.5),"fractional seconds")
		d.SetCalendarDuration(36,11,13,10,5,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5,None),"minute precision")
		d.SetCalendarDuration(36,11,13,10,5.5,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,5.5,None),"fractional minutes")
		d.SetCalendarDuration(36,11,13,10,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10,None,None),"hour precision")
		d.SetCalendarDuration(36,11,13,10.5,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,10.5,None,None),"fractional hours")
		d.SetCalendarDuration(36,11,13,None,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13,None,None,None),"day precision")
		d.SetCalendarDuration(36,11,13.5,None,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,13.5,None,None,None),"fractional days")
		d.SetCalendarDuration(36,11,None,None,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11,None,None,None,None),"month precision")
		d.SetCalendarDuration(36,11.5,None,None,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,11.5,None,None,None,None),"fractional months")
		d.SetCalendarDuration(36,None,None,None,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36,None,None,None,None,None),"year precision")
		d.SetCalendarDuration(36.5,None,None,None,None,None)
		self.assertTrue(d.GetCalendarDuration()==(36.5,None,None,None,None,None),"fractional years")
		d.SetWeekDuration(45)
		try:
			d.GetCalendarDuration()
			self.fail("week mode")
		except DateTimeError:
			pass
	
	def testWeekDuration(self):
		"""Test Get and Set Week Durations"""
		d=Duration()
		d.SetWeekDuration(45)
		self.assertTrue(d.GetWeekDuration()==45,"simple case")
		d.SetWeekDuration(45.5)
		self.assertTrue(d.GetWeekDuration()==45.5,"fractional case")
		d.SetCalendarDuration(36,11,13,10,5,0)
		try:
			d.GetWeekDuration()
			self.fail("calendar mode")
		except DateTimeError:
			pass
			
	def testGetStrings(self):
		"""Test the GetString method."""
		self.assertTrue(Duration("P36Y11M13DT10H5M0S").GetString()=="P36Y11M13DT10H5M0S","complete, default")
		self.assertTrue(Duration("P36Y11M13DT10H5M0S").GetString(1)=="P36Y11M13DT10H5M0S","complete, no truncation")
		self.assertTrue(Duration().GetString(0)=="P0Y0M0DT0H0M0S","complete zero")
		self.assertTrue(Duration().GetString(1)=="PT0S","complete zero with truncation")
		self.assertTrue(Duration("P0Y0M0DT0H").GetString(1)=="PT0H","hour precision zero with truncation")
		self.assertTrue(Duration("P0Y0M0DT0H").GetString(0)=="P0Y0M0DT0H","hour precision zero without truncation")
		self.assertTrue(Duration("P0Y11M13DT10H5M0S").GetString(1)=="P11M13DT10H5M0S","year truncation")
		self.assertTrue(Duration("P0Y0M13DT10H5M0S").GetString(1)=="P13DT10H5M0S","month truncation")
		self.assertTrue(Duration("P0Y0M0DT10H5M0S").GetString(1)=="PT10H5M0S","day truncation")
		self.assertTrue(Duration("P0Y0M0DT0H5M0S").GetString(1)=="PT5M0S","hour truncation")
		self.assertTrue(Duration("P0Y0M0DT0H5M").GetString(1)=="PT5M","hour truncation, minute precision")
		self.assertTrue(Duration("P36Y11M13DT10H5M0,5S").GetString(0)=="P36Y11M13DT10H5M0S","removal of fractional seconds")
		self.assertTrue(Duration("P36Y11M13DT10H5M0,5S").GetString(0,3)=="P36Y11M13DT10H5M0,500S","display of fractional seconds")
		self.assertTrue(Duration("P36Y11M13DT10H5M0S").GetString(0,3)=="P36Y11M13DT10H5M0S","missing fractional seconds")
		self.assertTrue(Duration("P36Y11M13DT10H5M0,5S").GetString(0,-3)=="P36Y11M13DT10H5M0.500S","display of fractional seconds alt format")
		self.assertTrue(Duration("P36Y11M13DT10H5M").GetString(0)=="P36Y11M13DT10H5M","minute precision")
		self.assertTrue(Duration("P36Y11M13DT10H5,0M").GetString(0)=="P36Y11M13DT10H5M","removal of fractional minutes")
		self.assertTrue(Duration("P36Y11M13DT10H5,0M").GetString(0,2)=="P36Y11M13DT10H5,00M","fractional minute precision")
		self.assertTrue(Duration("P36Y11M13DT10H5,0M").GetString(0,-2)=="P36Y11M13DT10H5.00M","fractional minute precision alt format")
		self.assertTrue(Duration("P36Y11M13DT10H").GetString(0)=="P36Y11M13DT10H","hour precision")
		self.assertTrue(Duration("P36Y11M13DT10,08H").GetString(0)=="P36Y11M13DT10H","removal of fractional hours")
		self.assertTrue(Duration("P36Y11M13DT10,08H").GetString(0,1)=="P36Y11M13DT10,0H","fractional hour precision")
		self.assertTrue(Duration("P36Y11M13DT10,08H").GetString(0,-1)=="P36Y11M13DT10.0H","fractional hour precision alt format")
		self.assertTrue(Duration("P36Y11M13D").GetString(0)=="P36Y11M13D","day precision")
		self.assertTrue(Duration("P36Y11M13,420D").GetString(0)=="P36Y11M13D","removal of fractional days")
		self.assertTrue(Duration("P36Y11M13,420D").GetString(0,4)=="P36Y11M13,4200D","fractional day precision")
		self.assertTrue(Duration("P36Y11M13,420D").GetString(0,-4)=="P36Y11M13.4200D","fractional day precision alt format")
		self.assertTrue(Duration("P36Y11M").GetString(0)=="P36Y11M","month precision")
		self.assertTrue(Duration("P36Y11,427M").GetString(0)=="P36Y11M","removal of fractional month")
		self.assertTrue(Duration("P36Y11,427M").GetString(0,2)=="P36Y11,42M","fractional month precision")
		self.assertTrue(Duration("P36Y11,427M").GetString(0,-2)=="P36Y11.42M","fractional month precision alt format")
		self.assertTrue(Duration("P36Y").GetString(0)=="P36Y","year precision")
		self.assertTrue(Duration("P36,95Y").GetString(0)=="P36Y","removal of fractional year")
		self.assertTrue(Duration("P36,95Y").GetString(0,1)=="P36,9Y","fractional year precision")
		self.assertTrue(Duration("P36,95Y").GetString(0,-1)=="P36.9Y","fractional year precision alt format")
		
	def testComparisons(self):
		"""Test the comparison methods"""
		self.assertTrue(Duration("P36Y11M13DT10H5M0S")==Duration("P36Y11M13DT10H5M0S"),"simple equality")
		self.assertTrue(Duration("P11M13DT10H5M0S")==Duration("P0Y11M13DT10H5M0S"),"missing years")
		
		
		
class ParserTests(unittest.TestCase):
	def setUp(self):
		pass
		
	def testDateParser(self):
		date=Date()
		base=Date()
		base=Date(century=19,year=65,month=4,day=12)
		self.assertTrue(Date.FromStringFormat("19850412",base)[1]=="YYYYMMDD")
		self.assertTrue(Date.FromStringFormat("1985-04-12",base)[1]=="YYYY-MM-DD")
		self.assertTrue(Date.FromStringFormat("1985-04",base)[1]=="YYYY-MM")
		self.assertTrue(Date.FromStringFormat("1985",base)[1]=="YYYY")
		self.assertTrue(Date.FromStringFormat("19",base)[1]=="YY")
		self.assertTrue(Date.FromStringFormat("850412",base)[1]=="YYMMDD")
		self.assertTrue(Date.FromStringFormat("85-04-12",base)[1]=="YY-MM-DD")
		self.assertTrue(Date.FromStringFormat("-8504",base)[1]=="-YYMM")
		self.assertTrue(Date.FromStringFormat("-85-04",base)[1]=="-YY-MM")
		self.assertTrue(Date.FromStringFormat("-85",base)[1]=="-YY")
		self.assertTrue(Date.FromStringFormat("--0412",base)[1]=="--MMDD")
		self.assertTrue(Date.FromStringFormat("--04-12",base)[1]=="--MM-DD")
		self.assertTrue(Date.FromStringFormat("--04",base)[1]=="--MM")
		self.assertTrue(Date.FromStringFormat("---12",base)[1]=="---DD")
		self.assertTrue(Date.FromStringFormat("1985102",base)[1]=="YYYYDDD")
		self.assertTrue(Date.FromStringFormat("1985-102",base)[1]=="YYYY-DDD")
		self.assertTrue(Date.FromStringFormat("85102",base)[1]=="YYDDD")
		self.assertTrue(Date.FromStringFormat("85-102",base)[1]=="YY-DDD")
		self.assertTrue(Date.FromStringFormat("-102",base)[1]=="-DDD")
		self.assertTrue(Date.FromStringFormat("1985W155",base)[1]=="YYYYWwwD")
		self.assertTrue(Date.FromStringFormat("1985-W15-5",base)[1]=="YYYY-Www-D")
		self.assertTrue(Date.FromStringFormat("1985W15",base)[1]=="YYYYWww")
		self.assertTrue(Date.FromStringFormat("1985-W15",base)[1]=="YYYY-Www")
		self.assertTrue(Date.FromStringFormat("85W155",base)[1]=="YYWwwD")
		self.assertTrue(Date.FromStringFormat("85-W15-5",base)[1]=="YY-Www-D")
		self.assertTrue(Date.FromStringFormat("85W15",base)[1]=="YYWww")
		self.assertTrue(Date.FromStringFormat("85-W15",base)[1]=="YY-Www")
		self.assertTrue(Date.FromStringFormat("-5W155",base)[1]=="-YWwwD")
		self.assertTrue(Date.FromStringFormat("-5-W15-5",base)[1]=="-Y-Www-D")
		self.assertTrue(Date.FromStringFormat("-5W15",base)[1]=="-YWww")
		self.assertTrue(Date.FromStringFormat("-5-W15",base)[1]=="-Y-Www")
		self.assertTrue(Date.FromStringFormat("-W155",base)[1]=="-WwwD")
		self.assertTrue(Date.FromStringFormat("-W15-5",base)[1]=="-Www-D")
		self.assertTrue(Date.FromStringFormat("-W15",base)[1]=="-Www")
		self.assertTrue(Date.FromStringFormat("-W-5",base)[1]=="-W-D")
	
	def testTimeParser(self):
		t=Time()
		base=Time(hour=20,minute=17,second=40)
		self.assertTrue(Time.FromStringFormat("201740",base)[2]=="hhmmss")
		self.assertTrue(Time.FromStringFormat("20:17:40",base)[2]=="hh:mm:ss")
		self.assertTrue(Time.FromStringFormat("2017",base)[2]=="hhmm")
		self.assertTrue(Time.FromStringFormat("20:17",base)[2]=="hh:mm")
		self.assertTrue(Time.FromStringFormat("20",base)[2]=="hh")
		self.assertTrue(Time.FromStringFormat("201740,5",base)[2]=="hhmmss,s")
		self.assertTrue(Time.FromStringFormat("201740.50",base)[2]=="hhmmss.s")
		self.assertTrue(Time.FromStringFormat("20:17:40,5",base)[2]=="hh:mm:ss,s")
		self.assertTrue(Time.FromStringFormat("2017,8",base)[2]=="hhmm,m")
		self.assertTrue(Time.FromStringFormat("2017.80",base)[2]=="hhmm.m")
		self.assertTrue(Time.FromStringFormat("20:17,8",base)[2]=="hh:mm,m")
		self.assertTrue(Time.FromStringFormat("20,3",base)[2]=="hh,h")
		self.assertTrue(Time.FromStringFormat("20.80",base)[2]=="hh.h")
		self.assertTrue(Time.FromStringFormat("-1740",base)[2]=="-mmss")
		self.assertTrue(Time.FromStringFormat("-17:40",base)[2]=="-mm:ss")
		self.assertTrue(Time.FromStringFormat("-20",base)[2]=="-mm")
		self.assertTrue(Time.FromStringFormat("--40",base)[2]=="--ss")
		self.assertTrue(Time.FromStringFormat("-1740,5",base)[2]=="-mmss,s")
		self.assertTrue(Time.FromStringFormat("-17:40,5",base)[2]=="-mm:ss,s")
		self.assertTrue(Time.FromStringFormat("-20,8",base)[2]=="-mm,m")
		self.assertTrue(Time.FromStringFormat("--40,5",base)[2]=="--ss,s")
		self.assertTrue(Time.FromStringFormat("T201740",base)[2]=="hhmmss")
		self.assertTrue(Time.FromStringFormat("T20:17:40",base)[2]=="hh:mm:ss")
		self.assertTrue(Time.FromStringFormat("T2017",base)[2]=="hhmm")
		self.assertTrue(Time.FromStringFormat("T20:17",base)[2]=="hh:mm")
		self.assertTrue(Time.FromStringFormat("T20",base)[2]=="hh")
		self.assertTrue(Time.FromStringFormat("T201740,5",base)[2]=="hhmmss,s")
		self.assertTrue(Time.FromStringFormat("T20:17:40,5",base)[2]=="hh:mm:ss,s")
		self.assertTrue(Time.FromStringFormat("T2017,8",base)[2]=="hhmm,m")
		self.assertTrue(Time.FromStringFormat("T20:17,8",base)[2]=="hh:mm,m")
		self.assertTrue(Time.FromStringFormat("T20,3",base)[2]=="hh,h")
		self.assertTrue(Time.FromStringFormat("000000")[2]=="hhmmss")
		self.assertTrue(Time.FromStringFormat("00:00:00")[2]=="hh:mm:ss")
		self.assertTrue(Time.FromStringFormat("240000")[2]=="hhmmss")
		self.assertTrue(Time.FromStringFormat("24:00:00")[2]=="hh:mm:ss")
		self.assertTrue(Time.FromStringFormat("201740Z",base)[2]=="hhmmssZ")
		self.assertTrue(Time.FromStringFormat("T20:17:40Z",base)[2]=="hh:mm:ssZ")
		self.assertTrue(Time.FromStringFormat("T20,3",base)[2]=="hh,h")
		self.assertTrue(Time.FromStringFormat("T20,3Z",base)[2]=="hh,hZ")
		self.assertTrue(Time.FromStringFormat("152746+0100")[2]=="hhmmss+hhmm")
		self.assertTrue(Time.FromStringFormat("152746-0500")[2]=="hhmmss+hhmm")
		self.assertTrue(Time.FromStringFormat("152746+01")[2]=="hhmmss+hh")
		self.assertTrue(Time.FromStringFormat("152746-05")[2]=="hhmmss+hh")
		self.assertTrue(Time.FromStringFormat("15:27:46+01:00")[2]=="hh:mm:ss+hh:mm")
		self.assertTrue(Time.FromStringFormat("15:27:46-05:00")[2]=="hh:mm:ss+hh:mm")
		self.assertTrue(Time.FromStringFormat("15:27:46+01")[2]=="hh:mm:ss+hh")
		self.assertTrue(Time.FromStringFormat("15:27:46-05")[2]=="hh:mm:ss+hh")
		self.assertTrue(Time.FromStringFormat("15:27+01",base)[2]=="hh:mm+hh")
		self.assertTrue(Time.FromStringFormat("15,5-05:00",base)[2]=="hh,h+hh:mm")
		# pure timezone functions
		self.assertTrue(t.WithZoneStringFormat("+0100")[1]=="+hhmm")
		self.assertTrue(t.WithZoneStringFormat("+01")[1]=="+hh")
		self.assertTrue(t.WithZoneStringFormat("-0100")[1]=="+hhmm")
		self.assertTrue(t.WithZoneStringFormat("-01")[1]=="+hh")
		self.assertTrue(t.WithZoneStringFormat("+01:00")[1]=="+hh:mm")
		
	def testTimePoint(self):
		"""Check TimePoint  syntax"""
		timePoint=TimePoint()
		base=TimePoint()
		self.assertTrue(TimePoint.FromStringFormat("19850412T101530",base)[1]=="YYYYMMDDThhmmss","basic local")
		self.assertTrue(TimePoint.FromStringFormat("19850412T101530Z",base)[1]=="YYYYMMDDThhmmssZ","basic z")
		self.assertTrue(TimePoint.FromStringFormat("19850412T101530+0400",base)[1]=="YYYYMMDDThhmmss+hhmm","basic zone minutes")
		self.assertTrue(TimePoint.FromStringFormat("19850412T101530+04",base)[1]=="YYYYMMDDThhmmss+hh","basic zone hours")
		self.assertTrue(TimePoint.FromStringFormat("1985-04-12T10:15:30",base)[1]=="YYYY-MM-DDThh:mm:ss","extended local")
		self.assertTrue(TimePoint.FromStringFormat("1985-04-12T10:15:30Z",base)[1]=="YYYY-MM-DDThh:mm:ssZ","extended z")
		self.assertTrue(TimePoint.FromStringFormat("1985-04-12T10:15:30+04:00",base)[1]=="YYYY-MM-DDThh:mm:ss+hh:mm","extended zone minutes")
		self.assertTrue(TimePoint.FromStringFormat("1985-04-12T10:15:30+04",base)[1]=="YYYY-MM-DDThh:mm:ss+hh","extended zone hours")

	def testDuration(self):
		"""Check Duration syntax"""
		duration=Duration()
		self.assertTrue(duration.SetFromString("P36Y11M13DT10H5M0S")=="PnYnMnDTnHnMnS","complete")
		self.assertTrue(duration.SetFromString("P36Y11M13DT10H5M0,5S")=="PnYnMnDTnHnMn,nS","complete with decimals")
		self.assertTrue(duration.SetFromString("P36Y11M13DT10H5M0.5S")=="PnYnMnDTnHnMn.nS","complete with alt decimals")
		self.assertTrue(duration.SetFromString("P36Y11M13DT10H5M")=="PnYnMnDTnHnM","minute precision")
		self.assertTrue(duration.SetFromString("P36Y11M13DT10H")=="PnYnMnDTnH","hour precision")
		self.assertTrue(duration.SetFromString("P36Y11M13D")=="PnYnMnD","day precision")
		self.assertTrue(duration.SetFromString("P36Y11M")=="PnYnM","month precision")
		self.assertTrue(duration.SetFromString("P36Y")=="PnY","year precision")
		self.assertTrue(duration.SetFromString("P36Y11,2M")=="PnYn,nM","month precision with decimals")
		self.assertTrue(duration.SetFromString("P11M")=="PnM","month only precision")
		self.assertTrue(duration.SetFromString("PT10H5M")=="PTnHnM","hour and minute only")
		self.assertTrue(duration.SetFromString("PT5M")=="PTnM","minute only")
		

if __name__ == "__main__":
	unittest.main()