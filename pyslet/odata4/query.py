#! /usr/bin/env python

from copy import copy

from ..py2 import (
    BoolMixin,
    long2,
    is_text,
    to_text,
    UnicodeMixin,
    )
from . import (
    comex,
    errors,
    names,
    )


class SelectItem(UnicodeMixin):

    """Object representing a single selected item

    path
        A tuple returned by :func:`names.path_from_str`, a string that
        can be passed to it or a string that contains a (namespace)
        wildcard.

    Some validation is done on the path, empty paths, term references
    and path qualifiers are not allowed."""

    def __init__(self, path):
        if not path:
            raise ValueError("Empty SelectItem rule")
        else:
            self.wildcard = None
            if is_text(path):
                if path and path[-2:] == ".*":
                    # wildcard domain
                    self.wildcard = path[:-2]
                    if not names.QNameTable.is_namespace(self.wildcard):
                        raise ValueError("Bad namespace: %s" % self.wildcard)
                    self.path = None
                    return
                else:
                    path = names.path_from_str(path)
            self.path = path
            # check the validity of the path
            cast = 0
            for seg in self.path:
                if cast >= 2:
                    # two casts in a row must end the path
                    raise ValueError(
                        "Bad path for select: %s" % names.path_to_str(path))
                if is_text(seg):
                    if seg == "*":
                        if len(self.path) != 1:
                            raise ValueError(
                                "Non-empty select paths must not use *: %s" %
                                names.path_to_str(path))
                        self.wildcard = "*"
                        self.path = None
                    elif seg.startswith("$"):
                        # other qualifiers are never allowed
                        raise ValueError(
                                "Select paths cannot be qualified: %s" %
                                names.path_to_str(path))
                    cast = 0
                elif isinstance(seg, names.QualifiedName):
                    # this must be an operation, last item
                    cast += 1
                else:
                    # we don't accept TermRef or more exotic segments
                    raise ValueError(
                        "Bad path for select: %s" % names.path_to_str(path))

    def __unicode__(self):
        if self.wildcard == "*":
            return self.wildcard
        elif self.wildcard:
            return self.wildcard + ".*"
        else:
            return names.path_to_str(self.path)

    def match_simple(self, qname, pname, nav=False):
        """Matches this select item rule for a simple property

        qname
            Optional QualifiedName of a type cast required to access
            the property being matched.

        pname
            The name of the property being matched.  Must be a simple
            identifier (for structural and navigation properties)
            or a QualifiedName for operations.

        nav (False)
            Boolean, set to True to indicate that pname is a navigation
            property.

        Returns a Boolean: True if this rule exactly matches a property
        with the above description and False otherwise.

        If this SelectItem rule is only a partial match with unmatched
        trailing path segments (or type casts) then a
        :class:`errors.PathError` is raised as the rule implies that the
        property is a complex property, not a simple one."""
        if self.wildcard:
            if self.wildcard == "*":
                # match a wildcard *includes* qualified properties but
                # excludes navigation properties and operations
                if is_text(pname) and not nav:
                    return True
                else:
                    return False
            else:
                if isinstance(pname, names.QualifiedName) and \
                        (self.wildcard == pname.namespace):
                    return True
                else:
                    return False
        else:
            if isinstance(pname, names.QualifiedName) and nav:
                raise ValueError(
                    "navigation property names must not be qualified %s" %
                    to_text(pname))
            ipath = iter(self.path)
            match = False
            try:
                seg = next(ipath)
                if qname:
                    # this will need to match
                    if not isinstance(seg, names.QualifiedName) or \
                            seg != qname:
                        return False
                    seg = next(ipath)
                if isinstance(pname, names.QualifiedName):
                    if not isinstance(seg, names.QualifiedName) or \
                            seg != pname:
                        return False
                elif not is_text(seg) or seg != pname:
                    return False
                match = True
                seg = next(ipath)
                # you must not have a cast after an operation
                if isinstance(seg, names.QualifiedName):
                    raise errors.PathError(
                        "type cast after operation select: %s/%s" %
                        (to_text(pname), to_text(seg)))
                else:
                    raise errors.PathError(
                        "complex match: %s/%s" %
                        (to_text(pname), to_text(seg)))
            except StopIteration:
                pass
            return match

    def match_complex(self, qname, pname):
        """Matches this select item rule for a complex property

        qname
            Optional QualifiedName of a type cast required to access
            the property being matched.

        pname
            The name of the complex property being matched.  Must be a
            simple identifier.

        Returns a tuple of (Boolean, SelectItem) with the first item
        being True if this rule matches a property (even partially) with
        the above description and False otherwise.  In the case of an
        exact match the second item is None.  In the case of a partial
        match a new SelectItem is returned reflecting the remainder of
        the rule.  For example, if the original rule is
        "Complex/Property" then a match with pname="Complex" will
        return::

            (True, SelectItem("Property")
        """
        if isinstance(pname, names.QualifiedName):
            raise ValueError(
                "copmlex property names must not be qualified %s" %
                to_text(pname))
        if self.wildcard:
            # match a wildcard, excludes qualified properties
            if qname is not None:
                return False, None
            if self.wildcard == "*":
                return True, None
            else:
                return False, None
        else:
            ipath = iter(self.path)
            match = False
            rule = None
            try:
                match_len = 0
                seg = next(ipath)
                if qname:
                    # this will need to match
                    if not isinstance(seg, names.QualifiedName) or \
                            seg != qname:
                        return False, None
                    seg = next(ipath)
                    match_len += 1
                if not is_text(seg) or seg != pname:
                    return False, None
                match = True
                seg = next(ipath)
                match_len += 1
                # so there are more path segments, construct a new
                # select rule
                rule = SelectItem(self.path[match_len:])
            except StopIteration:
                pass
            return match, rule


