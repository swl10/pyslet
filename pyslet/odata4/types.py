#! /usr/bin/env python

import collections
from copy import copy
import weakref

from . import errors

from .. import rfc2396 as uri
from ..py2 import (
    BoolMixin,
    force_text,
    is_text,
    SortableMixin,
    to_text,
    UnicodeMixin,
    )
from ..xml import xsdatatypes as xsi


_simple_identifier_re = xsi.RegularExpression(
    "[\p{L}\p{Nl}_][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")


def simple_identifier_from_str(src):
    """Returns src if it is a simple identifier

    Otherwise raises ValueError."""
    if src and len(src) <= 128 and _simple_identifier_re.match(src):
        return src
    else:
        raise ValueError("Bad simple identifier: %s" % src)


class QualifiedName(
        UnicodeMixin,
        collections.namedtuple('QualifiedName', ['namespace', 'name'])):

    """Represents a qualified name

    This is a Python namedtuple consisting of two strings, a namespace
    and a name.  No syntax checking is done on the values at creation.
    When converting to str (and unicode for Python 2) the two components
    are joined with a "." as you'd expect."""

    __slots__ = ()

    def __unicode__(self):
        return force_text("%s.%s" % self)

    @classmethod
    def from_str(cls, src):
        """Parses a QualifiedName from a source string"

        Raises ValueError if src is not a valid QualifiedName."""
        try:
            dot = src.rfind('.')
            parts = src.split(".")
            if len(parts) < 2:
                raise ValueError
            for id in parts:
                simple_identifier_from_str(id)
        except ValueError:
            raise ValueError("Bad qualified name: %s" % src)
        return cls(src[:dot], src[dot + 1:])


class TermRef(
        UnicodeMixin,
        collections.namedtuple('TermRef', ['name', 'qualifier'])):

    """Represents a term reference (including a term cast)

    This is a Python namedtuple consisting of a :class:`QualifiedName`
    instance and a qualifier that is a string or None.  No syntax
    checking is done on the values at creation.  When converting to
    str (and unicode for Python 2) the components are joined as per
    term references, e.g.::

        str(TermRef(QualifiedName('Schema', 'Term'), 'Print')) ==
            '@Schema.Term#Print'
    """

    __slots__ = ()

    def __unicode__(self):
        n, q = self
        if q is None:
            return force_text("@%s" % to_text(n))
        else:
            return force_text("@%s#%s" % (to_text(n), q))

    @classmethod
    def from_str(cls, src):
        """Parses a TermRef from a source string"

        Raises ValueError if src is not a valid TermRef."""
        try:
            if not src or src[0] != '@':
                raise ValueError
            hash = src.rfind('#')
            if hash < 0:
                return cls(name=QualifiedName.from_str(src[1:]),
                           qualifier=None)
            else:
                return cls(
                    name=QualifiedName.from_str(src[1:hash]),
                    qualifier=simple_identifier_from_str(src[hash + 1:]))
        except ValueError:
            raise ValueError("Bad term cast or reference: %s" % src)


def path_to_str(path):
    """Simple function for converting a path to a string

    path
        An array of strings and/or :class:`QualifiedName` or
        :class:`TermRef` named tuples.

    Returns a simple string representation with all components
    separated by "/"
    """
    return "/".join([to_text(segment) for segment in path])


def path_from_str(src):
    """Simple function for converting a string to a path

    src
        A text string

    Returns a (possibly empty) tuple of simple identifiers,
    QualifiedName or TermRef segments."""
    if not src:
        return tuple()
    segments = []
    for segment in src.split('/'):
        if segment.startswith('@'):
            segment = TermRef.from_str(segment)
        elif '.' in segment:
            segment = QualifiedName.from_str(segment)
        else:
            segment = simple_identifier_from_str(segment)
        segments.append(segment)
    return tuple(segments)


annotation_path_to_str = path_to_str
#: synonym for path_to_str


def annotation_path_from_str(src):
    """Simple function for converting a string to an annotation path

    src
        A text string

    Returns a non-empty tuple of simple identifiers, QualifiedName or
    TermRef segments guaranteeing that the last segment is a TermRef."""
    apath = path_from_str(src)
    if not len(apath) or not isinstance(apath[-1], TermRef):
        raise ValueError("Bad AnnotationPath: %s" % src)
    return apath


class EnumLiteral(
        UnicodeMixin,
        collections.namedtuple('EnumLiteral', ['qname', 'value'])):

    """Represents the literal representation of an enumerated value.

    Enumeration literals consist of a :class:`QualifiedName` (used to
    interpret the value at a later time) and a tuple of string
    identifiers or integers."""

    __slots__ = ()

    def __unicode__(self):
        return force_text(
            "%s'%s'" %
            (self.qname, ','.join(to_text(v) for v in self.value)))

    def to_xml_str(self):
        for v in self.value:
            if not is_text(v):
                # it's not clear why but this is not allowed
                raise ValueError
        return force_text(" ".join(['%s/%s' % (to_text(self.qname), v)
                                    for v in self.value]))

    @classmethod
    def from_str(cls, src):
        try:
            apos = src.find("'")
            qname = QualifiedName.from_str(src[:apos])
            vstr = src[apos + 1:-1]
            if not vstr or not src.endswith("'"):
                raise ValueError
            parts = vstr.split(",")
            values = []
            for v in parts:
                if v.isdigit():
                    values.append(int(v))
                else:
                    values.append(simple_identifier_from_str(v))
        except ValueError:
            raise ValueError("Bad enum literal: %s" % src)
        return cls(qname=qname, value=tuple(values))

    @classmethod
    def from_xml_str(cls, src):
        try:
            qname = None
            values = []
            parts = src.split()
            for v in parts:
                slash = v.find("/")
                new_qname = QualifiedName.from_str(v[:slash])
                if qname is None:
                    qname = new_qname
                elif qname != new_qname:
                    raise ValueError
                values.append(simple_identifier_from_str(v[slash + 1:]))
            if not values:
                raise ValueError
        except ValueError:
            raise ValueError("Bad enum xml literal: %s" % src)
        return cls(qname=qname, value=tuple(values))


class Named(UnicodeMixin):

    """An abstract class for a named object

    For more information see :class:`NameTable`."""

    def __init__(self):
        #: the name of this object, set by :meth:`declare`
        self.name = None
        #: a weak reference to the nametable in which this object was
        #: first declared (or None if the object has not been declared)
        self.nametable = None
        #: the qualified name of this object (if declared) as a string
        self.qname = None

    def __unicode__(self):
        if self.qname is not None:
            return self.qname
        else:
            return type(self).__name__

    def is_owned_by(self, nametable):
        """Checks the owning NameTable

        A named object may appear in multiple nametables, a Schema
        may be defined in one entity model (the owner) but referenced in
        other entity models.  This method returns True if the nametable
        argument is the nametable in which the named object was first
        declared (see :meth:`declare`)."""
        return self.nametable is not None and self.nametable() is nametable

    def declare(self, nametable, name):
        """Declares this object in the given nametable

        The first time a model element is declared the object's :attr:`name`
        and :attr:`qname` are set along with the owning :attr:`nametable`.

        Subsequent declarations represent aliases and do not change the
        object's attributes::

            schema.declare(model, "my.long.schema.namespace")
            # assign the alias 'mlsn'
            schema.declare(model, "mlsn")
            # declare in a different model
            schema.declare(model2, "my.long.schema.namespace")
            schema.name == "my.long.schema.namespace"   # True
            schema.nametable() is model                 # True
        """
        if self.nametable is None:
            if name is None:
                raise ValueError("%s declared with no name" % repr(self))
            # this declaration may trigger callbacks so we need to set
            # the owner now, even if the declaration later fails.
            self.nametable = weakref.ref(nametable)
            self.name = name
            self.qname = nametable.qualify_name(name)
            try:
                nametable[name] = self
            except:
                self.nametable = None
                self.name = None
                self.qname = None
                raise
        else:
            nametable[name] = self

    def root_nametable(self):
        """Returns the root table of a nametable hierarchy

        Uses the :attr:`nametable` attribute to trace back through a
        chain of containing NameTables until it finds one that has not
        itself been declared.

        If this object has not been declared then None is returned."""
        if self.nametable is None:
            return None
        else:
            n = self
            while n.nametable is not None:
                n = n.nametable()
            return n


