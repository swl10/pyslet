#! /usr/bin/env python

import decimal
import logging
import traceback
import unittest
import uuid

from pyslet import iso8601 as iso
from pyslet.odata4 import errors
from pyslet.odata4 import geotypes as geo
from pyslet.odata4 import model as odata
from pyslet.odata4 import metadata as csdl
from pyslet.odata4 import primitive
from pyslet.rfc2396 import URI
from pyslet.vfs import OSFilePath
from pyslet.xml.namespace import XMLNSParser
from pyslet.xml.structures import XMLValidityError
from pyslet.xml.xsdatatypes import Duration


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(NamespaceTests, 'test'),
        ))


TEST_DATA_DIR = OSFilePath(__file__).split()[0].join('data_odata4')


class NamespaceTests(unittest.TestCase):

    def test_edmx_values(self):
        self.assertTrue(
            csdl.PACKAGING_NAMESPACE ==
            'http://docs.oasis-open.org/odata/ns/edmx')
        self.assertTrue(
            csdl.edmx_version('http://docs.oasis-open.org/odata/ns/edmx') ==
            (4, 0), "Edmx 40")
        self.assertTrue(
            csdl.edmx_version('http://DOCS.oasis-open.org/odata/ns/edmx') ==
            (4, 0), "Edmx 40")
        self.assertTrue(
            csdl.edmx_version(
                'http://docs.oasis-open.org:80/odata/ns/edmx') == (4, 0),
            "Edmx 40")
        self.assertTrue(
            csdl.edmx_version(
                URI.from_octets(
                    'http://docs.oasis-open.org/odata/ns/edmx')) == (4, 0),
            "Edmx 4.0")
        self.assertTrue(
            csdl.edmx_version(
                'http://schemas.microsoft.com/ado/2007/06/edmx') == (1, 0),
            "Edmx 1.0")
        self.assertTrue(
            csdl.edmx_version(
                'http://schemas.microsoft.com/ado/2000/01/edmx') is None,
            "Unknown Edmx version")

    def test_edm_values(self):
        self.assertTrue(
            csdl.EDM_NAMESPACE ==
            'http://docs.oasis-open.org/odata/ns/edm')
        self.assertTrue(
            csdl.edm_version(
                'http://schemas.microsoft.com/ado/2006/04/edm') == (1, 0),
            "Edm 1.0")
        self.assertTrue(
            csdl.edm_version(
                URI.from_octets(
                    'http://schemas.microsoft.com/ado/2006/04/edm')) ==
            (1, 0), "Edm 1.0")
        self.assertTrue(
            csdl.edm_version(
                'http://schemas.microsoft.com/ado/2007/05/edm') == (1, 1),
            "Edm 1.1")
        self.assertTrue(
            csdl.edm_version(
                'http://schemas.microsoft.com/ado/2008/01/edm') == (1, 2),
            "Edm 1.2")
        self.assertTrue(
            csdl.edm_version(
                'http://schemas.microsoft.com/ado/2008/09/edm') == (2, 0),
            "Edm 2.0")
        self.assertTrue(
            csdl.edm_version(
                'http://schemas.microsoft.com/ado/2009/11/edm') == (3, 0),
            "Edm 3.0")
        self.assertTrue(
            csdl.edm_version(
                'http://schemas.microsoft.com/ado/2000/01/edm') is None,
            "Unknown Edm version")


class ValidatingParser(XMLNSParser):

    def __init__(self, entity):
        super(ValidatingParser, self).__init__(entity)
        self.raiseValidityErrors = True


class CSDLDocumentTests(unittest.TestCase):

    valid_example = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx"
    Version="4.0">
    <edmx:DataServices>
        <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"></Schema>
    </edmx:DataServices>
