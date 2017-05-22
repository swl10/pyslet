#! /usr/bin/env python

import logging
import os
import unittest
import zipfile

import pyslet.vfs as vfs

from pyslet.py2 import is_text, to_text, ul


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(VirtualFilePathTests, 'test'),
        unittest.makeSuite(MemFilePathTests, 'test'),
        unittest.makeSuite(BinarySystemTests, 'test'),
        unittest.makeSuite(DriveSystemTests, 'test'),
        unittest.makeSuite(UNCSystemTests, 'test'),
        unittest.makeSuite(OSFilePathTests, 'test')
    ))


class VirtualFilePathTests(unittest.TestCase):

    def test_fs_data(self):
        fs = vfs.VirtualFilePath
        self.assertTrue(fs.fs_name is None)
        self.assertFalse(fs.supports_unicode_filenames)
        self.assertFalse(fs.supports_unc)
        self.assertFalse(fs.supports_drives)
        self.assertTrue(fs.codec == "utf-8")
        self.assertTrue(fs.sep == b"/")
        self.assertTrue(fs.curdir == b".")
        self.assertTrue(fs.pardir == b"..")
        self.assertTrue(fs.empty == b"")

    def test_constructor(self):
        try:
            vfs.VirtualFilePath()
            self.fail("Can't instantiate abstract class")
        except NotImplementedError:
            pass

    def test_class_overrides(self):
        fs = vfs.VirtualFilePath
        try:
            fs.getcwd()
            self.fail("getcwd must be overridden")
        except NotImplementedError:
            pass
        try:
            fs.mkdtemp()
            self.fail("mkdtemp must be overridden")
        except NotImplementedError:
            pass

    def test_instance_overrides(self):
        class Dummy(vfs.VirtualFilePath):
            pass
        # uses all defaults so should allow instantiation
        path = Dummy()
        try:
            path.stat()
            self.fail("abstract stat")
        except NotImplementedError:
            pass
        try:
            path.exists()
            self.fail("abstract exists")
        except NotImplementedError:
            pass
        try:
            path.isfile()
            self.fail("abstract isfile")
        except NotImplementedError:
            pass
        try:
            path.isdir()
            self.fail("abstract isdir")
        except NotImplementedError:
            pass
        try:
            path.open()
            self.fail("abstract open")
        except NotImplementedError:
            pass
        try:
            path.move(Dummy('here'))
            self.fail("abstract move")
        except NotImplementedError:
            pass
        try:
            path.remove()
            self.fail("abstract remove")
        except NotImplementedError:
            pass
        try:
            path.listdir()
            self.fail("abstract listdir")
        except NotImplementedError:
            pass
        try:
            path.chdir()
            self.fail("abstract chdir")
        except NotImplementedError:
            pass
        try:
            path.mkdir()
            self.fail("abstract mkdir")
        except NotImplementedError:
            pass

        class DummyUNC(vfs.VirtualFilePath):
            supports_unc = True
        path = DummyUNC()


