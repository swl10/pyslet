IMS Content Packaging (version 1.2)
===================================

The IMS Content Packaging specification defines methods for packaging and
organizing resources and their associated metadata for transmission between
systems.  There is a small amount of information on Wikipedia about content
packaging in general, see http://en.wikipedia.org/wiki/Content_package.  The
main use of IMS Content Packaging in the market place is through the SCORM
profile.  Content Packaging is also used as the basis for the new IMS Common
Cartridge, and a method of packaging assessment materials using the
speicifcation is also described by IMS QTI version 2.1.

Official information about the specification is available from the IMS GLC:
http://www.imsglobal.org/content/packaging/index.html

.. py:module:: pyslet.imscpv1p2

Example
-------

The following example script illustrates the use of this module.  The script
takes two arguments, a resource file to be packaged (such as an index.html file)
and the path to save the zipped package to.  The script creates a new package
containing a single resource with the entry point set to point to the resource
file.  It also adds any other files in the same directory as the resource file,
using the python os.walk function to include files in sub-directories too.  The
:py:meth:`ContentPackage.IgnoreFilePath` method is used to ensure that hidden
files are not added::

	#! /usr/bin/env python
	
	import sys, os, os.path, shutil
	from pyslet.imscpv1p2 import ContentPackage, PathInPath
	from pyslet.rfc2396 import URIFactory
	
	def main():
		if len(sys.argv)!=3:
			print "Usage: makecp <resource file> <package file>"
			return
		resFile=sys.argv[1]
		pkgFile=sys.argv[2]
		pkg=ContentPackage()
		try:
			if os.path.isdir(resFile):
				print "Resource entry point must be a file, not a directory."
				return
			resHREF=URI.from_path(resFile)
			srcDir,srcFile=os.path.split(resFile)
			r=pkg.manifest.root.Resources.add_child(pkg.manifest.root.Resources.ResourceClass)
			r.href=str(resHREF.relative(URI.from_path(os.path.join(srcDir,'imsmanifest.xml'))))
			r.type=='webcontent'
			for dirpath,dirnames,filenames in os.walk(srcDir):
				for f in filenames:
					srcPath=os.path.join(dirpath,f)
					if pkg.IgnoreFilePath(srcPath):
						print "Skipping: %s"%srcPath
						continue
					dstPath=os.path.join(pkg.dPath,PathInPath(srcPath,srcDir))
					# copy the file
					dname,fName=os.path.split(dstPath)
					if not os.path.isdir(dname):
						os.makedirs(dname)
					print "Copying: %s"%srcPath
					shutil.copy(srcPath,dstPath)
					pkg.File(r,URI.from_path(dstPath))
			if os.path.exists(pkgFile):
				if raw_input("Are you sure you want to overwrite %s? (y/n) "%pkgFile).lower()!='y':
					return
			pkg.manifest.update()
			pkg.ExportToPIF(pkgFile)
		finally:
			pkg.Close()
	
	if __name__ == "__main__":
		main()


Note the use of the try:... finally: construct to ensure that the
:py:class:`ContentPackage` object is properly closed when it is finished with.
Note also the correct way to create elements within the manifest, using the
dependency safe \*Class attributes::

	r=pkg.manifest.root.Resources.add_child(pkg.manifest.root.Resources.ResourceClass)

This line creates a new resource element as a child of the (required) Resources element.

At the end of the script the :py:class:`ManifestDocument` is updated on the disk
using the inherited :py:meth:`~pyslet.xml.structures.Document.Update`
method.  The package can then be exported to the zip file format.

Reference
---------

..	autoclass:: ContentPackage
	:members:
	:show-inheritance:

..	autoclass:: ManifestDocument
	:members:
	:show-inheritance:


Constants
~~~~~~~~~

The following constants are used for setting and interpreting XML documents that conform
to the Content Packaging specification

..	autodata:: IMSCP_NAMESPACE

..	autodata:: IMSCP_SCHEMALOCATION

..	autodata:: IMSCPX_NAMESPACE


Elements
~~~~~~~~

..	autoclass:: CPElement
	:members:
	:show-inheritance:

..	autoclass:: Manifest
	:members:
	:show-inheritance:

..	autoclass:: Metadata
	:members:
	:show-inheritance:

..	autoclass:: Schema
	:members:
	:show-inheritance:

..	autoclass:: SchemaVersion
	:members:
	:show-inheritance:

..	autoclass:: Organizations
	:members:
	:show-inheritance:

..	autoclass:: Organization
	:members:
	:show-inheritance:

..	autoclass:: Resources
	:members:
	:show-inheritance:

..	autoclass:: Resource
	:members:
	:show-inheritance:

..	autoclass:: File
	:members:
	:show-inheritance:

..	autoclass:: Dependency
	:members:
	:show-inheritance:


Utilities
~~~~~~~~~

..	autofunction:: PathInPath
