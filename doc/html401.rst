HTML
====

.. py:module:: pyslet.html401

This module defines functions and classes for working with HTML
documents.  The version of the standard implemented is, loosely
speaking, the HTML 4.0.1 Specification: http://www.w3.org/TR/html401/

This module contains code that can help parse HTML documents into
classes based on the basic :mod:`xml` sub-package, acting as a gateway
to XHTML.  The module is designed to provide just enough HTML parsing to
support the use of HTML within other standards (such as Atom and QTI).

(X)HTML Documents
-----------------

The namespace to use in the delcaration of an XHTML document:
	
..	data:: XHTML_NAMESPACE

.. autoclass:: XHTMLDocument
	:members:
	:show-inheritance:

Because HTML 4 is an application of SGML, rather than XML, we need to
modify the basic XML parser to support the parsing of HTML documents.
This class is used automatically when reading an XHTMLDocument instance
from an entity with declared type that is anything other than text/xml.

.. autoclass:: HTMLParser
	:members:
	:show-inheritance:


Strict DTD
~~~~~~~~~~

The strict DTD describes the subset of HTML that is more compatible with
future versions and generally does not include handling of styling
directly but encourages the use of external style sheets.

The public ID to use in the declaration of an HTML document:

..	data:: HTML40_PUBLICID

The system ID to use in the declaration of an HTML document:

..  data:: HTML40_TRANSITIONAL_SYSTEMID


Transitional DTD
~~~~~~~~~~~~~~~~

The transitional DTD, often referred to as the loose DTD contains
additional elements and attribute to support backward compatibility. 
Although this module has been designed to support the the full set of
HTML elements attributes that are deprecated and only appear in the
loose DTD are not generally mapped to instance attributes in the
corresponding classes and where content models differ the classes may
enforce (of infer) the stricter model.  In particular, there are a
number of element that may support both inline and block elements in the
loose DTD but which are restricted to block elements in the strict DTD. 
On reading such a document an implied
:class:`Div` will be used to wrap the inline elements automatically.

The public ID for transitional documents:

..  data:: HTML40_TRANSITIONAL_PUBLICID

The system ID to use in the declaration of transitional documents:

..  data:: HTML40_TRANSITIONAL_SYSTEMID

It should be noted that it is customary to use the strict DTD in the
prolog of most HTML documents as this signals to the rendering agent
that the document adheres closely to the specification and generally
improves the appearance on web pages.  However, IFRAMEs are a popular
feature of HTML that require use of the transitional DTD.  In practice,
most content authors ignore this distinction.


Frameset DTD
~~~~~~~~~~~~

Although rarely used, there is a third form of HTML in which the body
of the document is replaced by a frameset.

The public ID for frameset documents:

..  data:: HTML40_FRAMESET_PUBLICID

The system ID to use in the declaration of frameset documents:

..  data:: HTML40_FRAMESET_SYSTEMID


(X)HTML Elements
----------------

All HTML elements are based on the :class:`XHTMLElement` class.  In
general, elements have their HTML-declared attributes mapped to
similarly names attributes of the instance.  A number of special
purposes types are defined to assist with attribute value validation
making it easier to reuse these concepts in other modules.  See
`Basic Types` for more information.

.. autoclass:: XHTMLMixin
	:members:
	:show-inheritance:


.. autoclass:: XHTMLElement
	:members:
	:show-inheritance:


Basic Types
-----------

The HTML DTD defines parameter entities to make the intention of each
attribute declaration clearer.  Theses definitions are often translated
into the similarly named classes enabling improved validation of
attribute values.  The special purpose types also make it easier to
parse and format information from and to attribute values.

A special note is required for attributes defined using a form like
this::

    option     (option)      #IMPLIED 

These are mapped to the boolean value True or the value None (or False)
indicating an absence of the option.  The HTML parser allows the SGML
markup minimisation feature so these values can be parsed from attribute
definitions such as::

    <INPUT disabled name="fred" value="stone">

All attributes of this form are based on the following abstract class.

.. autoclass:: NamedBoolean
	:members:
	:show-inheritance:

XML attributes generally use space separation for multiple values.  In
HTML there are a number of attributes that use comma-separation.  For
convenience that attributes are represented using a special purpose
tuple-like class.

.. autoclass:: CommaList
	:members:
	:show-inheritance:


Align
~~~~~

