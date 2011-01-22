import unittest

from metadata import *

def suite():
	return unittest.makeSuite(MetadataTest,'test')

class MetadataTest(unittest.TestCase):
	def testConstructor(self):
		md=QTIMetadata()
		self.failUnless(md.schema=="IMS QTI Item" and md.schemaVersion=="2.0")
	
if __name__ == "__main__":
	unittest.main()