class GeneralFilePathTests(object):

    def run_constructor(self):
        path = self.fs()
        self.assertTrue(isinstance(path, vfs.VirtualFilePath),
                        "VirtualFilePath abstract class")
        self.assertTrue(path.is_empty(), "Empty path creation")
        self.assertTrue(path.is_single_component(),
                        "Empty path is a single component")
        self.assertFalse(path.is_dirlike(), "Empty path is not diretory like")
        self.assertFalse(path.is_root(), "Empty path is not the root")
        self.assertFalse(path, "Non-zero test of empty path")
        path = self.fs('hello')
        self.assertFalse(path.is_empty(), "Single path component")
        self.assertTrue(path.is_single_component(),
                        "path is a single component")
        self.assertFalse(path.is_dirlike(), "path is not diretory like")
        self.assertFalse(path.is_root(), "path is not the root")
        self.assertTrue(path.to_bytes() == b"hello", "convert to binary str")
        self.assertTrue(to_text(path) == ul("hello"), "convert to text")
        self.assertTrue(path, "Non-zero test of non-empty path")
        # create a path from a path
        path = self.fs(path)
        self.assertTrue(to_text(path) == ul("hello"), "check path")
        # create a path from a string and instance mix
        hello_world = ul("hello") + to_text(self.fs.sep) + ul("world")
        path = self.fs(path, 'world')
        self.assertTrue(to_text(path) == hello_world)
        # create a path from a string ending with the separator
        path = self.fs(ul('hello') + to_text(self.fs.sep), 'world')
        self.assertTrue(to_text(path) == hello_world)
        self.assertTrue(str(path) == str(hello_world))
        path = self.fs(ul('Caf\xe9'))
        self.assertTrue(path.to_bytes() == ul('Caf\xe9').encode(path.codec),
                        "convert to binary string")
        self.assertTrue(to_text(path) == ul('Caf\xe9'), "convert to text")
        # create a path with a trailing sep
        hello = self.fs.path_str('hello') + self.fs.sep
        path = self.fs(hello)
        self.assertFalse(path.is_empty(), "Trailing slash non empty")
        self.assertFalse(path.is_single_component(),
                         "trailing slash is a single component")
        self.assertTrue(path.is_dirlike(), "trailing slash diretory like")
        self.assertFalse(path.is_root(), "trailing slash not the root")
        self.assertTrue(to_text(path) == ul(hello), "convert to text")
        # create a path with a trailing sep and current dir indicator
        hello = self.fs.path_str('hello') + self.fs.sep + self.fs.curdir
        path = self.fs(hello)
        self.assertFalse(path.is_empty(), "Trailing dot-slash non empty")
        self.assertFalse(path.is_single_component(),
                         "trailing dot-slash is a single component")
        self.assertTrue(path.is_dirlike(), "trailing dot-slash diretory like")
        self.assertFalse(path.is_root(), "trailing dot-slash not the root")
        self.assertTrue(to_text(path) == ul(hello), "convert to text")
        # bad argument types raise TypeError
        try:
            path = self.fs(45)
            self.fail("constructor requires string argument")
        except TypeError:
            pass

    def run_join(self):
        """Join one or more path components intelligently. If any
        component is an absolute path, all previous components (on
        Windows, including the previous drive letter, if there was one)
        are thrown away, and joining continues. The return value is the
        concatenation of path1, and optionally path2, etc., with exactly
        one directory separator (os.sep) inserted between components,
        unless path2 is empty. Note that on Windows, since there is a
        current directory for each drive, os.path.join("c:", "foo")
        represents a path relative to the current directory on drive C:
        (c:foo), not c:\\foo."""
        path = self.fs.getcwd()
        path1 = self.fs.join(path, self.fs('bye'))
        path2 = self.fs.join(path, self.fs('hello'), path, self.fs('bye'))
        self.assertTrue(
            path1 == path2,
            "If any component is an absolute path, all previous components "
            "are thrown away")
        path1 = self.fs.join(path, 'bye')
        path2 = self.fs.join(path, 'hello', path, 'bye')
        self.assertTrue(path1 == path2, "Re-test with strings in join")
        # catch some odd cases
        hello = self.fs.path_str('hello')
        world = self.fs.path_str('world')
        empty = self.fs.path_str('')
        hello_world = hello + self.fs.sep + world
        # extra sep ignored
        path = self.fs(hello + self.fs.sep).join(world)
        self.assertTrue(self.fs.path_str(path) == hello_world)
        # empty segment ignored
        path = self.fs(hello).join(empty, world)
        self.assertTrue(self.fs.path_str(path) == hello_world)
        path = self.fs(empty).join(empty, hello, world)
        self.assertTrue(self.fs.path_str(path) == hello_world)
        # ... except right at the end
        path = self.fs(hello).join(world, empty)
        self.assertTrue(self.fs.path_str(path) == hello_world + self.fs.sep)
        # ... some abs cases
        path = self.fs(hello).join(self.fs.sep + world)
        self.assertTrue(self.fs.path_str(path) == self.fs.sep + world)
        # ... components are not changed, only joined...
        path = self.fs(hello).join(world + self.fs.sep + world)
        self.assertTrue(self.fs.path_str(path) ==
                        hello_world + self.fs.sep + world)
        path = self.fs(hello).join(world + self.fs.sep + self.fs.sep + world)
        self.assertTrue(self.fs.path_str(path) ==
                        hello_world + self.fs.sep + self.fs.sep + world)
        # catch an odd case
        path = self.fs(hello, empty).join(empty, world)
        self.assertTrue(self.fs.path_str(path) == hello_world)
        if self.fs.supports_drives:
            cdrive = self.fs.path_str('C:')
            # If a component contains a drive letter, all previous
            # components are thrown away and the drive letter is reset
            # case 1: relative path follows drive
            path = self.fs(hello).join(cdrive, world)
            self.assertTrue(self.fs.path_str(path) == cdrive + world)
            # case 2: absolute path follows drive
            path = self.fs(hello).join(cdrive, self.fs.sep + world)
            self.assertTrue(self.fs.path_str(path) ==
                            cdrive + self.fs.sep + world)
            # case 3: drive + relative
            path = self.fs(cdrive).join(hello)
            self.assertTrue(self.fs.path_str(path) == cdrive + hello)
            # case 4: drive + absolute
            path = self.fs(cdrive).join(self.fs.sep + hello)
            self.assertTrue(self.fs.path_str(path) ==
                            cdrive + self.fs.sep + hello)

    def run_split(self):
        path = self.fs.getcwd()
        drive1, path1 = self.fs.splitdrive(path)
        drive2, path2 = path.splitdrive()
        self.assertTrue(drive1 == drive2, "Drives don't match")
        self.assertTrue(path1 == path2, "Driveless paths don't match")
        while path is not None:
            # an empty path is
            dpath, fpath = path.split()
            self.assertTrue(self.fs.split(path) == (dpath, fpath),
                            "fs.split(path) == path.split(), (%s)" %
                            str(path))
            self.assertTrue(isinstance(dpath, vfs.VirtualFilePath),
                            "head not a VirtualFilePath (%s)" % str(path))
            self.assertTrue(isinstance(fpath, vfs.VirtualFilePath),
                            "tail not a VirtualFilePath (%s)" % str(path))
            self.assertTrue(
                fpath.is_single_component(),
                "The tail part will never contain a slash (%s)" % str(path))
            if path.is_empty():
                self.assertTrue(
                    dpath.is_empty() and fpath.is_empty(),
                    "If path is empty, both head and tail are empty (%s)"
                    % str(path))
                break
            if path.is_single_component():
                self.assertTrue(
                    dpath.is_empty(),
                    "If there is no slash in path, head will be empty (%s)" %
                    str(path))
            if path.is_dirlike():
                self.assertTrue(
                    fpath.is_empty(),
                    "If path ends in a slash, tail will be empty (%s)" %
                    str(path))
            if not dpath.is_root():
                self.assertFalse(
                    dpath.is_dirlike(),
                    "Trailing slashes are stripped from head unless it is "
                    "the root (one or more slashes only) (%s)" % str(path))
            path2 = self.fs.join(dpath, fpath)
            self.assertTrue(path2 == path, "fs.join after split ")
            path2 = dpath.join(fpath)
            self.assertTrue(path2 == path, "path.join after split")
            path = dpath
            if path.is_root():
                break
        # catch an odd case
        path = self.fs('hello')
        head, tail = path.split()
        self.assertTrue(head.is_empty())
        self.assertTrue(tail == path)

    def run_split_ext(self):
        path = self.fs.getcwd().join('hello.txt')
        root, ext = path.splitext()
        self.assertTrue(isinstance(root, vfs.VirtualFilePath),
                        "Splitext root is a virtual file path")
        self.assertTrue(is_text(ext), "extension returns a string type")
        self.assertTrue(str(root.split()[1]) == "hello", "root match")
        self.assertTrue(ext == ".txt", "ext match")
        path = self.fs.getcwd().join('hello')
        root, ext = path.splitext()
        self.assertTrue(root == path)
        self.assertTrue(to_text(ext) == to_text(''))
        # catch an odd case
        hello = ul("hello") + to_text(self.fs.sep)
        path = self.fs(hello)
        root, ext = path.splitext()
        self.assertTrue(root == path)
        self.assertTrue(to_text(ext) == to_text(''))

    def run_abs(self):
        path = self.fs.getcwd()
        self.assertTrue(path.isabs(), "CWD not absolute:" + to_text(path))
        self.assertTrue(self.fs.isabs(path), "CWD not absolute, alternative")
        self.assertTrue(path.abspath() == path, "Absolute path from cwd")
        path = self.fs('hello')
        self.assertFalse(path.isabs(), "path component not absolute")
        self.assertFalse(
            self.fs.isabs(path), "path component not absolute, alternative")

    def run_realpath(self):
        path = self.fs.getcwd().realpath()
        self.assertTrue(path.isabs(), "CWD realpath not absolute")
        hello_world = self.fs('hello', 'world').realpath()
        self.assertTrue(hello_world.isabs(), "realpath absolute: %s" %
                        hello_world)
        self.assertTrue(path.join('hello', 'world') == hello_world)

    def run_normpath(self):
        hello = self.fs.path_str('hello')
        world = self.fs.path_str('world')
        empty = self.fs.path_str('')
        # we use root instead of empty on the left
        root = self.fs.getcroot()
        dot = self.fs.curdir
        dotdot = self.fs.pardir
        sl = self.fs.sep
        hello_world = hello + sl + world
        # we don't know if root ends in sep or not so we make this match
        # strings up manauully
        root_hello = self.fs(root, hello).path
        root_hello_world = self.fs(root, hello, world).path
        tests = [
            ((hello,), hello),
            ((dot,), dot),
            ((dotdot,), dotdot),
            ((empty,), dot),
            ((root,), root),
            # 2 elements
            ((hello, world), hello_world),
            ((hello, dot), hello),
            ((hello, dotdot), dot),
            ((hello, empty), hello),
            ((dot, hello), hello),
            ((dot, dot), dot),
            ((dot, dotdot), dotdot),
            ((dot, empty), dot),
            ((dotdot, hello), dotdot + sl + hello),
            ((dotdot, dot), dotdot),
            ((dotdot, dotdot), dotdot + sl + dotdot),
            ((dotdot, empty), dotdot),
            ((root, hello), root_hello),
            ((root, dot), root),
            ((root, dotdot), root),
            ((root, empty), root),
            # 3 elements
            ((hello, hello, world), hello + sl + hello_world),
            ((hello, world, dot), hello_world),
            ((hello, world, dotdot), hello),
            ((hello, world, empty), hello_world),
            ((hello, dot, world), hello_world),
            ((hello, dot, dot), hello),
            ((hello, dot, dotdot), dot),
            ((hello, dot, empty), hello),
            ((hello, dotdot, world), world),
            ((hello, dotdot, dot), dot),
            ((hello, dotdot, dotdot), dotdot),
            ((hello, dotdot, empty), dot),
            ((hello, empty, world), hello_world),
            ((hello, empty, dot), hello),
            ((hello, empty, dotdot), dot),
            ((hello, empty, empty), hello),
            ((dot, hello, world), hello_world),
            ((dot, hello, dot), hello),
            ((dot, hello, dotdot), dot),
            ((dot, hello, empty), hello),
            ((dot, dot, hello), hello),
            ((dot, dot, dot), dot),
            ((dot, dot, dotdot), dotdot),
            ((dot, dot, empty), dot),
            ((dot, dotdot, hello), dotdot + sl + hello),
            ((dot, dotdot, dot), dotdot),
            ((dot, dotdot, dotdot), dotdot + sl + dotdot),
            ((dot, dotdot, empty), dotdot),
            ((dot, empty, hello), hello),
            ((dot, empty, dot), dot),
            ((dot, empty, dotdot), dotdot),
            ((dot, empty, empty), dot),
            ((dotdot, hello, world), dotdot + sl + hello_world),
            ((dotdot, hello, dot), dotdot + sl + hello),
            ((dotdot, hello, dotdot), dotdot),
            ((dotdot, hello, empty), dotdot + sl + hello),
            ((dotdot, dot, hello), dotdot + sl + hello),
            ((dotdot, dot, dot), dotdot),
            ((dotdot, dot, dotdot), dotdot + sl + dotdot),
            ((dotdot, dot, empty), dotdot),
            ((dotdot, dotdot, hello), dotdot + sl + dotdot + sl + hello),
            ((dotdot, dotdot, dot), dotdot + sl + dotdot),
            ((dotdot, dotdot, dotdot), dotdot + sl + dotdot + sl + dotdot),
            ((dotdot, dotdot, empty), dotdot + sl + dotdot),
            ((dotdot, empty, hello), dotdot + sl + hello),
            ((dotdot, empty, dot), dotdot),
            ((dotdot, empty, dotdot), dotdot + sl + dotdot),
            ((dotdot, empty, empty), dotdot),
            ((root, hello, world), root_hello_world),
            ((root, hello, dot), root_hello),
            ((root, hello, dotdot), root),
            ((root, hello, empty), root_hello),
            ((root, dot, hello), root_hello),
            ((root, dot, dot), root),
            ((root, dot, dotdot), root),
            ((root, dot, empty), root),
            ((root, dotdot, hello), root_hello),
            ((root, dotdot, dot), root),
            ((root, dotdot, dotdot), root),
            ((root, dotdot, empty), root),
            ((root, empty, hello), root_hello),
            ((root, empty, dot), root),
            ((root, empty, dotdot), root),
            ((root, empty, empty), root)]
        for args, expected in tests:
            actual = self.fs.path_str(self.fs(*args).normpath())
            self.assertTrue(actual == expected,
                            "%s -> %s" % (repr(args), actual))

    def run_dirs(self):
        dpath = self.fs.mkdtemp('.d', 'test-')
        try:
            self.assertTrue(isinstance(dpath, vfs.VirtualFilePath))
            self.assertTrue(dpath.exists() and dpath.isdir())
            new_path = dpath.join("test-directory")
            self.assertFalse(new_path.exists() or new_path.isdir())
            new_path.mkdir()
            self.assertTrue(new_path.exists() and new_path.isdir())
            deep_path = dpath.join("missing", "dir")
            self.assertFalse(deep_path.exists() or deep_path.isdir())
            try:
                deep_path.mkdir()
                self.fail("Missing parent test")
            except:
                pass
            deep_path.makedirs()
            self.assertTrue(deep_path.exists() and deep_path.isdir())
            new_file = new_path.join('hello')
            f = new_file.open('w')
            f.write(ul("Hello"))
            f.close()
            self.assertTrue(new_file.exists() and new_file.isfile() and
                            not new_file.isdir())
            new_copy = new_path.join('hello-again')
            self.assertFalse(
                new_copy.exists() or new_copy.isfile() or new_copy.isdir())
            new_file.copy(new_copy)
            self.assertTrue(new_copy.exists() and new_copy.isfile() and
                            not new_copy.isdir())
            f = new_copy.open('r')
            data = f.read()
            f.close()
            self.assertTrue(data == "Hello", "Copy data test")
            new_file.remove()
            self.assertFalse(
                new_file.exists() or new_file.isfile() or new_file.isdir())
            listing = dpath.listdir()
            found = False
            for node in listing:
                if "test-directory" == node:
                    found = True
                    break
            self.assertTrue(
                found, "Couldn't find test-directory in new directory")
        finally:
            dpath.rmtree(True)

        def norandom(n):
            raise NotImplementedError
        try:
            save_random = os.urandom
            os.urandom = norandom
            # check that we can work even without urandom
            dpath = self.fs.mkdtemp('.d', 'test-')
            dpath.rmtree(True)
        finally:
            os.urandom = save_random


