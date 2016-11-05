#! /usr/bin/env python
"""This module implements the QML specification defined by Questionmark.

References:
"""

import itertools

from .py2 import to_text
from .xml import structures as xml
from .xml import xsdatatypes as xsi


def questionid_from_str(src):
    result = []
    for c in src.strip():
        if c in "0123456789":
            result.append(c)
        else:
            raise ValueError("Can't parse QuestionID from %s" % src)
    return ''.join(result)


def questionid_to_str(qid):
    return questionid_from_str(qid)


def name_from_str(src):
    if len(src) > 50:
        raise ValueError("NameString exceeds 50 characters: %s" % src)
    return src


def name_to_str(name):
    return name_from_str(name)


def alternative_from_str(src):
    if len(src) > 100:
        raise ValueError("AlternativeString exceeds 100 characters: %s" % src)
    return src


def alternative_to_str(alt):
    return alternative_from_str(alt)


def message_from_str(src):
    """MessageString is a simple length restricted string:

    <xs:simpleType name="MessageString">
            <xs:restriction base="xs:string">
                    <xs:maxLength value="1024"/>
            </xs:restriction>
    </xs:simpleType>"""
    if len(src) > 1024:
        raise ValueError("MessageString exceeds 1024 characters: %s" % src)
    return src


def message_to_str(msg):
    return message_from_str(msg)


def ceiling_from_str(src):
    """A simply restriction on integer:

    <xs:simpleType name="Ceiling">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="32767"/>
                    <xs:minInclusive value="-1"/>
            </xs:restriction>
    </xs:simpleType>
    """
    value = int(src)
    if value < -1 or value > 32767:
        raise ValueError("Value exceeds bounds for CEILING: %i" % value)
    return value


def ceiling_to_str(value):
    if value < -1:
        return to_text(-1)
    elif value > 32767:
        return to_text(32767)
    else:
        return to_text(value)


def floor_from_str(src):
    """A more complex restriction on integer.  A comment in the XSD assures
    that the value 1 is valid in the schema only for legacy reasons.  In
    other words, we may encounter content with a value of 1 but we should
    not generate this value in our output.

    <xs:simpleType name="Floor">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="1"/>
                    <xs:minInclusive value="-100"/>
            </xs:restriction>
    </xs:simpleType>
    """
    value = int(src)
    if value < -100 or value > 1:
        raise ValueError("Value out of bounds defined for FLOOR: %i" % value)
    return value


def floor_to_str(value):
    if value > 0:
        return to_text(0)
    elif value < -100:
        return to_text(-100)
    else:
        return to_text(value)


def length_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="Length">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="32767"/>
                    <xs:minInclusive value="-32768"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < -32768 or value > 32767:
        raise ValueError("Value exceeds bounds for Length: %i" % value)
    return value


def length_to_str(value):
    if value < -32768:
        return to_text(-32768)
    elif value > 32767:
        return to_text(32767)
    else:
        return to_text(value)


def pve_length_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="PositiveLength">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="32767"/>
                    <xs:minInclusive value="0"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < 0 or value > 32767:
        raise ValueError("Value exceeds bounds for PositiveLength: %i" % value)
    return value


def pve_length_to_str(value):
    if value < 0:
        return to_text(0)
    elif value > 32767:
        return to_text(32767)
    else:
        return to_text(value)


def comment_height_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="CommentHeight">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="40"/>
                    <xs:minInclusive value="1"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < 1 or value > 40:
        raise ValueError("Value exceeds bounds for CommentHeight: %i" % value)
    return value


def comment_height_to_str(value):
    if value < 1:
        return to_text(1)
    elif value > 40:
        return to_text(40)
    else:
        return to_text(value)


def comment_width_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="CommentWidth">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="100"/>
                    <xs:minInclusive value="5"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < 5 or value > 100:
        raise ValueError("Value exceeds bounds for CommentWidth: %i" % value)
    return value


def comment_width_to_str(value):
    if value < 5:
        return to_text(5)
    elif value > 100:
        return to_text(100)
    else:
        return to_text(value)


def max_select_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="MaxSelect">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="40"/>
                    <xs:minInclusive value="0"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < 0 or value > 40:
        raise ValueError("Value exceeds bounds for MaxSelect: %i" % value)
    return value


