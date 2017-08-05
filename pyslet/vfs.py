#! /usr/bin/env python

import binascii
import errno
import io
import logging
import os
import random
import shutil
import sys
import tempfile
import threading

from .py2 import (
    builtins,
    byte,
    dict_keys,
    force_bytes,
    is_unicode,
    is_text,
    join_bytes,
    py2,
    range3,
    SortableMixin,
    to_text,
    ul)


class VirtualFilePath(SortableMixin):

    """Abstract class representing a virtual file system

    Instances represent paths within a file system.  You can't create an
    instance of VirtualFilePath directly, instead you must create
    instances using a class derived from it.  (Do not call the __init__
    method of VirtualFilePath from your derived classes.)

    All instances are created from one or more strings, either byte
    strings or unicode strings, or existing instances. In the case of
    byte strings the encoding is assumed to be the default encoding of
    the file system.  If multiple arguments are given then they are
    joined to make a single path using :py:meth:`join`.

    Instances can be converted to either binary or character strings,
    use :meth:`to_bytes` for the former.  Note that the builtin str
    function returns a binary string in Python 2, not a character string.

    Instances are immutable, and can be used as keys in dictionaries.
    Instances must be from the same file system to be comparable, the
    unicode representation is used.

    An empty path is False, other paths are True.  You can also compare
    a file path with a string (or unicode string) which is first
    converted to a file path instance."""

    fs_name = None
    """The name of the file system, must be overridden by derived classes.

    The purpose of providing a name for a file system is to enable file
    systems to be mapped onto the authority (host) component of a file
    URL."""

    supports_unicode_filenames = False
    """Indicates whether this file system supports unicode file names
    natively. In general, you don't need to worry about this as all
    methods that accept strings will accept either type of string and
    convert to the native representation.

    When creating derived classes you must also override :attr:`sep`,
    :attr:`curdir`, :attr:`pardir`, :attr:`ext`, :attr:`drive_sep`
    (if applicable) and :attr:`empty` with the correct string types."""

    supports_unc = False
    """Indicates whether this file system supports UNC paths.

    UNC paths are of the general form::

        \\\\ComputerName\\SharedFolder\\Resource

    This format is used in Microsoft Windows.  See :meth:`is_unc` for
    details."""

    supports_drives = False
    """Indicates whether this file system supports 'drives', i.e., is
    Windows-like in having drive letters that may prefix paths."""

    codec = 'utf-8'
    """The codec used by this file system

    This codec is used to convert between byte strings and unicode
    strings.  The default is utf-8."""

    sep = b'/'
    """The path separator used by this file system

    This is either a character or byte string, depending on the setting
    of :attr:`supports_unicode_filenames`."""

    curdir = b'.'
    """The path component that represents the current directory"""

    pardir = b'..'
    """The path component that represents the parent directory"""

    ext = b'.'
    """The extension character"""

    drive_sep = b':'
    """The drive separator"""

    empty = b''
    """An empty path string (for use with join)"""

    @classmethod
    def getcwd(cls):
        """Returns an instance representing the working directory."""
        raise NotImplementedError

    @classmethod
    def getcroot(cls):
        """Returns an instance representing the current root.

        UNIX users will find this odd but in other file systems there
        are multiple roots.  Rather than invent an abstract concept of
        the root of roots we just accept that there can be more than
        one.  (We might struggle to perform actions like :meth:`listdir`
        on the root of roots.)

        The current root is determined by stripping back the current
        working directory until it can no longer be split."""
        wd = cls.getcwd()
        drive, root = wd.splitdrive()
        root = wd
        while True:
            head, tail = root.split()
            if root == head:
                # combine the drive with root
                return drive.join(root)
            elif len(head.path) >= len(root.path):
                raise OSError("Root error %s" % to_text(root.path))
            root = head

    @classmethod
    def mkdtemp(cls, suffix="", prefix=""):
        """Creates a temporary directory in the file system

        Returns an instance representing the path to the new directory.

        Similar to Python's tempfile.mkdtemp, like that function the
        caller is responsible for cleaning up the directory, which can
        be done with :py:meth:`rmtree`."""
        raise NotImplementedError

    @classmethod
    def path_str(cls, arg):
        """Converts a single argument to the correct string type

        File systems can use either binary or character strings and we
        convert between them using :attr:`codec`.  This method takes
        either type of string or an existing instance and returns a path
        string of the correct type."""
        if cls.supports_unicode_filenames:
            # native representation is unicode character
            if is_unicode(arg):
                return arg
            elif isinstance(arg, bytes):
                return arg.decode(cls.codec)
            elif isinstance(arg, cls):
                return arg.path
            else:
                raise TypeError
        else:
            # native representation is binary string
            if is_unicode(arg):
                return arg.encode(cls.codec)
            elif isinstance(arg, bytes):
                return arg
            elif isinstance(arg, cls):
                return arg.path
            else:
                raise TypeError

    def __init__(self, *args):
        if self.__class__ is VirtualFilePath:
            raise NotImplementedError
        elif args:
            #: the path, either character or binary string
            self.path = None
            for arg in args:
                new_path = self.path_str(arg)
                if self.path is None or new_path.startswith(self.sep):
                    self.path = new_path
                elif self.path.endswith(self.sep):
                    self.path = self.path + new_path
                else:
                    self.path = self.path + self.sep + new_path
        else:
            self.path = self.path_str('')

    def __str__(self):
        if py2:
            return self.to_bytes()
        else:
            return self.__unicode__()

    def to_bytes(self):
        """Returns the binary string representation of the path."""
        if is_unicode(self.path):
            return self.path.encode(self.codec)
        else:
            return self.path

    def __unicode__(self):
        if is_unicode(self.path):
            return self.path
        else:
            return self.path.decode(self.codec)

    def sortkey(self):
        """Instances are sortable using character strings."""
        return to_text(self)

    def join(self, *components):
        """Returns a new instance by joining path components

        Starting with the current instance, this method appends each
        component, returning a new instance representing the joined
        path. If components contains an absolute path then previous
        components, including the instance's path, are discarded.

        For details see Python's os.path.join function.

        For the benefit of derived classes a default implementation is
        provided."""
        # split the drive
        drive, tail = self.splitdrive()
        if tail.path:
            new_path = [tail.path]
            add_sep = not tail.path.endswith(self.sep)
        else:
            new_path = []
            add_sep = False
        for component in components:
            new_component = self.__class__(component)
            if self.supports_drives:
                # check for a drive letter
                new_drive, tail = new_component.splitdrive()
                if new_drive:
                    drive = new_drive
                    new_path = []
                    add_sep = False
                    new_component = tail
            if not new_component:
                # an empty component, add a separator (perhaps)
                if add_sep:
                    new_path.append(self.sep)
                    add_sep = False
                continue
            if new_component.isabs():
                new_path = [new_component.path]
                add_sep = not new_component.path.endswith(self.sep)
            else:
                if add_sep:
                    new_path.append(self.sep)
                new_path.append(new_component.path)
                add_sep = not new_component.path.endswith(self.sep)
        if drive:
            new_path[0:0] = [drive.path]
        return self.__class__(self.path_str('').join(new_path))

    def split(self):
        """Splits a path

        Returns a tuple of two instances (head, tail) where tail is the
        last path component and head is everything leading up to it.

        For details see Python's os.path.split."""
        drive, tail = self.splitdrive()
        pos = tail.path.rfind(self.sep)
        if pos >= 0:
            head_path = tail.path[0:pos]
            if head_path:
                # handle special case for UNC
                if not drive and self.supports_unc and head_path == self.sep:
                    # include the following separator
                    head = self.__class__(self.sep + self.sep)
                else:
                    head = self.__class__(drive.path + head_path)
            else:
                # don't return an empty head if sep is in the path
                head = self.__class__(drive.path + self.sep)
            tail = self.__class__(tail.path[pos + len(self.sep):])
            return head, tail
        else:
            # sep is not in the path - it's all tail
            return self.__class__(), self

    def splitext(self):
        """Splits an extension from a path

        Returns a tuple of (root, ext) where root is an instance
        containing just the root file path and ext is a string of
        *characters* representing the orignal path's extension.

        For details see Python's os.path.splitext."""
        if self.is_dirlike():
            return self, self.path_str('')
        else:
            pos = self.path.rfind(self.ext)
            if pos >= 0:
                return self.__class__(self.path[:pos]), \
                    to_text(self.path[pos:])
            else:
                return self, ""

    def splitdrive(self):
        """Splits a drive designation

        Returns a tuple of two instances (drive, tail) where drive is
        either a drive specification or is empty.

        Default implementation uses the :attr:`drive_sep` to determine
        if the first path component is a drive."""
        if self.supports_drives:
            if len(self.path) > 1 and self.path[1:2] == self.drive_sep:
                return self.__class__(self.path[:2]), \
                    self.__class__(self.path[2:])
        return self.__class__(), self

    def splitunc(self):
        """Splits a UNC path

        Returns a tuple of two instances (mount, path) where mount is an
        instance representing the UNC mount point or an instance
        representing the empty path if this isn't a UNC path.

        Default implementation checks for a double separator at the
        start of the path and at least one more separator."""
        if self.supports_unc:
            if self.path.startswith(self.sep + self.sep):
                host_start = 2 * len(self.sep)
                host_end = self.path.find(self.sep, host_start)
                if host_end > host_start:
                    mount_start = host_end + 1
                    mount_end = self.path.find(self.sep, mount_start)
                    if mount_end > mount_start:
                        # //host/mount/path
                        return self.__class__(self.path[:mount_end]), \
                            self.__class__(self.path[mount_end:])
                    else:
                        # //host/mount - return an empty path
                        return self, self.__class__()
                # else just //host, returned as *path*
        return self.__class__(), self

    def abspath(self):
        """Returns an absolute path instance."""
        return self.getcwd().join(self).normpath()

    def realpath(self):
        """Returns a real path, with any symbolic links removed.

        The default implementation normalises the path using
        :meth:`normpath` and :meth:`normcase`."""
        if self.isabs():
            result = self
        else:
            result = self.getcwd().join(self.path)
        return result.normpath().normcase()

    def normpath(self):
        """Returns a normalised path instance."""
        if not self:
            # empty paths become references to the current dir
            # deal with this special case now
            return self.__class__(self.curdir)
        drive, tail = self.splitdrive()
        components = tail.path.split(self.sep)
        i = 0
        while i < len(components):
            component = components[i]
            if not component:
                # empty path component removed except start and
                # special case of all empty components
                if i == 1 and not components[0]:
                    break
                elif i:
                    del components[i]
                else:
                    i = i + 1
            elif component == self.pardir:
                if i:
                    par = components[i - 1]
                    if par == self.pardir or par == self.curdir:
                        # ../.. and ./.. left unchanged
                        i = i + 1
                    elif par:
                        # x/.. becomes '.'
                        components[i - 1:i + 1] = [self.curdir]
                        i = i - 1
                    else:
                        # /.. goes to /
                        del components[i]
                else:
                    # ../ is ignored
                    i = i + 1
            elif component == self.curdir:
                if i > 0:
                    # something to the left
                    del components[i]
                else:
                    # we'll trim later if there is something to the
                    # right as it could be just a load blanks
                    i = i + 1
            else:
                # just a normal component
                i = i + 1
        if len(components) > 1 and components[0] == self.curdir:
            # take care of ./something
            del components[0]
        elif len(components) == 1 and not components[0]:
            # the root is depicted as '/' not an empty path!
            components.append(components[0])
        return self.__class__(drive.path + self.sep.join(components))

    def normcase(self):
        """Returns a case-normalised path instance.

        The default implementation returns the path unchanged."""
        return self

    def is_unc(self):
        """Returns True if this path is a UNC path.

        UNC paths contain a host designation, a path cannot contain a
        drive specification and also be a UNC path.

        Default implementation calls :meth:`splitunc` and returns True
        if the unc component is non-empty."""
        if self.supports_unc:
            unc, rest = self.splitunc()
            return not unc.is_empty()
        else:
            return False

    def is_single_component(self):
        """Returns True if this path is a single, non-root, component.

        E.g., tests that the path does not contain a slash (it may be
        empty)"""
        return self.sep not in self.path

    def __nonzero__(self):
        return not self.is_empty()

    def __bool__(self):
        return not self.is_empty()

    def is_empty(self):
        """Returns True if this path is empty"""
        return not self.path

    def is_dirlike(self):
        """Returns True if this is a directory-like path.

        E.g., test that the path ends in a slash (last component is
        empty)."""
        return self.path.endswith(self.sep) or \
            self.path.endswith(self.sep + self.curdir)

    def is_root(self):
        """Returns True if this is a root path.

        E.g., tests if it consists of just one or more slashes only (not
        counting any drive specification in file systems that support
        them)."""
        if self.isabs():
            head, tail = self.split()
            return head == self
        else:
            return False

    def isabs(self):
        """Returns True if the path is an absolute path."""
        drive, tail = self.splitdrive()
        return tail.path.startswith(self.sep)

    def stat(self):
        """Return information about the path."""
        raise NotImplementedError

    def exists(self):
        """Returns True if this is existing item in the file system."""
        raise NotImplementedError

    def isfile(self):
        """Returns True if this is a regular file in the file system."""
        raise NotImplementedError

    def isdir(self):
        """Returns True if this is a directory in the file system."""
        raise NotImplementedError

    def open(self, mode="r"):
        """Returns an open file-like object from this path."""
        raise NotImplementedError

    def copy(self, dst):
        """Copies a file to dst path like Python's shutil.copy.

        Note that you can't copy between file system implementations."""
        if not self.isfile():
            raise OSError("%s is not a file" % to_text(self))
        if dst.isdir():
            head, tail = self.split()
            dst = dst.join(tail)
        src_stream = dst_stream = None
        try:
            src_stream = self.open('rb')
            dst_stream = dst.open('wb')
            while True:
                data = src_stream.read(io.DEFAULT_BUFFER_SIZE)
                if not data:
                    break
                while data:
                    nbytes = dst_stream.write(data)
                    data = data[nbytes:]
        finally:
            if src_stream is not None:
                src_stream.close()
            if dst_stream is not None:
                dst_stream.close()

    def move(self, dst):
        """Moves a file to dst path like Python's os.rename."""
        raise NotImplementedError

    def remove(self):
        """Removes a file."""
        raise NotImplementedError

    def listdir(self):
        """List directory contents

        Returns a list containing path instances of the entries in the
        directory."""
        raise NotImplementedError

    def chdir(self):
        """Changes the current working directory to this path"""
        raise NotImplementedError

    def mkdir(self):
        """Creates a new directory at this path.

        If an item at this path already exists OSError is raised.  This
        method ignores any trailing separator."""
        raise NotImplementedError

    def makedirs(self):
        """Recursive directory creation function.

        Like mkdir(), but makes all intermediate-level directories
        needed to contain the leaf directory.

        The default implementation repeatedly uses a combination of
        split and mkdir."""
        cpath = self.realpath()
        if cpath.isdir():
            # nothing to do
            return
        elif cpath.exists():
            raise OSError("%s already exists" % to_text(cpath))
        missing = []
        head, tail = cpath.split()
        if not tail:
            # tail is empty, so ignore
            cpath = head
            head, tail = cpath.split()
        while not head.exists():
            missing[0:0] = [head]
            last_head = head
            head, tail = head.split()
            if last_head == head:
                break
        for dpath in missing:
            dpath.mkdir()
            if dpath == cpath:
                cpath = None
        if cpath is not None:
            cpath.mkdir()

    def walk(self):
        """A generator function that walks the file system

        Similar to os.walk. For each directory in the tree rooted at
        this path (including this path itself), it yields a 3-tuple of::

            (dirpath, dirnames, filenames)

        dirpath is an instance, dirnames and filename are lists of path
        instances."""
        raise NotImplementedError

    def rmtree(self, ignore_errors=False):
        """Removes the tree rooted at this directory

        ignore_errors can be used to ignore any errors from the file
        system."""
        raise NotImplementedError

    def __eq__(self, other):
        return self.path == self.path_str(other)

    def __cmp__(self, other):
        if is_text(other):
            other = self.__class__(other)
        elif self.__class__ is not other.__class__:
            raise ValueError(
                "Can't compare file paths from different file systems")
        return cmp(to_text(self), to_text(other))

    def __hash__(self):
        return hash(self.__class__) | hash(to_text(self))


