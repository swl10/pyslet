#! /usr/bin/env python

import base64
import collections
import datetime
import decimal
import logging
import math
import sys
import uuid
import weakref

from . import errors
from . import geotypes as geo

from .. import rfc2396 as uri
from ..iso8601 import (
    Date,
    DateTimeError,
    Time,
    TimePoint)
from ..py2 import (
    BoolMixin,
    byte,
    force_text,
    is_text,
    is_unicode,
    long2,
    py2,
    range3,
    to_text,
    ul,
    UnicodeMixin
    )
from ..xml import xsdatatypes as xsi
from ..unicode5 import BasicParser, CharClass, ParserError


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


class EntityModel(NameTable):

    """An EntityModel is the starting point for an OData service

    The EntityModel behaves like a mapping of namespace names (as text
    strings) on to :class:`Schema` instances.  """

    def __init__(self, **kwargs):
        super(EntityModel, self).__init__(**kwargs)
        #: a weak reference to the service this model is bound to
        self.service = None
        # all entity models have the built-in Edm namespace in scope
        self['Edm'] = edm
        self['odata'] = odata

    def check_name(self, name):
        """EntityModels contain schemas that define namespaces

        The syntax for a namespace is a dot-separated list of simple
        identifiers."""
        if name is None:
            raise ValueError("unnamed schema")
        if not self.is_namespace(name):
            raise ValueError("%s is not a valid namespace" % name)

    def check_value(self, value):
        """EntityModels can only contain Schemas"""
        if not isinstance(value, Schema):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<EntityModel>" if self.name is None else self.name))

    def qualified_get(self, qname, default=None):
        """Looks up qualified name in this entity model.

        qname
            A string or a :class:`QualifiedName` instance.

        default (None)
            The value to return if the name is not declared."""
        if isinstance(qname, QualifiedName):
            namespace, name = qname
        else:
            namespace, name = self.split_qname(qname)
        try:
            return self[namespace][name]
        except KeyError:
            return default

    def qualified_tell(self, qname, callback):
        """Deferred qualified name lookup.

        Similar to :meth:`Nametable.tell` except that it waits until
        both the Schema containing qname is defined *and* the target
        name is defined within that Schema.

        If the entity model or the indicated Schema is closed without
        qname being declared then the callback is called passing None."""
        nsname, name = self.split_qname(qname)

        def _callback(ns):
            if ns is None:
                callback(None)
            else:
                ns.tell(name, callback)

        self.tell(nsname, _callback)

    def close(self):
        """Overridden to perform additional validation checks

        The EntityModel is always closed to prevent the caller making
        future declarations in this model.  The following conditions
        will result in an error being raised.

            1. All declared Schema objects MUST be closed
            2. There MUST NOT be any disallowed circular type references
        """
        super(EntityModel, self).close()
        for s in self.values():
            if not s.closed:
                raise errors.ModelError("Schema %s is still open" % s.name)
        # Closing the entity model triggers any pending references to
        # undeclared schemas to be terminated.  The Schemas themselves
        # should all be closed at this point but circular references may
        # still be open and waiting for closure.
        for s in self.values():
            s.detect_circular_refs()
        for s in self.values():
            for item in s.values():
                if isinstance(item, StructuredType):
                    item.set_annotations()

    def derived_types(self, base):
        """Generates all types derived from base"""
        for name, schema in self.items():
            if name != schema.name:
                # ignore schema aliases
                continue
            for n, item in schema.items():
                if isinstance(item, StructuredType) and \
                        item.is_derived_from(base, strict=True):
                    yield item

    def bind_to_service(self, service):
        """Binds this EntityModel to a data service

        The act of binding an EntityModel to a data service binds
        all type definitions within the model to the same service
        enabling these types to be referred to with globally unique
        identifiers (the URLs used for @odata.type annotations) in
        OData payloads.

        The service should not be confused with the metadata document
        that contains a type definition.  Although every service must
        have a metadata document the reverse is not true: a metadata
        document may just be a CSDL document with a URL that contains
        common definitions included by reference.  (The standard OData
        vocabularies are an example.)

        On a more technical note: a common type defined in a metadata
        document that is reused by multiple services will have a
        different identity in each service, as represented by the
        @odata.type value used to describe the type of values.  As a
        result, each type definition can only be bound to one service!
        The CSDL parser in the metadata module handles this for you by
        creating separate instances of each Schema object loaded by
        reference so that applications that manage multiple services
        sharing common definitions do not violate this constraint.

        There is one special case: the Edm Schema object is only loaded
        once and the definitions within it are *never* bound to the
        service.  This is consistent with the way these types are handled
        by the specification:

            For built-in primitive types the value is the unqualified
            name of the primitive type, specified as a URI fragment

        In other words, types like Edm.String have the *same* identity
        in all services and are represented by the URL fragment
        #String."""
        self.service = weakref.ref(service)
        for sname, schema in self.items():
            if schema.name != sname or schema.name in ("Edm", "odata"):
                # skip aliases and reserved schemas
                continue
            for item in schema.values():
                if isinstance(item, NominalType):
                    logging.debug("Binding type: %s", item.qname)
                    item.bind_to_service(self.service)
        for item in self.get_container().values():
            if isinstance(item, EntitySet):
                item.bind_to_service(self.service)

    def get_context_url(self):
        """Returns the context URL of this model

        The model *must* have been bound to a service for have a context
        url."""
        if self.service is None or self.service() is None:
            raise errors.UnboundValue("Unbound EntityModel has no context")
        return self.service().context_base

    def get_container(self):
        """Returns the required container for this model

        The requirement to define an entity container is not applied to
        all entity models.  Models only designed to be included by
        reference do not need to define a container."""
        container = None
        for name, schema in self.items():
            if name != schema.name or not schema.is_owned_by(self):
                # ignore aliases and schemas included by reference
                continue
            for n, item in schema.items():
                if isinstance(item, EntityContainer):
                    if container is not None:
                        raise errors.ModelError(
                            errors.Requirement.one_container)
                    container = item
        return container