Attributes defined::

    <!ENTITY % align "align (left|center|right|justify)  #IMPLIED"
        -- default is left for ltr paragraphs, right for rtl --"""

may be represented using the following class.  These attributes are
limited to the loose DTD and this class is not used by any of the
element classes defined here.  It is provided for convenience only.

.. autoclass:: Align
	:show-inheritance:


Button type
~~~~~~~~~~~

The :class:`Button` element defines a type attribute::

     type   (button|submit|reset)   submit  -- for use as form button --

.. autoclass:: ButtonType
	:show-inheritance:


CDATA
~~~~~

Attributes defined to have CDATA are represented as character strings
or, where space separate values are indicated, lists of character
strings.


Character
~~~~~~~~~

Attributes defined to have type %Character::

    <!ENTITY % Character "CDATA" -- a single character from [ISO10646] -->

are parsed using the following function::

..  autofunc:: character_from_str


Charset
~~~~~~~

Atributes defined to have type %Charset or %Charsets::

    <!ENTITY % Charset "CDATA" -- a character encoding, as per [RFC2045] -->
    <!ENTITY % Charsets "CDATA"
        -- a space-separated list of character encodings, as per [RFC2045] -->

are left as character strings or lists of character strings respectively.


Checked
~~~~~~~

The :class:`Input` element defines::

    checked     (checked)   #IMPLIED    -- for radio buttons and check boxes --

.. autoclass:: Checked
	:members:
	:show-inheritance:


Clear
~~~~~

In the loose DTD the :class:`Br` element defines::

    clear       (left|all|right|none)   none    -- control of text flow --
    
The following class is provided as a convenience and is not used in the
implementation of the class.

.. autoclass:: Clear
	:members:
	:show-inheritance:


Color
~~~~~

.. autoclass:: Color
	:members:
	:show-inheritance:

As a convenience, pre-instantiated color constants are defined that
resolve to pre-initialised instances.

..  data:: BLACK

..  data:: GREEN

..  data:: SILVER

..  data:: LIME

..  data:: GRAY

..  data:: OLIVE

..  data:: WHITE

..  data:: YELLOW

..  data:: MAROON

..  data:: NAVY

..  data:: RED

..  data:: BLUE

..  data:: PURPLE

..  data:: TEAL

..  data:: FUCHSIA

..  data:: AQUA


ContentType
~~~~~~~~~~~

Attributes defined to have type %ContentType or %ContenTypes::

	<!ENTITY % ContentType "CDATA" -- media type, as per [RFC2045] --
	<!ENTITY % ContentTypes "CDATA"
	    -- comma-separated list of media types, as per [RFC2045]	-->	"""

are represented using instances of
:class:`pyslet.http.params.MediaType`.  The HTTP header convention of
comma-separation is used for multiple values (space being a valid
character inside a content type with parameters).  These are represented
using the tuple-like class:

.. autoclass:: ContentTypes
	:members:
	:show-inheritance:

 
Coordinate Values
~~~~~~~~~~~~~~~~~

Coordinate values are simple lists of Lengths.  In most cases Pyslet
doesn't define special types for lists of basic types but coordinates
are represented in attribute values using comma separation, not
space-separation.  As a result they require special processing in order
to be decoded/encoded correctly from/to XML streams.

..	autoclass:: Coords
	:members:
	:show-inheritance:
	:special-members:

The Coords class strays slightly into the territory of a rendering agent
by providing co-ordinate testing methods.  There is no intention to
extend this module to support HTML rendering, this functionality is
provided to support the server-side evaluation functions in the IMS QTI
response processing model.


Declare
~~~~~~~

.. autoclass:: Declare
	:members:
	:show-inheritance:

Defer
~~~~~

.. autoclass:: Defer
	:members:
	:show-inheritance:


Direction
~~~~~~~~~

Attributes defined to have type (ltr|rtl) are represented using integer
constants from the following Enumeration.

.. autoclass:: Direction
	:members:
	:show-inheritance:


Disabled
~~~~~~~~

.. autoclass:: Disabled
	:members:
	:show-inheritance:


Horizontal Cell Alignment
~~~~~~~~~~~~~~~~~~~~~~~~~

Attributes defined::

    align       (left|center|right|justify|char)    #IMPLIED

are used in table structures for cell alignment.

.. autoclass:: HAlign
	:members:
	:show-inheritance:


Image Alignment
~~~~~~~~~~~~~~~

