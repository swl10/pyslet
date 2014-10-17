#! /usr/bin/env python
"""OData core elements"""

import warnings

import pyslet.http.grammar as grammar
import pyslet.http.params as params
import pyslet.rfc4287 as atom
import pyslet.xmlnames20091208 as xmlns
from pyslet.pep8 import renamed_method

import csdl as edm
import edmx as edmx
import core as core


class FeedCustomisationMixin(object):

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

    @renamed_method
    def GetTargetPath(self):       # noqa
        pass

    def get_target_path(self):
        """Returns the target path for the property or None if there is
        no target path set for the property.  The result is a list of
        qualified element names, that is, tuples of (namespace,name).
        The last name may start with '@' indicating an attribute rather
        than an element."""
        try:
            path = self.GetAttribute(core.FC_TargetPath)
            if path in self.AtomPaths:
                return self.AtomPaths[path]
            else:
                ns = self.GetAttribute(core.FC_NsUri)
                return map(lambda x: (ns, x), path.split('/'))
        except KeyError:
            return None

    @renamed_method
    def KeepInContent(self):       # noqa
        pass

    def keep_in_content(self):
        """Returns true if the property should be kept in the content."""
        try:
            return self.GetAttribute(core.FC_KeepInContent) == "true"
        except KeyError:
            return False

    @renamed_method
    def GetFCNsPrefix(self):       # noqa
        pass

    def get_fc_ns_prefix(self):
        """Returns the custom namespace mapping to use.  The result is a
        tuple of:

        (prefix, namespace uri)

        If no mapping is specified then (None,None) is returned."""
        try:
            prefix = self.GetAttribute(core.FC_NsPrefix)
            ns = self.GetAttribute(core.FC_NsUri)
            return prefix, ns
        except KeyError:
            return None, None


class EntityType(edm.EntityType, FeedCustomisationMixin):

    @renamed_method
    def GetSourcePath(self):       # noqa
        pass

    def get_source_path(self):
        """Returns the source path for the property or None if there is
        no source path set.  The result is a list of property names."""
        try:
            return self.GetAttribute(core.FC_SourcePath).split('/')
        except KeyError:
            return None

    @renamed_method
    def HasStream(self):       # noqa
        pass

    def has_stream(self):
        """Returns true if this entity type describes a media link resource."""
        try:
            return self.GetAttribute(core.HAS_STREAM) == "true"
        except KeyError:
            return False


class Property(edm.Property, FeedCustomisationMixin):

    @renamed_method
    def GetMimeType(self):       # noqa
        pass

    def get_mime_type(self):
        try:
            return params.MediaType.from_str(self.GetAttribute(core.MIME_TYPE))
        except KeyError:
            return None

    def __call__(self, literal=None):
        """Overridden to add mime type handling"""
        value = super(Property, self).__call__(literal)
        value.mtype = self.get_mime_type()
        return value


class EntityContainer(edm.EntityContainer):

    @renamed_method
    def IsDefaultEntityContainer(self):       # noqa
        pass

    def is_default_entity_container(self):
        try:
            return self.GetAttribute(
                core.IS_DEFAULT_ENTITY_CONTAINER) == "true"
        except KeyError:
            return False

    def content_changed(self):
        super(EntityContainer, self).content_changed()
        if self.is_default_entity_container():
            ds = self.FindParent(DataServices)
            if ds is not None:
                ds.defaultContainer = self


class EntitySet(edm.EntitySet):

    def set_location(self):
        """Overridden to add support for the default entity container."""
        container = self.FindParent(EntityContainer)
        if container and not container.is_default_entity_container():
            path = container.name + '.' + self.name
        else:
            path = self.name
        self.location = self.ResolveURI(path)


class DataServices(edmx.DataServices):

    def __init__(self, parent):
        super(DataServices, self).__init__(parent)
        self.defaultContainer = None		#: the default entity container

    @renamed_method
    def DataServicesVersion(self):       # noqa
        pass

    def data_services_version(self):
        """Returns the data service version, or None if none is defined"""
        try:
            return self.GetAttribute(core.DATA_SERVICE_VERSION)
        except KeyError:
            return None

    @renamed_method
    def SearchContainers(self):         # noqa
        pass

    def search_containers(self, name):
        """Returns an entity set or service operation with *name*

        *name* must be of the form::

                [<entity container>.]<function or operation name>

        The entity container must be present unless the target is in the
        default container in which case it must not be present.

        If *name* can't be found KeyError is raised."""
        resource = None
        if name in self.defaultContainer:
            return self.defaultContainer[name]
        else:
            for s in self.Schema:
                if name in s:
                    resource = s[name]
                    container = resource.FindParent(edm.EntityContainer)
                    if container is self.defaultContainer:
                        continue
                    return resource
        raise KeyError(
            "No entity set or service operation with name %s" % name)


