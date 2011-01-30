#! /usr/bin/env python
"""This module implements the IMS CP 1.2 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns

from types import StringTypes
from tempfile import mkdtemp
import os.path, urlparse, urllib, shutil
import zipfile

IMSCP_NAMESPACE="http://www.imsglobal.org/xsd/imscp_v1p1"
IMSCPX_NAMESPACE="http://www.imsglobal.org/xsd/imscp_extensionv1p2"

cp_file=(IMSCP_NAMESPACE,'file')
cp_manifest=(IMSCP_NAMESPACE,'manifest')
cp_organization=(IMSCP_NAMESPACE,'organization')
cp_organizations=(IMSCP_NAMESPACE,'organizations')
cp_resource=(IMSCP_NAMESPACE,'resource')
cp_resources=(IMSCP_NAMESPACE,'resources')

cp_identifier="identifier"
cp_href="href"
cp_type="type"


class CPException(Exception): pass
class CPFilenameError(Exception): pass
class CPManifestError(CPException): pass
class CPValidationError(CPException): pass
class CPZIPBeenThereError(Exception): pass
class CPZIPDirectorySizeError(CPException): pass
class CPZIPDuplicateFileError(CPException): pass
class CPZIPFilenameError(CPException): pass

class CPElement(xmlns.XMLNSElement):
	"""Basic element to represent all CP elements"""  
	def __init__(self,parent):
		xmlns.XMLNSElement.__init__(self,parent)
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
		
	def AddChild(self,child):
		if isinstance(child,CPFile):
			CPElement.AddChild(self,child)
		else:
			# ignore the rest for now
			pass
			
class CPFile(CPElement):
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.SetXMLName(cp_file)
		
	def GetHREF(self):
		return self.attrs.get(cp_href,None)
		
	def SetHREF(self,href):
		CPElement.SetAttribute(self,cp_href,href)
				
	
class CPDocument(xmlns.XMLNSDocument):
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,**args)
		self.defaultNS=IMSCP_NAMESPACE

	def GetElementClass(self,name):
		return CPDocument.classMap.get(name,CPDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	classMap={
		cp_file:CPFile,
		cp_manifest:CPManifest,
		cp_organizations:CPOrganizations,
		cp_organization:CPOrganization,
		cp_resources:CPResources,
		cp_resource:CPResource
		}


class ContentPackage:
	def __init__(self,dPath=None):
		self.tempDir=False
		if dPath is None:
			self.dPath=mkdtemp('.d','imscpv1p2-')
			self.tempDir=True
		else:
			self.dPath=os.path.abspath(dPath)
			if os.path.isdir(self.dPath):
				# existing directory
				pass
			elif os.path.exists(self.dPath):
				# is this a zip archive?
				if zipfile.is_zipfile(self.dPath):
					self.ExpandZip(self.dPath)
				else:
					# anything else must be a manifest file
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
		self.RebuildFileTable()
	
	def GetFileTable(self):
		return self.fileTable
		
	def RebuildFileTable(self):
		self.fileTable={}
		beenThere={}
		for f in os.listdir(self.dPath):
			if os.path.normcase(f)=='imsmanifest.xml':
				continue
			self.FileScanner(f,beenThere)
		# Now scan the manifest and identify which file objects refer to which files
		for r in self.manifest.rootElement.GetResources().children:
			for f in r.children:
				url=urlparse.urlsplit(f.ResolveURI(f.GetHREF()))
				if url.scheme=='file' and url.netloc=='':
					relPath=[]
					fPath=urllib.url2pathname(url.path)
					while fPath!=self.dPath:
						fPath,tail=os.path.split(fPath)
						if not fPath or not tail:
							# We've gone as far as we can, fail!
							raise CPFilepathError(url.path)
						relPath[0:0]=[tail]
					relPath=os.path.normcase(os.path.join(*relPath))
					if self.fileTable.has_key(relPath):
						self.fileTable[relPath].append(f)
					else:
						self.fileTable[relPath]=[f]
					
	def FileScanner(self,fPath,beenThere):
		fullPath=os.path.join(self.dPath,fPath)
		rFullPath=os.path.realpath(fullPath)
		if beenThere.has_key(rFullPath):
			raise CPPackageBeenThereError(rFullPath)
		beenThere[rFullPath]=True
		if os.path.isdir(fullPath):
			for f in os.listdir(fullPath):
				self.FileScanner(os.path.join(fPath,f),beenThere)
		elif os.path.isfile(fullPath):
			self.fileTable[os.path.normcase(fPath)]=[]
		else: # skip non-regular files.
			pass
						
	def ExpandZip(self,zPath):
		self.dPath=mkdtemp('.d','imscpv1p2-')
		self.tempDir=True
		zf=zipfile.ZipFile(zPath)
		try:
			for zfi in zf.infolist():
				path=self.dPath
				for pathSeg in zfi.filename.split('/'):
					# The current path will need to be a directory
					if not os.path.isdir(path):
						os.mkdir(path)
					path=os.path.normpath(os.path.join(path,pathSeg))
					if not path.startswith(self.dPath):
						raise CPZIPFilenameError(zfi.filename)
				if os.path.isdir(path):
					if zfi.file_size>0:
						raise CPZIPDirectorySizeError("%s has size %i"%(zfi.filename,zfi.file_size))
				elif os.path.exists(path):
					# Duplicate entries in the zip file
					raise CPZIPDuplicateFileError(zfi.filename)
				else:
					f=open(path,'wb')
					f.write(zf.read(zfi.filename))
					f.close()
		finally:
			zf.close()
	
	def ExportToPIF(self,zPath):
		zf=zipfile.ZipFile(zPath,'w')
		base=''
		beenThere={}
		try:
			for f in os.listdir(self.dPath):
				self.AddToZip(os.path.join(self.dPath,f),zf,base,beenThere)
		finally:
			zf.close()
		
	def AddToZip(self,fPath,zf,zbase,beenThere):
		rfName=os.path.realpath(fPath)
		if beenThere.has_key(rfName):
			raise CPZIPBeenThereError(fPath)
		beenThere[rfName]=True
		fName=os.path.split(fPath)[1]
		zpath=zbase+fName.replace('/',':')
		if os.path.isdir(fPath):
			zpath+='/'
			zf.writestr(zpath,'')
			for f in os.listdir(fPath):
				self.AddToZip(os.path.join(fPath,f),zf,zpath,beenThere)
		elif os.path.isfile(fPath):
			zf.write(fPath,zpath)
		else: # skip non-regular files.
			pass
				
	def CPResource(self,identifier,type):
		resources=self.manifest.rootElement.GetResources()
		r=CPResource(resources)
		r.SetIdentifier(identifier)
		r.SetType(type)
		self.manifest.rootElement.resources.AddChild(r)
		return r

	def Close(self):
		self.manifest=None
		self.fileTable={}
		if self.tempDir:
			shutil.rmtree(self.dPath,True)
			self.dPath=None
