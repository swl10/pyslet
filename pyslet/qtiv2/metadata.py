#! /usr/bin/env python

from ..xml import structures as xml
from . import core


class QTIMetadata(core.QTIElement):

    """A new category of meta-data for the recording of QTI specific
    information. It is designed to be treated as an additional top-level
    category to augment the LOM profile::

        <xsd:group name="qtiMetadata.ContentGroup">
            <xsd:sequence>
                <xsd:element ref="itemTemplate" minOccurs="0" maxOccurs="1"/>
                <xsd:element ref="timeDependent" minOccurs="0" maxOccurs="1"/>
                <xsd:element ref="composite" minOccurs="0" maxOccurs="1"/>
                <xsd:element ref="interactionType" minOccurs="0"
                    maxOccurs="unbounded"/>
                <xsd:element ref="feedbackType" minOccurs="0" maxOccurs="1"/>
                <xsd:element ref="solutionAvailable" minOccurs="0"
                    maxOccurs="1"/>
                <xsd:element ref="toolName" minOccurs="0" maxOccurs="1"/>
                <xsd:element ref="toolVersion" minOccurs="0" maxOccurs="1"/>
                <xsd:element ref="toolVendor" minOccurs="0" maxOccurs="1"/>
            </xsd:sequence>
        </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'qtiMetadata')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.ItemTemplate = None
        self.TimeDependent = None
        self.Composite = None
        self.InteractionType = []
        self.FeedbackType = None
        self.SolutionAvailable = None
        self.ToolName = None
        self.ToolVersion = None
        self.ToolVendor = None

    def get_children(self):
        if self.ItemTemplate:
            yield self.ItemTemplate
        if self.TimeDependent:
            yield self.TimeDependent
        if self.Composite:
            yield self.Composite
        for child in self.InteractionType:
            yield child
        if self.FeedbackType:
            yield self.FeedbackType
        if self.SolutionAvailable:
            yield self.SolutionAvailable
        if self.ToolName:
            yield self.ToolName
        if self.ToolVersion:
            yield self.ToolVersion
        if self.ToolVendor:
            yield self.ToolVendor
        for child in core.QTIElement.get_children(self):
            yield child


class ItemTemplate(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'itemTemplate')


class TimeDependent(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'timeDependent')


class Composite(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'composite')


class InteractionType(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'interactionType')


class FeedbackType(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'feedbackType')


class SolutionAvailable(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'solutionAvailable')


class ToolName(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'toolName')


class ToolVersion(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'toolVersion')


class ToolVendor(core.QTIElement):
    XMLNAME = (core.IMSQTI_NAMESPACE, 'toolVendor')
