#! /usr/bin/env python

import collections
import weakref

from ..py2 import (
    force_text,
    is_text,
    to_text,
    UnicodeMixin,
    )
from ..xml import xsdatatypes as xsi

from . import errors


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


class TypeName(
        UnicodeMixin,
        collections.namedtuple('TypeName', ['qname', 'collection'])):

    """Represents a Type name

    This is a Python namedtuple consisting of a :class:`QualifiedName`
    instance and a boolean *collection* indicating if the type is a
    collection.  No syntax checking is done on the values at creation.
    When converting to str (and unicode for Python 2) the components are
    joined as per the CSDL, e.g.::

        str(TypeName(QualifiedName('Schema', 'Product'), True)) ==
            'Collection(Schema.Product)'
    """

    __slots__ = ()

    def __unicode__(self):
        qname, collection = self
        if collection:
            return force_text("Collection(%s)" % to_text(qname))
        else:
            return to_text(qname)

    @classmethod
    def from_str(cls, src):
        """Parses a TypeName from a source string"

        Raises ValueError if src is not a valid TypeName."""
        try:
            if src.startswith("Collection("):
                if not src.endswith(")"):
                    raise ValueError
                return cls(qname=QualifiedName.from_str(src[11:-1]),
                           collection=True)
            else:
                return cls(qname=QualifiedName.from_str(src),
                           collection=False)
        except ValueError:
            raise ValueError("Bad type name: %s" % src)


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


class PathQualifier(xsi.Enumeration):

    """An enumeration used to represent a path qualifier

    ::

            PathQualifier.count
            PathQualifier.DEFAULT == None

    For more methods see :py:class:`~pyslet.xml.xsdatatypes.Enumeration`"""

    decode = {
        "$count": 1,
        "$ref": 2,
        "$value": 3,
    }

    aliases = {
        "count": "$count",
        "ref": "$ref",
        "value": "$value",
    }


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
    QualifiedName or TermRef segments followed by a single, optional,
    :class:`PathQualifier` as either a $-prefixed *string* or the
    special symbol "*"."""
    if not src:
        return tuple()
    segments = []
    path_end = False
    star = False
    for segment in src.split('/'):
        if path_end or (star and not segment.startswith('$')):
            # there can be nothing after a path qualifier and only a
            # path qualifier may follow *
            raise ValueError(
                "Unexpected path segment after qualifier or *: %s" % src)
        elif segment.startswith('@'):
            segment = TermRef.from_str(segment)
        elif segment.startswith('$'):
            # will force error if not a valid path qualifier
            PathQualifier.from_str(segment)
            path_end = True
        elif segment == "*":
            star = True
        elif '.' in segment:
            segment = QualifiedName.from_str(segment)
        else:
            segment = simple_identifier_from_str(segment)
        segments.append(segment)
    return tuple(segments)


class TargetedTermRef(
        UnicodeMixin,
        collections.namedtuple('TargetedTermRef', ['target', 'term_ref'])):

    """Represents a targeted term reference

    This is a Python namedtuple consisting of a simple identifier
    and a :class:`TermRef` instance (another named tuple).  No syntax
    checking is done on the values at creation.  When converting to
    str (and unicode for Python 2) the components are simply
    joined, e.g.::

        str(TargetedTermRef(
            'TargetProperty',
            TermRef(QualifiedName('Schema', 'Term'), 'Print'))) ==
            'TargetProperty@Schema.Term#Print'
    """

    __slots__ = ()

    def __unicode__(self):
        t, tref = self
        return force_text("%s%s" % (t, to_text(tref)))

    @classmethod
    def from_str(cls, src):
        """Parses a TargetedTermRef from a source string"

        Raises ValueError if src is not a valid TargetedTermRef."""
        try:
            atpos = src.index('@')
            return cls(
                target=simple_identifier_from_str(src[:atpos]),
                term_ref=TermRef.from_str(src[atpos:]))
        except ValueError:
            raise ValueError("Bad targeted term reference: %s" % src)


path_expr_to_str = path_to_str
#: synonym for path_to_str


def path_expr_from_str(src):
    """Simple function for converting a string to a path expression

    src
        A text string

    Returns a (possibly empty) tuple of simple identifiers,
    QualifiedName, TermRef *or TargetedTermRef* segments followed by a
    single, optional, :class:`PathQualifier` as a $-prefixed *string*
    (the special symbol "*" is not allowed)."""
    if not src:
        return tuple()
    segments = []
    path_end = False
    for segment in src.split('/'):
        if path_end:
            # there can be nothing after a path qualifier
            raise ValueError(
                "Unexpected path segment after qualifier: %s" % src)
        elif segment.startswith('@'):
            segment = TermRef.from_str(segment)
        elif '@' in segment:
            segment = TargetedTermRef.from_str(segment)
        elif segment.startswith('$'):
            # will force error if not a valid path qualifier
            if segment != "$count":
                raise ValueError(
                    "%r not allowed in path expression" % segment)
            path_end = True
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
    TermRef or TargetedTermRef segments guaranteeing that the last
    segment is a TermRef."""
    apath = path_expr_from_str(src)
    if not len(apath) or not isinstance(apath[-1], TermRef):
        raise ValueError("Bad AnnotationPath: %s" % src)
    return apath


