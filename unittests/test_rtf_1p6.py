#! /usr/bin/env python

import unittest

from pyslet import rtf_1p6 as rtf   # noqa


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(RTFTests)
    ))


def load_tests(loader, tests, pattern):
    return suite()


class RTFTests(unittest.TestCase):

    def test_constants(self):
        pass


if __name__ == "__main__":
    unittest.main()
