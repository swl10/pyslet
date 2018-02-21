#! /usr/bin/env python

from decimal import Decimal
import logging
import unittest
import uuid


from pyslet.iso8601 import (
    Date,
    Time,
    TimePoint
    )
from pyslet.odata4 import (
    data,
    errors,
    geotypes as geo,
    metadata as csdl,
    model as odata,
    names,
    primitive,
    query,
    types,
    )
from pyslet.py2 import (
    u8,
    ul,
    )
from pyslet.rfc2396 import URI
from pyslet.vfs import OSFilePath
from pyslet.xml.xsdatatypes import Duration


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(EntityModelTests, 'test'),
        unittest.makeSuite(SchemaTests, 'test'),
        unittest.makeSuite(StructuredTypeTests, 'test'),
        unittest.makeSuite(CollectionTests, 'test'),
        unittest.makeSuite(StructuredValueTests, 'test'),
        unittest.makeSuite(EntitySetTests, 'test'),
        ))


TEST_DATA_DIR = OSFilePath(__file__).split()[0].join('data_odata4')


good_simple_identifiers = (
    "Hello",
    ul(b"Caf\xe9"),
    ul(b'\xe9faC'),
    u8(b'\xe3\x80\x87h'),
    "_Hello",
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_"
    )

bad_simple_identifiers = (
    "45", "M'", "M;", "M=", "M\\", "M.N", "M+", "M-", "M*",
    "M/", "M<", "M>", "M=", "M~", "M!", "M@", "M#", "M%",
    "M^", "M&", "M|", "M`", "M?", "M(", "M)", "M[", "M]",
    "M,", "M;", "M*", "M.M", "", None,
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_L")

good_namespaces = (
    "Edm", "Some.Vocabulary.V1", "Hello", ul(b"Caf\xe9"),
    ul(b'\xe9faC'), u8(b'\xe3\x80\x87h'), "_Hello",
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

bad_namespaces = (
    "45", "M'", "M;", "M=", "M\\", "M.", "M+", "M-", "M*",
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


def load_trippin():
    dpath = TEST_DATA_DIR.join('trippin.xml')
    uri = URI.from_virtual_path(dpath)
    doc = csdl.CSDLDocument(base_uri=uri)
    doc.read()
    return doc.root.entity_model

# save loading this schema for every setUp
trippin_ro = load_trippin()


class EntityModelTests(unittest.TestCase):

    def test_constructor(self):
        em = odata.EntityModel()
        self.assertTrue(len(em) == 2, "Predefined Edm and odata schemas")
        self.assertTrue("Edm" in em)
        self.assertTrue("odata" in em)

    def test_namespace(self):
        em = odata.EntityModel()
        for s in good_namespaces:
            try:
                em.check_name(s)
            except ValueError:
                self.fail("%s failed" % repr(s))
        for s in bad_namespaces:
            try:
                em.check_name(s)
                self.fail("%s failed" % repr(s))
            except ValueError:
                pass

    def test_entitymodel_declare(self):
        em = odata.EntityModel()
        ns = odata.Schema()
        # This should work fine!
        ns.declare(em, "Hello")
        self.assertTrue(ns.name == "Hello", "Declaration OK")
        self.assertTrue(em["Hello"] is ns, "Can look-up value")
        try:
            ns.declare(em, "+Hello")
            self.fail("check_name failed")
        except ValueError:
            pass
        try:
            ns.declare(em, "Some.Vocabulary.")
            self.fail("Schema.declare with bad name")
        except ValueError:
            pass
        n = names.Named()
        try:
            n.declare(em, "BadType")
            self.fail("Named.declare in EntityModel")
        except TypeError:
            pass
        ns.declare(em, "Some.Vocabulary.V1")
        self.assertTrue(len(em) == 4)       # includes Edm and odata
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
        self.assertTrue(em.qualified_get("com.example._X.x") is None)
        nsx = odata.Schema()
        nsx.declare(em, "com.example._X")
        nsy = odata.Schema()
        nsy.declare(em, "_Y")
        x = types.NominalType(value_type=data.Value)
        x.declare(nsx, "x")
        y = types.NominalType(value_type=data.Value)
        y.declare(nsy, "y")
        z = types.NominalType(value_type=data.Value)
        em.qualified_tell("com.example._X.x", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(em.qualified_get("com.example._X.x") is x)
        self.assertTrue(
            em.qualified_get(names.QualifiedName("com.example._X", "x")) is x)
        self.assertTrue(c.last_value is x)
        em.qualified_tell("com.example._X.z", c)
        em.qualified_tell("_Y.y", c)
        em.qualified_tell("_Y.ciao", c)
        em.qualified_tell("_Z.ciao", c)
        self.assertTrue(c.call_count == 2)
        self.assertTrue(c.last_value is y)
        z.declare(nsx, "z")
        self.assertTrue(c.call_count == 3)
        self.assertTrue(c.last_value is z)
        nsy.close()
        self.assertTrue(c.call_count == 4)
        self.assertTrue(c.last_value is None)
        nsx.close()
        # no change
        self.assertTrue(c.call_count == 4)
        self.assertTrue(c.last_value is None)
        em.close()
        # one more call due to the namespace _Z never appearing
        self.assertTrue(c.call_count == 5)
        self.assertTrue(c.last_value is None)

    def test_close(self):
        em = odata.EntityModel()
        ns = odata.Schema()
        # attempting to close an entity model containing an open
        # schema will fail
        ns.declare(em, "Hello")
        try:
            em.close()
        except errors.ModelError:
            pass

    def test_trippin(self):
        trippin = load_trippin()
        person = trippin[
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models"]["Person"]
        people = [t for t in trippin.derived_types(person)]
        self.assertTrue(len(people) == 2)
        # there should be a single container
        container = trippin.get_container()
        self.assertTrue(isinstance(container, odata.EntityContainer))
        # now simulate two containers
        schema = trippin["Trippin"]     # an extra alias
        schema._reopen()
        xcontainer = odata.EntityContainer()
        xcontainer.declare(schema, "XContainer")
        schema.close()
        try:
            trippin.get_container()
            self.fail("One container only")
        except errors.ModelError:
            pass

    def test_context(self):
        em = odata.EntityModel()
        try:
            em.get_context_url()
            self.fail("Unbound EntityModel has no context URL")
        except errors.UnboundValue:
            pass


class SchemaTests(unittest.TestCase):

    def test_constructor(self):
        ns = odata.Schema()
        self.assertTrue(len(ns) == 0, "no definitions on init")

    def test_checks(self):
        ns = odata.Schema()
        n = names.Named()
        try:
            n.declare(ns, "Hello")
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        n = types.NominalType(value_type=data.Value)
        try:
            n.declare(ns, "")
            self.fail("Named.declare with no name")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            self.fail("check_name with None")
        except ValueError:
            pass
        try:
            n.declare(ns, "+Hello")
            self.fail("Named.declare with bad name")
        except ValueError:
            pass
        try:
            n.declare(ns, "_Hello")
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")
        # you can't declare something twice (with the same name)
        try:
            n.declare(ns, "_Hello")
            self.fail("NominalType redeclared (same namespace and name)")
        except errors.DuplicateNameError:
            pass
        ns2 = odata.Schema()
        # declare in an alternate namespace
        n.declare(ns2, "Hello")
        self.assertTrue(n.name == "_Hello")
        self.assertTrue(n.nametable() is ns)
        self.assertTrue(ns2["Hello"] is n)
        # declare alias in same namespace
        n.declare(ns, "HelloAgain")
        self.assertTrue(n.name == "_Hello")
        self.assertTrue(n.nametable() is ns)
        self.assertTrue(ns["HelloAgain"] is n)

    def test_qname(self):
        ns = odata.Schema()
        n = types.NominalType(value_type=data.Value)
        # if the schema has no name, the qualified name is just name
        n.declare(ns, "Hello")
        self.assertTrue(n.qname == "Hello")
        self.assertTrue(n.nametable is not None)
        self.assertTrue(n.nametable() is ns)
        self.assertTrue(n.is_owned_by(ns))
        # if we delete the schema we should lose the link
        del ns
        self.assertTrue(n.nametable is not None)
        self.assertTrue(n.nametable() is None)
        # we're just an orphan
        ns2 = odata.Schema()
        # fake declaration of schema
        ns2.name = "my.namespace"
        n.declare(ns2, "HelloAgain")
        self.assertTrue(n.name == "Hello")
        self.assertTrue(n.nametable() is None)
        self.assertTrue(n.qname == "Hello")
        n = types.NominalType(value_type=data.Value)
        n.declare(ns2, "Hello")
        self.assertTrue(n.qname == "my.namespace.Hello")

    def test_edm(self):
        # There should be a default Edm Schema
        self.assertTrue(isinstance(odata.edm, odata.Schema))
        self.assertTrue(odata.edm.name == "Edm")
        self.assertTrue(len(odata.edm) == 39, sorted(odata.edm.keys()))

    def test_odata(self):
        # There should be a default odata Schema
        self.assertTrue(isinstance(odata.odata, odata.Schema))
        self.assertTrue(odata.odata.name == "odata")
        self.assertTrue(len(odata.odata) == 16, sorted(odata.odata.keys()))


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
    # odata.Geography is abstract
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
    # odata.Geometry is abstract
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


class StructuredTypeTests(unittest.TestCase):

    def test_constructors(self):
        # structured types are composed of structural properties they
        # are themselves name tables!
        t = types.StructuredType(value_type=data.StructuredValue)
        # abstract class
        self.assertTrue(isinstance(t, types.NominalType),
                        "structured types are nominal types")
        self.assertTrue(isinstance(t, names.NameTable),
                        "structured types define scope")
        pt = types.PrimitiveType(value_type=primitive.PrimitiveValue)
        p = types.Property()
        self.assertTrue(isinstance(p, names.Named), "properties are nameable")
        self.assertTrue(p.type_def is None)
        p.set_type(pt)
        self.assertTrue(p.type_def is pt)

    def test_derived(self):
        dpath = TEST_DATA_DIR.join('valid', 'atest.xml')
        uri = URI.from_virtual_path(dpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        ta = em['a.test.pyslet.org']['TypeA']
        derived = list(em.derived_types(ta))
        self.assertTrue(len(derived) == 2)
        tnames = [t.name for t in derived]
        self.assertTrue('TypeB' in tnames)
        self.assertTrue('TypeC' in tnames)
        tx = em['b.test.pyslet.org']['TypeX']
        derived = list(em.derived_types(tx))
        self.assertTrue(len(derived) == 3)
        tnames = [t.name for t in derived]
        self.assertTrue('TypeQ' not in tnames)

    def test_nppath(self):
        dpath = TEST_DATA_DIR.join('valid', 'structure-paths.xml')
        uri = URI.from_virtual_path(dpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        # simple case, just a navigation property name
        a = em['test.pyslet.org']['TypeA']
        b = em['test.pyslet.org']['TypeB']
        x = em['test.pyslet.org']['TypeX']
        np = x.resolve_nppath(["XP"], em)
        self.assertTrue(np.name == "XP")
        self.assertTrue(isinstance(np, types.NavigationProperty))
        self.assertTrue(np is x["XP"])
        # simple case resulting in simple property
        try:
            x.resolve_nppath(["X1"], em)
            self.fail("resolve_nppath resolved simpled property")
        except errors.PathError:
            pass
        # simple case with non-existent property name
        try:
            x.resolve_nppath(["X9"], em)
            self.fail("resolve_nppath: X9")
        except errors.PathError:
            pass
        # now follow a path using a complex type
        np = x.resolve_nppath(["X2", "AP"], em)
        self.assertTrue(np is a['AP'])
        try:
            x.resolve_nppath(["X2", "A1"], em)
            # can't resolve to simple property
            self.fail("TypeX/X2/A1")
        except errors.PathError:
            pass
        # now follow a path using a derived complex type
        np = x.resolve_nppath(
            ["X2", names.QualifiedName("test.pyslet.org", "TypeB"), "BP"], em)
        self.assertTrue(np is b['BP'])
        # but if we miss the type cast segment it fails...
        try:
            x.resolve_nppath(["X2", "BP"], em)
            self.fail("TypeX/X2/BP")
        except errors.PathError:
            pass
        # derived types inherit properties so it's ok to do this...
        np = x.resolve_nppath(
            ["X2", names.QualifiedName("test.pyslet.org", "TypeB"), "AP"], em)
        self.assertTrue(np is a['AP'])
        self.assertTrue(np is b['AP'])
        # it is OK to do a nop-cast like this too
        np = x.resolve_nppath(
            ["X2", names.QualifiedName("test.pyslet.org", "TypeA"), "AP"], em)
        self.assertTrue(np is a['AP'])
        # but a cast to a parent is not OK as it opens the door to
        # further casts that descend a different branch of the type tree
        # resulting in a type that is (derived from) TypeX.
        try:
            x.resolve_nppath(
                ["X3", names.QualifiedName("test.pyslet.org", "TypeA"), "AP"],
                em)
            self.fail("TypeX/X3/TypeA/AP")
        except errors.PathError:
            pass
        self.assertTrue(np is a['AP'])
        # ...but doing so places derived type properties out of reach
        try:
            x.resolve_nppath(
                ["X3", names.QualifiedName("test.pyslet.org", "TypeA"), "BP"],
                em)
            self.fail("TypeX/X3/TypeA/BP")
        except errors.PathError:
            pass


class StructuredValueTests(unittest.TestCase):

    def setUp(self):    # noqa
        self.em = odata.EntityModel()
        self.s = odata.Schema()
        self.s.declare(self.em, "Schema")
        # an entity type
        et = types.EntityType(value_type=data.EntityValue)
        et.declare(self.s, "TypeX")
        p = types.Property()
        p.set_type(odata.edm['Int32'])
        p.set_nullable(False)
        p.declare(et, "ID")
        et.add_key(("ID", ))
        p = types.Property()
        p.set_type(odata.edm['String'])
        p.set_nullable(True)
        p.declare(et, "Info")
        et.close()
        # a complex type
        st = types.ComplexType(value_type=data.ComplexValue)
        st.declare(self.s, "TypeA")
        p = types.Property()
        p.set_type(odata.edm['String'])
        p.set_nullable(True)
        p.set_default(p.type_def("Hello"))
        p.declare(st, "DefNullable")
        p = types.Property()
        p.set_type(odata.edm['String'])
        p.set_nullable(False)
        p.set_default(p.type_def("Hello"))
        p.declare(st, "DefNonNullable")
        p = types.Property()
        p.set_type(odata.edm['String'])
        p.set_nullable(True)
        p.declare(st, "Nullable")
        p = types.Property()
        p.set_type(odata.edm['String'])
        p.set_nullable(False)
        p.declare(st, "NonNullable")
        np = types.NavigationProperty()
        np.set_type(et, collection=False, contains_target=True)
        np.set_nullable(True)
        np.declare(st, "NullableSingleton")
        np = types.NavigationProperty()
        np.set_type(et, collection=False, contains_target=True)
        np.set_nullable(False)
        np.declare(st, "NonNullableSingleton")
        st.close()
        # more complex object
        st = types.ComplexType(value_type=data.ComplexValue)
        st.declare(self.s, "TypeB")
        p = types.Property()
        p.set_type(odata.edm['Int32'])
        p.declare(st, "Int32Property")
        p = types.Property()
        p.set_nullable(True)
        p.set_type(self.em["Schema"]["TypeA"])
        p.declare(st, "Nullable")
        p = types.Property()
        p.set_nullable(False)
        p.set_type(self.em["Schema"]["TypeA"])
        p.declare(st, "NonNullable")
        np = types.NavigationProperty()
        np.declare(st, "Related")
        st.close()
        self.s.close()
        self.em.close()

    def test_constructor(self):
        st = self.em.qualified_get("Schema.TypeA")
        sv = data.StructuredValue(type_def=st)
        self.assertTrue(len(sv) == 0, "empty on construction")
        self.assertTrue(sv.is_null())
        self.assertTrue(sv.base_def is st)
        # inherited characteristics
        self.assertTrue(sv.type_def is st)
        self.assertTrue(sv.service is None)
        self.assertTrue(sv.frozen is False)
        self.assertTrue(sv.dirty is False)
        self.assertTrue(sv.parent is None)
        self.assertTrue(sv.parent_cast is None)
        self.assertTrue(sv.name is None)
        # check null
        self.assertTrue(sv.get_value() is None)

    def test_primitives(self):
        # tests private implementation for setting options
        sv = data.StructuredValue(type_def=self.em['Schema']['TypeA'])
        self.assertTrue(sv.is_null())
        self.assertTrue(len(sv) == 0, repr(sv.keys()))
        # by default, all structural values are selected
        sv.set_defaults()
        # clean the value before proceeding...
        sv.clean()
        self.assertTrue(len(sv) == 4, repr(sv.keys()))
        self.assertTrue("DefNullable" in sv)
        self.assertTrue(sv.dirty is False, "private init is not dirty")
        pv = sv['DefNullable']
        self.assertTrue(isinstance(pv, primitive.StringValue))
        self.assertTrue(pv.type_def is odata.edm['String'])
        self.assertTrue(pv.service is None)
        self.assertTrue(pv.frozen is False)
        self.assertTrue(pv.dirty is False)
        self.assertTrue(pv.parent() is sv)
        self.assertTrue(pv.parent_cast is None)
        self.assertTrue(pv.name == "DefNullable")
        self.assertFalse(pv.is_null())
        self.assertTrue(pv.get_value() == "Hello")
        # change from default, value becomes dirty
        pv.set_value("Hi")
        self.assertTrue(pv.dirty is True)
        pv = sv['DefNonNullable']
        self.assertFalse(pv.is_null())
        self.assertTrue(pv.get_value() == "Hello")
        pv = sv['Nullable']
        self.assertTrue(pv.is_null())
        pv = sv['NonNullable']
        self.assertTrue(pv.is_null(), "No default value: null anyway")

    def test_complex(self):
        sv = data.StructuredValue(type_def=self.em['Schema']['TypeB'])
        # start out as null
        self.assertTrue(sv.is_null())
        self.assertTrue(len(sv) == 0, repr(sv.keys()))
        self.assertFalse("Nullable" in sv)
        # now create the defaults
        sv.set_defaults()
        # no select or expand = select all structural properties
        self.assertTrue(len(sv) == 3, repr(sv.keys()))
        self.assertTrue(sv['Int32Property'].is_null())
        pv = sv['Nullable']
        # a nullable complex type is created as null
        self.assertTrue(isinstance(pv, data.ComplexValue), repr(pv))
        self.assertTrue(pv.type_def is self.em['Schema']['TypeA'])
        self.assertTrue(pv.base_def is self.em['Schema']['TypeA'])
        self.assertTrue(pv.service is None)
        self.assertTrue(pv.frozen is False)
        self.assertTrue(pv.dirty is False)
        self.assertTrue(pv.parent() is sv)
        self.assertTrue(pv.parent_cast is None)
        self.assertTrue(pv.name == "Nullable")
        self.assertTrue(pv.is_null())
        # the value should have nothing defined in its property dictionary
        self.assertTrue(len(pv) == 0)
        # but it should have inherited the correct rules for options so
        # clearning the null value should activate the properties
        pv.set_defaults()
        self.assertTrue(pv.dirty is True)
        self.assertTrue(len(pv) == 4, repr(pv.keys()))
        self.assertTrue(pv["DefNullable"].get_value() == "Hello")
        self.assertTrue(pv["DefNullable"].dirty is False)
        # a non-nullable complex type starts off with default properties
        pv = sv['NonNullable']
        self.assertTrue(pv.dirty is False)
        self.assertTrue(len(pv) == 4, repr(pv.keys()))
        self.assertTrue(pv["DefNullable"].get_value() == "Hello")
        self.assertTrue(pv["DefNullable"].dirty is False)

    def test_navigation(self):
        sv = data.StructuredValue(type_def=self.em['Schema']['TypeA'])
        options = query.EntityOptions()
        # suppress structural properties
        options._select_default = False
        # expand all navigation properties
        options.add_expand_path("*")
        sv._set_options(options)
        # make it non-null and clean
        sv.set_defaults()
        sv.clean()
        self.assertTrue(len(sv) == 2, repr(sv.keys()))
        self.assertFalse("DefNullable" in sv)
        # a nullable *contained* singleton is created as a null entity value
        npv = sv['NullableSingleton']
        self.assertTrue(isinstance(npv, data.EntityValue), repr(npv))
        self.assertTrue(npv.type_def is self.em['Schema']['TypeX'])
        self.assertTrue(npv.base_def is self.em['Schema']['TypeX'])
        self.assertTrue(npv.service is None)
        self.assertTrue(npv.frozen is False)
        self.assertTrue(npv.dirty is False)
        self.assertTrue(npv.parent() is sv)
        self.assertTrue(npv.parent_cast is None)
        self.assertTrue(npv.name == "NullableSingleton")
        self.assertTrue(npv.is_null())
        self.assertTrue(len(npv) == 0)
        # a non-nullable *contained* singleton is created as default
        # entity value
        npv = sv['NonNullableSingleton']
        self.assertTrue(isinstance(npv, data.EntityValue), repr(npv))
        self.assertTrue(npv.type_def is self.em['Schema']['TypeX'])
        self.assertTrue(npv.base_def is self.em['Schema']['TypeX'])
        self.assertTrue(npv.service is None)
        self.assertTrue(npv.frozen is False)
        self.assertTrue(npv.dirty is False)
        self.assertTrue(npv.parent() is sv)
        self.assertTrue(npv.parent_cast is None)
        self.assertTrue(npv.name == "NonNullableSingleton")
        self.assertFalse(npv.is_null())
        self.assertTrue(len(npv) == 2)
        self.assertTrue(npv['ID'].is_null())
        self.assertTrue(npv['Info'].is_null())

    def test_set_value(self):
        pass

    def test_assign(self):
        pass


class CollectionTests(unittest.TestCase):

    def test_constructor(self):
        # collection types are collection wrappers for some other
        # primitive, complex or enumeration type.
        pt = types.PrimitiveType(value_type=primitive.PrimitiveValue)
        t = pt.collection_type()
        self.assertTrue(isinstance(t, types.NominalType),
                        "Collection types are nominal types")
        self.assertTrue(t.item_type is pt,
                        "Collection types must have an item type")

    def test_value(self):
        pt = types.PrimitiveType(value_type=primitive.PrimitiveValue)
        t = pt.collection_type()
        # types are callable to obtain values
        v = t()
        self.assertTrue(isinstance(v, data.CollectionValue))
        # never null
        self.assertTrue(v)
        self.assertFalse(v.is_null())


class EntitySetTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.em = odata.EntityModel()
        self.s = odata.Schema()
        self.s.declare(self.em, "Org.OData.Capabilities.V1")
        self.term = types.Term()
        self.term.declare(self.s, "IndexableByKey")
        self.term.set_type(odata.edm['Boolean'])
        self.s.close()
        self.em.close()

#     def test_constructor(self):
#         es = odata.EntitySet()
#         self.assertTrue(es.indexable_by_key() is True)
#
#     def test_indexable(self):
#         es = odata.EntitySet()
#         a = types.Annotation.from_term_ref(
#                 names.TermRef.from_str(
#                     "@Org.OData.Capabilities.V1.IndexableByKey"), self.em)
#         a.set_expression(comex.BooleanExpression(True))
#         es.annotate(a)
#         self.assertTrue(es.indexable_by_key() is True)
#         es = odata.EntitySet()
#         # by default, entity sets are indexable by key
#         self.assertTrue(es.indexable_by_key() is True)
#         a = types.Annotation.from_term_ref(
#                 names.TermRef.from_str(
#                     "@Org.OData.Capabilities.V1.IndexableByKey"), self.em)
#         a.set_expression(comex.BooleanExpression(False))
#         es.annotate(a)
#         self.assertTrue(es.indexable_by_key() is False)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
