#! /usr/bin/env python
"""This module implements the Atom 1.0 specification defined in RFC 4287

References:

IRIs [RFC3987]; cf URI [RFC3986]
(1) when an IRI that is not also a URI is given for dereferencing,
it MUST be mapped to a URI using the steps in Section 3.1 of [RFC3987]
(2) when an IRI is serving as an atom:id value, it MUST NOT be so mapped,
so that the comparison works as described in Section 4.2.6.1.

xml:base attribute [W3C.REC-xmlbase-20010627]
xml:lang attribute [W3C.REC-xml-20040204], Section 2.12

A Date construct is an element whose content MUST conform to the
"date-time" production in [RFC3339]
"""

import itertools

from . import html401 as html
from . import info
from . import iso8601
from . import rfc2396 as uri
from .pep8 import old_function
from .py2 import is_text, to_text
from .xml import structures as xml
from .xml import namespace as xmlns
from .xml import xsdatatypes as xsi


#: The namespace to use for Atom Document elements
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"

#: The mime type for Atom Document
ATOM_MIMETYPE = "application/atom+xml"

_ATOM_TEXT_TYPES = {'text': 1, 'html': 1, 'xhtml': 1}


class AtomElement(xmlns.XMLNSElement):

    """Base class for all APP elements.

    All atom elements can have xml:base and xml:lang attributes, these are
    handled by the :py:class:`~pyslet.xml.structures.Element` base
    class.

    See :py:meth:`~pyslet.xml.structures.Element.GetLang` and
    :py:meth:`~pyslet.xml.structures.Element.SetLang`,
    :py:meth:`~pyslet.xml.structures.Element.GetBase` and
    :py:meth:`~pyslet.xml.structures.Element.SetBase`"""
    pass


class TextType(xsi.Enumeration):

    """text type enumeration::

             "text" | "html" | "xhtml"

    This enumeration is used for setting the :py:attr:`Text.type` attribute.

    Usage: TextType.text, TextType.html, TextType.xhtml"""
    decode = {
        'text': 1,
        'html': 2,
        'xhtml': 3
    }


class Text(AtomElement):

    """Base class for atomPlainTextConstruct and atomXHTMLTextConstruct."""

    XMLATTR_type = ('type', TextType.from_str_lower, TextType.to_str)

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        self.type = TextType.text

    def set_value(self, value, type=TextType.text):
        """Sets the value of the element.  *type* must be a value from
        the :py:class:`TextType` enumeration

        Overloads the basic
        :py:meth:`~pyslet.xml.structures.Element.SetValue`
        implementation, adding an additional *type* attribute to enable
        the value to be set to either a plain TextType.text,
        TextType.html or TextType.xhtml value.  In the case of an xhtml
        type, *value* is parsed for the required XHTML div element and
        this becomes the only child of the element.  Given that the div
        itself is not considered to be part of the content the value can
        be given without the enclosing div, in which case it is
        generated automatically."""
        if type == TextType.text or type == TextType.html:
            AtomElement.set_value(self, value)
            self.type = type
        elif type == TextType.xhtml:
            e = xml.XMLEntity(value)
            doc = html.XHTMLDocument(base_uri=self.resolve_base())
            doc.read_from_entity(e)
            div = list(doc.root.Body.get_children())
            if len(div) == 1 and isinstance(div[0], html.Div):
                div = div[0]
                # We remove our existing content
                self.set_value(None)
                # And do a deep copy of the div instead
                new_div = div.deepcopy(self)
            else:
                new_div = self.add_child(html.Div)
                for divChild in div:
                    if isinstance(divChild, xml.Element):
                        divChild.deepcopy(new_div)
                    else:
                        new_div.add_data(divChild)
            new_div.make_prefix(html.XHTML_NAMESPACE, '')
            self.type = type
        else:
            raise ValueError(
                "Expected text or html identifiers, found %s" % str(type))

    def get_value(self):
        """Gets a single unicode string representing the value of the element.

        Overloads the basic
        :py:meth:`~pyslet.xml.structures.Element.get_value`
        implementation to add support for text of type xhtml.

        When getting the value of TextType.xhtml text the child div element is
        not returned as it is not considered to be part of the content."""
        if self.type == TextType.text or self.type == TextType.html:
            return AtomElement.get_value(self)
        elif self.type == TextType.xhtml:
            # concatenate all children, but should be just a single div
            result = []
            value_children = list(self.get_children())
            if len(value_children) and isinstance(value_children[0], html.Div):
                value_children = list(value_children[0].get_children())
            for c in value_children:
                result.append(to_text(c))
            return ''.join(result)
        else:
            raise ValueError("Unknown text type: %s" % str(self.type))


