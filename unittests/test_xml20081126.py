#! /usr/bin/env python

import unittest

from sys import maxunicode
from tempfile import mkdtemp
import shutil, os.path
from StringIO import StringIO
from types import UnicodeType

MAX_CHAR=0x10FFFF
if maxunicode<MAX_CHAR:
	MAX_CHAR=maxunicode
	print "xml tests truncated to unichr(0x%X) by narrow python build"%MAX_CHAR

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(XML20081126Tests,'test'),
		unittest.makeSuite(XMLDocumentTests,'test'),
		unittest.makeSuite(XMLCharacterTests,'test'),
		unittest.makeSuite(XMLEntityTests,'test'),
		unittest.makeSuite(XMLParserTests,'test'),		
		unittest.makeSuite(XMLElementTests,'test'),
		unittest.makeSuite(XMLValidationTests,'test')
		))

TEST_DATA_DIR=os.path.join(os.path.split(os.path.abspath(__file__))[0],'data_xml20081126')

from pyslet.xml20081126 import *


class PIRecorderElement(XMLElement):
	def __init__(self,parent):
		XMLElement.__init__(self,parent)
		self.target=None
		self.instruction=None
		
	def ProcessingInstruction(self,target,instruction):
		self.target=target
		self.instruction=instruction

	
class NamedElement(XMLElement):
	XMLNAME="test"

def DecodeYN(value):
	return value=='Yes'
	
def EncodeYN(value):
	if value:
		return 'Yes'
	else:
		return 'No'


class GenericElementA(XMLElement):
	pass

class GenericSubclassA(GenericElementA):
	pass

class GenericElementB(XMLElement):
	pass

class GenericSubclassB(GenericElementB):
	pass


class ReflectiveElement(XMLElement):
	XMLNAME="reflection"
	
	XMLATTR_btest='bTest'
	XMLATTR_ctest=('cTest',DecodeYN,EncodeYN)
	XMLATTR_dtest=('dTest',DecodeYN,EncodeYN)
	XMLATTR_dtestR=('dTestR',DecodeYN,EncodeYN,True)
	XMLATTR_etest=('eTest',DecodeYN,EncodeYN)
	XMLATTR_etestR=('eTestR',DecodeYN,EncodeYN,True)
	
	def __init__(self,parent):
		XMLElement.__init__(self,parent)
		self.atest=None
		self.bTest=None
		self.cTest=None
		self.dTest=[]
		self.dTestR=[]
		self.eTest={}
		self.eTestR={}
		self.child=None
		self.generics=[]
		self.GenericElementB=None
		
	def GetAttributes(self):
		attrs=XMLElement.GetAttributes(self)
		if self.atest:
			attrs['atest']=self.atest
		return attrs
		
	def Set_atest(self,value):
		self.atest=value
	
	def GetChildren(self):
		children=XMLElement.GetChildren(self)
		if self.child:
			children.append(self.child)
		return children
		
	def ReflectiveElement(self):
		if self.child:
			return self.child
		else:
			e=ReflectiveElement(self)
			self.child=e
			return e

	def GenericElementA(self,childClass=GenericElementA):
		child=childClass(self)
		self.generics.append(child)
		return child
		
	
class ReflectiveDocument(XMLDocument):
	def GetElementClass(self,name):
		if name in ["reflection","etest"]:
			return ReflectiveElement
		else:
			return XMLElement

		
class EmptyElement(XMLElement):
	XMLNAME="empty"
	XMLCONTENT=XMLEmpty
	
class ElementContent(XMLElement):
	XMLNAME="elements"
	XMLCONTENT=XMLElementContent

class MixedElement(XMLElement):
	XMLNAME="mixed"
	XMLCONTENT=XMLMixedContent

class IDElement(XMLElement):
	XMLName="ide"
	XMLCONTENT=XMLEmpty
	ID="id"

class BadElement:
	XMLNAME="bad"

	
class Elements:
	named=NamedElement
	reflective=ReflectiveElement
	empty=EmptyElement
	elements=ElementContent
	mixed=MixedElement
	id=IDElement
	bad=BadElement
	
class XML20081126Tests(unittest.TestCase):		
	def testCaseConstants(self):
		#self.failUnless(APP_NAMESPACE=="http://www.w3.org/2007/app","Wrong APP namespace: %s"%APP_NAMESPACE)
		#self.failUnless(ATOMSVC_MIMETYPE=="application/atomsvc+xml","Wrong APP service mime type: %s"%ATOMSVC_MIMETYPE)
		#self.failUnless(ATOMCAT_MIMETYPE=="application/atomcat+xml","Wrong APP category mime type: %s"%ATOMCAT_MIMETYPE)
		pass

	def testCaseDeclare(self):
		classMap={}
		MapClassElements(classMap,Elements)
		self.failUnless(type(classMap['mixed']) is types.ClassType,"class type not declared")
		self.failIf(hasattr(classMap,'bad'),"class type declared by mistake")

		
class XMLCharacterTests(unittest.TestCase):
	# Test IsNameChar
	def testChar(self):
		"""[2] Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]"""
		expectedEdges=[0x9,0xB,0xD,0xE,0x20,0xD800,0xE000,0xFFFE,0x10000,0x110000]
		if MAX_CHAR<0x10FFFF:
			expectedEdges=expectedEdges[0:8]
		self.failUnless(self.FindEdges(IsChar,MAX_CHAR)==expectedEdges,"IsChar")

	def testSpace(self):
		"""[3] S ::= (#x20 | #x9 | #xD | #xA)+"""
		expectedEdges=[0x9,0xB,0xD,0xE,0x20,0x21]
		self.failUnless(self.FindEdges(IsS,256)==expectedEdges,"IsS")
	
	def testNameStart(self):
		"""[4] NameStartChar ::= ":" | [A-Z] | "_" | [a-z] | [#xC0-#xD6] | [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] | [#x37F-#x1FFF] | [#x200C-#x200D] | [#x2070-#x218F] | [#x2C00-#x2FEF] | [#x3001-#xD7FF] | [#xF900-#xFDCF] | [#xFDF0-#xFFFD] | [#x10000-#xEFFFF]
		[5] NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 | [#x0300-#x036F] | [#x203F-#x2040]"""
		nNameStartChars=0
		nNameChars=0
		for code in xrange(0x10000):
			c=unichr(code)
			if IsNameChar(c):
				nNameChars+=1
				if IsNameStartChar(c):
					nNameStartChars+=1
			else:
				self.failIf(IsNameStartChar(c),"NameStart not a name char: %s"%c)
		self.failUnless(nNameChars==54129,"name char total %i"%nNameChars)
		self.failUnless(nNameStartChars==54002,"name start char total %i"%nNameStartChars)
	
	def testPubidChar(self):
		"""[13] PubidChar ::= #x20 | #xD | #xA | [a-zA-Z0-9] | [-'()+,./:=?;!*#@$_%] """
		matchSet=" \x0d\x0a-'()+,./:=?;!*#@$_%abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
		for code in xrange(0xFF):
			c=unichr(code)
			if IsPubidChar(c):
				if not c in matchSet:
					self.fail("PubidChar false positive: %s"%c)
			else:
				if c in matchSet:
					self.fail("PubidChar not recognized: %s"%c)
					
	def testCharClasses(self):
		"""[84] Letter ::= BaseChar | Ideographic
		[85] BaseChar ::= [#x0041-#x005A] | ...
		[86] Ideographic ::= [#x4E00-#x9FA5] | #x3007 | [#x3021-#x3029]
		[87] CombiningChar ::= [#x0300-#x0345] | ...
		[88] Digit ::= [#x0030-#x0039] | ...
		[89] Extender ::= #x00B7 | ..."""
		nBaseChars=0
		nIdeographics=0
		nCombiningChars=0
		nDigits=0
		nExtenders=0
		for code in xrange(0x10000):
			c=unichr(code)
			if IsLetter(c):
				if IsIdeographic(c):
					nIdeographics+=1
				elif IsBaseChar(c):
					nBaseChars+=1
				else:
					self.fail("unichr(%#x) is a letter but not an ideographic or base character"%code)
			else:
				self.failIf(IsIdeographic(c) or IsBaseChar(c),
					"unichr(%#x) is an ideographic or base character but not a letter")
			if IsCombiningChar(c):
				nCombiningChars+=1
			if IsDigit(c):
				nDigits+=1
			if IsExtender(c):
				nExtenders+=1
		self.failUnless(nBaseChars==13602,"base char total %i"%nBaseChars)
		self.failUnless(nIdeographics==20912,"ideographic char total %i"%nIdeographics)
		self.failUnless(nCombiningChars==437,"combing char total %i"%nCombiningChars)
		self.failUnless(nDigits==149,"digit total %i"%nDigits)
		self.failUnless(nExtenders==18,"extender total %i"%nExtenders)

	def FindEdges(self,testFunc,max):
		edges=[]
		flag=False
		for code in xrange(max+1):
			c=unichr(code)
			if flag!=testFunc(c):
				flag=not flag
				edges.append(code)
		return edges

class XMLValidationTests(unittest.TestCase):
	def testCaseName(self):
		self.failUnless(IsValidName("Simple"))
		self.failUnless(IsValidName(":BadNCName"))
		self.failUnless(IsValidName("prefix:BadNCName"))
		self.failUnless(IsValidName("_GoodNCName"))
		self.failIf(IsValidName("-BadName"))
		self.failIf(IsValidName(".BadName"))
		self.failIf(IsValidName("0BadName"))
		self.failUnless(IsValidName("GoodName-0.12"))
		self.failIf(IsValidName("BadName$"))
		self.failIf(IsValidName("BadName+"))
		self.failUnless(IsValidName(u"Caf\xe9"))



class XMLEntityTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=XMLEntity("<hello>")
		self.failUnless(e.lineNum==1)
		self.failUnless(e.linePos==1)
		self.failUnless(type(e.theChar) is UnicodeType and e.theChar==u'<')
		e=XMLEntity(u"<hello>")
		self.failUnless(type(e.theChar) is UnicodeType and e.theChar==u'<')
		e=XMLEntity(StringIO("<hello>"))
		self.failUnless(e.lineNum==1)
		self.failUnless(e.linePos==1)
		self.failUnless(type(e.theChar) is UnicodeType and e.theChar==u'<')

	def testCaseChars(self):
		e=XMLEntity("<hello>")
		for c in "<hello>":
			self.failUnless(e.theChar==c)
			e.NextChar()
		self.failUnless(e.theChar is None)
		e.Reset()
		self.failUnless(e.theChar=='<')

	def testLines(self):
		e=XMLEntity("Hello\nWorld\n!")
		while e.theChar is not None:
			c=e.theChar
			e.NextChar()
		self.failUnless(e.lineNum==3)
		self.failUnless(e.linePos==2)

	def testCodecs(self):
		m=u'Caf\xe9'
		e=XMLEntity('Caf\xc3\xa9')
		for c in m:
			self.failUnless(e.theChar==c,"Print: parsing utf-8 got %s instead of %s"%(repr(e.theChar),repr(c)))
			e.NextChar()
		e=XMLEntity('Caf\xe9','latin_1')
		for c in m:
			self.failUnless(e.theChar==c,"Print: parsing latin-1 got %s instead of %s"%(repr(e.theChar),repr(c)))
			e.NextChar()
		# This string should be automatically detected
		e=XMLEntity('\xff\xfeC\x00a\x00f\x00\xe9\x00','utf-16')
		for c in m:
			self.failUnless(e.theChar==c,"Print: parsing utf-16LE got %s instead of %s"%(repr(e.theChar),repr(c)))
			e.NextChar()		
		e=XMLEntity('\xfe\xff\x00C\x00a\x00f\x00\xe9','utf-16')
		for c in m:
			self.failUnless(e.theChar==c,"Print: parsing utf-16BE got %s instead of %s"%(repr(e.theChar),repr(c)))
			e.NextChar()			
		e=XMLEntity('\xef\xbb\xbfCaf\xc3\xa9','utf-8')
		for c in m:
			self.failUnless(e.theChar==c,"Print: parsing utf-8 with BOM got %s instead of %s"%(repr(e.theChar),repr(c)))
			e.NextChar()
		e=XMLEntity('Caf\xe9')
		for c in 'Ca':
			e.NextChar()
		e.ChangeEncoding('ISO-8859-1')
		self.failUnless(e.theChar=='f',"Bad encoding change")
		e.NextChar()
		self.failUnless(e.theChar==u'\xe9',"Print: change encoding got %s instead of %s"%(repr(e.theChar),repr(u'\xe9')))

		
class XMLParserTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=XMLEntity("<hello>")
		p=XMLParser(e)

	def testCaseRewind(self):
		data="Hello\r\nWorld\nCiao\rTutti!"
		data2="Hello\nWorld\nCiao\nTutti!"
		e=XMLEntity(data)
		p=XMLParser(e)
		for i in xrange(len(data2)):
			self.failUnless(p.theChar==data2[i],"Failed at data[%i] before look ahead"%i)
			for j in xrange(5):
				data=[]
				for k in xrange(j):
					if p.theChar is not None:
						data.append(p.theChar)
					p.NextChar()
				p.BuffText(string.join(data,''))
				self.failUnless(p.theChar==data2[i],"Failed at data[%i] after Rewind(%i)"%(i,j))
			p.NextChar()
	
	def testCaseNamecaseGeneral(self):
		data="Hello GoodBye"
		e=XMLEntity(data)
		p=XMLParser(e)
		self.failIf(p.ParseLiteral("HELLO"),"Case insensitve literal in default parser")
		p.sgmlNamecaseGeneral=True
		self.failUnless(p.ParseLiteral("HELLO"),"Upper-case literals")
		p.ParseS()
		#self.failUnless(p.ParseName()=="GOODBYE","Upper-case general names")

	def testDocument(self):
		"""[1] document ::= prolog element Misc* """
		os.chdir(TEST_DATA_DIR)
		f=open('readFile.xml','rb')
		e=XMLEntity(f)
		d=XMLDocument()
		d.Read(e)
		root=d.root
		self.failUnless(isinstance(root,XMLElement))
		self.failUnless(root.xmlname=='tag' and root.GetValue()=='Hello World')
		f.close()
		f=open('readFile.xml','rb')
		e=XMLEntity(f)
		p=XMLParser(e)
		p.ParseDocument()
		root=p.doc.root
		self.failUnless(isinstance(root,XMLElement))
		self.failUnless(root.xmlname=='tag' and root.GetValue()=='Hello World')
		f.close()
	
	# Following production is implemented as a character class:
	# [2] Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
	
	def testCaseS(self):
		"""[3] S ::= (#x20 | #x9 | #xD | #xA)+ """
		e=XMLEntity(" \t\r\n \r \nH ello")
		p=XMLParser(e)
		self.failUnless(p.ParseS()==" \t\n \n \n")
		self.failUnless(p.theChar=='H')
		p.NextChar()
		try:
			p.ParseRequiredS()
		except XMLWellFormedError:
			self.fail("ParseRequiredS failed to parse white space")
		try:
			p.ParseRequiredS()
			self.fail("ParseRequiredS failed to throw exception")
		except XMLWellFormedError:
			pass
			
	# Following two productions are implemented as character classes:
	# [4] NameStartChar ::= ":" | [A-Z] | "_" | [a-z] | [#xC0-#xD6] | [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] | [#x37F-#x1FFF] | [#x200C-#x200D] | [#x2070-#x218F] | [#x2C00-#x2FEF] | [#x3001-#xD7FF] | [#xF900-#xFDCF] | [#xFDF0-#xFFFD] | [#x10000-#xEFFFF]
	# [4a] NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 | [#x0300-#x036F] | [#x203F-#x2040]

	def testCaseName(self):
		"""[5] Name ::= NameStartChar (NameChar)*"""
		sGood=('hello',':ello',u'A\xb72','_')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			name=p.ParseName()
			self.failUnless(name==s,u"Name: %s (expected %s)"%(name,s))
		sBad=('-Atlantis','&hello','fish&chips','what?','.ello',u'\xb7RaisedDot','-')
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				name=p.ParseName()
				self.failIf(p.theChar is None,"ParseName negative test: %s"%s)
			except XMLWellFormedError:
				pass
		e=XMLEntity('&noname')
		p=XMLParser(e)
		try:
			p.ParseRequiredName()
			self.fail("ParseRequiredName: failed to throw exception")
		except XMLWellFormedError:
			pass
			
	def testCaseNames(self):
		"""[6] Names ::= Name (#x20 Name)*	"""
		e=XMLEntity("Hello World -Atlantis!")
		p=XMLParser(e)
		self.failUnless(p.ParseNames()==['Hello','World'])
			
	def testCaseNmtoken(self):
		"""[7] Nmtoken ::= (NameChar)+"""
		sGood=('hello','h:ello','-Atlantis',':ello',u'\xb7RaisedDot',u'1\xb72','-')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			name=p.ParseNmtoken()
			self.failUnless(name==s,u"Nmtoken: %s"%name)
		sBad=('&hello','fish&chips','what?')
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				name=p.ParseNmtoken()
				self.failIf(p.theChar is None,"ParseNmtoken negative test: %s"%s)
			except XMLWellFormedError:
				pass		

	def testCaseNmtokens(self):
		"""[8] Nmtokens ::= Nmtoken (#x20 Nmtoken)*"""
		e=XMLEntity("Hello World -Atlantis!")
		p=XMLParser(e)
		tokens=p.ParseNmtokens()
		self.failUnless(tokens==['Hello','World','-Atlantis'],repr(tokens))

	def testCaseEntityValue(self):
		"""[9] EntityValue ::= '"' ([^%&"] | PEReference | Reference)* '"' | "'" ([^%&'] | PEReference | Reference)* "'"	"""
		e=XMLEntity("'first'\"second\"'3&gt;2''2%ltpe;3'")
		m=['first','second','3&gt;2','2<3']
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('ltpe','<'))
		for match in m:
			value=p.ParseEntityValue()
			self.failUnless(value==match,"Match failed: %s (expected %s)"%(value,match))

	def testAttValue(self):
		"""[10] AttValue ::= '"' ([^<&"] | Reference)* '"' |  "'" ([^<&'] | Reference)* "'" """
		e=XMLEntity("'first'\"second\"'3&gt;2''Caf&#xE9;'")
		m=['first','second','3>2',u'Caf\xe9']
		p=XMLParser(e)
		for match in m:
			value=p.ParseAttValue()
			self.failUnless(value==match,"Match failed: %s (expected %s)"%(value,match))
		sBad=('"3<2"',"'Fish&Chips'")
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				value=p.ParseAttValue()
				self.fail("AttValue negative test: %s"%s)
			except XMLWellFormedError:
				pass		
	
	def testSystemLiteral(self):
		"""[11] SystemLiteral ::= ('"' [^"]* '"') | ("'" [^']* "'") """
		e=XMLEntity("'first'\"second\"'3&gt;2''2%ltpe;3''Caf&#xE9;'")
		m=[u'first',u'second',u'3&gt;2',u'2%ltpe;3',u'Caf&#xE9;']
		p=XMLParser(e)
		for match in m:
			value=p.ParseSystemLiteral()
			self.failUnless(value==match,"Match failed: %s (expected %s)"%(value,match))
	
	def testPubidLiteral(self):
		"""[12] PubidLiteral ::= '"' PubidChar* '"' | "'" (PubidChar - "'")* "'"	"""
		e=XMLEntity("'first'\"second\"'http://www.example.com/schema.dtd?strict''[bad]'")
		m=['first','second','http://www.example.com/schema.dtd?strict']
		p=XMLParser(e)
		for match in m:
			value=p.ParsePubidLiteral()
			self.failUnless(value==match,"Match failed: %s (expected %s)"%(value,match))
		try:
			value=p.ParsePubidLiteral()
			self.fail("Parsed bad PubidLiterasl: %s"%value)
		except XMLFatalError:
			pass

	# [13] PubidChar: tested as a character class
	
	def testCaseCharData(self):
		"""[14] CharData ::= [^<&]* - ([^<&]* ']]>' [^<&]*) """
		e=XMLEntity("First<Second&Third]]&Fourth]]>")
		m=['First','Second','Third]]','Fourth']
		p=XMLParser(e)
		p.doc=XMLDocument()
		for match in m:
			p.element=XMLElement(p.doc)
			p.ParseCharData()
			p.NextChar()
			self.failUnless(p.element.GetValue()==match,"Match failed: %s (expected %s)"%(p.element.GetValue(),match))

	def testCaseComment(self):
		"""[15] Comment ::= '<!--' ((Char - '-') | ('-' (Char - '-')))* '-->' """
		e=XMLEntity("<!--First--><!--Secon-d--><!--Thi<&r]]>d--><!--Fourt<!-h--><!--Bad--Comment-->")
		m=['First','Secon-d','Thi<&r]]>d','Fourt<!-h']
		p=XMLParser(e)
		for match in m:
			pStr=p.ParseComment()
			self.failUnless(pStr==match,"Match failed: %s (expected %s)"%(pStr,match))
		try:
			if p.ParseLiteral('<!--'):
				pStr=p.ParseComment()
			self.fail("Parsed bad comment: %s"%pStr)
		except XMLFatalError:
			pass
		
	def testCasePI(self):
		"""[16] PI ::= '<?' PITarget (S (Char* - (Char* '?>' Char*)))? '?>' """
		e=XMLEntity("<?target instruction?><?xm_xml \n\r<!--no comment-->?><?markup \t]]>?&<?>")
		m=[('target','instruction'),('xm_xml','<!--no comment-->'),('markup',']]>?&<')]
		p=XMLParser(e)
		p.doc=XMLDocument()
		for matchTarget,matchStr in m:
			p.element=PIRecorderElement(p.doc)
			p.ParsePI()
			self.failUnless(p.element.target==matchTarget,"Match failed for target: %s (expected %s)"%(p.element.target,matchTarget))
			self.failUnless(p.element.instruction==matchStr,"Match failed for instruction: %s (expected %s)"%(p.element.instruction,matchStr))
		sBad=('<?xml reserved?>')
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.doc=XMLDocument()
			try:
				p.ParsePI()
				self.fail("PI negative test: %s"%s)
			except XMLWellFormedError:
				pass		

	def testPITarget(self):
		"""[17] PITarget ::= Name - (('X' | 'x') ('M' | 'm') ('L' | 'l'))	"""
		sGood=('hello','helloxml','xmlhello','xmhello','xm','ml','xl')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			name=p.ParsePITarget()
			self.failUnless(name==s,"PITarget: %s"%name)
		sBad=('xml','XML','xML','Xml')
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				name=p.ParsePITarget()
				self.fail("PITarget negative test: %s"%s)
			except XMLWellFormedError:
				pass		
		
	def testCDSect(self):
		"""[18] CDSect ::= CDStart CData CDEnd	"""
		sGood=('<![CDATA[hello]]>',
			"<![CDATA[]]>",
			"<![CDATA[a]b]]c]>d><![CDATAe]]>",
			'hello]]>',
			"<![CDATA[<hello>&world;]]>")
		m=['hello','','a]b]]c]>d><![CDATAe','hello',"<hello>&world;"]
		for s,match in zip(sGood,m):
			e=XMLEntity(s)
			p=XMLParser(e)
			p.doc=XMLDocument()
			p.element=XMLElement(p.doc)
			p.ParseCDSect(p.theChar!='<')
			self.failUnless(p.element.GetValue()==match,"CDSect conent: %s"%p.element.GetValue())
		sBad=('<!CDATA [hello]]>',
			"<!CDATA[hello]]",
			"hello")
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.doc=XMLDocument()
			p.element=XMLElement(p.doc)
			try:
				p.ParseCDSect(p.theChar!='<')
				self.fail("CDSect negative test: %s"%s)
			except XMLWellFormedError:
				pass		
		e=XMLEntity("&hello;<end")
		p=XMLParser(e)
		p.doc=XMLDocument()
		p.element=XMLElement(p.doc)
		p.ParseCDSect(True,'<end')
		self.failUnless(p.element.GetValue()=='&hello;',"Custom CDSect: %s"%p.element.GetValue())
		
	def testCDStart(self):
		"""[21] CDStart ::= '<!CDATA['	"""
		e=XMLEntity("<![CDATA[")
		p=XMLParser(e)
		p.ParseCDStart()
		self.failUnless(p.theChar is None,"Short parse on CDStart")
		
	def testCData(self):
		"""[20] CData ::= (Char* - (Char* ']]>' Char*))	"""
		sGood=('',' ','<!-- comment -->',
			'&hello;]]>',
			']',
			']]',
			']]h>')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.doc=XMLDocument()
			p.element=XMLElement(p.doc)
			p.ParseCData()
			if p.theChar is None:
				self.failUnless(p.element.GetValue()==s,"CData conent: %s"%p.element.GetValue())
			else:
				p.ParseCDEnd()
				self.failUnless(p.element.GetValue()==s[:-3],"CData conent: %s"%p.element.GetValue())				
		# no negative tests as prolog can be empty, but check the custom CDEnd case.
		e=XMLEntity("hello<end")
		p=XMLParser(e)
		p.doc=XMLDocument()
		p.element=XMLElement(p.doc)
		p.ParseCData('<end')
		self.failUnless(p.element.GetValue()=='hello',"Custom CDEnd: %s"%p.element.GetValue())
		
	def testCDEnd(self):
		"""[21] CDEnd ::= ']]>'	"""
		e=XMLEntity("]]>")
		p=XMLParser(e)
		p.ParseCDEnd()
		self.failUnless(p.theChar is None,"Short parse on CDEnd")
		
	def testProlog(self):
		"""[22] prolog ::= XMLDecl? Misc* (doctypedecl Misc*)?	"""
		sGood=('',' ','<!-- comment -->',
			'<?xml version="1.0"?>',
			'<?xml version="1.0"?><!-- comment --> ',
			'<?xml version="1.0"?><!-- comment --> <!DOCTYPE steve>',
			'<?xml version="1.0"?><!-- comment --> <!DOCTYPE steve><?pi?> ')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.doc=XMLDocument()
			p.ParseProlog()
			self.failUnless(p.theChar is None,"Short parse on Prolog")
		# no negative tests as prolog can be empty!
		
	def testXMLDecl(self):
		"""[23] XMLDecl ::= '<?xml' VersionInfo EncodingDecl? SDDecl? S? '?>'	"""
		sGood=('<?xml version="1.0" encoding="utf-8" standalone="no" ?>',
			"<?xml version='1.0' standalone='yes'?>",
			"<?xml version='1.0' encoding='utf-8'?>",
			"<?xml version='1.1'?>",
			" version='1.2'?>")
		m=[('1.0','utf-8',False),
			('1.0',None,True),
			('1.0','utf-8',False),
			('1.1',None,False),
			('1.2',None,False)]
		for s,match in zip(sGood,m):
			e=XMLEntity(s)
			p=XMLParser(e)
			d=p.ParseXMLDecl(not ('x' in s))
			self.failUnless(isinstance(d,XMLDeclaration),"xml declaration type")
			self.failUnless(d.version==match[0],"declared version mismatch: %s"%d.version)
			self.failUnless(d.encoding==match[1],"declared encoding mismatch: %s"%d.encoding)
			self.failUnless(d.standalone==match[2],"standalone declaration mismatch: %s"%d.standalone)
			self.failUnless(p.theChar is None,"Short parse on XMLDecl")
		sBad=('','version="1.0"'," ='1.0'"," version=1.0")
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseXMLDecl()
				self.fail("XMLDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass		
		
	def testVersionInfo(self):
		"""[24] VersionInfo ::= S 'version' Eq ("'" VersionNum "'" | '"' VersionNum '"')	"""
		sGood=(' version="1.0"',"  version  =  '1.1'"," = '1.0'")
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.ParseVersionInfo(not ('v' in s))
			self.failUnless(p.theChar is None,"Short parse on VersionInfo")
		sBad=('','version="1.0"'," ='1.0'"," version=1.0")
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseVersionInfo()
				self.fail("VersionInfo negative test: %s"%s)
			except XMLWellFormedError:
				pass		
		
	def testEq(self):
		"""[25] Eq ::= S? '=' S?	"""
		sGood=('=',' = ',' =','= ')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.ParseEq()
			self.failUnless(p.theChar is None,"Short parse on Eq")
		sBad=('','-')
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseEq()
				self.fail("Eq negative test: %s"%s)
			except XMLWellFormedError:
				pass		
		
	def testVersionNum(self):
		"""[26] VersionNum ::= '1.' [0-9]+ """
		sGood=('1.0','1.10','1.1','1.0123456789')
		for s in sGood:
			e=XMLEntity(s)
			p=XMLParser(e)
			self.failUnless(p.ParseVersionNum()==s,"Failed to parse VersionNum: %s"%s)
			self.failUnless(p.theChar is None,"Short parse on VersionNum")
		sBad=('1. ','2.0','1','1,0')
		for s in sBad:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseVersionNum()
				self.fail("VersionNum negative test: %s"%s)
			except XMLWellFormedError:
				pass		
		
	def testMisc(self):
		"""[27] Misc ::= Comment | PI | S """
		s="<!-- comment --><?pi?> "
		e=XMLEntity(s)
		p=XMLParser(e)
		for i in xrange(3):
			p.ParseMisc()
		self.failUnless(p.theChar is None,"Short parse of Misc")
		
	def testDoctypedecl(self):
		"""[28] doctypedecl ::= '<!DOCTYPE' S Name (S ExternalID)? S? ('[' intSubset ']' S?)? '>'	"""
		s=["<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd'[ <!ENTITY name 'Steve'> ]>",
			"<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd' [] >",
			"<!DOCTYPE Steve SYSTEM 'SteveDoc.dtd' >",
			"<!DOCTYPE Steve [ ] >",
			"<!DOCTYPE Steve>"]
		m=[('Steve','SteveDoc.dtd','Steve'),
			('Steve','SteveDoc.dtd',None),
			('Steve','SteveDoc.dtd',None),
			('Steve',None,None),
			('Steve',None,None)]
		for sEntity,match in zip(s,m):
			e=XMLEntity(sEntity)
			p=XMLParser(e)
			p.ParseDoctypedecl()
			self.failUnless(isinstance(p.dtd,XMLDTD),"No DTD created")
			self.failUnless(p.dtd.name==match[0],"Name mismatch")
			if match[1] is None:
				self.failUnless(p.dtd.externalID is None,"External ID: expected None")
			else:
				self.failUnless(isinstance(p.dtd.externalID,XMLExternalID),"Type of ExternalID")
				self.failUnless(p.dtd.externalID.system==match[1],"System ID mismatch")
			if match[2] is not None:
				self.failUnless(p.dtd.GetEntity('name').definition==match[2],"Expected general entity declared: %s"%repr(p.dtd.GetEntity('name').definition))
			
	def testDeclSep(self):
		"""[28a] DeclSep ::= PEReference | S"""
		s="%stuff; %stuff; x"
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('stuff',' '))
		p.checkValidity=True
		p.refMode=XMLParser.RefModeInDTD
		while p.theChar!='x':
			p.ParseDeclSep()
		
	def testIntSubset(self):
		"""[28b] intSubset ::= (markupdecl | DeclSep)* """
		s="""<!ELEMENT elem1 ANY>
		<!ATTLIST elem1 attr CDATA 'Steve'>
		<!ENTITY name 'Steve'>
		<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'> 
		<?stuff?>
		<!-- more stuff -->
		x"""
		e=XMLEntity(s)
		p=XMLParser(e)
		p.doc=XMLDocument()
		p.ParseIntSubset()
		self.failUnless(p.theChar=='x',"Short parse on internal subset: found %s"%repr(p.theChar))		
		
	def testMarkupDecl(self):
		"""[29] markupdecl ::= elementdecl | AttlistDecl | EntityDecl | NotationDecl | PI | Comment	"""
		s="""<!ELEMENT elem1 ANY>
		<!ATTLIST elem1 attr CDATA 'Steve'>
		<!ENTITY name 'Steve'>
		<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'> 
		<?stuff?>
		<!-- more stuff -->
		x"""
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		while p.theChar=='<':
			p.ParseMarkupDecl(False)
			p.ParseS()
		self.failUnless(p.theChar=='x',"Short parse on markup declarations: found %s"%repr(p.theChar))
		eType=p.dtd.GetElementType('elem1')
		self.failUnless(eType.contentType==XMLElementType.Any,"element content type")
		aList=p.dtd.GetAttributeList('elem1')
		self.failUnless(aList['attr'].defaultValue=='Steve',"attlist")
		self.failUnless(p.dtd.GetEntity('name').definition=='Steve',"entity declaration")
		self.failUnless(p.dtd.GetNotation('SteveN').externalID.system=='/home/steve.txt',"notation declaration")
		
	def testExtSubset(self):
		"""[30] extSubset ::= TextDecl? extSubsetDecl """
		s='<?xml encoding = "x-steve"?> <?stuff?> !'
		e=XMLEntity(s)
		p=XMLParser(e)
		p.ParseExtSubset()
		self.failUnless(p.theChar=='!',"Short parse on extSubset: %s"%p.theChar)		
		s='<?stuff?> !'
		e=XMLEntity(s)
		p=XMLParser(e)
		p.ParseExtSubset()
		self.failUnless(p.theChar=='!',"Short parse on extSubset: %s"%p.theChar)		
		
	def testExtSubsetDecl(self):
		"""[31] extSubsetDecl ::= ( markupdecl | conditionalSect | DeclSep)*	"""
		s="<?stuff?><![INCLUDE[]]>%moreStuff; "
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('moreStuff',' <?stuff?>'))
		p.checkValidity=True
		p.refMode=XMLParser.RefModeInDTD
		p.ParseExtSubsetDecl()
		self.failUnless(p.theChar is None,"Short parse on extSubsetDecl: %s"%p.theChar)		

	def testSDDecl(self):
		"""[32] SDDecl ::= S 'standalone' Eq (("'" ('yes' | 'no') "'") | ('"' ('yes' | 'no') '"')) """
		e=XMLEntity(" standalone='yes' standalone = \"no\" standalone = 'bad'")
		m=[True,False]
		p=XMLParser(e)
		for match in m:
			value=p.ParseSDDecl()
			self.failUnless(value==match,"Match failed: %s (expected %s)"%(value,match))
		try:
			value=p.ParseSDDecl()
			self.fail("Parsed bad SDDecl: %s"%value)
		except XMLFatalError:
			pass		
		
	# There are no productions [33]-[38]

	def testElement(self):
		"""[39] element ::= EmptyElemTag | STag content ETag """
		s="""<elem1/><elem2>hello</elem2><elem3>goodbye</elem4>"""
		e=XMLEntity(s)
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInContent
		element=p.element=XMLElement("a")
		p.ParseElement()
		p.ParseElement()
		try:
			p.ParseElement()
			self.fail("Parsed bad element.")
		except XMLWellFormedError:
			pass
		children=element.GetChildren()
		self.failUnless(isinstance(children[0],XMLElement),"First element: %s"%repr(children[0]))
		self.failUnless(children[0].xmlname=='elem1',"First element name: %s"%repr(children[0].xmlname))
		self.failUnless(children[0].GetValue()=='',"First element empty value: %s"%repr(children[0].GetValue()))
		self.failUnless(isinstance(children[1],XMLElement),"Second element: %s"%repr(children[1]))
		self.failUnless(children[1].xmlname=='elem2',"Second element name: %s"%repr(children[1].xmlname))
		self.failUnless(children[1].GetValue()=='hello',"Second element value: %s"%repr(children[1].GetValue()))

		
	def testSTag(self):
		"""[40] STag ::= '<' Name (S Attribute)* S? '>' """
		e=XMLEntity("<tag hello='world' ciao=\"tutti\">")
		p=XMLParser(e)
		name,attrs,empty=p.ParseSTag()
		self.failUnless(name=='tag' and attrs['hello']=='world' and attrs['ciao']=='tutti' and empty==False)
		e=XMLEntity("<tag hello/>")
		p=XMLParser(e)
		p.sgmlShorttag=True
		name,attrs,empty=p.ParseSTag()
		self.failUnless(name=='tag' and attrs['@hello']=='hello' and empty is True)
		e=XMLEntity("<tag width=20%>")
		p=XMLParser(e)
		p.dontCheckWellFormedness=True
		name,attrs,empty=p.ParseSTag()
		self.failUnless(name=='tag' and attrs['width']=='20%' and empty is False)
		
		
	def testAttribute(self):
		"""[41] Attribute ::= Name Eq AttValue """
		s="a='b'c=\"d\"e=f i j g=h%"
		e=XMLEntity(s)
		m=[('a','b'),('c','d')]
		p=XMLParser(e)
		for match in m:
			name,value=p.ParseAttribute()
			self.failUnless(name==match[0],"Attribute name match failed: %s (expected %s)"%(name,match[0]))
			self.failUnless(value==match[1],"Attribute value match failed: %s (expected %s)"%(value,match[1]))
		try:
			p.ParseS()
			value=p.ParseAttribute()
			self.fail("Parsed bad Attribute: %s"%value)
		except XMLWellFormedError:
			pass
		e=XMLEntity(s)
		m=[('a','b'),('c','d'),('e','f'),('@i','i'),('@j','j'),('g','h%')]
		p=XMLParser(e)
		p.dontCheckWellFormedness=True
		p.sgmlShorttag=True
		for match in m:
			p.ParseS()
			name,value=p.ParseAttribute()
			self.failUnless(name==match[0],"Compatibility: Attribute name match failed: %s (expected %s)"%(name,match[0]))
			self.failUnless(value==match[1],"Compatibility: Attribute value match failed: %s (expected %s)"%(value,match[1]))
		self.failUnless(p.theChar is None,"Short parse of ETag tests")
		
	def testETag(self):
		"""[42] ETag ::= '</' Name S? '>' """
		s="</elem1>elem2></elem3/>"
		e=XMLEntity(s)
		m=['elem1','elem2']
		p=XMLParser(e)
		for match in m:
			value=p.ParseETag(p.theChar!='<')
			self.failUnless(value==match,"ETag name match failed: %s (expected %s)"%(value,match))
		try:
			value=p.ParseETag()
			self.fail("Parsed bad ETag: %s"%value)
		except XMLWellFormedError:
			p.ParseLiteral('/>')
			pass
		self.failUnless(p.theChar is None,"Short parse of ETag tests")
						
	def testContent(self):
		"""[43] content ::= CharData? ((element | Reference | CDSect | PI | Comment) CharData?)* """
		s="""a<elem1/>b&amp;c<![CDATA[&amp;]]>d<?x?>e<!-- y -->f"""
		e=XMLEntity(s)
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInContent
		p.element=XMLElement("a")
		p.ParseContent()
		children=p.element.GetChildren()
		self.failUnless(children[0]=='a',"First character: %s"%repr(children[0]))
		self.failUnless(isinstance(children[1],XMLElement),"First element: %s"%repr(children[1]))
		self.failUnless(children[1].xmlname=='elem1',"First element name: %s"%repr(children[1].xmlname))
		self.failUnless(children[2]=='b&c&amp;def',"Remaining data: %s"%repr(children[2]))

	def testEmptyElemTag(self):
		"""[44] EmptyElemTag ::= '<' Name (S Attribute)* S? '/> """
		s="""<elem1/> <elem2 /> <elem3 x="1"/>"""
		e=XMLEntity(s)
		p=XMLParser(e)
		m=[('elem1',{}),('elem2',{}),('elem3',{'x':'1'})]
		for match in m:
			try:
				p.ParseEmptyElemTag()
				self.fail("Expected ParseEmptyElem to be unimplemented.")
			except NotImplementedError:
				pass
			name,attrs,emptyFlag=p.ParseSTag()
			self.failUnless(emptyFlag,"Expected empty element tag")
			self.failUnless(name==match[0],"Element name mismatch: %s"%name)
			self.failUnless(attrs==match[1],"Element attrs mismatch: %s"%repr(attrs))
			p.ParseS()
		self.failUnless(p.theChar is None,"Short parse of empty elements")
	
	def testElementDecl(self):
		"""[45] elementdecl ::= '<!ELEMENT' S Name S contentspec S? '>'	"""
		s="""<!ELEMENT elem1 ANY>
		<!ELEMENT elem2 (#PCDATA)>
		<!ELEMENT elem3 ( A | ( B,C )? | (D,E,F)* | (G,H)+ | (I | (J,K)+)* ) >"""
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		try:
			while True:
				p.ParseElementDecl(p.theChar!='<')
				p.ParseS()
		except XMLWellFormedError:
			pass
		eType=p.dtd.GetElementType('elem1')
		self.failUnless(eType.contentType==XMLElementType.Any,"First element")
		eType=p.dtd.GetElementType('elem2')
		self.failUnless(eType.contentType==XMLElementType.Mixed,"Second element")
		eType=p.dtd.GetElementType('elem3')
		self.failUnless(eType.contentType==XMLElementType.ElementContent,"Third element")
		self.failUnless(eType.contentModel.children[4].children[1].children[1].name=="K","Third element model")
		self.failUnless(p.theChar is None,"Short parse on element declarations")
		
	def testContentSpec(self):
		"""[46] contentspec ::= 'EMPTY' | 'ANY' | Mixed | children """
		s="""EMPTY
			ANY
			(#PCDATA)
			(#PCDATA)*
			( #PCDATA | Steve1 | Steve2 )*
			(Particle2|Particle3)?
			(Particle4,Particle5,Particle6)+"""
		e=XMLEntity(s)
		m=[	(XMLElementType.Empty,None,None,None),
			(XMLElementType.Any,None,None,None),
			(XMLElementType.Mixed,XMLChoiceList,XMLContentParticle.ZeroOrMore,0),
			(XMLElementType.Mixed,XMLChoiceList,XMLContentParticle.ZeroOrMore,0),
			(XMLElementType.Mixed,XMLChoiceList,XMLContentParticle.ZeroOrMore,2),
			(XMLElementType.ElementContent,XMLChoiceList,XMLContentParticle.ZeroOrOne,2),
			(XMLElementType.ElementContent,XMLSequenceList,XMLContentParticle.OneOrMore,3) ]
		p=XMLParser(e)
		for match in m:
			eType=XMLElementType()
			p.ParseContentSpec(eType)
			self.failUnless(eType.contentType==match[0],"Content type mismatch")
			if match[1] is None:
				self.failUnless(eType.contentModel is None,"Content model type mismatch")
			else:	
				self.failUnless(isinstance(eType.contentModel,match[1]),"Content model type mismatch")
				self.failUnless(eType.contentModel.occurrence==match[2],"Content model occurrence mismatch")
				self.failUnless(len(eType.contentModel.children)==match[3],"Number of children in content model mismatch")
			p.ParseS()
		self.failUnless(p.theChar is None,"Incomplete parse in contentspec tests: %s"%repr(p.theChar))
		
	def testChildren(self):
		"""[47] children ::= (choice | seq) ('?' | '*' | '+')? """
		s="""(Particle2|Particle3)?
			(Particle4,Particle5)*
			(Particle6,(Particle7|Particle8),(Particle9,Particle10))+
			Particle1"""
		e=XMLEntity(s)
		m=[	(XMLChoiceList,XMLContentParticle.ZeroOrOne),
			(XMLSequenceList,XMLContentParticle.ZeroOrMore),
			(XMLSequenceList,XMLContentParticle.OneOrMore) ]
		p=XMLParser(e)
		for match in m:
			cp=p.ParseChildren()
			self.failUnless(isinstance(cp,match[0]),"Particle type mismatch")
			self.failUnless(cp.occurrence==match[1],"Particle occurrence mismatch, %i (expected %i)"%(cp.occurrence,match[1]))
			p.ParseS()
		try:
			cp=p.ParseChildren()
			self.fail("Name not allowed outside choice or sequence")
		except XMLFatalError:
			# fails to parse 'Particle1'
			p.ParseLiteral('Particle1')
		self.failUnless(p.theChar is None,"Incomplete parse in children tests: %s"%repr(p.theChar))
		
	def testCP(self):
		"""[48] cp ::= (Name | choice | seq) ('?' | '*' | '+')? """
		s="""Particle1
			(Particle2|Particle3)?
			(Particle4,Particle5)*
			(Particle6,(Particle7|Particle8),(Particle9,Particle10))+"""
		e=XMLEntity(s)
		m=[	(XMLNameParticle,XMLContentParticle.ExactlyOnce),
			(XMLChoiceList,XMLContentParticle.ZeroOrOne),
			(XMLSequenceList,XMLContentParticle.ZeroOrMore),
			(XMLSequenceList,XMLContentParticle.OneOrMore) ]
		p=XMLParser(e)
		for match in m:
			cp=p.ParseCP()
			self.failUnless(isinstance(cp,match[0]),"Particle type mismatch")
			self.failUnless(cp.occurrence==match[1],"Particle occurrence mismatch, %i (expected %i)"%(cp.occurrence,match[1]))
			p.ParseS()
		self.failUnless(p.theChar is None,"Incomplete parse in CP tests: %s"%repr(p.theChar))

	def testChoice(self):
		"""[49] choice ::= '(' S? cp ( S? '|' S? cp )+ S? ')' """
		s="(Particle1|Particle2?|Particle3*)( Particle4+ | Particle5 )(Particle6|Particle7+)+(Particle8*)()"
		e=XMLEntity(s)
		m=[[('Particle1',XMLContentParticle.ExactlyOnce),('Particle2',XMLContentParticle.ZeroOrOne),
			('Particle3',XMLContentParticle.ZeroOrMore)],[('Particle4',XMLContentParticle.OneOrMore),
			('Particle5',XMLContentParticle.ExactlyOnce)],[('Particle6',XMLContentParticle.ExactlyOnce),
			('Particle7',XMLContentParticle.OneOrMore)]]
		p=XMLParser(e)
		for match in m:
			cp=p.ParseChoice()
			self.failUnless(isinstance(cp,XMLChoiceList),"Choice list match failed")
			self.failUnless(len(cp.children)==len(match),"Choice list match length mismatch")
			i=0
			for cpi,mi in zip(cp.children,match):
				self.failUnless(isinstance(cpi,XMLNameParticle),"Not a name particle")
				self.failUnless(cpi.name==mi[0],"Particle name mismatch")
				self.failUnless(cpi.occurrence==mi[1],"Particle occurrence mismatch")
		self.failUnless(p.ParseLiteral('+'),"Final occurrence parsed in error")
		try:
			cp=p.ParseChoice()
			self.fail("Singleton choice not allowed")
		except XMLFatalError:
			# fails to parse ')'
			p.ParseLiteral(')')
		try:
			cp=p.ParseChoice()
			self.fail("Empty choice not allowed")
		except XMLFatalError:
			# fails to parse ')'
			p.ParseLiteral(')')
		self.failUnless(p.theChar is None,"Incomplete parse in choice tests: %s"%repr(p.theChar))
	
	def testSeq(self):
		"""[50] seq ::= '(' S? cp ( S? ',' S? cp )* S? ')' """
		s="(Particle1,Particle2?,Particle3*)( Particle4+ , Particle5 )(Particle6+)+()"
		e=XMLEntity(s)
		m=[[('Particle1',XMLContentParticle.ExactlyOnce),('Particle2',XMLContentParticle.ZeroOrOne),
			('Particle3',XMLContentParticle.ZeroOrMore)],[('Particle4',XMLContentParticle.OneOrMore),
			('Particle5',XMLContentParticle.ExactlyOnce)],[('Particle6',XMLContentParticle.OneOrMore)]]
		p=XMLParser(e)
		for match in m:
			cp=p.ParseSeq()
			self.failUnless(isinstance(cp,XMLSequenceList),"Sequence match failed")
			self.failUnless(len(cp.children)==len(match),"Sequence match length mismatch")
			i=0
			for cpi,mi in zip(cp.children,match):
				self.failUnless(isinstance(cpi,XMLNameParticle),"Not a name particle")
				self.failUnless(cpi.name==mi[0],"Particle name mismatch")
				self.failUnless(cpi.occurrence==mi[1],"Particle occurrence mismatch")
		self.failUnless(p.ParseLiteral('+'),"Final occurrence parsed in error")
		try:
			cp=p.ParseSeq()
			self.fail("Empty sequence not allowed")
		except XMLFatalError:
			# fails to parse ')'
			p.ParseLiteral(')')
		self.failUnless(p.theChar is None,"Incomplete parse in sequence tests: %s"%repr(p.theChar))
		
	def testMixed(self):
		"""[51] Mixed ::= '(' S? '#PCDATA' (S? '|' S? Name)* S? ')*' | '(' S? '#PCDATA' S? ')' """
		s="(#PCDATA)(#PCDATA)*( #PCDATA | Steve1 | Steve2 )*( #PCDATA |Steve1|Steve2)*(#PCDATA|Steve1)(Steve1|#PCDATA)*"
		e=XMLEntity(s)
		m=[[],[],['Steve1','Steve2'],['Steve1','Steve2']]
		p=XMLParser(e)
		for match in m:
			cp=p.ParseMixed()
			self.failUnless(isinstance(cp,XMLChoiceList),"Mixed must be a choice")
			self.failUnless(cp.occurrence==XMLContentParticle.ZeroOrMore,"Mixed must be '*'")
			self.failUnless(len(cp.children)==len(match),"Particle count mismatch: %s"%str(match))
			for cpi,mi in zip(cp.children,match):
				self.failUnless(isinstance(cpi,XMLNameParticle),"Mixed particles must be names")
				self.failUnless(cpi.occurrence==XMLContentParticle.ExactlyOnce,"Mixed occurrence")
				self.failUnless(cpi.name==mi,"Mixed particle name")
		try:
			values=p.ParseMixed()
			self.fail("Missed trailing *")
		except XMLFatalError:
			# fails to parse ')*'
			p.ParseLiteral(')')
		try:
			values=p.ParseMixed()
			self.fail("#PCDATA must come first")
		except XMLFatalError:
			# fails to parse '#PCDATA' 
			p.ParseLiteral('Steve1|#PCDATA)*')
		self.failUnless(p.theChar is None,"Incomplete parse in Mixed tests: %s"%repr(p.theChar))
		
	def testAttlistDecl(self):
		"""[52] AttlistDecl ::= '<!ATTLIST' S Name AttDef* S? '>' """
		s="""<!ATTLIST elem attr CDATA 'Steve' attr2 CDATA #IMPLIED>
		<!ATTLIST elem attr3 (1|2|3) '1'>
		 elem2 (1|2|3) >"""
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		try:
			while True:
				p.ParseAttlistDecl(p.theChar!='<')
				p.ParseS()
		except XMLWellFormedError:
			pass
		aList=p.dtd.GetAttributeList('elem')
		self.failUnless(aList['attr'].defaultValue=='Steve',"First attribute")
		self.failUnless(aList['attr2'].presence==XMLAttributeDefinition.Implied,"Second attribute")
		self.failUnless(aList['attr3'].type==XMLAttributeDefinition.Enumeration,"Third attribute")
		aList=p.dtd.GetAttributeList('elem2')
		self.failUnless(aList is None,"Bad attribute")
		
	def testAttDef(self):
		"""[53] AttDef ::= S Name S AttType S DefaultDecl"""
		s=" attr CDATA 'Steve' attr2 CDATA #IMPLIED attr3 (1|2|3) '1' attr4 #REQUIRED"
		e=XMLEntity(s)
		m=[	('attr',XMLAttributeDefinition.CData,None,XMLAttributeDefinition.Default,'Steve'),
			('attr2',XMLAttributeDefinition.CData,None,XMLAttributeDefinition.Implied,None),
			('attr3',XMLAttributeDefinition.Enumeration,['1','2','3'],XMLAttributeDefinition.Default,'1')]
		p=XMLParser(e)
		for match in m:
			a=p.ParseAttDef()
			self.failUnless(a.name==match[0],"AttDef match failed: %s (expected %s)"%(a.name,match[0]))
			self.failUnless(a.type==match[1],"AttDef match failed: %i (expected %i)"%(a.type,match[1]))
			self.failUnless(a.values==match[2],"AttDef match failed: %s (expected %s)"%(a.values,match[2]))
			self.failUnless(a.presence==match[3],"AttDef match failed: %i (expected %i)"%(a.presence,match[3]))
			self.failUnless(a.defaultValue==match[4],"AttDef match failed: %s (expected %s)"%(a.defaultValue,match[4]))
		try:
			a=p.ParseAttDef()
			self.fail("Parsed bad AttDef: %s"%a.name)
		except XMLFatalError:
			pass
		
	def testAttType(self):
		"""[54] AttType ::= StringType | TokenizedType | EnumeratedType"""
		s="CDATA ENTITIES NOTATION (Steve) (1 | 2 | 3) NAMES)"
		e=XMLEntity(s)
		m=[(XMLAttributeDefinition.CData,None),(XMLAttributeDefinition.Entities,None),(XMLAttributeDefinition.Notation,['Steve']),
			(XMLAttributeDefinition.Enumeration,['1','2','3'])]
		p=XMLParser(e)
		for match in m:
			a=XMLAttributeDefinition()
			p.ParseAttType(a)
			self.failUnless(a.type==match[0],"Attribute type match failed: %i (expected %i)"%(a.type,match[0]))
			self.failUnless(a.values==match[1],"Attribute type match failed: %s (expected %s)"%(a.values,match[1]))
			p.ParseS()
		try:
			a=XMLAttributeDefinition()
			value=p.ParseAttType(a)
			self.fail("Parsed bad AttType: %i; %s"%(a.type,a.values))
		except XMLFatalError:
			pass
				
	def testStringType(self):
		"""[55] StringType ::= 'CDATA' """
		s="CDATA ID"
		e=XMLEntity(s)
		m=[(XMLAttributeDefinition.CData,None)]
		p=XMLParser(e)
		for match in m:
			a=XMLAttributeDefinition()
			p.ParseStringType(a)
			self.failUnless(a.type==match[0],"String type match failed: %i (expected %i)"%(a.type,match[0]))
			self.failUnless(a.values==match[1],"String type match failed: %s (expected %s)"%(a.values,match[1]))
			p.ParseS()
		try:
			a=XMLAttributeDefinition()
			value=p.ParseStringType(a)
			self.fail("Parsed bad StringType: %i; %s"%(a.type,a.values))
		except XMLFatalError:
			pass
		
	def testTokenizedType(self):
		"""[56] TokenizedType ::= 'ID' | 'IDREF' | 'IDREFS' | 'ENTITY' | 'ENTITIES'	 | 'NMTOKEN' | 'NMTOKENS' """
		s="ID IDREF IDREFS ENTITY ENTITIES NMTOKEN NMTOKENS NAME"
		e=XMLEntity(s)
		m=[(XMLAttributeDefinition.ID,None),(XMLAttributeDefinition.IDRef,None),(XMLAttributeDefinition.IDRefs,None),
			(XMLAttributeDefinition.Entity,None),(XMLAttributeDefinition.Entities,None),(XMLAttributeDefinition.NmToken,None),
			(XMLAttributeDefinition.NmTokens,None)]
		p=XMLParser(e)
		for match in m:
			a=XMLAttributeDefinition()
			p.ParseTokenizedType(a)
			self.failUnless(a.type==match[0],"Tokenized type match failed: %i (expected %i)"%(a.type,match[0]))
			self.failUnless(a.values==match[1],"Tokenized type match failed: %s (expected %s)"%(a.values,match[1]))
			p.ParseS()
		try:
			a=XMLAttributeDefinition()
			value=p.ParseTokenizedType(a)
			self.fail("Parsed bad Tokenized: %i; %s"%(a.type,a.values))
		except XMLFatalError:
			pass
		
	def testEnumeratedType(self):
		"""[57] EnumeratedType ::= NotationType | Enumeration """
		s="NOTATION (Steve1)NOTATION (Steve1|Steve2)(1|2|3)NOTATION (1|2|3)"
		e=XMLEntity(s)
		m=[(XMLAttributeDefinition.Notation,['Steve1']),(XMLAttributeDefinition.Notation,['Steve1','Steve2']),(XMLAttributeDefinition.Enumeration,['1','2','3'])]
		p=XMLParser(e)
		for match in m:
			a=XMLAttributeDefinition()
			p.ParseEnumeratedType(a)
			self.failUnless(a.type==match[0],"Enumerated type match failed: %i (expected %i)"%(a.type,match[0]))
			self.failUnless(a.values==match[1],"Enumerated type match failed: %s (expected %s)"%(a.values,match[1]))
		try:
			a=XMLAttributeDefinition()
			value=p.ParseEnumeratedType(a)
			self.fail("Parsed bad EnumeratedType: %i; %s"%(a.type,a.values))
		except XMLFatalError:
			pass
		
	def testNotationType(self):
		"""[58] NotationType ::= 'NOTATION' S '(' S? Name (S? '|' S? Name)* S? ')'"""
		s="NOTATION (Steve1)NOTATION (Steve1|Steve2|Steve3)NOTATION ( Steve1 ) ( Steve1 | Steve2 | Steve3 )NOTATION(Steve1|Steve2)"
		e=XMLEntity(s)
		m=[['Steve1'],['Steve1','Steve2','Steve3'],['Steve1'],['Steve1','Steve2','Steve3']]
		p=XMLParser(e)
		for match in m:
			value=p.ParseNotationType(p.theChar!='N')
			self.failUnless(value==match,"NotationType match failed: %s (expected %s)"%(value,match))
		try:
			value=p.ParseNotationType()
			self.fail("Parsed bad NotationType: %s"%value)
		except XMLFatalError:
			pass

	def testEnumeration(self):
		"""[59] Enumeration	   ::=   	'(' S? Nmtoken (S? '|' S? Nmtoken)* S? ')' """
		s="(Steve1)(Steve1|Steve2|3Steve)( Steve1 )( Steve1 | Steve2 | 3Steve )(Steve1|Steve 2)"
		e=XMLEntity(s)
		m=[['Steve1'],['Steve1','Steve2','3Steve'],['Steve1'],['Steve1','Steve2','3Steve']]
		p=XMLParser(e)
		for match in m:
			value=p.ParseEnumeration()
			self.failUnless(value==match,"Enumeration match failed: %s (expected %s)"%(value,match))
		try:
			value=p.ParseEnumeration()
			self.fail("Parsed bad Enumeration: %s"%value)
		except XMLFatalError:
			pass

	def testDefaultDecl(self):
		"""[60] DefaultDecl ::= '#REQUIRED' | '#IMPLIED' | (('#FIXED' S)? AttValue) """
		s="#REQUIRED #IMPLIED #FIXED 'Steve' 'Steve'Steve"
		e=XMLEntity(s)
		m=[(XMLAttributeDefinition.Required,None),(XMLAttributeDefinition.Implied,None),(XMLAttributeDefinition.Fixed,'Steve'),
			(XMLAttributeDefinition.Default,'Steve')]
		p=XMLParser(e)
		for match in m:
			a=XMLAttributeDefinition()
			p.ParseDefaultDecl(a)
			self.failUnless(a.presence==match[0],"DefaultDecl declaration match failed: %i (expected %i)"%(a.presence,match[0]))
			self.failUnless(a.defaultValue==match[1],"DefaultDecl value match failed: %s (expected %s)"%(a.defaultValue,match[1]))
			p.ParseS()
		try:
			a=XMLAttributeDefinition()
			p.ParseDefaultDecl(a)
			self.fail("Parsed bad DefaultDecl: (%i,%s)"%(a.presence,a.defaultValue))
		except XMLFatalError:
			pass
		
	def testConditionalSect(self):
		"""[61] conditionalSect ::= includeSect | ignoreSect"""
		s="<![%include;[ <!ENTITY included 'yes'> <![ IGNORE [ <!ENTITY ignored 'no'> ]]> ]]>"
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('include','INCLUDE'))
		p.checkValidity=True
		p.refMode=XMLParser.RefModeInDTD
		try:
			p.ParseConditionalSect()
			self.failUnless(p.theChar is None,"Short parse on ConditionalSect: %s"%p.theChar)
			self.failUnless(p.dtd.GetEntity('included').definition=='yes',"included entity declaration")
			self.failUnless(p.dtd.GetEntity('ignored')==None,"ignored entity declaration")			
		except XMLWellFormedError,e:
			self.fail("ParseConditionalSect positive test: %s\n%s"%(s,str(e)))
		
	def testIncludeSect(self):
		"""[62] includeSect ::= '<![' S? 'INCLUDE' S? '[' extSubsetDecl ']]>' """
		for s in ["<![INCLUDE[]]>","<![ INCLUDE [ <?stuff?> ]]>","<![ INCLUDE [<![IGNORE[ included ]]> ]]>",
			"<![%include;[]]>"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.dtd=XMLDTD()
			p.dtd.DeclareEntity(XMLParameterEntity('include','INCLUDE'))
			p.checkValidity=True
			p.refMode=XMLParser.RefModeInDTD
			try:
				p.ParseIncludeSect()
				self.failUnless(p.theChar is None,"Short parse on IncludeSect: %s"%p.theChar)
			except XMLWellFormedError,e:
				self.fail("ParseIncludeSect positive test: %s\n%s"%(s,str(e)))
		for s in [" <![INCLUDE[]>","<! [INCLUDE[]]>","<![INCLUDE[] ]>"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.refMode=XMLParser.RefModeInDTD
			try:
				p.ParseIncludeSect()
				self.fail("ParseIncludeSect negative well-formedness test: %s"%s)
			except XMLWellFormedError:
				pass
		for s in ["<![ %include1; <?stuff?> ]]>","%include2; [ <!--stuff--> ]]>",
			"<![ INCLUDE [ <?stuff?> %include3;"
			]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.refMode=XMLParser.RefModeInContent
			p.dtd=XMLDTD()
			p.dtd.DeclareEntity(XMLParameterEntity('include1','INCLUDE ['))			
			p.dtd.DeclareEntity(XMLParameterEntity('include2','<![INCLUDE '))			
			p.dtd.DeclareEntity(XMLParameterEntity('include3','<?included?> ]]>'))		
			p.checkValidity=True
			p.raiseValidityErrors=True
			p.refMode=XMLParser.RefModeInDTD
			try:
				p.ParseS()
				p.ParseIncludeSect()
				self.fail("ParseIncludeSect negative validity test: %s"%s)
			except XMLWellFormedError,e:
				print e
				self.fail("ParseIncludeSect spurious well-formed error: %s"%s)
			except XMLValidityError:
				pass

	def testIgnoreSect(self):
		"""[63] ignoreSect ::= '<![' S? 'IGNORE' S? '[' ignoreSectContents* ']]>' """
		for s in ["<![IGNORE[]]>","<![ IGNORE [ stuff ]]>","<![ IGNORE [<![INCLUDE[ ignored ]]> ]]>",
			"<![%ignore;[]]>"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.dtd=XMLDTD()
			p.dtd.DeclareEntity(XMLParameterEntity('ignore','IGNORE'))
			p.checkValidity=True
			p.refMode=XMLParser.RefModeInDTD
			try:
				p.ParseIgnoreSect()
				self.failUnless(p.theChar is None,"Short parse on IgnoreSect: %s"%p.theChar)
			except XMLWellFormedError:
				self.fail("ParseIgnoreSect positive test: %s"%s)
		for s in [" <![IGNORE[]>","<! [IGNORE[]]>","<![IGNORE[] ]>"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.refMode=XMLParser.RefModeInDTD
			try:
				p.ParseIgnoreSect()
				self.fail("ParseIgnoreSect negative well-formedness test: %s"%s)
			except XMLWellFormedError:
				pass
		for s in ["<![ %ignore1; stuff ]]>","%ignore2; [ stuff ]]>",
			# "<![ IGNORE [ stuff %ignore3;" - this PE is ignored so we can't test this
			]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.refMode=XMLParser.RefModeInContent
			p.dtd=XMLDTD()
			p.dtd.DeclareEntity(XMLParameterEntity('ignore1','IGNORE ['))			
			p.dtd.DeclareEntity(XMLParameterEntity('ignore2','<![IGNORE '))			
			p.dtd.DeclareEntity(XMLParameterEntity('ignore3','ignored ]]>'))		
			p.checkValidity=True
			p.raiseValidityErrors=True
			p.refMode=XMLParser.RefModeInDTD
			try:
				p.ParseS()
				p.ParseIgnoreSect()
				self.fail("ParseIgnoreSect negative validity test: %s"%s)
			except XMLWellFormedError,e:
				print e
				self.fail("ParseIgnoreSect spurious well-formed error: %s"%s)
			except XMLValidityError:
				pass
		
	def testIgnoreSectContents(self):
		"""[64] ignoreSectContents ::= Ignore ('<![' ignoreSectContents ']]>' Ignore)* """
		s="preamble<![ INCLUDE [ %x; <![IGNORE[ also ignored ]]>]]> also ignored]]>end"
		e=XMLEntity(s)
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('x','bad'))
		p.ParseIgnoreSectContents()
		p.ParseLiteral(']]>')
		self.failUnless(p.ParseName()=='end',"Failed to parse ignore section contents")
		
	def testIgnore(self):
		"""[65] Ignore ::= Char* - (Char* ('<![' | ']]>') Char*) """
		s="<!FIRST%x;1st]]>second<![third]]3rd<!3rd<3rd]3rd"
		e=XMLEntity(s)
		# These tests are a bit odd because we follow the entity and not the parser
		# so we expect the trailing markup to be consumed; we check theChar too to be sure.
		m=[('<!FIRST%x;1st]]>',']'),('second<![','<'),('third]]3rd<!3rd<3rd]3rd',None)]
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('x','bad'))
		pos=0
		for match,c in m:
			p.ParseIgnore()
			self.failUnless(p.theChar==c,"Parser position: %s (expected %s)"%(p.theChar,c))
			self.failUnless(s[pos:e.linePos-1]==match,"Match failed: %s (expected %s)"%(s[pos:e.linePos-1],match))
			p.NextChar()
			pos=pos+len(match)
		
	def testCharRef(self):
		"""[66] CharRef ::= '&#' [0-9]+ ';'  |  '&#x' [0-9a-fA-F]+ ';' """
		for m in (XMLParser.RefModeInContent,XMLParser.RefModeInAttributeValue,XMLParser.RefModeInEntityValue):
			e=XMLEntity("&#xe9;")
			p=XMLParser(e)
			p.refMode=m
			data=p.ParseCharRef()
			self.failUnless(data==u'\xe9',"ParseCharRef failed to interpret hex character reference: %s"%data)
			self.failUnless(p.theChar is None,"Short parse on CharRef: %s"%p.theChar)
		e=XMLEntity("&#xe9;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeAsAttributeValue
		data=p.ParseCharRef()
		self.failUnless(data=="&#xe9;","ParseCharRef AsAttribute: %s"%data)
		self.failUnless(p.theChar is None,"Short parse on CharRef: %s"%p.theChar)
		e=XMLEntity("&#xe9;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInDTD
		try:
			data=p.ParseCharRef()
			self.fail("ParseCharRef InDTD")
		except XMLForbiddenEntityReference:
			pass
		e=XMLEntity("#233;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInContent
		data=p.ParseCharRef(True)
		self.failUnless(data==u'\xe9',"ParseCharRef failed to interpret decimal character reference: %s"%data)
		self.failUnless(p.theChar is None,"Short parse on CharRef: %s"%p.theChar)
		for s in [" &#xe9;","& #xe9;","&# xe9;","&#xe 9;","&#xe9 ;","&#e9;","&#xg9;","&#1;","&#;","&#x;"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.refMode=XMLParser.RefModeInContent
			try:
				p.ParseCharRef()
				self.fail("ParseCharRef negative test: %s"%s)
			except XMLWellFormedError:
				pass					
		
	def testReference(self):
		"""[67] Reference ::= EntityRef | CharRef """
		e=XMLEntity("&animal;")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLGeneralEntity('animal','dog'))
		p.refMode=XMLParser.RefModeInContent
		data=p.ParseReference()
		self.failUnless(data=='',"ParseReference failed to interpret entity reference")
		self.failUnless(p.ParseName()=='dog',"Failed to replace Entity in Content")
		self.failUnless(p.theChar is None,"Short parse on EntityRef")
		e=XMLEntity("&#xe9;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInContent
		data=p.ParseReference()
		self.failUnless(data==u'\xe9',"ParseReference failed to interpret character reference: %s"%data)
		self.failUnless(p.theChar is None,"Short parse on EntityRef: %s"%p.theChar)
		for s in [" &animal;","& animal;","&animal ;","animal","#xE9"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseReference()
				self.fail("ParseReference negative test: %s"%s)
			except XMLWellFormedError:
				pass	
		
	def testEntityRef(self):
		"""[68] EntityRef ::= '&' Name ';'	"""
		e=XMLEntity("&amp;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInContent
		self.failUnless(p.ParseEntityRef()=='&',"Predefined entity not recognized in Content")
		self.failUnless(p.theChar is None,"Short parse on Entity replacement text")
		e=XMLEntity("&animal;")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLGeneralEntity('animal','dog'))
		p.refMode=XMLParser.RefModeInContent
		self.failUnless(p.ParseEntityRef()=='',"EntityRef not recognized in Content")
		# This should result in the entity value being expanded into the stream
		self.failUnless(p.ParseName()=='dog',"Failed to replace Entity in Content")
		self.failUnless(p.theChar is None,"Short parse on Entity replacement text")
		e=XMLEntity("animal;")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLGeneralEntity('animal','dog'))
		p.refMode=XMLParser.RefModeInAttributeValue
		self.failUnless(p.ParseEntityRef(True)=='',"EntityRef not recognized in Attribute Value")
		# This should result in the entity value being expanded into the stream
		self.failUnless(p.ParseName()=='dog',"Failed to replace Entity in Attribute Vaue")
		self.failUnless(p.theChar is None,"Short parse on Entity replacement text")
		e=XMLEntity("&animal;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeAsAttributeValue
		try:
			p.ParseEntityRef()
			self.fail("EntityRef recognized as Attribute Value")
		except XMLForbiddenEntityReference:
			pass
		e=XMLEntity("&animal;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInEntityValue
		data=p.ParseEntityRef()
		self.failUnless(data=='&animal;',"EntityRef recognized in EntityValue: %s"%data)
		self.failUnless(p.theChar is None,"Short parse on EntityRef")
		e=XMLEntity("&animal;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInDTD
		try:
			p.ParseEntityRef()
			self.fail("EntityRef recognized in DTD")
		except XMLForbiddenEntityReference:
			pass
		e=XMLEntity("<element attribute='a-&EndAttr;>")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('EndAttr',"27'"))
		try:
			p.ParseSTag()
			self.fail("EntityRef quote test failed in attribute value")
		except XMLWellFormedError:
			pass
		
	def testPEReference(self):
		"""[69] PEReference ::= '%' Name ';' """
		e=XMLEntity("%animal;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInContent
		data=p.ParsePEReference()
		self.failUnless(data=='%animal;',"PEReference recognized in content: %s"%data)
		self.failUnless(p.theChar is None,"Short parse on PEReference")
		e=XMLEntity("%animal;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeInAttributeValue
		self.failUnless(p.ParsePEReference()=='%animal;',"PEReference recognized in attribute value")
		self.failUnless(p.theChar is None,"Short parse on PEReference")
		e=XMLEntity("%animal;")
		p=XMLParser(e)
		p.refMode=XMLParser.RefModeAsAttributeValue
		self.failUnless(p.ParsePEReference()=="%animal;","PEReference recognized as attribute value")
		self.failUnless(p.theChar is None,"Short parse on PEReference")
		e=XMLEntity("%animal;")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('animal','dog'))
		p.refMode=XMLParser.RefModeInEntityValue
		self.failUnless(p.ParsePEReference()=='',"PEReference not recognized in entity value")
		# This should result in the entity value being expanded into the stream
		self.failUnless(p.ParseName()=='dog',"Failed to replace PE in entity value")
		self.failUnless(p.theChar is None,"Short parse on PEReference replacement text")
		e=XMLEntity("%animal;")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('animal','dog'))
		p.refMode=XMLParser.RefModeInDTD
		self.failUnless(p.ParsePEReference()=='',"PEReference not recognized in DTD")
		# This should result in the entity value being expanded into the stream with surrounding spaces
		self.failUnless(p.ParseS()==' ',"Missing leading space on PE replacement text")
		self.failUnless(p.ParseName()=='dog',"Failed to replace PE in DTD")
		self.failUnless(p.ParseS()==' ',"Missing trailing space on PE replacement text")
		self.failUnless(p.theChar is None,"Short parse on PEReference")
		e=XMLEntity('<!ENTITY WhatHeSaid "He said %YN;" >')
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.dtd.DeclareEntity(XMLParameterEntity('YN','"Yes"'))
		try:
			ge=p.ParseEntityDecl()
			# This should result in the entity value being expanded into the stream with surrounding spaces
			self.failUnless(ge.definition=='He said "Yes"',"PEReference quote test failed in entity value: %s"%ge.definition)
			self.failUnless(p.theChar is None,"Short parse on PEReference in entity declaration")
		except XMLWellFormedError:
			self.fail("PEReference quote test failed in entity value")
	
		
	def testEntityDecl(self):
		"""[70] EntityDecl ::= GEDecl | PEDecl """
		e=XMLEntity("<!ENTITY Steve 'SteveValue'>")
		p=XMLParser(e)
		ed=p.ParseEntityDecl()
		self.failUnless(isinstance(ed,XMLGeneralEntity),"ParseEntityDecl failed to return GeneralEntity")		
		self.failUnless(ed.name=='Steve',"Failed to parse general entity name")
		self.failUnless(p.theChar is None,"Short parse on EntityDecl")
		e=XMLEntity(" % Steve 'SteveValue'>")
		p=XMLParser(e)
		ed=p.ParseEntityDecl(True)
		self.failUnless(isinstance(ed,XMLParameterEntity),"ParseEntityDecl failed to return ParameterEntity")		
		self.failUnless(ed.name=='Steve',"Failed to parse parameter entity name")
		self.failUnless(p.theChar is None,"Short parse on EntityDecl")
		
	def testGEDecl(self):
		"""[71] GEDecl ::= '<!ENTITY' S Name S EntityDef S? '>' """
		e=XMLEntity("<!ENTITY Steve 'SteveValue'>")
		p=XMLParser(e)
		ge=p.ParseGEDecl()
		self.failUnless(isinstance(ge,XMLGeneralEntity),"ParseGEDecl failed to return GeneralEntity")		
		self.failUnless(ge.name=='Steve',"Failed to parse general entity name")
		self.failUnless(ge.definition=='SteveValue',"Failed to parse general entity value")
		self.failUnless(p.theChar is None,"Short parse on GEDecl")
		e=XMLEntity("Steve PUBLIC 'Steve' '/home/steve.txt' NDATA SteveN  >")
		p=XMLParser(e)
		ge=p.ParseGEDecl(True)
		self.failUnless(ge.definition.public=='Steve',"ParseGEDecl failed to parse external public ID")
		self.failUnless(ge.definition.system=='/home/steve.txt',"ParseGEDecl failed to parse external system ID")
		self.failUnless(ge.notation=='SteveN',"ParseGEDecl failed to parse unparsed entity notation")
		self.failUnless(p.theChar is None,"Short parse on GEDecl")
		for s in ["<!entity Steve 'v'>","<!ENTITYSteve 'v'>",
			"<!ENTITY Steve PUBLIC 'Steve' '/home/steve.txt'NDATA SteveN >",
			"  Steve PUBLIC 'Steve' '/home/steve.txt' NDATA SteveN  >"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				ge=p.ParseGEDecl(s[0]!='<')
				self.fail("GEDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass	
	
	def testPEDecl(self):
		"""[72] PEDecl ::= '<!ENTITY' S '%' S Name S PEDef S? '>' """
		e=XMLEntity("<!ENTITY % Steve 'SteveValue'>")
		p=XMLParser(e)
		pe=p.ParsePEDecl()
		self.failUnless(isinstance(pe,XMLParameterEntity),"ParsePEDecl failed to return ParameterEntity")		
		self.failUnless(pe.name=='Steve',"Failed to parse parameter entity name")
		self.failUnless(pe.definition=='SteveValue',"Failed to parse parameter entity value")
		self.failUnless(p.theChar is None,"Short parse on PEDecl")
		e=XMLEntity("% Steve PUBLIC 'Steve' '/home/steve.txt'   >")
		p=XMLParser(e)
		pe=p.ParsePEDecl(True)
		self.failUnless(pe.definition.public=='Steve',"ParsePEDecl failed to parse external public ID")
		self.failUnless(pe.definition.system=='/home/steve.txt',"ParsePEDecl failed to parse external system ID")
		self.failUnless(p.theChar is None,"Short parse on PEDecl")
		for s in ["<!entity % Steve 'v'>","<!ENTITY% Steve 'v'>","<!ENTITY %Steve 'v'>","<!ENTITY % Steve'v'>",
			"  % Steve PUBLIC 'Steve' '/home/steve.txt'   >"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				pe=p.ParsePEDecl(s[0]!='<')
				self.fail("PEDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass	
		
	def testEntityDef(self):
		"""[73] EntityDef ::= EntityValue | (ExternalID NDataDecl?) """
		e=XMLEntity("'Steve'")
		p=XMLParser(e)
		ge=XMLGeneralEntity()
		p.ParseEntityDef(ge)
		self.failUnless(type(ge.definition) in StringTypes,"ParseEntityDef failed to for internal entity")		
		self.failUnless(ge.definition=='Steve',"Failed to parse internal entity value")
		self.failUnless(ge.notation is None,"Found notation for internal entity")
		self.failUnless(p.theChar is None,"Short parse on EntityDef")
		e=XMLEntity("PUBLIC 'Steve' '/home/steve.txt'")
		p=XMLParser(e)
		ge=XMLGeneralEntity()
		p.ParseEntityDef(ge)
		self.failUnless(isinstance(ge.definition,XMLExternalID),"ParseEntityDef failed for external entity")
		self.failUnless(ge.definition.public=='Steve',"ParseEntityDef failed to parse external public ID")
		self.failUnless(ge.definition.system=='/home/steve.txt',"ParseEntityDef failed to parse external system ID")
		self.failUnless(ge.notation is None,"Found notation for internal entity")
		self.failUnless(p.theChar is None,"Short parse on EntityDef")
		e=XMLEntity("SYSTEM '/path' NDATA SteveN")
		p=XMLParser(e)
		ge=XMLGeneralEntity()
		p.ParseEntityDef(ge)
		self.failUnless(ge.definition.public is None,"ParseEntityDef found spurious public ID")
		self.failUnless(ge.definition.system=='/path',"ParseEntityDef failed to parse external system ID")
		self.failUnless(ge.notation=='SteveN',"Failed to find notation for unparsed external entity")
		self.failUnless(p.theChar is None,"Short parse on EntityDef")
		for s in ["NDATA 'SteveN'"," 'Steve'"," SYSTEM '/path'"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			ge=XMLGeneralEntity()
			try:
				p.ParseEntityDef(ge)
				self.fail("EntityDef negative test: %s"%s)
			except XMLWellFormedError:
				pass	
		
	def testPEDef(self):
		"""[74] PEDef ::= EntityValue | ExternalID """
		e=XMLEntity("PUBLIC 'Steve' '/home/steve.txt'")
		p=XMLParser(e)
		pe=XMLParameterEntity()
		p.ParsePEDef(pe)
		self.failUnless(isinstance(pe.definition,XMLExternalID),"ParsePEDef failed to return XMLExternalID instance")
		self.failUnless(pe.definition.public=='Steve',"Failed to parse external public ID")
		self.failUnless(pe.definition.system=='/home/steve.txt',"Failed to parse external system ID")
		self.failUnless(p.theChar is None,"Short parse on PEDef")
		e=XMLEntity("'Steve'")
		p=XMLParser(e)
		pe=XMLParameterEntity()
		p.ParsePEDef(pe)
		self.failUnless(type(pe.definition) in StringTypes,"ParsePEDef failed to return String value")
		self.failUnless(pe.definition=='Steve',"Failed to parse simple entity value")
		self.failUnless(p.theChar is None,"Short parse on PEDef")
		e=XMLEntity('"Caf&#xE9;s &amp; Bars"')
		p=XMLParser(e)
		pe=XMLParameterEntity()
		p.ParsePEDef(pe)
		self.failUnless(type(pe.definition) in StringTypes,"ParsePEDef failed to return String value")
		self.failUnless(pe.definition==u'Caf\xe9s &amp; Bars',"Failed to replace character entities: %s"%repr(pe.definition))
		self.failUnless(p.theChar is None,"Short parse on PEDef")
		for s in ["Steve","Caf&#xE9;s &amp; Bars","PUBLIC 'Steve'"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			pe=XMLParameterEntity()
			try:
				p.ParsePEDef(pe)
				self.fail("PEDef negative test: %s"%s)
			except XMLWellFormedError:
				pass
		
	def testExternalID(self):
		"""[75] ExternalID ::= 'SYSTEM' S SystemLiteral | 'PUBLIC' S PubidLiteral S SystemLiteral """
		e=XMLEntity("PUBLIC 'Steve' '/home/steve.txt'")
		p=XMLParser(e)
		xID=p.ParseExternalID()
		self.failUnless(xID.public=='Steve',"Failed to parse external public ID")
		self.failUnless(xID.system=='/home/steve.txt',"Failed to parse external system ID")
		self.failUnless(p.theChar is None,"Short parse on ExternalID")
		e=XMLEntity("SYSTEM  '/home/steve.txt'")
		p=XMLParser(e)
		xID=p.ParseExternalID()
		self.failUnless(xID.public is None,"Failed to parse external empty public ID")
		self.failUnless(xID.system=='/home/steve.txt',"Failed to parse external system ID")
		self.failUnless(p.theChar is None,"Short parse on ExternalID")
		for s in ["PUBLIC 'Steve'","'Steve'"," SYSTEM '/path'","SYSTEM'/path'","PUBLIC'Steve' '/path'",
			"PUBLIC 'Steve''/path'"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				xID=p.ParseExternalID()
				self.fail("ExternalID negative test: %s"%s)
			except XMLWellFormedError:
				pass
		
	def testNDataDecl(self):
		"""[76] NDataDecl ::= S 'NDATA' S Name """
		e=XMLEntity("  NDATA Steve")
		p=XMLParser(e)
		self.failUnless(p.ParseNDataDecl()=="Steve","Failed to parse NData declaration")
		self.failUnless(p.theChar is None,"Short parse on NData declaration")
		e=XMLEntity(" Steve")
		p=XMLParser(e)
		self.failUnless(p.ParseNDataDecl(True)=="Steve","Failed to parse NData declaration (no literal)")
		self.failUnless(p.theChar is None,"Short parse on NData declaration")
		for s in ["NDATA Steve"," MDATA Steve","NDATASteve"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseNDataDecl()
				self.fail("NDataDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass
		
	def testTextDecl(self):
		"""[77] TextDecl ::= '<?xml' VersionInfo? EncodingDecl S? '?>' """
		e=XMLEntity("<?xml version='1.0' encoding='x-steve'  ?>")
		p=XMLParser(e)
		t=p.ParseTextDecl()
		self.failUnless(t.version=="1.0")
		self.failUnless(t.encoding=="x-steve","Failed to parse encoding in text declaration")
		self.failUnless(p.theChar is None,"Short parse on TextDecl")
		e=XMLEntity('<?xml encoding = "x-steve"?>')
		p=XMLParser(e)
		t=p.ParseTextDecl()
		self.failUnless(t.version is None)
		self.failUnless(t.encoding=="x-steve","Failed to parse encoding in text declaration")
		self.failUnless(p.theChar is None,"Short parse on TextDecl")
		for s in ["<?xml version='1.0' ?>"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseEncodingDecl()
				self.fail("TextDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass
		
	# There is no method for parsing production [78]
	
	# There is no production [79]
	
	def testEncodingDecl(self):
		"""[80] EncodingDecl ::= S 'encoding' Eq ('"' EncName '"' | "'" EncName "'" ) """
		e=XMLEntity("  encoding = 'x-steve'")
		p=XMLParser(e)
		self.failUnless(p.ParseEncodingDecl()=="x-steve","Failed to parse encoding declaration")
		self.failUnless(p.theChar is None,"Short parse on EncodingDecl")
		e=XMLEntity(" = 'x-steve'")
		p=XMLParser(e)
		self.failUnless(p.ParseEncodingDecl(True)=="x-steve","Failed to parse encoding declaration (no literal)")
		self.failUnless(p.theChar is None,"Short parse on EncodingDecl")
		e=XMLEntity(' encoding="x-steve"')
		p=XMLParser(e)
		self.failUnless(p.ParseEncodingDecl()=="x-steve","Failed to parse encoding declaration")
		self.failUnless(p.theChar is None,"Short parse on EncodingDecl")
		for s in ["encoding = 'x-steve'"," decoding='x-steve'"," encoding=x-steve"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParseEncodingDecl()
				self.fail("EncodingDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass

	def testEncName(self):
		"""[81] EncName ::= [A-Za-z] ([A-Za-z0-9._] | '-')* """
		e=XMLEntity("UTF-8 UTF-16 ISO-10646-UCS-2 ISO-10646-UCS-4 Shift_JIS -8 _JIS .Private x.Private")
		result=["UTF-8","UTF-16","ISO-10646-UCS-2","ISO-10646-UCS-4","Shift_JIS","JIS","Private","x.Private"]
		p=XMLParser(e)
		i=0
		while p.theChar!=None:
			eName=p.ParseEncName()
			if eName:
				self.failUnless(eName==result[i],"%s parsed, expected %s"%(eName,result[i]))
				p.ParseS()
				i=i+1
			else:
				p.NextChar()		
		
	def testCaseNotationDecl(self):
		"""[82] NotationDecl ::= '<!NOTATION' S Name S (ExternalID | PublicID) S? '>'"""
		e=XMLEntity("<!NOTATION SteveN PUBLIC 'Steve' '/home/steve.txt'>")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.ParseNotationDecl()
		n=p.dtd.GetNotation('SteveN')
		self.failUnless(n.name=='SteveN',"Failed to parse notation name")
		self.failUnless(n.externalID.public=='Steve',"Failed to parse notation public ID")
		self.failUnless(n.externalID.system=='/home/steve.txt',"Failed to parse notation system ID")
		self.failUnless(p.theChar is None,"Short parse on NotationDecl")
		e=XMLEntity(" SteveN PUBLIC 'Steve' >")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.ParseNotationDecl(True)
		n=p.dtd.GetNotation('SteveN')
		self.failUnless(n.name=='SteveN',"Failed to parse notation name")
		self.failUnless(n.externalID.public=='Steve',"Failed to parse notation public ID")
		self.failUnless(n.externalID.system is None,"Failed to parse empty notation system ID")
		self.failUnless(p.theChar is None,"Short parse on NotationDecl")
		e=XMLEntity("<!NOTATION SteveN SYSTEM  '/home/steve.txt' >")
		p=XMLParser(e)
		p.dtd=XMLDTD()
		p.ParseNotationDecl()
		n=p.dtd.GetNotation('SteveN')
		self.failUnless(n.name=='SteveN',"Failed to parse notation name")
		self.failUnless(n.externalID.public is None,"Failed to parse empty notation public ID")
		self.failUnless(n.externalID.system=='/home/steve.txt',"Failed to parse notation system ID")
		self.failUnless(p.theChar is None,"Short parse on NotationDecl")
		for s in ["SteveN PUBLIC 'Steve' >"," 'SteveN' PUBLIC 'Steve' >","SteveN 'Steve' >",
			"SteveN PUBLIC >","SteveN SYSTEM>","SteveN SYSTEM 'Steve' '/path'>","SteveN PUBLIC 'Steve' "]:
			e=XMLEntity(s)
			p=XMLParser(e)
			p.dtd=XMLDTD()
			try:
				p.ParseNotationDecl(True)
				self.fail("NotationDecl negative test: %s"%s)
			except XMLWellFormedError:
				pass

	def testCasePublicID(self):
		"""[83] PublicID ::= 'PUBLIC' S PubidLiteral"""
		e=XMLEntity("PUBLIC 'Steve'")
		p=XMLParser(e)
		self.failUnless(p.ParsePublicID()=='Steve',"Failed to parse Public ID")
		self.failUnless(p.theChar is None,"Short parse on Public ID")
		for s in [" PUBLIC 'Steve'","'Steve'","PUBLIC'Steve'","Public 'Steve'"]:
			e=XMLEntity(s)
			p=XMLParser(e)
			try:
				p.ParsePublicID()
				self.fail("PublicID negative test: %s"%s)
			except XMLWellFormedError:
				pass
		

class XMLElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=XMLElement(None)
		self.failUnless(e.xmlname==None,'element name on construction')
		self.failUnless(e.GetDocument() is None,'document set on construction')
		attrs=e.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		children=e.GetChildren()
		self.failUnless(len(children)==0,"Children present on construction")
		e=XMLElement(None,'test')
		self.failUnless(e.xmlname=='test','element named on construction')
		
	def testCaseDefaultName(self):
		e=NamedElement(None)
		self.failUnless(e.xmlname=='test','element default name on construction')
	
	def testSetXMLName(self):
		e=NamedElement(None,'test2')
		self.failUnless(e.xmlname=='test2','element named explicitly in construction')

	def testAttributes(self):
		e=XMLElement(None,'test')
		e.SetAttribute('atest','value')
		attrs=e.GetAttributes()
		self.failUnless(len(attrs.keys())==1,"Attribute not set")
		self.failUnless(attrs['atest']=='value',"Attribute not set correctly")
		e=ReflectiveElement(None)
		e.SetAttribute('atest','value')
		self.failUnless(e.atest=='value',"Attribute relfection")
		attrs=e.GetAttributes()
		self.failUnless(attrs['atest']=='value',"Attribute not set correctly")
		e.SetAttribute('btest','Yes')
		self.failUnless(e.bTest=='Yes',"Attribute relfection with simple assignment")
		attrs=e.GetAttributes()
		self.failUnless(attrs['btest']=='Yes',"Attribute not set correctly")
		e.SetAttribute('ctest','Yes')
		self.failUnless(e.cTest==True,"Attribute relfection with decode/encode")
		attrs=e.GetAttributes()
		self.failUnless(attrs['ctest']=='Yes',"Attribute not set correctly")
		self.failIf(attrs.has_key('dtest'),"Optional ordered list attribute") 
		self.failUnless(attrs['dtestR']=='',"Required ordered list attribute") 
		e.SetAttribute('dtest','Yes No')
		self.failUnless(e.dTest==[True,False],"Attribute relfection with list")
		attrs=e.GetAttributes()
		self.failUnless(attrs['dtest']=='Yes No',"Attribute not set correctly")
		self.failIf(attrs.has_key('etest'),"Optional unordered list attribute") 
		self.failUnless(attrs['etestR']=='',"Required unordered list attribute") 
		e.SetAttribute('etest','Yes No')
		self.failUnless(e.eTest=={True:'Yes',False:'No'},"Attribute relfection with list")
		attrs=e.GetAttributes()
		self.failUnless(attrs['etest']=='No Yes',"Attribute not set correctly")
	
	def testChildElements(self):
		"""Test child element behaviour"""
		e=XMLElement(None,'test')
		child1=e.ChildElement(XMLElement,'test1')
		children=e.GetChildren()
		self.failUnless(len(children)==1,"ChildElement failed to add child element")
	
	def testChildElementReflection(self):
		"""Test child element cases using reflection"""
		e=ReflectiveElement(None)
		child1=e.ChildElement(ReflectiveElement,'test1')
		self.failUnless(e.child is child1,"Element not set by reflection")
		children=e.GetChildren()
		self.failUnless(len(children)==1 and children[0] is child1,"ChildElement failed to add child element")
		# Now create a second child, should return the same one due to model restriction
		child2=e.ChildElement(ReflectiveElement,'test1')
		self.failUnless(e.child is child1 and child2 is child1,"Element model violated")
		child3=e.ChildElement(GenericElementA,'test3')
		self.failUnless(e.generics[0] is child3,"Generic element")
		child4=e.ChildElement(GenericSubclassA,'test4')
		self.failUnless(e.generics[1] is child4,"Generic sub-class element via method")
		child5=e.ChildElement(GenericSubclassB,'test5')
		self.failUnless(e.GenericElementB is child5,"Generic sub-class element via member")
		
	def testData(self):
		e=XMLElement(None)
		self.failUnless(e.IsMixed(),"Mixed default")
		e.AddData('Hello')
		self.failUnless(e.GetValue()=='Hello',"Data value")
		children=e.GetChildren()
		self.failUnless(len(children)==1,"Data child not set")
		self.failUnless(children[0]=="Hello","Data child not set correctly")
	
	def testEmpty(self):
		e=EmptyElement(None)
		self.failIf(e.IsMixed(),"EmptyElement is mixed")
		self.failUnless(e.IsEmpty(),"EmptyElement not empty")
		try:
			e.AddData('Hello')
			self.fail("Data in EmptyElement")
		except XMLValidityError:
			pass
		try:
			child=e.ChildElement(XMLElement)
			self.fail("Elements allowed in EmptyElement")
		except XMLValidityError:
			pass		

	def testElementContent(self):	
		e=ElementContent(None)
		self.failIf(e.IsMixed(),"ElementContent appears mixed")
		self.failIf(e.IsEmpty(),"ElementContent appears empty")
		try:
			e.AddData('Hello')
			self.fail("Data in ElementContent")
		except XMLValidityError:
			pass
		# white space should silently be ignored.
		e.AddData('  \n\r  \t')
		children=e.GetChildren()
		self.failUnless(len(children)==0,"Unexpected children")
		# elements can be added
		child=e.ChildElement(XMLElement)
		children=e.GetChildren()
		self.failUnless(len(children)==1,"Expected one child")
	
	def testMixedContent(self):
		e=MixedElement(None)
		self.failUnless(e.IsMixed(),"MixedElement not mixed")
		self.failIf(e.IsEmpty(),"MixedElement appears empty")
		e.AddData('Hello')
		self.failUnless(e.GetValue()=='Hello','Mixed content with a single value')
		child=e.ChildElement(XMLElement)
		try:
			e.GetValue()
		except XMLMixedContentError:
			pass
		
	def testCopy(self):
		e1=XMLElement(None)
		e2=e1.Copy()
		self.failUnless(isinstance(e2,XMLElement),"Copy didn't make XMLElement")
		self.failUnless(e1==e2 and e1 is not e2)
		

class XMLDocumentTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.d=mkdtemp('.d','pyslet-test_xml20081126-')
		os.chdir(self.d)
		
	def tearDown(self):
		os.chdir(self.cwd)
		shutil.rmtree(self.d,True)

	def testCaseConstructor(self):
		d=XMLDocument()
		self.failUnless(d.root is None,'root on construction')
		self.failUnless(d.GetBase() is None,'base set on construction')
		d=XMLDocument(root=XMLElement)
		self.failUnless(isinstance(d.root,XMLElement),'root not created on construction')
		self.failUnless(d.root.GetDocument() is d,'root not linked to document')
	
	def testCaseBase(self):
		"""Test the use of a file path on construction"""
		fpath=os.path.abspath('fpath.xml')
		furl=str(URIFactory.URLFromPathname(fpath))
		d=XMLDocument(baseURI=furl)
		self.failUnless(d.GetBase()==furl,"Base not set in constructor")
		self.failUnless(d.root is None,'root on construction')
		d=XMLDocument(baseURI='fpath.xml',root=XMLElement)
		self.failUnless(d.GetBase()==furl,"Base not made absolute from relative URL:\n\t%s\n\t%s"%(furl,d.GetBase()))
		self.failUnless(isinstance(d.root,XMLElement),'root not created on construction')
		d=XMLDocument()
		d.SetBase(furl)
		self.failUnless(d.GetBase()==furl,"Base not set by SetBase")

	def testCaseReadFile(self):
		"""Test the reading of the XMLDocument from the file system"""
		os.chdir(TEST_DATA_DIR)
		d=XMLDocument(baseURI='readFile.xml')
		d.Read()
		root=d.root
		self.failUnless(isinstance(root,XMLElement))
		self.failUnless(root.xmlname=='tag' and root.GetValue()=='Hello World')
		
	def testCaseReadString(self):
		"""Test the reading of the XMLDocument from a supplied stream"""
		os.chdir(TEST_DATA_DIR)
		d=XMLDocument(baseURI='readFile.xml')
		f=open('readFile.xml')
		d.Read(src=f)
		f.close()
		root=d.root
		self.failUnless(isinstance(root,XMLElement))
		self.failUnless(root.xmlname=='tag' and root.GetValue()=='Hello World')
	
	def testCaseString(self):
		os.chdir(TEST_DATA_DIR)
		d=XMLDocument(baseURI='readFile.xml')
		d.Read()
		f=open('readFile.xml')
		fData=f.read()
		f.close()
		self.failUnless(str(d)==fData,"XML output: %s"%str(d))
		d=XMLDocument(baseURI='ascii.xml')
		d.Read()
		f=open('ascii.xml')
		fData=f.read()
		f.close()
		self.failUnless(str(d)==fData,"XML output: %s"%str(d))
		
	def testCaseResolveBase(self):
		"""Test the use of ResolveURI and ResolveBase"""
		os.chdir(TEST_DATA_DIR)
		parent=XMLElement(None)
		self.failUnless(parent.ResolveBase() is None,"No default base")
		child=XMLElement(parent)
		self.failUnless(child.ResolveBase() is None,"No xml:base by default")
		parent.SetBase('file:///index.xml')
		self.failUnless(child.ResolveBase()=='file:///index.xml',"No xml:base inheritance")
		# Tests with a document follow....
		furl=str(URIFactory.URLFromPathname(os.path.abspath('base.xml')))
		href=URIFactory.URLFromPathname(os.path.abspath('link.xml'))
		hrefPath=href.absPath
		href=str(href)
		altRef='file:///hello/link.xml'
		d=XMLDocument(baseURI='base.xml')
		self.failUnless(d.GetBase()==furl,"Base not resolved relative to w.d. by constructor")
		d.Read()
		tag=d.root
		self.failUnless(tag.ResolveBase()==furl,"Root element resolves from document")
		self.failUnless(str(tag.ResolveURI("link.xml"))==href,"Root element HREF")
		self.failUnless(str(tag.RelativeURI(href))=='link.xml',"Root element relative")
		#self.failUnless(tag.RelativeURI(altRef)=='/hello/link.xml','Root element full path relative: %s'%tag.RelativeURI(altRef))
		childTag=tag._children[0]
		self.failUnless(childTag.ResolveBase()=="file:///hello/base.xml","xml:base overrides in childTag (%s)"%childTag.ResolveBase())
		self.failUnless(str(childTag.ResolveURI("link.xml"))==altRef,"child element HREF")
		self.failUnless(str(childTag.RelativeURI(href))=='..'+hrefPath,"child element relative resulting in full path: %s"%childTag.RelativeURI(href))
		self.failUnless(str(childTag.RelativeURI(altRef))=='link.xml','child element relative')
		# We require this next test to ensure that an href to the current document comes up blank
		# Although this was a major source of bugs in browsers (<img src=''> causing infinite loading loops)
		# these are largely fixed now and obfuscating by using a non-empty relative link to ourselves is
		# likely to start the whole thing going again.
		self.failUnless(str(childTag.RelativeURI(childTag.ResolveBase()))=='','child element relative avoiding empty URI(%s)'%childTag.RelativeURI(childTag.ResolveBase()))
		grandChildTag=childTag._children[0]
		self.failUnless(grandChildTag.ResolveBase()=="file:///hello/base.xml","xml:base inherited")
		self.failUnless(str(grandChildTag.ResolveURI("link.xml"))==altRef,"grandChild element HREF inherited")
		self.failUnless(str(grandChildTag.RelativeURI(href))=='..'+hrefPath,"grandChild element relative inherited: %s"%grandChildTag.RelativeURI(href))
		self.failUnless(str(grandChildTag.RelativeURI(altRef))=='link.xml','grandChild element relative inherited')
	
	def testCaseResolveLang(self):
		"""Test the use of ResolveLang"""
		parent=XMLElement(None)
		self.failUnless(parent.ResolveLang() is None,"No default language")
		parent.SetLang('en-GB')
		self.failUnless(parent.GetLang()=='en-GB',"Lang Get/Set")
		child=XMLElement(parent)
		self.failUnless(child.GetLang() is None,"No xml:lang by default")
		self.failUnless(child.ResolveLang()=='en-GB',"Lang inheritence")
		# repeat tests with a parent document
		d=XMLDocument()
		parent=XMLElement(d)
		self.failUnless(parent.ResolveLang() is None,"No default language")
		
	def testCaseCreate(self):
		"""Test the creating of the XMLDocument on the file system"""		
		CREATE_1_XML="""<?xml version="1.0" encoding="UTF-8"?>
<test/>"""
		d=XMLDocument(root=NamedElement)
		d.SetBase('create1.xml')
		d.Create()
		try:
			f=open("create1.xml")
			data=f.read()
			f.close()
			self.failUnless(data==CREATE_1_XML,"Create Test")
		except IOError:
			self.fail("Create Test failed to create file")
	
	def testCaseUpdate(self):
		"""Test the updating of the MXLDocument on the file system"""
		UPDATE_1_XML="""<?xml version="1.0" encoding="UTF-8"?>
<test>
	<test/>
</test>"""
		d=XMLDocument(root=NamedElement)
		d.SetBase('update1.xml')
		try:
			d.Update()
			self.fail("Update XMLDocument failed to spot missing file")
		except XMLMissingFileError:
			pass
		d.Create()
		d.root.ChildElement(NamedElement)
		d.Update()
		try:
			f=open("update1.xml")
			data=f.read()
			f.close()
			self.failUnless(data==UPDATE_1_XML,"Update Test")
		except IOError:
			self.fail("Update Test failed to update file")			
		
	def testCaseID(self):
		"""Test the built-in handling of a document's ID space."""
		doc=XMLDocument()
		e1=XMLElement(doc)
		e2=XMLElement(doc)
		e1.id=e2.id='test'
		doc.RegisterElement(e1)
		try:
			doc.RegisterElement(e2)
			self.fail("Failed to spot ID clash")
		except XMLIDClashError:
			pass
		e2.id='test2'
		doc.RegisterElement(e2)
		self.failUnless(doc.GetElementByID('test') is e1,"Element look-up failed")
		newID=doc.GetUniqueID('test')
		self.failIf(newID=='test' or newID=='test2')
	
	def testCaseReflection(self):
		"""Test the built-in handling of reflective attributes and elements."""
		REFLECTIVE_XML="""<?xml version="1.0" encoding="UTF-8"?>
<reflection atest="Hello"><etest>Hello Again</etest></reflection>"""
		f=StringIO(REFLECTIVE_XML)
		d=ReflectiveDocument()
		d.Read(src=f)
		root=d.root
		self.failUnless(isinstance(root,ReflectiveElement))
		self.failUnless(root.atest,"Attribute relfection")
		self.failUnless(root.child,"Element relfection")
		
		
if __name__ == "__main__":
	unittest.main()
