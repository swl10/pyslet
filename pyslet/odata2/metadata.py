#! /usr/bin/env python
"""OData core elements"""

import warnings

from .. import rfc4287 as atom
from ..http import grammar
from ..http import params
from ..pep8 import MigratedClass, old_method
from ..xml import namespace as xmlns

from . import csdl as edm
from . import edmx
from . import core


# Legacy name for compatibilty
InvalidMetadataDocument = edm.InvalidMetadataDocument


class FeedCustomisationMixin(MigratedClass):

    """Utility class used to add common feed customisation attributes"""

    AtomPaths = {
        'SyndicationAuthorName': [
            (atom.ATOM_NAMESPACE, "author"),
            (atom.ATOM_NAMESPACE, "name")],
        'SyndicationAuthorEmail': [
            (atom.ATOM_NAMESPACE, "author"),
            (atom.ATOM_NAMESPACE, "email")],
        'SyndicationAuthorUri': [
            (atom.ATOM_NAMESPACE, "author"),
            (atom.ATOM_NAMESPACE, "uri")],
        'SyndicationPublished': [(atom.ATOM_NAMESPACE, "published")],
        'SyndicationRights': [(atom.ATOM_NAMESPACE, "rights")],
        'SyndicationSummary': [(atom.ATOM_NAMESPACE, "summary")],
        'SyndicationTitle': [(atom.ATOM_NAMESPACE, "title")],
        'SyndicationUpdated': [(atom.ATOM_NAMESPACE, "updated")],
        'SyndicationContributorName': [
            (atom.ATOM_NAMESPACE, "contributor"),
            (atom.ATOM_NAMESPACE, "name")],
        'SyndicationContributorEmail': [
            (atom.ATOM_NAMESPACE, "contributor"),
            (atom.ATOM_NAMESPACE, "email")],
        'SyndicationContributorUri': [(atom.ATOM_NAMESPACE, "source")]
    }

    @old_method('GetTargetPath')
    def get_target_path(self):
        """Returns the target path for an element

        The result is a list of qualified element names, that is, tuples
        of (namespace,name). The last name may start with '@' indicating
        an attribute rather than an element.

        Feed customisations are declared using the FC_TargetPath
        attribute.  Returns None if there is no target path declared."""
        try:
            path = self.get_attribute(core.FC_TargetPath)
            if path in self.AtomPaths:
                return self.AtomPaths[path]
            else:
                ns = self.get_attribute(core.FC_NsUri)
                return [(ns, x) for x in path.split('/')]
        except KeyError:
            return None

    @old_method('KeepInContent')
    def keep_in_content(self):
        """Returns true if a property value should be kept in the content

        This is indicated with the FC_KeepInContent attribute.  If the
        attribute is missing then False is returned, so properties with
        custom paths default to being omitted from the properties
        list."""
        try:
            return self.get_attribute(core.FC_KeepInContent) == "true"
        except KeyError:
            return False

    @old_method('GetFCNsPrefix')
    def get_fc_ns_prefix(self):
        """Returns the custom namespace mapping to use.

        The value is read from the FC_NsPrefix attribute.  The result is
        a tuple of: (prefix, namespace uri).

        If no mapping is specified then (None,None) is returned."""
        try:
            prefix = self.get_attribute(core.FC_NsPrefix)
            ns = self.get_attribute(core.FC_NsUri)
            return prefix, ns
        except KeyError:
            return None, None


class EntityType(edm.EntityType, FeedCustomisationMixin):

    """Supports feed customisation behaviour of EntityTypes"""

    @old_method('GetSourcePath')
    def get_source_path(self):
        """Returns the source path

        This result is read from the FC_SourcePath attribute.  It is a
        *list* of property names that represents a path into the entity
        or None if there is no source path set."""
        try:
            return self.get_attribute(core.FC_SourcePath).split('/')
        except KeyError:
            return None

    @old_method('HasStream')
    def has_stream(self):
        """Returns true if this is a media link resource.

        Read from the HasStream attribute.  The default is False."""
        try:
            return self.get_attribute(core.HAS_STREAM) == "true"
        except KeyError:
            return False