class MemDirectory(object):

    def __init__(self, path=None):
        self.path = path


class MemFileData(io.BytesIO):

    def __init__(self, initial_bytes, memfile):
        self._memfile = memfile
        io.BytesIO.__init__(self, initial_bytes)

    def close(self):
        self.flush()
        self._memfile.data = self.getvalue()
        super(MemFileData, self).close()


class MemFile(object):

    def __init__(self, path=None):
        self.path = path
        self.stream = None
        self.data_stream = None
        self.data = b''

    def is_open(self):
        return self.data_stream is not None and not self.data_stream.closed

    def open(self, mode='r'):
        if self.is_open():
            raise IOError(errno.EPERM, os.strerror(errno.EPERM),
                          "pyslet.vfs.MemFile.open: file already open")
        if mode[0] == 'r':
            readable = True
            writable = '+' in mode
            truncate = False
            append = False
        elif mode[0] == 'w':
            readable = '+' in mode
            writable = True
            truncate = True
            append = False
        elif mode[0] == 'a':
            readable = '+' in mode
            writable = True
            truncate = False
            append = True
        else:
            raise ValueError("Bad mode: %s" % mode)
        if truncate:
            self.data = b''
        # create the base object
        self.data_stream = MemFileData(self.data, self)
        if readable and writable:
            stream = io.BufferedRandom(self.data_stream)
        elif writable:
            stream = io.BufferedWriter(self.data_stream)
        else:
            stream = io.BufferedReader(self.data_stream)
        if append:
            stream.seek(len(self.data))
        if 'b' in mode:
            # binary mode, we're done
            self.stream = stream
        else:
            if 'U' in mode:
                newline = None
            else:
                newline = ''
            self.stream = io.TextIOWrapper(stream, newline=newline)
        return self.stream


