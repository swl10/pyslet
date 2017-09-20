#! /usr/bin/env python

import datetime
import logging
import unittest
import uuid

from decimal import Decimal, getcontext

from pyslet.iso8601 import (
    Date,
    Time,
    TimePoint
    )
from pyslet.odata4 import errors
from pyslet.odata4 import geotypes as geo
from pyslet.odata4 import metadata as csdl
from pyslet.odata4 import model as odata
from pyslet.odata4 import primitive
from pyslet.odata4 import types
from pyslet.py2 import (
    BoolMixin,
    long2,
    to_text,
    uempty,
    ul,
    UnicodeMixin,
    )
from pyslet.rfc2396 import URI
from pyslet.vfs import OSFilePath
from pyslet.xml.xsdatatypes import Duration


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(PrimitiveTypeTests, 'test'),
        unittest.makeSuite(PrimitiveValueTests, 'test'),
        unittest.makeSuite(OperatorTests, 'test'),
        ))


TEST_DATA_DIR = OSFilePath(__file__).split()[0].join('data_odata4')


def load_trippin():
    dpath = TEST_DATA_DIR.join('trippin.xml')
    uri = URI.from_virtual_path(dpath)
    doc = csdl.CSDLDocument(base_uri=uri)
    doc.read()
    return doc.root.entity_model


ALL_TYPES = (
    # Value type, example value, True if it is the default value type
    # for this example value
    (primitive.BinaryValue, b'3.14', True),
    (primitive.BooleanValue, True, True),
    (primitive.ByteValue, 3, False),
    (primitive.DateValue, Date(), True),
    (primitive.DateTimeOffsetValue, TimePoint().with_zone(0), True),
    (primitive.DecimalValue, Decimal('3.14'), True),
    (primitive.DoubleValue, 3.14, True),
    (primitive.DurationValue, Duration(), True),
    (primitive.GuidValue, uuid.UUID(int=3), True),
    (primitive.Int16Value, 3, False),
    (primitive.Int32Value, 3, False),
    (primitive.Int64Value, 3, True),
    (primitive.SByteValue, 3, False),
    (primitive.SingleValue, 3.14, False),
    # primitive.StreamValue is handled specially
    (primitive.StringValue, ul('3.14'), True),
    (primitive.TimeOfDayValue, Time(), True),
    # primitive.Geography is abstract
    (primitive.GeographyPointValue, geo.PointLiteral(
        srid=4326, point=geo.Point(-1.00244140625, 51.44775390625)), True),
    (primitive.GeographyLineStringValue, geo.LineStringLiteral(
        srid=4326, line_string=geo.LineString(
            ((-1.00244140625, 51.44775390625),
             (-0.9964599609375, 51.455810546875)))), True),
    (primitive.GeographyPolygonValue, geo.PolygonLiteral(
        srid=4326, polygon=geo.Polygon(
            (((-1.003173828125, 51.439697265625),
              (-1.0029296875, 51.4437255859375),
              (-1.001708984375, 51.4437255859375),
              (-1.001708984375, 51.439697265625),
              (-1.003173828125, 51.439697265625)),
             ))), True),
    (primitive.GeographyMultiPointValue, geo.MultiPointLiteral(
        srid=4326, multipoint=(
            geo.Point(-1.00244140625, 51.44775390625),
            geo.Point(-0.9964599609375, 51.455810546875))), True),
    (primitive.GeographyMultiLineStringValue, geo.MultiLineStringLiteral(
        srid=4326, multi_line_string=(
            geo.LineString(((-1.00244140625, 51.44775390625),
                            (-0.9964599609375, 51.455810546875))),
            )), True),
    (primitive.GeographyMultiPolygonValue, geo.MultiPolygonLiteral(
        srid=4326, multi_polygon=(
            geo.Polygon((((-1.003173828125, 51.439697265625),
                          (-1.0029296875, 51.4437255859375),
                          (-1.001708984375, 51.4437255859375),
                          (-1.001708984375, 51.439697265625),
                          (-1.003173828125, 51.439697265625)),
                         )),
            )), True),
    (primitive.GeographyCollectionValue, geo.GeoCollectionLiteral(
        srid=4326, items=(
            geo.Point(-1.00244140625, 51.44775390625),
            geo.LineString(((-1.00244140625, 51.44775390625),
                            (-0.9964599609375, 51.455810546875)))
            )), True),
    # primitive.Geometry is abstract
    (primitive.GeometryPointValue, geo.PointLiteral(
        srid=0, point=geo.Point(1.0, -1.0)), True),
    (primitive.GeometryLineStringValue, geo.LineStringLiteral(
        srid=0, line_string=geo.LineString(
            ((1.0, -1.0), (-1.0, 1.0)))), True),
    (primitive.GeometryPolygonValue, geo.PolygonLiteral(
        srid=0, polygon=geo.Polygon(
            (((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0),
              (1.0, -1.0)), ))), True),
    (primitive.GeometryMultiPointValue, geo.MultiPointLiteral(
        srid=0, multipoint=(
            geo.Point(1.0, -1.0), geo.Point(-1.0, 1.0))), True),
    (primitive.GeometryMultiLineStringValue, geo.MultiLineStringLiteral(
        srid=0, multi_line_string=(
            geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
            geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
            )), True),
    (primitive.GeometryMultiPolygonValue, geo.MultiPolygonLiteral(
        srid=0, multi_polygon=(
            geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                          (-1.0, -1.0), (1.0, -1.0)), )),
            geo.Polygon((((4.0, -1.0), (4.0, 1.0), (2.0, 1.0),
                          (2.0, -1.0), (4.0, -1.0)), ))
            )), True),
    (primitive.GeometryCollectionValue, geo.GeoCollectionLiteral(
        srid=0, items=(
            geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
            geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
            geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                          (-1.0, -1.0), (1.0, -1.0)), )),
            )), True)
    )


