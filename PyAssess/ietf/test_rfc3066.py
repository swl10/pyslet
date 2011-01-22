import unittest
from types import *

from rfc3066 import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(LanguageTagTests),
		unittest.makeSuite(LanguageRangeTests)
		))
		

GOOD_LANGUAGES=["en","qqq","i","x",unicode("en-GB"),"en-GB1"]
BAD_LANGUAGES=["a","zzzz",u'en-caf\xe9',"en-GB-xxxxxxxxx","en-x","franglais","en-GB-steve's","wel","1","*"]

class LanguageTagTests(unittest.TestCase):
	def testConstructor(self):
		"""Check LanguageTag constructor and non-zero test"""
		lang=LanguageTag()
		self.failUnless(not lang,'empty constructor')
		try:
			LanguageTag(3.14159)
			self.fail('bad type to constructor')
		except TypeError:
			pass
		for good in GOOD_LANGUAGES:
			LanguageTag(good)
		for bad in BAD_LANGUAGES:
			try:
				lang=LanguageTag(bad)
				self.fail('constructor should fail for '+str(bad))
			except RFCSyntaxError:
				pass
			except RFC3066Error:
				pass
		lang=LanguageTag("en-GB")
		self.failUnless(LanguageTag(lang)==lang,"copy constructor test")

	def testStr(self):
		"""Check LanguageTag str method"""
		self.failUnless(str(LanguageTag("en-GB"))=="en-GB","basic test")
		self.failUnless(str(LanguageTag("EN"))=="EN","case preserve test")
		self.failUnless(str(LanguageTag())=="","empty test")
		
	def testRepr(self):
		"""Check LanguageTag repr method"""
		self.failUnless(repr(LanguageTag("en-GB"))=="LanguageTag('en-GB')","basic test")
		self.failUnless(repr(LanguageTag("En"))=="LanguageTag('En')","case preserve test")
		self.failUnless(repr(LanguageTag())=="LanguageTag()","empty test")
	
	def testCmp(self):
		"""Check the LanguageTag comparison method"""
		self.failUnless(LanguageTag("en")==LanguageTag("EN"),"primary-tag mixed-case cmp")		
		self.failUnless(LanguageTag("en-GB")==LanguageTag("en-gb"),"country-code mixed-case cmp")
		self.failUnless(LanguageTag("en")<LanguageTag("fr") and \
			LanguageTag("FR")>LanguageTag("en"),"sort order")
			
	def testCanonicalize(self):
		"""Check the LanguageTag canonicalization method"""
		lang=LanguageTag("en-gb-Estuary")
		lang.Canonicalize()
		self.failUnless(str(lang)=="en-GB-estuary")

class LanguageRangeTests(unittest.TestCase):
	def testConstructor(self):
		"""Check LanguageRange constructor and non-zero test"""
		langRange=LanguageRange()
		self.failUnless(not langRange,'empty constructor')
		# All the good languages are also language ranges
		for good in GOOD_LANGUAGES:
			LanguageRange(good)
		# All the bad languages except the wildcard are bad language ranges
		for bad in BAD_LANGUAGES:
			try:
				if bad!="*":
					langRange=LanguageRange(bad)
					self.fail('constructor should fail for '+str(bad))
			except RFCSyntaxError:
				pass
			except RFC3066Error:
				pass
	
	def testStr(self):
		"""Check LanguageRange str method"""
		self.failUnless(str(LanguageRange("en-GB"))=="en-GB","basic test")
		self.failUnless(str(LanguageRange("EN"))=="en","force case test")
		self.failUnless(str(LanguageRange("*"))=="*","wildcard test")
		self.failUnless(str(LanguageRange())=="","empty test")
	
	def testRepr(self):
		"""Check LanguageRange repr method"""
		self.failUnless(repr(LanguageRange("en-GB"))=="LanguageRange('en-GB')","basic test")
		self.failUnless(repr(LanguageRange("En"))=="LanguageRange('en')","force preserve test")
		self.failUnless(repr(LanguageRange("*"))=="LanguageRange('*')","wildcard test")

	def testMatch(self):
		"""Check the LanguageRange MatchLanguage method"""
		langRange=LanguageRange("*")
		for good in GOOD_LANGUAGES:
			self.failUnless(langRange.MatchLanguage(LanguageTag(good)))
		self.failUnless(LanguageRange("en").MatchLanguage("en-GB"))
		self.failUnless(LanguageRange("en-gb").MatchLanguage("en-GB"))
		self.failIf(LanguageRange("en-GB").MatchLanguage("en"))
		self.failIf(LanguageRange("en-GB").MatchLanguage("en-US"))
		

if __name__ == "__main__":
	unittest.main()