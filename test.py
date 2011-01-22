#! /usr/bin/env python

import unittest

suite=unittest.TestSuite()

# IEEE Modules
from PyAssess.ieee import test_p1484_12
suite.addTest(test_p1484_12.suite())

# IETF Modules
from PyAssess.ietf import test_rfc1738
suite.addTest(test_rfc1738.suite())
from PyAssess.ietf import test_rfc2234
suite.addTest(test_rfc2234.suite())
from PyAssess.ietf import test_rfc2396
suite.addTest(test_rfc2396.suite())
from PyAssess.ietf import test_rfc2425
suite.addTest(test_rfc2425.suite())
from PyAssess.ietf import test_rfc2426
suite.addTest(test_rfc2426.suite())
from PyAssess.ietf import test_rfc3066
suite.addTest(test_rfc3066.suite())

# IMS Modules
from PyAssess.ims import test_cp
suite.addTest(test_cp.suite())
from PyAssess.ims import test_md
suite.addTest(test_md.suite())
from PyAssess.ims.qti import test_metadata
suite.addTest(test_metadata.suite())
from PyAssess.ims.qti import test_assessmentItem
suite.addTest(test_assessmentItem.suite())
from PyAssess.ims.qti import test_session
suite.addTest(test_session.suite())
from PyAssess.ims.qti import test_deliveryEngine
suite.addTest(test_deliveryEngine.suite())

# ISO Modules
from PyAssess.iso import test_iso639
suite.addTest(test_iso639.suite())
from PyAssess.iso import test_iso8601
suite.addTest(test_iso8601.suite())

# W3C Modules
from PyAssess.w3c import test_xml
suite.addTest(test_xml.suite())
from PyAssess.w3c import test_xmlnamespaces
suite.addTest(test_xmlnamespaces.suite())
from PyAssess.w3c import test_xmlschema
suite.addTest(test_xmlschema.suite())

if __name__ == "__main__":
	runner=unittest.TextTestRunner()
	runner.run(suite)

