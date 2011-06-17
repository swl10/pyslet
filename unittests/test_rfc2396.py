#! /usr/bin/env python

import unittest
import os, os.path, sys
from types import UnicodeType, StringType

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(RFC2396Tests,'test'),
		unittest.makeSuite(URITests,'test'),
		unittest.makeSuite(FileURLTests,'test'),
		))

from pyslet.rfc2396 import *

SERVER_EXAMPLES={
	# if there is no authority then it is safe to parse
	None:
		(None,None,None),
	# empty string is a speical case and is treated as empty host
	'':
		(None,'',None),
	'@host.com':
		('','host.com',None),
	'host.com':
		(None,'host.com',None),
	'foo:@host.com':
		('foo:','host.com',None),
	'myname@host.dom':
		('myname','host.dom',None),
	'user:pass@host.com:443':
		('user:pass','host.com','443')
	}
	

class RFC2396Tests(unittest.TestCase):
	def testCaseBasics(self):
		"""Tests for basic character classes.
		
		alpha = lowalpha | upalpha
		lowalpha = "a" | ... | "z"
		upalpha  = "A" | ... | "Z"
		digit = "0" | ... | "9"
		alphanum = alpha | digit
		reserved = ";" | "/" | "?" | ":" | "@" | "&" | "=" | "+" | "$" | ","
		unreserved  = alphanum | mark
		mark = "-" | "_" | "." | "!" | "~" | "*" | "'" | "(" | ")"		
		"""
		# UPALPHA = <any US-ASCII uppercase letter "A".."Z">
		upalpha="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsUpAlpha(c)==(c in upalpha),"IsUpAlpha(chr(%i))"%i)
		lowalpha="abcdefghijklmnopqrstuvwxyz"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsLowAlpha(c)==(c in lowalpha),"IsLowAlpha(chr(%i))"%i)
		alpha=upalpha+lowalpha
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsAlpha(c)==(c in alpha),"IsAlpha(chr(%i))"%i)
		digit="0123456789"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsDigit(c)==(c in digit),"IsDigit(chr(%i))"%i)
		alphanum=alpha+digit
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsAlphaNum(c)==(c in alphanum),"IsAlphaNum(chr(%i))"%i)
		reserved=";/?:@&=+$,"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsReserved(c)==(c in reserved),"IsReserved(chr(%i))"%i)
		mark="-_.!~*'()"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsMark(c)==(c in mark),"IsMark(chr(%i))"%i)
		unreserved=alphanum+mark
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsUnreserved(c)==(c in unreserved),"IsUnreserved(chr(%i))"%i)
		control="\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1A\x1B\x1C\x1D\x1E\x1F\x7F"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsControl(c)==(c in control),"IsControl(chr(%i))"%i)
		space=" "
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsSpace(c)==(c in space),"IsSpace(chr(%i))"%i)
		delims="<>#%\""
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsDelims(c)==(c in delims),"IsDelims(chr(%i))"%i)
		unwise="{}|\\^[]`"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsUnwise(c)==(c in unwise),"IsUnwise(chr(%i))"%i)
		authorityReserved=";:@?/"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsAuthorityReserved(c)==(c in authorityReserved),"IsAuthorityReserved(chr(%i))"%i)
		pathSegmentReserved="/;=?"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsPathSegmentReserved(c)==(c in pathSegmentReserved),"IsPathSegmentReserved(chr(%i))"%i)
		queryReserved=";/?:@&=+,$"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsQueryReserved(c)==(c in queryReserved),"IsQueryReserved(chr(%i))"%i)
		
	def testURIC(self):
		"""uric = reserved | unreserved | escaped"""
		self.failUnless(ParseURIC("w ")==1,"space in URI")
		self.failUnless(ParseURIC("'w'>")==3,"single-quote in URI")
		self.failUnless(ParseURIC('"w">')==0,"double-quote in URI")
		self.failUnless(ParseURIC('Caf%E9 ')==6,"uc hex")
		self.failUnless(ParseURIC('Caf%e9 ')==6,"lc hex")
		self.failUnless(ParseURIC('index#frag')==5,"fragment in URI")
		
	def testEscape(self):
		DATA="\t\n\r !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
		ESCAPED_NORMAL="%09%0A%0D%20!%22%23%24%25%26'()*%2B%2C-.%2F0123456789%3A%3B%3C%3D%3E%3F%40ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E_%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D~"
		ESCAPED_MAX="%09%0A%0D%20%21%22%23%24%25%26%27%28%29%2A%2B%2C%2D%2E%2F0123456789%3A%3B%3C%3D%3E%3F%40ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E%5F%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D%7E"
		ESCAPED_MIN="%09%0A%0D%20!%22%23$%25&'()*+,-./0123456789:;%3C=%3E?@ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E_%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D~"
		self.CompareStrings(ESCAPED_NORMAL,EscapeData(DATA),"Normal escaping")
		self.CompareStrings(ESCAPED_MAX,EscapeData(DATA,lambda x:not IsAlphaNum(x)),"Max escaping")
		self.CompareStrings(ESCAPED_MIN,EscapeData(DATA,lambda x:False),"Min escaping")
		self.CompareStrings(DATA,UnescapeData(EscapeData(DATA)),"Round-trip escaping")		
			
	def CompareStrings(self,expected,found,label="Test"):
		for i in xrange(len(expected)):
			if i>=len(found):
				self.fail("%s truncation failure:\n%s... expected %s"%(label,found[0:i],expected[i]))
			if expected[i]==found[i]:
				continue
			self.fail("%s mismatch:\n%s... expected %s ; found %s"%(label,found[0:i+1],expected[i],found[i]))
	
	def testPathSegments(self):
		# if there is no absPath in a URI then absPath will be None, should be safe to split
		segments=SplitAbsPath(None)
		self.failUnless(segments==[])
		# an absPath cannot be an empty string so treat this the same as None
		segments=SplitAbsPath('')
		self.failUnless(segments==[])
		# if there is an absPath there is always at least one segment, so '/' is a single empty segment
		segments=SplitAbsPath('/')
		self.failUnless(segments==[''])
		# we don't decode when splitting, segments can contain params
		segments=SplitAbsPath('/Caf%e9/Nero;LHR.T2/Table4/')
		self.failUnless(segments==['Caf%e9','Nero;LHR.T2','Table4',''])
		# A segment may be empty
		pchar,params=SplitPathSegment('')
		self.failUnless(pchar=='' and params==[])
		# A segment may have no params (and should not remove escaping)
		pchar,params=SplitPathSegment('Caf%e9')
		self.failUnless(pchar=='Caf%e9' and params==[])
		# A segment param may be empty
		pchar,params=SplitPathSegment('Nero;')
		self.failUnless(pchar=='Nero' and params==[''],"Got: %s %s"%(pchar,str(params)))
		# A segment may consist only of params
		pchar,params=SplitPathSegment(';Nero')
		self.failUnless(pchar=='' and params==['Nero'])
		# Degenerate params
		pchar,params=SplitPathSegment(';')
		self.failUnless(pchar=='' and params==[''])
		# A segment param does not remove escaping
		pchar,params=SplitPathSegment('Nero;LHR.T2;curr=%a3')
		self.failUnless(pchar=='Nero' and params==['LHR.T2','curr=%a3'])
		
	def testServer(self):
		keys=SERVER_EXAMPLES.keys()
		for k in keys:
			userinfo,host,port=SplitServer(k)
			userinfo2,host2,port2=SERVER_EXAMPLES[k]
			self.failUnless(userinfo==userinfo2,"%s found userinfo %s"%(k,userinfo2))
			self.failUnless(host==host2,"%s found host %s"%(k,host2))
			self.failUnless(port==port2,"%s found port %s"%(k,port2))
		
