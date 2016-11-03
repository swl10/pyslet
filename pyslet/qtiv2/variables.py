#! /usr/bin/env python

import hashlib
import itertools
import logging
import os
import random
import time

from io import BytesIO

from . import core
from . import tests
from .. import html401 as html
from ..http import params
from ..pep8 import MigratedClass, old_method
from ..py2 import (
    BoolMixin,
    byte,
    dict_keys,
    force_text,
    is_text,
    join_bytes,
    long2,
    range3,
    SortableMixin,
    uempty,
    ul)
from ..rfc2396 import URI
from ..xml import structures as xml
from ..xml import namespace as xmlns
from ..xml import xsdatatypes as xsi


class SessionKeyMismatch(core.QTIError):

    """Exception raised when a session is invoked with the wrong key."""
    pass


class SessionKeyExpired(core.QTIError):

    """Exception raised when a session is invoked with an expired key."""
    pass


class SessionActionMissing(core.QTIError):

    """Exception raised when an unrecognised action is handled by a test
    session."""


class BadSessionParams(core.QTIError):

    """Data submitted is incompatible with session."""


class BaseType(xsi.EnumerationNoCase):

    """A base-type is simply a description of a set of atomic values (atomic to
    this specification). Note that several of the baseTypes used to define the
    runtime data model have identical definitions to those of the basic data
    types used to define the values for attributes in the specification itself.
    The use of an enumeration to define the set of baseTypes used in the
    runtime model, as opposed to the use of classes with similar names, is
    designed to help distinguish between these two distinct levels of
    modelling::

            <xsd:simpleType name="baseType.Type">
                    <xsd:restriction base="xsd:NMTOKEN">
                            <xsd:enumeration value="boolean"/>
                            <xsd:enumeration value="directedPair"/>
                            <xsd:enumeration value="duration"/>
                            <xsd:enumeration value="file"/>
                            <xsd:enumeration value="float"/>
                            <xsd:enumeration value="identifier"/>
                            <xsd:enumeration value="integer"/>
                            <xsd:enumeration value="pair"/>
                            <xsd:enumeration value="point"/>
                            <xsd:enumeration value="string"/>
                            <xsd:enumeration value="uri"/>
                    </xsd:restriction>
            </xsd:simpleType>

    Defines constants for the above base types.  Usage example::

            BaseType.float

    There is no default::

            BaseType.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'boolean': 1,
        'directedPair': 2,
        'duration': 3,
        'file': 4,
        'float': 5,
        'identifier': 6,
        'integer': 7,
        'pair': 8,
        'point': 9,
        'string': 10,
        'uri': 11
    }


def check_base_types(*base_type):
    """Checks base types for compatibility.  None is treated as a wild
    card that matches all base types.  It returns the resulting base
    type, or None if all are wild cards.  If they don't match then a
    ProcessingError is raised."""
    breturn = None
    for b in base_type:
        if b is None:
            continue
        elif breturn is None:
            breturn = b
        elif b != breturn:
            raise core.ProcessingError("Base type mismatch: %s and %s" % (
                BaseType.to_str(breturn),
                BaseType.to_str(b)))
    return breturn


def check_numerical_types(*base_type):
    """Checks base types for numerical compatibility.  None is treated
    as a wild card that matches all base types.  It returns the
    resulting base type, or None if all are wild cards.  If they don't
    match then a ProcessingError is raised."""
    breturn = None
    for b in base_type:
        if b is None:
            continue
        elif b not in (BaseType.float, BaseType.integer):
            raise core.ProcessingError(
                "Numeric type required, found: %s" % BaseType.to_str(b))
        elif breturn is None:
            breturn = b
        elif b != breturn:
            # we only return integer when all values are of type integer, so we
            # must return float!
            breturn = BaseType.float
    return breturn


class Cardinality(xsi.Enumeration):

    """An expression or itemVariable can either be single-valued or
    multi-valued. A multi-valued expression (or variable) is called a
    container.
    A container contains a list of values, this list may be empty in which case
    it is treated as NULL. All the values in a multiple or ordered container
    are drawn from the same value set::

            <xsd:simpleType name="cardinality.Type">
                    <xsd:restriction base="xsd:NMTOKEN">
                            <xsd:enumeration value="multiple"/>
                            <xsd:enumeration value="ordered"/>
                            <xsd:enumeration value="record"/>
                            <xsd:enumeration value="single"/>
                    </xsd:restriction>
            </xsd:simpleType>

    Defines constants for the above carinalities.  Usage example::

            Cardinality.multiple

    There is no default::

            Cardinality.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""
    decode = {
        'multiple': 1,
        'ordered': 2,
        'record': 3,
        'single': 4
    }


def check_cardinalities(*cardinality):
    """Checks cardinality values for compatibility.  None is treated as
    a wild card that matches all cardinalities.  It returns the
    resulting cardinality, or None if all are wild cards.  If they don't
    match then a ProcessingError is raised."""
    creturn = None
    for c in cardinality:
        if c is None:
            continue
        elif creturn is None:
            creturn = c
        elif c != creturn:
            raise core.ProcessingError("Cardinality mismatch: %s and %s" % (
                Cardinality.to_str(creturn),
                Cardinality.to_str(c)))
    return creturn


