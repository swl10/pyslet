#! /usr/bin/env python

import logging
import warnings

from ..pep8 import old_function, old_method
from ..py2 import (
    dict_keys,
    dict_values,
    force_text,
    is_string,
    ul)

from .parser import (
    XMLFatalError,
    XMLParser)
from .structures import (
    Document,
    DuplicateXMLNAME,
    Element,
    escape_cdsect,
    escape_char_data,
    is_name_char,
    is_name_start_char,
    is_s,
    Node,
    XMLDTD)


#: URI string constant for the special XML namespace
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

#: URI string constant for the special XMLNS namespace
XMLNS_NAMESPACE = "http://www.w3.org/2000/xmlns/"

#: Special string constant used to represent no namespace
NO_NAMESPACE = "~"


class XMLNSError(XMLFatalError):

    """Raised when an illegal QName is found."""
    pass


@old_function('IsValidNCName')
def is_valid_ncname(name):
    """Checks a string against NCName"""
    if name:
        if not is_name_start_char(name[0]) or name[0] == ":":
            return False
        for c in name[1:]:
            if not is_name_char(c) or c == ":":
                return False
        return True
    else:
        return False


def attr_name_key(aname):
    """A nasty function to make sorting attribute names predictable."""
    if is_string(aname):
        return (NO_NAMESPACE, force_text(aname))
    else:
        return aname


