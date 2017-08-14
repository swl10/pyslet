#! /usr/bin/env python

import collections
import weakref

from . import errors

from .. import rfc2396 as uri
from ..py2 import (
    BoolMixin,
    force_text,
    is_text,
    to_text,
    UnicodeMixin,
    )
from ..xml import xsdatatypes as xsi


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


class EnumLiteral(
        UnicodeMixin,
        collections.namedtuple('QualifiedEnum', ['qname', 'value'])):

    """Represents the literal representation of an enumerated value.

    Enumeration literals consist of a :class:`QualifiedName` (used to
    interpret the value at a later time) and a tuple of string
    identifiers or integers."""

    __slots__ = ()

    def __unicode__(self):
        return force_text("%s'%s'" % (self.qname, ','.join(self.value)))


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

    @staticmethod
    def split_qname(qname):
        """Splits a qualified name string

        Returns a :class:`QualifiedName` instance, a tuple of
        (namespace, name).  There is no validity checking other than
        that namespace and name must be non-empty otherwise ValueError
        is raised."""
        dot = qname.rfind('.')
        if dot < 1 or dot >= len(qname) - 1:
            # ".name" and "name." don't count!
            raise ValueError("qualified name required: %s" % qname)
        return QualifiedName(qname[:dot], qname[dot + 1:])


class Term(Named):

    """Represents a defined term in the OData model

    In many ways Annotations can be thought of as custom property values
    associated with an object and Terms can be thought of as custom
    property definitions.  Like property definitions, they have an
    associated type that can be called to create a new :class:`Value`
    instance of the correct type for the Term."""

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

    def set_type(self, type_def):
        self.type_def = type_def

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_default(self, default_value):
        self.default_value = default_value


class Annotatable(object):

    """Abstract class for model elements that can be annotated"""

    def __init__(self, **kwargs):
        super(Annotatable, self).__init__(**kwargs)
        self.annotations = Annotations()

    def annotate(self, qa, target=None):
        """Annotate this element with a qualified annotation

        qa
            A :class:`QualifiedAnnotation` instance.

        target
            An optional target as a string.  If given then the target
            must exist as a named child of this object and be
            Annotable.  This is an abbreviated form of::

                obj[target].annotate(qa)

            but with some additional type checking."""
        if target is not None:
            # will raise TypeError or KeyError if not found
            target = self[target]
            if not isinstance(target, Annotatable):
                raise TypeError("Annotation target is not Annotatable")
            target.annotate(qa)
        else:
            try:
                qualifier = qa.qualifier
                if qualifier is None:
                    qualifier = ""
                qa.qualified_declare(self.annotations, qualifier)
            except errors.DuplicateNameError:
                raise errors.DuplicateNameError(
                    errors.Requirement.annotations_s %
                    ("%s:%s)" % (qa.term.qname, qualifier)))