class PrimitiveTypeTests(unittest.TestCase):

    def test_constructor(self):
        t = primitive.PrimitiveType()
        self.assertTrue(t.base is None, "No base by default")
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # callable, returns a null of PrimitiveValue
        v = t()
        self.assertTrue(isinstance(v, primitive.PrimitiveValue))
        self.assertTrue(v.type_def is t)
        self.assertTrue(v.is_null())

    def test_max_length_binary(self):
        # For binary or stream properties this is the octet length of
        # the binary data
        t = primitive.edm_binary
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # create a derived class with max_length
        t1 = primitive.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # max_length is None, unknown restriction
        v = t1()
        self.assertTrue(isinstance(v, primitive.BinaryValue))
        v.set_value(b'Hello')
        # set a weak value: max_length of 3
        t1.set_max_length(3, can_override=True)
        v = t1()
        try:
            v.set_value(b'Hello')
            self.fail("Would truncate")
        except ValueError:
            pass
        v.set_value(b'Hel')
        # 0 => max size, treated the same as None in our case
        t1.set_max_length(0)
        v = t1()
        v.set_value(b'Hello')
        try:
            t1.set_max_length(4)
            self.fail("Strong facet redefined")
        except errors.ModelError:
            pass

    def test_max_length_stream(self):
        # TODO
        pass

    def test_max_length_string(self):
        cafe = ul('Caf\xe9')
        t = primitive.edm_string
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # create a derived class with max_length
        t1 = primitive.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # max_length is None, unknown restriction
        v = t1()
        self.assertTrue(isinstance(v, primitive.StringValue))
        v.set_value(cafe)
        # set a weak value
        t1.set_max_length(4, can_override=True)
        v = t1()
        v.set_value(cafe)     # OK as character length is 4, utf8 length check
        # set another weak value
        t1.set_max_length(3, can_override=True)
        try:
            v.set_value(cafe)
            self.fail("Would truncate")
        except ValueError:
            pass
        v.set_value(cafe[1:])
        # 0 => max size, treated the same as None in our case
        t1.set_max_length(0)
        v = t1()
        v.set_value(cafe)
        try:
            t1.set_max_length(4)
            self.fail("Strong facet redefined")
        except errors.ModelError:
            pass

    def test_precision_datetimeoffset(self):
        """For a temporal property the value of this attribute specifies
        the number of decimal places allowed in the seconds portion of
        the property's value..."""
        dt20 = TimePoint.from_str("2017-06-05T20:44:14.12345678901234567890Z")
        t = primitive.edm_date_time_offset
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # create a derived class (does not inherit precision)
        t1 = primitive.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, primitive.DateTimeOffsetValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set_value(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14Z")
        self.assertFalse(v.value == dt20)
        # set a weak value for precision
        t1.set_precision(6, can_override=True)
        v = t1()
        v.set_value(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14.123456Z",
                        v.value.time.second)
        self.assertFalse(v.value == dt20)
        # set a strong value for precision
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set_value(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14.123456789012Z")
        self.assertFalse(v.value == dt20)
        # set another strong value should now fail
        try:
            t1.set_precision(6)
            self.fail("Strong Precision redefined")
        except errors.ModelError:
            pass

    def test_precision_duration(self):
        d20 = Duration("PT0.12345678901234567890S")
        t = primitive.edm_duration
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # create a derived class with precision
        t1 = primitive.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, primitive.DurationValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set_value(d20)
        self.assertTrue(v.value == "PT0S", str(v.value))
        self.assertFalse(v.value == d20)
        # set a weak value for precision
        t1.set_precision(6, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == "PT0.123456S")
        self.assertFalse(v.value == d20)
        # set a strong value for precision
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == "PT0.123456789012S")
        self.assertFalse(v.value == d20)
        # set another strong value should now fail
        try:
            t1.set_precision(6)
            self.fail("Strong Precision redefined")
        except errors.ModelError:
            pass

    def test_precision_timeofday(self):
        t20 = Time.from_str("20:44:14.12345678901234567890")
        t = primitive.edm_time_of_day
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # create a derived class with precision
        t1 = primitive.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, primitive.TimeOfDayValue))
        # If unspecified the precision is 0
        v.set_value(t20)
        self.assertTrue(v.value == "20:44:14")
        self.assertFalse(v.value == t20)
        # set a weak value for precision
        t1.set_precision(6, can_override=True)
        v = t1()
        v.set_value(t20)
        self.assertTrue(v.value == "20:44:14.123456")
        self.assertFalse(v.value == t20)
        # set a strong value for precision
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set_value(t20)
        self.assertTrue(v.value == "20:44:14.123456789012")
        self.assertFalse(v.value == t20)
        # set another strong value should now fail
        try:
            t1.set_precision(6)
            self.fail("Strong Precision redefined")
        except errors.ModelError:
            pass

    def test_decimal_precision(self):
        """For a decimal property the value of this attribute specifies
        the maximum number of significant decimal digits of the
        property's value"""
        self.assertTrue(getcontext().prec >= 28,
                        "Tests require decimal precision of 28 or greater")
        d20str = "0.12345678901234567890"
        i20str = "12345678901234567890"
        f20str = "1234567890.1234567890"
        d20 = Decimal(d20str)
        i20 = Decimal(i20str)
        f20 = Decimal(f20str)
        t = primitive.edm_decimal
        self.assertTrue(t.precision is None, "No Precision by default")
        t1 = primitive.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, primitive.DecimalValue))
        # If no value is specified, the decimal property has unspecified
        # precision.  Python's default of 28 is larger than the 20 used
        # in these tests.  The scale property, however, defaults to 0!
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0"))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        v.set_value(f20)
        self.assertTrue(v.value == Decimal("1234567890"))
        # a specified precision, unspecified scale defaults to 0
        t1.set_precision(6, can_override=True)
        v = t1()
        # these results should be rounded
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0"))
        self.assertFalse(v.value == d20)
        try:
            v.set_value(i20)
            self.fail("Integer larger than precision")
        except ValueError:
            pass
        # a specified precision with a variable scale
        t1.set_precision(6, -1, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0.123457"))
        v.set_value(i20)
        self.assertTrue(v.value == Decimal("12345700000000000000"))
        v.set_value(f20)
        self.assertTrue(v.value == Decimal("1234570000"))
        # if we exceed the digits we had originally we do not add 0s as
        # this is a maximum number of digits, not an absolute number of
        # digits.
        t1.set_precision(42, 21, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == d20)
        self.assertTrue(str(v) == d20str, str(v))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        self.assertTrue(str(v) == i20str, str(v))
        v.set_value(f20)
        self.assertTrue(v.value == f20)
        self.assertTrue(str(v) == f20str, str(v))
        # Unspecified precision, variable scale (uses -1)
        # sig fig limited by python defaults, decimal places unlimited
        t1.set_precision(None, -1, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == d20)
        self.assertTrue(str(v) == d20str, str(v))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        self.assertTrue(str(v) == i20str, str(v))
        v.set_value(f20)
        self.assertTrue(v.value == f20)
        self.assertTrue(str(v) == f20str, str(v))
        # unspecified precision, scale is OK
        t1.set_precision(None, 3, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0.123"))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        v.set_value(f20)
        self.assertTrue(v.value == Decimal("1234567890.123"))
        try:
            t1.set_precision(2, 3, can_override=True)
            self.fail("scale must be <= precision")
        except errors.ModelError:
            pass
        # try scale > 0
        t1.set_precision(6, 3, can_override=True)
        v = t1()
        v.set_value(d20)
        # scale beats precision
        self.assertTrue(v.value == Decimal("0.123"))
        try:
            v.set_value(i20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        v.set_value(Decimal("123.4567"))
        self.assertTrue(v.value == Decimal("123.457"))
        # try scale = 0
        t1.set_precision(6, 0, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0"))
        try:
            v.set_value(f20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        # try scale = precision
        t1.set_precision(6, 6, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0.123457"))
        try:
            v.set_value(1)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        # There's a strange note about negative scale in the
        # specification.  Internally Python can support negative scale
        # but the suggestion is that this translates to a Precision
        # value that exceeds the maximum supported native precision.
        # For example, if Python's default precision is 28 then we could
        # allow precision to be set to 30 with an implied negative scale
        # of -2, this would result in values being rounded such that the
        # last two digits are always zero.  Given that scale cannot be
        # negative it would have to be omitted (implied 0 behaviour).
        t1.set_precision(getcontext().prec + 2)
        xstr = "1" * (getcontext().prec + 2)
        v.set_value(Decimal(xstr))
        self.assertTrue(v.value == Decimal(xstr[:-2] + "00"))
        # TOD: testing of strong values in set_precision

    def test_unicode_string(self):
        cafe = ul('Caf\xe9')
        t = primitive.edm_string
        self.assertTrue(t.unicode is None, "Facet unspecified by default")
        t1 = primitive.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # by default we accept unicode characters
        v = t1()
        self.assertTrue(isinstance(v, primitive.StringValue))
        v.set_value(cafe)
        # set a weak value
        t1.set_unicode(False, can_override=True)
        v = t1()
        try:
            v.set_value(cafe)
            self.fail("ASCII required")
        except ValueError:
            pass
        v.set_value(cafe[:-1])    # OK
        # set a strong value
        t1.set_unicode(True)
        v = t1()
        v.set_value(cafe)
        try:
            t1.set_unicode(False)
            self.fail("Strong facet can't be changed")
        except errors.ModelError:
            pass

    def test_srid_geo(self):
        for t, pv, default in ALL_TYPES:
            if issubclass(t, (primitive.GeographyValue,
                              primitive.GeometryValue)):
                geodef = t().type_def
                self.assertTrue(geodef.value_type is t)
                self.assertTrue(geodef.srid is None)
                t1 = primitive.PrimitiveType()
                t1.set_base(geodef)
                # value_type inherited from geodef
                self.assertTrue(t1.value_type is geodef.value_type)
                self.assertTrue(t1.srid is None)
                v = t1()
                self.assertTrue(isinstance(v, t))
                v.set_value(pv)
                if issubclass(t, primitive.GeographyValue):
                    def_srid = 4326
                else:
                    def_srid = 0
                self.assertTrue(v.value.srid == def_srid)
                # make up a similar value with a different srid
                pv1 = pv.__class__(27700, pv[1])
                v.set_value(pv1)
                # we don't force points to match the implied default!
                self.assertTrue(v.value.srid == 27700)
                # but we will convert raw points to literals with the
                # default SRID
                v.set_value(pv1[1])
                self.assertTrue(v.value.srid == def_srid)
                self.assertTrue(v.value == pv)


class GoodBytes(object):

    def __str__(self):
        return b'HiBytes'

    def __bytes__(self):
        return b'HiBytes'


class BadBytes(object):

    def __str__(self):
        raise ValueError

    def __bytes__(self):
        raise ValueError


class GoodBoolean(BoolMixin):

    def __bool__(self):
        return True


class BadBoolean(BoolMixin):

    def __bool__(self):
        raise ValueError


class GoodStr(UnicodeMixin):

    def __unicode__(self):
        return ul('Hello')


class BadStr(UnicodeMixin):

    def __unicode__(self):
        raise ValueError


class PrimitiveValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all Primitive values"""
        # construct without a property declaration
        v = primitive.PrimitiveValue()
        # this is a NULL value of an unspecified type
        self.assertTrue(isinstance(v, types.Value))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value on construction")
        # the associated type must be the built-in Edm.PrimitiveType
        self.assertTrue(v.type_def is primitive.edm_primitive_type)
        d = {}
        try:
            d[v] = 1
            self.fail("PrimitiveValue hashable")
        except TypeError:
            pass
        # construct a value from the abstract type
        ptype = primitive.edm_primitive_type
        v = ptype()
        self.assertTrue(isinstance(v, primitive.PrimitiveValue))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.do_set(
            primitive.PrimitiveValue,
            good=(),
            bad_values=(),
            bad_types=(True, 0, 'null'))

    def test_all_constructors(self):
        for t, pv, default in ALL_TYPES:
            t_def = t().type_def
            self.assertTrue(isinstance(t_def, primitive.PrimitiveType))
            v = t()
            self.assertTrue(isinstance(v, primitive.PrimitiveValue))
            self.assertFalse(v)
            self.assertTrue(v.is_null())
            self.assertTrue(v.value is None, "Null value on construction")
            self.assertTrue(
                v.type_def is t_def,
                "type_def mismatch %s != %s" % (repr(t), repr(v.type_def)))
            # now construct from the type
            v1 = t_def()
            self.assertTrue(isinstance(v1, type(v)))
            self.assertFalse(v1)
            self.assertTrue(v1.is_null())
            self.assertTrue(v1.value is None, "Null value on construction")
            self.assertTrue(v1.type_def is t_def)
        for t, pv, default in ALL_TYPES:
            t_def = t().type_def
            # null constructor
            v = t()
            self.assertTrue(isinstance(v, primitive.PrimitiveValue))
            self.assertFalse(v)
            self.assertTrue(v.is_null())
            self.assertTrue(v.value is None, "Null value on construction")
            self.assertTrue(v.type_def is t_def)
            # now construct from the type
            v1 = t_def()
            self.assertTrue(isinstance(v1, type(v)))
            self.assertFalse(v1)
            self.assertTrue(v1.is_null())
            self.assertTrue(v1.value is None, "Null value on construction")
            self.assertTrue(v1.type_def is t_def)
            # non-null constructor
            v = t(pv)
            self.assertTrue(v)
            self.assertFalse(v.is_null())
            self.assertTrue(v.value == pv,
                            "Non-null value on construction: %s" % repr(t))
            self.assertTrue(v.type_def is t_def)

    def test_from_value(self):
        v = primitive.PrimitiveValue.from_value(None)
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value from_value")
        self.assertTrue(v.type_def is primitive.edm_primitive_type)
        for t, pv, default in ALL_TYPES:
            if default:
                v = primitive.PrimitiveValue.from_value(pv)
                self.assertTrue(isinstance(v, t), "from_value default type")
            # you can't create a value from an existing value using this
            # method - use an OData operation like cast instead
            try:
                primitive.PrimitiveValue.from_value(t(pv))
                self.fail("from_value(%s) non-null" % repr(t))
            except TypeError:
                pass
            try:
                primitive.PrimitiveValue.from_value(t())
                self.fail("from_value(%s) null" % repr(t))
            except TypeError:
                pass

    def do_set(self, cls, good, bad_values, bad_types):
        type_msg = "%s: " % repr(cls)
        for pv, ov in good:
            value_msg = type_msg + "%s " % repr(pv)
            logging.debug("Checking good value: %s", value_msg)
            v = cls(pv)
            self.assertTrue(v, value_msg + "False")
            self.assertTrue(v.value == ov,
                            value_msg + " == %s" % repr(v.value))
            v.set_value(None)
            self.assertFalse(v)
            self.assertTrue(v.value is None, type_msg + "set_value(None)")
            v.set_value(pv)
            self.assertTrue(v.value == ov,
                            value_msg + " == %s" % repr(v.value))

        for pv in bad_values:
            value_msg = type_msg + "%s " % repr(pv)
            try:
                v = cls(pv)
                self.fail(value_msg + "constructor")
            except ValueError:
                pass
            v = cls()
            try:
                v.set_value(pv)
                self.fail(value_msg + "set_value")
            except ValueError:
                pass
        for pv in bad_types:
            value_msg = type_msg + "%s " % repr(pv)
            try:
                v = cls(pv)
                self.fail(value_msg + "constructor")
            except TypeError:
                pass
            v = cls()
            try:
                v.set_value(pv)
                self.fail(value_msg + "set_value")
            except TypeError:
                pass
        for t, pv, default in ALL_TYPES:
            # you can't create a value from an existing value using this
            # method - use an OData operation like cast instead
            xv = t(pv)
            try:
                v = cls(xv)
                self.fail(type_msg + "constructor(%s) non-null" % repr(t))
            except TypeError:
                pass
            v = cls()
            try:
                v.set_value(xv)
                self.fail("set_value(%s) non-null" % repr(t))
            except TypeError:
                pass

    def do_text(self, cls, test_items):
        type_msg = "%s: " % repr(cls)
        for pv, sv in test_items:
            value_msg = type_msg + "%s " % repr(pv)
            v = cls(pv)
            self.assertTrue(to_text(v) == sv,
                            value_msg + " str -> %s" % repr(to_text(v)))
        v = cls()
        try:
            to_text(v)
            self.fail(type_msg + "text of null")
        except ValueError:
            pass

    def test_binary(self):
        self.do_set(
            primitive.BinaryValue,
            good=((b'Hello', b'Hello'),
                  (b'', b''),
                  (b'null', b'null'),
                  (ul(b'Caf\xe9'), b'Caf\xc3\xa9'),
                  (GoodBytes(), b'HiBytes')),
            bad_values=(BadBytes(), ),
            bad_types=())
        self.do_text(
            primitive.BinaryValue,
            ((b'Hello', 'SGVsbG8='),
             (b'Caf\xc3\xa9', 'Q2Fmw6k='),
             (b'ab?de>g', 'YWI_ZGU-Zw==')))

    def test_boolean(self):
        """Boolean values"""
        self.do_set(
            primitive.BooleanValue,
            good=((True, True),
                  (False, False),
                  (1, True),
                  (0, False),
                  ("", False),
                  ("False", True),
                  ([], False),
                  (GoodBoolean(), True),
                  ),
            bad_values=(BadBoolean(), ),
            bad_types=())
        self.do_text(
            primitive.BooleanValue,
            ((True, 'true'),
             (False, 'false')))

    def test_byte(self):
        """Byte values"""
        self.do_set(
            primitive.ByteValue,
            good=((1, 1),
                  (0, 0),
                  (True, 1),
                  (False, 0),
                  (1.9, 1),
                  (255.9, 255),
                  (255, 255),
                  (-0.9, 0),
                  (Decimal('-0.999'), 0),
                  (long2(100), 100),
                  (Decimal('255.999'), 255),
                  ),
            bad_values=(-1, long2(-1), -1.0, Decimal('-1.0'),
                        256, long2(256), 256.0, Decimal('256.0')),
            bad_types=(GoodBoolean(),))
        self.do_text(
            primitive.ByteValue,
            ((0, '0'), (1, '1'), (255, '255')))
        # check limits
        self.assertTrue(primitive.ByteValue.MAX == 255)
        self.assertTrue(primitive.ByteValue.MIN == 0)

    def test_date(self):
        """Date values"""
        eagle_day = Date.from_str("19690720")
        rome_day = Date.from_str("-07520421", xdigits=0)
        self.do_set(
            primitive.DateValue,
            good=((eagle_day, eagle_day),
                  (datetime.date(1969, 7, 20), eagle_day),
                  (rome_day, rome_day),
                  (datetime.datetime(1969, 7, 20, 20, 17, 40), eagle_day),
                  ),
            bad_values=(Date.from_str("1969-07"),
                        Date.from_str("1969")),
            bad_types=(19690720, 19690720.0, '19690720'))
        self.do_text(
            primitive.DateValue,
            ((eagle_day, '1969-07-20'), (rome_day, '-0752-04-21')))

    def test_date_time_offset(self):
        """DateTimeOffset values"""
        eagle_time = TimePoint.from_str("19690720T201740Z")
        eagle_time_ms = TimePoint.from_str("19690720T201740.000Z")
        eagle_day = TimePoint.from_str("19690720T000000Z")
        future_time = TimePoint.from_str("20190720T201740Z")
        future_unix = future_time.get_unixtime()
        rome_time = TimePoint.from_str("-07520421T160000+0100", xdigits=0)
        leap_actual = TimePoint.from_str("2016-12-31T23:59:60Z")
        leap_adjusted = TimePoint.from_str("2016-12-31T23:59:59Z")
        leap_factual = TimePoint.from_str("2016-12-31T23:59:60.123Z")
        leap_fadjusted = TimePoint.from_str("2016-12-31T23:59:59.999999Z")
        self.do_set(
            primitive.DateTimeOffsetValue,
            good=((eagle_time, eagle_time),
                  (eagle_time_ms, eagle_time),
                  (datetime.datetime(1969, 7, 20, 20, 17, 40), eagle_time),
                  (datetime.date(1969, 7, 20), eagle_day),
                  (rome_time, rome_time),
                  (future_time, future_time),
                  (future_unix, future_time),
                  (long2(future_unix), future_time),
                  (float(future_unix), future_time),
                  (leap_actual, leap_adjusted),
                  (TimePoint.from_str("2016-12-31T24:00:00Z"),
                   TimePoint.from_str("2017-01-01T00:00:00Z"))
                  ),
            bad_values=(TimePoint.from_str("19690720T201740"),
                        TimePoint.from_str("19690720T2017Z"),
                        -1),
            bad_types=('19690720T201740Z'))
        self.do_text(
            primitive.DateTimeOffsetValue,
            ((eagle_time, '1969-07-20T20:17:40Z'),
             (rome_time, '-0752-04-21T16:00:00+01:00'),
             (eagle_time_ms, '1969-07-20T20:17:40.000000Z')))
        # check the correct operation of leap seconds with high precision
        t = primitive.PrimitiveType()
        t.set_base(primitive.edm_date_time_offset)
        t.set_precision(6)
        v = t()
        v.set_value(leap_factual)
        self.assertTrue(v.value == leap_fadjusted)
        v.set_value(eagle_time_ms)
        self.assertTrue(to_text(v) == '1969-07-20T20:17:40.000000Z')

    def test_decimal(self):
        """Decimal values"""
        self.do_set(
            primitive.DecimalValue,
            good=((Decimal(1), Decimal(1)),
                  (1, Decimal(1)),
                  (1.0, Decimal('1.0')),
                  (3.5, Decimal('3.5')),
                  (0, Decimal(0)),
                  (True, Decimal(1)),
                  (False, Decimal(0)),
                  (-1, Decimal(-1)),
                  (long2(100), Decimal(100)),
                  ),
            bad_values=(),
            bad_types=(GoodBoolean(),))
        self.do_text(
            primitive.DecimalValue,
            ((Decimal(0), '0'), (Decimal(1), '1'), (Decimal('1.00'), '1.00'),
             (Decimal(-1), '-1'), (Decimal('3.5'), '3.5')))

    def test_duration(self):
        """Duration values"""
        t12345 = Duration("P1DT2H3M4.5S")
        t1234 = Duration("P1DT2H3M4S")
        # OData only allows Days, Hours, Minutes and Seconds.
        self.do_set(
            primitive.DurationValue,
            good=((t12345, t12345),
                  (t1234, t1234),
                  (Duration("P01DT02H03M04S"), t1234)),
            bad_values=(Duration("P1Y"), Duration("P1M"), Duration("P1W")),
            bad_types=(1, 1.0, Time.from_str("02:03:04.5")))
        # by default, unspecified precision
        self.do_text(
            primitive.DurationValue,
            ((t12345, 'P1DT2H3M4.5S'),
             (t1234, 'P1DT2H3M4S')))
        # check the correct operation of precision
        t = primitive.PrimitiveType()
        t.set_base(primitive.edm_duration)
        t.set_precision(1)
        v = t()
        v.set_value(t12345)
        self.assertTrue(v.value == t12345)
        self.assertTrue(to_text(v) == 'P1DT2H3M4.5S')

    def test_float_value(self):
        """Double and Single values"""
        for cls in (primitive.DoubleValue, primitive.SingleValue):
            self.do_set(
                cls,
                good=((Decimal(1), 1.0),
                      (1, 1.0),
                      (1.0, 1.0),
                      (3.5, 3.5),
                      (0, 0.0),
                      (True, 1.0),
                      (False, 0.0),
                      (-1, -1.0),
                      (long2(100), 100.0),
                      (cls.MAX * 2, float('inf')),
                      (cls.MAX * -2, float('-inf')),
                      (cls.MIN * 2, float('-inf')),
                      (cls.MIN * -2, float('inf')),
                      # nan will never compare equal! no test
                      # (float('nan'), float('nan')),
                      ),
                bad_values=(),
                bad_types=(GoodBoolean(),))
            self.do_text(
                cls,
                ((1.0, '1.0'), (0.0, '0.0'), (-1.0, '-1.0')))

    def test_point(self):
        """Geography and Geometry points"""
        p = geo.Point(1.0, -1.0)
        self.assertTrue(p.x == 1.0)
        self.assertTrue(p.y == -1.0)
        self.assertTrue(p[0] == 1.0)
        self.assertTrue(p[1] == -1.0)
        p = geo.Point(y=-1.0, x=1.0)
        self.assertTrue(p.x == 1.0)
        self.assertTrue(p.y == -1.0)
        self.assertTrue(p[0] == 1.0)
        self.assertTrue(p[1] == -1.0)
        p = geo.Point(1, -1)
        self.assertTrue(isinstance(p.x, float), "force float")
        try:
            p = geo.Point("x", "y")
            self.fail("force float fail")
        except ValueError:
            pass
        # from_arg will accept any iterable
        pa = geo.Point.from_arg(p)
        self.assertTrue(pa == p)
        pa = geo.Point.from_arg((1.0, -1.0))
        self.assertTrue(pa == p)

        def genxy():
            for xy in (1.0, -1.0):
                yield xy

        p = geo.Point.from_arg(genxy())
        self.assertTrue(pa == p)
        # Now on to PointLiteral values...
        p1 = geo.PointLiteral(0, geo.Point(1.0, -1.0))
        p2 = geo.PointLiteral(0, geo.Point(1.5, -1.5))
        p3 = geo.PointLiteral(
            4326, geo.Point(-127.89734578345, 45.234534534))
        try:
            geo.PointLiteral(-1, geo.Point(1.0, -1.0))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (primitive.GeographyPointValue,
                    primitive.GeometryPointValue):
            self.do_set(
                cls,
                good=((p1, p1),
                      (p2, p2),
                      (p3, p3)),
                bad_values=(),
                bad_types=(1.0, ))
            self.do_text(
                cls,
                ((p1, "SRID=0;Point(1 -1)"),
                 (p2, "SRID=0;Point(1.5 -1.5)"),
                 (p3, "SRID=4326;Point(-127.89734578345 45.234534534)"),
                 ))

    def gen_square_ring(self, reverse=False, size=1.0):
        # generates a closed square ring turning anticlockwise
        x = 1.5 * size
        y = -1.5 * size
        n = 5
        while n:
            yield geo.Point(x, y)
            new_x = y if reverse else -y
            y = -x if reverse else x
            x = new_x
            n -= 1

    def gen_spiral(self, n):
        # generates an open line that spirals out
        x = 1.5
        y = -1.5
        while n:
            yield geo.Point(x, y)
            new_x = -1.125 * y
            y = 1.125 * x
            x = new_x
            n -= 1

    def test_line_string(self):
        """Geography and Geometry line strings"""
        l1 = geo.LineStringLiteral(
            0, geo.LineString(((1.0, -1.0), (-1.0, 1.0))))
        l2 = geo.LineStringLiteral(
            0, geo.LineString(((1.5, -1.5), (-1.5, 1.5))))
        l3 = geo.LineStringLiteral(
            4326, geo.LineString(((1.5, -1.5), (1.5, 1.5), (-1.5, 1.5),
                                  (-1.5, -1.5))))
        for arg in [
                (),                     # No points
                (1, 0),                 # Integers, not points
                ((1, 0), ),             # Only 1 point
                (geo.Point(1, 0), ),  # Only 1 point instance
                ]:
            try:
                geo.LineString(arg)
                self.fail("Bad LineString arg: %s" % repr(arg))
            except (ValueError, TypeError):
                pass
        try:
            geo.LineStringLiteral(
                -1, geo.LineString(((1.0, -1.0), (-1.0, 1.0))))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (primitive.GeographyLineStringValue,
                    primitive.GeometryLineStringValue):
            self.do_set(
                cls,
                good=((l1, l1),
                      (l2, l2),
                      (l3, l3),
                      (geo.LineStringLiteral(
                        0, geo.LineString(((30, 10), (10, 30), (40, 40)))),
                       # compares to regular tuple OK
                       (0, ((30, 10), (10, 30), (40, 40)))),
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((l1, "SRID=0;LineString(1 -1,-1 1)"),
                 (l2, "SRID=0;LineString(1.5 -1.5,-1.5 1.5)"),
                 (l3, "SRID=4326;LineString(1.5 -1.5,1.5 1.5,-1.5 1.5,"
                  "-1.5 -1.5)"),
                 ))

    def test_polygon(self):
        """Geography and Geometry polygons"""
        p1 = geo.PolygonLiteral(
            0, geo.Polygon(
                (geo.Ring(
                    (geo.Point(1.5, -1.5), geo.Point(1.5, 1.5),
                     geo.Point(-1.5, 1.5), geo.Point(-1.5, -1.5),
                     geo.Point(1.5, -1.5))), )))
        try:
            geo.PolygonLiteral(-1, p1.polygon)
            self.fail("negative SRID")
        except ValueError:
            pass
        try:
            geo.PolygonLiteral(0, [])
            self.fail("no rings")
        except ValueError:
            pass
        try:
            geo.PolygonLiteral(0, 1.0)
            self.fail("non-iterable rings")
        except TypeError:
            pass
        try:
            geo.Polygon([])
            self.fail("no rings")
        except ValueError:
            pass
        try:
            geo.Ring([geo.Point(1.5, -1.5), geo.Point(1.5, 1.5),
                      geo.Point(-1.5, 1.5), geo.Point(-1.5, -1.5)])
            self.fail("unclosed ring")
        except ValueError:
            pass
        for cls in (primitive.GeographyPolygonValue,
                    primitive.GeometryPolygonValue):
            self.do_set(
                cls,
                good=((p1, p1),
                      ),
                bad_values=(),
                bad_types=(1.0,
                           geo.PointLiteral(0, geo.Point(1.0, -1.0)),
                           geo.LineStringLiteral(
                            4326, (geo.Point(1.5, -1.5),
                                   geo.Point(1.5, 1.5),
                                   geo.Point(-1.5, 1.5),
                                   geo.Point(-1.5, -1.5))), )
                )
            self.do_text(
                cls,
                ((p1, "SRID=0;Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,"
                  "-1.5 -1.5,1.5 -1.5))"),
                 ))

    def test_multi_point(self):
        # a tuple of points
        mp = geo.MultiPoint((geo.Point(1, -1), ))
        self.assertTrue(len(mp) == 1)
        self.assertTrue(mp[0] == (1, -1))
        # can be created from anything that generates points
        mp = geo.MultiPoint(self.gen_spiral(10))
        self.assertTrue(len(mp) == 10)
        self.assertTrue(mp[0] == geo.Point(1.5, -1.5))
        # empty list is OK
        mp = geo.MultiPoint(())
        self.assertTrue(len(mp) == 0)
        # Now move on to the literal
        square = geo.MultiPoint(self.gen_square_ring())
        mp1 = geo.MultiPointLiteral(0, square)
        mp2 = geo.MultiPointLiteral(0, self.gen_square_ring())
        self.assertTrue(mp1 == mp2)
        mp3 = geo.MultiPointLiteral(
            4326, (geo.Point(-127.89734578345, 45.234534534), ))
        try:
            geo.MultiPointLiteral(-1, square)
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (primitive.GeographyMultiPointValue,
                    primitive.GeometryMultiPointValue):
            self.do_set(
                cls,
                good=((mp1, mp1),
                      (mp2, mp2),
                      (mp3, mp3)
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((mp1, "SRID=0;MultiPoint((1.5 -1.5),(1.5 1.5),(-1.5 1.5),"
                  "(-1.5 -1.5),(1.5 -1.5))"),
                 ))

    def test_multi_line_string(self):
        # a tuple of points
        square = geo.LineString(self.gen_square_ring())
        spiral2 = geo.LineString(self.gen_spiral(2))
        mls = geo.MultiLineString((spiral2, ))
        self.assertTrue(len(mls) == 1)
        self.assertTrue(mls[0][0] == (1.5, -1.5))
        # can be created from anything that can be converted to line strings
        mls = geo.MultiLineString((square, ((1, 0), (0, 1))))
        self.assertTrue(len(mls) == 2)
        self.assertTrue(mls[1][0] == (1.0, 0))
        # empty list is OK
        mls = geo.MultiLineString(())
        self.assertTrue(len(mls) == 0)
        # Now move on to the literal
        mls1 = geo.MultiLineStringLiteral(0, (square, ))
        mls2 = geo.MultiLineStringLiteral(0, (self.gen_square_ring(), ))
        self.assertTrue(mls1 == mls2)
        mls3 = geo.MultiLineStringLiteral(
            4326, (self.gen_spiral(5), self.gen_spiral(2)))
        try:
            geo.MultiLineStringLiteral(-1, (square, ))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (primitive.GeographyMultiLineStringValue,
                    primitive.GeometryMultiLineStringValue):
            self.do_set(
                cls,
                good=((mls1, mls1),
                      (mls2, mls2),
                      (mls3, mls3)
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((mls1, "SRID=0;MultiLineString((1.5 -1.5,1.5 1.5,-1.5 1.5,"
                  "-1.5 -1.5,1.5 -1.5))"),
                 (geo.MultiLineStringLiteral(4326, ()),
                  "SRID=4326;MultiLineString()")
                 ))

    def test_multi_polygon(self):
        # a tuple of points
        square1 = geo.Ring(self.gen_square_ring())
        rsquare1 = geo.Ring(self.gen_square_ring(reverse=True, size=0.5))
        square2 = geo.Ring(self.gen_square_ring(size=2))
        rsquare2 = geo.Ring(self.gen_square_ring(reverse=True))
        p1 = geo.Polygon((square1, rsquare1))
        p2 = geo.Polygon((square2, rsquare2))
        mp = geo.MultiPolygon((p1, p2))
        self.assertTrue(len(mp) == 2)
        self.assertTrue(mp[0][0][0] == (1.5, -1.5))
        # can be created from anything that can be converted to Polygon
        mp = geo.MultiPolygon((p1, (square2, )))
        self.assertTrue(len(mp) == 2)
        self.assertTrue(mp[1][0][0] == (3, -3))
        # empty list is OK
        mp = geo.MultiPolygon([])
        self.assertTrue(len(mp) == 0)
        # Now move on to the literal
        mp1 = geo.MultiPolygonLiteral(0, (p1, ))
        mp2 = geo.MultiPolygonLiteral(
            0, [(self.gen_square_ring(),
                 self.gen_square_ring(reverse=True, size=0.5))])
        self.assertTrue(mp1 == mp2, "%s == %s" % (mp1, mp2))
        mp3 = geo.MultiPolygonLiteral(
            4326, geo.MultiPolygon((p2, p1)))
        try:
            geo.MultiPolygonLiteral(-1, (p1, ))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (primitive.GeographyMultiPolygonValue,
                    primitive.GeometryMultiPolygonValue):
            self.do_set(
                cls,
                good=((mp1, mp1),
                      (mp2, mp2),
                      (mp3, mp3)
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((mp1, "SRID=0;MultiPolygon(("
                    "(1.5 -1.5,1.5 1.5,-1.5 1.5,-1.5 -1.5,1.5 -1.5),"
                    "(0.75 -0.75,-0.75 -0.75,-0.75 0.75,0.75 0.75,"
                    "0.75 -0.75)))"),
                 (geo.MultiPolygonLiteral(4326, ()),
                  "SRID=4326;MultiPolygon()")
                 ))

    def test_geo_collection(self):
        c0 = geo.GeoCollection([])
        self.assertTrue(len(c0) == 0)
        p = geo.Point(1.5, -1.5)
        l = geo.LineString(self.gen_spiral(2))
        square = geo.Ring(self.gen_square_ring())
        rsquare = geo.Ring(self.gen_square_ring(reverse=True, size=0.5))
        pg = geo.Polygon((square, rsquare))
        mp = geo.MultiPoint([p])
        ml = geo.MultiLineString([l])
        mpn = geo.MultiPolygon([pg])
        c = geo.GeoCollection([p, l, pg, mp, ml, mpn])
        rc = geo.GeoCollection([c, p])
        self.assertTrue(len(c) == 6)
        self.assertTrue(c[0] == (1.5, -1.5))
        self.assertTrue(rc[0] == c)
        # Now the literal form
        c_lit = geo.GeoCollectionLiteral(0, c)
        rc_lit = geo.GeoCollectionLiteral(0, rc)
        c_lit2 = geo.GeoCollectionLiteral(0, [p, l, pg, mp, ml, mpn])
        self.assertTrue(c_lit == c_lit2)
        try:
            geo.GeoCollectionLiteral(-1, c)
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (primitive.GeographyCollectionValue,
                    primitive.GeometryCollectionValue):
            self.do_set(
                cls,
                good=((c_lit, c_lit),
                      (rc_lit, rc_lit),
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((rc_lit,
                  "SRID=0;Collection("
                  "Collection("
                  "Point(1.5 -1.5),"
                  "LineString(1.5 -1.5,1.6875 1.6875),"
                  "Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,-1.5 -1.5,1.5 -1.5),"
                  "(0.75 -0.75,-0.75 -0.75,-0.75 0.75,0.75 0.75,0.75 -0.75)),"
                  "MultiPoint((1.5 -1.5)),"
                  "MultiLineString((1.5 -1.5,1.6875 1.6875)),"
                  "MultiPolygon(("
                  "(1.5 -1.5,1.5 1.5,-1.5 1.5,-1.5 -1.5,1.5 -1.5),"
                  "(0.75 -0.75,-0.75 -0.75,-0.75 0.75,0.75 0.75,0.75 -0.75)"
                  "))"      # MultiPolygon
                  "),"      # Collection
                  "Point(1.5 -1.5))"),
                 (geo.GeoCollectionLiteral(4326, ()),
                  "SRID=4326;Collection()")
                 ))

    def test_guid(self):
        """Guid values"""
        u1 = uuid.UUID(int=1)
        u2 = uuid.UUID(int=2)
        u3 = uuid.UUID(int=3)
        self.do_set(
            primitive.GuidValue,
            good=((u1, u1),
                  (u2, u2),
                  (u3.bytes, u3),
                  (u3.hex, u3),
                  # from a unicode string (must be hex)
                  (ul('00000000000000000000000000000003'), u3),
                  ),
            bad_values=('00000000-0000-0000-0000-000000000001',
                        ul('00000000-0000-0000-0000-000000000001'),
                        '{00000000-0000-0000-0000-000000000001}',
                        ul('{00000000-0000-0000-0000-000000000001}')),
            bad_types=(GoodBoolean(), 1, 1.0, GoodBytes()))
        self.do_text(
            primitive.GuidValue,
            ((u1, '00000000-0000-0000-0000-000000000001'),
             (u3, '00000000-0000-0000-0000-000000000003'),
             (uuid.UUID(int=3735928559),
              '00000000-0000-0000-0000-0000deadbeef'),
             ))

    def test_string(self):
        """String data"""
        uhello = ul('Hello')
        ucafe = ul(b'Caf\xe9')
        self.do_set(
            primitive.StringValue,
            good=(('Hello', uhello),
                  (ul('Hello'), uhello),
                  (b'Hello', uhello),
                  (ucafe, ucafe),
                  ('', uempty),
                  (ul(''), uempty),
                  (b'', uempty),
                  (True, ul('True')),
                  (1, ul('1')),
                  (3.5, ul('3.5')),
                  (GoodStr(), uhello),
                  ),
            bad_values=(b'Caf\xe9', BadStr()),
            bad_types=())
        self.do_text(
            primitive.StringValue,
            ((uhello, uhello),
             (ucafe, ucafe),
             ))

    def test_time(self):
        """TimeOfDay values"""
        slast = Time.from_str("235959")
        eagle_time = Time.from_str("201740")
        eagle_time_ms = Time.from_str("201740.000")
        self.do_set(
            primitive.TimeOfDayValue,
            good=((slast, slast),
                  (datetime.time(second=10), Time.from_str("000010")),
                  (eagle_time, eagle_time),
                  (eagle_time_ms, eagle_time_ms),
                  (Time.from_str("235960"), Time.from_str("235959")),
                  (Time.from_str("235960.5"),
                   Time.from_str("235959.999999")),
                  (Time.from_str("235960.55"),
                   Time.from_str("235959.999999")),
                  ),
            bad_values=(Time.from_str("2017"),
                        Time.from_str("20"),
                        Time.from_str("201740Z"),
                        Time.from_str("151740Z-0500"),
                        Time.from_str("240000")),
            bad_types=(201740, 201740.0, '201740'))
        self.do_text(
            primitive.TimeOfDayValue,
            ((eagle_time, '20:17:40'), (eagle_time_ms, '20:17:40.000000')))
        # check the correct operation of precision
        t = primitive.PrimitiveType()
        t.set_base(primitive.edm_time_of_day)
        t.set_precision(6)
        v = t()
        v.set_value(Time.from_str("235960.5"))
        self.assertTrue(v.value == Time.from_str("235959.999999"))
        v.set_value(Time.from_str("235960.55"))
        self.assertTrue(v.value == Time.from_str("235959.999999"))
        v.set_value(eagle_time_ms)
        self.assertTrue(v.value == eagle_time_ms)
        self.assertTrue(to_text(v) == '20:17:40.000000')


NUMERIC_TYPES = (
    primitive.ByteValue,
    primitive.DecimalValue,
    primitive.DoubleValue,
    primitive.Int16Value,
    primitive.Int32Value,
    primitive.Int64Value,
    primitive.SByteValue,
    primitive.SingleValue)


class OperatorTests(unittest.TestCase):

    def type_gen(self):
        for t in odata.edm.values():
            yield t

    def value_gen(self):
        for t, pv, default in ALL_TYPES:
            yield t(pv)

    def test_cast(self):
        # the null value can be cast to any type
        for t1 in self.type_gen():
            v1 = t1()
            v1.set_value(None)
            for t2 in self.type_gen():
                # a null instance of type t1 can be cast to t2
                logging.debug("Casting null of type %s to type: %s",
                              str(t1), str(t2))
                v2 = v1.cast(t2)
                self.assertTrue(
                    v2.is_null(), "%s -> %s" %
                    (v1.__class__.__name__, v2.__class__.__name__))
        # primitive types are cast to Edm.String using literal
        # representation used in payloads and WKT for Geo types.
        stype = primitive.edm_string
        for t, pv, default in ALL_TYPES:
            v1 = t(pv)
            v2 = v1.cast(stype)
            self.assertFalse(v2.is_null())
            self.assertTrue(isinstance(v2, primitive.StringValue))
            self.assertTrue(v2.value == str(v1), "%s -> %s" %
                            (repr(v1), repr(v2)))
        # TODO: cast fails if the target type specifies an insufficient
        # MaxLength
        #
        # Numeric primitive types are cast to each other with
        # appropriate rounding.
        for t1 in NUMERIC_TYPES:
            v1 = t1(3.75)
            for t2 in NUMERIC_TYPES:
                # create an instance, easiest way to obtain the type_def
                t2_def = t2().type_def
                v2 = v1.cast(t2_def)
                # should succeed!
                self.assertFalse(v2.is_null(), "%s -> %s is null" %
                                 (repr(v1), repr(v2)))
                if isinstance(v1, primitive.IntegerValue) or \
                        isinstance(v2, primitive.IntegerValue):
                    # appropriate round = truncation to integer
                    self.assertTrue(v2.value == 3, "%s -> %s is %s" %
                                    (repr(v1), repr(v2), str(v2)))
                else:
                    self.assertTrue(str(v2) == '3.75', "%s -> %s is %s" %
                                    (repr(v1), repr(v2), str(v2)))
                # the cast fails if the integer part doesn't fit into
                # the target type
                if isinstance(v2, primitive.DecimalValue):
                    # no max for Decimal
                    continue
                if isinstance(v1, primitive.DecimalValue):
                    # Decimal to something else
                    vmax = t1(Decimal(str(t2.MAX)) * 2)
                    v2 = vmax.cast(t2_def)
                    self.assertTrue(v2.is_null(), "%s -> %s not null" %
                                    (str(vmax), repr(v2)))
                    vmin = t1(Decimal(str(t2.MIN - 1)) * 2)
                    v2 = vmin.cast(t2_def)
                    self.assertTrue(v2.is_null(), "MIN(%s) -> %s not null" %
                                    (repr(vmin), repr(v2)))
                else:
                    if t2.MAX < t1.MAX:
                        vmax = t1(t1.MAX)
                        v2 = vmax.cast(t2_def)
                        self.assertTrue(v2.is_null())
                    if t2.MIN > t1.MIN:
                        vmin = t1(t1.MIN)
                        v2 = vmin.cast(t2_def)
                        self.assertTrue(
                            v2.is_null(), "MIN(%s) -> %s not null" %
                            (repr(vmin), repr(v2)))
        # TODO: Edm.DateTimeOffset, Edm.Duration, and Edm.TimeOfDay
        # values can be cast to the same type with a different precision
        # with appropriate rounding
        #
        # TODO: Structured types are assignable to their type or a
        # direct or indirect base type.
        #
        # TODO: collections are cast item by item
        #
        # TODO: Services MAY support structural casting of entities and
        # complex type instances to a derived type, or arbitrary
        # structured type, by assigning values of identically named
        # properties and casting them recursively. The cast fails if one
        # of the property-value casts fails or the target type contains
        # nonnullable properties that have not been assigned a value.
        #
        # Catch all: if the cast fails the cast function returns null
        for v1 in self.value_gen():
            for t2 in self.type_gen():
                # exclude Primitive -> Primitive of same type
                if isinstance(v1, primitive.PrimitiveValue) and \
                        issubclass(t2.value_type, type(v1)):
                    continue
                # exclude PrimitiveType -> String
                if isinstance(v1, primitive.PrimitiveValue) and \
                        issubclass(t2.value_type, primitive.StringValue):
                    continue
                # exclude Numeric -> Numeric
                if isinstance(v1, primitive.NumericValue) and \
                        issubclass(t2.value_type, primitive.NumericValue):
                    continue
                if isinstance(v1, primitive.PrimitiveValue) or \
                        issubclass(t2.value_type, primitive.PrimitiveValue):
                    # primitive -> structured/collection
                    # structured/collection -> primitive
                    logging.debug("Casting value of %s to type: %s",
                                  str(t1), str(t2))
                    v2 = v1.cast(t2)
                    self.assertTrue(v2.is_null(), "%s -> %s not null" %
                                    (repr(v1), repr(v2)))
                else:
                    self.fail("Unexpected cast: %s to %s" %
                              (repr(v1), repr(t2)))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
