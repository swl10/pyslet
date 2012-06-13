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
		self.failUnless(date.GetCalendarDay()==(0,1,1,1),"empty constructor")
		base=Date()
		base.SetCalendarDay(19,68,4,8)
		date=Date(base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"copy constructor")
		date=Date("19680408")
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"string constructor")
		date=Date(u"1968-04-08")
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"unicode constructor")
		date=Date("--0408",base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"truncated year")

	def testCalendarDay(self):
		"""Test Get and Set Calendar day"""
		date=Date()
		base=Date()
		baseOverflow=Date()
		base.SetCalendarDay(19,68,4,8)
		baseOverflow.SetCalendarDay(19,68,4,9)
		date.SetCalendarDay(19,68,4,8)
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"simple case")
		try:
			date.SetCalendarDay(None,68,4,8)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		date.SetCalendarDay(None,68,4,8,base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"truncated century")
		date.SetCalendarDay(None,68,4,8,baseOverflow)
		self.failUnless(date.GetCalendarDay()==(20,68,4,8),"truncated century with overflow")
		date.SetCalendarDay(None,None,4,8,base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"truncated year")
		date.SetCalendarDay(None,None,4,8,baseOverflow)
		self.failUnless(date.GetCalendarDay()==(19,69,4,8),"truncated year with overflow")
		date.SetCalendarDay(None,None,None,8,base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"truncated month")
		date.SetCalendarDay(None,None,None,8,baseOverflow)
		self.failUnless(date.GetCalendarDay()==(19,68,5,8),"truncated month with overflow")
		date.SetCalendarDay(19,68,4,None)
		self.failUnless(date.GetCalendarDay()==(19,68,4,None),"month precision")
		date.SetCalendarDay(19,68,None,None)
		self.failUnless(date.GetCalendarDay()==(19,68,None,None),"year precision")
		date.SetCalendarDay(19,None,None,None)
		self.failUnless(date.GetCalendarDay()==(19,None,None,None),"century precision")
		baseOverflow.SetCalendarDay(19,68,5,1)
		date.SetCalendarDay(None,68,4,None,base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,None),"month precision, truncated century")
		date.SetCalendarDay(None,68,4,None,baseOverflow)
		self.failUnless(date.GetCalendarDay()==(20,68,4,None),"month precision, truncated century with overflow")
		date.SetCalendarDay(None,None,4,None,base)
		self.failUnless(date.GetCalendarDay()==(19,68,4,None),"month precision, truncated year")
		date.SetCalendarDay(None,None,4,None,baseOverflow)
		self.failUnless(date.GetCalendarDay()==(19,69,4,None),"month precision, truncated year with overflow")
		baseOverflow.SetCalendarDay(19,69,1,1)
		date.SetCalendarDay(None,68,None,None,base)
		self.failUnless(date.GetCalendarDay()==(19,68,None,None),"year precision, truncated century")
		date.SetCalendarDay(None,68,None,None,baseOverflow)
		self.failUnless(date.GetCalendarDay()==(20,68,None,None),"year precision, truncated century with overflow")
		try:
			date.SetCalendarDay(100,68,4,8)
			self.fail("bad century")
		except DateTimeError:
			pass
		try:
			date.SetCalendarDay(19,100,4,8)
			self.fail("bad year")
		except DateTimeError:
			pass
		try:
			date.SetCalendarDay(19,68,13,8)
			self.fail("bad month")
		except DateTimeError:
			pass
		try:
			date.SetCalendarDay(19,00,2,29)
			self.fail("bad day")
		except DateTimeError:
			pass
		
	def testOrdinalDay(self):
		"""Test Get and Set Ordinal day"""
		date=Date()
		base=Date()
		baseOverflow=Date()
		base.SetCalendarDay(19,68,4,8)
		baseOverflow.SetCalendarDay(19,68,4,9)
		date.SetOrdinalDay(19,68,99)
		self.failUnless(date.GetOrdinalDay()==(19,68,99),"simple case ")
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"calendar cross check")
		date.SetOrdinalDay(19,68,1)
		self.failUnless(date.GetCalendarDay()==(19,68,1,1),"calendar cross check Jan 1st")
		date.SetOrdinalDay(19,68,366)
		self.failUnless(date.GetCalendarDay()==(19,68,12,31),"calendar cross check Dec 31st (leap)")
		date.SetOrdinalDay(19,69,365)
		self.failUnless(date.GetCalendarDay()==(19,69,12,31),"calendar cross check Dec 31st (non-leap)")
		try:
			date.SetOrdinalDay(None,68,99)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		date.SetOrdinalDay(None,68,99,base)
		self.failUnless(date.GetOrdinalDay()==(19,68,99),"truncated century")
		date.SetOrdinalDay(None,68,99,baseOverflow)
		self.failUnless(date.GetOrdinalDay()==(20,68,99),"truncated century with overflow")
		date.SetOrdinalDay(None,None,99,base)
		self.failUnless(date.GetOrdinalDay()==(19,68,99),"truncated year")
		date.SetOrdinalDay(None,None,99,baseOverflow)
		self.failUnless(date.GetOrdinalDay()==(19,69,99),"truncated year with overflow")
		# 1968 is a leap year and 1969 is not, therefore this should give us April 9th again!
		self.failUnless(date.GetCalendarDay()==(19,69,4,9),"calendar cross check on overflow")
		date.SetWeekDay(19,6,8,15,None)
		try:
			date.GetOrdinalDay()
			self.fail("ordinal day with week precision")
		except DateTimeError:
			pass
		date.SetCalendarDay(19,68,4,None)
		try:
			date.GetOrdinalDay()
			self.fail("ordinal day with month precision")
		except DateTimeError:
			pass	
		date.SetOrdinalDay(19,68,None,None)
		self.failUnless(date.GetOrdinalDay()==(19,68,None),"year precision")
		date.SetOrdinalDay(19,None,None,None)
		self.failUnless(date.GetOrdinalDay()==(19,None,None),"century precision")
		baseOverflow.SetCalendarDay(19,69,1,1)
		date.SetOrdinalDay(None,68,None,base)
		self.failUnless(date.GetOrdinalDay()==(19,68,None),"year precision, truncated century")
		date.SetOrdinalDay(None,68,None,baseOverflow)
		self.failUnless(date.GetOrdinalDay()==(20,68,None),"year precision, truncated century with overflow")
		try:
			date.SetOrdinalDay(100,68,99)
			self.fail("bad century")
		except DateTimeError:
			pass
		try:
			date.SetOrdinalDay(19,100,99)
			self.fail("bad year")
		except DateTimeError:
			pass
		try:
			date.SetOrdinalDay(19,68,367)
			self.fail("bad ordinal - leap")
		except DateTimeError:
			pass
		try:
			date.SetOrdinalDay(19,69,366)
			self.fail("bad ordinal - non-leap")
		except DateTimeError:
			pass

	def testWeekDay(self):
		"""Test Get and Set Week day"""
		date=Date()
		base=Date()
		baseOverflow=Date()
		base.SetCalendarDay(19,68,4,8)
		baseOverflow.SetCalendarDay(19,68,4,9)
		date.SetWeekDay(19,6,8,15,1)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,1),"simple case")
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"calendar cross check")
		date.SetWeekDay(19,6,9,1,1)
		self.failUnless(date.GetCalendarDay()==(19,68,12,30),"calendar cross check underflow")
		date.SetWeekDay(19,7,0,53,5)
		self.failUnless(date.GetCalendarDay()==(19,71,1,1),"calendar cross check overflow")
		try:
			date.SetWeekDay(None,6,8,15,1)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		date.SetWeekDay(None,6,8,15,1,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,1),"truncated century")
		date.SetWeekDay(None,6,8,15,1,baseOverflow)
		self.failUnless(date.GetWeekDay()==(20,6,8,15,1),"truncated century with overflow")
		date.SetWeekDay(None,None,8,15,1,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,1),"truncated decade")
		date.SetWeekDay(None,None,8,15,1,baseOverflow)
		self.failUnless(date.GetWeekDay()==(19,7,8,15,1),"truncated decade with overflow")
		date.SetWeekDay(None,None,None,15,1,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,1),"truncated year")
		date.SetWeekDay(None,None,None,15,1,baseOverflow)
		self.failUnless(date.GetWeekDay()==(19,6,9,15,1),"truncated year with overflow")
		date.SetWeekDay(None,None,None,None,1,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,1),"truncated week")
		date.SetWeekDay(None,None,None,None,1,baseOverflow)
		self.failUnless(date.GetWeekDay()==(19,6,8,16,1),"truncated week with overflow")		
		date.SetWeekDay(19,6,8,15,None)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,None),"week precision")
		date.SetCalendarDay(19,68,4,None)
		try:
			date.GetWeekDay()
			self.fail("month precision")			
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,6,8,None,None)
			self.fail("year precision")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,6,None,None,None)
			self.fail("decade precision")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,None,None,None,None)
			self.fail("century precision")
		except DateTimeError:
			pass
		baseOverflow.SetWeekDay(19,6,8,16,1)
		date.SetWeekDay(None,6,8,15,None,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,None),"week precision, truncated century")
		date.SetWeekDay(None,6,8,15,None,baseOverflow)
		self.failUnless(date.GetWeekDay()==(20,6,8,15,None),"week precision, truncated century with overflow")
		date.SetWeekDay(None,None,8,15,None,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,None),"week precision, truncated decade")
		date.SetWeekDay(None,None,8,15,None,baseOverflow)
		self.failUnless(date.GetWeekDay()==(19,7,8,15,None),"week precision, truncated decade with overflow")
		date.SetWeekDay(None,None,None,15,None,base)
		self.failUnless(date.GetWeekDay()==(19,6,8,15,None),"week precision, truncated year")
		date.SetWeekDay(None,None,None,15,None,baseOverflow)
		self.failUnless(date.GetWeekDay()==(19,6,9,15,None),"week precision, truncated year with overflow")
		try:
			date.SetWeekDay(None,6,8,None,None,base)
			self.fail("year precision, truncated century")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(None,6,None,None,None,base)
			self.fail("decade precision, truncated century")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(100,6,8,15,1)
			self.fail("bad century")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,10,8,15,1)
			self.fail("bad decade")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,6,10,15,1)
			self.fail("bad year")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,6,8,53,1)
			self.fail("bad week")
		except DateTimeError:
			pass
		try:
			date.SetWeekDay(19,6,8,52,8)
			self.fail("bad day")
		except DateTimeError:
			pass
	
	def testTimeTuple(self):
		"""Test Get and Set TimeTuple"""
		"""Note that a time-tuple is a 9-field tuple of:
		year
		month [1,12]
		day [1,31]
		hour [0,23]
		minute [0.59]
		second [0,61]
		weekday [0,6], Monday=0
		Julian day [1,366]
		daylight savings (0,1, or -1)
		We only deal with the first three fields and we don't allow reduced precision
		as this is not needed for interacting with the functions in the time module."""
		date=Date()
		date.SetTimeTuple([1968,4,8,None,None,None,None,None,None])
		timeTuple=[None]*9
		date.GetTimeTuple(timeTuple)
		self.failUnless(timeTuple==[1968,4,8,None,None,None,None,None,None],"simple case")
		self.failUnless(date.GetCalendarDay()==(19,68,4,8),"calendar cross-check")
		date.SetCalendarDay(19,68,4,None)
		try:
			date.GetTimeTuple(timeTuple)
			self.fail("month precision")
		except DateTimeError:
			pass
	
	def testAbsoluteDays(self):
		"""Test Get and Set Absolute Day"""
		date=Date()
		# check the 1st January each from from 0001 (the base day) through 2049
		absDay=1
		for year in xrange(1,2050):
			date.SetAbsoluteDay(absDay)
			self.failUnless(date.GetCalendarDay()==(year//100,year%100,1,1),"%04i-01-01 check"%year)
			self.failUnless(date.GetAbsoluteDay()==absDay,"%04i-01-01 symmetry check"%year)
			absDay+=365
			if (year%4==0 and (not year%100==0 or year%400==0)):
				absDay+=1
		# check each day in a sample (leap) year
		date.SetCalendarDay(19,68,1,1)
		absDay=date.GetAbsoluteDay()
		for i in xrange(366):
			date.SetAbsoluteDay(absDay)
			self.failUnless(date.GetOrdinalDay()==(19,68,i+1),"1968=%03i check"%(i+1))
			self.failUnless(date.GetAbsoluteDay()==absDay,"1968-%03i symmetry check"%(i+1))
			absDay+=1
								
	def testSetFromString(self):
		date=Date()
		date.SetFromString("19680408")
		self.failUnless(date.GetCalendarDay()==(19,68,4,8))

	def testGetPrecision(self):
		date=Date()
		date.SetCalendarDay(19,68,4,8)
		self.failUnless(date.GetPrecision()==Date.CompletePrecision,"complete precision")
		date.SetCalendarDay(19,68,4,None)
		self.failUnless(date.GetPrecision()==Date.MonthPrecision,"month precision")
		date.SetCalendarDay(19,68,None,None)
		self.failUnless(date.GetPrecision()==Date.YearPrecision,"year precision")
		date.SetCalendarDay(19,None,None,None)
		self.failUnless(date.GetPrecision()==Date.CenturyPrecision,"century precision")
		date.SetWeekDay(19,6,8,15,1)
		self.failUnless(date.GetPrecision()==Date.CompletePrecision,"complete precision (weekday)")
		date.SetWeekDay(19,6,8,15,None)
		self.failUnless(date.GetPrecision()==Date.WeekPrecision,"week precision")
	
	def testComparisons(self):
		"""Test the comparison methods"""
		self.failUnless(Date("19680408")==Date("19680408"),"simple equality")
		self.failUnless(Date("19680408")<Date("19680409"),"simple inequality")
		self.failUnless(Date("1968W15")==Date("1968W15"),"equality with week precision")
		self.failUnless(Date("1968W15")<Date("1968W16"),"inequality with week precision")
		self.failUnless(Date("1968-04")==Date("1968-04"),"equality with month precision")
		self.failUnless(Date("1968-04")<Date("1968-05"),"inequality with month precision")
		self.failUnless(Date("1968")==Date("1968"),"equality with year precision")
		self.failUnless(Date("1968")<Date("1969"),"inequality with year precision")
		self.failUnless(Date("19")==Date("19"),"equality with century precision")
		self.failUnless(Date("19")<Date("20"),"inequality with century precision")
		try:
			Date("1968-W15")==Date("1968-04")
			self.fail("precision mismatch")
		except ValueError:
			pass

	def testGetCalendarStrings(self):
		"""GetCalendarString tests"""
		self.failUnless(Date("19680408").GetCalendarString()=="1968-04-08","default test")
		self.failUnless(Date("19680408").GetCalendarString(1)=="19680408","basic test")
		self.failUnless(Date("19680408").GetCalendarString(0)=="1968-04-08","extended test")
		self.failUnless(Date("19680408").GetCalendarString(1,Date.NoTruncation)=="19680408","basic, no truncation")
		self.failUnless(Date("19680408").GetCalendarString(0,Date.NoTruncation)=="1968-04-08","extended, no truncation")
		self.failUnless(Date("19680408").GetCalendarString(1,Date.CenturyTruncation)=="680408","basic, century truncation")
		self.failUnless(Date("19680408").GetCalendarString(0,Date.CenturyTruncation)=="68-04-08","extended, century truncation")
		self.failUnless(Date("19680408").GetCalendarString(1,Date.YearTruncation)=="--0408","basic, year truncation")
		self.failUnless(Date("19680408").GetCalendarString(0,Date.YearTruncation)=="--04-08","extended, year truncation")
		self.failUnless(Date("19680408").GetCalendarString(1,Date.MonthTruncation)=="---08","basic, month truncation")
		self.failUnless(Date("19680408").GetCalendarString(0,Date.MonthTruncation)=="---08","extended, month truncation")
		self.failUnless(Date("1968-04").GetCalendarString(1,Date.NoTruncation)=="1968-04","basic, month precision, no truncation")
		self.failUnless(Date("1968-04").GetCalendarString(0,Date.NoTruncation)=="1968-04","extended, month precision, no truncation")
		self.failUnless(Date("1968-04").GetCalendarString(1,Date.CenturyTruncation)=="-6804","basic, month precision, century truncation")
		self.failUnless(Date("1968-04").GetCalendarString(0,Date.CenturyTruncation)=="-68-04","extended, month precision, century truncation")
		self.failUnless(Date("1968-04").GetCalendarString(1,Date.YearTruncation)=="--04","basic, month precision, year truncation")
		self.failUnless(Date("1968-04").GetCalendarString(0,Date.YearTruncation)=="--04","extended, month precision, year truncation")
		self.failUnless(Date("1968").GetCalendarString(1,Date.NoTruncation)=="1968","basic, year precision, no truncation")
		self.failUnless(Date("1968").GetCalendarString(0,Date.NoTruncation)=="1968","extended, year precision, no truncation")
		self.failUnless(Date("1968").GetCalendarString(1,Date.CenturyTruncation)=="-68","basic, year precision, century truncation")
		self.failUnless(Date("1968").GetCalendarString(0,Date.CenturyTruncation)=="-68","extended, year precision, century truncation")
		self.failUnless(Date("19").GetCalendarString(1,Date.NoTruncation)=="19","basic, century precision, no truncation")
		self.failUnless(Date("19").GetCalendarString(0,Date.NoTruncation)=="19","extended, century precision, no truncation")
	
	def testGetOrdinalStrings(self):
		"""GetOrdinalString tests"""
		self.failUnless(Date("1968-099").GetOrdinalString()=="1968-099","default test")
		self.failUnless(Date("1968-099").GetOrdinalString(1)=="1968099","basic test")
		self.failUnless(Date("1968-099").GetOrdinalString(0)=="1968-099","extended test")
		self.failUnless(Date("1968-099").GetOrdinalString(1,Date.NoTruncation)=="1968099","basic, no truncation")
		self.failUnless(Date("1968-099").GetOrdinalString(0,Date.NoTruncation)=="1968-099","extended, no truncation")
		self.failUnless(Date("1968-099").GetOrdinalString(1,Date.CenturyTruncation)=="68099","basic, century truncation")
		self.failUnless(Date("1968-099").GetOrdinalString(0,Date.CenturyTruncation)=="68-099","extended, century truncation")
		self.failUnless(Date("1968-099").GetOrdinalString(1,Date.YearTruncation)=="-099","basic, year truncation")
		self.failUnless(Date("1968-099").GetOrdinalString(0,Date.YearTruncation)=="-099","extended, year truncation")
		self.failUnless(Date("1968").GetOrdinalString(1,Date.NoTruncation)=="1968","basic, year precision, no truncation")
		self.failUnless(Date("1968").GetOrdinalString(0,Date.NoTruncation)=="1968","extended, year precision, no truncation")
		self.failUnless(Date("1968").GetOrdinalString(1,Date.CenturyTruncation)=="-68","basic, year precision, century truncation")
		self.failUnless(Date("1968").GetOrdinalString(0,Date.CenturyTruncation)=="-68","extended, year precision, century truncation")
		self.failUnless(Date("19").GetOrdinalString(1,Date.NoTruncation)=="19","basic, century precision, no truncation")
		self.failUnless(Date("19").GetOrdinalString(0,Date.NoTruncation)=="19","extended, century precision, no truncation")
			
	def testGetWeekStrings(self):
		"""GetWeekString tests"""
		self.failUnless(Date("1968-W15-1").GetWeekString()=="1968-W15-1","default test")
		self.failUnless(Date("1968-W15-1").GetWeekString(1)=="1968W151","basic test")
		self.failUnless(Date("1968-W15-1").GetWeekString(0)=="1968-W15-1","extended test")
		self.failUnless(Date("1968-W15-1").GetWeekString(1,Date.NoTruncation)=="1968W151","basic, no truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(0,Date.NoTruncation)=="1968-W15-1","extended, no truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(1,Date.CenturyTruncation)=="68W151","basic, century truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(0,Date.CenturyTruncation)=="68-W15-1","extended, century truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(1,Date.DecadeTruncation)=="-8W151","basic, decade truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(0,Date.DecadeTruncation)=="-8-W15-1","extended, decade truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(1,Date.YearTruncation)=="-W151","basic, year truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(0,Date.YearTruncation)=="-W15-1","extended, year truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(1,Date.WeekTruncation)=="-W-1","basic, week truncation")
		self.failUnless(Date("1968-W15-1").GetWeekString(0,Date.WeekTruncation)=="-W-1","extended, week truncation")
		self.failUnless(Date("1968-W15").GetWeekString(1,Date.NoTruncation)=="1968W15","basic, week precision, no truncation")
		self.failUnless(Date("1968-W15").GetWeekString(0,Date.NoTruncation)=="1968-W15","extended, week precision, no truncation")
		self.failUnless(Date("1968-W15").GetWeekString(1,Date.CenturyTruncation)=="68W15","basic, week precision, century truncation")
		self.failUnless(Date("1968-W15").GetWeekString(0,Date.CenturyTruncation)=="68-W15","extended, week precision, century truncation")
		self.failUnless(Date("1968-W15").GetWeekString(1,Date.DecadeTruncation)=="-8W15","basic, week precision, decade truncation")
		self.failUnless(Date("1968-W15").GetWeekString(0,Date.DecadeTruncation)=="-8-W15","extended, week precision, decade truncation")
		self.failUnless(Date("1968-W15").GetWeekString(1,Date.YearTruncation)=="-W15","basic, week precision, year truncation")
		self.failUnless(Date("1968-W15").GetWeekString(0,Date.YearTruncation)=="-W15","extended, week precision, year truncation")
		self.failUnless(Date("1968").GetWeekString(1,Date.NoTruncation)=="1968","basic, year precision, no truncation")
		self.failUnless(Date("1968").GetWeekString(0,Date.NoTruncation)=="1968","extended, year precision, no truncation")
		self.failUnless(Date("1968").GetWeekString(1,Date.CenturyTruncation)=="-68","basic, year precision, century truncation")
		self.failUnless(Date("1968").GetWeekString(0,Date.CenturyTruncation)=="-68","extended, year precision, century truncation")
		self.failUnless(Date("19").GetWeekString(1,Date.NoTruncation)=="19","basic, century precision, no truncation")
		self.failUnless(Date("19").GetWeekString(0,Date.NoTruncation)=="19","extended, century precision, no truncation")
	
	def testNow(self):
		# This is a weak test
		date=Date()
		date.Now()
		self.failUnless(date>"20050313","now test")


class TimeTests(unittest.TestCase):
	def testConstructor(self):
		t=Time()
		self.failUnless(t.GetTime()==(0,0,0),"empty constructor")
		tBase=Time()
		tBase.SetTime(23,20,50)
		t=Time(tBase)
		self.failUnless(t.GetTime()==(23,20,50),"copy constructor")
		t=Time("232050")
		self.failUnless(t.GetTime()==(23,20,50),"string constructor")
		t=Time(u"23:20:50")
		self.failUnless(t.GetTime()==(23,20,50),"unicode constructor")
		t=Time("-2050",tBase)
		self.failUnless(t.GetTime()==(23,20,50),"truncated hour")
		tBase.SetTime(23,20,30)
		tBase.SetZone(+1,1,None)
		t=Time(tBase)
		self.failUnless(t.GetTime()==(23,20,30) and t.GetZone()==(+1,60),"check zone copy on constructor")
	
	def testTime(self):
		"""Test Get and Set time methods"""
		t=Time()
		tBase=Time()
		tBaseOverflow=Time()
		tBase.SetTime(23,20,50)
		tBaseOverflow.SetTime(23,20,51)
		overflow=t.SetTime(23,20,50)
		self.failUnless(t.GetTime()==(23,20,50) and not overflow,"simple case")
		overflow=t.SetTime(23,20,50.5)
		self.failUnless(t.GetTime()==(23,20,50.5) and not overflow,"fractional seconds")
		try:
			t.SetTime(None,20,50)
			self.fail("truncation without base")
		except DateTimeError:
			pass
		overflow=t.SetTime(None,20,50,tBase)
		self.failUnless(t.GetTime()==(23,20,50) and not overflow,"truncated hour")
		overflow=t.SetTime(None,20,50,tBaseOverflow)
		self.failUnless(t.GetTime()==(0,20,50) and overflow,"truncated hour with overflow")
		overflow=t.SetTime(None,None,50,tBase)
		self.failUnless(t.GetTime()==(23,20,50) and not overflow,"truncated minute")
		overflow=t.SetTime(None,None,50,tBaseOverflow)
		self.failUnless(t.GetTime()==(23,21,50) and not overflow,"truncated minute with overflow")
		overflow=t.SetTime(23,20,None)
		self.failUnless(t.GetTime()==(23,20,None) and not overflow,"minute precision")
		overflow=t.SetTime(23,20.8,None)
		self.failUnless(t.GetTime()==(23,20.8,None) and not overflow,"fractional minute precision")
		overflow=t.SetTime(23,None,None)
		self.failUnless(t.GetTime()==(23,None,None) and not overflow,"hour precision")
		overflow=t.SetTime(23.3,None,None)
		self.failUnless(t.GetTime()==(23.3,None,None) and not overflow,"fractional hour precision")
		tBaseOverflow.SetTime(23,21,0)
		overflow=t.SetTime(None,20,None,tBase)
		self.failUnless(t.GetTime()==(23,20,None) and not overflow,"minute precision, truncated hour")
		overflow=t.SetTime(None,20,None,tBaseOverflow)
		self.failUnless(t.GetTime()==(0,20,None) and overflow,"minute precision, truncated hour with overflow")
		overflow=t.SetTime(24,0,0.0)
		self.failUnless(t.GetTime()==(24,0,0) and not overflow,"midnight alternate representation")
		try:
			t.SetTime(25,20,50)
			self.fail("bad hour")
		except DateTimeError:
			pass
		try:
			t.SetTime(23.3,20,50)
			self.fail("bad fractional hour")
		except DateTimeError:
			pass
		try:
			t.SetTime(0,60,50)
			self.fail("bad minute")
		except DateTimeError:
			pass
		try:
			t.SetTime(0,59,61)
			self.fail("bad second")
		except DateTimeError:
			pass
		try:
			t.SetTime(24,0,0.5)
			self.fail("bad midnight")
		except DateTimeError:
			pass
	
	def testTimeZone(self):
		"""Test Get and Set TimeZone and correct copy behaviour"""
		t=Time()
		self.failUnless(t.GetZone()==(None,None),"unknown zone")
		t.SetZone(0)
		self.failUnless(t.GetZone()==(0,0),"UTC")
		t.SetZone(+1,0,0)
		self.failUnless(t.GetZone()==(+1,0),"UTC, positive offset form")
		t.SetZone(-1,0,0)
		self.failUnless(t.GetZone()==(-1,0),"UTC, negative offset form")
		t.SetTime(15,27,46)
		t.SetZone(+1,1,0)
		self.failUnless(t.GetZone()==(+1,60),"plus one hour")
		t.SetZone(-1,5,0)
		self.failUnless(t.GetZone()==(-1,300),"minus five hours")
		t.SetZone(+1,1,None)
		self.failUnless(t.GetZone()==(+1,60),"plus one hour, hour precision")
		t.SetZone(-1,5,None)
		self.failUnless(t.GetZone()==(-1,300),"minus five hours, hour precision")
		tBase=Time()
		tBase.SetTime(23,20,30)
		tBase.SetZone(+1,1)
		t.SetTime(None,20,30,tBase)
		self.failUnless(t.GetZone()==(+1,60),"zone copy on SetTime with truncation")
		t.SetZone(-1,5)
		t.SetTime(23,20,30,tBase)
		self.failUnless(t.GetZone()==(-1,300),"no zone copy on SetTime without truncation")
		try:
			t.SetZone(-2,3)
			self.fail("bad direction")
		except DateTimeError:
			pass
		try:
			t.SetZone(+1,None,None)
			self.fail("bad offset")
		except DateTimeError:
			pass
		try:
			t.SetZone(-1,24,0)
			self.fail("large offset")
		except DateTimeError:
			pass

	def testTimeTuple(self):
		"""Test Get and Set TimeTuple"""
		"""To refresh, a time-tuple is a 9-field tuple of:
		year
		month [1,12]
		day [1,31]
		hour [0,23]
		minute [0.59]
		second [0,61]
		weekday [0,6], Monday=0
		Julian day [1,366]
		daylight savings (0,1, or -1)
		"""
		t=Time()
		t.SetTimeTuple([1968,4,8,23,20,50,None,None,None])
		timeTuple=[None]*9
		t.GetTimeTuple(timeTuple)
		self.failUnless(timeTuple==[None,None,None,23,20,50,None,None,None],"simple case")
		self.failUnless(t.GetTime()==(23,20,50),"time cross-check")
		t.SetTime(23,20,None)
		try:
			t.GetTimeTuple(timeTuple)
			self.fail("minute precision")
		except DateTimeError:
			pass
	
	def testSeconds(self):
		"""Test Get and Set seconds"""
		self.failUnless(Time("000000").GetSeconds()==0,"zero test")
		self.failUnless(Time("232050").GetSeconds()==84050,"sample test")
		self.failUnless(Time("240000").GetSeconds()==86400,"full day")
		# leap second is equivalent to the second before, not the second after!
		self.failUnless(Time("235960").GetSeconds()==86399,"leap second before midnight")
		t=Time()
		overflow=t.SetSeconds(0)
		self.failUnless(t.GetTime()==(0,0,0) and not overflow,"set zero")
		overflow=t.SetSeconds(84050)
		self.failUnless(t.GetTime()==(23,20,50) and not overflow,"set sample time")
		overflow=t.SetSeconds(84050.5)
		self.failUnless(t.GetTime()==(23,20,50.5) and not overflow,"set sample time with fraction")
		overflow=t.SetSeconds(86400)
		self.failUnless(t.GetTime()==(0,0,0) and overflow==1,"set midnight end of day")
		overflow=t.SetSeconds(688850)
		self.failUnless(t.GetTime()==(23,20,50) and overflow==7,"set sample time next week")
		overflow=t.SetSeconds(-520750)
		self.failUnless(t.GetTime()==(23,20,50) and overflow==-7,"set sample time last week")
				
	def testGetStrings(self):
		"""GetString tests"""
		self.failUnless(Time("232050").GetString()=="23:20:50","default test")
		self.failUnless(Time("232050").GetString(1)=="232050","basic test")
		self.failUnless(Time("232050").GetString(0)=="23:20:50","extended test")
		self.failUnless(Time("232050").GetString(1,Time.NoTruncation)=="232050","basic, no truncation")
		self.failUnless(Time("232050").GetString(0,Time.NoTruncation)=="23:20:50","extended, no truncation")
		self.failUnless(Time("232050,5").GetString(1,Time.NoTruncation)=="232050","basic, fractional seconds, default decimals")
		self.failUnless(Time("232050,5").GetString(1,Time.NoTruncation,1)=="232050,5","basic, fractional seconds")
		self.failUnless(Time("232050,5").GetString(1,Time.NoTruncation,-1)=="232050.5","basic, fractional seconds, alt point")
		self.failUnless(Time("232050,567").GetString(0,Time.NoTruncation,2)=="23:20:50,56","extended, fractional seconds with decimals")
		self.failUnless(Time("232050,567").GetString(0,Time.NoTruncation,-2)=="23:20:50.56","extended, fractional seconds with decimals and alt point")
		self.failUnless(Time("232050").GetString(1,Time.HourTruncation)=="-2050","basic, hour truncation")
		self.failUnless(Time("232050").GetString(0,Time.HourTruncation)=="-20:50","extended, hour truncation")
		self.failUnless(Time("232050").GetString(1,Time.MinuteTruncation)=="--50","basic, minute truncation")
		self.failUnless(Time("232050").GetString(0,Time.MinuteTruncation)=="--50","extended, minute truncation")
		self.failUnless(Time("2320").GetString(1,Time.NoTruncation)=="2320","basic, minute precision, no truncation")
		self.failUnless(Time("2320").GetString(0,Time.NoTruncation)=="23:20","extended, minute precision, no truncation")
		self.failUnless(Time("2320,8").GetString(1,Time.NoTruncation,3)=="2320,800","basic, fractional minute precision, no truncation")
		self.failUnless(Time("2320,895").GetString(0,Time.NoTruncation,3)=="23:20,895","extended, fractinoal minute precision, no truncation")
		self.failUnless(Time("23").GetString(1,Time.NoTruncation)=="23","basic, hour precision, no truncation")
		self.failUnless(Time("23").GetString(0,Time.NoTruncation)=="23","extended, hour precision, no truncation")
		self.failUnless(Time("23,3").GetString(1,Time.NoTruncation,3)=="23,300","basic, fractional hour precision")
		self.failUnless(Time("23,345").GetString(0,Time.NoTruncation,3)=="23,345","extended, fractinoal hour precision")
		self.failUnless(Time("2320").GetString(1,Time.HourTruncation)=="-20","basic, minute precision, hour truncation")
		self.failUnless(Time("2320").GetString(0,Time.HourTruncation)=="-20","extended, minute precision, hour truncation")
		self.failUnless(Time("2320,8").GetString(1,Time.HourTruncation,3)=="-20,800","basic, fractional minute precision, hour truncation")
		self.failUnless(Time("152746+0100").GetString()=="15:27:46+01:00","default test with zone offset")
		self.failUnless(Time("152746+0100").GetString(1)=="152746+0100","basic test with zone offset")
		self.failUnless(Time("152746+0100").GetString(0)=="15:27:46+01:00","extended test with zone offset")
		self.failUnless(Time("232030Z").GetString(1)=="232030Z","basic test with Z")
		self.failUnless(Time("232030Z").GetString(0)=="23:20:30Z","extended test with Z")
		self.failUnless(Time("152746-0500").GetString(0,Time.NoTruncation,0,Time.ZoneHourPrecision)=="15:27:46-05",
			"extended test with zone hour precision")
		
	def testSetFromString(self):
		"""Test the basic SetFromString method (exercised more fully by parser tests)"""
		t=Time()
		t.SetFromString("232050")
		self.failUnless(t.GetTime()==(23,20,50))
	
	def testGetPrecision(self):
		"""Test the precision constants"""
		t=Time()
		t.SetTime(23,20,50)
		self.failUnless(t.GetPrecision()==Time.CompletePrecision,"complete precision")
		t.SetTime(23,20,None)
		self.failUnless(t.GetPrecision()==Time.MinutePrecision,"minute precision")
		t.SetTime(23,None,None)
		self.failUnless(t.GetPrecision()==Time.HourPrecision,"hour precision")
	
	def testSetPrecision(self):
		"""Test the setting of the precision"""
		t=Time()
		t.SetTime(23,20,50)
		t.SetPrecision(Time.MinutePrecision)
		h,m,s=t.GetTime()
		self.failUnless((h,"%f"%m,s)==(23,"20.833333",None),"reduce to minute precision")
		t.SetPrecision(Time.HourPrecision)
		h,m,s=t.GetTime()
		self.failUnless(("%f"%h,m,s)==("23.347222",None,None),"reduce to hour precision")
		t.SetPrecision(Time.MinutePrecision)
		h,m,s=t.GetTime()
		self.failUnless((h,"%f"%m,s)==(23,"20.833333",None),"extend to minute precision")
		t.SetPrecision(Time.CompletePrecision)
		h,m,s=t.GetTime()
		self.failUnless((h,m,"%f"%s)==(23,20,"50.000000"),"extend to complete precision")
		t.SetTime(23,20,50)
		t.SetPrecision(Time.MinutePrecision,1)
		self.failUnless(t.GetTime()==(23,20,None),"reduce to integer minute precision")
		t.SetPrecision(Time.HourPrecision,1)
		self.failUnless(t.GetTime()==(23,None,None),"reduce to integer hour precision")
		t.SetPrecision(Time.MinutePrecision,1)
		self.failUnless(t.GetTime()==(23,0,None),"extend to integer minute precision")
		t.SetPrecision(Time.CompletePrecision,1)
		self.failUnless(t.GetTime()==(23,0,0),"extend to integer complete precision")
		t.SetTime(23,20,50.5)
		t.SetPrecision(Time.CompletePrecision,1)
		self.failUnless(t.GetTime()==(23,20,50),"integer complete precision")
		t.SetTime(23,20.8,None)
		t.SetPrecision(Time.MinutePrecision,1)
		self.failUnless(t.GetTime()==(23,20,None),"integer minute precision")
		t.SetTime(23.3,None,None)
		t.SetPrecision(Time.HourPrecision,1)
		self.failUnless(t.GetTime()==(23,None,None),"integer hour precision")
		
	def testComparisons(self):
		"""Test the comparison methods"""
		self.failUnless(Time("232050")==Time("232050"),"simple equality")
		self.failUnless(Time("232050")<Time("232051"),"simple inequality")
		self.failUnless(Time("2320")==Time("2320"),"equality with minute precision")
		self.failUnless(Time("2320")<Time("2321"),"inequality with minute precision")
		self.failUnless(Time("23")==Time("23"),"equality with hour precision")
		self.failUnless(Time("23")<Time("24"),"inequality with hour precision")
		self.failUnless(Time("232050Z")==Time("232050Z"),"simple equality with matching zone")
		self.failUnless(Time("232050Z")<Time("232051Z"),"simple inequality with matching zone")
		self.failUnless(Time("222050Z")==Time("232050+01"),"simple equality with non matching zone")
		self.failUnless(Time("232050Z")>Time("232050+01"),"simple inequality with non matching zone")
		self.failUnless(Time("232050Z")<Time("232050-01"),"inequality with non matching zone and overflow")
		try:
			Time("232050")==Time("2320")
			self.fail("precision mismatch")
		except ValueError:
			pass
		try:
			Time("232050Z")==Time("232050")
			self.fail("zone unspecified mismatch")
		except ValueError:
			pass

	def testNow(self):
		# A very weak test, how do we know the real time?
		t=Time()
		t.Now()

		
class TimePointTests(unittest.TestCase):
	def setUp(self):
		pass
			
	def tearDown(self):
		pass

	def testConstructor(self):
		t=TimePoint()
		self.failUnless(t.GetCalendarTimePoint()==(0,1,1,1,0,0,0) and t.time.GetZone()==(None,None),"empty constructor")
		base=TimePoint()
		base.date.SetCalendarDay(19,68,4,8)
		base.time.SetTime(23,20,50)
		base.time.SetZone(0)
		t=TimePoint(base)
		self.failUnless(t.time.GetTime()==(23,20,50) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,68,4,8),"copy constructor")
		t=TimePoint("19680408T232050Z")
		self.failUnless(t.time.GetTime()==(23,20,50) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,68,4,8),"string constructor")
		t=TimePoint(u"19680408T232050Z")
		self.failUnless(t.time.GetTime()==(23,20,50) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,68,4,8),"unicode constructor")
		base=Date(t.date)
		t=TimePoint("--0408T232050Z",base)
		self.failUnless(t.time.GetTime()==(23,20,50) and t.time.GetZone()==(0,0) and
			t.date.GetCalendarDay()==(19,68,4,8),"truncated year")

	def testGetStrings(self):
		"""GetString tests"""
		self.failUnless(TimePoint("19680408T232050Z").GetCalendarString()=="1968-04-08T23:20:50Z","default test")
		self.failUnless(TimePoint("19680408T232050+0100").GetCalendarString(1)=="19680408T232050+0100","basic test")
		self.failUnless(TimePoint("19680408T232050+0100").GetCalendarString(0)=="1968-04-08T23:20:50+01:00","extended test")
		self.failUnless(TimePoint("19680408T232050").GetCalendarString(1,Date.NoTruncation)=="19680408T232050","basic, no truncation")
		self.failUnless(TimePoint("19680408T232050").GetCalendarString(0,Date.NoTruncation)=="1968-04-08T23:20:50","extended, no truncation")
		self.failUnless(TimePoint("19680408T232050").GetCalendarString(1,Date.MonthTruncation)=="---08T232050","basic, month truncation")
		self.failUnless(TimePoint("19680408T232050").GetCalendarString(0,Date.MonthTruncation)=="---08T23:20:50","extended, month truncation")
		self.failUnless(TimePoint("19680408T232050+0100").GetCalendarString(0,Date.NoTruncation,3,Time.ZoneHourPrecision)==
			"1968-04-08T23:20:50,000+01","fractional seconds and time zone precision control")
		self.failUnless(TimePoint("19680408T232050Z").GetOrdinalString()=="1968-099T23:20:50Z","default ordinal test")
		self.failUnless(TimePoint("19680408T232050Z").GetOrdinalString(1)=="1968099T232050Z","basic ordinal test")
		self.failUnless(TimePoint("19680408T232050Z").GetOrdinalString(0)=="1968-099T23:20:50Z","extended ordinal test")
		self.failUnless(TimePoint("19680408T232050Z").GetOrdinalString(1,Date.NoTruncation)=="1968099T232050Z","basic ordinal, no truncation")
		self.failUnless(TimePoint("19680408T232050Z").GetOrdinalString(0,Date.NoTruncation)=="1968-099T23:20:50Z","extended ordinal, no truncation")
		self.failUnless(TimePoint("19680408T232050Z").GetWeekString()=="1968-W15-1T23:20:50Z","default week test")
		self.failUnless(TimePoint("19680408T232050Z").GetWeekString(1)=="1968W151T232050Z","basic week test")
		self.failUnless(TimePoint("19680408T232050Z").GetWeekString(0)=="1968-W15-1T23:20:50Z","extended week test")
		self.failUnless(TimePoint("19680408T232050Z").GetWeekString(1,Date.NoTruncation)=="1968W151T232050Z","basic week, no truncation")
		self.failUnless(TimePoint("19680408T232050Z").GetWeekString(0,Date.NoTruncation)=="1968-W15-1T23:20:50Z","extended week, no truncation")

	def testComparisons(self):
		"""Test the comparison methods"""
		self.failUnless(TimePoint("19680408T232050")==TimePoint("19680408T232050"),"simple equality")
		self.failUnless(TimePoint("19680408T232050")<TimePoint("19680408T232051"),"simple inequality")
		self.failUnless(TimePoint("19680407T232051")<TimePoint("19680408T232050"),"whole day inequality")
		self.failUnless(TimePoint("19680408T2320")==TimePoint("19680408T2320"),"equality with minute precision")
		self.failUnless(TimePoint("19680408T232050Z")==TimePoint("19680408T232050Z"),"simple equality with matching zone")
		self.failUnless(TimePoint("19680408T232050Z")<TimePoint("19680408T232051Z"),"simple inequality with matching zone")
		self.failUnless(TimePoint("19680408T222050Z")==TimePoint("19680408T232050+01"),"simple equality with non matching zone")
		self.failUnless(TimePoint("19680408T232050Z")>TimePoint("19680408T232050+01"),"simple inequality with non matching zone")
		self.failUnless(TimePoint("19680408T232050Z")<TimePoint("19680408T232050-01"),"inequality with non matching zone and overflow")
		try:
			TimePoint("19680408T232050")==TimePoint("19680408T2320")
			self.fail("precision mismatch")
		except ValueError:
			pass
		try:
			TimePoint("19680408T232050Z")==TimePoint("19680408T232050")
			self.fail("zone unspecified mismatch")
		except ValueError:
			pass


