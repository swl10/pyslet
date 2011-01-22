import unittest

from xml import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(RangeTestTests,'test'),
		unittest.makeSuite(ParserTests,'test')
		))

class RangeTestTests(unittest.TestCase):
	def testRangeCheck(self):
		"""Check a group of ranges"""
		CHAR_CLASS_TESTS=[
			[[],[]],
			[[[0,10]],[0,1,2,3,4,5,6,7,8,9,10]],
			[[[0,3],[5,10]],[0,1,2,3,5,6,7,8,9,10]],
			[[[1,1]],[1]],
			[[[0,1],[2,3],[4,5],[6,7],[8,9],[10,10]],[0,1,2,3,4,5,6,7,8,9,10]],
			[[[0,1],[3,5],[7,7]],[0,1,3,4,5,7]]
			]
		for test in CHAR_CLASS_TESTS:
			result=[]
			for i in range(11):
				if CharInClass(chr(i),test[0]):
					result.append(i)
			self.failUnless(result==test[1],repr(test[0])+" matched "+repr(result))

	def testCharClasses(self):
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
		
	def testEscapeAttributes(self):
		"""Check the EscapeAttributeValue"""
		self.failUnless(EscapeAttributeValue('<&"\'Done')==
			"&lt;&amp;&quot;&apos;Done","escapes")
		self.failUnless(EscapeAttributeValue(' !#$%()*+,-./0123456789:;=>?@AZ[\\]^_`az{|}~')==
			' !#$%()*+,-./0123456789:;=>?@AZ[\\]^_`az{|}~',"safe chars")
		self.failUnless(EscapeAttributeValue(u'Caf\xE9\x7F')=="Caf&#xE9;&#x7F;","ascii")
		self.failUnless(EscapeAttributeValue(u'Caf\xE9\x7F',1)==u"Caf\xE9&#x7F;","unicode")
		try:
			EscapeAttributeValue('\005')
			self.fail("non-char success")
		except ValueError:
			pass
		for code in range(0x80,0x9F):
			# We make an elective decision to escape these controls even in unicode
			self.failUnless(EscapeAttributeValue(unichr(code),1)==("&#x%X;"%code),"high-control")
	
	def testEscapeCharData(self):
		"""Check the EscapeCharData function"""
		self.failUnless(EscapeCharData('<&>Done')=="&lt;&amp;&gt;Done","escapes")
		self.failUnless(EscapeCharData(' !\"#$%\'()*+,-./0123456789:;=?@AZ[\\]^_`az{|}~')==
			' !\"#$%\'()*+,-./0123456789:;=?@AZ[\\]^_`az{|}~',"safe chars")
		self.failUnless(EscapeCharData(u'Caf\xE9\x7F')=="Caf&#xE9;&#x7F;","ascii")
		self.failUnless(EscapeCharData(u'Caf\xE9\x7F',1)==u"Caf\xE9&#x7F;","unicode")
		try:
			EscapeCharData('\005')
			self.fail("non-char success")
		except ValueError:
			pass
		for code in range(0x80,0x9F):
			# We make an elective decision to escape these controls even in unicode
			self.failUnless(EscapeCharData(unichr(code),1)==("&#x%X;"%code),"high-control")
		
	def testStartTag(self):
		"""Check StartTag"""
		self.failUnless(str(StartTag("ns","tagname"))=="<ns:tagname>","no attributes")
		self.failUnless(str(StartTag('',"tagname",{"name":"Steve","location":u"caf\xe9"}))==
			'<tagname location="caf&#xE9;" name="Steve">',"attributes")
		self.failUnless(unicode(StartTag('',"tagname",{"name":"Steve","location":u"caf\xe9"}))==
			u'<tagname location="caf\xe9" name="Steve">',"attributes with unicode")
		tag=StartTag("ns","tagname")
		tag.SetAttribute('',"name","Steve")
		tag.SetAttribute('',"location",u"caf\xe9")
		tag.SetAttribute('xml','lang',"en-GB")
		self.failUnless(str(tag)=='<ns:tagname location="caf&#xE9;" name="Steve" xml:lang="en-GB">',"SetAttribute")
	
	def testEmptyTag(self):
		"""Check EmptyTag"""
		self.failUnless(str(EmptyTag("ns","tagname"))=="<ns:tagname/>","no attributes")
		self.failUnless(str(EmptyTag('',"tagname",{"name":"Steve","location":u"caf\xe9"}))==
			'<tagname location="caf&#xE9;" name="Steve"/>',"attributes")
		self.failUnless(unicode(EmptyTag('',"tagname",{"name":"Steve","location":u"caf\xe9"}))==
			u'<tagname location="caf\xe9" name="Steve"/>',"attributes with unicode")
	
	def testEndTag(self):
		"""Check EndTag"""
		self.failUnless(str(EndTag("ns","tagname"))=="</ns:tagname>","prefix")
		self.failUnless(str(EndTag("","tagname"))=="</tagname>","no prefix")

	def testComment(self):
		"""Check Comment"""
		# Note that we do not require any padding around comments
		self.failUnless(str(Comment("Hello"))=="<!--Hello-->","simple case")
		self.failUnless(str(Comment("Hello-Mum"))=="<!--Hello-Mum-->","single hyphen")
		self.failUnless(str(Comment("-Hello-Mum-"))=="<!-- -Hello-Mum- -->","leading and trailing hyphen")
		self.failUnless(str(Comment("Hello--Mum"))=="<!--Hello-Mum-->","double hyphen")
		self.failUnless(str(Comment("Hello----Mum"))=="<!--Hello-Mum-->","multiple hyphen")
		self.failUnless(unicode(Comment(u'Caf\xE9\x7F'))==u"<!--Caf\xE9\x7F-->","unicode comment")
		try:
			str(Comment('\x00'))
			self.fail("non-char in comment")
		except ValueError:
			pass
		try:
			str(Comment(u'Caf\xE9\x7F'))
			self.fail("no unicode escaping in comments")
		except ValueError:
			pass

class ParserTests(unittest.TestCase):
	def testNameChar(self):
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
			elif not c in ".-_:":
				self.failIf(IsNameChar(c))
				continue
			self.failUnless(IsNameChar(c))
			if code>255 and gotLetter and gotDigit and gotCombiningChar and gotExtender:
				# we don't check every character (boring)
				break

	def testName(self):
		self.failIf(CheckName(".hi"),"leading .")
		self.failIf(CheckName("-hi"),"leading hyphen")
		self.failIf(CheckName("1hi"),"leading digit")
		self.failIf(CheckName("m!element"),"pling")
		self.failUnless(CheckName("a0-_.:"),"various")
		self.failUnless(CheckName("_a"),"leading underscore")
		self.failUnless(CheckName(":a"),"leading colon")
	
			 
if __name__ == "__main__":
	unittest.main()