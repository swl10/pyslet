#! /usr/bin/env python

#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml.structures as xml
import pyslet.xml.namespace as xmlns
import pyslet.xml.xsdatatypes as xsdatatypes
import pyslet.html401 as html
import pyslet.rfc2396 as uri

import string
import itertools
import types
import sys
from types import StringTypes

import pyslet.qtiv2.core as core
import pyslet.qtiv2.variables as variables
import pyslet.qtiv2.expressions as expressions
import pyslet.qtiv2.processing as processing
import pyslet.qtiv2.content as content
import pyslet.qtiv2.interactions as interactions
import pyslet.qtiv2.items as items
import pyslet.qtiv2.tests as tests
import pyslet.qtiv2.metadata as metadata

xsi = xsdatatypes

# MakeValidNCName = core.ValidateIdentifier

class QTIDocument(xmlns.XMLNSDocument):

    """Used to represent all documents representing information from the QTI v2
    specification."""

    classMap = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, defaultNS=core.IMSQTI_NAMESPACE, **args)
        self.make_prefix(xsi.XMLSCHEMA_NAMESPACE, 'xsi')
        if isinstance(self.root, core.QTIElement):
            self.root.set_attribute(
                (xsi.XMLSCHEMA_NAMESPACE, 'schemaLocation'),
                core.IMSQTI_NAMESPACE + ' ' + core.IMSQTI_SCHEMALOCATION)

    def get_element_class(self, name):
        return QTIDocument.classMap.get(
            name, QTIDocument.classMap.get(
                (name[0], None), xmlns.XMLNSElement))

    def AddToContentPackage(self, cp, md, dName=None):
        """Copies this QTI document into a content package and returns the
        resource ID used.

        An optional directory name can be specified in which to put the
        resource files."""
        # We call the element's AddToContentPackage method which returns the
        # new resource.
        # The document's base is automatically set to the URI of the resource
        # entry point.
        resource = self.root.AddToContentPackage(cp, md, dName)
        # Finish by writing out the document to the new base_uri
        self.create()
        return resource


xmlns.map_class_elements(QTIDocument.classMap, globals())
xmlns.map_class_elements(QTIDocument.classMap, variables)
xmlns.map_class_elements(QTIDocument.classMap, processing)
xmlns.map_class_elements(QTIDocument.classMap, content)
xmlns.map_class_elements(QTIDocument.classMap, interactions)
xmlns.map_class_elements(QTIDocument.classMap, items)
xmlns.map_class_elements(QTIDocument.classMap, tests)
xmlns.map_class_elements(QTIDocument.classMap, expressions)
xmlns.map_class_elements(QTIDocument.classMap, metadata)
# also add in the profile of HTML but with the namespace rewritten to ours
for name in core.QTI_HTML_PROFILE:
    eClass = html.XHTMLDocument.class_map.get(
        (html.XHTML_NAMESPACE, name), None)
    if eClass:
        QTIDocument.classMap[(core.IMSQTI_NAMESPACE, name)] = eClass
    else:
        print "Failed to map XHTML element name %s" % name
