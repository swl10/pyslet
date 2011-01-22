import unittest
from types import *

from p1484_12 import *
from PyAssess.iso.iso8601 import Date

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(LOMTests,'test'),
		unittest.makeSuite(LOMGeneralTests,'test'),
		unittest.makeSuite(LOMLifeCycleTests,'test'),
		unittest.makeSuite(LOMLifeCycleContributeTests,'test'),
		unittest.makeSuite(LOMMetaMetadataTests,'test'),
		unittest.makeSuite(LOMMetadataContributeTests,'test'),
		unittest.makeSuite(LOMEducationalTests,'test'),
		unittest.makeSuite(LOMMetaMetadataTests,'test'),
		unittest.makeSuite(LOMStringTests,'test'),
		unittest.makeSuite(LOMLangStringTests,'test'),
		unittest.makeSuite(LOMVocabularyTests,'test'),
		unittest.makeSuite(LOMDateTimeTests,'test')
		))
		
BAD_STRING="Macintosh Pie \xb9"
SAMPLE_LANGUAGE="en"
SAMPLE_STRING_1=u"Hello"
SAMPLE_STRING_2="Hello"
LONG_LANGUAGE="en-GB-xxxx"+"-xxxxxxxx"*110

## ISSN number for ALT-J
SAMPLE_CATALOG_1=u"ISSN"
SAMPLE_ENTRY_1=u"0968-7769"

## ISBN number for Extreme Programming Explained
SAMPLE_CATALOG_2="ISBN"
SAMPLE_ENTRY_2="0-201-61641-6"

SAMPLE_VCARD="""BEGIN:VCARD
FN:Joe Friday
TEL:+1-919-555-7878
TITLE:Area Administrator\\,Assistant
EMAIL;TYPE=INTERN
 ET:jfriday@host.com
END:VCARD
"""