class Annotatable(object):

    """Abstract class for model elements that can be annotated"""

    def __init__(self, **kwargs):
        super(Annotatable, self).__init__(**kwargs)
        self.annotations = Annotations()

    def annotate(self, qa):
        """Annotate this element with a qualified annotation

        If the qualified annotation has a specified target then the
        target must exist and it must not be another Annotable object.

        """
        if qa.target:
            # will raise TypeError or KeyError if not found
            target = self[qa.target]
            if isinstance(target, Annotatable):
                raise TypeError("Annotation target is Annotatable")
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
    "FirstName" with a primitive value ("Steve" of type Edm.String) is
    represented in JSON as::

        "FirstName": "Steve"

    Annotations of this value appear adjacent to the value itself using
    the optional object prefix described above::

        "FirstName": "Steve"
        "FirstName@Core.Description": "Abbreviated form of actual name"

    To keep the Pyslet classes more closely aligned with the JSON
    representation the primitive values do *not* inherit from
    :class:`Annotatable`.  Instead, annotations are declared in the
    containing object's :attr:`Annotatable.annotations` attribute using
    the object prefix.

    ..  note::  *Unlike* the JSON representation, annotations that
                apply to the object itself are declared *without* the
                leading '@' because they do not share a namespace with
                the declared children of the object.  The prefixed form
                is, however, stored in the :attr:`Annotation.qname`
                attribute of the Annotation object on declaration."""

    def check_name(self, name):
        """Checks the validity of 'name' against QualifiedName

        Raises ValueError if the name is not valid (or is None)."""
        if name is None:
            raise ValueError("Annotation with no name")
        if '@' in name:
            parts = name.split('@')
            target = parts[0]
            name = '@'.join(parts[1:])
            if not self.is_simple_identifier(target):
                raise ValueError("%s is not a simplie identifier" % target)
        if not self.is_qualified_name(name):
            raise ValueError("%s is not a valid qualified name" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a name

        The name is already a qualified name (of the annotation term)
        optionally prefixed with a target identifier.  If there is no
        target object prefix than "@" is prepended to the name to
        indicate that the annotation applies to the current object."""
        if '@' in name:
            return name
        else:
            return '@' + name

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

        In this NameTable, names are qualifier for annotations.  We
        create a qualified name by taking the *qualified* name of this
        Annotation and adding "#" followed by the qualifier (the name
        argument).  If this annotation has not been declared then we
        simply return name prefixed with '#'."""
        if self.qname:
            return self.qname + "#" + name
        else:
            return "#" + name

    def check_value(self, value):
        if not isinstance(value, QualifiedAnnotation):
            raise TypeError(
                "QualifiedAnnotation required, found %s" % repr(value))


class QualifiedAnnotation(Named):

    """A Qualified Annotation (applied to a model element)

    The name of this object is the qualifier used or *an empty string*
    if the annotation was applied without a qualifier."""

    def __init__(self, term, qualifier=None, target=None, **kwargs):
        super(QualifiedAnnotation, self).__init__(**kwargs)
        #: the simple identifier of the annotation target or None if
        #: this annotation applies to the object that contains it.
        self.target = target
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
    def from_json_name(cls, name, context):
        """Creates a new instance from a name and context

        name
            The name of an annotation as presented in a JSON payload.
            Names containing '@' and '.' are treated as annotation names.

        context
            The entity model within which to look up the associated
            term definition.

        Returns the QualifiedAnnotation instance or None if the
        definition of the term could not be found."""
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
        # lookup qname in the context
        term = context.qualified_get(qname)
        if not isinstance(term, Term):
            return None
        return cls(term, target=target, qualifier=qualifier)

    def qualified_declare(self, annotations, name=""):
        """Declares this qualified annotation in an Annotations instance

        The """
        if self.term is None or self.term.name is None:
            raise ValueError(
                "Can't declare annotation: Term is missing or undeclared")
        tname = self.term.qname
        if self.target:
            tname = self.target + '@' + tname
        a = annotations.get(tname, None)
        if a is None:
            a = Annotation()
            a.declare(annotations, tname)
        self.declare(a, name)


class Schema(Annotatable, NameTable):

    """A Schema is a container for OData model definitions."""

    def check_name(self, name):
        """Checks the validity of 'name' against SimpleIdentifier

        Raises ValueError if the name is not valid (or is None).

        From the spec:

            A nominal type has a name that MUST be a
            edm:TSimpleIdentifier."""
        if name is None:
            raise ValueError("unnamed type")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        """The following types may be declared in a Schema:

        NominalType
            Any named type.

        EntityContainer
            A container of entities.

        Term
            The definition of an annotation term."""
        if not isinstance(value, (Term, NominalType, EntityContainer)):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<Schema>" if self.name is None else self.name))

    def detect_circular_refs(self):
        """Detects any circular references

        In fact, this method searches for any objects with NameTables
        that are still open and warns that they may be part of a circular
        chain of references.  For EntityTypes we check for inheritance
        cycles specifically, otherwise we then intervene by closing one
        of the objects arbitrarily which should resolve the problem.

        Although undesirable, circular references are tolerated in
        EntityContainers (the specification uses the language SHOULD NOT
        rather than MUST NOT). In cases like these objects end up
        containing the union of the two sets of definitions."""
        for item in self.values():
            if isinstance(item, NameTable) and not item.closed:
                logging.warning("Circular reference detected: %s", item.qname)
                if isinstance(item, (ComplexType, EntityType)):
                    try:
                        item.is_derived_from(item, strict=True)
                    except errors.InheritanceCycleDetected:
                        raise errors.InheritanceCycleDetected(
                            (errors.Requirement.et_cycle_s if
                             isinstance(item, EntityType) else
                             errors.Requirement.ct_cycle_s) % item.qname)
                item.close()

    def get_model(self):
        """Returns the entity model that defines this Schema.

        If this Schema has not been declared yet then None is
        returned."""
        if self.nametable is not None:
            return self.nametable()

    edm = None
    """The Edm schema.

    This schema contains the base type definitions of the built-in
    types in the Edm namespace."""

    @classmethod
    def edm_init(cls):
        """Creates and returns the built-in Edm schema"""
        cls.edm = Schema()
        cls.edm.name = "Edm"
        cls.edm.qname = "Edm"
        primitive_base = PrimitiveType()
        primitive_base.set_abstract(True)
        primitive_base.declare(cls.edm, "PrimitiveType")
        complex_base = ComplexType()
        complex_base.declare(cls.edm, "ComplexType")
        complex_base.set_abstract(True)
        complex_base.close()
        entity_base = EntityType()
        entity_base.declare(cls.edm, "EntityType")
        entity_base.set_abstract(True)
        entity_base.close()
        for name, vtype in (('Binary', BinaryValue),
                            ('Boolean', BooleanValue),
                            ('Byte', ByteValue),
                            ('Date', DateValue),
                            ('DateTimeOffset', DateTimeOffsetValue),
                            ('Decimal', DecimalValue),
                            ('Double', DoubleValue),
                            ('Duration', DurationValue),
                            ('Guid', GuidValue),
                            ('Int16', Int16Value),
                            ('Int32', Int32Value),
                            ('Int64', Int64Value),
                            ('SByte', SByteValue),
                            ('Single', SingleValue),
                            ('Stream', StreamValue),
                            ('String', StringValue),
                            ('TimeOfDay', TimeOfDayValue)):
            primitive = PrimitiveType()
            primitive.set_base(primitive_base)
            primitive.value_type = vtype
            # set the default facets to sensible defaults
            if vtype in (DateTimeOffsetValue, DurationValue, TimeOfDayValue):
                primitive.set_precision(6, can_override=True)
            elif vtype is DecimalValue:
                primitive.set_precision(None, -1, can_override=True)
            primitive.declare(cls.edm, name)
        geography_base = PrimitiveType()
        geography_base.set_base(primitive_base)
        geography_base.set_abstract(True)
        geography_base.declare(cls.edm, "Geography")
        for name, vtype in (('GeographyPoint', GeographyPointValue),
                            ('GeographyLineString', GeographyLineStringValue),
                            ('GeographyPolygon', GeographyPolygonValue),
                            ('GeographyMultiPoint', GeographyMultiPointValue),
                            ('GeographyMultiLineString',
                             GeographyMultiLineStringValue),
                            ('GeographyMultiPolygon',
                             GeographyMultiPolygonValue),
                            ('GeographyCollection', GeographyCollectionValue)):
            geography = PrimitiveType()
            geography.set_base(geography_base)
            geography.value_type = vtype
            geography.declare(cls.edm, name)
        geometry_base = PrimitiveType()
        geometry_base.set_base(primitive_base)
        geometry_base.set_abstract(True)
        geometry_base.declare(cls.edm, "Geometry")
        for name, vtype in (('GeometryPoint', GeometryPointValue),
                            ('GeometryLineString', GeometryLineStringValue),
                            ('GeometryPolygon', GeometryPolygonValue),
                            ('GeometryMultiPoint', GeometryMultiPointValue),
                            ('GeometryMultiLineString',
                             GeometryMultiLineStringValue),
                            ('GeometryMultiPolygon',
                             GeometryMultiPolygonValue),
                            ('GeometryCollection', GeometryCollectionValue)):
            geometry = PrimitiveType()
            geometry.set_base(geometry_base)
            geometry.value_type = vtype
            geometry.declare(cls.edm, name)
        cls.edm.close()
        return cls.edm

    odata = None
    """The odata schema.

    This schema contains the builtin term definitions."""

    @classmethod
    def odata_init(cls):
        """Creates and returns the built-in odata schema"""
        cls.odata = Schema()
        cls.odata.name = "odata"
        cls.odata.qname = "odata"
        for tname in (
                "associationLink",
                "bind",
                "context",
                "deltaLink",
                "editLink",
                "etag",
                "id",
                "mediaContentType",
                "mediaEditLink",
                "mediaEtag",
                "mediaReadLink",
                "metadataEtag",
                "navigationLink",
                "nextLink",
                "type",
                ):
            term = Term()
            term.set_type(cls.edm["String"])
            term.declare(cls.odata, tname)
        term = Term()
        term.set_type(cls.edm["Int64"])
        term.declare(cls.odata, "count")
        cls.odata.close()
        return cls.odata


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

    def __call__(self):
        return self.value_type(type_def=self)

    def declare(self, nametable, name):
        try:
            super(NominalType, self).declare(nametable, name)
        except ValueError:
            raise ValueError(errors.Requirement.type_name)

    def get_qname(self):
        """Returns a :class:`QualifiedName` named tuple"""
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
            if self.namespace() is edm:
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


class PrimitiveType(Annotatable, NominalType):

    """A Primitive Type declaration

    Instances represent primitive type delcarations, such as those made
    by a TypeDefinition.  The built-in Edm Schema contains instances
    representing the base primitie types themselves and properties use
    this class to create undeclared types to constrain their values.

    The base type, and facet values are frozen when the type is first
    declared and the methods that modify them will raise errors if
    called after that."""

    # used for Decimal rounding, overridden by instance variables for
    # actual Decimal types.
    dec_nleft = decimal.getcontext().Emax + 1
    dec_nright = 0
    dec_digits = (1, ) * decimal.getcontext().prec

    # default used for temporal rounding (no fractional seconds)
    temporal_q = decimal.Decimal((0, (1, ), 0))

    def __init__(self, **kwargs):
        super(PrimitiveType, self).__init__(**kwargs)
        self.value_type = PrimitiveValue
        #: the specified MaxLength facet or None if unspecified
        self.max_length = None
        self._max_length = 0
        #: the specified Unicode facet or None if unspecified
        self.unicode = None
        self._unicode = True
        #: the specified Precision facet or None if unspecified
        self.precision = None
        #: the specified Scale facet or None if unspecified
        self.scale = None
        #: the specified SRID facet or None if unspecified.  The value
        #: -1 means variable
        self.srid = None
        self._srid = 0

    def set_base(self, base):
        """Sets the base type of this type

        The base must also be a PrimitiveType."""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not isinstance(base, PrimitiveType):
            raise TypeError(
                "%s is not a suitable base for a PrimitiveType" % base.qname)
        if not base.name:
            raise errors.ObjectNotDeclaredError("Base type must be declared")
        # update the value_type, impose a further restriction that the
        # incoming value_type MUST be a subclass of the previous
        # value_type.  In other words, you can't have a type based on
        # Edm.String and use set_base to 'rebase' it to Edm.Int64
        if not issubclass(base.value_type, self.value_type):
            raise TypeError(
                "Mismatched value types: can't base %s on %s" %
                (self.name, base.qname))
        self.value_type = base.value_type
        if issubclass(self.value_type, GeographyValue) and self.srid is None:
            # unspecified SRID, default for Geography is 4326
            self.set_srid(4326, can_override=True)
        elif issubclass(self.value_type,
                        (DateTimeOffsetValue, DurationValue, TimeOfDayValue)):
            # weak value
            self.set_precision(0, can_override=True)
        # now copy over strongly specified facets
        if base.max_length is not None:
            self.set_max_length(base.max_length)
        if base.unicode is not None:
            self.set_unicode(base.unicode)
        if base.precision is not None or base.scale is not None:
            self.set_precision(base.precision, base.scale)
        if base.srid is not None:
            self.set_srid(base.srid)
        super(PrimitiveType, self).set_base(base)

    def set_max_length(self, max_length, can_override=False):
        """Sets the MaxLength facet of this type.

        max_length
            A positive integer or 0 indicating 'max'

        can_override
            Used to control whether or not sub-types can override the
            value.  Defaults to False.  The value True is used to set
            limits on the primitives of the builtin Edm namespace which
            can be overridden by sub-types and/or property
            definitions.

        Can only be set for primitive types with underlying type Binary,
        Stream or String."""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not issubclass(
                self.value_type, (BinaryValue, StreamValue, StringValue)):
            logging.warning("MaxLength cannot be specified for %s",
                            self.value_type.__name__)
            return
        if max_length < 0:
            raise ValueError(
                "MaxLength facet must be a positive integer or 'max': %s" %
                repr(max_length))
        if can_override:
            # sets a weak value, ignored if already specified
            if self.max_length is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.max_length is not None:
                raise errors.ModelError(
                    errors.Requirement.td_facet_s % "MaxLength")
            self.max_length = max_length
        self._max_length = max_length

    def set_unicode(self, unicode_facet, can_override=False):
        """Sets the Unicode facet of this type

        unicode_facet
            A boolean

        can_override
            See :meth:`set_max_length` for details

        Can only be set on primitive types with underlying type
        String."""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not issubclass(self.value_type, StringValue):
            logging.warning("Unicode facet cannot be specified for %s",
                            self.value_type.__name__)
            return
        if can_override:
            # sets a weak value, ignored if already specified
            if self.unicode is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.unicode is not None:
                raise errors.ModelError(
                    errors.Requirement.td_facet_s % "Unicode")
            self.unicode = unicode_facet
        self._unicode = unicode_facet

    def set_precision(self, precision, scale=None, can_override=False):
        """Sets the Precision and (optionally) Scale facets

        precision
            A non-negative integer

        scale
            An non-negative integer or -1 indicating variable scale

        can_override
            See :meth:`set_max_length` for details

        Precision and Scale can only be set on primitive types with
        underlying type Decimal.  Precision on its own can be set on
        types with underlying temporal type.

        There is no explicit constraint in the specification that says
        you cannot set Scale without Precision for Decimal types.
        Therefore we allow prevision=None and use our default internal
        limit (typically 28 in the Python decimal module) instead.

        """
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if issubclass(self.value_type, DecimalValue):
            if precision is not None:
                if precision <= 0:
                    raise errors.ModelError(
                        errors.Requirement.decimal_precision)
                if scale is not None and scale > precision:
                    raise errors.ModelError(
                        errors.Requirement.scale_gt_precision)
        elif issubclass(self.value_type, (DateTimeOffsetValue, DurationValue,
                                          TimeOfDayValue)):
            if precision is not None and (precision < 0 or precision > 12):
                raise errors.ModelError(
                    errors.Requirement.temporal_precision)
        if can_override:
            # weak values are overridden by existing strong values
            if self.precision is not None:
                precision = self.precision
            if self.scale is not None:
                scale = self.scale
        else:
            # strong values
            if precision is None:
                precision = self.precision
            else:
                if self.precision is not None:
                    raise errors.ModelError(
                        errors.Requirement.td_facet_s % "Precision")
                self.precision = precision
            if scale is None:
                scale = self.scale
            else:
                if self.scale is not None:
                    raise errors.ModelError(
                        errors.Requirement.td_facet_s % "Scale")
                self.scale = scale
        if issubclass(self.value_type, DecimalValue):
            # precision must be positive (or None)
            if precision is None:
                if scale is None:
                    # both unspecified, scale implied 0 (default)
                    self.dec_nright = PrimitiveType.dec_nright
                elif scale < 0:
                    # variable scale, no limit on right digits as
                    # precision is also unlimited.
                    self.dec_nright = -(decimal.getcontext().Emin -
                                        decimal.getcontext().prec + 1)
                else:
                    # what is undefined - scale?  don't limit left
                    # digits, could perhaps throw an error here!
                    # scale must be <= precision, limit right digits
                    self.dec_nright = scale
                self.dec_nleft = PrimitiveType.dec_nleft
                self.dec_digits = PrimitiveType.dec_digits
            else:
                if scale is None:
                    # just precision specified, scale is implied 0
                    self.dec_nleft = precision
                    self.dec_nright = 0
                elif scale < 0:
                    # variable scale, up to precision on the right
                    self.dec_nleft = PrimitiveType.dec_nleft
                    self.dec_nright = precision
                else:
                    self.dec_nleft = precision - scale
                    self.dec_nright = scale
                self.dec_digits = (1, ) * min(decimal.getcontext().prec,
                                              precision)
        elif issubclass(self.value_type, (DateTimeOffsetValue, DurationValue,
                                          TimeOfDayValue)):
            # precision must be non-negative (max 12)
            if precision is None:
                # no precision = 0
                self.temporal_q = decimal.Decimal((0, (1, ), 0))
            else:
                # overload the class attribute
                self.temporal_q = decimal.Decimal(
                    (0, (1, ) * (precision + 1), -precision))
        elif scale is not None:
            logging.warning("Precision/Scale cannot be specified for %s",
                            self.value_type.__name__)
        else:
            logging.warning("Precision cannot be specified for %s",
                            self.value_type.__name__)

    def set_srid(self, srid, can_override=False):
        """Sets the SRID facet of this property

        srid
            A non-negative integer or -1 for variable

        can_override
            See :meth:`set_max_length` for details"""
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if not issubclass(self.value_type, (GeographyValue, GeometryValue)):
            logging.warning("SRID cannot be specified for %s",
                            self.value_type.__name__)
            return
        if srid < -1:
            raise errors.ModelError(errors.Requirement.srid_value)
        if can_override:
            # sets a weak value, ignored if already specified
            if self.srid is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.srid is not None:
                raise errors.ModelError(errors.Requirement.td_facet_s % "SRID")
            self.srid = srid
        self._srid = srid

    def match(self, other):
        """Returns True if this primitive type matches other

        Other must also be a PrimtiveType.  PrimitiveTypes match if they
        use the same underlying value type and any constrained facets
        are constrained in the same way.  If a facet is specified by
        only one of the types they are considered matching."""
        if not isinstance(other, PrimitiveType):
            return False
        if self.value_type is not other.value_type:
            return False
        if issubclass(self.value_type, StringValue):
            if self.unicode is None or other.unicode is None:
                # if either values are unspecified consider it a match
                return True
            if self.max_length is None or other.max_length is None:
                return True
            return (self.unicode == other.unicode and
                    self.max_length == other.max_length)
        elif issubclass(self.value_type, DecimalValue):
            return (self.dec_nleft == other.dec_nleft and
                    self.dec_nright == other.dec_nright and
                    self.dec_digits == other.dec_digits)
        elif issubclass(self.value_type, (DateTimeOffsetValue, DurationValue,
                                          TimeOfDayValue)):
            return self.temporal_q == other.temporal_q
        elif issubclass(self.value_type, (GeographyValue, GeometryValue)):
            return self.srid == other.srid
        else:
            return True

    def value_from_str(self, src):
        logging.debug("%s.value_from_str", self.value_type.edm_name)
        return self.value_type.from_str(src)


class PrimitiveValue(Value):

    """Class to represent a primitive value in OData.

    This class is not normally instantiated directly, use one of the
    *from\_* factory methods to construct a value of the correct
    sub-class from a string, literal or native python value.  Use one of
    the child classes directly to create a new value from an apporpriate
    python value using the default primitive type definition (i.e., with
    no additional constraining facets).  Otherwise, create instances by
    calling an instance of :class:`PrimitiveType`.

    If you do instantiate this class directly it will create a special
    type-less null value.

    When instances can be converted to strings they generate strings
    according to the primitiveValue ABNF defined in the specification.
    null values will raise a ValueError and cannot be serialised as
    strings."""

    edm_name = 'PrimitiveType'

    def __init__(self, pvalue=None, type_def=None, **kwargs):
        super(PrimitiveValue, self).__init__(
            type_def=edm[self.edm_name] if type_def is None else type_def,
            **kwargs)
        self.value = None
        if pvalue is not None:
            self.set_value(pvalue)

    def is_null(self):
        """Returns True if this object is null."""
        return self.value is None

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            # are the types compatible? lazy comparison to start with
            return self.value == other.value
        else:
            return self.value == other

    def __ne__(self, other):
        return not self == other

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(self.value)

    def get_value(self):
        """Returns a python 'native' value representation"""
        return self.value

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        The default implementation raises TypeError if value is anything
        other than None (as a typeless null is always null).

        Derived classes override this method to provide a more expansive
        set of value conversions from core Python types but to prevent
        mixing of python-native and odata-meta values instances of
        :class:`PrimitiveValue`, or any class derived from it, are not
        allowed and will raise TypeError.

        If the value argument is not of a suitable type for setting this
        primitive value instance then TypeError is raised.  If it is a
        suitable type but has a value out of the range permitted then
        ValueError is raised."""
        if self.frozen:
            raise errors.FrozenValueError
        elif value is None:
            self.value = None
            self.dirty = True
        else:
            raise TypeError("Can't set %s from %s" %
                            (str(self.type_def), repr(value)))

    @classmethod
    def from_value(cls, value):
        """Constructs a primitive value from a python native value

        The returned type depends on the input value:

        None
            A type-less null (PrimitiveValue instance)
        bool
            A BooleanValue instance
        bytes (Python2 str)
            BinaryValue instance
        datetime.date instance
            A DateValue instance
        datetime.datetime instance
            A DateTimeOffsetValue instance
        datetime.time instance
            A TimeOfDayValue instance
        decimal.Decimal instance
            A DecimalValue instance
        float
            A DoubleValue instance if the value is within range,
            otherwise a DecimalValue instance.
        int
            An Int64Value instance if the value is within range,
            otherwise a DecimalValue instance.
        long (Python 2 only)
            As for int.
        pyslet.odata4.geotypes.PointLiteral instance
            If SRID=0, GeometryPointValue, otherwise a
            GeographyPointValue instance.
        pyslet.odata4.geotypes.LineStringLiteral instance
            If SRID=0, GeometryLineStringValue, otherwise a
            GeographyLineStringValue instance.
        pyslet.odata4.geotypes.PolygonLiteral instance
            If SRID=0, GeometryPolygonValue, otherwise a
            GeographyPolygonValue instance.
        pyslet.odata4.geotypes.MultiPointLiteral instance
            If SRID=0, GeometryMultiPointValue, otherwise a
            GeographyMultiPointValue instance.
        pyslet.odata4.geotypes.MultiLineStringLiteral instance
            If SRID=0, GeometryMultiLineStringValue, otherwise a
            GeographyMultiLineStringValue instance.
        pyslet.odata4.geotypes.MultiPolygonLiteral instance
            If SRID=0, GeometryMultiPolygonValue, otherwise a
            GeographyMultiPolygonValue instance.
        pyslet.odata4.geotypes.GeoCollectionLiteral instance
            If SRID=0, GeometryCollectionValue, otherwise a
            GeographyCollectionValue instance.
        pyslet.iso8601.Date instance
            A DateValue instance
        pyslet.iso8601.Time instance
            A TimeOfDayValue instance
        pyslet.iso8601.TimePoint instance
            A DateTimeOffset instance.  The input value *must* be fully
            specified and have timezone information.
        pyslet.xml.xsdatatypes.Duration instance
            A DurationValue instance
        str (Python2 unicode only)
            A StringValue instance
        uuid.UUID instance
            A GuidValue instance

        All other input values raise TypeError."""
        if value is None:
            result = PrimitiveValue()
        elif value is True or value is False:
            result = BooleanValue()
            result.value = value
        elif is_unicode(value):
            result = StringValue()
            result.value = value
        elif isinstance(value, bytes):
            result = BinaryValue()
            result.value = value
        elif isinstance(value, decimal.Decimal):
            result = DecimalValue()
            result.value = value
        elif isinstance(value, int) or isinstance(value, long2):
            if value > Int64Value.MAX or value < Int64Value.MIN:
                result = DecimalValue.from_value(value)
            else:
                result = Int64Value()
                result.value = value
        elif isinstance(value, float):
            if value > DoubleValue.MAX or value < DoubleValue.MIN:
                result = DecimalValue.from_value(value)
            else:
                result = DoubleValue()
                result.value = value
        # warning: datetime() is derived from date(), check this first!
        elif isinstance(value, (TimePoint, datetime.datetime)):
            result = DateTimeOffsetValue()
            result.set_value(value)
        elif isinstance(value, (Date, datetime.date)):
            result = DateValue()
            result.set_value(value)
        elif isinstance(value, (Time, datetime.time)):
            result = TimeOfDayValue()
            result.set_value(value)
        elif isinstance(value, xsi.Duration):
            result = DurationValue()
            result.set_value(value)
        elif isinstance(value, uuid.UUID):
            result = GuidValue()
            result.set_value(value)
        elif isinstance(value, geo.PointLiteral):
            if value.srid:
                result = GeographyPointValue()
            else:
                result = GeometryPointValue()
            result.set_value(value)
        elif isinstance(value, geo.LineStringLiteral):
            if value.srid:
                result = GeographyLineStringValue()
            else:
                result = GeometryLineStringValue()
            result.set_value(value)
        elif isinstance(value, geo.PolygonLiteral):
            if value.srid:
                result = GeographyPolygonValue()
            else:
                result = GeometryPolygonValue()
            result.set_value(value)
        elif isinstance(value, geo.MultiPointLiteral):
            if value.srid:
                result = GeographyMultiPointValue()
            else:
                result = GeometryMultiPointValue()
            result.set_value(value)
        elif isinstance(value, geo.MultiLineStringLiteral):
            if value.srid:
                result = GeographyMultiLineStringValue()
            else:
                result = GeometryMultiLineStringValue()
            result.set_value(value)
        elif isinstance(value, geo.MultiPolygonLiteral):
            if value.srid:
                result = GeographyMultiPolygonValue()
            else:
                result = GeometryMultiPolygonValue()
            result.set_value(value)
        elif isinstance(value, geo.GeoCollectionLiteral):
            if value.srid:
                result = GeographyCollectionValue()
            else:
                result = GeometryCollectionValue()
            result.set_value(value)
        else:
            raise TypeError
        return result

    @classmethod
    def from_str(cls, src):
        """Constructs a primitive value from a source string

        This is an abstract method, each primitive type has its own
        parsing rules and its values can only be constructed from
        strings in a typed context.  Contrast this with the method
        :meth:`from_literal`."""
        raise NotImplementedError

    @classmethod
    def from_literal(cls, src):
        """Constructs a primitive value from a literal string

        Literal strings can appear directly in expressions and may or
        may not be explicitly typed.  The ABNF is ambiguous where
        numeric literals are concerned.  You may :meth:`cast` the result
        to the required value type if required."""
        raise NotImplementedError

    def cast(self, type_def):
        """Implements the cast function

        Any primitive type can be cast to a String using the ABNF
        format."""
        if type_def.is_derived_from(edm['String']):
            result = type_def()
            try:
                result.set_value(to_text(self))
            except ValueError:
                # bounds must be exceeded, return typed null
                pass
            return result
        else:
            return super(PrimitiveValue, self).cast(type_def)


