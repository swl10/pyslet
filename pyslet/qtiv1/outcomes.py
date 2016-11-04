#! /usr/bin/env python

import itertools

from . import common
from . import core
from . import item
from ..xml import structures as xml


class OutcomesProcessing(common.QTICommentContainer):

    """The <outcomes_processing> element is the container for all of the
    outcomes processing instructions for Assessments and Sections. Multiple
    outcomes processing containers can be use when multiple scoring algorithms
    are to be applied to produce the aggregated outcomes. If multiple
    outcomes_processing elements are supplied, it is the intention that all
    should be run and the outcomes from all of them together should be reported
    as the outcomes of the enclosing Section or Assessment. The outcome
    variables defined by each <outcomes_processing> element should be unique
    across all outcomes_processing elements defined by a section. In
    particular, it is an error for multiple <outcomes_processing> elements to
    set the same outcome variable and the results will be undefined::

    <!ELEMENT outcomes_processing (qticomment? , outcomes ,
            objects_condition* , processing_parameter* , map_output* ,
            outcomes_feedback_test*)>
    <!ATTLIST outcomes_processing  scoremodel CDATA  #IMPLIED >"""
    XMLNAME = "outcomes_processing"
    XMLATTR_scoremodel = 'scoreModel'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.scoreModel = None
        self.Outcomes = item.Outcomes(self)
        self.ObjectsCondition = []
        self.ProcessingParameter = []
        self.MapOutput = []
        self.OutcomesFeedbackTest = []

    def get_children(self):
        for child in common.QTICommentContainer.get_children():
            yield child
        yield self.Outcomes
        for child in itertools.chain(
                self.ObjectsCondition,
                self.ProcessingParameter,
                self.MapOutput,
                self.OutcomesFeedbackTest):
            yield child


class ProcessingParameter(core.QTIElement):

    """This element contains the value of a particular parameter that is to be
    used by the corresponding scoring algorithm. Each parameter has a
    particular meaning to each scoring algorithm i.e. there is no established
    vocabulary for these parameters::

    <!ELEMENT processing_parameter (#PCDATA)>
    <!ATTLIST processing_parameter  pname CDATA  #REQUIRED >"""
    XMLNAME = 'processing_parameter'
    XMLATTR_pname = 'pName'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.pName = None


class MapOutput(core.QTIElement):

    """This element is used to re-map the named variable to another named
    variable (given in the body of the element). The target variable name must
    have been declared using <decvar> in the <outcomes> element of the
    enclosing <outcomes_processing> element. When a variable is remapped, all
    of its derived variables are to be remapped as well. Thus if remapping
    'SCORE' to 'myScore', 'SCORE.min', 'SCORE.max' and 'SCORE.normalized'
    would be remapped to 'myScore.min', 'myScore.max' and 'myScore.normalized'
    respectively.
    Data-type = string (1-256 chars)::

    <!ELEMENT map_output (#PCDATA)>
    <!ATTLIST map_output  varname CDATA  'SCORE' >"""
    XMLNAME = 'map_output'
    XMLATTR_varname = 'varName'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.varName = None


class ObjectsCondition(common.QTICommentContainer):

    """Each <objects_condition> element defines a subset of the objects (Items
    and Sections) selected by the selection algorithm that are to be used in
    this score. This allows for the construction of subscores. If no
    <outcomes_metadata> element is present within the <objects_conditions>
    element to select a subset of objects, then the <objects_conditions>
    applies to all objects selected by the selection algorithm. If multiple
    <objects_conditions> are given within a single <outcomes_processing>
    element, then the algorithm is applied to the union of all objects
    selected.
    The <objects_parameter>, <map_input> and <objectscond_extension> elements
    within the <objects_condition> element apply only to those objects selected
    in the condition. If an object is selected by more than one
    <objects_condition> element, it should receive parameter assignments and
    input mapping as if it were the first element so selected. These conditions
    include the identification and mapping of the variables for input::

    <!ELEMENT objects_condition (qticomment? ,
            (outcomes_metadata | and_objects | or_objects | not_objects)? ,
            objects_parameter* , map_input* , objectscond_extension?)>"""
    XMLNAME = 'objects_condition'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.OutcomesOperator = None
        self.ObjectsParameter = []
        self.MapInput = []
        self.ObjectsCondExtension = None

    def get_children(self):
        for child in common.QTICommentContainer.get_children(self):
            yield child
        if self.OutcomesOperator:
            yield self.OutcomesOperator
        for child in itertools.chain(
                self.ObjectsParameter, self.MapInput):
            yield child
        if self.ObjectsCondExtension:
            yield self.ObjectsCondExtension


