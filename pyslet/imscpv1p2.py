#! /usr/bin/env python
"""This module implements the IMS CP 1.2 specification defined by IMS GLC
"""

import itertools
import random
import re
import zipfile

from . import imsmdv1p2p1 as imsmd
from . import rfc2396 as uri
from . import vfs
from .pep8 import MigratedClass, old_function, old_method
from .py2 import py2, to_text
from .qtiv2 import xml as qtixml2
from .qtiv2 import metadata as qtimd
from .xml import structures as xml
from .xml import namespace as xmlns
from .xml import xsdatatypes as xsi


# :	String constant for the main namespace
IMSCP_NAMESPACE = "http://www.imsglobal.org/xsd/imscp_v1p1"
# :	String constant for the official schema location
IMSCP_SCHEMALOCATION = "http://www.imsglobal.org/xsd/imscp_v1p1.xsd"
# :	String constant for the 1.2 extension elements' namespace
IMSCPX_NAMESPACE = "http://www.imsglobal.org/xsd/imscp_extensionv1p2"

IGNOREFILES_RE = "\\..*"


class CPException(Exception):
    pass


class CPFilePathError(Exception):
    pass


class CPFileTypeError(Exception):
    pass


class CPManifestError(CPException):
    pass


class CPProtocolError(CPException):
    pass


class CPValidationError(CPException):
    pass


class CPPackageBeenThereError(CPException):
    pass


class CPZIPBeenThereError(Exception):
    pass


class CPZIPDirectorySizeError(CPException):
    pass


class CPZIPDuplicateFileError(CPException):
    pass


class CPZIPFilenameError(CPException):
    pass


class CPElement(xmlns.XMLNSElement):

    """Base class for all elements defined by the Content Packaging
    specification."""
    pass


@old_function('PathInPath')
def path_in_path(child_path, parent_path):
    """Utility function that returns child_path expressed relative to parent_path

    This function processes file system paths, not the path components of URI.

    Both paths are normalized to remove any redundant navigational segments
    before any processing, the resulting path will not contain these either.

    If child_path is not contained in parent_path then None is returned.

    If child_path and parent_path are equal an empty string is returned."""
    rel_path = []
    child_path = child_path.normpath()
    parent_path = parent_path.normpath().normcase()
    while child_path.normcase() != parent_path:
        child_path, tail = child_path.split()
        if not child_path or not tail:
            # We've gone as far as we can, fail!
            return None
        rel_path[0:0] = [tail]
    if rel_path:
        return parent_path.__class__(*rel_path)
    else:
        return ''


class Schema(CPElement):

    """Represents the schema element."""
    XMLNAME = (IMSCP_NAMESPACE, 'schema')


class SchemaVersion(CPElement):

    """Represents the schemaversion element."""
    XMLNAME = (IMSCP_NAMESPACE, 'schemaversion')


class Metadata(CPElement):

    """Represents the Metadata element."""
    XMLNAME = (IMSCP_NAMESPACE, 'metadata')
    XMLCONTENT = xml.ElementContent

    #: the default class to represent the schema element
    SchemaClass = Schema
    # : the default class to represent the schemaVersion element
    SchemaVersionClass = SchemaVersion

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: the optional schema element
        self.Schema = None
        #: the optional schemaversion element
        self.SchemaVersion = None

    def get_children(self):
        if self.Schema:
            yield self.Schema
        if self.SchemaVersion:
            yield self.SchemaVersion
        for child in CPElement.get_children(self):
            yield child


class Organization(CPElement):

    """Represents the organization element."""
    XMLNAME = (IMSCP_NAMESPACE, 'organization')


class Organizations(CPElement):

    """Represents the organizations element."""
    XMLNAME = (IMSCP_NAMESPACE, 'organizations')
    XMLCONTENT = xml.ElementContent

    #: the default class to represent the organization element
    OrganizationClass = Organization

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: a list of organization elements
        self.Organization = []

    def get_children(self):
        return itertools.chain(self.Organization, CPElement.get_children(self))


