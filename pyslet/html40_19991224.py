#! /usr/bin/env python

from .py2 import py2
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2396 as uri

if py2:
    from htmlentitydefs import name2codepoint
else:
    from html.entities import name2codepoint
    
import string
import itertools
from types import *
import os.path
import shutil

HTML40_PUBLICID = "-//W3C//DTD HTML 4.01//EN"
HTML40_SYSTEMID = "http://www.w3.org/TR/html4/strict.dtd"

HTML40_TRANSITIONAL_PUBLICID = "-//W3C//DTD HTML 4.01 Transitional//EN"
HTML40_TRANSITIONAL_SYSTEMID = "http://www.w3.org/TR/1999/REC-html401-19991224/loose.dtd"

HTML40_FRAMESET_PUBLICID = "-//W3C//DTD HTML 4.01 Frameset//EN"
HTML40_FRAMESET_SYSTEMID = "http://www.w3.org/TR/1999/REC-html401-19991224/frameset.dtd"

HTML40_HTMLlat1_SYSTEMID = "http://www.w3.org/TR/1999/REC-html401-19991224/HTMLlat1.ent"
HTML40_HTMLsymbol_SYSTEMID = "http://www.w3.org/TR/1999/REC-html401-19991224/HTMLsymbol.ent"
HTML40_HTMLspecial_SYSTEMID = "http://www.w3.org/TR/1999/REC-html401-19991224/HTMLspecial.ent"

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"


class NamedBoolean:

    """An abstract class designed to make generating SGML-like single-value enumeration
    types easier, for example, attributes such as "checked" on <input>.

    The class is not designed to be instantiated but to act as a method of
    defining functions for decoding and encoding attribute values.

    The basic usage of this class is to derive a class from it with a single
    class member called 'name' which is the canonical representation of the
    name. You can then use it to call any of the following class methods to
    convert values between python Booleans and the appropriate string
    representations (None for False and the defined name for True)."""

    @classmethod
    def DecodeValue(cls, src):
        """Decodes a string returning True if it matches the name attribute
        and raising a ValueError otherwise.  If src is None then False is
        returned."""
        if src is None:
            return False
        else:
            src = src.strip()
            if src == cls.name:
                return True
            else:
                raise ValueError("Can't decode %s from %s" %
                                 (cls.__name__, src))

    @classmethod
    def DecodeLowerValue(cls, src):
        """Decodes a string, converting it to lower case first."""
        if src is None:
            return False
        else:
            src = src.strip().lower()
            if src == cls.name:
                return True
            else:
                raise ValueError("Can't decode %s from %s" %
                                 (cls.__name__, src))

    @classmethod
    def DecodeUpperValue(cls, src):
        """Decodes a string, converting it to upper case first."""
        if src is None:
            return False
        else:
            src = src.strip().upper()
            if src == cls.name:
                return True
            else:
                raise ValueError("Can't decode %s from %s" %
                                 (cls.__name__, src))

    @classmethod
    def EncodeValue(cls, value):
        """Encodes a boolean value returning either the defined name or None."""
        if value:
            return cls.name
        else:
            return None


XHTML_MIMETYPES = {
    None: False,
    'text/xml': True,
    'text/html': False
}


class XHTMLError(Exception):
    pass


class XHTMLValidityError(XHTMLError):
    pass


class XHTMLMimeTypeError(XHTMLError):
    pass

"""TODO: ContentType::

	<!ENTITY % ContentType "CDATA" -- media type, as per [RFC2045] --
	<!ENTITY % ContentTypes "CDATA" -- comma-separated list of media types, as per [RFC2045]	-->	"""


"""TODO: Charset::

	<!ENTITY % Charset "CDATA" -- a character encoding, as per [RFC2045] -->
	<!ENTITY % Charsets "CDATA" -- a space-separated list of character encodings, as per [RFC2045] -->	"""


"""TODO: LanguageCode::

	<!ENTITY % LanguageCode "NAME" -- a language code, as per [RFC1766] -->	"""


def DecodeCharacter(src):
    """Decodes a Character value::

            <!ENTITY % Character "CDATA" -- a single character from [ISO10646] -->

    Returns the first character of src or None, if src is empty."""
    if len(src) > 0:
        return src[0]
    else:
        return None


class XHTMLMixin(object):

    """An abstract class representing all elements with HTML-like properties.

    This class is used to determine if an element should be treated as if it is
    HTML-like or if it is simply a foreign element from some unknown schema.

    HTML-like elements are subject to appropriate HTML content constraints, for
    example, block elements are not allowed to appear where inline elements are
    required.  Non-HTML-like elements are permitted more freely."""
    pass


class XHTMLElement(XHTMLMixin, xmlns.XMLNSElement):

    """A base class for XHTML elements."""
    XMLCONTENT = xmlns.XMLMixedContent

    def AddToCPResource(self, cp, resource, beenThere):
        """See :py:meth:`pyslet.imsqtiv2p1.QTIElement.AddToCPResource`  """
        for child in self.GetChildren():
            if hasattr(child, 'AddToCPResource'):
                child.AddToCPResource(cp, resource, beenThere)

    def RenderHTML(self, parent, profile, arg):
        """Renders this HTML element to an external document represented by the *parent* node.

        *profile* is a dictionary mapping the names of allowed HTML elements to
        a list of allowed attributes.  This allows the caller to filter out
        unwanted elements and attributes on a whitelist basis.

        *arg* allows an additional argument to be passed through the HTML tree to any non-HTML
        nodes contained by it."""
        # the default implementation creates a node under parent if our name is
        # in the profile
        if self.xmlname in profile:
            newChild = parent.ChildElement(self.__class__)
            alist = profile[self.xmlname]
            attrs = self.GetAttributes()
            for aname in attrs.keys():
                ns, name = aname
                if ns is None and name in alist:
                    # this one is included
                    newChild.SetAttribute(aname, attrs[aname])
            for child in self.GetChildren():
                if type(child) in StringTypes:
                    newChild.AddData(child)
                else:
                    child.RenderHTML(newChild, profile, arg)

    def RenderText(self):
        output = []
        for child in self.GetChildren():
            if type(child) in StringTypes:
                output.append(child)
            else:
                output.append(child.RenderText())
        return string.join(output, '')


class FlowMixin(XHTMLMixin):

    """Mixin class for flow elements::

            <!ENTITY % flow "%block; | %inline;">
    """
    pass


class BlockMixin(FlowMixin):

    """Mixin class for block elements::

            <!ENTITY % block "P | %heading; | %list; | %preformatted; | DL | DIV |
                    NOSCRIPT | BLOCKQUOTE | FORM | HR | TABLE | FIELDSET | ADDRESS">
    """
    pass


class InlineMixin(FlowMixin):

    """Mixin class for inline elements::

            <!ENTITY % inline "#PCDATA | %fontstyle; | %phrase; | %special; | %formctrl;">	"""
    pass


def ValidateLinkType(value):
    """Link types may not contain white space characters
    ::

            <!ENTITY % LinkTypes "CDATA"	-- space-separated list of link types handled directly -->"""
    v = value.strip()
    for c in v:
        if xmlns.is_s(c):
            raise ValueError("White space in link type: %s" % repr(value))
    return v


class MediaDesc(object):

    """A list of media for which a linked resource is tailored
    ::

            <!ENTITY % MediaDesc "CDATA"	-- single or comma-separated list of media descriptors	-->

    Behaves like a list of strings, but when initialised will split by comma."""

    def __init__(self, value):
        self.values = []
        if value:
            if "," in value:
                self.values = map(
                    lambda x: unicode(x).strip(), value.split(","))
            else:
                self.values = [unicode(value.strip())]

    def __str__(self):
        return string.join(map(lambda x: str(x), self.values), ',')

    def __unicode__(self):
        return string.join(self.values, u",")

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __setitem__(self, index, value):
        if "," in value:
            raise ValueError("',' not allowed in media descriptor")
        self.values[index] = unicode(value).strip()

    def __iter__(self):
        return iter(self.values)


def DecodeURI(src):
    """Decodes a URI from src::

    <!ENTITY % URI "CDATA"  -- a Uniform Resource Identifier -->

    We adopt the algorithm recommended in Appendix B of the
    specification, which involves replacing non-ASCII characters with
    percent-encoded UTF-sequences.

    For more information see :func:`psylet.rfc2396.encode_unicode_uri`"""
    return uri.URI.from_octets(uri.encode_unicode_uri(src))


def EncodeURI(uri):
    """Encoding a URI means just converting it into a string.

    By definition, a URI will only result in ASCII characters that can be freely converted
    to Unicode by the default encoding.  However, it does mean that this function doesn't
    adhere to the principal of using the ASCII encoding only at the latest possible time."""
    return unicode(str(uri))

"""No special action required::

	<!ENTITY % Datetime "CDATA" -- date and time information. ISO date format -->
	<!ENTITY % Script "CDATA" -- script expression -->
	<!ENTITY % StyleSheet "CDATA" -- style sheet data -->
	<!ENTITY % FrameTarget "CDATA" -- render in this frame -->
	<!ENTITY % Text "CDATA">"""


class HeadMiscMixin(object):

    """Mixin class for misc head.misc elements::

            <!ENTITY % head.misc "SCRIPT|STYLE|META|LINK|OBJECT" -- repeatable head elements -->	"""
    pass


"""Headings and list classes are defined later with proper base classes::

		<!ENTITY % heading "H1|H2|H3|H4|H5|H6">
		<!ENTITY % list "UL | OL |  DIR | MENU">
		<!ENTITY % preformatted "PRE">"""


class Color(object):

    """Class to represent a color value.

    Instances can be created from strings and so can be used as attribute decoders.
    The unbound __unicode__ method can be used likewise::

            <!ENTITY % Color "CDATA" -- a color using sRGB: #RRGGBB as Hex values -->

            <!-- There are also 16 widely known color names with their sRGB values -->"""

    Black = u"#000000"
    Green = u"#008000"
    Silver = u"#C0C0C0"
    Lime = u"#00FF00"
    Gray = u"#808080"
    Olive = u"#808000"
    White = u"#FFFFFF"
    Yellow = u"#FFFF00"
    Maroon = u"#800000"
    Navy = u"#000080"
    Red = u"#FF0000"
    Blue = u"#0000FF"
    Purple = u"#800080"
    Teal = u"#008080"
    Fuchsia = u"#FF00FF"
    Aqua = u"#00FFFF"

    def __init__(self, src):
        cv = []
        base = 0
        len = 0
        for c in src:
            if uri.is_hex(c):
                len = len + 1
            else:
                base = base + len + 1
                len = 0
        if len >= 6:
            self.r = int(src[base:base + 2], 16)
            self.g = int(src[base + 2:base + 4], 16)
            self.b = int(src[base + 4:base + 6], 16)
        else:
            self.r = self.g = self.b = 0

    def __str__(self):
        return "#02X02X02X" % (self.r, self.g, self.b)

    def __unicode__(self):
        return u"#02X02X02X" % (self.r, self.g, self.b)