The loose DTD supports alignment of images through IAlign::

    <!ENTITY % IAlign "(top|middle|bottom|left|right)" -- center? -->"""

This class is provided as a convenience and is not used by the classes
in this module.

.. autoclass:: IAlign
	:members:
	:show-inheritance:


InputType
~~~~~~~~~

The :class:`Input` class defines a type attribute based on the following
definition (though we prefer lower-case for better XML compatibility)::

    <!ENTITY % InputType    "(TEXT | PASSWORD | CHECKBOX | RADIO |
        SUBMIT | RESET | FILE | HIDDEN | IMAGE | BUTTON)"   >


.. autoclass:: InputType
	:members:
	:show-inheritance:


Disabled
~~~~~~~~

.. autoclass:: IsMap
	:members:
	:show-inheritance:


LanguageCodes
~~~~~~~~~~~~~

Attributes defined to have type %LanguageCode::

    <!ENTITY % LanguageCode "NAME" -- a language code, as per [RFC1766] -->

are represented as character strings using the functions
:func:`~pyslet.xml.xsdatatypes.name_from_str` and 
:func:`~pyslet.xml.xsdatatypes.name_to_str`.


Length Values
~~~~~~~~~~~~~

Attributes defined to have type %Length::

    <!ENTITY % Length "CDATA"
        -- nn for pixels or nn% for percentage length -->

are represented using instances of the following class.

..	autoclass:: Length
	:members:
	:show-inheritance:


LinkTypes
~~~~~~~~~

Attributes defined to have type %LinkTypes::

    <!ENTITY % LinkTypes "CDATA"
        -- space-separated list of link types handled directly -->

are represented as a list of *lower-cased* strings.


MediaDesc
~~~~~~~~~

Attributes defined to have type %MediaDesc::

    <!ENTITY % MediaDesc "CDATA"
        -- single or comma-separated list of media descriptors	-->

are represented by instancs of the following class.

.. autoclass:: MediaDesc
	:members:
	:show-inheritance:

Method
~~~~~~

.. autoclass:: Method
	:members:
	:show-inheritance:


MultiLength(s)
~~~~~~~~~~~~~~

.. autoclass:: MultiLength
	:members:
	:show-inheritance:

.. autoclass:: MultiLengths
	:members:
	:show-inheritance:


Multiple
~~~~~~~~

.. autoclass:: Multiple
	:members:
	:show-inheritance:


NoHRef
~~~~~~

.. autoclass:: NoHRef
	:members:
	:show-inheritance:


NoResize
~~~~~~~~

.. autoclass:: NoResize
	:members:
	:show-inheritance:


Param Value Types
~~~~~~~~~~~~~~~~~

.. autoclass:: ParamValueType
	:members:
	:show-inheritance:


ReadOnly
~~~~~~~~

.. autoclass:: ReadOnly
	:members:
	:show-inheritance:


Scope
~~~~~

Attributes defined to have type %Scope::

    <!ENTITY % Scope "(row|col|rowgroup|colgroup)">

are represented as integer constants from the following enumeration.

.. autoclass:: Scope
	:members:
	:show-inheritance:


Script
~~~~~~

Attributes defined to have type %Script::

    <!ENTITY % Script   "CDATA"         -- script expression -->

are *not* mapped.  You can of course obtain their character string
values using :meth:`~pyslet.xml.structures.Element.get_attribute` and
set them using
:meth:`~pyslet.xml.structures.Element.set_attribute`.


Scrolling
~~~~~~~~~

Attributes defined to have type::

    scrolling   (yes|no|auto)   auto      -- scrollbar or none --

are represented with:

.. autoclass:: Scrolling
	:members:
	:show-inheritance:


Selected
~~~~~~~~

.. autoclass:: Selected
	:members:
	:show-inheritance:


Shape
~~~~~

.. autoclass:: Shape
	:members:
	:show-inheritance:


StyleSheet
~~~~~~~~~~

Attributes defined to have type %StyleSheet::

    <!ENTITY % StyleSheet   "CDATA"         -- style sheet data -->

are left as uninterpreted character strings.


Text
~~~~

Attributes defined to have type %Text::

    <!ENTITY % Text "CDATA">

are left as interpreted character strings.


TFrame
~~~~~~

The definition::

    <!ENTITY % TFrame
        "(void|above|below|hsides|lhs|rhs|vsides|box|border)">

is modelled by:

.. autoclass:: TFrame
	:members:
	:show-inheritance:


TRules
~~~~~~

The definition::

    <!ENTITY % TRules "(none | groups | rows | cols | all)">

is modelled by:

.. autoclass:: TRules
	:members:
	:show-inheritance:


URI
~~~

Attributes defined to have type %URI::

    <!ENTITY % URI "CDATA"  -- a Uniform Resource Identifier -->

are represented using :class:`pyslet.rfc2396.URI`.  This class
automatically handles non-ASCII characters using the algorithm
recommended in Appendix B of the specification, which involves replacing
them with percent-encoded UTF-sequences.

When serialising these attributes we use the classes native string
conversion which results in ASCII characters only so we don't adhere to
the principal of using the ASCII encoding only at the latest possible
time.


Vertical Cell Alignment
~~~~~~~~~~~~~~~~~~~~~~~

The definition::

    <!ENTITY % cellvalign
        "valign     (top|middle|bottom|baseline) #IMPLIED"  >

is modelled by:

.. autoclass:: VAlign
	:members:
	:show-inheritance:


Attribute Mixin Classes
-----------------------

The DTD uses parameter entities to group related attribute definitions
for re-use by multiple elements.  We define mixin classes for each to
group together the corresponding custom attribute mappings.

..	autoclass:: AlignMixin
	:members:
	:show-inheritance:

..	autoclass:: BodyColorsMixin
	:members:
	:show-inheritance:

..	autoclass:: CellAlignMixin
	:members:
	:show-inheritance:

..	autoclass:: CoreAttrsMixin
	:members:
	:show-inheritance:

..	autoclass:: EventsMixin
	:members:
	:show-inheritance:

..	autoclass:: I18nMixin
	:members:
	:show-inheritance:

..	autoclass:: ReservedMixin
	:members:
	:show-inheritance:


The following classes extend the above to form established groups.

..	autoclass:: AttrsMixin
	:members:
	:show-inheritance:

..	autoclass:: TableCellMixin
	:members:
	:show-inheritance:


Content Mixin Classes
---------------------

The DTD uses parameter entities to group elements into major roles.  The
most important roles are block, inline and flow.  A block element is
something like a paragraph, a list or table.  An inline element is
something that represents a span of text (including data itself) and a
flow refers to either a block or inline.  We exploit these definitions
to create mixin classes that have no implementation but enable us to use
Python issubclass or isinstance to test and enforce the content model.  
It also enables this model to be extended by external classes that also
inherit from these basic classes to declare their role when inserted
into HTML documents.  This technique is used extensively by IMS QTI
where non-HTML markup is intermingled with HTML markup.

..	autoclass:: FlowMixin
	:members:
	:show-inheritance:

..	autoclass:: BlockMixin
	:members:
	:show-inheritance:

..	autoclass:: InlineMixin
	:members:
	:show-inheritance:

With these basic three classes we can go on to define a number of
derived mixin classes representing the remaining specialised element
groupings.

..	autoclass:: FormCtrlMixin
	:members:
	:show-inheritance:

..	autoclass:: HeadContentMixin
	:members:
	:show-inheritance:

..	autoclass:: HeadMiscMixin
	:members:
	:show-inheritance:

..	autoclass:: OptItemMixin
	:members:
	:show-inheritance:

..	autoclass:: PreExclusionMixin
	:members:
	:show-inheritance:

..	autoclass:: SpecialMixin
	:members:
	:show-inheritance:

..	autoclass:: TableColMixin
	:members:
	:show-inheritance:


Abstract Element Classes
------------------------

Unlike the mixin classes that identify an element as belonging to a
group the following abstract classes are used as base classes for
implementing the rules of various content models.  Just as classes can
be inline, block or (rarely just) flow many elements are declared to
contain either inline, block or flow children.  The following classes
are used as the base class in each case.

..	autoclass:: BlockContainer
	:members:
	:show-inheritance:

..	autoclass:: InlineContainer
	:members:
	:show-inheritance:

..	autoclass:: FlowContainer
	:members:
	:show-inheritance:


The following more specific abstract classes build on the above to
implement base classes for elements that are defined together using
parameter entities.

..	autoclass:: FlowContainer
	:members:
	:show-inheritance:

..	autoclass:: Heading
	:members:
	:show-inheritance:

..	autoclass:: InsDelInclusion
	:members:
	:show-inheritance:

..	autoclass:: Phrase
	:members:
	:show-inheritance:

Lists
~~~~~

..	autoclass:: List
	:members:
	:show-inheritance:

Tables
~~~~~~

..	autoclass:: TRContainer
	:members:
	:show-inheritance:

Frames
~~~~~~

The content model of FRAMESET allows either (nested) FRAMESET or FRAME
elements.  The following class acts as both base class and as a way to
identify the members of this group.

..	autoclass:: FrameElement
	:members:
	:show-inheritance:


Element Reference
-----------------

The classes that model each HTML element are documented here in
alphabetical order for completeness.

..	autoclass:: A
	:show-inheritance:

..	autoclass:: Abbr
	:show-inheritance:

..	autoclass:: Address
	:show-inheritance:

..	autoclass:: Area
	:show-inheritance:

..	autoclass:: B
	:show-inheritance:

..	autoclass:: Base
	:show-inheritance:

..	autoclass:: BaseFont
	:show-inheritance:

..	autoclass:: BDO
	:show-inheritance:

..	autoclass:: Big
	:show-inheritance:

..	autoclass:: Blockquote
	:show-inheritance:

..	autoclass:: Body
	:show-inheritance:

..	autoclass:: Br
	:show-inheritance:

..	autoclass:: Button
	:show-inheritance:

..	autoclass:: Caption
	:show-inheritance:

..	autoclass:: Center
	:show-inheritance:

..	autoclass:: Cite
	:show-inheritance:

..	autoclass:: Code
	:show-inheritance:

..	autoclass:: Col
	:show-inheritance:

..	autoclass:: ColGroup
	:show-inheritance:

..	autoclass:: DD
	:show-inheritance:

..	autoclass:: Del
	:show-inheritance:

..	autoclass:: Dfn
	:show-inheritance:

..	autoclass:: Div
	:show-inheritance:

..	autoclass:: DL
	:show-inheritance:

..	autoclass:: DT
	:show-inheritance:

..	autoclass:: Em
	:show-inheritance:

..	autoclass:: FieldSet
	:show-inheritance:

..	autoclass:: Font
	:show-inheritance:

..	autoclass:: Form
	:show-inheritance:

..	autoclass:: Frame
	:show-inheritance:

..	autoclass:: Frameset
	:show-inheritance:

..	autoclass:: H1
	:show-inheritance:

..	autoclass:: H2
	:show-inheritance:

..	autoclass:: H3
	:show-inheritance:

..	autoclass:: H4
	:show-inheritance:

..	autoclass:: H5
	:show-inheritance:

..	autoclass:: H6
	:show-inheritance:

..	autoclass:: Head
	:show-inheritance:

..	autoclass:: HR
	:show-inheritance:

..	autoclass:: HTML
	:show-inheritance:

..	autoclass:: HTMLFrameset
	:show-inheritance:

..	autoclass:: I
	:show-inheritance:

..	autoclass:: IFrame
	:show-inheritance:

..	autoclass:: Img
	:show-inheritance:

..	autoclass:: Input
	:show-inheritance:

..	autoclass:: Ins
	:show-inheritance:

..	autoclass:: IsIndex
	:show-inheritance:

..	autoclass:: Kbd
	:show-inheritance:

..	autoclass:: Label
	:show-inheritance:

..	autoclass:: Legend
	:show-inheritance:

..	autoclass:: LI
	:show-inheritance:

..	autoclass:: Link
	:show-inheritance:

..	autoclass:: Map
	:show-inheritance:

..	autoclass:: Meta
	:show-inheritance:

..	autoclass:: NoFrames
	:show-inheritance:

..	autoclass:: NoFramesFrameset
	:show-inheritance:

..	autoclass:: NoScript
	:show-inheritance:

..	autoclass:: Object
	:show-inheritance:

..	autoclass:: OL
	:show-inheritance:

..	autoclass:: OptGroup
	:show-inheritance:

..	autoclass:: Option
	:show-inheritance:

..	autoclass:: P
	:show-inheritance:

..	autoclass:: Param
	:show-inheritance:

..	autoclass:: Pre
	:show-inheritance:

..	autoclass:: Q
	:show-inheritance:

..	autoclass:: S
	:show-inheritance:

..	autoclass:: Samp
	:show-inheritance:

..	autoclass:: Script
	:show-inheritance:

..	autoclass:: Select
	:show-inheritance:

..	autoclass:: Small
	:show-inheritance:

..	autoclass:: Span
	:show-inheritance:

..	autoclass:: Strike
	:show-inheritance:

..	autoclass:: Strong
	:show-inheritance:

..	autoclass:: Style
	:show-inheritance:

..	autoclass:: Sub
	:show-inheritance:

..	autoclass:: Sup
	:show-inheritance:

..	autoclass:: Table
	:show-inheritance:

..	autoclass:: TBody
	:show-inheritance:

..	autoclass:: TD
	:show-inheritance:

..	autoclass:: TextArea
	:show-inheritance:

..	autoclass:: TFoot
	:show-inheritance:

..	autoclass:: TH
	:show-inheritance:

..	autoclass:: THead
	:show-inheritance:

..	autoclass:: Title
	:show-inheritance:

..	autoclass:: TR
	:show-inheritance:

..	autoclass:: TT
	:show-inheritance:

..	autoclass:: U
	:show-inheritance:

..	autoclass:: UL
	:show-inheritance:

..	autoclass:: Var
	:show-inheritance:


Exceptions
----------

..	autoclass:: XHTMLError
	:show-inheritance:

..	autoclass:: XHTMLValidityError
	:show-inheritance:

..	autoclass:: XHTMLError
	:show-inheritance:







