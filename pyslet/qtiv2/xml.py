#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC"""

import logging

from .. import html401 as html
from ..pep8 import old_method
from ..xml import namespace as xmlns
from ..xml import xsdatatypes as xsi

from . import (     # noqa
    content,
    core,
    expressions,
    interactions,
    items,
    metadata,
    processing,
    tests,
    variables)


class QTIDocument(xmlns.XMLNSDocument):

    """Used to represent all documents representing information from the
    QTI v2 specification.

    Simple recipe to get started::

        import pyslet.qtiv2.xml as qti

        doc = qti.QTIDocument()
        with open('myqti.xml', 'rb') as f:
            doc.read(src=f)
            # do stuff with the QTI document here

    The root (doc.root) element of a QTI document may one of a number of
    elements, if you are interested in items look for an instance of
    qti.items.AssessmentItem, etc."""

    classMap = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self,
                                     defaultNS=core.IMSQTI_NAMESPACE, **args)
        self.make_prefix(xsi.XMLSCHEMA_NAMESPACE, 'xsi')
        if isinstance(self.root, core.QTIElement):
            self.root.set_attribute(
                (xsi.XMLSCHEMA_NAMESPACE, 'schemaLocation'),
                core.IMSQTI_NAMESPACE + ' ' + core.IMSQTI_SCHEMALOCATION)

    def get_element_class(self, name):
        return QTIDocument.classMap.get(
            name, QTIDocument.classMap.get(
                (name[0], None), xmlns.XMLNSElement))

    @old_method('AddToContentPackage')
    def add_to_content_package(self, cp, md, dname=None):
        """Copies this QTI document into a content package and returns the
        resource ID used.

        An optional directory name can be specified in which to put the
        resource files."""
        # We call the element's AddToContentPackage method which returns the
        # new resource.
        # The document's base is automatically set to the URI of the resource
        # entry point.
        resource = self.root.AddToContentPackage(cp, md, dname)
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
        logging.debug("Failed to map XHTML element name %s", name)
