#! /usr/bin/env python
"""This module implements the IMS CP 1.2 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.imsmdv1p2p1 as imsmd
import pyslet.imsqtiv2p1 as imsqti
import pyslet.rfc2396 as uri

from types import StringTypes, StringType, UnicodeType
from tempfile import mkdtemp
import os, os.path, shutil, sys
import string,re, random
import zipfile

IMSCP_NAMESPACE="http://www.imsglobal.org/xsd/imscp_v1p1"				#:	String constant for the main namespace
IMSCP_SCHEMALOCATION="http://www.imsglobal.org/xsd/imscp_v1p1.xsd"		#:	String constant for the official schema location
IMSCPX_NAMESPACE="http://www.imsglobal.org/xsd/imscp_extensionv1p2"		#:	String constant for the 1.2 extension elements' namespace

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
	"""Base class for all elements defined by the Content Packaging specification."""
	pass


def PathInPath(childPath, parentPath):
	"""Utility function that returns childPath expressed relative to parentPath
	
	This function processes file system paths, not the path components of URI.
	
	Both paths are normalized to remove any redundant navigational segments
	before any processing, the resulting path will not contain these either.

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

	
class Schema(CPElement):
	"""Represents the schema element."""
	XMLNAME=(IMSCP_NAMESPACE,'schema')
	
class SchemaVersion(CPElement):
	"""Represents the schemaversion element."""
	XMLNAME=(IMSCP_NAMESPACE,'schemaversion')
	
class Metadata(CPElement):
	"""Represents the Metadata element."""
	XMLNAME=(IMSCP_NAMESPACE,'metadata')
	XMLCONTENT=xmlns.ElementContent
	
	SchemaClass=Schema					#: the default class to represent the schema element
	SchemaVersionClass=SchemaVersion	#: the default class to represent the schemaVersion element
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.Schema=None				#: the optional schema element 
		self.SchemaVersion=None			#: the optional schemaversion element

	def GetChildren(self):
		children=[]
		if self.Schema:
			children.append(self.Schema)
		if self.SchemaVersion:
			children.append(self.SchemaVersion)
		return children+CPElement.GetChildren(self)
	
	
class Organization(CPElement):
	"""Represents the organization element."""
	XMLNAME=(IMSCP_NAMESPACE,'organization')
			

class Organizations(CPElement):
	"""Represents the organizations element."""
	XMLNAME=(IMSCP_NAMESPACE,'organizations')
	XMLCONTENT=xmlns.ElementContent
	
	OrganizationClass=Organization		#: the default class to represent the organization element
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.Organization=[]			#: a list of organization elements
	
	def GetChildren(self):
		return self.Organization+CPElement.GetChildren(self)
			

class File(CPElement):
	"""Represents the file element."""
	XMLNAME=(IMSCP_NAMESPACE,'file')
	XMLATTR_href=('href',uri.URIFactory.URI,str)

	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.href=None					#: the href used to locate the file object
		
	def PackagePath(self,cp):
		"""Returns the normalized file path relative to the root of the content package, *cp*.

		If the href does not point to a local file then None is returned.
		Otherwise, this function calculates an absolute path to the file and
		then calls the content package's :py:meth:`ContentPackage.PackagePath`
		method."""
		url=self.ResolveURI(self.href)
		if not isinstance(url,uri.FileURL):
			return None
		return cp.PackagePath(url.GetPathname())


class Dependency(CPElement):
	"""Represents the dependency element."""
	XMLNAME=(IMSCP_NAMESPACE,'dependency')
	XMLATTR_identifierref='identifierref'

	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.identifierref=None			#: the identifier of the resource in this dependency 
		
	
