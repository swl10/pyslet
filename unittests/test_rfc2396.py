#! /usr/bin/env python

import unittest, logging
import os, os.path, sys
from types import UnicodeType, StringType

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(RFC2396Tests,'test'),
		unittest.makeSuite(URITests,'test'),
		unittest.makeSuite(FileURLTests,'test'),
		unittest.makeSuite(VirtualFileURLTests,'test')
		))

from pyslet.rfc2396 import *
import pyslet.vfs as vfs

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
			c=chr(i);self.assertTrue(IsUpAlpha(c)==(c in upalpha),"IsUpAlpha(chr(%i))"%i)
		lowalpha="abcdefghijklmnopqrstuvwxyz"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsLowAlpha(c)==(c in lowalpha),"IsLowAlpha(chr(%i))"%i)
		alpha=upalpha+lowalpha
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsAlpha(c)==(c in alpha),"IsAlpha(chr(%i))"%i)
		digit="0123456789"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsDigit(c)==(c in digit),"IsDigit(chr(%i))"%i)
		alphanum=alpha+digit
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsAlphaNum(c)==(c in alphanum),"IsAlphaNum(chr(%i))"%i)
		reserved=";/?:@&=+$,"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsReserved(c)==(c in reserved),"IsReserved(chr(%i))"%i)
		mark="-_.!~*'()"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsMark(c)==(c in mark),"IsMark(chr(%i))"%i)
		unreserved=alphanum+mark
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsUnreserved(c)==(c in unreserved),"IsUnreserved(chr(%i))"%i)
		control="\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1A\x1B\x1C\x1D\x1E\x1F\x7F"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsControl(c)==(c in control),"IsControl(chr(%i))"%i)
		space=" "
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsSpace(c)==(c in space),"IsSpace(chr(%i))"%i)
		delims="<>#%\""
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsDelims(c)==(c in delims),"IsDelims(chr(%i))"%i)
		unwise="{}|\\^[]`"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsUnwise(c)==(c in unwise),"IsUnwise(chr(%i))"%i)
		authorityReserved=";:@?/"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsAuthorityReserved(c)==(c in authorityReserved),"IsAuthorityReserved(chr(%i))"%i)
		pathSegmentReserved="/;=?"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsPathSegmentReserved(c)==(c in pathSegmentReserved),"IsPathSegmentReserved(chr(%i))"%i)
		queryReserved=";/?:@&=+,$"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsQueryReserved(c)==(c in queryReserved),"IsQueryReserved(chr(%i))"%i)
		
	def testURIC(self):
		"""uric = reserved | unreserved | escaped"""
		self.assertTrue(ParseURIC("w ")==1,"space in URI")
		self.assertTrue(ParseURIC("'w'>")==3,"single-quote in URI")
		self.assertTrue(ParseURIC('"w">')==0,"double-quote in URI")
		self.assertTrue(ParseURIC('Caf%E9 ')==6,"uc hex")
		self.assertTrue(ParseURIC('Caf%e9 ')==6,"lc hex")
		self.assertTrue(ParseURIC('index#frag')==5,"fragment in URI")
		
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
			self.fail("%s mismatch:\n%s... expected %s ; found %s"%(label,repr(found[0:i+1]),repr(expected[i]),repr(found[i])))
	
	def testPathSegments(self):
		# if there is no absPath in a URI then absPath will be None, should be safe to split
		segments=SplitAbsPath(None)
		self.assertTrue(segments==[])
		# an absPath cannot be an empty string so treat this the same as None
		segments=SplitAbsPath('')
		self.assertTrue(segments==[])
		# if there is an absPath there is always at least one segment, so '/' is a single empty segment
		segments=SplitAbsPath('/')
		self.assertTrue(segments==[''])
		# we don't decode when splitting, segments can contain params
		segments=SplitAbsPath('/Caf%e9/Nero;LHR.T2/Table4/')
		self.assertTrue(segments==['Caf%e9','Nero;LHR.T2','Table4',''])
		# A segment may be empty
		pchar,params=SplitPathSegment('')
		self.assertTrue(pchar=='' and params==[])
		# A segment may have no params (and should not remove escaping)
		pchar,params=SplitPathSegment('Caf%e9')
		self.assertTrue(pchar=='Caf%e9' and params==[])
		# A segment param may be empty
		pchar,params=SplitPathSegment('Nero;')
		self.assertTrue(pchar=='Nero' and params==[''],"Got: %s %s"%(pchar,str(params)))
		# A segment may consist only of params
		pchar,params=SplitPathSegment(';Nero')
		self.assertTrue(pchar=='' and params==['Nero'])
		# Degenerate params
		pchar,params=SplitPathSegment(';')
		self.assertTrue(pchar=='' and params==[''])
		# A segment param does not remove escaping
		pchar,params=SplitPathSegment('Nero;LHR.T2;curr=%a3')
		self.assertTrue(pchar=='Nero' and params==['LHR.T2','curr=%a3'])
		
	def testServer(self):
		keys=SERVER_EXAMPLES.keys()
		for k in keys:
			userinfo,host,port=SplitServer(k)
			userinfo2,host2,port2=SERVER_EXAMPLES[k]
			self.assertTrue(userinfo==userinfo2,"%s found userinfo %s"%(k,userinfo2))
			self.assertTrue(host==host2,"%s found host %s"%(k,host2))
			self.assertTrue(port==port2,"%s found port %s"%(k,port2))
		