class MemFilePathTests(GeneralFilePathTests, unittest.TestCase):

    def setUp(self):    # noqa
        self.fs = vfs.MemFilePath

    def test_fs_data(self):
        self.assertTrue(self.fs.fs_name == "memfs.pyslet.org")
        self.assertTrue(self.fs.supports_unicode_filenames)
        self.assertFalse(self.fs.supports_unc)
        self.assertFalse(self.fs.supports_drives)
        self.assertTrue(self.fs.codec == "utf-8")
        self.assertTrue(self.fs.sep == ul("/"))
        self.assertTrue(isinstance(self.fs.sep, type(ul(""))))
        self.assertTrue(self.fs.curdir == ul("."))
        self.assertTrue(isinstance(self.fs.curdir, type(ul(""))))
        self.assertTrue(self.fs.pardir == ul(".."))
        self.assertTrue(isinstance(self.fs.pardir, type(ul(""))))
        self.assertTrue(self.fs.empty == ul(""))
        self.assertTrue(isinstance(self.fs.empty, type(ul(""))))

    def test_getcwd(self):
        wd = self.fs.getcwd()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('/'))
        self.assertTrue(wd.to_bytes() == b'/')
        self.assertTrue(isinstance(wd.to_bytes(), bytes))

    def test_getcroot(self):
        wd = self.fs.getcroot()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('/'))
        self.assertTrue(wd.to_bytes() == b'/')
        self.assertTrue(isinstance(wd.to_bytes(), bytes))

    def test_constructor(self):
        self.run_constructor()
        # as we don't support unc this should be False
        self.assertFalse(self.fs.getcroot().is_unc())

    def test_join(self):
        self.run_join()

    def test_split(self):
        self.run_split()

    def test_split_ext(self):
        self.run_split_ext()

    def test_abs(self):
        self.run_abs()
        self.run_realpath()
        self.run_normpath()

    def test_dirs(self):
        self.run_dirs()
        # check we can create the root
        path = self.fs('/')
        # benign call, should not raise an error
        path.makedirs()


