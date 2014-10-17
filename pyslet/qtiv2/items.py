#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
import pyslet.rfc2396 as uri

import pyslet.qtiv2.core as core
import pyslet.qtiv2.content as content
import pyslet.qtiv2.metadata as metadata

import sys


class AssessmentItem(core.QTIElement, core.DeclarationContainer):

    """An assessment item encompasses the information that is presented to a
    candidate and information about how to score the item::

            <xsd:attributeGroup name="assessmentItem.AttrGroup">
                    <xsd:attribute name="identifier" type="string.Type" use="required"/>
                    <xsd:attribute name="title" type="string.Type" use="required"/>
                    <xsd:attribute name="label" type="string256.Type" use="optional"/>
                    <xsd:attribute ref="xml:lang"/>
                    <xsd:attribute name="adaptive" type="boolean.Type" use="required"/>
                    <xsd:attribute name="timeDependent" type="boolean.Type" use="required"/>
                    <xsd:attribute name="toolName" type="string256.Type" use="optional"/>
                    <xsd:attribute name="toolVersion" type="string256.Type" use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="assessmentItem.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="responseDeclaration" minOccurs="0" maxOccurs="unbounded"/>
                            <xsd:element ref="outcomeDeclaration" minOccurs="0" maxOccurs="unbounded"/>
                            <xsd:element ref="templateDeclaration" minOccurs="0" maxOccurs="unbounded"/>
                            <xsd:element ref="templateProcessing" minOccurs="0" maxOccurs="1"/>
                            <xsd:element ref="stylesheet" minOccurs="0" maxOccurs="unbounded"/>
                            <xsd:element ref="itemBody" minOccurs="0" maxOccurs="1"/>
                            <xsd:element ref="responseProcessing" minOccurs="0" maxOccurs="1"/>
                            <xsd:element ref="modalFeedback" minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'assessmentItem')
    XMLATTR_adaptive = ('adaptive', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLATTR_identifier = 'identifier'
    XMLATTR_label = 'label'
    XMLATTR_timeDependent = (
        'timeDependent', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLATTR_title = 'title'
    XMLCONTENT = xmlns.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        core.DeclarationContainer.__init__(self)
        self.identifier = None
        self.title = None
        self.label = None
        self.adaptive = False
        self.timeDependent = False
        self.ResponseDeclaration = []
        self.OutcomeDeclaration = []
        self.TemplateDeclaration = []
        self.TemplateProcessing = None
        self.StyleSheet = []
        self.ItemBody = None
        self.ResponseProcessing = None
        self.QTIModalFeedback = []
        self.metadata = metadata.QTIMetadata(None)

    def GetChildren(self):
        for d in self.ResponseDeclaration:
            yield d
        for d in self.OutcomeDeclaration:
            yield d
        for d in self.TemplateDeclaration:
            yield d
        if self.ItemBody:
            yield self.ItemBody
        if self.ResponseProcessing:
            yield self.ResponseProcessing
        for child in self.QTIModalFeedback:
            yield child

    def content_changed(self):
        self.SortDeclarations()

    def SortDeclarations(self):
        """Sort each of the variable declaration lists so that they are in
        identifier order.  This is not essential but it does help ensure that
        output is predictable. This method is called automatically when reading
        items from XML files."""
        self.ResponseDeclaration.sort()
        self.OutcomeDeclaration.sort()
        self.TemplateDeclaration.sort()

    def RenderHTML(self, itemState, htmlParent=None):
        """Renders this item in html, adding nodes to *htmlParent*.  The state
        of the item (e.g., the values of any controls and template variables),
        is taken from *itemState*, a :py:class:`variables.ItemSessionState`
        instance.

        The result is the top-level div containing the item added to the
        htmlParent. If htmlParent is None then a parentless div is created. If
        the item has no itemBody then an empty Div is returned."""
        if self.ItemBody:
            htmlDiv = self.ItemBody.RenderHTML(
                htmlParent, content.HTMLProfile, itemState)
        else:
            if htmlParent:
                htmlDiv = htmlParent.ChildElement(html.Div)
            else:
                htmlDiv = html.Div(None)
        return htmlDiv

    def AddToContentPackage(self, cp, lom, dName=None):
        """Adds a resource and associated files to the content package."""
        resourceID = cp.manifest.GetUniqueID(self.identifier)
        resource = cp.manifest.root.Resources.ChildElement(
            cp.manifest.root.Resources.ResourceClass)
        resource.SetID(resourceID)
        resource.type = core.IMSQTI_ITEM_RESOURCETYPE
        resourceMetadata = resource.ChildElement(resource.MetadataClass)
        # resourceMetadata.AdoptChild(lom)
        # resourceMetadata.AdoptChild(self.metadata.Copy())
        lom.Copy(resourceMetadata)
        self.metadata.Copy(resourceMetadata)
        # Security alert: we're leaning heavily on ValidateIdentifier assuming
        # it returns a good file name
        fPath = (core.ValidateIdentifier(resourceID) +
                 '.xml').encode(sys.getfilesystemencoding())
        if dName:
            fPath = cp.FilePath(dName, fPath)
        fPath = cp.GetUniqueFile(fPath)
        # This will be the path to the file in the package
        fullPath = cp.dPath.join(fPath)
        base = uri.URIFactory.URLFromVirtualFilePath(fullPath)
        if isinstance(self.parent, xml.Document):
            # we are the root so we change the document base
            self.parent.SetBase(base)
        else:
            self.SetBase(base)
        # Turn this file path into a relative URL in the context of the new
        # resource
        href = resource.RelativeURI(base)
        f = cp.File(resource, href)
        resource.SetEntryPoint(f)
        for child in self.GetChildren():
            if isinstance(child, core.QTIElement):
                child.AddToCPResource(cp, resource, {})
        return resource
