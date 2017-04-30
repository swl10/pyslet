#! /usr/bin/env python

import datetime
import logging
import unittest

from decimal import Decimal

from pyslet.iso8601 import (
    Date,
    TimePoint
    )
from pyslet.odata4.primitives import (
    BinaryValue,
    BooleanValue,
    ByteValue,
    DateValue,
    DateTimeOffsetValue,
    DecimalValue,
    DoubleValue,
    Int16Value,
    Int32Value,
    Int64Value,
    PrimitiveValue,
    SByteValue,
    SingleValue,
    Value
    )
from pyslet.py2 import (
    long2,
    to_text,
    ul,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ValueTests, 'test'),
        unittest.makeSuite(PrimitiveValueTests, 'test'),
        ))


class ValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all values"""
        # construct without a property declaration
        v = Value()
        # this is a NULL value of an unspecified type
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        d = {}
        try:
            d[v] = 1
            self.fail("Unspecified Value is hashable")
        except TypeError:
            pass


NUMERIC_TYPES = (
    ByteValue,
    DecimalValue,
    DoubleValue,
    Int16Value,
    Int32Value,
    Int64Value,
    SByteValue,
    SingleValue)


class PrimitiveValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all Primitive values"""
        # construct without a property declaration
        self.assertTrue(PrimitiveValue.type_name is None)
        v = PrimitiveValue()
        # this is a NULL value of an unspecified type
        self.assertTrue(isinstance(v, Value))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value on construction")
        d = {}
        try:
            d[v] = 1
            self.fail("PrimitiveValue hashable")
        except TypeError:
            pass
        v = PrimitiveValue.from_value(None)
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value from_value")
        v.set(None)
        self.assertTrue(v.value is None, "Null value from set")
        # typeless null can be set from a typed null
        v.set(BooleanValue())
        self.assertTrue(v.value is None, "Null value from set")
        # but not from any other value type - results in null
        v.set(0)
        self.assertFalse(v)
        b = BooleanValue()
        b.set(True)
        v.set(b)
        self.assertFalse(v)
        v.set_default_value()
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value as default")
        # set from an existing type-less NULL, you get another one
        v1 = PrimitiveValue.from_value(v)
        self.assertFalse(v1)
        self.assertTrue(v1.is_null())
        self.assertTrue(v1.value is None, "Null value from type-less Null")
        # text representation of NULL is an error
        try:
            to_text(v)
            self.fail("Text of NULL")
        except ValueError:
            pass

    def test_binary(self):
        """Binary data"""
        self.assertTrue(BinaryValue.type_name == "Edm.Binary")
        typeless_null = PrimitiveValue()
        typed_null = BinaryValue()
        self.assertTrue(isinstance(typed_null, PrimitiveValue))
        self.assertFalse(typed_null)
        self.assertTrue(typed_null.is_null())
        self.assertTrue(typed_null.value is None, "Null value on construction")
        self.assertTrue(typed_null == typeless_null, "type-less NULL match")
        self.assertFalse(typed_null != typeless_null, "type-less NULL match")
        try:
            to_text(typed_null)
            self.fail("Text of NULL")
        except ValueError:
            pass
        v = PrimitiveValue.from_value(b'Hello')
        self.assertTrue(isinstance(v, BinaryValue))
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(v.value == b'Hello', "from_value(bytes)")
        self.assertTrue(to_text(v) == 'SGVsbG8=', "to_text()")
        v1 = BinaryValue()
        v1.set(b'Hello')
        self.assertTrue(v1 == v, "Values match")
        self.assertFalse(v1 != v, "Values match")
        self.assertFalse(v1 == typed_null, "Not a typed null")
        self.assertFalse(v1 == typeless_null, "Not a typeless null")
        # character-string special encoding
        v1.set(ul(b'Caf\xe9'))
        self.assertTrue(v1.value == b'Caf\xc3\xa9', "set(unicode)")
        self.assertTrue(to_text(v1) == 'Q2Fmw6k=', "to_text()")
        self.assertFalse(v1 == v, "Values don't match")
        self.assertTrue(v1 != v, "Values don't match")
        # check we're using the URL-safe version of base64
        v2 = BinaryValue()
        v2.set(ul(b'ab?de>g'))
        self.assertTrue(v2.value == b'ab?de>g', "set(unicode)")
        self.assertTrue(to_text(v2) == 'YWI_ZGU-Zw==', "to_text()")
        # casts to BinaryValue are not allowed (unless None)
        iv = Int64Value()
        v2.set(iv)
        self.assertFalse(v2)
        iv.set(3)
        v2.set(iv)
        self.assertFalse(v2, "Cast from Int64 to Binary")
        # other types are serialized using bytes representation
        v3 = BinaryValue()
        v3.set(1)
        self.assertTrue(v3.value == b'1', "set(int) %s" % v3.value)
        # check deep copy
        v4 = PrimitiveValue.from_value(v1)
        self.assertTrue(isinstance(v4, BinaryValue))
        self.assertTrue(v4.value == v1.value, "deep copy")
        v4.set(v1)
        self.assertTrue(v4.value == v1.value, "deep copy")
        # check __bytes__ call

        class HelloBytes(object):

            def __str__(self):
                return b'HiBytes'

            def __bytes__(self):
                return b'HiBytes'

        v4.set(HelloBytes())
        self.assertTrue(v4.value == b'HiBytes')
        v4.set()
        self.assertTrue(v4.value is None)

    def test_boolean(self):
        """Boolean values"""
        self.assertTrue(BooleanValue.type_name == "Edm.Boolean")
        typeless_null = PrimitiveValue()
        typed_null = BooleanValue()
        self.assertTrue(isinstance(typed_null, PrimitiveValue))
        self.assertFalse(typed_null)
        self.assertTrue(typed_null.is_null())
        self.assertTrue(typed_null.value is None, "Null value on construction")
        self.assertTrue(typed_null == typeless_null, "type-less NULL match")
        self.assertFalse(typed_null != typeless_null, "type-less NULL match")
        try:
            to_text(typed_null)
            self.fail("Text of NULL")
        except ValueError:
            pass
        v = PrimitiveValue.from_value(True)
        self.assertTrue(isinstance(v, BooleanValue))
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(v.value is True, "from_value(True)")
        self.assertTrue(to_text(v) == 'true', "to_text()")
        v1 = PrimitiveValue.from_value(False)
        self.assertTrue(isinstance(v, BooleanValue))
        self.assertTrue(v1.value is False, "from_value(False)")
        self.assertTrue(to_text(v1) == 'false', "to_text()")
        self.assertFalse(v1 == v, "Values don't match")
        self.assertTrue(v1 != v, "Values don't match")
        self.assertFalse(v1 == typed_null, "Not a typed null")
        self.assertFalse(v1 == typeless_null, "Not a typeless null")
        # casts to BooleanValue are not allowed (unless None)
        iv = Int64Value()
        v1.set(iv)
        self.assertFalse(v1)
        # we don't even allow logical to numeric cast (the spec isn't
        # that clear but better to be strict here)
        iv.set(1)
        v1.set(iv)
        self.assertFalse(v1, "Cast from Int64 to Boolean")
        # other types use Python's bool test
        v1.set(1)
        self.assertTrue(v1.value is True, "set(int) %s" % v1.value)
        v1.set(0.0)
        self.assertTrue(v1.value is False, "set(0.0) %s" % v1.value)
        v1.set("false")
        self.assertTrue(v1.value is True, "set(str) %s" % v1.value)
        # check deep copy
        v2 = PrimitiveValue.from_value(typed_null)
        self.assertTrue(isinstance(v2, BooleanValue))
        self.assertTrue(v2.value is None, "deep copy")
        v1.set(True)
        v2.set(v1)
        self.assertTrue(v2.value is True, "deep copy")
        v1.set(False)
        v2.set(v1)
        self.assertTrue(v2.value is False, "deep copy")
        v2.set()
        self.assertTrue(v2.value is None, "deep copy")

    def test_byte(self):
        """Byte values"""
        self.assertTrue(ByteValue.type_name == "Edm.Byte")
        typeless_null = PrimitiveValue()
        typed_null = ByteValue()
        self.assertTrue(isinstance(typed_null, PrimitiveValue))
        self.assertFalse(typed_null)
        self.assertTrue(typed_null.is_null())
        self.assertTrue(typed_null.value is None, "Null value on construction")
        self.assertTrue(typed_null == typeless_null, "type-less NULL match")
        self.assertFalse(typed_null != typeless_null, "type-less NULL match")
        try:
            to_text(typed_null)
            self.fail("Text of NULL")
        except ValueError:
            pass
        # can't be created from the PrimitiveValue factory method
        # v = PrimitiveValue.from_value(1)
        v = ByteValue()
        v.set(1)
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(isinstance(v.value, int))
        self.assertTrue(v.value == 1, "set(1)")
        self.assertTrue(to_text(v) == '1', "to_text()")
        v1 = ByteValue()
        v1.set(0)
        self.assertTrue(v1)
        self.assertTrue(v1.value == 0, "set(0)")
        self.assertTrue(to_text(v1) == '0', "to_text() = %s")
        self.assertFalse(v1 == v, "Values don't match")
        self.assertTrue(v1 != v, "Values don't match")
        self.assertFalse(v1 == typed_null, "Not a typed null")
        self.assertFalse(v1 == typeless_null, "Not a typeless null")
        # check limits
        self.assertTrue(ByteValue.MAX == 255)
        self.assertTrue(ByteValue.MIN == 0)
        v.set(-1)
        self.assertFalse(v, "Negative byte")
        v.set(256)
        self.assertFalse(v, "Large byte")
        v.set(255)
        self.assertTrue(to_text(v) == '255', "to_text()")
        self.assertTrue(isinstance(v.value, int))
        # set from python 2 long
        v.set(long2(100))
        self.assertTrue(to_text(v) == '100', "to_text()")
        self.assertTrue(isinstance(v.value, int))
        # set from float
        v.set(255.9)
        self.assertTrue(v.value == 255, "set(255.9)")
        self.assertTrue(isinstance(v.value, int))
        v.set(256.0)
        self.assertFalse(v, "Large float")
        v.set(-0.9)
        self.assertTrue(v.value == 0, "set(-0.9)")
        self.assertTrue(isinstance(v.value, int))
        v.set(-1.0)
        self.assertFalse(v, "Negative float")
        # set from decimal
        v.set(Decimal('255.999'))
        self.assertTrue(v.value == 255, "set(Decimal('255.999'))")
        self.assertTrue(isinstance(v.value, int))
        v.set(Decimal('256.0'))
        self.assertFalse(v, "Large decimal")
        v.set(Decimal('-0.999'))
        self.assertTrue(v.value == 0, "set(Decimal('-0.999'))")
        self.assertTrue(isinstance(v.value, int))
        v.set(Decimal('-1.0'))
        self.assertFalse(v, "Negative Decimal")
        # set from True and False
        v.set(True)
        self.assertTrue(isinstance(v.value, int))
        self.assertTrue(v.value == 1)
        v.set(False)
        self.assertTrue(isinstance(v.value, int))
        self.assertTrue(v.value == 0)
        # check deep copy
        v2 = PrimitiveValue.from_value(typed_null)
        self.assertTrue(isinstance(v2, ByteValue))
        self.assertTrue(v2.value is None, "deep copy")
        v1.set(3)
        v2.set(v1)
        self.assertTrue(v2.value == 3, "deep copy")
        v1.set(None)
        v2.set(v1)
        self.assertTrue(v2.value is None, "deep copy typed null")
        # casts to ByteValue are allowed from all Numeric types (and any
        # null)
        v2.set(BinaryValue())
        self.assertTrue(v2.value is None, "cast from Binary null")
        for cls in NUMERIC_TYPES:
            n = cls()
            n.set(3.14)
            v1.set(n)
            self.assertTrue(v1, "Set ByteValue from %s" % cls.type_name)
            self.assertTrue(v1.value == 3)
        # we don't even allow logical to numeric cast (the spec isn't
        # that clear but better to be strict here)
        b = BooleanValue()
        b.set(0)
        v1.set(b)
        self.assertFalse(v1, "Cast form Boolean to Byte")

    def test_date(self):
        """Date values"""
        self.assertTrue(DateValue.type_name == "Edm.Date")
        typeless_null = PrimitiveValue()
        typed_null = DateValue()
        self.assertTrue(isinstance(typed_null, PrimitiveValue))
        self.assertFalse(typed_null)
        self.assertTrue(typed_null.is_null())
        self.assertTrue(typed_null.value is None, "Null value on construction")
        self.assertTrue(typed_null == typeless_null, "type-less NULL match")
        self.assertFalse(typed_null != typeless_null, "type-less NULL match")
        try:
            to_text(typed_null)
            self.fail("Text of NULL")
        except ValueError:
            pass
        # PrimitiveValue factory method using iso8601.Date
        v = PrimitiveValue.from_value(Date.from_str("19690720"))
        self.assertTrue(isinstance(v, DateValue))
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(isinstance(v.value, Date), "from_value(Date)")
        self.assertTrue(v.value.get_calendar_day() == (19, 69, 7, 20))
        v = PrimitiveValue.from_value(datetime.date(1969, 7, 20))
        self.assertTrue(isinstance(v, DateValue))
        self.assertTrue(v)
        self.assertTrue(isinstance(v.value, Date),
                        "from_value(datetime.date)")
        self.assertTrue(v.value.get_calendar_day() == (19, 69, 7, 20))
        v = DateValue()
        v.set(Date.from_str("19690720"))
        self.assertTrue(isinstance(v.value, Date), "set(Date)")
        self.assertTrue(v.value.get_calendar_day() == (19, 69, 7, 20))
        v.set(datetime.date(1969, 7, 20))
        self.assertTrue(v.value.get_calendar_day() == (19, 69, 7, 20))
        v.set(Date.from_str("-07520421", xdigits=0))
        self.assertTrue(v.value.get_xcalendar_day() == (True, 7, 52, 4, 21))
        # check deep copy
        v = PrimitiveValue.from_value(typed_null)
        self.assertTrue(isinstance(v, DateValue))
        self.assertTrue(v.value is None, "deep copy")
        v1 = DateValue()
        v1.set(Date.from_str("19690720"))
        v2 = DateValue()
        v2.set(v1)
        self.assertTrue(v2.value == v1.value, "deep copy")
        v1.set(None)
        v2.set(v1)
        self.assertTrue(v2.value is None, "deep copy typed null")
        # casts to Date are not allowed
        i = Int16Value()
        v.set(i)
        self.assertFalse(v, "Cast from Int16 to Date")

    def test_date_time_offset(self):
        """DateTimeOffset values"""
        self.assertTrue(DateTimeOffsetValue.type_name == "Edm.DateTimeOffset")
        typeless_null = PrimitiveValue()
        typed_null = DateTimeOffsetValue()
        self.assertTrue(isinstance(typed_null, PrimitiveValue))
        self.assertFalse(typed_null)
        self.assertTrue(typed_null.is_null())
        self.assertTrue(typed_null.value is None, "Null value on construction")
        self.assertTrue(typed_null == typeless_null, "type-less NULL match")
        self.assertFalse(typed_null != typeless_null, "type-less NULL match")
        try:
            to_text(typed_null)
            self.fail("Text of NULL")
        except ValueError:
            pass
        # PrimitiveValue factory method using iso8601.TimePoint
        v = PrimitiveValue.from_value(TimePoint.from_str("19690720T201740Z"))
        self.assertTrue(isinstance(v, DateTimeOffsetValue))
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(isinstance(v.value, TimePoint),
                        "from_value(DateTimeOffset)")
        self.assertTrue(v.value.get_calendar_time_point() ==
                        (19, 69, 7, 20, 20, 17, 40))
        v = PrimitiveValue.from_value(
            datetime.datetime(1969, 7, 20, 20, 17, 40))
        self.assertTrue(isinstance(v, DateTimeOffsetValue), repr(v))
        self.assertTrue(v)
        self.assertTrue(isinstance(v.value, TimePoint),
                        "from_value(datetime.datetime)")
        self.assertTrue(v.value.get_calendar_time_point() ==
                        (19, 69, 7, 20, 20, 17, 40))
        v = DateTimeOffsetValue()
        v.set(TimePoint.from_str("19690720T201740Z"))
        self.assertTrue(isinstance(v.value, TimePoint), "set(TimePoint)")
        self.assertTrue(v.value.get_calendar_time_point() ==
                        (19, 69, 7, 20, 20, 17, 40))
        v.set(datetime.datetime(1969, 7, 20, 20, 17, 40))
        self.assertTrue(v.value.get_calendar_time_point() ==
                        (19, 69, 7, 20, 20, 17, 40))
        v.set(TimePoint.from_str("-07520421T160000", xdigits=0))
        self.assertTrue(v.value.get_xcalendar_time_point() ==
                        (True, 7, 52, 4, 21, 16, 0, 0))
        v.set(0)
        self.assertTrue(v.value.get_unixtime() == 0)
        v.set(0.0)
        self.assertTrue(v.value.get_unixtime() == 0)
        v.set(Decimal(0))
        self.assertTrue(v.value.get_unixtime() == 0)
        # OData does not allow leap seconds
        leap = TimePoint.from_str("2016-12-31T23:59:60Z")
        v.set(leap)
        self.assertTrue(str(v.value) == "2016-12-31T23:59:59Z",
                        "leap second stall")
        # check deep copy
        v = PrimitiveValue.from_value(typed_null)
        self.assertTrue(isinstance(v, DateTimeOffsetValue))
        self.assertTrue(v.value is None, "deep copy")
        v1 = DateTimeOffsetValue()
        v1.set(TimePoint.from_str("19690720T201740Z"))
        v2 = DateTimeOffsetValue()
        v2.set(v1)
        self.assertTrue(v2.value == v1.value, "deep copy")
        v1.set(None)
        v2.set(v1)
        self.assertTrue(v2.value is None, "deep copy typed null")
        # casts to Date are not allowed
        i = Int16Value()
        v.set(i)
        self.assertFalse(v, "Cast from Int16 to Date")

    def test_decimal(self):
        """Decimal values"""
        self.assertTrue(DecimalValue.type_name == "Edm.Decimal")
        typeless_null = PrimitiveValue()
        typed_null = DecimalValue()
        self.assertTrue(isinstance(typed_null, PrimitiveValue))
        self.assertFalse(typed_null)
        self.assertTrue(typed_null.is_null())
        self.assertTrue(typed_null.value is None, "Null value on construction")
        self.assertTrue(typed_null == typeless_null, "type-less NULL match")
        self.assertFalse(typed_null != typeless_null, "type-less NULL match")
        try:
            to_text(typed_null)
            self.fail("Text of NULL")
        except ValueError:
            pass
        # can be created from the PrimitiveValue factory method
        v = PrimitiveValue.from_value(Decimal(1))
        self.assertTrue(isinstance(v, DecimalValue))
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(isinstance(v.value, Decimal), "from_value(Decimal)")
        self.assertTrue(v.value == 1)
        v = DecimalValue()
        v.set(1)
        self.assertTrue(v)
        self.assertFalse(v.is_null())
        self.assertTrue(isinstance(v.value, Decimal))
        self.assertTrue(v.value == 1, "set(1)")
        self.assertTrue(to_text(v) == '1', "to_text()")
        v1 = DecimalValue()
        v1.set(0)
        self.assertTrue(v1)
        self.assertTrue(v1.value == 0, "set(0)")
        self.assertTrue(to_text(v1) == '0', "to_text() = %s")
        self.assertFalse(v1 == v, "Values don't match")
        self.assertTrue(v1 != v, "Values don't match")
        self.assertFalse(v1 == typed_null, "Not a typed null")
        self.assertFalse(v1 == typeless_null, "Not a typeless null")
        v.set(Decimal(-1))
        self.assertTrue(to_text(v) == '-1', "to_text()")
        self.assertTrue(isinstance(v.value, Decimal))
        # set from python 2 long
        v.set(long2(100))
        self.assertTrue(to_text(v) == '100', "to_text()")
        self.assertTrue(isinstance(v.value, Decimal))
        # set from float
        v.set(3.5)
        self.assertTrue(v.value == Decimal('3.5'), "set(3.5)")
        self.assertTrue(isinstance(v.value, Decimal))
        # set from decimal
        v.set(Decimal('255.999'))
        self.assertTrue(isinstance(v.value, Decimal))
        self.assertTrue(to_text(v) == '255.999')
        # set from True and False
        v.set(True)
        self.assertTrue(isinstance(v.value, Decimal))
        self.assertTrue(v.value == 1)
        v.set(False)
        self.assertTrue(isinstance(v.value, Decimal))
        self.assertTrue(v.value == 0)
        # check deep copy
        v2 = PrimitiveValue.from_value(typed_null)
        self.assertTrue(isinstance(v2, DecimalValue))
        self.assertTrue(v2.value is None, "deep copy")
        v1.set(3)
        v2.set(v1)
        self.assertTrue(v2.value == 3, "deep copy")
        v1.set(None)
        v2.set(v1)
        self.assertTrue(v2.value is None, "deep copy typed null")
        # casts to DecimalValue are allowed from all Numeric types (and any
        # null)
        v2.set(BinaryValue())
        self.assertTrue(v2.value is None, "cast from Binary null")
        for cls in NUMERIC_TYPES:
            n = cls()
            n.set(3.14)
            v1.set(n)
            self.assertTrue(v1, "Set DecimalValue from %s" % cls.type_name)
            self.assertTrue(v1.value >= Decimal(3) and
                            v1.value <= Decimal('3.15'), v1.value)
        # we don't even allow logical to numeric cast (the spec isn't
        # that clear but better to be strict here)
        b = BooleanValue()
        b.set(0)
        v1.set(b)
        self.assertFalse(v1, "Cast from Boolean to Decimal")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