class BinarySystem(vfs.MemFilePath):

    fs_name = "binfs.pyslet.org"
    supports_unicode_filenames = False
    sep = b"/"
    curdir = b"."
    pardir = b".."
    ext = b'.'
    drive_sep = b':'
    empty = b''

    # must override these to prevent mixed instances
    _wd = None
    _fsdir = {}


class BinarySystemTests(GeneralFilePathTests, unittest.TestCase):

    def setUp(self):    # noqa
        self.fs = BinarySystem

    def test_fs_data(self):
        self.assertTrue(self.fs.fs_name == "binfs.pyslet.org")
        self.assertFalse(self.fs.supports_unicode_filenames)

    def test_getcwd(self):
        wd = self.fs.getcwd()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('/'))
        self.assertTrue(wd.to_bytes() == b'/')
        self.assertTrue(isinstance(wd.to_bytes(), bytes))

    def test_getcroot(self):
        wd = self.fs.getcroot()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('/'))
        self.assertTrue(wd.to_bytes() == b'/')
        self.assertTrue(isinstance(wd.to_bytes(), bytes))

    def test_constructor(self):
        self.run_constructor()

    def test_join(self):
        self.run_join()

    def test_split(self):
        self.run_split()

    def test_split_ext(self):
        self.run_split_ext()

    def test_abs(self):
        self.run_abs()
        self.run_realpath()
        self.run_normpath()

    def test_dirs(self):
        self.run_dirs()


