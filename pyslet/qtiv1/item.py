#! /usr/bin/env python

import itertools

from . import common
from . import core
from .. import html401 as html
from .. import imsmdv1p2p1 as imsmd
from ..py2 import is_text
from ..qtiv2 import xml as qtiv2
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi


class Item(
        common.QTICommentContainer,
        core.SectionItemMixin,
        core.ObjectMixin):

    """The Item is the smallest unit data structure that can be
    exchanged using the QTI specification. Each Item consists of five
    distinct parts, namely: objectives - the materials used to describe
    the objectives with respect to each view; rubric - the materials
    used to define the context of the Item and available for each view;
    presentation - the instructions describing the nature of the
    question to be asked; resprocessing - the instructions to be
    followed when analyzing the responses to create a corresponding
    score and feedback; itemfeedback - the materials to be presented as
    feedback to the entered response::

    <!ELEMENT item (qticomment?
            duration?
            itemmetadata?
            objectives*
            itemcontrol*
            itemprecondition*
            itempostcondition*
            (itemrubric | rubric)*
            presentation?
            resprocessing*
            itemproc_extension?
            itemfeedback*
            reference?)>
    <!ATTLIST item  maxattempts CDATA  #IMPLIED
            label CDATA  #IMPLIED
            ident CDATA  #REQUIRED
            title CDATA  #IMPLIED
            xml:lang    CDATA  #IMPLIED >"""
    XMLNAME = 'item'
    XMLATTR_maxattempts = 'maxattempts'
    XMLATTR_label = 'label'
    XMLATTR_ident = 'ident'
    XMLATTR_title = 'title'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.maxattempts = None
        self.label = None
        self.ident = None
        self.title = None
        self.Duration = None
        self.ItemMetadata = None
        self.Objectives = []
        self.ItemControl = []
        self.ItemPreCondition = []
        self.ItemPostCondition = []
        self.Rubric = []				#: includes ItemRubric
        self.Presentation = None
        self.ResProcessing = []
        self.ItemProcExtension = None
        self.ItemFeedback = []
        self.QTIReference = None

    def get_children(self):
        for child in common.QTICommentContainer.get_children(self):
            yield child
        if self.Duration:
            yield self.Duration
        if self.ItemMetadata:
            yield self.ItemMetadata
        for child in itertools.chain(
                self.Objectives,
                self.ItemControl,
                self.ItemPreCondition,
                self.ItemPostCondition,
                self.Rubric):
            yield child
        if self.Presentation:
            yield self.Presentation
        for child in self.ResProcessing:
            yield child
        if self.ItemProcExtension:
            yield self.ItemProcExtension
        for child in self.ItemFeedback:
            yield child
        if self.QTIReference:
            yield self.QTIReference

    def migrate_to_v2(self, output):
        """Converts this item to QTI v2

        For details, see
        :py:meth:`pyslet.qtiv1.QuesTestInterop.migrate_to_v2`."""
        # First thing we do is initialize any fixups
        for rp in self.ResProcessing:
            rp._interactionFixup = {}
        doc = qtiv2.QTIDocument(root=qtiv2.items.AssessmentItem)
        item = doc.root
        lom = imsmd.LOM(None)
        log = []
        ident = qtiv2.core.ValidateIdentifier(self.ident)
        if self.ident != ident:
            log.append(
                "Warning: illegal NCName for ident: %s, replaced with: %s" %
                (self.ident, ident))
        item.identifier = ident
        title = self.title
        # may be specified in the metadata
        if self.ItemMetadata:
            md_titles = self.ItemMetadata.metadata.get('title', ())
        else:
            md_titles = ()
        if title:
            item.title = title
        elif md_titles:
            item.title = md_titles[0][0]
        else:
            item.title = ident
        if self.maxattempts is not None:
            log.append(
                "Warning: maxattempts can not be controlled at item level,"
                " ignored: maxattempts='" +
                self.maxattempts +
                "'")
        if self.label:
            item.label = self.label
        lang = self.resolve_lang()
        item.set_lang(lang)
        general = lom.add_child(imsmd.LOMGeneral)
        id = general.add_child(imsmd.LOMIdentifier)
        id.set_value(self.ident)
        if title:
            lom_title = general.add_child(imsmd.LOMTitle)
            lom_title = lom_title.add_child(lom_title.LangStringClass)
            lom_title.set_value(title)
            if lang:
                lom_title.set_lang(lang)
        if md_titles:
            if title:
                # If we already have a title, then we have to add
                # qmd_title as description metadata you may think
                # qmd_title is a better choice than the title attribute
                # but qmd_title is an extension so the title attribute
                # takes precedence
                i = 0
            else:
                lom_title = general.add_child(imsmd.LOMTitle)
                lom_title = lom_title.add_child(lom_title.LangStringClass)
                lom_title.set_value(md_titles[0][0])
                lang = md_titles[0][1].resolve_lang()
                if lang:
                    lom_title.set_lang(lang)
                i = 1
            for mdTitle in md_titles[i:]:
                description = general.add_child(general.DescriptionClass)
                lom_title = description.add_child(
                    description.LangStringClass)
                lom_title.set_value(mdTitle[0])
                md_lang = mdTitle[1].resolve_lang()
                if md_lang:
                    lom_title.set_lang(md_lang)
        if self.QTIComment:
            # A comment on an item is added as a description to the metadata
            description = general.add_child(general.DescriptionClass)
            description.add_child(description.LangStringClass).set_value(
                self.QTIComment.get_value())
        if self.Duration:
            log.append(
                "Warning: duration is currently outside the scope of"
                " version 2: ignored " +
                self.Duration.get_value())
        if self.ItemMetadata:
            self.ItemMetadata.migrate_to_v2(doc, lom, log)
        for objective in self.Objectives:
            if objective.view != core.View.All:
                objective.migrate_to_v2(item, log)
            else:
                objective.migrate_objectives_to_lrm(lom, log)
        if self.ItemControl:
            log.append(
                "Warning: itemcontrol is currently outside the scope of"
                " version 2")
        for rubric in self.Rubric:
            rubric.migrate_to_v2(item, log)
        if self.Presentation:
            self.Presentation.migrate_to_v2(item, log)
        if self.ResProcessing:
            if len(self.ResProcessing) > 1:
                log.append(
                    "Warning: multiople <resprocessing> not supported,"
                    " ignoring all but the last")
            self.ResProcessing[-1].migrate_to_v2(item, log)
        for feedback in self.ItemFeedback:
            feedback.migrate_to_v2(item, log)
        item.sort_declarations()
        output.append((doc, lom, log))
        # print doc.root