class EnumerationType(NameTable, NominalType):

    """An EnumerationType declaration"""

    def __init__(self, base=None, **kwargs):
        super(EnumerationType, self).__init__(**kwargs)
        if base is None:
            base = edm['Int32']
        elif base not in (edm['Byte'], edm['SByte'], edm['Int16'],
                          edm['Int32'], edm['Int64']):
            raise errors.ModelError(errors.Requirement.ent_type_s % base.qname)
        #: whether or not values are being auto-assigned None means
        #: 'undetermined', only possible when there are no members
        self.assigned_values = None
        #: whether or not this type is a flags-based enumeration
        self.is_flags = False
        #: the list of members in the order they were declared
        self.members = []
        # a mapping from values to the first declared member with that
        # value
        self._valuetable = {}
        self.value_type = EnumerationValue
        super(EnumerationType, self).set_base(base)

    def set_is_flags(self):
        """Sets is_flags to True.

        If the Enumeration already has members declared will raise
        ModelError."""
        if self.members:
            raise errors.ModelError(
                "Can't set is_flags on Enumeration with existing members")
        self.assigned_values = False
        self.is_flags = True

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed member")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        if not isinstance(value, Member):
            raise TypeError("Member required, found %s" % repr(value))
        # The value of the Member must be None (for auto assigned) or a
        # valid value of the base type
        if value.value is not None:
            v = self.base()
            try:
                v.set_value(value.value)
            except ValueError as err:
                raise errors.ModelError(
                    errors.Requirement.ent_valid_value_s %
                    ("%s: %s" % (self.qname, str(err))))

    def __setitem__(self, key, value):
        self.check_value(value)
        if self.assigned_values is None:
            self.assigned_values = value.value is None
        if self.assigned_values:
            if value.value is not None:
                raise errors.ModelError(
                    "Enum member %s declared with unexpected value" %
                    value.name)
            value.value = len(self.members)
            try:
                super(EnumerationType, self).__setitem__(key, value)
            except (ValueError, TypeError):
                # remove the auto-assigned value
                value.value = None
                raise
        else:
            if value.value is None:
                if self.is_flags:
                    raise errors.ModelError(
                        errors.Requirement.ent_nonauto_value_s %
                        ("%s:%s" % (self.qname, value.name)))
                else:
                    raise errors.ModelError(
                        errors.Requirement.ent_auto_value_s %
                        ("%s:%s" % (self.qname, value.name)))
            super(EnumerationType, self).__setitem__(key, value)
        self.members.append(value)
        self._valuetable.setdefault(value.value, value)

    def lookup(self, name_or_value):
        """Looks up a Member by name or value

        Returns the :class:`Member` instance.  If name_or_value is not
        the name or the value of a member then ValueError is raised. If
        name_or_value is an integer and multiple Members match then the
        first declared Member is returned."""
        try:
            if is_text(name_or_value):
                return self[name_or_value]
            elif isinstance(name_or_value, (int, long2)):
                return self._valuetable[name_or_value]
            else:
                raise ValueError("integer or string required")
        except KeyError:
            raise ValueError(
                "%s is not defined in %s" % (name_or_value, self.name))

    def lookup_flags(self, value):
        """Returns a list of Members that comprise this value

        For use with Enumerations that have :attr:`is_flags` set to
        True. Returns a compact list of members (in declaration order)
        that combine to make the input value.

        In the simplest case, where flags are defined using 1, 2, 4,
        etc. then this will just be the list of flags corresponding to
        the bits set in value.  In more complex examples where
        Enumerations define Members that combine flags then powerful
        Members are favoured over less powerful ones.  I.e., a Member
        with value 3 will be returned in preference to a list of two
        members with values 1 and 2.

        If :attr:`is_flags` is False, throws TypeError."""
        result = []
        rmask = 0
        for m in self.members:
            if m.value & value == m.value:
                # m is a candidate for adding to the result but does it
                # add any value?  Don't add superfluous multi-flags for
                # the sake of it.
                add_m = (m.value & rmask != m.value)
                i = 0
                while i < len(result):
                    match = result[i]
                    # if match is masked by (but not equal to m) then
                    # remove it from the result.  This rule ensures that
                    # 1 and 2 will be removed in favour or 3
                    if match.value & m.value == match.value:
                        del result[i]
                        # but we better add m now!
                        add_m = True
                    else:
                        i += 1
                if add_m:
                    result.append(m)
                    # expand rmask
                    rmask |= m.value
        return result

    def value_from_str(self, src):
        """Constructs an enumeration value from a source string"""
        p = ODataParser(src)
        v = self()
        mlist = p.require_enum_value()
        if not self.is_flags:
            if len(mlist) != 1:
                raise errors.ModelError(
                    "Enum member: expected single name or value")
            v.set_value(mlist[0])
        else:
            v.set_value(mlist)
        p.require_end()
        return v


class Member(Named):

    """Represents a member of an enumeration"""

    def __init__(self, **kwargs):
        super(Member, self).__init__(**kwargs)
        #: the integer value corresponding to this member
        #: defaults to None: auto-assigned when declared
        self.value = None


class EnumerationValue(Value):

    """Represents the value of an Enumeration type"""

    def __init__(self, type_def, pvalue=None, **kwargs):
        super(EnumerationValue, self).__init__(type_def, **kwargs)
        self.value = None
        if pvalue is not None:
            self.set_value(pvalue)

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        elif self.type_def.is_flags:
            return ul(',').join([v.name for
                                 v in self.type_def.lookup_flags(self.value)])
        else:
            return self.type_def.lookup(self.value).name

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        Accepts None (meaning null), integer, string or iterable objects
        that yield integer and/or strings (mixtures are acceptable).
        Other types raise TypeError.

        Strings and values are converted to enum members through look-up
        and (for flags) bitwise OR operation.  If a value is not
        defined in the enumeration then ValueError is raised.  Note
        that with flags enumerations you may *only* set the (integer) value
        to an integer representing multiple flags *if* that value has
        a defined name.  For example, if you have Red=1 and Blue=2 as
        members then you may::

            v.set_value(1)
            v.set_value(2)
            v.set_value((1, 2))

        however, you may *not*::

            v.set_value(3)

        This rule has implications for the use of 0 which, for a flags
        enumeration, means no flags are set.  You *must* define a member
        with value of 0 if you want to use this value.  E.g., extending
        the above example define Black=0 if you want to do this::

            v.set_value(0)"""
        if value is None:
            self.value = value
        elif is_text(value) or isinstance(value, (int, long2)):
            self.value = self.type_def.lookup(value).value
        elif self.type_def.is_flags:
            # iterate over the values
            total_value = 0
            count = 0
            try:
                for v in value:
                    count += 1
                    total_value |= self.type_def.lookup(v).value
            except TypeError:
                raise TypeError("int, str or iterable thereof required")
            if not count:
                raise ValueError("Enum member name or value expected")
            self.value = total_value
        else:
            raise TypeError("Enum member or value expected")


class CollectionType(NominalType):

    """Collections are treated as types in the model

    In fact, OData does not allow you to declare a named type to be a
    collection, instead, properties, navigation properties and entity
    collections define collections in terms of single-valued named types.

    To make implementing the model easier we treat these as private type
    definitions.  That is, type definitions which are never declared in
    the associated schema but are used as the type of other elements
    that are part of the model."""

    def __init__(self, item_type, **kwargs):
        super(CollectionType, self).__init__(**kwargs)
        #: the type being collected, we do not allow collections of
        #: collections
        self.item_type = item_type
        self.value_type = CollectionValue


class CollectionValue(Annotatable, collections.MutableSequence, Value):

    """Represents the value of a Collection

    The type_def is required on construction.  There is no default
    collection type.

    The CollectionValue object is blessed with Python's Sequence
    behaviour and is also :class:`Annotatable`."""

    def __init__(self, **kwargs):
        super(CollectionValue, self).__init__(**kwargs)
        self._fullycached = True
        self._cache = []

    def bind_to_service(self, service_ref):
        """Binds this CollectionValue to a data service

        This collection must be empty to be bound.

        Once bound, the CollectionValue automatically creates and
        executes requests to the underlying data service and caches the
        resulting information for speed."""
        if self._cache:
            raise errors.ServiceError("Collection must be empty to be bound")
        self._fullycached = False
        self._cache.clear()
        super(CollectionValue, self).bind_to_service(service_ref)

    def clear_cache(self):
        """Clears the local cache for this collection

        If this collection is bound to a service then any locally cached
        information about the entities is cleared."""
        if self.service is not None:
            self._fullycached = False
            del self._cache[:]

    def reload(self):
        """Reload the contents of this collection from source

        This collection must be bound to a service.  The cache is cleared
        and reloaded from the service."""
        if self.service is None:
            raise errors.UnboundValue
        self.clear_cache()
        self._load()

    def is_null(self):
        """CollectionValues are *never* null

        CollectionValues highlight the distinction between the default
        Python boolean test and the OData definition of null.  The
        native Python Sequence behaviour overrides the default
        :class:`Value` implementation of the boolean test.  In other
        words::

            if collection_value:
                # do something if a CollectionValue instance is 'True'

        will test whether or not the collection is empty, not if it's
        null."""
        return False

    def __len__(self):
        if self._fullycached:
            return len(self._cache)
        else:
            # we need to determine our contextual object and iterate it
            raise NotImplementedError

    def _is_cached(self, index):
        if isinstance(index, slice):
            if index.stop is None or index.stop < 0:
                return False
            else:
                return index.stop < len(self._cache)
        elif index < 0:
            return False
        else:
            return index < len(self._cache)

    def _check_type(self, value):
        if not value.type_def.is_derived_from(self.type_def.item_type):
            raise ValueError
        return value

    def __getitem__(self, index):
        if self._fullycached or self._is_cached(index):
            return self._cache[index]
        else:
            self._load(index)
            return self._cache[index]

    def __setitem__(self, index, value):
        if self.frozen:
            raise errors.FrozenValueError
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load(index)
        if isinstance(index, slice):
            # value must be an iterable of appropriate values
            self._cache[index] = [self._check_item(item) for item in value]
        else:
            self._cache[index] = self._check_type(value)
        self.dirty = True

    def __delitem__(self, index):
        if self.frozen:
            raise errors.FrozenValueError
        if isinstance(index, slice):
            if index.stop is None and index.step is None:
                # special case: delete everything past start.  We
                # optimise here as we don't need to load the remote data
                # just to mark it as being deleted, we everything cached
                # that needs to be cached!
                if index.start is None or self._is_cached(index.start):
                    self._fullycached = True
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load(index)
        del self._cache[index]
        self.dirty = True

    def insert(self, index, value):
        if self.frozen:
            raise errors.FrozenValueError
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load(index)
        self._cache.insert(index, value)
        self.dirty = True

    def _load(self, index=None):
        # Load the cache up to and including index,  If index is None
        # then load the entire collection.  We always start from the
        # beginning because the remote data may have changed.
        raise NotImplementedError


class StructuredType(NameTable, NominalType):

    """A Structured Type declaration

    Structured types are nametables in their own right, behaving as
    dictionaries with property names as keys and :class:`Property` (or
    :class:`NavigationProperty`) instances as the dictionary values.

    While the declaration's nametable is open new properties can be
    added but once it is closed the type is considered complete.  There
    are some restrictions on which operations are allowed on
    complete/incomplete type declarations.  The most important being
    that the you can't use a type as a base type until is complete."""

    def __init__(self, **kwargs):
        super(StructuredType, self).__init__(**kwargs)
        #: whether or not this is an open type, None indicates undetermined
        self.open_type = None

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed property")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a name

        By default we qualify name by prefixing with the name of this
        NameTable (type) and "/" as per the representation of property
        paths. If this NameTable has not been declared then name is
        returned unchanged."""
        if self.name:
            return self.name + "/" + name
        else:
            return name

    def check_value(self, value):
        if not isinstance(value, (Property, NavigationProperty)):
            raise TypeError(
                "Property or NavigationProperty required, found %s" %
                repr(value))

    def set_base(self, base):
        """Sets the base type of this type

        When structured types are associated with a base type the
        properties of the base type are copied on closure, therefore the
        type must be incomplete when the base it set and the base MUST
        be closed before the derived type."""
        if not isinstance(base, type(self)):
            raise TypeError(
                "%s is not a suitable base for %s" % (base.qname, self.name))
        if self.closed:
            raise errors.ModelError(
                "Can't set base on %s (declaration is complete)" % self.qname)
        super(StructuredType, self).set_base(base)

    def set_abstract(self, abstract):
        if self.closed:
            raise errors.ModelError(
                "Can't set abstract on %s (declaration is complete)" %
                self.qname)
        self.abstract = abstract

    def set_open_type(self, open_type):
        if self.closed:
            raise errors.ModelError(
                "Can't set open_type on %s (declaration is complete)" %
                self.qname)
        self.open_type = open_type

    def navigation_properties(self):
        """Generates all navigation properties of this type

        This iterator will traverse complex types but *not* collections
        of complex types.  It yields tuples of (path, nav property)."""
        for n, p in self.items():
            if isinstance(p, NavigationProperty):
                yield n, p
            elif isinstance(p.type_def, ComplexType):
                for nn, np in p.type_def.navigation_properties():
                    yield "%s/%s" % (n, nn), np

    def close(self):
        # before we close this nametable, add in the declarataions from
        # the base type if present
        if self.closed:
            return
        if self.base is not None:
            if not self.base.closed:
                raise errors.ModelError(
                    "Base type is incomplete: %s" % self.qname)
            if self.base.open_type is not None:
                if self.base.open_type is True and self.open_type is False:
                    if isinstance(self, EntityType):
                        raise errors.ModelError(
                            errors.Requirement.et_open_base_s % self.qname)
                    elif isinstance(self, ComplexType):
                        raise errors.ModelError(
                            errors.Requirement.ct_open_base_s % self.qname)
                    else:
                        raise errors.ModelError
                if self.open_type is None:
                    self.open_type = self.base.open_type
            else:
                # no base type
                if self.open_type is None:
                    self.open_type = False
            # add the base names
            for pname, p in self.base.items():
                try:
                    p.declare(self, pname)
                except errors.DuplicateNameError:
                    raise errors.DuplicateNameError(
                        errors.Requirement.property_unique_s %
                        ("%s/%s" % (self.qname, pname)))
        # The types of all our structural properties MUST also be
        # complete.
        for pname, p in self.items():
            if isinstance(p, Property):
                t = p.type_def
                if t is None:
                    raise errors.ModelError("%s is undefined" % p.qname)
                if isinstance(t, CollectionType):
                    t = t.item_type
                if isinstance(t, StructuredType) and not t.closed:
                    raise errors.ModelError("%s is incomplete" % p.qname)
        super(StructuredType, self).close()

    def set_annotations(self):
        """Called during EntityModel closure

        Properties that refer to TypeDefinitions need to have
        annotations copied as these Annotations "are considered applied
        wherever the type definition is used".
        """
        try:
            for pname, p in self.items():
                if isinstance(p, Property):
                    if not p.is_owned_by(self):
                        # inherited
                        continue
                    t = p.type_def
                    if isinstance(t, CollectionType):
                        t = t.item_type
                    # this type is just the wrapper of the real type
                    t = t.base
                    if isinstance(t, PrimitiveType):
                        logging.debug("Checking %s for annotations", t.qname)
                        for annotation in t.annotations.values():
                            logging.debug(
                                "Annotating %s with %s", p.qname,
                                annotation.name)
                            annotation.declare(p.annotations, annotation.name)
        except errors.DuplicateNameError as err:
            raise errors.ModelError(
                errors.Requirement.td_annotation_s % to_text(err))

    def resolve_sproperty_path(self, path, inheritance=True):
        """Resolves a property path

        path
            An array of strings representing the path.  There must be at
            least one segment.

        inheritance (default True)
            Whether or not to search inherited properties.  By default
            we do search them, the use cases for searching the set of
            limited properties defined by this entity type itself are
            limited to validation scenarios.  This restriction applies
            to the entity being searched, not to the types of complex
            properties (if any).

        This method will not resolve qualified names in the path so all
        items MUST be simple identifiers representing properties defined
        in the correspondig structural type.  In the simplest case path
        will comprise a single identifier of a primitive property but it
        may refer to complex properties (recursively) though not
        properties of derived complex properties.  The path MUST NOT
        include navigation properties.

        The upshot is that we return a property declaration of a
        structural property that is guaranteed to be valid for all
        instances of this structural type.

        This method can only be called once the type is complete."""
        if not self.closed:
            raise errors.ModelError("%s is incomplete" % self.qname)
        if not path:
            raise ValueError("Can't resolve empty property path")
        pos = 0
        t = self
        p = None
        try:
            while pos < len(path):
                logging.debug("resolve_sproperty_path searching in %s for %s",
                              t.qname, str(path[pos:]))
                if isinstance(t, CollectionType):
                    raise errors.PathError(
                        "%s is a collection" % p.qname)
                segment = path[pos]
                pos += 1
                if is_text(segment):
                    # must resole to a property of the current type
                    p = t[segment]
                    if isinstance(p, NavigationProperty):
                        raise errors.PathError(
                            "%s is a navigation property" % p.qname)
                    if not inheritance:
                        if not p.is_owned_by(t):
                            raise errors.PathError("%s is inherited" % p.qname)
                        inheritance = True
                    t = p.type_def
                else:
                    raise TypeError(
                        "Bad path segment %s" % repr(segment))
        except KeyError as err:
            raise errors.PathError("Path segment not found: %s" % str(err))
        return p

    def resolve_nppath(self, path, context, follow_containment=False,
                       require_containment=False):
        """Resolves a navigation property path

        path
            A list of strings and QualifiedName instances representing
            the path.  Any redundant segments are removed from the path
            during resolution ensuring that, on success, it is the
            canonical path to the returned navigation property.

        context
            The entity model within which to resolve qualified names.
            This won't necessarily be the entity model containing the
            definition of the EntityType itself as the type may be used
            through a reference in a separate schema that defines
            addition sub-types, changing the outcome of the path
            resolution algorithm.

        follow_containment
            A boolean, defaulting to False: don't traverse containinment
            navigation properties.  In this configuration the method
            behaves as per the resolution of partner paths in entity
            type definitions.  When set to True containment navigation
            properties are traversed (but will only be returned subject
            to require_containment below) as per the resolution of
            navigation binding paths.

        require_containment
            A boolean, defaulting to False: the resulting path must be a
            containment navigation property.  With both
            follow_containment and require_containment set the method
            behaves as per the resolution of a target path (excluding
            the entity set or singleton segments).

        The rules for following navigation property paths are different
        depending on the context. In Part 3, 7.1.4 they are defined
        as follows:

            The path may traverse complex types, including derived
            complex types, but MUST NOT traverse any navigation
            properties

        Whereas in Part 3, 13.4.1:

            The path can traverse one or more containment navigation
            properties but the last segment MUST be a non-containment
            navigation property and there MUST NOT be any
            non-containment navigation properties prior to the final
            segment"""
        pos = 0
        old_type = None
        from_type = self
        try:
            while pos < len(path):
                segment = path[pos]
                pos += 1
                if is_text(segment):
                    # must resolve to a property of this type
                    p = from_type[segment]
                    if old_type is not None:
                        # check the previous cast
                        best_type = from_type
                        base_type = from_type.base
                        while (best_type is not old_type and
                                segment in base_type):
                            best_type = base_type
                            base_type = base_type.base
                        if best_type is old_type:
                            # unnecessary cast
                            pos -= 1
                            del path[pos - 1]
                            from_type = old_type
                        elif best_type is not from_type:
                            # cast was over-specific, modify it
                            path[pos - 2] = best_type.get_qname()
                            from_type = best_type
                        old_type = None
                    if isinstance(p, NavigationProperty):
                        if follow_containment:
                            # navigation binding path
                            if p.containment:
                                if pos >= len(path):
                                    if require_containment:
                                        return p
                                    # or last segment can't be containment
                                    raise errors.ModelError(
                                        errors.Requirement.
                                        nav_contains_binding_s % self.qname)
                                from_type = p.entity_type
                                # continue to resolve
                            else:
                                # must be last segment
                                if pos < len(path):
                                    raise errors.ModelError(
                                        errors.Requirement.
                                        navbind_noncontain_s % self.qname)
                                if require_containment:
                                    raise errors.PathError(self.qname)
                                return p
                        else:
                            # partner path
                            if pos < len(path):
                                raise errors.ModelError(
                                    errors.Requirement.nav_partner_nav_s %
                                    p.name)
                            return p
                    else:
                        from_type = p.type_def
                        # must be a structured type, not a primitive or
                        # collection
                        if not isinstance(from_type, StructuredType):
                            raise errors.PathError(
                                "Can't resolve path containing: %s" %
                                repr(from_type))
                elif isinstance(segment, QualifiedName):
                    # a type-cast
                    new_type = context.qualified_get(segment)
                    if not isinstance(new_type, StructuredType):
                        raise errors.PathError(
                            "Can't resolve path containing: %s" %
                            repr(new_type))
                    if new_type.is_derived_from(from_type, strict=False):
                        # any derived type or the same type at this stage
                        old_type = from_type
                        from_type = new_type
                    else:
                        raise errors.PathError(
                            "Can't resolve cast from %s to %s" %
                            (from_type.qname, new_type.qname))
                else:
                    raise TypeError(
                        "Bad path segment %s" % repr(segment))
        except KeyError as err:
            raise errors.PathError("Path segment not found: %s" % str(err))
        # if we get here then the path finished at a complex property
        # or type-cast segment.
        raise errors.PathError("Path did not resolve to a navigation property")

    @staticmethod
    def path_to_str(path):
        """Static method for converting a path to a string

        path
            An array of strings and/or :class:`QualifiedName` named
            tuples.

        Returns a simple string representation with all components
        separated by "/"
        """
        return "/".join(
            [segment if is_text(segment) else
             (segment.namespace + "." + segment.name) for segment in path])


class Property(Annotatable, Named):

    """A Property declaration"""

    def __init__(self, **kwargs):
        super(Property, self).__init__(**kwargs)
        #: the type definition for values of this property
        self.type_def = None
        #: whether or not the property value can be null (or contain
        #: null in the case of a collection)
        self.nullable = True
        #: the default value of the property (primitive/enums only)
        self.default_value = None

    def set_type(self, type_def):
        self.type_def = type_def

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_default(self, default_value):
        self.default_value = default_value

    def __call__(self, parent_ref):
        value = self.type_def()
        if self.default_value:
            value.assign(self.default_value)
            value.clean()
        value.set_parent(parent_ref, self.name)
        return value


class OnDeleteAction(xsi.Enumeration):

    """An enumeration used to represent OnDelete actions.
    ::

            OnDeleteAction.Cascade
            OnDeleteAction.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "Cascade": 1,
        "None": 2,
        "SetNull": 3,
        "SetDefault": 4
    }


