#! /usr/bin/env python

import json
import logging
import unittest

from pyslet.http import params as http
from pyslet.odata4 import model as csdl
from pyslet.odata4 import payload
from pyslet.odata4 import service
from pyslet.rfc2396 import URI

from test_odata4_model import load_trippin


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ControlTests, 'test'),
        unittest.makeSuite(ParserTests, 'test'),
        ))


class ControlTests(unittest.TestCase):

    def test_parameters(self):
        self.assertTrue(payload.MetadataAmount.from_str_lower("None") ==
                        payload.MetadataAmount.none)
        self.assertTrue(payload.MetadataAmount.from_str_lower("minimal") ==
                        payload.MetadataAmount.minimal)
        self.assertTrue(payload.MetadataAmount.from_str_lower("FULL") ==
                        payload.MetadataAmount.full)
        self.assertTrue(payload.MetadataAmount.DEFAULT ==
                        payload.MetadataAmount.minimal)

    def test_media_type_write(self):
        p = payload.Payload()
        self.assertTrue(p.metadata == payload.MetadataAmount.minimal)
        self.assertTrue(p.streaming is False)
        self.assertTrue(p.ieee754_compatible is False)
        self.assertTrue(p.exponential_decimals is False)
        self.assertTrue(p.charset == "utf-8")
        ftype = p.get_media_type()
        self.assertTrue(isinstance(ftype, http.MediaType))
        self.assertTrue(ftype['odata.metadata'] == b"minimal")
        self.assertFalse("streaming" in ftype)
        self.assertFalse('ieee754compatible' in ftype)
        self.assertFalse('exponentialdecimals' in ftype)
        self.assertFalse("charset" in ftype)
        ftype_s = str(ftype)
        self.assertTrue("odata.metadata=minimal" in ftype_s)
        p = payload.Payload()
        p.metadata = payload.MetadataAmount.none
        p.streaming = True
        p.ieee754_compatible = True
        p.exponential_decimals = True
        p.charset = "utf-16"
        ftype = p.get_media_type()
        self.assertTrue(ftype['odata.metadata'] == b"none")
        self.assertTrue(ftype['odata.streaming'] == b"true")
        self.assertTrue(ftype['ieee754compatible'] == b"true")
        self.assertTrue(ftype['exponentialdecimals'] == b"true")
        self.assertTrue(ftype['charset'] == b"UTF-16")
        ftype_s = str(ftype)
        self.assertTrue("IEEE754Compatible=true" in ftype_s)
        self.assertTrue("ExponentialDecimals=true" in ftype_s)

    def test_media_type_read(self):
        p = payload.Payload()
        ftype = http.MediaType.from_str(
            "application/json;odata.metadata=minimal;odata.streaming=true")
        p.set_media_type(ftype)
        self.assertTrue(p.metadata == payload.MetadataAmount.minimal)
        self.assertTrue(p.streaming is True)
        self.assertTrue(p.ieee754_compatible is False)
        self.assertTrue(p.exponential_decimals is False)
        self.assertTrue(p.charset == "utf-8")
        ftype = http.MediaType.from_str(
            "application/json;odata.metadata=minimal")
        p.set_media_type(ftype)
        self.assertTrue(p.metadata == payload.MetadataAmount.minimal)
        self.assertTrue(p.streaming is False)
        self.assertTrue(p.ieee754_compatible is False)
        self.assertTrue(p.exponential_decimals is False)
        self.assertTrue(p.charset == "utf-8")


class MockService(service.DataService):
    pass


class ParserTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.service = MockService()
        self.service.context_base = URI.from_octets(
            "http://www.example.com/$metadata")

    def test_primitive(self):
        pass

    def test_primitive_collection(self):
        pass

    def test_complex(self):
        pass

    def test_complex_collection(self):
        pass

    def trippin_entity(self, em):
        p = payload.Payload()
        s = em['Microsoft.OData.Service.Sample.TrippinInMemory.Models']
        person_type = s['Person']
        e = person_type()
        e['UserName'].set_value("user001")
        e['FirstName'].set_value("Jane")
        e['LastName'].set_value("Doe")
        e['Gender'].set_value('Female')
        e['Age'].set_value(50)
        data = p.to_json(e)
        eout = person_type()
        p.obj_from_bytes(eout, data)
        self.assertTrue(eout['UserName'].value == "user001")
        self.assertTrue(eout['Age'].value == 50)

    def test_entity_ref(self):
        pass

    def test_entity_collection(self):
        pass

    def test_entity_ref_collection(self):
        pass

    def test_change_collection(self):
        pass

    def test_trippin(self):
        em = load_trippin()
        em.bind_to_service(self.service)
        p = payload.Payload(self.service)
        data = p.to_json(em)
        jdict = json.loads(data.decode('utf-8'))
        # modify the URL of one of the entity sets
        for item in jdict["value"]:
            if item["name"] == "People":
                item["url"] = "Modified/People"
        # the URL of the entity set should change on parsing
        data = json.dumps(jdict).encode('utf-8')
        em2 = load_trippin()
        obj = p.obj_from_bytes(em2, data)
        self.assertTrue(obj is None, "service doc from json returns None")
        container = em2.get_container()
        self.assertTrue(
            str(container['People'].get_url()) ==
            "http://www.example.com/Modified/People")
        # now test entity
        self.trippin_entity(em2)

    def test_null(self):
        # any primitive value
        v = csdl.StringValue()
        v.set_value("Hello")
        self.assertFalse(v.is_null())
        p = payload.Payload(self.service)
        obj = p.obj_from_bytes(v, b"null")
        self.assertTrue(obj is v)
        self.assertTrue(v.is_null())

    def test_boolean(self):
        v = csdl.BooleanValue()
        p = payload.Payload(self.service)
        obj = p.obj_from_bytes(v, b"null")
        self.assertTrue(obj is v)
        self.assertTrue(v.is_null())
        p.obj_from_bytes(v, b"true")
        self.assertFalse(v.is_null())
        self.assertTrue(v.value is True)
        p.obj_from_bytes(v, b"false")
        self.assertFalse(v.is_null())
        self.assertTrue(v.value is False)

    def test_int32(self):
        v = csdl.Int32Value()
        p = payload.Payload(self.service)
        obj = p.obj_from_bytes(v, b"null")
        self.assertTrue(obj is v)
        self.assertTrue(v.is_null())
        p.obj_from_bytes(v, b"256")
        self.assertFalse(v.is_null())
        self.assertTrue(v.value == 256)
        p.obj_from_bytes(v, b"-1024")
        self.assertFalse(v.is_null())
        self.assertTrue(v.value == -1024)

    def test_error(self):
        pass


class FormatTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.service = MockService()
        self.service.context_base = URI.from_octets(
            "http://www.example.com/$metadata")

    def test_service_document(self):
        em = load_trippin()
        em.bind_to_service(self.service)
        # we format a service document...
        p = payload.Payload(self.service)
        data = p.to_json(em)
        logging.debug("Service Document:\n" + data.decode('utf-8'))
        jdict = json.loads(data.decode('utf-8'))
        self.assertTrue(len(jdict) >= 2)
        self.assertTrue("@odata.context" in jdict)
        uri = URI.from_octets(jdict["@odata.context"])
        self.assertTrue(str(uri) == "http://www.example.com/$metadata")
        self.assertTrue(uri.fragment is None)
        self.assertTrue("value" in jdict)
        container = em.get_container()
        for item in jdict["value"]:
            self.assertTrue(len(item) >= 2)
            self.assertTrue("name" in item)
            self.assertTrue("url" in item)
            name = item["name"]
            sd_item = container[name]
            if isinstance(sd_item, csdl.EntitySet):
                self.assertTrue(sd_item.in_service)
            if "kind" in item:
                kind = item["kind"]
                if kind == "EntitySet":
                    self.assertTrue(isinstance(sd_item, csdl.EntitySet))
                elif kind == "Singleton":
                    self.assertTrue(isinstance(sd_item, csdl.Singleton))
                elif kind == "FunctionImport":
                    self.assertTrue(isinstance(sd_item, csdl.FunctionImport))
                # no related service documents in Trippin service
            else:
                self.assertTrue(isinstance(sd_item, csdl.EntitySet))
        self.trippin_entity(em)

    def test_null(self):
        # any primitive value
        v = csdl.PrimitiveValue()
        self.assertTrue(v.is_null())
        p = payload.Payload(self.service)
        data = p.to_json(v)
        self.assertTrue(data == b"null")

    def test_boolean(self):
        # any primitive value
        v = csdl.BooleanValue()
        p = payload.Payload(self.service)
        data = p.to_json(v)
        self.assertTrue(data == b"null")
        v.set_value(True)
        data = p.to_json(v)
        self.assertTrue(data == b"true")
        v.set_value(False)
        data = p.to_json(v)
        self.assertTrue(data == b"false")

    def test_int32(self):
        v = csdl.Int32Value()
        p = payload.Payload(self.service)
        data = p.to_json(v)
        self.assertTrue(data == b"null")
        v.set_value(-3)
        data = p.to_json(v)
        self.assertTrue(data == b"-3")

    def trippin_entity(self, em):
        p = payload.Payload(self.service)
        s = em['Microsoft.OData.Service.Sample.TrippinInMemory.Models']
        person_type = s['Person']
        e = person_type()
        e['UserName'].set_value("user001")
        e['FirstName'].set_value("Jane")
        e['LastName'].set_value("Doe")
        e['Gender'].set_value('Female')
        e['Age'].set_value(50)
        data = p.to_json(e)
        logging.debug("Person:\n%s", data.decode('utf-8'))
        jdict = json.loads(data.decode('utf-8'))
        # Each property to be transmitted is represented as a name/value
        # pair within the object.
        self.assertTrue(jdict['UserName'] == "user001")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
