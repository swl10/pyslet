#! /usr/bin/env python

"""Runs unit tests on all pyslet modules"""

import unittest

import test_imsbltiv1p0
import test_imscc_profilev1p0
import test_imscpv1p2
import test_imsmdv1p2p1
import test_imsqtiv1p2p1
import test_imsqtiv2p1
import test_iso8601
import test_rfc2234
import test_rfc2616
import test_rfc4287
import test_rfc5023
import test_unicode5
import test_xml20081126
import test_xmlnames20091208
import test_xsdatatypes20041028

def suite():
	s=unittest.TestSuite()
	s.addTest(test_imsbltiv1p0.suite())
	s.addTest(test_imscc_profilev1p0.suite())
	s.addTest(test_imscpv1p2.suite())
	s.addTest(test_imsmdv1p2p1.suite())
	s.addTest(test_imsqtiv1p2p1.suite())
	s.addTest(test_imsqtiv2p1.suite())
	s.addTest(test_iso8601.suite())
	s.addTest(test_rfc2234.suite())
	s.addTest(test_rfc2616.suite())
	s.addTest(test_rfc4287.suite())
	s.addTest(test_rfc5023.suite())
	s.addTest(test_unicode5.suite())
	s.addTest(test_xml20081126.suite())
	s.addTest(test_xmlnames20091208.suite())
	s.addTest(test_xsdatatypes20041028.suite())
	return s
	
if __name__ == "__main__":
	runner=unittest.TextTestRunner()
	runner.run(suite())