navigation_path_to_str = path_to_str
#: synonym for path_to_str


def navigation_path_from_str(src):
    return property_path_from_str(src, "NavigationProperty")


property_path_to_str = path_to_str
#: synonym for path_to_str


def property_path_from_str(src, _ptype="Property"):
    """Simple function for converting a string to a property path

    src
        A text string

    _ptype
        Used internally to customise the error message.

    Returns a non-empty tuple of simple identifiers, QualifiedName,
    TermRef or TargetedTermRef segments guaranteeing that the last
    segment is a simple identifier or TermRef."""
    ppath = path_expr_from_str(src)
    if (not len(ppath) or
            not (isinstance(ppath[-1], TermRef) or
                 (is_text(ppath[-1]) and not ppath[-1].startswith('$')))):
        raise ValueError("Bad %s: %s" % (_ptype, src))
    return ppath


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

    def declare(self, nametable, name):
        """A Nametable cannot be declared if it is non-empty"""
        if self._name_table:
            raise errors.NameTableNonEmpty(to_text(self))
        super(NameTable, self).declare(nametable, name)

    def __getitem__(self, key):
        return self._name_table[key]

    def __setitem__(self, key, value):
        if self.closed:
            raise errors.NameTableClosed(to_text(self))
        if key in self._name_table:
            raise errors.DuplicateNameError("%s in %s" % (key, to_text(self)))
        self.check_name(key)
        self.check_value(value)
        self._name_table[key] = value
        for c in self._callbacks.pop(key, []):
            c(value)

    def __delitem__(self, key):
        raise errors.UndeclarationError("%s in %s" % (key, to_text(self)))

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

    def waiting(self, name):
        """True if there is a pending callback for name."""
        if self._callbacks.get(name, None):
            return True
        else:
            return False

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

    @classmethod
    def is_simple_identifier(cls, identifier):
        """Returns True if identifier is a valid SimpleIdentifier"""
        return (identifier is not None and
                _simple_identifier_re.match(identifier) and
                len(identifier) <= 128)

    def _reopen(self):
        # reopens this name table (for unit testing only)
        self.closed = False
        self._callbacks = {}
        self._close_callbacks = []


class QNameTable(NameTable):

    """QNameTable is a special name table supporting QualifiedNames."""

    def check_name(self, name):
        """QNameTables define namespaces that contain named objects.

        The syntax for a namespace is a dot-separated list of simple
        identifiers."""
        if name is None:
            raise ValueError("unnamed schema")
        if not self.is_namespace(name):
            raise ValueError("%s is not a valid namespace" % name)

    def canonicalize_qname(self, qname):
        """Canonicalizes a qualified name

        A qname is either a string of the form "namespace.name" or a
        :class:`QualifiedName` instance.  The return result is a
        QualifiedName instance with the canonical name of the referenced
        namespace (replacing any alias with the canonical namespace
        name).

        If a namespace does not exist with the indicated qualified name
        then KeyError is raised.  (Note that the name does not have to
        exist within the namespace itself)."""
        if is_text(qname):
            qname = QualifiedName.from_str(qname)
        namespace = self[qname.namespace]
        if namespace.name == qname.namespace:
            return qname
        else:
            # replace alias with full namespace name
            return QualifiedName(namespace.name, qname.name)

    def canonicalize_term_ref(self, aname):
        """Canonicalizes a term reference

        A term reference is either a string of form "@namespace.name" or
        a :class:`TermRef` instance.  The return result is a
        TermRef instance with the canonical name of the referenced
        namespace as be :meth:`canonicalize_qname`."""
        if is_text(aname):
            aname = TermRef.from_str(aname)
        namespace = self[aname.name.namespace]
        if namespace.name == aname.name.namespace:
            return aname
        else:
            # replace alias with full namespace name
            return TermRef(
                QualifiedName(namespace.name, aname.name.name),
                aname.qualifier)

    def qualified_get(self, qname, default=None):
        """Looks up qualified name in this entity model.

        qname
            A string or a :class:`QualifiedName` instance.

        default (None)
            The value to return if the name is not declared."""
        if isinstance(qname, QualifiedName):
            namespace, name = qname
        else:
            namespace, name = QualifiedName.from_str(qname)
        try:
            return self[namespace][name]
        except KeyError:
            return default

    def qualified_tell(self, qname, callback):
        """Deferred qualified name lookup.

        Similar to :meth:`Nametable.tell` except that it waits until
        both the namespace containing qname is defined *and* the target
        name is defined within that namespace.

        If the nametable or the indicated namespace is closed without
        qname being declared then the callback is called passing None."""
        if isinstance(qname, QualifiedName):
            nsname, name = qname
        else:
            nsname, name = QualifiedName.from_str(qname)

        def _callback(ns):
            if ns is None:
                callback(None)
            else:
                ns.tell(name, callback)

        self.tell(nsname, _callback)

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
