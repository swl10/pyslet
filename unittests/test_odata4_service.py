#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4.errors import (
    Req40,
    )
import pyslet.odata4.service as odata


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ServiceTests, 'test'),
        ))


class ServiceTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.save_req = odata.Requirement
        odata.Requirement = Req40
        # create a service to use for testing

    def tearDown(self):     # noqa
        odata.Requirement = self.save_req


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