SIMPLE_EXAMPLE='http://www.example.com/'
RELATIVE_EXAMPLE="index.html"
LIST_EXAMPLE='http://www.example.com/ http://www.example.com/index.htm'

ABS_EXAMPLES={
	'ftp://ftp.is.co.za/rfc/rfc1808.txt':
		('ftp',None,'ftp.is.co.za','/rfc/rfc1808.txt',None),
	'gopher://spinaltap.micro.umn.edu/00/Weather/California/Los%20Angeles':
		('gopher',None,'spinaltap.micro.umn.edu','/00/Weather/California/Los%20Angeles',None),
	'http://www.math.uio.no/faq/compression-faq/part1.html':
		('http',None,'www.math.uio.no','/faq/compression-faq/part1.html',None),
	'mailto:mduerst@ifi.unizh.ch':
		('mailto','mduerst@ifi.unizh.ch',None,None,None),
	'news:comp.infosystems.www.servers.unix':
		('news','comp.infosystems.www.servers.unix',None,None,None),
	'telnet://melvyl.ucop.edu/':
		('telnet',None,'melvyl.ucop.edu','/',None),
	'http://www.ics.uci.edu/pub/ietf/uri/#Related':
		('http',None,'www.ics.uci.edu','/pub/ietf/uri/',None),
	'http://a/b/c/g?y':
		('http',None,'a','/b/c/g','y')
	}

