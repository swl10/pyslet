#! /usr/bin/env python

import unittest, random, decimal, math
from types import *

VERBOSE=False
HTTP_PORT=random.randint(1111,9999)

from threading import Thread
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from pyslet.vfs import OSFilePath as FilePath
from test_rfc5023 import MockRequest
import pyslet.rfc2396 as uri
import pyslet.rfc5023 as app
import pyslet.mc_edmx as edmx
import pyslet.pyds as pyds
import pyslet.iso8601 as iso8601

import traceback

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	pass


class MockODataServer:
	
	responseMap={
		('GET','/'):[(200,'application/xml; charset="utf-8"','root.xml')],
		('GET','/$metadata'):[(200,'application/xml; charset="utf-8"','metadata.xml')],	
		('GET','/Categories'):[(200,'application/xml; charset="utf-8"','categories.xml')],	
		}
		
	def __init__(self):
		self.state=0
		self.dataRoot=FilePath(FilePath(__file__).abspath().split()[0],'data_odatav2','mock_server')		
	
	def CheckCapabilityNegotiation(self,handler):
		"""Tests on the client:
		
		"If present on the request, the DataServiceVersion (section 2.2.5.3)
		header value states the version of the protocol used by the client to
		generate the request"
		
		and
		
		"If present on the request, the MaxDataServiceVersion (section 2.2.5.7)
		header value specifies the maximum version number the client can accept
		in a response. The client should set this value to the maximum version
		number of the protocol it is able to interpret"
		
		We require these to be both set to version 2.0."""
		major=minor=0
		dsv=handler.headers["DataServiceVersion"]
		if dsv is not None:
			major,minor,ua=ParseDataServiceVersion(dsv)
		if major!=2 or minor!=0:
			raise ValueError("DataServiceVersion: %s"%dsv)			
		maxDSV=handler.headers["MaxDataServiceVersion"]
		major=minor=0
		if maxDSV is not None:
			major,minor,sa=ParseMaxDataServiceVersion(maxDSV)
		if major!=2 or minor!=0:
			raise ValueError("MaxDataServiceVersion: %s"%maxDSV)			
			
	def HandleRequest(self,handler):
		try:
			self.CheckCapabilityNegotiation(handler)
			r=self.responseMap[('GET',handler.path)]
			if self.state>=len(r):
				r=r[-1]
			else:
				r=r[self.state]
			self.SendResponse(handler,r[0],r[1],r[2])
		except KeyError:
			handler.send_response(404)
			handler.send_header("Content-Length","0")
			handler.end_headers()
		except:
			handler.send_response(500)
			traceback.print_exception(*sys.exc_info())
			handler.send_header("Content-Length","0")
			handler.end_headers()
				
	
	def HandlePOST(self,handler):
		try:
			self.CheckCapabilityNegotiation(handler)
			raise KeyError
		except KeyError:
			handler.send_response(404)
			handler.send_header("Content-Length","0")
			handler.end_headers()
		except:
			handler.send_response(500)
			traceback.print_exception(*sys.exc_info())
			handler.send_header("Content-Length","0")
			handler.end_headers()
	
	def SendResponse(self,handler,code,rType,fileName):
		try:
			rPath=self.dataRoot.join(fileName)
			f=rPath.open('rb')
			rData=f.read()%{'port':HTTP_PORT}
			f.close()
		except IOError,e:
			code=500 
			rType='text/plain'
			rData=str(e)
		handler.send_response(code)
		handler.send_header("Content-type",rType)
		handler.send_header("Content-Length",str(len(rData)))
		handler.end_headers()
		handler.wfile.write(rData)
				
TEST_SERVER=MockODataServer()


class MockHandler(BaseHTTPRequestHandler):
	def do_GET(self):
		TEST_SERVER.HandleRequest(self)

	def do_POST(self):
		TEST_SERVER.HandleRequest(self)

	def log_request(self, code=None, size=None):
		BaseHTTPRequestHandler.log_request(self,code,size)
		# Prevent successful requests logging to stderr
		pass


def runODataServer():
	server=ThreadingHTTPServer(("localhost",HTTP_PORT), MockHandler)
	server.serve_forever()


def suite(prefix='test'):
	t=Thread(target=runODataServer)
	t.setDaemon(True)
	t.start()
	print "OData tests starting HTTP server on localhost, port %i"%HTTP_PORT
	loader=unittest.TestLoader()
	loader.testMethodPrefix=prefix
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(ODataTests),
		loader.loadTestsFromTestCase(ODataURILiteralTests),
		loader.loadTestsFromTestCase(ClientTests),
		loader.loadTestsFromTestCase(ODataURITests),
		loader.loadTestsFromTestCase(ServerTests),
		loader.loadTestsFromTestCase(SampleServerTests),
		loader.loadTestsFromTestCase(ODataStoreClientTests)		
		))
		

def load_tests(loader, tests, pattern):
	"""Called when we execute this file directly.
	
	This rather odd definition includes a larger number of tests, including one
	starting "tesx" which hit the sample OData services on the internet."""
	return suite('test')
	#return suite('tes')

	
from pyslet.odatav2 import *
import pyslet.rfc5023 as app
import pyslet.rfc4287 as atom
import pyslet.rfc2616 as http
import pyslet.iso8601 as iso
import pyslet.mc_csdl as edm

import sys


ODATA_SAMPLE_SERVICEROOT="http://services.odata.org/OData/OData.svc/"
ODATA_SAMPLE_READWRITE="http://services.odata.org/(S(readwrite))/OData/OData.svc/"


class ODataTests(unittest.TestCase):
	def testCaseConstants(self):
		# self.failUnless(IMSCP_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_v1p1","Wrong CP namespace: %s"%IMSCP_NAMESPACE)
		# self.failUnless(IMSCPX_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_extensionv1p2","Wrong extension namespace: %s"%IMSCPX_NAMESPACE)
		pass

