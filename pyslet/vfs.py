#! /usr/bin/env python

import sys
import os
import tempfile
import shutil
import __builtin__
from types import StringTypes, UnicodeType, StringType


class VirtualFilePath:

    """Defines a virtual file system, instances represent paths within that system.

    Instances are created from one or more strings, either byte strings or
    unicode strings. In the case of byte strings the encoding is assumed to be
    the default encoding of the file system.  If multiple strings are given then
    they are joined to make a single path using :py:meth:`join`."""

    fsName = None
    """The name of the file system, must be overridden by derived classes."""

    supports_unicode_filenames = False
    """Indicates whether this file system supports unicode file names natively.
	In general, you don't need to worry about this as all methods that accept
	strings will accept either type of string and convert to the native
	representation."""

    supports_unc = False
    """Indicates whether this file system supports UNC paths."""

    codec = 'utf-8'
    """The codec used by this file system to convert between byte strings and
	unicode strings."""

    sep = '/'
    """The path separator used by this file system"""

    curdir = '.'
    """The path component that represents the current directory"""

    pardir = '..'
    """The path component that represents the parent directory"""

    @classmethod
    def getcwd(cls):
        """Returns an instance representing the current working directory."""
        raise NotImplementedError

    @classmethod
    def mkdtemp(cls, suffix="", prefix=""):
        """Creates a temporary directory in the file system, returning a path instance to it.

        Similar to Python's tempfile.mkdtemp, like that function the caller is responsible for
        cleaning up the directory, which can be done with :py:meth:`rmtree`"""
        raise NotImplementedError

    def __init__(self):
        raise NotImplementedError

    def join(self, *components):
        """Returns an instance by joining the path to one or more additional
        path components intelligently.

        For details see Python's os.path.join."""
        raise NotImplementedError

    def split(self):
        """Returns a tuple of two instances (head, tail) where tail is the last
        path component and head is everything leading up to it.

        For details see Python's os.path.split."""
        raise NotImplementedError

    def splitext(self):
        """Returns a tuple of (root, ext) where root is an instance and ext is a
        string.

        For details see Python's os.path.splitext."""
        raise NotImplementedError

    def splitdrive(self):
        """Returns a tuple of two instances (drive, tail) where drive is either
        a drive specification or is empty."""
        raise NotImplementedError

    def abspath(self):
        """Returns an absolute path instance."""
        return self.getcwd().join(self).normpath()

    def realpath(self):
        """Returns a real path, with any symbolic links removed.

        The default implementation does nothing."""
        return self

    def normpath(self):
        """Returns a normalised path instance."""
        raise NotImplementedError

    def normcase(self):
        """Returns a case-normalised path instance."""
        raise NotImplementedError

    def IsUNC(self):
        """Returns True if this path is a UNC path.

        UNC paths contain a host designation, a path cannot contain a drive
        specification and also be a UNC path."""
        raise NotImplementedError

    def IsSingleComponent(self):
        """Returns True if this path is a single, non-root, component.

        E.g., tests that the path does not contain a slash (it may be empty)"""
        raise NotImplementedError

    def __nonzero__(self):
        """An empty path is False, other paths are True"""
        return not self.IsEmpty()

    def IsEmpty(self):
        """Returns True if this path is empty"""
        raise NotImplementedError

    def IsDirLike(self):
        """Returns True if this is a directory-like path.

        E.g., test that the path ends in a slash (last component is empty)."""
        raise NotImplementedError

    def IsRoot(self):
        """Returns True if this is the root path.

        E.g., tests if it consists of just one or more slashes only (not
        counting any drive specification in file systems that support them)."""
        raise NotImplementedError

    def isabs(self):
        """Returns True if the path is an absolute path."""
        raise NotImplementedError

    def stat(self):
        """Perform the equivalent of a stat() system call on the given path."""
        raise NotImplementedError

    def exists(self):
        """Returns True if this is the path of an object that exists in the file system."""
        raise NotImplementedError

    def isfile(self):
        """Returns True if this is the path of a regular file in the file system."""
        raise NotImplementedError

    def isdir(self):
        """Returns True if this is the path of a directory in the file system."""
        raise NotImplementedError

    def open(self, mode="r"):
        """Returns an open file-like object from this path."""
        raise NotImplementedError

    def copy(self, dst):
        """Copies a file to dst path like Python's shutil.copy.

        Note that you can't copy between file system implementations."""
        raise NotImplementedError

    def remove(self):
        """Removes a file."""
        raise NotImplementedError

    def listdir(self):
        """Returns a list containing path instances of the entries in the directory."""
        raise NotImplementedError

    def chdir(self):
        """Changes the current working directory to this path"""
        raise NotImplementedError

    def mkdir(self):
        """Creates a new directory at this path."""
        raise NotImplementedError

    def makedirs(self):
        """Recursive directory creation function. Like mkdir(), but makes all
        intermediate-level directories needed to contain the leaf directory"""
        raise NotImplementedError

    def walk(self):
        """A generator function that walks the file system, similar to os.walk.

        For each directory in the tree rooted at this path (including this path
        itself), it yields a 3-tuple of (dirpath, dirnames, filenames).  dirpath
        is an instance, dirnames and filename are lists of path instances."""
        raise NotImplementedError

    def rmtree(self, ignoreErrors=False):
        """Removes the tree rooted at the directory represented by this path.

        ignoreErrors can be used to ignore any errors from the file system."""
        raise NotImplementedError

    def __str__(self):
        """Returns a byte-string representing the file path.

        Bear in mind that you can convert paths to strings using either str or
        unicode, but that file systems that are natively unicode might not be
        able to represent all paths as plain strings."""
        raise NotImplementedError

    def __unicode__(self):
        """Returns a unicode string representing the file path."""
        raise NotImplementedError

    def __cmp__(self, other):
        """Compares two path instances by their unicode representations but only if
        they are from the same file system.

        You can also compare a file path with a string (or unicode string) which
        is first converted to a file path instance."""
        if type(other) in StringTypes:
            other = self.__class__(other)
        elif self.__class__ is not other.__class__:
            raise ValueError(
                "Can't compare file paths from different file systems")
        return cmp(unicode(self), unicode(other))

    def __hash__(self):
        """Virtual path instances are immutable, and can be used as keys in dictionaries."""
        return hash(self.__class__) | hash(unicode(self))