class LOMTests(unittest.TestCase):
	def setUp(self):
		self.lom=LOMMetadata()
	
	def tearDown(self):
		pass
	
	def RunIdentifierTests(self,addMethod,getEntriesMethod,container,fieldName,maxTest):
		# Empty test
		self.failIf(container)
		# Add an empty identifier, should still be empty
		addMethod(LOMIdentifier())
		self.failUnless(len(getattr(container,fieldName))==0)
		# Check the max
		for entry in range(maxTest):
			addMethod(LOMIdentifier(str(entry),'TEST'))
		self.failUnless(len(getattr(container,fieldName))==maxTest)
		# shoudl result in non-empty container too
		self.failUnless(container,'nonzero test')
		# clean the identifiers ready for getEntriesMethod
		del getattr(container,fieldName)[:]
		for entry in range(2):
			addMethod(LOMIdentifier("ko"+str(entry),'TEST1'))
		for entry in range(2):
			addMethod(LOMIdentifier("ok"+str(entry),'TEST2'))
		idList=getEntriesMethod('TEST2')
		idList.sort()
		self.failUnless(idList==['ok0','ok1'])
	
	def RunLanguageTests(self,addMethod,container,fieldName,maxTest):
		addMethod("en-GB")
		self.failUnless(container,'nonzero test')
		self.failUnless(repr(getattr(container,fieldName))=="[LanguageTag('en-GB')]")
		addMethod(LanguageTag("fr"))
		addMethod("")
		self.failUnless(len(getattr(container,fieldName))==2)
		for i in range(maxTest-2):
			addMethod("en-US-state"+str(i))
		self.failUnless(len(getattr(container,fieldName))==maxTest)
	
	def RunSingleLangStringTests(self,setMethod,container,fieldName):
		setMethod("Hello")
		self.failUnless(container,'nonzero test')
		self.failUnless(repr(getattr(container,fieldName))=="LOMLangString([LOMString(None, u'Hello')])")
		setMethod(LOMLangString([LOMString('en','Hello'),LOMString('fr','bonjour')]))
		self.failUnless(len(getattr(container,fieldName))==2)
		setMethod(None)
		self.failIf(container,"return to zero test")
	
	def RunLangStringTests(self,addMethod,container,fieldName,maxTest):
		addMethod("Hello")
		self.failUnless(container,'nonzero test')
		self.failUnless(repr(getattr(container,fieldName))=="[LOMLangString([LOMString(None, u'Hello')])]")
		addMethod("")
		self.failUnless(len(getattr(container,fieldName))==1)
		for i in range(maxTest-1):
			addMethod("Test "+str(i))
		self.failUnless(len(getattr(container,fieldName))==maxTest)
		
	def RunSingleVocabularyFieldTest(self,setMethod,container,fieldName,goodValue):
		setMethod("Hello")
		self.failUnless(container,'nonzero test')
		self.failUnless(repr(getattr(container,fieldName))=="LOMVocabulary(u'Hello', None)")
		setMethod(LOMVocabulary(goodValue,"LOMv1.0"))
		try:
			setMethod(LOMVocabulary("weird","LOMv1.0"))
			self.fail("vocabulary test")
		except LOMError:
			pass
		setMethod(None)
		self.failIf(container,"return to zero test")

	def RunVocabularyFieldTests(self,addMethod,container,fieldName,goodValue,maxTest):
		addMethod("Hello")
		self.failUnless(len(getattr(container,fieldName))==1,'nonzero test')
		self.failUnless(repr(getattr(container,fieldName)[0])=="LOMVocabulary(u'Hello', None)")
		addMethod(LOMVocabulary(goodValue,"LOMv1.0"))
		try:
			addMethod(LOMVocabulary("weird","LOMv1.0"))
			self.fail("vocabulary test")
		except LOMError:
			pass
		for i in xrange(maxTest-2):
			addMethod("Test%02i"%i)
		self.failUnless(len(getattr(container,fieldName))==maxTest)

	def RunSingleDateFieldTest(self,setMethod,container,fieldName):
		setMethod(LOMDateTime("2001-08-23"))
		self.failUnless(container,'nonzero test')
		self.failUnless(getattr(container,fieldName).dateTime==Date("2001-08-23"),'date only')
		setMethod(LOMDateTime("1997-07-16T19:20:30+01:00"))
		self.failUnless(getattr(container,fieldName).dateTime==TimePoint("1997-07-16T19:20:30+01:00"),'full timepoint')
		setMethod(LOMDateTime("2001-08-23","Hello"))
		self.failUnless(repr(getattr(container,fieldName).description)=="LOMLangString([LOMString(None, u'Hello')])",
			"description test")
		setMethod(None)
		self.failIf(container,"return to zero test")

	def RunSingleDurationFieldTest(self,setMethod,container,fieldName):
		setMethod(LOMDuration("PT1H30M"))
		self.failUnless(container,'nonzero test')
		self.failUnless(getattr(container,fieldName).duration==Duration("PT1H30M"),'duration')
		setMethod(LOMDuration("PT1H30M","90 minutes"))
		self.failUnless(repr(getattr(container,fieldName).description)=="LOMLangString([LOMString(None, u'90 minutes')])",
			"description test")
		setMethod(None)
		self.failIf(container,"return to zero test")

