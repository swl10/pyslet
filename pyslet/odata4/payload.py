#! /usr/bin/env python

import io
import json
import logging

from ..http import params as http
from ..py2 import (
    is_text,
    long2,
    to_text,
    )
from ..rfc2396 import URI
from ..xml import xsdatatypes as xsi

from . import errors
from . import model as csdl
from . import primitive
from . import types


class MetadataAmount(xsi.Enumeration):

    """An enumeration used to represent odata.metadata control.
    ::

            MetadataAmount.none
            MetadataAmount.DEFAULT == MetadataAmount.minimal

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "none": 0,
        "minimal": 1,
        "full": 2,
        }

    aliases = {
        None: 'minimal'
        }


class Payload(object):

    """A class to represent payload options and context information"""

    def __init__(self, service=None):
        self.service = service
        self.request_url = None
        self.metadata = MetadataAmount.minimal
        self.streaming = False
        self.ieee754_compatible = False
        self.exponential_decimals = False
        self.charset = "utf-8"
        self.current_type = None

    def get_media_type(self):
        params = {
            'odata.metadata':
            ('odata.metadata',
             MetadataAmount.to_str(self.metadata).encode('ascii'))}
        if self.streaming:
            params['odata.streaming'] = ('odata.streaming', b'true')
        if self.ieee754_compatible:
            params['ieee754compatible'] = ('IEEE754Compatible', b'true')
        if self.exponential_decimals:
            params['exponentialdecimals'] = ('ExponentialDecimals', b'true')
        if self.charset != 'utf-8':
            params['charset'] = (
                'charset', self.charset.upper().encode('ascii'))
        return http.MediaType('application', 'json', params)

    @classmethod
    def from_message(cls, url, message, service):
        result = cls(service)
        result.request_url = url
        content_type = message.get_content_type()
        if content_type.type != "application" or \
                content_type.subtype != "json":
            raise NotImplementedError("Expected application/json")
        result.set_media_type(content_type)
        return result

    def set_media_type(self, content_type):
        if "odata.metadata" in content_type:
            self.metadata = MetadataAmount.from_str(
                content_type["odata.metadata"].decode('utf-8'))
        else:
            self.metadata = MetadataAmount.minimal
        if "odata.streaming" in content_type:
            self.streaming = content_type["odata.streaming"] == b"true"
        else:
            self.streaming = False
        if "ieee754compatible" in content_type:
            self.ieee754_compatible = content_type[
                "ieee754compatible"] == b"true"
        else:
            self.ieee754_compatible = False
        if "exponentialdecimals" in content_type:
            self.exponential_decimals = content_type[
                "exponentialdecimals"] == b"true"
        else:
            self.exponential_decimals = False
        if "charset" in content_type:
            self.charset = content_type["charset"].decode('utf-8').lower()
        else:
            self.charset = "utf-8"

    def obj_from_bytes(self, obj, data):
        jdict = json.loads(data.decode(self.charset))
        return self.obj_from_json_value(obj, jdict)

    def obj_from_json_value(self, obj, jvalue):
        if isinstance(jvalue, dict):
            if isinstance(obj, csdl.EntityModel):
                # we are parsing a service document
                logging.info("Service root format: %s", str(jvalue))
                # The value of the odata.context property MUST be the
                # URL of the metadata document
                obj.bind_to_service(self.service)
                context_url = URI.from_octets(jvalue["@odata.context"])
                if context_url != self.service.context_base:
                    raise errors.ServiceError(
                        errors.Requirement.service_context)
                container = obj.get_container()
                for feed in jvalue["value"]:
                    name = feed["name"]
                    url = URI.from_octets(feed["url"]).resolve(context_url)
                    item = container[name]
                    item.set_url(url)
                return None
            if isinstance(obj, types.Annotatable):
                # first pass, object annotations
                for name, value in jvalue.items():
                    if name.startswith('@'):
                        t, qname, q = \
                            types.QualifiedAnnotation.split_json_name(name)
                        qa = types.QualifiedAnnotation.from_qname(
                            qname, self.service.model)
                        self.obj_from_json_value(qa.value, value)
                        obj.annotate(qa)
            if isinstance(obj, csdl.EntitySetValue):
                # we are parsing a simple (ordered) collection create a
                # type object on the fly
                result = obj.type_def.collection_type()
                for item in jvalue["value"]:
                    # create a new value of the type used in the collection
                    value = result.type_def.item_type()
                    value.set_entity_set(obj.entity_set)
                    value.bind_to_service(obj.service)
                    if isinstance(item, dict):
                        type_override = item.get('@odata.type', None)
                    else:
                        type_override = None
                    if type_override:
                        type_override = URI.from_octets(type_override)
                        if self.current_type:
                            type_override = type_override.resolve(
                                self.current_type)
                        if not type_override.is_absolute():
                            type_override = type_override.resolve(
                                self.service.context_base)
                        if not type_override.is_absolute() and \
                                self.request_url:
                            type_override = type_override.resolve(
                                self.request_url)
                        type_def = self.service.resolve_type(type_override)
                        value.set_type(type_def)
                    else:
                        type_override = self.current_type
                    save_base = self.current_type
                    self.current_type = type_override
                    self.obj_from_json_value(value, item)
                    self.current_type = save_base
                    result.append(value)
                return result
            elif isinstance(obj, csdl.StructuredValue):
                ta = []
                for name, value in jvalue.items():
                    if '@' in name and not name[0] == '@':
                        ta.append((name, value))
                        continue
                    pvalue = obj.get(name, None)
                    if pvalue is not None:
                        self.obj_from_json_value(pvalue, value)
                # second pass for annotations
                for name, value in ta:
                    target, qname, q = \
                        types.QualifiedAnnotation.split_json_name(name)
                    qa = types.QualifiedAnnotation.from_qname(
                        qname, self.service.model, qualifier=q)
                    if qa:
                        self.obj_from_json_value(qa.value, value)
                        obj.annotate(qa, target=target)
        elif jvalue is None:
            obj.set_value(None)
            obj.clean()
        elif jvalue is True:
            obj.set_value(True)
            obj.clean()
        elif jvalue is False:
            obj.set_value(False)
            obj.clean()
        elif is_text(jvalue):
            if isinstance(obj, csdl.EnumerationValue):
                new_obj = obj.type_def.value_from_str(jvalue)
            else:
                new_obj = obj.from_str(jvalue)
            # update the existing instance with the new value
            obj.set_value(new_obj.value)
            obj.clean()
        elif isinstance(jvalue, (float, int, long2)):
            obj.set_value(jvalue)
            obj.clean()
        elif isinstance(jvalue, list):
            if isinstance(obj, csdl.CollectionValue):
                next_link = obj.annotations.qualified_get("odata.nextLink")
                with obj.loading(next_link is None) as new_values:
                    for item in jvalue:
                        value = obj.type_def.item_type()
                        self.obj_from_json_value(value, item)
                        new_values.append(value)
                obj.clean()
            else:
                raise errors.FormatError(
                    "Can't parse %s from list" % repr(obj))
        else:
            raise errors.FormatError(
                "Unexpected item in payload %s" % repr(jvalue))
        return obj

    def to_json(self, obj):
        output = io.BytesIO()
        for data in self.generate_json(obj):
            if is_text(data):
                logging.error("Generator returned text: %s" % repr(data))
            output.write(data)
        return output.getvalue()

    def generate_json(self, obj):
        if isinstance(obj, csdl.EntityModel):
            # return a service document
            return self.generate_service_document(obj)
        elif isinstance(obj, (primitive.PrimitiveValue,
                              csdl.EnumerationValue)):
            if obj.is_null():
                return (b'null', )
            elif isinstance(obj, primitive.BooleanValue):
                return (b'true' if obj.value else b'false', )
            elif isinstance(obj, primitive.StringValue):
                return (json.dumps(obj.value).encode(self.charset), )
            elif isinstance(obj, primitive.NumericValue):
                return (str(obj.value).encode(self.charset), )
            else:
                return (json.dumps(to_text(obj)).encode(self.charset), )
        elif isinstance(obj, csdl.StructuredValue):
            return self.generate_structured(obj)
        elif isinstance(obj, csdl.CollectionValue):
            return self.generate_collection(obj)
        else:
            logging.error(
                "JSON serialization of %s not yet supported", repr(obj))
            raise NotImplementedError

    def generate_service_document(self, em):
        yield (
            b'{"@odata.context":%s,' %
            json.dumps(str(em.get_context_url())).encode(self.charset))
        yield b'"value":['
        container = em.get_container()
        comma = False
        for item in container.values():
            item_bytes = []
            if isinstance(item, csdl.EntitySet) and not item.in_service:
                continue
            item_bytes.append(
                b'"name":%s' %
                json.dumps(item.name).encode(self.charset))
            item_bytes.append(
                b'"url":%s' %
                json.dumps(str(item.get_url())).encode(self.charset))
            if isinstance(item, csdl.EntitySet):
                kind = "EntitySet"
            elif isinstance(item, csdl.Singleton):
                kind = "Singleton"
            elif isinstance(item, csdl.FunctionImport):
                kind = "FunctionImport"
            else:
                raise NotImplementedError(repr(item))
            item_bytes.append(
                b'"kind":%s' % json.dumps(kind).encode(self.charset))
            if comma:
                yield(b',')
            else:
                comma = True
            yield b'{%s}' % (b','.join(item_bytes))
        yield b']}'

    def generate_structured(self, svalue):
        yield b'{'
        comma = False
        for pname, pvalue in svalue.items():
            if comma:
                yield b','
            else:
                comma = True
            yield b"%s:" % json.dumps(pname).encode(self.charset)
            for data in self.generate_json(pvalue):
                yield data
        yield b'}'

    def generate_collection(self, collection):
        yield b'['
        comma = False
        for item in collection:
            if comma:
                yield b','
            else:
                comma = True
            for data in self.generate_json(item):
                yield data
        yield b']'
