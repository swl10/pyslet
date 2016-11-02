#! /usr/bin/env python

import itertools

from . import core
from . import content
from .. import html401 as html
from ..xml import structures as xml
from ..xml import xsdatatypes as xsi


class Interaction(content.BodyElement):

    """Interactions allow the candidate to interact with the item. Through an
    interaction, the candidate selects or constructs a response::

            <xsd:attributeGroup name="interaction.AttrGroup">
                    <xsd:attributeGroup ref="bodyElement.AttrGroup"/>
                    <xsd:attribute name="responseIdentifier"
                    type="identifier.Type" use="required"/>
            </xsd:attributeGroup>"""
    XMLATTR_responseIdentifier = (
        'responseIdentifier', core.ValidateIdentifier, lambda x: x)

    def __init__(self, parent):
        content.BodyElement.__init__(self, parent)
        self.responseIdentifier = ''


class InlineInteraction(html.InlineMixin, Interaction):

    """Abstract class for interactions that appear inline."""
    pass


class BlockInteraction(html.BlockMixin, Interaction):

    """An interaction that behaves like a block in the content model. Most
    interactions are of this type::

            <xsd:group name="blockInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="prompt" minOccurs="0"
                            maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        Interaction.__init__(self, parent)
        self.Prompt = None

    def get_children(self):
        if self.Prompt:
            yield self.Prompt


class Prompt(content.BodyElement):

    """The prompt used in block interactions
    ::

            <xsd:group name="prompt.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="inlineStatic.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'prompt')
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        content.BodyElement.__init__(self, parent)

    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.InlineMixin):
            return content.BodyElement.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (child_class.__name__, self.__class__.__name__))

    def render_html(self, parent, profile, item_state):
        html_p = parent.add_child(html.P)
        html_p.style_class = ["prompt"]
        self.render_html_children(html_p, profile, item_state)