class ItemMetadata(common.MetadataContainerMixin, core.QTIElement):

    """The itemmetadata element contains all of the QTI-specific
    meta-data to be applied to the Item. This meta-data can consist of
    either entries defined using an external vocabulary or the
    individually named entries::

    <!ELEMENT itemmetadata (
            qtimetadata*
            qmd_computerscored?
            qmd_feedbackpermitted?
            qmd_hintspermitted?
            qmd_itemtype?
            qmd_levelofdifficulty?
            qmd_maximumscore?
            qmd_renderingtype*
            qmd_responsetype*
            qmd_scoringpermitted?
            qmd_solutionspermitted?
            qmd_status?
            qmd_timedependence?
            qmd_timelimit?
            qmd_toolvendor?
            qmd_topic?
            qmd_weighting?
            qmd_material*
            qmd_typeofsolution?
            )>

    This element contains more structure than is in common use, at the
    moment we represent this structure directly and automaticaly conform
    output to it, adding extension elements at the end.  In the future
    we might be more generous and allow input *and* output of elements
    in any sequence and provide separate methods for conforming these
    elements."""
    XMLNAME = 'itemmetadata'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        common.MetadataContainerMixin.__init__(self)
        self.QTIMetadata = []
        self.QMDComputerScored = None
        self.QMDFeedbackPermitted = None
        self.QMDHintsPermitted = None
        self.QMDItemType = None
        self.QMDLevelOfDifficulty = None
        self.QMDMaximumScore = None
        self.QMDRenderingType = []
        self.QMDResponseType = []
        self.QMDScoringPermitted = None
        self.QMDSolutionsPermitted = None
        self.QMDStatus = None
        self.QMDTimeDependence = None
        self.QMDTimeLimit = None
        self.QMDToolVendor = None
        self.QMDTopic = None
        self.QMDWeighting = None
        self.QMDMaterial = []
        self.QMDTypeOfSolution = None
        # Extensions in common use....
        self.QMDAuthor = []
        self.QMDDescription = []
        self.QMDDomain = []
        self.QMDKeywords = []
        self.QMDOrganization = []
        self.QMDTitle = None

    def get_children(self):
        for child in self.QTIMetadata:
            yield child
        if self.QMDComputerScored:
            yield self.QMDComputerScored
        if self.QMDFeedbackPermitted:
            yield self.QMDFeedbackPermitted
        if self.QMDHintsPermitted:
            yield self.QMDHintsPermitted
        if self.QMDItemType:
            yield self.QMDItemType
        if self.QMDLevelOfDifficulty:
            yield self.QMDLevelOfDifficulty
        if self.QMDMaximumScore:
            yield self.QMDMaximumScore
        for child in itertools.chain(
                self.QMDRenderingType,
                self.QMDResponseType):
            yield child
        if self.QMDScoringPermitted:
            yield self.QMDScoringPermitted
        if self.QMDSolutionsPermitted:
            yield self.QMDSolutionsPermitted
        if self.QMDStatus:
            yield self.QMDStatus
        if self.QMDTimeDependence:
            yield self.QMDTimeDependence
        if self.QMDTimeLimit:
            yield self.QMDTimeLimit
        if self.QMDToolVendor:
            yield self.QMDToolVendor
        if self.QMDTopic:
            yield self.QMDTopic
        if self.QMDWeighting:
            yield self.QMDWeighting
        for child in self.QMDMaterial:
            yield child
        if self.QMDTypeOfSolution:
            yield self.QMDTypeOfSolution
        for child in itertools.chain(
                self.QMDAuthor,
                self.QMDDescription,
                self.QMDDomain,
                self.QMDKeywords,
                self.QMDOrganization):
            yield child
        if self.QMDTitle:
            yield self.QMDTitle
        for child in core.QTIElement.get_children(self):
            yield child

    def migrate_level_of_difficulty_to_lrm(self, lom, log):
        difficulty = self.metadata.get('levelofdifficulty', ())
        for value, definition in difficulty:
            # IMS Definition says: The options are: "Pre-school",
            # "School" or "HE/FE", "Vocational" and "Professional
            # Development" so we bind this value to the "Context" in LOM
            # if one of the QTI or LOM defined terms have been used,
            # otherwise, we bind to Difficulty, as this seems to be more
            # common usage.
            context, lom_flag = QMDLevelOfDifficulty.LOMContextMap.get(
                value.lower(), (None, False))
            educational = lom.add_child(imsmd.LOMEducational)
            if context is None:
                # add value as difficulty
                lom_flag = value.lower(
                ) in QMDLevelOfDifficulty.LOMDifficultyMap
                d = educational.add_child(imsmd.LOMDifficulty)
                if lom_flag:
                    d.LRMSource.LangString.set_value(imsmd.LOM_SOURCE)
                else:
                    d.LRMSource.LangString.set_value(imsmd.LOM_UNKNOWNSOURCE)
                d.LRMSource.LangString.set_lang("x-none")
                d.LRMValue.LangString.set_value(value)
                d.LRMValue.LangString.set_lang("x-none")
            else:
                # add value as educational context
                c = educational.add_child(imsmd.LOMContext)
                if lom_flag:
                    c.LRMSource.LangString.set_value(imsmd.LOM_SOURCE)
                else:
                    c.LRMSource.LangString.set_value(imsmd.LOM_UNKNOWNSOURCE)
                c.LRMSource.LangString.set_lang("x-none")
                c.LRMValue.LangString.set_value(context)
                c.LRMValue.LangString.set_lang("x-none")

    def migrate_status_to_lrm(self, lom, log):
        status = self.metadata.get('status', ())
        for value, definition in status:
            s = lom.add_child(
                imsmd.LOMLifecycle).add_child(imsmd.LOMStatus)
            value = value.lower()
            source = QMDStatus.SourceMap.get(value, imsmd.LOM_UNKNOWNSOURCE)
            s.LRMSource.LangString.set_value(source)
            s.LRMSource.LangString.set_lang("x-none")
            s.LRMValue.LangString.set_value(value)
            s.LRMValue.LangString.set_lang("x-none")

    def migrate_topic_to_lrm(self, lom, log):
        topics = self.metadata.get('topic', ())
        for value, definition in topics:
            lang = definition.resolve_lang()
            value = value.strip()
            description = lom.add_child(
                imsmd.LOMEducational).add_child(imsmd.Description)
            description.AddString(lang, value)

    def migrate_contributor_to_lrm(self, field_name, lom_role, lom, log):
        contributors = self.metadata.get(field_name, ())
        if contributors:
            if imsmd.vobject is None:
                log.append(
                    'Warning: qmd_%s support disabled'
                    ' (vobject not installed)' % field_name)
            else:
                for value, definition in contributors:
                    lifecycle = lom.add_child(imsmd.LOMLifecycle)
                    contributor = lifecycle.add_child(imsmd.LOMContribute)
                    role = contributor.LOMRole
                    role.LRMSource.LangString.set_value(imsmd.LOM_SOURCE)
                    role.LRMSource.LangString.set_lang("x-none")
                    role.LRMValue.LangString.set_value(lom_role)
                    role.LRMValue.LangString.set_lang("x-none")
                    names = value.strip().split(',')
                    for name in names:
                        if not name.strip():
                            continue
                        vcard = imsmd.vobject.vCard()
                        vcard.add('n')
                        vcard.n.value = imsmd.vobject.vcard.Name(
                            family=name, given='')
                        vcard.add('fn')
                        vcard.fn.value = name.strip()
                        contributor.add_child(
                            imsmd.LOMCEntity).LOMVCard.set_value(vcard)

    def migrate_description_to_lrm(self, lom, log):
        descriptions = self.metadata.get('description', ())
        for value, definition in descriptions:
            lang = definition.resolve_lang()
            gen_description = lom.add_child(
                imsmd.LOMGeneral).add_child(imsmd.Description)
            gen_description = gen_description.add_child(
                gen_description.LangStringClass)
            gen_description.set_value(value)
            if lang:
                gen_description.set_lang(lang)

    def migrate_domain_to_lrm(self, lom, log):
        domains = self.metadata.get('domain', ())
        warn = False
        for value, definition in domains:
            lang = definition.resolve_lang()
            kw_value = value.strip()
            if kw_value:
                kw_container = lom.add_child(
                    imsmd.LOMGeneral).add_child(imsmd.LOMKeyword)
                kw_container = kw_container.add_child(
                    kw_container.LangStringClass)
                kw_container.set_value(kw_value)
                # set the language of the kw
                if lang:
                    kw_container.set_lang(lang)
                if not warn:
                    log.append(
                        "Warning: qmd_domain extension field will be added"
                        " as LOM keyword")
                    warn = True

    def migrate_keywords_to_lrm(self, lom, log):
        keywords = self.metadata.get('keywords', ())
        for value, definition in keywords:
            lang = definition.resolve_lang()
            values = value.split(',')
            for kw_value in values:
                v = kw_value.strip()
                if v:
                    kw_container = lom.add_child(
                        imsmd.LOMGeneral).add_child(imsmd.LOMKeyword)
                    kw_container = kw_container.add_child(
                        kw_container.LangStringClass)
                    kw_container.set_value(v)
                    # set the language of the kw
                    if lang:
                        kw_container.set_lang(lang)

    def migrate_organization_to_lrm(self, lom, log):
        organizations = self.metadata.get('organization', ())
        if organizations:
            if imsmd.vobject is None:
                log.append(
                    'Warning: qmd_organization support disabled'
                    ' (vobject not installed)')
            else:
                for value, definition in organizations:
                    lifecycle = lom.add_child(imsmd.LOMLifecycle)
                    contributor = lifecycle.add_child(imsmd.LOMContribute)
                    role = contributor.LOMRole
                    role.LRMSource.LangString.set_value(imsmd.LOM_SOURCE)
                    role.LRMSource.LangString.set_lang("x-none")
                    role.LRMValue.LangString.set_value("unknown")
                    role.LRMValue.LangString.set_lang("x-none")
                    name = value.strip()
                    vcard = imsmd.vobject.vCard()
                    vcard.add('n')
                    vcard.n.value = imsmd.vobject.vcard.Name(
                        family=name, given='')
                    vcard.add('fn')
                    vcard.fn.value = name
                    vcard.add('org')
                    vcard.org.value = [name]
                    contributor.add_child(
                        imsmd.LOMCEntity).LOMVCard.set_value(vcard)

    def migrate_to_v2(self, doc, lom, log):
        item = doc.root
        itemtypes = self.metadata.get('itemtype', ())
        for itemtype, itemtypeDef in itemtypes:
            log.append(
                "Warning: qmd_itemtype now replaced by"
                " qtiMetadata.interactionType in manifest, ignoring %s" %
                itemtype)
        self.migrate_level_of_difficulty_to_lrm(lom, log)
        self.migrate_status_to_lrm(lom, log)
        vendors = self.metadata.get('toolvendor', ())
        for value, definition in vendors:
            item.metadata.add_child(qtiv2.metadata.ToolVendor).set_value(value)
        self.migrate_topic_to_lrm(lom, log)
        self.migrate_contributor_to_lrm('author', 'author', lom, log)
        self.migrate_contributor_to_lrm('creator', 'initiator', lom, log)
        self.migrate_contributor_to_lrm('owner', 'publisher', lom, log)
        self.migrate_description_to_lrm(lom, log)
        self.migrate_domain_to_lrm(lom, log)
        self.migrate_keywords_to_lrm(lom, log)
        self.migrate_organization_to_lrm(lom, log)


class QMDMetadataElement(core.QTIElement):

    """Abstract class to represent old-style qmd_ tags"""

    def content_changed(self):
        self.declare_metadata(self.get_xmlname(), self.get_value(), self)


class QMDComputerScored(QMDMetadataElement):

    """Whether or not the Item can be computer scored."""
    XMLNAME = 'qmd_computerscored'


class QMDFeedbackPermitted(QMDMetadataElement):

    """Indicates whether or not feedback is available within the Item."""
    XMLNAME = 'qmd_feedbackpermitted'


class QMDHintsPermitted(QMDMetadataElement):

    """Indicates whether or not hints are available within the Item."""
    XMLNAME = 'qmd_hintspermitted'


class QMDItemType(QMDMetadataElement):

    """The type of Item available."""
    XMLNAME = 'qmd_itemtype'


class QMDLevelOfDifficulty(QMDMetadataElement):

    """The educational level for which the Item is intended::

    <!ELEMENT qmd_levelofdifficulty (#PCDATA)>"""
    XMLNAME = 'qmd_levelofdifficulty'

    LOMDifficultyMap = {
        "very easy": True,
        "easy": True,
        "medium": True,
        "difficult": True,
        "very difficult": True
    }
    """A mapping from difficulty values to the LOM difficulties.  This
    value is supposed to be an educational level, e.g., "pre-school" but
    in practice it is often used for values more akin to the LOM concept
    of difficulty."""

    LOMContextMap = {
        # value is outside LOM defined vocab
        "pre-school": ("pre-school", False),
        "school": ("school", True),
        "he/fe": ("higher education", True),
        # value is outside LOM defined vocab
        "vocational": ("vocational", False),
        "professional development": ("training", True)
    }
    """A mapping from difficulty values to the LOM contexts.  This mapping
    returns a tuple of the context value and a boolean indicating whether or
    not this is one from the LOM standard or not."""


class QMDMaterial(QMDMetadataElement):

    """The type of material content used within the Item."""
    XMLNAME = 'qmd_material'


class QMDMaximumScore(QMDMetadataElement):

    """The maximum score possible from the Item."""
    XMLNAME = 'qmd_maximumscore'