SIMPLE_EXAMPLE='http://www.example.com/'
RELATIVE_EXAMPLE="index.html"
LIST_EXAMPLE='http://www.example.com/ http://www.example.com/index.htm'

ABS_EXAMPLES={
	'ftp://ftp.is.co.za/rfc/rfc1808.txt':
		('ftp',None,'ftp.is.co.za','/rfc/rfc1808.txt',None,'rfc1808.txt'),
	'gopher://spinaltap.micro.umn.edu/00/Weather/California/Los%20Angeles':
		('gopher',None,'spinaltap.micro.umn.edu','/00/Weather/California/Los%20Angeles',None,'Los Angeles'),
	'http://www.math.uio.no/faq/compression-faq/part1.html':
		('http',None,'www.math.uio.no','/faq/compression-faq/part1.html',None,'part1.html'),
	'mailto:mduerst@ifi.unizh.ch':
		('mailto','mduerst@ifi.unizh.ch',None,None,None,None),
	'news:comp.infosystems.www.servers.unix':
		('news','comp.infosystems.www.servers.unix',None,None,None,None),
	'telnet://melvyl.ucop.edu/':
		('telnet',None,'melvyl.ucop.edu','/',None,''),
	'http://www.ics.uci.edu/pub/ietf/uri/#Related':
		('http',None,'www.ics.uci.edu','/pub/ietf/uri/',None,''),
	'http://a/b/c/g?y':
		('http',None,'a','/b/c/g','y','g'),
	'http://a/b/c/g?':
		('http',None,'a','/b/c/g','','g'),
	'http://a/?':
		('http',None,'a','/','',''),		
	'noauth:/':
		('noauth',None,None,'/',None,''),		
	'noauth:/?':
		('noauth',None,None,'/','','')
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
	'/g?':('http://a/g?',None,None,'/g',None,'',None),
	'/':('http://a/',None,None,'/',None,None,None),
	'/?':('http://a/?',None,None,'/',None,'',None),
	'//g':('http://g',None,'g',None,None,None,None),
	'?y':('http://a/b/c/?y',None,None,None,'','y',None),
	'./?y':('http://a/b/c/?y',None,None,None,'./','y',None),
	'g?y':('http://a/b/c/g?y',None,None,None,'g','y',None),
	'g?':('http://a/b/c/g?',None,None,None,'g','',None),
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
	'../../g':('http://a/g',None,None,None,'../../g',None,None),
	'../../g?':('http://a/g?',None,None,None,'../../g','',None),
	'../../?':('http://a/?',None,None,None,'../../','',None),
	}
	