class Property(edm.Property, FeedCustomisationMixin):

    """Supports feed customisation behaviour of Properties"""

    @old_method('GetMimeType')
    def get_mime_type(self):
        """Returns the media type of a property

        The result is read from the MimeType attribute.  It is a
        :py:class:`~pyslet.http.params.MediaType` instance or None if
        the attribute is not defined."""
        try:
            return params.MediaType.from_str(
                self.get_attribute(core.MIME_TYPE))
        except KeyError:
            return None

    def __call__(self, literal=None):
        """Overridden to add mime type handling

        Property elements are callable in the core EDM, returning an
        :py:class:`~pyslet.odata2.core.EDMValue` object instantiated
        from the declaration.  This implementation adds to the base
        behaviour by reading the optional mime type attribute and adding
        it to the value if applicable."""
        value = super(Property, self).__call__(literal)
        value.mtype = self.get_mime_type()
        return value


class EntityContainer(edm.EntityContainer):

    """Supports OData's concept of the default container."""

    @old_method('IsDefaultEntityContainer')
    def is_default_entity_container(self):
        """Returns True if this is the default entity container

        The value is read from the IsDefaultEntityContainer attribute.
        The default is False."""
        try:
            return self.get_attribute(
                core.IS_DEFAULT_ENTITY_CONTAINER) == "true"
        except KeyError:
            return False

    def content_changed(self):
        super(EntityContainer, self).content_changed()
        if self.is_default_entity_container():
            ds = self.find_parent(DataServices)
            if ds is not None:
                ds.defaultContainer = self


class EntitySet(edm.EntitySet):

    def set_location(self):
        """Overridden to add support for the default entity container

        By default, the path to an EntitySet includes the name of the
        container it belongs to, e.g., MyDatabase.MyTable.  This
        implementation checks to see if we in the default container and,
        if so, omits the container name prefix before setting the
        location URI."""
        container = self.find_parent(EntityContainer)
        if container and not container.is_default_entity_container():
            path = container.name + '.' + self.name
        else:
            path = self.name
        self.location = self.resolve_uri(path)


class DataServices(edmx.DataServices):

    """Adds OData specific behaviour"""

    def __init__(self, parent):
        super(DataServices, self).__init__(parent)
        #: the default entity container
        self.defaultContainer = None

    @old_method('DataServicesVersion')
    def data_services_version(self):
        """Returns the data service version

        Read from the DataServiceVersion attribute.  Defaults to None."""
        try:
            return self.get_attribute(core.DATA_SERVICE_VERSION)
        except KeyError:
            return None

    @old_method('SearchContainers')
    def search_containers(self, name):
        """Returns an entity set or service operation with *name*

        *name* must be of the form::

            [<entity container>.]<entity set, function or operation name>

        The entity container must be present unless the target is in the
        default container in which case it *must not* be present.

        If *name* can't be found KeyError is raised."""
        resource = None
        if name in self.defaultContainer:
            return self.defaultContainer[name]
        else:
            for s in self.Schema:
                if name in s:
                    resource = s[name]
                    container = resource.find_parent(edm.EntityContainer)
                    if container is self.defaultContainer:
                        continue
                    return resource
        raise KeyError(
            "No entity set or service operation with name %s" % name)


class Edmx(edmx.Edmx):

    """The root element of OData-specific metadata documents"""

    DataServicesClass = DataServices


def ValidateMetadataDocument(doc):      # noqa
    warnings.warn(
        "ValidateMetadataDocument is deprecated, use validate method instead",
        DeprecationWarning,
        stacklevel=3)
    return doc.validate()


