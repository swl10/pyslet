#! /usr/bin/env python

import unittest, logging
import StringIO
import socket

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(HTTP2616Tests,'test'),
		unittest.makeSuite(GenericParserTests,'test'),
		unittest.makeSuite(ProtocolParameterTests,'test'),
		unittest.makeSuite(HeaderTests,'test'),
		unittest.makeSuite(ChunkedTests,'test')
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
		logging.info("Opening connection to %s...",self.host)
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
			logging.debug("sending: %s",repr(data[:nBytes]))
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
				logging.debug("%s handling request: \n%s",self.host,data)
				response=self.responseTable.get(data,BAD_REQUEST)
				# add this response to the recv buffer
				if response==BAD_REQUEST:
					logging.debug("** Bad Request")
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
			logging.debug("receiving %i bytes: %s",nBytes,repr(data))
			return data
		else:
			logging.debug("receiving: empty string")
			return ''

	def shutdown(self,mode):
		# Nothing to do
		pass
	
	def close(self):
		logging.info("Closing connection to %s...",self.host)
		self.socketSendBuffer=None
		self.socketRecvBuffer=None
		

class FakeHTTPRequestManager(HTTPRequestManager):

	FakeHTTPConnectionClass=FakeHTTPConnection

	def __init__(self):
		HTTPRequestManager.__init__(self)
		self.socketSelect=self.select
		
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
			
class GenericParserTests(unittest.TestCase):
	
	def testCaseBasic(self):
		# OCTET = <any 8-bit sequence of data>
		for c in xrange(0,256):
			self.assertTrue(IsOCTET(chr(c)),"IsOCTET(chr(%i))"%c)
		# CHAR = <any US-ASCII character (octets 0 - 127)>
		for c in xrange(0,128):
			self.assertTrue(IsCHAR(chr(c)),"IsCHAR(chr(%i))"%c)
		for c in xrange(128,256):
			self.assertFalse(IsCHAR(chr(c)),"IsCHAR(chr(%i))"%c)
		# UPALPHA = <any US-ASCII uppercase letter "A".."Z">
		UPALPHA="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsUPALPHA(c)==(c in UPALPHA),"IsUPALPHA(chr(%i))"%i)
		# LOALPHA = <any US-ASCII lowercase letter "a".."z">
		LOALPHA="abcdefghijklmnopqrstuvwxyz"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsLOALPHA(c)==(c in LOALPHA),"IsLOALPHA(chr(%i))"%i)
		# ALPHA = UPALPHA | LOALPHA
		ALPHA=UPALPHA+LOALPHA
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsALPHA(c)==(c in ALPHA),"IsALPHA(chr(%i))"%i)
		# DIGIT  = <any US-ASCII digit "0".."9">
		DIGIT="0123456789"
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsDIGIT(c)==(c in DIGIT),"IsDIGIT(chr(%i))"%i)
		# CTL = <any US-ASCII control character (octets 0 - 31) and DEL (127)>
		CTL=string.join(map(chr,xrange(0,32))+[chr(127)],'')
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsCTL(c)==(c in CTL),"IsCTL(chr(%i))"%i)
		# CR = <US-ASCII CR, carriage return (13)>
		self.assertTrue(CR==chr(13),"CR")
		# LF = <US-ASCII LF, linefeed (10)>
		self.assertTrue(LF==chr(10),"LF")
		# SP = <US-ASCII SP, space (32)>
		self.assertTrue(SP==chr(32),"SP")
		# HT = <US-ASCII HT, horizontal-tab (9)>
		self.assertTrue(HT==chr(9),"HT")
		# DQUOTE = <US-ASCII double-quote mark (34)>
		self.assertTrue(DQUOTE==chr(34),"DQUOTE")
		# CRLF
		self.assertTrue(CRLF==CR+LF,"CRLF")
		# LWS = [CRLF] 1*( SP | HT )
		LWS_TEST="; \t ;\r\n ;\r\n \r\n\t \r "
		p=HTTPParser(LWS_TEST)
		self.assertTrue(p.ParseLWS() is None,"No LWS")
		p.Parse(";")		
		self.assertTrue(p.ParseLWS()==" \t ","LWS no CRLF")
		p.Parse(";")		
		self.assertTrue(p.ParseLWS()=="\r\n ","LWS with CRLF")
		p.Parse(";")		
		self.assertTrue(p.ParseLWS()=="\r\n ","LWS ending at CRLF")
		self.assertTrue(p.ParseLWS()=="\r\n\t ","LWS ending at CRLF")
		# TEXT = <any OCTET except CTLs, but including LWS>
		p=HTTPParser(LWS_TEST)
		self.assertTrue(len(p.ParseTEXT())==16,"TEXT ending at CR")
		p=HTTPParser(LWS_TEST)
		self.assertTrue(p.ParseTEXT(True)=="; \t ; ;  ","Unfolded TEXT")
		# HEX = "A" | "B" | "C" | "D" | "E" | "F" | "a" | "b" | "c" | "d" | "e" | "f" | DIGIT		
		HEX="ABCDEFabcdef"+DIGIT
		for i in xrange(0,256):
			c=chr(i);self.assertTrue(IsHEX(c)==(c in HEX),"IsHEX(chr(%i))"%i)
		# words, including comment, quoted string and qdpair
		WORD_TEST='Hi(Hi\r\n Hi)Hi<Hi>Hi@Hi,Hi;Hi:Hi\\Hi"\\"Hi\r\n Hi\\""/Hi[Hi]Hi?Hi=Hi{Hi}Hi Hi\tHi\r\n Hi'
		WORD_TESTRESULT=["Hi","(Hi Hi)","Hi","<","Hi",">","Hi","@","Hi",",","Hi",";","Hi",":","Hi","\\","Hi",
			'"\\"Hi Hi\\""',"/","Hi","[","Hi","]","Hi","?","Hi","=","Hi","{","Hi","}","Hi","Hi","Hi","Hi"]
		p=HTTPParser(WORD_TEST)
		self.assertTrue(SplitWords(p.ParseTEXT(True))==WORD_TESTRESULT,"SplitWords")
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
	
	def testCaseToken(self):
		p=WordParser(" a ")
		self.assertTrue(p.cWord,"Expected a word")
		self.assertTrue(p.IsToken(),"Expected a token")
		self.assertTrue(p.ParseToken()=="a","Expected 'a'")
		self.assertFalse(p.cWord,"Expected no more words")
		self.assertFalse(p.IsToken(),"Expected no token")

	def testCaseTokenList(self):
		p=WordParser(" a ")
		self.assertTrue(p.ParseTokenList()==["a"],"Expected ['a']")
		self.assertFalse(p.cWord,"Expected no more words")
		self.assertFalse(p.IsToken(),"Expected no token")
		p=WordParser(" a , b,c ,d,,efg")
		self.assertTrue(p.ParseTokenList()==["a","b","c","d","efg"],"Bad token list")
		self.assertFalse(p.cWord,"Expected no more words")
		self.assertFalse(p.IsToken(),"Expected no token")