class LOMGeneralTests(LOMTests):
	def testIdentifier(self):
		"""Check AddIdentifier and GetCatalogEntries"""
		self.RunIdentifierTests(self.lom.general.AddIdentifier,self.lom.general.GetCatalogEntries,
			self.lom.general,'identifier',10)
			
	def testTitle(self):
		"""Check the SetTitle method"""
		self.RunSingleLangStringTests(self.lom.general.SetTitle,self.lom.general,'title')

	def testLanguage(self):
		"""Check the AddLanguage method"""
		self.RunLanguageTests(self.lom.general.AddLanguage,self.lom.general,'language',10)
		
	def testLanguageOld(self):
		"""Check the AddLanguage method"""
		self.lom.general.AddLanguage("en-GB")
		self.failUnless(self.lom.general,'nonzero test')
		self.failUnless(repr(self.lom.general.language)=="[LanguageTag('en-GB')]")
		self.lom.general.AddLanguage(LanguageTag("fr"))
		self.lom.general.AddLanguage("")
		self.failUnless(len(self.lom.general.language)==2)
		for i in range(8):
			self.lom.general.AddLanguage("en-US-state"+str(i))
		self.failUnless(len(self.lom.general.language)==10)
			
	def testDescription(self):
		"""Check the AddDescription method"""
		self.RunLangStringTests(self.lom.general.AddDescription,self.lom.general,'description',10)
			
	def testKeyword(self):
		"""Check the AddKeyword method"""
		self.RunLangStringTests(self.lom.general.AddKeyword,self.lom.general,'keyword',10)

	def testCoverage(self):
		"""Check the AddCoverage method"""
		self.RunLangStringTests(self.lom.general.AddCoverage,self.lom.general,'coverage',10)
						
	def testDescription(self):
		"""Check the AddDescription method"""
		self.RunLangStringTests(self.lom.general.AddDescription,self.lom.general,'description',10)
			
	def testStructure(self):
		"""Check the SetStructure method"""
		self.RunSingleVocabularyFieldTest(self.lom.general.SetStructure,self.lom.general,'structure','networked')
		
	def testAggregationLevel(self):
		"""Check the SetAggregationLevel method"""
		self.RunSingleVocabularyFieldTest(self.lom.general.SetAggregationLevel,self.lom.general,'aggregationLevel','1')


class LOMLifeCycleTests(LOMTests):
	def testVersion(self):
		self.RunSingleLangStringTests(self.lom.lifeCycle.SetVersion,self.lom.lifeCycle,'version')
		
	def testStatus(self):
		self.RunSingleVocabularyFieldTest(self.lom.lifeCycle.SetStatus,self.lom.lifeCycle,'status','draft')
		
	def testContribute(self):
		c1=LOMLifeCycleContribute()
		c1.SetRole("author")
		self.failUnless(not self.lom.lifeCycle,'zero test')
		self.lom.lifeCycle.AddContribute(c1)
		self.failUnless(self.lom.lifeCycle,'nonzero test')
		self.failUnless(len(self.lom.lifeCycle.contribute)==1 and self.lom.lifeCycle.contribute[0].role.value=="author")
		c2=LOMLifeCycleContribute()
		self.lom.lifeCycle.AddContribute(c2)
		self.failUnless(len(self.lom.lifeCycle.contribute)==1,"add empty contribute")
		for i in xrange(29):
			c=LOMLifeCycleContribute()
			c.SetDate(LOMDateTime(None,"contributor number %i"%(i+2)))
			self.lom.lifeCycle.AddContribute(c)
		self.failUnless(len(self.lom.lifeCycle.contribute)==30)


class LOMLifeCycleContributeTests(LOMTests):
	def setUp(self):
		self.contribute=LOMLifeCycleContribute()
		
	def testStructure(self):
		"""Check the SetRole method"""
		self.RunSingleVocabularyFieldTest(self.contribute.SetRole,self.contribute,'role','content provider')
		
	def testEntity(self):
		"""Check the AddEntity method"""
		self.contribute.AddEntity(SAMPLE_VCARD)
		self.failUnless(self.contribute,"non-zero test")
		self.failUnless(len(self.contribute.entity)==1,"entity length test")
		self.contribute.AddEntity(SAMPLE_VCARD)
		self.failUnless(len(self.contribute.entity)==2,"entity length test")
		for i in xrange(38):
			self.contribute.AddEntity(SAMPLE_VCARD)
		self.failUnless(len(self.contribute.entity)==40,"max entity test")
		
	def testDate(self):
		"""Check the SetDate method"""
		self.RunSingleDateFieldTest(self.contribute.SetDate,self.contribute,'date')


