#! /usr/bin/env python

import logging
import unittest

import pyslet.odata4.client as client
from pyslet.odata4.errors import (
    Requirement,
    )
import pyslet.odata4.metadata as csdlxml
import pyslet.odata4.model as csdl
import pyslet.odata4.service as odata
from pyslet.py2 import (
    output,
    to_text,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(URITests, 'test'),
        unittest.makeSuite(StaticTests, 'test'),
        ))


class URITests(unittest.TestCase):

    def test_constructor(self):
        # default constructor has empty service root URL, no query
        # options and just the path to the service root
        odata_url = client.ODataURL()
        self.assertTrue(odata_url.service_root == "/")
        self.assertTrue(odata_url.resource_path == [])
        self.assertTrue(isinstance(odata_url.query_options, dict))
        self.assertFalse(odata_url.query_options)

    def test_from_str(self):
        # RFC3986 steps for URL processing that MUST be performed before
        # percent-decoding...
        odata_url = client.ODataURL.from_str(
            "http://www.example.com/svc%2F%25q%3D1&/path?"
            "query?=%23=%3F&q=%252F#Hello#Mum")
        # By default we assume that the service is located at the root
        # path
        output(to_text(odata_url.query_options) + "\n")
        self.assertTrue(odata_url.service_root == "http://www.example.com/")
        self.assertTrue(len(odata_url.resource_path) == 2,
                        Requirement.path_split)
        self.assertTrue(len(odata_url.query_options) == 2,
                        Requirement.url_split)
        self.assertTrue(odata_url.query_options["query?"] == "#=?",
                        Requirement.query_split)
        self.assertTrue(odata_url.query_options["q"] == "%2F",
                        Requirement.percent_decode)
        self.assertTrue(odata_url.resource_path[0] == "svc/%q=1&",
                        Requirement.percent_decode)
        self.assertTrue(odata_url.resource_path[1] == "path",
                        Requirement.path_split)


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
        self.subtest_people(svc)

    def subtest_people(self, svc):
        # to access an entity set you need to open it
        people = svc.open("People")
        self.assertTrue(len(people) == 20)
        # now iterate through all the entities
        keys = []
        for e in people.values():
            user_name = e["UserName"]
            self.assertTrue(user_name)
            self.assertTrue(isinstance(user_name, csdl.StringValue))
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
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