class ODataURILiteralTests(unittest.TestCase):
	def testCaseNullLiteral(self):
		"""	nullLiteral = "null" """
		vType,value=ParseURILiteral("null")
		self.failUnless(vType is None,"null type: %s"%repr(vType))
		self.failUnless(value is None,"null value: %s"%repr(value))

	def testCaseBinaryLiteral(self):
		"""	binaryUriLiteral = caseSensitiveToken SQUOTE binaryLiteral SQUOTE
			binaryLiteral = hexDigPair
			caseSensitiveToken = "X" / "binary"
			; X is case sensitive binary is not
			hexDigPair = 2*HEXDIG [hexDigPair] """
		vType,value=ParseURILiteral("X'0A'")
		self.failUnless(vType==edm.SimpleType.Binary,"binary type: %s"%repr(vType))
		self.failUnless(value=='\x0a',"binary type: %s"%repr(value))
		vType,value=ParseURILiteral("X'0a'")
		self.failUnless(value=="\x0a","binary type: %s"%repr(value))
		try:
			vType,value=ParseURILiteral("x'0a'")
			self.fail("Syntax error")
		except ValueError:
			pass
		vType,value=ParseURILiteral("binary'0A'")
		self.failUnless(vType==edm.SimpleType.Binary,"binary type: %s"%repr(vType))
		self.failUnless(value=='\x0a',"binary type: %s"%repr(value))
		vType,value=ParseURILiteral("BINARY'0A'")
		self.failUnless(vType==edm.SimpleType.Binary,"binary type: %s"%repr(vType))
		self.failUnless(value=='\x0a',"binary type: %s"%repr(value))
		# gotta love those recursive rules
		vType,value=ParseURILiteral("X'deadBEEF'")
		self.failUnless(value=="\xde\xad\xbe\xef","binary type: %s"%repr(value))
		try:
			vType,value=ParseURILiteral("X'de'ad")
			self.fail("Spurious data")
		except ValueError:
			pass
	
	def testCaseBooleanLiteral(self):
		"""booleanLiteral = true / false
			true = "true" / "1"
			false = "false" / "0"
		
		The spec is ambiguous here because 0 and 1 are valid literals for
		integer types."""
		vType,value=ParseURILiteral("true")
		self.failUnless(vType==edm.SimpleType.Boolean,"boolean type: %s"%repr(vType))
		self.failUnless(value is True,"boolean value: %s"%repr(value))
		vType,value=ParseURILiteral("false")
		self.failUnless(vType==edm.SimpleType.Boolean,"boolean type: %s"%repr(vType))
		self.failUnless(value is False,"boolean value: %s"%repr(value))

	def testCaseIntLiteral(self):
		"""byteLiteral = 1*3DIGIT;
		int16Literal= sign 1*5DIGIT
		int32Literal= sign 1*10DIGIT
		sbyteliteral= sign 1*3DIGIT	
		All returned as an int32 with python int value."""
		vType,value=ParseURILiteral("0")
		self.failUnless(vType==edm.SimpleType.Int32,"0 type: %s"%repr(vType))
		self.failUnless(value==0,"0 value: %s"%repr(value))
		vType,value=ParseURILiteral("1")
		self.failUnless(vType==edm.SimpleType.Int32,"1 type: %s"%repr(vType))
		self.failUnless(value==1,"1 value: %s"%repr(value))
		vType,value=ParseURILiteral("2147483647")
		self.failUnless(vType==edm.SimpleType.Int32,"2147483647 type: %s"%repr(vType))
		self.failUnless(value==2147483647,"2147483647 value: %s"%repr(value))
		vType,value=ParseURILiteral("0000000000")
		self.failUnless(vType==edm.SimpleType.Int32,"0000000000 type: %s"%repr(vType))
		self.failUnless(value==0,"0000000000 value: %s"%repr(value))
		vType,value=ParseURILiteral("-2147483648")
		self.failUnless(vType==edm.SimpleType.Int32,"-2147483648 type: %s"%repr(vType))
		self.failUnless(value==-2147483648,"-2147483648 value: %s"%repr(value))
		for bad in [ "00000000000", "2147483648", "-2147483649","+1" ]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass
	
	def testCaseDateTimeLiteral(self):
		"""
			datetimeUriLiteral = "datetime" SQUOTE dateTimeLiteral SQUOTE
			
			dateTimeLiteral = year "-" month "-" day "T" hour ":" minute [":" second ["." nanoSeconds]]

			year = 4 *Digit;
			month = <any number between 1 and 12 inclusive>
			day = nonZeroDigit /("1" DIGIT) / ("2" DIGIT ) / "3" ("0" / "1")
			hour = nonZeroDigit / ("1" DIGIT) / ("2" zeroToFour)
			zeroToFour= <any nuumber between 0 and 4 inclusive>
			minute = doubleZeroToSixty
			second = doubleZeroToSixty
			nanoSeconds= 1*7Digit
		
		Strangely annoying but this is very close to iso, except the relaxed attitude
		to single-digits variants.
		"""
		vType,value=ParseURILiteral("datetime'2012-06-30T23:59'")
		self.failUnless(vType==edm.SimpleType.DateTime,"date time type: %s"%repr(vType))
		self.failUnless(isinstance(value,iso.TimePoint),"value type: %s"%repr(value))
		self.failUnless(str(value)=="2012-06-30T23:59","value: %s"%str(value))
		vType,value=ParseURILiteral("datetime'2012-06-30T23:59:59'")
		self.failUnless(vType==edm.SimpleType.DateTime,"date time type: %s"%repr(vType))
		self.failUnless(str(value)=="2012-06-30T23:59:59","value: %s"%str(value))
		vType,value=ParseURILiteral("datetime'2012-06-30T23:59:59.9999999'")
		self.failUnless(vType==edm.SimpleType.DateTime,"date time type: %s"%repr(vType))
		self.failUnless(value.GetCalendarString(ndp=-7)=="2012-06-30T23:59:59.9999999")
		# Now for the big one!
		vType,value=ParseURILiteral("datetime'2012-06-30T23:59:60'")
		self.failUnless(vType==edm.SimpleType.DateTime,"date time type for leap second: %s"%repr(vType))
		self.failUnless(str(value)=="2012-06-30T23:59:60","value for leap second: %s"%str(value))
		vType,value=ParseURILiteral("datetime'2012-06-30T24:00:00'")
		self.failUnless(vType==edm.SimpleType.DateTime,"date time extreme: %s"%repr(vType))
		self.failUnless(str(value)=="2012-06-30T24:00:00","date time extreme: %s"%str(value))
		# and now the crappy ones
		for crappy in [
			"datetime'2012-6-30T23:59:59'",
			"datetime'2012-06-1T23:59:59'",
			"datetime'2012-06-30T3:59:59'"
			]:
			vType,value=ParseURILiteral(crappy)
			self.failUnless(vType==edm.SimpleType.DateTime,"date time type: %s"%repr(vType))
		for bad in [
			"datetime'2012-02-30T23:59:59'",
			"datetime'12012-06-30T23:59:59'",
			"datetime'2012-00-30T23:59:59'",
			"datetime'2012-13-30T23:59:59'",
			"datetime'2012-06-00T23:59:59'",
			"datetime'2012-07-32T23:59:59'",
			"datetime'2012-06-30T24:59:59'",
			"datetime'2012-07-32T23:60:59'",	# surely illegal!
			"datetime'2012-06-30T23:59:61'",
			"datetime'2012-06-30T23:59:59.99999999'",
			"datetime'2012-06-30T23:59",
			"datetime2012-06-30T23:59'",
			"2012-06-30T23:59"
			 ]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,repr(value),edm.SimpleType.EncodeValue(vType)))
			except ValueError:
				pass

	def testCaseDecimalLiteral(self):
		"""decimalUriLiteral = decimalLiteral
			("M"/"m")
			decimalLiteral = sign 1*29DIGIT
			["." 1*29DIGIT]
		All returned as a python Decimal instance."""
		vType,value=ParseURILiteral("0M")
		self.failUnless(vType==edm.SimpleType.Decimal,"0M type: %s"%repr(vType))
		self.failUnless(isinstance(value,decimal.Decimal),"0M value type: %s"%repr(value))
		self.failUnless(value==0,"0M value: %s"%repr(value))
		vType,value=ParseURILiteral("1.1m")
		self.failUnless(vType==edm.SimpleType.Decimal,"1.1m type: %s"%repr(vType))
		self.failUnless(isinstance(value,decimal.Decimal),"1.1m value type: %s"%repr(value))
		self.failUnless(value*10==11,"1.1m value: %s"%repr(value))
		vType,value=ParseURILiteral("12345678901234567890123456789m")
		self.failUnless(vType==edm.SimpleType.Decimal,"29-digit type: %s"%repr(vType))
		self.failUnless(int(value.log10())==28,"29-digit log10 value: %s"%repr(value))
		vType,value2=ParseURILiteral("12345678901234567890123456789.12345678901234567890123456789m")
		self.failUnless(value2-value<0.13 and value2-value>0.12,"29digit.29digit value: %s"%repr(value2-value))
		vType,value=ParseURILiteral("-2147483648M")
		self.failUnless(vType==edm.SimpleType.Decimal,"-2147483648 type: %s"%repr(vType))
		self.failUnless(value==-2147483648,"-2147483648 value: %s"%repr(value))
		for bad in [ "123456789012345678901234567890m", "1.m", "1.123456789012345678901234567890m", "+1M" ]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass
	
	def testCaseDoubleLiteral(self):
		"""doubleLiteral = nonDecimalPoint / nonExp / exp / nan / negativeInfinity / postiveInfinity ("D" / "d")
		nonDecimalPoint= sign 1*17DIGIT
		nonExpDecimal = sign *DIGIT "." *DIGIT
		expDecimal = sign 1*DIGIT "." 16DIGIT ("e" / "E") sign 1*3DIGIT
		
		Is that really supposed to be 16DIGIT or 1*16DIGIT?  or even *16DIGIT?
		We decide to be generous here and accept *16DIGIT
		
		Also, the production allows .D and -.D as, presumably, valid forms of 0"""
		vType,value=ParseURILiteral("0D")
		self.failUnless(vType==edm.SimpleType.Double,"0D type: %s"%repr(vType))
		self.failUnless(type(value) is FloatType,"0D value type: %s"%repr(value))
		self.failUnless(value==0,"0D value: %s"%repr(value))
		vType,value=ParseURILiteral("1.1d")
		self.failUnless(vType==edm.SimpleType.Double,"1.1d type: %s"%repr(vType))
		self.failUnless(type(value) is FloatType,"1.1d value type: %s"%repr(value))
		self.failUnless(value*10==11,"1.1d value: %s"%repr(value))
		vType,value=ParseURILiteral("12345678901234567D")
		self.failUnless(vType==edm.SimpleType.Double,"17-digit type: %s"%repr(vType))
		self.failUnless(round(math.log10(value),3)==16.092,"29-digit log10 value: %s"%repr(value))
		vType,value=ParseURILiteral("-12345678901234567D")
		self.failUnless(vType==edm.SimpleType.Double,"17-digit negative type: %s"%repr(vType))
		self.failUnless(round(math.log10(-value),3)==16.092,"29-digit log10 value: %s"%repr(value))
		vType,value=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890D")
		self.failUnless(vType==edm.SimpleType.Double,"30digit.30digit type: %s"%repr(vType))
		self.failUnless(round(math.log10(value),3)==29.092,"30digit.30digit value: %s"%repr(value))
		vType,value=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890D")
		self.failUnless(round(math.log10(-value),3)==29.092,"30digit.30digit negative value: %s"%repr(value))
		vType,value=ParseURILiteral(".142D")
		self.failUnless(value==0.142,"Empty left value: %s"%repr(value))
		vType,value=ParseURILiteral("-.142D")
		self.failUnless(value==-0.142,"Empty left neg value: %s"%repr(value))
		vType,value=ParseURILiteral("3.D")
		self.failUnless(value==3,"Empty right value: %s"%repr(value))
		vType,value=ParseURILiteral("-3.D")
		self.failUnless(value==-3,"Empty right neg value: %s"%repr(value))
		vType,value=ParseURILiteral(".D")
		self.failUnless(value==0,"Empty left+right value: %s"%repr(value))
		vType,value=ParseURILiteral("-.D")
		self.failUnless(value==0,"Empty left+right neg value: %s"%repr(value))
		vType,value=ParseURILiteral("3.14159e000d")
		self.failUnless(round(value,3)==3.142,"zero exp: %s"%repr(value))
		vType,value=ParseURILiteral("-123456789012345678901234567890.1234567890123456E1d")
		self.failUnless(round(math.log10(-value),3)==30.092,"30.16 digits: %s"%repr(math.log10(-value)))
		vType,value=ParseURILiteral("NanD")
		self.failUnless(math.isnan(value),"Nan double: %s"%repr(value))
		vType,value=ParseURILiteral("INFD")
		self.failUnless(value>0 and math.isinf(value),"Inf double: %s"%repr(value))
		vType,value=ParseURILiteral("-INFD")
		self.failUnless(value<0 and math.isinf(value),"Negative Inf double: %s"%repr(value))		
		for bad in [ "123456789012345678D", "+1D", ".1e1d","+1.0E1d",
			"1.12345678901234567E10d","3.141Ed","3.141E1234d","3.141E+10d",".123E1D",
			"+NanD","-NanD","+INFD" ]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass
			

	def testCaseSingleLiteral(self):
		"""singleUriLiteral = singleLiteral ("F" / "f")
		singleLiteral = nonDecimalPoint / nonExp / exp / nan / negativeInfinity / postiveInfinity
		nonDecimalPoint = sign 1*8DIGIT
		nonExpDecimal = sign *DIGIT "." *DIGIT
		expDecimal = sign 1*DIGIT "." 8DIGIT ("e" / "E") sign 1*2DIGIT

		Float requires 8DIGIT, like double requires 16DIGIT.  Seems odd so we
		decide to be generous here and accept *8DIGIT
		
		The production allows .F and -.f as, presumably, valid forms of 0"""
		vType,value=ParseURILiteral("0F")
		self.failUnless(vType==edm.SimpleType.Single,"0f type: %s"%repr(vType))
		self.failUnless(type(value) is FloatType,"0f value type: %s"%repr(value))
		self.failUnless(value==0,"0f value: %s"%repr(value))
		vType,value=ParseURILiteral("1.1f")
		self.failUnless(vType==edm.SimpleType.Single,"1.1f type: %s"%repr(vType))
		self.failUnless(type(value) is FloatType,"1.1f value type: %s"%repr(value))
		self.failUnless(value*10==11,"1.1f value: %s"%repr(value))
		vType,value=ParseURILiteral("12345678F")
		self.failUnless(vType==edm.SimpleType.Single,"8-digit type: %s"%repr(vType))
		self.failUnless(value==12345678,"8-digit: %s"%repr(value))
		vType,value=ParseURILiteral("-12345678F")
		self.failUnless(vType==edm.SimpleType.Single,"8-digit negative type: %s"%repr(vType))
		self.failUnless(value==-12345678,"8-digit neg value: %s"%repr(value))
		vType,value=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890f")
		self.failUnless(vType==edm.SimpleType.Single,"30digit.30digit type: %s"%repr(vType))
		self.failUnless(round(math.log10(value),3)==29.092,"30digit.30digit value: %s"%repr(value))
		vType,value=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890F")
		self.failUnless(round(math.log10(-value),3)==29.092,"30digit.30digit negative value: %s"%repr(value))
		vType,value=ParseURILiteral(".142f")
		self.failUnless(value==0.142,"Empty left value: %s"%repr(value))
		vType,value=ParseURILiteral("-.142F")
		self.failUnless(value==-0.142,"Empty left neg value: %s"%repr(value))
		vType,value=ParseURILiteral("3.F")
		self.failUnless(value==3,"Empty right value: %s"%repr(value))
		vType,value=ParseURILiteral("-3.F")
		self.failUnless(value==-3,"Empty right neg value: %s"%repr(value))
		vType,value=ParseURILiteral(".f")
		self.failUnless(value==0,"Empty left+right value: %s"%repr(value))
		vType,value=ParseURILiteral("-.F")
		self.failUnless(value==0,"Empty left+right neg value: %s"%repr(value))
		vType,value=ParseURILiteral("3.14159e00F")
		self.failUnless(round(value,3)==3.142,"zero exp: %s"%repr(value))
		vType,value=ParseURILiteral("-123456789012345678901234567890.12345678E1F")
		self.failUnless(round(math.log10(-value),3)==30.092,"30.8 digits: %s"%repr(math.log10(-value)))
		vType,value=ParseURILiteral("3.E1F")
		self.failUnless(value==30,"Empty right exp value: %s"%repr(value))
		vType,value=ParseURILiteral("NanF")
		self.failUnless(math.isnan(value),"Nan single: %s"%repr(value))
		vType,value=ParseURILiteral("InfF")
		self.failUnless(value>0 and math.isinf(value),"Inf single: %s"%repr(value))
		vType,value=ParseURILiteral("-INFF")
		self.failUnless(value<0 and math.isinf(value),"Negative Inf single: %s"%repr(value))		
		for bad in [ "123456789F", "+1F", ".1e1F","+1.0E1F",
			"1.123456789E10F","3.141EF","3.141E023F","3.141E+10F",".123E1F",
			"+NanF","-NanF","+INFF" ]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass

	def testCaseGuidLiteral(self):
		"""	guidUriLiteral= "guid" SQUOTE guidLiteral SQUOTE
			guidLiteral = 8*HEXDIG "-" 4*HEXDIG "-" 4*HEXDIG "-" 12*HEXDIG
			
			This production appears to be in error as the CSDL uses the expected
			8-4-4-4-12 form.  We add an extra 4 hex digits, effectively
			inserting octets 8-11 of the UUID as the constant "FFFF".  This
			places our padded UUID in the 'reserved for future use' range.  We
			could then use this value to fix up issues when converting back to a
			string in future if desired.
			
			To be honest, I don't think the person who wrote this rule was having
			a good day because 8*HEXDIG means at least 8 hex-digits and not exactly
			8 hex digits as the author clearly intended."""
		vType,value=ParseURILiteral("guid'C0DEC0DE-C0DE-C0DE-C0DEC0DEC0DE'")
		self.failUnless(vType==edm.SimpleType.Guid,"guide type: %s"%repr(vType))
		self.failUnless(isinstance(value,uuid.UUID),"guide type: %s"%repr(value))
		self.failUnless(value.hex.lower()=='c0dec0dec0dec0deffffc0dec0dec0de',"guid value (missing bytes): %s"%repr(value))
		vType,value=ParseURILiteral("guid'cd04f705-390c-4736-98dc-a3baa6b3a283'")
		self.failUnless(vType==edm.SimpleType.Guid,"guide type: %s"%repr(vType))
		self.failUnless(isinstance(value,uuid.UUID),"guide type: %s"%repr(value))
		self.failUnless(value.hex.lower()=='cd04f705390c473698dca3baa6b3a283',"guid value (random): %s"%repr(value))
		for bad in [ 
			"guid'cd04g705-390c-4736-98dc-a3baa6b3a283'",
			"guid'cd04g705-390c-4736-98dc-a3baa6b3a283'",
			"guid'cd04f705-390g-4736-98dc-a3baa6b3a283'",
			"guid'cd04f705-390c-47g6-98dc-a3baa6b3a283'",
			"guid'cd04f705-390c-4736-9xdc-a3baa6b3a283'",
			"guid'cd04f705-390c-4736-98dc-a3baa6b3z283'",
			"guid'cd04f70-5390c-4736-98dc-a3baa6b3a283'",
			"guid'cd04f7-05390c-4736-98dc-a3baa6b3a283'",
			"guid'cd04f705-390c47-36-98dc-a3baa6b3a283'",
			"guid'cd04f705-390c-473698-dc-a3baa6b3a283'",
			"guid'cd04f705-390c-4736-98dca3b-aa6b3a283'",
			"guid'cd04f705-390c-4736-98dc-a3baa6b3a283FF'",
			"guid\"cd04f705-390c-4736-98dc-a3baa6b3a283\""]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass
	
	def testCaseInt64Literal(self):
		"""	int64UriLiteral= int64Literal ("L" / "l")
			int64Literal = sign 1*19DIGIT
			
			Return as a python long integer"""
		vType,value=ParseURILiteral("0L")
		self.failUnless(vType==edm.SimpleType.Int64,"0L type: %s"%repr(vType))
		self.failUnless(type(value)==LongType,"0L value type: %s"%repr(value))
		self.failUnless(value==0,"0L value: %s"%repr(value))
		vType,value=ParseURILiteral("1234567890123456789l")
		self.failUnless(vType==edm.SimpleType.Int64,"19-digit type: %s"%repr(vType))
		self.failUnless(value==1234567890123456789L,"19-digit value: %s"%repr(value))
		vType,value=ParseURILiteral("-1234567890123456789l")
		self.failUnless(vType==edm.SimpleType.Int64,"19-digit neg type: %s"%repr(vType))
		self.failUnless(value==-1234567890123456789L,"19-digit neg value: %s"%repr(value))
		for bad in [ "12345678901234567890L", "01234567890123456789l",
			 "+1l", "+0L" ]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass

	def testCaseStringLiteral(self):
		"""stringUriLiteral = SQUOTE [*characters] SQUOTE
			characters = UTF8-char """
		vType,value=ParseURILiteral("'0A'")
		self.failUnless(vType==edm.SimpleType.String,"string type: %s"%repr(vType))
		self.failUnless(value=='0A',"string type: %s"%repr(value))
		vType,value=ParseURILiteral("'0a'")
		self.failUnless(value=="0a","string type: %s"%repr(value))
		vType,value=ParseURILiteral("'Caf\xc3\xa9'")
		# When parsed from a URL we assume that %-encoding is removed
		# when the parameters are split leaving octet-strings that
		# are parsed.  So utf-8 encoding of strings must be removed
		# at the literal parsing stage
		self.failUnless(value==u"Caf\xe9","unicode string type: %s"%repr(value))
		# This next case is a shocker, the specification provides no way to escape SQUOTE
		# We support the undocumented doubling of the SQUOTE character.
		vType,value=ParseURILiteral("'Peter O''Toole'")
		self.failUnless(value==u"Peter O'Toole","double SQUOTE: %s"%repr(value))
		vType,value=ParseURILiteral("'Peter O%27Toole'")
		self.failUnless(value==u"Peter O%27Toole","%%-encoding ignored: %s"%repr(value))		
		for bad in [ "0A", "'0a","'Caf\xc3 Curtains'","'Peter O'Toole'"]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except UnicodeDecodeError:
				pass
			except ValueError:
				pass

	def testCaseDurationLiteral(self):
		"""
		timeUriLiteral = "time" SQUOTE timeLiteral SQUOTE
		timeLiteral = <Defined by the lexical representation for duration in [XMLSCHEMA2/2]>
		
		We test by using the examples from XMLSchema"""
		vType,value=ParseURILiteral("time'P1Y2M3DT10H30M'")
		self.failUnless(vType==edm.SimpleType.Time,"date time type: %s"%repr(vType))
		self.failUnless(isinstance(value,xsi.Duration),"value type: %s"%repr(value))
		self.failUnless(str(value)=="P1Y2M3DT10H30M","value: %s"%str(value))		
		vType,value=ParseURILiteral("time'-P120D'")
		self.failUnless(vType==edm.SimpleType.Time,"date time type: %s"%repr(vType))
		# There is no canonical representation so this is a weak test
		self.failUnless(str(value)=="-P0Y0M120D","value: %s"%str(value))
		for good in [
			"time'P1347Y'",
			"time'P1347M'",
			"time'P1Y2MT2H'",
			"time'P0Y1347M'",
			"time'P0Y1347M0D'",
			"time'-P1347M'"]:
			vType,value=ParseURILiteral(good)
			self.failUnless(vType==edm.SimpleType.Time,"date time type: %s"%repr(vType))
			self.failUnless(isinstance(value,xsi.Duration),"value type: %s"%repr(value))
		for bad in [
			"time'P-1347M'",
			"time'P1Y2MT'",
			"time'P1Y2M3DT10H30M",
			"timeP1Y2M3DT10H30M'",
			"P1Y2M3DT10H30M"
			]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,str(value),edm.SimpleType.EncodeValue(vType)))
			except ValueError:
				pass

	def testCaseDateTimeOffsetLiteral(self):
		"""
		dateTimeOffsetUriLiteral = "datetimeoffset" SQUOTE dateTimeOffsetLiteral SQUOTE
		dateTimeOffsetLiteral = <Defined by the lexical representation for datetime (including timezone offset) in [XMLSCHEMA2/2]>
		
		We test by using the examples from XMLSchema"""
		vType,value=ParseURILiteral("datetimeoffset'2002-10-10T12:00:00-05:00'")
		self.failUnless(vType==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(vType))
		self.failUnless(isinstance(value,iso.TimePoint),"value type: %s"%repr(value))
		self.failUnless(isinstance(value,iso.TimePoint),"value type: %s"%repr(value))
		for good in [
			"datetimeoffset'2002-10-10T17:00:00Z'",
			"datetimeoffset'2002-10-10T12:00:00Z'",
			"datetimeoffset'2002-10-10T12:00:00+05:00'",
			"datetimeoffset'2002-10-10T07:00:00Z'",
			"datetimeoffset'2002-10-10T00:00:00+05:00'",
			"datetimeoffset'2002-10-09T19:00:00Z'"
			]:
			vType,value=ParseURILiteral(good)
			self.failUnless(vType==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(vType))
			self.failUnless(isinstance(value,iso.TimePoint),"value type: %s"%repr(value))
		for bad in [
			"datetimeoffset'2002-10-10T17:00:00'",	# missing time zone
			"datetimeoffset'2002-10-10T17:00Z'",	# incomplete precision
			"datetimeoffset2002-10-10T17:00:00Z",	# missing quotes
			]:
			try:
				vType,value=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,str(value),edm.SimpleType.EncodeValue(vType)))
			except ValueError:
				pass
	
			