class NameTable(Named, collections.MutableMapping):

    """Abstract class for managing tables of declared names

    Derived types behave like dictionaries (using Python's built-in
    MutableMapping abstract base class).  Names can only be defined
    once, they cannot be undefined and their corresponding values cannot
    be modified.

    To declare a value use the :meth:`Named.declare` method.  Direct use
    of dictionary assignment declares an alias only (the declare method
    of a Named object will automaticaly declare an alias if the object
    has already been declared).  Names (keys) and values are checked on
    assignment using methods that must be implemented in derived classes.

    NameTables define names case-sensitively in accordance with the
    OData specification.

    NameTables are created in an open state, in which they will accept
    new declarations.  They can also be closed, after which they will
    not accept any new declarations (raising
    :class:`NameTabelClosedError` if you attempt to assign or modify a
    new key).  Model objects typically remain open during the model
    creation process (i.e., while parsing metadata files) and are closed
    before they can be used to access data using a data service.  The
    act of closing a model object may fail if model violations are
    detected."""

    def __init__(self, **kwargs):
        self._name_table = {}
        #: whether or not this name table is closed
        self.closed = False
        self._callbacks = {}
        self._close_callbacks = []
        super(NameTable, self).__init__(**kwargs)

    def __getitem__(self, key):
        return self._name_table[key]

    def __setitem__(self, key, value):
        if self.closed:
            raise errors.NameTableClosed(to_text(self.name))
        if key in self._name_table:
            raise errors.DuplicateNameError("%s in %s" % (key, to_text(self)))
        self.check_name(key)
        self.check_value(value)
        self._name_table[key] = value
        for c in self._callbacks.pop(key, []):
            c(value)

    def __delitem__(self, key):
        raise errors.UndeclarationError("%s in %s" % (key, to_text(self.name)))

    def __iter__(self):
        return iter(self._name_table)

    def __len__(self):
        return len(self._name_table)

    def check_name(self, name):
        """Abstract method to check validity of a name

        This method must raise ValueError if name is not a valid name
        for an object in this name table."""
        raise NotImplementedError

    def qualify_name(self, name):
        """Returns the qualified version of a name

        By default we qualify name by prefixing with the name of this
        NameTable and ".", if this NameTable has not been declared then
        name is returned unchanged."""
        if self.name:
            return self.name + "." + name
        else:
            return name

    def check_value(self, value):
        """Abstract method to check validity of a value

        This method must raise TypeError or ValueError if value is not a
        valid item for this type of name table."""
        raise NotImplementedError

    def tell(self, name, callback):
        """Deferred name lookup.

        Equivalent to::

            callback(self[name])

        *except* that if name is not yet defined it waits until name is
        defined before calling the callback.  If the name table is
        closed without name then the callback is called passing None."""
        value = self.get(name, None)
        if value is not None or self.closed:
            callback(value)
        else:
            callback_list = self._callbacks.setdefault(name, [])
            callback_list.append(callback)

    def tell_close(self, callback):
        """Notification of closure

        Calls callback (with no arguments) when the name table is
        closed.  This call is made after all unsuccessful notifications
        registered with :meth:`tell` have been made.

        If the table is already closed then callback is called
        immediately."""
        if self.closed:
            callback()
        else:
            self._close_callbacks.append(callback)

    @staticmethod
    def tell_all_closed(nametables, callback):
        """Notification of multiple closures

        Calls callback (with no arguments) when all the name tables in
        the nametables iterable are closed."""
        i = iter(nametables)

        def _callback():
            try:
                nt = next(i)
                # yes, it's OK to call ourselves here!
                nt.tell_close(_callback)
            except StopIteration:
                callback()

        _callback()

    def close(self):
        """closes this name table

        Any failed notification callbacks registered will :meth:`tell`
        are triggered followed by all notification callbacks registered
        with :meth:`tell_close`.  It is safe to call close on a name
        table that is already closed (callbacks are only ever called the
        first time) or even on one that is *being* closed.  In the
        latter case no action is taken, essentially the table is closed
        immediately, new declarations will fail and any calls to tell
        and tell_close made during queued callbacks will invoke the
        passed callback directly and nested calls to close itself do
        nothing."""
        if not self.closed:
            self.closed = True
            cbs = list(self._callbacks.values())
            self._callbacks = {}
            for callback_list in cbs:
                for c in callback_list:
                    c(None)
            cbs = self._close_callbacks
            self._close_callbacks = []
            for c in cbs:
                c()

    def _reopen(self):
        # reopens this name table (for unit testing only)
        self.closed = False
        self._callbacks = {}
        self._close_callbacks = []

    simple_identifier_re = xsi.RegularExpression(
        "[\p{L}\p{Nl}_][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}")

    @classmethod
    def is_simple_identifier(cls, identifier):
        """Returns True if identifier is a valid SimpleIdentifier"""
        return (identifier is not None and
                cls.simple_identifier_re.match(identifier) and
                len(identifier) <= 128)

    @classmethod
    def is_namespace(cls, identifier):
        """Returns True if identifier is a valid namespace name"""
        if identifier is None:
            return False
        parts = identifier.split(".")
        for id in parts:
            if not cls.is_simple_identifier(id):
                return False
        return True

    @classmethod
    def is_qualified_name(cls, identifier):
        """Returns True if identifier is a valid qualified name"""
        if identifier is None:
            return False
        parts = identifier.split(".")
        if len(parts) < 2:
            return False
        for id in parts:
            if not cls.is_simple_identifier(id):
                return False
        return True


def get_path(src):
    if is_text(src):
        if not src:
            return []
        src = src.split('/')
        i = 0
        while i < len(src):
            p = src[i]
            if "." in p:
                src[i] = QualifiedName.from_str(p)
            i += 1
        return tuple(src)
    else:
        return tuple(src)


class Annotatable(object):

    """Abstract class for model elements that can be annotated"""

    csdl_name = "Undefined"

    def __init__(self, **kwargs):
        super(Annotatable, self).__init__(**kwargs)
        self.annotations = Annotations()

    def annotate(self, a):
        """Annotate this element with an annotation

        a
            A :class:`Annotation` instance."""
        try:
            a.declare(self.annotations)
        except errors.DuplicateNameError:
            raise errors.DuplicateNameError(
                errors.Requirement.annotations_s %
                to_text(a.get_term_ref()))


class Term(Annotatable, Named):

    """Represents a defined term in the OData model

    In many ways Annotations can be thought of as custom property values
    associated with an object and Terms can be thought of as custom
    property definitions.  Like property definitions, they have an
    associated type that can be called to create a new :class:`Value`
    instance of the correct type for the Term."""

    csdl_name = "Term"

    def __init__(self, **kwargs):
        super(Term, self).__init__(**kwargs)
        #: the type definition for values of this property
        self.type_def = None
        #: the base term of this term
        self.base = None
        #: whether or not the term can be null (or contain null in the
        #: case of a collection)
        self.nullable = True
        #: the default value of the term (primitive/enums only)
        self.default_value = None
        #: a list of element names that the term can be applied to
        self.applies_to = []

    def set_type(self, type_def):
        self.type_def = type_def

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_default(self, default_value):
        self.default_value = default_value

    def set_base(self, base):
        self.base = base

    def set_applies_to(self, elements):
        self.applies_to = elements

    def get_default(self):
        """Returns the default value

        The return value is a *copy* of the default, so it is not frozen
        and can be modified if necessary by the caller at a later date.
        If there is no default then a null value of the Term's type is
        returned instead."""
        result = self.type_def()
        if self.default_value is not None:
            result.assign(self.default_value)
        return result