class ObjectsParameter(core.QTIElement):

    """This element contains the value of a particular parameter that is to be
    used by the corresponding scoring algorithm variable selection. Each
    parameter has a particular meaning to each scoring algorithm i.e. there is
    no established vocabulary for these parameters. These parameters are
    applied only to the objects selected by the enclosing <outcomes_condition>
    element.
    If multiple <outomes_condition> select the same object, the parameters are
    taken from the first <outcomes_condition> that selects the element::

    <!ELEMENT objects_parameter (#PCDATA)>
    <!ATTLIST objects_parameter  pname CDATA  #REQUIRED >"""
    XMLNAME = 'objects_parameter'
    XMLATTR_pname = 'pName'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.pName = None


class MapInput(core.QTIElement):

    """This element is used to re-map the named input variable to another
    variable. The default variable names are derived from the type of scoring
    algorithm identified in <outcomes_processing> element. The target variable
    name must have been declared in the evaluation objects that undergoing
    aggregation and must be of the same type as the default variable. When a
    variable is remapped, all of its derived variables are to be remapped as
    well. The input mapping is applied only to the objects selected by the
    enclosing <outcomes_condition> element. If multiple <outcomes_condition>
    select the same object, the input mapping used is the one contained in the
    first <outcomes_condition> that selects the element::

    <!ELEMENT map_input (#PCDATA)>
    <!ATTLIST map_input  varname CDATA  'SCORE' >"""
    XMLNAME = 'map_input'
    XMLATTR_varname = 'varName'
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.varName = None


class ObjectsCondExtension(core.QTIElement):

    """This element contains the proprietary extensions that can be used to
    extend the functionally capabilities of the <outcomes_condition> element::

    <!ELEMENT objectscond_extension (#PCDATA)>"""
    XMLNAME = "objectscond_extension"
    XMLCONTENT = xml.XMLMixedContent


class OutcomesFeedbackTest(core.QTIElement):

    """The <outcomes_feedback> element contains the tests to be applied to
    determine if any and the type of feedback to be presented. This feedback
    could include information about passing the assessment etc::

    <!ELEMENT outcomes_feedback_test (test_variable , displayfeedback+)>
    <!ATTLIST outcomes_feedback_test  title CDATA  #IMPLIED >"""
    XMLNAME = 'outcomes_feedback_test'
    XMLATTR_title = 'title'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.title = None
        self.TestVariable = TestVariable(self)
        self.DisplayFeedback = []

    def get_children(self):
        yield self.TestVariable
        for child in self.DisplayFeedback:
            yield child


class OutcomesOperator(core.QTIElement):

    """Abstract class for::

    (outcomes_metadata | and_objects | or_objects | not_objects)"""
    pass


