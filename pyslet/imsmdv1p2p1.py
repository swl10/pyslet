#! /usr/bin/env python
"""This module implements the IMS LRM 1.2.1 specification defined by IMS GLC
"""

import itertools

from .pep8 import old_method
from .xml import namespace as xmlns
from .xml import structures as xml

try:
    import vobject
except ImportError:
    vobject = None


IMSLRM_NAMESPACE = "http://www.imsglobal.org/xsd/imsmd_v1p2"
IMSLRM_SCHEMALOCATION = "http://www.imsglobal.org/xsd/imsmd_v1p2p4.xsd"

IMSLRM_NAMESPACE_ALIASES = {
    # "http://www.imsproject.org/metadata":"1.1",
    # "http://www.imsproject.org/metadata/":"1.1",
    "http://www.imsproject.org/xsd/imsmd_rootv1p2": IMSLRM_NAMESPACE,
    "http://www.imsglobal.org/xsd/imsmd_rootv1p2p1": IMSLRM_NAMESPACE}

LOM_SOURCE = "LOMv1.0"
LOM_UNKNOWNSOURCE = "None"


class LRMException(Exception):
    pass


class LRMElement(xmlns.XMLNSElement):

    """Basic element to represent all CP elements"""
    pass


class LangString(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'langstring')

    def __init__(self, parent, value=None):
        LRMElement.__init__(self, parent)
        if value is not None:
            self.set_value(value)


class LangStringList(LRMElement):
    LangStringClass = LangString

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LangString = []

    def get_children(self):
        return iter(self.LangString)

    @old_method('GetLangString')
    def get_lang_string(self, lang=None):
        if lang is None:
            for s in self.LangString:
                if s.get_lang() is None:
                    return s
            return None
        else:
            for s in self.LangString:
                if s.get_lang() == lang:
                    return s
            lang = lang.split('-')[0]
            for s in self.LangString:
                slang = s.get_lang().split('-')[0]
                if slang == lang:
                    return s
        return None

    @old_method('AddString')
    def add_string(self, lang, value):
        s = self.get_lang_string(lang)
        if s is None:
            s = self.add_child(self.LangStringClass)
            s.set_value(value)
            if lang:
                s.set_lang(lang)
        else:
            s.add_data('; ' + value)
        return s


class LRMSource(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'source')

    LangStringClass = LangString

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LangString = self.LangStringClass(self)

    def get_children(self):
        yield self.LangString


class LRMValue(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'value')

    LangStringClass = LangString

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LangString = self.LangStringClass(self)

    def get_children(self):
        yield self.LangString


class LRMSourceValue(LRMElement):
    LRMSourceClass = LRMSource
    LRMValueClass = LRMValue

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LRMSource = self.LRMSourceClass(self)
        self.LRMValue = self.LRMValueClass(self)

    def get_children(self):
        yield self.LRMSource
        yield self.LRMValue


class LOM(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'lom')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMGeneral = None
        self.LOMLifecycle = None
        self.LOMMetaMetadata = None
        self.LOMTechnical = None
        self.LOMEducational = None
        self.rights = None
        self.LOMRelation = []
        self.LOMAnnotation = []
        self.LOMClassification = []

    def get_children(self):
        if self.LOMGeneral:
            yield self.LOMGeneral
        if self.LOMLifecycle:
            yield self.LOMLifecycle
        if self.LOMMetaMetadata:
            yield self.LOMMetaMetadata
        if self.LOMTechnical:
            yield self.LOMTechnical
        if self.LOMEducational:
            yield self.LOMEducational
        if self.rights:
            yield self.rights
        for child in itertools.chain(
                self.LOMRelation,
                self.LOMAnnotation,
                self.LOMClassification,
                LRMElement.get_children(self)):
            yield child


class Description(LangStringList):
    XMLNAME = (IMSLRM_NAMESPACE, 'description')
    XMLCONTENT = xml.ElementContent