class Resource(CPElement):
	"""Represents the resource element."""
	XMLNAME=(IMSCP_NAMESPACE,'resource')
	ID=(xmlns.NO_NAMESPACE,"identifier")
	XMLATTR_href=('href',uri.URIFactory.URI,str)
	XMLATTR_type='type'
	XMLCONTENT=xmlns.ElementContent
	
	MetadataClass=Metadata				#: the default class to represent the metadata element
	FileClass=File						#: the default class to represent the file element
	DependencyClass=Dependency			#: the default class to represent the dependency element
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.type=None					#: the type of the resource
		self.href=None					#: the href pointing at the resource's entry point
		self.Metadata=None				#: the resource's optional metadata element
		self.File=[]					#: a list of file elements associated with the resource 
		self.Dependency=[]				#: a list of dependencies of this resource
	
	def GetEntryPoint(self):
		"""Returns the :py:class:`File` object that is identified as the entry point.
		
		If there is no entry point, or no :py:class:`File` object with a
		matching href, then None is returned."""
		href=self.href
		if href:
			href=self.ResolveURI(href)
			for f in self.File:
				fHREF=f.href
				if fHREF:
					fHREF=f.ResolveURI(fHREF)
					if href.Match(fHREF):
						return f
		return None

	def SetEntryPoint(self,f):
		"""Set's the :py:class:`File` object that is identified as the resource's entry point.
		
		The File must already exist and be associated with the resource."""
		# We resolve and recalculate just in case xml:base lurks on this file
		href=self.RelativeURI(f.ResolveURI(f.href))
		self.href=href

	def GetChildren(self):
		children=[]
		if self.Metadata:
			children.append(self.Metadata)
		return children+self.File+self.Dependency+CPElement.GetChildren(self)
	
	def DeleteFile(self,f):
		index=self.File.index(f)
		f.DetachFromDocument()
		f.parent=None
		del self.File[index]
		
	def DeleteDependency(self,d):
		index=self.Dependency.index(d)
		d.DetachFromDocument()
		d.parent=None
		del self.Dependency[index]
		
		
class Resources(CPElement):
	"""Represents the resources element."""
	XMLNAME=(IMSCP_NAMESPACE,'resources')
	XMLCONTENT=xmlns.ElementContent

	ResourceClass=Resource				#: the default class to represent the resource element
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.Resource=[]				#: the list of resources in the manifest
	
	def GetChildren(self):
		return self.Resource+CPElement.GetChildren(self)


class Manifest(CPElement):
	"""Represents the manifest element, the root element of the imsmanifest file."""
	ID=(xmlns.NO_NAMESPACE,"identifier")
	XMLNAME=(IMSCP_NAMESPACE,'manifest')
	XMLCONTENT=xmlns.ElementContent
	
	MetadataClass=Metadata				#: the default class to represent the metadata element
	OrganizationsClass=Organizations	#: the default class to represent the organizations element
	ResourcesClass=Resources			#: the default class to represent the resources element
	ManifestClass=None					#: the default class to represent child manifest elements
	
	def __init__(self,parent):
		CPElement.__init__(self,parent)
		self.Metadata=None									#: the manifest's metadata element
		self.Organizations=self.OrganizationsClass(self)	#: the organizations element
		self.Resources=self.ResourcesClass(self)			#: the resources element
		self.Manifest=[]									#: a list of child manifest elements
	
	def GetChildren(self):
		children=[]
		if self.Metadata:
			children.append(self.Metadata)
		children.append(self.Organizations)
		children.append(self.Resources)
		return children+self.Manifest+CPElement.GetChildren(self)

