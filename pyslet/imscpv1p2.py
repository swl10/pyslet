#! /usr/bin/env python
"""This module implements the IMS CP 1.2 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.imsmdv1p2p1 as imsmd
import pyslet.imsqtiv2p1 as imsqti
import pyslet.rfc2396 as uri

from types import StringTypes
from tempfile import mkdtemp
import os, os.path, shutil
import string,re, random
import zipfile

IMSCP_NAMESPACE="http://www.imsglobal.org/xsd/imscp_v1p1"
IMSCP_SCHEMALOCATION="http://www.imsglobal.org/xsd/imscp_v1p1.xsd"
IMSCPX_NAMESPACE="http://www.imsglobal.org/xsd/imscp_extensionv1p2"

IGNOREFILES_RE="\\..*"

class CPException(Exception): pass
class CPFilePathError(Exception): pass
class CPFileTypeError(Exception): pass
class CPManifestError(CPException): pass
class CPProtocolError(CPException): pass
class CPValidationError(CPException): pass
class CPZIPBeenThereError(Exception): pass
class CPZIPDirectorySizeError(CPException): pass
class CPZIPDuplicateFileError(CPException): pass
class CPZIPFilenameError(CPException): pass

class CPElement(xmlns.XMLNSElement):
	"""Basic element to represent all CP elements"""
	pass


def PathInPath(childPath, parentPath):
	"""Returns childPath expressed relative to parentPath
	
	Both paths are normalized to remove any navigational segments, the resulting
	path will not contain these either.

	If childPath is not contained in parentPath then None is returned.

	If childPath and parentPath are equal an empty string is returned."""
	relPath=[]
	childPath=os.path.normpath(childPath)
	parentPath=os.path.normpath(parentPath)
	while os.path.normcase(childPath)!=os.path.normcase(parentPath):
		childPath,tail=os.path.split(childPath)
		if not childPath or not tail:
			# We've gone as far as we can, fail!
			return None
		relPath[0:0]=[tail]
	if relPath:
		return os.path.join(*relPath)
	else:
		return ''
	
class CPManifest(CPElement):
	ID="identifier"
	XMLNAME=(IMSCP_NAMESPACE,'manifest')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.metadata=None
		self.organizations=CPOrganizations(self)
		self.resources=CPResources(self)
		self.childManifests=[]
	
	def GetChildren(self):
		children=[]
		if self.metadata:
			children.append(self.metadata)
		children.append(self.organizations)
		children.append(self.resources)
		return children+self.childManifests+CPElement.GetChildren(self)

	def CPMetadata(self):
		"""Factory method to create the metadata object if necessary.
		
		If the metadata object already exists then it is returned instead"""
		if not self.metadata:
			self.metadata=CPMetadata(self)
		return self.metadata

	def CPOrganizations(self):
		return self.organizations
	
	def CPResources(self):
		return self.resources

	def CPManifest(self):
		child=CPManifest(self)
		self.childManifests.append(child)
		return child

		
class CPSchema(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'schema')
	
class CPSchemaVersion(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'schemaversion')
	
class CPMetadata(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'metadata')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.schema=None
		self.schemaVersion=None

	def GetChildren(self):
		children=[]
		if self.schema:
			children.append(self.schema)
		if self.schemaVersion:
			children.append(self.schemaVersion)
		return children+CPElement.GetChildren(self)

	def CPSchema(self):
		if not self.schema:
			self.schema=CPSchema(self)
		return self.schema
		
	def CPSchemaVersion(self):
		if not self.schemaVersion:
			self.schemaVersion=CPSchemaVersion(self)
		return self.schemaVersion
		
	

class CPOrganizations(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'organizations')
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.list=[]
	
	def GetChildren(self):
		return self.list+CPElement.GetChildren(self)
	
	def CPOrganization(self):
		child=CPOrganization(self)
		self.list.append(child)
		return child
		

class CPOrganization(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'organization')
			

class CPResources(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'resources')
	XMLCONTENT=xmlns.XMLElementContent

	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.list=[]
	
	def GetChildren(self):
		return self.list+CPElement.GetChildren(self)
	
	def CPResource(self):
		child=CPResource(self)
		self.list.append(child)
		return child


class CPResource(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'resource')
	ID="identifier"
	XMLCONTENT=xmlns.XMLElementContent
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.type=None
		self.href=None
		self.metadata=None
		self.fileList=[]
		self.dependencies=[]
	
	def GetAttributes(self):
		attrs=CPElement.GetAttributes(self)
		if self.type:
			attrs['type']=self.type
		if self.href:
			attrs['href']=self.href
		return attrs
		
	def Set_type(self,value):
		self.type=value
		
	def Set_href(self,href):
		self.href=href
	
	def GetEntryPoint(self):
		"""Returns the CPFile object that is identified as the entry point.
		
		If there is no entry point, or no CPFile object with a matching
		href, then None is returned."""
		href=self.href
		if href:
			href=self.ResolveURI(href)
			for f in self.fileList:
				fHREF=f.href
				if fHREF:
					fHREF=f.ResolveURI(fHREF)
					if href==fHREF:
						return f
		return None

	def SetEntryPoint(self,f):
		"""Set's the CPFile object that is identified as the entry point.
		
		The CPFile must already exist and be associated with the resource."""
		# We resolve and recalculate just in case xml:base lurks on this file
		href=self.RelativeURI(f.ResolveURI(f.href))
		self.href=href

	def GetChildren(self):
		children=[]
		if self.metadata:
			children.append(self.metadata)
		return children+self.fileList+self.dependencies+CPElement.GetChildren(self)

	def CPMetadata(self):
		"""Factory method to create the metadata object if necessary.
		
		If the metadata object already exists then it is returned instead"""
		if not self.metadata:
			self.metadata=CPMetadata(self)
		return self.metadata
				
	def CPFile(self):
		child=CPFile(self)
		self.fileList.append(child)
		return child
	
	def DeleteFile(self,f):
		index=self.fileList.index(f)
		f.DetachFromDocument()
		f.parent=None
		del self.fileList[index]
		
	def CPDependency(self):
		child=CPDependency(self)
		self.dependencies.append(child)
		return child
		
	def DeleteDependency(self,d):
		index=self.dependencies.index(d)
		d.DetachFromDocument()
		d.parent=None
		del self.dependencies[index]
		
		
class CPDependency(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'dependency')

	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.identifierref=None
		
	def GetAttributes(self):
		attrs=CPElement.GetAttributes(self)
		if self.identifierref:
			attrs['identifierref']=self.identifierref
		return attrs

	def Set_identifierref(self,value):
		self.identifierref=value

			
class CPFile(CPElement):
	XMLNAME=(IMSCP_NAMESPACE,'file')

	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.href=None
		
	def GetAttributes(self):
		attrs=CPElement.GetAttributes(self)
		if self.href:
			attrs['href']=self.href
		return attrs

	def Set_href(self,href):
		self.href=href
				
	def PackagePath(self,cp):
		"""Returns the normalized file path relative to the root of the content
		package.

		If the HREF does not point to a local file then None is returned. 
		Otherwise, this function calculates an absolute path to the file and
		then calls the content package's PackagePath method."""
		url=uri.URIFactory.URI(self.ResolveURI(self.href))
		if not isinstance(url,uri.FileURL):
			return None
		return cp.PackagePath(url.GetPathname())

	