class DurationTests(unittest.TestCase):
	def testConstructor(self):
		"""Duration constructor tests."""
		d=Duration()
		self.failUnless(d.GetCalendarDuration()==(0,0,0,0,0,0),"empty constructor")
		dCopy=Duration()
		dCopy.SetCalendarDuration(36,11,13,10,5,0)
		d=Duration(dCopy)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5,0),"copy constructor")
		d=Duration("P36Y11M13DT10H5M0S")
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5,0),"string constructor")
		d=Duration(u"P36Y11M13DT10H5M0S")
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5,0),"unicode constructor")

	def testCalendarDuration(self):
		"""Test Get and Set Calendar Durations"""
		d=Duration()
		d.SetCalendarDuration(36,11,13,10,5,0)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5,0),"simple case")
		d.SetCalendarDuration(36,11,13,10,5,0.5)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5,0.5),"fractional seconds")
		d.SetCalendarDuration(36,11,13,10,5,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5,None),"minute precision")
		d.SetCalendarDuration(36,11,13,10,5.5,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,5.5,None),"fractional minutes")
		d.SetCalendarDuration(36,11,13,10,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10,None,None),"hour precision")
		d.SetCalendarDuration(36,11,13,10.5,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,10.5,None,None),"fractional hours")
		d.SetCalendarDuration(36,11,13,None,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,13,None,None,None),"day precision")
		d.SetCalendarDuration(36,11,13.5,None,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,13.5,None,None,None),"fractional days")
		d.SetCalendarDuration(36,11,None,None,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,11,None,None,None,None),"month precision")
		d.SetCalendarDuration(36,11.5,None,None,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,11.5,None,None,None,None),"fractional months")
		d.SetCalendarDuration(36,None,None,None,None,None)
		self.failUnless(d.GetCalendarDuration()==(36,None,None,None,None,None),"year precision")
		d.SetCalendarDuration(36.5,None,None,None,None,None)
		self.failUnless(d.GetCalendarDuration()==(36.5,None,None,None,None,None),"fractional years")
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
		self.failUnless(d.GetWeekDuration()==45,"simple case")
		d.SetWeekDuration(45.5)
		self.failUnless(d.GetWeekDuration()==45.5,"fractional case")
		d.SetCalendarDuration(36,11,13,10,5,0)
		try:
			d.GetWeekDuration()
			self.fail("calendar mode")
		except DateTimeError:
			pass
			
	def testGetStrings(self):
		"""Test the GetString method."""
		self.failUnless(Duration("P36Y11M13DT10H5M0S").GetString()=="P36Y11M13DT10H5M0S","complete, default")
		self.failUnless(Duration("P36Y11M13DT10H5M0S").GetString(1)=="P36Y11M13DT10H5M0S","complete, no truncation")
		self.failUnless(Duration().GetString(0)=="P0Y0M0DT0H0M0S","complete zero")
		self.failUnless(Duration().GetString(1)=="PT0S","complete zero with truncation")
		self.failUnless(Duration("P0Y0M0DT0H").GetString(1)=="PT0H","hour precision zero with truncation")
		self.failUnless(Duration("P0Y0M0DT0H").GetString(0)=="P0Y0M0DT0H","hour precision zero without truncation")
		self.failUnless(Duration("P0Y11M13DT10H5M0S").GetString(1)=="P11M13DT10H5M0S","year truncation")
		self.failUnless(Duration("P0Y0M13DT10H5M0S").GetString(1)=="P13DT10H5M0S","month truncation")
		self.failUnless(Duration("P0Y0M0DT10H5M0S").GetString(1)=="PT10H5M0S","day truncation")
		self.failUnless(Duration("P0Y0M0DT0H5M0S").GetString(1)=="PT5M0S","hour truncation")
		self.failUnless(Duration("P0Y0M0DT0H5M").GetString(1)=="PT5M","hour truncation, minute precision")
		self.failUnless(Duration("P36Y11M13DT10H5M0,5S").GetString(0)=="P36Y11M13DT10H5M0S","removal of fractional seconds")
		self.failUnless(Duration("P36Y11M13DT10H5M0,5S").GetString(0,3)=="P36Y11M13DT10H5M0,500S","display of fractional seconds")
		self.failUnless(Duration("P36Y11M13DT10H5M0S").GetString(0,3)=="P36Y11M13DT10H5M0S","missing fractional seconds")
		self.failUnless(Duration("P36Y11M13DT10H5M0,5S").GetString(0,-3)=="P36Y11M13DT10H5M0.500S","display of fractional seconds alt format")
		self.failUnless(Duration("P36Y11M13DT10H5M").GetString(0)=="P36Y11M13DT10H5M","minute precision")
		self.failUnless(Duration("P36Y11M13DT10H5,0M").GetString(0)=="P36Y11M13DT10H5M","removal of fractional minutes")
		self.failUnless(Duration("P36Y11M13DT10H5,0M").GetString(0,2)=="P36Y11M13DT10H5,00M","fractional minute precision")
		self.failUnless(Duration("P36Y11M13DT10H5,0M").GetString(0,-2)=="P36Y11M13DT10H5.00M","fractional minute precision alt format")
		self.failUnless(Duration("P36Y11M13DT10H").GetString(0)=="P36Y11M13DT10H","hour precision")
		self.failUnless(Duration("P36Y11M13DT10,08H").GetString(0)=="P36Y11M13DT10H","removal of fractional hours")
		self.failUnless(Duration("P36Y11M13DT10,08H").GetString(0,1)=="P36Y11M13DT10,0H","fractional hour precision")
		self.failUnless(Duration("P36Y11M13DT10,08H").GetString(0,-1)=="P36Y11M13DT10.0H","fractional hour precision alt format")
		self.failUnless(Duration("P36Y11M13D").GetString(0)=="P36Y11M13D","day precision")
		self.failUnless(Duration("P36Y11M13,420D").GetString(0)=="P36Y11M13D","removal of fractional days")
		self.failUnless(Duration("P36Y11M13,420D").GetString(0,4)=="P36Y11M13,4200D","fractional day precision")
		self.failUnless(Duration("P36Y11M13,420D").GetString(0,-4)=="P36Y11M13.4200D","fractional day precision alt format")
		self.failUnless(Duration("P36Y11M").GetString(0)=="P36Y11M","month precision")
		self.failUnless(Duration("P36Y11,427M").GetString(0)=="P36Y11M","removal of fractional month")
		self.failUnless(Duration("P36Y11,427M").GetString(0,2)=="P36Y11,42M","fractional month precision")
		self.failUnless(Duration("P36Y11,427M").GetString(0,-2)=="P36Y11.42M","fractional month precision alt format")
		self.failUnless(Duration("P36Y").GetString(0)=="P36Y","year precision")
		self.failUnless(Duration("P36,95Y").GetString(0)=="P36Y","removal of fractional year")
		self.failUnless(Duration("P36,95Y").GetString(0,1)=="P36,9Y","fractional year precision")
		self.failUnless(Duration("P36,95Y").GetString(0,-1)=="P36.9Y","fractional year precision alt format")
		
	def testComparisons(self):
		"""Test the comparison methods"""
		self.failUnless(Duration("P36Y11M13DT10H5M0S")==Duration("P36Y11M13DT10H5M0S"),"simple equality")
		self.failUnless(Duration("P11M13DT10H5M0S")==Duration("P0Y11M13DT10H5M0S"),"missing years")
		
		
		