REL_BASE="http://a/b/c/d;p?q"
REL_BASE1="http://a/b/"
REL_BASE2="c/d;p?q"

REL_CURRENT="current.doc"
REL_EXAMPLES={
	# resolved URI, scheme, authority, absPath, relPath, query, fragment
	'g:h':('g:h','g',None,None,None,None,None),
	'g':('http://a/b/c/g',None,None,None,'g',None,None),
	'./g':('http://a/b/c/g',None,None,None,'./g',None,None),
	'g/':('http://a/b/c/g/',None,None,None,'g/',None,None),
	'/g':('http://a/g',None,None,'/g',None,None,None),
	'//g':('http://g',None,'g',None,None,None,None),
	'?y':('http://a/b/c/?y',None,None,None,'','y',None),
	'./?y':('http://a/b/c/?y',None,None,None,'./','y',None),
	'g?y':('http://a/b/c/g?y',None,None,None,'g','y',None),
	'#s':('current.doc#s',None,None,None,'',None,'s'),
	'g#s':('http://a/b/c/g#s',None,None,None,'g',None,'s'),
	'g?y#s':('http://a/b/c/g?y#s',None,None,None,'g','y','s'),
	';x':('http://a/b/c/;x',None,None,None,';x',None,None),
	'g;x':('http://a/b/c/g;x',None,None,None,'g;x',None,None),
	'g;x?y#s':('http://a/b/c/g;x?y#s',None,None,None,'g;x','y','s'),
	'.':('http://a/b/c/',None,None,None,'.',None,None),
	'./':('http://a/b/c/',None,None,None,'./',None,None),
	'..':('http://a/b/',None,None,None,'..',None,None),
	'../':('http://a/b/',None,None,None,'../',None,None),
	'../g':('http://a/b/g',None,None,None,'../g',None,None),
	'../..':('http://a/',None,None,None,'../..',None,None),
	'../../':('http://a/',None,None,None,'../../',None,None),
	'../../g':('http://a/g',None,None,None,'../../g',None,None)
	}
	

