#! /usr/bin/env python

import itertools
import logging

from . import core
from . import variables
from ..pep8 import old_method
from ..xml import structures as xml


class ResponseProcessing(core.QTIElement):

    """Response processing is the process by which the Delivery Engine assigns
    outcomes based on the candidate's responses::

            <xsd:attributeGroup name="responseProcessing.AttrGroup">
                    <xsd:attribute name="template" type="uri.Type"
                                    use="optional"/>
                    <xsd:attribute name="templateLocation" type="uri.Type"
                                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="responseProcessing.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="responseRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseProcessing')
    XMLATTR_template = 'template'
    XMLATTR_templateLocation = 'templateLocation'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.template = None
        self.templateLocation = None
        self.ResponseRule = []

    def get_children(self):
        return itertools.chain(
            self.ResponseRule,
            core.QTIElement.get_children(self))

    @old_method('Run')
    def run(self, state):
        """Runs response processing using the values in *state*.

        *	*state* is an :py:class:`~pyslet.qtiv2.variables.ItemSessionState`
                instance."""
        try:
            for r in self.ResponseRule:
                if r.Run(state):
                    break
        except StopProcessing:
            # raised by exitResponse
            pass


class ResponseRule(core.QTIElement):

    """Abstract class to represent all response rules."""

    @old_method('Run')
    def run(self, state):
        """Abstract method to run this rule using the values in *state*."""
        raise NotImplementedError(
            "Unsupported response rule: <%s>" % repr(self.xmlname))


class ResponseCondition(ResponseRule):

    """If the expression given in a responseIf or responseElseIf evaluates to
    true then the sub-rules contained within it are followed and any following
    responseElseIf or responseElse parts are ignored for this response
    condition::

            <xsd:group name="responseCondition.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="responseIf" minOccurs="1"
                                            maxOccurs="1"/>
                            <xsd:element ref="responseElseIf" minOccurs="0"
                                            maxOccurs="unbounded"/>
                            <xsd:element ref="responseElse" minOccurs="0"
                                            maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseCondition')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        ResponseRule.__init__(self, parent)
        self.ResponseIf = ResponseIf(self)
        self.ResponseElseIf = []
        self.ResponseElse = None

    def get_children(self):
        if self.ResponseIf:
            yield self.ResponseIf
        for child in self.ResponseElseIf:
            yield child
        if self.ResponseElse:
            yield self.ResponseElse

    def run(self, state):
        if self.ResponseIf.Run(state):
            return
        for c in self.ResponseElseIf:
            if c.Run(state):
                return
        if self.ResponseElse:
            self.ResponseElse.Run(state)


class ResponseIf(core.QTIElement):

    """A responseIf part consists of an expression which must have an effective
    baseType of boolean and single cardinality. If the expression is true then
    the sub-rules are processed, otherwise they are skipped (including if the
    expression is NULL)::

            <xsd:group name="responseIf.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                            <xsd:group ref="responseRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseIf')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.Expression = None
        self.ResponseRule = []

    def get_children(self):
        if self.Expression:
            yield self.Expression
        for child in self.ResponseRule:
            yield child

    @old_method('Run')
    def run(self, state):
        """Run this test and, if True, any resulting rules.

        Returns *True* if the condition evaluated to *True*."""
        if self.Expression is None:
            raise core.ProcessingError("responseIf with missing condition")
        value = self.Expression.Evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.boolean)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value and value.value:
            for r in self.ResponseRule:
                r.Run(state)
            return True
        else:
            return False


class ResponseElse(core.QTIElement):

    """Represents the responseElse element, see :py:class:`ResponseCondition`
    ::

            <xsd:group name="responseElse.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="responseRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseElse')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.ResponseRule = []

    def get_children(self):
        return iter(self.ResponseRule)

    @old_method('Run')
    def run(self, state):
        """Runs the sub-rules."""
        for r in self.ResponseRule:
            r.Run(state)


class ResponseElseIf(ResponseIf):

    """Represents the responseElse element, see :py:class:`ResponseIf`
    ::

            <xsd:group name="responseElseIf.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                            <xsd:group ref="responseRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseElseIf')


class SetOutcomeValue(ResponseRule):

    """The setOutcomeValue rule sets the value of an outcome variable to the
    value obtained from the associated expression::

            <xsd:attributeGroup name="setOutcomeValue.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="setOutcomeValue.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'setOutcomeValue')
    XMLATTR_identifier = 'identifier'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        ResponseRule.__init__(self, parent)
        self.identifier = ''
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression

    def run(self, state):
        if self.Expression is None:
            raise core.ProcessingError(
                "setOutcomeValue with missing expression")
        value = self.Expression.Evaluate(state)
        if state.IsOutcome(self.identifier):
            state[self.identifier] = value
        else:
            raise core.ProcessingError(
                "Outcome variable required: %s" % self.identifier)


class StopProcessing(core.QTIError):

    """Raised when a rule which stops processing is encountered."""
    pass


