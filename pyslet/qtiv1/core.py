#! /usr/bin/env python

import pyslet.xml.structures as xml
import pyslet.xml.xsdatatypes as xsi
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.html401 as html

import string


class QTIError(Exception):

    """All errors raised by this module are derived from QTIError."""
    pass


class QTIUnimplementedError(QTIError):

    """A feature of QTI v1 that is not yet implemented by this module."""
    pass


QTI_SOURCE = 'QTIv1'  # : Constant used for setting the LOM source value


def MakeValidName(name):
    """This function takes a string that is supposed to match the
    production for Name in XML and forces it to comply by replacing
    illegal characters with '_'.  If name starts with a valid name
    character but not a valid name start character, it is prefixed
    with '_' too."""
    if name:
        goodName = []
        if not xml.is_name_start_char(name[0]):
            goodName.append(u'_')
        for c in name:
            if xml.is_name_char(c):
                goodName.append(c)
            else:
                goodName.append(u'_')
        return string.join(goodName, u'')
    else:
        return u'_'


def ParseYesNo(src):
    """Returns a True/False parsed from a "Yes" / "No" string.

    This function is generous in what it accepts, it will accept mixed case and
    strips surrounding space.  It returns True if the resulting string matches
    "yes" and False otherwise.

    Reverses the transformation defined by :py:func:`FormatYesNo`."""
    return src.strip().lower() == u'yes'


def FormatYesNo(value):
    """Returns "Yes" if *value* is True, "No" otherwise.

    Reverses the transformation defined by :py:func:`ParseYesNo`."""
    if value:
        return u'Yes'
    else:
        return u'No'


class Action(xsi.Enumeration):

    """Action enumeration (for :py:class:`pyslet.qtiv1.common.SetVar`::

    (Set | Add | Subtract | Multiply | Divide )  'Set'

    Defines constants for the above action types.  Usage example::

            Action.Add

    Note that::

            Action.DEFAULT == Action.Set

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Set': 1,
        'Add': 2,
        'Subtract': 3,
        'Multiply': 4,
        'Divide': 5
    }


class Area(xsi.Enumeration):

    """Area enumeration::

    (Ellipse | Rectangle | Bounded )  'Ellipse'

    Defines constants for the above area types.  Usage example::

            Area.Rectangle

    Note that::

            Area.DEFAULT == Area.Ellipse

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Ellipse': 1,
        'Rectangle': 2,
        'Bounded': 3
    }
    aliases = {
        None: 'Ellipse'
    }