class Annotations(NameTable):

    """The set of Annotations applied to a model element.

    A name table that contains :class:`Annotation` instances keyed on an
    instance of :class:`TermRef` that refers to the defining term.

    To give an example::

        @Org.OData.Core.V1.Description#en

    The qualified name of the annotation is the name of a defined Term,
    in this case "Description" in the "Org.OData.Core.V1" namespace.
    The qualifier "en" has been added, perhaps to indicate that the
    language used is "English".

    The specification draws attention to the wide applicability of
    annotations though:

        As the intended usage may evolve over time, clients SHOULD be
        prepared for any annotation to be applied to any element

    As a result, we use the :class:`Annotatable` class liberally in the
    model."""

    def check_name(self, name):
        """Checks that name is of type :class:`TermRef`.

        Raises ValueError if the name is not valid (or is None)."""
        if name is None:
            raise ValueError("Annotation with no name")
        if not isinstance(name, TermRef):
            raise ValueError(
                "%s is not a valid term reference" % to_text(name))

    def qualify_name(self, name):
        """Returns the qualified version of a name

        Simply returns the string representation of the name (a
        :class:`TermRef`) as the name is already qualified."""
        return to_text(name)

    def check_value(self, value):
        if not isinstance(value, Annotation):
            raise TypeError(
                "Annotation required, found %s" % repr(value))

    def qualified_get(self, term, qualifier=None, default=None):
        """Looks up an annotation

        term
            The qualified name of an annotation Term as a *string*

        qualifier
            An optional qualifier to search for, if None then
            the definition with an empty qualifier is returned.

            The qualifier may also be an iterable of qualifiers in
            preference order.  For example::

                annotations.qualified_get(
                    "Org.OData.Core.V1.Description", ("de", "en", ""))

            Extending the example above, this call might be used to
            search for a German language string, failing that an English
            language string, failing that a string with unspecified
            language.

        default (None)
            The value to return if the annotation is not found."""
        qname = QualifiedName.from_str(term)
        if not qualifier:
            qualifier = (None, )
        elif is_text(qualifier):
            qualifier = (qualifier, )
        for q in qualifier:
            try:
                return self[TermRef(qname, q if q else None)]
            except KeyError:
                continue
        return default


class Annotation(Named):

    """An Annotation (applied to a model element).

    The name of this object is a :class:`TermRef` tuple that refers to
    the term that defines this annotation's type.

    This package divides Annotations into two types.  Annotations
    declared in the schema (metadata) and applied to model elements
    declared there; such as EntityTypes, EntitySets, etc.; are
    represented by instances of this class.  Annotations applied to
    :class:`Value` instances are simply :class:`Value` instances
    themselves.  Effectively annotations applied to values are just
    special property values with @ qualified names (and optional #
    qualifiers) with a type declared by a Term.

    Instead of :class:`Value` instances, Annotations contain
    *expressions* that evaluate to :class:`Value` instances.  These
    expressions may be constant or dynamic expressions.  In the case of
    dynamic expressions the expression is evaluated when it is applied
    to the target Value.  An example will help.

    Suppose we have an EntityType called 'Product' with simple
    properties ProductName and ProdoctType.  The following Annotation
    might be applied to the EntityType in the metadata model::

        <Annotation Term="org.example.display.DisplayName">
            <Apply Function="odata.concat">
                <Path>ProductName</Path>
                <String>: </String>
                <Path>ProductType</Path>
            </Apply>
        </Annotation>

    The Annotation instance object representing this annotation will
    contain an expression equivalent to the inline expression::

        concat(ProductName, concat(': ', ProductType))

    The value of this expression is only meaningful when it is evaluated
    in the context of a specific entity instance.  Therefore, the
    Annotation element applied to the Product entity type contains the
    expression and not a value.

    A specific instance of this type behaves as if had the following
    JSON representation::

        {
            "ProductName": "Punch",
            "ProductType": "Magazine",
            "@org.example.display.DisplayName": "Punch: Magazine"
        }

    The annotation has been applied to the instance and evaluated to its
    string value.  In practice though, you don't see the annotation
    explicitly applied to the serialized form of the entity.  The
    purpose of applying annotations (as expressions) to the ProductType
    is to enable them to be inferred on the instance by the client.  The
    :meth:`Value.get_annotation` method on Value takes care of this by
    looking for annotation *expressions* applied to a Value's type and
    evaluating them dynamically (client side) to obtain the Value of the
    annotation itself.

    Constant expressions evaluate to the same value for all instances
    of the model element concerned and may be evaluated in the context
    of the model element itself.  For example, the reference Trippin
    service contains the following EntitySet declaration::

        <EntitySet Name="Airlines"
            EntityType=
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models.Airline">
            <Annotation Term="Org.OData.Core.V1.OptimisticConcurrency">
                <Collection>
                    <PropertyPath>Name</PropertyPath>
                </Collection>
            </Annotation>
        </EntitySet>

    The subtle difference here is that a PropertyPath value literally
    evaluates to the path (i.e, 'Name') and not the Name value of any
    specific instance.  The intent here is to provide a list of
    properties that are used to compute the ETag for an Airline, the
    same list will apply to all Airline instances.  The
    :meth:`Annotatable.get_annotation` method on Annotatable takes care
    of this, evaluating constant expressions without requiring a
    contextual instance Value."""

    csdl_name = "Annotation"

    def __init__(self, term, qualifier=None, **kwargs):
        super(Annotation, self).__init__(**kwargs)
        if term is None or term.name is None:
            raise ValueError(
                "Qualified annnotation with no declared term")
        #: a weak reference to the term that defines this annotation we
        #: use a weak reference to prevent cycles because Terms can also
        #: be annotated, even with themselves!  Witness Core.Description
        #: that is annotated with a self-referential description.
        self.term = weakref.ref(term)
        #: the qualifier associated with this annotation or None if the
        #: annotation has no qualifier.
        self.qualifier = qualifier
        #: the expression that defines this annotation's value
        self.expression = None

    def set_expression(self, expression):
        """Sets the expression for this annotation

        By default Annotations have no expression and will evaluate to
        the default value of the Term that defines them.  If an
        expression is provided it may be a constant or dynamic
        expression but evaluation is always deferred until the value
        of the annotation is looked up."""
        self.expression = expression

    def get_term_ref(self):
        """Returns a :class:`TermRef` tuple for this annotation"""
        return TermRef(name=QualifiedName.from_str(self.term().qname),
                       qualifier=self.qualifier)

    def declare(self, nametable, name=None):
        """Declares this annotation in an Annotations nametable

        This method is overridden as, unlike other Named objects,
        Annotation instances do not support aliasing and have
        predetermined names based on the :attr:`term` and
        :attr:`qualifier` attributes

        The name parameter is made optional and is provided only for
        consistency (when using super) and should be omitted.  If
        specified it must be a TermRef that matches the calculated
        value."""
        tref = self.get_term_ref()
        if name is not None and name != tref:
            raise ValueError(
                "Annotation declaration mismatch: %s declared as %s" %
                (to_text(tref), to_text(name)))
        super(Annotation, self).declare(nametable, tref)

    @classmethod
    def split_json_name(cls, name):
        """Splits a JSON encoded annotation name

        Returns a tuple of (target, term_ref).  For example, the
        annotation::

            FirstName@Core.Description#ascii

        would return::

            ("FirstName",
                TermRef(QualifiedName("Core", "Description"), "ascii"))

        The target and qualifier are optional and may be None in the
        result."""
        apos = name.find('@')
        if apos < 0:
            raise ValueError("Annotation name must contain '@': %s" % name)
        elif apos > 0:
            return (
                simple_identifier_from_str(name[:apos]),
                TermRef.from_str(name[apos:]))
        else:
            return (None, TermRef.from_str(name))

    @classmethod
    def from_term_ref(cls, term_ref, context):
        """Creates a new instance from a qualified name and context

        term_ref
            A :class:`TermRef` instance or a string from which one can
            be parsed.

        context
            The entity model within which to look up the associated
            term definition.

        Returns an Annotation instance or None if the definition of the
        term could not be found."""
        # lookup qname in the context
        if is_text(term_ref):
            term_ref = TermRef.from_str(term_ref)
        term = context.qualified_get(term_ref.name)
        if not isinstance(term, Term):
            return None
        return cls(term, qualifier=term_ref.qualifier)


