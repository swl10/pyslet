#! /usr/bin/env python
"""This module implements test to check against the IMSCC Profile 1.1
specification defined by IMS GLC"""

from . import imscc_profilev1p0 as v1p0
from . import imscpv1p2 as imscp
from .xml import namespace as xmlns
from .xml import xsdatatypes as xsi


IMSCC_CP_NAMESPACE = "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"
IMSCC_CP_SCHEMALOCATION = ("http://www.imsglobal.org/profile/cc/ccv1p2/"
                           "ccv1p2_imscp_v1p2_v1p0.xsd")

IMSCC_LOMMANIFEST_NAMESPACE = "http://ltsc.ieee.org/xsd/imsccv1p2/LOM/manifest"
IMSCC_LOMMANIFEST_SCHEMALOCATION = ("http://www.imsglobal.org/profile/cc/"
                                    "ccv1p2/LOM/ccv1p2_lommanifest_v1p0.xsd")

IMSCC_LOMRESOURCE_NAMESPACE = "http://ltsc.ieee.org/xsd/imsccv1p2/LOM/resource"
IMSCC_LOMRESOURCE_SCHEMALOCATION = ("http://www.imsglobal.org/profile/cc/"
                                    "ccv1p2/LOM/ccv1p2_lomresource_v1p0.xsd")


class Schema(imscp.Schema):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'schema')


class SchemaVersion(imscp.SchemaVersion):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'schemaversion')


class Metadata(imscp.Metadata):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'metadata')
    SchemaClass = Schema
    SchemaVersionClass = SchemaVersion


class Organization(imscp.Organization):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'organization')


class Organizations(imscp.Organizations):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'organizations')
    OrganizationClass = Organization


class File(imscp.File):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'file')


class Dependency(imscp.Dependency):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'dependency')


class Resource(imscp.Resource):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'resource')
    MetadataClass = Metadata
    FileClass = File
    DependencyClass = Dependency


class Resources(imscp.Resources):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'resources')
    ResourceClass = Resource


class Manifest(imscp.Manifest):
    XMLNAME = (IMSCC_CP_NAMESPACE, 'manifest')
    MetadataClass = Metadata
    OrganizationsClass = Organizations
    ResourcesClass = Resources
    ManifestClass = None

Manifest.ManifestClass = Manifest


class ManifestDocument(xmlns.XMLNSDocument):
    classMap = {}

    def __init__(self, **args):
        """"""
        xmlns.XMLNSDocument.__init__(self, **args)
        self.defaultNS = IMSCC_CP_NAMESPACE
        self.make_prefix(xsi.XMLSCHEMA_NAMESPACE, 'xsi')
        self.make_prefix(IMSCC_LOMMANIFEST_NAMESPACE, 'lomimscc')
        self.make_prefix(IMSCC_LOMRESOURCE_NAMESPACE, 'lom')
        schema_location = [IMSCC_CP_NAMESPACE, IMSCC_CP_SCHEMALOCATION,
                           IMSCC_LOMMANIFEST_NAMESPACE,
                           IMSCC_LOMMANIFEST_SCHEMALOCATION,
                           IMSCC_LOMRESOURCE_NAMESPACE,
                           IMSCC_LOMRESOURCE_SCHEMALOCATION]
        if isinstance(self.root, imscp.CPElement):
            self.root.set_attribute(
                (xsi.XMLSCHEMA_NAMESPACE, 'schemaLocation'),
                ' '.join(schema_location))

    def get_element_class(self, name):
        eclass = ManifestDocument.classMap.get(
            name, ManifestDocument.classMap.get((name[0], None),
                                                xmlns.XMLNSElement))
        return eclass

xmlns.map_class_elements(ManifestDocument.classMap, globals())
# xmlns.map_class_elements(ManifestDocument.classMap,imsmd)
# xmlns.map_class_elements(ManifestDocument.classMap,imsqti)
# Add other supported metadata schemas in here


class ContentPackage(imscp.ContentPackage):
    ManifestDocumentClass = ManifestDocument


class CommonCartridge(v1p0.CommonCartridge):
    ContentPackageClass = ContentPackage
