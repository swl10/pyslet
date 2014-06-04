#! /usr/bin/env python

import unittest


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(RTFTests)
    ))


def load_tests(loader, tests, pattern):
    return suite()


from pyslet.rtf_1p6 import *


class RTFTests(unittest.TestCase):

    def testCaseConstants(self):
        pass


if __name__ == "__main__":
    unittest.main()