class NominalType(Annotatable, Named):

    """A Nominal Type

    In Pyslet, all defined types are represented in the model by
    *instances* of NominalType.  Nominal types all have a :attr:`name`
    and typically a base type.

    NominalType instances are callable, returning a :class:`Value`
    instance of an appropriate class for representing a value of the
    type.  The instance returned is a null value of this of type.  When
    calling a type object you *may* pass an optional service argument to
    bind the value to a specific :class:`service.DataService`."""

    def __init__(self, **kwargs):
        super(NominalType, self).__init__(**kwargs)
        #: the base type (may be None for built-in abstract types)
        self.base = None
        # the class used for values of this type
        self.value_type = Value
        #: whether or not this type is abstract
        self.abstract = False
        #: the service this type is bound to
        self.service_ref = None

    def __unicode__(self):
        if self.qname is not None:
            return self.qname
        elif self.base is not None:
            # an undeclared type, return the string representation of
            # the base type
            return to_text(self.base)
        else:
            # undeclared type with no base, should not clash with qnames
            # of other types.
            return "UnknownType"

    def __call__(self, value=None):
        v = self.value_type(type_def=self)
        if value is not None:
            v.set_value(value)
        return v

    def declare(self, nametable, name):
        try:
            super(NominalType, self).declare(nametable, name)
        except ValueError:
            raise ValueError(errors.Requirement.type_name)

    def get_qname(self):
        """Returns a :class:`core.QualifiedName` named tuple"""
        if self.name is None:
            raise errors.ObjectNotDeclaredError
        return QualifiedName(namespace=self.nametable().name, name=self.name)

    def set_abstract(self, abstract):
        self.abstract = abstract

    def set_base(self, base):
        """Sets the base type of this type

        base
            Must be of the correct type to be the base of the current
            instance.

        The default implementation sets :attr:`base` while defending
        against the introduction of inheritance cycles."""
        if base.is_derived_from(self):
            raise errors.InheritanceCycleDetected
        self.base = base

    def bind_to_service(self, service_ref):
        """Binds this type definition to a specific OData service

        service
            A *weak reference* to the service we're binding to."""
        if self.service_ref is not None:
            raise errors.ModelError(
                "%s is already bound to a context" % self.qname)
        self.service_ref = service_ref

    def is_derived_from(self, t, strict=False):
        """Returns True if this type is derived from type t

        strict
            Optional flag determining the behaviour when t
            is the type itself::

                t.is_derived_from(t, True) is False

            as t is not strictly derived from itself. By default, strict
            mode is off::

                t.is_derived_from(t) is True"""
        curr_type = self
        if not strict and t is self:
            return True
        while curr_type.base is not None:
            curr_type = curr_type.base
            if curr_type is t:
                return True
        return False

    def bases(self):
        """Iterate this class and all it's bases"""
        t = self
        while t is not None:
            yield t
            t = t.base

    def declared_bases(self):
        """Iterate this class (if declared) and all it's declared bases

        Undeclared types are used in situations such as facetted
        restrictions of declared primitive types. This iterator will not
        yield these inominate types.  (Special rules apply for
        collection types, see :class:`model.CollectionType`)."""
        t = self
        while t is not None:
            if t.qname is not None:
                yield t
            t = t.base

    def get_model(self):
        """Returns the model in which this type was declared

        This returns the *model* in which the first
        :meth:`declared_base` was declared.  For collection types it is
        overridden to return the model in which the first declared_base
        of the item type was declared (as collection types are always
        undeclared)."""
        t = self
        while t is not None:
            if t.qname is not None:
                schema = t.nametable()
                return schema.get_model()
        return None

    def get_odata_type_fragment(self):
        """Returns the fragment identifier representing this type

        This fragment can be appended to the URL of the metadata
        document to make the value for the @odata.type annotation for an
        oject.  By implication, you cannot refer to an absract type this
        way (because that type cannot be instantiated as an object) so
        we raise an error for abstract types.

        The default implementation returns #qname if the type has been
        declared (and #name for items in the Edm namespace), otherwise
        it raises ObjectNotDeclaredError."""
        if self.abstract:
            raise errors.ModelError("Abstract type %s has no context URL" %
                                    to_text(self))
        elif self.qname:
            if self.nametable().name == "Edm":
                return "#" + self.name
            else:
                return "#" + self.qname
        else:
            raise errors.ObjectNotDeclaredError

    def get_odata_type_url(self, service=None):
        """Returns an odata.type URL identifier relative to service

        service (None)
            A service to use as a base context.

        If this is the same service that this type is bound to then a
        URI consisting of just the fragment is returned, otherwise a URI
        consisting of this type's service context URL + this type's
        fragment is returned."""
        if self.service_ref is None:
            svc = None
        else:
            svc = self.service_ref()
        if svc is service:
            return uri.URI.from_octets(self.get_odata_type_fragment)
        elif svc is not None:
            return uri.URI.from_octets(
                self.get_odata_type_fragment).resolve(svc.context_base)
        else:
            raise errors.ModelError("%s has no context" % to_text(self))


