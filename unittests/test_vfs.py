#! /usr/bin/env python
import unittest


from pyslet.vfs import *
import zipfile


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(VFSTests, 'test')
    ))


class VFSTests(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        dataPath = os.path.join(os.path.split(__file__)[0], 'data_vfs')
        os.chdir(dataPath)

    def tearDown(self):
        os.chdir(self.cwd)

    def testConstructor(self):
        vfs = OSFilePath
        self.assertTrue(issubclass(vfs, VirtualFilePath),
                        "OSFilePath subclass of VirtualFilePath abstract class")
        self.assertTrue(vfs.curdir == ".", "Current directory component")
        self.assertTrue(vfs.pardir == "..", "Parent directory component")
        path = vfs()
        self.assertTrue(
            isinstance(path, VirtualFilePath), "VirtualFilePath abstract class")
        self.assertTrue(path.IsEmpty(), "Empty path creation")
        self.assertTrue(
            path.IsSingleComponent, "Empty path is a single component")
        self.assertFalse(path.IsDirLike(), "Empty path is not diretory like")
        self.assertFalse(path.IsRoot(), "Empty path is not the root")
        self.assertFalse(path, "Non-zero test of empty path")
        path = vfs('hello')
        self.assertFalse(path.IsEmpty(), "Single path component")
        self.assertTrue(
            path.IsSingleComponent, "Empty path is a single component")
        self.assertFalse(path.IsDirLike(), "Empty path is not diretory like")
        self.assertFalse(path.IsRoot(), "Empty path is not the root")
        self.assertTrue(str(path) == "hello", "convert to str")
        self.assertTrue(unicode(path) == u"hello", "convert to unicode str")
        self.assertTrue(path, "Non-zero test of non-empty path")
        path = vfs(u'Caf\xe9')
        self.assertTrue(str(path) == u'Caf\xe9'.encode(
            sys.getfilesystemencoding()), "convert to str")
        self.assertTrue(unicode(path) == u'Caf\xe9', "convert to unicode str")

    def testCWD(self):
        vfs = OSFilePath
        cwd = vfs.getcwd()
        self.assertTrue(
            isinstance(cwd, VirtualFilePath), "getcwd returns VirtualFilePath")
        self.assertTrue(cwd.isdir(), "getcwd should return path with isdir")
        self.assertTrue(vfs.isdir(cwd), "getcwd should return path with isdir")
        self.assertTrue(cwd.exists(), "getcwd should return path with isdir")
        self.assertTrue(
            vfs.exists(cwd), "getcwd should return path with isdir")
        newDir = cwd.join('dir')
        newDir.chdir()
        newWD = vfs.getcwd()
        self.assertTrue(newWD == newDir, "change directory")

    def testSplit(self):
        vfs = OSFilePath
        path = vfs.getcwd()
        drive1, path1 = vfs.splitdrive(path)
        drive2, path2 = path.splitdrive()
        self.assertTrue(drive1 == drive2, "Drives don't match")
        self.assertTrue(path1 == path2, "Driveless paths don't match")
        while path is not None:
            # an empty path is
            dPath, fPath = path.split()
            self.assertTrue(vfs.split(path) == (
                dPath, fPath), "vfs.split(path) == path.split(), (%s)" % str(path))
            self.assertTrue(isinstance(dPath, VirtualFilePath),
                            "head not a VirtualFilePath (%s)" % str(path))
            self.assertTrue(isinstance(fPath, VirtualFilePath),
                            "tail not a VirtualFilePath (%s)" % str(path))
            self.assertTrue(fPath.IsSingleComponent(
            ), "The tail part will never contain a slash (%s)" % str(path))
            if path.IsEmpty():
                self.assertTrue(dPath.IsEmpty() and fPath.IsEmpty(
                ), "If path is empty, both head and tail are empty (%s)" % str(path))
                break
            if path.IsSingleComponent():
                self.assertTrue(
                    dPath.IsEmpty(), "If there is no slash in path, head will be empty (%s)" % str(path))
            if path.IsDirLike():
                self.assertTrue(
                    fPath.IsEmpty(), "If path ends in a slash, tail will be empty (%s)" % str(path))
            if not dPath.IsRoot():
                self.assertFalse(dPath.IsDirLike(
                ), "Trailing slashes are stripped from head unless it is the root (one or more slashes only) (%s)" % str(path))
            path2 = vfs.join(dPath, fPath)
            self.assertTrue(path2 == path, "vfs.join after split")
            path2 = dPath.join(fPath)
            self.assertTrue(path2 == path, "path.join after split")
            path = dPath
            if path.IsRoot():
                break

    def testJoin(self):
        """Join one or more path components intelligently. If any component is
        an absolute path, all previous components (on Windows, including the
        previous drive letter, if there was one) are thrown away, and joining
        continues. The return value is the concatenation of path1, and
        optionally path2, etc., with exactly one directory separator (os.sep)
        inserted between components, unless path2 is empty. Note that on
        Windows, since there is a current directory for each drive,
        os.path.join("c:", "foo") represents a path relative to the current
        directory on drive C: (c:foo), not c:\\foo."""
        vfs = OSFilePath
        path = vfs.getcwd()
        path1 = vfs.join(path, vfs('bye'))
        path2 = vfs.join(path, vfs('hello'), path, vfs('bye'))
        self.assertTrue(
            path1 == path2, "If any component is an absolute path, all previous components are thrown away")
        path1 = vfs.join(path, 'bye')
        path2 = vfs.join(path, 'hello', path, 'bye')
        self.assertTrue(path1 == path2, "Re-test with strings in join")

    def testSplitExt(self):
        vfs = OSFilePath
        path = vfs.getcwd().join('hello.txt')
        root, ext = path.splitext()
        self.assertTrue(
            isinstance(root, VirtualFilePath), "Splitext root is a virtual file path")
        self.assertTrue(
            type(ext) in StringTypes, "extension returns a string type")
        self.assertTrue(str(root.split()[1]) == "hello", "root match")
        self.assertTrue(ext == ".txt", "ext match")

    def testAbs(self):
        vfs = OSFilePath
        path = vfs.getcwd()
        self.assertTrue(path.isabs(), "CWD not absolute")
        self.assertTrue(vfs.isabs(path), "CWD not absolute, alternative")
        self.assertTrue(path.abspath() == path, "Absolute path from cwd")
        path = vfs('hello')
        self.assertFalse(path.isabs(), "path component not absolute")
        self.assertFalse(
            vfs.isabs(path), "path component not absolute, alternative")

    def testWalk(self):
        vfs = OSFilePath
        path = vfs.getcwd()
        foundIt = False
        for dirpath, dirnames, filenames in path.walk():
            if dirpath == path:
                foundIt = True
        self.assertTrue(foundIt, "Didn't get original path from walk")

    def testOpen(self):
        vfs = OSFilePath
        path = vfs.getcwd().join('hello.txt')
        f = path.open("rb")
        self.assertTrue(f.read() == "Hello", "Open and read file")
        f.close()

    def testDefaultFS(self):
        self.assertTrue(issubclass(defaultFS, VirtualFilePath))
        self.assertTrue(
            defaultFS is OSFilePath, "Default should be OS file path")
        self.assertTrue(defaultFS.fsName == "")
        self.assertTrue(GetFileSystemByName('') is defaultFS)

    def testTempDir(self):
        vfs = OSFilePath
        dPath = vfs.mkdtemp('.d', 'test-')
        try:
            self.assertTrue(isinstance(dPath, VirtualFilePath))
            self.assertTrue(dPath.exists() and dPath.isdir())
            newPath = dPath.join("test-directory")
            self.assertFalse(newPath.exists() or newPath.isdir())
            newPath.mkdir()
            self.assertTrue(newPath.exists() and newPath.isdir())
            deepPath = dPath.join("missing", "dir")
            self.assertFalse(deepPath.exists() or deepPath.isdir())
            try:
                deepPath.mkdir()
                self.fail("Missing paraent test")
            except:
                pass
            deepPath.makedirs()
            self.assertTrue(deepPath.exists() and deepPath.isdir())
            newFile = newPath.join('hello')
            f = newFile.open('w')
            f.write("Hello")
            f.close()
            self.assertTrue(
                newFile.exists() and newFile.isfile() and not newFile.isdir())
            newCopy = newPath.join('hello-again')
            self.assertFalse(
                newCopy.exists() or newCopy.isfile() or newCopy.isdir())
            newFile.copy(newCopy)
            self.assertTrue(
                newCopy.exists() and newCopy.isfile() and not newCopy.isdir())
            f = newCopy.open('r')
            data = f.read()
            f.close()
            self.assertTrue(data == "Hello", "Copy data test")
            newFile.remove()
            self.assertFalse(
                newFile.exists() or newFile.isfile() or newFile.isdir())
            listing = dPath.listdir()
            found = False
            for node in listing:
                if "test-directory" == node:
                    found = True
                    break
            self.assertTrue(
                found, "Couldn't find test-directory in new directory")
        finally:
            dPath.rmtree(True)

    def testZipHooks(self):
        stOrig = os.stat('hello.txt')
        vfs = OSFilePath
        path = vfs.getcwd().join('hello.txt')
        f = None
        zh = ZipHooks()
        try:
            st = os.stat(path)
            self.assertTrue(
                st.st_mode == stOrig.st_mode, "Stat hook failed for mode")
            self.assertTrue(
                st.st_mtime == stOrig.st_mtime, "Stat hook failed for mtime")
            self.assertTrue(
                st.st_size == stOrig.st_size, "Stat size hook failed")
            f = open(path, "rb")
            data = f.read()
            self.assertTrue(data == "Hello", "Open and read file: %s" % data)
        finally:
            if f:
                f.close()
            zh.Unhook()
        dPath = None
        f = None
        zf = None
        with ZipHooks() as zh:
            with ZipHooks() as zh2:
                try:
                    dPath = vfs.mkdtemp('.d', 'test-')
                    zpath = dPath.join('hello.zip')
                    f = zpath.open("w")
                    zf = zipfile.ZipFile(f, "w")
                    zf.write(path, 'hello.txt')
                    zf.close()
                    zf = None
                    f.close()
                    f = None
                    # now try and read the text back from the zip file
                    f = zpath.open("r")
                    zf = zipfile.ZipFile(f, "r")
                    ef = zf.open('hello.txt')
                    self.assertTrue(
                        ef.read() == "Hello", "Read back from zip file")
                finally:
                    if zf:
                        zf.close()
                    if f:
                        f.close()
                    if dPath:
                        dPath.rmtree(True)
        # check that builtin open function has returned to normal
        try:
            f = open(path)
            f.close()
            self.fail("open still hooked!")
        except:
            pass


if __name__ == "__main__":
    unittest.main()