class CPDocument(xmlns.XMLNSDocument):
	classMap={}

	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,**args)
		self.defaultNS=IMSCP_NAMESPACE
		self.SetNSPrefix(xsi.XMLSCHEMA_NAMESPACE,'xsi')
		self.SetNSPrefix(imsmd.IMSLRM_NAMESPACE,'imsmd')
		self.SetNSPrefix(imsqti.IMSQTI_NAMESPACE,'imsqti')
		schemaLocation=[IMSCP_NAMESPACE,IMSCP_SCHEMALOCATION,
			imsmd.IMSLRM_NAMESPACE,imsmd.IMSLRM_SCHEMALOCATION,
			imsqti.IMSQTI_NAMESPACE,imsqti.IMSQTI_SCHEMALOCATION]
		if isinstance(self.root,CPElement):
			self.root.SetAttribute((xsi.XMLSCHEMA_NAMESPACE,'schemaLocation'),string.join(schemaLocation,' '))

	def GetElementClass(self,name):
		eClass=CPDocument.classMap.get(name,CPDocument.classMap.get((name[0],None),xmlns.XMLNSElement))
		return eClass
	
xmlns.MapClassElements(CPDocument.classMap,globals())
xmlns.MapClassElements(CPDocument.classMap,imsmd)
xmlns.MapClassElements(CPDocument.classMap,imsqti)
# Add other supported metadata schemas in here


