#! /usr/bin/env python


from . import core
from .. import html401 as html
from ..py2 import is_text
from ..xml import structures as xml


class BodyElement(core.QTIElement):

    """The root class of all content objects in the item content model is the
    bodyElement. It defines a number of attributes that are common to all
    elements of the content model::

            <xsd:attributeGroup name="bodyElement.AttrGroup">
                    <xsd:attribute name="id" type="identifier.Type"
                    use="optional"/>
                    <xsd:attribute name="class" use="optional">
                            <xsd:simpleType>
                                    <xsd:list itemType="styleclass.Type"/>
                            </xsd:simpleType>
                    </xsd:attribute>
                    <xsd:attribute ref="xml:lang"/>
                    <xsd:attribute name="label" type="string256.Type"
                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_id = ('id', core.ValidateIdentifier, lambda x: x)
    XMLATTR_class = ('style_class', None, None, list)
    XMLATTR_label = 'label'

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.id = None
        self.label = None

    def render_html(self, parent, profile, item_state):
        """Renders this element in html form, adding nodes to *parent*.  This
        method effectively overrides
        :py:class:`html401.XHTMLElement.render_html` enabling QTI and
        XHTML elements to be mixed freely.

        The state of the item (e.g., the values of any controls), is taken from
        *item_state*, a :py:class:`variables.ItemSessionState` instance."""
        raise NotImplementedError(self.__class__.__name__ + ".render_html")

    def render_html_children(self, parent, profile, item_state):
        """Renders this element's children to an external document represented
        by the *parent* node"""
        for child in self.get_children():
            if is_text(child):
                parent.add_data(child)
            else:
                child.render_html(parent, profile, item_state)


TextElements = {
    'abbr': ('id', 'class', 'label'),
    'acronym': ('id', 'class', 'label'),
    'address': ('id', 'class', 'label'),
    'blockquote': ('id', 'class', 'label'),
    'br': ('id', 'class', 'label'),
    'cite': ('id', 'class', 'label'),
    'code': ('id', 'class', 'label'),
    'dfn': ('id', 'class', 'label'),
    'div': ('id', 'class', 'label'),
    'em': ('id', 'class', 'label'),
    'h1': ('id', 'class', 'label'),
    'h2': ('id', 'class', 'label'),
    'h3': ('id', 'class', 'label'),
    'h4': ('id', 'class', 'label'),
    'h5': ('id', 'class', 'label'),
    'h6': ('id', 'class', 'label'),
    'kbd': ('id', 'class', 'label'),
    'p': ('id', 'class', 'label'),
    'pre': ('id', 'class', 'label'),
    'q': ('id', 'class', 'label'),
    'samp': ('id', 'class', 'label'),
    'span': ('id', 'class', 'label'),
    'strong': ('id', 'class', 'label'),
    'var': ('id', 'class', 'label')
}       #: Basic text formatting elements

ListElements = {
    'dl': ('id', 'class', 'label'),
    'dt': ('id', 'class', 'label'),
    'dd': ('id', 'class', 'label'),
    'ol': ('id', 'class', 'label'),
    'ul': ('id', 'class', 'label'),
    'li': ('id', 'class', 'label')
}       #: Elements required for lists


ObjectElements = {
    'object': ('id', 'class', 'label', 'data', 'type', 'width', 'height'),
    'param': ('id', 'class', 'label', 'name', 'value', 'valuetype', 'type')
}       #: The object element


PresentationElements = {
    'caption': ('id', 'class', 'label'),
    'col': ('id', 'class', 'label', 'span'),
    'colgroup': ('id', 'class', 'label', 'span'),
    'table': ('id', 'class', 'label', 'summary'),
    'tbody': ('id', 'class', 'label'),
    'tfoot': ('id', 'class', 'label'),
    'thead': ('id', 'class', 'label'),
    'tr': ('id', 'class', 'label'),
    'th': ('id', 'class', 'label', 'headers', 'scope', 'abbr', 'axis',
           'rowspan', 'colspan'),
    'td': ('id', 'class', 'label', 'headers', 'scope', 'abbr', 'axis',
           'rowspan', 'colspan')
}  #: Tables

ImageElement = {
    'img': ('id', 'class', 'label', 'src', 'alt', 'longdesc', 'height',
            'width')}  #: Images


HypertextElement = {
    'a': ('id', 'class', 'label', 'href', 'type')
}       #: Hyperlinks


HTMLProfile = {}        #: The full HTML profile defined by QTI

HTMLProfile.update(TextElements)
HTMLProfile.update(ListElements)
HTMLProfile.update(ObjectElements)
HTMLProfile.update(PresentationElements)
HTMLProfile.update(ImageElement)
HTMLProfile.update(HypertextElement)


def fix_html_namespace(e):
    """Fixes e and all children to be in the QTI namespace"""
    if e.ns == html.XHTML_NAMESPACE:
        name = e.xmlname.lower()
        if name in core.QTI_HTML_PROFILE:
            e.set_xmlname((core.IMSQTI_NAMESPACE, name))
    for e in e.get_children():
        if is_text(e):
            continue
        fix_html_namespace(e)


class ItemBody(BodyElement):

    """The item body contains the text, graphics, media objects, and
    interactions that describe the item's content and information about how it
    is structured::

            <xsd:attributeGroup name="itemBody.AttrGroup">
                    <xsd:attributeGroup ref="bodyElement.AttrGroup"/>
            </xsd:attributeGroup>

            <xsd:group name="itemBody.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="block.ElementGroup" minOccurs="0"
                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'itemBody')
    XMLCONTENT = xml.ElementContent

    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.BlockMixin):
            return BodyElement.add_child(self, child_class, name)
        else:
            raise core.QTIValidityError(
                "%s (%s) in %s" %
                (repr(name),
                 child_class.__name__,
                 self.__class__.__name__))

    def render_html(self, parent, profile, item_state):
        """Overrides :py:meth:`BodyElement.render_html`, the result is always a
        Div with class set to "itemBody".  Unlike other such method *parent*
        may by None, in which case a new parentless Div is created."""
        if parent:
            html_div = parent.add_child(html.Div)
        else:
            html_div = html.Div(None)
        html_div.style_class = ["itemBody"]
        self.render_html_children(html_div, profile, item_state)