def max_select_to_str(value):
    if value < 0:
        return to_text(0)
    elif value > 40:
        return to_text(40)
    else:
        return to_text(value)


def max_response_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="MaxResponse">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="32767"/>
                    <xs:minInclusive value="1"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < 1 or value > 32767:
        raise ValueError("Value exceeds bounds for MaxResponse: %i" % value)
    return value


def max_response_to_str(value):
    if value < 1:
        return to_text(1)
    elif value > 32767:
        return to_text(32767)
    else:
        return to_text(value)


def truefalse_from_str(src):
    """One of the strings TRUE or FALSE:

    <xs:simpleType name="TrueFalseEnum">
            <xs:restriction base="xs:string">
                    <xs:enumeration value="FALSE"/>
                    <xs:enumeration value="TRUE"/>
            </xs:restriction>
    </xs:simpleType>
    """
    match = src.strip().upper()
    if match == "TRUE":
        return True
    elif match == "FALSE":
        return False
    else:
        raise ValueError("Bad value for TrueFalseEnum: %s" % src)


def truefalse_to_str(value):
    if value:
        return "TRUE"
    elif value is not None:
        return "FALSE"
    else:
        return None


class QMLAlignEnum(xsi.Enumeration):
    decode = {
        'Left': 1,
        'Right': 2,
        'Top': 3,
        'Bottom': 4,
        'Middle': 5
    }


def align_from_str(value):
    """Decodes a shape value from a string.

    <xs:simpleType name="AlignEnum">
            <xs:restriction base="xs:string">
                    <xs:enumeration value="Left"/>
                    <xs:enumeration value="Right"/>
                    <xs:enumeration value="Top"/>
                    <xs:enumeration value="Bottom"/>
                    <xs:enumeration value="Middle"/>
            </xs:restriction>
    </xs:simpleType>
    """
    try:
        return QMLAlignEnum.decode[value]
    except KeyError:
        match = value.strip().lower()
        if match:
            match = match[0].upper() + match[1:]
        try:
            return QMLAlignEnum.decode[value]
        except KeyError:
            raise ValueError("Can't decode AlignEnum from %s" % value)


def align_to_str(value):
    return QMLAlignEnum.encode.get(value, None)


class QMLShuffleEnum(xsi.Enumeration):
    decode = {
        'N': 1,
        'NO': 2,
        'Y': 3,
        'YES': 4,
        'P': 5,
        'PART': 6,
        'T': 7,
        'EXCEPT_LAST_TWO': 8
    }


def shuffle_from_str(value):
    """Decodes a shape value from a string, we canonicalize to upper case.

    <xs:simpleType name="ShuffleEnum">
            <xs:restriction base="xs:string">
                    <xs:enumeration value="N"/>
                    <xs:enumeration value="NO"/>
                    <xs:enumeration value="Y"/>
                    <xs:enumeration value="YES"/>
                    <xs:enumeration value="P"/>
                    <xs:enumeration value="PART"/>
                    <xs:enumeration value="T"/>
                    <xs:enumeration value="EXCEPT_LAST_TWO"/>
                    <xs:enumeration value="n"/>
                    <xs:enumeration value="no"/>
                    <xs:enumeration value="y"/>
                    <xs:enumeration value="yes"/>
                    <xs:enumeration value="p"/>
                    <xs:enumeration value="part"/>
                    <xs:enumeration value="t"/>
                    <xs:enumeration value="except_last_two"/>
            </xs:restriction>
    </xs:simpleType>
    """
    try:
        return QMLShuffleEnum.decode[value.upper()]
    except KeyError:
        raise ValueError("Can't decode ShuffleEnum from %s" % value)


def shuffle_to_str(value):
    return QMLShuffleEnum.encode.get(value, None)


def yesno_from_str(src):
    """One of the strings Y, YES, N or NO:

    <xs:simpleType name="YesNoEnum">
            <xs:restriction base="xs:string">
                    <xs:enumeration value="N"/>
                    <xs:enumeration value="NO"/>
                    <xs:enumeration value="Y"/>
                    <xs:enumeration value="YES"/>
            </xs:restriction>
    </xs:simpleType>
    """
    match = src.strip().upper()
    if match == "YES" or match == "Y":
        return True
    elif match == "NO" or match == "N":
        return False
    else:
        raise ValueError("Bad value for YesNoEnum: %s" % src)


