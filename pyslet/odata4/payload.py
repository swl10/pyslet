#! /usr/bin/env python

import io
import json
import logging

from ..http import params as http
from ..py2 import (
    is_text,
    is_unicode,
    long2,
    to_text,
    )
from ..rfc2396 import URI
from ..xml import xsdatatypes as xsi

from . import errors
from . import geotypes as geo
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
        self.odata_type = None
        self.odata_type_stack = []
        self.odata_context = None
        self.odata_context_stack = []
        self._patch_mode = False

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
        """Decodes a model object from a bytes string of data

        obj
            The expected model object

        data
            A bytes string containing the serialized representation of
            the object.

        There is no return value."""
        jdict = json.loads(data.decode(self.charset))
        self.obj_from_json_value(obj, jdict)

    def _resolve_in_context(self, url):
        if self.odata_context:
            url = url.resolve(self.odata_context)
        if not url.is_absolute() and self.request_url:
            url = url.resolve(self.request_url)
        return url

    def _push_context(self, odata_context):
        odata_context = self._resolve_in_context(
            URI.from_octets(odata_context))
        self.odata_context_stack.append(self.odata_context)
        self.odata_context = odata_context
        return odata_context

    def _pop_context(self):
        self.odata_context = self.odata_context_stack.pop()

    def _push_type(self, odata_type):
        odata_type = URI.from_octets(odata_type)
        if self.odata_type:
            odata_type = odata_type.resolve(self.odata_type)
        if not odata_type.is_absolute():
            odata_type = odata_type.resolve(self.service.context_base)
        if not odata_type.is_absolute() and self.request_url:
            odata_type = odata_type.resolve(self.request_url)
        self.odata_type_stack.append(self.odata_type)
        self.odata_type = odata_type
        return self.service.resolve_type(odata_type)

    def _pop_type(self):
        self.odata_type = self.odata_type_stack.pop()

    def obj_from_json_dict(self, obj, jdict):
        odata_context = jdict.pop("@odata.context", None)
        if odata_context:
            context_url = self._push_context(odata_context)
        else:
            context_url = None
        odata_type = jdict.pop("@odata.type", None)
        if odata_type:
            odata_type_def = self._push_type(odata_type)
            obj.type_cast(odata_type_def)
        else:
            odata_type_def = None
        next_link = jdict.pop("@odata.nextLink", None)
        if next_link:
            next_link = self._resolve_in_context(next_link)
        annotations = {}
        # first pass processes annotations, adds them to the current
        # object or stores them where there is an identified target
        for name, value in jdict.items():
            if '@' not in name:
                continue
            target, qname, q = \
                types.QualifiedAnnotation.split_json_name(name)
            if target:
                target_dict = annotations.setdefault(target, {})
                aname = "@" + to_text(qname)
                if q:
                    aname += "#" + q
                target_dict[aname] = value
            elif isinstance(obj, types.Annotatable):
                qa = types.QualifiedAnnotation.from_qname(
                    qname, self.service.model, qualifier=q)
                if qa:
                    self.obj_from_json_value(qa.value, value)
                    obj.annotate(qa)
        if isinstance(obj, csdl.EntityModel):
            # we are parsing a service document
            logging.debug("Service root format: %s", str(jdict))
            # The value of the odata.context property MUST be the
            # URL of the metadata document
            obj.bind_to_service(self.service)
            if context_url != self.service.context_base:
                raise errors.ServiceError(
                    errors.Requirement.service_context)
            container = obj.get_container()
            for feed in jdict["value"]:
                name = feed["name"]
                url = URI.from_octets(feed["url"]).resolve(context_url)
                item = container[name]
                item.set_url(url)
        elif isinstance(obj, csdl.ContainerValue):
            # we are parsing a simple (ordered) collection
            with obj.loading(next_link) as new_value:
                self.obj_from_json_value(new_value, jdict['value'])
        elif isinstance(obj, csdl.StructuredValue):
            with obj.loading() as new_value:
                for name, value in jdict.items():
                    if '@' in name:
                        continue
                    pvalue = new_value.get(name, None)
                    if pvalue is not None:
                        pdict = annotations.get(name, None)
                        if pdict:
                            # there are annotations targeted at us so we
                            # simulate the explicit dictionary form for
                            # this property
                            pdict["value"] = value
                            self.obj_from_json_dict(pvalue, pdict)
                        elif isinstance(pvalue, csdl.ContainerValue):
                            # no next link!
                            with pvalue.loading() as new_pvalue:
                                self.obj_from_json_value(new_pvalue, value)
                        else:
                            self.obj_from_json_value(pvalue, value)
        elif isinstance(
                obj, (primitive.GeographyValue, primitive.GeometryValue)):
            if 'value' in jdict:
                jdict = jdict['value']
            if not isinstance(jdict, dict):
                raise errors.FormatError("expected json object in value")
            gtype = jdict['type']
            coordinates = jdict.get('coordinates', None)
            if gtype == "Point":
                if not isinstance(obj, primitive.PointValue):
                    raise errors.FormatError(
                        "Can't parse %s from GeoJSON Point" % repr(obj))
                if not coordinates or len(coordinates) != 2:
                    raise errors.FormatError(
                        "Exactly 2 coordinates required for Point")
                point = geo.Point(*coordinates)
                srid = self.srid_from_geojson(jdict)
                if srid is None:
                    obj.set_value(point)
                else:
                    obj.set_value(geo.PointLiteral(srid, point))
            else:
                raise NotImplementedError
        else:
            # we have processed the annotations for this object now
            # including any type cast from @odata.type
            self.obj_from_json_value(obj, jdict['value'])
        if odata_type:
            self._pop_type()
        if odata_context:
            self._pop_context()

    def srid_from_geojson(self, jdict):
        crs = jdict.get('crs', None)
        if isinstance(crs, dict):
            # must be of type name
            if crs['type'] != 'name':
                raise errors.FormatError("CRS MUST be of type name")
            name = crs['properties']['name'].split(':')
            if len(name) < 2 or name[0].upper() != "EPSG":
                raise errors.FormatError(
                    "Unrecognized CRS: %s" % crs['properties']['name'])
            return int(name[1])
        else:
            return None

    def obj_from_json_value(self, obj, jvalue):
        if isinstance(jvalue, dict):
            self.obj_from_json_dict(obj, jvalue)
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
            if isinstance(obj, csdl.ContainerValue):
                for item in jvalue:
                    value = obj.new_item()
                    self.obj_from_json_value(value, item)
                    obj.load_item(value)
            else:
                raise errors.FormatError(
                    "Can't parse %s from list" % repr(obj))
        else:
            raise errors.FormatError(
                "Unexpected item in payload %s" % repr(jvalue))

    def to_json(self, obj, type_def=None, patch=False):
        self._patch_mode = patch
        output = io.BytesIO()
        for data in self.generate_json(obj, type_def=type_def):
            if is_unicode(data):
                logging.error("Generator returned text: %s" % repr(data))
            output.write(data)
        output.seek(0)
        return output

    def generate_json(self, obj, type_def=None):
        if isinstance(obj, csdl.EntityModel):
            # return a service document
            return self.generate_service_document(obj)
        elif obj.is_null():
            return (b'null', )
        elif isinstance(obj, (primitive.PrimitiveValue,
                              csdl.EnumerationValue)):
            if isinstance(obj, primitive.BooleanValue):
                return (b'true' if obj.value else b'false', )
            elif isinstance(obj, primitive.StringValue):
                return (json.dumps(obj.value).encode(self.charset), )
            elif isinstance(obj, primitive.NumericValue):
                return (str(obj.value).encode(self.charset), )
            else:
                return (json.dumps(to_text(obj)).encode(self.charset), )
        elif isinstance(obj, csdl.StructuredValue):
            return self.generate_structured(obj, type_def=type_def)
        elif isinstance(obj, csdl.CollectionValue):
            return self.generate_collection(obj, type_def=type_def)
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

    def generate_structured(self, svalue, type_def=None):
        if svalue.is_null():
            yield "null"
            return
        yield b'{'
        comma = False
        if type_def is None or svalue.type_def is not type_def:
            yield b'"@odata.type":"%s"' % \
                svalue.type_def.get_odata_type_fragment().encode(self.charset)
            comma = True
        for pname, pvalue in svalue.items():
            pdef = svalue.type_def[pname]
            ptype = None
            odata_type = None
            if self._patch_mode:
                if isinstance(pdef, csdl.Property):
                    if not pvalue.dirty:
                        continue
                else:
                    # ignore navigation properties in patch mode
                    continue
            if comma:
                yield b','
            else:
                comma = True
            if isinstance(pdef, csdl.Property):
                ptype = pdef.structural_type
                if isinstance(ptype, csdl.ComplexType):
                    if pdef.collection:
                        ptype = pvalue.item_type
                        if ptype is not pvalue.type_def.item_type:
                            # add the odata.type for this property
                            odata_type = pvalue.item_type.\
                                get_odata_type_fragment().encode(self.charset)
                if odata_type:
                    yield b"@odata.type:%s," % json.dumps(
                        odata_type).encode(self.charset)
            yield b"%s:" % json.dumps(pname).encode(self.charset)
            for data in self.generate_json(pvalue, type_def=ptype):
                yield data
        yield b'}'

    def generate_collection(self, collection, type_def=None):
        yield b'['
        comma = False
        for item in collection:
            if comma:
                yield b','
            else:
                comma = True
            for data in self.generate_json(item, type_def=type_def):
                yield data
        yield b']'