class ProtocolParameterTests(unittest.TestCase):

	def testCaseVersion(self):
		v=HTTPVersion()
		self.assertTrue(v.major==1 and v.minor==1,"1.1 on construction")
		self.assertTrue(str(v)=="HTTP/1.1","Formatting")
		v=HTTPVersion(1)
		self.assertTrue(v.major==1 and v.minor==1,"1.1 on construction")
		v=HTTPVersion(2)
		self.assertTrue(v.major==2 and v.minor==0,"2.0 on construction")
		v=HTTPVersion(2,1)
		self.assertTrue(v.major==2 and v.minor==1,"2.1 on construction")
		v=HTTPVersion.FromString(" HTTP / 1.0 ")
		self.assertTrue(str(v)=="HTTP/1.0","Parse of 1.0")
		v1=HTTPVersion.FromString("HTTP/2.4")
		self.assertTrue(v1.major==2 and v1.minor==4,"2.4")		
		v2=HTTPVersion.FromString("HTTP/2.13")
		v3=HTTPVersion.FromString("HTTP/12.3")
		self.assertTrue(v1<v2,"2.4 < 2.13")
		self.assertTrue(v2<v3,"2.13 < 12.3")
		self.assertTrue(v1<v3,"2.4 < 12.3")
		v4=HTTPVersion.FromString("HTTP/02.004")
		self.assertTrue(v4.major==2 and v4.minor==4,"2.4")		
		self.assertTrue(v1==v4,"2.4 == 02.004")
	
	def testCaseURL(self):
		v1=HTTPURL("http://abc.com:80/~smith/home.html")
		v2=HTTPURL("http://ABC.com/%7Esmith/home.html")
		v3=HTTPURL("http://ABC.com:/%7esmith/home.html")
		self.assertTrue(v1.Match(v2))
		self.assertTrue(v1.Match(v3))
		self.assertTrue(v2.Match(v3))

	def testCaseFullDate(self):		
		# RFC 822, updated by RFC 1123
		timestamp822=FullDate.FromHTTPString("Sun, 06 Nov 1994 08:49:37 GMT")
		# RFC 850, obsoleted by RFC 1036
		timestamp850=FullDate.FromHTTPString("Sunday, 06-Nov-94 08:49:37 GMT")
		# ANSI C's asctime() format
		timestampC=FullDate.FromHTTPString("Sun Nov  6 08:49:37 1994")
		self.assertTrue(timestamp822==timestamp850,"RFC 850 timestamp parser")
		self.assertTrue(timestamp822==timestampC,"ANSI C timestamp parser")
		self.assertTrue(str(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT")
		self.assertTrue(str(timestamp850)=="Sun, 06 Nov 1994 08:49:37 GMT")
		self.assertTrue(str(timestampC)=="Sun, 06 Nov 1994 08:49:37 GMT")
		try:
			# Weekday mismatch
			timestamp822=FullDate.FromHTTPString("Mon, 06 Nov 1994 08:49:37 GMT")
			self.fail("Weekday mismatch passed")
		except SyntaxError:
			pass
		timestamp822=FullDate.FromHTTPString("Sun, 06 Nov 1994 08:49:37 GMT")
		self.assertTrue(str(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT","All-in-one parser")
	
	def testCaseTransferEncoding(self):
		te=TransferEncoding()
		self.assertTrue(te.token=="chunked","Default not chunked")
		self.assertTrue(len(te.parameters)==0,"Default has extension parameters")
		te=TransferEncoding.FromString("Extension ; x=1 ; y = 2")
		self.assertTrue(te.token=="extension","Token not case insensitive")
		self.assertTrue(len(te.parameters)==2,"No of extension parameters")
		self.assertTrue(te.parameters=={'x':['x','1'],'y':['y','2']},"Extension parameters: %s"%repr(te.parameters))			
		self.assertTrue(str(te)=="extension; x=1; y=2","te output")
		te=TransferEncoding.FromString("bob; a=4")
		self.assertTrue(te.token=="bob","Token not case insensitive")
		self.assertTrue(len(te.parameters)==1,"No of extension parameters")
		self.assertTrue(te.parameters=={'a':['a','4']},"Single extension parameters: %s"%repr(te.parameters))			
		try:
			te=TransferEncoding.FromString("chunked ; x=1 ; y = 2")
			self.fail("chunked with spurious parameters")
		except SyntaxError:
			pass
		parameters={}
		ParameterParser("; x=1 ; y = 2").ParseParameters(parameters)
		te=TransferEncoding("chunked",parameters)
		self.assertTrue(len(te.parameters)==0,"Overparsing of chunked with parameters")
		te=TransferEncoding.FromString("chunkie ; z = 3 ")
		self.assertTrue(te.parameters=={'z':['z','3']},"chunkie parameters")
								
	def testCaseMediaType(self):
		mtype=MediaType()
		try:
			mtype=MediaType.FromString(' application / octet-stream ')
			self.fail("Space between type and sub-type")
		except SyntaxError:
			pass
		try:
			mtype=MediaType.FromString(' application/octet-stream ')
		except SyntaxError:
			self.fail("No space between type and sub-type")
		try:
			mtype=MediaType.FromString(' application/octet-stream ; Charset = "en-US"')
			self.fail("Space between param and value")
		except SyntaxError:
			pass
		try:
			mtype=MediaType.FromString(' application/octet-stream ; Charset="en-US" ; x=1')
		except SyntaxError:
			self.fail("No space between param and value")
		self.assertTrue(mtype.type=='application',"Media type")
		self.assertTrue(mtype.subtype=='octet-stream',"Media sub-type")
		self.assertTrue(mtype.parameters=={'charset':['Charset','en-US'],'x':['x','1']},"Media type parameters: %s"%repr(mtype.parameters))
		self.assertTrue(str(mtype)=='application/octet-stream; Charset=en-US; x=1')
		
	def testCaseProductToken(self):
		ptoken=ProductToken()
		self.assertTrue(ptoken.token is None)
		self.assertTrue(ptoken.version is None)
		p=ParameterParser('http/2616; x=1')
		ptoken=p.ParseProduction(p.RequireProductToken)
		self.assertTrue(p.cWord==";","ParseProductToken result: %s"%p.cWord)
		self.assertTrue(ptoken.token=="http","Product token")
		self.assertTrue(ptoken.version=="2616","Product token version")
		try:
			ptoken=ProductToken.FromString('http/2616; x=1')
			self.fail("Spurious data test")
		except SyntaxError:
			pass
		ptokens=ProductToken.ListFromString("CERN-LineMode/2.15 libwww/2.17b3")
		self.assertTrue(len(ptokens)==2)
		self.assertTrue(ptokens[0].version=="2.15")
		self.assertTrue(ptokens[1].version=="2.17b3")
		self.assertTrue(ProductToken.Explode("2.17b3")==((2,),(17,"b",3)),"Complex explode: %s"%repr(ProductToken.Explode("2.17b3")))
		self.assertTrue(ProductToken.Explode("2.b3")==((2,),(-1,"b",3)))
		self.assertTrue(ProductToken.Explode(".b3")==((),(-1,"b",3)))
		self.assertTrue(ProductToken("Apache","0.8.4")<ProductToken("Apache","0.8.30"))
		self.assertTrue(ProductToken("Apache","0.8.200")>ProductToken("Apache","0.8.30"))
		self.assertTrue(ProductToken("Apache","0.8.4")==ProductToken("Apache","0.8.04"))
		self.assertTrue(ProductToken("Apache","0.8.4")>ProductToken("Apache","0.8b1.4"))
		self.assertTrue(ProductToken("Apache","1b4.8.4")>ProductToken("Apache","0.8.4"))
       	
	def testCaseQValue(self):
		wp=ParameterParser('0.2 1.x x.1 1.001 0.14151')
		self.assertTrue(str(wp.ParseQualityValue())=='0.2',"0.2")
		self.assertTrue(wp.ParseQualityValue()==None,"1.x")
		wp.ParseToken()
		self.assertTrue(wp.ParseQualityValue()==None,"x.1")
		wp.ParseToken()
		self.assertTrue(wp.ParseQualityValue()==1.0,"1.001")
		q=wp.ParseQualityValue()
		self.assertTrue(str(q)=='0.142',"0.14151: %s"%str(q))
	
	def testCaseLanguageTag(self):
		lang=LanguageTag("EN")
		self.assertTrue(lang.primary=='EN',"Primary tag")
		self.assertTrue(len(lang.subtags)==0,"Sub-tags")
		self.assertTrue(str(lang)=="EN")
		lang=LanguageTag("x","pig","latin")
		self.assertTrue(lang.primary=='x',"Primary tag")
		self.assertTrue(len(lang.subtags)==2,"Sub-tags")	
		self.assertTrue(str(lang)=="x-pig-latin")
		try:
			# White space is not allowed within the tag
			lang=LanguageTag.FromString(' en - us ')
			self.fail("Space between primary tag and sub-tags")
		except SyntaxError:
			pass
		try:
			lang=LanguageTag.FromString(' en-us ')
		except SyntaxError:
			self.fail("No space between primary tag and sub-tags")
		lang=LanguageTag.FromString('en-US')
		self.assertTrue(lang.primary=='en',"Primary tag")
		self.assertTrue(lang.subtags==('US',),"Sub-tags: %s"%repr(lang.subtags))
		self.assertTrue(str(lang)=='en-US')
		# all tags are case-insensitive
		self.assertTrue(lang=="en-US","Naked string comparison")
		self.assertTrue(lang==LanguageTag.FromString('en-us'),"case insensitive comparison")
		for langStr in ["en", "en-US", "en-cockney", "i-cherokee", "x-pig-latin"]:
			lang=LanguageTag.FromString(langStr)
		# test for case-insensitive ordering
		self.assertTrue(LanguageTag.FromString("en-US")>LanguageTag.FromString("en-gb"),"case insensitive order")
		# test for hash
		self.assertTrue(hash(LanguageTag.FromString("en-us"))==hash(LanguageTag.FromString("en-US")),"case insensitive hash")
		
	def testCaseRelativeQualityToken(self):
		rqTokens=[]
		rqToken=RelativeQualityToken()
		self.assertTrue(rqToken.token=="*" and rqToken.q is None,"RelativeQualityToken constructor")
		self.assertTrue(str(rqToken)=="*","RelativeQualityToken Format default")
		rqToken=RelativeQualityToken("gzip",0.5)
		self.assertTrue(str(rqToken)=="gzip;q=0.5","RelativeQualityToken custom constructor Format default")
		rqTokens=RelativeQualityToken.ListFromString(" gzip;q=1.0, identity; q=0.5, *;q=0")
		self.assertTrue(rqTokens[0].token=='gzip' and rqTokens[0].q==1.0,
			"Parse accept encodings: gzip;q=1.0")
		self.assertTrue(str(rqTokens[0])=="gzip;q=1.0","Format accept encodings: gzip;q=1.0")
		self.assertTrue(rqTokens[1].token=='identity' and rqTokens[1].q==0.5,
			"Accept encodings identity;q=0.5")
		self.assertTrue(str(rqTokens[1])=="identity;q=0.5","Format accept encodings: identity;q=0.5")
		self.assertTrue(rqTokens[2].token=='*' and rqTokens[2].q==0,
			"Accept encodings *;q=0")
		self.assertTrue(str(rqTokens[2])=="*;q=0","Format accept encodings: *;q=0")
		# The next loop checks we are over-writing quality OK if left blank
		rqTokens[0].ParseWords(WordParser(" compress"))
		self.assertTrue(rqTokens[0].token=='compress' and rqTokens[0].q is None and str(rqTokens[0])=="compress",
			"Accept encodings compress")
		rqTokens[1].ParseWords(WordParser("gzip"))
		self.assertTrue(rqTokens[1].token=='gzip' and rqTokens[1].q is None and str(rqTokens[1])=="gzip",
			"Accept encodings gzip")
		# Final tests check bad values for q
		rqToken=RelativeQualityToken.ListFromString("x;q=1.3")[0]
		self.assertTrue(rqToken.q==1.0,"Large q value")

				
class HeaderTests(unittest.TestCase):

	def testCaseMediaRange(self):
		mr=MediaRange()
		self.assertTrue(isinstance(mr,MediaType),"Special type of media-type")
		self.assertTrue(str(mr)=="*/*")
		mr=MediaRange.FromString("*/*")
		self.assertTrue(mr.type=="*","Main type")
		self.assertTrue(mr.subtype=="*","subtype")
		self.assertTrue(len(mr.parameters)==0,"Parameters")
		p=HeaderParser("text/*;charset=utf-8; q=1.0; x=5")
		mr=MediaRange()
		mr=p.ParseMediaRange()
		self.assertTrue(len(mr.parameters)==1,"q-value terminates parameters: %s"%repr(mr.parameters))
		# check comparisons
		self.assertTrue(MediaRange.FromString("image/*")<MediaRange.FromString("*/*"),"Specific over general */*")
		self.assertTrue(MediaRange.FromString("image/png")<MediaRange.FromString("image/*"),"Specific over general image/*")
		self.assertTrue(MediaRange.FromString("text/plain;charset=utf-8")<MediaRange.FromString("text/plain"),"Parameter over no-parameter")

	def testCaseAcceptList(self):
		al=AcceptList()
		self.assertTrue(len(al)==0)
		al=AcceptList.FromString("audio/*; q=0.2, audio/basic")
		self.assertTrue(len(al)==2,"Length of AcceptList")
		self.assertTrue(isinstance(al[0],AcceptItem),"AcceptList item type")
		self.assertTrue(str(al[0].range)=="audio/basic",str(al[0].range))
		self.assertTrue(al[0].q==1.0)
		self.assertTrue(len(al[0].params)==0)
		self.assertTrue(str(al[0])=="audio/basic","don't add 1 for defaults: %s"%str(al[0]))
		self.assertTrue(str(al[1].range)=="audio/*")
		self.assertTrue(al[1].q==0.2)
		self.assertTrue(len(al[1].params)==0)
		self.assertTrue(str(al[1])=="audio/*; q=0.2","add the q value")
		al=AcceptList.FromString("text/plain; q=0.5, text/html,  text/x-dvi; q=0.8, text/x-c")
		self.assertTrue(len(al)==4,"Length of AcceptList")
		self.assertTrue(str(al)=="text/html, text/plain; q=0.5, text/x-c, text/x-dvi; q=0.8",str(al))
		al=AcceptList.FromString("text/*, text/html, text/html;level=1, */*")
		self.assertTrue(str(al)=="text/html; level=1, text/html, text/*, */*",str(al))
		mediaTypeList=[ MediaType.FromString("text/html;level=1"), MediaType.FromString("text/html"), MediaType.FromString("text/html;level=2"), MediaType.FromString("text/xhtml") ]
		bestType=al.SelectType(mediaTypeList)
		#	Accept: text/html; level=1, text/html, text/*, */*
		#	text/html;level=1	: q=1.0
		#	text/html			: q=1.0
		#	text/html;level=2	: q-1.0		partial match on text/html
		#	text/xhtml			: q=1.0		partial match on text/*
		self.assertTrue(str(bestType)=="text/html; level=1",str(bestType)) # first in list
		al=AcceptList.FromString("text/*; q=1.0, text/html; q=0.5, text/html;level=1; q=0, */*")
		#	Accept: text/*; q=1.0, text/html; q=0.5, text/html;level=1; q=0, */*
		#	text/html;level=1	: q=0.0
		#	text/html			: q=0.5
		#	text/html;level=2	: q-0.5		partial match on text/html
		#	text/xhtml			: q=1.0		partial match on text/*
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/xhtml","Specific match with confusing q value: %s"%str(bestType))
		del mediaTypeList[3]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/html","beats level 2 only on order in list")
		del mediaTypeList[1]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/html; level=2","Partial level match beats exact rule deprecation")
		al=AcceptList.FromString("text/*;q=0.3, text/html;q=0.7, text/html;level=1,	text/html;level=2;q=0.4, */*;q=0.5 ")
		mediaTypeList=[ MediaType.FromString("text/html;level=1"), MediaType.FromString("text/html"), 
			MediaType.FromString("text/plain"), MediaType.FromString("image/jpeg"), MediaType.FromString("text/html;level=2"),
			MediaType.FromString("text/html;level=3") ]
		#	Accept: text/*;q=0.3, text/html;q=0.7, text/html;level=1, text/html;level=2;q=0.4, */*;q=0.5
		#	text/html;level=1	: q=1.0
		#	text/html			: q=0.7
		#	text/plain			: q=0.3
		#	image/jpeg			: q=0.5
		#	text/html;level=2	: q=0.4
		#	text/html;level=3	: q=0.7
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/html; level=1","Only exact match with q=1")
		del mediaTypeList[0]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/html","beats level=3 on order in list")
		del mediaTypeList[0]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/html; level=3","matches text/html")
		del mediaTypeList[-1]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="image/jpeg","matches */*, returned %s"%str(str(bestType)))
		del mediaTypeList[1]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/html; level=2","exact match with q=0.4")
		del mediaTypeList[1]
		bestType=al.SelectType(mediaTypeList)
		self.assertTrue(str(bestType)=="text/plain","matches text/*")
		al=AcceptList.FromString("text/*, text/html, text/html;level=1, image/*; q=0, image/png; q=0.05")
		#	Accept: text/*, text/html, text/html;level=1, */*; q=0, image/*; q=0.05
		#	video/mpeg	: q=0.0
		#	image/png	: q=0.05		
		bestType=al.SelectType([MediaType.FromString('video/mpeg')])
		self.assertTrue(bestType is None,"Unacceptable: %s"%str(bestType))
		bestType=al.SelectType([MediaType.FromString('image/png')])
		self.assertTrue(str(bestType)=="image/png","Best partial match: %s"%str(bestType))
		

class HTTP2616Tests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		
	def tearDown(self):
		os.chdir(self.cwd)
	
	def testCaseParameter(self):
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;y=2;Zoo=";A=\\"Three\\""'),parameters,1)
		self.assertTrue(nWords==12,"ParseParameters result: %i"%nWords)
		self.assertTrue(parameters=={'x':['X','1'],'y':['y','2'],'zoo':['Zoo',';A="Three"']},"Paremters: %s"%repr(parameters))
		parameters={}
		try:
			nWords=ParseParameters(SplitWords('token ;X =1',ignoreSpace=False),parameters,1,ignoreAllSpace=False)
			self.fail("ParseParameters: ignoreSpace=False")
		except SyntaxError:
			pass
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;q=2;Zoo=";A=\\"Three\\""'),parameters,1,qMode="q")
		self.assertTrue(nWords==4,"ParseParameters qMode result: %i"%nWords)
		self.assertTrue(parameters=={'x':['X','1']},"Paremters: %s"%repr(parameters))
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;q=2;Zoo=";A=\\"Three\\""'),parameters,1+nWords)
		self.assertTrue(nWords==8,"ParseParameters qMode result 2: %i"%nWords)
		self.assertTrue(parameters=={'q':['q','2'],'zoo':['Zoo',';A="Three"']},"Paremters: %s"%repr(parameters))
		parameters={}
		nWords=ParseParameters(SplitWords('token ;X=1 ;y=2;Zoo=";A=\\"Three\\""'),parameters,1,caseSensitive=True)
		self.assertTrue(nWords==12,"ParseParameters caseSensitive result: %i"%nWords)
		self.assertTrue(parameters=={'X':['X','1'],'y':['y','2'],'Zoo':['Zoo',';A="Three"']},"Paremters: %s"%repr(parameters))
	
	def testCaseList(self):
		words=SplitWords(',hello, "Hi"(Hello), goodbye,  ')
		items=SplitItems(words,ignoreNulls=False)
		self.assertTrue(items[0]==[],"Leading empty item")
		self.assertTrue(items[1]==["hello"],"Token item")
		self.assertTrue(items[2]==['"Hi"',"(Hello)"],"Complex item")
		self.assertTrue(items[3]==['goodbye'],"Leading space item")
		self.assertTrue(items[4]==[],"Trailing empty item")
	
	def testCaseETag(self):
		eTag=HTTPETag()
		self.assertFalse(eTag.weak,"ETag constructor makes weak tags")
		self.assertTrue(eTag.tag is None,"ETag constructor tag not None")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords('W/"hello"'),eTag)
		self.assertTrue(nWords==3,"ParseETag result: %s"%nWords)
		self.assertTrue(eTag.weak,"Failed to parse weak tag")
		self.assertTrue(eTag.tag=="hello","Failed to parse ETag value")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords('w/ "h\\"ello"'),eTag)
		self.assertTrue(nWords==3,"ParseETag result: %s"%nWords)
		self.assertTrue(eTag.weak,"Failed to parse weak tag with lower case 'w'")
		self.assertTrue(eTag.tag=='h"ello',"Failed to unpick quoted pair from ETag value")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords('"hello"'),eTag)
		self.assertTrue(nWords==1,"ParseETag result: %s"%nWords)
		self.assertFalse(eTag.weak,"Failed to parse strong tag")
		self.assertTrue(eTag.tag=="hello","Failed to parse ETag value")
		eTag=HTTPETag()
		nWords=ParseETag(SplitWords(u'"hello"'),eTag)
		self.assertTrue(nWords==1,"ParseETag result: %s"%nWords)
		self.assertFalse(eTag.weak,"Failed to parse strong tag")
		self.assertTrue(eTag.tag=="hello","Failed to parse ETag value")

	def testCaseDate(self):
		timestamp822=ParseDate("Sun, 06 Nov 1994 08:49:37 GMT")	# RFC 822, updated by RFC 1123
		timestamp850=ParseDate("Sunday, 06-Nov-94 08:49:37 GMT")  # RFC 850, obsoleted by RFC 1036
		timestampC=ParseDate("Sun Nov  6 08:49:37 1994")		# ANSI C's asctime() format
		self.assertTrue(timestamp822==timestamp850,"RFC 850 timestamp parser")
		self.assertTrue(timestamp822==timestampC,"ANSI C timestamp parser")
		self.assertTrue(FormatDate(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT")
		try:
			timestamp822=ParseDate("Mon, 06 Nov 1994 08:49:37 GMT")	# Weekday mismatch
			self.fail("Weekday mismatch passed")
		except ValueError:
			pass
		self.assertTrue(FormatDate(timestamp822)=="Sun, 06 Nov 1994 08:49:37 GMT")
			
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
		self.assertTrue(request1.method=="GET")
		request2=HTTPRequest("http://www.domain2.com/","HEAD")
		self.assertTrue(request2.method=="HEAD")
		rm.QueueRequest(request1)
		rm.QueueRequest(request2)
		# ManagerLoop will process the queue until it blocks for more than the timeout (default, 60s)
		rm.ManagerLoop()
		response1=request1.response
		self.assertTrue(str(response1.protocolVersion)=="HTTP/1.1","Protocol in response1: %s"%response1.protocolVersion)
		self.assertTrue(response1.status==200,"Status in response1: %i"%response1.status)
		self.assertTrue(response1.reason=="You got it!","Reason in response1: %s"%response1.reason)
		self.assertTrue(request1.resBody==TEST_STRING,"Data in response1: %s"%request1.resBody)		
		response2=request2.response
		self.assertTrue(str(response2.protocolVersion)=="HTTP/1.1","Protocol in response2: %s"%response2.protocolVersion)
		self.assertTrue(response2.status==200,"Status in response2: %i"%response2.status)
		self.assertTrue(response2.reason=="You got it!","Reason in response2: %s"%response2.reason)
		self.assertTrue(request2.resBody=="","Data in response2: %s"%request2.resBody)
		
	def testCaseContinue(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		request1=HTTPRequest("http://www.domain1.com/file","PUT","123456\r\n\r\n")
		self.assertTrue(request1.method=="PUT")
		request2=HTTPRequest("http://www.domain1.com/file2","PUT","123456\r\n\r\n")
		request2.SetExpectContinue()
		rm.QueueRequest(request1)
		rm.QueueRequest(request2)
		# ManagerLoop will process the queue until it blocks for more than the timeout (default, forever) 
		#import pdb
		#pdb.set_trace()
		rm.ManagerLoop()
		response1=request1.response
		self.assertTrue(response1.status==200,"Status in response1: %i"%response1.status)
		self.assertTrue(response1.reason=="OK","Reason in response1: %s"%response1.reason)
		self.assertTrue(request1.resBody=='',"Data in response1: %s"%request1.resBody)		
		response2=request2.response
		self.assertTrue(response2.status==200,"Status in response2: %i"%response2.status)
		self.assertTrue(response2.reason=="OK","Reason in response2: %s"%response2.reason)
		self.assertTrue(request2.resBody=="","Data in response2: %s"%request2.resBody)
		# How do we test that response2 held back from sending the data before the redirect?

	def testCaseStreamedPut(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		request=HTTPRequest("http://www.domain1.com/file2","PUT",StringIO.StringIO("123456\r\n\r\n"))
		request.SetExpectContinue()
		rm.ProcessRequest(request)
		response=request.response
		self.assertTrue(response.status==200,"Status in response: %i"%response.status)
		self.assertTrue(response.reason=="OK","Reason in response: %s"%response.reason)
		self.assertTrue(request.resBody=="","Data in response: %s"%request.resBody)
		request=HTTPRequest("http://www.domain1.com/file","PUT",StringIO.StringIO("123456\r\n\r\n"))
		request.SetContentLength(10)
		rm.ProcessRequest(request)
		response=request.response
		self.assertTrue(response.status==200,"Status in response: %i"%response.status)
		self.assertTrue(response.reason=="OK","Reason in response: %s"%response.reason)
		self.assertTrue(request.resBody=="","Data in response: %s"%request.resBody)
		
	def testCaseStreamedGet(self):
		rm=FakeHTTPRequestManager()
		rm.httpUserAgent=None
		buff=StringIO.StringIO()
		request=HTTPRequest("http://www.domain1.com/","GET",'',buff)
		rm.ProcessRequest(request)
		response=request.response
		self.assertTrue(response.status==200,"Status in response: %i"%response.status)
		self.assertTrue(buff.getvalue()==TEST_STRING,"Data in response: %s"%request.resBody)		
		self.assertTrue(request.resBody=="","Data in streamed response: %s"%request.resBody)
			

class ChunkedTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		
	def tearDown(self):
		os.chdir(self.cwd)
	
	def ABC(self):
		for x in ("abc","defghi","j","klmn","","nopq","rstuvw","x","y","z"):
			yield x
			
	def untestCaseChunkedReader(self):
		r=HTTPChunkedWriter(stringSource=self.ABD())
		r.SetChunk(5)
		output=StringIO.StrionIO()
		self.assertTrue(string.join(list(r),'')=='9\r\nabcdefghi\r\n5\r\njklmn\r\nA\r\nnopqrstuvw\r\n3\r\nxyz\r\n0\r\n')
		r.SetChunk(1)
		output=StringIO.StrionIO()
		self.assertTrue(string.join(list(r),'')=='3\r\nabc\r\n6\r\ndefghi\r\n1\r\nj\r\n4\r\nklmn\r\n4\r\nnopq\r\n5\r\nrstuvw\r\n1\r\nx\r\n1\r\ny\r\n1\r\nz\r\n0\r\n')


if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	unittest.main()
