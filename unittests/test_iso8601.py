#! /usr/bin/env python

"""Runs unit tests on the pyslet.iso8601 module"""

import logging
import time
import unittest

import pyslet.iso8601 as iso

from pyslet.py2 import is_unicode, range3, to_text, ul


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(MiscTests),
        unittest.makeSuite(DateTests),
        unittest.makeSuite(TimeTests),
        unittest.makeSuite(ParserTests),
        unittest.makeSuite(TimePointTests),
        unittest.makeSuite(DurationTests)
    ))


class MiscTests(unittest.TestCase):

    def test_week_count(self):
        week53 = set((1998, 2004, 2009, 2015, 2020, 2026, 2032, 2037, 2043,
                      2048))
        for year in range3(1998, 2050):
            if year in week53:
                self.assertTrue(iso.week_count(year) == 53,
                                "week_count(%i)" % year)
            else:
                self.assertTrue(iso.week_count(year) == 52,
                                "week_count(%i)" % year)

    def get_monkey_time(self, zdirection, zhour, zminute, dst):
        def monkey_time(secs=None):
            if secs is None:
                secs = time.time()
            d = iso.TimePoint.from_unix_time(secs)
            # now shift the zone
            d = d.shift_zone(zdirection, zhour, zminute)
            # and return a time_tuple
            century, year, month, day, hour, minute, second = \
                d.get_calendar_time_point()
            wday = d.date.get_week_day()[4]
            yday = d.date.get_ordinal_day()[2]
            return time.struct_time((century * 100 + year, month, day, hour,
                                     minute, second, wday, yday, dst))

        return monkey_time

    def test_local_zone(self):
        # we're limited in our ability to test here
        zoffset = iso.get_local_zone()
        self.assertTrue(isinstance(zoffset, int))
        self.assertTrue(1440 > zoffset, "large zoffset")
        self.assertTrue(-1440 < zoffset, "large negative zoffset")
        logging.info("%i minutes ahead of UTC", zoffset)
        # now to use in anger
        save_local_time = time.localtime
        try:
            time.localtime = self.get_monkey_time(0, None, None, False)
            zoffset = iso.get_local_zone()
            self.assertTrue(zoffset == 0, "GMT: %i" % zoffset)
            # Eastern Standard Time (New York, Winter)
            time.localtime = self.get_monkey_time(-1, 5, 0, False)
            zoffset = iso.get_local_zone()
            self.assertTrue(zoffset == -300, "EST: %i" % zoffset)
            # Eastern Daylight Time (New York, Summer)
            time.localtime = self.get_monkey_time(-1, 4, 0, True)
            zoffset = iso.get_local_zone()
            self.assertTrue(zoffset == -240, "EDT: %i" % zoffset)
            # Indian Standard Time (Mumbai)
            time.localtime = self.get_monkey_time(1, 5, 30, False)
            zoffset = iso.get_local_zone()
            # Indian Standard Time (Mumbai)
            time.localtime = self.get_monkey_time(1, 5, 30, False)
            zoffset = iso.get_local_zone()
            self.assertTrue(zoffset == 330, "IST: %i" % zoffset)
            # Extreme zone to check overflow
            time.localtime = self.get_monkey_time(1, 23, 59, True)
            zoffset = iso.get_local_zone()
            self.assertTrue(zoffset == 1439, "+Day: %i" % zoffset)
            # Extreme zone to check underflow
            time.localtime = self.get_monkey_time(-1, 23, 59, True)
            zoffset = iso.get_local_zone()
            self.assertTrue(zoffset == -1439, "-Day: %i" % zoffset)
        finally:
            time.localtime = save_local_time


