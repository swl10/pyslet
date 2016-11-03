#! /usr/bin/env python
"""This module implements the QML specification defined by Questionmark.

References:
"""

import pyslet.xml.structures as xml
import pyslet.xml.xsdatatypes as xsi
import string
import itertools


def ParseQuestionID(src):
    result = []
    for c in src.strip():
        if c in "0123456789":
            result.append(c)
        else:
            raise ValueError("Can't parse QuestionID from %s" % src)
    return string.join(result, '')


def FormatQuestionID(qid):
    return ParseQuestionID(qid)


def ParseNameString(src):
    if len(src) > 50:
        raise ValueError("NameString exceeds 50 characters: %s" % src)
    return src


def FormatNameString(name):
    return ParseNameString(name)


def ParseAlternativeString(src):
    if len(src) > 100:
        raise ValueError("AlternativeString exceeds 100 characters: %s" % src)
    return src


def FormatAlternativeString(alt):
    return ParseAlternativeString(alt)


def ParseMessageString(src):
    """MessageString is a simple length restricted string:

    <xs:simpleType name="MessageString">
            <xs:restriction base="xs:string">
                    <xs:maxLength value="1024"/>
            </xs:restriction>
    </xs:simpleType>"""
    if len(src) > 1024:
        raise ValueError("MessageString exceeds 1024 characters: %s" % src)
    return src


def FormatMessageString(msg):
    return ParseMessageString(msg)


def ParseCeiling(src):
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


def FormatCeiling(value):
    if value < -1:
        return unicode(-1)
    elif value > 32767:
        return unicode(32767)
    else:
        return unicode(value)


def ParseFloor(src):
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


def FormatFloor(value):
    if value > 0:
        return unicode(0)
    elif value < -100:
        return unicode(-100)
    else:
        return unicode(value)


def ParseLength(src):
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


def FormatLength(value):
    if value < -32768:
        return unicode(-32768)
    elif value > 32767:
        return unicode(32767)
    else:
        return unicode(value)


def ParsePositiveLength(src):
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


def FormatPositiveLength(value):
    if value < 0:
        return unicode(0)
    elif value > 32767:
        return unicode(32767)
    else:
        return unicode(value)


def ParseCommentHeight(src):
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


def FormatCommentHeight(value):
    if value < 1:
        return unicode(1)
    elif value > 40:
        return unicode(40)
    else:
        return unicode(value)


def ParseCommentWidth(src):
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


def FormatCommentWidth(value):
    if value < 5:
        return unicode(5)
    elif value > 100:
        return unicode(100)
    else:
        return unicode(value)


def ParseMaxSelect(src):
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


def FormatMaxSelect(value):
    if value < 0:
        return unicode(0)
    elif value > 40:
        return unicode(40)
    else:
        return unicode(value)


def ParseMaxResponse(src):
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


def FormatMaxResponse(value):
    if value < 1:
        return unicode(1)
    elif value > 32767:
        return unicode(32767)
    else:
        return unicode(value)


def ParseTrueFalseEnum(src):
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


def FormatTrueFalseEnum(value):
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


def ParseAlignEnum(value):
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


def FormatAlignEnum(value):
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


def ParseShuffleEnum(value):
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


def FormatShuffleEnum(value):
    return QMLShuffleEnum.encode.get(value, None)


def ParseYesNoEnum(src):
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


def FormatYesNoEnum(value):
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


def ParseDirectionEnum(value):
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


def FormatDirectionEnum(value):
    return QMLDirectionEnum.encode.get(value, None)


def ParseMargin(src):
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