class ExitResponse(ResponseRule):

    """The exit response rule terminates response processing immediately (for
    this invocation).  It does this by raising :py:class:`StopProcessing`::

            <xsd:complexType name="exitResponse.Type"/>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'exitResponse')
    XMLCONTENT = xml.XMLEmpty

    def run(self, state):
        raise StopProcessing


class TemplateProcessing(core.QTIElement):

    """Template processing consists of one or more templateRules that are
    followed by the cloning engine or delivery system in order to assign values
    to the template variables::

            <xsd:group name="templateProcessing.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="templateRule.ElementGroup"
                                        minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>

            <xsd:complexType name="templateProcessing.Type" mixed="false">
                    <xsd:group ref="templateProcessing.ContentGroup"/>
            </xsd:complexType>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateProcessing')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.TemplateRule = []

    def get_children(self):
        return itertools.chain(
            self.TemplateRule,
            core.QTIElement.get_children(self))

    @old_method('Run')
    def run(self, state):
        """Runs template processing rules using the values in *state*.

        *	*state* is an :py:class:`~pyslet.qtiv2.variables.ItemSessionState`
                instance."""
        try:
            for r in self.TemplateRule:
                if r.Run(state):
                    break
        except StopProcessing:
            # raised by exitTemplate
            pass


class TemplateRule(core.QTIElement):

    """Abstract class to represent all template rules."""

    @old_method('Run')
    def run(self, state):
        """Abstract method to run this rule using the values in *state*."""
        raise NotImplementedError(
            "Unsupported template rule: <%s>" % repr(self.xmlname))


class TemplateCondition(TemplateRule):

    """If the expression given in the templateIf or templateElseIf evaluates to
    true then the sub-rules contained within it are followed and any following
    templateElseIf or templateElse parts are ignored for this template
    condition::

            <xsd:group name="templateCondition.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="templateIf" minOccurs="1"
                                            maxOccurs="1"/>
                            <xsd:element ref="templateElseIf" minOccurs="0"
                                            maxOccurs="unbounded"/>
                            <xsd:element ref="templateElse" minOccurs="0"
                                            maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateCondition')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        TemplateRule.__init__(self, parent)
        self.TemplateIf = TemplateIf(self)
        self.TemplateElseIf = []
        self.TemplateElse = None

    def get_children(self):
        if self.TemplateIf:
            yield self.TemplateIf
        for child in self.TemplateElseIf:
            yield child
        if self.TemplateElse:
            yield self.TemplateElse

    def run(self, state):
        if self.TemplateIf.Run(state):
            return
        for c in self.TemplateElseIf:
            if c.Run(state):
                return
        if self.TemplateElse:
            self.TemplateElse.Run(state)


class TemplateIf(core.QTIElement):

    """A templateIf part consists of an expression which must have an effective
    baseType of boolean and single cardinality. If the expression is true then
    the sub-rules are processed, otherwise they are skipped (including if the
    expression is NULL)::

            <xsd:group name="templateIf.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                            <xsd:group ref="templateRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateIf')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.Expression = None
        self.TemplateRule = []

    def get_children(self):
        if self.Expression:
            yield self.Expression
        for child in self.TemplateRule:
            yield child

    @old_method('Run')
    def run(self, state):
        """Run this test and, if True, any resulting rules.

        Returns *True* if the condition evaluated to *True*."""
        if self.Expression is None:
            raise core.ProcessingError("templateIf with missing condition")
        value = self.Expression.Evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.boolean)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        if value and value.value:
            for r in self.TemplateRule:
                r.Run(state)
            return True
        else:
            return False


class TemplateElse(core.QTIElement):

    """Represents the templateElse element, see :py:class:`TemplateCondition`
    ::

            <xsd:group name="templateElse.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="templateRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateElse')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.TemplateRule = []

    def get_children(self):
        return iter(self.TemplateRule)

    @old_method('Run')
    def run(self, state):
        """Runs the sub-rules."""
        for r in self.TemplateRule:
            r.Run(state)


class TemplateElseIf(TemplateIf):

    """Represents the templateElse element, see :py:class:`templateIf`
    ::

            <xsd:group name="templateElseIf.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                            <xsd:group ref="templateRule.ElementGroup"
                                        minOccurs="0" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateElseIf')


class SetTemplateValue(TemplateRule):

    """The setTemplateValue rule sets the value of a template variable to the
    value obtained from the associated expression::

            <xsd:attributeGroup name="setTemplateValue.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="setTemplateValue.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'setTemplateValue')
    XMLATTR_identifier = 'identifier'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        TemplateRule.__init__(self, parent)
        self.identifier = ''
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression

    def run(self, state):
        if self.Expression is None:
            raise core.ProcessingError(
                "setTemplateValue with missing expression")
        value = self.Expression.Evaluate(state)
        if state.IsTemplate(self.identifier):
            state[self.identifier] = value
        else:
            raise core.ProcessingError(
                "Template variable required: %s" % self.identifier)


class SetCorrectResponse(TemplateRule):

    """The setCorrectResponse rule sets the correct value of a response
    variable to the value obtained from the associated expression::

            <xsd:attributeGroup name="setCorrectResponse.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="setCorrectResponse.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'setCorrectResponse')
    XMLATTR_identifier = 'identifier'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        TemplateRule.__init__(self, parent)
        self.identifier = ''
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression

    def run(self, state):
        if self.Expression is None:
            raise core.ProcessingError(
                "setCorrectResponse with missing expression")
        value = self.Expression.Evaluate(state)
        d = state.GetDeclaration(self.identifier)
        if isinstance(d, variables.ResponseDeclaration):
            state[self.identifier + ".CORRECT"] = value
        elif state.IsResponse(self.identifier):
            raise core.ProcessingError(
                "Can't set the correct value of a built-in response %s" %
                self.identifier)
        else:
            raise core.ProcessingError(
                "%s is not a response variable" % self.identifier)


