#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsdatatypes
import pyslet.html40_19991224 as html
import pyslet.rfc2396 as uri

xsi = xsdatatypes

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
import pyslet.qtiv2.metadata as md


QTI_HTMLProfile = [
    'abbr', 'acronym', 'address', 'blockquote', 'br', 'cite', 'code', 'dfn', 'div',
    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'kbd', 'p', 'pre', 'q', 'samp', 'span',
    'strong', 'var', 'dl', 'dt', 'dd', 'ol', 'ul', 'li', 'object', 'param', 'b', 'big',
    'hr', 'i', 'small', 'sub', 'sup', 'tt', 'caption', 'col', 'colgroup', 'table',
    'tbody', 'tfoot', 'thead', 'td', 'th', 'tr', 'img', 'a']

MakeValidNCName = core.ValidateIdentifier


class RubricBlock(html.BlockMixin, content.BodyElement):

    """Represent the rubricBlock element.

    <xsd:attributeGroup name="rubricBlock.AttrGroup">
            <xsd:attributeGroup ref="simpleBlock.AttrGroup"/>
            <xsd:attribute name="view" use="required">
                    <xsd:simpleType>
                            <xsd:list itemType="view.Type"/>
                    </xsd:simpleType>
            </xsd:attribute>
    </xsd:attributeGroup>

    <xsd:group name="rubricBlock.ContentGroup">
            <xsd:sequence>
                    <xsd:group ref="simpleBlock.ContentGroup"/>
            </xsd:sequence>
    </xsd:group>
    """
    XMLNAME = (core.IMSQTI_NAMESPACE, 'rubricBlock')
    XMLATTR_view = (
        'view', core.View.DecodeLowerValue, core.View.EncodeValue, types.DictType)
    XMLCONTENT = xmlns.ElementContent

    def __init__(self, parent):
        content.BodyElement.__init__(self, parent)
        self.view = {}

    def AddView(self, view):
        if type(view) in StringTypes:
            view = core.View.DecodeLowerValue(view.strip())
        viewValue = core.View.EncodeValue(view)
        if viewValue:
            self.view[view] = viewValue
        else:
            raise ValueError("illegal value for view: %s" % view)

    # need to constrain content to html.BlockMixin
    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, html.BlockMixin):
            return content.BodyElement.ChildElement(self, childClass, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))

#
#		MISCELLANEOUS INTERACTIONS
#


#
#	Modal Feedback
#
class QTIModalFeedback(content.FlowContainerMixin, core.QTIElement):

    """Represents the modalFeedback element.

    <xsd:attributeGroup name="modalFeedback.AttrGroup">
            <xsd:attribute name="outcomeIdentifier" type="identifier.Type" use="required"/>
            <xsd:attribute name="showHide" type="showHide.Type" use="required"/>
            <xsd:attribute name="identifier" type="identifier.Type" use="required"/>
            <xsd:attribute name="title" type="string.Type" use="optional"/>
    </xsd:attributeGroup>

    <xsd:group name="modalFeedback.ContentGroup">
            <xsd:sequence>
                    <xsd:group ref="flowStatic.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
            </xsd:sequence>
    </xsd:group>
    """
    XMLNAME = (core.IMSQTI_NAMESPACE, 'modalFeedback')
    XMLATTR_outcomeIdentifier = (
        'outcomeIdentifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_showHide = (
        'showHide', core.ShowHide.DecodeLowerValue, core.ShowHide.EncodeValue)
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_title = 'title'
    XMLCONTENT = xmlns.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.outcomeIdentifier = None
        self.showHide = None
        self.identifier = None
        self.title = None

    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, html.FlowMixin):
            return core.QTIElement.ChildElement(self, childClass, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))


xmlns.MapClassElements(core.QTIDocument.classMap, globals())
xmlns.MapClassElements(core.QTIDocument.classMap, variables)
xmlns.MapClassElements(core.QTIDocument.classMap, processing)
xmlns.MapClassElements(core.QTIDocument.classMap, content)
xmlns.MapClassElements(core.QTIDocument.classMap, interactions)
xmlns.MapClassElements(core.QTIDocument.classMap, items)
xmlns.MapClassElements(core.QTIDocument.classMap, tests)
xmlns.MapClassElements(core.QTIDocument.classMap, expressions)
xmlns.MapClassElements(core.QTIDocument.classMap, md)
# also add in the profile of HTML but with the namespace rewritten to ours
for name in QTI_HTMLProfile:
    eClass = html.XHTMLDocument.classMap.get(
        (html.XHTML_NAMESPACE, name), None)
    if eClass:
        core.QTIDocument.classMap[(core.IMSQTI_NAMESPACE, name)] = eClass
    else:
        print "Failed to map XHTML element name %s" % name
