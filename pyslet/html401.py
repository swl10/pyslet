#! /usr/bin/env python

import itertools

from . import rfc2396 as uri
from .http.params import MediaType
from .pep8 import MigratedClass, old_method
from .py2 import (
    character,
    dict_keys,
    is_string,
    is_text,
    py2,
    range3,
    to_text,
    ul,
    UnicodeMixin)
from .unicode5 import CharClass
from .xml import structures as xml
from .xml import namespace as xmlns
from .xml import xsdatatypes as xsi

if py2:
    from htmlentitydefs import name2codepoint
else:
    from html.entities import name2codepoint


HTML40_PUBLICID = "-//W3C//DTD HTML 4.01//EN"
HTML40_SYSTEMID = "http://www.w3.org/TR/html4/strict.dtd"

HTML40_TRANSITIONAL_PUBLICID = "-//W3C//DTD HTML 4.01 Transitional//EN"
HTML40_TRANSITIONAL_SYSTEMID = \
    "http://www.w3.org/TR/1999/REC-html401-19991224/loose.dtd"

HTML40_FRAMESET_PUBLICID = "-//W3C//DTD HTML 4.01 Frameset//EN"
HTML40_FRAMESET_SYSTEMID = \
    "http://www.w3.org/TR/1999/REC-html401-19991224/frameset.dtd"

HTML40_HTMLlat1_SYSTEMID = \
    "http://www.w3.org/TR/1999/REC-html401-19991224/HTMLlat1.ent"
HTML40_HTMLsymbol_SYSTEMID = \
    "http://www.w3.org/TR/1999/REC-html401-19991224/HTMLsymbol.ent"
HTML40_HTMLspecial_SYSTEMID = \
    "http://www.w3.org/TR/1999/REC-html401-19991224/HTMLspecial.ent"

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"


ucomma = ul(',')
upercent = ul('%')
ustar = ul('*')


#
#   Boolean Flags
#   ------------

class NamedBoolean(MigratedClass):

    """An abstract class for named booleans

    This class is designed to make generating SGML-like single-value
    enumeration types easier, for example, attributes such as "checked"
    on <input>.

    The class is not designed to be instantiated but to act as a method
    of defining functions for decoding and encoding attribute values.

    The basic usage of this class is to derive a class from it with a
    single class member called 'name' which is the canonical
    representation of the name. You can then use it to call any of the
    following class methods to convert values between python Booleans
    and the appropriate string representations (None for False and the
    defined name for True)."""

    @classmethod
    @old_method('DecodeValue')
    def from_str(cls, src):
        """Decodes a string

        Returning True if it matches the name attribute and raises
        ValueError otherwise.  If src is None then False is returned."""
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
    @old_method('DecodeLowerValue')
    def from_str_lower(cls, src):
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
    @old_method('DecodeUpperValue')
    def from_str_upper(cls, src):
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
    @old_method('EncodeValue')
    def to_str(cls, value):
        """Encodes a named boolean value

        Returns either the defined name or None."""
        if value:
            return cls.name
        else:
            return None


#
# Attribute Types
# ---------------
#

