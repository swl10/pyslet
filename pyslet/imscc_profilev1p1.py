#! /usr/bin/env python
"""This module implements test to check against the IMSCC Profile 1.1 specification defined by IMS GLC"""

from types import StringTypes
import string

import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.imscpv1p2 as imscp
import pyslet.imscc_profilev1p0 as v1p0

IMSCC_CP_NAMESPACE="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"
IMSCC_CP_SCHEMALOCATION="http://www.imsglobal.org/profile/cc/ccv1p2/ccv1p2_imscp_v1p2_v1p0.xsd"

IMSCC_LOMMANIFEST_NAMESPACE="http://ltsc.ieee.org/xsd/imsccv1p2/LOM/manifest"
IMSCC_LOMMANIFEST_SCHEMALOCATION="http://www.imsglobal.org/profile/cc/ccv1p2/LOM/ccv1p2_lommanifest_v1p0.xsd"

IMSCC_LOMRESOURCE_NAMESPACE="http://ltsc.ieee.org/xsd/imsccv1p2/LOM/resource"
IMSCC_LOMRESOURCE_SCHEMALOCATION="http://www.imsglobal.org/profile/cc/ccv1p2/LOM/ccv1p2_lomresource_v1p0.xsd"

class CCCPDocument(xmlns.XMLNSDocument):
	classMap={}

	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,**args)
		self.defaultNS=IMSCC_CP_NAMESPACE
		self.MakePrefix(xsi.XMLSCHEMA_NAMESPACE,'xsi')
		self.MakePrefix(IMSCC_LOMMANIFEST_NAMESPACE,'lomimscc')
		self.MakePrefix(IMSCC_LOMRESOURCE_NAMESPACE,'lom')
		schemaLocation=[IMSCC_CP_NAMESPACE,IMSCC_CP_SCHEMALOCATION,
			IMSCC_LOMMANIFEST_NAMESPACE,IMSCC_LOMMANIFEST_SCHEMALOCATION,
			IMSCC_LOMRESOURCE_NAMESPACE,IMSCC_LOMRESOURCE_SCHEMALOCATION]
		if isinstance(self.root,imscp.CPElement):
			self.root.SetAttribute((xsi.XMLSCHEMA_NAMESPACE,'schemaLocation'),string.join(schemaLocation,' '))

	def GetElementClass(self,name):
		eClass=CCCPDocument.classMap.get(name,CCCPDocument.classMap.get((name[0],None),xmlns.XMLNSElement))
		return eClass
	
class ContentPackage(imscp.ContentPackage):
	CPDocumentClass=CCCPDocument

class CommonCartridge(v1p0.CommonCartridge):
	ContentPackageClass=ContentPackage

class Schema(imscp.Schema):
	XMLNAME=(IMSCC_CP_NAMESPACE,'schema')
	
class SchemaVersion(imscp.SchemaVersion):
	XMLNAME=(IMSCC_CP_NAMESPACE,'schemaversion')
	
class Metadata(imscp.Metadata):
	XMLNAME=(IMSCC_CP_NAMESPACE,'metadata')
	SchemaClass=Schema
	SchemaVersionClass=SchemaVersion

class Organization(imscp.Organization):
	XMLNAME=(IMSCC_CP_NAMESPACE,'organization')
			
class Organizations(imscp.Organizations):
	XMLNAME=(IMSCC_CP_NAMESPACE,'organizations')	
	OrganizationClass=Organization

class Resource(imscp.Resource):
	XMLNAME=(IMSCC_CP_NAMESPACE,'resource')
	MetadataClass=Metadata

class Manifest(imscp.Manifest):
	XMLNAME=(IMSCC_CP_NAMESPACE,'manifest')
	MetadataClass=Metadata
	OrganizationsClass=Organizations
	ManifestClass=None

Manifest.ManifestClass=Manifest

xmlns.MapClassElements(CCCPDocument.classMap,globals())
# xmlns.MapClassElements(CCCPDocument.classMap,imsmd)
# xmlns.MapClassElements(CCCPDocument.classMap,imsqti)
# Add other supported metadata schemas in here