class DriveSystem(vfs.MemFilePath):

    fs_name = "drivefs.pyslet.org"
    supports_drives = True
    sep = ul("\\")

    # must override these to prevent mixed instances
    _wd = None
    _fsdir = {}


class DriveSystemTests(GeneralFilePathTests, unittest.TestCase):

    def setUp(self):    # noqa
        self.fs = DriveSystem
        self.fs._wd = DriveSystem("C:\\home")

    def test_fs_data(self):
        self.assertTrue(self.fs.fs_name == "drivefs.pyslet.org")
        self.assertTrue(self.fs.supports_drives)
        self.assertTrue(self.fs.sep == ul("\\"))
        self.assertTrue(isinstance(self.fs.sep, type(ul(""))))

    def test_getcwd(self):
        wd = self.fs.getcwd()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('C:\\home'))
        # the current drive letter is used to make a path absolute
        path = self.fs(ul('\\home'))
        self.assertTrue(path.isabs(), "Missing path letter still absolute")
        apath = path.abspath()
        self.assertTrue(apath != path, "Path should change for abspath")
        self.assertTrue(apath.splitdrive()[0] == ul('C:'))
        # check that the drive is not absolute
        self.assertFalse(apath.splitdrive()[0].isabs())

    def test_getcroot(self):
        wd = self.fs.getcroot()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('C:\\'))

    def test_constructor(self):
        self.run_constructor()

    def test_join(self):
        self.run_join()

    def test_split(self):
        self.run_split()

    def test_split_ext(self):
        self.run_split_ext()

    def test_abs(self):
        self.run_abs()
        self.run_realpath()
        self.run_normpath()

    def test_dirs(self):
        self.run_dirs()