class LOMMetaMetadataTests(LOMTests):
	def testIdentifier(self):
		"""Check AddIdentifier and GetCatalogEntries"""
		self.RunIdentifierTests(self.lom.metaMetadata.AddIdentifier,self.lom.metaMetadata.GetCatalogEntries,
			self.lom.metaMetadata,'identifier',10)
		
	def testContribute(self):
		c1=LOMMetadataContribute()
		c1.SetRole("validator")
		self.failUnless(not self.lom.metaMetadata,'zero test')
		self.lom.metaMetadata.AddContribute(c1)
		self.failUnless(self.lom.metaMetadata,'nonzero test')
		self.failUnless(len(self.lom.metaMetadata.contribute)==1 and self.lom.metaMetadata.contribute[0].role.value=="validator")
		c2=LOMMetadataContribute()
		self.lom.metaMetadata.AddContribute(c2)
		self.failUnless(len(self.lom.metaMetadata.contribute)==1,"add empty contribute")
		for i in xrange(9):
			c=LOMMetadataContribute()
			c.SetDate(LOMDateTime(None,"contributor number %i"%(i+2)))
			self.lom.metaMetadata.AddContribute(c)
		self.failUnless(len(self.lom.metaMetadata.contribute)==10)

	def testMetadataSchema(self):
		# Empty string tests
		self.lom.metaMetadata.AddMetadataSchema("")
		self.failIf(self.lom.metaMetadata)
		self.lom.metaMetadata.AddMetadataSchema("LOMv1.0")
		self.failUnless(len(self.lom.metaMetadata.metadataSchema)==1 or
			self.lom.metaMetadata or self.lom.metaMetadata.metadataSchema=="LOMv1.0","simple test")
		for i in xrange(1,10):
			self.lom.metaMetadata.AddMetadataSchema("LOMv1.%i"%i)
		self.failUnless(len(self.lom.metaMetadata.metadataSchema)==10,"max test")
	
	def testLanguage(self):
		"""Check the SetLanguage method"""
		self.lom.metaMetadata.SetLanguage("en-GB")
		self.failUnless(self.lom.metaMetadata,'nonzero test')
		self.failUnless(repr(self.lom.metaMetadata.language)=="LanguageTag('en-GB')")
		self.lom.metaMetadata.SetLanguage(None)
		self.failIf(self.lom.metaMetadata.language)
		
		
class LOMMetadataContributeTests(LOMTests):
	def setUp(self):
		self.contribute=LOMMetadataContribute()
		
	def testStructure(self):
		"""Check the SetRole method"""
		self.RunSingleVocabularyFieldTest(self.contribute.SetRole,self.contribute,'role','creator')
		
	def testEntity(self):
		"""Check the AddEntity method"""
		self.contribute.AddEntity(SAMPLE_VCARD)
		self.failUnless(self.contribute,"non-zero test")
		self.failUnless(len(self.contribute.entity)==1,"entity length test")
		self.contribute.AddEntity(SAMPLE_VCARD)
		self.failUnless(len(self.contribute.entity)==2,"entity length test")
		for i in xrange(8):
			self.contribute.AddEntity(SAMPLE_VCARD)
		self.failUnless(len(self.contribute.entity)==10,"max entity test")
		
	def testDate(self):
		"""Check the SetDate method"""
		self.RunSingleDateFieldTest(self.contribute.SetDate,self.contribute,'date')