class NavigationProperty(Named):

    """A NavigationProperty declaration"""

    def __init__(self, **kwargs):
        super(NavigationProperty, self).__init__(**kwargs)
        #: the target entity type of this property
        self.entity_type = None
        #: whether or not this property points to a collection
        self.collection = None
        #: by default, navigation properties are nullable
        self.nullable = None
        #: whether of not the linked entities are contained
        self.containment = False
        #: the partner of this navigation property
        self.partner = None
        #: reverse partners are navigation properties that point back to
        #: us, there can be more than one but if the relationship is
        #: bidirectional there will *exactly* one and it will be the
        #: same object as self.partner.
        self.reverse_partners = []

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_containment(self, contains_target):
        self.containment = contains_target

    def set_type(self, entity_type, collection):
        self.entity_type = entity_type
        if collection:
            if self.nullable is not None:
                raise errors.ModelError(
                    errors.Requirement.nav_collection_exists_s % self.qname)
        else:
            if self.nullable is None:
                self.nullable = True
        self.collection = collection

    def set_partner(self, partner):
        if self.reverse_partners:
            if len(self.reverse_partners) > 1:
                raise errors.ModelError(
                    errors.Requirement.nav_partner_bidirection_s %
                    ("%s has multiple partners" % self.qname))
            if self.reverse_partners[0] is not partner:
                raise errors.ModelError(
                    errors.Requirement.nav_partner_bidirection_s %
                    ("%s is already partnered" % self.qname))
        self.partner = partner
        partner.reverse_partners.append(self)

    def add_constraint(self, dependent_path, principal_path):
        if self.nametable is None:
            raise errors.ObjectNotDeclaredError
        dependent_entity = self.nametable()
        principal_entity = self.entity_type
        try:
            dependent_property = dependent_entity.resolve_sproperty_path(
                dependent_path)
        except errors.PathError as err:
            raise errors.ModelError(
                errors.Requirement.refcon_ppath_s %
                ("%s: %s" % (self.qname, str(err))))
        try:
            principal_property = principal_entity.resolve_sproperty_path(
                principal_path)
        except errors.PathError as err:
            raise errors.ModelError(
                errors.Requirement.refcon_rppath_s %
                ("%s: %s" % (self.qname, str(err))))
        # these must be primitive properties
        if not isinstance(dependent_property.type_def, PrimitiveType):
            raise errors.ModelError(
                errors.Requirement.refcon_ppath_s % self.qname)
        # the types of these properties MUST match
        if not dependent_property.type_def.match(principal_property.type_def):
            raise errors.ModelError(
                errors.Requirement.refcon_match_s % self.qname)
        if ((self.nullable is True or principal_property.nullable is True) and
                dependent_property.nullable is False):
            raise errors.ModelError(
                errors.Requirement.refcon_match_null_s % self.qname)
        if ((self.nullable is False and
                principal_property.nullable is False) and
                dependent_property.nullable is not False):
            raise errors.ModelError(
                errors.Requirement.refcon_match_notnull_s % self.qname)

    def add_action(self, action):
        pass

    def __call__(self, parent_ref):
        p = parent_ref()
        path = [self.name]
        if self.name not in p.base_def:
            path.insert(0, p.nametable().qname)
        entity = p.get_entity(path)
        if not self.containment and entity.entity_set is not None:
            target_set = entity.entity_set.resolve_binding(tuple(path))
        else:
            target_set = None
        if self.collection:
            if self.containment:
                # this value defines an entity set in its own right
                value = EntitySetValue(type_def=self.entity_type)
            else:
                if target_set is None:
                    # unbound navigation, can't assume an entity set
                    value = CollectionType(self.entity_type)()
                else:
                    value = EntitySetValue(
                        type_def=self.entity_type, entity_set=target_set)
        else:
            # a single entity (related to the parent)
            value = EntityValue(
                type_def=self.entity_type, entity_set=target_set)
        return value.set_parent(parent_ref)


class StructuredValue(collections.MutableMapping, Annotatable, Value):

    """Abstract class that represents the value of a structured type

    Instances behave like dictionaries of property values keyed on
    property name.

    Instances may be null, this can be achieved using set(None).  They
    are created in a non-null state with all properties set to default
    values.

    The type definition used to create a structured value instance is
    considered special and is remembered as the :attr:`base_def` of the
    value throughout the value's life.  The actual type may change to a
    value derived from it but it may never be changed to a type that is
    more abstract."""

    def __init__(self, **kwargs):
        super(StructuredValue, self).__init__(**kwargs)
        #: the base type definition that controls the value space
        self.base_def = self.type_def
        self.null = False
        self._pvalues = {}
        self_ref = weakref.ref(self)
        for pname, ptype in self.type_def.items():
            # we call Property instances to create values
            if isinstance(ptype, Property):
                self._pvalues[pname] = ptype(self_ref)

    def __len__(self):
        return len(self._pvalues)

    def __getitem__(self, key):
        return self._pvalues[key]

    def __setitem__(self, key, value):
        if self.frozen:
            raise errors.FrozenValueError
        raise NotImplementedError

    def __delitem__(self, key):
        if self.frozen:
            raise errors.FrozenValueError
        raise NotImplementedError

    def __iter__(self):
        for k in self._pvalues:
            yield k

    def is_null(self):
        """Returns True if this object is null."""
        return self.null

    def clear_null(self):
        """Marks this value as being non-null"""
        if self.frozen:
            raise errors.FrozenValueError
        self.null = False
        self.dirty = True

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        Anything other than None raises TypeError.  Setting a structured
        value to null removes all properties from the dictionary and
        sets the :attr:`dirty` flag."""
        if self.frozen:
            raise errors.FrozenValueError
        if value is None:
            self.null = True
            self._pvalues.clear()
            self.dirty = True
        else:
            raise TypeError

    def assign(self, value):
        """Sets this value from another Value instance.

        If value is null then this instance is set to null.  Otherwise
        the incoming value must be of the same type, or a type derived
        from, the object being assigned.  The values of all properties
        present in the dictionary are assigned from the values with the
        same name in the other value instance.  Missing values are set
        to null.

        The assign operation does not change the type of a value.  You
        can do that using :meth:`set_type`."""
        if self.frozen:
            raise errors.FrozenValueError
        if value.is_null():
            self.set_value(None)
        elif value.type_def.is_derived_from(self.type_def):
            for pname, pvalue in self.items():
                new_value = value.get(pname, None)
                if new_value is None:
                    pvalue.set(None)
                else:
                    pvalue.assign(new_value)
            self.clear_null()
            self.dirty = True
        else:
            return super(StructuredValue, self).assign(value)

    def set_type(self, type_def):
        """Sets the type of this value

        type_def
            An instance of :class:`StructuredType` that *must* be in the
            same type hierarchy as the existing type and *must* be
            derived from the :attr:`base_def` used to create the value.

        This function is used to implement a dynamic type-cast such as
        when an entity (or complex value) is cast to a type derived from
        the type stipulated by the original declaration.

        If the new type is derived from the *current* type then any
        additional structural properties defined only in the derived
        type are created in the property diectionary with null/default
        values and marked clean.

        If the current type is derived from the new type then the change
        is to a more general value and any properties that are not
        defined in the new type are *removed* from the property
        dictionary."""
        if self.frozen:
            raise errors.FrozenValueError
        if type_def is self.type_def:
            # nothing to do
            return
        if not type_def.is_derived_from(self.base_def):
            raise TypeError("Incompatible types: %s -> %s" %
                            (self.base_type.qname, type_def.qname))
        if type_def.is_derived_from(self.type_def, strict=True):
            # we are extending this value, need to add missing properties
            old_def = self.type_def
            self.type_def = type_def
            self_ref = weakref.ref(self)
            for pname, ptype in self.type_def.items():
                if pname in old_def:
                    continue
                if isinstance(ptype, Property):
                    self._pvalues[pname] = ptype(self_ref)
        else:
            old_def = self.type_def
            self.type_def = type_def
            # we are re-generalizing this value so remove some properties
            for pname in old_def:
                if pname in self.type_def:
                    continue
                if pname in self._pvalues:
                    del self._pvalues[pname]
        self.dirty = True

    def bind_to_service(self, service_ref):
        """Binds this value to a specific OData service

        Binds all properties recursively."""
        if self.service is not None:
            raise errors.ModelError("Value is already bound" % to_text(self))
        self.service = service_ref
        for pvalue in self._pvalues.values():
            if isinstance(pvalue, EntityValue) and pvalue.service is not None:
                # it's OK for a navigation property in an unbound value
                # to be bound to an entity that is already bound (e.g.,
                # while waiting for a deep insert operation).
                continue
            pvalue.bind_to_service(service_ref)

    def get_entity(self, path, ignore_containment=True):
        """Returns the entity that contains this structured value

        For values with no parent entity, None is returned; for
        entities, the current object is returned and for complex values
        the chain of parents is followed until an entity is found (by
        calling get_entity recursively).

        path
            A list of strings that will be updated to represent the path
            to this value by pre-pending the required path segments to
            navigate from the context of the entity returned back to
            this value.

        ignore_containment
            If True (the default) then an entity that is contained by a
            parent entity (by a containment navigation property) will
            not be returned and the method will continue to follow the
            chain of parents until an entity that is not contained is
            found.

        For example, if an entity has a complex property with name 'A'
        then calling get_entity on the value of A returns the entity and
        pre-pends 'A' to path.

        More complex situations requiring type-casts are also handled.
        To extend the previous example, if the entity in question is of
        type Y, derived from type X, and is in an entity set or
        collection declared to be of type X *and* the property A is
        defined only for type Y, then a type cast segment is also
        pre-prended.  The path list will then start: ['schema.Y',
        'A',...].

        The upshot is that path is prefixed with the target path of this
        value. This path could then be used in expressions that require
        a property path."""
        # TODO: traversing entities contained in entity sets (rather
        # than as single entities) does not include the key in the path
        if self.parent_ref is None:
            return None
        p = self.parent_ref()
        path.insert(0, self.name)
        if self.type_cast:
            path.insert(0, self.type_cast)
        return p.get_entity(path)


class ComplexType(StructuredType):

    """A ComplexType declaration"""

    def __init__(self, **kwargs):
        super(ComplexType, self).__init__(**kwargs)
        self.value_type = ComplexValue

    def check_name(self, name):
        """Overridden to add a check against the declared name"""
        if self.name is not None and self.name == name:
            raise ValueError(errors.Requirement.ct_same_name_s % name)
        super(ComplexType, self).check_name(name)

    def __setitem__(self, key, value):
        if isinstance(value, Named) and value.is_owned_by(self):
            # we own this property, it must not share our name
            if self.name is not None and self.name == value.name:
                raise ValueError(errors.Requirement.ct_same_name_s % self.name)
        return super(ComplexType, self).__setitem__(key, value)


class ComplexValue(StructuredValue):

    """Represents the value of a Complex type

    Instances behave like dictionaries of property values."""

    def __init__(self, type_def=None, **kwargs):
        if type_def is not None and not isinstance(type_def, ComplexType):
            raise errors.ModelError(
                "ComplexValue required ComplexType: %s" % repr(type_def))
        super(ComplexValue, self).__init__(
            type_def=edm['ComplexType'] if type_def is None else type_def,
            **kwargs)


class EntityType(StructuredType):

    """An EntityType declaration"""

    def __init__(self, **kwargs):
        super(EntityType, self).__init__(**kwargs)
        self.value_type = EntityValue
        #: This entity type's key.  This attribute is only set if the
        #: key is defined by this entity type itself, keys can also
        #: be inherited.
        self.key = []
        #: A dictionary mapping the short name of each key property to a
        #: tuple of (path, Property) where path is an array of simple
        #: identifier strings and Property is the declaration of the
        #: property.
        self.key_dict = {}
        #: whether or not instances of this EntityType are contained
        #: None indicates undetermined.
        self.contained = None

    def check_name(self, name):
        """Overridden to add a check against the declared name"""
        if self.name is not None and self.name == name:
            raise ValueError(errors.Requirement.et_same_name_s % name)
        super(EntityType, self).check_name(name)

    def __setitem__(self, key, value):
        if isinstance(value, Named) and value.is_owned_by(self):
            # we own this property, it must not share our name
            if self.name is not None and self.name == value.name:
                raise ValueError(errors.Requirement.et_same_name_s % self.name)
        return super(EntityType, self).__setitem__(key, value)

    def declare(self, nametable, name):
        """Overridden to add a check against the declared name"""
        p = self.get(name, None)
        if p is not None and p.is_owned_by(self):
            # A property we own cannot share our name
            raise ValueError(errors.Requirement.et_same_name_s % name)
        super(EntityType, self).declare(nametable, name)

    def add_key(self, path, alias=None):
        if self.closed:
            raise errors.ModelError(
                "Can't add key to complete EntityType %s" % self.qname)
        if len(path) > 1:
            # this is a complex path, alias is required
            if alias is None:
                raise errors.ModelError(
                    errors.Requirement.key_alias_s %
                    ("%s: %s" % (self.qname, "/".join(path))))
        else:
            if alias is not None:
                raise errors.ModelError(
                    errors.Requirement.key_noalias_s %
                    ("%s: %s" % (self.qname, alias)))
            alias = path[0]
        # we'll check the validity of the key itself on closure
        self.key.append((alias, path))

    def key_defined(self):
        """Returns True if this type defines or inherits a key"""
        t = self
        while isinstance(t, EntityType):
            if t.key:
                return True
            else:
                t = t.base
        return False

    def set_contained(self):
        """Marks this entity type as being contained by another.

        This property is inherited and can only be set once within an
        entity type hierarchy.  The property can only be set *after* the
        type has been closed (ensuring the entity hierarchy is complete
        back to the root)"""
        if not self.closed:
            raise errors.ModelError(
                "Can't set contained on incomplete type %s" % self.qname)
        if self.contained is False:
            # a derived type has already indicated containment
            raise errors.ModelError(
                errors.Requirement.nav_multi_contains_s % self.qname)
        t = self.base
        while isinstance(t, EntityType):
            if t.contained:
                raise errors.ModelError(
                    errors.Requirement.nav_multi_contains_s % self.qname)
            else:
                t.contained = False
                t = t.base
        self.contained = True

    def close(self):
        """Overridden to catch additional EntityType constraints"""
        if not self.abstract and not self.key_defined():
            raise errors.ModelError(
                errors.Requirement.et_abstract_key_s % self.qname)
        if self.base is not None:
            # if we are abstract, our base MUST also be abstract
            if self.abstract and not self.base.abstract:
                raise errors.ModelError(
                    errors.Requirement.et_abstract_base_s % self.qname)
            if self.key and self.base.key_defined():
                raise errors.ModelError(
                    errors.Requirement.et_abstract_no_key_s % self.qname)
        # Now ready to close
        super(EntityType, self).close()
        # Post-closure validity checks...
        for name, path in self.key:
            try:
                kp = self.resolve_sproperty_path(path, inheritance=False)
            except errors.PathError as err:
                raise errors.ModelError(
                    errors.Requirement.key_path_s %
                    ("%s: %s" % (self.qname, str(err))))
            if isinstance(kp.type_def, EnumerationType) or (
                    isinstance(kp.type_def, PrimitiveType) and
                    issubclass(kp.type_def.value_type, (
                        BooleanValue, DateValue,
                        DateTimeOffsetValue, DecimalValue,
                        DurationValue, GuidValue, IntegerValue,
                        StringValue, TimeOfDayValue))):
                if kp.nullable:
                    raise errors.ModelError(
                        errors.Requirement.key_nullable_s % kp.qname)
                if len(path) > 1 and (name in self or name in self.key_dict):
                    raise errors.ModelError(
                        errors.Requirement.key_alias_unique_s % name)
                # this one's OK
                self.key_dict[name] = (path, kp)
            else:
                raise errors.ModelError(
                    errors.Requirement.key_type_s % kp.qname)


class EntityValue(StructuredValue):

    """Represents the value of an Entity type, i.e., an Entity.

    entity_set
        An optional EntitySet that contains this value."""

    def __init__(self, type_def=None, entity_set=None, **kwargs):
        if type_def is not None and not isinstance(type_def, EntityType):
            raise errors.ModelError(
                "EntityValue requires EntityType: %s" % repr(type_def))
        super(EntityValue, self).__init__(
            type_def=edm['EntityType'] if type_def is None else type_def,
            **kwargs)
        self.entity_set = entity_set

    def get_entity(self, path, ignore_containment=True):
        """Returns self

        See: :meth:`StructuredType.get_entity` for more information."""
        if self.parent_ref is None or not ignore_containment:
            return self
        else:
            return super(EntityValue, self).get_entity(
                path, ignore_containment)

    def get_path(self, path):
        """Returns the value of the property pointed to by path

        path
            A list of strings."""
        v = self
        for p in path:
            v = self[p]
        return v

    def get_key(self):
        """Returns this entity's key (as a tuple if composite)"""
        t = self.type_def
        key = None
        while isinstance(t, EntityType):
            if t.key:
                key = t.key
                break
            else:
                t = t.base
        if not key:
            raise errors.ModelError("Entity has no key!")
        if len(key) > 1:
            return tuple(self.get_path(p).value for a, p in key)
        else:
            return self.get_path(key[0][1]).value

    def get_read_url(self):
        """Returns the read URL of this entity

        If this is a transient entity, None is returned."""
        raise NotImplementedError

    def get_edit_url(self, path=None):
        """Returns the edit URL of this entity.

        path
            A property path, if None the edit URL of the entity itself
            is returned.

        If this is a transient entity, None is returned."""
        raise NotImplementedError


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