class NSNode(Node):

    """Base class for NSElement and Document shared attributes.

    This class adds a number of method for managing the mapping between
    namespace prefixes and namespace URIs in both elements and in the
    document itself.

    You don't have to worry about using these, they are called
    automatically enabling the transparent serialisation of XML elements
    with appropriately defined namespace prefixes.  You only need to use
    these method if you wish to customise the way the mapping is done.
    The most likely use case is simply to call :meth:`make_prefix` at
    the document level to add an explicit declaration of any auxiliary
    namespaces, typically done by the __init__ method on classes derived
    from NSDocument."""

    def __init__(self, parent=None):
        self._prefix_to_ns = {}
        self._ns_to_prefix = {}
        super(NSNode, self).__init__(parent)

    def reset_prefix_map(self, recursive=False):
        self._prefix_to_ns = {}
        self._ns_to_prefix = {}
        if recursive:
            for child in self.get_children():
                if not is_string(child):
                    child.reset_prefix_map(True)

    @old_method('GetPrefix')
    def get_prefix(self, ns):
        """Returns the prefix assigned to a namespace

        ns
            The namespace URI as a character string.

        Returns None if no prefix is currently in force for this
        namespace."""
        if ns == XML_NAMESPACE:
            return 'xml'
        elif ns is None:
            # Attributes with no namespace
            logging.error("Deprecation warning: None for ns")
            import traceback
            traceback.print_stack()
            return ''
        elif ns == NO_NAMESPACE:
            return ''
        prefix = None
        ei = self
        while prefix is None and ei is not None:
            prefix = ei._ns_to_prefix.get(ns, None)
            if prefix is not None:
                # this is the prefix to use, unless it has been reused...
                ej = self
                while ej is not ei:
                    if ej._prefix_to_ns.get(prefix, None) is not None:
                        # so prefix has been reused, keep searching
                        prefix = None
                        break
                    ej = ej.parent
            ei = ei.parent
        return prefix

    def get_ns(self, prefix=''):
        """Returns the namespace associated with prefix.

        prefix
            The prefix to search for, the empty string denotes the
            default namespace.

        This method searches back through the hierarchy until it finds
        the namespace in force or returns None if no definition for this
        prefix can be found.

        In the special case of prefix being 'xml' the XML namespace
        itself is returned.  See :data:`XML_NAMESPACE`."""
        if prefix == 'xml':
            return XML_NAMESPACE
        ns = None
        ei = self
        while ei is not None:
            ns = ei._prefix_to_ns.get(prefix, None)
            if ns:
                break
            if prefix == '':
                ns = getattr(ei, 'default_ns', None)
                if ns:
                    break
            ei = ei.parent
        return ns

    def new_prefix(self, stem='ns'):
        """Return an unused prefix

        stem
            The returned value will be of the form stem# where
            # is a number used in sequence starting with 1.
            This argument defaults to ns so, by default, the prefixes
            ns1, ns2, ns3, etc. are used."""
        ns = 1
        prefix = ''
        while True:
            prefix = "%s%s" % (stem, ns)
            if self.get_ns(prefix) is not None:
                ns = ns + 1
            else:
                break
        return prefix

    @old_method('MakePrefix')
    def make_prefix(self, ns, prefix=None):
        """Creates a new mapping for a namespace

        ns
            The namespace being mapped

        prefix
            The character string representing the namespace in qualified
            names (without the colon).  This parameter is optional, if
            no value is provided then a new randomly generated prefix is
            used using :meth:`new_prefix`.

            Note that an empty string denotes the default namespace,
            which will appear simply as xmlns=<ns> in the element's
            tag.

        If the prefix has already been declared for this node then
        ValueError is raised."""
        if prefix is None:
            prefix = self.new_prefix()
        if prefix in self._prefix_to_ns:
            raise ValueError
        self._prefix_to_ns[prefix] = ns
        self._ns_to_prefix[ns] = prefix
        return prefix

    def get_prefix_map(self):
        """Returns the complete prefix to ns mapping in force

        Combines the prefix mapping for this element with that of it's
        parents.  Returns a dictionary mapping prefix strings to the
        URIs of the namespaces they represent."""
        prefix_map = {}
        ei = self
        while ei is not None:
            prefix_list = dict_keys(ei._prefix_to_ns)
            for prefix in prefix_list:
                if prefix not in prefix_map:
                    prefix_map[prefix] = ei._prefix_to_ns[prefix]
            ei = ei.parent
        return prefix_map

    def write_nsattrs(self, attributes, escape_function=escape_char_data,
                      root=False, **kws):
        """Adds strings representing any namespace attributes

        See :meth:`~pyslet.xml.structures.Element.write_xml_attributes`
        for details of argument usage.

        This method is defined for both NSDocument and NSElement and it
        prefixes the attribute list with any XML namespace declarations
        that are defined by this node.  If *root* is True then all
        namespace declarations that are in force are written, not just
        those attached to this node.  See :meth:`get_prefix_map` for more
        information."""
        escape_function = kws.get('escapeFunction', escape_function)
        ns_attrs = []
        if root:
            prefix_map = self.get_prefix_map()
        else:
            prefix_map = self._prefix_to_ns
        prefix_list = sorted(dict_keys(prefix_map))
        for prefix in prefix_list:
            if prefix:
                ns_attrs.append(
                    ul('xmlns:%s=%s') %
                    (prefix, escape_function(prefix_map[prefix], True)))
            else:
                ns_attrs.append(
                    ul('xmlns=%s') % escape_function(prefix_map[prefix], True))
        attributes[0:0] = ns_attrs


_xmlns_base = (XML_NAMESPACE, 'base')
_xmlns_lang = (XML_NAMESPACE, 'lang')
_xmlns_space = (XML_NAMESPACE, 'space')


