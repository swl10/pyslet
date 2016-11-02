#! /usr/bin/env python

import sys

from . import content
from . import core
from . import metadata
from .. import html401 as html
from .. import rfc2396 as uri
from ..pep8 import old_method
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi


class AssessmentItem(core.QTIElement, core.DeclarationContainer):

    """An assessment item encompasses the information that is presented to a
    candidate and information about how to score the item::

            <xsd:attributeGroup name="assessmentItem.AttrGroup">
                    <xsd:attribute name="identifier" type="string.Type"
                                    use="required"/>
                    <xsd:attribute name="title" type="string.Type"
                                    use="required"/>
                    <xsd:attribute name="label" type="string256.Type"
                                    use="optional"/>
                    <xsd:attribute ref="xml:lang"/>
                    <xsd:attribute name="adaptive" type="boolean.Type"
                                    use="required"/>
                    <xsd:attribute name="timeDependent" type="boolean.Type"
                                    use="required"/>
                    <xsd:attribute name="toolName" type="string256.Type"
                                    use="optional"/>
                    <xsd:attribute name="toolVersion" type="string256.Type"
                                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="assessmentItem.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="responseDeclaration"
                                            minOccurs="0"
                                            maxOccurs="unbounded"/>
                            <xsd:element ref="outcomeDeclaration"
                                            minOccurs="0"
                                            maxOccurs="unbounded"/>
                            <xsd:element ref="templateDeclaration"
                                            minOccurs="0"
                                            maxOccurs="unbounded"/>
                            <xsd:element ref="templateProcessing"
                                            minOccurs="0"
                                            maxOccurs="1"/>
                            <xsd:element ref="stylesheet"
                                            minOccurs="0"
                                            maxOccurs="unbounded"/>
                            <xsd:element ref="itemBody"
                                            minOccurs="0"
                                            maxOccurs="1"/>
                            <xsd:element ref="responseProcessing"
                                            minOccurs="0"
                                            maxOccurs="1"/>
                            <xsd:element ref="modalFeedback"
                                            minOccurs="0"
                                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'assessmentItem')
    XMLATTR_adaptive = ('adaptive', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_identifier = 'identifier'
    XMLATTR_label = 'label'
    XMLATTR_timeDependent = (
        'timeDependent', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_title = 'title'
    XMLCONTENT = xml.ElementContent

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

    def get_children(self):
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
        self.sort_declarations()

    def sort_declarations(self):
        """Sort each of the variable declaration lists so that they are
        in identifier order.  This is not essential but it does help
        ensure that output is predictable. This method is called
        automatically when reading items from XML files."""
        self.ResponseDeclaration.sort()
        self.OutcomeDeclaration.sort()
        self.TemplateDeclaration.sort()

    def render_html(self, item_state, html_parent=None):
        """Renders this item in html, adding nodes to *html_parent*.
        The state of the item (e.g., the values of any controls and
        template variables), is taken from *item_state*, a
        :py:class:`variables.ItemSessionState` instance.

        The result is the top-level div containing the item added to the
        html_parent. If html_parent is None then a parentless div is
        created. If the item has no itemBody then an empty Div is
        returned."""
        if self.ItemBody:
            html_div = self.ItemBody.render_html(
                html_parent, content.HTMLProfile, item_state)
        else:
            if html_parent:
                html_div = html_parent.add_child(html.Div)
            else:
                html_div = html.Div(None)
        return html_div

    @old_method('AddToContentPackage')
    def add_to_content_package(self, cp, lom, dname=None):
        """Adds a resource and associated files to the content package."""
        resource_id = cp.manifest.get_unique_id(self.identifier)
        resource = cp.manifest.root.Resources.add_child(
            cp.manifest.root.Resources.ResourceClass)
        resource.set_id(resource_id)
        resource.type = core.IMSQTI_ITEM_RESOURCETYPE
        resource_metadata = resource.add_child(resource.MetadataClass)
        # resource_metadata.AdoptChild(lom)
        # resource_metadata.AdoptChild(self.metadata.deepcopy())
        lom.deepcopy(resource_metadata)
        self.metadata.deepcopy(resource_metadata)
        # Security alert: we're leaning heavily on ValidateIdentifier assuming
        # it returns a good file name
        fpath = (core.ValidateIdentifier(resource_id) +
                 '.xml').encode(sys.getfilesystemencoding())
        if dname:
            fpath = cp.FilePath(dname, fpath)
        fpath = cp.GetUniqueFile(fpath)
        # This will be the path to the file in the package
        full_path = cp.dPath.join(fpath)
        base = uri.URI.from_virtual_path(full_path)
        if isinstance(self.parent, xml.Document):
            # we are the root so we change the document base
            self.parent.set_base(base)
        else:
            self.set_base(base)
        # Turn this file path into a relative URL in the context of the new
        # resource
        href = resource.relative_uri(base)
        f = cp.File(resource, href)
        resource.SetEntryPoint(f)
        for child in self.get_children():
            if isinstance(child, core.QTIElement):
                child.add_to_cpresource(cp, resource, {})
        return resource


#
# Modal Feedback
#
class QTIModalFeedback(content.FlowContainerMixin, core.QTIElement):

    """Represents the modalFeedback element.

    <xsd:attributeGroup name="modalFeedback.AttrGroup">
            <xsd:attribute name="outcomeIdentifier" type="identifier.Type"
            use="required"/>
            <xsd:attribute name="showHide" type="showHide.Type"
            use="required"/>
            <xsd:attribute name="identifier" type="identifier.Type"
            use="required"/>
            <xsd:attribute name="title" type="string.Type" use="optional"/>
    </xsd:attributeGroup>

    <xsd:group name="modalFeedback.ContentGroup">
            <xsd:sequence>
                    <xsd:group ref="flowStatic.ElementGroup" minOccurs="0"
                    maxOccurs="unbounded"/>
            </xsd:sequence>
    </xsd:group>
    """
    XMLNAME = (core.IMSQTI_NAMESPACE, 'modalFeedback')
    XMLATTR_outcomeIdentifier = (
        'outcomeIdentifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_showHide = (
        'showHide', core.ShowHide.from_str_lower, core.ShowHide.to_str)
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_title = 'title'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.outcomeIdentifier = None
        self.showHide = None
        self.identifier = None
        self.title = None

    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.FlowMixin):
            return core.QTIElement.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))
