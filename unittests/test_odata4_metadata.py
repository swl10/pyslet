#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4 import model as odata
from pyslet.odata4 import metadata as csdl
from pyslet.rfc2396 import URI
from pyslet.vfs import OSFilePath


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


class CSDLDocumentTests(unittest.TestCase):

    valid_example = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx"
    Version="4.0">
    <edmx:DataServices>
        <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"></Schema>
    </edmx:DataServices>
</edmx:Edmx>"""

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
        self.assertTrue(v['Weight'] is not None, "property exists")

    def test_valid_examples(self):
        dpath = TEST_DATA_DIR.join('valid')
        for fname in dpath.listdir():
            stem, ext = fname.splitext()
            if ext != ".xml":
                continue
            uri = URI.from_virtual_path(dpath.join(fname))
            doc = csdl.CSDLDocument(base_uri=uri)
            logging.info("Validating: %s", str(uri))
            try:
                doc.read()
                doc.validate()
            except odata.ModelError as err:
                self.fail("%s raised by %s" % (str(err), str(fname)))

    def test_invalid_examples(self):
        dpath = TEST_DATA_DIR.join('invalid')
        for fname in dpath.listdir():
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
            logging.info("Checking: %s", str(uri))
            try:
                doc.read()
                doc.validate()
                self.fail("%s validated" % str(fname))
            except odata.ModelError as err:
                msg = str(err)
            if sid is not None:
                self.assertTrue(sid in msg.split(),
                                "%s raised %s" % (str(fname), msg))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
