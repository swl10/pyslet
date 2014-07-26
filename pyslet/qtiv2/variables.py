#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2616 as http
import pyslet.html40_19991224 as html
from pyslet.rfc2396 import URI, URIFactory
import pyslet.qtiv2.core as core
import pyslet.qtiv2.tests as tests

import os
import time
import hashlib
import types
import string
import itertools
from types import BooleanType, IntType, LongType, FloatType, StringTypes, DictType, TupleType, ListType


class SessionKeyMismatch(core.QTIError):

    """Exception raised when a session is invoked with the wrong key."""
    pass


class SessionKeyExpired(core.QTIError):

    """Exception raised when a session is invoked with an expired key."""
    pass


class SessionActionMissing(core.QTIError):

    """Exception raised when an unrecognised action is handled by a test session."""


class BaseType(xsi.Enumeration):

    """A base-type is simply a description of a set of atomic values (atomic to
    this specification). Note that several of the baseTypes used to define the
    runtime data model have identical definitions to those of the basic data
    types used to define the values for attributes in the specification itself.
    The use of an enumeration to define the set of baseTypes used in the runtime
    model, as opposed to the use of classes with similar names, is designed to
    help distinguish between these two distinct levels of modelling::

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

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
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
xsi.MakeEnumeration(BaseType)
xsi.MakeLowerAliases(BaseType)


def CheckBaseTypes(*baseType):
    """Checks base types for compatibility.  None is treated as a wild card that
    matches all base types.  It returns the resulting base type, or None if all
    are wild cards.  If they don't match then a ProcessingError is raised."""
    bReturn = None
    for b in baseType:
        if b is None:
            continue
        elif bReturn is None:
            bReturn = b
        elif b != bReturn:
            raise core.ProcessingError("Base type mismatch: %s and %s" % (
                BaseType.EncodeValue(bReturn),
                BaseType.EncodeValue(b)))
    return bReturn


def CheckNumericalTypes(*baseType):
    """Checks base types for numerical compatibility.  None is treated as a wild card that
    matches all base types.  It returns the resulting base type, or None if all
    are wild cards.  If they don't match then a ProcessingError is raised."""
    bReturn = None
    for b in baseType:
        if b is None:
            continue
        elif b not in (BaseType.float, BaseType.integer):
            raise core.ProcessingError(
                "Numeric type required, found: %s" % BaseType.EncodeValue(b))
        elif bReturn is None:
            bReturn = b
        elif b != bReturn:
            # we only return integer when all values are of type integer, so we
            # must return float!
            bReturn = BaseType.float
    return bReturn


class Cardinality(xsi.Enumeration):

    """An expression or itemVariable can either be single-valued or
    multi-valued. A multi-valued expression (or variable) is called a container.
    A container contains a list of values, this list may be empty in which case
    it is treated as NULL. All the values in a multiple or ordered container are
    drawn from the same value set::

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

    For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
    decode = {
        'multiple': 1,
        'ordered': 2,
        'record': 3,
        'single': 4
    }
xsi.MakeEnumeration(Cardinality)


def CheckCardinalities(*cardinality):
    """Checks cardinality values for compatibility.  None is treated as a wild
    card that matches all cardinalities.  It returns the resulting cardinality,
    or None if all are wild cards.  If they don't match then a ProcessingError
    is raised."""
    cReturn = None
    for c in cardinality:
        if c is None:
            continue
        elif cReturn is None:
            cReturn = c
        elif c != cReturn:
            raise core.ProcessingError("Cardinality mismatch: %s and %s" % (
                Cardinality.EncodeValue(cReturn),
                Cardinality.EncodeValue(c)))
    return cReturn


class ValueElement(core.QTIElement):

    """A class that can represent a single value of any baseType in variable
    declarations and result reports::

            <xsd:attributeGroup name="value.AttrGroup">
                    <xsd:attribute name="fieldIdentifier" type="identifier.Type" use="optional"/>
                    <xsd:attribute name="baseType" type="baseType.Type" use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'value')
    XMLATTR_baseType = (
        'baseType', BaseType.DecodeLowerValue, BaseType.EncodeValue)
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