class MemFilePath(VirtualFilePath):

    fs_name = "memfs.pyslet.org"
    """Set to memfs.pyslet.org

    This class is registered when the module is loaded enabling
    URLs of the form::

        file://memfs.pyslet.org/dir/file.ext"""

    supports_unicode_filenames = True
    """File names are treated as character (unicode) strings."""

    sep = ul("/")

    curdir = ul(".")

    pardir = ul("..")

    ext = ul(".")

    drive_sep = ul(':')

    empty = ul("")

    _wd = None

    _lock = threading.RLock()

    _fsdir = {}

    @classmethod
    def getcwd(cls):
        """Returns an instance representing the working directory."""
        if cls._wd is None:
            cls._wd = cls('/')
        return cls._wd

    def chdir(self):
        """Sets the current working directory"""
        if self.isabs():
            self.__class__._wd = self
        else:
            self.__class__._wd = self.abspath()

    @classmethod
    def mkdtemp(cls, suffix="", prefix=""):
        """Creates a temporary directory in the file system

        Returns an instance representing the path to the new directory.

        Similar to Python's tempfile.mkdtemp, like that function the
        caller is responsible for cleaning up the directory, which can
        be done with :py:meth:`rmtree`."""
        tmp = cls("/tmp")
        # create a random string of hex digits
        i = 0
        while i < 256:
            i += 1
            try:
                stem = os.urandom(10)
            except NotImplementedError:
                stem = []
                for i in range3(10):
                    stem.append(byte(random.getrandbits(8)))
                stem = join_bytes(stem)
            stem = binascii.hexlify(stem).lower()
            name = cls.path_str(prefix) + cls.path_str(stem) + \
                cls.path_str(suffix)
            if cls.sep in name:
                raise ValueError
            tmp = tmp.join(name)
            # now hold the file system lock
            with cls._lock:
                if not tmp.exists():
                    tmp.makedirs()
                    return tmp
        logging.error("MemFilePath.mkdtemp failed in 256 attempts")
        raise RuntimeError

    def __init__(self, *args):
        super(MemFilePath, self).__init__(*args)

    def exists(self):
        """Returns True if this is an existing item in the file system."""
        # step 1: canonicalise the path
        cpath = self.realpath()
        with self._lock:
            return cpath in self._fsdir

    def isfile(self):
        """Returns True if this is a file in the file system."""
        if self.is_dirlike():
            return False
        cpath = self.realpath()
        with self._lock:
            item = self._fsdir.get(cpath, None)
            return isinstance(item, MemFile)

    def isdir(self):
        """Returns True if this is a directory in the file system."""
        cpath = self.realpath()
        with self._lock:
            item = self._fsdir.get(cpath, None)
            return isinstance(item, MemDirectory)

    def open(self, mode="r"):
        """Returns an open file-like object from this path."""
        if not self or self.is_dirlike():
            # can't open empty paths, or directory-like paths
            raise OSError("%s cannot be opened as a file" % self)
        cpath = self.realpath()
        with self._lock:
            item = self._fsdir.get(cpath, None)
            if item is None:
                item = MemFile(cpath)
                self._fsdir[cpath] = item
            if isinstance(item, MemFile):
                return item.open(mode)
            else:
                # must be a directory, can't open one of those
                raise OSError("%s is a directory" % self)

    def mkdir(self):
        """Creates a new directory at this path."""
        cpath = self.realpath()
        head, tail = cpath.split()
        if not tail:
            # empty last component, repeat
            cpath = head
            head, tail = cpath.split()
        with self._lock:
            if head not in self._fsdir:
                if head.is_root():
                    # auto create the root if missing
                    self._fsdir[head] = MemDirectory(head)
                    if cpath == head:
                        return
                else:
                    raise OSError("%s does not exist" % to_text(head))
            if cpath in self._fsdir:
                raise OSError("%s already exists" % to_text(cpath))
            self._fsdir[cpath] = MemDirectory(cpath)

    def listdir(self):
        """List directory contents"""
        cpath = self.realpath()
        items = []
        with self._lock:
            dir = self._fsdir.get(cpath, None)
            if not isinstance(dir, MemDirectory):
                raise OSError("%s is not a directory" % to_text(cpath))
            if not cpath.is_root():
                prefix = cpath.path + self.sep
            else:
                prefix = cpath.path
            for path in dict_keys(self._fsdir):
                if not path.path.startswith(prefix):
                    continue
                head, tail = path.split()
                if head == cpath:
                    if tail and tail.is_single_component():
                        # catch case of empty tail ('/')
                        items.append(tail)
        return items

    def remove(self):
        """Removes a file."""
        if self.isfile():
            cpath = self.realpath()
            with self._lock:
                item = self._fsdir[cpath]
                if isinstance(item, MemFile):
                    if item.is_open():
                        raise IOError(
                            errno.EPERM, os.strerror(errno.EPERM),
                            "pyslet.vfs.MemFile.remove: file is open")
                    else:
                        del self._fsdir[cpath]
        elif self.isdir():
            raise OSError("%s is a directory" % self)
        else:
            raise OSError("%s no such file" % self)

    def rmtree(self, ignore_errors=False):
        """Removes the tree rooted at this directory"""
        cpath = self.realpath()
        with self._lock:
            dir = self._fsdir.get(cpath, None)
            if not isinstance(dir, MemDirectory):
                if ignore_errors:
                    return
                else:
                    raise OSError("%s is not a directory" % to_text(cpath))
            if not cpath.is_root():
                prefix = cpath.path + self.sep
            else:
                prefix = cpath.path
            dirs = []
            files = []
            open_files = False
            for path in dict_keys(self._fsdir):
                if not path.path.startswith(prefix):
                    continue
                item = self._fsdir[path]
                if isinstance(item, MemDirectory):
                    dirs.append(path)
                else:
                    # it must be a file object
                    if item.is_open():
                        # file is open, can't be removed
                        if not ignore_errors:
                            raise OSError("%s is open" % to_text(path))
                        else:
                            # don't remove any directories
                            open_files = True
                    else:
                        files.append(path)
            for fpath in files:
                del self._fsdir[fpath]
            if not open_files:
                for dpath in dirs:
                    del self._fsdir[dpath]