class CommaList(UnicodeMixin):

    """A tuple-like list of strings

    Values can be compared with each other for equality, and with
    strings though the order of items is important.  They can be
    indexed, iterated and supports the *in* operator for value testing."""

    def __init__(self, src):
        self.values = tuple(x for x in src)

    @classmethod
    def from_str(cls, src):
        return cls(src.split(','))

    def __unicode__(self):
        return ul(",").join(self.values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __contains__(self, value):
        return value in self.values

    def __eq__(self, other):
        if is_text(other):
            other = self.from_str(other)
        elif isinstance(other, list):
            other = self.__class__(other)
        if isinstance(other, CommaList):
            return self.values == other.values
        else:
            return NotImplemented


class Align(xsi.Enumeration):

    decode = {
        'left': 1,
        'center': 2,
        'right': 3,
        'justify': 4
    }


class ButtonType(xsi.Enumeration):

    """Enumeration used for the types allowed for :class:`Button`
::

    ButtonType.DEFAULT == ButtonType.submit"""
    decode = {
        'button': 1,
        'submit': 2,
        'reset': 3
    }
    aliases = {
        None: 'submit'
    }


def character_from_str(src):
    """Returns the first character of src or None, if src is empty."""
    if len(src) > 0:
        return src[0]
    else:
        return None


class Checked(NamedBoolean):

    name = "checked"


class Clear(xsi.Enumeration):

    decode = {
        'left': 1,
        'all': 2,
        'right': 3,
        'none': 4
    }
    aliases = {
        None: 'none'
    }


class Color(UnicodeMixin):

    """Class to represent a color value
::

    <!ENTITY % Color "CDATA"
        -- a color using sRGB: #RRGGBB as Hex values -->

Instances can be created using either a string or a 3-tuple of sRGB
values.  The string is either in the #xxxxxx format for hex sRGB values
or it one of the "16 widely known color names" which are matched case
insentiviely.  The canonical representation used when converting back to
a character string is the #xxxxxx form.

Color instances can be compared for equality with each other and with
characcter string and are hashable but are not sortable.

For convenience, the standard colors are provided as module-level
constants."""

    known_colors = {
        "black": (0x00, 0x00, 0x00),
        "green": (0x00, 0x80, 0x00),
        "silver": (0xC0, 0xC0, 0xC0),
        "lime": (0x00, 0xFF, 0x00),
        "gray": (0x80, 0x80, 0x80),
        "olive": (0x80, 0x80, 0x00),
        "white": (0xFF, 0xFF, 0xFF),
        "yellow": (0xFF, 0xFF, 0x00),
        "maroon": (0x80, 0x00, 0x00),
        "navy": (0x00, 0x00, 0x80),
        "red": (0xFF, 0x00, 0x00),
        "blue": (0x00, 0x00, 0xFF),
        "purple": (0x80, 0x00, 0x80),
        "teal": (0x00, 0x80, 0x80),
        "fuchsia": (0xFF, 0x00, 0xFF),
        "aqua": (0x00, 0xFF, 0xFF)}

    def __init__(self, src):
        if is_text(src):
            # first, look it up
            src = src.strip().lower()
            if src in self.known_colors:
                self.r, self.g, self.b = self.known_colors[src]
            else:
                hex_digits = []
                for c in src:
                    if uri.is_hex(c):
                        hex_digits.append(c)
                if len(hex_digits) >= 6:
                    rgb = int(''.join(hex_digits), 16)
                    self.r = (rgb & 0xFF0000) >> 16
                    self.g = (rgb & 0xFF00) >> 8
                    self.b = rgb & 0xFF
                else:
                    self.r = self.g = self.b = 0
        elif isinstance(src, tuple):
            self.r, self.g, self.b = src
        else:
            raise ValueError

    def __eq__(self, other):
        if isinstance(other, Color):
            return (self.r, self.g, self.b) == (other.r, other.g, other.b)
        elif is_text(other):
            other = Color(other)
            return (self.r, self.g, self.b) == (other.r, other.g, other.b)
        else:
            return NotImplemented

    def __unicode__(self):
        return ul("#%02X%02X%02X") % (self.r, self.g, self.b)

    def __hash__(self):
        return hash((self.r, self.g, self.b))


BLACK = Color("black")
GREEN = Color("green")
SILVER = Color("silver")
LIME = Color("lime")
GRAY = Color("gray")
OLIVE = Color("olive")
WHITE = Color("white")
YELLOW = Color("yellow")
MAROON = Color("maroon")
NAVY = Color("navy")
RED = Color("red")
BLUE = Color("blue")
PURPLE = Color("purple")
TEAL = Color("teal")
FUCHSIA = Color("fuchsia")
AQUA = Color("aqua")


class ContentTypes(UnicodeMixin):

    """A tuple-like list of :class:`pyslet.http.params.MediaType`.

    Values can be compared with each other for equality, and with
    strings though the order of items is important.  They can be
    indexed, iterated and supports the *in* operator for value testing."""

    def __init__(self, src):
        self.values = tuple(x for x in src)

    @classmethod
    def from_str(cls, src):
        return cls(MediaType.from_str(v) for v in src.split(','))

    def __unicode__(self):
        return ul(",").join(to_text(v) for v in self.values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __contains__(self, value):
        return value in self.values

    def __eq__(self, other):
        if is_text(other):
            other = self.from_str(other)
        elif isinstance(other, list):
            other = self.__class__(other)
        if isinstance(other, ContentTypes):
            return self.values == other.values
        else:
            return NotImplemented


class Coords(UnicodeMixin):

    """Represents HTML Coords values
::

    <!ENTITY % Coords "CDATA" -- comma-separated list of lengths -->

Instances can be initialized from an iterable of
:py:class:`Length` instances or any object that can be used to
construct a Length.

The resulting object behaves like a tuple of Length instances, for
example::

    x=Coords("10, 50, 60%,75%")
    len(x) == 4
    str(x[3]) == "75%"

It supports conversion to string and can be compared with a string
directly or with a list or tuple of Length values."""

    def __init__(self, values=()):
        #: a list of :py:class:`Length` values
        self.values = []
        for v in values:
            if isinstance(v, Length):
                self.values.append(v)
            else:
                self.values.append(Length(v))

    @classmethod
    def from_str(cls, src):
        """Returns a new instance parsed from a string.

        The string must be formatted as per the HTML attribute
        definition, using comma-separation of values."""
        if src:
            return cls(Length.from_str(l.strip()) for l in src.split(','))
        else:
            return cls()

    def __unicode__(self):
        return ucomma.join(to_text(v) for v in self.values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __iter__(self):
        return iter(self.values)

    def __eq__(self, other):
        if is_text(other):
            other = self.from_str(other)
        elif isinstance(other, (list, tuple)):
            other = self.__class__(other)
        if isinstance(other, Coords):
            return self.values == other.values
        else:
            return NotImplemented

    def test_rect(self, x, y, width, height):
        """Tests an x,y point against a rect with these coordinates.

        HTML defines the rect co-ordinates as: left-x, top-y, right-x,
        bottom-y"""
        if len(self.values) < 4:
            raise ValueError(
                "Rect test requires 4 coordinates: %s" % str(self.values))
        x0 = self.values[0].resolve_value(width)
        y0 = self.values[1].resolve_value(height)
        x1 = self.values[2].resolve_value(width)
        y1 = self.values[3].resolve_value(height)
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

    def test_circle(self, x, y, width, height):
        """Tests an x,y point against a circle with these coordinates.

        HTML defines a circle as: center-x, center-y, radius.

        The specification adds the following note:

            When the radius value is a percentage value, user agents
            should calculate the final radius value based on the
            associated object's width and height. The radius should be
            the smaller value of the two."""
        if len(self.values) < 3:
            raise ValueError(
                "Circle test requires 3 coordinates: %s" % str(self.values))
        if width is None:
            if height is None:
                rmax = None
            else:
                rmax = height
        elif height is None:
            rmax = width
        elif width < height:
            rmax = width
        else:
            rmax = height
        dx = x - self.values[0].resolve_value(width)
        dy = y - self.values[1].resolve_value(height)
        r = self.values[2].resolve_value(rmax)
        return dx * dx + dy * dy <= r * r

    def test_poly(self, x, y, width, height):
        """Tests an x,y point against a poly with these coordinates.

        HTML defines a poly as: x1, y1, x2, y2, ..., xN, yN.

        The specification adds the following note:

            The first x and y coordinate pair and the last should be the
            same to close the polygon. When these coordinate values are
            not the same, user agents should infer an additional
            coordinate pair to close the polygon.

        The algorithm used is the "Ray Casting" algorithm described
        here: http://en.wikipedia.org/wiki/Point_in_polygon"""
        if len(self.values) < 6:
            # We need at least six coordinates - to make a triangle
            raise ValueError(
                "Poly test requires as least 3 coordinates: %s" %
                str(self.values))
        if len(self.values) % 2:
            # We also need an even number of coordinates!
            raise ValueError(
                "Poly test requires an even number of coordinates: %s" %
                str(self.values))
        # We build an array of y-values and clean up the missing end point
        # problem
        vertex = []
        i = 0
        last_x = None   # unused dummy to suppress flake8 warning
        for v in self.values:
            if i % 2:
                # this is a y coordinate
                vertex.append((last_x, v.resolve_value(height)))
            else:
                # this is an x coordinate
                last_x = v.resolve_value(width)
            i = i + 1
        if vertex[0][0] != vertex[-1][0] or vertex[0][1] != vertex[-1][1]:
            # first point is not the same as the last point
            vertex.append(vertex[0])
        # We now have an array of vertex coordinates ready for the Ray
        # Casting algorithm We start from negative infinity with a
        # horizontal ray passing through x,y
        n_crossings = 0
        for i in range3(len(vertex) - 1):
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
                    n_crossings += 1
                continue
            if x < x0 and x < x1:
                # This edge is off to the right, a miss
                continue
            # Finally, we have to calculate an intersection
            xhit = float(y - y0) * float(x1 - x0) / float(y1 - y0) + float(x0)
            if xhit <= float(x):
                n_crossings += 1
        return n_crossings % 2 != 0


class Declare(NamedBoolean):

    """Used for the declare attribute of :class:`Object`."""
    name = "declare"


class Defer(NamedBoolean):

    """Used for the defer attribute of :class:`Script`."""
    name = "defer"


class Direction(xsi.Enumeration):

    """Enumeration for weak/neutral text values."""
    decode = {
        'ltr': 1,
        'rtl': 2
    }


class Disabled(NamedBoolean):

    """Used for the disabled attribute of form controls."""
    name = "disabled"


class HAlign(xsi.Enumeration):

    """Values horizontal table cell alignment"""
    decode = {
        'left': 1,
        'center': 2,
        'right': 3,
        'justify': 4,
        'char': 5
    }


class IAlign(xsi.Enumeration):

    decode = {
        'top': 1,
        'middle': 2,
        'bottom': 3,
        'left': 4,
        'right': 5
    }


class InputType(xsi.Enumeration):

    """The type of widget needed for an input element
::

    InputType.DEFAULT == InputType.text"""
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
    aliases = {
        None: "text"
    }


class IsMap(NamedBoolean):

    """Used for the ismap attribute."""
    name = "ismap"


class Length(UnicodeMixin, MigratedClass):

    """Represents the HTML Length in pixels or as a percentage

    value
        Can be either an integer value or another Length instance.

    value_type (defaults to None)
        if value is an integer then value_type may be used to select a
        PIXEL or PERCENTAGE using the data constants defined below.  If
        value is a string then value_type argument is ignored as this
        information is determined by the format defined in the
        specification (a trailing % indicating a PERCENTAGE).

    Instances can be compared for equality but not ordered (as pixels
    and percentages are on different scales).  They do support non-zero
    test though, with 0% and 0 pixels both evaluating to False."""

    Pixel = 0
    PIXEL = 0
    """data constant used to indicate pixel co-ordinates (also available
    as Pixel for backwards compatibility)."""

    Percentage = 1
    PERCENTAGE = 1
    """data constant used to indicate relative (percentage) co-ordinates
    (also available as Percentage for backwards compatibility)."""

    def __init__(self, value, value_type=None, **kws):
        value_type = kws.get('valueType', value_type)
        if isinstance(value, Length):
            self.type = value.type
            """type is one of the the Length constants: PIXEL or PERCENTAGE"""
            self.value = value.value
            """value is the integer value of the length"""
        elif isinstance(value, (int, float)):
            self.type = Length.PIXEL if value_type is None else value_type
            self.value = value
        else:
            raise TypeError

    @classmethod
    def from_str(cls, src):
        """Returns a new instance parsed from a string"""
        try:
            str_value = src.strip()
            v = []
            value_type = None
            for c in str_value:
                if value_type is None and c.isdigit():
                    v.append(c)
                elif c == upercent:
                    value_type = Length.PERCENTAGE
                    break
                else:
                    value_type = Length.PIXEL
            if value_type is None:
                value_type = Length.PIXEL
            v = int(''.join(v))
            if v < 0:
                raise ValueError
            return cls(v, value_type)
        except ValueError:
            raise ValueError("Failed to read length from %s" % str_value)

    def __bool__(self):
        if self.value:
            return True
        else:
            return False

    __nonzero__ = __bool__

    def __eq__(self, other):
        if is_text(other):
            other = self.from_str(other)
        if isinstance(other, Length):
            return (self.type, self.value) == (other.type, other.value)
        else:
            return NotImplemented

    def __unicode__(self):
        if self.type == Length.PERCENTAGE:
            return to_text(self.value) + upercent
        else:
            return to_text(self.value)

    @old_method('GetValue')
    def resolve_value(self, dim=None):
        """Returns the absolute value of the Length

        dim
            The size of the dimension used for interpreting percentage
            values.  For example, if dim=640 and the value represents
            50% the value 320 will be returned."""
        if self.type == self.PERCENTAGE:
            if dim is None:
                raise ValueError("Relative length without dimension")
            else:
                return (self.value * dim + 50) // 100
        else:
            return self.value

    @old_method('Add')
    def add(self, value):
        """Adds *value* to the length.

        If value is another Length instance then its value is added to
        the value of this instances' value only if the types match.  If
        value is an integer it is assumed to be a value of pixel type -
        a mismatch raises ValueError."""
        if isinstance(value, Length):
            if self.type == value.type:
                self.value += value.value
            else:
                raise ValueError(
                    "Can't add lengths of different types: %s+%s" %
                    (str(self), str(value)))
        elif self.type == Length.PIXEL:
            self.value += value
        else:
            raise ValueError(
                "Can't add integer to non-pixel length value: %s+&i" %
                (str(self), value))


#: For backward compatibility
LengthType = Length


class MediaDesc(UnicodeMixin):

    """A set-like list of media for which a linked resource is tailored

    value
        An iterable (yielding strings)

    Values are reduced according to the algorithm described in the
    specification, so that "print and resolution > 90dpi" becomes
    "print". Descriptors are further reduced by making them lower case
    in keeping with their behaviour in CSS.

    Instances support the *in* operator, equality testing (the order of
    individual descriptors is ignored) and the boolean & and | operators
    for intersection and union operations always returning new
    instances. As a convenience, these binary operators will also work
    with a string argument which is converted to an instance using
    :meth:`from_str`.

    Instances are canonicalized when converting to string by
    ASCII sorting."""

    def __init__(self, value=None):
        self.values = set()
        if value is not None:
            for vstr in value:
                v = self.reduce_str(vstr)
                if v:
                    self.values.add(v)

    mclass = CharClass(('a', 'z'), ('A', 'Z'), ('0', '9'), '-')

    @classmethod
    def reduce_str(cls, m):
        m = m.strip()
        vlen = 0
        for c in m:
            if cls.mclass.test(c):
                vlen += 1
            else:
                break
        return m[:vlen].lower()

    @classmethod
    def from_str(cls, src):
        return cls(cls.reduce_str(m) for m in src.split(','))

    def __len__(self):
        return len(self.values)

    def __contains__(self, vstr):
        return self.reduce_str(vstr) in self.values

    def __eq__(self, other):
        if is_text(other):
            other = self.from_str(other)
        if isinstance(other, MediaDesc):
            return self.values == other.values
        else:
            return NotImplemented

    def __or__(self, other):
        if is_text(other):
            other = self.from_str(other)
        if isinstance(other, MediaDesc):
            # union operation
            return MediaDesc(itertools.chain((v1 for v1 in self.values),
                                             (v2 for v2 in other.values)))
        else:
            return NotImplemented

    __ror__ = __or__

    def __and__(self, other):
        if is_text(other):
            other = self.from_str(other)
        if isinstance(other, MediaDesc):
            # intersect operation
            return MediaDesc(v for v in self.values if v in other.values)
        else:
            return NotImplemented

    __rand__ = __and__

    def __unicode__(self):
        return ucomma.join(sorted(self.values))

    def __iter__(self):
        return iter(self.values)


class Method(xsi.Enumeration):

    """HTTP method used to submit a form
::

    Method.DEFAULT == Method.GET"""
    decode = {
        'GET': 1,
        'POST': 2
    }
    aliases = {
        None: 'GET'
    }


class MultiLength(Length):

    """MultiLength type from HTML.

    "A relative length has the form "i\*", where "i" is an integer... ...The
    value "\*" is equivalent to "1\*"::

        <!ENTITY % MultiLength  "CDATA"
            -- pixel, percentage, or relative -->

    Extends the base class :class:`Length`."""

    RELATIVE = 2
    """data constant used to indicate relative (multilength) co-ordinates"""

    def __init__(self, value, value_type=None, **kws):
        value_type = kws.get('valueType', value_type)
        if isinstance(value, Length):
            self.type = value.type
            self.value = value.value
        elif isinstance(value, (int, float)):
            self.type = MultiLength.PIXEL if value_type is None else value_type
            self.value = value
        else:
            raise TypeError

    @classmethod
    def from_str(cls, src):
        """Returns a new instance parsed from a string"""
        try:
            str_value = src.strip()
            v = []
            value_type = None
            for c in str_value:
                if value_type is None and c.isdigit():
                    v.append(c)
                elif c == upercent:
                    value_type = MultiLength.PERCENTAGE
                    break
                elif c == ustar:
                    value_type = MultiLength.RELATIVE
                else:
                    value_type = MultiLength.PIXEL
            if value_type is None:
                value_type = MultiLength.PIXEL
            v = int(''.join(v))
            if v < 0:
                raise ValueError
            return cls(v, value_type)
        except ValueError:
            raise ValueError("Failed to read multilength from %s" % str_value)

    def __unicode__(self):
        """Overridden to add "*" handling."""
        if self.type == Length.Relative:
            return to_text(self.value) + ustar
        else:
            return super(MultiLength, self).__unicode__()

    def resolve_value(self, dim=None, multi_total=0):
        """Extended to handle relative dimension calculations.

        dim:
            For relative lengths *dim* must be the remaining space to be
            shared after PIXEL and PERCENTAGE lengths have been deducted.

        multi_total
            The sum of all MultiLength values in the current scope.  If
            omitted (defaults to 0) or if the value passed is less than
            or equal to the relative value then dim is returned
            (allocating all remaining space to this multilength value).

        The behaviour for PIXEL and PERCENTAGE lengths is unchanged."""
        if self.type == self.RELATIVE:
            if dim is None:
                raise ValueError("Relative length without dimension")
            elif self.value > multi_total:
                return dim
            else:
                return (self.value * dim) // multi_total
        else:
            return super(MultiLength, self).resolve_value(dim)

    @classmethod
    def allocate_pixels(cls, dim, lengths):
        """Allocates pixels amongst multilength values

        dim
            The total number of pixels available.

        lengths
            A sequence of :class:`MultiLength` values.

        Returns a list of integer pixel values corresponding to the
        values in lengths."""
        space_remaining = dim
        relative_total = 0
        pround = 0
        imax = len(lengths)
        result = [0] * imax
        for i in range3(imax):
            l = lengths[i]
            if l.value_type == cls.PIXEL:
                result[i] = l.value
                space_remaining = space_remaining - l.value
            elif l.value_type == cls.PERCENTAGE:
                lvalue = (dim * l.value) // 100
                pround += (dim * l.value) % 100
                space_remaining = space_remaining - lvalue
                if pround > 50 and space_remaining:
                    lvalue += 1
                    space_remaining -= 1
                    pround -= 100
                result[i] = lvalue
            elif l.value_type == cls.RELATIVE:
                relative_total = relative_total + l.value
        if relative_total:
            rround = 0
            dim = space_remaining
            for i in range3(imax):
                l = lengths[i]
                if l.value_type == cls.RELATIVE:
                    lvalue = (dim * l.value) // relative_total
                    rround += (dim * l.value) % relative_total
                    space_remaining = space_remaining - lvalue
                    if rround > relative_total // 2 and space_remaining:
                        lvalue += 1
                        space_remaining -= 1
                        rround -= relative_total
                    result[i] = lvalue
        return result


class MultiLengths(UnicodeMixin):

    """Behaves like a tuple of MultiLengths
::

    <!ENTITY % MultiLengths     "CDATA"
        -- comma-separated list of MultiLength -->

Constructed from an iterable of values that can be passed to
:class:`MultiLength`\'s constructor."""

    def __init__(self, values):
        self.values = [MultiLength(v) for v in values]

    @classmethod
    def from_str(cls, src):
        return cls(MultiLength.from_str(s.strip()) for s in src.split(','))

    def __unicode__(self):
        return ucomma.join(to_text(v) for v in self.values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __iter__(self):
        return iter(self.values)


class Multiple(NamedBoolean):

    """For setting the multiple attribute of <select>."""
    name = "multiple"


class NoHRef(NamedBoolean):

    """For setting the nohref attribute."""
    name = "nohref"


class NoResize(NamedBoolean):

    """For setting the noresize attribute."""
    name = "noresize"


class ParamValueType(xsi.Enumeration):

    """Enumeration for the valuetype of object parmeters."""
    decode = {
        'data': 1,
        'ref': 2,
        'object': 3
    }


class ReadOnly(NamedBoolean):

    """Used for the readonly attribute."""
    name = "readonly"


class Scope(xsi.Enumeration):

    """Enumeration for the scope of table cells."""
    decode = {
        'row': 1,
        'col': 2,
        'rowgroup': 3,
        'colgroup': 4
    }


class Scrolling(xsi.Enumeration):

    """Enumeration for the scrolling of iframes."""
    decode = {
        'yes': 1,
        'no': 2,
        'auto': 3
    }
    aliases = {
        None: 'auto'
    }


class Selected(NamedBoolean):

    """Used for the selected attribute of <option>."""
    name = "selected"


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


class TFrame(xsi.Enumeration):

    """Enumeration for the framing rules of a table."""
    decode = {
        'void': 1,
        'above': 2,
        'below': 3,
        'hsides': 4,
        'lhs': 5,
        'rhs': 6,
        'vsides': 7,
        'box': 8,
        'border': 9
    }


class TRules(xsi.Enumeration):

    """Enumeration for the framing rules of a table."""
    decode = {
        'none': 1,
        'groups': 2,
        'rows': 3,
        'cols': 4,
        'all': 5
    }


class VAlign(xsi.Enumeration):

    """Enumeration for the vertical alignment of table cells"""
    decode = {
        'top': 1,
        'middle': 2,
        'bottom': 3,
        'baseline': 4
    }

#
#   Exceptions
#   ----------
#


class XHTMLError(Exception):

    """Abstract base class for errors in this module"""
    pass


class XHTMLValidityError(XHTMLError):

    """General error raised by HTML model constraints.

    The parser is very generous in attempting to interpret HTML but
    there some situations where it would be dangerous to infer the
    intent and this error is raised in those circumstances."""
    pass


class XHTMLMimeTypeError(XHTMLError):

    """Attempt to parse HTML from an unrecognized entity type"""
    pass


#
#   XHTML Elements
#   --------------
#

class XHTMLMixin(object):

    """An abstract class representing all HTML-like elements.

    This class is used to determine if an element should be treated as
    if it is HTML-like or if it is simply a foreign element from some
    unknown schema.

    HTML-like elements are subject to appropriate HTML content
    constraints, for example, block elements are not allowed to appear
    where inline elements are required.  Non-HTML-like elements are
    permitted more freely."""
    pass


class XHTMLElement(XHTMLMixin, xmlns.XMLNSElement):

    """A base class for XHTML elements."""
    XMLCONTENT = xml.XMLMixedContent

    def find_self_or_parent(self, parent_class):
        if isinstance(self, parent_class):
            return self
        else:
            return self.find_parent(parent_class)

    def check_model(self, child_class):
        """Checks the validity of adding a child element

        child_class
            The class of an element to be tested

        If an instance of child_class would cause a model violation then
        :class:`XHTMLValidityError` is raised.  This logic is factored
        into its own method to allow it to be used by :meth:`add_child`
        and :meth:`get_child_class`, both of which may need to make a
        determination of the legality of adding a child (in the latter
        case to determine if an element's end tag has been omitted).

        The default implementation checks the rules for the inclusion of
        the Ins and Del elements to prevent nesting and to ensure that
        they only appear within a Body instance.

        It checks that a form does not appear within another form.

        It also checks that the NOFRAMES element in a frameset document
        is not being nested.

        Generally speaking, derived classes add to this implemenation
        with element-specific rules based on the element's content model
        and do not need to override the :meth:`add_child`."""
        if issubclass(child_class, InsDelInclusion):
            if self.find_self_or_parent(InsDelInclusion):
                raise XHTMLValidityError(
                    "%s inside inclusion" % (child_class.__name__))
            if not self.find_self_or_parent(Body):
                raise XHTMLValidityError(
                    "%s outside Body" % (child_class.__name__))
        elif issubclass(child_class, Form):
            # can't nest or be contained in BUTTON
            if self.find_self_or_parent((Form, Button)):
                raise XHTMLValidityError("FORM in BUTTON or FORM")
        elif issubclass(child_class,
                        (A, FormCtrlMixin, IsIndex, FieldSet, IFrame)):
            # can't be inside BUTTON
            if self.find_self_or_parent(Button):
                raise XHTMLValidityError("%s in BUTTON" % child_class.__name__)
        elif issubclass(child_class, NoFramesFrameset):
            # only allowed in a FRAMESET, can't nest
            if self.find_self_or_parent(NoFramesFrameset):
                raise XHTMLValidityError("NOFRAMES in NOFRAMES")

    def add_child(self, child_class, name=None):
        """Overridden to call :meth:`check_model`"""
        self.check_model(child_class)
        return super(XHTMLElement, self).add_child(child_class, name)

    def add_to_cpresource(self, cp, resource, been_there):
        """See :py:meth:`pyslet.imsqtiv2p1.QTIElement.add_to_cpresource`  """
        for child in self.get_children():
            if hasattr(child, 'add_to_cpresource'):
                child.add_to_cpresource(cp, resource, been_there)

    @old_method('RenderHTML')
    def render_html(self, parent, profile, arg):
        """Renders this HTML element to an external document

        parent
            The parent node to attach a copy of this data too.

        profile
            A dictionary mapping the names of allowed HTML elements to a
            list of allowed attributes.  This allows the caller to
            filter out unwanted elements and attributes on a whitelist
            basis.  Warning: this argument is deprecated.

        arg
            Allows an additional positional argument to be passed
            through the HTML tree to any non-HTML nodes contained by
            it.  Warning: this argument is deprecated.

        The default implementation creates a node under parent if our
        name is in the profile."""
        if self.xmlname in profile:
            new_child = parent.add_child(self.__class__)
            alist = profile[self.xmlname]
            attrs = self.get_attributes()
            for aname in dict_keys(attrs):
                ns, name = aname
                if ns is None and name in alist:
                    # this one is included
                    new_child.set_attribute(aname, attrs[aname])
            for child in self.get_children():
                if is_text(child):
                    new_child.add_data(child)
                else:
                    child.render_html(new_child, profile, arg)

    def generate_plain_text(self):
        for child in self.get_children():
            if is_string(child):
                yield child
            elif isinstance(child, XHTMLElement):
                for ptext in child.generate_plain_text():
                    yield ptext
            # ignore elements of unknown type

    @old_method('RenderText')
    def plain_text(self):
        return ''.join(self.generate_plain_text())


#
#   Attribute Type Mixin Classes
#   ----------------------------

class AlignMixin(object):

    """Mixin class for (loose) align attributes
::

    <!ENTITY % align "
        align   (left|center|right|justify) #IMPLIED"
            -- default is left for ltr paragraphs, right for rtl --

These attributes are only defined by the loose DTD and are therefore
not mapped to attributes of the instance."""
    pass


class BodyColorsMixin(object):

    """Mixin class for (loose) body color attributes
::

    <!ENTITY % bodycolors
        "bgcolor    %Color;     #IMPLIED  -- document background color --
         text       %Color;     #IMPLIED  -- document text color --
         link       %Color;     #IMPLIED  -- color of links --
         vlink      %Color;     #IMPLIED  -- color of visited links --
         alink      %Color;     #IMPLIED  -- color of selected links --"
        >

These attributes are only defined by the loose DTD and are deprecated,
they are therefore not mapped to attributes of the instance."""
    pass


class CellAlignMixin(object):

    """Mixin class for table cell aignment attributes
::

    <!ENTITY % cellhalign
        "align      (left|center|right|justify|char)    #IMPLIED
         char       %Character;                         #IMPLIED
            -- alignment char, e.g. char=':' --
         charoff    %Length;                            #IMPLIED
            -- offset for alignment char --"
        >

    <!ENTITY % cellvalign
        "valign     (top|middle|bottom|baseline)        #IMPLIED">"""
    XMLATTR_align = ('align', HAlign.from_str_lower, to_text)
    XMLATTR_char = ('char', character_from_str, None)
    XMLATTR_charoff = ('charoff', Length.from_str, to_text)
    XMLATTR_valign = ('valign', VAlign.from_str_lower, to_text)


class CoreAttrsMixin(object):

    """Mixin class for core attributes
::

    <!ENTITY % coreattrs
        "id     ID             #IMPLIED -- document-wide unique id --
         class  CDATA          #IMPLIED -- space-separated list of classes --
         style  %StyleSheet;   #IMPLIED -- associated style info --
         title  %Text;         #IMPLIED -- advisory title --"
        >

The id attribute is declared in the DTD to be of type ID so is mapped to
the special unique ID attribute for special handling by
:class:`~pyslet.xml.structures.Element`.

The class attribute is mapped to the python attribute style_class to
avoid the python reserved name."""
    ID = (xmlns.NO_NAMESPACE, 'id')
    XMLATTR_class = ('style_class', None, None, list)
    XMLATTR_style = 'style'
    XMLATTR_title = 'title'


class EventsMixin(object):

    """Mixin class for event attributes
::

    <!ENTITY % events
        "onclick     %Script;   #IMPLIED
            -- a pointer button was clicked --
         ondblclick  %Script;   #IMPLIED
            -- a pointer button was double clicked--
         onmousedown %Script;   #IMPLIED
            -- a pointer button was pressed down --
         onmouseup   %Script;   #IMPLIED
            -- a pointer button was released --
         onmouseover %Script;   #IMPLIED
            -- a pointer was moved onto --
         onmousemove %Script;   #IMPLIED
            -- a pointer was moved within --
         onmouseout  %Script;   #IMPLIED
            -- a pointer was moved away --
         onkeypress  %Script;   #IMPLIED
            -- a key was pressed and released --
         onkeydown   %Script;   #IMPLIED
            -- a key was pressed down --
         onkeyup     %Script;   #IMPLIED
            -- a key was released --"
        >

Pyslet is not an HTML rendering engine and so no attribute mappings are
provided for these script hooks.  Their values can of course be obtained
using the generic get_attribute."""
    pass


class I18nMixin(object):

    """Mixin class for i18n attributes
::

    <!ENTITY % i18n
        "lang  %LanguageCode; #IMPLIED     -- language code --
         dir   (ltr|rtl)      #IMPLIED
            -- direction for weak/neutral text --">"""
    XMLATTR_lang = ('lang', xsi.name_from_str, xsi.name_to_str)
    XMLATTR_dir = ('dir', Direction.from_str_lower, Direction.to_str)

    def get_lang(self):
        """Replaces access to xml:lang

        If an element has set the HTML lang attribute we return this,
        otherwise we check if the element has set xml:lang and return
        that instead.

        :meth:`set_lang` is not modified, it always sets the xml:lang
        attribute."""
        if self.lang:
            return self.lang
        else:
            return super(I18nMixin, self).get_lang()


class ReservedMixin(object):

    """Attributes reserved for future use
::

    <!ENTITY % reserved
        "datasrc        %URI;       #IMPLIED
            -- a single or tabular Data Source --
         datafld        CDATA       #IMPLIED
            -- the property or column name --
         dataformatas   (plaintext|html)    plaintext
            -- text or html --"
        >

As these attributes are reserved for future no mappings are provided."""
    pass


class AttrsMixin(CoreAttrsMixin, I18nMixin, EventsMixin):

    """Mixin class for common attributes
::

    <!ENTITY % attrs "%coreattrs; %i18n; %events;">"""
    pass


class TableCellMixin(CellAlignMixin, AttrsMixin):

    """Attributes shared by TD and TH
::

    <!ATTLIST (TH|TD)       -- header or data cell --
        %attrs;         -- %coreattrs, %i18n, %events --
        abbr            %Text;      #IMPLIED
            -- abbreviation for header cell --
        axis            CDATA       #IMPLIED
            -- comma-separated list of related headers--
        headers         IDREFS      #IMPLIED
            -- list of id's for header cells --
        scope           %Scope;     #IMPLIED
            -- scope covered by header cells --
        rowspan         NUMBER      1
            -- number of rows spanned by cell --
        colspan         NUMBER      1
            -- number of cols spanned by cell --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;    -- vertical alignment in cells --
        nowrap          (nowrap)    #IMPLIED
            -- suppress word wrap --
        bgcolor         %Color;     #IMPLIED
            -- cell background color --
        width           %Length;    #IMPLIED
            -- width for cell --
        height          %Length;    #IMPLIED
            -- height for cell --
        >

The nowrap, bgcolor, width and height attributes are only defined in the
loose DTD and are not mapped."""
    XMLATTR_abbr = 'abbr'
    XMLATTR_axis = ('axis', CommaList.from_str, to_text)
    XMLATTR_headers = ('headers', xsi.name_from_str, xsi.name_to_str, list)
    XMLATTR_scope = ('scope', Scope.from_str_lower, Scope.to_str)
    XMLATTR_rowspan = ('rowspan', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_colspan = ('colspan', xsi.integer_from_str, xsi.integer_to_str)


#
#   Element Group Mixins
#   --------------------
#


class FlowMixin(XHTMLMixin):

    """Mixin class for flow elements
::

    <!ENTITY % flow "%block; | %inline;">
    """
    pass


class BlockMixin(FlowMixin):

    """Mixin class for block elements
::

    <!ENTITY % block "P | %heading; | %list; | %preformatted; | DL | DIV |
        NOSCRIPT | BLOCKQUOTE | FORM | HR | TABLE | FIELDSET | ADDRESS">
    """
    pass


class InlineMixin(FlowMixin):

    """Mixin class for inline elements
::

    <!ENTITY % inline "#PCDATA | %fontstyle; | %phrase; | %special; |
        %formctrl;">
    """
    pass


class FormCtrlMixin(InlineMixin):

    """Form controls are just another type of inline element
::

    <!ENTITY % formctrl "INPUT | SELECT | TEXTAREA | LABEL | BUTTON">"""
    pass


class HeadContentMixin(object):

    """Mixin class for HEAD content elements
::

    <!ENTITY % head.content     "TITLE & BASE?">
    """
    pass


class HeadMiscMixin(object):

    """Mixin class for head.misc elements
::

    <!ENTITY % head.misc    "SCRIPT|STYLE|META|LINK|OBJECT"
        -- repeatable head elements -->"""
    pass


class OptItemMixin(object):

    """Mixin class for (OPTGROUP|OPTION)"""
    pass


class PreExclusionMixin(object):

    """Mixin class for elements excluded from PRE
::

    <!ENTITY % pre.exclusion
        "IMG|OBJECT|APPLET|BIG|SMALL|SUB|SUP|FONT|BASEFONT">"""


class SpecialMixin(InlineMixin):

    """Specials are just another type of inline element.

    Strict DTD::

        <!ENTITY % special "A | IMG | OBJECT | BR | SCRIPT | MAP | Q | SUB |
            SUP | SPAN | BDO">

    Loose DTD::

        <!ENTITY % special "A | IMG | APPLET | OBJECT | FONT | BASEFONT | BR |
            SCRIPT | MAP | Q | SUB | SUP | SPAN | BDO | IFRAME">"""
    pass


class TableColMixin(object):

    """Mixin class for COL | COLGROUP elements."""
    pass


#
#   Abstract Element Classes
#   ------------------------
#

class BlockContainer(XHTMLElement):

    """Abstract class for all HTML elements that contain just %block;

    We support start-tag omission for inline data or elements by forcing
    an implied <div>.  We also support end-tag omission."""
    XMLCONTENT = xml.ElementType.ElementContent

    def check_model(self, child_class):
        super(BlockContainer, self).check_model(child_class)
        if issubclass(child_class, (BlockMixin, InsDelInclusion)) or \
                not issubclass(child_class, XHTMLMixin):
            # allow %block | INS | DEL or non-HTML elemenets
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected block" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        if issubclass(stag_class, (InlineMixin, str)):
            return Div
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # treat as missing end tag
            return None


class InlineContainer(XHTMLElement):

    """Abstract class for elements that contain inline elements

    Support end-tag omission."""
    XMLCONTENT = xml.XMLMixedContent

    def check_model(self, child_class):
        super(InlineContainer, self).check_model(child_class)
        if issubclass(child_class, PreExclusionMixin):
            # are we descended from pre?
            if self.find_self_or_parent(Pre):
                raise XHTMLValidityError(
                    "%s not allowed in %s, excluded in pre context" %
                    (child_class.__name__, self.__class__.__name__))
        if issubclass(child_class, Label):
            # are we descended from label? no label in label allowed
            if self.find_self_or_parent(Label):
                raise XHTMLValidityError(
                    "%s not allowed in %s, nested label" %
                    (child_class.__name__, self.__class__.__name__))
        if issubclass(child_class, FormCtrlMixin):
            # are we descended from label (again)? only one form control
            label = self.find_self_or_parent(Label)
            if label and sum(
                    1 for e in
                    label.find_children_depth_first(FormCtrlMixin)):
                raise XHTMLValidityError(
                    "%s not allowed in %s, multiple form controls in label" %
                    (child_class.__name__, self.__class__.__name__))
        if issubclass(child_class, (InlineMixin, InsDelInclusion)) or \
                not issubclass(child_class, XHTMLMixin):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected flow" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # treat as missing end tag
            return None


class FlowContainer(XHTMLElement):

    """Abstract class for all HTML elements that contain %flow;

    We support end tag omission."""
    XMLCONTENT = xml.XMLMixedContent

    def check_model(self, child_class):
        super(FlowContainer, self).check_model(child_class)
        if issubclass(child_class, (str, FlowMixin, InsDelInclusion)) or \
                not issubclass(child_class, XHTMLMixin):
            # allow: PCDATA | %flow | INS | DEL or non HTML-like elements
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected flow" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # treat as missing end tag
            return None

    def can_pretty_print(self):
        """Deteremins if this flow-container should be pretty printed.

        We suppress pretty printing if we have any non-trivial data
        children."""
        for child in self.get_children():
            if is_text(child):
                for c in child:
                    if not xml.is_s(c):
                        return False
            # elif isinstance(child,InlineMixin):
            #   return False
        return True


class FontStyle(AttrsMixin, InlineMixin, InlineContainer):

    """Abstract class for font and style elements
::

    <!ENTITY % fontstyle "TT | I | B | U | S | STRIKE | BIG | SMALL">
    <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
    <!ATTLIST (%fontstyle;|%phrase;)
        %attrs;     -- %coreattrs, %i18n, %events --
        >"""
    pass


class FrameElement(CoreAttrsMixin, XHTMLElement):
    pass


class Heading(AttrsMixin, BlockMixin, InlineContainer):

    """Abstract class for representing headings
::

    <!ELEMENT (%heading;)   - - (%inline;)* -- heading -->
    <!ATTLIST (%heading;)
        %attrs;     -- %coreattrs, %i18n, %events --
        %align;     -- align, text alignment --
        >

The align attribute is unmapped as it is not available in the strict
DTD."""
    pass


class InsDelInclusion(AttrsMixin, FlowContainer):

    """Represents inserted or deleted content
::

    <!-- INS/DEL are handled by inclusion on BODY -->
    <!ELEMENT (INS|DEL) - - (%flow;)*   -- inserted text, deleted text -->
    <!ATTLIST (INS|DEL)
        %attrs;     -- %coreattrs, %i18n, %events --
        cite        %URI;       #IMPLIED  -- info on reason for change --
        datetime    %Datetime;  #IMPLIED  -- date and time of change --
        >

According to the DTD these elements can be inserted at will anywhere
inside the document body (except that they do not appear within their
own content models so do not nest).  However, the specification suggests
that they are actually to be treated as satisfying either block or
inline which suggests that the intention is not to allow them to be
inserted randomly in elements with more complex structures such as lists
and tables. Indeed, there is the additional constraint that an inclusion
appearing in an inline context may not contain block-level elements.

We don't allow omitted end tags (as that seems dangerous) so incorrectly
nested instances or block/inline misuse will cause validity exceptions.
E.g.::

    <body>
        <p>Welcome
        <ins><p>This document is about...</ins>
    </body>

triggers an exception because <ins> is permitted in <p> but takes on an
inline role.  <p> is therefore *not* allowed in <ins> but the end tag of
</ins> is required, triggering an error.  This seems harsh given (a)
that the markup is compatibile with the DTD and (b) the meaning seems
clear but I can only reiterate Goldfarb's words from the SGML handbook
where he says of exceptions:

    Like many good power tools, however, if used improperly they can
    cause significant damage"""

    XMLATTR_cite = ('cite', uri.URI.from_octets, to_text)
    XMLATTR_datetime = ('datetime', xsi.datetime_from_str, xsi.datetime_to_str)
    XMLCONTENT = xml.XMLMixedContent

    def check_model(self, child_class):
        if issubclass(child_class, BlockMixin):
            # adding a block as a child to Ins or Del required that the
            # Ins or Del was used in a block context not an inline
            # context
            if self.parent and isinstance(self.parent, InlineContainer):
                raise XHTMLValidityError(
                    "%s in inclusion not allowed in inline context" %
                    child_class.__name__)
        super(InsDelInclusion, self).check_model(child_class)

    def get_child_class(self, stag_class):
        result = super(InsDelInclusion, self).get_child_class(stag_class)
        if result is None:
            # FlowContainer allows a missing end tag, we do not
            return stag_class
        else:
            return result


class List(AttrsMixin, BlockMixin, XHTMLElement):

    """Abstract class for representing list elements
::

    <!ENTITY % list "UL | OL">

Although a list item start tag is compulsory we are generous and will
imply a list item if data is found.  The end tag of the list is
required."""

    def check_model(self, child_class):
        if issubclass(child_class, LI) or \
                not issubclass(child_class, XHTMLElement):
            # allow only LI in lists, naked INS & DEL are not allowed
            # even though they are expressed as inclusions
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected flow" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        # If we get raw data in this context we assume an LI even though
        # STag is compulsory
        if issubclass(stag_class, (str, FlowMixin)):
            return LI
        else:
            return stag_class


class Phrase(AttrsMixin, InlineMixin, InlineContainer):

    """Abstract class for phrase elements
::

    <!ENTITY % phrase "EM | STRONG | DFN | CODE | SAMP | KBD | VAR |
        CITE | ABBR | ACRONYM" >
    <!ELEMENT (%fontstyle;|%phrase;) - - (%inline;)*>
    <!ATTLIST (%fontstyle;|%phrase;)
        %attrs;         -- %coreattrs, %i18n, %events --
        >"""
    pass


class TRContainer(XHTMLElement):

    def check_model(self, child_class):
        if issubclass(child_class, TR) or \
                not issubclass(child_class, XHTMLElement):
            # allow only TR, naked INS & DEL are not allowed even though
            # they are expressed as inclusions
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected flow" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        """PCDATA or TH|TD trigger TR, end tags may be omitted"""
        if issubclass(stag_class, (str, TH, TD)):
            return TR
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # omitted end tag
            return None


#
#   HTML Elements
#   -------------
#


class A(AttrsMixin, SpecialMixin, InlineContainer):

    """The HTML anchor element
::

    <!ELEMENT A - - (%inline;)* -(A)       -- anchor -->
    <!ATTLIST A
        %attrs;     -- %coreattrs, %i18n, %events --
        charset     %Charset;       #IMPLIED
            -- char encoding of linked resource --
        type        %ContentType;   #IMPLIED
            -- advisory content type --
        name        CDATA           #IMPLIED
            -- named link end --
        href        %URI;           #IMPLIED
            -- URI for linked resource --
        hreflang    %LanguageCode;  #IMPLIED
            -- language code --
        target      %FrameTarget;   #IMPLIED
            -- render in this frame --
        rel         %LinkTypes;     #IMPLIED
            -- forward link types --
        rev         %LinkTypes;     #IMPLIED
            -- reverse link types --
        accesskey   %Character;     #IMPLIED
            -- accessibility key character --
        shape       %Shape;         rect
            -- for use with client-side image maps --
        coords      %Coords;        #IMPLIED
            -- for use with client-side image maps --
        tabindex    NUMBER          #IMPLIED
            -- position in tabbing order --
        onfocus     %Script;        #IMPLIED
            -- the element got the focus --
        onblur      %Script;        #IMPLIED
            -- the element lost the focus -->

The event hander attributes are not mapped but the target is, even
though it is only defined in the loose DTD.  Note that, despite the
default value given in the DTD the shape attribute is not set and it
will only have a non-None value in an instance if a value was provided
explicitly."""
    XMLNAME = (XHTML_NAMESPACE, 'a')
    XMLATTR_charset = 'charset'
    XMLATTR_type = ('type', MediaType.from_str, to_text)
    XMLATTR_name = 'name'
    XMLATTR_href = ('href', uri.URI.from_octets, to_text)
    XMLATTR_hreflang = ('hreflang', xsi.name_from_str, xsi.name_from_str)
    XMLATTR_target = 'target'
    XMLATTR_rel = ('rel', None, None, list)
    XMLATTR_rev = ('rev', None, None, list)
    XMLATTR_accesskey = 'accesskey'
    XMLATTR_shape = ('shape', Shape.from_str_lower, Shape.to_str)
    XMLATTR_coords = ('coords', Coords.from_str, to_text)
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)


class Abbr(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'abbr')


class Acronym(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'acronym')


class Address(AttrsMixin, BlockMixin, InlineContainer):

    """Address \\(of author)
::

    <!ELEMENT ADDRESS - - ((%inline;)|P)*  -- information on author -->
    <!ATTLIST ADDRESS
        %attrs;     -- %coreattrs, %i18n, %events --
        >
"""
    XMLNAME = (XHTML_NAMESPACE, 'address')

    def check_model(self, child_class):
        if issubclass(child_class, P):
            # allow P
            return
        super(Address, self).check_model(child_class)


class Area(AttrsMixin, XHTMLElement):

    """Client-side image map area
::

    <!ELEMENT AREA - O EMPTY        -- client-side image map area -->
    <!ATTLIST AREA
        %attrs;     -- %coreattrs, %i18n, %events --
        shape       %Shape;         rect
            -- controls interpretation of coords --
        coords      %Coords;        #IMPLIED
            -- comma-separated list of lengths --
        href        %URI;           #IMPLIED
            -- URI for linked resource --
        target      %FrameTarget;   #IMPLIED
            -- render in this frame --
        nohref      (nohref)        #IMPLIED
            -- this region has no action --
        alt         %Text;          #REQUIRED   -- short description --
        tabindex    NUMBER          #IMPLIED
            -- position in tabbing order --
        accesskey   %Character;     #IMPLIED
            -- accessibility key character --
        onfocus     %Script;        #IMPLIED
            -- the element got the focus --
        onblur      %Script;        #IMPLIED
            -- the element lost the focus --
        >

The event attributes are not mapped however the target attribute is,
even though it relates on to frames and the loose DTD."""
    XMLNAME = (XHTML_NAMESPACE, 'area')
    XMLATTR_shape = ('shape', Shape.from_str_lower, Shape.to_str)
    XMLATTR_coords = ('coords', Coords.from_str, to_text)
    XMLATTR_href = ('href', uri.URI.from_octets, to_text)
    XMLATTR_target = 'target'
    XMLATTR_nohref = ('nohref', NoHRef.from_str_lower, NoHRef.to_str)
    XMLATTR_alt = 'alt'
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_accesskey = 'accesskey'
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        super(Area, self).__init__(parent)
        self.shape = Shape.rect
        self.alt = ""


class B(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'b')


class Base(HeadContentMixin, XHTMLElement):

    """Represents the base element
::

    <!ELEMENT BASE - O EMPTY        -- document base URI -->
    <!ATTLIST BASE
        href    %URI;   #REQUIRED   -- URI that acts as base URI --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'base')
    XMLATTR_href = ('href', uri.URI.from_octets, to_text)
    XMLCONTENT = xml.ElementType.Empty


class BaseFont(PreExclusionMixin, SpecialMixin, XHTMLElement):

    """Deprecated base font specification
::

    <!ELEMENT BASEFONT - O EMPTY           -- base font size -->
    <!ATTLIST BASEFONT
        id      ID          #IMPLIED    -- document-wide unique id --
        size    CDATA       #REQUIRED
            -- base font size for FONT elements --
        color   %Color;     #IMPLIED    -- text color --
        face    CDATA       #IMPLIED
            -- comma-separated list of font names -->"""
    XMLNAME = (XHTML_NAMESPACE, 'basefont')
    ID = 'id'
    XMLATTR_size = 'size'
    XMLATTR_color = ('color', Color, to_text)
    XMLATTR_face = ('face', CommaList.from_str, to_text)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        super(BaseFont, self).__init__(parent)
        self.size = ''


class BDO(CoreAttrsMixin, SpecialMixin, InlineContainer):

    """BiDi over-ride element
::

    <!ELEMENT BDO - - (%inline;)*          -- I18N BiDi over-ride -->
    <!ATTLIST BDO
        %coreattrs;     -- id, class, style, title --
        lang            %LanguageCode;  #IMPLIED    -- language code --
        dir             (ltr|rtl)       #REQUIRED   -- directionality --
        >

The dir attribute is initialised to the :class:`Direction` constant
ltr."""
    XMLNAME = (XHTML_NAMESPACE, 'bdo')
    XMLATTR_lang = ('lang', xsi.name_from_str, xsi.name_from_str)
    XMLATTR_dir = ('dir', Direction.from_str_lower, Direction.to_str)

    def __init__(self, parent):
        super(BDO, self).__init__(parent)
        self.dir = Direction.ltr


class Big(PreExclusionMixin, FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'big')


class Blockquote(AttrsMixin, BlockMixin, BlockContainer):

    """Blocked quote.

Strict DTD::

    <!ELEMENT BLOCKQUOTE - - (%block;|SCRIPT)+ -- long quotation -->

Loost DTD::

    <!ELEMENT BLOCKQUOTE - - (%flow;)*     -- long quotation -->

This implementation enforces the strict DTD by wrapping data and
inline content in DIV.  The Attributes are common to both forms of
the DTD::

    <!ATTLIST BLOCKQUOTE
        %attrs;     -- %coreattrs, %i18n, %events --
        cite        %URI;   #IMPLIED
            -- URI for source document or msg -->"""
    XMLNAME = (XHTML_NAMESPACE, 'blockquote')
    XMLATTR_cite = ('cite', uri.URI.from_octets, to_text)

    def check_model(self, child_class):
        """Overridden to add SCRIPT to the content model"""
        if issubclass(child_class, Script):
            return
        super(Blockquote, self).check_model(child_class)

    def get_child_class(self, stag_class):
        """If we get raw data in this context we assume a P to move
        closer to strict DTD (loose DTD allows any flow so raw data
        would be OK)."""
        if issubclass(stag_class, str):
            return Div
        elif issubclass(stag_class, Script):
            return stag_class
        else:
            return super(Blockquote, self).get_child_class(stag_class)


class Body(AttrsMixin, BodyColorsMixin, BlockContainer):

    """Represents the HTML BODY element
::

    <!ELEMENT BODY O O (%block;|SCRIPT)+ +(INS|DEL) -- document body -->
    <!ATTLIST BODY
        %attrs;         -- %coreattrs, %i18n, %events --
        onload          %Script;    #IMPLIED
            -- the document has been loaded --
        onunload        %Script;    #IMPLIED
            -- the document has been removed --
        background      %URI;       #IMPLIED
            -- texture tile for document background --
        %bodycolors;    -- bgcolor, text, link, vlink, alink --
        >

Note that the event handlers are not mapped to instance attributes."""
    XMLNAME = (XHTML_NAMESPACE, 'body')
    XMLATTR_background = ('background', uri.URI.from_octets, to_text)
    XMLCONTENT = xml.ElementType.ElementContent

    def check_model(self, child_class):
        """Overridden to add SCRIPT to the content model"""
        if issubclass(child_class, Script):
            return
        super(Body, self).check_model(child_class)

    def get_child_class(self, stag_class):
        if issubclass(stag_class, (Head, HeadMiscMixin, HeadContentMixin)):
            # Catch HEAD content appearing in BODY and force HEAD, BODY,
            # HEAD, BODY,... to catch all of it.  As we can only have
            # one HEAD and one BODY in the parent HTML element the result is
            # that we just sort things into their right places
            return None
        else:
            return super(Body, self).get_child_class(stag_class)

    def reset(self, reset_attrs=False):
        """Ignored for Body

        The HTML document class is not designed to be read and re-read
        from entities and so we disable the reset function and just act
        as an accumulator of content.  This allows us to parse 'tag
        soup' where head and body elements are intermixed."""
        pass


class Br(CoreAttrsMixin, SpecialMixin, XHTMLElement):

    """Represents a line break
::

    <!ELEMENT BR - O EMPTY                 -- forced line break -->
    <!ATTLIST BR
        %coreattrs;     -- id, class, style, title --
        clear           (left|all|right|none)   none
            -- control of text flow -->

The clear attribute is only in the loose DTD and is not mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'br')
    XMLCONTENT = xml.ElementType.Empty


class Button(AttrsMixin, ReservedMixin, FormCtrlMixin, FlowContainer):

    """Alternative form of button (with content)
::

    <!ELEMENT BUTTON - - (%flow;)* -(A|%formctrl;|FORM|FIELDSET)
        -- push button -->
    <!ATTLIST BUTTON
        %attrs;     -- %coreattrs, %i18n, %events --
        name        CDATA                       #IMPLIED
        value       CDATA                       #IMPLIED
            -- sent to server when submitted --
        type        (button|submit|reset)       submit
            -- for use as form button --
        disabled    (disabled)                  #IMPLIED
            -- unavailable in this context --
        tabindex    NUMBER                      #IMPLIED
            -- position in tabbing order --
        accesskey   %Character;                 #IMPLIED
            -- accessibility key character --
        onfocus     %Script;                    #IMPLIED
            -- the element got the focus --
        onblur      %Script;                    #IMPLIED
            -- the element lost the focus --
        %reserved;  -- reserved for possible future use -->

    The event handlers are not mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'button')
    XMLATTR_name = 'name'
    XMLATTR_value = 'value'
    XMLATTR_type = ('type', ButtonType.from_str_lower, ButtonType.to_str)
    XMLATTR_disabled = ('disabled', Disabled.from_str_lower, Disabled.to_str)
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_accesskey = ('accesskey', character_from_str, None)

    def __init__(self, parent):
        super(Button, self).__init__(parent)
        self.type = ButtonType.DEFAULT

    def get_child_class(self, stag_class):
        result = super(Button, self).get_child_class(stag_class)
        if result is None:
            # Prevent omitted end tag
            return stag_class
        else:
            return result


class Caption(AttrsMixin, InlineContainer):

    """Represents a table caption
::

    <!ELEMENT CAPTION  - - (%inline;)*     -- table caption -->
    <!ATTLIST CAPTION
        %attrs;     -- %coreattrs, %i18n, %events --
        align       %CAlign;        #IMPLIED  -- relative to table --
        >

The align attribute is along defiend in the loose DTD and is not
mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'caption')


class Center(AttrsMixin, BlockMixin, FlowContainer):

    """Equivalent to <div align="center">, only applies to loose DTD
::

    <!ELEMENT CENTER - - (%flow;)*  -- shorthand for DIV align=center -->
    <!ATTLIST CENTER
        %attrs;                     -- %coreattrs, %i18n, %events --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'center')


class Cite(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'cite')


class Code(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'code')


class Col(AttrsMixin, CellAlignMixin, TableColMixin, XHTMLElement):

    """Represents a table column
::

    <!ELEMENT COL       - O EMPTY   -- table column -->
    <!ATTLIST COL                   -- column groups and properties --
        %attrs;         -- %coreattrs, %i18n, %events --
        span            NUMBER          1
            -- COL attributes affect N columns --
        width           %MultiLength;   #IMPLIED
            -- column width specification --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;        -- vertical alignment in cells --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'col')
    XMLATTR_span = ('span', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_width = ('width', MultiLength.from_str, to_text)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        super(Col, self).__init__(parent)
        self.span = 1


class ColGroup(AttrsMixin, CellAlignMixin, TableColMixin, XHTMLElement):

    """Represents a group of columns
::

    <!ELEMENT COLGROUP - O (COL)*          -- table column group -->
    <!ATTLIST COLGROUP
        %attrs;         -- %coreattrs, %i18n, %events --
        span            NUMBER          1
            -- default number of columns in group --
        width           %MultiLength;   #IMPLIED
            -- default width for enclosed COLs --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;    -- vertical alignment in cells --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'colgroup')
    XMLATTR_span = ('span', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_width = ('width', MultiLength.from_str, to_text)
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(ColGroup, self).__init__(parent)
        self.span = 1
        self.Col = []

    def get_children(self):
        for child in self.Col:
            yield child

    def check_model(self, child_class):
        if issubclass(child_class, Col):
            return
        else:
            raise XHTMLValidityError(
                "%s not allowed in %s, expected Col content" %
                (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # support omitted end tag
            return None


class DD(AttrsMixin, FlowContainer):

    """Represents the definition of a defined term
::

    <!ELEMENT DD - O (%flow;)*      -- definition description -->
    <!ATTLIST (DT|DD)
        %attrs;         -- %coreattrs, %i18n, %events --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'dd')
    XMLCONTENT = xml.XMLMixedContent


class Del(InsDelInclusion):
    XMLNAME = (XHTML_NAMESPACE, 'del')


class Dfn(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'dfn')


class Div(AttrsMixin, ReservedMixin, BlockMixin, FlowContainer):

    """A generic flow container
::

    <!ELEMENT DIV - -  (%flow;)*            --  -->
    <!ATTLIST DIV
        %attrs;         -- %coreattrs, %i18n, %events --
        %align;         -- align, text alignment --
        %reserved;      -- reserved for possible future use --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'div')


class DL(AttrsMixin, BlockMixin, XHTMLElement):

    """Represents definition lists
::

    <!ELEMENT DL - - (DT|DD)+              -- definition list -->
    <!ATTLIST DL
        %attrs;     -- %coreattrs, %i18n, %events --
        compact     (compact)   #IMPLIED    -- reduced interitem spacing --
        >

The compact attribute is not mapped as it is only defined in the loose
DTD."""
    XMLNAME = (XHTML_NAMESPACE, 'dl')
    XMLCONTENT = xml.ElementType.ElementContent

    def check_model(self, child_class):
        if issubclass(child_class, (DD, DT)) or \
                not issubclass(child_class, XHTMLMixin):
            return
        super(DL, self).check_model(child_class)

    def get_child_class(self, stag_class):
        """If we get raw or inline data in this context we assume a DT,
        however if we get block data it must be DD"""
        if issubclass(stag_class, (str, InlineMixin)):
            return DT
        elif issubclass(stag_class, FlowMixin):
            return DD
        else:
            return stag_class


class DT(AttrsMixin, InlineContainer):

    """Represents a defined term
::

    <!ELEMENT DT - O (%inline;)*    -- definition term -->
    <!ATTLIST (DT|DD)
        %attrs;     -- %coreattrs, %i18n, %events -->"""
    XMLNAME = (XHTML_NAMESPACE, 'dt')


class Em(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'em')


class FieldSet(AttrsMixin, BlockMixin, FlowContainer):

    """Represents a group of controls in a form
::

    <!ELEMENT FIELDSET - -  (#PCDATA,LEGEND,(%flow;)*)
        -- form control group -->
    <!ATTLIST FIELDSET
        %attrs;     -- %coreattrs, %i18n, %events -->"""
    XMLNAME = (XHTML_NAMESPACE, 'fieldset')

    def __init__(self, parent):
        FlowContainer.__init__(self, parent)
        self.Legend = Legend(self)

    def get_children(self):
        yield self.Legend
        for child in super(FieldSet, self).get_children():
            yield child

    def check_model(self, child_class):
        if issubclass(child_class, Legend):
            # a bit lax, we allow it anywhere, they'll all be grouped
            return
        super(FieldSet, self).check_model(child_class)

    def get_child_class(self, stag_class):
        if issubclass(stag_class, Legend):
            # a bit lax, we allow it anywhere, they'll all be grouped
            return stag_class
        else:
            return super(FieldSet, self).get_child_class(stag_class)


class Font(I18nMixin, CoreAttrsMixin, SpecialMixin, InlineContainer):

    """Represents font style information (loose DTD only)
::

    <!ELEMENT FONT - - (%inline;)*         -- local change to font -->
    <!ATTLIST FONT
        %coreattrs;     -- id, class, style, title --
        %i18n;          -- lang, dir --
        size            CDATA       #IMPLIED
            -- [+|-]nn e.g. size="+1", size="4" --
        color           %Color;     #IMPLIED
            -- text color --
        face            CDATA       #IMPLIED
            -- comma-separated list of font names -->

Although defined only in the loose DTD we provide custom mappings for
all of the attributes."""
    XMLNAME = (XHTML_NAMESPACE, 'font')
    XMLATTR_size = 'size'
    XMLATTR_color = ('color', Color, to_text)
    XMLATTR_face = ('face', CommaList.from_str, to_text)


class Form(AttrsMixin, BlockMixin, BlockContainer):

    """Represents the form element.

    Strict DTD::

        <!ELEMENT FORM - - (%block;|SCRIPT)+ -(FORM) -- interactive form -->

    Loose DTD::

        <!ELEMENT FORM - - (%flow;)* -(FORM)   -- interactive form -->

    Attributes (target is mapped even though it is only in the loose
    DTD) as it is for use in frame-based documents::

        <!ATTLIST FORM
            %attrs;     -- %coreattrs, %i18n, %events --
            action      %URI;           #REQUIRED
                -- server-side form handler --
            method      (GET|POST)      GET
                -- HTTP method used to submit the form--
            enctype     %ContentType;   "application/x-www-form-urlencoded"
            accept      %ContentTypes;  #IMPLIED
                -- list of MIME types for file upload --
            name        CDATA           #IMPLIED
                -- name of form for scripting --
            onsubmit    %Script;        #IMPLIED
                -- the form was submitted --
            onreset     %Script;        #IMPLIED    -- the form was reset --
            target      %FrameTarget;   #IMPLIED    -- render in this frame --
            accept-charset %Charsets;   #IMPLIED
                -- list of supported charsets --
            >"""
    XMLNAME = (XHTML_NAMESPACE, 'form')
    XMLATTR_action = ('action', uri.URI.from_octets, to_text)
    XMLATTR_method = ('method', Method.from_str_upper, Method.to_str)
    XMLATTR_enctype = ('enctype', MediaType.from_str, to_text)
    XMLATTR_accept = ('accept', ContentTypes.from_str, to_text)
    XMLATTR_name = 'name'
    XMLATTR_target = 'target'
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        BlockContainer.__init__(self, parent)
        self.action = uri.URI.from_octets('')
        self.method = Method.DEFAULT
        self.enctype = MediaType.from_str("application/x-www-form-urlencoded")

    def check_model(self, child_class):
        if issubclass(child_class, Script):
            return
        super(Form, self).check_model(child_class)

    def get_child_class(self, stag_class):
        if issubclass(stag_class, (Script, Form)):
            # catch script to prevent an implied div
            # prevent implied end tag on nested FORM
            return stag_class
        else:
            return super(Form, self).get_child_class(stag_class)


setattr(Form, 'XMLATTR_accept-charset', ('accept_charset', None, None, list))


class Frame(FrameElement):

    """Represents a Frame within a frameset document
::

    <!ELEMENT FRAME - O EMPTY              -- subwindow -->
    <!ATTLIST FRAME
        %coreattrs;     -- id, class, style, title --
        longdesc        %URI;           #IMPLIED
             -- link to long description (complements title) --
        name            CDATA           #IMPLIED
            -- name of frame for targetting --
        src             %URI;           #IMPLIED
            -- source of frame content --
        frameborder     (1|0)           1
            -- request frame borders? --
        marginwidth     %Pixels;        #IMPLIED
            -- margin widths in pixels --
        marginheight    %Pixels;        #IMPLIED
            -- margin height in pixels --
        noresize        (noresize)      #IMPLIED
            -- allow users to resize frames? --
        scrolling       (yes|no|auto)   auto
            -- scrollbar or none -->

The frameborder, marginwidth and marginheight attributes are not
mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'frame')
    XMLATTR_longdesc = ('longdesc', uri.URI.from_octets, to_text)
    XMLATTR_name = 'name'
    XMLATTR_src = ('src', uri.URI.from_octets, to_text)
    XMLATTR_noresize = ('noresize', NoResize.from_str_lower, NoResize.to_str)
    XMLATTR_scrolling = ('scrolling', Scrolling.from_str_lower,
                         Scrolling.to_str)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        super(Frame, self).__init__(parent)
        self.scrolling = Scrolling.auto


class Frameset(FrameElement):

    """Represents a frameset (within a Frameset document)
::

    <!ELEMENT FRAMESET - - ((FRAMESET|FRAME)+ & NOFRAMES?)
        -- window subdivision-->
    <!ATTLIST FRAMESET
        %coreattrs;     -- id, class, style, title --
        rows            %MultiLengths;  #IMPLIED
            -- list of lengths, default: 100% (1 row) --
        cols            %MultiLengths;  #IMPLIED
            -- list of lengths, default: 100% (1 col) --
        onload          %Script;        #IMPLIED
            -- all the frames have been loaded  --
        onunload        %Script;        #IMPLIED
            -- all the frames have been removed --
        >

The event handlers are not mapped to custom attributes."""
    XMLNAME = (XHTML_NAMESPACE, 'frameset')
    XMLATTR_rows = ('rows', MultiLengths.from_str, to_text)
    XMLATTR_cols = ('cols', MultiLengths.from_str, to_text)
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        FrameElement.__init__(self, parent)
        self.FrameElement = []
        self.NoFramesFrameset = None

    def get_children(self):
        for child in self.FrameElement:
            yield child
        if self.NoFramesFrameset:
            yield self.NoFramesFrameset


class H1(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h1')
    XMLCONTENT = xml.XMLMixedContent


class H2(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h2')
    XMLCONTENT = xml.XMLMixedContent


class H3(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h3')
    XMLCONTENT = xml.XMLMixedContent


class H4(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h4')
    XMLCONTENT = xml.XMLMixedContent


class H5(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h5')
    XMLCONTENT = xml.XMLMixedContent


class H6(Heading):
    XMLNAME = (XHTML_NAMESPACE, 'h6')
    XMLCONTENT = xml.XMLMixedContent


class Head(I18nMixin, XHTMLElement):

    """Represents the HTML head structure
::

    <!ELEMENT HEAD O O (%head.content;) +(%head.misc;)
        -- document head -->
    <!ATTLIST HEAD
        %i18n;      -- lang, dir --
        profile   %URI;   #IMPLIED
            -- named dictionary of meta info --
          >"""
    XMLNAME = (XHTML_NAMESPACE, 'head')
    XMLATTR_profile = ('profile', uri.URI.from_octets, to_text)
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        #: The document title
        self.Title = Title(self)
        #: The document's base URI
        self.Base = None
        self.HeadMiscMixin = []
        """The content model uses an inclusion to allow any of the
        :class:`HeadMiscMixin` elements but when we generate the output we
        always start with the <title>, and the optional <base>."""

    def check_model(self, child_class):
        if issubclass(child_class,
                      (HeadContentMixin, HeadMiscMixin, NoScript)):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Head content" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # omitted end tag
            return None

    def get_children(self):
        yield self.Title
        if self.Base:
            yield self.Base
        for child in itertools.chain(
                self.HeadMiscMixin,
                XHTMLElement.get_children(self)):
            yield child

    def generate_plain_text(self):
        # add a blank line after the header has been rendered
        for ptext in super(Head, self).generate_plain_text():
            yield ptext
        yield "\n\n"


class HR(AttrsMixin, BlockMixin, XHTMLElement):

    """Represents a horizontal rule
::

    <!ELEMENT HR - O EMPTY -- horizontal rule -->
    <!ATTLIST HR
        %attrs;     -- %coreattrs, %i18n, %events --
        align       (left|center|right)     #IMPLIED
        noshade     (noshade)               #IMPLIED
        size        %Pixels;                #IMPLIED
        width       %Length;                #IMPLIED
        >

The align, noshade, size and width attributes are not defined in the
strict DTD and are not mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'hr')
    XMLCONTENT = xml.ElementType.Empty


class HTML(I18nMixin, XHTMLElement):

    """Represents the HTML document strucuture
::

    <!ENTITY % html.content "HEAD, BODY">

    <!ELEMENT HTML O O (%html.content;)     -- document root element -->
    <!ATTLIST HTML
          %i18n;                            -- lang, dir --
    >"""
    XMLNAME = (XHTML_NAMESPACE, 'html')
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.Head = Head(self)
        self.Body = Body(self)

    def check_model(self, child_class):
        if issubclass(child_class, (Head, Body)):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Head or Body content" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        """Overridden for implied <head> or <body>

        Based on stag_class we return either :class:`Head` or
        :class:`Body`, we can accommodate any tag!"""
        if issubclass(stag_class,
                      (Head, HeadContentMixin, Style, Meta, Link)):
            # assume Head
            return Head
        elif issubclass(stag_class, (str, FlowMixin, InsDelInclusion)):
            # Script, Object (and may be NoScript) are ambiguous but we
            # infer body by default, including for data
            return Body
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # omitted end tag
            return None

    def get_children(self):
        yield self.Head
        yield self.Body

    def get_base(self):
        base = super(HTML, self).get_base()
        if base is None:
            # perhaps our Head has a Base?
            if self.Head.Base:
                return self.Head.Base.href


class HTMLFrameset(I18nMixin, XHTMLElement):

    """Represents the HTML frameset document element
::

    <!ENTITY % html.content "HEAD, FRAMESET">

See :class:`HTML` for a complete declaration.

We omit the default name declaration XMLNAME to ensure uniqueness in the
document mapping adding.  When creating orphan instances of this element
you must use :meth:`set_xmlname` to set a name for the element before
serialization."""
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(HTMLFrameset, self).__init__(parent)
        # force a default name for the element, necessary as we support
        # omitted tags
        self.set_xmlname(HTML.XMLNAME)
        self.Head = Head(self)
        self.Frameset = None

    def check_model(self, child_class):
        if issubclass(child_class, (Head, Frameset)):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Head or Frameset content in "
            "frameset document" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        """Overridden for implied <head> only."""
        if stag_class and issubclass(
                stag_class, (Head, HeadContentMixin, Style, Meta, Link)):
            # possibly missing STag for HEAD; we leave out Script
            return Head
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # omitted end tag, allow if we have a Frameset
            if self.Frameset is None:
                raise
            return None

    def get_children(self):
        yield self.Head
        yield self.Frameset

    def get_base(self):
        base = super(HTML, self).get_base()
        if base is None:
            # perhaps our Head has a Base?
            if self.Head.Base:
                return self.Head.Base.href


class I(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'i')


class IFrame(CoreAttrsMixin, SpecialMixin, FlowContainer):

    """Represents the iframe element
::

    <!ELEMENT IFRAME - - (%flow;)*         -- inline subwindow -->
    <!ATTLIST IFRAME
        %coreattrs;                          -- id, class, style, title --
        longdesc    %URI;          #IMPLIED
            -- link to long description (complements title) --
        name            CDATA           #IMPLIED
            -- name of frame for targetting --
        src             %URI;           #IMPLIED
            -- source of frame content --
        frameborder     (1|0)           1
            -- request frame borders? --
        marginwidth     %Pixels;        #IMPLIED
            -- margin widths in pixels --
        marginheight    %Pixels;        #IMPLIED
            -- margin height in pixels --
        scrolling       (yes|no|auto)   auto
            -- scrollbar or none --
        align           %IAlign;        #IMPLIED
            -- vertical or horizontal alignment --
        height          %Length;        #IMPLIED    -- frame height --
        width           %Length;        #IMPLIED    -- frame width --
        >

IFrames are not part of the strict DTD, perhaps surprisingly given their
widespread adoption.  For consistency with other elements we leave the
frameborder, marginwidth, marginheight and align attrbutes unmapped.  As
a result, we rely on the default frameborder value provided in the DTD
rather than setting an attribute explicitly on construction.  In
contrast, the scrolling attribute *is* mapped and is initialised to
:attr:`Scrolling.auto`."""
    XMLNAME = (XHTML_NAMESPACE, 'iframe')
    XMLATTR_longdesc = ('longdesc', uri.URI.from_octets, to_text)
    XMLATTR_name = 'name'
    XMLATTR_src = ('src', uri.URI.from_octets, to_text)
    XMLATTR_scrolling = ('scrolling', Scrolling.from_str_lower,
                         Scrolling.to_str)
    XMLATTR_height = ('height', Length.from_str, to_text)
    XMLATTR_width = ('width', Length.from_str, to_text)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        super(IFrame, self).__init__(parent)
        self.scrolling = Scrolling.auto


class Img(AttrsMixin, PreExclusionMixin, SpecialMixin, XHTMLElement):

    """Represents the <img> element
::

    <!ELEMENT IMG - O EMPTY                -- Embedded image -->
    <!ATTLIST IMG
        %attrs;     -- %coreattrs, %i18n, %events --
        src         %URI;       #REQUIRED   -- URI of image to embed --
        alt         %Text;      #REQUIRED   -- short description --
        longdesc    %URI;       #IMPLIED
            -- link to long description (complements alt) --
        name        CDATA       #IMPLIED
            -- name of image for scripting --
        height      %Length;    #IMPLIED    -- override height --
        width       %Length;    #IMPLIED    -- override width --
        usemap      %URI;       #IMPLIED
            -- use client-side image map --
        ismap       (ismap)     #IMPLIED
            -- use server-side image map --
        align       %IAlign;    #IMPLIED
            -- vertical or horizontal alignment --
        border      %Pixels;    #IMPLIED    -- link border width --
        hspace      %Pixels;    #IMPLIED    -- horizontal gutter --
        vspace      %Pixels;    #IMPLIED    -- vertical gutter --
        >

The align, border, hspace and vspace attributes are only defined by the
loose DTD are are no mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'img')
    XMLATTR_src = ('src', uri.URI.from_octets, to_text)
    XMLATTR_alt = 'alt'
    XMLATTR_longdesc = ('longdesc', uri.URI.from_octets, to_text)
    XMLATTR_name = 'name'
    XMLATTR_height = ('height', Length.from_str, to_text)
    XMLATTR_width = ('width', Length.from_str, to_text)
    XMLATTR_usemap = ('usemap', uri.URI.from_octets, to_text)
    XMLATTR_ismap = ('ismap', IsMap.from_str_lower, IsMap.to_str)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.src = None
        self.alt = ''

    def add_to_cpresource(self, cp, resource, been_there):
        if isinstance(self.src, uri.FileURL):
            f = been_there.get(str(self.src), None)
            if f is None:
                f = cp.FileCopy(resource, self.src)
                been_there[str(self.src)] = f
            new_src = f.resolve_uri(f.href)
            # Finally, we need change our src attribute
            self.src = self.relative_uri(new_src)


class Input(FormCtrlMixin, AttrsMixin, XHTMLElement):

    """Represents the input element
::

    <!-- attribute name required for all but submit and reset -->
    <!ELEMENT INPUT - O EMPTY              -- form control -->
    <!ATTLIST INPUT
        %attrs;     -- %coreattrs, %i18n, %events --
        type        %InputType;     TEXT
            -- what kind of widget is needed --
        name        CDATA           #IMPLIED
            -- submit as part of form --
        value       CDATA           #IMPLIED
            -- Specify for radio buttons and checkboxes --
        checked     (checked)       #IMPLIED
            -- for radio buttons and check boxes --
        disabled    (disabled)      #IMPLIED
            -- unavailable in this context --
        readonly    (readonly)      #IMPLIED
            -- for text and passwd --
        size        CDATA           #IMPLIED
            -- specific to each type of field --
        maxlength   NUMBER          #IMPLIED
            -- max chars for text fields --
        src         %URI;           #IMPLIED
            -- for fields with images --
        alt         CDATA           #IMPLIED
            -- short description --
        usemap      %URI;           #IMPLIED
            -- use client-side image map --
        ismap       (ismap)         #IMPLIED
            -- use server-side image map --
        tabindex    NUMBER          #IMPLIED
            -- position in tabbing order --
        accesskey   %Character;     #IMPLIED
            -- accessibility key character --
        onfocus     %Script;        #IMPLIED
            -- the element got the focus --
        onblur      %Script;        #IMPLIED
            -- the element lost the focus --
        onselect    %Script;        #IMPLIED
            -- some text was selected --
        onchange    %Script;        #IMPLIED
            -- the element value was changed --
        accept      %ContentTypes;  #IMPLIED
            -- list of MIME types for file upload --
        align       %IAlign;        #IMPLIED
            -- vertical or horizontal alignment --
        %reserved;  -- reserved for possible future use --
        >

The event handlers are unmapped.  The align attribute is defined only in
the loose DTD and is also unmapped."""
    XMLNAME = (XHTML_NAMESPACE, 'input')
    XMLATTR_type = ('type', InputType.from_str_lower, InputType.to_str)
    XMLATTR_name = 'name'
    XMLATTR_value = 'value'
    XMLATTR_checked = ('checked', Checked.from_str_lower, Checked.to_str)
    XMLATTR_disabled = ('disabled', Disabled.from_str_lower, Disabled.to_str)
    XMLATTR_readonly = ('readonly', ReadOnly.from_str_lower, ReadOnly.to_str)
    XMLATTR_size = ('size', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_maxlength = ('maxlength', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_src = ('src', uri.URI.from_octets, to_text)
    XMLATTR_alt = 'alt'
    XMLATTR_usemap = ('usemap', uri.URI.from_octets, to_text)
    XMLATTR_ismap = ('ismap', IsMap.from_str_lower, IsMap.to_str)
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_accesskey = ('accesskey', character_from_str, None)
    XMLATTR_accept = ('accept', ContentTypes.from_str, to_text)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.type = InputType.DEFAULT


class Ins(InsDelInclusion):
    XMLNAME = (XHTML_NAMESPACE, 'ins')


class IsIndex(CoreAttrsMixin, I18nMixin, HeadContentMixin, BlockMixin,
              XHTMLElement):

    """Deprecated one-element form control
::

    <!ELEMENT ISINDEX - O EMPTY            -- single line prompt -->
    <!ATTLIST ISINDEX
        %coreattrs;     -- id, class, style, title --
        %i18n;          -- lang, dir --
        prompt          %Text;  #IMPLIED    -- prompt message -->"""
    XMLNAME = (XHTML_NAMESPACE, 'isindex')
    XMLATTR_prompt = 'prompt'
    XMLCONTENT = xml.ElementType.Empty


class Kbd(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'kbd')


class Label(AttrsMixin, FormCtrlMixin, InlineContainer):

    """Label element
::

    <!ELEMENT LABEL - - (%inline;)* -(LABEL) -- form field label text -->
    <!ATTLIST LABEL
        %attrs;     -- %coreattrs, %i18n, %events --
        for         IDREF           #IMPLIED
            -- matches field ID value --
        accesskey   %Character;     #IMPLIED
            -- accessibility key character --
        onfocus     %Script;        #IMPLIED
            -- the element got the focus --
        onblur      %Script;        #IMPLIED
            -- the element lost the focus -->

To avoid the use of the reserved word 'for' this attribute is mapped to
the attribute name *for_field*.  The event attributes are not mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'label')
    XMLATTR_for = 'for_field'
    XMLATTR_accesskey = ('accesskey', character_from_str, None)


class Legend(AttrsMixin, InlineContainer):

    """legend element
::

    <!ELEMENT LEGEND - - (%inline;)*       -- fieldset legend -->

    <!ATTLIST LEGEND
      %attrs;                              -- %coreattrs, %i18n, %events --
      accesskey   %Character;    #IMPLIED  -- accessibility key character --
      >
    """
    XMLNAME = (XHTML_NAMESPACE, 'legend')
    XMLATTR_accesskey = ('accesskey', character_from_str, None)


class LI(AttrsMixin, FlowContainer):

    """Represent list items
::

    <!ELEMENT LI - O (%flow;)*             -- list item -->
    <!ATTLIST LI
        %attrs;     -- %coreattrs, %i18n, %events --
        type        %LIStyle;   #IMPLIED  -- list item style --
        value       NUMBER      #IMPLIED  -- reset sequence number -->

The type and value attributes are only defined by the loose DTD and are
not mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'li')
    XMLCONTENT = xml.XMLMixedContent


class Link(AttrsMixin, HeadMiscMixin, XHTMLElement):

    """Media-independent link
::

    <!ELEMENT LINK - O EMPTY               -- a media-independent link -->
    <!ATTLIST LINK
        %attrs;                              -- %coreattrs, %i18n, %events --
        charset     %Charset;      #IMPLIED
            -- char encoding of linked resource --
        href        %URI;          #IMPLIED  -- URI for linked resource --
        hreflang    %LanguageCode; #IMPLIED  -- language code --
        type        %ContentType;  #IMPLIED  -- advisory content type --
        rel         %LinkTypes;    #IMPLIED  -- forward link types --
        rev         %LinkTypes;    #IMPLIED  -- reverse link types --
        media       %MediaDesc;    #IMPLIED  -- for rendering on these media --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'link')
    XMLATTR_charset = 'charset'
    XMLATTR_href = ('href', uri.URI.from_octets, to_text)
    XMLATTR_hreflang = ('hreflang', xsi.name_from_str, xsi.name_from_str)
    XMLATTR_type = ('type', MediaType.from_str, to_text)
    XMLATTR_rel = ('rel', lambda x: x.lower(), None, list)
    XMLATTR_rev = ('rev', lambda x: x.lower(), None, list)
    XMLATTR_media = ('media', MediaDesc.from_str, to_text)
    XMLCONTENT = xml.ElementType.Empty


class Map(AttrsMixin, SpecialMixin, BlockContainer):

    """Represents a client-side image map
::

    <!ELEMENT MAP - - ((%block;) | AREA)+ -- client-side image map -->
    <!ATTLIST MAP
        %attrs;     -- %coreattrs, %i18n, %events --
        name        CDATA   #REQUIRED -- for reference by usemap --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'map')
    XMLATTR_name = 'name'

    def __init__(self, parent):
        super(Map, self).__init__(parent)
        self.name = ''

    def check_model(self, child_class):
        if issubclass(child_class, Area):
            return
        super(Map, self).check_model(child_class)


class Meta(I18nMixin, HeadMiscMixin, XHTMLElement):

    """Represents the meta element
::

    <!ELEMENT META - O EMPTY                -- generic metainformation -->
    <!ATTLIST META
      %i18n;        -- lang, dir, for use with content --
      http-equiv    NAME        #IMPLIED    -- HTTP response header name  --
      name          NAME        #IMPLIED    -- metainformation name --
      content       CDATA       #REQUIRED   -- associated information --
      scheme        CDATA       #IMPLIED    -- select form of content --
      >

The http-equiv attribute cannot be mapped"""
    XMLNAME = (XHTML_NAMESPACE, 'meta')
    XMLATTR_name = ('name', xsi.name_from_str, xsi.name_from_str)
    XMLATTR_content = 'content'
    XMLATTR_scheme = 'scheme'
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        super(Meta, self).__init__(parent)
        self.content = ""

# add this mapping manually to deal with hyphen in name
setattr(Meta, 'XMLATTR_http-equiv',
        ('http_equiv', xsi.name_from_str, xsi.name_from_str))


class NoFrames(AttrsMixin, BlockMixin, FlowContainer):

    """Represents the NOFRAMES element.

    This element is deprecated, it is not part of the strict DTD or
    HTML5.  This element is used to represent instances encountered
    in documents using the loose DTD::

        <!ENTITY % noframes.content "(%flow;)*">

        <!ELEMENT NOFRAMES - - %noframes.content;
            -- alternate content container for non frame-based rendering -->
        <!ATTLIST NOFRAMES
            %attrs;         -- %coreattrs, %i18n, %events -->"""
    XMLNAME = (XHTML_NAMESPACE, 'noframes')
    XMLCONTENT = xml.ElementType.MIXED


class NoFramesFrameset(AttrsMixin, XHTMLElement):

    """Represents the NOFRAMES element in a FRAMESET document.

    This element is deprecated, it is not part of the strict DTD or
    HTML5.  This element is used to represent instances encountered
    in documents using the frameset DTD::

        <!ENTITY % noframes.content "(BODY) -(NOFRAMES)">

        <!ATTLIST NOFRAMES
            %attrs;         -- %coreattrs, %i18n, %events -->

    We omit the XMLNAME attribute (the default element name) to prevent
    a name clash when declaring the elements in the name space.  Instead
    we'll use a special catch to ensure that <noframes> maps to this
    element in a frameset context."""

    def __init__(self, parent):
        super(NoFramesFrameset, self).__init__(parent)
        self.Body = Body(self)

    def check_model(self, child_class):
        if issubclass(child_class, Body):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Body" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        # support omitted start tag on body
        if issubclass(stag_class, (str, FlowMixin, Script)):
            return Body
        else:
            return stag_class

    def get_children(self):
        yield self.Body


class NoScript(AttrsMixin, BlockMixin, BlockContainer):

    """Represents the NOSCRIPT element

    Loose DTD::

        <!ELEMENT NOSCRIPT - - (%flow;)*
            -- alternate content container for non script-based rendering -->

    Strict DTD::

        <!ELEMENT NOSCRIPT - - (%block;)+
            -- alternate content container for non script-based rendering -->

    Common::

        <!ATTLIST NOSCRIPT
            %attrs;     -- %coreattrs, %i18n, %events -->

    We take the liberty of enforcing the stricter DTD which has the
    effect of starting an implicit <div> if inline elements are
    encountered in <noscript> elements.

    We also bring forward an element of HTML5 compatibility by allowing
    NoScript within the document <head> with a content model equivalent
    to::

        <!ELEMENT NOSCRIPT - - (LINK|STYLE|META)*   -->"""
    XMLNAME = (XHTML_NAMESPACE, 'noscript')
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(NoScript, self).__init__(parent)

    def check_model(self, child_class):
        if self.find_parent(Head):
            if issubclass(child_class, (Link, Meta, Style)):
                return
            else:
                raise XHTMLValidityError(
                    "%s not allowed in %s in Head context, expected Link, "
                    "Meta or Style" %
                    (child_class.__name__, self.__class__.__name__))
        else:
            super(NoScript, self).check_model(child_class)

    def get_child_class(self, stag_class):
        if self.find_parent(Head):
            try:
                self.check_model(stag_class)
                return stag_class
            except XHTMLValidityError:
                # allow omitted end tag (terminating noscript and head
                # too perhaps)
                return None
        else:
            return super(NoScript, self).get_child_class(stag_class)


class Object(AttrsMixin, ReservedMixin, SpecialMixin, HeadMiscMixin,
             FlowContainer):

    """Represents the object element
::

    <!ELEMENT OBJECT    - - (PARAM | %flow;)*

    <!ATTLIST OBJECT
        %attrs;     -- %coreattrs, %i18n, %events --
        declare   (declare)         #IMPLIED
            -- declare but don't instantiate flag --
        classid     %URI;           #IMPLIED
            -- identifies an implementation --
        codebase    %URI;           #IMPLIED
            -- base URI for classid, data, archive--
        data        %URI;           #IMPLIED
            -- reference to object's data --
        type        %ContentType;   #IMPLIED
            -- content type for data --
        codetype    %ContentType;   #IMPLIED
            -- content type for code --
        archive     CDATA           #IMPLIED
            -- space-separated list of URIs --
        standby     %Text;          #IMPLIED
            -- message to show while loading --
        height      %Length;        #IMPLIED    -- override height --
        width       %Length;        #IMPLIED    -- override width --
        usemap      %URI;           #IMPLIED
            -- use client-side image map --
        name        CDATA           #IMPLIED
            -- submit as part of form --
        tabindex    NUMBER          #IMPLIED
            -- position in tabbing order --
        %reserved;  -- reserved for possible future use --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'object')
    XMLATTR_declare = (
        'declare', Declare.from_str_lower, Declare.to_str)
    XMLATTR_classid = ('classid', uri.URI.from_octets, to_text)
    XMLATTR_codebase = ('codebase', uri.URI.from_octets, to_text)
    XMLATTR_data = ('data', uri.URI.from_octets, to_text)
    XMLATTR_type = ('type', MediaType.from_str, to_text)
    XMLATTR_codetype = ('codetype', MediaType.from_str, to_text)
    XMLATTR_archive = ('archive', uri.URI.from_octets, to_text, list)
    XMLATTR_standby = 'standby'
    XMLATTR_height = ('height', Length.from_str, to_text)
    XMLATTR_width = ('width', Length.from_str, to_text)
    XMLATTR_usemap = ('usemap', uri.URI.from_octets, to_text)
    XMLATTR_name = 'name'
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.XMLMixedContent

    def check_model(self, child_class):
        if issubclass(child_class, Param):
            return
        super(Object, self).check_model(child_class)

    def add_to_cpresource(self, cp, resource, been_there):
        if isinstance(self.data, uri.FileURL):
            f = been_there.get(str(self.data), None)
            if f is None:
                f = cp.FileCopy(resource, self.data)
                been_there[str(self.data)] = f
            new_data = f.resolve_uri(f.href)
            self.data = self.relative_uri(new_data)


class OL(List):

    """Represents ordered lists
::

    <!ELEMENT OL - - (LI)+                 -- ordered list -->
    <!ATTLIST OL
        %attrs;     -- %coreattrs, %i18n, %events --
        type        %OLStyle;   #IMPLIED  -- numbering style --
        compact     (compact)   #IMPLIED  -- reduced interitem spacing --
        start       NUMBER      #IMPLIED  -- starting sequence number --
        >

The type, compact and start attributes are only defined in the loose DTD
and so are not mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'ol')
    XMLCONTENT = xml.ElementType.ElementContent


class OptGroup(AttrsMixin, OptItemMixin, XHTMLElement):

    """OptGroup element
::

    <!ELEMENT OPTGROUP - - (OPTION)+ -- option group -->
    <!ATTLIST OPTGROUP
        %attrs;     -- %coreattrs, %i18n, %events --
        disabled    (disabled)      #IMPLIED
            -- unavailable in this context --
        label       %Text;          #REQUIRED
            -- for use in hierarchical menus --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'optgroup')
    XMLATTR_disabled = ('disabled', Disabled.from_str_lower, Disabled.to_str)
    XMLATTR_label = 'label'
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.label = 'OPTGROUP'

    def check_model(self, child_class):
        if issubclass(child_class, Option):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Option" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        # support missing end tag
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            return None


class Option(AttrsMixin, OptItemMixin, XHTMLElement):

    """Option element
::

    <!ELEMENT OPTION - O (#PCDATA)         -- selectable choice -->
    <!ATTLIST OPTION
        %attrs;     -- %coreattrs, %i18n, %events --
        selected    (selected)      #IMPLIED
        disabled    (disabled)      #IMPLIED
            -- unavailable in this context --
        label       %Text;          #IMPLIED
            -- for use in hierarchical menus --
        value       CDATA           #IMPLIED
            -- defaults to element content --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'option')
    XMLATTR_selected = ('selected', Selected.from_str_lower, Selected.to_str)
    XMLATTR_disabled = ('disabled', Disabled.from_str_lower, Disabled.to_str)
    XMLATTR_label = 'label'
    XMLATTR_value = 'value'
    XMLCONTENT = xml.XMLMixedContent

    def check_model(self, child_class):
        if not issubclass(child_class, XHTMLMixin):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Option" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            # support omitted end tag
            return None


class P(AttrsMixin, AlignMixin, BlockMixin, InlineContainer):

    """Represents a paragraph
::

    <!ELEMENT P - O (%inline;)*     -- paragraph -->
    <!ATTLIST P
        %attrs;     -- %coreattrs, %i18n, %events --
        %align;     -- align, text alignment --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'p')


class Param(XHTMLElement):

    """Represents an object parameter
::

    <!ELEMENT PARAM - O EMPTY           -- named property value -->
    <!ATTLIST PARAM
        id          ID                  #IMPLIED
            -- document-wide unique id --
        name        CDATA               #REQUIRED
            -- property name --
        value       CDATA               #IMPLIED
            -- property value --
        valuetype   (DATA|REF|OBJECT)   DATA
            -- How to interpret value --
        type        %ContentType;       #IMPLIED
            -- content type for value when valuetype=ref --
        >

The name attribute is required and is initialised to "_".  The valuetype
attribute is not populated automatically so applications processing this
element should treat a value of None as equivalent to the integer
constant ParamValueType.data.  The value of *value* is always a string,
even if valuetype is ref, indicating that it should be interpreted as a
URI."""
    XMLNAME = (XHTML_NAMESPACE, 'param')
    ID = (xmlns.NO_NAMESPACE, 'id')
    XMLATTR_name = 'name'
    XMLATTR_value = 'value'
    XMLATTR_valuetype = ('valuetype', ParamValueType.from_str_lower,
                         ParamValueType.to_str)
    XMLATTR_type = ('type', MediaType.from_str, to_text)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        super(Param, self).__init__(parent)
        self.name = "_"


class Pre(AttrsMixin, BlockMixin, InlineContainer):

    """Represents pre-formatted text
::

    <!ELEMENT PRE - - (%inline;)* -(%pre.exclusion;)
        -- preformatted text -->
    <!ATTLIST PRE
        %attrs;     -- %coreattrs, %i18n, %events --
        width       NUMBER      #IMPLIED
        >

The width attribute is only defined in the loose DTD and is not
mapped."""
    XMLNAME = (XHTML_NAMESPACE, 'pre')

    def get_space(self):
        """Pretend that this attribute is always set."""
        return "preserve"


class Q(AttrsMixin, SpecialMixin, InlineContainer):

    """Represents an inline quotation
::

    <!ELEMENT Q - - (%inline;)*     -- short inline quotation -->
    <!ATTLIST Q
        %attrs;     -- %coreattrs, %i18n, %events --
        cite        %URI;   #IMPLIED  -- URI for source document or msg --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'q')
    XMLATTR_cite = ('cite', uri.URI.from_octets, to_text)


class S(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 's')


class Samp(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'samp')


class Script(SpecialMixin, HeadMiscMixin, XHTMLElement):

    """Represents the script element
::

    <!ELEMENT SCRIPT    - - %Script;    -- script statements -->
    <!ATTLIST SCRIPT
        charset %Charset;      #IMPLIED
            -- char encoding of linked resource --
        type    %ContentType;  #REQUIRED
            -- content type of script language --
        src     %URI;          #IMPLIED
            -- URI for an external script --
        defer   (defer)        #IMPLIED
            -- UA may defer execution of script --
        event   CDATA          #IMPLIED
            -- reserved for possible future use --
        for     %URI;          #IMPLIED
            -- reserved for possible future use -->

As the type is required isntances are initialised with
text/javascript."""
    XMLNAME = (XHTML_NAMESPACE, 'script')
    XMLATTR_charset = 'charset'
    XMLATTR_type = ('type', MediaType.from_str, to_text)
    XMLATTR_src = ('src', uri.URI.from_octets, to_text)
    XMLATTR_defer = ('defer', Defer.from_str_lower, Defer.to_str)
    XMLCONTENT = xml.XMLMixedContent
    SGMLCONTENT = xml.SGMLCDATA
    """We use the special attribute SGMLCONTENT to signal to the parser
    that we'll be using CDATA mode when parsing this element. This
    parser mode is not available to regular XML documents.  It parses
    character data until it finds the string '</'.  Strictly speaking
    this is the only string you need to escape inside a SCRIPT tag.

    In reality, there is a lot of content out there that fails to escape
    this and our parser is a little more generous (and broken) as it
    continues to parse character data until it finds '</script'."""

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.type = MediaType('text', 'javascript')


class Select(AttrsMixin, FormCtrlMixin, XHTMLElement):

    """Select element
::

    <!ELEMENT SELECT - - (OPTGROUP|OPTION)+ -- option selector -->
    <!ATTLIST SELECT
        %attrs;     -- %coreattrs, %i18n, %events --
        name        CDATA       #IMPLIED  -- field name --
        size        NUMBER      #IMPLIED  -- rows visible --
        multiple    (multiple)  #IMPLIED  -- default is single selection --
        disabled    (disabled)  #IMPLIED  -- unavailable in this context --
        tabindex    NUMBER      #IMPLIED  -- position in tabbing order --
        onfocus     %Script;    #IMPLIED  -- the element got the focus --
        onblur      %Script;    #IMPLIED  -- the element lost the focus --
        onchange    %Script;    #IMPLIED  -- the element value was changed --
        %reserved;  -- reserved for possible future use --
        >

No custom mapping is provided for the event handlers."""
    XMLNAME = (XHTML_NAMESPACE, 'select')
    XMLATTR_name = 'name'
    XMLATTR_size = ('size', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_multiple = ('multiple', Multiple.from_str_lower, Multiple.to_str)
    XMLATTR_disabled = ('disabled', Disabled.from_str_lower, Disabled.to_str)
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)
    XMLCONTENT = xml.ElementType.ElementContent

    def check_model(self, child_class):
        if issubclass(child_class, (Option, OptGroup)):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Option" %
            (child_class.__name__, self.__class__.__name__))


class Small(PreExclusionMixin, FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'small')


class Span(AttrsMixin, SpecialMixin, InlineContainer):

    """Represents a span of text
::

    <!ELEMENT SPAN - - (%inline;)*
        -- generic language/style container -->
    <!ATTLIST SPAN
        %attrs;         -- %coreattrs, %i18n, %events --
        %reserved;      -- reserved for possible future use --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'span')


class Strike(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'strike')


class Strong(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'strong')


class Style(I18nMixin, HeadMiscMixin, XHTMLElement):

    """Represents the style element
::

    <!ELEMENT STYLE     - - %StyleSheet     -- style info -->
    <!ATTLIST STYLE
        %i18n;      -- lang, dir, for use with title --
        type        %ContentType;  #REQUIRED
            -- content type of style language --
        media       %MediaDesc;    #IMPLIED
            -- designed for use with these media --
        title       %Text;         #IMPLIED
            -- advisory title --
        >

As the content type is required instances are initialised with
text/css."""
    XMLNAME = (XHTML_NAMESPACE, 'style')
    XMLATTR_type = ('type', MediaType.from_str, to_text)
    XMLATTR_media = ('media', MediaDesc.from_str, to_text)
    XMLATTR_title = 'title'
    XMLCONTENT = xml.XMLMixedContent
    SGMLCONTENT = xml.SGMLCDATA
    """See note in :class:`Script.SGMLCONTENT`"""

    def __init__(self, parent):
        XHTMLElement.__init__(self, parent)
        self.type = MediaType('text', 'css')


class Sub(AttrsMixin, PreExclusionMixin, SpecialMixin, InlineContainer):

    """Represents a subscript
::

    <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
    <!ATTLIST (SUB|SUP)     %attrs;     -- %coreattrs, %i18n, %events -->
    """
    XMLNAME = (XHTML_NAMESPACE, 'sub')


class Sup(AttrsMixin, PreExclusionMixin, SpecialMixin, InlineContainer):

    """Represents a superscript
::

    <!ELEMENT (SUB|SUP) - - (%inline;)*    -- subscript, superscript -->
    <!ATTLIST (SUB|SUP)     %attrs;     -- %coreattrs, %i18n, %events -->
    """
    XMLNAME = (XHTML_NAMESPACE, 'sup')


class Table(AttrsMixin, ReservedMixin, BlockMixin, XHTMLElement):

    """Represents a table
::

    <!ELEMENT TABLE - - (CAPTION?, (COL*|COLGROUP*), THEAD?, TFOOT?,
                         TBODY+)>
    <!ATTLIST TABLE                 -- table element --
        %attrs;         -- %coreattrs, %i18n, %events --
        summary         %Text;      #IMPLIED
            -- purpose/structure for speech output--
        width           %Length;    #IMPLIED
            -- table width --
        border          %Pixels;    #IMPLIED
            -- controls frame width around table --
        frame           %TFrame;    #IMPLIED
            -- which parts of frame to render --
        rules           %TRules;    #IMPLIED
            -- rulings between rows and cols --
        cellspacing     %Length;    #IMPLIED
            -- spacing between cells --
        cellpadding     %Length;    #IMPLIED
            -- spacing within cells --
        align           %TAlign;    #IMPLIED
            -- table position relative to window --
        bgcolor         %Color;     #IMPLIED
            -- background color for cells --
        %reserved;      -- reserved for possible future use --
        datapagesize    CDATA       #IMPLIED
            -- reserved for possible future use --
        >

The align and bgcolor attributes are only defined in the loose DTD and
are not mapped.  The datapagesize is also not mapped.

When parsing we are generous in allowing data to automatically start the
corresponding TBody (and hence TR+TD)."""
    XMLNAME = (XHTML_NAMESPACE, 'table')
    XMLATTR_summary = 'summary'
    XMLATTR_width = ('width', Length.from_str, to_text)
    XMLATTR_border = ('border', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_frame = ('frame', TFrame.from_str, TFrame.to_str)
    XMLATTR_rules = ('rules', TRules.from_str, TRules.to_str)
    XMLATTR_cellspacing = ('cellspacing', Length.from_str, to_text)
    XMLATTR_cellpadding = ('cellpadding', Length.from_str, to_text)
    XMLCONTENT = xml.ElementType.ElementContent

    def __init__(self, parent):
        super(Table, self).__init__(parent)
        self.Caption = None
        self.TableColMixin = []
        self.THead = None
        self.TFoot = None
        self.TBody = []

    def get_children(self):
        if self.Caption:
            yield self.Caption
        for c in self.TableColMixin:
            yield c
        if self.THead:
            yield self.THead
        if self.TFoot:
            yield self.TFoot
        for c in self.TBody:
            yield c

    def check_model(self, child_class):
        if issubclass(
                child_class,
                (Caption, THead, TFoot, TBody, Col, ColGroup, TBody)) or \
                not issubclass(child_class, XHTMLMixin):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Option" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        if issubclass(stag_class, (str, TR)):
            return TBody
        else:
            return stag_class


class TBody(AttrsMixin, CellAlignMixin, TRContainer):

    """Represents a table body
::

    <!ELEMENT TBODY    O O (TR)+           -- table body -->
    <!ATTLIST (THEAD|TBODY|TFOOT)       -- table section --
        %attrs;         -- %coreattrs, %i18n, %events --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;    -- vertical alignment in cells --
        >

This is an unusual element as it is rarely seen in HTML because both
start and end tags can be omitted.  However, it appears as a required
part of TABLE's content model so will always be present if any TR
elements are present (unless they are contained in in THEAD or TFOOT)."""
    XMLNAME = (XHTML_NAMESPACE, 'tbody')
    XMLCONTENT = xml.ElementType.ElementContent


class TD(TableCellMixin, FlowContainer):

    """Represents a table cell
::

    <!ELEMENT (TH|TD)  - O (%flow;)*
        -- table header cell, table data cell-->

For attribute information see :class:`TableCellMixin`."""
    XMLNAME = (XHTML_NAMESPACE, 'td')
    XMLCONTENT = xml.XMLMixedContent


class TextArea(AttrsMixin, ReservedMixin, FormCtrlMixin, XHTMLElement):

    """TextArea element
::

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
      %reserved;    -- reserved for possible future use --
      >

The event handlers are not mapped.  As rows and cols are both required
the constructor provides initial values of 1 and 80 respectively."""
    XMLNAME = (XHTML_NAMESPACE, 'textarea')
    XMLATTR_name = 'name'
    XMLATTR_rows = ('rows', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_cols = ('cols', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_disabled = ('disabled', Disabled.from_str, Disabled.to_str)
    XMLATTR_readonly = ('readonly', ReadOnly.from_str, ReadOnly.to_str)
    XMLATTR_tabindex = ('tabindex', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_accesskey = ('accesskey', character_from_str, None)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        super(TextArea, self).__init__(parent)
        self.rows = 1
        self.cols = 80


class TFoot(AttrsMixin, CellAlignMixin, TRContainer):

    """Represents a table footer
::

    <!ELEMENT TFOOT    - O (TR)+        -- table footer -->
    <!ATTLIST (THEAD|TBODY|TFOOT)       -- table section --
        %attrs;         -- %coreattrs, %i18n, %events --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;    -- vertical alignment in cells --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'tfoot')
    XMLCONTENT = xml.ElementType.ElementContent