class UNCSystem(vfs.MemFilePath):

    fs_name = "uncfs.pyslet.org"
    supports_drives = False
    supports_unc = True
    sep = ul("\\")

    # must override these to prevent mixed instances
    _wd = None
    _fsdir = {}


class UNCSystemTests(GeneralFilePathTests, unittest.TestCase):

    def setUp(self):    # noqa
        self.fs = UNCSystem
        self.fs._wd = UNCSystem("\\home")

    def test_fs_data(self):
        self.assertTrue(self.fs.fs_name == "uncfs.pyslet.org")
        self.assertTrue(self.fs.supports_unc)
        self.assertTrue(self.fs.sep == ul("\\"))
        self.assertTrue(isinstance(self.fs.sep, type(ul(""))))

    def test_getcwd(self):
        wd = self.fs.getcwd()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('\\home'))

    def test_getcroot(self):
        wd = self.fs.getcroot()
        self.assertTrue(isinstance(wd, self.fs))
        self.assertTrue(isinstance(wd, vfs.VirtualFilePath))
        self.assertTrue(to_text(wd) == ul('\\'))

    def test_unc(self):
        d = self.fs("\\home")
        unc, path = d.splitunc()
        self.assertTrue(unc == self.fs(''), "Not a UNC path")
        self.assertTrue(path == d)
        d = self.fs("\\\\host\\mount\\dir")
        self.assertTrue(d.is_unc())
        unc, path = d.splitunc()
        self.assertTrue(unc == self.fs("\\\\host\\mount"),
                        "UNC mount: %s" % unc)
        self.assertTrue(path == self.fs("\\dir"))
        self.assertFalse(path.is_unc())
        self.assertTrue(path.isabs())
        self.assertTrue(unc.is_unc())
        # can we split the mount from the host? should be able to
        host, mount = unc.split()
        self.assertTrue(host == self.fs("\\\\host"))
        self.assertFalse(host.is_unc())
        self.assertTrue(host.isabs())
        self.assertTrue(mount == self.fs("mount"))
        self.assertFalse(mount.is_unc())
        self.assertFalse(mount.isabs())
        slash, hostname = host.split()
        self.assertTrue(slash == self.fs("\\\\"), slash)
        self.assertFalse(slash.is_unc())
        self.assertTrue(slash.isabs())
        self.assertTrue(hostname == self.fs("host"))
        self.assertFalse(hostname.is_unc())
        self.assertFalse(hostname.isabs())
        slash_head, slash_tail = slash.split()
        self.assertTrue(slash_head == self.fs("\\\\"))
        self.assertFalse(slash_head.is_unc())
        self.assertTrue(slash_head.isabs())
        self.assertTrue(slash_tail == self.fs(""))
        self.assertFalse(slash_tail.is_unc())
        self.assertFalse(slash_tail.isabs())

    def test_constructor(self):
        self.run_constructor()

    def test_join(self):
        self.run_join()

    def test_split(self):
        self.run_split()

    def test_split_ext(self):
        self.run_split_ext()

    def test_abs(self):
        self.run_abs()
        self.run_realpath()
        self.run_normpath()

    def test_dirs(self):
        self.run_dirs()


