#! /usr/bin/env python

import itertools

from . import common
from . import core
from ..xml import structures as xml


class Section(core.ObjectMixin, core.SectionMixin, common.QTICommentContainer):

    """The Section data structure is used to define arbitrarily complex
    hierarchical section and item data structures. It may contain meta-data,
    objectives, rubric control switches, assessment-level processing, feedback
    and selection and sequencing information for sections and items::

    <!ELEMENT section (qticomment? ,
            duration? ,
            qtimetadata* ,
            objectives* ,
            sectioncontrol* ,
            sectionprecondition* ,
            sectionpostcondition* ,
            rubric* ,
            presentation_material? ,
            outcomes_processing* ,
            sectionproc_extension? ,
            sectionfeedback* ,
            selection_ordering? ,
            reference? ,
            (itemref | item | sectionref | section)*
            )>
    <!ATTLIST section  ident CDATA  #REQUIRED
            title CDATA  #IMPLIED
            xml:lang CDATA  #IMPLIED >"""
    XMLNAME = "section"
    XMLATTR_ident = 'ident'
    XMLATTR_title = 'title'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.ident = None
        self.title = None
        self.Duration = None
        self.QTIMetadata = []
        self.Objectives = []
        self.SectionControl = []
        self.SectionPrecondition = []
        self.SectionPostcondition = []
        self.Rubric = []
        self.PresentationMaterial = None
        self.QTIOutcomesProcessing = []
        self.SectionProcExtension = None
        self.SectionFeedback = []
        self.QTISelectionOrdering = None
        self.QTIReference = None
        self.SectionItemMixin = []

    def get_children(self):
        for child in itertools.chain(
                core.QTIComment.get_children(self),
                self.QTIMetadata,
                self.Objectives,
                self.SectionControl,
                self.SectionPrecondition,
                self.SectionPostcondition,
                self.Rubric):
            yield child
        if self.PresentationMaterial:
            yield self.PresentationMaterial
        for child in self.QTIOutcomesProcessing:
            yield child
        if self.SectionProcExtension:
            yield self.SectionProcExtension
        for child in self.SectionFeedback:
            yield child
        if self.QTISelectionOrdering:
            yield self.QTISelectionOrdering
        if self.QTIReference:
            yield self.QTIReference
        for child in self.SectionItemMixin:
            yield child

    def migrate_to_v2(self, output):
        """Converts this section to QTI v2

        For details, see
        :py:class:`pyslet.qtiv1.QuesTestInterop.migrate_to_v2`."""
        for obj in self.SectionItemMixin:
            obj.migrate_to_v2(output)


class SectionPrecondition(core.QTIElement):

    """The preconditions that control whether or not the Section is activated.
    This is for further study in V2.0::

    <!ELEMENT sectionprecondition (#PCDATA)>"""
    XMLNAME = 'sectionprecondition'
    XMLCONTENT = xml.XMLMixedContent


class SectionPostcondition(core.QTIElement):

    """The postconditions that control whether or not the next Section may be
    activated. This is for further study in V2.0::

    <!ELEMENT sectionpostcondition (#PCDATA)>"""
    XMLNAME = 'sectionpostcondition'
    XMLCONTENT = xml.XMLMixedContent


class SectionControl(common.QTICommentContainer):

    """The control switches that are used to enable or disable the display of
    hints, solutions and feedback within the Section::

    <!ELEMENT sectioncontrol (qticomment?)>
    <!ATTLIST sectioncontrol  feedbackswitch  (Yes | No )  'Yes'
            hintswitch  (Yes | No )  'Yes'
            solutionswitch  (Yes | No )  'Yes'
            view	(All | Administrator | AdminAuthority | Assessor | Author |
                            Candidate | InvigilatorProctor | Psychometrician |
                            Scorer | Tutor ) 'All' >"""
    XMLNAME = 'sectioncontrol'
    XMLATTR_feedbackswitch = (
        'feedbackSwitch', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_hintswitch = ('hintSwitch', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_solutionswitch = (
        'solutionSwitch', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_view = ('view', core.View.from_str_lower, core.View.to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.feedbackSwitch = True
        self.hintSwitch = True
        self.solutionSwitch = True
        self.view = core.View.DEFAULT


class SectionProcExtension(core.QTIElement):

    """This is used to contain proprietary alternative Section-level processing
    functionality::

    <!ELEMENT sectionproc_extension ANY>"""
    XMLNAME = "sectionproc_extension"
    XMLCONTENT = xml.XMLMixedContent


class SectionFeedback(common.ContentMixin, common.QTICommentContainer):

    """The container for the Section-level feedback that is to be presented as a
    result of Section-level processing of the user's responses::

    <!ELEMENT sectionfeedback (qticomment? , (material+ | flow_mat+))>
    <!ATTLIST sectionfeedback
            view	(All | Administrator | AdminAuthority | Assessor | Author |
                            Candidate | InvigilatorProctor | Psychometrician |
                            Scorer | Tutor ) 'All'
            ident CDATA  #REQUIRED
            title CDATA  #IMPLIED >"""
    XMLNAME = 'sectionfeedback'
    XMLATTR_view = ('view', core.View.from_str_lower, core.View.to_str)
    XMLATTR_ident = 'ident'
    XMLATTR_title = 'title'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        common.ContentMixin.__init__(self)
        self.view = core.View.DEFAULT
        self.ident = None
        self.title = None

    def get_children(self):
        return itertools.chain(
            common.QTICommentContainer.get_children(self),
            common.ContentMixin.get_content_children(self))

    def content_child(self, child_class):
        return child_class in (common.Material, common.FlowMat)


class SectionRef(core.SectionMixin, core.QTIElement):

    """Represents the sectionref element::

    <!ELEMENT sectionref (#PCDATA)>
    <!ATTLIST sectionref  linkrefid CDATA  #REQUIRED >"""
    XMLNAME = 'sectionref'
    XMLATTR_linkrefid = 'linkrefid'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.linkrefid = None

    def migrate_to_v2(self, output):
        """Converts this sectionref to QTI v2

        Currently does nothing."""
        pass


class ItemRef(core.QTIElement, core.SectionItemMixin):

    """This element is used to 'pull' an Item into the scope. This is used to
    refer to a Item that has been defined elsewhere but which is to be
    logically related to this group of Items::

    <!ELEMENT itemref (#PCDATA)>
    <!ATTLIST itemref  linkrefid CDATA  #REQUIRED >"""
    XMLNAME = 'itemref'
    XMLATTR_linkrefid = 'linkrefid'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.linkrefid = None

    def migrate_to_v2(self, output):
        """Converts this itemref to QTI v2

        Currently does nothing."""
        pass