class LOMEducationalTests(LOMTests):
	def testInteractivityType(self):
		"""Check the SetInteractivityType method"""
		self.RunSingleVocabularyFieldTest(self.lom.educational.SetInteractivityType,
			self.lom.educational,'interactivityType','expositive')
	
	def testLearningResourceType(self):
		"""Check the AddLearningResourceType method"""
		self.RunVocabularyFieldTests(self.lom.educational.AddLearningResourceType,
			self.lom.educational,'learningResourceType','figure',10)		

	def testInteractivityLevel(self):
		"""Check the SetInteractivityLevel method"""
		self.RunSingleVocabularyFieldTest(self.lom.educational.SetInteractivityLevel,
			self.lom.educational,'interactivityLevel','medium')

	def testSemanticDensity(self):
		"""Check the SetSemanticDensity method"""
		self.RunSingleVocabularyFieldTest(self.lom.educational.SetSemanticDensity,
			self.lom.educational,'semanticDensity','very low')

	def testIntendedEndUserRole(self):
		"""Check the AddIntendedEndUserRole method"""
		self.RunVocabularyFieldTests(self.lom.educational.AddIntendedEndUserRole,
			self.lom.educational,'intendedEndUserRole','manager',10)

	def testContext(self):
		"""Check the AddContext method"""
		self.RunVocabularyFieldTests(self.lom.educational.AddContext,
			self.lom.educational,'context','training',10)

	def testTypicalAgeRange(self):
		"""Check the AddTypicalAgeRange method"""
		self.RunLangStringTests(self.lom.educational.AddTypicalAgeRange,
			self.lom.educational,'typicalAgeRange',5)
	
	def testDifficulty(self):
		"""Check the SetDifficulty method"""
		self.RunSingleVocabularyFieldTest(self.lom.educational.SetDifficulty,
			self.lom.educational,'difficulty','difficult')

	def testDate(self):
		"""Check the SetDate method"""
		self.RunSingleDurationFieldTest(self.lom.educational.SetTypicalLearningTime,
			self.lom.educational,'typicalLearningTime')
	
	def testDescription(self):
		"""Check the AddDescription method"""
		self.RunLangStringTests(self.lom.educational.AddDescription,
			self.lom.educational,'description',10)
	
	def testLanguage(self):
		"""Check the AddLanguage method"""
		self.RunLanguageTests(self.lom.educational.AddLanguage,self.lom.educational,'language',10)
		

class LOMIdentifierTests(unittest.TestCase):
	def testEmptyConstructor(self):
		"""Check LOMIdentifier empty constructor and non-zero test"""
		id=LOMIdentifier()
		self.failUnless(id.catalog==None and id.entry==None and not id,'empty constructor')
		try:
			# See below for why we insist on string types for arguments
			s=LOMIdentifier(3.14159,'')
			self.fail('incompatible argument')
		except TypeError:
			pass
		
	def testCatalogOnlyConstructor(self):
		"""Check LOMIdentifier catalog only constructor"""
		id=LOMIdentifier(None,SAMPLE_CATALOG_1)
		self.failUnless(id.catalog==SAMPLE_CATALOG_1 and id.entry==None)
	
	def testEntryOnlyConstructor(self):
		"""Check LOMIdentifier entry only constructor"""
		id=LOMIdentifier(SAMPLE_ENTRY_1,None)
		self.failUnless(id.catalog==None and id.entry==SAMPLE_ENTRY_1)
	
	def testCompleteConstructor(self):
		"""Check LOMIdentifier complete constructor"""
		id=LOMIdentifier(SAMPLE_ENTRY_1,SAMPLE_CATALOG_1)
		self.failUnless(id.catalog==SAMPLE_CATALOG_1 and id.entry==SAMPLE_ENTRY_1)

	def testConversionConstructor(self):
		"""Check LOMIdentifier conversion constructor"""
		id=LOMIdentifier(SAMPLE_ENTRY_2,SAMPLE_CATALOG_2)
		self.failUnless(type(id.catalog) is UnicodeType and type(id.entry) is UnicodeType,'no conversion to unicode')
		try:
			id=LOMIdentifier(BAD_STRING,BAD_STRING)
			self.fail('accepted bad string')
		except ValueError:
			pass
		
	def testLengths(self):
		"""Check the minimum permitted maximum length of identifier fields"""
		id=LOMIdentifier(u'e'*1000,u'c'*1000)
		self.failUnless(len(id.catalog)==1000 and len(id.entry)==1000)

	def testRepr(self):
		"""Check LOMIdentifier repr method"""
		self.failUnless(repr(LOMIdentifier('Entry','Catalog'))=="LOMIdentifier(u'Entry', u'Catalog')")
		
	def testCmp(self):
		"""Check the LOMIdentifier comparison method"""
		id=[LOMIdentifier('a',None),LOMIdentifier('z',None),LOMIdentifier(None,'a'),
			LOMIdentifier('a','a'),LOMIdentifier('z','a'),LOMIdentifier(None,'z'),LOMIdentifier('a','z')]
		for i in range(len(id)):
			# extra check to ensure that we haven't got a class address comparison issue
			self.failUnless(LOMIdentifier()<id[i] and LOMIdentifier('z','z')>id[i],repr(id[i])+" not between LOMIdentifier() and LOMIdentifier('z','z')")
		for i in range(len(id)):
			for j in range(len(id)):
				if i==j:
					self.failUnless(id[i]==id[j],repr(id[i])+"!="+repr(id[j]))
				elif i<j:
					self.failUnless(id[i]<id[j],repr(id[i])+">="+repr(id[j]))
				else:
					self.failUnless(id[i]>id[j],repr(id[i])+"<="+repr(id[j]))
	
			