class ClientTests(unittest.TestCase):
	def testCaseConstructor(self):
		c=Client()
		self.failUnless(len(c.feeds)==0,"Default constructor, no feeds")
		self.failUnless(len(c.feedTitles)==0,"Default constructor, no feed titles")
		self.failUnless(isinstance(c,app.Client),"OData client not an APP client")
		self.failUnless(c.pageSize is None,"Default constructor page size")
		
	def tesxCaseServiceRoot(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		self.failUnless(len(c.feeds)==3,"Sample feed, number of feeds")
		self.failUnless(c.feedTitles["Products"]==ODATA_SAMPLE_SERVICEROOT+"Products","Sample feed titles")
		c=Client()
		c.SetService(ODATA_SAMPLE_SERVICEROOT)
		self.failUnless(len(c.feeds)==3 and c.feedTitles["Suppliers"]==ODATA_SAMPLE_SERVICEROOT+"Suppliers","Addition of sample feed")

	def tesxCaseFeedEntries(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		fURL=c.feedTitles['Products']
		f=c.RetrieveFeed(fURL)
		self.failUnless(isinstance(f,atom.Feed),"Feed instance")
		self.failUnless(len(f.Entry)==9,"Number of entries returned")
		c.pageSize=2
		f=c.RetrieveFeed(fURL)
		self.failUnless(len(f.Entry)==2,"Number of entries returned, restricted pageSize")
		entries=c.RetrieveEntries(fURL)
		count=0
		while True:
			try:
				e=entries.next()
				count=count+1
			except StopIteration:
				break
		self.failUnless(count==9,"Number of entries returned by generator")

	def tesxCaseOrderBy(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		c.pageSize=1
		fURL=c.feedTitles['Products']
		query={'$orderby':'ID asc'}
		entries=c.RetrieveEntries(fURL,query)
		self.failUnless(entries.next().Title.GetValue()=="Bread","Order by ID asc")
		query={'$orderby':'ID desc'}
		entries=c.RetrieveEntries(fURL,query)
		self.failUnless(entries.next().Title.GetValue()=="LCD HDTV","Order by ID desc")
		query={'$orderby':'Rating asc,Price desc'}
		entries=c.RetrieveEntries(fURL,query)
		entries.next() # skip the LCD HDTV again
		self.failUnless(entries.next().Title.GetValue()=="DVD Player","Order by ID low rating, high price")
		
	def tesxCaseProperties(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		c.pageSize=1
		fURL=c.feedTitles['Products']
		entries=c.RetrieveEntries(fURL)
		e=entries.next()
		self.failUnless(isinstance(e,Entry),"OData entry type override")
		self.failUnless(e['Rating']==4,"Rating property")
		self.failUnless(e['Price']==2.5,"Price property")
		self.failUnless(isinstance(e['ReleaseDate'],iso.TimePoint),"ReleaseDate type")
		self.failUnless(e['ReleaseDate'].date.century==19 and e['ReleaseDate'].date.year==92,"ReleaseDate year")		
		self.failUnless(e['DiscontinuedDate'] is None,"DiscontinuedDate NULL test")		
		for link in e.Link:
			if link.title=="Category":
				eCat=c.RetrieveEntry(link.ResolveURI(link.href))
				
	def tesxCaseReadWrite(self):
		c=Client(ODATA_SAMPLE_READWRITE)
		fURL=c.feedTitles['Categories']
		entries=c.RetrieveEntries(fURL)
		catID=None
		for e in entries:
			if e.Title.GetValue()=='Electronics':
				catID=e.AtomId.GetValue()		
		fURL=c.feedTitles['Products']
		e=Entry(None)
		now=iso.TimePoint()
		now.NowUTC()
		e.Title.SetValue("Pyslet Python Package")
		e.ChildElement(atom.Summary).SetValue("Python package for Standards in Learning, Education and Training")
		e['ID']=100
		e['ReleaseDate']=now.GetCalendarString()
		e['Rating']=5
		e['Price']=0.0
		if catID is not None:
			# Link this to Electronics
			e.AddLink('Category',catID)
		eResult=c.AddEntry(fURL,e)
		self.failUnless(isinstance(eResult,Entry),"OData entry type POST result")
		self.failUnless(eResult['Rating']==5,"Rating property on POST")
		self.failUnless(eResult['Price']==0.0,"Price property on POST")
		self.failUnless(isinstance(eResult['ReleaseDate'],iso.TimePoint),"ReleaseDate type on POST: %s"%repr(eResult['ReleaseDate']))
		self.failUnless(eResult['ReleaseDate']==now,"ReleaseDate match on POST")		
		self.failUnless(eResult['DiscontinuedDate'] is None,"DiscontinuedDate NULL test on POST")
		for link in eResult.Link:
			if link.title=="Category":
				eCat=c.RetrieveEntry(link.ResolveURI(link.href))
				self.failUnless(eCat['Name']=='Electronics')

	def tesxCaseMetadata(self):
		c=Client()
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout)
		c.SetService(ODATA_SAMPLE_SERVICEROOT)
		# By default this should load the metadata document, if present
		self.failUnless(isinstance(c.schemas['ODataDemo'],edm.Schema),"Failed to load metadata document")
		fURL=c.feedTitles['Products']
		f=c.RetrieveFeed(fURL)
		for e in f.Entry:
			self.failUnless(e.entityType is c.schemas['ODataDemo']['Product'],"Entry not associated with EntityType")
		e=c.Entry('ODataDemo.Product')
		self.failUnless(isinstance(e,Entry),"Entry creation from client")
		self.failUnless(e.entityType is c.schemas['ODataDemo']['Product'],"New entry not associated with EntityType")
					

class ODataStoreClientTests(unittest.TestCase):

	Categories={
		0:"Food",
		1:"Beverages",
		2:"Electronics"
		}
		
	def testCaseConstructor(self):
		sClient=ODataStoreClient('http://localhost:%i/'%HTTP_PORT)
		self.failUnless(isinstance(sClient,edm.ERStore),"ODataStore not an ERStore")
		s=sClient['ODataDemo']
		self.failUnless(isinstance(s,edm.Schema),"ODataStore schema")
	
	def testCaseEntityReader(self):
		sClient=ODataStoreClient('http://localhost:%i/'%HTTP_PORT)
		for c in sClient.EntityReader("Categories"):
			self.failUnless("ID" in c,"No key field in category")
			self.failUnless(self.Categories[c["ID"]]==c["Name"],"Category Name")


class ODataURITests(unittest.TestCase):

	def testCaseConstructor(self):
		dsURI=ODataURI('/')
		self.failUnless(dsURI.pathPrefix=='',"empty path prefix")
		self.failUnless(dsURI.resourcePath=='/',"resource path")
		self.failUnless(dsURI.queryOptions==[],'query options')
		self.failUnless(dsURI.navPath==[],"navPath: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('/','/x')
		self.failUnless(dsURI.pathPrefix=='/x',"non-empty path prefix")
		self.failUnless(dsURI.resourcePath==None,"resource path")
		dsURI=ODataURI('/x','/x')
		self.failUnless(dsURI.pathPrefix=='/x',"non-empty path prefix")
		self.failUnless(dsURI.resourcePath=='',"empty resource path, special case")
		self.failUnless(dsURI.navPath==[],"empty navPath, special case: %s"%repr(dsURI.navPath))		
		dsURI=ODataURI('/x.svc/Products','/x.svc')
		self.failUnless(dsURI.pathPrefix=='/x.svc',"svc path prefix")
		self.failUnless(dsURI.resourcePath=='/Products',"resource path")
		self.failUnless(len(dsURI.navPath)==1,"navPath: %s"%repr(dsURI.navPath))
		self.failUnless(type(dsURI.navPath[0][0]) is UnicodeType,"entitySet name type")
		self.failUnless(dsURI.navPath[0][0]=='Products',"entitySet name: Products")
		self.failUnless(dsURI.navPath[0][1]=={},"entitySet no key-predicate")		
		dsURI=ODataURI('Products','/x.svc')
		self.failUnless(dsURI.pathPrefix=='/x.svc',"svc path prefix")
		self.failUnless(dsURI.resourcePath=='/Products',"resource path")
		try:
			dsURI=ODataURI('Products','x.svc')
			self.fail("x.svc/Products  - illegal path")
		except ValueError:
			pass
	
	def testCaseEntitySet(self):
		dsURI=ODataURI("Products()?$format=json&$top=20&$skip=10&space='%20'",'/x.svc')
		self.failUnless(dsURI.resourcePath=='/Products()',"resource path")
		self.failUnless(dsURI.queryOptions==['$format=json','$top=20','$skip=10',"space='%20'"],'query options')
		self.failUnless(dsURI.navPath==[(u'Products',{})],"entitySet: Products, found %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products()/$count','/x.svc')
		self.failUnless(dsURI.resourcePath=='/Products()/$count',"resource path")
		self.failUnless(dsURI.queryOptions==[],'query options')		
		self.failUnless(dsURI.navPath==[(u'Products',{}),(u"$count",{})],"path: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products(1)/$value','/x.svc')
		self.failUnless(dsURI.navPath==[(u'Products',{'':1}),(u"$value",{})],"path: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products(x=1,y=2)','/x.svc')
		self.failUnless(dsURI.navPath==[(u'Products',{u'x':1,u'y':2})],"path: %s"%repr(dsURI.navPath))
		
			
class ServerTests(unittest.TestCase):
	
	def setUp(self):
		self.sampleServerData=FilePath(FilePath(__file__).abspath().split()[0],'data_odatav2','sample_server')
		
	def tearDown(self):
		pass
		
	def testCaseConstructor(self):
		s=Server()
		self.failUnless(len(s.service.Workspace)==1,"Service not returning a single Workspace child")
		self.failUnless(s.service.Workspace[0].Title.GetValue()=="Default","Service not returning a single Workspace child")		
		self.failUnless(len(s.service.Workspace[0].Collection)==0,"Workspace not empty")
		self.failUnless(isinstance(s.serviceRoot,uri.URI),"Service root not a URI")
		# feed=s.GetFeed('Test')
		# self.failUnless(feed is None,"Missing feed")
		
	def testCaseCapability(self):
		"""Tests capability negotiation of the server:
		
		"When the server receives a request, it must validate that the version
		number specified in the DataServiceVersion ... is less than or equal to
		the maximum version number it supports. If it is not, then the server
		must return a response with a 4xx response code, as described in
		[RFC2616]. The server should also return a description of the error
		using the error format defined in Error Response (section 2.2.8.1)."

		"If present on the request, the MaxDataServiceVersion (section 2.2.5.7)
		header value specifies the maximum version number the client can accept
		in a response."

		and...
		
		"On a response from the server to the client, the DataServiceVersion
		(section 2.2.5.3) header should be specified."
		
		"""
		s=Server()
		s.debugMode=True
		request=MockRequest('/')
		request.Send(s)
		self.failUnless(request.responseCode==200,"No DataServiceVersion:\n\n"+request.wfile.getvalue())
		self.failUnless('DataServiceVersion' in request.responseHeaders,"Missing DataServiceVersion in response")
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.failUnless(major==2 and minor==0,"No version should return 2.0")
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.Send(s)
		self.failUnless(request.responseCode==200,"Version 1.0 request:\n\n"+request.wfile.getvalue())
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.failUnless(major==1 and minor==0,"Version 1.0 request should return 1.0 response")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.0; current request")
		request.Send(s)
		self.failUnless(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.failUnless(major==2 and minor==0,"Version 2.0 request should return 2.0 response")				
		# Should be OK
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.1; future request")
		request.Send(s)
		self.failUnless(request.responseCode==400,"Version mismatch error response: %i"%request.responseCode)
		doc=Document()
		doc.Read(src=request.wfile.getvalue())
		error=doc.root
		self.failUnless(isinstance(error,Error),"Expected an error instance")
		self.failUnless(error.Code.GetValue()=="DataServiceVersionMismatch","Error code")
		self.failUnless(error.Message.GetValue()=="Maximum supported protocol version: 2.0","Error message")
		self.failUnless(error.InnerError is None,"No inner error")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.1; future request")
		request.SetHeader('Accept',"application/json")
		request.Send(s)
		self.failUnless(request.responseCode==400,"Version mismatch error response")
		self.failUnless(request.responseHeaders['Content-Type']=="application/json","Expected JSON response")
		doc=json.loads(request.wfile.getvalue())
		self.failUnless(len(doc)==1,"Expected a single error object")
		self.failUnless(len(doc['error'])==2,"Expected two children")
		self.failUnless(doc['error']['code']=="DataServiceVersionMismatch","Error code")
		self.failUnless(doc['error']['message']=="Maximum supported protocol version: 2.0","Error message")
		self.failIf('innererror' in doc['error'],"No inner error")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(s)
		self.failUnless(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.failUnless(major==1 and minor==0,"MaxVersion 1.0 request should return 1.0 response: %i.%i"%(major,minor))				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"2.0; current max")
		request.Send(s)
		self.failUnless(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.failUnless(major==2 and minor==0,"MaxVersion 2.0 request should return 2.0 response")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"2.1; future max")
		request.Send(s)
		self.failUnless(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.failUnless(major==2 and minor==0,"MaxVersion 2.1 request should return 2.0 response")				

	def testCaseServiceRoot(self):
		"""The resource identified by [the service root] ... MUST be an AtomPub Service Document"""
		s=Server()
		request=MockRequest('/')
		request.Send(s)
		self.failUnless(request.responseCode==200)		
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,app.Service),"Service root not an app.Service")
		# An empty server has no workspaces
		self.failUnless(len(doc.root.Workspace)==1,"Empty server = 1 workspace")
		self.failUnless(len(doc.root.Workspace[0].Collection)==0,"Empty Server = no collections")
		self.failUnless(doc.root.GetBase()==str(s.serviceRoot),"Non-matching service root: base=%s, root=%s"%(repr(doc.root.GetBase()),repr(str(s.serviceRoot))))
		
	def testCaseModel(self):
		"""With a simple OData server we set the model manually"""
		s=Server()
		self.failUnless(s.model is None,"no model initially")
		# Load the model document
		doc=edmx.Document()
		mdPath=self.sampleServerData.join('metadata.xml')
		with mdPath.open('rb') as f:
			doc.Read(f)
		s.SetModel(doc.root)
		# at this point, the server's model root is available as model
		self.failUnless(s.model is doc.root,"model attribute")		
		

class SampleServerTests(unittest.TestCase):
	
	def setUp(self):
		"""
		The scheme and Service Root for this sample is http://host/service.svc.
		
		A Customer Entity Type instance exists with EntityKey value ALFKI.

		A total of 91 Customer Entity Type instances exist.

		An Employee Entity Type instance exists with EntityKey value 1.

		Two Order Entity Type instances exist, one with EntityKey value 1 and
		the other with EntityKey value 2. Order 1 and 2 are associated with
		Customer ALFKI.

		Two OrderLine Entity Type instances exist, one with EntityKey value 100
		and the other with EntityKey value 200. OrderLine 100 is associated with
		Order 1 and OrderLine 200 with Order 2.

		Two Document Entity Type instances exist, one with EntityKey value 300
		and the other with EntityKey value 301."""
		self.sampleServerData=FilePath(FilePath(__file__).abspath().split()[0],'data_odatav2','sample_server')
		self.svc=Server('http://host/service.svc')
		self.svc.debugMode=True
		doc=pyds.Document()
		mdPath=self.sampleServerData.join('metadata.xml')
		with mdPath.open('rb') as f:
			doc.Read(f)
		self.ds=doc.root.DataServices
		self.svc.SetModel(doc.root)
		customers=self.ds['SampleModel.SampleEntities.Customers']
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(90):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		orders=self.ds['SampleModel.SampleEntities.Orders']
		now=iso8601.TimePoint()
		now.Now()
		orders.data[1]=(1,now)
		orders.data[2]=(2,now)
		association=self.ds['SampleModel.SampleEntities.Orders_Customers']
		association.Associate('ALFKI',1)
		association.Associate('ALFKI',2)
		customersByCity=self.ds['SampleModel.SampleEntities.CustomersByCity']
		customersByCity.Bind(self.CustomersByCity)
	
	def CustomersByCity(self,f,params,key=None):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		city=params.get('city','Chunton')
		if key is None:
			return self.CustomersByCityGen(customers,city)
		else:
			e=customers[key]
			if e['Address']['City']==city:
				return e
			else:
				raise KeyError(key)
	
	def CustomersByCityGen(self,customers,city):
		for customer in customers.data.itervalues():
			if customer[2][1]==city:
				yield customers[customer[0]]
				
	def tearDown(self):
		pass
		
	def testCaseServiceRoot(self):
		"""The resource identified by [the service root] ... MUST be an AtomPub Service Document"""
		request=MockRequest('/service.svc')
		request.Send(self.svc)
		self.failUnless(request.responseCode==307)		
		self.failUnless(request.responseHeaders['Location']=='http://host/service.svc/',"Expected redirect")
		request=MockRequest('/service.svc/')	
		request.Send(self.svc)
		self.failUnless(request.responseCode==200,"Service root response: %i"%request.responseCode)		
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,app.Service),"Service root not an app.Service")
		self.failUnless(len(doc.root.Workspace)==1,"Sample server has 1 workspace")
		self.failUnless(len(doc.root.Workspace[0].Collection)==6,"Sample service has 5 entity sets")
	
	def testCaseEntitySet1(self):
		"""EntitySet names MAY be directly followed by open and close parenthesis."""		
		request1=MockRequest('/service.svc/Customers')
		request2=MockRequest('/service.svc/Customers()')
		request1.Send(self.svc)
		request2.Send(self.svc)
		self.failUnless(request1.responseCode==200)		
		self.failUnless(request2.responseCode==200)
		doc1=app.Document()
		doc1.Read(request1.wfile.getvalue())		
		doc2=app.Document()
		doc2.Read(request2.wfile.getvalue())		
		output=doc1.DiffString(doc2)
		self.failUnless(request1.wfile.getvalue()==request2.wfile.getvalue(),"Mismatched responses with (): \n%s"%(output))

	def testCaseEntitySet2(self):
		"""If an EntitySet is not in the default EntityContainer, then the URI
		MUST qualify the EntitySet name with the EntityContainer name.
		
		Although not explicitly stated, it seems that an entity set MAY NOT be
		prefixed with the container name if it is in the default
		EntityContainer.  Witness the error from
		http://services.odata.org/OData/OData.svc/DemoService.Products"""
		request=MockRequest('/service.svc/Content')
		request.Send(self.svc)
		self.failUnless(request.responseCode==404,"Unqualified entity set from non-default container")
		request=MockRequest('/service.svc/ExtraEntities.Content')
		request.Send(self.svc)
		self.failUnless(request.responseCode==200,"Qualified entity set from non-default container")
		request=MockRequest('/service.svc/SampleEntities.Customers')
		request.Send(self.svc)
		self.failUnless(request.responseCode==404,"Qualified entity set from default container")
	
	def testCaseEntitProperty(self):
		"""If the prior URI path segment identifies an EntityType instance in
		EntitySet ES1, this value MUST be the name of a declared property or
		dynamic property, of type EDMSimpleType, on the base EntityType of set
		ES1
		
		If the prior URI path segment represents an instance of ComplexType CT1,
		this value MUST be the name of a declared property defined on
		ComplexType CT1."""
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		# Add test case of a property on a sub-type perhaps?
		request=MockRequest("/service.svc/Customers('ALFKI')/Title")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)		
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)		
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/ZipCode")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)		
	
	def testCaseComplexProperty(self):
		"""If the prior URI path segment identifies an instance of an EntityType
		ET1, this value MUST be the name of a declared property or dynamic
		property on type ET1 which represents a ComplexType instance.
		
		If the prior URI path segment identifies an instance of a ComplexType
		CT1, this value MUST be the name of a declared property on CT1 which
		represents a ComplexType instance."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		# TODO: sample data doesn't have any nested Complex properties
	
	def testCaseNavProperty(self):
		"""If the prior URI path segment identifies an instance of an EntityType
		ET1, this value MUST be the name of a NavigationProperty on type ET1.
		
		If the URI path segment preceding an entityNavProperty segment is
		"$links", then there MUST NOT be any subsequent path segments in the URI
		after the entityNavProperty. If additional segments exist, the URI MUST
		be treated as invalid"""
		request=MockRequest("/service.svc/Customers('ALFKI')/Orders")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders/dummy")
		request.Send(self.svc)
		self.failUnless(request.responseCode==400)
		
	def testCaseKeyPredicateSingle(self):
		"""An EntityKey consisting of a single EntityType property MAY be
		represented using the "<Entity Type property name> = <Entity Type
		property value>" syntax"""
		request1=MockRequest("/service.svc/Customers('ALFKI')")
		request2=MockRequest("/service.svc/Customers(CustomerID='ALFKI')")
		request1.Send(self.svc)
		request2.Send(self.svc)
		self.failUnless(request1.responseCode==200)		
		self.failUnless(request2.responseCode==200)
		self.failUnless(request1.wfile.getvalue()==request2.wfile.getvalue(),"Mismatched responses with ()")

	def testCaseKeyPredicateComplex(self):
		"""The order in which the properties of a compound EntityKey appear in
		the URI MUST NOT be significant"""
		# TODO, sample data has no compound keys
		pass

	def testCaseAllInstances(self):
		"""... serviceRoot "/" entitySet MUST identify all instances of the base
		EntityType or any of the EntityType's subtypes within the specified
		EntitySet specified in the last URI segment."""
		request=MockRequest('/service.svc/Customers')
		request.Send(self.svc)
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Customers")
		self.failUnless(len(doc.root.Entry)==91,"Sample server has 91 Customers")
		request=MockRequest("/service.svc/CustomersByCity?city='Chunton'")
		# import pdb;pdb.set_trace()
		request.Send(self.svc)
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /CustomersByCity")
		self.failUnless(len(doc.root.Entry)==1,"Sample server has 1 Customer in Chunton")
				
	def testCaseMiscURI(self):
		"""Example URIs not tested elsewhere:"""
		for u in [
			"/service.svc/Customers",
			"/service.svc/Customers('ALFKI')/Orders"
			]:
			request=MockRequest(u)
			request.Send(self.svc)
			self.failUnless(request.responseCode==200,"misc URI failed (path): %s"%u)
						
		
if __name__ == "__main__":
	VERBOSE=True
	unittest.main()