def MigrateV2AreaCoords(area, value, log):
    """Returns a tuple of (shape,coords object) representing the area.

    *	*area* is one of the :py:class:`Area` constants.

    *	*value* is the string containing the content of the element to which
            the area applies.

    This conversion is generous because the separators have never been well
    defined and in some cases content uses a mixture of space and ','.

    Note also that the definition of rarea was updated in the 1.2.1 errata and
    that affects this algorithm.  The clarification on the definition of
    ellipse from radii to diameters might mean that some content ends up with
    hotspots that are too small but this is safer than hotspots that are too
    large.

    Example::

            import pyslet.qtiv1.core as qticore1
            import pyslet.qtiv2.core as qticore2
            import pyslet.html40_1991224 as html
            log=[]
            shape,coords=qticore1.MigrateV2AreaCoords(qticore1.Area.Ellipse,"10,10,2,2",log)
            # returns (qticore2.Shape.circle, html.Coords([10, 10, 1]) )

    Note that Ellipse was deprecated in QTI version 2::

            import pyslet.qtiv1.core as qticore1
            import pyslet.html40_1991224 as html
            log=[]
            shape,coords=qticore1.MigrateV2AreaCoords(qticore1.Area.Ellipse,"10,10,2,4",log)
            print log
            # outputs the following...

            ['Warning: ellipse shape is deprecated in version 2']"""
    coords = []
    vStr = []
    sep = 0
    for c in value:
        if c in "0123456789.":
            if sep and vStr:
                coords.append(int(float(string.join(vStr, ''))))
                sep = 0
                vStr = []
            vStr.append(c)
        else:
            sep = 1
    if vStr:
        coords.append(int(float(string.join(vStr, ''))))
    if area == Area.Rectangle:
        if len(coords) < 4:
            log.append(
                "Error: not enough coordinates for rectangle,"
                " padding with zeros")
            while len(coords) < 4:
                coords.append(0)
        shape = qtiv2.core.Shape.rect
        coords = [coords[0], coords[1], coords[
            0] + coords[3] - 1, coords[1] + coords[2] - 1]
    elif area == Area.Ellipse:
        if len(coords) < 4:
            if len(corrds) < 2:
                log.append(
                    "Error: not enough coordinates to locate ellipse,"
                    " padding with zero")
                while len(coords) < 2:
                    coords.append(0)
            if len(coords) == 2:
                log.append(
                    "Error: ellipse has no radius, treating as circule"
                    " radius 4")
                coords = coords + [8, 8]
            elif len(coords) == 3:
                log.append(
                    "Error: only one radius given for ellipse,"
                    " assuming circular")
                coords.append(coords[-1])
        if coords[2] == coords[3]:
            r = coords[2] // 2  # centre-pixel coordinate model again
            coords = [coords[0], coords[1], r]
            shape = qtiv2.core.Shape.circle
        else:
            log.append("Warning: ellipse shape is deprecated in version 2")
            coords = [coords[0], coords[1], coords[2] // 2, coords[3] // 2]
            shape = qtiv2.core.Shape.ellipse
    else:
        shape = qtiv2.core.Shape.poly
    return shape, html.Coords(coords)


class FeedbackStyle(xsi.Enumeration):

    """feedbackstyle enumeration::

    (Complete | Incremental | Multilevel | Proprietary )  'Complete'

    Defines constants for the above feedback style.  Usage example::

            FeedbackStyle.Decimal

    Note that::

            FeedbackStyle.DEFAULT == FeedbackStyle.Complete

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Complete': 1,
        'Incremental': 2,
        'Multilevel': 3,
        'Proprietary': 4
    }


class FeedbackType(xsi.Enumeration):

    """feedbacktype enumeration::

    (Response | Solution | Hint )  'Response'

    Defines constants for the above types of feedback.  Usage example::

            FeedbackType.Decimal

    Note that::

            FeedbackType.DEFAULT == FeedbackType.Response

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Response': 1,
        'Solution': 2,
        'Hint': 3
    }


class FIBType(xsi.Enumeration):

    """Fill-in-the-blank type enumeration::

    (String | Integer | Decimal | Scientific )  'String'

    Defines constants for the above fill-in-the-blank types.  Usage example::

            FIBType.Decimal

    Note that::

            FIBType.DEFAULT == FIBType.String

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'String': 1,
        'Integer': 2,
        'Decimal': 3,
        'Scientific': 4
    }
    aliases = {
        None: 'String'
    }


class MDOperator(xsi.EnumerationNoCase):

    """Metadata operator enumeration for
    :py:class:`pyslet.qtiv1.sao.SelectionMetadata`::

    (EQ | NEQ | LT | LTE | GT | GTE )

    Defines constants for the above operators.  Usage example::

            MDOperator.EQ

    Lower-case aliases of the constants are provided for compatibility.

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        u'EQ': 1,
        u'NEQ': 2,
        u'LT': 3,
        u'LTE': 4,
        u'GT': 5,
        u'GTE': 6
    }