class QMDRenderingType(QMDMetadataElement):

    """The type of rendering used within the Item."""
    XMLNAME = 'qmd_renderingtype'


class QMDResponseType(QMDMetadataElement):

    """The class of response expected for the Item."""
    XMLNAME = 'qmd_responsetype'


class QMDScoringPermitted(QMDMetadataElement):

    """Indicates whether or not scoring is available within the Item."""
    XMLNAME = 'qmd_scoringpermitted'


class QMDSolutionsPermitted(QMDMetadataElement):

    """Indicates whether or not solutions are available within the Item."""
    XMLNAME = 'qmd_solutionspermitted'


class QMDStatus(QMDMetadataElement):

    """The status of the Item."""
    XMLNAME = 'qmd_status'

    SourceMap = {
        'draft': imsmd.LOM_SOURCE,
        'final': imsmd.LOM_SOURCE,
        'revised': imsmd.LOM_SOURCE,
        'unavailable': imsmd.LOM_SOURCE,
        'experimental': core.QTI_SOURCE,
        'normal': core.QTI_SOURCE,
        'retired': core.QTI_SOURCE
    }
    """A mapping from status values to a metadata source, one of the
    following constants: :py:data:`~pyslet.imsmdv1p2p1.LOM_SOURCE`
    :py:data:`~pyslet.qtiv1.core.QTI_SOURCE`"""


class QMDTimeDependence(QMDMetadataElement):

    """Whether or not the responses are time dependent."""
    XMLNAME = 'qmd_timedependence'


class QMDTimeLimit(QMDMetadataElement):

    """The number of minutes to be permitted for the completion of the Item."""
    XMLNAME = 'qmd_timelimit'


class QMDToolVendor(QMDMetadataElement):

    """The name of the vendor of the tool creating the Item."""
    XMLNAME = 'qmd_toolvendor'


class QMDTopic(QMDMetadataElement):

    """The brief description of the topic covered by the Item."""
    XMLNAME = 'qmd_topic'


class QMDTypeOfSolution(QMDMetadataElement):

    """The type of solution available in the Item."""
    XMLNAME = 'qmd_typeofsolution'


class QMDWeighting(QMDMetadataElement):

    """The weighting to be applied to the scores allocated to this Item
    before aggregations with other scores."""
    XMLNAME = 'qmd_weighting'


class QMDAuthor(QMDMetadataElement):

    """Not defined by QTI but seems to be in common use."""
    XMLNAME = 'qmd_author'


class QMDDescription(QMDMetadataElement):

    """Not defined by QTI but seems to be in common use."""
    XMLNAME = 'qmd_description'


class QMDDomain(QMDMetadataElement):

    """Not defined by QTI but seems to be in common use."""
    XMLNAME = 'qmd_domain'


class QMDKeywords(QMDMetadataElement):

    """Not defined by QTI but seems to be in common use."""
    XMLNAME = 'qmd_keywords'


class QMDOrganization(QMDMetadataElement):

    """Not defined by QTI but seems to be in common use."""
    XMLNAME = 'qmd_organization'


class QMDTitle(QMDMetadataElement):

    """Not defined by QTI but seems to be in common use."""
    XMLNAME = 'qmd_title'


class ItemPreCondition(core.QTIElement):

    """The preconditions that control whether or not the Item is activated::

    <!ELEMENT itemprecondition (#PCDATA)>"""
    XMLNAME = 'itemprecondition'
    XMLCONTENT = xml.XMLMixedContent


class ItemPostCondition(core.QTIElement):

    """The postconditions that control whether or not the next Item may be
    activated::

    <!ELEMENT itempostcondition (#PCDATA)>"""
    XMLNAME = 'itempostcondition'
    XMLCONTENT = xml.XMLMixedContent