class ValueElement(core.QTIElement):

    """A class that can represent a single value of any baseType in variable
    declarations and result reports::

            <xsd:attributeGroup name="value.AttrGroup">
                    <xsd:attribute name="fieldIdentifier"
                                type="identifier.Type" use="optional"/>
                    <xsd:attribute name="baseType" type="baseType.Type"
                                use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'value')
    XMLATTR_baseType = (
        'baseType', BaseType.from_str_lower, BaseType.to_str)
    XMLATTR_fieldIdentifier = (
        'fieldIdentifier', core.ValidateIdentifier, lambda x: x)
    XMLCONTENT = xml.XMLMixedContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.fieldIdentifier = None
        self.baseType = None


class NullResult(core.QTIError):

    """Error raised when an operation on :py:class:`Value` instances results in
    NULL. Null errors can be passed a custom :py:class:`Value` instance (which
    must be a valid NULL representation) which it stores to enable code like
    this::

            try:
                    # some operation that might result in NULL
                    # ...
            except NullResult,e:
                    return e.value"""

    def __init__(self, value=None):
        core.QTIError.__init__(self, "NULL result error")
        if value is None:
            value = Value()
        self.value = value


class Value(MigratedClass, BoolMixin):

    """Represents a single value in the processing model.

    This class is the heart of the QTI processing model.  This is an abstract
    base class of a class hierarchy that represents the various types of value
    that may be encountered when processing."""

    def __init__(self):
        self.baseType = None
        """One of the :py:class:`BaseType` constants or None if the baseType is
        unknown.

        An unknown baseType acts like a wild-card.  It means that the baseType
        is not determined and could potentially be any of the
        :py:class:`BaseType` values. This distinction has implications for the
        way evaluation is done.  A value with a baseType of None will not raise
        TypeErrors during evaluation if the cardinalities match the context.
        This allows expressions which contain types bound only at runtime to be
        evaluated for validity checking."""
        self.value = None
        """The value of the variable.  The following representations are used
        for values of single cardinality:

        NULL value
            Represented by None

        boolean
            One of the built-in Python values True and False

        directedPair
            A tuple of strings (<source identifier>, <destination identifier>)

        duration
            real number of seconds

        file
            a file like object (supporting seek)

        float
            real number

        identifier
            A text string

        integer
            A plain python integer (QTI does not support long integer values)

        pair
            A *sorted* tuple of strings (<identifier A>, <identifier B>).  We
            sort the identifiers in a pair by python's native string sorting to
            ensure that pair values are comparable.

        point
            A tuple of integers (<x-coordinate>, <y-coordinate>)

        string
            A python string

        uri
            An instance of :py:class:`~pyslet.rfc2396.URI`

        For containers, we use the following structures:

        ordered
            A list of one of the above value types.

        multiple:
            A dictionary with keys that are one of the above value types and
            values that indicate the frequency of that value in the container.

        record:
            A dictionary with keys that are the field identifiers and
            values that Value instances."""

    def set_value(self, value):
        """Sets the value.

        All single values can be set from a single text string
        corresponding to their XML schema defined lexical values
        (*without* character level escaping).  If v is a single Value
        instance then the following always leaves v unchanged::

            v.set_value(unicode(v))     # str() in Python 3

        Value instances can also be set from values of the appropriate
        type as described in :py:attr:`value`.  For base types that are
        represented with tuples we also accept and convert lists.

        Containers values cannot be set from strings."""
        if value is None:
            self.value = None
        else:
            self.value_error(value)

    @old_method('ValueError')
    def value_error(self, value):
        """Raises a ValueError with a debug-friendly message string."""
        raise ValueError(
            "Can't set value of %s %s from %s" %
            (Cardinality.to_str(
                self.cardinality()), BaseType.to_str(
                self.baseType), repr(value)))

    @old_method('Cardinality')
    def cardinality(self):
        """Returns the cardinality of this value.  One of the
        :py:class:`Cardinality` constants.

        By default we return None - indicating unknown cardinality.  This can
        only be the case if the value is a NULL."""
        return None

    @old_method('IsNull')
    def is_null(self):
        """Returns True is this value is NULL, as defined by the QTI
        specification."""
        return self.value is None

    def __bool__(self):
        """The python 'non-zero' test: equivalent to the non-NULL test in QTI.

        Care is therefore needed, for example::

            flag = BooleanValue(False)
            if flag:
                print("All non-NULL values are True")
            if flag.value:
                print("Test the value attribute to access the "
                      "python native value")

            # prints the following...
            All non-NULL values are True"""
        return self.value is not None

    #: Value instances are mutable so cannot be used as dictionary keys
    __hash__ = None

    def __eq__(self, other):
        """The python equality test is treated like the match operator in QTI.

        We add the test that ensures the other value has matching cardinality
        and matching baseType.  The test then proceeds to return True if the
        two python values compare equal and False if they don't.  If either is
        Null we raise NullResult."""
        check_cardinalities(self.cardinality(), other.cardinality())
        if check_base_types(
                self.baseType, other.baseType) == BaseType.duration:
            raise core.ProcessingError("Can't match duration values")
        if self and other:
            return self.value == other.value
        else:
            raise NullResult(BooleanValue())

    def __unicode__(self):
        """Creates a string representation of the object.  The NULL value
        returns None."""
        if self.value is None:
            return uempty
        else:
            raise NotImplementedError(
                "Serialization of %s" % self.__class__.__name__)

    @classmethod
    @old_method('NewValue')
    def new_value(cls, cardinality, base_type=None):
        """Creates a new value instance with *cardinality* and *base_type*."""
        if cardinality == Cardinality.single:
            return SingleValue.new_value(base_type)
        elif cardinality == Cardinality.ordered:
            return OrderedContainer(base_type)
        elif cardinality == Cardinality.multiple:
            return MultipleContainer(base_type)
        elif cardinality == Cardinality.record:
            return RecordContainer()
        else:
            raise ValueError("Unknown cardinality")

    @classmethod
    @old_method('CopyValue')
    def copy_value(cls, value):
        """Creates a new value instance copying *value*."""
        v = cls.new_value(value.cardinality(), value.baseType)
        v.set_value(value.value)
        return v


class SingleValue(Value):

    """Represents all values with single cardinality."""

    def cardinality(self):
        return Cardinality.single

    @classmethod
    def new_value(cls, base_type, value=None):
        """Creates a new instance of a single value with *base_type* and
        *value*"""
        if base_type is None:
            return SingleValue()
        elif base_type == BaseType.boolean:
            return BooleanValue(value)
        elif base_type == BaseType.directedPair:
            return DirectedPairValue(value)
        elif base_type == BaseType.duration:
            return DurationValue(value)
        elif base_type == BaseType.file:
            return FileValue(value)
        elif base_type == BaseType.float:
            return FloatValue(value)
        elif base_type == BaseType.identifier:
            return IdentifierValue(value)
        elif base_type == BaseType.integer:
            return IntegerValue(value)
        elif base_type == BaseType.pair:
            return PairValue(value)
        elif base_type == BaseType.point:
            return PointValue(value)
        elif base_type == BaseType.string:
            return StringValue(value)
        elif base_type == BaseType.uri:
            return URIValue(value)
        else:
            raise ValueError("Unknown base type: %s" %
                             BaseType.to_str(base_type))


class BooleanValue(SingleValue):

    """Represents single values of type :py:class:`BaseType.boolean`."""

    def __init__(self, value=None):
        super(BooleanValue, self).__init__()
        self.baseType = BaseType.boolean
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return xsi.boolean_to_str(self.value)

    def set_value(self, value):
        """If value is a string it will be decoded according to the rules for
        representing boolean values.  Booleans and integers can be used
        directly in the normal python way but other values will raise
        ValueError.  To take advantage of a non-zero test you must explicitly
        force it to be a boolean.  For example::

                # x is a value of unknown type with non-zero test implemented
                v=BooleanValue()
                v.set_value(True if x else False)"""
        if value is None:
            self.value = None
        elif isinstance(value, bool):
            self.value = value
        elif isinstance(value, (int, long2)):
            self.value = True if value else False
        elif is_text(value):
            self.value = xsi.boolean_from_str(value)
        else:
            self.value_error(value)


class DirectedPairValue(SingleValue):

    """Represents single values of type :py:class:`BaseType.directedPair`."""

    def __init__(self, value=None):
        super(DirectedPairValue, self).__init__()
        self.baseType = BaseType.directedPair
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return ' '.join(self.value)

    def set_value(self, value, name_check=False):
        """See :py:meth:`Identifier.SetValue` for usage of *name_check*.

        Note that if value is a string then name_check is ignored and
        identifier validation is always performed."""
        if value is None:
            self.value = None
        else:
            if is_text(value):
                value = value.split()
                name_check = True
            if isinstance(value, (list, tuple)):
                if len(value) != 2:
                    raise ValueError("%s expected 2 values: %s" % (
                        BaseType.to_str(self.baseType), repr(value)))
                for v in value:
                    if (not is_text(v) or
                            (name_check and not xmlns.is_valid_ncname(v))):
                        raise ValueError("Illegal identifier %s" % repr(v))
                self.value = (force_text(value[0]), force_text(value[1]))
            else:
                self.value_error(value)


class FileValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.file`."""

    def __init__(self):
        super(FileValue, self).__init__()
        self.baseType = BaseType.file
        self.contentType = params.MediaType.from_str(
            "application/octet-stream")
        """The content type of the file, a
        :py:class:`pyslet.http.params.MediaType` instance."""
        self.file_name = "data.bin"
        """The file name to use for the file."""

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            raise NotImplementedError("String serialization of BaseType.file.")

    def set_value(self, value, type="application/octet-stream",
                  name="data.bin"):
        """Sets a file value from a file like object or a string.

        There are some important and subtle distinctions in this method.

        If value is a Unicode text string then it is parsed according to the
        MIME-like format defined in the QTI specification.  The values of
        *type* and *name* are only used as defaults if those values cannot
        be read from the value's headers.

        If value is a plain string then it is assumed to represent the file's
        data directly, *type* and *name* are used to interpret the data.
        Other file type objects are set in the same way."""
        self.contentType = type
        self.file_name = name
        if value is None:
            self.value = None
        elif isinstance(value, file):
            self.value = value
        elif isinstance(value, bytes):
            self.value = BytesIO.BytesIO(value)
        elif isinstance(value, str):
            # Parse this value from the MIME stream.
            raise NotImplementedError(
                "String deserialization of BaseType.file.")
        else:
            self.value_error(value)


class FloatValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.float`."""

    def __init__(self, value=None):
        super(FloatValue, self).__init__()
        self.baseType = BaseType.float
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return xsi.double_to_str(self.value)

    def set_value(self, value):
        """This method will *not* convert integers to float values, you must do
        this explicitly if you want automatic conversion, for example
        ::

                # x is a numeric value that may be float or integer
                v=FloatValue()
                v.set_value(float(x))"""
        if value is None:
            self.value = None
        elif isinstance(value, float):
            self.value = value
        elif is_text(value):
            self.value = xsi.double_from_str(value)
        else:
            self.value_error(value)


class DurationValue(FloatValue):

    """Represents single value of type :py:class:`BaseType.duration`."""

    def __init__(self, value=None):
        super(DurationValue, self).__init__()
        self.baseType = BaseType.duration
        if value is not None:
            self.set_value(value)


class IdentifierValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.identifier`."""

    def __init__(self, value=None):
        super(IdentifierValue, self).__init__()
        self.baseType = BaseType.identifier
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return force_text(self.value)

    def set_value(self, value, name_check=True):
        """In general, to speed up computation we do not check the validity of
        identifiers unless parsing the value from a string representation (such
        as a value read from an XML input document).

        As values of baseType identifier are represented natively as strings we
        cannot tell if this method is being called with an existing,
        name-checked value or a new value being parsed from an external source.
        To speed up computation you can suppress the name check in the first
        case by setting *name_check* to False (the default is True)."""
        if value is None:
            self.value = None
        elif is_text(value):
            if not name_check or xmlns.is_valid_ncname(value):
                self.value = force_text(value)
            else:
                raise ValueError("Illegal identifier %s" % repr(value))
        else:
            self.value_error(value)


class IntegerValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.integer`."""

    def __init__(self, value=None):
        super(IntegerValue, self).__init__()
        self.baseType = BaseType.integer
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return xsi.integer_to_str(self.value)

    def set_value(self, value):
        """Note that integers and floats are distinct types in QTI: we do not
        accept floats where we would expect integers or *vice versa*.  However,
        integers are accepted from long or plain integer values provided they
        are within the ranges specified in the QTI specification:
        -2147483648...2147483647."""
        if value is None:
            self.value = None
        elif isinstance(value, (int, long2)):
            # python integers may be bigger than 32bits
            if value < -2147483648 or value > 2147483647:
                raise ValueError("Integer range: %s" % repr(value))
            else:
                self.value = int(value)
        elif is_text(value):
            self.value = xsi.integer_from_str(value)
        else:
            self.value_error(value)