class BodyColorsMixin(object):

    """Mixin class for bodycolors attributes::

            <!ENTITY % bodycolors "
              bgcolor     %Color;        #IMPLIED  -- document background color --
              text        %Color;        #IMPLIED  -- document text color --
              link        %Color;        #IMPLIED  -- color of links --
              vlink       %Color;        #IMPLIED  -- color of visited links --
              alink       %Color;        #IMPLIED  -- color of selected links --
              ">"""
    XMLATTR_bgcolor = ('bgColor', Color, Color.__unicode__)
    XMLATTR_text = ('bgColor', Color, Color.__unicode__)
    XMLATTR_link = ('bgColor', Color, Color.__unicode__)
    XMLATTR_vlink = ('bgColor', Color, Color.__unicode__)
    XMLATTR_alink = ('bgColor', Color, Color.__unicode__)


"""HTML Entities are implemented directly from native python libraries::

		<!ENTITY % HTMLlat1 PUBLIC
		   "-//W3C//ENTITIES Latin1//EN//HTML"
		   "HTMLlat1.ent">
		%HTMLlat1;
		
		<!ENTITY % HTMLsymbol PUBLIC
		   "-//W3C//ENTITIES Symbols//EN//HTML"
		   "HTMLsymbol.ent">
		%HTMLsymbol;
		
		<!ENTITY % HTMLspecial PUBLIC
		   "-//W3C//ENTITIES Special//EN//HTML"
		   "HTMLspecial.ent">
		%HTMLspecial;"""


class CoreAttrsMixin(object):

    """Mixin class for core attributes::

            <!ENTITY % coreattrs
             "id          ID             #IMPLIED  -- document-wide unique id --
              class       CDATA          #IMPLIED  -- space-separated list of classes --
              style       %StyleSheet;   #IMPLIED  -- associated style info --
              title       %Text;         #IMPLIED  -- advisory title --"
              >"""
    ID = (xmlns.NO_NAMESPACE, 'id')
    XMLATTR_class = 'styleClass'  # re-mapped to avoid python reserved word
    XMLATTR_style = 'style'
    XMLATTR_title = 'title'


class Direction(xsi.Enumeration):

    """Enumeration for weak/neutral text values."""
    decode = {
        'ltr': 1,
        'rtl': 2
    }
xsi.MakeEnumeration(Direction)


class I18nMixin(object):

    """Mixin class for i18n attributes
    ::

            <!ENTITY % i18n
             "lang        %LanguageCode; #IMPLIED  -- language code --
              dir         (ltr|rtl)      #IMPLIED  -- direction for weak/neutral text --"
              >

            <!ENTITY % LanguageCode "NAME"	-- a language code, as per [RFC1766]	-->"""
    XMLATTR_lang = ('htmlLang', xsi.DecodeName, xsi.EncodeName)
    XMLATTR_dir = ('dir', Direction.DecodeLowerValue, Direction.EncodeValue)


class EventsMixin(object):

    """Mixin class for event attributes
    ::

            <!ENTITY % events
             "onclick     %Script;       #IMPLIED  -- a pointer button was clicked --
              ondblclick  %Script;       #IMPLIED  -- a pointer button was double clicked--
              onmousedown %Script;       #IMPLIED  -- a pointer button was pressed down --
              onmouseup   %Script;       #IMPLIED  -- a pointer button was released --
              onmouseover %Script;       #IMPLIED  -- a pointer was moved onto --
              onmousemove %Script;       #IMPLIED  -- a pointer was moved within --
              onmouseout  %Script;       #IMPLIED  -- a pointer was moved away --
              onkeypress  %Script;       #IMPLIED  -- a key was pressed and released --
              onkeydown   %Script;       #IMPLIED  -- a key was pressed down --
              onkeyup     %Script;       #IMPLIED  -- a key was released --"
              >"""
    XMLATTR_onclick = 'onClick'
    XMLATTR_ondblclick = 'onDblClick'
    XMLATTR_onmousedown = 'onMouseDown'
    XMLATTR_onmouseup = 'onMouseUp'
    XMLATTR_onmouseover = 'onMouseOver'
    XMLATTR_onmousemove = 'onMouseMove'
    XMLATTR_onmouseout = 'onMouseOut'
    XMLATTR_onkeypress = 'onKeyPress'
    XMLATTR_onkeydown = 'onKeyDown'
    XMLATTR_onkeyup = 'onKeyUp'


class AttrsMixin(CoreAttrsMixin, I18nMixin, EventsMixin):

    """Mixin class for common attributes
    ::

            <!ENTITY % attrs "%coreattrs; %i18n; %events;">"""
    pass


class Align(xsi.Enumeration):

    """Values for text alignment
    ::

            <!ENTITY % align "align (left|center|right|justify)  #IMPLIED"
                    -- default is left for ltr paragraphs, right for rtl --	"""
    decode = {
        'left': 1,
        'center': 2,
        'right': 3,
        'justify': 4
    }
xsi.MakeEnumeration(Align)


"""fontstyle and phrase become proper base classes later."""


class SpecialMixin(InlineMixin):

    """Specials are just another type of inline element
    ::

            Strict:	<!ENTITY % special "A | IMG | OBJECT | BR | SCRIPT | MAP | Q | SUB | SUP | SPAN | BDO">
            Loose:	<!ENTITY % special "A | IMG | APPLET | OBJECT | FONT | BASEFONT | BR | SCRIPT | MAP
                                    | Q | SUB | SUP | SPAN | BDO | IFRAME">"""
    pass


class FormCtrlMixin(InlineMixin):

    """Form controls are just another type of inline element
    ::

            <!ENTITY % formctrl "INPUT | SELECT | TEXTAREA | LABEL | BUTTON">"""
    pass


class InlineContainer(XHTMLElement):

    """Base class for elements with content models consisting of inline elements
    ::
    <!ELEMENT XXXX - - (%inline;)*>"""
    XMLCONTENT = xmlns.XMLMixedContent

    def GetChildClass(self, stag_class):
        """Implements omittag by returning None if stag_class is anything other than None (PCDATA), inline."""
        if stag_class is None or issubclass(stag_class, InlineMixin) or not issubclass(stag_class, XHTMLMixin):
            return stag_class
        else:
            return None

    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, InlineMixin) or not issubclass(childClass, XHTMLMixin):
            return super(XHTMLElement, self).ChildElement(childClass, name)
        else:
            raise XHTMLValidityError(
                "%s in %s" % (childClass.__name__, self.__class__.__name__))


class FontStyle(AttrsMixin, InlineMixin, InlineContainer):

    """Abstract class for font and style elements
    ::
            <!ENTITY % fontstyle "TT | I | B | U | S | STRIKE | BIG | SMALL">
            <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
            <!ATTLIST (%fontstyle;|%phrase;)
              %attrs;                              -- %coreattrs, %i18n, %events --
              >"""
    pass


class TT(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'tt')


class I(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'i')


class B(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'b')


class U(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'u')


class S(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 's')


class Strike(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'strike')


class Big(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'big')


class Small(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'small')


class Phrase(AttrsMixin, InlineMixin, InlineContainer):

    """Abstract class for phrase elements
    ::
            <!ENTITY % phrase "EM | STRONG | DFN | CODE | SAMP | KBD | VAR | CITE | ABBR | ACRONYM" >
            <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
            <!ATTLIST (%fontstyle;|%phrase;)
              %attrs;                              -- %coreattrs, %i18n, %events --
              >"""
    pass


class Em(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'em')


class Strong(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'strong')


class Dfn(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'dfn')


class Code(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'code')


class Samp(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'samp')


class Kbd(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'kbd')


class Var(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'var')


class Cite(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'cite')


class Abbr(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'abbr')


class Acronym(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'acronym')


class Sub(AttrsMixin, SpecialMixin, InlineContainer):

    """Subscript
    ::

            <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
            <!ATTLIST (SUB|SUP)	%attrs;                              -- %coreattrs, %i18n, %events --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'sub')


class Sup(AttrsMixin, SpecialMixin, InlineContainer):

    """Superscript
    ::

            <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript --> 
            <!ATTLIST (SUB|SUP)	%attrs;                              -- %coreattrs, %i18n, %events --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'sup')


class Span(AttrsMixin, SpecialMixin, InlineContainer):

    """Span
    ::

            <!ELEMENT SPAN - - (%inline;)*         -- generic language/style container -->
            <!ATTLIST SPAN
              %attrs;                              -- %coreattrs, %i18n, %events --
              %reserved;			       -- reserved for possible future use --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'span')


class BDO(CoreAttrsMixin, SpecialMixin, InlineContainer):

    """BiDi over-ride element
    ::

            <!ELEMENT BDO - - (%inline;)*          -- I18N BiDi over-ride -->
            <!ATTLIST BDO
              %coreattrs;                          -- id, class, style, title --
              lang        %LanguageCode; #IMPLIED  -- language code --
              dir         (ltr|rtl)      #REQUIRED -- directionality --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'bdo')
    XHTMLATTR_lang = ('lang', xsi.DecodeName, xsi.EncodeName)
    XMLATTR_dir = ('dir', Direction.DecodeLowerValue, Direction.EncodeValue)

    def __init__(self, parent):
        super(BDO, self).__init__(self, parent)
        self.dir = Direction.DEFAULT


class BaseFont(SpecialMixin, XHTMLElement):

    """Base font specification
    ::

            <!ELEMENT BASEFONT - O EMPTY           -- base font size -->
            <!ATTLIST BASEFONT
              id          ID             #IMPLIED  -- document-wide unique id --
              size        CDATA          #REQUIRED -- base font size for FONT elements --
              color       %Color;        #IMPLIED  -- text color --
              face        CDATA          #IMPLIED  -- comma-separated list of font names --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'basefont')
    ID = 'id'
    XMLATTR_size = 'size'
    XMLATTR_color = ('color', Color, Color.__unicode__)
    XMLATTR_face = 'face'
    XMLCONTENT = xmlns.ElementType.Empty

    def __init__(self, parent):
        super(BaseFont, self).__init__(parent)
        self.size = ''


class Font(I18nMixin, CoreAttrsMixin, SpecialMixin, InlineContainer):

    """Font element
    ::

            <!ELEMENT FONT - - (%inline;)*         -- local change to font -->
            <!ATTLIST FONT
              %coreattrs;                          -- id, class, style, title --
              %i18n;		               -- lang, dir --
              size        CDATA          #IMPLIED  -- [+|-]nn e.g. size="+1", size="4" --
              color       %Color;        #IMPLIED  -- text color --
              face        CDATA          #IMPLIED  -- comma-separated list of font names --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'font')
    XMLATTR_size = 'size'
    XMLATTR_color = ('color', Color, Color.__unicode__)
    XMLATTR_face = 'face'


class Clear(xsi.Enumeration):

    """For setting the clear attribute, e.g on Br"""
    decode = {
        'left': 1,
        'all': 2,
        'right': 3,
        'none': 4
    }
xsi.MakeEnumeration(Clear, "none")