class LOMGeneral(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'general')
    XMLCONTENT = xml.ElementContent

    DescriptionClass = Description

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMIdentifier = None
        self.LOMTitle = None
        self.LOMCatalogEntry = []
        self.LOMLanguage = []
        self.Description = []
        self.LOMKeyword = []
        self.LOMCoverage = []
        self.LOMStructure = None
        self.LOMAggregationLevel = None

    def get_children(self):
        if self.LOMIdentifier:
            yield self.LOMIdentifier
        if self.LOMTitle:
            yield self.LOMTitle
        for child in itertools.chain(
                self.LOMCatalogEntry,
                self.LOMLanguage,
                self.Description,
                self.LOMKeyword,
                self.LOMCoverage):
            yield child
        if self.LOMStructure:
            yield self.LOMStructure
        if self.LOMAggregationLevel:
            yield self.LOMAggregationLevel
        for child in LRMElement.get_children(self):
            yield child


class LOMIdentifier(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'identifier')


class LOMTitle(LangStringList):
    XMLNAME = (IMSLRM_NAMESPACE, 'title')


class LOMCatalogEntry(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'catalogentry')


class LOMLanguage(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'language')


class LOMKeyword(LangStringList):
    XMLNAME = (IMSLRM_NAMESPACE, 'keyword')


class LOMCoverage(LangStringList):
    XMLNAME = (IMSLRM_NAMESPACE, 'coverage')


class LOMStructure(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'structure')


class LOMAggregationLevel(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'aggregationlevel')


class LOMLifecycle(LRMElement):

    """
    <xsd:sequence>
            <xsd:element ref = "version" minOccurs = "0"/>
            <xsd:element ref = "status" minOccurs = "0"/>
            <xsd:element ref = "contribute" minOccurs = "0"
            maxOccurs = "unbounded"/>
            <xsd:group ref = "grp.any"/>
    </xsd:sequence>
    """
    XMLNAME = (IMSLRM_NAMESPACE, 'lifecycle')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMVersion = None
        self.LOMStatus = None
        self.LOMContribute = []

    def get_children(self):
        if self.LOMVersion:
            yield self.LOMVersion
        if self.LOMStatus:
            yield self.LOMStatus
        for child in itertools.chain(
                self.LOMContribute,
                LRMElement.get_children(self)):
            yield child


class LOMVersion(LangStringList):
    XMLNAME = (IMSLRM_NAMESPACE, 'version')


class LOMStatus(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'status')


class LOMContribute(LRMElement):

    """
    <xsd:sequence>
            <xsd:element ref = "role"/>
            <xsd:element ref = "centity" minOccurs = "0"
            maxOccurs = "unbounded"/>
            <xsd:element ref = "date" minOccurs = "0"/>
            <xsd:group ref = "grp.any"/>
    </xsd:sequence>
    """
    XMLNAME = (IMSLRM_NAMESPACE, 'contribute')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMRole = LOMRole(self)
        self.LOMCEntity = []
        self.LOMDate = None

    def get_children(self):
        yield self.LOMRole
        for child in self.LOMCEntity:
            yield child
        if self.LOMDate:
            yield self.LOMDate
        for child in LRMElement.get_children(self):
            yield child


class LOMRole(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'role')


class LOMCEntity(LRMElement):

    """
    """
    XMLNAME = (IMSLRM_NAMESPACE, 'centity')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMVCard = LOMVCard(self)

    def get_children(self):
        yield self.LOMVCard
        for child in LRMElement.get_children(self):
            yield child


class LOMVCard(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'vcard')

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.vcard = None

    def get_value(self):
        return self.vcard

    def set_value(self, vcard):
        self.vcard = vcard
        LRMElement.set_value(self, vcard.serialize())

    def can_pretty_print(self):
        """Overridden to prevent pretty-printing of the element contents."""
        return False

    def get_canonical_children(self):
        """Overridden to prevent collapsing of whitespace"""
        return self.get_children()

    def content_changed(self):
        # called when all children have been parsed
        if vobject is not None:
            src = LRMElement.get_value(self)
            if src is not None and src.strip():
                self.vcard = vobject.readOne(src)
            else:
                self.vcard = None


class LOMMetaMetadata(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'metametadata')


class LOMTechnical(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'technical')