class EntityContainer(NameTable):

    """An EntityContainer is a container for OData entities."""

    def __init__(self, **kwargs):
        super(EntityContainer, self).__init__(**kwargs)
        #: the entity container we are extending
        self.extends = None

    def check_name(self, name):
        """Checks the validity of 'name' against SimpleIdentifier

        Raises ValueError if the name is not valid (or is None).

        From the spec:

            The edm:EntityContainer element MUST provide a unique
            SimpleIdentifier value for the Name attribute."""
        if name is None:
            raise ValueError("unnamed container")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def check_value(self, value):
        """The following types may be declared in an EntityContainer:

        EntitySet, Singleton, ActionImport and FunctionImport."""
        if not isinstance(value, (EntitySet, Singleton)):
            raise TypeError(
                "%s can't be declared in %s" %
                (repr(value),
                 "<EntityContainer>" if self.name is None else self.name))

    def set_extends(self, extends):
        """Sets the container that this container extends"""
        if not isinstance(extends, EntityContainer):
            raise TypeError(
                "%s must be an entity container" % extends.qname)
        self.extends = extends

    def close(self):
        # before we close this nametable, add in the declarataions from
        # the extended container if present
        logging.debug("Closing EntityContainer %s", self.qname)
        if self.extends is not None:
            for name, item in self.extends.items():
                # we tolerate cycles, which means that if an item is
                # already declared we ignore it
                old_item = self.get(name, None)
                if old_item is item:
                    continue
                self[name] = item
        super(EntityContainer, self).close()
        # resolve the navigation bindings of each entity set relative
        # to the defining model.
        model = self.get_model()
        for name, item in self.items():
            if isinstance(item, EntitySet):
                item.bind_navigation(model)

    def get_model(self):
        """Returns the entity model that defines this container.

        The container must have been declared within a Schema which, in
        turn, must have been declared within an EntityModel.  Otherwise
        None is returned."""
        if self.nametable is not None:
            schema = self.nametable()
            return schema.get_model()


class NavigationBinding(object):

    """Represents a navigation property binding"""

    def __init__(self):
        #: the navigation property path
        self.np_path = None
        #: the navigation property definition
        self.np = None
        #: the target (an EntitySet or Singleton)
        self.target = None
        #: the target path within instances of the target
        self.target_path = None


class EntitySet(Named):

    """Represents an EntitySet in the OData model."""

    def __init__(self, **kwargs):
        super(EntitySet, self).__init__(**kwargs)
        #: the entity type of the entities in this set
        self.entity_type = None
        #: the service we're bound to
        self.service = None
        #: whether to advertise in the service document
        self.in_service = True
        self._nb_list = []
        #: navigation bindings, mapping from path tuple to
        #: NavigationBinding instance
        self.navigation_bindings = {}
        # the URL of this entity set
        self.url = None

    def set_type(self, entity_type):
        """Sets the entity type for this entity set

        The entity_type must be closed before it can be used as the type
        of an entity set."""
        if not entity_type.closed:
            raise errors.ModelError(
                "Type %s is still open" % entity_type.qname)
        if not entity_type.key_defined():
            raise errors.ModelError(
                errors.Requirement.entity_set_abstract_s % self.qname)
        self.entity_type = entity_type

    def set_in_service(self, in_service):
        """Sets whether or not to advertise this entity set

        in_service
            Boolean value, True meaning advertise in the service
            document"""
        self.in_service = in_service

    def add_navigation_binding(self, path, target):
        """Adds a navigation binding to this entity set

        path
            An array of strings/QualifiedName instances that define a
            path to the navigation property being bound.

        target
            An array of strings that define a path to the target entity
            set."""
        nb = NavigationBinding()
        nb.np_path = path
        nb.target_path = target
        self._nb_list.append(nb)

    def bind_navigation(self, model):
        """Binds navigation paths to target entity sets

        This method is called when the enclosing EntityContainer is
        closed but we must wait for the model itself to close before we
        can resolve the navigation bindings to ensure that qualified
        names can be resolved in the paths."""

        def model_closed():
            logging.debug("Resolving EntitySet bindings for %s", self.qname)
            if self.entity_type is None:
                raise errors.ModelError("%s has no EntityType" % self.qname)
            for nb in self._nb_list:
                try:
                    self.entity_type.resolve_nppath(
                        nb.np_path, model, follow_containment=True)
                    # freeze the path into a tuple
                    nb.np_path = tuple(nb.np_path)
                    if nb.np_path in self.navigation_bindings:
                        raise errors.ModelError(
                            errors.Requirement.navbinding_unique_s % (
                                self.qname + "/" +
                                StructuredType.path_to_str(nb.np_path)))
                    nb.target = self.resolve_target_path(
                        nb.target_path, model)
                    logging.debug("Binding %s to %s/%s", to_text(nb.np_path),
                                  nb.target.qname,
                                  StructuredType.path_to_str(nb.target_path))
                    self.navigation_bindings[nb.np_path] = nb
                except errors.PathError as err:
                    # takes care of most of our constraints at once
                    raise errors.ModelError(
                        errors.Requirement.navbinding_path_s % to_text(err))

        if self.nametable is not None:
            model = self.nametable().get_model()
            model.tell_close(model_closed)

    def resolve_target_path(self, path, context):
        """Resolves a target path relative to this entity set

        path
            A list of string and/or :class:`QualifiedName` that resolves
            to an entity set.  Redundant path segments will be removed
            so that this becomes a canonical path on return (see below).

        context
            The model within which to resolve qualified names.

        Returns the EntitySet or Singleton object the path resolves to
        and updates path so that it contains a path from that item's
        entity type to the target containment navigation property.  The
        path list will be empty on return if the target is the EntitySet
        or Singleton itself."""
        if self.name is None or self.nametable is None:
            return errors.ObjectNotDeclaredError
        if len(path) == 1 and is_text(path[0]):
            # a SimpleIdentifier, must be in the same container
            container = self.nametable()
            if path[0] not in container:
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s" % (self.qname, path[0])))
            target = container[path[0]]
            del path[0]
            return target
        else:
            # a QualifiedName refers to a container, it must be followed
            # by the simple identifier of an EntitySet or a Singleton
            if len(path) < 2 or not isinstance(path[0], QualifiedName) or \
                    not is_text(path[1]):
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s" %
                     (self.qname, StructuredType.path_to_str(path))))
            try:
                container = context.qualified_get(path[0])
                target = container[path[1]]
                del path[0:2]
                if len(path):
                    # we need to find a containment navigation property
                    # we don't need to retain the definition at this point
                    target.entity_type.resolve_nppath(
                        path, context, follow_containment=True,
                        require_containment=True)
                return target
            except errors.PathError as err:
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    to_text(err))
            except KeyError as err:
                raise errors.ModelError(
                    errors.Requirement.navbinding_simple_target_s %
                    ("%s => %s (%s)" %
                     (self.qname, StructuredType.path_to_str(path),
                      to_text(err))))

    def resolve_binding(self, path):
        """Returns the target entity set of a navigation property

        path
            A tuple of strings that specifies the canonical path to the
            navigation property."""
        nb = self.navigation_bindings(path)
        return nb.target

    def bind_to_service(self, service_ref):
        """Binds this EntitySet to an data service

        service_ref
            A weak reference to the service

        An EntitySet can only be bound to a single service."""
        self.service = service_ref

    def get_url(self):
        """Return a URI for this entity set

        An EntitySet has a URL if it is advertised by the service,
        otherwise it does not have a URL and None is returned.  By
        default the URI is a relative URI consisting of just the entity
        set name.  The default url may be overridden using
        :meth:`set_url`."""
        if not self.in_service:
            return None
        elif self.url is not None:
            return self.url
        else:
            return uri.URI.from_octets(
                uri.escape_data(self.name.encode('utf-8')))

    def set_url(self, url):
        if not self.in_service:
            raise errors.ModelError("EntitySet not advertised in service")
        else:
            self.url = url

    def open(self):
        """Opens this EntitySet

        Returns an EntitySetValue bound to the same service as the
        EntitySet."""
        esv = EntitySetValue(entity_set=self, type_def=self.entity_type)
        if self.service is not None:
            esv.bind_to_service(self.service)
        return esv


class EntitySetValue(collections.Mapping, Value):

    """Represents the value of an entity set

    This class is used to represent *any* set of entities.  This could
    be the set of entities exposed directly by an EntitySet in a
    service's container or a restricted set of entities obtained by
    navigation.  You can even instantiate it directly to create a
    temporary entity set that is not backed by a data service at all.

    The implementation inherits from Python's abstract MutableMapping
    with the Entity keys as keys and the Entity instances as values.
    The difference between an ordinary mapping and an EntitySet is that
    iterating the items results in a predictable order."""

    def __init__(self, entity_set=None, **kwargs):
        super(EntitySetValue, self).__init__(**kwargs)
        self.entity_set = entity_set
        self._fullycached = True
        self._keys = []
        self._cache = {}

    def bind_to_service(self, service_ref):
        """Binds this EntitySetValue to a data service

        This entity set value must be empty to be bound.

        Once bound, the EntitySetValue automatically creates and
        executes requests to the underlying data service and caches the
        resulting information for speed."""
        if self._keys:
            raise errors.ServiceError(
                "EntitySetValue must be empty to be bound")
        self._fullycached = False
        self._cache.clear()
        super(EntitySetValue, self).bind_to_service(service_ref)

    def clear_cache(self):
        """Clears the local cache for this entity set

        If this entity set value is bound to a service then any locally
        cached information about the entities is cleared.  If not, it
        does nothing."""
        if self.service is not None:
            self._fullycached = False
            self._cache.clear()
            del self._keys[:]

    def __len__(self):
        if self._fullycached:
            return len(self._keys)
        else:
            request = self.service().get_item_count(self)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            return request.result

    def __getitem__(self, key):
        result = self._cache.get(key, None)
        if result is None:
            if self._fullycached:
                raise KeyError
            else:
                # cache fault, load from source
                raise NotImplementedError
        return result

    def __iter__(self):
        if self._fullycached:
            for k in self._keys:
                yield k
        else:
            self._keys = []
            request = self.service().get_entity_collection(self)
            while request is not None:
                request.execute_request()
                if isinstance(request.result, Exception):
                    raise request.result
                # the result is a list of entities
                for e in request.result:
                    k = e.get_key()
                    self._keys.append(k)
                    self._cache[k] = e
                    yield k
                request = request.next_request

    def get_url(self):
        """Returns the context URL for this entity collection"""
        return self.entity_set.get_url()