class ExpandItem(UnicodeMixin):

    """Object representing a single expanded item

    """

    @staticmethod
    def trim_path(path):
        """Static method that trims any qualifier and/or type cast"""
        pos = -1
        seg = path[pos]
        if is_text(seg) and seg.startswith('$'):
            pos -= 1
            seg = path[pos]
        if isinstance(seg, names.QualifiedName):
            pos -= 1
        if pos < -1:
            return path[:pos + 1]
        else:
            return path

    def __init__(self, path):
        if is_text(path):
            path = names.path_from_str(path)
        if not path:
            raise ValueError("$expand path must be non-empty")
        self.path = path
        done = False
        cast = False
        prop = False
        star = False
        for seg in self.path:
            if done:
                raise ValueError(
                    "unexpected segment in $expand path: %s" %
                    names.path_to_str(path))
            if is_text(seg):
                cast = False
                if seg.startswith('$'):
                    done = True
                    if seg not in ("$ref", "$count"):
                        raise ValueError(
                            "bad path qualifier in $expand: %s" %
                            names.path_to_str(path))
                elif seg == "*":
                    star = True
                    prop = True     # equivalent to a property name
                elif star:
                    # nothing after * except qualifiers perhaps
                    raise ValueError(
                        "bad $expand path: %s" % names.path_to_str(path))
                else:
                    prop = True
                cast = False
            elif isinstance(seg, names.QualifiedName):
                if star:
                    raise ValueError(
                        "bad $expand path: %s" % names.path_to_str(path))
                if cast:
                    raise ValueError("Double cast in $exand path: %s" %
                                     names.path_to_str(self.path))
                cast = True
            else:
                raise ValueError("Bad segment in $expand path: %s" %
                                 names.path_to_str(self.path))
        if not prop:
            raise ValueError("$expand requires navigation property or *: %s" %
                             names.path_to_str(self.path))
        self.options = ExpandOptions()

    def __unicode__(self):
        value = names.path_to_str(self.path)
        if self.options:
            options = to_text(self.options)
            if options:
                value += "(%s)" % options
        return value

    def trimmed_path(self):
        return self.trim_path(self.path)

    def clone(self):
        item = ExpandItem(self.path)
        item.options = self.options.clone()
        return item

    def match_navigation(self, qname, pname):
        """Matches this expand item rule for a navigation property

        qname
            A QualifiedName instance or None if the property is defined
            on the base type of the object these options apply to.

        pname
            A string.  The property name.

        The purpose of this method is to determine if a navigation
        property should be expanded by this rule.

        The result is a match string, an optional type cast that applies
        to the expansion and an optional PathQualifier; if no type cast
        and/or qualifier applies None is returned as appropriate.

        The match string is empty if there is no match, "*" if the match
        was with a wildcard and pname if the match was specific."""
        ipath = iter(self.path)
        match = ""
        type_cast = None
        qualifier = None
        try:
            seg = next(ipath)
            if qname:
                if isinstance(seg, names.QualifiedName):
                    # this will need to match
                    if seg != qname:
                        return match, None, None
                    seg = next(ipath)
                elif seg != "*":
                    return match, None, None
            if not is_text(seg):
                return match, None, None
            if seg != "*" and seg != pname:
                return match, None, None
            match = seg
            seg = next(ipath)
            if isinstance(seg, names.QualifiedName):
                # this is a type cast
                type_cast = seg
                seg = next(ipath)
            # this had better be a qualifier
            if not is_text(seg) or not seg.startswith('$'):
                raise errors.PathError(
                    "Incomplete match of expand rule: %s" % to_text(self))
            qualifier = names.PathQualifier.from_str(seg)
        except StopIteration:
            pass
        return match, type_cast, qualifier

    def match_complex(self, qname, pname):
        """Matches this expand item rule for a complex property

        The purpose of this method is to determine if a complex property
        needs to be selected (implicitly) as a result of an expand rule.
        For example, the expand rule "$expand=Address/Country" would
        implicitly select the complex property Address (though only the
        Country navigation property within it would actually be selected).

        qname
            A QualifiedName instance or None if the property is defined
            on the base type of the object these options apply to.

        pname
            The name of the complex property being matched.  Must be a
            simple identifier.

        If this rule partially matches a property with the above
        description then a new ExpandItem instance is returned,
        otherwise None is returned.  Exact matches are not allowed,
        including matches that differ only in a trailing cast.

        The returned ExpandItem reflects the remainder of the rule.  For
        example, if the original rule is "Complex/NavProperty/$count"
        then a match with pname="Complex" will return::

            ExpandItem("Property/$count")

        An expand path of "*" is treated as a special case: this matches
        all complex properties on the basis that they might contain a
        navigation property.  The returned ExpandItem is a copy of this
        rule! For example, if the original rule is "*/$ref", and
        pname="Complex" then the method returns:

            ExpandItem("*/$ref")

        This is because * matches all navigation properties in the
        entity, including those contained by a complex property or
        properties."""
        ipath = iter(self.path)
        match = False
        match_len = 0
        try:
            seg = next(ipath)
            if qname:
                if isinstance(seg, names.QualifiedName):
                    # this will need to match
                    if seg != qname:
                        return None
                    seg = next(ipath)
                    match_len += 1
                elif seg != "*":
                    return None
            if not is_text(seg):
                return None
            if seg == "*":
                # the expand rule for this complex type is exactly
                # the same!
                return self.clone()
            elif seg == pname:
                match = True
                # but there must be more than just a cast or qualifier
                # left on this path: if there is return a new ExpandItem
                # for the remainder of the expansion rule!
                while True:
                    seg = next(ipath)
                    if is_text(seg) and not seg.startswith('$'):
                        break
                match_len += 1
                new_rule = ExpandItem(self.path[match_len:])
                new_rule.options = self.options
                return new_rule
            else:
                return None
        except StopIteration:
            if match:
                # exact match of complex property is an error
                raise errors.PathError(
                    "Expand rule matches complex property: %s" %
                    to_text(self))