class LOMEducational(LRMElement):

    """
<xsd:complexType name="educationalType" mixed="true">
  <xsd:sequence>
     <xsd:element ref="interactivitytype" minOccurs="0"/>
     <xsd:element ref="learningresourcetype" minOccurs="0"
     maxOccurs="unbounded"/>
     <xsd:element ref="interactivitylevel" minOccurs="0"/>
     <xsd:element ref="semanticdensity" minOccurs="0"/>
     <xsd:element ref="intendedenduserrole" minOccurs="0"
     maxOccurs="unbounded"/>
     <xsd:element ref="context" minOccurs="0" maxOccurs="unbounded"/>
     <xsd:element ref="typicalagerange" minOccurs="0" maxOccurs="unbounded"/>
     <xsd:element ref="difficulty" minOccurs="0"/>
     <xsd:element ref="typicallearningtime" minOccurs="0"/>
     <xsd:element ref="description" minOccurs="0"/>
     <xsd:element ref="language" minOccurs="0" maxOccurs="unbounded"/>
     <xsd:group ref="grp.any"/>
  </xsd:sequence>
</xsd:complexType>
    """
    XMLNAME = (IMSLRM_NAMESPACE, 'educational')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMInteractivityType = None
        self.LOMLearningResourceType = []
        self.LOMInteractivityLevel = None
        self.LOMSemanticDensity = None
        self.LOMIntendedEndUserRole = []
        self.LOMContext = []
        self.LOMTypicalAgeRange = []
        self.LOMDifficulty = None
        self.LOMTypicalLearningTime = None
        self.Description = None
        self.LOMLanguage = []

    def get_children(self):
        if self.LOMInteractivityType:
            yield self.LOMInteractivityType
        for child in self.LOMLearningResourceType:
            yield child
        if self.LOMInteractivityLevel:
            yield self.LOMInteractivityLevel
        if self.LOMSemanticDensity:
            yield self.LOMSemanticDensity
        for child in itertools.chain(
                self.LOMIntendedEndUserRole,
                self.LOMContext,
                self.LOMTypicalAgeRange):
            yield child
        if self.LOMDifficulty:
            yield self.LOMDifficulty
        if self.LOMTypicalLearningTime:
            yield self.LOMTypicalLearningTime
        if self.Description:
            yield self.Description
        for child in itertools.chain(
                self.LOMLanguage,
                LRMElement.get_children(self)):
            yield child


class LOMInteractivityType(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'interactivitytype')


class LOMLearningResourceType(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'learningresourcetype')


class LOMInteractivityLevel(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'interactivitylevel')


class LOMSemanticDensity(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'semanticdensity')


class LOMIntendedEndUserRole(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'intendedenduserrole')


class LOMContext(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'context')


class LOMTypicalAgeRange(LangStringList):
    XMLNAME = (IMSLRM_NAMESPACE, 'typicalagerange')


class LOMDifficulty(LRMSourceValue):
    XMLNAME = (IMSLRM_NAMESPACE, 'difficulty')


class LOMTypicalLearningTime(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'typicallearningimte')


class LOMRelation(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'relation')


class LOMAnnotation(LRMElement):

    """
    <xsd:complexType name="annotationType" mixed="true">
  <xsd:sequence>
     <xsd:element ref="person" minOccurs="0"/>
     <xsd:element ref="date" minOccurs="0"/>
     <xsd:element ref="description" minOccurs="0"/>
     <xsd:group ref="grp.any"/>
  </xsd:sequence>
    </xsd:complexType>
    """
    XMLNAME = (IMSLRM_NAMESPACE, 'annotation')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        LRMElement.__init__(self, parent)
        self.LOMPerson = None
        self.LOMDate = None
        self.Description = None

    def get_children(self):
        if self.LOMPerson:
            yield self.LOMPerson
        if self.LOMDate:
            yield self.LOMDate
        if self.Description:
            yield self.Description
        for child in LRMElement.get_children(self):
            yield child


class LOMClassification(LRMElement):
    XMLNAME = (IMSLRM_NAMESPACE, 'classification')


classMap = {
    (IMSLRM_NAMESPACE, None): LRMElement
}

xmlns.map_class_elements(classMap, globals())


def get_element_class(name):
    ns, xmlname = name
    if ns in IMSLRM_NAMESPACE_ALIASES:
        ns = IMSLRM_NAMESPACE_ALIASES[ns]
    return classMap.get((ns, xmlname), classMap.get((ns, None),
                                                    xmlns.XMLNSElement))