class TH(TableCellMixin, FlowContainer):

    """Represents a table header cell
::

    <!ELEMENT (TH|TD)  - O (%flow;)*
        -- table header cell, table data cell-->

For attribute information see :class:`TableCellMixin`."""
    XMLNAME = (XHTML_NAMESPACE, 'th')
    XMLCONTENT = xml.XMLMixedContent


class THead(AttrsMixin, CellAlignMixin, TRContainer):

    """Represents a table header
::

    <!ELEMENT THEAD    - O (TR)+        -- table header -->
    <!ATTLIST (THEAD|TBODY|TFOOT)       -- table section --
        %attrs;         -- %coreattrs, %i18n, %events --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;    -- vertical alignment in cells --
        >"""
    XMLNAME = (XHTML_NAMESPACE, 'thead')
    XMLCONTENT = xml.ElementType.ElementContent


class Title(I18nMixin, HeadContentMixin, XHTMLElement):

    """Represents the TITLE element
::

    <!ELEMENT TITLE - - (#PCDATA) -(%head.misc;) -- document title -->
    <!ATTLIST TITLE %i18n   >"""
    XMLNAME = (XHTML_NAMESPACE, 'title')
    XMLCONTENT = xml.XMLMixedContent


class TR(AttrsMixin, CellAlignMixin, XHTMLElement):

    """Represents a table row
::

    <!ELEMENT TR    - O (TH|TD)+        -- table row -->
    <!ATTLIST TR        -- table row --
        %attrs;         -- %coreattrs, %i18n, %events --
        %cellhalign;    -- horizontal alignment in cells --
        %cellvalign;    -- vertical alignment in cells --
        bgcolor     %Color;     #IMPLIED
            -- background color for row --
        >

The bgcolor attribute is only defined by the loose DTD so is left
unmapped.  We treat data inside <tr> as starting an implicit <td>
element."""
    XMLNAME = (XHTML_NAMESPACE, 'tr')
    XMLCONTENT = xml.ElementType.ElementContent

    def check_model(self, child_class):
        if issubclass(child_class, (TH, TD)):
            return
        raise XHTMLValidityError(
            "%s not allowed in %s, expected Option" %
            (child_class.__name__, self.__class__.__name__))

    def get_child_class(self, stag_class):
        if issubclass(stag_class, str):
            return TD
        try:
            self.check_model(stag_class)
            return stag_class
        except XHTMLValidityError:
            return None