class Br(CoreAttrsMixin, SpecialMixin, XHTMLElement):

    """Line break
    ::

            <!ELEMENT BR - O EMPTY                 -- forced line break -->
            <!ATTLIST BR
              %coreattrs;                          -- id, class, style, title --
              clear       (left|all|right|none) none -- control of text flow --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'br')
    XMLATTR_clear = ('clear', Clear.DecodeLowerValue, Clear.EncodeValue)
    XMLCONTENT = xmlns.ElementType.Empty


class Body(AttrsMixin, BodyColorsMixin, XHTMLElement):

    """Represents the HTML BODY structure
    ::

            <!ELEMENT BODY O O (%block;|SCRIPT)+ +(INS|DEL) -- document body -->
            <!ATTLIST BODY
                      %attrs;                              -- %coreattrs, %i18n, %events --
                      onload          %Script;   #IMPLIED  -- the document has been loaded --
                      onunload        %Script;   #IMPLIED  -- the document has been removed --
                      background      %URI;      #IMPLIED  -- texture tile for document
                                                                                                      background --
                      %bodycolors;                         -- bgcolor, text, link, vlink, alink --"""
    XMLNAME = (XHTML_NAMESPACE, 'body')
    XMLATTR_onload = 'onLoad'
    XMLATTR_onunload = 'onUnload'
    XMLATTR_background = ('background', DecodeURI, EncodeURI)
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """Handled omitted tags"""
        if stag_class is None:
            # data in Body implies DIV
            return Div
        elif issubclass(stag_class, (BlockMixin, Script, Ins, Del)) or not issubclass(stag_class, XHTMLMixin):
            # non-HTML like elements can go in here too
            return stag_class
        elif issubclass(stag_class, FlowMixin):
            # allowed by loose DTD but we encapsulate in Flow to satisfy strict
            return Div
        elif issubclass(stag_class, (Head, HeadMiscMixin, HeadContentMixin)):
            # Catch HEAD content appearing in BODY and force HEAD, BODY, HEAD, BODY,... to catch all
            # of it.  As we can only have one HEAD and one BODY we just put
            # things in their right place.
            return None
        else:
            raise XHTMLValidityError(
                "%s in %s" % (stag_class.__name__, self.__class__.__name__))

    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, (BlockMixin, Script, Ins, Del)) or not issubclass(childClass, XHTMLMixin):
            return super(XHTMLElement, self).ChildElement(childClass, name)
        else:
            raise XHTMLValidityError(
                "%s in %s" % (childClass.__name__, self.__class__.__name__))


class Address(AttrsMixin, BlockMixin, InlineContainer):

    """Address (of author)
    ::
            <!ELEMENT ADDRESS - - ((%inline;)|P)*  -- information on author -->
            <!ATTLIST ADDRESS
              %attrs;                              -- %coreattrs, %i18n, %events --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'address')
    XMLCONTENT = xmlns.XMLMixedContent

    def GetChildClass(self, stag_class):
        """We add P to our inline container."""
        if stag_class is P:
            return stag_class
        else:
            return super(Address, self).GetChildClass(stag_class)

    def ChildElement(self, childClass, name=None):
        if childClass is P:
            return P(self, name)
        else:
            return super(XHTMLElement, self).ChildElement(childClass, name)


class FlowContainer(XHTMLElement):

    """Abstract class for all HTML elements that contain %flow;"""
    XMLCONTENT = xmlns.XMLMixedContent

    def GetChildClass(self, stag_class):
        """If we get something other than, PCDATA, a flow or unknown element, assume end"""
        if stag_class is None or issubclass(stag_class, FlowMixin) or not issubclass(stag_class, XHTMLMixin):
            return stag_class
        else:
            return None

    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, FlowMixin) or not issubclass(childClass, XHTMLMixin):
            return super(XHTMLElement, self).ChildElement(childClass, name)
        else:
            raise XHTMLValidityError(
                "%s in %s" % (childClass.__name__, self.__class__.__name__))

    def PrettyPrint(self):
        """Deteremins if this flow-container should be pretty printed.

        We suppress pretty printing if we have any non-trivial data children or
        if we have any inline child elements."""
        for child in self.GetChildren():
            if type(child) in StringTypes:
                for c in child:
                    if not xml.is_s(c):
                        return False
            # elif isinstance(child,InlineMixin):
            #	return False
        return True


class Div(AttrsMixin, BlockMixin, FlowContainer):

    """A generic language/style container
    ::

            <!ELEMENT DIV - - (%flow;)*            --  -->
            <!ATTLIST DIV
              %attrs;                              -- %coreattrs, %i18n, %events --
              %align;                              -- align, text alignment --
              %reserved;                           -- reserved for possible future use --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'div')
    XMLATTR_align = ('align', Align.DecodeLowerValue, Align.EncodeValue)


class Center(AttrsMixin, BlockMixin, FlowContainer):

    """Same as <div align="center"> </div>
    ::
            <!ELEMENT CENTER - - (%flow;)*         -- shorthand for DIV align=center -->
            <!ATTLIST CENTER
              %attrs;                              -- %coreattrs, %i18n, %events --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'center')


class Shape(xsi.Enumeration):

    """Enumeration for the shape of clickable areas
    ::

            <!ENTITY % Shape "(rect|circle|poly|default)">"""
    decode = {
        'rect': 1,
        'circle': 2,
        'poly': 3,
        'default': 4
    }
xsi.MakeEnumeration(Shape)


class LengthType(object):

    """Represents the HTML Length::

            <!ENTITY % Length "CDATA" -- nn for pixels or nn% for percentage length -->

    *	value can be either an integer value, another LengthType instance or a
            string.

    *	if value is an integer then valueType can be used to select Pixel or
            Percentage

    *	if value is a string then it is parsed for the length as per the format
            defined for length attributes in HTML.		

    By default values are assumed to be Pixel lengths but valueType can be used
    to force such a value to be a Percentage if desired."""

    Pixel = 0
    """data constant used to indicate pixel co-ordinates"""

    Percentage = 1
    """data constant used to indicate relative (percentage) co-ordinates"""

    def __init__(self, value, valueType=None):
        if isinstance(value, LengthType):
            self.type = value.type
            """type is one of the the LengthType constants: Pixel or Percentage"""
            self.value = value.value
            """value is the integer value of the length"""
        elif type(value) in StringTypes:
            try:
                strValue = value.strip()
                v = []
                for c in strValue:
                    if valueType is None and c.isdigit():
                        v.append(c)
                    elif c == u"%":
                        valueType = LengthType.Percentage
                        break
                    else:
                        valueType = LengthType.Pixel
                if valueType is None:
                    valueType = LengthType.Pixel
                v = int(string.join(v, ''))
                if v < 0:
                    raise ValueError
                self.type = valueType
                self.value = v
            except ValueError:
                raise XHTMLValidityError(
                    "Failed to read length from %s" % strValue)
        else:
            self.type = LengthType.Pixel if valueType is None else valueType
            self.value = value

    def __nonzero__(self):
        """Length values are non-zero if they have a non-zero value (pixel or percentage)."""
        if self.value:
            return True
        else:
            return False

    def __str__(self):
        """Formats the length as a string of form nn for pixels or nn% for percentage."""
        if self.type == LengthType.Percentage:
            return str(self.value) + '%'
        else:
            return str(self.value)

    def __unicode__(self):
        """Formats the length as a unicode string of form nn for pixels or nn% for percentage."""
        if self.type == LengthType.Percentage:
            return unicode(self.value) + '%'
        else:
            return unicode(self.value)

    def GetValue(self, dim=None):
        """Returns the value of the Length, *dim* is the size of the dimension
        used for interpreting percentage values.  I.e., 100% will return
        *dim*."""
        if self.type == self.Percentage:
            if dim is None:
                raise ValueError("Relative length without dimension")
            else:
                return (self.value * dim + 50) // 100
        else:
            return self.value

    def Add(self, value):
        """Adds *value* to the length.

        If value is another LengthType instance then its value is added to the
        value of this instances' value only if the types match.  If value is an
        integer it is assumed to be a value of pixel type - a mismatch raises
        ValueError."""
        if isinstance(value, LengthType):
            if self.type == value.type:
                self.value += value.value
            else:
                raise ValueError(
                    "Can't add lengths of different types: %s+%s" % (str(self), str(value)))
        elif self.type == LengthType.Pixel:
            self.value += value
        else:
            raise ValueError(
                "Can't add integer to non-Pixel length value: %s+&i" % (str(self), value))


class Coords:

    """Represents HTML Coords values
    ::

            <!ENTITY % Coords "CDATA" -- comma-separated list of lengths -->

    Instances can be initialized from an existing list of
    :py:class:`LengthType`, or a list of any object that can be used to
    construct a LengthType.  It can also be constructed from a string formatted
    as per the HTML attribute definition.

    The resulting object behaves like a list of LengthType instances, for example::

            x=Coords("10, 50, 60%,75%")
            len(x)==4
            x[0].value==10
            x[2].type==LengthType.Percentage
            str(x[3])=="75%"
            # items are also assignable...
            x[1]="40%"
            x[1].type==LengthType.Percentage
            x[1].value==40
    """

    def __init__(self, values=None):
        #: a list of :py:class:`LengthType` values
        self.values = []
        if values:
            if type(values) in StringTypes:
                if ',' in values:
                    self.values = map(
                        lambda x: LengthType(x.strip()), values.split(','))
            else:
                for v in values:
                    if isinstance(v, LengthType):
                        self.values.append(v)
                    else:
                        self.values.append(LengthType(v))

    def __unicode__(self):
        """Formats the Coords as comma-separated unicode string of Length values."""
        return string.join(map(lambda x: unicode(x), self.values), u',')

    def __str__(self):
        """Formats the Coords as a comma-separated string of Length values."""
        return string.join(map(lambda x: str(x), self.values), ',')

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __setitem__(self, index, value):
        if isinstance(value, LengthType):
            self.values[index] = value
        else:
            self.values[index] = LengthType(value)

    def __iter__(self):
        return iter(self.values)

    def TestRect(self, x, y, width, height):
        """Tests an x,y point against a rect with these coordinates.

        HTML defines the rect co-ordinates as: left-x, top-y, right-x, bottom-y"""
        if len(self.values) < 4:
            raise ValueError(
                "Rect test requires 4 coordinates: %s" % str(self.values))
        x0 = self.values[0].GetValue(width)
        y0 = self.values[1].GetValue(height)
        x1 = self.values[2].GetValue(width)
        y1 = self.values[3].GetValue(height)
        # swap the coordinates so that x0,y0 really is the top-left
        if x0 > x1:
            xs = x0
            x0 = x1
            x1 = xs
        if y0 > y1:
            ys = y0
            y0 = y1
            y1 = ys
        if x < x0 or y < y0:
            return False
        if x >= x1 or y >= y1:
            return False
        return True

    def TestCircle(self, x, y, width, height):
        """Tests an x,y point against a circle with these coordinates.

        HTML defines a circle as: center-x, center-y, radius.

        The specification adds the following note:

                When the radius value is a percentage value, user agents should
                calculate the final radius value based on the associated object's
                width and height. The radius should be the smaller value of the two."""
        if len(self.values) < 3:
            raise ValueError(
                "Circle test requires 3 coordinates: %s" % str(self.values))
        if width < height:
            rMax = width
        else:
            rMax = height
        dx = x - self.values[0].GetValue(width)
        dy = y - self.values[1].GetValue(height)
        r = self.values[2].GetValue(rMax)
        return dx * dx + dy * dy <= r * r

    def TestPoly(self, x, y, width, height):
        """Tests an x,y point against a poly with these coordinates.

        HTML defines a poly as: x1, y1, x2, y2, ..., xN, yN.

        The specification adds the following note:

                The first x and y coordinate pair and the last should be the same to
                close the polygon. When these coordinate values are not the same,
                user agents should infer an additional coordinate pair to close the
                polygon.

        The algorithm used is the "Ray Casting" algorithm described here:
        http://en.wikipedia.org/wiki/Point_in_polygon"""
        if len(self.values) < 6:
            # We need at least six coordinates - to make a triangle
            raise ValueError(
                "Poly test requires as least 3 coordinates: %s" % str(self.values))
        if len(self.values) % 2:
            # We also need an even number of coordinates!
            raise ValueError(
                "Poly test requires an even number of coordinates: %s" % str(self.values))
        # We build an array of y-values and clean up the missing end point
        # problem
        vertex = []
        i = 0
        for v in self.values:
            if i % 2:
                # this is a y coordinate
                vertex.append((lastX, v.GetValue(height)))
            else:
                # this is an x coordinate
                lastX = v.GetValue(width)
            i = i + 1
        if vertex[0][0] != vertex[-1][0] or vertex[0][1] != vertex[-1][1]:
            # first point is not the same as the last point
            vertex.append(vertex[0])
        # We now have an array of vertex coordinates ready for the Ray Casting algorithm
        # We start from negative infinity with a horizontal ray passing through
        # x,y
        nCrossings = 0
        for i in xrange(len(vertex) - 1):
            # we use a horizontal ray passing through the point x,y
            x0, y0 = vertex[i]
            x1, y1 = vertex[i + 1]
            i += 1
            if y0 == y1:
                # ignore horizontal edges
                continue
            if y0 > y1:
                # swap the vertices so that x1,y1 has the higher y value
                xs, ys = x0, y0
                x0, y0 = x1, y1
                x1, y1 = xs, ys
            if y < y0 or y >= y1:
                # A miss, or at most a touch on the lower (higher y value)
                # vertex
                continue
            elif y == y0:
                # The ray at most touches the upper vertex
                if x >= x0:
                    # upper vertex intersection, or a miss
                    nCrossings += 1
                continue
            if x < x0 and x < x1:
                # This edge is off to the right, a miss
                continue
            # Finally, we have to calculate an intersection
            xHit = float(y - y0) * float(x1 - x0) / float(y1 - y0) + float(x0)
            if xHit <= float(x):
                nCrossings += 1
        return nCrossings % 2 != 0