class Choice(content.BodyElement):

    """Many of the interactions involve choosing one or more predefined choices
    ::

            <xsd:attributeGroup name="choice.AttrGroup">
                    <xsd:attributeGroup ref="bodyElement.AttrGroup"/>
                    <xsd:attribute name="identifier" type="identifier.Type"
                    use="required"/>
                    <xsd:attribute name="fixed" type="boolean.Type"
                    use="optional"/>
                    <xsd:attribute name="templateIdentifier"
                    type="identifier.Type" use="optional"/>
                    <xsd:attribute name="showHide" type="showHide.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_fixed = ('fixed', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_templateIdentifier = (
        'templateIdentifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_showHide = (
        'showHide', core.ShowHide.from_str_lower, core.ShowHide.to_str)

    def __init__(self, parent):
        content.BodyElement.__init__(self, parent)
        self.identifier = ''
        self.fixed = None
        self.templateIdentifier = None
        self.showHide = None


class AssociableChoice(Choice):

    """Other interactions involve associating pairs of predefined choices
    ::

            <xsd:attributeGroup name="associableChoice.AttrGroup">
                    <xsd:attributeGroup ref="choice.AttrGroup"/>
                    <xsd:attribute name="matchGroup" use="optional">
                            <xsd:simpleType>
                                    <xsd:list itemType="identifier.Type"/>
                            </xsd:simpleType>
                    </xsd:attribute>
            </xsd:attributeGroup>"""
    XMLATTR_matchGroup = ('matchGroup', core.ValidateIdentifier, lambda x: x)

    def __init__(self, parent):
        Choice.__init__(self, parent)
        self.matchGroup = []


class ChoiceInteraction(BlockInteraction):

    """The choice interaction presents a set of choices to the candidate. The
    candidate's task is to select one or more of the choices, up to a maximum
    of maxChoices::

            <xsd:attributeGroup name="choiceInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="shuffle" type="boolean.Type"
                    use="required"/>
                    <xsd:attribute name="maxChoices" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="minChoices" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="choiceInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:element ref="simpleChoice" minOccurs="1"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'choiceInteraction')
    XMLATTR_shuffle = ('shuffle', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_maxChoices = (
        'maxChoices', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minChoices = (
        'minChoices', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.shuffle = False
        self.maxChoices = 1
        self.minChoices = None
        self.SimpleChoice = []

    def get_children(self):
        for child in itertools.chain(BlockInteraction.get_children(self),
                                     self.SimpleChoice):
            yield child

    def render_html(self, parent, profile, item_state):
        html_div = parent.add_child(html.Div)
        html_div.style_class = ["choiceInteraction"]
        for child in self.get_children():
            child.render_html(html_div, profile, item_state)


class OrderInteraction(BlockInteraction):

    """In an order interaction the candidate's task is to reorder the choices,
    the order in which the choices are displayed initially is significant::

            <xsd:attributeGroup name="orderInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="shuffle" type="boolean.Type"
                    use="required"/>
                    <xsd:attribute name="minChoices" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="maxChoices" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="orientation" type="orientation.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="orderInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:element ref="simpleChoice" minOccurs="1"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'orderInteraction')
    XMLATTR_shuffle = ('shuffle', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_maxChoices = (
        'maxChoices', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minChoices = (
        'minChoices', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_orientation = (
        'orientation',
        core.Orientation.from_str_lower,
        core.Orientation.to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.shuffle = False
        self.maxChoices = 1
        self.minChoices = None
        self.orientation = None
        self.SimpleChoice = []

    def get_children(self):
        for child in itertools.chain(
                BlockInteraction.get_children(self),
                self.SimpleChoice):
            yield child

    def render_html(self, parent, profile, item_state):
        html_div = parent.add_child(html.Div)
        html_div.style_class = ["orderInteraction"]
        for child in self.get_children():
            child.render_html(html_div, profile, item_state)


class SimpleChoice(content.FlowContainerMixin, Choice):

    """A SimpleChoice is a choice that contains flow objects; it must not
    contain any nested interactions::

            <xsd:group name="simpleChoice.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="flowStatic.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'simpleChoice')
    XMLCONTENT = xml.XMLMixedContent

    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.FlowMixin):
            return Choice.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))

    def render_html(self, parent, profile, item_state):
        # what type of choice are we?
        interaction = self.find_parent(Interaction)
        if isinstance(interaction, ChoiceInteraction):
            # represented as a DL with DD for each choice
            html_div = parent.add_child(html.Div)
            html_div.style_class = ['simpleChoice']
            html_input = html_div.add_child(html.Input)
            sname = interaction.responseIdentifier + ".SAVED"
            if sname in item_state:
                v = item_state[sname]
            else:
                v = item_state[interaction.responseIdentifier]
            if interaction.maxChoices != 1:
                # we need to be a check-box
                html_input.type = html.InputType.checkbox
                html_input.name = item_state.formPrefix + \
                    interaction.responseIdentifier
                html_input.value = self.identifier
                html_input.checked = (self.identifier in v.value)
            else:
                # we should be a radio button
                html_input.type = html.InputType.radio
                html_input.name = item_state.formPrefix + \
                    interaction.responseIdentifier
                html_input.value = self.identifier
                html_input.checked = (v.value == self.identifier)
            parent = html_div
        elif isinstance(interaction, OrderInteraction):
            # we need to be a pull down menu of rank orderings
            raise NotImplementedError
        self.render_html_children(parent, profile, item_state)