def yesno_to_str(value):
    if value:
        return "YES"
    elif value is not None:
        return "NO"
    else:
        return None


class QMLDirectionEnum(xsi.Enumeration):
    decode = {
        'VERT': 1,
        'HORZ': 2,
        'FLASH': 3
    }


def direction_from_str(value):
    """Decodes a shape value from a string.

    <xs:simpleType name="DirectionEnum">
            <xs:restriction base="xs:string">
                    <xs:enumeration value="VERT"/>
                    <xs:enumeration value="HORZ"/>
                    <xs:enumeration value="FLASH"/>
            </xs:restriction>
    </xs:simpleType>
    """
    try:
        return QMLDirectionEnum.decode[value.upper()]
    except KeyError:
        raise ValueError("Can't decode DirectionEnum from %s" % value)


def direction_to_str(value):
    return QMLDirectionEnum.encode.get(value, None)


def margin_from_str(src):
    """A simple restriction of integer:

    <xs:simpleType name="Margin">
            <xs:restriction base="xs:integer">
                    <xs:maxInclusive value="50"/>
                    <xs:minInclusive value="0"/>
            </xs:restriction>
    </xs:simpleType>"""
    value = int(src)
    if value < 0 or value > 50:
        raise ValueError("Value exceeds bounds for Margin: %i" % value)
    return value


def margin_to_str(value):
    if value < 0:
        return to_text(0)
    elif value > 50:
        return to_text(50)
    else:
        return to_text(value)


class QMLElement(xml.Element):

    """Basic element to represent all QML-defined elements"""


class QML(QMLElement):

    """QML root element.

    Not defined in the document but used as a wrapper element for QML
    documents, presumably to enable them to contain multiple QUESTION
    instances, as per this quote from the specification...

    QML describes individual questions only. Each question defined in QML is
    independent to any other. [snip]...
    Although more than one question may be defined in the same QML file, there
    is no link or interdependence between different questions within QML"""
    XMLNAME = 'QML'


class QMLQuestion(QMLElement):

    """QML QUESSTION element which holds all question data.
            <xs:complexType>
                    <xs:sequence minOccurs="0" maxOccurs="unbounded">
                            <xs:element name="TAG" type="Tag" minOccurs="0"
                            maxOccurs="unbounded"/>
                            <xs:element name="COMMENT" type="Comment"
                            minOccurs="0" maxOccurs="unbounded"/>
                            <xs:element name="CONTENT" type="Content"
                            minOccurs="0" maxOccurs="unbounded"/>
                            <xs:element name="ANSWER" type="Answer"
                            minOccurs="0"/>
                            <xs:element name="OUTCOME" type="Outcome"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xs:sequence>
                    <xs:attribute name="ID" type="QuestionID" use="optional"/>
                    <xs:attribute name="TOPIC" type="xs:string"/>
                    <xs:attribute name="DESCRIPTION" type="DescriptionString"
                    use="optional" default="Question Description"/>
                    <xs:attribute name="TYPE" type="NameString"/>
                    <xs:attribute name="STATUS" type="NameString"/>
                    <xs:attribute name="CEILING" type="Ceiling"/>
                    <xs:attribute name="FLOOR" type="Floor"/>
                    <xs:attribute name="VOICE_SERVER" type="xs:string"/>
                    <xs:attribute name="VOICE_RID" type="xs:string"/>
            </xs:complexType>
    """
    XMLNAME = 'QUESTION'
    XMLATTR_ID = ('qid', questionid_from_str, questionid_to_str)
    XMLATTR_TOPIC = 'topic'
    XMLATTR_DESCRIPTION = 'description'
    XMLATTR_TYPE = ('type', name_from_str, name_to_str)
    XMLATTR_STATUS = ('status', name_from_str, name_to_str)
    XMLATTR_CEILING = ('ceiling', ceiling_from_str, ceiling_to_str)
    XMLATTR_FLOOR = ('floor', floor_from_str, floor_to_str)
    XMLATTR_VOICE_SERVER = 'voiceServer'
    XMLATTR_VOICE_RID = 'voiceRId'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        QMLElement.__init__(self, parent)
        self.qid = None
        self.topic = None
        self.description = 'Question Description'
        self.type = None
        self.status = None
        self.ceiling = None
        self.floor = None
        self.voiceServer = None
        self.voiceRId = None
        self.QMLTag = []
        self.QMLComment = []
        self.QMLContent = []
        self.QMLAnswer = None
        self.QMLOutcome = []

    def get_children(self):
        for child in itertools.chain(
                self.QMLTag,
                self.QMLComment,
                self.QMLContent):
            yield child
        if self.QMLAnswer:
            yield self.QMLAnswer
        for child in self.QMLOutcome:
            yield child