class File(CPElement):

    """Represents the file element."""
    XMLNAME = (IMSCP_NAMESPACE, 'file')
    XMLATTR_href = ('href', uri.URI.from_octets, str)

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: the href used to locate the file object
        self.href = None

    @old_method('PackagePath')
    def package_path(self, cp):
        """Returns the normalized file path relative to the root of the content
        package, *cp*.

        If the href does not point to a local file then None is returned.
        Otherwise, this function calculates an absolute path to the file and
        then calls the content package's :py:meth:`ContentPackage.package_path`
        method."""
        url = self.resolve_uri(self.href)
        if not isinstance(url, uri.FileURL):
            return None
        return cp.package_path(url.get_virtual_file_path())


class Dependency(CPElement):

    """Represents the dependency element."""
    XMLNAME = (IMSCP_NAMESPACE, 'dependency')
    XMLATTR_identifierref = 'identifierref'

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: the identifier of the resource in this dependency
        self.identifierref = None


class Resource(CPElement):

    """Represents the resource element."""
    XMLNAME = (IMSCP_NAMESPACE, 'resource')
    ID = (xmlns.NO_NAMESPACE, "identifier")
    XMLATTR_href = ('href', uri.URI.from_octets, str)
    XMLATTR_type = 'type'
    XMLCONTENT = xml.ElementContent

    #: the default class to represent the metadata element
    MetadataClass = Metadata
    #: the default class to represent the file element
    FileClass = File
    #: the default class to represent the dependency element
    DependencyClass = Dependency

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: the type of the resource
        self.type = None
        #: the href pointing at the resource's entry point
        self.href = None
        #: the resource's optional metadata element
        self.Metadata = None
        #: a list of file elements associated with the resource
        self.File = []
        #: a list of dependencies of this resource
        self.Dependency = []

    @old_method('GetEntryPoint')
    def get_entry_point(self):
        """Returns the :py:class:`File` object that is identified as the entry point.

        If there is no entry point, or no :py:class:`File` object with a
        matching href, then None is returned."""
        href = self.href
        if href:
            href = self.resolve_uri(href)
            for f in self.File:
                f_href = f.href
                if f_href:
                    f_href = f.resolve_uri(f_href)
                    if href.match(f_href):
                        return f
        return None

    @old_method('SetEntryPoint')
    def set_entry_point(self, f):
        """Set's the :py:class:`File` object that is identified as the
        resource's entry point.

        The File must already exist and be associated with the resource."""
        # We resolve and recalculate just in case xml:base lurks on this file
        href = self.relative_uri(f.resolve_uri(f.href))
        self.href = href

    def get_children(self):
        if self.Metadata:
            yield self.Metadata
        for child in itertools.chain(
                self.File,
                self.Dependency,
                CPElement.get_children(self)):
            yield child

    @old_method('DeleteFile')
    def delete_file(self, f):
        index = self.File.index(f)
        f.detach_from_doc()
        f.parent = None
        del self.File[index]

    @old_method('DeleteDependency')
    def delete_dependency(self, d):
        index = self.Dependency.index(d)
        d.detach_from_doc()
        d.parent = None
        del self.Dependency[index]


class Resources(CPElement):

    """Represents the resources element."""
    XMLNAME = (IMSCP_NAMESPACE, 'resources')
    XMLCONTENT = xml.ElementContent

    #: the default class to represent the resource element
    ResourceClass = Resource

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: the list of resources in the manifest
        self.Resource = []

    def get_children(self):
        return itertools.chain(self.Resource, CPElement.get_children(self))