class ItemControl(common.QTICommentContainer):

    """The control switches that are used to enable or disable the display of
    hints, solutions and feedback within the Item::

    <!ELEMENT itemcontrol (qticomment?)>
    <!ATTLIST itemcontrol  feedbackswitch  (Yes | No )  'Yes'
            hintswitch  (Yes | No )  'Yes'
            solutionswitch  (Yes | No )  'Yes'
            view	(All | Administrator | AdminAuthority | Assessor | Author |
                            Candidate | InvigilatorProctor | Psychometrician |
                            Scorer | Tutor ) 'All' >
    """
    XMLNAME = 'itemcontrol'
    XMLATTR_feedbackswitch = (
        'feedbackSwitch', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_hintswitch = ('hintSwitch', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_solutionswitch = (
        'solutionSwitch', core.ParseYesNo, core.FormatYesNo)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.feedbackSwitch = True
        self.hintSwitch = True
        self.solutionSwitch = True
        self.view = core.View.DEFAULT


class ItemRubric(common.Rubric):

    """The itemrubric element is used to contain contextual information
    that is important to the element e.g. it could contain standard data
    values that might or might not be useful for answering the question.
    Different sets of rubric can be defined for each of the possible
    views::

    <!ELEMENT itemrubric (material)>
    <!ATTLIST itemrubric
            view	(All | Administrator | AdminAuthority | Assessor |
                     Author | Candidate | InvigilatorProctor |
                     Psychometrician | Scorer | Tutor ) 'All' >

    We are generous with this element, extending the allowable content
    model to make it equivalent to <rubric> which is a superset.
    <itemrubric> was deprecated in favour of <rubric> with QTI v1.2"""
    XMLNAME = 'itemrubric'
    XMLCONTENT = xml.ElementContent


class FlowContainer(common.ContentMixin, common.QTICommentContainer):

    """Abstract class used to represent elements that contain flow and
    related elements::

    <!ELEMENT XXXXXXXXXX (qticomment? , (material | flow | response_*)* )>"""

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        common.ContentMixin.__init__(self)

    def get_children(self):
        return itertools.chain(
            common.QTICommentContainer.get_children(self),
            common.ContentMixin.get_content_children(self))

    def content_child(self, child_class):
        return child_class in (common.Material, Flow) or \
            issubclass(child_class, Response)


class Presentation(FlowContainer, common.PositionMixin):

    """This element contains all of the instructions for the
    presentation of the question during an evaluation. This information
    includes the actual material to be presented. The labels for the
    possible responses are also identified and these are used by the
    response processing element defined elsewhere in the Item::

    <!ELEMENT presentation (qticomment? ,
            (flow |
                    (material |
                    response_lid |
                    response_xy |
                    response_str |
                    response_num |
                    response_grp |
                    response_extension)+
                    )
            )>
    <!ATTLIST presentation  label CDATA  #IMPLIED
            xml:lang CDATA  #IMPLIED
            y0 CDATA  #IMPLIED
            x0 CDATA  #IMPLIED
            width CDATA  #IMPLIED
            height CDATA  #IMPLIED >"""
    XMLNAME = 'presentation'
    XMLATTR_label = 'label'

    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        FlowContainer.__init__(self, parent)
        common.PositionMixin.__init__(self)
        self.label = None

    def migrate_to_v2(self, v2_item, log):
        """Presentation maps to the main content in item_body."""
        item_body = v2_item.get_or_add_child(qtiv2.content.ItemBody)
        if self.got_position():
            log.append(
                "Warning: discarding absolute positioning information"
                " on presentation")
        if self.inline_children():
            p = item_body.add_child(
                html.P, (qtiv2.core.IMSQTI_NAMESPACE, 'p'))
            if self.label is not None:
                # p.label=self.label
                p.set_attribute('label', self.label)
            self.migrate_content_to_v2(p, html.InlineMixin, log)
        elif self.label is not None:
            # We must generate a div to hold the label, we can't rely on
            # owning the whole item_body
            div = item_body.add_child(
                html.Div, (qtiv2.core.IMSQTI_NAMESPACE, 'div'))
            div.set_attribute('label', self.label)
            # Although div will take an inline directly we force blocking at
            # the top level
            self.migrate_content_to_v2(div, html.BlockMixin, log)
        else:
            # mixture or block children, force use of blocks
            self.migrate_content_to_v2(item_body, html.BlockMixin, log)
        self.clean_hotspot_images(item_body)

    def clean_hotspot_images(self, item_body):
        """Removes spurious img tags which represent images used in
        hotspotInteractions.

        Unfortunately we have to do this because images needed in hotspot
        interactions are often clumsily placed outside the response/render
        constructs.  Rather than fiddle around at the time we simply migrate
        the lot, duplicating the images in the hotspotInteractions.  When the
        item_body is complete we do a grand tidy up to remove spurious
        images."""
        hotspots = list(
            item_body.find_children_depth_first(
                (qtiv2.interactions.HotspotInteraction,
                 qtiv2.interactions.SelectPointInteraction),
                False))
        images = list(item_body.find_children_depth_first(html.Img, False))
        for hs in hotspots:
            for img in images:
                # migrated images/hotspots will always have absolute URIs
                if img.src and str(img.src) == str(hs.Object.data):
                    parent = img.parent
                    parent.remove_child(img)
                    if (isinstance(parent, html.P) and
                            len(list(parent.get_children())) == 0):
                        # It is always safe to remove a paragraph left
                        # empty by deleting an image. The chances are
                        # the paragraph was created by us to house a
                        # matimage
                        parent.parent.remove_child(parent)

    def is_inline(self):
        return False


class Flow(FlowContainer, common.FlowMixin):

    """This element contains all of the instructions for the
    presentation with flow blocking of the question during a test. This
    information includes the actual material to be presented. The labels
    for the possible responses are also identified and these are used by
    the response processing element defined elsewhere in the Item::

    <!ELEMENT flow (qticomment? ,
            (flow |
            material |
            material_ref |
            response_lid |
            response_xy |
            response_str |
            response_num |
            response_grp |
            response_extension)+
            )>
    <!ATTLIST flow  class CDATA  'Block' >"""
    XMLNAME = 'flow'
    XMLATTR_class = 'flow_class'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        FlowContainer.__init__(self, parent)

    def is_inline(self):
        """flow is always treated as a block if flow_class is specified,
        otherwise it is treated as a block unless it is an only child."""
        if not self.flow_class:
            return self.inline_children()
        else:
            return False

    def migrate_content_to_v2(self, parent, child_type, log):
        """flow typically maps to a div element.

        A flow with a specified class always becomes a div
        A flow with inline children generates a paragraph to hold them
        A flow with no class is ignored."""
        if self.flow_class:
            if child_type in (html.BlockMixin, html.FlowMixin):
                div = parent.add_child(
                    html.Div, (qtiv2.core.IMSQTI_NAMESPACE, 'div'))
                div.style_class = self.flow_class
                FlowContainer.migrate_content_to_v2(self, div, html.FlowMixin,
                                                    log)
            else:
                span = parent.add_child(
                    html.Span, (qtiv2.core.IMSQTI_NAMESPACE, 'span'))
                span.style_class = self.flow_class
                FlowContainer.migrate_content_to_v2(
                    self, span, html.InlineMixin, log)
        else:
            FlowContainer.migrate_content_to_v2(self, parent, child_type, log)


class Response(common.ContentMixin, core.QTIElement):

    """Abstract class to act as a parent for all response_* elements."""

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        common.ContentMixin.__init__(self)


class ResponseExtension(Response):

    """This element supports proprietary alternatives to the current range of
    'response' elements::

    <!ELEMENT response_extension ANY>"""
    XMLNAME = "response_extension"
    XMLCONTENT = xml.XMLMixedContent


class ResponseThing(Response):

    """Abstract class for the main response_* elements::

    <!ELEMENT response_* ((material | material_ref)? ,
            (render_choice | render_hotspot | render_slider | render_fib |
            render_extension) ,
            (material | material_ref)?)>
    <!ATTLIST response_*
            rcardinality	(Single | Multiple | Ordered )  'Single'
    rtiming  		(Yes | No )  'No'
            ident 			CDATA  #REQUIRED >"""
    XMLATTR_ident = 'ident'
    XMLATTR_rcardinality = (
        'rCardinality',
        core.RCardinality.from_str_title,
        core.RCardinality.to_str)
    XMLATTR_rtiming = ('rTiming', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_ident = 'ident'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        Response.__init__(self, parent)
        self.ident = None
        self.rCardinality = core.RCardinality.DEFAULT
        self.rTiming = False
        self.intro = []
        self.prompt = []
        self.inlinePrompt = True
        self.render = None
        self.outro = []
        self.footer = []
        self.inlineFooter = True

    def add_child(self, child_class, name=None):
        if issubclass(child_class, (common.Material, common.MaterialRef)):
            child = child_class(self)
            if self.render:
                self.outro.append(child)
            else:
                self.intro.append(child)
            if name:
                child.set_xmlname(name)
            return child
        elif issubclass(child_class, Render):
            child = child_class(self)
            self.render = child
            if name:
                child.set_xmlname(name)
            return child
        elif issubclass(child_class, common.ContentMixin):
            raise TypeError
        else:
            return super(ResponseThing, self).add_child(child_class, name)

    def get_children(self):
        for child in self.intro:
            yield child
        if self.render:
            yield self.render
        for child in self.outro:
            yield child

    def content_changed(self):
        if isinstance(self.render, RenderFIB) and self.render.mixed_model():
            # use simplified prompt logic.
            self.prompt = self.intro
            self.inlintPrompt = True
            for child in self.prompt:
                if not child.is_inline():
                    self.inlinePrompt = False
            self.footer = self.outro
            self.inlineFooter = True
            for child in self.footer:
                if not child.is_inline():
                    self.inlineFooter = False
        elif self.render:
            # all the material up to the first response_label is the prompt
            self.prompt = []
            self.inlinePrompt = True
            render_children = self.render.get_label_content()
            for child in self.intro + render_children:
                # print child.__class__,child.xmlname
                if isinstance(child, ResponseLabel):
                    break
                self.prompt.append(child)
                if not child.is_inline():
                    self.inlinePrompt = False
            self.footer = []
            self.inlineFooter = True
            found_label = False
            for child in render_children + self.outro:
                if isinstance(child, ResponseLabel):
                    self.footer = []
                    self.inlineFooter = True
                    found_label = True
                    continue
                if found_label:
                    self.footer.append(child)
                    if not child.is_inline():
                        self.inlineFooter = False

    def inline_children(self):
        return self.inlinePrompt and (
            self.render is None or
            self.render.is_inline()) and self.inlineFooter

    def get_base_type(self, interaction):
        """Returns the base type to use for the given interaction."""
        raise core.QTIUnimplementedError(
            "BaseType selection for %s" % self.__class__.__name__)

    def migrate_content_to_v2(self, parent, child_type, log):
        if self.inlinePrompt:
            interaction_prompt = self.prompt
        else:
            if child_type is html.InlineMixin:
                raise core.QTIError("Unexpected attempt to inline interaction")
            interaction_prompt = None
            if isinstance(self.render, RenderHotspot):
                div = parent.add_child(
                    html.Div, (qtiv2.core.IMSQTI_NAMESPACE, 'div'))
                common.ContentMixin.migrate_content_to_v2(
                    self, div, html.FlowMixin, log, self.prompt)
                # Now we need to find any images and pass them to render
                # hotspot instead which we do by reusing the interaction_prompt
                # (currently we only find the first image).
                interaction_prompt = list(
                    div.find_children_depth_first(html.Img, False))[0:1]
            else:
                common.ContentMixin.migrate_content_to_v2(
                    self, parent, child_type, log, self.prompt)
        if self.render:
            interaction_list = self.render.migrate_interaction_to_v2(
                parent, child_type, interaction_prompt, log)
            item = parent.find_parent(qtiv2.items.AssessmentItem)
            if (len(interaction_list) > 1 and
                    self.rCardinality == core.RCardinality.Single):
                log.append(
                    "Error: unable to migrate a response with Single"
                    " cardinality to a single interaction: %s" %
                    self.ident)
                interaction_list = []
                response_list = []
            else:
                base_identifier = qtiv2.core.ValidateIdentifier(self.ident)
                response_list = []
                if len(interaction_list) > 1:
                    i = 0
                    for interaction in interaction_list:
                        i = i + 1
                        while True:
                            ridentifier = "%s_%02i" % (base_identifier, i)
                            if (item is None or
                                    not item.IsDeclared(ridentifier)):
                                break
                        interaction.responseIdentifier = ridentifier
                        response_list.append(ridentifier)
                elif interaction_list:
                    interaction = interaction_list[0]
                    interaction.responseIdentifier = base_identifier
                    response_list = [interaction.responseIdentifier]
            if item:
                for i, r in zip(interaction_list, response_list):
                    d = item.add_child(qtiv2.variables.ResponseDeclaration)
                    d.identifier = r
                    d.cardinality = core.MigrateV2Cardinality(
                        self.rCardinality)
                    d.baseType = self.get_base_type(interaction_list[0])
                    self.render.migrate_interaction_default_to_v2(d, i)
                    item.RegisterDeclaration(d)
                if len(response_list) > 1:
                    d = item.add_child(qtiv2.variables.OutcomeDeclaration)
                    d.identifier = base_identifier
                    d.cardinality = core.MigrateV2Cardinality(
                        self.rCardinality)
                    d.baseType = self.get_base_type(interaction_list[0])
                    item.RegisterDeclaration(d)
                    # now we need to fix this outcome up with a value in
                    # response processing
                    self_item = self.find_parent(Item)
                    if self_item:
                        for rp in self_item.ResProcessing:
                            rp._interactionFixup[base_identifier] = \
                                response_list
        # the footer is in no-man's land so we just back-fill
        common.ContentMixin.migrate_content_to_v2(
            self, parent, child_type, log, self.footer)


class ResponseLId(ResponseThing):

    """The <response_lid> element contains the instructions for the
    presentation of questions whose response will be the logical label
    of the selected answer. The question can be rendered in a variety of
    ways depending on the way in which the material is to be presented
    to the participant::

    <!ELEMENT response_lid ((material | material_ref)? ,
            (render_choice | render_hotspot | render_slider | render_fib |
            render_extension) ,
            (material | material_ref)?)>
    <!ATTLIST response_lid
            rcardinality	(Single | Multiple | Ordered )  'Single'
            rtiming  		(Yes | No )  'No'
            ident 			CDATA  #REQUIRED >"""
    XMLNAME = 'response_lid'

    def get_base_type(self, interaction):
        """We always return identifier for response_lid."""
        return qtiv2.variables.BaseType.identifier


class ResponseXY(ResponseThing):

    """The <response_xy> element contains the instructions for the
    presentation of questions whose response will be the 'x-y'
    co-ordinate of the selected answer. The question can be rendered in
    a variety of ways depending on the way in which the material is to
    be presented to the participant::

    <!ELEMENT response_xy ((material | material_ref)? ,
            (render_choice | render_hotspot | render_slider | render_fib |
            render_extension) ,
            (material | material_ref)?)>
    <!ATTLIST response_xy
            rcardinality	(Single | Multiple | Ordered )  'Single'
            rtiming  		(Yes | No )  'No'
            ident 			CDATA  #REQUIRED >
    """
    XMLNAME = 'response_xy'

    def get_base_type(self, interaction):
        """For select point we return a point for response_xy."""
        if isinstance(interaction, qtiv2.interactions.SelectPointInteraction):
            return qtiv2.variables.BaseType.point
        else:
            return ResponseThing.get_base_type(self)


class ResponseStr(ResponseThing):

    """The <response_str> element contains the instructions for the
    presentation of questions whose response will be the a string. The
    question can be rendered in a variety of ways depending on the way
    in which the material is to be presented to the participant::

    <!ELEMENT response_str ((material | material_ref)? ,
            (render_choice | render_hotspot | render_slider | render_fib |
            render_extension) ,
            (material | material_ref)?)>

    <!ATTLIST response_str
            rcardinality	(Single | Multiple | Ordered )  'Single'
            ident 			CDATA #REQUIRED
            rtiming  		(Yes | No )  'No' >"""
    XMLNAME = 'response_str'

    def get_base_type(self, interaction):
        """We always return string for response_str."""
        return qtiv2.variables.BaseType.string


class ResponseNum(ResponseThing):

    """The <response_num> element contains the instructions for the
    presentation of questions whose response will be a number. The
    question can be rendered in a variety of ways depending on the way
    in which the material is to be presented to the participant::

    <!ELEMENT response_num ((material | material_ref)? ,
            (render_choice | render_hotspot | render_slider | render_fib |
            render_extension) ,
            (material | material_ref)?)>
    <!ATTLIST response_num
            numtype			(Integer | Decimal | Scientific )  'Integer'
            rcardinality	(Single | Multiple | Ordered )  'Single'
            ident CDATA  	#REQUIRED
            rtiming  		(Yes | No )  'No' >
    """
    XMLNAME = 'response_num'
    XMLATTR_numtype = (
        'numType', core.NumType.from_str_title, core.NumType.to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        ResponseThing.__init__(self, parent)
        self.numType = core.NumType.Integer

    def get_base_type(self, interaction):
        """Returns integer for numtype of "Integer", float otherwise."""
        if self.numType == core.NumType.Integer:
            return qtiv2.variables.BaseType.integer
        else:
            return qtiv2.variables.BaseType.float


class ResponseGrp(common.ContentMixin, core.QTIElement):

    """The <response_grp> element contains the instructions for the
    presentation of questions whose response will be a group of logical
    identifiers. The question can be rendered in a variety of ways
    depending on the way in which the material is to be presented to the
    participant::

    <!ELEMENT response_grp ((material | material_ref)? ,
            (render_choice | render_hotspot | render_slider | render_fib |
            render_extension) ,
            (material | material_ref)?)>
    <!ATTLIST response_grp
            rcardinality	(Single | Multiple | Ordered )  'Single'
            ident			CDATA  #REQUIRED
            rtiming			(Yes | No )  'No' >"""
    XMLNAME = 'response_grp'
    XMLCONTENT = xml.ElementContent


class Render(common.ContentMixin, core.QTIElement):

    """Abstract class to act as a parent for all render_* elements."""

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        common.ContentMixin.__init__(self)


class RenderThing(Render):

    """Abstract base class for all render_* objects::

    <!ELEMENT render_* ((material | material_ref | response_label |
    flow_label)* , response_na?)>"""
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        Render.__init__(self, parent)
        self.ResponseNA = None

    def content_child(self, child_class):
        return child_class in (common.Material, common.MaterialRef,
                               ResponseLabel, FlowLabel)

    def get_children(self):
        for child in self.get_content_children():
            yield child
        if self.ResponseNA:
            yield self.ResponseNA

    def get_label_content(self):
        """Returns a flat list of content items, stripping away flow_labels."""
        children = []
        for child in self.get_content_children():
            if isinstance(child, FlowLabel):
                children = children + child.get_label_content()
            else:
                children.append(child)
        return children

    def is_inline(self):
        for child in self.get_label_content():
            if not child.is_inline():
                return False
        return True

    def migrate_interaction_to_v2(self, parent, child_type, prompt, log):
        raise core.QTIUnimplementedError(
            "%s x %s" %
            (self.parent.__class__.__name__, self.__class__.__name__))

    def migrate_interaction_default_to_v2(self, parent, interaction):
        # Most interactions do not need default values.
        pass


class RenderChoice(RenderThing):

    """The <render_choice> element instructs the question-engine to render the
    question using a classical multiple-choice format. The number of possible
    responses is determined by the <response_label> elements contained. Both
    flowed and non-flowed formats are supported::

    <!ELEMENT render_choice ((material | material_ref | response_label |
    flow_label)* , response_na?)>
    <!ATTLIST render_choice
            shuffle     (Yes | No )  'No'
            minnumber	CDATA  #IMPLIED
            maxnumber	CDATA  #IMPLIED >"""
    XMLNAME = 'render_choice'
    XMLATTR_shuffle = ('shuffle', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_minnumber = ('minNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_maxnumber = ('maxNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        RenderThing.__init__(self, parent)
        self.shuffle = False
        self.minNumber = None
        self.maxNumber = None

    def is_inline(self):
        """This always results in a block-like interaction."""
        return False

    def migrate_interaction_to_v2(self, parent, child_type, prompt, log):
        """Migrates this content to v2 adding it to the parent content node."""
        interaction = None
        if isinstance(self.parent, ResponseLId):
            if child_type is html.InlineMixin:
                raise core.QTIError(
                    "Unexpected attempt to put block interaction in"
                    " inline context")
            if self.parent.rCardinality == core.RCardinality.Ordered:
                raise core.QTIUnimplementedError("OrderInteraction")
            else:
                interaction = parent.add_child(
                    qtiv2.interactions.ChoiceInteraction)
        else:
            raise core.QTIUnimplementedError(
                "%s x render_choice" % self.parent.__class__.__name__)
        if prompt:
            interaction_prompt = interaction.add_child(
                qtiv2.interactions.Prompt)
            for child in prompt:
                child.migrate_content_to_v2(
                    interaction_prompt, html.InlineMixin, log)
        if self.minNumber is not None:
            interaction.minChoices = self.minNumber
        if self.maxNumber is not None:
            interaction.maxChoices = self.maxNumber
        interaction.shuffle = self.shuffle
        for child in self.get_label_content():
            if isinstance(child, ResponseLabel):
                child.migrate_simple_choice_to_v2(interaction, log)
        return [interaction]


class RenderHotspot(RenderThing):

    """The <render_hotspot> element instructs the question-engine to render the
    question using a classical image hot-spot format. The number of possible
    responses is determined by the <response_label> elements contained. Both
    flowed and non-flowed formats are supported::

    <!ELEMENT render_hotspot ((material | material_ref | response_label |
    flow_label)* , response_na?)>
    <!ATTLIST render_hotspot
            maxnumber	CDATA  #IMPLIED
            minnumber	CDATA  #IMPLIED
            showdraw    (Yes | No )  'No' >"""
    XMLNAME = 'render_hotspot'
    XMLATTR_maxnumber = ('maxNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minnumber = ('minNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_showdraw = ('showDraw', core.ParseYesNo, core.FormatYesNo)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        RenderThing.__init__(self, parent)
        self.maxNumber = None
        self.minNumber = None
        self.showDraw = False

    def is_inline(self):
        """This always results in a block-like interaction."""
        return False

    def migrate_interaction_to_v2(self, parent, child_type, prompt, log):
        """Migrates this content to v2 adding it to the parent content node."""
        interaction = None
        if isinstance(self.parent, ResponseLId):
            if self.parent.rCardinality == core.RCardinality.Ordered:
                raise core.QTIUnimplementedError("GraphicOrderInteraction")
            else:
                interaction = parent.add_child(
                    qtiv2.interactions.HotspotInteraction)
        elif isinstance(self.parent, ResponseXY):
            if self.parent.rCardinality == core.RCardinality.Ordered:
                raise core.QTIUnimplementedError(
                    'response_xy x render_hotspot')
            else:
                interaction = parent.add_child(
                    qtiv2.interactions.SelectPointInteraction)
        else:
            raise core.QTIUnimplementedError(
                "%s x render_hotspot" % self.parent.__class__.__name__)
        if self.showDraw:
            log.append(
                'Warning: ignoring showdraw="Yes", what did you really want'
                ' to happen?')
        if self.minNumber is not None:
            interaction.minChoices = self.minNumber
        if self.maxNumber is not None:
            interaction.maxChoices = self.maxNumber
        labels = list(self.find_children_depth_first(ResponseLabel, False))
        # prompt is either a single <img> tag we already migrated or.. a
        # set of inline objects that are still to be migrated (and which
        # should contain the hotspot image).
        img = None
        interaction_prompt = None
        hotspot_image = interaction.add_child(
            html.Object, (qtiv2.core.IMSQTI_NAMESPACE, 'object'))
        if prompt:
            if not isinstance(prompt[0], html.Img):
                interaction_prompt = interaction.add_child(
                    qtiv2.interactions.Prompt)
                for child in prompt:
                    child.migrate_content_to_v2(
                        interaction_prompt, html.InlineMixin, log)
                prompt = list(
                    interaction_prompt.find_children_depth_first(
                        html.Img,
                        False))[
                    0:1]
        if prompt:
            # now the prompt should be a list containing a single image to use
            # as the hotspot
            img = prompt[0]
            hotspot_image.data = img.src
            hotspot_image.height = img.height
            hotspot_image.width = img.width
            if img.src:
                # Annoyingly, Img throws away mime-type information from
                # matimage
                images = list(
                    self.parent.find_children_depth_first(
                        common.MatImage,
                        False))[
                    0:1]
                if images and images[0].uri:
                    # Check that this is the right image in case img was
                    # embedded in MatText
                    if (str(images[0].resolve_uri(images[0].uri)) ==
                            str(img.resolve_uri(img.src))):
                        hotspot_image.type = images[0].imageType
            for child in labels:
                if isinstance(child, ResponseLabel):
                    child.migrate_hotspot_choice_to_v2(interaction, log)
            return [interaction]
        else:
            # tricky, let's start by getting all the matimage elements in the
            # presentation
            images = []
            presentation = self.find_parent(Presentation)
            if presentation:
                images = list(
                    presentation.find_children_depth_first(
                        common.MatImage,
                        False))
            hsi = []
            if len(images) == 1:
                # Single image that must have gone AWOL
                hsi.append((images[0], labels))
            else:
                # multiple images are scanned for those at fixed positions in
                # the presentation which are hit by a hotspot (interpreted
                # relative to the presentation).
                for img in images:
                    hits = []
                    for child in labels:
                        if child.hotspot_in_image(img):
                            hits.append(child)
                    if hits:
                        # So some of our hotspots hit this image
                        hsi.append((img, hits))
            if len(hsi) == 0:
                log.append(
                    "Error: omitting render_hotspot with no hotspot image")
                return []
            else:
                img, hits = hsi[0]
                hotspot_image.data = img.resolve_uri(img.uri)
                hotspot_image.type = img.imageType
                hotspot_image.height = html.LengthType(img.height)
                hotspot_image.width = html.LengthType(img.width)
                # it will get cleaned up later
                if len(hsi) > 0:
                    # Worst case: multiple images => multiple hotspot
                    # interactions
                    if self.maxNumber is not None:
                        log.append(
                            "Warning: multi-image hotspot maps to multiple"
                            " interactions, maxChoices can no longer be"
                            " enforced")
                    interaction.minChoices = None
                    for child in hits:
                        child.migrate_hotspot_choice_to_v2(
                            interaction, log, img.x0, img.y0)
                    interaction_list = [interaction]
                    for img, hits in hsi[1:]:
                        interaction = parent.add_child(
                            qtiv2.interactions.HotspotInteraction)
                        if self.maxNumber is not None:
                            interaction.maxChoices = self.maxNumber
                        hotspot_image = interaction.add_child(
                            html.Object, (qtiv2.core.IMSQTI_NAMESPACE,
                                          'object'))
                        hotspot_image.data = img.resolve_uri(img.uri)
                        hotspot_image.type = img.imageType
                        hotspot_image.height = html.LengthType(img.height)
                        hotspot_image.width = html.LengthType(img.width)
                        for child in hits:
                            child.migrate_hotspot_choice_to_v2(
                                interaction, log, img.x0, img.y0)
                        interaction_list.append(interaction)
                    return interaction_list
                else:
                    # Best case: single image that just went AWOL
                    for child in labels:
                        child.migrate_hotspot_choice_to_v2(
                            interaction, log, img.x0, img.y0)
                    return [interaction]


class RenderFIB(RenderThing):

    """The <render_fib> element instructs the question-engine to render the
    question using a classical fill-in-blank format. The number of possible
    responses is determined by the <response_label> elements contained. Both
    flowed and non-flowed formats are supported::

    <!ELEMENT render_fib ((material | material_ref | response_label |
    flow_label)* , response_na?)>
    <!ATTLIST render_fib
            encoding	CDATA  'UTF_8'
            fibtype		(String | Integer | Decimal | Scientific )  'String'
            rows		CDATA  #IMPLIED
            maxchars	CDATA  #IMPLIED
            prompt		(Box | Dashline | Asterisk | Underline )  #IMPLIED
            columns		CDATA  #IMPLIED
            charset		CDATA  'ascii-us'
            maxnumber	CDATA  #IMPLIED
            minnumber	CDATA  #IMPLIED >"""
    XMLNAME = 'render_fib'
    XMLATTR_encoding = 'encoding'
    XMLATTR_fibtype = (
        'fibType', core.FIBType.from_str_title, core.FIBType.to_str)
    XMLATTR_rows = ('rows', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_maxchars = ('maxChars', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_prompt = (
        'prompt',
        core.PromptType.from_str_title,
        core.PromptType.to_str)
    XMLATTR_columns = ('columns', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_charset = 'charset'
    XMLATTR_maxnumber = ('maxNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minnumber = ('minNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        RenderThing.__init__(self, parent)
        self.encoding = 'UTF_8'
        self.fibType = core.FIBType.String
        self.rows = None
        self.maxChars = None
        self.prompt = None
        self.columns = None
        self.charset = 'ascii-us'
        self.minNumber = None
        self.maxNumber = None
        self.labels = []

    def content_changed(self):
        self.labels = list(
            self.find_children_depth_first(ResponseLabel, False))

    def mixed_model(self):
        """Indicates whether or not this FIB uses a mixed model or not.

        A mixed model means that render_fib is treated as a mixture of
        interaction and content elements.  In an unmixed model the render_fib
        is treated as a single block interaction with an optional prompt.

        If the render_fib contains content, followed by labels, then we treat
        it as a prompt + fib and return False

        If the render_fib contains a mixture of content and labels, then we
        return True

        If the render_fib contains no content at all we assume it needs to be
        mixed into the surrounding content and return True."""
        children = self.get_label_content()
        found_label = False
        found_content = False
        for child in children:
            if isinstance(child, ResponseLabel):
                found_label = True
            elif found_label:
                # any content after the first label means mixed mode.
                return True
            else:
                found_content = True
        return not found_content

    def is_inline(self):
        if self.mixed_model():
            return RenderThing.is_inline(self)
        else:
            return False

    def inline_fib_label(self):
        if self.rows is None or self.rows == 1:
            return True
        else:
            return False

    def migrate_fib_label_to_v2(self, label, parent, child_type, log):
        if self.inline_fib_label() or child_type is html.InlineMixin:
            parent.add_child(qtiv2.interactions.TextEntryInteraction)
        else:
            parent.add_child(qtiv2.interactions.ExtendedTextInteraction)
        if list(label.get_children()):
            log.append(
                "Warning: ignoring content in render_fib.response_label")

    def migrate_interaction_to_v2(self, parent, child_type, prompt, log):
        if self.inline_fib_label() or child_type is html.InlineMixin:
            interaction_type = qtiv2.interactions.TextEntryInteraction
        else:
            interaction_type = qtiv2.interactions.ExtendedTextInteraction
        interaction_list = list(
            parent.find_children_depth_first(interaction_type, False))
        icount = len(interaction_list)
        # now migrate this object
        RenderThing.migrate_content_to_v2(self, parent, child_type, log)
        interaction_list = list(
            parent.find_children_depth_first(interaction_type, False))
        # ignore any pre-existing interactions of this type
        interaction_list = interaction_list[icount:]
        if (self.parent.rCardinality == core.RCardinality.Single and
                len(interaction_list) > 1):
            log.append(
                "Warning: single response fib ignoring all but last"
                " <response_label>")
            for interaction in interaction_list[:-1]:
                interaction.parent.remove_child(interaction)
            interaction_list = interaction_list[-1:]
        for interaction in interaction_list:
            if self.maxChars is not None:
                interaction.expectedLength = self.maxChars
            elif self.rows is not None and self.columns is not None:
                interaction.expectedLength = self.rows * self.columns
            if interaction_type is qtiv2.interactions.ExtendedTextInteraction:
                if self.rows is not None:
                    interaction.expectedLines = self.rows
        return interaction_list


class RenderSlider(RenderThing):

    """The <render_slider> element instructs the question-engine to render the
    question using dynamic slider. The number of possible responses is
    determined by the <response_label> elements contained. Both flowed and
    non-flowed formats are supported::

    <!ELEMENT render_slider ((material | material_ref | response_label |
    flow_label)* , response_na?)>
    <!ATTLIST render_slider
            orientation		(Horizontal | Vertical )  'Horizontal'
            lowerbound		CDATA  #REQUIRED
            upperbound		CDATA  #REQUIRED
            step			CDATA  #IMPLIED
            startval		CDATA  #IMPLIED
            steplabel		(Yes | No )  'No'
            maxnumber		CDATA  #IMPLIED
            minnumber		CDATA  #IMPLIED >"""
    XMLNAME = 'render_slider'
    XMLATTR_orientation = (
        'orientation',
        core.Orientation.from_str_title,
        core.Orientation.to_str)
    XMLATTR_lowerbound = (
        'lowerBound', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_upperbound = (
        'upperBound', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_step = ('step', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_startval = ('startVal', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_steplabel = ('stepLabel', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_maxnumber = ('maxNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minnumber = ('minNumber', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        RenderThing.__init__(self, parent)
        self.orientation = core.Orientation.Horizontal
        self.lowerBound = None
        self.upperBound = None
        self.step = None
        self.startVal = None
        self.stepLabel = False
        self.minNumber = None
        self.maxNumber = None

    def is_inline(self):
        """This always results in a block-like interaction."""
        return False

    def migrate_interaction_to_v2(self, parent, child_type, prompt, log):
        """Migrates this content to v2 adding it to the parent content node."""
        interaction = None
        labels = list(self.find_children_depth_first(ResponseLabel, False))
        if self.maxNumber is None:
            max_choices = len(labels)
        else:
            max_choices = self.maxNumber
        if isinstance(self.parent, ResponseLId):
            if self.parent.rCardinality == core.RCardinality.Single:
                log.append(
                    "Warning: choice-slider replaced with"
                    " choiceInteraction.slider")
                interaction = parent.add_child(
                    qtiv2.interactions.ChoiceInteraction)
                interaction.style_class = ['slider']
                interaction.minChoices = 1
                interaction.maxChoices = 1
            elif self.parent.rCardinality == core.RCardinality.Ordered:
                log.append(
                    "Error: ordered-slider replaced with"
                    " orderInteraction.slider")
                raise core.QTIUnimplementedError("OrderInteraction")
            else:
                log.append(
                    "Error: multiple-slider replaced with"
                    " choiceInteraction.slider")
                interaction = parent.add_child(
                    qtiv2.interactions.ChoiceInteraction)
                interaction.style_class = ['slider']
                if self.minNumber is not None:
                    interaction.minChoices = self.minNumber
                else:
                    interaction.minChoices = max_choices
                interaction.maxChoices = max_choices
            interaction.shuffle = False
            for child in labels:
                child.migrate_simple_choice_to_v2(interaction, log)
        elif isinstance(self.parent, ResponseNum):
            if self.parent.rCardinality == core.RCardinality.Single:
                interaction = parent.add_child(
                    qtiv2.interactions.SliderInteraction)
                interaction.lowerBound = float(self.lowerBound)
                interaction.upperBound = float(self.upperBound)
                if self.step is not None:
                    interaction.step = self.step
                if self.orientation is not None:
                    interaction.orientation = core.MigrateV2Orientation(
                        self.orientation)
                # startValues are handled below after the variable is declared
            else:
                raise core.QTIUnimplementedError(
                    "Multiple/Ordered SliderInteraction")
        else:
            raise core.QTIUnimplementedError(
                "%s x render_slider" % self.parent.__class__.__name__)
        if prompt:
            interaction_prompt = interaction.add_child(
                qtiv2.interactions.Prompt)
            for child in prompt:
                child.migrate_content_to_v2(
                    interaction_prompt, html.InlineMixin, log)
        return [interaction]

    def migrate_interaction_default_to_v2(self, declaration, interaction):
        # Most interactions do not need default values.
        if (isinstance(interaction, qtiv2.interactions.SliderInteraction) and
                self.startVal is not None):
            value = declaration.add_child(
                qtiv2.variables.DefaultValue).add_child(
                qtiv2.variables.ValueElement)
            if declaration.baseType == qtiv2.variables.BaseType.integer:
                value.set_value(xsi.integer_to_str(self.startVal))
            elif declaration.baseType == qtiv2.variables.BaseType.float:
                value.set_value(xsi.float_to_str(self.startVal))
            else:
                # slider bound to something else?
                raise core.QTIError(
                    "Unexpected slider type for default: %s" %
                    qtiv2.variables.BaseType.to_str(
                        declaration.baseType))


class RenderExtension(Render):

    """This element supports proprietary alternatives to the current range of
    'render' elements::

    <!ELEMENT render_extension ANY>"""
    XMLNAME = "render_extension"
    XMLCONTENT = xml.XMLMixedContent


class ResponseLabel(common.ContentMixin, core.QTIElement):

    """The <response_label> is used to define the possible response
    choices that are presented to the user. This information includes
    the material to be shown to the user and the logical label that is
    associated with that response. The label is used in the response
    processing. Flow and non-flow approaches are supported::

    <!ELEMENT response_label (#PCDATA | qticomment | material | material_ref |
    flow_mat)*>
    <!ATTLIST response_label  rshuffle     (Yes | No )  'Yes'
    rarea			(Ellipse | Rectangle | Bounded )  'Ellipse'
    rrange			(Exact | Range )  'Exact'
    labelrefid		CDATA  #IMPLIED
    ident CDATA		#REQUIRED
    match_group		CDATA  #IMPLIED
    match_max		CDATA  #IMPLIED >"""
    XMLNAME = 'response_label'
    XMLATTR_ident = 'ident'
    XMLATTR_rshuffle = ('rShuffle', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_rarea = (
        'rArea', core.Area.from_str_title, core.Area.to_str)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        common.ContentMixin.__init__(self)
        self.ident = ''
        self.rShuffle = True
        self.rArea = None

    def add_child(self, child_class, name=None):
        """Although we inherit from the ContentMixin class we don't
        allow it to capture content-children because this element has
        mixed content - though in practice it really should have either
        data or element content."""
        if issubclass(child_class, common.ContentMixin):
            # add it to the default content model
            child = child_class(self)
            self._children.append(child)
            if name:
                child.set_xmlname(name)
            return child
        else:
            return super(ResponseLabel, self).add_child(child_class, name)

    def is_inline(self):
        """Whether or not a response_label is inline depends on the context...

        render_choice: a choice is a block
        render_hotspot: at most a label on the image so treated as inline
        render_fib: always inline
        """
        render = self.find_parent(RenderThing)
        if isinstance(render, RenderChoice):
            return False
        elif isinstance(render, RenderHotspot):
            return True
        elif isinstance(render, RenderFIB):
            return render.inline_fib_label()
        else:
            return self.inline_children()

    def inline_children(self):
        for child in core.QTIElement.get_children(self):
            if is_text(child):
                continue
            elif issubclass(child.__class__, common.ContentMixin):
                if child.is_inline():
                    continue
                return False
            else:
                # QTIComment most likely
                continue
        return True

    def migrate_content_to_v2(self, parent, child_type, log):
        """Migrates this content to v2 adding it to the parent content node."""
        render = self.find_parent(RenderThing)
        if isinstance(render, RenderFIB):
            render.migrate_fib_label_to_v2(self, parent, child_type, log)

    def migrate_simple_choice_to_v2(self, interaction, log):
        """Migrate this label into a v2 simpleChoice in interaction."""
        choice = interaction.add_child(qtiv2.interactions.SimpleChoice)
        choice.identifier = qtiv2.core.ValidateIdentifier(self.ident)
        if (isinstance(interaction, qtiv2.interactions.ChoiceInteraction) and
                interaction.shuffle):
            choice.fixed = not self.rShuffle
        data = []
        got_elements = False
        for child in core.QTIElement.get_children(self):
            if is_text(child):
                if len(child.strip()):
                    data.append(child)
            elif isinstance(child, common.QTIComment):
                continue
            else:
                got_elements = True
        if data and got_elements:
            log.append(
                'Warning: ignoring PCDATA in <response_label>, "%s"' %
                ' '.join(data))
        elif data:
            for d in data:
                choice.add_data(d)
        else:
            content = []
            for child in core.QTIElement.get_children(self):
                if isinstance(child, common.ContentMixin):
                    content.append(child)
            common.ContentMixin.migrate_content_to_v2(
                self, choice, html.FlowMixin, log, content)

    def migrate_hotspot_choice_to_v2(self, interaction, log, xoffset=0,
                                     yoffset=0):
        """Migrate this label into a v2 hotspotChoice in interaction."""
        if isinstance(interaction, qtiv2.interactions.SelectPointInteraction):
            log.append(
                "Warning: ignoring response_label in"
                " selectPointInteraction (%s)" %
                self.ident)
            return
        choice = interaction.add_child(qtiv2.interactions.HotspotChoice)
        choice.identifier = qtiv2.core.ValidateIdentifier(self.ident)
        # Hard to believe I know, but we sift the content of the
        # response_label into string data (which is parsed for
        # coordinates) and elements which have their text extracted for
        # the hotspot label.
        lang, label_data, value_data = self.parse_value()
        choice.shape, choice.coords = core.MigrateV2AreaCoords(
            self.rArea, value_data, log)
        if xoffset or yoffset:
            qtiv2.core.offset_shape(
                choice.shape, choice.coords, xoffset, yoffset)
        if lang is not None:
            choice.set_lang(lang)
        if label_data:
            choice.hotspotLabel = label_data

    def hotspot_in_image(self, mat_image):
        """Tests this hotspot to see if it overlaps with mat_image.

        The coordinates in the response label are interpreted relative to
        a notional 'stage' on which the presentation takes place.  If the
        image does not have X0,Y0 coordinates then it is ignored and
        we return 0.
        """
        if mat_image.x0 is None or mat_image.y0 is None:
            return False
        if mat_image.width is None or mat_image.height is None:
            return False
        lang, label, value = self.parse_value()
        shape, coords = core.MigrateV2AreaCoords(self.rArea, value, [])
        bounds = qtiv2.core.calculate_shape_bounds(shape, coords)
        if bounds[0] > mat_image.x0 + mat_image.width or bounds[2] < \
                mat_image.x0:
            return False
        if (bounds[1] > mat_image.y0 + mat_image.height or
                bounds[3] < mat_image.y0):
            return False
        return True

    def parse_value(self):
        """Returns lang,label,coords parsed from the value."""
        value_data = []
        label_data = []
        lang = None
        for child in self.get_children():
            if is_text(child):
                value_data.append(child)
            else:
                childLang, text = child.extract_text()
                if lang is None and childLang is not None:
                    lang = childLang
                label_data.append(text)
        value_data = ' '.join(value_data)
        label_data = ' '.join(label_data)
        return lang, label_data, value_data


class FlowLabel(
        common.FlowMixin,
        common.ContentMixin,
        common.QTICommentContainer):

    """The <flow_label> element is the blocking/paragraph equivalent to the
    <response_label> element::

    <!ELEMENT flow_label	(qticomment? , (flow_label | response_label)+)>
    <!ATTLIST flow_label	class CDATA  'Block' >"""
    XMLNAME = 'flow_label'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        common.ContentMixin.__init__(self)

    def content_child(self, child_class):
        return child_class is FlowLabel or issubclass(
            child_class, ResponseLabel)

    def get_children(self):
        return itertools.chain(
            common.QTICommentContainer.get_children(self),
            self.contentChildren)

    def get_label_content(self):
        children = []
        for child in self.contentChildren:
            if isinstance(child, FlowLabel):
                children = children + child.get_label_content()
            else:
                children.append(child)
        return children


class ResponseNA(core.QTIElement):

    """This element supports proprietary alternatives for defining the response
    to be created when a participant makes no response to an Item::

    <!ELEMENT response_na ANY>"""
    XMLNAME = 'response_na'
    XMLCONTENT = xml.XMLMixedContent


class ResProcessing(common.QTICommentContainer):

    """This is the element within which all of the instructions for the
    response processing are contained. This includes the scoring
    variables to contain the associated scores and the set of response
    condition tests that are to be applied to the received user
    response::

    <!ELEMENT resprocessing (qticomment? , outcomes ,
    (respcondition | itemproc_extension)+)>
    <!ATTLIST resprocessing  scoremodel CDATA  #IMPLIED >"""
    XMLNAME = 'resprocessing'
    XMLATTR_scoremodel = 'scoreModel'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.scoreModel = None
        self.Outcomes = Outcomes(self)
        self.ConditionMixin = []

    def get_children(self):
        for child in common.QTICommentContainer.get_children(self):
            yield child
        yield self.Outcomes
        for child in self.ConditionMixin:
            yield child

    def migrate_to_v2(self, v2_item, log):
        """Migrates v1 resprocessing to v2 ResponseProcessing."""
        rp = v2_item.add_child(qtiv2.processing.ResponseProcessing)
        for outcomeFixup in sorted(self._interactionFixup.keys()):
            set_value = rp.add_child(qtiv2.processing.SetOutcomeValue)
            set_value.identifier = outcomeFixup
            multi = set_value.add_child(qtiv2.expressions.Multiple)
            for rID in self._interactionFixup[outcomeFixup]:
                var = multi.add_child(qtiv2.expressions.Variable)
                var.identifier = rID
        self.Outcomes.migrate_to_v2(v2_item, log)
        cmode = True
        rule_container = rp
        for condition in self.ConditionMixin:
            cmode, rule_container = condition.migrate_rule_to_v2(
                cmode, rule_container, log)


class Outcomes(common.QTICommentContainer):

    """The <outcomes> element contains all of the variable declarations
    that are to be made available to the scoring algorithm. Each
    variable is declared using the <decvar> element apart from the
    default variable called 'SCORE' that is an integer and has a default
    value of zero (0)::

    <!ELEMENT outcomes (qticomment? , (decvar , interpretvar*)+)>

    The implementation of this element takes a liberty with the content model
    because, despite the formulation above, the link between variables and
    their interpretation is not related to the order of the elements within
    the outcomes element.  (An interpretation without a variable reference
    defaults to an interpretation of the default 'SCORE' outcome.)

    When we output this element we do the decvars first, followed by
    the interpretVars."""
    XMLNAME = 'outcomes'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.DecVar = []
        self.InterpretVar = []

    def get_children(self):
        return itertools.chain(
            common.QTICommentContainer.get_children(self),
            self.DecVar,
            self.InterpretVar)

    def migrate_to_v2(self, v2_item, log):
        for d in self.DecVar:
            d.migrate_to_v2(v2_item, log)
        for i in self.InterpretVar:
            i.migrate_to_v2(v2_item, log)


class ConditionMixin:

    """Mixin class to identify condition elements::

    (respcondition | itemproc_extension)"""
    pass


class RespCondition(common.QTICommentContainer, ConditionMixin):

    """This element contains the actual test to be applied to the user
    responses to determine their correctness or otherwise. Each
    <respcondition> contains an actual test, the assignment of a value
    to the associate scoring variables and the identification of the
    feedback to be associated with the test::

    <!ELEMENT respcondition (qticomment? , conditionvar , setvar* ,
    displayfeedback* , respcond_extension?)>
    <!ATTLIST respcondition
            continue  (Yes | No )  'No'
            title CDATA  #IMPLIED >"""
    XMLNAME = 'respcondition'
    XMLATTR_continue = ('continueFlag', core.ParseYesNo, core.FormatYesNo)
    XMLATTR_title = 'title'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.continueFlag = False
        self.title = None
        self.ConditionVar = common.ConditionVar(self)
        self.SetVar = []
        self.DisplayFeedback = []
        self.RespCondExtension = None

    def get_children(self):
        for child in common.QTICommentContainer.get_children(self):
            yield child
        yield self.ConditionVar
        for child in itertools.chain(
                self.SetVar,
                self.DisplayFeedback):
            yield child
        if self.RespCondExtension:
            yield self.RespCondExtension

    def migrate_rule_to_v2(self, cmode, rule_container, log):
        """Converts a response condition into v2 response processing rules.

        This method contains some tricky logic to help implement the confusing
        'continue' attribute of response conditions.  The continue attribute
        is interpreted in the following way:

        True: regardless of whether or not the condition matches, carry on to
        evaluate the next expression.

        False: only evaluate the next expression if the condition fails.

        The incoming cmode tells us if the previous condition set continue mode
        (the default is False on the attribute but the algorithm starts with
        continue mode True as the first rule is always evaluated).

        The way the rules are implemented is best illustrated by example, where
        X(True) represents condition X with continue='Yes' etc::

                R1(True),R2(True|False) becomes...

                if R1.test:
                        R1.rules
                if R2.test:
                        R2.rules

                R1(False),R2(True) becomes...

                if R1.test:
                        R1.rules
                else:
                        if R2.test:
                                R2.rules

                R1(False),R2(False) becomes...

                if R1.test:
                        R1.rules
                elif R2.test:
                        R2.rules"""
        if self.continueFlag:
            if not cmode:
                rule_container = rule_container.add_child(
                    qtiv2.processing.ResponseElse)
            rc = rule_container.add_child(qtiv2.processing.ResponseCondition)
            rc_if = rc.add_child(qtiv2.processing.ResponseIf)
        else:
            if cmode:
                rc = rule_container.add_child(
                    qtiv2.processing.ResponseCondition)
                rule_container = rc
                rc_if = rc.add_child(qtiv2.processing.ResponseIf)
            else:
                rc_if = rule_container.add_child(
                    qtiv2.processing.ResponseElseIf)
        self.ConditionVar.migrate_expression_to_v2(rc_if, log)
        for rule in self.SetVar:
            rule.migrate_rule_to_v2(rc_if, log)
        for rule in self.DisplayFeedback:
            rule.migrate_rule_to_v2(rc_if, log)
        return self.continueFlag, rule_container


class RespCondExtension(core.QTIElement):

    """This element supports proprietary alternatives to the <respcondition>
    element::

    <!ELEMENT respcond_extension ANY>"""
    XMLNAME = "respcond_extension"
    XMLCONTENT = xml.XMLMixedContent


class ItemProcExtension(common.ContentMixin, core.QTIElement, ConditionMixin):

    """This element supports proprietary alternatives to the standard Item
    response processing algorithms. element::

    <!ELEMENT itemproc_extension ANY>"""
    XMLNAME = "itemproc_extension"
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        common.ContentMixin.__init__(self)

    def migrate_rule_to_v2(self, cmode, rule_container, log):
        """Converts an itemProcExtension into v2 response processing rules.

        We only support one type of extension at the moment, the
        humanrater element used as an illustration in the specification
        examples."""
        for child in self.get_children():
            if is_text(child):
                # ignore data
                continue
            elif child.xmlname == 'humanraterdata':
                # humanraterdata extension, migrate content with appropriate
                # view
                v2_item = rule_container.find_parent(
                    qtiv2.items.AssessmentItem)
                rubric = v2_item.get_or_add_child(
                    qtiv2.content.ItemBody).add_child(
                        qtiv2.content.RubricBlock)
                rubric.view = qtiv2.core.View.scorer
                material = list(
                    child.find_children_depth_first(common.Material, False))
                self.migrate_content_to_v2(rubric, html.BlockMixin, log,
                                           material)
        return cmode, rule_container


class ItemFeedback(common.ContentMixin, core.QTIElement):

    """The container for the feedback that is to be presented as a
    result of the user's responses. The feedback can include hints and
    solutions and both of these can be revealed in a variety of
    different ways::

    <!ELEMENT itemfeedback ((flow_mat | material) | solution | hint)+>
    <!ATTLIST itemfeedback
        view	(All | Administrator | AdminAuthority | Assessor |
                 Author | Candidate | InvigilatorProctor |
                 Psychometrician | Scorer | Tutor ) 'All'
        ident CDATA  #REQUIRED
        title CDATA  #IMPLIED >"""
    XMLNAME = 'itemfeedback'
    XMLATTR_view = ('view', core.View.from_str_lower, core.View.to_str)
    XMLATTR_title = 'title'
    XMLATTR_ident = 'ident'

    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.view = core.View.DEFAULT
        common.ContentMixin.__init__(self)
        self.title = None
        self.ident = None

    def content_child(self, child_class):
        return child_class in (common.FlowMat, common.Material, Solution, Hint)

    def get_children(self):
        return itertools.chain(
            core.QTIElement.get_children(self),
            self.contentChildren)

    def migrate_to_v2(self, v2_item, log):
        feedback = v2_item.add_child(qtiv2.items.QTIModalFeedback)
        if self.view not in (core.View.All, core.View.Candidate):
            log.append("Warning: discarding view on feedback (%s)" %
                       core.View.to_str(self.view))
        identifier = qtiv2.core.ValidateIdentifier(self.ident, 'FEEDBACK_')
        feedback.outcomeIdentifier = 'FEEDBACK'
        feedback.showHide = qtiv2.core.ShowHide.show
        feedback.identifier = identifier
        feedback.title = self.title
        common.ContentMixin.migrate_content_to_v2(
            self, feedback, html.FlowMixin, log)


class Solution(common.ContentMixin, common.QTICommentContainer):

    """The <solution> element contains the solution(s) that are to be revealed
    to the participant. When these solutions are revealed is outside the scope
    of the specification::

    <!ELEMENT solution (qticomment? , solutionmaterial+)>
    <!ATTLIST solution  feedbackstyle  (Complete | Incremental | Multilevel |
                                        Proprietary )  'Complete' >"""
    XMLNAME = 'solution'
    XMLATTR_feedbackstyle = (
        'feedbackStyle',
        core.FeedbackStyle.from_str_title,
        core.FeedbackStyle.to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        common.ContentMixin.__init__(self)
        self.feedbackStyle = core.FeedbackStyle.DEFAULT

    def content_child(self, child_class):
        return child_class is SolutionMaterial

    def get_children(self):
        return itertools.chain(
            common.QTICommentContainer.get_children(self),
            common.ContentMixin.get_content_children(self))


class FeedbackMaterial(common.ContentMixin, core.QTIElement):

    """Abstract class for solutionmaterial and hintmaterial::

    <!ELEMENT * (material+ | flow_mat+)>"""
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        common.ContentMixin.__init__(self)

    def content_child(self, child_class):
        return child_class in (common.Material, common.FlowMat)

    def get_children(self):
        return common.ContentMixin.get_content_children(self)


class SolutionMaterial(FeedbackMaterial):

    """This is the container for the materials to be presented to the
    participant as the recommended solution. The solution can be revealed in a
    variety of ways but this information is not contained within the material
    being displayed::

    <!ELEMENT solutionmaterial (material+ | flow_mat+)>"""
    XMLNAME = 'solutionmaterial'


class Hint(common.ContentMixin, common.QTICommentContainer):

    """The <hint> element contains the hint(s) that are to be revealed to the
    participant. When these hints are revealed is outside the scope of the
    specification::

    <!ELEMENT hint (qticomment? , hintmaterial+)>
    <!ATTLIST hint  feedbackstyle  (Complete | Incremental | Multilevel |
                                    Proprietary )  'Complete' >"""
    XMLNAME = 'hint'
    XMLATTR_feedbackstyle = (
        'feedbackStyle',
        core.FeedbackStyle.from_str_title,
        core.FeedbackStyle.to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        common.ContentMixin.__init__(self)
        self.feedbackStyle = core.FeedbackStyle.DEFAULT

    def content_child(self, child_class):
        return child_class is HintMaterial

    def get_children(self):
        return itertools.chain(
            common.QTICommentContainer.get_children(self),
            common.ContentMixin.get_content_children(self))


class HintMaterial(FeedbackMaterial):

    """This is the container for the materials to be presented to the
    participant as a hint. The hint can be revealed in a variety of ways but
    this information is not contained within the material being displayed::

    <!ELEMENT hintmaterial (material+ | flow_mat+)>"""
    XMLNAME = 'hintmaterial'