class NumType(xsi.Enumeration):

    """numtype enumeration::

    (Integer | Decimal | Scientific )  'Integer'

    Defines constants for the above numeric types.  Usage example::

            NumType.Scientific

    Note that::

            NumType.DEFAULT == NumType.Integer

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Integer': 1,
        'Decimal': 2,
        'Scientific': 3
    }
    aliases = {
        None: 'Integer'
    }


class Orientation(xsi.Enumeration):

    """Orientation enumeration::

    (Horizontal | Vertical )  'Horizontal'

    Defines constants for the above orientation types.  Usage example::

            Orientation.Horizontal

    Note that::

            Orientation.DEFAULT == Orientation.Horizontal

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Horizontal': 1,
        'Vertical': 2,
    }
    aliases = {
        None: 'Horizontal'
    }


def MigrateV2Orientation(orientation):
    """Maps a v1 orientation onto the corresponding v2 constant.

    Raises KeyError if *orientation* is not one of the :py:class:`Orientation`
    constants."""
    return {
        Orientation.Horizontal: qtiv2.core.Orientation.horizontal,
        Orientation.Vertical: qtiv2.core.Orientation.vertical
    }[orientation]


class PromptType(xsi.Enumeration):

    """Prompt type enumeration::

    (Box | Dashline | Asterisk | Underline )

    Defines constants for the above prompt types.  Usage example::

            PromptType.Dashline

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Box': 1,
        'Dashline': 2,
        'Asterisk': 3,
        'Underline': 4
    }


class RCardinality(xsi.Enumeration):

    """rcardinality enumeration::

    (Single | Multiple | Ordered )  'Single'

    Defines constants for the above cardinality types.  Usage example::

            RCardinality.Multiple

    Note that::

            RCardinality.DEFAULT == RCardinality.Single

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Single': 1,
        'Multiple': 2,
        'Ordered': 3
    }


def MigrateV2Cardinality(rCardinality):
    """Maps a v1 cardinality onto the corresponding v2 constant.

    Raises KeyError if *rCardinality* is not one of the
    :py:class:`RCardinality` constants."""
    return {
        RCardinality.Single: qtiv2.variables.Cardinality.single,
        RCardinality.Multiple: qtiv2.variables.Cardinality.multiple,
        RCardinality.Ordered: qtiv2.variables.Cardinality.ordered
    }[rCardinality]


TestOperator = MDOperator
"""A simple alias of :py:class:`MDOperator` defined for
:py:class:`pyslet.qtiv1.outcomes.VariableTest`"""


class VarType(xsi.Enumeration):

    """vartype enumeration::

        (Integer | String | Decimal | Scientific | Boolean | Enumerated |
            Set )  'Integer'

    Defines constants for the above view types.  Usage example::

            VarType.String

    Note that::

            VarType.DEFAULT == VarType.Integer

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'Integer': 1,
        'String': 2,
        'Decimal': 3,
        'Scientific': 4,
        'Boolean': 5,
        'Enumerated': 5,
        'Set': 6
    }


def MigrateV2VarType(vartype, log):
    """Returns the v2 BaseType representing the v1 *vartype*.

    Note that we reduce both Decimal and Scientific to the float types.  In
    version 2 the BaseType values were chosen to map onto the typical types
    available in most programming languages.  The representation of the number
    in decimal or exponent form is considered to be part of the interaction or
    the presentation rather than part of the underlying processing model.
    Although there clearly are use cases where retaining this distinction would
    have been an advantage the quality of implementation was likely to be poor
    and use cases that require a distinction are now implemented in more
    cumbersome, but probably more interoperable ways.

    Note also that the poorly defined Set type in version 1 maps to an
    identifier in version 2 on the assumption that the cardinality will be
    upgraded as necessary.

    Raises KeyError if *vartype* is not one of the :py:class:`VarType`
    constants."""
    return {
        VarType.Integer: qtiv2.variables.BaseType.integer,
        VarType.String: qtiv2.variables.BaseType.string,
        VarType.Decimal: qtiv2.variables.BaseType.float,
        VarType.Scientific: qtiv2.variables.BaseType.float,
        VarType.Boolean: qtiv2.variables.BaseType.boolean,
        VarType.Enumerated: qtiv2.variables.BaseType.identifier,
        VarType.Set: qtiv2.variables.BaseType.identifier
    }[vartype]


class View(xsi.EnumerationNoCase):

    """View enumeration::

            (All | Administrator | AdminAuthority | Assessor | Author |
            Candidate | InvigilatorProctor | Psychometrician | Scorer |
            Tutor )  'All'

    Defines constants for the above view types.  Usage example::

            View.Candidate

    Note that::

            View.DEFAULT == View.All

    In addition to the constants defined in the specification we add two
    aliases which are in common use::

            (Invigilator | Proctor)

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'All': 1,
        'Administrator': 2,
        'AdminAuthority': 3,
        'Assessor': 4,
        'Author': 5,
        'Candidate': 6,
        'InvigilatorProctor': 7,
        'Psychometrician': 8,
        'Scorer': 9,
        'Tutor': 10
    }
    aliases = {
        None: 'All',
        'Proctor': 'InvigilatorProctor',
        'proctor': 'InvigilatorProctor',
        'Invigilator': 'InvigilatorProctor',
        'invigilator': 'InvigilatorProctor'
    }


