#! /usr/bin/env python

import io
import logging
import os.path
import sys
import unittest
import zipfile

import pyslet.py26 as py26


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(Python26Tests, 'test'),
    ))


TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_py26')


class Python26Tests(unittest.TestCase):

    def test_py26(self):
        if sys.version_info[0] == 2 and sys.version_info[1] == 6:
            self.assertTrue(py26.py26)
        else:
            self.assertFalse(py26.py26)

    def test_io(self):
        self.assertTrue(io.SEEK_SET == 0)
        self.assertTrue(io.SEEK_CUR == 1)
        self.assertTrue(io.SEEK_END == 2)

    def test_zip(self):
        zip_path = os.path.join(TEST_DATA_DIR, "test.zip")
        self.assertTrue(zipfile.is_zipfile(zip_path))
        with open(zip_path, 'rb') as f:
            self.assertTrue(zipfile.is_zipfile(f))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
