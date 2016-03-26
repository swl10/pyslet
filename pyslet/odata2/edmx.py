#! /usr/bin/env python
"""This module implements the EDMX specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541284(v=prot.10)"""

import itertools

from . import csdl as edm
from .. import rfc2396 as uri
from ..xml import structures as xml
from ..xml import namespace as xmlns


#: Namespace to use for EDMX elements
EDMX_NAMESPACE = "http://schemas.microsoft.com/ado/2007/06/edmx"


class EDMXElement(xmlns.XMLNSElement):
    XMLCONTENT = xml.ElementType.ElementContent


class DataServices(edm.NameTableMixin, EDMXElement):
    XMLNAME = (EDMX_NAMESPACE, 'DataServices')

    def __init__(self, parent):
        EDMXElement.__init__(self, parent)
        edm.NameTableMixin.__init__(self)
        self.Schema = []

    def get_children(self):
        for s in self.Schema:
            yield s
        for child in super(DataServices, self).get_children():
            yield child

    def content_changed(self):
        for s in self.Schema:
            self.declare(s)
        for s in self.Schema:
            s.update_type_refs(self)
        for s in self.Schema:
            s.update_set_refs(self)

    def validate(self):
        for s in self.Schema:
            s.validate()


class Reference(EDMXElement):
    XMLNAME = (EDMX_NAMESPACE, 'Reference')

    XMLATTR_Url = ('url', uri.URI.from_octets, str)

    def __init__(self, parent):
        EDMXElement.__init__(self, parent)
        self.url = None


class AnnotationsReference(EDMXElement):
    XMLNAME = (EDMX_NAMESPACE, 'AnnotationsReference')

    XMLATTR_Url = ('url', uri.URI.from_octets, str)

    def __init__(self, parent):
        EDMXElement.__init__(self, parent)
        self.url = None


class Edmx(EDMXElement):

    """Represents the Edmx root element."""
    XMLNAME = (EDMX_NAMESPACE, 'Edmx')
    DataServicesClass = DataServices

    XMLATTR_Version = 'version'

    def __init__(self, parent):
        EDMXElement.__init__(self, parent)
        self.version = "1.0"
        self.Reference = []
        self.AnnotationsReference = []
        self.DataServices = self.DataServicesClass(self)

    def get_children(self):
        for child in itertools.chain(
                self.Reference,
                self.AnnotationsReference):
            yield child
        yield self.DataServices
        for child in EDMXElement.get_children(self):
            yield child

    def validate(self):
        self.DataServices.validate()


class Document(xmlns.XMLNSDocument):

    """Represents an Edmx document."""

    classMap = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        self.defaultNS = EDMX_NAMESPACE
        self.make_prefix(EDMX_NAMESPACE, 'edmx')

    @classmethod
    def get_element_class(cls, name):
        """Overridden to look up name in the class map"""
        eclass = Document.classMap.get(
            name, Document.classMap.get((name[0], None), xmlns.XMLNSElement))
        return eclass

    def validate(self):
        # These extensions MUST be used by a data service in conjunction
        # with the "dataservices" node
        if not isinstance(self.root.DataServices, DataServices):
            raise edm.InvalidMetadataDocument("Expected dataservices node")
        self.root.validate()


xmlns.map_class_elements(Document.classMap, globals())
xmlns.map_class_elements(Document.classMap, edm, edm.NAMESPACE_ALIASES)