class Singleton(Named):

    """Represents a Singleton in the OData model."""

    def __init__(self, **kwargs):
        super(Singleton, self).__init__(**kwargs)
        #: the entity type of this entity
        self.entity_type = None
        # the URL of this entity set
        self.url = None

    def set_type(self, entity_type):
        """Sets the entity type for this entity

        The entity_type must be closed before it can be used as the type
        of a singleton."""
        if not entity_type.closed:
            raise errors.ModelError(
                "Type %s is still open" % entity_type.qname)
        self.entity_type = entity_type

    def get_url(self):
        """Return a URI for this singleton

        Singletons are always advertised by the service so always have a
        URL.  By default the URI is a relative URI consisting of just
        the singleton's name.  The default url may be overridden using
        :meth:`set_url`."""
        if self.url is not None:
            return self.url
        else:
            return uri.URI.from_octets(
                uri.escape_data(self.name.encode('utf-8')))

    def set_url(self, url):
        self.url = url


class NumericValue(PrimitiveValue):

    """Abstract class for representing all numeric primitives"""

    if py2:
        _num_types = (int, long2, float, decimal.Decimal)
    else:
        _num_types = (int, float, decimal.Decimal)

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(self.value)

    def cast(self, type_def):
        """Implements the numeric cast exceptions"""
        if issubclass(type_def.value_type, NumericValue):
            result = type_def()
            try:
                result.set_value(self.value)
                if issubclass(type_def.value_type, FloatValue) and \
                        result.value is not None:
                    if math.isinf(result.value):
                        if not isinstance(self, FloatValue) or \
                                not math.isinf(self.value):
                            # only allow inf from inf!
                            result.value = None
            except ValueError:
                # bounds exception
                pass
            return result
        else:
            return super(NumericValue, self).cast(type_def)


class IntegerValue(NumericValue):

    """Abstract class for representing all integer primitives

    All types of IntegerValue can be set from numeric values of the
    following types: int, long (Python 2), float and Decimal. The native
    bool is also an int (isinstance(True, int) is True!) so these value
    are also accepted as synonymous for 0 and 1 in the usual way but
    non-numeric types are not allowed (even if they have a valid
    __bool__/__nonzero__ implementation).

    Rounding is towards zero where necessary.  If the value does not fit
    in the valid range for the sub-class then ValueError is raised.  The
    class attributes MIN and MAX are defined to contain the minimum and
    maximum values.  For signed values, MIN is the largest representable
    negative value."""

    _pytype = None      # override for each integer type

    def set_value(self, value):
        if isinstance(value, self._num_types):
            v = self._pytype(value)
            if v < self.MIN or v > self.MAX:
                raise ValueError(
                    "%s out of range for %s" % (repr(value), self.edm_name))
            else:
                self.value = v

        elif value is None:
            self.value = None
        else:
            raise TypeError(
                "can't set %s from %s" % (self.edm_name, repr(value)))


class FloatValue(NumericValue):

    """Abstract class for representing all floating-point primitives

    Both types of FloatValue can be set from numeric values of the
    following types: int (bool, see :class:`IntegerValue`), long (Python
    2), float and Decimal.

    If the value does not fit in the valid range for the sub-class then
    the value is set to one of the signed infinity values inf or -inf
    that are supported by OData.  ValueError is never raised.  The class
    attributes MIN and MAX are defined to contain the minimum and
    maximum representable values and DECIMAL_MIN and DECIMAL_MAX are
    defined to hold the Decimal representations of those values."""

    _inf = float('inf')
    _negative_inf = float('-inf')

    def set_value(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, decimal.Decimal):
            if value > self.DECIMAL_MAX:
                self.value = self._inf
            elif value < self.DECIMAL_MIN:
                self.value = self._negative_inf
            else:
                self.value = float(value)
        elif isinstance(value, self._num_types):
            try:
                value = float(value)
                if math.isnan(value) or math.isinf(value):
                    self.value = value
                elif value > self.MAX:
                    self.value = self._inf
                elif value < self.MIN:
                    self.value = self._negative_inf
                else:
                    self.value = value
            except OverflowError:
                # Yes: integers can be bigger than floats!
                if value > 0:
                    self.value = self._inf
                else:
                    self.value = self._negative_inf
        else:
            raise TypeError(
                "can't set %s from %s" % (self.edm_name, repr(value)))


class BinaryValue(PrimitiveValue):

    """Represents a value of type Edm.Binary

    The value member of a BinaryValue is either None or of type bytes.

    Binary literals are base64url encoded binary-strings as per
    http://tools.ietf.org/html/rfc4648#section-5

    Binary values can also be set from most Python types, character
    strings are UTF-8 encoded, any other types are converted using the
    builtin bytes function.  For consistency, BinaryValues can *not* be
    set from instances of PrimitiveValue."""

    edm_name = 'Binary'

    def set_value(self, value=None):
        if value is None:
            self.value = None
        else:
            if isinstance(value, bytes):
                new_value = value
            elif is_unicode(value):
                new_value = value.encode("utf-8")
            elif isinstance(value, PrimitiveValue):
                raise TypeError
            else:
                new_value = bytes(value)
            # check limits
            if self.type_def._max_length and len(new_value) > \
                    self.type_def._max_length:
                raise ValueError("MaxLength exceeded for binary value")
            self.value = new_value

    @classmethod
    def from_str(cls, src):
        p = ODataParser(src)
        v = p.require_binary_value()
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return to_text(base64.urlsafe_b64encode(self.value))


class BooleanValue(PrimitiveValue):

    """Represents a value of type Edm.Boolean

    The value member of a BooleanValue is either None, True or False.

    Boolean literals are one of the strings "true" or "false"

    Boolean values can be set from any other input type (except
    PrimitiveValue instances), the resulting value is the logical
    evaluation of the input value.  E.g., empty strings and lists are
    False, non-zero integer values True, etc."""

    edm_name = 'Boolean'

    def set_value(self, value=None):
        if value is None or value is True or value is False:
            self.value = value
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            self.value = True if value else False

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        return "true" if self.value else "false"

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax is case insenstive for the values "true" and
        "false" but case sensitive for the value 'null'."""
        p = ODataParser(src)
        v = p.require_boolean_value()
        p.require_end()
        return v


class ByteValue(IntegerValue):

    """Represents a value of type Edm.Byte"""

    MIN = 0
    MAX = 255

    _pytype = int

    edm_name = 'Byte'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_byte_value()
        p.require_end()
        return v


class DecimalValue(NumericValue):

    """Represents a value of type Edm.Decimal

    Can be set from numeric values of the
    following types: int (bool, see :class:`IntegerValue` for details),
    long (Python 2), float and Decimal."""

    edm_name = 'Decimal'

    def _round(self, value):
        precision = len(self.type_def.dec_digits)
        vt = value.as_tuple()
        vprec = len(vt.digits)
        # check bounds on exponent
        if vt.exponent + vprec > self.type_def.dec_nleft:
            raise ValueError("Value too large for scaled Decimal")
        if vt.exponent + vprec >= precision:
            # negative scale results in integer (perhaps with trailing
            # zeros)
            q = decimal.Decimal(
                (0, self.type_def.dec_digits, vprec + vt.exponent - precision))
        else:
            # some digits to the right of the decimal point, this needs
            # a litte explaining.  We take the minimum of:
            #   1. the specified max scale in the type
            #   2. the number of digits to the right of the point in the
            #      original value (-vt.exponent) - to prevent spurious 0s
            #   3. the number of digits to the right of the point after
            #      rounding to the current precision - to prevent us
            #      exceeding precision
            rdigits = min(self.type_def.dec_nright, -vt.exponent,
                          max(0, precision - (vprec + vt.exponent)))
            q = decimal.Decimal((0, self.type_def.dec_digits, -rdigits))
        return value.quantize(q, rounding=decimal.ROUND_HALF_UP)

    def set_value(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, (int, bool, long2)):
            self.value = self._round(decimal.Decimal(value))
        elif isinstance(value, decimal.Decimal):
            self.value = self._round(value)
        elif isinstance(value, float):
            self.value = self._round(decimal.Decimal(repr(value)))
        else:
            raise TypeError("Can't set Decimal from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax requires at least one digit before the decimal
        point and, if a point is given, at least one digit after it.

        The ABNF allows the use of the %-encoded sequence %2B to
        represent the + sign but we do not allow it here on the
        assumption that the value has already been unencoded.  That
        means that we won't allow '%2B1' to be interpreted as +1 when it
        is used in XML attribute/element values or JSON decimal strings
        which I assume is what is intended."""
        p = ODataParser(src)
        v = p.require_decimal_value()
        p.require_end()
        return v


class DoubleValue(FloatValue):

    """Represents a value of type Edm.Double"""

    edm_name = 'Double'

    try:
        MAX = (2 - 2 ** -52) * 2 ** 1023
    except OverflowError:
        try:
            MAX = (2 - 2 ** -23) * 2 ** 127
            logging.warning(
                "IEEE 754 binary64 not supported, using binary32 instead")
        except OverflowError:
            try:
                MAX = (2 - 2 ** -10) * 2 ** 15
                logging.warning(
                    "IEEE 754 binary32 not supported, using binary16 instead")
            except OverflowError:
                logging.error("IEEE 754 binary16 not supported""")
                raise

    MIN = -MAX

    DECIMAL_MAX = decimal.Decimal(repr(MAX))
    DECIMAL_MIN = decimal.Decimal(repr(MIN))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_double_value()
        p.require_end()
        return v


class Int16Value(IntegerValue):

    MIN = -32768
    MAX = 32767

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int16'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_int16_value()
        p.require_end()
        return v


class Int32Value(IntegerValue):

    MIN = -2147483648
    MAX = 2147483647

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int32'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_int32_value()
        p.require_end()
        return v


class Int64Value(IntegerValue):

    MAX = 9223372036854775807
    MIN = -9223372036854775808

    if py2:
        _pytype = long2 if MAX > sys.maxint else int
    else:
        _pytype = int

    edm_name = 'Int64'

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_int64_value()
        p.require_end()
        return v


class SByteValue(IntegerValue):

    MIN = -128
    MAX = 127

    _pytype = int

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_sbyte_value()
        p.require_end()
        return v

    edm_name = 'SByte'


class SingleValue(FloatValue):

    """Represents a value of type Edm.Single"""

    edm_name = 'Single'

    try:
        MAX = (2 - 2 ** -23) * 2 ** 127
    except OverflowError:
        try:
            MAX = (2 - 2 ** -10) * 2 ** 15
            logging.warning(
                "IEEE 754 binary32 not supported, using binary16 instead")
        except OverflowError:
            logging.error("IEEE 754 binary16 not supported""")
            raise

    MIN = -MAX

    DECIMAL_MAX = decimal.Decimal(repr(MAX))
    DECIMAL_MIN = decimal.Decimal(repr(MIN))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_single_value()
        p.require_end()
        return v