class TT(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'tt')


class U(FontStyle):
    XMLNAME = (XHTML_NAMESPACE, 'u')


class UL(List):

    """Represents the unordered list element
::

    <!ELEMENT UL - - (LI)+      -- ordered list -->
    <!ATTLIST UL
        %attrs;     -- %coreattrs, %i18n, %events --
        type        %ULStyle;   #IMPLIED    -- bullet style --
        compact     (compact)   #IMPLIED
            -- reduced interitem spacing --
        >

The type and compact attributes are only defined by the loose DTD and
are left unmapped."""
    XMLNAME = (XHTML_NAMESPACE, 'ul')
    XMLCONTENT = xml.ElementType.ElementContent


class Var(Phrase):
    XMLNAME = (XHTML_NAMESPACE, 'var')


#   HTML Parser
#   -----------
#

class HTMLParser(xmlns.XMLNSParser):

    """Custom HTML parser

    This variation on the base :class:`pyslet.xml.namespace.XMLNSParser`
    does not have to be customised much.  Most of the hard work is done
    by the existing mechanisms for inferring missing tags.
    """

    def __init__(self, entity=None, **kws):
        xmlns.XMLNSParser.__init__(self, entity)
        """A flag that indicates if the parser is in xml mode."""

    def lookup_predefined_entity(self, name):
        """Supports HTML entity references

        XML includes only a small number of basic entity references to
        allow the most basic encoding of documents, for example &lt;,
        &amp;, and so on.

        HTML supports a much larger set of character entity references:
        https://www.w3.org/TR/html401/sgml/entities.html
        """
        codepoint = name2codepoint.get(name, None)
        if codepoint is None:
            return None
        else:
            return character(codepoint)

    def parse_prolog(self):
        """Custom prolog parsing.

        We override this method to enable us to dynamically set the
        parser options based on the presence of an XML declaration or
        DOCTYPE."""
        if self.parse_literal('<?xml'):
            self.parse_xml_decl(True)
        else:
            self.declaration = None
            self.sgml_namecase_general = True
            self.sgml_omittag = True
            self.sgml_shorttag = True
            self.sgml_content = True
            self.dont_check_wellformedness = True
        self.entity.keep_encoding()
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
            if self.sgml_namecase_general:
                self.dtd.name = 'HTML'
                # no XML declaration, and no DOCTYPE, are we at the first
                # element?
                if self.the_char != '<':
                    # this document starts with character data but we
                    # want to force any leading space to be included, as
                    # that is usually the intention of authors writing
                    # HTML fragments, particularly as they are in
                    # <![CDATA[ sections in the enclosing document,
                    # e.g., <tag>Yes I<htmlFrag><![CDATA[
                    # <b>did</b>]]></htmlFrag></tag> we do this by
                    # tricking the parser with a character reference
                    if s:
                        s[0] = "&#x%02X;" % ord(s[0])
                    self.buff_text(''.join(s))
            else:
                self.dtd.name = 'html'