class OSFilePath(VirtualFilePath):

    fsName = ""
    sep = os.sep
    curdir = os.curdir
    pardir = os.pardir
    supports_unicode_filenames = os.path.supports_unicode_filenames
    supports_unc = hasattr(os.path, 'splitunc')
    codec = sys.getfilesystemencoding()

    @classmethod
    def ConformPath(cls, path):
        if isinstance(path, OSFilePath):
            return path.path
        elif cls.supports_unicode_filenames:
            if path is None:
                return u""
            elif type(path) is StringType:
                return unicode(path, cls.codec)
            elif type(path) is UnicodeType:
                return path
        else:
            if path is None:
                return ""
            elif type(path) is StringType:
                return path
            elif type(path) is UnicodeType:
                return path.encode(cls.codec)
        raise ValueError("Can't initialise OSFilePath with %s" % repr(path))

    @classmethod
    def getcwd(cls):
        return cls(os.getcwd())

    @classmethod
    def mkdtemp(cls, suffix="", prefix=""):
        return cls(tempfile.mkdtemp(suffix, prefix))

    def __init__(self, *path):
        if path:
            self.path = os.path.join(*map(self.ConformPath, path))
        else:
            self.path = self.ConformPath(None)

    def join(self, *components):
        return OSFilePath(self, *components)

    def split(self):
        head, tail = os.path.split(self.path)
        return OSFilePath(head), OSFilePath(tail)

    def splitext(self):
        root, ext = os.path.splitext(self.path)
        return OSFilePath(root), ext

    def splitdrive(self):
        drive, path = os.path.splitdrive(self.path)
        return OSFilePath(drive), OSFilePath(path)

    def abspath(self):
        return OSFilePath(os.path.abspath(self.path))

    def realpath(self):
        return OSFilePath(os.path.realpath(self.path))

    def normpath(self):
        return OSFilePath(os.path.normpath(self.path))

    def normcase(self):
        return OSFilePath(os.path.normcase(self.path))

    def IsUNC(self):
        if self.supports_unc:
            unc, rest = os.path.splitunc(self.path)
            return len(unc) > 0
        else:
            return False

    def IsSingleComponent(self):
        return not (os.sep in self.path)

    def IsEmpty(self):
        return not len(self.path)

    def IsDirLike(self):
        return self.path and self.path[-1] == os.sep

    def IsRoot(self):
        drive, tail = os.path.splitdrive(self.path)
        if tail:
            for c in tail:
                if c != os.sep:
                    return False
            return True
        else:
            return False

    def isabs(self):
        return os.path.isabs(self.path)

    def stat(self):
        return os.stat(self.path)

    def exists(self):
        return os.path.exists(self.path)

    def isfile(self):
        """Returns True if this is the path of a regular file in the file system."""
        return os.path.isfile(self.path)

    def isdir(self):
        return os.path.isdir(self.path)

    def open(self, mode="r"):
        return open(self.path, mode)

    def copy(self, dst):
        if not isinstance(dst, self.__class__):
            raise ValueError("Can't copy across file system implementations")
        else:
            shutil.copy(self.path, dst.path)

    def remove(self):
        """Removes a file."""
        os.remove(self.path)

    def listdir(self):
        return map(lambda x: OSFilePath(x), os.listdir(self.path))

    def chdir(self):
        os.chdir(self.path)

    def mkdir(self):
        os.mkdir(self.path)

    def makedirs(self):
        os.makedirs(self.path)

    def walk(self):
        wrap = lambda x: OSFilePath(x)
        for dirpath, dirnames, filenames in os.walk(self.path):
            yield wrap(dirpath), map(wrap, dirnames), map(wrap, filenames)

    def rmtree(self, ignoreErrors=False):
        shutil.rmtree(self.path, ignoreErrors)

    def __str__(self):
        if type(self.path) is UnicodeType:
            return self.path.encode(sys.getfilesystemencoding())
        else:
            return self.path

    def __unicode__(self):
        if type(self.path) is StringType:
            return self.path.decode(sys.getfilesystemencoding())
        else:
            return self.path


stat_pass = os.stat
open_pass = __builtin__.open


def stat_hook(path):
    if isinstance(path, VirtualFilePath):
        return path.stat()
    else:
        return stat_pass(path)


def open_hook(path, *params):
    if isinstance(path, VirtualFilePath):
        return path.open(*params)
    else:
        return open_pass(path, *params)


class ZipHooks(object):
    hookCount = 0

    def __init__(self):
        if not ZipHooks.hookCount:
            os.stat = stat_hook
            __builtin__.open = open_hook
        ZipHooks.hookCount += 1

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.Unhook()

    def Unhook(self):
        ZipHooks.hookCount -= 1
        if not ZipHooks.hookCount:
            os.stat = stat_pass
            __builtin__.open = open_pass


fsRegister = {}


def RegisterFileSystem(fs):
    fsRegister[fs.fsName] = fs


def GetFileSystemByName(fsName):
    return fsRegister.get(fsName, None)

defaultFS = OSFilePath
RegisterFileSystem(OSFilePath)