class NSElement(NSNode, Element):

    """Element class used for namespace-aware elements.

    Namespace aware elements have special handling for elements that
    contain namespace declarations and for handling qualified names. A
    qualified name is a name that starts with a namespace prefix
    followed by a colon, for example "md:name" might represent the
    'name' element in a particular namespace indicated by the prefix
    'md'.

    The *same* element could equally be encountered with a different prefix
    depending on the namespace declarations in the document.  As a result,
    to interpret element (and attribute) names they must be expanded.

    An expanded name is represented as a 2-tuple consisting of two
    character strings, the first is a URI of a namespace (used only as
    an identifier, the URI does not have to be the URI of an actual
    resource).  The second item is the element name defined within
    that namespace.

    In general, when dealing with classes derived from NSElement you
    should use expanded names wherever you would normally use a plain
    character string.  For example, the class attribute XMLNAME, used by
    derived classes to indicate the default name to use for the element
    the class represents must be an expanded name::

        class MyElement(NSElement):
            XMLNAME = ('http://www.example.com/namespace', 'MyElement')

    Custom attribute mappings use special class attributes with names
    starting with XMLATTR\_ and this mechanism cannot be extended to use
    the expanded names.  As a result these mappings can only be used for
    attributes that have no namespace.  In practice this is not a
    significant limitation as attributes are usually defined this way in
    XML documents.  Note that the special XML attributes (which appear
    to be in the namespace implicitly decared by the prefix "xml:")
    should be referenced using the special purpose get/set methods
    provided."""

    def __init__(self, parent, name=None):
        super(NSElement, self).__init__(parent)
        if name is not None:
            warnings.warn(
                "NSElement: passing name to constructor is deprecated (%s); "
                "use set_xmlname instead" % name)
            import traceback
            traceback.print_stack()
            self.set_xmlname(name)

    def set_xmlname(self, name):
        """Sets the name of this element

        Overridden to support setting the name from either an expanded
        name or an *unqualified* name (in which case the namespace is
        set to None)."""
        if is_string(name):
            self.ns = None
            self.xmlname = name
        elif name is None:
            self.ns = self.xmlname = None
        else:
            self.ns, self.xmlname = name

    def get_xmlname(self):
        """Returns the name of this element

        For classes derived from NSElement this is always an expanded
        name (even if the first component is None, indicating that the
        namespace is not known."""
        return (self.ns, self.xmlname)

    @classmethod
    def mangle_aname(cls, name):
        """Returns a mangled attribute name

        Custom setters are enabled only for attributes with no
        namespace.  For attriubtes from other namespaces the default
        processing defined by the Element's
        set_attribute/get_attribute(s) implementation is used."""
        ns, aname = name
        if ns is None:
            logging.error("Deprecation warning: None for ns")
            import traceback
            traceback.print_stack()
            return "XMLATTR_" + aname
        elif ns == NO_NAMESPACE:
            return "XMLATTR_" + aname
        else:
            return None

    @classmethod
    def unmangle_aname(cls, mname):
        """Overridden to return an expanded name.

        Custom attribute mappings are only supported for attributes with
        no namespace."""
        if mname.startswith('XMLATTR_'):
            return (NO_NAMESPACE, mname[8:])
        else:
            return None

    def set_attribute(self, name, value):
        """Sets the value of an attribute.

        Overridden to allow attributes to be set using either expanded
        names (2-tuples) or *unqualified* names (character strings).

        Implementation notes: for elements descended from NSElement all
        attributes are stored using expanded names internally.  The
        method :meth:`unmangle_name` is overridden to return a 2-tuple
        to make their 'no namespace' designation explicit.

        This method also catches the new namespace prefix mapping for
        the element which is placed in a special attribute by
        :py:meth:`XMLNSParser.parse_nsattrs` and updates the element's
        namespace mappings accordingly."""
        if name == (NO_NAMESPACE, ".ns"):
            self._prefix_to_ns = nsMap = value
            self._ns_to_prefix = dict(
                (k, v) for (k, v) in
                zip(dict_values(nsMap), dict_keys(nsMap)))
            return
        elif (hasattr(self.__class__, 'ID') and
                (name == (NO_NAMESPACE, self.__class__.ID) or
                 name == self.__class__.ID)):
            # we have to override ID handling as mangling is special
            self.set_id(value)
        if is_string(name):
            return Element.set_attribute(self, (NO_NAMESPACE, name), value)
        else:
            return Element.set_attribute(self, name, value)

    def get_attribute(self, name):
        """Gets the value of an attribute.

        Overridden to allow attributes to be got using either expanded
        names (2-tuples) or *unqualified* names (character strings)."""
        if (hasattr(self.__class__, 'ID') and
                (name == (NO_NAMESPACE, self.__class__.ID) or
                 name == self.__class__.ID)):
            # we have to override ID handling as mangling is special
            return self.id
        if is_string(name):
            return Element.get_attribute(self, (NO_NAMESPACE, name))
        else:
            return Element.get_attribute(self, name)

    def is_valid_name(self, value):
        return is_valid_ncname(value)

    @staticmethod
    def sort_names(name_list):
        name_list.sort(key=attr_name_key)

    def get_base(self):
        return self._attrs.get(_xmlns_base, None)

    def set_base(self, base):
        if base is None:
            self._attrs.pop(_xmlns_base, None)
        else:
            self._attrs[_xmlns_base] = str(base)

    def get_lang(self):
        return self._attrs.get(_xmlns_lang, None)

    def set_lang(self, lang):
        if lang is None:
            self._attrs.pop(_xmlns_lang, None)
        else:
            self._attrs[_xmlns_lang] = lang

    def get_space(self):
        return self._attrs.get(_xmlns_space, None)

    def set_space(self, space):
        if space is None:
            self._attrs.pop(_xmlns_space, None)
        else:
            self._attrs[_xmlns_space] = space

    def write_xml_attributes(self, attributes,
                             escape_function=escape_char_data, root=False,
                             **kws):
        escape_function = kws.get('escapeFunction', escape_function)
        attrs = self.get_attributes()
        keys = sorted(dict_keys(attrs))
        for a in keys:
            if is_string(a):
                logging.error(
                    "Deprecation warning: found attribute with no namespace "
                    "in NSElement, %s(%s)", self.__class__.__name__, a)
                aname = a
                prefix = ''
            else:
                ns, aname = a
                prefix = self.get_prefix(ns)
            if prefix is None:
                prefix = self.make_prefix(ns)
            if prefix:
                prefix = prefix + ':'
            attributes.append(
                ul('%s%s=%s') % (prefix, aname, escape_function(attrs[a],
                                                                True)))
        self.write_nsattrs(
            attributes, escape_function=escape_char_data, root=root)

    def generate_xml(self, escape_function=escape_char_data, indent='',
                     tab='\t', root=False, **kws):
        escape_function = kws.get('escapeFunction', escape_function)
        if tab:
            ws = '\n' + indent
            indent = indent + tab
        else:
            ws = ''
        if not self.can_pretty_print():
            # inline all children
            indent = ''
            tab = ''
        attributes = []
        if self.ns:
            # look up the element prefix
            prefix = self.get_prefix(self.ns)
            if prefix is None:
                # We need to declare our namespace
                prefix = self.make_prefix(self.ns, '')
        else:
            prefix = ''
        if prefix:
            prefix = prefix + ':'
        self.write_xml_attributes(attributes, escape_function, root=root)
        if attributes:
            attributes[0:0] = ['']
            attributes = ' '.join(attributes)
        else:
            attributes = ''
        children = self.get_canonical_children()
        try:
            child = next(children)
            if is_string(child) and len(child) and is_s(child[0]):
                # First character is WS, so assume pre-formatted.
                indent = tab = ''
            yield ul('%s<%s%s%s>') % (ws, prefix, self.xmlname, attributes)
            if hasattr(self.__class__, 'SGMLCDATA'):
                # When expressed in SGML this element would have type
                # CDATA so put it in a CDSect
                yield escape_cdsect(self.get_value())
            else:
                while True:
                    if is_string(child):
                        # We force encoding of carriage return as these
                        # are subject to removal
                        yield escape_function(child)
                        # if we have character data content skip closing
                        # ws
                        ws = ''
                    else:
                        try:
                            for s in child.generate_xml(
                                    escape_function, indent, tab):
                                yield s
                        except TypeError:
                            logging.error(
                                "Problem with %s: child was %s",
                                self.__class__.__name__, repr(child))
                            raise
                    try:
                        child = next(children)
                    except StopIteration:
                        break
            if not tab:
                # if we weren't tabbing children we need to skip closing
                # white space
                ws = ''
            yield ul('%s</%s%s>') % (ws, prefix, self.xmlname)
        except StopIteration:
            yield ul('%s<%s%s%s/>') % (ws, prefix, self.xmlname, attributes)


