import unittest

from xml import *
from StringIO import StringIO

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(MainTests,'test'),
		unittest.makeSuite(ParserTests,'test')
		))

class MainTests(unittest.TestCase):
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
	
	def testXMLFile(self):
		"""Check XMLFile"""
		f=StringIO()
		xf=XMLFile(f)
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>','default constructor')
		xf.AppendStartTag(Element('',"x"),1)
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x>',"add start tag: %s"%f.getvalue())
		xf.AppendEmptyTag(EmptyTag('',"void"))
		xf.AppendStartTag(Element('',"y"),1)
		xf.AppendStartTag(Element('',"z"),0)
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x>\n\t<void/>\n\t<y>\n\t\t<z>',"add indented start tags: %s"%f.getvalue())
		xf.AppendData(u"xml caf\xe9")
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x>\n\t<void/>\n\t<y>\n\t\t<z>xml caf&#xE9;',"add data: %s"%f.getvalue())
		xf.AppendEndTag()
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x>\n\t<void/>\n\t<y>\n\t\t<z>xml caf&#xE9;</z>\n\t</y>',"end indented tag: %s"%f.getvalue())
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x>\n\t<void/>\n\t<y>\n\t\t<z>xml caf&#xE9;</z>\n\t</y>\n</x>',"end all tags: %s"%f.getvalue())
	
	def testXMLFileUTF(self):
		"""Check XMLFile in Unicode mode"""
		f=StringIO()
		xf=XMLFile(f,1)
		xf.AppendStartTag(Element('',"x"),0)
		xf.AppendData(u"xml caf\xe9")
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x>xml caf\xc3\xa9</x>',"UTF-8 output: %s"%f.getvalue())
	
	def testXMLFileNS(self):
		"""Check XMLFile namespace handling"""
		f=StringIO()
		xf=XMLFile(f)
		xf.AppendStartTag(Element('http://www.w3.org/XML/1998/namespace','x',[Attribute('http://www.w3.org/XML/1998/namespace','lang','en')]))
		xf.AppendData("Hello")
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<xml:x xml:lang="en">Hello</xml:x>',"Built-in XML namespace:\n%s"%f.getvalue())
		f=StringIO()
		xf=XMLFile(f)
		xf.AppendStartTag(Element('http://www.example.com/','x'))
		xf.AppendStartTag(Element('http://www.example.com/','y'))
		xf.AppendData("Hello")
		xf.AppendEndTag()
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x xmlns="http://www.example.com/"><y>Hello</y></x>',"Setting default namespace:\n%s"%f.getvalue())
		f=StringIO()
		xf=XMLFile(f)
		xf.AppendStartTag(Element('http://www.example.com/A','x'))
		xf.AppendStartTag(Element('http://www.example.com/B','y'))
		xf.AppendData("Hello")
		xf.AppendEndTag()
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x xmlns="http://www.example.com/A"><y xmlns="http://www.example.com/B">Hello</y></x>',"Overriding default namespace:\n%s"%f.getvalue())
		f=StringIO()
		xf=XMLFile(f)
		xf.AppendStartTag(Element('http://www.example.com/A','x',[Attribute('','xmlns:B','http://www.example.com/B')]))
		xf.AppendStartTag(Element('http://www.example.com/B','y',[Attribute('http://www.example.com/A','z','bye')]))
		xf.AppendData("Hello")
		xf.AppendEndTag()
		xf.AppendEndTag()
		self.failUnless(f.getvalue()=='<?xml version="1.0" encoding="UTF-8"?>\n<x xmlns="http://www.example.com/A" xmlns:B="http://www.example.com/B"><B:y z="bye">Hello</B:y></x>',"Defining a namespace prefix")
						
	def testStartTag(self):
		"""Check StartTag"""
		self.failUnless(Element("http://www.example.com/","tagname").StartTag()=="<tagname>","no attributes, no prefix")
		self.failUnless(Element('',"x:tagname").StartTag()=="<x:tagname>","no attributes with prefix")
		self.failUnless(Element('',"tagname",[Attribute('',"name","Steve"),Attribute('',"location",u"caf\xe9")]).StartTag()==
			'<tagname name="Steve" location="caf&#xE9;">',"attributes")
		self.failUnless(Element('',"tagname",[Attribute('',"name","Steve"),Attribute('',"location",u"caf\xe9")]).UnicodeStartTag()==
			u'<tagname name="Steve" location="caf\xe9">',"attributes with unicode")
		e=Element("http://www.example.com/","tagname")
		e.SetAttribute('',"name","Steve")
		e.SetAttribute('',"location",u"caf\xe9")
		e.SetAttribute('','xml:lang',"en-GB")
		self.failUnless(e.StartTag()=='<tagname name="Steve" location="caf&#xE9;" xml:lang="en-GB">',"SetAttribute: %s"%e.StartTag())
	
	def testEmptyTag(self):
		"""Check EmptyTag"""
		self.failUnless(Element('',"tagname").EmptyTag()=="<tagname/>","no attributes, no prefix")
		self.failUnless(Element('',"x:tagname").EmptyTag()=="<x:tagname/>","no attributes with prefix")
		self.failUnless(Element('',"tagname",[Attribute('',"name","Steve"),Attribute('',"location",u"caf\xe9")]).EmptyTag()==
			'<tagname name="Steve" location="caf&#xE9;"/>',"attributes")
		self.failUnless(Element('',"tagname",[Attribute('',"name","Steve"),Attribute('',"location",u"caf\xe9")]).UnicodeEmptyTag()==
			u'<tagname name="Steve" location="caf\xe9"/>',"attributes with unicode")
	
	def testEndTag(self):
		"""Check EndTag"""
		self.failUnless(Element('',"x:tagname").EndTag()=="</x:tagname>","prefix")
		self.failUnless(Element('',"tagname").EndTag()=="</tagname>","no prefix")

	def testAttribute(self):
		"""Check Attribute"""
		self.failUnless(str(Attribute('','name','Steve'))=='name="Steve"',"simple attribute test")
		self.failUnless(str(Attribute('','location',u"caf\xe9"))=='location="caf&#xE9;"',"unicode attribute test")
		
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