class LOMStringTests(unittest.TestCase):
	def testLOMStringEmptyConstructor(self):
		"""Check LOMString empty constructor, non-zero and bad argument test"""
		s=LOMString()
		self.failUnless(s.language==None and s.string==None and not s,'empty constructor')
		try:
			# We don't allow this type of thing because otherwise LOMString('en',0) would be true
			# which seems counter-intuitive
			s=LOMString('',3.14159)
			self.fail('incompatible argument')
		except TypeError:
			pass

	def testCopyConstructor(self):
		"""Check LOMString copy constructor"""
		s1=LOMString("en-GB","Hello")
		s2=LOMString(s1)
		self.failUnless(s1.language==s2.language and s1.string==s2.string)
		
	def testLanguageOnlyConstructor(self):
		"""Check LOMString language only constructor"""
		s=LOMString(SAMPLE_LANGUAGE,None)
		# a LOMString with a language but not string is still basically an empty string!
		self.failUnless(s.language==SAMPLE_LANGUAGE and s.string==None and not s)
	
	def testStringOnlyConstructor(self):
		"""Check LOMString string only constructor"""
		s=LOMString(None,SAMPLE_STRING_1)
		self.failUnless(s.language==None and s.string==SAMPLE_STRING_1 and s)
	
	def testCompleteConstructor(self):
		"""Check LOMString complete constructor"""
		s=LOMString(SAMPLE_LANGUAGE,SAMPLE_STRING_1)
		self.failUnless(s.language==SAMPLE_LANGUAGE and s.string==SAMPLE_STRING_1)

	def testConversionConstructor(self):
		"""Check LOMString conversion constructor"""
		s=LOMString(SAMPLE_LANGUAGE,SAMPLE_STRING_2)
		## self.failUnless(type(s.language) is UnicodeType and type(s.string) is UnicodeType)
	
	def testNullCharacter(self):
		"""Check LOMString with null character"""
		try:
			s=LOMString(None,"NUL = \x00")
			self.fail("accepted null character")
		except LOMError:
			pass
			
	def testLengths(self):
		"""Check LOMString minimum permitted maximum lenths"""
		s=LOMString(LONG_LANGUAGE,u's'*1000)
		self.failUnless(len(s.string)==1000)

	def testRepr(self):
		"""Check the LOMString repr method"""
		self.failUnless(repr(LOMString('en-GB','Hello'))=="LOMString('en-GB', u'Hello')")
		
	def testCmp(self):
		"""Check the LOMString comparison method"""
		# language is ignored during comparisons
		self.failUnless(LOMString('en','Hello')==LOMString('fr','Hello'),'Language not ignored')
		self.failUnless(LOMString('fr',None)<LOMString('en',"apple"),'fr:None >= en:apple')
		self.failUnless(LOMString('en','a')<LOMString('en','z') and LOMString('en','y')>LOMString('en','b'),'simple string comparisons')
		self.failUnless(LOMString('en',"Hello")>"Goodbye")