class Value(object):

    """Represents a single value in the processing model.

    This class is the heart of the QTI processing model.  This is an abstract
    base class of a class hierarchy that represents the various types of value
    that may be encountered when processing."""

    def __init__(self):
        self.baseType = None
        """One of the :py:class:`BaseType` constants or None if the baseType is unknown.
		
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

    def SetValue(self, value):
        """Sets the value.

        All single values can be set from a single text string corresponding to
        their XML schema defined lexical values (*without* character level
        escaping).  If v is a single Value instance then the following always
        leaves v unchanged::

                v.SetValue(unicode(v))

        Value instances can also be set from values of the appropriate type as
        described in :py:attr:`value`.  For base types that are represented with
        tuples we also accept and convert lists.

        Containers values cannot be set from strings."""
        if value is None:
            self.value = None
        else:
            self.ValueError(value)

    def ValueError(self, value):
        """Raises a ValueError with a debug-friendly message string."""
        raise ValueError(
            "Can't set value of %s %s from %s" %
            (Cardinality.EncodeValue(
                self.Cardinality()), BaseType.EncodeValue(
                self.baseType), repr(value)))

    def Cardinality(self):
        """Returns the cardinality of this value.  One of the :py:class:`Cardinality` constants.

        By default we return None - indicating unknown cardinality.  This can
        only be the case if the value is a NULL."""
        return None

    def IsNull(self):
        """Returns True is this value is NULL, as defined by the QTI specification."""
        return self.value is None

    def __nonzero__(self):
        """The python non-zero test is equivalent to the non-NULL test in QTI.

        Care is therefore needed, for example::

                flag=BooleanValue(False)
                if flag:
                        print "All non-NULL values are True"
                if flag.value:
                        print "Test the value attribute to access the python native value"

                # prints the following...
                All non-NULL values are True"""
        return self.value is not None

    #: Value instances are mutable so cannot be used as dictionary keys
    __hash__ = None

    def __eq__(self, other):
        """The python equality test is treated like the match operator in QTI.

        We add the test that ensures the other value has matching cardinality
        and matching baseType.  The test then proceeds to return True if the two
        python values compare equal and False if they don't.  If either is Null
        we raise NullResult."""
        CheckCardinalities(self.Cardinality(), other.Cardinality())
        if CheckBaseTypes(self.baseType, other.baseType) == BaseType.duration:
            raise core.ProcessingError("Can't match duration values")
        if self and other:
            return self.value == other.value
        else:
            raise NullResult(BooleanValue())

    def __unicode__(self):
        """Creates a string representation of the object.  The NULL value returns None."""
        if self.value is None:
            return u''
        else:
            raise NotImplementedError(
                "Serialization of %s" % self.__class__.__name__)

    @classmethod
    def NewValue(cls, cardinality, baseType=None):
        """Creates a new value instance with *cardinality* and *baseType*."""
        if cardinality == Cardinality.single:
            return SingleValue.NewValue(baseType)
        elif cardinality == Cardinality.ordered:
            return OrderedContainer(baseType)
        elif cardinality == Cardinality.multiple:
            return MultipleContainer(baseType)
        elif cardinality == Cardinality.record:
            return RecordContainer()
        else:
            raise ValueError("Unknown cardinality")

    @classmethod
    def CopyValue(cls, value):
        """Creates a new value instance copying *value*."""
        v = cls.NewValue(value.Cardinality(), value.baseType)
        v.SetValue(value.value)
        return v


class SingleValue(Value):

    """Represents all values with single cardinality."""

    def Cardinality(self):
        return Cardinality.single

    @classmethod
    def NewValue(cls, baseType, value=None):
        """Creates a new instance of a single value with *baseType* and *value*"""
        if baseType is None:
            return SingleValue()
        elif baseType == BaseType.boolean:
            return BooleanValue(value)
        elif baseType == BaseType.directedPair:
            return DirectedPairValue(value)
        elif baseType == BaseType.duration:
            return DurationValue(value)
        elif baseType == BaseType.file:
            return FileValue(value)
        elif baseType == BaseType.float:
            return FloatValue(value)
        elif baseType == BaseType.identifier:
            return IdentifierValue(value)
        elif baseType == BaseType.integer:
            return IntegerValue(value)
        elif baseType == BaseType.pair:
            return PairValue(value)
        elif baseType == BaseType.point:
            return PointValue(value)
        elif baseType == BaseType.string:
            return StringValue(value)
        elif baseType == BaseType.uri:
            return URIValue(value)
        else:
            raise ValueError("Unknown base type: %s" %
                             BaseType.EncodeValue(baseType))


class BooleanValue(SingleValue):

    """Represents single values of type :py:class:`BaseType.boolean`."""

    def __init__(self, value=None):
        super(BooleanValue, self).__init__()
        self.baseType = BaseType.boolean
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return xsi.EncodeBoolean(self.value)

    def SetValue(self, value):
        """If value is a string it will be decoded according to the rules for representing
        boolean values.  Booleans and integers can be used directly in the normal python
        way but other values will raise ValueError.  To take advantage of a non-zero test
        you must explicitly force it to be a boolean.  For example::

                # x is a value of unknown type with non-zero test implemented
                v=BooleanValue()
                v.SetValue(True if x else False)"""
        if value is None:
            self.value = None
        elif isinstance(value, BooleanType):
            self.value = value
        elif type(value) in (IntType, LongType):
            self.value = True if value else False
        elif type(value) in StringTypes:
            self.value = xsi.DecodeBoolean(value)
        else:
            self.ValueError(value)


class DirectedPairValue(SingleValue):

    """Represents single values of type :py:class:`BaseType.directedPair`."""

    def __init__(self, value=None):
        super(DirectedPairValue, self).__init__()
        self.baseType = BaseType.directedPair
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return string.join(self.value, ' ')

    def SetValue(self, value, nameCheck=False):
        """See comment on :py:meth:`Identifier.SetValue` for usage of *nameCheck*.

        Note that if value is a string then nameCheck is ignored and identifier
        validation is always performed."""
        if value is None:
            self.value = None
        else:
            if type(value) in StringTypes:
                value = string.split(value)
                nameCheck = True
            if type(value) in (ListType, TupleType):
                if len(value) != 2:
                    raise ValueError("%s expected 2 values: %s" % (
                        BaseType.EncodeValue(self.baseType), repr(value)))
                for v in value:
                    if type(v) not in StringTypes or (nameCheck and not xmlns.IsValidNCName(v)):
                        raise ValueError("Illegal identifier %s" % repr(v))
                self.value = (unicode(value[0]), unicode(value[1]))
            else:
                self.ValueError(value)


class FileValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.file`."""

    def __init__(self):
        super(FileValue, self).__init__()
        self.baseType = BaseType.file
        self.contentType = params.MediaType.from_str(
            "application/octet-stream")
        """The content type of the file, a :py:class:`pyslet.rfc2616.HTTPMediaType` instance."""
        self.fileName = "data.bin"
        """The file name to use for the file."""

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            raise NotImplementedError("String serialization of BaseType.file.")

    def SetValue(
            self,
            value,
            type="application/octet-stream",
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
        self.fileName = name
        if value is None:
            self.value = None
        elif isinstance(value, FileType):
            self.value = value
        elif isinstance(value, StringType):
            self.value = StringIO.StringIO(value)
        elif isinstance(value, UnicodeType):
            # Parse this value from the MIME stream.
            raise NotImplementedError(
                "String deserialization of BaseType.file.")
        else:
            self.ValueError(value)


class FloatValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.float`."""

    def __init__(self, value=None):
        super(FloatValue, self).__init__()
        self.baseType = BaseType.float
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return xsi.EncodeDouble(self.value)

    def SetValue(self, value):
        """This method will *not* convert integers to float values, you must do
        this explicitly if you want automatic conversion, for example
        ::

                # x is a numeric value that may be float or integer
                v=FloatValue()
                v.SetValue(float(x))"""
        if value is None:
            self.value = None
        elif isinstance(value, FloatType):
            self.value = value
        elif type(value) in StringTypes:
            self.value = xsi.DecodeDouble(value)
        else:
            self.ValueError(value)


class DurationValue(FloatValue):

    """Represents single value of type :py:class:`BaseType.duration`."""

    def __init__(self, value=None):
        super(DurationValue, self).__init__()
        self.baseType = BaseType.duration
        if value is not None:
            self.SetValue(value)


class IdentifierValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.identifier`."""

    def __init__(self, value=None):
        super(IdentifierValue, self).__init__()
        self.baseType = BaseType.identifier
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return unicode(self.value)

    def SetValue(self, value, nameCheck=True):
        """In general, to speed up computation we do not check the validity of
        identifiers unless parsing the value from a string representation (such
        as a value read from an XML input document).

        As values of baseType identifier are represented natively as strings we
        cannot tell if this method is being called with an existing,
        name-checked value or a new value being parsed from an external source.
        To speed up computation you can suppress the name check in the first
        case by setting *nameCheck* to False (the default is True)."""
        if value is None:
            self.value = None
        elif type(value) in StringTypes:
            if not nameCheck or xmlns.IsValidNCName(value):
                self.value = unicode(value)
            else:
                raise ValueError("Illegal identifier %s" % repr(value))
        else:
            self.ValueError(value)


class IntegerValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.integer`."""

    def __init__(self, value=None):
        super(IntegerValue, self).__init__()
        self.baseType = BaseType.integer
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return xsi.EncodeInteger(self.value)

    def SetValue(self, value):
        """Note that integers and floats are distinct types in QTI: we do not
        accept floats where we would expect integers or *vice versa*.  However,
        integers are accepted from long or plain integer values provided they
        are within the ranges specified in the QTI specification:
        -2147483648...2147483647."""
        if value is None:
            self.value = None
        elif type(value) in (IntType, LongType):
            # python integers may be bigger than 32bits
            if value < -2147483648 or value > 2147483647:
                raise ValueError("Integer range: %s" % repr(value))
            else:
                self.value = int(value)
        elif type(value) in StringTypes:
            self.value = xsi.DecodeInteger(value)
        else:
            self.ValueError(value)


class PairValue(DirectedPairValue):

    """Represents single values of type :py:class:`BaseType.pair`."""

    def __init__(self, value=None):
        super(PairValue, self).__init__()
        self.baseType = BaseType.pair
        if value is not None:
            self.SetValue(value)

    def SetValue(self, value, nameCheck=True):
        """Overrides DirectedPair's implementation to force a predictable ordering on the identifiers."""
        super(PairValue, self).SetValue(value, nameCheck)
        if self.value and self.value[0] > self.value[1]:
            self.value = (self.value[1], self.value[0])


class PointValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.point`."""

    def __init__(self, value=None):
        super(PointValue, self).__init__()
        self.baseType = BaseType.point
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return string.join(map(xsi.EncodeInteger, self.value), ' ')

    def SetValue(self, value):
        if value is None:
            self.value = None
        else:
            if type(value) in StringTypes:
                value = map(xsi.DecodeInteger, string.split(value))
            if type(value) in (ListType, TupleType):
                if len(value) != 2:
                    raise ValueError("%s expected 2 values: %s" % (
                        BaseType.EncodeValue(self.baseType), repr(value)))
                for v in value:
                    if type(v) not in (IntType, LongType):
                        raise ValueError(
                            "Illegal type for point coordinate %s" %
                            repr(
                                type(v)))
                    elif v < -2147483648 or v > 2147483647:
                        raise ValueError(
                            "Integer coordinate range: %s" % repr(v))
                self.value = (int(value[0]), int(value[1]))
            else:
                self.ValueError(value)


class StringValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.string`."""

    def __init__(self, value=None):
        super(StringValue, self).__init__()
        self.baseType = BaseType.string
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return unicode(self.value)

    def SetValue(self, value):
        if value is None:
            self.value = None
        elif type(value) in StringTypes:
            self.value = unicode(value)
            if len(self.value) == 0:
                self.value = None
        else:
            self.ValueError(value)


class URIValue(SingleValue):

    """Represents single value of type :py:class:`BaseType.uri`."""

    def __init__(self, value=None):
        super(URIValue, self).__init__()
        self.baseType = BaseType.uri
        if value is not None:
            self.SetValue(value)

    def __unicode__(self):
        if self.value is None:
            return u''
        else:
            return unicode(self.value)

    def SetValue(self, value):
        """Sets a uri value from a string or another URI instance."""
        if value is None:
            self.value = None
        elif type(value) in StringTypes:
            self.value = URIFactory.URI(value)
        elif isinstance(value, URI):
            self.value = value
        else:
            self.ValueError(value)


class Container(Value):

    """An abstract class for all container types.

    By default containers are empty (and are treated as NULL values).  You can
    force the type of an empty container by passing a baseType constant to the
    constructor.  This will cause the container to generate TypeError if used in
    a context where the specified baseType is not allowed."""

    def __init__(self, baseType=None):
        super(Container, self).__init__()
        self.baseType = baseType

    def GetValues(self):
        """Returns an iterable of the container's values."""
        return

    def __unicode__(self):
        """For single values we return a representation suitable for use as the
        content of a single XML element.  For containers this option is not
        open to us because they are always represented by multiple elements.

        We therefore opt for a minimal representation."""
        if self.baseType is None:
            return u"%s container of unknown base type" % Cardinality.EncodeValue(
                self.Cardinality)
        else:
            return u"%s container of base type %s" % (Cardinality.EncodeValue(
                self.Cardinality),
                BaseType.EncodeValue(
                self.baseType))

    @classmethod
    def NewValue(cls, cardinality, baseType=None):
        """Creates a new container with *cardinality* and *baseType*."""
        if cardinality == Cardinality.single:
            raise ValueError("Container with single cardinality")
        elif cardinality == Cardinality.ordered:
            return OrderedContainer(baseType)
        elif cardinality == Cardinality.multiple:
            return MultipleContainer(baseType)
        elif cardinality == Cardinality.record:
            return RecordContainer()
        else:
            return Container(baseType)


class OrderedContainer(Container):

    """Represents containers with ordered :py:class:`Cardinality`."""

    def Cardinality(self):
        return Cardinality.ordered

    def SetValue(self, value, baseType=None):
        """Sets the value of this container from a list, tuple or other
        iterable. The list must contain valid representations of *baseType*,
        items may be None indicating a NULL value in the list.  In accordance
        with the specification's multiple operator NULL values are ignored.

        If the input list of values empty, or contains only NULL values then the
        resulting container is empty.

        If *baseType* is None the base type specified when the container was
        constructed is assumed."""
        if baseType is not None:
            self.baseType = baseType
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
                        "Can't create non-empty ordered container without a base type")
                vAdd = SingleValue.NewValue(self.baseType, v)
                self.value.append(vAdd.value)
            if not self.value:
                self.value = None

    def GetValues(self):
        """Returns an iterable of values in the ordered container."""
        if self.value is None:
            return
        for v in self.value:
            yield v