class OutcomesMetadata(OutcomesOperator):

    """This element defines the rule that is applied to the IMS QTI-specific
    and/or IMS Meta-data fields of the object to decide if the object scoring
    is to be aggregated. The content contains the value of the meta-data field
    that is being tested for within the rule. Data-type = String (1-64 chars)::

    <!ELEMENT outcomes_metadata (#PCDATA)>
    <!ATTLIST outcomes_metadata
            mdname CDATA  #REQUIRED
            mdoperator  (EQ | NEQ | LT | LTE | GT | GTE )  #REQUIRED >"""
    XMLNAME = 'outcomes_metadata'
    XMLATTR_mdname = 'mdName'
    XMLATTR_mdoperator = (
        'mdOperator',
        core.MDOperator.from_str_lower,
        core.MDOperator.to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesOperator.__init__(self, parent)
        self.mdname = None
        self.mdoperator = None


class AndObjects(OutcomesOperator):

    """The <and_objects> element supports the construction of complex score
    condition rules to be built based upon the logical 'AND' operator. The
    object is selected for aggregation if all of the contained rules are
    'True'::

    <!ELEMENT and_objects (outcomes_metadata | and_objects | or_objects |
    not_objects)+>"""
    XMLNAME = 'and_objects'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesOperator.__init__(self, parent)
        self.OutcomesOperator = []

    def get_children(self):
        return iter(self.OutcomesOperator)


class OrObjects(OutcomesOperator):

    """The <or_objects> element supports the construction of complex score
    condition rules to be built based upon the logical 'OR' operator. The
    object is selected for aggregation if at least one of the contained rules
    is 'True'::

    <!ELEMENT or_objects (outcomes_metadata | and_objects | or_objects |
    not_objects)+>"""
    XMLNAME = 'or_objects'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesOperator.__init__(self, parent)
        self.OutcomesOperator = []

    def get_children(self):
        return iter(self.OutcomesOperator)


class NotObjects(OutcomesOperator):

    """The <not_objects> element supports the construction of complex rules to
    be built based upon the logical 'NOT' operator. The object is selected for
    aggregation if the contained rule(s) is 'False'::

    <!ELEMENT not_objects (outcomes_metadata | and_objects | or_objects |
    not_objects)>
    """
    XMLNAME = 'not_objects'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesOperator.__init__(self, parent)
        self.OutcomesOperator = None

    def get_children(self):
        if self.OutcomesOperator:
            yield self.OutcomesOperator


class TestVariable(core.QTIElement):

    """The <test_variable> element contains the conditions that are applied to a
    defined set of input scoring variables to determine if feedback is to be
    presented. Complex test structures can be constructed using the associated
    logic elements::

    <!ELEMENT test_variable (variable_test | and_test | or_test | not_test)>"""
    XMLNAME = 'test_variable'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.OutcomesTest = None

    def get_children(self):
        if self.OutcomesTest:
            yield self.OutcomesTest


class OutcomesTest(core.QTIElement):

    """Abstract class for::

    (variable_test | and_test | or_test | not_test)"""
    pass


class VariableTest(OutcomesTest):

    """The conditional test that is to be applied to the aggregated score
    variables. A wide range of separate and combinatorial tests can be
    applied::

    <!ELEMENT variable_test (#PCDATA)>
    <!ATTLIST variable_test
            varname CDATA  'SCORE'
            testoperator  (EQ | NEQ | LT | LTE | GT | GTE )  #REQUIRED >"""
    XMLNAME = 'variable_test'
    XMLATTR_varname = 'varName'
    XMLATTR_testoperator = (
        'testOperator',
        core.TestOperator.from_str_lower,
        core.TestOperator.to_str)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        OutcomesTest.__init__(self, parent)
        self.varName = None
        self.testOperator = None


class AndTest(OutcomesTest):

    """The <and_test> element is used to define variable test conditions all of
    which must be defined as 'True' to result in the output variables being
    assigned the corresponding values::

    <!ELEMENT and_test (variable_test | and_test | or_test | not_test)+>"""
    XMLNAME = 'and_test'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesTest.__init__(self, parent)
        self.OutcomesTest = []


class OrTest(OutcomesTest):

    """The <or_test> element is used to define variable test conditions at least
    one of which must be defined as 'True' to result in the output variables
    being assigned the corresponding values::

    <!ELEMENT or_test (variable_test | and_test | or_test | not_test)+>"""
    XMLNAME = 'or_test'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesTest.__init__(self, parent)
        self.OutcomesTest = []


class NotTest(OutcomesTest):

    """The <not_test> element is used to define variable test conditions that
    result in the condition being defined as 'False' to result in the output
    variables being assigned the corresponding values::

    <!ELEMENT not_test (variable_test | and_test | or_test | not_test)>"""
    XMLNAME = 'not_test'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        OutcomesTest.__init__(self, parent)
        self.OutcomesTest = None