class QMLTag(QMLElement):

    """Represents a Tag element.

    <xs:complexType name="Tag">
            <xs:simpleContent>
                    <xs:extension base="NameString">
                            <xs:attribute name="NAME" type="NameString"
                            use="required"/>
                    </xs:extension>
            </xs:simpleContent>
    </xs:complexType>"""
    XMLNAME = 'TAG'
    XMLATTR_NAME = ('name', name_from_str, name_to_str)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        QMLElement.__init__(self, parent)
        self.name = None
        self.value = None

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value

    def content_changed(self):
        # called when all children have been parsed
        self.value = name_from_str(QMLElement.get_value(self))


class QMLComment(QMLElement):

    """Used to represent Comments in QML

    <xs:complexType name="Comment">
            <xs:simpleContent>
                    <xs:extension base="xs:string">
                            <xs:attribute name="AUTHOR" type="NameString"
                            use="required"/>
                            <xs:attribute name="NAME" type="NameString"
                            use="required"/>
                            <xs:attribute name="DATE" type="NameString"
                            use="required"/>
                            <xs:attribute name="TYPE" type="NameString"
                            use="required"/>
                    </xs:extension>
            </xs:simpleContent>
    </xs:complexType>
    """
    XMLNAME = 'COMMENT'
    XMLCONTENT = xml.XMLMixedContent
    SGMLCDATA = True
    XMLATTR_AUTHOR = ('author', name_from_str, name_to_str)
    XMLATTR_NAME = ('name', name_from_str, name_to_str)
    XMLATTR_DATE = ('date', name_from_str, name_to_str)
    XMLATTR_TYPE = ('type', name_from_str, name_to_str)

    def __init__(self, parent):
        QMLElement.__init__(self, parent)
        self.author = None
        self.name = None
        self.date = None
        self.type = None


class QMLAnswerThing(QMLElement):
    pass


class QMLContent(QMLAnswerThing):

    """Used to represent content in a question, typically contains text/html

    <xs:complexType name="Content">
            <xs:simpleContent>
                    <xs:extension base="xs:string">
                            <xs:attribute name="NAME" type="NameString"
                            use="optional"/>
                            <xs:attribute name="TYPE" type="NameString"
                            use="optional"/>
                            <xs:attribute name="STYLE" type="NameString"
                            use="optional"/>
                            <xs:attribute name="WIDTH" type="PositiveLength"
                            use="optional"/>
                            <xs:attribute name="HEIGHT" type="PositiveLength"
                            use="optional"/>
                            <xs:attribute name="HIDDEN" type="TrueFalseEnum"
                            use="optional"/>
                            <xs:attribute name="AUTOSTART" type="TrueFalseEnum"
                            use="optional"/>
                            <xs:attribute name="LOOP" type="TrueFalseEnum"
                            use="optional"/>
                            <xs:attribute name="ALIGN" type="AlignEnum"
                            use="optional"/>
                            <xs:attribute name="VSPACE" type="Margin"
                            use="optional"/>
                            <xs:attribute name="HSPACE" type="Margin"
                            use="optional"/>
                            <xs:attribute name="BORDER" type="Margin"
                            use="optional"/>
                            <xs:attribute name="ALT" type="AlternativeString"
                            use="optional"/>
                    </xs:extension>
            </xs:simpleContent>
    </xs:complexType>
    """
    XMLNAME = 'CONTENT'
    XMLCONTENT = xml.XMLMixedContent
    SGMLCDATA = True
    XMLATTR_NAME = ('name', name_from_str, name_to_str)
    XMLATTR_TYPE = ('type', name_from_str, name_to_str)
    XMLATTR_STYLE = ('style', name_from_str, name_to_str)
    XMLATTR_WIDTH = ('width', pve_length_from_str, pve_length_to_str)
    XMLATTR_HEIGHT = ('height', pve_length_from_str, pve_length_to_str)
    XMLATTR_HIDDEN = ('hidden', truefalse_from_str, truefalse_to_str)
    XMLATTR_AUTOSTART = ('autoStart', truefalse_from_str, truefalse_to_str)
    XMLATTR_LOOP = ('loop', truefalse_from_str, truefalse_to_str)
    XMLATTR_ALIGN = ('align', align_from_str, align_to_str)
    XMLATTR_VSPACE = ('vspace', margin_from_str, margin_to_str)
    XMLATTR_HSPACE = ('hspace', margin_from_str, margin_to_str)
    XMLATTR_BORDER = ('border', margin_from_str, margin_to_str)
    XMLATTR_ALT = ('alt', alternative_from_str, alternative_to_str)

    def __init__(self, parent):
        QMLAnswerThing.__init__(self, parent)
        self.name = None
        self.type = None
        self.style = None
        self.width = None
        self.height = None
        self.hidden = None
        self.autostart = None
        self.loop = None
        self.align = None
        self.vspace = None
        self.hspace = None
        self.border = None
        self.alt = None