class AtomId(AtomElement):

    """A permanent, universally unique identifier for an entry or feed."""
    XMLNAME = (ATOM_NAMESPACE, 'id')


class Name(AtomElement):

    """A human-readable name for a person."""
    XMLNAME = (ATOM_NAMESPACE, 'name')


class Title(Text):

    """A :py:class:`Text` construct that conveys a human-readable title
    for an entry or feed."""
    XMLNAME = (ATOM_NAMESPACE, 'title')


class Subtitle(Text):

    """A :py:class:`Text` construct that conveys a human-readable
    description or subtitle for a feed."""
    XMLNAME = (ATOM_NAMESPACE, 'subtitle')


class Summary(Text):

    """A :py:class:`Text` construct that conveys a short summary,
    abstract, or excerpt of an entry."""
    XMLNAME = (ATOM_NAMESPACE, 'summary')


class Rights(Text):

    """A Text construct that conveys information about rights held in
    and over an entry or feed."""
    XMLNAME = (ATOM_NAMESPACE, 'rights')


class Date(AtomElement):

    """An element conforming to the definition of date-time in RFC3339.

    This class is modeled using the iso8601 module."""

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        #: a :py:class:`~pyslet.iso8601.TimePoint` instance representing
        #: this date
        self.date = iso8601.TimePoint()

    def get_value(self):
        """Overrides
        :py:meth:`~pyslet.xml.structures.Element.get_value`, returning a
        :py:class:`pyslet.iso8601.TimePoint` instance."""
        return self.date

    def set_value(self, value):
        """Overrides :py:meth:`~pyslet.xml.structures.Element.SetValue`,
        enabling the value to be set from a
        :py:class:`pyslet.iso8601.TimePoint` instance.

        If *value* is a string the behaviour is unchanged, if *value* is
        a TimePoint instance then it is formatted using the extended
        format of ISO 8601 in accordance with the requirements of the
        Atom specification."""
        if isinstance(value, iso8601.TimePoint):
            self.date = value
            super(Date, self).set_value(value.get_calendar_string())
        else:
            super(Date, self).set_value(value)
            self.content_changed()

    def content_changed(self):
        """Re-reads the value of the element and sets :py:attr:`date`
        accordingly."""
        self.date = iso8601.TimePoint.from_str(AtomElement.get_value(self))


class Updated(Date):

    """A Date construct indicating the most recent instant in time when
    an entry or feed was modified in a way the publisher considers
    significant."""
    XMLNAME = (ATOM_NAMESPACE, 'updated')


class Published(Date):

    """A Date construct indicating an instant in time associated with an
    event early in the life cycle of the entry."""
    XMLNAME = (ATOM_NAMESPACE, "published")


class Link(AtomElement):

    """A reference from an entry or feed to a Web resource."""
    XMLNAME = (ATOM_NAMESPACE, 'link')
    XMLATTR_href = ('href', uri.URI.from_octets, str)
    XMLATTR_rel = 'rel'
    XMLATTR_type = 'type'
    XMLATTR_hreflang = 'hreflang'
    XMLATTR_title = 'title'
    XMLATTR_length = ('length', xsi.integer_from_str, xsi.integer_to_str)

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        #: a :py:class:`~pyslet.rfc2396.URI` instance, the link's IRI
        self.href = None
        self.rel = None         #: a string indicating the link relation type
        self.type = None        #: an advisory media type
        #: the language of the resource pointed to by :py:attr:`href`
        self.hreflang = None
        self.title = None       #: human-readable information about the link
        #: an advisory length of the linked content in octets
        self.length = None


class Icon(AtomElement):

    """An image that provides iconic visual identification for a feed."""
    XMLNAME = (ATOM_NAMESPACE, 'icon')

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        #: a :py:class:`~pyslet.rfc2396.URI` instance representing the
        #: URI of the icon
        self.uri = None

    def get_value(self):
        """Returning a :py:class:`pyslet.rfc2396.URI` instance."""
        return self.uri

    def set_value(self, value):
        """Enables the value to be set from a URI instance.

        If *value* is a string it is used to set the element's content,
        :py:meth:`content_changed` is then called to update the value of
        :py:attr:`uri`.  If *value* is a URI instance then
        :py:attr:`uri` is set directory and it is then converted to a
        string and used to set the element's content."""
        if isinstance(value, uri.URI):
            self.uri = value
            AtomElement.set_value(self, str(value))
        else:
            AtomElement.set_value(self, value)
            self.content_changed()

    def content_changed(self):
        """Sets :py:attr:`uri` accordingly."""
        self.uri = uri.URI.from_octets(AtomElement.get_value(self))