class DateTests(unittest.TestCase):

    def test_constructor(self):
        date = iso.Date()
        self.assertTrue(date.get_calendar_day() == (0, 1, 1, 1),
                        "empty constructor results in the origin")
        base = iso.Date(century=19, year=69, month=7, day=20)
        self.assertTrue(base.get_calendar_day() == (19, 69, 7, 20),
                        "explicit constructor")
        date = iso.Date(base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "copy constructor")
        date = iso.Date(src=base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "copy constructor, named parameter")
        try:
            date = iso.Date(src=1969)
            self.fail("legacy src constructor take int")
        except TypeError:
            pass
        date = iso.Date.from_str("19690720")
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "string constructor")
        date = iso.Date.from_str(ul("1969-07-20"))
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "unicode constructor")
        date = iso.Date.from_str("--0720", base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "truncated year")
        # negative tests
        try:
            date = iso.Date(century=0, year=0, month=1, day=1)
            self.fail("Year 0")
        except iso.DateTimeError:
            pass
        # expanded representation
        try:
            date = iso.Date(bce=True, century=7, year=52, month=4, day=21)
            self.fail("Expanded date requires xdigits")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=-7, year=52, month=4, day=21, xdigits=0)
            self.fail("Can't use negative century, requires bce")
        except iso.DateTimeError:
            pass
        date = iso.Date(bce=True, century=7, year=52, month=4, day=21,
                        xdigits=0)
        try:
            date.get_calendar_day()
            self.fail("bce dates must use get_xcalendar_day()")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, 21),
                        "explicit negative constructor")
        date = iso.Date(century=119, year=69, month=7, day=20, xdigits=1)
        try:
            date.get_calendar_day() == (119, 69, 7, 20)
            self.fail("explicit large constructor requires get_x...")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.get_xcalendar_day() == (False, 119, 69, 7, 20),
                        "explicit large constructor")
        date2 = iso.Date(date)
        self.assertTrue(date2.get_xcalendar_day() == (False, 119, 69, 7, 20),
                        "explicit large constructor")
        self.assertTrue(date2.xdigits == 1, "copy constructor xdigits")
        date2 = iso.Date(src=date)
        self.assertTrue(date2.get_xcalendar_day() == (False, 119, 69, 7, 20),
                        "explicit large constructor")
        self.assertTrue(date2.xdigits == 1, "src constructor xdigits")
        date = iso.Date.from_str("+119690720", xdigits=1)
        self.assertTrue(date.get_xcalendar_day() == (False, 119, 69, 7, 20),
                        "string constructor, large century")
        date = iso.Date.from_str("-007520421", xdigits=1)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, 21),
                        "string constructor, negative century")
        # base is not allowed with xdigits - even if it matches!
        base = date
        try:
            date = iso.Date(year=52, month=4, day=22, base=base, xdigits=1)
            self.fail("can't use xdigits and base")
        except iso.DateTimeError:
            pass
        # but truncated forms are OK, even when base is expanded
        date = iso.Date(year=52, month=4, day=22, base=base)
        self.assertTrue(date.xdigits == 1, "xdigits copied from base")
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, 22),
                        "truncated form, negative year")
        # finally, Year 0 is OK when using expanded form
        date = iso.Date(century=0, year=0, month=1, day=1, xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 0, 1, 1),
                        "1 BC (Year 0), expanded representation")
        date = iso.Date(bce=True, century=0, year=0, month=1, day=1,
                        xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 0, 1, 1),
                        "1 BC (Year 0), bce is stripped")

    def test_repr(self):
        result = repr(iso.Date(century=19, year=69, month=7, day=20))
        self.assertTrue(
            result == "Date(century=19, year=69, month=7, day=20)", result)
        result = repr(iso.Date(century=19, year=69, month=7))
        self.assertTrue(
            result == "Date(century=19, year=69, month=7, day=None)", result)
        result = repr(iso.Date(century=19, decade=6, year=9, week=29,
                      weekday=7))
        self.assertTrue(
            result == "Date(century=19, year=69, month=7, day=20)", result)
        result = repr(iso.Date(century=19, decade=6, year=9, week=29))
        self.assertTrue(
            result == "Date(century=19, decade=6, year=9, week=29)", result)
        # expanded forms
        result = repr(iso.Date(century=119, year=69, month=7, day=20,
                      xdigits=1))
        self.assertTrue(
            result == "Date(century=119, year=69, month=7, day=20, xdigits=1)",
            result)
        result = repr(iso.Date(bce=True, century=7, year=52, month=4, day=21,
                               xdigits=2))
        self.assertTrue(result == "Date(bce=True, century=7, year=52, "
                        "month=4, day=21, xdigits=2)", result)
        result = repr(
            iso.Date(bce=True, century=7, year=52, month=4, xdigits=1))
        self.assertTrue(result == "Date(bce=True, century=7, year=52, "
                        "month=4, day=None, xdigits=1)", result)
        result = repr(iso.Date(bce=True, century=7, year=52, xdigits=-1))
        self.assertTrue(result == "Date(bce=True, century=7, year=52, "
                        "month=None, day=None, xdigits=-1)", result)
        result = repr(iso.Date(bce=True, century=7, xdigits=0))
        self.assertTrue(result == "Date(bce=True, century=7, year=None, "
                        "month=None, day=None, xdigits=0)", result)
        result = repr(iso.Date(bce=True, century=7, decade=5, year=2, week=17,
                      weekday=2, xdigits=0))
        self.assertTrue(result == "Date(bce=True, century=7, year=52, "
                        "month=4, day=21, xdigits=0)", result)
        result = repr(iso.Date(bce=True, century=7, decade=5, year=2, week=17,
                               xdigits=-1))
        self.assertTrue(result == "Date(bce=True, century=7, decade=5, "
                        "year=2, week=17, xdigits=-1)", result)

    def test_calendar_day(self):
        """Test Get and Set Calendar day"""
        date = iso.Date()
        base = iso.Date()
        base_overflow = iso.Date()
        base = iso.Date(century=19, year=69, month=7, day=20)
        base_overflow = iso.Date(century=19, year=69, month=7, day=21)
        base_max = iso.Date(century=99, year=99, month=12, day=25)
        date = iso.Date(century=19, year=69, month=7, day=20)
        self.assertTrue(
            date.get_calendar_day() == (19, 69, 7, 20), "simple case")
        try:
            date = iso.Date(year=69, month=7, day=20)
            self.fail("truncation without base")
        except iso.DateTimeError:
            pass
        date = iso.Date(year=69, month=7, day=20, base=base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "truncated century")
        date = iso.Date(year=69, month=7, day=20, base=base_overflow)
        self.assertTrue(date.get_calendar_day() == (20, 69, 7, 20),
                        "truncated century with overflow")
        date = iso.Date(month=7, day=20, base=base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "truncated year")
        date = iso.Date(month=7, day=20, base=base_overflow)
        self.assertTrue(date.get_calendar_day() == (19, 70, 7, 20),
                        "truncated year with overflow")
        date = iso.Date(day=20, base=base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "truncated month")
        date = iso.Date(day=20, base=base_overflow)
        self.assertTrue(date.get_calendar_day() == (19, 69, 8, 20),
                        "truncated month with overflow")
        try:
            incomplete = iso.Date(century=19, year=69, month=7)
            date = iso.Date(day=20, base=incomplete)
            self.fail("incomplete base with truncation")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(base=base)
            self.fail("empty constructor with base")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(day=1, base=base_max)
            self.fail("10001-01-01: illegal date")
        except iso.DateTimeError:
            pass
        date = iso.Date(century=19, year=69, month=7)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, None),
                        "month precision")
        date = iso.Date(century=19, year=69)
        self.assertTrue(date.get_calendar_day() == (19, 69, None, None),
                        "year precision")
        date = iso.Date(century=19)
        self.assertTrue(date.get_calendar_day() == (19, None, None, None),
                        "century precision")
        base_overflow = iso.Date(century=19, year=69, month=8, day=1)
        date = iso.Date(year=69, month=7, base=base)
        self.assertTrue(date.get_calendar_day() == (
            19, 69, 7, None), "month precision, truncated century")
        date = iso.Date(year=69, month=7, base=base_overflow)
        self.assertTrue(date.get_calendar_day() == (20, 69, 7, None),
                        "month precision, truncated century with overflow")
        date = iso.Date(month=7, base=base)
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, None),
                        "month precision, truncated year")
        date = iso.Date(month=7, base=base_overflow)
        self.assertTrue(date.get_calendar_day() == (19, 70, 7, None),
                        "month precision, truncated year with overflow")
        base_overflow = iso.Date(century=19, year=69, month=1, day=1)
        date = iso.Date(year=69, base=base)
        self.assertTrue(date.get_calendar_day() == (19, 69, None, None),
                        "year precision, truncated century")
        date = iso.Date(year=68, base=base_overflow)
        self.assertTrue(date.get_calendar_day() == (20, 68, None, None),
                        "year precision, truncated century with overflow")
        try:
            date = iso.Date(century=100, year=69, month=7, day=20)
            self.fail("bad century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, year=100, month=7, day=20)
            self.fail("bad year")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, year=69, month=13, day=20)
            self.fail("bad month")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, year=0, month=2, day=29)
            self.fail("bad day")
        except iso.DateTimeError:
            pass
        # expanded forms
        try:
            date = iso.Date(year=52, month=4, day=21, xdigits=0)
            self.fail("truncation not allowed with xdigits")
        except iso.DateTimeError:
            pass
        date = iso.Date(bce=True, century=7, year=52, month=4, xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, None),
                        "month precision")
        date = iso.Date(bce=True, century=7, year=52, xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, None, None),
                        "year precision")
        date = iso.Date(bce=True, century=7, xdigits=2)
        self.assertTrue(date.get_xcalendar_day() ==
                        (True, 7, None, None, None), "century precision")
        date = iso.Date(century=119, year=69, month=7, day=20, xdigits=1)
        try:
            date = iso.Date(century=119, year=69, month=7, day=20, xdigits=0)
            self.fail("bad century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(bce=True, century=7, year=100, month=4, day=21,
                            xdigits=1)
            self.fail("bad year")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(bce=True, century=7, year=52, month=13, day=21,
                            xdigits=0)
            self.fail("bad month")
        except iso.DateTimeError:
            pass
        try:
            # 753 BC (-0752) was a leap year so try -0751
            date = iso.Date(bce=True, century=7, year=51, month=2, day=29,
                            xdigits=0)
            self.fail("bad day")
        except iso.DateTimeError:
            pass
        base = iso.Date(bce=True, century=1, year=0, month=4, day=21,
                        xdigits=0)
        date = iso.Date(month=4, day=20, base=base)
        self.assertTrue(date.get_xcalendar_day() == (True, 0, 99, 4, 20))
        date = iso.Date(month=4, day=19, base=date)
        self.assertTrue(date.get_xcalendar_day() == (True, 0, 98, 4, 19))
        base = date
        date = iso.Date(year=99, month=4, day=19, base=base)
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 99, 4, 19),
                        "big jump over year 0")
        date = iso.Date(year=1, month=4, day=19, base=base)
        self.assertTrue(date.get_xcalendar_day() == (True, 0, 1, 4, 19))
        base = date
        date = iso.Date(year=1, month=4, day=18, base=base)
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 1, 4, 18),
                        "small jump over year 0")

    def test_ordinal_day(self):
        """Test Get and Set Ordinal day"""
        date = iso.Date()
        base = iso.Date()
        base_overflow = iso.Date()
        base = iso.Date(century=19, year=69, month=7, day=20)
        base_overflow = iso.Date(century=19, year=69, month=7, day=21)
        date = iso.Date(century=19, year=69, ordinalDay=201)
        self.assertTrue(date.get_ordinal_day() == (19, 69, 201),
                        "simple case ordinal")
        self.assertTrue(date.get_xordinal_day() == (False, 19, 69, 201),
                        "simple case of xordinal")
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "calendar cross check")
        date = iso.Date(century=19, year=69, ordinalDay=1)
        self.assertTrue(date.get_calendar_day() == (19, 69, 1, 1),
                        "calendar cross check Jan 1st")
        date = iso.Date(century=19, year=68, ordinalDay=366)
        self.assertTrue(date.get_calendar_day() == (
            19, 68, 12, 31), "calendar cross check Dec 31st (leap)")
        date = iso.Date(century=19, year=69, ordinalDay=365)
        self.assertTrue(date.get_calendar_day() == (19, 69, 12, 31),
                        "calendar cross check Dec 31st (non-leap)")
        try:
            date = iso.Date(year=69, ordinalDay=201)
            self.fail("truncation without base")
        except iso.DateTimeError:
            pass
        date = iso.Date(year=69, ordinalDay=201, base=base)
        self.assertTrue(date.get_ordinal_day() == (19, 69, 201),
                        "truncated century")
        date = iso.Date(year=69, ordinalDay=201, base=base_overflow)
        self.assertTrue(date.get_ordinal_day() == (20, 69, 201),
                        "truncated century with overflow")
        date = iso.Date(ordinalDay=201, base=base)
        self.assertTrue(date.get_ordinal_day() == (19, 69, 201),
                        "truncated year")
        date = iso.Date(ordinalDay=201, base=base_overflow)
        self.assertTrue(date.get_ordinal_day() == (19, 70, 201),
                        "truncated year with overflow")
        date = iso.Date(century=19, decade=6, year=9, week=29)
        try:
            date.get_ordinal_day()
            self.fail("ordinal day with week precision")
        except iso.DateTimeError:
            pass
        date = iso.Date(century=19, year=69, month=7)
        try:
            date.get_ordinal_day()
            self.fail("ordinal day with month precision")
        except iso.DateTimeError:
            pass
        date = iso.Date(century=19, year=69)
        self.assertTrue(date.get_ordinal_day() == (19, 69, None),
                        "year precision")
        date = iso.Date(century=19)
        self.assertTrue(date.get_ordinal_day() == (19, None, None),
                        "century precision")
        base_overflow = iso.Date(century=19, year=69, month=1, day=1)
        date = iso.Date(year=69, base=base)
        self.assertTrue(date.get_ordinal_day() == (19, 69, None),
                        "year precision, truncated century")
        date = iso.Date(year=68, base=base_overflow)
        self.assertTrue(date.get_ordinal_day() == (20, 68, None),
                        "year precision, truncated century with overflow")
        try:
            date = iso.Date(century=100, year=69, ordinalDay=201)
            self.fail("bad century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, year=100, ordinalDay=201)
            self.fail("bad year")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, year=68, ordinalDay=367)
            self.fail("bad ordinal - leap")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, year=69, ordinalDay=366)
            self.fail("bad ordinal - non-leap")
        except iso.DateTimeError:
            pass
        # expanded forms
        date = iso.Date(bce=True, century=7, year=52, ordinal_day=112,
                        xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, 21),
                        "simple case")
        try:
            date.get_ordinal_day()
            self.fail("negative ordinal requires get_xcalendar_day")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.get_xordinal_day() == (True, 7, 52, 112),
                        "simple case ordinal")
        date = iso.Date(bce=True, century=7, year=52, ordinal_day=1, xdigits=1)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 1, 1),
                        "calendar cross check Jan 1st")
        date = iso.Date(bce=True, century=7, year=52, ordinal_day=366,
                        xdigits=-1)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 12, 31),
                        "calendar cross check Dec 31st (leap)")
        date = iso.Date(bce=True, century=7, year=51, ordinal_day=365,
                        xdigits=2)
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 51, 12, 31),
                        "calendar cross check Dec 31st (non-leap)")
        date = iso.Date(bce=True, century=7, year=52, xdigits=1)
        self.assertTrue(date.get_xordinal_day() == (True, 7, 52, None),
                        "negative year precision")
        date = iso.Date(bce=True, century=7, xdigits=1)
        self.assertTrue(date.get_xordinal_day() == (True, 7, None, None),
                        "negative century precision")
        date = iso.Date(century=10019, year=69, ordinal_day=201, xdigits=3)
        try:
            date = iso.Date(century=10019, year=69, ordinal_day=201, xdigits=2)
            self.fail("bad century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(bce=True, century=7, year=100, ordinal_day=112,
                            xdigits=0)
            self.fail("bad year")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(bce=True, century=7, year=52, ordinal_day=367,
                            xdigits=0)
            self.fail("bad ordinal - leap")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(bce=True, century=7, year=51, ordinal_day=366,
                            xdigits=0)
            self.fail("bad ordinal - non-leap")
        except iso.DateTimeError:
            pass

    def test_week_day(self):
        """Test Get and Set Week day"""
        date = iso.Date()
        base = iso.Date(century=19, year=69, month=7, day=20)
        base_overflow = iso.Date(century=19, year=69, month=7, day=21)
        date = iso.Date(century=19, decade=6, year=9, week=29, weekday=7)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, 7),
                        "simple case")
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "calendar cross check")
        date = iso.Date(century=19, decade=6, year=9, week=1, weekday=1)
        self.assertTrue(date.get_calendar_day() == (
            19, 68, 12, 30), "calendar cross check underflow")
        date = iso.Date(century=19, decade=7, year=0, week=53, weekday=5)
        self.assertTrue(date.get_calendar_day() == (19, 71, 1, 1),
                        "calendar cross check overflow")
        try:
            date = iso.Date(decade=6, year=9, week=29, weekday=7)
            self.fail("truncation without base")
        except iso.DateTimeError:
            pass
        date = iso.Date(decade=6, year=9, week=29, weekday=7, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, 7),
                        "truncated century")
        date = iso.Date(decade=6, year=9, week=29, weekday=7,
                        base=base_overflow)
        self.assertTrue(date.get_week_day() == (20, 6, 9, 29, 7),
                        "truncated century with overflow")
        date = iso.Date(year=9, week=29, weekday=7, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, 7),
                        "truncated decade")
        date = iso.Date(year=9, week=29, weekday=7, base=base_overflow)
        self.assertTrue(date.get_week_day() == (19, 7, 9, 29, 7),
                        "truncated decade with overflow")
        date = iso.Date(week=29, weekday=7, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, 7),
                        "truncated year")
        date = iso.Date(week=29, weekday=7, base=base_overflow)
        self.assertTrue(date.get_week_day() == (19, 7, 0, 29, 7),
                        "truncated year with overflow")
        date = iso.Date(weekday=7, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, 7),
                        "truncated week")
        date = iso.Date(weekday=1, base=base_overflow)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 30, 1),
                        "truncated week with overflow")
        date = iso.Date(century=19, decade=6, year=9, week=29)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, None),
                        "week precision")
        date = iso.Date(century=19, year=69, month=7)
        try:
            date.get_week_day()
            self.fail("month precision")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=6, year=9)
            self.fail("year precision")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=6)
            self.fail("decade precision")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=6, year=9, week=-1, weekday=1)
            self.fail("negative week")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=20, decade=1, year=6, week=53, weekday=1)
            self.fail("too large week")
        except iso.DateTimeError:
            pass
        base_overflow = iso.Date(century=19, decade=6, year=9, week=30,
                                 weekday=2)
        date = iso.Date(decade=6, year=9, week=29, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, None),
                        "week precision, truncated century")
        date = iso.Date(decade=6, year=9, week=29, base=base_overflow)
        self.assertTrue(date.get_week_day() == (20, 6, 9, 29, None),
                        "week precision, truncated century with overflow")
        date = iso.Date(year=9, week=29, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, None),
                        "week precision, truncated decade")
        date = iso.Date(year=9, week=29, base=base_overflow)
        self.assertTrue(date.get_week_day() == (19, 7, 9, 29, None),
                        "week precision, truncated decade with overflow")
        date = iso.Date(week=29, base=base)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 29, None),
                        "week precision, truncated year")
        date = iso.Date(week=29, base=base_overflow)
        self.assertTrue(date.get_week_day() == (19, 7, 0, 29, None),
                        "week precision, truncated year with overflow")
        date = iso.Date(weekday=1, base=base_overflow)
        self.assertTrue(date.get_week_day() == (19, 6, 9, 31, 1),
                        "weekday precision, truncated week with overflow")
        date = iso.Date(century=20, decade=1, year=5, week=1, weekday=3)
        self.assertTrue(date.get_calendar_day() == (20, 14, 12, 31),
                        "underflow on caldenar conversion (non leap)")
        date = iso.Date(century=20, decade=1, year=6, week=1, weekday=3)
        self.assertTrue(date.get_calendar_day() == (20, 16, 1, 6),
                        "convert to caldenar (leap year)")
        date = iso.Date(weekday=1, base=iso.Date(century=20, decade=1, year=6,
                                                 week=52, weekday=3))
        self.assertTrue(date.get_calendar_day() == (20, 17, 1, 2),
                        "convert to caldenar (leap year) with overflow")
        date = iso.Date(century=20, year=16, month=1, day=1)
        self.assertTrue(date.get_week_day() == (20, 1, 5, 53, 5),
                        "underflow on week conversion")
        date = iso.Date(century=20, year=14, month=12, day=31)
        self.assertTrue(date.get_week_day() == (20, 1, 5, 1, 3),
                        "overflow on week conversion")
        try:
            date = iso.Date(decade=6, year=9, base=base)
            self.fail("year precision, truncated century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(decade=6, base=base)
            self.fail("decade precision, truncated century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=100, decade=6, year=9, week=29, weekday=7)
            self.fail("bad century")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=10, year=9, week=29, weekday=7)
            self.fail("bad decade")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=6, year=10, week=29, weekday=7)
            self.fail("bad year")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=6, year=8, week=53, weekday=1)
            self.fail("bad week")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date(century=19, decade=6, year=8, week=52, weekday=8)
            self.fail("bad day")
        except iso.DateTimeError:
            pass
        # expanded forms
        date = iso.Date(bce=True, century=7, decade=5, year=2, week=17,
                        weekday=2, xdigits=0)
        try:
            date.get_week_day()
            self.fail("get_xweek_day required for negative years")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.get_xweek_day() == (True, 7, 5, 2, 17, 2),
                        "simple negative")
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, 21),
                        "calendar cross check")
        base = date
        date = iso.Date(year=3, week=17, weekday=2, base=base)
        self.assertTrue(date.get_xweek_day() == (True, 7, 4, 3, 17, 2),
                        "truncated decade with overflow")
        date = iso.Date(week=17, weekday=1, base=base)
        self.assertTrue(date.get_xweek_day() == (True, 7, 5, 1, 17, 1),
                        "truncated year with overflow")

    def test_time_tuple(self):
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
        date = iso.Date.from_struct_time(
            [1969, 7, 20, None, None, None, None, None, None])
        time_tuple = [None] * 9
        date.update_struct_time(time_tuple)
        self.assertTrue(time_tuple == [1969, 7, 20, None, None, None, 6, 201,
                                       None], "simple case")
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20),
                        "calendar cross-check")
        date = iso.Date(century=19, year=69, month=7)
        try:
            date.update_struct_time(time_tuple)
            self.fail("month precision")
        except iso.DateTimeError:
            pass

    def test_absolute_days(self):
        """Test Get and Set Absolute Day"""
        date = iso.Date()
        # check the 1st January each from  0001 (the base day) through
        # 2049
        abs_day = 1
        for year in range3(1, 1740):
            date = iso.Date(absolute_day=abs_day)
            self.assertTrue(date.get_calendar_day() ==
                            (year // 100, year % 100, 1, 1),
                            "%04i-01-01 check" % year)
            self.assertTrue(date.get_absolute_day() == abs_day,
                            "%04i-01-01 symmetry check" % year)
            abs_day += 365
            if (year % 4 == 0 and (not year % 100 == 0 or year % 400 == 0)):
                abs_day += 1
        # check each day in a sample (leap) year
        date = iso.Date(century=19, year=68, month=1, day=1)
        abs_day = date.get_absolute_day()
        for i in range3(366):
            date = iso.Date(absolute_day=abs_day)
            self.assertTrue(date.get_ordinal_day() == (19, 68, i + 1),
                            "1968=%03i check" % (i + 1))
            self.assertTrue(date.get_absolute_day() == abs_day,
                            "1968-%03i symmetry check" % (i + 1))
            abs_day += 1
        # check a 400-year boundary
        date = iso.Date(century=20, year=00, month=6, day=21)
        abs_day = date.get_absolute_day()
        for i in range3(366):
            date = iso.Date(absolute_day=abs_day)
            self.assertTrue(date.get_absolute_day() == abs_day,
                            "%i symmetry check" % abs_day)
            abs_day += 1
        # check exception for incomplete date
        date = iso.Date(century=20, year=00, month=6)
        try:
            abs_day = date.get_absolute_day()
            self.fail("Expected error on incomplete date")
        except iso.DateTimeError:
            pass
        # check some expanded dates
        abs_day = 1
        for year in range3(1001):
            # first of Jan for years going backwards
            abs_day -= 365
            if (year % 4 == 0 and (not year % 100 == 0 or year % 400 == 0)):
                abs_day -= 1
            date = iso.Date(absolute_day=abs_day, xdigits=1)
            self.assertTrue(
                date.get_xcalendar_day() ==
                (True if year else False, year // 100, year % 100, 1, 1),
                "-%04i-01-01 check" % year)
            self.assertTrue(date.get_absolute_day() == abs_day,
                            "-%04i-01-01 symmetry check" % year)

    def test_offset(self):
        date = iso.Date(century=20, year=16, month=1, day=1)
        self.assertTrue(date.offset(days=1).get_calendar_day() ==
                        (20, 16, 1, 2), "simple day offset")
        self.assertTrue(date.offset(days=31).get_calendar_day() ==
                        (20, 16, 2, 1), "day offset, month overflow")
        self.assertTrue(date.offset(days=-1).get_calendar_day() ==
                        (20, 15, 12, 31), "negative day offset with underflow")
        self.assertTrue(date.offset(days=366).get_calendar_day() ==
                        (20, 17, 1, 1), "day offset, leap year overflow")
        self.assertTrue(date.offset(weeks=1).get_calendar_day() ==
                        (20, 16, 1, 8), "simple week offset")
        self.assertTrue(date.offset(weeks=5).get_calendar_day() ==
                        (20, 16, 2, 5), "week offset, month overflow")
        self.assertTrue(date.offset(weeks=53).get_calendar_day() ==
                        (20, 17, 1, 6), "week offset, year overflow")
        self.assertTrue(date.offset(weeks=-1).get_calendar_day() ==
                        (20, 15, 12, 25), "simple week offset")
        try:
            date.offset(months=1)
            self.fail("simple month offset, full precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(years=1)
            self.fail("simple month offset, full precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(centuries=1)
            self.fail("simple month offset, full precision")
        except iso.DateTimeError:
            pass
        # reduced precision forms, gets more tricky
        date = iso.Date(century=20, year=16, month=1)
        try:
            date.offset(days=1)
            self.fail("simple day offset, month precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(weeks=1)
            self.fail("simple week offset, month precision")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.offset(months=1).get_calendar_day() ==
                        (20, 16, 2, None),
                        "simple month offset, month precision")
        self.assertTrue(date.offset(months=12).get_calendar_day() ==
                        (20, 17, 1, None),
                        "month offset, year overflow, month precision")
        self.assertTrue(date.offset(months=-1).get_calendar_day() ==
                        (20, 15, 12, None),
                        "negative month offset, month precision")
        self.assertTrue(date.offset(years=1).get_calendar_day() ==
                        (20, 17, 1, None), "simple year offset")
        self.assertTrue(date.offset(years=-1).get_calendar_day() ==
                        (20, 15, 1, None), "negative year offset")
        self.assertTrue(date.offset(years=99).get_calendar_day() ==
                        (21, 15, 1, None), "year offset with overflow")
        self.assertTrue(date.offset(years=-20).get_calendar_day() ==
                        (19, 96, 1, None),
                        "negative year offset with underflow")
        self.assertTrue(date.offset(centuries=1).get_calendar_day() ==
                        (21, 16, 1, None), "simple century offset")
        self.assertTrue(date.offset(centuries=-1).get_calendar_day() ==
                        (19, 16, 1, None), "negative century offset")
        # week precision is limited to week offsets
        date = iso.Date(century=20, decade=1, year=6, week=1)
        try:
            date.offset(days=1)
            self.fail("simple day offset, week precision")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.offset(weeks=1).get_week_day() ==
                        (20, 1, 6, 2, None),
                        "simple week offset, week precision")
        self.assertTrue(date.offset(weeks=-1).get_week_day() ==
                        (20, 1, 5, 53, None),
                        "negative week offset, week precision")
        self.assertTrue(date.offset(weeks=52).get_week_day() ==
                        (20, 1, 7, 1, None),
                        "week offset, year offlow, week precision")
        try:
            date.offset(months=1)
            self.fail("simple month offset, week precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(years=1)
            self.fail("simple year offset, week precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(centuries=1)
            self.fail("simple century offset, week precision")
        except iso.DateTimeError:
            pass
        # year precision is limited to years and centuries
        date = iso.Date(century=20, year=16)
        try:
            date.offset(days=1)
            self.fail("simple day offset, year precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(weeks=1)
            self.fail("simple week offset, year precision")
        except iso.DateTimeError:
            pass
        try:
            date.offset(months=1)
            self.fail("simple month offset, year precision")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.offset(years=1).get_calendar_day() ==
                        (20, 17, None, None), "simple year offset")
        self.assertTrue(date.offset(years=-1).get_calendar_day() ==
                        (20, 15, None, None), "negative year offset")
        self.assertTrue(date.offset(years=99).get_calendar_day() ==
                        (21, 15, None, None), "year offset with overflow")
        self.assertTrue(date.offset(years=-20).get_calendar_day() ==
                        (19, 96, None, None),
                        "negative year offset with underflow")
        self.assertTrue(date.offset(centuries=1).get_calendar_day() ==
                        (21, 16, None, None), "simple century offset")
        self.assertTrue(date.offset(centuries=-1).get_calendar_day() ==
                        (19, 16, None, None), "negative century offset")
        # expanded forms
        date = iso.Date(bce=True, century=7, year=52, month=1, day=1,
                        xdigits=0)
        self.assertTrue(date.offset(days=1).get_xcalendar_day() ==
                        (True, 7, 52, 1, 2), "BCE simple day offset")
        self.assertTrue(date.offset(days=-1).get_xcalendar_day() ==
                        (True, 7, 53, 12, 31),
                        "BCE negative day offset with underflow")
        date = iso.Date(bce=True, century=7, year=52, month=1, xdigits=0)
        self.assertTrue(date.offset(years=800).get_xcalendar_day() ==
                        (False, 0, 48, 1, None),
                        "BCE year offset with roll over")

    def test_leap(self):
        date = iso.Date(century=20, year=16)
        self.assertTrue(date.leap_year(), "2016 is leap")
        date = iso.Date(century=19, year=16)
        self.assertTrue(date.leap_year(), "1916 is leap")
        date = iso.Date(century=19, year=00)
        self.assertFalse(date.leap_year(), "1900 is not leap")
        date = iso.Date(century=20, year=00)
        self.assertTrue(date.leap_year(), "2000 is leap")
        date = iso.Date(bce=True, century=7, year=52, xdigits=0)
        self.assertTrue(date.leap_year(), "-0752 is leap")
        # and finally...
        date = iso.Date(century=19)
        try:
            date.leap_year()
            self.fail("19th century is can't be tested for leap")
        except iso.DateTimeError:
            pass

    def test_julian(self):
        # check the switch-over in the British Empire
        # Wednesday 2 September 1752 (Julian) is followed by Thursday 14
        # September 1752 (Gregorian)
        date = iso.Date.from_julian(1752, 9, 2)
        self.assertTrue(date.get_week_day()[4] == 3)
        self.assertTrue(date.offset(days=1).get_calendar_day() ==
                        (17, 52, 9, 14),  "Gregorian switch over")
        self.assertTrue(date.get_julian_day() == (1752, 9, 2),
                        "Julian switch over day")
        # Christmas is on 7th Jan (Gregorian) for some people (until 2100)
        date = iso.Date.from_julian(2016, 12, 25)
        self.assertTrue(date.get_calendar_day() == (20, 17, 1, 7),
                        "Julian leap Christmas")
        self.assertTrue(date.get_julian_day() == (2016, 12, 25),
                        "Julian leap Christmas read-back")
        date = iso.Date.from_julian(2015, 12, 25)
        self.assertTrue(date.get_calendar_day() == (20, 16, 1, 7),
                        "Julian non-leap Christmas")
        self.assertTrue(date.get_julian_day() == (2015, 12, 25),
                        "Julian non-leap Christmas read-back")
        # tricky case, New Year's Eve, leap year
        date = iso.Date.from_julian(2016, 12, 31)
        self.assertTrue(date.get_julian_day() == (2016, 12, 31),
                        "Julian New Year's Eve leap read-back")
        # D = Y//100 - Y//400 -2
        date = iso.Date.from_julian(1, 1, 3)
        self.assertTrue(date.get_calendar_day() == (0, 1, 1, 1))
        date = iso.Date.from_julian(1701, 1, 1)
        self.assertTrue(date.get_calendar_day() == (17, 1, 1, 12))
        # expanded dates
        date = iso.Date(bce=True, century=0, year=44, month=1, day=1,
                        xdigits=0)
        self.assertTrue(date.get_julian_day() == (-44, 1, 3))
        try:
            date = iso.Date.from_julian(-44, 1, 3)
            self.fail("BCE requires xdigits in from_juian")
        except iso.DateTimeError:
            pass
        date = iso.Date.from_julian(-44, 1, 3, xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (True, 0, 44, 1, 1))
        date = iso.Date.from_julian(-752, 4, 21, xdigits=0)
        # should be 8 days ahead of Gregorian
        self.assertTrue(date.get_xcalendar_day() == (True, 7, 52, 4, 13))

    def test_set_from_string(self):
        date = iso.Date.from_str(ul("19690720"))
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20))
        date = iso.Date.from_str("19690720")
        self.assertTrue(date.get_calendar_day() == (19, 69, 7, 20))
        try:
            date = iso.Date.from_str(iso.Date.from_str(ul("19690720")))
            self.fail("from_str with non-string")
        except TypeError:
            pass
        # expanded forms
        try:
            date = iso.Date.from_str("119690720")
            self.fail("expanded form requires xdigits and leading +")
        except iso.DateTimeError:
            pass
        try:
            date = iso.Date.from_str("119690720", xdigits=1)
            self.fail("expanded form requires leading +")
        except ValueError:
            pass
        try:
            date = iso.Date.from_str("+119690720")
            self.fail("expanded form requires xdigits")
        except ValueError:
            pass
        try:
            date = iso.Date.from_str("00000101")
            self.fail("0 counts as expanded form")
        except iso.DateTimeError:
            pass
        date = iso.Date.from_str("+119690720", xdigits=1)
        try:
            date.get_calendar_day()
            self.fail("Expanded date requires get_xcalendar_day")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.get_xcalendar_day() == (False, 119, 69, 7, 20))
        date = iso.Date.from_str("11969-07-20", xdigits=-1)
        self.assertTrue(date.get_xcalendar_day() == (False, 119, 69, 7, 20))
        date = iso.Date.from_str("+00000101", xdigits=0)
        try:
            date.get_calendar_day()
            self.fail("Year 0 requires get_xcalendar_day")
        except iso.DateTimeError:
            pass
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 0, 1, 1))
        date = iso.Date.from_str("-00000101", xdigits=0)
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 0, 1, 1))
        # odd cases
        base = iso.Date(century=19, year=70, month=1, day=1)
        date = iso.Date.from_str("-8504", base=base)
        # year and month in implied century (straight from ISO8601)
        self.assertTrue(date.get_xcalendar_day() == (False, 19, 85, 4, None))
        date = iso.Date.from_str("-8504", xdigits=0)
        # century and year with reduced precision
        self.assertTrue(date.get_xcalendar_day() == (True, 85, 4, None, None))
        date = iso.Date.from_str("-8504", xdigits=-1)
        # century and year with reduced precision (non conformant but OK)
        self.assertTrue(date.get_xcalendar_day() == (True, 85, 4, None, None))
        date = iso.Date.from_str("-850401", xdigits=-1)
        # century and year with reduced precision (non conformant but OK)
        self.assertTrue(date.get_xcalendar_day() ==
                        (True, 8504, 1, None, None))
        # century, year and month with reduced precision (non conformant)
        date = iso.Date.from_str("-8504-01", xdigits=-1)
        self.assertTrue(date.get_xcalendar_day() == (True, 85, 4, 1, None))
        date = iso.Date.from_str("-8504-01-01", xdigits=-1)
        self.assertTrue(date.get_xcalendar_day() == (True, 85, 4, 1, 1))
        date = iso.Date.from_str("+8504-01-01", xdigits=-1)
        self.assertTrue(date.get_xcalendar_day() == (False, 85, 4, 1, 1))
        date = iso.Date.from_str("+000000-01-01", xdigits=-1)
        self.assertTrue(date.get_xcalendar_day() == (False, 0, 0, 1, 1))
        try:
            date = iso.Date.from_str("+000-01-01", xdigits=-1)
            self.fail("xdigits=-1 requires at least 4 digits for year")
        except ValueError:
            pass

    def test_get_precision(self):
        date = iso.Date(century=19, year=69, month=7, day=20)
        self.assertTrue(date.get_precision() == iso.Precision.Complete,
                        "complete precision")
        date = iso.Date(century=19, year=69, month=7)
        self.assertTrue(date.get_precision() == iso.Precision.Month,
                        "month precision")
        date = iso.Date(century=19, year=69)
        self.assertTrue(date.get_precision() == iso.Precision.Year,
                        "year precision")
        date = iso.Date(century=19)
        self.assertTrue(date.get_precision() == iso.Precision.Century,
                        "century precision")
        date = iso.Date(century=119, xdigits=1)
        self.assertTrue(date.get_precision() == iso.Precision.Century,
                        "century precision")
        date = iso.Date(century=19, decade=6, year=9, week=29, weekday=7)
        self.assertTrue(date.get_precision() == iso.Precision.Complete,
                        "complete precision (weekday)")
        date = iso.Date(century=19, decade=6, year=9, week=29)
        self.assertTrue(date.get_precision() == iso.Precision.Week,
                        "week precision")

    def test_comparisons(self):
        """Test the comparison methods"""
        self.assertTrue(
            iso.Date.from_str("19690720") == iso.Date.from_str("19690720"),
            "simple equality")
        self.assertTrue(
            iso.Date.from_str("19690720") <= iso.Date.from_str("19690720"),
            "simple equality")
        self.assertTrue(
            iso.Date.from_str("19690720") >= iso.Date.from_str("19690720"),
            "simple equality")
        self.assertFalse(
            iso.Date.from_str("19690720") != iso.Date.from_str("19690720"),
            "simple equality")
        self.assertTrue(
            iso.Date.from_str("19690720") < iso.Date.from_str("19690721"),
            "simple inequality")
        self.assertTrue(
            iso.Date.from_str("19690721") > iso.Date.from_str("19690720"),
            "simple inequality")
        # expanded forms compare as normal
        self.assertTrue(
            iso.Date.from_str("19690720") <
            iso.Date.from_str("+119690720", xdigits=1),
            "simple inequality with expanded date")
        self.assertTrue(
            iso.Date.from_str("19690720") >
            iso.Date.from_str("-07520421", xdigits=0),
            "simple inequality with expanded date")
        self.assertTrue(
            iso.Date.from_str("1969W29") == iso.Date.from_str("1969W29"),
            "equality with week precision")
        self.assertTrue(
            iso.Date.from_str("1969W29") < iso.Date.from_str("1969W30"),
            "inequality with week precision")
        self.assertTrue(
            iso.Date.from_str("1969-07") == iso.Date.from_str("1969-07"),
            "equality with month precision")
        self.assertTrue(
            iso.Date.from_str("1969-07") < iso.Date.from_str("1969-08"),
            "inequality with month precision")
        self.assertTrue(
            iso.Date.from_str("1969") == iso.Date.from_str("1969"),
            "equality with year precision")
        self.assertTrue(
            iso.Date.from_str("1969") < iso.Date.from_str("1970"),
            "inequality with year precision")
        self.assertTrue(
            iso.Date.from_str("19") == iso.Date.from_str("19"),
            "equality with century precision")
        self.assertTrue(
            iso.Date.from_str("19") < iso.Date.from_str("20"),
            "inequality with century precision")
        self.assertFalse(iso.Date.from_str("1969-W29") ==
                         iso.Date.from_str("1969-07"))

    def test_get_calendar_strings(self):
        """get_calendar_string tests"""
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string() ==
            "1969-07-20", "default test")
        self.assertTrue(
            iso.Date.from_str("+119690720", xdigits=1).get_calendar_string() ==
            "+11969-07-20", "positive test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "-0119690720", xdigits=2).get_calendar_string() ==
            "-011969-07-20", "negative test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "+0011969-07-20", xdigits=-1).get_calendar_string() ==
            "11969-07-20", "canonical test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "-00752-04-21", xdigits=-1).get_calendar_string() ==
            "-0752-04-21", "canonical test expanded negative")
        # default string formatter
        result = to_text(iso.Date.from_str("19690720"))
        self.assertTrue(result == ul("1969-07-20"), "string format")
        self.assertTrue(is_unicode(result))
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(1) == "19690720",
            "basic test")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(0) ==
            "1969-07-20", "extended test")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                1, iso.NoTruncation) == "19690720",
            "basic, no truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                0, iso.NoTruncation) == "1969-07-20",
            "extended, no truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                1, iso.Truncation.Century) == "690720",
            "basic, century truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                0, iso.Truncation.Century) == "69-07-20",
            "extended, century truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                1, iso.Truncation.Year) == "--0720", "basic, year truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                0, iso.Truncation.Year) == "--07-20",
            "extended, year truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                1, iso.Truncation.Month) == "---20",
            "basic, month truncation")
        self.assertTrue(
            iso.Date.from_str("19690720").get_calendar_string(
                0, iso.Truncation.Month) == "---20",
            "extended, month truncation")
        self.assertTrue(
            iso.Date.from_str("1969-07").get_calendar_string(
                1, iso.NoTruncation) == "1969-07",
            "basic, month precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-07").get_calendar_string(
                0, iso.NoTruncation) == "1969-07",
            "extended, month precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-07").get_calendar_string(
                1, iso.Truncation.Century) == "-6907",
            "basic, month precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-07").get_calendar_string(
                0, iso.Truncation.Century) == "-69-07",
            "extended, month precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-07").get_calendar_string(
                1, iso.Truncation.Year) == "--07",
            "basic, month precision, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969-07").get_calendar_string(
                0, iso.Truncation.Year) == "--07",
            "extended, month precision, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_calendar_string(
                1, iso.NoTruncation) == "1969",
            "basic, year precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_calendar_string(
                0, iso.NoTruncation) == "1969",
            "extended, year precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_calendar_string(
                1, iso.Truncation.Century) == "-69",
            "basic, year precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_calendar_string(
                0, iso.Truncation.Century) == "-69",
            "extended, year precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("19").get_calendar_string(
                1, iso.NoTruncation) == "19",
            "basic, century precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("19").get_calendar_string(
                0, iso.NoTruncation) == "19",
            "extended, century precision, no truncation")
        # negative tests
        try:
            iso.Date.from_str("1969-W29").get_calendar_string()
            self.fail("Calendar string with week precision")
        except iso.DateTimeError:
            pass
        try:
            iso.Date.from_str("19").get_calendar_string(
                0, iso.Truncation.Century)
            self.fail("Truncation cntury with century precision")
        except iso.DateTimeError:
            pass
        try:
            iso.Date.from_str("1969").get_calendar_string(
                0, iso.Truncation.Year)
            self.fail("Truncate year with year precision")
        except iso.DateTimeError:
            pass
        try:
            iso.Date.from_str("1969-07").get_calendar_string(
                0, iso.Truncation.Month)
            self.fail("Truncate month with month precision")
        except iso.DateTimeError:
            pass
        try:
            iso.Date.from_str("1969-07-20").get_calendar_string(
                0, iso.Truncation.Week)
            self.fail("Truncate week with complete precision")
        except iso.DateTimeError:
            pass

    def test_get_ordinal_strings(self):
        """get_ordinal_string tests"""
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string() == "1969-201",
            "default test")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(1) == "1969201",
            "basic test")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(0) == "1969-201",
            "extended test")
        self.assertTrue(
            iso.Date.from_str("+119690720", xdigits=1).get_ordinal_string() ==
            "+11969-201", "positive test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "-0119690720", xdigits=2).get_ordinal_string() ==
            "-011969-201", "negative test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "+0011969-07-20", xdigits=-1).get_ordinal_string() ==
            "11969-201", "canonical test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "-00752-04-21", xdigits=-1).get_ordinal_string() ==
            "-0752-112", "canonical test expanded negative")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(
                1, iso.NoTruncation) == "1969201", "basic, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(
                0, iso.NoTruncation) == "1969-201", "extended, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(
                1, iso.Truncation.Century) == "69201",
            "basic, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(
                0, iso.Truncation.Century) == "69-201",
            "extended, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(
                1, iso.Truncation.Year) == "-201",
            "basic, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969-201").get_ordinal_string(
                0, iso.Truncation.Year) == "-201",
            "extended, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_ordinal_string(
                1, iso.NoTruncation) == "1969",
            "basic, year precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_ordinal_string(
                0, iso.NoTruncation) == "1969",
            "extended, year precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_ordinal_string(
                1, iso.Truncation.Century) == "-69",
            "basic, year precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_ordinal_string(
                0, iso.Truncation.Century) == "-69",
            "extended, year precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("19").get_ordinal_string(1, iso.NoTruncation) ==
            "19", "basic, century precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("19").get_ordinal_string(0, iso.NoTruncation) ==
            "19", "extended, century precision, no truncation")
        # negative tests
        try:
            iso.Date.from_str("1969-07-20").get_ordinal_string(
                0, iso.Truncation.Month)
            self.fail("Truncate month")
        except iso.DateTimeError:
            pass
        try:
            iso.Date.from_str("1969-07-20").get_ordinal_string(
                0, iso.Truncation.Week)
            self.fail("Truncate month")
        except iso.DateTimeError:
            pass

    def test_get_week_strings(self):
        """get_week_string tests"""
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string() == "1969-W29-7",
            "default test")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(1) == "1969W297",
            "basic test")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(0) == "1969-W29-7",
            "extended test")
        self.assertTrue(
            iso.Date.from_str("+119690720", xdigits=1).get_week_string() ==
            "+11969-W29-7", "positive test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "-0119690720", xdigits=2).get_week_string() ==
            "-011969-W29-7", "negative test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "+0011969-07-20", xdigits=-1).get_week_string() ==
            "11969-W29-7", "canonical test expanded")
        self.assertTrue(
            iso.Date.from_str(
                "-00752-04-21", xdigits=-1).get_week_string() ==
            "-0752-W17-2", "canonical test expanded negative")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                1, iso.NoTruncation) == "1969W297",
            "basic, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                0, iso.NoTruncation) == "1969-W29-7",
            "extended, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                1, iso.Truncation.Century) == "69W297",
            "basic, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                0, iso.Truncation.Century) == "69-W29-7",
            "extended, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                1, iso.Truncation.Decade) == "-9W297",
            "basic, decade truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                0, iso.Truncation.Decade) == "-9-W29-7",
            "extended, decade truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                1, iso.Truncation.Year) == "-W297", "basic, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                0, iso.Truncation.Year) == "-W29-7",
            "extended, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                1, iso.Truncation.Week) == "-W-7", "basic, week truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29-7").get_week_string(
                0, iso.Truncation.Week) == "-W-7", "extended, week truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                1, iso.NoTruncation) == "1969W29",
            "basic, week precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                0, iso.NoTruncation) == "1969-W29",
            "extended, week precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                1, iso.Truncation.Century) == "69W29",
            "basic, week precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                0, iso.Truncation.Century) == "69-W29",
            "extended, week precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                1, iso.Truncation.Decade) == "-9W29",
            "basic, week precision, decade truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                0, iso.Truncation.Decade) == "-9-W29",
            "extended, week precision, decade truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                1, iso.Truncation.Year) == "-W29",
            "basic, week precision, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969-W29").get_week_string(
                0, iso.Truncation.Year) == "-W29",
            "extended, week precision, year truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_week_string(1, iso.NoTruncation) ==
            "1969", "basic, year precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_week_string(0, iso.NoTruncation) ==
            "1969", "extended, year precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_week_string(
                1, iso.Truncation.Century) == "-69",
            "basic, year precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("1969").get_week_string(
                0, iso.Truncation.Century) == "-69",
            "extended, year precision, century truncation")
        self.assertTrue(
            iso.Date.from_str("19").get_week_string(1, iso.NoTruncation) ==
            "19", "basic, century precision, no truncation")
        self.assertTrue(
            iso.Date.from_str("19").get_week_string(0, iso.NoTruncation) ==
            "19", "extended, century precision, no truncation")
        try:
            iso.Date.from_str("1969-W29-7").get_week_string(
                0, iso.Truncation.Month)
            self.fail("Truncate month")
        except iso.DateTimeError:
            pass
        try:
            iso.Date.from_str("1969-W29").get_week_string(
                0, iso.Truncation.Month)
            self.fail("Truncate month")
        except iso.DateTimeError:
            pass

    def test_now(self):
        # This is a weak test
        date = iso.Date.from_now()
        self.assertTrue(date > iso.Date.from_str("20050313"), "now test")

    def test_expand(self):
        d1 = iso.Date.from_str("19690720")
        self.assertTrue(d1.xdigits is None)
        self.assertTrue(str(d1) == "1969-07-20")
        d2 = iso.Date.from_str("-07520421", xdigits=0)
        self.assertTrue(d2.xdigits == 0)
        self.assertTrue(str(d2) == "-0752-04-21")
        xd = d1.expand(xdigits=0)
        self.assertTrue(str(xd) == "+1969-07-20")
        xd = d1.expand(xdigits=1)
        self.assertTrue(str(xd) == "+01969-07-20")
        xd = d1.expand(xdigits=5)
        self.assertTrue(str(xd) == "+000001969-07-20")
        xd = d1.expand(xdigits=-1)
        self.assertTrue(str(xd) == "1969-07-20")
        xd = d2.expand(xdigits=0)
        self.assertTrue(str(xd) == "-0752-04-21")
        xd = d2.expand(xdigits=1)
        self.assertTrue(str(xd) == "-00752-04-21")
        xd = d2.expand(xdigits=5)
        self.assertTrue(str(xd) == "-000000752-04-21")
        xd = d2.expand(xdigits=-1)
        self.assertTrue(str(xd) == "-0752-04-21")

    def test_legacy(self):
        date = iso.Date()
        now = iso.Date.from_now()
        try:
            date.set_from_date(now)
            self.fail("Legacy: set_from_date")
        except iso.DateTimeError:
            pass
        try:
            date.set_origin()
            self.fail("Legacy: set_origin")
        except iso.DateTimeError:
            pass
        try:
            date.set_absolute_day(1)
            self.fail("Legacy: set_absolute_day")
        except iso.DateTimeError:
            pass
        try:
            date.set_calendar_day(19, 69, 7, 20, None)
            self.fail("Legacy: set_calendar_day")
        except iso.DateTimeError:
            pass
        try:
            date.set_ordinal_day(19, 69, 201, None)
            self.fail("Legacy: set_ordinal_day")
        except iso.DateTimeError:
            pass
        try:
            date.set_week_day(19, 6, 9, 29, 7, None)
            self.fail("Legacy: set_week_day")
        except iso.DateTimeError:
            pass
        t = [0] * 9
        date.update_struct_time(t)
        try:
            date.set_time_tuple(t)
            self.fail("Legacy: set_time_tuple")
        except iso.DateTimeError:
            pass
        try:
            date.get_time_tuple(t)
            self.fail("Legacy: get_time_tuple")
        except iso.DateTimeError:
            pass
        try:
            date.set_from_string("1969-07-20", None)
            self.fail("Legacy: set_from_string")
        except iso.DateTimeError:
            pass
        try:
            date.now()
            self.fail("Legacy: now")
        except iso.DateTimeError:
            pass
        try:
            date.set_julian_day(1969, 7, 7)
            self.fail("Legacy: set_julian_day")
        except iso.DateTimeError:
            pass
        try:
            date.add_century()
            self.fail("Legacy: add_century")
        except iso.DateTimeError:
            pass
        try:
            date.add_year()
            self.fail("Legacy: add_year")
        except iso.DateTimeError:
            pass
        try:
            date.add_month()
            self.fail("Legacy: add_month")
        except iso.DateTimeError:
            pass
        try:
            date.add_week()
            self.fail("Legacy: add_week")
        except iso.DateTimeError:
            pass
        try:
            date.add_days(1)
            self.fail("Legacy: add_days")
        except iso.DateTimeError:
            pass


