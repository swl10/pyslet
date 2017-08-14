#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4 import model as csdl
from pyslet.odata4 import errors
from pyslet.odata4 import service
from pyslet.odata4 import types
from pyslet.py2 import (
    is_text,
    to_text,
    )
from pyslet.rfc2396 import URI


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ServiceTests, 'test'),
        ))


class ServiceTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.save_req = errors.Requirement
        errors.Requirement = errors.Req40
        self.svc = service.DataService()
        self.svc.model = csdl.EntityModel()

    def tearDown(self):     # noqa
        errors.Requirement = self.save_req

    def test_constructor(self):
        svc = service.DataService()
        self.assertTrue(svc.model is None)
        self.assertTrue(svc.container is None)
        self.assertTrue(svc.context_base is None)
        self.assertTrue(svc.service_root == "/")

    def test_set_context_base(self):
        base_str = "http://www.example.com/$metadata"
        base = URI.from_octets(base_str)
        self.svc.set_context_base(base)
        self.assertTrue(isinstance(self.svc.context_base, URI))
        self.assertTrue(self.svc.context_base == base)
        # the service root URL always terminates in a slash
        self.assertTrue(self.svc.service_root == "http://www.example.com/",
                        self.svc.service_root)
        base_str = "http://www.Example.com:80/$metadata"
        base = URI.from_octets(base_str)
        self.svc.set_context_base(base)
        self.assertTrue(self.svc.context_base == base)
        self.assertTrue(self.svc.service_root == "http://www.example.com/",
                        self.svc.service_root)
        base_str = "http://services.odata.org/TripPinRESTierService/"\
            "(S(dr2fkaae5jkd1a0bzivadkky))/$metadata"
        base = URI.from_octets(base_str)
        self.svc.set_context_base(base)
        # the service root URL always terminates in a slash
        self.assertTrue(
            self.svc.service_root ==
            "http://services.odata.org/TripPinRESTierService/"
            "(S(dr2fkaae5jkd1a0bzivadkky))/")


class URITests(unittest.TestCase):

    def setUp(self):        # noqa
        self.svc = service.DataService()
        self.svc.model = csdl.EntityModel()

    def test_constructor(self):
        # default constructor has empty service root URL, no query
        # options and just the path to the service root
        odata_url = service.ODataURL(self.svc)
        self.assertTrue(odata_url.service is self.svc)
        self.assertTrue(odata_url.resource_path == [])
        self.assertTrue(isinstance(odata_url.query_options, dict))
        self.assertFalse(odata_url.query_options)

    def test_from_str(self):
        # RFC3986 steps for URL processing that MUST be performed before
        # percent-decoding...
        odata_url = self.svc.url_from_str(
            "http://www.example.com/svc%2F%25q%3D1&/path?"
            "query?=%23=%3F&q=%252F#Hello#Mum")
        # self.svc has no context_base so service_root is just '/' with
        # no service_canonical_root, therefore any canonical root
        # matches in the URL string
        self.assertTrue(len(odata_url.resource_path) == 2,
                        errors.Requirement.path_split)
        self.assertTrue(len(odata_url.query_options) == 2,
                        errors.Requirement.url_split)
        self.assertTrue(odata_url.query_options["query?"] == "#=?",
                        errors.Requirement.query_split)
        self.assertTrue(odata_url.query_options["q"] == "%2F",
                        errors.Requirement.percent_decode)
        self.assertTrue(odata_url.resource_path[0] == "svc/%q=1&",
                        errors.Requirement.percent_decode)
        self.assertTrue(odata_url.resource_path[1] == "path",
                        errors.Requirement.path_split)
        tp_root = "http://services.odata.org/TripPinRESTierService/"\
            "(S(dr2fkaae5jkd1a0bzivadkky))/"
        self.svc.set_context_base(URI.from_octets(tp_root + "$metadata"))
        odata_url = self.svc.url_from_str(
            tp_root + "People('kristakemp')/"
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models.Employee")
        self.assertTrue(len(odata_url.resource_path) == 2)
        self.assertTrue(len(odata_url.query_options) == 0)
        self.assertTrue(
            odata_url.resource_path[1] ==
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models.Employee")
        try:
            self.svc.url_from_str(
                "http://services.odata.org/TripPinRESTierService/"
                "(S(badkey))/People('kristakemp')/"
                "Microsoft.OData.Service.Sample.TrippinInMemory.Models."
                "Employee")
            self.fail("service root path mismatch")
        except errors.URLError:
            pass
        # check authority too
        tp_root80 = "http://services.odata.org:80/TripPinRESTierService/"\
            "(S(dr2fkaae5jkd1a0bzivadkky))/"
        odata_url = self.svc.url_from_str(
            tp_root80 + "People('kristakemp')/"
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models.Employee")
        try:
            self.svc.url_from_str(
                "https://services.odata.org/TripPinRESTierService/"
                "(S(dr2fkaae5jkd1a0bzivadkky))/People('kristakemp')/"
                "Microsoft.OData.Service.Sample.TrippinInMemory.Models."
                "Employee")
            self.fail("service canonical root mismatch")
        except errors.URLError:
            pass

    def test_resource_segments(self):
        # entitySetName, singletonEntity or actionImportCall
        odata_url = self.svc.url_from_str("http://host/People")
        self.assertTrue(len(odata_url.resource_path) == 1)
        try:
            odata_url.resource_path_segments[1]
            self.fail("Path segment index")
        except IndexError:
            pass
        seg = odata_url.resource_path_segments[0]
        self.assertTrue(is_text(seg.name))
        self.assertTrue(seg.name == "People")
        self.assertFalse(seg.params)
        # entitySetName, singletonEntity with qualified type
        odata_url = self.svc.url_from_str(
            "http://host/People/my.schema.Manager")
        self.assertTrue(len(odata_url.resource_path) == 2)
        seg = odata_url.resource_path_segments[1]
        self.assertTrue(isinstance(seg.name, types.QualifiedName))
        self.assertTrue(seg.name[0] == "my.schema")
        self.assertTrue(seg.name[1] == "Manager")
        self.assertFalse(seg.params)
        # key predicate
        odata_url = self.svc.url_from_str(
            "http://host/People/my.schema.Manager(25)")
        self.assertTrue(len(odata_url.resource_path) == 2)
        seg = odata_url.resource_path_segments[1]
        self.assertTrue(isinstance(seg.params[''], int))
        self.assertTrue(seg.params[''] == 25)

    def test_string_literals(self):
        valid = (
            "http://host/service/People('O''Neil')",
            "http://host/service/People(%27O%27%27Neil%27)",
            "http://host/service/People%28%27O%27%27Neil%27%29",
            "http://host/service/Categories('Smartphone%2FTablet')",
            )
        invalid = (
            "http://host/service/People('O'Neil')",
            "http://host/service/People('O%27Neil')",
            "http://host/service/Categories('Smartphone/Tablet')",
            )
        for url in valid:
            self.svc.url_from_str(url)
        for url in invalid:
            try:
                self.svc.url_from_str(url)
                self.fail("Invalid URL parsed: %s" % url)
            except errors.URLError as err:
                logging.debug(to_text(err))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