class Logo(Icon):

    """An image that provides visual identification for a feed."""
    XMLNAME = (ATOM_NAMESPACE, 'logo')


class Generator(AtomElement):

    """Identifies the agent used to generate a feed

    The agent is used for debugging and other purposes."""
    XMLNAME = (ATOM_NAMESPACE, 'generator')
    XMLATTR_uri = ('uri', uri.URI.from_octets, str)
    XMLATTR_version = 'version'

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        #: the uri of the tool used to generate the feed
        self.uri = None
        #: the version of the tool used to generate the feed
        self.version = None

    def set_pyslet_info(self):
        """Sets this generator to a default value

        A representation of this Pyslet module."""
        self.uri = uri.URI.from_octets(info.home)
        self.version = info.version
        self.set_value(info.title)


@old_function('DecodeContentType')
def decode_content_type(src):
    try:
        return TextType.from_str_lower(src)
    except ValueError:
        return src.strip()


@old_function('EncodeContentType')
def encode_content_type(value):
    if is_text(value):
        return value
    else:
        return TextType.to_str(value)


class Content(Text):

    """Contains or links to the content of the entry.

    Although derived from :py:class:`Text` this class overloads the
    meaning of the :py:attr:`Text.type` attribute allowing it to be a
    media type."""
    XMLNAME = (ATOM_NAMESPACE, "content")
    XMLATTR_src = ('src', uri.URI.from_octets, str)
    XMLATTR_type = ('type', decode_content_type, encode_content_type)

    def __init__(self, parent):
        Text.__init__(self, parent)
        self.src = None         #: link to remote content

    def get_value(self):
        """Gets a single string representing the value of the element.

        Overloads the basic :py:meth:`~Text.get_value`, if
        :py:attr:`type` is a media type rather than one of the text
        types then a ValueError is raised."""
        if is_text(self.type):
            raise ValueError("Can't get value of non-text content")
        else:
            Text.get_value(self)


class URI(AtomElement):

    """An IRI associated with a person"""
    XMLNAME = (ATOM_NAMESPACE, 'uri')


class Email(AtomElement):

    """An e-mail address associated with a person"""
    XMLNAME = (ATOM_NAMESPACE, 'email')


class Person(AtomElement):

    """An element that describes a person, corporation, or similar entity"""
    NameClass = Name
    URIClass = URI

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        self.Name = self.NameClass(self)
        self.URI = None
        self.Email = None

    def get_children(self):
        if self.Name:
            yield self.Name
        if self.URI:
            yield self.URI
        if self.Email:
            yield self.Email
        for child in AtomElement.get_children(self):
            yield child


class Author(Person):

    """A Person construct that indicates the author of the entry or feed."""
    XMLNAME = (ATOM_NAMESPACE, 'author')


class Contributor(Person):

    """A Person construct representing a contributor

    Indicates a person or other entity who contributed to the entry or
    feed."""
    XMLNAME = (ATOM_NAMESPACE, "contributor")


class Category(AtomElement):

    """Information about a category associated with an entry or feed."""
    XMLNAME = (ATOM_NAMESPACE, "category")
    XMLATTR_term = 'term'
    XMLATTR_scheme = 'scheme'
    XMLATTR_label = 'label'

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        #: a string that identifies the category to which the entry or
        #: feed belongs
        self.term = None
        self.scheme = None
        """an IRI that identifies a categorization scheme.

        This is not converted to a :py:class:`pyslet.rfc2396.URI`
        instance as it is not normally resolved to a resource.  Instead
        it defines a type of namespace."""
        #: a human-readable label for display in end-user applications
        self.label = None