class EntityOptions(BoolMixin, UnicodeMixin):

    """Object representing the options select and expand

    This object is used to hold options that are applied to any
    composite value, including ComplexValues.  The specification does
    not directly support the use of $select and $expand when requesting
    complex property values even though the same effect can be achieved
    when the complex value is a property of an entity::

        Entity?$select=Complex/Property     # allowed
        Entity/Complex?$select=Property     # not allowed

    Despite this restriction we do calculate and propagate options from
    entity to complex value in the manner of the second for internal
    reasons.  The select and expand methods, used to set these options
    on value instances, are restricted to use on entities.

    There are two list attributes.  The select attribute contains a list
    of :class:`SelectItem` instances that describe the selected
    properties. An empty list indicates no selection rules and, for
    entities, is interpreted in the same way as a single item list
    containing the select item "*".

    The expand attribute contains a similar list of :class:`ExpandItem`
    instances that describe the more complex expansion rules.

    Instances evaluate to True in boolean expressions if any options
    have non-default values.  In other words, they evaluate to True if
    there is at least one select or expand rule in effect.

    Instances can be converted to strings, this results in a
    representation that corresponds to the way options appear within the
    expandOption rule in the syntax.  The applicable options are
    returned as a *semicolon* separated list.  This constrasts with
    their appearance in the query string of an OData URL where each
    option is individually rendered as a query parameter (using & as a
    separator and URI encoding to prevent ambiguities)."""

    def __init__(self):
        # a boolean indicating whether or not structural properties are
        # selected by default (in the absence of an explicit select
        # rule).
        self._select_default = True
        #: a list of path tuples describing selected properties
        self.select = []
        self._selected = {}
        self._complex_selected = {}
        self._nav_expanded = {}
        #: a list of :class:`ExpandItem` instances contain expansion rules
        self.expand = []

    def clone(self):
        """Creates a new instance forked from this one

        The implementation tries to avoid unnecessary copying of
        instances partly for performance reasons.  This enables one set
        of options to be shared amongst multiple values.  For example,
        you set the options once on an EntitySet and the same instance
        is used for all entity values returned by querying that set.
        (An approach that enables caching to speed up the process of
        populating entity value dictionaries with the correct set of
        selected and expanded properties.)

        The clone method is only used when the options must be forked
        from the original options in force.  For example, you may
        retrieve an entity from an entity set using one set of options
        but then decide to alter the projection or to expand (or
        contract!) certain navigation properties before reloading that
        value in isolation."""
        options = self.__class__()
        options.select = copy(self.select)
        for item in self.expand:
            options.expand.append(item.clone())
        return options

    def __bool__(self):
        if self.select or self.expand:
            return True
        else:
            return False

    def _format_items(self, result):
        if self.select:
            result.append(
                "$select=" + ",".join(to_text(s) for s in self.select))
        if self.expand:
            result.append(
                "$expand=" + ",".join(to_text(x) for x in self.expand))

    def __unicode__(self):
        result = []
        self._format_items(result)
        return ";".join(result)

    def to_str_list(self):
        """Generates a list of strings, one per option

        Each string is of the form $option=value.  The list may be empty
        if no options are set."""
        result = []
        self._format_items(result)
        return result

    def _clear_cache(self):
        self._selected.clear()
        self._complex_selected.clear()
        self._nav_expanded.clear()

    def add_select_path(self, path):
        """Add an additional select path to the options

        path
            A value that can be used to create a :class:`SelectItem`.

        This method uses *path* to create a new :class;`SelectItem`
        instance which is added to the select rules.

        If there is already a select rule for this path no action is
        taken."""
        self._clear_cache()
        item = SelectItem(path)
        self.add_select_item(item)

    def add_select_item(self, item):
        """Add an additional select item to the options

        item
            A :class:`SelectItem` instance such as would be returned
            from the parser when parsing the $select query option.

        Duplicate select rules are ignored."""
        if isinstance(item, SelectItem):
            for rule in self.select:
                if rule.path == item.path:
                    return
            self._clear_cache()
            self.select.append(item)
        else:
            raise TypeError

    def remove_select_path(self, path):
        """Removes a select item from these options

        path
            See :meth:`add_select_path` for details.

        If there is no matching select item no action is taken. The path
        must exactly match the path used to add the select rule,
        including any type cast::

            options = EntityOptions()
            options.add_select_path("ComplexProperty/Schema.SubType")
            options.remove_select_path("ComplexProperty")   # no match

        """
        if is_text(path):
            path = names.path_from_str(path)
        i = 0
        while i < len(self.select):
            if self.select[i].path == path:
                del self.select[i]
            else:
                i += 1

    def clear_select(self):
        """Removes all select items from the options"""
        self.select = []
        self._clear_cache()

    def selected(self, qname, pname):
        """Returns True if this property is selected

        qname
            A string or QualifiedName instance identifying the name of
            the type on which this property is declared if it is not the
            base type.  Pass None when the property *is* defined on the
            base type.

        pname
            A string representing the the property name or a
            QualifiedName instance representing an operation.

        Tests the select rules for an *exact* match against a specified
        simple structural property or operation.

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property are efficient."""
        if not self.select:
            # no select means select default structural properties
            return self._select_default
        if is_text(qname):
            qname = names.QualifiedName.from_str(qname)
        result = self._selected.get((qname, pname), None)
        if result is not None:
            return result
        result = False
        for rule in self.select:
            # do we match this select rule?  We can ignore type
            # casts as they don't apply to primitive properties
            result = rule.match_simple(qname, pname, nav=False)
            if result:
                break
        self._selected[(qname, pname)] = result
        return result

    def add_expand_path(self, path, options=None):
        """Add an additional expand item to these options

        path
            A value that can be used to create a :class:`ExpandItem`.

        options
            An :class:`ExpandOptions` instance controlling the options
            to apply to the expanded navigation property.  Defaults to
            None in which case a default set of options apply (including
            the default select rule that selects a default, typically
            all, structural properties).

        If there is already an expand rule for this path it is replaced.
        Returns the new :class:`ExpandItem`."""
        xitem = ExpandItem(path)
        if options is not None:
            # override the default set of (empty) options
            xitem.options = options
        self.add_expand_item(xitem)
        return xitem

    def add_expand_item(self, item):
        """Add an additional expand item to the options

        item
            A :class:`ExpandItem` instance such as would be returned
            from the parser when parsing the $expand query option.

        This item replaces any existing rule for the same path.
        Qualifiers and trailing type casts are ignored when matching so
        a rule $expand=NavProperty/Schema.TypeX, $expand=NavProperty and
        $expand=NavProperty/$count are all mutually exclusive and will
        replace each other if passed to this method."""
        if isinstance(item, ExpandItem):
            trimmed_path = ExpandItem.trim_path(item.path)
            self._clear_cache()
            i = 0
            while i < len(self.expand):
                if self.expand[i].trimmed_path() == trimmed_path:
                    del self.expand[i]
                else:
                    i += 1
            self.expand.append(item)
        else:
            raise TypeError

    def remove_expand_path(self, path):
        """Removes an expand item from these options

        path
            See :meth:`add_expand_path` for details.

        If there is no matching expand item no action is taken."""
        if is_text(path):
            path = names.path_from_str(path)
        trimmed_path = ExpandItem.trim_path(path)
        i = 0
        while i < len(self.expand):
            if self.expand[i].trimmed_path() == trimmed_path:
                del self.expand[i]
            else:
                i += 1

    def get_expand_item(self, path):
        """Returns the current ExpandItem for a navigation path

        path
            See :meth:`add_expand_path` for details but must end in the
            name of a navigation property and not contain any trailing
            type cast or qualifier.

        If there is no match, None is returned."""
        if is_text(path):
            path = names.path_from_str(path)
        for xitem in self.expand:
            if xitem.trimmed_path() == path:
                return xitem
        return None

    def clear_expand(self):
        """Removes all expand items from the options"""
        self._clear_cache()
        self.expand = []

    def complex_selected(self, qname, pname):
        """Returns an ExpandOptions instance

        Tests the select *and* expand rules for a match against a
        qualified name (as a *string* or None) and a property name.  The
        result is a set of expand options with the given property name
        factored out.  For example, if there is a rule "A/PrimitiveB"
        and we pass pname="A" we'll get back a set of options containing
        the select rule "$select=PrimitiveB".

        If there is no match then None is returned.

        Navigation properties make the situation more complex but the
        basic idea is the same.  If there is a rule
        "A/NavX($expand=NavY)" then passing pname="A" will result in the
        *expand* rule "$expand=NavX($expand=NavY)".

        Paths that *contain* derived types are treated in the same way,
        we may know nothing of the relationship between types so will
        happily reduce "A/Schema.ComplexTypeB/B,A/Schema.ComplexTypeC/C"
        to "$select=Schema.ComplexTypeB/B,Schema.ComplexTypeC/C" even if, in
        fact, ComplexTypeB and ComplexTypeC are incompatible derived
        types of the type of property A and can never be selected
        simultaneously.

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property return the *same*
        :class:`ExpandOptions` instance."""
        if is_text(qname):
            qname = names.QualifiedName.from_str(qname)
        result = self._complex_selected.get((qname, pname), None)
        if result is not None:
            return result
        options = ExpandOptions()
        # no rule means no selection in complex types
        options._select_default = False
        if self.select:
            selected = False
            for rule in self.select:
                match, rule = rule.match_complex(qname, pname)
                if match:
                    selected = True
                    if isinstance(rule, SelectItem):
                        options.add_select_item(rule)
                    else:
                        # an exact match, add a wild card rule
                        options.add_select_path("*")
        else:
            selected = self._select_default
            if selected:
                options.add_select_path("*")
        # now add the expansion options, even if we aren't selected
        # by the select rules we may be implicitly selected by an
        # expand path
        for rule in self.expand:
            xitem = rule.match_complex(qname, pname)
            if xitem is not None:
                options.add_expand_item(xitem)
        if not selected and not options.expand:
            result = None
        else:
            result = options
        self._complex_selected[(qname, pname)] = result
        return result

    def nav_selected(self, qname, pname):
        """Returns True if this property is selected

        qname
            A string or QualifiedName instance identifying the name of
            the type on which this property is declared if it is not the
            base type.  Pass None when the property *is* defined on the
            base type.

        pname
            A string representing the property name.

        Tests the select rules for an *exact* match against a specified
        navigation property.

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property are efficient."""
        if not self.select:
            # no select means select default structural properties
            # so no navigation
            return False
        if is_text(qname):
            qname = names.QualifiedName.from_str(qname)
        result = self._selected.get((qname, pname), None)
        if result is not None:
            return result
        result = False
        for rule in self.select:
            # do we match this select rule?  We can ignore type
            # casts as they don't apply to primitive properties
            result = rule.match_simple(qname, pname, nav=True)
            if result:
                break
        self._selected[(qname, pname)] = result
        return result

    def expanded(self, qname, pname):
        """Determines if a navigation property is expanded

        qname
            A string, QualifiedName instance or None if the property is
            defined on the base type of the object these options apply
            to.

        pname
            A string.  The navigation property name.

        Tests the expand rules only for a match against a specified
        property.  The (best) matching :class:`ExpandItem` is returned
        or None if there is no match.

        The result is actually a triple of the ExpandItem, the optional
        type cast (as a QualifiedName or None) and the optional
        qualifier as an integer PathQualifier constant (or None).

        An internal cache is kept to speed up rule matching so repeated
        calls for the same property are efficient."""
        if not self.expand:
            return None, None, None
        if is_text(qname):
            qname = names.QualifiedName.from_str(qname)
        result = self._nav_expanded.get((qname, pname), None)
        if result is not None:
            return result
        result = None, None, None
        # now have we been expanded?
        for rule in self.expand:
            match, type_cast, qualifier = rule.match_navigation(qname, pname)
            if match:
                result = rule, type_cast, qualifier
                if match == pname:
                    # specific match, not a wildcard
                    break
        self._nav_expanded[(qname, pname)] = result
        return result