class Manifest(CPElement):

    """Represents the manifest element, the root element of the imsmanifest
    file."""
    ID = (xmlns.NO_NAMESPACE, "identifier")
    XMLNAME = (IMSCP_NAMESPACE, 'manifest')
    XMLCONTENT = xml.ElementContent

    #: the default class to represent the metadata element
    MetadataClass = Metadata
    #: the default class to represent the organizations element
    OrganizationsClass = Organizations
    #: the default class to represent the resources element
    ResourcesClass = Resources
    #: the default class to represent child manifest elements
    ManifestClass = None

    def __init__(self, parent):
        CPElement.__init__(self, parent)
        #: the manifest's metadata element
        self.Metadata = None
        #: the organizations element
        self.Organizations = self.OrganizationsClass(self)
        #: the resources element
        self.Resources = self.ResourcesClass(self)
        #: a list of child manifest elements
        self.Manifest = []

    def get_children(self):
        if self.Metadata:
            yield self.Metadata
        if self.Organizations:
            yield self.Organizations
        if self.Resources:
            yield self.Resources
        for child in itertools.chain(
                self.Manifest,
                CPElement.get_children(self)):
            yield child

Manifest.ManifestClass = Manifest


class ManifestDocument(xmlns.XMLNSDocument):

    """Represents the imsmanifest.xml file itself.

    Buildong on :py:class:`pyslet.xml.namespace.XMLNSDocument` this class is
    used for parsing and writing manifest files.

    The constructor defines three additional prefixes using
    :py:meth:`~pyslet.xml.namespace.XMLNSDocument.make_prefix`, mapping xsi
    onto XML schema, imsmd onto the IMS LRM namespace and imsqti onto the IMS
    QTI 2.1 namespace.  It also adds a schemaLocation attribute.  The elements
    defined by the :py:mod:`pyslet.imsmdv1p2p1` and :py:mod:`pyslet.imsqtiv2p1`
    modules are added to the :py:attr:`classMap` to ensure that metadata from
    those schemas are bound to the special classes defined there."""

    classMap = {}

    def __init__(self, **args):
        xmlns.XMLNSDocument.__init__(self, **args)
        #: the default namespace is set to :py:const:`IMSCP_NAMESPACE`
        self.defaultNS = IMSCP_NAMESPACE
        self.make_prefix(xsi.XMLSCHEMA_NAMESPACE, 'xsi')
        self.make_prefix(imsmd.IMSLRM_NAMESPACE, 'imsmd')
        self.make_prefix(qtixml2.core.IMSQTI_NAMESPACE, 'imsqti')
        schema_location = [
            IMSCP_NAMESPACE, IMSCP_SCHEMALOCATION,
            imsmd.IMSLRM_NAMESPACE, imsmd.IMSLRM_SCHEMALOCATION,
            qtixml2.core.IMSQTI_NAMESPACE,
            qtixml2.core.IMSQTI_SCHEMALOCATION]
        if isinstance(self.root, CPElement):
            self.root.set_attribute(
                (xsi.XMLSCHEMA_NAMESPACE, 'schemaLocation'),
                ' '.join(schema_location))

    def get_element_class(self, name):
        """Overrides
        :py:meth:`pyslet.xml.namespace.XMLNSDocument.get_element_class` to look
        up name.

        The class contains a mapping from (namespace,element name) pairs to
        class objects representing the elements.  Any element not in the class
        map returns :py:meth:`~pyslet.xml.namespace.XMLNSElement` instead."""
        eclass = ManifestDocument.classMap.get(
            name, ManifestDocument.classMap.get((name[0], None),
                                                xmlns.XMLNSElement))
        return eclass

xmlns.map_class_elements(ManifestDocument.classMap, globals())
xmlns.map_class_elements(ManifestDocument.classMap, imsmd)
xmlns.map_class_elements(ManifestDocument.classMap, qtimd)
# Add other supported metadata schemas in here