XHTML_MIMETYPES = {
    None: False,
    'text/xml': True,
    'text/html': False
}


class XHTMLDocument(xmlns.NSDocument):

    """Represents an HTML document.

    Although HTML documents are not always represented using XML they
    can be, and therefore we base our implementation on the
    :class:`pyslet.xml.namespace.NSDocument` class, the
    namespace-aware variant of the basic :class:`pyslet.xml.Document`
    class."""

    class_map = {}
    """Data member used to store a mapping from element names to the classes
    used to represent them.  This mapping is initialized when the module is
    loaded."""

    default_ns = XHTML_NAMESPACE  #: the default namespace for HTML elements

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)

    def XMLParser(self, entity):    # noqa
        """Create a parser suitable for parsing HTML

        We override the basic XML parser to use a custom parser that is
        intelligent about the use of omitted tags, elements defined to
        have CDATA content and other SGML-based variations.  If the
        document starts with an XML declaration then the normal XML
        parser is used instead.

        You won't normally need to call this method as it is invoked
        automatically when you call :meth:`pyslet.xml.Document.read`.

        The result is always a proper element hierarchy rooted in an
        HTML node, even if no tags are present at all the parser will
        construct an HTML document containing a single :class:`Div`
        element to hold the parsed text."""
        xml_hint = XHTML_MIMETYPES.get(entity.mimetype, None)
        if xml_hint is not None:
            return HTMLParser(entity)
        else:
            raise XHTMLMimeTypeError(entity.mimetype)

    def get_child_class(self, stag_class):
        # check for frameset document, support omitted start tags
        if self.dtd and self.dtd.external_id and \
                self.dtd.external_id.public == HTML40_FRAMESET_PUBLICID:
            return HTMLFrameset
        else:
            return HTML

    def get_element_class(self, name):
        if self.root is None:
            # trying to determine the root element
            if self.dtd and self.dtd.external_id and \
                    self.dtd.external_id.public == HTML40_FRAMESET_PUBLICID:
                lcname = (name[0], name[1].lower())
                if lcname == (XHTML_NAMESPACE, 'html'):
                    return HTMLFrameset
                elif lcname == (XHTML_NAMESPACE, 'noframes'):
                    return NoFramesFrameset
        elif isinstance(self.root, HTMLFrameset):
            lcname = (name[0], name[1].lower())
            if lcname == (XHTML_NAMESPACE, 'noframes'):
                return NoFramesFrameset
        # fall through to default handling
        eclass = XHTMLDocument.class_map.get(name, None)
        if eclass is None:
            lcname = (name[0], name[1].lower())
            eclass = XHTMLDocument.class_map.get(lcname, xmlns.XMLNSElement)
        return eclass

xmlns.map_class_elements(XHTMLDocument.class_map, globals())
