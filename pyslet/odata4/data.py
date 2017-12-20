#! /usr/bin/env python

import collections
import contextlib
import weakref

from ..py2 import (
    BoolMixin,
    is_text,
    to_text,
    UnicodeMixin,
    )
from . import (
    errors,
    names,
    parser,
    types,
    )


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

    @classmethod
    def new_type(cls):
        """Creates a new :class:`types.NominalType` instance

        The Value class hierarchy has a corresponding Type class hierarchy that
        contains the declarations of the Values' types.  Each Value class has
        one (and only one) corresponding Type class used to represent it's
        declaration but the reverse is not true!

        While building models dynamically, including when parsing
        metadata files, we create new types using this factory method."""
        return types.NominalType(value_type=cls)

    @classmethod
    def collection_class(cls):
        """Returns the class to use for Collection values"""
        return CollectionValue

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
        if name and name not in p.base_def and name in p.type_def:
            # we weren't declared in the base type of the parent but we
            # are declared in the current type of the parent (i.e.,
            # we're not a dynamic property of an open type) so we need a
            # type cast to the type we were declared in (not necessarily
            # the type of our parent which may be further derived).
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
            #qualifier or an existing :class:`names.TermRef` instance.

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
            aname = names.TermRef.from_str(aname)
        value = self._annotations.get(aname, None)
        if value is None:
            # TODO: if value is a property value, look up annotations in
            # the property definition too perhaps?
            for t in self.type_def.declared_bases():
                # look up the annotation in the value's type
                a = t.annotations.get(aname, None)
                if a is None:
                    continue
                value = a.term().type_def()
                value.assign(self.Evaluator.evaluate_annotation(a, self))
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
        aname = names.TermRef(name=names.QualifiedName.from_str(term.qname),
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
            aname = names.TermRef.from_str(aname)
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

        Returns a dictionary mapping annotation :class:`names.TermRef` tuples
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


class CompositeValue(Value):

    """An abstract class for values that support query options

    The :attr:`options` attribute contains query options that are in
    force for this container.  The type of options that apply will
    depend on the type of the container.  The object is either None,
    indicating that default options should be assumed or an instance of
    one of the options classes (see concrete implementations for
    details)."""

    def __init__(self, **kwargs):
        super(CompositeValue, self).__init__(**kwargs)
        #: the (system query) options that are in force
        self.options = None
        self._options_inherited = True
        #: whether or not we are a collection
        self.is_collection = True

    #: the class to use for the options attribute
    OptionsType = types.CollectionOptions

    def _clone_options(self):
        if self.options:
            self.options = self.options.clone()
        else:
            self.options = self.OptionsType()
        self._options_inherited = False

    def _set_options(self, options, type_cast=None):
        # Internal method used to implement option inheritance, this
        # ensures that one options object is shared over all values that
        # use it, e.g., when expanding a navigation property lots of
        # entity values will contain the property and inherit any
        # options set on the original expansion.
        if self.options is not None:
            raise errors.ODataError("container options already set")
        # dump all our data, this is a significant change
        self.clear_cache()
        self.options = options
        self._options_inherited = True
        if type_cast is not None:
            self.type_cast(type_cast)

    def set_options(self, options_dict):
        """Sets the options for this container

        options_dict
            A dictionary mapping option name (e.g., "$filter") to a
            character string representing the option's value as per the
            syntax for options defined in the specification.

        All existing options are cleared and replaced with those
        parsed from the new dictionary."""
        raise NotImplementedError

    def get_applicable_type(self):
        """Returns the type that any options are applicable to

        For structured types this is the type itself, for containers
        this is the type of the items they contain."""
        raise NotImplementedError

    def type_cast(self, new_type):
        """Abstract method to implement type casting of a value

        new_type
            An instance of :class:`NominalType` that *must* be in the
            same type hierarchy as the existing applicable type and
            *must* be derived from the applicable base type (used to
            create the value).

        For values of structured types the applicable type is the type
        of the value itself, for containers (e.g., collections) the
        applicable type is the type of the contained items.

        This function is used to implement a dynamic type-cast such as
        when an entity set or collection valued property is cast to a
        type derived from the type stipulated by the original
        declaration.

        In theory, primitive types (including enumeration types) can be
        cast too because Collection(Edm.PrimitiveType) is well defined
        within the model *but* there are significant restrictions in the
        specification on when this construct can be used so, in
        practice, type casts almost always relate to complex or entity
        types (or containers thereof).

        You may not cast a frozen value."""
        raise NotImplementedError

    def select(self, path):
        """Selects a structural property

        path
            As per :meth:`types.EntityType.split_path`.

        Can only be applied when the applicable type is an *Entity*
        type. Although it may seem well-defined to use select for
        Complex values the specification does not allow the use of
        $select/$expand on queries that identify complex values.  You
        can still select properties within complex values but you must
        do it using the full path of the property within the entity.

        This method allows you to traverse complex types *and* navigation
        properties.  This may result in an expand option being set or
        modified rather than a simple select option being set.  For
        example::

            people.select("Friends/UserName")

        might translate into an *expand* option::

            $expand=Friends($select=UserName)

        Bear in mind that, by default, there are no select rules in
        place resulting in a default set of (typically all) structural
        properties being retrieved.  Setting explicit select rules is
        used to *restrict* the set of returned properties.

        The cache is automatically cleared."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, types.EntityType):
            raise errors.ODataError(
                "Can't resolve select path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            path,
            context=self.service.model if self.service is not None else None,
            navigation=False)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths[:-1]:
            # add a simple expand item for each parent path if it isn't
            # already expanded
            xitem = options.get_expand_item(path)
            if xitem is None:
                xitem = options.add_expand_path(path)
            options = xitem.options
        path = paths[-1]
        options.add_select_path(path)
        self.clear_cache()

    def select_default(self, xpath=None):
        """Sets the selection to the default seletion

        Can only be applied when the applicable type is an *Entity*
        type.  The default selection is indicated by the absence of a
        $select query option.

        xpath (None)
            An optional path (see :meth:`types.EntityType.split_path`) to a
            navigation property.

        With no xpath, this method effectively removes the $select
        option from future queries.  With an xpath, it removes the
        $select option from the $expand rule in effect for that path. If
        xpath is given but is not expanded no action is taken."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, types.EntityType):
            raise errors.ODataError(
                "select requires entity type, not %s" % repr(app_type))
        if xpath:
            options = self._resolve_xpath(xpath)
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.clear_select()
        self.clear_cache()

    def expand(self, path, qualifier=None):
        """Expands a navigation property

        path
            As per :meth:`types.EntityType.split_path`.

        qualifier
            An optional path qualifier, one of the values from
            :class:`names.PathQualifier`.  Only $count and
            $ref are allowed.  These options determine how much data is
            retrieved for the expanded navigation property.

        This method allows you to traverse complex types *and*
        navigation properties though the path must terminate in a
        navigation property.  This may result in nested expand options
        being set, for example::

            people.expand("Friends/Friends")

        might translate into::

            $expand=Friends($expand=Friends)

        The use of path qualifiers enables you to suppress the return
        of detailed information from the service while still creating
        the indicated object in the parent entity's property dictionary.
        For example::

            people.expand("Friends", PathQualifier.ref)

        Will cause the contained entities to have a "Friends" property
        defined in their property dictionary and you'll be able to
        iterate through the resulting values and use the len function
        without causing additional service requests (assuming the result
        is within any server paging limits) but the resulting entity
        objects are only references to the associated entities. If you
        drill down on one of the associated Friends, say by accessing a
        named structural property, this will trigger the request to
        retrieve the entity itself from the data service."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, types.EntityType):
            raise errors.ODataError(
                "Can't resolve expand path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            path,
            context=self.service.model if self.service is not None else None,
            navigation=True)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths[:-1]:
            # add a simple expand item for each parent path if it isn't
            # already expanded
            xitem = options.get_expand_item(path)
            if xitem is None:
                xitem = options.add_expand_path(path)
            options = xitem.options
        path = paths[-1]
        options.add_expand_path(path, qualifier=qualifier)
        self.clear_cache()

    def collapse(self, path):
        """Collapses a navigation property

        path
            As per :meth:`types.EntityType.split_path`."""
        app_type = self.get_applicable_type()
        if not isinstance(app_type, types.EntityType):
            raise errors.ODataError(
                "Can't resolve expand path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            path,
            context=self.service.model if self.service is not None else None,
            navigation=True)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths[:-1]:
            xitem = options.get_expand_item(path)
            if xitem is None:
                # we're done, we weren't even expanded
                return
            options = xitem.options
        path = paths[-1]
        options.remove_expand_path(path)
        self.clear_cache()

    def set_filter(self, filter_expr, xpath=None):
        """Sets the filter for this value (or a related value)

        filter_expr
            A :class:`types.CommonExpression` instance or a string
            from which one can be parsed.

        xpath (None)
            An optional path (see :meth:`types.EntityType.split_path`) to a
            navigation property.  Can only be used when the applicable
            type is an entity.

            The filter is applied to the entity set(s) expanded from
            this navigation property.  If this path has not been
            expanded then :meth:`expand` is used to add it
            automatically.

        With no xpath, can only be applied to a collection or entity
        set."""
        if is_text(filter_expr):
            p = parser.Parser(filter_expr)
            filter_expr = p.require_filter()
            p.require_end()
        self.clear_cache()
        if xpath:
            options = self._resolve_xpath(xpath)
        elif not self.is_collection:
            raise errors.ODataError("%s is not a collection" % repr(self))
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.set_filter(filter_expr)

    def set_search(self, search_expr, xpath=None):
        """Sets the search expression for the result set"""
        raise NotImplementedError

    def set_orderby(self, orderby_expr, xpath=None):
        """Sets the orderby expression for the result set

        orderby_expr
            A list or iterable of :class:`types.OrderByItem` instances
            or a string from which one can be parsed.

        xpath (None)
            As per :meth:`set_filter`.

        With no xpath, can only be applied to a collection or entity
        set.  With an xpath you can also apply a filter to a
        singleton."""
        if is_text(orderby_expr):
            p = parser.Parser(orderby_expr)
            orderby_expr = p.require_orderby()
            p.require_end()
        self.clear_cache()
        if xpath:
            options = self._resolve_xpath(xpath)
        elif not self.is_collection:
            raise errors.ODataError("%s is not a collection" % repr(self))
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.set_orderby(orderby_expr)

    def set_page(self, top, skip=0, xpath=None):
        """Sets the page for the result set

        top
            An integer to limit the size of the collection or None for
            unlimited.

        skip
            An integer used to exclude items from the contained
            collection or 0 (the default) if no items should be
            excluded.

        xpath (None)
            As per :meth:`set_filter`.

        With no xpath, can only be applied to a collection or entity
        set."""
        self.clear_cache()
        if xpath:
            options = self._resolve_xpath(xpath)
        elif not self.is_collection:
            raise errors.ODataError("%s is not a collection" % repr(self))
        else:
            if self._options_inherited:
                self._clone_options()
            options = self.options
        options.set_top(top)
        if skip == 0:
            skip = None
        options.set_skip(skip)

    def get_page_size(self):
        """Returns the maximum size of a collection

        Returns the value of top previously set by set_page, None
        indicates that there is not limit on the size of the
        collection."""
        if self.options:
            return self.options.top
        else:
            return None

    def _resolve_xpath(self, xpath):
        # returns the options for this xpath expanding as required
        app_type = self.get_applicable_type()
        if not isinstance(app_type, types.EntityType):
            raise errors.ODataError(
                "Can't resolve expand path in non-entity %s" %
                repr(app_type))
        paths = app_type.split_path(
            xpath, context=self.service.model if self.service is not None
            else None, navigation=True)
        if self._options_inherited:
            self._clone_options()
        options = self.options
        for path in paths:
            xitem = options.get_expand_item(path)
            if xitem is None:
                xitem = options.add_expand_path(path)
            options = xitem.options
        return options


class ContainerValue(CompositeValue):

    """Abstract value type for containers

    Containers are either collections (of primitive, complex or entity
    types) or Singletons which behave in some ways like collections of
    (up to) one entity.

    The type_def attribute points to the type of the *container*, not to
    the type of the item, a separate attribute :attr:`item_type` is used
    to point to the type definition of the contained objects."""

    def __init__(self, **kwargs):
        super(ContainerValue, self).__init__(**kwargs)
        #: the type contained by this value
        self.item_type = self.type_def.item_type

    @contextlib.contextmanager
    def loading(self, next_link=None):
        """Used during deserialization"""
        raise NotImplementedError

    def load_item(self, obj):
        """Used during deserialization"""
        raise NotImplementedError

    def get_applicable_type(self):
        """Returns the current item type"""
        return self.item_type

    def type_cast(self, new_type):
        """Constrains value to contain only objects of the given type

        See: :meth:`CompositeValue.type_cast`.

        For containers the applicable type is the item type they
        contain. The original item type is referred to as the base type
        and is always available as::

            self.type_def.item_type

        The :attr:`item_type` attribute refers to the current item type
        taking into consideration any type cast in effect.

        You can think of these container-level type-casts as if they
        were a special kind of filter on the container (hence they are
        managed in tandem with other query options).  It is important to
        be aware that with a type cast in effect you are only seeing a
        partial view of the original container's contents."""
        if self.frozen:
            raise errors.FrozenValueError
        if new_type is self.item_type:
            # nothing to do
            return
        if not new_type.is_derived_from(self.type_def.item_type):
            raise TypeError("Incompatible types: %s -> %s" %
                            (self.type_def.item_type.qname, new_type.qname))
        self.item_type = new_type
        self.clear_cache()

    def new_item(self):
        """Creates a new value suitable for this container

        This method creates a new transient value, it does not add it to
        the container.  To add the resulting value to the container use
        the appropriate container-specific action.

        You should always use this method to create a new item as it
        ensures that any options applied to the container (particularly
        select and expand options) are correctly applied to the new
        value too before it is added to the container.

        The new value will be of the type indicated by the attribute
        :attr:`item_type` so it includes any type cast that is in
        effect. Furthermore, the value is created directly to be of
        that type (it is not itself type cast) making it the base type
        for the new value.

        This is a subtle distinction but it means that the new value
        cannot be cast back to the base type of this container because a
        value of the derived type is required (by the container's type
        cast). In OData URL syntax you can see the difference in the
        position of the key predicate when the container is an entity
        set::

            service/People/Schema.Employee('kristakemp')

        illustrates the form of URL when the entity set People is type
        cast to show Employees only and the entity with key 'kristakemp'
        is looked up in the sub-set of entities of that type.

        On the other hand, the following URL shows a look up in the
        default entity set (of all People) but returning the specific
        entity with key 'kristakemp' only if it is of type Empolyee::

            service/People('kristakemp')/Schema.Employee

        (At the time of writing the Trippin service from where these
        examples were taken, doesn't handle this in the expected way and
        returns 204 No Content rather than 404 Not Found.)

        Anyway, in the latter case the type cast is applied to the
        entity and not to the entity set.  For a specific entity the
        effect is the same, the difference is whether or not the
        restriction is applied to the container value itself.

        In the rare case of a container of abstract primitive types,
        i.e., Collection(Edm.PrimitiveType), you will get back a
        :class:`primitive.PrimitiveValue` object that does not, itself,
        support further type casting (and is always null).  To put a
        concrete value into the container you will either have to cast
        the container (assuming there is a concrete class that can
        represent all items) and use this method or simply create the
        value directly from the appropriate primitive type yourself."""
        item = self.item_type()
        # now implement the entity options, select and expand
        if isinstance(item, (ComplexValue, EntityValue)):
            item._set_options(self.options)
        return item


class CollectionValue(collections.MutableSequence, ContainerValue):

    """Represents the value of a Collection

    The type_def is required on construction.  There is no default
    collection type.

    The CollectionValue object is blessed with Python's Sequence
    behaviour."""

    def __init__(self, **kwargs):
        super(CollectionValue, self).__init__(**kwargs)
        self._fullycached = True
        self._cache = []
        self._next_link = None

    def set_value(self, value):
        """Sets the value from a python 'native' value representation"""
        if value is None:
            raise TypeError("Collection values cannot be null")
        elif isinstance(value, (list, collections.Sequence)):
            with self.loading() as seq:
                for new_value in value:
                    v = seq.new_item()
                    v.set_value(new_value)
                    seq.load_item(v)
            self.touch()
        else:
            raise TypeError

    def assign(self, value):
        """Assigns the value of a collection

        value
            Must be another collection, collections cannot be null, they
            can only be empty.  The values in the collection MUST be
            compatible with the *current type* of this collection.

        The collection is first cleared and then updated with a copy of
        the items in *value*.

        To given an example of the type restrictions, if you have a
        complex type 'Address' with a derived type 'UKAddress' and you
        create a collection of 'Address' then you may assign a
        collection that contains either 'Address' or 'UKAddress' (or a
        mixture) to it but if you were to type-cast the original
        collection to Collection(UKAddress) you would only be able to
        assign a *value* containing UKAddress values."""
        if not isinstance(value, CollectionValue):
            raise TypeError(
                "Can't assign %s from %s" %
                (to_text(self.type_def), to_text(value.type_def)))
        # we actually ignore the type of the incoming collection itself
        # and just check that each item is assignable.
        del self[:]
        for item in value:
            new_value = self.new_item()
            new_value.assign(item)
            self.append(new_value)

    @contextlib.contextmanager
    def loading(self, next_link=None):
        self._next_link = next_link
        if self.service is None:
            # an unbound collection is simpler
            self._fullycached = True
            self._cache = []
            yield self
        else:
            # called via a _load method that has cleared cache
            yield self
            self._fullycached = next_link is None
            max_size = self.get_page_size()
            if max_size is not None:
                # we ignore next_link if we asked to limit the page
                self._fullycached = self._fullycached or \
                    len(self._cache) >= max_size
                if self._fullycached:
                    self._next_link = None
        self.clean()

    def load_item(self, obj):
        if isinstance(obj, EntityValue) and self.name:
            # inserting an entity into a collection, the entity must
            # have an id of it's own OR have an explicit null id to
            # indicate that it is transient.  If we are missing those
            # and this collection is a navigation property value (a
            # named child) then we will fake the entity id by assuming
            # that it can be referenced by key from this collection.
            # This is consistent with the TripPin service which, at the
            # time of writing, throws a 500 error if you try and force
            # it to tell you the id of a Trip entity using metadata=full!
            try:
                self.service.get_entity_id(obj)
            except errors.InvalidEntityID:
                self.service.fix_entity_id(obj, self)
        self._cache.append(obj)

    def clear_cache(self):
        """Clears the local cache for this collection

        If this collection is bound to a service then any locally cached
        information about the entities is cleared."""
        if self.service is not None:
            self._fullycached = False
            del self._cache[:]

    def reload(self):
        """Reload the contents of this collection from the service

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
            self._load()
        if isinstance(index, slice):
            # value must be an iterable of appropriate values
            self._cache[index] = [self._check_item(item) for item in value]
        else:
            self._cache[index] = self._check_type(value)
        self.touch()

    def __delitem__(self, index):
        if self.frozen:
            raise errors.FrozenValueError
        if isinstance(index, slice):
            if index.stop is None and index.step is None:
                # special case: delete everything past start.  We
                # optimise here as we don't need to load the remote data
                # just to mark it as being deleted, we have everything
                # cached that needs to be cached!
                if index.start is None or self._is_cached(index.start):
                    self._fullycached = True
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load()
        del self._cache[index]
        self.touch()

    def insert(self, index, value):
        if self.frozen:
            raise errors.FrozenValueError
        if not self._fullycached:
            # must be fully cached to be writeable
            self._load()
        self._cache.insert(index, value)
        self.touch()

    def set_key_filter(self, key):
        """Filter this collection by an entity key

        The collection *must* be a colleciton of entities.  The key is
        turned into a filter expression, replacing any existing
        filter."""
        if not isinstance(self.item_type, types.EntityType):
            raise errors.ODataError("set_key_filter requires EntityType")
        self.set_filter(self.item_type.get_key_expression(key))

    def _load(self, index=None):
        # Load the cache up to and including index,  If index is None
        # then load the entire collection.  We always start from the
        # beginning because the remote data may have changed.
        self._fullycached = False
        del self._cache[:]
        request = self.service.get_collection(self)
        while request is not None:
            self._next_link = None
            # loading called during execution to populate _cache
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            if self._next_link:
                request = self.service.get_collection(
                    self, self._next_link)
                self._next_link = None
            else:
                request = None


class StructuredValue(collections.MutableMapping, CompositeValue):

    """Abstract class that represents the value of a structured type

    Instances behave like dictionaries of property values keyed on
    property name.  On construction the value is *empty* (len returns 0)
    and evaluates to null.  The value automatically becomes non-null if
    you set a property value, directly using assignment::

        value['StringProperty'] = primitive.StringValue("Hello")

    or if you explicitly request the creation of property defaults::

        value.set_defaults()

    You can set a value back to null using::

        value.set_value(None).

    The range of properties that you can get and set is determined by
    the select/expand options that are in effect for the value.  These
    are typically set on creation and will vary depending on the
    context. For example, the :meth:`EntityContainerValue.new_item`
    method will create a new entity (a structured type) using the
    select/expand rules that are in effect for that container.

    If you create a transient value of a structured type directly by
    calling a type instance then all structural properties are selected.

    Recall that Value instances are either bound (to a service) or are
    transient.  Some operations are not permitted on bound values, for
    more details see the appropriate methods and the notes in the
    derived classes :class:`EntityValue` and :class:`ComplexValue`.

    In keeping with the other composite Value classes, structured values
    maintain an internal cache of the property values so you only
    generate one call to the underlying service to populate them. You
    may explicitly clear the cache to force a call to the service.

    The type definition used to create a structured value instance is
    considered special and is remembered as the :attr:`base_def` of the
    value throughout the value's life.  The actual type may change to a
    value derived from it but it may never be changed to a type that is
    more abstract.

    The following types may appear as values of properties:

    :class:`PrimitiveValue`
        For single valued primitive properties

    :class:`EnumerationValue`
        For single valued enumeration properties

    :class:`ComplexValue`
        For single valued complex propeties

    :class:`CollectionValue` (of any of the above)
        For collection valued structural properties.

    :class:`EntityValue`
        For single valued navigation properties that *contain* their
        target entity.

    :class:`SingletonValue`
        For single valued navigation properties that do *not contain*
        their target entity.

    :class:`EntitySetValue`
        For collection-valued navigation properties whether or not they
        contain the target entities.

    :class:`CollectionValue` (of :class:`EntityValue`)
        The rare case in which a collection valued navigation property
        is neither contained nor successfully bound to an entity set.
        Such properties are discouraged but not disallowed by the
        specification. The simpler collection results because there is
        no guarantee that all entities in the collection come from the
        same entity set and hence no guarantee that the keys are unique."""

    def __init__(self, **kwargs):
        super(StructuredValue, self).__init__(**kwargs)
        #: the (initial) base type definition
        self.base_def = self.type_def
        self.null = True
        self._cache = None
        self._loading = False

    def get_applicable_type(self):
        """Returns the *current* type definition"""
        return self.type_def

    def type_cast(self, new_type):
        """Casts this value to a new type

        You may not cast a *bound* structured value.  This restriction
        is imposed by the specification, to change the type of a complex
        value you must replace the value completely rather than modify
        in place. To change the type of an existing entity you would
        need to remove it and reinsert a new value of the desired type;
        this operation is not possible if keys are assigned
        automatically by the data service.

        The property dictionary is updated to reflect the change in type
        taking in to consideration any options applied to this value.
        The values of existing properties are not modified but bear in
        mind that, in the unusual case of a cast to a more general type,
        properties not defined in the new type are *removed* from the
        property dictionary.

        You can always obtain the (original) base type of the value from
        the attribute :attr:`base_type`."""
        if self.frozen:
            raise errors.FrozenValueError
        if self.service is not None and not self._loading:
            raise errors.BoundValue("type_cast on bound value")
        if new_type is self.type_def:
            # nothing to do
            return
        if not new_type.is_derived_from(self.base_def):
            raise TypeError("Incompatible types: %s -> %s" %
                            (self.base_type.qname, new_type.qname))
        self.type_def = new_type
        # a transient value, modify the values in place
        self._init_cache(clear=False)

    def clear_cache(self):
        """Clears the local cache of property values."""
        if self.service is not None:
            self._cache = None
        else:
            # otherwise, update the properties to reflect any changes in
            # the select/expand rules
            self._init_cache(clear=False)

    def _init_cache(self, clear=True):
        # a null value should have no properties: nothing to do!
        if self.null:
            return
        if self._cache is None or clear:
            self._cache = {}
        self_ref = weakref.ref(self)
        for ptype in self.type_def.values():
            if isinstance(ptype, types.Property):
                if isinstance(ptype.structural_type, types.ComplexType):
                    # a complex (or complex collection) property
                    self._init_complex(ptype, self_ref)
                else:
                    # simple case, a primitive property
                    self._init_primitive(ptype, self_ref)
            else:
                self._init_navigation(ptype, self_ref)

    def _init_primitive(self, ptype, self_ref):
        selected = True
        pname = ptype.name
        if self.options:
            if pname not in self.base_def:
                # this is a property of a derived type so the select path
                # MUST be qualified with the name of this type
                qname = ptype.nametable().qname
            else:
                qname = None
            selected = self.options.selected(qname, pname)
        if selected:
            if pname not in self:
                self._cache[pname] = ptype(self_ref)
        else:
            if pname in self:
                del self._cache[pname]

    def _init_complex(self, ptype, self_ref):
        pname = ptype.name
        if self.options:
            if pname not in self.base_def:
                qname = ptype.nametable().qname
            else:
                qname = None
            options, qname = self.options.complex_selected(qname, pname)
            if options:
                if pname not in self:
                    self._cache[pname] = p = ptype(self_ref)
                    p._set_options(options)
                    if qname:
                        type_def = self.options.resolve_type(qname)
                        p.type_cast(type_def)
            elif pname in self:
                del self._cache[pname]
        elif pname not in self:
            # default selected if there are no options
            self._cache[pname] = ptype(self_ref)

    def _init_navigation(self, ptype, self_ref):
        pname = ptype.name
        if self.options:
            if pname not in self.base_def:
                qname = ptype.nametable().qname
            else:
                qname = None
            selected = self.options.selected(qname, pname, nav=True)
            xitem = self.options.nav_expanded(qname, pname)
            if xitem is not None:
                if pname not in self:
                    self._cache[pname] = p = ptype(self_ref, xitem.qualifier)
                    if xitem.type_cast:
                        type_cast = p.type_cast(
                            self.options.resolve_type(xitem.type_cast))
                    else:
                        type_cast = None
                    p._set_options(xitem.options, type_cast=type_cast)
            elif selected:
                # just selected for link, same as no qualifier
                # service request will be deferred
                if pname not in self:
                    self._cache[pname] = p = ptype(self_ref)
            elif pname in self:
                del self._cache[pname]
        elif pname in self:
            # default is not selected if there are no options
            del self._cache[pname]

    def bind_to_service(self, service):
        """Binds this value to a specific OData service

        Binds all properties recursively."""
        if self.service is not None:
            raise errors.BoundValue(to_text(self))
        self.service = service
        if self._cache is not None:
            for pvalue in self._cache.values():
                pvalue.bind_to_service(service)

    def _load_cache(self):
        # load the cache
        self._init_cache()
        if self.service is not None:
            # load the entity from the service
            self.reload()

    @contextlib.contextmanager
    def loading(self):
        self.null = False
        if self._cache is None:
            # creating the cache (with defaults) prevents the mapping
            # methods from attempting a reload
            self._init_cache()
        try:
            self._loading = True
            yield self
        finally:
            self._loading = False
        # just deserialized so mark as clean
        self.clean()

    def __len__(self):
        if self.null:
            return 0
        if self._cache is None:
            self._load_cache()
        return len(self._cache)

    def __getitem__(self, key):
        if self.null:
            raise KeyError
        if self._cache is None:
            self._load_cache()
        return self._cache[key]

    def __setitem__(self, key, value):
        # supported for open types
        if not self.type_def.open_type:
            raise errors.ModelError(
                "Can't set properties on a closed structured type (%s)" % key)
        if self.frozen:
            raise errors.FrozenValueError
        # the value of a dynamic property must not be the value of two
        # structural properties simultaneously
        if value.parent is not None or value.service is not None:
            raise errors.BoundValue
        # the key must be valid and unused
        names.simple_identifier_from_str(key)
        if key in self.type_def or (self._cache and key in self._cache):
            raise errors.DuplicateNameError
        if self.null:
            # implicitly makes us non-null
            self.set_defaults()
        value.set_parent(weakref.ref(self), key)
        self._cache[key] = value

    def __delitem__(self, key):
        raise NotImplementedError

    def __iter__(self):
        if self.null:
            return
        if self._cache is None:
            self._load_cache()
        for k in self._cache:
            yield k

    def is_null(self):
        """Returns True if this object is null."""
        return self.null

    def set_defaults(self):
        """Sets default values for all properties

        For a null value his method automatically triggers the creation
        of the selected/expanded property values in the property
        dictionary with their default values set.  The structured value
        as a whole is marked as being dirty but the individual values
        are not.  This is an important distinction as when creating a
        new entity defaults are *not* sent to the service.  If a service
        lies about the default that will be used for a property then the
        property value may be different from the default immediately
        after creation.  If you want to force the published default to
        be used for any reason you should mark the individual property
        as being dirty too by calling :meth:`Value.touch` on it
        prior to creation.  If you want to force all published defaults
        to be used then you can call this method twice as on the second
        invocation the value will be non-null and the following rules
        will apply...

        For a non-null value all properties with defined defaults are
        set to their default values (and marked as dirty), including
        recursively through complex children.  Values without defaults
        defined are left unmodified."""
        if self.frozen:
            raise errors.FrozenValueError
        elif self.null:
            self.null = False
            self._init_cache()
            self.touch()
        else:
            for ptype in self.type_def.values():
                if isinstance(ptype, types.Property):
                    if isinstance(ptype.structural_type, types.ComplexType):
                        # a complex (or complex collection) property
                        if not ptype.collection:
                            self[ptype.name].set_defaults()
                    else:
                        # simple case, a primitive property
                        if ptype.default_value is not None:
                            self[ptype.name].set_value(
                                ptype.default_value.get_value())

    def select_value(self, value):
        """Sets the value from a python 'native' value representation

        This is wrapper for :meth:`set_value` that imposes the
        additional constraint that all structural properties with keys
        in *value* are selected and any structural properties with keys
        that are missing from *value* are unselected.  The upshot is
        that the structured value becomes a 'tight fit' around the
        incoming value with no default values.  This method is also
        strict about extraneous data, any data in *value* that cannot be
        accommodated in the structured value will raise ValueError.  In
        cases where there is a collection of complex values then all
        dict/mapping items in the corresponding list must contain an
        identical set of keys.

        One use case for using this method (instead of set_value) would
        be if there are computed defaults in your data service.  That
        is, structural properties that are marked as non-nullable in the
        model but which can be omitted on insert without generating an
        error.  Such values can be safely omitted from the value
        dictionary in order to invoke the server-side computed defaults.
        An obvious example is auto-generated key fields."""
        if value is None:
            self.null = True
            self.clear_cache()
            self.touch()
        elif isinstance(value, (dict, collections.Mapping)):
            selected = self._subselect(self.type_def, value)
            if self._options_inherited:
                self._clone_options()
            self.options.clear_select()
            for path in selected:
                self.options.add_select_path(path)
            self.set_value(value)
        else:
            raise ValueError

    def _subselect(self, ctype, value):
        if value is None:
            # a complex type set to null, no need to sub-select
            return []
        elif not value:
            # a complex type set to {} perhaps, we can't select no
            # properties so this is an error
            raise ValueError("no properties to select for %s" % ctype.qname)
        elif isinstance(value, (dict, collections.Mapping)):
            selected = []
            unselected = 0
            vkeys = set(value.keys())
            for pname, ptype in ctype.items():
                vkeys.discard(pname)
                if not isinstance(ptype, types.Property):
                    continue
                if pname not in value:
                    unselected += 1
                    continue
                if isinstance(ptype.structural_type, types.ComplexType):
                    if ptype.collection:
                        # never null, but need to intersect selects
                        subselect = self._subselect_intersect(
                            ptype.structural_type, value[pname])
                    else:
                        subselect = self._subselect(
                            ptype.structural_type, value[pname])
                    if subselect:
                        unselected += 1
                        for s in subselect:
                            s.insert(0, pname)
                        selected += subselect
                        continue
                # we're just selected
                selected.append([pname])
            if vkeys:
                raise ValueError(
                    "unused fields in value: %s" % ", ".join(list(vkeys)))
            if unselected:
                # if there is anything unselected then we return the
                # select rules
                if not selected:
                    raise ValueError(
                        "no properties to select for %s" % ctype.qname)
                return selected
            else:
                # everything is selected, we can return an empty list
                # meaning default (all properties)
                return []
        else:
            raise ValueError

    def _subselect_intersect(self, ctype, value):
        if value is None:
            # collections can never be null
            raise ValueError("collections cannot be null")
        elif not value:
            # an empty list perhaps, no need to sub-select
            return []
        elif isinstance(value, (list, tuple, collections.Sequence)):
            subselect = sorted(self._subselect(ctype, value[0]))
            for v in value[1:]:
                # All items in the list must be the same!
                vselect = sorted(self._subselect(ctype, v))
                if vselect != subselect:
                    raise ValueError(
                        "set_value: incompatible selections in collection")
            return subselect
        else:
            raise ValueError("list or sequenced required")

    def set_value(self, value):
        """Sets the value from a python 'native' value representation

        None sets a null value.

        A dict or dict-like object will update all (selected)
        *structural* properties of this value from the corresponding
        values in the dictionary.  If a property has no corresponding
        entry in *value* then it is set to its default (or null).

        We deal with one special case here, if the incoming dictionary
        contains another :class:`Value` instance then
        :meth:`Value.get_value` is used to extract its value
        before passing it to the corresponding set_value method of this
        object's property.  The upshot is that you may pass another
        entity or complex value to set_value but that, unlike
        :meth:`assign`, no type checking it performed and the operation
        succeeds provided that the underlying value types are
        compatible."""
        if self.frozen:
            raise errors.FrozenValueError
        if value is None:
            self.null = True
            self.clear_cache()
            self.touch()
        elif isinstance(value, (dict, collections.Mapping)):
            self.null = False
            self._init_cache(clear=False)
            for pname, pvalue in self.items():
                ptype = self.type_def[pname]
                if isinstance(ptype, types.Property):
                    new_value = value.get(pname, None)
                    if new_value is None:
                        if isinstance(pvalue, CollectionValue):
                            del pvalue[:]
                        elif isinstance(
                                ptype.structural_type, types.ComplexType):
                            if ptype.nullable:
                                pvalue.set_value(None)
                            else:
                                pvalue.set_defaults()
                        else:
                            if ptype.default_value is not None:
                                pvalue.set_value(
                                    ptype.default_value.get_value())
                            else:
                                pvalue.set_value(None)
                    else:
                        if isinstance(new_value, Value):
                            new_value = new_value.get_value()
                        pvalue.set_value(new_value)
        else:
            raise TypeError

    def assign(self, value):
        """Sets this value from another Value instance.

        If value is null then this instance is set to null.  Otherwise
        the incoming value must be of the same type as, or a type
        derived from, the object being assigned.  The values of all
        properties present in the dictionary are assigned from the
        values with the same name in the other value instance.  Missing
        values are set to null.

        The assign operation does not change the type of a value.  You
        can do that using :meth:`set_type`."""
        if self.frozen:
            raise errors.FrozenValueError
        if value.is_null():
            self.set_value(None)
        elif value.type_def.is_derived_from(self.type_def):
            if self.null:
                self.set_defaults()
            for pname, pvalue in self.items():
                new_value = value.get(pname, None)
                if new_value is None:
                    pvalue.set(None)
                else:
                    pvalue.assign(new_value)
            self.touch()
        elif isinstance(value, StructuredValue):
            # identically named properties are cast recursively. The
            # cast fails if one of the property-value casts fails or the
            # target type contains nonnullable properties that have not
            # been assigned a value
            self.null = False
            self._init_cache(clear=True)
            for pname, pvalue in self.items():
                ptype = self.type_def[pname]
                if isinstance(ptype, types.Property):
                    new_value = value.get(pname, None)
                    if new_value is None:
                        if isinstance(pvalue, CollectionValue):
                            del pvalue[:]
                        elif not ptype.nullable:
                            # non-nullable property, fail returns null
                            self.set_value(None)
                            return
                        elif ptype.default_value is not None:
                            # nullable but with a default, set it
                            pvalue.assign(ptype.default_value)
                    else:
                        pvalue.assign(new_value)
        else:
            return super(StructuredValue, self).assign(value)

    def commit(self):
        """Pushes changes to this entity"""
        if self.service is not None:
            # we're bound, push to the service
            if isinstance(self, EntityValue):
                request = self.service.update_entity(self)
            else:
                request = self.service.update_property(self)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
        else:
            self.rclean()

    def rclean(self):
        for pvalue in self.values():
            if isinstance(pvalue, StructuredValue):
                pvalue.rclean()
            else:
                pvalue.clean()
        self.clean()


class ComplexValue(StructuredValue):

    """Represents the value of a Complex type

    Instances behave like dictionaries of property values."""

    def __init__(self, type_def=None, **kwargs):
        if type_def is not None and \
                not isinstance(type_def, types.ComplexType):
            raise errors.ModelError(
                "ComplexValue requires ComplexType: %s" % repr(type_def))
        super(ComplexValue, self).__init__(
            type_def=edm_complex_type if type_def is None else type_def,
            **kwargs)

    def touch(self):
        """Implements touch behaviour

        If this complex value is the value of a commplex or entity
        property then touch the parent too."""
        super(ComplexValue, self).touch()
        if self.parent:
            self.parent().touch()

    def reload(self):
        """Reloads this value from the service

        The value must be bound."""
        if self.service is None or self.parent is None:
            raise errors.UnboundValue
        request = self.service.get_property(self)
        request.execute_request()
        if isinstance(request.result, Exception):
            raise request.result


class EntityValue(StructuredValue):

    """Represents the value of an Entity type, i.e., an Entity.

    There is no special representation of an entity reference.  Entity
    references are just bound entity values with an empty cache.  Any
    operation on the property values (including use of len) will cause
    the cache to be loaded by retrieving the entity from the data
    service.  For references, the entity is identified by its id which
    is stored in the odata.id annotation when the entity is bound to the
    service."""

    @classmethod
    def singleton_class(cls):
        """Returns the class to use for Singleton values"""
        return SingletonValue

    @classmethod
    def entity_set_class(cls):
        """Returns the class to use for EntitySet values"""
        return EntitySetValue

    def __init__(self, type_def=None, **kwargs):
        if type_def is not None and not isinstance(type_def, types.EntityType):
            raise errors.ModelError(
                "EntityValue requires EntityType: %s" % repr(type_def))
        super(EntityValue, self).__init__(
            type_def=edm_complex_type if type_def is None else type_def,
            **kwargs)
        self.entity_binding = None

    def set_entity_binding(self, entity_binding):
        if self.service is not None:
            raise errors.BoundValue(
                "set_entity_binding(%s)" % repr(entity_binding))
        self.entity_binding = entity_binding

    def get_entity(self, path, ignore_containment=True):
        """Returns self

        See: :meth:`types.StructuredType.get_entity` for more
        information."""
        if self.parent is None or not ignore_containment:
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
        while isinstance(t, types.EntityType):
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

    def reload(self):
        """Reloads this value from the service

        The value must be bound."""
        if self.service is None:
            raise errors.UnboundValue
        request = self.service.get_entity(self)
        request.execute_request()
        if isinstance(request.result, Exception):
            raise request.result

    def get_ref(self):
        """Return a reference to this entity

        The entity value must be bound to a service as references only
        have meaning in the context of a service."""
        if self.service is None:
            raise errors.UnboundValue
        return self.service.get_entity_ref(self)

    def delete(self):
        """Deletes this entity

        This is an alternative to deleting the entity using the del
        operator on the parent entity set.  This form *must* be used if
        deletion is protected by optimistic concurrency control.

        On success the value of the entity is set to null, effectively
        removing the key.  Future operations on the entity will fail.
        Warning: the entity may still exist in the cache of the entity
        set or collection used to retrieve it and those caches are *not*
        automatically invalidated."""
        if self.service is None:
            raise errors.UnboundValue
        request = self.service.delete_entity(self)
        request.execute_request()
        if isinstance(request.result, Exception):
            raise request.result
        self.set_value(None)


class EntityContainerValue(ContainerValue):

    """Abstract class for a value that contains an entity or entities

    This class is used as the base class for representing *any* object
    that contains one or more entities.  This is a base class for
    :class:`EntitySetValue` and :class:`SingletonValue` that are used
    to represent the values of declared EntitySets and Singletons but it
    also includes the values of navigation properties that refer to a
    subset of entities from a declared EntitySet (including single
    valued navigation properties that are treated as Singletons)."""

    def __init__(self, **kwargs):
        super(EntityContainerValue, self).__init__(**kwargs)
        if not isinstance(self.item_type, types.EntityType):
            raise errors.ODataError(
                "EntityType required: %s" % self.item_type.qname)
        #: the optional entity set or singleton we're bound to
        self.entity_binding = None

    OptionsType = types.EntityOptions

    def set_entity_binding(self, entity_binding):
        """Binds this value to an entity set or singleton

        When creating an EntitySetValue providing a view on an EntitySet
        exposed by a service the value is *bound*, not just to the
        service, but to the entity set itself (similarly for
        SingletonValue and singletons).  This further constrains the
        entities that the value can contain to be both of the entity
        type (as per :attr:`item_type`) *and* to come from a specific
        entity_set. (It is possible for a model to define multiple
        distinct entity sets that contain entities of the same type.)
        The same is true for navigation properties that are bound to
        entity sets using navigation bindings.

        You don't normally need to call this method yourself, values are
        automatically bound to the appropriate entity context when they
        are added to the container immediately prior to binding them to
        the service itself (see :meth:`bind_to_service`).

        Once set, you can't change the entity context that a value is
        bound to. Also, you can't bind a value to an entity context
        after it has been bound to a service."""
        if self.service is not None:
            raise errors.BoundValue(
                "set_entity_binding(%s)" % repr(entity_binding))
        self.entity_binding = entity_binding

    def new_item(self):
        """Creates an entity suitable for this entity container

        If this value is bound to an entity set then the entity value
        returned is also bound to that entity set, in addition to
        inheriting any select/expand options that may be set on the
        parent."""
        entity = self.item_type()
        # now implement the entity options, select and expand
        if self.entity_binding is not None:
            entity.set_entity_binding(self.entity_binding)
        entity._set_options(self.options)
        return entity


class EntitySetValue(collections.MutableMapping, EntityContainerValue):

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

    def __init__(self, **kwargs):
        super(EntitySetValue, self).__init__(**kwargs)
        self._fullycached = True
        self._keys = []
        self._cache = {}
        self._key_lock = 1
        self._next_link = None

    def _clone_options(self):
        if self.options:
            self.options = self.options.clone()
        else:
            self.options = types.CollectionOptions()
        self._options_inherited = False

    def bind_to_service(self, service):
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
        super(EntitySetValue, self).bind_to_service(service)

    def clear_cache(self):
        if self.service is not None:
            self._fullycached = False
            self._cache.clear()
            del self._keys[:]
            self._key_lock += 1

    def get_annotation(self, aname):
        """Looks up an annotation by name

        We augment the base implementation to add a look-up the
        annotation in the associated EntitySet definition (if we are
        bound)."""
        if is_text(aname):
            aname = names.TermRef.from_str(aname)
        value = super(EntitySetValue, self).get_annotation(aname)
        if value is None and self.entity_binding is not None:
            # look up the annotation in the value's type
            a = self.entity_binding.annotations.get(aname, None)
            if a is not None:
                value = a.term().type_def()
                value.assign(self.Evaluator.evaluate_annotation(a, self))
                # freeze this value before returning it
                value.freeze()
        return value

    @contextlib.contextmanager
    def loading(self, next_link=None):
        self._next_link = next_link
        if self.service is None:
            # an unbound entity set is simpler
            self._fullycached = True
            self._cache.clear()
            del self._keys[:]
            self._key_lock += 1
            yield self
        else:
            yield self
            self._fullycached = next_link is None
            max_size = self.get_page_size()
            if max_size is not None:
                # we ignore next_link if we asked to limit the page
                self._fullycached = self._fullycached or \
                    len(self._cache) == max_size
        self.clean()

    def load_item(self, e):
        """Only used during deserialization"""
        k = e.get_key()
        self._keys.append(k)
        self._cache[k] = e

    def __len__(self):
        if self._fullycached:
            return len(self._keys)
        else:
            request = self.service.get_item_count(self)
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
                request = self.service.get_entity_by_key(self, key)
                request.execute_request()
                if isinstance(request.result, errors.ServiceError):
                    if request.result.http_code == 404:
                        raise KeyError
                if isinstance(request.result, Exception):
                    raise request.result
                e = request.result
                k = e.get_key()
                # we don't know where in the sequence this key belongs
                # self._keys.append(k)
                self._cache[k] = e
                return e
        return result

    def __setitem__(self, key, value):
        # entity_set[key] = entity
        raise NotImplementedError

    def __delitem__(self, key):
        # del entity_set[key]
        if self._fullycached and self.service is not None:
            if key in self._cache:
                del self._cache[key]
                self._keys.remove(key)
            else:
                raise KeyError
        else:
            # this is enough to discard our cache completely
            self.clear_cache()
            request = self.service.delete_entity_by_key(self, key)
            request.execute_request()
            if isinstance(request.result, errors.ServiceError):
                if request.result.http_code == 404:
                    raise KeyError
            if isinstance(request.result, Exception):
                raise request.result

    def __iter__(self):
        self._key_lock += 1
        key_lock = self._key_lock
        if self._fullycached:
            for k in self._keys:
                yield k
                if key_lock != self._key_lock:
                    raise errors.ODataError("Stale iterator detected")
        else:
            self._keys = []
            self._cache.clear()
            request = self.service.get_entity_collection(self)
            i = 0
            while request is not None:
                self._next_link = None
                request.execute_request()
                if isinstance(request.result, Exception):
                    raise request.result
                if self._next_link:
                    request = self.service.get_entity_collection(
                        self, self._next_link)
                    self._next_link = None
                else:
                    request = None
                while i < len(self._keys):
                    yield self._keys[i]
                    if key_lock != self._key_lock:
                        raise errors.ODataError("Stale iterator detected")
                    i += 1

    def insert(self, entity, omit_clean=False):
        # entity must be of the correct type
        if not entity.type_def.is_derived_from(self.item_type):
            raise TypeError
        if self.service is None:
            k = entity.get_key()
            if k in self._cache:
                raise KeyError
            self._key_lock += 1
            self._keys.append(k)
            self._cache[k] = entity
        else:
            # TODO: check we're not being filtered
            request = self.service.create_entity(
                self, entity, omit_clean=omit_clean)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            # critical, update the key as it may have been computed
            k = entity.get_key()
            self._cache[k] = entity
            self._key_lock += 1


class SingletonValue(EntityContainerValue):
    """Represents the value of a Singleton

    Whereas an :class:`EntitySetValue` follows Python's mutable mapping
    protocol a Singleton contains at most one entity, it is therefore
    callable instead.  I.e., calling a SingletonValue returns the entity
    it contains.  If the Singleton is nullable and does not contain an
    entity then an *unbound* null EntityValue is returned as if
    :meth:`new_item` had been called.  See :meth:`change` for how
    to change the entity a Singleton points to. Singletons exposed by
    the container itself are *never* nullable and the entity they
    contain cannot be changed directly (though it may change as a
    consequence of some other action)."""

    def __init__(self, **kwargs):
        super(SingletonValue, self).__init__(**kwargs)
        self.is_collection = False
        self._cache = None
        self._cached = True

    def bind_to_service(self, service):
        """Binds this singleton to a data service

        The singleton must be empty to be bound.

        Once bound, the SingletonValue automatically creates and
        executes requests to the underlying data service and caches the
        resulting information for speed."""
        if self._cache:
            raise errors.ServiceError(
                "SingletonValue must be empty to be bound")
        self._cache = None
        self._cached = False
        super(SingletonValue, self).bind_to_service(service)

    def clear_cache(self):
        if self.service is not None:
            self._cache = None
            self._cached = False

    def __call__(self):
        if self._cached:
            if self._cache is None:
                return self.new_item()
            else:
                return self._cache
        else:
            # cache fault, load from source
            request = self.service.get_singleton(self)
            request.execute_request()
            if isinstance(request.result, Exception):
                raise request.result
            # may return None
            e = request.result
            self._cache = e
            self._cached = True
            if e is None:
                return self.new_item()
            else:
                return e

    def change(self, new_entity):
        """Changes the entity in this Singleton

        SingletonValues are used to represent the value of Singleton (a
        child of the EntityContainer) and as the value of a
        single-valued navigation property when that navigation property
        does *not* contain the related entity.

        You can't change the value of a true Singleton, it's value is
        frozen on creation, but you can update the entity reference in a
        single-valued navigation property using this method.  For the
        purposes of this method it can be assumed that this
        SingletonValue will always have a parent entity value.

        If the parent is bound to a service (i.e., it already exists as
        an entity exposed by the service) the service is not updated
        until the parent entity's :meth:`EntityValue.commit` method is
        called.

        Bear in mind that if the new entity is not bound to a service
        then it will be created when the parent entity is committed (or
        inserted).  This operation may require more than one service
        request as you cannot insert a new entity into a single valued
        navigation property on an existing entity, instead the new
        entity is created and then the relationship is updated to point
        to it.

        The creation of new_entity will fail if both ends of the
        relationship are exposed and it is non-nullable on new_entity's
        type.  To workaround the problem you need to work from the
        required side of the relationship, expanding the navigation
        property in new_entity and updating that value with a reference
        to this value's parent entity.  You may then create the new
        entity by inserting it into an appropriate entity set."""
        if self.frozen:
            raise errors.FrozenValueError
        self._cache = new_entity
        self._cached = True
        self.touch()


edm_complex_type = types.ComplexType(value_type=ComplexValue)
edm_complex_type.set_abstract(True)
edm_complex_type.close()

edm_entity_type = types.EntityType(value_type=EntityValue)
edm_entity_type.set_abstract(True)
edm_entity_type.close()