class MultipleContainer(Container):

    """Represents containers with multiple :py:class:`Cardinality`."""

    def Cardinality(self):
        return Cardinality.multiple

    def SetValue(self, value, baseType=None):
        """Sets the value of this container from a list, tuple or other
        iterable. The list must contain valid representations of *baseType*,
        items may be None indicating a NULL value in the list.  In accordance
        with the specification's multiple operator NULL values are ignored.

        If the input list of values is empty, or contains only NULL values then the
        resulting container is empty.

        If *baseType* is None the base type specified when the container was
        constructed is assumed."""
        if baseType is not None:
            self.baseType = baseType
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
                        "Can't create non-empty multiple container without a base type")
                vAdd = SingleValue.NewValue(self.baseType, v)
                self.value[vAdd.value] = self.value.get(vAdd.value, 0) + 1
            if not self.value:
                self.value = None

    def GetValues(self):
        """Returns an iterable of values in the ordered container."""
        if self.value is None:
            return
        keys = sorted(self.value.keys())
        for k in keys:
            for i in xrange(self.value[k]):
                yield k


class RecordContainer(Container):

    """Represents containers with record :py:class:`Cardinality`."""

    def __init__(self):
        super(Container, self).__init__()

    def Cardinality(self):
        return Cardinality.record

    def SetValue(self, value):
        """Sets the value of this container from an existing dictionary in which
        the keys are the field identifiers and the values are :py:class:`Value`
        instances. You cannot parse containers from strings.

        Records are always treated as having a wild-card base type.

        If the input *value* contains any keys which map to None or to a NULL
        value then these fields are omitted from the resulting value."""
        if value is None:
            self.value = None
        else:
            newValue = {}
            if isinstance(value, DictType):
                valueDict = value
                fieldList = value.keys()
            else:
                raise ValueError(
                    "RecordContainer.SetValue expected dictionary, found %s" %
                    repr(value))
            for f in fieldList:
                v = value[f]
                if v is None:
                    continue
                if not isinstance(v, SingleValue):
                    raise ValueError(
                        "Single value required, found %s" % repr(v))
                if not v:
                    # ignore NULL, no need to type check in records
                    continue
                newValue[f] = value[f]
            if newValue:
                self.value = newValue
            else:
                self.value = None

    def __len__(self):
        if self.value:
            return len(self.value)
        else:
            return 0

    def __getitem__(self, fieldIdentifier):
        """Returns the :py:class:`Value` instance corresponding to
        *fieldIdentifier* or raises KeyError if there is no field with that
        name."""
        if self.value:
            return self.value[fieldIdentifier]
        else:
            raise KeyError(fieldIdentifier)

    def __setitem__(self, fieldIdentifier, value):
        """Sets the value in the named field to *value*.

        We add some special behaviour here.  If *value* is None or is a NULL
        value then we remove the field with the give name.  In other words::

                r=RecordContainer()
                r['pi']=FloatValue(3.14)
                r['pi']=FloatValue()     # a NULL value
                print r['pi']            # raises KeyError"""
        if value is None:
            if self.value and fieldIdentifier in self.value:
                del self.value[fieldIdentifier]
        elif isinstance(value, SingleValue):
            if not value:
                if self.value and fieldIdentifier in self.value:
                    del self.value[fieldIdentifier]
            else:
                if self.value is None:
                    self.value = {fieldIdentifier: value}
                else:
                    self.value[fieldIdentifier] = value
        else:
            raise ValueError("Single value required, found %s" % repr(v))

    def __delitem__(self, fieldIdentifier):
        if self.value:
            del self.value[fieldIdentifier]
        else:
            raise KeyError(fieldIdentifier)

    def __iter__(self):
        if self.value:
            return iter(self.value)
        else:
            return iter([])

    def __contains__(self, fieldIdentifier):
        if self.value:
            return fieldIdentifier in self.value
        else:
            return False