class A(AttrsMixin, SpecialMixin, InlineContainer):

    """The HTML anchor element::

    <!ELEMENT A - - (%inline;)* -(A)       -- anchor -->
    <!ATTLIST A
      %attrs;                              -- %coreattrs, %i18n, %events --
      charset     %Charset;      #IMPLIED  -- char encoding of linked resource --
      type        %ContentType;  #IMPLIED  -- advisory content type --
      name        CDATA          #IMPLIED  -- named link end --
      href        %URI;          #IMPLIED  -- URI for linked resource --
      hreflang    %LanguageCode; #IMPLIED  -- language code --
      target      %FrameTarget;  #IMPLIED  -- render in this frame --
      rel         %LinkTypes;    #IMPLIED  -- forward link types --
      rev         %LinkTypes;    #IMPLIED  -- reverse link types --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      shape       %Shape;        rect      -- for use with client-side image maps --
      coords      %Coords;       #IMPLIED  -- for use with client-side image maps --
      tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
      onfocus     %Script;       #IMPLIED  -- the element got the focus --
      onblur      %Script;       #IMPLIED  -- the element lost the focus --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'a')
    XMLATTR_charset = 'charset'
    XMLATTR_type = 'type'
    XMLATTR_name = 'name'
    XMLATTR_href = ('href', DecodeURI, EncodeURI)
    XMLATTR_hreflang = ('hrefLang', xsi.DecodeName, xsi.EncodeName)
    XMLATTR_target = 'target'
    XMLATTR_rel = ('rel', ValidateLinkType, None, list)
    XMLATTR_rev = ('rev', ValidateLinkType, None, list)
    XMLATTR_accesskey = 'accessKey'
    XMLATTR_shape = ('shape', Shape.DecodeLowerValue, Shape.EncodeValue)
    XMLATTR_coords = ('coords', Coords, Coords.__unicode__)
    XMLATTR_tabindex = ('tabIndex', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_onfocus = 'onFocus'
    XMLATTR_onblur = 'onBlur'


class BlockContainer(XHTMLElement):

    """Abstract class for all HTML elements that contain just %block;"""
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """If we get inline data in this context we force it to wrap in DIV"""
        if stag_class is None or issubclass(stag_class, InlineMixin):
            return Div
        elif issubclass(stag_class, (BlockMixin, Script)) or not issubclass(stag_class, XHTMLMixin):
            return stag_class
        else:
            return None

    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, BlockMixin) or not issubclass(childClass, XHTMLMixin):
            return super(XHTMLElement, self).ChildElement(childClass, name)
        else:
            raise XHTMLValidityError(
                "%s in %s" % (childClass.__name__, self.__class__.__name__))


class Map(AttrsMixin, SpecialMixin, BlockContainer):

    """Client-side image maps
    ::

            <!ELEMENT MAP - - ((%block;) | AREA)+ -- client-side image map -->
            <!ATTLIST MAP
              %attrs;                              -- %coreattrs, %i18n, %events --
              name        CDATA          #REQUIRED -- for reference by usemap --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'map')
    XMLATTR_name = 'name'

    def __init__(self, parent):
        super(Map, self).__init__(parent)
        self.name = ''

    def GetChildClass(self, stag_class):
        """We add Area to our allowed content model."""
        if stag_class is Area:
            return Area
        else:
            return super(Map, self).GetChildClass(stag_class)

    def ChildElement(self, childClass, name=None):
        if childClass is Area:
            return Area(self, name)
        else:
            return super(Map, self).ChildElement(childClass, name)


class NoHRef(NamedBoolean):

    """For setting the nohref attribute."""
    name = "nohref"