class OSFilePath(VirtualFilePath):

    """A concrete implementation mapping to Python's os modules

    In most cases the methods map straightforwardly to functions in os
    and os.path."""

    fs_name = ""
    """An empty string.

    The file system name affects the way URIs are interpreted, an empty
    string is consistent with the use of file:/// to reference the
    local file system."""

    supports_unicode_filenames = os.path.supports_unicode_filenames
    """Copied from os.path

    That means you won't know ahead of time whether paths are expected
    as binary or unicode strings.  In most cases it won't matter as the
    methods will convert as appropriate but it does affect the type of
    the static path constants defined below."""

    supports_unc = hasattr(os.path, 'splitunc')
    """Automatically determined from os.path

    Tests if os.path has defined splitunc."""

    supports_drives = not (os.sep in os.path.join("C:", "foo"))
    """Automatically determined

    The method chosen is straight out of the documentation for os.path.
    We join the segments "C:" and "foo" and check to see if the result
    contains the path separator or not."""

    #: as returned by sys.getfilesystemencoding()
    codec = sys.getfilesystemencoding()

    #: copied from os.sep
    sep = os.sep if os.path.supports_unicode_filenames else \
        force_bytes(os.sep)

    #: copied from os.curdir
    curdir = os.curdir if os.path.supports_unicode_filenames else \
        force_bytes(os.curdir)

    #: copied from os.pardir
    pardir = os.pardir if os.path.supports_unicode_filenames else \
        force_bytes(os.pardir)

    #: copied from os.extsep
    ext = os.extsep if os.path.supports_unicode_filenames else \
        force_bytes(os.extsep)

    drive_sep = ul(":") if os.path.supports_unicode_filenames else b":"
    """always set to ':'

    Correctly set to either binary or character string depending on the
    setting of :attr:`supports_unicode_filenames`."""

    empty = ul("") if os.path.supports_unicode_filenames else b""
    """Set to the empty string

    Uses either a binary or character string depending on the setting of
    :attr:`supports_unicode_filenames`."""

    @classmethod
    def getcwd(cls):
        return cls(os.getcwd())

    @classmethod
    def mkdtemp(cls, suffix="", prefix=""):
        return cls(tempfile.mkdtemp(suffix, prefix))

    def __init__(self, *path):
        if path:
            self.path = os.path.join(*map(self.path_str, path))
        else:
            self.path = self.path_str('')

    def join(self, *components):
        return OSFilePath(self, *components)

    def split(self):
        head, tail = os.path.split(self.path)
        return OSFilePath(head), OSFilePath(tail)

    def splitext(self):
        root, ext = os.path.splitext(self.path)
        return OSFilePath(root), to_text(ext)

    def splitdrive(self):
        drive, path = os.path.splitdrive(self.path)
        return OSFilePath(drive), OSFilePath(path)

    def splitunc(self):
        if self.supports_unc:
            unc, path = os.path.splitunc(self.path)
            return OSFilePath(unc), OSFilePath(path)
        else:
            return None, self

    def abspath(self):
        return OSFilePath(os.path.abspath(self.path))

    def realpath(self):
        return OSFilePath(os.path.realpath(self.path))

    def normpath(self):
        return OSFilePath(os.path.normpath(self.path))

    def normcase(self):
        return OSFilePath(os.path.normcase(self.path))

    def is_single_component(self):
        return not (self.sep in self.path)

    def is_empty(self):
        return not len(self.path)

    def isabs(self):
        return os.path.isabs(self.path)

    def stat(self):
        return os.stat(self.path)

    def exists(self):
        return os.path.exists(self.path)

    def isfile(self):
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

    def move(self, dst):
        if not isinstance(dst, self.__class__):
            raise ValueError("Can't move across file system implementations")
        else:
            os.rename(self.path, dst.path)

    def remove(self):
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
        def wrap(fname):
            return OSFilePath(fname)
        for dirpath, dirnames, filenames in os.walk(self.path):
            yield wrap(dirpath), map(wrap, dirnames), map(wrap, filenames)

    def rmtree(self, ignore_errors=False):
        shutil.rmtree(self.path, ignore_errors)