class Entity(AtomElement):

    """Base class for feed, entry and source elements."""

    LinkClass = Link

    def __init__(self, parent):
        AtomElement.__init__(self, parent)
        self.AtomId = None
        """the atomId of the object

        Note that we qualify the class name used to represent the id to
        avoid confusion with the existing 'id' attribute in
        :py:class:`~pyslet.xml.structures.Element`."""
        self.Author = []        #: atomAuthor
        self.Category = []      #: atomCategory
        self.Contributor = []   #: atomContributor
        self.Link = []          #: atomLink
        self.Rights = None      #: atomRights
        self.Title = None       #: atomTitle
        self.Updated = None     #: atomUpdated

    def reset(self):
        for child in itertools.chain(self.Author, self.Category,
                                     self.Contributor, self.Link):
            child.DetachFromParent
        self.Author = []
        self.Category = []
        self.Contributor = []
        self.Link = []
        if self.Rights:
            self.Rights.detach_from_parent()
            self.Rights = None
        if self.Title:
            self.Title.detach_from_parent()
            self.Title = None
        if self.Updated:
            self.Updated.detach_from_parent()
            self.Updated = None
        super(Entity, self).reset()

    def get_children(self):
        if self.AtomId:
            yield self.AtomId
        if self.Title:
            yield self.Title
        if self.Rights:
            yield self.Rights
        if self.Updated:
            yield self.Updated
        for child in itertools.chain(
                self.Link,
                self.Author,
                self.Contributor,
                self.Category,
                AtomElement.get_children(self)):
            yield child


class Source(Entity):

    """Metadata from the original source feed of an entry.

    This class is also used a base class for :py:class:`Feed`."""
    XMLNAME = (ATOM_NAMESPACE, 'source')
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        Entity.__init__(self, parent)
        self.Generator = None       #: atomGenerator
        self.Icon = None            #: atomIcon
        self.Logo = None            #: atomLogo
        self.Subtitle = None        #: atomSubtitle

    def get_children(self):
        for child in Entity.get_children(self):
            yield child
        if self.Generator:
            yield self.Generator
        if self.Icon:
            yield self.Icon
        if self.Logo:
            yield self.Logo
        if self.Subtitle:
            yield self.Subtitle


class Feed(Source):

    """Represents an Atom feed.

    This is the document (i.e., top-level) element of an Atom Feed Document,
    acting as a container for metadata and data associated with the feed"""
    XMLNAME = (ATOM_NAMESPACE, 'feed')
    AtomIdClass = AtomId
    TitleClass = Title
    UpdatedClass = Updated

    def __init__(self, parent):
        Source.__init__(self, parent)
        self.AtomId = self.AtomIdClass(self)
        self.Title = self.TitleClass(self)
        self.Updated = self.UpdatedClass(self)
        now = iso8601.TimePoint.from_now_utc()
        self.Updated.set_value(now)
        self.Entry = []     #: atomEntry

    def get_children(self):
        for child in itertools.chain(
                Source.get_children(self),
                self.Entry):
            yield child


class Entry(Entity):

    """Represents an individual entry

    Acts as a container for metadata and data associated with the
    entry."""
    XMLNAME = (ATOM_NAMESPACE, 'entry')
    XMLCONTENT = xml.ElementType.ElementContent
    AtomIdClass = AtomId
    TitleClass = Title
    UpdatedClass = Updated
    LinkClass = Link

    def __init__(self, parent):
        Entity.__init__(self, parent)
        self.AtomId = self.AtomIdClass(self)
        self.Title = self.TitleClass(self)
        self.Updated = self.UpdatedClass(self)
        now = iso8601.TimePoint.from_now_utc()
        self.Updated.set_value(now)
        self.Content = None
        self.Published = None
        self.Source = None
        self.Summary = None

    def reset(self):
        self.AtomId.reset()
        if self.Content:
            self.Content.DetatchFromParent()
            self.Content = None
        if self.Published:
            self.Published.detach_from_parent()
            self.Published = None
        if self.Source:
            self.Source.detach_from_parent()
            self.Source = None
        if self.Summary:
            self.Summary.detach_from_parent()
            self.Summary = None
        super(Entry, self).reset()
        # Parent reset removes 'optional' Title and Updated elements
        self.Title = self.TitleClass(self)
        self.Updated = self.UpdatedClass(self)
        now = iso8601.TimePoint.from_now_utc()
        self.Updated.set_value(now)

    def get_children(self):
        for child in Entity.get_children(self):
            yield child
        if self.Content:
            yield self.Content
        if self.Published:
            yield self.Published
        if self.Source:
            yield self.Source
        if self.Summary:
            yield self.Summary


class AtomDocument(xmlns.XMLNSDocument):
    classMap = {}

    default_ns = ATOM_NAMESPACE

    def __init__(self, **args):
        """"""
        xmlns.XMLNSDocument.__init__(self, defaultNS=ATOM_NAMESPACE, **args)

    @classmethod
    def get_element_class(cls, name):
        return AtomDocument.classMap.get(
            name, AtomDocument.classMap.get((name[0], None),
                                            xmlns.XMLNSElement))

xmlns.map_class_elements(AtomDocument.classMap, globals())