class DateValue(PrimitiveValue):

    """Represents a value of type Edm.Date

    The value member of a DateValue is either None or an instance of
    :class:`pyslet.iso8601.Date`.

    Date literals allow an expanded range of dates with a potentially
    unlimited range using ISO 8601 extended format (using hyphen
    separators).  As a result, Date instances always have xdigits set to
    -1.

    Date values can be set from an instance of
    :py:class:`iso8601.Date` though the date must be complete (i.e., it
    must have day precision). The standard Python datetime.date type may
    also be used, the datetime.datetime type is defined to be a subclass
    of datetime.date so can also be used (the time component being
    discarded)."""

    edm_name = 'Date'

    def set_value(self, value):
        if isinstance(value, Date):
            # force xdigits=-1, must be complete
            if not value.complete():
                raise ValueError("Can't set Date from %s" % str(value))
            else:
                self.value = value.expand(xdigits=-1)
        elif isinstance(value, datetime.date):
            bce, c, y = Date.split_year(value.year)
            self.value = Date(bce=bce, century=c, year=y, month=value.month,
                              day=value.day, xdigits=-1)
        elif value is None:
            self.value = None
        else:
            raise TypeError("Can't set Date from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_date_value()
        p.require_end()
        return v


def _struncate(temporal_q, s):
    # truncate a seconds value to the active temporal precision
    if isinstance(s, float):
        s = decimal.Decimal(
            repr(s)).quantize(temporal_q, rounding=decimal.ROUND_DOWN)
        if temporal_q.as_tuple().exponent == 0:
            return int(s)
        else:
            return float(s)
    else:
        return s


class DateTimeOffsetValue(PrimitiveValue):

    """Represents a value of type Edm.DateTimeOffset

    The value member of a DateTimeOffsetValue is either None or an
    instance of :class:`pyslet.iso8601.TimePoint`.  OData excludes leap
    seconds.

    DateTimeOffset literals allow an expanded range of dates with
    potentially unlimited range (as per :class:`DateValue`).  As a
    result, the date component of the TimePoint is always in expanded
    form supporting a variable number of leading century digits.

    DateTimeOffset values can be set from an instance of
    :py:class:`iso8601.TimePoint` though the value must be complete
    (have second precision) and have a valid timezone.  There is *no*
    automatic assumption of UTC when setting from TimePoint instances.

    The standard python datetime.datetime and datetime.date can also be
    used. Values are *assumed* to be in UTC if utcoffset returns None.
    The standard python date object is set by extending it to be the
    beginning of the UTC day 00:00:00Z on that date.

    Finally, positive numeric values are accepted and interpreted as
    unix times (seconds since the epoch).  UTC is assumed.  See the
    :py:meth:`~pyslet.iso8601.TimePoint.from_unix_time` factory method of
    TimePoint for more information."""

    edm_name = 'DateTimeOffset'

    def set_value(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, TimePoint):
            # force xdigits=-1, must be complete
            if not value.complete():
                raise ValueError(
                    "Can't set DateTimeOffset from %s" % str(value))
            elif value.time.get_zone()[0] is None:
                raise ValueError(
                    "Missing timezone in %s" % str(value))
            else:
                # handle precision
                h, m, s = value.time.get_time()
                zd, zh, zm = value.time.get_zone3()
                if h == 24:
                    h = 0
                    date = value.date.offset(days=1)
                else:
                    date = value.date
                if s >= 60:
                    # leap second!
                    if isinstance(s, float):
                        # max precision
                        s = _struncate(
                            self.type_def.temporal_q, 59.999999999999)
                    else:
                        s = 59
                elif isinstance(s, float):
                    s = _struncate(self.type_def.temporal_q, s)
                self.value = TimePoint(
                    date=date.expand(xdigits=-1),
                    time=Time(hour=h, minute=m, second=s, zdirection=zd,
                              zhour=zh, zminute=zm))
        elif isinstance(value, datetime.datetime):
            # the timezone information is probably missing, assume UTC!
            zdirection = 0
            zhour = zminute = None
            zoffset = value.utcoffset()
            if zoffset is not None:
                zoffset = zoffset.total_seconds()
                if zoffset is None:
                    zoffset = 0
                if zoffset < 0:
                    zdirection = -1
                    zoffset = -zoffset
                elif zoffset:
                    zdirection = 1
                zminute = zoffset // 60     # discard seconds
                zhour = zminute // 60
                zminute = zminute % 60
            bce, c, y = Date.split_year(value.year)
            self.value = TimePoint(
                date=Date(
                    bce=bce, century=c, year=y,
                    month=value.month,
                    day=value.day,
                    xdigits=-1),
                time=Time(
                    hour=value.hour,
                    minute=value.minute,
                    second=_struncate(
                        self.type_def.temporal_q,
                        value.second + (value.microsecond / 1000000.0)),
                    zdirection=zdirection,
                    zhour=zhour,
                    zminute=zminute))
        elif isinstance(value, datetime.date):
            bce, c, y = Date.split_year(value.year)
            self.value = TimePoint(
                date=Date(
                    bce=bce, century=c, year=y,
                    month=value.month,
                    day=value.day,
                    xdigits=-1),
                time=Time(
                    hour=0,
                    minute=0,
                    second=0,
                    zdirection=0))
        elif isinstance(value, (int, long2, float, decimal.Decimal)):
            if value >= 0:
                self.value = TimePoint.from_unix_time(
                    _struncate(self.type_def.temporal_q, value))
            else:
                raise ValueError(
                    "Can't set DateTimeOffset from %s" % str(value))
        else:
            raise TypeError("Can't set DateTimeOffset from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_date_time_offset_value()
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        h, m, s = self.value.time.get_time()
        if isinstance(s, float):
            return self.value.get_calendar_string(ndp=6, dp='.')
        else:
            return self.value.get_calendar_string(ndp=0)


class DurationValue(PrimitiveValue):

    """Represents a value of type Edm.Duration

    The value member of a DurationValue is either None or an instance of
    :class:`pyslet.xml.xsdatatypes.Duration`.

    Duration literals allow a reduced range of values as values expressed
    in terms of years, months or weeks are not allowed.

    Duration values can be set from an existing Duration only."""

    edm_name = 'Duration'

    def set_value(self, value):
        if value is None:
            self.value = None
        elif isinstance(value, xsi.Duration):
            try:
                d = value.get_calender_duration()
                if d[0] or d[1]:
                    raise ValueError("Can't set Duration from %s" % str(value))
                else:
                    self.value = xsi.Duration(value)
                    self.value.seconds = _struncate(
                        self.type_def.temporal_q, self.value.seconds)
            except DateTimeError:
                # must be a week-based value
                raise ValueError("Can't set Duration from %s" % str(value))
        else:
            raise TypeError("Can't set Duration from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string

        OData syntax follows XML schema convention of an optional sign
        followed by an ISO-type duration specified in days, hours,
        minutes and seconds."""
        p = ODataParser(src)
        v = p.require_duration_value()
        p.require_end()
        return v


class GuidValue(PrimitiveValue):

    """Represents a value of type Edm.Guid

    The value member of a GuidValue is either None or an instance of
    Python's built-in UUID class.

    Guid literals allow content in the following form:
    dddddddd-dddd-dddd-dddd-dddddddddddd where each d represents
    [A-Fa-f0-9].

    Guid values can also be set directly from either binary or hex
    strings. Binary strings must be of length 16 and are passed as raw
    bytes to the UUID constructor, hexadecimal strings must be of length
    32 characters.  (In Python 2 both str and unicode types are accepted
    as hexadecimal strings, the length being used to determine if the
    source is a binary or hexadecimal representation.)"""
    pass

    edm_name = 'Guid'

    def set_value(self, value=None):
        if value is None:
            self.value = None
        elif isinstance(value, bytes) and len(value) == 16:
            self.value = uuid.UUID(bytes=value)
        elif is_text(value) and len(value) == 32:
            self.value = uuid.UUID(hex=value)
        elif is_text(value):
            raise ValueError("Can't set Guid from %s" % str(value))
        elif isinstance(value, uuid.UUID):
            self.value = value
        else:
            raise TypeError("Can't set Guid from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_guid_value()
        p.require_end()
        return v


class StreamValue(PrimitiveValue):

    """Represents a value of type Edm.Stream

    The value member of a StreamValue is either None or a StreamInfo
    instance (TODO) containing the stream's metadata.

        The values for stream properties do not appear in the entity
        payload. Instead, the values are read or written through URLs.
    """

    edm_name = 'Stream'


class StringValue(PrimitiveValue):

    """Represents a value of type Edm.String

    The value member of a StringValue is either None or a character
    string (Python 2, unicode).

    The literal form of a string is the string itself.

    Values may be set from any character string or object which supports
    conversion to character string (using the builtin str/unicode
    function) with the exception of instances of PrimitiveValue which
    raise TypeError for consistency and to prevent confusion with the
    OData-defined cast operation.

    Special rules apply to the use of binary strings (bytes) to set
    string values.  A raw bytes object must be an ASCII-encodable
    string, otherwise ValueError is raised.  This applies to both
    Python 2 and Python 3!"""

    edm_name = 'String'

    def set_value(self, value=None):
        if value is None:
            self.value = None
        else:
            if isinstance(value, bytes):
                try:
                    new_value = value.decode('ascii')
                except UnicodeDecodeError:
                    raise ValueError(
                        "Can't set String from non-ascii bytes %s" %
                        str(value))
            elif is_unicode(value):
                new_value = value
            elif isinstance(value, PrimitiveValue):
                raise TypeError("Can't set String from %s" % repr(value))
            else:
                new_value = to_text(value)
            # check limits
            if not self.type_def._unicode:
                try:
                    value.encode('ascii')
                except UnicodeEncodeError:
                    raise ValueError(
                        "Can't store non-ascii text in Edm.String type "
                        "that " "does not accept Unicode characters")
            if self.type_def._max_length and len(new_value) > \
                    self.type_def._max_length:
                raise ValueError("MaxLength exceeded for string value")
            self.value = new_value

    @classmethod
    def from_str(cls, src):
        return cls(src)


class TimeOfDayValue(PrimitiveValue):

    """Represents a value of type Edm.TimeOfDay

    The value member of a TimeOfDayValue is either None or an instance
    of :class:`pyslet.iso8601.Time` with no zone specification.  OData
    excludes leap seconds.

    TimeOfDay literals use the extended ISO form with a '.' as decimal
    indicator if (optional) fractional seconds are used.

    TimeOfDay values can be set from an instance of
    :py:class:`iso8601.Time` though the value must be complete
    (have second precision) and have no timezone.  There is *no*
    automatic removal of timezone information to prevent accidentally
    introducing unintended mixed-zone comparison bugs.

    The standard python datetime.time can also be used provided
    utcoffset() returns None.

    Finally, positive numeric values are accepted and interpreted as
    seconds since midnight but must be in the range 0 up to (but not
    including) 86400.  See the :py:class:`~pyslet.iso8601.Time` for more
    information."""

    edm_name = 'TimeOfDay'

    def set_value(self, value):
        if isinstance(value, Time):
            # no zone allowed
            if not value.complete():
                raise ValueError(
                    "Can't set TimeOfDay from incomplete %s" % str(value))
            elif value.get_zone()[0] is not None:
                raise ValueError(
                    "Can't set TimeOfDay with timezone %s" % str(value))
            else:
                h, m, s = value.get_time()
                if h == 24:
                    # This is not allowed in OData
                    raise ValueError(
                        "Can't set TimeOfDay from %s" % str(value))
                if s >= 60:
                    # leap second!
                    if isinstance(s, float):
                        # max precision
                        s = _struncate(self.type_def.temporal_q,
                                       59.999999999999)
                    else:
                        s = 59
                elif isinstance(s, float):
                    s = _struncate(self.type_def.temporal_q, s)
                self.value = Time(hour=h, minute=m, second=s)
        elif isinstance(value, datetime.time):
            self.value = Time(
                hour=value.hour, minute=value.minute,
                second=_struncate(self.type_def.temporal_q, value.second))
        elif value is None:
            self.value = None
        else:
            raise TypeError("Can't set TimeOfDay from %s" % repr(value))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_time_of_day_value()
        p.require_end()
        return v

    def __unicode__(self):
        if self.value is None:
            raise ValueError("null value has no text representation")
        h, m, s = self.value.get_time()
        if isinstance(s, float):
            return self.value.get_string(ndp=6, dp='.')
        else:
            return self.value.get_string(ndp=0)


class PointValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.PointLiteral):
            self.value = value
        elif isinstance(value, geo.Point):
            # a Point without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.PointLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_point_literal()
        p.require_end()
        return cls(v)


class LineStringValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.LineStringLiteral):
            self.value = value
        elif isinstance(value, geo.LineString):
            # a LineString without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.LineStringLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_line_string_literal()
        p.require_end()
        return cls(v)


class PolygonValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.PolygonLiteral):
            # validate this literal
            self.value = value
        elif isinstance(value, geo.Polygon):
            # a Polygon without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.PolygonLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_polygon_literal()
        p.require_end()
        return cls(v)


class MultiPointValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiPointLiteral):
            self.value = value
        elif isinstance(value, geo.MultiPoint):
            # a MultiPoint without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.MultiPointLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_multi_point_literal()
        p.require_end()
        return cls(v)


class MultiLineStringValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiLineStringLiteral):
            self.value = value
        elif isinstance(value, geo.MultiLineString):
            # a MultiLineString without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.MultiLineStringLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_multi_line_string_literal()
        p.require_end()
        return cls(v)


class MultiPolygonValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.MultiPolygonLiteral):
            self.value = value
        elif isinstance(value, geo.MultiPolygon):
            # a MultiPolygon without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.MultiPolygonLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_multi_polygon_literal()
        p.require_end()
        return cls(v)


class GeoCollectionValue(object):

    def set_value(self, value=None):
        if value is None:
            self.value = value
        elif isinstance(value, geo.GeoCollectionLiteral):
            self.value = value
        elif isinstance(value, geo.GeoCollection):
            # a GeoCollection without a CRS acquires the default
            srid = self.type_def._srid
            self.value = geo.GeoCollectionLiteral(srid, value)
        elif isinstance(value, PrimitiveValue):
            raise TypeError
        else:
            raise TypeError("Can't set %s from %s" %
                            (self.__class__.__name__, repr(value)))

    @classmethod
    def from_str(cls, src):
        """Constructs a value from a string"""
        p = ODataParser(src)
        v = p.require_full_collection_literal()
        p.require_end()
        return cls(v)


class GeographyValue(PrimitiveValue):
    pass


class GeographyPointValue(PointValue, GeographyValue):

    edm_name = 'GeographyPoint'


class GeographyLineStringValue(LineStringValue, GeographyValue):

    edm_name = 'GeographyLineString'


class GeographyPolygonValue(PolygonValue, GeographyValue):

    edm_name = 'GeographyPolygon'


class GeographyMultiPointValue(MultiPointValue, GeographyValue):

    edm_name = 'GeographyMultiPoint'


class GeographyMultiLineStringValue(MultiLineStringValue, GeographyValue):

    edm_name = 'GeographyMultiLineString'


class GeographyMultiPolygonValue(MultiPolygonValue, GeographyValue):

    edm_name = 'GeographyMultiPolygon'


class GeographyCollectionValue(GeoCollectionValue, GeographyValue):

    edm_name = 'GeographyCollection'


class GeometryValue(PrimitiveValue):
    pass


class GeometryPointValue(PointValue, GeometryValue):

    edm_name = 'GeometryPoint'


class GeometryLineStringValue(LineStringValue, GeometryValue):

    edm_name = 'GeometryLineString'


class GeometryPolygonValue(PolygonValue, GeometryValue):

    edm_name = 'GeometryPolygon'


class GeometryMultiPointValue(MultiPointValue, GeometryValue):

    edm_name = 'GeometryMultiPoint'


class GeometryMultiLineStringValue(MultiLineStringValue, GeometryValue):

    edm_name = 'GeometryMultiLineString'


class GeometryMultiPolygonValue(MultiPolygonValue, GeometryValue):

    edm_name = 'GeometryMultiPolygon'


class GeometryCollectionValue(GeoCollectionValue, GeometryValue):

    edm_name = 'GeometryCollection'


_oid_start_char = CharClass("_")
_oid_start_char.add_class(CharClass.ucd_category("L"))
_oid_start_char.add_class(CharClass.ucd_category("Nl"))

_oid_char = CharClass()
for c in ("L", "Nl", "Nd", "Mn", "Mc", "Pc", "Cf"):
    _oid_char.add_class(CharClass.ucd_category(c))


class ODataParser(BasicParser):

    """A Parser for the OData ABNF

    This class takes case of parsing primitive values only."""

    # Line 252
    def require_expand_path(self):
        """Parses production expandPath

        The syntax is a bit obscure from the definition due to
        the equivalence of many of the constructs but it
        reduces to::

            [ qualifiedName "/" ] odataIdentifier
                *( "/" [ qualifiedName "/" ] odataIdentifier )
                [ "/" qualifiedName ]

        We return a list of strings and/or :class:`QualifiedName`
        instances containing the path elements without separators. There
        is no ambiguity as the path can neither start nor end in a
        separator."""
        result = []
        qname = self.parse_production(self.require_qualified_name)
        if qname:
            result.append(qname)
            self.require("/")
            result.append(self.require_odata_identifier())
        else:
            result.append(self.require_odata_identifier())
        while self.parse("/"):
            qname = self.parse_production(self.require_qualified_name)
            if qname:
                result.append(qname)
                if self.parse("/"):
                    result.append(self.require_odata_identifier())
                else:
                    break
            else:
                result.append(self.require_odata_identifier())
        return result

    # Line 701-704
    def require_qualified_name(self):
        """Parses productions of the form qualified<type>Name

        Returns a named tuple of (namespace, name).

        Although split out in the ABNF these definitions are all
        equivalent and can't be differentiated in the syntax without
        reference to a specific model."""
        result = []
        result.append(self.require_odata_identifier())
        self.require(".")
        result.append(self.require_odata_identifier())
        while self.parse("."):
            result.append(self.require_odata_identifier())
        return QualifiedName(".".join(result[:-1]), result[-1])

    # Line 707
    def require_namespace(self):
        """Parses procution namespace

        Returns a string representing the namespace.  This method is
        greedy, it will parse as many identifiers as it can."""
        result = []
        result.append(self.require_odata_identifier())
        while self.parse("."):
            result.append(self.require_odata_identifier())
        return ".".join(result)

    # Line 720
    def require_odata_identifier(self):
        result = []
        if not _oid_start_char.test(self.the_char):
            self.parser_error("simple identifier")
        result.append(self.the_char)
        self.next_char()
        while _oid_char.test(self.the_char):
            result.append(self.the_char)
            self.next_char()
        if len(result) > 128:
            self.parser_error("simple identifier; 128 chars or fewer")
        return ''.join(result)

    # Line 856
    #: Matches production: nullValue
    null_value = 'null'

    # Line 859
    def require_binary(self):
        """Parses production: binary

        Returns a :class:`BinaryValue` instance or raises a parser
        error."""
        # binary = "binary" SQUOTE binaryValue SQUOTE
        self.require_production(self.parse_insensitive("binary"), "binary")
        self.require("'")
        v = self.require_binary_value()
        self.require("'")
        return v

    # Line 860
    def require_binary_value(self):
        """Parses production: binaryValue

        Returns a :class:`BinaryValue` instance or raises a parser
        error."""
        result = bytearray()
        while self.base64_char.test(self.the_char):
            result.append(byte(self.the_char))
            self.next_char()
        # in OData, the trailing "=" are optional but if given they must
        # result in the correct length string.
        pad = len(result) % 4
        if pad == 3:
            self.parse('=')
            result.append(byte('='))
        elif pad == 2:
            self.parse('==')
            result.append(byte('='))
            result.append(byte('='))
        return BinaryValue(base64.urlsafe_b64decode(bytes(result)))

    # Line 863
    #: a character class representing production base64char
    base64_char = CharClass(('A', 'Z'), ('a', 'z'), ('0', '9'), '-', '_')

    # Line 865
    def require_boolean_value(self):
        """Parses production: booleanValue

        Returns a :class:`BooleanValue` instance or raises a parser
        error."""
        v = BooleanValue()
        if self.parse_insensitive("true"):
            v.set_value(True)
        elif self.parse_insensitive("false"):
            v.set_value(False)
        else:
            self.parser_error("booleanValue")
        return v

    # Line 867
    def require_decimal_value(self):
        """Parses production: decimalValue

        Returns a :class:`DecimalValue` instance or raises a parser
        error."""
        v = DecimalValue()
        sign = self.parse_sign()
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            v.set_value(decimal.Decimal(sign + ldigits + '.' + rdigits))
        else:
            v.set_value(decimal.Decimal(sign + ldigits))
        return v

    # Line 869
    def require_double_value(self):
        """Parses production: doubleValue

        Returns a :class:`DoubleValue` instance or raises a parser
        error."""
        v = DoubleValue()
        sign = self.parse_one('+-')
        if not sign:
            if self.parse('INF'):
                v.set_value(float('inf'))
                return v
            elif self.parse('NaN'):
                v.set_value(float('nan'))
                return v
            sign = ''
        elif sign == '-' and self.parse('INF'):
            v.set_value(float('-inf'))
            return v
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            dec = sign + ldigits + '.' + rdigits
        else:
            dec = sign + ldigits
        if self.parse_insensitive('e'):
            sign = self.parse_one('+-')
            if not sign:
                sign = ''
            edigits = self.require_production(self.parse_digits(1), "exponent")
            exp = 'E' + sign + edigits
        else:
            exp = ''
        v.set_value(float(dec + exp))
        return v

    # Line 870
    def require_single_value(self):
        """Parses production: singleValue

        Returns a :class:`SingleValue` instance or raises a parser
        error."""
        v = SingleValue()
        v.set_value(self.require_double_value().value)
        return v

    # Line 873
    def require_guid_value(self):
        """Parses production: guidValue

        Returns a :class:`GuidValue` instance or raises a parser
        error."""
        hex_parts = []
        part = self.parse_hex_digits(8, 8)
        if not part:
            self.parser_error("8HEXDIG")
        hex_parts.append(part)
        for i in range3(3):
            self.require('-')
            part = self.parse_hex_digits(4, 4)
            if not part:
                self.parser_error("4HEXDIG")
            hex_parts.append(part)
        self.require('-')
        part = self.parse_hex_digits(12, 12)
        if not part:
            self.parser_error("12HEXDIG")
        hex_parts.append(part)
        result = GuidValue()
        result.set_value(uuid.UUID(hex=''.join(hex_parts)))
        return result

    # Line 875
    def require_byte_value(self):
        """Parses production: byteValue

        Returns a :class:`ByteValue` instance of raises a parser
        error."""
        #   1*3DIGIT
        digits = self.require_production(self.parse_digits(1, 3), "byteValue")
        v = ByteValue()
        try:
            v.set_value(int(digits))
        except ValueError:
            self.parser_error('byte in range [0, 255]')
        return v

    # Line 876
    def require_sbyte_value(self):
        """Parses production: sbyteValue

        Returns a :class:`SByteValue` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 3), "sbyteValue")
        v = SByteValue()
        try:
            v.set_value(int(sign + digits))
        except ValueError:
            self.parser_error('sbyte in range [-128, 127]')
        return v

    # Line 877
    def require_int16_value(self):
        """Parses production: int16Value

        Returns a :class:`Int16Value` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 5), "int16Value")
        v = Int16Value()
        try:
            v.set_value(int(sign + digits))
        except ValueError:
            self.parser_error('int16Value in range [-32768, 32767]')
        return v

    # Line 878
    def require_int32_value(self):
        """Parses production: int32Value

        Returns a :class:`Int32Value` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(
            self.parse_digits(1, 10), "int32Value")
        v = Int32Value()
        try:
            v.set_value(int(sign + digits))
        except ValueError:
            self.parser_error('int32Value in range [-2147483648, 2147483647]')
        return v

    # Line 879
    def require_int64_value(self):
        """Parses production: int64Value

        Returns a :class:`Int64Value` instance or raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 19),
                                         "int64Value")
        v = Int64Value()
        try:
            v.set_value(int(sign + digits))
        except ValueError:
            self.parser_error('int64Value in range [-9223372036854775808, '
                              '9223372036854775807]')
        return v

    # Line 881
    def require_string(self):
        """Parses production: string

        Returns a :class:`StringValue` instance or raises a parser
        error. Note that this is the literal quoted form of the string
        for use in URLs, string values in XML and JSON payloads are
        represented using native representations.  It is assumed that
        the input *has already* been decoded from the URL and is
        represented as a character string (it may also contain non-ASCII
        characters interpreted from the URL in an appropriate way)."""
        result = []
        self.require("'")
        while self.the_char is not None:
            if self.parse("'"):
                if self.parse("'"):
                    # an escaped single quote
                    result.append("'")
                else:
                    break
            else:
                result.append(self.the_char)
                self.next_char()
        return "".join(result)

    # Line 884
    def require_date_value(self):
        """Parses the production: dateValue

        Returns a :class:`DateValue` instance or raises a parser
        error."""
        year = self.require_year()
        self.require('-')
        month = self.require_month()
        self.require('-')
        day = self.require_day()
        bce, c, y = Date.split_year(year)
        result = DateValue()
        try:
            result.set_value(Date(bce=bce, century=c, year=y, month=month,
                                  day=day, xdigits=-1))
            return result
        except DateTimeError:
            self.parser_error("valid dateValue")

    # Line 886
    def require_date_time_offset_value(self):
        """Parses production: dateTimeOffsetValue

        Returns a :class:`DateTimeOffsetValue` instance or raises a
        parser error."""
        year = self.require_year()
        self.require('-')
        month = self.require_month()
        self.require('-')
        day = self.require_day()
        bce, c, y = Date.split_year(year)
        self.require('T')
        hour = self.require_hour()
        self.require(':')
        minute = self.require_minute()
        if self.parse(':'):
            second = self.require_second()
            if self.parse('.'):
                fraction = self.require_production(self.parse_digits(1, 12))
                second = float(second) + float('0.' + fraction)
            else:
                second = int(second)
        else:
            second = 0
        if self.parse('Z'):
            zdirection = zhour = zminute = 0
        else:
            if self.parse('+'):
                zdirection = 1
            else:
                self.require('-')
                zdirection = -1
            zhour = self.require_hour()
            self.require(':')
            zminute = self.require_minute()
        result = DateTimeOffsetValue()
        try:
            result.set_value(
                TimePoint(
                    date=Date(bce=bce, century=c, year=y, month=month, day=day,
                              xdigits=-1),
                    time=Time(hour=hour, minute=minute, second=second,
                              zdirection=zdirection, zhour=zhour,
                              zminute=zminute)))
            return result
        except DateTimeError:
            self.parser_error("valid dateTimeOffsetValue")

    # Line 889
    def require_duration_value(self):
        """Parses production: durationValue

        Returns a :class:`DurationValue` instance or raises a parser
        error."""
        sign = self.parse_sign_int()
        self.require("P")
        digits = self.parse_digits(1)
        if digits:
            self.require("D")
            days = int(digits)
        else:
            days = 0
        hours = minutes = seconds = 0
        if self.parse("T"):
            # time fields
            digits = self.parse_digits(1)
            if digits and self.parse("H"):
                hours = int(digits)
                digits = None
            if not digits:
                digits = self.parse_digits(1)
            if digits and self.parse('M'):
                minutes = int(digits)
                digits = None
            if not digits:
                digits = self.parse_digits(1)
            if digits:
                if self.parse('.'):
                    rdigits = self.require_production(
                        self.parse_digits(1), "fractional seconds")
                    self.require("S")
                    seconds = float(digits + "." + rdigits)
                elif self.parse("S"):
                    seconds = int(digits)
        d = xsi.Duration()
        d.sign = sign
        d.days = days
        d.hours = hours
        d.minutes = minutes
        d.seconds = seconds
        return DurationValue(d)

    # Line 893
    def require_time_of_day_value(self):
        """Parses production: timeOfDayValue

        Returns a :class:`TimeOfDayValue` instance or raises a parser
        error."""
        hour = self.require_hour()
        self.require(':')
        minute = self.require_minute()
        if self.parse(':'):
            second = self.require_second()
            if self.parse('.'):
                fraction = self.require_production(self.parse_digits(1, 12))
                second = float(second) + float('0.' + fraction)
            else:
                second = int(second)
        else:
            second = 0
        result = TimeOfDayValue()
        try:
            result.set_value(Time(hour=hour, minute=minute, second=second))
            return result
        except DateTimeError:
            self.parser_error("valid timeOfDayValue")

    # Line 896
    def require_zero_to_fifty_nine(self, production):
        """Parses production: zeroToFiftyNine

        Returns an integer in the range 0..59 or raises a parser
        error."""
        digits = self.require_production(self.parse_digits(2, 2), production)
        i = int(digits)
        if i > 59:
            self.parser_error("%s in range [0..59]" % production)
        return i

    # Line 897
    def require_year(self):
        """Parses production: year

        Returns an integer representing the parsed year or raises a
        parser error."""
        if self.parse('-'):
            sign = -1
        else:
            sign = 1
        if self.parse('0'):
            digits = self.parse_digits(3, 3)
        else:
            digits = self.parse_digits(4)
        if not digits:
            self.parser_error("year")
        return sign * int(digits)

    # Line 898
    def require_month(self):
        """Parses production: month

        Returns an integer representing the month or raises a parser
        error."""
        if self.parse('0'):
            digits = self.parse_digit()
        elif self.parse('1'):
            digits = '1' + self.require_production(
                self.parse_one("012"), "month")
        else:
            digits = None
        if not digits:
            self.parser_error("month")
        return int(digits)

    # Line 900
    def require_day(self):
        """Parses production: day

        Returns an integer representing the day or raises a parser
        error."""
        if self.parse("0"):
            digits = self.parse_digit()
        else:
            d = self.parse_one("12")
            if d:
                digits = d + self.require_production(
                    self.parse_digit(), "day")
            elif self.parse("3"):
                digits = '3' + self.require_production(
                    self.parse_one("01"), "day")
            else:
                digits = None
        if not digits:
            self.parser_error("day")
        return int(digits)

    # Line 903
    def require_hour(self):
        """Parses production: hour

        Returns an integer representing the hour or raises a parser
        error."""
        digits = self.require_production(self.parse_digits(2, 2), "hour")
        hour = int(digits)
        if hour > 23:
            self.parser_error("hour in range [0..23]")
        return hour

    # Line 905
    def require_minute(self):
        """Parses production: minute

        Returns an integer representation of the minute or raises a
        parser error."""
        return self.require_zero_to_fifty_nine("minute")

    # Line 906
    def require_second(self):
        """Parses production: second

        Returns an integer representation of the second or raises a
        parser error."""
        return self.require_zero_to_fifty_nine("second")

    # Line 910
    def require_enum_value(self):
        """Parses production: enumValue

        Returns a non-empty *list* of strings and/or integers or raises
        a parser error."""
        result = []
        result.append(self.require_single_enum_value())
        while self.parse(","):
            # no need to use look ahead
            result.append(self.require_single_enum_value())
        return result

    # Line 911
    def require_single_enum_value(self):
        """Parses production: singleEnumValue

        Reuturns either a simple identifier string, an integer or raises
        a parser error."""
        name = self.parse_production(self.require_odata_identifier)
        if name:
            return name
        else:
            return self.require_int64_value()

    # Line 915
    def require_full_collection_literal(self):
        """Parses production: fullCollectionLiteral

        Returns a :class:`geotypes.GeoCollectionLiteral` instance, a
        named tuple consisting of 'srid' and 'items' members."""
        srid = self.require_srid_literal()
        items = self.require_collection_literal()
        return geo.GeoCollectionLiteral(srid, items)

    # Line 916
    def require_collection_literal(self):
        """Parses production: collectionLiteral

        Returns a :class:`geotypes.GeoCollection` instance."""
        self.require_production(
            self.parse_insensitive("collection("), "collectionLiteral")
        items = [self.require_geo_literal()]
        while self.parse(self.COMMA):
            items.append(self.require_geo_literal())
        self.require(self.CLOSE)
        return geo.GeoCollection(items)

    # Line 917
    def require_geo_literal(self):
        """Parses production: geoLiteral

        Returns a :class:`geotypes.GeoItem` instance."""
        item = self.parse_production(self.require_collection_literal)
        if not item:
            item = self.parse_production(self.require_line_string_literal)
        if not item:
            item = self.parse_production(self.require_multi_point_literal)
        if not item:
            item = self.parse_production(
                self.require_multi_line_string_literal)
        if not item:
            item = self.parse_production(
                self.require_multi_polygon_literal)
        if not item:
            item = self.parse_production(self.require_point_literal)
        if not item:
            item = self.parse_production(self.require_polygon_literal)
        if not item:
            self.parser_error("geoLiteral")
        return item

    # Line 926
    def require_full_line_string_literal(self):
        """Parses production: fullLineStringLiteral

        Returns a :class:`geotypes.LineStringLiteral` instance, a named
        tuple consisting of 'srid' and 'line_string' members."""
        srid = self.require_srid_literal()
        l = self.require_line_string_literal()
        return geo.LineStringLiteral(srid, l)

    # Line 927
    def require_line_string_literal(self):
        """Parses production: lineStringLiteral

        Returns a :class:`geotypes.LineString` instance."""
        self.require_production(
            self.parse_insensitive("linestring"), "lineStringLiteral")
        return self.require_line_string_data()

    # Line 928
    def require_line_string_data(self):
        """Parses production: lineStringData

        Returns a :class:`geotypes.LineString` instance."""
        self.require(self.OPEN)
        coords = []
        coords.append(self.require_position_literal())
        while self.parse(self.COMMA):
            coords.append(self.require_position_literal())
        self.require(self.CLOSE)
        return geo.LineString(coords)

    # Line 931
    def require_full_multi_line_string_literal(self):
        """Parses production: fullMultiLineStringLiteral

        Returns a :class:`geotypes.MultiLineStringLiteral` instance."""
        srid = self.require_srid_literal()
        ml = self.require_multi_line_string_literal()
        return geo.MultiLineStringLiteral(srid, ml)

    # Line 932
    def require_multi_line_string_literal(self):
        """Parses production: multiLineStringLiteral

        Returns a :class:`geotypes.MultiLineString` instance."""
        try:
            self.require_production(
                self.parse_insensitive("multilinestring("),
                "MultiLineStringLiteral")
            # may be empty
            line_strings = []
            l = self.parse_production(self.require_line_string_data)
            if l:
                line_strings.append(l)
                while self.parse(self.COMMA):
                    line_strings.append(self.require_line_string_data())
            self.require(self.CLOSE)
        except ParserError:
            self.parser_error()
        return geo.MultiLineString(line_strings)

    # Line 935
    def require_full_multi_point_literal(self):
        """Parses production: fullMultiPointLiteral

        Returns a :class:`geotypes.MultiPointLiteral` instance."""
        srid = self.require_srid_literal()
        mp = self.require_multi_point_literal()
        return geo.MultiPointLiteral(srid, mp)

    # Line 936
    def require_multi_point_literal(self):
        """Parses production: multiPointLiteral

        Returns a :class:`geotypes.MultiPoint` instance."""
        self.require_production(
            self.parse_insensitive("multipoint("), "MultiPointLiteral")
        # may be empty
        points = []
        p = self.parse_production(self.require_point_data)
        if p:
            points.append(p)
            while self.parse(self.COMMA):
                points.append(self.require_point_data())
        self.require(self.CLOSE)
        return geo.MultiPoint(points)

    # Line 939
    def require_full_multi_polygon_literal(self):
        """Parses production: fullMultiPolygonLiteral

        Returns a :class:`geotypes.MultiPolygonLiteral` instance."""
        srid = self.require_srid_literal()
        mp = self.require_multi_polygon_literal()
        return geo.MultiPolygonLiteral(srid, mp)

    # Line 940
    def require_multi_polygon_literal(self):
        """Parses production: multiPolygonLiteral

        Returns a :class:`geotypes.MultiPolygon` instance."""
        try:
            self.require_production(
                self.parse_insensitive("multipolygon("), "MultiPolygonLiteral")
            # may be empty
            polygons = []
            p = self.parse_production(self.require_polygon_data)
            if p:
                polygons.append(p)
                while self.parse(self.COMMA):
                    polygons.append(self.require_polygon_data())
            self.require(self.CLOSE)
        except ParserError:
            self.parser_error()
        return geo.MultiPolygon(polygons)

    # Line 943
    def require_full_point_literal(self):
        """Parses production: fullPointLiteral

        Returns a :class:`geotypes.PointLiteral` instance, a named tuple
        consisting of "srid" and "point" members."""
        srid = self.require_srid_literal()
        p = self.require_point_literal()
        return geo.PointLiteral(srid, p)

    # Line 944
    def require_srid_literal(self):
        """Parses production: sridLiteral

        Returns an integer reference for the SRID or raises a parser
        error."""
        self.require_production(
            self.parse_insensitive("srid"), "SRID")
        self.require(self.EQ)
        digits = self.require_production(self.parse_digits(1, 5))
        self.require(self.SEMI)
        return int(digits)

    # Line 945
    def require_point_literal(self):
        """Parses production: pointLiteral

        Reuturns a Point instance."""
        self.require_production(
            self.parse_insensitive("point"), "pointLiteral")
        return self.require_point_data()

    # Line 946
    def require_point_data(self):
        """Parses production: pointData

        Returns a :class:`geotypes.Point` instance."""
        self.require(self.OPEN)
        coords = self.require_position_literal()
        self.require(self.CLOSE)
        return geo.Point(*coords)

    # Line 947
    def require_position_literal(self):
        """Parses production: positionLiteral

        Returns a tuple of two float values or raises a parser error.
        Although the ABNF refers to "longitude then latitude" this
        production is used for all co-ordinate reference systems in both
        Geography and Geometry types so we make no such judgement
        ourselves and simply return an unamed tuple."""
        d1 = self.require_double_value()
        self.require(self.SP)
        d2 = self.require_double_value()
        return (d1.value, d2.value)

    # Line 950
    def require_full_polygon_literal(self):
        """Parses production: fullPolygonLiteral

        Returns a :class:`geotypes.PolygonLiteral` instance."""
        srid = self.require_srid_literal()
        p = self.require_polygon_literal()
        return geo.PolygonLiteral(srid, p)

    # Line 951
    def require_polygon_literal(self):
        """Parses production: polygonLiteral

        Returns a :class:`geotypes.Polygon` instance."""
        self.require_production(
            self.parse_insensitive("polygon"), "polygonLiteral")
        return self.require_polygon_data()

    # Line 952
    def require_polygon_data(self):
        """Parses production: polygonData

        Returns a :class:`geotypes.Polygon` instance."""
        self.require(self.OPEN)
        rings = []
        rings.append(self.require_ring_literal())
        while self.parse(self.COMMA):
            rings.append(self.require_ring_literal())
        self.require(self.CLOSE)
        return geo.Polygon(rings)

    # Line 953
    def require_ring_literal(self):
        """Parses production: ringLiteral

        Returns a :class:`geotypes.Ring` instance."""
        self.require(self.OPEN)
        coords = []
        coords.append(self.require_position_literal())
        while self.parse(self.COMMA):
            coords.append(self.require_position_literal())
        self.require(self.CLOSE)
        return geo.Ring(coords)

    # Line 1052
    def parse_sign(self):
        """Parses production: SIGN (aka sign)

        This production is typically optional so we either return "+",
        "-" or "" depending on the sign character parsed.  The ABNF
        allows for the percent encoded value "%2B" instead of "+" but we
        assume that percent-encoding has been removed before parsing.
        (That may not be true in XML documents but it seems
        unintentional to allow this form in that context.)"""
        sign = self.parse_one('+-')
        return sign if sign else ''

    # Line 1050
    COMMA = ul(",")

    # Line 1051
    EQ = ul("=")

    # Line 1052
    def parse_sign_int(self):
        """Parses production: SIGN (aka sign)

        Returns the integer 1 or -1 depending on the sign.  If no sign
        is parsed then 1 is returned."""
        sign = self.parse_one('+-')
        return -1 if sign == "-" else 1

    # Line 1053
    SEMI = ul(";")

    # Line 1057
    OPEN = ul("(")
    # Line 1058
    CLOSE = ul(")")

    # Line 1162
    SP = ul(" ")


edm = Schema.edm_init()
odata = Schema.odata_init()


class DocumentSchemas(NameTable):

    """A name table of schema names (and aliases)"""

    def check_name(self):
        """Checks the name against edm:TNamespaceName

        From the spec:

            Non-normatively speaking it is a dot-separated sequence of
            SimpleIdentifiers with a maximum length of 511 Unicode
            characters."""
        raise NotImplementedError
