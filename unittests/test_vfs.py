#! /usr/bin/env python
import unittest


from pyslet.vfs import *
import zipfile

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(VFSTests,'test')
		))

class VFSTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		dataPath=os.path.join(os.path.split(__file__)[0],'data_vfs')
		os.chdir(dataPath)

	def tearDown(self):
		os.chdir(self.cwd)
		
	def testConstructor(self):
		vfs=OSFilePath
		self.failUnless(issubclass(vfs,VirtualFilePath),"OSFilePath subclass of VirtualFilePath abstract class")
		self.failUnless(vfs.curdir==".","Current directory component")
		self.failUnless(vfs.pardir=="..","Parent directory component")
		path=vfs()
		self.failUnless(isinstance(path,VirtualFilePath),"VirtualFilePath abstract class")
		self.failUnless(path.IsEmpty(),"Empty path creation")
		self.failUnless(path.IsSingleComponent,"Empty path is a single component")
		self.failIf(path.IsDirLike(),"Empty path is not diretory like")		
		self.failIf(path.IsRoot(),"Empty path is not the root")
		self.failIf(path,"Non-zero test of empty path")
		path=vfs('hello')
		self.failIf(path.IsEmpty(),"Single path component")
		self.failUnless(path.IsSingleComponent,"Empty path is a single component")
		self.failIf(path.IsDirLike(),"Empty path is not diretory like")		
		self.failIf(path.IsRoot(),"Empty path is not the root")
		self.failUnless(str(path)=="hello","convert to str")
		self.failUnless(unicode(path)==u"hello","convert to unicode str")
		self.failUnless(path,"Non-zero test of non-empty path")
		path=vfs(u'Caf\xe9')
		self.failUnless(str(path)==u'Caf\xe9'.encode(sys.getfilesystemencoding()),"convert to str")
		self.failUnless(unicode(path)==u'Caf\xe9',"convert to unicode str")
		
	def testCWD(self):
		vfs=OSFilePath
		cwd=vfs.getcwd()	
		self.failUnless(isinstance(cwd,VirtualFilePath),"getcwd returns VirtualFilePath")
		self.failUnless(cwd.isdir(),"getcwd should return path with isdir")
		self.failUnless(vfs.isdir(cwd),"getcwd should return path with isdir")
		self.failUnless(cwd.exists(),"getcwd should return path with isdir")
		self.failUnless(vfs.exists(cwd),"getcwd should return path with isdir")
		newDir=cwd.join('dir')
		newDir.chdir()
		newWD=vfs.getcwd()
		self.failUnless(newWD==newDir,"change directory")
				
	def testSplit(self):
		vfs=OSFilePath
		path=vfs.getcwd()
		drive1,path1=vfs.splitdrive(path)
		drive2,path2=path.splitdrive()
		self.failUnless(drive1==drive2,"Drives don't match")
		self.failUnless(path1==path2,"Driveless paths don't match")
		while path is not None:
			# an empty path is 
			dPath,fPath=path.split()
			self.failUnless(vfs.split(path)==(dPath,fPath),"vfs.split(path) == path.split(), (%s)"%str(path))
			self.failUnless(isinstance(dPath,VirtualFilePath),"head not a VirtualFilePath (%s)"%str(path))
			self.failUnless(isinstance(fPath,VirtualFilePath),"tail not a VirtualFilePath (%s)"%str(path))
			self.failUnless(fPath.IsSingleComponent(),"The tail part will never contain a slash (%s)"%str(path))
			if path.IsEmpty():
				self.failUnless(dPath.IsEmpty() and fPath.IsEmpty(),"If path is empty, both head and tail are empty (%s)"%str(path)) 
				break
			if path.IsSingleComponent():
				self.failUnless(dPath.IsEmpty(),"If there is no slash in path, head will be empty (%s)"%str(path))
			if path.IsDirLike():
				self.failUnless(fPath.IsEmpty(),"If path ends in a slash, tail will be empty (%s)"%str(path))
			if not dPath.IsRoot():
				self.failIf(dPath.IsDirLike(),"Trailing slashes are stripped from head unless it is the root (one or more slashes only) (%s)"%str(path)) 
			path2=vfs.join(dPath,fPath)
			self.failUnless(path2==path,"vfs.join after split")
			path2=dPath.join(fPath)
			self.failUnless(path2==path,"path.join after split")
			path=dPath
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
		vfs=OSFilePath
		path=vfs.getcwd()
		path1=vfs.join(path,vfs('bye'))
		path2=vfs.join(path,vfs('hello'),path,vfs('bye'))
		self.failUnless(path1==path2,"If any component is an absolute path, all previous components are thrown away")
		path1=vfs.join(path,'bye')
		path2=vfs.join(path,'hello',path,'bye')
		self.failUnless(path1==path2,"Re-test with strings in join")
	
	def testSplitExt(self):
		vfs=OSFilePath
		path=vfs.getcwd().join('hello.txt')
		root,ext=path.splitext()
		self.failUnless(isinstance(root,VirtualFilePath),"Splitext root is a virtual file path")
		self.failUnless(type(ext) in StringTypes,"extension returns a string type")
		self.failUnless(str(root.split()[1])=="hello","root match")
		self.failUnless(ext==".txt","ext match")
				
	def testAbs(self):
		vfs=OSFilePath
		path=vfs.getcwd()
		self.failUnless(path.isabs(),"CWD not absolute")
		self.failUnless(vfs.isabs(path),"CWD not absolute, alternative")
		self.failUnless(path.abspath()==path,"Absolute path from cwd")		
		path=vfs('hello')
		self.failIf(path.isabs(),"path component not absolute")
		self.failIf(vfs.isabs(path),"path component not absolute, alternative")
		
	def testWalk(self):
		vfs=OSFilePath
		path=vfs.getcwd()
		foundIt=False
		for dirpath,dirnames,filenames in path.walk():
			if dirpath==path:
				foundIt=True
		self.failUnless(foundIt,"Didn't get original path from walk")

	def testOpen(self):
		vfs=OSFilePath
		path=vfs.getcwd().join('hello.txt')
		f=path.open("rb")
		self.failUnless(f.read()=="Hello","Open and read file")
		f.close()
				
	def testDefaultFS(self):
		self.failUnless(issubclass(defaultFS,VirtualFilePath))
		self.failUnless(defaultFS is OSFilePath,"Default should be OS file path")
		self.failUnless(defaultFS.fsName=="")
		self.failUnless(GetFileSystemByName('') is defaultFS)

	def testTempDir(self):
		vfs=OSFilePath
		dPath=vfs.mkdtemp('.d','test-')
		try:
			self.failUnless(isinstance(dPath,VirtualFilePath))
			self.failUnless(dPath.exists() and dPath.isdir())
			newPath=dPath.join("test-directory")
			self.failIf(newPath.exists() or newPath.isdir())
			newPath.mkdir()
			self.failUnless(newPath.exists() and newPath.isdir())
			deepPath=dPath.join("missing","dir")
			self.failIf(deepPath.exists() or deepPath.isdir())
			try:
				deepPath.mkdir()
				self.fail("Missing paraent test")
			except:
				pass
			deepPath.makedirs()
			self.failUnless(deepPath.exists() and deepPath.isdir())						
			newFile=newPath.join('hello')
			f=newFile.open('w')
			f.write("Hello")
			f.close()
			self.failUnless(newFile.exists() and newFile.isfile() and not newFile.isdir())
			newCopy=newPath.join('hello-again')
			self.failIf(newCopy.exists() or newCopy.isfile() or newCopy.isdir())			
			newFile.copy(newCopy)
			self.failUnless(newCopy.exists() and newCopy.isfile() and not newCopy.isdir())
			f=newCopy.open('r')
			data=f.read()
			f.close()
			self.failUnless(data=="Hello","Copy data test")
			newFile.remove()
			self.failIf(newFile.exists() or newFile.isfile() or newFile.isdir())			
			listing=dPath.listdir()
			found=False
			for node in listing:
				if "test-directory"==node:
					found=True
					break
			self.failUnless(found,"Couldn't find test-directory in new directory")
		finally:
			dPath.rmtree(True)


	def testZipHooks(self):
		stOrig=os.stat('hello.txt')
		vfs=OSFilePath
		path=vfs.getcwd().join('hello.txt')
		f=None
		zh=ZipHooks()
		try:
			st=os.stat(path)
			self.failUnless(st.st_mode==stOrig.st_mode,"Stat hook failed for mode")
			self.failUnless(st.st_mtime==stOrig.st_mtime,"Stat hook failed for mtime")
			self.failUnless(st.st_size==stOrig.st_size,"Stat size hook failed")
			f=open(path,"rb")
			data=f.read()
			self.failUnless(data=="Hello","Open and read file: %s"%data)
		finally:
			if f:
				f.close()			
			zh.Unhook()		
		dPath=None
		f=None
		zf=None
		with ZipHooks() as zh:
			with ZipHooks() as zh2:
				try:
					dPath=vfs.mkdtemp('.d','test-')
					zpath=dPath.join('hello.zip')
					f=zpath.open("w")
					zf=zipfile.ZipFile(f,"w")
					zf.write(path,'hello.txt')
					zf.close()
					zf=None
					f.close()
					f=None
					# now try and read the text back from the zip file			
					f=zpath.open("r")
					zf=zipfile.ZipFile(f,"r")
					ef=zf.open('hello.txt')
					self.failUnless(ef.read()=="Hello","Read back from zip file")
				finally:
					if zf:
						zf.close()
					if f:
						f.close()
					if dPath:
						dPath.rmtree(True)
		# check that builtin open function has returned to normal
		try:
			f=open(path)
			f.close()
			self.fail("open still hooked!")
		except:
			pass

					
if __name__ == "__main__":
	unittest.main()