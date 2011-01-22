import unittest
from types import *

from rfc2425 import *
from rfc3066 import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(DirectoryTests),
		unittest.makeSuite(ParserTests)
		))
		
class DirectoryTests(unittest.TestCase):
	def testConstructor(self):
		d=RFC2425Directory()

CONTENT_LINE_TESTS=(
	("name:value\r\n",(None,'name',[],'value')),
	('group.name;p=pval;q="x;:y":value\r\n',
		("group","name",[('p',['pval']),('q',['x;:y'])],"value")),
	("name:value",None),
	("name;:value\r\n",None),
	("name;p:value\r\n",None),
	("name;p=pval",None)
	)

ENCODING_TESTS=(
	("n;encoding=b:\r\n","b"),
	("n;encoding=!:\r\n",RFC2425Error),
	("n;Encoding=q:\r\n","q"),
	("n;p=1;q=1;encoding=:\r\n",RFC2425Error),
	("n;encoding=x-enigma:\r\n","x-enigma")
	)

VALUETYPE_TESTS=(
	("n;valuetype=uri:\r\n","uri"),
	("n;valuetype=!:\r\n",RFC2425Error),
	("n;Valuetype=text:\r\n","text"),
	("n;p=1;q=1;valuetype=:\r\n",RFC2425Error),
	("n;valuetype=x-type:\r\n","x-type")
	)

LANGUAGE_TESTS=(
	("n;language=en:\r\n","en"),
	("n;Language=!:\r\n",RFCSyntaxError),
	("n;Language=en-GB:\r\n","en-GB"),
	("n;p=1;q=1;language=:\r\n",RFC2425Error),
	("n;language=x-i:\r\n",RFC3066Error)
	)

CONTEXT_TESTS=(
	("n;context=LDAP:\r\n","LDAP"),
	("n;context=!:\r\n",RFC2425Error),
	("n;Context=SQL:\r\n","SQL"),
	("n;p=1;q=1;context=:\r\n",RFC2425Error),
	("n;context=x-context:\r\n","x-context")
	)

NAME_TESTS=(
	("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
		"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"),
	("0.","0"),
	("-.","-"),
	(":a",None),
	(" A",None))

XNAME_TESTS=(
	("x-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
		"x-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"),
	("a",None),
	("0",None),
	("-",None),
	("x-",None),
	("x-0:","x-0"))

PARAM_TESTS=(
	("p = Hello",None),
	("p=Hello",("p",["Hello"])),
	('p="x,y"',("p",["x,y"])),
	('p=x,y',("p",['x','y'])),
	('p=x,,y',("p",['x','','y'])),
	('p=x,"a\x7F',("p",['x'])),
	('p=\x7F',("p",[''])),
	('p\x7F',None))
	
PARAM_VALUE_TESTS=(
	("'Hello'","'Hello'"),
	('Hello,"Hello"','Hello'))

QUOTED_STRING_TESTS=(
	('"Hello"','Hello'),
	('"Hell\x7F"',None),
	('"Hello,\'Hello\'"',"Hello,'Hello'")
	)
	
PTEXT_TESTS=(
	(" \t!#$%&'()*+-./0123456789<=>?@az[\\]^_`AZ",
		" \t!#$%&'()*+-./0123456789<=>?@az[\\]^_`AZ"),
	("comma,","comma"),
	('quote"','quote'),
	("quote'","quote'"),
	("semicolon;","semicolon"),
	("colon:","colon"),
	(u"caf\xE9",u"caf\xE9"),
	("\x7F",""))

VALUE_TESTS=(
	(" \twsp"," \twsp"),
	("hello\x00","hello"),
	(u"caf\xE9",u"caf\xE9"),
	("\x7F",""))
	