class VariableDeclaration(core.QTIElement):

    """Item variables are declared by variable declarations... The purpose of the
    declaration is to associate an identifier with the variable and to identify
    the runtime type of the variable's value::

            <xsd:attributeGroup name="variableDeclaration.AttrGroup">
                    <xsd:attribute name="identifier" type="identifier.Type" use="required"/>
                    <xsd:attribute name="cardinality" type="cardinality.Type" use="required"/>
                    <xsd:attribute name="baseType" type="baseType.Type" use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="variableDeclaration.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="defaultValue" minOccurs="0" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLATTR_baseType = (
        'baseType', BaseType.DecodeLowerValue, BaseType.EncodeValue)
    XMLATTR_cardinality = (
        'cardinality', Cardinality.DecodeLowerValue, Cardinality.EncodeValue)
    XMLATTR_identifier = ('identifier', core.ValidateIdentifier, lambda x: x)

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.identifier = ''
        self.cardinality = Cardinality.DEFAULT
        self.baseType = None
        self.DefaultValue = None

    def __cmp__(self, other):
        if isinstance(other, VariableDeclaration):
            return cmp(self.identifier, other.identifier)
        else:
            raise TypeError(
                "Can't compare VariableDeclaration with %s" % repr(other))

    def GetChildren(self):
        if self.DefaultValue:
            yield self.DefaultValue
        for child in core.QTIElement.GetChildren(self):
            yield child

    def ContentChanged(self):
        if self.parent:
            self.parent.RegisterDeclaration(self)

    def GetDefinedValue(self, definedValue):
        if definedValue:
            if self.cardinality == Cardinality.single:
                value = SingleValue.NewValue(
                    self.baseType, definedValue.ValueElement[0].GetValue())
            else:
                value = Value.NewValue(self.cardinality, self.baseType)
                if isinstance(value, RecordContainer):
                    # handle record processing
                    for v in definedValue.ValueElement:
                        value[v.fieldIdentifier] = SingleValue.NewValue(
                            v.baseType, v.GetValue())
                else:
                    # handle multiple and ordered processing
                    value.SetValue(
                        map(lambda v: v.GetValue(), definedValue.ValueElement))
        else:
            # generate NULL values with the correct cardinality and base type
            if self.cardinality == Cardinality.single:
                value = SingleValue.NewValue(self.baseType)
            else:
                value = Value.NewValue(self.cardinality, self.baseType)
        return value

    def GetDefaultValue(self):
        """Returns a :py:class:`Value` instance representing either the default
        value or an appropriately typed NULL value if there is no default
        defined."""
        return self.GetDefinedValue(self.DefaultValue)


class DefinedValue(core.QTIElement):

    """An abstract class used to implement the common behaviour of
    :py:class:`DefaultValue` and :py:class:`CorrectResponse` ::

            <xsd:attributeGroup name="defaultValue.AttrGroup">
                    <xsd:attribute name="interpretation" type="string.Type" use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="defaultValue.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="value" minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLATTR_interpretation = 'interpretation'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.interpretation = None
        self.ValueElement = []

    def GetChildren(self):
        return itertools.chain(
            self.ValueElement,
            core.QTIElement.GetChildren(self))


class DefaultValue(DefinedValue):

    """An optional default value for a variable. The point at which a variable
    is set to its default value varies depending on the type of item
    variable."""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'defaultValue')


