#! /usr/bin/env python
"""Runs unit tests on all pyslet modules"""

import unittest
import logging
import sys

from pyslet.py26 import py26

import test_blockstore
import test_html401
import test_http_auth
import test_http_client
import test_http_cookie
import test_http_grammar
import test_http_messages
import test_http_multipart
import test_http_params
import test_http_server
import test_imsbltiv1p0
import test_imscc_profilev1p0
import test_imscc_profilev1p1
import test_imscpv1p2
import test_imsmdv1p2p1
import test_imsqtiv1p2p1
import test_imsqtiv2p1
import test_iso8601
import test_odata2_core
import test_odata2_client
import test_odata2_csdl
import test_odata2_edmx
import test_odata2_memds
import test_odata2_metadata
import test_odata2_server
import test_odata2_sqlds
import test_pep8
import test_py2
import test_py26
import test_qml420
import test_rfc2396
import test_rfc4287
import test_rfc5023
import test_rtf_1p6
import test_streams
import test_unicode5
import test_urn
import test_vfs
import test_wsgi
import test_xml_namespace
import test_xml_parser
import test_xml_structures
import test_xml_xsdatatypes


all_tests = unittest.TestSuite()
all_tests.addTest(test_blockstore.suite())
all_tests.addTest(test_html401.suite())
all_tests.addTest(test_http_auth.suite())
all_tests.addTest(test_http_client.suite())
all_tests.addTest(test_http_cookie.suite())
all_tests.addTest(test_http_grammar.suite())
all_tests.addTest(test_http_messages.suite())
all_tests.addTest(test_http_multipart.suite())
all_tests.addTest(test_http_params.suite())
all_tests.addTest(test_http_server.suite())
all_tests.addTest(test_imsbltiv1p0.suite())
all_tests.addTest(test_imscc_profilev1p0.suite())
all_tests.addTest(test_imscc_profilev1p1.suite())
all_tests.addTest(test_imscpv1p2.suite())
all_tests.addTest(test_imsmdv1p2p1.suite())
all_tests.addTest(test_imsqtiv1p2p1.suite())
all_tests.addTest(test_imsqtiv2p1.suite())
all_tests.addTest(test_iso8601.suite())
all_tests.addTest(test_odata2_core.suite())
all_tests.addTest(test_odata2_client.suite())
all_tests.addTest(test_odata2_csdl.suite())
all_tests.addTest(test_odata2_edmx.suite())
all_tests.addTest(test_odata2_memds.suite())
all_tests.addTest(test_odata2_metadata.suite())
all_tests.addTest(test_odata2_server.suite())
all_tests.addTest(test_odata2_sqlds.suite())
all_tests.addTest(test_pep8.suite())
all_tests.addTest(test_py2.suite())
all_tests.addTest(test_py26.suite())
all_tests.addTest(test_qml420.suite())
all_tests.addTest(test_rfc2396.suite())
all_tests.addTest(test_rfc4287.suite())
all_tests.addTest(test_rfc5023.suite())
all_tests.addTest(test_rtf_1p6.suite())
all_tests.addTest(test_streams.suite())
all_tests.addTest(test_unicode5.suite())
all_tests.addTest(test_urn.suite())
all_tests.addTest(test_vfs.suite())
all_tests.addTest(test_wsgi.suite())
all_tests.addTest(test_xml_namespace.suite())
all_tests.addTest(test_xml_parser.suite())
all_tests.addTest(test_xml_structures.suite())
all_tests.addTest(test_xml_xsdatatypes.suite())


def suite():
    global all_tests
    return all_tests


def load_tests(loader, tests, pattern):
    return suite()

if __name__ == "__main__":
    # 	runner=unittest.TextTestRunner()
    # 	runner.run(suite())
    logging.basicConfig(level=logging.ERROR)
    if py26:
        result = unittest.TextTestRunner(verbosity=0).run(suite())
        sys.exit(not result.wasSuccessful())
    else:
        unittest.main()
