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

class FakeHTTPRequestManager(HTTPRequestManager):
	def __init__(self):
		HTTPRequestManager.__init__(self)
		self.socketSelect=self.select
		#self.SetLog(HTTP_LOG_ALL)
		
	def NewConnection(self,scheme,server,port):
		if scheme=='http':
			return FakeHTTPConnection(self,server,port)
		else:
			raise ValueError

	def select(self,readers,writers,errors,timeout):
		r=[]
		for reader in readers:
			if reader.CanRead():
				r.append(reader)
		return r,writers,errors
			

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
	
	def testCaseList(self):
		words=SplitWords(',hello, "Hi"(Hello), goodbye,  ')
		items=SplitItems(words)
		self.failUnless(items[0]==[],"Leading empty item")
		self.failUnless(items[1]==["hello"],"Token item")
		self.failUnless(items[2]==['"Hi"',"(Hello)"],"Complex item")
		self.failUnless(items[3]==['goodbye'],"Leading space item")
		self.failUnless(items[4]==[],"Trailing empty item")
		
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

	def testCaseMediaType(self):
		mtype=HTTPMediaType()
		nWords=ParseMediaType(SplitWords('application / octet-stream; Charset="en-US"'),mtype)
		self.failUnless(nWords==7,"ParseMediaType result: %s"%nWords)
		self.failUnless(mtype.type=='application',"Media type")
		self.failUnless(mtype.subtype=='octet-stream',"Media sub-type")
		self.failUnless(mtype.parameters=={'charset':['Charset','en-US']},"Media type parameters")
		self.failUnless(str(mtype)=='application/octet-stream; Charset=en-US')
		
	def testCaseProductToken(self):
		ptoken=HTTPProductToken()
		nWords=ParseProductToken(SplitWords('http/2616; x=1'),ptoken)
		self.failUnless(nWords==3,"ParseProductToken result: %s"%nWords)
		self.failUnless(ptoken.token=="http","Product token")
		self.failUnless(ptoken.version=="2616","Product token version")
	
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
	
	def testCaseVersion(self):
		self.failUnless(CanonicalVersion("http/00004.00002")=="HTTP/4.2","Leading zeros in version")
		try:
			CanonicalVersion("https/1.0")
			self.fail("HTTP protocol name") 
		except HTTP2616Exception,e:
			pass
		try:
			CanonicalVersion("http 1.1")
			self.fail("HTTP protocol name/version separator") 
		except HTTP2616Exception,e:
			pass
		try:
			CanonicalVersion("http/1")
			self.fail("HTTP protocol version form") 
		except HTTP2616Exception,e:
			pass
			
	def testCaseHeaders(self):
		message=HTTPRequest("http://www.google.com/")
		message.SetHeader("x-test","Hello")
		message.SetContentLength(3)
		mtype=HTTPMediaType()
		mtype.type='application'
		mtype.subtype='octet-stream'
		mtype.parameters['charset']='utf8'
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
	main()