class Value(BoolMixin, UnicodeMixin):

    """Abstract class to represent a value in OData.

    All values processed by OData classes are reprsented by instances of
    this class.  All values have an associated type definition that
    controls the range of values it can represent (see
    :class:`NominalType` and its sub-classes).

    Values are mutable so cannot be used as dictionary keys (they are
    not hashable).  By default they evaluate to True unless they are
    null, in which case they evaluate to False but you *should* use the
    :meth:`is_null` test when you want to test for null as per the OData
    specification as there are some special cases where the two
    diverge."""

    #: class used for evaluation (set by model module)
    Evaluator = None

    def __init__(self, type_def, **kwargs):
        super(Value, self).__init__(**kwargs)
        #: the type definition that controls the current value space
        self.type_def = type_def
        #: a weak reference to the service we're bound to
        self.service = None
        #: whether or not this value is frozen
        self.frozen = False
        #: whether or not this value has been modified since it was
        #: created or the last call to :meth:`clean`.
        self.dirty = False
        #: if this value is part of a structured type then we keep a
        #: weak reference to the parent value
        self.parent = None
        #: the fully qualified type name of the type that defines this
        #: property if it is of a type derived from the declared type of
        #: our parent's property (not necessarily the same type as our
        #: parent currently is!).
        self.parent_cast = None
        #: the name of this value within the parent (property name)
        self.name = None
        # used internally to cache annotation values
        self._annotations = {}

    __hash__ = None

    def __bool__(self):
        return not self.is_null()

    def __unicode__(self):
        return to_text("%s of type %s" % (
            self.__class__.__name__, to_text(self.type_def.qname)))

    def is_null(self):
        """Returns True if this object is null.

        You can use simple Python boolean evaluation with primitive
        value instances but in general, to test for null as per the
        definition in the specification you should use this method."""
        return True

    def get_value(self):
        """Returns a python 'native' value representation

        The default implementation will return None if the object
        represents a null value."""
        if self.is_null():
            return None
        else:
            raise NotImplementedError

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        This is an abstract method that is overridden in each value
        type."""
        raise NotImplementedError

    def freeze(self):
        """Makes this value read-only

        The interpretation of read only depends on the type but in
        general primitive and enumeration values will become completely
        immutable whereas collections will have the set of values they
        represent fixed but the values themselves are still free to
        change just as a tuple behaves like a frozen list in Python.

        There is no 'thaw' operation, frozen objects are frozen forever
        indicating that attempting to modify them is futile.  For example,
        a value returned by an OData function or action.  A bound value
        that is frozen *may* still change if its value is reloaded from the
        original data service, for example, after a local cached copy
        is cleared."""
        self.frozen = True

    def touch(self):
        """Marks this value as dirty (modified)

        Each time a value is modified using :meth:`set_value` or one of
        the type-specific modification methods the value is marked as
        being modified using the :attr:`dirty` flag. This method sets
        the dirty flag to True explicitly making it dirty.

        In general, if an operation will fail on a frozen value then it
        will set the dirty flag and if it succeeds on a frozen value
        then it will not."""
        self.dirty = True

    def clean(self):
        """Marks this value as clean (unmodified)

        This method sets the dirty flag back to False, 'cleaning' the
        value again."""
        self.dirty = False

    def assign(self, value):
        """Sets this value from another Value instance.

        If value is null then this instance is set to null.  Otherwise
        the incoming value must be of the same type, or a type derived
        from, the object being assigned."""
        if value.is_null():
            self.set_value(None)
        elif value.type_def.is_derived_from(self.type_def):
            self.set_value(value.get_value())
        else:
            raise TypeError(
                "Can't assign %s from %s" %
                (to_text(self.type_def), to_text(value.type_def)))

    def cast(self, type_def):
        """Implements the cast function

        type_def
            An instance of :class:`NominalType`.

        Returns a new instance casting the current value to the type
        specified.  The default implementation implements 3 rules:

            1.  any null value can be cast to another null value
            2.  a value can be cast to a value of the same type
            3.  casting to an abstract type fails (returns null of the
                abstract type)

        Any other cast results in a null value representing a failed
        cast."""
        result = type_def()
        if type_def.abstract:
            result.set_value(None)
        elif self.type_def.is_derived_from(type_def):
            result.assign(self)
        else:
            result.set_value(None)
        return result

    def set_parent(self, parent_ref, name):
        """Sets the parent (owner) of this value.

        A value is owned if it is a named property of another value or,
        it is the result of ."""
        if self.parent is not None:
            raise ValueError("Object already owned")
        self.parent = parent_ref
        p = parent_ref()
        self.name = name
        if name and name not in p.base_def:
            # we weren't declared in the base type of the parent so we
            # need a type cast to the type we were declared in (not
            # necessarily the type of our parent which may be further
            # derived).
            self.parent_cast = p.type_def[name].nametable().qname
        if p.service is not None:
            self.bind_to_service(p.service)

    def get_entity(self, path, ignore_containment=True):
        """Returns the entity that contains this value

        For values with no parent entity, None is returned.  If the
        value is itself an entity then it is returned *unless* it is a
        contained singleton in which case the process continues as for a
        complex value.  Otherwise, the chain of parents is followed
        recursively until an entity or a parentless value is found.

        ..  note:: If this value is an item in a collection of complex
                   values (directly or indirectly) then it will return
                   None as no path exists from the containing entity to
                   the value.

        path
            A list of *strings* that will be updated to represent the
            path to this value by pre-pending the required path segments
            to navigate from the context of the entity returned back to
            this value.   You should pass an empty list.  Note that
            qualified names that appear in the path are represented as
            strings and not QualifiedName tuples.

        ignore_containment (True)
            Set to False to force get_entity to return the first entity
            it finds, even if that entity is a contained singleton.

        For example, if an entity has a complex property with name 'A'
        then calling get_entity on the value of A returns the entity and
        pre-pends 'A' to path.

        More complex situations requiring type-casts are also handled.
        To extend the previous example, if the entity in question is of
        type Y, derived from type X, and is in an entity set or
        collection declared to be of type X *and* the property A is
        defined only for type Y, then a type cast segment is also
        pre-prended when calling get_entity on the property.  The path
        list will then start: ['schema.Y', 'A',...].

        The upshot is that *path* is prefixed with the target path of
        this value. This path could then be used in expressions that
        require a property path."""
        # TODO: traversing entities contained in entity sets (rather
        # than as single entities) does not include the key in the path
        if self.parent is None:
            return None
        p = self.parent()
        if p is None:
            raise errors.ServiceError("Value has expired")
        path.insert(0, self.name)
        if self.parent_cast:
            path.insert(0, self.parent_cast)
        return p.get_entity(path, ignore_containment)

    def bind_to_service(self, service):
        """Binds this value to a specific OData service

        service
            The service we're binding to - note that unlike the similar
            method for types, we are strongly bound to the service
            rather than weakly bound (i.e., with a weak reference).
            This is safe because, unlike types, the service does not
            hold references to bound values.

        There are basically two types of Value instances in Pyslet's
        OData model: bound values that provide a local view of an object
        bound to a shared data service and transient values that are
        not.  (In this sense, a collection might be transient even if
        its items are bound.)  This method binds a value to a service.

        In normal use you won't need to bind values yourself.  All
        values are created transient.  Values are bound automatically by
        the data service when deserlizing data service responses and may
        also be bound as an indirect consequence of an operation.  For
        example, if you create an EntityValue by calling an EntityType
        instance you get a transient entity but if you (successfully)
        insert that entity into a bound EntitySetValue it will become
        bound to the same service as the EntitySetValue as you would
        expect."""
        if self.service is not None:
            raise errors.BoundValue
        self.service = service

    def clear_cache(self):
        """Clears the local cache for this value

        To force the value object to load the object's value from the
        service again next time it is used call this method to clear the
        local cache.  This method does nothing for values of primitive
        or enumeration types as these value types are not composite
        values and so do not use caching.

        This method only affects values that are bound to a service,
        otherwise it does nothing because a value that is not bound to a
        service is transient and the value is *only* stored locally."""
        if self.service is not None:
            raise NotImplementedError

    def reload(self):
        """Reloads this value from the service

        The value must be bound."""
        if self.service is None:
            raise errors.UnboundValue
        raise NotImplementedError

    def get_model(self):
        """Returns the model that contains this value

        If this Value is bound to a service then the model associated
        with the servie is returned.  If unbound, then the model in
        which the Value's type was declared is returned instead.
        Property values use the containing EntityType, not the type of
        the property itself.  In the case of types that are not bound to
        a model at all (such as unbond values of primitive types) then
        None is returned."""
        model = None
        if self.service:
            model = self.service.model
        if model is None:
            entity = self.get_entity(path=[])
            if entity is not None:
                model = entity.type_def.get_model()
        if model is None:
            model = self.type_def.get_model()
        return model

    def get_annotation(self, aname):
        """Looks up an annotation by name

        aname
            A text string that must start with '@' and consist of the
            qualified term name followed by and optional
            #qualifier or an existing :class:`TermRef` instance.

        Returns a (possibly *frozen*) :class:`Value` instance of the
        appropriate type as defined by the Term declaration or None if
        the annotation does not apply to this value.

        Use this method when you want to look up the value of an
        annotation.  If the annotation has not been applied to the value
        directly then annotations applied to the Value's type (or
        declaration) are looked up in the metadata model including the
        evaluation of any dynamic expressions or Term defaults.  The
        resulting instance may be computed from related values or shared
        amongst multiple instances (e.g., in the case of a Term default)
        and so may be frozen to prevent changes.

        If the annotation value is computed from a dynamic expression
        the expression is re-evaluated each time this method is
        called."""
        if is_text(aname):
            aname = TermRef.from_str(aname)
        value = self._annotations.get(aname, None)
        if value is None:
            # TODO: if value is a property value, look up annotations in
            # the property definition too perhaps?
            for t in self.type_def.declared_bases():
                # look up the annotation in the value's type
                a = t.annotations.get(aname, None)
                if a is None:
                    continue
                value = self.Evaluator.evaluate_annotation(a, self).get_value()
                # freeze this value before returning it
                value.freeze()
                break
        return value

    def get_updatable_annotation(self, term, qualifier=None, default=False):
        """Looks up an annotation by name

        term
            The :class:`Term` that defines this annotation

        qualifier (None)
            The optional qualifier to use with this instance of the term.

        default (False)
            Compute a default value for the annotation if it has not had
            a value assigned already.  Otherwise a null value is
            assigned.  (The default is the value that would be returned
            by :meth:`get_annotation``.)

        Returns an updatable :class:`Value` instance of the appropriate
        type as defined by the Term declaration.  The annotation is
        applied to this value if it does not already apply.

        Use this method when you want to set the value of the annotation
        as applied to this value only.  The return value becomes the
        value of this annotation for the remaining life of the Value
        instance and will be returned by all future calls to both this
        method and :meth:`get_annotation`, therefore, updating it
        changes the value of the annotation for this isntance.

        If the annotation value can be computed from the metadata model
        then it will be updated to the computed value before being
        returned only if *default* is True."""
        aname = TermRef(name=QualifiedName.from_str(term.qname),
                        qualifier=qualifier)
        value = self._annotations.get(aname, None)
        if default:
            computed_value = self.get_annotation(aname)
        else:
            computed_value = None
        if value is None:
            # create a new value instance for this term
            value = term.type_def()
            self._annotations[aname] = value
        if computed_value is not None:
            value.assign(computed_value)
        return value

    def remove_updatable_annotation(self, aname):
        """Removes an annotation from this value by name

        aname
            See :meth:`get_annotation`.

        This method removes any updateable annotation applied to this
        specific value.  After this call, get_annotation may still
        return a value if it can be computed from an Annotation
        expression applied to the value's type.

        Use this method to remove an annotation that was applied using
        :meth:`get_updatable_annotation`."""
        if is_text(aname):
            aname = TermRef.from_str(aname)
        self._annotations.pop(aname, None)

    def get_annotations(self, apattern):
        """Looks up a set of annotations by pattern

        apattern
            A pattern that satisfies the syntax for the
            odata.include-annotations Prefer header.  A comma separated
            list of qualified term names with optional #qualifiers that
            may contain the wild card character "*" on its own or after
            a schema name and/or be prefixed with the exclusion
            character "-".

        Returns a dictionary mapping annotation :class:`TermRef` tuples
        onto Value instances.  See :meth:`get_annotation` for further
        information on the way values are calculated."""
        raise NotImplementedError

    def get_callable(self, qname, params=None):
        """Returns a :class:`model.CallableValue` bound to this value

        qname
            The qualified name of the action or function (callable)

        params
            An optional list or iterable of non-binding parameter names
            (strings) used to disambiguate function overloads."""
        if self.service is None:
            raise errors.UnboundValue
        cdef = self.service.model.qualified_get(qname)
        if cdef is None:
            raise KeyError
        if cdef.is_action():
            if params is not None:
                raise errors.ODataError(
                    "Can't use params for action overload resolution")
            c = cdef.resolve(self)
        else:
            c = cdef.resolve(self, params)
        if c is None:
            raise errors.ODataError("No matching callable declared")
        cv = c()
        cv.set_callable_binding(self)
        cv.bind_to_service(self.service)
        return cv


class SelectItem(UnicodeMixin):

    """Object representing a single selected item"""

    def __init__(self):
        self.path = ()
        self.type_cast = None


class PathQualifier(xsi.Enumeration):

    """An enumeration used to represent a path qualifier

    ::

            PathQualifier.count
            PathQualifier.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "count": 1,
        "ref": 2,
        "value": 3,
    }


class ExpandItem(UnicodeMixin):

    """Object representing a single expanded item

    """

    def __init__(self):
        self.path = ()
        self.type_cast = None
        self.qualifier = None
        self.options = ExpandOptions()

    def __unicode__(self):
        value = ["/".join(p for p in self.path)]
        if self.type_cast:
            value.append("/" + to_text(self.type_cast))
        if self.qualifier is not None:
            value.append("/$" + PathQualifier.to_str(self.qualifier))
        if self.options:
            options = to_text(self.options)
            if options:
                value.append("(%s)" % options)
        return "".join(value)

    def clone(self):
        item = ExpandItem()
        item.path = self.path
        item.type_cast = self.type_cast
        item.qualifier = self.qualifier
        item.options = self.options.clone()


class EntityOptions(object):

    """Object representing the options select and expand

    There are two attributes.  The select attribute contains a list of
    :class:`SelectItem` instances that describe the selected properties.
    An empty list indicates no selection rules and is interpreted in the
    same way as a single item list containing the select item "*".

    The expand attribute contains a list of :class:`ExpandItem`
    instances that describe the more complex expansion rules.

    This object contains the valid options that may be specified when
    requesting individual entities."""

    def __init__(self):
        #: the entity model that provides the context for interpreting
        #: qualified names in these options
        self.context = None
        #: a boolean indicated whether or not structural properties are
        #: selected by default (in the absence of an explicit select
        #: rule)
        self.select_default = True
        #: a list of path tuples describing selected properties
        self.select = []
        self._selected = {}
        self._complex_selected = {}
        self._nav_expanded = {}
        #: a list of :class:`ExpandItem` instances contain expansion rules
        self.expand = []

    def clone(self):
        """Creates a new instance forked from this one"""
        options = self.__class__()
        options.select = copy(self.select)
        for item in self.expand:
            self.expand.append(item.clone())
        return options

    def _clear_cache(self):
        self._selected.clear()
        self._complex_selected.clear()
        self._nav_expanded.clear()

    def add_select_path(self, path):
        """Add an additional select path to the options

        path
            A list or other iterable returning identifiers (as strings),
            :class:`QualifiedName` tuples or the special value "*".
            Alternatively, a string is also accepted for convenience and
            this will be split into path components but no syntax
            checking is performed.  For untrusted input you MUST use the
            :class:`parser.Parser` class to parse a selectItem and the
            corresponding :meth:`add_select_item` method instead.

        If the incoming value represents a selected property and ends
        with a qualified name this is a type-cast and it is removed from
        the path and used to set the type_cast attribute of the item."""
        self._clear_cache()
        sitem = SelectItem()
        path = get_path(path)
        if not len(path):
            raise ValueError
        if isinstance(path[-1], QualifiedName) and (
                len(path) > 1 and is_text(path[-2])):
            sitem.type_cast = path[-1]
            path = path[:-1]
        sitem.path = tuple(path)
        self.select.append(sitem)

    def remove_select_path(self, path):
        """Removes a select item from these options

        path
            See :meth:`add_select_path` for details.

        If there is no matching select item no action is taken."""
        path = get_path(path)
        if not len(path):
            raise ValueError
        if isinstance(path[-1], QualifiedName):
            path = path[:-1]
            if not len(path):
                raise ValueError
        path = tuple(path)
        i = 0
        while i < len(self.select):
            if self.select[i].path == path:
                del self.select[i]
            else:
                i += 1

    def add_select_item(self, item):
        """Add an additional select item to the options

        item
            A :class:`SelectItem` instance such as would be returned
            from the parser when parsing the $select query option."""
        if isinstance(item, SelectItem):
            self._clear_cache()
            self.select.append(item)
        else:
            raise ValueError

    def clear_select(self):
        """Removes all select items from the options"""
        self.select = []
        self._clear_cache()

    def selected(self, qname, pname, nav=False):
        """Returns True if this property is selected

        qname
            A string, QualifiedName instance or None if the property is
            defined on the base type of the object these options apply
            to.

        pname
            A string.  The property name.

        nav
            A boolean (default False): the property is a navigation
            property.

        Tests the select rules for a match against a specified property.
        Set the optional nav to True to indicate that pname is the name
        of a navigation property: the result will then be True only if
        an explicit rule matches the item.

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property are efficient."""
        if not self.select:
            # no select means select default structural properties
            return not nav and self.select_default
        if is_text(qname):
            qname = QualifiedName.from_str(qname)
        result = self._selected.get((qname, pname), None)
        if result is not None:
            return result
        result = False
        for rule in self.select:
            # do we match this select rule?  We can ignore type
            # casts as they don't apply to primitive properties
            path = rule.path
            if not path:
                # an empty select rule is ignored (shouldn't happen)
                continue
            p = path[0]
            if p == "*":
                # * matches all structural properties, including us
                if not nav:
                    result = True
                break
            if qname:
                if not isinstance(p, QualifiedName) or p != qname:
                    continue
                p = path[1]
                maxlen = 2
            else:
                maxlen = 1
            if p == pname:
                if len(path) > maxlen:
                    raise errors.PathError(
                        "Unexpected complex property path: %s" %
                        path_to_str(path))
                result = True
                break
        self._selected[(qname, pname)] = result
        return result

    def add_expand_path(self, path, qualifier=None, options=None):
        """Add an additional expand item to these options

        path
            See :meth:`add_select_path` for details.  The string
            MUST NOT contain a trailing qualifer as this is set
            separately.

        qualifier
            One of the :class:`PathQualifier` values ref or count
            or None for no qualification (the default).

        options
            A :class:`ExpandOptions` instance controlling the options to
            apply to the expanded navigation property.  Defaults to None
            in which case a default set of options apply (including the
            default select rule that selects a default, typically all,
            structural properties).

        If there is already an expand rule for this path it is replaced.
        Returns the new :class:`ExpandItem`."""
        xitem = ExpandItem()
        path = get_path(path)
        if not len(path):
            raise ValueError
        if isinstance(path[-1], QualifiedName):
            xitem.type_cast = path[-1]
            path = path[:-1]
            if not len(path):
                raise ValueError
        xitem.path = tuple(path)
        xitem.qualifier = qualifier
        if options is not None:
            # override the default set of (empty) options
            xitem.options = options
        self.add_expand_item(xitem)
        return xitem

    def remove_expand_path(self, path):
        """Removes an expand item from these options

        path
            See :meth:`add_select_path` for details.  The string
            MUST NOT contain a trailing qualifer as this is set
            separately.

        If there is no matching expand item no action is taken."""
        path = get_path(path)
        if not len(path):
            raise ValueError
        if isinstance(path[-1], QualifiedName):
            path = path[:-1]
            if not len(path):
                raise ValueError
        path = tuple(path)
        i = 0
        while i < len(self.expand):
            if self.expand[i].path == path:
                del self.expand[i]
            else:
                i += 1

    def add_expand_item(self, item):
        """Add an additional expand item to the options

        item
            A :class:`ExpandItem` instance such as would be returned
            from the parser when parsing the $expand query option."""
        if isinstance(item, ExpandItem):
            self._clear_cache()
            i = 0
            while i < len(self.expand):
                if self.expand[i].path == item.path:
                    del self.expand[i]
                else:
                    i += 1
            self.expand.append(item)
        else:
            raise ValueError

    def get_expand_item(self, path):
        """Returns the current ExpandItem for a navigation path"""
        path = get_path(path)
        if isinstance(path[-1], QualifiedName):
            path = path[:-1]
        if not len(path):
            raise ValueError
        path = tuple(path)
        for item in self.expand:
            if item.path == path:
                return item
        return None

    def clear_expand(self):
        """Removes all expand items from the options"""
        self._clear_cache()
        self.expand = []

    def complex_selected(self, qname, pname):
        """Returns a (ExpandOptions, QualifiedName) tuple

        Tests the select *and* expand rules for a match against a
        qualified name (as a *string* or None) and a property name.  The
        result is a set of expand options with the given property name
        factored out.  For example, if there is a rule "A/PrimitiveB"
        and we pass pname="A" we'll get back a set of expand options
        containing the select rule "PrimitiveB".

        Both select and expand paths may also be qualified with a
        trailing type cast.  We treat select paths (for complex types)
        in a way that is consistent with navigation via derived types.
        The caveat is that you must not have more than one such rule
        for a given property, in other words::

            $select=A/Schema.ComplexTypeB,A/Schema.ComplexTypeC

        This is never allowed as the types are assumed to conflict.  It
        appears possible that ComplexTypeC is derived from ComplexTypeB
        (or vice versa) but such redundancy is not allowed (by this
        implementation).

        The second item in the return tuple is either None or the
        QualifiedName of an explicit *required* type cast.  For example,
        if there is a rule "A/Schema.ComplexTypeB" and we pass
        pname="A" you get back a pseudo rule:

            $select=* and an explicit type cast to "Schema.ComplexTypeB"

        The type cast is only returned when an explicit type cast is
        found in a select rule.  The rule
        "A/Schema.ComplexTypeB/PropertyB" would still return:

            $select=Schema.ComplexTypeB/PropertyB (and no type cast)

        Navigation properties make the situation more complex but the
        basic idea is the same.  If there is a rule
        "A/NavX($expand=NavY)" then passing pname="A" will result in the
        *expand* rule "NavX($expand=NavY)".

        Paths that *contain* derived types are treated in the same way,
        we may know nothing of the relationship between types so will
        happily reduce "A/Schema.ComplexTypeB/B,A/Schema.ComplexTypeC/C"
        to "Schema.ComplexTypeB/B,Schema.ComplexTypeC/C" even if, in
        fact, ComplexTypeB and ComplexTypeC are incompatible derived
        types of the type of property A and can never be selected
        simultaneously.

        Paths are always evaluated related to the base type of a complex
        property, even if that value is subject to a type cast. As a
        result::

            $select=ComplexA/Schema.ComplexTypeB&
                $expand=ComplexA/Schema.ComplexTypeB/NavX

        still reduces to:

            $select=*&$expand=Schema.ComplexTypeB/NavX

        with a type cast to Schema.ComplexTypeB

        Although all selected values are required to have ComplexTypeB
        the base type is the defined type of ComplexA and that is used
        when evaluating the sub-rules, hence the need to retain
        Schema.ComplexTypeB in the expand path.

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property return the *same*
        :class:`ExpandOptions` instance."""
        result = self._complex_selected.get((qname, pname), None)
        if result is not None:
            return result
        options = ExpandOptions()
        # no rule means no selection in complex types
        options.select_default = False
        type_cast = None
        if self.select:
            selected = False
            for rule in self.select:
                # do we match this select rule?
                path = rule.path
                if not path:
                    # an empty select rule is ignored
                    continue
                p = path[0]
                if p == "*":
                    # * matches all structural properties, including all
                    # children and derived types of this complex type!
                    # OData doesn't allow complexProperty/* so we should
                    # only have a a single * in the resulting sub-select
                    # rules
                    selected = True
                    options.add_select_path("*")
                    continue
                if qname:
                    if not isinstance(p, QualifiedName) or to_text(p) != qname:
                        continue
                    p = path[1]
                    match_len = 2
                else:
                    match_len = 1
                if p == pname:
                    selected = True
                    subpath = path[match_len:]
                else:
                    continue
                if subpath:
                    new_rule = SelectItem()
                    new_rule.path = subpath
                    new_rule.type_cast = rule.type_cast
                    options.add_select_item(new_rule)
                else:
                    # a complete rule matching a complex property is
                    # treated as complexProperty/* but watch out for the
                    # type cast!
                    options.add_select_path("*")
                    if type_cast is None:
                        type_cast = rule.type_cast
                    elif type_cast == rule.type_cast:
                        # tolerate repeated rule
                        continue
                    else:
                        # complexProperty/schema.typeA
                        # complexProperty/schema.typeB
                        # conflict!
                        raise errors.PathError(
                            "Type cast in select rule: %s conflict with %s" %
                            (to_text(rule.path), type_cast))
        else:
            selected = self.select_default
            if selected:
                options.add_select_path("*")
        # now add the expansion options, even if we aren't selected
        # by the select rules we may be implicitly selected by an
        # expand path
        for rule in self.expand:
            path = rule.path
            if not path:
                continue
            p = path[0]
            if p == "*":
                if selected:
                    options.add_expand_path("*")
                # else:
                    # all navigation properties are matched but our
                    # complex type is not selected. We consider any
                    # descendent complex properties hidden and will
                    # not select them implicitly!
                continue
            if qname:
                if not isinstance(p, QualifiedName) or \
                        to_text(p) != qname:
                    continue
                p = path[1]
                match_len = 2
            else:
                match_len = 1
            if p == pname:
                subpath = path[match_len:]
            else:
                continue
            if subpath:
                # actually this must be the case, we are not a
                # navigation property ourselves!
                new_rule = ExpandItem()
                new_rule.path = subpath
                new_rule.type_cast = rule.type_cast
                new_rule.qualifer = rule.qualifier
                new_rule.options = rule.options
                options.add_expand_item(new_rule)
            else:
                raise errors.PathError(
                    "Expand rule matches complex property: %s" %
                    to_text(rule))
        if not selected and not options.expand:
            result = (None, None)
        else:
            result = (options, type_cast)
        self._complex_selected[(qname, pname)] = result
        return result

    def nav_expanded(self, qname, pname):
        """Returns an ExpandItem instance if this property is expanded

        qname
            A string, QualifiedName instance or None if the property is
            defined on the base type of the object these options apply
            to.

        pname
            A string.  The property name.

        Tests the expand rules only for a match against a specified
        property.  The (best) matching :class:`ExpandItem` is returned
        or None if there is no match.

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property are efficient."""
        if not self.expand:
            return None
        if is_text(qname):
            qname = QualifiedName.from_str(qname)
        result = self._nav_expanded.get((qname, pname), None)
        if result is not None:
            return result
        # now have we been expanded?
        for rule in self.expand:
            if not rule.path:
                continue
            path = rule.path
            p = path[0]
            if p == "*":
                # matches all navigation properties but continue
                # in case we find a better match
                result = rule
            if qname:
                if not isinstance(p, QualifiedName) or p != qname:
                    continue
                p = path[1]
                match_len = 2
            else:
                match_len = 1
            if p == pname:
                subpath = path[match_len:]
            else:
                continue
            if not subpath:
                # actually this must be the case, only a type cast
                # may appear after us.  This is a specific match
                # so exit the loop now
                result = rule
                break
            else:
                raise errors.PathError(
                    "Expand rule with trailing segments: %s" %
                    to_text(rule))
        self._nav_expanded[(qname, pname)] = result
        return result

    def resolve_type(self, qname):
        """Looks up a type in the context"""
        if self.context:
            type_def = self.context.qualified_get(qname)
        else:
            raise errors.PathError(
                "no context for type in path segment: %s" %
                to_text(qname))
        if type_def is None:
            raise errors.PathError(
                "couldn't resolve type in path segment: %s" %
                to_text(qname))
        return type_def


class OrderbyItem(object):

    """Object representing a single orderby item

    """

    def __init__(self):
        self.expr = None
        #: 1 = asc, -1  desc
        self.direction = 1


class CollectionOptions(EntityOptions):

    """Object representing a set of query options for a collection"""

    def __init__(self):
        super(CollectionOptions, self).__init__()
        self.skip = None
        self.top = None
        self.count = None
        self.filter = None
        self.search = None
        self.orderby = None

    def clone(self):
        """Creates a new instance forked from this one"""
        options = super(CollectionOptions, self).clone()
        options.skip = self.skip
        options.top = self.top
        options.count = self.count
        # no need to clone expressions, they shouldn't be dynamically
        # modified
        options.filter = self.filter
        options.search = self.search
        options.orderby = self.orderby
        return options

    def set_filter(self, filter_expr):
        self.filter = filter_expr

    def set_search(self, search_expr):
        self.search = search_expr

    def set_orderby(self, orderby_items):
        # Force orderby to be a tuple to ease cloning
        if orderby_items:
            self.orderby = tuple(orderby_items)
        else:
            self.orderby = None

    def set_top(self, top):
        self.top = top

    def set_skip(self, skip):
        self.skip = skip


class ExpandOptions(CollectionOptions):

    """Object representing a set of query options for a collection"""

    def __init__(self):
        super(ExpandOptions, self).__init__()
        self.levels = None

    def clone(self):
        """Creates a new instance forked from this one"""
        options = super(ExpandOptions, self).clone()
        options.levels = self.levels
        return options

    def set_option(self, name, value):
        if name == "$select":
            self.select = value
        elif name == "$expand":
            self.expand = value
        elif name == "$skip":
            self.skip = value
        elif name == "$top":
            self.top = value
        elif name == "$count":
            self.count = value
        elif name == "$filter":
            self.filter = value
        elif name == "$search":
            self.search = value
        elif name == "$orderby":
            self.orderby = value
        elif name == "$levels":
            self.levels = value


class SystemQueryOptions(CollectionOptions):

    """Object representing all system query options

    This class extends the collection options to include the
    client-specific options. The functions of these query options are
    not explicit in the model as their use is either implied (in the
    case of $id) or internal to the operation of the OData client."""

    def __init__(self):
        super(SystemQueryOptions, self).__init__()
        self.id = None
        self.format = None
        self.skiptoken = None

    def set_id(self, id):
        self.id = id


class Operator(xsi.Enumeration):
    """Enumeration for operators

    ::

            Operator.eq
            Operator.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "eq": 1,
        "ne": 2,
        "lt": 3,
        "le": 4,
        "gt": 5,
        "ge": 6,
        "has": 7,
        "and": 8,
        "or": 9,
        "add": 10,
        "sub": 11,
        "mul": 12,
        "div": 13,
        "mod": 14,
        "not": 15,
        "negate": 16,
        "isof": 17,
        "cast": 18,
        "member": 19,
        "method": 20,
        "lambda_bind": 21,
        "collection": 22,
    }

    aliases = {
        'bool_not': 'not',
        'bool_and': 'and',
        'bool_or': 'or',
        }


class CommonExpression(SortableMixin):

    """Abstract class for all expression objects."""

    def sortkey(self):
        # by default, expressions have max precedence
        return 100

    def otherkey(self, other):
        if isinstance(other, CommonExpression):
            return other.sortkey()
        else:
            return NotImplemented

    def evaluate(self, evaluator):
        raise NotImplementedError("Evaluation of %s" % repr(self))


class NameExpression(CommonExpression):

    """Class representing a simple name in an expression"""

    def __init__(self, name):
        self.name = name


class ReservedExpression(CommonExpression):

    """Class representing a simple reserved name in an expression"""

    def __init__(self, name):
        self.name = name


class WordExpression(CommonExpression):

    """Class representing a search word in an expression

    Only used in search expressions, not valid in common expressions."""

    def __init__(self, word):
        self.word = word


class LiteralExpression(CommonExpression):

    """Class representing a literal expression

    For example, values matching primitiveLiteral in the ABNF.  We
    actually store the expression's value 'unboxed', that is, as a raw
    value rather than a transient :class:`Value` instance."""

    def __init__(self, value):
        self.value = value

    def evaluate(self, evaluator):
        return evaluator.primitive(self.value)


class OperatorExpression(CommonExpression):

    """Class representing an operator expression"""

    def __init__(self, op_code):
        self.op_code = op_code
        self.operands = []

    precedence = {
        Operator.lambda_bind: 0,
        Operator.bool_or: 1,
        Operator.bool_and: 2,
        Operator.ne: 3,
        Operator.eq: 3,
        Operator.gt: 4,
        Operator.ge: 4,
        Operator.lt: 4,
        Operator.le: 4,
        Operator.isof: 4,
        Operator.add: 5,
        Operator.sub: 5,
        Operator.mul: 6,
        Operator.div: 6,
        Operator.negate: 7,
        Operator.bool_not: 7,
        Operator.cast: 7,
        Operator.member: 8,
        Operator.has: 8,
        Operator.method: 8,
        Operator.collection: 8,
        }

    def sortkey(self):
        return self.precedence.get(self.op_code, 0)

    def add_operand(self, operand):
        self.operands.append(operand)


class UnaryExpression(OperatorExpression):

    """Class representing unary operator expression"""

    def add_operand(self, operand):
        if len(self.operands):
            raise ValueError("unary operator already bound")
        self.operands.append(operand)


class BinaryExpression(OperatorExpression):

    """Class representing binary operator expression"""

    def add_operand(self, operand):
        if len(self.operands) > 1:
            raise ValueError("binary operator already bound")
        self.operands.append(operand)

    def format_expr(self, operand_strs):
        if self.op_code == Operator.member:
            return "%s/%s" % (
                operand_strs[0],
                operand_strs[1])
        elif self.op_code == Operator.lambda_bind:
            return "%s:%s" % (
                operand_strs[0],
                operand_strs[1])
        else:
            return "%s %s %s" % (
                operand_strs[0],
                Operator.to_str(self.op_code),
                operand_strs[1])


class CallExpression(OperatorExpression):

    """Class representing function call expression"""

    def __init__(self, name):
        OperatorExpression.__init__(self, Operator.method)
        self.name = name

    def format_expr(self, operand_strs):
        return "%s(%s)" % (
            self.name,
            ",".join(operand_strs))


class CollectionExpression(OperatorExpression):

    """Class representing an expression that evaluates to a collection

    Not used in inline syntax where JSON formatted arrays are treated as
    literals but available in Annotation expressions through use of the
    <Collection> element."""

    def __init__(self):
        OperatorExpression.__init__(self, Operator.collection)

    def format_expr(self, operand_strs):
        return "[%s]" % (",".join(operand_strs))


class APathExpression(LiteralExpression):

    """An expression that evaluates to an AnnotationPath

    Not used in inline syntax where paths are decomposed and evaluated
    using the notional member operator.  Instead, AnnotationPath
    expressions evaluate to the path itself hence they are treated
    as a special type of literal expression."""
    pass


class PathExpression(CommonExpression):

    """An expression that evaluates a path

    We actually store the expression's value as a tuple (as per the
    return value of :func:`path_from_str`) but when evaluated a path
    expression is evaluated in the current context by path traversal."""

    def __init__(self, path):
        self.path = path

    def evaluate(self, evaluator):
        return evaluator.resolve_path(self.path)
