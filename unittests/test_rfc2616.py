#! /usr/bin/env python

import unittest
import StringIO
import socket

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(HTTP2616Tests,'test') #,
#		unittest.makeSuite(MoreTests,'test')
		))

from pyslet.rfc2616 import *

import random
import os

TEST_STRING="The quick brown fox jumped over the lazy dog"

TEST_SERVER_1={
	"GET / HTTP/1.1\r\nHost: www.domain1.com":"HTTP/1.1 200 You got it!\r\nContent-Length: %i\r\n\r\n%s"%(len(TEST_STRING),TEST_STRING),
	"HEAD / HTTP/1.1\r\nHost: www.domain1.com":"HTTP/1.1 200 You got it!\r\nContent-Length: %i\r\n\r\n"%len(TEST_STRING),
	"PUT /file HTTP/1.1\r\nContent-Length: 10\r\nHost: www.domain1.com":"",
	"123456":"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n",
	"a\r\n123456":"", # A chunk containing our test string
	"\r\n0":"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n", # The chunked encoding trailer, assume this is OK
	"PUT /file HTTP/1.1\r\nContent-Length: 10\r\nExpect: 100-continue\r\nHost: www.domain1.com":"HTTP/1.1 100 Go on then!\r\n\r\n",
	"PUT /file2 HTTP/1.1\r\nContent-Length: 10\r\nExpect: 100-continue\r\nHost: www.domain1.com":
		"HTTP/1.1 301 PUT it somewhere else\r\nLocation: http://www.domain1.com/file\r\nContent-Length: 0\r\n\r\n",
	"PUT /file2 HTTP/1.1\r\nExpect: 100-continue\r\nHost: www.domain1.com\r\nTransfer-Encoding: chunked":
		"HTTP/1.1 301 PUT it somewhere else\r\nLocation: http://www.domain1.com/file\r\nContent-Length: 0\r\n\r\n",
	"PUT /file HTTP/1.1\r\nExpect: 100-continue\r\nHost: www.domain1.com\r\nTransfer-Encoding: chunked":"HTTP/1.1 100 Go on then!\r\n\r\n"
	}

TEST_SERVER_2={
	"HEAD / HTTP/1.1\r\nHost: www.domain2.com":"HTTP/1.1 301 Moved\r\nLocation: http://www.domain1.com/\r\n\r\n"
	}
	
TEST_SERVER={
	'www.domain1.com': TEST_SERVER_1,
	'www.domain2.com': TEST_SERVER_2
	}

BAD_REQUEST="HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"

class FakeHTTPConnection(HTTPConnection):
	def NewSocket(self):
		# Socket implementation to follow
		self.manager.Log(HTTP_LOG_DETAIL,"Opening connection to %s..."%self.host)
		self.socket=self
		self.socketFile=self
		self.socketSelect=self.select
		self.socketSendBuffer=StringIO.StringIO()
		self.socketRecvBuffer=StringIO.StringIO()
		self.responseTable=TEST_SERVER[self.host]

	def select(self,readers,writers,errors,timeout):
		r=[]
		w=[self.socketFile]
		if self.CanRead():
			r.append(self.socketFile)
		return r,w,[]
	
	def CanRead(self):
		return len(self.socketRecvBuffer.getvalue())>self.socketRecvBuffer.tell()
		
	def send(self,data):
		if data:
			nBytes=random.randint(1,len(data))
			self.manager.Log(HTTP_LOG_DEBUG,"sending: %s"%repr(data[:nBytes]))
			self.socketSendBuffer.write(data[:nBytes])
			# check to see if this request matches any we know about...
			data=self.socketSendBuffer.getvalue()
			endpos=data.find(CRLF+CRLF)
			if endpos>=0:
				# OK, we have a chunk of data, strip it out of the buffer and
				# look up the response in the table
				newData=data[endpos+4:]
				self.socketSendBuffer=StringIO.StringIO(newData)
				self.socketSendBuffer.seek(len(newData))
				data=data[:endpos]
				self.manager.Log(HTTP_LOG_DEBUG,"%s handling request: \n%s"%(self.host,data))
				response=self.responseTable.get(data,BAD_REQUEST)
				# add this response to the recv buffer
				if response==BAD_REQUEST:
					self.manager.Log(HTTP_LOG_DEBUG,"** Bad Request")
				pos=self.socketRecvBuffer.tell()
				data=self.socketRecvBuffer.getvalue()
				self.socketRecvBuffer=StringIO.StringIO(data[pos:]+response)
			return nBytes
	
	def recv(self,maxBytes):
		if maxBytes:
			nBytes=random.randint(1,maxBytes)
			if nBytes>5:
				nBytes=5
			data=self.socketRecvBuffer.read(nBytes)
			self.manager.Log(HTTP_LOG_DEBUG,"receiving %i bytes: %s"%(nBytes,repr(data)))
			return data
		else:
			self.manager.Log(HTTP_LOG_DEBUG,"receiving: empty string")
			return ''

	def shutdown(self,mode):
		# Nothing to do
		pass
	
	def close(self):
		self.manager.Log(HTTP_LOG_DETAIL,"Closing connection to %s..."%self.host)
		self.socketSendBuffer=None
		self.socketRecvBuffer=None
		