class ContentPackage(MigratedClass):

    """Represents a content package.

    When constructed with no arguments a new package is created.  A temporary
    folder to hold the contents of the package is created and will not be
    cleaned up until the :py:meth:`Close` method is called.

    Alternatively, you can pass an operating system or virtual file path to a
    content package directory, to an imsmanifest.xml file or to a Package
    Interchange Format file.  In the latter case, the file is unzipped into a
    temporary folder to facilitate manipulation of the package contents.

    A new manifest file is created and written to the file system when creating
    a new package, or if it is missing from an existing package or
    directory."""

    #: the default class for representing the Manifest file
    ManifestDocumentClass = ManifestDocument

    def __init__(self, dpath=None):
        self.tempDir = False
        error_flag = True
        try:
            if dpath is None:
                #: the :py:class:`~pyslet.vfs.VirtualFilePath` to the package's
                # directory
                self.dPath = vfs.defaultFS.mkdtemp('.d', 'imscpv1p2-')
                self.tempDir = True
                self.packageName = 'imscp'
            else:
                if not isinstance(dpath, vfs.VirtualFilePath):
                    dpath = vfs.defaultFS(dpath)
                self.dPath = dpath.abspath()
                head, tail = self.dPath.split()
                self.packageName = tail
                if self.dPath.isdir():
                    # existing directory
                    pass
                elif self.dPath.exists():
                    # is this a zip archive?
                    f = self.dPath.open("rb")
                    try:
                        if zipfile.is_zipfile(f):
                            name, ext = tail.splitext()
                            if ext.lower() == ".zip":
                                self.packageName = name
                            self.expand_zip(f)
                        else:
                            # anything else must be a manifest file
                            self.dPath = head
                            mpath = tail
                            head, tail = self.dPath.split()
                            if str(mpath.normcase()) != 'imsmanifest.xml':
                                raise CPManifestError(
                                    "%s must be named imsmanifest.xml" %
                                    str(mpath))
                            self.packageName = str(tail)
                    finally:
                        f.close()
                else:
                    self.dPath.mkdir()
            if not isinstance(self.dPath, vfs.VirtualFilePath):
                import traceback
                traceback.print_stack()
            mpath = self.dPath.join('imsmanifest.xml')
            if mpath.exists():
                self.manifest = self.ManifestDocumentClass(
                    base_uri=str(uri.URI.from_virtual_path(mpath)))
                """The :py:class:`ManifestDocument` object representing the
                imsmanifest.xml file.

                The file is read (or created) on construction."""
                self.manifest.read()
                if not isinstance(self.manifest.root, Manifest):
                    raise CPManifestError("%s not a manifest file, found"
                                          " %s::%s " %
                                          (mpath, self.manifest.root.ns,
                                           self.manifest.root.xmlname))
            else:
                self.manifest = self.ManifestDocumentClass(
                    root=Manifest,
                    base_uri=str(uri.URI.from_virtual_path(mpath)))
                self.manifest.root.set_id(
                    self.manifest.get_unique_id('manifest'))
                md = self.manifest.root.add_child(
                    self.manifest.root.MetadataClass)
                md.add_child(md.SchemaClass).set_value("IMS Content")
                md.add_child(md.SchemaVersionClass).set_value("1.2")
                self.manifest.create()
            self.set_ignore_files(IGNOREFILES_RE)
            self.fileTable = {}
            """The fileTable is a dictionary that maps package relative file
            paths to the :py:class:`File` objects that represent them in the
            manifest.

            It is possible for a file to be referenced multiple times (although
            dependencies were designed to take care of most cases it is still
            possible for two resources to share a physical file, or even for a
            resource to contain multiple references to the same file.)
            Therefore, the dictionary values are lists of :py:class:`File`
            objects.

            If a file path maps to an empty list then a file exists in the
            package which is not referenced by any resource.  In some packages
            it is common for auxiliary files such as supporting schemas to be
            included in packages without a corresponding :py:class:`File`
            object so an empty list does not indicate that the file can be
            removed safely.  These files are still included when packaging the
            content package for interchange.

            Finally, if a file referred to by a :py:class:`File` object in the
            manifest is missing an entry is still created in the fileTable. You
            can walk the keys of the fileTable testing if each file exists to
            determine if some expected files are missing from the package.

            The keys in fileTable are VirtualFilePath instances.  To convert a
            string to an appropriate instance use the :py:meth:`FilePath`
            method."""
            self.rebuild_file_table()
            error_flag = False
        finally:
            if error_flag:
                self.Close()

    @old_method('FilePath')
    def make_file_path(self, *path):
        """Converts a string into a :py:class:`pyslet.vfs.VirtualFilePath`
        instance suitable for using as a key into the :py:attr:`fileTable`. The
        conversion is done using the file system of the content package's
        directory, :py:attr:`dPath`."""
        return self.dPath.__class__(*path)

    @old_method('SetIgnoreFiles')
    def set_ignore_files(self, ignore_files):
        """Sets the regular expression used to determine if a file should be ignored.

        Some operating systems and utilities create hidden files or other
        spurious data inside the content package directory.  For example,
        's OS X creates .DS_Store files and the svn source control utility
        creates .svn directories.  The files shouldn't generally be included in
        exported packages as they may confuse the recipient (who may be using a
        system on which these files and directories are not hidden) and be
        deemed to violate the specification, not to mention adding
        unnecessarily to the size of the package and perhaps even leaking
        information unintentionally.

        To help avoid this type of problem the class uses a regular expression
        to determine if a file should be considered part of the package.  When
        listing directories, the names of the files found are compared against
        this regular expression and are ignored if they match.

        By default, the pattern is set to match all directories and files with
        names beginning '.' so you will not normally need to call this
        method."""
        self.ignore_files = re.compile(ignore_files)

    @old_method('IgnoreFile')
    def ignore_file(self, f):
        """Compares a file or directory name against the pattern set by
        :py:meth:`set_ignore_files`.

        f is a unicode string."""
        match = self.ignore_files.match(f)
        if match:
            return len(f) == match.end()
        else:
            return False

    @old_method('IgnoreFilePath')
    def ignore_file_path(self, fpath):
        """Compares a file path against the pattern set by :py:meth:`set_ignore_files`

        The path is normalised before comparison and any segments consisting of
        the string '..' are skipped.  The method returns True if any of the
        remaining path components matches the ignore pattern.  In other words,
        if the path describes a file that is is in a directory that should be
        ignored it will also be ignored.

        The path can be relative or absolute.  Relative paths are *not* made
        absolute prior to comparison so this method is not affected by the
        current directory, even if the current diretory would itself be
        ignored."""
        fpath = fpath.normpath()
        while True:
            head, tail = fpath.split()
            if (tail and tail != fpath.pardir and
                    self.ignore_file(to_text(tail))):
                return True
            if not head or head == fpath:
                # No head left, or the path is unsplitable
                return False
            fpath = head

    @old_method('RebuildFileTable')
    def rebuild_file_table(self):
        """Rescans the file system and manifest and rebuilds the
        :py:attr:`fileTable`."""
        self.fileTable = {}
        been_there = {}
        for f in self.dPath.listdir():
            if self.ignore_file(to_text(f)):
                continue
            if f.normcase() == 'imsmanifest.xml':
                continue
            self.file_scanner(f, been_there)
        # Now scan the manifest and identify which file objects refer to which
        # files
        for r in self.manifest.root.Resources.Resource:
            for f in r.File:
                fpath = f.package_path(self)
                if fpath is None:
                    continue
                if fpath in self.fileTable:
                    self.fileTable[fpath].append(f)
                else:
                    self.fileTable[fpath] = [f]

    @old_method('FileScanner')
    def file_scanner(self, fpath, been_there):
        full_path = self.dPath.join(fpath)
        rfull_path = full_path.realpath()
        if rfull_path in been_there:
            raise CPPackageBeenThereError(rfull_path)
        been_there[rfull_path] = True
        if full_path.isdir():
            for f in full_path.listdir():
                if self.ignore_file(to_text(f)):
                    continue
                self.file_scanner(fpath.join(f), been_there)
        elif full_path.isfile():
            self.fileTable[fpath.normcase()] = []
        else:  # skip non-regular files.
            pass

    @old_method('PackagePath')
    def package_path(self, fpath):
        """Converts an absolute file path into a canonical package-relative path

        Returns None if fpath is not inside the package."""
        rel_path = []
        assert isinstance(fpath, vfs.VirtualFilePath)
        while fpath != self.dPath:
            fpath, tail = fpath.split()
            if not fpath or not tail:
                # We've gone as far as we can, fail!
                return None
            rel_path[0:0] = [tail]
        return self.dPath.__class__(*rel_path).normcase()

    @old_method('ExpandZip')
    def expand_zip(self, zf):
        self.dPath = vfs.defaultFS.mkdtemp('.d', 'imscpv1p2-')
        self.tempDir = True
        zf = zipfile.ZipFile(zf)
        try:
            for zfi in zf.infolist():
                path = self.dPath
                for path_seg in zfi.filename.split('/'):
                    # The current path will need to be a directory
                    if not path.isdir():
                        path.mkdir()
                    if isinstance(path_seg, bytes):
                        path_seg = path_seg.decode('utf-8')
                    elif not py2 and (zfi.flag_bits ^ 0x800):
                        # Python3 decodes as cp437 if the flag is clear
                        # we force utf-8 in this case
                        path_seg = path_seg.encode('cp437').decode('utf-8')
                    path = path.join(path_seg).normpath()
                    if self.package_path(path) is None:
                        raise CPZIPFilenameError(zfi.filename)
                if path.isdir():
                    if zfi.file_size > 0:
                        raise CPZIPDirectorySizeError(
                            "%s has size %i" % (zfi.filename, zfi.file_size))
                elif path.exists():
                    # Duplicate entries in the zip file
                    raise CPZIPDuplicateFileError(zfi.filename)
                else:
                    f = path.open('wb')
                    try:
                        f.write(zf.read(zfi.filename))
                    finally:
                        f.close()
        finally:
            zf.close()

    @old_method('ExportToPIF')
    def export_to_pif(self, zpath):
        """Exports the content package, saving the zipped package in *zpath*

        *zpath* is overwritten by this operation.

        In order to make content packages more interoperable this method goes
        beyond the basic zip specification and ensures that pathnames are
        always UTF-8 encoded when added to the archive.  When creating
        instances of :py:class:`ContentPackage` from an existing archive the
        reverse transformation is performed.  When exchanging PIF files between
        systems with different native file path encodings, encoding erros may
        occur."""
        zf = zipfile.ZipFile(zpath, 'w')
        base = b''
        been_there = {}
        try:
            for f in self.dPath.listdir():
                if self.ignore_file(to_text(f)):
                    continue
                self.add_to_zip(self.dPath.join(f), zf, base, been_there)
        finally:
            zf.close()

    @old_method('AddToZip')
    def add_to_zip(self, fpath, zf, zbase, been_there):
        rfname = fpath.realpath()
        if rfname in been_there:
            raise CPZIPBeenThereError(fpath)
        been_there[rfname] = True
        fname = to_text(fpath.split()[1])
        zfname = fname.replace('/', ':')
