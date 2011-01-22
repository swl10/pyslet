import unittest
import pdb
from types import *
from string import join

from rfc2396 import *
from rfc2234 import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CharacterTests,'test'),
		unittest.makeSuite(URICStringTests,'test'),
		unittest.makeSuite(URIReferenceTests,'test'),
		unittest.makeSuite(ParserTests,'test')
		))

class CharacterTests(unittest.TestCase):
	def ASCIITest(self,method):
		result=[]
		for i in range(256):
			if method(chr(i)):
				result.append(chr(i))
		return join(result,'')
				
	def testAlpha(self):
		"""Test IsAlpha"""
		self.failUnless(self.ASCIITest(IsAlpha)=="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
	
	def testIsLowalpha(self):
		"""Test IsLowalpha"""
		self.failUnless(self.ASCIITest(IsLowalpha)=="abcdefghijklmnopqrstuvwxyz")
	
	def testIsUpalpha(self):
		"""Test IsUpalpha"""
		self.failUnless(self.ASCIITest(IsUpalpha)=="ABCDEFGHIJKLMNOPQRSTUVWXYZ")

	def testIsDigit(self):
		"""Test IsDigit"""
		self.failUnless(self.ASCIITest(IsDigit)=="0123456789")

	def testIsAlphanum(self):
		"""Test IsAlphanum"""
		self.failUnless(self.ASCIITest(IsAlphanum)=="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
	
	def testIsReserved(self):
		"""Test IsReserved"""
		self.failUnless(self.ASCIITest(IsReserved)=="$&+,/:;=?@")
	
	def testIsMark(self):
		"""Test IsMark"""
		self.failUnless(self.ASCIITest(IsMark)=="!'()*-._~")

	def testIsUnreserved(self):
		"""Test IsUnreserved"""
		self.failUnless(self.ASCIITest(IsUnreserved)=="!'()*-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz~")
		
	                    				
class URICStringTests(unittest.TestCase):
	"""
	The RFC says:
	"If the given URI scheme defines a canonicalization algorithm, then
	unreserved characters may be unescaped according to that algorithm."
	By implication we can't canonicalize escapes in case the resulting
	string loses its meaning. 
	"""
	def testConstructor(self):
		"""Test URICString constructor and repr"""
		# pdb.set_trace()
		self.failUnless(repr(URICString("mum"))=="URICString('mum')","simple string")
		self.failUnless(repr(URICString("Montr%e9al",URICString.encoded))=="URICString('Montr%E9al')","simple escape")
		self.failUnless(repr(URICString("Montr%e9%61l"))=="URICString('Montr%E9%61l')","redundant escape")
		self.failUnless(repr(URICString("Montr\xe9al",URICString.raw))=="URICString('Montr%E9al')","raw string")
		self.failUnless(repr(URICString("Montr%e9al",URICString.raw))=="URICString('Montr%25e9al')","raw escape")
		try:
			URICString("Montr\xe9al")
			self.fail("bad character")
		except RFCSyntaxError:
			pass
		self.failUnless(repr(URICString(URICString("mum")))=="URICString('mum')","copy constructor")
		
	def testStr(self):
		"""Check str method"""
		self.failUnless(str(URICString("mum"))=='mum')
	
	def testRaw(self):
		"""Check raw method"""
		self.failUnless(URICString("Montr%E9%61l").value=="Montr\xe9al")

		
class URIReferenceTests(unittest.TestCase):
	def testConstructor(self):
		"""Test URIReference constructor and repr"""
		self.failUnless(repr(URIReference("http://127.0.0.1/#frag"))==
			"URIReference('http://127.0.0.1/#frag')","full string")
		self.failUnless(repr(URIReference(AbsoluteURI("http://127.0.0.1/"),"frag"))==
			"URIReference('http://127.0.0.1/#frag')","absolute separate fragment")
		self.failUnless(repr(URIReference(RelativeURI("index.html"),"frag"))==
			"URIReference('index.html#frag')","relative separate fragment")
		self.failUnless(repr(URIReference(URIReference("index.html")))==
			"URIReference('index.html')","copy constructor")
	
	def testStr(self):
		"""Check str method"""
		self.failUnless(str(URIReference("http://127.0.0.1/#frag"))=='http://127.0.0.1/#frag')


class ParserTests(unittest.TestCase):
	def setUp(self):
		self.p=RFC2396Parser(None)
	
	def tearDown(self):
		pass

	def RunParseTests(self,methodName,testStrings):
		method=getattr(self.p,methodName)
		for t in testStrings:
			if type(t[1]) is ClassType and issubclass(t[1],Exception):
				try:
					self.p.ResetParser(t[0])
					method()
					self.fail("No error from "+methodName+" for: "+repr(t[0]))
				except t[1]:
					pass
			else:
				self.p.ResetParser(t[0])
				result=method()
				self.failUnless(result==t[1],methodName+" returned "+repr(result)+" for "+repr(t[0]))
	
	def testURIC(self):
		"""Test ParseUricRepeat"""
		pass
					
	def testParseMethods(self):
		tests=(
			("ParseURIReference","http://a.b/c?d#e",
				URIReference(AbsoluteURI("http://a.b/c?d"),URIFragment('e'))),
			("ParseURIReference","//a.b/c?d#e",
				URIReference(RelativeURI("//a.b/c?d"),URIFragment('e'))),			
			("ParseURIReference","/c?d#e",
				URIReference(RelativeURI("/c?d"),URIFragment('e'))),			
			("ParseURIReference","c?d#e",
				URIReference(RelativeURI("c?d"),URIFragment('e'))),			
			("ParseURIReference","c?d#",
				URIReference(RelativeURI("c?d"),URIFragment(''))),
			("ParseURIReference","c?d",
				URIReference(RelativeURI("c?d"),None)),			
			("ParseAbsoluteURI","http://a.b?c",
				AbsoluteURI("http",URIHierPart(URINetPath(URIServer(URIHostname(['a','b']))),URIQuery('c')))),
			("ParseAbsoluteURI","mailto:steve",AbsoluteURI("mailto",URIOpaquePart('steve'))),
			("ParseRelativeURI","//a.b?c",
				RelativeURI(URINetPath(URIServer(URIHostname(['a','b']))),URIQuery('c'))),
			("ParseRelativeURI","/a.b?",
				RelativeURI(URIAbsPath([URISegment('a.b')]),URIQuery(''))),
			("ParseRelativeURI","a.b?c",
				RelativeURI(URIRelPath(URIRelSegment('a.b')),URIQuery('c'))),
			("ParseHierPart","//a.b?c",URIHierPart(URINetPath(URIServer(URIHostname(['a','b']))),URIQuery('c'))),
			("ParseHierPart","/a.b?c",URIHierPart(URIAbsPath([URISegment('a.b')]),URIQuery('c'))),  
			("ParseHierPart","/a.b?",URIHierPart(URIAbsPath([URISegment('a.b')]),URIQuery(''))),  
			("ParseHierPart","/a.b",URIHierPart(URIAbsPath([URISegment('a.b')]))),  
			("ParseOpaquePart","/a/b",RFCSyntaxError),
			("ParseOpaquePart","a/b/c",URIOpaquePart("a/b/c")),
			("ParseOpaquePart","%2Fa/b",URIOpaquePart("/a/b")),
			("ParseNetPath","//a.b",URINetPath(URIServer(URIHostname(['a','b'])))),
			("ParseNetPath","//1.2.3/",
				URINetPath(URIRegName("1.2.3"),URIAbsPath([URISegment('')]))),
			("ParseNetPath","/1.2",RFCSyntaxError),
			("ParseAbsPath","/a/b",URIAbsPath([URISegment('a'),URISegment('b')])),
			("ParseAbsPath","a/b",RFCSyntaxError),
			("ParseRelPath","/a/b",RFCSyntaxError),
			("ParseRelPath","a/b:",
				URIRelPath(URIRelSegment('a'),URIAbsPath([URISegment('b:')]))),
			("ParseRelPath","a:/b:",
				URIRelPath(URIRelSegment('a'))),
			("ParseRelSegment","azAZ09-_.!~*'();@&=+$,%2F/",
				URIRelSegment("azAZ09-_.!~*'();@&=+$,/")),
			("ParseRelSegment","/",RFCSyntaxError),
			("ParseScheme","http:","http"),
			("ParseScheme","x-http","x-http"),
			("ParseScheme","azAZ09.+-:","azAZ09.+-"),
			("ParseScheme","3:",RFCSyntaxError),
			("ParseScheme","-:",RFCSyntaxError),
			("ParseScheme",".:",RFCSyntaxError),
			("ParseAuthority","1.2.3/",URIRegName("1.2.3")),
			("ParseAuthority","a.b.c/",URIServer(URIHostname(['a','b','c']))),
			("ParseRegName","azAZ09-_.!~*'()$,;:@&=+/",URIRegName("azAZ09-_.!~*'()$,;:@&=+")),
			("ParseRegName","/",RFCSyntaxError),
			("ParseScheme",":",RFCSyntaxError),
			("ParseServer","a.b.c.:80@127.0.0.1:81",
				URIServer(URIIPv4Address([127,0,0,1]),81,"a.b.c.:80")),
			("ParseServer","127.0.0.1/@",URIServer(URIIPv4Address([127,0,0,1]))),
			("ParseUserInfo","azAZ09-_.!~*'();:&=+$,","azAZ09-_.!~*'();:&=+$,"),
			("ParseUserInfo","az?","az"),
			("ParseUserInfo","a.b.c.:80@","a.b.c.:80"),
			("ParseHostPort","127.0.0.1:8080",(URIIPv4Address([127,0,0,1]),8080)),
			("ParseHostPort","a.b.c.:8080",(URIHostname(['a','b','c','']),8080)),
			("ParseHostPort","a:",(URIHostname(['a']),None)),
			("ParseHost","a.b.c",URIHostname(['a','b','c'])),
			("ParseHost","127.0.0.1",URIIPv4Address([127,0,0,1])),
			("ParseHost","127.0.0.1.uk",URIHostname(['127','0','0','1','uk'])),
			("ParseHostname","a.b.c",URIHostname(['a','b','c'])),
			("ParseHostname","a.b.c.",URIHostname(['a','b','c',''])),
			("ParseHostname","1.2.3.",RFCSyntaxError),
			("ParseHostname","uk",URIHostname(["uk"])),
			("ParseHostname",".",RFCSyntaxError),
			("ParseDomainLabel","a","a"),
			("ParseDomainLabel","a-3","a-3"),
			("ParseDomainLabel","a-3-",RFCSyntaxError),
			("ParseDomainLabel","127","127"),
			("ParseTopLabel","a","a"),
			("ParseTopLabel","a-3","a-3"),
			("ParseTopLabel","a-3-",RFCSyntaxError),
			("ParseIPv4Address","127.0.0.1",URIIPv4Address([127,0,0,1])),
			("ParseIPv4Address","1000.0.0.0",URIIPv4Address([1000,0,0,0])),
			("ParseIPv4Address","127...",RFCSyntaxError),
			("ParsePort","/",None),
			("ParsePort","8080",8080),			
			("ParsePath","/a/b",URIAbsPath([URISegment('a'),URISegment('b')])),
			("ParsePath","a/b",URIOpaquePart("a/b")),
			("ParsePath","%2Fa/b",URIOpaquePart("/a/b")),
			("ParsePath","{a}",RFCSyntaxError),
			("ParsePathSegments","/",[URISegment('',[]),URISegment('',[])]),
			("ParsePathSegments","?",[URISegment('',[])]),
			("ParsePathSegments","a/b",[URISegment("a",[]),URISegment("b",[])]),
			("ParsePathSegments","a;b/c;d;/",[URISegment("a",['b']),
				URISegment("c",["d",""]),URISegment("",[])]),
			("ParseSegment","a/?",URISegment("a",[])),
			("ParseSegment","a?",URISegment("a",[])),
			("ParseSegment","az09AZ",URISegment("az09AZ",[])),
			("ParseSegment","-_.!~*'():@&=+$,",URISegment("-_.!~*'():@&=+$,",[])),
			("ParseSegment","a;/",URISegment("a",[""])),
			("ParseSegment","a;b;c/",URISegment("a",["b","c"])),
			("ParseSegment","a%61a",URISegment("aaa",[])),
			("ParseEscaped","%00",0),
			("ParseEscaped","%10",16),
			("ParseEscaped","%FF",255),
			("ParseEscaped","%0a",10),
			("ParseEscaped","%xa",RFCSyntaxError),
			("ParseEscaped","%a",RFCSyntaxError),
			("ParseEscaped","%111",17),
			("ParseEscaped","0",RFCSyntaxError)
			)
		# pdb.set_trace()	
		for t in tests:
			method=getattr(self.p,t[0])
			if type(t[2]) is ClassType and issubclass(t[2],Exception):
				try:
					self.p.ResetParser(t[1])
					method()
					self.fail("No error from "+t[0]+" for: "+t[1])
				except t[2]:
					pass
			else:
				self.p.ResetParser(t[1])
				result=method()
				self.failUnless(result==t[2],t[0]+" returned "+repr(result)+" for "+t[1])
			
		
if __name__ == "__main__":
	unittest.main()