class FakeHTTPRequestManager(HTTPRequestManager):

	FakeHTTPConnectionClass=FakeHTTPConnection

	def __init__(self):
		HTTPRequestManager.__init__(self)
		self.socketSelect=self.select
		#self.SetLog(HTTP_LOG_ALL)
		
	def NewConnection(self,scheme,server,port):
		if scheme=='http':
			return self.FakeHTTPConnectionClass(self,server,port)
		else:
			raise ValueError

	def select(self,readers,writers,errors,timeout):
		r=[]
		for reader in readers:
			if reader.CanRead():
				r.append(reader)
		return r,writers,errors
			
			
class HTTP2616Tests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		
	def tearDown(self):
		os.chdir(self.cwd)
	
	def testCaseBasic(self):
		# OCTET = <any 8-bit sequence of data>
		for c in xrange(0,256):
			self.failUnless(IsOCTET(chr(c)),"IsOCTET(chr(%i))"%c)
		# CHAR = <any US-ASCII character (octets 0 - 127)>
		for c in xrange(0,128):
			self.failUnless(IsCHAR(chr(c)),"IsCHAR(chr(%i))"%c)
		for c in xrange(128,256):
			self.failIf(IsCHAR(chr(c)),"IsCHAR(chr(%i))"%c)
		# UPALPHA = <any US-ASCII uppercase letter "A".."Z">
		UPALPHA="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsUPALPHA(c)==(c in UPALPHA),"IsUPALPHA(chr(%i))"%i)
		# LOALPHA = <any US-ASCII lowercase letter "a".."z">
		LOALPHA="abcdefghijklmnopqrstuvwxyz"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsLOALPHA(c)==(c in LOALPHA),"IsLOALPHA(chr(%i))"%i)
		# ALPHA = UPALPHA | LOALPHA
		ALPHA=UPALPHA+LOALPHA
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsALPHA(c)==(c in ALPHA),"IsALPHA(chr(%i))"%i)
		# DIGIT  = <any US-ASCII digit "0".."9">
		DIGIT="0123456789"
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsDIGIT(c)==(c in DIGIT),"IsDIGIT(chr(%i))"%i)
		# CTL = <any US-ASCII control character (octets 0 - 31) and DEL (127)>
		CTL=string.join(map(chr,xrange(0,32))+[chr(127)],'')
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsCTL(c)==(c in CTL),"IsCTL(chr(%i))"%i)
		# CR = <US-ASCII CR, carriage return (13)>
		self.failUnless(CR==chr(13),"CR")
		# LF = <US-ASCII LF, linefeed (10)>
		self.failUnless(LF==chr(10),"LF")
		# SP = <US-ASCII SP, space (32)>
		self.failUnless(SP==chr(32),"SP")
		# HT = <US-ASCII HT, horizontal-tab (9)>
		self.failUnless(HT==chr(9),"HT")
		# DQUOTE = <US-ASCII double-quote mark (34)>
		self.failUnless(DQUOTE==chr(34),"DQUOTE")
		# CRLF
		self.failUnless(CRLF==CR+LF,"CRLF")
		# LWS = [CRLF] 1*( SP | HT )
		LWS_TEST="Hi \t Hello\r\n Hi\r\n \r\n\t \r "
		self.failUnless(ParseLWS(LWS_TEST,0)==0,"No LWS")
		self.failUnless(ParseLWS(LWS_TEST,2)==3,"LWS no CRLF")
		self.failUnless(ParseLWS(LWS_TEST,10)==3,"LWS with CRLF")
		self.failUnless(ParseLWS(LWS_TEST,15)==3,"LWS ending at CRLF")
		self.failUnless(ParseLWS(LWS_TEST,15)==3,"LWS ending at CRLF")
		self.failUnless(ParseLWS(LWS_TEST,18)==4,"LWS ending at CR")
		# TEXT = <any OCTET except CTLs, but including LWS>
		self.failUnless(ParseTEXT(LWS_TEST,0)==22,"TEXT ending at CR")
		self.failUnless(UnfoldTEXT(LWS_TEST[:-2])=="Hi \t Hello Hi  ","Unfolded TEXT")
		# HEX = "A" | "B" | "C" | "D" | "E" | "F" | "a" | "b" | "c" | "d" | "e" | "f" | DIGIT		
		HEX="ABCDEFabcdef"+DIGIT
		for i in xrange(0,256):
			c=chr(i);self.failUnless(IsHEX(c)==(c in HEX),"IsHEX(chr(%i))"%i)
		# words, including comment, quoted string and qdpair
		WORD_TEST='Hi(Hi\r\n Hi)Hi<Hi>Hi@Hi,Hi;Hi:Hi\\Hi"\\"Hi\r\n Hi\\""/Hi[Hi]Hi?Hi=Hi{Hi}Hi Hi\tHi\r\n Hi'
		WORD_TESTRESULT=["Hi","(Hi Hi)","Hi","<","Hi",">","Hi","@","Hi",",","Hi",";","Hi",":","Hi","\\","Hi",
			'"\\"Hi Hi\\""',"/","Hi","[","Hi","]","Hi","?","Hi","=","Hi","{","Hi","}","Hi","Hi","Hi","Hi"]
		self.failUnless(SplitWords(UnfoldTEXT(WORD_TEST))==WORD_TESTRESULT,"SplitWords")
		# token
		try:
			CheckToken("Hi")
		except ValueError:
			self.fail("CheckToken('Hi')")
		for t in WORD_TESTRESULT:
			if t=="Hi":
				continue
			try:
				CheckToken(t)
				self.fail("Non token checked OK: %s"%t)
			except ValueError:
				pass
		# comment
	
	def testCaseParameter(self):
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;y=2;Zoo=";A=\\"Three\\""'),parameters,1)
		self.failUnless(nWords==12,"ParseParameters result: %i"%nWords)
		self.failUnless(parameters=={'x':['X','1'],'y':['y','2'],'zoo':['Zoo',';A="Three"']},"Paremters: %s"%repr(parameters))
		parameters={}
		try:
			nWords=ParseParameters(SplitWords('token ;X =1',ignoreSpace=False),parameters,1,ignoreAllSpace=False)
			self.fail("ParseParameters: ignoreSpace=False")
		except HTTPParameterError:
			pass
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;q=2;Zoo=";A=\\"Three\\""'),parameters,1,qMode="q")
		self.failUnless(nWords==4,"ParseParameters qMode result: %i"%nWords)
		self.failUnless(parameters=={'x':['X','1']},"Paremters: %s"%repr(parameters))
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;q=2;Zoo=";A=\\"Three\\""'),parameters,1+nWords)
		self.failUnless(nWords==8,"ParseParameters qMode result 2: %i"%nWords)
		self.failUnless(parameters=={'q':['q','2'],'zoo':['Zoo',';A="Three"']},"Paremters: %s"%repr(parameters))
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;y=2;Zoo=";A=\\"Three\\""'),parameters,1,caseSensitive=True)
		self.failUnless(nWords==12,"ParseParameters caseSensitive result: %i"%nWords)
		self.failUnless(parameters=={'X':['X','1'],'y':['y','2'],'Zoo':['Zoo',';A="Three"']},"Paremters: %s"%repr(parameters))
	
	def testCaseList(self):
		words=SplitWords(',hello, "Hi"(Hello), goodbye,  ')
		items=SplitItems(words,ignoreNulls=False)
		self.failUnless(items[0]==[],"Leading empty item")
		self.failUnless(items[1]==["hello"],"Token item")
		self.failUnless(items[2]==['"Hi"',"(Hello)"],"Complex item")
		self.failUnless(items[3]==['goodbye'],"Leading space item")
		self.failUnless(items[4]==[],"Trailing empty item")
	
	def testCaseVersion(self):
		v=HTTPVersion()
		self.failUnless(v.major==1 and v.minor==1,"1.1 on construction")
		self.failUnless(str(v)=="HTTP/1.1","Formatting")
		v=HTTPVersion(" HTTP / 1.0 ")
		self.failUnless(str(v)=="HTTP/1.0","Parse of 1.0")
		v1=HTTPVersion("HTTP/2.4")
		self.failUnless(v1.major==2 and v1.minor==4,"2.4")		
		v2=HTTPVersion("HTTP/2.13")
		v3=HTTPVersion("HTTP/12.3")
		self.failUnless(v1<v2,"2.4 < 2.13")
		self.failUnless(v2<v3,"2.13 < 12.3")
		self.failUnless(v1<v3,"2.4 < 12.3")
		v4=HTTPVersion("HTTP/02.004")
		self.failUnless(v4.major==2 and v4.minor==4,"2.4")		
		self.failUnless(v1==v4,"2.4 == 02.004")
					
	def testCaseFullDate(self):		
		timestamp822=FullDate()
		# RFC 822, updated by RFC 1123
		timestamp822.ParseWords(WordParser("Sun, 06 Nov 1994 08:49:37 GMT"))
		# RFC 850, obsoleted by RFC 1036
		timestamp850=FullDate("Sunday, 06-Nov-94 08:49:37 GMT")
		# ANSI C's asctime() format
		timestampC=FullDate()
		timestampC.ParseWords(WordParser("Sun Nov  6 08:49:37 1994"))
		self.failUnless(timestamp822==timestamp850,"RFC 850 timestamp parser")
		self.failUnless(timestamp822==timestampC,"ANSI C timestamp parser")
		self.failUnless(str(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT")
		self.failUnless(str(timestamp850)=="Sun, 06 Nov 1994 08:49:37 GMT")
		self.failUnless(str(timestampC)=="Sun, 06 Nov 1994 08:49:37 GMT")
		try:
			# Weekday mismatch
			timestamp822.ParseWords(WordParser("Mon, 06 Nov 1994 08:49:37 GMT"))
			self.fail("Weekday mismatch passed")
		except HTTPParameterError:
			pass
		timestamp822=FullDate("Sun, 06 Nov 1994 08:49:37 GMT")
		self.failUnless(str(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT","All-in-one parser")
	
	def testCaseTransferEncoding(self):
		te=TransferEncoding()
		self.failUnless(te.token=="chunked","Default not chunked")
		self.failUnless(len(te.parameters)==0,"Default has extension parameters")
		te.Parse("Extension ; x=1 ; y = 2")
		self.failUnless(te.token=="extension","Token not case insensitive")
		self.failUnless(len(te.parameters)==2,"No of extension parameters")
		self.failUnless(te.parameters=={'x':['x','1'],'y':['y','2']},"Extension parameters: %s"%repr(te.parameters))			
		self.failUnless(str(te)=="extension; x=1; y=2","te output")
		te.ParseWords(WordParser("bob; a=4"))
		self.failUnless(te.token=="bob","Token not case insensitive")
		self.failUnless(len(te.parameters)==1,"No of extension parameters")
		self.failUnless(te.parameters=={'a':['a','4']},"Single extension parameters: %s"%repr(te.parameters))			
		try:
			te.Parse("chunked ; x=1 ; y = 2")
			self.fail("chunked with spurious parameters")
		except HTTPParameterError:
			pass
		te.ParseWords(WordParser("chunked ; x=1 ; y = 2",ignoreSpace=False))
		self.failUnless(len(te.parameters)==0,"Overparsing of chunked with parameters")
		wp=WordParser("chunkie ; z = 3 ",ignoreSpace=False)
		te.ParseWords(wp)
		self.failUnless(wp.cWord==SP,"Wrong parsing of chunkie with parameters (trailing space)")		
		self.failUnless(te.parameters=={'z':['z','3']},"chunkie parameters")
		
	def testCaseMediaType(self):
		mtype=MediaType()
		try:
			mtype=MediaType(' application / octet-stream ')
			self.fail("Space between type and sub-type")
		except HTTPParameterError:
			pass
		try:
			mtype=MediaType(' application/octet-stream ')
		except HTTPParameterError:
			self.fail("No space between type and sub-type")
		try:
			mtype=MediaType(' application/octet-stream ; Charset = "en-US"')
			self.fail("Space between param and value")
		except HTTPParameterError:
			pass
		try:
			mtype=MediaType(' application/octet-stream ; Charset="en-US" ; x=1')
		except HTTPParameterError:
			self.fail("No space between param and value")
		self.failUnless(mtype.type=='application',"Media type")
		self.failUnless(mtype.subtype=='octet-stream',"Media sub-type")
		self.failUnless(mtype.parameters=={'charset':['Charset','en-US'],'x':['x','1']},"Media type parameters: %s"%repr(mtype.parameters))
		self.failUnless(str(mtype)=='application/octet-stream; Charset=en-US; x=1')
		
	def testCaseProductToken(self):
		ptoken=ProductToken()
		self.failUnless(ptoken.token is None)
		self.failUnless(ptoken.version is None)
		wp=WordParser('http/2616; x=1')
		ptoken.ParseWords(wp)
		self.failUnless(wp.cWord==";","ParseWords result: %s"%wp.cWord)
		self.failUnless(ptoken.token=="http","Product token")
		self.failUnless(ptoken.version=="2616","Product token version")
		try:
			ptoken=ProductToken('http/2616; x=1')
			self.fail("Spurious data test")
		except HTTPParameterError:
			pass
	
	def testCaseQValue(self):
		wp=WordParser('0.2 1.x x.1 1.001 0.14151')
		self.failUnless(str(wp.ParseQualityValue())=='0.2',"0.2")
		self.failUnless(wp.ParseQualityValue()==None,"1.x")
		wp.ParseToken()
		self.failUnless(wp.ParseQualityValue()==None,"x.1")
		wp.ParseToken()
		self.failUnless(wp.ParseQualityValue()==None,"1.001")
		wp.ParseToken()
		q=wp.ParseQualityValue()
		self.failUnless(str(q)=='0.142',"0.14151: %s"%str(q))
	
	def testCaseMediaRange(self):
		mr=MediaRange()
		self.failUnless(isinstance(mr,MediaType),"Special type of media-type")
		mr=MediaRange("*/*")
		self.failUnless(mr.type=="*","Main type")
		self.failUnless(mr.subtype=="*","subtype")
		self.failUnless(len(mr.parameters)==0,"Parameters")
		wp=WordParser("text/*;charset=utf-8; q=1.0")
		mr=MediaRange()
		mr.ParseWords(wp)
		self.failUnless(len(mr.parameters)==1,"q-value skipped parameters: %s"%repr(mr.parameters))
	
	def testCaseAcceptList(self):
		al=AcceptList()
		al=AcceptList("audio/*; q=0.2, audio/basic")
		self.failUnless(len(al)==2,"Length of AcceptList")
		self.failUnless(isinstance(al[0],AcceptItem),"AcceptList item type")
		self.failUnless(str(al[0].range)=="audio/basic",str(al[0].range))
		self.failUnless(al[0].q==1.0)
		self.failUnless(len(al[0].params)==0)
		self.failUnless(str(al[0])=="audio/basic","don't add 1 for defaults: %s"%str(al[0]))
		self.failUnless(str(al[1].range)=="audio/*")
		self.failUnless(al[1].q==0.2)
		self.failUnless(len(al[1].params)==0)
		self.failUnless(str(al[1])=="audio/*; q=0.2","add the q value")
		al=AcceptList("text/plain; q=0.5, text/html,  text/x-dvi; q=0.8, text/x-c")
		self.failUnless(len(al)==4,"Length of AcceptList")
		self.failUnless(str(al)=="text/html, text/plain; q=0.5, text/x-c, text/x-dvi; q=0.8",str(al))
		al=AcceptList("text/*, text/html, text/html;level=1, */*")
		self.failUnless(str(al)=="text/html; level=1, text/html, text/*, */*",str(al))
		mediaTypeList=[ MediaType("text/html;level=1"), MediaType("text/html"), MediaType("text/html;level=2"), MediaType("text/xhtml") ]
		bestType=al.SelectType(mediaTypeList)
		#	Accept: text/html; level=1, text/html, text/*, */*
		#	text/html;level=1	: q=1.0
		#	text/html			: q=1.0
		#	text/html;level=2	: q-1.0		partial match on text/html
		#	text/xhtml			: q=1.0		partial match on text/*
		self.failUnless(str(bestType)=="text/html; level=1",str(bestType)) # first in list
		al=AcceptList("text/*; q=1.0, text/html; q=0.5, text/html;level=1; q=0, */*")
		#	Accept: text/*; q=1.0, text/html; q=0.5, text/html;level=1; q=0, */*
		#	text/html;level=1	: q=0.0
		#	text/html			: q=0.5
		#	text/html;level=2	: q-0.5		partial match on text/html
		#	text/xhtml			: q=1.0		partial match on text/*
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/xhtml","Specific match with confusing q value: %s"%str(bestType))
		del mediaTypeList[3]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/html","beats level 2 only on order in list")
		del mediaTypeList[1]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/html; level=2","Partial level match beats exact rule deprecation")
		al=AcceptList("text/*;q=0.3, text/html;q=0.7, text/html;level=1,	text/html;level=2;q=0.4, */*;q=0.5 ")
		mediaTypeList=[ MediaType("text/html;level=1"), MediaType("text/html"), 
			MediaType("text/plain"), MediaType("image/jpeg"), MediaType("text/html;level=2"),
			MediaType("text/html;level=3") ]
		#	Accept: text/*;q=0.3, text/html;q=0.7, text/html;level=1, text/html;level=2;q=0.4, */*;q=0.5
		#	text/html;level=1	: q=1.0
		#	text/html			: q=0.7
		#	text/plain			: q=0.3
		#	image/jpeg			: q=0.5
		#	text/html;level=2	: q=0.4
		#	text/html;level=3	: q=0.7
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/html; level=1","Only exact match with q=1")
		del mediaTypeList[0]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/html","beats level=3 on order in list")
		del mediaTypeList[0]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/html; level=3","matches text/html")
		del mediaTypeList[-1]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="image/jpeg","matches */*, returned %s"%str(str(bestType)))
		del mediaTypeList[1]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/html; level=2","exact match with q=0.4")
		del mediaTypeList[1]
		bestType=al.SelectType(mediaTypeList)
		self.failUnless(str(bestType)=="text/plain","matches text/*")
		al=AcceptList("text/*, text/html, text/html;level=1, image/*; q=0, image/png; q=0.05")
		#	Accept: text/*, text/html, text/html;level=1, */*; q=0, image/*; q=0.05
		#	video/mpeg	: q=0.0
		#	image/png	: q=0.05		
		bestType=al.SelectType([MediaType('video/mpeg')])
		self.failUnless(bestType is None,"Unacceptable: %s"%str(bestType))
		bestType=al.SelectType([MediaType('image/png')])
		self.failUnless(str(bestType)=="image/png","Best partial match: %s"%str(bestType))
		
	def testCaseETag(self):
		eTag=HTTPETag()
		self.failIf(eTag.weak,"ETag constructor makes weak tags")
		self.failUnless(eTag.tag is None,"ETag constructor tag not None")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords('W/"hello"'),eTag)
		self.failUnless(nWords==3,"ParseETag result: %s"%nWords)
		self.failUnless(eTag.weak,"Failed to parse weak tag")
		self.failUnless(eTag.tag=="hello","Failed to parse ETag value")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords('w/ "h\\"ello"'),eTag)
		self.failUnless(nWords==3,"ParseETag result: %s"%nWords)
		self.failUnless(eTag.weak,"Failed to parse weak tag with lower case 'w'")
		self.failUnless(eTag.tag=='h"ello',"Failed to unpick quoted pair from ETag value")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords('"hello"'),eTag)
		self.failUnless(nWords==1,"ParseETag result: %s"%nWords)
		self.failIf(eTag.weak,"Failed to parse strong tag")
		self.failUnless(eTag.tag=="hello","Failed to parse ETag value")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords(u'"hello"'),eTag)
		self.failUnless(nWords==1,"ParseETag result: %s"%nWords)
		self.failIf(eTag.weak,"Failed to parse strong tag")
		self.failUnless(eTag.tag=="hello","Failed to parse ETag value")

	def testCaseRelativeQualityToken(self):
		rqTokens=[]
		rqToken=HTTPRelativeQualityToken()
		self.failUnless(rqToken.token=="*" and rqToken.q is None,"HTTPRelativeQualityToken constructor")
		self.failUnless(str(rqToken)=="*","HTTPRelativeQualityToken Format default")
		rqToken=HTTPRelativeQualityToken("gzip",0.5)
		self.failUnless(str(rqToken)=="gzip;q=0.5","HTTPRelativeQualityToken custom constructor Format default")
		for item in SplitItems(SplitWords(" gzip;q=1.0, identity; q=0.5, *;q=0")):
			rqToken=HTTPRelativeQualityToken()
			nWords=ParseRelativeQualityToken(item,rqToken)
			rqTokens.append(rqToken)
		self.failUnless(rqTokens[0].token=='gzip' and rqTokens[0].q==1.0,
			"Parse accept encodings: gzip;q=1.0")
		self.failUnless(str(rqTokens[0])=="gzip;q=1.0","Format accept encodings: gzip;q=1.0")
		self.failUnless(rqTokens[1].token=='identity' and rqTokens[1].q==0.5,
			"Accept encodings identity;q=0.5")
		self.failUnless(str(rqTokens[1])=="identity;q=0.5","Format accept encodings: identity;q=0.5")
		self.failUnless(rqTokens[2].token=='*' and rqTokens[2].q==0,
			"Accept encodings *;q=0")
		self.failUnless(str(rqTokens[2])=="*;q=0","Format accept encodings: *;q=0")
		# The next loop checks we are over-writing quality OK if left blank
		i=0
		for item in SplitItems(SplitWords(" compress, gzip")):
			nWords=ParseRelativeQualityToken(item,rqTokens[i])
			i=i+1
		self.failUnless(rqTokens[0].token=='compress' and rqTokens[0].q is None and str(rqTokens[0])=="compress",
			"Accept encodings compress")
		self.failUnless(rqTokens[1].token=='gzip' and rqTokens[1].q is None and str(rqTokens[1])=="gzip",
			"Accept encodings gzip")
		# Final tests check bad values for q
		rqToken=HTTPRelativeQualityToken()
		ParseRelativeQualityToken(SplitWords("x;q=-2.3"),rqToken)
		self.failUnless(rqToken.q==0,"Negative q value")
		ParseRelativeQualityToken(SplitWords("x;q=2.3"),rqToken)
		self.failUnless(rqToken.q==1.0,"Large q value")		
		
		
	def testCaseDate(self):
		timestamp822=ParseDate("Sun, 06 Nov 1994 08:49:37 GMT")	# RFC 822, updated by RFC 1123
		timestamp850=ParseDate("Sunday, 06-Nov-94 08:49:37 GMT")  # RFC 850, obsoleted by RFC 1036
		timestampC=ParseDate("Sun Nov  6 08:49:37 1994")		# ANSI C's asctime() format
		self.failUnless(timestamp822==timestamp850,"RFC 850 timestamp parser")
		self.failUnless(timestamp822==timestampC,"ANSI C timestamp parser")
		self.failUnless(FormatDate(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT")
		try:
			timestamp822=ParseDate("Mon, 06 Nov 1994 08:49:37 GMT")	# Weekday mismatch
			self.fail("Weekday mismatch passed")
		except ValueError:
			pass
		self.failUnless(FormatDate(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT")
			
	def testCaseHeaders(self):
		message=HTTPRequest("http://www.google.com/")
		message.SetHeader("x-test","Hello")
		message.SetContentLength(3)
		mtype=MediaType()
		mtype.type='application'
		mtype.subtype='octet-stream'
		mtype.parameters['charset']=['charset','utf8']
		message.SetContentType(mtype)
		
	def testCaseManager(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		request1=HTTPRequest("http://www.domain1.com/")
		self.failUnless(request1.method=="GET")
		request2=HTTPRequest("http://www.domain2.com/","HEAD")
		self.failUnless(request2.method=="HEAD")
		rm.QueueRequest(request1)
		rm.QueueRequest(request2)
		# ManagerLoop will process the queue until it blocks for more than the timeout (default, 60s)
		rm.ManagerLoop()
		response1=request1.response
		self.failUnless(response1.protocolVersion=="HTTP/1.1","Protocol in response1: %s"%response1.protocolVersion)
		self.failUnless(response1.status==200,"Status in response1: %i"%response1.status)
		self.failUnless(response1.reason=="You got it!","Reason in response1: %s"%response1.reason)
		self.failUnless(request1.resBody==TEST_STRING,"Data in response1: %s"%request1.resBody)		
		response2=request2.response
		self.failUnless(response2.protocolVersion=="HTTP/1.1","Protocol in response2: %s"%response2.protocolVersion)
		self.failUnless(response2.status==200,"Status in response2: %i"%response2.status)
		self.failUnless(response2.reason=="You got it!","Reason in response2: %s"%response2.reason)
		self.failUnless(request2.resBody=="","Data in response2: %s"%request2.resBody)
		
	def testCaseContinue(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		request1=HTTPRequest("http://www.domain1.com/file","PUT","123456\r\n\r\n")
		self.failUnless(request1.method=="PUT")
		request2=HTTPRequest("http://www.domain1.com/file2","PUT","123456\r\n\r\n")
		request2.SetExpectContinue()
		rm.QueueRequest(request1)
		rm.QueueRequest(request2)
		# ManagerLoop will process the queue until it blocks for more than the timeout (default, forever) 
		#import pdb
		#pdb.set_trace()
		rm.ManagerLoop()
		response1=request1.response
		self.failUnless(response1.status==200,"Status in response1: %i"%response1.status)
		self.failUnless(response1.reason=="OK","Reason in response1: %s"%response1.reason)
		self.failUnless(request1.resBody=='',"Data in response1: %s"%request1.resBody)		
		response2=request2.response
		self.failUnless(response2.status==200,"Status in response2: %i"%response2.status)
		self.failUnless(response2.reason=="OK","Reason in response2: %s"%response2.reason)
		self.failUnless(request2.resBody=="","Data in response2: %s"%request2.resBody)
		# How do we test that response2 held back from sending the data before the redirect?

	def testCaseStreamedPut(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		request=HTTPRequest("http://www.domain1.com/file2","PUT",StringIO.StringIO("123456\r\n\r\n"))
		request.SetExpectContinue()
		rm.ProcessRequest(request)
		response=request.response
		self.failUnless(response.status==200,"Status in response: %i"%response.status)
		self.failUnless(response.reason=="OK","Reason in response: %s"%response.reason)
		self.failUnless(request.resBody=="","Data in response: %s"%request.resBody)
		request=HTTPRequest("http://www.domain1.com/file","PUT",StringIO.StringIO("123456\r\n\r\n"))
		request.SetContentLength(10)
		rm.ProcessRequest(request)
		response=request.response
		self.failUnless(response.status==200,"Status in response: %i"%response.status)
		self.failUnless(response.reason=="OK","Reason in response: %s"%response.reason)
		self.failUnless(request.resBody=="","Data in response: %s"%request.resBody)
		
	def testCaseStreamedGet(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		buff=StringIO.StringIO()
		request=HTTPRequest("http://www.domain1.com/","GET",'',buff)
		rm.ProcessRequest(request)
		response=request.response
		self.failUnless(response.status==200,"Status in response: %i"%response.status)
		self.failUnless(buff.getvalue()==TEST_STRING,"Data in response: %s"%request.resBody)		
		self.failUnless(request.resBody=="","Data in streamed response: %s"%request.resBody)
			

if __name__ == '__main__':
	unittest.main()