</edmx:Edmx>"""

    def setUp(self):        # noqa
        self.save_req = errors.Requirement
        errors.Requirement = errors.Req40

    def tearDown(self):     # noqa
        errors.Requirement = self.save_req

    def test_container(self):
        # The metadata document contains a single entity container
        # TODO
        pass

    def test_edmx(self):
        # A CSDL document MUST contain a root edmx:Edmx element
        e = csdl.Edmx(None)
        self.assertTrue(e.get_xmlname() == (csdl.PACKAGING_NAMESPACE, 'Edmx'))
        self.assertTrue(e.version == "4.0")
        self.assertTrue(e.DataServices is not None)
        self.assertTrue(isinstance(e.DataServices, csdl.DataServices))
        # none or more Reference elements...
        self.assertTrue(isinstance(e.Reference, list))
        self.assertTrue(len(e.Reference) == 0)
        # check the entity model is present and open
        self.assertTrue(isinstance(e.entity_model, odata.EntityModel))
        self.assertTrue(e.entity_model.closed is False)

    def test_data_services(self):
        e = csdl.DataServices(None)
        self.assertTrue(
            e.get_xmlname() == (csdl.PACKAGING_NAMESPACE, 'DataServices'))
        self.assertTrue(isinstance(e.Schema, list))
        self.assertTrue(len(e.Schema) == 0, "initially empty")

    def test_reference(self):
        e = csdl.Reference(None)
        self.assertTrue(
            e.get_xmlname() == (csdl.PACKAGING_NAMESPACE, 'Reference'))
        self.assertTrue(e.uri is None)
        self.assertTrue(isinstance(e.ReferenceContent, list))
        self.assertTrue(len(e.ReferenceContent) == 0, "initially empty")
        # TODO check directly referenced definitions are in the
        # entity_model
        dpath = TEST_DATA_DIR.join('valid', 'section-3.3-direct.xml')
        uri = URI.from_virtual_path(dpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        # types.pyslet.org is reference and should be present
        self.assertTrue("types.pyslet.org" in em)
        # other namespaces defined or referenced there should not be
        # present
        self.assertFalse("odata.pyslet.org" in em)
        self.assertFalse("simple.pyslet.org" in em)

    def test_include(self):
        e = csdl.Include(None)
        self.assertTrue(
            e.get_xmlname() == (csdl.PACKAGING_NAMESPACE, 'Include'))
        self.assertTrue(e.namespace is None)
        self.assertTrue(e.alias is None)

    def test_include_annotations(self):
        e = csdl.IncludeAnnotations(None)
        self.assertTrue(
            e.get_xmlname() == (csdl.PACKAGING_NAMESPACE,
                                'IncludeAnnotations'))
        self.assertTrue(e.term_namespace is None)
        self.assertTrue(e.qualifier is None)
        self.assertTrue(e.target_namespace is None)

    def test_section_4_4(self):
        # TODO: Edm.Stream, or a type definition whose underlying type
        # is Edm.Stream, cannot be used in collections or for
        # non-binding parameters to functions or actions.
        pass

    def test_section_4_5(self):
        # TODO: Edm.EntityType cannot be used as the type of a singleton
        # in an entity container
        # TODO: Edm.EntityType cannot be used as the type of an entity
        # set
        # TODO: Edm.EntityType cannot be the base type of an entity type
        # or complex type.
        # TODO: Edm.ComplexType cannot be the base type of an entity
        # type or complex type
        # TODO: Edm.PrimitiveType cannot be used as the type of a key
        # property of an entity type
        # TODO: Edm.PrimitiveType cannot be used as the underlying type
        # of a type definition or enumeration type
        # TODO: Collection(Edm.PrimitiveType) cannot be used as the type
        # of a property
        # TODO: Collection(Edm.PrimitiveType) cannot be used as the
        # return type of a function
        # TODO: Collection(Edm.ComplexType)) cannot be used as the type
        # of a property
        # TODO: Collection(Edm.ComplexType)) cannot be used as the
        # return type of a function
        pass

    def test_section_6_2_1(self):
        # If no value is specified for a property whose Type attribute
        # does not specify a collection, the Nullable attribute defaults
        # to true
        fpath = TEST_DATA_DIR.join('valid', 'section-6.2.1.xml')
        uri = URI.from_virtual_path(fpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        # Measurement.Dimension should be nullable
        s = em['test.pyslet.org']
        p = s['Measurement']['Dimension']
        self.assertTrue(p.nullable)
        # If no value is specified for a property whose Type attribute
        # specifies a collection, the client cannot assume any default
        # value.
        # Specifications.Weight has indeterminate nullability
        p = s['Specifications']['Weight']
        self.assertTrue(p.nullable is None)
        # If the edm:Property element contains a Type attribute that
        # specifies a collection, the property MUST always exist...
        # The absence of the Nullable attribute means it is unknown
        # whether the collection can contain null values.
        ct = s['Specifications']
        v = ct()
        v.set_defaults()
        self.assertTrue(v['Weight'] is not None, "property exists")

    def test_section_6_2_7_defaults(self):
        # A primitive or enumeration property MAY define a value for the
        # DefaultValue attribute.
        fpath = TEST_DATA_DIR.join('valid', 'section-6.2.7-defaults.xml')
        uri = URI.from_virtual_path(fpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        s = em['test.pyslet.org']
        data = (
            ('BinaryTest', primitive.BinaryValue, b'Caf\xc3\xa9'),
            ('BooleanTest', primitive.BooleanValue, True),
            ('ByteTest', primitive.ByteValue, 239),
            ('DateTest', primitive.DateValue, iso.Date(
                century=20, year=17, month=5, day=30)),
            ('DateTimeOffsetTest', primitive.DateTimeOffsetValue,
             iso.TimePoint(
                date=iso.Date(century=20, year=17, month=5, day=30),
                time=iso.Time(hour=4, minute=20, second=00, zdirection=1,
                              zhour=1, zminute=0))),
            ('DecimalTest', primitive.DecimalValue,
             decimal.Decimal('3.14159')),
            ('DoubleTest', primitive.DoubleValue, 3.1416015625),
            ('DurationTest', primitive.DurationValue, Duration("PT1S")),
            ('GeographyPointTest', primitive.GeographyPointValue,
             geo.PointLiteral(
                srid=4326, point=geo.Point(-1.00244140625, 51.44775390625))),
            ('GeographyLineStringTest', primitive.GeographyLineStringValue,
             geo.LineStringLiteral(
                srid=4326, line_string=geo.LineString(
                    ((-1.00244140625, 51.44775390625),
                     (-0.9964599609375, 51.455810546875))))),
            ('GeographyPolygonTest', primitive.GeographyPolygonValue,
             geo.PolygonLiteral(srid=4326, polygon=geo.Polygon(
                (((-1.003173828125, 51.439697265625),
                  (-1.0029296875, 51.4437255859375),
                  (-1.001708984375, 51.4437255859375),
                  (-1.001708984375, 51.439697265625),
                  (-1.003173828125, 51.439697265625)),
                 )))),
            ('GeographyMultiPointTest', primitive.GeographyMultiPointValue,
             geo.MultiPointLiteral(
                srid=4326, multipoint=(
                    geo.Point(-1.00244140625, 51.44775390625),
                    geo.Point(-0.9964599609375, 51.455810546875)))),
            ('GeographyMultiLineStringTest',
             primitive.GeographyMultiLineStringValue,
             geo.MultiLineStringLiteral(
                srid=4326, multi_line_string=(
                    geo.LineString(((-1.00244140625, 51.44775390625),
                                    (-0.9964599609375, 51.455810546875))),
                    ))),
            ('GeographyMultiPolygonTest', primitive.GeographyMultiPolygonValue,
             geo.MultiPolygonLiteral(
                srid=4326, multi_polygon=(
                    geo.Polygon((((-1.003173828125, 51.439697265625),
                                  (-1.0029296875, 51.4437255859375),
                                  (-1.001708984375, 51.4437255859375),
                                  (-1.001708984375, 51.439697265625),
                                  (-1.003173828125, 51.439697265625)),
                                 )),
                    ))),
            ('GeographyCollectionTest', primitive.GeographyCollectionValue,
             geo.GeoCollectionLiteral(
                srid=4326, items=(
                    geo.Point(-1.00244140625, 51.44775390625),
                    geo.LineString(((-1.00244140625, 51.44775390625),
                                    (-0.9964599609375, 51.455810546875)))
                    ))),
            ('GeometryPointTest', primitive.GeometryPointValue,
             geo.PointLiteral(srid=0, point=geo.Point(1.0, -1.0))),
            ('GeometryLineStringTest', primitive.GeometryLineStringValue,
             geo.LineStringLiteral(
                srid=0, line_string=geo.LineString(
                    ((1.0, -1.0), (-1.0, 1.0))))),
            ('GeometryPolygonTest', primitive.GeometryPolygonValue,
             geo.PolygonLiteral(srid=0, polygon=geo.Polygon(
                (((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0),
                  (1.0, -1.0)), )
                ))),
            ('GeometryMultiPointTest', primitive.GeometryMultiPointValue,
             geo.MultiPointLiteral(
                srid=0, multipoint=(
                    geo.Point(1.0, -1.0), geo.Point(-1.0, 1.0)))),
            ('GeometryMultiLineStringTest',
             primitive.GeometryMultiLineStringValue,
             geo.MultiLineStringLiteral(
                srid=0, multi_line_string=(
                    geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
                    geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
                    ))),
            ('GeometryMultiPolygonTest', primitive.GeometryMultiPolygonValue,
             geo.MultiPolygonLiteral(
                srid=0, multi_polygon=(
                    geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                                  (-1.0, -1.0), (1.0, -1.0)), )),
                    geo.Polygon((((4.0, -1.0), (4.0, 1.0), (2.0, 1.0),
                                  (2.0, -1.0), (4.0, -1.0)), ))
                    ))),
            ('GeometryCollectionTest', primitive.GeometryCollectionValue,
             geo.GeoCollectionLiteral(
                srid=0, items=(
                    geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
                    geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
                    geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                                  (-1.0, -1.0), (1.0, -1.0)), )),
                    ))),
            ('GuidTest', primitive.GuidValue, uuid.UUID(int=0xdeadbeef)),
            ('Int16Test', primitive.Int16Value, -16657),
            ('Int32Test', primitive.Int32Value, -559038737),
            ('Int64Test', primitive.Int64Value, 3735928559),
            ('SByteTest', primitive.SByteValue, -17),
            ('SingleTest', primitive.SingleValue, 3.1416015625),
            ('StringTest', primitive.StringValue, "Fish&Chips"),
            ('TimeOfDayTest', primitive.TimeOfDayValue,
             iso.Time(hour=4, minute=20, second=0)),
            ('EnumTest', odata.EnumerationValue, 1)
            )
        for pname, ptype, default in data:
            p = s['DefaultTest'][pname]
            self.assertTrue(
                isinstance(p.default_value, ptype),
                "%s (Expected %s)" % (repr(p.default_value), repr(ptype)))
            self.assertTrue(
                p.default_value.value == default,
                "Default: %s = %s" % (pname, repr(p.default_value.value)))

    def test_section_13_1_2_cycle(self):
        # services should not introduce cycles with Extends. Clients
        # should be prepared to process cycles introduced with Extends.
        fpath = TEST_DATA_DIR.join('valid', 'section-13.1.2-cycle.xml')
        uri = URI.from_virtual_path(fpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        s = em['test.pyslet.org']
        container_a = s['ContainerA']
        container_b = s['ContainerB']
        # the cycle between these contains simply means that all
        # definitions in A are in B *and* vice versa
        self.assertTrue(len(container_a) == 2)
        self.assertTrue(len(container_b) == 2)

    def test_valid_examples(self):
        dpath = TEST_DATA_DIR.join('valid')
        for fname in dpath.listdir():
            stem, ext = fname.splitext()
            if ext != ".xml":
                continue
            uri = URI.from_virtual_path(dpath.join(fname))
            doc = csdl.CSDLDocument(base_uri=uri)
            logging.debug("Validating: %s", str(uri))
            try:
                doc.read()
            except errors.ModelError as err:
                self.fail("%s raised by %s" % (str(err), str(fname)))

    def test_invalid_examples(self):
        dpath = TEST_DATA_DIR.join('invalid')
        for fname in dpath.listdir():
            # if 'dupbinding' not in str(fname):
            #    continue
            stem, ext = fname.splitext()
            if ext != ".xml":
                continue
            # if the test is of the form test-* look for mention of the
            # suffix in the exception message.
            parts = str(fname).split('-')
            if len(parts) >= 2 and parts[0] == 'section':
                sid = parts[1]
            else:
                sid = None
            uri = URI.from_virtual_path(dpath.join(fname))
            doc = csdl.CSDLDocument(base_uri=uri)
            doc.XMLParser = ValidatingParser
            logging.debug("Checking: %s", str(uri))
            try:
                doc.read()
                self.fail("%s validated" % str(fname))
            except errors.ODataError as err:
                msg = str(err)
                long_msg = traceback.format_exc()
            except XMLValidityError as err:
                msg = str(err)
                long_msg = traceback.format_exc()
            if sid is not None:
                logging.debug(msg)
                self.assertTrue(
                    sid in msg.split(),
                    "%s raised %s\n%s" % (str(fname), msg, long_msg))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
