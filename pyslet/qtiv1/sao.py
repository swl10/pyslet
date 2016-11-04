#! /usr/bin/env python

import itertools

from . import common
from . import core
from ..xml import structures as xml


class SelectionOrdering(common.QTICommentContainer):

    """The <selection_ordering> element is the container for all of the
    selection and ordering instructions that are to be applied to the
    corresponding objects (Sections and Items). The positioning of the Section
    and Item objects within the parent object defines the default coverage of
    the ordering with respect to the selected objects::

    <!ELEMENT selection_ordering (qticomment? , sequence_parameter* ,
    selection* , order?)>
    <!ATTLIST selection_ordering  sequence_type CDATA  #IMPLIED >"""
    XMLNAME = "selection_ordering"
    XMLATTR_sequence_type = 'sequenceType'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.sequenceType = None
        self.SequenceParameter = []
        self.Selection = []
        self.Order = None

    def get_children(self):
        for child in itertools.chain(
                common.QTICommentContainer.get_children(self),
                self.SequenceParameter,
                self.Selection):
            yield child
        if self.Order:
            yield self.Order


class SequenceParameter(core.QTIElement):

    """This element contains the comments that are relevant to the
    selection and ordering structure as a whole::

    <!ELEMENT sequence_parameter (#PCDATA)>
    <!ATTLIST sequence_parameter  pname CDATA  #REQUIRED >"""
    XMLNAME = 'sequence_parameter'
    XMLATTR_pname = 'pName'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.pName = None


class Selection(core.QTIElement):

    """The <selection> element is used to express the selection rules that are
    to be applied to the identified objectbank or the set of child objects
    contained within the parent. The full set of rules must be parsed before
    the consistent selection can be achieved::

    <!ELEMENT selection (sourcebank_ref? , selection_number? ,
            selection_metadata? ,
            (and_selection | or_selection | not_selection |
            selection_extension)?)>"""
    XMLNAME = 'selection'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.SourceBankRef = None
        self.SelectionNumber = None
        self.SelectionMetadata = None
        self.SelectionChildMixin = None

    def get_children(self):
        if self.SourceBankRef:
            yield self.SourceBankRef
        if self.SelectionNumber:
            yield self.SelectionNumber
        if self.SelectionMetadata:
            yield self.SelectionMetadata
        if self.SelectionChildMixin:
            yield self.SelectionChildMixin


class SourcebankRef(core.QTIElement):

    """Identifies the objectbank to which the selection and ordering rules are
    to be applied. This objectbank may or may not be contained in the same
    <questestinterop> package::

    <!ELEMENT sourcebank_ref (#PCDATA)>"""
    XMLNAME = 'sourcebank_ref'
    XMLCONTENT = xml.XMLMixedContent


class SelectionNumber(core.QTIElement):

    """This element defines the partial selection rule i.e. chose 'x' objects
    from the set of objects contained in the identified object or parent
    object.
    This data is an integer number in the range 1-4096::

    <!ELEMENT selection_number (#PCDATA)>"""
    XMLNAME = 'selection_number'
    XMLCONTENT = xml.XMLMixedContent


class SelectionChildMixin:

    """Mix-in class to identify one of the following::

    (and_selection | or_selection | not_selection | selection_extension)"""
    pass


class SelectionOperator(core.QTIElement):

    """Abstract class to identify selection operators::

    (selection_metadata | and_selection | or_selection | not_selection)"""
    pass


class SelectionMetadata(SelectionOperator):

    """This element defines the rule that is applied to the IMS QTI-specific
    meta-data and/or IMS Meta-data fields of the object. The content contains
    the value of the meta-data field that is being tested for within the rule.
    This data is a string of up to 64 characters length::

    <!ELEMENT selection_metadata (#PCDATA)>
    <!ATTLIST selection_metadata
            mdname CDATA  #REQUIRED
            mdoperator  (EQ | NEQ | LT | LTE | GT | GTE )  #REQUIRED >"""
    XMLNAME = 'selection_metadata'
    XMLATTR_mdname = 'mdName'
    XMLATTR_mdoperator = (
        'mdOperator',
        core.MDOperator.from_str_lower,
        core.MDOperator.to_str)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.mdname = None
        self.mdoperator = None


class OrSelection(SelectionOperator, SelectionChildMixin):

    """The <or_selection> element is used to express the selection of
    the object if at least one of the rules is found to be relevant. It
    is used to select objects that have particular metadata content or
    through the parameterized extension mechanism::

    <!ELEMENT or_selection (selection_metadata | and_selection | or_selection |
                            not_selection)+>"""
    XMLNAME = 'or_selection'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        SelectionOperator.__init__(self, parent)
        self.SelectionOperator = []

    def get_children(self, parent):
        return iter(self.SelectionOperator)


class AndSelection(SelectionOperator, SelectionChildMixin):

    """The <and_selection> element is used to express the selection of
    the object if all of the contained rules are found to be 'True'. It
    is used to select objects that have particular metadata content or
    through the parameterized extension mechanism::

    <!ELEMENT and_selection (selection_metadata | and_selection |
                            or_selection | not_selection)+>
    """
    XMLNAME = 'and_selection'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        SelectionOperator.__init__(self, parent)
        self.SelectionOperator = []

    def get_children(self, parent):
        return iter(self.SelectionOperator)


class NotSelection(SelectionOperator, SelectionChildMixin):

    """The <not_selection> element is used to exclude the identified objects
    from selection. The object will not be selected if the contained rule is
    'True'. It is used to select objects that have particular metadata content
    or through the parameterized extension mechanism::

    <!ELEMENT not_selection (selection_metadata | and_selection |
                            or_selection | not_selection)>"""
    XMLNAME = 'not_selection'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        SelectionOperator.__init__(self, parent)
        self.SelectionOperator = None

    def get_children(self, parent):
        if self.SelectionOperator:
            yield self.SelectionOperator


class SelectionExtension(core.QTIElement, SelectionChildMixin):

    """This element allows proprietary extensions to be made to the selection
    rules. The nature of these extensions is limited to that of the 'ANY'
    definition for an element within the XML schema::

    <!ELEMENT selection_extension ANY>"""
    XMLNAME = "selection_extension"
    XMLCONTENT = xml.XMLMixedContent


class Order(core.QTIElement):

    """This element contains the ordering instructions that are to be
    applied to the objects that have been previously selected::

    <!ELEMENT order (order_extension?)>
    <!ATTLIST order  order_type CDATA  #REQUIRED >
    """
    XMLNAME = 'order'
    XMLATTR_order_type = 'orderType'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.orderType = None
        self.OrderExtension = None


class OrderExtension(core.QTIElement):

    """This element allows proprietary extensions to be made to the
    order rules. The nature of these extensions is limited to that of
    the 'ANY' definition for an element within the XML schema::

    <!ELEMENT order_extension ANY>"""
    XMLNAME = "order_extension"
    XMLCONTENT = xml.XMLMixedContent
