#! /usr/bin/env python
"""This module implements the IMS CP 1.2 specification defined by IMS GLC
"""

import pyslet.xml20081126 as xml

from types import StringTypes
from tempfile import mkdtemp
import os.path, urllib

IMSCP_NAMESPACE="http://www.imsglobal.org/xsd/imscp_v1p1"
IMSCPX_NAMESPACE="http://www.imsglobal.org/xsd/imscp_extensionv1p2"

cp_manifest=(IMSCP_NAMESPACE,'manifest')
cp_organization=(IMSCP_NAMESPACE,'organization')
cp_organizations=(IMSCP_NAMESPACE,'organizations')
cp_resource=(IMSCP_NAMESPACE,'resource')
cp_resources=(IMSCP_NAMESPACE,'resources')

cp_identifier="identifier"
cp_type="type"


class CPException(Exception): pass
class CPManifestError(CPException): pass
class CPValidationError(CPException): pass

class CPElement(xml.XMLElement):
	"""Basic element to represent all CP elements"""  
	def __init__(self,parent):
		xml.XMLElement.__init__(self,parent)
		self.SetXMLName((IMSCP_NAMESPACE,None))


class CPManifest(CPElement):
	ID=cp_identifier
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.SetXMLName(cp_manifest)
		self.organizations=CPOrganizations(self)
		self.resources=CPResources(self)

	def GetIdentifier(self):
		return self.attrs.get(cp_identifier,None)
		
	def SetIdentifier(self,identifier):
		CPElement.SetAttribute(self,cp_identifier,identifier)
		
	def GetOrganizations(self):
		return self.organizations
		
	def GetMetadata(self):
		return None
		
	def GetResources(self):
		return self.resources

	def AddChild(self,child):
		if isinstance(child,CPResources):
			self.resources=child
		else:
			CPElement.AddChild(self,child)


class CPOrganizations(CPElement):
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.SetXMLName(cp_organizations)
		
	def AddChild(self,child):
		if isinstance(child,CPOrganization):
			CPElement.AddChild(self,child)
		elif type(child) in StringTypes:
			if child.strip():
				raise CPValidationError
		else:
			raise CPValidationError

class CPOrganization(CPElement):
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.SetXMLName(cp_organization)
		

class CPResources(CPElement):
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.SetXMLName(cp_resources)
		
	def AddChild(self,child):
		if isinstance(child,CPResource):
			CPElement.AddChild(self,child)
		elif type(child) in StringTypes:
			if child.strip():
				raise CPValidationError
		else:
			raise CPValidationError


class CPResource(CPElement):
	ID=cp_identifier

	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.SetXMLName(cp_resource)
		
	def GetIdentifier(self):
		return self.attrs.get(cp_identifier,None)
		
	def SetIdentifier(self,identifier):
		CPElement.SetAttribute(self,cp_identifier,identifier)
		
	def GetType(self):
		return self.attrs.get(cp_type,None)
		
	def SetType(self,type):
		CPElement.SetAttribute(self,cp_type,type)
		
	
class CPDocument(xml.XMLDocument):
	def __init__(self,**args):
		""""""
		xml.XMLDocument.__init__(self,**args)
		self.defaultNS=IMSCP_NAMESPACE

	def GetElementClass(self,name):
		return CPDocument.classMap.get(name,CPDocument.classMap.get((name[0],None),xml.XMLElement))

	classMap={
		cp_manifest:CPManifest,
		cp_organizations:CPOrganizations,
		cp_organization:CPOrganization,
		cp_resources:CPResources,
		cp_resource:CPResource
		}


class ContentPackage:
	def __init__(self,dPath=None):
		if dPath is None:
			self.dPath=mkdtemp('.d','imscpv1p2-')
		else:
			self.dPath=os.path.abspath(dPath)
			if os.path.isdir(self.dPath):
				# existing directory
				pass
			elif os.path.exists(self.dPath):
				# anything other than a directory should be a manifest file
				self.dPath,mPath=os.path.split(self.dPath)
				if os.path.normcase(mPath)!='imsmanifest.xml':
					raise CPManifestError("%s must be named imsmanifest.xml"%mPath)
			else:
				os.mkdir(self.dPath)
		mPath=os.path.join(self.dPath,'imsmanifest.xml')
		if os.path.exists(mPath):
			self.manifest=CPDocument(baseURI=urllib.pathname2url(mPath))
			self.manifest.Read()
			if not isinstance(self.manifest.rootElement,CPManifest):
				raise CPManifestError("%s not a manifest file, found %s::%s "%
					(mPath,self.manifest.rootElement.ns,self.manifest.rootElement.xmlname))
		else:
			self.manifest=CPDocument(root=CPManifest, baseURI=urllib.pathname2url(mPath))
			self.manifest.rootElement.SetIdentifier(self.manifest.GetUniqueID('manifest'))
			self.manifest.Create()
	
	def CPResource(self,identifier,type):
		resources=self.manifest.rootElement.GetResources()
		r=CPResource(resources)
		r.SetIdentifier(identifier)
		r.SetType(type)
		self.manifest.rootElement.resources.AddChild(r)
		return r