def MigrateV2View(view, log):
    """Returns a list of v2 view values representing the v1 *view*.

    The use of a list as the return type enables mapping of the special value
    'All', which has no direct equivalent in version 2 other than providing all
    the defined views.

    Raises KeyError if *view* is not one of the :py:class:`View` constants.

    This function will log warnings when migrating the following v1 values:
    Administrator, AdminAuthority, Assessor and Psychometrician"""
    newView, warnFlag = {
        View.Administrator: ([qtiv2.core.View.proctor], True),
        View.AdminAuthority: ([qtiv2.core.View.proctor], True),
        View.Assessor: ([qtiv2.core.View.scorer], True),
        View.Author: ([qtiv2.core.View.author], False),
        View.Candidate: ([qtiv2.core.View.candidate], False),
        View.Invigilator: ([qtiv2.core.View.proctor], False),
        View.Proctor: ([qtiv2.core.View.proctor], False),
        View.InvigilatorProctor: ([qtiv2.core.View.proctor], False),
        View.Psychometrician: ([qtiv2.core.View.testConstructor], True),
        View.Scorer: ([qtiv2.core.View.scorer], False),
        View.Tutor: ([qtiv2.core.View.tutor], False),
        View.All: ([
            qtiv2.core.View.author,
            qtiv2.core.View.candidate,
            qtiv2.core.View.proctor,
            qtiv2.core.View.scorer,
            qtiv2.core.View.testConstructor,
            qtiv2.core.View.tutor], False)
    }[view]
    if warnFlag:
        log.append("Warning: changing view %s to %s" % (
            View.to_str(view), qtiv2.core.View.list_to_str(newView)))
    return newView


class QTIElement(xml.Element):

    """Base class for all elements defined by the QTI specification"""

    def DeclareMetadata(self, label, entry, definition=None):
        """Declares a piece of metadata to be associated with the element.

        Most QTIElements will be contained by some type of metadata container
        that collects metadata in a format suitable for easy lookup and export
        to other metadata formats.  The default implementation simply passes
        the call to the parent element or, if there is no parent, the
        declaration is ignored.

        For more information see :py:class:`MetadataContainer`."""
        if isinstance(self.parent, QTIElement):
            self.parent.DeclareMetadata(label, entry, definition)
        else:
            pass


class ObjectMixin:

    """Mix-in class for elements that can be inside :py:class:`ObjectBank`::

    (section | item)+"""
    pass


class SectionItemMixin:

    """Mix-in class for objects that can be in section objects::

    (itemref | item | sectionref | section)*"""
    pass


class SectionMixin(SectionItemMixin):

    """Mix-in class for objects that can be in assessment objects::

    (sectionref | section)+"""
    pass