class TimeTests(unittest.TestCase):

    def test_constructor(self):
        t = iso.Time()
        self.assertTrue(t.get_time() == (0, 0, 0), "empty constructor")
        tbase = iso.Time(hour=20, minute=17, second=40)
        t = iso.Time(tbase)
        self.assertTrue(t.get_time() == (20, 17, 40), "copy constructor")
        t = iso.Time.from_str("201740")
        self.assertTrue(t.get_time() == (20, 17, 40), "string constructor")
        t = iso.Time.from_str(ul("20:17:40"))
        self.assertTrue(t.get_time() == (20, 17, 40), "unicode constructor")
        t = iso.Time.from_str("-1740", tbase)
        self.assertTrue(t.get_time() == (20, 17, 40), "truncated hour")
        tbase = iso.Time(hour=20, minute=20, second=30)
        tbase = tbase.with_zone(zdirection=+1, zhour=1)
        t = iso.Time(tbase)
        self.assertTrue(t.get_time() == (20, 20, 30) and
                        t.get_zone() == (+1, 60),
                        "check zone copy on constructor")

    def test_time(self):
        """Test Get and Set time methods"""
        t = iso.Time()
        tbase = iso.Time()
        tbase_overflow = iso.Time()
        tbase = iso.Time(hour=20, minute=17, second=40)
        tbase_overflow = iso.Time(hour=23, minute=20, second=51)
        t = iso.Time(hour=20, minute=17, second=40)
        self.assertTrue(t.get_time() == (20, 17, 40), "simple case")
        t = iso.Time(hour=20, minute=17, second=40.5)
        self.assertTrue(t.get_time() == (20, 17, 40.5), "fractional seconds")
        try:
            t = iso.Time(minute=20, second=50)
            self.fail("truncation without base")
        except iso.DateTimeError:
            pass
        t, overflow = tbase.extend(None, 47, 40)
        self.assertTrue(t.get_time() == (20, 47, 40) and not overflow,
                        "truncated hour")
        t, overflow = tbase_overflow.extend(None, 20, 50)
        self.assertTrue(t.get_time() == (0, 20, 50) and overflow,
                        "truncated hour with overflow")
        t, overflow = tbase.extend(None, None, 50)
        self.assertTrue(t.get_time() == (20, 17, 50) and not overflow,
                        "truncated minute")
        t, overflow = tbase_overflow.extend(None, None, 50)
        self.assertTrue(t.get_time() == (23, 21, 50) and not overflow,
                        "truncated minute with overflow")
        t = iso.Time(hour=20, minute=17)
        self.assertTrue(t.get_time() == (20, 17, None), "minute precision")
        t = iso.Time(hour=20, minute=17.67)
        self.assertTrue(t.get_time() == (20, 17.67, None),
                        "fractional minute precision")
        t = iso.Time(hour=20)
        self.assertTrue(t.get_time() == (20, None, None), "hour precision")
        t = iso.Time(hour=20.3)
        self.assertTrue(t.get_time() == (20.3, None, None),
                        "fractional hour precision")
        t, overflow = tbase.extend(None, 20, None)
        self.assertTrue(t.get_time() == (20, 20, None) and not overflow,
                        "minute precision, truncated hour")
        t, overflow = tbase_overflow.extend(None, 19, None)
        self.assertTrue(t.get_time() == (0, 19, None) and overflow,
                        "minute precision, truncated hour with overflow")
        t = iso.Time(hour=24, minute=0, second=0.0)
        self.assertTrue(t.get_time() == (24, 0, 0),
                        "midnight alternate representation")
        try:
            t = iso.Time(hour=25, minute=20, second=50)
            self.fail("bad hour")
        except iso.DateTimeError:
            pass
        try:
            t = iso.Time(hour=20.3, minute=20, second=50)
            self.fail("bad fractional hour")
        except iso.DateTimeError:
            pass
        try:
            t = iso.Time(hour=0, minute=60, second=50)
            self.fail("bad minute")
        except iso.DateTimeError:
            pass
        try:
            t = iso.Time(hour=0, minute=59, second=61)
            self.fail("bad second")
        except iso.DateTimeError:
            pass
        try:
            t = iso.Time(hour=24, minute=0, second=0.5)
            self.fail("bad midnight")
        except iso.DateTimeError:
            pass

    def test_time_zone(self):
        """Test Get and Set TimeZone and correct copy behaviour"""
        t = iso.Time()
        self.assertTrue(t.get_zone() == (None, None), "unknown zone")
        t = t.with_zone(zdirection=0)
        self.assertTrue(t.get_zone() == (0, 0), "UTC")
        t = t.with_zone(zdirection=+1, zhour=0, zminute=0)
        self.assertTrue(t.get_zone() == (+1, 0), "UTC, positive offset form")
        t = t.with_zone(zdirection=-1, zhour=0, zminute=0)
        self.assertTrue(t.get_zone() == (-1, 0), "UTC, negative offset form")
        t = iso.Time(hour=15, minute=27, second=46)
        t = t.with_zone(zdirection=+1, zhour=1, zminute=0)
        self.assertTrue(t.get_zone() == (+1, 60), "plus one hour")
        t = t.with_zone(zdirection=-1, zhour=5, zminute=0)
        self.assertTrue(t.get_zone() == (-1, 300), "minus five hours")
        t = t.with_zone(zdirection=+1, zhour=1)
        self.assertTrue(t.get_zone() == (+1, 60),
                        "plus one hour, hour precision")
        t = t.with_zone(zdirection=-1, zhour=5)
        self.assertTrue(t.get_zone() == (-1, 300),
                        "minus five hours, hour precision")
        tbase = iso.Time(hour=20, minute=20, second=30)
        tbase = t.with_zone(zdirection=+1, zhour=1)
        t, overflow = tbase.extend(minute=20, second=30)
        self.assertTrue(t.get_zone() == (+1, 60),
                        "zone copy on set_time with truncation")
        try:
            t = t.with_zone(zdirection=-2, zhour=3)
            self.fail("bad direction")
        except iso.DateTimeError:
            pass
        try:
            t = t.with_zone(zdirection=+1)
            self.fail("bad offset")
        except iso.DateTimeError:
            pass
        try:
            t = t.with_zone(zdirection=-1, zhour=24, zminute=0)
            self.fail("large offset")
        except iso.DateTimeError:
            pass

    def test_time_tuple(self):
        """Test Get and Set TimeTuple

        To refresh, a time-tuple is a 9-field tuple of:
        year
        month [1,12]
        day [1,31]
        hour [0,20]
        minute [0.59]
        second [0,61]
        weekday [0,6], Monday=0
        Julian day [1,366]
        daylight savings (0,1, or -1)"""
        t = iso.Time.from_struct_time([1969, 7, 20, 20, 17, 40, None, None,
                                       None])
        time_tuple = [None] * 9
        t.update_struct_time(time_tuple)
        self.assertTrue(time_tuple == [None, None, None, 20, 17, 40, None,
                                       None, -1], "simple case")
        self.assertTrue(t.get_time() == (20, 17, 40), "time cross-check")
        t = iso.Time(hour=20, minute=20)
        try:
            t.update_struct_time(time_tuple)
            self.fail("minute precision")
        except iso.DateTimeError:
            pass

    def test_seconds(self):
        """Test Get and Set seconds"""
        self.assertTrue(iso.Time.from_str("000000").get_total_seconds() == 0,
                        "zero test")
        self.assertTrue(iso.Time.from_str("201740").get_total_seconds() ==
                        73060, "sample test")
        self.assertTrue(iso.Time.from_str("240000").get_total_seconds() ==
                        86400, "full day")
        # leap second is equivalent to the second before, not the second
        # after!
        self.assertTrue(iso.Time.from_str("235960").get_total_seconds() ==
                        86399, "leap second before midnight")
        t = iso.Time()
        t, overflow = iso.Time().offset(seconds=0)
        self.assertTrue(t.get_time() == (0, 0, 0) and not overflow, "set zero")
        t, overflow = iso.Time().offset(seconds=73060)
        self.assertTrue(t.get_time() == (20, 17, 40) and not overflow,
                        "set sample time")
        t, overflow = iso.Time().offset(seconds=73060.5)
        self.assertTrue(t.get_time() == (20, 17, 40.5) and not overflow,
                        "set sample time with fraction")
        t, overflow = iso.Time().offset(seconds=86400)
        self.assertTrue(t.get_time() == (0, 0, 0) and overflow == 1,
                        "set midnight end of day")
        t, overflow = iso.Time().offset(seconds=677860)
        self.assertTrue(t.get_time() == (20, 17, 40) and overflow == 7,
                        "set sample time next week")
        t, overflow = iso.Time().offset(seconds=-531740)
        self.assertTrue(t.get_time() == (20, 17, 40) and overflow == -7,
                        "set sample time last week")

    def test_get_strings(self):
        """get_string tests"""
        self.assertTrue(
            iso.Time.from_str("201740").get_string() == "20:17:40",
            "default test")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(1) == "201740",
            "basic test")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(0) == "20:17:40",
            "extended test")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(1, iso.NoTruncation) ==
            "201740", "basic, no truncation")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(0, iso.NoTruncation) ==
            "20:17:40", "extended, no truncation")
        self.assertTrue(
            iso.Time.from_str("201740,5").get_string(1, iso.NoTruncation) ==
            "201740", "basic, fractional seconds, default decimals")
        self.assertTrue(
            iso.Time.from_str("201740,5").get_string(1, iso.NoTruncation, 1) ==
            "201740,5", "basic, fractional seconds")
        self.assertTrue(
            iso.Time.from_str("201740,5").get_string(
                1, iso.NoTruncation, 1, dp=".") == "201740.5",
            "basic, fractional seconds, alt point")
        self.assertTrue(
            iso.Time.from_str("201740,567").get_string(
                0, iso.NoTruncation, 2) == "20:17:40,56",
            "extended, fractional seconds with decimals")
        self.assertTrue(
            iso.Time.from_str("201740,567").get_string(
                0, iso.NoTruncation, 2, dp=".") == "20:17:40.56",
            "extended, fractional seconds with decimals and alt point")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(1, iso.Truncation.Hour) ==
            "-1740", "basic, hour truncation")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(0, iso.Truncation.Hour) ==
            "-17:40", "extended, hour truncation")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(1, iso.Truncation.Minute) ==
            "--40", "basic, minute truncation")
        self.assertTrue(
            iso.Time.from_str("201740").get_string(0, iso.Truncation.Minute) ==
            "--40", "extended, minute truncation")
        self.assertTrue(
            iso.Time.from_str("2017").get_string(1, iso.NoTruncation) ==
            "2017", "basic, minute precision, no truncation")
        self.assertTrue(
            iso.Time.from_str("2017").get_string(0, iso.NoTruncation) ==
            "20:17", "extended, minute precision, no truncation")
        self.assertTrue(
            iso.Time.from_str("2017,8").get_string(1, iso.NoTruncation, 3) ==
            "2017,800", "basic, fractional minute precision, no truncation")
        self.assertTrue(
            iso.Time.from_str("2017,895").get_string(0, iso.NoTruncation, 3) ==
            "20:17,895",
            "extended, fractinoal minute precision, no truncation")
        self.assertTrue(
            iso.Time.from_str("20").get_string(1, iso.NoTruncation) ==
            "20", "basic, hour precision, no truncation")
        self.assertTrue(
            iso.Time.from_str("20").get_string(0, iso.NoTruncation) ==
            "20", "extended, hour precision, no truncation")
        self.assertTrue(
            iso.Time.from_str("20,3").get_string(1, iso.NoTruncation, 3) ==
            "20,300", "basic, fractional hour precision")
        self.assertTrue(
            iso.Time.from_str("20,345").get_string(0, iso.NoTruncation, 3) ==
            "20,345", "extended, fractinoal hour precision")
        self.assertTrue(
            iso.Time.from_str("2017").get_string(1, iso.Truncation.Hour) ==
            "-17", "basic, minute precision, hour truncation")
        self.assertTrue(
            iso.Time.from_str("2017").get_string(0, iso.Truncation.Hour) ==
            "-17", "extended, minute precision, hour truncation")
        self.assertTrue(
            iso.Time.from_str("2017,667").get_string(
                1, iso.Truncation.Hour, 3) == "-17,667",
            "basic, fractional minute precision, hour truncation")
        self.assertTrue(
            iso.Time.from_str("211740+0100").get_string() == "21:17:40+01:00",
            "default test with zone offset")
        self.assertTrue(
            iso.Time.from_str("211740+0100").get_string(1) == "211740+0100",
            "basic test with zone offset")
        self.assertTrue(
            iso.Time.from_str("211740+0100").get_string(0) == "21:17:40+01:00",
            "extended test with zone offset")
        self.assertTrue(
            iso.Time.from_str("201740Z").get_string(1) == "201740Z",
            "basic test with Z")
        self.assertTrue(
            iso.Time.from_str("201740Z").get_string(
                0) == "20:17:40Z", "extended test with Z")
        self.assertTrue(
            iso.Time.from_str("151740-0500").get_string(
                0, iso.NoTruncation, 0, iso.Precision.Hour) == "15:17:40-05",
            "extended test with zone hour precision")

    def test_set_from_string(self):
        """Test the basic set_from_string method (exercised more fully
        by parser tests)"""
        t = iso.Time.from_str("201740")
        self.assertTrue(t.get_time() == (20, 17, 40))

    def test_get_precision(self):
        """Test the precision constants"""
        t = iso.Time(hour=20, minute=17, second=40)
        self.assertTrue(
            t.get_precision() == iso.Precision.Complete, "complete precision")
        t = iso.Time(hour=20, minute=20)
        self.assertTrue(
            t.get_precision() == iso.Precision.Minute, "minute precision")
        t = iso.Time(hour=20)
        self.assertTrue(t.get_precision() == iso.Precision.Hour,
                        "hour precision")

    def test_set_precision(self):
        """Test the setting of the precision"""
        t = iso.Time(hour=20, minute=17, second=40)
        t = t.with_precision(iso.Precision.Minute)
        h, m, s = t.get_time()
        self.assertTrue((h, "%f" % m, s) == (20, "17.666667", None),
                        "reduce to minute precision")
        t = t.with_precision(iso.Precision.Hour)
        h, m, s = t.get_time()
        self.assertTrue(("%f" % h, m, s) == ("20.294444", None, None),
                        "reduce to hour precision")
        t = t.with_precision(iso.Precision.Minute)
        h, m, s = t.get_time()
        self.assertTrue((h, "%f" % m, s) == (20, "17.666667", None),
                        "extend to minute precision")
        t = t.with_precision(iso.Precision.Complete)
        h, m, s = t.get_time()
        self.assertTrue((h, m, "%f" % s) == (20, 17, "40.000000"),
                        "extend to complete precision")
        t = iso.Time(hour=20, minute=17, second=40)
        t = t.with_precision(iso.Precision.Minute, 1)
        self.assertTrue(t.get_time() == (20, 17, None),
                        "reduce to integer minute precision")
        t = t.with_precision(iso.Precision.Hour, 1)
        self.assertTrue(t.get_time() == (20, None, None),
                        "reduce to integer hour precision")
        t = t.with_precision(iso.Precision.Minute, 1)
        self.assertTrue(t.get_time() == (20, 0, None),
                        "extend to integer minute precision")
        t = t.with_precision(iso.Precision.Complete, 1)
        self.assertTrue(t.get_time() == (20, 0, 0),
                        "extend to integer complete precision")
        t = iso.Time(hour=20, minute=17, second=40.5)
        t = t.with_precision(iso.Precision.Complete, 1)
        self.assertTrue(t.get_time() == (20, 17, 40),
                        "integer complete precision")
        t = iso.Time(hour=20, minute=17.666668)
        t = t.with_precision(iso.Precision.Minute, 1)
        self.assertTrue(t.get_time() == (20, 17, None),
                        "integer minute precision")
        t = iso.Time(hour=20.294444)
        t = t.with_precision(iso.Precision.Hour, 1)
        self.assertTrue(t.get_time() == (20, None, None),
                        "integer hour precision")

    def test_comparisons(self):
        """Test the comparison methods"""
        self.assertTrue(iso.Time.from_str("201740") ==
                        iso.Time.from_str("201740"), "simple equality")
        self.assertTrue(iso.Time.from_str("201740") <
                        iso.Time.from_str("201751"), "simple inequality")
        self.assertTrue(iso.Time.from_str("2017") == iso.Time.from_str("2017"),
                        "equality with minute precision")
        self.assertTrue(iso.Time.from_str("2017") < iso.Time.from_str("2021"),
                        "inequality with minute precision")
        self.assertTrue(iso.Time.from_str("20") == iso.Time.from_str("20"),
                        "equality with hour precision")
        self.assertTrue(iso.Time.from_str("20") < iso.Time.from_str("24"),
                        "inequality with hour precision")
        self.assertTrue(iso.Time.from_str("201740Z") ==
                        iso.Time.from_str("201740Z"),
                        "simple equality with matching zone")
        self.assertTrue(iso.Time.from_str("201740Z") <
                        iso.Time.from_str("201751Z"),
                        "simple inequality with matching zone")
        self.assertTrue(iso.Time.from_str("201740Z") ==
                        iso.Time.from_str("201740+00"),
                        "simple equality with positive zone")
        self.assertTrue(iso.Time.from_str("201740Z") <
                        iso.Time.from_str("211740-00"),
                        "simple inequality with negative zone")
        self.assertTrue(iso.Time.from_str("201740Z") >
                        iso.Time.from_str("201739-00"),
                        "inequality with non matching zone and overflow")
        self.assertFalse(iso.Time.from_str("201740") ==
                         iso.Time.from_str("2017"))
        self.assertFalse(iso.Time.from_str("201740Z") ==
                         iso.Time.from_str("201740"))
        self.assertFalse(iso.Time.from_str("201740+00") ==
                         iso.Time.from_str("211740+01"))

    def test_now(self):
        # A very weak test, how do we know the real time?
        iso.Time.from_now()