class OSFilePathTests(GeneralFilePathTests, unittest.TestCase):

    def setUp(self):        # noqa
        self.fs = vfs.OSFilePath
        self.cwd = os.getcwd()
        data_path = os.path.join(os.path.split(__file__)[0], 'data_vfs')
        os.chdir(data_path)

    def tearDown(self):     # noqa
        os.chdir(self.cwd)

    def test_fs_data(self):
        self.assertTrue(
            issubclass(self.fs, vfs.VirtualFilePath),
            "OSFilePath subclass of VirtualFilePath abstract class")
        self.assertTrue(to_text(self.fs.curdir) == ".",
                        "Current directory component")
        self.assertTrue(to_text(self.fs.pardir) == "..",
                        "Parent directory component")

    def test_constructor(self):
        self.run_constructor()

    def test_cwd(self):
        cwd = self.fs.getcwd()
        self.assertTrue(isinstance(cwd, vfs.VirtualFilePath),
                        "getcwd returns VirtualFilePath")
        self.assertTrue(cwd.isdir(), "getcwd should return path with isdir")
        self.assertTrue(self.fs.isdir(cwd),
                        "getcwd should return path with isdir")
        self.assertTrue(cwd.exists(), "getcwd should return path with isdir")
        self.assertTrue(
            self.fs.exists(cwd), "getcwd should return path with isdir")
        new_dir = cwd.join('dir')
        new_dir.chdir()
        new_wd = self.fs.getcwd()
        self.assertTrue(new_wd == new_dir, "change directory")

    def test_join(self):
        self.run_join()

    def test_split(self):
        self.run_split()

    def test_split_ext(self):
        self.run_split_ext()

    def test_abs(self):
        self.run_abs()
        self.run_realpath()
        self.run_normpath()

    def test_walk(self):
        path = self.fs.getcwd()
        found_it = False
        for dirpath, dirnames, filenames in path.walk():
            if dirpath == path:
                found_it = True
        self.assertTrue(found_it, "Didn't get original path from walk")

    def test_open(self):
        path = self.fs.getcwd().join('hello.txt')
        f = path.open("rb")
        self.assertTrue(f.read() == b"Hello", "Open and read file")
        f.close()

    def test_default_fs(self):
        self.assertTrue(issubclass(vfs.defaultFS, vfs.VirtualFilePath))
        self.assertTrue(
            vfs.defaultFS is vfs.OSFilePath, "Default should be OS file path")
        self.assertTrue(vfs.defaultFS.fs_name == "")
        self.assertTrue(vfs.get_file_system_by_name('') is vfs.defaultFS)

    def test_dirs(self):
        self.run_dirs()

    def test_zip_hooks(self):
        st_orig = os.stat('hello.txt')
        path = self.fs.getcwd().join('hello.txt')
        f = None
        zh = vfs.ZipHooks()
        try:
            st = os.stat(path)
            self.assertTrue(
                st.st_mode == st_orig.st_mode, "Stat hook failed for mode")
            self.assertTrue(
                st.st_mtime == st_orig.st_mtime, "Stat hook failed for mtime")
            self.assertTrue(
                st.st_size == st_orig.st_size, "Stat size hook failed")
            f = open(path, "rb")
            data = f.read()
            self.assertTrue(data == b"Hello", "Open and read file: %s" % data)
        finally:
            if f:
                f.close()
            zh.unhook()
        dpath = None
        f = None
        zf = None
        with vfs.ZipHooks() as zh:
            with vfs.ZipHooks():
                try:
                    dpath = self.fs.mkdtemp('.d', 'test-')
                    zpath = dpath.join('hello.zip')
                    f = zpath.open("wb")
                    zf = zipfile.ZipFile(f, "w")
                    zf.write(path, 'hello.txt')
                    zf.close()
                    zf = None
                    f.close()
                    f = None
                    # now try and read the text back from the zip file
                    f = zpath.open("rb")
                    zf = zipfile.ZipFile(f, "r")
                    ef = zf.open('hello.txt')
                    self.assertTrue(
                        ef.read() == b"Hello", "Read back from zip file")
                finally:
                    if zf:
                        zf.close()
                    if f:
                        f.close()
                    if dpath:
                        dpath.rmtree(True)
        # check that builtin open function has returned to normal
        try:
            f = open(path)
            f.close()
            self.fail("open still hooked!")
        except:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
