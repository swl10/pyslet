#! /usr/bin/env python

import logging
import unittest
import os

import pyslet.xml.structures as xml
import pyslet.rfc2396 as uri

import pyslet.odata2.csdl as edm
import pyslet.odata2.edmx as edmx


TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_odatav2', 'edmx')


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(EDMXTests)
    ))


def load_tests(loader, tests, pattern):
    return suite()


class EDMXTests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(
            edmx.EDMX_NAMESPACE ==
            "http://schemas.microsoft.com/ado/2007/06/edmx",
            "Wrong EDMX namespace: %s" % edmx.EDMX_NAMESPACE)

    def test_edmx(self):
        e = edmx.Edmx(None)
        self.assertTrue(
            isinstance(e, xml.Element), "Edmx not an XML element")
        self.assertTrue(e.ns == edmx.EDMX_NAMESPACE, "Edmx namespace")
        self.assertTrue(e.version == "1.0", "Edmx version")
        self.assertTrue(
            len(e.Reference) == 0,
            "No Reference children allowed on construction")
        self.assertTrue(
            len(e.AnnotationsReference) == 0,
            "No AnnotationReference children allowed on construction")
        self.assertTrue(
            isinstance(e.DataServices, edmx.DataServices),
            "No DataServices element")
        self.assertTrue(len(e.DataServices.Schema) == 0,
                        "No Schema children allowed on construction")

    def test_valid_metadata_examples(self):
        dpath = os.path.join(TEST_DATA_DIR, 'valid')
        for fName in os.listdir(dpath):
            if fName[-4:] != ".xml":
                continue
            logging.debug("testing valid Edmx file %s", fName)
            f = uri.URI.from_path(os.path.join(dpath, fName))
            doc = edmx.Document(base_uri=f)
            try:
                doc.read()
                doc.validate()
            except (edm.ModelError, edm.DuplicateName) as e:
                self.fail("%s is valid but raised "
                          "InvalidMetadataDocument: %s" % (fName, str(e)))

    def test_invalid_metadata_examples(self):
        dpath = os.path.join(TEST_DATA_DIR, 'invalid')
        for fName in os.listdir(dpath):
            if fName[-4:] != ".xml":
                continue
            logging.debug("testing invalid Edmx file %s", fName)
            f = uri.URI.from_path(os.path.join(dpath, fName))
            doc = edmx.Document(base_uri=f)
            try:
                doc.read()
                doc.validate()
                self.fail("%s is invalid but did not raise "
                          "InvalidMetadataDocument" % fName)
            except (edm.ModelError, edm.DuplicateName):
                pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
