#! /usr/bin/env python

import decimal
import logging
import unittest
import uuid

from pyslet.odata4 import parser
from pyslet.odata4 import types


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ParserTests, 'test'),
        ))


class ParserTests(unittest.TestCase):

    # literals enclosed in single quotes are treated case-sensitive

    def test_expand(self):
        # work through examples from the specification
        p = parser.Parser("Category")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        cat = expand[0]
        self.assertTrue(isinstance(cat, types.ExpandItem))
        self.assertTrue(isinstance(cat.path, tuple))
        self.assertTrue(len(cat.path) == 1)
        self.assertTrue(cat.path == ("Category", ))
        self.assertTrue(cat.qualifier is None)
        self.assertTrue(cat.options.select is None)
        self.assertTrue(cat.options.expand is None)
        self.assertTrue(cat.options.skip is None)
        self.assertTrue(cat.options.top is None)
        self.assertTrue(cat.options.count is None)
        self.assertTrue(cat.options.filter is None)
        self.assertTrue(cat.options.search is None)
        self.assertTrue(cat.options.orderby is None)
        self.assertTrue(cat.options.levels is None)

    def from_str(self, meth, good, bad):
        for s in good:
            logging.debug("%s(%s)", meth.__name__, repr(s))
            p = parser.Parser(s)
            try:
                meth(p)
                p.require_end()
            except ValueError as e:
                logging.error(str(e))
                self.fail("%s(%s) failed" % (meth.__name__, repr(s)))
        for s in bad:
            p = parser.Parser(s)
            try:
                meth(p)
                p.require_end()
                self.fail("%s(%s) succeeded" % (meth.__name__, repr(s)))
            except ValueError:
                pass

    def test_boolean_value(self):
        """booleanValue = "true" / "false" """
        v = parser.Parser("true").require_boolean_value()
        self.assertTrue(v is True)
        v = parser.Parser("false").require_boolean_value()
        self.assertTrue(v is False)
        good = ("True", "TRUE", "False", "FALSE")
        bad = ('1', '0', 'yes', 'no', ' true', 'true ', "'true'", "null", "")
        self.from_str(parser.Parser.require_boolean_value, good, bad)

    def test_guid_value(self):
        """guidValue =  8HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-"
                        12HEXDIG"""
        v = parser.Parser(
            "00000000-0000-0000-0000-00000000002A").require_guid_value()
        self.assertTrue(v == uuid.UUID(int=42))
        good = (
            "00000000-0000-0000-0000-00000000002a",
            "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
            "01234567-89AB-CDEF-0123-456789abcdef",
            )
        bad = (
            "0000000000000000000000000000002A",
            "000H3110-0000-0000-0000-00000000002A",
            "0000000-00000-0000-0000-00000000002A",
            "000000-000000-0000-0000-00000000002A",
            " 00000000-0000-0000-0000-00000000002A",
            "00000000-0000-0000-0000-00000000002A ",
            "00000000-0000-0000-0000-00000000002AB",
            "null", "")
        self.from_str(parser.Parser.require_guid_value, good, bad)

    def test_duration_value(self):
        """durationValue = [ sign ] "P" [ 1*DIGIT "D" ]
                [ "T" [ 1*DIGIT "H" ] [ 1*DIGIT "M" ]
                 [ 1*DIGIT [ "." 1*DIGIT ] "S" ] ]"""
        p = parser.Parser("-P3DT1H4M1.5S")
        try:
            v = p.require_duration_value()
            p.require_end()
        except ValueError as err:
            self.fail(str(err))
        self.assertTrue(v.sign == -1)
        self.assertTrue(v.years == 0)
        self.assertTrue(v.months == 0)
        self.assertTrue(v.weeks is None)
        self.assertTrue(v.days == 3)
        self.assertTrue(v.hours == 1)
        self.assertTrue(v.minutes == 4)
        self.assertTrue(v.seconds == 1.5)
        good = (
            "P", "+P", "PT1S", "PT1.1S", "P1D",
            )
        bad = (
            "", "P1H", "1H", "P1D1H", "P1DT1M1H", "1S",
            )
        self.from_str(parser.Parser.require_duration_value, good, bad)

    def test_date_value(self):
        """dateValue = year "-" month "-" day

        year  = [ "-" ] ( "0" 3DIGIT / oneToNine 3*DIGIT )
        month = "0" oneToNine
              / "1" ( "0" / "1" / "2" )
        day   = "0" oneToNine
              / ( "1" / "2" ) DIGIT
              / "3" ( "0" / "1" )"""
        v = parser.Parser("0000-01-01").require_date_value()
        self.assertTrue(v.get_xcalendar_day() == (False, 0, 0, 1, 1))
        v = parser.Parser("-0999-01-01").require_date_value()
        self.assertTrue(v.get_xcalendar_day() == (True, 9, 99, 1, 1))
        good = (
            "-0000-01-01",
            "0999-01-01",
            "11234-01-01",
            )
        bad = (
            "01234-01-01",
            "-01234-01-01",
            "100-01-01",
            "-100-01-01",
            "9999-13-01",
            "9999-12-32",
            "1234-7-04",
            "1234-07-4",
            "1234-007-04",
            "1234-07-004",
            "2017-02-29",
            "2017-03-40",
            "null", "")
        self.from_str(parser.Parser.require_date_value, good, bad)

    def test_date_time_offset_value(self):
        """dateTimeOffsetValue =
            year "-" month "-" day "T" hour ":" minute
            [ ":" second [ "." fractionalSeconds ] ]
            ( "Z" / sign hour ":" minute )

        hour   = ( "0" / "1" ) DIGIT / "2" ( "0" / "1" / "2" / "3" )
        minute = zeroToFiftyNine
        second = zeroToFiftyNine
        fractionalSeconds = 1*12DIGIT"""
        v = parser.Parser(
            "0000-01-01T00:00:00Z").require_date_time_offset_value()
        self.assertTrue(v.get_xcalendar_time_point() ==
                        (False, 0, 0, 1, 1, 0, 0, 0))
        self.assertTrue(v.get_zone() == (0, 0))
        v = parser.Parser(
            "-0752-04-21T16:00:00+01:00").require_date_time_offset_value()
        self.assertTrue(v.get_xcalendar_time_point() ==
                        (True, 7, 52, 4, 21, 16, 0, 0))
        self.assertTrue(v.get_zone() == (1, 60))
        good = (
            "99999999-12-31T23:59:59.999999999999+23:59",
            "0000-01-01T00:00:00.000000000000+00:00",
            "1969-07-20T20:17Z",
            "1969-07-20T20:17+00:00",
            "1969-07-20T20:17:40.0Z",
            "1969-07-20T20:17:40.0Z",
            "1969-07-20T20:12:40.0-05:00",
            )
        bad = (
            "1969-07-20T-01:17Z",
            "1969-07-20T-1:17Z",
            "1969-07-20T60:17Z",
            "1969-07-20T20:-01Z",
            "1969-07-20T20:-1Z",
            "1969-07-20T20:60Z",
            "1969-07-20T20:17:+1Z",
            "1969-07-20T20:17:-1Z",
            "1969-07-20T20:17:-01Z",
            "1969-07-20T20:17:60Z",
            "1969-07-20T20:17:40.0000000000000Z",   # 13 fractional digits
            "1969-07-20T20:17:59.9999999999999Z",   # 13 fractional digits
            "1969-07-20T20:12:40.0+24:00",
            "1969-07-20T20:12:40.0-24:00",
            "1969-07-20T20:12:40.0-05:-1",
            "1969-07-20T20:12:40.0-05:-01",
            "1969-07-20T20:12:40.0-05:+1",
            "1969-07-20T20:12:40.0-05:60",
            "1969-07-20T20:17:40.Z",
            "null", ""
            )
        self.from_str(parser.Parser.require_date_time_offset_value, good, bad)

    def test_time_of_day_value(self):
        """timeOfDayValue = hour ":" minute
                            [ ":" second [ "." fractionalSeconds ] ]"""
        v = parser.Parser("00:00:00").require_time_of_day_value()
        self.assertTrue(v.get_time() == (0, 0, 0))
        self.assertTrue(v.get_zone() == (None, None))
        v = parser.Parser("00:00").require_time_of_day_value()
        self.assertTrue(v.get_time() == (0, 0, 0))
        self.assertTrue(v.get_zone() == (None, None))
        good = (
            "23:59:59.999999999999",
            "00:00:00.000000000000",
            "20:17",
            "20:17",
            "20:17:40.0",
            )
        bad = (
            "-01:17",
            "-1:17",
            "60:17",
            "20:-01",
            "20:-1",
            "20:60",
            "20:17:+1",
            "20:17:-1",
            "20:17:-01",
            "20:17:60",
            "20:17:40.0000000000000",   # 13 fractional digits
            "20:17:59.9999999999999",   # 13 fractional digits
            "20:12:40.0Z"
            "20:12:40.0+00:00"
            "20:17:40.",
            "null", ""
            )
        self.from_str(parser.Parser.require_time_of_day_value, good, bad)

    def test_enum_value(self):
        """enumValue = singleEnumValue *( COMMA singleEnumValue )
        singleEnumValue = enumerationMember / enumMemberValue
        enumMemberValue = int64Value
        enumerationMember   = odataIdentifier"""
        good = (
            ("Rock,Paper,Scissors", ["Rock", "Paper", "Scissors"]),
            ("Rock", ["Rock"]),
            ("1", [1]),
            ("-1", [-1]),   # negatives are OK
            )
        bad = (
            "1.0",      # floats are not
            "Rock+Paper",
            )
        for src, value in good:
            p = parser.Parser(src)
            try:
                v = p.require_enum_value()
            except ValueError as err:
                self.fail("%s raised %s" % (src, str(err)))
            self.assertTrue(v == value, "failed to parse %s" % src)
            p.require_end()
        for src in bad:
            p = parser.Parser(src)
            try:
                v = p.require_enum_value()
                p.require_end()
                self.fail("%s validated for enumValue" % repr(src))
            except ValueError:
                pass

    def test_decimal_value(self):
        """decimalValue = [SIGN] 1*DIGIT ["." 1*DIGIT]"""
        v = parser.Parser("3.14").require_decimal_value()
        self.assertTrue(v == decimal.Decimal('3.14'))
        v = parser.Parser("-02.0").require_decimal_value()
        self.assertTrue(v == decimal.Decimal('-2'))
        good = (
            "+12345678901234567890.12345678901234567890",
            "-12345678901234567890.12345678901234567890",
            "12345678901234567890.12345678901234567890",
            "1",
            "12345678901234567890",
            "0",
            "-1"
            "0002",
            )
        bad = (
            "%2B1.1",
            "%2b1.1",
            " 1",
            "1.",
            "2b",
            "2B",
            "0x09",
            "null", ""
            )
        self.from_str(parser.Parser.require_decimal_value, good, bad)

    def test_double_value(self):
        """doubleValue = decimalValue [ "e" [SIGN] 1*DIGIT ] / nanInfinity
            nanInfinity = 'NaN' / '-INF' / 'INF'
        """
        v = parser.Parser("3.14").require_double_value()
        self.assertTrue(v == 3.14)
        v = parser.Parser("-02.0").require_double_value()
        self.assertTrue(v == -2.0)
        v = parser.Parser("3.14e8").require_double_value()
        self.assertTrue(v == 3.14e8)
        good = (
            "+12345678901234567890.12345678901234567890e+00000000000000000008",
            "-12345678901234567890.12345678901234567890E-00000000000000000008",
            "12345678901234567890.12345678901234567890e00000000000000000008",
            "1",
            "12345678901234567890",
            "0",
            "-1"
            "0002",
            "1e1",
            "1E8",
            "NaN",
            "INF",
            "-INF",
            "1e0"
            )
        bad = (
            "%2B1.1",
            "%2b1.1",
            " 1",
            "1.",
            "2b",
            "2B",
            "0x09",
            "NAN",
            "inf",
            "-inf",
            "1e",
            "1.e1",
            "null", ""
            )
        self.from_str(parser.Parser.require_double_value, good, bad)
        self.from_str(parser.Parser.require_single_value, good, bad)

    def test_sbyte_value(self):
        """decimalValue = [ sign ] 1*3DIGIT"""
        v = parser.Parser("+123").require_sbyte_value()
        self.assertTrue(v == 123)
        v = parser.Parser("-9").require_sbyte_value()
        self.assertTrue(v == -9)
        good = (
            "+127",
            "127",
            "-128",
            "12",
            "1",
            "0",
            "-1",
            "001",
            )
        bad = (
            "128",
            "-129",
            "%2B1",
            "%2b1",
            " 1",
            "1.",
            "2b",
            "2B",
            "0x09",
            "0002",
            "2 ",
            "null", ""
            )
        self.from_str(parser.Parser.require_sbyte_value, good, bad)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