class AssociateInteraction(BlockInteraction):

    """An associate interaction is a blockInteraction that presents candidates
    with a number of choices and allows them to create associations between
    them::

            <xsd:attributeGroup name="associateInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="shuffle" type="boolean.Type"
                    use="required"/>
                    <xsd:attribute name="maxAssociations" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="minAssociations" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="associateInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:element ref="simpleAssociableChoice"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'associateInteraction')
    XMLATTR_shuffle = ('shuffle', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_maxAssociations = (
        'maxAssociations', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minAssociations = (
        'minAssociations', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.shuffle = False
        self.maxAssociations = 1
        self.minAssociations = None
        self.SimpleAssociableChoice = []

    def get_children(self):
        for child in itertools.chain(
                BlockInteraction.get_children(self),
                self.SimpleAssociableChoice):
            yield child

    def render_html(self, parent, profile, item_state):
        html_div = parent.add_child(html.Div)
        html_div.style_class = ["associateInteraction"]
        for child in self.get_children():
            child.render_html(html_div, profile, item_state)


class MatchInteraction(BlockInteraction):

    """A match interaction is a blockInteraction that presents candidates with
    two sets of choices and allows them to create associates between pairs of
    choices in the two sets, but not between pairs of choices in the same set::

            <xsd:attributeGroup name="matchInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="shuffle" type="boolean.Type"
                    use="required"/>
                    <xsd:attribute name="maxAssociations" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="minAssociations" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="matchInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:element ref="simpleMatchSet" minOccurs="2"
                            maxOccurs="2"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'matchInteraction')
    XMLATTR_shuffle = ('shuffle', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_maxAssociations = (
        'maxAssociations', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minAssociations = (
        'minAssociations', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.shuffle = False
        self.maxAssociations = 1
        self.minAssociations = None
        self.SimpleMatchSet = []

    def get_children(self):
        for child in itertools.chain(
                BlockInteraction.get_children(self),
                self.SimpleMatchSet):
            yield child

    def render_html(self, parent, profile, item_state):
        html_div = parent.add_child(html.Div)
        html_div.style_class = ["matchInteraction"]
        for child in self.get_children():
            child.render_html(html_div, profile, item_state)


class SimpleAssociableChoice(content.FlowContainerMixin, AssociableChoice):

    """associableChoice is a choice that contains flowStatic objects, it must
    not contain nested interactions::

            <xsd:attributeGroup name="simpleAssociableChoice.AttrGroup">
                    <xsd:attributeGroup ref="associableChoice.AttrGroup"/>
                    <xsd:attribute name="matchMax" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="matchMin" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="simpleAssociableChoice.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="flowStatic.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'simpleAssociableChoice')
    XMLATTR_matchMax = ('matchMax', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_matchMin = ('matchMin', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        AssociableChoice.__init__(self, parent)
        self.matchMax = None
        self.matchMin = None

    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.FlowMixin):
            return Choice.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))


class SimpleMatchSet(core.QTIElement):

    """Contains an ordered set of choices for the set
    ::

            <xsd:group name="simpleMatchSet.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="simpleAssociableChoice"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'simpleMatchSet')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.SimpleAssociableChoice = []

    def get_children(self):
        for child in self.SimpleAssociableChoice:
            yield child


class GapMatchInteraction(BlockInteraction):

    """A gap match interaction is a blockInteraction that contains a number gaps
    that the candidate can fill from an associated set of choices::

            <xsd:attributeGroup name="gapMatchInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="shuffle" type="boolean.Type"
                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="gapMatchInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:group ref="gapChoice.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                            <xsd:group ref="blockStatic.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'gapMatchInteraction')
    XMLATTR_shuffle = ('shuffle', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.shuffle = False
        self.GapChoice = []

    def get_children(self):
        for child in itertools.chain(
                BlockInteraction.get_children(self),
                self.GapChoice):
            yield child
        for child in content.BodyElement.get_children(self):
            yield child

    def add_child(self, child_class, name=None):
        if issubclass(child_class, (Prompt, GapChoice, html.BlockMixin)):
            return BlockInteraction.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))

    def render_html(self, parent, profile, item_state):
        html_div = parent.add_child(html.Div)
        html_div.style_class = ["gapMatchInteraction"]
        for child in self.get_children():
            child.render_html(html_div, profile, item_state)


class Gap(html.InlineMixin, AssociableChoice):

    """A gap is an inline element that must only appear within a
    gapMatchInteraction
    ::

            <xsd:attributeGroup name="gap.AttrGroup">
                    <xsd:attributeGroup ref="associableChoice.AttrGroup"/>
                    <xsd:attribute name="required" type="boolean.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'gap')
    XMLATTR_required = ('required', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        AssociableChoice.__init__(self, parent)
        self.required = False


class GapChoice(AssociableChoice):

    """The choices that are used to fill the gaps in a gapMatchInteraction are
    either simple runs of text or single image objects, both derived from
    gapChoice::

            <xsd:attributeGroup name="gapChoice.AttrGroup">
                    <xsd:attributeGroup ref="associableChoice.AttrGroup"/>
                    <xsd:attribute name="matchMax" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="matchMin" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_matchMax = ('matchMax', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_matchMin = ('matchMin', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        AssociableChoice.__init__(self, parent)
        self.matchMax = None
        self.matchMin = None


class GapText(GapChoice):

    """A simple run of text to be inserted into a gap by the user, may be
    subject to variable value substitution with printedVariable::

            <xsd:group name="gapText.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="printedVariable" minOccurs="0"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'gapText')
    XMLCONTENT = xml.XMLMixedContent

    def add_child(self, child_class, name=None):
        if issubclass(child_class, content.PrintedVariable):
            return GapChoice.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (child_class.__name__, self.__class__.__name__))


class GapImg(GapChoice):

    """A gap image contains a single image object to be inserted into a gap by
    the candidate::

            <xsd:attributeGroup name="gapImg.AttrGroup">
                    <xsd:attributeGroup ref="gapChoice.AttrGroup"/>
                    <xsd:attribute name="objectLabel" type="string.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="gapImg.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="object" minOccurs="1"
                            maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'gapImg')
    XMLATTR_objectLabel = 'objectLabel'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        GapChoice.__init__(self, parent)
        self.objectLabel = None
        self.Object = html.Object(self)
        content.fix_html_namespace(self.Object)

    def get_children(self):
        yield self.Object


class InlineChoiceInteraction(InlineInteraction):

    """An inline choice is an inlineInteraction that presents the user with a
    set of choices, each of which is a simple piece of text::

            <xsd:attributeGroup name="inlineChoiceInteraction.AttrGroup">
                    <xsd:attributeGroup ref="inlineInteraction.AttrGroup"/>
                    <xsd:attribute name="shuffle" type="boolean.Type"
                    use="required"/>
                    <xsd:attribute name="required" type="boolean.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="inlineChoiceInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="inlineChoice" minOccurs="1"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'inlineChoiceInteraction')
    XMLATTR_shuffle = ('shuffle', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_required = ('required', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        InlineInteraction.__init__(self, parent)
        self.shuffle = False
        self.required = False
        self.InlineChoice = []

    def get_children(self):
        for child in self.InlineChoice:
            yield child


class InlineChoice(Choice):

    """A simple run of text to be displayed to the user, may be subject to
    variable value substitution with printedVariable::

            <xsd:group name="inlineChoice.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="printedVariable" minOccurs="0"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'inlineChoice')
    XMLCONTENT = xml.XMLMixedContent

    def add_child(self, child_class, name=None):
        if issubclass(child_class, content.PrintedVariable):
            return Choice.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (child_class.__name__, self.__class__.__name__))


class StringInteractionMixin:

    """Abstract mix-in class for interactions based on free-text input.  String
    interactions can be bound to numeric response variables, instead of
    strings, if desired::

            <xsd:attributeGroup name="stringInteraction.AttrGroup">
                    <xsd:attribute name="base" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="stringIdentifier"
                    type="identifier.Type" use="optional"/>
                    <xsd:attribute name="expectedLength" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="patternMask" type="string.Type"
                    use="optional"/>
                    <xsd:attribute name="placeholderText" type="string.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_base = ('base', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_stringIdentifier = (
        'stringIdentifier', core.ValidateIdentifier, lambda x: x)
    XMLATTR_expectedLength = (
        'expectedLength', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_patternMask = 'patternMask'
    XMLATTR_placeholderText = 'placeholderText'

    def __init__(self):
        self.base = None
        self.stringIdentifier = None
        self.expectedLength = None
        self.patternMask = None
        self.placeholderText = None


class TextEntryInteraction(StringInteractionMixin, InlineInteraction):

    """A textEntry interaction is an inlineInteraction that obtains a simple
    piece of text from the candidate."""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'textEntryInteraction')
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        InlineInteraction.__init__(self, parent)
        StringInteractionMixin.__init__(self)


class TextFormat(xsi.EnumerationNoCase):

    """Used to control the format of the text entered by the candidate::

            <xsd:simpleType name="textFormat.Type">
                    <xsd:restriction base="xsd:NMTOKEN">
                            <xsd:enumeration value="plain"/>
                            <xsd:enumeration value="preFormatted"/>
                            <xsd:enumeration value="xhtml"/>
                    </xsd:restriction>
            </xsd:simpleType>

    Defines constants for the above formats.  Usage example::

            TextFormat.plain

    Note that::

            TextFormat.DEFAULT == TextFormat.plain

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'plain': 1,
        'preFormatted': 2,
        'xhtml': 3
    }
    aliases = {
        None: 'plain'
    }


class ExtendedTextInteraction(StringInteractionMixin, BlockInteraction):

    """An extended text interaction is a blockInteraction that allows the
    candidate to enter an extended amount of text::

            <xsd:attributeGroup name="extendedTextInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attributeGroup ref="stringInteraction.AttrGroup"/>
                    <xsd:attribute name="maxStrings" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="minStrings" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="expectedLines" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="format" type="textFormat.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'extendedTextInteraction')
    XMLATTR_maxStrings = (
        'maxStrings', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minStrings = (
        'minStrings', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_expectedLines = (
        'expectedLines', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_format = (
        'format', TextFormat.from_str_lower, TextFormat.to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        StringInteractionMixin.__init__(self)
        self.maxStrings = None
        self.minStrings = None
        self.expectedLines = None
        self.format = None


class HottextInteraction(BlockInteraction):

    """The hottext interaction presents a set of choices to the candidate
    represented as selectable runs of text embedded within a surrounding
    context, such as a simple passage of text::

            <xsd:attributeGroup name="hottextInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="maxChoices" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="minChoices" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="hottextInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:group ref="blockStatic.ElementGroup"
                            minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>
    """
    XMLNAME = (core.IMSQTI_NAMESPACE, 'hottextInteraction')
    XMLATTR_maxChoices = (
        'maxChoices', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minChoices = (
        'minChoices', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.maxChoices = 1
        self.minChoices = None

    def add_child(self, child_class, name=None):
        if issubclass(child_class, (Prompt, html.BlockMixin)):
            return BlockInteraction.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))


class Hottext(html.FlowMixin, Choice):

    """A hottext area is used within the content of an hottextInteraction to
    provide the individual choices::

            <xsd:group name="hottext.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="inlineStatic.ElementGroup"
                            minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'hottext')
    XMLCONTENT = xml.XMLMixedContent

    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.InlineMixin):
            return Choice.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))


class HotspotMixin:

    """Used by graphic interactions involving images with specially defined
    areas or hotspots::

            <xsd:attributeGroup name="hotspot.AttrGroup">
                    <xsd:attribute name="shape" type="shape.Type"
                    use="required"/>
                    <xsd:attribute name="coords" type="coords.Type"
                    use="required"/>
                    <xsd:attribute name="hotspotLabel" type="string256.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_shape = (
        'shape', core.Shape.from_str_lower, core.Shape.to_str)
    XMLATTR_coords = ('coords', html.Coords.from_str, html.Coords.__unicode__)
    XMLATTR_hotspotLabel = 'hotspotLabel'

    def __init__(self):
        self.shape = None
        self.coords = html.Coords()
        self.hotspotLabel = None


class HotspotChoice(HotspotMixin, Choice):

    """A simple choice consisting of a hot-spot
    ::

            <xsd:attributeGroup name="hotspotChoice.AttrGroup">
                    <xsd:attributeGroup ref="choice.AttrGroup"/>
                    <xsd:attributeGroup ref="hotspot.AttrGroup"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'hotspotChoice')
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        Choice.__init__(self, parent)
        HotspotMixin.__init__(self)


class AssociableHotspot(HotspotMixin, AssociableChoice):

    """An associable choice consisting of a hot-spot
    ::

            <xsd:attributeGroup name="associableHotspot.AttrGroup">
                    <xsd:attributeGroup ref="associableChoice.AttrGroup"/>
                    <xsd:attributeGroup ref="hotspot.AttrGroup"/>
                    <xsd:attribute name="matchMax" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="matchMin" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'associableHotspot')
    XMLATTR_matchMax = ('matchMax', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_matchMin = ('matchMin', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.XMLEmpty

    def __init__(self, parent):
        AssociableChoice.__init__(self, parent)
        HotspotMixin.__init__(self)
        self.matchMax = None
        self.matchMin = None


class GraphicInteraction(BlockInteraction):

    """Abstract class for all graphical interactions
    ::

            <xsd:group name="graphicInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="blockInteraction.ContentGroup"/>
                            <xsd:element ref="object" minOccurs="1"
                            maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.Object = html.Object(self)
        content.fix_html_namespace(self.Object)

    def get_children(self):
        for child in BlockInteraction.get_children(self):
            yield child
        yield self.Object


class HotspotInteraction(GraphicInteraction):

    """A hotspot interaction is a graphical interaction with a corresponding set
    of choices that are defined as areas of the graphic image::

            <xsd:attributeGroup name="hotspotInteraction.AttrGroup">
                    <xsd:attributeGroup ref="graphicInteraction.AttrGroup"/>
                    <xsd:attribute name="maxChoices" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="minChoices" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="hotspotInteraction.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="graphicInteraction.ContentGroup"/>
                            <xsd:element ref="hotspotChoice" minOccurs="1"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'hotspotInteraction')
    XMLATTR_maxChoices = (
        'maxChoices', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minChoices = (
        'minChoices', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        GraphicInteraction.__init__(self, parent)
        self.maxChoices = 1
        self.minChoices = None
        self.HotspotChoice = []

    def get_children(self):
        return itertools.chain(
            GraphicInteraction.get_children(self),
            self.HotspotChoice)


class SelectPointInteraction(GraphicInteraction):

    """Like hotspotInteraction, a select point interaction is a graphic
    interaction. The candidate's task is to select one or more points::

            <xsd:attributeGroup name="selectPointInteraction.AttrGroup">
                    <xsd:attributeGroup ref="graphicInteraction.AttrGroup"/>
                    <xsd:attribute name="maxChoices" type="integer.Type"
                    use="required"/>
                    <xsd:attribute name="minChoices" type="integer.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'selectPointInteraction')
    XMLATTR_maxChoices = (
        'maxChoices', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_minChoices = (
        'minChoices', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        GraphicInteraction.__init__(self, parent)
        self.maxChoices = 1
        self.minChoices = None


class SliderInteraction(BlockInteraction):

    """The slider interaction presents the candidate with a control for
    selecting a numerical value between a lower and upper bound. It must be
    bound to a response variable with single cardinality with a base-type of
    either integer or float::

            <xsd:attributeGroup name="sliderInteraction.AttrGroup">
                    <xsd:attributeGroup ref="blockInteraction.AttrGroup"/>
                    <xsd:attribute name="lowerBound" type="float.Type"
                    use="required"/>
                    <xsd:attribute name="upperBound" type="float.Type"
                    use="required"/>
                    <xsd:attribute name="step" type="integer.Type"
                    use="optional"/>
                    <xsd:attribute name="stepLabel" type="boolean.Type"
                    use="optional"/>
                    <xsd:attribute name="orientation" type="orientation.Type"
                    use="optional"/>
                    <xsd:attribute name="reverse" type="boolean.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'sliderInteraction')
    XMLATTR_lowerBound = ('lowerBound', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_upperBound = ('upperBound', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_step = ('step', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_stepLabel = ('stepLabel', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_orientation = (
        'orientation',
        core.Orientation.from_str_lower,
        core.Orientation.to_str)
    XMLATTR_reverse = ('reverse', xsi.boolean_from_str, xsi.boolean_to_str)

    def __init__(self, parent):
        BlockInteraction.__init__(self, parent)
        self.lowerBound = None
        self.upperBound = None
        self.step = None
        self.stepLabel = False
        self.orientation = None
        self.reverse = None