class LOMLangStringTests(unittest.TestCase):
	def testLangStringEmptyConstructor(self):
		"""Check LOMLangString empty constructor and non-zero test"""
		self.failIf(LOMLangString(),'empty constructor')
		self.failIf(LOMLangString([]),'empty sequence')
		self.failIf(LOMLangString(LOMString()),'empty string')
		self.failIf(LOMLangString([LOMString(),LOMString('en')]),'sequence of empty strings')

	def testLangStringConstructor(self):
		"""Check LOMLangString constructor"""
		self.failUnless(LOMLangString("Hello"),'string constructor')
		self.failUnless(LOMLangString(u"Hello"),'unicode constructor')
		self.failUnless(LOMLangString(LOMString(None,"Hello")),'unicode constructor')
		self.failUnless(LOMLangString(["Hello","Hi"]),'sequence of string')
		self.failUnless(LOMLangString([LOMString('en',"Hello"),LOMString('fr','bonjour')]),'sequence of LOMString')
		self.failUnless(LOMLangString(["Hello",LOMString('fr',"bonjour")]),'mixed sequence')
	
	def testSmallestMaximum(self):
		"""Check LOMLangString minimum permitted maximum length"""
		LOMLangString(["Hello"]*10)

	def testRepr(self):
		"""Check the LOMLangString repr method"""
		self.failUnless(repr(LOMLangString(LOMString('en-GB','Hello')))=="LOMLangString([LOMString('en-GB', u'Hello')])")
		self.failUnless(repr(LOMLangString(['Hello','Hello']))=="LOMLangString([LOMString(None, u'Hello'), LOMString(None, u'Hello')])")

	def testAddString(self):
		"""Check the LOMLangString.AddString and len method"""
		langString=LOMLangString('Hello')
		langString.AddString(u"")
		langString.AddString('bonjour')
		langString.AddString(LOMString('it','buon giorno'))
		self.failUnless(len(langString)==3)
		
	def testMatchRange(self):
		"""Check the LOMLangString.MatchLanguageRange method"""
		langString=LOMLangString([LOMString('en','Hello'),LOMString('fr','bonjour'),LOMString('en-GB','Good day to you'),LOMString(None,'Hi')])
		result=langString.MatchLanguage("*")
		result.sort()
		self.failUnless(result==['Good day to you','Hello','bonjour'],"wildcard match")
		result1=langString.MatchLanguage("en")
		result2=langString.MatchLanguage(LanguageRange('en'))
		result1.sort()
		result2.sort()
		self.failUnless(result1==result2 and result1==['Good day to you','Hello'],"multiple result test")
		result3=langString.MatchLanguage("en","en-US")
		result3.sort()
		self.failUnless(result3==['Good day to you','Hello','Hi'],"default language given test")
		self.failIf(langString.MatchLanguage("en-US"),"range too specific test")