class PairValue(DirectedPairValue):

    """Represents single values of type :py:class:`BaseType.pair`."""

    def __init__(self, value=None):
        super(PairValue, self).__init__()
        self.baseType = BaseType.pair
        if value is not None:
            self.set_value(value)

    def set_value(self, value, name_check=True):
        """Overrides DirectedPair's implementation to force a predictable
        ordering on the identifiers."""
        super(PairValue, self).set_value(value, name_check)
        if self.value and self.value[0] > self.value[1]:
            self.value = (self.value[1], self.value[0])


class PointValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.point`."""

    def __init__(self, value=None):
        super(PointValue, self).__init__()
        self.baseType = BaseType.point
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return ' '.join(map(xsi.integer_to_str, self.value))

    def set_value(self, value):
        if value is None:
            self.value = None
        else:
            if is_text(value):
                value = [xsi.integer_from_str(x) for x in value.split()]
            if isinstance(value, (list, tuple)):
                if len(value) != 2:
                    raise ValueError("%s expected 2 values: %s" % (
                        BaseType.to_str(self.baseType), repr(value)))
                for v in value:
                    if not isinstance(v, (int, long2)):
                        raise ValueError(
                            "Illegal type for point coordinate %s" %
                            repr(type(v)))
                    elif v < -2147483648 or v > 2147483647:
                        raise ValueError(
                            "Integer coordinate range: %s" % repr(v))
                self.value = (int(value[0]), int(value[1]))
            else:
                self.value_error(value)


class StringValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.string`."""

    def __init__(self, value=None):
        super(StringValue, self).__init__()
        self.baseType = BaseType.string
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return force_text(self.value)

    def set_value(self, value):
        if value is None:
            self.value = None
        elif is_text(value):
            self.value = force_text(value)
            if len(self.value) == 0:
                self.value = None
        else:
            self.value_error(value)


class URIValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.uri`."""

    def __init__(self, value=None):
        super(URIValue, self).__init__()
        self.baseType = BaseType.uri
        if value is not None:
            self.set_value(value)

    def __unicode__(self):
        if self.value is None:
            return uempty
        else:
            return force_text(self.value)

    def set_value(self, value):
        """Sets a uri value from a string or another URI instance."""
        if value is None:
            self.value = None
        elif is_text(value):
            self.value = URI.from_octets(value)
        elif isinstance(value, URI):
            self.value = value
        else:
            self.value_error(value)


class Container(Value):

    """An abstract class for all container types.

    By default containers are empty (and are treated as NULL values).  You can
    force the type of an empty container by passing a baseType constant to the
    constructor.  This will cause the container to generate TypeError if used
    in a context where the specified baseType is not allowed."""

    def __init__(self, base_type=None):
        super(Container, self).__init__()
        self.baseType = base_type

    def get_values(self):
        """Returns an iterable of the container's values."""
        return

    def __unicode__(self):
        """For single values we return a representation suitable for use as the
        content of a single XML element.  For containers this option is not
        open to us because they are always represented by multiple elements.

        We therefore opt for a minimal representation."""
        if self.baseType is None:
            return ul(
                "%s container of unknown base type") % Cardinality.to_str(
                    self.Cardinality)
        else:
            return ul("%s container of base type %s") % (
                Cardinality.to_str(self.Cardinality),
                BaseType.to_str(self.baseType))

    @classmethod
    def new_value(cls, cardinality, base_type=None):
        """Creates a new container with *cardinality* and *base_type*."""
        if cardinality == Cardinality.single:
            raise ValueError("Container with single cardinality")
        elif cardinality == Cardinality.ordered:
            return OrderedContainer(base_type)
        elif cardinality == Cardinality.multiple:
            return MultipleContainer(base_type)
        elif cardinality == Cardinality.record:
            return RecordContainer()
        else:
            return Container(base_type)


class OrderedContainer(Container):

    """Represents containers with ordered :py:class:`Cardinality`."""

    def cardinality(self):
        return Cardinality.ordered

    def set_value(self, value, base_type=None):
        """Sets the value of this container from a list, tuple or other
        iterable. The list must contain valid representations of *base_type*,
        items may be None indicating a NULL value in the list.  In accordance
        with the specification's multiple operator NULL values are ignored.

        If the input list of values empty, or contains only NULL values then
        the resulting container is empty.

        If *base_type* is None the base type specified when the container was
        constructed is assumed."""
        if base_type is not None:
            self.baseType = base_type
        if value is None:
            self.value = None
        else:
            # assume that value is iterable
            self.value = []
            for v in value:
                if v is None:
                    # ignore NULLs
                    continue
                if self.baseType is None:
                    # wild-card lists only work if they're empty!
                    raise ValueError(
                        "Can't create non-empty ordered container without a"
                        " base type")
                v_add = SingleValue.new_value(self.baseType, v)
                self.value.append(v_add.value)
            if not self.value:
                self.value = None

    def get_values(self):
        """Returns an iterable of values in the ordered container."""
        if self.value is None:
            return
        for v in self.value:
            yield v


class MultipleContainer(Container):

    """Represents containers with multiple :py:class:`Cardinality`."""

    def cardinality(self):
        return Cardinality.multiple

    def set_value(self, value, base_type=None):
        """Sets the value of this container from a list, tuple or other
        iterable. The list must contain valid representations of *base_type*,
        items may be None indicating a NULL value in the list.  In accordance
        with the specification's multiple operator NULL values are ignored.

        If the input list of values is empty, or contains only NULL values then
        the resulting container is empty.

        If *base_type* is None the base type specified when the container was
        constructed is assumed."""
        if base_type is not None:
            self.baseType = base_type
        if value is None:
            self.value = None
        else:
            self.value = {}
            for v in value:
                if v is None:
                    # ignore NULLs
                    continue
                if self.baseType is None:
                    # wild-card lists only work if they're empty!
                    raise ValueError(
                        "Can't create non-empty multiple container without a"
                        " base type")
                v_add = SingleValue.new_value(self.baseType, v)
                self.value[v_add.value] = self.value.get(v_add.value, 0) + 1
            if not self.value:
                self.value = None

    def get_values(self):
        """Returns an iterable of values in the ordered container."""
        if self.value is None:
            return
        keys = sorted(dict_keys(self.value))
        for k in keys:
            for i in range3(self.value[k]):
                yield k


class RecordContainer(Container):

    """Represents containers with record :py:class:`Cardinality`."""

    def __init__(self):
        super(Container, self).__init__()

    def cardinality(self):
        return Cardinality.record

    def set_value(self, value):
        """Sets the value of this container from an existing dictionary in which
        the keys are the field identifiers and the values are :py:class:`Value`
        instances. You cannot parse containers from strings.

        Records are always treated as having a wild-card base type.

        If the input *value* contains any keys which map to None or to a NULL
        value then these fields are omitted from the resulting value."""
        if value is None:
            self.value = None
        else:
            new_value = {}
            if isinstance(value, dict):
                field_list = list(dict_keys(value))
            else:
                raise ValueError(
                    "RecordContainer.SetValue expected dictionary, found %s" %
                    repr(value))
            for f in field_list:
                v = value[f]
                if v is None:
                    continue
                if not isinstance(v, SingleValue):
                    raise ValueError(
                        "Single value required, found %s" % repr(v))
                if not v:
                    # ignore NULL, no need to type check in records
                    continue
                new_value[f] = value[f]
            if new_value:
                self.value = new_value
            else:
                self.value = None

    def __len__(self):
        if self.value:
            return len(self.value)
        else:
            return 0

    def __getitem__(self, field_identifier):
        """Returns the :py:class:`Value` instance corresponding to
        *field_identifier* or raises KeyError if there is no field with that
        name."""
        if self.value:
            return self.value[field_identifier]
        else:
            raise KeyError(field_identifier)

    def __setitem__(self, field_identifier, value):
        """Sets the value in the named field to *value*.

        We add some special behaviour here.  If *value* is None or is a
        NULL value then we remove the field with the give name.  In
        other words::

            r=RecordContainer()
            r['pi']=FloatValue(3.14)
            r['pi']=FloatValue()    # a NULL value
            r['pi']                 # raises KeyError"""
        if value is None:
            if self.value and field_identifier in self.value:
                del self.value[field_identifier]
        elif isinstance(value, SingleValue):
            if not value:
                if self.value and field_identifier in self.value:
                    del self.value[field_identifier]
            else:
                if self.value is None:
                    self.value = {field_identifier: value}
                else:
                    self.value[field_identifier] = value
        else:
            raise ValueError("Single value required, found %s" % repr(value))

    def __delitem__(self, field_identifier):
        if self.value:
            del self.value[field_identifier]
        else:
            raise KeyError(field_identifier)

    def __iter__(self):
        if self.value:
            return iter(self.value)
        else:
            return iter([])

    def __contains__(self, field_identifier):
        if self.value:
            return field_identifier in self.value
        else:
            return False