class TimePointTests(unittest.TestCase):

    def test_constructor(self):
        t = iso.TimePoint()
        self.assertTrue(
            t.get_calendar_time_point() == (0, 1, 1, 1, 0, 0, 0) and
            t.time.get_zone() == (None, None), "empty constructor")
        base = iso.TimePoint()
        base.date = iso.Date(century=19, year=69, month=7, day=20)
        base.time = iso.Time(hour=20, minute=17, second=40)
        base.time = base.time.with_zone(zdirection=0)
        t = iso.TimePoint(base)
        self.assertTrue(t.time.get_time() == (20, 17, 40) and
                        t.time.get_zone() == (0, 0) and
                        t.date.get_calendar_day() == (19, 69, 7, 20),
                        "copy constructor")
        t = iso.TimePoint.from_str("19690720T201740Z")
        self.assertTrue(t.time.get_time() == (20, 17, 40) and
                        t.time.get_zone() == (0, 0) and
                        t.date.get_calendar_day() == (19, 69, 7, 20),
                        "string constructor")
        t = iso.TimePoint.from_str(ul("19690720T201740Z"))
        self.assertTrue(t.time.get_time() == (20, 17, 40) and
                        t.time.get_zone() == (0, 0) and
                        t.date.get_calendar_day() == (19, 69, 7, 20),
                        "unicode constructor")
        t = iso.TimePoint.from_str("--0720T201740Z", base)
        self.assertTrue(t.time.get_time() == (20, 17, 40) and
                        t.time.get_zone() == (0, 0) and
                        t.date.get_calendar_day() == (19, 69, 7, 20),
                        "truncated year")
        # expanded forms
        t = iso.TimePoint(date=iso.Date.from_str("-0007520421", xdigits=2),
                          time=iso.Time(hour=16, minute=0, second=0,
                                        zdirection=1, zhour=1))
        self.assertTrue(t.time.get_time() == (16, 0, 0) and
                        t.time.get_zone() == (1, 60) and
                        t.date.get_xcalendar_day() == (True, 7, 52, 4, 21),
                        "truncated year")
        try:
            t.get_calendar_time_point()
            self.fail("Expanded year requires get_xcalendar_time_point")
        except iso.DateTimeError:
            pass
        self.assertTrue(t.get_xcalendar_time_point() ==
                        (True, 7, 52, 4, 21, 16, 0, 0))
        try:
            t.get_ordinal_time_point()
            self.fail("Expanded year requires get_xordinal_time_point")
        except iso.DateTimeError:
            pass
        self.assertTrue(t.get_xordinal_time_point() ==
                        (True, 7, 52, 112, 16, 0, 0))
        try:
            t.get_week_day_time_point()
            self.fail("Expanded year requires get_xweek_time_point")
        except iso.DateTimeError:
            pass
        self.assertTrue(t.get_xweek_day_time_point() ==
                        (True, 7, 5, 2, 17, 2, 16, 0, 0))
        t = iso.TimePoint.from_str("19690720T201740Z", xdigits=None)
        self.assertTrue(str(t) == "1969-07-20T20:17:40Z")
        self.assertTrue(str(t) == "1969-07-20T20:17:40Z")
        t = iso.TimePoint.from_str("+19690720T201740Z", xdigits=0)
        self.assertTrue(str(t) == "+1969-07-20T20:17:40Z")
        try:
            t = iso.TimePoint.from_str("+19690720T201740Z", xdigits=1)
            self.fail("ordinal overflow")
        except iso.DateTimeError:
            pass
        t = iso.TimePoint.from_str("+019690720T201740Z", xdigits=1)
        self.assertTrue(str(t) == "+01969-07-20T20:17:40Z")
        try:
            t = iso.TimePoint.from_str("119690720T201740Z", xdigits=-1)
            self.fail("xdigits=-1 requires extended format")
        except iso.DateTimeError:
            pass
        t = iso.TimePoint.from_str("11969-07-20T20:17:40Z", xdigits=-1)
        self.assertTrue(str(t) == "11969-07-20T20:17:40Z")
        t = iso.TimePoint.from_str("+119690720T201740Z", xdigits=1)
        self.assertTrue(str(t) == "+11969-07-20T20:17:40Z")
        t = iso.TimePoint.from_str("-07520421T160000+0100", xdigits=0)
        self.assertTrue(str(t) == "-0752-04-21T16:00:00+01:00")
        t = iso.TimePoint.from_str("-0007520421T160000+0100", xdigits=2)
        self.assertTrue(str(t) == "-000752-04-21T16:00:00+01:00")
        t = iso.TimePoint.from_str("-000752-04-21T16:00:00+01:00", xdigits=-1)
        self.assertTrue(str(t) == "-0752-04-21T16:00:00+01:00")

    def test_get_strings(self):
        """get_string tests"""
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_calendar_string() ==
            "1969-07-20T20:17:40Z", "default test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T211740+0100").get_calendar_string(
                1) == "19690720T211740+0100", "basic test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T211740+0100").get_calendar_string(
                0) == "1969-07-20T21:17:40+01:00", "extended test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740").get_calendar_string(
                1, iso.NoTruncation) == "19690720T201740",
            "basic, no truncation")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740").get_calendar_string(
                0, iso.NoTruncation) == "1969-07-20T20:17:40",
            "extended, no truncation")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740").get_calendar_string(
                1, iso.Truncation.Month) == "---20T201740",
            "basic, month truncation")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740").get_calendar_string(
                0, iso.Truncation.Month) == "---20T20:17:40",
            "extended, month truncation")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T211740+0100").get_calendar_string(
                0, iso.NoTruncation, 3, iso.Precision.Hour) ==
            "1969-07-20T21:17:40,000+01",
            "fractional seconds and time zone precision control")
        # expanded forms
        self.assertTrue(
            iso.TimePoint.from_str(
                "+119690720T201740Z", xdigits=1).get_calendar_string() ==
            "+11969-07-20T20:17:40Z", "expanded test")
        self.assertTrue(
            iso.TimePoint.from_str(
                "+119690720T201740Z", xdigits=1).get_calendar_string(True) ==
            "+119690720T201740Z", "expanded basic test")
        self.assertTrue(
            iso.TimePoint.from_str(
                "+11969-07-20T20:17:40Z", xdigits=-1).get_calendar_string() ==
            "11969-07-20T20:17:40Z", "expanded test - non conformant")
        d = iso.TimePoint.from_str("+11969-07-20T20:17:40Z", xdigits=-1)
        try:
            d.get_calendar_string(True)
            self.fail("basic incompatible with xdigits=-1")
        except iso.DateTimeError:
            pass
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_ordinal_string() ==
            "1969-201T20:17:40Z", "default ordinal test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_ordinal_string(1) ==
            "1969201T201740Z", "basic ordinal test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_ordinal_string(0) ==
            "1969-201T20:17:40Z", "extended ordinal test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_ordinal_string(
                1, iso.NoTruncation) == "1969201T201740Z",
            "basic ordinal, no truncation")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_ordinal_string(
                0, iso.NoTruncation) == "1969-201T20:17:40Z",
            "extended ordinal, no truncation")
        # expanded forms
        self.assertTrue(
            iso.TimePoint.from_str(
                "+119690720T201740Z", xdigits=1).get_ordinal_string() ==
            "+11969-201T20:17:40Z", "expanded test")
        self.assertTrue(
            iso.TimePoint.from_str(
                "+119690720T201740Z", xdigits=1).get_ordinal_string(True) ==
            "+11969201T201740Z", "expanded basic test")
        self.assertTrue(
            iso.TimePoint.from_str(
                "+11969-07-20T20:17:40Z", xdigits=-1).get_ordinal_string() ==
            "11969-201T20:17:40Z", "expanded test - non conformant")
        d = iso.TimePoint.from_str("+11969-07-20T20:17:40Z", xdigits=-1)
        try:
            d.get_ordinal_string(True)
            self.fail("basic incompatible with xdigits=-1")
        except iso.DateTimeError:
            pass
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_week_string() ==
            "1969-W29-7T20:17:40Z", "default week test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_week_string(1) ==
            "1969W297T201740Z", "basic week test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_week_string(0) ==
            "1969-W29-7T20:17:40Z", "extended week test")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_week_string(
                1, iso.NoTruncation) == "1969W297T201740Z",
            "basic week, no truncation")
        self.assertTrue(
            iso.TimePoint.from_str("19690720T201740Z").get_week_string(
                0, iso.NoTruncation) == "1969-W29-7T20:17:40Z",
            "extended week, no truncation")
        # expanded forms
        self.assertTrue(
            iso.TimePoint.from_str(
                "+119690720T201740Z", xdigits=1).get_week_string() ==
            "+11969-W29-7T20:17:40Z", "expanded test")
        self.assertTrue(
            iso.TimePoint.from_str(
                "+119690720T201740Z", xdigits=1).get_week_string(True) ==
            "+11969W297T201740Z", "expanded basic test")
        self.assertTrue(
            iso.TimePoint.from_str(
                "+11969-07-20T20:17:40Z", xdigits=-1).get_week_string() ==
            "11969-W29-7T20:17:40Z", "expanded test - non conformant")
        d = iso.TimePoint.from_str("+11969-07-20T20:17:40Z", xdigits=-1)
        try:
            d.get_week_string(True)
            self.fail("basic incompatible with xdigits=-1")
        except iso.DateTimeError:
            pass

    def test_comparisons(self):
        """Test the comparison methods"""
        self.assertTrue(iso.TimePoint.from_str("19690720T201740") ==
                        iso.TimePoint.from_str("19690720T201740"),
                        "simple equality")
        self.assertTrue(iso.TimePoint.from_str("19690720T201740") <
                        iso.TimePoint.from_str("19690720T201751"),
                        "simple inequality")
        self.assertTrue(iso.TimePoint.from_str("19680407T201751") <
                        iso.TimePoint.from_str("19690720T201740"),
                        "whole day inequality")
        self.assertTrue(iso.TimePoint.from_str("19690720T2017") ==
                        iso.TimePoint.from_str("19690720T2017"),
                        "equality with minute precision")
        self.assertTrue(iso.TimePoint.from_str("19690720T201740Z") ==
                        iso.TimePoint.from_str("19690720T201740Z"),
                        "simple equality with matching zone")
        self.assertTrue(iso.TimePoint.from_str("19690720T201740Z") <
                        iso.TimePoint.from_str("19690720T201751Z"),
                        "simple inequality with matching zone")
        self.assertTrue(iso.TimePoint.from_str("19690720T201740Z") ==
                        iso.TimePoint.from_str("19690720T211740+01"),
                        "simple equality with non matching zone")
        self.assertTrue(iso.TimePoint.from_str("19690720T201740Z") >
                        iso.TimePoint.from_str("19690720T201740+01"),
                        "simple inequality with non matching zone")
        self.assertTrue(iso.TimePoint.from_str("19690720T201740Z") <
                        iso.TimePoint.from_str("19690720T201740-01"),
                        "inequality with non matching zone and overflow")
        self.assertFalse(iso.TimePoint.from_str("19690720T201740") ==
                         iso.TimePoint.from_str("19690720T2017"))
        # The end of one day [2400] coincides with [0000] at the start
        # of the next day, e.g. 2400 on 1985 April 12 is the same as
        # 0000 on 1985 April 13.
        self.assertFalse(iso.TimePoint.from_str("19850412T240000") ==
                         iso.TimePoint.from_str("19850413T000000"))
        try:
            iso.TimePoint.from_str("19690720T201740Z") < \
                iso.TimePoint.from_str("19690720T201740")
            self.fail("zone unspecified mismatch")
        except TypeError:
            pass

    def test_hash(self):
        """Test the ability to hash TimePoints"""
        d = {}
        d[iso.TimePoint.from_str("19690720T201740")] = True
        self.assertTrue(iso.TimePoint.from_str("19690720T201740") in d)
        self.assertFalse(iso.TimePoint.from_str("19680720T201740") in d)
        d = {}
        d[iso.TimePoint.from_str("19690720T201740Z")] = True
        self.assertTrue(iso.TimePoint.from_str("19690720T201740Z") in d)
        self.assertTrue(iso.TimePoint.from_str("19690720T201740+00") in d)
        self.assertTrue(iso.TimePoint.from_str("19690720T201740+0000") in d)
        self.assertTrue(iso.TimePoint.from_str("19690720T211740+0100") in d)
        self.assertTrue(iso.TimePoint.from_str("19690720T151740-0500") in d)
        self.assertFalse(iso.TimePoint.from_str("19690720T201740-0500") in d)
        self.assertFalse(iso.TimePoint.from_str("19690720T201740+0100") in d)

    def test_leap_second(self):
        t = iso.TimePoint(date=iso.Date(century=20, year=16, month=12, day=31),
                          time=iso.Time(hour=23, minute=59, second=60,
                                        zdirection=0))
        self.assertTrue(t.get_calendar_time_point() ==
                        (20, 16, 12, 31, 23, 59, 60))
        t = iso.TimePoint.from_str("20161231T235960Z")
        self.assertTrue(t.get_calendar_time_point() ==
                        (20, 16, 12, 31, 23, 59, 60))


