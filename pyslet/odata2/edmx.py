#! /usr/bin/env python
"""This module implements the EDMX specification defined by Microsoft.

http://msdn.microsoft.com/en-us/library/dd541284(v=prot.10)"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.rfc2396 as uri
import pyslet.odata2.csdl as edm

import itertools

#: Namespace to use for EDMX elements
EDMX_NAMESPACE = "http://schemas.microsoft.com/ado/2007/06/edmx"


class EDMXElement(xmlns.XMLNSElement):
    XMLCONTENT = xmlns.ElementType.ElementContent


class DataServices(edm.NameTableMixin, EDMXElement):
    XMLNAME = (EDMX_NAMESPACE, 'DataServices')

    def __init__(self, parent):
        EDMXElement.__init__(self, parent)
        edm.NameTableMixin.__init__(self)
        self.Schema = []

    def GetChildren(self):
        for s in self.Schema:
            yield s
        for child in super(DataServices, self).GetChildren():
            yield child

    def ContentChanged(self):
        for s in self.Schema:
            self.Declare(s)
        for s in self.Schema:
            s.UpdateTypeRefs(self)
        for s in self.Schema:
            s.UpdateSetRefs(self)


class Reference(EDMXElement):
    XMLNAME = (EDMX_NAMESPACE, 'Reference')

    XMLATTR_Url = ('url', uri.URIFactory.URI, str)

    def __init__(self, parent):
        EDMXElement.__init__(self, parent)
        self.url = None


class AnnotationsReference(EDMXElement):
    XMLNAME = (EDMX_NAMESPACE, 'AnnotationsReference')

    XMLATTR_Url = ('url', uri.URIFactory.URI, str)

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

    def GetChildren(self):
        for child in itertools.chain(
                self.Reference,
                self.AnnotationsReference):
            yield child
        yield self.DataServices
        for child in EDMXElement.GetChildren(self):
            yield child


class Document(xmlns.XMLNSDocument):

    """Represents an Edmx document."""

    classMap = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        self.defaultNS = EDMX_NAMESPACE
        self.MakePrefix(EDMX_NAMESPACE, 'edmx')

    @classmethod
    def GetElementClass(cls, name):
        """Overrides :py:meth:`pyslet.xmlnames20091208.XMLNSDocument.GetElementClass` to look up name."""
        eClass = Document.classMap.get(
            name, Document.classMap.get((name[0], None), xmlns.XMLNSElement))
        return eClass

xmlns.MapClassElements(Document.classMap, globals())
xmlns.MapClassElements(Document.classMap, edm, edm.NAMESPACE_ALIASES)
