#! /usr/bin/env python
"""Runs unit tests on all pyslet modules"""

from pyslet.py2 import py2
from pyslet.py26 import py26

import unittest
import logging
import sys

all_tests = unittest.TestSuite()
if py2:
    import test_blockstore
    all_tests.addTest(test_blockstore.suite())
import test_html401
all_tests.addTest(test_html401.suite())
import test_http_auth
all_tests.addTest(test_http_auth.suite())
import test_http_client
all_tests.addTest(test_http_client.suite())
import test_http_cookie
all_tests.addTest(test_http_cookie.suite())
import test_http_grammar
all_tests.addTest(test_http_grammar.suite())
import test_http_messages
all_tests.addTest(test_http_messages.suite())
import test_http_params
all_tests.addTest(test_http_params.suite())
import test_http_server
all_tests.addTest(test_http_server.suite())
if py2:
    import test_imsbltiv1p0
    all_tests.addTest(test_imsbltiv1p0.suite())
if py2:
    import test_imscc_profilev1p0
    all_tests.addTest(test_imscc_profilev1p0.suite())
if py2:
    import test_imscc_profilev1p1
    all_tests.addTest(test_imscc_profilev1p1.suite())
if py2:
    import test_imscpv1p2
    all_tests.addTest(test_imscpv1p2.suite())
if py2:
    import test_imsmdv1p2p1
    all_tests.addTest(test_imsmdv1p2p1.suite())
if py2:
    import test_imsqtiv1p2p1
    all_tests.addTest(test_imsqtiv1p2p1.suite())
if py2:
    import test_imsqtiv2p1
    all_tests.addTest(test_imsqtiv2p1.suite())
import test_iso8601
all_tests.addTest(test_iso8601.suite())
import test_odata2_core
all_tests.addTest(test_odata2_core.suite())
if py2:
    import test_odata2_client
    all_tests.addTest(test_odata2_client.suite())
import test_odata2_csdl
all_tests.addTest(test_odata2_csdl.suite())
import test_odata2_edmx
all_tests.addTest(test_odata2_edmx.suite())
if py2:
    import test_odata2_memds
    all_tests.addTest(test_odata2_memds.suite())
import test_odata2_metadata
all_tests.addTest(test_odata2_metadata.suite())
if py2:
    import test_odata2_server
    all_tests.addTest(test_odata2_server.suite())
if py2:
    import test_odata2_sqlds
    all_tests.addTest(test_odata2_sqlds.suite())
import test_pep8
all_tests.addTest(test_pep8.suite())
import test_py2
all_tests.addTest(test_py2.suite())
import test_py26
all_tests.addTest(test_py26.suite())
if py2:
    import test_qml420
    all_tests.addTest(test_qml420.suite())
import test_rfc2396
all_tests.addTest(test_rfc2396.suite())
import test_rfc4287
all_tests.addTest(test_rfc4287.suite())
import test_rfc5023
all_tests.addTest(test_rfc5023.suite())
if py2:
    import test_rtf_1p6
    all_tests.addTest(test_rtf_1p6.suite())
import test_streams
all_tests.addTest(test_streams.suite())
import test_unicode5
all_tests.addTest(test_unicode5.suite())
import test_urn
all_tests.addTest(test_urn.suite())
import test_vfs
all_tests.addTest(test_vfs.suite())
if py2:
    import test_wsgi
    all_tests.addTest(test_wsgi.suite())
import test_xml_namespace
all_tests.addTest(test_xml_namespace.suite())
import test_xml_parser
all_tests.addTest(test_xml_parser.suite())
import test_xml_structures
all_tests.addTest(test_xml_structures.suite())
import test_xml_xsdatatypes
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