class QMLAnswer(QMLElement):

    """Represents the Answer element.

    <xs:complexType name="Answer">
            <xs:choice maxOccurs="unbounded">
                    <xs:element name="CONTENT" type="Content"/>
                    <xs:element name="CHOICE" type="Choice"/>
            </xs:choice>
            <xs:attribute name="QTYPE" type="NameString" use="required"/>
            <xs:attribute name="SHUFFLE" type="ShuffleEnum" use="optional"/>
            <xs:attribute name="COMMENT" type="YesNoEnum" use="optional"/>
            <xs:attribute name="COMMENTLABEL" type="MessageString"
            use="optional"/>
            <xs:attribute name="COMMENTHEIGHT" type="CommentHeight"
            use="optional"/>
            <xs:attribute name="COMMENTWIDTH" type="CommentWidth"
            use="optional"/>
            <xs:attribute name="MAXSELECT" type="MaxSelect" use="optional"/>
            <xs:attribute name="SUBTYPE" type="DirectionEnum" use="optional"/>
            <xs:attribute name="EXTENSIONS" type="xs:string" use="optional"/>
            <xs:attribute name="MAXRESPONSE" type="MaxResponse"
            use="optional"/>
    </xs:complexType>
    """
    XMLNAME = 'ANSWER'
    XMLCONTENT = xml.ElementContent
    XMLATTR_QTYPE = ('qType', name_from_str, name_to_str)
    XMLATTR_SHUFFLE = ('shuffle', shuffle_from_str, shuffle_to_str)
    XMLATTR_COMMENT = ('comment', yesno_from_str, yesno_to_str)
    XMLATTR_COMMENTLABEL = (
        'commentLabel', message_from_str, message_to_str)
    XMLATTR_COMMENTHEIGHT = (
        'commentHeight', comment_height_from_str, comment_height_to_str)
    XMLATTR_COMMENTWIDTH = (
        'commentWidth', comment_width_from_str, comment_width_to_str)
    XMLATTR_MAXSELECT = ('maxSelect', max_select_from_str, max_select_to_str)
    XMLATTR_SUBTYPE = ('subType', direction_from_str, direction_to_str)
    XMLATTR_EXTENSIONS = 'extensions'
    XMLATTR_MAXRESPONSE = ('maxResponse', max_response_from_str,
                           max_response_to_str)

    def __init__(self, parent):
        QMLElement.__init__(self, parent)
        self.qType = None
        self.shuffle = None
        self.comment = None
        self.commentLabel = None
        self.commentHeight = None
        self.commentWidth = None
        self.maxSelect = None
        self.subType = None
        self.extensions = None
        self.maxResponse = None
        self.QMLAnswerThing = []

    def get_children(self):
        for child in self.QMLAnswerThing:
            yield child