class URITests(unittest.TestCase):
	def testCaseConstructor(self):
		u=URI(SIMPLE_EXAMPLE)
		self.failUnless(isinstance(u,URI))
		self.failUnless(str(u)==SIMPLE_EXAMPLE)
		u=URI(LIST_EXAMPLE)
		self.failUnless(str(u)==SIMPLE_EXAMPLE,"Simple from list")
		u=URI(u'\u82f1\u56fd.xml')
		self.failUnless(str(u)=='%E8%8B%B1%E5%9B%BD.xml',"Unicode example: %s"%str(u))
		self.failUnless(type(u.octets) is StringType,"octest must be string")
	
	def testCaseCompare(self):
		u1=URI(SIMPLE_EXAMPLE)
		u2=URI(SIMPLE_EXAMPLE)
		self.failUnless(u1.Match(u2) and u2.Match(u1),"Equal URIs fail to match")
		u2=URI('hello.xml')
		self.failIf(u1.Match(u2) or u2.Match(u1),"Mismatched URIs do match")		
	
	def testCaseScheme(self):
		u=URI(SIMPLE_EXAMPLE)
		self.failUnless(u.IsAbsolute(),"Absolute test")
		self.failUnless(u.scheme=='http',"Scheme")
		self.failUnless(u.schemeSpecificPart=='//www.example.com/')
		u=URI(RELATIVE_EXAMPLE)
		self.failIf(u.IsAbsolute(),"Relative test")
		self.failUnless(u.scheme is None,"relative scheme")
		self.failUnless(u.schemeSpecificPart is None)

	def testCaseFragment(self):
		u=URI(SIMPLE_EXAMPLE)
		self.failUnless(u.fragment is None,"no fragment")
		u=URI('http://www.ics.uci.edu/pub/ietf/uri/#Related')
		self.failUnless(u.schemeSpecificPart=='//www.ics.uci.edu/pub/ietf/uri/','URI with fragment')
		self.failUnless(u.fragment=='Related','fragment')
		
	def testCaseAbsoluteExamples(self):
		keys=ABS_EXAMPLES.keys()
		for k in keys:
			u=URI(k)
			scheme,opaquePart,authority,absPath,query=ABS_EXAMPLES[k]
			self.failUnless(scheme==u.scheme,"%s found scheme %s"%(k,u.scheme))
			self.failUnless(opaquePart==u.opaquePart,"%s found opaquePart %s"%(k,u.opaquePart))
			self.failUnless(authority==u.authority,"%s found authority %s"%(k,u.authority))
			self.failUnless(absPath==u.absPath,"%s found absPath %s"%(k,u.absPath))
			self.failUnless(query==u.query,"%s found query %s"%(k,u.query))
		
	def testCaseRelativeExamples(self):
		keys=REL_EXAMPLES.keys()
		base=URI(REL_BASE)
		current=URI(REL_CURRENT)
		relatives={}
		for k in keys:
			u=URI(k)
			resolved,scheme,authority,absPath,relPath,query,fragment=REL_EXAMPLES[k]
			relatives[resolved]=relatives.get(resolved,[])+[k]
			resolution=str(u.Resolve(base,current))
			self.failUnless(scheme==u.scheme,"%s found scheme %s"%(k,u.scheme))
			self.failUnless(authority==u.authority,"%s found authority %s"%(k,u.authority))
			self.failUnless(absPath==u.absPath,"%s found absPath %s"%(k,u.absPath))
			self.failUnless(relPath==u.relPath,"%s found relPath %s"%(k,u.relPath))
			self.failUnless(query==u.query,"%s found query %s"%(k,u.query))
			self.failUnless(fragment==u.fragment,"%s found fragment %s"%(k,u.fragment))
			self.failUnless(resolved==resolution,"%s [*] %s = %s ; found %s"%(str(base),k,resolved,resolution))
		for r in relatives.keys():
			# print "Testing %s [/] %s = ( %s )"%(r,str(base),string.join(relatives[r],' | '))
			u=URI(r)
			if not u.IsAbsolute(): # this check removes the 'current document' case
				continue
			relative=str(u.Relative(base))
			# relative should be one of the relatives!
			noMatch=True
			for k in relatives[r]:
				if k==relative:
					noMatch=False
					break
			self.failIf(noMatch,"%s [/] %s = ( %s ) ; found %s"%(r,str(base),string.join(relatives[r],' | '),relative))

	def testCaseRelativeJoinExamples(self):
		keys=REL_EXAMPLES.keys()
		base1=URI(REL_BASE1)
		base2=URI(REL_BASE2)
		current=URI(REL_CURRENT)
		relatives={}
		for k in keys:
			u=URI(k)
			if not u.octets: # don't test same document cases
				continue
			resolved,scheme,authority,absPath,relPath,query,fragment=REL_EXAMPLES[k]
			# print "Testing: %s [*] ( %s [*] %s ) = %s"%(str(base1),str(base2),k,resolved)
			# two-step resolution, first combines relative URLs, second resolves to absolute
			resolution1=u.Resolve(base2,current)
			relatives[str(resolution1)]=relatives.get(str(resolution1),[])+[k]
			resolution2=str(resolution1.Resolve(base1,current))
			self.failUnless(scheme==u.scheme,"%s found scheme %s"%(k,u.scheme))
			self.failUnless(authority==u.authority,"%s found authority %s"%(k,u.authority))
			self.failUnless(absPath==u.absPath,"%s found absPath %s"%(k,u.absPath))
			self.failUnless(relPath==u.relPath,"%s found relPath %s"%(k,u.relPath))
			self.failUnless(query==u.query,"%s found query %s"%(k,u.query))
			self.failUnless(fragment==u.fragment,"%s found fragment %s"%(k,u.fragment))
			self.failUnless(resolved==resolution2,"%s [*] ( %s [*] %s ) = %s ; found %s"%(str(base1),str(base2),k,resolved,resolution2))
		for r in relatives.keys():
			#print "Testing: %s [/] %s = ( %s )"%(r,str(base2),string.join(relatives[r],' | '))
			u=URI(r)
			if u.octets=='current.doc': # this check removes the 'current document' case
				continue
			relative=str(u.Relative(base2))
			# now relative should be one of the relatives!
			noMatch=True
			for k in relatives[r]:
				if k==relative:
					noMatch=False
					break
			self.failIf(noMatch,"%s [/] %s = ( %s ); found %s"%(r,str(base2),repr(relatives[r]),relative))