class ContentPackage:
	def __init__(self,dPath=None):
		self.tempDir=False
		errorFlag=True
		try:
			if dPath is None:
				self.dPath=mkdtemp('.d','imscpv1p2-')
				self.tempDir=True
				self.packageName='imscp'
			else:
				self.dPath=os.path.abspath(dPath)
				head,tail=os.path.split(self.dPath)
				self.packageName=tail
				if os.path.isdir(self.dPath):
					# existing directory
					pass
				elif os.path.exists(self.dPath):
					# is this a zip archive?
					if zipfile.is_zipfile(self.dPath):					
						name,ext=os.path.splitext(tail)
						if ext.lower()==".zip":
							self.packageName=name
						self.ExpandZip(self.dPath)
					else:
						# anything else must be a manifest file
						self.dPath=head;mPath=tail
						head,tail=os.path.split(self.dPath)
						if os.path.normcase(mPath)!='imsmanifest.xml':
							raise CPManifestError("%s must be named imsmanifest.xml"%mPath)
						self.packageName=tail
				else:
					os.mkdir(self.dPath)
			mPath=os.path.join(self.dPath,'imsmanifest.xml')
			if os.path.exists(mPath):
				self.manifest=CPDocument(baseURI=str(uri.URIFactory.URLFromPathname(mPath)))				
				self.manifest.Read()
				if not isinstance(self.manifest.root,CPManifest):
					raise CPManifestError("%s not a manifest file, found %s::%s "%
						(mPath,self.manifest.root.ns,self.manifest.root.xmlname))
			else:
				self.manifest=CPDocument(root=CPManifest, 
					baseURI=str(uri.URIFactory.URLFromPathname(mPath)))
				self.manifest.root.SetID(self.manifest.GetUniqueID('manifest'))
				md=self.manifest.root.CPMetadata()
				md.CPSchema().SetValue("IMS Content")
				md.CPSchemaVersion().SetValue("1.2")
				self.manifest.Create()
			self.SetIgnoreFiles(IGNOREFILES_RE)
			self.RebuildFileTable()
			errorFlag=False
		finally:
			if errorFlag:
				self.Close()
	
	def SetIgnoreFiles(self,ignoreFiles):
		self.ignoreFiles=re.compile(ignoreFiles)
	
	def IgnoreFile(self,f):
		match=self.ignoreFiles.match(f)
		if match:
			return len(f)==match.end()
		else:
			return False
		
	def RebuildFileTable(self):
		self.fileTable={}
		beenThere={}
		for f in os.listdir(self.dPath):
			if self.IgnoreFile(f):
				continue
			if os.path.normcase(f)=='imsmanifest.xml':
				continue
			self.FileScanner(f,beenThere)
		# Now scan the manifest and identify which file objects refer to which files
		for r in self.manifest.root.resources.list:
			for f in r.fileList:
				fPath=f.PackagePath(self)
				if fPath is None:
					continue
				if self.fileTable.has_key(fPath):
					self.fileTable[fPath].append(f)
				else:
					self.fileTable[fPath]=[f]
					
	def FileScanner(self,fPath,beenThere):
		fullPath=os.path.join(self.dPath,fPath)
		rFullPath=os.path.realpath(fullPath)
		if beenThere.has_key(rFullPath):
			raise CPPackageBeenThereError(rFullPath)
		beenThere[rFullPath]=True
		if os.path.isdir(fullPath):
			for f in os.listdir(fullPath):
				if self.IgnoreFile(f):
					continue
				self.FileScanner(os.path.join(fPath,f),beenThere)
		elif os.path.isfile(fullPath):
			self.fileTable[os.path.normcase(fPath)]=[]
		else: # skip non-regular files.
			pass
	
	def PackagePath(self,fPath):
		"""Converts an absolute file path into a canonical package-relative path
		
		Returns None if fPath is not inside the package."""
		relPath=[]
		while fPath!=self.dPath:
			fPath,tail=os.path.split(fPath)
			if not fPath or not tail:
				# We've gone as far as we can, fail!
				return None
			relPath[0:0]=[tail]
		return os.path.normcase(os.path.join(*relPath))
		
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
					if self.PackagePath(path) is None:
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
				if self.IgnoreFile(f):
					continue
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
				if self.IgnoreFile(f):
					continue
				self.AddToZip(os.path.join(fPath,f),zf,zpath,beenThere)
		elif os.path.isfile(fPath):
			zf.write(fPath,zpath)
		else: # skip non-regular files.
			pass
	
	def GetUniqueFile(self,suggestedPath):
		"""Returns a unique file path suitable for creating a new file in the package.
		
		suggestedPath is used to provide a suggested path for the file.  This
		may be relative (to the root and manifest) or absolute but it must
		resolve to an file (potentially) in the package.

		The return result is always normalized and returned relative to the
		package root.
		"""
		fPath=os.path.join(self.dPath,suggestedPath)
		fPath=PathInPath(fPath,self.dPath)
		if fPath is None:
			raise CPFilePathError(suggestedPath)
		fPath=os.path.normcase(fPath)
		# Now we can try and make it unique
		pathStr=fPath
		pathExtra=0
		while self.fileTable.has_key(pathStr):
			if not pathExtra:
				pathExtra=random.randint(0,0xFFFF)
			fName,fExt=os.path.splitext(fPath)
			pathStr='%s_%X%s'%(fName,pathExtra,fExt)
			pathExtra=pathExtra+1
		# we have the path string
		return pathStr
	
	def CPFile(self,resource,href):
		"""Creates a new CPFile attached to a resource, pointing to href

		href is expressed relative to resource, e.g., using
		resource.RelativeURI"""
		fURL=uri.URIFactory.URI(resource.ResolveURI(href))
		if not isinstance(fURL,uri.FileURL):
			# Not a local file
			r=resource.CPFile()
			r.Set_href(href)		
		else:
			fullPath=fURL.GetPathname()
			head,tail=os.path.split(fullPath)
			if self.IgnoreFile(tail):
				raise CPFilePathError(fullPath)
			relPath=PathInPath(fullPath,self.dPath)
			if relPath is None or relPath.lower=='imsmanifest.xml':
				raise CPFilePathError(url.path)
			# normalise the case ready to put in the file table
			relPath=os.path.normcase(relPath)
			f=resource.CPFile()
			f.Set_href(href)
			if not self.fileTable.has_key(relPath):
				self.fileTable[relPath]=[f]
			else:
				self.fileTable[relPath].append(f)
		return f
		
	def DeleteFile(self,href):
		"""Removes the file at href from the file system
		
		This method also removes any file references to it from resources in the
		manifest. href is given relative to the package root (i.e., ignoring any
		xml:base overrides in the manifest element).  File references are only
		removed if they point to the same file after any xml:base references
		have been taken into account of course.
		
		CPFileTypeError is raised if the file is not a regular file

		CPFilePathError is raised if the file is an IgnoreFile, the manifest
		itself or outside of the content package.

		CPProtocolError is raised if the content package is not in the local
		file system."""
		baser=self
		baseURI=self.manifest.GetBase()
		base=uri.URIFactory.URI(baseURI)
		fURL=uri.URIFactory.URI(href).Resolve(base)
		if not isinstance(fURL,uri.FileURL):
			# We cannot delete non-file objects (though in future
			# we should support HTTP DELETE)
			return CPProtocolError(str(fURL))
		fullPath=fURL.GetPathname()
		if not os.path.isfile(fullPath):
			raise CPFileTypeError(fullPath)
		head,tail=os.path.split(fullPath)
		if self.IgnoreFile(tail):
			raise CPFilePathError(fullPath)
		relPath=PathInPath(fullPath,self.dPath)
		if relPath is None or relPath.lower=='imsmanifest.xml':
			raise CPFilePathError(fullPath)
		# normalise the case ready for comparisons
		relPath=os.path.normcase(relPath)
		for r in self.manifest.root.resources.list:
			delList=[]
			for f in r.fileList:
				# Does f point to the same file?
				if f.PackagePath(self)==relPath:
					delList.append(f)
			for f in delList:
				r.DeleteFile(f)
		# Now there are no more references, safe to remove the file itself
		os.remove(fullPath)
		if self.fileTable.has_key(relPath):
			del self.fileTable[relPath]
		
	def GetPackageName(self):
		"""Returns a name for the package

		The name is determined by the method used to create the CPPackage object.
		The purpose is to return a name that would be intuitive to the user if it
		were to be used as the name of the package directory or the stem of a file
		name when exporting to a PIF file.
		
		Note that the name is returned as a unicode string suitable for showing to
		the user and may need to be encoded before being used in file path operations."""
		return unicode(self.packageName,'utf-8')
		
	def Close(self):
		self.manifest=None
		self.fileTable={}
		if self.tempDir:
			shutil.rmtree(self.dPath,True)
			self.dPath=None