class LOMDateTimeTests(unittest.TestCase):
	def testConstructor(self):
		"""Check LOMDateTime constructor and non-zero test"""
		d=LOMDateTime()
		self.failUnless(d.dateTime==None and d.description==None and not d,"empty constructor")
		self.failUnless(LOMDateTime(Date("19680408")),"Date only")
		self.failUnless(LOMDateTime("1968-04-08"),"Date string only")
		self.failUnless(LOMDateTime(None,LOMLangString("circa 1300 BCE")),
			"LOMLangString description only")
		self.failUnless(LOMDateTime(None,"circa 1300 BCE"),"string description only")
		self.failUnless(LOMDateTime(None,u"circa 1300 BCE"),"unicode description only")
		self.failUnless(LOMDateTime("1968-04-08","circa 1300 BCE"),"date and description strings")

	def testJulianCutOff(self):
		"""Check the change between  formats are dissalowed"""
		d=LOMDateTime("1582-10-04")
		self.failUnless(d.dateTime=="1582-10-14","Julian date before cut-off")
		d=LOMDateTime("1582-10-14")
		self.failUnless(d.dateTime=="1582-10-24","Julian date post cut-off")
		d=LOMDateTime("1582-10-15")
		self.failUnless(d.dateTime=="1582-10-15","Gregorian date")

	def testBadISOFormats(self):
		"""Check that certain formats are dissalowed"""
		try:
			d=LOMDateTime("19680408")
			self.fail("basic format allowed")
		except LOMError:
			pass
		try:
			d=LOMDateTime("1968-04-08T23:20:50,5")
			self.fail("comma for point allowed")
		except LOMError:
			pass
				
class LOMVocabularyTests(unittest.TestCase):
	def testEmptyConstructor(self):
		"""Check LOMVocabulary empty constructor and non-zero test"""
		v=LOMVocabulary()
		self.failUnless(v.source==None and v.value==None and not v,'empty constructor')
		try:
			# See LOMStringTests for why we insist on string types for arguments
			v=LOMVocabulary(0,'')
			self.fail('incompatible argument')
		except TypeError:
			pass
		
	def testSourceOnlyConstructor(self):
		"""Check LOMVocabulary source only constructor"""
		v=LOMVocabulary(None,"LOMv1.0")
		self.failUnless(v.source=="LOMv1.0" and v.value==None)
	
	def testValueOnlyConstructor(self):
		"""Check LOMVocabulary value only constructor"""
		v=LOMVocabulary("hello",None)
		self.failUnless(v.source==None and v.value=="hello")
	
	def testCompleteConstructor(self):
		"""Check LOMVocabulary complete constructor"""
		v=LOMVocabulary("atomic","LOMv1.0")
		self.failUnless(v.source=="LOMv1.0" and v.value=="atomic")
		self.failUnless(type(v.source) is UnicodeType and type(v.value) is UnicodeType)
		try:
			v=LOMVocabulary(BAD_STRING,BAD_STRING)
			self.fail('accepted bad string')
		except ValueError:
			pass

	def testLengths(self):
		"""Check the minimum permitted maximum length of vocabulary fields"""
		v=LOMVocabulary(u'v'*1000,u's'*1000)
		self.failUnless(len(v.source)==1000 and len(v.value)==1000)

	def testRepr(self):
		"""Check LOMVocabulary repr method"""
		self.failUnless(repr(LOMVocabulary('atomic','LOMv1.0'))=="LOMVocabulary(u'atomic', u'LOMv1.0')")
		
	def testCmp(self):
		"""Check the LOMVocabulary comparison method"""
		# primary sort is on the value, not the source
		v=[LOMVocabulary(None,'a'),LOMVocabulary(None,'z'),LOMVocabulary('a',None),
			LOMVocabulary('a','a'),LOMVocabulary('a','z'),LOMVocabulary('z',None),LOMVocabulary('z','a')]
		for i in range(len(v)):
			# extra check to ensure that we haven't got a class address comparison issue
			self.failUnless(LOMVocabulary()<v[i] and LOMVocabulary('z','z')>v[i],repr(v[i])+" not between LOMVocabulary() and LOMVocabulary('z','z')")
		for i in range(len(v)):
			for j in range(len(v)):
				if i==j:
					self.failUnless(v[i]==v[j],repr(v[i])+"!="+repr(v[j]))
				elif i<j:
					self.failUnless(v[i]<v[j],repr(v[i])+">="+repr(v[j]))
				else:
					self.failUnless(v[i]>v[j],repr(v[i])+"<="+repr(v[j]))
	
			
if __name__ == "__main__":
	unittest.main()