class VariableDeclaration(core.QTIElement, SortableMixin):

    """Item variables are declared by variable declarations... The purpose of the
    declaration is to associate an identifier with the variable and to identify
    the runtime type of the variable's value::

        <xsd:attributeGroup name="variableDeclaration.AttrGroup">
            <xsd:attribute name="identifier" type="identifier.Type"
                use="required"/>
            <xsd:attribute name="cardinality" type="cardinality.Type"
                use="required"/>
            <xsd:attribute name="baseType" type="baseType.Type"
                use="optional"/>
        </xsd:attributeGroup>

        <xsd:group name="variableDeclaration.ContentGroup">
            <xsd:sequence>
                <xsd:element ref="defaultValue" minOccurs="0" maxOccurs="1"/>
            </xsd:sequence>
        </xsd:group>"""
    XMLATTR_baseType = (
        'baseType', BaseType.from_str_lower, BaseType.to_str)
    XMLATTR_cardinality = (
        'cardinality', Cardinality.from_str_lower, Cardinality.to_str)
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.identifier = ''
        self.cardinality = Cardinality.DEFAULT
        self.baseType = None
        self.DefaultValue = None

    def sortkey(self):
        return self.identifier

    def get_children(self):
        if self.DefaultValue:
            yield self.DefaultValue
        for child in core.QTIElement.get_children(self):
            yield child

    def content_changed(self):
        if self.parent:
            self.parent.RegisterDeclaration(self)

    def get_defined_value(self, defined_value):
        if defined_value:
            if self.cardinality == Cardinality.single:
                value = SingleValue.new_value(
                    self.baseType, defined_value.ValueElement[0].get_value())
            else:
                value = Value.new_value(self.cardinality, self.baseType)
                if isinstance(value, RecordContainer):
                    # handle record processing
                    for v in defined_value.ValueElement:
                        value[v.fieldIdentifier] = SingleValue.new_value(
                            v.baseType, v.get_value())
                else:
                    # handle multiple and ordered processing
                    value.set_value(
                        [v.get_value() for v in defined_value.ValueElement])
        else:
            # generate NULL values with the correct cardinality and base type
            if self.cardinality == Cardinality.single:
                value = SingleValue.new_value(self.baseType)
            else:
                value = Value.new_value(self.cardinality, self.baseType)
        return value

    @old_method('GetDefaultValue')
    def get_default_value(self):
        """Returns a :py:class:`Value` instance representing either the default
        value or an appropriately typed NULL value if there is no default
        defined."""
        return self.get_defined_value(self.DefaultValue)