class QMLChoice(QMLAnswerThing):

    """Represents a choice.

    <xs:complexType name="Choice">
            <xs:sequence>
                    <xs:element name="OPTION" type="Option" minOccurs="0"
                    maxOccurs="unbounded"/>
                    <xs:element name="CONTENT" type="Content"/>
            </xs:sequence>
            <xs:attribute name="ID" type="NameString" use="optional"/>
            <xs:attribute name="MAXCHARS" type="PositiveLength"
            use="optional"/>
            <xs:attribute name="SCROLL" type="DirectionEnum" use="optional"/>
    </xs:complexType>
    """
    XMLNAME = 'CHOICE'
    XMLCONTENT = xml.ElementContent
    XMLATTR_ID = ('cid', name_from_str, name_to_str)
    XMLATTR_MAXCHARS = ('maxChars', pve_length_from_str, pve_length_to_str)
    XMLATTR_SCROLL = ('scroll', direction_from_str, direction_to_str)

    def __init__(self, parent):
        QMLAnswerThing.__init__(self, parent)
        self.cid = None
        self.maxChars = None
        self.scroll = None
        self.QMLOption = []
        self.QMLContent = QMLContent(self)

    def get_children(self):
        for child in self.QMLOption:
            yield child
        yield self.QMLContent


class QMLOption(QMLElement):

    """Represents an option.

    <xs:complexType name="Option">
            <xs:simpleContent>
                    <xs:extension base="xs:string">
                            <xs:attribute name="VISIBLE" type="YesNoEnum"
                            use="optional"/>
                    </xs:extension>
            </xs:simpleContent>
    </xs:complexType>
    """
    XMLNAME = 'OPTION'
    XMLCONTENT = xml.XMLMixedContent
    XMLATTR_VISIBLE = ('visible', yesno_from_str, yesno_to_str)

    def __init__(self, parent):
        QMLElement.__init__(self, parent)
        self.visible = None


class QMLOutcome(QMLElement):

    """Represents an outcome.

    <xs:complexType name="Outcome">
            <xs:sequence>
                    <xs:element name="CONDITION" type="xs:string"/>
                    <xs:element name="CONTENT" type="Content"/>
            </xs:sequence>
            <xs:attribute name="ID" type="NameString" use="optional"/>
            <xs:attribute name="SCORE" type="Length" use="optional"/>
            <xs:attribute name="ADD" type="Length" use="optional"/>
            <xs:attribute name="CONTINUE" type="TrueFalseEnum" use="optional"/>
    </xs:complexType>
    """
    XMLNAME = 'OUTCOME'
    XMLCONTENT = xml.ElementContent
    XMLATTR_ID = ('oid', name_from_str, name_to_str)
    XMLATTR_SCORE = ('length', length_from_str, length_to_str)
    XMLATTR_ADD = ('add', length_from_str, length_to_str)
    XMLATTR_CONTINTUE = (
        'continueFlag', truefalse_from_str, truefalse_to_str)

    def __init__(self, parent):
        QMLElement.__init__(self, parent)
        self.oid = None
        self.length = None
        self.add = None
        self.continueFlag = None
        self.QMLCondition = QMLCondition(self)
        self.QMLContent = QMLContent(self)

    def get_children(self):
        yield self.QMLCondition
        yield self.QMLContent


class QMLCondition(QMLElement):
    XMLNAME = "CONDITION"
    XMLCONTENT = xml.XMLMixedContent


class QMLDocument(xml.Document):

    """Class for working with QML documents."""

    def __init__(self, **args):
        """"""
        xml.Document.__init__(self, **args)

    classMap = {}
    """classMap is a mapping from element names to the class object that
    will be used to represent them."""

    def get_element_class(self, name):
        """Returns the class to use to represent an element with the
        given name.

        This method is used by the XML parser.  The class object is
        looked up in :py:attr:`classMap`, if no specialized class is
        found then the general :py:class:`pyslet.xml.structures.Element`
        class is returned."""
        return QMLDocument.classMap.get(
            name, QMLDocument.classMap.get(None, xml.Element))


xml.map_class_elements(QMLDocument.classMap, globals())