FILE_EXAMPLE="file://vms.host.edu/disk$user/my/notes/note12345.txt"

class FileURLTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_rfc2396')
		if not os.path.isabs(self.dataPath):
			self.dataPath=os.path.join(os.getcwd(),self.dataPath)
			
	def testCaseConstructor(self):
		u=URIFactory.URI(FILE_EXAMPLE)
		self.failUnless(isinstance(u,URI),"FileURL is URI")
		self.failUnless(isinstance(u,FileURL),"FileURI is FileURL")
		self.failUnless(str(u)==FILE_EXAMPLE)
		u=FileURL()
		self.failUnless(str(u)=='file:///','Default file')
		
	def testCasePathnames(self):
		force8Bit=type(self.dataPath) is StringType
		base=URIFactory.URLFromPathname(self.dataPath)
		self.failUnless(base.GetPathname(force8Bit)==self.dataPath,
			"Expected %s found %s"%(self.dataPath,base.GetPathname(force8Bit)))
		os.path.walk(self.dataPath,self.VisitMethod,None)

	def testCaseUnicodePathnames(self):
		if type(self.dataPath) is StringType:
			c=sys.getfilesystemencoding()
			dataPath=unicode(self.dataPath,c)
		base=URIFactory.URLFromPathname(dataPath)
		if os.path.supports_unicode_filenames:
			dataPath2=base.GetPathname()
			self.failUnless(type(dataPath2) is UnicodeType,"Expected GetPathname to return unicode") 
			self.failUnless(dataPath2==dataPath,
				u"Expected %s found %s"%(dataPath,dataPath2))
			os.path.walk(dataPath,self.VisitMethod,None)
		else:
			dataPath2=base.GetPathname()
			self.failUnless(type(dataPath2) is StringType,"Expected GetPathname to return string")
			print "\nWarning: os.path.supports_unicode_filenames is False (skipped unicode path tests)"
			
	def VisitMethod(self,arg,dirname,names):
		d=URIFactory.URLFromPathname(os.path.join(dirname,os.curdir))
		c=sys.getfilesystemencoding()
		for name in names:
                        if name.startswith('??'):
                                print "\nWarning: 8-bit path tests limited to ASCII file names by %s encoding"%c
                                continue
			joinMatch=os.path.join(dirname,name)
			if type(name) is UnicodeType:
				segName=EscapeData(name.encode('utf-8'),IsPathSegmentReserved)
			else:
				segName=EscapeData(name,IsPathSegmentReserved)
			u=URI(segName)
			u=u.Resolve(d)
			self.failUnless(isinstance(u,FileURL))
			joined=u.GetPathname()
			if type(joinMatch) is StringType and type(joined) is UnicodeType:
				# if we're walking in 8-bit mode we need to downgrade to compare
				joined=joined.encode(c)
			self.failUnless(joined==joinMatch,"Joined pathnames mismatch:\n%s\n%s"%(joined,joinMatch))
		

if __name__ == "__main__":
	unittest.main()