class DefinedValue(core.QTIElement):

    """An abstract class used to implement the common behaviour of
    :py:class:`DefaultValue` and :py:class:`CorrectResponse` ::

            <xsd:attributeGroup name="defaultValue.AttrGroup">
                    <xsd:attribute name="interpretation" type="string.Type"
                                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="defaultValue.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="value" minOccurs="1"
                                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLATTR_interpretation = 'interpretation'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.interpretation = None
        self.ValueElement = []

    def get_children(self):
        return itertools.chain(
            self.ValueElement,
            core.QTIElement.get_children(self))


class DefaultValue(DefinedValue):

    """An optional default value for a variable. The point at which a variable
    is set to its default value varies depending on the type of item
    variable."""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'defaultValue')


class Mapping(core.QTIElement):

    """A special class used to create a mapping from a source set of any
    baseType (except file and duration) to a single float::

            <xsd:attributeGroup name="mapping.AttrGroup">
                    <xsd:attribute name="lowerBound" type="float.Type"
                                    use="optional"/>
                    <xsd:attribute name="upperBound" type="float.Type"
                                    use="optional"/>
                    <xsd:attribute name="defaultValue" type="float.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="mapping.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="mapEntry" minOccurs="1"
                                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'mapping')
    XMLATTR_lowerBound = ('lowerBound', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_upperBound = ('upperBound', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_defaultValue = (
        'defaultValue', xsi.float_from_str, xsi.float_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.lowerBound = None
        self.upperBound = None
        self.defaultValue = 0.0
        self.MapEntry = []
        self.baseType = BaseType.string
        self.map = {}

    def get_children(self):
        return iter(self.MapEntry)

    def content_changed(self):
        """Builds an internal dictionary of the values being mapped.

        In order to fully specify the mapping we need to know the baseType of
        the source values.  (The targets are always floats.)  We do this based
        on our parent, orphan Mapping elements are treated as mappings from
        source strings."""
        if isinstance(self.parent, ResponseDeclaration):
            self.baseType = self.parent.baseType
        # <categorizedStatistic>  not yet supported
        # elif isinstance(self.parent, CategorizedStatistic):
        #    self.baseType = BaseType.integer
        else:
            self.baseType = BaseType.string
        self.map = {}
        for me in self.MapEntry:
            v = SingleValue.new_value(self.baseType, me.mapKey)
            self.map[v.value] = me.mappedValue

    @old_method('MapValue')
    def map_value(self, value):
        """Maps an instance of :py:class:`Value` with the same base type as the
        mapping to an instance of :py:class:`Value` with base type float."""
        null_flag = False
        if not value:
            src_values = []
            null_flag = True
        elif value.cardinality() == Cardinality.single:
            src_values = [value.value]
        elif value.cardinality() == Cardinality.ordered:
            src_values = value.value
        elif value.cardinality() == Cardinality.multiple:
            src_values = list(dict_keys(value.value))
        else:
            raise ValueError("Can't map %s" % repr(value))
        result = 0.0
        been_there = {}
        dst_value = FloatValue(0.0)
        if value.baseType is None:
            # a value of unknown type results in NULL
            null_flag = True
        for v in src_values:
            if v in been_there:
                # If a container contains multiple instances of the same value
                # then that value is counted once only
                continue
            else:
                been_there[v] = True
            result = result + self.map.get(v, self.defaultValue)
        if null_flag:
            # We save the NULL return up to the end to ensure that we generate
            # errors in the case where a container contains mixed or
            # mismatching values.
            return dst_value
        else:
            if self.lowerBound is not None and result < self.lowerBound:
                result = self.lowerBound
            elif self.upperBound is not None and result > self.upperBound:
                result = self.upperBound
            dst_value.set_value(result)
            return dst_value


class MapEntry(core.QTIElement):

    """An entry in a :py:class:`Mapping`
    ::

            <xsd:attributeGroup name="mapEntry.AttrGroup">
                    <xsd:attribute name="mapKey" type="valueType.Type"
                                    use="required"/>
                    <xsd:attribute name="mappedValue" type="float.Type"
                                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'mapEntry')
    XMLATTR_mapKey = 'mapKey'
    XMLATTR_mappedValue = ('mappedValue', xsi.float_from_str, xsi.float_to_str)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.mapKey = None			#: The source value
        self.mappedValue = 0.0		#: The mapped value


class ResponseDeclaration(VariableDeclaration):

    """Response variables are declared by response declarations and bound to
    interactions in the itemBody::

            <xsd:group name="responseDeclaration.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="variableDeclaration.ContentGroup"/>
                            <xsd:element ref="correctResponse" minOccurs="0"
                                            maxOccurs="1"/>
                            <xsd:element ref="mapping" minOccurs="0"
                                            maxOccurs="1"/>
                            <xsd:element ref="areaMapping" minOccurs="0"
                                            maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseDeclaration')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        VariableDeclaration.__init__(self, parent)
        self.CorrectResponse = None
        self.Mapping = None
        self.AreaMapping = None

    def get_children(self):
        for child in VariableDeclaration.get_children(self):
            yield child
        if self.CorrectResponse:
            yield self.CorrectResponse
        if self.Mapping:
            yield self.Mapping
        if self.AreaMapping:
            yield self.AreaMapping

    def get_correct_value(self):
        """Returns a :py:class:`Value` instance representing either the correct
        response value or an appropriately typed NULL value if there is no
        correct value."""
        return self.get_defined_value(self.CorrectResponse)

    def get_stage_dimensions(self):
        """For response variables with point type, returns a pair of integer
        values: width,height

        In HTML, shapes (including those used in the AreaMapping) can use
        relative coordinates. To interpret relative coordinates we need to know
        the size of the stage used to interpret the point values.  For a
        response variable that is typically the size of the image or object
        used in the interaction.

        This method searches for the interaction associated with the response
        and obtains the width and height of the corresponding object.

        [TODO: currently returns 100,100]"""
        return 100, 100


class CorrectResponse(DefinedValue):

    """A response declaration may assign an optional correctResponse. This value
    may indicate the only possible value of the response variable to be
    considered correct or merely just a correct value."""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'correctResponse')


class AreaMapping(core.QTIElement):

    """A special class used to create a mapping from a source set of point
    values to a target set of float values::

            <xsd:attributeGroup name="areaMapping.AttrGroup">
                    <xsd:attribute name="lowerBound" type="float.Type"
                                    use="optional"/>
                    <xsd:attribute name="upperBound" type="float.Type"
                                    use="optional"/>
                    <xsd:attribute name="defaultValue" type="float.Type"
                                    use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="areaMapping.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="areaMapEntry" minOccurs="1"
                                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'areaMapping')
    XMLATTR_lowerBound = ('lowerBound', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_upperBound = ('upperBound', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_defaultValue = (
        'defaultValue', xsi.float_from_str, xsi.float_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.lowerBound = None
        self.upperBound = None
        self.defaultValue = 0.0
        self.AreaMapEntry = []

    def get_children(self):
        return iter(self.AreaMapEntry)

    @old_method('MapValue')
    def map_value(self, value, width, height):
        """Maps a point onto a float.

        Returns an instance of :py:class:`Value` with base type float.

        *	value is a :py:class:`Value` of base type point

        *   width is the integer width of the object on which the area
            is defined

        *   height is the integer height of the object on which the
            area is defined

        The width and height of the object are required because HTML allows
        relative values to be used when defining areas."""
        null_flag = False
        if not value:
            src_values = []
            null_flag = True
        elif value.cardinality() == Cardinality.single:
            src_values = [value.value]
        elif value.cardinality() == Cardinality.ordered:
            src_values = value.value
        elif value.cardinality() == Cardinality.multiple:
            src_values = list(dict_keys(value.value))
        else:
            raise ValueError("Can't map %s" % repr(value))
        result = 0.0
        been_there = [False] * len(self.AreaMapEntry)
        dst_value = FloatValue(0.0)
        if value.baseType is None:
            # a value of unknown type results in NULL
            null_flag = True
        elif value.baseType != BaseType.point:
            raise ValueError("Can't map %s" % repr(value))
        for v in src_values:
            hit_point = False
            for i in range3(len(self.AreaMapEntry)):
                if self.AreaMapEntry[i].TestPoint(v, width, height):
                    hit_point = True
                    if not been_there[i]:
                        # When mapping containers each area can be mapped once
                        # only
                        been_there[i] = True
                        result = result + self.AreaMapEntry[i].mappedValue
                    break
            if not hit_point:
                # This point is not in any of the areas
                result = result + self.defaultValue
        if null_flag:
            # We save the NULL return up to the end to ensure that we generate
            # errors in the case where a container contains mixed or
            # mismatching values.
            return dst_value
        else:
            if self.lowerBound is not None and result < self.lowerBound:
                result = self.lowerBound
            elif self.upperBound is not None and result > self.upperBound:
                result = self.upperBound
            dst_value.set_value(result)
            return dst_value


class AreaMapEntry(core.QTIElement, core.ShapeElementMixin):

    """An :py:class:`AreaMapping` is defined by a set of areaMapEntries, each of
    which maps an area of the coordinate space onto a single float::

            <xsd:attributeGroup name="areaMapEntry.AttrGroup">
                    <xsd:attribute name="shape" type="shape.Type"
                                    use="required"/>
                    <xsd:attribute name="coords" type="coords.Type"
                                    use="required"/>
                    <xsd:attribute name="mappedValue" type="float.Type"
                                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'areaMapEntry')
    XMLATTR_mappedValue = ('mappedValue', xsi.float_from_str, xsi.float_to_str)
    XMLCONTENT = xml.ElementType.Empty

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        core.ShapeElementMixin.__init__(self)
        self.mappedValue = 0.0			#: The mapped value


class OutcomeDeclaration(VariableDeclaration):

    """Outcome variables are declared by outcome declarations
    ::

            <xsd:attributeGroup name="outcomeDeclaration.AttrGroup">
                    <xsd:attributeGroup ref="variableDeclaration.AttrGroup"/>
                    <xsd:attribute name="view" use="optional">
                            <xsd:simpleType>
                                    <xsd:list itemType="view.Type"/>
                            </xsd:simpleType>
                    </xsd:attribute>
                    <xsd:attribute name="interpretation" type="string.Type"
                                    use="optional"/>
                    <xsd:attribute name="longInterpretation" type="uri.Type"
                                    use="optional"/>
                    <xsd:attribute name="normalMaximum" type="float.Type"
                                    use="optional"/>
                    <xsd:attribute name="normalMinimum" type="float.Type"
                                    use="optional"/>
                    <xsd:attribute name="masteryValue" type="float.Type"
                                    use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="outcomeDeclaration.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="variableDeclaration.ContentGroup"/>
                            <xsd:group ref="lookupTable.ElementGroup"
                                        minOccurs="0" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'outcomeDeclaration')
    XMLATTR_view = ('view', core.View.from_str_lower, core.View.to_str, dict)
    XMLATTR_interpretation = 'interpretation'
    XMLATTR_longInterpretation = (
        'longInterpretation', html.uri.URI.from_octets, html.to_text)
    XMLATTR_normalMaximum = (
        'normalMaximum', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_normalMinimum = (
        'normalMinimum', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_masteryValue = (
        'masteryValue', xsi.float_from_str, xsi.float_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        VariableDeclaration.__init__(self, parent)
        self.view = None
        self.interpretation = None
        self.longInterpretation = None
        self.normalMaximum = None
        self.normalMinimum = None
        self.masteryValue = None
        self.LookupTable = None

    def get_children(self):
        for child in VariableDeclaration.get_children(self):
            yield child
        if self.LookupTable:
            yield self.LookupTable


class LookupTable(core.QTIElement):

    """An abstract class associated with an outcomeDeclaration used to create a
    lookup table from a numeric source value to a single outcome value in the
    declared value set::

            <xsd:attributeGroup name="lookupTable.AttrGroup">
                    <xsd:attribute name="defaultValue" type="valueType.Type"
                                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_defaultValue = 'defaultValue'
    XMLATTR_interpretation = 'interpretation'
    XMLATTR_longInterpretation = (
        'longInterpretation', html.uri.URI.from_octets, html.to_text)
    XMLATTR_normalMaximum = (
        'normalMaximum', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_normalMinimum = (
        'normalMinimum', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_masteryValue = (
        'masteryValue', xsi.float_from_str, xsi.float_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        # : a string from which the default is parsed when its base type is
        # known
        self.defaultValue = None
        self.baseType = BaseType.string
        #: a :py:class:`Value` instance representing the default
        self.default = None

    def content_changed(self):
        if isinstance(self.parent, OutcomeDeclaration):
            self.baseType = self.parent.baseType
        else:
            self.baseType = BaseType.string
        self.default = SingleValue.new_value(self.baseType, self.defaultValue)


class MatchTable(LookupTable):

    """A matchTable transforms a source integer by finding the first
    matchTableEntry with an exact match to the source::

            <xsd:group name="matchTable.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="matchTableEntry" minOccurs="1"
                                            maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'matchTable')

    def __init__(self, parent):
        LookupTable.__init__(self, parent)
        self.MatchTableEntry = []
        self.map = {}

    def get_children(self):
        return iter(self.MatchTableEntry)

    def content_changed(self):
        """Builds an internal dictionary of the values being mapped."""
        LookupTable.content_changed(self)
        self.map = {}
        for mte in self.MatchTableEntry:
            v = SingleValue.new_value(self.baseType, mte.targetValue)
            self.map[mte.sourceValue] = v.value

    def lookup(self, value):
        """Maps an instance of :py:class:`Value` with integer base type to an
        instance of :py:class:`Value` with the base type of the match table."""
        null_flag = False
        if not value:
            null_flag = True
            src_value = None
        elif value.cardinality() != Cardinality.single:
            raise ValueError("Can't match container: %s" % repr(value))
        elif value.baseType != BaseType.integer:
            raise ValueError(
                "MatchTable requires integer, found %s" %
                BaseType.to_str(
                    value.baseType))
        else:
            src_value = value.value
        dst_value = SingleValue.new_value(self.baseType)
        if not null_flag:
            dst_value.set_value(self.map.get(src_value, self.default.value))
        return dst_value


class MatchTableEntry(core.QTIElement):

    """sourceValue
            The source integer that must be matched exactly.

    targetValue
            The target value that is used to set the outcome when a match is
            found

    ::

            <xsd:attributeGroup name="matchTableEntry.AttrGroup">
                    <xsd:attribute name="sourceValue" type="integer.Type"
                                    use="required"/>
                    <xsd:attribute name="targetValue" type="valueType.Type"
                                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'matchTableEntry')
    XMLATTR_sourceValue = (
        'sourceValue', xsi.integer_from_str, xsi.integer_to_str)
    XMLATTR_targetValue = 'targetValue'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.sourceValue = None
        self.targetValue = None


class InterpolationTable(LookupTable):

    """An interpolationTable transforms a source float (or integer) by finding
    the first interpolationTableEntry with a sourceValue that is less than or
    equal to (subject to includeBoundary) the source value::

            <xsd:group name="interpolationTable.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="interpolationTableEntry"
                                        minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'interpolationTable')

    def __init__(self, parent):
        LookupTable.__init__(self, parent)
        self.InterpolationTableEntry = []
        self.table = []

    def get_children(self):
        return iter(self.InterpolationTableEntry)

    def content_changed(self):
        """Builds an internal table of the values being mapped."""
        LookupTable.content_changed(self)
        self.table = []
        for ite in self.InterpolationTableEntry:
            v = SingleValue.new_value(self.baseType, ite.targetValue)
            self.table.append((ite.sourceValue, ite.includeBoundary, v.value))

    def lookup(self, value):
        """Maps an instance of :py:class:`Value` with integer or float base type
        to an instance of :py:class:`Value` with the base type of the
        interpolation table."""
        null_flag = False
        if not value:
            null_flag = True
            src_value = None
        elif value.cardinality() != Cardinality.single:
            raise ValueError("Can't match container: %s" % repr(value))
        elif value.baseType == BaseType.integer:
            src_value = float(value.value)
        elif value.baseType in (BaseType.float, BaseType.duration):
            src_value = value.value
        else:
            raise ValueError(
                "Interpolation table requires integer or float, found %s" %
                BaseType.to_str(
                    value.baseType))
        dst_value = SingleValue.new_value(self.baseType)
        if not null_flag:
            dst_value.set_value(self.default.value)
            for testValue, lte, targetValue in self.table:
                if testValue < src_value or (lte and testValue == src_value):
                    dst_value.set_value(targetValue)
                    break
        return dst_value


class InterpolationTableEntry(core.QTIElement):

    """sourceValue
            The lower bound for the source value to match this entry.

    includeBoundary
            Determines if an exact match of sourceValue matches this entry. If
            true, the default, then an exact match of the value is considered a
            match of this entry.

    targetValue
            The target value that is used to set the outcome when a match is
            found

    ::

            <xsd:attributeGroup name="interpolationTableEntry.AttrGroup">
                    <xsd:attribute name="sourceValue" type="float.Type"
                                    use="required"/>
                    <xsd:attribute name="includeBoundary" type="boolean.Type"
                                    use="optional"/>
                    <xsd:attribute name="targetValue" type="valueType.Type"
                                    use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'interpolationTableEntry')
    XMLATTR_sourceValue = ('sourceValue', xsi.float_from_str, xsi.float_to_str)
    XMLATTR_includeBoundary = (
        'includeBoundary', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_targetValue = 'targetValue'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.sourceValue = None
        self.includeBoundary = True
        self.targetValue = None


class TemplateDeclaration(VariableDeclaration):

    """Template declarations declare item variables that are to be used
    specifically for the purposes of cloning items
    ::

            <xsd:attributeGroup name="templateDeclaration.AttrGroup">
                    <xsd:attributeGroup ref="variableDeclaration.AttrGroup"/>
                    <xsd:attribute name="paramVariable" type="boolean.Type"
                                    use="optional"/>
                    <xsd:attribute name="mathVariable" type="boolean.Type"
                                    use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateDeclaration')
    XMLATTR_paramVariable = (
        'paramVariable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLATTR_mathVariable = (
        'mathVariable', xsi.boolean_from_str, xsi.boolean_to_str)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        VariableDeclaration.__init__(self, parent)
        self.paramVariable = None
        self.mathVariable = None


class SessionState(MigratedClass):

    """Abstract class used as the base class for namespace-like objects used to
    track the state of an item or test session.  Instances can be used as if
    they were dictionaries of :py:class:`Value`."""

    @old_method('GetDeclaration')
    def get_declaration(self, var_name):
        """Returns the declaration associated with *var_name* or None if the
        variable is one of the built-in variables.  If *var_name* is not a
        variable KeyError is raised.  To test for the existence of a variable
        just use the object as you would a dictionary::

                # state is a SessionState instance
                if 'RESPONSE' in state:
                    print("RESPONSE declared!") """
        raise KeyError(var_name)

    @old_method('IsResponse')
    def is_response(self, var_name):
        """Return True if *var_name* is the name of a response variable."""
        d = self.get_declaration(var_name)
        return isinstance(d, ResponseDeclaration)

    @old_method('IsOutcome')
    def is_outcome(self, var_name):
        """Return True if *var_name* is the name of an outcome variable."""
        d = self.get_declaration(var_name)
        return isinstance(d, OutcomeDeclaration)

    def set_outcome_defaults(self):
        raise NotImplementedError

    @old_method('IsTemplate')
    def is_template(self, var_name):
        """Return True if *var_name* is the name of a template variable."""
        d = self.get_declaration(var_name)
        return isinstance(d, TemplateDeclaration)

    def __len__(self):
        return 0

    def __getitem__(self, var_name):
        """Returns the :py:class:`Value` instance corresponding to *var_name* or
        raises KeyError if there is no variable with that name."""
        raise KeyError(var_name)

    def __setitem__(self, var_name, value):
        """Sets the value of *var_name* to the :py:class:`Value` instance *value*.

        The *baseType* and cardinality of *value* must match those expected for
        the variable.

        This method does not actually update the dictionary with the *value*
        instance but instead, it copies the value of *value* into the
        :py:class:`Value` instance already stored in the session.  The
        side-effect of this implementation is that a previous look-up will be
        updated by a subsequent assignment::

                # state is a SessionState instance
                state['RESPONSE']=IdentifierValue('Hello')
                r1=state['RESPONSE']
                state['RESPONSE']=IdentifierValue('Bye')
                r2=state['RESPONSE']
                r1==r2		# WARNING: r1 has been updated so still evaluates to
                                        True!"""
        if not isinstance(value, Value):
            raise TypeError
        v = self[var_name]
        if (value.cardinality() is not None and
                value.cardinality() != v.cardinality()):
            raise ValueError(
                "Expected %s value, found %s" %
                (Cardinality.to_str(
                    v.cardinality()), Cardinality.to_str(
                    value.cardinality())))
        if value.baseType is not None and value.baseType != v.baseType:
            raise ValueError(
                "Expected %s value, found %s" %
                (BaseType.to_str(
                    v.baseType), BaseType.to_str(
                    value.baseType)))
        v.set_value(value.value)

    def __delitem__(self, var_name):
        raise TypeError("Can't delete variables from SessionState")

    def __iter__(self):
        raise NotImplementedError

    def __contains__(self, var_name):
        raise KeyError(var_name)


class ItemSessionState(SessionState):

    """Represents the state of an item session.  *item* is the item from which
    the session should be created.

    On construction, all declared variables (included built-in variables) are
    added to the session with NULL values, except the template variables which
    are set to their defaults.

    In addition to the variables defined by the specification we add meta
    variables corresponding to response and outcome defaults, these have the
    same name as the variable but with ".DEFAULT" appended.  Similarly, we
    define names for the correct values of response variables using ".CORRECT".
    The values of these meta-variables are all initialised from the item
    definition on construction."""

    def __init__(self, item):
        super(ItemSessionState, self).__init__()
        # : the required prefix for HTML form variable names
        self.formPrefix = ""
        self.item = item
        self.map = {}
        for td in self.item.TemplateDeclaration:
            self.map[td.identifier] = td.get_default_value()
        # add the default response variables
        self.map['numAttempts'] = IntegerValue()
        self.map['duration'] = DurationValue()
        self.map['completionStatus'] = IdentifierValue()
        # now loop through the declared variables...
        for rd in self.item.ResponseDeclaration:
            self.map[rd.identifier + ".CORRECT"] = rd.get_correct_value()
            self.map[rd.identifier + ".DEFAULT"] = rd.get_default_value()
            # Response variables do not get their default... yet!
            self.map[rd.identifier] = Value.new_value(
                rd.cardinality, rd.baseType)
        # outcomes do not get their default yet either
        for od in self.item.OutcomeDeclaration:
            self.map[od.identifier + ".DEFAULT"] = od.get_default_value()
            self.map[od.identifier] = Value.new_value(
                od.cardinality, od.baseType)

    def select_clone(self):
        """Item templates describe a range of possible items referred to as
        *clones*.

        If the item used to create the session object is an item
        template then you must call select_clone before beginning the
        candidate's session with :py:meth:`begin_session`.

        The main purpose of this method is to run the template processing
        rules. These rules update the values of the template variables and may
        also alter correct responses and default outcome (or response)
        values."""
        if self.item.TemplateProcessing:
            self.item.TemplateProcessing.Run(self)

    def begin_session(self):
        """Called at the start of an item session. According to the specification:

                "The session starts when the associated item first becomes
                eligible for delivery to the candidate"

        The main purpose of this method is to set the outcome values to their
        defaults."""
        # sets the default values of all outcome variables
        self.map['completionStatus'].value = ul('not_attempted')
        self.set_outcome_defaults()
        # The spec says that numAttempts is a response that has value 0
        # initially. That suggests that it behaves more like an outcome in this
        # respect so we initialise the value here.
        self.map['numAttempts'].value = 0
        # similar consideration applies to the built-in duration
        self.map['duration'].value = 0.0
        # the rest of the response variables are initialised when the first
        # attempt starts

    def begin_attempt(self, html_parent=None):
        """Called at the start of an attempt.

        This method sets the default RESPONSE values and completionStatus if
        this is the first attempt and increments numAttempts accordingly."""
        num_attempts = self.map['numAttempts']
        num_attempts.set_value(num_attempts.value + 1)
        if num_attempts.value == 1:
            # first attempt, set default responses
            for rd in self.item.ResponseDeclaration:
                self.map[rd.identifier] = Value.copy_value(
                    self.map[rd.identifier + ".DEFAULT"])
            # and set completionStatus
            self.map['completionStatus'] = IdentifierValue('unknown')
        return self.item.render_html(self, html_parent)

    def save_session(self, params, html_parent=None):
        """Called when we wish to save unsubmitted values."""
        self._save_parameters(params)
        return self.item.render_html(self, html_parent)

    def submit_session(self, params, html_parent=None):
        """Called when we wish to submit values (i.e., end an attempt)."""
        self._save_parameters(params)
        # Now we go through all response variables and update their value from
        # the saved value, removing the saved values as we go.
        for rd in self.item.ResponseDeclaration:
            sname = rd.identifier + ".SAVED"
            if sname in self.map:
                self.map[rd.identifier].set_value(self.map[sname].value)
                del self.map[sname]
        self.end_attempt()
        return self.item.render_html(self, html_parent)

    def _save_parameters(self, params):
        ordered_params = {}
        for p in params:
            if self.formPrefix and not p.startswith(self.formPrefix):
                # ignore values not intended for us
                continue
            rname = p[len(self.formPrefix):].split(".")
            if not rname:
                continue
            # rname must be the name of a response variable
            rd = self.get_declaration(rname[0])
            if rd is None or not isinstance(rd, ResponseDeclaration):
                # unexpected item in bagging area!
                raise BadSessionParams(
                    "Unexpected item submitted wth form: %s" % p)
            # so we have a new response value to save
            save_name = rname[0] + ".SAVED"
            if save_name not in self:
                self.map[save_name] = v = Value.new_value(
                    rd.cardinality, rd.baseType)
            else:
                v = self.map[save_name]
            # now we need to parse a value from the form to save
            svalue = params[p]
            if rd.cardinality == Cardinality.single:
                # We are expecting a single value from the form
                if is_text(svalue):
                    v.set_value(svalue)
                else:
                    raise BadSessionParams(
                        "Unexpected multi-value submission: %s" % p)
            elif rd.cardinality == Cardinality.multiple:
                # we are expecting a simple list of values
                if is_text(svalue):
                    # single item list
                    v.set_value([svalue])
                else:
                    v.set_value(svalue)
            elif rd.cardinality == Cardinality.ordered:
                # there are two ways of setting these values, either
                # RESPONSE.rank=VALUE or RESPONSE.VALUE=rank.  The latter
                # representation is only valid for identifiers, to ensure we
                # don't mix them up with ranks.
                if len(rname) != 2:
                    continue
                try:
                    if (rd.baseType == BaseType.Identifier and
                            core.ValidateIdentifier(rname[1])):
                        if is_text(svalue):
                            v.set_value(svalue)
                        else:
                            raise ValueError
                        rank = xsi.integer_from_str(svalue)
                        svalue = rname[1]
                    else:
                        rank = xsi.integer_from_str(rname[1])
                    if save_name in ordered_params:
                        if rank in ordered_params[save_name]:
                            # duplicate entries, we don't allow these
                            raise ValueError
                        ordered_params[save_name][rank] = svalue
                    else:
                        ordered_params[save_name] = {rank: svalue}
                except ValueError:
                    raise BadSessionParams(
                        "Bad value in submission for: %s" % p)
            else:
                raise NotImplementedError
        if ordered_params:
            # we've gathered ordered parameters in a dictionary of dictionaries
            # keyed first on response identifier and then on rank.  For each
            # response we just sort them, so missing ranks are OK.
            for response in ordered_params:
                rparams = ordered_params[response]
                ranks = sorted(rparams.keys())
                svalue = []
                for r in ranks:
                    svalue.append(rparams[r])
                save_name = response + ".SAVED"
                v = self.map[save_name]
                v.set_value(svalue)

    def end_attempt(self):
        """Called at the end of an attempt.  Invokes response processing if
        present."""
        if not self.item.adaptive:
            # For a Non-adaptive Item the values of the outcome variables are
            # reset to their default values (or NULL if no default is given)
            # before each invocation of response processing
            self.set_outcome_defaults()
        if self.item.ResponseProcessing:
            self.item.ResponseProcessing.Run(self)

    def get_declaration(self, var_name):
        if var_name in self.map:
            return self.item.get_declaration(var_name)
        else:
            raise KeyError(var_name)

    def is_response(self, var_name):
        """Return True if *var_name* is the name of a response variable.

        We add handling of the built-in response variables numAttempts and
        duration."""
        d = self.get_declaration(var_name)
        if d is None:
            return var_name in ('numAttempts', 'duration')
        else:
            return isinstance(d, ResponseDeclaration)

    def is_outcome(self, var_name):
        """Return True if *var_name* is the name of an outcome variable.

        We add handling of the built-in outcome variable completionStatus."""
        d = self.get_declaration(var_name)
        if d is None:
            return var_name == 'completionStatus'
        else:
            return isinstance(d, OutcomeDeclaration)

    def set_outcome_defaults(self):
        for od in self.item.OutcomeDeclaration:
            self.map[od.identifier] = v = Value.copy_value(
                self.map[od.identifier + ".DEFAULT"])
            if not v:
                if v.cardinality() == Cardinality.single:
                    if v.baseType == BaseType.integer:
                        v.set_value(0)
                    elif v.baseType == BaseType.float:
                        v.set_value(0.0)

    def __len__(self):
        return len(self.map)

    def __getitem__(self, var_name):
        return self.map[var_name]

    def __iter__(self):
        return iter(self.map)

    def __contains__(self, var_name):
        return var_name in self.map


class TestSessionState(SessionState):

    """Represents the state of a test session.  The keys are the names of the
    variables *including* qualified names that can be used to look up the value
    of variables from the associated item session states.  *form* is the test
    form from which the session should be created.

    On construction, all declared variables (included built-in variables) are
    added to the session with NULL values."""

    def __init__(self, form):
        super(TestSessionState, self).__init__()
        # : the :py:class:`tests.TestForm` used to initialise this session
        self.form = form
        #: the :py:class:`tests.AssessmentTest` that this session is an
        # instance of
        self.test = form.test
        self.namespace = len(form) * [None]
        self.namespace[0] = {}
        # add the default response variables
        self.namespace[0]['duration'] = DurationValue()
        # now loop through all test parts and (visible) sections to define
        # other durations
        for i in range3(1, len(self.namespace)):
            p = form[i]
            if p[0] == "-":
                continue
            part = self.test.GetPart(p)
            if isinstance(part, (tests.AssessmentSection, tests.TestPart)):
                self.namespace[i] = {'duration': DurationValue()}
            elif isinstance(part, tests.AssessmentItemRef):
                item = part.GetItem()
                self.namespace[i] = ItemSessionState(item)
                self.namespace[i].formPrefix = p + "."
        # now loop through the declared variables, outcomes do not get their
        # default yet
        for od in self.test.OutcomeDeclaration:
            self.namespace[0][od.identifier] = Value.new_value(
                od.cardinality, od.baseType)
        self.t = None			#: the time of the last event
        try:
            #: a random string of bytes used to add entropy to the session key
            self.salt = os.urandom(8)
        except NotImplementedError:
            self.salt = []
            for i in range3(8):
                self.salt.append(byte(random.randint(0, 255)))
            self.salt = join_bytes(self.salt)
        self.key = ''
        """A key representing this session in its current state, this key is
        initialised to a random value and changes as each event is received.
        The key must be supplied when triggering subsequent events.  The key is
        designed to be unguessable and unique so a caller presenting the
        correct key when triggering an event can be securely assumed to be the
        owner of the existing session."""
        self.prevKey = ''
        """The key representing the previous state.  This can be used to follow
        session state transitions back through a chain of states back to the
        beginning of the session (i.e., for auditing)."""
        self.keyMap = {}
        """A mapping of keys previously used by this session.  A caller
        presenting an expired key when triggering an event generates a
        :py:class:`SessionKeyExpired` exception. This condition might indicate
        that a session response was not received (e.g., due to a connection
        failure) and that the session should be re-started with the previous
        response."""
        self.event_update(self.key)
        self.cQuestion = 0

    def event_update(self, key_check):
        if self.key != key_check:
            if key_check in self.keyMap:
                raise SessionKeyExpired(key_check)
            else:
                raise SessionKeyMismatch(key_check)
        if self.key:
            self.keyMap[self.key] = True
            self.prevKey = self.key
            dt = self.t
            self.t = time.time()
            dt = self.t - dt
            if dt == 0.0:
                # add a small time anyway
                dt = 0.000001
                self.t = self.t + dt
        else:
            self.t = time.time()
            dt = 0.0
        hash = hashlib.sha224()
        hash.update(self.salt + ("%.6f" % self.t).encode('ascii'))
        self.key = force_text(hash.hexdigest())
        return dt

    def get_current_test_part(self):
        """Returns the current test part or None if the test is finished."""
        q = self.get_current_question()
        if q is None:
            return None
        else:
            return q.find_parent(tests.TestPart)

    def get_current_question(self):
        """Returns the current question or None if the test is finished."""
        if self.cQuestion is None:
            return None
        else:
            return self.test.GetPart(self.form[self.cQuestion])

    def _branch_target(self, qpos):
        id = self.form[qpos]
        if id[0] == "-":
            id = id[1:]
        q = self.test.GetPart(id)
        target = q.get_branch_target(self)
        if target is None:
            return qpos + 1
        elif target == "EXIT_TEST":
            return len(self.form)
        else:
            qpos = qpos + 1
            while True:
                if qpos >= len(self.form):
                    return qpos
                id = self.form[qpos]
                if target == id:
                    return qpos
                qpos = qpos + 1
                # handle the other special identifiers which move to the point
                # just after the end of the part being exited
                if id[0] == "-":
                    if target == "EXIT_SECTION":
                        return qpos
                    elif (target == "EXIT_TESTPART" and
                          isinstance(self.test.GetPart(id[1:]),
                                     tests.TestPart)):
                        return qpos

    def _next_question(self):
        if self.cQuestion is None:
            # we've finished
            return
        elif self.cQuestion is 0:
            # We need to find the first question
            iq = 1
        else:
            # we're currently pointing at an assessmentItemRef
            iq = self._branch_target(self.cQuestion)
        while iq is not None:
            # What type of thing is iq?
            if iq >= len(self.form):
                # we've run out of stuff, that was the end of the test.
                self.cQuestion = None
                break
            # check for preConditions
            id = self.form[iq]
            if id[0] == "-":
                # end of a section or test part
                iq = self._branch_target(iq)
            else:
                # check preconditions
                part = self.test.GetPart(id)
                if part.check_pre_conditions(self):
                    if isinstance(part, tests.TestPart):
                        # descend in to this testPart
                        iq = iq + 1
                        if (part.navigationMode ==
                                tests.NavigationMode.nonlinear):
                            # evaluate templateDefaults for all items in this
                            # part
                            end_id = "-" + part.identifier
                            jq = iq
                            while jq <= len(self.form):
                                id = self.form[jq]
                                if id == end_id:
                                    break
                                if id[0] != "-":
                                    jpart = self.test.GetPart(id)
                                    if isinstance(jpart,
                                                  tests.AssessmentItemRef):
                                        # Now evaluate the template defaults
                                        item_state = self.namespace[jq]
                                        jpart.SetTemplateDefaults(
                                            item_state, self)
                                        # and pick a clone
                                        item_state.select_clone()
                                        item_state.begin_session()
                                jq = jq + 1
                    elif isinstance(part, tests.AssessmentSection):
                        # descend in to this section
                        iq = iq + 1
                    elif isinstance(part, tests.AssessmentItemRef):
                        # we've found the next question
                        test_part = part.find_parent(tests.TestPart)
                        if (test_part.navigationMode ==
                                tests.NavigationMode.linear):
                            item_state = self.namespace[iq]
                            part.SetTemplateDefaults(item_state, self)
                            item_state.select_clone()
                            item_state.begin_session()
                        self.cQuestion = iq
                        break
                else:
                    # skip this item
                    iq = iq + 1

    def begin_session(self, key, html_parent=None):
        """Called at the start of a test session.  Represents a 'Start Test' event.

        The main purpose of this method is to set the outcome values to their
        defaults and to select the first question."""
        # ignore any time elapsed between construction and beginSession
        self.event_update(key)
        # sets the default values of all outcome variables
        self.set_outcome_defaults()
        self.namespace[0]['duration'].value = 0.0
        self._next_question()
        div, form = self.create_html_form(html_parent)
        if self.cQuestion:
            self.form[self.cQuestion]
            item_state = self.namespace[self.cQuestion]
            item_state.begin_attempt(form)
        else:
            # this test had no questions: end screen
            pass
        self.add_html_navigation(form)
        return div

    def handle_event(self, params, html_parent=None):
        # seek out the action
        if "SAVE" in params:
            return self.save_session(params["SAVE"], params, html_parent)
        elif "SUBMIT" in params:
            return self.submit_session(params["SUBMIT"], params, html_parent)
        else:
            raise SessionActionMissing

    def save_session(self, key, params, html_parent=None):
        dt = self.event_update(key)
        # Now add the accumulated time to the various durations
        self.add_duration(dt)
        div, form = self.create_html_form(html_parent)
        # Now go through params and look for updated values
        if self.cQuestion:
            item_state = self.namespace[self.cQuestion]
            item_state.save_session(params, form)
        else:
            pass
        self.add_html_navigation(form)
        return div

    def submit_session(self, key, params, html_parent=None):
        dt = self.event_update(key)
        # Now add the accumulated time to the various durations
        self.add_duration(dt)
        div, form = self.create_html_form(html_parent)
        # Now go through params and look for updated values
        if self.cQuestion:
            id = self.form[self.cQuestion]
            part = self.test.GetPart(id)
            test_part = part.find_parent(tests.TestPart)
            # so what type of testPart are we in?
            if test_part.navigationMode == tests.NavigationMode.linear:
                if test_part.submissionMode == tests.SubmissionMode.individual:
                    item_state = self.namespace[self.cQuestion]
                    item_state.submit_session(params)
                else:
                    # simultaneous submission means we save the current values
                    # then run through all questions in this part submitting
                    # the saved values - it still happens at the end of the
                    # test part
                    item_state = self.namespace[self.cQuestion]
                    item_state.save_session(params)
                    raise NotImplementedError
                # Now move on to the next question
                self._next_question()
            else:
                # nonlinear mode
                raise NotImplementedError
        else:
            pass
        if self.cQuestion:
            id = self.form[self.cQuestion]
            item_state = self.namespace[self.cQuestion]
            item_state.begin_attempt(form)
        else:
            # this test had no questions: end screen
            id = None
            pass
        self.add_html_navigation(form)
        return div

    def create_html_form(self, html_parent=None):
        if html_parent:
            div = html_parent.add_child(html.Div)
        else:
            div = html.Div(None)
        form = div.add_child(html.Form)
        form.method = html.Method.POST
        return div, form

    def add_html_navigation(self, form):
        # Now add the navigation
        nav = form.add_child(html.Div)
        nav.style_class = ["navigation"]
        save = nav.add_child(html.Button)
        save.type = html.ButtonType.submit
        save.name = "SAVE"
        save.value = self.key
        save.add_data("_save")
        # Now we need to add the buttons that apply...
        if self.cQuestion:
            id = self.form[self.cQuestion]
            part = self.test.GetPart(id)
            test_part = part.find_parent(tests.TestPart)
            # so what type of testPart are we in?
            if test_part.navigationMode == tests.NavigationMode.linear:
                if test_part.submissionMode == tests.SubmissionMode.individual:
                    # going to the next question is a submit
                    submit = nav.add_child(html.Button)
                    submit.type = html.ButtonType.submit
                    submit.name = "SUBMIT"
                    submit.value = self.key
                    submit.add_data("_next")
                else:
                    raise NotImplementedError
            else:
                raise NotImplementedError
        else:
            save.disabled = True
        return nav

    def add_duration(self, dt):
        iq = self.cQuestion
        ignore = 0
        if iq:
            # we have a question, add to the duration
            self.namespace[iq]["duration"].value += dt
            iq = iq - 1
            ignore = 0
            while iq > 0:
                id = self.form[iq]
                if id[0] == "-":
                    ignore += 1
                else:
                    part = self.test.GetPart(id)
                    if isinstance(part, (tests.AssessmentSection,
                                         tests.TestPart)):
                        if ignore:
                            ignore = ignore - 1
                        else:
                            # This must be an open section or test part
                            v = self.namespace[iq]["duration"]
                            if v:
                                v.value += dt
                            else:
                                v.set_value(dt)
                iq = iq - 1
            # Finally, add to the total test duration
            self.namespace[0]["duration"].value += dt
        else:
            # we've finished the test, don't count time
            pass

    def get_namespace(self, var_name):
        """Returns a tuple of namespace/var_name from variable name

        The resulting namespace will be a dictionary or a
        dictionary-like object from which the value of the returned
        var_name object can be looked up."""
        split_name = var_name.split('.')
        if len(split_name) == 1:
            return self.namespace[0], var_name
        elif len(split_name) > 1:
            ns_index_list = self.form.find(split_name[0])
            if ns_index_list:
                # we can only refer to the first instance when looking up
                # variables
                ns = self.namespace[ns_index_list[0]]
                return ns, '.'.join(split_name[1:])
        logging.debug("Looking for: %s", var_name)
        logging.debug(self.namespace)
        logging.debug(self.form.components)
        raise KeyError(var_name)

    def get_declaration(self, var_name):
        ns, name = self.get_namespace(var_name)
        if isinstance(ns, ItemSessionState):
            return ns.get_declaration(name)
        elif ns:
            if name in ns:
                # a test level variable
                return self.test.get_declaration(name)
            else:
                raise KeyError(var_name)
        else:
            # attempt to look up an unsupported namespace
            raise NotImplementedError

    def is_response(self, var_name):
        """Return True if *var_name* is the name of a response variable.  The
        test-level duration values are treated as built-in responses and return
        True."""
        ns, name = self.get_namespace(var_name)
        if isinstance(ns, ItemSessionState):
            return ns.is_response(name)
        elif ns:
            # duration is the only test-level response variable
            return name == ul('duration')
        else:
            # attempt to look up an unsupported namespace
            raise NotImplementedError

    def set_outcome_defaults(self):
        for od in self.test.OutcomeDeclaration:
            self.namespace[0][od.identifier] = v = od.get_default_value()
            if not v:
                if v.cardinality() == Cardinality.single:
                    if v.baseType == BaseType.integer:
                        v.set_value(0)
                    elif v.baseType == BaseType.float:
                        v.set_value(0.0)

    def __len__(self):
        """Returns the total length of all namespaces combined."""
        total = 0
        for ns in self.namespace:
            if ns is None:
                continue
            else:
                total = total + len(ns)
        return total

    def __getitem__(self, var_name):
        """Returns the :py:class:`Value` instance corresponding to *var_name* or
        raises KeyError if there is no variable with that name."""
        ns, name = self.get_namespace(var_name)
        if ns:
            return ns[name]
        logging.debug("Looking for: %s", var_name)
        logging.debug(self.namespace)
        logging.debug(self.form.components)
        raise KeyError(var_name)

    def __iter__(self):
        for nsName, ns in zip(self.form, self.namespace):
            if ns is None:
                continue
            else:
                if nsName:
                    prefix = nsName + "."
                else:
                    prefix = nsName
                for key in ns:
                    yield prefix + key

    def __contains__(self, var_name):
        try:
            self[var_name]
            return True
        except KeyError:
            return False