class OrderbyItem(UnicodeMixin):

    """Object representing a single orderby item

    """

    def __init__(self, expr, direction=1):
        if not isinstance(expr, comex.CommonExpression):
            raise TypeError
        if direction not in (1, -1):
            raise ValueError
        self.expr = expr
        #: 1 = asc, -1  desc
        self.direction = direction

    def __unicode__(self):
        f = comex.ExpressionFormatter()
        op, expr_str = f.evaluate(self.expr)
        if self.direction is -1:
            expr_str += " desc"
        return expr_str


class CollectionOptions(EntityOptions):

    """Object representing a set of query options for a collection"""

    def __init__(self):
        super(CollectionOptions, self).__init__()
        self.skip = None
        self.top = None
        self.count = None
        self.filter = None
        self.search = None
        self.orderby = ()

    def __bool__(self):
        if super(CollectionOptions, self).__bool__() or (
                self.skip is not None or
                self.top is not None or
                self.count or
                self.filter is not None or
                self.search is not None or
                self.orderby):
            return True
        else:
            return False

    def _format_items(self, result):
        if self.skip is not None:
            result.append("$skip=%i" % self.skip)
        if self.top is not None:
            result.append("$top=%i" % self.top)
        if self.count:
            result.append("$count=true")
        f = None
        if self.filter:
            f = comex.ExpressionFormatter()
            op, expr_str = f.evaluate(self.filter)
            result.append("$filter=%s" % expr_str)
        if self.search:
            sf = comex.SearchFormatter()
            op, expr_str = sf.evaluate(self.search)
            result.append("$search=%s" % expr_str)
        if self.orderby:
            items = [to_text(item) for item in self.orderby]
            result.append("$orderby=%s" % ",".join(items))
        super(CollectionOptions, self)._format_items(result)

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

    def set_skip(self, skip):
        if skip is not None:
            if not isinstance(skip, (int, long2)):
                raise TypeError
            if skip < 0:
                raise ValueError
        self.skip = skip

    def set_top(self, top):
        if top is not None:
            if not isinstance(top, (int, long2)):
                raise TypeError
            if top < 0:
                raise ValueError
        self.top = top

    def set_count(self, count):
        if count is None:
            self.count = None
        elif count:
            self.count = True
        else:
            self.count = False

    def set_filter(self, filter_expr):
        if filter_expr is not None:
            if not isinstance(filter_expr, comex.CommonExpression):
                raise TypeError
        self.filter = filter_expr

    def set_search(self, search_expr):
        if search_expr is not None:
            if not isinstance(search_expr, comex.CommonExpression):
                raise TypeError
        self.search = search_expr

    def set_orderby(self, orderby_items):
        """Sets the orderby expression

        orderby_items
            An iterable of :class:`OrderbyItem` instances."""
        if orderby_items is None:
            self.orderby = tuple()
        else:
            for expr in orderby_items:
                if not isinstance(expr, OrderbyItem):
                    raise TypeError
            self.orderby = tuple(orderby_items)


class ExpandOptions(CollectionOptions):

    """Object representing a set of query options for a collection"""

    def __init__(self):
        super(ExpandOptions, self).__init__()
        self.levels = None

    def __bool__(self):
        if super(ExpandOptions, self).__bool__() or (
                self.levels is not None):
            return True
        else:
            return False

    def _format_items(self, result):
        super(ExpandOptions, self)._format_items(result)
        if self.levels is not None:
            if self.levels < 0:
                result.append("$levels=max")
            else:
                result.append("$levels=%i" % self.levels)

    def clone(self):
        """Creates a new instance forked from this one"""
        options = super(ExpandOptions, self).clone()
        options.levels = self.levels
        return options

    def set_levels(self, levels):
        if levels is not None:
            if not isinstance(levels, (int, long2)):
                raise TypeError
            if levels < -1:
                levels = -1
        self.levels = levels

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