class Mapping(core.QTIElement):

    """A special class used to create a mapping from a source set of any
    baseType (except file and duration) to a single float::

            <xsd:attributeGroup name="mapping.AttrGroup">
                    <xsd:attribute name="lowerBound" type="float.Type" use="optional"/>
                    <xsd:attribute name="upperBound" type="float.Type" use="optional"/>
                    <xsd:attribute name="defaultValue" type="float.Type" use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="mapping.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="mapEntry" minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'mapping')
    XMLATTR_lowerBound = ('lowerBound', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_upperBound = ('upperBound', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_defaultValue = ('defaultValue', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.lowerBound = None
        self.upperBound = None
        self.defaultValue = 0.0
        self.MapEntry = []
        self.baseType = BaseType.string
        self.map = {}

    def GetChildren(self):
        return iter(self.MapEntry)

    def ContentChanged(self):
        """Builds an internal dictionary of the values being mapped.

        In order to fully specify the mapping we need to know the baseType of
        the source values.  (The targets are always floats.)  We do this based
        on our parent, orphan Mapping elements are treated as mappings from
        source strings."""
        if isinstance(self.parent, ResponseDeclaration):
            self.baseType = self.parent.baseType
        elif isinstance(self.parent, CategorizedStatistic):
            self.baseType = BaseType.integer
        else:
            self.baseType = BaseType.string
        self.map = {}
        for me in self.MapEntry:
            v = SingleValue.NewValue(self.baseType, me.mapKey)
            self.map[v.value] = me.mappedValue

    def MapValue(self, value):
        """Maps an instance of :py:class:`Value` with the same base type as the
        mapping to an instance of :py:class:`Value` with base type float."""
        nullFlag = False
        if not value:
            srcValues = []
            nullFlag = True
        elif value.Cardinality() == Cardinality.single:
            srcValues = [value.value]
        elif value.Cardinality() == Cardinality.ordered:
            srcValues = value.value
        elif value.Cardinality() == Cardinality.multiple:
            srcValues = value.value.keys()
        else:
            raise ValueError("Can't map %s" % repr(value))
        result = 0.0
        beenThere = {}
        dstValue = FloatValue(0.0)
        if value.baseType is None:
            # a value of unknown type results in NULL
            nullFlag = True
        for v in srcValues:
            if v in beenThere:
                # If a container contains multiple instances of the same value
                # then that value is counted once only
                continue
            else:
                beenThere[v] = True
            result = result + self.map.get(v, self.defaultValue)
        if nullFlag:
            # We save the NULL return up to the end to ensure that we generate errors
            # in the case where a container contains mixed or mismatching
            # values.
            return dstValue
        else:
            if self.lowerBound is not None and result < self.lowerBound:
                result = self.lowerBound
            elif self.upperBound is not None and result > self.upperBound:
                result = self.upperBound
            dstValue.SetValue(result)
            return dstValue


class MapEntry(core.QTIElement):

    """An entry in a :py:class:`Mapping`
    ::

            <xsd:attributeGroup name="mapEntry.AttrGroup">
                    <xsd:attribute name="mapKey" type="valueType.Type" use="required"/>
                    <xsd:attribute name="mappedValue" type="float.Type" use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'mapEntry')
    XMLATTR_mapKey = 'mapKey'
    XMLATTR_mappedValue = ('mappedValue', xsi.DecodeFloat, xsi.EncodeFloat)
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
                            <xsd:element ref="correctResponse" minOccurs="0" maxOccurs="1"/>
                            <xsd:element ref="mapping" minOccurs="0" maxOccurs="1"/>
                            <xsd:element ref="areaMapping" minOccurs="0" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'responseDeclaration')
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        VariableDeclaration.__init__(self, parent)
        self.CorrectResponse = None
        self.Mapping = None
        self.AreaMapping = None

    def GetChildren(self):
        for child in VariableDeclaration.GetChildren(self):
            yield child
        if self.CorrectResponse:
            yield self.CorrectResponse
        if self.Mapping:
            yield self.Mapping
        if self.AreaMapping:
            yield self.AreaMapping

    def GetCorrectValue(self):
        """Returns a :py:class:`Value` instance representing either the correct
        response value or an appropriately typed NULL value if there is no
        correct value."""
        return self.GetDefinedValue(self.CorrectResponse)

    def GetStageDimensions(self):
        """For response variables with point type, returns a pair of integer
        values: width,height

        In HTML, shapes (including those used in the AreaMapping) can use
        relative coordinates. To interpret relative coordinates we need to know
        the size of the stage used to interpret the point values.  For a
        response variable that is typically the size of the image or object used
        in the interaction.

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
                    <xsd:attribute name="lowerBound" type="float.Type" use="optional"/>
                    <xsd:attribute name="upperBound" type="float.Type" use="optional"/>
                    <xsd:attribute name="defaultValue" type="float.Type" use="required"/>
            </xsd:attributeGroup>

            <xsd:group name="areaMapping.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="areaMapEntry" minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'areaMapping')
    XMLATTR_lowerBound = ('lowerBound', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_upperBound = ('upperBound', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_defaultValue = ('defaultValue', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        self.lowerBound = None
        self.upperBound = None
        self.defaultValue = 0.0
        self.AreaMapEntry = []

    def GetChildren(self):
        return iter(self.AreaMapEntry)

    def MapValue(self, value, width, height):
        """Maps an instance of :py:class:`Value` with point base type to an
        instance of :py:class:`Value` with base type float.

        *	value is a :py:class:`Value` of base type point

        *	width is the integer width of the object on which the area is defined

        *	height is the integer height of the object on which the area is defined

        The width and height of the object are required because HTML allows
        relative values to be used when defining areas."""
        nullFlag = False
        if not value:
            srcValues = []
            nullFlag = True
        elif value.Cardinality() == Cardinality.single:
            srcValues = [value.value]
        elif value.Cardinality() == Cardinality.ordered:
            srcValues = value.value
        elif value.Cardinality() == Cardinality.multiple:
            srcValues = value.value.keys()
        else:
            raise ValueError("Can't map %s" % repr(value))
        result = 0.0
        beenThere = [False] * len(self.AreaMapEntry)
        dstValue = FloatValue(0.0)
        if value.baseType is None:
            # a value of unknown type results in NULL
            nullFlag = True
        elif value.baseType != BaseType.point:
            raise ValueError("Can't map %s" % repr(value))
        for v in srcValues:
            hitPoint = False
            for i in xrange(len(self.AreaMapEntry)):
                if self.AreaMapEntry[i].TestPoint(v, width, height):
                    hitPoint = True
                    if not beenThere[i]:
                        # When mapping containers each area can be mapped once
                        # only
                        beenThere[i] = True
                        result = result + self.AreaMapEntry[i].mappedValue
                    break
            if not hitPoint:
                # This point is not in any of the areas
                result = result + self.defaultValue
        if nullFlag:
            # We save the NULL return up to the end to ensure that we generate errors
            # in the case where a container contains mixed or mismatching
            # values.
            return dstValue
        else:
            if self.lowerBound is not None and result < self.lowerBound:
                result = self.lowerBound
            elif self.upperBound is not None and result > self.upperBound:
                result = self.upperBound
            dstValue.SetValue(result)
            return dstValue


class AreaMapEntry(core.QTIElement, core.ShapeElementMixin):

    """An :py:class:`AreaMapping` is defined by a set of areaMapEntries, each of
    which maps an area of the coordinate space onto a single float::

            <xsd:attributeGroup name="areaMapEntry.AttrGroup">
                    <xsd:attribute name="shape" type="shape.Type" use="required"/>
                    <xsd:attribute name="coords" type="coords.Type" use="required"/>
                    <xsd:attribute name="mappedValue" type="float.Type" use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'areaMapEntry')
    XMLATTR_mappedValue = ('mappedValue', xsi.DecodeFloat, xsi.EncodeFloat)
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
                    <xsd:attribute name="interpretation" type="string.Type" use="optional"/>
                    <xsd:attribute name="longInterpretation" type="uri.Type" use="optional"/>
                    <xsd:attribute name="normalMaximum" type="float.Type" use="optional"/>
                    <xsd:attribute name="normalMinimum" type="float.Type" use="optional"/>
                    <xsd:attribute name="masteryValue" type="float.Type" use="optional"/>
            </xsd:attributeGroup>

            <xsd:group name="outcomeDeclaration.ContentGroup">
                    <xsd:sequence>
                            <xsd:group ref="variableDeclaration.ContentGroup"/>
                            <xsd:group ref="lookupTable.ElementGroup" minOccurs="0" maxOccurs="1"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'outcomeDeclaration')
    XMLATTR_view = (
        'view',
        core.View.DecodeLowerValue,
        core.View.EncodeValue,
        types.DictType)
    XMLATTR_interpretation = 'interpretation'
    XMLATTR_longInterpretation = (
        'longInterpretation', html.DecodeURI, html.EncodeURI)
    XMLATTR_normalMaximum = ('normalMaximum', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_normalMinimum = ('normalMinimum', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_masteryValue = ('masteryValue', xsi.DecodeFloat, xsi.EncodeFloat)
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

    def GetChildren(self):
        for child in VariableDeclaration.GetChildren(self):
            yield child
        if self.LookupTable:
            yield self.LookupTable


class LookupTable(core.QTIElement):

    """An abstract class associated with an outcomeDeclaration used to create a
    lookup table from a numeric source value to a single outcome value in the
    declared value set::

            <xsd:attributeGroup name="lookupTable.AttrGroup">
                    <xsd:attribute name="defaultValue" type="valueType.Type" use="optional"/>
            </xsd:attributeGroup>"""
    XMLATTR_defaultValue = 'defaultValue'
    XMLATTR_interpretation = 'interpretation'
    XMLATTR_longInterpretation = (
        'longInterpretation', html.DecodeURI, html.EncodeURI)
    XMLATTR_normalMaximum = ('normalMaximum', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_normalMinimum = ('normalMinimum', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_masteryValue = ('masteryValue', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        core.QTIElement.__init__(self, parent)
        # : a string from which the default is parsed when its base type is known
        self.defaultValue = None
        self.baseType = BaseType.string
        #: a :py:class:`Value` instance representing the default
        self.default = None

    def ContentChanged(self):
        if isinstance(self.parent, OutcomeDeclaration):
            self.baseType = self.parent.baseType
        else:
            self.baseType = BaseType.string
        self.default = SingleValue.NewValue(self.baseType, self.defaultValue)


class MatchTable(LookupTable):

    """A matchTable transforms a source integer by finding the first
    matchTableEntry with an exact match to the source::

            <xsd:group name="matchTable.ContentGroup">
                    <xsd:sequence>
                            <xsd:element ref="matchTableEntry" minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'matchTable')

    def __init__(self, parent):
        LookupTable.__init__(self, parent)
        self.MatchTableEntry = []
        self.map = {}

    def GetChildren(self):
        return iter(self.MatchTableEntry)

    def ContentChanged(self):
        """Builds an internal dictionary of the values being mapped."""
        LookupTable.ContentChanged(self)
        self.map = {}
        for mte in self.MatchTableEntry:
            v = SingleValue.NewValue(self.baseType, mte.targetValue)
            self.map[mte.sourceValue] = v.value

    def Lookup(self, value):
        """Maps an instance of :py:class:`Value` with integer base type to an
        instance of :py:class:`Value` with the base type of the match table."""
        nullFlag = False
        if not value:
            nullFlag = True
            srcValue = None
        elif value.Cardinality() != Cardinality.single:
            raise ValueError("Can't match container: %s" % repr(value))
        elif value.baseType != BaseType.integer:
            raise ValueError(
                "MatchTable requires integer, found %s" %
                BaseType.EncodeValue(
                    value.baseType))
        else:
            srcValue = value.value
        dstValue = SingleValue.NewValue(self.baseType)
        if not nullFlag:
            dstValue.SetValue(self.map.get(srcValue, self.default.value))
        return dstValue


class MatchTableEntry(core.QTIElement):

    """sourceValue
            The source integer that must be matched exactly.

    targetValue
            The target value that is used to set the outcome when a match is found

    ::

            <xsd:attributeGroup name="matchTableEntry.AttrGroup">
                    <xsd:attribute name="sourceValue" type="integer.Type" use="required"/>
                    <xsd:attribute name="targetValue" type="valueType.Type" use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'matchTableEntry')
    XMLATTR_sourceValue = ('sourceValue', xsi.DecodeInteger, xsi.EncodeInteger)
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
                            <xsd:element ref="interpolationTableEntry" minOccurs="1" maxOccurs="unbounded"/>
                    </xsd:sequence>
            </xsd:group>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'interpolationTable')

    def __init__(self, parent):
        LookupTable.__init__(self, parent)
        self.InterpolationTableEntry = []
        self.table = []

    def GetChildren(self):
        return iter(self.InterpolationTableEntry)

    def ContentChanged(self):
        """Builds an internal table of the values being mapped."""
        LookupTable.ContentChanged(self)
        self.table = []
        for ite in self.InterpolationTableEntry:
            v = SingleValue.NewValue(self.baseType, ite.targetValue)
            self.table.append((ite.sourceValue, ite.includeBoundary, v.value))

    def Lookup(self, value):
        """Maps an instance of :py:class:`Value` with integer or float base type
        to an instance of :py:class:`Value` with the base type of the
        interpolation table."""
        nullFlag = False
        if not value:
            nullFlag = True
            srcValue = None
        elif value.Cardinality() != Cardinality.single:
            raise ValueError("Can't match container: %s" % repr(value))
        elif value.baseType == BaseType.integer:
            srcValue = float(value.value)
        elif value.baseType in (BaseType.float, BaseType.duration):
            srcValue = value.value
        else:
            raise ValueError(
                "Interpolation table requires integer or float, found %s" %
                BaseType.EncodeValue(
                    value.baseType))
        dstValue = SingleValue.NewValue(self.baseType)
        if not nullFlag:
            dstValue.SetValue(self.default.value)
            for testValue, lte, targetValue in self.table:
                if testValue < srcValue or (lte and testValue == srcValue):
                    dstValue.SetValue(targetValue)
                    break
        return dstValue


class InterpolationTableEntry(core.QTIElement):

    """sourceValue
            The lower bound for the source value to match this entry.

    includeBoundary
            Determines if an exact match of sourceValue matches this entry. If true,
            the default, then an exact match of the value is considered a match of
            this entry.

    targetValue
            The target value that is used to set the outcome when a match is found

    ::

            <xsd:attributeGroup name="interpolationTableEntry.AttrGroup">
                    <xsd:attribute name="sourceValue" type="float.Type" use="required"/>
                    <xsd:attribute name="includeBoundary" type="boolean.Type" use="optional"/>
                    <xsd:attribute name="targetValue" type="valueType.Type" use="required"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'interpolationTableEntry')
    XMLATTR_sourceValue = ('sourceValue', xsi.DecodeFloat, xsi.EncodeFloat)
    XMLATTR_includeBoundary = (
        'includeBoundary', xsi.DecodeBoolean, xsi.EncodeBoolean)
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
                    <xsd:attribute name="paramVariable" type="boolean.Type" use="optional"/>
                    <xsd:attribute name="mathVariable" type="boolean.Type" use="optional"/>
            </xsd:attributeGroup>"""
    XMLNAME = (core.IMSQTI_NAMESPACE, 'templateDeclaration')
    XMLATTR_paramVariable = (
        'paramVariable', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLATTR_mathVariable = (
        'mathVariable', xsi.DecodeBoolean, xsi.EncodeBoolean)
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        VariableDeclaration.__init__(self, parent)
        self.paramVariable = None
        self.mathVariable = None


class SessionState(object):

    """Abstract class used as the base class for namespace-like objects used to
    track the state of an item or test session.  Instances can be used as if
    they were dictionaries of :py:class:`Value`."""

    def GetDeclaration(self, varName):
        """Returns the declaration associated with *varName* or None if the
        variable is one of the built-in variables.  If *varName* is not a
        variable KeyError is raised.  To test for the existence of a variable
        just use the object as you would a dictionary::

                # state is a SessionState instance
                if 'RESPONSE' in state:
                        print "RESPONSE declared!" """
        raise KeyError(varName)

    def IsResponse(self, varName):
        """Return True if *varName* is the name of a response variable."""
        d = self.GetDeclaration(varName)
        return isinstance(d, ResponseDeclaration)

    def IsOutcome(self, varName):
        """Return True if *varName* is the name of an outcome variable."""
        d = self.GetDeclaration(varName)
        return isinstance(d, OutcomeDeclaration)

    def SetOutcomeDefaults(self):
        raise NotImplementedError

    def IsTemplate(self, varName):
        """Return True if *varName* is the name of a template variable."""
        d = self.GetDeclaration(varName)
        return isinstance(d, TemplateDeclaration)

    def __len__(self):
        return 0

    def __getitem__(self, varName):
        """Returns the :py:class:`Value` instance corresponding to *varName* or
        raises KeyError if there is no variable with that name."""
        raise KeyError(varName)

    def __setitem__(self, varName, value):
        """Sets the value of *varName* to the :py:class:`Value` instance *value*.

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
                r1==r2		# WARNING: r1 has been updated so still evaluates to True!"""
        if not isinstance(value, Value):
            raise TypeError
        v = self[varName]
        if value.Cardinality() is not None and value.Cardinality() != v.Cardinality():
            raise ValueError(
                "Expected %s value, found %s" %
                (Cardinality.EncodeValue(
                    v.Cardinality()), Cardinality.EncodeValue(
                    value.Cardinality())))
        if value.baseType is not None and value.baseType != v.baseType:
            raise ValueError(
                "Expected %s value, found %s" %
                (BaseType.EncodeValue(
                    v.baseType), BaseType.EncodeValue(
                    value.baseType)))
        v.SetValue(value.value)

    def __delitem__(self, varName):
        raise TypeError("Can't delete variables from SessionState")

    def __iter__(self):
        raise NotImplementedError

    def __contains__(self, varName):
        raise KeyError(varName)


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
            self.map[td.identifier] = td.GetDefaultValue()
        # add the default response variables
        self.map['numAttempts'] = IntegerValue()
        self.map['duration'] = DurationValue()
        self.map['completionStatus'] = IdentifierValue()
        # now loop through the declared variables...
        for rd in self.item.ResponseDeclaration:
            self.map[rd.identifier + ".CORRECT"] = rd.GetCorrectValue()
            self.map[rd.identifier + ".DEFAULT"] = rd.GetDefaultValue()
            # Response variables do not get their default... yet!
            self.map[rd.identifier] = Value.NewValue(
                rd.cardinality, rd.baseType)
        # outcomes do not get their default yet either
        for od in self.item.OutcomeDeclaration:
            self.map[od.identifier + ".DEFAULT"] = od.GetDefaultValue()
            self.map[od.identifier] = Value.NewValue(
                od.cardinality, od.baseType)

    def SelectClone(self):
        """Item templates describe a range of possible items referred to as
        *clones*.

        If the item used to create the session object is an item template then
        you must call SelectClone before beginning the candidate's session with
        :py:meth:`BeginSession`.

        The main purpose of this method is to run the template processing rules.
        These rules update the values of the template variables and may also
        alter correct responses and default outcome (or response) values."""
        if self.item.TemplateProcessing:
            self.item.TemplateProcessing.Run(self)

    def BeginSession(self):
        """Called at the start of an item session. According to the specification:

                "The session starts when the associated item first becomes eligible
                for delivery to the candidate"

        The main purpose of this method is to set the outcome values to their
        defaults."""
        # sets the default values of all outcome variables
        self.map['completionStatus'].value = u'not_attempted'
        self.SetOutcomeDefaults()
        # The spec says that numAttempts is a response that has value 0 initially.
        # That suggests that it behaves more like an outcome in this respect so we
        # initialise the value here.
        self.map['numAttempts'].value = 0
        # similar consideration applies to the built-in duration
        self.map['duration'].value = 0.0
        # the rest of the response variables are initialised when the first
        # attempt starts

    def BeginAttempt(self, htmlParent=None):
        """Called at the start of an attempt.

        This method sets the default RESPONSE values and completionStatus if
        this is the first attempt and increments numAttempts accordingly."""
        numAttempts = self.map['numAttempts']
        numAttempts.SetValue(numAttempts.value + 1)
        if numAttempts.value == 1:
            # first attempt, set default responses
            for rd in self.item.ResponseDeclaration:
                self.map[rd.identifier] = Value.CopyValue(
                    self.map[rd.identifier + ".DEFAULT"])
            # and set completionStatus
            self.map['completionStatus'] = IdentifierValue('unknown')
        return self.item.RenderHTML(self, htmlParent)

    def SaveSession(self, params, htmlParent=None):
        """Called when we wish to save unsubmitted values."""
        self._SaveParameters(params)
        return self.item.RenderHTML(self, htmlParent)

    def SubmitSession(self, params, htmlParent=None):
        """Called when we wish to submit values (i.e., end an attempt)."""
        self._SaveParameters(params)
        # Now we go through all response variables and update their value from the
        # saved value, removing the saved values as we go.
        for rd in self.item.ResponseDeclaration:
            sName = rd.identifier + ".SAVED"
            if sName in self.map:
                self.map[rd.identifier].SetValue(self.map[sName].value)
                del self.map[sName]
        self.EndAttempt()
        return self.item.RenderHTML(self, htmlParent)

    def _SaveParameters(self, params):
        orderedParams = {}
        for p in params:
            if self.formPrefix and not p.startswith(self.formPrefix):
                # ignore values not intended for us
                continue
            rName = p[len(self.formPrefix):].split(".")
            if not rName:
                continue
            # rName must be the name of a response variable
            rd = self.GetDeclaration(rName[0])
            if rd is None or not isinstance(rd, ResponseDeclaration):
                # unexpected item in bagging area!
                raise BadSessionParams(
                    "Unexpected item submitted wth form: %s" % p)
            # so we have a new response value to save
            saveName = rName[0] + ".SAVED"
            if saveName not in self:
                self.map[saveName] = v = Value.NewValue(
                    rd.cardinality, rd.baseType)
            else:
                v = self.map[saveName]
            # now we need to parse a value from the form to save
            sValue = params[p]
            if rd.cardinality == Cardinality.single:
                # We are expecting a single value from the form
                if type(sValue) in StringTypes:
                    v.SetValue(sValue)
                else:
                    raise BadSessionParams(
                        "Unexpected multi-value submission: %s" % p)
            elif rd.cardinality == Cardinality.multiple:
                # we are expecting a simple list of values
                if type(sValue) in StringTypes:
                    # single item list
                    v.SetValue([sValue])
                else:
                    v.SetValue(sValue)
            elif rd.cardinality == Cardinality.ordered:
                # there are two ways of setting these values, either RESPONSE.rank=VALUE
                # or RESPONSE.VALUE=rank.  The latter representation is only valid for
                # identifiers, to ensure we don't mix them up with ranks.
                if len(rName) != 2:
                    continue
                try:
                    if rd.baseType == BaseType.Identifier and core.ValidateIdentifier(rName[1]):
                        if type(sValue) in StringTypes:
                            v.SetValue(sValue)
                        else:
                            raise ValueError
                        rank = xsi.DecodeInteger(sValue)
                        sValue = rName[1]
                    else:
                        rank = xsi.DecodeInteger(rName[1])
                    if saveName in orderedParams:
                        if rank in orderedParams[saveName]:
                            # duplicate entries, we don't allow these
                            raise ValueError
                        orderedParams[saveName][rank] = sValue
                    else:
                        orderedParams[saveName] = {rank: sValue}
                except ValueError:
                    raise BadSessionParams(
                        "Bad value in submission for: %s" % p)
            else:
                raise NotImplementedError
        if orderedParams:
            # we've gathered ordered parameters in a dictionary of dictionaries
            # keyed first on response identifier and then on rank.  For each
            # response we just sort them, so missing ranks are OK.
            for response in orderedParams:
                rParams = orderedParams[response]
                ranks = sorted(rParams.keys())
                sValue = []
                for r in ranks:
                    sValue.append(rParams[r])
                saveName = response + ".SAVED"
                v = self.map[saveName]
                v.SetValue(sValue)

    def EndAttempt(self):
        """Called at the end of an attempt.  Invokes response processing if present."""
        if not self.item.adaptive:
            # For a Non-adaptive Item the values of the outcome variables are
            # reset to their default values (or NULL if no default is given)
            # before each invocation of response processing
            self.SetOutcomeDefaults()
        if self.item.ResponseProcessing:
            self.item.ResponseProcessing.Run(self)

    def GetDeclaration(self, varName):
        if varName in self.map:
            return self.item.GetDeclaration(varName)
        else:
            raise KeyError(varName)

    def IsResponse(self, varName):
        """Return True if *varName* is the name of a response variable.

        We add handling of the built-in response variables numAttempts and duration."""
        d = self.GetDeclaration(varName)
        if d is None:
            return varName in ('numAttempts', 'duration')
        else:
            return isinstance(d, ResponseDeclaration)

    def IsOutcome(self, varName):
        """Return True if *varName* is the name of an outcome variable.

        We add handling of the built-in outcome variable completionStatus."""
        d = self.GetDeclaration(varName)
        if d is None:
            return varName == 'completionStatus'
        else:
            return isinstance(d, OutcomeDeclaration)

    def SetOutcomeDefaults(self):
        for od in self.item.OutcomeDeclaration:
            self.map[od.identifier] = v = Value.CopyValue(
                self.map[od.identifier + ".DEFAULT"])
            if not v:
                if v.Cardinality() == Cardinality.single:
                    if v.baseType == BaseType.integer:
                        v.SetValue(0)
                    elif v.baseType == BaseType.float:
                        v.SetValue(0.0)

    def __len__(self):
        return len(self.map)

    def __getitem__(self, varName):
        return self.map[varName]

    def __iter__(self):
        return iter(self.map)

    def __contains__(self, varName):
        return varName in self.map


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
        #: the :py:class:`tests.AssessmentTest` that this session is an instance of
        self.test = form.test
        self.namespace = len(form) * [None]
        self.namespace[0] = {}
        # add the default response variables
        self.namespace[0]['duration'] = DurationValue()
        # now loop through all test parts and (visible) sections to define
        # other durations
        for i in xrange(1, len(self.namespace)):
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
            self.namespace[0][od.identifier] = Value.NewValue(
                od.cardinality, od.baseType)
        self.t = None			#: the time of the last event
        try:
            #: a random string of bytes used to add entropy to the session key
            self.salt = os.urandom(8)
        except NotImplementedError:
            self.salt = []
            for i in xrange(8):
                self.salt.append(chr(random.randint(0, 255)))
            self.salt = string.join(self.salt, '')
        self.key = ''
        """A key representing this session in its current state, this key is
		initialised to a random value and changes as each event is received.
		The key must be supplied when triggering subsequent events.  The key is
		designed to be unguessable and unique so a caller presenting the correct
		key when triggering an event can be securely assumed to be the owner of
		the existing session."""
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
        self.EventUpdate(self.key)
        self.cQuestion = 0

    def EventUpdate(self, keyCheck):
        if self.key != keyCheck:
            if keyCheck in self.keyMap:
                raise SessionKeyExpired(keyCheck)
            else:
                raise SessionKeyMismatch(keyCheck)
        if self.key:
            self.keyMap[self.key] = True
            self.prevKey = self.key
            dt = self.t
            self.t = time.time()
            dt = self.t - dt
        else:
            self.t = time.time()
            dt = 0.0
        hash = hashlib.sha224()
        hash.update(self.salt + "%.6f" % self.t)
        self.key = unicode(hash.hexdigest())
        return dt

    def GetCurrentTestPart(self):
        """Returns the current test part or None if the test is finished."""
        q = self.GetCurrentQuestion()
        if q is None:
            return None
        else:
            return q.FindParent(tests.TestPart)

    def GetCurrentQuestion(self):
        """Returns the current question or None if the test is finished."""
        if self.cQuestion is None:
            return None
        else:
            return self.test.GetPart(self.form[self.cQuestion])

    def _BranchTarget(self, qPos):
        id = self.form[qPos]
        if id[0] == u"-":
            id = id[1:]
        q = self.test.GetPart(id)
        target = q.GetBranchTarget(self)
        if target is None:
            return qPos + 1
        elif target == u"EXIT_TEST":
            return len(self.form)
        else:
            qPos = qPos + 1
            while True:
                if qPos >= len(self.form):
                    return qPos
                id = self.form[qPos]
                if target == id:
                    return qPos
                qPos = qPos + 1
                # handle the other special identifiers which move to the point just
                # after the end of the part being exited
                if id[0] == u"-":
                    if target == u"EXIT_SECTION":
                        return qPos
                    elif target == u"EXIT_TESTPART" and isinstance(self.test.GetPart(id[1:]), tests.TestPart):
                        return qPos

    def _NextQuestion(self):
        if self.cQuestion is None:
            # we've finished
            return
        elif self.cQuestion is 0:
            # We need to find the first question
            iQ = 1
        else:
            # we're currently pointing at an assessmentItemRef
            iQ = self._BranchTarget(self.cQuestion)
        while iQ is not None:
            # What type of thing is iQ?
            if iQ >= len(self.form):
                # we've run out of stuff, that was the end of the test.
                self.cQuestion = None
                break
            # check for preConditions
            id = self.form[iQ]
            if id[0] == u"-":
                # end of a section or test part
                iQ = self._BranchTarget(iQ)
            else:
                # check preconditions
                part = self.test.GetPart(id)
                if part.CheckPreConditions(self):
                    if isinstance(part, tests.TestPart):
                        # descend in to this testPart
                        iQ = iQ + 1
                        if part.navigationMode == tests.NavigationMode.nonlinear:
                            # evaluate templateDefaults for all items in this
                            # part
                            endId = u"-" + part.identifier
                            jQ = iQ
                            while jQ <= len(self.form):
                                id = self.form[jQ]
                                if id == endId:
                                    break
                                if id[0] != u"-":
                                    jPart = self.test.GetPart(id)
                                    if isinstance(jPart, tests.AssessmentItemRef):
                                        # Now evaluate the template defaults
                                        itemState = self.namespace[jQ]
                                        jPart.SetTemplateDefaults(
                                            itemState, self)
                                        # and pick a clone
                                        itemState.SelectClone()
                                        itemState.BeginSession()
                                jQ = jQ + 1
                    elif isinstance(part, tests.AssessmentSection):
                        # descend in to this section
                        iQ = iQ + 1
                    elif isinstance(part, tests.AssessmentItemRef):
                        # we've found the next question
                        testPart = part.FindParent(tests.TestPart)
                        if testPart.navigationMode == tests.NavigationMode.linear:
                            itemState = self.namespace[iQ]
                            part.SetTemplateDefaults(itemState, self)
                            itemState.SelectClone()
                            itemState.BeginSession()
                        self.cQuestion = iQ
                        break
                else:
                    # skip this item
                    iQ = iQ + 1

    def BeginSession(self, key, htmlParent=None):
        """Called at the start of a test session.  Represents a 'Start Test' event.

        The main purpose of this method is to set the outcome values to their
        defaults and to select the first question."""
        # ignore any time elapsed between construction and beginSession
        self.EventUpdate(key)
        # sets the default values of all outcome variables
        self.SetOutcomeDefaults()
        self.namespace[0]['duration'].value = 0.0
        self._NextQuestion()
        div, form = self.CreateHTMLForm(htmlParent)
        if self.cQuestion:
            id = self.form[self.cQuestion]
            itemState = self.namespace[self.cQuestion]
            itemDiv = itemState.BeginAttempt(form)
        else:
            # this test had no questions: end screen
            id = None
            pass
        self.AddHTMLNavigation(form)
        return div

    def HandleEvent(self, params, htmlParent=None):
        # seek out the action
        if "SAVE" in params:
            return self.SaveSession(params["SAVE"], params, htmlParent)
        elif "SUBMIT" in params:
            return self.SubmitSession(params["SUBMIT"], params, htmlParent)
        else:
            raise SessionActionMissing

    def SaveSession(self, key, params, htmlParent=None):
        dt = self.EventUpdate(key)
        # Now add the accumulated time to the various durations
        self.AddDuration(dt)
        div, form = self.CreateHTMLForm(htmlParent)
        # Now go through params and look for updated values
        if self.cQuestion:
            itemState = self.namespace[self.cQuestion]
            itemState.SaveSession(params, form)
        else:
            pass
        self.AddHTMLNavigation(form)
        return div

    def SubmitSession(self, key, params, htmlParent=None):
        dt = self.EventUpdate(key)
        # Now add the accumulated time to the various durations
        self.AddDuration(dt)
        div, form = self.CreateHTMLForm(htmlParent)
        # Now go through params and look for updated values
        if self.cQuestion:
            id = self.form[self.cQuestion]
            part = self.test.GetPart(id)
            testPart = part.FindParent(tests.TestPart)
            # so what type of testPart are we in?
            if testPart.navigationMode == tests.NavigationMode.linear:
                if testPart.submissionMode == tests.SubmissionMode.individual:
                    itemState = self.namespace[self.cQuestion]
                    itemState.SubmitSession(params)
                else:
                    # simultaneous submission means we save the current values
                    # then run through all questions in this part submitting the saved
                    # values - it still happens at the end of the test part
                    itemState = self.namespace[self.cQuestion]
                    itemState.SaveSession(params)
                    raise NotImplementedError
                # Now move on to the next question
                self._NextQuestion()
            else:
                # nonlinear mode
                raise NotImplementedError
        else:
            pass
        if self.cQuestion:
            id = self.form[self.cQuestion]
            itemState = self.namespace[self.cQuestion]
            itemDiv = itemState.BeginAttempt(form)
        else:
            # this test had no questions: end screen
            id = None
            pass
        self.AddHTMLNavigation(form)
        return div

    def CreateHTMLForm(self, htmlParent=None):
        if htmlParent:
            div = htmlParent.ChildElement(html.Div)
        else:
            div = html.Div(None)
        form = div.ChildElement(html.Form)
        form.method = html.Method.POST
        return div, form

    def AddHTMLNavigation(self, form):
        # Now add the navigation
        nav = form.ChildElement(html.Div)
        nav.styleClass = "navigation"
        save = nav.ChildElement(html.Button)
        save.type = html.ButtonType.submit
        save.name = "SAVE"
        save.value = self.key
        save.AddData("_save")
        # Now we need to add the buttons that apply...
        if self.cQuestion:
            id = self.form[self.cQuestion]
            part = self.test.GetPart(id)
            testPart = part.FindParent(tests.TestPart)
            # so what type of testPart are we in?
            if testPart.navigationMode == tests.NavigationMode.linear:
                if testPart.submissionMode == tests.SubmissionMode.individual:
                    # going to the next question is a submit
                    submit = nav.ChildElement(html.Button)
                    submit.type = html.ButtonType.submit
                    submit.name = "SUBMIT"
                    submit.value = self.key
                    submit.AddData("_next")
                else:
                    raise NotImplementedError
            else:
                raise NotImplementedError
        else:
            save.disabled = True
        return nav

    def AddDuration(self, dt):
        iQ = self.cQuestion
        ignore = 0
        if iQ:
            # we have a question, add to the duration
            self.namespace[iQ]["duration"].value += dt
            iQ = iQ - 1
            ignore = 0
            while iQ > 0:
                id = self.form[iQ]
                if id[0] == "-":
                    ignore += 1
                else:
                    part = self.test.GetPart(id)
                    if isinstance(part, (tests.AssessmentSection, tests.TestPart)):
                        if ignore:
                            ignore = ignore - 1
                        else:
                            # This must be an open section or test part
                            v = self.namespace[iQ]["duration"]
                            if v:
                                v.value += dt
                            else:
                                v.SetValue(dt)
                iQ = iQ - 1
            # Finally, add to the total test duration
            self.namespace[0]["duration"].value += dt
        else:
            # we've finished the test, don't count time
            pass

    def GetNamespace(self, varName):
        """Takes a variable name *varName* and returns a tuple of namespace/varName.

        The resulting namespace will be a dictionary or a dictionary-like object
        from which the value of the returned varName object can be looked up."""
        splitName = varName.split('.')
        if len(splitName) == 1:
            return self.namespace[0], varName
        elif len(splitName) > 1:
            nsIndexList = self.form.find(splitName[0])
            if nsIndexList:
                # we can only refer to the first instance when looking up
                # variables
                ns = self.namespace[nsIndexList[0]]
                return ns, string.join(splitName[1:], '.')
        print "Looking for: " + varName
        print self.namespace
        print self.form.components
        raise KeyError(varName)

    def GetDeclaration(self, varName):
        ns, name = self.GetNamespace(varName)
        if isinstance(ns, ItemSessionState):
            return ns.GetDeclaration(name)
        elif ns:
            if name in ns:
                # a test level variable
                return self.test.GetDeclaration(name)
            else:
                raise KeyError(varName)
        else:
            # attempt to look up an unsupported namespace
            raise NotImplementedError

    def IsResponse(self, varName):
        """Return True if *varName* is the name of a response variable.  The
        test-level duration values are treated as built-in responses and return
        True."""
        ns, name = self.GetNamespace(varName)
        if isinstance(ns, ItemSessionState):
            return ns.IsResponse(name)
        elif ns:
            # duration is the only test-level response variable
            return name == u'duration'
        else:
            # attempt to look up an unsupported namespace
            raise NotImplementedError

    def SetOutcomeDefaults(self):
        for od in self.test.OutcomeDeclaration:
            self.namespace[0][od.identifier] = v = od.GetDefaultValue()
            if not v:
                if v.Cardinality() == Cardinality.single:
                    if v.baseType == BaseType.integer:
                        v.SetValue(0)
                    elif v.baseType == BaseType.float:
                        v.SetValue(0.0)

    def __len__(self):
        """Returns the total length of all namespaces combined."""
        total = 0
        for ns in self.namespace:
            if ns is None:
                continue
            else:
                total = total + len(ns)
        return total

    def __getitem__(self, varName):
        """Returns the :py:class:`Value` instance corresponding to *varName* or
        raises KeyError if there is no variable with that name."""
        ns, name = self.GetNamespace(varName)
        if ns:
            return ns[name]
        print "Looking for: " + varName
        print self.namespace
        print self.form.components
        raise KeyError(varName)

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

    def __contains__(self, varName):
        try:
            v = self[varName]
            return True
        except KeyError:
            return False