def FormatMargin(value):
    if value < 0:
        return unicode(0)
    elif value > 50:
        return unicode(50)
    else:
        return unicode(value)


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
    XMLATTR_ID = ('qid', ParseQuestionID, FormatQuestionID)
    XMLATTR_TOPIC = 'topic'
    XMLATTR_DESCRIPTION = 'description'
    XMLATTR_TYPE = ('type', ParseNameString, FormatNameString)
    XMLATTR_STATUS = ('status', ParseNameString, FormatNameString)
    XMLATTR_CEILING = ('ceiling', ParseCeiling, FormatCeiling)
    XMLATTR_FLOOR = ('floor', ParseFloor, FormatFloor)
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
    XMLATTR_NAME = ('name', ParseNameString, FormatNameString)
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
        self.value = ParseNameString(QMLElement.get_value(self))


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
    XMLATTR_AUTHOR = ('author', ParseNameString, FormatNameString)
    XMLATTR_NAME = ('name', ParseNameString, FormatNameString)
    XMLATTR_DATE = ('date', ParseNameString, FormatNameString)
    XMLATTR_TYPE = ('type', ParseNameString, FormatNameString)

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
    XMLATTR_NAME = ('name', ParseNameString, FormatNameString)
    XMLATTR_TYPE = ('type', ParseNameString, FormatNameString)
    XMLATTR_STYLE = ('style', ParseNameString, FormatNameString)
    XMLATTR_WIDTH = ('width', ParsePositiveLength, FormatPositiveLength)
    XMLATTR_HEIGHT = ('height', ParsePositiveLength, FormatPositiveLength)
    XMLATTR_HIDDEN = ('hidden', ParseTrueFalseEnum, FormatTrueFalseEnum)
    XMLATTR_AUTOSTART = ('autoStart', ParseTrueFalseEnum, FormatTrueFalseEnum)
    XMLATTR_LOOP = ('loop', ParseTrueFalseEnum, FormatTrueFalseEnum)
    XMLATTR_ALIGN = ('align', ParseAlignEnum, FormatAlignEnum)
    XMLATTR_VSPACE = ('vspace', ParseMargin, FormatMargin)
    XMLATTR_HSPACE = ('hspace', ParseMargin, FormatMargin)
    XMLATTR_BORDER = ('border', ParseMargin, FormatMargin)
    XMLATTR_ALT = ('alt', ParseAlternativeString, FormatAlternativeString)

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
    XMLATTR_QTYPE = ('qType', ParseNameString, FormatNameString)
    XMLATTR_SHUFFLE = ('shuffle', ParseShuffleEnum, FormatShuffleEnum)
    XMLATTR_COMMENT = ('comment', ParseYesNoEnum, FormatYesNoEnum)
    XMLATTR_COMMENTLABEL = (
        'commentLabel', ParseMessageString, FormatMessageString)
    XMLATTR_COMMENTHEIGHT = (
        'commentHeight', ParseCommentHeight, FormatCommentHeight)
    XMLATTR_COMMENTWIDTH = (
        'commentWidth', ParseCommentWidth, FormatCommentWidth)
    XMLATTR_MAXSELECT = ('maxSelect', ParseMaxSelect, FormatMaxSelect)
    XMLATTR_SUBTYPE = ('subType', ParseDirectionEnum, FormatDirectionEnum)
    XMLATTR_EXTENSIONS = 'extensions'
    XMLATTR_MAXRESPONSE = ('maxResponse', ParseMaxResponse, FormatMaxResponse)

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
    XMLATTR_ID = ('cid', ParseNameString, FormatNameString)
    XMLATTR_MAXCHARS = ('maxChars', ParsePositiveLength, FormatPositiveLength)
    XMLATTR_SCROLL = ('scroll', ParseDirectionEnum, FormatDirectionEnum)

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
    XMLATTR_VISIBLE = ('visible', ParseYesNoEnum, FormatYesNoEnum)

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
    XMLATTR_ID = ('oid', ParseNameString, FormatNameString)
    XMLATTR_SCORE = ('length', ParseLength, FormatLength)
    XMLATTR_ADD = ('add', ParseLength, FormatLength)
    XMLATTR_CONTINTUE = (
        'continueFlag', ParseTrueFalseEnum, FormatTrueFalseEnum)

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
    """classMap is a mapping from element names to the class object that will be
    used to represent them."""

    def get_element_class(self, name):
        """Returns the class to use to represent an element with the given name.

        This method is used by the XML parser.  The class object is looked up
        in :py:attr:`classMap`, if no specialized class is found then the
        general :py:class:`pyslet.xml.structures.Element` class is returned."""
        return QMLDocument.classMap.get(
            name, QMLDocument.classMap.get(None, xml.Element))


xml.map_class_elements(QMLDocument.classMap, globals())