class Area(AttrsMixin, XHTMLElement):

    """Client-side image map area
    ::

            <!ELEMENT AREA - O EMPTY               -- client-side image map area -->
            <!ATTLIST AREA
              %attrs;                              -- %coreattrs, %i18n, %events --
              shape       %Shape;        rect      -- controls interpretation of coords --
              coords      %Coords;       #IMPLIED  -- comma-separated list of lengths --
              href        %URI;          #IMPLIED  -- URI for linked resource --
              target      %FrameTarget;  #IMPLIED  -- render in this frame --
              nohref      (nohref)       #IMPLIED  -- this region has no action --
              alt         %Text;         #REQUIRED -- short description --
              tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
              accesskey   %Character;    #IMPLIED  -- accessibility key character --
              onfocus     %Script;       #IMPLIED  -- the element got the focus --
              onblur      %Script;       #IMPLIED  -- the element lost the focus --
              >"""
    XMLNAME = (XHTML_NAMESPACE, 'area')
    XMLATTR_shape = ('shape', Shape.DecodeLowerValue, Shape.EncodeValue)
    XMLATTR_coords = ('coords', Coords, Coords.__unicode__)
    XMLATTR_href = ('href', DecodeURI, EncodeURI)
    XMLATTR_target = 'target'
    XMLATTR_nohref = ('noHRef', NoHRef.DecodeLowerValue, NoHRef.EncodeValue)
    XMLATTR_alt = 'alt'
    XMLATTR_tabindex = ('tabIndex', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_accesskey = 'accessKey'
    XMLATTR_onfocus = 'onFocus'
    XMLATTR_onblur = 'onBlur'
    XMLCONTENT = xmlns.ElementType.Empty

    def __init__(self, parent):
        super(Area, self).__init__(parent)
        self.alt = ""


class Link(AttrsMixin, HeadMiscMixin, XHTMLElement):

    """Media-independent link::

    <!ELEMENT LINK - O EMPTY               -- a media-independent link -->
    <!ATTLIST LINK
      %attrs;                              -- %coreattrs, %i18n, %events --
      charset     %Charset;      #IMPLIED  -- char encoding of linked resource --
      href        %URI;          #IMPLIED  -- URI for linked resource --
      hreflang    %LanguageCode; #IMPLIED  -- language code --
      type        %ContentType;  #IMPLIED  -- advisory content type --
      rel         %LinkTypes;    #IMPLIED  -- forward link types --
      rev         %LinkTypes;    #IMPLIED  -- reverse link types --
      media       %MediaDesc;    #IMPLIED  -- for rendering on these media --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'link')
    XMLATTR_charset = 'charset'
    XMLATTR_href = ('href', DecodeURI, EncodeURI)
    XMLATTR_hreflang = ('hrefLang', xsi.DecodeName, xsi.EncodeName)
    XMLATTR_type = 'type'
    XMLATTR_rel = ('rel', ValidateLinkType, None, list)
    XMLATTR_rev = ('rev', ValidateLinkType, None, list)
    XMLATTR_media = ('media', MediaDesc, MediaDesc.__unicode__)
    XMLCONTENT = xmlns.ElementType.Empty


class MultiLength(LengthType):

    """MultiLength type from HTML.

    "A relative length has the form "i*", where "i" is an integer... ...The
    value "*" is equivalent to "1*".

    ::
            <!ENTITY % MultiLength "CDATA" -- pixel, percentage, or relative -->"""

    Relative = 2
    """data constant used to indicate relative (multilength) co-ordinates"""

    def __init__(self, value, valueType=None):
        if isinstance(value, LengthType):
            super(MultiLength, self).__init__(value, valueType)
        elif type(value) in StringTypes:
            try:
                strValue = value.strip()
                if "*" in strValue:
                    valueType = MultiLength.Relative
                    strValue = strValue[0:strValue.index("*")]
                    if strValue:
                        self.value = int(strValue)
                        if v < 0:
                            raise ValueError
                    else:
                        self.value = 1
                    self.type = valueType
            except ValueError:
                raise XHTMLValidityError(
                    "Failed to read MultiLength from %s" % value)
        else:
            super(MultiLength, self).__init__(value, valueType)

    def __str__(self):
        """Overridden to add "*" handling."""
        if self.type == MultiLength.Relative:
            return str(self.value) + '*'
        else:
            return super(MultiLength, self).__str__()

    def __unicode__(self):
        """Overridden to add "*" handling."""
        if self.type == LengthType.Relative:
            return unicode(self.value) + '*'
        else:
            return super(MultiLength, self).__unicode__()

    def GetValue(self, dim=None, multiTotal=1):
        """Extends :py:meth:`LengthType.GetValue` to handle relative dimension
        calculations.

        For relative lengths *dim* is the remaining space to be shared.

        *multiTotal* is the sum of all MultiLengths to share between.  It
        defaults to 1.  If this MultiLength is relative and it's value exceeds
        multiTotal all of the remaining dimension is returned."""
        if self.type == self.Relative:
            if dim is None:
                raise ValueError("Relative length without dimension")
            elif self.value > multiTotal:
                return dim
            else:
                return (self.value * dim) // multiTotal
        else:
            return super(MultiLength, self).GetValue(dim)


class MultiLengths(object):

    """Behaves like a lists of MultiLengths
    ::
            <!ENTITY % MultiLengths "CDATA" -- comma-separated list of MultiLength -->"""

    def __init__(self, values=None):
        #: a list of :py:class:`MultiLength` values
        self.values = []
        if values:
            if type(values) in StringTypes:
                if ',' in values:
                    self.values = map(
                        lambda x: MultiLength(x.strip()), value.split(','))
            else:
                for v in values:
                    if isinstance(v, MultiLength):
                        self.values.append(v)
                    else:
                        self.values.append(MultiLength(v))

    def __unicode__(self):
        """Formats the Coords as comma-separated unicode string of Length values."""
        return string.join(map(lambda x: unicode(x), self.values), u',')

    def __str__(self):
        """Formats the Coords as a comma-separated string of Length values."""
        return string.join(map(lambda x: str(x), self.values), ',')

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __setitem__(self, index, value):
        if isinstance(value, MultiLength):
            self.values[index] = value
        else:
            self.values[index] = MultiLength(value)

    def __iter__(self):
        return iter(self.values)


"""Pixels is just handled directly using xsi integer concept
	::
		<!ENTITY % Pixels "CDATA" -- integer representing length in pixels -->"""


class IAlign(xsi.Enumeration):

    """Values for image alignment
    ::

            <!ENTITY % IAlign "(top|middle|bottom|left|right)" -- center? -->	"""
    decode = {
        'top': 1,
        'middle': 2,
        'bottom': 3,
        'left': 4,
        'right': 5
    }
xsi.MakeEnumeration(IAlign)


class IsMap(NamedBoolean):

    """Used for the ismap attribute."""
    name = "ismap"


class Img(AttrsMixin, SpecialMixin, XHTMLElement):

    """Represents the <img> element::

    <!ELEMENT IMG - O EMPTY                -- Embedded image -->
    <!ATTLIST IMG
      %attrs;                              -- %coreattrs, %i18n, %events --
      src         %URI;          #REQUIRED -- URI of image to embed --
      alt         %Text;         #REQUIRED -- short description --
      longdesc    %URI;          #IMPLIED  -- link to long description
                                                                                      (complements alt) --
      name        CDATA          #IMPLIED  -- name of image for scripting --
      height      %Length;       #IMPLIED  -- override height --
      width       %Length;       #IMPLIED  -- override width --
      usemap      %URI;          #IMPLIED  -- use client-side image map --
      ismap       (ismap)        #IMPLIED  -- use server-side image map --
      align       %IAlign;       #IMPLIED  -- vertical or horizontal alignment --
      border      %Pixels;       #IMPLIED  -- link border width --
      hspace      %Pixels;       #IMPLIED  -- horizontal gutter --
      vspace      %Pixels;       #IMPLIED  -- vertical gutter --
      >
"""
    XMLNAME = (XHTML_NAMESPACE, 'img')
    XMLATTR_src = ('src', DecodeURI, EncodeURI)
    XMLATTR_alt = 'alt'
    XMLATTR_longdesc = ('longdesc', DecodeURI, EncodeURI)
    XMLATTR_name = 'name'
    XMLATTR_height = ('height', LengthType, LengthType.__unicode__)
    XMLATTR_width = ('width', LengthType, LengthType.__unicode__)
    XMLATTR_usemap = ('usemap', DecodeURI, EncodeURI)
    XMLATTR_ismap = ('ismap', IsMap.DecodeLowerValue, IsMap.EncodeValue)
    XMLATTR_align = ('align', Align.DecodeLowerValue, Align.EncodeValue)
    XMLATTR_border = ('border', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_border = ('hspace', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_border = ('vspace', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLCONTENT = xmlns.ElementType.Empty

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.src = None
        self.alt = ''

    def AddToCPResource(self, cp, resource, beenThere):
        if isinstance(self.src, uri.FileURL):
            f = beenThere.get(str(self.src), None)
            if f is None:
                f = cp.FileCopy(resource, self.src)
                beenThere[str(self.src)] = f
            newSrc = f.ResolveURI(f.href)
            # Finally, we need change our src attribute
            self.src = self.RelativeURI(newSrc)


#
#		TODO....  remaining refactoring
#


class HR(BlockMixin, XHTMLElement):
    # <!ELEMENT HR - O EMPTY -- horizontal rule -->
    XMLNAME = (XHTML_NAMESPACE, 'hr')
    XMLCONTENT = xmlns.ElementType.Empty


class Ins(AttrsMixin, FlowContainer):

    """Represents the INS element::

    <!-- INS/DEL are handled by inclusion on BODY -->
    <!ELEMENT (INS|DEL) - - (%flow;)*      -- inserted text, deleted text -->
    <!ATTLIST (INS|DEL)
      %attrs;                              -- %coreattrs, %i18n, %events --
      cite        %URI;          #IMPLIED  -- info on reason for change --
      datetime    %Datetime;     #IMPLIED  -- date and time of change --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'ins')
    XMLATTR_cite = ('cite', DecodeURI, EncodeURI)
    XMLATTR_datetime = ('dateTime', xsi.DecodeDateTime, xsi.EncodeDateTime)
    XMLCONTENT = xmlns.XMLMixedContent


class Del(FlowContainer):

    """Represents the DEL element::

    <!-- INS/DEL are handled by inclusion on BODY -->
    <!ELEMENT (INS|DEL) - - (%flow;)*      -- inserted text, deleted text -->
    <!ATTLIST (INS|DEL)
      %attrs;                              -- %coreattrs, %i18n, %events --
      cite        %URI;          #IMPLIED  -- info on reason for change --
      datetime    %Datetime;     #IMPLIED  -- date and time of change --
      >"""
    XMLNAME = (XHTML_NAMESPACE, 'del')
    XMLATTR_datetime = ('dateTime', xsi.DecodeDateTime, xsi.EncodeDateTime)
    XMLCONTENT = xmlns.XMLMixedContent


class List(BlockMixin, XHTMLElement):
    # <!ENTITY % list "UL | OL">

    def GetChildClass(self, stag_class):
        """If we get raw data in this context we assume an LI even though STag is compulsory."""
        if stag_class is None or issubclass(stag_class, FlowMixin):
            return LI
        elif issubclass(stag_class, LI) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


# Text Elements

class Blockquote(BlockMixin, XHTMLElement):
    # <!ELEMENT BLOCKQUOTE - - (%block;|SCRIPT)+ -- long quotation -->
    XMLNAME = (XHTML_NAMESPACE, 'blockquote')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """If we get raw data in this context we assume a P to move closer to strict DTD
        (loose DTD allows any flow so raw data would be OK)."""
        if stag_class is None:
            return P
        elif issubclass(stag_class, (BlockMixin, Script)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


class Heading(BlockMixin, InlineContainer):
    # <!ENTITY % heading "H1|H2|H3|H4|H5|H6">
    pass


class H1(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h1')
    XMLCONTENT = xmlns.XMLMixedContent


class H2(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h2')
    XMLCONTENT = xmlns.XMLMixedContent


class H3(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h3')
    XMLCONTENT = xmlns.XMLMixedContent


class H4(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h4')
    XMLCONTENT = xmlns.XMLMixedContent


class H5(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h5')
    XMLCONTENT = xmlns.XMLMixedContent


class H6(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h6')
    XMLCONTENT = xmlns.XMLMixedContent


class P(BlockMixin, InlineContainer):
    # <!ELEMENT P - O (%inline;)*            -- paragraph -->
    XMLNAME = (XHTML_NAMESPACE, 'p')
    XMLCONTENT = xmlns.XMLMixedContent

    def GetChildClass(self, stag_class):
        """End tag can be omitted."""
        if stag_class and issubclass(stag_class, InlineMixin):
            return stag_class
        else:
            return None


class Pre(BlockMixin, InlineContainer):
    # <!ENTITY % pre.exclusion "IMG|OBJECT|BIG|SMALL|SUB|SUP">
    # <!ELEMENT PRE - - (%inline;)* -(%pre.exclusion;) -- preformatted text -->
    XMLNAME = (XHTML_NAMESPACE, 'pre')
    XMLCONTENT = xmlns.XMLMixedContent

    def PrettyPrint(self):
        return False


class Q(SpecialMixin, InlineContainer):
    # <!ELEMENT Q - - (%inline;)*            -- short inline quotation -->
    XMLNAME = (XHTML_NAMESPACE, 'q')
    XMLCONTENT = xmlns.XMLMixedContent


# List Elements

class DL(BlockMixin, XHTMLElement):
    # <!ELEMENT DL - - (DT|DD)+              -- definition list -->
    XMLNAME = (XHTML_NAMESPACE, 'dl')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """If we get raw data in this context we assume a DD"""
        if stag_class is None:
            return DD
        elif issubclass(stag_class, (DT, DD)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


class DT(InlineContainer):
    # <!ELEMENT DT - O (%inline;)*           -- definition term -->
    XMLNAME = (XHTML_NAMESPACE, 'dt')
    XMLCONTENT = xmlns.XMLMixedContent

    def GetChildClass(self, stag_class):
        """End tag can be omitted."""
        if stag_class and issubclass(stag_class, InlineMixin):
            return stag_class
        else:
            return None


class DD(FlowContainer):
    # <!ELEMENT DD - O (%flow;)*             -- definition description -->
    XMLNAME = (XHTML_NAMESPACE, 'dd')
    XMLCONTENT = xmlns.XMLMixedContent


class OL(List):
    # <!ELEMENT OL - - (LI)+                 -- ordered list -->
    XMLNAME = (XHTML_NAMESPACE, 'ol')
    XMLCONTENT = xmlns.ElementType.ElementContent


class UL(List):
    # <!ELEMENT UL - - (LI)+                 -- ordered list -->
    XMLNAME = (XHTML_NAMESPACE, 'ul')
    XMLCONTENT = xmlns.ElementType.ElementContent


class LI(FlowContainer):
    # <!ELEMENT LI - O (%flow;)*             -- list item -->
    XMLNAME = (XHTML_NAMESPACE, 'li')
    XMLCONTENT = xmlns.XMLMixedContent


# Form Elements

class Method(xsi.Enumeration):

    """HTTP method used to submit a form.  Usage example::

            Method.POST

    Note that::

            Method.DEFAULT == GET

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'GET': 1,
        'POST': 2
    }
xsi.MakeEnumeration(Method, "GET")


class Form(AttrsMixin, BlockMixin, BlockContainer):

    """Represents the form element::

    <!ELEMENT FORM - - (%block;|SCRIPT)+ -(FORM) -- interactive form -->
    <!ATTLIST FORM
      %attrs;                              -- %coreattrs, %i18n, %events --
      action      %URI;          #REQUIRED -- server-side form handler --
      method      (GET|POST)     GET       -- HTTP method used to submit the form--
      enctype     %ContentType;  "application/x-www-form-urlencoded"
      accept      %ContentTypes; #IMPLIED  -- list of MIME types for file upload --
      name        CDATA          #IMPLIED  -- name of form for scripting --
      onsubmit    %Script;       #IMPLIED  -- the form was submitted --
      onreset     %Script;       #IMPLIED  -- the form was reset --
      accept-charset %Charsets;  #IMPLIED  -- list of supported charsets --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'form')
    XMLATTR_action = ('action', DecodeURI, EncodeURI)
    XMLATTR_method = ('method', Method.DecodeUpperValue, Method.EncodeValue)
    XMLATTR_enctype = 'enctype'
    XMLATTR_accept = 'accept'
    XMLATTR_name = 'name'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        BlockContainer.__init__(self, parent)
        self.action = None
        self.method = Method.DEFAULT
        self.enctype = "application/x-www-form-urlencoded"


class Label(FormCtrlMixin, InlineContainer):

    """Label element::

    <!ELEMENT LABEL - - (%inline;)* -(LABEL) -- form field label text -->
    <!ATTLIST LABEL
      %attrs;                              -- %coreattrs, %i18n, %events --
      for         IDREF          #IMPLIED  -- matches field ID value --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      onfocus     %Script;       #IMPLIED  -- the element got the focus --
      onblur      %Script;       #IMPLIED  -- the element lost the focus --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'label')
    XMLCONTENT = xmlns.XMLMixedContent


class InputType(xsi.Enumeration):

    """The type of widget needed for an input element.  Usage example::

            InputType.radio

    Note that::

            InputType.DEFAULT == InputType.text

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'text': 1,
        'password': 2,
        'checkbox': 3,
        'radio': 4,
        'submit': 5,
        'reset': 6,
        'file': 7,
        'hidden': 8,
        'image': 9,
        'button': 10
    }
xsi.MakeEnumeration(InputType, "text")


class Checked(NamedBoolean):

    """Used for the checked attribute."""
    name = "checked"


class Disabled(NamedBoolean):

    """Used for the disabled attribute."""
    name = "disabled"


class ReadOnly(NamedBoolean):

    """Used for the readonly attribute."""
    name = "readonly"


class Input(FormCtrlMixin, AttrsMixin, XHTMLElement):

    """Represents the input element::

    <!-- attribute name required for all but submit and reset -->
    <!ELEMENT INPUT - O EMPTY              -- form control -->
    <!ATTLIST INPUT
      %attrs;                              -- %coreattrs, %i18n, %events --
      type        %InputType;    TEXT      -- what kind of widget is needed --
      name        CDATA          #IMPLIED  -- submit as part of form --
      value       CDATA          #IMPLIED  -- Specify for radio buttons and checkboxes --
      checked     (checked)      #IMPLIED  -- for radio buttons and check boxes --
      disabled    (disabled)     #IMPLIED  -- unavailable in this context --
      readonly    (readonly)     #IMPLIED  -- for text and passwd --
      size        CDATA          #IMPLIED  -- specific to each type of field --
      maxlength   NUMBER         #IMPLIED  -- max chars for text fields --
      src         %URI;          #IMPLIED  -- for fields with images --
      alt         CDATA          #IMPLIED  -- short description --
      usemap      %URI;          #IMPLIED  -- use client-side image map --
      ismap       (ismap)        #IMPLIED  -- use server-side image map --
      tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      onfocus     %Script;       #IMPLIED  -- the element got the focus --
      onblur      %Script;       #IMPLIED  -- the element lost the focus --
      onselect    %Script;       #IMPLIED  -- some text was selected --
      onchange    %Script;       #IMPLIED  -- the element value was changed --
      accept      %ContentTypes; #IMPLIED  -- list of MIME types for file upload --
      %reserved;                           -- reserved for possible future use --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'input')
    XMLATTR_type = ('type', InputType.DecodeLowerValue, InputType.EncodeValue)
    XMLATTR_name = 'name'
    XMLATTR_value = 'value'
    XMLATTR_checked = (
        'checked', Checked.DecodeLowerValue, Checked.EncodeValue)
    XMLATTR_disabled = (
        'disabled', Disabled.DecodeLowerValue, Disabled.EncodeValue)
    XMLATTR_readonly = (
        'readonly', ReadOnly.DecodeLowerValue, ReadOnly.EncodeValue)
    XMLATTR_size = 'size'
    XMLATTR_maxLength = ('maxLength', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_src = ('src', DecodeURI, EncodeURI)
    XMLATTR_alt = 'alt'
    XMLATTR_usemap = ('usemap', DecodeURI, EncodeURI)
    XMLATTR_ismap = ('ismap', IsMap.DecodeLowerValue, IsMap.EncodeValue)
    XMLATTR_tabindex = ('tabindex', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_accesskey = ('accesskey', DecodeCharacter, None)
    XMLATTR_onfocus = 'onfocus'
    XMLATTR_onblur = 'onblur'
    XMLATTR_onselect = 'onselect'
    XMLATTR_onchange = 'onchange'
    XMLATTR_accept = 'accept'

    XMLCONTENT = xmlns.ElementType.Empty

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.type = InputType.DEFAULT


class Select(AttrsMixin, FormCtrlMixin, XHTMLElement):

    """Select element::

    <!ELEMENT SELECT - - (OPTGROUP|OPTION)+ -- option selector -->
    <!ATTLIST SELECT
      %attrs;                              -- %coreattrs, %i18n, %events --
      name        CDATA          #IMPLIED  -- field name --
      size        NUMBER         #IMPLIED  -- rows visible --
      multiple    (multiple)     #IMPLIED  -- default is single selection --
      disabled    (disabled)     #IMPLIED  -- unavailable in this context --
      tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
      onfocus     %Script;       #IMPLIED  -- the element got the focus --
      onblur      %Script;       #IMPLIED  -- the element lost the focus --
      onchange    %Script;       #IMPLIED  -- the element value was changed --
      %reserved;                           -- reserved for possible future use --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'select')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.options = []

    def OptGroup(self):
        child = OptGroup(self)
        self.options.append(child)
        return child

    def Option(self):
        child = Option(self)
        self.options.append(child)
        return child

    def GetChildren(self):
        return iter(self.options)


class OptGroup(AttrsMixin, XHTMLElement):

    """OptGroup element::

    <!ELEMENT OPTGROUP - - (OPTION)+ -- option group -->
    <!ATTLIST OPTGROUP
      %attrs;                              -- %coreattrs, %i18n, %events --
      disabled    (disabled)     #IMPLIED  -- unavailable in this context --
      label       %Text;         #REQUIRED -- for use in hierarchical menus --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'optgroup')
    XMLATTR_label = 'label'
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.label = ''
        self.Option = []

    def GetChildren(self):
        return iter(self.Option)


class Option(XHTMLElement):

    """Option element::

    <!ELEMENT OPTION - O (#PCDATA)         -- selectable choice -->
    <!ATTLIST OPTION
      %attrs;                              -- %coreattrs, %i18n, %events --
      selected    (selected)     #IMPLIED
      disabled    (disabled)     #IMPLIED  -- unavailable in this context --
      label       %Text;         #IMPLIED  -- for use in hierarchical menus --
      value       CDATA          #IMPLIED  -- defaults to element content --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'option')
    XMLCONTENT = xmlns.XMLMixedContent


class TextArea(FormCtrlMixin, XHTMLElement):

    """TextArea element::

    <!ELEMENT TEXTAREA - - (#PCDATA)       -- multi-line text field -->
    <!ATTLIST TEXTAREA
      %attrs;                              -- %coreattrs, %i18n, %events --
      name        CDATA          #IMPLIED
      rows        NUMBER         #REQUIRED
      cols        NUMBER         #REQUIRED
      disabled    (disabled)     #IMPLIED  -- unavailable in this context --
      readonly    (readonly)     #IMPLIED
      tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      onfocus     %Script;       #IMPLIED  -- the element got the focus --
      onblur      %Script;       #IMPLIED  -- the element lost the focus --
      onselect    %Script;       #IMPLIED  -- some text was selected --
      onchange    %Script;       #IMPLIED  -- the element value was changed --
      %reserved;                           -- reserved for possible future use --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'textarea')
    XMLCONTENT = xmlns.XMLMixedContent


class FieldSet(AttrsMixin, BlockMixin, FlowContainer):

    """fieldset element::

    <!ELEMENT FIELDSET - - (#PCDATA,LEGEND,(%flow;)*) -- form control group -->
    <!ATTLIST FIELDSET
      %attrs;                              -- %coreattrs, %i18n, %events --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'fieldset')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        FlowContainer.__init__(self, parent)
        self.Legend = Legend(self)

    def GetChildren(self):
        yield self.Legend
        for child in FlowContainer.GetChildren(self):
            yield child

    def GetChildClass(self, stag_class):
        if stag_class is not None and issubclass(stag_class, Legend):
            return stag_class
        else:
            return FlowContainer.GetChildClass(self, stag_class)

    def ChildElement(self, childClass, name=None):
        if issubclass(childClass, Legend):
            return super(XHTMLElement, self).ChildElement(childClass, name)
        else:
            return FlowContainer.ChildElement(self, childClass, name)


class Legend(InlineContainer):

    """legend element::

    <!ELEMENT LEGEND - - (%inline;)*       -- fieldset legend -->

    <!ATTLIST LEGEND
      %attrs;                              -- %coreattrs, %i18n, %events --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'legend')
    XMLCONTENT = xmlns.XMLMixedContent


class ButtonType(xsi.Enumeration):

    """The type action required for a form button."""
    decode = {
        'button': 1,
        'submit': 2,
        'reset': 3
    }
xsi.MakeEnumeration(ButtonType, "submit")


class Button(AttrsMixin, FormCtrlMixin, FlowContainer):

    """button element::

    <!ELEMENT BUTTON - - (%flow;)* -(A|%formctrl;|FORM|FIELDSET) -- push button -->
    <!ATTLIST BUTTON
      %attrs;                              -- %coreattrs, %i18n, %events --
      name        CDATA          #IMPLIED
      value       CDATA          #IMPLIED  -- sent to server when submitted --
      type        (button|submit|reset) submit -- for use as form button --
      disabled    (disabled)     #IMPLIED  -- unavailable in this context --
      tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      onfocus     %Script;       #IMPLIED  -- the element got the focus --
      onblur      %Script;       #IMPLIED  -- the element lost the focus --
      %reserved;                           -- reserved for possible future use --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'button')
    XMLATTR_name = 'name'
    XMLATTR_value = 'value'
    XMLATTR_type = (
        'type', ButtonType.DecodeLowerValue, ButtonType.EncodeValue)
    XMLATTR_disabled = (
        'disabled', Disabled.DecodeLowerValue, Disabled.EncodeValue)
    XMLATTR_tabindex = ('tabindex', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLATTR_accesskey = ('accesskey', DecodeCharacter, None)
    XMLATTR_onfocus = 'onfocus'
    XMLATTR_onblur = 'onblur'
    XMLCONTENT = xmlns.XMLMixedContent

    def __init__(self, parent):
        FlowContainer.__init__(self, parent)
        self.type = ButtonType.DEFAULT

# Object Elements


class Declare(NamedBoolean):

    """Used for the declare attribute."""
    name = "declare"


class Object(AttrsMixin, SpecialMixin, HeadMiscMixin, XHTMLElement):

    """Represents the object element::

    <!ELEMENT OBJECT - - (PARAM | %flow;)*

    <!ATTLIST OBJECT
      %attrs;                              -- %coreattrs, %i18n, %events --
      declare     (declare)      #IMPLIED  -- declare but don't instantiate flag --
      classid     %URI;          #IMPLIED  -- identifies an implementation --
      codebase    %URI;          #IMPLIED  -- base URI for classid, data, archive--
      data        %URI;          #IMPLIED  -- reference to object's data --
      type        %ContentType;  #IMPLIED  -- content type for data --
      codetype    %ContentType;  #IMPLIED  -- content type for code --
      archive     CDATA          #IMPLIED  -- space-separated list of URIs --
      standby     %Text;         #IMPLIED  -- message to show while loading --
      height      %Length;       #IMPLIED  -- override height --
      width       %Length;       #IMPLIED  -- override width --
      usemap      %URI;          #IMPLIED  -- use client-side image map --
      name        CDATA          #IMPLIED  -- submit as part of form --
      tabindex    NUMBER         #IMPLIED  -- position in tabbing order --
      %reserved;                           -- reserved for possible future use --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'object')
    XMLATTR_declare = (
        'declare', Declare.DecodeLowerValue, Declare.EncodeValue)
    XMLATTR_classid = 'classid'
    XMLATTR_codebase = 'codebase'
    XMLATTR_data = ('data', DecodeURI, EncodeURI)
    XMLATTR_type = 'type'
    XMLATTR_codetype = 'codetype'
    XMLATTR_archive = 'archive'
    XMLATTR_archive = 'standby'
    XMLATTR_height = ('height', LengthType, LengthType.__unicode__)
    XMLATTR_width = ('width', LengthType, LengthType.__unicode__)
    XMLATTR_usemap = ('usemap', DecodeURI, EncodeURI)
    XMLATTR_name = 'name'
    XMLATTR_tabindex = ('tabindex', xsi.DecodeInteger, xsi.EncodeInteger)
    XMLCONTENT = xmlns.XMLMixedContent

    def GetChildClass(self, stag_class):
        """stag_class should not be None"""
        if stag_class is None:
            raise XHTMLError("Object: Unexpected None in GetChildClass")
        elif issubclass(stag_class, (Param, FlowMixin)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None

    def AddToCPResource(self, cp, resource, beenThere):
        if isinstance(self.data, uri.FileURL):
            f = beenThere.get(str(self.data), None)
            if f is None:
                f = cp.FileCopy(resource, self.data)
                beenThere[str(self.data)] = f
            newData = f.ResolveURI(f.href)
            self.data = self.RelativeURI(newData)


class Param(XHTMLElement):
    # <!ELEMENT PARAM - O EMPTY              -- named property value -->
    XMLNAME = (XHTML_NAMESPACE, 'param')
    XMLCONTENT = xmlns.ElementType.Empty

# Table Elements


class Table(BlockMixin, XHTMLElement):
    # <!ELEMENT TABLE - - (CAPTION?, (COL*|COLGROUP*), THEAD?, TFOOT?, TBODY+)>
    XMLNAME = (XHTML_NAMESPACE, 'table')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """PCDATA triggers the TBody"""
        if stag_class is None or issubclass(stag_class, TR):
            return TBody
        elif issubclass(stag_class, (Caption, Col, ColGroup, THead, TFoot, TBody)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


class Caption(InlineContainer):
    # <!ELEMENT CAPTION  - - (%inline;)*     -- table caption -->
    XMLNAME = (XHTML_NAMESPACE, 'caption')
    XMLCONTENT = xmlns.XMLMixedContent


class TRContainer(XHTMLElement):

    def GetChildClass(self, stag_class):
        """PCDATA or TH|TD trigger TR"""
        if stag_class is None or issubclass(stag_class, (TH, TD)):
            return TR
        elif issubclass(stag_class, (TR)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


class THead(TRContainer):
    # <!ELEMENT THEAD    - O (TR)+           -- table header -->
    XMLNAME = (XHTML_NAMESPACE, 'thead')
    XMLCONTENT = xmlns.ElementType.ElementContent


class TFoot(TRContainer):
    # <!ELEMENT TFOOT    - O (TR)+           -- table footer -->
    XMLNAME = (XHTML_NAMESPACE, 'tfoot')
    XMLCONTENT = xmlns.ElementType.ElementContent


class TBody(TRContainer):
    # <!ELEMENT TBODY    O O (TR)+           -- table body -->
    XMLNAME = (XHTML_NAMESPACE, 'tbody')
    XMLCONTENT = xmlns.ElementType.ElementContent


class ColGroup(XHTMLElement):
    # <!ELEMENT COLGROUP - O (COL)*          -- table column group -->
    XMLNAME = (XHTML_NAMESPACE, 'colgroup')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """PCDATA in ColGroup ends the ColGroup"""
        if stag_class is None:
            return None
        elif issubclass(stag_class, (Col)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


class Col(BlockMixin, XHTMLElement):
    # <!ELEMENT COL      - O EMPTY           -- table column -->
    XMLNAME = (XHTML_NAMESPACE, 'col')
    XMLCONTENT = xmlns.ElementType.Empty


class TR(XHTMLElement):
    # <!ELEMENT TR       - O (TH|TD)+        -- table row -->
    XMLNAME = (XHTML_NAMESPACE, 'tr')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def GetChildClass(self, stag_class):
        """PCDATA in TR starts a TD"""
        if stag_class is None:
            return TD
        elif issubclass(stag_class, (TH, TD)) or not issubclass(stag_class, XHTMLElement):
            return stag_class
        else:
            return None


class TH(FlowContainer):
    # <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
    XMLNAME = (XHTML_NAMESPACE, 'th')
    XMLCONTENT = xmlns.XMLMixedContent


class TD(FlowContainer):
    # <!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
    XMLNAME = (XHTML_NAMESPACE, 'td')
    XMLCONTENT = xmlns.XMLMixedContent


# Link Element

# Image Element


# Hypertext Element


# Frames

class FrameElement(XHTMLElement):
    pass


class Frameset(FrameElement):

    """Frameset element::

    <!ELEMENT FRAMESET - - ((FRAMESET|FRAME)+ & NOFRAMES?) -- window subdivision-->
    <!ATTLIST FRAMESET
      %coreattrs;                          -- id, class, style, title --
      rows        %MultiLengths; #IMPLIED  -- list of lengths,
                                                                                      default: 100% (1 row) --
      cols        %MultiLengths; #IMPLIED  -- list of lengths,
                                                                                      default: 100% (1 col) --
      onload      %Script;       #IMPLIED  -- all the frames have been loaded  -- 
      onunload    %Script;       #IMPLIED  -- all the frames have been removed -- 
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'frameset')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        FrameElement.__init__(self, parent)
        self.FrameElement = []
        self.NoFrames = None

    def GetChildren(self):
        for child in self.FrameElement:
            yield child
        if self.NoFrames:
            yield self.NoFrames


class Frame(FrameElement):

    """Frame element:
    <!-- reserved frame names start with "_" otherwise starts with letter -->
    <!ELEMENT FRAME - O EMPTY              -- subwindow -->
    <!ATTLIST FRAME
      %coreattrs;                          -- id, class, style, title --
      longdesc    %URI;          #IMPLIED  -- link to long description
                                                                                      (complements title) --
      name        CDATA          #IMPLIED  -- name of frame for targetting --
      src         %URI;          #IMPLIED  -- source of frame content --
      frameborder (1|0)          1         -- request frame borders? --
      marginwidth %Pixels;       #IMPLIED  -- margin widths in pixels --
      marginheight %Pixels;      #IMPLIED  -- margin height in pixels --
      noresize    (noresize)     #IMPLIED  -- allow users to resize frames? --
      scrolling   (yes|no|auto)  auto      -- scrollbar or none --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'frame')
    XMLCONTENT = xmlns.ElementType.Empty


class IFrame(SpecialMixin, FlowContainer):

    """Represents the iframe element::

    <!ELEMENT IFRAME - - (%flow;)*         -- inline subwindow -->
    <!ATTLIST IFRAME
      %coreattrs;                          -- id, class, style, title --
      longdesc    %URI;          #IMPLIED  -- link to long description
                                                                                      (complements title) --
      name        CDATA          #IMPLIED  -- name of frame for targetting --
      src         %URI;          #IMPLIED  -- source of frame content --
      frameborder (1|0)          1         -- request frame borders? --
      marginwidth %Pixels;       #IMPLIED  -- margin widths in pixels --
      marginheight %Pixels;      #IMPLIED  -- margin height in pixels --
      scrolling   (yes|no|auto)  auto      -- scrollbar or none --
      align       %IAlign;       #IMPLIED  -- vertical or horizontal alignment --
      height      %Length;       #IMPLIED  -- frame height --
      width       %Length;       #IMPLIED  -- frame width --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'iframe')
    XMLCONTENT = xmlns.XMLMixedContent


class NoFrames(FlowContainer):

    """Represents the NOFRAMES element::

    In a frameset document:
    <!ENTITY % noframes.content "(BODY) -(NOFRAMES)">

    In a regular document:	
    <!ENTITY % noframes.content "(%flow;)*">

    <!ELEMENT NOFRAMES - - %noframes.content;
     -- alternate content container for non frame-based rendering -->
    <!ATTLIST NOFRAMES
      %attrs;                              -- %coreattrs, %i18n, %events --
      >
    """

    def __init__(self, parent):
        FlowContainer.__init__(self, parent)
        self.Body = None

    def GetChildClass(self, stag_class):
        """In a FRAMESET document, any element in NOFRAMES introduces Body"""
        if self.FindParent(Frameset):
            return Body
        else:
            return stag_class
            if issubclass(stag_class, FlowMixin) or not issubclass(stag_class, XHTMLElement):
                return stag_class
            else:
                return None

    def GetChildren(self):
        if self.Body:
            yield Body
        else:
            for child in FlowContainer.GetChildren(self):
                yield child


# Document Head

class HeadContentMixin:

    """Mixin class for HEAD content elements::

            <!ENTITY % head.content "TITLE & BASE?">
    """
    pass


class Head(I18nMixin, XHTMLElement):

    """Represents the HTML head structure::

            <!ELEMENT HEAD O O (%head.content;) +(%head.misc;) -- document head -->
            <!ATTLIST HEAD
              %i18n;                               -- lang, dir --
              profile     %URI;          #IMPLIED  -- named dictionary of meta info --
              >
    """
    XMLNAME = (XHTML_NAMESPACE, 'head')
    XMLATTR_profile = ('profile', DecodeURI, EncodeURI)
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.Title = Title(self)
        self.Base = None
        self.HeadMiscMixin = []

    def GetChildClass(self, stag_class):
        if stag_class is None:
            # PCDATA in Head indicates end of Head, start of Body
            return None
        elif issubclass(stag_class, (HeadContentMixin, HeadMiscMixin, NoScript)):
            # We add NoScript for future HTML5 compatibility
            return stag_class
        else:
            # anything else terminates HEAD
            return None

    def GetChildren(self):
        yield self.Title
        if self.Base:
            yield self.Base
        for child in itertools.chain(
                self.HeadMiscMixin,
                XHTMLElement.GetChildren(self)):
            yield child

    def RenderText(self):
        return XHTMLElement.RenderText(self) + "\n\n"


class Title(I18nMixin, HeadContentMixin, XHTMLElement):

    """Represents the title element::

    <!ELEMENT TITLE - - (#PCDATA) -(%head.misc;) -- document title -->
    <!ATTLIST TITLE %i18n>
    """
    XMLNAME = (XHTML_NAMESPACE, 'title')
    XMLCONTENT = xmlns.XMLMixedContent


class Meta(I18nMixin, HeadMiscMixin, XHTMLElement):

    """Represents the meta element::

    <!ELEMENT META - O EMPTY               -- generic metainformation -->
    <!ATTLIST META
      %i18n;                               -- lang, dir, for use with content --
      http-equiv  NAME           #IMPLIED  -- HTTP response header name  --
      name        NAME           #IMPLIED  -- metainformation name --
      content     CDATA          #REQUIRED -- associated information --
      scheme      CDATA          #IMPLIED  -- select form of content --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'meta')
    XMLCONTENT = xmlns.ElementType.Empty


class Base(HeadContentMixin, XHTMLElement):

    """Represents the base element::

    <!ELEMENT BASE - O EMPTY               -- document base URI -->
    <!ATTLIST BASE
      href        %URI;          #REQUIRED -- URI that acts as base URI --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'base')
    XMLATTR_base = ('base', DecodeURI, EncodeURI)
    XMLCONTENT = xmlns.ElementType.Empty


class Style(I18nMixin, HeadMiscMixin, XHTMLElement):

    """Represents the style element::

    <!ELEMENT STYLE - - %StyleSheet        -- style info -->
    <!ATTLIST STYLE
      %i18n;                               -- lang, dir, for use with title --
      type        %ContentType;  #REQUIRED -- content type of style language --
      media       %MediaDesc;    #IMPLIED  -- designed for use with these media --
      title       %Text;         #IMPLIED  -- advisory title --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'style')
    XMLATTR_type = 'type'
    XMLATTR_media = 'media'
    XMLATTR_title = 'title'
    XMLCONTENT = xmlns.XMLMixedContent
    SGMLCONTENT = xmlns.SGMLCDATA

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.type = 'text/css'


class Script(SpecialMixin, HeadMiscMixin, XHTMLElement):

    """Represents the script element::

    <!ELEMENT SCRIPT - - %Script;          -- script statements -->
    <!ATTLIST SCRIPT
      charset     %Charset;      #IMPLIED  -- char encoding of linked resource --
      type        %ContentType;  #REQUIRED -- content type of script language --
      src         %URI;          #IMPLIED  -- URI for an external script --
      defer       (defer)        #IMPLIED  -- UA may defer execution of script --
      event       CDATA          #IMPLIED  -- reserved for possible future use --
      for         %URI;          #IMPLIED  -- reserved for possible future use --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'script')
    XMLCONTENT = xmlns.XMLMixedContent
    SGMLCONTENT = xmlns.SGMLCDATA


class NoScript(BlockMixin, FlowContainer):

    """Represents the noscript element::

    <!ELEMENT NOSCRIPT - - (%flow;)*
      -- alternate content container for non script-based rendering -->
    <!ATTLIST NOSCRIPT
      %attrs;                              -- %coreattrs, %i18n, %events --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'noscript')
    XMLCONTENT = xmlns.XMLMixedContent

    def ChildElement(self, childClass, name=None):
        if self.FindParent(Head) and issubclass(childClass, (Link, Style, Meta)):
            # HTML5 compatibility, bypass normal FlowContainer handling.
            return super(XHTMLElement, self).ChildElement(childClass, name)
        else:
            return FlowContainer.ChildElement(self, childClass, name)


# Document Body


# Document Structures

class HTML(I18nMixin, XHTMLElement):

    """Represents the HTML document strucuture::

            <!ENTITY % html.content "HEAD, BODY">

            <!ELEMENT HTML O O (%html.content;)    -- document root element -->
            <!ATTLIST HTML
              %i18n;                               -- lang, dir --
              >
    """
    XMLNAME = (XHTML_NAMESPACE, 'html')
    XMLCONTENT = xmlns.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.Head = Head(self)
        self.Body = Body(self)

    def GetChildClass(self, stag_class):
        """Overridden to ensure we always return either HEAD or BODY, we can accommodate any tag!"""
        if stag_class and issubclass(stag_class, (Head, HeadContentMixin, Style, Meta, Link)):
            # possibly missing STag for HEAD; we leave out Script
            return Head
        else:
            # Script, Object (and may be NoScript) are ambiguous but we infer
            # body by default
            return Body

    def GetChildren(self):
        yield self.Head
        yield self.Body


class HTMLParser(xmlns.XMLNSParser):

    def __init__(self, entity=None, xmlHint=False):
        xmlns.XMLNSParser.__init__(self, entity)
        self.xmlFlag = xmlHint
        """A flag that indicates if the parser is in xml mode."""

    def lookup_predefined_entity(self, name):
        codepoint = name2codepoint.get(name, None)
        if codepoint is None:
            return None
        else:
            return unichr(codepoint)

    def parse_prolog(self):
        """[22] prolog: parses the document prolog, including the XML declaration and dtd.

        We override this method to enable us to dynamically set the parser options
        based on the presence of an XML declaration or DOCTYPE."""
        production = "[22] prolog"
        if self.parse_literal('<?xml'):
            self.parse_xml_decl(True)
        else:
            self.declaration = None
            self.sgmlNamecaseGeneral = True
            self.sgmlOmittag = True
            self.sgmlContent = True
            self.dontCheckWellFormedness = True
        self.entity.KeepEncoding()
        # we inline parse_misc to capture all the white space
        s = []
        while True:
            if xml.is_s(self.the_char):
                s.append(self.the_char)
                self.next_char()
                continue
            elif self.parse_literal('<!--'):
                self.parse_comment(True)
                continue
            elif self.parse_literal('<?'):
                self.parse_pi(True)
                continue
            else:
                break
        if self.parse_literal('<!DOCTYPE'):
            self.parse_doctypedecl(True)
            self.parse_misc()
        else:
            self.dtd = xml.XMLDTD()
            if self.sgmlNamecaseGeneral:
                self.dtd.name = 'HTML'
                # no XML declaration, and no DOCTYPE, are we at the first
                # element?
                if self.the_char != '<':
                    # this document starts with character data but we want to fore
                    # any leading space to be included, as that is usually the
                    # intention of authors writing HTML fragments,
                    # particularly as they are typically in <![CDATA[ sections in the
                    # enclosing document, e.g.,
                    # <tag>Yes I<htmlFrag><![CDATA[ <b>did</b>]]></htmlFrag></tag>
                    # we do this by tricking the parser with a character
                    # reference
                    if s:
                        s[0] = "&#x%02X;" % ord(s[0])
                    self.buff_text(string.join(s, ''))
            else:
                self.dtd.name = 'html'


class XHTMLDocument(xmlns.XMLNSDocument):

    """Represents an HTML document.

    Although HTML documents are not always represented using XML they can be,
    and therefore we base our implementation on the
    :class:`pyslet.xmlnames20091208.XMLNSDocument` class - a namespace-aware
    variant of the basic :class:`pyslet.xml20081126.XMLDocument` class."""

    classMap = {}
    """Data member used to store a mapping from element names to the classes
	used to represent them.  This mapping is initialized when the module is
	loaded."""

    DefaultNS = XHTML_NAMESPACE  # : the default namespace for HTML elements

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        self.p = None

    def XMLParser(self, entity):
        """We override the basic XML parser to use a custom parser that
        is intelligent about the use of omitted tags, elements defined
        to have CDATA content and other SGML-based variations.  If the
        document starts with an XML declaration then the normal XML
        parser is used instead.

        You won't normally need to call this method as it is invoked automatically
        when you call :meth:`pyslet.xml20081126.XMLDocument.Read`.

        The result is always a proper element hierarchy rooted in an HTML node,
        even if no tags are present at all the parser will construct an HTML
        document containing a single Div element to hold the parsed text."""
        xmlHint = XHTML_MIMETYPES.get(entity.mimetype, None)
        if xmlHint is not None:
            return HTMLParser(entity, xmlHint)
        else:
            raise XHTMLMimeTypeError(entity.mimetype)

    def GetChildClass(self, stag_class):
        """Always returns HTML."""
        return HTML

    def get_element_class(self, name):
        eClass = XHTMLDocument.classMap.get(name, None)
        if eClass is None:
            lcName = (name[0], name[1].lower())
            eClass = XHTMLDocument.classMap.get(lcName, xmlns.XMLNSElement)
        return eClass

xmlns.MapClassElements(XHTMLDocument.classMap, globals())


"""sgmlOmittag Feature:

Empty elements are handled by a simple XMLCONTENT attribute:

<!ELEMENT BASEFONT - O EMPTY           -- base font size -->
<!ELEMENT BR - O EMPTY                 -- forced line break -->
<!ELEMENT IMG - O EMPTY                -- Embedded image -->
<!ELEMENT HR - O EMPTY -- horizontal rule -->
<!ELEMENT INPUT - O EMPTY              -- form control -->
<!ELEMENT FRAME - O EMPTY              -- subwindow -->
<!ELEMENT ISINDEX - O EMPTY            -- single line prompt -->
<!ELEMENT BASE - O EMPTY               -- document base URI -->
<!ELEMENT META - O EMPTY               -- generic metainformation -->
<!ELEMENT AREA - O EMPTY               -- client-side image map area -->
<!ELEMENT LINK - O EMPTY               -- a media-independent link -->
<!ELEMENT PARAM - O EMPTY              -- named property value -->
<!ELEMENT COL      - O EMPTY           -- table column -->

Missing start tags must be handled in the context where these elements may occur:

<!ELEMENT BODY O O (%flow;)* +(INS|DEL) -- document body -->
<!ELEMENT TBODY    O O (TR)+           -- table body -->
<!ELEMENT HEAD O O (%head.content;) +(%head.misc;) -- document head -->
<!ELEMENT HTML O O (%html.content;)    -- document root element -->

Missing end tags must be handled in the elements themselves:

<!ELEMENT P - O (%inline;)*            -- paragraph -->
<!ELEMENT DT - O (%inline;)*           -- definition term -->
<!ELEMENT DD - O (%flow;)*             -- definition description -->
<!ELEMENT LI - O (%flow;)*             -- list item -->
<!ELEMENT OPTION - O (#PCDATA)         -- selectable choice -->
<!ELEMENT THEAD    - O (TR)+           -- table header -->
<!ELEMENT TFOOT    - O (TR)+           -- table footer -->
<!ELEMENT COLGROUP - O (COL)*          -- table column group -->
<!ELEMENT TR       - O (TH|TD)+        -- table row -->
<!ELEMENT (TH|TD)  - O (%flow;)*       -- table header cell, table data cell-->
"""