# 		if type(zfname) is StringType:
# 			zfname=zfname.decode(sys.getfilesystemencoding())
        zpath = zbase + zfname.encode('utf-8')
        if fpath.isdir():
            zpath += b'/'
            if py2:
                zf.writestr(zpath, b'')
            else:
                zf.writestr(zpath.decode('utf-8'), b'')
            for f in fpath.listdir():
                if self.ignore_file(to_text(f)):
                    continue
                self.add_to_zip(fpath.join(f), zf, zpath, been_there)
        elif fpath.isfile():
            with vfs.ZipHooks():
                # in Python3 zpath must be a string
                if not py2:
                    zpath = zpath.decode('utf-8')
                zf.write(fpath, zpath)
        else:  # skip non-regular files.
            pass

    @old_method('GetUniqueFile')
    def get_unique_path(self, suggested_path):
        """Returns a unique file path suitable for creating a new file in the package.

        suggested_path is used to provide a suggested path for the file.  This
        may be relative (to the root and manifest) or absolute but it must
        resolve to a file (potentially) in the package.  The suggested_path
        should either be a VirtualFilePath (of the same type as the content
        package's :py:attr:`dPath`) or a string suitable for conversion to a
        VirtualFilePath.

        When suggested_path is relative, it is forced to lower-case.  This is
        consistent with the behaviour of normcase on systems that are case
        insensitive.  The trouble with case insensitive file systems is that it
        may be impossible to unpack a content package created on a case
        sensitive system and store it on a case insenstive one.  By channelling
        all file storage through this method (and constructing any URIs *after*
        the file has been stored) the resulting packages will be more portable.

        If suggested_path already corresponds to a file already in the package,
        or to a file already referred to in the manifest, then a random string
        is added to it while preserving the suggested extension in order to
        make it unique.

        The return result is always normalized and returned relative to the
        package root."""
        if not isinstance(suggested_path, vfs.VirtualFilePath):
            suggested_path = self.dPath.__class__(suggested_path)
        if suggested_path.isabs():
            fpath = suggested_path
        else:
            fpath = self.dPath.join(to_text(suggested_path).lower())
        fpath = path_in_path(fpath, self.dPath)
        if fpath is None:
            raise CPFilePathError(suggested_path)
        fpath = fpath.normcase()
        # Now we can try and make it unique
        path_str = fpath
        path_extra = 0
        while path_str in self.fileTable:
            if not path_extra:
                path_extra = random.randint(0, 0xFFFF)
            fname, fExt = fpath.splitext()
            path_str = '%s_%X%s' % (to_text(fname), path_extra, fExt)
            path_extra = path_extra + 1
        # we have the path string
        return self.dPath.__class__(path_str)

    @old_method('File')
    def new_file(self, resource, href):
        """Returns a new :py:class:`File` object attached to *resource*

        *href* is the URI of the file expressed relative to the resource
        element in the manifest.  Although this is normally the same as the URI
        expressed relative to the package, a resource may have an xml:base
        attribute that alters the base for resolving relative URIs.

        *href* may of course be an absolute URI to an external resource.  If an
        absolute URI is given to a local file it must be located inside the
        package.

        Attempting to add a :py:class:`File` object representing the manifest
        file iteself will raise :py:class:`CPFilePathError`.

        The :py:attr:`fileTable` is updated automatically by this method."""
        furl = resource.resolve_uri(href)
        if not isinstance(furl, uri.FileURL):
            # Not a local file
            f = resource.add_child(resource.FileClass)
            f.href = href
        else:
            if href.is_absolute():
                href = uri.URIFactory.relative(href, resource.resolve_base())
            full_path = furl.get_virtual_file_path()
            head, tail = full_path.split()
            if self.ignore_file(to_text(tail)):
                raise CPFilePathError(full_path)
            rel_path = path_in_path(full_path, self.dPath)
            if (rel_path is None or
                    to_text(rel_path).lower() == 'imsmanifest.xml'):
                raise CPFilePathError(furl.path)
            # normalise the case ready to put in the file table
            rel_path = rel_path.normcase()
            f = resource.add_child(resource.FileClass)
            f.href = href
            if rel_path not in self.fileTable:
                self.fileTable[rel_path] = [f]
            else:
                self.fileTable[rel_path].append(f)
        return f

    @old_method('FileCopy')
    def file_copy(self, resource, src_url):
        """Returns a new :py:class:`File` object copied into the package from
        *src_url*, attached to *resource*.

        The file is copied to the same directory as the resource's entry point
        or to the main package directory if the resource has no entry point.

        The :py:class:`File` object is actually created with the
        :py:meth:`File` method.

        Note that if src_url points to a missing file then no file is copied to
        the package but the associated :py:class:`File` is still created.
        It will point to a missing file."""
        src_path = src_url.get_virtual_file_path()
        # We need to create a new file object
        fstart = resource.get_entry_point()
        if fstart is None:
            base_path = self.dPath
        else:
            url = fstart.resolve_uri(fstart.href)
            if not isinstance(url, uri.FileURL):
                base_path = self.dPath
            else:
                base_path, tail = url.get_virtual_file_path().split()
        # now pick up the last component of src
        head, tail = src_path.split()
        new_src_path = self.get_unique_path(base_path.join(tail))
        new_src_path = self.dPath.join(new_src_path)
        new_src = uri.URI.from_virtual_path(new_src_path)
        # Turn this file path into a relative URL in the context of the new
        # resource
        href = resource.relative_uri(new_src)
        f = self.File(resource, href)
        dname, fname = new_src_path.split()
        if not dname.isdir():
            dname.makedirs()
        if src_path.isfile():
            src_path.copy(new_src_path)
        return f

    @old_method('DeleteFile')
    def delete_file(self, href):
        """Removes the file at *href* from the file system

        This method also removes any file references to it from resources in
        the manifest. href may be given relative to the package root directory.
        The entry in :py:attr:`fileTable` is also removed.

        :py:class:`CPFileTypeError` is raised if the file is not a regular file

        :py:class:`CPFilePathError` is raised if the file is an
        :py:meth:`ignore_file`, the manifest itself or outside of the content
        package.

        :py:class:`CPProtocolError` is raised if the indicated file is not in
        the local file system."""
        base_uri = self.manifest.get_base()
        base = uri.URI.from_octets(base_uri)
        furl = uri.URI.from_octets(href).resolve(base)
        if not isinstance(furl, uri.FileURL):
            # We cannot delete non-file objects (though in future
            # we should support HTTP DELETE)
            return CPProtocolError(str(furl))
        full_path = furl.get_virtual_file_path()
        if not full_path.isfile():
            raise CPFileTypeError(full_path)
        head, tail = full_path.split()
        if self.ignore_file(to_text(tail)):
            raise CPFilePathError(full_path)
        rel_path = path_in_path(full_path, self.dPath)
        if rel_path is None or to_text(rel_path).lower() == 'imsmanifest.xml':
            raise CPFilePathError(full_path)
        # normalise the case ready for comparisons
        rel_path = rel_path.normcase()
        for r in self.manifest.root.Resources.Resource:
            del_list = []
            for f in r.File:
                # Does f point to the same file?
                if f.package_path(self) == rel_path:
                    del_list.append(f)
            for f in del_list:
                r.delete_file(f)
        # Now there are no more references, safe to remove the file itself
        full_path.remove()
        if rel_path in self.fileTable:
            del self.fileTable[rel_path]

    @old_method('GetPackageName')
    def get_package_name(self):
        """Returns a human readable name for the package

        The name is determined by the method used to create the object. The
        purpose is to return a name that would be intuitive to the user if it
        were to be used as the name of the package directory or the stem of a
        file name when exporting to a PIF file.

        Note that the name is returned as a unicode string suitable for showing
        to the user and may need to be encoded before being used in file path
        operations."""
        if isinstance(self.packageName, bytes):
            return self.packageName.decode('utf-8')
        else:
            return to_text(self.packageName)

    @old_method('Close')
    def close(self):
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
        self.manifest = None
        self.fileTable = {}
        if self.tempDir and self.dPath:
            self.dPath.rmtree(True)
            self.dPath = None
