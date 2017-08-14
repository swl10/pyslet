#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4 import client
from pyslet.odata4 import metadata as csdlxml
from pyslet.odata4 import model as csdl
from pyslet.odata4 import primitive
from pyslet.odata4 import service as odata


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(StaticTests, 'test'),
        ))


class StaticTests(unittest.TestCase):

    def test_constructor(self):
        # empty constructor
        svc = client.Client()
        self.assertTrue(isinstance(svc, odata.DataService))


class TripPinTests(unittest.TestCase):

    """A set of tests that use the TripPin reference service

    These tests are not included in the standard Pyslet unittest runs
    but are run when this module is tested in isolation."""

    trippin_url = "http://services.odata.org/TripPinRESTierService"
    trippin_ns = "Microsoft.OData.Service.Sample.TrippinInMemory.Models"

    def test_trippin(self):
        svc = client.Client(self.trippin_url)
        self.assertTrue(isinstance(svc, odata.DataService))
        self.assertTrue(isinstance(svc.model, csdl.EntityModel))
        self.assertTrue(isinstance(svc.container, csdl.EntityContainer))
        self.assertTrue(isinstance(svc.metadata, csdlxml.CSDLDocument))
        # There should be a single Schema
        self.assertTrue(len(svc.model) == 3, "Single schema (+Edm +odata)")
        self.assertTrue(self.trippin_ns in svc.model)
        # To preserve context we now execute other tests directly
        # self.subtest_people(svc)
        self.subtest_friends(svc)

    def subtest_people(self, svc):
        # to access an entity set you need to open it
        people = svc.open("People")
        self.assertTrue(len(people) == 20)
        # now iterate through all the entities
        keys = []
        for e in people.values():
            user_name = e["UserName"]
            self.assertTrue(user_name)
            self.assertTrue(isinstance(user_name, primitive.StringValue))
            logging.info("UserName: %s (%s)", user_name.value,
                         e.type_def.name)
            keys.append(user_name.value)
        for k in keys:
            try:
                e = people[k]
            except KeyError:
                self.fail("People(%s) missing" % repr(k))

    def subtest_friends(self, svc):
        people = svc.open("People")
        kristakemp = people['kristakemp']
        self.assertTrue(kristakemp.get_key() == 'kristakemp')
        # initially friends is not expanded
        self.assertTrue("Friends" not in kristakemp)
        kristakemp.expand("Friends")
        self.assertTrue("Friends" in kristakemp)
        self.assertTrue(len(kristakemp["Friends"]) == 1)
        keys = []
        for e in kristakemp["Friends"].values():
            user_name = e["UserName"]
            self.assertTrue(user_name)
            self.assertTrue(isinstance(user_name, primitive.StringValue))
            logging.info("UserName: %s (%s)", user_name.value,
                         e.type_def.name)
            keys.append(user_name.value)
        for k in keys:
            try:
                e = people[k]
            except KeyError:
                self.fail("People(%s) missing" % repr(k))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