Manifest.ManifestClass=Manifest
		
			
class ManifestDocument(xmlns.XMLNSDocument):
	"""Represents the imsmanifest.xml file itself.
	
	Buildong on :py:class:`pyslet.xmlnames20091208.XMLNSDocument` this class is used
	for parsing and writing manifest files.
	
	The constructor defines three additional prefixes using
	:py:meth:`~pyslet.xmlnames20091208.XMLNSDocument.MakePrefix`, mapping xsi
	onto XML schema, imsmd onto the IMS LRM namespace and imsqti onto the IMS
	QTI 2.1 namespace.  It also adds a schemaLocation attribute.  The elements
	defined by the :py:mod:`pyslet.imsmdv1p2p1` and :py:mod:`pyslet.imsqtiv2p1`
	modules are added to the :py:attr:`classMap` to ensure that metadata from
	those schemas are bound to the special classes defined there."""

	classMap={}

	def __init__(self,**args):
		xmlns.XMLNSDocument.__init__(self,**args)
		self.defaultNS=IMSCP_NAMESPACE						#: the default namespace is set to :py:const:`IMSCP_NAMESPACE`
		self.MakePrefix(xsi.XMLSCHEMA_NAMESPACE,'xsi')
		self.MakePrefix(imsmd.IMSLRM_NAMESPACE,'imsmd')
		self.MakePrefix(imsqti.IMSQTI_NAMESPACE,'imsqti')
		schemaLocation=[IMSCP_NAMESPACE,IMSCP_SCHEMALOCATION,
			imsmd.IMSLRM_NAMESPACE,imsmd.IMSLRM_SCHEMALOCATION,
			imsqti.IMSQTI_NAMESPACE,imsqti.IMSQTI_SCHEMALOCATION]
		if isinstance(self.root,CPElement):
			self.root.SetAttribute((xsi.XMLSCHEMA_NAMESPACE,'schemaLocation'),string.join(schemaLocation,' '))

	def GetElementClass(self,name):
		"""Overrides :py:meth:`pyslet.xmlnames20091208.XMLNSDocument.GetElementClass` to look up name.
		
		The class contains a mapping from (namespace,element name) pairs to
		class objects representing the elements.  Any element not in the class
		map returns :py:meth:`~pyslet.xmlnames20091208.XMLNSElement` instead."""
		eClass=ManifestDocument.classMap.get(name,ManifestDocument.classMap.get((name[0],None),xmlns.XMLNSElement))
		return eClass
	
xmlns.MapClassElements(ManifestDocument.classMap,globals())
xmlns.MapClassElements(ManifestDocument.classMap,imsmd)
xmlns.MapClassElements(ManifestDocument.classMap,imsqti)
# Add other supported metadata schemas in here