class Edmx(edmx.Edmx):
    DataServicesClass = DataServices


def ValidateMetadataDocument(doc):      # noqa
    warnings.warn(
        "ValidateMetadataDocument is deprecated, use validate method instead",
        DeprecationWarning,
        stacklevel=3)
    return doc.validate()


class Document(edmx.Document):

    """Class for working with OData metadata documents."""
    classMap = {}

    def __init__(self, **args):
        edmx.Document.__init__(self, **args)
        self.MakePrefix(core.ODATA_METADATA_NAMESPACE, 'm')
        self.MakePrefix(core.ODATA_DATASERVICES_NAMESPACE, 'd')

    @classmethod
    def get_element_class(cls, name):
        """Returns the OData, edmx or csdl class used to represent name.

        Overrides :py:meth:`~pyslet.rfc5023.Document.get_element_class` to
        allow custom implementations of the edmx/csdl classes to be
        created and to cater for OData-specific annotations."""
        result = Document.classMap.get(name, None)
        if result is None:
            result = edmx.Document.get_element_class(name)
        return result

    @renamed_method
    def Validate(self):       # noqa
        pass

    def validate(self):
        """Validates the OData extensions and returns the data service
        version required to process the service or None if no data
        service version is specified."""
        # These extensions MUST be used by a data service in conjunction
        # with the "dataservices" node
        if not isinstance(self.root.DataServices, edmx.DataServices):
            raise core.InvalidMetadataDocument("Expected dataservices node")
        # IsDefaultEntityContainer: This attribute MUST be used on an
        # EntityContainer element to indicate which EntityContainer is the
        # default container for the data service. Each conceptual schema
        # definition language (CSDL) document used to describe a data
        # service MUST mark exactly one EntityContainer with this attribute
        # to denote it is the default.
        ndefaults = 0
        for container in self.root.FindChildrenDepthFirst(edm.EntityContainer):
            try:
                flag = container.GetAttribute(core.IS_DEFAULT_ENTITY_CONTAINER)
                if flag == "true":
                    ndefaults += 1
                elif flag != "false":
                    raise core.InvalidMetadataDocument(
                        "IsDefaultEntityContainer: %s" % flag)
            except KeyError:
                pass
        if ndefaults != 1:
            raise core.InvalidMetadataDocument(
                "IsDefaultEntityContainer required on "
                "one and only one EntityContainer")
        for p in self.root.FindChildrenDepthFirst(edm.Property):
            try:
                params.MediaType.from_str(p.GetAttribute(core.MIME_TYPE))
            except grammar.BadSyntax as e:
                raise core.InvalidMetadataDocument(
                    "MimeType format error in property %s: %s" %
                    (p.name, str(e)))
            except KeyError:
                pass
        # HttpMethod: This attribute MUST be used on a <FunctionImport>
        # element to indicate the HTTP method which is to be used to invoke
        # the ServiceOperation exposing the FunctionImport
        for f in self.root.FindChildrenDepthFirst(edm.FunctionImport):
            try:
                if f.GetAttribute(core.HttpMethod) in (
                        u"POST", u"PUT", u"GET", u"MERGE", u"DELETE"):
                    continue
                raise core.InvalidMetadataDocument(
                    "Bad HttpMethod: %s" % f.GetAttribute(core.HttpMethod))
            except KeyError:
                raise core.InvalidMetadataDocument(
                    "FunctionImport must have HttpMethod defined: %s" % f.name)
        # HasStream: This attribute MUST only be used on an <EntityType>
        # element
        for e in self.root.FindChildrenDepthFirst(edm.CSDLElement):
            try:
                hs = e.GetAttribute(core.HAS_STREAM)
                if not isinstance(e, edm.EntityType):
                    raise core.InvalidMetadataDocument(
                        "HasStream must only be used on EntityType")
                elif hs not in ("true", "false"):
                    raise core.InvalidMetadataDocument(
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
            version = self.root.DataServices.GetAttribute(
                core.DATA_SERVICE_VERSION)
            match = "1.0"
            for e in self.root.FindChildrenDepthFirst(edm.CSDLElement):
                try:
                    if e.GetAttribute(core.FC_KeepInContent) == "false":
                        match = "2.0"
                        break
                except KeyError:
                    pass
            if version != match:
                raise core.InvalidMetadataDocument(
                    "Expected version %s, found %s" % (match, version))
            return version
        except KeyError:
            return None

xmlns.MapClassElements(Document.classMap, globals(), edm.NAMESPACE_ALIASES)