class DurationTests(unittest.TestCase):

    def test_constructor(self):
        """Duration constructor tests."""
        d = iso.Duration()
        self.assertTrue(d.get_calender_duration() ==
                        (0, 0, 0, 0, 0, 0), "empty constructor")
        dcopy = iso.Duration()
        dcopy.set_calender_duration(36, 11, 13, 10, 5, 0)
        d = iso.Duration(dcopy)
        self.assertTrue(d.get_calender_duration() ==
                        (36, 11, 13, 10, 5, 0), "copy constructor")
        d = iso.Duration("P36Y11M13DT10H5M0S")
        self.assertTrue(d.get_calender_duration() ==
                        (36, 11, 13, 10, 5, 0), "string constructor")
        d = iso.Duration(ul("P36Y11M13DT10H5M0S"))
        self.assertTrue(d.get_calender_duration() ==
                        (36, 11, 13, 10, 5, 0), "unicode constructor")

    def test_calendar_duration(self):
        """Test Get and Set Calendar Durations"""
        d = iso.Duration()
        d.set_calender_duration(36, 11, 13, 10, 5, 0)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, 10, 5, 0), "simple case")
        d.set_calender_duration(36, 11, 13, 10, 5, 0.5)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, 10, 5, 0.5), "fractional seconds")
        d.set_calender_duration(36, 11, 13, 10, 5, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, 10, 5, None), "minute precision")
        d.set_calender_duration(36, 11, 13, 10, 5.5, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, 10, 5.5, None), "fractional minutes")
        d.set_calender_duration(36, 11, 13, 10, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, 10, None, None), "hour precision")
        d.set_calender_duration(36, 11, 13, 10.5, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, 10.5, None, None), "fractional hours")
        d.set_calender_duration(36, 11, 13, None, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13, None, None, None), "day precision")
        d.set_calender_duration(36, 11, 13.5, None, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, 13.5, None, None, None), "fractional days")
        d.set_calender_duration(36, 11, None, None, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11, None, None, None, None), "month precision")
        d.set_calender_duration(36, 11.5, None, None, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, 11.5, None, None, None, None), "fractional months")
        d.set_calender_duration(36, None, None, None, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36, None, None, None, None, None), "year precision")
        d.set_calender_duration(36.5, None, None, None, None, None)
        self.assertTrue(d.get_calender_duration() == (
            36.5, None, None, None, None, None), "fractional years")
        d.set_week_duration(45)
        try:
            d.get_calender_duration()
            self.fail("week mode")
        except iso.DateTimeError:
            pass

    def test_week_duration(self):
        """Test Get and Set Week Durations"""
        d = iso.Duration()
        d.set_week_duration(45)
        self.assertTrue(d.get_week_duration() == 45, "simple case")
        d.set_week_duration(45.5)
        self.assertTrue(d.get_week_duration() == 45.5, "fractional case")
        d.set_calender_duration(36, 11, 13, 10, 5, 0)
        try:
            d.get_week_duration()
            self.fail("calendar mode")
        except iso.DateTimeError:
            pass

    def test_get_strings(self):
        """Test the get_string method."""
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0S").get_string() ==
                        "P36Y11M13DT10H5M0S", "complete, default")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0S").get_string(1) ==
                        "P36Y11M13DT10H5M0S", "complete, no truncation")
        self.assertTrue(iso.Duration().get_string(0) == "P0Y0M0DT0H0M0S",
                        "complete zero")
        self.assertTrue(iso.Duration().get_string(1) == "PT0S",
                        "complete zero with truncation")
        self.assertTrue(iso.Duration("P0Y0M0DT0H").get_string(1) == "PT0H",
                        "hour precision zero with truncation")
        self.assertTrue(iso.Duration("P0Y0M0DT0H").get_string(0) ==
                        "P0Y0M0DT0H",
                        "hour precision zero without truncation")
        self.assertTrue(iso.Duration("P0Y11M13DT10H5M0S").get_string(1) ==
                        "P11M13DT10H5M0S", "year truncation")
        self.assertTrue(iso.Duration("P0Y0M13DT10H5M0S").get_string(1) ==
                        "P13DT10H5M0S", "month truncation")
        self.assertTrue(iso.Duration("P0Y0M0DT10H5M0S").get_string(1) ==
                        "PT10H5M0S", "day truncation")
        self.assertTrue(iso.Duration("P0Y0M0DT0H5M0S").get_string(1) ==
                        "PT5M0S", "hour truncation")
        self.assertTrue(iso.Duration("P0Y0M0DT0H5M").get_string(1) == "PT5M",
                        "hour truncation, minute precision")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0,5S").get_string(0) ==
                        "P36Y11M13DT10H5M0S", "removal of fractional seconds")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0,5S").get_string(
                        0, 3) == "P36Y11M13DT10H5M0,500S",
                        "display of fractional seconds")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0S").get_string(0, 3) ==
                        "P36Y11M13DT10H5M0S", "missing fractional seconds")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0,5S").get_string(
                        0, -3) == "P36Y11M13DT10H5M0.500S",
                        "display of fractional seconds alt format")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M").get_string(0) ==
                        "P36Y11M13DT10H5M", "minute precision")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5,0M").get_string(0) ==
                        "P36Y11M13DT10H5M", "removal of fractional minutes")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5,0M").get_string(0, 2) ==
                        "P36Y11M13DT10H5,00M", "fractional minute precision")
        self.assertTrue(iso.Duration("P36Y11M13DT10H5,0M").get_string(0, -2) ==
                        "P36Y11M13DT10H5.00M",
                        "fractional minute precision alt format")
        self.assertTrue(iso.Duration("P36Y11M13DT10H").get_string(0) ==
                        "P36Y11M13DT10H", "hour precision")
        self.assertTrue(iso.Duration("P36Y11M13DT10,08H").get_string(0) ==
                        "P36Y11M13DT10H", "removal of fractional hours")
        self.assertTrue(iso.Duration("P36Y11M13DT10,08H").get_string(0, 1) ==
                        "P36Y11M13DT10,0H", "fractional hour precision")
        self.assertTrue(iso.Duration("P36Y11M13DT10,08H").get_string(0, -1) ==
                        "P36Y11M13DT10.0H",
                        "fractional hour precision alt format")
        self.assertTrue(iso.Duration("P36Y11M13D").get_string(0) ==
                        "P36Y11M13D", "day precision")
        self.assertTrue(iso.Duration("P36Y11M13,420D").get_string(0) ==
                        "P36Y11M13D", "removal of fractional days")
        self.assertTrue(iso.Duration("P36Y11M13,420D").get_string(0, 4) ==
                        "P36Y11M13,4200D", "fractional day precision")
        self.assertTrue(iso.Duration("P36Y11M13,420D").get_string(0, -4) ==
                        "P36Y11M13.4200D",
                        "fractional day precision alt format")
        self.assertTrue(iso.Duration("P36Y11M").get_string(0) == "P36Y11M",
                        "month precision")
        self.assertTrue(iso.Duration("P36Y11,427M").get_string(
            0) == "P36Y11M", "removal of fractional month")
        self.assertTrue(iso.Duration("P36Y11,427M").get_string(0, 2) ==
                        "P36Y11,42M", "fractional month precision")
        self.assertTrue(iso.Duration("P36Y11,427M").get_string(0, -2) ==
                        "P36Y11.42M", "fractional month precision alt format")
        self.assertTrue(iso.Duration("P36Y").get_string(0) == "P36Y",
                        "year precision")
        self.assertTrue(iso.Duration("P36,95Y").get_string(0) == "P36Y",
                        "removal of fractional year")
        self.assertTrue(iso.Duration("P36,95Y").get_string(0, 1) == "P36,9Y",
                        "fractional year precision")
        self.assertTrue(iso.Duration("P36,95Y").get_string(0, -1) == "P36.9Y",
                        "fractional year precision alt format")

    def test_comparisons(self):
        """Test the comparison methods"""
        self.assertTrue(iso.Duration("P36Y11M13DT10H5M0S") ==
                        iso.Duration("P36Y11M13DT10H5M0S"), "simple equality")
        self.assertTrue(iso.Duration("P11M13DT10H5M0S") ==
                        iso.Duration("P0Y11M13DT10H5M0S"), "missing years")


