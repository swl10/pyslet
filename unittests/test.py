#! /usr/bin/env python

"""Runs unit tests on all pyslet modules"""

import unittest

import test_iso8601
import test_rfc2234

def suite():
	s=unittest.TestSuite()
	s.addTest(test_rfc2234.suite())
	s.addTest(test_iso8601.suite())
	return s
	
if __name__ == "__main__":
	runner=unittest.TextTestRunner()
	runner.run(suite())