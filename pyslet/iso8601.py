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

import decimal
import time as pytime
import warnings

from math import modf, floor

from .pep8 import PEP8Compatibility
from .py2 import (
    is_string,
    is_text,
    range3,
    SortableMixin,
    to_text,
    UnicodeMixin)
from .unicode5 import BasicParser


class DateTimeError(Exception):
    pass


MONTH_SIZES = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
MONTH_SIZES_LEAPYEAR = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
MONTH_OFFSETS = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def leap_year(year):
    """leap_year returns True if *year* is a leap year and False otherwise.

    Note that leap years famously fall on all years that divide by 4
    except those that divide by 100 but including those that divide
    by 400."""
    if year % 4:            # doesn't divide by 4
        return False
    elif year % 100:        # doesn't divide by 100
        return True
    elif year % 400:        # doesn't divide by 400
        return False
    else:
        return True


def day_of_week(year, month, day):
    """day_of_week returns the day of week 1-7

    1 being Monday for the given year, month and day"""
    num = year * 365
    num = num + year // 4 + 1
    num = num - (year // 100 + 1)
    num = num + year // 400 + 1
    if month < 3 and leap_year(year):
        num = num - 1
    return (num + MONTH_OFFSETS[month - 1] + day + 4) % 7 + 1


def week_count(year):
    """Week count returns the number of calendar weeks in a year.

    Most years have 52 weeks of course, but if the year begins on a
    Thursday or a leap year begins on a Wednesday then it has 53."""
    weekday = day_of_week(year, 1, 1)
    if weekday == 4:
        return 53
    elif weekday == 3 and leap_year(year):
        return 53
    else:
        return 52


def get_local_zone():
    """Returns the number of minutes ahead of UTC we are

    This is calculated by comparing the return result of the time
    module's gmtime and localtime methods."""
    t = pytime.time()
    utc_tuple = pytime.gmtime(t)
    utc_date = Date.from_struct_time(utc_tuple)
    utc_time = Time.from_struct_time(utc_tuple)
    local_tuple = pytime.localtime(t)
    local_date = Date.from_struct_time(local_tuple)
    local_time = Time.from_struct_time(local_tuple)
    # Crude but effective, calculate the zone in force by comaring utc and
    # local time
    if local_date == utc_date:
        zoffset = 0
    elif local_date < utc_date:
        zoffset = -1440
    else:
        zoffset = 1440
    zoffset += int(local_time.get_total_seconds() -
                   utc_time.get_total_seconds()) // 60
    return zoffset


class Truncation(object):

    """Defines constants to use when formatting to truncated forms."""
    No = 0          #: constant for no truncation
    Century = 1     #: constant for truncating to century
    Decade = 2      #: constant for truncating to decade
    Year = 3        #: constant for truncating to year
    Month = 4       #: constant for truncating to month
    Week = 5        #: constant for truncating to week
    Hour = 6        #: constant for truncating to hour
    Minute = 7      #: constant for truncating to minute

NoTruncation = Truncation.No    #: a synonym for Truncation.No


class Precision(object):

    """Defines constants for representing reduced precision."""
    Century = 1     #: constant for century precision
    Year = 2        #: constant for year precision
    Month = 3       #: constant for month precision
    Week = 4        #: constant for week precision
    Hour = 5        #: constant for hour precision
    Minute = 6      #: constant for minute precision
    Complete = 7    #: constant for complete representations


class Date(PEP8Compatibility, SortableMixin, UnicodeMixin):

    """A class for representing ISO dates.

    Values can represent dates with reduced precision, for example::

        Date(century=20, year=13, month=12)

    represents December 2013, no specific day.

    There are a number of different forms of the constructor based on
    named parameters, the simplest is::

        Date(century=19, year=69, month=7, day=20)

    You can also use weekday format (decade must be provided separately
    when using this format)::

        Date(century=19, decade=6, year=9, week=29, weekday=7)

    ...ordinal format (where day 1 is 1st Jan)::

        Date(century=19, year=69, ordinal_day=201)

    ...absolute format (where day 1 is the notional 1st Jan 0001)::

        Date(absolute_day=718998)

    An empty constructor is equivalent to::

        Date() == Date(absolute_day=1)      # True

    By default the calendar used supports dates in the range 0001-01-01
    through to 9999-12-31.  ISO 8601 allows this range to be extended
    *by agreement* using a fixed number of additional digits in the
    century specification.  These dates are referred to as *expanded*
    dates and they include provision for negative, as well as larger
    positive, years using the astronomical convention of including a
    year 0.

    Given that the use of expanded dates can only be done by agreement
    the constructor supports an additional parameter to enable you to
    construct a date using an *agreed* number of additional digits::

        Date(century=19, year=69, month=7, day=20, xdigits=2)

    The above instance represents the same date as the previous examples
    but with an expanded century representation consisting of an
    *additional* two decimal digits.  Using xdigits=2 the range of
    allowable dates is now -999999-01-01 to +999999-12-31.  Notice that
    ISO 8601 uses the leading +/- to indicate the use of an expanded
    form.  If one instance is used to create another, e.g., using
    :meth:`offset` or the base parameter described below then value of
    xdigits is copied from the existing instance to the new one.

    It is acceptable for xdigits to be set to 0, this indicates expanded
    dates with *no* additional decimal digits but has the effect of
    extending the default range to -9999-01-01 to +9999-12-31.

    When constructing instances for negative years you must set the bce
    flag on the constructor (indicating that the date is "before common
    era").  The values passed for century and year (and optionally
    decade when using weekday form) must always be positive as they
    would be written in the documented ISO decimal forms.

    Expanded dates include the year 0 (as per ISO 8601).  As a result,
    the common meaning of 1 BCE would be year 0, not year -1.  To
    represent the year 753 BCE you would use::

        Date(bce=True, century=7, year=52, xdigits=0)

    For year 0, the bce flag can be set either way (or omitted).

    The constructor includes a wildcard form of expansion using the
    special value -1 for xdigits.  Such dates are assumed to have been
    represented in the minimum number of decimal digits for the century
    (but not less than 4) and will accept a century of any size.

    ..  warn:   Python's default div/mod operators create results that
                are useful mathematically but can trip you up when
                dealing with negative values.  You cannot take a year as
                an integer and simply pass year // 100 for the century
                as -752 // 100 is -8, not -7!  As a convenience, this
                class provides a staticmethod :meth:`split_year`.

    All constructors, except the absolute form, allow the passing of a
    *base* date which allows the most-significant values to be omitted,
    (truncated forms) for example::

        base = Date(century=19, year=69, month=7, day=20)
        new_date = Date(day=21, base=base)  #: 21st July 1969

    *base* always represents a date *on or before* the newly constructed
    date, so::

        base = Date(century=19, year=99, month=12, day=31)
        new_date = Date(day=5, base=base)

    constructs a Date representing the 5th January 2000.  These
    truncated forms cannot be used with xdigits as the century is never
    present so cannot be expanded.  However, the value of *base* may be
    an expanded date and the result is another expanded date with the
    *same* xdigits constraint.  Caution is required when dealing with
    negative dates::

        base = Date(bce=True, century=7, year=52, month=4, day=21, xdigits=0)
        new_date = Date(year=53, month=4, day=21, base=base)

    results in the date -0653-04-21 and not -0753-04-21 because the year
    -0753 would have been *before* the base year -0752.

    Given that Date can hold imprecise dates, there is some ambiguity
    over the comparisons between things such as January 1985 and Week 3
    1985. Although at first sight it may be tempting to declare 1st
    April to be greater than March, it is harder to determine the
    relationship between 1st April and April itself.  Especially if a
    complete ordering is required.

    The approach taken here is to disallow comparisons between dates
    with different precisions.

    Date objects are immutable and so can be used as the keys in
    dictionaries provided they all share the same precision.

    Some older functions did allow modification but these now raise an
    error with an appropriate suggested refactoring.

    Instances can be converted directly to strings using the default,
    extended calendar format.  Other formats are supported through
    format specific methods."""

    def __init__(self, src=None, base=None, bce=False, century=None,
                 decade=None, year=None, month=None, day=None, week=None,
                 weekday=None, ordinal_day=None, absolute_day=None,
                 xdigits=None, **kwargs):
        PEP8Compatibility.__init__(self)
        ordinal_day = kwargs.get('ordinalDay', ordinal_day)
        absolute_day = kwargs.get('absoluteDay', absolute_day)
        if src is None:
            # explicit form
            if absolute_day:
                self._set_from_absolute_day(absolute_day, xdigits)
            elif decade or week or weekday:
                self._set_from_week_day(
                    bce, century, decade, year, week, weekday, base, xdigits)
            elif ordinal_day:
                self._set_from_ordinal_day(
                    bce, century, year, ordinal_day, base, xdigits)
            elif century is None and base is None:
                # use the origin, but everything else must be None too
                if year is not None or month is not None or day is not None:
                    raise DateTimeError("truncated date with no base")
                #: the number of expanded digits in the century
                self.xdigits = xdigits
                #: BCE flag (before common era)
                self.bce = False
                #: the century
                self.century = 0
                #: the year, 0..99
                self.year = 1
                #: the month, 1..12 (for dates stored in calendar form)
                self.month = 1
                self.week = None
                """the week (for dates stored in week form)

                Fully specified dates are always stored in calendar form
                but instances can represent reduced precision dates in
                week format, e.g., 2016-W01.  In these cases,
                :attr:`day` and :attr:`month` will be None and the week
                will be recorded instead."""
                #: the day, 1..31
                self.day = 1
            else:
                self._set_from_calendar_day(
                    bce, century, year, month, day, base, xdigits)
            self._check_date()
        elif isinstance(src, Date):
            self.xdigits = src.xdigits
            self.bce = src.bce
            self.century = src.century
            self.year = src.year
            self.month = src.month
            self.week = src.week
            self.day = src.day
        else:
            raise TypeError("Can't construct Date from %s" % repr(src))

    def _set_from_absolute_day(self, abs_day, xdigits):
        quad_century = 146097   # 365*400+97 always holds
        century = 36524         # 365*100+24 excludes centennial leap
        quad_year = 1461        # 365*4+1    includes leap
        # Shift the base so that day 0 is 1st Jan 0000, makes the
        # calculation easier (year 0 is leap!)
        abs_day = abs_day + 365
        # All quad centuries are equal
        abs_year = 400 * (abs_day // quad_century)
        abs_day = abs_day % quad_century
        # the first century of a quad century is one day longer than expected
        if abs_day > century:
            abs_day -= (century + 1)
            abs_year += 100
            abs_year = abs_year + 100 * (abs_day // century)
            abs_day = abs_day % century
            carry_leap = False
            # the first quad year of a century is one day shorter than
            # expected
            if abs_day >= (quad_year - 1):
                abs_day -= (quad_year - 1)
                abs_year += 4
                abs_year = abs_year + 4 * (abs_day // quad_year)
                abs_day = abs_day % quad_year
                carry_leap = True
        else:
            carry_leap = True
            abs_year = abs_year + 4 * (abs_day // quad_year)
            abs_day = abs_day % quad_year
        if carry_leap:
            # the first year of a quad year is one day longer than expected
            if abs_day > 365:
                abs_day -= 366
                abs_year += 1
                abs_year = abs_year + (abs_day // 365)
                abs_day = abs_day % 365
        else:
            # no leap during this quad year
            abs_year = abs_year + (abs_day // 365)
            abs_day = abs_day % 365
        bce, c, y = self.split_year(abs_year)
        self._set_from_ordinal_day(bce, c, y, abs_day + 1, xdigits=xdigits)
        """
        # A quad century has one more day than 4 centuries because it
        # ends in a leap year We must check for this case specially to
        # stop abother 4 complete centuries being added!
        if abs_day == (quad_century - 1):
            abs_year = abs_year + 399
            abs_day = 365
        else:
            abs_year = abs_year + 100 * (abs_day // century)
            abs_day = abs_day % century
            # A century has one fewer days than 25 quad years so we are safe
            # this time
            abs_year = abs_year + 4 * (abs_day // quad_year)
            abs_day = abs_day % quad_year
            # However, a quad year has 1 more day than 4 years so we have a
            # second special case
            if abs_day == (quad_year - 1):
                abs_year = abs_year + 3
                abs_day = 365
            else:
                abs_year = abs_year + (abs_day // 365)
                abs_day = abs_day % 365
        abs_year = abs_year + 1
        # Finally, restore the base so that 1 is the 1st of Jan for
        # setting the ordinal
        bce, c, y = self.split_year(abs_year)
        self._set_from_ordinal_day(bce, c, y, abs_day + 1, xdigits=xdigits)
        """

    def get_absolute_day(self):
        """Return a notional day number

        The number 1 being the 0001-01-01 which is the base day of our
        calendar."""
        if not self.complete():
            raise DateTimeError("absolute day requires complete date")
        quad_century = 146097   # 365*400+97 always holds
        century = 36524         # 365*100+24 excludes centennial leap
        quad_year = 1461        # 365*4+1    includes leap
        abs_year = self._year()
        abs_day = (abs_year // 400) * quad_century
        abs_year = abs_year % 400
        if abs_year >= 100:
            # first century longer than expected
            abs_day += century + 1
            abs_year -= 100
            abs_day += (abs_year // 100) * century
            abs_year = abs_year % 100
            if abs_year >= 4:
                # first quad of the century shorter than expected
                abs_day += quad_year - 1
                abs_year -= 4
                carry_leap = True
            else:
                carry_leap = False
        else:
            carry_leap = True
        abs_day += (abs_year // 4) * quad_year
        abs_year = abs_year % 4
        if carry_leap:
            # first year longer than expected
            if abs_year > 0:
                abs_day += 366
                abs_year -= 1
                abs_day += abs_year * 365
        else:
            abs_day += abs_year * 365
        # abs_day now correct for day 0 = 0000-01-01
        return abs_day - 366 + self.get_xordinal_day()[3]

    def _set_from_calendar_day(
            self, bce, century, year, month, day, base=None, xdigits=None):
        self.xdigits = xdigits if base is None else base.xdigits
        self.week = None
        if century is None:
            # Truncation level>=1
            if xdigits is not None:
                raise DateTimeError("truncated date with expansion")
            elif base is None or not base.complete():
                raise DateTimeError("truncated date with no base")
            else:
                base_bce, base_century, base_year, base_month, base_day = \
                    base.get_xcalendar_day()
                # adjust base precision to match inputs
                if day is None:
                    base_day = None
                    if month is None:
                        base_month = None
            self.bce = base_bce
            self.century = base_century
            if year is None:
                # Truncation level>=2
                self.year = base_year
                if month is None:
                    # Truncation level>=3
                    self.month = base_month
                    if day is None:
                        raise DateTimeError(
                            "Truncated forms required at least one field")
                    else:
                        self.day = day
                        if self.day < base_day:
                            self._add_month()
                else:
                    self.month = month
                    self.day = day
                    if (self.month < base_month or
                            (self.month == base_month and
                             self.day is not None and self.day < base_day)):
                        self._add_year()
            else:
                self.year = year
                self.month = month
                self.day = day
                y = self._year()
                ybase = base._year()
                if (y < ybase or
                        (y == ybase and self.month is not None and
                         (self.month < base_month or
                          (self.month == base_month and
                           self.day is not None and self.day < base_day)))):
                    self._add_century()
        else:
            self.bce = bce and bool(century or year)
            self.century = century
            self.year = year
            self.month = month
            self.day = day

    def _add_century(self):
        # strange case, e.g., -0098 goes to +0098, not +0002 or -0198!
        if self.bce:
            if self.century:
                self.century -= 1
            else:
                self.bce = False
        else:
            self.century += 1
        self._check_century_range()

    def _add_year(self):
        y = self._year()
        self.bce, self.century, self.year = self.split_year(y + 1)
        self._check_century_range()

    def _add_month(self):
        if self.month >= 12:
            self.month = 1
            self._add_year()
        else:
            self.month += 1

    def get_calendar_day(self):
        """Returns a tuple of: (century, year, month, day)"""
        year = self._year()
        if self.bce or (year is not None and (year < 1 or year > 9999)):
            raise DateTimeError("Use get_xcalendar_day for extended dates")
        return (self.century, self.year, self.month, self.day)

    def get_xcalendar_day(self):
        """Returns a tuple of: (bce, century, year, month, day)"""
        return (self.bce, self.century, self.year, self.month, self.day)

    def _set_from_ordinal_day(self, bce, century, year, ordinal_day, base=None,
                              xdigits=None):
        self.xdigits = xdigits if base is None else base.xdigits
        self.week = None
        if century is None:
            if base is None or not base.complete():
                raise DateTimeError("truncated date with no base")
            else:
                base_bce, base_century, base_year, base_ordinal_day = \
                    base.get_xordinal_day()
            self.bce = base_bce
            self.century = base_century
            if year is None:
                # Truncation level==2
                self.year = base_year
                self.day = ordinal_day
                if self.day < base_ordinal_day:
                    self._add_year()
            else:
                self.year = year
                self.day = ordinal_day
                y = self._year()
                ybase = base._year()
                if (y < ybase or
                        (y == ybase and self.day < base_ordinal_day)):
                    self._add_century()
        else:
            self.bce = bce
            self.century = century
            self.year = year
            self.day = ordinal_day
        if self.leap_year():
            msizes = MONTH_SIZES_LEAPYEAR
        else:
            msizes = MONTH_SIZES
        self.month = 1
        for m in msizes:
            if self.day > m:
                self.day = self.day - m
                self.month = self.month + 1
            else:
                break

    def get_ordinal_day(self):
        """Returns a tuple of (century, year, ordinal_day)"""
        bce, century, year, ordinal_day = self.get_xordinal_day()
        if bce:
            raise DateTimeError("Use get_xordinal_day for BCE dates")
        return century, year, ordinal_day

    def get_xordinal_day(self):
        """Returns a tuple of (century,year,ordinal_day)"""
        if self.day is None:
            if self.month is None and self.week is None:
                return (self.bce, self.century, self.year, None)
            else:
                raise DateTimeError(
                    "can't get ordinal day with month or week precision")
        if self.leap_year():
            msizes = MONTH_SIZES_LEAPYEAR
        else:
            msizes = MONTH_SIZES
        ordinal_day = self.day
        for m in msizes[:self.month - 1]:
            ordinal_day = ordinal_day + m
        return (self.bce, self.century, self.year, ordinal_day)

    def _set_from_week_day(self, bce, century, decade, year, week, weekday,
                           base=None, xdigits=None):
        self.xdigits = xdigits if base is None else base.xdigits
        if weekday is None:
            if week is None:
                raise DateTimeError(
                    "can't set date with year precision or less "
                    "using week format")
        else:
            if weekday <= 0 or weekday > 7:
                raise DateTimeError("weekday %i out of range" % weekday)
        if week is not None and (week < 0 or week > 53):
            raise DateTimeError("week %i out of range" % week)
        if year is not None and (year < 0 or year > 9):
            raise DateTimeError("year %i within decade is out of range")
        if decade is not None and (decade < 0 or decade > 9):
            raise DateTimeError("decade %i is out of range")
        self.month = None
        if century is None:
            # Truncation
            if base is None or not base.complete():
                raise DateTimeError("truncated date with no base")
            else:
                base_bce, base_century, base_decade, base_year, base_week, \
                    base_weekday = base.get_xweek_day()
                # adjust base precision
                if weekday is None:
                    base_weekday = None
            self.bce = base_bce
            self.century = base_century
            if decade is None:
                if year is None:
                    self.year = base_decade * 10 + base_year
                    if week is None:
                        self.week = base_week
                        self.day = weekday
                        if self.day is not None and self.day < base_weekday:
                            self._add_week()
                    else:
                        self.week = week
                        self.day = weekday
                        if (self.week < base_week or
                                (self.week == base_week and
                                 self.day is not None and
                                 self.day < base_weekday)):
                            self._add_year()
                else:
                    self.year = base_decade * 10 + year
                    self.week = week
                    self.day = weekday
                    y = self._year()
                    ybase = base._year()
                    if (y < ybase or
                            (y == ybase and
                             (self.week < base_week or
                              (self.week == base_week and
                               self.day is not None and
                               self.day < base_weekday)))):
                        self._add_decade()
            else:
                self.year = decade * 10 + year
                self.week = week
                self.day = weekday
                y = self._year()
                ybase = base._year()
                if (y < ybase or
                        (y == ybase and
                         (self.week < base_week or
                          (self.week == base_week and self.day is not None and
                           self.day < base_weekday)))):
                    self._add_century()
        else:
            self.bce = bce
            self.century = century
            self.year = decade * 10 + year
            self.week = week
            self.day = weekday
        if self.day is not None:
            # We must convert to calendar form
            year = self._year()
            if self.week > week_count(year):
                raise DateTimeError(
                    "bad week %i for year %i" % (self.week, year))
            self.day = 4 - day_of_week(year, 1, 4) + \
                (self.week - 1) * 7 + self.day
            if self.day < 1:
                year -= 1
                leap = leap_year(year)
                if leap:
                    self.day += 366
                else:
                    self.day += 365
            else:
                leap = leap_year(year)
                if leap:
                    year_length = 366
                else:
                    year_length = 365
                if self.day > year_length:
                    year += 1
                    self.day -= year_length
                    leap = leap_year(year)
            if leap:
                msizes = MONTH_SIZES_LEAPYEAR
            else:
                msizes = MONTH_SIZES
            self.month = 1
            for m in msizes:
                if self.day > m:
                    self.day = self.day - m
                    self.month = self.month + 1
                else:
                    break
            self.bce, self.century, self.year = self.split_year(year)
            self.week = None

    def _add_decade(self):
        # strange case, e.g., -0008 goes to +0008, not +0002 or -0018!
        decade = self.year // 10
        year = self.year % 10
        if self.bce:
            if decade:
                decade -= 1
            else:
                self.bce = False
        else:
            decade += 1
            if decade >= 10:
                self.century += 1
                decade = decade % 10
        self.year = decade * 10 + year
        self._check_century_range()

    def _add_week(self):
        if self.week >= week_count(self._year()):
            self.week = 1
            self._add_year()
        else:
            self.week += 1

    def get_week_day(self):
        """Returns a tuple of (century, decade, year, week, weekday), note
        that Monday is 1 and Sunday is 7"""
        bce, century, decade, year, week, weekday = self.get_xweek_day()
        if bce:
            raise DateTimeError("Use get_xweek_day for BCE dates")
        return century, decade, year, week, weekday

    def get_xweek_day(self):
        """Returns a tuple of (bce, century, decade, year, week, weekday),
        note that Monday is 1 and Sunday is 7"""
        if self.day is None:
            if self.week:
                return (self.bce, self.century, self.year // 10,
                        self.year % 10, self.week, None)
            elif self.month is None:
                if self.year is None:
                    return (self.bce, self.century, None, None, None, None)
                else:
                    return (self.bce, self.century, self.year // 10,
                            self.year % 10, None, None)
            else:
                raise DateTimeError("can't get week day with month precision")
        else:
            ordinal_day = self.get_xordinal_day()[3]
            year = self._year()
            if leap_year(year):
                year_length = 366
            else:
                year_length = 365
            weekday = day_of_week(year, self.month, self.day)
            thursday = ordinal_day + 4 - weekday
            if thursday < 1:
                # Thursday this week was actually last year, and so we
                # are part of the last calendar week of last year too.
                # may return year==0
                year -= 1
                week = week_count(year)
            elif thursday > year_length:
                # Thursday this week is actually next year, and so we
                # are part of the first calendar week of next year too.
                # may return century=100
                year += 1
                week = 1
            else:
                # We are part of this year, but which week?  Jan 4th
                # is always part of the first week of the year, so we
                # calculate the ordinal value of the Monay that began
                # that week
                year_base = 5 - day_of_week(year, 1, 4)
                week = (ordinal_day - year_base) // 7 + 1
            bce, c, y = self.split_year(year)
            return bce, c, y // 10, y % 10, week, weekday

    def expand(self, xdigits):
        """Constructs a new expanded instance

        The purpose of this method is to create a new instance from an
        existing Date but with a different expansion (value of xdigits).

        The resulting value must still satisfy the constraints imposed
        by the new xdigits value.  In particular, if you pass
        xdigits=None the new instance will not be expanded and must be
        in the range 0001-01-01 to 9999-12-31."""
        return self.__class__(
            bce=self.bce, century=self.century, year=self.year,
            month=self.month, week=self.week, day=self.day, xdigits=xdigits)

    @classmethod
    def from_struct_time(cls, t):
        """Constructs a :py:class:`Date` from a struct_time, such as
        might be returned from time.gmtime() and related functions."""
        return cls(century=t[0] // 100, year=t[0] % 100, month=t[1], day=t[2])

    def update_struct_time(self, t):
        """update_struct_time changes the year, month, date, wday and ydat
        fields of t, a struct_time, to match the values in this date."""
        if not self.complete():
            raise DateTimeError("update_struct_time requires complete date")
        t[0] = self._year()
        t[1] = self.month
        t[2] = self.day
        t[6] = self.get_week_day()[4] - 1
        t[7] = self.get_xordinal_day()[3]

    @classmethod
    def from_now(cls):
        """Constructs a :py:class:`Date` from the current local time."""
        return cls.from_struct_time(pytime.localtime(pytime.time()))

    def offset(self, centuries=0, years=0, months=0, weeks=0, days=0):
        """Adds an offset

        Constructs a :py:class:`Date` from the given date + a given
        offset.

        There are significant limitations on this method to avoid
        ambiguous outcomes such as adding 1 year to a leap day such as
        2016-02-29.

        A fully specified date can be offset by days or weeks, in the
        latter case all weeks have 7 days so this is always unambiguous.

        Dates known only to week precision can only be offset by weeks.

        Dates with month precision can be offset by months, years or
        centuries because every year has exactly the same number of
        months.  The concept of February next year is always meaningful
        (unlike the meaning of 29th Feb next year or the similarly
        problematic week 53 next year).

        Dates with year precision can be offset by years or centuries
        and, for completeness, dates with century precision can only be
        offset by centuries.

        Creating an offset date from an expanded date always results in
        another expanded date (with the same xdigits value)."""
        precision = self.get_precision()
        if precision == Precision.Complete:
            if not months and not years and not centuries:
                base_day = self.get_absolute_day()
                base_day += days + 7 * weeks
                return type(self)(absolute_day=base_day, xdigits=self.xdigits)
            else:
                raise DateTimeError("offset incompatible with complete date")
        elif precision == Precision.Week:
            if not days and not months and not years and not centuries:
                week = self.week + weeks
                # years don't have regular numbers of weeks
                year = self._year()
                while True:
                    if week < 1:
                        year = year - 1
                        max_week = week_count(year)
                        week = week + max_week
                    else:
                        max_week = week_count(year)
                        if week > max_week:
                            week = week - max_week
                            year += 1
                        else:
                            break
                bce, century, year = self.split_year(year)
                decade = year // 10
                year = year % 10
                return type(self)(bce=bce, century=century, decade=decade,
                                  year=year, week=week, xdigits=self.xdigits)
            else:
                raise DateTimeError("offset incompatible with week precision")
        elif precision == Precision.Month:
            if not days and not weeks:
                month = self.month + months
                if month > 12 or month < 1:
                    years += (month - 1) // 12
                    month = (month - 1) % 12 + 1
                year = self._year() + years
                bce, century, year = self.split_year(year)
                return type(self)(bce=bce, century=century + centuries,
                                  year=year, month=month, xdigits=self.xdigits)
            else:
                raise DateTimeError("offset incompatible with month precision")
        elif precision == Precision.Year:
            if not days and not weeks and not months:
                year = self._year() + years
                bce, century, year = self.split_year(year)
                return type(self)(bce=bce, century=century + centuries,
                                  year=year, xdigits=self.xdigits)
            else:
                raise DateTimeError("offset incompatible with year precision")

    @classmethod
    def from_str(cls, src, base=None, xdigits=None):
        """Parses a :py:class:`Date` instance from a *src* string."""
        if is_text(src):
            p = ISO8601Parser(src)
            if xdigits is None:
                d, dFormat = p.parse_date_format(base)
            else:
                d, dFormat = p.require_xdate_format(xdigits)
        else:
            raise TypeError
        return d

    @classmethod
    def from_string_format(cls, src, base=None, xdigits=None):
        """Similar to :py:meth:`from_str` except that a tuple is
        returned, the first item is the resulting :py:class:`Date`
        instance, the second is a string describing the format parsed.
        For example::

                        d,f=Date.from_string_format("1969-07-20")
                        # f is set to "YYYY-MM-DD". """
        if is_text(src):
            p = ISO8601Parser(src)
            if xdigits is None:
                return p.parse_date_format(base)
            else:
                return p.require_xdate_format(xdigits)
        else:
            raise TypeError

    def __unicode__(self):
        return self.get_calendar_string()

    def __repr__(self):
        if self.bce:
            bce = 'bce=True, '
        else:
            bce = ''
        if self.xdigits is None:
            xdigits = ''
        else:
            xdigits = ", xdigits=%s" % str(self.xdigits)
        if self.week is None:
            return "Date(%scentury=%s, year=%s, month=%s, day=%s%s)" % (
                bce, str(self.century), str(self.year), str(self.month),
                str(self.day), xdigits)
        else:
            return "Date(%scentury=%s, decade=%s, year=%s, week=%s%s)" % (
                bce, str(self.century), str(self.year // 10),
                str(self.year % 10), str(self.week), xdigits)

    def _century_format(self, basic):
        if self.xdigits is None:
            century_format = "%02i"
        elif self.xdigits < 0:
            if basic:
                raise DateTimeError(
                    "basic format incompatible with variable expanded dates")
            if self.bce:
                century_format = "-%02i"
            else:
                century_format = "%02i"
        else:
            if self.bce:
                century_format = "-%%0%ii" % (self.xdigits + 2)
            else:
                century_format = "+%%0%ii" % (self.xdigits + 2)
        return century_format

    def get_calendar_string(self, basic=False, truncation=NoTruncation):
        """Formats this date using calendar form, for example 1969-07-20

        *basic*
            True/False, selects basic form, e.g., 19690720.  Default is
            False.  Expanded dates that use the non-conformant
            xdigits=-1 mode are not compatible with basic formatting.

        *truncation*
            One of the :py:class:`Truncation` constants used to
            select truncated forms of the date.  For example, if you
            specify :py:attr:`Truncation.Year` you'll get --07-20 or
            --0720.  Default is :py:attr:`NoTruncation`.

        Calendar format only supports Century, Year and Month truncated
        forms."""
        century_format = self._century_format(basic)
        if self.day is None:
            if self.month is None:
                if self.week:
                    raise DateTimeError(
                        "can't get calendar string with week precision")
                if self.year is None:
                    if self.century is None:
                        raise DateTimeError("no date to format")
                    else:
                        if truncation == NoTruncation:
                            return century_format % self.century
                        else:
                            raise DateTimeError("More precision required")
                else:
                    if truncation == NoTruncation:
                        return (century_format + "%02i") % (
                            self.century, self.year)
                    elif truncation == Truncation.Century:
                        return "-%02i" % self.year
                    else:
                        raise DateTimeError("More precision required")
            else:
                if truncation == NoTruncation:
                    return (century_format + "%02i-%02i") % (
                        self.century, self.year, self.month)
                elif truncation == Truncation.Century:
                    if basic:
                        return "-%02i%02i" % (self.year, self.month)
                    else:
                        return "-%02i-%02i" % (self.year, self.month)
                elif truncation == Truncation.Year:
                    return "--%02i" % self.month
                else:
                    raise DateTimeError("More precision required")
        else:
            if truncation == NoTruncation:
                if basic:
                    return (century_format + "%02i%02i%02i") % (
                        self.century, self.year, self.month, self.day)
                else:
                    return (century_format + "%02i-%02i-%02i") % (
                        self.century, self.year, self.month, self.day)
            elif truncation == Truncation.Century:
                if basic:
                    return "%02i%02i%02i" % (self.year, self.month, self.day)
                else:
                    return "%02i-%02i-%02i" % (self.year, self.month, self.day)
            elif truncation == Truncation.Year:
                if basic:
                    return "--%02i%02i" % (self.month, self.day)
                else:
                    return "--%02i-%02i" % (self.month, self.day)
            elif truncation == Truncation.Month:
                return "---%02i" % self.day
            else:
                raise DateTimeError("Truncation error")

    def get_ordinal_string(self, basic=False, truncation=NoTruncation):
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
        century_format = self._century_format(basic)
        bce, century, year, ordinal_day = self.get_xordinal_day()
        if ordinal_day is None:
            # same as for calendar strings
            return self.get_calendar_string(basic, truncation)
        else:
            if truncation == NoTruncation:
                if basic:
                    return (century_format + "%02i%03i") % (
                        century, year, ordinal_day)
                else:
                    return (century_format + "%02i-%03i") % (
                        century, year, ordinal_day)
            elif truncation == Truncation.Century:
                if basic:
                    return "%02i%03i" % (year, ordinal_day)
                else:
                    return "%02i-%03i" % (year, ordinal_day)
            elif truncation == Truncation.Year:
                return "-%03i" % ordinal_day
            else:
                raise DateTimeError("Truncation error")

    def get_week_string(self, basic=False, truncation=NoTruncation):
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
        century_format = self._century_format(basic)
        bce, century, decade, year, week, day = self.get_xweek_day()
        if day is None:
            if week is None:
                # same as the calendar string
                return self.get_calendar_string(basic, truncation)
            else:
                if truncation == NoTruncation:
                    if basic:
                        return (century_format + "%i%iW%02i") % (
                            century, decade, year, week)
                    else:
                        return (century_format + "%i%i-W%02i") % (
                            century, decade, year, week)
                elif truncation == Truncation.Century:
                    if basic:
                        return "%i%iW%02i" % (decade, year, week)
                    else:
                        return "%i%i-W%02i" % (decade, year, week)
                elif truncation == Truncation.Decade:
                    if basic:
                        return "-%iW%02i" % (year, week)
                    else:
                        return "-%i-W%02i" % (year, week)
                elif truncation == Truncation.Year:
                    return "-W%02i" % week
                else:
                    raise DateTimeError("Truncation error")
        else:
            if truncation == NoTruncation:
                if basic:
                    return (century_format + "%i%iW%02i%i") % (
                        century, decade, year, week, day)
                else:
                    return (century_format + "%i%i-W%02i-%i") % (
                        century, decade, year, week, day)
            elif truncation == Truncation.Century:
                if basic:
                    return "%i%iW%02i%i" % (decade, year, week, day)
                else:
                    return "%i%i-W%02i-%i" % (decade, year, week, day)
            elif truncation == Truncation.Decade:
                if basic:
                    return "-%iW%02i%i" % (year, week, day)
                else:
                    return "-%i-W%02i-%i" % (year, week, day)
            elif truncation == Truncation.Year:
                if basic:
                    return "-W%02i%i" % (week, day)
                else:
                    return "-W%02i-%i" % (week, day)
            elif truncation == Truncation.Week:
                return "-W-%i" % day
            else:
                raise DateTimeError("Truncation error")

    @classmethod
    def from_julian(cls, year, month, day, xdigits=None):
        """Constructs a :py:class:`Date` from a year, month and day
        expressed in the Julian calendar.

        If the year is 0 or negative you *must* provide a value for
        xdigits in order to construct an expanded date."""
        if year % 4:
            msizes = MONTH_SIZES
        else:
            msizes = MONTH_SIZES_LEAPYEAR
        year -= 1
        for m in msizes[:month - 1]:
            day += m
        return cls(absolute_day=(year // 4) + (year * 365) + day - 2,
                   xdigits=xdigits)

    def get_julian_day(self):
        """Returns a tuple of: (year,month,day) representing the
        equivalent date in the Julian calendar."""
        quad_year = 1461        # 365*4+1    includes leap
        # Returns tuple of (year,month,day)
        day = self.get_absolute_day()
        # 1st Jan 0001 Gregorian -> 3rd Jan 0001 Julian
        # We would add 2 but we want to shift the base so that day 0 is
        # 1st Jan 0001 (Julian) We add the second bit after the
        # calculation is done
        day += 1
        year = 4 * (day // quad_year)
        day = day % quad_year
        # A quad year has 1 more day than 4 years
        if day == (quad_year - 1):
            year += 3
            day = 365
        else:
            year += day // 365
            day = day % 365
        # correct for base year being 1...
        year += 1
        # and base day being 1st
        day += 1
        if year % 4:
            msizes = MONTH_SIZES
        else:
            msizes = MONTH_SIZES_LEAPYEAR
        month = 1
        for m in msizes:
            if day > m:
                day -= m
                month += 1
            else:
                break
        return (year, month, day)

    def _year(self):
        if self.century is None or self.year is None:
            return None
        result = self.century * 100 + self.year
        if self.bce:
            return -result
        else:
            return result

    @staticmethod
    def split_year(year):
        """Static method that splits an integer year into a 3-tuple

        Returns::

            (bce, century, year)

        Can be used as a convenience when constructing new instances::

            int_year = -752
            bce, century, year = Date.split_year(int_year)
            d = Date(bce=bce, century=century, year=year, month=4, day=21,
                     xdigits=2)
            str(d) == "-000752-04-21"     # True
        """
        if year < 0:
            year = -year
            return True, year // 100, year % 100
        else:
            return False, year // 100, year % 100

    def _check_date(self):
        if self.century is None:
            raise DateTimeError("missing date")
        self._check_century_range()
        if self.year is None:
            return
        if self.year < 0 or self.year > 99:
            raise DateTimeError("year out of range %i" % self.year)
        if self.xdigits is None and self.year == 0 and self.century == 0:
            raise DateTimeError("illegal year 0000")
        year = self._year()
        if self.week:
            # week form of date:
            if self.week < 1 or self.week > week_count(year):
                raise DateTimeError(
                    "illegal week %i in year %i" % (self.week, year))
            if self.month is not None:
                raise DateTimeError("mixed week/calendar forms")
        else:
            if self.month is None:
                return
            if self.month < 1 or self.month > 12:
                raise DateTimeError("illegal month %i" % self.month)
            if self.day is None:
                return
            if leap_year(year):
                month_sizes = MONTH_SIZES_LEAPYEAR
            else:
                month_sizes = MONTH_SIZES
            if self.day < 1 or self.day > month_sizes[self.month - 1]:
                raise DateTimeError(
                    "illegal day %i for month %i" % (self.day, self.month))

    def _check_century_range(self):
        if self.xdigits is None:
            if self.century < 0 or self.century > 99:
                raise DateTimeError("century out of range %i" % self.century)
            if self.bce:
                raise DateTimeError("BCE year requires expanded date format")
        elif self.xdigits >= 0:
            if self.century < 0 or self.century > 10 ** (self.xdigits + 2) - 1:
                raise DateTimeError("century out of range %i" % self.century)

    def leap_year(self):
        """leap_year returns True if this date is (in) a leap year and
        False otherwise.

        Note that leap years fall on all years that divide by 4 except
        those that divide by 100 but including those that divide by
        400."""
        if self.year is None:
            raise DateTimeError(
                "Insufficient precision for leap year calculation")
        if self.year % 4:           # doesn't divide by 4
            return False
        elif self.year:         # doesn't divide by 100
            return True
        elif self.century % 4:  # doesn't divide by 400
            return False
        else:
            return True

    def complete(self):
        """Returns True if this date has a complete representation,
        i.e., does not use one of the reduced precision forms."""
        return self.century is not None and self.day is not None

    def get_precision(self):
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

    def sortkey(self):
        return (not self.bce, self.century, self.year, self.month, self.week,
                self.day)

    def otherkey(self, other):
        if is_string(other):
            other = self.from_str(other)
        if isinstance(other, self.__class__):
            if self.get_precision() == other.get_precision():
                return other.sortkey()
        return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())

    def set_from_date(self, src):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_from_date(src) with: d = src")

    def set_origin(self):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_origin() with: d = Date()")

    def set_absolute_day(self, abs_day):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_absolute_day(x) with d = Date(absolute_day=x)")

    def set_calendar_day(self, century, year, month, day, base=None):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_calendar_day(century=cc, year=yy, month=mm, "
            "day=dd, base=base) with\n"
            "d = Date(century=cc, year=yy, month=mm, day=dd, base=base)")

    def set_ordinal_day(self, century, year, ordinal_day, base=None, **kwargs):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_ordinal_day(century=cc, year=yy, ordinal_day=dd, "
            "base=base) with\n"
            "d = Date(century=cc, year=yy, ordinal_day=dd, base=base)")

    def set_week_day(self, century, decade, year, week, weekday, base=None):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_week_day(century=cc, decade=dd, year=yy, "
            "week=ww, weekday=dd, base=base) with\n"
            "d = Date(century=cc, decade=dd, year=yy, week=ww, weekday=dd, "
            "base=base)")

    def set_time_tuple(self, t):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_time_tuple(t) with\n"
            "d = Date.from_struct_time(t)")

    def get_time_tuple(self, t):
        raise DateTimeError(
            "Date.get_time_tuple no longer supported: \n"
            "Replace d.get_time_tuple(t) with\n"
            "st = [0] * 9\n"
            "d.update_struct_time(st)")

    def set_from_string(self, date_str, base=None):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_from_string(s, base) with\n"
            "d = Date.from_str(s, base)")

    def now(self):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.now() with\n"
            "d = Date.from_now()")

    def set_julian_day(self, year, month, day):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.set_julian_day(yy, mm, dd) with\n"
            "d = Date.from_julian(yy, mm, dd)")

    def add_century(self):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.add_century() with\n"
            "d = d.offset(centuries=1) # precision restrictions apply")

    def add_year(self):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.add_year() with\n"
            "d = d.offset(years=1) # precision restrictions apply")

    def add_month(self):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.add_month() with\n"
            "d = d.offset(months=1) # precision restrictions apply")

    def add_week(self):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.add_week() with\n"
            "d = d.offset(weeks=1) # precision restrictions apply")

    def add_days(self, days):
        raise DateTimeError(
            "Date is now immutable: \n"
            "Replace d.add_days(dd) with\n"
            "d = d.offset(days=dd)")


class Time(PEP8Compatibility, UnicodeMixin, SortableMixin):

    """A class for representing ISO times

    Values can represent times with reduced precision, for example::

        Time(hour=20)

    represents 8pm without a specific minute/seconds value.

    There are a number of different forms of the constructor based on
    named parameters, the simplest is::

        Time(hour=20, minute=17, second=40)

    Indicate UTC (Zulu time) by providing a zone direction of 0::

        Time(hour=20, minute=17, second=40, zdirection=0)

    To indicate a UTC offset provide additional values for hours (and
    optionally minutes) with 1 or -1 for zdirection to indicate the
    direction of the shift.  1 indicates a more Easterly timezone, -1
    indicates a more Westerly zone::

        Time(hour=15, minute=17, second=40, zdirection=-1, zhour=5,
             zminute=0)

    A UTC offset of 0 hours and minutes results in a value that compares
    as equal to the corresponding Zulu time but is formatted using an
    explicit offset by str() rather than using the canonical "Z" form.

    You may also specify a total number of seconds past midnight (no
    zone):

        Time(total_seconds=73060)

    If total_seconds overflows an error is raised.  To create a time
    from an arbitrary number of seconds and catch overflow use offset
    instead::

        Time(total_seconds=159460)
        # raises DateTimeError

        t, overflow = Time().offset(seconds=159460)
        # sets t to 20:40:17 and overflow=1

    Time supports two representations of midnight: 00:00:00 and 24:00:00
    in keeping with the ISO specification.  These are considered
    equivalent by comparisons!

    Truncated forms can be created directly from the base time, see
    :py:meth:`extend` for more information.

    Comparisons are dealt with in a similar way to Date in that times
    must have the same precision to be comparable.  Although this
    behaviour is consistent it might seem strange at first as it rules
    out comparing 09:00:15 with 09:00 but, in effect, 09:00 is actually
    all times in the range 09:00:00-09:00:59.999....

    Zones further complicate this method but the rule is very simple, we
    only ever compare times from the same zone (or if both have
    unspecified zones).  There is one subtlety to this implementation.
    Times stored with a redundant +00:00 or -00:00 are treated the same
    as those with a zero zone direction (Zulu time).

    Time objects are immutable and so can be used as the keys in
    dictionaries provided they all share the same precision.

    Some older functions did allow modification but these have been
    deprecated.  Use python -Wd to force warnings from these unsafe
    methods.

    Instances can be converted directly to strings or unicode strings
    using the default, extended format.  Other formats are supported
    through format specific methods."""

    def __init__(self, src=None, hour=None, minute=None, second=None,
                 total_seconds=None, zdirection=None, zhour=None,
                 zminute=None, **kwargs):
        PEP8Compatibility.__init__(self)
        total_seconds = kwargs.get('totalSeconds', total_seconds)
        zdirection = kwargs.get('zDirection', zdirection)
        zhour = kwargs.get('zHour', zhour)
        zminute = kwargs.get('zMinute', zminute)
        if src is None:
            # explicit form
            if total_seconds is not None:
                if zdirection is not None:
                    raise DateTimeError(
                        "Zone not allowed with Time's total_seconds "
                        "constructor")
                self._set_from_total_seconds(total_seconds)
            elif hour is None and minute is None and second is None:
                # use the origin
                self.hour = 0               #: the hour, 0..24
                self.minute = 0         #: the minute, 0..59
                #: the seconds, 0..60 (to include leap seconds)
                self.second = 0
                # : an integer with the sign of the zone offset or None
                self.zdirection = None
                self.zoffset = None     #: the difference in minutes to UTC
            else:
                self._set_from_values(
                    hour, minute, second, zdirection, zhour, zminute)
                self._check_time()
        elif isinstance(src, Time):
            self.hour = src.hour
            self.minute = src.minute
            self.second = src.second
            self.zdirection = src.zdirection
            self.zoffset = src.zoffset
        else:
            raise TypeError("Can't construct Time from %s" % repr(src))

    def _set_from_total_seconds(self, total_seconds):
        t, overflow = type(self)().offset(seconds=total_seconds)
        if overflow:
            raise DateTimeError(
                "Can't construct Time from total_seconds=%i" % total_seconds)
        self.hour = t.hour
        self.minute = t.minute
        self.second = t.second
        self.zdirection = self.zoffset = None

    def get_total_seconds(self):
        """Note that leap seconds are handled as if they were invisible,
        e.g., 23:00:60 returns the same total seconds as 23:00:59."""
        if not self.complete():
            raise DateTimeError(
                "get_total_seconds requires complete precision")
        if self.second == 60:
            return 59 + self.minute * 60 + self.hour * 3600
        else:
            return self.second + self.minute * 60 + self.hour * 3600

    def _set_from_values(self, hour, minute, second, zdirection,
                         zhour, zminute):
        self.hour = hour
        self.minute = minute
        self.second = second
        self.zdirection = zdirection
        if zdirection is None:
            self.zoffset = None
        elif zdirection == 0:
            self.zoffset = 0
        elif zhour is None:
            raise DateTimeError(
                "non-zero UTC offset requires at least hour zone precision")
        elif zminute is None:
            self.zoffset = zhour * 60
        else:
            self.zoffset = zhour * 60 + zminute

    def get_time(self):
        """Returns a tuple of (hour,minute,second).

        Times with reduced precision will return None for second and or
        minute."""
        return self.hour, self.minute, self.second

    def get_zone(self):
        """Returns a tuple of::

        (zdirection, zoffset)

        zdirection is defined as per Time's constructor, zoffset is a
        non-negative integer minute offset or None, if the zone is
        unspecified for this Time."""
        return self.zdirection, self.zoffset

    def get_zone_offset(self):
        """Returns a single integer representing the zone offset (in
        minutes) or None if this time does not have a time zone
        offset."""
        if self.zdirection is None:
            return None
        else:
            return self.zdirection * self.zoffset

    def get_zone3(self):
        """Returns a tuple of::

        (zdirection, zhour, zminute)

        These values are defined as per Time's constructor."""
        zdirection = self.zdirection
        if zdirection is None:
            zhour = zminute = None
        elif zdirection == 0:
            zhour = zminute = 0
        else:
            zhour = self.zoffset // 60
            zminute = self.zoffset % 60
        return zdirection, zhour, zminute

    def get_canonical_zone(self):
        """Returns a tuple of::

        (zdirection, zhour, zminute)

        These values are defined as per Time's constructor but zero
        offsets always return zdirection=0.  If present, the zone is
        always returned with complete (minute) precision."""
        zdirection = self.zdirection
        if zdirection is None:
            zhour = zminute = None
        elif zdirection == 0 or self.zoffset == 0:
            zdirection = zhour = zminute = 0
        else:
            zhour = self.zoffset // 60
            zminute = self.zoffset % 60
        return zdirection, zhour, zminute

    def get_time_and_zone(self):
        """Returns a tuple of (hour,minute,second,zone direction,zone
        offset) as defined in get_time and get_zone."""
        return (self.hour, self.minute, self.second,
                self.zdirection, self.zoffset)

    def extend(self, hour=None, minute=None, second=None):
        """Constructs a :py:class:`Time` instance from an existing time,
        extended a (possibly) truncated hour/minute/second value.

        The time zone is always copied if present.  The result is a
        tuple of (<Time instance>,overflow) where overflow 0 or 1
        indicating whether or not the time overflowed.  For example::

            # set base to 20:17:40Z
            base=Time(hour=20,minute=17,second=40,zdirection=0)
            t,overflow=base.extend(minute=37)
            # t is 20:37:40Z, overflow is 0
            t,overflow=base.extend(minute=7)
            # t is 21:07:40Z, overflow is 0
            t,overflow=base.extend(hour=19,minute=7)
            # t is 19:07:40Z, overflow is 1"""
        if not self.complete():
            raise DateTimeError(
                "Can't construct truncated time from incomplete base: %s" %
                str(self))
        add_minute = add_hour = 0
        if hour is None:
            # Truncation of hour or more
            base_hour, base_minute, base_second = self.get_time()
            if second is None:
                base_second = None
                if minute is None:
                    base_minute = None
            new_hour = base_hour
            if minute is None:
                # Truncation of minutes
                new_minute = base_minute
                if second is None:
                    raise ValueError
                else:
                    new_second = second
                    if new_second < base_second:
                        add_minute = 1
            else:
                new_minute = minute
                new_second = second
                if new_minute < base_minute or (new_minute == base_minute and
                                                new_second < base_second):
                    add_hour = 1
        else:
            # no truncation
            new_hour = hour
            new_minute = minute
            new_second = second
        # always copy time zone from base
        zdirection, zhour, zminute = self.get_zone3()
        new_time = type(self)(hour=new_hour, minute=new_minute,
                              second=new_second, zdirection=zdirection,
                              zhour=zhour, zminute=zminute)
        if add_hour or add_minute:
            return new_time.offset(hours=add_hour, minutes=add_minute)
        else:
            return new_time, 0

    def offset(self, hours=0, minutes=0, seconds=0):
        """Constructs a :py:class:`Time` instance from an existing time
        and an offset number of hours, minutes and or seconds.

        The time zone is always copied (if present).  The result is a
        tuple of (<Time instance>,overflow) where overflow is the number
        of days by which the time overflowed.  For example::

            # set base to 20:17:40Z
            base = Time(hour=20, minute=17, second=40, zdirection=0)
            t, overflow = base.offset(minutes=37)
            # t is 20:54:40Z, overflow is 0
            t, overflow = base.offset(hours=4, minutes=37)
            # t is 00:54:40Z, overflow is 1

        Reduced precision times can still be offset but only by matching
        arguments.  In other words, if the time has minute precision
        then you may not pass a non-zero value for seconds, etc.  A
        similar constraint applies to the passing of floating point
        arguments.  You may pass a fractional offset for seconds if the
        time has second precision but the minute and hour offsets must
        be to integer precision.  Similarly, you may pass a fractional
        offset for minutes if the time has minute precision, etc."""
        days = 0
        second = self.second
        if seconds:
            if second is None:
                raise DateTimeError("second precision required")
            second = second + seconds
            if isinstance(second, float):
                fs, s = modf(second)
                s = int(s)
                minutes += s // 60
                second = float(s % 60) + fs
            else:
                minutes += second // 60
                second = second % 60
        minute = self.minute
        if minutes:
            if minute is None:
                raise DateTimeError("minute or second precision required")
            minute = minute + minutes
            if isinstance(minute, float):
                if second is not None:
                    raise DateTimeError("minute precision required")
                fm, m = modf(minute)
                m = int(m)
                hours += minute // 60
                minute = float(minute % 60) + fm
            else:
                hours += minute // 60
                minute = minute % 60
        hour = self.hour
        if hours:
            hour = hour + hours
            if isinstance(hour, float):
                if minute is not None:
                    raise DateTimeError("hour precision required")
                fh, h = modf(hour)
                h = int(h)
                days += float(h // 24)
                hour = float(hour % 24) + fh
            else:
                days += hour // 24
                hour = hour % 24
        # always copy time zone from base
        zdirection, zhour, zminute = self.get_zone3()
        return type(self)(hour=hour, minute=minute, second=second,
                          zdirection=zdirection, zhour=zhour,
                          zminute=zminute), days

    def with_zone(self, zdirection, zhour=None, zminute=None, **kwargs):
        """Replace time zone information

        Constructs a new :py:class:`Time` instance from an existing time
        but with the time zone specified.  The time zone of the existing
        time is ignored.  Pass *zdirection*\=None to strip the zone
        information completely."""
        zdirection = kwargs.get('zDirection', zdirection)
        zhour = kwargs.get('zHour', zhour)
        zminute = kwargs.get('zMinute', zminute)
        return type(self)(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            zdirection=zdirection,
            zhour=zhour,
            zminute=zminute)

    def shift_zone(self, zdirection, zhour=None, zminute=None, **kwargs):
        """Constructs a :py:class:`Time` instance from an existing time
        but shifted so that it is in the time zone specified.  The return
        value is a tuple of::

            (<Time instance>, overflow)

        overflow is one of -1, 0 or 1 indicating if the time over- or
        under-flowed as a result of the time zone shift."""
        zdirection = kwargs.get('zDirection', zdirection)
        zhour = kwargs.get('zHour', zhour)
        zminute = kwargs.get('zMinute', zminute)
        if self.zoffset is None:
            raise DateTimeError(
                "Can't shift time with unspecified zone: " + str(self))
        if zdirection is None or (zdirection != 0 and zhour is None):
            raise DateTimeError("Can't shift time to unspecified zone")
        # start by calculating the time shift
        new_offset = zdirection * \
            ((0 if zhour is None else zhour) * 60 +
             (0 if zminute is None else zminute))
        zshift = new_offset - self.get_zone_offset()
        second = self.second
        if self.second is None:
            if self.minute is None:
                # hour precision only - the shift better be a whole number of
                # hours
                if zshift % 60:
                    raise DateTimeError(
                        "Zone shift of %i minutes requires at least "
                        "minute precision: " % zshift)
        # // and % may seem odd when negative shifting but this still works
        # shift of -105 minutes results in +15 minutes and -2 hours!
        minute = self.minute
        hour = self.hour
        if minute is not None:
            minute = minute + zshift % 60
            if minute > 59:
                hour += 1
                minute -= 60
            elif minute < 0:
                hour -= 1
                minute += 60
        hour = hour + zshift // 60
        if hour > 23:
            hour -= 24
            overflow = 1
        elif hour < 0:
            hour += 24
            overflow = -1
        else:
            overflow = 0
        return type(self)(hour=hour, minute=minute, second=second,
                          zdirection=zdirection, zhour=zhour,
                          zminute=zminute), overflow

    @classmethod
    def from_struct_time(cls, t):
        """Constructs a zone-less :py:class:`Time` from a struct_time,
        such as might be returned from time.gmtime() and related
        functions."""
        return cls(hour=t[3], minute=t[4], second=t[5])

    def update_struct_time(self, t):
        """update_struct_time changes the hour, minute, second and isdst
        fields of t, a struct_time, to match the values in this time.

        isdst is always set to -1"""
        if not self.complete():
            raise DateTimeError("update_struct_time requires a complete time")
        t[3] = self.hour
        t[4] = self.minute
        t[5] = self.second
        t[8] = -1

    @classmethod
    def from_now(cls):
        """Constructs a :py:class:`Time` from the current local time."""
        return cls.from_struct_time(pytime.localtime(pytime.time()))

    @classmethod
    def from_str(cls, src, base=None):
        """Constructs a :py:class:`Time` instance from a string
        representation, truncated forms are returned as the earliest
        time on or after *base* and may have overflowed.  See
        :py:meth:`from_string_format` for more."""
        if is_text(src):
            p = ISO8601Parser(src)
            t, overflow, f = p.parse_time_format(base)
            return t
        else:
            raise TypeError

    def with_zone_string(self, zone_str):
        """Constructs a :py:class:`Time` instance from an existing time
        but with the time zone parsed from *zone_str*.  The time zone of
        the existing time is ignored."""
        if is_text(zone_str):
            p = ISO8601Parser(zone_str)
            zdirection, zhour, zminute, format = p.parse_time_zone_format()
            return self.with_zone(
                zdirection=zdirection, zhour=zhour, zminute=zminute)
        else:
            raise TypeError

    def with_zone_string_format(self, zone_str):
        """Constructs a :py:class:`Time` instance from an existing time
        but with the time zone parsed from *zone_str*.  The time zone of
        the existing time is ignored.

        Returns a tuple of: (<Time instance>,format)"""
        if is_text(zone_str):
            p = ISO8601Parser(zone_str)
            zdirection, zhour, zminute, format = p.parse_time_zone_format()
            return self.with_zone(
                zdirection=zdirection, zhour=zhour, zminute=zminute), format
        else:
            raise TypeError

    @classmethod
    def from_string_format(cls, src, base=None):
        """Constructs a :py:class:`Time` instance from a string
        representation, truncated forms are returned as the earliest
        time on or after *base*.

        Returns a tuple of (<Time instance>,overflow,format) where
        overflow is 0 or 1 indicating whether or not a truncated form
        overflowed and format is a string representation of the format
        parsed, e.g., "hhmmss"."""
        if is_text(src):
            p = ISO8601Parser(src)
            return p.parse_time_format(base)
        else:
            raise TypeError

    def __unicode__(self):
        return self.get_string()

    def __repr__(self):
        return ("Time(hour=%s, minute=%s, second=%s, zdirection=%s, "
                "zhour=%s, zminute=%s)" %
                ((str(self.hour), str(self.minute), str(self.second)) +
                 tuple(map(str, self.get_zone3()))))

    def get_string(self, basic=False, truncation=NoTruncation, ndp=0,
                   zone_precision=Precision.Complete, dp=",", **kwargs):
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

        *zone_precision*
            One of :py:attr:`Precision.Hour` or
            :py:attr:`Precision.Complete` to control the precision
            of the zone offset.

        Note that time formats only support Minute and Second truncated
        forms."""
        zone_precision = kwargs.get('zonePrecision', zone_precision)
        if ndp < 0:
            warnings.warn(
                "Replace negative ndp in Time.get_string with "
                "dp parameter instead", DeprecationWarning, stacklevel=2)
            ndp = -ndp
            dp = "."
        if self.second is None:
            if self.minute is None:
                if self.hour is None:
                    raise DateTimeError("no time to format")
                else:
                    if truncation == NoTruncation:
                        if isinstance(self.hour, float):
                            fraction, hour = modf(self.hour)
                            hour = int(hour)
                        else:
                            fraction, hour = 0, self.hour
                        stem = "%02i" % hour
                    else:
                        raise ValueError
            else:
                if isinstance(self.minute, float):
                    fraction, minute = modf(self.minute)
                    minute = int(minute)
                else:
                    fraction, minute = 0, self.minute
                if truncation == NoTruncation:
                    if basic:
                        stem = "%02i%02i" % (self.hour, minute)
                    else:
                        stem = "%02i:%02i" % (self.hour, minute)
                elif truncation == Truncation.Hour:
                    stem = "-%02i" % minute
                else:
                    raise ValueError
        else:
            if isinstance(self.second, float):
                fraction, second = modf(self.second)
                second = int(second)
            else:
                fraction, second = 0, self.second
            if truncation == NoTruncation:
                if basic:
                    stem = "%02i%02i%02i" % (self.hour, self.minute, second)
                else:
                    stem = "%02i:%02i:%02i" % (self.hour, self.minute, second)
            elif truncation == Truncation.Hour:
                if basic:
                    stem = "-%02i%02i" % (self.minute, second)
                else:
                    stem = "-%02i:%02i" % (self.minute, second)
            elif truncation == Truncation.Minute:
                stem = "--%02i" % second
        if ndp:
            # to prevent truncation being caught out by sloppy machine rounding
            # we add a small time to the fraction (at most 1ns and typically
            # less)
            fraction_str = "%s%s%0*i"
            fraction += 2e-13
            fraction = int(floor(fraction * float(10 ** ndp)))
            stem = fraction_str % (stem, dp, ndp, fraction)
        if truncation == NoTruncation:
            # untruncated forms can have a zone string
            stem += self.get_zone_string(basic, zone_precision)
        return stem

    def get_zone_string(self, basic=False, zone_precision=Precision.Complete,
                        **kwargs):
        """Formats this time's zone, for example -05:00.

        *basic*
            True/False, selects basic form, e.g., -0500.  Default
            is False

        *zone_precision*
            One of :py:attr:`Precision.Hour` or
            :py:attr:`Precision.Complete` to control the precision
            of the zone offset.

        Times constructed with a zdirection value of 0 are always
        rendered using "Z" for Zulu time (the name is taken from the
        phonetic alphabet).  To force use of the offset format you must
        construct the time with a non-zero value for zdirection."""
        zone_precision = kwargs.get('zonePrecision', zone_precision)
        if self.zdirection is None:
            return ""
        elif self.zdirection == 0:
            return "Z"
        else:
            if self.zdirection > 0:
                zstr = "+"
            else:
                zstr = "-"
            hour = self.zoffset // 60
            minute = self.zoffset % 60
            if zone_precision == Precision.Complete or minute > 0:
                if basic:
                    return "%s%02i%02i" % (zstr, hour, minute)
                else:
                    return "%s%02i:%02i" % (zstr, hour, minute)
            else:
                if basic:
                    return "%s%02i" % (zstr, hour)
                else:
                    return "%s%02i" % (zstr, hour)

    def complete(self):
        """Returns True if this date has a complete representation,
        i.e., does not use one of the reduced precision forms.

        (Whether or not a time is complete refers only to the precision
        of the time value, it says nothing about the presence or absence
        of a time zone offset.)"""
        return (self.hour is not None and self.minute is not None and
                self.second is not None)

    def get_precision(self):
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

    def with_precision(self, precision, truncate=False):
        """Constructs a :py:class:`Time` instance from an existing time but
        with the precision specified by *precision*.

        *precision* is one of the :py:class:`Precision` constants, only
        hour, minute and complete precision are valid.

        *truncate* is True/False indicating whether or not the time
        value should be truncated so that all values are integers.  For
        example::

            t = Time(hour=20, minute=17, second=40)
            tm = t.with_precision(Precision.Minute, False)
            print tm.get_string(ndp=3)
            #   20:17,667
            tm=t.with_precision(Precision.Minute, True)
            print tm.get_string(ndp=3)
            #   20:17,000   """
        hour = self.hour
        minute = self.minute
        second = self.second
        if precision == Precision.Complete:
            if second is None:
                if minute is None:
                    if hour is None:
                        raise DateTimeError("Missing time")
                    elif isinstance(hour, float):
                        minute, hour = modf(hour)
                        minute *= 60.0
                        hour = int(hour)
                    else:
                        minute = 0
                if isinstance(minute, float):
                    second, minute = modf(minute)
                    second *= 60.0
                    minute = int(minute)
                else:
                    second = 0
            if truncate and isinstance(second, float):
                second = int(floor(second))
        elif precision == Precision.Minute:
            if second is None:
                if minute is None:
                    if hour is None:
                        raise DateTimeError("Missing time")
                    elif isinstance(hour, float):
                        minute, hour = modf(hour)
                        minute *= 60.0
                        hour = int(hour)
                    else:
                        minute = 0
                if truncate and isinstance(minute, float):
                    minute = int(floor(minute))
            elif truncate:
                second = None
            else:
                minute = float(minute) + second / 60.0
                second = None
        elif precision == Precision.Hour:
            if second is None:
                if minute is None:
                    if hour is None:
                        hour = 0
                    elif truncate and isinstance(hour, float):
                        hour = int(floor(hour))
                elif truncate:
                    minute = None
                else:
                    hour = float(hour) + minute / 60.0
                    minute = None
            elif truncate:
                minute = second = None
            else:
                hour = float(hour) + minute / 60.0 + second / 3600.0
                minute = second = None
        else:
            raise ValueError
        zdirection, zhour, zminute = self.get_zone3()
        return type(self)(hour=hour, minute=minute, second=second,
                          zdirection=zdirection, zhour=zhour, zminute=zminute)

    def _check_time(self):
        if self.zdirection is not None:
            if self.zdirection < -1 or self.zdirection > +1:
                raise DateTimeError(
                    "zone direction out of range %i" % self.zdirection)
            if self.zdirection != 0:
                if self.zoffset is None:
                    raise DateTimeError("missing zone offset")
                elif self.zoffset >= 1440:
                    raise DateTimeError(
                        "zone offset out of range %i:%02i" %
                        (self.zoffset // 60, self.zoffset % 60))
        if self.hour is None:
            raise DateTimeError("missing time")
        if self.hour < 0 or self.hour > 24:
            raise DateTimeError("hour out of range %i" % self.hour)
        if self.hour == 24 and (
                (self.minute is not None and self.minute > 0) or
                (self.second is not None and self.second > 0)):
            raise DateTimeError("time overflow")
        if self.minute is None:
            return
        if isinstance(self.hour, float):
            raise DateTimeError("bad fractional hour %s" % str(self.hour))
        if self.minute < 0 or self.minute > 59:
            raise DateTimeError("minute out of range %s" % str(self.minute))
        if self.second is None:
            return
        if isinstance(self.minute, float):
            raise DateTimeError("bad fractional minute %s" % str(self.minute))
        if self.second < 0 or self.second >= 61:
            raise DateTimeError("second out of range %s" % str(self.second))

    def sortkey(self):
        z = self.get_zone_offset()
        if z is None:
            return (self.hour, self.minute, self.second)
        else:
            return (self.hour, self.minute, self.second, z)

    def otherkey(self, other):
        if is_string(other):
            other = self.from_str(other)
        if isinstance(other, self.__class__):
            if self.get_precision() == other.get_precision() and \
                    self.get_zone_offset() == other.get_zone_offset():
                return other.sortkey()
        return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())

    def set_origin(self):
        warnings.warn(
            "Time.set_origin is deprecated, use Time() instead",
            DeprecationWarning, stacklevel=2)
        self._set_from_values(0, 0, 0, None, None, None)

    def set_seconds(self, s):
        warnings.warn(
            "Time.set_seconds is deprecated, use "
            "Time().offset(seconds=s) instead", DeprecationWarning,
            stacklevel=2)
        t, overflow = type(self)().offset(seconds=s)
        self.set_from_time(t)
        return overflow

    def add_seconds(self, s):
        warnings.warn(
            "Time.add_seconds is deprecated, use "
            "Time().offset(seconds=s) instead", DeprecationWarning,
            stacklevel=2)
        t, overflow = self.offset(seconds=s)
        self.set_from_time(t)
        return overflow

    def add_minute(self):
        warnings.warn(
            "Time.add_minute is deprecated, use "
            "Time().offset(minutes=1) instead", DeprecationWarning,
            stacklevel=2)
        t, overflow = self.offset(minutes=1)
        self.set_from_time(t)
        return overflow

    def add_hour(self):
        warnings.warn(
            "Time.add_hour is deprecated, use Time().offset(hour=1) instead",
            DeprecationWarning, stacklevel=2)
        t, overflow = self.offset(hours=1)
        self.set_from_time(t)
        return overflow

    def set_time(self, hour, minute, second, base=None):
        warnings.warn(
            "Time.set_time is deprecated, use Time(hour=##,...) or "
            "base.extend(hour=##,...) instead", DeprecationWarning,
            stacklevel=2)
        if base is None:
            t = type(self)(hour=hour, minute=minute, second=second)
            overflow = 0
        else:
            t, overflow = base.extend(hour=hour, minute=minute, second=second)
        self.set_from_time(t)
        return overflow

    def set_zone(self, zdirection, hour_offset=None, minute_offset=None,
                 **kwargs):
        zdirection = kwargs.get('zDirection', zdirection)
        hour_offset = kwargs.get('hourOffset', hour_offset)
        minute_offset = kwargs.get('minuteOffset', minute_offset)
        warnings.warn(
            "Time.set_zone is deprecated, use with_zone(zdirection, etc...) "
            "instead", DeprecationWarning, stacklevel=2)
        t = self.with_zone(zdirection, hour_offset, minute_offset)
        self.set_from_time(t)

    def get_seconds(self):
        warnings.warn(
            "Time.get_seconds is deprecated, use get_total_seconds() instead",
            DeprecationWarning, stacklevel=2)
        return self.get_total_seconds()

    def set_from_time(self, src):
        warnings.warn(
            "Time.set_from_time is deprecated, use Time(src) instead",
            DeprecationWarning, stacklevel=2)
        self.hour = src.hour
        self.minute = src.minute
        self.second = src.second
        self.zdirection = src.zdirection
        self.zoffset = src.zoffset

    def set_time_tuple(self, t):
        warnings.warn(
            "Time.set_time_tuple is deprecated, use "
            "Time.from_struct_time(t) instead", DeprecationWarning,
            stacklevel=2)
        t = Time.from_struct_time(t)
        self.set_from_time(t)

    def get_time_tuple(self, t):
        warnings.warn(
            "Time.get_time_tuple is deprecated, use "
            "Time.update_struct_time(t) instead", DeprecationWarning,
            stacklevel=2)
        self.update_struct_time(t)

    def now(self):
        warnings.warn(
            "Time.now is deprecated, use Time.from_now() instead",
            DeprecationWarning, stacklevel=2)
        t = Time.from_now()
        self.set_from_time(t)

    def set_from_string(self, src, base=None):
        raise DateTimeError(
            "Time is now immutable: \n"
            "Replace t.set_from_string(src, base) with\n"
            "t = Time.from_str(src, base)")

    def set_zone_from_string(self, zone_str):
        warnings.warn(
            "Time.set_zone_from_string is deprecated, use "
            "Time.with_zone_string(t, zone_str) instead", DeprecationWarning,
            stacklevel=2)
        if is_text(zone_str):
            p = ISO8601Parser(zone_str)
            return p.parse_time_zone(self)
        else:
            raise TypeError

    def set_precision(self, precision, truncate=False):
        warnings.warn(
            "Time.set_precision is deprecated, use "
            "with_precision(precision, truncate) instead", DeprecationWarning,
            stacklevel=2)
        t = self.with_precision(precision, truncate)
        self.set_from_time(t)

    def change_zone(self, zchange):
        warnings.warn(
            "Time.change_zone is deprecated, use "
            "shift_zone(zdirection, zhour, zminute) instead",
            DeprecationWarning, stacklevel=2)
        # we need to calculate the new zone from zchange
        z = self.get_zone_offset()
        if z is None:
            raise ValueError(
                "Time zone required for change_zone " + str(self))
        new_offset = z + zchange
        if new_offset == 0:
            t, overflow = self.shift_zone(zdirection=0)
        elif new_offset < 0:
            new_offset = -new_offset
            t, overflow = self.shift_zone(
                zdirection=-1, zhour=new_offset // 60, zminute=new_offset % 60)
        else:
            t, overflow = self.shift_zone(
                zdirection=1, zhour=new_offset // 60, zminute=new_offset % 60)
        self.set_from_time(t)
        return overflow


class TimePoint(PEP8Compatibility, UnicodeMixin, SortableMixin):

    """A class for representing ISO timepoints

    TimePoints are constructed from a date and a time (which may or
    may not have a time zone), for example::

        TimePoint(date=Date(century=19,year=69,month=7,day=20),
                  time=Time(hour=20,minute=17,second=40,zdirection=0))

    If the date is missing then the date origin is used, Date() or
    0001-01-01.  Similarly, if the time is missing then the time
    origin is used, Time() or 00:00:00

    Times may be given with reduced precision but the date must be
    complete. In other words, there is no such thing as a timepoint
    with, month precision, use Date instead.  Expanded dates may be used.

    When comparing TimePoint instances we deal with partially specified
    TimePoints in the same way as :class:`Time`.  However, unlike the
    comparison of Time instances, we reduce all TimePoints with
    time-zones to a common zone before doing a comparison. As a result,
    TimePoints which are equal but are expressed in different time zones
    will still compare equal.

    Instances can be converted directly to strings or unicode strings
    using the default, extended calendar format.  Other formats are
    supported through format specific methods."""

    def __init__(self, src=None, date=None, time=None):
        PEP8Compatibility.__init__(self)
        if src is None:
            # explicit form
            if date is None:
                self.date = Date()
            else:
                self.date = date
            if time is None:
                self.time = Time()
            else:
                self.time = time
            self._check_time_point()
        elif isinstance(src, TimePoint):
            self.date = src.date
            self.time = src.time
        else:
            raise TypeError("Can't construct TimePoint from %s" % repr(src))

    def get_calendar_time_point(self):
        """Returns a tuple representing the calendar time point

        The result is::

            (century, year, month, day, hour, minute, second)

        This method cannot be used for expanded dates, use
        :meth:`get_xcalendar_time_point` instead when dealing with dates
        outside of the normal ISO 8601 range."""
        return self.date.get_calendar_day() + self.time.get_time()

    def get_xcalendar_time_point(self):
        """Returns a tuple representing an expanded calendar time point

        The result is::

            (bce, century, year, month, day, hour, minute, second)"""
        return self.date.get_xcalendar_day() + self.time.get_time()

    def get_ordinal_time_point(self):
        """Returns a tuple representing the ordinal time point

        The result is::

            (century, year, ordinal_day, hour, minute, second)

        This method cannot be used for expanded dates, use
        :meth:`get_xordinal_time_point` instead when dealing with dates
        outside of the normal ISO 8601 range."""
        return self.date.get_ordinal_day() + self.time.get_time()

    def get_xordinal_time_point(self):
        """Returns a tuple representing an expanded ordinal time point

        The result is::

            (bce, century, year, ordinal_day, hour, minute, second)"""
        return self.date.get_xordinal_day() + self.time.get_time()

    def get_week_day_time_point(self):
        """Returns a tuple representing the week-day time point

        The result is::

            (century, decade, year, week, weekday, hour, minute,
             second)

        This method cannot be used for expanded dates, use
        :meth:`get_xweek_day_time_point` instead when dealing with dates
        outside of the normal ISO 8601 range."""
        return self.date.get_week_day() + self.time.get_time()

    def get_xweek_day_time_point(self):
        """Returns a tuple representing an expanded week-day time point

        The result is::

            (bce, century, decade, year, week, weekday, hour, minute,
             second)"""
        return self.date.get_xweek_day() + self.time.get_time()

    def get_zone(self):
        """Returns a tuple representing the zone

        The result is (zdirection, zoffset)

        See :py:meth:`Time.get_zone` for details."""
        return self.time.get_zone()

    def expand(self, xdigits):
        """Constructs a new expanded instance

        The purpose of this method is to create a new instance from an
        existing TimePoint but with a different date expansion (value of
        xdigits).

        This is equivalent to::

            TimePoint(date=self.date.expand(xdigits), time=self.time)"""
        return self.__class__(date=self.date.expand(xdigits), time=self.time)

    def with_zone(self, zdirection, zhour=None, zminute=None, **kwargs):
        """Constructs a :py:class:`TimePoint` instance from an existing
        TimePoint but with the time zone specified.  The time zone of
        the existing TimePoint is ignored."""
        zdirection = kwargs.get('zDirection', zdirection)
        zhour = kwargs.get('zHour', zhour)
        zminute = kwargs.get('zMinute', zminute)
        return type(self)(
            date=self.date,
            time=self.time.with_zone(
                zdirection=zdirection,
                zhour=zhour,
                zminute=zminute))

    def shift_zone(self, zdirection, zhour=None, zminute=None, **kwargs):
        """Shifts time zone

        Constructs a :py:class:`TimePoint` instance from an existing
        TimePoint but shifted so that it is in the time zone
        specified."""
        zdirection = kwargs.get('zDirection', zdirection)
        zhour = kwargs.get('zHour', zhour)
        zminute = kwargs.get('zMinute', zminute)
        t, overflow = self.time.shift_zone(zdirection, zhour, zminute)
        if overflow:
            d = self.date.offset(days=overflow)
        else:
            d = self.date
        return type(self)(date=d, time=t)

    def update_struct_time(self, t):
        """Outputs the TimePoint in struct_time format

        Changes the year, month, date, hour, minute and second fields of
        t, t must be a mutable list arranged in the same order as
        struct_time."""
        self.date.update_struct_time(t)
        self.time.update_struct_time(t)

    @classmethod
    def from_struct_time(cls, t):
        """Constructs an instance from a struct_time

        In other words, constructs an instance from the object returned
        from time.gmtime() and related functions."""
        return cls(date=Date.from_struct_time(t),
                   time=Time.from_struct_time(t))

    @classmethod
    def from_str(cls, src, base=None, tdesignators="T", xdigits=None):
        """Constructs a TimePoint from a string representation.
        Truncated forms are parsed with reference to *base*."""
        if is_text(src):
            p = ISO8601Parser(src)
            if xdigits is None:
                tp, f = p.parse_time_point_format(base, tdesignators)
            else:
                tp, f = p.require_xtime_point_format(xdigits, tdesignators)
            return tp
        else:
            raise TypeError

    @classmethod
    def from_string_format(cls, src, base=None, tdesignators="T", xdigits=None,
                           **kwargs):
        """Creates an instance from a string

        Similar to :py:meth:`from_str` except that a tuple is returned,
        the first item is the resulting :py:class:`TimePoint` instance,
        the second is a string describing the format parsed. For
        example::

            tp, f = TimePoint.from_string_format("1969-07-20T20:40:17")
            # f is set to "YYYY-MM-DDTmm:hh:ss"."""
        tdesignators = kwargs.get('tDesignators', tdesignators)
        if is_text(src):
            p = ISO8601Parser(src)
            if xdigits is None:
                return p.parse_time_point_format(base, tdesignators)
            else:
                return p.require_xtime_point_format(xdigits, tdesignators)
        else:
            raise TypeError

    def __unicode__(self):
        return self.get_calendar_string()

    def __repr__(self):
        return "TimePoint(date=%s,time=%s)" % (
            repr(self.date), repr(self.time))

    def get_calendar_string(self, basic=False, truncation=NoTruncation, ndp=0,
                            zone_precision=Precision.Complete, dp=",",
                            tdesignator="T", **kwargs):
        """Formats this TimePoint using calendar form

        For example '1969-07-20T20:17:40'

        *basic*
            True/False, selects basic form, e.g., 19690720T201740.
            Default is False

        *truncation*
            One of the :py:class:`Truncation` constants used to
            select truncated forms of the date.  For example, if you
            specify :py:attr:`Truncation.Year` you'll get
            --07-20T20:17:40 or --0720T201740.  Default is
            :py:attr:`NoTruncation`.  Calendar format only
            supports Century, Year and Month truncated forms, the time
            component cannot be truncated.

        *ndp*, *dp* and *zone_precision*
            As specified in :py:meth:`Time.get_string`

        If the instance is an expanded time point with xdigits=-1 then
        basic format is not allowed."""
        zone_precision = kwargs.get('zonePrecision', zone_precision)
        tdesignator = kwargs.get('tDesignator', tdesignator)
        return (self.date.get_calendar_string(basic, truncation) +
                tdesignator + self.time.get_string(basic, NoTruncation,
                                                   ndp, zone_precision, dp))

    def get_ordinal_string(self, basic=0, truncation=0, ndp=0,
                           zone_precision=Precision.Complete, dp=",",
                           tdesignator="T", **kwargs):
        """Formats this TimePoint using ordinal form

        For example '1969-201T20:17:40'

        *basic*
            True/False, selects basic form, e.g., 1969201T201740.
            Default is False

        *truncation*
            One of the :py:class:`Truncation` constants used to select
            truncated forms of the date.     For example, if you specify
            :py:attr:`Truncation.Year` you'll get -201T20-17-40. Default
            is :py:attr:`NoTruncation`. Note that ordinal format only
            supports century and year truncated forms, the time
            component cannot be truncated.

        *ndp*, *dp* and *zone_precision*
            As specified in :py:meth:`Time.get_string`

        If the instance is an expanded time point with xdigits=-1 then
        basic format is not allowed."""
        zone_precision = kwargs.get('zonePrecision', zone_precision)
        tdesignator = kwargs.get('tDesignator', tdesignator)
        return self.date.get_ordinal_string(basic, truncation) + tdesignator +\
            self.time.get_string(basic, NoTruncation, ndp, zone_precision, dp)

    def get_week_string(self, basic=0, truncation=0, ndp=0,
                        zone_precision=Precision.Complete, dp=",",
                        tdesignator="T", **kwargs):
        """Formats this TimePoint using week form

        For example '1969-W29-7T20:17:40'

        *basic*
            True/False, selects basic form, e.g., 1969W297T201740.
            Default is False

        *truncation*
            One of the :py:class:`Truncation` constants used to select
            truncated forms of the date.     For example, if you specify
            :py:attr:`Truncation.Year` you'll get -W297T20-17-40.
            Default is :py:attr:`NoTruncation`. Note that week format
            only supports century, decade, year and week truncated
            forms, the time component cannot be truncated.

        *ndp*, *dp* and *zone_precision*
            As specified in :py:meth:`Time.get_string`

        If the instance is an expanded time point with xdigits=-1 then
        basic format is not allowed."""
        zone_precision = kwargs.get('zonePrecision', zone_precision)
        tdesignator = kwargs.get('tDesignator', tdesignator)
        return self.date.get_week_string(basic, truncation) + tdesignator +\
            self.time.get_string(basic, NoTruncation, ndp, zone_precision, dp)

    @classmethod
    def from_unix_time(cls, unix_time):
        """Constructs a TimePoint from *unix_time*, the number of seconds
        since the time origin.  The resulting time is in UTC.

        This method uses python's gmtime(0) to obtain the time origin,
        it isn't necessarily the Unix base time of 1970-01-01."""
        utc_tuple = pytime.gmtime(0)
        t, overflow = Time.from_struct_time(utc_tuple).offset(
            seconds=unix_time)
        d = Date.from_struct_time(utc_tuple).offset(days=overflow)
        return cls(date=d, time=t.with_zone(zdirection=0))

    def get_unixtime(self):
        """Returns a unix time value representing this time point."""
        if not self.complete():
            raise DateTimeError("get_unixtime requires complete timepoint")
        zoffset = self.time.get_zone_offset()
        if zoffset is None:
            raise DateTimeError("get_unixtime requires timezone")
        elif zoffset == 0:
            zt = self
        else:
            zt = self.shift_zone(zdirection=0)
        days = zt.date.get_absolute_day() - EPOCH.date.get_absolute_day()
        seconds = zt.time.get_total_seconds() - EPOCH.time.get_total_seconds()
        return 86400 * days + seconds

    @classmethod
    def from_now(cls):
        """Constructs a TimePoint from the current local date and time."""
        t = pytime.time()
        local_time = pytime.localtime(t)
        return cls.from_struct_time(local_time)

    @classmethod
    def from_now_utc(cls):
        """Constructs a TimePoint from the current UTC date and time."""
        t = pytime.time()
        utc_time = pytime.gmtime(t)
        return cls.from_struct_time(utc_time).with_zone(zdirection=0)

    def complete(self):
        """Test for complete precision

        Returns True if this TimePoint has a complete representation,
        i.e., does not use one of the reduced precision forms

        (Whether or not a TimePoint is complete refers only to the
        precision of the time value, it says nothing about the presence
        or absence of a time zone offset.)"""
        return self.date.complete() and self.time.complete()

    def get_precision(self):
        """Returns one of the :py:class:`Precision` constants
        representing the precision of this TimePoint."""
        return self.time.get_precision()

    def with_precision(self, precision, truncate):
        """Return new instance with *precision*

        Constructs a :py:class:`TimePoint` instance from an existing
        TimePoint but with the precision specified by *precision*.  For
        more details see :py:meth:`Time.with_precision`"""
        return type(self)(date=self.date,
                          time=self.time.with_precision(precision, truncate))

    def _check_time_point(self):
        self.date._check_date()
        self.time._check_time()
        if self.date.get_precision() != Precision.Complete:
            raise DateTimeError(
                "timepoint requires complete precision for date")

    def sortkey(self):
        if self.time.get_zone_offset():
            # force UTC for comparisons and hashing
            return self.shift_zone(zdirection=0).sortkey()
        else:
            # no zone, or Zulu time
            return tuple(list(self.date.sortkey()) + list(self.time.sortkey()))

    def otherkey(self, other):
        if is_string(other):
            other = self.from_str(other)
        if isinstance(other, self.__class__):
            if self.get_precision() == other.get_precision():
                zself = self.time.get_zone_offset()
                zother = other.time.get_zone_offset()
                if (zself is None) ^ (zother is None):
                    # can't compare a time with a zone with one without
                    return NotImplemented
                return other.sortkey()
        return NotImplemented

    def __hash__(self):
        return hash(self.sortkey())

    def set_origin(self):
        warnings.warn(
            "TimePoint.set_origin is deprecated, use TimePoint() instead",
            DeprecationWarning, stacklevel=2)
        self.date = Date()
        self.time = Time()

    def set_from_time_point(self, t):
        warnings.warn(
            "TimePoint.set_from_time_point is deprecated, use "
            "TimePoint(t.date,t.time) instead",
            DeprecationWarning, stacklevel=2)
        self.date = Date(t.date)
        self.time = Time(t.time)

    def set_calendar_time_point(self, century, year, month, day,
                                hour, minute, second, base=None):
        warnings.warn(
            "TimePoint.set_calendar_time_point is deprecated, use"
            "TimePoint(Date(century=...), Time(hour=...)) instead",
            DeprecationWarning, stacklevel=2)
        self.set_from_time_point(
            TimePoint(date=Date(century=century, year=year, month=month,
                                day=day, base=base),
                      time=Time(hour=hour, minute=minute, second=second)))

    def set_ordinal_time_point(self, century, year, ordinal_day,
                               hour, minute, second, base=None, **kwargs):
        ordinal_day = kwargs.get('ordinalDay', ordinal_day)
        warnings.warn(
            "TimePoint.set_ordinal_time_point is deprecated, use "
            "TimePoint(Date(century=...), Time(hour=...)) instead",
            DeprecationWarning, stacklevel=2)
        self.set_from_time_point(
            TimePoint(date=Date(century=century, year=year,
                                ordinal_day=ordinal_day, base=base),
                      time=Time(hour, minute, second)))

    def set_week_time_point(self, century, decade, year, week, day,
                            hour, minute, second, base=None):
        warnings.warn(
            "TimePoint.set_week_time_point is deprecated, use "
            "TimePoint(Date(century=...), Time(hour=...)) instead",
            DeprecationWarning, stacklevel=2)
        self.set_from_time_point(
            TimePoint(date=Date(century=century, decade=decade, year=year,
                                week=week, day=day, base=base),
                      time=Time(hour=hour, minute=minute, second=second)))

    def set_from_string(self, time_point_str, base=None):
        raise DateTimeError(
            "TimePoint is now immutable: \n"
            "Replace tp.set_from_string(src, base) with\n"
            "tp = TimePoint.from_str(src, base)")

    def set_zone(self, zdirection, hour_offset=None, minute_offset=None,
                 **kwargs):
        zdirection = kwargs.get('zDirection', zdirection)
        hour_offset = kwargs.get('hourOffset', hour_offset)
        minute_offset = kwargs.get('minuteOffset', minute_offset)
        warnings.warn(
            "TimePoint.set_zone is deprecated, use "
            "TimePoint.with_zone(zdirection, etc...) instead",
            DeprecationWarning, stacklevel=2)
        t = self.time.with_zone(zdirection, hour_offset, minute_offset)
        self.set_from_time_point(TimePoint(date=self.date, time=t))

    def get_time_tuple(self, time_tuple):
        warnings.warn(
            "TimePoint.get_time_tuple is deprecated, use "
            "TimePoint.update_struct_time(t) instead", DeprecationWarning,
            stacklevel=2)
        self.update_struct_time(time_tuple)

    def set_time_tuple(self, t):
        warnings.warn(
            "TimePoint.set_time_tuple is deprecated, use "
            "TimePoint.from_struct_time(t) instead", DeprecationWarning,
            stacklevel=2)
        self.set_from_time_point(TimePoint.from_struct_time(t))

    def set_unix_time(self, unix_time):
        warnings.warn(
            "TimePoint.set_unix_time is deprecated, use "
            "TimePoint.from_unix_time(t) instead", DeprecationWarning,
            stacklevel=2)
        self.set_from_time_point(TimePoint.from_unix_time(unix_time))

    def now(self):
        warnings.warn(
            "TimePoint.now is deprecated, use TimePoint.from_now() instead",
            DeprecationWarning,
            stacklevel=2)
        self.set_from_time_point(TimePoint.from_now())

    def now_utc(self):
        warnings.warn(
            "TimePoint.now_utc is deprecated, use "
            "TimePoint.from_now_utc() instead", DeprecationWarning,
            stacklevel=2)
        self.set_from_time_point(TimePoint.from_now_utc())

    def set_precision(self, precision, truncate=0):
        warnings.warn(
            "TimePoint.set_precision is deprecated, use "
            "with_precision(precision,truncate) instead",
            DeprecationWarning,
            stacklevel=2)
        return self.set_from_time_point(self.with_precision(precision,
                                                            truncate))

    def change_zone(self, zchange):
        warnings.warn(
            "TimePoint.change_zone is deprecated, use shift_zone() instead",
            DeprecationWarning,
            stacklevel=2)
        z = self.time.get_zone_offset()
        if z is None:
            raise ValueError(
                "Time zone required for change_zone " + str(self))
        else:
            new_offset = z + zchange
        if new_offset == 0:
            t = self.shift_zone(zdirection=0)
        elif new_offset < 0:
            new_offset = -new_offset
            t = self.shift_zone(
                zdirection=-1, zhour=new_offset // 60, zminute=new_offset % 60)
        else:
            t = self.shift_zone(
                zdirection=1, zhour=new_offset // 60, zminute=new_offset % 60)
        return self.set_from_time_point(t)


class Duration(UnicodeMixin, PEP8Compatibility):

    """A class for representing ISO durations"""

    def __init__(self, value=None):
        PEP8Compatibility.__init__(self)
        if is_text(value):
            self.set_from_string(value)
        elif isinstance(value, Duration):
            self.set_from_duration(value)
        elif value is None:
            self.set_zero()
        else:
            raise TypeError

    def __unicode__(self):
        return to_text(self.get_string())

    def set_zero(self):
        self.years = 0
        self.months = 0
        self.days = 0
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.weeks = None

    def set_calender_duration(self, years, months, days, hours, minutes,
                              seconds):
        self.years = years
        self.months = months
        self.days = days
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.weeks = None

    def get_calender_duration(self):
        if self.weeks is None:
            return (self.years, self.months, self.days, self.hours,
                    self.minutes, self.seconds)
        else:
            raise DateTimeError("duration mode mismatch")

    def set_week_duration(self, weeks):
        self.weeks = weeks
        self.years = self.months = self.days = None
        self.hours = self.minutes = self.seconds = None

    def get_week_duration(self):
        if self.weeks is None:
            raise DateTimeError("duration mode mismatch")
        else:
            return self.weeks

    def set_from_string(self, duration_str):
        if is_text(duration_str):
            p = ISO8601Parser(duration_str)
            return p.parse_duration(self)
        else:
            raise TypeError

    def get_string(self, truncate_zeros=0, ndp=0, dp=','):
        if self.weeks is None:
            components = list(self.get_calender_duration())
            while components[-1] is None:
                # adjust for the precision
                components = components[:-1]
            if truncate_zeros:
                for i in range(len(components) - 1):
                    if components[i] == 0:
                        components[i] = None
                    else:
                        break
            for i in range(len(components)):
                value = components[i]
                if value is None:
                    components[i] = ""
                    continue
                if isinstance(value, float):
                    if ndp is None:
                        f = decimal.Decimal(str(value)).quantize(
                            decimal.Decimal('1.' + '0' * 6),
                            rounding=decimal.ROUND_DOWN)
                        components[i] = str(f).rstrip('.0')
                    else:
                        if ndp < 0:
                            # shorthand for '.'
                            dp = '.'
                            ndp = -ndp
                        f = decimal.Decimal(str(value)).quantize(
                            decimal.Decimal('1.' + '0' * ndp),
                            rounding=decimal.ROUND_DOWN)
                        components[i] = str(f)
                    if dp == ',':
                        components[i] = components[i].replace('.', ',')
                else:
                    components[i] = str(value)
                components[i] = components[i] + "YMDHMS"[i]
            date_part = ''.join(components[0:3])
            time_part = ''.join(components[3:])
            if time_part:
                return 'P' + date_part + 'T' + time_part
            else:
                return 'P' + date_part
        else:
            if isinstance(self.weeks, float):
                f = decimal.Decimal(str(self.weeks)).quantize(
                    decimal.Decimal('1.' + '0' * ndp),
                    rounding=decimal.ROUND_DOWN)
                week_part = str(f) + 'W'
            else:
                week_part = str(self.weeks) + 'W'
            return 'P' + week_part

    def set_from_duration(self, src):
        self.years = src.years
        self.months = src.months
        self.days = src.days
        self.hours = src.hours
        self.minutes = src.minutes
        self.seconds = src.seconds
        self.weeks = src.weeks

    def __eq__(self, other):
        if not isinstance(other, Duration):
            other = Duration(other)
        if self.years == other.years and \
                self.months == other.months and \
                self.days == other.days and \
                self.hours == other.hours and \
                self.minutes == other.minutes and \
                self.seconds == other.seconds and \
                self.weeks == other.weeks:
            return 1
        else:
            return 0


# For compatibility
ISODate = Date
ISOTime = Time
ISOTimePoint = TimePoint

BasicDateFormats = {
    "YYYYMMDD": 1,
    "YYYY-MM": 1,
    "YYYY": 1,
    "YY": 1,
    "YYMMDD": 1,
    "-YYMM": 1,
    "-YY": 1,
    "--MMDD": 1,
    "--MM": 1,
    "---DD": 1,
    "YYYYDDD": 1,
    "YYDDD": 1,
    "-DDD": 1,
    "YYYYWwwD": 1,
    "YYYYWww": 1,
    "YYWwwD": 1,
    "YYWww": 1,
    "-YWwwD": 1,
    "-YWww": 1,
    "-WwwD": 1,
    "-Www": 1,
    "-W-D": 1
}

ExtendedDateFormats = {
    "YYYY-MM-DD": 1,
    "YYYY-MM": 1,
    "YYYY": 1,
    "YY": 1,
    "YY-MM-DD": 1,
    "-YY-MM": 1,
    "-YY": 1,
    "--MM-DD": 1,
    "--MM": 1,
    "---DD": 1,
    "YYYY-DDD": 1,
    "YY-DDD": 1,
    "-DDD": 1,
    "YYYY-Www-D": 1,
    "YYYY-Www": 1,
    "YY-Www-D": 1,
    "YY-Www": 1,
    "-Y-Www-D": 1,
    "-Y-Www": 1,
    "-Www-D": 1,
    "-Www": 1,
    "-W-D": 1
}

BasicTimeFormats = {
    "hhmmss": 1,
    "hhmm": 1,
    "hh": 1,
    "hhmmss,s": 1,
    "hhmmss.s": 1,
    "hhmm,m": 1,
    "hhmm.m": 1,
    "hh,h": 1,
    "hh.h": 1,
    "hhmmssZ": 1,
    "hhmmZ": 1,
    "hhZ": 1,
    "hhmmss,sZ": 1,
    "hhmmss.sZ": 1,
    "hhmm,mZ": 1,
    "hhmm.mZ": 1,
    "hh,hZ": 1,
    "hh.hZ": 1,
    "hhmmss+hhmm": 1,
    "hhmm+hhmm": 1,
    "hh+hhmm": 1,
    "hhmmss,s+hhmm": 1,
    "hhmmss.s+hhmm": 1,
    "hhmm,m+hhmm": 1,
    "hhmm.m+hhmm": 1,
    "hh,h+hhmm": 1,
    "hh.h+hhmm": 1,
    "hhmmss+hh": 1,
    "hhmm+hh": 1,
    "hh+hh": 1,
    "hhmmss,s+hh": 1,
    "hhmmss.s+hh": 1,
    "hhmm,m+hh": 1,
    "hhmm.m+hh": 1,
    "hh,h+hh": 1,
    "hh.h+hh": 1,
    "-mmss": 1,
    "-mm": 1,
    "--ss": 1,
    "-mmss,s": 1,
    "-mm,m": 1,
    "-mm.m": 1,
    "--ss,s": 1,
    "--ss.s": 1
}

ExtendedTimeFormats = {
    "hh:mm:ss": 1,
    "hh:mm": 1,
    "hh": 1,
    "hh:mm:ss,s": 1,
    "hh:mm:ss.s": 1,
    "hh:mm,m": 1,
    "hh:mm.m": 1,
    "hh,h": 1,
    "hh.h": 1,
    "hh:mm:ssZ": 1,
    "hh:mmZ": 1,
    "hhZ": 1,
    "hh:mm:ss,sZ": 1,
    "hh:mm:ss.sZ": 1,
    "hh:mm,mZ": 1,
    "hh:mm.mZ": 1,
    "hh,hZ": 1,
    "hh.hZ": 1,
    "hh:mm:ss+hh:mm": 1,
    "hh:mm+hh:mm": 1,
    "hh+hh:mm": 1,
    "hh:mm:ss,s+hh:mm": 1,
    "hh:mm:ss.s+hh:mm": 1,
    "hh:mm,m+hh:mm": 1,
    "hh:mm.m+hh:mm": 1,
    "hh,h+hh:mm": 1,
    "hh.h+hh:mm": 1,
    "hh:mm:ss+hh": 1,
    "hh:mm+hh": 1,
    "hh+hh": 1,
    "hh:mm:ss,s+hh": 1,
    "hh:mm:ss.s+hh": 1,
    "hh:mm,m+hh": 1,
    "hh:mm.m+hh": 1,
    "hh,h+hh": 1,
    "hh.h+hh": 1,
    "-mm:ss": 1,
    "-mm": 1,
    "--ss": 1,
    "-mm:ss,s": 1,
    "-mm:ss.s": 1,
    "-mm,m": 1,
    "-mm.m": 1,
    "--ss,s": 1,
    "--ss.s": 1
}


class ISO8601Parser(BasicParser):

    def __init__(self, src):
        if is_text(src):
            super(ISO8601Parser, self).__init__(src)
        else:
            raise DateTimeError(
                "iso8601 requires character source, not binary data")

    def require_xtime_point_format(self, xdigits, tdesignators="T"):
        d, df = self.require_xdate_format(xdigits)
        return self.require_time_point_time_format(d, df, tdesignators)

    def parse_time_point_format(self, base=None, tdesignators="T"):
        d, df = self.parse_date_format(None if base is None else base.date)
        return self.require_time_point_time_format(d, df, tdesignators)

    def require_time_point_time_format(self, d, df, tdesignators):
        if not d.complete():
            raise DateTimeError("incomplete date in time point %s" % str(d))
        if self.the_char not in tdesignators:
            raise DateTimeError("time-point requires time %s..." % str(d))
        tdesignator = self.the_char
        t, overflow, tf = self.parse_time_format(None, tdesignators)
        if overflow:
            d = d.offset(days=overflow)
        # check that the date format and time format are compatible,
        # i.e., both either basic or extended
        if d.xdigits is not None:
            if d.xdigits < 0:
                # only works with extended format
                dext = True
                dbasic = False
            else:
                dext = ExtendedDateFormats.get(df[d.xdigits + 1:]) is not None
                dbasic = BasicDateFormats.get(df[d.xdigits + 1:]) is not None
        else:
            dext = ExtendedDateFormats.get(df)
            dbasic = BasicDateFormats.get(df)
        if not ((ExtendedTimeFormats.get(tf) and dext) or
                (BasicTimeFormats.get(tf) and dbasic)):
            raise DateTimeError(
                "inconsistent use of basic/extended form in time point "
                "%s%s%s" % (df, tdesignator, tf))
        return TimePoint(date=d, time=t), df + tdesignator + tf

    def parse_time_point(self, time_point, base=None, tdesignators="T"):
        raise DateTimeError(
            "ISO8601Parser.parse_time_point no longer supported\n"
            "Replace: tformat = p.parse_time_point(d, base, 'T') with:\n"
            "         d, tformat = p.parse_time_point_format(base, 'T')")

    def require_xdate_format(self, xdigits):
        """Returns a tuple of (:py:class:`ExpandedDate`, string)

        The second item in the tuple is a string representing the format
        parsed which will be one of the expanded forms.

        The number of expanded year digits must be specified and be
        present exactly."""
        sign = self.parse_one('+-')
        if sign:
            bce = sign == '-'
        elif xdigits < 0:
            bce = False
            sign = ''
        else:
            self.parser_error("expanded date format")
        century = 0
        if xdigits < 0:
            # in this mode we parse the entire year, must be in extended
            # format as we won't stop until we run out digits.
            ndigits = 0
            while self.match_digit():
                century = 10 * century + self.require_digit_value()
                ndigits += 1
            if ndigits < 4:
                self.parser_error(
                    "variable length expanded year with 4 or more digits")
            year = century % 100
            century = century // 100
        else:
            for i in range3(xdigits + 2):
                century = 10 * century + self.require_digit_value()
            year = None
        xformat = sign + 'Y' * xdigits
        if self.match_digit() or year is not None:
            if year is None:
                year = self.require_digit_value()
                year = year * 10 + self.require_digit_value()
            if self.match_digit():
                v1 = self.require_digit_value()
                v1 = v1 * 10 + self.require_digit_value()
                v2 = self.require_digit_value()
                if self.match_digit():
                    v2 = v2 * 10 + self.require_digit_value()
                    return (Date(bce=bce, century=century, year=year, month=v1,
                                 day=v2, xdigits=xdigits),
                            xformat + "YYYYMMDD")
                else:
                    return (Date(bce=bce, century=century, year=year,
                                 ordinal_day=v1 * 10 + v2, xdigits=xdigits),
                            xformat + "YYYYDDD")
            elif self.the_char == "-":
                self.next_char()
                if self.match_digit():
                    v1 = self.require_digit_value()
                    v1 = v1 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v1 = v1 * 10 + self.require_digit_value()
                        return (Date(bce=bce, century=century, year=year,
                                     ordinal_day=v1, xdigits=xdigits),
                                xformat + "YYYY-DDD")
                    elif self.the_char == "-":
                        self.next_char()
                        v2 = self.require_digit_value()
                        v2 = v2 * 10 + self.require_digit_value()
                        return (Date(bce=bce, century=century, year=year,
                                     month=v1, day=v2, xdigits=xdigits),
                                xformat + "YYYY-MM-DD")
                    else:
                        return (Date(bce=bce, century=century, year=year,
                                     month=v1, xdigits=xdigits),
                                xformat + "YYYY-MM")
                elif self.the_char == "W":
                    self.next_char()
                    week = self.require_digit_value()
                    week = week * 10 + self.require_digit_value()
                    if self.the_char == "-":
                        self.next_char()
                        weekday = self.require_digit_value()
                        return (Date(bce=bce, century=century,
                                     decade=year // 10, year=year % 10,
                                     week=week, weekday=weekday,
                                     xdigits=xdigits), xformat + "YYYY-Www-D")
                    else:
                        return (Date(bce=bce, century=century,
                                     decade=year // 10, year=year % 10,
                                     week=week, xdigits=xdigits),
                                xformat + "YYYY-Www")
                else:
                    self.parser_error("digit or W in ISO expanded date")
            elif self.the_char == "W":
                self.next_char()
                week = self.require_digit_value()
                week = week * 10 + self.require_digit_value()
                if self.match_digit():
                    weekday = self.require_digit_value()
                    return (Date(bce=bce, century=century, decade=year // 10,
                                 year=year % 10, week=week, weekday=weekday,
                                 xdigits=xdigits), xformat + "YYYYWwwD")
                else:
                    return (Date(bce=bce, century=century, decade=year // 10,
                                 year=v2 % 10, week=week, xdigits=xdigits),
                            xformat + "YYYYWww")
            else:
                return (Date(bce=bce, century=century, year=year,
                        xdigits=xdigits), xformat + "YYYY")
        else:
            return (Date(bce=bce, century=century, xdigits=xdigits),
                    xformat + "YY")

    def parse_date_format(self, base=None):
        """Returns a tuple of (:py:class:`Date`, string).

        The second item in the tuple is a string representing the format
        parsed."""
        if self.match_digit():
            v1 = self.require_digit_value()
            v1 = v1 * 10 + self.require_digit_value()
            if self.match_digit():
                v2 = self.require_digit_value()
                v2 = v2 * 10 + self.require_digit_value()
                if self.match_digit():
                    v3 = self.require_digit_value()
                    if self.match_digit():
                        v3 = v3 * 10 + self.require_digit_value()
                        if self.match_digit():
                            v4 = self.require_digit_value()
                            if self.match_digit():
                                v4 = v4 * 10 + self.require_digit_value()
                                return (Date(century=v1, year=v2, month=v3,
                                             day=v4, base=base), "YYYYMMDD")
                            else:
                                return (Date(century=v1, year=v2,
                                             ordinal_day=v3 * 10 + v4,
                                             base=base), "YYYYDDD")
                        else:
                            return (Date(year=v1, month=v2, day=v3, base=base),
                                    "YYMMDD")
                    else:
                        return (Date(year=v1, ordinal_day=v2 * 10 + v3,
                                     base=base), "YYDDD")
                elif self.the_char == "-":
                    self.next_char()
                    if self.match_digit():
                        v3 = self.require_digit_value()
                        v3 = v3 * 10 + self.require_digit_value()
                        if self.match_digit():
                            v3 = v3 * 10 + self.require_digit_value()
                            return (Date(century=v1, year=v2, ordinal_day=v3,
                                         base=base), "YYYY-DDD")
                        elif self.the_char == "-":
                            self.next_char()
                            v4 = self.require_digit_value()
                            v4 = v4 * 10 + self.require_digit_value()
                            return (Date(century=v1, year=v2, month=v3,
                                         day=v4, base=base), "YYYY-MM-DD")
                        else:
                            return (Date(century=v1, year=v2, month=v3,
                                         base=base), "YYYY-MM")
                    elif self.the_char == "W":
                        self.next_char()
                        v3 = self.require_digit_value()
                        v3 = v3 * 10 + self.require_digit_value()
                        if self.the_char == "-":
                            self.next_char()
                            v4 = self.require_digit_value()
                            return (Date(century=v1, decade=v2 // 10,
                                         year=v2 % 10, week=v3, weekday=v4,
                                         base=base), "YYYY-Www-D")
                        else:
                            return Date(
                                century=v1, decade=v2 // 10, year=v2 %
                                10, week=v3, base=base), "YYYY-Www"
                    else:
                        self.parser_error("digit or W in ISO date")
                elif self.the_char == "W":
                    self.next_char()
                    v3 = self.require_digit_value()
                    v3 = v3 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v4 = self.require_digit_value()
                        return Date(
                            century=v1, decade=v2 // 10, year=v2 %
                            10, week=v3, weekday=v4, base=base), "YYYYWwwD"
                    else:
                        return (Date(century=v1, decade=v2 // 10, year=v2 % 10,
                                     week=v3, base=base), "YYYYWww")
                else:
                    return Date(century=v1, year=v2, base=base), "YYYY"
            elif self.the_char == "-":
                self.next_char()
                if self.match_digit():
                    """YY-DDD, YY-MM-DD"""
                    v2 = self.require_digit_value()
                    v2 = v2 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v2 = v2 * 10 + self.require_digit_value()
                        return Date(
                            year=v1, ordinal_day=v2, base=base), "YY-DDD"
                    elif self.the_char == "-":
                        self.next_char()
                        v3 = self.require_digit_value()
                        v3 = v3 * 10 + self.require_digit_value()
                        return Date(
                            year=v1, month=v2, day=v3, base=base), "YY-MM-DD"
                    else:
                        self.parser_error("digit or hyphen in ISO date")
                elif self.the_char == "W":
                    self.next_char()
                    v2 = self.require_digit_value()
                    v2 = v2 * 10 + self.require_digit_value()
                    if self.the_char == "-":
                        self.next_char()
                        v3 = self.require_digit_value()
                        return Date(
                            decade=v1 // 10, year=v1 %
                            10, week=v2, weekday=v3, base=base), "YY-Www-D"
                    else:
                        return Date(
                            decade=v1 // 10, year=v1 %
                            10, week=v2, base=base), "YY-Www"
                else:
                    self.parser_error("digit or W in ISO date")
            elif self.the_char == "W":
                self.next_char()
                v2 = self.require_digit_value()
                v2 = v2 * 10 + self.require_digit_value()
                if self.match_digit():
                    v3 = self.require_digit_value()
                    return Date(
                        decade=v1 // 10, year=v1 %
                        10, week=v2, weekday=v3, base=base), "YYWwwD"
                else:
                    return Date(
                        decade=v1 // 10, year=v1 %
                        10, week=v2, base=base), "YYWww"
            else:
                return Date(century=v1, base=base), "YY"
        elif self.the_char == "-":
            self.next_char()
            if self.match_digit():
                v1 = self.require_digit_value()
                if self.match_digit():
                    v1 = v1 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v2 = self.require_digit_value()
                        if self.match_digit():
                            v2 = v2 * 10 + self.require_digit_value()
                            return Date(year=v1, month=v2, base=base), "-YYMM"
                        else:
                            return Date(
                                ordinal_day=v1 * 10 + v2, base=base), "-DDD"
                    elif self.the_char == "-":
                        self.next_char()
                        v2 = self.require_digit_value()
                        v2 = v2 * 10 + self.require_digit_value()
                        return Date(year=v1, month=v2, base=base), "-YY-MM"
                    else:
                        return Date(year=v1, base=base), "-YY"
                elif self.the_char == "-":
                    self.next_char()
                    self.require("W")
                    v2 = self.require_digit_value()
                    v2 = v2 * 10 + self.require_digit_value()
                    if self.the_char == "-":
                        self.next_char()
                        v3 = self.require_digit_value()
                        return (Date(year=v1, week=v2, weekday=v3, base=base),
                                "-Y-Www-D")
                    else:
                        return Date(year=v1, week=v2, base=base), "-Y-Www"
                elif self.the_char == "W":
                    self.next_char()
                    v2 = self.require_digit_value()
                    v2 = v2 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v3 = self.require_digit_value()
                        return Date(
                            year=v1, week=v2, weekday=v3, base=base), "-YWwwD"
                    else:
                        return Date(year=v1, week=v2, base=base), "-YWww"
            elif self.the_char == "-":
                self.next_char()
                if self.match_digit():
                    v1 = self.require_digit_value()
                    v1 = v1 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v2 = self.require_digit_value()
                        v2 = v2 * 10 + self.require_digit_value()
                        return Date(month=v1, day=v2, base=base), "--MMDD"
                    elif self.the_char == "-":
                        self.next_char()
                        v2 = self.require_digit_value()
                        v2 = v2 * 10 + self.require_digit_value()
                        return Date(month=v1, day=v2, base=base), "--MM-DD"
                    else:
                        return Date(month=v1, base=base), "--MM"
                elif self.the_char == "-":
                    self.next_char()
                    v1 = self.require_digit_value()
                    v1 = v1 * 10 + self.require_digit_value()
                    return Date(day=v1, base=base), "---DD"
                else:
                    self.parser_error("digit or hyphen in truncated ISO date")
            elif self.the_char == "W":
                self.next_char()
                if self.match_digit():
                    v1 = self.require_digit_value()
                    v1 = v1 * 10 + self.require_digit_value()
                    if self.match_digit():
                        v2 = self.require_digit_value()
                        return Date(week=v1, weekday=v2, base=base), "-WwwD"
                    elif self.the_char == "-":
                        self.next_char()
                        v2 = self.require_digit_value()
                        return Date(week=v1, weekday=v2, base=base), "-Www-D"
                    else:
                        return Date(week=v1, base=base), "-Www"
                elif self.the_char == "-":
                    self.next_char()
                    v1 = self.require_digit_value()
                    return Date(weekday=v1, base=base), "-W-D"
                else:
                    self.parser_error("digit or hyphen in truncated ISO date")
            else:
                self.parser_error("digit, hyphen or W in truncated ISO date")
        else:
            self.parser_error("digit or hyphen in ISO date")

    def parse_date(self, date, base=None):
        raise DateTimeError(
            "ISO8601Parser.parse_date no longer supported\n"
            "Replace: dformat = p.parse_date(d, base) with:\n"
            "         d, tformat = p.parse_date_format(base)")

    def parse_time_format(self, base=None, tdesignators="T"):
        if self.the_char in tdesignators:
            self.next_char()
            tdesignator = 1
        else:
            tdesignator = 0
        if self.match_digit():
            v1 = self.require_digit_value()
            v1 = v1 * 10 + self.require_digit_value()
            if self.match_digit():
                v2 = self.require_digit_value()
                v2 = v2 * 10 + self.require_digit_value()
                if self.match_digit():
                    v3 = self.require_digit_value()
                    v3 = v3 * 10 + self.require_digit_value()
                    if self.the_char == "." or self.the_char == ",":
                        point = self.the_char
                        v3 = float(v3) + self.parse_fraction()
                        hour, minute, second = v1, v2, v3
                        tformat = "hhmmss%ss" % point
                    else:
                        hour, minute, second = v1, v2, v3
                        tformat = "hhmmss"
                elif self.the_char == "." or self.the_char == ",":
                    point = self.the_char
                    v2 = float(v2) + self.parse_fraction()
                    hour, minute, second = v1, v2, None
                    tformat = "hhmm%sm" % point
                else:
                    hour, minute, second = v1, v2, None
                    tformat = "hhmm"
            elif self.the_char == "." or self.the_char == ",":
                point = self.the_char
                v1 = float(v1) + self.parse_fraction()
                hour, minute, second = v1, None, None
                tformat = "hh%sh" % point
            elif self.the_char == ":":
                self.next_char()
                v2 = self.require_digit_value()
                v2 = v2 * 10 + self.require_digit_value()
                if self.the_char == ":":
                    self.next_char()
                    v3 = self.require_digit_value()
                    v3 = v3 * 10 + self.require_digit_value()
                    if self.the_char == "." or self.the_char == ",":
                        point = self.the_char
                        v3 = float(v3) + self.parse_fraction()
                        hour, minute, second = v1, v2, v3
                        tformat = "hh:mm:ss%ss" % point
                    else:
                        hour, minute, second = v1, v2, v3
                        tformat = "hh:mm:ss"
                elif self.the_char == "," or self.the_char == ".":
                    point = self.the_char
                    v2 = float(v2) + self.parse_fraction()
                    hour, minute, second = v1, v2, None
                    tformat = "hh:mm%sm" % point
                else:
                    hour, minute, second = v1, v2, None
                    tformat = "hh:mm"
            else:
                hour, minute, second = v1, None, None
                tformat = "hh"
        elif self.the_char == "-":
            if tdesignator:
                self.parser_error("time designator T before truncated time")
            self.next_char()
            if self.match_digit():
                v1 = self.require_digit_value()
                v1 = v1 * 10 + self.require_digit_value()
                if self.match_digit():
                    v2 = self.require_digit_value()
                    v2 = v2 * 10 + self.require_digit_value()
                    if self.the_char == "." or self.the_char == ",":
                        point = self.the_char
                        v2 = float(v2) + self.parse_fraction()
                        hour, minute, second = None, v1, v2
                        tformat = "-mmss%ss" % point
                    else:
                        hour, minute, second = None, v1, v2
                        tformat = "-mmss"
                elif self.the_char == "." or self.the_char == ",":
                    point = self.the_char
                    v1 = float(v1) + self.parse_fraction()
                    hour, minute, second = None, v1, None
                    tformat = "-mm%sm" % point
                elif self.the_char == ":":
                    self.next_char()
                    v2 = self.require_digit_value()
                    v2 = v2 * 10 + self.require_digit_value()
                    if self.the_char == "." or self.the_char == ",":
                        point = self.the_char
                        v2 = float(v2) + self.parse_fraction()
                        hour, minute, second = None, v1, v2
                        tformat = "-mm:ss%ss" % point
                    else:
                        hour, minute, second = None, v1, v2
                        tformat = "-mm:ss"
                else:
                    hour, minute, second = None, v1, None
                    tformat = "-mm"
            elif self.the_char == "-":
                self.next_char()
                v1 = self.require_digit_value()
                v1 = v1 * 10 + self.require_digit_value()
                if self.the_char == "." or self.the_char == ",":
                    point = self.the_char
                    v1 = float(v1) + self.parse_fraction()
                    hour, minute, second = None, None, v1
                    tformat = "--ss%ss" % point
                else:
                    hour, minute, second = None, None, v1
                    tformat = "--ss"
            else:
                self.parser_error("digit or hyphen in truncated Time")
            # truncated forms cannot take timezones, return early
            t, overflow = base.extend(hour=hour, minute=minute, second=second)
            return t, overflow, tformat
        else:
            self.parser_error("digit or hyphen in Time")
        if self.the_char is not None and self.the_char in "Z+-":
            # can't be truncated form
            zdirection, zhour, zminute, tzFormat = \
                self.parse_time_zone_format()
            tformat += tzFormat
            if not (BasicTimeFormats.get(tformat) or
                    ExtendedTimeFormats.get(tformat)):
                raise DateTimeError(
                    "inconsistent use of extended/basic format in time zone")
            return (Time(hour=hour, minute=minute, second=second,
                         zdirection=zdirection, zhour=zhour, zminute=zminute),
                    0, tformat)
        elif base is not None:
            t, overflow = base.extend(hour=hour, minute=minute, second=second)
            return t, overflow, tformat
        else:
            return Time(hour=hour, minute=minute, second=second), 0, tformat

    def parse_time_zone_format(self):
        if self.the_char == "Z":
            self.next_char()
            zdirection, zhour, zminute = 0, 0, 0
            format = 'Z'
        elif self.the_char == "+" or self.the_char == "-":
            if self.the_char == "+":
                v1 = +1
            else:
                v1 = -1
            self.next_char()
            v2 = self.require_digit_value()
            v2 = v2 * 10 + self.require_digit_value()
            if self.match_digit():
                v3 = self.require_digit_value()
                v3 = v3 * 10 + self.require_digit_value()
                zdirection, zhour, zminute = v1, v2, v3
                format = "+hhmm"
            elif self.the_char == ":":
                self.next_char()
                v3 = self.require_digit_value()
                v3 = v3 * 10 + self.require_digit_value()
                zdirection, zhour, zminute = v1, v2, v3
                format = "+hh:mm"
            else:
                zdirection, zhour, zminute = v1, v2, None
                format = "+hh"
        return zdirection, zhour, zminute, format

    def parse_time(self, t, tbase=None, tdesignators="T"):
        raise DateTimeError(
            "ISO8601Parser.parse_time no longer supported\n"
            "Replace: tformat = p.parse_time(t, base, 'T') with:\n"
            "         t, tformat = p.parse_time_format(base, 'T')")

    def parse_time_zone(self, t):
        raise DateTimeError(
            "ISO8601Parser.parse_time_zone no longer supported\n"
            "Replace: zformat = p.parse_time_zone(t) with:\n"
            "         zd, zh, zm, zformat = p.parse_time_zone_format()\n"
            "         t = t.with_zone(zd, zh, zm)")

    def parse_duration_value(self, allow_fraction=True):
        """Returns a tuple of (value, formatString) or (None,None).

        formatString is one of "n", "n.n" or "n,n".

        If allow_fraction is False then a fractional format raises an error."""
        value = self.parse_integer()
        if value is None:
            return None, None
        if self.the_char in ".,":
            if not allow_fraction:
                raise DateTimeError(
                    "fractional component in duration must have lowest order")
            format = "n" + self.the_char + "n"
            value = value + self.parse_fraction()
        else:
            format = "n"
        return value, format

    def parse_duration(self, d):
        if self.the_char != 'P':
            raise DateTimeError("expected duration")
        format = ['P']
        values = []
        self.next_char()
        allow_fraction = True
        value, vformat = self.parse_duration_value(allow_fraction)
        allow_fraction = allow_fraction and (value is None or vformat == "n")
        if value is not None and self.the_char == "W":
            format.append(vformat + "W")
            self.next_char()
            d.set_week_duration(value)
            return ''.join(format)
        if value is not None and self.the_char == 'Y':
            format.append(vformat + "Y")
            self.next_char()
            values.append(value)
            value, vformat = self.parse_duration_value(allow_fraction)
            allow_fraction = allow_fraction and (value is None or
                                                 vformat == "n")
        else:
            values.append(None)
        if value is not None and self.the_char == 'M':
            format.append(vformat + "M")
            self.next_char()
            values.append(value)
            value, vformat = self.parse_duration_value(allow_fraction)
            allow_fraction = allow_fraction and (value is None or
                                                 vformat == "n")
        else:
            values.append(None)
        if value is not None and self.the_char == 'D':
            format.append(vformat + "D")
            self.next_char()
            values.append(value)
            value, vformat = None, None
        else:
            values.append(None)
        if value is not None:
            raise DateTimeError("expected 'T', found %s" % str(value))
        if self.the_char == 'T':
            format.append("T")
            self.next_char()
            value, vformat = self.parse_duration_value(allow_fraction)
            allow_fraction = allow_fraction and (value is None or
                                                 vformat == "n")
            if value is not None and self.the_char == 'H':
                format.append(vformat + "H")
                self.next_char()
                values.append(value)
                value, vformat = self.parse_duration_value(allow_fraction)
                allow_fraction = allow_fraction and (
                    value is None or vformat == "n")
            else:
                values.append(None)
            if value is not None and self.the_char == 'M':
                format.append(vformat + "M")
                self.next_char()
                values.append(value)
                value, vformat = self.parse_duration_value(allow_fraction)
                allow_fraction = allow_fraction and (
                    value is None or vformat == "n")
            else:
                values.append(None)
            if value is not None and self.the_char == 'S':
                format.append(vformat + "S")
                self.next_char()
                values.append(value)
                value, vformat = None, None
            else:
                values.append(None)
        else:
            values = values + [None, None, None]
        if value is not None:
            raise DateTimeError(
                "expected end of duration, found %s" % str(value))
        if len(format) == 1:
            # "P" not allowed
            raise DateTimeError("duration must have at least one component")
        elif format[-1] == "T":
            # "P...T" not allowed either
            raise DateTimeError("expected time component in duration")
        # Now deal with partial precision, higher order components
        # default to 0
        def_value = None
        for i in range3(5, -1, -1):
            # loop backwards through the values
            if values[i] is None:
                values[i] = def_value
            else:
                def_value = 0
        format = ''.join(format)
        years, months, days, hours, minutes, seconds = values
        d.set_calender_duration(years, months, days, hours, minutes, seconds)
        return format

    def parse_fraction(self):
        if not (self.the_char == "." or self.the_char == ","):
            self.parser_error("decimal sign")
        self.next_char()
        f = 0
        fmag = 1
        while self.match_digit():
            f = f * 10 + self.require_digit_value()
            fmag *= 10
        if fmag == 1:
            self.parser_error("decimal digit")
        return float(f) / float(fmag)

    def require_digit_value(self):
        return self.require_production(self.parse_digit_value(),
                                       "expected DIGIT")


EPOCH = TimePoint.from_struct_time(pytime.gmtime(0)).with_zone(zdirection=0)
