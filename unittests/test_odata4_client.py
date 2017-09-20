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
        # self.subtest_requesting_data(svc)
        self.subtest_querying_data(svc)
        # self.subtest_people(svc)
        # self.subtest_friends(svc)
        # self.subtest_employees(svc)

    def subtest_requesting_data(self, svc):
        people = svc.open("People")
        # Requesting EntitySet
        for e in people.values():
            user_name = e["UserName"]
            self.assertTrue(user_name)
            self.assertTrue(isinstance(user_name, primitive.StringValue))
            logging.info("UserName: %s (%s)", user_name.value,
                         e.type_def.name)
        # Requesting Single Entity by ID
        people.clear_cache()
        russellwhyte = people['russellwhyte']
        self.assertTrue(
            russellwhyte["UserName"].get_value() == "russellwhyte")
        # Requesting Single Property Value
        airports = svc.open("Airports")
        ksfo = airports['KSFO']
        name = ksfo['Name']
        # force a reload of a specific property
        self.assertTrue(name.get_value() ==
                        "San Francisco International Airport")
        name.set_value("Modified")
        name.reload()
        self.assertTrue(name.get_value() ==
                        "San Francisco International Airport")
        address = ksfo["Location"]["Address"]
        self.assertTrue(address.get_value() ==
                        "South McDonnell Road, San Francisco, CA 94128")
        address.set_value("Modified")
        address.reload()
        self.assertTrue(address.get_value() ==
                        "South McDonnell Road, San Francisco, CA 94128")
        # Requesting a Single Primitive or Enum Type Property Raw Value
        # currently not implemented, we use json syntax for all props
        # Requesting Complex Property
        location = ksfo["Location"]
        address.set_value("Modified")
        location.reload()
        self.assertTrue(address.get_value() ==
                        "South McDonnell Road, San Francisco, CA 94128")
        # Requesting Collection of Complex Property
        address_info = russellwhyte['AddressInfo']
        address_info.clear_cache()
        for a in address_info:
            logging.info("Address: %s (%s)", a['Address'].get_value(),
                         a['City']['Name'].get_value())

    def subtest_querying_data(self, svc):
        people = svc.open("People")
        # System Query Option $filter
        people.set_filter("FirstName eq 'Scott'")
        for e in people.values():
            user_name = e["UserName"]
            self.assertTrue(user_name)
            self.assertTrue(isinstance(user_name, primitive.StringValue))
            logging.info("UserName: %s (%s)", user_name.value,
                         e.type_def.name)
        airports = svc.open("Airports")
        airports.set_filter("contains(Location/Address, 'San Francisco')")
        for e in airports.values():
            name = e["Name"]
            self.assertTrue(name)
            self.assertTrue(isinstance(name, primitive.StringValue))
            logging.info("Airport Name: %s (%s)", name.get_value(),
                         e.type_def.name)
        people.set_filter(
            "Gender eq Microsoft.OData.Service.Sample.TrippinInMemory."
            "Models.PersonGender'Female'")
        for e in people.values():
            user_name = e["UserName"]
            logging.info("UserName: %s (%s)", user_name.value,
                         e.type_def.name)
        airports.set_filter(None)
        airports.select("Name")
        airports.select("IcaoCode")
        for e in airports.values():
            name = e["Name"]
            code = e["IcaoCode"]
            self.assertTrue("IataCode" not in e)
            logging.info("Airport Name: %s (%s)", name.get_value(),
                         code.get_value())

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
        # initially friends is not expanded
        self.assertTrue("Friends" not in kristakemp)
        people.expand("Friends")
        kristakemp = people['kristakemp']
        self.assertTrue(kristakemp.get_key() == 'kristakemp')
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

    def subtest_employees(self, svc):
        employee = svc.model.qualified_get(
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models.Employee")
        employees = svc.container["People"]()
        employees.type_cast(employee)
        self.assertTrue(len(employees) == 1)
        kristakemp = employees.values()[0]
        self.assertTrue(kristakemp.type_def is employee)
        self.assertTrue(kristakemp['UserName'] == 'kristakemp')


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