class ParserTests(unittest.TestCase):

    def test_date_parser(self):
        base = iso.Date()
        base = iso.Date(century=19, year=65, month=4, day=12)
        self.assertTrue(iso.Date.from_string_format("19850412", base)[1] ==
                        "YYYYMMDD")
        self.assertTrue(iso.Date.from_string_format("1985-04-12", base)[1] ==
                        "YYYY-MM-DD")
        self.assertTrue(iso.Date.from_string_format("1985-04", base)[1] ==
                        "YYYY-MM")
        self.assertTrue(iso.Date.from_string_format("1985", base)[1] == "YYYY")
        self.assertTrue(iso.Date.from_string_format("19", base)[1] == "YY")
        self.assertTrue(iso.Date.from_string_format("850412", base)[1] ==
                        "YYMMDD")
        self.assertTrue(iso.Date.from_string_format("85-04-12", base)[1] ==
                        "YY-MM-DD")
        self.assertTrue(iso.Date.from_string_format("-8504", base)[1] ==
                        "-YYMM")
        self.assertTrue(iso.Date.from_string_format("-85-04", base)[1] ==
                        "-YY-MM")
        self.assertTrue(iso.Date.from_string_format("-85", base)[1] == "-YY")
        self.assertTrue(iso.Date.from_string_format("--0412", base)[1] ==
                        "--MMDD")
        self.assertTrue(iso.Date.from_string_format("--04-12", base)[1] ==
                        "--MM-DD")
        self.assertTrue(iso.Date.from_string_format("--04", base)[1] == "--MM")
        self.assertTrue(iso.Date.from_string_format("---12", base)[1] ==
                        "---DD")
        self.assertTrue(iso.Date.from_string_format("1985102", base)[1] ==
                        "YYYYDDD")
        self.assertTrue(iso.Date.from_string_format("1985-102", base)[1] ==
                        "YYYY-DDD")
        self.assertTrue(iso.Date.from_string_format("85102", base)[1] ==
                        "YYDDD")
        self.assertTrue(iso.Date.from_string_format("85-102", base)[1] ==
                        "YY-DDD")
        self.assertTrue(iso.Date.from_string_format("-102", base)[1] == "-DDD")
        self.assertTrue(iso.Date.from_string_format("1985W155", base)[1] ==
                        "YYYYWwwD")
        self.assertTrue(iso.Date.from_string_format("1985-W15-5", base)[1] ==
                        "YYYY-Www-D")
        self.assertTrue(iso.Date.from_string_format("1985W15", base)[1] ==
                        "YYYYWww")
        self.assertTrue(iso.Date.from_string_format("1985-W15", base)[1] ==
                        "YYYY-Www")
        self.assertTrue(iso.Date.from_string_format("85W155", base)[1] ==
                        "YYWwwD")
        self.assertTrue(iso.Date.from_string_format("85-W15-5", base)[1] ==
                        "YY-Www-D")
        self.assertTrue(iso.Date.from_string_format("85W15", base)[1] ==
                        "YYWww")
        self.assertTrue(iso.Date.from_string_format("85-W15", base)[1] ==
                        "YY-Www")
        self.assertTrue(iso.Date.from_string_format("-5W155", base)[1] ==
                        "-YWwwD")
        self.assertTrue(iso.Date.from_string_format("-5-W15-5", base)[1] ==
                        "-Y-Www-D")
        self.assertTrue(iso.Date.from_string_format("-5W15", base)[1] ==
                        "-YWww")
        self.assertTrue(iso.Date.from_string_format("-5-W15", base)[1] ==
                        "-Y-Www")
        self.assertTrue(iso.Date.from_string_format("-W155", base)[1] ==
                        "-WwwD")
        self.assertTrue(iso.Date.from_string_format("-W15-5", base)[1] ==
                        "-Www-D")
        self.assertTrue(iso.Date.from_string_format("-W15", base)[1] == "-Www")
        self.assertTrue(iso.Date.from_string_format("-W-5", base)[1] == "-W-D")
        try:
            iso.Date.from_string_format(base, base)
            self.fail("from_string_format without string")
        except TypeError:
            pass

    def test_time_parser(self):
        t = iso.Time()
        base = iso.Time(hour=20, minute=17, second=40)
        self.assertTrue(iso.Time.from_string_format("201740", base)[2] ==
                        "hhmmss")
        self.assertTrue(iso.Time.from_string_format("20:17:40", base)[2] ==
                        "hh:mm:ss")
        self.assertTrue(iso.Time.from_string_format("2017", base)[2] == "hhmm")
        self.assertTrue(iso.Time.from_string_format("20:17", base)[2] ==
                        "hh:mm")
        self.assertTrue(iso.Time.from_string_format("20", base)[2] == "hh")
        self.assertTrue(iso.Time.from_string_format("201740,5", base)[2] ==
                        "hhmmss,s")
        self.assertTrue(iso.Time.from_string_format("201740.50", base)[2] ==
                        "hhmmss.s")
        self.assertTrue(iso.Time.from_string_format("20:17:40,5", base)[2] ==
                        "hh:mm:ss,s")
        self.assertTrue(iso.Time.from_string_format("2017,8", base)[2] ==
                        "hhmm,m")
        self.assertTrue(iso.Time.from_string_format("2017.80", base)[2] ==
                        "hhmm.m")
        self.assertTrue(iso.Time.from_string_format("20:17,8", base)[2] ==
                        "hh:mm,m")
        self.assertTrue(iso.Time.from_string_format("20,3", base)[2] == "hh,h")
        self.assertTrue(iso.Time.from_string_format("20.80", base)[2] ==
                        "hh.h")
        self.assertTrue(iso.Time.from_string_format("-1740", base)[2] ==
                        "-mmss")
        self.assertTrue(iso.Time.from_string_format("-17:40", base)[2] ==
                        "-mm:ss")
        self.assertTrue(iso.Time.from_string_format("-20", base)[2] == "-mm")
        self.assertTrue(iso.Time.from_string_format("--40", base)[2] ==
                        "--ss")
        self.assertTrue(iso.Time.from_string_format("-1740,5", base)[2] ==
                        "-mmss,s")
        self.assertTrue(iso.Time.from_string_format("-17:40,5", base)[2] ==
                        "-mm:ss,s")
        self.assertTrue(iso.Time.from_string_format("-20,8", base)[2] ==
                        "-mm,m")
        self.assertTrue(iso.Time.from_string_format("--40,5", base)[2] ==
                        "--ss,s")
        self.assertTrue(iso.Time.from_string_format("T201740", base)[2] ==
                        "hhmmss")
        self.assertTrue(iso.Time.from_string_format("T20:17:40", base)[2] ==
                        "hh:mm:ss")
        self.assertTrue(iso.Time.from_string_format("T2017", base)[2] ==
                        "hhmm")
        self.assertTrue(iso.Time.from_string_format("T20:17", base)[2] ==
                        "hh:mm")
        self.assertTrue(iso.Time.from_string_format("T20", base)[2] == "hh")
        self.assertTrue(iso.Time.from_string_format("T201740,5", base)[2] ==
                        "hhmmss,s")
        self.assertTrue(iso.Time.from_string_format("T20:17:40,5", base)[2] ==
                        "hh:mm:ss,s")
        self.assertTrue(iso.Time.from_string_format("T2017,8", base)[2] ==
                        "hhmm,m")
        self.assertTrue(iso.Time.from_string_format("T20:17,8", base)[2] ==
                        "hh:mm,m")
        self.assertTrue(iso.Time.from_string_format("T20,3", base)[2] ==
                        "hh,h")
        self.assertTrue(iso.Time.from_string_format("000000")[2] == "hhmmss")
        self.assertTrue(iso.Time.from_string_format("00:00:00")[2] ==
                        "hh:mm:ss")
        self.assertTrue(iso.Time.from_string_format("240000")[2] == "hhmmss")
        self.assertTrue(iso.Time.from_string_format("24:00:00")[2] ==
                        "hh:mm:ss")
        self.assertTrue(iso.Time.from_string_format("201740Z", base)[2] ==
                        "hhmmssZ")
        self.assertTrue(iso.Time.from_string_format("T20:17:40Z", base)[2] ==
                        "hh:mm:ssZ")
        self.assertTrue(iso.Time.from_string_format("T20,3", base)[2] ==
                        "hh,h")
        self.assertTrue(iso.Time.from_string_format("T20,3Z", base)[2] ==
                        "hh,hZ")
        self.assertTrue(iso.Time.from_string_format("152746+0100")[2] ==
                        "hhmmss+hhmm")
        self.assertTrue(iso.Time.from_string_format("152746-0500")[2] ==
                        "hhmmss+hhmm")
        self.assertTrue(iso.Time.from_string_format("152746+01")[2] ==
                        "hhmmss+hh")
        self.assertTrue(iso.Time.from_string_format("152746-05")[2] ==
                        "hhmmss+hh")
        self.assertTrue(iso.Time.from_string_format("15:27:46+01:00")[2] ==
                        "hh:mm:ss+hh:mm")
        self.assertTrue(iso.Time.from_string_format("15:27:46-05:00")[2] ==
                        "hh:mm:ss+hh:mm")
        self.assertTrue(iso.Time.from_string_format("15:27:46+01")[2] ==
                        "hh:mm:ss+hh")
        self.assertTrue(iso.Time.from_string_format("15:27:46-05")[2] ==
                        "hh:mm:ss+hh")
        self.assertTrue(iso.Time.from_string_format("15:27+01", base)[2] ==
                        "hh:mm+hh")
        self.assertTrue(iso.Time.from_string_format("15,5-05:00", base)[2] ==
                        "hh,h+hh:mm")
        # pure timezone functions
        self.assertTrue(t.with_zone_string_format("+0100")[1] == "+hhmm")
        self.assertTrue(t.with_zone_string_format("+01")[1] == "+hh")
        self.assertTrue(t.with_zone_string_format("-0100")[1] == "+hhmm")
        self.assertTrue(t.with_zone_string_format("-01")[1] == "+hh")
        self.assertTrue(t.with_zone_string_format("+01:00")[1] == "+hh:mm")

    def test_time_point(self):
        """Check TimePoint  syntax"""
        base = iso.TimePoint()
        self.assertTrue(
            iso.TimePoint.from_string_format("19850412T101530", base)[1] ==
            "YYYYMMDDThhmmss", "basic local")
        self.assertTrue(
            iso.TimePoint.from_string_format("19850412T101530Z", base)[1] ==
            "YYYYMMDDThhmmssZ", "basic z")
        self.assertTrue(
            iso.TimePoint.from_string_format(
                "19850412T101530+0400", base)[1] == "YYYYMMDDThhmmss+hhmm",
            "basic zone minutes")
        self.assertTrue(
            iso.TimePoint.from_string_format("19850412T101530+04", base)[1] ==
            "YYYYMMDDThhmmss+hh", "basic zone hours")
        self.assertTrue(
            iso.TimePoint.from_string_format(
                "1985-04-12T10:15:30", base)[1] == "YYYY-MM-DDThh:mm:ss",
            "extended local")
        self.assertTrue(
            iso.TimePoint.from_string_format(
                "1985-04-12T10:15:30Z", base)[1] == "YYYY-MM-DDThh:mm:ssZ",
            "extended z")
        self.assertTrue(
            iso.TimePoint.from_string_format(
                "1985-04-12T10:15:30+04:00", base)[1] ==
            "YYYY-MM-DDThh:mm:ss+hh:mm", "extended zone minutes")
        self.assertTrue(
            iso.TimePoint.from_string_format("1985-04-12T10:15:30+04",
                                             base)[1] ==
            "YYYY-MM-DDThh:mm:ss+hh", "extended zone hours")

    def test_duration(self):
        """Check Duration syntax"""
        duration = iso.Duration()
        self.assertTrue(duration.set_from_string("P36Y11M13DT10H5M0S") ==
                        "PnYnMnDTnHnMnS", "complete")
        self.assertTrue(duration.set_from_string("P36Y11M13DT10H5M0,5S") ==
                        "PnYnMnDTnHnMn,nS", "complete with decimals")
        self.assertTrue(duration.set_from_string("P36Y11M13DT10H5M0.5S") ==
                        "PnYnMnDTnHnMn.nS", "complete with alt decimals")
        self.assertTrue(duration.set_from_string("P36Y11M13DT10H5M") ==
                        "PnYnMnDTnHnM", "minute precision")
        self.assertTrue(duration.set_from_string("P36Y11M13DT10H") ==
                        "PnYnMnDTnH", "hour precision")
        self.assertTrue(duration.set_from_string("P36Y11M13D") == "PnYnMnD",
                        "day precision")
        self.assertTrue(duration.set_from_string("P36Y11M") == "PnYnM",
                        "month precision")
        self.assertTrue(duration.set_from_string("P36Y") == "PnY",
                        "year precision")
        self.assertTrue(duration.set_from_string("P36Y11,2M") == "PnYn,nM",
                        "month precision with decimals")
        self.assertTrue(duration.set_from_string("P11M") == "PnM",
                        "month only precision")
        self.assertTrue(duration.set_from_string("PT10H5M") == "PTnHnM",
                        "hour and minute only")
        self.assertTrue(duration.set_from_string("PT5M") == "PTnM",
                        "minute only")


if __name__ == "__main__":
    unittest.main()
