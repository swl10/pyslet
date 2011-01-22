import unittest

from iso639 import *

def suite():
	return unittest.makeSuite(ISO639LanguageTests)

class ISO639LanguageTests(unittest.TestCase):
	def testCodeType(self):
		"""Test the GetCodeType function"""
		self.failUnless(GetISO639CodeType("ENG")==ISO639BibliographicCode,"bib code, upper case")
		self.failUnless(GetISO639CodeType("wel")==ISO639BibliographicCode,"bib code, lower case")
		self.failUnless(GetISO639CodeType("cym")==ISO639TerminologicCode,"term code")
		self.failUnless(GetISO639CodeType("qqq")==ISO639ReservedCode,"reserved code")
		self.failUnless(GetISO639CodeType("en")==ISO639Alpha2Code,"alpha2 code, lower case")
		self.failUnless(GetISO639CodeType("zzz")==ISO639UnknownCode,"unknown code")
		
	def testAlpha2Mapping(self):
		"""Check the GetISO639Alpha2Code function"""
		self.failUnless(GetISO639Alpha2Code("ENG")=="en" and GetISO639Alpha2Code("cor")=="kw","success test")
		self.failUnless(GetISO639Alpha2Code("cym")=="cy" and GetISO639Alpha2Code("wel")=="cy","bib/term success test")
		self.failIf(GetISO639Alpha2Code("grc") or GetISO639Alpha2Code("enm"),"fail test")
		self.failIf(GetISO639Alpha2Code("qqq"),"reserved language test")
		self.failIf(GetISO639Alpha2Code("pzz"),"non-existent language test")
		self.failUnless(GetISO639Alpha2Code("en")=="en","trivial test")
	
	def testBibMapping(self):
		"""Check the GetISO639BibCode function"""
		# Test English and Cornish
		self.failUnless(GetISO639BibCode("en")=="eng" and GetISO639BibCode("kw")=="cor","part 1 code success test")
		# Test Welsh
		self.failUnless(GetISO639BibCode("cym")=="wel","term code success test")
		self.failUnless(GetISO639BibCode("qqq")=="qqq","reserved language test")
		self.failIf(GetISO639BibCode("zz"),"non-existent language test")
		self.failUnless(GetISO639BibCode("eng")=="eng","trivial test")
	
	def testTermMapping(self):
		"""Check the GetISO639TermCode function"""
		self.failUnless(GetISO639TermCode("cy")=="cym" and GetISO639TermCode("zh")=="zho","part 1 code success test")
		self.failUnless(GetISO639TermCode("wel")=="cym" and GetISO639TermCode("chi")=="zho","bib code success test")
		self.failIf(GetISO639TermCode("qqq"),"reserved language test")
		self.failIf(GetISO639TermCode("zz"),"non-existent language test")
		self.failUnless(GetISO639TermCode("cym")=="cym","trivial test")
	
	def testCanonicalization(self):
		"""Check the GetISO639CanonicalCode function, returns part1 code, term code or ultimately bib code"""
		self.failUnless(GetISO639CanonicalCode("ENG")=="en" and GetISO639CanonicalCode("Grc")=="grc","success test")
		self.failIf(GetISO639CanonicalCode("pzz") or GetISO639CanonicalCode("qua"),"non-existent language test")
		self.failUnless(GetISO639CanonicalCode("qaa")=="qaa" and GetISO639CanonicalCode("qqq")=="qqq" and
			GetISO639CanonicalCode("qtz")=="qtz","reserved code test")
		# Note there are no terminologic codes with no corresponding part 1 code
		self.failUnless(GetISO639CanonicalCode("cym")=="cy","term code test")
		self.failUnless(GetISO639CanonicalCode("en")=="en","trivial test")
		
	def testNameLookups(self):
		"""Check the GetISO639EnglishName and GetISO639FrenchName functions"""
		self.failUnless(GetISO639EnglishName("En")=="English" or GetISO639FrenchName("en")=="anglais","part 1 code")
		self.failUnless(GetISO639EnglishName("eng")=="English" or GetISO639FrenchName("ENG")=="anglais","part 2 code")
		self.failUnless(GetISO639EnglishName("cym")=="Welsh","term code")
		self.failUnless(GetISO639EnglishName("enm")=="English, Middle (1100-1500)","part 2 only code")
		self.failUnless(GetISO639FrenchName("frm")==u'fran\xe7ais moyen (1400-1800)',"non-ascii response")
		self.failUnless(GetISO639EnglishName("qqq") and GetISO639FrenchName("qqq"),"reserved code test")
		self.failIf(GetISO639EnglishName("pzz") or GetISO639FrenchName("pzz"),"non-existent language test")
		
if __name__ == "__main__":
	unittest.main()