class Annotations(NameTable):

    """The set of Annotations applied to a model element.

    A name table that contains :class:`Annotation` instances keyed on
    the qualified name of the defining term.  The vocabulary is
    confusing here because the qualified name of an annotation is a
    namespace-qualified name such as "odata.context", meaning the term
    "context" in the (built-in) namespace "odata".  Annotations
    themselves can be further qualified using 'qualifiers' that have
    nothing to do with the qualified name!  These qualifiers act more
    like filters on the annotations allowing the annotations themselves
    to be multi-valued.  One possible use of these qualifiers might be
    to allow for language tags on human-readable annotations (though the
    restriction that qualifiers are simple identifiers is problematic in
    this regard).

    To give an example, when they appear in JSON payloads annotations
    appear as <object>@<qualified name>#qualifier -- in many cases the
    <object> is empty as the annotation is attached to the object itself
    as a name/value pair so you might see something like::

        @Org.OData.Core.V1.Description#en

    The qualified name of the annotation is the name of a defined Term,
    in this case "Description" in the "Org.OData.Core.V1" namespace.
    The qualifier "en" has been added, perhaps to indicate that the
    language used is "English".

    The Annotations object contains all annotations associated with an
    object.  In contrast, the Annotation object contains all annotations
    that share the same qualified name (i.e., they differ only in the
    optional qualifier).  To obtain an actual qualified annotation (with
    its associated value) therefore requires two index lookups, for the
    example above::

        annotations["Org.OData.Core.V1.Description"]["en"]
        # a convenience method is also provided that returns None rather
        # than raise KeyError if the lookup fails...
        annotations.qualified_get("Org.OData.Core.V1.Description", "en")

    The result is a :class:`QualifiedAnnotation` instance.  For
    unqualified annotations just use the empty string as the second
    index.

    There is one further complication: some objects that are annotatable
    in the specification are not directly annotatable when represented
    in JSON payloads.  For example, an instance of a property called
    "FirstName" with a primitive value "Steve" of type Edm.String is
    represented in JSON as::

        "FirstName": "Steve"

    Annotations of this value appear adjacent to the value itself using
    the optional object prefix described above::

        "FirstName": "Steve"
        "FirstName@Core.Description": "Abbreviated form of actual name"

    The specification draws attention to the wide applicability of annotations
    though:

        As the intended usage may evolve over time, clients SHOULD be
        prepared for any annotation to be applied to any element

    As a result, we use the :class:`Annotatable` class liberally in the
    model including making the abstract :class:`Value` annotatable.  The
    upshot is that annotations of the form "FirstName@Core.Description"
    can be resolved and applied to the correct instance at runtime."""

    def check_name(self, name):
        """Checks the validity of 'name' against QualifiedName

        Raises ValueError if the name is not valid (or is None)."""
        if name is None:
            raise ValueError("Annotation with no name")
        if not self.is_qualified_name(name):
            raise ValueError("%s is not a valid qualified name" % name)

    def check_value(self, value):
        if not isinstance(value, Annotation):
            raise TypeError(
                "Annotation required, found %s" % repr(value))

    def qualified_get(self, term, qualifier=None, default=None):
        """Looks up an annotation

        term
            The qualified name of an annotation Term

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
        if qualifier is None:
            qualifier = ('', )
        elif is_text(qualifier):
            qualifier = (qualifier, )
        for q in qualifier:
            try:
                a = self[term]
                return a[q]
            except KeyError:
                continue
        return default


class Annotation(NameTable):

    """An Annotation (applied to a model element).

    The name of this object is the qualified name of the term that
    defines this annotation.  The Annnotation is itself a name table
    comprising the :class:`QualifiedAnnotation` instances."""

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier

        Raises ValueError if the name is not valid (or is None).
        Empty string is allowed, as it represents no qualifier."""
        if name is None:
            raise ValueError("None is not a valid qualifier (use '')")
        elif name and not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid qualifier" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a name

        In this NameTable, names are qualifiers for annotations.  We
        create a qualified name by taking the *qualified* name of this
        Annotation and adding "#" followed by the qualifier (the name
        argument).  If this annotation has not been declared then we
        simply return name prefixed with '#'.  In the special case where
        the qualifier (name) is the empty string no '#' is appended."""
        if self.qname:
            if name:
                return self.qname + "#" + name
            else:
                return self.qname
        elif name:
            return "#" + name
        else:
            return name

    def check_value(self, value):
        if not isinstance(value, QualifiedAnnotation):
            raise TypeError(
                "QualifiedAnnotation required, found %s" % repr(value))


class QualifiedAnnotation(Named):

    """A Qualified Annotation (applied to a model element)

    The name of this object is the qualifier used or *an empty string*
    if the annotation was applied without a qualifier."""

    def __init__(self, term, qualifier=None, **kwargs):
        super(QualifiedAnnotation, self).__init__(**kwargs)
        #: the term that defines this annotation
        if term is None or term.type_def is None:
            raise ValueError(
                "Qualified annnotation with no defined term")
        self.term = term
        #: the qualifier associated with this annotation or None the
        #: annotation has no qualifier.
        self.qualifier = qualifier
        #: the value of this annotation, a :class:`Value` instance
        self.value = term.type_def()

    @classmethod
    def split_json_name(cls, name):
        """Splits a JSON encoded annotation name

        Returns a 3-tuple of (target, qname, qualifier).  For example,
        the annotation::

            FirstName@Core.Description#ascii

        would return::

            ("FirstName", "Core.Description", "ascii")

        The target and qualifier and optional and may be None."""
        target = None
        qualifier = None
        apos = name.find('@')
        if apos < 0:
            raise ValueError("Annotation name must contain '@': %s" % name)
        fpos = name.find('#', apos)
        if fpos >= 0:
            qname = name[apos + 1: fpos]
            qualifier = name[fpos + 1:]
        else:
            qname = name[apos + 1:]
        if apos >= 1:
            target = name[:apos]
        qname = NameTable.split_qname(qname)
        return (target, qname, qualifier)

    @classmethod
    def from_qname(cls, qname, context, qualifier=None):
        """Creates a new instance from a qualified name and context

        qname
            The qualified name of the annotation (a string or a
            :class:`QualifiedName` tuple).

        context
            The entity model within which to look up the associated
            term definition.

        qualifier
            The optional qualifier for this annotation.

        Returns a QualifiedAnnotation instance or None if the definition
        of the term could not be found."""
        # lookup qname in the context
        term = context.qualified_get(qname)
        if not isinstance(term, Term):
            return None
        return cls(term, qualifier=qualifier)

    def qualified_declare(self, annotations, qualifier=""):
        """Declares this qualified annotation in an Annotations instance"""
        if self.term is None or self.term.name is None:
            raise ValueError(
                "Can't declare annotation: Term is missing or undeclared")
        tname = self.term.qname
        a = annotations.get(tname, None)
        if a is None:
            a = Annotation()
            a.declare(annotations, tname)
        self.declare(a, qualifier)


class NominalType(Named):

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
        self.service = None

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
        if self.service is not None:
            raise errors.ModelError(
                "%s is already bound to a context" % self.qname)
        self.service = service_ref

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
            if self.namespace().name == "Edm":
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
        if self.service is None:
            svc = None
        else:
            svc = self.service()
        if svc is service:
            return uri.URI.from_octets(self.get_odata_type_fragment)
        elif svc is not None:
            return uri.URI.from_octets(
                self.get_odata_type_fragment).resolve(svc.context_base)
        else:
            raise errors.ModelError("%s has no context" % to_text(self))


class Value(Annotatable, BoolMixin, UnicodeMixin):

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
        #: the fully qualified type name of this value's type if it is
        #: of a type derived from the declared type for the property
        #: that we are a value of
        self.type_cast = None
        #: the name of this value within the parent (property name)
        self.name = None

    __hash__ = None

    def __bool__(self):
        return not self.is_null()

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

        A value is owned if it is a named property of another value."""
        if self.parent is not None:
            raise ValueError("Object already owned")
        self.parent = parent_ref
        p = parent_ref()
        self.name = name
        if name not in p.base_def:
            # we weren't declared in the base type of the parent so we
            # need a type cast to the type we were declared in (not
            # necessarily the type of our parent which may be further
            # derived).
            self.type_cast = p.type_def[name].nametable().qname
        if p.service is not None:
            self.bind_to_service(p.service)

    def bind_to_service(self, service_ref):
        """Binds this value to a specific OData service

        service
            A weak reference to the service we're binding to.

        There are basically two types of Value instances in Pyslet's
        OData model: dynamic values that provide a local view of an
        object bound to a shared data service and static values that are
        not.  (In this sense, a collection might be static even if its
        items are dynamic.)  This method binds a value to a service
        making it dynamic.

        In normal use you won't need to bind values yourself.  All
        values are created static.  Values are bound automatically by
        the data service when deserlizing data service responses and may
        also be bound as an indirect consequence of an operation.  For
        example, if you create an EntityValue by calling an EntityType
        instance you get a static entity but if you (successfully)
        insert that entity into a dynamic EntitySetValue it will become
        bound to the same service as the EntitySetValue value as you
        would expect."""
        if self.service is not None:
            raise errors.ModelError("Value is already bound" % to_text(self))
        self.service = service_ref


class PropertyOptions(object):

    """Object representing the property options: select and expand

    There are two attributes.  The select attribute contains a list of
    path tuples describing the selected property paths (or None if the
    default selection should be used).

    The expand attribute contains..."""

    def __init__(self):
        self.select = None
        self.expand = None

    def get_select_str(self):
        """Returns the select option as a string"""
        if self.select:
            return ",".join(
                "/".join(to_text(i) for i in p) for p in self.select)


class CollectionOptions(PropertyOptions):

    """Object representing a set of query options for a collection"""

    def __init__(self):
        super(CollectionOptions, self).__init__()
        self.skip = None
        self.top = None
        self.count = None
        self.filter = None
        self.search = None
        self.orderby = None


class ExpandOptions(CollectionOptions):

    """Object representing a set of query options for a collection"""

    def __init__(self):
        super(ExpandOptions, self).__init__()
        self.levels = None


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


class ExpandItem(object):

    """Object representing a single expanded item

    """

    def __init__(self):
        self.path = None
        self.qualifier = None
        self.options = ExpandOptions()
