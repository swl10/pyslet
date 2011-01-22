import unittest
import os.path
from os import getcwd

from rfc1738 import *

def suite():
	return unittest.TestSuite([
		unittest.makeSuite(FileSchemeTests,'test')
		])

class FileSchemeTests(unittest.TestCase):
	def testFileURL(self):
		"""Test path to URL conversion functions"""
		cwd=getcwd()
		result=URLToFilePath(FilePathToURL(cwd))
		self.failUnless(result==cwd,"Two-way conversion fail %s -> %s"%(cwd,result))


if __name__ == "__main__":
	unittest.main()