class ParserTests(unittest.TestCase):
	def setUp(self):
		pass
		
	def testDateParser(self):
		date=Date()
		base=Date()
		base.SetCalendarDay(19,85,04,12)
		self.failUnless(date.SetFromString("19850412",base)=="YYYYMMDD")
		self.failUnless(date.SetFromString("1985-04-12",base)=="YYYY-MM-DD")
		self.failUnless(date.SetFromString("1985-04",base)=="YYYY-MM")
		self.failUnless(date.SetFromString("1985",base)=="YYYY")
		self.failUnless(date.SetFromString("19",base)=="YY")
		self.failUnless(date.SetFromString("850412",base)=="YYMMDD")
		self.failUnless(date.SetFromString("85-04-12",base)=="YY-MM-DD")
		self.failUnless(date.SetFromString("-8504",base)=="-YYMM")
		self.failUnless(date.SetFromString("-85-04",base)=="-YY-MM")
		self.failUnless(date.SetFromString("-85",base)=="-YY")
		self.failUnless(date.SetFromString("--0412",base)=="--MMDD")
		self.failUnless(date.SetFromString("--04-12",base)=="--MM-DD")
		self.failUnless(date.SetFromString("--04",base)=="--MM")
		self.failUnless(date.SetFromString("---12",base)=="---DD")
		self.failUnless(date.SetFromString("1985102",base)=="YYYYDDD")
		self.failUnless(date.SetFromString("1985-102",base)=="YYYY-DDD")
		self.failUnless(date.SetFromString("85102",base)=="YYDDD")
		self.failUnless(date.SetFromString("85-102",base)=="YY-DDD")
		self.failUnless(date.SetFromString("-102",base)=="-DDD")
		self.failUnless(date.SetFromString("1985W155",base)=="YYYYWwwD")
		self.failUnless(date.SetFromString("1985-W15-5",base)=="YYYY-Www-D")
		self.failUnless(date.SetFromString("1985W15",base)=="YYYYWww")
		self.failUnless(date.SetFromString("1985-W15",base)=="YYYY-Www")
		self.failUnless(date.SetFromString("85W155",base)=="YYWwwD")
		self.failUnless(date.SetFromString("85-W15-5",base)=="YY-Www-D")
		self.failUnless(date.SetFromString("85W15",base)=="YYWww")
		self.failUnless(date.SetFromString("85-W15",base)=="YY-Www")
		self.failUnless(date.SetFromString("-5W155",base)=="-YWwwD")
		self.failUnless(date.SetFromString("-5-W15-5",base)=="-Y-Www-D")
		self.failUnless(date.SetFromString("-5W15",base)=="-YWww")
		self.failUnless(date.SetFromString("-5-W15",base)=="-Y-Www")
		self.failUnless(date.SetFromString("-W155",base)=="-WwwD")
		self.failUnless(date.SetFromString("-W15-5",base)=="-Www-D")
		self.failUnless(date.SetFromString("-W15",base)=="-Www")
		self.failUnless(date.SetFromString("-W-5",base)=="-W-D")
	
	def testTimeParser(self):
		t=Time()
		base=Time()
		base.SetTime(23,20,50)
		self.failUnless(t.SetFromString("232050",base)=="hhmmss")
		self.failUnless(t.SetFromString("23:20:50",base)=="hh:mm:ss")
		self.failUnless(t.SetFromString("2320",base)=="hhmm")
		self.failUnless(t.SetFromString("23:20",base)=="hh:mm")
		self.failUnless(t.SetFromString("23",base)=="hh")
		self.failUnless(t.SetFromString("232050,5",base)=="hhmmss,s")
		self.failUnless(t.SetFromString("232050.50",base)=="hhmmss.s")
		self.failUnless(t.SetFromString("23:20:50,5",base)=="hh:mm:ss,s")
		self.failUnless(t.SetFromString("2320,8",base)=="hhmm,m")
		self.failUnless(t.SetFromString("2320.80",base)=="hhmm.m")
		self.failUnless(t.SetFromString("23:20,8",base)=="hh:mm,m")
		self.failUnless(t.SetFromString("23,3",base)=="hh,h")
		self.failUnless(t.SetFromString("23.80",base)=="hh.h")
		self.failUnless(t.SetFromString("-2050",base)=="-mmss")
		self.failUnless(t.SetFromString("-20:50",base)=="-mm:ss")
		self.failUnless(t.SetFromString("-20",base)=="-mm")
		self.failUnless(t.SetFromString("--50",base)=="--ss")
		self.failUnless(t.SetFromString("-2050,5",base)=="-mmss,s")
		self.failUnless(t.SetFromString("-20:50,5",base)=="-mm:ss,s")
		self.failUnless(t.SetFromString("-20,8",base)=="-mm,m")
		self.failUnless(t.SetFromString("--50,5",base)=="--ss,s")
		self.failUnless(t.SetFromString("T232050",base)=="hhmmss")
		self.failUnless(t.SetFromString("T23:20:50",base)=="hh:mm:ss")
		self.failUnless(t.SetFromString("T2320",base)=="hhmm")
		self.failUnless(t.SetFromString("T23:20",base)=="hh:mm")
		self.failUnless(t.SetFromString("T23",base)=="hh")
		self.failUnless(t.SetFromString("T232050,5",base)=="hhmmss,s")
		self.failUnless(t.SetFromString("T23:20:50,5",base)=="hh:mm:ss,s")
		self.failUnless(t.SetFromString("T2320,8",base)=="hhmm,m")
		self.failUnless(t.SetFromString("T23:20,8",base)=="hh:mm,m")
		self.failUnless(t.SetFromString("T23,3",base)=="hh,h")
		self.failUnless(t.SetFromString("000000")=="hhmmss")
		self.failUnless(t.SetFromString("00:00:00")=="hh:mm:ss")
		self.failUnless(t.SetFromString("240000")=="hhmmss")
		self.failUnless(t.SetFromString("24:00:00")=="hh:mm:ss")
		self.failUnless(t.SetFromString("232050Z",base)=="hhmmssZ")
		self.failUnless(t.SetFromString("T23:20:50Z",base)=="hh:mm:ssZ")
		self.failUnless(t.SetFromString("T23,3",base)=="hh,h")
		self.failUnless(t.SetFromString("T23,3Z",base)=="hh,hZ")
		self.failUnless(t.SetFromString("152746+0100")=="hhmmss+hhmm")
		self.failUnless(t.SetFromString("152746-0500")=="hhmmss+hhmm")
		self.failUnless(t.SetFromString("152746+01")=="hhmmss+hh")
		self.failUnless(t.SetFromString("152746-05")=="hhmmss+hh")
		self.failUnless(t.SetFromString("15:27:46+01:00")=="hh:mm:ss+hh:mm")
		self.failUnless(t.SetFromString("15:27:46-05:00")=="hh:mm:ss+hh:mm")
		self.failUnless(t.SetFromString("15:27:46+01")=="hh:mm:ss+hh")
		self.failUnless(t.SetFromString("15:27:46-05")=="hh:mm:ss+hh")
		self.failUnless(t.SetFromString("15:27+01",base)=="hh:mm+hh")
		self.failUnless(t.SetFromString("15,5-05:00",base)=="hh,h+hh:mm")
		# pure timezone functions
		self.failUnless(t.SetZoneFromString("+0100")=="+hhmm")
		self.failUnless(t.SetZoneFromString("+01")=="+hh")
		self.failUnless(t.SetZoneFromString("-0100")=="+hhmm")
		self.failUnless(t.SetZoneFromString("-01")=="+hh")
		self.failUnless(t.SetZoneFromString("+01:00")=="+hh:mm")
		
	def testTimePoint(self):
		"""Check TimePoint  syntax"""
		timePoint=TimePoint()
		base=TimePoint()
		self.failUnless(timePoint.SetFromString("19850412T101530",base)=="YYYYMMDDThhmmss","basic local")
		self.failUnless(timePoint.SetFromString("19850412T101530Z",base)=="YYYYMMDDThhmmssZ","basic z")
		self.failUnless(timePoint.SetFromString("19850412T101530+0400",base)=="YYYYMMDDThhmmss+hhmm","basic zone minutes")
		self.failUnless(timePoint.SetFromString("19850412T101530+04",base)=="YYYYMMDDThhmmss+hh","basic zone hours")
		self.failUnless(timePoint.SetFromString("1985-04-12T10:15:30",base)=="YYYY-MM-DDThh:mm:ss","extended local")
		self.failUnless(timePoint.SetFromString("1985-04-12T10:15:30Z",base)=="YYYY-MM-DDThh:mm:ssZ","extended z")
		self.failUnless(timePoint.SetFromString("1985-04-12T10:15:30+04:00",base)=="YYYY-MM-DDThh:mm:ss+hh:mm","extended zone minutes")
		self.failUnless(timePoint.SetFromString("1985-04-12T10:15:30+04",base)=="YYYY-MM-DDThh:mm:ss+hh","extended zone hours")

	def testDuration(self):
		"""Check Duration syntax"""
		duration=Duration()
		self.failUnless(duration.SetFromString("P36Y11M13DT10H5M0S")=="PnYnMnDTnHnMnS","complete")
		self.failUnless(duration.SetFromString("P36Y11M13DT10H5M0,5S")=="PnYnMnDTnHnMn,nS","complete with decimals")
		self.failUnless(duration.SetFromString("P36Y11M13DT10H5M0.5S")=="PnYnMnDTnHnMn.nS","complete with alt decimals")
		self.failUnless(duration.SetFromString("P36Y11M13DT10H5M")=="PnYnMnDTnHnM","minute precision")
		self.failUnless(duration.SetFromString("P36Y11M13DT10H")=="PnYnMnDTnH","hour precision")
		self.failUnless(duration.SetFromString("P36Y11M13D")=="PnYnMnD","day precision")
		self.failUnless(duration.SetFromString("P36Y11M")=="PnYnM","month precision")
		self.failUnless(duration.SetFromString("P36Y")=="PnY","year precision")
		self.failUnless(duration.SetFromString("P36Y11,2M")=="PnYn,nM","month precision with decimals")
		self.failUnless(duration.SetFromString("P11M")=="PnM","month only precision")
		self.failUnless(duration.SetFromString("PT10H5M")=="PTnHnM","hour and minute only")
		self.failUnless(duration.SetFromString("PT5M")=="PTnM","minute only")
		

if __name__ == "__main__":
	unittest.main()