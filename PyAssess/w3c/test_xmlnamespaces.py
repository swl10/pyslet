import unittest

from xmlnamespaces import *
from xml import IsLetter, IsDigit, IsCombiningChar, IsExtender

def suite():
	return unittest.makeSuite(NamespaceTests,'test')

class NamespaceTests(unittest.TestCase):
	def testNCNameChar(self):
		gotLetter=0
		gotDigit=0
		gotCombiningChar=0
		gotExtender=0
		for code in xrange(0x10000):
			c=unichr(code)
			if IsLetter(c):
				gotLetter=1			
			elif IsDigit(c):
				gotDigit=1
			elif IsCombiningChar(c):
				gotCombiningChar=1
			elif IsExtender(c):
				gotExtender=1
			elif not c in ".-_":
				self.failIf(IsNCNameChar(c))
				continue
			self.failUnless(IsNCNameChar(c))
			if code>255 and gotLetter and gotDigit and gotCombiningChar and gotExtender:
				# we don't check every character (boring)
				break

	def testNCName(self):
		self.failIf(CheckNCName(".hi"),"leading .")
		self.failIf(CheckNCName("-hi"),"leading hyphen")
		self.failIf(CheckNCName("1hi"),"leading digit")
		self.failIf(CheckNCName("m:element"),"colon")
		self.failUnless(CheckNCName("a0-_."),"various")
		self.failUnless(CheckNCName("_a"),"leading underscore")
	
	def testXMLNamespace(self):
		self.failUnless(XMLNamespace=="http://www.w3.org/XML/1998/namespace","xml namespace constant")	
		
if __name__ == "__main__":
	unittest.main()