# name provided for backwards compatibility
XMLNSElement = NSElement


class NSDocument(Document, NSNode):

    default_ns = None
    """The default namespace for this document class

    A special class attribute used to set the default namespace for
    elements created within the document that are parsed without an
    effective namespace declaration.  Set to None, but typically
    overridden by derived classes."""

    def XMLParser(self, entity):    # noqa
        """Namespace documents use the special :py:class:`XMLNSParser`.
        """
        return XMLNSParser(entity)

    @classmethod
    def get_element_class(cls, name):
        """Returns a class object suitable for representing <name>

        name is a tuple of (namespace, name), this overrides the
        behaviour of Document, in which name is a string.

        The default implementation returns NSElement."""
        return NSElement


#: name provided for backwards compatibility
XMLNSDocument = NSDocument


class XMLNSParser(XMLParser):

    """A special parser for parsing documents that may use namespaces."""

    _nsdoc_class_table = {}

    @classmethod
    def register_nsdoc_class(cls, doc_class, xname):
        """Registers a document class

        Internally XMLNSParser maintains a single table of document
        classes which can be used to identify the correct class to use
        to represent a document based on the expanded name of the root
        element.

        doc_class
            the class object being registered, it must be derived from
            :py:class:`NSDocument`

        xname
            A tuple of (namespace, name) representing the name of the
            root element.  If either (or both) components are None a
            wildcard is registered that will match any corresponding
            value."""
        cls._nsdoc_class_table[xname] = doc_class

    def get_nsdoc_class(self, xname):
        """Returns a doc class object suitable for this root element

        xname
            An expanded name.

        Returns a class object derived from :py:class:`NSDocument`
        suitable for representing a document with a root element with
        the given expanded name.

        This default implementation uses xname to locate a class
        registered with :meth:`register_nsdoc_class`.  If an exact match
        is not found then wildcard matches are tried matching *only* the
        namespace and root element name in turn.

        A wildcard match is stored in the mapping table either as an
        expanded name of the form (<uri string>, None) or (None,
        <element name>).  The former is preferred as it enables a
        document class to be defined that is capable of representing a
        document with any root element from the given namespace (a
        common use case) and is thus always tried first.

        If no document class can be found, :py:class:`NSDocument` is
        returned."""
        if xname[0] is None:
            doc_class = XMLParser._nsdoc_class_table.get(xname, None)
        else:
            doc_class = XMLParser._nsdoc_class_table.get(xname, None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (xname[0], None), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (None, xname[1]), None)
        if doc_class is None:
            doc_class = NSDocument
        return doc_class

    def __init__(self, entity=None):
        XMLParser.__init__(self, entity)

    def expand_qname(self, qname, ns_defs, use_default=True):
        """Expands a QName, returning a (namespace, name) tuple.

        qname
            The qualified name

        ns_defs
            A mapping of prefix to namespace URI used to expand the name

            If *ns_defs* does not contain a suitable namespace
            definition then the context's existing prefix mapping is
            used, then its parent's mapping is used, and so on.

        use_default (defaults to True)
            Whether or not to return the default namespace for an
            unqualified name.

            If *use_default* is False an unqualified name is returned
            with :py:data:`NO_NAMESPACE` as the namespace (this is used when
            expanding attribute names)."""
        context = self.get_context()
        xname = qname.split(':')
        if len(xname) == 1:
            if qname == 'xmlns':
                return (XMLNS_NAMESPACE, '')
            elif use_default:
                ns_uri = ns_defs.get('', None)
                if ns_uri is None and context is not None:
                    ns_uri = context.get_ns('')
                return (ns_uri, qname)
            else:
                return (NO_NAMESPACE, qname)
        elif len(xname) == 2:
            nsprefix, local = xname
            if nsprefix == 'xml':
                return (XML_NAMESPACE, local)
            elif nsprefix == 'xmlns':
                return (XMLNS_NAMESPACE, local)
            else:
                ns_uri = ns_defs.get(nsprefix, None)
                if ns_uri is None and context is not None:
                    ns_uri = context.get_ns(nsprefix)
                return (ns_uri, local)
        else:
            # something wrong with this element
            raise XMLNSError("Illegal QName: %s" % qname)

    def match_xml_name(self, element, qname):
        """Tests if *qname* is a possible name for this element.

        This method is used by the parser to determine if an end tag is the end
        tag of this element."""
        return element.get_xmlname() == self.expand_qname(qname, {}, True)

    def parse_nsattrs(self, attrs):
        """Manages namespace prefix mappings

        Takes a dictionary of attributes as returned by
        :meth:`parse_stag` and finds any namespace prefix mappings
        returning them as a dictionary of prefix:namespace suitable for
        passing to :py:meth:`expand_qname`.  It also removes the
        namespace declarations from attrs and expands the attribute
        names into (ns, name) pairs.

        Implementation note: a special attribute called '.ns' (in no
        namespace) is set to the parsed prefix mapping dictionary
        enabling the prefix mapping to be passed transparently to
        :py:meth:`NSElement.set_attribute` by py:class:`XMLParser`."""
        ns = {}
        for aname in list(dict_keys(attrs)):
            if aname.startswith('xmlns'):
                if len(aname) == 5:
                    # default ns declaration
                    ns[''] = attrs[aname]
                elif aname[5] == ':':
                    # ns prefix declaration
                    ns[aname[6:]] = attrs[aname]
                del attrs[aname]
        for aname in list(dict_keys(attrs)):
            xname = self.expand_qname(aname, ns, False)
            attrs[xname] = attrs[aname]
            del attrs[aname]
        # Finally, we hide the ns object in the list of attributes so we
        # can retrieve it later Note that '.' is not a valid
        # NameStartChar so we will never collide with a real attribute
        attrs[(NO_NAMESPACE, ".ns")] = ns
        return ns

    def get_stag_class(self, qname, attrs=None):
        """[40] STag

        Overridden to allow for namespace handling."""
        if self.doc is None:
            if self.dtd is None:
                self.dtd = XMLDTD()
            if self.dtd.name is None:
                self.dtd.name = qname
            elif qname is None:
                # document starts with PCDATA, use name declared in DOCTYPE
                qname = self.dtd.name
        # go through attributes and process namespace declarations
        if attrs and not ((NO_NAMESPACE, ".ns") in attrs):
            # This deserves an explanation.  It is possible that
            # get_stag_class will infer an element in sgml_omittag mode
            # forcing the parser to buffer this qname and its associated
            # attributes after we've done namespace expansion of them.
            # There is a real question over whether or not it is safe to
            # buffer expanded attribute names.  It is conceivable that
            # the omitted tag could have FIXED attributes which alter
            # the namespace prefix map.  In theory, we should go back to
            # the original attribute names but smglOmittag mode is a fix
            # up for conforming SGML-style documents into XML (i.e.,
            # HTML).  As such, ignoring this subtle namespacing issue
            # seems reasonable.
            ns = self.parse_nsattrs(attrs)
        else:
            ns = {}
        if qname:
            xname = self.expand_qname(qname, ns)
        else:
            xname = None
        if self.doc is None:
            # we use the expanded name to find the document class, not the DTD
            doc_class = self.get_nsdoc_class(xname)
            self.doc = doc_class()
        else:
            doc_class = self.doc.__class__
        context = self.get_context()
        if qname and xname[0] is None:
            xname = (doc_class.default_ns, xname[1])
        if self.sgml_omittag:
            if qname:
                stag_class = self.doc.get_element_class(xname)
            else:
                stag_class = str
            element_class = context.get_child_class(stag_class)
            if element_class is not stag_class:
                return element_class, None, True
            elif element_class is str:
                # unhanded data, end tag omission not supported
                self.validity_error(
                    "data not allowed in %s (and end-tag omission not "
                    "supported)" % context.__class__.__name__)
                return None, xname, False
            else:
                return element_class, xname, False
        else:
            stag_class = context.get_element_class(xname)
            if stag_class is None:
                stag_class = self.doc.get_element_class(xname)
            return stag_class, xname, False
            # return
            # self.doc.get_element_class(xname),xname,False