class FlowContainerMixin(object):

    """Mixin class used for objects that can contain flows."""

    def pretty_print(self):
        """True if this object should be pretty printed.

        This is similar to the algorithm we use in HTML flow containers,
        suppressing pretty printing if we have inline elements (ignoring
        non-trivial data).  This could be refactored in future."""
        for child in self.get_children():
            if is_text(child):
                for c in child:
                    if not xml.is_s(c):
                        return False
            elif isinstance(child, html.InlineMixin):
                return False
        return True


class RubricBlock(html.BlockMixin, BodyElement):

    """Represent the rubricBlock element.

    <xsd:attributeGroup name="rubricBlock.AttrGroup">
            <xsd:attributeGroup ref="simpleBlock.AttrGroup"/>
            <xsd:attribute name="view" use="required">
                    <xsd:simpleType>
                            <xsd:list itemType="view.Type"/>
                    </xsd:simpleType>
            </xsd:attribute>
    </xsd:attributeGroup>

    <xsd:group name="rubricBlock.ContentGroup">
            <xsd:sequence>
                    <xsd:group ref="simpleBlock.ContentGroup"/>
            </xsd:sequence>
    </xsd:group>
    """
    XMLNAME = (core.IMSQTI_NAMESPACE, 'rubricBlock')
    XMLATTR_view = (
        'view', core.View.from_str_lower, core.View.to_str, dict)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        BodyElement.__init__(self, parent)
        self.view = {}

    def add_view(self, view):
        if is_text(view):
            view = core.View.from_str_lower(view.strip())
        view_value = core.View.to_str(view)
        if view_value:
            self.view[view] = view_value
        else:
            raise ValueError("illegal value for view: %s" % view)

    # need to constrain content to html.BlockMixin
    def add_child(self, child_class, name=None):
        if issubclass(child_class, html.BlockMixin):
            return BodyElement.add_child(self, child_class, name)
        else:
            # This child cannot go in here
            raise core.QTIValidityError(
                "%s in %s" % (repr(name), self.__class__.__name__))