class SetDefaultValue(TemplateRule):

    """The setDefaultValue rule sets the default value of a response or outcome
    variable to the value obtained from the associated expression::

            <xsd:attributeGroup name="setDefaultValue.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="setDefaultValue.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'setDefaultValue')
    XMLATTR_identifier = 'identifier'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        TemplateRule.__init__(self, parent)
        self.identifier = ''
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression

    def run(self, state):
        if self.Expression is None:
            raise core.ProcessingError(
                "setDefaultValue with missing expression")
        value = self.Expression.Evaluate(state)
        d = state.GetDeclaration(self.identifier)
        if (isinstance(d, variables.ResponseDeclaration) or
                isinstance(d, variables.OutcomeDeclaration)):
            state[self.identifier + ".DEFAULT"] = value
        elif (state.IsResponse(self.identifier) or
              state.IsOutcome(self.identifier)):
            raise core.ProcessingError(
                "Can't set the correct value of a built-in variable %s" %
                self.identifier)
        else:
            raise core.ProcessingError(
                "%s is not a response or outcome variable" % self.identifier)


class ExitTemplate(TemplateRule):

    """The exit template rule terminates template processing immediately.  It
    does this by raising :py:class:`StopProcessing`::

            <xsd:complexType name="exitTemplate.Type"/>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'exitTemplate')
    XMLCONTENT = xml.XMLEmpty

    def run(self, state):
        raise StopProcessing


class TestPartCondition(core.QTIElement):

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression
        for child in core.QTIElement.get_children(self):
            yield child

    @old_method('Evaluate')
    def evaluate(self, state):
        """Evaluates the condition using the values in *state*.

        *	*state* is a :py:class:`~pyslet.qtiv2.variables.TestSessionState`
                instance."""
        if self.Expression is None:
            raise core.ProcessingError(
                "preCondition or branchRule with missing condition")
        value = self.Expression.Evaluate(state)
        variables.check_base_types(value.baseType, variables.BaseType.boolean)
        variables.check_cardinalities(
            value.Cardinality(), variables.Cardinality.single)
        return value and value.value


class PreCondition(TestPartCondition):

    """A preCondition is a simple expression attached to an assessmentSection or
    assessmentItemRef that must evaluate to true if the item is to be
    presented::

            <xsd:group name="preCondition.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'preCondition')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        TestPartCondition.__init__(self, parent)


class BranchRule(TestPartCondition):

    """A branch-rule is a simple expression attached to an assessmentItemRef,
    assessmentSection or testPart that is evaluated after the item, section, or
    part has been presented to the candidate::

            <xsd:attributeGroup name="branchRule.AttrGroup">
                    <xsd:attribute name="target" type="identifier.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="branchRule.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'branchRule')
    XMLATTR_target = 'target'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        TestPartCondition.__init__(self, parent)
        self.target = None


class TemplateDefault(core.QTIElement):

    """Overrides the default value of a template variable based on the test
    context in which the template is instantiated::

            <xsd:attributeGroup name="templateDefault.AttrGroup">
                    <xsd:attribute name="templateIdentifier"
                                    type="identifier.Type" use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="templateDefault.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="expression.ElementGroup"
                                        minOccurs="1" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateDefault')
    XMLATTR_templateIdentifier = 'templateIdentifier'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.templateIdentifier = None
        self.Expression = None

    def get_children(self):
        if self.Expression:
            yield self.Expression
        for child in core.QTIElement.get_children(self):
            yield child

    @old_method('Run')
    def run(self, item_state, test_state):
        """Updates the value of a template variable in *item_state* based on the
        values in *test_state*."""
        if self.Expression is None:
            raise core.ProcessingError(
                "templateDefault with missing expression")
        value = self.Expression.Evaluate(test_state)
        if self.templateIdentifier is None:
            logging.debug("TemplateDefault.run: %s", self)
        try:
            d = item_state.GetDeclaration(self.templateIdentifier)
        except KeyError:
            raise core.ProcessingError(
                "%s is not a variable" % self.templateIdentifier)
        if isinstance(d, variables.TemplateDeclaration):
            # we don't actually use the .DEFAULT form for template variables as
            # they have their values set directly.
            item_state[self.templateIdentifier] = value
        else:
            raise core.ProcessingError(
                "%s is not a template variable" % self.templateIdentifier)