class URITests(unittest.TestCase):
	def testCaseConstructor(self):
		u=URI(SIMPLE_EXAMPLE)
		self.assertTrue(isinstance(u,URI))
		self.assertTrue(str(u)==SIMPLE_EXAMPLE)
		try:
			u=URI(LIST_EXAMPLE)
			# we don't support this type of thing any more
			# self.assertTrue(str(u)==SIMPLE_EXAMPLE,"Simple from list")
		except URIException:
			pass
		u=URI(u'\u82f1\u56fd.xml')
		self.assertTrue(str(u)=='%E8%8B%B1%E5%9B%BD.xml',"Unicode example: %s"%str(u))
		self.assertTrue(type(u.octets) is StringType,"octest must be string")
	
	def testCaseCompare(self):
		u1=URI(SIMPLE_EXAMPLE)
		u2=URI(SIMPLE_EXAMPLE)
		self.assertTrue(u1.Match(u2) and u2.Match(u1),"Equal URIs fail to match")
		u2=URI('hello.xml')
		self.assertFalse(u1.Match(u2) or u2.Match(u1),"Mismatched URIs do match")		
		u1=URI("HTTP://www.example.com/")
		u2=URI("http://www.example.com/")
		self.assertTrue(u1.Match(u2) and u2.Match(u1),"Equal URIs fail to match")
		
	def testCaseScheme(self):
		u=URI(SIMPLE_EXAMPLE)
		self.assertTrue(u.IsAbsolute(),"Absolute test")
		self.assertTrue(u.scheme=='http',"Scheme")
		self.assertTrue(u.schemeSpecificPart=='//www.example.com/')
		u=URI(RELATIVE_EXAMPLE)
		self.assertFalse(u.IsAbsolute(),"Relative test")
		self.assertTrue(u.scheme is None,"relative scheme")
		self.assertTrue(u.schemeSpecificPart is None)

	def testCaseFragment(self):
		u=URI(SIMPLE_EXAMPLE)
		self.assertTrue(u.fragment is None,"no fragment")
		u=URI('http://www.ics.uci.edu/pub/ietf/uri/#Related')
		self.assertTrue(u.schemeSpecificPart=='//www.ics.uci.edu/pub/ietf/uri/','URI with fragment')
		self.assertTrue(u.fragment=='Related','fragment')
		
	def testCaseAbsoluteExamples(self):
		keys=ABS_EXAMPLES.keys()
		for k in keys:
			logging.info("Testing absolute: %s",k)
			u=URI(k)
			scheme,opaquePart,authority,absPath,query,fName=ABS_EXAMPLES[k]
			self.assertTrue(scheme==u.scheme,"%s found scheme %s"%(k,u.scheme))
			self.assertTrue(opaquePart==u.opaquePart,"%s found opaquePart %s"%(k,u.opaquePart))
			self.assertTrue(authority==u.authority,"%s found authority %s"%(k,u.authority))
			self.assertTrue(absPath==u.absPath,"%s found absPath %s"%(k,u.absPath))
			self.assertTrue(query==u.query,"%s found query %s"%(k,u.query))
			self.assertTrue(fName==u.GetFileName(),"%s found file name %s"%(k,u.GetFileName()))
		
	def testCaseRelativeExamples(self):
		keys=REL_EXAMPLES.keys()
		base=URI(REL_BASE)
		current=URI(REL_CURRENT)
		relatives={}
		for k in keys:
			logging.info("Testing relative: %s",k)
			u=URI(k)
			resolved,scheme,authority,absPath,relPath,query,fragment=REL_EXAMPLES[k]
			relatives[resolved]=relatives.get(resolved,[])+[k]
			resolution=str(u.Resolve(base,current))
			self.assertTrue(scheme==u.scheme,"%s found scheme %s"%(k,u.scheme))
			self.assertTrue(authority==u.authority,"%s found authority %s"%(k,u.authority))
			self.assertTrue(absPath==u.absPath,"%s found absPath %s"%(k,u.absPath))
			self.assertTrue(relPath==u.relPath,"%s found relPath %s"%(k,u.relPath))
			self.assertTrue(query==u.query,"%s found query %s"%(k,u.query))
			self.assertTrue(fragment==u.fragment,"%s found fragment %s"%(k,u.fragment))
			self.assertTrue(resolved==resolution,"%s [*] %s = %s ; found %s"%(str(base),k,resolved,resolution))
		for r in relatives.keys():
			logging.info("Testing %s [/] %s = ( %s )",r,str(base),string.join(relatives[r],' | '))
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
			self.assertFalse(noMatch,"%s [/] %s = ( %s ) ; found %s"%(r,str(base),string.join(relatives[r],' | '),relative))

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
			logging.info("Testing: %s [*] ( %s [*] %s ) = %s",str(base1),str(base2),k,resolved)
			# two-step resolution, first combines relative URLs, second resolves to absolute
			resolution1=u.Resolve(base2,current)
			relatives[str(resolution1)]=relatives.get(str(resolution1),[])+[k]
			resolution2=str(resolution1.Resolve(base1,current))
			self.assertTrue(scheme==u.scheme,"%s found scheme %s"%(k,u.scheme))
			self.assertTrue(authority==u.authority,"%s found authority %s"%(k,u.authority))
			self.assertTrue(absPath==u.absPath,"%s found absPath %s"%(k,u.absPath))
			self.assertTrue(relPath==u.relPath,"%s found relPath %s"%(k,u.relPath))
			self.assertTrue(query==u.query,"%s found query %s"%(k,u.query))
			self.assertTrue(fragment==u.fragment,"%s found fragment %s"%(k,u.fragment))
			self.assertTrue(resolved==resolution2,"%s [*] ( %s [*] %s ) = %s ; found %s"%(str(base1),str(base2),k,resolved,resolution2))
		for r in relatives.keys():
			logging.info("Testing: %s [/] %s = ( %s )",r,str(base2),string.join(relatives[r],' | '))
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
			self.assertFalse(noMatch,"%s [/] %s = ( %s ); found %s"%(r,str(base2),repr(relatives[r]),relative))

FILE_EXAMPLE="file://vms.host.edu/disk$user/my/notes/note12345.txt"

class FileURLTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		self.dataPath=os.path.join(os.path.split(__file__)[0],'data_rfc2396')
		if not os.path.isabs(self.dataPath):
			self.dataPath=os.path.join(os.getcwd(),self.dataPath)
			
	def testCaseConstructor(self):
		u=URIFactory.URI(FILE_EXAMPLE)
		self.assertTrue(isinstance(u,URI),"FileURL is URI")
		self.assertTrue(isinstance(u,FileURL),"FileURI is FileURL")
		self.assertTrue(str(u)==FILE_EXAMPLE)
		u=FileURL()
		self.assertTrue(str(u)=='file:///','Default file')
		
	def testCasePathnames(self):
		force8Bit=type(self.dataPath) is StringType
		base=URIFactory.URLFromPathname(self.dataPath)
		self.assertTrue(base.GetPathname(force8Bit)==self.dataPath,
			"Expected %s found %s"%(self.dataPath,base.GetPathname(force8Bit)))
		for dirpath,dirnames,filenames in os.walk(self.dataPath):
			self.VisitMethod(dirpath,filenames)

	def testCaseUnicodePathnames(self):
		if type(self.dataPath) is StringType:
			c=sys.getfilesystemencoding()
			dataPath=unicode(self.dataPath,c)
		else:
			dataPath=self.dataPath
		base=URIFactory.URLFromPathname(dataPath)
		if os.path.supports_unicode_filenames:
			dataPath2=base.GetPathname()
			self.assertTrue(type(dataPath2) is UnicodeType,"Expected GetPathname to return unicode") 
			self.assertTrue(dataPath2==dataPath,
				u"Expected %s found %s"%(dataPath,dataPath2))
			# os.path.walk(dataPath,self.VisitMethod,None)
			for dirpath,dirnames,filenames in os.walk(dataPath):
				self.VisitMethod(dirpath,filenames)
		else:
			dataPath2=base.GetPathname()
			self.assertTrue(type(dataPath2) is StringType,"Expected GetPathname to return string")
			logging.warn("os.path.supports_unicode_filenames is False (skipped unicode path tests)")
			
	def VisitMethod(self,dirname,names):
		d=URIFactory.URLFromPathname(os.path.join(dirname,os.curdir))
		c=sys.getfilesystemencoding()
		for name in names:
			if name.startswith('??'):
				logging.warn("8-bit path tests limited to ASCII file names by %s encoding",c)
				continue
			joinMatch=os.path.join(dirname,name)
			if type(name) is UnicodeType:
				segName=EscapeData(name.encode('utf-8'),IsPathSegmentReserved)
			else:
				segName=EscapeData(name,IsPathSegmentReserved)
			u=URI(segName)
			u=u.Resolve(d)
			self.assertTrue(isinstance(u,FileURL))
			joined=u.GetPathname()
			if type(joinMatch) is StringType and type(joined) is UnicodeType:
				# if we're walking in 8-bit mode we need to downgrade to compare
				joined=joined.encode(c)
			self.assertTrue(joined==joinMatch,"Joined pathnames mismatch:\n%s\n%s"%(joined,joinMatch))


class VirtualFileURLTests(unittest.TestCase):
	def setUp(self):
		self.vfs=vfs.defaultFS
		self.cwd=self.vfs.getcwd()
		self.dataPath=self.vfs(__file__).split()[0].join('data_rfc2396')
		if not self.dataPath.isabs():
			self.dataPath=self.vfs.getcwd().join(self.dataPath)

	def testCaseConstructor(self):
		u=URIFactory.URI(FILE_EXAMPLE)
		self.assertTrue(isinstance(u,URI),"FileURL is URI")
		self.assertTrue(isinstance(u,FileURL),"FileURI is FileURL")
		self.assertTrue(str(u)==FILE_EXAMPLE)
		u=FileURL()
		self.assertTrue(str(u)=='file:///','Default file')
		
	def testCasePathnames(self):
		base=URIFactory.URLFromVirtualFilePath(self.dataPath)
		self.assertTrue(base.GetVirtualFilePath()==self.dataPath,
			"Expected %s found %s"%(self.dataPath,base.GetVirtualFilePath()))
		for dirpath,dirnames,filenames in self.dataPath.walk():
			self.VisitMethod(dirpath,filenames)

	def VisitMethod(self,dirname,names):
		# Make d a directory like path by adding an empty component at the end
		d=URIFactory.URLFromVirtualFilePath(dirname.join(dirname.curdir))
		for name in names:
			if unicode(name).startswith('??'):
				logging.warn("8-bit path tests limited to ASCII file names")
				continue
			joinMatch=dirname.join(name)
			segName=EscapeData(unicode(name).encode('utf-8'),IsPathSegmentReserved)
			u=URI(segName)
			u=u.Resolve(d)
			self.assertTrue(isinstance(u,FileURL))
			joined=u.GetVirtualFilePath()
			self.assertTrue(joined==joinMatch,"Joined pathnames mismatch:\n%s\n%s"%(joined,joinMatch))
		

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	unittest.main()

