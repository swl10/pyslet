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
        # TODO check indirectly referenced definitions are not in the
        # entity_model

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
        # An edmx:IncludeAnnotations element MUST provide a Namespace
        # value for the TermNamespace attribute

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
