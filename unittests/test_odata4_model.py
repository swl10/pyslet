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
import pyslet.odata4.geotypes as geo
import pyslet.odata4.model as odata
from pyslet.py2 import (
    BoolMixin,
    long2,
    to_text,
    u8,
    uempty,
    ul,
    UnicodeMixin,
    )
from pyslet.xml.xsdatatypes import Duration


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(NamedTests, 'test'),
        unittest.makeSuite(NameTableTests, 'test'),
        unittest.makeSuite(SchemaTests, 'test'),
        unittest.makeSuite(NominalTypeTests, 'test'),
        unittest.makeSuite(PrimitiveTypeTests, 'test'),
        unittest.makeSuite(StructuredTypeTests, 'test'),
        unittest.makeSuite(CollectionTests, 'test'),
        unittest.makeSuite(EnumerationTests, 'test'),
        unittest.makeSuite(ValueTests, 'test'),
        unittest.makeSuite(PrimitiveValueTests, 'test'),
        unittest.makeSuite(OperatorTests, 'test'),
        unittest.makeSuite(ParserTests, 'test')
        ))


class NamedTests(unittest.TestCase):

    def test_constructor(self):
        n = odata.Named()
        self.assertTrue(n.name is None)
        self.assertTrue(n.nametable is None)
        try:
            n.get_qualified_name()
            self.fail("check_name implemented")
        except NotImplementedError:
            pass


class NameTableTests(unittest.TestCase):

    def setUp(self):        # noqa

        class MockSchema(odata.NameTable):

            def check_name(self, name):
                pass

            def check_value(self, value):
                pass

        self.mock_ns = MockSchema()

    def test_constructor(self):
        ns = odata.NameTable()
        # abstract class...
        n = odata.Named()
        n.name = "Hello"
        try:
            ns["Hello"] = n
            self.fail("check_name and check_value implemented")
        except NotImplementedError:
            pass
        # same result if we try and declare something
        try:
            n.declare(ns)
            self.fail("Named.declare in abstract name space")
        except NotImplementedError:
            pass

    def test_simple_identifier(self):
        good = ("Hello",
                ul(b"Caf\xe9"),
                ul(b'\xe9faC'),
                u8(b'\xe3\x80\x87h'),
                "_Hello",
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_"
                )
        bad = ("45", "M'", "M;", "M=", "M\\", "M.N", "M+", "M-", "M*",
               "M/", "M<", "M>", "M=", "M~", "M!", "M@", "M#", "M%",
               "M^", "M&", "M|", "M`", "M?", "M(", "M)", "M[", "M]",
               "M,", "M;", "M*", "M.M", "",
               "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
               "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
               "LongOne_LongOne_L")
        for s in good:
            self.assertTrue(odata.NameTable.is_simple_identifier(s),
                            "%s failed" % repr(s))
        for s in bad:
            self.assertFalse(odata.NameTable.is_simple_identifier(s),
                             "%s failed" % repr(s))

    def test_set_item(self):
        x = object()
        y = object()
        z = object()
        self.assertTrue(len(self.mock_ns) == 0)
        self.assertFalse(self.mock_ns.closed)
        self.mock_ns["Hello"] = x
        self.assertTrue(self.mock_ns["Hello"] is x)
        try:
            self.mock_ns["Hello"] = y
            self.fail("Name redeclared")
        except odata.DuplicateNameError:
            pass
        try:
            del self.mock_ns["Hello"]
            self.fail("Name undeclared")
        except odata.UndeclarationError:
            pass
        self.mock_ns["Bye"] = y
        self.assertTrue(len(self.mock_ns) == 2)
        self.mock_ns.close()
        self.assertTrue(self.mock_ns.closed)
        try:
            self.mock_ns["Ciao"] = z
            self.fail("Declartion in closed NameTable")
        except odata.NameTableClosed:
            pass

    def test_tell(self):
        class Callback(object):

            def __init__(self):
                self.call_count = 0
                self.last_value = None

            def __call__(self, value):
                self.call_count += 1
                self.last_value = value

        c = Callback()
        self.assertTrue(c.call_count == 0)
        x = object()
        y = object()
        self.mock_ns["Hello"] = x
        self.mock_ns.tell("Hello", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        self.mock_ns.tell("Bye", c)
        self.mock_ns.tell("Ciao", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        self.mock_ns["Bye"] = y
        self.assertTrue(c.call_count == 2)
        self.assertTrue(c.last_value is y)
        self.mock_ns.close()
        self.assertTrue(c.call_count == 3)
        self.assertTrue(c.last_value is None)

    def test_tell_close(self):
        class Callback(object):

            def __init__(self):
                self.call_count = 0

            def __call__(self):
                self.call_count += 1

        c = Callback()
        x = object()
        self.mock_ns.tell_close(c)
        self.mock_ns.tell_close(c)
        self.mock_ns["Ciao"] = x
        self.assertTrue(c.call_count == 0)
        self.mock_ns.close()
        self.assertTrue(c.call_count == 2)


class SchemaTests(unittest.TestCase):

    def test_constructor(self):
        ns = odata.Schema()
        self.assertTrue(len(ns) == 0, "no definitions on init")

    def test_checks(self):
        ns = odata.Schema()
        n = odata.Named()
        try:
            ns["Hello"] = n
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        n = odata.NominalType()
        try:
            n.declare(ns)
            self.fail("Named.declare with no name")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            self.fail("check_name with None")
        except ValueError:
            pass
        n.name = "+Hello"
        try:
            n.declare(ns)
            self.fail("Named.declare with bad name")
        except ValueError:
            pass
        n.name = "_Hello"
        try:
            n.declare(ns)
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")
        # you can't declare something twice
        try:
            n.declare(ns)
            self.fail("NominalType redeclared (same namespace)")
        except odata.ObjectRedclared:
            pass
        ns2 = odata.Schema()
        try:
            n.declare(ns2)
            self.fail("NominalType redeclared (different namespace)")
        except odata.ObjectRedclared:
            pass

    def test_qname(self):
        ns = odata.Schema()
        n = odata.NominalType()
        n.name = "Hello"
        # if the schema has no name, there is no qualified name
        n.declare(ns)
        self.assertTrue(n.qname is None)
        self.assertTrue(n.nametable() is not None)
        self.assertTrue(n.is_owned_by(ns))
        # if we delete the schema we should lose the link
        del ns
        self.assertTrue(n.nametable is not None)
        self.assertTrue(n.nametable() is None)
        # we are still not allowed to redeclare
        ns2 = odata.Schema()
        ns2.name = "my.namespace"
        try:
            n.declare(ns2)
            self.fail("NominalType redeclared (after ns del)")
        except odata.ObjectRedclared:
            pass
        n = odata.NominalType()
        n.name = "Hello"
        n.declare(ns2)
        self.assertTrue(n.qname == "my.namespace.Hello")

    def test_edm(self):
        # There should be a default Edm Schema
        self.assertTrue(isinstance(odata.edm, odata.Schema))
        self.assertTrue(odata.edm.name == "Edm")
        self.assertTrue(len(odata.edm) == 36, sorted(odata.edm.keys()))


class AnnotationsTests(unittest.TestCase):

    def test_constructors(self):
        atable = odata.Annotations()
        self.assertTrue(len(atable) == 0, "No annotations initially")
        a = odata.Annotation()
        # annotation is itself a nametable keyed on qualifier
        self.assertTrue(len(a) == 0, "No qualified annotations initially")
        self.assertTrue(a.name is None)     # the qualified name of the term
        qa = odata.QualifiedAnnotation()
        self.assertTrue(qa.name is None)    # the (optional) qualifier
        self.assertTrue(qa.term is None)    # the defining term

    def test_qualified_checks(self):
        a = odata.Annotation()
        # name must be a qualifier (simple identifier), type is
        # QualifiedAnnotation
        qa = odata.NominalType()
        try:
            a["Tablet"] = qa
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        qa = odata.QualifiedAnnotation()
        try:
            qa.declare(a)
            self.fail("QualifiedAnnotation.declare with no name")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            self.fail("check_name with None")
        except ValueError:
            pass
        qa.name = "+Tablet"
        try:
            qa.declare(a)
            self.fail("QualifiedAnnotation.declare with bad name")
        except ValueError:
            pass
        qa.name = "Tablet"
        try:
            qa.declare(a)
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")

    def test_annotation_checks(self):
        aa = odata.Annotations()
        # name must be a qualified name, type is Annotation
        a = odata.NominalType()
        try:
            aa["Vocab.Description"] = a
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        a = odata.Annotation()
        try:
            a.declare(aa)
            self.fail("Annotation.declare with no name")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            self.fail("check_name with None")
        except ValueError:
            pass
        a.name = "Description"
        try:
            a.declare(aa)
            self.fail("Annotation.declare with bad name")
        except ValueError:
            pass
        a.name = "Vocab.Description"
        try:
            a.declare(aa)
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")

    def test_declare(self):
        term = odata.Term()
        term.name = "Description"
        # mock declaration in the "Vocab" namespace
        term.qname = "Vocab.Description"
        aa = odata.Annotations()
        # check that we can apply a qualified term directly
        qa = odata.QualifiedAnnotation()
        qa.term = term
        qa.name = "Tablet"
        qa.qualified_declare(aa)
        self.assertTrue(len(aa) == 1)
        self.assertTrue(len(aa['Vocab.Description']) == 1)
        self.assertTrue(aa['Vocab.Description']['Tablet'] is qa)
        # an unqualified name goes in with an empty string qualifier
        uqa = odata.QualifiedAnnotation()
        uqa.term = term
        uqa.name = None     # automatically declared as ""
        uqa.qualified_declare(aa)
        self.assertTrue(len(aa) == 1)
        self.assertTrue(len(aa['Vocab.Description']) == 2)
        self.assertTrue(aa['Vocab.Description'][''] is uqa)
        # you can't declare a qualified name twice
        dqa = odata.QualifiedAnnotation()
        dqa.name = "Tablet"
        dqa.term = term
        try:
            dqa.qualified_declare(aa)
            self.fail("Duplicate qualified annotation")
        except odata.DuplicateNameError:
            pass
        # test the lookup
        self.assertTrue(len(aa['Vocab.Description']) == 2)
        self.assertTrue(aa.qualified_get('Vocab.Description') is uqa)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Tablet') is qa)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Phone') is None)


