#! /usr/bin/env python

import decimal
import logging
import weakref

from . import (
    comex,
    errors,
    names,
    )

from .. import rfc2396 as uri
from ..py2 import (
    long2,
    is_text,
    to_text,
    )
from ..xml import xsdatatypes as xsi


class Annotations(names.NameTable):

    """The set of Annotations applied to a model element.

    A name table that contains :class:`Annotation` instances keyed on an
    instance of :class:`names.TermRef` that refers to the defining term.

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
        """Checks that name is of type :class:`names.TermRef`.

        Raises ValueError if the name is not valid (or is None)."""
        if name is None:
            raise ValueError("Annotation with no name")
        if not isinstance(name, names.TermRef):
            raise ValueError(
                "%s is not a valid term reference" % to_text(name))

    def qualify_name(self, name):
        """Returns the qualified version of a name

        Simply returns the string representation of the name (a
        :class:`names.TermRef`) as the name is already qualified."""
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
        qname = names.QualifiedName.from_str(term)
        if not qualifier:
            qualifier = (None, )
        elif is_text(qualifier):
            qualifier = (qualifier, )
        for q in qualifier:
            try:
                return self[names.TermRef(qname, q if q else None)]
            except KeyError:
                continue
        return default


class Annotation(names.Named):

    """An Annotation (applied to a model element).

    The name of this object is a :class:`names.TermRef` tuple that
    refers to the term that defines this annotation's type.

    This package divides Annotations into two types.  Annotations
    applied to data are treated like special property values with @
    qualified names (and optional # qualifiers) and types declared by
    the corresponding :class:`Term`.

    On the other hand, Annotations applied to metadata objects like
    EntityTypes, EntitySets, etc.; are represented by instances of this
    class.  Instances contain *expressions* that evaluate to
    :class:`Value` instances rather than values themselves.  These
    expressions may be constant or dynamic expressions.  In the case of
    dynamic expressions the expression is evaluated when it is applied
    to the target data.  An example will help.

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
    in the context of a specific entity instance in the data model.
    Therefore, the Annotation element applied to the Product entity type
    contains the expression and not a value.

    To complete the example, a specific instance of this entity type
    behaves as if had the following JSON representation::

        {
            "ProductName": "Punch",
            "ProductType": "Magazine",
            "@org.example.display.DisplayName": "Punch: Magazine"
        }

    The annotation has been applied to the instance and evaluated to its
    string value.  In practice though, you don't see the annotation
    explicitly applied to the serialized form of the entity.  The
    purpose of applying annotations (as expressions) to the ProductType
    is to enable them to be inferred on the instance by the *client*.
    The :meth:`Value.get_annotation` method on Value takes care of this
    by looking for annotation *expressions* applied to a Value's type
    and evaluating them dynamically (client side) to obtain the Value of
    the annotation itself.

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
    specific instance.  The intent is to provide a list of properties
    that are used to compute the ETag for an Airline, the same list will
    apply to all Airline instances.  The
    :meth:`Annotatable.get_annotation` method on Annotatable objects in
    the metadata model takes care of this, evaluating constant
    expressions without requiring a contextual instance Value."""

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
        """Returns a :class:`names.TermRef` tuple for this annotation"""
        return names.TermRef(
            name=names.QualifiedName.from_str(self.term().qname),
            qualifier=self.qualifier)

    def declare(self, nametable, name=None):
        """Declares this annotation in an Annotations nametable

        This method is overridden as, unlike other Named objects,
        Annotation instances do not support aliasing and have
        predetermined names based on the :attr:`term` and
        :attr:`qualifier` attributes

        The name parameter is made optional and is provided only for
        consistency with the parent class' signature and should be
        omitted.  If specified it must be a names.TermRef that matches
        the value returned by :meth:`get_term_ref`."""
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
             names.TermRef(
                names.QualifiedName("Core", "Description"), "ascii"))

        The target and qualifier are optional and may be None in the
        result."""
        apos = name.find('@')
        if apos < 0:
            raise ValueError("Annotation name must contain '@': %s" % name)
        elif apos > 0:
            return (
                names.simple_identifier_from_str(name[:apos]),
                names.TermRef.from_str(name[apos:]))
        else:
            return (None, names.TermRef.from_str(name))

    @classmethod
    def from_term_ref(cls, term_ref, context):
        """Creates a new instance from a qualified name and context

        term_ref
            A :class:`names.TermRef` instance or a string from which one can
            be parsed.

        context
            The QNameTable within which to look up the associated
            term definition.

        Returns an Annotation instance or None if the definition of the
        term could not be found."""
        # lookup qname in the context
        if is_text(term_ref):
            term_ref = names.TermRef.from_str(term_ref)
        term = context.qualified_get(term_ref.name)
        if not isinstance(term, Term):
            return None
        return cls(term, qualifier=term_ref.qualifier)


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

    def get_model(self):
        """Returns the model containing this annotable object

        When evaluating annotations we may need to know the context in
        which the annotation was applied to this model element. This is
        an abstract class and we offer no implementation here as each
        element type will have its own implementation."""
        raise NotImplementedError("%r.get_model" % self)


class Term(Annotatable, names.Named):

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

    def get_model(self):
        if self.nametable is not None:
            return self.nametable().get_model()
        else:
            return None

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


class NominalType(Annotatable, names.Named):

    """A Nominal Type

    In Pyslet, all types are represented in the model by *instances* of
    NominalType.  Declared types all have a :attr:`name` and typically a
    base type.

    NominalType instances are callable, returning a :class:`Value`
    instance of an appropriate class for representing a value of the
    type.  The instance returned is a null value of the type (or in the
    case of collections, an empty collection).  When calling a type
    object you *may* pass an optional argument to initialise the the
    value with :meth:`Value.set_value`.

    The string representation of a type is the fully-qualified declared
    name of the type, for undeclared types it is the fully-qualified
    declared name of the base type."""

    def __init__(self, value_type, **kwargs):
        super(NominalType, self).__init__(**kwargs)
        #: the base type (may be None for built-in abstract types)
        self.base = None
        #: the type representing Collection(self)
        self._collection_type = None
        # the class used for values of this type
        self.value_type = value_type
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
            return "<%s>" % self.__class__.__name__

    def __call__(self, value=None):
        if self.value_type:
            v = self.value_type(type_def=self)
            if value is not None:
                v.set_value(value)
            return v
        else:
            raise errors.ODataError(
                "Can't instantiate abstract type: %s" % to_text(self))

    def derive_type(self):
        """Return a new undeclared type derived from this one"""
        new_type = type(self)(value_type=self.value_type)
        new_type.set_base(self)
        return new_type

    def collection_type(self):
        """Return *the* type Collection(self)

        Returns a class representing a Collection of this type.  The new
        CollectionType instance is created the first time the method is
        called and cached thereafter."""
        if self._collection_type is None:
            self._collection_type = CollectionType(
                item_type=self, value_type=self.value_type.collection_class())
        return self._collection_type

    def declare(self, nametable, name):
        try:
            super(NominalType, self).declare(nametable, name)
        except ValueError:
            raise ValueError(errors.Requirement.type_name)

    def get_qname(self):
        """Returns a :class:`names.QualifiedName` named tuple"""
        if self.name is None:
            raise errors.ObjectNotDeclaredError
        return names.QualifiedName(
            namespace=self.nametable().name, name=self.name)

    def set_abstract(self, abstract):
        """Sets this abstract nature of this type

        abstract
            A boolean, on creation types are concrete (abstract is False).

        You cannot modify the abstract nature of a type after it has
        been declared: this restriction ensures that consumers of the
        type can rely on the value of the :attr:`abstract` attribute."""
        if self.nametable:
            raise errors.ObjectDeclaredError(to_text(self))
        if self.base and not self.base.abstract and abstract:
            raise errors.ModelError(
                errors.Requirement.et_abstract_base_s % to_text(self))
        self.abstract = abstract

    def set_base(self, base):
        """Sets the base type of this type

        base
            Must be of the correct type to be the base of the current
            instance.

        You can't set the base for a type of a Collection or of a type
        that has already been declared.

        The default implementation sets :attr:`base` while defending
        against the introduction of inheritance cycles.  It also does a
        basic check of type-compatibility to prevent non-sensical
        relationships such as a ComplexType derived from a
        PrimitiveType."""
        if base.is_derived_from(self):
            raise errors.InheritanceCycleDetected
        if not issubclass(type(self), type(base)):
            # we must be of the same, or a derived type as the base
            raise TypeError(
                "Incompatible type implementations: can't derive %s from %s" %
                (str(self), str(base)))
        if self.value_type is None or issubclass(
                base.value_type, self.value_type):
            # The base imposes a further restriction on us, update our
            # value implementation.
            self.value_type = base.value_type
        elif issubclass(self.value_type, base.value_type):
            # we impose a restriction on the base, OK
            pass
        else:
            # the two value types are unrelated, that's an error!
            raise TypeError(
                "Incompatible value implementations: can't derive %s from %s" %
                (to_text(self), to_text(base)))
        if not base.abstract and self.abstract:
            raise errors.ModelError(
                errors.Requirement.et_abstract_base_s % to_text(self))
        self.base = base
        if self._collection_type:
            self._collection_type.base = base.collection_type()

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

    def common_ancestor(self, other):
        """Returns the common ancestor of this type and other

        Will return None if the two types do not share a common
        ancestor."""
        for t in self.bases():
            for other_t in other.bases():
                if t is other_t:
                    return t
        return None

    def declared_base(self):
        """Returns the first declared base of this type

        Returns None if this type is undeclared and has no declared
        bases."""
        t = self
        while t is not None:
            if t.nametable is not None:
                return t
            t = t.base
        return None

    def declared_bases(self):
        """Iterate this class (if declared) and all it's declared bases

        Undeclared types are used in situations such as facetted
        restrictions of declared primitive types. This iterator will not
        yield these inominate types.  (Special rules apply for
        collection types, see :class:`CollectionType`)."""
        t = self
        while t is not None:
            if t.qname is not None:
                yield t
            t = t.base

    def derived_types(self, context=None):
        """Iterates all types derived from this one.

        context
            Optional context (EntityModel) to search for derived types.
            If omitted defaults to the model that this type was
            originally declared in.

        The yielded types must be strictly derived from this one.
        Therefore, undeclared types, such as types used to create
        constrained sub-types of primitives for property declarations,
        will not yield any derived types.

        This iterator is not recursive, only the immediate descendents
        are returned (see :meth:`all_derived_types` for an alternative).

        For collections, collection types are returned for all types
        derived from the collection's item type."""
        if context is None:
            context = self.get_model()
        if context is not None:
            for s in context.values():
                for t in s.values():
                    if isinstance(t, NominalType) and t.base is self:
                        yield t

    @staticmethod
    def resolve_type(qname, context):
        """Resolves a type name in a context

        qname
            The QualifiedName to resolve

        context
            The context in which to resolve qname, must be a
            QNameTable (e.g., an Entity Model).  If None, a
            ModelError is raised.

        This method looks up qname and returns the resulting type. If
        qname is not the name of any object then KeyError is raised, it
        is the name of a non-type object then ModelError is raised
        instead."""
        if context is not None:
            type_def = context.qualified_get(qname)
        else:
            raise errors.ModelError(
                "no context for resolving type name: %s" %
                to_text(qname))
        if type_def is None:
            raise KeyError(
                "couldn't resolve type name: %s" %
                to_text(qname))
        elif not isinstance(type_def, NominalType):
            raise errors.ModelError(
                "expected type definition: %s" % to_text(qname))
        return type_def

    def compatible(self, other):
        """Returns True if this type is compatible with *other* type

        Types are compatible if a value of *other* type (or a type
        derived from it) may be used, or *implicitly* cast to a value
        that may be used, in a context where a value of this type is
        expected.  All types are compatible with :class:`NullType`.

        The test is loose, if type B is derived from type A then both
        A.compatible(B) and B.compatible(A) are True. The first
        condition is trivially True because all values of type B are
        also values of type A but the reverse is considered True merely
        because there exist *some* values of type A that are also values
        of B.

        In essence, this test is used to determine the potential
        validity of an assignment with unknown values and will only
        return False if such an assignment is bound to fail.

        The default implementation uses the test described above, it
        returns True if other is derived from self or vice versa."""
        return (self is other or self.is_derived_from(other) or
                other.is_derived_from(self) or isinstance(other, NullType))

    def and_type(self, other):
        """Returns the expected outcome of the and operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_and_or)

    def or_type(self, other):
        """Returns the expected outcome of the or operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_and_or)

    def not_type(self):
        """Returns the expected outcome of the not operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_not)

    def eq_type(self, other):
        """Returns the expected outcome of the eq operator

        If values of this type cannot be compared to values of other
        type then an ExpressionError is raised, otherwise, the type
        instance representing Edm.Boolean is returned."""
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s eq %s" % (to_text(self), to_text(other))))

    def ne_type(self, other):
        """Returns the expected outcome of the ne operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s ne %s" % (to_text(self), to_text(other))))

    def gt_type(self, other):
        """Returns the expected outcome of the gt operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s gt %s" % (to_text(self), to_text(other))))

    def ge_type(self, other):
        """Returns the expected outcome of the ge operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s ge %s" % (to_text(self), to_text(other))))

    def lt_type(self, other):
        """Returns the expected outcome of the lt operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s lt %s" % (to_text(self), to_text(other))))

    def le_type(self, other):
        """Returns the expected outcome of the le operator"""
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s le %s" % (to_text(self), to_text(other))))

    def has_type(self, other):
        """Returns the expected outcome of the has operator

        other
            Another NominalType instance use NullType to indicate an
            unknown type.

        The default implementation raises ExpressionError"""
        raise errors.ExpressionError(
            "%s does not support has" % to_text(self))

    def add_type(self, other):
        """Returns the expected outcome of the add operator

        other
            Another NominalType instance use NullType to indicate an
            unknown type.

        The default implementation raises ExpressionError"""
        raise errors.ExpressionError(
            "%s does not support add" % to_text(self))

    def sub_type(self, other):
        """Returns the expected outcome of the sub operator

        other
            Another NominalType instance use NullType to indicate an
            unknown type."""
        raise errors.ExpressionError(
            "%s does not support sub" % to_text(self))

    def mul_type(self, other):
        """Returns the expected outcome of the mul operator

        other
            Another NominalType instance use NullType to indicate an
            unknown type."""
        raise errors.ExpressionError(
            "%s does not support mul" % to_text(self))

    def div_type(self, other):
        """Returns the expected outcome of the div operator

        other
            Another NominalType instance use NullType to indicate an
            unknown type."""
        raise errors.ExpressionError(
            "%s does not support div" % to_text(self))

    def mod_type(self, other):
        """Returns the expected outcome of the mod operator

        other
            Another NominalType instance use NullType to indicate an
            unknown type."""
        raise errors.ExpressionError(
            "%s does not support mod" % to_text(self))

    def negate_type(self):
        """Returns the expected outcome of the negate operator."""
        raise errors.ExpressionError(
            "%s does not support negate" % to_text(self))

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
                if schema.nametable:
                    return schema.nametable()
                else:
                    return None
            else:
                t = t.base
        return None

    def get_odata_type_fragment(self):
        """Returns the fragment identifier representing this type

        This fragment can be appended to the URL of the metadata
        document to make the value for the @odata.type annotation for an
        object.  By implication, you cannot refer to an absract type
        this way (because that type cannot be instantiated as an object)
        so we raise an error for abstract types.

        The default implementation returns #qname if the type has been
        declared or is derived from a base type that has been declared
        (and #name for qnames in the Edm namespace), otherwise it raises
        ObjectNotDeclaredError."""
        t = self.declared_base()
        if t is None:
            raise errors.ObjectNotDeclaredError
        elif t.abstract:
            raise errors.ModelError("Abstract type %s has no context URL" %
                                    to_text(self))
        else:
            if t.nametable().name == "Edm":
                return "#" + t.name
            else:
                return "#" + t.qname

    def bind_to_service(self, service_ref):
        """Binds this type definition to a specific OData service

        service
            A *weak reference* to the service we're binding to."""
        if self.service_ref is not None:
            raise errors.ModelError(
                "%s is already bound to a context" % self.qname)
        self.service_ref = service_ref
        if self._collection_type:
            self._collection_type.service_ref = service_ref

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
            return uri.URI.from_octets(self.get_odata_type_fragment())
        elif svc is not None:
            return uri.URI.from_octets(
                self.get_odata_type_fragment()).resolve(svc.context_base)
        else:
            raise errors.ModelError("%s has no context" % to_text(self))


class NullType(NominalType):

    """A special type used to represent a type-less null"""

    def compatible(self, other):
        return isinstance(other, NominalType)

    def and_type(self, other):
        if isinstance(other, (NullType, BooleanType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                errors.Requirement.annotation_and_or)

    def or_type(self, other):
        if isinstance(other, (NullType, BooleanType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                errors.Requirement.annotation_and_or)

    def not_type(self):
        return BooleanType.edm_base

    def eq_type(self, other):
        if isinstance(other, (NullType, PrimitiveType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "can't compare null eq %s" % to_text(other))

    def ne_type(self, other):
        if isinstance(other, (NullType, PrimitiveType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "can't compare null ne %s" % to_text(other))

    def gt_type(self, other):
        if (isinstance(other, (NullType, PrimitiveType)) and
                not isinstance(other, NoComparisonPrimitiveType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "can't compare null gt %s" % to_text(other))

    def ge_type(self, other):
        if (isinstance(other, (NullType, PrimitiveType)) and
                not isinstance(other, NoComparisonPrimitiveType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "can't compare null ge %s" % to_text(other))

    def lt_type(self, other):
        if (isinstance(other, (NullType, PrimitiveType)) and
                not isinstance(other, NoComparisonPrimitiveType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "can't compare null lt %s" % to_text(other))

    def le_type(self, other):
        if (isinstance(other, (NullType, PrimitiveType)) and
                not isinstance(other, NoComparisonPrimitiveType)):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                "can't compare null le %s" % to_text(other))

    def has_type(self, other):
        if not isinstance(other, EnumerationType):
            raise errors.ExpressionError(
                "has operator requires enumeration type, not %s" %
                to_text(other))
        if not other.is_flags:
            raise errors.ExpressionError(
                "has operator requires flags enumeration, not %s" %
                to_text(other))
        return BooleanType.edm_base

    def add_type(self, other):
        if isinstance(other, (NullType, DurationType)):
            return self
        elif isinstance(other, ByteType):
            # always promoted to Int16
            return Int16Type.edm_base
        elif isinstance(other, NumericType):
            return other
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s add %s" %
                (to_text(self), to_text(other)))

    def sub_type(self, other):
        if isinstance(other, (NullType, DurationType)):
            return self
        elif isinstance(other, (DateType, DateTimeOffsetType)):
            # null sub Date MUST be date sub date = Duration
            return DurationType.edm_base
        elif isinstance(other, ByteType):
            # always promoted to Int16
            return Int16Type.edm_base
        elif isinstance(other, NumericType):
            return other
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s sub %s" %
                (to_text(self), to_text(other)))

    def mul_type(self, other):
        if isinstance(other, (NullType, NumericType)):
            return self
        elif isinstance(other, DurationType):
            return other
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s mul %s" %
                (to_text(self), to_text(other)))

    def div_type(self, other):
        if isinstance(other, (NullType, NumericType)):
            # could be Duration div Numeric
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s mul %s" %
                (to_text(self), to_text(other)))

    def mod_type(self, other):
        if isinstance(other, NullType):
            return self
        elif isinstance(other, ByteType):
            # null div Byte returns Int16
            return Int16Type.edm_base
        elif isinstance(other, NumericType):
            return other
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s mul %s" %
                (to_text(self), to_text(other)))

    def negate_type(self):
        return self


class CollectionType(NominalType):

    """Collections are treated as types in the meta model

    In fact, OData does not allow you to declare a named type to be a
    collection, instead, properties, navigation properties and entity
    collections define collections in terms of single-valued named types.

    To make implementing the model easier we treat these as private type
    definitions.  That is, type definitions that are never declared in
    the associated schema but are used as the type of other elements
    that are part of the model."""

    @classmethod
    def from_types(cls, type_list):
        """Returns a CollectionType instance for multiple types

        type_list
            An iterable of NominalType instances containing the types
            that must be accommodated in the collection.

        Due to type inheritence, a collection can hold values of
        different types provided that they have a common ancestor or can
        be implicitly cast on assignment (in the case of numeric
        promotion).  This method returns a CollectionType instance
        suitable for holding all the types passed in type_list.  If the
        types are incompatible then None is returned.  In the special
        case where type_list is empty then a collection of NullType is
        returned."""
        item_type = None
        numeric = False
        for t in type_list:
            if not isinstance(t, NominalType):
                raise ValueError("Expected NominalType: %r" % t)
            if item_type is None:
                item_type = t
                numeric = isinstance(item_type, NumericType)
            else:
                if numeric and isinstance(t, NumericType):
                    # use numeric promotion
                    new_item_type = item_type._arithmetic_type(t, "with")
                else:
                    new_item_type = item_type.common_ancestor(t)
                    numeric = False
                if (new_item_type is None or
                        new_item_type is PrimitiveType.edm_base or
                        new_item_type is ComplexType.edm_base):
                    # incompatible types
                    raise errors.ExpressionError(
                        errors.Requirement.collection_expression_s %
                        ("%s in list of %s" %
                         (to_text(t), to_text(item_type))))
                item_type = new_item_type
        if item_type is None:
            item_type = NullType.edm_base
        return item_type.collection_type()

    def __init__(self, item_type, **kwargs):
        super(CollectionType, self).__init__(**kwargs)
        #: the type being collected, we do not allow collections of
        #: collections
        if isinstance(item_type, CollectionType) or not isinstance(
                item_type, NominalType):
            raise TypeError("Can't create Collection(%s)" % to_text(item_type))
        self.item_type = item_type
        if self.item_type.base:
            self.base = self.item_type.base.collection_type()
        self.service_ref = self.item_type.service_ref

    def __unicode__(self):
        return to_text("Collection(%s)" % to_text(self.item_type))

    def derive_type(self):
        """You cannot derive a new type from a Collection"""
        raise TypeError("Can't derive a new type from %s" % to_text(self))

    def declare(self, nametable, name):
        """You cannot declare Collection types"""
        raise TypeError("Can't declare %s" % to_text(self))

    def set_abstract(self, abstract):
        if abstract:
            raise TypeError("Can't make %s abstract" % to_text(self))

    def set_base(self, base):
        raise TypeError("Can't set the base of %s" % to_text(self))

    def declared_base(self):
        """Returns the first declared base of this type

        For the purposes of this method (and :meth:`declared_bases`) a
        CollectionType is considered to be declared if its item_type is
        declared."""
        t = self
        while t is not None:
            if t.item_type.nametable is not None:
                return t
            t = t.base
        return None

    def declared_bases(self):
        """Iterate this class (if declared) and all it's declared bases

        For the purposes of this method (and :meth:`declared_base`) a
        CollectionType is considered to be declared if its item_type is
        declared."""
        t = self
        while t is not None:
            if t.item_type.nametable is not None:
                yield t
            t = t.base

    def derived_types(self, context=None):
        if context is None:
            context = self.get_model()
        if context is not None:
            for s in context.values():
                for t in s.values():
                    if isinstance(t, NominalType) and t.base is self.item_type:
                        yield t.collection_type()

    def get_model(self):
        """Returns the model in which the item type was declared"""
        return self.item_type.get_model()

    def get_odata_type_fragment(self):
        """Returns the fragment identifier of this collection type

        Returns Collection(<item_type>) using the fully qualified name
        of the item type even if it is in the built-in Edm namespace.

        Unlike single types, collections are never abstract (even if the
        corresponding item type is abstract) and so this method will only
        raise an error if there is no declared base."""
        t = self.declared_base()
        if t is None:
            raise errors.ObjectNotDeclaredError
        else:
            return "#Collection(%s)" % t.item_type.qname

    def bind_to_service(self, service_ref):
        raise TypeError("Can't bind %s" % to_text(self))


class PrimitiveType(NominalType):

    """A Primitive Type declaration

    Instances represent primitive type delcarations, such as those made
    by a TypeDefinition.  The built-in Edm Schema contains instances
    representing the base primitie types themselves and properties use
    this class to create undeclared types to constrain their values.

    The base type, and facet values are frozen when the type is first
    declared and the methods that modify them will raise errors if
    called after that."""

    #: set to an the instance used to define the Edm base type for each
    #: NominalType.  The value is set later when the builtin types are
    #: actually defined.  The exception is the NullType is not defined a
    #: named type in the Edm but which does have a special instanced
    #: defined for use as a type-less null during expression processing.
    edm_base = None

    def __init__(self, **kwargs):
        super(PrimitiveType, self).__init__(**kwargs)
        # self.value_type = PrimitiveValue
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
        self._srid = -1

    def set_base(self, base):
        """Sets the base type of this type

        The base must also be a PrimitiveType."""
        super(PrimitiveType, self).set_base(base)
        # now copy over strongly specified facets
        if base.max_length is not None:
            self.set_max_length(base.max_length)
        if base.unicode is not None:
            self.set_unicode(base.unicode)
        if base.precision is not None or base.scale is not None:
            self.set_precision(base.precision, base.scale)
        if base.srid is not None:
            self.set_srid(base.srid)

    def get_max_length(self):
        """Returns the MaxLength facet value in effect.

        The returned value may be 0 (max) or a postive integer
        indicating a restriction on the maximum length of the value.
        This method is used when processing values as the
        :attr:`max_length` attribute only reflects an explicitly set
        facet in a custom type definition and so may be None
        (unspecified)."""
        return self._max_length

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

        Can only be set for undeclared primitive types with underlying
        type Binary, Stream or String."""
        self.validate_max_length(max_length)
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
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

    def validate_max_length(self, max_length):
        logging.warning("MaxLength specified for %s", to_text(self))

    def get_unicode(self):
        """Returns the Unicode facet value in effect.

        The returned value may be True or False indicating whether or
        not Unicode strings are allowed.  This method is used when
        processing values as the :attr:`unicode` attribute only reflects
        an explicitly set facet in a custom type definition and so may
        be None (unspecified)."""
        return self._unicode

    def set_unicode(self, unicode_facet, can_override=False):
        """Sets the Unicode facet of this type

        unicode_facet
            A boolean

        can_override
            See :meth:`set_max_length` for details

        Can only be set on undeclared primitive types with underlying
        type String."""
        self.validate_unicode(unicode_facet)
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
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

    def validate_unicode(self, unicode_facet):
        logging.warning("Unicode facet specified for %s", to_text(self))

    def set_precision(self, precision, scale=None, can_override=False):
        """Sets the Precision and (optionally) Scale facets

        precision
            A non-negative integer

        scale
            An non-negative integer or -1 indicating variable scale

        can_override
            See :meth:`set_max_length` for details

        Precision and Scale can only be set on undeclared primitive
        types with underlying type Decimal.  Precision on its own can be
        set on types with underlying temporal type.

        There is no explicit constraint in the specification that says
        you cannot set Scale without Precision for Decimal types.
        Therefore we allow precision=None and use our default internal
        limit (typically 28 in the Python decimal module) instead."""
        self.validate_precision(precision, scale)
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if can_override:
            # weak values are overridden by existing strong values we
            # leave it to the individual precision-handling types to
            # store the values in effect and manage only the storage
            # of strong values here
            return
        else:
            # strong values
            if precision is not None:
                if self.precision is not None:
                    raise errors.ModelError(
                        errors.Requirement.td_facet_s %
                        ("%s.Precision" % to_text(self)))
                self.precision = precision
            if scale is not None:
                if self.scale is not None:
                    raise errors.ModelError(
                        errors.Requirement.td_facet_s % "Scale")
                self.scale = scale

    def validate_precision(self, precision, scale):
        logging.warning(
            "Precision/Scale facet specified for %s", to_text(self))

    def get_srid(self):
        """Gets the SRID facet in effect.

        Returns a non-negative integer representing the SRID in effect
        or -1 if the SRID may vary for this type."""
        return self._srid

    def set_srid(self, srid, can_override=False):
        """Sets the SRID facet of this property

        srid
            A non-negative integer or -1 for variable

        can_override
            See :meth:`set_max_length` for details"""
        self.validate_srid(srid)
        if self.name:
            raise errors.ObjectDeclaredError(self.qname)
        if srid < -1:
            raise errors.ModelError(errors.Requirement.srid_value)
        if can_override:
            # sets a weak value, ignored if already specified
            if self.srid is not None:
                return
        else:
            # sets a strong value, error if already specified
            if self.srid is not None:
                raise errors.ModelError(
                    errors.Requirement.td_facet_s %
                    ("%s.SRID" % to_text(self)))
            self.srid = srid
        self._srid = srid

    def validate_srid(self, srid):
        logging.warning(
            "SRID facet specified for %s", to_text(self))

    def compatible(self, other):
        """Returns True if primitive types are compatible"""
        # if the *python* types used to represent these type objects
        # are in the same hierarchy they are compatible. OData does
        # not make this explicit, in other words, the abstract test
        # described in :meth:`NominalType.compatible` must be made
        # looser still as two types that share a common underlying
        # primitive type are compatible, e.g., Strings with
        # differing MaxLength facets can be implicitly converted.
        if isinstance(other, NullType):
            return True
        else:
            pt1, pt2 = type(self), type(other)
        return issubclass(pt2, PrimitiveType) and (
             issubclass(pt1, pt2) or issubclass(pt2, pt1))

    def cmp_type(self, other, op):
        if not self.compatible(other):
            raise errors.ExpressionError(
                errors.Requirement.annotation_comparison_s %
                ("%s %s %s" % (to_text(self), op, to_text(other))))
        return BooleanType.edm_base

    def eq_type(self, other):
        return self.cmp_type(other, "eq")

    def ne_type(self, other):
        return self.cmp_type(other, "ne")

    def gt_type(self, other):
        return self.cmp_type(other, "gt")

    def ge_type(self, other):
        return self.cmp_type(other, "ge")

    def lt_type(self, other):
        return self.cmp_type(other, "lt")

    def le_type(self, other):
        return self.cmp_type(other, "le")

    def match(self, other):
        """Returns True if this primitive type matches other

        Other must also be of the same underlying PrimtiveType, have the
        same underlying value type and any constrained facets are
        constrained in the same way.  If a facet is specified by only
        one of the types they are considered matching."""
        if type(other) is not type(self) or \
                self.value_type is not other.value_type:
            return False
        if self.unicode is not None and other.unicode is not None and \
                self.unicode != other.unicode:
            return False
        if self.max_length is not None and other.max_length is not None and \
                self.max_length != other.max_length:
            return False
        if self.precision is not None and other.precision is not None and \
                self.precision != other.precision:
            return False
        if self.scale is not None and other.scale is not None and \
                self.scale != other.scale:
            return False
        if self.srid is not None and other.srid is not None and \
                self.srid != other.srid:
            return False
        return True

    def derived_match(self, other):
        """Sub-type test

        Returns True if this primitive type is considered a sub-type of
        other. Unlike :meth:`match` which tests that the facets are
        exactly the same, this method uses a looser test that simply
        determines if all values of this type can also be considered
        values of type *other*. For example, if this type is Edm.String
        with MaxLength=10 and the *other* type is the more generous
        Edm.String with MaxLength=20 then we return True indicating that
        this type's value space is a special subset of the *other*
        type's value space (roughly akin to deriving structured
        types)."""
        if type(other) is not type(self) or \
                self.value_type is not other.value_type:
            return False
        if self.unicode is not None and other.unicode is not None and \
                self.unicode and not other.unicode:
            # All unicode values are not ASCII values
            return False
        if self.max_length is not None and other.max_length is not None and \
                self.max_length > other.max_length:
            # we accept longer strings
            return False
        if self.precision is not None and other.precision is not None and \
                self.precision > other.precision:
            # we accept more digits of precision
            return False
        if self.scale is not None and other.scale is not None and \
                (other.scale > -1 and
                 (self.scale > other.precision or self.scale == -1)):
            # we accept more digits to the right of the decimal point
            return False
        if self.srid is not None and other.srid is not None and \
                self.srid != other.srid:
            # we have different co-ordinate systems
            return False
        return True


class NoComparisonPrimitiveType(PrimitiveType):

    def eq_type(self, other):
        if isinstance(other, NullType):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                errors.Requirement.annotation_comparison_s %
                ("%s eq %s" % (to_text(self), to_text(other))))

    def ne_type(self, other):
        if isinstance(other, NullType):
            return BooleanType.edm_base
        else:
            raise errors.ExpressionError(
                errors.Requirement.annotation_comparison_s %
                ("%s ne %s" % (to_text(self), to_text(other))))

    def gt_type(self, other):
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s gt %s" % (to_text(self), to_text(other))))

    def ge_type(self, other):
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s ge %s" % (to_text(self), to_text(other))))

    def lt_type(self, other):
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s lt %s" % (to_text(self), to_text(other))))

    def le_type(self, other):
        raise errors.ExpressionError(
            errors.Requirement.annotation_comparison_s %
            ("%s le %s" % (to_text(self), to_text(other))))


class NumericType(PrimitiveType):

    def compatible(self, other):
        """Returns True if other is also a Numeric type

        Also returns True if other is an abstract PrimitiveType
        instance or NullType."""
        if issubclass(type(other), (NumericType, NullType)):
            return True
        else:
            return super(NumericType, self).compatible(other)

    def _arithmetic_type(self, other, op):
        raise NotImplementedError

    def add_type(self, other):
        return self._arithmetic_type(other, "add")

    def sub_type(self, other):
        return self._arithmetic_type(other, "sub")

    def mul_type(self, other):
        if isinstance(other, (DurationType, NullType)):
            return other
        else:
            return self._arithmetic_type(other, "mul")

    def div_type(self, other):
        return self._arithmetic_type(other, "div")

    def mod_type(self, other):
        return self._arithmetic_type(other, "mod")

    def negate_type(self):
        return self


class IntegerType(NumericType):

    pass


class FloatType(NumericType):

    pass


class TemporalSecondsType(PrimitiveType):

    # default used for temporal rounding (no fractional seconds)
    temporal_q = decimal.Decimal((0, (1, ), 0))

    def validate_precision(self, precision, scale):
        if scale is not None:
            logging.warning(
                "Scale facet specified for %s", to_text(self))
        if precision is not None and (precision < 0 or precision > 12):
            raise errors.ModelError(
                errors.Requirement.temporal_precision)

    def set_precision(self, precision, scale=None, can_override=False):
        super(TemporalSecondsType, self).set_precision(
            precision, scale, can_override)
        if can_override:
            if self.precision is not None:
                precision = self.precision
        # using existing strong values if unspecified
        if precision is None:
            precision = self.precision
        # now update the class attributes that define the default
        # temporal precision
        if precision is None:
            # no precision = 0
            self.temporal_q = decimal.Decimal((0, (1, ), 0))
        else:
            # overload the class attribute
            self.temporal_q = decimal.Decimal(
                (0, (1, ) * (precision + 1), -precision))

    def truncate(self, s):
        # truncate a seconds value to the active temporal precision
        if isinstance(s, float):
            s = decimal.Decimal(
                repr(s)).quantize(self.temporal_q, rounding=decimal.ROUND_DOWN)
            if self.temporal_q.as_tuple().exponent == 0:
                return int(s)
            else:
                return float(s)
        else:
            return s


class BinaryType(NoComparisonPrimitiveType):

    def validate_max_length(self, max_length):
        pass


class BooleanType(PrimitiveType):

    def and_type(self, other):
        if isinstance(other, (NullType, BooleanType)):
            return self.edm_base
        else:
            raise errors.ExpressionError(
                errors.Requirement.annotation_and_or)

    def or_type(self, other):
        if isinstance(other, (NullType, BooleanType)):
            return self.edm_base
        else:
            raise errors.ExpressionError(
                errors.Requirement.annotation_and_or)

    def not_type(self):
        return self.edm_base


class ByteType(IntegerType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, (FloatType, Int64Type, Int32Type, Int16Type,
                              DecimalType)):
            return other
        elif isinstance(other, (ByteType, SByteType, NullType)):
            return Int16Type.edm_base
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))

    def negate_type(self):
        return Int16Type.edm_base


class DateTimeOffsetType(TemporalSecondsType):

    def add_type(self, other):
        """DateTimeOffset supports add only with Duration"""
        if isinstance(other, (NullType, DurationType)):
            # self add null = self
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operating: %s add %s" %
                (to_text(self), to_text(other)))

    def sub_type(self, other):
        """DateTimeOffset supports sub with DateTimeOffset and Duration"""
        if isinstance(other, NullType):
            return other
        elif isinstance(other, DurationType):
            return self
        elif isinstance(other, DateTimeOffsetType):
            return DurationType.edm_base
        else:
            raise errors.ExpressionError(
                "Unsupported operating: %s sub %s" %
                (to_text(self), to_text(other)))


class DateType(PrimitiveType):

    def add_type(self, other):
        """Date supports add only with Duration"""
        if isinstance(other, (NullType, DurationType)):
            # self add null = self
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operating: %s add %s" %
                (to_text(self), to_text(other)))

    def sub_type(self, other):
        """Date supports sub with Date and Duration"""
        if isinstance(other, NullType):
            return other
        elif isinstance(other, DurationType):
            return self
        elif isinstance(other, DateType):
            return DurationType.edm_base
        else:
            raise errors.ExpressionError(
                "Unsupported operating: %s sub %s" %
                (to_text(self), to_text(other)))


class DecimalType(NumericType):

    # defaults used for Decimal rounding, overridden by instance
    # variables for actual Decimal types.
    dec_nleft = decimal.getcontext().Emax + 1
    dec_nright = -(decimal.getcontext().Emin - decimal.getcontext().prec + 1)
    dec_digits = (1, ) * decimal.getcontext().prec

    def validate_precision(self, precision, scale):
        if precision is None:
            precision = self.precision
        if scale is None:
            scale = self.scale
        if precision is not None:
            if precision <= 0:
                raise errors.ModelError(
                    errors.Requirement.decimal_precision)
            if scale is not None and scale > precision:
                raise errors.ModelError(
                    errors.Requirement.scale_gt_precision)

    def set_precision(self, precision, scale=None, can_override=False):
        super(DecimalType, self).set_precision(precision, scale, can_override)
        # replace unspecified values with existing strong value (if
        # already specified)
        if can_override:
            if self.precision is not None:
                precision = self.precision
            if self.scale is not None:
                scale = self.scale
        else:
            # using existing strong values if unspecified
            if precision is None:
                precision = self.precision
            if scale is None:
                scale = self.scale
        # now update the class attributes that define the default
        # decimal precision
        if precision is None:
            precision = self.precision
        if scale is None:
            scale = self.scale
        if precision is None:
            if scale is None or scale < 0:
                # both unspecified or variable scale, limit right
                # digits to default decimal context
                self.dec_nright = DecimalType.dec_nright
            else:
                # Undefined precision, default Scale (could be
                # implied 0) don't limit left digits but as scale
                # must be <= precision, limit right digits
                self.dec_nright = scale
            self.dec_nleft = DecimalType.dec_nleft
            self.dec_digits = DecimalType.dec_digits
        else:
            if scale is None:
                # for decimals scale defaults to 0 but can be
                # overridden in a sub-type
                self.dec_nleft = precision
                self.dec_nright = 0
            elif scale < 0:
                # variable scale, up to precision on the right
                self.dec_nleft = DecimalType.dec_nleft
                self.dec_nright = precision
            else:
                self.dec_nleft = precision - scale
                self.dec_nright = scale
            self.dec_digits = (1, ) * min(decimal.getcontext().prec,
                                          precision)

    def round(self, value):
        precision = len(self.dec_digits)
        vt = value.as_tuple()
        vprec = len(vt.digits)
        # check bounds on exponent
        if vt.exponent + vprec > self.dec_nleft:
            raise ValueError("Value too large for scaled Decimal")
        if vt.exponent + vprec >= precision:
            # negative scale results in integer (perhaps with trailing
            # zeros)
            q = decimal.Decimal(
                (0, self.dec_digits, vprec + vt.exponent - precision))
        else:
            # some digits to the right of the decimal point, this needs
            # a litte explaining.  We take the minimum of:
            #   1. the specified max scale in the type
            #   2. the number of digits to the right of the point in the
            #      original value (-vt.exponent) - to prevent spurious 0s
            #   3. the number of digits to the right of the point after
            #      rounding to the current precision - to prevent us
            #      exceeding precision
            rdigits = min(self.dec_nright, -vt.exponent,
                          max(0, precision - (vprec + vt.exponent)))
            q = decimal.Decimal((0, self.dec_digits, -rdigits))
        return value.quantize(q, rounding=decimal.ROUND_HALF_UP)

    def _arithmetic_type(self, other, op):
        if isinstance(other, FloatType):
            return other
        elif isinstance(other, (NullType, SByteType, ByteType, Int16Type,
                                Int32Type, Int64Type, DecimalType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class DoubleType(FloatType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, (NullType, NumericType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class DurationType(TemporalSecondsType):

    def add_type(self, other):
        if isinstance(other, (NullType, DurationType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s add %s" %
                (to_text(self), to_text(other)))

    def sub_type(self, other):
        if isinstance(other, (NullType, DurationType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s sub %s" %
                (to_text(self), to_text(other)))

    def mul_type(self, other):
        if isinstance(other, (NullType, NumericType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s mul %s" %
                (to_text(self), to_text(other)))

    def div_type(self, other):
        if isinstance(other, (NullType, NumericType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s div %s" %
                (to_text(self), to_text(other)))

    def negate_type(self):
        return self


class GeoType(NoComparisonPrimitiveType):

    def validate_srid(self, srid):
        pass

    def compatible(self, other):
        """Returns True if geography types are compatible"""
        if isinstance(other, NullType):
            return True
        elif isinstance(other, (GeographyType, GeometryType)):
            return self.value_type.compatible(other.value_type)
        else:
            return False


class GeographyType(GeoType):

    def __init__(self, **kwargs):
        super(GeographyType, self).__init__(**kwargs)
        self._srid = 4326


class GeographyPointType(GeographyType):

    pass


class GeographyLineStringType(GeographyType):

    pass


class GeographyPolygonType(GeographyType):

    pass


class GeographyMultiPointType(GeographyType):

    pass


class GeographyMultiLineStringType(GeographyType):

    pass


class GeographyMultiPolygonType(GeographyType):

    pass


class GeographyCollectionType(GeographyType):

    pass


class GeometryType(GeoType):

    def __init__(self, **kwargs):
        super(GeometryType, self).__init__(**kwargs)
        self._srid = 0


class GeometryPointType(GeometryType):

    pass


class GeometryLineStringType(GeometryType):

    pass


class GeometryPolygonType(GeometryType):

    pass


class GeometryMultiPointType(GeometryType):

    pass


class GeometryMultiLineStringType(GeometryType):

    pass


class GeometryMultiPolygonType(GeometryType):

    pass


class GeometryCollectionType(GeometryType):

    pass


class GuidType(PrimitiveType):

    pass


class Int16Type(IntegerType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, NullType):
            return self
        elif isinstance(other, (FloatType, Int64Type, Int32Type, DecimalType)):
            return other
        elif isinstance(other, (SByteType, ByteType, Int16Type)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class Int32Type(IntegerType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, NullType):
            return self
        elif isinstance(other, (FloatType, Int64Type, DecimalType)):
            return other
        elif isinstance(other, (SByteType, ByteType, Int16Type, Int32Type)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class Int64Type(IntegerType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, NullType):
            return self
        elif isinstance(other, (FloatType, DecimalType)):
            return other
        elif isinstance(other, (SByteType, ByteType, Int16Type, Int32Type,
                                Int64Type)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class SByteType(IntegerType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, (NullType, SByteType)):
            return self
        elif isinstance(other, ByteType):
            return Int16Type.edm_base
        elif isinstance(other, NumericType):
            return other
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class SingleType(FloatType):

    def _arithmetic_type(self, other, op):
        if isinstance(other, DoubleType):
            return other
        elif isinstance(other, (NullType, NumericType)):
            return self
        else:
            raise errors.ExpressionError(
                "Unsupported operation: %s %s %s" %
                (to_text(self), op, to_text(other)))


class StreamType(NoComparisonPrimitiveType):

    def validate_max_length(self, max_length):
        pass


class StringType(PrimitiveType):

    def validate_max_length(self, max_length):
        pass

    def validate_unicode(self, unicode_facet):
        pass


class TimeOfDayType(TemporalSecondsType):

    pass


class EnumerationType(names.NameTable, PrimitiveType):

    """An EnumerationType declaration"""

    csdl_name = "EnumType"

    def __init__(self, underlying_type, **kwargs):
        super(EnumerationType, self).__init__(**kwargs)
        #: whether or not values are being auto-assigned None means
        #: 'undetermined', only possible when there are no members
        self._assigned_values = None
        #: whether or not this type is a flags-based enumeration
        self.is_flags = False
        #: the list of members in the order they were declared
        self.members = []
        # a mapping from values to the first declared member with that
        # value
        self._valuetable = {}
        self.set_underlying_type(underlying_type)

    def derive_type(self):
        """Return a new undeclared type derived from this one"""
        raise errors.ModelError("Enumerations cannot be used as base types")

    def set_abstract(self, abstract):
        if abstract:
            raise TypeError("Can't make %s abstract" % to_text(self))

    def set_base(self, base):
        if type(base) is not PrimitiveType:
            raise errors.ModelError(
                "Bad type for Enumeration base: %s" % to_text(base))
        super(EnumerationType, self).set_base(base)

    def set_underlying_type(self, underlying_type):
        """Changes the underlying type of this Enumeration

        underlying_type
            An :class:`IntegerType` instance.

        You can't change the underlying type of an enumeration if it
        already contains declared members or if it has, itself, been
        declared."""
        if self.nametable is not None:
            raise errors.ObjectDeclaredError
        if self.members:
            raise errors.ObjectDeclaredError("%s has members" % to_text(self))
        if not isinstance(underlying_type, IntegerType):
            # edm['Byte'], edm['SByte'], edm['Int16'], edm['Int32'],
            # edm['Int64']
            raise errors.ModelError(
                errors.Requirement.ent_type_s % to_text(underlying_type))
        self.underlying_type = underlying_type

    def has_type(self, other):
        if not self.is_flags:
            raise errors.ExpressionError(
                "has operator requires flags enumeration, not %s" %
                to_text(self))
        if other is not self:
            raise errors.ExpressionError(
                "has operator enumeration type mismatch, %s has %s" %
                (to_text(self), to_text(self)))
        return BooleanType.edm_base

    def set_is_flags(self):
        """Sets is_flags to True.

        You can't change the flags mode of an enumeration if it already
        contains declared members or if it has, itself, been declared."""
        if self.nametable is not None:
            raise errors.ObjectDeclaredError
        if self.members:
            raise errors.ObjectDeclaredError(
                "Can't set is_flags on Enumeration with existing members")
        self._assigned_values = False
        self.is_flags = True

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a member name

        Enumeration members are qualified by prefixing with the
        qualified name of the EnumerationType followed by the member
        name in single quotes.  If the enumeration is not declared
        then just the single-quoted name is returned."""
        if self.qname:
            return "%s'%s'" % (self.qname, name)
        else:
            return "'%s'" % name

    def check_value(self, value):
        if not isinstance(value, Member):
            raise TypeError("Member required, found %s" % repr(value))
        # The value of the Member must be None (for auto assigned) or a
        # valid value of the base type
        if value.value is not None:
            v = self.underlying_type()
            try:
                v.set_value(value.value)
            except ValueError as err:
                raise errors.ModelError(
                    errors.Requirement.ent_valid_value_s %
                    ("%s: %s" % (self.qname, str(err))))

    def __setitem__(self, key, value):
        self.check_value(value)
        if self._assigned_values is None:
            self._assigned_values = value.value is None
        if self._assigned_values:
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
        if not isinstance(value, (int, long2)):
            raise ValueError("integer or string required")
        if not self.is_flags:
            raise TypeError("%s is not a flags EnumType" % to_text(self))
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
                    if match.value & m.value == match.value and \
                            match.value != m.value:
                        del result[i]
                        # but we better add m now!
                        add_m = True
                    else:
                        i += 1
                if add_m:
                    result.append(m)
                    # expand rmask
                    rmask |= m.value
        if rmask != value:
            # We failed to span the required value
            raise ValueError("%i is not a declared member of %s" %
                             (value, to_text(self)))
        return result


class Member(names.Named):

    """Represents a member of an enumeration"""

    csdl_name = "Member"

    def __init__(self, **kwargs):
        super(Member, self).__init__(**kwargs)
        #: the integer value corresponding to this member
        #: defaults to None: auto-assigned when declared
        self.value = None


class PathType(PrimitiveType):

    pass


class StructuredType(names.NameTable, NominalType):

    """A Structured Type declaration

    Structured types are nametables in their own right, behaving as
    dictionaries with property names as keys and :class:`Property` (or
    :class:`NavigationProperty`) instances as the dictionary values.

    While the declaration's nametable is open new properties can be
    added but once it is closed the type is considered complete.  There
    are some restrictions on which operations are allowed on
    complete/incomplete type declarations.  The most important being
    that the you can't use a type as a base type until it is complete."""

    def __init__(self, **kwargs):
        super(StructuredType, self).__init__(**kwargs)
        #: whether or not this is an open type, defaults to False
        self.open_type = False
        #: Property/Navigation properties sorted in declaration order
        self._plist = []

    def __setitem__(self, key, value):
        i = len(self._plist)
        try:
            super(StructuredType, self).__setitem__(key, value)
        finally:
            # callbacks could generate exceptions after a successful
            # insertion so wrap this in finally and test that our value
            # really did get inserted.  Also, we can't rule out a
            # callback declaring a name in the table too so we insert
            # our item rather than simply append
            if self.get(key, None) is value:
                self._plist.insert(i, value)

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if not self.is_simple_identifier(name):
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

    def derive_type(self):
        """Return a new undeclared type derived from this one

        If this type is an OpenType the derived type is also set to be
        open."""
        new_type = type(self)(value_type=self.value_type)
        if self.open_type:
            new_type.set_open_type(True)
        new_type.set_base(self)
        return new_type

    def set_abstract(self, abstract):
        """A complete structured type can't be made abstract"""
        if self.closed:
            raise errors.ModelError(
                "Can't set abstract on %s (declaration is complete)" %
                self.qname)
        super(StructuredType, self).set_abstract(abstract)

    def set_base(self, base):
        """Sets the base type of this type

        When structured types are associated with a base type the
        properties of the base type are copied on closure, therefore the
        type must be incomplete when the base is set and the base MUST
        be closed before the derived type.

        We currently enforce the stricter rule that the base type MUST
        itself be closed before it can be set as the base of another
        type."""
        if base.is_derived_from(self):
            if isinstance(self, ComplexType):
                raise errors.InheritanceCycleDetected(
                    errors.Requirement.ct_cycle_s % to_text(self))
            else:
                raise errors.InheritanceCycleDetected(
                    errors.Requirement.et_cycle_s % to_text(self))
        if not base.closed:
            raise errors.ModelError(
                "Can't set base on %s (declaration of %s is incomplete)" %
                (to_text(self), to_text(base)))
        if self.closed:
            raise errors.ModelError(
                "Can't set base on %s (declaration is complete)" %
                to_text(self))
        if base.open_type and not self.open_type:
            if isinstance(self, ComplexType):
                raise errors.ModelError(
                    errors.Requirement.ct_open_base_s % to_text(self))
            else:
                raise errors.ModelError(
                    errors.Requirement.et_open_base_s % to_text(self))
        super(StructuredType, self).set_base(base)

    def set_open_type(self, open_type):
        if self.closed or self.nametable:
            raise errors.ModelError(
                "Can't set open_type on %s as it is already declared "
                "or complete" % self.qname)
        self.open_type = open_type

    def properties(
            self, expand_complex=False, expand_contained=False,
            expand_all_nav=False, expand_collections=False,
            expand_derived=None, max_depth=1, _from_p=None,
            _ignore_base=False):
        """Generates all properties of this type

        expand_complex (False)
            A boolean argument where True means that complex types will
            be expanded and the individual properties returned *in
            addition to* a single result representing the entire complex
            property.

        expand_contained (False)
            A boolean argument where True means that containment
            navigation properties will be expanded and the contained
            entity's properties returned *in addition to* a single
            result representing the containment navigation property
            itself.

        expand_all_nav (False)
            A boolean argument where True means that all navigation
            properties will be expanded and the related entity's
            properties returned *in addition to* a single result
            representing the navigation property itself.  This value
            overrides implies expand_contained and will override
            expand_contained=False.

        expand_collections (False)
            Although this iterator may expand complex types and
            navigation properties is does *not* expand collections of
            complex types or collection-valued navigation properties by
            default.  Set this argument to True *in addition to one or
            more of the expand\_ arguments* to expand these as if they
            were single valued.  The resulting paths are not valid
            resource paths but may be used in other contexts where
            iteration of the collection's items is implied (such as
            annotations).

        expand_derived (None)
            If not None, contains a context (:class:`EntityModel`
            instance) to use to generate expanded properties from
            complex and entity types derived from those declared in this
            type.  The yielded paths contain the property names preceded
            by the appropriate qualified name of the defining derived
            type.

        max_depth (1)
            By default, navigation properties are not expanded
            recursively and so navigation properties of related entities
            are not, themselves, expanded.  You can use the max_depth
            argument to increase the depth of the expansion.

        It yields tuples of (path, property) for both structural and
        navigation properties.  The properties are generated in the
        order in which they were declared with inhertied properties
        first."""
        if expand_all_nav:
            expand_contained = True
        for p in self._plist:
            if _ignore_base and p.nametable() is not self:
                continue
            path = (p.name, )
            yield path, p
            if isinstance(p, NavigationProperty):
                if max_depth <= 0:
                    continue
                if not expand_contained:
                    continue
                if not p.containment and not expand_all_nav:
                    continue
                if p.collection and not expand_collections:
                    continue
                for npath, np in p.entity_type.properties(
                        expand_complex=expand_complex,
                        expand_contained=expand_contained,
                        expand_all_nav=expand_all_nav,
                        expand_collections=expand_collections,
                        expand_derived=expand_derived,
                        max_depth=max_depth - 1,
                        _from_p=p):
                    yield path + npath, np
                if expand_derived:
                    for t in p.entity_type.derived_types(
                            context=expand_derived):
                        tpath = path + (t.qname, )
                        for npath, np in t.properties(
                                expand_complex=expand_complex,
                                expand_contained=expand_contained,
                                expand_all_nav=expand_all_nav,
                                expand_collections=expand_collections,
                                expand_derived=expand_derived,
                                max_depth=max_depth - 1,
                                _from_p=p, _ignore_base=True):
                            yield tpath + npath, np
            else:
                if isinstance(p.type_def, CollectionType):
                    if not expand_collections:
                        continue
                    ptype = p.type_def.item_type
                else:
                    ptype = p.type_def
                if isinstance(ptype, ComplexType) and expand_complex:
                    for cpath, cp in ptype.properties(
                            expand_complex=True,
                            expand_contained=expand_contained,
                            expand_all_nav=expand_all_nav,
                            expand_collections=expand_collections,
                            expand_derived=expand_derived,
                            max_depth=max_depth,
                            _from_p=_from_p):
                        yield path + cpath, cp
                    if expand_derived:
                        for t in ptype.derived_types(context=expand_derived):
                            tpath = path + (t.qname, )
                            for cpath, cp in t.properties(
                                    expand_complex=expand_complex,
                                    expand_contained=expand_contained,
                                    expand_all_nav=expand_all_nav,
                                    expand_collections=expand_collections,
                                    expand_derived=expand_derived,
                                    max_depth=max_depth,
                                    _from_p=_from_p, _ignore_base=True):
                                yield tpath + cpath, cp

    @staticmethod
    def navigation_properties(properties):
        """Filter for navigation properties

        properties
            An iterable of (path, property) tuples such as would be returned
            by :meth:`properies`.

        Filters properties yielding only the tuples corresponding to
        navigation properties."""
        for path, p in properties:
            if isinstance(p, NavigationProperty):
                yield path, p

    def check_navigation(self):
        for n, p in self.items():
            if isinstance(p, Property) and \
                    isinstance(p.type_def, CollectionType) and \
                    isinstance(p.type_def.item_type, ComplexType):
                # a collection of complex values
                for path, np in p.type_def.item_type.navigation_properties(
                        p.type_def.item_type.properties(expand_complex=True)):
                    logging.debug("Checking %s/%s/%s for containment",
                                  to_text(self), n, names.path_to_str(path))
                    if np.containment:
                        raise errors.ModelError(
                            errors.Requirement.nav_contains_s % p.qname)

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
            save_list = self._plist
            self._plist = []
            for pname, p in self.base.properties():
                try:
                    p.declare(self, pname[0])
                except errors.DuplicateNameError:
                    raise errors.DuplicateNameError(
                        errors.Requirement.property_unique_s %
                        ("%s/%s" % (to_text(self), pname[0])))
            self._plist += save_list
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
                    for ti in t.bases():
                        for annotation in ti.annotations.values():
                            logging.debug(
                                "Annotating %s with %s", p.qname,
                                annotation.name)
                            annotation.declare(p.annotations, annotation.name)
        except errors.DuplicateNameError as err:
            raise errors.ModelError(
                errors.Requirement.td_annotation_s % to_text(err))

    def canonical_get(self, name, base_type=None):
        """Does a canonical lookup of a named property

        Returns a tuple of instances: (StructuredType, Property) after
        looking up a named property.

        The type returned is the most general type containing the named
        property.  This may be the current type but it may also be one
        of the current type's base types if the property is inherited.

        The optional base_type argument allows you to terminate the
        search early: if name is defined in base_type then base_type is
        returned even if the property was actually defined in one of
        *its* base types.

        This method is used in situations where a type-cast segment is
        given for a property, for example, suppose we have a type
        hierarchy of TypeC derived from TypeB which is, in turn, derived
        from TypeA. If property B is defined on TypeB then::

            TypeC.canonical_get("B")    # returns (TypeB, PropertyB)"""
        match_property = self[name]
        if base_type is not None and name in base_type:
            return (base_type, match_property)
        match_type = self
        ctype = self.base_type
        while ctype is not None and name in ctype:
            match_type = ctype
            ctype = ctype.base_type
        return (match_type, match_property)

    def resolve_sproperty_path(self, path, inheritance=True):
        """Resolves a property path

        path
            An array of strings representing the path.  There must be at
            least one segment.

        inheritance (default True)
            Whether or not to search inherited properties.  By default
            we do search them, the use cases for searching the set of
            properties defined by this entity type alone are limited to
            validation scenarios.  This restriction applies to the
            entity being searched, not to the types of complex
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
                elif isinstance(segment, names.QualifiedName):
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
            An array of strings and/or :class:`names.QualifiedName` named
            tuples.

        Returns a simple string representation with all components
        separated by "/"
        """
        return "/".join(
            [segment if is_text(segment) else
             (segment.namespace + "." + segment.name) for segment in path])


class Property(Annotatable, names.Named):

    """A Property declaration

    Properties are defined within a structured type.  The corresponding
    :class:`StructuredType` object therefore becomes the namespace
    in which the property is first declared and the qname attribute is
    composed of the type's qualified name and the property's name
    separated by a '/'.  The same property is also declared in any
    derived types as an alias."""

    csdl_name = "Property"

    def __init__(self, **kwargs):
        super(Property, self).__init__(**kwargs)
        #: the target structural type of this property
        self.structural_type = None
        #: whether or not this property points to a collection
        self.collection = None
        #: the type definition for values of this property
        self.type_def = None
        #: whether or not the property value can be null (or contain
        #: null in the case of a collection)
        self.nullable = True
        #: the default value of the property (primitive/enums only)
        self.default_value = None

    def get_model(self):
        if self.nametable is not None:
            return self.nametable().get_model()
        else:
            return None

    def set_type(self, structural_type, collection=False):
        self.structural_type = structural_type
        self.collection = collection
        if collection:
            self.type_def = structural_type.collection_type()
        else:
            self.type_def = structural_type

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_default(self, default_value):
        self.default_value = default_value

    def __call__(self, parent_ref):
        value = self.type_def()
        if self.default_value:
            value.assign(self.default_value)
            value.clean()
        elif isinstance(self.type_def, ComplexType) and not self.nullable:
            # a non-nullable complex value is set to be non-null
            # directly but there are no property values yet (the cache
            # is empty and will be created later)
            value.null = False
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


class NavigationProperty(names.Named):

    """A NavigationProperty declaration"""

    csdl_name = "NavigationProperty"

    def __init__(self, **kwargs):
        super(NavigationProperty, self).__init__(**kwargs)
        #: the target entity type of this property
        self.entity_type = None
        #: whether or not this property points to a collection
        self.collection = None
        #: The type definition to use for values of this navigation property.
        #: For collections, this is a :class:`CollectionType`.
        self.type_def = None
        #: The type definition to use for bound values of this
        #: navigation property.  For collections, this is an
        #: :class:`EntitySetType`.
        self.bound_def = None
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

    def get_model(self):
        if self.nametable is not None:
            return self.nametable().get_model()
        else:
            return None

    def set_type(self, entity_type, collection, contains_target=False):
        self.containment = contains_target
        self.entity_type = entity_type
        if collection:
            if self.nullable is not None:
                raise errors.ModelError(
                    errors.Requirement.nav_collection_exists_s % self.qname)
            # use a collection for unbound value creation, if values of
            # this property appear in contexts where they are bound to
            # an entity set then we will upgrade to an EntitySetValue at
            # that time.
            self.type_def = entity_type.collection_type()
            self.bound_def = entity_type.entity_set_type()
        else:
            if self.nullable is None:
                self.nullable = True
            if self.containment:
                self.type_def = entity_type
            else:
                self.type_def = entity_type.singleton_type()
            self.bound_def = self.type_def
        self.collection = collection

    def set_nullable(self, nullable):
        self.nullable = nullable

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
        if not isinstance(dependent_property.type_def,
                          PrimitiveType):
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

    def __call__(self, parent_ref, qualifier=None):
        if self.containment:
            # simpler case, we contain the entity (or collection)
            value = self.bound_def()
            if not self.nullable:
                value.null = False
        else:
            # harder case, are we bound?
            p = parent_ref()
            path = [self.name]
            if self.name not in p.base_def:
                path.insert(0, self.nametable().qname)
            entity = p.get_entity(path)
            if entity.entity_binding is not None:
                target_set = entity.entity_binding.resolve_binding(tuple(path))
                if target_set:
                    value = self.bound_def()
                    value.set_entity_binding(target_set)
                else:
                    value = self.type_def()
            else:
                value = self.type_def()
        value.set_parent(parent_ref, self.name)
        return value


class ComplexType(StructuredType):

    """A ComplexType declaration"""

    csdl_name = "ComplexType"

    def check_name(self, name):
        """Overridden to add a check against the declared name"""
        if self.name is not None and self.name == name:
            raise ValueError(errors.Requirement.ct_same_name_s % name)
        super(ComplexType, self).check_name(name)

    def __setitem__(self, key, value):
        if isinstance(value, names.Named) and value.is_owned_by(self):
            # we own this property, it must not share our name
            if self.name is not None and self.name == value.name:
                raise ValueError(errors.Requirement.ct_same_name_s % self.name)
        return super(ComplexType, self).__setitem__(key, value)


class EntityType(StructuredType):

    """An EntityType declaration"""

    csdl_name = "EntityType"

    def __init__(self, **kwargs):
        super(EntityType, self).__init__(**kwargs)
        #: This entity type's key.  This attribute is only set if the
        #: key is defined by this entity type itself, keys can also
        #: be inherited.
        self.key = []
        self._key = []
        #: A dictionary mapping the short name of each key property to a
        #: tuple of (path, Property) where path is an array of simple
        #: identifier strings and Property is the declaration of the
        #: property.
        self.key_dict = {}
        self._key_dict = {}
        #: whether or not instances of this EntityType are contained
        #: None indicates undetermined.
        self.contained = None
        self._singleton_type = None
        self._entity_set_type = None

    def check_name(self, name):
        """Overridden to add a check against the declared name"""
        if self.name is not None and self.name == name:
            raise ValueError(errors.Requirement.et_same_name_s % name)
        super(EntityType, self).check_name(name)

    def __setitem__(self, key, value):
        if isinstance(value, names.Named) and value.is_owned_by(self):
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

    def singleton_type(self):
        """Return *the* type instance representing Singleton(self)

        Returns a class representing a Singleton of this entity type.
        The new SingletonType instance is created the first time the
        method is called and cached thereafter."""
        if self._singleton_type is None:
            self._singleton_type = SingletonType(
                entity_type=self, value_type=self.value_type.singleton_class())
        return self._singleton_type

    def entity_set_type(self):
        """Return *the* type instance representing EntitySet(self)

        Returns a class representing an EntitySet of this entity type.
        The new EntitySetType instance is created the first time the
        method is called and cached thereafter."""
        if self._entity_set_type is None:
            self._entity_set_type = EntitySetType(
                entity_type=self,
                value_type=self.value_type.entity_set_class())
        return self._entity_set_type

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

    def get_key_dict(self, key=None):
        """Creates a key dictionary representing *key*

        key
            A simple value (e.g., a python int or tuple for a composite
            key) representing the key of an entity of this type.  If
            None (the default) then the dictionary contains null values
            of the correct types.

        Returns a dictionary of Value instances representing the key
        where the keys are the names of the key properties."""
        key_dict = {}
        if key is None:
            for name, path in self._key:
                key_dict[name] = self._key_dict[name][1].type_def()
        else:
            if not isinstance(key, tuple):
                key = (key, )
            if len(key) != len(self._key):
                raise errors.ODataError("invalid key for %s" % str(self))
            for key_info, key_value in zip(self._key, key):
                name, path = key_info
                value = self._key_dict[name][1].type_def()
                value.set_value(key_value)
                key_dict[name] = value
        return key_dict

    def get_key_from_dict(self, key_dict):
        """Extracts the key from a Python dictionary

        key_dict
            A dictionary containing a mapping of names to
            :class:`data.Value` instances that represents a key value
            for this entity type.

        Returns a python value (e.g., an integer, string or tuple) to
        use as the key.  This simpler form of the key is the immutable
        value used as the key to look up values in
        :class:`data.EntitySetValue` instances of this Entity type.

        This method reverses the transformation provided in
        :meth:`get_key_dict`."""
        if len(key_dict) != len(self._key):
            raise errors.ODataError("invalid key for %s" % str(self))
        key = []
        for name, path in self._key:
            key.append(key_dict[name].get_value())
        if len(key) == 1:
            return key[0]
        else:
            return tuple(key)

    def get_key_type_dict(self):
        """Creates a key dictionary of type definitions

        Returns a dictionary of key name/alias mapping to the
        PrimitiveType instances required to represent the key.

        Unlike :meth:`get_key_dict` the returned dict always uses the
        name (or alias) of the key property, it does not use the empty
        string when there is only one key property."""
        key_dict = {}
        for name, path in self._key:
            key_dict[name] = self._key_dict[name][1].type_def
        return key_dict

    def get_key_expression(self, key):
        """Creates a :class:`CommonExpression` representing key

        key
            A simple value (e.g., a python int or tuple for a composite
            key) representing the key of an entity of this type.

        Returns a common expression suitable for use as a filter, the
        expression will be of the form "property eq value" for single
        valued keys and "p1 eq v1 and p2 eq v2 and..." for composite
        keys."""
        if not isinstance(key, tuple):
            key = (key, )
        if len(key) != len(self._key):
            raise errors.ODataError("invalid key for %s" % str(self))
        expr = None
        for key_info, key_value in zip(self._key, key):
            name, path = key_info
            # start with the path...
            path_expr = None
            for p in path:
                if path_expr:
                    # turn Property into Property/SubProperty
                    new_expr = comex.MemberExpression()
                    new_expr.add_operand(path_expr)
                    new_expr.add_operand(comex.IdentifierExpression(p))
                    path_expr = new_expr
                else:
                    path_expr = comex.IdentifierExpression(p)
            # literal value is stored unboxed in the expression!
            test_expr = comex.EqExpression()
            test_expr.add_operand(path_expr)
            test_expr.add_operand(
                self.resolve_sproperty_path(path).type_def(
                    key_value).get_value_expression())
            if expr:
                # turn PropertyA eq 1 into PropertyA eq 1 and PropertyB eq 2
                new_expr = comex.AndExpression()
                new_expr.add_operand(expr)
                new_expr.add_operand(test_expr)
                expr = new_expr
            else:
                expr = test_expr
        return expr

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
            if isinstance(kp.type_def, PrimitiveType) and \
                    kp.type_def.value_type.key_type:
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
        # set inherited key properties so we don't have to recurse every
        # time we need to look up the key
        t = self
        while isinstance(t, EntityType):
            if t.key:
                self._key = t.key
                self._key_dict = t.key_dict
                break
            else:
                t = t.base

    def split_path(self, path, context=None, navigation=False):
        """Splits a path at navigation boundaries

        path
            A list or other iterable returning identifiers (as strings),
            :class:`QualifiedName` tuples or the special value "*".
            Alternatively, a string is also accepted for convenience and
            this will be split into path components.

        context
            The context in which to look up qualified names.  Required
            if the path contains type cast segments.

        navigation (False)
            Set to True to indicate that only navigation property paths
            should be returned in the last path tuple.

        Returns a sequence of path *lists*, each containing simple
        identifiers (as strings) or :class:`names.QualifiedName`
        instances. The sequence consists of optional paths to navigation
        properties that are traversed by the path, followed by the
        terminal property path that may be navigation or structural and
        may contain a trailing type-cast segment.

        The returned paths are canonicalised automatically (removing or
        reducing spurious type-casts)."""
        if is_text(path):
            path = names.path_from_str(path)
        result = []
        i = 0
        p = None
        while i < len(path):
            if p is None:
                # first time around
                ctype = ctype_cast = self
            elif isinstance(p, Property):
                # nothing is allowed after a primitive property and this
                # can't be complex (as the inner loop only terminates on
                # a complex property if it runs out of segments).
                raise errors.PathError(
                    "Bad select property: %s" % self.path_to_str(path))
            else:
                # type of preceding navigation property
                ctype = ctype_cast = p.entity_type
                p = None
            xpath = []
            while i < len(path):
                seg = path[i]
                if is_text(seg):
                    if seg == "*":
                        if ctype_cast is not ctype:
                            # e.g., "Self.Emmployee/*"
                            xpath.append(ctype_cast.get_qname())
                        xpath.append(seg)
                        i += 1
                        p = None
                        # this must be the last segment
                        if i < len(path):
                            raise errors.PathError(
                                "Bad wildcard in select property: %s" %
                                self.path_to_str(path))
                    else:
                        # plain identifier, should be a property of the
                        # current type
                        ptype, p = ctype_cast.canonical_get(seg, ctype)
                        if ptype is not ctype:
                            # automatically minimises the cast
                            xpath.append(ptype.get_qname())
                        xpath.append(seg)
                        i += 1
                        if isinstance(p, Property) and isinstance(
                                p.structural_type, ComplexType):
                            ctype = ctype_cast = p.structural_type
                            continue
                    break
                else:
                    # this is a type-cast segment, must have a context
                    if context is None:
                        raise errors.PathError(
                            "Type cast segment requires context")
                    new_type = context.qualified_get(seg)
                    if not new_type.is_derived_from(ctype_cast):
                        raise errors.PathError(
                            "Incompatible types for cast: %s" % to_text(seg))
                    ctype_cast = new_type
                    i += 1
            if not xpath:
                # the path consists only of type cast segments, must
                # be the trailing type-cast
                if result:
                    result[-1].append(ctype_cast.get_qname())
                    break
                else:
                    raise errors.PathError(
                        "Expected property path: %s" % self.path_to_str(path))
            if isinstance(p, Property):
                if navigation:
                    raise errors.PathError(
                        "Expected navigation or complex property: %s" % seg)
                if ctype_cast is not ctype:
                    # loop completed with a type cast of a complex property
                    xpath.append(ctype_cast.get_qname())
            result.append(xpath)
        return result


class LabeledExpression(Annotatable, names.Named):

    """A labeled expression in the model"""

    def __init__(self, **kwargs):
        super(LabeledExpression, self).__init__(**kwargs)
        self.expr = None

    def set_expression(self, expression):
        self.expression = expression


class SingletonType(NominalType):

    """The type of an object that contains a single entity

    This type is used as the type of singletons and navigation
    properties to single entities (when they do not contain their
    values)."""

    def __init__(self, entity_type, **kwargs):
        super(SingletonType, self).__init__(**kwargs)
        #: the type of the entity, we do not allow singletons of
        #: collection types
        self.item_type = entity_type

    def get_model(self):
        """Returns the model in which the item type was declared"""
        return self.item_type.get_model()


class EntitySetType(NominalType):

    """Collections of entities that can be accessed by key

    This type is used as the type of entity sets and navigation
    properties when they contain their values *or* dynamically when they
    are bound to a target entity set (which *should* be the case but is
    not guaranteed by the specification).

    The dfference between an EntitySetType and the weaker CollectionType
    is that they can only aggregate entities (of the same type) and
    those entities must all have unique keys allowing value of
    EntitSetType (instances of :class:`EntitySetValue` to behave like
    dictionaries).

    Instances take two additional (but optional) keyword arguments when
    called: type_cast and options.  See :meth:`EntitySet.open` for more
    information."""

    def __init__(self, entity_type, **kwargs):
        super(EntitySetType, self).__init__(**kwargs)
        #: the type being collected, we do not allow collections of
        #: collections
        self.item_type = entity_type

    def get_model(self):
        """Returns the model in which the item type was declared"""
        return self.item_type.get_model()


class CallableType(names.NameTable, NominalType):

    """An abstract class for Actions and Functions

    Actions and Functions are treated as named types within the model
    though, due to overloading, they are not declared directly in the
    enclosing schema but instead are grouped into
    :class:`CallableOverload` instances before being declared to enable
    disambiguation."""

    def __init__(self, **kwargs):
        super(CallableType, self).__init__(**kwargs)
        #: a weak reference to the Overload that contains us
        self.overload = None
        self.is_bound = False
        self.return_type = None
        self.nullable = True
        self.params = []
        self.entity_set_path = None

    def check_name(self, name):
        """Checks the validity of 'name' against simple identifier"""
        if name is None:
            raise ValueError("unnamed parameter")
        elif not self.is_simple_identifier(name):
            raise ValueError("%s is not a valid SimpleIdentifier" % name)

    def qualify_name(self, name):
        """Returns the qualified version of a (parameter) name

        By default we qualify name by prefixing with the name of this
        NameTable (type) and ":" rather than "/" to emphasize that
        parameters are not separately addressable within the model.  If
        this NameTable has not been declared then name is returned
        unchanged."""
        if self.name:
            return self.name + ":" + name
        else:
            return name

    def check_value(self, value):
        if not isinstance(value, Parameter):
            raise TypeError(
                "Parameter required, found %s" % repr(value))

    def set_is_bound(self, is_bound):
        self.is_bound = is_bound

    def binding(self):
        """Returns the type we are bound to"""
        if self.is_bound:
            return self.params[0].type_def
        else:
            return None

    def set_return_type(self, return_type):
        """Sets the return type for this callable

        If the return_type is a structured type (or collection thereof)
        it must be closed before it can be used as the return type of an
        action or function."""
        if isinstance(return_type, CollectionType):
            check_type = return_type.item_type
        else:
            check_type = return_type
        if isinstance(check_type, StructuredType) and \
                not check_type.closed:
            raise errors.ModelError("Type%s is still open" % check_type.qname)
        self.return_type = return_type

    def set_nullable(self, nullable):
        self.nullable = nullable

    def set_entity_set_path(self, path):
        self.entity_set_path = path

    def add_parameter(self, p, name):
        """Adds a parameter to this callable"""
        p.declare(self, name)
        self.params.append(p)

    #: the class used for Overload groups
    OverloadClass = None

    def declare_overload(self, schema, name):
        """Declares this callable in the given Schema

        Declarations of callables are special due to overloading rules,
        they do not appear in their parent's name table in the normal
        way but as part of an Overload object."""
        if name in schema:
            # add this declaration to the existing group
            fgroup = schema[name]
        else:
            fgroup = self.OverloadClass()
            fgroup.declare(schema, name)
        self.name = name
        self.qname = schema.qualify_name(name)
        self.overload = weakref.ref(fgroup)
        try:
            fgroup.overload(self)
        except:
            self.name = None
            self.qname = None
            self.overload = None
            raise

    def is_action(self):
        """Returns True if this CallableType is an action"""
        return isinstance(self, Action)


class CallableOverload(names.Named):

    def __init__(self, **kwargs):
        super(CallableOverload, self).__init__(**kwargs)
        self.callables = []

    def overload(self, callable):
        raise NotImplementedError

    def is_action(self):
        """Returns True if this CallableType is an action"""
        return isinstance(self, ActionOverload)


class ActionOverload(CallableOverload):

    def __init__(self, **kwargs):
        super(ActionOverload, self).__init__(**kwargs)
        self.bindings = {}

    def overload(self, action):
        if action.is_bound:
            # action name and binding parameter type
            key = to_text(action.binding())
        else:
            key = ""
        if key in self.bindings:
            raise errors.ModelError("Illegal overload: %s" % to_text(key))
        else:
            self.bindings[key] = action
            self.callables.append(action)

    def get_unbound_action(self):
        if self.name:
            return self.bindings.get("", None)
        else:
            return None

    def resolve(self, binding):
        """Resolves this action call

        binding
            The target type of the call for a bound call, None if the
            call is being made unbound.

        Returns the matching :class:`Action` declaration.

        The most specific binding is always returned so if an action is
        overloaded such that one declaration has a binding parameter of
        type Schema.Employee and another Schema.Person (where Person is
        the base type of Employee) then passing an Employee value for
        *binding* will always match the function with binding parameter
        of type Employee."""
        if binding:
            # create a set of strings to match the binding working
            # backwards through the base types.  E.g.,
            # ["Schema.Person", "Edm.EntityType"]
            blist = [to_text(b) for b in binding.declared_bases()]
        else:
            blist = [""]
        for bname in blist:
            a = self.bindings.get(bname, None)
            if a is not None:
                return a
        return None


class FunctionOverload(CallableOverload):

    def __init__(self, **kwargs):
        super(FunctionOverload, self).__init__(**kwargs)
        self.bound_type = None
        self.unbound_type = None
        self.name_bindings = {}
        self.type_bindings = {}

    def overload(self, function):
        if function.is_bound:
            if self.bound_type:
                if to_text(self.bound_type) != to_text(function.return_type):
                    raise errors.ModelError("Illegal overload")
            else:
                self.bound_type = function.return_type
            binding = to_text(function.binding())
            non_binding_params = function.params[1:]
        else:
            if self.unbound_type:
                if to_text(self.unbound_type) != to_text(function.return_type):
                    raise errors.ModelError("Illegal overload")
            else:
                self.unbound_type = function.return_type
            binding = ""
            non_binding_params = function.params
        name_key = tuple(
            [binding] + sorted([p.name for p in non_binding_params]))
        type_key = tuple(
            [binding] + [to_text(p.type_def) for p in non_binding_params])
        if name_key in self.name_bindings or type_key in self.type_bindings:
            raise errors.ModelError("Illegal overload")
        self.name_bindings[name_key] = function
        self.type_bindings[type_key] = function
        self.callables.append(function)

    def is_unbound(self):
        """Returns True if this Function can be called unbound"""
        return self.unbound_type is not None

    def resolve(self, binding, params):
        """Resolves this function call

        binding
            The target type of the call for a bound call, None if the
            call is being made unbound.

        params
            Optional list or iterable of parameter names representing
            non-binding parameters.  This list is only required if the
            function is overloaded *for the same binding* parameter.
            The order of the parameter names in the iterable is
            disregarded when resolving overloads.

        Returns the matching :class:`Function` declaration or None if
        no match is found.

        The most specific binding is always returned so if a function is
        overloaded such that one declaration has a binding parameter of
        type Schema.Employee and another Schema.Person (where Person is
        the base type of Employee) then passing an Employee value for
        *binding* will always match the function with binding parameter
        of type Employee even if the names of the non-binding parameters
        are otherwise the same.  This means that the params list may be
        omitted even when the binding parameter matches multiple
        overloads of the binding parameter via the type hierarchy."""
        if binding:
            # create a set of strings to match the binding working
            # backwards through the base types.  E.g.,
            # ["Schema.Person", "Edm.EntityType"]
            blist = [to_text(b) for b in binding.declared_bases()]
        else:
            blist = [""]
        if params is not None:
            pnames = sorted(params)
            for bname in blist:
                f = self.name_bindings.get(tuple([bname] + pnames), None)
                if f is not None:
                    return f
        else:
            best_depth = None
            fmatch = None
            for nb, f in self.name_bindings.items():
                binding = nb[0]
                try:
                    depth = blist.index(binding)
                    if best_depth is None or depth < best_depth:
                        best_depth = depth
                        fmatch = f
                    elif depth == best_depth:
                        # Two functions with the same binding (but
                        # different sets of named parameters) is
                        # ambiguous
                        raise errors.ODataError(
                            "Overloaded callable requires params list for "
                            "disambiguation: %s" % self.qname)
                except ValueError:
                    continue
            return fmatch
        return None


class Action(CallableType):

    csdl_name = "Action"

    OverloadClass = ActionOverload


class Function(CallableType):

    csdl_name = "Function"

    def __init__(self, **kwargs):
        super(Function, self).__init__(**kwargs)
        #: whether or not we are composable
        self.is_composable = False

    OverloadClass = FunctionOverload

    def set_is_composable(self, is_composable):
        self.is_composable = is_composable


class Parameter(Annotatable, names.Named):

    """A Parameter declaration

    Parameters are defined within callables (Action or Function).  The
    corresponding :class:`CallableType` therefore becomes the namespace
    in which the parameter is first declared and the qname attribute
    is composed of the callable's qualified name and the parameter's name
    separated by ':' (we avoid '/' just to emphasize that parameters are
    not individually addressable within the model)."""

    csdl_name = "Parameter"

    def __init__(self, **kwargs):
        super(Parameter, self).__init__(**kwargs)
        #: the base parameter type
        self.param_type = None
        #: whether or not this parameter requires a collection
        self.collection = None
        #: the type definition for parameter values
        self.type_def = None
        #: whether or not the parameter value can be null (or contain
        #: null in the case of a collection)
        self.nullable = True

    def set_type(self, param_type, collection=False):
        self.param_type = param_type
        self.collection = collection
        if collection:
            self.type_def = param_type.collection_type()
        else:
            self.type_def = param_type

    def set_nullable(self, nullable):
        if self.collection:
            raise errors.ModelError(
                "collection parameters may not specify nullable")
        self.nullable = nullable

    def __call__(self):
        value = self.type_def()
        if not self.collection and not self.nullable:
            if isinstance(self.param_type, StructuredType):
                value.set_defaults()
        return value