class Document(edmx.Document):

    """Class for working with OData-specific metadata documents.

    Adds namespace prefix declarations for the OData metadata and OData
    dataservices namespaces."""

    classMap = {}

    def __init__(self, **args):
        edmx.Document.__init__(self, **args)
        self.make_prefix(core.ODATA_METADATA_NAMESPACE, 'm')
        self.make_prefix(core.ODATA_DATASERVICES_NAMESPACE, 'd')

    @classmethod
    def get_element_class(cls, name):
        """Returns the class used to represent an element.

        Overrides
        :py:meth:`~pyslet.odata2.edmx.Document.get_element_class` to use
        the OData-specific implementations of the edmx/csdl classes
        defined in this module."""
        result = Document.classMap.get(name, None)
        if result is None:
            result = edmx.Document.get_element_class(name)
        return result

    @old_method('Validate')
    def validate(self):
        """Validates any declared OData extensions

        Checks many of the requirements given in the specification and
        raises :py:class:`~pyslet.odata2.csdl.InvalidMetadataDocument`
        if the tests fail.

        Returns the data service version required to process the service
        or None if no data service version is specified."""
        super(Document, self).validate()
        # IsDefaultEntityContainer: This attribute MUST be used on an
        # EntityContainer element to indicate which EntityContainer is the
        # default container for the data service. Each conceptual schema
        # definition language (CSDL) document used to describe a data
        # service MUST mark exactly one EntityContainer with this attribute
        # to denote it is the default.
        ndefaults = 0
        for container in self.root.find_children_depth_first(
                edm.EntityContainer):
            try:
                flag = container.get_attribute(
                    core.IS_DEFAULT_ENTITY_CONTAINER)
                if flag == "true":
                    ndefaults += 1
                elif flag != "false":
                    raise edm.InvalidMetadataDocument(
                        "IsDefaultEntityContainer: %s" % flag)
            except KeyError:
                pass
        if ndefaults != 1:
            raise edm.InvalidMetadataDocument(
                "IsDefaultEntityContainer required on "
                "one and only one EntityContainer")
        for p in self.root.find_children_depth_first(edm.Property):
            try:
                params.MediaType.from_str(p.get_attribute(core.MIME_TYPE))
            except grammar.BadSyntax as e:
                raise edm.InvalidMetadataDocument(
                    "MimeType format error in property %s: %s" %
                    (p.name, str(e)))
            except KeyError:
                pass
        # HttpMethod: This attribute MUST be used on a <FunctionImport>
        # element to indicate the HTTP method which is to be used to invoke
        # the ServiceOperation exposing the FunctionImport
        for f in self.root.find_children_depth_first(edm.FunctionImport):
            try:
                if f.get_attribute(core.HttpMethod) in (
                        "POST", "PUT", "GET", "MERGE", "DELETE"):
                    continue
                raise edm.InvalidMetadataDocument(
                    "Bad HttpMethod: %s" % f.get_attribute(core.HttpMethod))
            except KeyError:
                raise edm.InvalidMetadataDocument(
                    "FunctionImport must have HttpMethod defined: %s" % f.name)
        # HasStream: This attribute MUST only be used on an <EntityType>
        # element
        for e in self.root.find_children_depth_first(edm.CSDLElement):
            try:
                hs = e.get_attribute(core.HAS_STREAM)
                if not isinstance(e, edm.EntityType):
                    raise edm.InvalidMetadataDocument(
                        "HasStream must only be used on EntityType")
                elif hs not in ("true", "false"):
                    raise edm.InvalidMetadataDocument(
                        "Bad value for HasStream: %s" % hs)
            except KeyError:
                pass
        # DataServiceVersion: This attribute MUST be in the data service
        # metadata namespace and SHOULD be present on a <edmx:DataServices>
        # element to indicate the version of the data service CSDL
        # annotations (attributes in the data service metadata namespace)
        # used by the document.
        #
        # The value of this attribute MUST be 1.0 unless a
        # "FC_KeepInContent" Customizable Feed annotation with a value equal
        # to false is present... In this case, the attribute value MUST be
        # 2.0.
        try:
            version = self.root.DataServices.get_attribute(
                core.DATA_SERVICE_VERSION)
            match = "1.0"
            for e in self.root.find_children_depth_first(edm.CSDLElement):
                try:
                    if e.get_attribute(core.FC_KeepInContent) == "false":
                        match = "2.0"
                        break
                except KeyError:
                    pass
            if version != match:
                raise edm.InvalidMetadataDocument(
                    "Expected version %s, found %s" % (match, version))
            return version
        except KeyError:
            return None

xmlns.map_class_elements(Document.classMap, globals(), edm.NAMESPACE_ALIASES)