@old_function('MapClassElements')
def map_class_elements(class_map, scope, ns_alias_table=None):
    """Adds element name -> class mappings to class_map

    class_map
        A dictionary that maps XML element *expanded* names onto class
        objects that should be used to represent them.

    scope
        A dictionary, or an object containing a __dict__ attribute, that
        will be scanned for class objects to add to the mapping.  This
        enables scope to be a module.  The search is not recursive, to
        add class elements from imported modules you must call
        map_class_elements for each module.

    ns_alias_table
        Used to create multiple mappings for selected element classes
        based on namespace aliases.  It is a dictionary mapping a
        canonical namespace to a list of aliases.  For example, if::

            ns_alias_table={'http://www.example.com/schema-v3': [
                                'http://www.example.com/schema-v2',
                                'http://www.example.com/schema-v1']}

        An element class with::

            XMLNAME = ('http://www.example.com/schema-v3', 'data')

        would then be used by the parser to represent the <data> element
        in the v1, v2 and v3 schema variants.

    The scope is searched for classes derived from :py:class:`NSElement`
    that have an XMLNAME attribute defined.  It is an error if a class
    is found with an XMLNAME that has already been mapped."""
    if not isinstance(scope, dict):
        scope = scope.__dict__
    for name in dict_keys(scope):
        obj = scope[name]
        if issubclass(type(obj), type) and issubclass(obj, NSElement):
            if hasattr(obj, 'XMLNAME'):
                if obj.XMLNAME in class_map:
                    raise DuplicateXMLNAME(
                        "%s and %s have matching XMLNAMEs" %
                        (obj.__name__, class_map[obj.XMLNAME].__name__))
                class_map[obj.XMLNAME] = obj
                if ns_alias_table:
                    aliases = ns_alias_table.get(obj.XMLNAME[0], ())
                    for alias in aliases:
                        alias_name = (alias, obj.XMLNAME[1])
                        if alias_name in class_map:
                            raise DuplicateXMLNAME(
                                "%s and %s have matching XMLNAME alias %s" %
                                (obj.__name__,
                                 class_map[obj.XMLNAME].__name__, alias_name))
                        class_map[alias_name] = obj


@old_function('NSEqualNames')
def match_expanded_names(xname, xmatch, ns_aliases=None):
    """Compares two expanded names

    xname, xmatch
        Expanded names, i.e., 2-tuples of character strings containing
        (namespace URI, element name).

    ns_aliases
        Used to match multiple names based on namespace aliases.  It is
        a list of namespaces that should be treated as equivalent to the
        namespace of xname.  For example::

            match_expanded_names(
                ('http://www.example.com/schema-v3','data'),
                ('http://www.example.com/schema-v1','data'),
                ['http://www.example.com/schema-v2',
                 'http://www.example.com/schema-v1'])

        returns True as xmatch uses an allowed alias for the namespace
        of xname."""
    if xname == xmatch:
        return True
    else:
        for alias in ns_aliases:
            if (alias, xname[1]) == xmatch:
                return True
    return False


@old_function('RegisterNSDocumentClass')
def register_nsdoc_class(doc_class, expanded_name):
    XMLNSParser.register_nsdoc_class(doc_class, expanded_name)