class EntityModelTests(unittest.TestCase):

    def test_constructor(self):
        em = odata.EntityModel()
        self.assertTrue(len(em) == 1, "Predefined Edm schema")
        self.assertTrue("Edm" in em)

    def test_namespace(self):
        em = odata.EntityModel()
        good = ("Edm",
                "Some.Vocabulary.V1",
                "Hello",
                ul(b"Caf\xe9"),
                ul(b'\xe9faC'),
                u8(b'\xe3\x80\x87h'),
                "_Hello",
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_",
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_."
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
                "LongOne_LongOne_",
                "M.M"
                )
        bad = ("45", "M'", "M;", "M=", "M\\", "M.", "M+", "M-", "M*",
               "M/", "M<", "M>", "M=", "M~", "M!", "M@", "M#", "M%",
               "M^", "M&", "M|", "M`", "M?", "M(", "M)", "M[", "M]",
               "M,", "M;", "M*", "", None,
               "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
               "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
               "LongOne_LongOne_L."
               "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
               "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
               "LongOne_LongOne_"
               )
        for s in good:
            try:
                em.check_name(s)
            except ValueError:
                self.fail("%s failed" % repr(s))
        for s in bad:
            try:
                em.check_name(s)
                self.fail("%s failed" % repr(s))
            except ValueError:
                pass

    def test_entitymodel_declare(self):
        em = odata.EntityModel()
        em.name = "Test"
        # abstract class...
        ns = odata.Schema()
        # This should work fine!
        em["Hello"] = ns
        self.assertTrue(ns.name is None, "Alias declaration OK")
        self.assertTrue(em["Hello"] is ns, "Can look-up value")
        try:
            em["+Hello"] = ns
            self.fail("check_name failed")
        except ValueError:
            pass
        ns.name = "Some.Vocabulary."
        try:
            ns.declare(em)
            self.fail("Schema.declare with bad name")
        except ValueError:
            pass
        ns.name = "Some.Vocabulary.V1"
        ns.declare(em)
        self.assertTrue(len(em) == 3)
        self.assertTrue(ns.nametable is not None, "nametable set on declare")
        self.assertTrue(ns.nametable() is em, "nametable callable (weakref)")

    def test_tell(self):
        class Callback(object):

            def __init__(self):
                self.call_count = 0
                self.last_value = None

            def __call__(self, value):
                self.call_count += 1
                self.last_value = value

        c = Callback()
        self.assertTrue(c.call_count == 0)
        em = odata.EntityModel()
        nsx = odata.Schema()
        nsx.name = "com.example._X"
        nsy = odata.Schema()
        nsy.name = "_Y"
        x = odata.NominalType()
        x.name = "x"
        x.declare(nsx)
        y = odata.NominalType()
        y.name = "y"
        y.declare(nsy)
        z = odata.NominalType()
        z.name = "z"
        nsx.declare(em)
        em.qualified_tell("com.example._X.x", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        em.qualified_tell("com.example._X.z", c)
        em.qualified_tell("_Y.y", c)
        em.qualified_tell("_Y.ciao", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        z.declare(nsx)
        self.assertTrue(c.call_count == 2)
        self.assertTrue(c.last_value is z)
        nsy.declare(em)
        self.assertTrue(c.call_count == 3)
        self.assertTrue(c.last_value is y)
        em.close()
        self.assertTrue(c.call_count == 4)
        self.assertTrue(c.last_value is None)


class NominalTypeTests(unittest.TestCase):

    def test_constructor(self):
        n = odata.NominalType()
        self.assertTrue(n.base is None)
        # callable, returns a null of type n
        v = n()
        self.assertTrue(isinstance(v, odata.Value))
        self.assertTrue(v.type_def is n)
        self.assertTrue(v.is_null())

    def test_namespace_declare(self):
        ns = odata.Schema()
        ns.name = "Test"
        # abstract class...
        n = odata.NominalType()
        # This should work fine!
        ns["Hello"] = n
        self.assertTrue(n.name is None, "Alias declaration OK")
        self.assertTrue(ns["Hello"] is n, "Can look-up value")
        try:
            ns["+Hello"] = n
            self.fail("check_name failed")
        except ValueError:
            pass
        n.name = "+Hello"
        try:
            n.declare(ns)
            self.fail("Named.declare with bad name")
        except ValueError:
            pass
        n.name = "_Hello"
        n.declare(ns)
        self.assertTrue(len(ns) == 2)
        self.assertTrue(n.nametable is not None, "nametable set on declare")
        self.assertTrue(n.nametable() is ns, "nametable callable (weakref)")

    def test_abstract_types(self):
        # Edm namespace should contain the abstract types
        t1 = odata.edm['PrimitiveType']
        self.assertTrue(t1.name == 'PrimitiveType')
        try:
            odata.edm['Primitivetype']
            self.fail('case insensitive namespace look-up')
        except KeyError:
            pass
        t2 = odata.edm['ComplexType']
        self.assertTrue(t2.name == 'ComplexType')
        self.assertTrue(t1 is not t2)
        t3 = odata.edm['EntityType']
        self.assertTrue(t3.name == 'EntityType')
        self.assertTrue(t1 is not t3)
        self.assertTrue(t2 is not t3)


ALL_TYPES = (
    # Value type, example value, True if it is the default value type
    # for this example value
    (odata.BinaryValue, b'3.14', True),
    (odata.BooleanValue, True, True),
    (odata.ByteValue, 3, False),
    (odata.DateValue, Date(), True),
    (odata.DateTimeOffsetValue, TimePoint().with_zone(0), True),
    (odata.DecimalValue, Decimal('3.14'), True),
    (odata.DoubleValue, 3.14, True),
    (odata.DurationValue, Duration(), True),
    (odata.GuidValue, uuid.UUID(int=3), True),
    (odata.Int16Value, 3, False),
    (odata.Int32Value, 3, False),
    (odata.Int64Value, 3, True),
    (odata.SByteValue, 3, False),
    (odata.SingleValue, 3.14, False),
    # odata.StreamValue is handled specially
    (odata.StringValue, ul('3.14'), True),
    (odata.TimeOfDayValue, Time(), True),
    # odata.Geography is abstract
    (odata.GeographyPointValue, geo.PointLiteral(
        srid=4326, point=geo.Point(-1.00244140625, 51.44775390625)), True),
    (odata.GeographyLineStringValue, geo.LineStringLiteral(
        srid=4326, line_string=geo.LineString(
            ((-1.00244140625, 51.44775390625),
             (-0.9964599609375, 51.455810546875)))), True),
    (odata.GeographyPolygonValue, geo.PolygonLiteral(
        srid=4326, polygon=geo.Polygon(
            (((-1.003173828125, 51.439697265625),
              (-1.0029296875, 51.4437255859375),
              (-1.001708984375, 51.4437255859375),
              (-1.001708984375, 51.439697265625),
              (-1.003173828125, 51.439697265625)),
             ))), True),
    (odata.GeographyMultiPointValue, geo.MultiPointLiteral(
        srid=4326, multipoint=(
            geo.Point(-1.00244140625, 51.44775390625),
            geo.Point(-0.9964599609375, 51.455810546875))), True),
    (odata.GeographyMultiLineStringValue, geo.MultiLineStringLiteral(
        srid=4326, multi_line_string=(
            geo.LineString(((-1.00244140625, 51.44775390625),
                            (-0.9964599609375, 51.455810546875))),
            )), True),
    (odata.GeographyMultiPolygonValue, geo.MultiPolygonLiteral(
        srid=4326, multi_polygon=(
            geo.Polygon((((-1.003173828125, 51.439697265625),
                          (-1.0029296875, 51.4437255859375),
                          (-1.001708984375, 51.4437255859375),
                          (-1.001708984375, 51.439697265625),
                          (-1.003173828125, 51.439697265625)),
                         )),
            )), True),
    (odata.GeographyCollectionValue, geo.GeoCollectionLiteral(
        srid=4326, items=(
            geo.Point(-1.00244140625, 51.44775390625),
            geo.LineString(((-1.00244140625, 51.44775390625),
                            (-0.9964599609375, 51.455810546875)))
            )), True),
    # odata.Geometry is abstract
    (odata.GeometryPointValue, geo.PointLiteral(
        srid=0, point=geo.Point(1.0, -1.0)), True),
    (odata.GeometryLineStringValue, geo.LineStringLiteral(
        srid=0, line_string=geo.LineString(
            ((1.0, -1.0), (-1.0, 1.0)))), True),
    (odata.GeometryPolygonValue, geo.PolygonLiteral(
        srid=0, polygon=geo.Polygon(
            (((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0),
              (1.0, -1.0)), ))), True),
    (odata.GeometryMultiPointValue, geo.MultiPointLiteral(
        srid=0, multipoint=(
            geo.Point(1.0, -1.0), geo.Point(-1.0, 1.0))), True),
    (odata.GeometryMultiLineStringValue, geo.MultiLineStringLiteral(
        srid=0, multi_line_string=(
            geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
            geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
            )), True),
    (odata.GeometryMultiPolygonValue, geo.MultiPolygonLiteral(
        srid=0, multi_polygon=(
            geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                          (-1.0, -1.0), (1.0, -1.0)), )),
            geo.Polygon((((4.0, -1.0), (4.0, 1.0), (2.0, 1.0),
                          (2.0, -1.0), (4.0, -1.0)), ))
            )), True),
    (odata.GeometryCollectionValue, geo.GeoCollectionLiteral(
        srid=0, items=(
            geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
            geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
            geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                          (-1.0, -1.0), (1.0, -1.0)), )),
            )), True)
    )