class ParserTests(unittest.TestCase):
	def setUp(self):
		self.p=RFC2425Parser()
	
	def tearDown(self):
		pass

	def testUnfolding(self):
		"""Test RFC2425Parser line unfolding"""
		self.p.ResetParser("Hello"+CRLF+"Tab, "+CRLF+HTAB+"Space, "+CRLF+SP+"Goodbye")
		unfolded=""
		while self.p.theChar is not None:
			unfolded=unfolded+self.p.theChar
			self.p.NextChar()
		self.failUnless(unfolded=="Hello"+CRLF+"Tab, Space, Goodbye")
	
	def RunParseTests(self,method,testStrings):
		for t in testStrings:
			if t[1] is None:
				try:
					self.p.ResetParser(t[0])
					method()
					self.fail("No error for: "+t[0])
				except RFCSyntaxError:
					pass
			else:
				self.p.ResetParser(t[0])
				result=method()
				self.failUnless(result==t[1],t[0]+" returned "+unicode(result))
	
	def RunParamTests(self,method,testStrings):
		for t in testStrings:
			self.p.ResetParser(t[0])
			group,name,plist,value=self.p.ParseContentLine()
			if type(t[1]) is ClassType and issubclass(t[1],Exception):
				try:
					method(plist)
					self.fail("No error for: "+t[0])
				except t[1]:
					pass
			else:
				result=method(plist)
				self.failUnless(result==t[1],t[0]+" returned "+unicode(result))
			# a second attempt to remove the parameter finds nothing
			# even if there has been an exception
			self.failUnless(method(plist) is None,"param removal test: "+t[0])

	def testContentLine(self):
		"""Test RFC2425Parser.ParseContentLine"""
		self.RunParseTests(self.p.ParseContentLine,CONTENT_LINE_TESTS)

	def testGetEncoding(self):
		"""Test RFC2425Parser.GetEncodingParam"""
		self.RunParamTests(self.p.GetEncodingParam,ENCODING_TESTS)
		
	def testGetValuetype(self):
		"""Test RFC2425Parser.GetValuetypeParam"""
		self.RunParamTests(self.p.GetValuetypeParam,VALUETYPE_TESTS)
		
	def testGetLanguage(self):
		"""Test RFC2425Parser.GetLanguageParam"""
		self.RunParamTests(self.p.GetLanguageParam,LANGUAGE_TESTS)
		
	def testGetContext(self):
		"""Test RFC2425Parser.GetContextParam"""
		self.RunParamTests(self.p.GetContextParam,CONTEXT_TESTS)
		
	def testGroup(self):
		"""Test RFC2425Parser.ParseGroup"""
		self.RunParseTests(self.p.ParseGroup,NAME_TESTS)
			
	def testName(self):
		"""Test RFC2425Parser.ParseName"""
		self.RunParseTests(self.p.ParseName,NAME_TESTS)

	def testXName(self):
		"""Test RFC2425Parser.ParseXName"""
		self.RunParseTests(self.p.ParseXName,XNAME_TESTS)

	def testParam(self):
		"""Test RFC2425Parser.ParseParam"""
		self.RunParseTests(self.p.ParseParam,PARAM_TESTS)

	def testParamName(self):
		"""Test RFC2425Parser.ParseParamName"""
		self.RunParseTests(self.p.ParseParamName,NAME_TESTS)

	def testParamValue(self):
		"""Test RFC2245Parser.ParseParamValue"""
		self.RunParseTests(self.p.ParseParamValue,PARAM_VALUE_TESTS)
		
	def testQuotedString(self):
		"""Test RFC2245Parser.ParseQuotedString"""
		self.RunParseTests(self.p.ParseQuotedString,QUOTED_STRING_TESTS)
		
	def testPText(self):
		"""Test RFC2245Parser.ParsePText"""
		self.RunParseTests(self.p.ParsePText,PTEXT_TESTS)
		
	def testValue(self):
		"""Test RFC2425Parser.ParseValue"""
		self.RunParseTests(self.p.ParseValue,VALUE_TESTS)
		
if __name__ == "__main__":
	unittest.main()