class ContentPackage:
	"""Represents a content package.
	
	When constructed with no arguments a new package is created.  A temporary folder to hold the contents
	of the package is created and will not be cleaned up until the :py:meth:`Close` method is called.
	
	Alternatively, you can pass an operating system file path to a content package directory, to
	an imsmanifest.xml file or to a Package Interchange Format file.  In the latter case, the file
	is unzipped into a temporary folder to facilitate manipulation of the package contents.
	
	A new manifest file is created and written to the file system when creating
	a new package, or if it is missing from an existing package or directory."""
	
	ManifestDocumentClass=ManifestDocument		#: the default class for representing the Manifest file
	
	def __init__(self,dPath=None):
		self.tempDir=False
		errorFlag=True
		try:
			if dPath is None:
				self.dPath=mkdtemp('.d','imscpv1p2-')		#: the operating system path to the package's directory
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
				self.manifest=self.ManifestDocumentClass(baseURI=str(uri.URIFactory.URLFromPathname(mPath)))
				"""The :py:class:`ManifestDocument` object representing the imsmanifest.xml file.
				
				The file is read (or created) on construction."""
				self.manifest.Read()
				if not isinstance(self.manifest.root,Manifest):
					raise CPManifestError("%s not a manifest file, found %s::%s "%
						(mPath,self.manifest.root.ns,self.manifest.root.xmlname))
			else:
				self.manifest=self.ManifestDocumentClass(root=Manifest, 
					baseURI=str(uri.URIFactory.URLFromPathname(mPath)))
				self.manifest.root.SetID(self.manifest.GetUniqueID('manifest'))
				md=self.manifest.root.ChildElement(self.manifest.root.MetadataClass)
				md.ChildElement(md.SchemaClass).SetValue("IMS Content")
				md.ChildElement(md.SchemaVersionClass).SetValue("1.2")
				self.manifest.Create()
			self.SetIgnoreFiles(IGNOREFILES_RE)
			self.fileTable={}
			"""The fileTable is a dictionary that maps package relative file system paths
			to the :py:class:`File` objects that represent them in the manifest.
			
			It is possible for a file to be referenced multiple times (although
			dependencies were designed to take care of most cases it is still
			possible for two resources to share a physical file, or even for a
			resource to contain multiple references to the same file.)  Therefore,
			the dictionary values are lists of :py:class:`File` objects.
	
			If a file path maps to an empty list then a file exists in the package
			which is not referenced by any resource.  In some packages it is commone
			for auxiliary files such as supporting schemas to be included in
			packages without a corresponding :py:class:`File` object so an empty
			list does not indicate that the file can be removed safely.  These files
			are still included when packaging the content package for
			interchange.
			
			Finally, if a file referred to by a :py:class:`File` object in the
			manifest is missing an entry is still created in the fileTable.  You
			can walk the keys of the fileTable testing if each file exists to
			determine if some expected files are missing from the package."""
			self.RebuildFileTable()
			errorFlag=False
		finally:
			if errorFlag:
				self.Close()
	
	def SetIgnoreFiles(self,ignoreFiles):
		"""Sets the regular expression used to determine if a file should be ignored.
		
		Some operating systems and utilities create hidden files or other spurious data
		inside the content package directory.  For example, Apple's OS X creates .DS_Store
		files and the svn source control utility creates .svn directories.  The files shouldn't
		generally be included in exported packages as they may confuse the recipient (who
		may be using a system on which these files and directories are not hidden) and be
		deemed to violate the specification, not to mention adding unnecessarily to the size
		of the package and perhaps even leaking information unintentionally.
		
		To help avoid this type of problem the class uses a regular expression to determine
		if a file should be considered part of the package.  When listing directories, the
		names of the files found are compared against this regular expression and are ignored
		if they match.
		
		By default, the pattern is set to match all directories and files with
		names beginning '.' so you will not normally need to call this
		method."""
		self.ignoreFiles=re.compile(ignoreFiles)
	
	def IgnoreFile(self,f):
		"""Compares an operating system file or directory name against the pattern set by :py:meth:`SetIgnoreFiles`"""
		match=self.ignoreFiles.match(f)
		if match:
			return len(f)==match.end()
		else:
			return False
	
	def IgnoreFilePath(self,fPath):
		"""Compares an operating system file path against the pattern set by :py:meth:`SetIgnoreFiles`
		
		The path is normalised before comparison and any segments consisting of
		the string '..' are skipped.  The method returns True if any of the
		remaining path components matches the ignore pattern.  In other words,
		if the path describes a file that is is in a directory that should be
		ignored it will also be ignored.

		The path can be relative or absolute.  Relative paths are *not* made
		absolute prior to comparison so this method is not affected by the
		current directory, even if the current diretory would itself be
		ignored."""
		fPath=os.path.normpath(fPath)
		while True:
			head,tail=os.path.split(fPath)
			if tail and tail!=".." and self.IgnoreFile(tail):
				return True
			if not head or head==fPath:
				# No head left, or the path is unsplitable
				return False
			fPath=head
						
	def RebuildFileTable(self):
		"""Rescans the file system and manifest and rebuilds the :py:attr:`fileTable`."""
		self.fileTable={}
		beenThere={}
		for f in os.listdir(self.dPath):
			if self.IgnoreFile(f):
				continue
			if os.path.normcase(f)=='imsmanifest.xml':
				continue
			self.FileScanner(f,beenThere)
		# Now scan the manifest and identify which file objects refer to which files
		for r in self.manifest.root.Resources.Resource:
			for f in r.File:
				fPath=f.PackagePath(self)
				if fPath is None:
					continue
				if fPath in self.fileTable:
					self.fileTable[fPath].append(f)
				else:
					self.fileTable[fPath]=[f]
					
	def FileScanner(self,fPath,beenThere):
		fullPath=os.path.join(self.dPath,fPath)
		rFullPath=os.path.realpath(fullPath)
		if rFullPath in beenThere:
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
		if type(self.dPath) is StringType and os.path.supports_unicode_filenames:
			self.dPath=self.dPath.decode(sys.getfilesystemencoding())		
		self.tempDir=True
		zf=zipfile.ZipFile(zPath)
		try:
			for zfi in zf.infolist():
				path=self.dPath
				for pathSeg in zfi.filename.split('/'):
					# The current path will need to be a directory
					if not os.path.isdir(path):
						os.mkdir(path)
					pathSeg=unicode(pathSeg,'utf-8')
					if type(path) is StringType:
						pathSeg=pathSeg.encode(sys.getfilesystemencoding())
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
		"""Exports the content package, saving the zipped package in *zPath*
		
		*zPath* is overwritten by this operation.
		
		In order to make content packages more interoperable this method goes
		beyond the basic zip specification and ensures that pathnames are always
		UTF-8 encoded when added to the archive.  When creating instances of
		:py:class:`ContentPackage` from an existing archive the reverse
		transformation is performed.  When exchanging PIF files between systems
		with different native file path encodings, as indicated by the built-in
		python function sys.getfilesystemencoding(), encoding erros may
		occurr."""
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
		if rfName in beenThere:
			raise CPZIPBeenThereError(fPath)
		beenThere[rfName]=True
		fName=os.path.split(fPath)[1]
		zfName=fName.replace('/',':')
		if type(zfName) is StringType:
			zfName=zfName.decode(sys.getfilesystemencoding())
		zpath=zbase+zfName.encode('utf-8')
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
		resolve to a file (potentially) in the package.

		When suggestedPath is relative, it is forced to lower-case.  This is
		consistent with the behaviour of os.path.normcase on systems that are
		case insensitive.  The trouble with case insensitive file systems is
		that it may be impossible to unpack a content package created on a case
		sensitive system and store it on a case insenstive one.  By channelling
		all file storage through this method (and constructing any URIs *after*
		the file has been stored) the resulting packages will be more portable.

		If suggestedPath already corresponds to a file already in the package,
		or to a file already referred to in the manifest, then a random string
		is added to it while preserving the suggested extension in order to make
		it unique.

		The return result is always normalized and returned relative to the
		package root."""
		if os.path.isabs(suggestedPath):
			fPath=suggestedPath
		else:
			fPath=os.path.join(self.dPath,suggestedPath.lower())
		fPath=PathInPath(fPath,self.dPath)
		if fPath is None:
			raise CPFilePathError(suggestedPath)
		fPath=os.path.normcase(fPath)
		# Now we can try and make it unique
		pathStr=fPath
		pathExtra=0
		while pathStr in self.fileTable:
			if not pathExtra:
				pathExtra=random.randint(0,0xFFFF)
			fName,fExt=os.path.splitext(fPath)
			pathStr='%s_%X%s'%(fName,pathExtra,fExt)
			pathExtra=pathExtra+1
		# we have the path string
		return pathStr
	
	def File(self,resource,href):
		"""Returns a new :py:class:`File` object attached to *resource*

		*href* is the URI of the file expressed relative to the resource element
		in the manifest.  Although this is normally the same as the URI
		expressed relative to the package, a resource may have an xml:base
		attribute that alters the base for resolving relative URIs.

		*href* may of course be an absolute URI to an external resource.  If an
		absolute URI is given to a local file it must be located inside the
		package.
		
		Attempting to add a :py:class:`File` object representing the manifest
		file iteself will raise :py:class:`CPFilePathError`.
		
		The :py:attr:`fileTable` is updated automatically by this method."""
		fURL=resource.ResolveURI(href)
		if not isinstance(fURL,uri.FileURL):
			# Not a local file
			f=resource.ChildElement(resource.FileClass)
			f.href=href
		else:
			if href.IsAbsolute():
				href=uri.URIFactory.Relative(href,resource.ResolveBase())
			fullPath=fURL.GetPathname()
			head,tail=os.path.split(fullPath)
			if self.IgnoreFile(tail):
				raise CPFilePathError(fullPath)
			relPath=PathInPath(fullPath,self.dPath)
			if relPath is None or relPath.lower=='imsmanifest.xml':
				raise CPFilePathError(url.path)
			# normalise the case ready to put in the file table
			relPath=os.path.normcase(relPath)
			f=resource.ChildElement(resource.FileClass)
			f.href=href
			if not relPath in self.fileTable:
				self.fileTable[relPath]=[f]
			else:
				self.fileTable[relPath].append(f)
		return f
	
	
	def FileCopy(self,resource,srcURL):
		"""Returns a new :py:class:`File` object copied into the package from *srcURL*, attached to *resource*.
		
		The file is copied to the same directory as the resource's entry point
		or to the main package directory if the resource has no entry point.
		
		The :py:class:`File` object is actually created with the :py:meth:`File` method.
		
		Note that if srcURL points to a missing file then no file is copied to the package but the
		associated :py:class:`File` is still created.  It will point to a missing file."""
		srcPath=srcURL.GetPathname()
		# We need to create a new file object
		fStart=resource.GetEntryPoint()
		if fStart is None:
			basePath=self.dPath
		else:
			url=fStart.ResolveURI(fStart.href)
			if not isinstance(url,uri.FileURL):
				basePath=self.dPath
			else:
				basePath,tail=os.path.split(url.GetPathname())
		# now pick up the last component of src
		head,tail=os.path.split(srcPath)
		newSrcPath=self.GetUniqueFile(os.path.join(basePath,tail))
		newSrcPath=os.path.join(self.dPath,newSrcPath)
		newSrc=uri.URIFactory.URLFromPathname(newSrcPath)
		# Turn this file path into a relative URL in the context of the new resource
		href=resource.RelativeURI(newSrc)
		f=self.File(resource,href)
		dName,fName=os.path.split(newSrcPath)
		if not os.path.isdir(dName):
			os.makedirs(dName)
		if os.path.isfile(srcPath):
			shutil.copy(srcPath,newSrcPath)
		return f

	
	def DeleteFile(self,href):
		"""Removes the file at *href* from the file system
		
		This method also removes any file references to it from resources in the
		manifest. href may be given relative to the package root directory.  The
		entry in :py:attr:`fileTable` is also removed. 
				
		:py:class:`CPFileTypeError` is raised if the file is not a regular file

		:py:class:`CPFilePathError` is raised if the file is an
		:py:meth:`IgnoreFile`, the manifest itself or outside of the content
		package.

		:py:class:`CPProtocolError` is raised if the indicated file is not in
		the local file system."""
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
		for r in self.manifest.root.Resources.Resource:
			delList=[]
			for f in r.File:
				# Does f point to the same file?
				if f.PackagePath(self)==relPath:
					delList.append(f)
			for f in delList:
				r.DeleteFile(f)
		# Now there are no more references, safe to remove the file itself
		os.remove(fullPath)
		if relPath in self.fileTable:
			del self.fileTable[relPath]
		
	def GetPackageName(self):
		"""Returns a human readable name for the package

		The name is determined by the method used to create the object. The
		purpose is to return a name that would be intuitive to the user if it
		were to be used as the name of the package directory or the stem of a
		file name when exporting to a PIF file.
		
		Note that the name is returned as a unicode string suitable for showing
		to the user and may need to be encoded before being used in file path
		operations."""
		if type(self.packageName) is StringType:
			return unicode(self.packageName,'utf-8')
		else:
			return self.packageName
		
	def Close(self):
		"""Closes the content package, removing any temporary files.
		
		This method must be called to clean up any temporary files created when
		processing the content package.  Temporary files are created inside a
		special temporary directory created using the builtin python
		tempdir.mkdtemp function.  They are not automatically cleaned up when
		the process exits or when the garbage collector disposes of the object. 
		Use of try:... finally: to clean up the package is recommended.  For
		example::
		
			pkg=ContentPackage("MyPackage.zip")
			try:
				# do stuff with the content package here
			finally:
				pkg.Close()
			
		"""
		self.manifest=None
		self.fileTable={}
		if self.tempDir:
			shutil.rmtree(self.dPath,True)
			self.dPath=None