class PrimitiveTypeTests(unittest.TestCase):

    def test_constructor(self):
        t = odata.PrimitiveType()
        self.assertTrue(t.base is None, "No base by default")
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # callable, returns a null of PrimitiveValue
        v = t()
        self.assertTrue(isinstance(v, odata.PrimitiveValue))
        self.assertTrue(v.type_def is t)
        self.assertTrue(v.is_null())

    def test_max_length_binary(self):
        # For binary or stream properties this is the octet length of
        # the binary data
        t = odata.edm['Binary']
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # create a derived class with max_length
        t1 = odata.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # max_length is None, unknown restriction
        v = t1()
        self.assertTrue(isinstance(v, odata.BinaryValue))
        v.set(b'Hello')
        # max_length is 3
        t1.set_max_length(3)
        v = t1()
        try:
            v.set(b'Hello')
            self.fail("Would truncate")
        except ValueError:
            pass
        v.set(b'Hel')
        # 0 => max size, treated the same as None in our case
        t1.set_max_length(0)
        v = t1()
        v.set(b'Hello')

    def test_max_length_stream(self):
        # TODO
        pass

    def test_max_length_string(self):
        cafe = ul('Caf\xe9')
        t = odata.edm['String']
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # create a derived class with max_length
        t1 = odata.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # max_length is None, unknown restriction
        v = t1()
        self.assertTrue(isinstance(v, odata.StringValue))
        v.set(cafe)
        # max_length is 3
        t1.set_max_length(4)
        v = t1()
        v.set(cafe)     # OK as character length is 4, utf8 length check
        t1.set_max_length(3)
        try:
            v.set(cafe)
            self.fail("Would truncate")
        except ValueError:
            pass
        v.set(cafe[1:])
        # 0 => max size, treated the same as None in our case
        t1.set_max_length(0)
        v = t1()
        v.set(cafe)

    def test_precision_datetimeoffset(self):
        """For a temporal property the value of this attribute specifies
        the number of decimal places allowed in the seconds portion of
        the property's value..."""
        dt20 = TimePoint.from_str("2017-06-05T20:44:14.12345678901234567890Z")
        t = odata.edm['DateTimeOffset']
        self.assertTrue(t.precision == 6, "Default Precision")
        # create a derived class (does not inherit precision)
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.DateTimeOffsetValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14Z")
        self.assertFalse(v.value == dt20)
        t1.set_precision(6)
        v = t1()
        v.set(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14.123456Z",
                        v.value.time.second)
        self.assertFalse(v.value == dt20)
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except ValueError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14.123456789012Z")
        self.assertFalse(v.value == dt20)

    def test_precision_duration(self):
        d20 = Duration("PT0.12345678901234567890S")
        t = odata.edm['Duration']
        self.assertTrue(t.precision == 6, "Default Precision")
        # create a derived class with precision
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.DurationValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set(d20)
        self.assertTrue(v.value == "PT0S", str(v.value))
        self.assertFalse(v.value == d20)
        t1.set_precision(6)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == "PT0.123456S")
        self.assertFalse(v.value == d20)
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except ValueError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == "PT0.123456789012S")
        self.assertFalse(v.value == d20)

    def test_precision_timeofday(self):
        t20 = Time.from_str("20:44:14.12345678901234567890")
        t = odata.edm['TimeOfDay']
        self.assertTrue(t.precision == 6, "Default Precision")
        # create a derived class with precision
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.TimeOfDayValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set(t20)
        self.assertTrue(v.value == "20:44:14")
        self.assertFalse(v.value == t20)
        t1.set_precision(6)
        v = t1()
        v.set(t20)
        self.assertTrue(v.value == "20:44:14.123456")
        self.assertFalse(v.value == t20)
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except ValueError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set(t20)
        self.assertTrue(v.value == "20:44:14.123456789012")
        self.assertFalse(v.value == t20)

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
        t = odata.edm['Decimal']
        self.assertTrue(t.precision is None, "No Precision by default")
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.DecimalValue))
        # If no value is specified, the decimal property has unspecified
        # precision.  Python's default of 28 is larger than the 20 used
        # in these tests.  The scale property, however, defaults to 0!
        v.set(d20)
        self.assertTrue(v.value == Decimal("0"))
        v.set(i20)
        self.assertTrue(v.value == i20)
        v.set(f20)
        self.assertTrue(v.value == Decimal("1234567890"))
        # a specified precision, scale defaults to 0
        t1.set_precision(6)
        v = t1()
        # these results should be rounded
        v.set(d20)
        self.assertTrue(v.value == Decimal("0"))
        self.assertFalse(v.value == d20)
        try:
            v.set(i20)
            self.fail("Integer larger than precision")
        except ValueError:
            pass
        # a specified precision with a variable scale
        t1.set_precision(6, -1)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == Decimal("0.123457"))
        v.set(i20)
        self.assertTrue(v.value == Decimal("12345700000000000000"))
        v.set(f20)
        self.assertTrue(v.value == Decimal("1234570000"))
        # if we exceed the digits we had originally we do not add 0s as
        # this is a maximum number of digits, not an absolute number of
        # digits.
        t1.set_precision(42, 21)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == d20)
        self.assertTrue(str(v) == d20str, str(v))
        v.set(i20)
        self.assertTrue(v.value == i20)
        self.assertTrue(str(v) == i20str, str(v))
        v.set(f20)
        self.assertTrue(v.value == f20)
        self.assertTrue(str(v) == f20str, str(v))
        # Unspecified precision, variable scale (uses -1)
        # sig fig limited by python defaults, decimal places unlimited
        t1.set_precision(None, -1)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == d20)
        self.assertTrue(str(v) == d20str, str(v))
        v.set(i20)
        self.assertTrue(v.value == i20)
        self.assertTrue(str(v) == i20str, str(v))
        v.set(f20)
        self.assertTrue(v.value == f20)
        self.assertTrue(str(v) == f20str, str(v))
        # unspecified precision, scale is OK
        t1.set_precision(None, 3)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == Decimal("0.123"))
        v.set(i20)
        self.assertTrue(v.value == i20)
        v.set(f20)
        self.assertTrue(v.value == Decimal("1234567890.123"))
        try:
            t1.set_precision(2, 3)
            self.fail("scale must be <= precision")
        except ValueError:
            pass
        # try scale > 0
        t1.set_precision(6, 3)
        v = t1()
        v.set(d20)
        # scale beats precision
        self.assertTrue(v.value == Decimal("0.123"))
        try:
            v.set(i20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        v.set(Decimal("123.4567"))
        self.assertTrue(v.value == Decimal("123.457"))
        # try scale = 0
        t1.set_precision(6, 0)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == Decimal("0"))
        try:
            v.set(f20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        # try scale = precision
        t1.set_precision(6, 6)
        v = t1()
        v.set(d20)
        self.assertTrue(v.value == Decimal("0.123457"))
        try:
            v.set(1)
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
        v.set(Decimal(xstr))
        self.assertTrue(v.value == Decimal(xstr[:-2] + "00"))

    def test_unicode_string(self):
        cafe = ul('Caf\xe9')
        t = odata.edm['String']
        self.assertTrue(t.unicode is True, "Unicode by default")
        t1 = odata.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # Unicode is None, same as False
        v = t1()
        self.assertTrue(isinstance(v, odata.StringValue))
        v.set(cafe)
        t1.set_unicode(False)
        v = t1()
        try:
            v.set(cafe)
            self.fail("ASCII required")
        except ValueError:
            pass
        v.set(cafe[:-1])    # OK
        t1.set_unicode(True)
        v = t1()
        v.set(cafe)

    def test_srid_geo(self):
        for t, pv, default in ALL_TYPES:
            if issubclass(t, (odata.GeographyValue, odata.GeometryValue)):
                edm_type = odata.edm[t.edm_name]
                self.assertTrue(edm_type.value_type is t)
                self.assertTrue(edm_type.srid is None)
                t1 = odata.PrimitiveType()
                t1.set_base(edm_type)
                # value_type inherited from edm_type
                self.assertTrue(t1.value_type is edm_type.value_type)
                self.assertTrue(t1.srid is None)
                v = t1()
                self.assertTrue(isinstance(v, t))
                v.set(pv)
                if issubclass(t, odata.GeographyValue):
                    def_srid = 4326
                else:
                    def_srid = 0
                self.assertTrue(v.value.srid == def_srid)
                # make up a similar value with a different srid
                pv1 = pv.__class__(6832, pv[1])
                v.set(pv1)
                # we don't force points to match the implied default!
                self.assertTrue(v.value.srid == 6832)
                # but we will convert raw points to literals with the
                # default SRID
                v.set(pv1[1])
                self.assertTrue(v.value.srid == def_srid)
                self.assertTrue(v.value == pv)


class StructuredTypeTests(unittest.TestCase):

    def test_constructors(self):
        # structured types are composed of structural properties they
        # are themselves name tables!
        t = odata.StructuredType()
        # abstract class
        self.assertTrue(isinstance(t, odata.NominalType),
                        "structured types are nominal types")
        self.assertTrue(isinstance(t, odata.NameTable),
                        "structured types define scope")
        it = odata.PrimitiveType()
        p = odata.Property(it)
        self.assertTrue(isinstance(p, odata.Named), "properties are nameable")

    def test_declare(self):
        t = odata.StructuredType()
        # they require properties with simple identifier names
        n = odata.NominalType()
        n.name = "Dimension"
        try:
            n.declare(t)
            self.fail("NominalType declared in StructuredType")
        except TypeError:
            pass
        it = odata.PrimitiveType()
        p = odata.Property(it)
        p.name = "Max.Dimension"
        try:
            p.declare(t)
            self.fail("Property declared with bad name")
        except ValueError:
            pass
        p.name = "Dimension"
        p.declare(t)
        np = odata.NavigationProperty()
        np.name = "Related"
        np.declare(t)
        self.assertTrue(t["Dimension"] is p)
        self.assertTrue(t["Related"] is np)


class CollectionTests(unittest.TestCase):

    def test_constructor(self):
        # collection types are collection wrappers for some other
        # primitive, complex or enumeration type.
        it = odata.PrimitiveType()
        t = odata.CollectionType(it)
        self.assertTrue(isinstance(t, odata.NominalType),
                        "Collection types are nominal types")
        self.assertTrue(t.item_type is it,
                        "Collection types must have an item type")

    def test_value(self):
        it = odata.PrimitiveType()
        t = odata.CollectionType(it)
        # types are callable to obtain values
        v = t()
        self.assertTrue(isinstance(v, odata.CollectionValue))
        # never null
        self.assertTrue(v)
        self.assertFalse(v.is_null())


class EnumerationTests(unittest.TestCase):

    def test_constructor(self):
        # enumeration types are wrappers for one of a limited number of
        # integer types: Edm.Byte, Edm.SByte, Edm.Int16, Edm.Int32, or
        # Edm.Int64 - defaulting to Edm.Int32
        et = odata.EnumerationType()
        self.assertTrue(isinstance(et, odata.NominalType),
                        "Enumeration types are nominal types")
        self.assertTrue(isinstance(et, odata.NameTable),
                        "Enumeration types define scope for members")
        self.assertTrue(et.base is odata.edm['Int32'],
                        "Default base type is Int32")
        self.assertTrue(et.assigned_values is None,
                        "Whether or not")
        self.assertTrue(et.is_flags is False, "Default to no flags")
        self.assertTrue(isinstance(et.members, list), "Members type")
        self.assertTrue(len(et.members) == 0, "No Members")
        for base in ('Byte', 'SByte', 'Int16', 'Int32', 'Int64'):
            et = odata.EnumerationType(odata.edm[base])
            self.assertTrue(et.base is odata.edm[base])
        for base in ('Binary', 'String', 'Guid', 'Double', 'Decimal'):
            try:
                et = odata.EnumerationType(odata.edm[base])
                self.fail("EnumerationType(%s) should fail" % base)
            except ValueError:
                pass

    def test_declare(self):
        et = odata.EnumerationType()
        # they require Members with simple identifier names
        n = odata.NominalType()
        n.name = "Dimension"
        try:
            n.declare(et)
            self.fail("NominalType declared in EnumerationType")
        except TypeError:
            pass
        m = odata.Member()
        m.name = "Game.Rock"
        try:
            m.declare(et)
            self.fail("Member declared with bad name")
        except ValueError:
            pass
        m.name = "Rock"
        m.declare(et)

    def test_auto_members(self):
        et = odata.EnumerationType()
        m0 = odata.Member()
        m0.name = "Rock"
        self.assertTrue(m0.value is None, "No value by default")
        m0.declare(et)
        self.assertTrue(et.assigned_values is True)
        self.assertTrue(len(et.members) == 1)
        self.assertTrue(et.members[0] is m0)
        self.assertTrue(et['Rock'] is m0)
        self.assertTrue(m0.value == 0, "Auto-assigned starts at 0")
        m1 = odata.Member()
        m1.name = "Paper"
        m1.declare(et)
        self.assertTrue(m1.value == 1, "Auto-assigned 1")
        m2 = odata.Member()
        m2.name = "Scissors"
        m2.value = 2
        try:
            m2.declare(et)
            self.fail("Can't declare value with auto-assigned enum")
        except odata.ModelError:
            pass
        m2.value = None
        m2.declare(et)
        self.assertTrue(m2.value == 2)

    def test_auto_value(self):
        et = odata.EnumerationType()
        for n in ("Rock", "Paper", "Scissors"):
            m = odata.Member()
            m.name = n
            m.declare(et)
        v = et()
        self.assertTrue(isinstance(v, odata.EnumerationValue))
        # is null
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        # we can set from string
        v.set("Rock")
        self.assertTrue(v.value == 0)
        try:
            v.set("Red")
            self.fail("Bad enumeration string")
        except ValueError:
            pass
        # can't set multiple values when is_flags is False
        try:
            v.set("Rock,Paper")
            self.fail("Single value required")
        except ValueError:
            pass
        # we can set from an integer
        v.set(1)
        self.assertTrue(v.value == 1)
        self.assertTrue(str(v) == "Paper", to_text(v))
        try:
            v.set(4)
            self.fail("Enum member must be a member")
        except ValueError:
            pass
        try:
            v.set(3)
            self.fail("Enum value must be a member (no bitwise or)")
        except ValueError:
            pass
        try:
            v.set(1.0)
            self.fail("Enum set from float")
        except TypeError:
            pass

    def test_manual_members(self):
        et = odata.EnumerationType()
        m3 = odata.Member()
        m3.name = "Rock"
        m3.value = 3
        m3.declare(et)
        self.assertTrue(et.assigned_values is False)
        self.assertTrue(len(et.members) == 1)
        self.assertTrue(et.members[0] is m3)
        self.assertTrue(et['Rock'] is m3)
        self.assertTrue(m3.value == 3, "Manual value 3")
        m2 = odata.Member()
        m2.name = "Paper"
        m2.value = 2
        m2.declare(et)
        self.assertTrue(m2.value == 2, "Manual value 2")
        m1 = odata.Member()
        m1.name = "Scissors"
        try:
            m1.declare(et)
            self.fail("Manual member requires value")
        except odata.ModelError:
            pass
        m3alt = odata.Member()
        m3alt.name = "Stone"
        m3alt.value = 3
        # aliases are OK
        m3alt.declare(et)

    def test_manual_value(self):
        et = odata.EnumerationType()
        for name, value in (("Rock", 3), ("Paper", 2), ("Scissors", 1)):
            m = odata.Member()
            m.name = name
            m.value = value
            m.declare(et)
        # we can set from an integer
        v = et()
        v.set(1)
        self.assertTrue(v.value == 1)
        self.assertTrue(str(v) == "Scissors")
        try:
            v.set(0)
            self.fail("No zero value")
        except ValueError:
            pass
        v.set("Paper")
        self.assertTrue(v.value == 2)

    def test_flags(self):
        # If the IsFlags attribute has a value of true, a non-negative
        # integer value MUST be specified for the Value attribute
        et = odata.EnumerationType()
        m = odata.Member()
        m.name = "Red"
        m.declare(et)
        # you can't set is_flags if there are already members
        try:
            et.set_is_flags()
            self.fail("flags with auto-members")
        except odata.ModelError:
            pass
        et = odata.EnumerationType()
        et.set_is_flags()
        self.assertTrue(et.is_flags is True)
        self.assertTrue(et.assigned_values is False)
        m = odata.Member()
        m.name = "Red"
        try:
            m.declare(et)
            self.fail("flags requires member values")
        except odata.ModelError:
            pass
        m.value = 1
        m.declare(et)
        m = odata.Member()
        m.name = "Green"
        m.value = 2
        m.declare(et)
        self.assertTrue(len(et.members) == 2)

    def test_flag_values(self):
        et = odata.EnumerationType()
        et.set_is_flags()
        for name, value in (
                ("Red", 1), ("Green", 2), ("Blue", 4),
                ("Yellow", 3), ("Magenta", 5),
                # ("Cyan", 6),
                ("White", 7)):
            m = odata.Member()
            m.name = name
            m.value = value
            m.declare(et)
        v = et()
        v.set(1)
        self.assertTrue(v.value == 1)
        self.assertTrue(str(v) == "Red")
        # you can't use a value that isn't defined even if it makes sense.
        try:
            v.set(0)
            self.fail("0 for flags when unspecified")
        except ValueError:
            pass
        v.set("White")
        self.assertTrue(v.value == 7)
        # when converting to strings, use an exact match if there is one
        self.assertTrue(str(v) == "White")
        v.set(["Red", "Green"])
        self.assertTrue(str(v) == "Yellow")
        v.set(["Green", "Blue"])
        # otherwise use the composed flags preserving definition order
        self.assertTrue(str(v) == "Green,Blue")


class ValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all values"""
        # construct without a type definition
        try:
            v = odata.Value()
            self.fail("Value require type definition")
        except TypeError:
            pass
        t = odata.edm['PrimitiveType']
        v = odata.Value(t)
        # this is a NULL value of an unspecified type
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.type_def is t)
        d = {}
        try:
            d[v] = 1
            self.fail("Unspecified Value is hashable")
        except TypeError:
            pass


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
        v = odata.PrimitiveValue()
        # this is a NULL value of an unspecified type
        self.assertTrue(isinstance(v, odata.Value))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value on construction")
        # the associated type must be the built-in Edm.PrimitiveType
        self.assertTrue(v.type_def is odata.edm['PrimitiveType'])
        d = {}
        try:
            d[v] = 1
            self.fail("PrimitiveValue hashable")
        except TypeError:
            pass
        # construct a value from the abstract type
        primitive = odata.edm['PrimitiveType']
        v = primitive()
        self.assertTrue(isinstance(v, odata.PrimitiveValue))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.do_set(
            odata.PrimitiveValue,
            good=(),
            bad_values=(),
            bad_types=(True, 0, 'null'))

    def test_all_constructors(self):
        for t, pv, default in ALL_TYPES:
            t_def = odata.edm[t.__name__[:-5]]
            self.assertTrue(isinstance(t_def, odata.PrimitiveType))
            v = t()
            self.assertTrue(isinstance(v, odata.PrimitiveValue))
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
            t_def = odata.edm[t.__name__[:-5]]
            # null constructor
            v = t()
            self.assertTrue(isinstance(v, odata.PrimitiveValue))
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
        v = odata.PrimitiveValue.from_value(None)
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value from_value")
        self.assertTrue(v.type_def is odata.edm['PrimitiveType'])
        for t, pv, default in ALL_TYPES:
            if default:
                v = odata.PrimitiveValue.from_value(pv)
                self.assertTrue(isinstance(v, t), "from_value default type")
            # you can't create a value from an existing value using this
            # method - use an OData operation like cast instead
            try:
                odata.PrimitiveValue.from_value(t(pv))
                self.fail("from_value(%s) non-null" % repr(t))
            except TypeError:
                pass
            try:
                odata.PrimitiveValue.from_value(t())
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
            v.set(None)
            self.assertFalse(v)
            self.assertTrue(v.value is None, type_msg + "set(None)")
            v.set(pv)
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
                v.set(pv)
                self.fail(value_msg + "set")
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
                v.set(pv)
                self.fail(value_msg + "set")
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
                v.set(xv)
                self.fail("set(%s) non-null" % repr(t))
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
            odata.BinaryValue,
            good=((b'Hello', b'Hello'),
                  (b'', b''),
                  (b'null', b'null'),
                  (ul(b'Caf\xe9'), b'Caf\xc3\xa9'),
                  (GoodBytes(), b'HiBytes')),
            bad_values=(BadBytes(), ),
            bad_types=())
        self.do_text(
            odata.BinaryValue,
            ((b'Hello', 'SGVsbG8='),
             (b'Caf\xc3\xa9', 'Q2Fmw6k='),
             (b'ab?de>g', 'YWI_ZGU-Zw==')))

    def test_boolean(self):
        """Boolean values"""
        self.do_set(
            odata.BooleanValue,
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
            odata.BooleanValue,
            ((True, 'true'),
             (False, 'false')))

    def test_byte(self):
        """Byte values"""
        self.do_set(
            odata.ByteValue,
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
            odata.ByteValue,
            ((0, '0'), (1, '1'), (255, '255')))
        # check limits
        self.assertTrue(odata.ByteValue.MAX == 255)
        self.assertTrue(odata.ByteValue.MIN == 0)

    def test_date(self):
        """Date values"""
        eagle_day = Date.from_str("19690720")
        rome_day = Date.from_str("-07520421", xdigits=0)
        self.do_set(
            odata.DateValue,
            good=((eagle_day, eagle_day),
                  (datetime.date(1969, 7, 20), eagle_day),
                  (rome_day, rome_day),
                  (datetime.datetime(1969, 7, 20, 20, 17, 40), eagle_day),
                  ),
            bad_values=(Date.from_str("1969-07"),
                        Date.from_str("1969")),
            bad_types=(19690720, 19690720.0, '19690720'))
        self.do_text(
            odata.DateValue,
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
            odata.DateTimeOffsetValue,
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
            odata.DateTimeOffsetValue,
            ((eagle_time, '1969-07-20T20:17:40Z'),
             (rome_time, '-0752-04-21T16:00:00+01:00'),
             (eagle_time_ms, '1969-07-20T20:17:40.000000Z')))
        # check the correct operation of leap seconds with high precision
        t = odata.PrimitiveType()
        t.set_base(odata.edm['DateTimeOffset'])
        t.set_precision(6)
        v = t()
        v.set(leap_factual)
        self.assertTrue(v.value == leap_fadjusted)
        v.set(eagle_time_ms)
        self.assertTrue(to_text(v) == '1969-07-20T20:17:40.000000Z')

    def test_decimal(self):
        """Decimal values"""
        self.do_set(
            odata.DecimalValue,
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
            odata.DecimalValue,
            ((Decimal(0), '0'), (Decimal(1), '1'), (Decimal('1.00'), '1.00'),
             (Decimal(-1), '-1'), (Decimal('3.5'), '3.5')))

    def test_duration(self):
        """Duration values"""
        t12345 = Duration("P1DT2H3M4.5S")
        t1234 = Duration("P1DT2H3M4S")
        # OData only allows Days, Hours, Minutes and Seconds.
        self.do_set(
            odata.DurationValue,
            good=((t12345, t12345),
                  (t1234, t1234),
                  (Duration("P01DT02H03M04S"), t1234)),
            bad_values=(Duration("P1Y"), Duration("P1M"), Duration("P1W")),
            bad_types=(1, 1.0, Time.from_str("02:03:04.5")))
        # by default, unspecified precision
        self.do_text(
            odata.DurationValue,
            ((t12345, 'P1DT2H3M4.5S'),
             (t1234, 'P1DT2H3M4S')))
        # check the correct operation of precision
        t = odata.PrimitiveType()
        t.set_base(odata.edm['Duration'])
        t.set_precision(1)
        v = t()
        v.set(t12345)
        self.assertTrue(v.value == t12345)
        self.assertTrue(to_text(v) == 'P1DT2H3M4.5S')

    def test_float_value(self):
        """Double and Single values"""
        for cls in (odata.DoubleValue, odata.SingleValue):
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
        for cls in (odata.GeographyPointValue, odata.GeometryPointValue):
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
        for cls in (odata.GeographyLineStringValue,
                    odata.GeometryLineStringValue):
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
        for cls in (odata.GeographyPolygonValue,
                    odata.GeometryPolygonValue):
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
        for cls in (odata.GeographyMultiPointValue,
                    odata.GeometryMultiPointValue):
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
        for cls in (odata.GeographyMultiLineStringValue,
                    odata.GeometryMultiLineStringValue):
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
        for cls in (odata.GeographyMultiPolygonValue,
                    odata.GeometryMultiPolygonValue):
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
        for cls in (odata.GeographyCollectionValue,
                    odata.GeometryCollectionValue):
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
            odata.GuidValue,
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
            odata.GuidValue,
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
            odata.StringValue,
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
            odata.StringValue,
            ((uhello, uhello),
             (ucafe, ucafe),
             ))

    def test_time(self):
        """TimeOfDay values"""
        slast = Time.from_str("235959")
        eagle_time = Time.from_str("201740")
        eagle_time_ms = Time.from_str("201740.000")
        self.do_set(
            odata.TimeOfDayValue,
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
            odata.TimeOfDayValue,
            ((eagle_time, '20:17:40'), (eagle_time_ms, '20:17:40.000000')))
        # check the correct operation of precision
        t = odata.PrimitiveType()
        t.set_base(odata.edm['TimeOfDay'])
        t.set_precision(6)
        v = t()
        v.set(Time.from_str("235960.5"))
        self.assertTrue(v.value == Time.from_str("235959.999999"))
        v.set(Time.from_str("235960.55"))
        self.assertTrue(v.value == Time.from_str("235959.999999"))
        v.set(eagle_time_ms)
        self.assertTrue(v.value == eagle_time_ms)
        self.assertTrue(to_text(v) == '20:17:40.000000')


NUMERIC_TYPES = (
    odata.ByteValue,
    odata.DecimalValue,
    odata.DoubleValue,
    odata.Int16Value,
    odata.Int32Value,
    odata.Int64Value,
    odata.SByteValue,
    odata.SingleValue)


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
            for t2 in self.type_gen():
                # a null instance of type t1 can be cast to t2
                v2 = v1.cast(t2)
                self.assertTrue(v2.is_null())
        # primitive types are cast to Edm.String using literal
        # representation used in payloads and WKT for Geo types.
        stype = odata.edm['String']
        for t, pv, default in ALL_TYPES:
            v1 = t(pv)
            v2 = v1.cast(stype)
            self.assertFalse(v2.is_null())
            self.assertTrue(isinstance(v2, odata.StringValue))
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
                v2 = v1.cast(odata.edm[t2.edm_name])
                # should succeed!
                self.assertFalse(v2.is_null(), "%s -> %s is null" %
                                 (repr(v1), repr(v2)))
                if isinstance(v1, odata.IntegerValue) or \
                        isinstance(v2, odata.IntegerValue):
                    # appropriate round = truncation to integer
                    self.assertTrue(v2.value == 3, "%s -> %s is %s" %
                                    (repr(v1), repr(v2), str(v2)))
                else:
                    self.assertTrue(str(v2) == '3.75', "%s -> %s is %s" %
                                    (repr(v1), repr(v2), str(v2)))
                # the cast fails if the integer part doesn't fit into
                # the target type
                if isinstance(v2, odata.DecimalValue):
                    # no max for Decimal
                    continue
                if isinstance(v1, odata.DecimalValue):
                    # Decimal to something else
                    vmax = t1(Decimal(str(t2.MAX)) * 2)
                    v2 = vmax.cast(odata.edm[t2.edm_name])
                    self.assertTrue(v2.is_null(), "%s -> %s not null" %
                                    (str(vmax), repr(v2)))
                    vmin = t1(Decimal(str(t2.MIN - 1)) * 2)
                    v2 = vmin.cast(odata.edm[t2.edm_name])
                    self.assertTrue(v2.is_null(), "MIN(%s) -> %s not null" %
                                    (repr(vmin), repr(v2)))
                else:
                    if t2.MAX < t1.MAX:
                        vmax = t1(t1.MAX)
                        v2 = vmax.cast(odata.edm[t2.edm_name])
                        self.assertTrue(v2.is_null())
                    if t2.MIN > t1.MIN:
                        vmin = t1(t1.MIN)
                        v2 = vmin.cast(odata.edm[t2.edm_name])
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
                if isinstance(v1, odata.PrimitiveValue) and \
                        issubclass(t2.value_type, type(v1)):
                    continue
                # exclude PrimitiveType -> String
                if isinstance(v1, odata.PrimitiveValue) and \
                        issubclass(t2.value_type, odata.StringValue):
                    continue
                # exclude Numeric -> Numeric
                if isinstance(v1, odata.NumericValue) and \
                        issubclass(t2.value_type, odata.NumericValue):
                    continue
                if isinstance(v1, odata.PrimitiveValue) or \
                        issubclass(t2.value_type, odata.PrimitiveValue):
                    # primitive -> structured/collection
                    # structured/collection -> primitive
                    v2 = v1.cast(t2)
                    self.assertTrue(v2.is_null(), "%s -> %s not null" %
                                    (repr(v1), repr(v2)))
                else:
                    self.fail("Unexpected cast: %s to %s" %
                              (repr(v1), repr(t2)))


class ParserTests(unittest.TestCase):

    # literals enclosed in single quotes are treated case-sensitive

    def from_str(self, cls, good, bad):
        for s in good:
            logging.debug("Parsing %s from %s", cls.__name__, repr(s))
            try:
                v = cls.from_str(s)
                self.assertTrue(v, "%s.from_str(%s) is False" %
                                (cls.__name__, repr(s)))
            except ValueError as e:
                logging.error(str(e))
                self.fail("%s.from_str(%s) failed" % (cls.__name__, repr(s)))
        for s in bad:
            try:
                cls.from_str(s)
                self.fail("%s.from_str(%s) succeeded" %
                          (cls.__name__, repr(s)))
            except ValueError:
                pass

    def test_boolean_value(self):
        """booleanValue = "true" / "false" """
        v = odata.BooleanValue.from_str("true")
        self.assertTrue(v.value is True)
        v = odata.BooleanValue.from_str("false")
        self.assertTrue(v.value is False)
        good = ("True", "TRUE", "False", "FALSE")
        bad = ('1', '0', 'yes', 'no', ' true', 'true ', "'true'", "null", "")
        self.from_str(odata.BooleanValue, good, bad)

    def test_guid_value(self):
        """guidValue =  8HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-"
                        12HEXDIG"""
        v = odata.GuidValue.from_str("00000000-0000-0000-0000-00000000002A")
        self.assertTrue(v.value == uuid.UUID(int=42))
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
        self.from_str(odata.GuidValue, good, bad)

    def test_duration_value(self):
        """durationValue = [ sign ] "P" [ 1*DIGIT "D" ]
                [ "T" [ 1*DIGIT "H" ] [ 1*DIGIT "M" ]
                 [ 1*DIGIT [ "." 1*DIGIT ] "S" ] ]"""
        v = odata.DurationValue.from_str("-P3DT1H4M1.5S")
        self.assertTrue(v.value.sign == -1)
        self.assertTrue(v.value.years == 0)
        self.assertTrue(v.value.months == 0)
        self.assertTrue(v.value.weeks is None)
        self.assertTrue(v.value.days == 3)
        self.assertTrue(v.value.hours == 1)
        self.assertTrue(v.value.minutes == 4)
        self.assertTrue(v.value.seconds == 1.5)
        good = (
            "P", "+P", "PT1S", "PT1.1S", "P1D",
            )
        bad = (
            "", "P1H", "1H", "P1D1H", "P1DT1M1H", "1S",
            )
        self.from_str(odata.DurationValue, good, bad)

    def test_date_value(self):
        """dateValue = year "-" month "-" day

        year  = [ "-" ] ( "0" 3DIGIT / oneToNine 3*DIGIT )
        month = "0" oneToNine
              / "1" ( "0" / "1" / "2" )
        day   = "0" oneToNine
              / ( "1" / "2" ) DIGIT
              / "3" ( "0" / "1" )"""
        v = odata.DateValue.from_str("0000-01-01")
        self.assertTrue(v.value.get_xcalendar_day() == (False, 0, 0, 1, 1))
        v = odata.DateValue.from_str("-0999-01-01")
        self.assertTrue(v.value.get_xcalendar_day() == (True, 9, 99, 1, 1))
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
        self.from_str(odata.DateValue, good, bad)

    def test_date_time_offset_value(self):
        """dateTimeOffsetValue =
            year "-" month "-" day "T" hour ":" minute
            [ ":" second [ "." fractionalSeconds ] ]
            ( "Z" / sign hour ":" minute )

        hour   = ( "0" / "1" ) DIGIT / "2" ( "0" / "1" / "2" / "3" )
        minute = zeroToFiftyNine
        second = zeroToFiftyNine
        fractionalSeconds = 1*12DIGIT"""
        v = odata.DateTimeOffsetValue.from_str("0000-01-01T00:00:00Z")
        self.assertTrue(v.value.get_xcalendar_time_point() ==
                        (False, 0, 0, 1, 1, 0, 0, 0))
        self.assertTrue(v.value.get_zone() == (0, 0))
        v = odata.DateTimeOffsetValue.from_str("-0752-04-21T16:00:00+01:00")
        self.assertTrue(v.value.get_xcalendar_time_point() ==
                        (True, 7, 52, 4, 21, 16, 0, 0))
        self.assertTrue(v.value.get_zone() == (1, 60))
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
        self.from_str(odata.DateTimeOffsetValue, good, bad)

    def test_time_of_day_value(self):
        """timeOfDayValue = hour ":" minute
                            [ ":" second [ "." fractionalSeconds ] ]"""
        v = odata.TimeOfDayValue.from_str("00:00:00")
        self.assertTrue(v.value.get_time() == (0, 0, 0))
        self.assertTrue(v.value.get_zone() == (None, None))
        v = odata.TimeOfDayValue.from_str("00:00")
        self.assertTrue(v.value.get_time() == (0, 0, 0))
        self.assertTrue(v.value.get_zone() == (None, None))
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
        self.from_str(odata.TimeOfDayValue, good, bad)

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
            p = odata.PrimitiveParser(src)
            try:
                v = p.require_enum_value()
            except ValueError as err:
                self.fail("%s raised %s" % (src, str(err)))
            self.assertTrue(v == value, "failed to parse %s" % src)
            p.require_end()
        for src in bad:
            p = odata.PrimitiveParser(src)
            try:
                v = p.require_enum_value()
                p.require_end()
                self.fail("%s validated for enumValue" % repr(src))
            except ValueError:
                pass

    def test_decimal_value(self):
        """decimalValue = [SIGN] 1*DIGIT ["." 1*DIGIT]"""
        v = odata.DecimalValue.from_str("3.14")
        self.assertTrue(v.value == Decimal('3.14'))
        v = odata.DecimalValue.from_str("-02.0")
        self.assertTrue(v.value == Decimal('-2'))
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
        self.from_str(odata.DecimalValue, good, bad)

    def test_double_value(self):
        """doubleValue = decimalValue [ "e" [SIGN] 1*DIGIT ] / nanInfinity
            nanInfinity = 'NaN' / '-INF' / 'INF'
        """
        v = odata.DoubleValue.from_str("3.14")
        self.assertTrue(v.value == 3.14)
        v = odata.DoubleValue.from_str("-02.0")
        self.assertTrue(v.value == -2.0)
        v = odata.DoubleValue.from_str("3.14e8")
        self.assertTrue(v.value == 3.14e8)
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
        self.from_str(odata.DoubleValue, good, bad)
        self.from_str(odata.SingleValue, good, bad)

    def test_sbyte_value(self):
        """decimalValue = [ sign ] 1*3DIGIT"""
        v = odata.SByteValue.from_str("+123")
        self.assertTrue(v.value == 123)
        v = odata.SByteValue.from_str("-9")
        self.assertTrue(v.value == -9)
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
        self.from_str(odata.SByteValue, good, bad)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