stat_pass = os.stat
open_pass = builtins.open


def stat_hook(path, *args, **kwargs):
    if isinstance(path, VirtualFilePath):
        return path.stat()
    else:
        return stat_pass(path, *args, **kwargs)


def open_hook(path, *params):
    if isinstance(path, VirtualFilePath):
        return path.open(*params)
    else:
        return open_pass(path, *params)


class ZipHooks(object):

    """Context manager for compatibility with zipfile

    The zipfile module allows you to write either a string or the
    contents of a named file to a zip archive.  This class
    monkey-patches the builtin open function and os.stat with versions
    that support :class:`VirtualFilePath` objects allowing us to copy
    the contents of a virtual represented file path directly to a zip
    archive without having to load it into memory first.

    For more information on this approach see this `blog post`__.

    ..  __:
        http://swl10.blogspot.co.uk/2012/12/writing-stream-to-zipfile-in-python.html

    This implementation uses a lock on the class attributes to ensure
    thread safety.

    As currently implemented, Pyslet does not contain a full
    implementation of :class:`VirtualFilePath` so this class is provided
    in readiness for a more comprehensive implementation based on
    :class:`pyslet.blockstore.StreamStore`."""
    hookCount = 0
    lock = threading.RLock()

    def __init__(self):
        with self.lock:
            if not ZipHooks.hookCount:
                os.stat = stat_hook
                builtins.open = open_hook
            ZipHooks.hookCount += 1
            self.hooked = True

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.unhook()

    def unhook(self):
        with self.lock:
            if self.hooked:
                ZipHooks.hookCount -= 1
                if not ZipHooks.hookCount:
                    os.stat = stat_pass
                    builtins.open = open_pass
                self.hooked = False
            else:
                raise RuntimeError("ZipHooks already unhooked")

fsRegister = {}


def register_file_system(fs):
    fsRegister[fs.fs_name] = fs


def get_file_system_by_name(fs_name):
    return fsRegister.get(fs_name, None)

defaultFS = OSFilePath
register_file_system(OSFilePath)
register_file_system(MemFilePath)
