#! /usr/bin/env python

import logging
import os
import unittest

from pyslet.odata2 import csdl as edm
from pyslet.odata2 import metadata as edmx
from pyslet import rfc2396 as uri


TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_odatav2', 'metadata')


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(EDMXTests)
    ))


def load_tests(loader, tests, pattern):
    return suite()


class EDMXTests(unittest.TestCase):

    def test_valid_metadata_examples(self):
        dpath = os.path.join(TEST_DATA_DIR, 'valid')
        for fName in os.listdir(dpath):
            if fName[-4:] != ".xml":
                continue
            logging.debug("testing valid metadata file %s", fName)
            f = uri.URI.from_path(os.path.join(dpath, fName))
            doc = edmx.Document(base_uri=f)
            doc.read()
            try:
                doc.validate()
            except edm.InvalidMetadataDocument as e:
                self.fail("%s is valid but raised "
                          "InvalidMetadataDocument: %s" % (fName, str(e)))

    def test_invalid_metadata_examples(self):
        dpath = os.path.join(TEST_DATA_DIR, 'invalid')
        for fName in os.listdir(dpath):
            if fName[-4:] != ".xml":
                continue
            logging.debug("testing invalid metadata file %s", fName)
            f = uri.URI.from_path(os.path.join(dpath, fName))
            doc = edmx.Document(base_uri=f)
            doc.read()
            try:
                doc.validate()
                self.fail("%s is invalid but did not raise "
                          "InvalidMetadataDocument" % fName)
            except edm.InvalidMetadataDocument:
                pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
